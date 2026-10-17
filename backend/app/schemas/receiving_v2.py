"""Receiving policy and session DTOs; these do not perform three-state comparison."""
from pydantic import Field, model_validator
from app.schemas.observation_v2 import ContractModel, Identifier, Reason, Score


class FreshnessPolicy(ContractModel):
    max_age_seconds: float = Field(strict=True, gt=0, allow_inf_nan=False)
    max_future_skew_seconds: float = Field(strict=True, ge=0, allow_inf_nan=False)
    minimum_model_score: Score | None


class ReceiverConfig(ContractModel):
    callsigns: dict[Identifier, dict[Identifier, Reason]]
    freshness: FreshnessPolicy | None

    @model_validator(mode="after")
    def check_aliases(self):
        seen = set()
        if not self.callsigns:
            raise ValueError("at least one registered callsign is required")
        for aliases in self.callsigns.values():
            if not aliases:
                raise ValueError("each callsign requires registered alias expressions")
            for raw in aliases.values():
                key = " ".join(raw.casefold().split())
                if key in seen:
                    raise ValueError("ambiguous or duplicated callsign alias")
                seen.add(key)
        return self


class StartFlightV2(ContractModel):
    callsign: Identifier


class CancelSegmentV2(ContractModel):
    reason: Reason
