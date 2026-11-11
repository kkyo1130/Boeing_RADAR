#!/usr/bin/env python3
"""Local-only ATC specialist experiment. Does not change production models.

CTC has no calibrated/Whisper-compatible score here. Preserve None: server must
hold unknown score even when a separately labelled text-only gate succeeds.
"""
import argparse,base64,json,math,os,subprocess,sys,tempfile,time,wave
from datetime import datetime,timedelta,timezone
from pathlib import Path


def pcm16(path, target_rate=None):
    import numpy as np
    from scipy.signal import resample_poly
    with wave.open(str(path)) as f:
        if f.getsampwidth()!=2: raise ValueError('PCM16 required')
        rate=f.getframerate(); channels=f.getnchannels()
        samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
    samples=samples.reshape(-1,channels).mean(axis=1)
    if target_rate and rate!=target_rate:
        divisor=math.gcd(rate,target_rate)
        samples=resample_poly(samples,target_rate//divisor,rate//divisor).astype(np.float32)
        rate=target_rate
    return samples,rate


class CTC:
    def __init__(self,path):
        import torch
        from transformers import AutoModelForCTC,Wav2Vec2Processor
        self.processor=Wav2Vec2Processor.from_pretrained(path,local_files_only=True)
        self.model=AutoModelForCTC.from_pretrained(path,local_files_only=True,
            use_safetensors=bool(list(Path(path).glob('*.safetensors'))),weights_only=True,
            attn_implementation='eager').eval().to('cpu')
    def transcribe(self,path):
        import torch
        samples,rate=pcm16(path,16000)
        inputs=self.processor(samples,sampling_rate=rate,return_tensors='pt')
        with torch.inference_mode(): logits=self.model(**inputs).logits
        text=self.processor.batch_decode(logits.argmax(dim=-1))[0]
        return {'transcript':text,'model_score':None,'score_calibrated':False,
                'score_reason':'CTC score is not calibrated or equivalent to Whisper avg_logprob',
                'segments':[]}


def text_gate(payload, expected_call, expected_heading):
    values={k:v['value'] for k,v in payload['fields'].items()}
    return (payload['instruction_check']=='PASS' and payload['callsign']['value']==expected_call
            and values=={'HDG':expected_heading})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['radar-root','scorer-root','plan','audio-dir','model-dir','bert-dir','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--model-name',required=True);p.add_argument('--engine',choices=['ctc','whisper'],required=True)
    p.add_argument('--no-prompt',action='store_true');args=p.parse_args()
    if args.engine=='ctc' and args.no_prompt:p.error('CTC does not use a prompt')
    sys.path.insert(0,str(args.scorer_root.resolve()/'scripts/evaluation'))
    from compare_atc_stt import sha,word_errors
    plan=json.loads(args.plan.read_text())
    assert args.model_name in plan['models']
    for clip in plan['clips']:assert sha(args.audio_dir/clip['file'])==clip['sha256']
    sys.path.insert(0,str(args.radar_root.resolve()/'backend'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    import torch;torch.set_num_threads(4)
    with tempfile.TemporaryDirectory(prefix='radar-specialist-') as temp:
        cfg=Path(temp)/'config.json';cfg.write_text(json.dumps(plan['flight_config']))
        os.environ.update(RADAR_DEMO_ENABLED='1',RADAR_V2_CONFIG=str(cfg),
            RADAR_DATABASE_URL=f'sqlite:///{temp}/eval.db',RADAR_NER_BACKEND='bert-hybrid',
            RADAR_NER_MODEL=str(args.bert_dir.resolve()))
        from app.main import app
        from app.services.demo import adapters
        from app.services.speech.local import LocalWhisper
        from fastapi.testclient import TestClient
        start=time.perf_counter()
        if args.engine=='ctc':
            model=CTC(str(args.model_dir.resolve()))
        else:
            from faster_whisper import WhisperModel
            model=LocalWhisper.__new__(LocalWhisper)
            engine=WhisperModel(str(args.model_dir.resolve()),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
            if args.no_prompt:
                class NoPrompt:
                    def transcribe(self,*pos,**kw):
                        kw['initial_prompt']=None;return engine.transcribe(*pos,**kw)
                model.model=NoPrompt()
            else:model.model=engine
        load_seconds=time.perf_counter()-start
        class Measured:
            def transcribe(self,path):
                start=time.perf_counter();self.last=model.transcribe(path)
                self.seconds=time.perf_counter()-start;return self.last
        measured=Measured();adapters.MODEL=measured
        result={'model':args.model_name,'engine':args.engine,'plan_sha256':sha(args.plan),
            'radar_commit':subprocess.check_output(['git','-C',str(args.radar_root),'rev-parse','HEAD'],text=True).strip(),
            'scorer_commit':subprocess.check_output(['git','-C',str(args.scorer_root),'rev-parse','HEAD'],text=True).strip(),
            'weights':{f.name:sha(f) for f in args.model_dir.iterdir() if f.name.endswith(('.bin','.safetensors'))},
            'load_seconds':load_seconds,'device':'cpu','threads':4,
            'precision':'float32' if args.engine=='ctc' else 'int8',
            'decode':'greedy CTC, no LM, 16kHz resample, no VAD' if args.engine=='ctc' else 'existing LocalWhisper beam5, VAD, English',
            'prompt':'not_applicable' if args.engine=='ctc' else 'none' if args.no_prompt else 'generic_atc',
            'rows':[]}
        with TestClient(app) as client:
            for clip in plan['clips']:
                file=args.audio_dir/clip['file'];samples,rate=pcm16(file);duration=len(samples)/rate
                response=client.post('/api/v2/flights',json={'callsign':clip['callsign']});response.raise_for_status();flight=response.json()['flight_id']
                now=datetime.now(timezone.utc)
                body={'audio':base64.b64encode(file.read_bytes()).decode(),'input_mode':'file_upload',
                    'started_at':(now-timedelta(seconds=duration)).isoformat().replace('+00:00','Z'),
                    'ended_at':now.isoformat().replace('+00:00','Z')}
                start=time.perf_counter();response=client.post(f'/api/demo/{flight}/atc',json=body);response.raise_for_status();out=response.json()
                pipeline_seconds=time.perf_counter()-start
                state=client.get(f'/api/v2/flights/{flight}/state').json()
                # Separate diagnostic of actual predicted text, with no acoustic-quality claim.
                segment={'role':'ATC','started_at':body['started_at'],'segment_id':'text-diagnostic','attempt_id':'text-diagnostic','atc_input_id':'text-diagnostic'}
                diagnostic=adapters.speech_payload(flight,0,segment,out['transcript'],None,
                    plan['flight_config']['callsigns'],{'evidence_id':'not-stored','ref':'stored:not-stored'},ner_result=out['ner'])
                adopted=state['readback_required'] is not None
                target=state['targets']['HDG']
                row={'id':clip['id'],'condition':clip['condition'],'audio_sha256':clip['sha256'],
                    'reference':clip['reference'],'transcript':out['transcript'],
                    'wer':word_errors(clip['reference'],out['transcript'],True),
                    'lexical_wer':word_errors(clip['reference'],out['transcript']),
                    'stt_seconds':measured.seconds,'pipeline_seconds':pipeline_seconds,
                    'model_score':out['model_score'],'quality_reason':out['quality_reason'],
                    'text_extraction_correct':text_gate(diagnostic,clip['callsign'],clip['heading']),
                    'text_fields':{k:v['value'] for k,v in diagnostic['fields'].items()},
                    'text_callsign':diagnostic['callsign']['value'],
                    'adopted':adopted,'correct_adoption':bool(adopted and target and target['value']==clip['heading'] and state['targets']['ALT'] is None),
                    'structure':state['structure_checks'].get('ATC'),'validation_reason':state['validation']['reason'],
                    'ner_issues':out['ner']['issues'] if out['ner'] else None}
                result['rows'].append(row);args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
                print(json.dumps({k:row[k] for k in ['condition','transcript','wer','stt_seconds','text_extraction_correct','correct_adoption','quality_reason']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
