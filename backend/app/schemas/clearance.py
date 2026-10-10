from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import ClearanceStatus
from app.schemas.observation import Observation

class ValidationError(BaseModel):
    field: str = Field(description='비교 또는 변경 대상: ALT(고도), HDG(방위). 일반 이벤트는 null')
    expected: int = Field(description='기대값. 오류 이벤트는 ATC 기준값, 수정 이벤트는 수정 전 값')
    actual: int = Field(description='실제 비교값 또는 수정 후 값')

class ClearanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    clearance_id: str = Field(description='관제 지시 고유 ID. CLR-NNN 형식. 비행 자체 이벤트는 null')
    flight_id: str = Field(description='비행 세션 고유 ID. FLT-YYYYMMDD-NNN 형식')
    atc: Observation = Field(description='해당 지시의 ATC Observation')
    readback: Observation | None = Field(description='최신 복명복창 Observation. 미입력 시 null')
    cockpit: Observation | None = Field(description='최신 Cockpit Observation. 미입력 시 null')
    status: ClearanceStatus = Field(description='현재 처리 상태')
    errors: list[ValidationError] = Field(description='현재 ALT/HDG 불일치 목록. 오류가 없으면 빈 배열')
