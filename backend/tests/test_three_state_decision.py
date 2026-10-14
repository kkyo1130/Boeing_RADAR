from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from app.db import Base, make_engine
from app.migrate_contract_storage import upgrade
from app.models.flight import Flight
from app.models.contract_observation import ContractClearance
from app.services import contract_service

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / "contracts/rule-policy-demo.json").read_text())


@pytest.fixture
def rig(client, monkeypatch):
    clock = [datetime(2026, 10, 14, tzinfo=timezone.utc)]
    monkeypatch.setattr(contract_service, "utc_now", lambda: clock[0])
    monkeypatch.setenv("RADAR_OBSERVATION_MAX_AGE_SECONDS", "30")
    flight = client.post("/api/flights/start").json()["flight_id"]
    c = client.post(f"/api/v1/flights/{flight}/clearances").json()["clearance_id"]
    return client, clock, flight, c


def settings(rig, actions=None):
    client, _, _, c = rig
    data = {"confirmed": True, "confirmed_by": "fixture-operator", "rule_policy": POLICY,
            "minimum_model_score": 0.5, "atc_context": {"expected_callsign": "RADAR1",
            "expected_conditions": [], "expected_ordered_actions": actions if actions is not None else []}}
    response = client.post(f"/api/v1/clearances/{c}/validation-settings", json=data)
    assert response.status_code == 201, response.text
    return data


def data(rig, source, altitude=3000, heading=270, previous=None):
    _, clock, flight, c = rig
    clock[0] += timedelta(seconds=1)
    body = json.loads((ROOT / "contracts/examples/observation-v1/normal.json").read_text())
    token = str(uuid4())
    body.update(flight_id=flight, clearance_id=c, source=source, channel_id=source,
                event_id="event-"+token, observation_id="obs-"+token, sample_id="frame-"+token,
                captured_at=clock[0].isoformat(), processed_at=clock[0].isoformat())
    body["fields"]["altitude"].update(value=altitude, raw_text=str(altitude))
    body["fields"]["heading"].update(value=heading, raw_text=str(heading))
    if source != "COCKPIT":
        body["speech"] = {"transcript": "labelled test", "callsign": "RADAR1", "callsign_reason": None,
                          "role_basis": "labelled_fixture", "conditions": [], "ordered_actions": []}
        body["evidence"][0]["kind"] = "audio"
    if previous:
        body.update(intent="correction", supersedes_observation_id=previous["observation_id"])
    return body


def send(rig, body):
    response = rig[0].post("/api/v1/observations", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def state(rig):
    response = rig[0].get(f"/api/v1/clearances/{rig[3]}")
    assert response.status_code == 200, response.text
    return response.json()


def normal(rig):
    values = {}
    for source in ("ATC", "READBACK", "COCKPIT"):
        values[source] = data(rig, source)
        assert send(rig, values[source])["accepted"]
    return values


def test_full_normal_and_missing_context(rig):
    normal(rig)
    assert state(rig)["verdict"] == "UNVERIFIED"
    assert "validation_context_missing" in state(rig)["reasons"]


def test_verified_requires_all_stages_and_freshness(rig):
    settings(rig)
    normal(rig)
    result = state(rig)
    assert (result["verdict"], result["status"]) == ("NORMAL", "VERIFIED")
    assert all(s["verdict"] == "NORMAL" for s in result["stages"].values())
    assert result["errors"] == [] and result["reasons"] == []
    assert result["validation_context"]["settings"]["confirmed_by"] == "fixture-operator"
    rig[1][0] += timedelta(seconds=31)
    assert state(rig)["status"] == "UNVERIFIED"
    assert "stale_observation" in state(rig)["reasons"]


@pytest.mark.parametrize("source,status", [("READBACK", "READBACK_ERROR"), ("COCKPIT", "SETTING_ERROR")])
def test_numeric_mismatch_and_fresh_correction(rig, source, status):
    settings(rig)
    send(rig, data(rig, "ATC"))
    if source == "COCKPIT":
        send(rig, data(rig, "READBACK"))
    bad = data(rig, source, altitude=3500)
    send(rig, bad)
    result = state(rig)
    assert result["status"] == status and result["verdict"] == "MISMATCH"
    assert result["errors"] == [{"field": "ALT", "expected": 3000, "actual": 3500}]
    correction = data(rig, source, previous=bad)
    send(rig, correction)
    result = state(rig)
    assert result["status"] == "RESOLVED"
    assert result["resolutions"][source.lower()] == "RESOLVED"
    if source == "READBACK":
        assert result["verdict"] == "UNVERIFIED"
        assert result["stages"]["cockpit"]["verdict"] == "UNVERIFIED"
        send(rig, data(rig, "COCKPIT"))
        assert state(rig)["verdict"] == "NORMAL"
    else:
        assert result["verdict"] == "NORMAL"


def test_confirmed_readback_mismatch_precedes_unreadable_cockpit(rig):
    settings(rig)
    send(rig, data(rig, "ATC"))
    send(rig, data(rig, "READBACK", heading=290))
    cockpit = data(rig, "COCKPIT")
    cockpit["fields"]["altitude"].update(value=None, raw_text=None, reason="blank_roi")
    send(rig, cockpit)
    result = state(rig)
    assert result["status"] == "READBACK_ERROR"
    assert result["stages"]["cockpit"]["verdict"] == "UNVERIFIED"
    assert "blank_roi" in result["stages"]["cockpit"]["reasons"]


@pytest.mark.parametrize("case,reason", [("null", "blank_roi"), ("score", "low_or_missing_model_score"),
    ("quality", "occluded"), ("raw", "raw_value_conflict"), ("callsign", "callsign_conflict"),
    ("conditions", "conditions_conflict"), ("evidence", "evidence_unavailable")])
def test_unusable_readback_does_not_become_setting_or_readback_error(rig, case, reason):
    settings(rig)
    send(rig, data(rig, "ATC"))
    readback = data(rig, "READBACK")
    if case == "null":
        readback["fields"]["altitude"].update(value=None, reason="blank_roi")
    elif case == "score":
        readback["fields"]["altitude"]["model_score"] = 0.0
    elif case == "quality":
        readback["fields"]["altitude"]["quality"] = {"status": "degraded", "reasons": ["occluded"]}
    elif case == "raw":
        readback["fields"]["altitude"]["raw_text"] = "3500"
    elif case == "callsign":
        readback["speech"]["callsign"] = "RADAR2"
    elif case == "conditions":
        readback["speech"]["conditions"] = ["after ABC"]
    else:
        readback["evidence"][0]["availability"] = "missing"
    send(rig, readback)
    send(rig, data(rig, "COCKPIT", altitude=3500))
    result = state(rig)
    assert result["status"] == "UNVERIFIED" and result["errors"] == []
    assert reason in result["reasons"]


def test_partial_heading_zero(rig):
    settings(rig)
    for source in ("ATC", "READBACK", "COCKPIT"):
        body = data(rig, source, heading=0)
        body["fields"]["altitude"] = None
        send(rig, body)
    assert state(rig)["status"] == "VERIFIED"
    assert "missing_altitude" not in state(rig)["reasons"]


def test_health_recovery_requires_a_new_frame(rig):
    settings(rig)
    old = normal(rig)
    health = data(rig, "COCKPIT")
    health.update(event_type="health", observation_id=None, sample_id=None, fields=None, intent=None,
                  supersedes_observation_id=None, captured_at=None, capture_time_basis="unknown", evidence=[],
                  health={"status": "unavailable", "reason": "camera_disconnected"})
    send(rig, health)
    assert state(rig)["status"] == "UNVERIFIED"
    rig[1][0] += timedelta(seconds=1)
    recovered = deepcopy(health)
    recovered.update(event_id="recovery", processed_at=rig[1][0].isoformat(), health={"status": "available", "reason": None})
    send(rig, recovered)
    assert state(rig)["status"] == "UNVERIFIED"
    assert "new_observation_required" in state(rig)["reasons"]
    send(rig, data(rig, "COCKPIT", previous=old["COCKPIT"]))
    assert state(rig)["status"] == "VERIFIED"


def test_rejected_stale_correction_cannot_keep_old_verified_badge(rig):
    settings(rig)
    old = normal(rig)
    stale = data(rig, "COCKPIT", previous=old["COCKPIT"])
    stale["captured_at"] = "2026-10-13T00:00:00Z"
    assert not send(rig, stale)["accepted"]
    assert state(rig)["status"] == "UNVERIFIED"
    assert "stale_observation" in state(rig)["reasons"]
    send(rig, data(rig, "COCKPIT", previous=old["COCKPIT"]))
    assert state(rig)["status"] == "VERIFIED"


def test_context_is_explicit_immutable_and_not_reused_on_new_instruction(rig):
    body = settings(rig)
    client, _, flight, c = rig
    assert client.post(f"/api/v1/clearances/{c}/validation-settings", json=body).status_code == 409
    normal(rig)
    new = client.post(f"/api/v1/flights/{flight}/clearances").json()
    assert new["status"] == "UNVERIFIED" and new["observations"] == {}
    assert state(rig)["status"] == "UNVERIFIED"


def test_canonical_action_order_does_not_hide_numeric_mismatch(rig):
    settings(rig, actions=["altitude 3000 feet", "heading 270 degrees"])
    a = data(rig, "ATC")
    a["speech"]["ordered_actions"] = ["altitude 3000 feet", "heading 270 degrees"]
    send(rig, a)
    r = data(rig, "READBACK", heading=290)
    r["speech"]["ordered_actions"] = ["altitude 3000 feet", "heading 290 degrees"]
    send(rig, r)
    assert state(rig)["status"] == "READBACK_ERROR"
    reversed_order = data(rig, "READBACK", previous=r)
    reversed_order["speech"]["ordered_actions"] = ["heading 270 degrees", "altitude 3000 feet"]
    send(rig, reversed_order)
    assert state(rig)["status"] == "UNVERIFIED"
    assert "ordered_actions_conflict" in state(rig)["reasons"]


def test_existing_v1_clearance_survives_settings_migration(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'old-v1.db'}")
    Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t.name != "contract_validation_settings"])
    with Session(engine) as db:
        db.add(Flight(flight_id="old", started_at="2026-10-14T00:00:00Z", status="ACTIVE"))
        db.flush()
        db.add(ContractClearance(clearance_id="old-c", flight_id="old", active=True,
                                 created_at="2026-10-14T00:00:00Z", latest={}))
        db.commit()
    upgrade(engine)
    upgrade(engine)
    assert "contract_validation_settings" in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(ContractClearance, "old-c").latest == {}
        assert db.scalar(select(Flight).where(Flight.flight_id == "old")).status == "ACTIVE"
    engine.dispose()


def test_known_readback_error_with_other_field_unreadable(rig):
    settings(rig)
    send(rig, data(rig, "ATC"))
    r = data(rig, "READBACK", heading=290)
    r["fields"]["altitude"].update(value=None, reason="no_text")
    send(rig, r)
    result = state(rig)
    assert result["status"] == "READBACK_ERROR"
    assert result["errors"] == [{"field": "HDG", "expected": 270, "actual": 290}]
    assert "no_text" in result["stages"]["readback"]["reasons"]


@pytest.mark.parametrize("case", ["false", "late", "invalid_policy"])
def test_settings_cannot_silently_enable_pass(rig, case):
    client, _, _, c = rig
    body = {"confirmed": True, "confirmed_by": "fixture-operator", "rule_policy": deepcopy(POLICY),
            "minimum_model_score": 0.5, "atc_context": {"expected_callsign": "RADAR1",
             "expected_conditions": [], "expected_ordered_actions": []}}
    if case == "false":
        body["confirmed"] = False
    elif case == "invalid_policy":
        body["rule_policy"]["max_altitude_feet"] = 0
    else:
        send(rig, data(rig, "ATC"))
    response = client.post(f"/api/v1/clearances/{c}/validation-settings", json=body)
    assert response.status_code == (409 if case == "late" else 422)
    assert state(rig)["status"] == "UNVERIFIED"


def test_clock_unknown_correction_and_rapid_change_do_not_resolve(rig):
    settings(rig)
    old = normal(rig)
    unknown = data(rig, "COCKPIT", previous=old["COCKPIT"])
    unknown.update(captured_at=None, capture_time_basis="unknown")
    assert not send(rig, unknown)["accepted"]
    assert state(rig)["status"] == "UNVERIFIED"
    jump = data(rig, "COCKPIT", altitude=15000, previous=old["COCKPIT"])
    assert send(rig, jump)["accepted"]
    result = state(rig)
    assert result["status"] == "UNVERIFIED" and not result["resolutions"]
    assert "rapid_change" in result["reasons"]


def test_ended_session_cannot_remain_verified(rig):
    settings(rig)
    normal(rig)
    rig[0].post(f"/api/flights/{rig[2]}/end")
    assert state(rig)["status"] == "UNVERIFIED"
    assert "flight_ended" in state(rig)["reasons"]


def test_uncertain_intermediate_correction_does_not_erase_error_resolution(rig):
    settings(rig)
    send(rig, data(rig, "ATC"))
    bad = data(rig, "READBACK", altitude=3500)
    send(rig, bad)
    assert state(rig)["status"] == "READBACK_ERROR"
    uncertain = data(rig, "READBACK", previous=bad)
    uncertain["fields"]["altitude"]["model_score"] = 0.0
    send(rig, uncertain)
    assert state(rig)["status"] == "UNVERIFIED"
    send(rig, data(rig, "READBACK", previous=uncertain))
    assert state(rig)["status"] == "RESOLVED"
    assert state(rig)["verdict"] == "UNVERIFIED"  # Cockpit still missing.


def test_readback_error_then_remaining_setting_error(rig):
    settings(rig)
    send(rig, data(rig, "ATC"))
    readback = data(rig, "READBACK", heading=290)
    cockpit = data(rig, "COCKPIT", altitude=3500)
    send(rig, readback)
    send(rig, cockpit)
    assert state(rig)["status"] == "READBACK_ERROR"
    send(rig, data(rig, "READBACK", previous=readback))
    assert state(rig)["status"] == "SETTING_ERROR"
    send(rig, data(rig, "COCKPIT", previous=cockpit))
    assert state(rig)["status"] == "RESOLVED" and state(rig)["verdict"] == "NORMAL"


@pytest.mark.parametrize("score,status", [(0.5, "VERIFIED"), (0.499, "UNVERIFIED")])
def test_model_score_policy_boundary(rig, score, status):
    settings(rig)
    send(rig, data(rig, "ATC"))
    send(rig, data(rig, "READBACK"))
    cockpit = data(rig, "COCKPIT")
    cockpit["fields"]["altitude"]["model_score"] = score
    send(rig, cockpit)
    assert state(rig)["status"] == status
