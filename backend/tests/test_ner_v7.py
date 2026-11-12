import math
import os
import pytest
from app.services.speech.ner import assemble, check_candidates, extract_atc, ExtractionError
from app.services.demo.adapters import speech_payload


def result(text, labels):
    return assemble(text, labels.split(), [.9]*len(text.split()))


def test_offsets_and_invalid_bio_are_not_repaired():
    text = '  alpha  one\nclimb flight level two three zero'
    r = result(text, 'B-CALLSIGN I-CALLSIGN B-ACTION B-ALT I-ALT I-ALT I-ALT I-ALT')
    for e in r['entities']: assert text[e['start']:e['end']] == e['text']
    assert r['entities'][0]['text'] == 'alpha  one'
    bad = result('qnh one zero', 'O I-CALLSIGN I-CALLSIGN')
    assert bad['issues'] == ['INVALID_BIO'] and bad['entities'] == []
    assert bad['instruction_check'] == 'NEEDS_REVIEW'


@pytest.mark.parametrize('labels,scores', [(['O'], []), (['B-UNKNOWN'], [.9]), (['O'], [math.nan])])
def test_rejects_misalignment_unknown_and_nonfinite(labels, scores):
    with pytest.raises(ExtractionError): assemble('word', labels, scores)


def good_result():
    text = 'Radar one two three maintain three thousand feet heading two seven zero'
    return result(text, 'B-CALLSIGN I-CALLSIGN I-CALLSIGN I-CALLSIGN B-ACTION B-ALT I-ALT I-ALT O B-HDG I-HDG I-HDG')


def test_full_grammar_and_ner_must_agree():
    r = good_result()
    assert check_candidates(r, 'Radar one two three', {'ALT':3000, 'HDG':270}) is None
    assert check_candidates(r, 'Radar one two three', {'ALT':3000, 'HDG':280}) == 'ner_target_disagreement'
    assert check_candidates(r, 'different call', {'ALT':3000, 'HDG':270}) == 'ner_callsign_disagreement'


def test_model_never_bypasses_conditional_or_quality_checks():
    r = good_result()
    seg = dict(started_at='2026-11-08T00:00:00Z', role='ATC', segment_id='s', attempt_id='t', atc_input_id='a')
    registry = {'RADAR123':{'r':'Radar one two three'}}
    args = ('f',0,seg,r['transcript'],.9,registry,{'evidence_id':'e','ref':'stored:e'})
    assert speech_payload(*args, ner_result=r)['instruction_check'] == 'PASS'
    assert speech_payload(*args, quality_reason='clipped_audio', ner_result=r)['instruction_check'] == 'NEEDS_REVIEW'
    p = speech_payload(*args[:3], args[3]+' if able', *args[4:], ner_result=r)
    assert p['instruction_check'] == 'NEEDS_REVIEW' and p['fields'] == {}
    r['issues'] = ['INVALID_BIO']
    p = speech_payload(*args, ner_result=r)
    assert p['instruction_check'] == 'NEEDS_REVIEW' and p['fields'] == {}


def test_text_api_is_opt_in_and_failure_is_not_a_clearance(client, monkeypatch):
    monkeypatch.delenv('RADAR_DEMO_ENABLED', raising=False)
    assert client.post('/api/demo/speech/extract',json={'text':'hello'}).status_code == 404
    monkeypatch.setenv('RADAR_DEMO_ENABLED','1');monkeypatch.delenv('RADAR_NER_MODEL', raising=False)
    assert client.post('/api/demo/speech/extract',json={'text':'hello'}).status_code == 503
    monkeypatch.setattr('app.services.speech.ner.extract_atc', lambda text: result(text,'O'))
    body=client.post('/api/demo/speech/extract',json={'text':'hello'}).json()
    assert body['instruction_check']=='NEEDS_REVIEW' and body['score_calibrated'] is False


def test_real_v7_artifact():
    path = os.getenv('RADAR_TEST_NER_MODEL')
    if not path: pytest.skip('Set RADAR_TEST_NER_MODEL for actual safetensors smoke test')
    text = 'singapore six two one climb flight level two three zero'
    r = extract_atc(text, path)
    assert r['issues'] == []
    assert [(e['label'], e['text']) for e in r['entities']] == [('CALLSIGN','singapore six two one'),('ACTION','climb'),('ALT','flight level two three zero')]
    with pytest.raises(ExtractionError, match='EMPTY_TRANSCRIPT'): extract_atc(' ', path)
    with pytest.raises(ExtractionError, match='NER_TOKEN_LIMIT'): extract_atc('one '*130, path)
    for text in ['quality eight nine sierra taxi zulu hotel hold short of lima','roger qnh one zero one eight for check contact tower one one eight one']:
        r=extract_atc(text, path)
        for t in r['tokens']:
            if t['word'] in {'taxi','zulu','hotel','qnh','tower'}: assert t['label']=='O'
