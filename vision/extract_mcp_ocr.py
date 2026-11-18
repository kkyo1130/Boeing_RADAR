"""Extract HDG/ALT OCR crops from Blender synthetic renders.

Example:
  python vision/extract_mcp_ocr.py --dataset vision/data/mcp_blender_v8

Requires: Pillow. The original YOLO dataset is not modified.
"""
import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


def crop_box(row, prefix, size, padding):
    width, height = size
    cx, cy, bw, bh = (float(row[f"{prefix}_{field}"]) for field in ("cx", "cy", "w", "h"))
    if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < bw <= 1 and 0 < bh <= 1):
        raise ValueError(f"Invalid {prefix} normalized box: {(cx, cy, bw, bh)}")
    left = (cx - bw * (0.5 + padding)) * width
    right = (cx + bw * (0.5 + padding)) * width
    top = (cy - bh * (0.5 + padding)) * height
    bottom = (cy + bh * (0.5 + padding)) * height
    bounds = (max(0, round(left)), max(0, round(top)),
              min(width, round(right)), min(height, round(bottom)))
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError(f"Empty {prefix} crop: {bounds}")
    return bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Dataset containing images/{split} and ocr_manifest.csv")
    parser.add_argument("--output", type=Path, default=None,
                        help="Defaults to <dataset>/ocr")
    parser.add_argument("--padding", type=float, default=0.04,
                        help="Fractional padding on each side of display bounding box")
    parser.add_argument("--height", type=int, default=64,
                        help="Output crop height; width preserves aspect ratio")
    parser.add_argument("--min-width", type=int, default=24,
                        help="Reject crops narrower than this before resizing")
    args = parser.parse_args()
    if not 0 <= args.padding <= 0.5:
        parser.error("--padding must be between 0 and 0.5")
    if args.height < 1 or args.min_width < 1:
        parser.error("--height and --min-width must be positive")
    dataset = args.dataset.resolve()
    output = (args.output or dataset / "ocr").resolve()
    source_csv = dataset / "ocr_manifest.csv"
    if not source_csv.is_file():
        raise FileNotFoundError(source_csv)
    with source_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Empty ocr_manifest.csv")

    records = []
    counts = Counter()
    for row in rows:
        split = row["split"]
        if split not in {"train", "val", "test"}:
            raise ValueError(f"Invalid split: {split}")
        rel_image = Path(row["image_path"])
        if rel_image.is_absolute() or ".." in rel_image.parts:
            raise ValueError(f"Unsafe image path: {rel_image}")
        source = dataset / rel_image
        if not source.is_file():
            raise FileNotFoundError(source)
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        for prefix, kind, value_key, digits in (
            ("hdg", "hdg", "heading", 3),
            ("alt", "alt", "altitude", 5),
        ):
            value = row[value_key]
            if len(value) != digits or not value.isascii() or not value.isdigit():
                raise ValueError(f"Invalid {kind} ground truth: {value!r}")
            bounds = crop_box(row, prefix, image.size, args.padding)
            crop = image.crop(bounds)
            if crop.width < args.min_width:
                raise ValueError(f"{source}: {kind} width {crop.width}px is too small")
            new_width = max(1, round(crop.width * args.height / crop.height))
            crop = crop.resize((new_width, args.height), Image.Resampling.LANCZOS)
            # Include the kind in the path; avoid accidental collisions across sessions.
            name = rel_image.stem + ".png"
            rel_output = Path(split) / kind / name
            target = output / rel_output
            target.parent.mkdir(parents=True, exist_ok=True)
            crop.save(target)
            records.append({
                "image_path": str(rel_output),
                "source_image": str(rel_image),
                "split": split,
                "kind": kind,
                "text": value,
                "session_id": row["session_id"],
                "crop_x1": bounds[0],
                "crop_y1": bounds[1],
                "crop_x2": bounds[2],
                "crop_y2": bounds[3],
            })
            counts[(split, kind)] += 1

    output.mkdir(parents=True, exist_ok=True)
    with (output / "labels.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    for split in ("train", "val", "test"):
        with (output / f"{split}.tsv").open("w", encoding="utf-8") as handle:
            for record in records:
                if record["split"] == split:
                    handle.write(f'{record["image_path"]}\t{record["text"]}\n')
    print(f"OCR dataset: {output}")
    print(f"Total crops: {len(records)} from {len(rows)} renders")
    for split in ("train", "val", "test"):
        print(f"  {split}: HDG={counts[(split, 'hdg')]}, ALT={counts[(split, 'alt')]}")
    print("Inspect crops before OCR training; boxes describe display windows, not individual digits.")


if __name__ == "__main__":
    main()
