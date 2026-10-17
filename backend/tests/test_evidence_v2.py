"""Current evidence scope, constrained media and non-resolving user events."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from test_receiving_v2 import setup, scenario, Scenario
from test_validation_v2_api import match_readback, cockpit


def failure(s):
    a = s.adopt(); match_readback(s, a); cockpit(s); cockpit(s, heading=90)
    return s.state()["validation"]["setting"]["fields"][1]


def params(row):
    return {key: row[key] for key in ("instruction_id", "stage", "field")}


def path(s, row):
    return s.url+"/evidence/"+row["observation_id"]


def interaction(row, action="ACKNOWLEDGED"):
    return dict(event_id=uuid4().hex, observation_id=row["observation_id"], action=action, **params(row))


def test_panel_shows_raw_observation_and_target_without_changing_verdict(scenario):
    s = scenario; row = failure(s); before, trace = s.state(), s.trace()
    response = s.client.get(path(s, row), params=params(row)); assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == row
    assert data["groups"]["OBSERVED"]["reading"]["value"] == 90
    assert data["groups"]["ATC"]["reading"]["value"] == 270
    assert data["groups"]["OBSERVED"]["evidence_unavailable_reason"] == "fixture_has_no_media"
    assert s.state() == before and s.trace() == trace


@pytest.mark.parametrize("change", ["instruction_id", "field", "observation_id", "stage"])
def test_wrong_context_cannot_open_or_acknowledge(scenario, change):
    s = scenario; row = failure(s); selection = dict(row)
    selection[change] = {"field":"CALLSIGN", "stage":"READBACK"}.get(change, "wrong-id")
    response = s.client.get(path(s, selection), params=params(selection)); assert response.status_code == 409
    assert s.client.post(s.url+"/interactions", json=interaction(selection)).status_code == 409


def test_old_panel_stops_after_new_observation_or_partial_replacement(scenario):
    s = scenario; row = failure(s)
    cockpit(s, heading=80)
    assert s.client.get(path(s, row), params=params(row)).status_code == 409
    row = s.state()["validation"]["setting"]["fields"][1]
    s.tick(); s.adopt()  # Both targets replaced.
    assert s.client.get(path(s, row), params=params(row)).status_code == 409


def test_acknowledgement_is_atomic_idempotent_and_never_resolves(scenario, monkeypatch):
    s = scenario; row = failure(s); before = s.state(); trace = s.trace(); message = interaction(row)
    original = Session.commit
    def fail(self): raise RuntimeError("interaction commit failure")
    monkeypatch.setattr(Session, "commit", fail)
    with pytest.raises(RuntimeError): s.client.post(s.url+"/interactions", json=message)
    monkeypatch.setattr(Session, "commit", original)
    assert s.state() == before and s.trace() == trace
    first = s.client.post(s.url+"/interactions", json=message); assert first.status_code == 201
    after = s.state()
    assert after["validation"] == before["validation"] and after["incidents"] == before["incidents"]
    again = s.client.post(s.url+"/interactions", json=message)
    assert again.status_code == 200 and again.json() == first.json()
    assert s.state() == after
    message["action"] = "EVIDENCE_OPENED"
    assert s.client.post(s.url+"/interactions", json=message).status_code == 409
    assert s.trace()[-1]["event_type"] == "USER_ACKNOWLEDGED"
    assert s.trace()[-1]["snapshot"]["occurrence_id"] == after["incidents"][0]["occurrence_id"]


def test_view_is_separate_from_ack_and_new_correction_needs_no_ack(scenario):
    s = scenario; row = failure(s)
    assert s.client.post(s.url+"/interactions", json=interaction(row, "EVIDENCE_OPENED")).status_code == 201
    assert not any(event["event_type"] == "USER_ACKNOWLEDGED" for event in s.trace())
    cockpit(s)
    assert s.state()["incidents"][0]["status"] == "RESOLVED"
    assert s.client.post(s.url+"/interactions", json=interaction(row)).status_code == 409


def test_other_flight_and_ended_session_cannot_acknowledge(setup):
    s = Scenario(setup[0], setup[1]); row = failure(s)
    other = Scenario(setup[0], setup[1])
    assert other.client.get(path(other, row), params=params(row)).status_code == 409
    assert s.client.post(s.url+"/end").status_code == 200
    assert s.client.post(s.url+"/interactions", json=interaction(row)).status_code == 409


@pytest.mark.parametrize("ref,expected", [("media:sample.png", True), ("media:missing.png", False),
    ("media:../secret.png", False), ("media:/etc/passwd", False), ("https://example.com/image.png", False),
    ("media:active.html", False), ("media:escape.png", False)])
def test_media_is_scoped_and_never_fetches_arbitrary_path(scenario, tmp_path, monkeypatch, ref, expected):
    s = scenario; a = s.adopt(); match_readback(s, a)
    root = tmp_path/"media"; root.mkdir()
    (root/"sample.png").write_bytes(b"synthetic-image-fixture")
    (root/"active.html").write_text("<script>bad()</script>")
    (tmp_path/"secret.png").write_bytes(b"secret")
    (root/"escape.png").symlink_to(tmp_path/"secret.png")
    monkeypatch.setenv("RADAR_EVIDENCE_ROOT", str(root))
    s.tick(); data = s.camera(); data["fields"]["HDG"].update(value=90, raw_text="90")
    data.update(evidence_unavailable_reason=None, evidence_refs=[dict(evidence_id="image", kind="ROI", ref=ref, field="HDG", roi=[0,0,20,20])])
    assert s.send(data).status_code == 201
    row = s.state()["validation"]["setting"]["fields"][1]
    meta = s.client.get(path(s,row), params=params(row)).json()
    asset = meta["groups"]["OBSERVED"]["assets"][0]
    if expected:
        assert asset["url"] and asset["unavailable_reason"] is None
        response = s.client.get(asset["url"])
        assert response.status_code == 200 and response.content == b"synthetic-image-fixture"
        assert response.headers["x-content-type-options"] == "nosniff"
        for value, expected_bytes in [("bytes=0-3", b"synt"), ("bytes=10-", b"image-fixture"), ("bytes=-7", b"fixture")]:
            partial = s.client.get(asset["url"], headers={"Range": value})
            assert partial.status_code == 206 and partial.content == expected_bytes
        for value in ["bytes=999-", "bytes=-0", "bytes=0-1,3-4", "bytes="+"9"*5000+"-"]:
            assert s.client.get(asset["url"], headers={"Range": value}).status_code == 416
        cockpit(s)  # A URL captured earlier can no longer open the replaced observation.
        assert s.client.get(asset["url"]).status_code == 409
    else:
        assert asset["url"] is None and asset["unavailable_reason"]
        manual = path(s,row)+"/media/OBSERVED/image"
        assert s.client.get(manual, params=params(row)).status_code == 404


def test_actual_correction_readback_can_start_without_panel_or_ack(scenario):
    s = scenario; a = s.adopt(); s.tick()
    data = s.speech(s.segment(a)); data["transcript"] = "Radar one two three maintain four thousand feet heading two seven zero"
    data["fields"]["ALT"].update(value=4000,raw_text="4000"); s.send(data)
    match_readback(s,a)
    assert s.state()["incidents"][0]["status"] == "RESOLVED"
    assert not any(e["event_type"] in ("USER_ACKNOWLEDGED", "EVIDENCE_OPENED") for e in s.trace())


def test_open_descriptor_remains_safe_after_producer_replaces_path(tmp_path, monkeypatch):
    from app.services import evidence_v2 as service
    root=tmp_path/'media';root.mkdir();file=root/'image.png';file.write_bytes(b'original')
    secret=tmp_path/'secret.png';secret.write_bytes(b'private')
    monkeypatch.setenv('RADAR_EVIDENCE_ROOT', str(root))
    original=service.os.fstat
    def swap(fd):
        info=original(fd)
        file.unlink();file.symlink_to(secret)
        return info
    monkeypatch.setattr(service.os, 'fstat', swap)
    assert service.read_media('media:image.png')[0] == b'original'


def test_replaced_parent_directory_is_not_followed(tmp_path, monkeypatch):
    from app.services import evidence_v2 as service
    from app.services.receiving_v2 import ReceivingError
    root=tmp_path/'media';root.mkdir();outside=tmp_path/'outside';outside.mkdir()
    (outside/'image.png').write_bytes(b'private');(root/'sub').symlink_to(outside,target_is_directory=True)
    monkeypatch.setenv('RADAR_EVIDENCE_ROOT', str(root))
    with pytest.raises(ReceivingError):service.read_media('media:sub/image.png')
