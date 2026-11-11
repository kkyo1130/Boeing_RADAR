"""Train a small supervised digit classifier on labeled digit crops.

Requires a CSV with columns filename,digit and images relative to --data.
This is a training baseline, NOT a trained or validated Boeing MCP model.
"""
from __future__ import annotations
import argparse
import csv
import json
import random
from pathlib import Path

def train(data: Path, train_csv: Path, val_csv: Path, output: Path,
          epochs: int = 10, seed: int = 42):
    import torch
    from torch import nn
    from torch.utils.data import Dataset, DataLoader
    from PIL import Image, ImageOps

    random.seed(seed)
    torch.manual_seed(seed)

    class DigitDataset(Dataset):
        def __init__(self, labels):
            with labels.open(newline="", encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))
            if not self.rows or not {"filename", "digit"}.issubset(self.rows[0]):
                raise ValueError("CSV requires filename,digit and at least one row")
        def __len__(self):
            return len(self.rows)
        def __getitem__(self, index):
            row = self.rows[index]
            digit = int(row["digit"])
            if not 0 <= digit <= 9:
                raise ValueError("Digit label must be 0..9")
            with Image.open(data / row["filename"]) as original:
                img = ImageOps.pad(original.convert("L"), (32, 32))
                pixels = torch.tensor(list(img.getdata()), dtype=torch.float32).reshape(1, 32, 32) / 255.
            return pixels, digit

    model = nn.Sequential(
        nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(32 * 8 * 8, 64), nn.ReLU(), nn.Linear(64, 10)
    )
    train_loader = DataLoader(DigitDataset(train_csv), batch_size=64, shuffle=True)
    val_loader = DataLoader(DigitDataset(val_csv), batch_size=64)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    output.mkdir(parents=True, exist_ok=True)
    history = []
    best = -1.
    for epoch in range(epochs):
        model.train()
        for x, y in train_loader:
            optimizer.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            optimizer.step()
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in val_loader:
                correct += (model(x).argmax(1) == y).sum().item()
                total += len(y)
        accuracy = correct / total if total else 0.
        history.append({"epoch": epoch + 1, "val_digit_accuracy": accuracy})
        if accuracy > best:
            best = accuracy
            torch.save({"model": model.state_dict(), "seed": seed,
                        "val_digit_accuracy": accuracy}, output / "best.pt")
        print(f"epoch={epoch+1} val_digit_accuracy={accuracy:.4f}")
    (output / "metrics.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    return best

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--val", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("vision/checkpoints/digits"))
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train(args.data, args.train, args.val, args.output, args.epochs, args.seed)
