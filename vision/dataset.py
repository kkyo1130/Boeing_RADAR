"""Reproducible, leakage-aware train/validation/test splitting for labeled photos."""
from __future__ import annotations
import argparse
import csv
import hashlib
from pathlib import Path

def split_dataset(source: Path, output: Path, seed: int = 42):
    with source.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("Empty dataset")
    required = {"filename", "altitude", "heading"}
    if not required.issubset(rows[0]):
        raise ValueError("Expected filename, altitude and heading columns")
    groups = {}
    for row in rows:
        if not row["altitude"] or not row["heading"]:
            continue
        # Real frames should share a session_id, original_id, or source group.
        group = row.get("session_id") or row.get("original_id") or row["filename"]
        groups.setdefault(group, []).append(row)
    output.mkdir(parents=True, exist_ok=True)
    partitions = {"train": [], "val": [], "test": []}
    for group, items in groups.items():
        h = hashlib.sha256(f"{seed}:{group}".encode()).digest()
        bucket = int.from_bytes(h[:8], "big") / (1 << 64)
        split = "train" if bucket < .8 else "val" if bucket < .9 else "test"
        partitions[split].extend(items)
    for name, items in partitions.items():
        with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(items)
    return {k: len(v) for k, v in partitions.items()}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(split_dataset(args.labels, args.output, args.seed))
