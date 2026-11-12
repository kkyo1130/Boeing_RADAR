"""Train a YOLO detector for the full MCP panel.

Requires optional dependency: pip install ultralytics
No weights or training images are bundled in this repository.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def validate_dataset(root: Path):
    # Apply the same pending-label and human-review integrity checks as fine-tuning.
    try:
        from .yolo_camera_data import load_dataset
    except ImportError:
        from yolo_camera_data import load_dataset
    load_dataset(root)
    manifest = root / "manifest.csv"
    if not manifest.exists():
        raise FileNotFoundError(f"Missing {manifest}; run vision.label_mcp first")
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("No annotated images")
    groups = {}
    for row in rows:
        split, session = row["split"], row["session_id"]
        if split not in ("train", "val", "test"):
            raise ValueError(f"Invalid split: {split}")
        groups.setdefault(session, set()).add(split)
        if not (root / row["image_path"]).is_file():
            raise FileNotFoundError(root / row["image_path"])
        if not (root / row["label_path"]).is_file():
            raise FileNotFoundError(root / row["label_path"])
    leaking = [session for session, splits in groups.items() if len(splits) > 1]
    if leaking:
        raise ValueError(f"Sessions across splits: {leaking}")
    counts = {s: sum(row["split"] == s for row in rows) for s in ("train", "val", "test")}
    if not counts["train"] or not counts["val"]:
        raise ValueError(f"Need at least one train and val image from distinct sessions: {counts}")
    return counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("vision/data/mcp_detection"))
    p.add_argument("--model", default="yolo11n.pt",
                   help="Ultralytics pretrained detection checkpoint")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=960)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--device", default="cpu",
                   help="cpu, mps, or a CUDA device index such as 0")
    p.add_argument("--project", default="vision/checkpoints/mcp_yolo")
    p.add_argument("--name", default="baseline")
    args = p.parse_args()
    counts = validate_dataset(args.data)
    # Blender-generated dataset.yaml can contain an absolute path from another machine.
    # Write a portable, local training config without modifying the source dataset.
    yaml_path = args.data.resolve() / "dataset_local.yaml"
    yaml_path.write_text(
        f"path: {args.data.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: mcp\n",
        encoding="utf-8",
    )
    print("Dataset counts:", counts, flush=True)
    from ultralytics import YOLO
    model = YOLO(args.model)
    model.train(data=str(yaml_path),
                epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                device=args.device, project=args.project, name=args.name)
    best = Path(model.trainer.best)
    print(f"Training finished. Best weights: {best}", flush=True)
    if counts["test"]:
        from ultralytics import YOLO
        metrics = YOLO(str(best)).val(data=str(yaml_path), split="test", device=args.device)
        print(f"Test metrics: precision={metrics.box.mp:.4f}, recall={metrics.box.mr:.4f}, "
              f"mAP50={metrics.box.map50:.4f}, mAP50-95={metrics.box.map:.4f}", flush=True)


if __name__ == "__main__":
    main()
