import pytest
from app.services.validation_service import validate

def obs(alt=18000, hdg=240):
    return {"altitude": alt, "heading": hdg}

@pytest.mark.parametrize('source,field,wrong,status', [
    ('readback','altitude',16000,'READBACK_ERROR'),
    ('readback','heading',250,'READBACK_ERROR'),
    ('cockpit','altitude',16000,'SETTING_ERROR'),
    ('cockpit','heading',250,'SETTING_ERROR'),
])
def test_mismatch(source, field, wrong, status):
    atc, readback, cockpit = obs(), obs(), obs()
    (readback if source == 'readback' else cockpit)[field] = wrong
    actual, errors = validate(atc, readback, cockpit)
    assert actual == status
    assert errors == [{'field': 'ALT' if field == 'altitude' else 'HDG',
                       'expected': atc[field], 'actual': wrong}]

def test_priority_and_waiting():
    assert validate(obs())[0] == 'WAITING_READBACK'
    assert validate(obs(), obs())[0] == 'WAITING_COCKPIT'
    assert validate(obs(), obs(), obs()) == ('VERIFIED', [])
    assert validate(obs(), obs(16000), obs(15000))[0] == 'READBACK_ERROR'
