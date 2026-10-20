"""Additive v2 storage; legacy tables and snapshots retain their wire shape."""
from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class V2FlightContext(Base):
    __tablename__ = "v2_flight_contexts"
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), primary_key=True)
    callsign: Mapped[str]
    callsign_registry: Mapped[dict] = mapped_column(JSON)
    policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    revision: Mapped[int] = mapped_column(default=0)
    state: Mapped[dict] = mapped_column(JSON)


class V2Instruction(Base):
    __tablename__ = "v2_instructions"
    atc_input_id: Mapped[str] = mapped_column(primary_key=True)
    instruction_id: Mapped[str] = mapped_column(unique=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    atc_segment_id: Mapped[str]
    atc_attempt_id: Mapped[str]
    latest_pilot_attempt_id: Mapped[str | None]
    status: Mapped[str]


class V2Segment(Base):
    __tablename__ = "v2_segments"
    segment_id: Mapped[str] = mapped_column(primary_key=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    atc_input_id: Mapped[str] = mapped_column(ForeignKey("v2_instructions.atc_input_id"))
    attempt_id: Mapped[str] = mapped_column(unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str]
    cancelled: Mapped[bool] = mapped_column(default=False)


class V2TraceEvent(Base):
    __tablename__ = "v2_trace_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    event_type: Mapped[str]
    occurred_at: Mapped[str]
    revision: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)


class V2Input(Base):
    __tablename__ = "v2_inputs"
    __table_args__ = (UniqueConstraint("kind", "input_id"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    kind: Mapped[str]
    input_id: Mapped[str]
    source: Mapped[str]
    sample_id: Mapped[str | None]
    fingerprint: Mapped[str]
    received_at: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    applied: Mapped[bool]
    reason: Mapped[str]
    event_id: Mapped[int] = mapped_column(ForeignKey("v2_trace_events.id"))


class V2Migration(Base):
    __tablename__ = "v2_schema_migrations"
    version: Mapped[str] = mapped_column(primary_key=True)
    applied_at: Mapped[str]
