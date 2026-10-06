from sqlalchemy import select
from app.db import now
from app.models.safety_event import SafetyEvent

def record(db, flight_id, event_type, clearance_id=None, observation=None, **details):
    db.add(SafetyEvent(flight_id=flight_id, clearance_id=clearance_id,
                      event_type=event_type, timestamp=now(), observation=observation, **details))

def trace(db, flight_id):
    return db.scalars(select(SafetyEvent).where(SafetyEvent.flight_id == flight_id)
                      .order_by(SafetyEvent.timestamp, SafetyEvent.id)).all()
