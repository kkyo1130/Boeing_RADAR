"""Fixed-length HDG (3 digits) and ALT (5 digits) OCR training baseline.

Example:
 python vision/train_mcp_fixed_ocr.py --data vision/data/mcp_blender_v8/ocr --epochs 60 --augment
The dataset must contain labels.csv from extract_mcp_ocr.py.
"""
import argparse
import csv
import json
import random
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("vision/checkpoints/mcp_fixed_ocr"))
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    p.add_argument("--augment", action="store_true")
    args = p.parse_args()

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    with (args.data / "labels.csv").open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    if not records:
        raise ValueError("No records in labels.csv")
    for row in records:
        n = {"hdg": 3, "alt": 5}.get(row["kind"])
        if n is None or len(row["text"]) != n or not row["text"].isascii() or not row["text"].isdigit():
            raise ValueError(f"Invalid label: {row}")

    class DatasetOCR(Dataset):
        def __init__(self, split):
            self.rows = [r for r in records if r["split"] == split]
            if not self.rows:
                raise ValueError(f"No {split} samples; regenerate with more sessions")
            self.augment = split == "train" and args.augment

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            row = self.rows[i]
            with Image.open(args.data / row["image_path"]) as f:
                im = f.convert("L")
            im = ImageOps.pad(im, (192, 48), color=12, method=Image.Resampling.LANCZOS)
            if self.augment:
                im = ImageEnhance.Brightness(im).enhance(random.uniform(.8, 1.2))
                im = ImageEnhance.Contrast(im).enhance(random.uniform(.85, 1.15))
                if random.random() < .15:
                    im = im.filter(ImageFilter.GaussianBlur(.4))
            x = torch.tensor(list(im.getdata()), dtype=torch.float32).reshape(1, 48, 192) / 255
            y = torch.tensor([int(c) for c in row["text"]] + [-100] * (5 - len(row["text"])), dtype=torch.long)
            return x, y, row["text"], row["kind"]

    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 5))
            )
            self.head = nn.Linear(128, 10)

        def forward(self, x):
            x = self.features(x).squeeze(2).transpose(1, 2)
            return self.head(x)

    train_loader = DataLoader(DatasetOCR("train"), batch_size=args.batch, shuffle=True)
    val_loader = DataLoader(DatasetOCR("val"), batch_size=args.batch)
    model = Model().to(args.device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)
    args.output.mkdir(parents=True, exist_ok=True)
    best = -1.0
    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for x, y, _, _ in train_loader:
            x, y = x.to(args.device), y.to(args.device)
            opt.zero_grad()
            pred = model(x)
            loss = criterion(pred.reshape(-1, 10), y.reshape(-1))
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))

        model.eval()
        totals = {"hdg": 0, "alt": 0}
        correct = {"hdg": 0, "alt": 0}
        digit_correct = digit_total = 0
        examples = []
        with torch.no_grad():
            for x, y, texts, kinds in val_loader:
                pred = model(x.to(args.device)).argmax(-1).cpu()
                for i, (truth, kind) in enumerate(zip(texts, kinds)):
                    n = len(truth)
                    guess = "".join(str(v) for v in pred[i, :n].tolist())
                    totals[kind] += 1
                    correct[kind] += int(guess == truth)
                    digit_correct += sum(a == b for a, b in zip(guess, truth))
                    digit_total += n
                    if len(examples) < 6:
                        examples.append({"kind": kind, "truth": truth, "pred": guess})
        total = sum(totals.values())
        stats = {
            "epoch": epoch,
            "train_loss": sum(losses) / len(losses),
            "val_exact_accuracy": sum(correct.values()) / total,
            "val_digit_accuracy": digit_correct / digit_total,
            "val_hdg_accuracy": correct["hdg"] / totals["hdg"] if totals["hdg"] else None,
            "val_alt_accuracy": correct["alt"] / totals["alt"] if totals["alt"] else None,
            "examples": examples if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs else []
        }
        history.append(stats)
        print(json.dumps(stats, ensure_ascii=False))
        if stats["val_exact_accuracy"] > best:
            best = stats["val_exact_accuracy"]
            torch.save({"model": model.state_dict(), "epoch": epoch,
                        "val_exact_accuracy": best, "input_size": [192, 48],
                        "architecture": "fixed_5_position_cnn_v1"}, args.output / "best.pt")
        (args.output / "metrics.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Best exact match: {best:.4f}. Small synthetic datasets are not evidence of real-world accuracy.")


if __name__ == "__main__":
    main()
