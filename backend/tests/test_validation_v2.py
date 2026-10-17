"""SPEC-005-WI-02: exact time boundaries, field provenance and no false normal."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.services.validation_v2 import evaluate, stamp

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)
POLICY = dict(max_age_seconds=60, max_future_skew_seconds=0.1)


def target(value, iid="A"):
    return dict(value=value, instruction_id=iid)


def reading(value, iid="A", obs="obs", observed=None):
    return dict(value=value, instruction_id=iid, observation_id=obs,
        observed_at=observed or stamp(NOW), structure_eligible=True, reason=None)


def state():
    return dict(targets={"ALT": target(3000), "HDG": target(270)},
        latest_atc_input_id="input-A",
        readback_required=dict(instruction_id="A", atc_input_id="input-A", fields=["ALT", "HDG"]),
        current=dict(READBACK={"ALT": reading(3000), "HDG": reading(270)},
            COCKPIT={"ALT": reading(2000), "HDG": reading(90)}),
        readbacks={"A": reading("RADAR123")})


def run(s, seconds=0, persist=True):
    return evaluate(s, POLICY, "RADAR123", NOW+timedelta(seconds=seconds), persist=persist)


def setting(report, name):
    return next(field for field in report.setting.fields if field.field == name)


@pytest.mark.parametrize("seconds,expected", [(0, "UNVERIFIED"), (4.999, "UNVERIFIED"),
    (5, "MISMATCH"), (5.001, "MISMATCH")])
def test_initial_wait_has_exact_five_second_boundary(seconds, expected):
    s = state(); run(s)
    report = run(s, seconds)
    assert report.result == expected
    assert setting(report, "ALT").wait_until == stamp(NOW+timedelta(seconds=5))
    assert bool(report.advisory_candidates) == (expected == "MISMATCH")


def test_two_second_full_match_completes_early_and_later_deviation_has_no_wait():
    s = state(); run(s)
    s["current"]["COCKPIT"].update(ALT=reading(3000), HDG=reading(270))
    assert run(s, 2).result == "NORMAL"
    s["current"]["COCKPIT"]["HDG"] = reading(90, obs="new-frame")
    report = run(s, 2.1)
    assert report.result == "MISMATCH"
    assert setting(report, "HDG").reason == "SETTING_DEVIATED_AFTER_MATCH"


def test_one_matching_field_does_not_complete_initial_group_or_latch_early():
    s = state(); run(s)
    s["current"]["COCKPIT"]["ALT"] = reading(3000)
    assert run(s, 2).result == "UNVERIFIED"
    assert s["validation_memory"]["setting_matched"] == {}
    s["current"]["COCKPIT"]["ALT"] = reading(2000)
    assert setting(run(s, 3), "ALT").reason == "INITIAL_ADJUSTMENT_WAIT"


def test_readback_mismatch_wins_and_preserves_other_unverified_fields():
    s = state()
    s["current"]["READBACK"]["ALT"] = reading(4000)
    s["current"]["READBACK"]["HDG"] = None
    s["current"]["COCKPIT"]["HDG"] = None
    report = run(s)
    assert report.result == "MISMATCH"
    assert report.representative_stage == "READBACK"
    assert any(field.result == "UNVERIFIED" for field in report.readback.fields)
    assert [(field.stage, field.field) for field in report.advisory_candidates] == [("READBACK", "ALT")]


@pytest.mark.parametrize("change", ["null", "stale", "future", "quality", "wrong_context", "legacy_context"])
def test_unavailable_setting_is_never_numeric_mismatch_or_normal(change):
    s = state(); run(s)
    item = s["current"]["COCKPIT"]["ALT"]
    if change in ("null", "quality"):
        item.update(value=None, reason="blank_roi" if change == "null" else "INPUT_QUALITY_UNVERIFIED")
    elif change == "stale":
        item["observed_at"] = stamp(NOW-timedelta(seconds=61))
    elif change == "future":
        item["observed_at"] = stamp(NOW+timedelta(seconds=20))
    elif change == "wrong_context":
        item["instruction_id"] = "other"
    else:
        item.pop("instruction_id")
    report = run(s, 5)
    assert setting(report, "ALT").result == "UNVERIFIED"
    assert all(field.field != "ALT" for field in report.advisory_candidates)


def test_missing_rule_proof_and_callsign_block_normal():
    s = state()
    s["current"]["READBACK"]["ALT"].pop("structure_eligible")
    s["readbacks"] = {}
    report = run(s, 5)
    assert report.result == "UNVERIFIED"
    assert s["validation_memory"]["readback_confirmed_at"] == {}


def test_explicit_callsign_difference_is_distinct_from_unreadable_callsign():
    s = state(); s["readbacks"]["A"]["value"] = "OTHER123"
    report = run(s)
    assert report.result == "MISMATCH"
    assert report.advisory_candidates[0].field == "CALLSIGN"
    s["readbacks"]["A"]["value"] = None
    assert run(s).result == "UNVERIFIED"


def test_duplicate_readback_does_not_restart_timer():
    s = state(); run(s)
    first = deepcopy(s["validation_memory"]["readback_confirmed_at"])
    run(s, 4)
    assert s["validation_memory"]["readback_confirmed_at"] == first
    assert run(s, 5).result == "MISMATCH"


def test_pending_new_atc_suppresses_old_guidance_without_losing_old_error():
    s = state(); run(s)
    assert run(s, 5).result == "MISMATCH"
    s["latest_atc_input_id"] = "input-B"
    report = run(s, 6)
    assert report.result == "UNVERIFIED" and report.phase == "WAITING_ATC"
    assert report.setting.result == "MISMATCH"
    assert report.advisory_candidates == []


def test_new_altitude_wait_does_not_hide_existing_heading_deviation():
    s = state()
    s["current"]["COCKPIT"].update(ALT=reading(3000), HDG=reading(270))
    assert run(s).result == "NORMAL"
    s["targets"]["ALT"] = target(4000, "B")
    s["latest_atc_input_id"] = "input-B"
    s["readback_required"] = dict(instruction_id="B", atc_input_id="input-B", fields=["ALT"])
    s["current"]["READBACK"]["ALT"] = None
    s["current"]["COCKPIT"].update(ALT=reading(3000, "B"), HDG=reading(90))
    waiting = run(s, 1)
    assert waiting.advisory_candidates == [] and waiting.phase == "READBACK"
    assert setting(waiting, "HDG").result == "MISMATCH"
    s["current"]["READBACK"]["ALT"] = reading(4000, "B")
    s["readbacks"]["B"] = reading("RADAR123", "B")
    report = run(s, 2)
    assert setting(report, "ALT").reason == "INITIAL_ADJUSTMENT_WAIT"
    assert setting(report, "HDG").result == "MISMATCH"
    assert report.result == "MISMATCH"
    assert [field.field for field in report.advisory_candidates] == ["HDG"]
    assert s["validation_memory"]["readback_confirmed_at"] == {"A": stamp(NOW), "B": stamp(NOW+timedelta(seconds=2))}


def test_query_is_read_only_and_ended_flight_cannot_be_normal():
    s = state(); run(s)
    before = deepcopy(s)
    report = run(s, 5, persist=False)
    assert s == before and report.result == "MISMATCH"
    report = evaluate(s, POLICY, "RADAR123", NOW, ended=True)
    assert report.result == "UNVERIFIED" and report.phase == "ENDED"
    assert report.advisory_candidates == []


def test_expired_camera_keeps_readback_history_but_withholds_current_normal():
    s = state(); run(s)
    report = run(s, 61)
    assert report.result == "UNVERIFIED"
    assert report.readback.result == "NORMAL"
    assert s["validation_memory"]["readback_confirmed_at"]["A"] == stamp(NOW)


def test_partial_first_instruction_does_not_require_readback_of_unknown_heading():
    s = state()
    s["targets"]["HDG"] = None
    report = run(s)
    assert report.readback.result == "NORMAL"
    assert [field.field for field in report.readback.fields] == ["ALT", "CALLSIGN"]
    assert report.result == "UNVERIFIED"  # Still no heading setting target.


def test_validation_schema_matches_runtime_model():
    import json
    from pathlib import Path
    from app.schemas.validation_v2 import ValidationSnapshot
    schema = ValidationSnapshot.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:radar:contracts:validation-snapshot-v1"
    actual = json.loads((Path(__file__).resolve().parents[2] / "contracts/schemas/validation-snapshot-v1.schema.json").read_text())
    assert schema == actual


def test_zero_heading_is_a_valid_match_and_missing_policy_is_unverified():
    s = state()
    s["targets"]["HDG"]["value"] = 0
    s["current"]["READBACK"]["HDG"]["value"] = 0
    s["current"]["COCKPIT"].update(ALT=reading(3000), HDG=reading(0))
    assert run(s).result == "NORMAL"
    assert evaluate(s, None, "RADAR123", NOW).result == "UNVERIFIED"
