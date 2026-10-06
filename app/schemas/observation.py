from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.enums import Source

class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"transcript": "Climb and maintain flight level one eight zero heading two four zero",
         "altitude": 18000, "heading": 240, "confidence": 0.96,
         "observed_at": "2026-10-04T05:32:02Z"}
    ]})
    transcript: str | None = Field(default=None, description="인식된 발화 텍스트. Cockpit 입력에서는 null 또는 생략 가능")
    altitude: int = Field(ge=0, strict=True, description="고도 설정값(feet). 0 이상의 정수", examples=[18000])
    heading: int = Field(ge=0, le=359, strict=True, description="방위 설정값(degrees). 0~359 정수", examples=[240])
    confidence: float = Field(ge=0, le=1, description="입력 신뢰도(0~1). 현재 비교 결과에는 반영하지 않음", examples=[0.96])
    observed_at: datetime | None = Field(default=None, description="Observation 관측 시각(ISO 8601). 생략 시 서버 시각, 시간대 미지정 시 UTC")

    @field_validator("observed_at")
    @classmethod
    def normalize_time(cls, value):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc) if value else None

    def observation(self, source: Source):
        data = self.model_dump(mode="json")
        data["source"] = source.value
        data["observed_at"] = (self.observed_at or datetime.now(timezone.utc)).isoformat()
        return data

class Observation(ObservationInput):
    source: Source
    observed_at: datetime
