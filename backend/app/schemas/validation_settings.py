from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.services.validation.rules import RuleContext, RulePolicy


class ValidationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    confirmed: Annotated[bool, Field(strict=True)]
    confirmed_by: Annotated[str, Field(min_length=1, pattern=r"^\S+$")]
    rule_policy: RulePolicy
    minimum_model_score: Annotated[float, Field(strict=True, ge=0, le=1)]
    atc_context: RuleContext

    @model_validator(mode="after")
    def require_confirmation(self):
        if not self.confirmed:
            raise ValueError("Policy and instruction context must be explicitly confirmed")
        return self
