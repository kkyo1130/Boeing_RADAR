# Bloom augmentation, synchronized capture and frozen OCR evaluation

Local simulated MCP workflow. Models, raw camera images, generated datasets and full per-frame reports stay outside Git. Sanitized measurements: `vision/evaluation/glare-20261112.json`.

## Capture

Open the camera-facing display at `/cockpit?display=training` and keep it visible. Run the webcam from a separate `/cockpit` window. The operator must confirm that the camera actually sees this selected display. A sentinel107/12300 was visually checked before the recorded runs.

`collect_ack_frames.py` changes only this simulated display through the existing local MCP API. It waits for the selected sequence/value render ACK to remain valid for1s, then accepts only a later camera request after another1s. The image and sidecar hash must match, frames must differ and be no older than6s. All raw frames are retained regardless of detection/OCR success. Ground truth comes from authorized display commands and render ACK, never OCR predictions. Every exit attempts to restore270/03000 and records how many of the scheduled frames were actually saved. Review the restore ACK as well.

The opt-in `RADAR_VISION_DEBUG_FRAME` enables a single atomic latest JPEG/metadata pair for collection. Do not enable this for normal operation. The OCR service refuses overlapping inference with429 instead of queueing stale frames.

```sh
python vision/collect_ack_frames.py --plan plan.json --output vision/data/<fresh_session> --condition <physical_condition> --role train --frames 3
```

Use different physical sessions for train, development and final. Frames from a single setting are correlated. Do not describe them as independent samples. Incomplete runs remain incomplete in reports; retakes are separate sessions.

## Synthesis and preparation

`generate_photo_mcp.py --glare` renders exact new digit labels before applying homography, bloom, exposure, reflection bands, sensor noise and JPEG compression. The homography also transforms the labelled boxes. Every derivative of the source photo is train-only. Severe erased inputs must not be forced into numerical outputs.

```sh
python vision/generate_photo_mcp.py --source <development_photo> --rois <roi_json> --output vision/data/<fresh_augmented> --count 300 --seed 20261112 --glare
python -m vision.prepare_live_training --output vision/data/<train_crops> --train vision/data/<train_session> --synthetic vision/data/<fresh_augmented>
python -m vision.prepare_live_training --output vision/data/<dev_crops> --development vision/data/<development_session>
```

Set `RADAR_REGION_OCR_BINARY` to the compiled `vision/native/regions.swift` binary when using the label-anchored locator. It uses actual HDG/ALT labels and image geometry without instruction values. One unrecognized numeric span may receive a geometric window proposal from the other visible field and aligned labels; conflicting/weak text evidence remains a hold. This is a region proposal, not a successful numeric reading.

`prepare_live_training` validates roles and duplicate frame hashes. Detection/preprocessing failures are audited and remain in raw-session evaluation denominators even if they cannot produce optimizer inputs.

## Model versions and selection

`train_character_ocr.py --init` loads compatible character weights, preserving old checkpoints. V2/V3/V4 preprocessing is explicitly checkpoint-versioned. V4 excludes thin panel-edge components and may use exactly3/5 aligned connected components when a column projection has no separating blank column. Missing/merged glyphs are not reconstructed. Do not silently change old checkpoint preprocessing.

```sh
OMP_NUM_THREADS=4 python vision/train_character_ocr.py --train vision/data/<train_crops> --validation vision/data/<dev_crops> --output vision/checkpoints/<fresh_candidate> --init <character_v2>/character_best.pt --device cpu --epochs 12 --batch 32 --lr .0001 --preprocessing amber_components_glyph_v4_components
```

Candidate selection uses development data only: fewer wrong accepted strings, then worst-field correct-output coverage, then raw exact-string performance. Epoch0 is retained if later training does not improve this ordering. Model score .75 remains an uncalibrated gate; it is not75% accuracy.

Freeze the checkpoint hash, inference-code hashes and evaluation policy before any final capture. Never use final images to tune this candidate. A failed final requires a new development designation and a fresh future final session.

## Evaluation and activation

`evaluate_capture_session.py` keeps scheduled/recorded/detected/preprocessed/accepted/correct/wrong/held counts separate. The preprocessing count is not a manual crop-completeness ground truth. Exact crop quality still requires reviewed box annotations. `--regions baseline.json` freezes identical region proposals for the model comparison and checks the raw-session hash; timing then excludes detector work.

Compare both standalone CNN and `--apple-fallback` pipelines. Fallback reads the same image crop; it is not an independent safety channel. A valid disagreement returns unknown. Do not infer broad operational accuracy from one setup or correlated frames.

The local selected frozen checkpoint is recorded in `.demo/active-vision.json`, read by `scripts/run-zip-ai.sh` in the integrated workspace. The service supports `RADAR_CHARACTER_CHECKPOINT` and optional `RADAR_CHARACTER_SHA256`. Without a character checkpoint it retains the original `RADAR_VISION_CHECKPOINTS` v3 engine. The original models remain available for rollback. Direct launch:

```sh
RADAR_CHARACTER_CHECKPOINT=<frozen_character_best.pt> RADAR_CHARACTER_SHA256=<sha256> RADAR_REGION_OCR_BINARY=<regions_binary> RADAR_OCR_BINARY=<existing_ocr_binary> python -m uvicorn vision.ocr_web:app --host 127.0.0.1 --port 8766
```

The integrated launcher is a separate local integration change; this training work does not replace its DB/report/flight behavior. See the WI-06 result record for exact measured counts and limitations.
