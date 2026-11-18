"""Train/evaluate an eight-position MCP OCR baseline on synthetic full-display images.

Fixed layout: HDG=3 digits, ALT=5 digits. Requires images produced by
vision.generate_mcp; NOT calibrated for real Boeing hardware.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

# (x, width) for heading first, then altitude. Coordinates from generate_mcp.py.
SLOTS = [(54, 48), (143, 48), (232, 48),
         (437, 46), (509, 46), (581, 46), (653, 46), (725, 46)]
IMAGE_SIZE = (48, 64)


def extract_slots(image):
    """Return eight normalized 48x64 grayscale digit crops, shape (8,1,64,48)."""
    import numpy as np
    import torch
    from PIL import ImageOps
    if image.size != (850, 190):
        raise ValueError(f"Expected 850x190 generated image, got {image.size}")
    gray = image.convert("L")
    crops = []
    for x, width in SLOTS:
        # Extra horizontal/vertical margin helps tolerate modest rotation.
        patch = gray.crop((x - 12, 31, x + width + 12, 159))
        patch = ImageOps.fit(patch, IMAGE_SIZE)
        crops.append(torch.from_numpy(
            np.asarray(patch, dtype=np.float32).copy() / 255.0
        ).unsqueeze(0))
    return torch.stack(crops)


def build_model():
    from torch import nn
    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.AdaptiveAvgPool2d((3, 3)), nn.Flatten(),
        nn.Linear(128 * 3 * 3, 128), nn.ReLU(),
        nn.Dropout(.2), nn.Linear(128, 10),
    )


class MCPDataset:
    def __init__(self, root: Path, csv_path: Path):
        with csv_path.open(newline="", encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        if not self.rows:
            raise ValueError(f"No rows in {csv_path}")
        for row in self.rows:
            if len(row["heading"]) != 3 or len(row["altitude"]) != 5:
                raise ValueError("Expected three heading and five altitude digits")
        self.root = root

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        import torch
        from PIL import Image
        row = self.rows[index]
        with Image.open(self.root / row["filename"]) as img:
            crops = extract_slots(img)
        labels = torch.tensor([int(d) for d in row["heading"] + row["altitude"]],
                              dtype=torch.long)
        return crops, labels


def measure(model, loader, device):
    import torch
    model.eval()
    digit_correct = 0
    hdg_correct = alt_correct = both_correct = total = 0
    with torch.inference_mode():
        for crops, labels in loader:
            batch = crops.size(0)
            logits = model(crops.to(device).reshape(-1, 1, 64, 48))
            predictions = logits.argmax(dim=1).reshape(batch, 8).cpu()
            digit_correct += (predictions == labels).sum().item()
            hdg = (predictions[:, :3] == labels[:, :3]).all(dim=1)
            alt = (predictions[:, 3:] == labels[:, 3:]).all(dim=1)
            hdg_correct += hdg.sum().item()
            alt_correct += alt.sum().item()
            both_correct += (hdg & alt).sum().item()
            total += batch
    if not total:
        raise ValueError("Empty evaluation set")
    return {
        "images": total,
        "digit_accuracy": digit_correct / (total * 8),
        "heading_exact": hdg_correct / total,
        "altitude_exact": alt_correct / total,
        "joint_exact": both_correct / total,
    }


def train(args):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available()
                          else "cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(MCPDataset(args.data, args.train),
                              batch_size=args.batch_size, shuffle=True,
                              num_workers=0)
    val_loader = DataLoader(MCPDataset(args.data, args.val),
                            batch_size=args.batch_size, num_workers=0)
    model = build_model().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()
    args.output.mkdir(parents=True, exist_ok=True)
    best = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum = 0.0
        for crops, labels in train_loader:
            batch = crops.size(0)
            inputs = crops.to(device).reshape(-1, 1, 64, 48)
            targets = labels.to(device).reshape(-1)
            optimizer.zero_grad()
            loss = criterion(model(inputs), targets)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * batch
        metrics = measure(model, val_loader, device)
        print(f"epoch={epoch:02d} loss={loss_sum / len(train_loader.dataset):.4f} "
              f"val_digit={metrics['digit_accuracy']:.4f} "
              f"val_hdg={metrics['heading_exact']:.4f} "
              f"val_alt={metrics['altitude_exact']:.4f} "
              f"val_joint={metrics['joint_exact']:.4f}", flush=True)
        if metrics["joint_exact"] > best:
            best = metrics["joint_exact"]
            torch.save({"model": model.cpu().state_dict(),
                        "architecture": "fixed_slots_v1",
                        "epoch": epoch, "val_metrics": metrics},
                       args.output / "best.pt")
            model.to(device)
            (args.output / "val_metrics.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"best_val_joint={best:.4f} checkpoint={args.output / 'best.pt'}")


def test(args):
    import torch
    from torch.utils.data import DataLoader
    device = torch.device("cpu")
    model = build_model()
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    if checkpoint.get("architecture") != "fixed_slots_v1":
        raise ValueError("Incompatible checkpoint architecture")
    model.load_state_dict(checkpoint["model"])
    loader = DataLoader(MCPDataset(args.data, args.test),
                        batch_size=args.batch_size, num_workers=0)
    metrics = measure(model, loader, device)
    print(json.dumps(metrics, indent=2))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"report={args.report}")


def predict(args):
    import torch
    from PIL import Image
    model = build_model()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != "fixed_slots_v1":
        raise ValueError("Incompatible checkpoint architecture")
    model.load_state_dict(checkpoint["model"])
    model.eval()
    with Image.open(args.image) as image, torch.inference_mode():
        crops = extract_slots(image)
        predictions = model(crops).argmax(dim=1).tolist()
    print(json.dumps({"heading": "".join(map(str, predictions[:3])),
                      "altitude": "".join(map(str, predictions[3:]))}, indent=2))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("train", "test", "predict"):
        s = sub.add_parser(name)
        s.add_argument("--checkpoint", type=Path,
                       default=Path("vision/checkpoints/mcp_ocr/best.pt"))
        if name in ("train", "test"):
            s.add_argument("--data", type=Path,
                           default=Path("vision/data/boeing_737/mcp_synthetic"))
            s.add_argument("--batch-size", type=int, default=32)
        if name == "train":
            s.add_argument("--train", type=Path,
                           default=Path("vision/data/boeing_737/mcp_synthetic/train.csv"))
            s.add_argument("--val", type=Path,
                           default=Path("vision/data/boeing_737/mcp_synthetic/val.csv"))
            s.add_argument("--output", type=Path,
                           default=Path("vision/checkpoints/mcp_ocr"))
            s.add_argument("--epochs", type=int, default=15)
            s.add_argument("--lr", type=float, default=.001)
            s.add_argument("--seed", type=int, default=42)
        if name == "test":
            s.add_argument("--test", type=Path,
                           default=Path("vision/data/boeing_737/mcp_synthetic/test.csv"))
            s.add_argument("--report", type=Path,
                           default=Path("vision/checkpoints/mcp_ocr/test_metrics.json"))
        if name == "predict":
            s.add_argument("--image", type=Path, required=True)
    args = p.parse_args()
    if args.command == "train":
        train(args)
    elif args.command == "test":
        test(args)
    else:
        predict(args)


if __name__ == "__main__":
    main()
