from datetime import datetime
from uuid import uuid4
from sqlalchemy import select
from app.models.operations import OperationalEvent, Incident, FlightReport
from app.models.contract_observation import ContractClearance, ContractEvent


def record(db, flight_id, clearance_id, kind, timestamp, **data):
    db.add(OperationalEvent(flight_id=flight_id, clearance_id=clearance_id,
                           kind=kind, timestamp=timestamp, data=data))


def reconcile(db, c, decision, timestamp):
    """Only checked fresh numeric comparisons open/resolve an incident."""
    db.flush()
    for stage in ("readback", "cockpit"):
        current = db.scalar(select(Incident).where(
            Incident.clearance_id == c.clearance_id, Incident.stage == stage,
            Incident.status == "OPEN"))
        result = decision["stages"][stage]
        if result["verdict"] == "MISMATCH" and current is None:
            observed = c.latest[stage.upper()]
            current = Incident(incident_id=str(uuid4()), flight_id=c.flight_id,
                clearance_id=c.clearance_id, stage=stage, detected_at=timestamp,
                resolved_at=None, status="OPEN", observation_id=observed["observation_id"],
                errors=result["errors"])
            db.add(current)
            record(db, c.flight_id, c.clearance_id, "INCIDENT_DETECTED", timestamp,
                   incident_id=current.incident_id, stage=stage, errors=current.errors)
        elif current and result["verdict"] == "NORMAL" and decision["resolutions"].get(stage) == "RESOLVED":
            current.status = "RESOLVED"
            current.resolved_at = timestamp
            record(db, c.flight_id, c.clearance_id, "INCIDENT_RESOLVED", timestamp,
                   incident_id=current.incident_id,
                   observation_id=c.latest[stage.upper()]["observation_id"])


def incident_dict(item):
    return {key: getattr(item, key) for key in (
        "incident_id", "clearance_id", "stage", "detected_at", "resolved_at",
        "status", "observation_id", "errors")} | {
        "resolution_seconds": ((datetime.fromisoformat(item.resolved_at) -
            datetime.fromisoformat(item.detected_at)).total_seconds() if item.resolved_at else None)}


def input_active(db, flight_id, clock):
    channels = {}
    for event in db.scalars(select(OperationalEvent).where(
            OperationalEvent.flight_id == flight_id, OperationalEvent.kind == "INPUT_ACTIVITY")
            .order_by(OperationalEvent.id)):
        channels[event.data["channel_id"]] = event
    return any(event.data["active"] and
               0 <= (clock - datetime.fromisoformat(event.timestamp)).total_seconds() < event.data["lease_seconds"]
               for event in channels.values())


def report(db, flight_id, terminal=False):
    from app.services.contract_service import snapshot, utc_now
    from app.services.flight_service import get_flight
    get_flight(db, flight_id)
    frozen = db.get(FlightReport, flight_id)
    if frozen:
        return frozen.data
    clearances = [snapshot(db, c) for c in db.scalars(select(ContractClearance).where(
        ContractClearance.flight_id == flight_id).order_by(ContractClearance.created_at))]
    incidents = [incident_dict(i) for i in db.scalars(select(Incident).where(
        Incident.flight_id == flight_id).order_by(Incident.detected_at, Incident.incident_id))]
    timeline = [{"id": e.id, "timestamp": e.timestamp, "clearance_id": e.clearance_id,
                 "kind": e.kind, "data": e.data} for e in db.scalars(select(OperationalEvent).where(
        OperationalEvent.flight_id == flight_id).order_by(OperationalEvent.id))]
    archived = {e["clearance_id"]: e["data"]["decision"] for e in timeline
                if e["kind"] == "CLEARANCE_SUPERSEDED"}
    clearances = [{**archived[c["clearance_id"]], "active": False}
                  if not c["active"] and c["clearance_id"] in archived else c for c in clearances]
    events = list(db.scalars(select(ContractEvent).where(ContractEvent.flight_id == flight_id)))
    result = {"schema_version": "radar-report/1", "flight_id": flight_id,
        "generated_at": utc_now().isoformat(), "terminal": terminal,
        "input_active": input_active(db, flight_id, utc_now()),
        "summary": {"clearances": len(clearances), "incidents": len(incidents),
            "resolved": sum(i["status"] == "RESOLVED" for i in incidents),
            "unresolved": sum(i["status"] != "RESOLVED" for i in incidents),
            "normal": sum(c["verdict"] == "NORMAL" for c in clearances),
            "unverified": sum(c["verdict"] == "UNVERIFIED" for c in clearances),
            "mismatch": sum(c["verdict"] == "MISMATCH" for c in clearances),
            "rejected_inputs": sum(not e.accepted for e in events),
            "channel_faults": sum(e.payload["health"]["status"] != "available" for e in events)},
        "clearances": clearances, "incidents": incidents, "timeline": timeline,
        "corrections": [{"event_id": e.event_id, "source": e.source, "accepted": e.accepted,
                         "supersedes_observation_id": e.payload["supersedes_observation_id"],
                         "observation_id": e.observation_id, "received_at": e.received_at}
                        for e in events if e.payload.get("intent") == "correction"],
        "advisories": [e for e in timeline if e["kind"] in (
            "VOICE_REQUESTED", "VOICE_PLAYED", "VOICE_SUPPRESSED", "ACKNOWLEDGED", "ADVISORY_POLICY")],
        "classification": {stage: sum(i["stage"] == stage for i in incidents)
                           for stage in ("readback", "cockpit")},
        "training_feedback": [{"incident_id": i["incident_id"], "stage": i["stage"],
            "fields": sorted({error["field"] for error in i["errors"]}),
            "message": ("새 관측으로 해당 단계의 수정이 확인되었습니다." if i["status"] == "RESOLVED"
                        else "원본 지시와 관측을 대조하고 새 입력으로 다시 확인하세요."),
            "limitation": "이 기록은 조종 능력이나 운항 적합성 평가가 아닙니다."} for i in incidents],
        "observations": [{"event_id": e.event_id, "accepted": e.accepted,
                          "reasons": e.reasons, "payload": e.payload} for e in events]}
    if terminal:
        db.add(FlightReport(flight_id=flight_id, data=result))
    return result
