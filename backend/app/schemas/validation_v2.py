"""Three-state comparison DTOs, distinct from legacy ClearanceStatus."""
from typing import Literal
from app.schemas.observation_v2 import ContractModel

Result = Literal["NORMAL", "MISMATCH", "UNVERIFIED"]
Stage = Literal["READBACK", "SETTING"]


class FieldVerdict(ContractModel):
    stage: Stage
    field: Literal["ALT", "HDG", "CALLSIGN"]
    instruction_id: str | None
    observation_id: str | None
    expected: int | str | None
    actual: int | str | None
    result: Result
    reason: str
    wait_until: str | None = None


class StageVerdict(ContractModel):
    result: Result
    fields: list[FieldVerdict]


class ValidationSnapshot(ContractModel):
    validation_version: Literal["1"] = "1"
    result: Result
    phase: Literal["WAITING_ATC", "READBACK", "SETTING", "MONITORING", "ENDED"]
    reason: str
    representative_stage: Stage | None
    readback: StageVerdict
    setting: StageVerdict
    advisory_candidates: list[FieldVerdict]
