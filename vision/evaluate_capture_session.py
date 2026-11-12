"""Evaluate raw ACK-labelled sessions; missing/detection failures stay in denominators."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from PIL import Image
try:
    from .auto_windows import locate_windows
    from .ocr_v3_runtime import OCRv3
    from .mcp_preprocessing import prepare_camera_crop
except ImportError:
    from vision.auto_windows import locate_windows
    from vision.ocr_v3_runtime import OCRv3
    from vision.mcp_preprocessing import prepare_camera_crop


def evaluate(session, checkpoints, output, regions_file=None, apple_fallback=False):
    info=json.loads((session/'session.json').read_text())
    rows=[json.loads(line) for line in (session/'frames.jsonl').read_text().splitlines()]
    character = (Path(checkpoints)/'character_best.pt').is_file()
    if character:
        from vision.mcp_character_ocr import CharacterOCR
        model=CharacterOCR(Path(checkpoints)/'character_best.pt')
    else:
        model=OCRv3(checkpoints)
    scheduled=len(info['plan'])*info['frames_per_value']
    stats={k:dict(scheduled=scheduled,recorded=len(rows),detected=0,preprocessed=0,accepted=0,correct=0,wrong=0) for k in ('hdg','alt')}
    session_hash=hashlib.sha256((session/'frames.jsonl').read_bytes()).hexdigest()
    frozen=None
    if regions_file:
        reference=json.loads(regions_file.read_text())
        if reference.get('session_sha256')!=session_hash:raise ValueError('Region reference belongs to another session')
        frozen={row['path']:row['rois'] for row in reference['predictions']}
    predictions=[]
    for row in rows:
        start=time.monotonic()
        if hashlib.sha256((session/row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Frame content changed')
        image=Image.open(session/row['path']).convert('RGB')
        rois=frozen[row['path']] if frozen is not None else locate_windows(image)
        results={}
        for kind in ('hdg','alt'):
            s=stats[kind];out=dict(value=None,reason='REGION_NOT_FOUND')
            if rois:
                s['detected']+=1;crop=image.crop(rois[kind])
                aligned=prepare_camera_crop(crop,kind);s['preprocessed']+=aligned is not None
                out=(model.infer_aligned(aligned,kind) if aligned is not None else dict(value=None,reason='PREPROCESSING_FAILED')) if character else model.infer(crop,kind)
            if apple_fallback and rois:
                from vision.text_windows import read_crop
                fallback=read_crop(image.crop(rois[kind]),kind)
                if fallback and out.get('value') is None:
                    out={**fallback,'primary_reason':out.get('reason')}
                elif fallback and out['value']!=fallback['value']:
                    out=dict(value=None,reason='OCR_ENGINE_DISAGREEMENT')
            if out['value'] is not None:
                s['accepted']+=1;s['correct']+=out['value']==row[kind];s['wrong']+=out['value']!=row[kind]
            results[kind]=out
        predictions.append(dict(path=row['path'],group=row['group'],truth={k:row[k] for k in ('hdg','alt')},rois=rois,results=results,seconds=time.monotonic()-start))
    for s in stats.values():
        s['missing']=scheduled-len(rows);s['held_or_missing']=scheduled-s['accepted']
        s['correct_per_scheduled']=s['correct']/scheduled if scheduled else None
        s['wrong_per_accepted']=s['wrong']/s['accepted'] if s['accepted'] else None
    report=dict(role=info['role'],condition=info['condition'],groups=len(info['plan']),correlated_frames=True,session_sha256=session_hash,regions_frozen=regions_file is not None,apple_fallback=apple_fallback,timing_scope='model_only_with_frozen_regions' if regions_file else 'detector_and_model',
                models={k:hashlib.sha256((Path(checkpoints)/('character_best.pt' if character else k+'_best.pt')).read_bytes()).hexdigest() for k in ('hdg','alt')},
                stats=stats,predictions=predictions,scope='Scoped capture session; not operational accuracy')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--checkpoints',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--regions',type=Path);p.add_argument('--apple-fallback',action='store_true');a=p.parse_args()
    import torch;torch.set_num_threads(4)
    print(json.dumps(evaluate(a.session,a.checkpoints,a.output,a.regions,a.apple_fallback)['stats']),flush=True)
