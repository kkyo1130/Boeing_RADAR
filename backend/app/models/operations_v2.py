"""Additional artifacts only; v2 remains the single observation/decision store."""
from sqlalchemy import ForeignKey, JSON, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class V2Report(Base):
    __tablename__ = 'v2_reports'
    flight_id: Mapped[str] = mapped_column(ForeignKey('v2_flight_contexts.flight_id'), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class V2Media(Base):
    __tablename__ = 'v2_media'
    evidence_id: Mapped[str] = mapped_column(primary_key=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey('v2_flight_contexts.flight_id'), index=True)
    media_type: Mapped[str]
    created_at: Mapped[str]
    deleted_at: Mapped[str | None]
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
