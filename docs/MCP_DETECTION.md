# Step 1: YOLO MCP detector (simulator screenshots)

This implements the **first stage** of the proposed pipeline: find the entire MCP in a wide cockpit screenshot, then crop it. It is **not** a trained detector yet, and its crop is **not** directly compatible with the synthetic fixed-slot OCR.

## Prepare screenshots

Capture screenshots of the *actual simulator* at different camera distances, cockpit viewpoints, brightness levels, and MCP settings. For the initial experiment, target 100–200 **diverse** frames, not adjacent near-identical frames. Capture multiple independent sessions, ideally at least 10, so train/val/test can be separated by session. Do not include screenshots without MCP in this first positive-only labeling workflow. Keep original files outside the Git repository, e.g. `~/Desktop/mcp_screenshots/session01/`.

## Setup

```bash
git fetch origin
git merge --ff-only origin/feat/vision-ai
python -m pip install ultralytics
```

OpenCV, Pillow and PyTorch are already used by the existing vision environment. On macOS, the OpenCV ROI selector needs a graphical desktop.

## Label bounding boxes

```bash
python -m vision.label_mcp \
  --images ~/Desktop/mcp_screenshots/session01 \
  --session session01
```

Drag a rectangle tightly around the **entire MCP** (not just digits), then press Enter or Space. Press `c` to skip. Run again with a *different session name* for each independently recorded session. Repeated runs skip already-labeled source paths. Data is stored in `vision/data/mcp_detection/`, including `manifest.csv`, YOLO `images/` and `labels/` split folders, and `dataset.yaml`.

**Important:** the same `--session` value is always assigned to the same split. A single session is not enough for training. The hash split is approximately 80/10/10 by session, so check distribution and add sessions if needed.

## Train

```bash
python -m vision.train_mcp_yolo --epochs 50 --imgsz 960 --batch 8 --device cpu
```

On Apple Silicon, you may try `--device mps` if your PyTorch build supports it. The pretrained `yolo11n.pt` is downloaded by Ultralytics on first use. Training requires internet for that initial download.

Model files are stored under `vision/checkpoints/mcp_yolo/baseline/weights/`. Use a held-out test session and measure precision, recall and mAP, especially for small MCP regions. Do not infer accuracy without running training/evaluation.

## Predict and crop

```bash
python -m vision.detect_mcp \
  --image ~/Desktop/mcp_screenshots/session01/frame001.png \
  --weights vision/checkpoints/mcp_yolo/baseline/weights/best.pt \
  --output vision/data/mcp_crop.png
open vision/data/mcp_crop.png
```

The command prints detection confidence and pixel bounding box, and writes a crop.

## Follow-on stages

1. Calibrate and rectify the real MCP crop; annotate **HDG display** and **ALT display** regions separately.
2. Collect paired real-crop labels (HDG and ALT values) and fine-tune/retrain OCR. The current fixed-slot model expects the synthetic 850×190 layout.
3. Integrate detector + real-layout OCR + temporal stability, then verify the FastAPI contract before submitting cockpit readings.
4. Test under simulator-to-webcam domain shift. Real-aircraft deployment would require substantially stronger validation and appropriate approvals.
