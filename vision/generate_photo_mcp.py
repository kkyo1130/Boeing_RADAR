"""Labelled photo-derived training augmentation. No synthetic final-test claim."""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
try:
    from .mcp_preprocessing import prepare_camera_crop
    from .camera_effects import camera_effects
except ImportError:
    from mcp_preprocessing import prepare_camera_crop
    from camera_effects import camera_effects

FIELDS=['image_path','source_image','split','kind','text','session_id']

def transformed_box(box, matrix, size):
    x,y,r,b=box
    corners=np.array([[[x,y],[r,y],[r,b],[x,b]]],dtype=np.float32)
    points=cv2.perspectiveTransform(corners,matrix)[0]
    width,height=size
    return [max(0,int(np.floor(points[:,0].min()))),max(0,int(np.floor(points[:,1].min()))),
            min(width,int(np.ceil(points[:,0].max()))),min(height,int(np.ceil(points[:,1].max())))]


def replace_number(image, box, text, font):
    x,y,r,b=box;w,h=r-x,b-y
    patch=np.asarray(image.crop(box));lum=patch.mean(axis=2)
    dark=patch[lum<=np.quantile(lum,.25)]
    background=tuple(int(v) for v in np.median(dark,axis=0))
    layer=Image.new('RGB',(w,h),background)
    glyph=Image.new('L',(1200,300));draw=ImageDraw.Draw(glyph)
    bounds=draw.textbbox((0,0),text,font=font)
    draw.text((-bounds[0],-bounds[1]),text,font=font,fill=255)
    glyph=glyph.crop((0,0,bounds[2]-bounds[0],bounds[3]-bounds[1]))
    glyph=glyph.resize((max(1,round(w*.78)),max(1,round(h*.72))),Image.Resampling.LANCZOS)
    colored=Image.new('RGB',glyph.size,(255,211,135))
    layer.paste(colored,((w-glyph.width)//2,(h-glyph.height)//2),glyph)
    image.paste(layer,(x,y))


def generate(source, rois, output, count=600, seed=42, font_path=None, glare=False):
    if output.exists():raise ValueError('Choose a new output directory')
    font_path=font_path or '/System/Library/Fonts/Supplemental/Courier New Bold.ttf'
    font=ImageFont.truetype(str(font_path),190)
    image=Image.open(source).convert('RGB')
    scale=min(1,1280/image.width);size=(round(image.width*scale),round(image.height*scale));image=image.resize(size)
    boxes={k:[round(n*scale) for n in rois[k]] for k in ('hdg','alt')}
    output.mkdir(parents=True);(output/'previews').mkdir()
    rng=random.Random(seed);rows=[];manifest=[];failures=[]
    width,height=size;corners=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    for index in range(count):
        text={'hdg':f'{rng.randrange(360):03d}','alt':f'{rng.randrange(501)*100:05d}'}
        photo=image.copy()
        for kind in ('hdg','alt'):replace_number(photo,boxes[kind],text[kind],font)
        angle=rng.uniform(-9,9);affine=cv2.getRotationMatrix2D((width/2,height/2),angle,rng.uniform(.90,1.03))
        rotated=cv2.transform(corners[None],affine)[0]
        warped=rotated+np.array([[rng.uniform(-width*.025,width*.025),rng.uniform(-height*.025,height*.025)] for _ in corners],dtype=np.float32)
        matrix=cv2.getPerspectiveTransform(corners,warped.astype(np.float32))
        photo=Image.fromarray(cv2.warpPerspective(np.asarray(photo),matrix,size,borderMode=cv2.BORDER_REFLECT))
        photo=ImageEnhance.Brightness(photo).enhance(rng.uniform(.65,1.25))
        if rng.random()<.35:photo=photo.filter(ImageFilter.GaussianBlur(rng.uniform(.1,.65)))
        effects={}
        if glare:photo,effects=camera_effects(photo,rng)
        projected={k:transformed_box(boxes[k],matrix,size) for k in boxes}
        pair=[]
        for kind in ('hdg','alt'):
            crop=prepare_camera_crop(photo.crop(projected[kind]),kind)
            if crop is None:break
            pair.append((kind,crop))
        if len(pair)!=2:
            failures.append(index);continue
        if index<8:photo.save(output/'previews'/f'{index:04d}.jpg',quality=90)
        for kind,crop in pair:
            rel=f'train/{kind}/{index:05d}.png';(output/rel).parent.mkdir(parents=True,exist_ok=True);crop.save(output/rel)
            rows.append(dict(image_path=rel,source_image=f'photo_{index:05d}',split='train',kind=kind,text=text[kind],session_id='photo_augmented_train_only'))
        manifest.append(dict(index=index,labels=text,boxes=projected,homography=matrix.tolist(),angle=angle,camera_effects=effects))
    with (output/'labels.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    metadata=dict(source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),seed=seed,
                  source_role='consumed_development_photo',requested=count,training_pairs=len(manifest),failed=failures,
                  policy='All derivatives are train only; independent real capture required for final evaluation',samples=manifest)
    (output/'augmentation.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps({k:v for k,v in metadata.items() if k!='samples'}),flush=True)
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--rois',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--count',type=int,default=600);p.add_argument('--seed',type=int,default=42);p.add_argument('--glare',action='store_true');a=p.parse_args()
    if a.count<1:p.error('count must be positive')
    generate(a.source,json.loads(a.rois.read_text()),a.output,a.count,a.seed,glare=a.glare)
