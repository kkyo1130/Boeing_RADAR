#!/usr/bin/env python3
"""Validate complete fixed-input coverage, then publish measured specialist results."""
import argparse,importlib.metadata,json,statistics,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,required=True);p.add_argument('--scorer-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.scorer_root/'scripts/evaluation'))
    from compare_atc_stt import sha,word_errors
    plan=json.loads((a.runs/'plan.json').read_text());expected={(r['id'],r['condition']):r['sha256'] for r in plan['clips']}
    report={'purpose':'Previously inspected three ATC utterances with two recording conditions; not held-out accuracy',
        'hardware':'Apple M4, 16GiB, CPU4 threads. Float32 greedy CTC vs int8 beam5 CTranslate2 Whisper; latency is implementation-specific, single pass per file.',
        'data_source':'https://huggingface.co/datasets/Jzuluaga/uwb_atcc','data_license':'CC-BY-NC-SA-4.0','attribution':'University of West Bohemia UWB-ATCC; Jzuluaga Hugging Face distribution',
        'packages':{p:importlib.metadata.version(p) for p in ['torch','transformers','faster-whisper','ctranslate2','scipy']},
        'plan':plan,'leakage_audit':json.loads((a.runs/'leakage-audit.json').read_text()),
        'model_sources':{name:json.loads((a.runs/(name+'-source.json')).read_text()) for name in plan['models']},
        'notes':['CTC score is None: do not treat inability to pass current Whisper-oriented quality gate as CTC transcription accuracy.',
                 'Text extraction match is a separate diagnostic of actual ASR output using unchanged BERT/rules/registry; no quality threshold and no adoption.',
                 'UWB-trained results are contaminated by training-corpus overlap risk and excluded from independent-generalization claims.',
                 'No training, no current production model switch, no new microphone recording, no ATCO2 evaluation samples loaded.'],
        'runs':[]}
    files=['ctc-atcosim-results.json','ctc-uwb-atcosim-results.json','whisper-atc-turbo-results.json','whisper-atc-turbo-no-prompt-results.json']
    for file in files:
        r=json.loads((a.runs/file).read_text())
        assert r['plan_sha256']==sha(a.runs/'plan.json')
        assert len(r['rows'])==6 and {(v['id'],v['condition']):v['audio_sha256'] for v in r['rows']}==expected
        for row in r['rows']:
            assert row['wer']==word_errors(row['reference'],row['transcript'],True)
            assert row['lexical_wer']==word_errors(row['reference'],row['transcript'])
            if r['engine']=='ctc':assert row['model_score'] is None and not row['adopted']
        r['summary']=[]
        for condition in ['original','recorded_microphone']:
            rows=[x for x in r['rows'] if x['condition']==condition]
            item={'condition':condition,'count':len(rows),'word_errors':sum(x['wer']['errors'] for x in rows),'reference_words':sum(x['wer']['reference_words'] for x in rows),
                'text_extraction_correct':sum(x['text_extraction_correct'] for x in rows),
                'correct_adoptions':sum(x['correct_adoption'] for x in rows),'incorrect_adoptions':sum(x['adopted'] and not x['correct_adoption'] for x in rows),
                'stt_median_seconds':statistics.median(x['stt_seconds'] for x in rows)}
            item['wer']=item['word_errors']/item['reference_words'];r['summary'].append(item)
            print(r['model'],r['prompt'],condition,f"WER {100*item['wer']:.1f}%",'text',item['text_extraction_correct'],'adopt',item['correct_adoptions'],f"{item['stt_median_seconds']:.2f}s")
        report['runs'].append(r)
    prior=json.loads((a.scorer_root/'docs/evaluation/atc-stt-comparison-2026-11-10.json').read_text())
    report['previous_generic_whisper']=[{'model':r['model'],'prompt':r['prompt_mode'],'summary':r['summary']} for r in prior['runs'] if r['prompt_mode']=='generic_atc']
    report['conversion']=json.loads((a.runs/'conversion.json').read_text())
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
