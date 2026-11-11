# ALT/HDG joint OCR baseline

This is a **fixed-slot synthetic baseline**. One 850×190 image is split into eight known digit positions: three HDG digits and five ALT digits. A shared CNN predicts each digit, then the outputs are concatenated. It is not a general-purpose OCR model and **does not yet support arbitrary webcam frames or real MCP layouts**.

## 1. Generate training data

```bash
git fetch origin
git merge --ff-only origin/feat/vision-ai
python -m vision.generate_mcp --count 20000
```

## 2. Train

```bash
python -m vision.mcp_ocr train --epochs 15 --batch-size 32
```

Best validation checkpoint: `vision/checkpoints/mcp_ocr/best.pt`. Keep the training terminal open. On CPU, 20,000 images can take a long time; start with `--epochs 3` for a smoke test if needed.

## 3. Test on held-out synthetic split

```bash
python -m vision.mcp_ocr test
```

Outputs digit accuracy, **exact HDG match**, **exact ALT match**, and **joint exact match**. These metrics measure only the synthetic generator's domain, not real-world performance.

## 4. Try a generated image

```bash
python -m vision.mcp_ocr predict --image vision/data/boeing_737/mcp_synthetic/mcp_000000.png
```

## Constraints and next steps

- Input must be an 850×190 image following `vision.generate_mcp` layout. Do not send a raw webcam frame to this model.
- The training and evaluation CSVs are split by ALT/HDG pair to avoid identical value pairs crossing splits. The same renderer and typography are used in all partitions.
- Need real simulator frames, perspective/ROI correction, variable layouts, camera glare and independent annotations before cockpit integration.
- Checkpoint is generated **locally**; it is not uploaded to GitHub.
- Existing local modifications to `vision/train_digits.py` are independent and should be preserved.
