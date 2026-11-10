"""Homophone candidates in explicit numeric slots; never rewrite source evidence."""
import re
from app.services.structure_rules import (DIGITS, NUMBER_HOMOPHONES, HEADING_HESITATIONS,
                                          digits, feet, flight_level, heading_value)


def normalize_numeric_slots(tokens):
    words = [w.casefold() for w in tokens]
    normalized = list(tokens)
    changes = []
    allowed = set(DIGITS) | set(NUMBER_HOMOPHONES) | {'hundred', 'thousand'}
    for i, word in enumerate(words):
        if word == 'heading':
            start, kind = i + 1, 'HDG'
            if start < len(words) and words[start] in HEADING_HESITATIONS:
                start += 1
        elif words[i:i+2] == ['flight', 'level']:
            start, kind = i + 2, 'FL'
        elif word in {'maintain', 'climb', 'descend'}:
            start, kind = i + 1, 'FEET'
        else:
            continue
        end = start
        while end < len(words) and (words[end] in allowed or words[end].isascii() and words[end].isdigit()):
            end += 1
        if end == start or not any(w in NUMBER_HOMOPHONES for w in words[start:end]):
            continue
        raw = ' '.join(words[start:end])
        if kind == 'HDG':
            value = digits(raw)
            # Do not drop a preposition from e.g. "heading to two seven zero".
            if value is None or len(value) != 3 or int(value) > 360:
                continue
        elif kind == 'FL':
            if flight_level(raw) is None:
                continue
        elif end == len(words) or words[end] != 'feet' or feet(raw) is None:
            continue
        for j in range(start, end):
            if words[j] in NUMBER_HOMOPHONES:
                replacement = NUMBER_HOMOPHONES[words[j]]
                normalized[j] = replacement
                changes.append({'token_index': j, 'original_token': tokens[j],
                                'candidate_token': replacement, 'slot': kind,
                                'reason': 'numeric_slot_homophone'})
    return normalized, changes


def augment_numeric_candidates(tokens, original):
    """Add explicit FL spelling and hesitation candidates without editing source tokens."""
    w = [x.casefold().strip('.,;:') for x in tokens]
    out, changes, reasons = list(original), [], []
    allowed = set(DIGITS) | set(NUMBER_HOMOPHONES) | {'hundred', 'thousand'}

    def end_number(start):
        end = start
        while end < len(w) and (w[end] in allowed or w[end].isascii() and w[end].isdigit()):
            end += 1
        return end

    def put(a, b, label, reason):
        if a < b and all(tag == 'O' for tag in out[a:b]):
            out[a:b] = ['B-'+label] + ['I-'+label]*(b-a-1)
            changes.append({'start_token': a, 'end_token': b, 'reason': reason})
            return True
        return False

    def altitude_command_before(index):
        j = index - 1
        while j >= 0 and w[j] in {'to', 'and', 'altitude'}:
            j -= 1
        return j >= 0 and w[j] in {'climb', 'descend', 'maintain'}

    for i, word in enumerate(w):
        if re.fullmatch(r'fl[0-9]{2,3}', word) and altitude_command_before(i):
            put(i, i+1, 'ALT', 'explicit_compact_flight_level')
        elif word == 'fl' and altitude_command_before(i):
            end = end_number(i+1)
            if flight_level(' '.join(w[i+1:end])) is not None:
                put(i, end, 'ALT', 'explicit_spaced_flight_level')
        elif word == 'heading' and i+1 < len(w) and w[i+1] in HEADING_HESITATIONS:
            end = end_number(i+2)
            if heading_value(' '.join(w[i+1:end])) is not None:
                if put(i+1, end, 'HDG', 'heading_hesitation_candidate'):
                    reasons.append('heading_hesitation_requires_review')
    return out, changes, reasons
