from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import FlightStatus

class FlightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    flight_id: str = Field(description='비행 세션 고유 ID. FLT-YYYYMMDD-NNN 형식')
    started_at: str = Field(description='비행 시작 시각(UTC ISO 8601)')
    ended_at: str | None = Field(description='비행 종료 시각(UTC ISO 8601). 종료 전에는 null')
    status: FlightStatus = Field(description='현재 처리 상태')
