"""Create reproducible original digit-display samples and ground-truth CSV.

This is a synthetic baseline, NOT a faithful certified Boeing MCP rendering.
"""
import argparse
import csv
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def generate(output: Path, count: int = 500, seed: int = 42):
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    output.mkdir(parents=True, exist_ok=True)
    labels = []
    for index in range(count):
        altitude = rng.randrange(0, 50001, 100)
        heading = rng.randrange(360)
        image = Image.new("RGB", (800, 180), (14, 21, 21))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", rng.randrange(50, 65))
        except OSError:
            font = ImageFont.load_default()
        brightness = rng.randrange(155, 256)
        color = (rng.randrange(20, 75), brightness, rng.randrange(45, 130))
        draw.rectangle((25, 20, 335, 155), outline=(90, 110, 110), width=3)
        draw.rectangle((405, 20, 775, 155), outline=(90, 110, 110), width=3)
        draw.text((45, 55), f"{heading:03d}", font=font, fill=color)
        draw.text((425, 55), f"{altitude:05d}", font=font, fill=color)
        if rng.random() < 0.5:
            image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.1, 0.8)))
        name = f"synthetic_{index:05d}.png"
        image.save(output / name)
        labels.append({"filename": name, "altitude": altitude, "heading": heading,
                       "source": "synthetic", "seed": seed})
    with (output / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "altitude", "heading", "source", "seed"])
        writer.writeheader()
        writer.writerows(labels)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("vision/data/boeing_737/synthetic"))
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.output, args.count, args.seed)
