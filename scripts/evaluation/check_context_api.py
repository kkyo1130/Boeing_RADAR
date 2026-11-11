"""Isolated ASGI request with real local Whisper and BERT (no injected recognizer)."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
folder = root/'.demo/context'
os.environ.update(RADAR_DEMO_ENABLED='1', RADAR_STT_CALLSIGN_CONTEXT='1',
    RADAR_V2_CONFIG=str(root.parent/'atc-microphone-modes/.demo/config.json'),
    RADAR_DATABASE_URL='sqlite:///'+str(folder/'api-check.db'),
    RADAR_WHISPER_MODEL=str(root.parent/'atc-specialist-comparison/.demo/specialist/models/whisper-atc-turbo-ct2'),
    RADAR_NER_BACKEND='bert-hybrid', RADAR_NER_MODEL=str(root.parent/'bert-hybrid-stt/.demo/bert-hybrid-model'))
assert not (folder/'api-check.json').exists(), 'Keep earlier verification evidence'
sys.path.insert(0,str(root/'backend'))
import torch
torch.set_num_threads(4)
from fastapi.testclient import TestClient
from app.main import app

results=[]
with TestClient(app) as client:
    assert client.get('/api/demo/status').json()['callsign_context_enabled']
    manifest=json.loads((root.parent/'atc-microphone-modes/.demo/real-atc/manifest.json').read_text())
    path=root.parent/'atc-microphone-modes/.demo/real-atc'/manifest[1]['file']
    for label,wav in [('actual_lufthansa_file',path),('synthetic_silence',folder/'silence.wav')]:
        created=client.post('/api/v2/flights',json={'callsign':'DLH1KK'})
        assert created.status_code==201,created.text
        flight=created.json()['flight_id']
        now=datetime.now(timezone.utc)
        response=client.post(f'/api/demo/{flight}/atc',json={
            'audio':base64.b64encode(wav.read_bytes()).decode(), 'input_mode':'file_upload',
            'started_at':(now-timedelta(seconds=4)).isoformat().replace('+00:00', 'Z'),
            'ended_at':(now-timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')})
        assert response.status_code==200,response.text
        body=response.json()
        assert body['stt_context']['enabled'] and body['stt_context']['source']=='flight_callsign_registry'
        assert body['quality_reason']!='speech_engine_unavailable'
        assert body['ner'] is not None
        if label == 'actual_lufthansa_file':
            assert 'NER_UNAVAILABLE' not in body['ner']['issues']
        state=client.get(f'/api/v2/flights/{flight}/state').json()
        assert state['targets']=={'ALT':None,'HDG':None}
        assert state['result']=='UNVERIFIED'
        results.append(dict(case=label,audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),response=body,
                            targets=state['targets'],result=state['result']))
        print(label,body['transcript'],body['quality_reason'],flush=True)
(folder/'api-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
