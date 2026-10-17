from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import Base, make_engine
from app.migrate_contract_storage import upgrade
from app.models.flight import Flight
from app.models.contract_observation import ContractClearance, ContractEvent
from app.services import contract_service as service


@pytest.fixture
def clock(monkeypatch):
    value = [datetime(2026, 10, 13, tzinfo=timezone.utc)]
    monkeypatch.setattr(service, "utc_now", lambda: value[0])
    monkeypatch.setenv("RADAR_OBSERVATION_MAX_AGE_SECONDS", "30")
    return value


def setup(client):
    f = client.post("/api/flights/start").json()["flight_id"]
    response = client.post(f"/api/v1/flights/{f}/clearances")
    assert response.status_code == 201, response.text
    return f, response.json()["clearance_id"]


def payload(f, c, clock, source="ATC", name="normal"):
    clock[0] += timedelta(seconds=1)
    p = json.loads((Path(__file__).resolve().parents[2] /
                   f"contracts/examples/observation-v1/{name}.json").read_text())
    token = str(uuid4())
    p.update(flight_id=f, clearance_id=c, source=source, channel_id=source,
             event_id=f"evt-{token}", observation_id=f"obs-{token}", sample_id=f"sample-{token}",
             captured_at=clock[0].isoformat(), processed_at=clock[0].isoformat())
    if source != "COCKPIT":
        p["speech"] = dict(transcript="fixture", callsign="RADAR1", callsign_reason=None,
                           role_basis="labelled_fixture", conditions=[], ordered_actions=[])
        p["evidence"][0]["kind"] = "audio"
    return p


def send(client, p):
    response = client.post("/api/v1/observations", json=p)
    assert response.status_code == 200, response.text
    return response.json()


def state(client, c):
    r = client.get(f"/api/v1/clearances/{c}")
    assert r.status_code == 200, r.text
    return r.json()


def test_partial_unreadable_correction_and_receipt_log(client, clock):
    f, c = setup(client)
    a = payload(f, c, clock, name="partial-atc")
    assert send(client, a)["accepted"]
    r = payload(f, c, clock, "READBACK", "partial-atc")
    assert send(client, r)["accepted"]
    v = payload(f, c, clock, "COCKPIT", "unreadable")
    assert send(client, v)["accepted"]
    result = state(client, c)
    assert result["status"] == "UNVERIFIED"
    assert "blank_roi" in result["reasons"]
    assert result["observations"]["ATC"]["fields"]["heading"]["value"] == 0
    correction = payload(f, c, clock, "COCKPIT")
    correction.update(intent="correction", supersedes_observation_id=v["observation_id"])
    assert send(client, correction)["accepted"]
    assert state(client, c)["observations"]["COCKPIT"]["observation_id"] == correction["observation_id"]
    events = client.get(f"/api/v1/flights/{f}/observation-events").json()
    assert len(events) == 4
    assert events[2]["payload"]["fields"]["altitude"]["value"] is None
    assert state(client, c)["status"] not in ("VERIFIED", "RESOLVED")


@pytest.mark.parametrize("case,reason", [
    ("stale", "stale_observation"), ("unknown", "capture_time_unknown"),
    ("future", "future_capture"), ("before", "before_clearance")])
def test_timestamp_rejections_preserve_receipt(client, clock, case, reason):
    f, c = setup(client)
    p = payload(f, c, clock)
    if case == "stale":
        clock[0] += timedelta(seconds=31)
    elif case == "unknown":
        p.update(captured_at=None, capture_time_basis="unknown")
    elif case == "future":
        p["captured_at"] = p["processed_at"] = (clock[0] + timedelta(seconds=1)).isoformat()
    else:
        p["captured_at"] = (clock[0] - timedelta(seconds=2)).isoformat()
    receipt = send(client, p)
    assert not receipt["accepted"] and reason in receipt["reasons"]
    assert state(client, c)["observations"] == {}
    assert len(client.get(f"/api/v1/flights/{f}/observation-events").json()) == 1


def test_duplicate_retry_conflict_and_sample_reuse(client, clock):
    f, c = setup(client)
    p = payload(f, c, clock)
    assert not send(client, p)["replayed"]
    assert send(client, p)["replayed"]
    altered = deepcopy(p)
    altered["fields"]["heading"]["value"] = 280
    assert client.post("/api/v1/observations", json=altered).status_code == 409
    reused = payload(f, c, clock)
    reused.update(sample_id=p["sample_id"], intent="correction", supersedes_observation_id=p["observation_id"])
    assert client.post("/api/v1/observations", json=reused).status_code == 409
    assert len(client.get(f"/api/v1/flights/{f}/observation-events").json()) == 1


def test_reverse_and_old_correction_cannot_replace_latest(client, clock):
    f, c = setup(client)
    p = payload(f, c, clock)
    send(client, p)
    reverse = payload(f, c, clock)
    reverse.update(intent="correction", supersedes_observation_id=p["observation_id"],
                   captured_at=p["captured_at"], processed_at=p["processed_at"])
    r = send(client, reverse)
    assert not r["accepted"]
    assert {"out_of_order", "correction_not_newer"}.issubset(r["reasons"])
    assert state(client, c)["observations"]["ATC"]["observation_id"] == p["observation_id"]
    newer = payload(f, c, clock)
    newer.update(intent="correction", supersedes_observation_id=p["observation_id"])
    assert send(client, newer)["accepted"]
    outdated = payload(f, c, clock)
    outdated.update(intent="correction", supersedes_observation_id=p["observation_id"])
    assert client.post("/api/v1/observations", json=outdated).status_code == 409


def test_isolation_supersession_and_ended_flight(client, clock):
    f, c = setup(client)
    other_f, other_c = setup(client)
    wrong = payload(other_f, c, clock)
    assert client.post("/api/v1/observations", json=wrong).status_code == 409
    missing = payload(f, "absent", clock)
    assert client.post("/api/v1/observations", json=missing).status_code == 404
    newest = client.post(f"/api/v1/flights/{f}/clearances").json()["clearance_id"]
    assert client.post("/api/v1/observations", json=payload(f, c, clock)).status_code == 409
    assert not state(client, c)["active"]
    assert state(client, newest)["observations"] == {}
    client.post(f"/api/flights/{other_f}/end")
    assert client.post("/api/v1/observations", json=payload(other_f, other_c, clock)).status_code == 409
    assert client.post(f"/api/v1/flights/{other_f}/clearances").status_code == 409


def test_health_and_age_are_visible_without_reusing_a_frame(client, clock):
    f, c = setup(client)
    for source in ("ATC", "READBACK", "COCKPIT"):
        assert send(client, payload(f, c, clock, source))["accepted"]
    h = payload(f, c, clock, "COCKPIT", "health")
    h.update(event_type="health", observation_id=None, sample_id=None,
             captured_at=None, capture_time_basis="unknown", intent=None,
             fields=None, evidence=[])
    assert send(client, h)["accepted"]
    assert "camera_disconnected" in state(client, c)["reasons"]
    clock[0] += timedelta(seconds=31)
    assert "stale_observation" in state(client, c)["reasons"]
    assert state(client, c)["status"] == "UNVERIFIED"


def test_future_rejected_event_does_not_poison_channel_watermark(client, clock):
    f, c = setup(client)
    future = payload(f, c, clock)
    future["captured_at"] = future["processed_at"] = (clock[0] + timedelta(days=1)).isoformat()
    assert not send(client, future)["accepted"]
    assert send(client, payload(f, c, clock))["accepted"]


def test_order_and_atc_correction_clear_dependent_inputs(client, clock):
    f, c = setup(client)
    assert client.post("/api/v1/observations", json=payload(f, c, clock, "READBACK")).status_code == 409
    a = payload(f, c, clock)
    send(client, a)
    assert client.post("/api/v1/observations", json=payload(f, c, clock, "COCKPIT")).status_code == 409
    send(client, payload(f, c, clock, "READBACK"))
    update = payload(f, c, clock)
    update.update(intent="correction", supersedes_observation_id=a["observation_id"])
    send(client, update)
    assert set(state(client, c)["observations"]) == {"ATC"}


def test_additive_migration_preserves_legacy_data(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    tables = [t for t in Base.metadata.sorted_tables if t.name not in (
        "contract_clearances", "contract_events", "contract_validation_settings")]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        db.add(Flight(flight_id="old", started_at="2026-10-13T00:00:00Z", status="ACTIVE"))
        db.commit()
    upgrade(engine)
    upgrade(engine)
    assert {"contract_clearances", "contract_events", "contract_validation_settings"}.issubset(inspect(engine).get_table_names())
    with Session(engine) as db:
        assert db.scalar(select(Flight)).flight_id == "old"
        assert db.scalar(select(ContractEvent)) is None
        assert db.scalar(select(ContractClearance)) is None
    engine.dispose()


@pytest.mark.parametrize("age,accepted", [(30, True), (30.001, False)])
def test_freshness_boundary(client, clock, age, accepted):
    f, c = setup(client)
    p = payload(f, c, clock)
    clock[0] += timedelta(seconds=age)
    assert send(client, p)["accepted"] is accepted


def test_simultaneous_duplicate_has_one_receipt(client, clock):
    f, c = setup(client)
    p = payload(f, c, clock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(client, p), range(2)))
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert len(client.get(f"/api/v1/flights/{f}/observation-events").json()) == 1


def test_failed_commit_rolls_back_latest_and_log(client, clock, monkeypatch):
    f, c = setup(client)
    p = payload(f, c, clock)
    def failed_commit(self):
        raise IntegrityError("injected commit failure", {}, Exception("test"))
    monkeypatch.setattr(Session, "commit", failed_commit)
    assert client.post("/api/v1/observations", json=p).status_code == 409
    assert state(client, c)["observations"] == {}
    assert client.get(f"/api/v1/flights/{f}/observation-events").json() == []
