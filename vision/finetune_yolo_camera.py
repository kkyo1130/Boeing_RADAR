"""Mix synthetic + session-separated camera train/val; reserve real test."""
import os
os.environ.setdefault("MPLBACKEND","Agg")
import argparse
import csv
import json
import shutil
from pathlib import Path
from yolo_camera_data import FIELDS,load_dataset,disjoint,fresh_output,write_yaml

def prepare(synthetic,cameras,test,initial,output,*,blind_camera=False,diagnostic_tests=None):
    sources=[load_dataset(synthetic)]+[load_dataset(c,{'train','val'}) for c in cameras]
    held=load_dataset(test,{'test'})
    retired=[load_dataset(path,{'test'}) for path in (diagnostic_tests or [])]
    disjoint(sources+[held]+retired)
    evaluation_policy=None
    if blind_camera:
        from yolo_final_test_policy import require_blind,retired_records,check_final_test
        if not retired:raise ValueError('--blind-camera requires --diagnostic-test for the previously inspected test set')
        for camera in cameras:require_blind(camera)
        evaluation_policy=dict(version=1,requires_blind_final_test=True,retired_tests=retired_records(retired))
        check_final_test(held,evaluation_policy)
    if not Path(initial).is_file():raise ValueError('Missing initial weights')
    camera_splits={entry['row']['split'] for data in sources[1:] for entry in data['entries']}
    if camera_splits!={'train','val'}:raise ValueError('Independent real train and val sessions required')
    output=fresh_output(output,[synthetic,*cameras,test,Path(initial),*(diagnostic_tests or [])]);output.mkdir(parents=True)
    merged=output/'mixed';merged.mkdir();rows=[]
    for index,data in enumerate(sources):
        for i,entry in enumerate(data['entries']):
            row=entry['row'];split=row['split'];name=f'd{index}_{i:06d}'
            ir=f'images/{split}/{name}'+Path(row['image_path']).suffix;lr=f'labels/{split}/{name}.txt'
            for old,new in [(row['image_path'],ir),(row['label_path'],lr)]:
                (merged/new).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(Path(data['root'])/old,merged/new)
            item={k:row.get(k,'') for k in FIELDS};item.update(image_path=ir,label_path=lr,session_id=f'd{index}:{row["session_id"]}')
            rows.append(item)
    with (merged/'manifest.csv').open('w',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    config=write_yaml(merged)
    manifest=dict(initial=str(Path(initial).resolve()),datasets=[{k:d[k] for k in ('root','fingerprint')} for d in sources],
                  heldout={k:held[k] for k in ('root','fingerprint')},evaluation_policy=evaluation_policy)
    (output/'training_manifest.json').write_text(json.dumps(manifest,indent=2))
    return config,output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--synthetic',type=Path,required=True)
    p.add_argument('--camera',type=Path,action='append',required=True)
    p.add_argument('--real-test',type=Path,required=True)
    p.add_argument('--init',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=40)
    p.add_argument('--imgsz',type=int,default=960)
    p.add_argument('--batch',type=int,default=4)
    p.add_argument('--device',default='mps')
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--blind-camera',action='store_true',help='Require fresh blind labels for every camera train/val and final-test dataset')
    p.add_argument('--diagnostic-test',type=Path,action='append',help='Previously used test: retain for diagnosis, prohibit its pixels/sessions in new train/final test')
    args=p.parse_args()
    if min(args.epochs,args.imgsz,args.batch)<=0:p.error('Positive epochs/imgsz/batch required')
    config,output=prepare(args.synthetic,args.camera,args.real_test,args.init,args.output,blind_camera=args.blind_camera,diagnostic_tests=args.diagnostic_test)
    if args.prepare_only:print(config);return
    from ultralytics import YOLO
    model=YOLO(str(args.init))
    model.train(data=str(config),epochs=args.epochs,imgsz=args.imgsz,batch=args.batch,device=args.device,
        project=str(output),name='fit',exist_ok=False,seed=42,workers=0,optimizer='AdamW',lr0=0.0005,
        plots=False,fliplr=0,flipud=0,mosaic=0.3,close_mosaic=10,degrees=8,perspective=0.0003,
        hsv_h=0.01,hsv_s=0.3,hsv_v=0.4)
    print(f'Best weights: {model.trainer.best}. Real test reserved; no automatic model replacement.')

if __name__=='__main__':main()
