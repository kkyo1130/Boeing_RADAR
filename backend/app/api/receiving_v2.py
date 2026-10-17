"""Versioned intake routes. No inference provider or aircraft control is called."""
from fastapi import APIRouter, Depends, Query, Request
from typing import Literal
from fastapi.responses import FileResponse
from app.schemas.evidence_v2 import EvidenceInteraction
from app.services import evidence_v2
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.observation_v2 import V2Input, V2TraceEvent
from app.schemas.observation_v2 import ObservationV2, HealthEventV2, SpeechSegmentV2, ContractErrorV2, IngestionReceiptV2
from app.schemas.receiving_v2 import StartFlightV2, CancelSegmentV2
from app.services import receiving_v2 as service

router = APIRouter(prefix="/api/v2/flights", tags=["v2 intake"])


def install_handlers(app):
    @app.exception_handler(service.ReceivingError)
    async def receiving_error(request, exc):
        error = ContractErrorV2(schema_version="2", code=exc.code, message=exc.message,
                                input_id=exc.input_id, field_path=exc.field_path)
        return JSONResponse(status_code=exc.status, content=error.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def payload_error(request: Request, exc: RequestValidationError):
        if not request.url.path.startswith("/api/v2/"):
            return await request_validation_exception_handler(request, exc)
        body = exc.body if isinstance(exc.body, dict) else {}
        code = "UNSUPPORTED_VERSION" if "schema_version" in body and body["schema_version"] != "2" else "INVALID_PAYLOAD"
        errors = exc.errors()
        error = ContractErrorV2(schema_version="2", code=code, message="Request failed v2 contract validation",
            input_id=None, field_path=".".join(map(str, errors[0]["loc"])) if errors else None)
        return JSONResponse(status_code=422, content=error.model_dump(mode="json"))


@router.post("", status_code=201)
def start(payload: StartFlightV2, db: Session = Depends(get_db)):
    return service.start(db, payload.callsign)


@router.post("/{flight_id}/end")
def end(flight_id: str, db: Session = Depends(get_db)):
    return service.end(db, flight_id)


@router.post("/{flight_id}/speech-segments", status_code=201)
def segment(flight_id: str, payload: SpeechSegmentV2, db: Session = Depends(get_db)):
    result = service.register_segment(db, flight_id, payload)
    return JSONResponse(status_code=200 if result["disposition"] == "DUPLICATE" else 201, content=result)


@router.post("/{flight_id}/speech-segments/{segment_id}/cancel")
def cancel(flight_id: str, segment_id: str, payload: CancelSegmentV2, db: Session = Depends(get_db)):
    return service.cancel_segment(db, flight_id, segment_id, payload.reason)


@router.post("/{flight_id}/observations", response_model=IngestionReceiptV2, status_code=201)
def observation(flight_id: str, payload: ObservationV2, db: Session = Depends(get_db)):
    receipt, code = service.receive(db, flight_id, payload, "OBSERVATION")
    return JSONResponse(status_code=code, content=receipt)


@router.post("/{flight_id}/health-events", response_model=IngestionReceiptV2, status_code=201)
def health(flight_id: str, payload: HealthEventV2, db: Session = Depends(get_db)):
    receipt, code = service.receive(db, flight_id, payload, "HEALTH")
    return JSONResponse(status_code=code, content=receipt)


@router.get("/{flight_id}/state")
def state(flight_id: str, db: Session = Depends(get_db)):
    return service.get_state(db, flight_id)


@router.get("/{flight_id}/inputs")
def inputs(flight_id: str, limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    service.context(db, flight_id)
    rows = db.scalars(select(V2Input).where(V2Input.flight_id == flight_id).order_by(V2Input.id.desc()).limit(limit)).all()
    return [dict(input_id=row.input_id, kind=row.kind, received_at=row.received_at,
        applied=row.applied, reason=row.reason, event_id=f"v2-event-{row.event_id}", payload=row.payload) for row in rows]


@router.get("/{flight_id}/safety-trace")
def trace(flight_id: str, after: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    service.context(db, flight_id)
    rows = db.scalars(select(V2TraceEvent).where(V2TraceEvent.flight_id == flight_id,
        V2TraceEvent.id > after).order_by(V2TraceEvent.id).limit(limit)).all()
    return [dict(event_id=f"v2-event-{row.id}", sequence=row.id, event_type=row.event_type,
        occurred_at=row.occurred_at, revision=row.revision, snapshot=row.snapshot) for row in rows]


@router.post("/{flight_id}/revalidate")
def revalidate(flight_id: str, db: Session = Depends(get_db)):
    return service.revalidate(db, flight_id)


@router.get("/{flight_id}/evidence/{observation_id}")
def evidence(flight_id: str, observation_id: str, instruction_id: str,
             stage: Literal["READBACK", "SETTING"], field: Literal["ALT", "HDG", "CALLSIGN"], db: Session = Depends(get_db)):
    return evidence_v2.metadata(db, flight_id, instruction_id, stage, field, observation_id)


@router.get("/{flight_id}/evidence/{observation_id}/media/{role}/{evidence_id}")
def media(flight_id: str, observation_id: str, role: Literal["ATC", "OBSERVED"], evidence_id: str,
          instruction_id: str, stage: Literal["READBACK", "SETTING"], field: Literal["ALT", "HDG", "CALLSIGN"], db: Session = Depends(get_db)):
    path, mime = evidence_v2.content(db, flight_id, instruction_id, stage, field, observation_id, role, evidence_id)
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/{flight_id}/interactions", status_code=201)
def interaction(flight_id: str, payload: EvidenceInteraction, db: Session = Depends(get_db)):
    result, status = evidence_v2.interact(db, flight_id, payload)
    return JSONResponse(status_code=status, content=result)
