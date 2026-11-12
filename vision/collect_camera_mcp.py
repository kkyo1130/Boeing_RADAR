"""Capture synchronized HDG/ALT camera pairs from the selected simulated display.

Use --display-id tablet with /cockpit?display=tablet and a fresh --output folder.
SPACE saves manually; --auto-interval 0 disables automatic saves.
N selects next preset or manual labels; Q exits. No OCR predictions become labels.
"""
import argparse
import csv
import time
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",default="0")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--pairs",type=int,default=150)
    p.add_argument("--auto-interval",type=float,default=0.6,help="Automatically save a pair every N seconds; 0 disables auto capture")
    p.add_argument("--hdg",default="270")
    p.add_argument("--alt",default="03000")
    p.add_argument("--yolo-weights",type=Path,help="Trained MCP YOLO best.pt for panel localization")
    p.add_argument("--yolo-conf",type=float,default=0.5)
    p.add_argument('--sync-url', default='http://127.0.0.1:5173')
    p.add_argument('--display-id', required=True, help='Matches tablet /cockpit?display=ID')
    p.add_argument('--settle-seconds', type=float, default=1.0)
    p.add_argument('--preset-plan', action='store_true', help='8 combinations, 15 pairs each; N advances')
    p.add_argument('--v6-plan', choices=('train','test'), help='Separate 160-pair train or 40-pair held-out test collection')
    p.add_argument('--session-id', help='Physical capture session ID. Use distinct sessions for train and test.')
    p.add_argument('--yolo-imgsz',type=int,default=960)
    p.add_argument('--yolo-stable-frames',type=int,default=3)
    args=p.parse_args()
    from mcp_camera_presets import collection_plan
    try:
        plan, pairs_per_value, split = collection_plan(args.preset_plan,args.v6_plan)
    except ValueError as exc:
        p.error(str(exc))
    if args.v6_plan and (not args.session_id or not all(c.isalnum() or c in '_-' for c in args.session_id)):
        p.error('--v6-plan requires an explicit alphanumeric --session-id')
    if plan:
        args.pairs=len(plan)*pairs_per_value

    from mcp_display_sync import DisplaySync, PRESETS, validate_labels
    if args.settle_seconds < 1:
        p.error('--settle-seconds must be >= 1')

    import cv2
    from PIL import Image
    from auto_detect_mcp import detect_readouts
    from mcp_preprocessing import prepare_camera_crop
    if args.auto_interval < 0:
        p.error("--auto-interval must be >= 0")
    if args.pairs < 1:
        p.error("--pairs must be positive")
    validate = validate_labels
    validate(args.hdg,args.alt)
    sync = DisplaySync(args.sync_url, args.display_id, args.settle_seconds)
    def synchronize():
        try:
            sync.set(args.hdg, args.alt)
            print('Waiting for selected display render ACK and stabilization...')
        except Exception as exc:
            print('SYNC FAILED; capture blocked. Press N to retry:', exc)
    from mcp_yolo_gate import PanelGate, detect_panel_readouts, validate_detector
    gate=PanelGate(args.yolo_conf,args.yolo_stable_frames)
    yolo = None
    if args.yolo_weights:
        if not args.yolo_weights.is_file():
            p.error(f"Missing YOLO weights: {args.yolo_weights}")
        from ultralytics import YOLO
        yolo = YOLO(str(args.yolo_weights))
        validate_detector(yolo)
    source=int(args.source) if args.source.isdecimal() else args.source
    cap=cv2.VideoCapture(source)
    if not cap.isOpened():
        p.error("Cannot open camera")
    args.output.mkdir(parents=True, exist_ok=True)
    fields=["image_path","kind","text","split","session_id","source_image"]
    labels=args.output/"labels.csv"
    metadata=args.output/'collection.json'
    if args.v6_plan:
        expected={'version':1,'plan':'v6','split':split,'session_id':args.session_id,
                  'pairs_per_value':pairs_per_value,'presets':plan,'preprocessing':'camera_amber_align_v1'}
        expected=json.loads(json.dumps(expected))
        if metadata.exists():
            if json.loads(metadata.read_text()) != expected:
                p.error('Collection metadata differs; use a fresh output folder')
        elif any(args.output.iterdir()):
            p.error('v6 collection requires a fresh folder or matching collection metadata')
        else:
            metadata.write_text(json.dumps(expected,indent=2))

    existing = []
    if labels.exists():
        with labels.open(newline="", encoding="utf-8") as fp:
            existing = list(csv.DictReader(fp))
        by_source = {}
        for row in existing:
            rel = Path(row["image_path"])
            if (row.get("kind") not in ("hdg", "alt") or rel.is_absolute()
                    or ".." in rel.parts or not (args.output / rel).is_file()):
                p.error(f"Invalid or missing existing image: {rel}")
            by_source.setdefault(row["source_image"], set()).add(row["kind"])
        if any(kinds != {"hdg", "alt"} for kinds in by_source.values()):
            p.error("Incomplete pair in labels.csv; inspect before resuming")
        count = len(by_source)
    else:
        if any(f != metadata for f in args.output.iterdir()):
            p.error("Existing folder has no labels.csv; refusing to overwrite")
        count = 0
    print(f"Resuming at {count}/{args.pairs} pairs")
    if plan:
        if args.v6_plan and existing:
            from mcp_dataset import validate_dataset
            validate_dataset(args.output,{split},paired=True)
            for i in range(count):
                for row in existing[2*i:2*i+2]:
                    h,a=plan[min(i//pairs_per_value,len(plan)-1)]
                    if row['text'] != (h if row['kind']=='hdg' else a):
                        p.error('Existing labels do not match preset sequence')
        args.hdg,args.alt = plan[min(count//pairs_per_value,len(plan)-1)]
    if count >= args.pairs:
        print("Batch already complete.")
        cap.release()
        return
    synchronize()
    last_saved = 0.0
    try:
        with labels.open("a",newline="",encoding="utf-8") as fp:
            writer=csv.DictWriter(fp,fieldnames=fields)
            if fp.tell() == 0:
                writer.writeheader()
            while count<args.pairs:
                ready = sync.ready()
                # Continuously drain camera frames while blocked; never save an old preview after N.
                ok,frame=cap.read()
                if not ok:
                    break
                if yolo is None:
                    boxes=detect_readouts(frame)
                else:
                    boxes,reason=detect_panel_readouts(yolo,frame,gate,detect_readouts,imgsz=args.yolo_imgsz)
                    if reason:
                        ready=False
                preview=frame.copy()
                for kind,color in (("hdg",(0,230,255)),("alt",(255,190,40))):
                    if kind in boxes:
                        x,y,w,h=boxes[kind]
                        cv2.rectangle(preview,(x,y),(x+w,y+h),color,2)
                cv2.putText(preview,f"HDG {args.hdg} ALT {args.alt}  {count}/{args.pairs} pairs", (15,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
                cv2.putText(preview,f"{'READY' if ready else 'SYNC BLOCKED'} | SPACE save | N labels/next | Q quit",(15,65),cv2.FONT_HERSHEY_SIMPLEX,.58,(255,255,255),2)
                cv2.imshow("Camera OCR data collection",preview)
                key=cv2.waitKey(20)&255
                if key in (ord("q"),27):
                    break
                if key==ord("n"):
                    sync.command = None
                    try:
                        choice=input("Enter=next preset; M=manual; R=retry current: ").strip().lower()
                        if choice == 'r':
                            h,a=args.hdg,args.alt
                        elif choice == '':
                            if plan:
                                h,a=plan[min(count//pairs_per_value,len(plan)-1)]
                            else:
                                index=PRESETS.index((args.hdg,args.alt)) if (args.hdg,args.alt) in PRESETS else -1
                                h,a=PRESETS[(index+1)%len(PRESETS)]
                        else:
                            h=input("HDG (3 digits): ").strip()
                            a=input("ALT (5 digits): ").strip()
                        validate(h,a)
                        if plan and (h,a)!=plan[min(count//pairs_per_value,len(plan)-1)]:
                            raise ValueError('Preset plan requires the current preset combination')
                        args.hdg,args.alt=h,a
                        synchronize()
                    except (ValueError,EOFError) as exc:
                        print("Capture remains blocked:",exc)
                    last_saved=time.monotonic()
                    continue
                now = time.monotonic()
                should_capture = key == 32 or (args.auto_interval > 0 and now - last_saved >= args.auto_interval)
                if plan and (args.hdg,args.alt) != plan[min(count//pairs_per_value,len(plan)-1)]:
                    continue
                if not ready or not should_capture or set(boxes)!={"hdg","alt"}:
                    continue
                crops={}
                for kind in ("hdg","alt"):
                    x,y,w,h=boxes[kind]
                    image=Image.fromarray(cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2RGB))
                    aligned=prepare_camera_crop(image,kind)
                    if aligned is None:
                        break
                    crops[kind]=aligned
                if len(crops)!=2:
                    print("Rejected: preprocessing could not locate digits")
                    continue
                # Recheck after preprocessing: network errors, expired ACK or another command block saving.
                if not sync.ready():
                    continue
                # Group pairs by capture session; never place near-identical frames in test.
                session=args.session_id or f"camera_{count//15:04d}"
                # This collection is for training; keep a separate unseen camera test set.
                if any((args.output/f'{split}/{kind}/{count:05d}.png').exists() for kind in ('hdg','alt')):
                    raise RuntimeError('Unindexed capture files exist; refusing overwrite. Use a new batch.')
                for kind in ("hdg","alt"):
                    rel=f"{split}/{kind}/{count:05d}.png"
                    dest=args.output/rel
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    crops[kind].save(dest)
                    writer.writerow(dict(image_path=rel,kind=kind,text=getattr(args,kind),
                                         split=split,session_id=session,source_image=f"webcam_{count:05d}"))
                fp.flush()
                count+=1
                last_saved = time.monotonic()
                if plan and count % pairs_per_value == 0 and count < args.pairs:
                    sync.command = None
                    print('Combination complete: press N then Enter for next preset.')
                print(f"Saved {count}/{args.pairs} pairs, {2*count} crops")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"Saved {2*count} OCR crops at {args.output}. Verify labels before training.")

if __name__=="__main__":
    main()
