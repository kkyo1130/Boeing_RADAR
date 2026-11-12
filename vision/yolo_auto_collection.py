"""Unverified auto-capture staging. Never writes YOLO training labels."""
import hashlib
import json
import math
import os
import time
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from PIL import Image
from mcp_yolo_gate import PanelGate,validate_detector


def atomic_json(path,data):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8') as fp:
        json.dump(data,fp,ensure_ascii=False,indent=2,allow_nan=False);fp.flush();os.fsync(fp.fileno())
    temporary.replace(path)


def signature(image):
    rgb=image.convert('RGB')
    return hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()


class SimilarFrames:
    """Compare decoded RGB and small color thumbnails; remember only saved frames."""
    def __init__(self,distance=.015,history=20):
        if not math.isfinite(distance) or not 0<=distance<=1:raise ValueError('Invalid duplicate distance')
        self.distance=distance;self.recent=deque(maxlen=history);self.exact=set()
    def thumbnail(self,image):
        return np.asarray(image.convert('RGB').resize((64,48),Image.Resampling.BILINEAR),dtype=np.float32)/255
    def duplicate(self,image):
        if signature(image) in self.exact:return True
        sample=self.thumbnail(image)
        return any(float(np.abs(sample-old).mean())<=self.distance for old in self.recent)
    def remember(self,image):
        self.exact.add(signature(image));self.recent.append(self.thumbnail(image))


def predict_candidate(model,frame,gate,*,device='cpu',imgsz=960):
    """Uncertain proposals are retained for humans; no failed prediction is ground truth."""
    try:
        result=model.predict(frame,conf=.1,device=device,imgsz=imgsz,verbose=False)[0]
        boxes=result.boxes
        candidates=[] if boxes is None else [dict(box=[float(v) for v in b],score=float(s),**{'class':int(c)}) for b,s,c in
            zip(boxes.xyxy.cpu().tolist(),boxes.conf.cpu().tolist(),boxes.cls.cpu().tolist())]
        candidates=[c for c in candidates if c['class']==0 and math.isfinite(c['score']) and len(c['box'])==4 and all(math.isfinite(v) for v in c['box'])]
        candidates.sort(key=lambda c:c['score'],reverse=True)
        height,width=frame.shape[:2]
        accepted,reason=gate.select(candidates,width,height)
        top=candidates[0] if candidates else None
        proposed=None
        if top:
            a,b,c,d=top['box'];a,b,c,d=max(0,a),max(0,b),min(width,c),min(height,d)
            if c>a and d>b:proposed=[a,b,c,d]
        return dict(category='candidates' if accepted else 'needs_review',
            proposed_box=list(accepted) if accepted else proposed,model_score=top['score'] if top else None,
            reason=reason or 'HIGH_SCORE_STABLE_UNVERIFIED',detections=candidates)
    except Exception as exc:
        gate.reject('DETECTOR_ERROR')
        return dict(category='needs_review',proposed_box=None,model_score=None,
            reason='DETECTOR_ERROR:'+type(exc).__name__,detections=[])


def collect_auto(args,output,*,model=None):
    import cv2
    output=Path(output)
    capture_only=getattr(args,'capture_only',False)
    if not capture_only:
        if not args.yolo_weights or not args.yolo_weights.is_file():raise ValueError('--auto-interval requires a trained --yolo-weights file')
        if model is None:
            from ultralytics import YOLO
            model=YOLO(str(args.yolo_weights))
        validate_detector(model)
    gate=PanelGate(args.yolo_conf,args.yolo_stable_frames)
    duplicate_filter=SimilarFrames(args.dedup_distance)
    cap=cv2.VideoCapture(int(args.source) if args.source.isdecimal() else args.source)
    if not cap.isOpened():
        cap.release();raise ValueError('Cannot open camera')
    window='MCP auto capture - UNVERIFIED | SPACE capture | N notes | Q quit'
    count=0;candidate_count=0;review_count=0;duplicates=0
    manifest=dict(version=1,mode='AUTO_CANDIDATES',session=args.session,split=args.split,target_count=args.count,records=[])
    stop_reason='TARGET_REACHED'
    try:
        output.mkdir(parents=True)
        atomic_json(output/'collection.json',dict(session=args.session,split=args.split,source=args.source,
            mode='AUTO_CANDIDATES',requires_review=True,review_complete=False,
            auto_interval=args.auto_interval,target_count=args.count,capture_only=capture_only,
            yolo_weights=None if capture_only else str(args.yolo_weights.resolve()),
            weights_sha256=None if capture_only else hashlib.sha256(args.yolo_weights.read_bytes()).hexdigest(),
            threshold=args.yolo_conf,stable_frames=args.yolo_stable_frames,dedup_distance=args.dedup_distance))
        atomic_json(output/'capture_manifest.json',manifest)
        last_attempt=time.monotonic()
        while count<args.count:
            ok,frame=cap.read()
            if not ok:
                stop_reason='CAMERA_READ_FAILED';break
            frame_at=datetime.now(timezone.utc).isoformat()
            candidate=(dict(category='needs_review',proposed_box=None,model_score=None,reason='BLIND_CAPTURE_ONLY_NO_MODEL',detections=[]) if capture_only else predict_candidate(model,frame,gate,device=args.yolo_device,imgsz=args.yolo_imgsz))
            preview=frame.copy();box=candidate['proposed_box']
            if box:
                x1,y1,x2,y2=map(int,box)
                color=(70,210,110) if candidate['category']=='candidates' else (0,180,255)
                cv2.rectangle(preview,(x1,y1),(x2,y2),color,2)
            score='missing' if candidate['model_score'] is None else f"{candidate['model_score']:.2f}"
            lines=[f'AUTO {args.auto_interval:g}s | saved {count}/{args.count} | ALL {count} labels UNVERIFIED',
                f'stable candidates {candidate_count} | needs review {review_count} | duplicates skipped {duplicates}',
                f'MCP score {score} | {candidate["reason"]}', 'SPACE capture | N condition note | Q quit']
            for index,line in enumerate(lines):
                cv2.putText(preview,line,(10,25+index*24),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
            cv2.imshow(window,preview);key=cv2.waitKey(20)&255
            if key in (ord('q'),27):
                stop_reason='USER_QUIT';break
            if key==ord('n'):
                args.condition=input('Distance/angle/brightness/reflection notes: ').strip()
                # Input may block for a long time. Read new frames before the next timed save.
                last_attempt=time.monotonic();gate.reject('CONDITION_CHANGED');continue
            now=time.monotonic()
            if key!=32 and now-last_attempt<args.auto_interval:continue
            last_attempt=now
            image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            if duplicate_filter.duplicate(image):duplicates+=1;continue
            category=candidate['category'];rel=f'{category}/{count:05d}.png'
            (output/rel).parent.mkdir(parents=True,exist_ok=True)
            image.save(output/rel)
            record=dict(id=f'{count:05d}',image_path=rel,image_sha256=signature(image),
                width=image.width,height=image.height,session_id=args.session,split=args.split,
                captured_at=frame_at,time_basis='CAMERA_READ_COMPLETED',condition=args.condition,
                review_status='PENDING',**candidate)
            manifest['records'].append(record)
            atomic_json(output/'capture_manifest.json',manifest)
            duplicate_filter.remember(image);count+=1
            candidate_count+=category=='candidates';review_count+=category=='needs_review'
            print(f'Saved {count}/{args.count}; candidates={candidate_count}, needs_review={review_count}; ALL require human review')
    finally:
        cap.release();cv2.destroyAllWindows()
    metadata=json.loads((output/'collection.json').read_text())
    metadata.update(saved_count=count,completed=count==args.count,stop_reason=stop_reason)
    atomic_json(output/'collection.json',metadata)
    print(f'Stopped: {count}/{args.count} saved, {candidate_count} candidates, {review_count} needs_review, {duplicates} duplicates skipped.')
    print('No training labels created. Run vision/review_yolo_camera.py before training.')
    return manifest
