"""Normalize amber MCP digits while preserving OCR labels and split boundaries.

Example:
 python vision/preprocess_mcp_ocr.py --data vision/data/mcp_ocr_1004 --output vision/data/mcp_ocr_aligned --preview 12
"""
import argparse
import csv
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def amber_mask(im):
    """Amber display pixels: strong red, moderate green, weak blue."""
    import numpy as np
    a = np.asarray(im.convert("RGB"), dtype=np.int16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return (r > 105) & (g > 55) & (r > g * 1.12) & (g > b * 1.30) & ((r - b) > 65)


def find_digit_bounds(im, kind):
    import numpy as np
    mask = amber_mask(im)
    h, w = mask.shape
    # Ignore isolated highlights by requiring sufficient amber pixels per column/row.
    col = mask.sum(axis=0)
    row = mask.sum(axis=1)
    min_col = max(2, round(h * .035))
    min_row = max(2, round(w * .018))
    xs = np.flatnonzero(col >= min_col)
    ys = np.flatnonzero(row >= min_row)
    if len(xs) < 6 or len(ys) < 5:
        return None
    x1, x2 = int(xs[0]), int(xs[-1]) + 1
    y1, y2 = int(ys[0]), int(ys[-1]) + 1
    # Guard against picking orange background noise instead of display digits.
    if x2 - x1 < w * .15 or y2 - y1 < h * .10:
        return None
    return (x1, y1, x2, y2)


def align(im, kind):
    """Crop around detected amber digits, deskew modest tilt, fit fixed canvas."""
    import numpy as np
    bounds = find_digit_bounds(im, kind)
    if bounds is None:
        return None
    x1, y1, x2, y2 = bounds
    pw, ph = x2 - x1, y2 - y1
    pad_x, pad_y = max(3, round(pw * .09)), max(3, round(ph * .22))
    box = (max(0, x1 - pad_x), max(0, y1 - pad_y),
           min(im.width, x2 + pad_x), min(im.height, y2 + pad_y))
    crop = im.crop(box)
    # Choose angle that makes amber pixels most horizontally concentrated.
    # Avoid excessive correction; strong perspective distortion is not handled.
    best, best_score = crop, -1.
    for angle in (-12, -9, -6, -3, 0, 3, 6, 9, 12):
        rotated = crop.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(12, 14, 16))
        m = amber_mask(rotated)
        rows = m.sum(axis=1).astype(float)
        if rows.sum() < 12:
            continue
        score = float((rows ** 2).sum() / (rows.sum() ** 2))
        if score > best_score:
            best, best_score = rotated, score
    bounds2 = find_digit_bounds(best, kind)
    if bounds2 is not None:
        a, b, c, d = bounds2
        px, py = max(3, round((c-a)*.08)), max(3, round((d-b)*.22))
        best = best.crop((max(0,a-px), max(0,b-py), min(best.width,c+px), min(best.height,d+py)))
    target_w = 36 * (3 if kind == "hdg" else 5)
    target_h = 48
    # Preserve aspect ratio, center on dark background.
    result = ImageOps.contain(best, (target_w - 8, target_h - 6), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (12, 14, 16))
    canvas.paste(result, ((target_w-result.width)//2, (target_h-result.height)//2))
    return canvas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preview", type=int, default=12)
    p.add_argument("--strict", action="store_true", help="Fail if digit localization fails")
    args = p.parse_args()
    data, output = args.data.resolve(), args.output.resolve()
    if data == output or data in output.parents or output in data.parents:
        p.error("Input and output must be separate directories")
    if output.exists() and any(output.iterdir()):
        p.error(f"Output directory is not empty: {output}")
    with (data / "labels.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        p.error("Empty labels.csv")
    output.mkdir(parents=True, exist_ok=True)
    failed = []
    for row in rows:
        rel = Path(row["image_path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe path: {rel}")
        with Image.open(data / rel) as f:
            im = ImageOps.exif_transpose(f).convert("RGB")
        result = align(im, row["kind"])
        if result is None:
            failed.append(str(rel))
            if args.strict:
                raise RuntimeError(f"No amber digits detected in {rel}")
            # Keep sample rather than silently dropping its label.
            result = ImageOps.pad(im, (36 * len(row["text"]), 48), color=(12,14,16))
        dest = output / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        result.save(dest)
    with (output / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for split in ("train", "val", "test"):
        with (output / f"{split}.tsv").open("w", encoding="utf-8") as f:
            for row in rows:
                if row["split"] == split:
                    f.write(f"{row['image_path']}\t{row['text']}\n")
    (output / "failed_detection.txt").write_text("\n".join(failed), encoding="utf-8")
    print(f"Aligned {len(rows)} crops into {output}; fallback images: {len(failed)}")
    if args.preview:
        rng = random.Random(42)
        selected = []
        for kind in ("hdg", "alt"):
            candidates = [r for r in rows if r["kind"] == kind]
            selected += rng.sample(candidates, min(args.preview // 2, len(candidates)))
        preview = Image.new("RGB", (650, max(1,len(selected))*110), "#202020")
        draw = ImageDraw.Draw(preview)
        for i, row in enumerate(selected):
            with Image.open(data / row["image_path"]) as f:
                original = f.convert("RGB")
            original.thumbnail((235, 75))
            with Image.open(output / row["image_path"]) as f:
                aligned = f.convert("RGB")
            preview.paste(original, (90, i*110+18))
            preview.paste(aligned, (390, i*110+18))
            draw.text((8, i*110+28), f"{row['kind']} {row['text']}", fill="white")
        preview.save(output / "preview.png")
        print(f"Preview: {output / 'preview.png'}")
    print("Check preview.png and failed_detection.txt BEFORE training; source data untouched.")


if __name__ == "__main__":
    main()
