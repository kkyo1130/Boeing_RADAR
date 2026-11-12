"""Run the same specialist ASR configuration on the frozen added clips."""
import hashlib,json,time
from pathlib import Path
from faster_whisper import WhisperModel

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
root=Path('.demo/slots');plan=json.loads((root/'supplement-plan.json').read_text())
goldpath=Path('docs/evaluation/atc-slot-gold-2026-11-10.json');gold=json.loads(goldpath.read_text())
assert gold['supplement_plan_sha256']==sha(root/'supplement-plan.json')
assert {r['id'] for r in plan['clips']}=={r['id'] for r in gold['rows'] if r['set']!='tower60'}
for r in plan['clips']:assert sha(root/'audio'/(r['id']+'.wav'))==r['sha256']
prior=json.loads(Path('../atc-unseen-whisper/docs/evaluation/unseen-atc-whisper-2026-11-10.json').read_text());config=prior['experiment']['settings']['decode']
modelpath=Path('../atc-specialist-comparison/.demo/specialist/models/whisper-atc-turbo-ct2')
assert sha(modelpath/'model.bin')==prior['experiment']['weights_sha256']['specialist']
model=WhisperModel(str(modelpath.resolve()),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
out={'plan_sha256':sha(root/'supplement-plan.json'),'gold_before_asr_sha256':sha(goldpath),'weights_sha256':sha(modelpath/'model.bin'),'decode':config,'rows':[]}
for i,row in enumerate(plan['clips'],1):
 start=time.perf_counter();segments,_=model.transcribe(str(root/'audio'/(row['id']+'.wav')),**config);segments=list(segments)
 out['rows'].append({'id':row['id'],'audio_sha256':row['sha256'],'reference':row['text'],'transcript':' '.join(s.text.strip() for s in segments),'seconds':time.perf_counter()-start})
 temp=root/'supplement-asr.tmp';temp.write_text(json.dumps(out,indent=2)+'\n');temp.replace(root/'supplement-asr.json')
 print(i,'/',len(plan['clips']),out['rows'][-1]['transcript'],flush=True)
