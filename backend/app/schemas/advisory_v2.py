"""Server owns eligibility; clients only report input and playback outcomes."""
from typing import Literal
from app.schemas.observation_v2 import ContractModel, Identifier

class VoiceClaim(ContractModel):
    attempt_id: Identifier
    candidate_id: Identifier

class VoiceResult(ContractModel):
    status: Literal['COMPLETED', 'INTERRUPTED', 'FAILED']

class VoiceInput(ContractModel):
    event_id: Identifier
    token: Identifier
    kind: Literal['ATC', 'PILOT', 'SIMULATION', 'EVIDENCE']
    action: Literal['BEGIN', 'END']
