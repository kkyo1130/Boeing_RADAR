# Vision AI PoC

Issue: [#30](https://github.com/kkyo1130/Boeing_RADAR/issues/30). This is an **experimental, not flight-certified** camera-to-API prototype.

## Install

Python 3.11+ and a working webcam are required for live mode.

```bash
python -m pip install -r requirements-vision.txt
# macOS:
brew install tesseract
# Debian / Raspberry Pi OS:
sudo apt-get install tesseract-ocr
```

Tesseract OCR executable must be on PATH. The Python package `pytesseract` alone is not sufficient.

## Generate labeled synthetic images

```bash
python -m vision.generate_synthetic --count 500 --seed 42
```

Images and `labels.csv` are written to `vision/data/boeing_737/synthetic/`. They are original **simplified digit-display samples**, not genuine Boeing 737 MCP photographs. No internet photographs or trained weights are bundled. Real-world performance has not been measured.

## Calibrate ROI and run

Create `vision/roi.local.json` from `vision/roi.example.json` and replace both rectangles with **pixel coordinates in the camera frame**: `[x, y, width, height]`. The example ROI corresponds only to the 800×180 synthetic image, **not** a real cockpit/camera. A fixed camera and display are assumed; re-calibrate when the camera moves.

```bash
python -m vision.run_camera --roi vision/roi.local.json
# Start RADAR API, create flight/clearance, submit readback first:
python -m vision.run_camera --roi vision/roi.local.json --clearance CLR-001
```

Press `c` to submit a stable reading; `q` to exit. API mode checks current clearance state before selecting `/cockpit` or `/cockpit/reverify`. The user must explicitly confirm; no automatic submissions. Unreadable or low-confidence readings are never sent.

## Limitations and data handling

- Tesseract confidence is a heuristic, **not calibrated probability**. Default threshold 0.65 and 4/5-frame agreement are initial values, not validated thresholds.
- Current MVP requires manually configured ALT/HDG regions. Automatic MCP detection, YOLO training, OCR fine-tuning, camera calibration UI, and accuracy evaluation against real cockpit photos remain future work.
- A Tesseract model is **pre-trained**, not trained on the user's Boeing photos. No claim of achieving 95% accuracy.
- `confidence` is accepted by RADAR but does not currently influence the backend's matching rules.
- Real photos require explicit reuse/training permissions. Store Airbus A300-600R images separately from Boeing 737 data.
- The original image is not sent to the API; only numeric observations are posted. Never rely on this prototype for operational flight decisions.

## Tests

```bash
python -m pytest -q
```

Tests cover parsing, stability and API transition decisions; they do not establish real-camera recognition accuracy.
