"""Actual HTTP WAV -> local Whisper -> BERT/rules -> stored checks, no mocked ASR."""
import argparse,base64,json,time,wave,io
from datetime import datetime,timedelta,timezone
from pathlib import Path
import httpx

def times(start_ago=20, end_ago=1):
    now=datetime.now(timezone.utc)
    return {'started_at':(now-timedelta(seconds=start_ago)).isoformat().replace('+00:00','Z'),'ended_at':(now-timedelta(seconds=end_ago)).isoformat().replace('+00:00','Z')}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--server',default='http://127.0.0.1:8013');p.add_argument('--audio',type=Path,required=True);p.add_argument('--recorded-wav',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    c=httpx.Client(base_url=a.server,timeout=180)
    def request(method,url,**kw):
        r=c.request(method,url,**kw)
        if r.is_error:raise RuntimeError(f'{r.status_code}: {r.text}')
        return r.json()
    status=request('GET','/api/demo/status');assert status['ner_backend']=='bert-hybrid' and status['speech_ready']
    cases=[('generated_correct',(a.audio/'baseline.wav').read_bytes()),('generated_wrong_heading',(a.audio/'heading.wav').read_bytes())]
    b=io.BytesIO()
    with wave.open(b,'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*16000*3)
    cases.append(('silence',b.getvalue()))
    if a.recorded_wav:cases.append(('previous_user_microphone',a.recorded_wav.read_bytes()))
    reports=[]
    for name,data in cases:
        fid=request('POST','/api/v2/flights',json={'callsign':'RADAR123'})['flight_id']
        atc=request('POST',f'/api/demo/{fid}/scenario/baseline',json=times(40,35))
        state=request('GET',f'/api/v2/flights/{fid}/state')
        assert state['targets']['ALT'] and state['targets']['ALT']['value']==3000,(name,state)
        start=time.monotonic()
        rb=request('POST',f'/api/demo/{fid}/readback',json={**times(),'atc_input_id':state['readback_required']['atc_input_id'],'audio':base64.b64encode(data).decode()})
        state=request('GET',f'/api/v2/flights/{fid}/state')
        check=state['structure_checks'].get('READBACK') or {}
        comparison=state['validation'].get('readback') or {}
        if name=='generated_correct':
            assert check.get('result')=='PASS' and check.get('derived_values')=={'ALT':3000,'HDG':270},check
            assert comparison.get('result')=='NORMAL',comparison
        elif name=='generated_wrong_heading':
            assert check.get('derived_values')=={'ALT':3000,'HDG':290},check
            assert comparison.get('result')=='MISMATCH',comparison
        elif name=='silence':
            assert not rb['transcript'] and check.get('result')=='NEEDS_REVIEW',rb
        assert rb['ner']['model_version']=='bert-hybrid-rules-v3' or not rb['transcript']
        item={'case':name,'input_kind':'previous_real_microphone_recording' if name=='previous_user_microphone' else 'synthetic_audio_fixture','elapsed_seconds':time.monotonic()-start,'atc':atc,'readback':rb,'state':state}
        (a.output/(name+'.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2))
        reports.append({'case':name,'transcript':rb['transcript'],'quality_reason':rb['quality_reason'],'ner_issues':rb['ner']['issues'],'structure':state['structure_checks'].get('READBACK'),'readback_validation':state['validation'].get('readback'),'state_result':state['result'],'elapsed_seconds':item['elapsed_seconds']})
        print(json.dumps(reports[-1],ensure_ascii=False),flush=True)
    (a.output/'summary.json').write_text(json.dumps({'status':status,'cases':reports},ensure_ascii=False,indent=2))
    c.close()
if __name__=='__main__':main()
