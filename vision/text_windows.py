"""Optional local Apple Vision localization by observed labels and digit spans."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def labelled_regions(rows, size):
    width, height = size
    usable = [r for r in rows if isinstance(r, dict) and isinstance(r.get('text'), str)
              and isinstance(r.get('score'), (int, float)) and .75 <= r['score'] <= 1
              and isinstance(r.get('box'), list) and len(r['box']) == 4
              and all(isinstance(n, (int, float)) and 0 <= n <= 1 for n in r['box'])
              and r['box'][0] < r['box'][2] and r['box'][1] < r['box'][3]]
    anchors={}
    found={}
    missing=[]
    for key, digits in [('hdg', 3), ('alt', 5)]:
        labels = [r for r in usable if r['text'].strip().upper() == key.upper()]
        if len(labels) != 1: return None
        lx, ly, lr, lb = labels[0]['box']; lh = lb - ly
        anchors[key]=labels[0]['box']
        candidates = []
        nearby_text=[]
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('box'),list) or len(row['box'])!=4:continue
            x,y,r,b=row['box']
            if not all(isinstance(n,(int,float)) and 0<=n<=1 for n in (x,y,r,b)):continue
            if not (lb - lh * .2 <= y <= lb + lh * 2 and
                    abs((x+r-lx-lr)/2) <= max(lr-lx, r-x)*.55): continue
            nearby_text.append(row)
            if row not in usable or not re.fullmatch(r'[0-9]{%d}' % digits,row['text'].strip()):continue
            if key=='hdg' and int(row['text'])>359:continue
            candidates.append(row)
        if len(candidates)>1:return None
        if candidates:found[key]=candidates[0]['box']
        elif nearby_text:return None  # Do not override conflicting/weak OCR evidence.
        else:missing.append(key)
    if missing:
        if len(missing)!=1 or len(found)!=1:return None
        key=missing[0];other=next(iter(found))
        hdg,alt=anchors['hdg'],anchors['alt']
        gap=(alt[0]+alt[2]-hdg[0]-hdg[2])/2
        hh,ah=hdg[3]-hdg[1],alt[3]-alt[1]
        if not (gap>0 and .7<ah/hh<1.4 and abs((alt[1]+alt[3]-hdg[1]-hdg[3])/2)<max(hh,ah)*1.5
                and 1.3*(hdg[2]-hdg[0])<gap<6*(hdg[2]-hdg[0])):return None
        anchor=anchors[key];reference=anchors[other];numeric=found[other]
        ratio=(anchor[3]-anchor[1])/(reference[3]-reference[1])
        top=anchor[3]+(numeric[1]-reference[3])*ratio
        bottom=top+(numeric[3]-numeric[1])*ratio
        center=(anchor[0]+anchor[2])/2
        found[key]=[center-gap*.43,top,center+gap*.43,bottom]
    result={}
    for key,(x,y,r,b) in found.items():
        pad=(b-y)*.12
        result[key]=[max(0,round((x-pad)*width)),max(0,round((y-pad)*height)),
                     min(width,round((r+pad)*width)),min(height,round((b+pad)*height))]
    return result


def locate_text_windows(image):
    binary = os.getenv('RADAR_REGION_OCR_BINARY')
    if not binary: return None
    try:
        with tempfile.TemporaryDirectory(prefix='radar-regions-') as folder:
            path = Path(folder)/'frame.png'; image.save(path)
            output = subprocess.run([binary, str(path)], check=True, capture_output=True, text=True, timeout=2)
        return labelled_regions(json.loads(output.stdout), image.size)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def read_crop(image, kind):
    binary = os.getenv('RADAR_OCR_BINARY')
    if not binary: return None
    try:
        with tempfile.TemporaryDirectory(prefix='radar-field-') as folder:
            path=Path(folder)/'field.png'; image.save(path)
            output=subprocess.run([binary,str(path)],check=True,capture_output=True,text=True,timeout=2)
        rows=json.loads(output.stdout)
        if len(rows)!=1: return None
        row=rows[0]; text=row['text'].strip(); score=row['score']
        if not re.fullmatch(r'[0-9]{%d}' % (3 if kind=='hdg' else 5),text): return None
        if not isinstance(score,(int,float)) or not .75 <= score <= 1: return None
        if kind=='hdg' and int(text)>359: return None
        return dict(value=text,model_score=score,reason=None,source='apple_vision_fallback')
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        return None
