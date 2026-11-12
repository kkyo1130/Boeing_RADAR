"""Stored-event acceptance A-E, capability isolation and safe AI fallback."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from pypdf import PdfReader
from test_receiving_v2 import setup,scenario,Scenario
from test_validation_v2_api import match_readback,cockpit
from test_advisory_v2 import claim,result


def finish(s):
    assert s.client.post(s.url+'/end').status_code==200
    response=s.client.get(s.url+'/report');assert response.status_code==200,response.text
    return response.json()


def instruction180(s):
    atc=s.segment();data=s.speech(atc)
    data['transcript']='Radar one two three climb and maintain flight level one eight zero heading two seven zero'
    data['fields']['ALT'].update(value=18000,raw_text='FL180')
    assert s.send(data).status_code==201
    assert s.state()['targets']['ALT']['value']==18000
    return atc


def readback180(s,atc,altitude=18000):
    s.tick(.5);data=s.speech(s.segment(atc));text='one eight zero' if altitude==18000 else 'one six zero'
    data['transcript']=f'Radar one two three climb and maintain flight level {text} heading two seven zero'
    data['fields']['ALT'].update(value=altitude,raw_text='FL180' if altitude==18000 else 'FL160')
    assert s.send(data).status_code==201
    return data


def test_a_normal_flight_counts_and_english_pdf(scenario):
    s=scenario;atc=instruction180(s);readback180(s,atc);cockpit(s,altitude=18000)
    facts=finish(s)['safety']['summary']
    assert facts['instruction_count']==facts['normal_instruction_count']==1
    assert facts['incident_count']==facts['unresolved_count']==0 and facts['correction_rate'] is None
    pdf=s.client.get(s.url+'/report.pdf');assert pdf.status_code==200
    assert pdf.headers['content-type']=='application/pdf' and 'Flight_Safety_Report_' in pdf.headers['content-disposition']
    assert 'Boeing' not in pdf.headers['content-disposition']
    reader=PdfReader(BytesIO(pdf.content));text='\n'.join(p.extract_text() for p in reader.pages)
    assert 'Flight Summary' in text and 'AI Safety Summary' in text and 'Total ATC instructions' in text and s.flight in text
    import re
    assert not re.search(r'boeing[\s_]+radar',text,re.IGNORECASE)
    assert reader.metadata.title=='Flight Safety Report'
    assert reader.metadata.author in (None,'')
    assert not re.search(r'[가-힣]',text)
    assert len(reader.pages)>=2


def test_b_readback_error_duplicate_warning_and_correction(scenario):
    s=scenario;atc=instruction180(s);bad=readback180(s,atc,16000)
    assert s.state()['incidents'][0]['stage']=='READBACK'
    assert s.send(bad).status_code==200
    attempt=claim(s).json();assert result(s,attempt).json()['status']=='COMPLETED'
    readback180(s,atc);cockpit(s,altitude=18000)
    data=finish(s)['safety'];facts=data['summary']
    assert facts['incident_count']==facts['readback_error_count']==facts['resolved_count']==1
    assert facts['setting_error_count']==0 and facts['correction_rate']==1
    trace=data['correction_trace'][0]
    assert trace['state']=='RESOLVED' and trace['warning_completed']
    assert {'DETECTED','WARNED','RESOLVED'}<=set(step['state'] for step in trace['steps'])


def test_c_setting_error_fresh_correction_and_warning(scenario):
    s=scenario;atc=instruction180(s);readback180(s,atc)
    cockpit(s,altitude=16000);s.tick(5);assert s.client.post(s.url+'/revalidate').status_code==200
    attempt=claim(s).json();assert result(s,attempt).json()['status']=='COMPLETED'
    cockpit(s,altitude=18000);data=finish(s)['safety']
    assert data['summary']['setting_error_count']==data['summary']['resolved_count']==1
    row=data['correction_trace'][0]
    assert row['initial_actual']==16000 and row['final_actual']==row['expected']==18000
    assert row['resolved_at'] and row['warning_completed'] and any(e['warning_completed'] for e in data['timeline'])


def test_d_unreadable_after_error_remains_unresolved(scenario):
    s=scenario;atc=instruction180(s);readback180(s,atc)
    cockpit(s,altitude=16000);s.tick(5);s.client.post(s.url+'/revalidate')
    s.tick();payload=s.camera();payload['fields']['HDG'].update(value=270,raw_text='270');payload['fields']['ALT'].update(value=None,raw_text=None,validity='UNREADABLE',reason='blank_roi')
    assert s.send(payload).status_code==201
    data=finish(s)['safety'];assert data['summary']['incident_count']==data['summary']['unresolved_count']==1
    assert data['summary']['resolved_count']==0
    row=data['correction_trace'][0]
    assert row['state']=='UNRESOLVED' and row['verification']=='UNVERIFIED' and row['resolved_at'] is None
    assert not row['warning_completed']


def test_replaced_instruction_never_counts_as_correction(scenario):
    s=scenario;a=s.adopt();match_readback(s,a);cockpit(s);cockpit(s,altitude=2000)
    s.tick();s.adopt(partial=True);facts=finish(s)['safety']['summary']
    assert facts['incident_count']==facts['superseded_count']==facts['unresolved_count']==1
    assert facts['resolved_count']==0


def test_cross_browser_access_denied_all_report_formats(scenario):
    s=scenario;finish(s);owner=s.client.cookies.get('radar_report_owner');s.client.cookies.clear()
    other=Scenario(s.client,s.clock)
    for suffix in ['/report','/report.json','/report.pdf']:assert s.client.get(s.url+suffix).status_code==403
    assert s.client.get(other.url+'/report').status_code==200
    s.client.cookies.clear();s.client.cookies.set('radar_report_owner',owner)
    assert s.client.get(s.url+'/report.pdf').status_code==200
    assert s.client.get(other.url+'/report').status_code==403


def test_active_pdf_conflict_and_empty_flight_not_normal(scenario):
    s=scenario;assert s.client.get(s.url+'/report.pdf').status_code==409
    data=finish(s)['safety'];assert data['summary']['instruction_count']==data['summary']['normal_instruction_count']==0


def test_ai_failure_falls_back_frozen_pdf_survives(scenario,monkeypatch):
    s=scenario;atc=s.adopt();match_readback(s,atc);cockpit(s)
    monkeypatch.setenv('RADAR_REPORT_AI_URL','http://summary.invalid')
    with patch('app.services.reports.summary.httpx.Client') as ai_client:
        ai_client.return_value.__enter__.return_value.post.side_effect=TimeoutError
        report=finish(s)
    assert report['safety']['ai_summary']['source']=='RULE_BASED'
    assert report['safety']['ai_summary']['reason']=='AI_FAILED_OR_UNVERIFIED'
    s.tick(1000);assert s.client.get(s.url+'/report').json()==deepcopy(report)
    assert s.client.get(s.url+'/report.pdf').status_code==200


def test_summary_only_accepts_exact_server_fact_ids(monkeypatch):
    import httpx
    from app.services.reports.summary import summarize
    facts=dict(instruction_count=1,normal_instruction_count=0,unverified_instruction_count=1,incident_count=0,
        readback_error_count=0,setting_error_count=0,resolved_count=0,unresolved_count=0,superseded_count=0)
    monkeypatch.setenv('RADAR_REPORT_AI_URL','https://summary.example')
    def respond(self,url,**kwargs):
        return httpx.Response(200,json=dict(facts_digest=kwargs['json']['facts_digest'],fact_ids=['scope','corrections','errors','instructions']),request=httpx.Request('POST',url))
    with patch('httpx.Client.post',respond):assert summarize(facts,[])['source']=='AI_ASSISTED_FACTS'
    def invented(self,url,**kwargs):return httpx.Response(200,json={'fact_ids':['all_safe'],'facts_digest':'fake'},request=httpx.Request('POST',url))
    with patch('httpx.Client.post',invented):
        summary=summarize(facts,[]);assert summary['source']=='RULE_BASED' and 'all_safe' not in summary['text']


def test_access_code_exchange_requires_secret_and_never_leaks(scenario):
    s=scenario;finish(s);token=s.client.cookies.get('radar_report_owner');s.client.cookies.clear()
    assert s.client.post(s.url+'/report-access',json={'token':'0'*64}).status_code==403
    assert s.client.post(s.url+'/report-access',json={'token':token}).status_code==200
    response=s.client.get(s.url+'/report');assert response.status_code==200
    assert token not in response.text and token not in str(s.trace())


def test_long_korean_transcript_splits_across_pages(scenario):
    from app.services.reports.pdf import render_pdf
    s=scenario;atc=s.adopt();match_readback(s,atc);cockpit(s)
    safety=finish(s)['safety'];safety['timeline'][0]['transcript']='한글 긴 관제 기록 <문자> & 원문 보존. '*700
    safety['timeline'][0]['source']='ATC'
    pdf=render_pdf(safety);reader=PdfReader(BytesIO(pdf))
    text=''.join(p.extract_text() for p in reader.pages)
    assert len(reader.pages)>3 and '한글 긴 관제 기록' in text and 'AI Safety Summary' in text


def test_unresolved_pdf_contains_same_incident_and_verdict_as_json(scenario):
    s=scenario;atc=instruction180(s);readback180(s,atc)
    cockpit(s,altitude=16000);s.tick(5);s.client.post(s.url+'/revalidate')
    report=finish(s);assert report['safety']['summary']['unresolved_count']==1
    data=s.client.get(s.url+'/report.pdf');text=''.join(p.extract_text() for p in PdfReader(BytesIO(data.content)).pages)
    item=report['safety']['correction_trace'][0]
    assert item['occurrence_id'] in text and 'UNRESOLVED' in text
    assert '16000' in text and '18000' in text and '1 incident remains unresolved' in text


def test_legacy_korean_summary_is_rendered_in_english_without_mutation(scenario):
    import re
    from app.services.reports.pdf import render_pdf
    s=scenario;atc=s.adopt();match_readback(s,atc);cockpit(s)
    safety=finish(s)['safety'];safety['ai_summary'].pop('text_en',None)
    safety['ai_summary']['text']='기존에 저장된 한글 요약'
    safety['missing_data']='미수집 항목은 확인 불가입니다.'
    original=deepcopy(safety)
    pdf=render_pdf(safety);text=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert not re.search(r'[가-힣]',text)
    assert 'stored record contains 1 ATC instruction' in text
    assert safety==original
