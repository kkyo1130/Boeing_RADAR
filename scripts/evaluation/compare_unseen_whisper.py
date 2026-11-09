"""Paired local ASR comparison on a frozen manifest; no training or server mutation."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import statistics
import time


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def words(text, digits=True):
    raw=re.findall(r'[^\W\d_]+|\d+',text.casefold())
    names='zero one two three four five six seven eight nine'.split()
    return [v for w in raw for v in ([names[int(c)] for c in w] if digits and w.isdigit() else [w])]


def distance(ref,hyp):
    prev=list(range(len(hyp)+1))
    for i,w in enumerate(ref,1):
        cur=[i]
        for j,v in enumerate(hyp,1):cur.append(min(prev[j]+1,cur[-1]+1,prev[j-1]+(w!=v)))
        prev=cur
    return prev[-1]


def metrics(ref,hyp):
    r,h=words(ref),words(hyp)
    numeric=set('zero one two three four five six seven eight nine oh niner hundred thousand'.split())
    rn,hn=[w for w in r if w in numeric],[w for w in h if w in numeric]
    return {'errors':distance(r,h),'reference_words':len(r),'exact':r==h,
        'lexical_errors':distance(words(ref,False),words(hyp,False)), 'lexical_words':len(words(ref,False)),
        'numeric_errors':distance(rn,hn),'numeric_reference_tokens':len(rn),
        'numeric_sequence_exact':rn==hn,'reference_numeric_sequence':rn,'hypothesis_numeric_sequence':hn}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--generic',type=Path,required=True)
    p.add_argument('--specialist',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();plan=json.loads(args.plan.read_text())
    for row in plan['clips']:
        if sha(args.plan.parent/row['file'])!=row['sha256']:raise ValueError('Audio hash mismatch')
    model_paths={'generic':args.generic,'specialist':args.specialist}
    metadata={'plan_sha256':sha(args.plan),'script_sha256':sha(Path(__file__)),
        'weights_sha256':{k:sha(v/'model.bin') for k,v in model_paths.items()},
        'settings':{'device':'cpu','compute_type':'int8','cpu_threads':4,'decode':plan['decode'],
            'order':'Alternate model order per clip; both models loaded before measurement',
            'score':'Raw full transcription, no downstream model-score or no_speech filter; no corrections'},
        'packages':{k:importlib.metadata.version(k) for k in ('faster-whisper','ctranslate2')},'rows':[]}
    if args.output.exists():
        saved=json.loads(args.output.read_text())
        for k in ('plan_sha256','script_sha256','weights_sha256','settings','packages'):
            if saved[k]!=metadata[k]:raise ValueError('Cannot resume changed experiment: '+k)
        metadata=saved
    done={(x['id'],x['model']) for x in metadata['rows']}
    if len(done)!=len(metadata['rows']):raise ValueError('Duplicate results')
    from faster_whisper import WhisperModel
    models={k:WhisperModel(str(v.resolve()),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True) for k,v in model_paths.items()}
    for i,clip in enumerate(plan['clips']):
        order=['generic','specialist'] if i%2==0 else ['specialist','generic']
        for name in order:
            if (clip['id'],name) in done:continue
            start=time.perf_counter()
            segments,info=models[name].transcribe(str(args.plan.parent/clip['file']),**plan['decode'])
            segments=list(segments);text=' '.join(s.text.strip() for s in segments)
            elapsed=time.perf_counter()-start
            row={'id':clip['id'],'group':clip['group'],'model':name,'audio_sha256':clip['sha256'],
                'reference':clip['reference'],'transcript':text,'duration':clip['duration'],'seconds':elapsed,
                'metrics':metrics(clip['reference'],text),'segments':[{'start':s.start,'end':s.end,'text':s.text,'no_speech_prob':s.no_speech_prob,'avg_logprob':s.avg_logprob} for s in segments]}
            metadata['rows'].append(row)
            tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n');tmp.replace(args.output)
            print(json.dumps({'clip':i+1,'of':len(plan['clips']),'model':name,'seconds':round(elapsed,2),'errors':row['metrics']['errors'],'words':row['metrics']['reference_words']},ensure_ascii=False),flush=True)
    print('COMPLETE',len(metadata['rows']),flush=True)

if __name__=='__main__':main()
