from copy import deepcopy
from datetime import datetime

import pytest


def temporal_meaning(data):
    result = deepcopy(data)
    for key in ("captured_at", "processed_at"):
        if result[key] is not None:
            result[key] = datetime.fromisoformat(result[key].replace("Z", "+00:00"))
    return result


def accepted(producer, data):
    response = producer.send(data)
    assert response.status_code == 200, response.text
    assert response.json()["accepted"], response.text


@pytest.mark.parametrize("name,source", [
    ("normal", "ATC"), ("normal", "READBACK"), ("normal", "COCKPIT"),
    ("partial-atc", "ATC"), ("unreadable", "COCKPIT")])
def test_fixture_meaning_survives_wire_storage_and_query(producer, name, source):
    for prerequisite in ("ATC", "READBACK"):
        if prerequisite == source:
            break
        accepted(producer, producer.build("normal", prerequisite))
    data = producer.build(name, source)
    accepted(producer, data)
    stored = producer.state()["observations"][source]
    assert stored["schema_version"] == "radar-observation/1"
    assert stored["fields"] == data["fields"]
    assert stored["evidence"] == data["evidence"]
    assert temporal_meaning(stored)["captured_at"] == temporal_meaning(data)["captured_at"]
    assert stored["source"] == source
    assert temporal_meaning(producer.events()[-1]["payload"]) == temporal_meaning(data)
    if name == "partial-atc":
        assert stored["fields"]["altitude"] is None
        assert stored["fields"]["heading"]["value"] == 0
    if name == "unreadable":
        assert stored["fields"]["altitude"]["value"] is None
        assert "blank_roi" in producer.state()["reasons"]
    assert producer.state()["status"] == "UNVERIFIED"


def test_unknown_time_preserved_without_becoming_latest(producer):
    data = producer.build("unknown-time", "ATC")
    response = producer.send(data)
    assert response.status_code == 200
    assert not response.json()["accepted"]
    assert "capture_time_unknown" in response.json()["reasons"]
    assert producer.events()[-1]["payload"]["captured_at"] is None
    assert producer.state()["observations"] == {}


def test_health_does_not_fabricate_observation_or_resolution(producer):
    for source in ("ATC", "READBACK", "COCKPIT"):
        accepted(producer, producer.build("normal", source))
    previous = producer.state()["observations"]
    health = producer.build("health", "COCKPIT")
    accepted(producer, health)
    state = producer.state()
    assert state["observations"] == previous
    assert "camera_disconnected" in state["reasons"]
    event = producer.events()[-1]["payload"]
    assert event["fields"] is None and event["sample_id"] is None and event["evidence"] == []
    assert state["status"] == "UNVERIFIED"


def test_new_sample_correction_and_exact_retry(producer):
    for source in ("ATC", "READBACK"):
        accepted(producer, producer.build("normal", source))
    old = producer.build("unreadable", "COCKPIT")
    accepted(producer, old)
    correction = producer.build("correction", "COCKPIT", supersedes=old["observation_id"])
    assert correction["sample_id"] != old["sample_id"]
    accepted(producer, correction)
    assert producer.send(correction).json()["replayed"]
    assert len(producer.events()) == 4
    assert producer.events()[-2]["payload"]["fields"]["altitude"]["value"] is None
    assert temporal_meaning(producer.state()["observations"]["COCKPIT"]) == temporal_meaning(correction)
    assert producer.state()["status"] == "UNVERIFIED"


def test_new_instruction_never_inherits_old_observations(producer):
    old_id = producer.clearance_id
    old = producer.build("normal", "ATC")
    accepted(producer, old)
    response = producer.client.post(f"/api/v1/flights/{producer.flight_id}/clearances")
    assert response.status_code == 201
    producer.clearance_id = response.json()["clearance_id"]
    assert producer.state()["observations"] == {}
    assert producer.send(old).status_code == 200  # Exact replay only; no mutation.
    changed = deepcopy(old)
    changed["event_id"] = "another-event"
    assert producer.send(changed).status_code == 409
    assert not producer.client.get(f"/api/v1/clearances/{old_id}").json()["active"]
    accepted(producer, producer.build("normal", "ATC"))
    assert set(producer.state()["observations"]) == {"ATC"}


@pytest.mark.parametrize("key,value", [("schema_version", "radar-observation/2"),
                                       ("unit", "FL"), ("missing_reason", None)])
def test_incompatible_producer_payload_rejected(producer, key, value):
    data = producer.build("normal", "ATC")
    if key == "unit":
        data["fields"]["altitude"]["unit"] = value
    elif key == "missing_reason":
        data["fields"]["altitude"]["value"] = value
    else:
        data[key] = value
    assert producer.send(data).status_code == 422
    assert producer.events() == []


def test_partial_instruction_all_sources_keep_null_and_zero(producer):
    for source in ("ATC", "READBACK", "COCKPIT"):
        data = producer.build("partial-atc", source)
        accepted(producer, data)
    for data in producer.state()["observations"].values():
        assert data["fields"]["altitude"] is None
        assert data["fields"]["heading"]["value"] == 0
    assert "missing_altitude" not in producer.state()["reasons"]


def test_equivalent_utc_serialization_is_an_idempotent_retry(producer):
    data = producer.build("normal", "ATC")
    accepted(producer, data)
    for key in ("captured_at", "processed_at"):
        data[key] = data[key].replace("+00:00", "Z")
    response = producer.send(data)
    assert response.status_code == 200 and response.json()["replayed"]
    assert len(producer.events()) == 1
