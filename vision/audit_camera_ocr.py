"""Read-only OCR crop audit. Predictions never become labels or automatic quality decisions."""
import argparse,csv,json,html
from pathlib import Path
from collections import Counter
from PIL import Image,ImageDraw
from mcp_dataset import validate_dataset,separate_output
from mcp_preprocessing import normalize_aligned

def build(data,comparison,output):
    checked=validate_dataset(data,{'test'},paired=True)
    output=separate_output(output,[data,comparison]);output.mkdir(parents=True)
    predictions={}
    for name in ('v5','v6'):
        with (Path(comparison)/name/'predictions.csv').open() as f:
            rows=list(csv.DictReader(f))
        mapping={r['image_path']:r for r in rows}
        if len(mapping)!=len(rows) or set(mapping)!={r['image_path'] for r in checked['rows']}:
            raise ValueError('Prediction paths do not match dataset exactly')
        for r in checked['rows']:
            pred=mapping[r['image_path']]
            if pred['truth']!=r['text'] or pred['kind']!=r['kind'] or len(pred['prediction'])!=len(r['text']):
                raise ValueError('Prediction provenance/format mismatch')
        predictions[name]=mapping
    confusion=Counter();audit=[];links=[]
    for offset in range(0,len(checked['rows']),20):
        page=Image.new('RGB',(1000,10*112),'#202020');draw=ImageDraw.Draw(page)
        for index,row in enumerate(checked['rows'][offset:offset+20]):
            x=(index%2)*500;y=(index//2)*112
            with Image.open(Path(data)/row['image_path']) as source:
                crop=source.convert('RGB');tensor=normalize_aligned(crop,row['kind'])
            page.paste(crop,(x+5,y+25));page.paste(tensor.convert('RGB'),(x+205,y+25))
            p5=predictions['v5'][row['image_path']]['prediction'];p6=predictions['v6'][row['image_path']]['prediction']
            draw.text((x+5,y+3),f"{row['kind']} GT {row['text']} | v5 {p5} | v6 {p6}",fill='white')
            draw.text((x+5,y+80),row['image_path'],fill='white')
            for model,pred in [('v5',p5),('v6',p6)]:
                for pos,(truth,guess) in enumerate(zip(row['text'],pred)):
                    if truth!=guess:confusion[(model,row['kind'],pos+1,truth,guess)]+=1
            audit.append(dict(image_path=row['image_path'],kind=row['kind'],truth=row['text'],v5=p5,v6=p6,
                review_status='PENDING',visual_text='',crop_issue='',note=''))
        filename=f'crops_{offset//20+1:02d}.png';page.save(output/filename);links.append(filename)
    with (output/'manual_review.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
    counts=[dict(model=k[0],kind=k[1],position=k[2],truth=k[3],prediction=k[4],count=v) for k,v in sorted(confusion.items())]
    (output/'confusions.json').write_text(json.dumps(counts,indent=2))
    summary=dict(samples=len(audit),fingerprint=checked['fingerprint'],reviewed_automatically=False,
        purpose='DIAGNOSTIC_ONLY_CONSUMED_TEST',label_changes=0,
        limitation='Saved aligned crops cannot prove the original camera ROI or physical display label. Manual review required.')
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>OCR crop audit</title><h1>Saved crop / CNN grayscale input</h1><p>Diagnostic only. No labels changed. Manual review CSV starts PENDING.</p>'+''.join(f'<img style="max-width:100%" src="{html.escape(n)}">' for n in links))
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--comparison',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.data,a.comparison,a.output),indent=2))
if __name__=='__main__':main()
