"""Train a sequence OCR baseline for synthetic Boeing MCP HDG/ALT crops.

Uses the existing <dataset>/ocr/labels.csv. Unlike train_digits.py, this
recognizes entire 3/5-character displays with CTC, without digit segmentation.
Requires torch and Pillow. This is a research prototype, not flight equipment.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True, help="Path to extracted ocr directory")
    p.add_argument("--output", type=Path, default=Path("vision/checkpoints/mcp_ocr"))
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--height", type=int, default=48)
    p.add_argument("--width", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    p.add_argument("--augment", action="store_true", help="Apply mild train-only photometric augmentation")
    args = p.parse_args()
    if min(args.epochs, args.batch, args.height, args.width) <= 0:
        p.error("epochs, batch, height and width must be positive")

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    with (args.data / "labels.csv").open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    if not records:
        raise ValueError("No OCR records")
    for row in records:
        expected = 3 if row["kind"] == "hdg" else 5 if row["kind"] == "alt" else None
        if expected is None or len(row["text"]) != expected or not row["text"].isascii() or not row["text"].isdigit():
            raise ValueError(f"Bad OCR record: {row}")

    class OCRDataset(Dataset):
        def __init__(self, split):
            self.rows = [r for r in records if r["split"] == split]
            if not self.rows:
                raise ValueError(f"No samples in split {split}")
            self.augment = split == "train" and args.augment

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, index):
            row = self.rows[index]
            with Image.open(args.data / row["image_path"]) as source:
                image = source.convert("L")
            # Preserve aspect ratio, pad with a dark background to avoid stretching glyphs.
            image.thumbnail((args.width, args.height), Image.Resampling.LANCZOS)
            image = ImageOps.pad(image, (args.width, args.height), color=12,
                                 method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            if self.augment:
                image = ImageEnhance.Brightness(image).enhance(random.uniform(0.75, 1.25))
                image = ImageEnhance.Contrast(image).enhance(random.uniform(0.8, 1.2))
                if random.random() < 0.2:
                    image = image.filter(ImageFilter.GaussianBlur(random.uniform(0.1, 0.6)))
            tensor = torch.tensor(list(image.getdata()), dtype=torch.float32).reshape(1, args.height, args.width) / 255
            target = torch.tensor([int(c) + 1 for c in row["text"]], dtype=torch.long)
            return tensor, target, row["text"], row["kind"]

    def collate(items):
        images, targets, texts, kinds = zip(*items)
        return torch.stack(images), torch.cat(targets), torch.tensor([len(t) for t in targets]), texts, kinds

    class OCR(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2, 2),
                nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2, 2),
                nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
                nn.MaxPool2d((2, 1)), nn.AdaptiveAvgPool2d((1, None))
            )
            self.rnn = nn.LSTM(128, 96, num_layers=2, bidirectional=True, batch_first=True)
            self.classifier = nn.Linear(192, 11)  # 0=CTC blank, 1..10 = digits 0..9

        def forward(self, x):
            x = self.features(x).squeeze(2).transpose(1, 2)
            x, _ = self.rnn(x)
            return self.classifier(x).log_softmax(-1).transpose(0, 1)

    def decode(log_probs):
        paths = log_probs.argmax(-1).transpose(0, 1).tolist()
        result = []
        for path in paths:
            previous = None
            chars = []
            for value in path:
                if value != 0 and value != previous:
                    chars.append(str(value - 1))
                previous = value
            result.append("".join(chars))
        return result

    train_loader = DataLoader(OCRDataset("train"), batch_size=args.batch, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(OCRDataset("val"), batch_size=args.batch, collate_fn=collate)
    model = OCR().to(args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CTCLoss(blank=0, zero_infinity=True)
    args.output.mkdir(parents=True, exist_ok=True)
    best = -1.0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for images, targets, lengths, _, _ in train_loader:
            images, targets = images.to(args.device), targets.to(args.device)
            optimizer.zero_grad()
            logits = model(images)
            input_lengths = torch.full((images.shape[0],), logits.shape[0], dtype=torch.long)
            loss = criterion(logits, targets, input_lengths, lengths)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        model.eval()
        correct = {"hdg": 0, "alt": 0}
        totals = {"hdg": 0, "alt": 0}
        with torch.no_grad():
            for images, _, _, texts, kinds in val_loader:
                predictions = decode(model(images.to(args.device)))
                for pred, truth, kind in zip(predictions, texts, kinds):
                    totals[kind] += 1
                    correct[kind] += int(pred == truth)
        total = sum(totals.values())
        accuracy = sum(correct.values()) / total
        stats = {"epoch": epoch, "train_loss": sum(losses) / len(losses),
                 "val_exact_accuracy": accuracy,
                 "val_hdg_accuracy": correct["hdg"] / totals["hdg"] if totals["hdg"] else None,
                 "val_alt_accuracy": correct["alt"] / totals["alt"] if totals["alt"] else None}
        history.append(stats)
        print(json.dumps(stats, ensure_ascii=False))
        if accuracy > best:
            best = accuracy
            torch.save({"model": model.state_dict(), "height": args.height,
                        "width": args.width, "seed": args.seed,
                        "val_exact_accuracy": accuracy}, args.output / "best.pt")
        (args.output / "metrics.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Best validation exact-match accuracy: {best:.4f}")
    print("Synthetic validation alone does not establish real-camera OCR accuracy.")


if __name__ == "__main__":
    main()
