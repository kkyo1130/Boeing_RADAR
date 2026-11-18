"""Conservative MCP glass-window localization within a YOLO-gated panel only."""
import cv2
import numpy as np

def glyph_runs(mask, reject_border=False):
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    candidates=[i for i in range(1,count) if stats[i,cv2.CC_STAT_AREA]>=3]
    if reject_border:
        candidates=[i for i in candidates if stats[i,0]>0 and stats[i,1]>0 and stats[i,0]+stats[i,2]<mask.shape[1] and stats[i,1]+stats[i,3]<mask.shape[0]]
    if not candidates:return [],None
    tallest=max(stats[i,cv2.CC_STAT_HEIGHT] for i in candidates)
    keep=[i for i in candidates if stats[i,cv2.CC_STAT_HEIGHT]>=max(4,tallest*.5)]
    clean=np.isin(labels,keep)
    xs=np.flatnonzero(clean.sum(0)>0)
    if not len(xs):return [],None
    groups=np.split(xs,np.where(np.diff(xs)>1)[0]+1)
    boxes=[]
    for group in groups:
        x1,x2=int(group[0]),int(group[-1])+1;ys=np.flatnonzero(clean[:,x1:x2].sum(1))
        boxes.append((x1,int(ys[0]),x2,int(ys[-1])+1))
    return boxes,clean

def detect_mcp_readouts(frame):
    """Return complete three/five digit windows, or {}. No OCR/label inputs."""
    if frame is None or frame.ndim!=3:return {}
    height,width=frame.shape[:2]
    if height<40 or width<120:return {}
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    dark=cv2.inRange(gray,0,85)
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    bright=cv2.bitwise_and(cv2.inRange(hsv,(0,0,200),(179,160,255)),cv2.inRange(gray,190,255))
    # Remove broad panel edges/legends before grouping; exposure can join them to readouts.
    count,labels,stats,_=cv2.connectedComponentsWithStats(bright,8)
    keep=[i for i in range(1,count) if stats[i,cv2.CC_STAT_AREA]>=4
          and 5<=stats[i,cv2.CC_STAT_HEIGHT]<=height*.25
          and 1<=stats[i,cv2.CC_STAT_WIDTH]<=width*.12]
    bright=np.isin(labels,keep).astype(np.uint8)*255
    # Scale grouping to the panel width: a fixed13px kernel split widely spaced 107.
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(max(3,round(width*.04))|1,3))
    merged=cv2.morphologyEx(bright,cv2.MORPH_CLOSE,kernel)
    contours,_=cv2.findContours(merged,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    windows=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if not (width*.025<=w<=width*.35 and 8<=h<=height*.35 and 1.1<=w/h<=12):continue
        if x<=0 or y<=0 or x+w>=width or y+h>=height:continue
        boxes,clean=glyph_runs(bright[y:y+h,x:x+w]>0)
        if len(boxes) not in (3,5):continue
        gh=[b[3]-b[1] for b in boxes]
        if min(gh)<5 or min(gh)<max(gh)*.55:continue
        centers=[(b[1]+b[3])/2 for b in boxes]
        if max(centers)-min(centers)>max(gh)*.4:continue
        pad=max(2,round(float(np.median(gh))*.18))
        gx1=max(1,x+min(b[0] for b in boxes)-pad);gy1=max(1,y+min(b[1] for b in boxes)-pad)
        gx2=min(width-1,x+max(b[2] for b in boxes)+pad);gy2=min(height-1,y+max(b[3] for b in boxes)+pad)
        # A complete digit group must have dark display glass around its strokes.
        if cv2.countNonZero(dark[gy1:gy2,gx1:gx2])/((gx2-gx1)*(gy2-gy1))<.35:continue
        crop=(gx1,gy1,gx2-gx1,gy2-gy1)
        windows.append(dict(box=(x,y,w,h),crop_box=crop,n=len(boxes),glyph_height=float(np.median(gh))))
    pairs=[]
    for alt in [r for r in windows if r['n']==5]:
        ax,ay,aw,ah=alt['box'];left=[]
        for hdg in [r for r in windows if r['n']==3]:
            hx,hy,hw,hh=hdg['box']
            if hx+hw>=ax:continue
            if abs((hy+hh/2)-(ay+ah/2))>max(hh,ah)*.5:continue
            if not .6<=hdg['glyph_height']/alt['glyph_height']<=1.6:continue
            if ax-(hx+hw)>width*.2:continue
            left.append(hdg)
        if left:
            # HDG is the immediate three-digit readout left of ALT; IAS lies farther left.
            hdg=max(left,key=lambda r:r['box'][0]);pairs.append((hdg,alt))
    if len(pairs)!=1:return {}
    return {'hdg':pairs[0][0]['crop_box'],'alt':pairs[0][1]['crop_box']}
