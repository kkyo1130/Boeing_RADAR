"""Review EVERY auto label, drag to correct, and export a separate confirmed dataset.
Enter/SPACE: accept displayed box. R: redraw on original image. D: reject image. Q: save review progress and quit.
No dataset is exported until all staged images have an explicit human decision.
"""
import argparse
import csv
import hashlib
import json
import math
import shutil
from datetime import datetime,timezone
from pathlib import Path
from yolo_auto_collection import atomic_json,signature
from yolo_camera_data import FIELDS,load_dataset,write_yaml,fresh_output
from PIL import Image

BLIND_PROTOCOL="MCP_FULL_PANEL_EXCLUDES_WINDSHIELD_EFIS_PRIMARY"


def valid_box(box,width,height):
    return (isinstance(box,(list,tuple)) and len(box)==4 and
        all(isinstance(v,(int,float)) and math.isfinite(v) for v in box) and
        0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height)


def load_capture(root):
    root=Path(root).resolve();path=root/'capture_manifest.json'
    data=json.loads(path.read_text())
    meta=json.loads((root/'collection.json').read_text())
    if data.get('mode')!='AUTO_CANDIDATES' or meta.get('mode')!='AUTO_CANDIDATES':raise ValueError('Not an auto capture batch')
    if data.get('session')!=meta.get('session') or data.get('split')!=meta.get('split') or data.get('split') not in ('train','val','test') or not data.get('session'):
        raise ValueError('Capture session/split metadata differs')
    if not data.get('records'):raise ValueError('No images to review')
    ids=set();paths=set();hashes=set()
    for record in data['records']:
        identifier=record.get('id')
        if not isinstance(identifier,str) or len(identifier)!=5 or not identifier.isascii() or not identifier.isdigit():
            raise ValueError('Unsafe capture identifier')
        rel=Path(record['image_path']);image=(root/rel).resolve()
        if (rel.is_absolute() or '..' in rel.parts or root not in image.parents or not image.is_file()
            or image in paths or record['id'] in ids):raise ValueError('Missing, duplicate or unsafe image')
        if record['session_id']!=data['session'] or record['split']!=data['split'] or record.get('review_status')!='PENDING':
            raise ValueError('Inconsistent capture record')
        if record.get('category') not in ('candidates','needs_review'):raise ValueError('Unknown candidate category')
        with Image.open(image) as decoded:
            digest=signature(decoded)
            if decoded.size!=(record['width'],record['height']):raise ValueError('Image dimensions changed')
        if digest!=record['image_sha256'] or digest in hashes:raise ValueError('Image changed or duplicate pixels')
        if record['proposed_box'] is not None and not valid_box(record['proposed_box'],record['width'],record['height']):raise ValueError('Invalid proposal box')
        ids.add(record['id']);paths.add(image);hashes.add(digest)
    actual={p.resolve() for folder in ('candidates','needs_review') for p in (root/folder).glob('*.png')}
    if actual!=paths:raise ValueError('Unindexed capture images found; inspect interrupted capture before review')
    digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    return data,digest


def review_location(root,*,blind=False,review_dir=None):
    root=Path(root).resolve()
    if not blind:return root/'reviews.json'
    if review_dir is None:raise ValueError('--blind requires a separate --review-dir')
    directory=Path(review_dir).resolve()
    if directory==root or directory in root.parents or root in directory.parents:
        raise ValueError('Blind progress must be outside the original capture directory')
    return directory/'reviews.json'


def load_reviews(root,digest,*,blind=False,review_dir=None):
    path=review_location(root,blind=blind,review_dir=review_dir)
    if not path.exists():
        return dict(version=2 if blind else 1,capture_digest=digest,decisions={},
            annotation_mode='BLIND' if blind else 'ASSISTED',label_protocol=BLIND_PROTOCOL if blind else None)
    reviews=json.loads(path.read_text())
    if reviews.get('capture_digest')!=digest:raise ValueError('Source capture changed since review')
    if blind and (reviews.get('annotation_mode')!='BLIND' or reviews.get('label_protocol')!=BLIND_PROTOCOL):
        raise ValueError('Existing assisted approvals cannot be reused for blind labeling')
    if not blind and reviews.get('annotation_mode')=='BLIND':raise ValueError('Blind progress requires --blind')
    if blind and any(d.get('method')!='BLIND_MANUAL' for d in reviews.get('decisions',{}).values() if d.get('action')=='ACCEPTED'):
        raise ValueError('Blind approvals must come from a fresh manual rectangle')
    return reviews


def export_reviewed(root,output,*,blind=False,review_dir=None):
    root=Path(root).resolve();capture,digest=load_capture(root);reviews=load_reviews(root,digest,blind=blind,review_dir=review_dir)
    records=capture['records'];decisions=reviews['decisions']
    if set(decisions)!={r['id'] for r in records}:raise ValueError('Every image must be explicitly reviewed before export')
    accepted=[]
    for record in records:
        decision=decisions[record['id']]
        if decision.get('image_sha256')!=record['image_sha256'] or not decision.get('reviewed_at'):
            raise ValueError('Missing human review provenance')
        if decision.get('action')=='ACCEPTED':
            if decision.get('method') not in (('BLIND_MANUAL',) if blind else ('HUMAN_ACCEPT','HUMAN_DRAG')) or not valid_box(decision.get('box'),record['width'],record['height']):
                raise ValueError('Invalid human-approved box')
            accepted.append((record,decision))
        elif decision.get('action')!='REJECTED':raise ValueError('Unreviewed image')
    if not accepted:raise ValueError('All images rejected; no training dataset exported')
    output=fresh_output(output,[root,*([Path(review_dir).resolve()] if blind else [])]);output.mkdir(parents=True)
    try:from .label_mcp import yolo_bbox
    except ImportError:from label_mcp import yolo_bbox
    rows=[]
    for record,decision in accepted:
        split=record['split'];name=record['id'];ir=f'images/{split}/{name}.png';lr=f'labels/{split}/{name}.txt'
        (output/ir).parent.mkdir(parents=True,exist_ok=True);(output/lr).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(root/record['image_path'],output/ir)
        x1,y1,x2,y2=decision['box'];box=yolo_bbox(x1,y1,x2-x1,y2-y1,record['width'],record['height'])
        (output/lr).write_text('0 '+' '.join(f'{v:.8f}' for v in box)+'\n')
        rows.append(dict(source_path=f'{record["session_id"]}/{record["id"]}',image_path=ir,label_path=lr,
            session_id=record['session_id'],split=split,x=x1,y=y1,width=x2-x1,height=y2-y1,condition=record['condition']))
    with (output/'manifest.csv').open('w',newline='',encoding='utf-8') as fp:
        writer=csv.DictWriter(fp,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    atomic_json(output/'collection.json',dict(mode='HUMAN_REVIEWED',review_complete=True,requires_review=False,
        session=capture['session'],split=capture['split'],source_capture=str(root),capture_digest=digest,
        accepted=len(accepted),rejected=len(records)-len(accepted),annotation_mode='BLIND' if blind else 'ASSISTED',
        label_protocol=BLIND_PROTOCOL if blind else None))
    atomic_json(output/'review_audit.json',reviews)
    load_dataset(output,{capture['split']});write_yaml(output)
    return output


def review_gui(root,output,*,blind=False,review_dir=None):
    import cv2
    root=Path(root).resolve();capture,digest=load_capture(root);reviews=load_reviews(root,digest,blind=blind,review_dir=review_dir)
    progress_path=review_location(root,blind=blind,review_dir=review_dir)
    if blind:
        fresh_output(output,[root,Path(review_dir).resolve()])
        progress_path.parent.mkdir(parents=True,exist_ok=True)
    decisions=reviews['decisions'];window='BLIND MCP annotation - R draw | ENTER confirm | D reject | Q save' if blind else 'Review ALL MCP boxes - ENTER accept | R redraw | D reject | Q save/quit'
    try:
        for record in capture['records']:
            if record['id'] in decisions:continue
            frame=cv2.imread(str(root/record['image_path']))
            if frame is None:raise ValueError('Cannot decode review image')
            box=None if blind else record['proposed_box'];method='BLIND_MANUAL' if blind else 'HUMAN_ACCEPT'
            while True:
                preview=frame.copy()
                if box:
                    x1,y1,x2,y2=map(round,box);cv2.rectangle(preview,(x1,y1),(x2,y2),(0,180,255),2)
                lines=[f'Review {len(decisions)+1}/{len(capture["records"])} | {record["category"]} | score={record["model_score"]}',
                    record['reason'],'ENTER accept box | R mouse redraw | D reject image | Q save/quit']
                if blind:
                    lines=[f'BLIND manual annotation {len(decisions)+1}/{len(capture["records"])} | session {capture["session"]}',
                        'Include the full MCP panel: readouts, knobs and controls.',
                        'EXCLUDE windshield, EFIS side panels and lower primary flight displays.',
                        'R: draw a NEW rectangle | ENTER: confirm | D: reject | Q: save/quit']
                for i,line in enumerate(lines):cv2.putText(preview,line,(10,25+24*i),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
                cv2.imshow(window,preview);key=cv2.waitKey(30)&255
                if key in (ord('q'),27):
                    atomic_json(progress_path,reviews);return None
                if key==ord('r'):
                    x,y,w,h=cv2.selectROI(window,frame,showCrosshair=True,fromCenter=False)
                    if w>0 and h>0:box=[float(x),float(y),float(x+w),float(y+h)];method='BLIND_MANUAL' if blind else 'HUMAN_DRAG'
                    continue
                if key==ord('d') or (key in (10,13,32) and valid_box(box,record['width'],record['height'])):
                    decisions[record['id']]=dict(action='REJECTED' if key==ord('d') else 'ACCEPTED',
                        box=None if key==ord('d') else box,method=method,reviewed_at=datetime.now(timezone.utc).isoformat(),
                        image_sha256=record['image_sha256'])
                    atomic_json(progress_path,reviews);break
        return export_reviewed(root,output,blind=blind,review_dir=review_dir)
    finally:cv2.destroyAllWindows()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True,help='Separate new directory containing only reviewed/accepted labels')
    p.add_argument('--export-only',action='store_true',help='Export previously completed human reviews; never auto-accept')
    p.add_argument('--blind',action='store_true',help='Never display proposals/scores or reuse assisted approvals; draw every box manually')
    p.add_argument('--review-dir',type=Path,help='Separate progress directory required for --blind; supports resuming only its new blind reviews')
    args=p.parse_args()
    try:
        if args.blind and args.review_dir is None:raise ValueError('--blind requires --review-dir outside the source')
        fresh_output(args.output,[args.input,*([args.review_dir] if args.blind else [])])
        options=dict(blind=args.blind,review_dir=args.review_dir)
        result=export_reviewed(args.input,args.output,**options) if args.export_only else review_gui(args.input,args.output,**options)
        print(f'Exported confirmed dataset: {result}' if result else 'Review paused. No training dataset exported; rerun to resume.')
    except (ValueError,OSError,KeyError) as exc:p.error(str(exc))

if __name__=='__main__':main()
