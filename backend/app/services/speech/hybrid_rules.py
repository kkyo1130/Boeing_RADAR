"""Experimental NER rule corrections; never an instruction acceptance decision.

Input tags come from the frozen comparison baseline, not the server grammar.
Keep source token boundaries and return every suppression with its reason.
"""
import re


def spans(tags):
    i = 0
    while i < len(tags):
        if not tags[i].startswith('B-'):
            i += 1
            continue
        label = tags[i][2:]
        j = i + 1
        while j < len(tags) and tags[j] == 'I-' + label:
            j += 1
        yield i, j, label
        i = j


def invalid_bio(tags):
    return any(t.startswith('I-') and (i == 0 or tags[i-1] not in ('B-'+t[2:], t))
               for i, t in enumerate(tags))


def refine_rules(tokens, original):
    if len(tokens) != len(original):
        raise ValueError('token alignment mismatch')
    w = [x.lower().strip('.,;:') for x in tokens]
    out = list(original)
    changes, reasons = [], set()

    def drop(a, b, why):
        changes.append({'start_token': a, 'end_token': b,
                        'original_tags': original[a:b], 'reason': why})
        out[a:b] = ['O'] * (b-a)

    actions = [(a,b) for a,b,k in spans(original) if k == 'ACTION']
    for a,b in actions:
        # "fly nicky" is a name; bare "fly" isn't a supported numeric command.
        if w[a] == 'fly' and (b == len(w) or w[b] != 'heading'):
            drop(a,b,'fly_without_heading_operand')
        # A rate-of-climb noun phrase is not a new climb instruction.
        elif w[a] in {'climb','descend'} and a >= 2 and w[a-2:a] == ['rate','of']:
            drop(a,b,'rate_reference_not_action')

    for a,b,label in spans(original):
        if label != 'ALT':
            continue
        tail = w[b:b+4]
        # The old rules greedily read numbers before noticing their units.
        speed = bool(tail and tail[0] in {'knot','knots','kt','kts','mach'})
        rate = (tail[:2] in (['per','minute'],['a','minute']) or
                bool(tail and tail[0] in {'fpm','ft/min'}))
        if speed or rate:
            why = 'speed_not_altitude' if speed else 'vertical_rate_not_altitude'
            drop(a,b,why)
            # Only suppress the directly governing action, not earlier clauses.
            for x,y in reversed(actions):
                if y <= a and all(t in {'to','and','maintain','altitude'} for t in w[y:a]):
                    drop(x,y,why)
                    break
            reasons.add('unsupported_speed_or_rate_clause')
            continue
        # Use the closest governing verb/reference marker, rather than a
        # sentence-wide "rate" filter that would erase a subsequent target.
        command = -1
        reference = -1
        for j in range(a):
            if w[j] in {'climb','descend','maintain'}:
                if j >= 2 and w[j-2:j] == ['rate','of']:
                    reference = j
                else:
                    command = j
            if w[j] in {'passing','leaving','through','report','reporting',
                        'reaching','above','below'}:
                reference = j
            if w[j] == 'rate':
                reference = j
        if reference > command:
            drop(a,b,'reference_altitude_not_assigned_target')
            reasons.add('reference_or_conditional_clause')

    if any(x in {'if','when','until','after','before','unless'} for x in w):
        reasons.add('condition_scope_not_resolved')
    if any(x in {'correction','disregard','cancel','negative','not'} for x in w):
        reasons.add('correction_or_negation_not_resolved')
    # Detect obvious cutoff phrases; this is not a complete truncation detector.
    if w and (w[-1] in {'by','to','and','level','heading'} or w[-2:] == ['flight','level']):
        reasons.add('possibly_incomplete_clause')
    if invalid_bio(original):
        reasons.add('rule_invalid_bio')
    return {'tags':out, 'changes':changes, 'review_reasons':sorted(reasons)}


def combine(tokens, model_tags, original_rule_tags):
    if len(tokens) != len(model_tags) or len(tokens) != len(original_rule_tags):
        raise ValueError('token alignment mismatch')
    corrected = refine_rules(tokens, original_rule_tags)
    out = [t if t[2:] in {'ACTION','ALT','HDG'} else 'O' for t in corrected['tags']]
    reasons = set(corrected['review_reasons'])
    conflicts = []
    if invalid_bio(model_tags):
        reasons.add('model_invalid_bio')
    i = 0
    while i < len(out):
        if model_tags[i][2:] != 'CALLSIGN':
            i += 1
            continue
        j = i+1
        while j < len(out) and model_tags[j] == 'I-CALLSIGN':
            j += 1
        if any(t != 'O' for t in out[i:j]):
            conflicts.append({'start_token':i,'end_token':j})
            reasons.add('callsign_rule_overlap')
        else:
            out[i:j] = model_tags[i:j]
        i = j
    if invalid_bio(out): reasons.add('output_invalid_bio')
    if sum(t == 'B-CALLSIGN' for t in out) != 1:
        reasons.add('missing_or_multiple_callsigns')
    return {'tags':out, 'review_reasons':sorted(reasons),
            'rule_changes':corrected['changes'], 'conflicts':conflicts,
            'status':'NEEDS_REVIEW' if reasons else 'NER_CANDIDATE_ONLY',
            'numeric_normalization':'NOT_EVALUATED',
            'instruction_association':'NOT_EVALUATED'}
