"""SPEC-005-WI-03: independent JSON producer/public HTTP acceptance cases."""
from itertools import product

import pytest

from mock_producer import MockProducer, validate

MODES = ("NORMAL", "MISMATCH", "UNVERIFIED")


def establish_normal(p):
    atc, _ = p.adopt()
    p.send(p.speech(p.segment(atc)))
    data = p.camera()
    data["fields"]["HDG"].update(value=270, raw_text="270")
    p.send(data)
    assert p.state()["result"] == "NORMAL"
    return atc


@pytest.mark.parametrize("alt,hdg", list(product(MODES, repeat=2)))
def test_all_setting_outcomes_after_completion_over_http(producer, alt, hdg):
    p = producer
    atc = establish_normal(p)
    data = p.camera()
    for name, mode in (("ALT", alt), ("HDG", hdg)):
        value = {"ALT": 3000, "HDG": 270}[name]
        field = data["fields"][name]
        actual = value if mode == "NORMAL" else value-1
        field.update(value=actual, raw_text=str(actual))
        if mode == "UNVERIFIED":
            field.update(value=None, raw_text=None, validity="UNREADABLE", reason="fixture_unavailable")
    receipt = p.send(data)
    state = p.state()
    report = state["validation"]
    validate("validation-snapshot-v1", report)
    expected = "MISMATCH" if "MISMATCH" in (alt, hdg) else "UNVERIFIED" if "UNVERIFIED" in (alt, hdg) else "NORMAL"
    assert report["result"] == state["result"] == expected
    assert report["readback"]["result"] == "NORMAL"
    assert {field["field"]: field["result"] for field in report["setting"]["fields"]} == {"ALT": alt, "HDG": hdg}
    assert all(field["instruction_id"] == atc["instruction_id"] and field["observation_id"] == data["observation_id"]
        for field in report["setting"]["fields"])
    event = next(event for event in p.trace() if event["event_id"] == receipt["event_id"])
    assert event["snapshot"]["validation"] == report
    assert event["snapshot"]["payload"] == data


def test_readback_mismatch_quality_hold_and_camera_unreadable_coexist_over_http(producer):
    p = producer
    atc, _ = p.adopt()
    data = p.speech(p.segment(atc))
    data["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    data["fields"]["ALT"].update(value=4000, raw_text="4000")
    data["fields"]["HDG"]["quality"].update(input_quality="INSUFFICIENT", reason="fixture_overlap")
    p.send(data)
    p.send(p.camera("cockpit-unreadable.json"))
    report = p.state()["validation"]
    validate("validation-snapshot-v1", report)
    fields = {field["field"]: field for field in report["readback"]["fields"]}
    assert fields["ALT"]["result"] == "MISMATCH"
    assert fields["HDG"]["result"] == "UNVERIFIED"
    assert report["representative_stage"] == "READBACK"
    assert report["setting"]["result"] == "UNVERIFIED"
    assert all(field["stage"] == "READBACK" for field in report["advisory_candidates"])


def test_new_run_cannot_inherit_another_flights_completed_validation(producer, live_backend, tmp_path):
    p = producer
    establish_normal(p)
    another = MockProducer(live_backend, tmp_path / "second-exchange.json")
    try:
        another.start()
        assert another.run_id != p.run_id and another.flight_id != p.flight_id
        initial = another.state()
        assert initial["result"] == "UNVERIFIED" and initial["validation"]["phase"] == "WAITING_ATC"
        assert another.inputs() == []
        stolen = p.camera()
        assert another.send(stolen, expected=409)["code"] == "CONTEXT_MISMATCH"
        assert another.state() == initial
        assert p.state()["result"] == "NORMAL"
    finally:
        another.close()
