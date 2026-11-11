"""Audit and publish paired replay scores; no additional inference or tuning."""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
folder=root/'.demo/context'
result=json.loads((folder/'results.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(folder/'plan.json')==result['plan_sha256']
assert sha(root/'scripts/evaluation/evaluate_callsign_context.py')==result['script_sha256']
assert sha(root.parent/'atc-microphone-modes/.demo/config.json')==result['plan']['config_sha256']
assert sha(root.parent/'atc-slot-evaluation/docs/evaluation/atc-slot-gold-2026-11-10.json')==result['plan']['gold_sha256']
assert sha(root.parent/'atc-microphone-modes/.demo/real-atc/manifest.json')==result['plan']['manifest_sha256']
assert sha(root.parent/'atc-specialist-comparison/.demo/specialist/models/whisper-atc-turbo-ct2/model.bin')==result['plan']['model_sha256']
assert sha(root.parent/'bert-hybrid-stt/.demo/bert-hybrid-model/model.safetensors')==result['plan']['bert_sha256']
for file,digest in result['source_hashes'].items():assert sha(root/file)==digest
clips={r['id']:r for r in result['plan']['clips']}
assert len(clips)==24 and len(result['rows'])==48
for clip in clips.values():
    if clip['cohort']=='registered_demo_replay':
        path=root.parent/'atc-microphone-modes/.demo/real-atc'/(clip['id']+'.wav')
    elif clip['cohort']=='synthetic_silence':
        path=folder/'silence.wav'
    else:
        base='atc-unseen-whisper/.demo/unseen/audio' if clip['set']=='tower60' else 'atc-slot-evaluation/.demo/slots/audio'
        path=root.parent/base/(clip['id']+'.wav')
    assert sha(path)==clip['audio_sha256']
assert {(r['id'],r['condition']) for r in result['rows']}=={(i,c) for i in clips for c in ('without_context','with_context')}
spec=importlib.util.spec_from_file_location('score',root.parent/'atc-slot-evaluation/scripts/evaluation/evaluate_atc_slots.py')
score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)
for row in result['rows']:
    gold=clips[row['id']]
    assert row['callsign_context']==(result['plan']['context'] if row['condition']=='with_context' else None)
    for k in ('CALLSIGN','ALT','HDG'):
        expected=[score.call_key(c) for c in gold[k]] if k=='CALLSIGN' else gold[k]
        assert score.scored(expected,row['predicted'][k])==row['scores'][k]
result['summary']={}
for cohort in sorted({r['cohort'] for r in result['rows']}):
    result['summary'][cohort]={}
    for condition in ('without_context','with_context'):
        rows=[r for r in result['rows'] if r['cohort']==cohort and r['condition']==condition]
        result['summary'][cohort][condition]={k:score.summarize(rows,k) for k in ('CALLSIGN','ALT','HDG')}
        result['summary'][cohort][condition].update(count=len(rows),
            complete_callsign_correct=sum(r['scores']['CALLSIGN']['exact'] for r in rows),
            gold_callsign_present=sum(r['gold_callsign_present'] for r in rows if clips[r['id']]['CALLSIGN']),
            registered_call_insertions=sum(bool(r['registered_callsign_mentions']) for r in rows) if cohort!='registered_demo_replay' else None,
            all_fields_correct=sum(all(v['exact'] for v in r['scores'].values()) for r in rows))
api=json.loads((folder/'api-check.json').read_text())
assert len(api)==2
for row in api:
    assert row['audio_sha256'] in {clip['audio_sha256'] for clip in clips.values()}
    assert row['targets']=={'ALT':None,'HDG':None} and row['result']=='UNVERIFIED'
    assert row['response']['stt_context']['registry_sha256']==result['plan']['context']['registry_sha256']
result['api_checks']=api
result['data_attribution']='University of West Bohemia UWB-ATCC; Jzuluaga Hugging Face redistribution'
result['data_license']='CC-BY-NC-SA-4.0'
result['audit']={'real_recordings':23,'synthetic_silence':1,'paired_inferences':48,'actual_api_requests':2,
                 'frozen_plan_and_weight_hashes':True,'recomputed_scores':True,'independent_test':False,
                 'reference_derived_new_hints':False,'existing_demo_aliases_previously_curated_from_known_clips':True}
result['packages']={name:importlib.metadata.version(name) for name in ('faster-whisper','ctranslate2','torch','transformers')}
path=root/'docs/evaluation/callsign-context-2026-11-10.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({cohort:{condition:{k:v for k,v in metrics.items() if k not in ('CALLSIGN','ALT','HDG')} for condition,metrics in conditions.items()} for cohort,conditions in result['summary'].items()},indent=2))
