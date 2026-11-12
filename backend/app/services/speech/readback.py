"""Explicit registered readback candidates; never infer a callsign from the target.

BERT's original output is retained. Only a missing callsign and an explicit
altitude may be supplemented, with rule provenance and no invented score.
Other model problems, conflicting candidates and full-grammar failures remain.
"""
from copy import deepcopy
import re

from app.services.structure_rules import normalize, split_callsign, readback_parts, parse_readback


def readback_candidates(text, registry, result):
    if not result.get('model_version', '').startswith('bert-hybrid-rules-'):
        return result
    matched = split_callsign(normalize(text), registry, readback=True)
    if not matched or result.get('transcript') != text:
        return result
    canonical, alias, raw, command = matched
    values, issues = parse_readback(command)
    if not values or any(i[2] != 'READBACK_ALTITUDE_ACTION_MISSING' for i in issues):
        return result
    if set(result['issues']) - {'HYBRID_MISSING_OR_MULTIPLE_CALLSIGNS'}:
        return result
    calls = [e for e in result['entities'] if e['label'] == 'CALLSIGN']
    if calls and (len(calls) != 1 or normalize(calls[0]['text']) != raw):
        return result  # Explicit model disagreement is not a missing prediction.
    out = deepcopy(result)
    additions = []
    words = list(re.finditer(r'\S+', text))

    def entity(label, normalized):
        # Exact original spans only; never manufacture source text/offsets.
        candidates = []
        for i, start in enumerate(words):
            for end in words[i:]:
                original = text[start.start():end.end()]
                if normalize(original) == normalized:
                    candidates.append(dict(label=label, text=original, start=start.start(), end=end.end(),
                                           source='registered_readback_rule', model_score=None))
        return candidates[0] if len(candidates) == 1 else None

    if not calls:
        candidate = entity('CALLSIGN', raw)
        if candidate is None:
            return result
        candidate.update(canonical=canonical, alias_key=alias)
        additions.append(candidate)
        out['issues'] = [i for i in out['issues'] if i != 'HYBRID_MISSING_OR_MULTIPLE_CALLSIGNS']
    parts = readback_parts(command).groupdict()
    if 'ALT' in values and not any(e['label'] == 'ALT' for e in out['entities']):
        candidate = entity('ALT', parts['alt'])
        if candidate is None:
            return result
        additions.append(candidate)
    if not additions:
        return result
    out['base_entities'] = deepcopy(result['entities'])
    out['base_issues'] = list(result['issues'])
    out['entities'] = sorted(out['entities'] + additions, key=lambda e: e['start'])
    out['readback_candidate_policy'] = 'exact-registered-boundary-v1'
    out['readback_rule_additions'] = additions
    # tokens/model_tokens retain the unmodified model/fusion diagnostic output;
    # entity additions are explicitly separate, not presented as BERT labels.
    return out
