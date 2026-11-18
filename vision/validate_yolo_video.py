"""Record actual consecutive-frame YOLO safety-gate checks. Never runs/changes CNN.
Use a camera index or a real recorded video. Fixed confidence .5 and 3-frame IoU .8.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from mcp_yolo_gate import PanelGate,iou,validate_detector
from yolo_auto_collection import predict_candidate,atomic_json
from yolo_gate_diagnostics import explain
from yolo_camera_data import fresh_output


def check_readouts(frame,panel,detector):
    x1,y1,x2,y2=map(int,panel)
    local=detector(frame[y1:y2,x1:x2])
    if set(local)!={'hdg','alt'}:return {},'READOUTS_MISSING_OR_AMBIGUOUS'
    for x,y,w,h in local.values():
        if min(x,y)<0 or min(w,h)<=0 or x+w>x2-x1 or y+h>y2-y1:
            return {},'READOUT_OUTSIDE_PANEL'
    return {k:(b[0]+x1,b[1]+y1,b[2],b[3]) for k,b in local.items()},None


def run(args,*,model=None,readout_detector=None):
    import cv2
    if not args.weights.is_file():raise ValueError('Missing MCP detector weights')
    output=fresh_output(args.output,[args.weights])
    if model is None:
        from ultralytics import YOLO
        model=YOLO(str(args.weights))
    validate_detector(model)
    if readout_detector is None:
        from auto_detect_mcp import detect_readouts
        readout_detector=detect_readouts
    gate=PanelGate() # Keep the deployed confidence=.5, stable_frames=3 and IoU=.8.
    cap=cv2.VideoCapture(int(args.source) if args.source.isdecimal() else args.source)
    if not cap.isOpened():cap.release();raise ValueError('Cannot open camera/video')
    output.mkdir(parents=True);counts=Counter();index=0;spatial_count=0;temporal_count=0;eligible_count=0
    before=hashlib.sha256(args.weights.read_bytes()).hexdigest();reason='MAX_FRAMES'
    failure_saved=0; failure_limit=getattr(args,'save_failure_frames',0)
    fields=['frame','read_at_utc','source_msec','score','box','spatial_pass','spatial_reason',
        'previous_box_iou','consecutive_valid_frames','three_frame_pass','readout_reason','readouts',
        'eligible_after_all_checks','cnn_forwarded']
    try:
        with (output/'frames.csv').open('w',newline='',encoding='utf-8') as fp:
            writer=csv.DictWriter(fp,fieldnames=fields);writer.writeheader()
            while index<args.max_frames:
                ok,frame=cap.read()
                if not ok:reason='CAMERA_READ_FAILED_OR_VIDEO_ENDED';break
                at=datetime.now(timezone.utc).isoformat();previous=gate.previous
                proposal=predict_candidate(model,frame,gate,device=args.device,imgsz=args.imgsz)
                spatial=explain(proposal['detections'],frame.shape[1],frame.shape[0])
                temporal=proposal['category']=='candidates';readouts={};readout_reason='PANEL_GATE_NOT_PASSED'
                if temporal:
                    readouts,readout_reason=check_readouts(frame,proposal['proposed_box'],readout_detector)
                eligible=temporal and set(readouts)=={'hdg','alt'} and readout_reason is None
                current_reason=readout_reason if temporal and not eligible else proposal['reason']
                counts[current_reason or 'ELIGIBLE']+=1;index+=1
                spatial_count+=spatial['accepted'];temporal_count+=temporal;eligible_count+=eligible
                writer.writerow(dict(frame=index,read_at_utc=at,source_msec=cap.get(cv2.CAP_PROP_POS_MSEC),
                    score=proposal['model_score'],box=json.dumps(proposal['proposed_box']),
                    spatial_pass=spatial['accepted'],spatial_reason=spatial['primary_reason'],
                    previous_box_iou=iou(previous,proposal['proposed_box']) if previous and proposal['proposed_box'] else None,
                    consecutive_valid_frames=gate.count,three_frame_pass=temporal,readout_reason=readout_reason,
                    readouts=json.dumps(readouts),eligible_after_all_checks=eligible,cnn_forwarded=False))
                fp.flush()
                if temporal and not eligible and failure_saved<failure_limit:
                    folder=output/'readout_failures';folder.mkdir(exist_ok=True)
                    stem=f'{index:06d}'
                    if not cv2.imwrite(str(folder/f'{stem}.png'),frame):
                        raise OSError('Cannot save diagnostic frame')
                    atomic_json(folder/f'{stem}.json',dict(frame=index,panel=proposal['proposed_box'],
                        reason=readout_reason,score=proposal['model_score'],readouts=readouts))
                    failure_saved+=1
                if not args.headless:
                    preview=frame.copy()
                    if proposal['proposed_box']:
                        x1,y1,x2,y2=map(int,proposal['proposed_box'])
                        cv2.rectangle(preview,(x1,y1),(x2,y2),(0,220,100) if eligible else (0,180,255),2)
                    cv2.putText(preview,f'frame {index} | valid consecutive {gate.count}/3 | eligible {eligible}',(10,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
                    cv2.putText(preview,str(current_reason),(10,50),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
                    cv2.imshow('YOLO gate validation (no CNN) - Q quit',preview)
                    if cv2.waitKey(1)&255 in (ord('q'),27):reason='USER_QUIT';break
    finally:cap.release();cv2.destroyAllWindows()
    after=hashlib.sha256(args.weights.read_bytes()).hexdigest()
    if before!=after:raise ValueError('Weights changed during validation')
    summary=dict(frame_count=index,spatial_pass_count=spatial_count,three_frame_pass_count=temporal_count,
        eligible_count=eligible_count,spatial_pass_rate=spatial_count/index if index else None,
        three_frame_pass_rate=temporal_count/index if index else None,
        eligible_rate=eligible_count/index if index else None,reasons=dict(counts),policy=gate.policy(),
        source=args.source,stopped_reason=reason,weights_sha256=before,cnn_forwarded=False,
        readout_failure_frames_saved=failure_saved,
        limitation='Consecutive frame policy/readout localization only; no GT panel accuracy or CNN accuracy is inferred.')
    atomic_json(output/'summary.json',summary);print(json.dumps(summary,indent=2));return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='0')
    p.add_argument('--weights',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--device',default='mps')
    p.add_argument('--imgsz',type=int,default=960)
    p.add_argument('--max-frames',type=int,default=300)
    p.add_argument('--headless',action='store_true')
    p.add_argument('--save-failure-frames',type=int,default=0,help='Save at most N original frames and panel metadata when stable panel readout localization fails')
    args=p.parse_args()
    if args.max_frames<1 or args.imgsz<32 or args.save_failure_frames<0:p.error('Invalid frame count/imgsz')
    try:run(args)
    except (ValueError,OSError) as exc:p.error(str(exc))

if __name__=='__main__':main()
