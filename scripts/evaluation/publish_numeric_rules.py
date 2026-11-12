"""Verify the fixed replay and publish its evidence without rerunning models."""
import hashlib
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
folder=root/'.demo/numeric'
result=json.loads((folder/'results.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=result['plan']
assert sha(folder/'plan.json')==result['plan_sha256']
assert sha(root/'scripts/evaluation/replay_numeric_rules.py')==plan['script_sha256']
for file,digest in plan['source_hashes'].items():assert sha(root/file)==digest
assert sha(root.parent/'atc-slot-evaluation/docs/evaluation/atc-slot-results-2026-11-10.json')==plan['primary_sha256']
assert sha(root.parent/'atc-slot-evaluation/docs/evaluation/atc-slot-gold-2026-11-10.json')==plan['gold_sha256']
assert sha(root/'docs/evaluation/callsign-context-2026-11-10.json')==plan['context_sha256']
assert sha(root.parent/'bert-hybrid-stt/.demo/bert-hybrid-model/model.safetensors')==plan['bert_sha256']
spec=importlib.util.spec_from_file_location('score',root.parent/'atc-slot-evaluation/scripts/evaluation/evaluate_atc_slots.py')
score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)
keys={(x['batch'],x['id'],x['condition']) for x in result['rows']}
assert len(keys)==224 and keys=={(x['batch'],x['id'],x['condition']) for x in plan['inputs']}
input_hashes={(x['batch'],x['id'],x['condition']):x['text_sha256'] for x in plan['inputs']}
for row in result['rows']:
    assert hashlib.sha256(row['text'].encode()).hexdigest()==input_hashes[(row['batch'],row['id'],row['condition'])]
    assert row['before']['predicted']['CALLSIGN']==row['after']['predicted']['CALLSIGN']
    for stage in ('before','after'):
        for field in ('CALLSIGN','ALT','HDG'):
            gold=row['gold'][field]
            expected=None if gold is None else score.scored([score.call_key(x) for x in gold] if field=='CALLSIGN' else gold,row[stage]['predicted'][field])
            assert expected==row[stage]['scores'][field]
for batch,sets in result['summary'].items():
    for dataset,conditions in sets.items():
        for condition,pair in conditions.items():
            rows=[r for r in result['rows'] if r['batch']==batch and r['set']==dataset and r['condition']==condition]
            for stage,metrics in pair.items():
                for field in ('CALLSIGN','ALT','HDG'):
                    assert score.summarize([r[stage] for r in rows],field)==metrics[field]
assert not result['regressions']
assert result['actual_bert_inferences']==222
assert len(plan['audio_hashes'])==92
result['audit']={'condition_evaluations':224,'actual_bert_inferences':222,'empty_silence_evaluations':2,
                 'unique_real_recordings':91,'synthetic_silence_recordings':1,
                 'unchanged_stt_inputs':True,'unchanged_callsign_predictions':True,'score_recalculation':True,
                 'previous_correct_field_regressions':0,'asr_rerun':False,'independent_test':False}
result['base_commit']='203e5e0'
result['grammar_contract']='Speech FL2/3 digits and whole hundreds; spoken heading360->0 only; wire/OCR range unchanged; hesitation candidates require review.'
path=root/'docs/evaluation/numeric-rules-replay-2026-11-10.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(result['audit'])
