"""Public HTTP occurrence contract with independent JSON producers."""
from mock_producer import validate
from test_validation_regression_http import establish_normal


def camera(p, altitude=3000, heading=270):
    data = p.camera()
    for name, value in (("ALT", altitude), ("HDG", heading)):
        data["fields"][name].update(value=value, raw_text=str(value))
    p.send(data)
    return data


def rows(p):
    result = p.state()["incidents"]
    for item in result:
        validate("incident-v1", item)
    return result


def test_new_frame_resolves_then_new_occurrence_recurs(producer):
    p = producer; establish_normal(p)
    failed = camera(p, heading=90)
    incident = rows(p)[0]
    assert incident["status"] == "OPEN"
    assert incident["latest_evidence"]["frame_id"] == failed["frame_id"]
    fixed = camera(p)
    resolved = rows(p)[0]
    assert resolved["status"] == "RESOLVED" and resolved["resolved_at"]
    assert resolved["resolution_evidence"]["observation_id"] == fixed["observation_id"]
    camera(p, heading=90)
    all_rows = rows(p)
    assert [item["status"] for item in all_rows] == ["RESOLVED", "OPEN"]
    assert all_rows[1]["occurrence_id"] != incident["occurrence_id"]
    assert len([event for event in p.trace() if event["event_type"] == "INCIDENT_UPDATED"]) == 3


def test_same_frame_new_id_and_health_recovery_cannot_resolve(producer):
    p = producer; establish_normal(p)
    old = camera(p, altitude=2000)
    correction = p.camera()
    correction["frame_id"] = old["frame_id"]
    correction["fields"]["HDG"].update(value=270, raw_text="270")
    p.send(correction)
    assert p.inputs()[0]["reason"] == "SOURCE_SAMPLE_REUSED"
    assert rows(p)[0]["status"] == "OPEN"
    p.health("DISCONNECTED"); p.health("AVAILABLE")
    assert rows(p)[0]["status"] == "OPEN"
    camera(p)
    assert rows(p)[0]["status"] == "RESOLVED"


def test_partial_altitude_replacement_keeps_heading_history(producer):
    p = producer; a = establish_normal(p)
    camera(p, altitude=2000, heading=90)
    before = {row["field"]: row for row in rows(p)}
    b, _ = p.adopt("atc-partial.json")
    after = {row["field"]: row for row in rows(p)}
    assert after["ALT"]["status"] == "SUPERSEDED" and after["ALT"]["resolved_at"] is None
    assert after["HDG"]["status"] == "OPEN"
    assert after["HDG"]["occurrence_id"] == before["HDG"]["occurrence_id"]
    assert after["HDG"]["instruction_id"] == a["instruction_id"]
    p.send(p.speech(p.segment(b), "atc-partial.json"))
    camera(p, altitude=4000, heading=90)
    assert len(rows(p)) == 2 and rows(p)[1]["status"] == "OPEN"


def test_readback_correction_does_not_claim_global_completion(producer):
    p = producer; atc, _ = p.adopt()
    data = p.speech(p.segment(atc))
    data["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    data["fields"]["ALT"].update(value=4000, raw_text="4000")
    p.send(data)
    original = rows(p)[0]
    p.send(p.speech(p.segment(atc)))
    corrected = rows(p)[0]
    assert corrected["occurrence_id"] == original["occurrence_id"]
    assert corrected["status"] == "RESOLVED"
    assert p.state()["result"] == "UNVERIFIED"


def test_end_keeps_unresolved_and_explicit_revalidate_is_versioned(producer):
    p = producer; establish_normal(p); camera(p, altitude=2000)
    p.request("POST", p.path+"/revalidate")
    assert len(rows(p)) == 1
    p.request("POST", p.path+"/end")
    assert rows(p)[0]["status"] == "ENDED_UNRESOLVED"
    assert rows(p)[0]["resolved_at"] is None
    assert p.request("POST", p.path+"/revalidate", expected=409)["code"] == "FLIGHT_ENDED"
