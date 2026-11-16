"""Persist deadline transitions independently of browser polling."""
import logging
from sqlalchemy import select
from app.db import get_db
from contextlib import contextmanager
from app.models.flight import Flight
from app.core.enums import FlightStatus
from app.models.observation_v2 import V2FlightContext
from app.services import receiving_v2 as intake

log = logging.getLogger(__name__)

def tick(provider=get_db):
    sessions = contextmanager(provider)
    with sessions() as db:
        ids = list(db.scalars(select(V2FlightContext.flight_id).join(Flight).where(Flight.status == FlightStatus.ACTIVE)))
    for flight_id in ids:
        with sessions() as db:
            try:
                from app.services.demo.adapters import expire_camera
                expire_camera(db, flight_id)
                intake.revalidate(db, flight_id)
            except intake.ReceivingError as error:
                if error.status != 409:
                    log.exception('Deadline evaluation failed for %s', flight_id)
            except Exception:
                log.exception('Deadline evaluation failed for %s', flight_id)
