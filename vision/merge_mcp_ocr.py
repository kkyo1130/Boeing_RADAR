"""Merge extracted MCP OCR batches without filename/session collisions.

Usage:
 python vision/merge_mcp_ocr.py --input vision/data/ocr_batches --output vision/data/mcp_ocr_1004
"""
from __future__ import annotations
import argparse
import csv
import shutil
from collections import Counter
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True, help="Parent containing batch_01, batch_02, ...")
    p.add_argument("--output", type=Path, required=True, help="New merged dataset directory")
    args = p.parse_args()
    source = args.input.resolve()
    target = args.output.resolve()
    if target == source or source in target.parents or target in source.parents:
        p.error("Output must be outside the input directory")
    batches = sorted(x for x in source.glob("batch_*") if x.is_dir())
    if not batches:
        p.error(f"No batch_* directories under {source}")
    if target.exists() and any(target.iterdir()):
        p.error(f"Output directory is not empty: {target}; refusing to overwrite")
    rows_out = []
    planned = []
    seen_paths = set()
    split_counts = Counter()
    for batch in batches:
        labels = batch / "labels.csv"
        if not labels.is_file():
            raise FileNotFoundError(labels)
        with labels.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError(f"Empty labels: {labels}")
        for row in rows:
            split = row["split"]
            kind = row["kind"]
            value = row["text"]
            n = {"hdg": 3, "alt": 5}.get(kind)
            if split not in ("train", "val", "test") or n is None or len(value) != n or not value.isascii() or not value.isdigit():
                raise ValueError(f"Invalid label in {labels}: {row}")
            old_rel = Path(row["image_path"])
            if old_rel.is_absolute() or ".." in old_rel.parts:
                raise ValueError(f"Unsafe image path: {old_rel}")
            src = batch / old_rel
            if not src.is_file():
                raise FileNotFoundError(src)
            new_rel = Path(split) / kind / (batch.name + "_" + old_rel.name)
            if new_rel in seen_paths:
                raise ValueError(f"Duplicate output path: {new_rel}")
            seen_paths.add(new_rel)
            new_row = dict(row)
            new_row["image_path"] = new_rel.as_posix()
            new_row["session_id"] = f"{batch.name}_{row['session_id']}"
            new_row["source_image"] = f"{batch.name}/{row['source_image']}"
            rows_out.append(new_row)
            planned.append((src, target / new_rel))
            split_counts[(split, kind)] += 1
    # Preserve source labels exactly and only rename paths and session IDs.
    target.mkdir(parents=True, exist_ok=True)
    for src, dst in planned:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    fieldnames = list(rows_out[0])
    with (target / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    for split in ("train", "val", "test"):
        with (target / f"{split}.tsv").open("w", encoding="utf-8") as f:
            for row in rows_out:
                if row["split"] == split:
                    f.write(f"{row['image_path']}\t{row['text']}\n")
    print(f"Merged {len(batches)} batches into {target}: {len(rows_out)} OCR images")
    for split in ("train", "val", "test"):
        print(f"  {split}: HDG={split_counts[(split, 'hdg')]}, ALT={split_counts[(split, 'alt')]}")
    print("Original batches were not modified. Check sample images before training.")


if __name__ == "__main__":
    main()
