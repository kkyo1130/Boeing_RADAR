"""Strict OCR dataset preflight and provenance; no torch dependency."""
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image

FIELDS=['image_path','kind','text','split','session_id','source_image']

def validate_dataset(root, splits, paired=False):
    root=Path(root).resolve()
    with (root/'labels.csv').open(newline='',encoding='utf-8') as fp:
        reader=csv.DictReader(fp)
        if not set(FIELDS).issubset(reader.fieldnames or []): raise ValueError(f'Missing columns: {root}')
        rows=list(reader)
    if not rows: raise ValueError(f'Empty dataset: {root}')
    paths=set(); sessions={}; sources={}; hashes={}; digests=[]
    for row in rows:
        kind=row['kind']; text=row['text']; split=row['split']; rel=Path(row['image_path'])
        n={'hdg':3,'alt':5}.get(kind)
        if (n is None or len(text)!=n or not text.isascii() or not text.isdigit()
            or int(text)>(359 if kind=='hdg' else 99900) or split not in splits
            or not row['session_id'] or not row['source_image'] or rel.is_absolute() or '..' in rel.parts):
            raise ValueError(f'Invalid label/path: {row}')
        path=(root/rel).resolve()
        if root not in path.parents or not path.is_file() or path in paths:
            raise ValueError(f'Missing/duplicate/unsafe image: {path}')
        paths.add(path)
        sid=row['session_id']
        if sid in sessions and sessions[sid]!=split: raise ValueError(f'Session leakage: {sid}')
        sessions[sid]=split
        source=(sid,row['source_image'])
        members=sources.setdefault(source,[])
        if any(x['kind']==kind for x in members): raise ValueError(f'Duplicate source/kind: {source}')
        if any(x['split']!=split for x in members): raise ValueError(f'Source leakage: {source}')
        members.append(row)
        with Image.open(path) as im:
            im.load(); rgb=im.convert('RGB')
            if im.width<8 or im.height<8: raise ValueError(f'Invalid image dimensions: {path}')
            digest=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        if digest in hashes:
            old=hashes[digest]
            if paired or (old['split'],old['kind'],old['text'])!=(split,kind,text):
                raise ValueError(f'Duplicate pixels/conflicting label/split: {path}')
        hashes[digest]=row; digests.append(digest)
    if paired and any({x['kind'] for x in pair}!={'hdg','alt'} for pair in sources.values()):
        raise ValueError('Incomplete HDG/ALT pair')
    meta=root/'collection.json'
    if meta.exists():
        info=json.loads(meta.read_text())
        if info.get('plan')=='v6':
            if info.get('preprocessing')!='camera_amber_align_v1' or set(sessions)!={info['session_id']} or set(sessions.values())!={info['split']}:
                raise ValueError('Collection metadata/session mismatch')
    # Stable content fingerprint includes labels and ordering, independent of directory location.
    fingerprint=hashlib.sha256(json.dumps(list(zip(rows,digests)),sort_keys=True).encode()).hexdigest()
    return dict(root=str(root),rows=rows,hashes=hashes,sessions=sessions,fingerprint=fingerprint)

def disjoint(datasets):
    seen_hashes={}; seen_roots=set(); camera_sessions={}
    for data in datasets:
        root=data['root']
        if root in seen_roots: raise ValueError(f'Duplicate dataset: {root}')
        seen_roots.add(root)
        for digest in data['hashes']:
            if digest in seen_hashes: raise ValueError(f'Duplicate image across datasets: {root} and {seen_hashes[digest]}')
            seen_hashes[digest]=root
        # Legacy camera_0000 IDs were local to a batch. New v6 physical session IDs are global.
        meta=Path(root)/'collection.json'
        if meta.exists() or any(not sid.startswith(('camera_', 'base:', 'camera_1:', 'camera_2:')) for sid in data['sessions']):
            for sid,split in data['sessions'].items():
                if sid in camera_sessions: raise ValueError(f'Capture session shared by datasets: {sid}')
                camera_sessions[sid]=(root,split)

def separate_output(output, inputs):
    output=Path(output).resolve()
    for source in inputs:
        source=Path(source).resolve()
        if output==source or output in source.parents or source in output.parents:
            raise ValueError('Output must be separate from datasets and initial checkpoints')
    if output.exists(): raise ValueError(f'Output exists; refusing overwrite: {output}')
    return output
