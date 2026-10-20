"""Virtual-clock queue/input/occurrence contracts, no hardware claims."""
from uuid import uuid4
from test_receiving_v2 import setup, scenario
from test_validation_v2_api import match_readback, cockpit


def queue(s):return s.state()['voice']['candidates']
def claim(s, candidate=None, attempt=None):
    return s.client.post(s.url+'/voice/claims', json=dict(attempt_id=attempt or uuid4().hex, candidate_id=(candidate or queue(s)[0])['candidate_id']))
def result(s, attempt, status='COMPLETED'):
    return s.client.post(s.url+'/voice/attempts/'+attempt['attempt_id'], json=dict(status=status))
def control(s,kind='ATC',action='BEGIN',token=None,event=None):
    return s.client.post(s.url+'/voice/inputs',json=dict(event_id=event or uuid4().hex,token=token or uuid4().hex,kind=kind,action=action))
def normal(s):
    a=s.adopt();match_readback(s,a);cockpit(s);return a


def test_combined_sentence_once_then_only_new_heading_and_recurrence(scenario):
    s=scenario;normal(s);cockpit(s,altitude=2000,heading=90)
    assert [q['phrase_key'] for q in queue(s)]==['BOTH']
    a=claim(s).json();assert result(s,a).json()['status']=='COMPLETED'
    assert not queue(s)
    cockpit(s,altitude=1900,heading=80);assert not queue(s)
    cockpit(s);cockpit(s,heading=90)
    assert [q['phrase_key'] for q in queue(s)]==['HDG']
    assert all(i['voice_completed_at'] for i in s.state()['incidents'][:2])


def test_alt_completed_then_heading_does_not_repeat_alt(scenario):
    s=scenario;normal(s);cockpit(s,altitude=2000)
    a=claim(s).json();assert a['phrase_key']=='ALT';result(s,a)
    cockpit(s,altitude=2000,heading=90)
    assert [q['phrase_key'] for q in queue(s)]==['HDG']


def test_input_tail_suppression_interrupt_and_whole_sentence_retry(scenario):
    s=scenario;normal(s);cockpit(s,heading=90);a=claim(s).json()
    c=control(s).json();assert s.state()['voice']['active_attempt']['cancel_requested']
    assert claim(s).status_code==409
    assert result(s,a,'INTERRUPTED').json()['status']=='INTERRUPTED'
    assert claim(s).status_code==409
    assert control(s,action='END',token=c['token']).status_code==200
    b=claim(s).json();assert b['text']==a['text'] and b['attempt_id']!=a['attempt_id']
    assert result(s,b).json()['status']=='COMPLETED';assert not queue(s)


def test_blocked_capture_not_queued_and_input_idempotency(scenario):
    s=scenario;c=control(s,kind='PILOT',event='event1',token='token1')
    assert c.status_code==200
    assert control(s,kind='ATC').status_code==409
    assert control(s,kind='PILOT',event='event1',token='token1').json()==c.json()
    assert len(s.state()['voice']['inputs'])==1
    assert control(s,kind='ATC',event='event1',token='token1').status_code==409


def test_superseded_sentence_never_completes_and_retained_heading_survives(scenario):
    s=scenario;normal(s);cockpit(s,altitude=2000,heading=90);a=claim(s).json()
    s.tick();b=s.adopt(partial=True)
    assert not queue(s)
    assert result(s,a).json()['status']=='CANCELLED'
    match_readback(s,b,partial=True);cockpit(s,altitude=4000,heading=90)
    assert [q['phrase_key'] for q in queue(s)]==['HDG']


def test_stale_and_resolution_cancel_without_false_completion(scenario):
    s=scenario;normal(s);cockpit(s,heading=90);a=claim(s).json();cockpit(s)
    assert result(s,a).json()['status']=='CANCELLED';assert not queue(s)
    cockpit(s,heading=90);a=claim(s).json();s.tick(11)
    assert result(s,a).status_code==409
    assert not queue(s);assert not s.state()['incidents'][-1]['voice_completed_at']


def test_failure_and_expiry_never_complete_single_claim_and_retry_ids(scenario):
    s=scenario;normal(s);cockpit(s,heading=90);candidate=queue(s)[0]
    a=claim(s,candidate,attempt='attempt1').json()
    assert claim(s,candidate,attempt='attempt1').json()==a
    assert claim(s,candidate).status_code==409
    assert result(s,a,'FAILED').json()['status']=='FAILED'
    assert queue(s);assert not s.state()['incidents'][0]['voice_completed_at']
    b=claim(s).json();s.tick(10);s.client.post(s.url+'/revalidate')
    assert s.state()['voice']['history'][-1]['reason']=='LEASE_EXPIRED'
    assert result(s,b).status_code==409


def occlude(s, reason='roi_occluded'):
    s.tick(.25);data=s.camera()
    for f in data['fields'].values():f.update(value=None,validity='UNREADABLE',reason=reason,raw_text=None)
    r=s.send(data);assert r.status_code==201,r.text


def test_visibility_exact_five_seconds_recovery_and_no_generic_blank_guidance(scenario):
    s=scenario;normal(s);occlude(s,'blank_roi');s.tick(5);assert not queue(s)
    occlude(s);assert not queue(s);s.tick(4.999);assert not queue(s)
    s.tick(.001);assert [q['phrase_key'] for q in queue(s)]==['VISIBILITY']
    a=claim(s).json();result(s,a);assert not queue(s)
    s.tick(6);assert not queue(s)
    cockpit(s);occlude(s);s.tick(5)
    assert queue(s)[0]['occurrence_ids']!=a['occurrence_ids']


def test_camera_immediate_once_available_not_recovery_new_frame_silent(scenario):
    s=scenario;normal(s);s.tick();s.health()
    a=claim(s).json();assert a['phrase_key']=='CAMERA';result(s,a)
    s.tick();s.health('AVAILABLE');assert not queue(s)
    assert 'CAMERA' in s.state()['voice']['episodes']
    cockpit(s);assert 'CAMERA' not in s.state()['voice']['episodes'];assert not queue(s)
    s.tick();s.health();assert queue(s)[0]['occurrence_ids']!=a['occurrence_ids']


def test_visibility_first_but_not_yet_due_does_not_delay_heading(scenario):
    s=scenario;normal(s);cockpit(s,heading=90)
    s.tick(.1);data=s.camera();data['fields']['ALT'].update(value=None,validity='UNREADABLE',reason='roi_occluded',raw_text=None)
    data['fields']['HDG'].update(value=90,raw_text='90');s.send(data)
    assert [q['phrase_key'] for q in queue(s)]==['HDG']
    s.tick(5);assert [q['phrase_key'] for q in queue(s)]==['VISIBILITY','HDG']
    a=claim(s).json();result(s,a);b=claim(s).json();result(s,b,'INTERRUPTED')
    assert [q['phrase_key'] for q in queue(s)]==['HDG']


def test_ended_flight_cancels_and_other_flight_cannot_report(scenario,setup):
    from test_receiving_v2 import Scenario
    s=scenario;normal(s);cockpit(s,heading=90);a=claim(s).json()
    other=Scenario(setup[0],setup[1]);assert result(other,a).status_code==404
    s.client.post(s.url+'/end');assert result(s,a).json()['status']=='CANCELLED';assert not queue(s)


def test_failed_transaction_leaves_no_voice_history_or_completion(scenario, monkeypatch):
    from sqlalchemy.orm import Session
    import pytest
    s=scenario;normal(s);cockpit(s,heading=90);a=claim(s).json();before=s.state();trace=s.trace()
    def fail(self):raise RuntimeError('commit failure')
    monkeypatch.setattr(Session,'commit',fail)
    with pytest.raises(RuntimeError):result(s,a)
    assert s.state()==before and s.trace()==trace


def test_colon_attempt_id_and_expired_reservation_can_be_replaced(scenario):
    s=scenario;normal(s);cockpit(s,heading=90)
    a=claim(s,attempt='attempt:one').json();assert result(s,a,'FAILED').json()['status']=='FAILED'
    b=claim(s).json();s.tick(10)
    # No background revalidate required: GET exposes expiry, claim persists it.
    assert s.state()['voice']['active_attempt']['lease_expired']
    cockpit(s,heading=90)
    c=claim(s).json();assert c['attempt_id']!=b['attempt_id']
    assert s.state()['voice']['history'][-2]['status']=='INTERRUPTED'


def test_readback_guidance_unknown_input_and_strict_playback_dto(scenario):
    s=scenario;a=s.adopt();s.tick();data=s.speech(s.segment(a))
    data['transcript']='Radar one two three maintain four thousand feet heading two seven zero'
    data['fields']['ALT'].update(value=4000,raw_text='4000');assert s.send(data).status_code==201
    assert queue(s)[0]['phrase_key']=='READBACK'
    item=claim(s).json()
    assert s.client.post(s.url+'/voice/attempts/'+item['attempt_id'],json={'status':'COMPLETED','resolve':True}).status_code==422
    assert result(s,item,'COMPLETED').json()['status']=='COMPLETED'
    assert s.state()['incidents'][0]['status']=='OPEN'


def test_claim_cannot_skip_first_priority_sentence(scenario):
    s=scenario;normal(s);cockpit(s,heading=90)
    s.tick(.1);data=s.camera();data['fields']['ALT'].update(value=None,validity='UNREADABLE',reason='roi_occluded',raw_text=None)
    data['fields']['HDG'].update(value=90,raw_text='90');s.send(data);s.tick(5)
    assert len(queue(s))==2
    assert claim(s,queue(s)[1]).status_code==409


def test_two_clients_cannot_claim_the_same_sentence_concurrently(scenario):
    from concurrent.futures import ThreadPoolExecutor
    s=scenario;normal(s);cockpit(s,heading=90);candidate=queue(s)[0]
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses=list(executor.map(lambda _:claim(s,candidate).status_code,range(2)))
    assert sorted(statuses)==[201,409]


def test_evidence_cannot_begin_during_capture_or_atc_tail(scenario):
    s=scenario
    for kind in ['ATC','PILOT']:
        c=control(s,kind=kind).json()
        assert control(s,kind='EVIDENCE').status_code==409
        assert len(s.state()['voice']['inputs'])==1
        assert control(s,kind=kind,action='END',token=c['token']).status_code==200
    assert control(s,kind='EVIDENCE').status_code==200
