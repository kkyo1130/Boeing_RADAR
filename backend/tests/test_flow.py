import pytest

GOOD = {'altitude': 18000, 'heading': 240, 'confidence': .96}

def setup(client):
    response = client.post('/api/flights/start')
    assert response.status_code == 201
    f = response.json()['flight_id']
    response = client.post(f'/api/flights/{f}/clearances', json=GOOD)
    assert response.status_code == 201
    return f, response.json()['clearance_id']

def post(client, c, path, payload=GOOD):
    response = client.post(f'/api/clearances/{c}/{path}', json=payload)
    assert response.status_code == 200, response.text
    return response.json()

def test_verified_and_end(client):
    f, c = setup(client)
    assert post(client, c, 'readback')['status'] == 'WAITING_COCKPIT'
    assert post(client, c, 'cockpit')['status'] == 'VERIFIED'
    assert client.get(f'/api/clearances/{c}').json()['errors'] == []
    assert len(client.get(f'/api/flights/{f}/clearances').json()) == 1
    ended = client.post(f'/api/flights/{f}/end').json()
    assert ended['status'] == 'ENDED' and ended['ended_at']
    assert client.get(f'/api/flights/{f}').json() == ended
    assert client.post(f'/api/flights/{f}/clearances', json=GOOD).status_code == 409
    assert client.post(f'/api/flights/{f}/end').status_code == 409
    events = client.get(f'/api/flights/{f}/safety-trace').json()
    assert [e['event_type'] for e in events] == [
        'FLIGHT_STARTED', 'ATC_RECOGNIZED', 'READBACK_RECOGNIZED',
        'COCKPIT_RECOGNIZED', 'VERIFIED', 'FLIGHT_ENDED']
    assert [e['timestamp'] for e in events] == sorted(e['timestamp'] for e in events)

@pytest.mark.parametrize('source,field,wrong,status', [
    ('readback','altitude',16000,'READBACK_ERROR'),
    ('readback','heading',250,'READBACK_ERROR'),
    ('cockpit','altitude',16000,'SETTING_ERROR'),
    ('cockpit','heading',250,'SETTING_ERROR'),
])
def test_error_resolution(client, source, field, wrong, status):
    f, c = setup(client)
    if source == 'cockpit':
        post(client, c, 'readback')
    result = post(client, c, source, dict(GOOD, **{field: wrong}))
    assert result['status'] == status
    assert result['errors'][0]['actual'] == wrong
    result = post(client, c, source + '/reverify')
    assert result['status'] == 'RESOLVED' and result['errors'] == []
    events = client.get(f'/api/flights/{f}/safety-trace').json()
    names = [e['event_type'] for e in events]
    assert names.index(status) < names.index('ALERTED') < names.index('REVERIFYING') < names.index('RESOLVED')
    observations = [e['observation'] for e in events if e['observation'] and e['observation']['source'] == source.upper()]
    assert observations[0][field] == wrong and observations[-1][field] == GOOD[field]
    if source == 'readback':
        assert post(client, c, 'cockpit')['status'] == 'VERIFIED'

def test_guards_and_isolation(client):
    f, c = setup(client)
    other = client.post(f'/api/flights/{f}/clearances', json=dict(GOOD, altitude=20000)).json()['clearance_id']
    assert other != c
    assert client.post(f'/api/clearances/{c}/cockpit', json=GOOD).status_code == 409
    assert client.post(f'/api/clearances/{c}/readback/reverify', json=GOOD).status_code == 409
    post(client, c, 'readback')
    assert client.get(f'/api/clearances/{other}').json()['readback'] is None
    assert client.post(f'/api/clearances/{c}/readback', json=GOOD).status_code == 409
    assert client.get('/api/clearances/missing').status_code == 404
    assert client.get('/api/flights/missing/safety-trace').status_code == 404
    client.post(f'/api/flights/{f}/end')
    assert client.post(f'/api/clearances/{c}/cockpit', json=GOOD).status_code == 409

@pytest.mark.parametrize('payload', [dict(GOOD, heading=360), dict(GOOD, altitude=-1), dict(GOOD, confidence=1.1), dict(GOOD, altitude=18000.5), dict(GOOD, extra=1)])
def test_invalid_input(client, payload):
    f, _ = setup(client)
    assert client.post(f'/api/flights/{f}/clearances', json=payload).status_code == 422

def test_readback_priority_with_cockpit(client):
    _, c = setup(client)
    post(client, c, 'readback', dict(GOOD, altitude=16000))
    assert post(client, c, 'cockpit', dict(GOOD, heading=250))['status'] == 'READBACK_ERROR'
    assert post(client, c, 'readback/reverify')['status'] == 'SETTING_ERROR'
    assert post(client, c, 'cockpit/reverify')['status'] == 'RESOLVED'
