"""Actual BERT+rules on frozen reference/ASR text; no registry or gold in inference."""
import argparse,collections,hashlib,importlib.metadata,json,re,subprocess,sys,time
from pathlib import Path

DIGITS=dict(zip('zero oh one two three four five six seven eight nine niner'.split(),'001234567899'))
NATO=dict(zip('alfa bravo charlie delta echo foxtrot golf hotel india juliett kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu'.split(),'abcdefghijklmnopqrstuvwxyz'))
NATO.update(alpha='a',juliet='j',whisky='w')

def call_key(text):
    # Evaluation only: formatting/digit/NATO equivalence, no airline aliases or homophone guessing.
    return ''.join(DIGITS.get(w,NATO.get(w,w)) for w in re.findall(r'[a-z]+|[0-9]+',text.casefold()))

def scored(expected,predicted):
    gold=collections.Counter(expected);pred=collections.Counter(predicted)
    tp=sum((gold&pred).values())
    return {'tp':tp,'fp':sum(pred.values())-tp,'fn':sum(gold.values())-tp,'exact':gold==pred,'support':sum(gold.values())}

def summarize(rows,field):
    checks=[r['scores'][field] for r in rows if r['scores'][field] is not None]
    tp=sum(x['tp'] for x in checks);fp=sum(x['fp'] for x in checks);fn=sum(x['fn'] for x in checks)
    positive=[x for x in checks if x['support']>0];negative=[x for x in checks if x['support']==0]
    return {'tp':tp,'fp':fp,'fn':fn,'support':tp+fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        'positive_rows':len(positive),'positive_exact':sum(x['exact'] for x in positive),'absent_rows':len(negative),'false_positive_rows':sum(x['fp']>0 for x in negative)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gold',type=Path,required=True);p.add_argument('--prior',type=Path,required=True)
    p.add_argument('--supplement',type=Path);p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();gold=json.loads(args.gold.read_text());prior=json.loads(args.prior.read_text())
    asr={r['id']:r['transcript'] for r in prior['experiment']['rows'] if r['model']=='specialist'}
    if args.supplement:
        supplement=json.loads(args.supplement.read_text())
        assert supplement['gold_before_asr_sha256']==hashlib.sha256(args.gold.read_bytes()).hexdigest()
        assert supplement['plan_sha256']==gold['supplement_plan_sha256']
        expected={r['id']:r for r in gold['rows'] if r['set']!='tower60'}
        assert len(supplement['rows'])==len(expected) and {r['id'] for r in supplement['rows']}==set(expected)
        for r in supplement['rows']:assert r['reference']==expected[r['id']]['reference'] and r['audio_sha256']==expected[r['id']]['audio_sha256']
        asr.update({r['id']:r['transcript'] for r in supplement['rows']})
    assert all(r['id'] in asr for r in gold['rows'])
    sys.path.insert(0,str(Path('backend').resolve()))
    import torch;torch.set_num_threads(4)
    from app.services.speech.ner import extract_atc,ExtractionError
    from app.services.structure_rules import parse_command,normalize
    result={'evaluator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'supplement_sha256':hashlib.sha256(args.supplement.read_bytes()).hexdigest() if args.supplement else None,'backend_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'backend_files_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('backend/app/services/structure_rules.py'),*Path('backend/app/services/speech').glob('*.py')]},'packages':{k:importlib.metadata.version(k) for k in ('torch','transformers')},'gold_sha256':hashlib.sha256(args.gold.read_bytes()).hexdigest(),'prior_sha256':hashlib.sha256(args.prior.read_bytes()).hexdigest(),'model_manifest':json.loads((args.model/'radar_hybrid.json').read_text()),'rows':[]}
    for row in gold['rows']:
        for condition,text in [('reference',row['reference']),('asr',asr[row['id']])]:
            start=time.perf_counter()
            try:raw=extract_atc(text,args.model,backend='bert-hybrid')
            except ExtractionError as ex:raw={'entities':[],'issues':[str(ex)]}
            predicted={'CALLSIGN':[],'ALT':[],'HDG':[]};numeric=[]
            for e in raw['entities']:
                kind=e['label']
                if kind=='CALLSIGN':predicted[kind].append(call_key(e['text']))
                elif kind in ('ALT','HDG'):
                    values,issues=parse_command(('maintain ' if kind=='ALT' else 'heading ')+normalize(e['text']))
                    value=values.get(kind) if not issues and set(values)=={kind} else None
                    predicted[kind].append(value if value is not None else 'UNRESOLVED')
                    numeric.append({'label':kind,'text':e['text'],'value':value,'issues':issues})
            scores={k:None if row[k] is None else scored([call_key(c) for c in row[k]] if k=='CALLSIGN' else row[k],predicted[k]) for k in predicted}
            result['rows'].append({'id':row['id'],'set':row['set'],'condition':condition,'text':text,'entities':raw['entities'],'issues':raw['issues'],'numeric_conversion':numeric,'predicted':predicted,'scores':scores,'seconds':time.perf_counter()-start})
    result['summary']={}
    for dataset in sorted({r['set'] for r in gold['rows']}):
        result['summary'][dataset]={}
        for condition in ('reference','asr'):
            rows=[r for r in result['rows'] if r['set']==dataset and r['condition']==condition]
            result['summary'][dataset][condition]={k:summarize(rows,k) for k in ('CALLSIGN','ALT','HDG')}
            result['summary'][dataset][condition]['rows_with_review_issues']=sum(bool(r['issues']) for r in rows)
            result['summary'][dataset][condition]['all_scored_fields_exact']=sum(all(s['exact'] for s in r['scores'].values() if s is not None) for r in rows if all(s is not None for s in r['scores'].values()))
    result['numeric_failure_breakdown']={}
    for dataset in sorted({r['set'] for r in gold['rows']}):
        result['numeric_failure_breakdown'][dataset]={}
        for condition in ('reference','asr'):
            result['numeric_failure_breakdown'][dataset][condition]={}
            for field in ('ALT','HDG'):
                tally=collections.Counter()
                for row in result['rows']:
                    if row['set']!=dataset or row['condition']!=condition:continue
                    score=row['scores'][field]
                    if score is None or not score['support'] or score['exact']:continue
                    values=row['predicted'][field]
                    reason='missing' if not values else 'number_unresolved' if 'UNRESOLVED' in values else 'wrong_or_extra_value'
                    tally[reason]+=1
                result['numeric_failure_breakdown'][dataset][condition][field]=dict(tally)
    result['callsign_error_breakdown']={}
    for dataset in sorted({r['set'] for r in gold['rows']}):
        labels={r['id']:r for r in gold['rows'] if r['set']==dataset}
        counts={'correct':0,'expected_expression_absent_in_asr':0,'expression_present_but_extraction_wrong':0}
        for row in result['rows']:
            label=labels.get(row['id'])
            if row['condition']!='asr' or not label or not label['CALLSIGN']:continue
            if row['scores']['CALLSIGN']['exact']:counts['correct']+=1;continue
            tokens=row['text'].split();expected=[call_key(c) for c in label['CALLSIGN']]
            observed={call_key(' '.join(tokens[i:j])) for i in range(len(tokens)) for j in range(i+1,len(tokens)+1)}
            if all(c in observed for c in expected):counts['expression_present_but_extraction_wrong']+=1
            else:counts['expected_expression_absent_in_asr']+=1
        result['callsign_error_breakdown'][dataset]=counts
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['summary'],indent=2))

if __name__=='__main__':main()
