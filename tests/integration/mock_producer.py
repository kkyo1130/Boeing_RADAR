"""JSON/HTTP mock producer: intentionally has no backend/DTO/ORM imports."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import httpx
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "contracts" / "examples" / "v2"
CASES = json.loads((ROOT / "contracts/examples/integration/cases.json").read_text())


def timestamp(offset=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def validate(schema, value):
    definition = json.loads((ROOT / "contracts/schemas" / f"{schema}.schema.json").read_text())
    Draft202012Validator(definition, format_checker=FormatChecker()).validate(value)


class MockProducer:
    def __init__(self, base_url, record_path):
        self.run_id = uuid4().hex
        self.client = httpx.Client(base_url=base_url, timeout=5, trust_env=False)
        self.record_path = record_path
        self.records = []
        self.flight_id = None

    def identifier(self, kind):
        return f"{kind}-{self.run_id}-{uuid4().hex}"

    @property
    def path(self):
        return f"/api/v2/flights/{self.flight_id}"

    def request(self, method, path, payload=None, expected=200):
        sent_at = timestamp()
        response = self.client.request(method, path, json=payload)
        try:
            body = response.json()
        except ValueError:
            body = {"non_json_body": response.text}
        self.records.append(dict(run_id=self.run_id, sent_at=sent_at, received_at=timestamp(), method=method,
            path=path, request=deepcopy(payload), status=response.status_code, response=body))
        self.record_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2)+"\n")
        assert response.status_code == expected, (response.status_code, expected, body)
        if response.status_code >= 400:
            validate("contract-error-v2", body)
        return body

    def start(self):
        data = self.request("POST", "/api/v2/flights", {"callsign": "RADAR123"}, expected=201)
        self.flight_id = data["flight_id"]
        return data

    def state(self):
        data = self.request("GET", self.path+"/state")
        validate("target-snapshot-v2", {key: data[key] for key in
            ("schema_version", "flight_id", "revision", "targets", "readback_required")})
        return data

    def inputs(self):
        return self.request("GET", self.path+"/inputs?limit=1000")

    def trace(self):
        return self.request("GET", self.path+"/safety-trace?limit=1000")

    def observation(self, name):
        data = json.loads((EXAMPLES / name).read_text())
        data.update(flight_id=self.flight_id, observation_id=self.identifier("obs"),
            target_revision=self.state()["revision"], observed_at=timestamp(), processed_at=timestamp())
        # Explicit synthetic quality from the integration fixture, never inferred
        # from a real model or upgraded for UNREADABLE/UNKNOWN input.
        for field in data["fields"].values():
            if field["validity"] == "VALID":
                field["quality"] = deepcopy(CASES["quality"])
        if data.get("callsign", {}).get("validity") == "VALID":
            data["callsign"]["quality"] = deepcopy(CASES["quality"])
        return data

    def camera(self, name="cockpit-readable.json"):
        data = self.observation(name)
        data["frame_id"] = self.identifier("frame")
        return data

    def segment(self, atc=None, complete=True):
        data = json.loads((EXAMPLES / "speech-complete.json").read_text())
        started = timestamp()
        ended = timestamp()
        while ended == started:
            ended = timestamp()
        data.update(flight_id=self.flight_id, segment_id=self.identifier("segment"),
            atc_input_id=atc["atc_input_id"] if atc else self.identifier("atc"),
            attempt_id=self.identifier("attempt"), role="PILOT" if atc else "ATC",
            role_basis="PILOT_PTT" if atc else "ATC_PLAYBACK", started_at=started, ended_at=ended,
            complete=complete, interruption_reason=None if complete else "fixture_interruption",
            audio_ref=f"fixture-audio-{self.run_id}")
        validate("speech-segment-v2", data)
        response = self.request("POST", self.path+"/speech-segments", data, expected=201)
        return {**data, "instruction_id": response["instruction_id"]}

    def speech(self, segment, name="atc-full.json"):
        data = self.observation(name)
        data.update(segment_id=segment["segment_id"], atc_input_id=segment["atc_input_id"],
            attempt_id=segment["attempt_id"], observed_at=segment["started_at"])
        if segment["role"] == "PILOT":
            data.update(source="READBACK", instruction_id=segment["instruction_id"])
        return data

    def send(self, data, expected=201, check_schema=True):
        if check_schema:
            validate("observation-v2", data)
        result = self.request("POST", self.path+"/observations", data, expected=expected)
        if expected in (200, 201):
            validate("ingestion-receipt-v2", result)
            assert result["input_id"] == data["observation_id"]
        return result

    def adopt(self, name="atc-full.json"):
        segment = self.segment()
        data = self.speech(segment, name)
        self.send(data)
        return segment, data

    def health(self, status):
        data = dict(schema_version="2", flight_id=self.flight_id,
            event_id=self.identifier("health"), channel="CAMERA", observed_at=timestamp(),
            health=dict(status=status, reason=None if status == "AVAILABLE" else "camera_disconnected"))
        validate("health-event-v2", data)
        receipt = self.request("POST", self.path+"/health-events", data, expected=201)
        validate("ingestion-receipt-v2", receipt)
        return data, receipt

    def close(self):
        self.client.close()
