import json
import os
from pathlib import Path
import pytest
from app.services.speech.ner import assemble, extract_atc, ExtractionError, check_candidates
from app.services.speech.hybrid import fuse, BertHybridExtractor
from app.services.speech.hybrid_baseline import rules
from app.services.speech.hybrid_rules import refine_rules, spans
from app.services.demo.adapters import speech_payload


def fake(text, callsign_words):
    tags=['B-CALLSIGN']+['I-CALLSIGN']*(callsign_words-1)+['O']*(len(text.split())-callsign_words)
    return assemble(text,tags,[.9]*len(tags))


def test_rules_scores_are_not_bert_probabilities_and_offsets_preserved():
    t='Radar one two three maintain 3,000 feet heading 270.'
    out=fuse(t,fake(t,4))
    assert [(e['label'],e['text']) for e in out['entities'] if e['label'] in {'ALT','HDG'}]==[('ALT','3,000 feet'),('HDG','270.')]
    for e in out['entities']:
        assert t[e['start']:e['end']]==e['text']
        assert (e['model_score'] is None)==(e['source']=='rule')
    assert check_candidates(out,'Radar one two three',{'ALT':3000,'HDG':270}) is None
    assert out['instruction_check']=='NEEDS_REVIEW' and out['numeric_validation']=='NOT_PERFORMED'


@pytest.mark.parametrize('unit',['knots','knot','kt','kts','feet per minute','fpm'])
def test_speed_and_rate_never_delivered_as_altitude(unit):
    t='Hotel India Alpha maintain one hundred '+unit
    out=fuse(t,fake(t,3))
    assert not any(e['label']=='ALT' for e in out['entities'])
    assert 'HYBRID_UNSUPPORTED_SPEED_OR_RATE_CLAUSE' in out['issues']


def test_rate_threshold_excluded_and_new_target_after_reference_preserved():
    for t,expected in [('b air one four one climb flight level one six zero appreciate higher rate of climb up to flight level one zero zero','flight level one six zero'),('after passing flight level one zero zero climb flight level one six zero','flight level one six zero')]:
        words=t.split();r=refine_rules(words,rules(words))
        assert [' '.join(words[a:b]) for a,b,k in spans(r['tags']) if k=='ALT']==[expected]
        assert r['review_reasons']


def test_fly_name_kept_but_model_split_is_not_repaired():
    t='fly nicky eight four nine zero climb flight level three six zero'
    good=fuse(t,fake(t,6))
    assert good['entities'][0]['text']=='fly nicky eight four nine zero'
    raw=fake(t,6);raw['tokens'][1]['label']='B-CALLSIGN'
    out=fuse(t,raw)
    assert 'HYBRID_MISSING_OR_MULTIPLE_CALLSIGNS' in out['issues']
    assert check_candidates(out,'fly nicky eight four nine zero',{'ALT':36000})=='hybrid_needs_review'


@pytest.mark.parametrize('suffix',[' if able',' after passing flight level one zero zero',' level by'])
def test_conditions_and_cutoff_block_payload(suffix):
    text='Radar one two three maintain three thousand feet'+suffix
    out=fuse(text,fake(text,4))
    p=speech_payload('f',0,{'started_at':'2026-11-09T00:00:00Z','role':'ATC','segment_id':'s','attempt_id':'a','atc_input_id':'i'},text,.9,{'RADAR123':{'r':'Radar one two three'}},{'evidence_id':'e','ref':'stored:e'},ner_result=out)
    assert p['instruction_check']=='NEEDS_REVIEW' and p['fields']=={}


def test_missing_or_tampered_model_rejected_before_loading(tmp_path):
    with pytest.raises(ExtractionError):BertHybridExtractor(tmp_path)


def test_backend_not_configured_or_unknown_fails(monkeypatch):
    monkeypatch.delenv('RADAR_NER_MODEL',raising=False)
    monkeypatch.setenv('RADAR_NER_BACKEND','bert-hybrid')
    with pytest.raises(ExtractionError,match='NOT_CONFIGURED'):extract_atc('hello')
    with pytest.raises(ExtractionError,match='BACKEND_UNSUPPORTED'):extract_atc('hello','/nonexistent',backend='unknown')


def test_real_bert_artifact():
    path=os.getenv('RADAR_TEST_BERT_MODEL')
    if not path:pytest.skip('Set RADAR_TEST_BERT_MODEL for actual BERT inference')
    text='singapore six two one climb flight level two three zero'
    out=extract_atc(text,path,backend='bert-hybrid')
    assert out['model_version']=='bert-hybrid-rules-v3'
    assert [(e['label'],e['text']) for e in out['entities']]==[('CALLSIGN','singapore six two one'),('ACTION','climb'),('ALT','flight level two three zero')]
    with pytest.raises(ExtractionError,match='EMPTY_TRANSCRIPT'):extract_atc(' ',path,backend='bert-hybrid')
    with pytest.raises(ExtractionError,match='NER_TOKEN_LIMIT'):extract_atc('one '*130,path,backend='bert-hybrid')


# Reuse the existing real HTTP adapter fixture; ASR below is explicitly a stub.
from test_demo import flight, wav_bytes
import base64
from datetime import timedelta
from app.services import receiving_v2 as intake
from app.services.demo import adapters


def test_stt_dispatches_hybrid_and_bad_configuration_never_falls_back(client,flight,monkeypatch):
    from app.services.speech import ner
    now=intake.utc_now()
    response=client.post(f'/api/demo/{flight}/scenario/baseline',json={'started_at':intake.stamp(now-timedelta(seconds=4)),'ended_at':intake.stamp(now-timedelta(seconds=3))})
    assert response.status_code==200
    state=client.get(f'/api/v2/flights/{flight}/state').json()
    text='Radar one two three maintain 3,000 feet heading 270.'
    class ASR:
        def transcribe(self,path):return {'transcript':text,'model_score':.9}
    monkeypatch.setattr(adapters,'MODEL',ASR())
    monkeypatch.setenv('RADAR_NER_BACKEND','bert-hybrid');monkeypatch.setenv('RADAR_NER_MODEL','fake')
    called=[]
    def extract(t):called.append(t);return fuse(t,fake(t,4))
    monkeypatch.setattr(ner,'extract_atc',extract)
    def send():
        n=intake.utc_now();return client.post(f'/api/demo/{flight}/readback',json={'started_at':intake.stamp(n-timedelta(seconds=2)),'ended_at':intake.stamp(n-timedelta(seconds=1)),'atc_input_id':state['readback_required']['atc_input_id'],'audio':base64.b64encode(wav_bytes()).decode()})
    r=send();assert r.status_code==200,r.text
    assert called==[text] and r.json()['ner']['model_version']=='bert-hybrid-rules-v3'
    assert client.get(f'/api/v2/flights/{flight}/state').json()['structure_checks']['READBACK']['result']=='PASS'
    # Explicit mode with missing path must still attempt extraction and hold.
    monkeypatch.delenv('RADAR_NER_MODEL',raising=False)
    def unavailable(t):raise ExtractionError('NER_MODEL_NOT_CONFIGURED')
    monkeypatch.setattr(ner,'extract_atc',unavailable)
    r=send();assert r.status_code==200,r.text
    assert r.json()['quality_reason']=='ner_engine_unavailable'
    assert client.get(f'/api/v2/flights/{flight}/state').json()['result']!='NORMAL'

@pytest.mark.parametrize('text,expected',[('2-7-0',270),('0-0-0',0),('270-280',None),('2-7',None),('-90',None),('2--7-0',None),('1-2-3-4',None)])
def test_hyphen_digits_only_in_numeric_slot(text,expected):
    from app.services.structure_rules import parse_command
    values,issues=parse_command('heading '+text)
    if expected is None:assert issues and not values
    else:assert not issues and values=={'HDG':expected}


def test_stt_punctuation_normalization_preserves_token_count_and_source():
    text='Radar one, two, three, maintain 3,000 feet, heading 2-7-0.'
    assert BertHybridExtractor.words_for_model(text)==['Radar','one','two','three','maintain','3,000','feet','heading','2-7-0']
    out=fuse(text,fake(text,4))
    assert out['transcript']==text
    assert check_candidates(out,'Radar one two three',{'ALT':3000,'HDG':270}) is None
    assert next(e for e in out['entities'] if e['label']=='HDG')['text']=='2-7-0.'


def test_tampered_manifest_is_not_loaded(tmp_path):
    from app.services.speech.ner import LABELS
    from app.services.speech.hybrid import ARTIFACT_FILES
    for f in ARTIFACT_FILES:(tmp_path/f).write_text('invalid model bytes')
    (tmp_path/'config.json').write_text(json.dumps({'model_type':'bert','id2label':{str(i):t for i,t in enumerate(LABELS)},'label2id':{t:i for i,t in enumerate(LABELS)}}))
    (tmp_path/'radar_hybrid.json').write_text(json.dumps({'schema_version':1,'backend':'bert-hybrid','sha256':{f:'wrong' for f in ARTIFACT_FILES}}))
    with pytest.raises(ExtractionError,match='HASH_MISMATCH'):BertHybridExtractor(tmp_path)


@pytest.mark.parametrize('operand,value', [('to seven zero',270),('too seven zero',270),('one ate zero',180),('tree fore fife',345),('o for zero',40)])
def test_homophones_in_complete_heading_slot_preserve_evidence(operand,value):
    t='Radar one two three maintain three thousand feet heading '+operand
    out=fuse(t,fake(t,4))
    assert check_candidates(out,'Radar one two three',{'ALT':3000,'HDG':value}) is None
    entity=next(e for e in out['entities'] if e['label']=='HDG')
    assert entity['text']==operand and t[entity['start']:entity['end']]==operand
    assert out['transcript']==t and out['numeric_normalizations']
    assert entity['model_score'] is None


@pytest.mark.parametrize('command', ['heading to seven', 'heading to two seven zero', 'heading for seven zero', 'heading to seven zero degrees', 'contact tower for clearance', 'taxi to holding point', 'turn to the left', 'climb to three thousand feet'])
def test_non_numeric_to_or_incomplete_grammar_cannot_be_approved(command):
    from app.services.speech.numeric_slots import normalize_numeric_slots
    if not command.startswith('heading'):
        assert normalize_numeric_slots(command.split())[1]==[]
    t='Radar one two three '+command
    out=fuse(t,fake(t,4))
    p=speech_payload('f',0,{'started_at':'2026-11-09T00:00:00Z','role':'ATC','segment_id':'s','attempt_id':'a','atc_input_id':'i'},t,.9,{'RADAR123':{'r':'Radar one two three'}},{'evidence_id':'e','ref':'stored:e'},ner_result=out)
    assert p['instruction_check']=='NEEDS_REVIEW' and p['fields']=={}


@pytest.mark.parametrize('command,alt',[('maintain flight level one ate zero',18000),('maintain to thousand feet',2000)])
def test_explicit_altitude_slot_homophones(command,alt):
    t='Radar one two three '+command
    out=fuse(t,fake(t,4))
    assert check_candidates(out,'Radar one two three',{'ALT':alt}) is None
    assert out['numeric_normalizations']


def test_homophones_do_not_rewrite_callsign_and_conditions_still_hold():
    t='Radar to fore maintain three thousand feet heading to seven zero if able'
    out=fuse(t,fake(t,3))
    assert out['entities'][0]['text']=='Radar to fore'
    assert all(c['token_index']>3 for c in out['numeric_normalizations'])
    assert check_candidates(out,'Radar to fore',{'ALT':3000,'HDG':270})=='hybrid_needs_review'


def test_real_bert_with_unchanged_live_stt_transcript():
    path=os.getenv('RADAR_TEST_BERT_MODEL')
    if not path:pytest.skip('Set RADAR_TEST_BERT_MODEL for actual BERT inference')
    text='Radar, one, two, three, climb and maintain, three thousand feet, heading to seven, zero.'
    out=extract_atc(text,path,backend='bert-hybrid')
    assert out['transcript']==text
    assert check_candidates(out,'Radar one two three',{'ALT':3000,'HDG':270}) is None
    assert next(e for e in out['entities'] if e['label']=='HDG')['text']=='to seven, zero.'
