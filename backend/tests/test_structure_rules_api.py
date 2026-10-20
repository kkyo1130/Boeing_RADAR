"""Actual intake application, persistence, frozen configuration and rollback."""
from copy import deepcopy
import json

from test_receiving_v2 import Scenario, setup, scenario  # shared v2 context fixtures


def test_extractor_pass_does_not_override_independent_raw_value_conflict(scenario):
    s = scenario
    data = s.speech(s.segment())
    data["fields"]["ALT"].update(value=4000, raw_text="4000")
    before = deepcopy(data)
    receipt = s.send(data)
    assert receipt.status_code == 201
    assert s.inputs()[0]["reason"] == "STRUCTURE_INVALID"
    assert s.inputs()[0]["payload"] == before
    assert s.state()["targets"] == {"ALT": None, "HDG": None}
    check = s.state()["structure_checks"]["ATC"]
    assert check["observation_id"] == data["observation_id"]
    assert check["derived_values"]["ALT"] == 3000
    assert check["result"] == "INVALID"
    assert s.trace()[-1]["snapshot"]["structure_check"] == check
    assert s.state()["result"] == "UNVERIFIED"


def test_supported_flight_level_is_checked_against_feet_without_rewriting_payload(scenario):
    s = scenario
    data = s.speech(s.segment(), partial=True)
    data["transcript"] = "Radar one two three maintain FL040"
    data["fields"]["ALT"]["raw_text"] = "FL040"
    assert s.send(data).status_code == 201
    assert s.state()["targets"]["ALT"]["value"] == 4000
    assert s.state()["structure_checks"]["ATC"]["derived_values"] == {"ALT": 4000}
    assert s.inputs()[0]["payload"] == data


def test_unsupported_condition_is_withheld_even_if_extractor_says_pass(scenario):
    s = scenario
    data = s.speech(s.segment())
    data["transcript"] = "Radar one two three after departure maintain three thousand feet heading two seven zero"
    assert s.send(data).status_code == 201
    assert s.inputs()[0]["reason"] == "STRUCTURE_NEEDS_REVIEW"
    assert s.state()["targets"]["ALT"] is None


def test_missing_rule_policy_uses_review_instead_of_invented_limits(setup):
    client, clock, config, path = setup
    config.pop("structure_rules")
    path.write_text(json.dumps(config))
    s = Scenario(client, clock)
    data = s.speech(s.segment())
    assert s.send(data).status_code == 201
    assert s.state()["structure_checks"]["ATC"]["result"] == "NEEDS_REVIEW"
    assert s.state()["targets"]["ALT"] is None


def test_rule_policy_is_frozen_for_each_flight(scenario, setup):
    s = scenario
    config, path = setup[2:]
    config["structure_rules"].update(max_altitude_ft=1, policy_ref="changed-config")
    path.write_text(json.dumps(config))
    s.adopt()
    assert s.state()["structure_checks"]["ATC"]["policy_ref"] == "synthetic-contract-tests/1"
    other = Scenario(setup[0], setup[1])
    assert other.send(other.speech(other.segment())).status_code == 201
    assert other.state()["structure_checks"]["ATC"]["result"] == "INVALID"


def test_structurally_valid_output_does_not_promote_extractor_invalid(scenario):
    s = scenario
    data = s.speech(s.segment())
    data["instruction_check"] = "INVALID"
    assert s.send(data).status_code == 201
    assert s.state()["structure_checks"]["ATC"]["result"] == "PASS"
    assert s.inputs()[0]["reason"] == "EXTRACTION_UNVERIFIED"
    assert s.state()["targets"]["ALT"] is None


def test_readback_structure_conflict_clears_only_current_readback_fields(scenario):
    s = scenario
    atc = s.adopt(); s.tick()
    pilot = s.segment(atc)
    data = s.speech(pilot)
    data["fields"]["HDG"].update(value=90, raw_text="90")
    assert s.send(data).status_code == 201
    assert s.state()["current"]["READBACK"]["HDG"]["value"] is None
    assert s.state()["current"]["READBACK"]["HDG"]["reason"] == "STRUCTURE_INVALID"
    assert s.state()["targets"]["HDG"]["value"] == 270


def test_deferred_pilot_recheck_records_its_own_structure_evidence(scenario):
    s = scenario
    atc = s.segment(); s.tick()
    pilot = s.segment(atc)
    data = s.speech(pilot)
    s.send(data)
    assert s.inputs()[0]["reason"] == "ATC_NOT_ADOPTED"
    s.tick(); s.send(s.speech(atc))
    event = next(event for event in s.trace() if event["event_type"] == "DEFERRED_READBACK_RECHECKED")
    assert event["snapshot"]["structure_check"]["observation_id"] == data["observation_id"]
    assert event["snapshot"]["structure_check"]["result"] == "PASS"


def test_reused_sample_cannot_inherit_another_observations_report(scenario):
    s = scenario
    data = s.speech(s.adopt())
    # adopt() has already consumed this segment under a different observation ID.
    assert s.send(data).status_code == 201
    assert s.inputs()[0]["reason"] == "SOURCE_SAMPLE_REUSED"
    assert s.trace()[-1]["snapshot"]["structure_check"] is None


def test_extra_command_in_altitude_raw_text_is_not_adopted(scenario):
    s = scenario
    data = s.speech(s.segment(), partial=True)
    data["fields"]["ALT"]["raw_text"] = "FL040 heading 090"
    assert s.send(data).status_code == 201
    assert s.state()["structure_checks"]["ATC"]["result"] == "INVALID"
    assert s.state()["targets"]["ALT"] is None
    assert s.inputs()[0]["payload"] == data
