"""Field ownership, three-state comparison and per-instruction adjustment time.

No model, aircraft control, playback or Incident state is changed here.
Only mutation callers persist memory; GET evaluates a copy without a DB write.
"""
from datetime import datetime, timedelta

from app.schemas.validation_v2 import FieldVerdict, StageVerdict, ValidationSnapshot

ADJUSTMENT_SECONDS = 5


def parsed(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def freshness(policy, observed_at, now):
    if policy is None:
        return "POLICY_NOT_CONFIGURED"
    if observed_at is None:
        return "CAPTURE_TIME_UNKNOWN"
    age = (now-parsed(observed_at)).total_seconds()
    if age < -policy["max_future_skew_seconds"]:
        return "FUTURE_OBSERVATION"
    if age > policy["max_age_seconds"]:
        return "STALE_OBSERVATION"
    return None


def aggregate(fields):
    if any(field.result == "MISMATCH" for field in fields):
        return "MISMATCH"
    if not fields or any(field.result == "UNVERIFIED" for field in fields):
        return "UNVERIFIED"
    return "NORMAL"


def evaluate(state, policy, callsign, now, *, ended=False, persist=False):
    targets = state["targets"]
    previous_memory = state.get("validation_memory", {})
    confirmed = dict(previous_memory.get("readback_confirmed_at", {}))
    proofs = {iid: dict(fields) for iid, fields in previous_memory.get("readback_proofs", {}).items()}
    matched = dict(previous_memory.get("setting_matched", {}))
    active_ids = {target["instruction_id"] for target in targets.values() if target}
    confirmed = {key: value for key, value in confirmed.items() if key in active_ids}
    proofs = {key: value for key, value in proofs.items() if key in active_ids}
    matched = {key: value for key, value in matched.items()
        if targets.get(key) and targets[key]["instruction_id"] == value}
    readbacks = state.get("readbacks", {})
    readback_fields, setting_fields = [], []

    def field(stage, name, target, current, *, call=False):
        expected = callsign if call else target["value"] if target else None
        iid = target["instruction_id"] if target else None
        actual = current.get("value") if current else None
        reason = None
        if target is None:
            reason = "TARGET_NOT_AVAILABLE"
        elif not current:
            reason = "INPUT_NOT_AVAILABLE"
        elif current.get("instruction_id") != iid:
            reason = "TARGET_CONTEXT_UNVERIFIED"
        elif actual is None:
            reason = current.get("reason") or "VALUE_UNAVAILABLE"
        else:
            reason = freshness(policy, current.get("observed_at"), now)
            if (reason == "STALE_OBSERVATION" and stage == "READBACK" and actual == expected
                and proofs.get(iid, {}).get(name) == current.get("observation_id")):
                # An unchanged, completed verification is a historical fact, not
                # a stale new extraction. New attempts/health clear current proof.
                reason = None
            if not reason and stage == "READBACK" and not current.get("structure_eligible"):
                reason = "STRUCTURE_CONTEXT_UNVERIFIED"
        result = "UNVERIFIED" if reason else "NORMAL" if actual == expected else "MISMATCH"
        return FieldVerdict(stage=stage, field=name, instruction_id=iid,
            observation_id=current.get("observation_id") if current else None,
            expected=expected, actual=actual, result=result,
            reason=reason or ("VALUE_MATCH" if result == "NORMAL" else "VALUE_MISMATCH"))

    for name, target in targets.items():
        if target:
            readback_fields.append(field("READBACK", name, target, state["current"]["READBACK"].get(name)))
    for iid in sorted(active_ids):
        target = next(target for target in targets.values() if target and target["instruction_id"] == iid)
        readback_fields.append(field("READBACK", "CALLSIGN", target, readbacks.get(iid), call=True))
    for iid in active_ids:
        relevant = [item for item in readback_fields if item.instruction_id == iid]
        if aggregate(relevant) == "NORMAL" and iid not in confirmed:
            confirmed[iid] = stamp(now)
        if aggregate(relevant) == "NORMAL":
            proofs[iid] = {item.field: item.observation_id for item in relevant}
        else:
            proofs.pop(iid, None)
    for name, target in targets.items():
        current = state["current"]["COCKPIT"].get(name)
        verdict = field("SETTING", name, target, current)
        if target:
            iid = target["instruction_id"]
            readback_result = aggregate([item for item in readback_fields if item.instruction_id == iid])
            t0 = confirmed.get(iid)
            if verdict.result != "UNVERIFIED":
                if not t0 or readback_result != "NORMAL":
                    verdict.result, verdict.reason = "UNVERIFIED", "READBACK_NOT_CONFIRMED"
                elif verdict.result == "MISMATCH" and matched.get(name) != iid:
                    deadline = parsed(t0)+timedelta(seconds=ADJUSTMENT_SECONDS)
                    verdict.wait_until = stamp(deadline)
                    if now < deadline:
                        verdict.result, verdict.reason = "UNVERIFIED", "INITIAL_ADJUSTMENT_WAIT"
                    else:
                        verdict.reason = "ADJUSTMENT_DEADLINE_MISMATCH"
                elif verdict.result == "MISMATCH":
                    verdict.reason = "SETTING_DEVIATED_AFTER_MATCH"
        setting_fields.append(verdict)
    for iid in active_ids:
        relevant = [item for item in setting_fields if item.instruction_id == iid]
        if aggregate(relevant) == "NORMAL":
            for item in relevant:
                matched[item.field] = iid
    rb = StageVerdict(result=aggregate(readback_fields), fields=readback_fields)
    setting = StageVerdict(result=aggregate(setting_fields), fields=setting_fields)
    required = state.get("readback_required")
    adopted = bool(required and required["atc_input_id"] == state.get("latest_atc_input_id"))
    representative, advisories = None, []
    if ended:
        result, phase, reason = "UNVERIFIED", "ENDED", "FLIGHT_ENDED"
    elif not adopted:
        result, phase, reason = "UNVERIFIED", "WAITING_ATC", "LATEST_ATC_NOT_ADOPTED"
    elif aggregate([item for item in readback_fields if item.instruction_id == required["instruction_id"]]) == "UNVERIFIED":
        result, phase, reason = "UNVERIFIED", "READBACK", "LATEST_READBACK_UNVERIFIED"
    elif rb.result == "MISMATCH":
        result, phase, reason, representative = "MISMATCH", "READBACK", "READBACK_MISMATCH", "READBACK"
    elif setting.result == "MISMATCH":
        result, phase, reason, representative = "MISMATCH", "SETTING", "SETTING_MISMATCH", "SETTING"
    elif rb.result == "UNVERIFIED":
        result, phase, reason = "UNVERIFIED", "READBACK", "READBACK_UNVERIFIED"
    elif setting.result == "UNVERIFIED":
        result, phase, reason = "UNVERIFIED", "SETTING", "SETTING_UNVERIFIED"
    else:
        result, phase, reason = "NORMAL", "MONITORING", "ALL_REQUIRED_FIELDS_MATCH"
    if representative:
        advisories = [item for item in (readback_fields if representative == "READBACK" else setting_fields)
            if item.result == "MISMATCH"]
    if persist:
        state["validation_memory"] = dict(readback_confirmed_at=confirmed, setting_matched=matched,
            readback_proofs=proofs)
        state["validation_snapshot"] = ValidationSnapshot(result=result, phase=phase, reason=reason,
            representative_stage=representative, readback=rb, setting=setting,
            advisory_candidates=advisories).model_dump(mode="json")
    return ValidationSnapshot(result=result, phase=phase, reason=reason,
        representative_stage=representative, readback=rb, setting=setting,
        advisory_candidates=advisories)
