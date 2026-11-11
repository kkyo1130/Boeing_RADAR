# Real Boeing 737 MCP image collection

## Current status

A **source catalog** is tracked in `vision/commons_sources.csv` (four identified, license-labeled Wikimedia Commons files). This is **not** a labeled OCR training dataset: the photographs have not been visually checked for readable ALT/HDG digits, and no real image files are committed.

A Wikimedia Commons category collector is implemented in `vision/collect_commons.py`. It can run on a machine with internet access, query Boeing 737 NG/MAX cockpit categories, filter license metadata, optionally download thumbnails, and write an attribution/sha256 manifest. The GitHub execution environment used to prepare this PR did not have access to Commons image bytes, so **no downloads have been claimed**.

## Run on a networked development machine

```bash
python -m vision.collect_commons --max-files 30 --download
```

Output: `vision/data/boeing_737/commons/images/` and `manifest.csv` (ignored by Git). Without `--download`, it creates only a metadata manifest.

## Before training

1. Open each downloaded photograph; confirm it is a real Boeing 737 NG/MAX cockpit and the **MCP ALT and HDG display digits** are visible and readable.
2. Remove non-MCP and unreadable images from the OCR training set; they can be retained separately for negative examples if appropriate.
3. Manually annotate `altitude`, `heading`, and pixel ROIs; **do not invent labels**. The collector deliberately leaves both values empty.
4. Record photographer, source URL, license, license URL, image modifications and attribution; honor CC BY/CC BY-SA conditions when distributing adaptations.
5. Split by original photo / photographer / shooting session to avoid near-duplicate leakage. Do not mix Airbus A300-600R images into the initial Boeing training set.
6. Evaluate on independently captured webcam photos before claiming any recognition accuracy.

## Scope caveats

The license filter is conservative but not a substitute for checking the file's current Commons license page and third-party rights. A licensed cockpit image is not necessarily a useful OCR sample. Wikimedia Commons does not supply ground-truth ALT/HDG labels for this project. Real cockpit photographs may show powered-off or unreadable MCP displays.

No automatic redistribution of photos through the repository is performed.
