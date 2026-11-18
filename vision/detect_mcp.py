"""Find the MCP in a cockpit image and save a crop for inspection.

This detects only the whole MCP, NOT HDG/ALT displays. Crops cannot yet be
fed directly into the synthetic fixed-slot OCR without real-layout calibration.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def detect(image: Path, weights: Path, output: Path, conf: float):
    import cv2
    from ultralytics import YOLO
    frame = cv2.imread(str(image))
    if frame is None:
        raise ValueError(f"Cannot read image: {image}")
    results = YOLO(str(weights)).predict(source=frame, conf=conf, verbose=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        print(json.dumps({"detected": False, "image": str(image)}))
        return
    idx = int(boxes.conf.argmax().item())
    xyxy = boxes.xyxy[idx].cpu().numpy().astype(int).tolist()
    x1, y1, x2, y2 = xyxy
    h, w = frame.shape[:2]
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Invalid detected bounding box")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), frame[y1:y2, x1:x2]):
        raise IOError(f"Could not save {output}")
    print(json.dumps({"detected": True, "confidence": float(boxes.conf[idx]),
                      "bbox_xyxy": [x1, y1, x2, y2],
                      "crop": str(output)}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("vision/data/mcp_crop.png"))
    p.add_argument("--conf", type=float, default=.4)
    args = p.parse_args()
    detect(args.image, args.weights, args.output, args.conf)


if __name__ == "__main__":
    main()
