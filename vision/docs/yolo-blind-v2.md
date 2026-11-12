# YOLO blind relabeling v2 — implementation and handoff

## Scope and data contract

Original 190 captures and prior labels/weights remain unchanged. Relabel original train_near (40), train_far (40), train_angle (40), val (30): 150 images. Original test (40) remains diagnostic-only, excluded from training and final evaluation. A new physical session supplies the independent final test.

`review_yolo_camera.py --blind` starts each undecided image with no rectangle, never displays model score/proposal/reason, and ignores original assisted approvals. R draws a manual rectangle on the original image; Enter or SPACE confirms, D rejects, Q saves. Draw the complete MCP panel including readouts and controls; exclude windshield, EFIS side panels and lower primary flight displays. Only the new human rectangle is displayed. Progress resumes only from the separate blind work directory. All images require an explicit accept/reject before export; accepted decisions must be BLIND_MANUAL. Human anatomical correctness still requires careful review.

New progress: `vision/data/yolo_blind_v2/work/<batch>/reviews.json`. New labels: `vision/data/yolo_blind_v2/labels/<batch>`. Existing output datasets are never overwritten.

## Executable steps

Run from Boeing_RADAR-vision with the Python environment containing OpenCV, PyTorch and Ultralytics activated. The helper uses that same Python interpreter. Append `--dry-run` to print the complete underlying command without executing it.

### 1. Blind relabel old training/validation images

```sh
python vision/yolo_blind_workflow.py review train_near
python vision/yolo_blind_workflow.py review train_far
python vision/yolo_blind_workflow.py review train_angle
python vision/yolo_blind_workflow.py review val
```

Q saves partial work; rerun the same command to resume. Original reviews.json is neither consumed nor changed. Direct equivalent for one batch:

```sh
python vision/review_yolo_camera.py --blind \
  --input vision/data/yolo_camera/train_near \
  --review-dir vision/data/yolo_blind_v2/work/train_near \
  --output vision/data/yolo_blind_v2/labels/train_near
```

### 2. Collect a new independent test session, then blind-label it

Use a new physical filming session with varied distance, angle, brightness and reflection; do not reuse training images or the old test40. Collection loads no detector and shows no predicted rectangles. It saves 40 raw frames, at 2-second intervals, subject to duplicate rejection. Accepted labels may number fewer than 40 if images are rejected; collect an additional separate session if needed.

```sh
python vision/yolo_blind_workflow.py collect-final
python vision/yolo_blind_workflow.py review final_test
```

Capture output is `vision/data/yolo_camera/final_test_02`, session `yolo_final_test_02`. Direct capture command:

```sh
python vision/collect_yolo_camera.py --source 0 --auto-interval 2 --capture-only \
  --session yolo_final_test_02 --split test --count 40 \
  --output vision/data/yolo_camera/final_test_02
```

### 3. Validate/prepare, then train

```sh
python vision/yolo_blind_workflow.py train --prepare-only
python vision/yolo_blind_workflow.py train --epochs 40 --device mps
```

Preparation requires complete human-reviewed blind datasets, checks labels, hashes and session overlap, and preserves synthetic train/val/test splits. Old diagnostic-test pixels and sessions are retired in the training manifest. The preflight writes a separate `mcp_yolo_blind_v2_preflight` folder. Actual training writes `vision/checkpoints/mcp_yolo_blind_v2`; initializer is the existing sibling Boeing_RADAR baseline_v7/weights/best.pt. Old model files are not modified. Use `train --dry-run` to inspect full paths and arguments. Training uses the established fine-tuning configuration; no automatic runtime model switch occurs.

### 4. Compare both models on the new final test

```sh
python vision/yolo_blind_workflow.py evaluate --device mps
```

Reports: `vision/reports/yolo_blind_v2_final_01`. Reports include Precision, Recall, mAP50, mAP50-95, top-score histogram/quantiles, missing detections, IoU denominators, spatial gate pass rate, per-image reasons and overlays. Confidence distribution is for top MCP detections above the .1 diagnostic floor; missing detections remain separate. P/R from AP evaluation are not fixed-.5 operating-point metrics. Static spatial checks do not claim temporal stability. Final mode requires blind labels and the new model's retired-test policy; re-labeling old test pixels or reusing their session fails validation.

Keep this final test frozen. Tuning on its outcomes makes it diagnostic for subsequent iterations and requires another independent final session.

### 5. Validate consecutive real-camera frames

```sh
python vision/yolo_blind_workflow.py video --source 0 --max-frames 300
```

For a recorded real-camera video, replace `--source 0` with `--source /path/to/video.mp4`. Output: `vision/reports/yolo_blind_v2_video_01/frames.csv` and `summary.json`. Checks confidence .5, spatial constraints, three valid consecutive frames with IoU .8 and both internal HDG/ALT readouts. This tool forwards nothing to CNN; eligible_after_all_checks indicates gate eligibility, not independently verified panel accuracy. No threshold relaxation flags are exposed. Use direct tools with a new output directory for repeat runs; existing outputs are rejected.

## Changed files and responsibilities

- review_yolo_camera.py: blind GUI, separate progress/export and manual provenance.
- yolo_camera_data.py: blind audit/protocol validation.
- yolo_final_test_policy.py: blind final-test requirement and retired hashes/sessions.
- finetune_yolo_camera.py: blind mixed-data preparation and evaluation policy manifest.
- compare_yolo_camera.py, yolo_gate_diagnostics.py: final mode, score distributions and honest annotation provenance.
- collect_yolo_camera.py, yolo_auto_collection.py: capture-only raw collection without a detector.
- validate_yolo_video.py: fixed three-frame gate validation and per-frame logs.
- yolo_blind_workflow.py: executable stage commands.
- test_yolo_blind_pipeline.py: blind UI/provenance, isolation, retirement, mocked evaluation, capture and consecutive-frame regressions.

CNN, React, Cockpit and deployed gate thresholds are unchanged by this task. Other pre-existing workspace changes remain present.

## Verification and review

Executed from Boeing_RADAR-vision using the existing sibling Boeing_RADAR/.venv interpreter:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=vision:. ../Boeing_RADAR/.venv/bin/python -m pytest \
 vision/test_yolo_blind_pipeline.py vision/test_yolo_auto_collection.py \
 vision/test_yolo_camera_pipeline.py vision/test_yolo_gate_diagnostics.py \
 vision/test_v6_pipeline.py vision/test_mcp_display_sync.py vision/tests \
 -q -p no:cacheprovider --basetemp=/tmp/radar-yolo-blind-regression-final
```

Result: 107 passed in 3.97s. New tests verify hidden old boxes/scores/approvals, unchanged raw bytes, separate resumable progress, rejection of copied assisted approvals, blind-only exports, retirement protections, score distributions and final report mode, capture-only never invoking YOLO, and mocked seven-frame temporal reset/pass behavior (frames 3 and 7 eligible). Workflow dry runs for review, preparation and evaluation succeeded. Tests use temporary fixtures/mocks; they do not establish camera detection accuracy.

Self-review: old labels cannot seed blind decisions; source image hashes and session separation are validated; old test pixels remain disallowed even with new labels; outputs are separate; confidence .5 and temporal 3/.8 remain intact. Semantic correctness of a manually drawn MCP boundary is a human responsibility.

Not executed: physical camera capture, interactive human blind annotation, official new training, final real-test comparison and real-camera three-frame acceptance. No new performance improvement is claimed. Changes remain uncommitted; existing workitem acceptance status is unchanged.
