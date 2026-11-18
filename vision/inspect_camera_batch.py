"""Inspect webcam OCR batch labels and generate a visual contact sheet.

python vision/inspect_camera_batch.py --data vision/data/camera_batches/batch_002
"""
import argparse
import csv
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--output",type=Path)
    p.add_argument("--samples",type=int,default=40)
    args=p.parse_args()
    from PIL import Image, ImageDraw
    with (args.data/"labels.csv").open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    if not rows:
        p.error("No labels found")
    errors=[]
    counts=Counter()
    for row in rows:
        kind,text=row["kind"],row["text"]
        expected={"hdg":3,"alt":5}.get(kind)
        if expected is None or len(text)!=expected or not text.isascii() or not text.isdigit():
            errors.append(f"Invalid label: {row}")
        rel=Path(row["image_path"])
        if rel.is_absolute() or ".." in rel.parts or not (args.data/rel).is_file():
            errors.append(f"Missing/unsafe image: {rel}")
        counts[(kind,text)]+=1
    print(f"Total images: {len(rows)}")
    for (kind,text),n in sorted(counts.items()):
        print(f"{kind.upper()} {text}: {n}")
    if errors:
        for error in errors[:30]:print("ERROR:",error)
        raise SystemExit(1)
    selected=[]
    for kind in ("hdg","alt"):
        candidates=[r for r in rows if r["kind"]==kind]
        step=max(1,len(candidates)//max(1,args.samples//2))
        selected.extend(candidates[::step][:args.samples//2])
    w,h=430,94
    sheet=Image.new("RGB",(w,h*len(selected)),"#202020")
    draw=ImageDraw.Draw(sheet)
    for i,row in enumerate(selected):
        with Image.open(args.data/row["image_path"]) as f:
            im=f.convert("RGB")
        im.thumbnail((235,75))
        sheet.paste(im,(8,i*h+10))
        draw.text((255,i*h+25),f'{row["kind"].upper()}  {row["text"]}',fill="white")
    output=args.output or args.data/"inspection_contact_sheet.png"
    output.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(output)
    print(f"Inspection sheet: {output}")
    print("Image contents cannot be validated from labels alone; inspect sheet before training.")
if __name__=="__main__":main()
