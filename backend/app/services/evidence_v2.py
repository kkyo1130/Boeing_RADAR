"""Read-only evidence linkage and atomic user interaction records.

Media references are local, explicit media: paths under a configured trusted root.
Never fetch producer-provided URLs, arbitrary local files, or execute active content.
"""
import os
import stat
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlencode, quote
from sqlalchemy import select
from app.models.observation_v2 import V2Input, V2TraceEvent
from app.services import receiving_v2 as intake

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}
MAX_BYTES = 20 * 1024 * 1024


def selected(db, flight_id, instruction_id, stage, field, observation_id):
    state = intake.get_state(db, flight_id)
    rows = state["validation"]["readback" if stage == "READBACK" else "setting"]["fields"]
    verdict = next((row for row in rows if row["field"] == field and row["instruction_id"] == instruction_id
        and row["observation_id"] == observation_id), None)
    if verdict is None:
        raise intake.ReceivingError(409, "CONTEXT_MISMATCH", "Selection no longer matches the current instruction and observation")
    def observation(oid):
        return db.scalar(select(V2Input).where(V2Input.flight_id == flight_id,
            V2Input.kind == "OBSERVATION", V2Input.input_id == oid))
    current = observation(observation_id)
    targets = [target for target in state["targets"].values() if target and target["instruction_id"] == instruction_id]
    target = next((target for target in targets if field == "CALLSIGN" or state["targets"].get(field) == target), None)
    atc = observation(target["source_observation_id"]) if target else None
    if current is None or atc is None:
        raise intake.ReceivingError(404, "NOT_FOUND", "Observation evidence is not available")
    return state, verdict, {"ATC": atc, "OBSERVED": current}


def media_path(ref):
    root = os.environ.get("RADAR_EVIDENCE_ROOT")
    if not root:
        return None, "MEDIA_ROOT_NOT_CONFIGURED"
    if not ref.startswith("media:"):
        return None, "UNSUPPORTED_MEDIA_REFERENCE"
    relative = Path(ref[6:])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return None, "UNSAFE_MEDIA_REFERENCE"
    try:
        base = Path(root).resolve(strict=True)
        path = (base / relative).resolve(strict=True)
        if not path.is_relative_to(base) or not path.is_file():
            return None, "UNSAFE_MEDIA_REFERENCE"
        if not os.access(path, os.R_OK):
            return None, "MEDIA_NOT_AVAILABLE"
        if path.suffix.lower() not in MIME:
            return None, "UNSUPPORTED_MEDIA_TYPE"
        if path.stat().st_size > MAX_BYTES:
            return None, "MEDIA_TOO_LARGE"
        return path, None
    except (OSError, RuntimeError):
        return None, "MEDIA_NOT_AVAILABLE"


def refs(row, field):
    return [ref for ref in row.payload.get("evidence_refs", []) if ref["field"] in (None, field)]


def metadata(db, flight_id, instruction_id, stage, field, observation_id):
    state, verdict, observations = selected(db, flight_id, instruction_id, stage, field, observation_id)
    groups = {}
    query = urlencode(dict(instruction_id=instruction_id, stage=stage, field=field))
    for role, row in observations.items():
        data = row.payload
        assets = []
        for ref in refs(row, field):
            path, reason = media_path(ref["ref"])
            if ref["kind"] == "TRANSCRIPT":
                path, reason = None, "TRANSCRIPT_SHOWN_AS_TEXT"
            elif path and ((ref["kind"] == "AUDIO") != MIME[path.suffix.lower()].startswith("audio/")):
                path, reason = None, "MEDIA_KIND_CONFLICT"
            assets.append({**{key: value for key, value in ref.items() if key != "ref"},
                "url": (f"/api/v2/flights/{quote(flight_id, safe='')}/evidence/{quote(observation_id, safe='')}/media/{role}/{quote(ref['evidence_id'], safe='')}?{query}" if path else None),
                "unavailable_reason": reason})
        groups[role] = dict(observation_id=row.input_id, observed_at=data.get("observed_at"),
            time_reason=data.get("time_reason"), source=data["source"], transcript=data.get("transcript"),
            reading=data.get("callsign") if field == "CALLSIGN" else data.get("fields", {}).get(field),
            assets=assets, evidence_unavailable_reason=data.get("evidence_unavailable_reason"),
            applied=row.applied, intake_reason=row.reason)
    return dict(schema_version="2", flight_id=flight_id, instruction_id=instruction_id, observation_id=observation_id,
        stage=stage, field=field, verdict=verdict, groups=groups)


def content(db, flight_id, instruction_id, stage, field, observation_id, role, evidence_id):
    _, _, observations = selected(db, flight_id, instruction_id, stage, field, observation_id)
    ref = next((ref for ref in refs(observations[role], field) if ref["evidence_id"] == evidence_id), None)
    if not ref or ref["kind"] == "TRANSCRIPT":
        raise intake.ReceivingError(404, "NOT_FOUND", "Media is not available for this selection")
    data, mime = read_media(ref["ref"])
    if (ref["kind"] == "AUDIO") != mime.startswith("audio/"):
        raise intake.ReceivingError(404, "NOT_FOUND", "MEDIA_KIND_CONFLICT")
    return data, mime


def interact(db, flight_id, message):
    data = message.model_dump(mode="json")
    now = intake.utc_now()
    with intake.atomic(db):
        _, profile = intake.context(db, flight_id, active=True, lock=True)
        existing = db.scalar(select(V2TraceEvent).where(V2TraceEvent.flight_id == flight_id,
            V2TraceEvent.event_type.in_(["USER_ACKNOWLEDGED", "EVIDENCE_OPENED"]),
            V2TraceEvent.snapshot["client_event_id"].as_string() == message.event_id))
        if existing:
            if existing.snapshot["request"] != data:
                raise intake.ReceivingError(409, "ID_CONTENT_CONFLICT", "Interaction ID already has different content")
            return interaction_receipt(existing), 200
        state, verdict, _ = selected(db, flight_id, message.instruction_id, message.stage, message.field, message.observation_id)
        if message.action == "ACKNOWLEDGED" and verdict["result"] == "NORMAL":
            raise intake.ReceivingError(409, "INVALID_SEQUENCE", "There is no current mismatch or hold to acknowledge")
        incident = next((item for item in state["incidents"] if item["status"] == "OPEN"
            and item["instruction_id"] == message.instruction_id and item["stage"] == message.stage
            and item["field"] == message.field), None)
        profile.revision += 1
        event = intake.trace(db, profile, "USER_ACKNOWLEDGED" if message.action == "ACKNOWLEDGED" else "EVIDENCE_OPENED",
            dict(client_event_id=message.event_id, request=data, verdict=verdict,
                occurrence_id=incident["occurrence_id"] if incident else None), now)
        return interaction_receipt(event), 201


def interaction_receipt(event):
    return dict(schema_version="2", event_id=f"v2-event-{event.id}", recorded_at=event.occurred_at,
        action=event.snapshot["request"]["action"], observation_id=event.snapshot["request"]["observation_id"])


def read_media(ref):
    """Open every component without symlinks; validate/read the SAME descriptor."""
    root = os.environ.get("RADAR_EVIDENCE_ROOT")
    relative = Path(ref[6:]) if ref.startswith("media:") else Path()
    if not root or not relative.parts or relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in MIME:
        raise intake.ReceivingError(404, "NOT_FOUND", "MEDIA_NOT_AVAILABLE")
    try:
        with ExitStack() as stack:
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, directory)
            for part in relative.parts[:-1]:
                directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                stack.callback(os.close, directory)
            descriptor = os.open(relative.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            stack.callback(os.close, descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                raise OSError("Unsupported media file")
            chunks, length = [], 0
            while chunk := os.read(descriptor, min(65536, MAX_BYTES + 1 - length)):
                chunks.append(chunk); length += len(chunk)
                if length > MAX_BYTES:
                    raise OSError("Media exceeded resource bound")
            return b"".join(chunks), MIME[relative.suffix.lower()]
    except OSError as exc:
        raise intake.ReceivingError(404, "NOT_FOUND", "MEDIA_NOT_AVAILABLE") from exc
