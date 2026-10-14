"""Fresh, field-specific comparisons with separate error and resolution stages."""
from datetime import datetime
import re

from sqlalchemy import select
from app.models.contract_observation import ContractEvent, ContractValidationSettings
from app.models.flight import Flight
from app.schemas.observation_contract import ObservationContract
from app.schemas.validation_settings import ValidationSettings
from app.services.validation.rules import check_observation


def readback_context(context, data):
    # Preserve confirmed order/conditions. Numeric disagreement belongs to comparison,
    # not to a format error. Never copy the readback's action list into its reference.
    actions = context.expected_ordered_actions
    if actions is None:
        return context
    updated = []
    for action in actions:
        match = re.fullmatch(r"(altitude|heading) ([0-9]+)( (?:feet|degrees))?", action.casefold())
        if not match:
            return context.model_copy(update={"expected_ordered_actions": None})
        key, digits, suffix = match.groups()
        field = data["fields"][key]
        if field is None or field["value"] is None:
            return context.model_copy(update={"expected_ordered_actions": None})
        updated.append(f"{key} {str(field['value']).zfill(len(digits))}{suffix or ''}")
    return context.model_copy(update={"expected_ordered_actions": updated})


def inspect_input(db, c, data, settings, clock, *, historical=False, previous=None):
    from app.services.contract_service import time_reasons
    payload = ObservationContract.model_validate(data)
    context = settings.atc_context
    if payload.source == "READBACK":
        context = readback_context(context, data)
    result = check_observation(data, policy=settings.rule_policy, context=context, previous=previous)
    global_reasons = time_reasons(payload, clock, c.created_at)
    global_reasons.extend(issue.code for issue in result.issues if issue.field not in ("altitude", "heading"))
    if payload.health.status != "available":
        global_reasons.append(payload.health.reason)
    if not historical:
        channel_events = list(db.scalars(select(ContractEvent).where(
            ContractEvent.flight_id == c.flight_id, ContractEvent.channel_id == payload.channel_id)))
        if channel_events:
            last_received = max(event.received_at for event in channel_events)
            for event in channel_events:
                if event.received_at == last_received and not event.accepted:
                    global_reasons.extend(event.reasons)
                if event.accepted and event.payload["health"]["status"] != "available":
                    if datetime.fromisoformat(event.processed_at) >= payload.processed_at:
                        global_reasons.extend([event.payload["health"]["reason"], "new_observation_required"])
        attempts = list(db.scalars(select(ContractEvent).where(
            ContractEvent.clearance_id == c.clearance_id, ContractEvent.source == payload.source)))
        if attempts:
            last_received = max(event.received_at for event in attempts)
            for event in attempts:
                if event.received_at == last_received and not event.accepted:
                    global_reasons.extend(event.reasons)
    fields = {}
    for key in ("altitude", "heading"):
        field = getattr(payload.fields, key)
        reasons = list(global_reasons)
        reasons.extend(issue.code for issue in result.issues if issue.field == key)
        if field is None:
            reasons.append(f"missing_{key}")
        else:
            if field.value is None:
                reasons.append(field.reason)
            if field.quality.status != "acceptable":
                reasons.extend(field.quality.reasons)
            if field.model_score is None or field.model_score < settings.minimum_model_score:
                reasons.append("low_or_missing_model_score")
            evidence = {item.evidence_id: item for item in payload.evidence}
            if not field.evidence_ids or any(evidence[item].availability != "available" for item in field.evidence_ids):
                reasons.append("evidence_unavailable")
        fields[key] = {"eligible": not reasons, "reasons": sorted(set(reasons)),
                       "value": field.value if field else None}
    return {"rules": result.model_dump(mode="json"), "fields": fields}


def decide(db, c, clock):
    row = db.get(ContractValidationSettings, c.clearance_id)
    flight = db.scalar(select(Flight).where(Flight.flight_id == c.flight_id))
    blockers = []
    if not c.active:
        blockers.append("superseded_clearance")
    if flight.status != "ACTIVE":
        blockers.append("flight_ended")
    if row is None:
        blockers.append("validation_context_missing")
    settings = ValidationSettings.model_validate(row.settings) if row else None
    atc = c.latest.get("ATC")
    requested = [key for key in ("altitude", "heading") if atc and atc["fields"][key] is not None]
    stages = {}
    inspections = {}
    for source in ("ATC", "READBACK", "COCKPIT"):
        data = c.latest.get(source)
        stage = {"verdict": "UNVERIFIED", "reasons": list(blockers), "errors": [],
                 "comparisons": [], "rules": None}
        stages[source.lower()] = stage
        if data is None:
            stage["reasons"].append(f"missing_{source.lower()}")
            continue
        if settings is None:
            continue
        previous = None
        if data["supersedes_observation_id"]:
            event = db.scalar(select(ContractEvent).where(
                ContractEvent.observation_id == data["supersedes_observation_id"],
                ContractEvent.accepted.is_(True)))
            previous = event.payload if event else None
        inspection = inspect_input(db, c, data, settings, clock, previous=previous)
        inspections[source] = inspection
        stage["rules"] = inspection["rules"]
        for key in requested:
            stage["reasons"].extend(inspection["fields"][key]["reasons"])
        if not requested:
            stage["reasons"].append("atc_target_unavailable")
        if source == "ATC":
            if not stage["reasons"]:
                stage["verdict"] = "NORMAL"
            continue
        if stages["atc"]["verdict"] != "NORMAL":
            stage["reasons"].append("atc_unverified")
            continue
        if source == "COCKPIT" and stages["readback"]["verdict"] != "NORMAL":
            stage["reasons"].append("readback_not_verified")
            continue
        if blockers:
            continue
        for key in requested:
            field = inspection["fields"][key]
            if field["eligible"]:
                expected = inspections["ATC"]["fields"][key]["value"]
                mismatch = expected != field["value"]
                stage["comparisons"].append({"field": key, "expected": expected,
                    "actual": field["value"], "verdict": "MISMATCH" if mismatch else "NORMAL"})
                if mismatch:
                    stage["errors"].append({"field": "ALT" if key == "altitude" else "HDG",
                                             "expected": expected, "actual": field["value"]})
        if stage["errors"]:
            stage["verdict"] = "MISMATCH"
        elif not stage["reasons"]:
            stage["verdict"] = "NORMAL"

    resolutions = {}
    if settings and not blockers and stages["atc"]["verdict"] == "NORMAL":
        for source in ("READBACK", "COCKPIT"):
            data = c.latest.get(source)
            if not data or stages[source.lower()]["verdict"] != "NORMAL" or not data["supersedes_observation_id"]:
                continue
            history = {e.observation_id: e for e in db.scalars(select(ContractEvent).where(
                ContractEvent.accepted.is_(True),
                ContractEvent.clearance_id == c.clearance_id, ContractEvent.source == source,
                ContractEvent.observation_id.is_not(None)))}
            previous_id = data["supersedes_observation_id"]
            visited = set()
            while previous_id in history and previous_id not in visited:
                visited.add(previous_id)
                old = history[previous_id]
                parent = history.get(old.payload["supersedes_observation_id"])
                inspection = inspect_input(db, c, old.payload, settings,
                    datetime.fromisoformat(old.received_at), historical=True,
                    previous=parent.payload if parent else None)
                if any(inspection["fields"][key]["eligible"] and
                       inspection["fields"][key]["value"] != inspections["ATC"]["fields"][key]["value"] for key in requested):
                    resolutions[source.lower()] = "RESOLVED"
                    break
                previous_id = old.payload["supersedes_observation_id"]

    verdict, status, errors = "UNVERIFIED", "UNVERIFIED", []
    if stages["readback"]["verdict"] == "MISMATCH":
        verdict, status, errors = "MISMATCH", "READBACK_ERROR", stages["readback"]["errors"]
    elif stages["cockpit"]["verdict"] == "MISMATCH":
        verdict, status, errors = "MISMATCH", "SETTING_ERROR", stages["cockpit"]["errors"]
    elif all(stage["verdict"] == "NORMAL" for stage in stages.values()):
        verdict, status = "NORMAL", "RESOLVED" if resolutions else "VERIFIED"
    elif resolutions.get("readback") == "RESOLVED":
        status = "RESOLVED"  # Readback error resolved; never implies full verification.
    reasons = set(blockers)
    for stage in stages.values():
        stage["reasons"] = sorted(set(stage["reasons"]))
        reasons.update(stage["reasons"])
    return {"verdict": verdict, "status": status, "errors": errors,
            "stages": stages, "resolutions": resolutions, "reasons": sorted(reasons),
            "validation_context": {"confirmed_at": row.confirmed_at, "settings": row.settings} if row else None}
