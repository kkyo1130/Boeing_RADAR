from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Flight(Base):
    __tablename__ = "flights"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(String, unique=True)
    started_at: Mapped[str]
    ended_at: Mapped[str | None]
    status: Mapped[str]
