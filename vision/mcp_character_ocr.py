"""Image-only glyph segmentation + shared CNN. No cockpit state or labels in inference."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageOps
import torch
from torch import nn
try:from .preprocess_mcp_ocr import amber_mask
except ImportError:from preprocess_mcp_ocr import amber_mask

LEGACY_PREPROCESSING='amber_components_glyph_v1'
PREPROCESSING='amber_components_glyph_v2_stretch'
BORDER_PREPROCESSING='amber_components_glyph_v3_border_reject'
ARTIFACT_PREPROCESSING='amber_components_glyph_v4_components'

def segment(image,kind,preprocessing=PREPROCESSING):
    if preprocessing not in (PREPROCESSING,LEGACY_PREPROCESSING,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING):raise ValueError("Unknown glyph normalization")
    if kind not in ('hdg','alt'):raise ValueError('Unknown kind')
    n=3 if kind=='hdg' else 5
    image=image.convert('RGB');mask=amber_mask(image).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
    components=[s for s in stats[1:] if s[cv2.CC_STAT_AREA]>=3]
    if not components:return None
    tallest=max(s[cv2.CC_STAT_HEIGHT] for s in components)
    # Thin horizontal artifacts cannot be digits. No value/template lookup.
    keep=[i for i in range(1,count) if stats[i,cv2.CC_STAT_AREA]>=3 and stats[i,cv2.CC_STAT_HEIGHT]>=max(4,tallest*.5)]
    if preprocessing in (BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING):
        # Very narrow, tall panel edges are not glyphs. Missing actual digits
        # still fail the exact glyph-count check below; never reconstruct them.
        keep=[i for i in keep if stats[i,cv2.CC_STAT_WIDTH]>=max(2,stats[i,cv2.CC_STAT_HEIGHT]*.06)]
    if preprocessing==ARTIFACT_PREPROCESSING and keep:
        typical=float(np.median([stats[i,cv2.CC_STAT_WIDTH] for i in keep]))
        keep=[i for i in keep if stats[i,cv2.CC_STAT_WIDTH]>=max(2,typical*.35)]
    cleaned=np.isin(labels,keep)
    if not cleaned.any():return None
    xs=np.flatnonzero(cleaned.sum(0)>0)
    groups=np.split(xs,np.where(np.diff(xs)>1)[0]+1)
    if len(groups)!=n and preprocessing==ARTIFACT_PREPROCESSING and len(keep)==n:
        ordered=sorted(keep,key=lambda i:stats[i,cv2.CC_STAT_LEFT])
        centers=[stats[i,cv2.CC_STAT_TOP]+stats[i,cv2.CC_STAT_HEIGHT]/2 for i in ordered]
        if max(centers)-min(centers)<=tallest*.35:
            groups=[np.arange(stats[i,cv2.CC_STAT_LEFT],stats[i,cv2.CC_STAT_LEFT]+stats[i,cv2.CC_STAT_WIDTH]) for i in ordered]
    if len(groups)!=n:return None # Never guess missing/merged glyphs.
    glyphs=[];boxes=[]
    for group in groups:
        x1,x2=int(group[0]),int(group[-1])+1
        ys=np.flatnonzero(cleaned[:,x1:x2].sum(1))
        y1,y2=int(ys[0]),int(ys[-1])+1
        if y2-y1<4:return None
        # Remove non-digit components inside each slice as well.
        rgb=np.asarray(image).copy();rgb[~cleaned]=(12,14,16)
        patch=Image.fromarray(rgb[y1:y2,x1:x2]).convert('L')
        patch=(ImageOps.contain(patch,(24,28),Image.Resampling.BILINEAR) if preprocessing==LEGACY_PREPROCESSING else patch.resize((24,28),Image.Resampling.BILINEAR))
        canvas=Image.new('L',(32,32),14);canvas.paste(patch,((32-patch.width)//2,(32-patch.height)//2))
        glyphs.append(canvas);boxes.append([x1,y1,x2,y2])
    return glyphs,boxes

class CharacterCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features=nn.Sequential(nn.Conv2d(1,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(32,64,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(64,96,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d((4,4)))
        self.head=nn.Sequential(nn.Flatten(),nn.Linear(96*4*4,128),nn.ReLU(),nn.Linear(128,10))
    def forward(self,x):return self.head(self.features(x))

def tensor(glyphs):
    return torch.from_numpy(np.stack([np.asarray(im,dtype=np.float32) for im in glyphs]).copy())[:,None]/255.

class CharacterOCR:
    def __init__(self,checkpoint,device='cpu'):
        self.device=device
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        self.preprocessing=saved.get('preprocessing')
        if self.preprocessing not in (PREPROCESSING,LEGACY_PREPROCESSING,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING):raise ValueError('Character preprocessing mismatch')
        self.model=CharacterCNN().to(device);self.model.load_state_dict(saved['model']);self.model.eval()
    def infer_aligned(self,image,kind):
        result=segment(image,kind,self.preprocessing)
        if result is None:return dict(value=None,raw_value=None,model_score=None,reason='GLYPH_SEGMENTATION_FAILED')
        with torch.inference_mode():probs=self.model(tensor(result[0]).to(self.device)).softmax(-1).cpu()
        text=''.join(map(str,probs.argmax(-1).tolist()));score=float(probs.max(-1).values.min())
        reason='LOW_MODEL_SCORE' if score<.75 else ('OUT_OF_RANGE' if kind=='hdg' and int(text)>359 else None)
        return dict(value=text if reason is None else None,raw_value=text,model_score=score,reason=reason,glyph_boxes=result[1])
