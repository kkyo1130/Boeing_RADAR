"""Executable stages for reusing 190 images and reserving a new blind final test.
Each stage runs separately; manual rectangles are never supplied by this helper.
"""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BATCHES=('train_near','train_far','train_angle','val','final_test')
OLD=ROOT.parent/'Boeing_RADAR/runs/detect/vision/checkpoints/mcp_yolo/baseline_v7/weights/best.pt'
LABELS=Path('vision/data/yolo_blind_v2/labels')
MODEL=Path('vision/checkpoints/mcp_yolo_blind_v2')


def command(args):
    run=[sys.executable]
    if args.action=='review':
        if args.batch not in BATCHES:raise ValueError('review requires a batch: '+', '.join(BATCHES))
        source=Path('vision/data/yolo_camera')/('final_test_02' if args.batch=='final_test' else args.batch)
        return run+['vision/review_yolo_camera.py','--blind','--input',str(source),
            '--review-dir',f'vision/data/yolo_blind_v2/work/{args.batch}','--output',str(LABELS/args.batch)]
    if args.batch:raise ValueError('Only the review action takes a batch name')
    if args.action=='collect-final':
        return run+['vision/collect_yolo_camera.py','--source',args.source,'--auto-interval','2','--capture-only',
            '--session','yolo_final_test_02','--split','test','--count','40','--output','vision/data/yolo_camera/final_test_02']
    if args.action=='train':
        result=run+['vision/finetune_yolo_camera.py','--blind-camera','--synthetic','vision/data/mcp_blender_v7']
        for name in BATCHES[:-1]:result+=['--camera',str(LABELS/name)]
        result+=['--real-test',str(LABELS/'final_test'),'--diagnostic-test','vision/data/yolo_camera_confirmed/test',
            '--init',str(OLD),'--output',str(MODEL)+'_preflight' if args.prepare_only else str(MODEL),
            '--epochs',str(args.epochs),'--imgsz','960','--batch','4','--device',args.device]
        if args.prepare_only:result+=['--prepare-only']
        return result
    if args.action=='evaluate':
        result=run+['vision/compare_yolo_camera.py','--final-test','--test',str(LABELS/'final_test'),
            '--old',str(OLD),'--new',str(MODEL/'fit/weights/best.pt'),'--seen','vision/data/mcp_blender_v7']
        for name in BATCHES[:-1]:result+=['--seen',str(LABELS/name)]
        return result+['--output','vision/reports/yolo_blind_v2_final_01','--imgsz','960','--device',args.device,'--gate-conf','0.5']
    if args.action=='video':
        return run+['vision/validate_yolo_video.py','--source',args.source,'--weights',str(MODEL/'fit/weights/best.pt'),
            '--output','vision/reports/yolo_blind_v2_video_01','--device',args.device,'--max-frames',str(args.max_frames),'--imgsz','960']
    raise ValueError('Unknown action')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('review','collect-final','train','evaluate','video'))
    p.add_argument('batch',nargs='?',choices=BATCHES)
    p.add_argument('--device',default='mps')
    p.add_argument('--source',default='0')
    p.add_argument('--epochs',type=int,default=40)
    p.add_argument('--max-frames',type=int,default=300)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--dry-run',action='store_true',help='Print exact argv without running GUI, training, evaluation or creating output')
    args=p.parse_args()
    if args.prepare_only and args.action!='train':p.error('--prepare-only is only valid for train')
    if args.epochs<1 or args.max_frames<1:p.error('Positive epochs/frame count required')
    try:argv=command(args)
    except ValueError as exc:p.error(str(exc))
    print(shlex.join(argv),flush=True)
    if not args.dry_run:subprocess.run(argv,cwd=ROOT,check=True)

if __name__=='__main__':main()
