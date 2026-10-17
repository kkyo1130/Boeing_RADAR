"""Real intake comparisons with fixed clock; no device/model accuracy claims."""
from copy import deepcopy
import pytest
from sqlalchemy.orm import Session

from test_receiving_v2 import Scenario, setup, scenario


def match_readback(s, atc, partial=False):
    s.tick(0.5)
    pilot = s.segment(atc)
    data = s.speech(pilot, partial=partial)
    assert s.send(data).status_code == 201
    return data


def cockpit(s, altitude=3000, heading=270):
    s.tick(0.25)
    data = s.camera()
    for name, value in (("ALT", altitude), ("HDG", heading)):
        data["fields"][name].update(value=value, raw_text=str(value))
    assert s.send(data).status_code == 201
    return data


def test_full_three_state_success_is_not_legacy_resolved(scenario):
    s = scenario
    atc = s.adopt(); match_readback(s, atc); cockpit(s)
    state = s.state()
    assert state["result"] == "NORMAL"
    assert state["status"] == "ACTIVE"
    assert state["validation"]["phase"] == "MONITORING"
    assert state["validation"]["advisory_candidates"] == []
    assert s.trace()[-1]["snapshot"]["validation"] == state["validation"]


def test_setting_wait_exact_boundary_and_duplicate_receipt(scenario):
    s = scenario
    atc = s.adopt(); rb = match_readback(s, atc)
    t0 = s.clock[0]
    cockpit(s, altitude=2000)
    s.clock[0] = t0
    s.tick(4.999)
    assert s.state()["result"] == "UNVERIFIED"
    before_trace, before_state = s.trace(), s.state()
    assert s.send(rb).status_code == 200
    assert s.trace() == before_trace and s.state() == before_state
    s.tick(0.001)
    state = s.state()
    assert state["result"] == "MISMATCH"
    assert [field["field"] for field in state["validation"]["advisory_candidates"]] == ["ALT"]


def test_early_match_then_immediate_deviation_and_health_recovery(scenario):
    s = scenario
    atc = s.adopt(); match_readback(s, atc)
    cockpit(s)
    assert s.state()["result"] == "NORMAL"
    cockpit(s, heading=90)
    assert s.state()["result"] == "MISMATCH"
    assert s.state()["validation"]["setting"]["fields"][1]["reason"] == "SETTING_DEVIATED_AFTER_MATCH"
    assert s.health().status_code == 201
    assert s.state()["result"] == "UNVERIFIED"
    s.tick(0.1); assert s.health("AVAILABLE").status_code == 201
    assert s.state()["result"] == "UNVERIFIED"
    cockpit(s)
    assert s.state()["result"] == "NORMAL"


def test_readback_error_is_confirmed_while_camera_is_unreadable(scenario):
    s = scenario
    atc = s.adopt(); s.tick()
    data = s.speech(s.segment(atc))
    data["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    data["fields"]["ALT"].update(value=4000, raw_text="4000")
    assert s.send(data).status_code == 201
    state = s.state()
    assert state["result"] == "MISMATCH"
    assert state["validation"]["representative_stage"] == "READBACK"
    assert state["validation"]["setting"]["result"] == "UNVERIFIED"


def test_known_wrong_callsign_and_missing_callsign_have_different_verdicts(scenario):
    s = scenario
    atc = s.adopt(); s.tick()
    data = s.speech(s.segment(atc))
    data["transcript"] = data["transcript"].replace("Radar one two three", "Other one two three")
    data["callsign"].update(raw_text="Other one two three", value="OTHER123", alias_key="other-one-two-three")
    assert s.send(data).status_code == 201
    state = s.state()
    assert state["result"] == "MISMATCH"
    assert state["validation"]["advisory_candidates"][0]["field"] == "CALLSIGN"
    s.tick(); missing = s.speech(s.segment(atc))
    missing["callsign"].update(value=None, raw_text=None, alias_key=None, validity="UNREADABLE", reason="callsign_missing")
    missing["instruction_check"] = "NEEDS_REVIEW"
    assert s.send(missing).status_code == 201
    assert s.state()["result"] == "UNVERIFIED"


def test_partial_altitude_uses_new_timer_and_preserves_heading_monitor(scenario):
    s = scenario
    a = s.adopt(); match_readback(s, a); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    cockpit(s, heading=90)
    assert s.state()["result"] == "MISMATCH"
    s.tick(); b = s.adopt(partial=True)
    assert s.state()["validation"]["advisory_candidates"] == []
    match_readback(s, b, partial=True)
    cockpit(s, altitude=3000, heading=90)
    state = s.state()
    assert state["targets"]["HDG"]["instruction_id"] == a["instruction_id"]
    assert state["targets"]["ALT"]["instruction_id"] == b["instruction_id"]
    assert [field["field"] for field in state["validation"]["advisory_candidates"]] == ["HDG"]


def test_pending_or_failed_new_atc_never_reuses_old_normal(scenario):
    s = scenario
    a = s.adopt(); match_readback(s, a); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    s.tick(); segment = s.segment()
    assert s.state()["result"] == "UNVERIFIED"
    data = s.speech(segment)
    data["fields"]["ALT"].update(value=4000, raw_text="4000")
    assert s.send(data).status_code == 201
    assert s.state()["result"] == "UNVERIFIED"
    assert s.state()["targets"]["ALT"]["instruction_id"] == a["instruction_id"]


def test_cancel_retry_and_expiry_do_not_leave_false_normal(scenario):
    s = scenario
    a = s.adopt(); rb = match_readback(s, a); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    assert s.client.post(s.url+f"/speech-segments/{rb['segment_id']}/cancel", json={"reason":"fixture_cancel"}).status_code == 200
    assert s.state()["result"] == "UNVERIFIED"
    match_readback(s, a); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    s.tick(11)
    assert s.state()["result"] == "UNVERIFIED"
    assert s.client.post(s.url+"/end").status_code == 200
    assert s.state()["validation"]["phase"] == "ENDED"


def test_readback_confirmation_and_timer_roll_back_with_failed_commit(scenario, monkeypatch):
    s = scenario
    atc = s.adopt(); s.tick()
    pilot = s.segment(atc)
    data = s.speech(pilot)
    before, trace = s.state(), s.trace()
    original = Session.commit
    def fail(self):
        raise RuntimeError("timer commit failure")
    monkeypatch.setattr(Session, "commit", fail)
    with pytest.raises(RuntimeError, match="timer commit failure"):
        s.send(data)
    monkeypatch.setattr(Session, "commit", original)
    assert s.state() == before and s.trace() == trace


def test_get_after_deadline_changes_derived_result_without_writing_events(scenario):
    s = scenario
    atc = s.adopt(); match_readback(s, atc); cockpit(s, altitude=2000)
    before = s.state()
    trace = s.trace()
    assert before["result"] == "UNVERIFIED"
    s.tick(5)
    after = s.state()
    assert after["result"] == "MISMATCH"
    assert after["revision"] == before["revision"] and s.trace() == trace


def test_completed_readback_survives_age_for_continued_new_camera_monitoring(scenario):
    s = scenario
    a = s.adopt(); match_readback(s, a); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    s.tick(11)
    assert s.state()["result"] == "UNVERIFIED"  # Camera expired.
    cockpit(s)
    assert s.state()["result"] == "NORMAL"  # No repeat readback of unchanged ATC.
    cockpit(s, heading=90)
    assert s.state()["result"] == "MISMATCH"
