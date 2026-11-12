"""Stub-ASR routing/state tests; hardware evidence is recorded separately."""
import base64
from datetime import timedelta
import pytest
from test_demo import flight, wav_bytes
from app.services import receiving_v2 as intake
from app.services.demo import adapters as demo

TEXT = 'Radar one two three climb and maintain three thousand feet heading two seven zero'

def body(**extra):
    now = intake.utc_now()
    return dict(audio=base64.b64encode(wav_bytes()).decode(), started_at=intake.stamp(now-timedelta(seconds=2)), ended_at=intake.stamp(now-timedelta(seconds=1)), **extra)

def asr(monkeypatch, text=TEXT, raises=False):
    calls = []
    class Model:
        def transcribe(self, path):
            calls.append(path.read_bytes())
            if raises: raise RuntimeError('model offline')
            return {'transcript':text, 'model_score':.9}
    monkeypatch.setattr(demo, 'MODEL', Model())
    return calls

@pytest.mark.parametrize('mode', ['microphone_live', 'microphone_playback', 'file_upload'])
def test_atc_asr_then_bound_pilot(client, flight, monkeypatch, mode):
    calls = asr(monkeypatch)
    segments = []
    original = intake.register_segment
    def capture_segment(db, flight, segment):
        segments.append(segment)
        return original(db, flight, segment)
    monkeypatch.setattr(intake, 'register_segment', capture_segment)
    atc = client.post(f'/api/demo/{flight}/atc', json=body(input_mode=mode))
    assert atc.status_code == 200, atc.text
    result = atc.json()
    assert result['role'] == 'ATC' and result['input_mode'] == mode
    assert result['transcript'] == TEXT and calls == [wav_bytes()]
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['readback_required']['atc_input_id'] == result['atc_input_id']
    assert state['targets']['ALT']['value'] == 3000
    assert state['targets']['HDG']['value'] == 270
    now = intake.utc_now()
    pilot = body(atc_input_id=result['atc_input_id'])
    pilot.update(started_at=intake.stamp(now-timedelta(seconds=.8)), ended_at=intake.stamp(now-timedelta(seconds=.1)))
    response = client.post(f'/api/demo/{flight}/readback', json=pilot)
    assert response.status_code == 200, response.text
    assert response.json()['role'] == 'PILOT'
    assert response.json()['atc_input_id'] == result['atc_input_id']
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['validation']['readback']['result'] == 'NORMAL'
    assert len(calls) == 2
    assert [s.role_basis for s in segments] == [('ATC_DEMO_MICROPHONE' if mode == 'microphone_live' else 'ATC_FILE_UPLOAD' if mode == 'file_upload' else 'ATC_PLAYBACK'), 'PILOT_PTT']

@pytest.mark.parametrize('text,raises', [('unintelligible',False), (TEXT+' if able',False), ('',True)])
def test_failed_atc_blocks_old_pilot(client, flight, monkeypatch, text, raises):
    asr(monkeypatch)
    old = client.post(f'/api/demo/{flight}/atc', json=body(input_mode='file_upload')).json()
    asr(monkeypatch, text, raises)
    payload = body(input_mode='microphone_live'); now = intake.utc_now()
    payload.update(started_at=intake.stamp(now-timedelta(seconds=.8)), ended_at=intake.stamp(now-timedelta(seconds=.2)))
    new = client.post(f'/api/demo/{flight}/atc', json=payload)
    assert new.status_code == 200, new.text
    assert new.json()['atc_input_id'] != old['atc_input_id']
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['validation']['readback']['result'] != 'NORMAL'
    assert state['targets']['ALT']['value'] == 3000
    asr(monkeypatch)
    pilot = client.post(f'/api/demo/{flight}/readback', json=body(atc_input_id=old['atc_input_id']))
    assert pilot.status_code == 409, pilot.text

def test_busy_has_no_state_side_effect(client, flight, monkeypatch):
    calls = asr(monkeypatch)
    before = client.get(f'/api/v2/flights/{flight}/state').json()
    assert demo.STT_LOCK.acquire(blocking=False)
    try: response = client.post(f'/api/demo/{flight}/atc', json=body(input_mode='file_upload'))
    finally: demo.STT_LOCK.release()
    assert response.status_code == 409
    after = client.get(f'/api/v2/flights/{flight}/state').json()
    assert after['revision'] == before['revision'] and not calls
    assert after['readback_required'] is None

@pytest.mark.parametrize('extra', [{'transcript':TEXT}, {'role':'PILOT'}, {'atc_input_id':'old'}, {'input_mode':'guess'}])
def test_rejects_hints_and_role_override(client, flight, extra):
    payload = body(input_mode='file_upload'); payload.update(extra)
    assert client.post(f'/api/demo/{flight}/atc', json=payload).status_code == 422

def test_bad_audio_no_atc(client, flight, monkeypatch):
    calls = asr(monkeypatch)
    payload = body(input_mode='file_upload'); payload['audio'] = base64.b64encode(b'not wav').decode()
    response = client.post(f'/api/demo/{flight}/atc', json=payload)
    assert response.status_code == 422, response.text
    assert not calls
    assert client.get(f'/api/v2/flights/{flight}/state').json()['readback_required'] is None


@pytest.mark.parametrize('pilot_text,result',[(TEXT,'NORMAL'),('Radar one two three climb and maintain three thousand five hundred feet heading two seven zero','MISMATCH')])
def test_file_atc_then_pilot_uses_asr_and_records_file_roles(client,flight,monkeypatch,pilot_text,result):
    calls=asr(monkeypatch)
    segments=[];original=intake.register_segment
    def capture(db,flight,segment):
        segments.append(segment)
        return original(db,flight,segment)
    monkeypatch.setattr(intake,'register_segment',capture)
    atc=client.post(f'/api/demo/{flight}/atc',json=body(input_mode='file_upload'))
    assert atc.status_code==200,atc.text
    asr(monkeypatch,pilot_text)
    now=intake.utc_now()
    pilot_body=body(input_mode='file_upload',atc_input_id=atc.json()['atc_input_id'])
    pilot_body.update(started_at=intake.stamp(now-timedelta(seconds=.03)),ended_at=intake.stamp(now-timedelta(seconds=.01)))
    pilot=client.post(f'/api/demo/{flight}/readback',json=pilot_body)
    assert pilot.status_code==200,pilot.text
    assert pilot.json()['input_mode']=='file_upload' and pilot.json()['role']=='PILOT'
    assert [s.role_basis for s in segments]==['ATC_FILE_UPLOAD','PILOT_FILE_UPLOAD']
    state=client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['validation']['readback']['result']==result
    assert calls==[wav_bytes()]


def test_file_role_mismatch_rejected_by_contract():
    from app.schemas.observation_v2 import SpeechSegmentV2
    from pydantic import ValidationError
    from uuid import uuid4
    now=intake.utc_now()
    data=dict(schema_version='2',flight_id='f',segment_id='s',attempt_id='a',atc_input_id='i',role='ATC',role_basis='PILOT_FILE_UPLOAD',started_at=intake.stamp(now-timedelta(seconds=2)),ended_at=intake.stamp(now-timedelta(seconds=1)),complete=True,interruption_reason=None,audio_ref='stored:x',audio_unavailable_reason=None)
    with pytest.raises(ValidationError):SpeechSegmentV2.model_validate(data)
