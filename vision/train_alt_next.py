"""ALT-only v5 fine-tuning using a NEW diverse, labeled webcam batch.

Example:
 python vision/train_alt_next.py --camera vision/data/camera_batches/batch_003 \
   --base vision/checkpoints/mcp_ocr_v4/merged_training_data \
   --init vision/checkpoints/mcp_ocr_v4 \
   --output vision/checkpoints/mcp_ocr_v5_alt --device cpu

Preserves the HDG checkpoint, old checkpoints and all input images.
The base test split is diagnostic only; use new independent real camera test for a 90% claim.
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


def read(root):
    with (root / "labels.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check(root, rows, allowed):
    if not rows:
        raise ValueError(f"No labels: {root}")
    for row in rows:
        kind, value = row.get("kind"), row.get("text", "")
        rel = Path(row.get("image_path", ""))
        if (kind not in ("hdg", "alt") or len(value) != (3 if kind == "hdg" else 5)
                or not value.isascii() or not value.isdigit()
                or row.get("split") not in allowed or rel.is_absolute()
                or ".." in rel.parts or not (root / rel).is_file()):
            raise ValueError(f"Invalid label/image: {row}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--camera", type=Path, required=True)
    p.add_argument("--init", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    p.add_argument("--min-alt-values", type=int, default=8)
    args = p.parse_args()
    base, camera, output = args.base.resolve(), args.camera.resolve(), args.output.resolve()
    if base == camera or any(output == x or output in x.parents or x in output.parents for x in (base, camera)):
        p.error("Input and output directories must be separate")
    if output.exists():
        p.error(f"Output already exists: {output} (refusing to overwrite)")
    if args.epochs < 1 or args.min_alt_values < 2:
        p.error("Invalid epochs or minimum distinct ALT values")
    for kind in ("hdg", "alt"):
        if not (args.init / f"{kind}_best.pt").is_file():
            p.error(f"Missing checkpoint: {kind}")
    original, fresh = read(base), read(camera)
    check(base, original, {"train", "val", "test"})
    check(camera, fresh, {"train"})
    distinct = sorted({r["text"] for r in fresh if r["kind"] == "alt"})
    print(f"New camera ALT values ({len(distinct)}): {', '.join(distinct)}", flush=True)
    if len(distinct) < args.min_alt_values:
        p.error(f"Need >= {args.min_alt_values} distinct ALT values with verified labels. "
                "Repeated 03000 frames cannot validate general ALT recognition.")
    for split in ("train", "val", "test"):
        if not any(r["kind"] == "alt" and r["split"] == split for r in original):
            p.error(f"Base missing ALT/{split}")
    merged = output / "merged_training_data"
    merged.mkdir(parents=True)
    rows_out = []
    for tag, root, rows in (("base", base, original), ("new_camera", camera, fresh)):
        for i, row in enumerate(rows):
            # New camera crops must only ever be used for training.
            if tag == "new_camera" and row["kind"] != "alt":
                continue
            rel = Path(row["split"]) / row["kind"] / f"{tag}_{i:06d}{Path(row['image_path']).suffix}"
            dest = merged / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / row["image_path"], dest)
            item = dict(row)
            item["image_path"] = rel.as_posix()
            item["session_id"] = f"{tag}_{row.get('session_id', 'unknown')}"
            item["source_image"] = f"{tag}/{row.get('source_image', row['image_path'])}"
            rows_out.append(item)
    fieldnames = ["image_path", "kind", "text", "split", "session_id", "source_image"]
    with (merged / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)
    print("Dataset:", dict(Counter((r["split"], r["kind"]) for r in rows_out)), flush=True)
    shutil.copy2(args.init / "hdg_best.pt", output / "hdg_best.pt")
    trainer = Path(__file__).with_name("train_mcp_ocr_v2.py")
    subprocess.run([sys.executable, str(trainer), "--data", str(merged), "--output", str(output),
                    "--init-checkpoints", str(args.init), "--kinds", "alt",
                    "--epochs", str(args.epochs), "--device", args.device, "--augment"], check=True)
    evaluator = Path(__file__).with_name("evaluate_mcp_ocr.py")
    subprocess.run([sys.executable, str(evaluator), "--data", str(merged),
                    "--checkpoints", str(output), "--output", str(output / "diagnostic_base_test"),
                    "--device", args.device], check=True)
    summary = json.loads((output / "diagnostic_base_test" / "summary.json").read_text())
    print(f"ALT diagnostic exact accuracy: {summary['alt']['exact_accuracy']:.2%}")
    print("WARNING: base test was previously inspected; it is not an independent final test.")
    print("For real 90% accuracy, evaluate on an unseen, diverse camera test dataset.")


if __name__ == "__main__":
    main()
