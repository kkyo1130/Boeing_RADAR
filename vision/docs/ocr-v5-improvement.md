# v5 camera OCR audit and conservative candidate

Status: verifying, uncommitted. Existing CNN v5/v6, original images/labels, React/ACK, YOLO gate and default OCR model remain unchanged. No automatic correction of labels or thresholds.

## Evidence and limits

Read actual v5/v6 errors/predictions and inspected all80 saved test crops alongside the exact grayscale CNN input. No obvious missing digit or label mismatch was visible in these saved crops. Some ALT crops have thin upper horizontal artifacts. Original full camera frames for these OCR captures were not saved, so this cannot prove the original ROI or physical displayed label. Training review covered first/last sample of each of16 kind/value groups in new160 pairs (32 crops), not every training image. Formal dataset/preset/hash/session checks passed.

v5 mistakes are exactly9 HDG 032→052 and5 ALT 00600→00800. v6 additionally reads HDG3→1 (18), HDG3→5 (2), ALT8→9 (18), ALT6→8 (8), ALT6→9 (1). These are observed saved-crop digit confusions; causal attribution solely to domain drift, noise or class imbalance remains a hypothesis. Shared prepare_camera_crop and normalize_aligned contracts match collection/training/inference; prior tensor-equivalence regression remains passing.

Artifacts: vision/reports/ocr_crop_audit_01/index.html (all80 saved RGB/grayscale comparisons); confusions.json; manual_review.csv (PENDING, no fabricated human approval); train_first_last.png; candidate_development report. audit_camera_ocr.py is reusable, checks prediction path/truth provenance and never changes labels. Its summary marks DIAGNOSTIC_ONLY_CONSUMED_TEST.

## Implementation

finetune_camera_mcp.py adds explicit --camera-val, requiring a distinct camera session (val or already-consumed test). Train, development and final test must be disjoint. Development is remapped to val with camera_val: provenance; synthetic original train/val/test are preserved. training_manifest records development fingerprint and selection policy. compare_camera_mcp.py checks development provenance even if merged data is absent, preventing development data being declared independent final test.

train_mcp_ocr_v2.py adds explicit --camera-validation. Only camera_val rows select checkpoints when requested. Initial v5 is evaluated/saved as epoch0 baseline, and only strictly better exact development accuracy replaces it. Unrounded fractions select best; history logs rounded values. Existing synthetic selection behavior is retained without the option. This protects the observed development score, not unknown camera generalization.

cnn_v6_workflow.py adds collect-final and compare-final with new session03 and separate candidate path. These do not deploy a model or alter Cockpit settings outside the established operator-triggered simulated capture synchronization.

## Actual training and results

One controlled candidate run, no hyperparameter sweep:

```sh
python vision/finetune_camera_mcp.py \
 --base vision/data/mcp_ocr_aligned \
 --camera vision/data/camera_batches/sync_test_20261112_021206 \
 --camera vision/data/camera_batches/v6_train_160_02 \
 --camera-val vision/data/camera_batches/v6_test_40_02 \
 --init-checkpoints vision/checkpoints/mcp_ocr_v5 \
 --output vision/checkpoints/mcp_ocr_v5_camera_candidate_01 \
 --epochs 12 --lr 0.00001 --device mps
```

MPS12epochs completed for both kinds. Existing40 pairs were explicitly consumed as development, never gradient train samples. HDG initializer31/40→selected40/40(epoch8). ALT initializer35/40→selected35/40(epoch0); every new ALT epoch was worse, so ALT tensor values are exactly identical to v5 (verified every state_dict tensor). Combined development75/80=93.75% versus v5 66/80=82.5%. This is checkpoint-selection data performance, not independent improvement evidence. Candidate synthetic test: HDG133/134, ALT102/134. No final generalization or E2E accuracy claim; no default change.

## New independent final collection

Different physical camera session/conditions; keep label correctness and ROI completeness under visual review:

```sh
python vision/cnn_v6_workflow.py collect-final
# only after new40 pairs complete
python vision/cnn_v6_workflow.py compare-final
```

New data: vision/data/camera_batches/v5_candidate_final_40_03. New report: vision/reports/v5_candidate_final_03. Comparison labels its second model v6 for legacy compatibility; it actually points to mcp_ocr_v5_camera_candidate_01. Uses two known test combinations in a fresh session, so conclusions remain restricted to those combinations/conditions. Broader unseen numbers require additional independent coverage. No final frames have been collected by this task.

## Verification and handoff

109 regression cases passed (4.96s): full vision tests plus v6/sync/YOLO pipeline suites; includes camera-val remapping, preserved synthetic splits, train/development/final overlap rejection, selected camera rows, audit label immutability and per-position confusions. Actual MPS training and development evaluation completed; ALT initializer equality verified. Workflow final collection/comparison dry runs succeeded. Git diff --check passed. Source changes: audit_camera_ocr.py, finetune_camera_mcp.py, train_mcp_ocr_v2.py, compare_camera_mcp.py, cnn_v6_workflow.py, test_v6_pipeline.py and docs/TODO.

Self-review: no predictions promoted to truth, no training on consumed-test pixels, no development-as-final claim, no YOLO/readout safety relaxation. Readout-localization failures and upper crop artifacts remain unresolved pending raw-frame evidence/manual boundaries. Full training-crop human review and fresh independent final evaluation remain outstanding. Existing user changes and unrelated files preserved; no commit/PR created.
