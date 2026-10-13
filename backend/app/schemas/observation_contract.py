"""radar-observation/1 contract only; not registered on legacy API routes."""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Identifier = Annotated[str, Field(min_length=1, pattern=r"^\S+$")]
Reason = Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Quality(ContractModel):
    status: Literal["acceptable", "degraded", "unknown"]
    reasons: list[Reason]

    @model_validator(mode="after")
    def check_reasons(self):
        if (self.status == "acceptable") != (not self.reasons):
            raise ValueError("acceptable quality has no reasons; other quality requires reasons")
        return self


class Health(ContractModel):
    status: Literal["available", "degraded", "unavailable"]
    reason: Reason | None

    @model_validator(mode="after")
    def check_reason(self):
        if (self.status == "available") != (self.reason is None):
            raise ValueError("available health has no reason; other health requires a reason")
        return self


class Evidence(ContractModel):
    evidence_id: Identifier
    kind: Literal["image", "audio"]
    reference: Identifier
    availability: Literal["available", "missing", "unavailable"]
    roi: tuple[Annotated[int, Field(strict=True, ge=0)],
               Annotated[int, Field(strict=True, ge=0)],
               Annotated[int, Field(strict=True, ge=0)],
               Annotated[int, Field(strict=True, ge=0)]] | None

    @model_validator(mode="after")
    def check_roi(self):
        if self.roi is not None:
            left, top, right, bottom = self.roi
            if self.kind != "image" or right <= left or bottom <= top:
                raise ValueError("ROI must be a nonempty image rectangle")
        return self


class FieldObservation(ContractModel):
    value: Annotated[int, Field(strict=True, ge=0)] | None
    reason: Reason | None
    raw_text: str | None
    model_score: Annotated[float, Field(strict=True, ge=0, le=1)] | None
    score_calibrated: Literal[False]
    quality: Quality
    evidence_ids: list[Identifier]

    @field_validator("score_calibrated", mode="before")
    @classmethod
    def require_uncalibrated_boolean(cls, value):
        if value is not False:
            raise ValueError("score_calibrated must be the boolean false")
        return value

    @model_validator(mode="after")
    def check_missing(self):
        if (self.value is None) != (self.reason is not None):
            raise ValueError("null value requires reason; present value requires null reason")
        return self


class AltitudeObservation(FieldObservation):
    unit: Literal["feet"]


class HeadingObservation(FieldObservation):
    value: Annotated[int, Field(strict=True, ge=0, le=359)] | None
    unit: Literal["degrees"]


class ObservedFields(ContractModel):
    altitude: AltitudeObservation | None
    heading: HeadingObservation | None


class SpeechContext(ContractModel):
    transcript: str | None
    callsign: Identifier | None
    callsign_reason: Reason | None
    role_basis: str | None
    conditions: list[str]
    ordered_actions: list[str]

    @model_validator(mode="after")
    def check_callsign(self):
        if (self.callsign is None) != (self.callsign_reason is not None):
            raise ValueError("missing callsign requires reason")
        return self


class ObservationContract(ContractModel):
    schema_version: Literal["radar-observation/1"]
    event_type: Literal["observation", "health"]
    event_id: Identifier
    observation_id: Identifier | None
    flight_id: Identifier
    clearance_id: Identifier | None
    source: Literal["ATC", "READBACK", "COCKPIT"]
    channel_id: Identifier
    input_mode: Literal["camera", "microphone", "sdr", "image_file", "audio_file", "video_file", "fixture"]
    sample_id: Identifier | None
    captured_at: datetime | None
    capture_time_basis: Literal["device", "host_receive", "provided", "unknown"]
    processed_at: datetime
    health: Health
    intent: Literal["initial", "correction"] | None
    supersedes_observation_id: Identifier | None
    fields: ObservedFields | None
    speech: SpeechContext | None
    evidence: list[Evidence]

    @field_validator("captured_at", "processed_at", mode="before")
    @classmethod
    def require_utc(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must be an explicit UTC ISO 8601 datetime")
        return value

    @model_validator(mode="after")
    def check_event(self):
        if (self.captured_at is None) != (self.capture_time_basis == "unknown"):
            raise ValueError("unknown capture time must be null")
        if self.captured_at is not None and self.captured_at > self.processed_at:
            raise ValueError("capture time cannot follow processing time")
        if self.event_type == "health":
            if any(x is not None for x in (self.observation_id, self.sample_id, self.fields,
                                          self.intent, self.supersedes_observation_id, self.speech)) or self.evidence:
                raise ValueError("health event must not reuse an observation or evidence")
            return self
        if any(x is None for x in (self.observation_id, self.sample_id, self.clearance_id, self.fields, self.intent)):
            raise ValueError("observation requires sample, observation, clearance IDs, fields and intent")
        if self.intent == "correction":
            if not self.supersedes_observation_id or self.supersedes_observation_id == self.observation_id:
                raise ValueError("correction must reference a distinct previous observation")
        elif self.supersedes_observation_id is not None:
            raise ValueError("initial observation cannot supersede an observation")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("duplicate evidence IDs")
        fields = [self.fields.altitude, self.fields.heading]
        if all(item is None for item in fields):
            raise ValueError("observation must contain at least one requested field")
        for item in fields:
            if item is None:
                continue
            if not set(item.evidence_ids).issubset(evidence_ids):
                raise ValueError("field references unknown evidence")
            if self.health.status == "unavailable" and item.value is not None:
                raise ValueError("unavailable channel cannot emit a numeric observation")
        if self.source == "COCKPIT" and self.speech is not None:
            raise ValueError("cockpit observation cannot contain speech context")
        if self.source != "COCKPIT" and self.speech is None:
            raise ValueError("speech source requires context, including missing callsign reason")
        return self
