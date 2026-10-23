"""Download the public local ASR model and generate explicitly registered ATC audio."""
import json
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.services.demo.adapters import SCENARIOS
from huggingface_hub import snapshot_download
snapshot_download('Systran/faster-whisper-base.en',local_dir=root/'.demo/model',allow_patterns=['*.json','*.bin','*.txt'])
folder=root/'.demo/audio';folder.mkdir(parents=True,exist_ok=True)
for name,text in SCENARIOS.items():
    subprocess.run(['say','-v','Samantha','-r','145','-o',str(folder/(name+'.aiff')),text],check=True)
    subprocess.run(['afconvert','-f','WAVE','-d','LEI16@16000',str(folder/(name+'.aiff')),str(folder/(name+'.wav'))],check=True)
config={'callsigns':{'RADAR123':{'radar-one-two-three':'Radar one two three','radar-digits':'Radar 123','radar-hyphen':'Radar 1-2-3'}},
        'freshness':{'max_age_seconds':120.0,'max_future_skew_seconds':0.1,'minimum_model_score':None},
        'structure_rules':{'policy_ref':'local-demo-experimental/1','max_altitude_ft':50000,'max_altitude_change_ft':10000,'max_heading_change_deg':180}}
(root/'.demo/config.json').write_text(json.dumps(config,indent=2))
print('Local model and registered scenario audio ready.')
