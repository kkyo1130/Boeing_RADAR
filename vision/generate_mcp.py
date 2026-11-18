"""Generate original MCP-inspired 7-segment ALT/HDG image pairs.

Not an exact reproduction of Boeing hardware; synthetic labels are ground truth.
Creates images and train/val/test CSVs, grouping augmented views by value pair.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

SEGMENTS = {
    "0": "ab cdef".replace(" ", ""), "1": "bc", "2": "abged",
    "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgecd",
    "7": "abc", "8": "abcdefg", "9": "abcdfg",
}
# Horizontal a/g/d and vertical b/c/e/f
def draw_digit(draw, x, y, digit, scale, active, inactive):
    s = scale
    t = max(2, round(s * .17))
    w, h = 2 * s, 4 * s
    segments = {
        "a": (x+t,y,x+w-t,y+t),
        "g": (x+t,y+h//2-t//2,x+w-t,y+h//2+t//2),
        "d": (x+t,y+h-t,x+w-t,y+h),
        "f": (x,y+t,x+t,y+h//2),
        "b": (x+w-t,y+t,x+w,y+h//2),
        "e": (x,y+h//2,x+t,y+h-t),
        "c": (x+w-t,y+h//2,x+w,y+h-t),
    }
    for name, coords in segments.items():
        draw.rounded_rectangle(coords, radius=max(1,t//3),
                               fill=active if name in SEGMENTS[digit] else inactive)

def render(altitude, heading, rng):
    width, height = 850, 190
    background = rng.randint(6, 25)
    img = Image.new("RGB", (width,height), (background,background+2,background+4))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12,12,838,178), radius=13, fill=(24,27,31), outline=(70,74,78), width=3)
    d.rounded_rectangle((34,28,338,159), radius=6, fill=(3,6,8), outline=(60,63,65), width=3)
    d.rounded_rectangle((418,28,818,159), radius=6, fill=(3,6,8), outline=(60,63,65), width=3)
    brightness = rng.randint(165,255)
    active = (brightness, min(255,int(brightness*.74)), rng.randint(12,45))
    inactive = (23,17,11)
    for start, value, scale, step in [(54, f"{heading:03d}", 24, 89),
                                      (437, f"{altitude:05d}", 23, 72)]:
        for i, digit in enumerate(value):
            draw_digit(d,start+i*step,45,digit,scale,active,inactive)
    # Camera artifacts; preserve digits while perturbing the overall display.
    if rng.random() < .85:
        img = img.rotate(rng.uniform(-5,5), resample=Image.Resampling.BICUBIC,
                         fillcolor=(background,background+2,background+4))
    if rng.random() < .6:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(.1,1.1)))
    return img

def split_of(pair, seed):
    value = int.from_bytes(hashlib.sha256(f"{seed}:{pair}".encode()).digest()[:8],"big") / 2**64
    return "train" if value < .8 else "val" if value < .9 else "test"

def generate(output, count=20000, seed=42):
    if count < 1:
        raise ValueError("count must be positive")
    output.mkdir(parents=True,exist_ok=True)
    rng = random.Random(seed)
    # Diverse unique pairs; keep all views of the same pair in one partition.
    with (output/"labels.csv").open("w",newline="",encoding="utf-8") as all_f, \
         (output/"train.csv").open("w",newline="",encoding="utf-8") as train_f, \
         (output/"val.csv").open("w",newline="",encoding="utf-8") as val_f, \
         (output/"test.csv").open("w",newline="",encoding="utf-8") as test_f:
        fields=["filename","altitude","heading","original_id","session_id","source"]
        writers={name:csv.DictWriter(f,fieldnames=fields) for name,f in [
            ("all",all_f),("train",train_f),("val",val_f),("test",test_f)]}
        for writer in writers.values(): writer.writeheader()
        for index in range(count):
            altitude=rng.randrange(0,50001,100)
            heading=rng.randrange(360)
            pair=f"{altitude:05d}_{heading:03d}"
            filename=f"mcp_{index:06d}.png"
            render(altitude,heading,rng).save(output/filename)
            row=dict(filename=filename,altitude=f"{altitude:05d}",heading=f"{heading:03d}",
                     original_id=pair,session_id=pair,source="synthetic_mcp_inspired")
            writers["all"].writerow(row)
            writers[split_of(pair,seed)].writerow(row)
    print(f"Generated {count} synthetic MCP-inspired ALT/HDG pairs in {output}")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=Path("vision/data/boeing_737/mcp_synthetic"))
    p.add_argument("--count",type=int,default=20000)
    p.add_argument("--seed",type=int,default=42)
    args=p.parse_args()
    generate(args.output,args.count,args.seed)
