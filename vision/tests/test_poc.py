import pytest
from PIL import Image
from radar_vision.poc import load_config, parse_field, recognize
from pathlib import Path

CONFIG = Path(__file__).parents[1] / "configs/synthetic.json"

@pytest.mark.parametrize("text,unit,value,reason", [
    ("000","degrees",0,None), ("360","degrees",None,"out_of_range"),
    ("160","FL",16000,None), ("3000","feet",3000,None),
    ("3O00","feet",None,"invalid_format"), ("-1","feet",None,"invalid_format"),
    ("3 000","feet",None,"invalid_format")])
def test_digits(text, unit, value, reason):
    result = parse_field([{"text":text,"score":0.9}],unit,0.5)
    assert (result["value"], result["reason"]) == (value,reason)


def test_low_score_and_empty():
    assert parse_field([],"feet",0.5)["value"] is None
    assert parse_field([{"text":"3000","score":0.1}],"feet",0.5)["reason"] == "low_model_score"
    assert parse_field([{"text":"3000","score":float("nan")}],"feet",0.5)["reason"] == "invalid_score"


def test_blank_image_and_time(tmp_path):
    image = tmp_path / "blank.png"
    Image.new("RGB",(800,300)).save(image)
    result = recognize(image, load_config(CONFIG), "/missing-ocr", tmp_path / "out")
    assert result["captured_at"] is None
    assert not result["capture_time_known"]
    assert result["fields"]["altitude"]["reason"] == "blank_roi"
    assert Path(result["fields"]["heading"]["evidence"]).exists()
    with pytest.raises(ValueError, match="timezone"):
        recognize(image, load_config(CONFIG), "/missing",tmp_path,"2026-10-10T12:00:00")


def test_wrong_resolution(tmp_path):
    image = tmp_path / "small.png"
    Image.new("RGB",(100,100)).save(image)
    with pytest.raises(ValueError, match="size"):
        recognize(image,load_config(CONFIG),"/missing",tmp_path)


def test_missing_ocr(tmp_path):
    image = tmp_path / "nonblank.png"
    sample = Image.new("RGB",(800,300),"white")
    sample.paste("black",(50,110,100,150))
    sample.save(image)
    result = recognize(image,load_config(CONFIG),"/missing",tmp_path / "out")
    assert result["fields"]["altitude"]["reason"] == "ocr_unavailable"


def test_ambiguous_multiple_results():
    rows = [{"text":"3000", "score":0.9}, {"text":"3500", "score":0.9}]
    assert parse_field(rows,"feet",0.5)["reason"] == "invalid_format"


def test_invalid_roi(tmp_path):
    import json
    config = json.loads(CONFIG.read_text())
    config['altitude']['roi'] = [-1,100,380,210]
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='ROI'):
        load_config(path)


@pytest.mark.parametrize('text,unit,value,reason', [
    ('250','knots',250,None), ('.780','mach',0.780,None),
    ('0.78','mach',0.78,None), ('250','mach',None,'invalid_format'),
    ('.780','knots',None,'invalid_format'), ('---','knots',None,'invalid_format')])
def test_explicit_speed_units(text,unit,value,reason):
    result = parse_field([{'text':text,'score':0.9}],unit,0.5)
    assert (result['value'],result['reason']) == (value,reason)


def test_optional_speed_and_version(tmp_path):
    config = load_config(CONFIG)
    config['speed'] = {'roi':[0,0,100,100], 'unit':'knots'}
    image = tmp_path / 'blank.png'
    Image.new('RGB',(800,300)).save(image)
    result = recognize(image,config,'/missing',tmp_path / 'out')
    assert result['schema_version'] == 'vision-poc/2'
    assert result['fields']['speed']['unit'] == 'knots'
    assert result['fields']['speed']['value'] is None
    assert Path(result['fields']['speed']['evidence']).exists()
    del config['speed']
    result = recognize(image,config,'/missing',tmp_path / 'legacy')
    assert result['schema_version'] == 'vision-poc/1'
    assert 'speed' not in result['fields']


@pytest.mark.parametrize('preprocessing', [
    {'scale':0}, {'scale':9}, {'scale':True}, {'scale':2.5},
    {'grayscale':'true'}, {'rotate':180}, []])
def test_invalid_preprocessing(tmp_path,preprocessing):
    import json
    config = load_config(CONFIG)
    config['ocr_preprocessing'] = preprocessing
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError,match='ocr_preprocessing'):
        load_config(path)


def test_preprocessing_preserves_original_evidence(tmp_path):
    config = load_config(CONFIG)
    config['ocr_preprocessing'] = {'grayscale':True,'scale':4}
    source = tmp_path / 'frame.png'
    Image.new('RGB',(800,300),'black').save(source)
    result = recognize(source,config,'/missing',tmp_path / 'out')
    field = result['fields']['heading']
    with Image.open(field['evidence']) as original:
        assert original.size == (330,110)
        assert original.mode == 'RGB'
    with Image.open(field['ocr_evidence']) as prepared:
        assert prepared.size == (1320,440)
        assert prepared.mode == 'L'
    assert field['ocr_preprocessing'] == {'grayscale':True,'scale':4}
    assert field['value'] is None
    assert field['reason'] == 'blank_roi'


def test_field_specific_preprocessing(tmp_path):
    config = load_config(CONFIG)
    config['heading']['ocr_preprocessing'] = {'grayscale':True,'scale':4}
    source = tmp_path / 'frame.png'
    Image.new('RGB',(800,300)).save(source)
    result = recognize(source,config,'/missing',tmp_path / 'out')
    assert 'ocr_evidence' not in result['fields']['altitude']
    assert result['fields']['heading']['ocr_preprocessing']['scale'] == 4
    import json
    config['heading']['ocr_preprocessing']['scale'] = 0
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError,match='ocr_preprocessing'):
        load_config(path)
