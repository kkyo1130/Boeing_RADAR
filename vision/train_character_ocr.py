"""Train shared glyph CNN; validation is development only, never independent final accuracy."""
import argparse,csv,json,random
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image,ImageEnhance,ImageFilter
import torch
from torch.utils.data import Dataset,DataLoader
try:
    from .mcp_dataset import validate_dataset,disjoint,separate_output
    from .mcp_character_ocr import CharacterCNN,segment,tensor,PREPROCESSING,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING
except ImportError:
    from mcp_dataset import validate_dataset,disjoint,separate_output
    from mcp_character_ocr import CharacterCNN,segment,tensor,PREPROCESSING,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING

def selection_score(metrics):
    # Development-only selection: fewer wrong outputs, then useful coverage.
    wrong=sum(m['accepted']-m['accepted_correct'] for m in metrics.values())
    coverage=min(m['accepted_correct']/m['samples'] if m['samples'] else 0 for m in metrics.values())
    return (-wrong,coverage,min(m['exact_accuracy'] for m in metrics.values()))


def evaluate(model,records,device,preprocessing=PREPROCESSING):
    stats={k:dict(samples=0,segmented=0,exact_correct=0,accepted=0,accepted_correct=0) for k in ('hdg','alt')};predictions=[]
    model.eval()
    with torch.inference_mode():
        for row in records:
            s=stats[row['kind']];s['samples']+=1
            with Image.open(row['_path']) as im:result=segment(im,row['kind'],preprocessing)
            pred=None;score=None
            if result:
                s['segmented']+=1;p=model(tensor(result[0]).to(device)).softmax(-1).cpu()
                pred=''.join(map(str,p.argmax(-1).tolist()));score=float(p.max(-1).values.min())
            correct=pred==row['text'];s['exact_correct']+=correct
            accepted=pred is not None and score>=.75 and (row['kind']!='hdg' or int(pred)<=359)
            s['accepted']+=accepted;s['accepted_correct']+=accepted and correct
            predictions.append(dict(kind=row['kind'],image_path=row['_path'],truth=row['text'],prediction=pred,score=score,accepted=accepted,correct=correct))
    for s in stats.values():
        s['exact_accuracy']=s['exact_correct']/s['samples'] if s['samples'] else 0
        s['accepted_accuracy']=s['accepted_correct']/s['accepted'] if s['accepted'] else None
        s['coverage']=s['accepted']/s['samples'] if s['samples'] else 0
    return stats,predictions

def load(root,splits):
    d=validate_dataset(root,splits)
    return d,[dict(r,_path=str(Path(d['root'])/r['image_path'])) for r in d['rows'] if r['split'] in splits]

def main():
    p=argparse.ArgumentParser();p.add_argument('--train',type=Path,action='append',required=True);p.add_argument('--validation',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--device',default='mps');p.add_argument('--epochs',type=int,default=20);p.add_argument('--init',type=Path);p.add_argument('--lr',type=float,default=.0005);p.add_argument('--batch',type=int,default=128);p.add_argument('--preprocessing',choices=[PREPROCESSING,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING],default=PREPROCESSING);a=p.parse_args()
    random.seed(42);np.random.seed(42);torch.manual_seed(42);torch.set_num_threads(4)
    train_data=[];dev_data=[];provenance=[];datasets=[]
    for root in a.train:
        # Validate all synthetic splits but feed only training rows.
        d=validate_dataset(root,{'train','val','test'});datasets.append(d);provenance.append(dict(role='train',root=d['root'],fingerprint=d['fingerprint']))
        train_data.extend(dict(r,_path=str(Path(d['root'])/r['image_path'])) for r in d['rows'] if r['split']=='train')
    for root in a.validation:
        d=validate_dataset(root,{'val','test'},paired=True);datasets.append(d);provenance.append(dict(role='development',root=d['root'],fingerprint=d['fingerprint']))
        dev_data.extend(dict(r,_path=str(Path(d['root'])/r['image_path'])) for r in d['rows'])
    disjoint(datasets);out=separate_output(a.output,[*a.train,*a.validation]);out.mkdir(parents=True)
    samples=[];fail=[]
    for row in train_data:
        with Image.open(row['_path']) as im:result=segment(im,row['kind'],a.preprocessing)
        if result is None:fail.append(row['_path']);continue
        samples.extend((glyph,int(ch)) for glyph,ch in zip(result[0],row['text']))
    (out/'training_manifest.json').write_text(json.dumps(dict(provenance=provenance,preprocessing=a.preprocessing,train_crops=len(train_data),segmentation_failed=fail,characters=len(samples),class_counts=dict(Counter(y for _,y in samples)),selection='DEVELOPMENT_ONLY',seed=42),indent=2))
    if len(set(y for _,y in samples))!=10:raise ValueError('Training must cover all ten digits')
    class Glyphs(Dataset):
        def __len__(self):return len(samples)
        def __getitem__(self,i):
            im,y=samples[i]
            # Geometry/intensity augmentation is label independent.
            im=im.rotate(random.uniform(-8,8),resample=Image.Resampling.BILINEAR,fillcolor=14)
            im=im.transform(im.size,Image.Transform.AFFINE,(1,random.uniform(-.1,.1),random.uniform(-2,2),0,1,random.uniform(-2,2)),resample=Image.Resampling.BILINEAR,fillcolor=14)
            im=ImageEnhance.Brightness(im).enhance(random.uniform(.8,1.15))
            if random.random()<.25:im=im.filter(ImageFilter.GaussianBlur(random.uniform(.1,.6)))
            return tensor([im])[0],y
    model=CharacterCNN().to(a.device)
    if a.init:
        saved=torch.load(a.init,map_location='cpu',weights_only=True)
        if saved.get('preprocessing') not in (PREPROCESSING,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING):raise ValueError('Initializer preprocessing mismatch')
        model.load_state_dict(saved['model'])
    optim=torch.optim.AdamW(model.parameters(),lr=a.lr)
    counts=Counter(y for _,y in samples);weights=torch.tensor([len(samples)/(10*counts[d]) for d in range(10)],device=a.device).clamp(.2,5.)
    loader=DataLoader(Glyphs(),batch_size=a.batch,shuffle=True);history=[];best=None
    if a.init:
        metrics,predictions=evaluate(model,dev_data,a.device,a.preprocessing)
        best=selection_score(metrics)
        torch.save(dict(model=model.state_dict(),preprocessing=a.preprocessing,epoch=0,architecture='shared_character_cnn_v1',development=metrics),out/'character_best.pt')
        (out/'development_predictions.json').write_text(json.dumps(predictions,indent=2))
        print(json.dumps(dict(epoch=0,development=metrics,policy='initializer_baseline')),flush=True)
    for epoch in range(1,a.epochs+1):
        model.train();losses=[]
        for x,y in loader:
            optim.zero_grad();loss=torch.nn.functional.cross_entropy(model(x.to(a.device)),y.to(a.device),weight=weights);loss.backward();optim.step();losses.append(float(loss.detach()))
        metrics,predictions=evaluate(model,dev_data,a.device,a.preprocessing)
        score=selection_score(metrics)
        stat=dict(epoch=epoch,loss=sum(losses)/len(losses),development=metrics);history.append(stat);print(json.dumps(stat),flush=True)
        if best is None or score>best:
            best=score;torch.save(dict(model=model.state_dict(),preprocessing=a.preprocessing,epoch=epoch,architecture='shared_character_cnn_v1',development=metrics),out/'character_best.pt')
            (out/'development_predictions.json').write_text(json.dumps(predictions,indent=2))
        (out/'metrics.json').write_text(json.dumps(history,indent=2))
    print('Saved candidate; development scores are not final test accuracy:',out,flush=True)
if __name__=='__main__':main()
