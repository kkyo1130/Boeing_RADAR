"""SPEC-002-WI-01 contract validation; no v2 receiving routes are mounted."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
import pytest

from app.schemas.observation import ObservationInput
from app.schemas.observation_v2 import (
    ContractErrorV2, HealthEventV2, IngestionReceiptV2, ObservationV2,
    Quality, SCHEMA_MODELS, SpeechSegmentV2, TargetSnapshotV2,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "contracts" / "examples" / "v2"
MANIFEST = json.loads((EXAMPLES / "manifest.json").read_text())


def fixture(name):
    return json.loads((EXAMPLES / name).read_text())


def changed(payload, path, value):
    payload = deepcopy(payload)
    item = payload
    keys = path.split(".")
    for key in keys[:-1]:
        item = item[key]
    item[keys[-1]] = value
    return payload


@pytest.mark.parametrize("case", MANIFEST, ids=lambda c: c["file"])
def test_fixture_schema_and_semantic_expectations(case):
    payload = fixture(case["file"])
    schema = json.loads((ROOT / "contracts" / "schemas" / f"{case['schema']}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert validator.is_valid(payload) == case["schema_valid"]
    model = SCHEMA_MODELS[case["schema"]]
    if case["valid"]:
        parsed = model.model_validate(payload)
        # DTO serialization must retain omitted fields and wire validity/nulls.
        assert model.model_validate_json(parsed.model_dump_json()) == parsed
        assert validator.is_valid(json.loads(parsed.model_dump_json()))
    else:
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_generated_schemas_match_models_and_all_examples_are_registered():
    spec = importlib.util.spec_from_file_location("contract_check", ROOT / "contracts" / "check_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, rendered in module.rendered_schemas().items():
        assert (ROOT / "contracts" / "schemas" / f"{name}.schema.json").read_text() == rendered
    assert {c["file"] for c in MANIFEST} == {
        p.name for p in EXAMPLES.glob("*.json") if p.name != "manifest.json"
    }
    assert len(MANIFEST) == len({c["file"] for c in MANIFEST})


@pytest.mark.parametrize("path,value", [
    ("fields.ALT.value", -1),
    ("fields.ALT.value", "3000"),
    ("fields.ALT.value", True),
    ("fields.ALT.value", 3000.0),
    ("fields.HDG.value", 360),
    ("fields.HDG.value", -1),
    ("fields.HDG.value", False),
    ("fields.HDG.unit", "ft"),
    ("fields.ALT.unit", "FL"),
    ("fields.ALT.value", None),
    ("fields.HDG.reason", "guessed_value"),
    ("fields.ALT.validity", "NORMAL"),
    ("fields.HDG.quality.model_score", 1.01),
    ("fields.HDG.quality.model_score", -0.01),
    ("fields.HDG.quality.model_score", True),
    ("fields.HDG.quality.model_score", float("nan")),
    ("fields.HDG.quality.model_score", float("inf")),
    ("schema_version", "1"),
    ("schema_version", 2),
    ("flight_id", ""),
    ("observation_id", "bad ID with spaces"),
    ("target_revision", True),
    ("target_revision", -1),
    ("observed_at", "2026-10-17T01:00:01"),
    ("observed_at", "2026-10-17T10:00:01+09:00"),
    ("observed_at", "2026-02-30T01:00:01Z"),
    ("observed_at", 1792198801),
    ("processed_at", "2026-10-17T01:00:00Z"),
    ("time_basis", "UNKNOWN"),
    ("channel_health.status", "DISCONNECTED"),
    ("channel_health.reason", "camera_disconnected"),
    ("evidence_unavailable_reason", None),
    ("frame_id", None),
    ("source", "ATC"),
])
def test_reject_malformed_observations(path, value):
    payload = changed(fixture("cockpit-readable.json"), path, value)
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(payload)


@pytest.mark.parametrize("path,value", [
    ("fields.ALT.value", 0),
    ("fields.HDG.value", 359),
    ("fields.HDG.quality.model_score", 0.0),
    ("fields.HDG.quality.model_score", 1.0),
])
def test_real_zero_and_boundaries_remain_numbers(path, value):
    payload = changed(fixture("cockpit-readable.json"), path, value)
    ObservationV2.model_validate(payload)


@pytest.mark.parametrize("source", ["ATC", "READBACK", "COCKPIT"])
def test_source_specific_shape_forbids_foreign_fields(source):
    filename = {"ATC": "atc-full.json", "READBACK": "readback-partial.json", "COCKPIT": "cockpit-readable.json"}[source]
    payload = fixture(filename)
    payload["instruction_id" if source != "READBACK" else "frame_id"] = "foreign-context"
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(payload)


def test_omitted_field_and_failed_mention_are_preserved_differently():
    partial = ObservationV2.model_validate(fixture("atc-partial.json")).root
    ambiguous = ObservationV2.model_validate(fixture("atc-ambiguous.json")).root
    assert set(partial.fields) == {"ALT"}
    assert partial.fields["ALT"].value == 4000
    assert partial.mentioned_fields == ["ALT"]
    assert ambiguous.fields["ALT"].value is None
    assert ambiguous.fields["ALT"].reason == "number_not_recognized"
    assert ambiguous.instruction_check == "NEEDS_REVIEW"
    assert "HDG" not in json.loads(partial.model_dump_json())["fields"]


@pytest.mark.parametrize("path,value", [
    ("fields.HDG", None),
    ("mentioned_fields", ["ALT", "HDG", "HDG"]),
    ("mention_status", "UNKNOWN"),
    ("transcript", None),
    ("callsign.value", None),
    ("callsign.alias_key", None),
    ("callsign.raw_text", ""),
    ("callsign.reason", "not_registered"),
    ("channel_health", {"status": "DEGRADED", "reason": "overlap"}),
])
def test_speech_pass_requires_complete_coherent_extraction(path, value):
    payload = changed(fixture("atc-full.json"), path, value)
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(payload)


def test_unknown_time_and_old_time_are_recordable_but_not_normal_verdicts():
    unknown = ObservationV2.model_validate(fixture("cockpit-time-unknown.json")).root
    old = ObservationV2.model_validate(fixture("cockpit-stale.json")).root
    assert unknown.observed_at is None
    assert unknown.time_reason == "file_capture_time_unknown"
    assert old.observed_at == "2020-01-01T00:00:00Z"
    assert "result" not in old.model_dump()
    assert "status" not in old.model_dump()
    # Schema validation deliberately has no wall clock or safety verdict.
    for payload in (unknown.model_dump(), old.model_dump()):
        payload["result"] = "NORMAL"
        with pytest.raises(ValidationError):
            ObservationV2.model_validate(payload)


def test_disconnected_camera_only_reports_null_current_readings():
    payload = fixture("cockpit-unreadable.json")
    payload["channel_health"] = {"status": "DISCONNECTED", "reason": "camera_disconnected"}
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(payload)  # HDG270 is a last value, not a current reading.
    payload["fields"]["HDG"].update(value=None, validity="UNREADABLE", reason="camera_disconnected")
    ObservationV2.model_validate(payload)
    HealthEventV2.model_validate(fixture("camera-disconnected.json"))


@pytest.mark.parametrize("roi", [[0, 0, 0, 5], [0, 0, 5, 0], [3, 3, 1, 1], [-1, 0, 5, 5]])
def test_invalid_evidence_coordinates(roi):
    payload = fixture("cockpit-readable.json")
    payload.update(evidence_unavailable_reason=None, evidence_refs=[dict(
        evidence_id="roi-alt", kind="ROI", ref="fixture/alt.png", field="ALT", roi=roi,
    )])
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(payload)


def test_roi_and_original_frame_evidence_keep_distinct_references():
    payload = fixture("cockpit-readable.json")
    payload.update(evidence_unavailable_reason=None, evidence_refs=[
        dict(evidence_id="frame-evidence", kind="FRAME", ref="fixture/frame.png", field=None, roi=None),
        dict(evidence_id="alt-evidence", kind="ROI", ref="fixture/alt.png", field="ALT", roi=[0, 0, 50, 20]),
    ])
    parsed = ObservationV2.model_validate(payload).root
    assert parsed.evidence_refs[1].roi == (0, 0, 50, 20)
    payload["evidence_refs"][1]["evidence_id"] = "frame-evidence"
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(payload)


@pytest.mark.parametrize("changes", [
    {"model_score": None, "reason": None},
    {"input_quality": "UNKNOWN", "reason": None},
    {"score_calibrated": True, "calibration_ref": None},
    {"score_calibrated": False, "calibration_ref": "calibration-unclaimed"},
    {"score_calibrated": True, "calibration_ref": "calibration-run", "model_score": None},
])
def test_quality_never_silently_implies_accuracy(changes):
    payload = dict(model_score=0.9, input_quality="SUFFICIENT", reason=None,
                   score_calibrated=False, calibration_ref=None)
    payload.update(changes)
    with pytest.raises(ValidationError):
        Quality.model_validate(payload)


def test_partial_targets_keep_provenance_and_only_new_readback_scope():
    data = fixture("targets-partial.json")
    parsed = TargetSnapshotV2.model_validate(data)
    assert parsed.targets.ALT.instruction_id == "B"
    assert parsed.targets.HDG.instruction_id == "A"
    assert parsed.readback_required.fields == ["ALT"]
    data["readback_required"]["fields"] = ["ALT", "HDG"]
    with pytest.raises(ValidationError):
        TargetSnapshotV2.model_validate(data)


@pytest.mark.parametrize("path,value", [
    ("role_basis", "ATC_PLAYBACK"),
    ("complete", True),
    ("interruption_reason", None),
    ("ended_at", "2026-10-17T01:00:00Z"),
    ("ended_at", "2026-10-17T01:00:01Z"),
    ("audio_unavailable_reason", None),
])
def test_incomplete_recording_and_control_basis_are_explicit(path, value):
    with pytest.raises(ValidationError):
        SpeechSegmentV2.model_validate(changed(fixture("speech-incomplete.json"), path, value))


def test_receipt_is_not_a_verdict_and_errors_do_not_carry_fake_values():
    payload = fixture("receipt.json")
    assert IngestionReceiptV2.model_validate(payload).disposition == "ACCEPTED"
    payload["result"] = "VERIFIED"
    with pytest.raises(ValidationError):
        IngestionReceiptV2.model_validate(payload)
    error = fixture("error-conflict.json")
    ContractErrorV2.model_validate(error)
    error["actual"] = 0
    with pytest.raises(ValidationError):
        ContractErrorV2.model_validate(error)


def test_v1_and_v2_are_not_silently_coerced_into_each_other():
    v1 = {"altitude": 3000, "heading": 270, "confidence": 0.9}
    ObservationInput.model_validate(v1)
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(v1)
    for name in ("cockpit-readable.json", "cockpit-unreadable.json", "atc-partial.json"):
        with pytest.raises(ValidationError):
            ObservationInput.model_validate(fixture(name))
    with pytest.raises(ValidationError):
        ObservationInput.model_validate({**v1, "altitude": None})
    with pytest.raises(ValidationError):
        ObservationInput.model_validate({"heading": 270})


def test_existing_vision_local_outputs_require_an_explicit_adapter():
    for name in ("vision-readable.json", "vision-unreadable.json", "mcp-observation.json"):
        local = json.loads((ROOT / "contracts" / "examples" / name).read_text())
        with pytest.raises(ValidationError):
            ObservationV2.model_validate(local)


def test_v2_receiving_keeps_the_running_legacy_input_contract(client):
    schema = client.get("/openapi.json").json()
    assert "/api/flights/start" in schema["paths"]
    assert "/api/v2/flights/{flight_id}/observations" in schema["paths"]
    fields = schema["components"]["schemas"]["ObservationInput"]
    assert set(fields["required"]) == {"altitude", "heading", "confidence"}
    assert fields["additionalProperties"] is False


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_readback_callsign_requirement_is_strictly_true(value):
    payload = fixture("targets-partial.json")
    payload["readback_required"]["callsign_required"] = value
    with pytest.raises(ValidationError):
        TargetSnapshotV2.model_validate(payload)


@pytest.mark.parametrize("source", ["ATC", "READBACK"])
@pytest.mark.parametrize("check", ["PASS", "INVALID", "NEEDS_REVIEW"])
def test_unknown_mention_scope_requires_review_in_dto_and_schema(source, check):
    payload = fixture("atc-ambiguous.json")
    payload.update(source=source, instruction_check=check)
    if source == "READBACK":
        payload["instruction_id"] = "B"
    schema = json.loads((ROOT / "contracts/schemas/observation-v2.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert validator.is_valid(payload) == (check == "NEEDS_REVIEW")
    if check == "NEEDS_REVIEW":
        ObservationV2.model_validate(payload)
    else:
        with pytest.raises(ValidationError, match="UNKNOWN mention scope"):
            ObservationV2.model_validate(payload)
