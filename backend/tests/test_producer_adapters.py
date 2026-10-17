import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from test_three_state_decision import rig, settings
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('radar_producer', ROOT / 'scripts/produce_observation.py')
producer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer_module)


def connect(rig, source):
    client, _, flight, c = rig
    producer = producer_module.Producer('http://unused', flight, c, source, f'test-{source}')
    def request(path, data=None, media='application/json'):
        response = (client.get(path) if data is None else
                    client.post(path, json=data) if isinstance(data, dict) else
                    client.post(path, content=data, headers={'Content-Type': media}))
        assert response.is_success, response.text
        return response.json()
    producer.request = request
    return producer


def test_audio_file_unknown_time_stays_unverified_and_original_is_stored(rig, tmp_path, monkeypatch):
    import wave
    from app.services.speech import local
    settings(rig)
    path = tmp_path / 'speech.wav'
    with wave.open(str(path), 'wb') as target:
        target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        target.writeframes(b'\x00\x10' * 16000)
    # Provider stub tests wiring only, never counted as a Whisper model result.
    class Stub:
        def __init__(self, model):
            pass
        def transcribe(self, path):
            return {'transcript': 'RADAR1 altitude 3000 heading 270', 'model_score': .9}
    monkeypatch.setattr(local, 'LocalWhisper', Stub)
    producer = connect(rig, 'ATC')
    producer_module.audio(producer, SimpleNamespace(wav=path, captured_at=None, microphone=False,
        model=tmp_path, seconds=10, device=None, callsign='RADAR1', reviewed_channel=True))
    events = rig[0].get(f'/api/v1/flights/{rig[2]}/observation-events').json()
    observed = events[0]['payload']
    assert observed['captured_at'] is None and observed['capture_time_basis'] == 'unknown'
    assert 'capture_time_unknown' in events[0]['reasons']
    assert rig[0].get(observed['evidence'][0]['reference']).status_code == 200
    assert rig[0].get(f'/api/v1/clearances/{rig[3]}').json()['verdict'] == 'UNVERIFIED'


def test_health_events_never_carry_previous_numeric_values(rig):
    settings(rig)
    producer = connect(rig, 'COCKPIT')
    # Clock injection only aligns this synthetic health event with the fixture server.
    original = producer.envelope
    def envelope(*args):
        body = original(*args)
        body['processed_at'] = rig[1][0].isoformat()
        return body
    producer.envelope = envelope
    assert producer.health('camera', 'camera_disconnected')['accepted']
    event = rig[0].get(f'/api/v1/flights/{rig[2]}/observation-events').json()[0]['payload']
    assert event['fields'] is None and event['observation_id'] is None
    assert event['evidence'] == [] and event['health']['status'] == 'unavailable'


@pytest.mark.parametrize('mode,verdict', [('camera', 'NORMAL'), ('video', 'UNVERIFIED')])
def test_vision_roi_binding_and_unknown_video_time(rig, tmp_path, mode, verdict):
    from datetime import timedelta
    from PIL import Image
    from test_three_state_decision import data, send
    settings(rig)
    send(rig, data(rig, 'ATC'))
    send(rig, data(rig, 'READBACK'))
    rig[1][0] += timedelta(seconds=1)
    stamp = rig[1][0].isoformat()
    path = tmp_path / 'roi.png'
    Image.new('RGB', (20, 20), 'white').save(path)
    # Synthetic stream event verifies adapter wiring, not camera/OCR accuracy.
    observed = {'frame_id': f'synthetic-{mode}-frame', 'captured_at': stamp, 'processed_at': stamp,
                'fields': {name: {'value': value, 'raw_text': str(value), 'model_score': .9,
                                 'reason': None, 'evidence': str(path)}
                           for name, value in [('altitude', 3000), ('heading', 270)]}}
    events = tmp_path / 'events.jsonl'
    events.write_text(json.dumps({'event_type': 'observation', 'input_mode': mode,
                                 'health': {'status': 'available', 'reason': None}, 'observation': observed})+'\n')
    producer_module.vision(connect(rig, 'COCKPIT'), SimpleNamespace(events=events))
    state = rig[0].get(f'/api/v1/clearances/{rig[3]}').json()
    assert state['verdict'] == verdict
    event = rig[0].get(f'/api/v1/flights/{rig[2]}/observation-events').json()[-1]['payload']
    assert event['sample_id'] == observed['frame_id']
    if mode == 'camera':
        from datetime import datetime
        assert datetime.fromisoformat(event['captured_at'].replace('Z', '+00:00')) == datetime.fromisoformat(stamp)
    else:
        assert event['captured_at'] is None
    assert all(rig[0].get(e['reference']).status_code == 200 for e in event['evidence'])
