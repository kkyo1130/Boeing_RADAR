"""Local stream events; not a backend observation contract or safety verdict."""
import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, RLock, Thread
from time import monotonic, sleep
from uuid import uuid4

from .capture import LatestCamera, utc_now, video_frames
from .poc import load_config, recognize


class Stabilizer:
    def __init__(self, required=3):
        if type(required) is not int or required < 1:
            raise ValueError("stable_frames must be a positive integer")
        self.required = required
        self.history = {}
        self.lock = RLock()

    def reset(self):
        with self.lock:
            self.history.clear()

    def apply(self, fields):
        with self.lock:
            self._apply(fields)

    def _apply(self, fields):
        for name, field in fields.items():
            value = field["value"]
            if value is None or field["reason"] is not None:
                self.history.pop(name, None)
                field["stable_count"] = 0
                continue
            previous, count = self.history.get(name, (None, 0))
            count = count + 1 if previous == value else 1
            self.history[name] = (value, count)
            field.update(candidate_value=value, stable_count=count)
            if count < self.required:
                field.update(value=None, reason="unstable_reading")


def invalidate(fields, reason):
    for field in fields.values():
        field.update(value=None, reason=reason, stable_count=0)


def process_frame(frame, config, binary, output_dir, mode, stabilizer, max_age,
                  camera=None, generation=None, clock=monotonic, read_timeout=None):
    with TemporaryDirectory(prefix="radar-frame-") as temporary:
        source = Path(temporary) / "frame.png"
        frame.image.save(source)
        observation = recognize(source, config, binary, output_dir, frame.received_at)
    age = max(0, clock() - frame.received_monotonic)
    reason = None
    if camera is not None:
        _, reason, current_generation = camera.snapshot(read_timeout if read_timeout is not None else max_age)
        if generation != current_generation:
            reason = "camera_reconnected"
    if mode == "camera" and age > max_age:
        reason = reason or "stale_frame"
    if reason:
        stabilizer.reset()
        invalidate(observation["fields"], reason)
    else:
        stabilizer.apply(observation["fields"])
    observation.update(ocr_schema_version=observation["schema_version"],
                       schema_version="vision-stream-observation/1",
                       input_mode=mode, frame_sequence=frame.sequence,
                       capture_time_basis="host_receive" if mode == "camera" else "unknown",
                       media_time_ms=frame.media_time_ms)
    # Keep saved observation and emitted event consistent after stabilization.
    Path(observation["evidence"]).with_name("observation.json").write_text(
        json.dumps(observation, indent=2))
    return {"schema_version": "vision-stream/1", "event_type": "observation",
            "emitted_at": utc_now(), "input_mode": mode,
            "health": {"status": "degraded" if reason else "available", "reason": reason},
            "frame_age_seconds": round(age, 3) if mode == "camera" else None,
            "live_input": mode == "camera", "observation": observation}


def health_event(reason, mode="camera"):
    return {"schema_version": "vision-stream/1", "event_type": "health",
            "emitted_at": utc_now(), "input_mode": mode,
            "health": {"status": "unavailable", "reason": reason},
            "live_input": mode == "camera", "observation": None}


class EventWriter:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "events.jsonl"
        self.lock = RLock()
        self.latest = None
        self.deadline = None

    def emit(self, event):
        with self.lock:
            self._emit(event)

    def _emit(self, event):
        with self.path.open("a") as output:
            output.write(json.dumps(event) + "\n")
        temporary = self.directory / "latest.tmp"
        temporary.write_text(json.dumps(event, indent=2))
        temporary.replace(self.directory / "latest.json")
        self.latest = event
        self.deadline = None
        print(json.dumps(event), flush=True)

    def monitor(self, camera, stabilizer, timeout, now=None):
        now = monotonic() if now is None else now
        _, reason, _ = camera.snapshot(timeout, now)
        with self.lock:
            if reason is None and self.deadline is not None and now > self.deadline:
                reason = "stale_observation"
            if reason and (self.latest is None or self.latest["health"]["reason"] != reason):
                stabilizer.reset()
                self._emit(health_event(reason))


def watch_camera(camera, writer, stabilizer, timeout, stop):
    while not stop.wait(0.1):
        writer.monitor(camera, stabilizer, timeout)


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def main():
    parser = argparse.ArgumentParser(description="Local camera/video OCR stream; no server transmission")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--camera", type=int, help="Camera device index, e.g. 0")
    source.add_argument("--video", type=Path, help="Offline video replay")
    parser.add_argument("--config", required=True)
    parser.add_argument("--ocr-binary", required=True)
    parser.add_argument("--output-dir", default="vision/output/stream")
    parser.add_argument("--sample-seconds", type=positive, default=1.0)
    parser.add_argument("--read-timeout", type=positive, default=3.0)
    parser.add_argument("--max-frame-age", type=positive, default=5.0)
    parser.add_argument("--retry-seconds", type=positive, default=1.0)
    parser.add_argument("--stable-frames", type=int, default=3)
    parser.add_argument("--duration", type=positive, help="Stop after this many seconds; otherwise Ctrl-C")
    args = parser.parse_args()
    camera = None
    watch_stop = Event()
    watcher = None
    writer = None
    mode = "camera" if args.camera is not None else "video_file"
    try:
        config = load_config(args.config)
        stabilizer = Stabilizer(args.stable_frames)
        if args.camera is not None and args.camera < 0:
            raise ValueError("Camera index must be nonnegative")
        directory = Path(args.output_dir) / str(uuid4())
        writer = EventWriter(directory)
        start = monotonic()
        if mode == "video_file":
            if not args.video.is_file():
                raise ValueError("Video file does not exist")
            count = 0
            end_reason = "video_ended"
            for frame in video_frames(args.video, args.sample_seconds):
                if args.duration and monotonic() - start >= args.duration:
                    end_reason = "playback_stopped"
                    break
                writer.emit(process_frame(frame, config, args.ocr_binary, directory, mode,
                                          stabilizer, args.max_frame_age))
                count += 1
            if not count and end_reason == "video_ended":
                end_reason = "video_no_frames"
            writer.emit(health_event(end_reason, mode))
        else:
            camera = LatestCamera(args.camera, *config["image_size"], args.retry_seconds).start()
            watcher = Thread(target=watch_camera,
                             args=(camera, writer, stabilizer, args.read_timeout, watch_stop), daemon=True)
            watcher.start()
            last_sequence, last_generation, last_reason = 0, None, None
            next_sample = 0
            while not args.duration or monotonic() - start < args.duration:
                now = monotonic()
                frame, reason, generation = camera.snapshot(args.read_timeout, now)
                if reason:
                    stabilizer.reset()
                    if reason != last_reason:
                        writer.emit(health_event(reason))
                    last_reason = reason
                elif frame.sequence != last_sequence and now >= next_sample:
                    if generation != last_generation:
                        stabilizer.reset()
                    event = process_frame(frame, config, args.ocr_binary, directory, mode,
                                          stabilizer, args.max_frame_age, camera, generation,
                                          read_timeout=args.read_timeout)
                    # Local writer metadata is not part of the portable event JSON.
                    with writer.lock:
                        writer.emit(event)
                        writer.deadline = frame.received_monotonic + args.max_frame_age
                    last_reason = event["health"]["reason"]
                    last_sequence, last_generation = frame.sequence, generation
                    next_sample = monotonic() + args.sample_seconds
                sleep(0.05)
            watch_stop.set()
            writer.emit(health_event("capture_stopped"))
    except KeyboardInterrupt:
        watch_stop.set()
        if writer:
            writer.emit(health_event("capture_stopped", mode))
    except (OSError, ValueError, KeyError) as error:
        watch_stop.set()
        if writer:
            writer.emit(health_event("input_error", mode))
        parser.exit(2, f"Input/capture error: {error}\n")
    finally:
        watch_stop.set()
        if watcher:
            watcher.join(timeout=1)
        if camera:
            camera.close()


if __name__ == "__main__":
    main()
