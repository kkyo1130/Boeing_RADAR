"""Preview synthetic MCP and HDG/ALT bounding boxes over rendered PNGs.

Usage: python vision/preview_mcp_labels.py --dataset vision/data/mcp_blender_v7
Requires Pillow (pip install Pillow).
"""
import argparse
import csv
from pathlib import Path
from PIL import Image, ImageDraw


def rectangle(draw, box, size, color, label):
    cx, cy, w, h = map(float, box)
    width, height = size
    xy = ((cx - w / 2) * width, (cy - h / 2) * height,
          (cx + w / 2) * width, (cy + h / 2) * height)
    draw.rectangle(xy, outline=color, width=3)
    draw.text((xy[0] + 3, max(0, xy[1] - 17)), label, fill=color)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    output = args.dataset / "previews"
    output.mkdir(parents=True, exist_ok=True)
    with (args.dataset / "ocr_manifest.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows[:args.limit]:
        path = args.dataset / row["image_path"]
        with Image.open(path) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        label_path = args.dataset / row["image_path"].replace("images/", "labels/").replace(".png", ".txt")
        label = label_path.read_text(encoding="utf-8").strip().split()
        if len(label) != 5 or label[0] != "0":
            raise ValueError(f"Unexpected YOLO label: {label_path}")
        rectangle(draw, label[1:], image.size, "#00ff66", "MCP")
        rectangle(draw, [row[f"hdg_{key}"] for key in ("cx", "cy", "w", "h")],
                  image.size, "#ffb000", "HDG " + row["heading"])
        rectangle(draw, [row[f"alt_{key}"] for key in ("cx", "cy", "w", "h")],
                  image.size, "#00dfff", "ALT " + row["altitude"])
        image.save(output / path.name)
        print(output / path.name)


if __name__ == "__main__":
    main()
