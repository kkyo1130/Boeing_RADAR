"""Explain the existing panel policy without relaxing it or reading GT at runtime."""
from collections import Counter
import json
import math
from pathlib import Path
from mcp_yolo_gate import PanelGate,iou


def explain(candidates,width,height,threshold=.5):
    gate=PanelGate(threshold,1)
    accepted,reason=gate.select(candidates,width,height)
    policy=gate.policy()
    ranked=sorted((c for c in candidates if c['class']==0 and math.isfinite(c['score']) and c['score']>=policy['candidate_floor']),key=lambda c:c['score'],reverse=True)
    top=ranked[0] if ranked else None
    geometry=None;alternatives=[];failures=[]
    if not top:failures.append('NO_MCP_DETECTION_AT_0_1')
    elif top['score']<threshold:failures.append('LOW_CONFIDENCE')
    if top:
        x1,y1,x2,y2=top['box'];bw,bh=x2-x1,y2-y1;area=bw*bh/(width*height)
        geometry=dict(width_px=bw,height_px=bh,area_ratio=area,aspect_ratio=bw/bh if bh>0 else None,
            center_x_normalized=(x1+x2)/(2*width),center_y_normalized=(y1+y2)/(2*height),
            edge_clearance_px=[x1,y1,width-x2,height-y2])
        for index,c in enumerate(ranked[1:],1):
            overlap=iou(top['box'],c['box'])
            conflict=c['score']>=policy['alternative_score'] and overlap<policy['alternative_iou']
            alternatives.append(dict(rank=index,score=c['score'],box=c['box'],iou_with_top=overlap,conflict=conflict))
        if any(a['conflict'] for a in alternatives):failures.append('AMBIGUOUS_PANELS')
        if min(x1,y1)<=policy['edge_margin_px'] or x2>=width-policy['edge_margin_px'] or y2>=height-policy['edge_margin_px']:failures.append('EDGE_CLIPPED')
        if min(bw,bh)<policy['min_side_px']:failures.append('BOX_SIDE_TOO_SMALL')
        if not policy['min_area_ratio']<=area<=policy['max_area_ratio']:failures.append('BOX_AREA_OUT_OF_RANGE')
    return dict(accepted=accepted is not None,accepted_box=list(accepted) if accepted else None,
        primary_reason=reason,all_failures=failures,geometry=geometry,alternatives=alternatives,
        policy=policy,temporal_stability_evaluated=False,cnn_forwarding='NOT_AUTHORIZED_BY_STATIC_EVALUATION')


def aggregate(rows):
    total=len(rows);detected=[r for r in rows if r['prediction'] is not None]
    localized=[r for r in detected if r['top_iou']>=.5];accepted=[r for r in rows if r['accepted']]
    mean=lambda values:sum(values)/len(values) if values else None
    scores=sorted(r['top_score'] for r in detected)
    bins=[0]*10
    for score in scores:bins[min(9,max(0,int(score*10)))]+=1
    def quantile(q):
        if not scores:return None
        index=(len(scores)-1)*q;low=int(index);high=min(low+1,len(scores)-1)
        return scores[low]+(scores[high]-scores[low])*(index-low)
    distribution=dict(scope='top class-0 score per detected image at floor 0.1; missing images counted separately',
        detected_images=len(scores),missing_images=total-len(scores),
        bins=[dict(lower=i/10,upper=(i+1)/10,count=count) for i,count in enumerate(bins)],
        quantiles={str(int(q*100)):quantile(q) for q in [0,.1,.25,.5,.75,.9,1]})
    return dict(confidence_distribution=distribution,image_count=total,detected_image_count=len(detected),no_detection_image_count=total-len(detected),
        mean_top1_iou=mean([r['top_iou'] for r in rows]),
        mean_top1_iou_all_images=mean([r['top_iou'] for r in rows]),
        mean_top1_iou_detected_images=mean([r['top_iou'] for r in detected]),
        localized_iou50_image_count=len(localized),mean_top1_iou_localized_iou50=mean([r['top_iou'] for r in localized]),
        top1_iou50_rate=sum(r['top_iou']>=.5 for r in rows)/total,
        top1_iou75_rate=sum(r['top_iou']>=.75 for r in rows)/total,
        spatial_gate_coverage=len(accepted)/total,accepted_image_count=len(accepted),
        accepted_mean_iou=mean([r['accepted_iou'] for r in accepted]),
        primary_rejections=dict(Counter(r['reason'] for r in rows if not r['accepted'])),
        all_check_failures=dict(Counter(reason for r in rows for reason in r['gate_diagnostics']['all_failures'])),
        top_score_min=min((r['top_score'] for r in detected),default=None),
        top_score_max=max((r['top_score'] for r in detected),default=None),
        top_score_mean=mean([r['top_score'] for r in detected]))


def annotation_provenance(root,entries):
    root=Path(root);audit=root/'review_audit.json';meta=root/'collection.json'
    if not audit.exists() or not meta.exists():return dict(status='ANNOTATION_PROVENANCE_UNAVAILABLE')
    metadata=json.loads(meta.read_text());reviews=json.loads(audit.read_text())
    source=Path(metadata.get('source_capture',''))
    capture_file=source/'capture_manifest.json';source_meta=source/'collection.json'
    records={};producer={}
    if capture_file.is_file():records={r['id']:r for r in json.loads(capture_file.read_text())['records']}
    if source_meta.is_file():producer=json.loads(source_meta.read_text())
    counts=Counter();alignment=[];by_image={}
    for entry in entries:
        row=entry['row'];key=Path(row['image_path']).stem;decision=reviews.get('decisions',{}).get(key,{})
        method=decision.get('method','UNKNOWN');counts[method]+=1
        record=records.get(key,{});proposal=record.get('proposed_box')
        overlap=iou(entry['box'],proposal) if proposal else None
        if overlap is not None:alignment.append(overlap)
        by_image[row['image_path']]=dict(method=method,source_proposal_iou=overlap,
            source_weights_sha256=producer.get('weights_sha256'))
    return dict(status='HUMAN_REVIEW_AUDIT',methods=dict(counts),source_weights_sha256=producer.get('weights_sha256'),
        proposal_alignment_mean=sum(alignment)/len(alignment) if alignment else None,
        labels_matching_proposal_iou_999=sum(x>=.999 for x in alignment),
        annotation_mode=metadata.get('annotation_mode','ASSISTED'),
        warning=('Independent BLIND_MANUAL rectangles recorded; proposals were not shown by the blind labeling workflow.' if metadata.get('annotation_mode')=='BLIND' else 'Human approval of detector proposals is not an independent blind annotation. High agreement with the proposing model can reflect annotation anchoring.'),
        by_image=by_image)
