"""Additive v2 occurrence response, independent of legacy clearance enums."""
from typing import Literal
from app.schemas.observation_v2 import ContractModel, EvidenceRef
from app.schemas.validation_v2 import FieldVerdict


class IncidentEvidence(ContractModel):
    observation_id: str
    observed_at: str
    frame_id: str | None
    segment_id: str | None
    attempt_id: str | None
    evidence_refs: list[EvidenceRef]
    evidence_unavailable_reason: str | None


class IncidentV1(ContractModel):
    occurrence_id: str
    flight_id: str
    instruction_id: str
    stage: Literal["READBACK", "SETTING"]
    field: Literal["ALT", "HDG", "CALLSIGN"]
    status: Literal["OPEN", "RESOLVED", "SUPERSEDED", "ENDED_UNRESOLVED"]
    detected_at: str
    first_evidence: IncidentEvidence
    latest_evidence: IncidentEvidence
    last_mismatch_evidence: IncidentEvidence
    current_check: FieldVerdict
    first_check: FieldVerdict
    reobserved_at: str | None
    reverified_at: str | None
    resolved_at: str | None
    closed_at: str | None
    close_reason: str | None
    resolution_evidence: IncidentEvidence | None
    notified_at: str | None
    voice_completed_at: str | None
