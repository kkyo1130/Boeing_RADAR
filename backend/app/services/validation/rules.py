"""Check extraction consistency, never repair values or assert operational safety."""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.schemas.observation_contract import ObservationContract


class RulePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    policy_id: Annotated[str, Field(min_length=1)]
    max_altitude_feet: Annotated[int, Field(strict=True, gt=0)]
    max_altitude_change_feet: Annotated[int, Field(strict=True, ge=0)]
    max_heading_change_degrees: Annotated[int, Field(strict=True, ge=0, le=180)]
    change_window_seconds: Annotated[float, Field(strict=True, gt=0)]


class RuleContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_callsign: str | None
    expected_conditions: list[str] | None
    expected_ordered_actions: list[str] | None


class RuleIssue(BaseModel):
    status: Literal["INVALID", "NEEDS_REVIEW"]
    code: str
    field: str
    expected: str | int | float | list[str] | None = None
    actual: str | int | float | list[str] | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RuleResult(BaseModel):
    status: Literal["PASS", "INVALID", "NEEDS_REVIEW"]
    policy_id: str | None
    issues: list[RuleIssue]


def normalized(text):
    # No synonym expansion, number guessing, fuzzy callsign match or negation removal.
    return " ".join(text.casefold().split())


def check_observation(data, *, policy=None, context=None, previous=None):
    """Return all issues. Missing policy/context never silently enables PASS.

    context must come from the session/confirmed instruction, not be copied from
    the same extraction to manufacture agreement. Inputs are not mutated.
    """
    policy = RulePolicy.model_validate(policy) if policy is not None else None
    context = RuleContext.model_validate(context) if context is not None else None
    issues = []

    def add(status, code, field, expected=None, actual=None, evidence_ids=None):
        issues.append(RuleIssue(status=status, code=code, field=field,
                                expected=expected, actual=actual,
                                evidence_ids=evidence_ids or []))

    def result():
        statuses = {issue.status for issue in issues}
        status = "INVALID" if "INVALID" in statuses else "NEEDS_REVIEW" if statuses else "PASS"
        return RuleResult(status=status, policy_id=policy.policy_id if policy else None, issues=issues)

    try:
        observation = ObservationContract.model_validate(data)
    except ValidationError as error:
        for detail in error.errors():
            add("INVALID", "contract_violation", ".".join(map(str, detail["loc"])))
        return result()
    if observation.event_type == "health":
        add("NEEDS_REVIEW", "health_without_observation", "health", actual=observation.health.status)
        return result()
    if policy is None:
        add("NEEDS_REVIEW", "policy_missing", "policy")
    if observation.health.status != "available":
        add("NEEDS_REVIEW", observation.health.reason, "health")
    if observation.captured_at is None:
        add("NEEDS_REVIEW", "capture_time_unknown", "captured_at")
    for key in ("altitude", "heading"):
        field = getattr(observation.fields, key)
        if field is None:  # Nonrequested field, not a numeric zero or failed read.
            continue
        refs = field.evidence_ids
        if field.value is None:
            add("NEEDS_REVIEW", field.reason, key, evidence_ids=refs)
            continue
        if field.quality.status != "acceptable":
            add("NEEDS_REVIEW", "input_quality", key, actual=field.quality.status, evidence_ids=refs)
        if key == "altitude" and policy and field.value > policy.max_altitude_feet:
            add("INVALID", "altitude_above_policy", key, expected=policy.max_altitude_feet,
                actual=field.value, evidence_ids=refs)
        raw = field.raw_text
        if raw is None or not raw.strip():
            add("NEEDS_REVIEW", "raw_text_missing", key, evidence_ids=refs)
            continue
        raw = raw.strip()
        parsed = None
        if key == "altitude" and raw.upper().startswith("FL"):
            if not re.fullmatch(r"FL ?[0-9]{3}", raw, flags=re.IGNORECASE):
                add("INVALID", "invalid_fl_format", key, actual=raw, evidence_ids=refs)
            else:
                parsed = int(re.sub(r"\s", "", raw)[2:]) * 100
        elif re.fullmatch(r"[0-9]{1,5}" if key == "altitude" else r"[0-9]{1,3}", raw):
            parsed = int(raw)
        else:
            # Spoken numbers/free text need a separate STT structure parser.
            add("NEEDS_REVIEW", "unsupported_raw_format", key, actual=raw, evidence_ids=refs)
        if parsed is not None:
            if key == "heading" and parsed > 359:
                add("INVALID", "heading_out_of_range", key, expected="0..359", actual=parsed, evidence_ids=refs)
            if parsed != field.value:
                add("INVALID", "raw_value_conflict", key, expected=parsed, actual=field.value, evidence_ids=refs)
        if key == "altitude" and policy and parsed is not None and parsed > policy.max_altitude_feet and field.value <= policy.max_altitude_feet:
            add("INVALID", "altitude_above_policy", key, expected=policy.max_altitude_feet,
                actual=parsed, evidence_ids=refs)

    if observation.speech is not None:
        speech = observation.speech
        if not speech.transcript or not speech.transcript.strip() or not speech.role_basis or not speech.role_basis.strip():
            add("NEEDS_REVIEW", "speech_context_incomplete", "speech")
        expected_callsign = context.expected_callsign if context else None
        if not speech.callsign:
            add("NEEDS_REVIEW", "callsign_missing", "speech.callsign")
        elif not expected_callsign or not expected_callsign.strip():
            add("NEEDS_REVIEW", "callsign_context_missing", "speech.callsign")
        elif speech.callsign.upper() != expected_callsign.strip().upper():
            add("INVALID", "callsign_conflict", "speech.callsign", expected_callsign, speech.callsign)
        for name in ("conditions", "ordered_actions"):
            actual = getattr(speech, name)
            expected = getattr(context, f"expected_{name}") if context else None
            if expected is None:
                add("NEEDS_REVIEW", "instruction_context_missing", f"speech.{name}")
            elif any(not item.strip() for item in actual + expected):
                add("NEEDS_REVIEW", "empty_context_item", f"speech.{name}")
            elif [normalized(item) for item in actual] != [normalized(item) for item in expected]:
                add("INVALID", f"{name}_conflict", f"speech.{name}", expected, actual)

    if previous is not None:
        try:
            old = ObservationContract.model_validate(previous)
        except ValidationError:
            add("NEEDS_REVIEW", "invalid_previous_observation", "previous")
            return result()
        if old.event_type != "observation" or (old.flight_id, old.clearance_id, old.source) != (
                observation.flight_id, observation.clearance_id, observation.source):
            add("NEEDS_REVIEW", "unrelated_previous_observation", "previous")
        elif old.captured_at is None or observation.captured_at is None:
            add("NEEDS_REVIEW", "change_time_unknown", "previous")
        else:
            delta = (observation.captured_at - old.captured_at).total_seconds()
            if delta <= 0 or old.sample_id == observation.sample_id or old.observation_id == observation.observation_id:
                add("NEEDS_REVIEW", "non_new_observation", "previous")
            elif policy and delta <= policy.change_window_seconds:
                for key in ("altitude", "heading"):
                    before, after = getattr(old.fields, key), getattr(observation.fields, key)
                    if before is None or after is None or before.value is None or after.value is None:
                        continue
                    change = abs(after.value - before.value)
                    if key == "heading":
                        change = min(change, 360 - change)
                    threshold = policy.max_altitude_change_feet if key == "altitude" else policy.max_heading_change_degrees
                    if change > threshold:
                        add("NEEDS_REVIEW", "rapid_change", key, threshold, change, after.evidence_ids)
    return result()
