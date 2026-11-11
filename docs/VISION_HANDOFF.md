# Vision AI dataset + training handoff

This PR provides **code**, not a completed trained Boeing 737 OCR model. Real photo image bytes and annotations are not in Git.

## What is implemented

- Fixed-ROI webcam OCR baseline: `vision/run_camera.py`
- Original synthetic *display* generator: `vision/generate_synthetic.py`
- Original synthetic **single-digit** dataset generator: `vision/generate_digits.py`
- Supervised PyTorch digit classifier training baseline: `vision/train_digits.py`
- Leakage-aware CSV split helper: `vision/dataset.py`
- Commons source catalog and license-filtered downloader: `vision/commons_sources.csv`, `vision/collect_commons.py`
- Evaluation script for OCR full ALT/HDG reading: `vision/evaluate.py`

## On your machine

```bash
git fetch origin
git switch feat/vision-ai
python -m pip install -r requirements-vision.txt
python -m pip install torch
# Install Tesseract executable separately (brew install tesseract on macOS)
python -m pytest -q

# Generate 20,000 original labeled digit images; output is git-ignored.
python -m vision.generate_digits --count 20000
python -m vision.train_digits \
  --data vision/data/boeing_737/digits \
  --train vision/data/boeing_737/digits/train.csv \
  --val vision/data/boeing_737/digits/val.csv \
  --output vision/checkpoints/digits

# Fetch candidate licensed cockpit photos, not numeric training labels.
python -m vision.collect_commons --max-files 30 --download
```

## Critical limitations

- The small PyTorch digit classifier is a **training demonstration only**. Its saved `best.pt` is **not wired into** the webcam full-number recognition pipeline, which currently uses Tesseract. Do not describe the project as having a deployed custom trained OCR model.
- Synthetic digits are not faithful Boeing MCP 7-segment displays; the training generator must be upgraded to the actual visual domain before meaningful performance claims.
- The Commons collector depends on external API categories and network availability, and may yield zero usable images. Every photo needs current license review and manual ALT/HDG labeling.
- A real camera or simulator cannot be operated from the GitHub connector. No real photo bytes were downloaded here.
- Unit tests were added but were **not run on the GitHub branch** from this environment. No model training or measured accuracy was performed here.
- Keep train/val/test independent by original source and camera session. Do not claim high accuracy on synthetic data as real-world accuracy.

## What remains before a review-ready PR

1. Run unit tests and fix any errors against the current `dev` backend.
2. Capture actual webcam recordings of the monitor showing the 737 MCP with varied altitude, heading, distance, glare, and angles.
3. Verify licenses, download and review public cockpit photos; manually label numeric values and ROIs.
4. Improve the synthetic renderer to match 737 MCP segmented displays and camera artifacts.
5. Train/fine-tune an appropriate sequence OCR model on full ALT/HDG crops (the current single-digit classifier is only a stepping stone).
6. Integrate trained sequence OCR into `vision/core.py` and compare against Tesseract.
7. Measure held-out real-camera ALT, HDG, joint accuracy and abstention rate; tune thresholds.
8. Perform full end-to-end `SETTING_ERROR` → `RESOLVED` test and then mark PR ready for review.

Target: `dev`; branch: `feat/vision-ai`; issue: #30; PR: #31.
