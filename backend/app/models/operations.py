"""Append-only operational history, separate from the legacy clearance schema."""
from sqlalchemy import ForeignKey, JSON, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    clearance_id: Mapped[str | None]
    timestamp: Mapped[str]
    kind: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)


class Incident(Base):
    __tablename__ = "operational_incidents"
    incident_id: Mapped[str] = mapped_column(primary_key=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    clearance_id: Mapped[str]
    stage: Mapped[str]
    detected_at: Mapped[str]
    resolved_at: Mapped[str | None]
    status: Mapped[str]
    observation_id: Mapped[str]
    errors: Mapped[list] = mapped_column(JSON)


class FlightReport(Base):
    __tablename__ = "operational_reports"
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class StoredEvidence(Base):
    __tablename__ = "operational_evidence"
    evidence_id: Mapped[str] = mapped_column(primary_key=True)
    clearance_id: Mapped[str] = mapped_column(ForeignKey("contract_clearances.clearance_id"), index=True)
    media_type: Mapped[str]
    created_at: Mapped[str]
    deleted_at: Mapped[str | None]
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
