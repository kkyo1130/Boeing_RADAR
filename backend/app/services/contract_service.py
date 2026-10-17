from datetime import datetime, timezone
import math
import os
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, text
from app.models.contract_observation import ContractClearance, ContractEvent, ContractValidationSettings
from app.models.flight import Flight
from app.services.flight_service import get_flight


def utc_now():
    return datetime.now(timezone.utc)


def max_age():
    value = float(os.getenv("RADAR_OBSERVATION_MAX_AGE_SECONDS", "30"))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("RADAR_OBSERVATION_MAX_AGE_SECONDS must be finite and positive")
    return value


def lock_writes(db, flight_id):
    # Serialize read/check/write, including duplicate retries and new-clearance races.
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    else:
        db.scalar(select(Flight).where(Flight.flight_id == flight_id).with_for_update())


def clearance(db, clearance_id):
    result = db.get(ContractClearance, clearance_id)
    if result is None:
        raise HTTPException(404, "Contract clearance not found")
    return result


def reserve(db, flight_id):
    lock_writes(db, flight_id)
    get_flight(db, flight_id, active=True)
    for old in db.scalars(select(ContractClearance).where(
            ContractClearance.flight_id == flight_id, ContractClearance.active.is_(True))):
        from app.services.operations import record
        record(db, flight_id, old.clearance_id, "CLEARANCE_SUPERSEDED", utc_now().isoformat(),
               decision=snapshot(db, old))
        old.active = False
        from app.models.operations import Incident
        for incident in db.scalars(select(Incident).where(Incident.clearance_id == old.clearance_id,
                                                        Incident.status == "OPEN")):
            incident.status = "SUPERSEDED"
            record(db, flight_id, old.clearance_id, "INCIDENT_SUPERSEDED", utc_now().isoformat(),
                   incident_id=incident.incident_id, reason="new_clearance")
    c = ContractClearance(clearance_id=f"V1-CLR-{uuid4()}", flight_id=flight_id,
                          created_at=utc_now().isoformat(), active=True, latest={})
    db.add(c)
    db.commit()
    return snapshot(db, c)


def confirm_settings(db, clearance_id, payload):
    # SQLite lock must precede reads, just like observation submissions.
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    c = clearance(db, clearance_id)
    if db.get_bind().dialect.name != "sqlite":
        db.scalar(select(Flight).where(Flight.flight_id == c.flight_id).with_for_update())
        db.refresh(c)
    get_flight(db, c.flight_id, active=True)
    if not c.active:
        raise HTTPException(409, "Clearance superseded")
    if db.get(ContractValidationSettings, clearance_id) or db.scalar(select(ContractEvent).where(
            ContractEvent.clearance_id == clearance_id)):
        raise HTTPException(409, "Confirm settings once, before observations")
    stamp = utc_now().isoformat()
    data = payload.model_dump(mode="json")
    db.add(ContractValidationSettings(clearance_id=clearance_id, confirmed_at=stamp, settings=data))
    db.commit()
    return {"clearance_id": clearance_id, "confirmed_at": stamp, "settings": data}


def time_reasons(payload, clock, created_at=None):
    reasons = []
    if payload.processed_at > clock:
        reasons.append("future_processed_at")
    if payload.captured_at is None:
        reasons.append("capture_time_unknown")
    else:
        if payload.captured_at > clock:
            reasons.append("future_capture")
        if (clock - payload.captured_at).total_seconds() > max_age():
            reasons.append("stale_observation")
        if created_at and payload.captured_at < datetime.fromisoformat(created_at):
            reasons.append("before_clearance")
    return reasons


def receive(db, payload):
    lock_writes(db, payload.flight_id)
    data = payload.model_dump(mode="json")
    previous = db.get(ContractEvent, payload.event_id)
    if previous:
        if previous.payload != data:
            raise HTTPException(409, "Event ID already used with different content")
        # Retry is a receipt replay, never a new observation or resolution.
        return receipt(previous, replayed=True)
    get_flight(db, payload.flight_id, active=True)
    c = None
    if payload.clearance_id:
        c = clearance(db, payload.clearance_id)
        if c.flight_id != payload.flight_id:
            raise HTTPException(409, "Clearance belongs to another flight")
        if not c.active:
            raise HTTPException(409, "Clearance superseded by a new instruction")
    clock = utc_now()
    reasons = time_reasons(payload, clock, c.created_at if c else None)
    prior_channel = db.scalar(select(ContractEvent).where(
        ContractEvent.flight_id == payload.flight_id,
        ContractEvent.channel_id == payload.channel_id,
        ContractEvent.accepted.is_(True)
    ).order_by(ContractEvent.processed_at.desc()).limit(1))
    if prior_channel and payload.processed_at <= datetime.fromisoformat(prior_channel.processed_at):
        reasons.append("out_of_order")
    if payload.event_type == "health":
        # Health has no capture; ordering uses the producer's emitted processing time.
        reasons = [r for r in reasons if r != "capture_time_unknown"]
        if (clock - payload.processed_at).total_seconds() > max_age():
            reasons.append("stale_health")
    else:
        if db.scalar(select(ContractEvent).where(
                ContractEvent.observation_id == payload.observation_id)):
            raise HTTPException(409, "Observation ID already used")
        if db.scalar(select(ContractEvent).where(
                ContractEvent.flight_id == payload.flight_id,
                ContractEvent.channel_id == payload.channel_id,
                ContractEvent.sample_id == payload.sample_id)):
            raise HTTPException(409, "Sample already used; correction requires a new sample")
        latest = c.latest.get(payload.source)
        if payload.intent == "initial" and latest is not None:
            raise HTTPException(409, "Source already exists; submit a correction")
        if payload.intent == "correction":
            if latest is None or latest["observation_id"] != payload.supersedes_observation_id:
                raise HTTPException(409, "Correction must reference the latest observation of this source")
            old_capture = latest["captured_at"]
            if old_capture and (payload.captured_at is None or payload.captured_at <= datetime.fromisoformat(old_capture)):
                reasons.append("correction_not_newer")
        if payload.source != "ATC" and "ATC" not in c.latest:
            raise HTTPException(409, "ATC required before readback or cockpit")
        if payload.source == "COCKPIT" and "READBACK" not in c.latest:
            raise HTTPException(409, "Readback required before cockpit")
        if payload.source != "ATC":
            atc = c.latest["ATC"]
            if atc["captured_at"] and payload.captured_at and payload.captured_at < datetime.fromisoformat(atc["captured_at"]):
                reasons.append("before_atc")
    accepted = not reasons
    event = ContractEvent(event_id=payload.event_id, observation_id=payload.observation_id,
        flight_id=payload.flight_id, clearance_id=payload.clearance_id,
        channel_id=payload.channel_id, sample_id=payload.sample_id, source=payload.source,
        processed_at=payload.processed_at.isoformat(), received_at=clock.isoformat(),
        accepted=accepted, reasons=reasons, payload=data)
    db.add(event)
    if accepted and payload.event_type == "observation":
        # Input acceptance and safety verdict are separate. Null/low-quality are retained.
        updated = dict(c.latest)
        if payload.source == "ATC":
            # Changed instruction content invalidates all prior dependent observations.
            updated = {}
            from app.models.operations import Incident
            for incident in db.scalars(select(Incident).where(Incident.clearance_id == c.clearance_id,
                                                            Incident.status == "OPEN")):
                incident.status = "SUPERSEDED"
                from app.services.operations import record
                record(db, c.flight_id, c.clearance_id, "INCIDENT_SUPERSEDED", clock.isoformat(),
                       incident_id=incident.incident_id, reason="atc_instruction_changed")
        updated[payload.source] = data
        c.latest = updated
    from app.services.operations import record, reconcile
    record(db, payload.flight_id, payload.clearance_id, "INPUT_RECEIVED", clock.isoformat(),
           event_id=payload.event_id, accepted=accepted, reasons=reasons, intent=payload.intent)
    if c:
        db.flush()
        decision = snapshot(db, c)
        reconcile(db, c, decision, clock.isoformat())
        record(db, c.flight_id, c.clearance_id, "DECISION", clock.isoformat(), decision=decision)
    # Receipt, incident transition, trace and latest pointer share the transaction.
    db.commit()
    return receipt(event)


def receipt(event, replayed=False):
    return {"event_id": event.event_id, "accepted": event.accepted,
            "replayed": replayed, "received_at": event.received_at, "reasons": event.reasons}


def snapshot(db, c):
    from app.schemas.observation_contract import ObservationContract
    reasons = []
    if not c.active:
        reasons.append("superseded_clearance")
    flight = get_flight(db, c.flight_id)
    if flight.status != "ACTIVE":
        reasons.append("flight_ended")
    clock = utc_now()
    for source in ("ATC", "READBACK", "COCKPIT"):
        data = c.latest.get(source)
        if data is None:
            reasons.append(f"missing_{source.lower()}")
            continue
        payload = ObservationContract.model_validate(data)
        reasons.extend(time_reasons(payload, clock, c.created_at))
        if payload.health.status != "available":
            reasons.append(payload.health.reason)
        latest_channel = db.scalar(select(ContractEvent).where(
            ContractEvent.flight_id == c.flight_id,
            ContractEvent.channel_id == payload.channel_id,
            ContractEvent.accepted.is_(True)
        ).order_by(ContractEvent.processed_at.desc()).limit(1))
        if latest_channel and latest_channel.payload["health"]["status"] != "available":
            reasons.append(latest_channel.payload["health"]["reason"])
        requested = c.latest.get("ATC", {}).get("fields", {})
        for key, field in data["fields"].items():
            if requested.get(key) is not None and field is None:
                reasons.append(f"missing_{key}")
            if field:
                if field["value"] is None:
                    reasons.append(field["reason"])
                if field["quality"]["status"] != "acceptable":
                    reasons.extend(field["quality"]["reasons"])
        if any(e["availability"] != "available" for e in data["evidence"]):
            reasons.append("evidence_unavailable")
    from app.services.validation.decision import decide
    decision = decide(db, c, clock)
    decision_reasons = decision.pop("reasons")
    if db.get(ContractValidationSettings, c.clearance_id):
        reasons = decision_reasons  # Only requested, checked fields determine the verdict.
    else:
        reasons.extend(decision_reasons)
    return {"clearance_id": c.clearance_id, "flight_id": c.flight_id,
            "created_at": c.created_at, "active": c.active,
            "reasons": sorted(set(reasons)), "observations": c.latest, **decision}
