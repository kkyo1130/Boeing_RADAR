"""Post-hoc diagnosis only: rerun both models on paired outliers with production temperature fallback.

Do not replace the primary fixed-temperature results or interpret this selected
subset as an independent benchmark. Selection is either model's WER > 100%.
"""
import argparse
import json
from pathlib import Path
import time

from compare_unseen_whisper import metrics, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','results','generic','specialist','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();plan=json.loads(a.plan.read_text());prior=json.loads(a.results.read_text())
    assert prior['plan_sha256']==sha(a.plan) and len(prior['rows'])==120
    selected={x['id'] for x in prior['rows'] if x['metrics']['errors']>x['metrics']['reference_words']}
    settings=dict(plan['decode']);settings['temperature']=[0.0,0.2,0.4,0.6,0.8,1.0]
    output={'kind':'post-hoc selected-outlier diagnosis, not primary benchmark','selection':'Either model WER>100% in primary fixed-temperature run; both models rerun on the same selected clips',
        'primary_sha256':sha(a.results),'plan_sha256':sha(a.plan),'settings':settings,'ct2_seed_per_call':20261110,'rows':[]}
    import ctranslate2
    from faster_whisper import WhisperModel
    for name,path in [('generic',a.generic),('specialist',a.specialist)]:
        assert sha(path/'model.bin')==prior['weights_sha256'][name]
        model=WhisperModel(str(path.resolve()),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
        for clip in plan['clips']:
            if clip['id'] not in selected:continue
            assert sha(a.plan.parent/clip['file'])==clip['sha256']
            ctranslate2.set_random_seed(20261110);start=time.perf_counter()
            segments,info=model.transcribe(str(a.plan.parent/clip['file']),**settings);segments=list(segments)
            text=' '.join(s.text.strip() for s in segments)
            row={'id':clip['id'],'model':name,'reference':clip['reference'],'transcript':text,
                'metrics':metrics(clip['reference'],text),'seconds':time.perf_counter()-start,
                'temperature_per_segment':[s.temperature for s in segments]}
            output['rows'].append(row);a.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
            print(name,clip['id'],row['metrics']['errors'],flush=True)
        del model
    print('DIAGNOSTIC COMPLETE',len(output['rows']),flush=True)

if __name__=='__main__':main()
