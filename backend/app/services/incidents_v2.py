"""Server-owned occurrence history. Unknown input never proves resolution.

Stored inside the flight's existing JSON state and committed with Safety Trace.
Playback/acknowledgement and real producer stabilization belong to later WIs.
"""
from copy import deepcopy
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.incidents_v2 import IncidentEvidence

from app.services.validation_v2 import parsed, stamp


def evidence(state, verdict):
    if verdict["field"] == "CALLSIGN":
        current = state.get("readbacks", {}).get(verdict["instruction_id"])
    else:
        source = "COCKPIT" if verdict["stage"] == "SETTING" else "READBACK"
        current = state["current"][source].get(verdict["field"])
    if not current or current.get("observation_id") != verdict["observation_id"]:
        return None
    sample = "frame_id" if verdict["stage"] == "SETTING" else "segment_id"
    if not current.get(sample) or not current.get("observed_at"):
        return None  # Pre-policy state is not new, attributable correction evidence.
    proof = {key: deepcopy(current.get(key)) for key in (
        "observation_id", "observed_at", "frame_id", "segment_id", "attempt_id", "evidence_refs",
        "evidence_unavailable_reason")}
    if verdict["stage"] == "READBACK" and not proof["attempt_id"]:
        return None
    if bool(proof["evidence_refs"]) == (proof["evidence_unavailable_reason"] is not None):
        return None
    try:
        return IncidentEvidence.model_validate(proof).model_dump(mode="json")
    except ValidationError:
        return None  # Legacy/incomplete provenance cannot emit an invalid Incident DTO.


def key(item):
    return item["instruction_id"], item["stage"], item["field"]


def reconcile(state, flight_id, validation, now, *, ended=False):
    """Mutate only on transactional commands; return changed occurrence snapshots."""
    incidents = state.setdefault("incidents", [])
    before = {item["occurrence_id"]: deepcopy(item) for item in incidents}
    verdicts = validation["readback"]["fields"] + validation["setting"]["fields"]
    by_key = {key(item): item for item in verdicts if item["instruction_id"]}
    targets = state["targets"]
    active = {target["instruction_id"] for target in targets.values() if target}
    at = stamp(now)
    for item in incidents:
        if item["status"] != "OPEN":
            continue
        target = targets.get(item["field"])
        replaced = (item["instruction_id"] not in active if item["field"] == "CALLSIGN"
            else not target or target["instruction_id"] != item["instruction_id"])
        if ended or replaced:
            item.update(status="ENDED_UNRESOLVED" if ended else "SUPERSEDED", closed_at=at,
                close_reason="FLIGHT_ENDED" if ended else "TARGET_REPLACED")
            continue
        verdict = by_key.get(key(item))
        if verdict:
            item["current_check"] = deepcopy(verdict)
            proof = evidence(state, verdict)
            if proof and proof != item["latest_evidence"]:
                item.update(latest_evidence=proof, reobserved_at=proof["observed_at"], reverified_at=at)
            if verdict["result"] == "MISMATCH":
                if proof and proof["observed_at"]:
                    item["last_mismatch_evidence"] = proof
                continue
            if verdict["result"] != "NORMAL" or not proof or not proof["observed_at"]:
                continue
            # Readback correction must verify every still-owned required field and
            # callsign in the new attempt; missing fields are never filled from history.
            if item["stage"] == "READBACK" and any(v["result"] != "NORMAL"
                for v in validation["readback"]["fields"] if v["instruction_id"] == item["instruction_id"]):
                continue
            previous = item["last_mismatch_evidence"]
            sample = "frame_id" if item["stage"] == "SETTING" else "segment_id"
            if (proof["observation_id"] != previous["observation_id"] and proof[sample]
                and proof[sample] != previous[sample]
                and parsed(proof["observed_at"]) > parsed(previous["observed_at"])):
                item.update(status="RESOLVED", resolved_at=at, closed_at=at,
                    close_reason="NEW_VALID_OBSERVATION", resolution_evidence=proof)
    if not ended:
        open_keys = {key(item) for item in incidents if item["status"] == "OPEN"}
        for verdict in verdicts:
            if verdict["result"] != "MISMATCH" or key(verdict) in open_keys:
                continue
            proof = evidence(state, verdict)
            if not proof or not proof["observed_at"]:
                continue
            item = dict(occurrence_id="INC-"+uuid4().hex, flight_id=flight_id,
                instruction_id=verdict["instruction_id"], stage=verdict["stage"], field=verdict["field"],
                status="OPEN", detected_at=at, first_evidence=proof, latest_evidence=proof,
                first_check=deepcopy(verdict),
                last_mismatch_evidence=proof, current_check=deepcopy(verdict),
                reobserved_at=None, reverified_at=None, resolved_at=None, closed_at=None,
                close_reason=None, resolution_evidence=None,
                notified_at=None, voice_completed_at=None)
            incidents.append(item)
            open_keys.add(key(item))
    return [deepcopy(item) for item in incidents if before.get(item["occurrence_id"]) != item]


def view(state, validation):
    """Read-only current freshness display; never invent an unpersisted lifecycle."""
    verdicts = {key(item): item for item in validation["readback"]["fields"] + validation["setting"]["fields"]}
    items = deepcopy(state.get("incidents", []))
    for item in items:
        if item["status"] == "OPEN" and key(item) in verdicts:
            item["current_check"] = verdicts[key(item)]
    return items
