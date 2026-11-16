"""Current-frame regions for AUTO and bounded panel translation for MANUAL.

Automatic localization uses current image evidence only. Manual matching uses
panel pixels outside the digit windows and does not claim scale/rotation recovery.
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


def regions_changed(previous, current):
    """Large geometric jumps must start a fresh three-frame sequence."""
    if not previous:
        return True
    for field in ('ALT', 'HDG'):
        a, b = previous[field], current[field]
        aw, ah = a[2]-a[0], a[3]-a[1]
        bw, bh = b[2]-b[0], b[3]-b[1]
        if not (.8 <= bw/aw <= 1.25 and .8 <= bh/ah <= 1.25):
            return True
        if abs((a[0]+a[2]-b[0]-b[2])/2) > max(10, aw*.5) or abs((a[1]+a[3]-b[1]-b[3])/2) > max(10, ah*.5):
            return True
    return False


def follow_regions(image, session):
    """AUTO re-detects from each image; MANUAL follows the last valid panel."""
    previous = session['rois']
    if session.get('method') == 'AUTO':
        from vision.yolo_cnn_runtime import locate_windows
        found = locate_windows(image)
        rois = ({'ALT': list(found['alt']), 'HDG': list(found['hdg'])}
                if found and set(found) == {'alt', 'hdg'} else None)
    else:
        shift = locate(image, session['tracked'])
        rois = ({field: [box[0]+shift[0], box[1]+shift[1], box[2]+shift[0], box[3]+shift[1]]
                 for field, box in previous.items()} if shift is not None else None)
    if rois and any(not (0 <= r[0] < r[2] <= image.width and 0 <= r[1] < r[3] <= image.height)
                    for r in rois.values()):
        rois = None
    if not rois:
        session['stable'].reset()
        session['tracking_lost'] = True
        return None
    if session.pop('tracking_lost', False) or regions_changed(previous, rois):
        session['stable'].reset()
    session['rois'] = rois
    session['size'] = image.size
    if session.get('method') != 'AUTO':
        session['tracked'] = reference(image, rois)
    return rois
