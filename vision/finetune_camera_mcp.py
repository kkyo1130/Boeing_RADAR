"""Fine-tune v3 OCR on original training data plus verified webcam crops.

Example:
 python vision/finetune_camera_mcp.py --base vision/data/mcp_ocr_aligned \
   --camera vision/data/camera_batches/batch_002 \
   --init-checkpoints vision/checkpoints/mcp_ocr_v3 \
   --output vision/checkpoints/mcp_ocr_v4 --epochs 15

Original data and v3 checkpoints are never modified or deleted.
Use --real-test with a separately captured, diverse, unseen test dataset.
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


FIELDS = ["image_path", "kind", "text", "split", "session_id", "source_image"]


def load(root):
    with (root / "labels.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def verify(root, rows, splits):
    if not rows:
        raise ValueError(f"No labels in {root}")
    for row in rows:
        kind = row.get("kind")
        value = row.get("text", "")
        rel = Path(row.get("image_path", ""))
        if (kind not in ("hdg", "alt") or len(value) != (3 if kind == "hdg" else 5)
                or not value.isascii() or not value.isdigit()
                or row.get("split") not in splits
                or rel.is_absolute() or ".." in rel.parts
                or not (root / rel).is_file()):
            raise ValueError(f"Invalid record in {root}: {row}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True, help="Original diverse OCR dataset with train/val/test")
    p.add_argument("--camera", type=Path, required=True, help="Verified camera training batch")
    p.add_argument("--init-checkpoints", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("vision/checkpoints/mcp_ocr_v4"))
    p.add_argument("--real-test", type=Path, help="Independent unseen webcam test dataset; must contain test split")
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    args = p.parse_args()
    base, camera = args.base.resolve(), args.camera.resolve()
    output = args.output.resolve()
    if base == camera or output in (base, camera) or base in output.parents or camera in output.parents:
        p.error("Keep output separate from input datasets")
    if args.epochs < 1:
        p.error("--epochs must be positive")
    if any(not (args.init_checkpoints / f"{kind}_best.pt").is_file() for kind in ("hdg", "alt")):
        p.error("Missing original HDG/ALT checkpoints")
    original, cam = load(base), load(camera)
    verify(base, original, {"train", "val", "test"})
    verify(camera, cam, {"train"})
    for kind in ("hdg", "alt"):
        for split in ("train", "val", "test"):
            if not any(r["kind"] == kind and r["split"] == split for r in original):
                p.error(f"Base dataset missing {kind}/{split}")
        if not any(r["kind"] == kind for r in cam):
            p.error(f"Camera dataset missing {kind}")
    distinct = {kind: sorted({r["text"] for r in cam if r["kind"] == kind}) for kind in ("hdg", "alt")}
    print("Camera labels:", json.dumps(distinct))
    if any(len(values) == 1 for values in distinct.values()):
        print("WARNING: single-value camera batch; this does not prove generalization.")
    merged = output / "merged_training_data"
    if merged.exists():
        p.error(f"Merged output exists: {merged}; choose a new --output to avoid overwriting")
    output.mkdir(parents=True, exist_ok=True)
    merged.mkdir()
    rows_out = []
    # Never copy webcam frames into validation or test: they were captured in the same session.
    for source, tag, rows in ((base, "base", original), (camera, "camera", cam)):
        for i, row in enumerate(rows):
            split, kind = row["split"], row["kind"]
            suffix = Path(row["image_path"]).suffix or ".png"
            rel = Path(split) / kind / f"{tag}_{i:06d}{suffix}"
            dst = merged / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / row["image_path"], dst)
            item = dict(row)
            item["image_path"] = rel.as_posix()
            item["session_id"] = f"{tag}_{row.get('session_id', 'unknown')}"
            item["source_image"] = f"{tag}/{row.get('source_image', row['image_path'])}"
            rows_out.append({key: item.get(key, "") for key in FIELDS})
    with (merged / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows_out)
    print("Merged counts:", dict(Counter((r["split"], r["kind"]) for r in rows_out)), flush=True)
    script = Path(__file__).with_name("train_mcp_ocr_v2.py")
    command = [sys.executable, str(script), "--data", str(merged),
               "--output", str(output), "--init-checkpoints", str(args.init_checkpoints),
               "--epochs", str(args.epochs), "--device", args.device, "--augment"]
    print("Starting fine-tuning...", flush=True)
    subprocess.run(command, check=True)
    evaluate = Path(__file__).with_name("evaluate_mcp_ocr.py")
    # Base test remains synthetic if base is synthetic. This is not a webcam accuracy claim.
    subprocess.run([sys.executable, str(evaluate), "--data", str(merged),
                    "--checkpoints", str(output), "--output", str(output / "base_test_report"),
                    "--device", args.device], check=True)
    if args.real_test:
        test_root = args.real_test.resolve()
        test_rows = load(test_root)
        verify(test_root, test_rows, {"test"})
        for kind in ("hdg", "alt"):
            if not any(r["kind"] == kind for r in test_rows):
                p.error(f"Real test dataset missing {kind}")
        subprocess.run([sys.executable, str(evaluate), "--data", str(test_root),
                        "--checkpoints", str(output), "--output", str(output / "real_camera_test_report"),
                        "--device", args.device], check=True)
        summary = json.loads((output / "real_camera_test_report" / "summary.json").read_text())
        for kind in ("hdg", "alt"):
            value = summary[kind]["exact_accuracy"]
            print(f"REAL CAMERA {kind.upper()} exact: {value:.2%}; target >= 90%: {value >= .9}")
    else:
        print("NO REAL CAMERA TEST: 90% webcam accuracy cannot be determined.")
    print(f"Fine-tuned checkpoints saved at {output}; original images/checkpoints retained.")


if __name__ == "__main__":
    main()
