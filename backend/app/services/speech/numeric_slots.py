"""Homophone candidates in explicit numeric slots; never rewrite source evidence."""
from app.services.structure_rules import DIGITS, NUMBER_HOMOPHONES, digits, feet


def normalize_numeric_slots(tokens):
    words = [w.casefold() for w in tokens]
    normalized = list(tokens)
    changes = []
    allowed = set(DIGITS) | set(NUMBER_HOMOPHONES) | {'hundred', 'thousand'}
    for i, word in enumerate(words):
        if word == 'heading':
            start, kind = i + 1, 'HDG'
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
        if kind in {'HDG', 'FL'}:
            value = digits(raw)
            # Exactly three digits are required when disambiguating homophones.
            # Do not drop a preposition from e.g. "heading to two seven zero".
            if value is None or len(value) != 3 or kind == 'HDG' and int(value) > 359:
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
