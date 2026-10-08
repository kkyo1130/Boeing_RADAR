from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Clearance(Base):
    __tablename__ = "clearances"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clearance_id: Mapped[str] = mapped_column(unique=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"), index=True)
    atc: Mapped[dict] = mapped_column(JSON)
    readback: Mapped[dict | None] = mapped_column(JSON)
    cockpit: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str]
    errors: Mapped[list] = mapped_column(JSON, default=list)
