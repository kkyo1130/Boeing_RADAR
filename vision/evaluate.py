"""Evaluate OCR on labeled images; report coverage and exact-match accuracy.

Expected labels.csv columns: filename, altitude, heading. All images must share
the same calibrated pixel ROI, so synthetic and webcam sessions are evaluated separately.
"""
import argparse
import csv
import json
from pathlib import Path
import cv2
from vision.core import Regions, TesseractReader, recognize

def evaluate(directory: Path, roi_file: Path, min_confidence: float = 0.65):
    with roi_file.open(encoding="utf-8") as f:
        regions = Regions.from_json(json.load(f))
    reader = TesseractReader()
    rows = list(csv.DictReader((directory / "labels.csv").open(encoding="utf-8", newline="")))
    if not rows:
        raise ValueError("No labeled samples")
    alt_ok = hdg_ok = both_ok = accepted = 0
    for row in rows:
        path = directory / row["filename"]
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Cannot read image: {path}")
        result = recognize(image, regions, reader, min_confidence)
        if result is None:
            continue
        accepted += 1
        alt_match = result.altitude == int(row["altitude"])
        hdg_match = result.heading == int(row["heading"])
        alt_ok += alt_match
        hdg_ok += hdg_match
        both_ok += alt_match and hdg_match
    n = len(rows)
    return {
        "total": n,
        "accepted": accepted,
        "coverage": accepted / n,
        "alt_exact_total": alt_ok / n,
        "hdg_exact_total": hdg_ok / n,
        "both_exact_total": both_ok / n,
        "both_exact_accepted": both_ok / accepted if accepted else None,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--roi", type=Path, required=True)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.data, args.roi, args.min_confidence), indent=2))
