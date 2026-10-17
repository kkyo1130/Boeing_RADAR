"""Public HTTP linkage and user-event receipts with no backend imports."""
from copy import deepcopy
from test_validation_regression_http import establish_normal


def mismatch(p):
    establish_normal(p)
    data = p.camera(); data['fields']['HDG'].update(value=90,raw_text='90'); p.send(data)
    return p.state()['validation']['setting']['fields'][1]


def test_panel_ack_idempotency_and_new_sample_resolution_over_http(producer):
    p = producer; row = mismatch(p)
    context = {key:row[key] for key in ('instruction_id','stage','field')}
    query = '&'.join(f'{key}={value}' for key,value in context.items())
    endpoint = p.path+'/evidence/'+row['observation_id']+'?'+query
    panel = p.request('GET',endpoint)
    assert panel['verdict']['actual']==90 and panel['groups']['ATC']['reading']['value']==270
    before = p.state()
    event = dict(event_id=p.identifier('ack'),observation_id=row['observation_id'],action='ACKNOWLEDGED',**context)
    receipt = p.request('POST',p.path+'/interactions',event,expected=201)
    assert p.request('POST',p.path+'/interactions',event)==receipt
    after = p.state()
    assert after['incidents']==before['incidents'] and after['validation']==before['validation']
    assert any(e['event_id']==receipt['event_id'] and e['event_type']=='USER_ACKNOWLEDGED' for e in p.trace())
    fixed=p.camera();fixed['fields']['HDG'].update(value=270,raw_text='270');p.send(fixed)
    assert p.state()['incidents'][0]['status']=='RESOLVED'
    assert p.request('GET',endpoint,expected=409)['code']=='CONTEXT_MISMATCH'


def test_other_flight_and_conflicting_interaction_cannot_mix_evidence(producer):
    p=producer;row=mismatch(p)
    context={key:row[key] for key in ('instruction_id','stage','field','observation_id')}
    event=dict(event_id=p.identifier('view'),action='EVIDENCE_OPENED',**context)
    p.request('POST',p.path+'/interactions',event,expected=201)
    conflict=deepcopy(event);conflict['action']='ACKNOWLEDGED'
    assert p.request('POST',p.path+'/interactions',conflict,expected=409)['code']=='ID_CONTENT_CONFLICT'
    other=p.request('POST','/api/v2/flights',{'callsign':'RADAR123'},expected=201)['flight_id']
    assert p.request('POST',f'/api/v2/flights/{other}/interactions',event,expected=409)['code']=='CONTEXT_MISMATCH'
