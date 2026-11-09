"""Package an existing local fine-tuned BERT; no download, training, or model selection."""
import argparse, hashlib, json, shutil
from pathlib import Path

FILES = ('model.safetensors','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args()
    config=json.loads((a.source/'config.json').read_text())
    if config.get('model_type')!='bert':p.error('Expected an existing fine-tuned BERT artifact')
    if not all((a.source/f).is_file() for f in FILES):p.error('Missing required local artifact files')
    a.destination.mkdir(parents=True,exist_ok=False)
    for f in FILES:shutil.copyfile(a.source/f,a.destination/f)
    manifest={'schema_version':1,'backend':'bert-hybrid','sha256':{f:hashlib.sha256((a.destination/f).read_bytes()).hexdigest() for f in FILES}}
    (a.destination/'radar_hybrid.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Prepared local BERT artifact:',a.destination)
if __name__=='__main__':main()
