# Boeing 737NG-inspired GLB → Blender → YOLO synthetic dataset

## Source and fidelity

The existing model is on branch `codex/cockpit-glb`, at `frontend/public/models/cockpit.glb`.
Its editable source is `frontend/scripts/build-cockpit.mjs`. It is an **original stylized simulator mesh** informed by 737NG references, **not Boeing CAD**. The named `mcp_root`, `heading_display`, `altitude_display`, and associated knobs are present in the authored source. It is not yet proven dimensionally faithful to a 737-800. Runtime HDG/ALT text is generated in React, so Blender renders of the GLB **do not include those dynamic values**. This dataset trains *whole-MCP detection only*, not OCR.

The source branch is left unchanged; `feat/vision-ai` contains only generator scripts.

## 1. Obtain the model without merging branches

From the local repository worktree on `feat/vision-ai`:

```bash
git fetch origin
git merge --ff-only origin/feat/vision-ai
mkdir -p frontend/public/models
git show origin/codex/cockpit-glb:frontend/public/models/cockpit.glb > frontend/public/models/cockpit.glb
```

Do not commit this binary model into the Vision branch unless its license and intended asset ownership are reviewed. The generator reads the local file directly.

## 2. Audit model

Install Blender (4.2+ recommended) and ensure `blender` is on PATH. On macOS, it may be at `/Applications/Blender.app/Contents/MacOS/Blender`.

```bash
blender -b --python vision/audit_cockpit_glb.py -- \
  --glb frontend/public/models/cockpit.glb \
  --output vision/data/mcp_model_audit.json
```

Inspect the report. Check MCP placement against licensed/authorized Boeing 737-800 cockpit reference imagery. The audit checks object names and geometry extents; **it cannot certify 737 fidelity**. Source uses arbitrary dimensions and has layout approximations; revise `build-cockpit.mjs` separately if accurate geometry is required, then rebuild the GLB in the source branch.

## 3. Smoke test rendering (6 sessions × 3 frames)

```bash
blender -b -t 4 --python vision/blender_render_mcp.py -- \
  --glb frontend/public/models/cockpit.glb \
  --output vision/data/mcp_blender \
  --sessions 6 --frames-per-session 3 --width 1280 --height 720
```

Open rendered PNGs and check that MCP is visible and bounding boxes fit the panel. The script projects **the bounding boxes of all MCP mesh objects**; this is an approximation and can include occluded geometry. It rejects heavily clipped or tiny projections but does not guarantee visibility. Validate labels visually before training. If the GLB import renames objects or axes, inspect Blender object names and correct the generator.

## 4. Full dataset and YOLO training

```bash
blender -b -t 4 --python vision/blender_render_mcp.py -- \
  --glb frontend/public/models/cockpit.glb \
  --output vision/data/mcp_blender \
  --sessions 20 --frames-per-session 100
python -m pip install ultralytics
python -m vision.train_mcp_yolo --data vision/data/mcp_blender --epochs 50 --imgsz 960 --batch 8 --device cpu
```

Data splits are by camera/lighting **session**, not frame. This reduces near-duplicate leakage, but all samples still share the same synthetic source model. Actual performance on real simulator screens must be evaluated separately.

```bash
python -m vision.detect_mcp \
  --image vision/data/mcp_blender/images/test/session000_frame0000.png \
  --weights vision/checkpoints/mcp_yolo/baseline/weights/best.pt
```

Choose an image that actually exists in the test folder; the example session index is illustrative.

## Next engineering tasks

1. Visual comparison and geometry refinement for 737-800 MCP (IAS/MACH, HDG, ALT, V/S, COURSE positions and real proportions).
2. Add dynamic seven-segment HDG/ALT text to Blender render scenes and ground-truth digit labels.
3. Add realistic monitor artifacts (perspective, glare, blur, moiré) and actual simulator frames to close synthetic-to-real gap.
4. Validate OCR separately; never report synthetic-only accuracy as real-camera accuracy.

**No render or training run has been executed by this GitHub-only change.**
