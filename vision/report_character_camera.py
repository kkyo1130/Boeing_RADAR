"""Derive audit/presentation artifacts without running inference or selecting checkpoints."""
import argparse,json,html
from pathlib import Path
from collections import deque
from PIL import Image,ImageDraw

def temporal_metrics(records):
    result={}
    for model in ('v5','character'):
        result[model]={}
        for kind in ('hdg','alt'):
            history=deque(maxlen=3);stable=correct=0
            for row in records:
                value=row['models'].get(model,{}).get(kind,{}).get('value')
                if value is None:history.clear();continue
                history.append(value)
                if len(history)==3 and len(set(history))==1:
                    stable+=1;correct+=value==row['truth'][kind]
            result[model][kind]=dict(frames=len(records),stable_outputs=stable,stable_correct=correct,
                stable_exact_all_frames=correct/len(records) if records else None,
                stable_output_accuracy=correct/stable if stable else None)
    return result

def build(root):
    records=[json.loads(line) for line in (root/'frames.jsonl').read_text().splitlines()]
    summary=json.loads((root/'summary.json').read_text());out=root/'audit'
    if out.exists():raise ValueError('Audit output exists')
    out.mkdir();metrics=temporal_metrics(records)
    (out/'temporal_summary.json').write_text(json.dumps(metrics,indent=2))
    chosen=[]
    for setting in sorted({r['setting'] for r in records}):
        group=[r for r in records if r['setting']==setting]
        chosen.append(next((r for r in group if set(r.get('crops',{}))=={'hdg','alt'}),group[0]))
    contact=Image.new('RGB',(1050,len(chosen)*90),'#202020');draw=ImageDraw.Draw(contact)
    for i,row in enumerate(chosen):
        y=i*90
        draw.text((5,y+5),f"setting {row['setting']+1} frame {row['frame']} | GT HDG {row['truth']['hdg']} ALT {row['truth']['alt']}",fill='white')
        for j,kind in enumerate(('hdg','alt')):
            x=5+j*500
            if kind in row.get('crops',{}):
                with Image.open(root/row['crops'][kind]) as im:contact.paste(im.convert('RGB'),(x,y+28))
            old=row['models'].get('v5',{}).get(kind,{}).get('raw_value');new=row['models'].get('character',{}).get(kind,{})
            draw.text((x+200,y+30),f"v5 {old} | new {new.get('raw_value')}",fill='white')
            draw.text((x+200,y+50),f"accepted {new.get('value')} | score {new.get('model_score')}",fill='white')
    contact.save(out/'all_settings.png')
    example=next((r for r in records if r.get('raw') and set(r.get('crops',{}))=={'hdg','alt'}),None)
    if example:
        with Image.open(root/example['raw']) as im:image=im.convert('RGB')
        d=ImageDraw.Draw(image)
        for kind,box in example['regions'].items():
            x,y,w,h=box;d.rectangle((x,y,x+w,y+h),outline=(0,255,80),width=3)
            pred=example['models']['character'][kind];d.text((x,max(0,y-18)),f"{kind.upper()} {pred.get('value')} | score {pred.get('model_score',0):.3f}",fill=(0,255,80))
        image.save(out/'first_eligible_frame.png')
    content='<p>Single camera setup/time-separated unseen camera-number sequence. Correlated frames. Scores are uncalibrated. All scheduled failures included in all-frame metrics. Example chosen as first cropped frame, not by correctness.</p>'
    content+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Additional 3-frame OCR stability (offline replay)</h2><pre>'+html.escape(json.dumps(metrics,indent=2))+'</pre><img style="max-width:100%" src="first_eligible_frame.png"><img style="max-width:100%" src="all_settings.png">'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Camera OCR experiment</title><h1>Frozen camera OCR evaluation</h1>'+content)
    return metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.input),indent=2))
if __name__=='__main__':main()
