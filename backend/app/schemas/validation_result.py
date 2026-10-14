from typing import Literal
from pydantic import BaseModel
from app.schemas.clearance import ValidationError as ComparisonError
from app.schemas.observation_contract import ObservationContract
from app.schemas.validation_settings import ValidationSettings
from app.services.validation.rules import RuleResult

Verdict = Literal["NORMAL", "MISMATCH", "UNVERIFIED"]


class FieldComparison(BaseModel):
    field: Literal["altitude", "heading"]
    expected: int
    actual: int
    verdict: Literal["NORMAL", "MISMATCH"]


class ValidationStage(BaseModel):
    verdict: Verdict
    reasons: list[str]
    errors: list[ComparisonError]
    comparisons: list[FieldComparison]
    rules: RuleResult | None


class ValidationContext(BaseModel):
    confirmed_at: str
    settings: ValidationSettings


class ClearanceDecisionResponse(BaseModel):
    clearance_id: str
    flight_id: str
    created_at: str
    active: bool
    status: Literal["UNVERIFIED", "READBACK_ERROR", "SETTING_ERROR", "VERIFIED", "RESOLVED"]
    verdict: Verdict
    reasons: list[str]
    errors: list[ComparisonError]
    observations: dict[Literal["ATC", "READBACK", "COCKPIT"], ObservationContract]
    stages: dict[Literal["atc", "readback", "cockpit"], ValidationStage]
    resolutions: dict[Literal["readback", "cockpit"], Literal["RESOLVED"]]
    validation_context: ValidationContext | None
