"""Same unused real-camera test: AP metrics + per-image panel IoU and overlays."""
import os
os.environ.setdefault("MPLBACKEND","Agg")
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from html import escape
from collections import Counter
from yolo_gate_diagnostics import explain,aggregate,annotation_provenance
from yolo_camera_data import load_dataset,disjoint,fresh_output,write_yaml
from mcp_yolo_gate import PanelGate,iou,validate_detector

def validation_prediction(directory,entry):
    rel=Path(entry['row']['image_path'])
    try:
        rel=rel.relative_to(Path('images')/entry['row'].get('split','test'))
    except ValueError:
        return None
    path=directory/'labels'/('_'.join(rel.with_suffix('').parts)+'.txt')
    if not path.is_file():return None
    candidates=[]
    for line in path.read_text().splitlines():
        values=line.split()
        if len(values)==6 and values[0]=='0':
            x,y,w,h,score=map(float,values[1:]);iw,ih=entry['width'],entry['height']
            candidates.append(dict(score=score,box=[(x-w/2)*iw,(y-h/2)*ih,(x+w/2)*iw,(y+h/2)*ih]))
    return max(candidates,key=lambda c:c['score']) if candidates else None


def draw_overlay(image,entry,panels,row,destination):
    with Image.open(image) as source:canvas=source.convert('RGB')
    draw=ImageDraw.Draw(canvas);font=ImageFont.load_default(size=18)
    for index,c in enumerate(panels[1:],1):
        if c['score']>=row['gate_diagnostics']['policy']['alternative_score']:
            draw.rectangle(c['box'],outline='orange',width=2)
            draw.text((c['box'][0],max(110,c['box'][1]-22)),f"alt{index} {c['score']:.3f}",font=font,fill='orange',stroke_width=1,stroke_fill='black')
    draw.rectangle(entry['box'],outline='lime',width=6)
    if row['prediction']:draw.rectangle(row['prediction'],outline='red',width=3)
    lines=[f"{row['model']} | image {row['image_path']} | GT lime / top red / alternatives orange",
        f"score={row['top_score']} | top IoU={row['top_iou']:.4f} | gate={row['reason'] or 'SPATIAL_PASS'}",
        'All failing checks: '+(', '.join(row['gate_diagnostics']['all_failures']) or 'none'),
        'Static gate pass is not authorization to forward pixels to CNN.']
    draw.rectangle((0,0,canvas.width,108),fill='black')
    for n,line in enumerate(lines):draw.text((8,6+n*25),line,font=font,fill='white')
    canvas.save(destination)


def write_diagnostics(output,report,rows):
    columns=['model','image_path','session_id','top_score','top_iou','detected','localized_iou50','accepted','reason','all_failures','candidate_count','box_width','box_height','area_ratio','aspect_ratio','annotation_method','source_proposal_iou','val_top_iou']
    with (output/'per_image.csv').open('w',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=columns);writer.writeheader()
        for row in rows:
            geometry=row['gate_diagnostics']['geometry'] or {}
            writer.writerow(dict(model=row['model'],image_path=row['image_path'],session_id=row['session_id'],
                top_score=row['top_score'],top_iou=row['top_iou'],detected=row['prediction'] is not None,
                localized_iou50=row['top_iou']>=.5,accepted=row['accepted'],reason=row['reason'],
                all_failures=';'.join(row['gate_diagnostics']['all_failures']),candidate_count=len(row['candidates']),
                box_width=geometry.get('width_px'),box_height=geometry.get('height_px'),area_ratio=geometry.get('area_ratio'),aspect_ratio=geometry.get('aspect_ratio'),
                annotation_method=row['annotation'].get('method'),source_proposal_iou=row['annotation'].get('source_proposal_iou'),val_top_iou=row['val_top_iou']))
    final=report.get('evaluation_mode')=='FINAL_BLIND_INDEPENDENT'
    title='Independent blind final-test comparison' if final else 'Same-test YOLO diagnostic comparison'
    notice='New blind final-test labels; previously inspected diagnostic image/session hashes are blocked. Reserve another new session if tuning follows this evaluation.' if final else 'This is a diagnostic repeat of the existing test set, not a newly unused holdout.'
    text=['# '+title,'',notice,
        'No confidence, ambiguity, geometry or temporal threshold has been relaxed.','',
        '|Model|P|R|mAP50|mAP50-95|Detected / total|IoU all|IoU detected|Spatial pass|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    details=[]
    for name,m in report['models'].items():
        detected='N/A' if m['mean_top1_iou_detected_images'] is None else f"{m['mean_top1_iou_detected_images']:.6f}"
        text.append(f"|{name}|{m['precision']:.4f}|{m['recall']:.4f}|{m['mAP50']:.4f}|{m['mAP50_95']:.4f}|{m['detected_image_count']}/{m['image_count']}|{m['mean_top1_iou_all_images']:.6f}|{detected}|{m['accepted_image_count']}/{m['image_count']}|")
        details+=['',f"{name} primary rejection counts: {m['primary_rejections']}",f"{name} all-check failures: {m['all_check_failures']}",
            f"{name} top-score range: {m['top_score_min']} to {m['top_score_max']}",f"{name} confidence distribution: {m.get('confidence_distribution')}",
            f"{name} validator layout: {m.get('validator_preprocessing')}",f"{name} single-image layout: {m.get('single_image_preprocessing')}",
            f"{name} validator top-1 IoU (all images): {m.get('validator_top1_iou_all_images')}",'']
    text+=details
    provenance=report['annotation_provenance']
    text+=['## Annotation provenance',json.dumps({k:v for k,v in provenance.items() if k!='by_image'},indent=2),
        '', 'The overlap formula uses original-image continuous xyxy pixel coordinates. Missing predictions count as zero in the all-image mean; detected-only means use only images with a class-0 prediction at score >= 0.1.',
        'Precision and recall are reported at the Ultralytics maximum-F1 operating point, not at the fixed deployment confidence of 0.5.',
        'A prediction being present is different from localization at IoU >= 0.5, AP recall, spatial gate approval, temporal stability, or successful OCR.',
        'AP uses the Ultralytics validator with conf=0.001; deployment-style diagnostics use predict(conf=0.1). Validator predictions are exported separately to inspect preprocessing/NMS differences.',
        'Stills cannot establish three-frame temporal stability. Full runtime checks and both internal readout regions remain mandatory.',
        'Aspect ratio is reported, but the existing gate has no aspect-ratio interval or center-position prior. Do not invent one from the test set.',
        '', '## Next annotation/training steps',
        'Independently redraw the complete MCP boundary while hiding all model proposals. Include controls and readout windows; exclude windshield, EFIS and lower flight displays. Do not change this test set in place.',
        'Audit high-IoU proposal approvals and inconsistent target extents before retraining. A model can agree with its own proposals without identifying the intended physical panel.',
        'Use additional independent physical sessions, sharper/focus-locked captures and consistent full-panel boxes. Select training settings and gate calibration using validation only. Reserve new independently annotated sessions for final testing.']
    (output/'diagnosis.md').write_text('\n'.join(text))
    cards=[]
    for i,row in enumerate(rows):
        relative=f"{row['model']}/overlays/{row['image_index']:05d}.jpg"
        cards.append(f'<article data-model="{row["model"]}" data-reason="{escape(row["reason"] or "SPATIAL_PASS")}"><h3>{row["model"]}: {escape(row["image_path"])}</h3><p>{escape(str(row["top_score"]))} / IoU {row["top_iou"]:.4f} / {escape(row["reason"] or "SPATIAL_PASS")}</p><a href="{relative}"><img loading="lazy" src="{relative}" alt="Ground truth, top prediction and competing candidates"></a></article>')
    reasons=sorted({r['reason'] or 'SPATIAL_PASS' for r in rows})
    options=''.join(f'<option>{escape(reason)}</option>' for reason in reasons)
    html='<!doctype html><meta charset="utf-8"><title>YOLO gate diagnostics</title><style>body{font:16px system-ui;background:#17222d;color:#eef4fa;padding:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:20px}article{border:1px solid #607080;padding:12px}img{width:100%}article[hidden]{display:none}select{margin:12px;padding:8px}</style><h1>Same-test YOLO gate diagnostics</h1><p>Proposal-based annotations may favor the proposing model. No gate thresholds were lowered.</p><label>Model <select id="model"><option>all</option><option>old</option><option>new</option></select></label><label>Primary reason <select id="reason"><option>all</option>'+options+'</select></label><main>'+''.join(cards)+'</main>'
    html+="<script>for(const control of document.querySelectorAll('select'))control.onchange=()=>{const m=document.getElementById('model').value,r=document.getElementById('reason').value;for(const row of document.querySelectorAll('article'))row.hidden=(m!=='all'&&row.dataset.model!==m)||(r!=='all'&&row.dataset.reason!==r)}</script>"
    if final:
        html=html.replace('Same-test YOLO gate diagnostics','Independent blind final-test YOLO evaluation').replace('Proposal-based annotations may favor the proposing model. No gate thresholds were lowered.',notice+' No gate thresholds were lowered.')
    (output/'index.html').write_text(html)


def validation_layout(validator):
    dataset=validator.dataloader.dataset
    return dict(rectangular=bool(dataset.rect),padding_batches=float(dataset.pad),
        batch_shapes=sorted({tuple(int(v) for v in shape) for shape in getattr(dataset,'batch_shapes',[])}),
        requested_imgsz=validator.args.imgsz,nms_iou=validator.args.iou)


def prediction_layout(model,image):
    predictor=getattr(model,'predictor',None)
    if predictor is None:return None
    import cv2
    array=cv2.imread(str(image))
    shape=predictor.pre_transform([array])[0].shape[:2]
    return dict(rectangular=bool(predictor.args.rect),input_height=int(shape[0]),input_width=int(shape[1]),
        requested_imgsz=predictor.args.imgsz,nms_iou=predictor.args.iou)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--test',type=Path,required=True)
    p.add_argument('--old',type=Path,required=True)
    p.add_argument('--new',type=Path,required=True)
    p.add_argument('--seen',type=Path,action='append',required=True,help='Repeat for all synthetic and camera training/validation datasets')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--imgsz',type=int,default=960)
    p.add_argument('--device',default='mps')
    p.add_argument('--gate-conf',type=float,default=.5)
    p.add_argument('--final-test',action='store_true',help='Require blind final-test labels and block previously inspected diagnostic images/sessions')
    args=p.parse_args()
    if args.final_test and args.gate_conf!=.5:p.error('Final test must retain the confidence 0.5 safety policy')
    test=load_dataset(args.test,{'test'})
    final_policies=[]
    for source in args.seen:disjoint([load_dataset(source),test])
    for path in (args.old,args.new):
        if not path.is_file():p.error(f'Missing weights: {path}')
        manifest=path.resolve().parents[2]/'training_manifest.json'
        if manifest.exists():
            info=json.loads(manifest.read_text())
            if info.get('evaluation_policy'):final_policies.append(info['evaluation_policy'])
            if info['heldout']['fingerprint']!=test['fingerprint']:p.error('Held-out test differs from frozen training preflight')
            for source in info['datasets']:
                data=load_dataset(source['root'])
                if data['fingerprint']!=source['fingerprint']:p.error('Training dataset changed')
                disjoint([data,test])
    if args.final_test:
        from yolo_final_test_policy import check_final_test
        if not final_policies:p.error('No training manifest defines the retired diagnostic tests; train with --blind-camera')
        for policy in final_policies:check_final_test(test,policy)
    output=fresh_output(args.output,[args.test,*args.seen,args.old,args.new]);output.mkdir(parents=True)
    # Stage copies: Ultralytics caches and writes beside data. Original held-out files stay read-only.
    staged=output/'test_data';staged.mkdir()
    for entry in test['entries']:
        for key in ('image_path','label_path'):
            rel=entry['row'][key];dest=staged/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(Path(test['root'])/rel,dest)
    config=write_yaml(staged)
    from ultralytics import YOLO
    provenance=annotation_provenance(args.test,test['entries'])
    summary={};all_rows=[]
    for name,weights in [('old',args.old),('new',args.new)]:
        model=YOLO(str(weights))
        validate_detector(model)
        observed_layout={}
        if hasattr(model,'add_callback'):
            model.add_callback('on_val_end',lambda validator:observed_layout.update(validation_layout(validator)))
        # Independent low-confidence AP sweep, not the deployment gate threshold.
        metrics=model.val(data=str(config),split='test',imgsz=args.imgsz,device=args.device,
            conf=.001,save_txt=True,save_conf=True,plots=False,project=str(output),name=name,exist_ok=False,workers=0,batch=1)
        summary[name]=dict(precision=float(metrics.box.mp),recall=float(metrics.box.mr),
            mAP50=float(metrics.box.map50),mAP50_95=float(metrics.box.map),
            weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),validator_preprocessing=observed_layout)
        model_rows=[]
        overlays=output/name/'overlays';overlays.mkdir(parents=True,exist_ok=True)
        for index,entry in enumerate(test['entries']):
            image=staged/entry['row']['image_path']
            result=model.predict(str(image),imgsz=args.imgsz,device=args.device,conf=.1,verbose=False)[0]
            boxes=result.boxes
            candidates=[] if boxes is None else [dict(box=b,score=s,**{'class':int(c)}) for b,s,c in
                zip(boxes.xyxy.cpu().tolist(),boxes.conf.cpu().tolist(),boxes.cls.cpu().tolist())]
            panels=sorted((c for c in candidates if c['class']==0),key=lambda c:c['score'],reverse=True)
            top=panels[0] if panels else None
            overlap=iou(top['box'],entry['box']) if top else 0.
            diagnostic=explain(candidates,entry['width'],entry['height'],args.gate_conf)
            val_top=validation_prediction(output/name,entry)
            row=dict(model=name,image_index=index,image_path=entry['row']['image_path'],session_id=entry['row']['session_id'],
                top_score=top['score'] if top else None,top_iou=overlap,accepted=diagnostic['accepted'],reason=diagnostic['primary_reason'],
                accepted_iou=iou(diagnostic['accepted_box'],entry['box']) if diagnostic['accepted'] else None,
                ground_truth=entry['box'],prediction=top['box'] if top else None,
                candidates=candidates,gate_diagnostics=diagnostic,
                annotation=provenance.get('by_image',{}).get(entry['row']['image_path'],{}),
                val_prediction=val_top['box'] if val_top else None,val_top_score=val_top['score'] if val_top else None,
                val_top_iou=iou(val_top['box'],entry['box']) if val_top else 0.,prediction_preprocessing=prediction_layout(model,image))
            all_rows.append(row);model_rows.append(row)
            draw_overlay(image,entry,panels,row,overlays/f'{index:05d}.jpg')
        summary[name].update(aggregate(model_rows))
        summary[name]['single_image_preprocessing']=model_rows[0]['prediction_preprocessing']
        summary[name]['validator_top1_iou_all_images']=sum(r['val_top_iou'] for r in model_rows)/len(model_rows)
        summary[name]['validator_detection_image_count']=sum(r['val_prediction'] is not None for r in model_rows)
        if load_dataset(args.test,{'test'})['fingerprint']!=test['fingerprint']:raise ValueError('Test dataset changed during evaluation')
    report=dict(evaluation_mode='FINAL_BLIND_INDEPENDENT' if args.final_test else 'DIAGNOSTIC_REPEAT',diagnostic_version='yolo-gate/2',annotation_provenance=provenance,gate_policy=PanelGate(args.gate_conf,3).policy(),
        metric_definitions=dict(precision_recall_operating_point='Ultralytics maximum-F1 operating point, not the fixed deployment gate confidence',detection_floor=.1,all_image_iou='Missing predictions count as zero; top class-0 prediction only',detected_iou='Only images with a class-0 prediction at conf >= 0.1',temporal_stability='NOT_EVALUATED_ON_STILLS',cnn_forwarding='NOT_AUTHORIZED_BY_STATIC_EVALUATION'),
        test_fingerprint=test['fingerprint'],samples=len(test['entries']),imgsz=args.imgsz,
        models=summary,delta={k:summary['new'][k]-summary['old'][k] for k in ('precision','recall','mAP50','mAP50_95','mean_top1_iou')})
    (output/'comparison.json').write_text(json.dumps(report,indent=2))
    (output/'boxes.json').write_text(json.dumps(all_rows,indent=2))
    write_diagnostics(output,report,all_rows)
    print(json.dumps(report,indent=2))
    print('Final blind test evaluated; do not tune on these results. Temporal policy still needs real-video validation.' if args.final_test else 'Diagnostic evaluation only; this is not a new unused holdout. Temporal policy needs real-video validation.')

if __name__=='__main__':main()
