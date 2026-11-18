"""Fine-tune v3 OCR on original training data plus verified webcam crops.

Example:
 python vision/finetune_camera_mcp.py --base vision/data/mcp_ocr_aligned \
   --camera vision/data/camera_batches/batch_002 \
   --init-checkpoints vision/checkpoints/mcp_ocr_v3 \
   --output vision/checkpoints/mcp_ocr_v4 --epochs 15

Original data and v3 checkpoints are never modified or deleted.
Use --real-test with a separately captured, diverse, unseen test dataset.
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


FIELDS = ["image_path", "kind", "text", "split", "session_id", "source_image"]


from mcp_dataset import validate_dataset, disjoint, separate_output

def load(root):
    with (root / 'labels.csv').open(newline='',encoding='utf-8') as fp:
        return list(csv.DictReader(fp))

def verify(root, rows, splits):
    checked=validate_dataset(root,splits)
    if rows!=checked['rows']: raise ValueError('Rows differ from validated dataset')


def prepare(base, cameras, initial, output, real_test=None, *, camera_val=None):
    datasets=[validate_dataset(base,{'train','val','test'})]
    for kind in ('hdg','alt'):
        for split in ('train','val','test'):
            if not any(r['kind']==kind and r['split']==split for r in datasets[0]['rows']):
                raise ValueError(f'Base missing {kind}/{split}')
    datasets += [validate_dataset(c,{'train'},paired=True) for c in cameras]
    test=validate_dataset(real_test,{'test'},paired=True) if real_test else None
    development=validate_dataset(camera_val,{'val','test'},paired=True) if camera_val else None
    disjoint(datasets+([test] if test else [])+([development] if development else []))
    initial=Path(initial).resolve()
    for kind in ('hdg','alt'):
        if not (initial/f'{kind}_best.pt').is_file(): raise ValueError(f'Missing initial checkpoint: {kind}')
    # Also reject a held-out set that overlaps the v5 training provenance if available.
    ancestor=initial/'merged_training_data'
    if ancestor.exists():
        for held in (test,development):
            if held:disjoint([validate_dataset(ancestor,{'train','val','test'}),held])
    output=separate_output(output,[base,*cameras,initial,*([real_test] if real_test else []),*([camera_val] if camera_val else [])])
    output.mkdir(parents=True)
    merged=output/'merged_training_data'; merged.mkdir()
    rows_out=[]
    for index,data in enumerate(datasets+([development] if development else [])):
        tag='camera_val' if data is development else ('base' if index==0 else f'camera_{index}')
        for i,row in enumerate(data['rows']):
            target_split='val' if data is development else row['split']
            rel=Path(target_split)/row['kind']/f'{tag}_{i:06d}.png'
            dest=merged/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            # Re-encode decoded pixels; sources are never edited.
            from PIL import Image
            with Image.open(Path(data['root'])/row['image_path']) as im: im.save(dest)
            item=dict(row,split=target_split,image_path=rel.as_posix(),session_id=f"{tag}:{row['session_id']}",
                      source_image=f"{tag}/{row['source_image']}")
            rows_out.append(item)
    with (merged/'labels.csv').open('w',newline='',encoding='utf-8') as fp:
        extra_fields=sorted({key for row in rows_out for key in row}-set(FIELDS))
        writer=csv.DictWriter(fp,fieldnames=FIELDS+extra_fields);writer.writeheader();writer.writerows(rows_out)
    manifest={'camera_validation':({k:development[k] for k in ('root','fingerprint')} if development else None),
              'validation_policy':'CAMERA_DEVELOPMENT_NOT_FINAL' if development else 'SYNTHETIC',
              'initial':str(initial),'datasets':[{k:d[k] for k in ('root','fingerprint')} for d in datasets],
              'test':({k:test[k] for k in ('root','fingerprint')} if test else None),
              'preprocessing':'camera_amber_align_v1 then grayscale_bilinear_36n_48',
              'counts':dict(Counter(f"{r['split']}/{r['kind']}" for r in rows_out))}
    (output/'training_manifest.json').write_text(json.dumps(manifest,indent=2))
    return merged


def verify_plan(path, presets, split):
    rows=validate_dataset(path,{split},paired=True)['rows']
    groups={}
    for row in rows:
        groups.setdefault((row['session_id'],row['source_image']),{})[row['kind']]=row['text']
    counts=Counter((v['hdg'],v['alt']) for v in groups.values())
    if counts!=Counter({pair:20 for pair in presets}):
        raise ValueError(f'Expected exactly 20 pairs for each v6 {split} preset: {counts}')
    if not (Path(path)/'collection.json').exists():
        raise ValueError('v6 batch requires original collection.json session provenance')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True, help="Original diverse OCR dataset with train/val/test")
    p.add_argument("--camera", type=Path, required=True, action="append", help="Camera train batch; repeat for multiple batches")
    p.add_argument("--init-checkpoints", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("vision/checkpoints/mcp_ocr_v4"))
    p.add_argument("--real-test", type=Path, help="Independent unseen webcam test dataset; must contain test split")
    p.add_argument("--camera-val",type=Path,help="Separate camera development session, val or consumed test split; never an independent final test")
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    p.add_argument("--v6", action="store_true", help="Require exactly 120 old + 160 new train pairs and independent 40-pair v6 test")
    p.add_argument("--prepare-only", action="store_true", help="Validate and merge without training")
    p.add_argument("--lr", type=float, default=0.0001)
    args = p.parse_args()
    if not 10 <= args.epochs <= 15:
        p.error('--epochs must be 10–15 for camera fine-tuning')
    try:
        if args.v6:
            from mcp_camera_presets import V6_TRAIN, V6_TEST
            if not args.real_test or len(args.camera)!=2:
                raise ValueError('--v6 needs two --camera batches (120 old + 160 new) and --real-test')
            counts=[]
            for path in args.camera:
                data=validate_dataset(path,{'train'},paired=True)
                counts.append(len(data['rows'])//2)
                if len(data['rows'])==320:
                    verify_plan(path,V6_TRAIN,'train')
            if sorted(counts)!=[120,160]: raise ValueError('Expected 120 + 160 camera train pairs')
            verify_plan(args.real_test,V6_TEST,'test')
        merged=prepare(args.base,args.camera,args.init_checkpoints,args.output,args.real_test,camera_val=args.camera_val)
    except (ValueError,OSError) as exc:
        p.error(str(exc))
    output=args.output.resolve()
    if args.prepare_only:
        print(f'Validated and merged: {merged}'); return
    script = Path(__file__).with_name("train_mcp_ocr_v2.py")
    command = [sys.executable, str(script), "--data", str(merged),
               "--output", str(output), "--init-checkpoints", str(args.init_checkpoints),
               "--epochs", str(args.epochs), "--lr", str(args.lr), "--device", args.device, "--augment", "--camera-preprocessing"]
    if args.camera_val:command += ["--camera-validation"]
    print("Starting fine-tuning...", flush=True)
    subprocess.run(command, check=True)
    evaluate = Path(__file__).with_name("evaluate_mcp_ocr.py")
    # Base test remains synthetic if base is synthetic. This is not a webcam accuracy claim.
    subprocess.run([sys.executable, str(evaluate), "--data", str(merged),
                    "--checkpoints", str(output), "--output", str(output / "base_test_report"),
                    "--device", args.device], check=True)
    if args.real_test and not args.v6:
        test_root = args.real_test.resolve()
        test_rows = load(test_root)
        verify(test_root, test_rows, {"test"})
        for kind in ("hdg", "alt"):
            if not any(r["kind"] == kind for r in test_rows):
                p.error(f"Real test dataset missing {kind}")
        subprocess.run([sys.executable, str(evaluate), "--data", str(test_root),
                        "--checkpoints", str(output), "--output", str(output / "real_camera_test_report"),
                        "--device", args.device], check=True)
        summary = json.loads((output / "real_camera_test_report" / "summary.json").read_text())
        for kind in ("hdg", "alt"):
            value = summary[kind]["exact_accuracy"]
            print(f"REAL CAMERA {kind.upper()} exact: {value:.2%}; target >= 90%: {value >= .9}")
    elif args.camera_val:
        print("Camera development data selected checkpoints; independent final camera test remains unexecuted.")
    elif args.v6:
        print("V6 held-out camera test validated but reserved for compare_camera_mcp.py; no model selection from test.")
    else:
        print("NO REAL CAMERA TEST: 90% webcam accuracy cannot be determined.")
    print(f"Fine-tuned checkpoints saved at {output}; original images/checkpoints retained.")


if __name__ == "__main__":
    main()
