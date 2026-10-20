"""Deterministic extraction checks; PASS is never an operational verdict."""
from typing import Literal

from pydantic import Field
from app.schemas.observation_v2 import ContractModel, Reason

RuleStatus = Literal["PASS", "INVALID", "NEEDS_REVIEW"]


class StructurePolicy(ContractModel):
    policy_ref: Reason
    max_altitude_ft: int | None = Field(strict=True, ge=0)
    max_altitude_change_ft: int | None = Field(strict=True, ge=0)
    max_heading_change_deg: int | None = Field(strict=True, ge=0, le=180)


class RuleCheck(ContractModel):
    rule: str
    field: Literal["ALT", "HDG", "CALLSIGN"] | None = None
    result: RuleStatus
    reason: str


class StructureResult(ContractModel):
    rules_version: Literal["1"] = "1"
    observation_id: str
    flight_id: str
    segment_id: str
    attempt_id: str
    result: RuleStatus
    policy_ref: str | None
    derived_values: dict[str, int]
    checks: list[RuleCheck]
