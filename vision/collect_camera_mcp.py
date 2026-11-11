"""Capture 300 automatically detected webcam MCP pairs with operator-confirmed labels.

Example:
 python vision/collect_camera_mcp.py --source 0 --output vision/data/camera_batches/batch_001 --pairs 150
Every accepted frame produces 2 OCR crops (HDG and ALT).
Press SPACE to save the current pair, N to update labels, Q to quit.
Only save when the physical display actually matches the entered labels.
"""
import argparse
import csv
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",default="0")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--pairs",type=int,default=150)
    p.add_argument("--hdg",default="270")
    p.add_argument("--alt",default="03000")
    args=p.parse_args()
    import cv2
    from PIL import Image
    from auto_detect_mcp import detect_readouts
    from camera_digit_preprocess import camera_to_amber
    from preprocess_mcp_ocr import align
    if args.output.exists() and any(args.output.iterdir()):
        p.error("Output must be a new empty directory (avoid accidental overwrite)")
    if args.pairs < 1:
        p.error("--pairs must be positive")
    def validate(h,a):
        if not (len(h)==3 and h.isascii() and h.isdigit() and len(a)==5 and a.isascii() and a.isdigit()):
            raise ValueError("HDG must be 3 digits and ALT must be 5 digits")
    validate(args.hdg,args.alt)
    source=int(args.source) if args.source.isdecimal() else args.source
    cap=cv2.VideoCapture(source)
    if not cap.isOpened():
        p.error("Cannot open camera")
    args.output.mkdir(parents=True)
    fields=["image_path","kind","text","split","session_id","source_image"]
    labels=args.output/"labels.csv"
    count=0
    try:
        with labels.open("w",newline="",encoding="utf-8") as fp:
            writer=csv.DictWriter(fp,fieldnames=fields)
            writer.writeheader()
            while count<args.pairs:
                ok,frame=cap.read()
                if not ok:
                    break
                boxes=detect_readouts(frame)
                preview=frame.copy()
                for kind,color in (("hdg",(0,230,255)),("alt",(255,190,40))):
                    if kind in boxes:
                        x,y,w,h=boxes[kind]
                        cv2.rectangle(preview,(x,y),(x+w,y+h),color,2)
                cv2.putText(preview,f"HDG {args.hdg} ALT {args.alt}  {count}/{args.pairs} pairs", (15,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
                cv2.putText(preview,"SPACE save | N labels | Q quit",(15,65),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
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
                if key!=32 or set(boxes)!={"hdg","alt"}:
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
                print(f"Saved {count}/{args.pairs} pairs, {2*count} crops")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"Saved {2*count} OCR crops at {args.output}. Verify labels before training.")

if __name__=="__main__":
    main()
