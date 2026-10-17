"""Fixture-only producer: no backend models, camera, microphone or OCR dependencies."""
import json
from pathlib import Path
from uuid import uuid4

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts/examples/observation-v1"


class MockContractProducer:
    def __init__(self, client, flight_id, clearance_id, capture):
        self.client = client
        self.flight_id = flight_id
        self.clearance_id = clearance_id
        self.capture = capture

    def build(self, name, source, supersedes=None):
        # This creates a NEW synthetic sample. Never retime recorded real observations.
        data = json.loads((EXAMPLES / f"{name}.json").read_text())
        stamp = self.capture().isoformat()
        token = str(uuid4())
        data.update(event_id=f"event-{token}", flight_id=self.flight_id,
                    clearance_id=self.clearance_id, source=source,
                    channel_id=f"mock-{source.lower()}", input_mode="fixture",
                    processed_at=stamp)
        if data["event_type"] == "health":
            return data
        data.update(observation_id=f"observation-{token}", sample_id=f"sample-{token}")
        if data["captured_at"] is not None:
            data["captured_at"] = stamp
        if data["intent"] == "correction":
            if supersedes is None:
                raise ValueError("Correction needs the prior observation ID")
            data["supersedes_observation_id"] = supersedes
        if source != "COCKPIT":
            context = json.loads((EXAMPLES / "partial-atc.json").read_text())["speech"]
            # Fixture role assignment is labelled, never inferred from arrival order.
            actions = [f"{key} {field['value']} {field['unit']}"
                       for key, field in data["fields"].items() if field is not None]
            context.update(transcript="RADAR1 " + "; ".join(actions), ordered_actions=actions)
            data["speech"] = context
            for evidence in data["evidence"]:
                evidence.update(kind="audio", roi=None)
        else:
            data["speech"] = None
        return data

    def send(self, data):
        # Crossing the JSON API boundary, not calling backend validators directly.
        return self.client.post("/api/v1/observations", json=data)

    def state(self):
        return self.client.get(f"/api/v1/clearances/{self.clearance_id}").json()

    def events(self):
        return self.client.get(f"/api/v1/flights/{self.flight_id}/observation-events").json()
