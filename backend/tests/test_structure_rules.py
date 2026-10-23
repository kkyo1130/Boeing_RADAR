"""SPEC-005-WI-01 grammar, context and configured boundaries; synthetic inputs."""
from copy import deepcopy
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from app.schemas.structure_rules import StructurePolicy
from app.services.structure_rules import check_structure

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "contracts/examples/structure-rules/cases.json").read_text())
POLICY = dict(policy_ref="synthetic-contract-tests/1", max_altitude_ft=50000,
    max_altitude_change_ft=10000, max_heading_change_deg=180)


def sample(transcript=None, fields=None):
    data = json.loads((ROOT / "contracts/examples/v2/atc-full.json").read_text())
    segment = json.loads((ROOT / "contracts/examples/v2/speech-complete.json").read_text())
    data["processed_at"] = segment["ended_at"]
    if transcript is not None:
        data["transcript"] = transcript
    if fields is not None:
        prototype = deepcopy(data["fields"]["ALT"])
        data["fields"] = {name: {**deepcopy(prototype), "value": value,
            "unit": "ft" if name == "ALT" else "deg", "raw_text": str(value)} for name, value in fields.items()}
        data["mentioned_fields"] = list(fields)
    return data, dict(target_callsign="RADAR123", registry={"RADAR123": {
        "radar-one-two-three": "Radar one two three"}}, segment=segment,
        instruction_id="instruction-A", previous_targets={"ALT": None, "HDG": None},
        policy=StructurePolicy(**POLICY))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_declared_grammar_fixtures(case):
    data, context = sample(case["transcript"], case["fields"])
    before = deepcopy(data), deepcopy(context)
    report = check_structure(data, **context)
    assert report.result == case["result"]
    assert report.observation_id == data["observation_id"]
    if case["reason"]:
        assert case["reason"] in {check.reason for check in report.checks}
    assert (data, context) == before
    assert check_structure(data, **context) == report


@pytest.mark.parametrize("value", [True, 3.0, "3000", -1])
def test_normalized_numbers_are_not_coerced(value):
    data, context = sample()
    data["fields"]["ALT"]["value"] = value
    report = check_structure(data, **context)
    assert report.result == "INVALID"
    assert "VALUE_OUT_OF_RANGE" in {c.reason for c in report.checks}


@pytest.mark.parametrize("unit", ["FL", "m", "feet"])
def test_wire_altitude_must_already_be_normalized_feet(unit):
    data, context = sample()
    data["fields"]["ALT"]["unit"] = unit
    assert check_structure(data, **context).result == "INVALID"


@pytest.mark.parametrize("field", ["ALT", "HDG"])
def test_unreadable_fields_stay_needs_review(field):
    data, context = sample()
    data["fields"][field].update(value=None, validity="UNREADABLE", reason="no_text")
    assert check_structure(data, **context).result == "NEEDS_REVIEW"


@pytest.mark.parametrize("key", ["flight_id", "segment_id", "atc_input_id", "attempt_id"])
def test_context_ids_are_not_reassigned(key):
    data, context = sample()
    data[key] = "other"
    assert check_structure(data, **context).result == "INVALID"


def test_registered_role_and_readback_instruction_must_match():
    data, context = sample()
    data.update(source="READBACK", instruction_id="other-instruction")
    assert check_structure(data, **context).result == "INVALID"
    data["instruction_id"] = context["instruction_id"]
    assert check_structure(data, **context).result == "INVALID"  # ATC role is still wrong
    context["segment"]["role"] = "PILOT"
    assert check_structure(data, **context).result == "PASS"


@pytest.mark.parametrize("change", ["missing_time", "incomplete", "missing_transcript", "unknown_scope"])
def test_missing_information_cannot_pass(change):
    data, context = sample()
    if change == "missing_time":
        data["observed_at"] = None
    elif change == "incomplete":
        context["segment"]["complete"] = False
    elif change == "missing_transcript":
        data["transcript"] = None
    else:
        data["mention_status"] = "UNKNOWN"
    assert check_structure(data, **context).result == "NEEDS_REVIEW"


@pytest.mark.parametrize("change", ["before_end", "different_capture"])
def test_capture_processing_order_is_checked(change):
    data, context = sample()
    if change == "before_end":
        data["processed_at"] = data["observed_at"]
    else:
        data["observed_at"] = context["segment"]["ended_at"]
    report = check_structure(data, **context)
    assert report.result == "INVALID"
    assert "CAPTURE_PROCESSING_ORDER_CONFLICT" in {c.reason for c in report.checks}


@pytest.mark.parametrize("change,expected", [("alias", "INVALID"), ("raw", "INVALID"),
    ("canonical", "INVALID"), ("prefix", "NEEDS_REVIEW"), ("target", "NEEDS_REVIEW")])
def test_callsign_uses_registered_alias_and_whole_transcript_prefix(change, expected):
    data, context = sample()
    if change == "alias":
        data["callsign"]["alias_key"] = "guessed-alias"
    elif change == "raw":
        data["callsign"]["raw_text"] = "guessed raw"
    elif change == "canonical":
        data["callsign"]["value"] = "OTHER"
    elif change == "prefix":
        data["transcript"] = "Unregistered plane maintain three thousand feet"
    else:
        context["target_callsign"] = "OTHER"
    assert check_structure(data, **context).result == expected


@pytest.mark.parametrize("key", ["max_altitude_ft", "max_altitude_change_ft", "max_heading_change_deg"])
def test_missing_required_policy_limit_is_reviewed(key):
    data, context = sample()
    context["policy"] = StructurePolicy(**{**POLICY, key: None})
    assert check_structure(data, **context).result == "NEEDS_REVIEW"


def test_entire_missing_policy_is_not_silently_defaulted():
    data, context = sample()
    context["policy"] = None
    report = check_structure(data, **context)
    assert report.result == "NEEDS_REVIEW" and report.policy_ref is None


@pytest.mark.parametrize("delta,expected", [(10000, "PASS"), (10001, "NEEDS_REVIEW")])
def test_altitude_jump_exact_boundary(delta, expected):
    data, context = sample(f"Radar one two three maintain {3000+delta} feet", {"ALT": 3000+delta})
    context["previous_targets"]["ALT"] = {"value": 3000}
    assert check_structure(data, **context).result == expected


@pytest.mark.parametrize("heading,expected", [(1, "PASS"), (2, "NEEDS_REVIEW"), (359, "PASS")])
def test_heading_change_uses_shortest_circular_distance(heading, expected):
    data, context = sample(f"Radar one two three heading {heading}", {"HDG": heading})
    context["policy"] = StructurePolicy(**{**POLICY, "max_heading_change_deg": 2})
    context["previous_targets"]["HDG"] = {"value": 359}
    assert check_structure(data, **context).result == expected


@pytest.mark.parametrize("key,value", [("max_altitude_ft", True), ("max_altitude_ft", 50000.0),
    ("max_altitude_change_ft", -1), ("max_heading_change_deg", 181), ("policy_ref", "")])
def test_policy_configuration_is_strict(key, value):
    with pytest.raises(ValidationError):
        StructurePolicy(**{**POLICY, key: value})


def test_readback_difference_from_atc_is_not_a_structure_failure():
    data, context = sample("Radar one two three maintain four thousand feet", {"ALT": 4000})
    data.update(source="READBACK", instruction_id="instruction-A")
    context["segment"]["role"] = "PILOT"
    context["previous_targets"]["ALT"] = {"value": 3000}
    context["policy"] = StructurePolicy(**{**POLICY, "max_altitude_change_ft": 1})
    assert check_structure(data, **context).result == "PASS"


def test_mention_field_metadata_cannot_hide_duplicates():
    data, context = sample()
    data["mentioned_fields"] = ["ALT", "ALT", "HDG"]
    assert check_structure(data, **context).result == "INVALID"


@pytest.mark.parametrize("raw,expected", [("FL030", "PASS"), ("FL040", "INVALID"),
    ("FL30", "INVALID"), (None, "NEEDS_REVIEW")])
def test_explicit_raw_flight_level_and_missing_raw_text_are_checked(raw, expected):
    data, context = sample()
    data["fields"]["ALT"]["raw_text"] = raw
    assert check_structure(data, **context).result == expected


def test_published_rule_schemas_match_runtime_models():
    from app.schemas.structure_rules import StructureResult
    for name, model in (("structure-policy-v1", StructurePolicy), ("structure-result-v1", StructureResult)):
        expected = model.model_json_schema(mode="validation")
        expected["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        expected["$id"] = "urn:radar:contracts:" + name
        actual = json.loads((ROOT / "contracts/schemas" / f"{name}.schema.json").read_text())
        assert actual == expected


@pytest.mark.parametrize("source", ["transcript", "raw_field"])
def test_excessively_long_numeric_text_is_reviewed_without_integer_conversion_failure(source):
    data, context = sample()
    if source == "transcript":
        data["transcript"] = "Radar one two three maintain " + "9"*5000 + " feet"
    else:
        data["fields"]["ALT"]["raw_text"] = "9"*5000
    assert check_structure(data, **context).result == "NEEDS_REVIEW"


@pytest.mark.parametrize("raw", ["FL040 heading 090", "4000 feet heading zero nine zero"])
def test_altitude_raw_field_cannot_hide_an_extra_heading_command(raw):
    data, context = sample("Radar one two three maintain FL040", {"ALT": 4000})
    data["fields"]["ALT"]["raw_text"] = raw
    result = check_structure(data, **context)
    assert result.result == "INVALID"
    assert "RAW_FIELD_SET_CONFLICT" in {check.reason for check in result.checks}

@pytest.mark.parametrize('command,expected', [
    ('heading to seven zero', {'HDG':270}),
    ('heading too seven zero', {'HDG':270}),
    ('heading two ate zero', {'HDG':280}),
    ('heading to for fore', {'HDG':244}),
    ('heading 2 seven 0', {'HDG':270}),
    ('heading o tree fife', {'HDG':35}),
    ('maintain tree thousand feet heading to seven zero', {'ALT':3000,'HDG':270}),
    ('maintain flight level to for zero', {'ALT':24000}),
])
def test_contextual_number_homophones(command,expected):
    from app.services.structure_rules import parse_command
    assert parse_command(command)==(expected, [])

@pytest.mark.parametrize('command', [
    'heading for clearance', 'heading to seven zero if able',
    'heading ate zero zero', 'maintain 3 sound feet',
    'turn to heading two seven zero', 'maintain tree thousand',
])
def test_homophones_do_not_guess_unknown_or_out_of_range_commands(command):
    from app.services.structure_rules import parse_command
    assert parse_command(command)[1]
