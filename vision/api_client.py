"""Explicit, state-aware submission to existing RADAR APIs."""
from __future__ import annotations
from datetime import datetime, timezone
import httpx
from vision.core import Recognition

class RadarClient:
    def __init__(self, base_url: str, clearance_id: str, timeout: float = 5):
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self.clearance_id = clearance_id
        self.last_submitted: tuple[int, int] | None = None

    def close(self):
        self.client.close()

    def submit(self, reading: Recognition):
        pair = (reading.altitude, reading.heading)
        if pair == self.last_submitted:
            return {"skipped": "duplicate"}
        path = f"/api/clearances/{self.clearance_id}"
        state_response = self.client.get(path)
        state_response.raise_for_status()
        state = state_response.json()
        if state.get("readback") is None:
            return {"skipped": "waiting_readback"}
        if state.get("cockpit") is None:
            endpoint = path + "/cockpit"
        elif state.get("status") == "SETTING_ERROR":
            endpoint = path + "/cockpit/reverify"
        else:
            return {"skipped": "no_allowed_cockpit_transition"}
        payload = {
            "altitude": reading.altitude,
            "heading": reading.heading,
            "confidence": reading.confidence,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        response = self.client.post(endpoint, json=payload)
        response.raise_for_status()
        self.last_submitted = pair
        return response.json()
