"""WI-04 integrated server evidence; synthetic input is NOT device acceptance.

Optionally export the exact snapshots consumed by frontend acceptance tests.
No old run bundle is read as input or reused as evidence.
"""
import json
import os
from pathlib import Path
import time

from mock_producer import timestamp
from test_validation_regression_http import establish_normal


def send_camera(p, *, altitude=3000, heading=270, occluded=False):
    data=p.camera()
    data['fields']['ALT'].update(value=altitude,raw_text=str(altitude))
    data['fields']['HDG'].update(value=heading,raw_text=str(heading))
    if occluded:
        data['fields']['ALT'].update(value=None,raw_text=None,validity='UNREADABLE',reason='roi_occluded')
    p.send(data)
    return data


def claim(p):
    candidate=p.state()['voice']['candidates'][0]
    return p.request('POST',p.path+'/voice/claims',dict(attempt_id=p.identifier('playback'),candidate_id=candidate['candidate_id']),expected=201)


def finish(p, attempt, status='COMPLETED'):
    return p.request('POST',p.path+'/voice/attempts/'+attempt['attempt_id'],{'status':status})


def input_event(p, kind, action='BEGIN',token=None):
    token=token or p.identifier('input')
    p.request('POST',p.path+'/voice/inputs',dict(event_id=p.identifier('event'),token=token,kind=kind,action=action))
    return token


def capture(p, cases, name):
    value=p.state()
    cases.append({'name':name,'snapshot':value})
    return value


def export(p,cases):
    root=Path(os.environ.get('RADAR_INTERFACE_ACCEPTANCE_DIR',str(p.record_path.parent/'interface-acceptance')))
    root.mkdir(parents=True,exist_ok=True)
    bundle={'schema_version':'1','environment':'synthetic_http','run_id':p.run_id,
        'flight_id':p.flight_id,'captured_at':timestamp(),'cases':cases,
        'trace':p.trace(),'hardware_acceptance':False,
        'unexecuted':['SPEC-003-WI-05','SPEC-004-WI-04','physical_speaker_microphone_tail']}
    target=root/(p.run_id+'.json')
    assert not target.exists(), 'Refuse to replace earlier acceptance evidence'
    target.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')


def test_visibility_heading_priority_interrupt_only_second_sentence(producer):
    p=producer;cases=[];establish_normal(p)
    send_camera(p,heading=0,occluded=True)
    early=capture(p,cases,'visibility_before_five_seconds')
    assert early['validation']['setting']['fields'][0]['result']=='UNVERIFIED'
    assert [q['phrase_key'] for q in early['voice']['candidates']]==['HDG']
    # Real server clock, no production clock override/hidden time-travel endpoint.
    due=time.monotonic()+5.05
    while time.monotonic()<due:time.sleep(max(0,min(.1,due-time.monotonic())))
    ready=capture(p,cases,'visibility_and_heading_due')
    assert [q['phrase_key'] for q in ready['voice']['candidates']]==['VISIBILITY','HDG']
    first=claim(p);finish(p,first)
    second=claim(p);assert second['phrase_key']=='HDG'
    token=input_event(p,'ATC');finish(p,second,'INTERRUPTED')
    held=capture(p,cases,'atc_tail_held')
    assert held['voice']['inputs'] and held['voice']['history'][-2]['status']=='COMPLETED'
    p.request('POST',p.path+'/voice/claims',dict(attempt_id=p.identifier('blocked'),candidate_id=second['candidate_id']),expected=409)
    input_event(p,'ATC','END',token)
    again=claim(p);assert again['phrase_key']=='HDG';finish(p,again)
    final=capture(p,cases,'only_second_sentence_restarted')
    assert not final['voice']['candidates']
    assert [a['phrase_key'] for a in final['voice']['history']]==['VISIBILITY','HDG','HDG']
    assert [a['status'] for a in final['voice']['history']]==['COMPLETED','INTERRUPTED','COMPLETED']
    assert final['voice']['history'][-1]['occurrence_ids']==second['occurrence_ids']
    export(p,cases)


def test_camera_disconnect_no_old_normal_badge_available_needs_frame(producer):
    p=producer;cases=[];establish_normal(p);capture(p,cases,'initial_normal')
    p.health('DISCONNECTED')
    disconnected=capture(p,cases,'camera_disconnected')
    assert all(f['result']=='UNVERIFIED' and f['actual'] is None for f in disconnected['validation']['setting']['fields'])
    assert [q['phrase_key'] for q in disconnected['voice']['candidates']]==['CAMERA']
    a=claim(p);finish(p,a)
    p.health('DISCONNECTED');assert not p.state()['voice']['candidates']
    p.health('AVAILABLE')
    waiting=capture(p,cases,'camera_open_without_new_frame')
    assert 'CAMERA' in waiting['voice']['episodes'] and waiting['result']=='UNVERIFIED'
    assert not waiting['voice']['candidates']
    send_camera(p)
    restored=capture(p,cases,'fresh_frame_recovery_silent')
    assert restored['result']=='NORMAL' and not restored['voice']['episodes']
    assert not restored['voice']['candidates'] and len(restored['voice']['history'])==1
    p.health('DISCONNECTED')
    recurring=capture(p,cases,'new_disconnect_new_occurrence')
    assert recurring['voice']['candidates'][0]['occurrence_ids']!=a['occurrence_ids']
    p.request('POST',p.path+'/end')
    ended=capture(p,cases,'ended_no_playback')
    assert not ended['voice']['candidates'] and ended['status']=='ENDED'
    export(p,cases)


def test_evidence_matches_live_verdict_media_and_superseded_selection(producer,evidence_root):
    p=producer;cases=[];establish_normal(p)
    # Known generated fixture is passed through byte-for-byte; no OCR accuracy claim.
    image=(Path(__file__).resolve().parents[2]/'vision/evaluation/fixtures/changed.png').read_bytes()
    name=p.identifier('frame')+'.png';(evidence_root/name).write_bytes(image)
    data=p.camera();data['fields']['ALT'].update(value=3500,raw_text='3500');data['fields']['HDG'].update(value=290,raw_text='290')
    data.update(evidence_unavailable_reason=None,evidence_refs=[dict(evidence_id=p.identifier('image'),kind='FRAME',field=None,ref='media:'+name,roi=None)])
    p.send(data)
    state=capture(p,cases,'media_backed_mismatch')
    row=state['validation']['setting']['fields'][1]
    query='&'.join(f'{k}={row[k]}' for k in ['instruction_id','stage','field'])
    url=p.path+'/evidence/'+row['observation_id']+'?'+query
    meta=p.request('GET',url)
    assert meta['verdict']==row and meta['groups']['OBSERVED']['observation_id']==data['observation_id']
    asset=meta['groups']['OBSERVED']['assets'][0]
    response=p.client.get(asset['url']);assert response.status_code==200 and response.content==image
    event=dict(event_id=p.identifier('ack'),observation_id=row['observation_id'],instruction_id=row['instruction_id'],stage=row['stage'],field=row['field'],action='ACKNOWLEDGED')
    p.request('POST',p.path+'/interactions',event,expected=201)
    assert p.state()['incidents']==state['incidents']
    missing=p.camera();missing['fields']['ALT'].update(value=3500,raw_text='3500');missing['fields']['HDG'].update(value=290,raw_text='290');p.send(missing)
    assert p.request('GET',url,expected=409)['code']=='CONTEXT_MISMATCH'
    row2=p.state()['validation']['setting']['fields'][1]
    q2='&'.join(f'{k}={row2[k]}' for k in ['instruction_id','stage','field'])
    meta2=p.request('GET',p.path+'/evidence/'+row2['observation_id']+'?'+q2)
    assert meta2['groups']['OBSERVED']['evidence_unavailable_reason']=='fixture_has_no_media'
    cases[-1]['evidence']=meta
    capture(p,cases,'missing_media_does_not_resolve')
    send_camera(p)
    final=capture(p,cases,'new_sample_resolves_without_ack_prerequisite')
    assert all(i['status']=='RESOLVED' for i in final['incidents'])
    export(p,cases)
