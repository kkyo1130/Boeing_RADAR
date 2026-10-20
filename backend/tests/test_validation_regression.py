"""SPEC-005-WI-03: declarative outcomes and public API no-false-normal cases."""
from itertools import product

import pytest

from app.schemas.validation_v2 import ValidationSnapshot
from test_validation_v2 import state, reading, run
from test_validation_v2_api import match_readback, cockpit
from test_receiving_v2 import setup, scenario

MODES = ("NORMAL", "MISMATCH", "UNVERIFIED")
MATRIX = list(product(MODES, repeat=4))


def expected_result(rb_alt, rb_hdg, cp_alt, cp_hdg):
    # Test oracle from the acceptance table, independent of service aggregation.
    if "MISMATCH" in (rb_alt, rb_hdg):
        return "MISMATCH", "READBACK"
    if "UNVERIFIED" in (rb_alt, rb_hdg):
        return "UNVERIFIED", None
    if "MISMATCH" in (cp_alt, cp_hdg):
        return "MISMATCH", "SETTING"
    if "UNVERIFIED" in (cp_alt, cp_hdg):
        return "UNVERIFIED", None
    return "NORMAL", None


@pytest.mark.parametrize("modes", MATRIX, ids=lambda modes: "-".join(modes))
def test_all_81_mixed_field_outcomes_against_acceptance_table(modes):
    s = state()
    for (source, field), mode in zip(product(("READBACK", "COCKPIT"), ("ALT", "HDG")), modes):
        value = {"ALT": 3000, "HDG": 270}[field]
        s["current"][source][field] = reading(value if mode == "NORMAL" else value-1)
        if mode == "UNVERIFIED":
            s["current"][source][field].update(value=None, reason="fixture_unavailable")
    run(s)  # First eligible readback confirmation, if any.
    result = run(s, 6)
    expected, representative = expected_result(*modes)
    assert (result.result, result.representative_stage) == (expected, representative)
    if result.result == "NORMAL":
        assert modes == ("NORMAL",)*4
        assert all(item.result == "NORMAL" for item in result.readback.fields+result.setting.fields)
    assert all(item.result == "MISMATCH" and item.stage == representative for item in result.advisory_candidates)
    assert all(item.instruction_id == "A" for item in result.readback.fields+result.setting.fields)


@pytest.mark.parametrize("alt,hdg", list(product(MODES, repeat=2)))
def test_setting_matrix_through_intake_and_trace(scenario, alt, hdg):
    s = scenario
    atc = s.adopt(); match_readback(s, atc)
    s.tick(5)
    data = s.camera()
    for name, mode in (("ALT", alt), ("HDG", hdg)):
        field = data["fields"][name]
        value = {"ALT": 3000, "HDG": 270}[name]
        actual = value if mode == "NORMAL" else value-1
        field.update(value=actual, raw_text=str(actual))
        if mode == "UNVERIFIED":
            field.update(value=None, raw_text=None, validity="UNREADABLE", reason="fixture_unavailable")
    assert s.send(data).status_code == 201
    snapshot = s.state()["validation"]
    ValidationSnapshot.model_validate(snapshot)
    expected, representative = expected_result("NORMAL", "NORMAL", alt, hdg)
    assert (snapshot["result"], snapshot["representative_stage"]) == (expected, representative)
    assert s.trace()[-1]["snapshot"]["validation"] == snapshot
    assert s.trace()[-1]["snapshot"]["payload"] == data
    assert all(field["instruction_id"] == atc["instruction_id"] for field in snapshot["setting"]["fields"])


@pytest.mark.parametrize("fault", ["low_quality", "stale", "future", "unknown_time", "unreadable",
    "old_revision", "CAMERA", "MICROPHONE", "SPEECH_API", "new_atc", "rule_conflict", "missing_callsign"])
def test_completed_normal_cannot_hide_new_uncertainty(scenario, fault):
    s = scenario
    atc = s.adopt(); match_readback(s, atc); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    s.tick(0.5)
    if fault in ("CAMERA", "MICROPHONE", "SPEECH_API"):
        data = s.payload("camera-disconnected.json")
        data.update(channel=fault, event_id="regression-"+fault, observed_at=s.time(-0.1),
            health={"status": "DISCONNECTED", "reason": "fixture_channel_disconnected"})
        assert s.client.post(s.url+"/health-events", json=data).status_code == 201
    elif fault == "new_atc":
        s.segment()
    elif fault in ("rule_conflict", "missing_callsign"):
        data = s.speech(s.segment(atc))
        if fault == "rule_conflict":
            data["fields"]["ALT"].update(value=4000, raw_text="4000")
        else:
            data["callsign"].update(value=None, raw_text=None, alias_key=None,
                validity="UNREADABLE", reason="callsign_missing")
            data["instruction_check"] = "NEEDS_REVIEW"
        assert s.send(data).status_code == 201
    else:
        data = s.camera()
        data["fields"]["HDG"].update(value=270, raw_text="270")
        if fault == "low_quality":
            data["fields"]["ALT"]["quality"].update(input_quality="INSUFFICIENT", reason="fixture_blur")
        elif fault == "stale":
            s.tick(11)  # Expire the previously valid sample as well.
            data["observed_at"] = s.time(-11)
            data["processed_at"] = s.time(-0.1)
        elif fault == "future":
            data.update(observed_at=s.time(1), processed_at=s.time(1.1))
        elif fault == "unknown_time":
            data.update(observed_at=None, time_basis="UNKNOWN", time_reason="fixture_clock_unknown")
        elif fault == "unreadable":
            data["fields"]["ALT"].update(value=None, validity="UNREADABLE", raw_text=None, reason="fixture_blank")
        else:
            data["target_revision"] = 0
        assert s.send(data).status_code == 201
    report = s.state()["validation"]
    assert report["result"] == "UNVERIFIED"
    assert report["advisory_candidates"] == []
    assert any(field["result"] == "UNVERIFIED" for field in report["readback"]["fields"]+report["setting"]["fields"]) or fault == "new_atc"


def test_confirmed_readback_error_keeps_other_readback_quality_hold(scenario):
    s = scenario
    atc = s.adopt(); s.tick()
    data = s.speech(s.segment(atc))
    data["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    data["fields"]["ALT"].update(value=4000, raw_text="4000")
    data["fields"]["HDG"]["quality"].update(input_quality="INSUFFICIENT", reason="fixture_overlap")
    assert s.send(data).status_code == 201
    report = s.state()["validation"]
    by_name = {field["field"]: field for field in report["readback"]["fields"]}
    assert by_name["ALT"]["result"] == "MISMATCH"
    assert by_name["HDG"]["result"] == "UNVERIFIED"
    assert report["result"] == "MISMATCH" and report["representative_stage"] == "READBACK"
    assert report["setting"]["result"] == "UNVERIFIED"


def test_legacy_resolved_does_not_make_an_unobserved_v2_flight_normal(scenario):
    s = scenario
    good = dict(altitude=3000, heading=270, confidence=0.9)
    legacy = s.client.post("/api/flights/start").json()["flight_id"]
    c = s.client.post(f"/api/flights/{legacy}/clearances", json=good).json()["clearance_id"]
    assert s.client.post(f"/api/clearances/{c}/readback", json={**good, "altitude": 4000}).status_code == 200
    resolved = s.client.post(f"/api/clearances/{c}/readback/reverify", json=good)
    assert resolved.json()["status"] == "RESOLVED"
    assert s.state()["result"] == "UNVERIFIED"
    assert s.client.get(f"/api/v2/flights/{legacy}/state").status_code == 404


def test_delayed_old_sample_does_not_erase_a_newer_fresh_match(scenario):
    s = scenario
    atc = s.adopt(); match_readback(s, atc); cockpit(s)
    current = s.state()["current"]["COCKPIT"]
    s.tick(0.5)
    delayed = s.camera()
    delayed["observed_at"] = s.time(-11)
    assert s.send(delayed).status_code == 201
    assert s.inputs()[0]["reason"] == "OBSERVATION_OUT_OF_ORDER"
    assert s.state()["current"]["COCKPIT"] == current
    assert s.state()["result"] == "NORMAL"
