"""Evaluate saved v2/v3 HDG and ALT checkpoints on held-out OCR test images.

Example:
 python vision/evaluate_mcp_ocr.py --data vision/data/mcp_ocr_aligned --checkpoints vision/checkpoints/mcp_ocr_v3 --output vision/reports/mcp_ocr_v3_test
"""
from mcp_preprocessing import normalize_aligned
import argparse
import csv
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--checkpoints", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    args = p.parse_args()
    from mcp_dataset import validate_dataset
    validate_dataset(args.data, {'train','val','test'})
    if args.output.exists():
        p.error('Evaluation output exists; choose a new directory')
    import numpy as np
    import torch
    from torch import nn
    from torch.utils.data import Dataset, DataLoader
    from PIL import Image, ImageOps, ImageDraw

    class DigitCNN(nn.Module):
        # Must match vision/train_mcp_ocr_v2.py exactly.
        def __init__(self, n):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, n)),
            )
            self.head = nn.Linear(128, 10)

        def forward(self, x):
            z = self.features(x).squeeze(2).transpose(1, 2)
            return self.head(z)

    with (args.data / "labels.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("Empty labels.csv")
    sessions = {}
    for row in rows:
        sid, split = row["session_id"], row["split"]
        if sid in sessions and sessions[sid] != split:
            raise ValueError(f"Data leakage: session {sid} in both {sessions[sid]} and {split}")
        sessions[sid] = split
    args.output.mkdir(parents=True, exist_ok=True)

    class OCRDataset(Dataset):
        def __init__(self, kind):
            self.rows = [r for r in rows if r["split"] == "test" and r["kind"] == kind]
            if not self.rows:
                raise ValueError(f"No test samples for {kind}")

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            row = self.rows[i]
            rel = Path(row["image_path"])
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"Unsafe image path: {rel}")
            with Image.open(args.data / rel) as f:
                im = ImageOps.exif_transpose(f).convert("L")
            im = normalize_aligned(im, row["kind"])
            x = torch.from_numpy(np.asarray(im, dtype="float32").copy()).unsqueeze(0) / 255
            return x, row["text"], row["image_path"]

    summary = {}
    all_results = []
    mistakes = []
    for kind, n in (("hdg", 3), ("alt", 5)):
        ckpt_path = args.checkpoints / f"{kind}_best.pt"
        if not ckpt_path.is_file():
            raise FileNotFoundError(ckpt_path)
        checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        if checkpoint.get("kind") != kind or checkpoint.get("digits") != n:
            raise ValueError(f"Checkpoint metadata mismatch: {ckpt_path}")
        model = DigitCNN(n)
        model.load_state_dict(checkpoint["model"])
        model.to(args.device).eval()
        ds = OCRDataset(kind)
        loader = DataLoader(ds, batch_size=args.batch, shuffle=False)
        exact = digit_correct = 0
        with torch.no_grad():
            for x, truths, paths in loader:
                predictions = model(x.to(args.device)).argmax(-1).cpu().tolist()
                for digits, truth, path in zip(predictions, truths, paths):
                    pred = "".join(map(str, digits))
                    matched = pred == truth
                    exact += matched
                    digit_correct += sum(a == b for a, b in zip(pred, truth))
                    item = {"kind": kind, "image_path": path, "truth": truth, "prediction": pred, "correct": matched}
                    all_results.append(item)
                    if not matched:
                        mistakes.append(item)
        count = len(ds)
        summary[kind] = {"samples": count, "exact_correct": exact, "exact_accuracy": exact/count,
                         "digit_accuracy": digit_correct/(count*n), "errors": count-exact,
                         "checkpoint_epoch": checkpoint.get("epoch")}
        print(json.dumps({kind: summary[kind]}, ensure_ascii=False))
    total = sum(s["samples"] for s in summary.values())
    summary["overall"] = {"samples": total, "exact_accuracy": sum(s["exact_correct"] for s in summary.values())/total,
                          "errors": len(mistakes)}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["kind", "image_path", "truth", "prediction", "correct"])
        writer.writeheader()
        writer.writerows(all_results)
    with (args.output / "errors.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["kind", "image_path", "truth", "prediction", "correct"])
        writer.writeheader()
        writer.writerows(mistakes)
    if mistakes:
        preview_rows = mistakes[:30]
        canvas = Image.new("RGB", (580, len(preview_rows)*90), "#202020")
        draw = ImageDraw.Draw(canvas)
        for i, row in enumerate(preview_rows):
            with Image.open(args.data / row["image_path"]) as f:
                im = f.convert("RGB")
            im.thumbnail((225, 64))
            canvas.paste(im, (8, i*90+12))
            draw.text((250, i*90+22), f"{row['kind'].upper()}  GT: {row['truth']}", fill="white")
            draw.text((250, i*90+44), f"PRED: {row['prediction']}", fill="#ff8080")
        canvas.save(args.output / "errors_preview.png")
        print(f"Error preview: {args.output / 'errors_preview.png'}")
    print(json.dumps({"overall": summary["overall"]}, ensure_ascii=False))
    print(f"Saved test-only evaluation to {args.output}")


if __name__ == "__main__":
    main()
