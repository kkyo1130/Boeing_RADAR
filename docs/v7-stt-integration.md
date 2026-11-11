# v7 extraction and local STT integration

`app.services.speech.ner.extract_atc(text, model_path=None)` returns English BIO tokens,
CALLSIGN/ACTION/ALT/HDG spans, offsets into the original transcript and uncalibrated model
scores. Spans are not numeric clearances. Illegal BIO is reported, never silently repaired.
Maximum input: 2048 characters / 128 model tokens. CPU inference, local safetensors only.

## Setup and usage

Install `backend/requirements-ner.txt` using Python 3.11 in the server environment.
Audio recognition also needs `backend/requirements-demo.txt`, a local Whisper model and
the existing demo dependencies. Supply an extracted, trusted v7 directory with tokenizer,
`model.safetensors`, `config.json`, and `experiment.json`. No weights are committed.

```sh
export RADAR_NER_MODEL=/path/to/radar_atc_ner_boundary_v7_model
python scripts/extract-atc.py 'singapore six two one climb flight level two three zero'
```

With `backend` on the import path:

```python
from app.services.speech.ner import extract_atc
result = extract_atc('singapore six two one climb flight level two three zero')
print(result['entities'])
```

The existing `scripts/run-demo.sh` inherits `RADAR_NER_MODEL`. When the demo is enabled,
`POST /api/demo/speech/extract` accepts `{"text":"..."}` and returns diagnostics without
creating a flight or Observation. Missing/incompatible weights return 503. Status reports
`ner_enabled` and `ner_model_present`, which are configuration/file checks, not accuracy guarantees.

## Integration behavior

The existing readback WAV route performs:
`LocalWhisper.transcribe → extract_atc → full-transcript grammar + registered callsign checks
→ NER/rule agreement → existing ObservationV2 receiving and structure checks`.
The response includes `ner` separately from Whisper `model_score`.
Registered ATC scenarios use the same gate, but remain registered-text simulation, not ATC STT.

With no `RADAR_NER_MODEL`, existing rule-only behavior remains. With it configured, model
load/inference failures, illegal BIO, ambiguous/missing/mismatched callsigns, duplicate or
unresolved targets and rule disagreement hold the input for review. There is no silent
fallback to PASS. Audio quality, timing, registered callsigns and downstream checks remain.
The same transcript feeds both checks; they are not independent safety channels.

The grammar is deliberately unchanged. NER may extract `climb flight level ...` while the
existing parser still holds it for review. Unsupported suffixes/conditions are never dropped
just to pass. Existing numeric conversion and downstream range checks apply. No automatic
Cockpit settings or neural-score-to-accuracy conversion.

## Verification

```sh
cd backend
python -m pytest -q
RADAR_TEST_NER_MODEL=/path/to/v7 python -m pytest -q tests/test_ner_v7.py
```

Default tests inject model output/mock ASR. The optional artifact test loads actual weights
and checks English, taxi/QNH and token limits. Live microphone, actual Whisper transcription
and device E2E remain distinct, unverified integration boundaries.
