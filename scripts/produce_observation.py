"""File/microphone/vision adapters for the single v2 receiving contract.

No producer verdict: existing v2 structure, freshness, incident and voice policy
remain authoritative. Unknown capture time and incomplete utterances stay held.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from tempfile import TemporaryDirectory
from uuid import uuid4
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'communication'))


def stamp(value=None):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError('Capture timestamps require a timezone')
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def quality(score, reasons):
    return dict(model_score=score, input_quality='INSUFFICIENT' if reasons else 'SUFFICIENT',
                reason='; '.join(reasons) if reasons else 'model_score_unknown' if score is None else None,
                score_calibrated=False, calibration_ref=None)


class Producer:
    def __init__(self, base, flight, source):
        self.base, self.flight, self.source = base.rstrip('/'), flight, source
        self.url = f'/api/v2/flights/{flight}'

    def request(self, path, data=None, media='application/json'):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        with urlopen(Request(self.base+path, data=data, headers={'Content-Type': media}), timeout=30) as response:
            return json.load(response)

    def state(self):
        return self.request(self.url+'/state')

    def evidence(self, path, media, kind, field=None):
        stored = self.request(self.url+'/media', Path(path).read_bytes(), media)
        return dict(**stored, kind=kind, field=field, roi=None)

    def envelope(self, captured, revision, *, processed=None):
        return dict(schema_version='2', observation_id='obs-'+uuid4().hex, flight_id=self.flight,
            source=self.source, observed_at=stamp(captured) if captured else None,
            processed_at=stamp(processed), time_basis='CAPTURED' if captured else 'UNKNOWN',
            time_reason=None if captured else 'original_capture_time_unknown', target_revision=revision,
            channel_health=dict(status='AVAILABLE', reason=None), fields={}, evidence_refs=[],
            evidence_unavailable_reason='original_media_unavailable')

    def send(self, body):
        from app.schemas.observation_v2 import ObservationV2
        body = ObservationV2.model_validate(body).model_dump(mode='json')
        return self.request(self.url+'/observations', body)

    def health(self, reason, *, observed=None, status='DISCONNECTED'):
        from app.schemas.observation_v2 import HealthEventV2
        body = dict(schema_version='2', event_id='health-'+uuid4().hex, flight_id=self.flight,
            channel='CAMERA' if self.source == 'COCKPIT' else 'MICROPHONE',
            observed_at=stamp(observed), health=dict(status=status, reason=None if status == 'AVAILABLE' else reason))
        return self.request(self.url+'/health-events', HealthEventV2.model_validate(body).model_dump(mode='json'))

    def input(self, token, action):
        return self.request(self.url+'/voice/inputs', dict(event_id='input-'+uuid4().hex,
            token=token, kind='ATC' if self.source == 'ATC' else 'PILOT', action=action))

    def wait_for_playback_stop(self):
        # Remote browser must acknowledge stop. An expired lease alone does not
        # prove the loudspeaker stopped, so do not begin capture in that case.
        for _ in range(50):
            if self.state()['voice']['active_attempt'] is None:
                return
            time.sleep(.1)
        raise RuntimeError('Playback stop was not acknowledged; input not started')


def speech_fields(transcript, callsign, alias_key, alias_text, score, reasons):
    from app.services.structure_rules import normalize, parse_command
    normalized = normalize(transcript or '')
    prefix = normalize(alias_text)
    found = normalized.startswith(prefix+' ')
    values, issues = parse_command(normalized[len(prefix)+1:]) if found else ({}, [(None, 'NEEDS_REVIEW', 'CALLSIGN_NOT_FOUND')])
    q = quality(score, reasons)
    fields = {name: dict(value=value, unit='ft' if name == 'ALT' else 'deg', raw_text=str(value),
                        validity='VALID', reason=None, quality=q) for name, value in values.items()}
    valid = found and bool(fields) and not issues and not reasons
    return dict(transcript=transcript or None, transcript_reason=None if transcript else 'no_speech_recognized',
        callsign=dict(raw_text=alias_text if found else None, value=callsign if found else None,
            alias_key=alias_key if found else None, validity='VALID' if found else 'UNREADABLE',
            reason=None if found else 'callsign_not_recognized', quality=q),
        mention_status='KNOWN' if valid else 'UNKNOWN', mentioned_fields=list(fields),
        instruction_check='PASS' if valid else 'NEEDS_REVIEW', fields=fields)


def audio(producer, args):
    from radar_audio.audio import prepare, record_microphone
    from app.services.speech.local import LocalWhisper
    if producer.source not in ('ATC', 'READBACK'):
        raise ValueError('Audio source must be ATC or READBACK')
    engine = LocalWhisper(args.model)
    token = 'capture-'+uuid4().hex
    producer.input(token, 'BEGIN')
    try:
        producer.wait_for_playback_stop()
        # Bind to the revision BEFORE capture, never to a new target after OCR/STT.
        context = producer.state()
        target = context['readback_required']
        if producer.source == 'READBACK' and not target:
            raise ValueError('No current ATC instruction to read back')
        with TemporaryDirectory(prefix='radar-audio-') as folder:
            path, captured = args.wav, args.captured_at
            if args.microphone:
                if producer.source != 'READBACK':
                    raise ValueError('Microphone input must use READBACK')
                path = Path(folder)/'microphone.wav'
                captured = record_microphone(path, args.seconds, args.device)
            segments = list(prepare(path, Path(folder)/'segments', seconds=30))
            if len(segments) != 1:
                raise ValueError('Provide one utterance of at most 30 seconds; do not split commands into adopted instructions')
            segment = segments[0]
            evidence = producer.evidence(segment['path'], 'audio/wav', 'AUDIO')
            processed_start = datetime.fromisoformat(stamp())
            start = datetime.fromisoformat(stamp(captured)) if captured else processed_start
            end = start+timedelta(seconds=segment['duration_seconds']) if captured else processed_start+timedelta(microseconds=1)
            complete = bool(captured and args.complete_utterance)
            registered = dict(schema_version='2', flight_id=producer.flight,
                segment_id=segment['segment_id'], attempt_id='try-'+uuid4().hex,
                atc_input_id='atc-'+uuid4().hex if producer.source == 'ATC' else target['atc_input_id'],
                role='ATC' if producer.source == 'ATC' else 'PILOT',
                role_basis='ATC_PLAYBACK' if producer.source == 'ATC' else 'PILOT_PTT',
                started_at=stamp(start), ended_at=stamp(end), complete=complete,
                interruption_reason=None if complete else 'capture_time_or_utterance_completion_unconfirmed',
                audio_ref=evidence['ref'], audio_unavailable_reason=None)
            receipt = producer.request(producer.url+'/speech-segments', registered)
            result = engine.transcribe(segment['path'])
            body = producer.envelope(captured, context['revision'])
            reasons = list(segment['quality_reasons'])
            if not args.reviewed_channel:
                reasons.append('channel_overlap_noise_feedback_unchecked')
            body.update(speech_fields(result['transcript'], args.callsign, args.alias_key,
                                      args.alias_text, result['model_score'], reasons))
            body.update(segment_id=registered['segment_id'], attempt_id=registered['attempt_id'],
                        atc_input_id=registered['atc_input_id'], evidence_refs=[evidence], evidence_unavailable_reason=None)
            if producer.source == 'READBACK':
                body['instruction_id'] = receipt['instruction_id']
            if reasons:
                body['channel_health'] = dict(status='DEGRADED', reason='; '.join(reasons))
            print(json.dumps(producer.send(body)))
    finally:
        producer.input(token, 'END')


def vision(producer, args):
    if producer.source != 'COCKPIT':
        raise ValueError('Vision source must be COCKPIT')
    source = sys.stdin if str(args.events) == '-' else args.events.open()
    try:
        for line in source:
            event = json.loads(line)
            if event['event_type'] == 'health':
                # Offline events without an original health timestamp cannot
                # pretend to report a current camera status.
                observed = event.get('emitted_at')
                if not observed:
                    raise ValueError('Vision health event requires its original timestamp')
                health = event['health']
                print(json.dumps(producer.health(health['reason'], observed=observed,
                    status={'available':'AVAILABLE','degraded':'DEGRADED','unavailable':'DISCONNECTED'}[health['status']])))
                continue
            original = event['observation']
            captured = original['captured_at'] if event['input_mode'] == 'camera' else None
            # The producer records the revision before capture when available.
            # 0 is conservative; backend also checks adopted_at for every field.
            body = producer.envelope(captured, event.get('target_revision', args.target_revision), processed=original['processed_at'])
            body['frame_id'] = original['frame_id']
            body['channel_health'] = dict(status={'available':'AVAILABLE','degraded':'DEGRADED','unavailable':'DISCONNECTED'}[event['health']['status']], reason=event['health']['reason'])
            for original_name, name in [('altitude','ALT'),('heading','HDG')]:
                field = original['fields'][original_name]
                reason = field['reason']
                raw = field['raw_text']
                if name == 'ALT' and field.get('display_unit') == 'FL' and raw:
                    raw = 'FL '+raw.zfill(3)
                body['fields'][name] = dict(value=field['value'], unit='ft' if name=='ALT' else 'deg',
                    raw_text=raw, validity='VALID' if field['value'] is not None else 'UNREADABLE',
                    reason=reason, quality=quality(field['model_score'], [reason] if reason else []))
                if field.get('evidence'):
                    body['evidence_refs'].append(producer.evidence(field['evidence'], 'image/png', 'FRAME', name))
            if body['evidence_refs']:
                body['evidence_unavailable_reason'] = None
            print(json.dumps(producer.send(body)))
    finally:
        if source is not sys.stdin:
            source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:8000')
    parser.add_argument('--flight', required=True)
    parser.add_argument('--source', choices=['ATC','READBACK','COCKPIT'], required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sound = sub.add_parser('audio')
    inputs = sound.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--wav', type=Path)
    inputs.add_argument('--microphone', action='store_true')
    sound.add_argument('--model', type=Path, required=True)
    sound.add_argument('--callsign', required=True)
    sound.add_argument('--alias-key', required=True)
    sound.add_argument('--alias-text', required=True, help='Registered alias; must occur in the actual transcript')
    sound.add_argument('--captured-at', help='Original timezone-aware capture timestamp, never processing time')
    sound.add_argument('--seconds', type=int, default=10)
    sound.add_argument('--device')
    sound.add_argument('--reviewed-channel', action='store_true')
    sound.add_argument('--complete-utterance', action='store_true', help='Operator confirms no clipped/incomplete command')
    image = sub.add_parser('vision')
    image.add_argument('--events', type=Path, required=True)
    image.add_argument('--target-revision', type=int, required=True, help='Server revision read BEFORE starting capture; restart adapter after new ATC adoption')
    args = parser.parse_args()
    producer = Producer(args.server, args.flight, args.source)
    (audio if args.command == 'audio' else vision)(producer, args)


if __name__ == '__main__':
    main()
