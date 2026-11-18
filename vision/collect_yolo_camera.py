"""Collect MCP panels manually or stage unverified auto-capture proposals.
Auto mode: --auto-interval 2 --yolo-weights <MCP best.pt>; review every image before training.
SPACE: freeze + drag full panel + Enter to accept. N: change condition note. Q: quit.
A complete session belongs to one split. Never derive labels from predictions.
"""
import math
import argparse
import csv
import json
import time
from pathlib import Path
from yolo_camera_data import FIELDS, image_hash, write_yaml, fresh_output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='0')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--session',required=True)
    p.add_argument('--split',choices=('train','val','test'),required=True)
    p.add_argument('--count',type=int,default=40)
    p.add_argument('--min-interval',type=float,default=2)
    p.add_argument('--condition',default='distance-angle-light-reflection: operator notes')
    p.add_argument('--auto-interval',type=float,default=0,help='Seconds between auto captures; 0 keeps manual SPACE/drag mode')
    p.add_argument('--yolo-weights',type=Path,help='Existing single-class MCP YOLO best.pt; required in auto mode')
    p.add_argument('--yolo-conf',type=float,default=.5)
    p.add_argument('--yolo-stable-frames',type=int,default=3)
    p.add_argument('--yolo-imgsz',type=int,default=960)
    p.add_argument('--yolo-device',default='cpu',help='cpu, mps, or CUDA index')
    p.add_argument('--dedup-distance',type=float,default=.015,help='RGB thumbnail MAD threshold in [0,1], auto mode only')
    p.add_argument('--capture-only',action='store_true',help='Auto-save raw images without loading YOLO or showing proposals; use for a new blind final-test session')
    args=p.parse_args()
    if args.capture_only and args.auto_interval<=0:p.error('--capture-only requires --auto-interval > 0')
    if not math.isfinite(args.auto_interval) or args.auto_interval<0 or not math.isfinite(args.min_interval):p.error('Intervals must be finite and nonnegative')
    if not 0<=args.dedup_distance<=1 or not .001<=args.yolo_conf<=1 or args.yolo_stable_frames<1 or args.yolo_imgsz<32:p.error('Invalid YOLO/dedup configuration')
    if not 1<=args.count<=200 or args.min_interval<1 or not args.session.strip():p.error('Invalid count/interval/session')
    try:output=fresh_output(args.output,[])
    except ValueError as exc:p.error(str(exc))
    if args.auto_interval>0:
        from yolo_auto_collection import collect_auto
        try:collect_auto(args,output)
        except (ValueError,OSError) as exc:p.error(str(exc))
        return
    import cv2
    from PIL import Image
    try:from .label_mcp import yolo_bbox
    except ImportError:from label_mcp import yolo_bbox
    cap=cv2.VideoCapture(int(args.source) if args.source.isdecimal() else args.source)
    if not cap.isOpened():p.error('Cannot open camera')
    output.mkdir(parents=True)
    (output/'collection.json').write_text(json.dumps(dict(session=args.session,split=args.split,source=args.source),indent=2))
    window='Full MCP labels: SPACE freeze/box, N condition, Q quit'
    count=0;last=-float('inf');seen=set()
    try:
        with (output/'manifest.csv').open('w',newline='',encoding='utf-8') as fp:
            writer=csv.DictWriter(fp,fieldnames=FIELDS);writer.writeheader();fp.flush()
            while count<args.count:
                ok,frame=cap.read()
                if not ok:break
                preview=frame.copy()
                cv2.putText(preview,f'{args.split} {count}/{args.count} | SPACE box full MCP | Q quit',
                    (10,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
                cv2.imshow(window,preview);key=cv2.waitKey(20)&255
                if key in (ord('q'),27):break
                if key==ord('n'):
                    args.condition=input('Distance/angle/brightness/reflection notes: ').strip();continue
                if key!=32 or time.monotonic()-last<args.min_interval:continue
                h,w=frame.shape[:2]
                x,y,bw,bh=map(int,cv2.selectROI(window,frame,showCrosshair=True,fromCenter=False))
                if not bw or not bh:continue
                box=yolo_bbox(x,y,bw,bh,w,h)
                image_rel=f'images/{args.split}/{count:05d}.png';label_rel=f'labels/{args.split}/{count:05d}.txt'
                image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                import hashlib
                digest=hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
                if digest in seen:print('Rejected duplicate frame');continue
                for rel in (image_rel,label_rel):(output/rel).parent.mkdir(parents=True,exist_ok=True)
                image.save(output/image_rel)
                (output/label_rel).write_text('0 '+' '.join(f'{v:.8f}' for v in box)+'\n')
                writer.writerow(dict(source_path=f'{args.session}/{count:05d}',image_path=image_rel,
                    label_path=label_rel,session_id=args.session,split=args.split,x=x,y=y,width=bw,height=bh,condition=args.condition))
                fp.flush();seen.add(digest);count+=1;last=time.monotonic()
                print(f'Saved {count}/{args.count}: include all MCP controls, exclude surrounding instrument panels')
    finally:cap.release();cv2.destroyAllWindows()
    write_yaml(output)
    print(f'Saved {count} manually labeled images at {output}')

if __name__=='__main__':main()
