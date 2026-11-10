"""Generate labeled synthetic *single-digit* crops for supervised training.

These are original synthetic glyph images, not real Boeing cockpit photos.
"""
from __future__ import annotations
import argparse
import csv
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def generate(output: Path, count: int = 20000, seed: int = 42):
    if count < 10:
        raise ValueError("count must be >= 10")
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        digit = index % 10  # guaranteed balanced classes
        size = rng.randint(25, 40)
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", size)
        except OSError:
            font = ImageFont.load_default()
        bg = rng.randint(0, 50)
        image = Image.new("L", (64, 64), bg)
        draw = ImageDraw.Draw(image)
        bbox = draw.textbbox((0, 0), str(digit), font=font)
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = (64-w)//2 - bbox[0] + rng.randint(-5, 5)
        y = (64-h)//2 - bbox[1] + rng.randint(-5, 5)
        draw.text((x, y), str(digit), font=font, fill=rng.randint(150, 255))
        image = image.rotate(rng.uniform(-9, 9), resample=Image.Resampling.BILINEAR,
                             fillcolor=bg)
        if rng.random() < 0.6:
            image = image.filter(ImageFilter.GaussianBlur(rng.uniform(.1, 1.2)))
        name = f"digit_{index:06d}.png"
        image.save(output / name)
        rows.append({"filename": name, "digit": digit, "session_id": f"batch_{index//100}"})
    # Split by generated batch rather than individual frames.
    # Keep class balance by assigning full batches (each has 10 digits).
    with (output / "train.csv").open("w", newline="", encoding="utf-8") as train_f, \
         (output / "val.csv").open("w", newline="", encoding="utf-8") as val_f, \
         (output / "test.csv").open("w", newline="", encoding="utf-8") as test_f:
        writers = [csv.DictWriter(f, fieldnames=rows[0].keys()) for f in (train_f, val_f, test_f)]
        for writer in writers:
            writer.writeheader()
        for row in rows:
            batch = int(row["session_id"].split("_")[1])
            writers[0 if batch % 10 < 8 else 1 if batch % 10 == 8 else 2].writerow(row)
    print(f"Generated {count} labeled digit crops in {output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("vision/data/boeing_737/digits"))
    parser.add_argument("--count", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.output, args.count, args.seed)
