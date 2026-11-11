#!/usr/bin/env python3
"""Fixed-audio, local STT comparison. Requires the ATC upload API from PR #22.

No audio upload to model providers, answer prompts, model training, or production
configuration changes. Each invocation isolates one STT model in a new process.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import wave


def normalized_words(text, expand_digits=False):
    words = re.findall(r"[^\W\d_]+|\d+", text.casefold())
    digits = 'zero one two three four five six seven eight nine'.split()
    return [token for w in words for token in
            ([digits[int(c)] for c in w] if expand_digits and w.isdigit() else [w])]


def word_errors(reference, hypothesis, expand_digits=False):
    ref, hyp = normalized_words(reference, expand_digits), normalized_words(hypothesis, expand_digits)
    previous = list(range(len(hyp)+1))
    for i, word in enumerate(ref, 1):
        current = [i]
        for j, other in enumerate(hyp, 1):
            current.append(min(previous[j]+1, current[j-1]+1, previous[j-1]+(word != other)))
        previous = current
    return {'errors':previous[-1], 'reference_words':len(ref),
            'wer':previous[-1]/len(ref) if ref else None}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--radar-root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--audio-dir', type=Path, required=True)
    parser.add_argument('--model-name', required=True)
    parser.add_argument('--no-prompt', action='store_true', help='Diagnostic ablation: remove only generic initial_prompt')
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--bert-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    assert args.no_prompt == (plan.get('prompt_mode') == 'none'), 'Prompt mode must match the frozen plan'
    # Validate the complete fixed evaluation set before doing any inference.
    for row in plan['clips']:
        assert sha(args.audio_dir/row['file']) == row['sha256'], row['file']
    sys.path.insert(0, str(args.radar_root.resolve()/'backend'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='radar-stt-eval-') as temp:
        config = Path(temp)/'config.json'
        config.write_text(json.dumps(plan['flight_config']))
        os.environ.update(RADAR_DEMO_ENABLED='1', RADAR_V2_CONFIG=str(config),
            RADAR_DATABASE_URL=f'sqlite:///{temp}/eval.db',
            RADAR_NER_BACKEND='bert-hybrid', RADAR_NER_MODEL=str(args.bert_dir.resolve()))
        from app.main import app
        from app.services.demo import adapters
        from app.services.speech.local import LocalWhisper
        from fastapi.testclient import TestClient
        import numpy as np
        import torch
        torch.set_num_threads(4)
        started = time.perf_counter()
        from faster_whisper import WhisperModel
        model = LocalWhisper.__new__(LocalWhisper)
        model.model = WhisperModel(str(args.model_dir.resolve()), device='cpu', compute_type='int8', cpu_threads=4, local_files_only=True)
        load_seconds = time.perf_counter()-started
        if args.no_prompt:
            engine = model.model
            class NoPrompt:
                def transcribe(self, *positional, **kwargs):
                    kwargs['initial_prompt'] = None
                    return engine.transcribe(*positional, **kwargs)
            model.model = NoPrompt()
        class MeasuredModel:
            def transcribe(self, path):
                start = time.perf_counter()
                self.last = model.transcribe(path)
                self.seconds = time.perf_counter()-start
                return self.last
        measured = MeasuredModel()
        adapters.MODEL = measured
        result = {'scoring_version':'unicode-word-boundaries-v1', 'model':args.model_name, 'prompt_mode':'none' if args.no_prompt else 'generic_atc', 'plan_sha256':sha(args.plan),
                  'radar_commit':subprocess.check_output(['git','-C',str(args.radar_root),'rev-parse','HEAD'],text=True).strip(),
                  'load_seconds':load_seconds,'weights_sha256':sha(args.model_dir/'model.bin'),
                  'packages':{p:importlib.metadata.version(p) for p in ('faster-whisper','ctranslate2','torch','transformers')},
                  'settings':{'device':'cpu','compute_type':'int8','cpu_threads':4,
                              'decoding':'RADAR LocalWhisper: beam5, English, VAD; prompt mode recorded separately',
                              'latency':'Single measured pass per file, excludes model loading, includes VAD. No throughput claims.'},
                  'rows':[]}
        with TestClient(app) as client:
            assert '/api/demo/{flight}/atc' in app.openapi()['paths'], 'Need ATC API from PR #22'
            for row in plan['clips']:
                path = args.audio_dir/row['file']
                with wave.open(str(path)) as audio:
                    duration = audio.getnframes()/audio.getframerate()
                    pcm = np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').astype(float)/32768
                response = client.post('/api/v2/flights', json={'callsign':row['callsign']})
                response.raise_for_status()
                flight = response.json()['flight_id']
                end = datetime.now(timezone.utc)
                # Replayed-file processing interval, not a new live mic capture.
                payload = {'audio':base64.b64encode(path.read_bytes()).decode(),
                           'started_at':(end-timedelta(seconds=duration)).isoformat().replace('+00:00','Z'),
                           'ended_at':end.isoformat().replace('+00:00','Z'), 'input_mode':'file_upload'}
                total = time.perf_counter()
                response = client.post(f'/api/demo/{flight}/atc', json=payload)
                response.raise_for_status()
                seconds = time.perf_counter()-total
                out = response.json()
                state = client.get(f'/api/v2/flights/{flight}/state').json()
                target = state['targets']['HDG']
                adopted = state['readback_required'] is not None
                correct = adopted and target is not None and target['value']==row['heading'] and state['targets']['ALT'] is None
                entry = {'id':row['id'],'condition':row['condition'],'audio_sha256':row['sha256'],
                         'duration_seconds':duration,'rms':float(np.sqrt(np.mean(pcm**2))),
                         'reference':row['reference'],'transcript':out['transcript'],
                         'lexical_wer':word_errors(row['reference'],out['transcript']),
                         'digit_expanded_wer':word_errors(row['reference'],out['transcript'],True),
                         'stt_seconds':measured.seconds,'pipeline_seconds':seconds,
                         'stt_model_score':out['model_score'],'quality_reason':out['quality_reason'],
                         'adopted':adopted,'correct_adoption':bool(correct),
                         'targets':state['targets'],'structure_check':state['structure_checks'].get('ATC'),
                         'validation_reason':state['validation']['reason'],
                         'ner':out['ner'],'asr_segments':measured.last['segments']}
                result['rows'].append(entry)
                args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
                print(json.dumps({k:entry[k] for k in ('id','condition','transcript','digit_expanded_wer','stt_seconds','correct_adoption','quality_reason')},ensure_ascii=False),flush=True)


if __name__ == '__main__': main()
