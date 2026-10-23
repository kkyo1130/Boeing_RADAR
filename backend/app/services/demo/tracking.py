"""Bounded translation tracking around manually selected MCP windows.

Uses panel pixels outside the digit windows. Does not use expected values.
No scale/rotation recovery: loss of a sufficiently similar panel means null.
"""
import cv2
import numpy as np


def reference(image,rois):
    gray=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY)
    h,w=gray.shape
    x1=max(0,min(r[0] for r in rois.values())-45);x2=min(w,max(r[2] for r in rois.values())+45)
    y1=max(0,min(r[1] for r in rois.values())-30);y2=min(h,max(r[3] for r in rois.values())+60)
    patch=gray[y1:y2,x1:x2].copy();mask=np.full(patch.shape,255,np.uint8)
    for r in rois.values(): mask[max(0,r[1]-y1-3):min(y2-y1,r[3]-y1+3),max(0,r[0]-x1-3):min(x2-x1,r[2]-x1+3)]=0
    return dict(patch=patch,mask=mask,box=(x1,y1,x2,y2),size=image.size)


def locate(image,ref):
    if image.size!=ref['size']: return None
    gray=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY);h,w=gray.shape
    x1,y1,x2,y2=ref['box'];left=max(0,x1-60);top=max(0,y1-60)
    region=gray[top:min(h,y2+60),left:min(w,x2+60)]
    if np.std(ref['patch'][ref['mask']>0])<10: return None
    scores=cv2.matchTemplate(region,ref['patch'],cv2.TM_CCOEFF_NORMED,mask=ref['mask'])
    scores=np.nan_to_num(scores,nan=-1,posinf=-1,neginf=-1)
    _,value,_,point=cv2.minMaxLoc(scores)
    if value<.8: return None
    dx,dy=point[0]+left-x1,point[1]+top-y1
    return dx,dy
