"""Real file/microphone/vision adapter. Never substitutes processing time for capture time."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "communication"))


class Producer:
    def __init__(self, base, flight, clearance, source, channel):
        self.base, self.flight, self.clearance = base.rstrip('/'), flight, clearance
        self.source, self.channel = source, channel

    def request(self, path, data=None, media="application/json"):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        request = Request(self.base + path, data=data, headers={"Content-Type": media})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def evidence(self, path, media):
        return self.request(f"/api/v1/clearances/{self.clearance}/evidence", Path(path).read_bytes(), media)

    def envelope(self, mode, captured, basis):
        stamp = datetime.now(timezone.utc).isoformat()
        token = str(uuid4())
        return {"schema_version": "radar-observation/1", "event_type": "observation",
            "event_id": f"event-{token}", "observation_id": f"obs-{token}",
            "sample_id": f"sample-{token}", "flight_id": self.flight,
            "clearance_id": self.clearance, "source": self.source, "channel_id": self.channel,
            "input_mode": mode, "captured_at": captured, "capture_time_basis": basis,
            "processed_at": stamp, "health": {"status": "available", "reason": None},
            "intent": "initial", "supersedes_observation_id": None, "fields": {},
            "speech": None, "evidence": []}

    def send(self, body):
        from app.schemas.observation_contract import ObservationContract
        if body["event_type"] == "observation":
            current = self.request(f"/api/v1/clearances/{self.clearance}")
            previous = current["observations"].get(self.source)
            if previous:
                body.update(intent="correction", supersedes_observation_id=previous["observation_id"])
        wire = ObservationContract.model_validate(body).model_dump(mode="json")
        return self.request("/api/v1/observations", wire)

    def health(self, mode, reason):
        body = self.envelope(mode, None, "unknown")
        body.update(event_type="health", observation_id=None, sample_id=None, fields=None,
                    intent=None, health={"status": "unavailable", "reason": reason})
        return self.send(body)


def audio(producer, args):
    from radar_audio.audio import prepare, record_microphone
    from app.services.speech.local import LocalWhisper, structure
    with TemporaryDirectory(prefix="radar-audio-") as folder:
        path = args.wav
        captured = args.captured_at
        engine = LocalWhisper(args.model)
        if args.microphone:
            if producer.source != "READBACK":
                raise ValueError("Pilot microphone must explicitly use READBACK")
            path = Path(folder) / "microphone.wav"
            activity = {"channel_id": producer.channel, "active": True, "lease_seconds": min(60, args.seconds + 10)}
            producer.request(f"/api/v1/flights/{producer.flight}/input-activity", activity)
            try:
                captured = record_microphone(path, args.seconds, args.device)
            finally:
                producer.request(f"/api/v1/flights/{producer.flight}/input-activity", {**activity, "active": False})
        segments = list(prepare(path, Path(folder) / "segments", seconds=args.seconds))
        if not segments:
            print(json.dumps(producer.health("microphone" if args.microphone else "audio_file", "empty_audio")))
        for segment in segments:
            stamp = ((datetime.fromisoformat(captured.replace("Z", "+00:00")) +
                      timedelta(seconds=segment["offset_seconds"])).isoformat() if captured else None)
            body = producer.envelope("microphone" if args.microphone else "audio_file", stamp,
                                     "host_receive" if args.microphone else "provided" if stamp else "unknown")
            result = engine.transcribe(segment["path"])
            parsed = structure(result["transcript"], args.callsign)
            evidence = producer.evidence(segment["path"], "audio/wav")
            reasons = segment["quality_reasons"] + parsed["quality_reasons"]
            if not result["transcript"]:
                reasons.append("no_speech_recognized")
            if not args.reviewed_channel:
                reasons.append("channel_overlap_noise_feedback_unchecked")
            body["speech"] = parsed["speech"]
            if reasons:
                body["health"] = {"status": "degraded", "reason": reasons[0]}
            body["evidence"] = [evidence]
            body["sample_id"] = segment["segment_id"]
            for name, field in parsed["fields"].items():
                if (producer.source == "ATC" and any(parsed["mentioned"].values())
                        and not parsed["mentioned"][name]):
                    body["fields"][name] = None
                    continue
                body["fields"][name] = {**field, "unit": "feet" if name == "altitude" else "degrees",
                    "model_score": result["model_score"], "score_calibrated": False,
                    "quality": {"status": "degraded" if reasons else "acceptable", "reasons": reasons},
                    "evidence_ids": [evidence["evidence_id"]]}
            print(json.dumps(producer.send(body)))


def vision(producer, args):
    if producer.source != "COCKPIT":
        raise ValueError("Vision must explicitly use COCKPIT")
    # stdin permits a live stream pipeline; JSONL files retain their original timestamps.
    source = sys.stdin if str(args.events) == '-' else args.events.open()
    try:
        for line in source:
            event = json.loads(line)
            mode = "camera" if event["input_mode"] == "camera" else "video_file"
            if event["event_type"] == "health":
                print(json.dumps(producer.health(mode, event["health"]["reason"])))
                continue
            observed = event["observation"]
            stamp = observed["captured_at"] if mode == "camera" else None
            body = producer.envelope(mode, stamp, "host_receive" if stamp else "unknown")
            body["sample_id"] = observed["frame_id"]
            body["processed_at"] = observed["processed_at"]
            body["health"] = event["health"]
            for name in ("altitude", "heading"):
                field = observed["fields"][name]
                evidence = producer.evidence(field["evidence"], "image/png")
                body["evidence"].append(evidence)
                reason = field["reason"]
                raw_text = field["raw_text"]
                if name == "altitude" and field.get("display_unit") == "FL" and raw_text:
                    raw_text = "FL " + raw_text.zfill(3)
                body["fields"][name] = {"value": field["value"], "reason": reason,
                    "raw_text": raw_text, "model_score": field["model_score"],
                    "unit": "feet" if name == "altitude" else "degrees", "score_calibrated": False,
                    "quality": {"status": "degraded" if reason else "acceptable", "reasons": [reason] if reason else []},
                    "evidence_ids": [evidence["evidence_id"]]}
            print(json.dumps(producer.send(body)))
    finally:
        if source is not sys.stdin:
            source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--flight", required=True)
    parser.add_argument("--clearance", required=True)
    parser.add_argument("--source", choices=["ATC", "READBACK", "COCKPIT"], required=True)
    parser.add_argument("--channel", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sound = sub.add_parser("audio")
    inputs = sound.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--wav", type=Path)
    inputs.add_argument("--microphone", action="store_true")
    sound.add_argument("--model", type=Path, required=True)
    sound.add_argument("--callsign", required=True)
    sound.add_argument("--captured-at", help="Original UTC capture time; omitted stays unknown")
    sound.add_argument("--seconds", type=int, default=10)
    sound.add_argument("--device")
    sound.add_argument("--reviewed-channel", action="store_true", help="Operator attests no overlap/noise/warning feedback")
    image = sub.add_parser("vision")
    image.add_argument("--events", type=Path, required=True, help="vision-stream/1 JSONL or - for stdin")
    args = parser.parse_args()
    if args.command == "audio" and args.source == "COCKPIT":
        parser.error("Audio source must be ATC or READBACK")
    producer = Producer(args.server, args.flight, args.clearance, args.source, args.channel)
    try:
        (audio if args.command == "audio" else vision)(producer, args)
    except Exception:
        try:
            producer.health("microphone" if getattr(args, "microphone", False) else
                            "audio_file" if args.command == "audio" else "camera", "producer_failed")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
