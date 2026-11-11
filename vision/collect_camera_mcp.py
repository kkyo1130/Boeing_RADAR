"""Capture 300 automatically detected webcam MCP pairs with operator-confirmed labels.

Example:
 python vision/collect_camera_mcp.py --source 0 --output vision/data/camera_batches/batch_001 --pairs 150
Every accepted frame produces 2 OCR crops (HDG and ALT).
Automatically saves one pair every 0.6 seconds (adjust --auto-interval).\nPress SPACE for manual save, N to update labels, Q to quit.
Only save when the physical display actually matches the entered labels.
"""
import argparse
import csv
import time
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
    p.add_argument("--yolo-conf",type=float,default=0.25)
    args=p.parse_args()
    import cv2
    from PIL import Image
    from auto_detect_mcp import detect_readouts
    from camera_digit_preprocess import camera_to_amber
    from preprocess_mcp_ocr import align
    if args.auto_interval < 0:
        p.error("--auto-interval must be >= 0")
    if args.pairs < 1:
        p.error("--pairs must be positive")
    def validate(h,a):
        if not (len(h)==3 and h.isascii() and h.isdigit() and len(a)==5 and a.isascii() and a.isdigit()):
            raise ValueError("HDG must be 3 digits and ALT must be 5 digits")
    validate(args.hdg,args.alt)
    yolo = None
    if args.yolo_weights:
        if not args.yolo_weights.is_file():
            p.error(f"Missing YOLO weights: {args.yolo_weights}")
        from ultralytics import YOLO
        yolo = YOLO(str(args.yolo_weights))
    source=int(args.source) if args.source.isdecimal() else args.source
    cap=cv2.VideoCapture(source)
    if not cap.isOpened():
        p.error("Cannot open camera")
    args.output.mkdir(parents=True, exist_ok=True)
    fields=["image_path","kind","text","split","session_id","source_image"]
    labels=args.output/"labels.csv"
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
        if any(args.output.iterdir()):
            p.error("Existing folder has no labels.csv; refusing to overwrite")
        count = 0
    print(f"Resuming at {count}/{args.pairs} pairs")
    if count >= args.pairs:
        print("Batch already complete.")
        cap.release()
        return
    last_saved = 0.0
    try:
        with labels.open("a",newline="",encoding="utf-8") as fp:
            writer=csv.DictWriter(fp,fieldnames=fields)
            if not existing:
                writer.writeheader()
            while count<args.pairs:
                ok,frame=cap.read()
                if not ok:
                    break
                if yolo is None:
                    boxes=detect_readouts(frame)
                else:
                    boxes={}
                    results=yolo.predict(frame,conf=args.yolo_conf,verbose=False)
                    candidates=results[0].boxes
                    if candidates is not None and len(candidates):
                        idx=int(candidates.conf.argmax().item())
                        x1,y1,x2,y2=map(int,candidates.xyxy[idx].tolist())
                        fh,fw=frame.shape[:2]
                        x1,y1,x2,y2=max(0,x1),max(0,y1),min(fw,x2),min(fh,y2)
                        if x2>x1 and y2>y1:
                            local=detect_readouts(frame[y1:y2,x1:x2])
                            boxes={kind:(box[0]+x1,box[1]+y1,box[2],box[3]) for kind,box in local.items()}
                preview=frame.copy()
                for kind,color in (("hdg",(0,230,255)),("alt",(255,190,40))):
                    if kind in boxes:
                        x,y,w,h=boxes[kind]
                        cv2.rectangle(preview,(x,y),(x+w,y+h),color,2)
                cv2.putText(preview,f"HDG {args.hdg} ALT {args.alt}  {count}/{args.pairs} pairs", (15,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
                cv2.putText(preview,"AUTO capture | SPACE save | N labels/pause | Q quit",(15,65),cv2.FONT_HERSHEY_SIMPLEX,.58,(255,255,255),2)
                cv2.imshow("Camera OCR data collection",preview)
                key=cv2.waitKey(20)&255
                if key in (ord("q"),27):
                    break
                if key==ord("n"):
                    print("Set actual displayed values, not OCR predictions.")
                    try:
                        h=input("HDG (3 digits): ").strip()
                        a=input("ALT (5 digits): ").strip()
                        validate(h,a)
                        args.hdg,args.alt=h,a
                    except (ValueError,EOFError) as exc:
                        print("Invalid labels; keeping previous values:",exc)
                    last_saved=time.monotonic()
                    continue
                now = time.monotonic()
                should_capture = key == 32 or (args.auto_interval > 0 and now - last_saved >= args.auto_interval)
                if not should_capture or set(boxes)!={"hdg","alt"}:
                    continue
                crops={}
                for kind in ("hdg","alt"):
                    x,y,w,h=boxes[kind]
                    image=Image.fromarray(cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2RGB))
                    aligned=align(camera_to_amber(image),kind)
                    if aligned is None:
                        break
                    crops[kind]=aligned
                if len(crops)!=2:
                    print("Rejected: preprocessing could not locate digits")
                    continue
                # Group pairs by capture session; never place near-identical frames in test.
                session=f"camera_{count//15:04d}"
                # This collection is for training; keep a separate unseen camera test set.
                for kind in ("hdg","alt"):
                    rel=f"train/{kind}/{count:05d}.png"
                    dest=args.output/rel
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    crops[kind].save(dest)
                    writer.writerow(dict(image_path=rel,kind=kind,text=getattr(args,kind),
                                         split="train",session_id=session,source_image=f"webcam_{count:05d}"))
                fp.flush()
                count+=1
                last_saved = time.monotonic()
                print(f"Saved {count}/{args.pairs} pairs, {2*count} crops")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"Saved {2*count} OCR crops at {args.output}. Verify labels before training.")

if __name__=="__main__":
    main()
