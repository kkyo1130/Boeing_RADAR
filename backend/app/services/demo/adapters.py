import base64
import io
import os
import threading
import time
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image
from app.schemas.observation_v2 import ObservationV2, SpeechSegmentV2
from app.services import receiving_v2 as intake, media_v2
from app.services.structure_rules import normalize, parse_command

SCENARIOS = {
    'baseline': 'Radar one two three climb and maintain three thousand feet heading two seven zero',
    'altitude': 'Radar one two three climb and maintain three thousand five hundred feet heading two seven zero',
    'heading': 'Radar one two three maintain three thousand feet heading two nine zero',
}
STT_LOCK = threading.Lock()
MODEL = None
CAMERAS = {}
CAMERA_LOCK = threading.Lock()


def error(message, status=422):
    raise intake.ReceivingError(status, 'INVALID_PAYLOAD', message)


def quality(score, sufficient=True, reason=None):
    return dict(model_score=score, input_quality='SUFFICIENT' if sufficient else 'INSUFFICIENT',
                reason=reason or (None if score is not None else 'deterministic_registered_scenario'),
                score_calibrated=False, calibration_ref=None)


def reading(value, field, score, reason=None, raw=None):
    return dict(value=value, unit='ft' if field == 'ALT' else 'deg',
                validity='VALID' if value is not None else 'UNREADABLE',
                reason=reason if value is None else None, raw_text=raw,
                quality=quality(score, value is not None, reason))


def base(flight, revision, observed, evidence):
    return dict(schema_version='2', observation_id='obs-'+uuid4().hex, flight_id=flight,
                target_revision=revision, observed_at=observed, processed_at=intake.stamp(intake.utc_now()),
                time_basis='HOST_RECEIVE', time_reason=None,
                channel_health=dict(status='AVAILABLE', reason=None), evidence_refs=evidence,
                evidence_unavailable_reason=None)


def speech_payload(flight, revision, segment, transcript, score, registry, audio, quality_reason=None):
    text = normalize(transcript)
    matches = [(canonical, alias, raw) for canonical, aliases in registry.items()
               for alias, raw in aliases.items() if text.startswith(normalize(raw)+' ')]
    values, issues = {}, ['callsign_not_recognized']
    call = dict(value=None, alias_key=None, raw_text=None, validity='UNREADABLE',
                reason='callsign_not_recognized', quality=quality(score, False, 'callsign_not_recognized'))
    if len(matches) == 1:
        canonical, alias, raw = matches[0]
        values, issues = parse_command(text[len(normalize(raw))+1:])
        call = dict(value=canonical, alias_key=alias, raw_text=raw, validity='VALID', reason=None,
                    quality=quality(score, not quality_reason, quality_reason))
    if issues:
        values = {}  # No partial guess from an unconsumed transcript.
    fields = {key: reading(value, key, score, raw=str(value)) for key, value in values.items()}
    if quality_reason:
        for field in fields.values():
            field['quality'] = quality(score, False, quality_reason)
    payload = base(flight, revision, segment['started_at'], [dict(**audio, kind='AUDIO', field=None, roi=None)])
    payload.update(source='ATC' if segment['role'] == 'ATC' else 'READBACK',
                   segment_id=segment['segment_id'], attempt_id=segment['attempt_id'],
                   atc_input_id=segment['atc_input_id'], transcript=transcript or None,
                   transcript_reason=None if transcript else 'no_speech_detected', callsign=call,
                   mention_status='UNKNOWN' if issues else 'KNOWN', mentioned_fields=list(fields),
                   instruction_check='NEEDS_REVIEW' if issues or quality_reason else 'PASS', fields=fields)
    if segment['role'] == 'PILOT':
        payload['instruction_id'] = segment['instruction_id']
    return payload


def register(db, flight, body, audio, role):
    segment = dict(schema_version='2', flight_id=flight, segment_id='seg-'+uuid4().hex,
                   attempt_id='try-'+uuid4().hex, atc_input_id=body['atc_input_id'] if role == 'PILOT' else 'atc-'+uuid4().hex,
                   role=role, role_basis='PILOT_PTT' if role == 'PILOT' else 'ATC_PLAYBACK',
                   started_at=body['started_at'], ended_at=body['ended_at'], complete=True,
                   interruption_reason=None, audio_ref=audio['ref'], audio_unavailable_reason=None)
    receipt = intake.register_segment(db, flight, SpeechSegmentV2.model_validate(segment))
    return {**segment, 'instruction_id': receipt['instruction_id']}


def profile(db, flight):
    _, row = intake.context(db, flight, active=True)
    result = (row.revision, row.callsign_registry)
    db.rollback()  # Reads must not leave an implicit transaction before intake.atomic.
    return result


def receive_speech(db, flight, body, data, *, scenario=None):
    revision, registry = profile(db, flight)
    media_v2.validate(data, 'audio/wav')
    with wave.open(io.BytesIO(data)) as wav:
        duration = wav.getnframes()/wav.getframerate()
        if duration > 30: error('Record at most 30 seconds')
        import numpy as np
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(float)/32768
        rms = float(np.sqrt(np.mean(pcm**2)))
        clipped = float(np.mean(np.abs(pcm) >= .998))
    if intake.parsed(body['ended_at']) > intake.utc_now() or intake.parsed(body['started_at']) >= intake.parsed(body['ended_at']):
        error('Invalid capture interval')
    audio = media_v2.upload(db, flight, data, 'audio/wav')
    segment = register(db, flight, body, audio, 'ATC' if scenario else 'PILOT')
    reason = 'silence_or_weak_signal' if rms < .01 else 'clipped_audio' if clipped > .01 else None
    transcript, score = '', None
    if scenario:
        transcript = SCENARIOS[scenario]
    else:
        global MODEL
        if not STT_LOCK.acquire(blocking=False): error('Speech recognition is busy; retry recording', 409)
        try:
            from app.services.speech.local import LocalWhisper
            if MODEL is None:
                MODEL = LocalWhisper(os.environ.get('RADAR_WHISPER_MODEL', ''))
            with TemporaryDirectory() as temp:
                path = Path(temp)/'input.wav'; path.write_bytes(data)
                result = MODEL.transcribe(path)
            transcript, score = result['transcript'], result['model_score']
            if score is None or score < .5: reason = reason or 'low_or_unknown_model_score'
        except Exception as exc:
            reason = 'speech_engine_unavailable'
        finally:
            STT_LOCK.release()
    payload = speech_payload(flight, revision, segment, transcript, score, registry, audio, reason)
    receipt, _ = intake.receive(db, flight, ObservationV2.model_validate(payload), 'OBSERVATION')
    return dict(receipt=receipt, transcript=transcript, model_score=score, quality_reason=reason,
                input_mode='registered_scenario' if scenario else 'uploaded_wav_local_whisper',
                instruction_id=segment['instruction_id'])


def decode_image(encoded):
    try:
        data = base64.b64decode(encoded, validate=True)
        media_v2.validate(data, 'image/jpeg')
        image = Image.open(io.BytesIO(data)).convert('RGB')
        if image.width > 2560 or image.height > 1440: error('Use camera resolution at most 2560x1440')
        return data, image
    except (ValueError, OSError):
        error('Invalid camera image')


def calibrate(flight, encoded, rois):
    from radar_vision.stream import Stabilizer
    _, image = decode_image(encoded)
    for roi in rois.values():
        x1,y1,x2,y2 = roi
        if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height): error('ROI outside frame')
        if x2-x1 < 10 or y2-y1 < 10: error('Select the complete digit window')
    from .tracking import reference
    tracked = reference(image, rois)
    token = uuid4().hex
    with CAMERA_LOCK:
        # One active calibration per flight; all caches are bounded.
        for key in list(CAMERAS):
            if CAMERAS[key]['flight'] == flight or time.monotonic()-CAMERAS[key]['updated'] > 1800:
                del CAMERAS[key]
        if len(CAMERAS) >= 4: error('Too many camera sessions', 409)
        CAMERAS[token] = dict(tracked=tracked, flight=flight, size=image.size, rois=rois, stable=Stabilizer(3),
                             updated=time.monotonic(), last=None, count=0, targets=None, emitted=None, expired=False)
    return dict(token=token, image_size=image.size)


def camera(db, flight, body):
    from radar_vision.poc import recognize
    with CAMERA_LOCK:
        session = CAMERAS.get(body['token'])
        if session is None or session['flight'] != flight: error('Recalibrate the camera', 409)
        if session['expired']: error('Camera stream timed out; recalibrate', 409)
        if session['last'] and body['captured_at'] <= session['last']: error('Duplicate or out-of-order frame', 409)
        if session['count'] >= 600: error('Demo frame limit reached; recalibrate for a new run', 409)
        session['last'] = body['captured_at']; session['count'] += 1
        now = intake.utc_now()
        age = (now-intake.parsed(body['captured_at'])).total_seconds()
        if age < -.1 or age > 5:
            session['stable'].reset(); error('Stale camera frame')
        _, image = decode_image(body['image'])
        if image.size != session['size']:
            session['stable'].reset(); error('Camera resolution changed; recalibrate')
        state = intake.get_state(db, flight); db.rollback()
        targets = [(k, v['instruction_id'] if v else None) for k,v in state['targets'].items()]
        if targets != session['targets'] or time.monotonic()-session['updated'] > 5:
            session['stable'].reset()
        session['targets'] = targets
        from .tracking import locate
        shift = locate(image, session['tracked'])
        config = dict(image_size=list(image.size), minimum_model_score=.5)
        for name, field in [('altitude','ALT'),('heading','HDG')]:
            roi=session['rois'][field]
            if shift is not None: roi=[roi[0]+shift[0],roi[1]+shift[1],roi[2]+shift[0],roi[3]+shift[1]]
            if not (0 <= roi[0] < roi[2] <= image.width and 0 <= roi[1] < roi[3] <= image.height): shift=None; roi=session['rois'][field]
            config[name] = dict(roi=roi, unit='feet' if field=='ALT' else 'degrees')
        with TemporaryDirectory() as temp:
            path=Path(temp)/'frame.png'; image.save(path)
            result=recognize(path, config, os.environ['RADAR_OCR_BINARY'], Path(temp)/'ocr', body['captured_at'])
        if shift is None:
            for item in result['fields'].values(): item.update(value=None, reason='panel_tracking_lost')
        if (intake.utc_now()-intake.parsed(body['captured_at'])).total_seconds() > 5:
            session['stable'].reset()
            for item in result['fields'].values(): item.update(value=None, reason='stale_frame')
        session['stable'].apply(result['fields'])
        session['updated']=time.monotonic()
        evidence_buffer=io.BytesIO();image.save(evidence_buffer,format='JPEG',quality=85)
        evidence=media_v2.upload(db, flight, evidence_buffer.getvalue(), 'image/jpeg')
        payload=base(flight,body['target_revision'],body['captured_at'],[dict(**evidence,kind='FRAME',field=None,roi=None)])
        payload.update(source='COCKPIT',frame_id='frame-'+uuid4().hex,fields={})
        for name,key in [('altitude','ALT'),('heading','HDG')]:
            item=result['fields'][name]
            payload['fields'][key]=reading(item['value'],key,item['model_score'],item['reason'],item['raw_text'])
        receipt,_=intake.receive(db,flight,ObservationV2.model_validate(payload),'OBSERVATION')
        session['emitted']=time.monotonic()
        return dict(receipt=receipt,fields=result['fields'],captured_at=body['captured_at'])


def expire_camera(db, flight):
    """Called before UI state reads; a hung/closed tab cannot keep a camera normal."""
    if os.getenv('RADAR_DEMO_ENABLED') != '1': return
    from app.schemas.observation_v2 import HealthEventV2
    for item in list(CAMERAS.values()):
        if item['flight'] != flight or item['expired'] or item['emitted'] is None: continue
        if time.monotonic()-item['emitted'] <= 6: continue
        item['expired']=True
        try:
            event=HealthEventV2(schema_version='2',event_id='health-'+uuid4().hex,flight_id=flight,
                channel='CAMERA',observed_at=intake.stamp(intake.utc_now()),
                health={'status':'DISCONNECTED','reason':'demo_camera_timeout'})
            intake.receive(db,flight,event,'HEALTH')
        except intake.ReceivingError:
            db.rollback()
