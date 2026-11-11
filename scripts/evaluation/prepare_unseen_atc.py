"""Freeze a new controller-only sample before either model is evaluated."""
import argparse
import hashlib
import io
import json
import random
import re
from pathlib import Path
import wave

import pyarrow.parquet as pq

ID = re.compile(r'uwb-atcc_[A-Za-z0-9-]+_[0-9]+_[0-9]+_[A-Z]+')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def group(identifier):
    return identifier.split('_')[1]

def normalize(text):
    return ' '.join(re.findall(r'[^\W\d_]+|\d+', text.casefold()))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--communication',type=Path,required=True)
    p.add_argument('--parquet',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if (args.output/'plan.json').exists():
        raise FileExistsError('Frozen plan already exists; use a new directory for another selection')
    prior_ids=set();prior_texts=set();audit=[]
    current=Path.cwd().resolve()
    def collect(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k in ('text','reference','transcript') and isinstance(v,str):prior_texts.add(normalize(v))
                collect(v)
        elif isinstance(obj,list):
            for v in obj:collect(v)
    # Only prior JSON experiment/training records. Do not inspect weights/audio.
    for path in sorted(args.communication.rglob('*.json')):
        if current in path.resolve().parents or any(x in path.parts for x in ('.venv','node_modules','.git','models')):continue
        if path.stat().st_size>20_000_000:continue
        # This is a downloaded full-split catalog, not model training/evaluation input.
        if path.name=='uwb_official_test_text.json':continue
        raw=path.read_text(errors='replace');ids=set(ID.findall(raw))
        if not ids:continue
        prior_ids.update(ids)
        try:collect(json.loads(raw))
        except json.JSONDecodeError:pass
        audit.append({'path':str(path.relative_to(args.communication)), 'sha256':sha(path),'ids':len(ids)})
    prior_groups={group(i) for i in prior_ids}
    rows=pq.read_table(args.parquet).to_pylist()
    candidates=[];reasons={}
    def exclude(reason):reasons[reason]=reasons.get(reason,0)+1
    for row in rows:
        if not row['id'].endswith('_AT'):exclude('non_controller_or_mixed');continue
        if group(row['id']) in prior_groups:exclude('previous_recording_group');continue
        if normalize(row['text']) in prior_texts:exclude('previous_text');continue
        if not normalize(row['text']):exclude('empty_reference');continue
        candidates.append(row)
    # One random utterance per recording, then fixed random 60 groups. No filtering by errors or command vocabulary.
    rng=random.Random(20261110);rng.shuffle(candidates)
    chosen=[];seen_groups=set();seen_texts=set();seen_audio=set()
    for row in candidates:
        g=group(row['id']);text=normalize(row['text']);digest=hashlib.sha256(row['audio']['bytes']).hexdigest()
        if g in seen_groups or text in seen_texts or digest in seen_audio:continue
        chosen.append(row);seen_groups.add(g);seen_texts.add(text);seen_audio.add(digest)
        if len(chosen)==60:break
    if len(chosen)<60:raise ValueError(f'Only {len(chosen)} eligible groups; do not silently change sample')
    args.output.mkdir(parents=True,exist_ok=True)
    manifest={'dataset':'Jzuluaga/uwb_atcc','revision':'1e8270beb8c1643c8735dddb7229fffb0e399f74','split':'test','seed':20261110,
        'selection':'First 60 distinct recording groups after seeded shuffle, controller-only _AT; exclude all prior JSON IDs by recording group and exact normalized prior text; deduplicate text/audio. No duration, quality, vocabulary or model-output selection.',
        'parquet_sha256':sha(args.parquet),'catalog_only_excluded_from_used_set':['external-ner-eval-20261109/uwb_official_test_text.json (full split metadata, not training/evaluation selection)'],'prior_files':audit,'prior_ids':len(prior_ids),'prior_groups':len(prior_groups),
        'excluded':reasons,'eligible_rows':len(candidates),'eligible_groups':len({group(r['id']) for r in candidates}),
        'pretraining_overlap':'Unknown for base Whisper; specialist card declares ATCO2+ATCOSIM, not UWB; exact third-party training manifest unavailable.',
        'decode':{'language':'en','beam_size':5,'condition_on_previous_text':False,'vad_filter':True,'temperature':0.0,
            'initial_prompt':'Air traffic control phraseology: climb and maintain, descend and maintain, feet, flight level, turn left, turn right, heading. Numbers: zero, one, two, three, four, five, six, seven, eight, nine, thousand, hundred.'},
        'clips':[]}
    for row in chosen:
        raw=row['audio']['bytes'];name=row['id']+'.wav';(args.output/name).write_bytes(raw)
        with wave.open(io.BytesIO(raw)) as f:rate=f.getframerate();duration=f.getnframes()/rate
        manifest['clips'].append({'id':row['id'],'group':group(row['id']),'file':name,'reference':row['text'],'sha256':hashlib.sha256(raw).hexdigest(),'duration':duration,'sample_rate':rate})
    (args.output/'plan.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('clips','prior_files','decode')},indent=2))
    print('chosen',len(chosen),'seconds',sum(c['duration'] for c in manifest['clips']))

if __name__=='__main__':main()
