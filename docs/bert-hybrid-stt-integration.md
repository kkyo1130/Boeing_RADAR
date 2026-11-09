# BERT + corrected rules in the local STT path

This opt-in backend connects the existing local Whisper WAV adapter to BERT
CALLSIGN extraction and the evaluated rules-v2 ACTION/ALT/HDG candidates. It
retains registered callsign matching, full-transcript grammar, numeric/range
checks, capture context, and the existing backend verdict. It never controls
Cockpit settings. V7 remains the default for existing configurations.

## Local setup

Install `backend/requirements-demo.txt`, `backend/requirements-ner.txt`, and the
existing Vision capture dependency in the same Python environment. No models
are downloaded by the application. Supply local fine-tuned BERT and
faster-whisper directories. The model weights are not committed.

Package the BERT artifact once (the destination must not exist):

```sh
.venv/bin/python scripts/prepare-hybrid-model.py \
  --source /absolute/path/to/bert/model \
  --destination .demo/bert-hybrid-model
```

`radar_hybrid.json` stores SHA-256 digests for weights, configuration and tokenizer
files. Loading verifies BERT architecture and the exact nine BIO labels. The
local experiment used seed13, selected by the original validation99 results
(98 exact sentences; seed42 97, seed73 96), not by the fresh test scores.

Configure the existing `.demo/config.json` callsign registry, `.demo/audio`
registered scenario WAVs, and `.demo/model` faster-whisper model. Local absolute
paths can instead be passed with `RADAR_V2_CONFIG`, `RADAR_DEMO_AUDIO`, and
`RADAR_WHISPER_MODEL`. Run:

```sh
scripts/run-hybrid-backend.sh
# In another terminal, from frontend/:
RADAR_API_TARGET=http://127.0.0.1:8013 npm run dev -- --host 127.0.0.1 --port 5176
```

The launcher uses `.venv/bin/python` (`RADAR_PYTHON` overrides it) and binds only
127.0.0.1, port8013 (`RADAR_PORT` overrides it). It enables:

```sh
RADAR_NER_BACKEND=bert-hybrid
RADAR_NER_MODEL=/absolute/path/to/prepared/bert-hybrid-model
```

`GET /api/demo/status` reports the selected backend and artifact presence, not
proof of prediction accuracy. `POST /api/demo/speech/extract` accepts
`{"text":"Radar one two three maintain 3000 feet heading 270"}` for diagnostics.
The response is a candidate extraction, always `instruction_check=NEEDS_REVIEW`;
only the full speech intake/structure pipeline can produce a PASS check.

CLI:

```sh
.venv/bin/python scripts/extract-atc.py \
  --backend bert-hybrid --model .demo/bert-hybrid-model \
  'Radar one two three maintain 3000 feet heading 270'
```

## Processing and failure behavior

- Original transcript, whitespace-token and character offsets are preserved.
  BERT input only strips punctuation at token edges, with normalized input tokens
  returned for inspection. No word substitution or missing-word completion.
- BERT provides CALLSIGN. The frozen training-derived rule baseline plus the
  rules-v2 filters provides ACTION, ALT, HDG. Speed/rate units and referenced
  altitudes are filtered; `fly` in a name is not an ACTION. The 46-prefix data
  file has a separate source/license notice (`speech/HYBRID_DATA_NOTICE.txt`).
- Rule tokens/entities have `source=rule` and `model_score=null`. Only BERT
  callsign scores are retained, uncalibrated. Original model tokens remain in
  diagnostics and are not mistaken for the combined rule output.
- Grouped numbers (`3,000`) preserve their original text. Exactly three
  hyphen-separated single digits (`2-7-0`) are accepted inside numeric grammar
  slots. Ranges (`270-280` or `2-7`), negatives, malformed hyphens and longer
  sequences are rejected. Callsign spelling still requires a registered alias.
- Invalid BIO, missing/multiple callsigns, overlapping spans, conditions,
  correction/negation and detected cutoff clauses remain review reasons.
  Absence of a flag does not certify an input. The complete existing grammar
  still has to consume the transcript and agree with extracted numeric spans.
- Explicitly enabling a backend without a model, with an incompatible artifact,
  or with an inference error does not fall back to grammar-only PASS. Fields are
  withheld and the result requires review.
- Same-transcript checks are not independent safety channels. Broader ATC
  grammar, free-form callsign resolution, actual ATC STT and all microphone
  environments remain outside the validated scope. Registered ATC playback is
  still a scenario; the pilot WAV adapter actually runs Whisper.

## Verification (2026-11-09)

- Both actual local model loaders exercised, along with backend regression tests.
  Exact final counts are recorded in SPEC-004-WI-02/TODO and the PR.
- Ported merger: 487 existing transcripts × 3 model-seed prediction streams
  matched the previous rules-v2 experiment labels and source offsets. This used
  cached predictions and does not constitute fresh model inference accuracy.
  Runtime punctuation handling is an additional STT integration adaptation.
- Actual local HTTP server, actual faster-whisper base.en and BERT seed13:

| Audio input | Observed result |
| --- | --- |
| Generated correct phrase | STT `Radar 1-2-3 climb and maintain 3,000 feet, heading 2-7-0.`; RADAR123/3000ft/270deg, READBACK structure PASS and comparison NORMAL |
| Generated wrong heading | STT `Radar one, two, three, maintain 3,000 feet, heading two, nine, zero.`; actual290 versus expected270, READBACK MISMATCH |
| Three seconds of silence | Empty transcript, NEEDS_REVIEW/UNVERIFIED |
| Previously recorded user microphone WAV | `Eight thousand feet, heading 270.`; missing callsign/command, NEEDS_REVIEW/UNVERIFIED |

The first two audio fixtures are synthetic speech, not real ATC recordings. The
last input is replay of a prior microphone recording, not a new live recording.
Overall flight state remains UNVERIFIED without a Cockpit observation even when
the readback itself matches. No frontend microphone permissions or camera E2E
were tested here.

Re-run the actual WAV HTTP checks against an already-running local server:

```sh
.venv/bin/python scripts/test-hybrid-stt.py \
  --audio .demo/audio --output .demo/hybrid-http-results
```

Optional `--recorded-wav` includes an existing microphone recording in the report.
The generated fixtures must correspond to the existing baseline/heading
scenarios. Saved reports contain original transcripts, raw candidate evidence,
and backend state. `.demo/` (audio, weights, DB and reports) is Git-ignored.

Run automated tests from `backend/`:

```sh
RADAR_TEST_BERT_MODEL=/absolute/path/to/prepared/bert-hybrid-model \
RADAR_TEST_NER_MODEL=/absolute/path/to/v7/model \
../.venv/bin/python -m pytest -q
```

Without those two test variables, actual model smoke tests are skipped; other
unit/API tests do not require model files. Switch back by setting
`RADAR_NER_BACKEND=v7` and a v7 `RADAR_NER_MODEL` before restarting the server.
