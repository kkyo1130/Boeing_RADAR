"""PDF instruction provenance and complete-log acceptance, using a temporary DB."""
from copy import deepcopy
from io import BytesIO

from pypdf import PdfReader
from test_receiving_v2 import setup, scenario
from test_validation_v2_api import match_readback, cockpit
from test_flight_safety_report import finish
from app.services.reports.register import instruction_register
from app.services.reports.pdf import render_pdf


def project(data):
    return instruction_register(data['safety'], data['timeline'])


def test_partial_instruction_keeps_field_owner_and_observation_provenance(scenario):
    s = scenario
    first = s.adopt(); match_readback(s, first); cockpit(s)
    s.tick(); second = s.adopt(partial=True)
    s.tick(); assert s.send(s.speech(s.segment(second), partial=True)).status_code == 201
    cockpit(s, altitude=4000)
    data = finish(s); before = deepcopy(data); rows = project(data)['items']
    assert [(r['instruction_id'], r['field']) for r in rows] == [
        (first['instruction_id'], 'ALT'), (first['instruction_id'], 'HDG'),
        (second['instruction_id'], 'ALT')]
    assert rows[1]['expected'] == 270 and rows[2]['expected'] == 4000
    assert rows[2]['readback']['actual'] == 4000
    assert rows[2]['readback']['observed_at']
    assert data == before


def test_unreadable_and_stale_do_not_inherit_historical_normal(scenario):
    s = scenario; atc = s.adopt(); match_readback(s, atc); cockpit(s)
    s.tick(); camera = s.camera()
    camera['fields']['HDG'].update(value=270, raw_text='270')
    camera['fields']['ALT'].update(value=None, raw_text=None, validity='UNREADABLE', reason='blank_roi')
    assert s.send(camera).status_code == 201
    s.tick(20); s.client.post(s.url+'/revalidate')
    data = finish(s); rows = project(data)['items']
    assert data['safety']['summary']['normal_instruction_count'] == 1
    assert all(r['cockpit']['result'] == 'UNVERIFIED' for r in rows)
    pdf = s.client.get(s.url+'/report.pdf')
    text = ''.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert 'UNVERIFIED' in text and 'STALE' in text


def test_recurrence_keeps_all_incidents_and_original_mismatch_values(scenario):
    s = scenario; atc = s.adopt(); match_readback(s, atc); cockpit(s)
    cockpit(s, heading=90); cockpit(s); cockpit(s, heading=90)
    data = finish(s); row = next(r for r in project(data)['items'] if r['field']=='HDG')
    assert len(row['incidents']) == 2
    assert {i['state'] for i in row['incidents']} == {'RESOLVED', 'UNRESOLVED'}
    reader = PdfReader(BytesIO(s.client.get(s.url+'/report.pdf').content))
    log = ''.join(page.extract_text() for page in reader.pages[1:])
    assert all(i['occurrence_id'] in log for i in row['incidents'])
    assert 'Warning playback completed: Not recorded' in log


def test_many_items_have_one_summary_and_complete_paginated_log(scenario):
    s = scenario
    for _ in range(14):
        atc = s.adopt(); match_readback(s, atc); cockpit(s); s.tick()
    data = finish(s); before = deepcopy(data)
    pdf = s.client.get(s.url+'/report.pdf')
    reader = PdfReader(BytesIO(pdf.content))
    assert 'OVERALL FLIGHT SUMMARY' in reader.pages[0].extract_text()
    assert 'Complete instruction register' in reader.pages[1].extract_text()
    assert len(project(data)['items']) == 28
    log = ''.join(page.extract_text() for page in reader.pages[1:])
    assert all(f'I{n:03}' in log for n in range(1,29))
    assert 'Incheon' not in log and 'Departure' not in log
    assert data == before and s.client.get(s.url+'/report').json() == data


def test_more_than_three_incidents_are_bounded_only_in_summary(scenario):
    s = scenario; atc = s.adopt(); match_readback(s, atc); cockpit(s)
    for _ in range(6):
        cockpit(s, heading=90); cockpit(s)
    data = finish(s)
    reader = PdfReader(BytesIO(s.client.get(s.url+'/report.pdf').content))
    assert 'Showing 3 of 6 incidents' in reader.pages[0].extract_text()
    assert 'Complete instruction register' in reader.pages[1].extract_text()
    log = ''.join(page.extract_text() for page in reader.pages[1:])
    assert all(i['occurrence_id'] in log for i in data['safety']['correction_trace'])


def test_missing_legacy_provenance_and_callsign_incident_remain_visible(scenario):
    s = scenario; atc = s.adopt(); match_readback(s, atc); cockpit(s, heading=90)
    s.tick(5); s.client.post(s.url+'/revalidate'); data=finish(s)
    safety=deepcopy(data['safety']); incident=safety['correction_trace'][0]
    incident['field']='CALLSIGN'; incident['initial_actual']='OTHER123'
    original=deepcopy(safety)
    projection=instruction_register(safety)
    assert projection['orphan_incidents'][0]['field']=='CALLSIGN'
    assert all(r['cockpit'].get('observed_at') is None for r in projection['items'])
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(safety))).pages)
    assert 'Additional recorded incidents' in text and 'OTHER123' in text
    assert safety==original


def test_same_clock_inputs_link_by_observation_id_and_zero_is_not_missing(scenario):
    s=scenario; atc=s.adopt(); match_readback(s,atc); cockpit(s,heading=90); cockpit(s,heading=0)
    data=finish(s); row=next(r for r in project(data)['items'] if r['field']=='HDG')
    assert row['cockpit']['actual']==0
    oid=row['cockpit']['observation_id']
    source=next(r for r in data['observations'] if r['input_id']==oid)
    assert row['cockpit']['observed_at']==source['payload']['observed_at']


def test_empty_flight_and_rejected_atc_do_not_create_register_items(scenario):
    s=scenario; segment=s.segment(complete=False)
    assert s.send(s.speech(segment)).status_code==201
    data=finish(s); assert project(data)['items']==[]
    reader=PdfReader(BytesIO(s.client.get(s.url+'/report.pdf').content))
    assert len(reader.pages)==2
    assert 'No applied ALT/HDG instruction items' in reader.pages[1].extract_text()
