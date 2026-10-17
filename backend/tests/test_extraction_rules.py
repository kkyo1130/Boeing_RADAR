from copy import deepcopy
from pathlib import Path
import json

import pytest
from pydantic import ValidationError
from app.services.validation.rules import check_observation, RulePolicy

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / "contracts/rule-policy-demo.json").read_text())


def observation(name="normal"):
    return json.loads((ROOT / f"contracts/examples/observation-v1/{name}.json").read_text())


def codes(result):
    return {issue.code for issue in result.issues}


@pytest.mark.parametrize("value,raw,status,code", [
    (18000, "FL180", "PASS", None), (18000, "fl 180", "PASS", None),
    (60000, "FL600", "PASS", None), (60100, "FL601", "INVALID", "altitude_above_policy"),
    (18000, "FL18", "INVALID", "invalid_fl_format"),
    (18000, "FL\n180", "INVALID", "invalid_fl_format"),
    (180, "FL180", "INVALID", "raw_value_conflict"),
    (3000, "three thousand", "NEEDS_REVIEW", "unsupported_raw_format"),
    (3000, None, "NEEDS_REVIEW", "raw_text_missing"),
    (60001, None, "INVALID", "altitude_above_policy"),
])
def test_altitude_and_fl(value, raw, status, code):
    data = observation()
    data["fields"]["altitude"].update(value=value, raw_text=raw)
    result = check_observation(data, policy=POLICY)
    assert result.status == status
    assert code is None or code in codes(result)


@pytest.mark.parametrize("value,raw,status,code", [
    (0, "000", "PASS", None), (359, "359", "PASS", None),
    (360, "360", "INVALID", "contract_violation"),
    (0, "360", "INVALID", "heading_out_of_range"),
    (270, "O70", "NEEDS_REVIEW", "unsupported_raw_format"),
    (270, "280", "INVALID", "raw_value_conflict"),
])
def test_heading(value, raw, status, code):
    data = observation()
    data["fields"]["heading"].update(value=value, raw_text=raw)
    result = check_observation(data, policy=POLICY)
    assert result.status == status
    assert code is None or code in codes(result)


def context():
    return dict(expected_callsign="RADAR1", expected_conditions=[], expected_ordered_actions=["heading 000"])


def test_partial_instruction_and_confirmed_context():
    data = observation("partial-atc")
    before = deepcopy(data)
    assert check_observation(data, policy=POLICY, context=context()).status == "PASS"
    assert data == before


@pytest.mark.parametrize("case,expected_code", [
    ("callsign", "callsign_conflict"), ("conditions", "conditions_conflict"),
    ("order", "ordered_actions_conflict")])
def test_confirmed_context_conflicts(case, expected_code):
    data = observation("partial-atc")
    confirmed = context()
    if case == "callsign":
        data["speech"]["callsign"] = "RADAR2"
    elif case == "conditions":
        confirmed["expected_conditions"] = ["after passing ABC"]
    else:
        confirmed["expected_ordered_actions"] = ["altitude 3000", "heading 000"]
        data["speech"]["ordered_actions"] = ["heading 000", "altitude 3000"]
    result = check_observation(data, policy=POLICY, context=confirmed)
    assert result.status == "INVALID" and expected_code in codes(result)


def test_missing_policy_context_callsign_and_role_are_not_pass():
    data = observation("partial-atc")
    assert check_observation(data).status == "NEEDS_REVIEW"
    assert {"policy_missing", "callsign_context_missing", "instruction_context_missing"}.issubset(codes(check_observation(data)))
    data["speech"].update(callsign=None, callsign_reason="callsign_missing", role_basis=None)
    result = check_observation(data, policy=POLICY, context=context())
    assert {"callsign_missing", "speech_context_incomplete"}.issubset(codes(result))


def test_missing_or_uncertain_inputs_are_not_numeric_mismatch():
    for name, code in [("unreadable", "blank_roi"), ("unknown-time", "capture_time_unknown"),
                       ("health", "health_without_observation")]:
        result = check_observation(observation(name), policy=POLICY)
        assert result.status == "NEEDS_REVIEW" and code in codes(result)


def changed(old):
    new = deepcopy(old)
    new.update(observation_id="new-obs", sample_id="new-frame",
               captured_at="2026-10-13T00:00:01Z", processed_at="2026-10-13T00:00:02Z")
    return new


@pytest.mark.parametrize("start,end,altitude,status", [
    (359, 0, 3000, "PASS"), (0, 90, 9000, "PASS"),
    (0, 91, 3000, "NEEDS_REVIEW"), (270, 270, 9001, "NEEDS_REVIEW")])
def test_rapid_change_and_circular_heading(start, end, altitude, status):
    old = observation()
    old["fields"]["heading"].update(value=start, raw_text=str(start))
    new = changed(old)
    new["fields"]["heading"].update(value=end, raw_text=str(end))
    new["fields"]["altitude"].update(value=altitude, raw_text=str(altitude))
    result = check_observation(new, previous=old, policy=POLICY)
    assert result.status == status
    if status == "NEEDS_REVIEW":
        assert "rapid_change" in codes(result)


def test_previous_identity_time_and_window():
    old = observation()
    assert "non_new_observation" in codes(check_observation(old, previous=old, policy=POLICY))
    new = changed(old)
    new["clearance_id"] = "another-clearance"
    assert "unrelated_previous_observation" in codes(check_observation(new, previous=old, policy=POLICY))
    new = changed(old)
    new.update(captured_at="2026-10-13T00:00:11Z", processed_at="2026-10-13T00:00:12Z")
    new["fields"]["heading"].update(value=90, raw_text="90")
    assert check_observation(new, previous=old, policy=POLICY).status == "PASS"


@pytest.mark.parametrize("key,value", [("max_altitude_feet", True), ("max_altitude_feet", 0),
                                       ("max_heading_change_degrees", 181),
                                       ("change_window_seconds", float("nan"))])
def test_bad_policy_rejected(key, value):
    with pytest.raises(ValidationError):
        RulePolicy.model_validate({**POLICY, key: value})
