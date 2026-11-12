# Character CNN — actual webcam improvement and frozen evaluation

Status: verifying for broad deployment. Implementation, local MPS training and scoped actual-camera measurement completed; changes remain uncommitted. No PR created. Broader distance/lighting/angle acceptance remains open. Existing v5/v6 weights, original datasets, CNN default paths, React/ACK and Cockpit design are preserved.

## Outcome and exact denominator

Frozen experiment: `vision/reports/character_camera_final_08`.

20 preselected camera-number combinations ×20 scheduled frames =400 frames (800 HDG/ALT strings). Values are held out from the camera train/development values and prior experimental plans. Synthetic training may contain the same numeric labels; there is no claim that every string is unseen in synthetic training. Model and extractor frozen before capture; experiment seed20261116. All400 frames retained, raw JPEGs, aligned PNGs, per-frame JSONL, model hashes and plan stored. Camera readout labels come from operator-authorized simulated display commands with matching render ACK, never from OCR. The old display values are restored after the experiment.

| Metric | Existing v5 HDG | New HDG | Existing v5 ALT | New ALT |
|---|---:|---:|---:|---:|
| Complete-crop exact string |224/360=62.22%|360/360=100%|48/360=13.33%|360/360=100%|
| Exact string / all scheduled frames |224/400=56%|360/400=90%|48/400=12%|360/400=90%|
| Accepted and correct / all frames (.75 score gate) |165/400=41.25%|360/400=90%|15/400=3.75%|360/400=90%|

40 frames are PANEL_STABILIZING (two after every planned setting change). They remain in the400 denominator; no failed frame is silently excluded. Same new readout extractor/crops are used for v5 and character models, isolating CNN comparison on identical images. This v5 result uses different values/conditions than earlier40-pair reports and must not be compared as an identical benchmark.

Additional offline replay requiring three consecutive equal accepted OCR strings yields320/400=80% for both HDG and ALT, all320 outputs correct. This replay is not a full measurement of the live UI's additional ROI-history delay. Panel confidence .5, panel three frames, IoU .8, edge/size/ambiguity gates unchanged. OCR .75 is an uncalibrated model-score threshold, not measured accuracy.

Scope: later camera capture with new value sequences in the setup left running by the user. Multiple distances/framing were encountered during development, but the final400 frames are one setup with20 correlated setting groups, not400 independent scenes. No across-condition, real-aircraft, ATC integration, or operational safety accuracy claim. Final08 is now consumed and must not be used to tune a successor while still calling it an independent final test.

## Diagnosed causes and solution

Actual raw frame evidence revealed partial digit cropping: e.g. the107 HDG window was cut to39px width and some of the wrong fragments were sent to the old CNN. A fixed13px bright-character grouping kernel did not scale with panel size. Bright panel borders also connected to digit masks under another framing/exposure. Original saved crops showed thin upper/lower artifacts and glyph aspect-ratio shifts. These are observed failure mechanisms; no claim that every historical error has a single cause.

`mcp_window_readouts.py` adds a panel-only complete-group detector: bright strokes, exclusion of broad panel-border components, panel-width-scaled grouping, full3/5 glyph counts, aligned glyph rows, dark glass support and immediate HDG/ALT pairing. Missing/merged/ambiguous groups return empty. No truth, instruction text or model prediction is used to locate/correct glyphs. New detector is explicitly selected in character live mode; legacy whole-frame fallback remains unchanged by default.

`mcp_character_ocr.py`: shared ten-class CharacterCNN, independent of digit position, reconstructs3/5 strings from image-only separated glyphs. Components shorter than half the dominant glyph height remove thin artifacts; exact expected count is mandatory. V2 explicitly resizes each glyph to24×28 within32×32, reducing aspect-ratio domain shifts. V1 aspect-preserving normalization remains supported by checkpoint metadata; no silent preprocessing change to old checkpoints. Inference rejects low score<.75, incomplete glyphs, or HDG>359. It never receives the simulator state or truth.

`train_character_ocr.py`: seed42,20 epochs, AdamW .0005, class-balanced loss, small rotation/shear/translation/intensity/blur augmentation. This is a new shared-character architecture trained from scratch, not a claim of loading v5 weights into an incompatible architecture. Uses the same original synthetic train split, existing120 camera pairs, new160 pairs, and216 complete camera pairs from explicitly retired development session06. All original synthetic split definitions remain intact; only train rows reach optimizer. 1460 training crops;31 ambiguous synthetic segmentations logged,5701 glyphs used. Development uses the two consumed40-pair camera batches (80 strings per kind); no gradients use those development pixels. Dataset hashes/session disjointness checked. Best checkpoint selected at epoch10, both development exact100%; final08 was captured only after freezing.

## Experiments retained, not hidden

- character_v1: development100%, but fresh06 HDG74.54%, ALT94.91% conditional crop exact; main HDG confusion8→0. No success claim based on development100%.
- camera_final_04: partial ROI/low YOLO confidence failures, retained for diagnosis.
- camera_final_05: initial glass-contour detector failed; results retained.
- camera_final_06: scale grouping worked,216 complete pairs; later deliberately reclassified as development/training to address8/0 and camera domain shift. It is no longer a final benchmark. Export copied images and operator ACK labels to `vision/data/camera_batches/character_development_06_train`, keeping originals.
- camera_final_07: changed framing exposed broad bright-border merging; all failures retained, used only to fix localizer. No CNN gradient training on07.
- camera_final_08: frozen corrected extractor + character_v2, new seed and excluded prior camera values, final scoped result above.

Static diagnostic resolution check on12 development scenes:480/640 each12 complete crops,800 eight,960 five;1280 was worse in an earlier diagnostic. Only this diagnostic used a one-frame PanelGate to isolate spatial behavior. Every actual video experiment and live character mode uses at leastthree.640 is explicitly selected; confidence was never lowered. This is inference-size tuning, not new YOLO weight training. Existing YOLO weights unchanged.

## Reproducible commands

Environment: activate existing Python environment (verified with sibling Boeing_RADAR/.venv). From Boeing_RADAR-vision:

```sh
python vision/train_character_ocr.py \
 --train vision/data/mcp_ocr_aligned \
 --train vision/data/camera_batches/sync_test_20261112_021206 \
 --train vision/data/camera_batches/v6_train_160_02 \
 --train vision/data/camera_batches/character_development_06_train \
 --validation vision/data/camera_batches/v6_test_40_02 \
 --validation vision/data/camera_batches/v5_candidate_final_40_03 \
 --output vision/checkpoints/mcp_character_v2 --epochs 20 --device mps
```

Already executed; existing outputs are protected. Choose a new output for another run. Do not overwrite the tested model.

Live mode (already started by this task):

```sh
python vision/live_mcp_ocr.py --source 0 \
 --character-checkpoint vision/checkpoints/mcp_character_v2/character_best.pt \
 --yolo-weights vision/checkpoints/mcp_yolo_blind_v2/fit/weights/best.pt \
 --yolo-imgsz 640 --yolo-conf 0.5 --yolo-stable-frames 3 \
 --stable-frames 3 --device mps
```

Q quits; R resets. Character mode rejects CLI attempts to weaken confidence/panel/OCR stability and disables manual ROI overrides. This selection does not change default models or the React OCR service. No operational Cockpit setting control is added.

Fresh camera evaluation tool: `evaluate_character_camera.py --help`. It freezes plan/hash before capture, restores the previous simulated values, and logs every scheduled frame. To repeat beyond08, choose a new output/seed and exclude all prior plans plus all camera training/development batches. Original08 command used --settings20 --frames20 --seed20261116 --imgsz640, character_v2, v5, blind_v2 YOLO, all four prior camera batches +character_development_06_train as --exclude, reports04/05/06/07 as --exclude-plan. Labels are scoring-only; no OCR receives command values.

Reports: `report_character_camera.py --input vision/reports/character_camera_final_08` (already executed; audit directory protected). `audit/index.html`, `all_settings.png`, `first_eligible_frame.png`, `temporal_summary.json` support inspection/presentation. Images are selected as the first complete-crop frame per setting, not by correctness. Inspected all20 representative crop pairs; values match their intended labels. No manual-review approval is fabricated for uninspected raw frames.

## Verification and review

116 regression tests passed (8.27s): character noise/partial glyph rejection, version compatibility, low-score abstention, IAS vs HDG selection, CLI safety minimums, deterministic unseen camera-value plans, temporal reset and truth-independent acceptance, existing CNN/v6/ACK/YOLO tests. `git diff --check` and CLI help passed. Actual MPS20-epoch character training completed for v1/v2, actual webcam sessions04–08 completed; late hash checks confirm character weights, v5 HDG/ALT and localizer unchanged through08. Existing unrelated changes preserved.

Changed/added: mcp_character_ocr.py, mcp_window_readouts.py, train_character_ocr.py, evaluate_character_camera.py, report_character_camera.py, test_character_ocr.py, live_mcp_ocr.py, this document and TODO. GUI startup observed (`Character CNN + YOLO automatic mode`); no assertion that every future frame is correct. Broader final sessions at varied distances/angles/reflections, end-to-end operational integration and frontend model migration remain out of scope/unverified here.
