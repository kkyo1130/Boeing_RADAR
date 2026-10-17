"""Deterministic advisory queue. No aircraft writes or operational severity thresholds."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4
from app.services.validation_v2 import evaluate, freshness, parsed, stamp

PHRASES = {
    'ALT': '고도 설정을 확인하세요', 'HDG': '방위 설정을 확인하세요',
    'BOTH': '고도와 방위 설정을 확인하세요', 'READBACK': '복명복창 내용을 확인하세요',
    'VISIBILITY': '계기판이 보이도록 해주세요', 'CAMERA': '카메라 연결을 확인하세요',
}
LEASE_SECONDS = 10  # Playback reservation, not an operational warning threshold.


def memory(state):
    return state.setdefault('voice', {'episodes': {}, 'attempts': {}, 'inputs': {}, 'events': {}})


def reconcile(state, policy, now, *, ended=False):
    """Called within the receiver transaction; episodes survive unknown/stale inputs."""
    voice = memory(state)
    episodes = voice['episodes']
    health = state['channels'].get('CAMERA', {})
    current = list(state['current']['COCKPIT'].values())
    fresh = [row for row in current if row and not freshness(policy, row.get('observed_at'), now)]
    disconnected = health.get('status') == 'DISCONNECTED'
    camera = episodes.get('CAMERA')
    # AVAILABLE alone cannot recover an outage. An attributable later frame can.
    recovered = camera and any(row.get('frame_id') and parsed(row['observed_at']) > parsed(camera['detected_at']) for row in fresh)
    if disconnected and not camera:
        episodes['CAMERA'] = dict(occurrence_id='DEV-'+uuid4().hex, detected_at=stamp(now), voice_completed_at=None)
    elif camera and not disconnected and recovered:
        episodes.pop('CAMERA')
    occluded = any(row.get('reason') == 'roi_occluded' for row in fresh)
    if not disconnected and occluded and 'CAMERA' not in episodes:
        episodes.setdefault('VISIBILITY', dict(occurrence_id='VIS-'+uuid4().hex, detected_at=stamp(now), voice_completed_at=None))
    elif 'VISIBILITY' in episodes and (disconnected or (
        current and len(fresh) == len(current) and all(row.get('value') is not None for row in fresh)
        and any(parsed(row['observed_at']) > parsed(episodes['VISIBILITY']['detected_at']) for row in fresh))):
        episodes.pop('VISIBILITY')
    if ended:
        episodes.clear()
    return voice


def candidates(state, policy, callsign, now, *, ended=False):
    if ended:
        return []
    voice = state.get('voice', {})
    out = []
    def add(phrase, ids, instruction_id=None):
        out.append(dict(candidate_id='ADV-'+sha256((phrase+'|'+ '|'.join(sorted(ids))).encode()).hexdigest()[:32],
            phrase_key=phrase, text=PHRASES[phrase], occurrence_ids=sorted(ids), instruction_id=instruction_id,
            asset_url='/voice/'+phrase.lower()+'.wav'))
    for name in ['CAMERA', 'VISIBILITY']:
        item = voice.get('episodes', {}).get(name)
        if name == 'VISIBILITY' and not any(row and row.get('reason') == 'roi_occluded' and not freshness(policy, row.get('observed_at'), now) for row in state['current']['COCKPIT'].values()):
            continue
        if item and not item['voice_completed_at'] and (name == 'CAMERA' or now >= parsed(item['detected_at'])+timedelta(seconds=5)):
            add(name, [item['occurrence_id']])
    validation = evaluate(state, policy, callsign, now).model_dump(mode='json')
    latest = state.get('readback_required')
    if not latest or latest['atc_input_id'] != state.get('latest_atc_input_id') or any(
        row['result'] == 'UNVERIFIED' for row in validation['readback']['fields'] if row['instruction_id'] == latest['instruction_id']):
        return out
    verdicts = {(r['instruction_id'], r['stage'], r['field']): r for group in ['readback', 'setting'] for r in validation[group]['fields']}
    groups = {}
    for item in state.get('incidents', []):
        key = item['instruction_id'], item['stage'], item['field']
        row = verdicts.get(key)
        if item['status'] == 'OPEN' and not item['voice_completed_at'] and row and row['result'] == 'MISMATCH':
            groups.setdefault(key[:2], []).append(item)
    # Readback sentences precede setting sentences, each remains independently complete.
    for (iid, stage), items in sorted(groups.items(), key=lambda pair: (pair[0][1] != 'READBACK', pair[0][0])):
        phrase = 'READBACK' if stage == 'READBACK' else 'BOTH' if len(items) == 2 else items[0]['field']
        add(phrase, [i['occurrence_id'] for i in items], iid)
    return out


def active(voice):
    return next((item for item in voice.get('attempts', {}).values() if item['status'] == 'PLAYING'), None)


def settle(state, policy, callsign, now, *, ended=False):
    voice = reconcile(state, policy, now, ended=ended)
    attempt = active(voice)
    if attempt:
        valid = {item['candidate_id'] for item in candidates(state, policy, callsign, now, ended=ended)}
        if now >= parsed(attempt['lease_until']):
            attempt.update(status='INTERRUPTED', finished_at=stamp(now), reason='LEASE_EXPIRED')
        elif ended or attempt['candidate_id'] not in valid or voice['inputs']:
            # Keep the reservation until stop acknowledgement/expiry so another
            # browser cannot overlap an as-yet unacknowledged remote stop.
            attempt['cancel_requested'] = True
            attempt['cancel_reason'] = 'INPUT_PRIORITY' if voice['inputs'] else 'NO_LONGER_ELIGIBLE'
    return voice


def view(state, policy, callsign, now, *, ended=False):
    voice = deepcopy(state.get('voice', {}))
    attempt = active(voice)
    if attempt:
        attempt['lease_expired'] = now >= parsed(attempt['lease_until'])
    eligible = candidates(state, policy, callsign, now, ended=ended)
    return dict(version='1', candidates=eligible,
        inputs=list(voice.get('inputs', {}).values()), active_attempt=attempt,
        episodes=voice.get('episodes', {}), history=list(voice.get('attempts', {}).values())[-50:])


def command(db, flight_id, action, payload):
    from app.services import receiving_v2 as receiver
    now = receiver.utc_now()
    with receiver.atomic(db):
        flight, profile = receiver.context(db, flight_id, active=':' not in action, lock=True)
        state = deepcopy(profile.state)
        ended = flight.status == 'ENDED'
        receiver.refresh_validation(db, profile, state, now, ended=ended)
        voice = memory(state)
        data = payload.model_dump(mode='json')
        if action == 'claim':
            previous = voice['attempts'].get(payload.attempt_id)
            if previous:
                if previous['candidate_id'] != payload.candidate_id:
                    raise receiver.ReceivingError(409, 'ID_CONTENT_CONFLICT', 'Attempt ID content differs')
                return deepcopy(previous)
            available = candidates(state, profile.policy, profile.callsign, now)
            candidate = available[0] if available and available[0]['candidate_id'] == payload.candidate_id else None
            if not candidate or voice['inputs'] or active(voice):
                raise receiver.ReceivingError(409, 'INVALID_SEQUENCE', 'Input priority, active playback or stale candidate')
            result = {**candidate, 'attempt_id': payload.attempt_id, 'status': 'PLAYING', 'started_at': stamp(now),
                'lease_until': stamp(now+timedelta(seconds=LEASE_SECONDS)), 'cancel_requested': False}
            voice['attempts'][payload.attempt_id] = result
        elif action == 'input':
            previous = voice['events'].get(payload.event_id)
            if previous:
                if previous['request'] != data:
                    raise receiver.ReceivingError(409, 'ID_CONTENT_CONFLICT', 'Input event content differs')
                return previous['result']
            inputs = voice['inputs']
            if payload.action == 'BEGIN':
                if payload.token in inputs or (payload.kind in ('ATC', 'PILOT') and any(i['kind'] in ('ATC', 'PILOT') for i in inputs.values())):
                    raise receiver.ReceivingError(409, 'INVALID_SEQUENCE', 'Capture already active; request is not queued')
                inputs[payload.token] = dict(token=payload.token, kind=payload.kind, started_at=stamp(now))
            else:
                if payload.token not in inputs or inputs[payload.token]['kind'] != payload.kind:
                    raise receiver.ReceivingError(409, 'CONTEXT_MISMATCH', 'Unknown input token')
                del inputs[payload.token]
            result = dict(event_id=payload.event_id, token=payload.token, action=payload.action, kind=payload.kind)
            voice['events'][payload.event_id] = dict(request=data, result=result)
            settle(state, profile.policy, profile.callsign, now)
        else:
            attempt_id, status = action.rsplit(':', 1)
            result = voice['attempts'].get(attempt_id)
            if not result:
                raise receiver.ReceivingError(404, 'NOT_FOUND', 'Playback attempt not found')
            if result['status'] != 'PLAYING':
                if result['status'] == status:
                    return deepcopy(result)
                raise receiver.ReceivingError(409, 'INVALID_SEQUENCE', 'Attempt is already terminal')
            valid = any(c['candidate_id'] == result['candidate_id'] for c in candidates(state, profile.policy, profile.callsign, now, ended=ended))
            if not valid or ended:
                status = 'CANCELLED'
            elif status == 'COMPLETED' and (result['cancel_requested'] or voice['inputs'] or not valid or now >= parsed(result['lease_until'])):
                status = 'CANCELLED'
            result.update(status=status, finished_at=stamp(now))
            if status == 'COMPLETED':
                for item in state.get('incidents', [])+list(voice['episodes'].values()):
                    if item['occurrence_id'] in result['occurrence_ids']:
                        item['voice_completed_at'] = stamp(now)
        profile.revision += 1
        profile.state = state
        receiver.trace(db, profile, 'VOICE_'+('RESULT' if ':' in action else action.upper()), dict(request=data, result=result), now)
        return deepcopy(result)
