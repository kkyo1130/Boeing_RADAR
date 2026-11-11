#!/usr/bin/env python3
"""Audit fixed clip coverage and generate a compact, shareable experiment record."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from compare_atc_stt import word_errors

MODELS=['base.en','small.en','medium.en','large-v3-turbo']

def summarize(directory):
    plans={mode:json.loads((directory/name).read_text()) for mode,name in [('generic_atc','plan.json'),('none','no-prompt-plan.json')]}
    result={'hardware':{'cpu':'Apple M4','memory_bytes':17179869184,'logical_cores':10},
            'scope':'3 previously inspected utterances, each original and previously recorded microphone WAV. Not independent held-out evaluation.',
            'source':{'dataset':'https://huggingface.co/datasets/Jzuluaga/uwb_atcc','revision':plans['generic_atc']['source_revision'],'license':'CC-BY-NC-SA-4.0','attribution':'University of West Bohemia UWB-ATCC; Hugging Face Jzuluaga redistribution'},
            'metric':'Pooled token edit distance / reference token count; lowercase/punctuation normalization. digit_expanded_wer additionally expands 080 to zero eight zero only.',
            'notes':['Original corpus references unchanged, including Lufthansa k vs spoken kilo ambiguity.',
                     'No target/callsign hints in ASR; same registry, BERT, rules and quality thresholds.',
                     'Initial generic prompt condition was primary. No-prompt follow-up was triggered by observed number-list output; not an independent confirmatory experiment.',
                     'Latency is a single pass per clip on CPU int8/4 threads, excludes loading; first inference may include startup overhead. No Apple GPU benchmark.',
                     'Models are Whisper checkpoints, not four unrelated ASR architectures.'],
            'plans':plans,'reference_text_control':json.loads((directory/'reference-control.json').read_text()),'model_sources':{},'runs':[]}
    for model in MODELS:
        source=directory/f'{model}-source.json'
        result['model_sources'][model]=json.loads(source.read_text()) if source.exists() else {'name':model,'source':'Existing local base.en artifact; weights hash recorded below'}
    for mode,suffix in [('generic_atc',''),('none','-no-prompt')]:
        plan=plans[mode]
        plan_name='plan.json' if mode=='generic_atc' else 'no-prompt-plan.json'
        plan_hash=hashlib.sha256((directory/plan_name).read_bytes()).hexdigest()
        expected={(c['id'],c['condition']):c['sha256'] for c in plan['clips']}
        for model in MODELS:
            run=json.loads((directory/f'{model}{suffix}-results.json').read_text())
            assert run['plan_sha256']==plan_hash
            for row in run['rows']:
                assert row['lexical_wer']==word_errors(row['reference'],row['transcript'])
                assert row['digit_expanded_wer']==word_errors(row['reference'],row['transcript'],True)
            actual={(r['id'],r['condition']):r['audio_sha256'] for r in run['rows']}
            assert actual==expected and len(run['rows'])==len(expected)==6, model
            summary=[]
            for condition in ['original','recorded_microphone']:
                rows=[r for r in run['rows'] if r['condition']==condition]
                item={'condition':condition,'count':len(rows),
                      'correct_adoptions':sum(r['correct_adoption'] for r in rows),
                      'incorrect_adoptions':sum(r['adopted'] and not r['correct_adoption'] for r in rows),
                      'stt_median_seconds':statistics.median(r['stt_seconds'] for r in rows),
                      'stt_total_seconds':sum(r['stt_seconds'] for r in rows),
                      'audio_total_seconds':sum(r['duration_seconds'] for r in rows)}
                for key in ['lexical_wer','digit_expanded_wer']:
                    errors=sum(r[key]['errors'] for r in rows);count=sum(r[key]['reference_words'] for r in rows)
                    item[key]={'errors':errors,'reference_words':count,'wer':errors/count}
                summary.append(item)
            compact={k:run[k] for k in ['model','radar_commit','plan_sha256','weights_sha256','load_seconds','settings','packages','scoring_version']}
            compact.update(prompt_mode=mode,summary=summary,rows=[{k:r[k] for k in ['id','condition','audio_sha256','duration_seconds','transcript','lexical_wer','digit_expanded_wer','stt_seconds','pipeline_seconds','stt_model_score','quality_reason','adopted','correct_adoption','validation_reason']} for r in run['rows']])
            result['runs'].append(compact)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    report=summarize(a.directory);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    for run in report['runs']:
        for r in run['summary']:
            print(run['model'],run['prompt_mode'],r['condition'],f"WER {100*r['digit_expanded_wer']['wer']:.1f}%",f"{r['stt_median_seconds']:.2f}s",f"adopt {r['correct_adoptions']}/{r['count']}")
