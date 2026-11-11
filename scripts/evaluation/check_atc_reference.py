"""Text-only diagnostic after all timed STT runs; never supplied to ASR."""
import json,sys,os,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--radar-root',type=Path,required=True)
parser.add_argument('--plan',type=Path,required=True)
parser.add_argument('--bert-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.radar_root.resolve()
sys.path.insert(0,str(root/'backend'))
os.environ['RADAR_NER_BACKEND']='bert-hybrid'
os.environ['RADAR_NER_MODEL']=str(args.bert_dir.resolve())
from app.services.demo.adapters import speech_payload
from app.services.speech.ner import extract_atc
plan=json.loads(args.plan.read_text())
rows=[]
for row in plan['clips'][:3]:
 n=extract_atc(row['reference'])
 seg={'role':'ATC','started_at':'2026-11-09T16:00:00Z','segment_id':'text-only','attempt_id':'text-only','atc_input_id':'text-only'}
 p=speech_payload('text-only',0,seg,row['reference'],None,plan['flight_config']['callsigns'],{'evidence_id':'not-uploaded','ref':'stored:not-uploaded'},ner_result=n)
 rows.append({'id':row['id'],'reference':row['reference'],'instruction_check':p['instruction_check'],'callsign':p['callsign']['value'],'fields':{k:v['value'] for k,v in p['fields'].items()},'ner_issues':n['issues']})
out={'diagnostic':'Reference text to extractor only: no ASR, no audio, no actual state adoption; separate from STT comparison. No changes to registry or model.', 'rows':rows}
args.output.write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out,ensure_ascii=False))
