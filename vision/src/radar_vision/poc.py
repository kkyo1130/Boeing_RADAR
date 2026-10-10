"""Still-image PoC. Scores are uncalibrated; no flight safety decision here."""
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, ImageStat


def parse_field(rows, unit, minimum_score):
    if not rows:
        return {"value": None, "raw_text": "", "model_score": None, "reason": "no_text"}
    text = " ".join(row["text"] for row in rows)
    score = min(float(row["score"]) for row in rows)
    result = {"value": None, "raw_text": text, "model_score": score, "reason": None}
    if not math.isfinite(score) or not 0 <= score <= 1:
        result.update(model_score=None, reason="invalid_score")
    elif len(rows) != 1 or not re.fullmatch(
            r"(?:[0-9]{1,2})?\.[0-9]{2,3}" if unit == "mach" else
            r"[0-9]{1,3}" if unit == "knots" else r"[0-9]{1,5}", text):
        result["reason"] = "invalid_format"
    elif score < minimum_score:
        result["reason"] = "low_model_score"
    else:
        value = float(text) if unit == "mach" else int(text) * (100 if unit == "FL" else 1)
        if unit == "degrees" and value > 359:
            result["reason"] = "out_of_range"
        else:
            result["value"] = value
    return result


def load_config(path):
    config = json.loads(Path(path).read_text())
    size = config["image_size"]
    if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
        raise ValueError("image_size must contain two positive integers")
    field_units = [("altitude", {"feet", "FL"}), ("heading", {"degrees"})]
    if "speed" in config:
        field_units.append(("speed", {"knots", "mach"}))
    for field, units in field_units:
        item = config[field]
        if item["unit"] not in units:
            raise ValueError("unsupported field unit")
        box = item["roi"]
        if (len(box) != 4 or any(type(x) is not int for x in box)
                or not 0 <= box[0] < box[2] <= size[0]
                or not 0 <= box[1] < box[3] <= size[1]):
            raise ValueError("ROI must be inside configured image size")
    preprocessing_options = [config.get("ocr_preprocessing", {})] + [
        config[field].get("ocr_preprocessing", {}) for field, _ in field_units]
    for preprocessing in preprocessing_options:
        if (not isinstance(preprocessing, dict)
                or set(preprocessing) - {"scale", "grayscale"}
                or type(preprocessing.get("scale", 1)) is not int
                or not 1 <= preprocessing.get("scale", 1) <= 8
                or type(preprocessing.get("grayscale", False)) is not bool):
            raise ValueError("invalid ocr_preprocessing: scale 1..8 and grayscale boolean")
    threshold = config["minimum_model_score"]
    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise ValueError("invalid minimum_model_score")
    return config


def recognize(path, config, ocr_binary, output_dir, captured_at=None):
    # File processing time is not camera capture time. Missing capture time stays null.
    if captured_at is not None:
        stamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("captured_at requires timezone")
        captured_at = stamp.astimezone(timezone.utc).isoformat()
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if list(image.size) != config["image_size"]:
        raise ValueError("image size differs from ROI config; do not silently resize")
    frame_id = str(uuid4())
    destination = Path(output_dir) / frame_id
    destination.mkdir(parents=True)
    image.save(destination / "frame.png")
    fields = {}
    for name in ("altitude", "heading", *(["speed"] if "speed" in config else [])):
        item = config[name]
        crop = image.crop(item["roi"])
        evidence = destination / (name + ".png")
        crop.save(evidence)
        ocr_evidence = evidence
        preprocessing = item.get("ocr_preprocessing", config.get("ocr_preprocessing"))
        if preprocessing:
            prepared = crop.convert("L") if preprocessing.get("grayscale", False) else crop
            scale = preprocessing.get("scale", 1)
            prepared = prepared.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
            ocr_evidence = destination / (name + "-ocr.png")
            prepared.save(ocr_evidence)
        # Uniform crops are unreadable, regardless of any OCR hallucination.
        contrast = ImageStat.Stat(crop.convert("L")).stddev[0]
        if contrast < 1:
            result = {"value": None, "raw_text": "", "model_score": None, "reason": "blank_roi"}
        else:
            try:
                process = subprocess.run([str(Path(ocr_binary).resolve()), str(ocr_evidence.resolve())],
                                         capture_output=True, text=True, check=True, timeout=20)
                result = parse_field(json.loads(process.stdout), item["unit"], config["minimum_model_score"])
            except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
                result = {"value": None, "raw_text": "", "model_score": None, "reason": "ocr_unavailable"}
        result.update(unit="feet" if name == "altitude" else item["unit"], roi=item["roi"],
                      contrast_stddev=round(contrast, 3), evidence=str(evidence))
        if preprocessing:
            result.update(ocr_evidence=str(ocr_evidence),
                          ocr_preprocessing={"grayscale": preprocessing.get("grayscale", False),
                                             "scale": preprocessing.get("scale", 1)})
        fields[name] = result
    observation = {"schema_version": "vision-poc/2" if "speed" in config else "vision-poc/1", "source": "cockpit_image",
                   "frame_id": frame_id, "captured_at": captured_at,
                   "processed_at": datetime.now(timezone.utc).isoformat(),
                   "capture_time_known": captured_at is not None,
                   "input_mode": "still_image", "score_calibrated": False,
                   "fields": fields, "evidence": str(destination / "frame.png")}
    (destination / "observation.json").write_text(json.dumps(observation, indent=2))
    return observation
