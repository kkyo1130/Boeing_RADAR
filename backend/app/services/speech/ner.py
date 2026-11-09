"""Local v7 word-level NER. Scores are uncalibrated; spans are not clearances."""
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
from threading import Lock

LABELS = ['O', 'B-CALLSIGN', 'I-CALLSIGN', 'B-ACTION', 'I-ACTION',
          'B-ALT', 'I-ALT', 'B-HDG', 'I-HDG']


class ExtractionError(ValueError):
    pass


def assemble(text, labels, scores):
    """Preserve raw whitespace-token offsets; never repair an illegal I label."""
    words = list(re.finditer(r'\S+', text))
    if len(words) != len(labels) or len(words) != len(scores):
        raise ExtractionError('NER_ALIGNMENT_ERROR')
    tokens, entities, issues = [], [], []
    current = None
    for word, label, score in zip(words, labels, scores):
        if label not in LABELS or not math.isfinite(score) or not 0 <= score <= 1:
            raise ExtractionError('NER_INVALID_OUTPUT')
        tokens.append(dict(word=word[0], start=word.start(), end=word.end(),
                           label=label, model_score=score))
        if label == 'O':
            current = None
            continue
        kind = label[2:]
        if label.startswith('B-'):
            current = dict(label=kind, start=word.start(), end=word.end(),
                           text=word[0], model_score=score)
            entities.append(current)
        elif current is None or current['label'] != kind:
            if 'INVALID_BIO' not in issues: issues.append('INVALID_BIO')
            current = None
        else:
            current['end'] = word.end()
            current['text'] = text[current['start']:current['end']]
            current['model_score'] = min(current['model_score'], score)
    return dict(transcript=text, tokens=tokens, entities=entities, issues=issues,
                model_version='v7', score_calibrated=False, instruction_check='NEEDS_REVIEW',
                numeric_validation='NOT_PERFORMED')


class V7Extractor:
    def __init__(self, model_path):
        path = Path(model_path)
        if not path.is_dir() or not (path/'model.safetensors').is_file():
            raise ExtractionError('NER_MODEL_UNAVAILABLE')
        config = json.loads((path/'config.json').read_text())
        manifest = json.loads((path/'experiment.json').read_text())
        if (manifest.get('schema_version') != 7 or config.get('model_type') != 'distilbert'
                or config.get('id2label') != {str(i): t for i, t in enumerate(LABELS)}
                or config.get('label2id') != {t: i for i, t in enumerate(LABELS)}):
            raise ExtractionError('NER_MODEL_INCOMPATIBLE')
        import torch
        from transformers import AutoTokenizer, AutoModelForTokenClassification
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path, use_fast=True, local_files_only=True)
        if not self.tokenizer.is_fast: raise ExtractionError('NER_FAST_TOKENIZER_REQUIRED')
        self.model = AutoModelForTokenClassification.from_pretrained(
            path, local_files_only=True, use_safetensors=True).to('cpu').eval()
        self.lock = Lock()

    def extract(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ExtractionError('EMPTY_TRANSCRIPT')
        if len(text) > 2048: raise ExtractionError('TRANSCRIPT_TOO_LONG')
        with self.lock:
            model_words = self.words_for_model(text) if hasattr(self, 'words_for_model') else text.split()
            encoded = self.tokenizer(model_words, is_split_into_words=True,
                                     truncation=False, return_tensors='pt')
            if encoded['input_ids'].shape[1] > 128:
                raise ExtractionError('NER_TOKEN_LIMIT')
            word_ids = encoded.word_ids()
            with self.torch.inference_mode():
                probabilities = self.model(**encoded).logits[0].softmax(-1)
            labels, scores, previous = [], [], None
            for i, word_id in enumerate(word_ids):
                if word_id is not None and word_id != previous:
                    score, label = probabilities[i].max(-1)
                    labels.append(LABELS[int(label)])
                    scores.append(float(score))
                previous = word_id
            result = assemble(text, labels, scores)
            result['model_version'] = getattr(self, 'version', 'v7')
            if model_words != text.split(): result['model_input_tokens'] = model_words
            return result


LOAD_LOCK = Lock()


@lru_cache(maxsize=2)
def _load(path, backend='v7'):
    if backend == 'v7':
        return V7Extractor(path)
    if backend == 'bert-hybrid':
        from .hybrid import BertHybridExtractor
        return BertHybridExtractor(path)
    raise ExtractionError('NER_BACKEND_UNSUPPORTED')


def extract_atc(text, model_path=None, *, backend=None):
    """English transcript -> raw BIO tokens and entity spans, without numeric approval."""
    path = model_path or os.getenv('RADAR_NER_MODEL')
    if not path: raise ExtractionError('NER_MODEL_NOT_CONFIGURED')
    # Serialize first load as functools' cache alone may construct twice concurrently.
    with LOAD_LOCK:
        extractor = _load(str(Path(path).resolve()), backend or os.getenv('RADAR_NER_BACKEND', 'v7'))
    return extractor.extract(text)


def check_candidates(result, callsign_raw, values):
    """Veto disagreement with the full-transcript grammar; never bypass it."""
    from app.services.structure_rules import normalize, parse_command
    if result['issues']:
        return 'hybrid_needs_review' if result.get('model_version') == 'bert-hybrid-rules-v2' else 'ner_invalid_bio'
    calls = [e for e in result['entities'] if e['label'] == 'CALLSIGN']
    if len(calls) != 1 or normalize(calls[0]['text']) != normalize(callsign_raw or ''):
        return 'ner_callsign_disagreement'
    candidates = {}
    for entity in result['entities']:
        kind = entity['label']
        if kind not in {'ALT', 'HDG'}: continue
        if kind in candidates: return 'ner_multiple_targets'
        prefix = 'maintain ' if kind == 'ALT' else 'heading '
        parsed, issues = parse_command(prefix + normalize(entity['text']))
        if issues or set(parsed) != {kind}: return 'ner_number_unresolved'
        candidates[kind] = parsed[kind]
    if candidates != values: return 'ner_target_disagreement'
    return None
