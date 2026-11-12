"""Speech grammar expansion: candidates, normalized wire values and review gates."""
from copy import deepcopy
import base64
from datetime import timedelta

import pytest
from app.services.structure_rules import parse_command, normalize, check_structure
from app.services.speech.hybrid import fuse
from app.services.speech.ner import check_candidates
from test_ner_hybrid import fake
from test_structure_rules import sample
from test_demo import flight, wav_bytes


@pytest.mark.parametrize('command,expected', [
    ('maintain FL80', {'ALT':8000}), ('maintain FL080', {'ALT':8000}),
    ('maintain FL 80', {'ALT':8000}), ('maintain fl eight zero', {'ALT':8000}),
    ('maintain flight level eight zero', {'ALT':8000}),
    ('maintain flight level ate zero', {'ALT':8000}),
    ('maintain flight level three hundred', {'ALT':30000}),
    ('maintain FL three hundred', {'ALT':30000}),
    ('maintain flight level one ate zero', {'ALT':18000}),
    ('heading three six zero', {'HDG':0}), ('heading 360', {'HDG':0}),
    ('heading 3-6-0', {'HDG':0}), ('heading zero', {'HDG':0}),
    ('heading three five nine', {'HDG':359}),
    ('maintain FL80 heading 360', {'ALT':8000,'HDG':0}),
])
def test_complete_supported_speech_forms_match_hybrid_and_structure(command, expected):
    values, issues = parse_command(normalize(command))
    assert values == expected and not issues
    text = 'Radar one two three '+command
    result = fuse(text, fake(text,4))
    assert result['transcript'] == text
    assert check_candidates(result, 'Radar one two three', expected) is None
    for entity in result['entities']:
        assert text[entity['start']:entity['end']] == entity['text']
    data, context = sample(text, expected)
    assert check_structure(data, **context).result == 'PASS'


@pytest.mark.parametrize('command', [
    'maintain FL8', 'maintain FL8000', 'maintain FL-80', 'maintain FL80-90',
    'maintain flight level eight', 'maintain flight level three hundred and ten',
    'maintain flight level three thousand', 'maintain flight level three one zero one thousand or greater',
    'maintain flight level obama zero zero', 'maintain FL80 knots', 'maintain FL80 meters',
    'heading 361', 'heading 720', 'heading -360', 'heading 360-370', 'heading 0360',
    'heading q zero five zero', 'heading kel two nine zero',
    'heading ah uh two seven zero', 'heading two ah seven zero',
    'heading ah two seven', 'heading ah two seven zero one', 'heading ah two seven zero degrees',
])
def test_invalid_or_ambiguous_operand_is_not_completed_or_truncated(command):
    _, issues = parse_command(normalize(command))
    assert issues


@pytest.mark.parametrize('filler', ['ah','uh','um'])
def test_hesitation_candidate_preserves_evidence_and_cannot_pass(filler):
    operand=f'{filler} two seven zero'
    text='Radar one two three heading '+operand
    result=fuse(text,fake(text,4))
    assert next(e for e in result['entities'] if e['label']=='HDG')['text']==operand
    assert parse_command('heading '+operand)==({'HDG':270},[])
    assert 'HYBRID_HEADING_HESITATION_REQUIRES_REVIEW' in result['issues']
    assert check_candidates(result,'Radar one two three',{'HDG':270})=='hybrid_needs_review'
    data,context=sample(text,{'HDG':270})
    report=check_structure(data,**context)
    assert report.result=='NEEDS_REVIEW'
    assert 'HEADING_HESITATION_REQUIRES_REVIEW' in {c.reason for c in report.checks}


@pytest.mark.parametrize('raw', ['360','three six zero','3-6-0'])
def test_heading_raw_source_converts_to_zero_without_mutating_evidence(raw):
    data,context=sample('Radar one two three heading '+raw,{'HDG':0})
    data['fields']['HDG']['raw_text']=raw
    before=deepcopy(data)
    assert check_structure(data,**context).result=='PASS'
    assert data==before
    data['fields']['HDG']['value']=360
    assert check_structure(data,**context).result=='INVALID'


def test_compact_fl_is_not_a_callsign_replacement():
    text='Radar FL80 report position'
    result=fuse(text,fake(text,2))
    assert [e['label'] for e in result['entities']]==['CALLSIGN']
    assert result['entities'][0]['text']=='Radar FL80'


@pytest.mark.parametrize('command', ['heading ah two seven zero', 'maintain flight level three one zero one thousand or greater'])
def test_server_does_not_adopt_ambiguous_numeric_candidate_even_without_ner(client,flight,monkeypatch,command):
    from app.services import receiving_v2 as intake
    from app.services.demo import adapters
    monkeypatch.delenv('RADAR_NER_BACKEND',raising=False)
    monkeypatch.delenv('RADAR_NER_MODEL',raising=False)
    monkeypatch.delenv('RADAR_STT_CALLSIGN_CONTEXT',raising=False)
    class ASR:
        def transcribe(self,path):
            return {'transcript':'Radar one two three '+command,'model_score':.99}
    monkeypatch.setattr(adapters,'MODEL',ASR())
    now=intake.utc_now()
    response=client.post(f'/api/demo/{flight}/atc',json={'audio':base64.b64encode(wav_bytes()).decode(),
        'started_at':intake.stamp(now-timedelta(seconds=2)), 'ended_at':intake.stamp(now-timedelta(seconds=1)),
        'input_mode':'file_upload'})
    assert response.status_code==200,response.text
    state=client.get(f'/api/v2/flights/{flight}/state').json()
    assert state['targets']=={'ALT':None,'HDG':None}
    assert state['result']=='UNVERIFIED'
