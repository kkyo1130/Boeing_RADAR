"""Occurrence identity, new evidence, replacement and atomic persistence."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from test_receiving_v2 import setup, scenario, Scenario
from test_validation_v2_api import match_readback, cockpit


def incidents(s, status=None):
    rows = s.state()["incidents"]
    return [row for row in rows if status is None or row["status"] == status]


def monitoring(s):
    atc = s.adopt(); match_readback(s, atc); cockpit(s)
    assert s.state()["result"] == "NORMAL"
    return atc


def test_occurrence_updates_resolves_and_recurs_with_distinct_id(scenario):
    s = scenario; monitoring(s)
    first = cockpit(s, altitude=2000)
    original = incidents(s)[0]
    assert original["first_evidence"]["frame_id"] == first["frame_id"]
    assert original["notified_at"] is None and original["voice_completed_at"] is None
    second = cockpit(s, altitude=2500)
    updated = incidents(s)[0]
    assert updated["occurrence_id"] == original["occurrence_id"]
    assert updated["detected_at"] == original["detected_at"]
    assert updated["latest_evidence"]["observation_id"] == second["observation_id"]
    fixed = cockpit(s)
    resolved = incidents(s)[0]
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution_evidence"]["frame_id"] == fixed["frame_id"]
    cockpit(s, altitude=2000)
    assert len(incidents(s)) == 2
    assert incidents(s, "OPEN")[0]["occurrence_id"] != original["occurrence_id"]
    assert incidents(s, "OPEN")[0]["notified_at"] is None


@pytest.mark.parametrize("fault", ["same_frame", "stale", "unknown_time", "old_revision", "unreadable", "future", "low_quality"])
def test_invalid_correction_never_resolves_incident(scenario, fault):
    s = scenario; monitoring(s)
    previous = cockpit(s, altitude=2000)
    s.tick(0.5); data = s.camera()
    for name, value in (("ALT", 3000), ("HDG", 270)):
        data["fields"][name].update(value=value, raw_text=str(value))
    if fault == "same_frame":
        data["frame_id"] = previous["frame_id"]
    elif fault == "stale":
        data["observed_at"] = s.time(-11)
    elif fault == "unknown_time":
        data.update(observed_at=None, time_basis="UNKNOWN", time_reason="capture_missing")
    elif fault == "old_revision":
        data["target_revision"] = 0
    elif fault == "unreadable":
        data["fields"]["ALT"].update(value=None, raw_text=None, validity="UNREADABLE", reason="blank_roi")
    elif fault == "future":
        data.update(observed_at=s.time(2), processed_at=s.time(2))
    else:
        data["fields"]["ALT"]["quality"]["model_score"] = 0.1
    response = s.send(data)
    assert response.status_code == 201, response.text
    assert len(incidents(s, "OPEN")) == 1
    assert incidents(s)[0]["resolution_evidence"] is None


def test_health_loss_and_expiry_keep_open_with_unverified_current_check(scenario):
    s = scenario; monitoring(s); cockpit(s, heading=90)
    s.tick(11)
    assert incidents(s)[0]["current_check"]["result"] == "UNVERIFIED"
    assert s.health().status_code == 201
    assert incidents(s)[0]["status"] == "OPEN"
    s.tick(); assert s.health("AVAILABLE").status_code == 201
    assert incidents(s)[0]["status"] == "OPEN"
    cockpit(s)
    assert incidents(s)[0]["status"] == "RESOLVED"


def test_partial_replacement_supersedes_altitude_and_keeps_heading_occurrence(scenario):
    s = scenario; a = monitoring(s); cockpit(s, altitude=2000, heading=90)
    old = {row["field"]: row for row in incidents(s)}
    s.tick(); b = s.adopt(partial=True)
    rows = {row["field"]: row for row in incidents(s)}
    assert rows["ALT"]["status"] == "SUPERSEDED" and rows["ALT"]["resolved_at"] is None
    assert rows["HDG"]["status"] == "OPEN"
    assert rows["HDG"]["occurrence_id"] == old["HDG"]["occurrence_id"]
    assert rows["HDG"]["instruction_id"] == a["instruction_id"]
    match_readback(s, b, partial=True); cockpit(s, altitude=4000, heading=90)
    assert len(incidents(s, "OPEN")) == 1
    assert incidents(s, "OPEN")[0]["field"] == "HDG"


def test_pending_failed_and_out_of_target_atc_do_not_supersede(scenario):
    s = scenario; monitoring(s); cockpit(s, altitude=2000)
    s.tick(); atc = s.segment()
    assert incidents(s)[0]["status"] == "OPEN"
    data = s.speech(atc)
    data["fields"]["ALT"].update(value=4000, raw_text="4000")  # Transcript conflict.
    assert s.send(data).status_code == 201
    assert incidents(s)[0]["status"] == "OPEN"
    s.tick(); atc = s.segment(); data = s.speech(atc)
    data["transcript"] = data["transcript"].replace("Radar", "Other")
    data["callsign"].update(value="OTHER123", alias_key="other-one-two-three", raw_text="Other one two three")
    assert s.send(data).status_code == 201
    assert incidents(s)[0]["status"] == "OPEN"


def test_readback_requires_new_complete_attempt_and_keeps_same_occurrence(scenario):
    s = scenario; atc = s.adopt(); s.tick()
    bad = s.speech(s.segment(atc))
    bad["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    bad["fields"]["ALT"].update(value=4000, raw_text="4000")
    assert s.send(bad).status_code == 201
    occurrence = incidents(s)[0]["occurrence_id"]
    s.tick(); incomplete = s.segment(atc, complete=False)
    assert s.send(s.speech(incomplete)).status_code == 201
    assert incidents(s)[0]["status"] == "OPEN"
    match_readback(s, atc)
    row = incidents(s)[0]
    assert row["occurrence_id"] == occurrence and row["status"] == "RESOLVED"
    assert row["resolution_evidence"]["segment_id"] != bad["segment_id"]
    assert s.state()["result"] == "UNVERIFIED"  # Camera still unavailable.


def test_retransmission_old_frame_and_get_do_not_duplicate_transitions(scenario):
    s = scenario; monitoring(s); data = cockpit(s, altitude=2000)
    before, trace = s.state(), s.trace()
    assert s.send(data).status_code == 200
    assert s.state() == before and s.trace() == trace
    replay = deepcopy(data); replay["observation_id"] = "replay-"+uuid4().hex
    assert s.send(replay).status_code == 201
    assert s.inputs()[0]["reason"] == "SOURCE_SAMPLE_REUSED"
    assert incidents(s) == before["incidents"]
    assert sum(row["event_type"] == "INCIDENT_UPDATED" for row in s.trace()) == 1


def test_timer_revalidation_is_explicit_and_end_preserves_unresolved_history(scenario):
    s = scenario; a = s.adopt(); match_readback(s, a); cockpit(s, altitude=2000)
    before = s.trace(); s.tick(5)
    assert s.state()["result"] == "MISMATCH" and incidents(s) == []
    assert s.trace() == before  # GET remains read-only.
    result = s.client.post(s.url+"/revalidate")
    assert result.status_code == 200 and len(incidents(s, "OPEN")) == 1
    s.client.post(s.url+"/revalidate")
    assert len(incidents(s)) == 1
    assert s.client.post(s.url+"/end").status_code == 200
    assert incidents(s)[0]["status"] == "ENDED_UNRESOLVED"
    assert incidents(s)[0]["resolved_at"] is None
    assert s.client.post(s.url+"/revalidate").status_code == 409


def test_occurrence_and_trace_roll_back_together(scenario, monkeypatch):
    s = scenario; monitoring(s)
    s.tick(); data = s.camera()
    data["fields"]["ALT"].update(value=2000, raw_text="2000")
    data["fields"]["HDG"].update(value=270, raw_text="270")
    before, trace = s.state(), s.trace()
    original = Session.commit
    monkeypatch.setattr(Session, "commit", lambda self: (_ for _ in ()).throw(RuntimeError("commit fail")))
    with pytest.raises(RuntimeError, match="commit fail"):
        s.send(data)
    monkeypatch.setattr(Session, "commit", original)
    assert s.state() == before and s.trace() == trace
    assert s.send(data).status_code == 201
    assert len(incidents(s)) == 1


def test_incidents_are_isolated_per_flight(setup):
    one = Scenario(setup[0], setup[1]); monitoring(one); cockpit(one, heading=90)
    two = Scenario(setup[0], setup[1]); monitoring(two)
    assert incidents(two) == [] and len(incidents(one, "OPEN")) == 1


def test_corrected_field_does_not_resolve_incomplete_readback(scenario):
    s = scenario; atc = s.adopt(); s.tick()
    bad = s.speech(s.segment(atc))
    bad["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    bad["fields"]["ALT"].update(value=4000, raw_text="4000")
    s.send(bad)
    s.tick(); correction = s.speech(s.segment(atc))
    correction["fields"]["HDG"].update(value=None, raw_text=None, validity="UNREADABLE", reason="capture_missing")
    correction["instruction_check"] = "NEEDS_REVIEW"
    assert s.send(correction).status_code == 201
    assert incidents(s)[0]["status"] == "OPEN"
    match_readback(s, atc)
    assert incidents(s)[0]["status"] == "RESOLVED"


def test_partial_replacement_preserves_completed_voice_metadata(scenario):
    from app.services.incidents_v2 import reconcile
    s = scenario; monitoring(s); cockpit(s, altitude=2000, heading=90)
    snapshot = s.state()
    heading = next(item for item in snapshot["incidents"] if item["field"] == "HDG")
    heading["voice_completed_at"] = s.time()
    heading["notified_at"] = s.time()
    before = deepcopy(heading)
    snapshot["targets"]["ALT"]["instruction_id"] = "B"
    reconcile(snapshot, s.flight, snapshot["validation"], s.clock[0])
    assert heading == before


def test_runtime_incident_schema_matches_contract_and_real_response(scenario):
    import json
    from pathlib import Path
    from app.schemas.incidents_v2 import IncidentV1
    s = scenario; monitoring(s); cockpit(s, altitude=2000); cockpit(s)
    for row in incidents(s):
        assert IncidentV1.model_validate(row).model_dump(mode="json") == row
    schema = IncidentV1.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:radar:contracts:incident-v1"
    actual = json.loads((Path(__file__).resolve().parents[2] / "contracts/schemas/incident-v1.schema.json").read_text())
    assert schema == actual
