"""Verify the frozen gold, inputs, exclusions, and all paired scores before publication."""
import hashlib,json,re
from pathlib import Path
from evaluate_atc_slots import call_key,scored,summarize

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
root=Path('.demo/slots');goldpath=Path('docs/evaluation/atc-slot-gold-2026-11-10.json');gold=json.loads(goldpath.read_text())
r=json.loads((root/'results.json').read_text());plan=json.loads((root/'supplement-plan.json').read_text());asr=json.loads((root/'supplement-asr.json').read_text())
priorpath=Path('../atc-unseen-whisper/docs/evaluation/unseen-atc-whisper-2026-11-10.json');prior=json.loads(priorpath.read_text())
assert r['gold_sha256']==sha(goldpath)==asr['gold_before_asr_sha256']
assert r['evaluator_sha256']==sha(Path('scripts/evaluation/evaluate_atc_slots.py'))
assert r['supplement_sha256']==sha(root/'supplement-asr.json')
assert gold['source_report_sha256']==r['prior_sha256']==sha(priorpath)
assert gold['supplement_plan_sha256']==asr['plan_sha256']==sha(root/'supplement-plan.json')
labels={x['id']:x for x in gold['rows']};assert len(labels)==88
assert len(r['rows'])==176 and {(x['id'],x['condition']) for x in r['rows']}=={(i,c) for i in labels for c in ('reference','asr')}
texts={x['id']:x['transcript'] for x in prior['experiment']['rows'] if x['model']=='specialist'};texts.update({x['id']:x['transcript'] for x in asr['rows']})
for row in r['rows']:
 g=labels[row['id']];assert row['text']==(g['reference'] if row['condition']=='reference' else texts[row['id']])
 for k in ('CALLSIGN','ALT','HDG'):
  expected=None if g[k] is None else scored([call_key(x) for x in g[k]] if k=='CALLSIGN' else g[k],row['predicted'][k])
  assert row['scores'][k]==expected
for dataset,conditions in r['summary'].items():
 for condition,metrics in conditions.items():
  rows=[x for x in r['rows'] if x['set']==dataset and x['condition']==condition]
  for k in ('CALLSIGN','ALT','HDG'):assert summarize(rows,k)==metrics[k]
for file,digest in r['backend_files_sha256'].items():assert sha(Path(file))==digest
used=set();pattern=re.compile(r'uwb-atcc_[A-Za-z0-9-]+_[0-9]+_[0-9]+_[A-Z]+')
for item in prior['plan']['prior_files']:
 p=Path('../..')/item['path'];assert sha(p)==item['sha256'];used.update(pattern.findall(p.read_text()))
used.update(x['id'] for x in prior['plan']['clips']);prior_groups={x.split('_')[1] for x in used}
trainpath=Path('../real-model-comparison-20261109/data.json');assert sha(trainpath)==plan['bert_train_validation_manifest_sha256']
train=json.loads(trainpath.read_text())['splits'];tg={x['id'].split('_')[1] for s in ('train','validation') for x in train[s]}
assert sha(Path('../real-model-comparison-20261109/bert-seed13/model/model.safetensors'))==r['model_manifest']['sha256']['model.safetensors']
for x in plan['clips']:
 assert x['id'] not in used and x['group'] not in tg
 if x['stratum']=='ALT':assert x['group'] not in prior_groups
 assert sha(root/'audio'/(x['id']+'.wav'))==x['sha256']==labels[x['id']]['audio_sha256']
for file,digest in plan['parquet_sha256'].items():assert sha(root/'source/data'/file)==digest
r['supplement_plan']=plan;r['new_asr']=asr;r['annotation_basis']=gold['annotation_basis']
r['data_license']='CC-BY-NC-SA-4.0';r['data_attribution']='University of West Bohemia UWB-ATCC; Jzuluaga Hugging Face distribution'
r['audit']={'paired_extractions':176,'new_asr_runs':28,'prior_record_files_verified':len(prior['plan']['prior_files']),'new_exact_clip_overlap':0,'supplement_bert_train_validation_group_overlap':0,'altitude_prior_group_overlap':0,'heading_prior_evaluation_group_overlap':len(plan['previous_eval_group_overlap_ids']),'gold_frozen_before_new_asr':True,'raw_candidate_metrics_not_instruction_acceptance':True}
r['joint_with_explicit_callsign']={}
for dataset in r['summary']:
 r['joint_with_explicit_callsign'][dataset]={}
 for cond in ('reference','asr'):
  rows=[x for x in r['rows'] if x['set']==dataset and x['condition']==cond and labels[x['id']]['CALLSIGN']]
  r['joint_with_explicit_callsign'][dataset][cond]={'count':len(rows),'correct':sum(all(s['exact'] for s in x['scores'].values() if s is not None) for x in rows)}
Path('docs/evaluation/atc-slot-results-2026-11-10.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print('AUDIT',r['audit']);print('CALL',r['callsign_error_breakdown']);print('NUMERIC',r['numeric_failure_breakdown']);print('JOINT',r['joint_with_explicit_callsign'])
