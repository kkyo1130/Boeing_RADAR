"""YOLO MCP manifest validation, pixel provenance and leakage checks."""
import csv
import hashlib
import json
import math
from pathlib import Path
from PIL import Image

FIELDS=['source_path','image_path','label_path','session_id','split','x','y','width','height','condition']

def bbox_xyxy(values,w,h):
    x,y,bw,bh=values
    if not all(math.isfinite(v) for v in values) or min(bw,bh)<=0:
        raise ValueError('Invalid YOLO box')
    if x-bw/2 < -1e-6 or y-bh/2 < -1e-6 or x+bw/2>1+1e-6 or y+bh/2>1+1e-6:
        raise ValueError('YOLO box outside image')
    return [(x-bw/2)*w,(y-bh/2)*h,(x+bw/2)*w,(y+bh/2)*h]

def image_hash(path):
    with Image.open(path) as image:
        image.load();rgb=image.convert('RGB')
        if min(rgb.size)<16: raise ValueError('Image too small')
        return hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest(),rgb.size

def load_dataset(root,allowed=('train','val','test')):
    root=Path(root).resolve()
    metadata=root/'collection.json'
    meta={}
    if metadata.exists():
        meta=json.loads(metadata.read_text())
        if meta.get('mode')=='AUTO_CANDIDATES' or meta.get('requires_review'):
            raise ValueError('Automatic labels are UNVERIFIED. Review every image and export a confirmed dataset first.')
    with (root/'manifest.csv').open(newline='',encoding='utf-8') as fp:
        reader=csv.DictReader(fp)
        if not {'image_path','label_path','session_id','split'}.issubset(reader.fieldnames or []):
            raise ValueError('Missing manifest columns')
        rows=list(reader)
    if not rows: raise ValueError(f'Empty dataset: {root}')
    paths=set();hashes=set();sessions={};entries=[]
    for row in rows:
        split,sid=row['split'],row['session_id']
        if split not in allowed or not sid: raise ValueError('Invalid split/session')
        if sid in sessions and sessions[sid]!=split: raise ValueError(f'Session leakage: {sid}')
        sessions[sid]=split
        files=[]
        for key in ('image_path','label_path'):
            rel=Path(row[key]);path=(root/rel).resolve()
            if rel.is_absolute() or '..' in rel.parts or root not in path.parents or not path.is_file() or path in paths:
                raise ValueError(f'Missing, duplicate or unsafe path: {path}')
            paths.add(path);files.append(path)
        digest,(w,h)=image_hash(files[0])
        if digest in hashes: raise ValueError('Duplicate image pixels')
        hashes.add(digest)
        lines=files[1].read_text().strip().splitlines()
        if len(lines)!=1: raise ValueError('Exactly one full MCP label required per image')
        parts=lines[0].split()
        if len(parts)!=5 or parts[0]!='0': raise ValueError('Expected single class 0 MCP YOLO label')
        box=bbox_xyxy(list(map(float,parts[1:])),w,h)
        entries.append(dict(row=row,hash=digest,box=box,width=w,height=h))
    if meta.get('mode')=='HUMAN_REVIEWED':
        audit_path=root/'review_audit.json'
        if not meta.get('review_complete') or not audit_path.is_file():
            raise ValueError('Missing completed human review audit')
        audit=json.loads(audit_path.read_text())
        if audit.get('capture_digest')!=meta.get('capture_digest'):
            raise ValueError('Review provenance differs from capture')
        decisions=audit.get('decisions',{})
        accepted={key:value for key,value in decisions.items() if value.get('action')=='ACCEPTED'}
        if len(entries)!=meta.get('accepted') or len(entries)!=len(accepted) or len(decisions)!=meta.get('accepted',0)+meta.get('rejected',0):
            raise ValueError('Incomplete human review counts')
        if any(d.get('action') not in ('ACCEPTED','REJECTED') or not d.get('reviewed_at') for d in decisions.values()):
            raise ValueError('Unreviewed image in audit')
        blind=meta.get('annotation_mode')=='BLIND'
        if blind and (audit.get('annotation_mode')!='BLIND' or audit.get('label_protocol')!='MCP_FULL_PANEL_EXCLUDES_WINDSHIELD_EFIS_PRIMARY' or meta.get('label_protocol')!=audit.get('label_protocol')):
            raise ValueError('Missing blind annotation protocol/provenance')
        for entry in entries:
            row=entry['row'];decision=accepted.get(Path(row['image_path']).stem,{})
            approved=decision.get('box')
            if (row['split']!=meta.get('split') or row['session_id']!=meta.get('session') or
                decision.get('image_sha256')!=entry['hash'] or decision.get('method') not in (('BLIND_MANUAL',) if blind else ('HUMAN_ACCEPT','HUMAN_DRAG')) or
                not isinstance(approved,list) or len(approved)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in approved) or
                any(abs(a-b)>.001 for a,b in zip(approved,entry['box']))):
                raise ValueError('Training label/image differs from approved human review')
    fingerprint=hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()
    return dict(root=str(root),entries=entries,sessions=sessions,hashes=hashes,fingerprint=fingerprint)

def disjoint(datasets):
    hashes=set();sessions=set();roots=set()
    for data in datasets:
        if data['root'] in roots or hashes & data['hashes'] or sessions & set(data['sessions']):
            raise ValueError('Duplicate dataset/image or capture session across datasets')
        roots.add(data['root']);hashes.update(data['hashes']);sessions.update(data['sessions'])

def fresh_output(output,inputs):
    output=Path(output).resolve()
    if output.exists():raise ValueError(f'Output already exists: {output}')
    for root in inputs:
        root=Path(root).resolve()
        if root==output or root in output.parents or output in root.parents:
            raise ValueError('Output overlaps an input')
    return output

def write_yaml(root,destination=None):
    destination=Path(destination or Path(root)/'dataset.yaml')
    destination.write_text('path: '+json.dumps(str(Path(root).resolve()))+
        '\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: mcp\n')
    return destination
