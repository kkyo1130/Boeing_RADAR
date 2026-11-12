"""Label simulator cockpit screenshots for YOLO MCP detection.

Run: python -m vision.label_mcp --images path/to/screenshots --output vision/data/mcp_detection
Drag a rectangle around the entire MCP and press Enter/Space. Press c to skip.
Requires a local graphical desktop and OpenCV.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import shutil
from pathlib import Path

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
CLASS_NAMES = ("mcp",)


def yolo_bbox(x, y, w, h, image_w, image_h):
    if min(w, h, image_w, image_h) <= 0:
        raise ValueError("Bounding box and image dimensions must be positive")
    if x < 0 or y < 0 or x + w > image_w or y + h > image_h:
        raise ValueError("Bounding box outside image")
    return ((x + w / 2) / image_w, (y + h / 2) / image_h,
            w / image_w, h / image_h)


def split_for_group(group: str, seed: int):
    digest = hashlib.sha256(f"{seed}:{group}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    return "train" if fraction < .8 else "val" if fraction < .9 else "test"


def annotate(images_dir: Path, output: Path, session: str, seed: int):
    import cv2
    images = sorted(p for p in images_dir.rglob("*") if p.suffix.lower() in EXTENSIONS)
    if not images:
        raise ValueError(f"No images found under {images_dir}")
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.csv"
    existing = {}
    if manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as f:
            existing = {row["source_path"]: row for row in csv.DictReader(f)}
    fields = ["source_path", "image_path", "label_path", "session_id", "split",
              "x", "y", "width", "height"]
    records = dict(existing)
    try:
        for path in images:
            source = str(path.resolve())
            if source in records:
                print(f"skip already labeled: {path.name}")
                continue
            image = cv2.imread(str(path))
            if image is None:
                print(f"skip unreadable: {path}")
                continue
            ih, iw = image.shape[:2]
            cv2.namedWindow("Select MCP (Enter=save, c=skip)", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Select MCP (Enter=save, c=skip)", 1100, 750)
            x, y, w, h = (int(v) for v in cv2.selectROI(
                "Select MCP (Enter=save, c=skip)", image, showCrosshair=True))
            cv2.destroyAllWindows()
            if w == 0 or h == 0:
                print(f"skipped: {path.name}")
                continue
            bbox = yolo_bbox(x, y, w, h, iw, ih)
            # Session is a capture session, not a frame. Same session never crosses splits.
            split = split_for_group(session, seed)
            name = hashlib.sha256(source.encode()).hexdigest()[:16] + path.suffix.lower()
            image_rel = f"images/{split}/{name}"
            label_rel = f"labels/{split}/{Path(name).stem}.txt"
            (output / image_rel).parent.mkdir(parents=True, exist_ok=True)
            (output / label_rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, output / image_rel)
            (output / label_rel).write_text(
                "0 " + " ".join(f"{v:.6f}" for v in bbox) + "\n", encoding="utf-8")
            records[source] = dict(source_path=source, image_path=image_rel,
                                   label_path=label_rel, session_id=session,
                                   split=split, x=x, y=y, width=w, height=h)
            with manifest_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(records.values())
            print(f"saved {split}: {path.name}")
    finally:
        cv2.destroyAllWindows()
    yaml_text = ("path: " + str(output.resolve()) +
                 "\ntrain: images/train\nval: images/val\ntest: images/test\n"
                 "names:\n  0: mcp\n")
    (output / "dataset.yaml").write_text(yaml_text, encoding="utf-8")
    print(f"manifest={manifest_path}")
    print("Note: collect multiple independent sessions until train/val/test all contain images.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--images", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("vision/data/mcp_detection"))
    p.add_argument("--session", required=True,
                   help="Unique capture-session identifier, e.g. sim_day1_angle1")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    annotate(args.images, args.output, args.session, args.seed)


if __name__ == "__main__":
    main()
