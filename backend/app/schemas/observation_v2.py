"""SPEC-002 v2 wire contracts. These DTOs are not mounted on the current API.

JSON Schema covers structural and local value constraints. Cross-object rules
and time ordering are also checked by these DTOs. Freshness, callsign registry,
flight/attempt ownership and safety decisions belong to the receiving service.
"""
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, RootModel,
    StrictBool, StrictInt, StringConstraints, model_validator,
)
from typing_extensions import NotRequired, TypedDict

Identifier = Annotated[str, StringConstraints(
    strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
)]
Reason = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
Text = Annotated[str, StringConstraints(strict=True)]
FieldName = Literal["ALT", "HDG"]
NonnegativeInt = Annotated[StrictInt, Field(ge=0)]
HeadingInt = Annotated[StrictInt, Field(ge=0, le=359)]
Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


def _calendar_timestamp(value: str) -> str:
    # Pattern enforces a canonical UTC wire representation, parser checks dates.
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


UtcTimestamp = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$",
    ),
    AfterValidator(_calendar_timestamp),
    Field(json_schema_extra={"format": "date-time"}),
]


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _coherent_value_schema(schema: dict) -> None:
    schema["allOf"] = [
        {
            "if": {"properties": {"validity": {"const": "VALID"}}},
            "then": {"properties": {"value": {"type": "integer"}, "reason": {"type": "null"}}},
            "else": {"properties": {"value": {"type": "null"}, "reason": {"type": "string", "minLength": 1}}},
        }
    ]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Quality(ContractModel):
    """Uncalibrated model scores and measured input quality are separate."""
    model_score: Score | None
    input_quality: Literal["SUFFICIENT", "INSUFFICIENT", "UNKNOWN"]
    reason: Reason | None
    score_calibrated: StrictBool
    calibration_ref: Reason | None

    @model_validator(mode="after")
    def check_quality(self):
        if (self.model_score is None or self.input_quality != "SUFFICIENT") and self.reason is None:
            raise ValueError("unknown score or insufficient/unknown quality requires a reason")
        if self.score_calibrated != (self.calibration_ref is not None):
            raise ValueError("calibration_ref is required exactly when score_calibrated is true")
        if self.score_calibrated and self.model_score is None:
            raise ValueError("an absent score cannot be calibrated")
        return self


class Reading(ContractModel):
    validity: Literal["VALID", "UNREADABLE", "INVALID"]
    reason: Reason | None
    raw_text: Text | None
    quality: Quality

    @model_validator(mode="after")
    def check_value(self):
        if self.validity == "VALID":
            if self.value is None or self.reason is not None:
                raise ValueError("VALID requires a value and null reason")
        elif self.value is not None or self.reason is None:
            raise ValueError("UNREADABLE/INVALID requires null value and an explicit reason")
        return self


class AltitudeReading(Reading):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_coherent_value_schema)
    value: NonnegativeInt | None
    unit: Literal["ft"]


class HeadingReading(Reading):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_coherent_value_schema)
    value: HeadingInt | None
    unit: Literal["deg"]


class CockpitFields(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")
    ALT: AltitudeReading
    HDG: HeadingReading


class SpeechFields(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")
    ALT: NotRequired[AltitudeReading]
    HDG: NotRequired[HeadingReading]


class CallsignReading(ContractModel):
    raw_text: Text | None
    value: Identifier | None
    validity: Literal["VALID", "UNREADABLE", "INVALID"]
    reason: Reason | None
    alias_key: Identifier | None
    quality: Quality

    @model_validator(mode="after")
    def check_callsign(self):
        if self.validity == "VALID":
            if not self.raw_text or self.value is None or self.alias_key is None or self.reason is not None:
                raise ValueError("VALID callsign requires raw_text, value, registered alias_key, null reason")
        elif self.value is not None or self.alias_key is not None or self.reason is None:
            raise ValueError("unverified callsign requires null normalized value/alias and a reason")
        return self


class ChannelHealth(ContractModel):
    status: Literal["AVAILABLE", "DEGRADED", "DISCONNECTED"]
    reason: Reason | None

    @model_validator(mode="after")
    def check_reason(self):
        if self.status == "AVAILABLE" and self.reason is not None:
            raise ValueError("AVAILABLE requires null reason")
        if self.status != "AVAILABLE" and self.reason is None:
            raise ValueError("DEGRADED/DISCONNECTED requires a reason")
        return self


class EvidenceRef(ContractModel):
    evidence_id: Identifier
    kind: Literal["FRAME", "ROI", "AUDIO", "TRANSCRIPT"]
    ref: Reason
    field: FieldName | None
    roi: tuple[NonnegativeInt, NonnegativeInt, NonnegativeInt, NonnegativeInt] | None

    @model_validator(mode="after")
    def check_roi(self):
        if self.kind == "ROI":
            if self.field is None or self.roi is None:
                raise ValueError("ROI evidence requires field and pixel coordinates")
            left, top, right, bottom = self.roi
            if right <= left or bottom <= top:
                raise ValueError("ROI must have positive width and height")
        elif self.roi is not None:
            raise ValueError("coordinates belong only to ROI evidence")
        return self


class ObservationBase(ContractModel):
    schema_version: Literal["2"]
    observation_id: Identifier
    flight_id: Identifier
    observed_at: UtcTimestamp | None
    processed_at: UtcTimestamp
    time_basis: Literal["CAPTURED", "HOST_RECEIVE", "UNKNOWN"]
    time_reason: Reason | None
    target_revision: NonnegativeInt
    channel_health: ChannelHealth
    evidence_refs: list[EvidenceRef]
    evidence_unavailable_reason: Reason | None

    @model_validator(mode="after")
    def check_context(self):
        if self.time_basis == "UNKNOWN":
            if self.observed_at is not None or self.time_reason is None:
                raise ValueError("UNKNOWN time requires null observed_at and a reason")
        elif self.observed_at is None or self.time_reason is not None:
            raise ValueError("known time requires observed_at and null time_reason")
        if self.observed_at is not None and _time(self.processed_at) < _time(self.observed_at):
            raise ValueError("processed_at must not precede observed_at")
        if bool(self.evidence_refs) == (self.evidence_unavailable_reason is not None):
            raise ValueError("provide evidence_refs or an unavailable reason, exclusively")
        ids = [e.evidence_id for e in self.evidence_refs]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence IDs")
        return self


class CockpitObservation(ObservationBase):
    source: Literal["COCKPIT"]
    frame_id: Identifier
    fields: CockpitFields

    @model_validator(mode="after")
    def check_camera(self):
        if self.channel_health.status == "DISCONNECTED" and any(
            field.value is not None for field in self.fields.values()
        ):
            raise ValueError("disconnected camera cannot publish current numeric readings")
        if any(e.kind not in ("FRAME", "ROI") for e in self.evidence_refs):
            raise ValueError("COCKPIT evidence must be FRAME or ROI")
        return self


class SpeechObservation(ObservationBase):
    segment_id: Identifier
    atc_input_id: Identifier
    attempt_id: Identifier
    transcript: Text | None
    transcript_reason: Reason | None
    callsign: CallsignReading
    mention_status: Literal["KNOWN", "UNKNOWN"]
    mentioned_fields: list[FieldName] = Field(json_schema_extra={"uniqueItems": True})
    instruction_check: Literal["PASS", "INVALID", "NEEDS_REVIEW"]
    fields: SpeechFields

    @model_validator(mode="after")
    def check_speech(self):
        if bool(self.transcript) == (self.transcript_reason is not None):
            raise ValueError("provide a nonempty transcript or transcript_reason, exclusively")
        if self.transcript == "":
            raise ValueError("use null, not an empty transcript")
        if len(self.mentioned_fields) != len(set(self.mentioned_fields)):
            raise ValueError("mentioned_fields must be unique")
        if set(self.mentioned_fields) != set(self.fields):
            raise ValueError("mentioned_fields and fields keys must agree")
        if self.instruction_check == "PASS" and (
            self.mention_status != "KNOWN" or not self.fields
            or self.callsign.validity != "VALID" or not self.transcript
            or self.channel_health.status != "AVAILABLE"
            or any(field.validity != "VALID" for field in self.fields.values())
        ):
            raise ValueError("PASS requires known mentions, complete valid extraction and available input")
        if any(e.kind not in ("AUDIO", "TRANSCRIPT") for e in self.evidence_refs):
            raise ValueError("speech evidence must be AUDIO or TRANSCRIPT")
        return self


class AtcObservation(SpeechObservation):
    source: Literal["ATC"]


class ReadbackObservation(SpeechObservation):
    source: Literal["READBACK"]
    instruction_id: Identifier


class ObservationV2(RootModel):
    root: Annotated[
        Union[CockpitObservation, AtcObservation, ReadbackObservation],
        Field(discriminator="source"),
    ]


class HealthEventV2(ContractModel):
    schema_version: Literal["2"]
    event_id: Identifier
    flight_id: Identifier
    channel: Literal["CAMERA", "MICROPHONE", "SPEECH_API"]
    observed_at: UtcTimestamp
    health: ChannelHealth


class AltitudeTarget(ContractModel):
    value: NonnegativeInt
    unit: Literal["ft"]
    instruction_id: Identifier
    source_observation_id: Identifier
    adopted_at: UtcTimestamp


class HeadingTarget(ContractModel):
    value: HeadingInt
    unit: Literal["deg"]
    instruction_id: Identifier
    source_observation_id: Identifier
    adopted_at: UtcTimestamp


class Targets(ContractModel):
    ALT: AltitudeTarget | None
    HDG: HeadingTarget | None


class ReadbackRequired(ContractModel):
    instruction_id: Identifier
    atc_input_id: Identifier
    fields: list[FieldName] = Field(min_length=1, max_length=2, json_schema_extra={"uniqueItems": True})
    callsign_required: StrictBool = Field(json_schema_extra={"const": True})

    @model_validator(mode="after")
    def check_unique(self):
        if not self.callsign_required:
            raise ValueError("callsign is always required for a readback")
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("duplicate required fields")
        return self


class TargetSnapshotV2(ContractModel):
    schema_version: Literal["2"]
    flight_id: Identifier
    revision: NonnegativeInt
    targets: Targets
    readback_required: ReadbackRequired | None

    @model_validator(mode="after")
    def check_sources(self):
        request = self.readback_required
        if request is not None:
            matching = {
                name for name in ("ALT", "HDG")
                if (target := getattr(self.targets, name)) is not None
                and target.instruction_id == request.instruction_id
            }
            if matching != set(request.fields):
                raise ValueError("readback fields must match the current instruction's targets only")
        return self


class SpeechSegmentV2(ContractModel):
    schema_version: Literal["2"]
    flight_id: Identifier
    segment_id: Identifier
    atc_input_id: Identifier
    attempt_id: Identifier
    role: Literal["ATC", "PILOT"]
    role_basis: Literal["ATC_PLAYBACK", "PILOT_PTT"]
    started_at: UtcTimestamp
    ended_at: UtcTimestamp
    complete: StrictBool
    interruption_reason: Reason | None
    audio_ref: Reason | None
    audio_unavailable_reason: Reason | None

    @model_validator(mode="after")
    def check_segment(self):
        if (self.role == "ATC") != (self.role_basis == "ATC_PLAYBACK"):
            raise ValueError("role must match the controlling action")
        if _time(self.ended_at) <= _time(self.started_at):
            raise ValueError("ended_at must be after started_at")
        if self.complete == (self.interruption_reason is not None):
            raise ValueError("complete segments have no interruption reason; incomplete ones require it")
        if (self.audio_ref is None) == (self.audio_unavailable_reason is None):
            raise ValueError("provide audio_ref or audio_unavailable_reason, exclusively")
        if self.complete and self.audio_ref is None:
            raise ValueError("complete input requires captured audio")
        return self


class IngestionReceiptV2(ContractModel):
    """Acknowledges durable receipt, never a NORMAL/VERIFIED safety verdict."""
    schema_version: Literal["2"]
    flight_id: Identifier
    input_id: Identifier
    event_id: Identifier
    received_at: UtcTimestamp
    disposition: Literal["ACCEPTED", "DUPLICATE"]


class ContractErrorV2(ContractModel):
    schema_version: Literal["2"]
    code: Literal[
        "INVALID_PAYLOAD", "UNSUPPORTED_VERSION", "NOT_FOUND", "FLIGHT_ENDED",
        "ID_CONTENT_CONFLICT", "CONTEXT_MISMATCH", "INVALID_SEQUENCE",
    ]
    message: Reason
    input_id: Identifier | None
    field_path: Text | None


SCHEMA_MODELS = {
    "observation-v2": ObservationV2,
    "health-event-v2": HealthEventV2,
    "target-snapshot-v2": TargetSnapshotV2,
    "speech-segment-v2": SpeechSegmentV2,
    "ingestion-receipt-v2": IngestionReceiptV2,
    "contract-error-v2": ContractErrorV2,
}
