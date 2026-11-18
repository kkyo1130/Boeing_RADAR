"""Evaluate a saved single-digit CNN on untouched test.csv.

Supports the original v1 and manually upgraded v2 architectures.
The result is synthetic digit accuracy, NOT real Boeing MCP accuracy.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build_model(architecture: str):
    from torch import nn
    if architecture == "v2":
        return nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 10),
        )
    if architecture == "v1":
        return nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(32 * 8 * 8, 64), nn.ReLU(),
            nn.Linear(64, 10),
        )
    raise ValueError("architecture must be v1 or v2")


def evaluate(data: Path, labels: Path, checkpoint: Path, architecture: str):
    import torch
    import numpy as np
    from PIL import Image, ImageOps

    with labels.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"filename", "digit"}.issubset(rows[0]):
        raise ValueError("test CSV must contain filename,digit and at least one row")

    model = build_model(architecture)
    # Only load checkpoints created locally by the project's training script.
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(saved["model"])
    model.eval()
    confusion = [[0] * 10 for _ in range(10)]
    failures = []
    with torch.inference_mode():
        for row in rows:
            expected = int(row["digit"])
            if not 0 <= expected <= 9:
                raise ValueError(f"invalid digit: {expected}")
            with Image.open(data / row["filename"]) as original:
                img = ImageOps.pad(original.convert("L"), (32, 32))
                pixels = np.asarray(img, dtype=np.float32).copy() / 255.0
            tensor = torch.from_numpy(pixels).unsqueeze(0).unsqueeze(0)
            predicted = int(model(tensor).argmax(1).item())
            confusion[expected][predicted] += 1
            if predicted != expected:
                failures.append({"filename": row["filename"], "expected": expected, "predicted": predicted})
    total = len(rows)
    correct = sum(confusion[d][d] for d in range(10))
    report = {
        "architecture": architecture,
        "samples": total,
        "correct": correct,
        "accuracy": correct / total,
        "per_digit_accuracy": {
            str(d): (confusion[d][d] / sum(confusion[d]) if sum(confusion[d]) else None)
            for d in range(10)
        },
        "confusion_matrix": confusion,
        "failures": failures[:100],
        "note": "Synthetic single-digit test only; no real cockpit performance implied.",
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--architecture", choices=["v1", "v2"], default="v2")
    parser.add_argument("--report", type=Path, default=Path("vision/checkpoints/digits_v2/test_metrics.json"))
    args = parser.parse_args()
    result = evaluate(args.data, args.test, args.checkpoint, args.architecture)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"test_accuracy={result['accuracy']:.4f} ({result['correct']}/{result['samples']})")
    print("per_digit_accuracy:", result["per_digit_accuracy"])
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
