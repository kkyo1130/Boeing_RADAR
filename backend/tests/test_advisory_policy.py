from datetime import timedelta
from test_three_state_decision import rig, settings, data, send


def test_voice_denied_by_default_suppression_and_freshness(rig):
    client, clock, flight, c = rig
    settings(rig)
    send(rig, data(rig, 'ATC'))
    send(rig, data(rig, 'READBACK', heading=290))
    report = client.get(f'/api/v1/flights/{flight}/report').json()
    incident = report['incidents'][0]['incident_id']
    path = f'/api/v1/incidents/{incident}/actions'
    payload = {'action': 'VOICE_REQUESTED', 'actor': 'test', 'reason': 'enabled'}
    assert client.post(path, json=payload).status_code == 409
    policy = {'actor': 'test', 'voice_enabled': True, 'critical_phase': True, 'radio_active': False}
    assert client.post(f'/api/v1/flights/{flight}/advisory-policy', json=policy).status_code == 200
    assert client.post(path, json=payload).status_code == 409
    policy['critical_phase'] = False
    client.post(f'/api/v1/flights/{flight}/advisory-policy', json=policy)
    assert client.post(path, json=payload).json()['recorded']
    assert not client.post(path, json=payload).json()['recorded']
    activity = {'channel_id': 'pilot-microphone', 'active': True, 'lease_seconds': 3}
    assert client.post(f'/api/v1/flights/{flight}/input-activity', json=activity).status_code == 200
    assert client.get(f'/api/v1/flights/{flight}/report').json()['input_active']
    assert client.post(path, json={**payload, 'action': 'VOICE_PLAYED'}).status_code == 409
    clock[0] += timedelta(seconds=4)
    assert not client.get(f'/api/v1/flights/{flight}/report').json()['input_active']
    assert client.post(path, json={**payload, 'action': 'VOICE_PLAYED'}).json()['recorded']
    policy['radio_active'] = True
    client.post(f'/api/v1/flights/{flight}/advisory-policy', json=policy)
    assert client.post(path, json={**payload, 'action': 'VOICE_PLAYED'}).status_code == 409
    policy['radio_active'] = False
    client.post(f'/api/v1/flights/{flight}/advisory-policy', json=policy)
    clock[0] += timedelta(seconds=31)
    assert client.post(path, json={**payload, 'action': 'VOICE_PLAYED'}).status_code == 409
    client.post(f'/api/v1/flights/{flight}/refresh')
    report = client.get(f'/api/v1/flights/{flight}/report').json()
    assert report['timeline'][-1]['kind'] == 'DECISION'
    assert report['timeline'][-1]['data']['decision']['verdict'] == 'UNVERIFIED'
