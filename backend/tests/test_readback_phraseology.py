"""Synthetic regression cases; real recorded audio is tested separately, not committed."""
from copy import deepcopy
from datetime import timedelta
import base64
import os
import pytest

from app.services.structure_rules import normalize, split_callsign, parse_readback, check_structure
from app.services.speech.ner import assemble, check_candidates, extract_atc
from app.services.speech.hybrid import fuse
from app.services.speech.readback import readback_candidates
from app.services.demo.adapters import speech_payload
from test_demo import flight, wav_bytes
from test_structure_rules import sample
from app.services.demo import adapters
from app.services import receiving_v2 as intake

REGISTRY = {'DELTA123': {'delta': 'Delta one two three'}, 'RADAR123': {'radar': 'Radar one two three'}}
TEXT = '3,000 feet heading, two, seven, zero, delta, one, two, three.'


def empty_call_model(text):
    return fuse(text, assemble(text, ['O']*len(text.split()), [.9]*len(text.split())))


@pytest.mark.parametrize('text', [
    'Delta one two three climb and maintain three thousand feet heading two seven zero',
    'Climb and maintain three thousand feet heading two seven zero Delta one two three',
    'Climbing to three thousand feet heading two seven zero Delta one two three',
    'Climbing to altitude 3000 feet fly heading 270 Delta one two three',
    'Descending to 3000 feet turning left heading 270 Delta one two three',
    'Maintaining 3000 feet heading 270 Delta one two three',
])
def test_supported_readback_without_reordering_or_target_injection(text):
    matched = split_callsign(normalize(text), REGISTRY, readback=True)
    assert matched[0] == 'DELTA123'
    assert parse_readback(matched[3]) == ({'ALT':3000, 'HDG':270}, [])
    base = empty_call_model(text)
    original = deepcopy(base)
    out = readback_candidates(text, REGISTRY, base)
    assert check_candidates(out, matched[2], {'ALT':3000, 'HDG':270}) is None
    assert base == original
    for entity in out['entities']:
        assert text[entity['start']:entity['end']] == entity['text']
        assert entity['model_score'] is None
    assert out['base_issues'] == ['HYBRID_MISSING_OR_MULTIPLE_CALLSIGNS']


def test_original_delta_text_extracts_values_but_missing_action_is_reviewed():
    matched = split_callsign(normalize(TEXT), REGISTRY, readback=True)
    values, issues = parse_readback(matched[3])
    assert values == {'ALT':3000, 'HDG':270}
    assert issues == [('ALT','NEEDS_REVIEW','READBACK_ALTITUDE_ACTION_MISSING')]
    ner = readback_candidates(TEXT, REGISTRY, empty_call_model(TEXT))
    assert check_candidates(ner, matched[2], values) is None
    segment = dict(started_at='2026-11-11T10:00:00Z', role='PILOT', segment_id='s', attempt_id='a', atc_input_id='i', instruction_id='j')
    payload = speech_payload('f',0,segment,TEXT,.9,REGISTRY,{'evidence_id':'e','ref':'stored:e'},ner_result=ner)
    assert payload['callsign']['value'] == 'DELTA123'
    assert {k:v['value'] for k,v in payload['fields'].items()} == values
    assert payload['instruction_check'] == 'NEEDS_REVIEW'


@pytest.mark.parametrize('text', [
    '3000 feet heading 270',
    '3000 feet heading 270 delta one two',
    'Delta one two three 3000 feet Radar one two three',
    'Delta one two three 3000 feet Delta one two three',
    '3000 feet Delta one two three heading 270',
    'Delta one two threefour climb and maintain 3000 feet',
])
def test_absent_partial_multiple_or_middle_callsigns_never_accepted(text):
    assert split_callsign(normalize(text), REGISTRY, readback=True) is None


def test_alias_collision_and_atc_suffix_not_silently_accepted():
    registry = {**REGISTRY, 'OTHER': {'duplicate': 'Delta one two three'}}
    assert split_callsign(normalize(TEXT), registry, readback=True) is None
    assert split_callsign(normalize(TEXT), REGISTRY) is None


@pytest.mark.parametrize('tail', [' if able', ' after passing 2000 feet', ' correction 4000 feet', ' per minute', ' negative', ' and', ' heading 280'])
def test_extra_conditions_references_and_duplicate_clauses_remain_blocked(tail):
    _, issues = parse_readback('climbing to 3000 feet heading 270' + tail)
    assert issues


@pytest.mark.parametrize('command', ['3000 heading 270','three thousand knots heading 270','three thousand feet per minute heading 270', 'heading to two seven zero','heading -90','heading 270-280'])
def test_ambiguous_units_ranges_and_bad_numbers_remain_blocked(command):
    assert parse_readback(command)[1]


def test_model_failure_and_explicit_conflict_not_overridden():
    base = empty_call_model(TEXT)
    for issue in ['NER_UNAVAILABLE','INVALID_BIO','HYBRID_MODEL_INVALID_BIO','HYBRID_CONDITION_SCOPE_NOT_RESOLVED']:
        bad = deepcopy(base); bad['issues'].append(issue)
        assert readback_candidates(TEXT, REGISTRY, bad) == bad
    bad = deepcopy(base)
    bad['entities'].append(dict(label='CALLSIGN',text='3,000 feet',start=0,end=10))
    assert readback_candidates(TEXT, REGISTRY, bad) == bad


@pytest.mark.parametrize('command,reason', [
    ('Climbing to 3000 feet heading 270',None),
    ('Descending to 3000 feet heading 270','READBACK_VERTICAL_MISSING_OR_CONFLICT'),
    ('Maintaining 3000 feet heading 270','READBACK_VERTICAL_MISSING_OR_CONFLICT'),
    ('3000 feet heading 270','READBACK_ALTITUDE_ACTION_MISSING'),
    ('Climbing to 3000 feet turning right heading 270','READBACK_TURN_MISSING_OR_CONFLICT'),
])
def test_server_checks_actual_directions_independently_of_candidate_adapter(command,reason):
    data, context = sample(command + ' Radar one two three', {'ALT':3000,'HDG':270})
    data.update(source='READBACK',instruction_id=context['instruction_id'])
    context['segment']['role'] = 'PILOT'
    context['expected_phraseology'] = {'vertical':'CLIMB','turn':'left' if 'turning' in command else None}
    report = check_structure(data, **context)
    assert report.result == ('PASS' if reason is None else 'NEEDS_REVIEW')
    if reason: assert reason in {c.reason for c in report.checks}


@pytest.mark.parametrize('command,expected', [
    ('Climbing to 3000 feet heading 270','NORMAL'),
    ('Climb and maintain 3500 feet heading 270','MISMATCH'),
    ('Climb and maintain 3000 feet heading 280','MISMATCH'),
    ('Descending to 3000 feet heading 270','UNVERIFIED'),
    ('3000 feet heading 270','UNVERIFIED'),
])
def test_readback_http_new_attempts_and_camera_stays_unverified(client,flight,monkeypatch,command,expected):
    now = intake.utc_now()
    atc = client.post(f'/api/demo/{flight}/scenario/baseline',json={'started_at':intake.stamp(now-timedelta(seconds=4)),'ended_at':intake.stamp(now-timedelta(seconds=3))})
    assert atc.status_code == 200
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    text = command + ', Radar one two three.'
    class ASR:
        def transcribe(self,path): return dict(transcript=text,model_score=.9)
    monkeypatch.setattr(adapters,'MODEL',ASR())
    monkeypatch.setenv('RADAR_NER_BACKEND','bert-hybrid')
    monkeypatch.setenv('RADAR_NER_MODEL','fixture')
    from app.services.speech import ner
    monkeypatch.setattr(ner,'extract_atc',empty_call_model)
    response = client.post(f'/api/demo/{flight}/readback',json={'started_at':intake.stamp(now-timedelta(seconds=2)),'ended_at':intake.stamp(now-timedelta(seconds=1)),'atc_input_id':state['readback_required']['atc_input_id'],'audio':base64.b64encode(wav_bytes()).decode()})
    assert response.status_code == 200, response.text
    state = client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['validation']['readback']['result'] == expected
    assert state['validation']['setting']['result'] == 'UNVERIFIED'


@pytest.mark.parametrize('text', [TEXT,
    'Climb and maintain three thousand feet, heading two seven zero, Delta one two three.',
    'Climbing to three thousand feet, heading two seven zero, Delta one two three.',
])
def test_real_bert_original_delta_text(text):
    path = os.getenv('RADAR_TEST_BERT_MODEL')
    if not path: pytest.skip('Actual BERT path not configured')
    base = extract_atc(text,path,backend='bert-hybrid')
    out = readback_candidates(text, REGISTRY, base)
    assert check_candidates(out, 'Delta one two three', {'ALT':3000,'HDG':270}) is None
    assert out['transcript'] == text
    assert any(e['label'] == 'CALLSIGN' and normalize(e['text']) == 'delta one two three' for e in out['entities'])


def test_missing_phraseology_context_and_turn_omission_are_not_approved():
    data, context = sample('Climb and maintain 3000 feet heading 270 Radar one two three', {'ALT':3000,'HDG':270})
    data.update(source='READBACK',instruction_id=context['instruction_id'])
    context['segment']['role']='PILOT'
    for expected, reason in [({'context_missing':True},'READBACK_PHRASEOLOGY_CONTEXT_UNAVAILABLE'),
                             ({'turn':'left'},'READBACK_TURN_MISSING_OR_CONFLICT')]:
        report=check_structure(data, **context, expected_phraseology=expected)
        assert report.result == 'NEEDS_REVIEW'
        assert reason in {c.reason for c in report.checks}
