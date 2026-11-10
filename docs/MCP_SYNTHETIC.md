# MCP-inspired ALT/HDG synthetic dataset

The generator draws original 7-segment-style heading (3 digits) and altitude (5 digits) displays, applies mild rotation/blur/brightness changes, and writes ground-truth CSV labels. This is an **approximation**, not an exact Boeing 737 MCP rendering or an actual photographed cockpit dataset.

## Generate

```bash
git pull --ff-only origin feat/vision-ai
python -m vision.generate_mcp --count 20000
```

Data appears in `vision/data/boeing_737/mcp_synthetic/` (git-ignored). Each image is 850×190. The CSVs are `labels.csv`, `train.csv`, `val.csv`, `test.csv` with `filename,altitude,heading,original_id,session_id,source`. Splitting uses the ALT/HDG pair to prevent the same value combination from crossing partitions. Other combinations share the same rendering procedure, so this **does not** establish real-camera generalization.

## Next required implementation

1. Build a full-string ALT/HDG OCR model (e.g., two field-specific sequence recognizers) trained using these CSVs. **The existing digit CNN is not suitable for predicting an entire 3- or 5-digit string without segmentation.**
2. Add independent test sets with distinct font styles and photographed display artifacts; record exact ALT match, exact HDG match, joint match and abstention rates.
3. Collect real webcam frames from the target flight simulator and annotate ROIs and displayed values.
4. Integrate the trained full-string model into the camera pipeline, compare against Tesseract and only then validate FastAPI transitions.

## Known limits

- Not trained or evaluated here. The generated dataset is an input to future full-string training, not a finished model.
- 7-segment-style appearance and sampled values are synthetic design choices. Real MCP typography, decimal/negative values, mode states, glare and camera perspective may differ.
- No Boeing trademarks or copyrighted cockpit photographs are embedded in the generator.
