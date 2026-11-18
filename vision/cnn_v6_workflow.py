"""Explicit camera collection, preparation, training and independent evaluation stages."""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
BATCH=Path('vision/data/camera_batches')
TRAIN=BATCH/'v6_train_160_02'
TEST=BATCH/'v6_test_40_02'
OLD=BATCH/'sync_test_20261112_021206'
YOLO='vision/checkpoints/mcp_yolo_blind_v2/fit/weights/best.pt'
MODEL='vision/checkpoints/mcp_ocr_v6'
CANDIDATE='vision/checkpoints/mcp_ocr_v5_camera_candidate_01'
FINAL=BATCH/'v5_candidate_final_40_03'

def command(a):
    if a.action=='diagnose':
        return [sys.executable,'vision/validate_yolo_video.py','--source',a.source,'--weights',YOLO,
            '--output','vision/reports/cnn_v6_readout_diagnosis_01','--device',a.device,
            '--max-frames','300','--save-failure-frames','30']
    if a.action=='collect-final':
        return [sys.executable,'vision/collect_camera_mcp.py','--source',a.source,'--display-id','tablet',
            '--auto-interval','0','--v6-plan','test','--session-id','v5_candidate_final_session_03',
            '--output',str(FINAL),'--yolo-weights',YOLO,'--yolo-conf','0.5','--yolo-stable-frames','3']
    if a.action=='compare-final':
        return [sys.executable,'vision/compare_camera_mcp.py','--test',str(FINAL),
            '--v5','vision/checkpoints/mcp_ocr_v5','--v6',CANDIDATE,
            '--training-data','vision/data/mcp_ocr_aligned','--training-data',str(OLD),
            '--training-data',str(TRAIN),'--training-data',str(TEST),
            '--output','vision/reports/v5_candidate_final_03','--device',a.device]
    if a.action.startswith('collect-'):
        split=a.action.split('-')[1]
        return [sys.executable,'vision/collect_camera_mcp.py','--source',a.source,'--display-id','tablet',
            '--auto-interval','0','--v6-plan',split,'--session-id',f'v6_{split}_session_02',
            '--output',str(TRAIN if split=='train' else TEST),'--yolo-weights',YOLO,
            '--yolo-conf','0.5','--yolo-stable-frames','3']
    if a.action=='train':
        out=MODEL+'_preflight' if a.prepare_only else MODEL
        result=[sys.executable,'vision/finetune_camera_mcp.py','--v6','--base','vision/data/mcp_ocr_aligned',
            '--camera',str(OLD),'--camera',str(TRAIN),'--real-test',str(TEST),
            '--init-checkpoints','vision/checkpoints/mcp_ocr_v5','--output',out,
            '--epochs','12','--lr','0.0001','--device',a.device]
        if a.prepare_only:result+=['--prepare-only']
        return result
    return [sys.executable,'vision/compare_camera_mcp.py','--test',str(TEST),
        '--v5','vision/checkpoints/mcp_ocr_v5','--v6',MODEL,
        '--training-data','vision/data/mcp_ocr_aligned','--training-data',str(OLD),
        '--training-data',str(TRAIN),'--output','vision/reports/v5_vs_v6_camera_02','--device',a.device]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('diagnose','collect-train','collect-test','collect-final','train','compare','compare-final'))
    p.add_argument('--source',default='0')
    p.add_argument('--device',default='mps')
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    if a.prepare_only and a.action!='train':p.error('--prepare-only requires train')
    argv=command(a);print(shlex.join(argv),flush=True)
    if not a.dry_run:
        if a.action=='compare-final' and not (ROOT/FINAL/'labels.csv').is_file():
            p.error('Independent final data missing. Run: python vision/cnn_v6_workflow.py collect-final')
        if a.action in ('train','compare') and not (ROOT/TEST/'labels.csv').is_file():
            p.error('Independent test data missing. Run: python vision/cnn_v6_workflow.py collect-test')
        if a.action=='compare' and not all((ROOT/MODEL/f'{kind}_best.pt').is_file() for kind in ('hdg','alt')):
            p.error('v6 checkpoints missing. Complete train successfully before compare.')
        try:subprocess.run(argv,cwd=ROOT,check=True)
        except subprocess.CalledProcessError as exc:
            print('Stage failed; fix the reported error before proceeding to the next stage.',file=sys.stderr)
            raise SystemExit(exc.returncode) from None
if __name__=='__main__':main()
