"""Evaluate frozen v5/v6 on exactly the same independent camera test images."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from mcp_dataset import validate_dataset, disjoint, separate_output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--test',type=Path,required=True)
    p.add_argument('--v5',type=Path,required=True)
    p.add_argument('--v6',type=Path,required=True)
    p.add_argument('--training-data',type=Path,action='append',required=True,help='Repeat for all training/base datasets')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--device',choices=('cpu','mps','cuda'),default='cpu')
    args=p.parse_args()
    test=validate_dataset(args.test,{'test'},paired=True)
    for root in args.training_data:
        disjoint([validate_dataset(root,{'train','val','test'}),test])
    # Include model provenance; CLI cannot accidentally omit known training sources.
    for model in (args.v5,args.v6):
        for kind in ('hdg','alt'):
            if not (model/f'{kind}_best.pt').is_file(): p.error(f'Missing {model}/{kind}_best.pt')
        merged=model/'merged_training_data'
        if merged.exists(): disjoint([validate_dataset(merged,{'train','val','test'}),test])
        manifest=model/'training_manifest.json'
        if manifest.exists():
            provenance=json.loads(manifest.read_text())
            sources=provenance['datasets']+([provenance['camera_validation']] if provenance.get('camera_validation') else [])
            for source in sources:
                known=validate_dataset(source['root'],{'train','val','test'})
                if known['fingerprint']!=source['fingerprint']: p.error('Training dataset changed since training')
                disjoint([known,test])
    output=separate_output(args.output,[args.test,args.v5,args.v6,*args.training_data]);output.mkdir(parents=True)
    summaries={}
    for name,model in (('v5',args.v5),('v6',args.v6)):
        subprocess.run([sys.executable,str(Path(__file__).with_name('evaluate_mcp_ocr.py')),
            '--data',str(args.test),'--checkpoints',str(model),'--output',str(output/name),'--device',args.device],check=True)
        summaries[name]=json.loads((output/name/'summary.json').read_text())
        if validate_dataset(args.test,{'test'},paired=True)['fingerprint']!=test['fingerprint']:
            raise ValueError('Test data changed during comparison')
    result={'test_fingerprint':test['fingerprint'],'models':summaries,'checkpoints':{},'comparison':{}}
    for name,model in (('v5',args.v5),('v6',args.v6)):
        result['checkpoints'][name]={k:hashlib.sha256((model/f'{k}_best.pt').read_bytes()).hexdigest() for k in ('hdg','alt')}
    for kind in ('hdg','alt'):
        old=summaries['v5'][kind]['exact_accuracy'];new=summaries['v6'][kind]['exact_accuracy']
        result['comparison'][kind]={'v5':old,'v6':new,'delta_percentage_points':100*(new-old)}
        print(f'{kind.upper()}: v5 {old:.2%}, v6 {new:.2%}, delta {100*(new-old):+.2f} pp')
    (output/'comparison.json').write_text(json.dumps(result,indent=2))
    print('Default OCR model unchanged. This held-out set is consumed; reserve new data for later tuning.')

if __name__=='__main__': main()
