"""MCP image processing and OCR. Regions are calibrated for a fixed camera."""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Protocol
import re

@dataclass(frozen=True)
class Regions:
    heading: tuple[int, int, int, int]
    altitude: tuple[int, int, int, int]

    @classmethod
    def from_json(cls, data: dict) -> "Regions":
        return cls(tuple(data["heading"]), tuple(data["altitude"]))

def crop(image, region):
    x, y, w, h = map(int, region)
    height, width = image.shape[:2]
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError("ROI is outside the image")
    return image[y:y+h, x:x+w]

def preprocess(image):
    import cv2
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

class Reader(Protocol):
    def read(self, image) -> tuple[str, float]: ...

class TesseractReader:
    """Tesseract pre-trained digit OCR. Confidence is a heuristic, not calibrated."""
    def read(self, image) -> tuple[str, float]:
        import pytesseract
        from pytesseract import Output
        data = pytesseract.image_to_data(
            preprocess(image), config="--psm 7 -c tessedit_char_whitelist=0123456789",
            output_type=Output.DICT,
        )
        pairs = [(t.strip(), float(c)) for t, c in zip(data["text"], data["conf"])
                 if t.strip() and float(c) >= 0]
        digits = "".join(t for t, _ in pairs)
        confidence = min((c for _, c in pairs), default=0.0) / 100.0
        return digits, confidence

@dataclass(frozen=True)
class Recognition:
    altitude: int
    heading: int
    confidence: float

def parse_reading(alt_text: str, hdg_text: str, alt_conf: float, hdg_conf: float,
                  min_confidence: float = 0.65) -> Recognition | None:
    if not re.fullmatch(r"\d{4,5}", alt_text) or not re.fullmatch(r"\d{3}", hdg_text):
        return None
    altitude, heading = int(alt_text), int(hdg_text)
    if altitude > 99999 or not 0 <= heading <= 359:
        return None
    confidence = min(alt_conf, hdg_conf)
    if not 0 <= confidence <= 1 or confidence < min_confidence:
        return None
    return Recognition(altitude, heading, confidence)

def recognize(image, regions: Regions, reader: Reader, min_confidence: float = 0.65):
    alt_text, alt_conf = reader.read(crop(image, regions.altitude))
    hdg_text, hdg_conf = reader.read(crop(image, regions.heading))
    return parse_reading(alt_text, hdg_text, alt_conf, hdg_conf, min_confidence)

class Stabilizer:
    """Require repeated, matching complete readings; never invent missing values."""
    def __init__(self, window: int = 5, required: int = 4):
        if not 1 <= required <= window:
            raise ValueError("required must be in 1..window")
        self.window, self.required = window, required
        self.samples: list[Recognition | None] = []

    def push(self, sample: Recognition | None) -> Recognition | None:
        self.samples.append(sample)
        self.samples = self.samples[-self.window:]
        if len(self.samples) < self.window:
            return None
        valid = [s for s in self.samples if s is not None]
        counts = Counter((s.altitude, s.heading) for s in valid)
        if not counts:
            return None
        pair, count = counts.most_common(1)[0]
        if count < self.required:
            return None
        return Recognition(pair[0], pair[1], min(s.confidence for s in valid
                           if (s.altitude, s.heading) == pair))
