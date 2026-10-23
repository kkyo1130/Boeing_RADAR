import base64,io,json,math,struct,wave
from datetime import timedelta
import pytest
from PIL import Image
from app.services import receiving_v2 as intake
from app.services.demo import adapters as demo

def wav_bytes():
    b=io.BytesIO()
    with wave.open(b,'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(i/10))) for i in range(16000)))
    return b.getvalue()
@pytest.fixture
def flight(client,tmp_path,monkeypatch):
    cfg={'callsigns':{'RADAR123':{'radar-one-two-three':'Radar one two three'}},'freshness':{'max_age_seconds':120.0,'max_future_skew_seconds':.1,'minimum_model_score':None},'structure_rules':{'policy_ref':'test','max_altitude_ft':50000,'max_altitude_change_ft':10000,'max_heading_change_deg':180}}
    p=tmp_path/'config.json';p.write_text(json.dumps(cfg));monkeypatch.setenv('RADAR_V2_CONFIG',str(p));monkeypatch.setenv('RADAR_DEMO_ENABLED','1');monkeypatch.setenv('RADAR_DEMO_AUDIO',str(tmp_path));monkeypatch.setenv('RADAR_OCR_BINARY','test')
    (tmp_path/'baseline.wav').write_bytes(wav_bytes());demo.CAMERAS.clear()
    r=client.post('/api/v2/flights',json={'callsign':'RADAR123'});assert r.status_code==201,r.text
    return r.json()['flight_id']
def test_registered_and_unknown_speech(client,flight,monkeypatch):
    now=intake.utc_now()
    r=client.post(f'/api/demo/{flight}/scenario/baseline',json={'started_at':intake.stamp(now-timedelta(seconds=4)),'ended_at':intake.stamp(now-timedelta(seconds=3))});assert r.status_code==200,r.text
    state=client.get(f'/api/v2/flights/{flight}/state').json();assert state['targets']['ALT']['value']==3000
    class Model:
        def transcribe(self,path):return {'transcript':'unintelligible','model_score':.9}
    monkeypatch.setattr(demo,'MODEL',Model())
    r=client.post(f'/api/demo/{flight}/readback',json={'started_at':intake.stamp(now-timedelta(seconds=2)),'ended_at':intake.stamp(now-timedelta(seconds=1)),'atc_input_id':state['readback_required']['atc_input_id'],'audio':base64.b64encode(wav_bytes()).decode()});assert r.status_code==200,r.text
    assert client.get(f'/api/v2/flights/{flight}/state').json()['result']!='NORMAL'
def test_parser_rejects_unknown_suffix_and_missing_callsign():
    registry={'RADAR123':{'r':'Radar one two three'}};seg={'started_at':'2026-10-23T01:00:00Z','role':'ATC','segment_id':'s','attempt_id':'t','atc_input_id':'a'}
    for text in ['maintain three thousand feet heading two seven zero','Radar one two three maintain three thousand feet heading two seven zero if able']:
        p=demo.speech_payload('f',0,seg,text,.9,registry,{'evidence_id':'e','ref':'stored:e'});assert p['instruction_check']=='NEEDS_REVIEW';assert p['fields']=={}
def test_camera_stabilizes_clears_and_preserves_zero(client,flight,monkeypatch):
    import radar_vision.poc
    import app.services.demo.tracking as tracking
    monkeypatch.setattr(tracking,'locate',lambda *args:(0,0))
    image=Image.new('RGB',(100,100),'gray');b=io.BytesIO();image.save(b,format='JPEG');encoded=base64.b64encode(b.getvalue()).decode()
    c=client.post(f'/api/demo/{flight}/calibration',json={'image':encoded,'rois':{'ALT':[10,10,40,30],'HDG':[50,10,80,30]}});assert c.status_code==200,c.text
    value=[3500,0]
    def recognize(*args,**kwargs):return {'fields':{name:{'value':value[i],'reason':None if value[i] is not None else 'blank_roi','model_score':.9,'raw_text':str(value[i])} for i,name in enumerate(['altitude','heading'])}}
    monkeypatch.setattr(radar_vision.poc,'recognize',recognize)
    for i in range(3):
        body={'token':c.json()['token'],'image':encoded,'captured_at':intake.stamp(intake.utc_now()),'target_revision':0};r=client.post(f'/api/demo/{flight}/frame',json=body);assert r.status_code==200,r.text;assert r.json()['fields']['heading']['value']==(0 if i==2 else None)
    assert client.post(f'/api/demo/{flight}/frame',json=body).status_code==409
    value[0]=None;r=client.post(f'/api/demo/{flight}/frame',json={**body,'captured_at':intake.stamp(intake.utc_now())});assert r.status_code==200,r.text;assert r.json()['fields']['altitude']['value'] is None;assert r.json()['fields']['heading']['value']==0
    r=client.post(f'/api/demo/{flight}/frame',json={**body,'captured_at':intake.stamp(intake.utc_now()+timedelta(seconds=20))});assert r.status_code==422

def test_disabled(client,monkeypatch):
    monkeypatch.delenv('RADAR_DEMO_ENABLED',raising=False);assert client.get('/api/demo/status').status_code==404

def test_tracking_translation_ignores_changed_digits():
    import numpy as np
    from app.services.demo.tracking import reference,locate
    rng=np.random.default_rng(9);pixels=rng.integers(0,255,(300,500,3),dtype=np.uint8)
    rois={'ALT':[230,100,300,130],'HDG':[140,100,190,130]}
    image=Image.fromarray(pixels);ref=reference(image,rois)
    shifted=np.roll(pixels,-12,axis=0)
    shifted[88:118,230:300]=0;shifted[88:118,140:190]=255
    assert locate(Image.fromarray(shifted),ref)==(0,-12)
    assert locate(Image.new('RGB',(500,300),'black'),ref) is None

def test_camera_watchdog_clears_channel(client,flight):
    demo.CAMERAS['expired']={'flight':flight,'expired':False,'emitted':demo.time.monotonic()-8}
    state=client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['channels']['CAMERA']['status']=='DISCONNECTED'
    assert state['result']!='NORMAL'

def test_real_asr_numeric_format_preserves_transcript():
    registry={'RADAR123':{'hyphen':'Radar 1-2-3'}}
    seg={'started_at':'2026-10-23T01:00:00Z','role':'ATC','segment_id':'s','attempt_id':'t','atc_input_id':'a'}
    text='Radar 1-2-3 climb and maintain 3,000 feet heading 270.'
    p=demo.speech_payload('f',0,seg,text,.66,registry,{'evidence_id':'e','ref':'stored:e'})
    assert p['transcript']==text
    assert p['fields']['ALT']['value']==3000
    assert p['fields']['HDG']['value']==270
    assert p['instruction_check']=='PASS'

@pytest.mark.parametrize('heading,expected', [('to seven zero',270),('to ate zero',280)])
def test_homophone_readback_preserves_raw_and_compares_actual(client,flight,monkeypatch,heading,expected):
    now=intake.utc_now()
    r=client.post(f'/api/demo/{flight}/scenario/baseline',json={'started_at':intake.stamp(now-timedelta(seconds=4)),'ended_at':intake.stamp(now-timedelta(seconds=3))})
    assert r.status_code==200,r.text
    state=client.get(f'/api/v2/flights/{flight}/state').json()
    text=f'Radar one, two, three, climb and maintain 3,000 feet, heading {heading}.'
    class Model:
        def transcribe(self,path): return {'transcript':text,'model_score':.9}
    monkeypatch.setattr(demo,'MODEL',Model())
    r=client.post(f'/api/demo/{flight}/readback',json={'started_at':intake.stamp(now-timedelta(seconds=2)),'ended_at':intake.stamp(now-timedelta(seconds=1)),'atc_input_id':state['readback_required']['atc_input_id'],'audio':base64.b64encode(wav_bytes()).decode()})
    assert r.status_code==200,r.text
    assert r.json()['transcript']==text
    state=client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['structure_checks']['READBACK']['result']=='PASS'
    row=next(row for row in state['validation']['readback']['fields'] if row['field']=='HDG')
    assert row['actual']==expected
    assert row['result']==('NORMAL' if expected==270 else 'MISMATCH')
