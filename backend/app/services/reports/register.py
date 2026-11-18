"""Read-only instruction register from frozen decisions, never a new validator."""
from copy import deepcopy

FIELDS = ('ALT', 'HDG')


def instruction_register(safety, raw_events=()):
    raw = {event['sequence']: event.get('snapshot', {}) for event in raw_events}
    times = {}
    for snapshot in raw.values():
        payload = snapshot.get('payload', {})
        if payload.get('observation_id'):
            times[payload['observation_id']] = payload.get('observed_at')
    items = {}
    for event in safety.get('timeline', []):
        if event.get('source') != 'ATC' or event.get('applied') is not True:
            continue
        snapshot = raw.get(event['sequence'], {})
        targets = snapshot.get('state', {}).get('targets', {})
        for field, reading in event.get('fields', {}).items():
            if field not in FIELDS:
                continue
            target = targets.get(field) or {}
            # A partial instruction retains other targets. Only explicitly
            # supplied fields belong to this exchange; never copy those targets.
            iid = target.get('instruction_id')
            if not iid:
                candidates = {check.get('instruction_id') for check in event.get('checks', [])
                              if check.get('field') == field and check.get('instruction_id')
                              and check.get('expected') == reading.get('value')}
                if len(candidates) == 1:
                    iid = candidates.pop()
            # Legacy ambiguous association remains visible, without borrowing
            # later checks or treating an unlinked value as verified.
            key = (iid or f"unlinked-{event['sequence']}", field)
            items.setdefault(key, dict(instruction_id=iid, field=field,
                expected=reading.get('value'), issued_at=event.get('occurred_at'),
                sequence=event['sequence'], readback=None, cockpit=None,
                callsign=None, checks_at=None, incidents=[]))
    for event in safety.get('timeline', []):
        checks = event.get('checks', [])
        by_id = {}
        for check in checks:
            by_id.setdefault(check.get('instruction_id'), []).append(check)
        for iid, rows in by_id.items():
            for field in FIELDS:
                item = items.get((iid, field))
                if not item or event['sequence'] < item['sequence']:
                    continue
                relevant = [r for r in rows if r.get('field') in (field, 'CALLSIGN')]
                if not any(r.get('field') == field for r in relevant):
                    continue
                # Replace the whole snapshot: no assembling a NORMAL state
                # from independent observations that never coincided.
                for name, stage, check_field in (('readback', 'READBACK', field),
                        ('cockpit', 'SETTING', field), ('callsign', 'READBACK', 'CALLSIGN')):
                    check = next((r for r in relevant if r.get('stage') == stage
                                  and r.get('field') == check_field), None)
                    item[name] = deepcopy(check)
                    if check:
                        item[name]['observed_at'] = times.get(check.get('observation_id'))
                item['checks_at'] = event.get('occurred_at')
    orphan_incidents = []
    for incident in safety.get('correction_trace', []):
        item = items.get((incident['instruction_id'], incident['field']))
        if item:
            item['incidents'].append(deepcopy(incident))
        else:
            # CALLSIGN and legacy incidents must not disappear from the PDF.
            orphan_incidents.append(deepcopy(incident))
    return dict(items=list(items.values()), orphan_incidents=orphan_incidents)
