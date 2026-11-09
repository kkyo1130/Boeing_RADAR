"""Local BERT CALLSIGN + corrected deterministic ACTION/ALT/HDG candidates."""
import hashlib
import json
import re
from pathlib import Path
from threading import Lock

from .ner import ExtractionError, LABELS, V7Extractor, assemble
from .hybrid_baseline import rules
from .hybrid_rules import combine
from .numeric_slots import normalize_numeric_slots

ARTIFACT_FILES = ('model.safetensors', 'config.json', 'tokenizer.json',
                  'tokenizer_config.json', 'special_tokens_map.json', 'vocab.txt')


def fuse(text, raw):
    words = text.split()
    if raw.get('transcript') != text or [t['word'] for t in raw['tokens']] != words:
        raise ExtractionError('NER_ALIGNMENT_ERROR')
    # Preserve original token/character boundaries. Only canonicalize grouped
    # digits inside a single numeric token (3,000 -> 3000), never free text.
    numeric_words = [re.sub(r'(?<=\d),(?=\d)', '', w).strip('.,;:') for w in words]
    numeric_words = [w.replace('-', '') if re.fullmatch(r'[0-9](?:-[0-9]){2}', w) else w
                     for w in numeric_words]
    numeric_words, numeric_changes = normalize_numeric_slots(numeric_words)
    combined = combine(words, [t['label'] for t in raw['tokens']], rules(numeric_words))
    result = assemble(text, combined['tags'], [0.0]*len(words))
    # A deterministic rule has no probability. Never pass the discarded BERT
    # ALT/HDG score off as the score of a rule-generated entity.
    for token, original in zip(result['tokens'], raw['tokens']):
        is_call = token['label'][2:] == 'CALLSIGN'
        token['source'] = 'bert' if is_call else 'rule' if token['label'] != 'O' else None
        token['model_score'] = original['model_score'] if is_call else None
    for entity in result['entities']:
        entity['source'] = 'bert' if entity['label'] == 'CALLSIGN' else 'rule'
        selected = [t for t in result['tokens'] if t['start'] >= entity['start'] and t['end'] <= entity['end']]
        entity['model_score'] = min(t['model_score'] for t in selected) if entity['source'] == 'bert' else None
    result.update(model_version='bert-hybrid-rules-v2', model_tokens=raw['tokens'],
                  model_input_tokens=raw.get('model_input_tokens', words),
                  numeric_candidate_policy='slot-homophones-v1',
                  numeric_normalizations=numeric_changes,
                  rule_changes=combined['rule_changes'], conflicts=combined['conflicts'],
                  issues=sorted(set(result['issues'] + raw['issues'] +
                                    ['HYBRID_'+r.upper() for r in combined['review_reasons']])))
    return result


class BertHybridExtractor(V7Extractor):
    @staticmethod
    def words_for_model(text):
        # STT-added punctuation is not a lexical word. Token count/order and
        # original character offsets remain unchanged; do not rewrite words.
        return [word.strip('.,;:') or word for word in text.split()]

    def __init__(self, model_path):
        path = Path(model_path)
        try:
            config = json.loads((path/'config.json').read_text())
            manifest = json.loads((path/'radar_hybrid.json').read_text())
            if (manifest.get('schema_version') != 1 or manifest.get('backend') != 'bert-hybrid'
                    or config.get('model_type') != 'bert'
                    or config.get('id2label') != {str(i): t for i,t in enumerate(LABELS)}
                    or config.get('label2id') != {t:i for i,t in enumerate(LABELS)}):
                raise ExtractionError('NER_MODEL_INCOMPATIBLE')
            if any(hashlib.sha256((path/f).read_bytes()).hexdigest() != manifest['sha256'].get(f)
                   for f in ARTIFACT_FILES):
                raise ExtractionError('NER_ARTIFACT_HASH_MISMATCH')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, ExtractionError): raise
            raise ExtractionError('NER_MODEL_UNAVAILABLE') from exc
        import torch
        from transformers import AutoTokenizer, AutoModelForTokenClassification
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path, use_fast=True, local_files_only=True)
        if not self.tokenizer.is_fast: raise ExtractionError('NER_FAST_TOKENIZER_REQUIRED')
        self.model = AutoModelForTokenClassification.from_pretrained(
            path, local_files_only=True, use_safetensors=True).to('cpu').eval()
        self.lock = Lock()
        self.version = 'bert-real-only'

    def extract(self, text):
        return fuse(text, super().extract(text))
