"""Replay frozen real-recording transcripts through changed extraction/number rules only."""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.services.speech.ner import extract_atc
from app.services.structure_rules import normalize, parse_command
spec = importlib.util.spec_from_file_location('slot_score',ROOT.parent/'atc-slot-evaluation/scripts/evaluation/evaluate_atc_slots.py')
score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import torch
    torch.set_num_threads(4)
    folder=ROOT/'.demo/numeric'
    output=folder/'results.json'
    assert not output.exists(), 'Preserve previous replay'
    primary_path=ROOT.parent/'atc-slot-evaluation/docs/evaluation/atc-slot-results-2026-11-10.json'
    gold_path=ROOT.parent/'atc-slot-evaluation/docs/evaluation/atc-slot-gold-2026-11-10.json'
    context_path=ROOT/'docs/evaluation/callsign-context-2026-11-10.json'
    primary=json.loads(primary_path.read_text());gold=json.loads(gold_path.read_text())
    contextual=json.loads(context_path.read_text())
    labels={'primary':{x['id']:x for x in gold['rows']}, 'context':{x['id']:x for x in contextual['plan']['clips']}}
    assert primary['gold_sha256']==sha(gold_path)
    model=ROOT.parent/'bert-hybrid-stt/.demo/bert-hybrid-model'
    assert sha(model/'model.safetensors')==primary['model_manifest']['sha256']['model.safetensors']==contextual['plan']['bert_sha256']
    audio_hashes={}
    for cohort,items in labels.items():
        for id,item in items.items():
            if item.get('cohort')=='synthetic_silence':
                path=ROOT.parent/'atc-callsign-context/.demo/context/silence.wav'
            elif item.get('cohort')=='registered_demo_replay':
                path=ROOT.parent/'atc-microphone-modes/.demo/real-atc'/(id+'.wav')
            else:
                base='atc-unseen-whisper/.demo/unseen/audio' if item['set']=='tower60' else 'atc-slot-evaluation/.demo/slots/audio'
                path=ROOT.parent/base/(id+'.wav')
            digest=sha(path)
            assert digest==item['audio_sha256']
            audio_hashes[id]=digest
    sources=[ROOT/'backend/app/services/structure_rules.py',*sorted((ROOT/'backend/app/services/speech').glob('*.py'))]
    plan=dict(primary_sha256=sha(primary_path),gold_sha256=sha(gold_path),context_sha256=sha(context_path),
              bert_sha256=sha(model/'model.safetensors'),source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources},
              audio_hashes=audio_hashes,script_sha256=sha(Path(__file__)),asr_rerun=False,
              scope='Existing recordings and frozen transcripts. Development/regression replay, not fresh accuracy. Context set overlaps primary.',
              inputs=[{'batch':batch,'id':r['id'],'condition':r['condition'], 'text_sha256':hashlib.sha256(r.get('text',r.get('transcript','')).encode()).hexdigest()} for batch,data in [('primary',primary),('context',contextual)] for r in data['rows']])
    (folder/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    result=dict(plan=plan,plan_sha256=sha(folder/'plan.json'),rows=[],actual_bert_inferences=0)
    for batch,data in [('primary',primary),('context',contextual)]:
        for previous in data['rows']:
            label=labels[batch][previous['id']]
            text=previous.get('text',previous.get('transcript',''))
            if text.strip():
                raw=extract_atc(text,model,backend='bert-hybrid')
                result['actual_bert_inferences']+=1
            else:
                raw={'entities':[],'issues':['NO_SPEECH'],'numeric_normalizations':[],'rule_changes':[]}
            predicted={'CALLSIGN':[],'ALT':[],'HDG':[]};conversions=[]
            for entity in raw['entities']:
                assert text[entity['start']:entity['end']]==entity['text']
                kind=entity['label']
                if kind=='CALLSIGN':predicted[kind].append(score.call_key(entity['text']))
                elif kind in ('ALT','HDG'):
                    values,issues=parse_command(('maintain ' if kind=='ALT' else 'heading ')+normalize(entity['text']))
                    value=values.get(kind) if not issues and set(values)=={kind} else None
                    predicted[kind].append(value if value is not None else 'UNRESOLVED')
                    conversions.append(dict(label=kind,text=entity['text'],value=value,issues=issues))
            scores={k:None if label[k] is None else score.scored([score.call_key(c) for c in label[k]] if k=='CALLSIGN' else label[k],predicted[k]) for k in predicted}
            for k in predicted:
                expected=None if label[k] is None else score.scored([score.call_key(c) for c in label[k]] if k=='CALLSIGN' else label[k],previous['predicted'][k])
                assert previous['scores'][k]==expected
            result['rows'].append(dict(batch=batch,id=previous['id'],set=previous.get('set',previous.get('cohort')),
                condition=previous['condition'],text=text,gold={k:label[k] for k in predicted},
                before={k:previous[k] for k in ('entities','issues','predicted','scores')},
                after=dict(entities=raw['entities'],issues=raw['issues'],predicted=predicted,scores=scores,
                           numeric_conversion=conversions,numeric_normalizations=raw['numeric_normalizations'],rule_changes=raw['rule_changes'])))
    assert len(result['rows'])==224 and result['actual_bert_inferences']==222
    assert sha(folder/'plan.json')==result['plan_sha256']
    for file,digest in plan['source_hashes'].items():assert sha(ROOT/file)==digest
    result['summary']={};result['regressions']=[]
    for batch in ('primary','context'):
        result['summary'][batch]={}
        for dataset in sorted({r['set'] for r in result['rows'] if r['batch']==batch}):
            result['summary'][batch][dataset]={}
            for condition in sorted({r['condition'] for r in result['rows'] if r['batch']==batch and r['set']==dataset}):
                rows=[r for r in result['rows'] if r['batch']==batch and r['set']==dataset and r['condition']==condition]
                pair={}
                for stage in ('before','after'):
                    pair[stage]={field:score.summarize([r[stage] for r in rows],field) for field in ('CALLSIGN','ALT','HDG')}
                    positive_calls=[r for r in rows if r['gold']['CALLSIGN']]
                    pair[stage]['joint_with_callsign']={'count':len(positive_calls),'correct':sum(all(s['exact'] for s in r[stage]['scores'].values() if s is not None) for r in positive_calls)}
                    pair[stage]['rows_with_issues']=sum(bool(r[stage]['issues']) for r in rows)
                result['summary'][batch][dataset][condition]=pair
    for r in result['rows']:
        for field,old in r['before']['scores'].items():
            if old is not None and old['exact'] and not r['after']['scores'][field]['exact']:
                result['regressions'].append({k:r[k] for k in ('batch','set','id','condition')}|{'field':field})
    result['packages']={k:importlib.metadata.version(k) for k in ('torch','transformers')}
    result['data_license']='CC-BY-NC-SA-4.0'
    result['data_attribution']='University of West Bohemia UWB-ATCC; Jzuluaga distribution'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for dataset,conditions in result['summary']['primary'].items():
        for condition,pair in conditions.items():
            print(dataset,condition,{field:[(pair[s][field]['positive_exact'],pair[s][field]['positive_rows']) for s in ('before','after')] for field in ('CALLSIGN','ALT','HDG')})
    print('REGRESSIONS',result['regressions'],flush=True)

if __name__=='__main__':main()
