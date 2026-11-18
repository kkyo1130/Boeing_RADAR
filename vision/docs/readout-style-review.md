# Taller, sharper MCP readouts with camera regression acceptance

User request: increase vertical proportions and HDG/ALT legibility; retain only changes with nondecreasing Vision performance. Local implementation and scoped camera verification completed; broad deployment status remains verifying. Uncommitted; existing user changes, original training data and model weights preserved.

## Accepted visual change

frontend/src/Cockpit3D.jsx:

- MCP parent vertical compression reduced by multiplying loaded root Y scale by1.25 (original .52→.65).
- Numeric plane height factor1.3→1.5; combined rendered height is about44% taller than the immediately preceding UI. Width unchanged. Numeric Courier bold glyph shape retained; experimental per-character squeezing was rejected.
- Black window/bezel height factor1.2→1.45, combined with parent scale about51% taller. Centers remain y.5.
- Screens use unlit matte black MeshBasicMaterial (0x050809), avoiding synthetic glass lighting/reflection artifacts inside crops.
- Numeric color #ffd28a, non-tone-mapped sharp material. Fourfold canvas resolution and anisotropy8 for numeric/HDG/ALT textures; low alpha fringe cutoff. Legacy non-sharp ancillary text retains previous treatment.
- HDG/ALT label planes1.3×.72 instead of1×.336; muted light text #d0dce5, normal-weight Courier, black matte backing. Forward z.425 prevents the glareshield occluding the label. Less saturated highlights and larger letter counters improve visible legibility. No artificial UI text overlay outside the 3D scene.

Existing dimensions/design positions elsewhere, ACK/value handling and default models are preserved. The whole MCP's vertical proportions also affect its knobs, reducing their previous flattening. Frontend GLB file was not rebuilt or overwritten.

## Controlled camera measurements

Model: mcp_character_v2/character_best.pt. YOLO: mcp_yolo_blind_v2/fit/weights/best.pt, inference640. Confidence .5, three panel frames, temporal IoU .8 and OCR score .75 unchanged. No retraining, lookup of displayed labels during OCR, threshold reduction or gate bypass.

Camera view initially varied during exploratory phases. Those phases are not clean causal A/B evidence. During the accepted experiment the existing capture prop temporarily locked MCP front view and OrbitControls across both phases. CockpitVision.jsx was restored to capture=false afterwards; no permanent lock added.

`vision/reports/readout_style_ab_03` contains15 identical preselected settings ×20 frames =300 scheduled frames per phase. This is a paired UI regression benchmark, not a newly unused generalization test. Values were commanded in the simulated collector only, checked by render ACK; OCR receives camera pixels and kind only. Commands restore the previous values after capture. Repeated frames are correlated and all results are scoped to the fixed setup/MCP front view.

| Character CNN metric | Matte/taller candidate | Final larger HDG/ALT labels |
|---|---:|---:|
| HDG exact / all300 frames |270/300=90%|270/300=90%|
| ALT exact / all300 frames |270/300=90%|270/300=90%|
| HDG/ALT exact / complete270 crops |100% /100%|100% /100%|
| HDG accepted-correct /300 |270/300=90%|270/300=90%|
| ALT accepted-correct /300 |269/300=89.67%|269/300=89.67%|
| Additional OCR3-frame replay correct /300 |HDG80%, ALT79%|HDG80%, ALT79%|

30 scheduled frames remain blocked for panel stabilization (two per setting). One ALT low-score output remains withheld; no threshold was weakened to suppress this abstention. All actually accepted outputs were correct in these samples. The OCR3-frame report is an offline replay and does not measure every live UI ROI-history delay.

The prior compressed display in the same locked-front experiment produced zero complete readout crops (270 localization failures plus30 stabilizing frames). This exposed a view-dependent weakness of that display/localizer combination; it does not invalidate previously observed90% in the earlier camera setup. Matte/taller numbers restored90% in this setup. Adding the final clear labels caused no further measured decline in any acceptance metric.

`comparison.json` checks prior→matte/taller nondecrease. `comparison_labels.json` checks matte/taller→final labels, including unchanged model/extractor hashes, plan, count, gates, crop coverage, all-frame raw exact, accepted-correct, accepted accuracy and OCR3 replay; also requires raw all-frame exact>=.9. All14 final checks pass, keep_candidate=true. This is an observational regression pass, not a statistical proof of equal performance for all angles/brightness.

## Exploratory failures and storage constraint

- ab_01: initial400-frame baseline aborted by ENOSPC near completion. Not used for accuracy claims. Only temporary JPEGs from this current-task aborted trial were removed to recover space; JSONL/crops retained. Original datasets/models and completed earlier experiments were untouched.
- ab_02: raw JPEG quality70 reduced audit storage but another storage failure occurred. First15 complete settings formed a storage-only prefix, not chosen by accuracy. Candidate enlargement and later narrow-glyph variant were rejected. Camera view also changed, so these are diagnostic records, not the final paired comparison.
- ab_03: controlled-front, sparse audit raw storage succeeded. Every scheduled frame still runs inference and is logged; every complete CNN crop remains lossless PNG. Only full raw audit JPEGs are sampled once per20 frames. Storage settings do not alter the in-memory camera inference pixels.

No claim is made that an accepted design is best among all possible designs. Rejected source snapshots and diagnostic summaries remain under their report folders. Original capture/controller ACK and CNN/YOLO logic are unchanged by this UI request.

## Tools and reproduction

Added compare_readout_styles.py plus four meaningful regression cases: no decreasing coverage hidden behind perfect accepted accuracy; incomplete capture rejected; changed safety parameters rejected; unchanged low accuracy cannot pass an explicit minimum. It only reports a decision and never edits UI/models. evaluate_character_camera.py adds --raw-jpeg-quality and --raw-every for audit storage (defaults95/1 preserve existing behavior); all frames still count. report_character_camera.py handles sparse raw JPEG selection.

```sh
python vision/compare_readout_styles.py \
 --before vision/reports/readout_style_ab_03/after \
 --after vision/reports/readout_style_ab_03/after_labels \
 --min-all-frame-exact .9 \
 --output /tmp/readout-style-comparison-recheck.json
```

Source snapshots, protocol, full metrics and `visual_comparison.png` are in readout_style_ab_03. Per-frame/crop audit: after_labels/audit/index.html. The comparison image uses the predetermined twentieth frame of the first setting on each side, not a correctness-selected image. The final source hash is in protocol.json; final model hashes are in each manifest. Test view lock restored after acceptance.

Build passed (existing large-chunk warning); frontend58 tests passed. Full Vision regression result is recorded in TODO after completion. No real-camera claim beyond this observed fixed setup, no guarantee of future frame correctness, no frontend OCR-service model migration. The independent safety gate/model score must not be described as calibrated accuracy.

Final verification: Vision120 passed in4.94s, frontend58 passed, final build passed (1.58s, existing chunk warning). Selectable character-CNN live window restarted with unchanged safety arguments. New source applied by Vite HMR; no permanent capture lock remains.
