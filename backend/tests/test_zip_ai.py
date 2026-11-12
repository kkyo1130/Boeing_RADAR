"""ZIP AI must veto disagreement and preserve the existing grammar."""
from app.services.demo.adapters import speech_payload
from app.services.speech.ner import assemble
from app.services.speech.hybrid import fuse


def payload(result=None):
    text = 'Radar one two three maintain 3000 feet heading 270'
    segment = dict(started_at='2026-11-12T00:00:00Z', role='ATC', segment_id='s', attempt_id='a', atc_input_id='i')
    return speech_payload('f', 0, segment, text, .9,
                          {'RADAR123': {'spoken': 'Radar one two three'}},
                          {'ref': 'audio'}, ner_result=result)


def extraction():
    text = 'Radar one two three maintain 3000 feet heading 270'
    tags = ['B-CALLSIGN', 'I-CALLSIGN', 'I-CALLSIGN', 'I-CALLSIGN'] + ['O'] * 5
    return fuse(text, assemble(text, tags, [.9] * len(tags)))


def test_ai_agreement_preserves_grammar_values():
    result = payload(extraction())
    assert result['instruction_check'] == 'PASS'
    assert result['fields']['ALT']['value'] == 3000
    assert result['fields']['HDG']['value'] == 270


def test_ai_disagreement_cannot_produce_normal_fields():
    result = extraction()
    for entity in result['entities']:
        if entity['label'] == 'HDG': entity['text'] = '290'
    out = payload(result)
    assert out['instruction_check'] == 'NEEDS_REVIEW'
    assert out['fields'] == {}


def test_ai_issues_hold_and_opt_out_remains_available():
    result = extraction()
    result['issues'].append('MODEL_UNCERTAIN')
    assert payload(result)['instruction_check'] == 'NEEDS_REVIEW'
    assert payload()['instruction_check'] == 'PASS'
