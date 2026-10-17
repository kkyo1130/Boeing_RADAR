"""Real TCP/SQLite advisory ownership; synthetic producer, no devices."""
from test_validation_regression_http import establish_normal


def candidate(p):return p.state()['voice']['candidates'][0]
def mismatch(p):
    establish_normal(p);data=p.camera()
    data['fields']['ALT'].update(value=2000,raw_text='2000')
    data['fields']['HDG'].update(value=90,raw_text='90');p.send(data)
def claim(p):
    return p.request('POST',p.path+'/voice/claims',dict(attempt_id=p.identifier('voice'),candidate_id=candidate(p)['candidate_id']),expected=201)
def finish(p,a,status):return p.request('POST',p.path+'/voice/attempts/'+a['attempt_id'],dict(status=status))


def test_combined_completion_survives_requests_and_has_trace(producer):
    p=producer;mismatch(p);a=claim(p);assert a['phrase_key']=='BOTH'
    assert finish(p,a,'COMPLETED')['status']=='COMPLETED'
    assert not p.state()['voice']['candidates']
    assert all(i['status']=='OPEN' and i['voice_completed_at'] for i in p.state()['incidents'])
    assert finish(p,a,'COMPLETED')['attempt_id']==a['attempt_id']
    assert any(e['event_type']=='VOICE_RESULT' and e['snapshot']['result']['attempt_id']==a['attempt_id'] for e in p.trace())


def test_input_interrupt_tail_and_resolution_cancel_over_http(producer):
    p=producer;mismatch(p);a=claim(p)
    token=p.identifier('capture')
    p.request('POST',p.path+'/voice/inputs',dict(event_id=p.identifier('event'),token=token,kind='ATC',action='BEGIN'))
    assert p.state()['voice']['active_attempt']['cancel_requested']
    assert finish(p,a,'INTERRUPTED')['status']=='INTERRUPTED'
    p.request('POST',p.path+'/voice/claims',dict(attempt_id=p.identifier('blocked'),candidate_id=candidate(p)['candidate_id']),expected=409)
    p.request('POST',p.path+'/voice/inputs',dict(event_id=p.identifier('event'),token=token,kind='ATC',action='END'))
    b=claim(p);assert b['occurrence_ids']==a['occurrence_ids']
    data=p.camera();data['fields']['HDG'].update(value=270,raw_text='270');p.send(data)
    assert finish(p,b,'COMPLETED')['status']=='CANCELLED'
    assert not p.state()['voice']['candidates']
