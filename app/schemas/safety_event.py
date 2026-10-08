from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import EventType
from app.schemas.observation import Observation

class SafetyEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description='이벤트 고유 번호. 동일 timestamp의 정렬 기준')
    flight_id: str = Field(description='비행 세션 고유 ID. FLT-YYYYMMDD-NNN 형식')
    clearance_id: str | None = Field(description='관제 지시 고유 ID. CLR-NNN 형식. 비행 자체 이벤트는 null')
    event_type: EventType = Field(description='인식·오류·경보·수정·재검증·비행 수명주기 이벤트 유형')
    field: str | None = Field(description='비교 또는 변경 대상: ALT(고도), HDG(방위). 일반 이벤트는 null')
    expected: int | None = Field(description='기대값. 오류 이벤트는 ATC 기준값, 수정 이벤트는 수정 전 값')
    actual: int | None = Field(description='실제 비교값 또는 수정 후 값')
    timestamp: str = Field(description='서버가 이벤트를 기록한 시각(UTC ISO 8601)')
    observation: Observation | None = Field(description='이벤트 발생 당시 입력 스냅샷. Observation 입력 외 이벤트는 null')
