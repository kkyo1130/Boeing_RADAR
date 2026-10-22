from fastapi import HTTPException
from sqlalchemy import select
from app.db import now
from app.models.flight import Flight
from app.core.enums import FlightStatus, EventType
from app.services.safety_trace_service import record

def get_flight(db, flight_id, active=False):
    flight = db.scalar(select(Flight).where(Flight.flight_id == flight_id))
    if flight is None:
        raise HTTPException(404, "Flight not found")
    if active and flight.status != FlightStatus.ACTIVE:
        raise HTTPException(409, "Flight has ended")
    return flight

def start(db):
    stamp = now()
    # SQLite allocates the integer key; no count-based identifier race.
    flight = Flight(flight_id="pending", started_at=stamp, status=FlightStatus.ACTIVE)
    db.add(flight)
    db.flush()
    flight.flight_id = f"FLT-{stamp[:10].replace('-', '')}-{flight.id:03d}"
    db.flush()
    record(db, flight.flight_id, EventType.FLIGHT_STARTED)
    db.commit()
    return flight

def end(db, flight_id):
    flight = get_flight(db, flight_id, active=True)
    flight.status = FlightStatus.ENDED
    flight.ended_at = now()
    record(db, flight_id, EventType.FLIGHT_ENDED)
    db.commit()
    return flight
