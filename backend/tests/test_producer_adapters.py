import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import wave
import pytest
from test_receiving_v2 import setup, scenario
from test_validation_v2_api import match_readback
from test_operations_v2 import png

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('radar_producer',ROOT/'scripts/produce_observation.py')
producer_module=importlib.util.module_from_spec(spec); spec.loader.exec_module(producer_module)


def connect(s,source):
    p=producer_module.Producer('http://unused',s.flight,source)
    def request(path,data=None,media='application/json'):
        r=(s.client.get(path) if data is None else s.client.post(path,json=data) if isinstance(data,dict)
           else s.client.post(path,content=data,headers={'Content-Type':media}))
        assert r.is_success,r.text
        return r.json()
    p.request=request
    return p


@pytest.mark.parametrize('known',[False,True])
def test_audio_v2_segments_unknown_time_stays_held(scenario,tmp_path,monkeypatch,known):
    from app.services.speech import local
    s=scenario
    class Stub:
        def __init__(self,model): pass
        def transcribe(self,path):
            return dict(transcript='Radar one two three maintain three thousand feet heading two seven zero',model_score=.9)
    monkeypatch.setattr(local,'LocalWhisper',Stub)
    original=producer_module.stamp
    monkeypatch.setattr(producer_module,'stamp',lambda value=None:original(value or s.clock[0]))
    path=tmp_path/'audio.wav'
    with wave.open(str(path),'wb') as out:
        out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(b'\x00\x10'*16000)
    args=SimpleNamespace(wav=path,microphone=False,captured_at=s.time(-2) if known else None,
        model=tmp_path,seconds=10,device=None,callsign='RADAR123',alias_key='radar-one-two-three',
        alias_text='Radar one two three',reviewed_channel=True,complete_utterance=True)
    producer_module.audio(connect(s,'ATC'),args)
    row=s.inputs()[0]
    assert row['payload']['schema_version']=='2'
    assert row['applied'] is known,row
    assert bool(s.state()['targets']['ALT']) is known
    assert not s.state()['voice']['inputs']
    assert row['payload']['evidence_refs'][0]['ref'].startswith('stored:')


@pytest.mark.parametrize('mode,expected',[('camera','NORMAL'),('video','UNVERIFIED')])
def test_vision_v2_and_unknown_video_time(scenario,tmp_path,mode,expected):
    s=scenario
    atc=s.adopt();match_readback(s,atc);s.tick()
    path=tmp_path/'roi.png';path.write_bytes(png())
    observed=dict(frame_id='synthetic-frame',captured_at=s.time(-.2),processed_at=s.time(-.1),
        fields={name:dict(value=value,raw_text=str(value),model_score=.9,reason=None,evidence=str(path))
                for name,value in [('altitude',3000),('heading',270)]})
    events=tmp_path/'events.jsonl'
    events.write_text(json.dumps(dict(event_type='observation',input_mode=mode,
        health=dict(status='available',reason=None),observation=observed))+'\n')
    producer_module.vision(connect(s,'COCKPIT'),SimpleNamespace(events=events,target_revision=s.state()['revision']))
    assert s.state()['result']==expected,s.state()
    assert s.inputs()[0]['payload']['observed_at']==(observed['captured_at'] if mode=='camera' else None)


def test_health_no_numeric_data(scenario):
    s=scenario
    connect(s,'COCKPIT').health('camera_disconnected',observed=s.time(-.1))
    row=s.inputs()[0]
    assert row['kind']=='HEALTH' and 'fields' not in row['payload']
    assert row['payload']['observed_at']==s.time(-.1)


def test_capture_failure_releases_input(scenario,tmp_path,monkeypatch):
    from app.services.speech import local
    monkeypatch.setattr(local,'LocalWhisper',lambda _:object())
    p=connect(scenario,'ATC')
    monkeypatch.setattr(p,'wait_for_playback_stop',lambda:(_ for _ in ()).throw(RuntimeError('not stopped')))
    with pytest.raises(RuntimeError,match='not stopped'):
        producer_module.audio(p,SimpleNamespace(model=tmp_path))
    assert not scenario.state()['voice']['inputs']
    assert not scenario.state()['targets']['ALT']


@pytest.mark.parametrize('transcript,valid',[
    ('Radar one two three maintain three thousand feet heading zero',True),
    ('Radar one two three heading 360',False),
    ('Radar one two three heading 270 after departure',False),
    ('Other one two three heading 270',False),
])
def test_speech_extraction_reuses_v2_grammar(transcript,valid):
    result=producer_module.speech_fields(transcript,'RADAR123','radar-one-two-three','Radar one two three',.9,[])
    assert (result['instruction_check']=='PASS') is valid
    if not valid: assert result['mention_status']=='UNKNOWN'


def test_stale_vision_revision_does_not_bind_to_new_target(scenario,tmp_path):
    s=scenario
    atc=s.adopt();match_readback(s,atc);s.tick()
    observed=dict(frame_id='old-revision-frame',captured_at=s.time(-.2),processed_at=s.time(-.1),
        fields={name:dict(value=value,raw_text=str(value),model_score=.9,reason=None,evidence=None)
                for name,value in [('altitude',3000),('heading',270)]})
    events=tmp_path/'events.jsonl'
    events.write_text(json.dumps(dict(event_type='observation',input_mode='camera',
        health=dict(status='available',reason=None),observation=observed))+'\n')
    producer_module.vision(connect(s,'COCKPIT'),SimpleNamespace(events=events,target_revision=0))
    assert s.state()['result']=='UNVERIFIED'
    assert s.inputs()[0]['reason']=='TARGET_REVISION_OLD'
