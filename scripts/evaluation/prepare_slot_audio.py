"""Select fresh positive ALT/HDG controller recordings before ASR/NER."""
import hashlib,json,random,re,wave,io
from pathlib import Path
import pyarrow.parquet as pq

root=Path('.demo/slots');prior=json.loads(Path('../atc-unseen-whisper/docs/evaluation/unseen-atc-whisper-2026-11-10.json').read_text())
ids=set();pat=re.compile(r'uwb-atcc_[A-Za-z0-9-]+_[0-9]+_[0-9]+_[A-Z]+')
for item in prior['plan']['prior_files']:
 p=Path('../..')/item['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'];ids.update(pat.findall(p.read_text()))
ids.update(c['id'] for c in prior['plan']['clips']);groups={x.split('_')[1] for x in ids}
pqpath=root/'source/data/train-00000-of-00002-4a9602acfde9f517.parquet'
paths=sorted((root/'source/data').glob('train-*.parquet'))
assert len(paths)==2, 'Both source shards required before selection'
rows=[r for p in paths for r in pq.read_table(p).to_pylist()];random.Random(20261111).shuffle(rows)
training_path=Path('../real-model-comparison-20261109/data.json')
training=json.loads(training_path.read_text())['splits']
training_groups={r['id'].split('_')[1] for split in ('train','validation') for r in training[split]}
selected=[];counts={'ALT':0,'HDG':0};seen=set()
for row in rows:
 id=row['id'];group=id.split('_')[1];text=row['text']
 if not id.endswith('_AT') or group in seen or id in ids:continue
 # Positive-content sampling only, not general prevalence evaluation.
 alt=bool(re.search(r'\b(?:climb|descend|maintain)\b.*\bflight level (?:zero|one|two|three|four|five|six|seven|eight|nine|[0-9])',text))
 hdg=bool(re.search(r'\bheading (?:(?:zero|one|two|three|four|five|six|seven|eight|nine) ){2}(?:zero|one|two|three|four|five|six|seven|eight|nine)\b',text))
 if alt==hdg:continue
 kind='ALT' if alt else 'HDG'
 if kind=='ALT' and (group in groups or counts[kind]>=15):continue
 if kind=='HDG' and (group in training_groups or counts[kind]>=13):continue
 selected.append({k:v for k,v in row.items() if k!='audio'}|{'group':group,'stratum':kind})
 seen.add(group);counts[kind]+=1
 (root/'audio').mkdir(parents=True,exist_ok=True)
 data=row['audio']['bytes'];(root/'audio'/f'{id}.wav').write_bytes(data)
 selected[-1]['sha256']=hashlib.sha256(data).hexdigest()
 with wave.open(io.BytesIO(data)) as f:selected[-1]['audio_seconds']=f.getnframes()/f.getframerate()
 if counts=={'ALT':15,'HDG':13}:break
assert counts=={'ALT':15,'HDG':13}, counts
plan={'source':'Jzuluaga/uwb_atcc','revision':prior['plan']['revision'],'split':'train','parquet_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'seed':20261111,'counts':counts,'prior_recording_groups':len(groups),'bert_train_validation_manifest_sha256':hashlib.sha256(training_path.read_bytes()).hexdigest(),'bert_train_validation_groups':len(training_groups),'previous_eval_group_overlap_ids':[r['id'] for r in selected if r['group'] in groups],'selection':'ALT15: exclude all prior-used groups. HDG13: unused exact clips and exclude BERT train/validation groups, but prior evaluation group overlap retained as flagged diagnostic. One per group, explicit numeric operand, mixed ALT/HDG excluded. Protocol amended before ASR/NER after no fully unseen HDG groups found.','clips':selected}
(root/'supplement-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
for i,r in enumerate(selected,1):print(i,r['stratum'],r['id'],'|',r['text'])
print(counts)
