"""Transactional v2 intake and provenance. Final comparison belongs to SPEC-005."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from app.core.enums import FlightStatus, EventType
from app.models.flight import Flight
from app.models.observation_v2 import V2FlightContext, V2Instruction, V2Segment, V2TraceEvent, V2Input
from app.schemas.receiving_v2 import ReceiverConfig
from app.schemas.structure_rules import StructurePolicy
from app.services.structure_rules import check_structure
from app.services.validation_v2 import evaluate
from app.services.incidents_v2 import reconcile, view
from app.services.safety_trace_service import record


class ReceivingError(Exception):
    def __init__(self, status, code, message, input_id=None, field_path=None):
        self.status, self.code, self.message = status, code, message
        self.input_id, self.field_path = input_id, field_path


def utc_now():
    return datetime.now(timezone.utc)


def stamp(now):
    return now.isoformat().replace("+00:00", "Z")


def parsed(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@contextmanager
def atomic(db):
    try:
        if db.get_bind().dialect.name == "sqlite":
            # Serialize intake with other intake writers and legacy flight ending.
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def context(db, flight_id, active=False, lock=False):
    stmt = select(Flight, V2FlightContext).join(V2FlightContext, V2FlightContext.flight_id == Flight.flight_id).where(Flight.flight_id == flight_id)
    if lock:
        stmt = stmt.with_for_update()
    row = db.execute(stmt).first()
    if row is None:
        raise ReceivingError(404, "NOT_FOUND", "v2 flight not found")
    flight, profile = row
    if active and flight.status != FlightStatus.ACTIVE:
        raise ReceivingError(409, "FLIGHT_ENDED", "Flight has ended")
    return flight, profile


def trace(db, profile, event_type, payload, now):
    row = V2TraceEvent(flight_id=profile.flight_id, event_type=event_type,
                       occurred_at=stamp(now), revision=profile.revision, snapshot=deepcopy(payload))
    db.add(row)
    db.flush()
    return row


def refresh_validation(db, profile, state, now, ended=False):
    active_ids = {target["instruction_id"] for target in state["targets"].values() if target}
    state["readbacks"] = {iid: value for iid, value in state.get("readbacks", {}).items() if iid in active_ids}
    evaluate(state, profile.policy, profile.callsign, now, persist=True, ended=ended)
    for item in reconcile(state, profile.flight_id, state["validation_snapshot"], now, ended=ended):
        trace(db, profile, "INCIDENT_UPDATED", item, now)
    from app.services.alerts.advisory_v2 import settle
    before_voice = deepcopy(state.get('voice'))
    voice = settle(state, profile.policy, profile.callsign, now, ended=ended)
    if before_voice != voice:
        trace(db, profile, 'VOICE_POLICY_CHANGED', {'episodes': voice['episodes'],
            'active_attempt': next((a for a in voice['attempts'].values() if a['status'] == 'PLAYING'), None)}, now)


def start(db, callsign):
    try:
        path = os.environ["RADAR_V2_CONFIG"]
        config = ReceiverConfig.model_validate_json(Path(path).read_text())
    except (KeyError, OSError, UnicodeError, ValidationError) as exc:
        raise ReceivingError(422, "INVALID_PAYLOAD", "Valid RADAR_V2_CONFIG is required", field_path="configuration") from exc
    if callsign not in config.callsigns:
        raise ReceivingError(422, "INVALID_PAYLOAD", "Callsign is not registered. Available: " + ", ".join(sorted(config.callsigns)), field_path="callsign")
    now = utc_now()
    with atomic(db):
        flight = Flight(flight_id="FLT2-" + uuid4().hex, started_at=stamp(now), status=FlightStatus.ACTIVE)
        db.add(flight)
        db.flush()
        profile = V2FlightContext(flight_id=flight.flight_id, callsign=callsign,
            callsign_registry=config.callsigns, policy=config.freshness.model_dump() if config.freshness else None,
            revision=0, state={"targets": {"ALT": None, "HDG": None}, "readback_required": None,
                "channels": {}, "current": {"COCKPIT": {}, "READBACK": {}}, "latest_atc_input_id": None,
                "structure_policy": config.structure_rules.model_dump() if config.structure_rules else None,
                "structure_checks": {}})
        db.add(profile)
        initial = deepcopy(profile.state)
        refresh_validation(db, profile, initial, now)
        profile.state = initial
        record(db, flight.flight_id, EventType.FLIGHT_STARTED)
        trace(db, profile, "FLIGHT_STARTED", {"callsign": callsign, "policy": profile.policy}, now)
    return session_response(flight, profile)


def session_response(flight, profile):
    return dict(schema_version="2", flight_id=flight.flight_id, callsign=profile.callsign,
                status=flight.status, revision=profile.revision, policy=profile.policy)


def end(db, flight_id):
    now = utc_now()
    with atomic(db):
        flight, profile = context(db, flight_id, active=True, lock=True)
        flight.status, flight.ended_at = FlightStatus.ENDED, stamp(now)
        state = deepcopy(profile.state)
        profile.revision += 1
        refresh_validation(db, profile, state, now, ended=True)
        profile.state = state
        record(db, flight_id, EventType.FLIGHT_ENDED)
        trace(db, profile, "FLIGHT_ENDED", {"unverified": True}, now)
    return session_response(flight, profile)


def register_segment(db, flight_id, segment):
    data = segment.model_dump(mode="json")
    if segment.flight_id != flight_id:
        raise ReceivingError(409, "CONTEXT_MISMATCH", "URL and body flight IDs differ")
    now = utc_now()
    with atomic(db):
        _, profile = context(db, flight_id, active=True, lock=True)
        if profile.policy and (parsed(segment.ended_at) - now).total_seconds() > profile.policy["max_future_skew_seconds"]:
            raise ReceivingError(409, "INVALID_SEQUENCE", "Segment cannot end in the future")
        existing = db.get(V2Segment, segment.segment_id)
        if existing:
            if existing.flight_id != flight_id or existing.fingerprint != fingerprint(data):
                raise ReceivingError(409, "ID_CONTENT_CONFLICT", "Segment ID already has different content")
            return segment_response(db, existing, "DUPLICATE")
        if db.scalar(select(V2Segment).where(V2Segment.attempt_id == segment.attempt_id)):
            raise ReceivingError(409, "ID_CONTENT_CONFLICT", "Attempt ID already belongs to another segment")
        instruction = db.get(V2Instruction, segment.atc_input_id)
        state = deepcopy(profile.state)
        if segment.role == "ATC":
            if instruction is not None:
                raise ReceivingError(409, "ID_CONTENT_CONFLICT", "ATC retry requires a new atc_input_id")
            instruction = V2Instruction(atc_input_id=segment.atc_input_id, instruction_id="INS-"+uuid4().hex,
                flight_id=flight_id, atc_segment_id=segment.segment_id, atc_attempt_id=segment.attempt_id,
                status="PENDING" if segment.complete else "CANCELLED")
            db.add(instruction)
            db.flush()
            latest_id = state["latest_atc_input_id"]
            latest = db.get(V2Instruction, latest_id) if latest_id else None
            latest_segment = db.get(V2Segment, latest.atc_segment_id) if latest else None
            if latest_segment is None or parsed(segment.started_at) > parsed(latest_segment.payload["started_at"]):
                state["latest_atc_input_id"] = segment.atc_input_id
        else:
            if instruction is None or instruction.flight_id != flight_id or instruction.status == "CANCELLED":
                raise ReceivingError(409, "CONTEXT_MISMATCH", "Pilot segment requires the same active ATC input")
            retained_correction = instruction.status == "ADOPTED" and any(
                target and target["instruction_id"] == instruction.instruction_id
                for target in state["targets"].values()) and any(
                item["status"] == "OPEN" and item["stage"] == "READBACK"
                and item["instruction_id"] == instruction.instruction_id
                for item in state.get("incidents", []))
            if state["latest_atc_input_id"] != segment.atc_input_id and not retained_correction:
                raise ReceivingError(409, "INVALID_SEQUENCE", "Older ATC input has no retained readback error to correct")
            atc_segment = db.get(V2Segment, instruction.atc_segment_id)
            if parsed(segment.started_at) < parsed(atc_segment.payload["ended_at"]):
                raise ReceivingError(409, "INVALID_SEQUENCE", "Pilot cannot precede ATC capture completion")
            # Prevent old registrations arriving late from replacing a newer attempt.
            previous = db.scalar(select(V2Segment).where(V2Segment.attempt_id == instruction.latest_pilot_attempt_id)) if instruction.latest_pilot_attempt_id else None
            if previous and parsed(segment.started_at) <= parsed(previous.payload["started_at"]):
                raise ReceivingError(409, "INVALID_SEQUENCE", "Pilot segment is older than the current attempt")
            instruction.latest_pilot_attempt_id = segment.attempt_id
            state.setdefault("readbacks", {}).pop(instruction.instruction_id, None)
            for field, target in state["targets"].items():
                if target and target["instruction_id"] == instruction.instruction_id:
                    state["current"]["READBACK"][field] = None
        stored = V2Segment(segment_id=segment.segment_id, flight_id=flight_id,
            atc_input_id=segment.atc_input_id, attempt_id=segment.attempt_id,
            payload=data, fingerprint=fingerprint(data), cancelled=not segment.complete)
        db.add(stored)
        profile.revision += 1
        refresh_validation(db, profile, state, now)
        profile.state = state
        trace(db, profile, "SEGMENT_REGISTERED", data, now)
        return segment_response(db, stored, "ACCEPTED")


def segment_response(db, segment, disposition):
    instruction = db.get(V2Instruction, segment.atc_input_id)
    return dict(schema_version="2", flight_id=segment.flight_id, segment_id=segment.segment_id,
        instruction_id=instruction.instruction_id, atc_input_id=segment.atc_input_id,
        attempt_id=segment.attempt_id, complete=segment.payload["complete"],
        cancelled=segment.cancelled, disposition=disposition)


def cancel_segment(db, flight_id, segment_id, reason):
    with atomic(db):
        _, profile = context(db, flight_id, active=True, lock=True)
        segment = db.get(V2Segment, segment_id)
        if segment is None or segment.flight_id != flight_id:
            raise ReceivingError(404, "NOT_FOUND", "Segment not found")
        instruction = db.get(V2Instruction, segment.atc_input_id)
        if segment.payload["role"] == "ATC" and instruction.status == "ADOPTED":
            raise ReceivingError(409, "INVALID_SEQUENCE", "Cannot cancel an adopted instruction")
        if not segment.cancelled:
            segment.cancelled = True
            state = deepcopy(profile.state)
            if segment.payload["role"] == "PILOT":
                current_call = state.get("readbacks", {}).get(instruction.instruction_id)
                if current_call and current_call.get("segment_id") == segment_id:
                    state["readbacks"].pop(instruction.instruction_id)
                for field, current in state["current"]["READBACK"].items():
                    if current and current.get("segment_id") == segment_id:
                        state["current"]["READBACK"][field] = None
            profile.revision += 1
            refresh_validation(db, profile, state, utc_now())
            profile.state = state
            if segment.payload["role"] == "ATC":
                instruction.status = "CANCELLED"
            trace(db, profile, "SEGMENT_CANCELLED", {"segment_id": segment_id, "reason": reason}, utc_now())
        return segment_response(db, segment, "ACCEPTED")


def temporal_reason(profile, observed_at, now):
    if profile.policy is None:
        return "POLICY_NOT_CONFIGURED"
    if observed_at is None:
        return "CAPTURE_TIME_UNKNOWN"
    age = (now - parsed(observed_at)).total_seconds()
    if age < -profile.policy["max_future_skew_seconds"]:
        return "FUTURE_OBSERVATION"
    if age > profile.policy["max_age_seconds"]:
        return "STALE_OBSERVATION"
    return None


def quality_reason(profile, reading):
    if reading.validity != "VALID":
        return reading.reason
    if reading.quality.input_quality != "SUFFICIENT":
        return "INPUT_QUALITY_UNVERIFIED"
    minimum = profile.policy["minimum_model_score"] if profile.policy else None
    if minimum is not None and (reading.quality.model_score is None or reading.quality.model_score < minimum):
        return "MODEL_SCORE_UNVERIFIED"
    return None


def speech_context(db, flight_id, observation):
    instruction = db.get(V2Instruction, observation.atc_input_id)
    segment = db.get(V2Segment, observation.segment_id)
    if instruction is None or segment is None or instruction.flight_id != flight_id or segment.flight_id != flight_id:
        raise ReceivingError(409, "CONTEXT_MISMATCH", "Unknown segment/ATC input in this flight")
    expected_role = "ATC" if observation.source == "ATC" else "PILOT"
    if segment.atc_input_id != observation.atc_input_id or segment.attempt_id != observation.attempt_id or segment.payload["role"] != expected_role:
        raise ReceivingError(409, "CONTEXT_MISMATCH", "Source, segment, attempt and ATC input must agree")
    if observation.source == "READBACK" and observation.instruction_id != instruction.instruction_id:
        raise ReceivingError(409, "CONTEXT_MISMATCH", "Readback instruction ID differs from its ATC input")
    return instruction, segment


def callsign_reason(profile, observation):
    call = observation.callsign
    if call.validity != "VALID":
        return call.reason
    if quality_reason(profile, call):
        return "CALLSIGN_QUALITY_UNVERIFIED"
    aliases = profile.callsign_registry.get(call.value, {})
    expected = aliases.get(call.alias_key)
    if expected is None or " ".join(call.raw_text.casefold().split()) != " ".join(expected.casefold().split()):
        return "CALLSIGN_ALIAS_UNVERIFIED"
    if call.value != profile.callsign:
        return "OUT_OF_TARGET"
    return None


def receipt(row, disposition):
    return dict(schema_version="2", flight_id=row.flight_id, input_id=row.input_id,
        event_id=f"v2-event-{row.event_id}", received_at=row.received_at, disposition=disposition)


def structure_check_for(state, observation):
    checked = state.get("structure_checks", {}).get(observation.source)
    return checked if checked and checked["observation_id"] == observation.observation_id else None


def receive(db, flight_id, message, kind):
    obj = message.root if kind == "OBSERVATION" else message
    data = obj.model_dump(mode="json")
    input_id = obj.observation_id if kind == "OBSERVATION" else obj.event_id
    if obj.flight_id != flight_id:
        raise ReceivingError(409, "CONTEXT_MISMATCH", "URL and body flight IDs differ", input_id)
    now = utc_now()
    with atomic(db):
        _, profile = context(db, flight_id, active=True, lock=True)
        existing = db.scalar(select(V2Input).where(V2Input.kind == kind, V2Input.input_id == input_id))
        if existing:
            if existing.flight_id != flight_id or existing.fingerprint != fingerprint(data):
                raise ReceivingError(409, "ID_CONTENT_CONFLICT", "Input ID already has different content", input_id)
            return receipt(existing, "DUPLICATE"), 200
        state = deepcopy(profile.state)
        if kind == "HEALTH":
            applied, reason = apply_health(profile, state, obj, now)
            source, sample_id = obj.channel, None
        else:
            source = obj.source
            sample_id = obj.frame_id if source == "COCKPIT" else obj.segment_id
            instruction, segment = speech_context(db, flight_id, obj) if source != "COCKPIT" else (None, None)
            used = db.scalar(select(V2Input.id).where(V2Input.kind == kind, V2Input.flight_id == flight_id,
                V2Input.source == source, V2Input.sample_id == sample_id))
            if used:
                applied, reason = False, "SOURCE_SAMPLE_REUSED"
            else:
                applied, reason = apply_observation(profile, state, obj, instruction, segment, now)
                if source == "ATC" and applied:
                    from app.schemas.observation_v2 import ObservationV2
                    pending_rows = db.scalars(select(V2Input).where(V2Input.flight_id == flight_id,
                        V2Input.source == "READBACK", V2Input.reason == "ATC_NOT_ADOPTED").order_by(V2Input.id)).all()
                    for pending in pending_rows:
                        if pending.payload["atc_input_id"] != obj.atc_input_id:
                            continue
                        pilot = ObservationV2.model_validate(pending.payload).root
                        pending_instruction, pending_segment = speech_context(db, flight_id, pilot)
                        pending.applied, pending.reason = apply_observation(profile, state, pilot, pending_instruction, pending_segment, now)
                        trace(db, profile, "DEFERRED_READBACK_RECHECKED", {
                            "input_id": pending.input_id, "applied": pending.applied, "reason": pending.reason,
                            "structure_check": structure_check_for(state, pilot),
                        }, now)
        profile.revision += 1
        refresh_validation(db, profile, state, now)
        profile.state = state
        event = trace(db, profile, "INPUT_RECEIVED", {
            "kind": kind, "input_id": input_id, "applied": applied, "reason": reason,
            "payload": data, "state": state,
            "structure_check": structure_check_for(state, obj) if kind == "OBSERVATION" else None,
            "validation": state["validation_snapshot"],
        }, now)
        row = V2Input(flight_id=flight_id, kind=kind, input_id=input_id, source=source, sample_id=sample_id,
            fingerprint=fingerprint(data), received_at=stamp(now), payload=data,
            applied=applied, reason=reason, event_id=event.id)
        db.add(row)
        db.flush()
        return receipt(row, "ACCEPTED"), 201


def apply_health(profile, state, message, now):
    reason = temporal_reason(profile, message.observed_at, now)
    previous = state["channels"].get(message.channel)
    if reason:
        return False, reason
    if previous and parsed(message.observed_at) <= parsed(previous["observed_at"]):
        return False, "HEALTH_OUT_OF_ORDER"
    state["channels"][message.channel] = {**message.health.model_dump(), "observed_at": message.observed_at}
    # Even AVAILABLE clears the old readings: recovery requires a new sample.
    sources = ["COCKPIT"] if message.channel == "CAMERA" else ["READBACK"]
    for source in sources:
        state["current"][source] = {}
    if message.channel != "CAMERA":
        state["readbacks"] = {}
    return True, "HEALTH_RECORDED_AWAITING_NEW_OBSERVATION"


def data_evidence(obj):
    return [ref.model_dump(mode="json") for ref in obj.evidence_refs]


def apply_observation(profile, state, obj, instruction, segment, now):
    if obj.source == "COCKPIT" and obj.target_revision > profile.revision:
        raise ReceivingError(409, "CONTEXT_MISMATCH", "Cockpit target_revision exceeds current flight revision")
    reason = temporal_reason(profile, obj.observed_at, now)
    if profile.policy and (parsed(obj.processed_at) - now).total_seconds() > profile.policy["max_future_skew_seconds"]:
        reason = reason or "FUTURE_PROCESSING_TIME"
    if obj.source != "COCKPIT":
        if segment.cancelled or instruction.status == "CANCELLED":
            return False, "ATTEMPT_CANCELLED"
        if not segment.payload["complete"]:
            return False, "SEGMENT_INCOMPLETE"
        if obj.observed_at is not None and parsed(obj.observed_at) != parsed(segment.payload["started_at"]):
            raise ReceivingError(409, "CONTEXT_MISMATCH", "Speech observed_at must match segment start")
        if obj.source == "ATC" and state["latest_atc_input_id"] != obj.atc_input_id:
            return False, "ATC_INPUT_SUPERSEDED"
        if obj.source == "READBACK" and obj.attempt_id != instruction.latest_pilot_attempt_id:
            return False, "PILOT_ATTEMPT_SUPERSEDED"
        if obj.source == "READBACK" and instruction.status != "ADOPTED":
            return False, "ATC_NOT_ADOPTED"
        reason = reason or callsign_reason(profile, obj)
        reason = reason or (None if obj.instruction_check == "PASS" else "EXTRACTION_UNVERIFIED")
        api_health = state["channels"].get("SPEECH_API")
        if api_health and api_health["status"] != "AVAILABLE":
            reason = reason or "SPEECH_API_UNAVAILABLE"
        configured = state.get("structure_policy")
        checked = check_structure(obj.model_dump(mode="json"), target_callsign=profile.callsign,
            registry=profile.callsign_registry, segment=segment.payload,
            instruction_id=instruction.instruction_id, previous_targets=state["targets"],
            policy=StructurePolicy.model_validate(configured) if configured else None)
        state.setdefault("structure_checks", {})[obj.source] = checked.model_dump(mode="json")
        if checked.result != "PASS":
            reason = reason or "STRUCTURE_" + checked.result
    channel = "CAMERA" if obj.source == "COCKPIT" else "MICROPHONE"
    health = state["channels"].get(channel)
    if health and (obj.observed_at is None or parsed(obj.observed_at) <= parsed(health["observed_at"])):
        reason = reason or "OBSERVATION_PRECEDES_HEALTH"
    if obj.channel_health.status != "AVAILABLE":
        reason = reason or "CHANNEL_UNAVAILABLE"
    if obj.source == "ATC":
        reason = reason or next((r for f in obj.fields.values() if (r := quality_reason(profile, f))), None)
        if reason:
            return False, reason
        # Only fully eligible ATC extraction changes the explicitly named targets.
        for field, reading in obj.fields.items():
            state["targets"][field] = dict(value=reading.value, unit=reading.unit,
                instruction_id=instruction.instruction_id, source_observation_id=obj.observation_id,
                adopted_at=stamp(now), target_revision=profile.revision+1)
            state["current"]["COCKPIT"][field] = None
            state["current"]["READBACK"][field] = None
        instruction.status = "ADOPTED"
        state["readback_required"] = dict(instruction_id=instruction.instruction_id,
            atc_input_id=obj.atc_input_id, fields=list(obj.fields), callsign_required=True)
        state["channels"][channel] = {**obj.channel_health.model_dump(), "observed_at": obj.observed_at}
        return True, "TARGETS_ADOPTED_AWAITING_VALIDATION"
    applied = False
    reasons = []
    if obj.source == "READBACK":
        # A registered, explicit callsign difference remains separate from missing input.
        call_eligible = reason is None or (reason == "OUT_OF_TARGET" and all(
            check.result == "PASS" or check.reason == "CALLSIGN_OUT_OF_TARGET" for check in checked.checks))
        state.setdefault("readbacks", {})[instruction.instruction_id] = dict(
            instruction_id=instruction.instruction_id, segment_id=obj.segment_id,
            observation_id=obj.observation_id, observed_at=obj.observed_at,
            value=obj.callsign.value if call_eligible else None, structure_eligible=call_eligible,
            reason=reason, attempt_id=obj.attempt_id, evidence_refs=data_evidence(obj), evidence_unavailable_reason=obj.evidence_unavailable_reason)
    for field, reading in obj.fields.items():
        target = state["targets"][field]
        previous = state["current"][obj.source].get(field)
        if previous and previous.get("observed_at") and obj.observed_at and parsed(obj.observed_at) <= parsed(previous["observed_at"]):
            reasons.append("OBSERVATION_OUT_OF_ORDER")
            continue
        if obj.source == "READBACK" and target and target["instruction_id"] != instruction.instruction_id:
            reasons.append("TARGET_SUPERSEDED")
            continue
        issue = reason or quality_reason(profile, reading)
        if target is None:
            issue = issue or "TARGET_NOT_AVAILABLE"
        elif obj.source == "READBACK" and target["instruction_id"] != instruction.instruction_id:
            issue = issue or "TARGET_SUPERSEDED"
        elif obj.source == "COCKPIT":
            if obj.target_revision < target["target_revision"]:
                issue = issue or "TARGET_REVISION_OLD"
            if obj.observed_at and parsed(obj.observed_at) <= parsed(target["adopted_at"]):
                issue = issue or "OBSERVATION_PRECEDES_TARGET"
        state["current"][obj.source][field] = dict(value=reading.value if issue is None else None,
            unit=reading.unit, observed_at=obj.observed_at, observation_id=obj.observation_id,
            result="UNVERIFIED", reason=issue or "AWAITING_THREE_STATE_VALIDATION",
            instruction_id=target["instruction_id"] if target else None,
            structure_eligible=obj.source == "COCKPIT" or checked.result == "PASS",
            segment_id=getattr(obj, "segment_id", None),
            frame_id=getattr(obj, "frame_id", None), attempt_id=getattr(obj, "attempt_id", None),
            evidence_refs=data_evidence(obj), evidence_unavailable_reason=obj.evidence_unavailable_reason)
        applied = applied or issue is None
        if issue:
            reasons.append(issue)
    if reason is None:
        state["channels"][channel] = {**obj.channel_health.model_dump(), "observed_at": obj.observed_at}
    return applied, reasons[0] if reasons else "RECORDED_AWAITING_THREE_STATE_VALIDATION"


def get_state(db, flight_id):
    flight, profile = context(db, flight_id)
    state = deepcopy(profile.state)
    now = utc_now()
    for source, fields in state["current"].items():
        if source == "READBACK":
            continue  # Completed readback facts are evaluated with their proof IDs.
        for field, current in fields.items():
            if not current:
                continue
            issue = temporal_reason(profile, current["observed_at"], now)
            if issue:
                fields[field] = {**current, "value": None, "result": "UNVERIFIED", "reason": issue}
    # Remove internal per-target receive revision from the public target DTO.
    targets = {name: ({k:v for k,v in value.items() if k != "target_revision"} if value else None)
               for name,value in state["targets"].items()}
    validation = evaluate(state, profile.policy, profile.callsign, now,
        ended=flight.status == FlightStatus.ENDED).model_dump(mode="json")
    from app.services.alerts.advisory_v2 import view as voice_view
    return dict(schema_version="2", flight_id=flight_id, revision=profile.revision, status=flight.status,
        voice=voice_view(state, profile.policy, profile.callsign, now, ended=flight.status == FlightStatus.ENDED),
        callsign=profile.callsign, targets=targets, readback_required=state["readback_required"],
        channels=state["channels"], current=state["current"], result=validation["result"],
        structure_checks=state.get("structure_checks", {}),
        validation=validation, reason=validation["reason"],
        incident_version="1", incidents=view(state, validation), readbacks=state.get("readbacks", {}))


def revalidate(db, flight_id):
    """Persist timer-driven verdicts/incidents; GET remains read-only."""
    now = utc_now()
    with atomic(db):
        _, profile = context(db, flight_id, active=True, lock=True)
        state = deepcopy(profile.state)
        profile.revision += 1
        refresh_validation(db, profile, state, now)
        profile.state = state
        trace(db, profile, "REVALIDATED", {"validation": state["validation_snapshot"]}, now)
    return get_state(db, flight_id)
