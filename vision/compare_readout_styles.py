"""Paired style regression check. Never changes models, thresholds, or UI source."""
import argparse,json
from pathlib import Path
from report_character_camera import temporal_metrics

def compare(before,after,min_exact=0.):
    if not 0<=min_exact<=1:raise ValueError("Minimum exact rate must be 0-1")
    manifests=[json.loads((p/'manifest.json').read_text()) for p in (before,after)]
    for key in ('plan','frames_per_setting','character_sha256','v5_sha256','gate','candidate_score_threshold','yolo_imgsz','localizer_sha256','raw_jpeg_quality'):
        if manifests[0].get(key)!=manifests[1].get(key):raise ValueError('Unpaired experiment: '+key)
    summaries=[json.loads((p/'summary.json').read_text()) for p in (before,after)]
    rows=[[json.loads(line) for line in (p/'frames.jsonl').read_text().splitlines()] for p in (before,after)]
    expected=len(manifests[0]['plan'])*manifests[0]['frames_per_setting']
    if any(len(r)!=expected for r in rows):raise ValueError('Incomplete scheduled frame records')
    temporal=[temporal_metrics(r)['character'] for r in rows];checks=[]
    for kind in ('hdg','alt'):
        a,b=[s['results']['character'][kind] for s in summaries]
        if a['scheduled']!=expected or b['scheduled']!=expected:raise ValueError('Wrong summary denominator')
        metrics={k:(a[k],b[k]) for k in ('all_frame_raw_exact_accuracy','all_frame_accepted_exact_accuracy','accepted_accuracy')}
        metrics['crop_coverage']=(a['cropped']/expected,b['cropped']/expected)
        metrics['ocr3_stable_correct_all_frames']=(temporal[0][kind]['stable_exact_all_frames'],temporal[1][kind]['stable_exact_all_frames'])
        metrics['ocr3_stable_output_accuracy']=(temporal[0][kind]['stable_output_accuracy'],temporal[1][kind]['stable_output_accuracy'])
        for name,(old,new) in metrics.items():
            passed=(new if new is not None else 0)>=(old if old is not None else 0)-1e-12
            checks.append(dict(kind=kind,metric=name,before=old,after=new,nondecreasing=passed))
        if min_exact>0:
            checks.append(dict(kind=kind,metric='minimum_all_frame_exact',before=min_exact,after=b['all_frame_raw_exact_accuracy'],nondecreasing=b['all_frame_raw_exact_accuracy']>=min_exact-1e-12))
    return dict(keep_candidate=all(c['nondecreasing'] for c in checks),scheduled_frames_per_style=expected,checks=checks,
        limitation='Observed paired regression check in one setup; not a statistical guarantee across conditions')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--min-all-frame-exact',type=float,default=0.);a=p.parse_args()
    if a.output.exists():p.error('Output exists')
    result=compare(a.before,a.after,a.min_all_frame_exact);a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    if not result['keep_candidate']:raise SystemExit(1)
if __name__=='__main__':main()
