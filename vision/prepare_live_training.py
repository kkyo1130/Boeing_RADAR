"""Create aligned train/development data from independently labelled raw sessions."""
import argparse
import csv
import json
import shutil
from pathlib import Path
from PIL import Image
try:
    from .auto_windows import locate_windows
    from .mcp_preprocessing import prepare_camera_crop
except ImportError:
    from vision.auto_windows import locate_windows
    from vision.mcp_preprocessing import prepare_camera_crop

FIELDS=['image_path','source_image','split','kind','text','session_id']

def prepare(output, train, development, synthetic):
    if output.exists():raise ValueError('Fresh output required')
    if development is not None and any(p.resolve()==development.resolve() for p in train):raise ValueError('Train/development session leakage')
    output.mkdir(parents=True);rows=[];audit=[];seen=set()
    for source in [*train,*([development] if development is not None else [])]:
        info=json.loads((source/'session.json').read_text());split='val' if source==development else 'train'
        if info['role']!=('development' if split=='val' else 'train'):raise ValueError('Session role mismatch')
        for i,line in enumerate((source/'frames.jsonl').read_text().splitlines()):
            record=json.loads(line)
            if record['sha256'] in seen:raise ValueError('Duplicate frame/session leakage')
            seen.add(record['sha256']);image=Image.open(source/record['path']).convert('RGB');rois=locate_windows(image);pair=[]
            if rois:
                for kind in ('hdg','alt'):
                    crop=prepare_camera_crop(image.crop(rois[kind]),kind)
                    if crop is None:break
                    pair.append((kind,crop))
            audit.append(dict(source=source.name,path=record['path'],split=split,detected=rois is not None,complete_pair=len(pair)==2))
            if len(pair)!=2:continue
            for kind,crop in pair:
                rel=f'{split}/{source.name}/{kind}/{i:04d}.png';dest=output/rel;dest.parent.mkdir(parents=True,exist_ok=True);crop.save(dest)
                rows.append(dict(image_path=rel,source_image=record['path'],split=split,kind=kind,text=record[kind],session_id=('camera_val:' if split=='val' else 'camera_train:')+source.name))
    for source in synthetic:
        for i,row in enumerate(csv.DictReader((source/'labels.csv').open())):
            if row['split']!='train':continue
            rel=f'train/synthetic/{source.name}/{i:05d}.png';dest=output/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/row['image_path'],dest)
            rows.append({**{k:row[k] for k in FIELDS},'image_path':rel,'session_id':'synthetic:'+source.name+':'+row['session_id']})
    if development is not None and not all(any(r['split']=='val' and r['kind']==kind for r in rows) for kind in ('hdg','alt')):raise ValueError('No usable development pairs')
    with (output/'labels.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    (output/'preparation.json').write_text(json.dumps(dict(audit=audit,train_sessions=[p.name for p in train],development_session=development.name if development else None,policy='Raw failures remain in session evaluation denominators'),indent=2))
    print(json.dumps(dict(rows=len(rows),raw_frames=len(audit),usable_pairs=sum(r['complete_pair'] for r in audit))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--train',type=Path,action='append',default=[]);p.add_argument('--development',type=Path);p.add_argument('--synthetic',type=Path,action='append',default=[]);a=p.parse_args();prepare(a.output,a.train,a.development,a.synthetic)
