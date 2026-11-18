"""Frozen, operator-authorized simulated cockpit camera experiment.
Commands provide scoring labels only, never OCR inputs. All scheduled frames count.
"""
import argparse,csv,hashlib,json,random,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import cv2,numpy as np,torch
from PIL import Image
from ultralytics import YOLO
from mcp_display_sync import DisplaySync
from mcp_yolo_gate import PanelGate,detect_panel_readouts,validate_detector
from mcp_window_readouts import detect_mcp_readouts as detect_readouts
from mcp_preprocessing import prepare_camera_crop,normalize_aligned
from mcp_character_ocr import CharacterOCR
from mcp_dataset import separate_output
# Shared unchanged baseline architecture.
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vision.ocr_v3_runtime import DigitCNN

def make_plan(seed,settings,excluded):
    rng=random.Random(seed);plan=[];used_h={h for h,a in excluded};used_a={a for h,a in excluded}
    while len(plan)<settings:
        h=f'{rng.randrange(360):03d}';a=f'{rng.randrange(1,391)*100:05d}'
        if h in used_h or a in used_a:continue
        used_h.add(h);used_a.add(a);plan.append((h,a))
    return plan

def run(a):
    torch.set_num_threads(4)
    baseline={}
    for kind,n in [('hdg',3),('alt',5)]:
        model=DigitCNN(n);saved=torch.load(a.baseline/f'{kind}_best.pt',map_location='cpu',weights_only=True);model.load_state_dict(saved['model']);model.eval();baseline[kind]=model
    character=CharacterOCR(a.character,'cpu');detector=YOLO(str(a.yolo));validate_detector(detector)
    out=separate_output(a.output,[a.character,a.baseline,a.yolo]);out.mkdir(parents=True);(out/'raw').mkdir();(out/'crops').mkdir()
    # Freeze the models and entire plan before the first new camera frame.
    excluded=set()
    for root in a.exclude:
        with (root/'labels.csv').open() as fp:rows=list(csv.DictReader(fp))
        by={}
        for row in rows:by.setdefault((row['session_id'],row['source_image']),{})[row['kind']]=row['text']
        excluded.update((v['hdg'],v['alt']) for v in by.values() if set(v)=={'hdg','alt'})
    for root in a.exclude_plan:
        excluded.update(tuple(pair) for pair in json.loads((root/'manifest.json').read_text())['plan'])
    plan=make_plan(a.seed,a.settings,excluded)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(created_at=datetime.now(timezone.utc).isoformat(),plan=plan,frames_per_setting=a.frames,seed=a.seed,
        purpose='FROZEN_NEW_CAMERA_SESSION',condition_limit='Single operator camera setup; no claimed unseen-angle generalization',
        character_sha256=sha(a.character),v5_sha256={k:sha(a.baseline/f'{k}_best.pt') for k in baseline},
        gate=PanelGate().policy(),candidate_score_threshold=.75,yolo_imgsz=a.imgsz,raw_jpeg_quality=a.raw_jpeg_quality,raw_every=a.raw_every,
        localizer_sha256=sha(Path(__file__).with_name('mcp_window_readouts.py')),truth_source='OPERATOR_AUTHORIZED_SIMULATOR_COMMAND_MATCHING_RENDER_ACK',
        inference_inputs='camera RGB and kind only; no command or truth supplied to OCR',localizer='glass_windows_v1')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    cap=cv2.VideoCapture(int(a.source) if a.source.isdecimal() else a.source)
    if not cap.isOpened():raise RuntimeError('Camera unavailable')
    sync=DisplaySync(a.sync_url,'tablet',1.0);old=sync.request('state');records=[];index=0
    try:
        with (out/'frames.jsonl').open('w') as fp:
            for setting,(hdg,alt) in enumerate(plan):
                sync.set(hdg,alt);gate=PanelGate();start=time.monotonic();warm=0
                # Drain while awaiting actual client ACK, never infer labels from OCR.
                while True:
                    ok,frame=cap.read()
                    if not ok:raise RuntimeError('Camera read failure during settle')
                    warm+=1
                    if sync.ready() and warm>=5:break
                    if time.monotonic()-start>20:raise RuntimeError('Selected display ACK unavailable; experiment stopped')
                for j in range(a.frames):
                    ok,frame=cap.read();index+=1
                    row=dict(frame=index,setting=setting,truth={'hdg':hdg,'alt':alt},ack=sync.ready(),camera_ok=ok,regions={},gate_reason=None,models={})
                    if not row['ack']:raise RuntimeError('Display ACK lost; no unverified label written')
                    if ok:
                        if index%a.raw_every==0:
                            raw=f'raw/{index:05d}.jpg'
                            if not cv2.imwrite(str(out/raw),frame,[cv2.IMWRITE_JPEG_QUALITY,a.raw_jpeg_quality]):raise OSError('Raw write failed')
                            row['raw']=raw
                        regions,reason=detect_panel_readouts(detector,frame,gate,detect_readouts,device=a.device,imgsz=a.imgsz)
                        row['gate_reason']=reason;row['regions']=regions
                        if set(regions)=={'hdg','alt'}:
                            for kind,(x,y,w,h) in regions.items():
                                image=prepare_camera_crop(Image.fromarray(cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2RGB)),kind)
                                if image is None:continue
                                rel=f'crops/{index:05d}_{kind}.png';image.save(out/rel)
                                with torch.inference_mode():
                                    data=torch.from_numpy(np.asarray(normalize_aligned(image,kind),dtype=np.float32).copy())[None,None]/255.
                                    p=baseline[kind](data).softmax(-1)[0];pred=''.join(map(str,p.argmax(-1).tolist()));score=float(p.max(-1).values.min())
                                accepted=score>=.75 and (kind!='hdg' or int(pred)<=359)
                                row['models'].setdefault('v5',{})[kind]=dict(raw_value=pred,value=pred if accepted else None,model_score=score)
                                row['models'].setdefault('character',{})[kind]=character.infer_aligned(image,kind)
                                row.setdefault('crops',{})[kind]=rel
                    fp.write(json.dumps(row)+'\n');fp.flush();records.append(row)
                print(json.dumps(dict(setting=setting+1,total=len(plan),hdg=hdg,alt=alt,scheduled_frames=len(records))),flush=True)
    finally:
        cap.release()
        try:sync.set(f"{old['heading']:03d}",f"{old['altitude']:05d}")
        except Exception:pass
    results={}
    for model in ('v5','character'):
        results[model]={}
        for kind in ('hdg','alt'):
            available=[r for r in records if kind in r['models'].get(model,{})]
            raw_correct=sum(r['models'][model][kind]['raw_value']==r['truth'][kind] for r in available)
            accepted=[r for r in available if r['models'][model][kind]['value'] is not None]
            correct=sum(r['models'][model][kind]['value']==r['truth'][kind] for r in accepted)
            results[model][kind]=dict(scheduled=len(records),cropped=len(available),raw_exact_correct=raw_correct,
                crop_string_accuracy=raw_correct/len(available) if available else None,all_frame_raw_exact_accuracy=raw_correct/len(records),
                accepted=len(accepted),accepted_correct=correct,accepted_accuracy=correct/len(accepted) if accepted else None,
                all_frame_accepted_exact_accuracy=correct/len(records))
    summary=dict(results=results,gate_reasons=dict(Counter(r['gate_reason'] or 'READOUTS_FOUND' for r in records)),
        temporal_startup_included=True,uncertainty='Repeated frames are correlated; frame accuracy is not a large independent sample estimate')
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)
    assert sha(a.character)==manifest['character_sha256']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',default='0');p.add_argument('--sync-url',default='http://127.0.0.1:5173');p.add_argument('--device',default='mps');p.add_argument('--character',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--yolo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--exclude',type=Path,action='append',default=[]);p.add_argument('--exclude-plan',type=Path,action='append',default=[]);p.add_argument('--settings',type=int,default=12);p.add_argument('--frames',type=int,default=10);p.add_argument('--raw-every',type=int,default=1,help='Audit JPEG cadence only; all frames inferred/logged, all complete CNN crops saved');p.add_argument('--raw-jpeg-quality',type=int,default=95,help='Audit JPEG storage only; inference uses the original camera frame, aligned crops remain lossless PNG');p.add_argument('--imgsz',type=int,default=640);p.add_argument('--seed',type=int,default=20261112);a=p.parse_args()
    if a.raw_every<1:p.error('raw-every must be positive')
    if not 1<=a.raw_jpeg_quality<=100:p.error('JPEG quality must be 1-100')
    if a.settings<1 or a.frames<3:p.error('Need settings>=1 and frames>=3')
    run(a)
if __name__=='__main__':main()
