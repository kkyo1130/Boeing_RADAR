"""Explicit user interaction, distinct from correction and resolution."""
from typing import Literal
from app.schemas.observation_v2 import ContractModel, Identifier


class EvidenceInteraction(ContractModel):
    event_id: Identifier
    instruction_id: Identifier
    observation_id: Identifier
    stage: Literal["READBACK", "SETTING"]
    field: Literal["ALT", "HDG", "CALLSIGN"]
    action: Literal["ACKNOWLEDGED", "EVIDENCE_OPENED"]
