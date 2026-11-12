"""Conservative panel gate: model score is not calibrated accuracy."""
import math

def iou(a,b):
    """Continuous xyxy pixel-coordinate IoU. Missing/invalid boxes contribute zero.

    YOLO label xywh coordinates must be converted to the original image pixels
    before calling. This function never selects a prediction using ground truth.
    """
    try:
        a=tuple(float(v) for v in a);b=tuple(float(v) for v in b)
        if len(a)!=4 or len(b)!=4 or not all(math.isfinite(v) for v in a+b):return 0.
        if a[2]<=a[0] or a[3]<=a[1] or b[2]<=b[0] or b[3]<=b[1]:return 0.
    except (TypeError,ValueError):return 0.
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return min(1.,max(0.,inter/union)) if union>0 else 0.


class PanelGate:
    CANDIDATE_FLOOR=.1
    ALTERNATIVE_SCORE_RATIO=.6
    ALTERNATIVE_MAX_IOU=.5
    EDGE_MARGIN_PX=1
    MIN_SIDE_PX=12
    MIN_AREA_RATIO=.003
    MAX_AREA_RATIO=.9
    STABILITY_IOU=.8

    def policy(self):
        return dict(confidence=self.threshold,candidate_floor=self.CANDIDATE_FLOOR,
            alternative_score=self.threshold*self.ALTERNATIVE_SCORE_RATIO,alternative_iou=self.ALTERNATIVE_MAX_IOU,
            edge_margin_px=self.EDGE_MARGIN_PX,min_side_px=self.MIN_SIDE_PX,
            min_area_ratio=self.MIN_AREA_RATIO,max_area_ratio=self.MAX_AREA_RATIO,
            stability_iou=self.STABILITY_IOU,stable_frames=self.stable_frames,
            aspect_ratio_constraint=None,position_constraint='Within image edge margins; no center prior')
    def __init__(self,threshold=.5,stable_frames=3):
        if not .001<=threshold<=1 or stable_frames<1:raise ValueError('Invalid YOLO threshold/stability')
        self.threshold=threshold;self.stable_frames=stable_frames;self.previous=None;self.count=0
    def reject(self,reason):
        self.previous=None;self.count=0
        return None,reason
    def select(self,candidates,width,height):
        # Retain low-score alternatives for ambiguity checks, not as CNN inputs.
        candidates=[c for c in candidates if c['class']==0 and math.isfinite(c['score']) and c['score']>=self.CANDIDATE_FLOOR]
        candidates.sort(key=lambda c:c['score'],reverse=True)
        if not candidates or candidates[0]['score']<self.threshold:return self.reject('LOW_OR_MISSING_PANEL_SCORE')
        best=candidates[0];box=best['box']
        if any(c['score']>=self.threshold*self.ALTERNATIVE_SCORE_RATIO and iou(box,c['box'])<self.ALTERNATIVE_MAX_IOU for c in candidates[1:]):
            return self.reject('AMBIGUOUS_PANELS')
        if not all(math.isfinite(v) for v in box):return self.reject('INVALID_PANEL_BOX')
        x1,y1,x2,y2=box;area=(x2-x1)*(y2-y1)/max(1,width*height)
        if x1<=self.EDGE_MARGIN_PX or y1<=self.EDGE_MARGIN_PX or x2>=width-self.EDGE_MARGIN_PX or y2>=height-self.EDGE_MARGIN_PX or min(x2-x1,y2-y1)<self.MIN_SIDE_PX or not self.MIN_AREA_RATIO<=area<=self.MAX_AREA_RATIO:
            return self.reject('CLIPPED_OR_IMPLAUSIBLE_PANEL')
        self.count=self.count+1 if self.previous and iou(self.previous,box)>=self.STABILITY_IOU else 1
        self.previous=box
        if self.count<self.stable_frames:return None,'PANEL_STABILIZING'
        return tuple(map(int,box)),None

def detect_panel_readouts(model,frame,gate,detect_readouts,device=None,imgsz=960):
    try:
        kwargs=dict(conf=.1,verbose=False,imgsz=imgsz)
        if device is not None:kwargs['device']=device
        result=model.predict(frame,**kwargs)[0]
        boxes=result.boxes
        candidates=[] if boxes is None else [dict(box=b,score=s,**{'class':int(c)}) for b,s,c in
            zip(boxes.xyxy.cpu().tolist(),boxes.conf.cpu().tolist(),boxes.cls.cpu().tolist())]
        h,w=frame.shape[:2];panel,reason=gate.select(candidates,w,h)
        if panel is None:return {},reason
        x1,y1,x2,y2=panel
        local=detect_readouts(frame[y1:y2,x1:x2])
        if set(local)!={'hdg','alt'}:return {},'READOUTS_MISSING_OR_AMBIGUOUS'
        for x,y,bw,bh in local.values():
            if min(x,y)<0 or min(bw,bh)<=0 or x+bw>x2-x1 or y+bh>y2-y1:
                return {},'READOUT_OUTSIDE_PANEL'
        return {kind:(b[0]+x1,b[1]+y1,b[2],b[3]) for kind,b in local.items()},None
    except Exception as exc:
        gate.reject('DETECTOR_ERROR')
        return {},f'DETECTOR_ERROR:{type(exc).__name__}'

def validate_detector(model):
    names=model.names
    if not isinstance(names,dict) or len(names)!=1 or str(names.get(0,'')).lower()!='mcp':
        raise ValueError('Expected a single-class MCP detector; generic COCO weights are not MCP weights')
