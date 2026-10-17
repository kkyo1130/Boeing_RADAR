import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.flight import Flight
from app.models.contract_observation import ContractClearance
from app.models.operations import Incident, OperationalEvent, StoredEvidence
from app.services import contract_service, operations
from app.services.flight_service import get_flight

router = APIRouter(prefix="/api/v1", tags=["operations"])


class AdvisoryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["ACKNOWLEDGED", "VOICE_REQUESTED", "VOICE_PLAYED", "VOICE_SUPPRESSED"]
    actor: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=200)


class AdvisoryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice_enabled: StrictBool
    critical_phase: StrictBool
    radio_active: StrictBool
    actor: str = Field(min_length=1, max_length=100)


class InputActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel_id: str = Field(min_length=1, max_length=100)
    active: StrictBool
    lease_seconds: int = Field(strict=True, ge=1, le=60)


@router.post("/flights/{flight_id}/input-activity")
def input_activity(flight_id: str, payload: InputActivity, db: Session = Depends(get_db)):
    get_flight(db, flight_id, active=True)
    operations.record(db, flight_id, None, "INPUT_ACTIVITY", contract_service.utc_now().isoformat(),
                      **payload.model_dump())
    db.commit()
    return payload


@router.post("/flights/{flight_id}/advisory-policy")
def policy(flight_id: str, payload: AdvisoryPolicy, db: Session = Depends(get_db)):
    get_flight(db, flight_id, active=True)
    operations.record(db, flight_id, None, "ADVISORY_POLICY", contract_service.utc_now().isoformat(),
                      **payload.model_dump())
    db.commit()
    return payload


@router.post("/flights/{flight_id}/refresh")
def refresh(flight_id: str, db: Session = Depends(get_db)):
    contract_service.lock_writes(db, flight_id)
    get_flight(db, flight_id, active=True)
    for c in db.scalars(select(ContractClearance).where(
            ContractClearance.flight_id == flight_id, ContractClearance.active.is_(True))):
        decision = contract_service.snapshot(db, c)
        previous = db.scalar(select(OperationalEvent).where(
            OperationalEvent.clearance_id == c.clearance_id, OperationalEvent.kind == "DECISION")
            .order_by(OperationalEvent.id.desc()).limit(1))
        if previous is None or previous.data["decision"] != decision:
            operations.record(db, flight_id, c.clearance_id, "DECISION", contract_service.utc_now().isoformat(),
                              decision=decision)
    db.commit()
    return {"refreshed": True}


@router.get("/flights")
def flights(db: Session = Depends(get_db)):
    return [{"flight_id": f.flight_id, "status": f.status, "started_at": f.started_at,
             "ended_at": f.ended_at} for f in db.scalars(select(Flight).order_by(Flight.id.desc()))]


@router.get("/flights/{flight_id}/clearances")
def clearances(flight_id: str, db: Session = Depends(get_db)):
    get_flight(db, flight_id)
    return [contract_service.snapshot(db, c) for c in db.scalars(select(ContractClearance).where(
        ContractClearance.flight_id == flight_id).order_by(ContractClearance.created_at))]


@router.get("/flights/{flight_id}/report")
def report(flight_id: str, db: Session = Depends(get_db)):
    return operations.report(db, flight_id)


@router.get("/flights/{flight_id}/report.json")
def export(flight_id: str, db: Session = Depends(get_db)):
    data = operations.report(db, flight_id)
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="radar-report.json"'})


@router.post("/incidents/{incident_id}/actions", status_code=201)
def action(incident_id: str, payload: AdvisoryAction, db: Session = Depends(get_db)):
    if db.get_bind().dialect.name == "sqlite":
        from sqlalchemy import text
        db.execute(text("BEGIN IMMEDIATE"))
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    get_flight(db, incident.flight_id, active=True)
    if incident.status != "OPEN":
        raise HTTPException(409, "Incident is no longer open")
    if payload.action in ("VOICE_REQUESTED", "VOICE_PLAYED"):
        c = contract_service.clearance(db, incident.clearance_id)
        decision = contract_service.snapshot(db, c)
        if decision["stages"][incident.stage]["verdict"] != "MISMATCH":
            raise HTTPException(409, "Current evidence does not support a mismatch advisory")
        policy_event = db.scalar(select(OperationalEvent).where(
            OperationalEvent.flight_id == incident.flight_id, OperationalEvent.kind == "ADVISORY_POLICY")
            .order_by(OperationalEvent.id.desc()).limit(1))
        policy = policy_event.data if policy_event else {}
        if not policy.get("voice_enabled") or policy.get("critical_phase", True) or policy.get("radio_active", True):
            raise HTTPException(409, "Voice suppressed by server policy")
        if operations.input_active(db, incident.flight_id, contract_service.utc_now()):
            raise HTTPException(409, "Voice suppressed while microphone input is active")
    # Each acknowledgement and playback is recorded at most once per incident.
    for previous in db.scalars(select(OperationalEvent).where(
            OperationalEvent.flight_id == incident.flight_id, OperationalEvent.kind == payload.action)):
        if previous.data.get("incident_id") == incident_id and (
                payload.action != "VOICE_SUPPRESSED" or previous.data.get("reason") == payload.reason):
            return {"recorded": False, "id": previous.id}
    operations.record(db, incident.flight_id, incident.clearance_id, payload.action,
                      contract_service.utc_now().isoformat(), incident_id=incident_id,
                      actor=payload.actor, reason=payload.reason)
    db.commit()
    return {"recorded": True}


@router.post("/clearances/{clearance_id}/evidence", status_code=201)
async def upload(clearance_id: str, request: Request, db: Session = Depends(get_db)):
    from uuid import uuid4
    c = contract_service.clearance(db, clearance_id)
    get_flight(db, c.flight_id, active=True)
    if not c.active:
        raise HTTPException(409, "Clearance superseded")
    media = request.headers.get("content-type", "").split(";")[0]
    if media not in ("image/png", "image/jpeg", "audio/wav"):
        raise HTTPException(415, "Only PNG, JPEG and PCM WAV evidence")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(413, "Evidence exceeds 8 MiB")
    if not content:
        raise HTTPException(422, "Empty evidence")
    import io
    if media == "audio/wav":
        import wave
        try:
            with wave.open(io.BytesIO(content)) as audio:
                if audio.getsampwidth() != 2 or audio.getnchannels() not in (1, 2):
                    raise ValueError()
                expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
                if not expected or len(audio.readframes(audio.getnframes())) != expected:
                    raise ValueError()
        except (wave.Error, EOFError, ValueError):
            raise HTTPException(422, "Invalid PCM WAV")
    else:
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 16000000 or image.format != ("PNG" if media == "image/png" else "JPEG"):
                    raise ValueError()
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(422, "Invalid or oversized image")
    token = str(uuid4())
    db.add(StoredEvidence(evidence_id=token, clearance_id=clearance_id, media_type=media,
                         created_at=contract_service.utc_now().isoformat(), deleted_at=None,
                         content=bytes(content)))
    operations.record(db, c.flight_id, clearance_id, "EVIDENCE_STORED",
                      contract_service.utc_now().isoformat(), evidence_id=token)
    db.commit()
    return {"evidence_id": token, "reference": f"/api/v1/clearances/{clearance_id}/evidence/{token}",
            "availability": "available", "kind": "audio" if media == "audio/wav" else "image", "roi": None}


@router.get("/clearances/{clearance_id}/evidence/{evidence_id}")
def evidence(clearance_id: str, evidence_id: str, db: Session = Depends(get_db)):
    item = db.get(StoredEvidence, evidence_id)
    if item is None or item.clearance_id != clearance_id:
        raise HTTPException(404, "Evidence not found for this clearance")
    if item.deleted_at:
        raise HTTPException(410, "Evidence deleted; trace retained")
    return Response(item.content, media_type=item.media_type,
                    headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.delete("/clearances/{clearance_id}/evidence/{evidence_id}")
def delete_evidence(clearance_id: str, evidence_id: str, db: Session = Depends(get_db)):
    item = db.get(StoredEvidence, evidence_id)
    if item is None or item.clearance_id != clearance_id:
        raise HTTPException(404, "Evidence not found for this clearance")
    c = contract_service.clearance(db, clearance_id)
    if item.deleted_at is None:
        item.content = None
        item.deleted_at = contract_service.utc_now().isoformat()
        operations.record(db, c.flight_id, clearance_id, "EVIDENCE_DELETED", item.deleted_at,
                          evidence_id=evidence_id)
        db.commit()
    return {"evidence_id": evidence_id, "availability": "unavailable"}
