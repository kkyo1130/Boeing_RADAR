"""SPEC-002 AC-03: wire-level producer/consumer agreement, not model accuracy."""
from copy import deepcopy
import json

import pytest

from mock_producer import CASES, MockProducer, timestamp, validate


def stored(producer, payload):
    return next(row for row in producer.inputs() if row["input_id"] == payload["observation_id"])


def test_normal_input_preserves_zero_null_timestamps_and_evidence(producer):
    p = producer
    p.adopt()
    camera = p.camera("cockpit-unreadable.json")
    camera["fields"]["HDG"].update(value=0, raw_text="0")
    receipt = p.send(camera)
    state = p.state()
    assert state["current"]["COCKPIT"]["HDG"]["value"] == 0
    assert state["current"]["COCKPIT"]["ALT"]["value"] is None
    assert state["current"]["COCKPIT"]["ALT"]["reason"] == "blank_roi"
    row = stored(p, camera)
    assert row["payload"] == camera
    assert row["event_id"] == receipt["event_id"]
    event = next(event for event in p.trace() if event["event_id"] == receipt["event_id"])
    assert event["snapshot"]["payload"] == camera
    assert camera["evidence_refs"] == []
    assert camera["evidence_unavailable_reason"] == "fixture_has_no_media"
    assert camera["observed_at"] <= camera["processed_at"]
    assert state["result"] == "UNVERIFIED"


def test_partial_instruction_and_readback_keep_unchanged_heading_owner(producer):
    p = producer
    a, first = p.adopt()
    b, partial = p.adopt("atc-partial.json")
    pilot = p.segment(b)
    readback = p.speech(pilot, "readback-partial.json")
    p.send(readback)
    state = p.state()
    assert state["targets"]["ALT"] == dict(value=4000, unit="ft", instruction_id=b["instruction_id"],
        source_observation_id=partial["observation_id"], adopted_at=state["targets"]["ALT"]["adopted_at"])
    assert state["targets"]["HDG"]["value"] == 270
    assert state["targets"]["HDG"]["instruction_id"] == a["instruction_id"]
    assert state["targets"]["HDG"]["source_observation_id"] == first["observation_id"]
    assert state["readback_required"]["fields"] == ["ALT"]
    assert state["readback_required"]["callsign_required"] is True
    assert list(stored(p, readback)["payload"]["fields"]) == ["ALT"]
    assert state["current"]["READBACK"]["ALT"]["value"] == 4000
    assert state["result"] == "UNVERIFIED"


def test_unrecognized_new_instruction_does_not_become_partial_success(producer):
    p = producer
    p.adopt()
    before = p.state()["targets"]
    segment = p.segment()
    ambiguous = p.speech(segment, "atc-ambiguous.json")
    p.send(ambiguous)
    assert p.state()["targets"] == before
    assert stored(p, ambiguous)["applied"] is False
    assert stored(p, ambiguous)["reason"] == "EXTRACTION_UNVERIFIED"
    assert stored(p, ambiguous)["payload"]["fields"]["ALT"]["value"] is None


def test_disconnect_recovery_requires_a_new_frame(producer):
    p = producer
    p.adopt()
    previous = p.camera()
    p.send(previous)
    p.health("DISCONNECTED")
    state = p.state()
    assert state["channels"]["CAMERA"]["status"] == "DISCONNECTED"
    assert state["current"]["COCKPIT"] == {}
    p.health("AVAILABLE")
    assert p.state()["current"]["COCKPIT"] == {}
    replay = deepcopy(previous)
    replay["observation_id"] = p.identifier("replay")
    p.send(replay)
    assert stored(p, replay)["reason"] == "SOURCE_SAMPLE_REUSED"
    assert p.state()["current"]["COCKPIT"] == {}
    fresh = p.camera()
    p.send(fresh)
    assert p.state()["current"]["COCKPIT"]["HDG"]["observation_id"] == fresh["observation_id"]
    assert p.state()["result"] == "UNVERIFIED"


def test_new_target_rejects_old_camera_and_allows_fresh_reobservation(producer):
    p = producer
    p.adopt()
    old = p.camera()
    p.send(old)
    delayed = p.camera()
    p.adopt("atc-partial.json")
    p.send(delayed)
    state = p.state()
    assert state["current"]["COCKPIT"]["ALT"]["value"] is None
    assert state["current"]["COCKPIT"]["ALT"]["reason"] == "TARGET_REVISION_OLD"
    assert state["current"]["COCKPIT"]["HDG"]["observation_id"] == delayed["observation_id"]
    fresh = p.camera("cockpit-reverify.json")
    p.send(fresh)
    assert p.state()["current"]["COCKPIT"]["ALT"]["value"] == fresh["fields"]["ALT"]["value"]
    assert stored(p, old)["payload"] == old
    assert p.state()["result"] == "UNVERIFIED"


@pytest.mark.parametrize("case", CASES["invalid_observations"], ids=lambda case: case["name"])
def test_invalid_wire_payload_is_rejected_without_partial_save(producer, case):
    p = producer
    p.adopt()
    data = p.camera()
    for path, value in case.get("patch", {}).items():
        obj = data
        keys = path.split(".")
        for key in keys[:-1]:
            obj = obj[key]
        obj[keys[-1]] = value
    if "remove" in case:
        data.pop(case["remove"])
    before, inputs, trace = p.state(), p.inputs(), p.trace()
    error = p.send(data, expected=case["status"], check_schema=False)
    assert error["code"] == case["code"]
    assert p.state() == before
    assert p.inputs() == inputs
    assert p.trace() == trace


@pytest.mark.parametrize("kind,reason", [("stale", "STALE_OBSERVATION"),
    ("future", "FUTURE_OBSERVATION"), ("unknown", "CAPTURE_TIME_UNKNOWN")])
def test_capture_time_is_not_replaced_with_receive_time(producer, kind, reason):
    p = producer
    p.adopt()
    data = p.camera()
    if kind == "unknown":
        data.update(observed_at=None, time_basis="UNKNOWN", time_reason="fixture_clock_unavailable")
    else:
        data["observed_at"] = timestamp(-3600 if kind == "stale" else 3600)
        if kind == "future":
            data["processed_at"] = data["observed_at"]
    p.send(data)
    row = stored(p, data)
    assert row["payload"]["observed_at"] == data["observed_at"]
    assert row["reason"] == reason
    assert row["applied"] is False
    assert all(value["value"] is None for value in p.state()["current"]["COCKPIT"].values())


def test_future_revision_cannot_cross_the_http_boundary(producer):
    p = producer
    p.adopt()
    data = p.camera()
    before = p.state()
    data["target_revision"] = before["revision"]+1
    assert p.send(data, expected=409)["code"] == "CONTEXT_MISMATCH"
    assert p.state() == before
    assert not any(row["input_id"] == data["observation_id"] for row in p.inputs())


def test_retries_and_id_content_conflicts_have_distinct_wire_results(producer):
    p = producer
    p.adopt()
    data = p.camera()
    receipt = p.send(data)
    before, trace = p.state(), p.trace()
    duplicate = p.send(data, expected=200)
    assert duplicate == {**receipt, "disposition": "DUPLICATE"}
    changed = deepcopy(data)
    changed["fields"]["HDG"].update(value=1, raw_text="1")
    assert p.send(changed, expected=409)["code"] == "ID_CONTENT_CONFLICT"
    assert p.state() == before
    assert p.trace() == trace


def test_cancelled_pilot_and_late_atc_results_cannot_change_current_context(producer):
    p = producer
    first, _ = p.adopt()
    pilot = p.segment(first)
    readback = p.speech(pilot)
    p.request("POST", p.path+f"/speech-segments/{pilot['segment_id']}/cancel", {"reason": "fixture_ptt_cancel"})
    p.send(readback)
    assert stored(p, readback)["reason"] == "ATTEMPT_CANCELLED"
    late_segment = p.segment()
    late_result = p.speech(late_segment)
    p.adopt("atc-partial.json")
    before = p.state()["targets"]
    p.send(late_result)
    assert stored(p, late_result)["reason"] == "ATC_INPUT_SUPERSEDED"
    assert p.state()["targets"] == before


def test_early_pilot_result_is_relinked_only_to_its_registered_atc(producer):
    p = producer
    atc = p.segment()
    pilot = p.segment(atc)
    readback = p.speech(pilot)
    p.send(readback)
    assert stored(p, readback)["reason"] == "ATC_NOT_ADOPTED"
    p.send(p.speech(atc))
    assert stored(p, readback)["applied"] is True
    assert p.state()["current"]["READBACK"]["ALT"]["segment_id"] == pilot["segment_id"]
    assert p.state()["result"] == "UNVERIFIED"


def test_second_run_and_other_flight_cannot_reuse_previous_evidence(producer, live_backend, tmp_path):
    p = producer
    p.adopt()
    data = p.camera()
    p.send(data)
    other = MockProducer(live_backend, tmp_path / "second-exchange.json")
    try:
        other.start()
        assert other.run_id != p.run_id
        assert other.flight_id != p.flight_id
        assert other.state()["targets"] == {"ALT": None, "HDG": None}
        assert other.inputs() == []
        assert other.send(data, expected=409)["code"] == "CONTEXT_MISMATCH"
        other.adopt()
        new = other.camera()
        other.send(new)
        assert new["observation_id"] != data["observation_id"]
        assert new["frame_id"] != data["frame_id"]
        assert [row["payload"] for row in p.inputs() if row["input_id"] == data["observation_id"]] == [data]
        records = json.loads(other.record_path.read_text())
        assert {row["run_id"] for row in records} == {other.run_id}
    finally:
        other.close()


def test_legacy_http_contract_and_ended_v2_flight_remain_distinct(producer):
    p = producer
    legacy = p.request("POST", "/api/flights/start", {}, expected=201)
    assert legacy["flight_id"] != p.flight_id
    p.adopt()
    p.request("POST", p.path+"/end")
    assert p.send(p.camera(), expected=409)["code"] == "FLIGHT_ENDED"
    assert p.state()["reason"] == "FLIGHT_ENDED"


@pytest.mark.parametrize("command,value,expected", [
    ("maintain FL040", 4000, "PASS"),
    ("maintain four thousand feet", 3000, "INVALID"),
    ("after departure maintain three thousand feet", 3000, "NEEDS_REVIEW"),
])
def test_server_rechecks_structure_independently_of_extractor_pass(producer, command, value, expected):
    p = producer
    data = p.speech(p.segment(), "atc-partial.json")
    data["transcript"] = "Radar one two three " + command
    data["fields"]["ALT"].update(value=value, raw_text=str(value))
    p.send(data)
    state = p.state()
    report = state["structure_checks"]["ATC"]
    validate("structure-result-v1", report)
    assert data["instruction_check"] == "PASS"
    assert report["result"] == expected
    assert report["observation_id"] == data["observation_id"]
    assert stored(p, data)["payload"] == data
    assert stored(p, data)["applied"] == (expected == "PASS")
    assert p.trace()[-1]["snapshot"]["structure_check"] == report
    assert state["result"] == "UNVERIFIED"
