"""Replay saved human speech through the live-demo API; not a new hardware recording.
Expected fixture: RADAR123, climb and maintain 3000 feet, heading 270.
The expected values are checked AFTER inference, never sent as recognition hints.
"""
import argparse,base64,hashlib,io,json,wave
from datetime import datetime,timedelta,timezone
from pathlib import Path
import httpx

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server',default='http://127.0.0.1:8018')
    p.add_argument('--wav',type=Path,required=True)
    p.add_argument('--wrong-heading-wav',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();reports=[]
    def body(data,**extra):
        now=datetime.now(timezone.utc)
        with wave.open(io.BytesIO(data)) as w:duration=w.getnframes()/w.getframerate()
        return dict(audio=base64.b64encode(data).decode(),started_at=(now-timedelta(seconds=duration+1)).isoformat().replace('+00:00','Z'),ended_at=(now-timedelta(seconds=1)).isoformat().replace('+00:00','Z'),**extra)
    with httpx.Client(base_url=a.server,timeout=180) as c:
        def call(path,data=None):
            r=c.get(path) if data is None else c.post(path,json=data)
            if r.is_error: raise RuntimeError(f'{r.status_code}: {r.text}')
            return r.json()
        status=call('/api/demo/status')
        assert status['speech_ready'] and status['ner_backend']=='bert-hybrid'
        assert not status['callsign_context_enabled'], 'This test expects unbiased ASR; context still requires review.'
        raw=a.wav.read_bytes()
        fid=call('/api/v2/flights',dict(callsign='RADAR123'))['flight_id']
        atc=call(f'/api/demo/{fid}/atc',body(raw,input_mode='microphone_live'))
        state=call(f'/api/v2/flights/{fid}/state')
        reports.append(dict(case='saved_human_as_controller',response=atc,state=state))
        assert state['targets']['ALT']['value']==3000 and state['targets']['HDG']['value']==270,atc
        assert not atc['quality_reason'],atc
        for name,data,expected in [('same_saved_human_readback',raw,'NORMAL'),('synthetic_wrong_heading',a.wrong_heading_wav.read_bytes(),'MISMATCH')]:
            # Replaying a saved file is instantaneous. Use ordered synthetic capture
            # times for this API test, not the original recording's acquisition time.
            b=body(data,atc_input_id=atc['atc_input_id'])
            now=datetime.now(timezone.utc)
            b.update(started_at=(now-timedelta(seconds=.5)).isoformat().replace('+00:00','Z'),ended_at=(now-timedelta(seconds=.1)).isoformat().replace('+00:00','Z'))
            rb=call(f'/api/demo/{fid}/readback',b)
            state=call(f'/api/v2/flights/{fid}/state')
            reports.append(dict(case=name,response=rb,state=state))
            assert state['validation']['readback']['result']==expected,rb
        buf=io.BytesIO()
        with wave.open(buf,'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*16000)
        b=body(buf.getvalue(),input_mode='microphone_live')
        now=datetime.now(timezone.utc)
        b.update(started_at=(now-timedelta(seconds=.5)).isoformat().replace('+00:00','Z'),ended_at=(now-timedelta(seconds=.1)).isoformat().replace('+00:00','Z'))
        silent=call(f'/api/demo/{fid}/atc',b)
        state=call(f'/api/v2/flights/{fid}/state')
        reports.append(dict(case='silent_new_controller',response=silent,state=state))
        assert silent['quality_reason'] and state['validation']['reason']=='LATEST_ATC_NOT_ADOPTED'
        old=body(raw,atc_input_id=atc['atc_input_id'])
        assert c.post(f'/api/demo/{fid}/readback',json=old).status_code==409
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(dict(input_kind='saved_human_audio_replay_with_synthetic_request_times',wav_sha256=hashlib.sha256(raw).hexdigest(),status=status,cases=reports),ensure_ascii=False,indent=2))
        for item in reports:
            print(item['case'],item['response']['transcript'],item['response']['quality_reason'],item['state']['validation']['readback']['result'])
if __name__=='__main__':main()
