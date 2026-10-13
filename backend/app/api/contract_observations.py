from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.contract_observation import ContractEvent
from app.schemas.observation_contract import ObservationContract
from app.services import contract_service as service
from app.services.flight_service import get_flight

router = APIRouter(prefix="/api/v1", tags=["contract observations"])


@router.post("/flights/{flight_id}/clearances", status_code=201)
def reserve(flight_id: str, db: Session = Depends(get_db)):
    return service.reserve(db, flight_id)


@router.post("/observations")
def receive(payload: ObservationContract, db: Session = Depends(get_db)):
    try:
        return service.receive(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Observation identity conflict")


@router.get("/clearances/{clearance_id}")
def get(clearance_id: str, db: Session = Depends(get_db)):
    return service.snapshot(db, service.clearance(db, clearance_id))


@router.get("/flights/{flight_id}/observation-events")
def events(flight_id: str, db: Session = Depends(get_db)):
    get_flight(db, flight_id)
    return [{**service.receipt(e), "payload": e.payload} for e in db.scalars(
        select(ContractEvent).where(ContractEvent.flight_id == flight_id)
        .order_by(ContractEvent.received_at, ContractEvent.event_id))]
