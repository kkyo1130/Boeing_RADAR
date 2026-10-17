"""SPEC-005 AC-01..03: known NORMAL control followed by uncertain input."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "contracts/examples/validation-safety-cases.json").read_text())
PARAMS = [(source, case) for case in CASES for source in case.get("sources", ["ATC", "READBACK", "COCKPIT"])]


def activate(producer):
    body = {"confirmed": True, "confirmed_by": "fixture-reviewer",
            "rule_policy": json.loads((ROOT / "contracts/rule-policy-demo.json").read_text()),
            "minimum_model_score": 0.5, "atc_context": {"expected_callsign": "RADAR1",
                "expected_conditions": [], "expected_ordered_actions": ["altitude 3000 feet", "heading 270 degrees"]}}
    response = producer.client.post(f"/api/v1/clearances/{producer.clearance_id}/validation-settings", json=body)
    assert response.status_code == 201, response.text
    originals = {}
    for source in ("ATC", "READBACK", "COCKPIT"):
        originals[source] = producer.build("normal", source)
        response = producer.send(originals[source])
        assert response.status_code == 200 and response.json()["accepted"]
    assert producer.state()["verdict"] == "NORMAL"
    assert producer.state()["status"] == "VERIFIED"
    return originals


def mutate(body, case, old):
    field = body["fields"]["altitude"]
    if case == "unreadable":
        field.update(value=None, reason="no_text")
    elif case == "zero_score":
        field["model_score"] = 0.0
    elif case == "missing_score":
        field["model_score"] = None
    elif case == "degraded_quality":
        field["quality"] = {"status": "degraded", "reasons": ["occluded"]}
    elif case == "unknown_quality":
        field["quality"] = {"status": "unknown", "reasons": ["quality_not_measured"]}
    elif case == "missing_evidence":
        field["evidence_ids"] = []
    elif case == "raw_conflict":
        field["raw_text"] = "3500"
    elif case == "missing_raw":
        field["raw_text"] = None
    elif case == "callsign":
        body["speech"]["callsign"] = "OTHER1"
    elif case == "conditions":
        body["speech"]["conditions"] = ["after passing ABC"]
    elif case == "order":
        body["speech"]["ordered_actions"].reverse()
    elif case == "unknown_time":
        body.update(captured_at=None, capture_time_basis="unknown")
    elif case == "stale":
        body["captured_at"] = "2026-10-12T00:00:00Z"
    elif case == "future_processing":
        body["processed_at"] = (datetime.fromisoformat(body["processed_at"]) + timedelta(days=1)).isoformat()
    elif case == "reverse_time":
        body.update(captured_at=old["captured_at"], processed_at=old["processed_at"])
    elif case == "policy_upper":
        field.update(value=70000, raw_text="70000")
    elif case == "degraded_channel":
        body["health"] = {"status": "degraded", "reason": "channel_degraded"}
    else:
        raise AssertionError(f"Unknown fixture: {case}")


@pytest.mark.parametrize("source,case", PARAMS, ids=[f"{s}-{c['case']}" for s, c in PARAMS])
def test_uncertainty_cannot_preserve_a_previous_verified_result(producer, source, case):
    originals = activate(producer)
    body = producer.build("normal", source)
    body.update(intent="correction", supersedes_observation_id=originals[source]["observation_id"])
    mutate(body, case["case"], originals[source])
    sent = deepcopy(body)
    response = producer.send(body)
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is case.get("accepted", True)
    result = producer.state()
    assert result["verdict"] == "UNVERIFIED" and result["status"] == "UNVERIFIED"
    assert case["reason"] in result["reasons"]
    assert result["errors"] == [] and result["resolutions"] == {}
    events = producer.events()
    event = next(e for e in events if e["event_id"] == sent["event_id"])
    assert event["payload"]["fields"] == sent["fields"]
    assert event["payload"]["observation_id"] == sent["observation_id"]
    assert result["validation_context"]["settings"]["confirmed_by"] == "fixture-reviewer"


@pytest.mark.parametrize("source", ["ATC", "READBACK", "COCKPIT"])
def test_recovery_health_never_reuses_pre_fault_values(producer, source):
    originals = activate(producer)
    health = producer.build("health", source)
    assert producer.send(health).json()["accepted"]
    assert producer.state()["status"] == "UNVERIFIED"
    recovered = producer.build("health", source)
    recovered["health"] = {"status": "available", "reason": None}
    assert producer.send(recovered).json()["accepted"]
    assert producer.state()["status"] == "UNVERIFIED"
    assert "new_observation_required" in producer.state()["reasons"]
    new = producer.build("normal", source)
    new.update(intent="correction", supersedes_observation_id=originals[source]["observation_id"])
    assert producer.send(new).json()["accepted"]
    if source == "ATC":
        for dependent in ("READBACK", "COCKPIT"):
            assert producer.send(producer.build("normal", dependent)).json()["accepted"]
    assert producer.state()["status"] == "VERIFIED"


def test_confirmed_error_remains_visible_with_other_channel_uncertainty(producer):
    originals = activate(producer)
    readback = producer.build("normal", "READBACK")
    readback.update(intent="correction", supersedes_observation_id=originals["READBACK"]["observation_id"])
    readback["fields"]["heading"].update(value=290, raw_text="290")
    readback["speech"]["ordered_actions"] = ["altitude 3000 feet", "heading 290 degrees"]
    assert producer.send(readback).json()["accepted"]
    health = producer.build("health", "COCKPIT")
    assert producer.send(health).json()["accepted"]
    result = producer.state()
    assert result["verdict"] == "MISMATCH" and result["status"] == "READBACK_ERROR"
    assert result["errors"] == [{"field": "HDG", "expected": 270, "actual": 290}]
    assert result["stages"]["cockpit"]["verdict"] == "UNVERIFIED"
    assert "camera_disconnected" in result["stages"]["cockpit"]["reasons"]
