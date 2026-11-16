from io import BytesIO
from PIL import Image
from test_receiving_v2 import Scenario, setup, scenario
from test_validation_v2_api import match_readback, cockpit


def png():
    data = BytesIO()
    Image.new('RGB', (20, 20), 'white').save(data, format='PNG')
    return data.getvalue()


def test_report_freezes_last_live_decision(scenario):
    s=scenario
    atc=s.adopt(); match_readback(s,atc); cockpit(s); cockpit(s,heading=90)
    assert s.state()['result']=='MISMATCH'
    cockpit(s)
    assert s.client.post(s.url+'/end').status_code==200
    report=s.client.get(s.url+'/report').json()
    assert report['schema_version']=='radar-report/2'
    assert report['terminal'] and report['snapshot']['result']=='NORMAL'
    assert report['summary']['resolved']==1 and report['summary']['open']==0
    assert report['timeline'][-1]['event_type']=='FLIGHT_ENDED'
    assert s.state()['result']=='UNVERIFIED'
    s.tick(100)
    assert s.client.get(s.url+'/report').json()==report
    exported=s.client.get(s.url+'/report.json')
    assert 'attachment' in exported.headers['content-disposition']
    assert exported.json()==report


def test_upload_existing_panel_and_scoped_delete(scenario):
    s=scenario
    atc=s.adopt(); match_readback(s,atc)
    upload=s.client.post(s.url+'/media',content=png(),headers={'Content-Type':'image/png'})
    assert upload.status_code==201,upload.text
    ref=upload.json(); s.tick(); data=s.camera()
    data.update(evidence_refs=[dict(**ref,kind='FRAME',field='ALT',roi=None)],evidence_unavailable_reason=None)
    assert s.send(data).status_code==201
    params=dict(instruction_id=atc['instruction_id'],stage='SETTING',field='ALT')
    url=s.url+'/evidence/'+data['observation_id']
    metadata=s.client.get(url,params=params)
    assert metadata.status_code==200,metadata.text
    asset=metadata.json()['groups']['OBSERVED']['assets'][0]
    assert s.client.get(asset['url']).content==png()
    other=Scenario(s.client,s.clock)
    assert s.client.delete(other.url+'/media/'+ref['evidence_id']).status_code==404
    assert s.client.delete(s.url+'/media/'+ref['evidence_id']).status_code==200
    assert s.client.get(asset['url']).status_code==410
    assert s.client.get(url,params=params).json()['groups']['OBSERVED']['assets'][0]['url'] is None
    assert s.trace()[-1]['event_type']=='EVIDENCE_DELETED'
    assert s.state()['current']['COCKPIT']['ALT']['observation_id']==data['observation_id']


def test_media_rejects_bad_bytes_and_closed_flight(scenario):
    s=scenario
    assert s.client.post(s.url+'/media',content=b'not image',headers={'Content-Type':'image/png'}).status_code==422
    assert s.client.post(s.url+'/media',content=b'<script>',headers={'Content-Type':'text/html'}).status_code==415
    assert s.client.post(s.url+'/end').status_code==200
    assert s.client.post(s.url+'/media',content=png(),headers={'Content-Type':'image/png'}).status_code==409


def test_no_parallel_v1_routes(client):
    paths=client.get('/openapi.json').json()['paths']
    assert not any(path.startswith('/api/v1') for path in paths)
    assert '/api/v2/flights/{flight_id}/report' in paths
    assert '/api/flights/start' in paths


def test_poll_and_revalidation_do_not_duplicate_incident_or_frozen_end(scenario):
    s=scenario
    atc=s.adopt();match_readback(s,atc);cockpit(s);cockpit(s,heading=90)
    initial=s.state()
    assert len(initial['incidents']) == 1
    for _ in range(10):
        assert s.client.post(s.url+'/revalidate').status_code == 200
        assert len(s.state()['incidents']) == 1
    assert s.client.post(s.url+'/end').status_code == 200
    frozen=s.client.get(s.url+'/report').json()
    assert s.client.post(s.url+'/end').status_code == 200
    assert s.client.get(s.url+'/report').json() == frozen
    assert sum(e['event_type']=='FLIGHT_ENDED' for e in frozen['timeline']) == 1


def test_unchanged_revalidation_does_not_write_trace(scenario):
    from sqlalchemy import select
    from app.models.observation_v2 import V2TraceEvent
    s=scenario
    s.client.post(s.url+'/revalidate')
    from contextlib import contextmanager
    from app.main import app
    from app.db import get_db
    with contextmanager(app.dependency_overrides[get_db])() as db:
        before=len(list(db.scalars(select(V2TraceEvent))))
    for _ in range(5):
        assert s.client.post(s.url+'/revalidate').status_code==200
    from contextlib import contextmanager
    from app.main import app
    from app.db import get_db
    with contextmanager(app.dependency_overrides[get_db])() as db:
        assert len(list(db.scalars(select(V2TraceEvent))))==before


def test_timer_persists_expiry_without_any_poll(scenario):
    from contextlib import contextmanager
    from app.main import app
    from app.db import get_db
    from app.services.timer_v2 import tick
    from app.models.observation_v2 import V2FlightContext
    s=scenario
    atc=s.adopt();match_readback(s,atc);cockpit(s)
    s.tick(200)
    tick(app.dependency_overrides[get_db])
    with contextmanager(app.dependency_overrides[get_db])() as db:
        profile=db.get(V2FlightContext,s.flight)
        assert profile.state['validation_snapshot']['result']=='UNVERIFIED'
