"""Intake, association, atomicity and no-false-normal tests (no real devices)."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from app.db import Base, make_engine
from app.migrate_observation_v2 import migrate
from app.models.flight import Flight
from app.models.clearance import Clearance
from app.models.safety_event import SafetyEvent
from app.models.observation_v2 import V2Migration
from app.schemas.observation_v2 import TargetSnapshotV2, IngestionReceiptV2
from app.services import receiving_v2 as service

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts/examples/v2"


class Scenario:
    def __init__(self, client, clock):
        self.client, self.clock = client, clock
        response = client.post("/api/v2/flights", json={"callsign": "RADAR123"})
        assert response.status_code == 201, response.text
        self.flight = response.json()["flight_id"]
        self.url = f"/api/v2/flights/{self.flight}"

    def tick(self, seconds=1):
        self.clock[0] += timedelta(seconds=seconds)

    def time(self, seconds=0):
        return service.stamp(self.clock[0] + timedelta(seconds=seconds))

    def payload(self, name):
        data = json.loads((EXAMPLES / name).read_text())
        data["flight_id"] = self.flight
        if "observation_id" in data:
            data["observation_id"] = "obs-"+uuid4().hex
            data["observed_at"] = self.time(-0.2)
            data["processed_at"] = self.time(-0.1)
            for value in data["fields"].values():
                value["quality"] = dict(model_score=0.9, input_quality="SUFFICIENT", reason=None,
                    score_calibrated=False, calibration_ref=None)
            if data.get("callsign"):
                data["callsign"]["quality"] = deepcopy(next(iter(data["fields"].values()))["quality"])
        return data

    def segment(self, atc=None, complete=True):
        data = self.payload("speech-complete.json")
        data.update(segment_id="seg-"+uuid4().hex, attempt_id="try-"+uuid4().hex,
            atc_input_id=atc["atc_input_id"] if atc else "atc-"+uuid4().hex,
            role="PILOT" if atc else "ATC", role_basis="PILOT_PTT" if atc else "ATC_PLAYBACK",
            started_at=self.time(-0.2), ended_at=self.time(-0.1), complete=complete,
            interruption_reason=None if complete else "focus_lost")
        response = self.client.post(self.url+"/speech-segments", json=data)
        assert response.status_code == 201, response.text
        return {**data, "instruction_id": response.json()["instruction_id"]}

    def speech(self, segment, partial=False):
        data = self.payload("atc-partial.json" if partial else "atc-full.json")
        data.update(segment_id=segment["segment_id"], atc_input_id=segment["atc_input_id"],
            attempt_id=segment["attempt_id"], observed_at=segment["started_at"])
        if segment["role"] == "PILOT":
            data.update(source="READBACK", instruction_id=segment["instruction_id"])
        return data

    def send(self, data):
        return self.client.post(self.url+"/observations", json=data)

    def adopt(self, partial=False):
        segment = self.segment()
        response = self.send(self.speech(segment, partial=partial))
        assert response.status_code == 201, response.text
        assert self.inputs()[0]["applied"], self.inputs()[0]
        return segment

    def camera(self):
        data = self.payload("cockpit-readable.json")
        data["frame_id"] = "frame-"+uuid4().hex
        data["target_revision"] = self.state()["revision"]
        return data

    def health(self, status="DISCONNECTED", offset=-0.1, event_id=None):
        data = self.payload("camera-disconnected.json")
        data.update(event_id=event_id or "health-"+uuid4().hex, observed_at=self.time(offset),
            health=dict(status=status, reason=None if status == "AVAILABLE" else "camera_disconnected"))
        return self.client.post(self.url+"/health-events", json=data)

    def state(self):
        response = self.client.get(self.url+"/state")
        assert response.status_code == 200, response.text
        return response.json()

    def inputs(self):
        return self.client.get(self.url+"/inputs").json()

    def trace(self):
        return self.client.get(self.url+"/safety-trace").json()


@pytest.fixture
def setup(client, tmp_path, monkeypatch):
    clock = [datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(service, "utc_now", lambda: clock[0])
    config = dict(callsigns={"RADAR123": {"radar-one-two-three": "Radar one two three"},
                             "OTHER123": {"other-one-two-three": "Other one two three"}},
                  freshness=dict(max_age_seconds=10.0, max_future_skew_seconds=0.2, minimum_model_score=0.5))
    config["structure_rules"] = {'policy_ref': 'synthetic-contract-tests/1', 'max_altitude_ft': 50000, 'max_altitude_change_ft': 10000, 'max_heading_change_deg': 180}
    path = tmp_path / "receiver.json"
    path.write_text(json.dumps(config))
    monkeypatch.setenv("RADAR_V2_CONFIG", str(path))
    return client, clock, config, path


@pytest.fixture
def scenario(setup):
    return Scenario(setup[0], setup[1])


def test_partial_instruction_retains_per_field_sources_and_no_false_normal(scenario):
    s = scenario
    a = s.adopt()
    s.tick()
    b = s.adopt(partial=True)
    state = s.state()
    assert state["targets"]["ALT"]["value"] == 4000
    assert state["targets"]["ALT"]["instruction_id"] == b["instruction_id"]
    assert state["targets"]["HDG"]["instruction_id"] == a["instruction_id"]
    assert state["readback_required"]["fields"] == ["ALT"]
    TargetSnapshotV2.model_validate({k: state[k] for k in ("schema_version", "flight_id", "revision", "targets", "readback_required")})
    s.tick()
    pilot = s.segment(b)
    assert s.send(s.speech(pilot, partial=True)).status_code == 201
    s.tick()
    assert s.send(s.camera()).status_code == 201
    assert s.state()["current"]["COCKPIT"]["HDG"]["value"] == 0
    assert s.state()["result"] == "UNVERIFIED"
    assert s.state()["current"]["READBACK"]["ALT"]["result"] == "UNVERIFIED"


def test_duplicate_id_is_idempotent_and_different_content_is_conflict(scenario):
    s = scenario
    s.adopt(); s.tick()
    payload = s.camera()
    response = s.send(payload)
    assert response.status_code == 201
    IngestionReceiptV2.model_validate(response.json())
    revision, events = s.state()["revision"], len(s.trace())
    duplicate = s.send(deepcopy(payload))
    assert duplicate.status_code == 200
    assert duplicate.json()["disposition"] == "DUPLICATE"
    assert duplicate.json()["event_id"] == response.json()["event_id"]
    payload["fields"]["ALT"]["value"] = 3001
    assert s.send(payload).status_code == 409
    assert s.state()["revision"] == revision
    assert len(s.trace()) == events


@pytest.mark.parametrize("has_current", [False, True])
def test_future_target_revision_is_rejected_without_mutating_state(scenario, has_current):
    s = scenario
    s.adopt(); s.tick()
    if has_current:
        assert s.send(s.camera()).status_code == 201
        s.tick()
    before, inputs, trace = s.state(), s.inputs(), s.trace()
    data = s.camera()
    data["target_revision"] = before["revision"] + 1
    response = s.send(data)
    assert response.status_code == 409
    assert response.json()["code"] == "CONTEXT_MISMATCH"
    assert s.state() == before
    assert s.inputs() == inputs
    assert s.trace() == trace
    # The exact current server revision is valid; the rejected frame was not consumed.
    data["target_revision"] = before["revision"]
    assert s.send(data).status_code == 201
    assert s.state()["current"]["COCKPIT"]["HDG"]["value"] == 0


def test_source_frame_cannot_be_replayed_with_a_new_observation_id(scenario):
    s = scenario
    s.adopt(); s.tick()
    data = s.camera(); assert s.send(data).status_code == 201
    data["observation_id"] = "new-obs-for-old-frame"
    assert s.send(data).status_code == 201
    assert not s.inputs()[0]["applied"]
    assert s.inputs()[0]["reason"] == "SOURCE_SAMPLE_REUSED"


@pytest.mark.parametrize("mutation,reason", [
    ("stale", "STALE_OBSERVATION"), ("unknown", "CAPTURE_TIME_UNKNOWN"),
    ("future", "FUTURE_OBSERVATION"), ("future_processing", "FUTURE_PROCESSING_TIME"),
    ("quality", "INPUT_QUALITY_UNVERIFIED"), ("score", "MODEL_SCORE_UNVERIFIED"),
    ("unreadable", "blank_roi"), ("old_revision", "TARGET_REVISION_OLD"),
    ("before_target", "OBSERVATION_PRECEDES_TARGET"),
])
def test_untrusted_camera_inputs_do_not_supply_current_values(scenario, mutation, reason):
    s = scenario
    s.adopt(); s.tick()
    data = s.camera()
    if mutation == "stale":
        data.update(observed_at=s.time(-11), processed_at=s.time(-0.1))
    elif mutation == "unknown":
        data.update(observed_at=None, time_basis="UNKNOWN", time_reason="file_time_unknown")
    elif mutation == "future":
        data.update(observed_at=s.time(1), processed_at=s.time(1.1))
    elif mutation == "future_processing":
        data["processed_at"] = s.time(1)
    elif mutation == "quality":
        data["fields"]["ALT"]["quality"].update(input_quality="UNKNOWN", reason="not_measured")
    elif mutation == "score":
        data["fields"]["ALT"]["quality"]["model_score"] = 0.1
    elif mutation == "unreadable":
        data["fields"]["ALT"].update(value=None, validity="UNREADABLE", reason="blank_roi")
    elif mutation == "old_revision":
        data["target_revision"] = 0
    elif mutation == "before_target":
        data["observed_at"] = s.time(-2)
    assert s.send(data).status_code == 201
    state = s.state()
    assert state["current"]["COCKPIT"]["ALT"]["value"] is None
    assert state["current"]["COCKPIT"]["ALT"]["reason"] == reason
    assert state["result"] == "UNVERIFIED"


def test_new_target_cannot_reuse_frame_from_before_adoption(scenario):
    s = scenario
    s.adopt(); s.tick()
    before = s.camera()
    s.tick(); s.adopt(partial=True)
    before["target_revision"] = s.state()["revision"]
    assert s.send(before).status_code == 201
    assert s.state()["current"]["COCKPIT"]["ALT"]["reason"] == "OBSERVATION_PRECEDES_TARGET"
    assert s.state()["current"]["COCKPIT"]["HDG"]["value"] == 0  # old instruction remains applicable


def test_older_camera_result_cannot_overwrite_newer_result(scenario):
    s = scenario
    s.adopt(); s.tick()
    older = s.camera()
    s.tick(); newer = s.camera(); newer["fields"]["ALT"]["value"] = 4000
    assert s.send(newer).status_code == 201
    assert s.send(older).status_code == 201
    assert s.state()["current"]["COCKPIT"]["ALT"]["value"] == 4000
    assert s.inputs()[0]["reason"] == "OBSERVATION_OUT_OF_ORDER"


def test_current_reading_expires_on_state_query_without_new_input(scenario):
    s = scenario
    s.adopt(); s.tick()
    s.send(s.camera())
    assert s.state()["current"]["COCKPIT"]["ALT"]["value"] == 3000
    s.tick(11)
    assert s.state()["current"]["COCKPIT"]["ALT"]["value"] is None
    assert s.state()["current"]["COCKPIT"]["ALT"]["reason"] == "STALE_OBSERVATION"


def test_disconnect_and_reconnect_require_a_new_camera_sample(scenario):
    s = scenario
    s.adopt(); s.tick(); old = s.camera(); s.send(old)
    assert s.health().status_code == 201
    assert not s.state()["current"]["COCKPIT"]
    s.tick(); assert s.health("AVAILABLE").status_code == 201
    assert not s.state()["current"]["COCKPIT"]
    old["observation_id"] = "old-after-reconnect"; old["frame_id"] = "old-frame-with-new-id"
    assert s.send(old).status_code == 201
    assert s.state()["current"]["COCKPIT"]["ALT"]["value"] is None
    s.tick(); s.send(s.camera())
    assert s.state()["current"]["COCKPIT"]["ALT"]["value"] == 3000
    assert s.state()["result"] == "UNVERIFIED"


def test_health_duplicates_and_out_of_order_events_do_not_restore_state(scenario):
    s = scenario
    s.adopt(); s.tick()
    assert s.health(event_id="health-one").status_code == 201
    before = len(s.trace())
    assert s.health(event_id="health-one").status_code == 200
    assert len(s.trace()) == before
    assert s.health("AVAILABLE", offset=-0.2).status_code == 201
    assert s.state()["channels"]["CAMERA"]["status"] == "DISCONNECTED"
    assert not s.inputs()[0]["applied"]


def test_cross_flight_ids_and_wrong_source_ownership_are_rejected(scenario, setup):
    s = scenario
    other = Scenario(setup[0], setup[1])
    data = s.camera(); data["flight_id"] = other.flight
    assert s.send(data).status_code == 409
    seg = other.segment(); bad = s.speech(seg); bad["flight_id"] = s.flight
    assert s.send(bad).status_code == 409
    assert s.inputs() == []


@pytest.mark.parametrize("key,value", [("attempt_id", "wrong"), ("atc_input_id", "wrong"), ("segment_id", "wrong")])
def test_speech_requires_registered_matching_context(scenario, key, value):
    s = scenario
    seg = s.segment(); data = s.speech(seg); data[key] = value
    assert s.send(data).status_code == 409
    assert s.state()["targets"]["ALT"] is None


def test_cancelled_or_superseded_attempts_cannot_change_targets(scenario):
    s = scenario
    old = s.segment(); old_data = s.speech(old)
    response = s.client.post(s.url+f"/speech-segments/{old['segment_id']}/cancel", json={"reason":"timeout"})
    assert response.status_code == 200
    assert s.send(old_data).status_code == 201
    assert s.inputs()[0]["reason"] == "ATTEMPT_CANCELLED"
    s.tick(); a = s.segment(); data = s.speech(a)
    s.tick(); b = s.adopt(partial=True)
    assert s.send(data).status_code == 201
    assert s.inputs()[0]["reason"] == "ATC_INPUT_SUPERSEDED"
    assert s.state()["targets"]["ALT"]["instruction_id"] == b["instruction_id"]


def test_incomplete_segment_is_evidence_only(scenario):
    s = scenario
    seg = s.segment(complete=False)
    assert s.send(s.speech(seg)).status_code == 201
    assert not s.inputs()[0]["applied"]
    assert s.state()["targets"]["ALT"] is None


def test_early_pilot_result_waits_for_its_own_atc(scenario):
    s = scenario
    atc = s.segment()
    s.tick(0.5); pilot = s.segment(atc)
    assert s.send(s.speech(pilot)).status_code == 201
    assert s.inputs()[0]["reason"] == "ATC_NOT_ADOPTED"
    s.tick(0.5); assert s.send(s.speech(atc)).status_code == 201
    state = s.state()
    assert state["current"]["READBACK"]["ALT"]["value"] == 3000
    assert any(e["event_type"] == "DEFERRED_READBACK_RECHECKED" for e in s.trace())


def test_old_pilot_attempt_does_not_replace_new_correction(scenario):
    s = scenario
    atc = s.adopt()
    s.tick(); old = s.segment(atc); old_result = s.speech(old)
    s.tick(); new = s.segment(atc); new_result = s.speech(new)
    assert s.send(new_result).status_code == 201
    assert s.send(old_result).status_code == 201
    assert s.inputs()[0]["reason"] == "PILOT_ATTEMPT_SUPERSEDED"
    assert s.state()["current"]["READBACK"]["ALT"]["segment_id"] == new["segment_id"]


def test_wrong_readback_instruction_is_not_rebound(scenario):
    s = scenario
    atc = s.adopt(); s.tick(); pilot = s.segment(atc)
    data = s.speech(pilot); data["instruction_id"] = "OTHER-INSTRUCTION"
    assert s.send(data).status_code == 409


@pytest.mark.parametrize("mutate,expected", [("missing", "callsign_missing"), ("unknown_alias", "CALLSIGN_ALIAS_UNVERIFIED"), ("other", "OUT_OF_TARGET")])
def test_callsign_registry_and_target_are_checked(scenario, mutate, expected):
    s = scenario
    seg = s.segment(); data = s.speech(seg)
    if mutate == "missing":
        data["callsign"].update(value=None, raw_text=None, alias_key=None, validity="UNREADABLE", reason="callsign_missing")
        data["instruction_check"] = "NEEDS_REVIEW"
    elif mutate == "unknown_alias":
        data["callsign"]["alias_key"] = "not-registered"
    else:
        data["callsign"].update(value="OTHER123", raw_text="Other one two three", alias_key="other-one-two-three")
    assert s.send(data).status_code == 201
    assert s.inputs()[0]["reason"] == expected
    assert s.state()["targets"]["ALT"] is None


def test_policy_is_explicit_and_frozen_per_flight(setup):
    client, clock, config, path = setup
    config["freshness"] = None; path.write_text(json.dumps(config))
    s = Scenario(client, clock)
    config["freshness"] = dict(max_age_seconds=10.0, max_future_skew_seconds=0.2, minimum_model_score=0.5)
    path.write_text(json.dumps(config))
    assert s.send(s.speech(s.segment())).status_code == 201
    assert s.inputs()[0]["reason"] == "POLICY_NOT_CONFIGURED"
    assert s.state()["targets"]["ALT"] is None


def test_unregistered_and_unconfigured_flights_cannot_start(setup, monkeypatch):
    client, clock, _, _ = setup
    response = client.post("/api/v2/flights", json={"callsign":"NOTREGISTERED"})
    assert response.status_code == 422
    assert "RADAR123" in response.json()["message"]
    monkeypatch.delenv("RADAR_V2_CONFIG")
    assert client.post("/api/v2/flights", json={"callsign":"RADAR123"}).status_code == 422


def test_ended_flight_rejects_all_mutations_even_via_legacy_end(scenario):
    s = scenario
    s.adopt(); s.tick(); data = s.camera()
    response = s.client.post(f"/api/flights/{s.flight}/end")
    assert response.status_code == 200
    assert s.send(data).status_code == 409
    assert s.health().status_code == 409
    assert s.client.post(s.url+"/end").status_code == 409
    assert s.state()["reason"] == "FLIGHT_ENDED"


def test_v2_end_keeps_legacy_trace_response_shape(scenario):
    s = scenario
    s.adopt(); s.tick(); s.send(s.camera())
    assert s.client.post(s.url+"/end").status_code == 200
    legacy = s.client.get(f"/api/flights/{s.flight}/safety-trace")
    assert legacy.status_code == 200
    assert len(legacy.json()) == 2
    assert all(e["observation"] is None for e in legacy.json())
    assert s.trace()[-1]["event_type"] == "FLIGHT_ENDED"


def test_versioned_payload_errors_and_legacy_errors_keep_separate_shapes(scenario):
    s = scenario
    data = s.camera(); data["schema_version"] = "99"
    response = s.send(data)
    assert response.status_code == 422 and response.json()["code"] == "UNSUPPORTED_VERSION"
    data["schema_version"] = "2"; data["fields"]["HDG"]["value"] = 360
    assert s.send(data).json()["code"] == "INVALID_PAYLOAD"
    assert "detail" in s.client.post("/api/flights/unknown/clearances", json={}).json()
    assert s.client.get("/api/v2/flights/unknown/state").status_code == 404


def test_concurrent_duplicate_is_received_exactly_once(scenario):
    s = scenario
    s.adopt(); s.tick(); data = s.camera()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: s.send(deepcopy(data)), range(2)))
    assert sorted(r.status_code for r in responses) == [200,201]
    assert len([r for r in s.inputs() if r["input_id"] == data["observation_id"]]) == 1


def test_commit_failure_rolls_back_state_input_and_trace_together(scenario, monkeypatch):
    s = scenario
    seg = s.segment()
    before_state, before_trace = s.state(), s.trace()
    original = Session.commit
    def fail_commit(self):
        raise RuntimeError("simulated disk/commit failure")
    monkeypatch.setattr(Session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="commit failure"):
        s.send(s.speech(seg))
    monkeypatch.setattr(Session, "commit", original)
    assert s.state() == before_state
    assert s.trace() == before_trace
    assert s.inputs() == []


def test_additive_migration_preserves_existing_database_and_is_repeatable(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path/'old.db'}")
    try:
        Base.metadata.create_all(engine, tables=[Flight.__table__, Clearance.__table__, SafetyEvent.__table__])
        with engine.begin() as connection:
            connection.execute(Flight.__table__.insert().values(flight_id="OLD-FLIGHT", started_at="2026-10-01T00:00:00Z", status="ACTIVE"))
        def columns():
            return [{**c, "type": str(c["type"])} for c in inspect(engine).get_columns("flights")]
        columns_before = columns()
        migrate(engine); migrate(engine)
        assert columns() == columns_before
        with engine.connect() as connection:
            assert connection.scalar(select(Flight.flight_id)) == "OLD-FLIGHT"
            assert len(connection.execute(select(V2Migration.version)).all()) == 1
        assert "v2_inputs" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_low_quality_callsign_cannot_adopt_a_target(scenario):
    s = scenario
    data = s.speech(s.segment())
    data["callsign"]["quality"].update(input_quality="INSUFFICIENT", reason="overlapping_speech")
    assert s.send(data).status_code == 201
    assert s.inputs()[0]["reason"] == "CALLSIGN_QUALITY_UNVERIFIED"
    assert s.state()["targets"]["ALT"] is None


def test_cancel_pilot_clears_only_its_current_result(scenario):
    s = scenario
    atc = s.adopt(); s.tick(); pilot = s.segment(atc)
    s.send(s.speech(pilot))
    assert s.state()["current"]["READBACK"]["ALT"]["value"] == 3000
    assert s.client.post(s.url+f"/speech-segments/{pilot['segment_id']}/cancel", json={"reason":"timeout"}).status_code == 200
    assert s.state()["current"]["READBACK"]["ALT"] is None


def test_pilot_cannot_be_registered_before_atc_capture_ends(scenario):
    s = scenario
    atc = s.segment()
    data = s.payload("speech-complete.json")
    data.update(segment_id="early-pilot", attempt_id="early-attempt", atc_input_id=atc["atc_input_id"],
                role="PILOT", role_basis="PILOT_PTT", started_at=s.time(-0.3), ended_at=s.time(-0.25))
    assert s.client.post(s.url+"/speech-segments", json=data).status_code == 409


def test_future_segment_cannot_block_later_real_input(scenario):
    s = scenario
    data = s.payload("speech-complete.json")
    data.update(segment_id="future-segment", attempt_id="future-attempt", atc_input_id="future-input",
                started_at=s.time(99), ended_at=s.time(100))
    assert s.client.post(s.url+"/speech-segments", json=data).status_code == 409
    assert s.adopt()["instruction_id"] == s.state()["targets"]["ALT"]["instruction_id"]


def test_segment_reregistration_is_idempotent_and_attempt_id_cannot_be_reassigned(scenario):
    s = scenario
    segment = s.segment()
    body = {k:v for k,v in segment.items() if k != "instruction_id"}
    before = len(s.trace())
    assert s.client.post(s.url+"/speech-segments", json=body).status_code == 200
    assert len(s.trace()) == before
    body["segment_id"] = "different-segment"
    assert s.client.post(s.url+"/speech-segments", json=body).status_code == 409


def test_snapshot_and_registry_are_not_changed_by_later_configuration_edits(scenario, setup):
    s = scenario
    config, path = setup[2], setup[3]
    config["callsigns"]["RADAR123"] = {"replacement":"Different phrase"}
    config["freshness"]["max_age_seconds"] = 0.01
    path.write_text(json.dumps(config))
    s.adopt()
    assert s.state()["targets"]["ALT"]["value"] == 3000


def test_existing_v1_flight_requires_v2_context_instead_of_silent_upgrade(setup):
    client = setup[0]
    flight = client.post("/api/flights/start").json()["flight_id"]
    assert client.get(f"/api/v2/flights/{flight}/state").status_code == 404


def test_equal_target_adoption_timestamp_is_not_a_new_correction(scenario):
    s = scenario
    s.adopt(); s.tick()
    data = s.camera()
    data["observed_at"] = s.state()["targets"]["ALT"]["adopted_at"]
    assert s.send(data).status_code == 201
    assert s.state()["current"]["COCKPIT"]["ALT"]["value"] is None
    assert s.inputs()[0]["reason"] == "OBSERVATION_PRECEDES_TARGET"


def test_old_pilot_registration_does_not_reset_new_attempt(scenario):
    s = scenario
    atc = s.adopt(); s.tick(); first = s.segment(atc)
    s.tick(); latest = s.segment(atc)
    body = {k:v for k,v in first.items() if k != "instruction_id"}
    body.update(segment_id="delayed-old-segment", attempt_id="delayed-old-attempt")
    assert s.client.post(s.url+"/speech-segments", json=body).status_code == 409
    assert s.send(s.speech(latest)).status_code == 201
    assert s.inputs()[0]["applied"]


def test_explicit_speech_api_outage_cannot_be_cleared_by_a_numeric_extraction(scenario):
    s = scenario
    response = s.health()
    assert response.status_code == 201
    data = s.payload("camera-disconnected.json")
    data.update(event_id="speech-api-outage", channel="SPEECH_API", observed_at=s.time(-0.1),
                health={"status":"DISCONNECTED", "reason":"provider_unavailable"})
    assert s.client.post(s.url+"/health-events", json=data).status_code == 201
    s.tick(); segment = s.segment(); s.send(s.speech(segment))
    assert s.inputs()[0]["reason"] == "SPEECH_API_UNAVAILABLE"
    assert s.state()["targets"]["ALT"] is None


def test_readback_of_replaced_field_does_not_clear_new_instruction_result(scenario):
    s = scenario
    a = s.adopt(); s.tick(); old_pilot = s.segment(a); old = s.speech(old_pilot)
    s.tick(); b = s.adopt(partial=True); s.tick(); pilot = s.segment(b)
    s.send(s.speech(pilot, partial=True))
    expected = s.state()["current"]["READBACK"]["ALT"]
    # A late result has an older capture time and cannot overwrite B's result.
    s.send(old)
    assert s.state()["current"]["READBACK"]["ALT"] == expected


def test_duplicate_observation_id_is_not_reusable_in_another_flight(scenario, setup):
    s = scenario
    data = s.camera(); assert s.send(data).status_code == 201
    other = Scenario(setup[0],setup[1]); data["flight_id"] = other.flight
    assert other.send(data).status_code == 409
