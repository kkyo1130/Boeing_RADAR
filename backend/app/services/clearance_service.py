from fastapi import HTTPException
from sqlalchemy import select
from app.core.enums import Source, ClearanceStatus as Status, EventType
from app.models.clearance import Clearance
from app.services.flight_service import get_flight
from app.services.safety_trace_service import record
from app.services.validation_service import validate, compare

def get_clearance(db, clearance_id):
    result = db.scalar(select(Clearance).where(Clearance.clearance_id == clearance_id))
    if result is None:
        raise HTTPException(404, "Clearance not found")
    return result

def create(db, flight_id, payload):
    get_flight(db, flight_id, active=True)
    c = Clearance(clearance_id="pending", flight_id=flight_id,
                  atc=payload.observation(Source.ATC), status=Status.WAITING_READBACK, errors=[])
    db.add(c)
    db.flush()
    c.clearance_id = f"CLR-{c.id:03d}"
    db.flush()
    record(db, flight_id, EventType.ATC_RECOGNIZED, c.clearance_id, c.atc)
    db.commit()
    return c

def submit(db, clearance_id, payload, source, reverify=False):
    c = get_clearance(db, clearance_id)
    get_flight(db, c.flight_id, active=True)
    key = source.value.lower()
    if reverify:
        required = Status.READBACK_ERROR if source == Source.READBACK else Status.SETTING_ERROR
        if c.status != required:
            raise HTTPException(409, f"Reverification requires {required}")
    elif source == Source.READBACK:
        if c.readback is not None:
            raise HTTPException(409, "Readback already exists; use reverify after an error")
    elif c.readback is None:
        raise HTTPException(409, "Readback is required before cockpit")
    elif c.cockpit is not None:
        raise HTTPException(409, "Cockpit already exists; use reverify after an error")
    old = getattr(c, key)
    observation = payload.observation(source)
    if reverify:
        c.status = Status.REVERIFYING
        record(db, c.flight_id, EventType.REVERIFYING, c.clearance_id)
    setattr(c, key, observation)
    event_type = EventType[f"{source.value}_{'UPDATED' if reverify else 'RECOGNIZED'}"]
    record(db, c.flight_id, event_type, c.clearance_id, observation)
    if reverify:
        for change in compare(old, observation):
            record(db, c.flight_id, event_type, c.clearance_id, **change)
    status, errors = validate(c.atc, c.readback, c.cockpit)
    if reverify and status in (Status.VERIFIED, Status.WAITING_COCKPIT):
        status = Status.RESOLVED
    c.status, c.errors = status, errors
    for error in errors:
        record(db, c.flight_id, EventType[status.value], c.clearance_id, **error)
    if errors:
        record(db, c.flight_id, EventType.ALERTED, c.clearance_id)
    elif status in (Status.VERIFIED, Status.RESOLVED):
        record(db, c.flight_id, EventType[status.value], c.clearance_id)
    db.commit()
    return c
