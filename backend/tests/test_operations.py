import io
import json
import wave
from datetime import timedelta
from test_three_state_decision import rig, settings, data, send, normal


def report(rig):
    return rig[0].get(f"/api/v1/flights/{rig[2]}/report").json()


def test_incident_correction_ack_export_and_frozen_end(rig):
    client, clock, flight, c = rig
    settings(rig)
    send(rig, data(rig, "ATC"))
    bad = data(rig, "READBACK", altitude=3500)
    send(rig, bad)
    first = report(rig)
    incident = first["incidents"][0]
    assert first["summary"]["incidents"] == 1
    send(rig, bad)  # Retry must not create another incident or trace.
    assert report(rig) == first
    action = {"action": "ACKNOWLEDGED", "actor": "tester", "reason": "reviewed"}
    path = f'/api/v1/incidents/{incident["incident_id"]}/actions'
    assert client.post(path, json=action).json()["recorded"]
    assert not client.post(path, json=action).json()["recorded"]
    fixed = data(rig, "READBACK", previous=bad)
    send(rig, fixed)
    final = report(rig)
    assert final["incidents"][0]["status"] == "RESOLVED"
    assert final["summary"]["normal"] == 0  # Cockpit still missing.
    assert final["incidents"][0]["resolution_seconds"] == 1
    send(rig, data(rig, "COCKPIT"))
    assert client.post(f"/api/flights/{flight}/end").status_code == 200
    frozen = report(rig)
    assert frozen["terminal"] and frozen["summary"]["normal"] == 1
    clock[0] += timedelta(days=1)
    assert report(rig) == frozen
    assert client.get(f"/api/v1/flights/{flight}/report.json").json() == frozen


def test_uncertain_correction_and_new_instruction_cannot_close_incident(rig):
    settings(rig)
    send(rig, data(rig, "ATC"))
    bad = data(rig, "READBACK", heading=280)
    send(rig, bad)
    uncertain = data(rig, "READBACK", previous=bad)
    uncertain["fields"]["heading"].update(value=None, reason="unreadable")
    send(rig, uncertain)
    assert report(rig)["incidents"][0]["status"] == "OPEN"
    incident = report(rig)["incidents"][0]
    assert rig[0].post(f'/api/v1/incidents/{incident["incident_id"]}/actions', json={
        "action": "VOICE_PLAYED", "actor": "test", "reason": "test"}).status_code == 409
    rig[0].post(f"/api/v1/flights/{rig[2]}/clearances")
    assert report(rig)["incidents"][0]["status"] == "SUPERSEDED"
    assert report(rig)["summary"]["unresolved"] == 1


def test_evidence_binding_deletion_and_freshness(rig):
    client, _, flight, c = rig
    settings(rig)
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 100)
    response = client.post(f"/api/v1/clearances/{c}/evidence", content=stream.getvalue(),
                           headers={"Content-Type": "audio/wav"})
    assert response.status_code == 201
    evidence = response.json()
    assert client.get(evidence["reference"]).content == stream.getvalue()
    assert client.get(evidence["reference"].replace(c, "other")).status_code == 404
    from PIL import Image
    image = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(image, format="PNG")
    evidence = client.post(f"/api/v1/clearances/{c}/evidence", content=image.getvalue(),
                           headers={"Content-Type": "image/png"}).json()
    values = normal(rig)
    correction = data(rig, "COCKPIT", previous=values["COCKPIT"])
    correction["evidence"] = [evidence]
    for field in correction["fields"].values():
        field["evidence_ids"] = [evidence["evidence_id"]]
    send(rig, correction)
    assert report(rig)["summary"]["normal"] == 1
    assert client.delete(evidence["reference"]).status_code == 200
    assert client.get(evidence["reference"]).status_code == 410
    assert report(rig)["summary"]["unverified"] == 1
    assert client.post(f"/api/v1/clearances/{c}/evidence", content=b"bad",
                       headers={"Content-Type": "image/png"}).status_code == 422
