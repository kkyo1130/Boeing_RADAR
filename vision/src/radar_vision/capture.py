"""Camera acquisition is separate from OCR so slow inference cannot queue old frames."""
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from time import monotonic


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def opencv():
    try:
        import cv2
    except ImportError as error:
        raise ValueError("Install capture dependencies: pip install -e './vision[capture]'") from error
    return cv2


@dataclass(frozen=True)
class Frame:
    image: object
    sequence: int
    received_at: str | None
    received_monotonic: float
    media_time_ms: float | None = None


class LatestCamera:
    """One-slot mailbox. Camera reconnects in the reader; OCR never owns the device."""
    def __init__(self, index, width, height, retry_seconds=1.0, cv=None):
        self.cv = cv or opencv()
        self.index, self.width, self.height = index, width, height
        self.retry_seconds = retry_seconds
        self.stop_event = Event()
        self.lock = Lock()
        self.frame = None
        self.reason = "camera_starting"
        self.sequence = 0
        self.generation = 0
        self.thread = Thread(target=self._read, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def snapshot(self, timeout, now=None):
        now = monotonic() if now is None else now
        with self.lock:
            frame, reason, generation = self.frame, self.reason, self.generation
        if reason:
            return None, reason, generation
        if frame is None or now - frame.received_monotonic > timeout:
            return None, "frame_timeout", generation
        return frame, None, generation

    def _unavailable(self, reason):
        with self.lock:
            self.frame, self.reason = None, reason

    def _read(self):
        from PIL import Image
        while not self.stop_event.is_set():
            capture = None
            try:
                capture = self.cv.VideoCapture(self.index)
                if not capture.isOpened():
                    self._unavailable("camera_unavailable")
                else:
                    capture.set(self.cv.CAP_PROP_FRAME_WIDTH, self.width)
                    capture.set(self.cv.CAP_PROP_FRAME_HEIGHT, self.height)
                    capture.set(self.cv.CAP_PROP_BUFFERSIZE, 1)
                    with self.lock:
                        self.generation += 1
                    while not self.stop_event.is_set():
                        ok, pixels = capture.read()
                        if not ok or pixels is None:
                            self._unavailable("camera_disconnected")
                            break
                        received, stamp = monotonic(), utc_now()
                        image = Image.fromarray(self.cv.cvtColor(pixels, self.cv.COLOR_BGR2RGB))
                        with self.lock:
                            self.sequence += 1
                            self.frame = Frame(image, self.sequence, stamp, received)
                            self.reason = None
            except Exception:
                self._unavailable("camera_error")
            finally:
                if capture is not None:
                    capture.release()
            self.stop_event.wait(self.retry_seconds)

    def close(self):
        self.stop_event.set()
        # A stalled native read must not prevent Ctrl-C. Worker releases on return.
        self.thread.join(timeout=1)


def video_frames(path, sample_seconds, cv=None):
    """Offline replay: media position is never substituted for UTC capture time."""
    from PIL import Image
    cv = cv or opencv()
    capture = cv.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot open video file")
        fps = capture.get(cv.CAP_PROP_FPS)
        if not 0 < fps < 1000:
            raise ValueError("Video FPS unavailable; cannot sample media timeline")
        interval = max(1, round(fps * sample_seconds))
        sequence = 0
        while True:
            ok, pixels = capture.read()
            if not ok:
                break
            sequence += 1
            if (sequence - 1) % interval:
                continue
            image = Image.fromarray(cv.cvtColor(pixels, cv.COLOR_BGR2RGB))
            yield Frame(image, sequence, None, monotonic(), (sequence - 1) * 1000 / fps)
    finally:
        capture.release()
