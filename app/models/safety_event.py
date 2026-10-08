from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class SafetyEvent(Base):
    __tablename__ = "safety_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    clearance_id: Mapped[str | None] = mapped_column(ForeignKey("clearances.clearance_id"))
    event_type: Mapped[str]
    field: Mapped[str | None]
    expected: Mapped[int | None]
    actual: Mapped[int | None]
    timestamp: Mapped[str]
    observation: Mapped[dict | None] = mapped_column(JSON)
