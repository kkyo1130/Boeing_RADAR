"""Train separate HDG (3 digit) and ALT (5 digit) OCR models.

Usage:
 python vision/train_mcp_ocr_v2.py --data vision/data/mcp_ocr_1004 --output vision/checkpoints/mcp_ocr_v2 --epochs 60 --device cpu --augment
"""
import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("vision/checkpoints/mcp_ocr_v2"))
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    p.add_argument("--augment", action="store_true")
    p.add_argument("--test", action="store_true", help="Evaluate held-out test split after training")
    p.add_argument("--init-checkpoints", type=Path, help="Load existing HDG/ALT weights for fine-tuning")
    args = p.parse_args()
    import torch
    from torch import nn
    from torch.utils.data import Dataset, DataLoader
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    with (args.data / "labels.csv").open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    if not records:
        raise ValueError("Empty labels.csv")
    sessions = {}
    for row in records:
        kind, split = row["kind"], row["split"]
        n = {"hdg": 3, "alt": 5}.get(kind)
        if n is None or split not in ("train", "val", "test") or len(row["text"]) != n or not row["text"].isascii() or not row["text"].isdigit():
            raise ValueError(f"Invalid label: {row}")
        sid = row["session_id"]
        if sid in sessions and sessions[sid] != split:
            raise ValueError(f"Session leakage: {sid} appears in {sessions[sid]} and {split}")
        sessions[sid] = split

    class OCRDataset(Dataset):
        def __init__(self, kind, split):
            self.rows = [r for r in records if r["kind"] == kind and r["split"] == split]
            self.kind = kind
            self.aug = args.augment and split == "train"
            if not self.rows:
                raise ValueError(f"No {kind}/{split} images")

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            row = self.rows[i]
            with Image.open(args.data / row["image_path"]) as f:
                im = ImageOps.exif_transpose(f).convert("L")
            # Normalize each display to its own number of digit cells; no letterbox padding.
            width = 36 * len(row["text"])
            im = im.resize((width, 48), Image.Resampling.BILINEAR)
            if self.aug:
                im = ImageEnhance.Brightness(im).enhance(random.uniform(.8, 1.2))
                im = ImageEnhance.Contrast(im).enhance(random.uniform(.85, 1.15))
                if random.random() < .12:
                    im = im.filter(ImageFilter.GaussianBlur(.4))
            x = torch.from_numpy(__import__("numpy").asarray(im, dtype="float32").copy()).unsqueeze(0) / 255
            y = torch.tensor([int(c) for c in row["text"]], dtype=torch.long)
            return x, y, row["text"]

    class DigitCNN(nn.Module):
        def __init__(self, n):
            super().__init__()
            self.n = n
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

    args.output.mkdir(parents=True, exist_ok=True)
    for kind, n in (("hdg", 3), ("alt", 5)):
        train_ds, val_ds = OCRDataset(kind, "train"), OCRDataset(kind, "val")
        train = DataLoader(train_ds, batch_size=args.batch, shuffle=True)
        val = DataLoader(val_ds, batch_size=args.batch)
        model = DigitCNN(n).to(args.device)
        if args.init_checkpoints:
            ckpt_path = args.init_checkpoints / f"{kind}_best.pt"
            checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
            if checkpoint.get("kind") != kind or checkpoint.get("digits") != n:
                raise ValueError(f"Checkpoint kind/digits mismatch: {ckpt_path}")
            model.load_state_dict(checkpoint["model"])
            print(f"Fine-tuning {kind} from {ckpt_path}", flush=True)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
        # Per-position weighting prevents frequent trailing zeroes from dominating.
        frequencies = [Counter(int(r["text"][pos]) for r in train_ds.rows) for pos in range(n)]
        weights = torch.tensor([[min(5., (len(train_ds) / 10) / max(1, frequencies[pos][d])) for d in range(10)] for pos in range(n)], dtype=torch.float32, device=args.device)
        weights = weights / weights.mean(dim=1, keepdim=True)
        history, best = [], -1.
        for epoch in range(1, args.epochs + 1):
            model.train()
            losses = []
            for x, y, _ in train:
                x, y = x.to(args.device), y.to(args.device)
                optimizer.zero_grad()
                logits = model(x)
                ce = nn.functional.cross_entropy(logits.reshape(-1, 10), y.reshape(-1), reduction="none").reshape(-1, n)
                loss = (ce * weights[torch.arange(n, device=args.device).unsqueeze(0), y]).mean()
                loss.backward()
                optimizer.step()
                losses.append(loss.item())
            model.eval()
            exact = digits = total = 0
            examples = []
            with torch.no_grad():
                for x, y, texts in val:
                    pred = model(x.to(args.device)).argmax(-1).cpu()
                    exact += (pred == y).all(dim=1).sum().item()
                    digits += (pred == y).sum().item()
                    total += len(texts)
                    if len(examples) < 4 and (epoch == 1 or epoch % 10 == 0 or epoch == args.epochs):
                        examples.extend({"truth": t, "pred": "".join(map(str, pred[i].tolist()))} for i, t in enumerate(texts[:4-len(examples)]))
            stat = {"kind": kind, "epoch": epoch, "train_loss": round(sum(losses)/len(losses), 5),
                    "val_exact_accuracy": round(exact/total, 5), "val_digit_accuracy": round(digits/(total*n), 5), "examples": examples}
            history.append(stat)
            print(json.dumps(stat, ensure_ascii=False), flush=True)
            if stat["val_exact_accuracy"] > best:
                best = stat["val_exact_accuracy"]
                torch.save({"model": model.state_dict(), "kind": kind, "digits": n, "epoch": epoch,
                            "val_exact_accuracy": best, "architecture": "digit_cnn_v2", "input_size": [36*n, 48]}, args.output / f"{kind}_best.pt")
            (args.output / f"{kind}_metrics.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(f"{kind} best validation exact: {best:.2%}", flush=True)
        if args.test:
            checkpoint = torch.load(args.output / f"{kind}_best.pt", map_location=args.device, weights_only=True)
            model.load_state_dict(checkpoint["model"])
            model.eval()
            test = DataLoader(OCRDataset(kind, "test"), batch_size=args.batch)
            correct = digit_correct = count = 0
            with torch.no_grad():
                for x, y, _ in test:
                    pred = model(x.to(args.device)).argmax(-1).cpu()
                    correct += (pred == y).all(dim=1).sum().item()
                    digit_correct += (pred == y).sum().item()
                    count += len(y)
            print(json.dumps({"kind": kind, "test_exact_accuracy": correct/count, "test_digit_accuracy": digit_correct/(count*n), "samples": count}))


if __name__ == "__main__":
    main()
