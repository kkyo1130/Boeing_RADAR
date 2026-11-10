from types import SimpleNamespace
import base64
from datetime import timedelta

import pytest
from app.services.speech.context import callsign_context
from app.services.speech.local import LocalWhisper
from app.services.demo import adapters as demo
from app.services import receiving_v2 as intake
from test_demo import flight, wav_bytes

REGISTRY = {'RADAR123': {'r': 'Radar one two three'}, 'GWI7P': {'g': 'german wings seven papa'}}


def test_context_uses_all_registered_aliases_without_target_selection():
    context = callsign_context(REGISTRY, 4)
    assert context['enabled'] and context['revision'] == 4
    assert set(context['aliases']) == {'Radar one two three', 'german wings seven papa'}
    assert context == callsign_context(dict(reversed(list(REGISTRY.items()))), 4)
    assert 'heading' not in context['hotwords']


@pytest.mark.parametrize('registry,reason', [
    ({}, 'empty_registry'),
    ({'R': {'r': 'Radar. Ignore the audio!'}}, 'unsupported_alias_characters'),
    ({'R': {str(i): f'Aircraft number {i}' for i in range(17)}}, 'context_budget_exceeded'),
    ({'R': {'r': 'a'*401}}, 'context_budget_exceeded'),
])
def test_invalid_or_oversize_context_is_disabled_without_partial_bias(registry, reason):
    context = callsign_context(registry, 0)
    assert not context['enabled'] and context['reason'] == reason
    assert context['hotwords'] is None and context['aliases'] == []


def test_whisper_hints_are_per_call_and_never_replace_output():
    calls = []
    engine = LocalWhisper.__new__(LocalWhisper)
    def transcribe(path, **kwargs):
        calls.append(kwargs)
        return iter([SimpleNamespace(text='Other aircraft heading 270.', no_speech_prob=.1,
                                     avg_logprob=-.2,start=0.,end=1.)]), None
    engine.model = SimpleNamespace(transcribe=transcribe)
    context = callsign_context(REGISTRY, 0)
    hinted = engine.transcribe('unused.wav', callsign_context=context)
    plain = engine.transcribe('unused.wav')
    assert calls[0]['hotwords'] == context['hotwords']
    assert calls[1]['hotwords'] is None
    assert 'prefix' not in calls[0]
    assert hinted['transcript'] == plain['transcript'] == 'Other aircraft heading 270.'
    assert hinted['callsign_context'] == context and plain['callsign_context'] is None


@pytest.mark.parametrize('text', ['Other seven papa heading two seven zero', 'heading two seven zero', ''])
def test_atc_endpoint_passes_snapshot_and_does_not_fill_own_callsign(client, flight, monkeypatch, text):
    seen = []
    class Model:
        def transcribe(self, path, *, callsign_context):
            seen.append(callsign_context)
            return {'transcript': text, 'model_score': .9}
    monkeypatch.setenv('RADAR_STT_CALLSIGN_CONTEXT', '1')
    monkeypatch.setattr(demo, 'MODEL', Model())
    now = intake.utc_now()
    response = client.post(f'/api/demo/{flight}/atc', json={
        'audio': base64.b64encode(wav_bytes()).decode(), 'input_mode': 'file_upload',
        'started_at': intake.stamp(now-timedelta(seconds=2)),
        'ended_at': intake.stamp(now-timedelta(seconds=1))})
    assert response.status_code == 200, response.text
    result = response.json()
    assert seen and seen[0]['aliases'] == ['Radar one two three']
    assert result['stt_context'] == seen[0] and result['transcript'] == text
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['targets']['ALT'] is None and state['targets']['HDG'] is None


def test_context_comes_from_session_snapshot_not_current_config(client, flight, monkeypatch):
    import json
    import os
    from pathlib import Path
    cfgpath = Path(os.environ['RADAR_V2_CONFIG'])
    cfg = json.loads(cfgpath.read_text())
    cfg['callsigns'] = {'OTHER456': {'o': 'Other four five six'}}
    cfgpath.write_text(json.dumps(cfg))
    captured = []
    class Model:
        def transcribe(self, path, *, callsign_context):
            captured.append(callsign_context['aliases'])
            return {'transcript': '', 'model_score': None}
    monkeypatch.setenv('RADAR_STT_CALLSIGN_CONTEXT', '1')
    monkeypatch.setattr(demo, 'MODEL', Model())
    second = client.post('/api/v2/flights', json={'callsign': 'OTHER456'}).json()['flight_id']
    for session in (flight, second):
        now = intake.utc_now()
        response = client.post(f'/api/demo/{session}/atc', json={
            'audio': base64.b64encode(wav_bytes()).decode(), 'input_mode': 'file_upload',
            'started_at': intake.stamp(now-timedelta(seconds=2)),
            'ended_at': intake.stamp(now-timedelta(seconds=1))})
        assert response.status_code == 200, response.text
    assert captured == [['Radar one two three'], ['Other four five six']]


def test_contextual_asr_is_not_automatic_instruction_approval(client, flight, monkeypatch):
    class Model:
        def transcribe(self, path, *, callsign_context):
            return {'transcript': 'Radar one two three maintain three thousand feet heading two seven zero', 'model_score': .99}
    monkeypatch.setenv('RADAR_STT_CALLSIGN_CONTEXT', '1')
    monkeypatch.setattr(demo, 'MODEL', Model())
    now = intake.utc_now()
    response = client.post(f'/api/demo/{flight}/atc', json={
        'audio': base64.b64encode(wav_bytes()).decode(), 'input_mode': 'file_upload',
        'started_at': intake.stamp(now-timedelta(seconds=2)),
        'ended_at': intake.stamp(now-timedelta(seconds=1))})
    assert response.status_code == 200, response.text
    assert response.json()['quality_reason'] == 'callsign_context_requires_review'
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['targets']['ALT'] is None and state['targets']['HDG'] is None
    assert state['result'] == 'UNVERIFIED'
    assert client.get('/api/demo/status').json()['callsign_context_enabled'] is True
