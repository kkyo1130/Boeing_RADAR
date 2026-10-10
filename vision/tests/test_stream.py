from pathlib import Path
from threading import Event

import pytest
from PIL import Image

from radar_vision.capture import Frame, LatestCamera, video_frames
from radar_vision.poc import load_config
from radar_vision.stream import EventWriter, Stabilizer, health_event, process_frame


CONFIG = Path(__file__).parents[1] / "configs/synthetic.json"


def field(value, reason=None):
    return {"value": value, "reason": reason, "raw_text": str(value)}


def test_changed_value_and_failure_never_reuse_stable_value():
    stable = Stabilizer(2)
    def step(value, reason=None):
        fields = {"heading": field(value, reason)}
        stable.apply(fields)
        return fields["heading"]
    assert step(270)["reason"] == "unstable_reading"
    assert step(270)["value"] == 270
    changed = step(290)
    assert changed["value"] is None
    assert changed["candidate_value"] == 290
    assert step(None, "no_text")["reason"] == "no_text"
    assert step(290)["value"] is None
    assert step(290)["value"] == 290
    stable.reset()
    assert step(290)["value"] is None


def test_north_zero_stabilizes_independently_of_failed_altitude():
    stable = Stabilizer(2)
    for _ in range(2):
        fields = {"heading": field(0), "altitude": field(None, "blank_roi")}
        stable.apply(fields)
    assert fields["heading"]["value"] == 0
    assert fields["altitude"]["value"] is None


def test_mailbox_drops_old_frame_after_disconnect_or_timeout():
    camera = LatestCamera(0, 800, 300, cv=object())
    camera.frame = Frame(None, 1, "2026-10-10T00:00:00Z", 10)
    camera.reason = None
    assert camera.snapshot(3, now=11)[0].sequence == 1
    assert camera.snapshot(3, now=14)[:2] == (None, "frame_timeout")
    camera._unavailable("camera_disconnected")
    assert camera.snapshot(3, now=11)[:2] == (None, "camera_disconnected")


def test_stale_frame_invalidates_even_successful_ocr(tmp_path):
    # Actual deterministic executable adapter. Exercise OCR boundary and saved output.
    binary = tmp_path / "ocr"
    binary.write_text('#!/bin/sh\nprintf \'[{"text":"270","score":0.9}]\'\n')
    binary.chmod(0o755)
    image = Image.open(CONFIG.parents[1] / "evaluation/fixtures/normal.png")
    frame = Frame(image, 12, "2026-10-10T00:00:00Z", 10)
    stable = Stabilizer(1)
    event = process_frame(frame, load_config(CONFIG), binary, tmp_path / "out",
                          "camera", stable, 5, clock=lambda: 16)
    assert event["health"]["reason"] == "stale_frame"
    assert all(item["value"] is None for item in event["observation"]["fields"].values())
    assert stable.history == {}
    import json
    saved = json.loads(Path(event["observation"]["evidence"]).with_name("observation.json").read_text())
    assert saved["fields"]["heading"]["reason"] == "stale_frame"


def test_disconnect_during_ocr_invalidates_output(tmp_path):
    class Disconnected:
        def snapshot(self, timeout):
            return None, "camera_disconnected", 1
    frame = Frame(Image.new("RGB", (800, 300)), 1, "2026-10-10T00:00:00Z", 10)
    event = process_frame(frame, load_config(CONFIG), "/missing", tmp_path, "camera",
                          Stabilizer(1), 5, Disconnected(), 1, clock=lambda: 11)
    assert event["health"]["reason"] == "camera_disconnected"
    assert all(item["reason"] == "camera_disconnected" for item in event["observation"]["fields"].values())


def test_replay_does_not_invent_live_capture_time(tmp_path):
    frame = Frame(Image.new("RGB", (800, 300)), 1, None, 10, 1250)
    event = process_frame(frame, load_config(CONFIG), "/missing", tmp_path, "video_file",
                          Stabilizer(), 5, clock=lambda: 1000)
    assert event["live_input"] is False
    assert event["frame_age_seconds"] is None
    assert event["observation"]["captured_at"] is None
    assert event["observation"]["media_time_ms"] == 1250


def test_latest_health_replaces_last_observation(tmp_path):
    import json
    writer = EventWriter(tmp_path)
    writer.emit({"event_type": "observation", "observation": {"fields": {"heading": field(270)}}})
    writer.emit(health_event("camera_disconnected"))
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["observation"] is None
    assert latest["health"]["reason"] == "camera_disconnected"
    assert len(writer.path.read_text().splitlines()) == 2


def test_watchdog_expires_previous_result_while_ocr_is_busy(tmp_path):
    import json
    camera = LatestCamera(0, 800, 300, cv=object())
    camera.frame = Frame(None, 9, "2026-10-10T00:00:00Z", 20)
    camera.reason = None
    stable = Stabilizer(1)
    stable.apply({"heading": field(270)})
    writer = EventWriter(tmp_path)
    writer.emit({"event_type": "observation", "input_mode": "camera",
                 "health": {"status": "available", "reason": None},
                 "observation": {"fields": {"heading": field(270)}}})
    writer.deadline = 19
    writer.monitor(camera, stable, 3, now=21)
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["health"]["reason"] == "stale_observation"
    assert latest["observation"] is None
    assert stable.history == {}
    writer.monitor(camera, stable, 3, now=25)
    assert writer.latest["health"]["reason"] == "frame_timeout"


def test_reconnect_during_ocr_invalidates_previous_generation(tmp_path):
    class Reconnected:
        def snapshot(self, timeout):
            return None, None, 2
    frame = Frame(Image.new("RGB", (800, 300)), 1, "2026-10-10T00:00:00Z", 10)
    event = process_frame(frame, load_config(CONFIG), "/missing", tmp_path, "camera",
                          Stabilizer(1), 5, Reconnected(), 1, clock=lambda: 11)
    assert event["health"]["reason"] == "camera_reconnected"
    assert all(item["value"] is None for item in event["observation"]["fields"].values())


def test_read_timeout_still_applies_after_ocr(tmp_path):
    class TimedOut:
        def snapshot(self, timeout):
            assert timeout == 3
            return None, "frame_timeout", 1
    frame = Frame(Image.new("RGB", (800, 300)), 1, "2026-10-10T00:00:00Z", 10)
    event = process_frame(frame, load_config(CONFIG), "/missing", tmp_path, "camera",
                          Stabilizer(1), 5, TimedOut(), 1, clock=lambda: 14, read_timeout=3)
    assert event["health"]["reason"] == "frame_timeout"


def test_real_video_sampling_and_end_of_file(tmp_path):
    cv = pytest.importorskip("cv2")
    import numpy as np
    path = tmp_path / "sample.avi"
    writer = cv.VideoWriter(str(path), cv.VideoWriter_fourcc(*"MJPG"), 4, (800, 300))
    assert writer.isOpened()
    for _ in range(8):
        writer.write(np.zeros((300, 800, 3), dtype=np.uint8))
    writer.release()
    frames = list(video_frames(path, 0.5))
    assert [frame.sequence for frame in frames] == [1, 3, 5, 7]
    assert [frame.media_time_ms for frame in frames] == [0, 500, 1000, 1500]
    assert all(frame.received_at is None for frame in frames)


def test_camera_worker_reconnects_and_releases(monkeypatch):
    monkeypatch.setattr(Image, "fromarray", lambda pixels: Image.new("RGB", (8, 3)))
    ready = Event()
    class Device:
        def __init__(self, cv, index):
            self.cv, self.index, self.reads = cv, index, 0
        def isOpened(self):
            return True
        def set(self, *args):
            return True
        def read(self):
            self.reads += 1
            if self.index == 0:
                return False, None
            if self.reads == 1:
                return True, object()
            ready.set()
            self.cv.unblock.wait(2)
            return False, None
        def release(self):
            self.cv.released += 1
    class CV:
        CAP_PROP_FRAME_WIDTH = CAP_PROP_FRAME_HEIGHT = CAP_PROP_BUFFERSIZE = COLOR_BGR2RGB = 1
        def __init__(self):
            self.opens, self.released = 0, 0
            self.unblock = Event()
        def VideoCapture(self, index):
            device = Device(self, self.opens)
            self.opens += 1
            return device
        def cvtColor(self, pixels, code):
            return pixels
    cv = CV()
    camera = LatestCamera(0, 8, 3, retry_seconds=0.01, cv=cv).start()
    try:
        assert ready.wait(2)
        frame, reason, generation = camera.snapshot(3)
        assert frame.sequence == 1 and reason is None
        assert generation == 2
    finally:
        camera.stop_event.set()
        cv.unblock.set()
        camera.close()
    assert cv.released == 2


@pytest.mark.parametrize("count", [0, -1])
def test_invalid_stable_frames(count):
    with pytest.raises(ValueError):
        Stabilizer(count)
