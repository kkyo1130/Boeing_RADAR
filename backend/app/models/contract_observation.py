"""Additive storage for the versioned contract, isolated from legacy Mock DTOs."""
from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class ContractClearance(Base):
    __tablename__ = "contract_clearances"
    clearance_id: Mapped[str] = mapped_column(primary_key=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    created_at: Mapped[str]
    active: Mapped[bool]
    latest: Mapped[dict] = mapped_column(JSON, default=dict)


class ContractEvent(Base):
    __tablename__ = "contract_events"
    __table_args__ = (UniqueConstraint("flight_id", "channel_id", "sample_id"),)
    event_id: Mapped[str] = mapped_column(primary_key=True)
    observation_id: Mapped[str | None] = mapped_column(unique=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    clearance_id: Mapped[str | None] = mapped_column(ForeignKey("contract_clearances.clearance_id"))
    channel_id: Mapped[str]
    sample_id: Mapped[str | None]
    source: Mapped[str]
    processed_at: Mapped[str]
    received_at: Mapped[str]
    accepted: Mapped[bool]
    reasons: Mapped[list] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)


class ContractValidationSettings(Base):
    __tablename__ = "contract_validation_settings"
    clearance_id: Mapped[str] = mapped_column(ForeignKey("contract_clearances.clearance_id"), primary_key=True)
    confirmed_at: Mapped[str]
    settings: Mapped[dict] = mapped_column(JSON)
