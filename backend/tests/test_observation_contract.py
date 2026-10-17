import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.observation import ObservationInput
from app.schemas.observation_contract import ObservationContract


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "contracts/examples/observation-v1"


def example(name="normal"):
    return json.loads((EXAMPLES / f"{name}.json").read_text())


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda p: p.stem)
def test_examples_round_trip(path):
    data = json.loads(path.read_text())
    model = ObservationContract.model_validate(data)
    assert ObservationContract.model_validate_json(model.model_dump_json()) == model


@pytest.mark.parametrize("path,value", [
    (("fields", "heading", "value"), 360),
    (("fields", "heading", "value"), True),
    (("fields", "altitude", "value"), "3000"),
    (("fields", "altitude", "value"), -1),
    (("fields", "altitude", "value"), None),
    (("fields", "altitude", "reason"), "unreadable"),
    (("fields", "altitude", "model_score"), float("nan")),
    (("fields", "altitude", "model_score"), 1.1),
    (("fields", "altitude", "score_calibrated"), True),
    (("fields", "altitude", "score_calibrated"), 0),
    (("fields", "altitude", "evidence_ids"), ["other-observation"]),
    (("fields", "altitude", "quality", "reasons"), ["occluded"]),
    (("captured_at",), "2026-10-13T00:00:00"),
    (("captured_at",), "2026-10-13T09:00:00+09:00"),
    (("captured_at",), "2026-10-13T00:00:02Z"),
    (("captured_at",), None),
    (("processed_at",), 123),
    (("clearance_id",), None),
    (("schema_version",), "radar-observation/2"),
    (("event_type",), "health"),
    (("intent",), "correction"),
    (("supersedes_observation_id",), "obs-0"),
    (("health",), {"status": "unavailable", "reason": "disconnected"}),
    (("evidence",), []),
    (("evidence", 0, "roi"), [10, 10, 5, 20]),
    (("fields", "speed"), {}),
])
def test_reject_unsafe_or_malformed_payload(path, value):
    data = example()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        ObservationContract.model_validate(data)


def test_missing_field_different_from_unreadable_and_zero():
    partial = ObservationContract.model_validate(example("partial-atc"))
    assert partial.fields.altitude is None
    assert partial.fields.heading.value == 0
    unreadable = ObservationContract.model_validate(example("unreadable"))
    assert unreadable.fields.altitude.value is None
    assert unreadable.fields.altitude.reason == "blank_roi"
    data = example()
    del data["fields"]["altitude"]
    with pytest.raises(ValidationError):
        ObservationContract.model_validate(data)


def test_duplicate_evidence_and_self_correction_rejected():
    data = example()
    data["evidence"].append(deepcopy(data["evidence"][0]))
    with pytest.raises(ValidationError):
        ObservationContract.model_validate(data)
    data = example("correction")
    data["supersedes_observation_id"] = data["observation_id"]
    with pytest.raises(ValidationError):
        ObservationContract.model_validate(data)


def test_absent_requested_fields_and_invalid_speech_rejected():
    data = example()
    data["fields"] = {"altitude": None, "heading": None}
    with pytest.raises(ValidationError):
        ObservationContract.model_validate(data)
    for updates in ({"callsign": None}, {"callsign": ""}):
        data = example("partial-atc")
        data["speech"].update(updates)
        with pytest.raises(ValidationError):
            ObservationContract.model_validate(data)


def test_legacy_api_remains_separate():
    old = {"altitude": 3000, "heading": 270, "confidence": 0.9}
    assert ObservationInput.model_validate(old).altitude == 3000
    for data in [example(), {**old, "altitude": None}, {"heading": 270, "confidence": 0.9}]:
        with pytest.raises(ValidationError):
            ObservationInput.model_validate(data)


def test_published_schema_matches_model():
    stored = json.loads((ROOT / "contracts/schemas/observation-v1.schema.json").read_text())
    assert stored == ObservationContract.model_json_schema()
