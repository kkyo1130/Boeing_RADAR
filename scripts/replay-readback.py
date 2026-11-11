"""Replay existing ATC/pilot WAVs through real HTTP STT; never edit the transcript.

Replay timestamps describe this file injection, not original microphone capture.
Keep original recording timestamps/hash manifests alongside the local output.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import wave
import time
import httpx


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server', required=True)
    p.add_argument('--callsign', required=True)
    p.add_argument('--atc', type=Path, required=True)
    p.add_argument('--readback', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.server, timeout=180) as client:
        def request(method, url, **kwargs):
            response = client.request(method, url, **kwargs)
            
            if response.is_error:
                raise RuntimeError(f"{response.status_code}: {response.text}")
            return response.json()
        flight = request('POST','/api/v2/flights',json={'callsign':args.callsign})['flight_id']
        report = dict(input_kind='previous_microphone_wav_replay',flight_id=flight,
                      status=request('GET','/api/demo/status'), cases=[])
        for role, path in (('ATC',args.atc),('READBACK',args.readback)):
            data = path.read_bytes()
            with wave.open(io.BytesIO(data)) as wav:
                duration = wav.getnframes()/wav.getframerate()
            if role == "READBACK":
                time.sleep(duration + .6)  # Preserve the ATC -> pilot capture ordering on replay.
            now = datetime.now(timezone.utc)
            body = dict(audio=base64.b64encode(data).decode(),
                        started_at=(now-timedelta(seconds=duration+.5)).isoformat().replace("+00:00","Z"),
                        ended_at=(now-timedelta(seconds=.5)).isoformat().replace("+00:00","Z"))
            if role == 'ATC':
                body['input_mode']='file_upload'
            else:
                state = request('GET',f'/api/v2/flights/{flight}/state')
                if not state['readback_required']:
                    raise RuntimeError('Original ATC was not adopted; refusing invented target')
                body['atc_input_id']=state['readback_required']['atc_input_id']
            response = request('POST',f'/api/demo/{flight}/'+('atc' if role=='ATC' else 'readback'),json=body)
            state = request('GET',f'/api/v2/flights/{flight}/state')
            case=dict(role=role,sha256=hashlib.sha256(data).hexdigest(),response=response,state=state)
            report['cases'].append(case)
            (args.output/(role.lower()+'.json')).write_text(json.dumps(case,ensure_ascii=False,indent=2))
            print(json.dumps(dict(role=role,transcript=response['transcript'],
                entities=[{k:e[k] for k in ('label','text','source') if k in e} for e in (response.get('ner') or {}).get('entities',[])],
                structure=state['structure_checks'].get(role),
                readback=state['validation']['readback']['result']),ensure_ascii=False),flush=True)
        (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
