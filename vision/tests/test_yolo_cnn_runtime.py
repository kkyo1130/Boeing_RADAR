"""No private weights: assert model routing, conservative gates and image coordinates."""
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock
import torch
from PIL import Image
import pytest
from vision import yolo_cnn_runtime as module


def runtime(predictions):
    instance = module.YoloCnnRuntime.__new__(module.YoloCnnRuntime)
    instance.lock = RLock()
    def predict(frame, **kwargs):
        candidates = predictions.get(kwargs['imgsz'], [])
        return [SimpleNamespace(boxes=SimpleNamespace(
            xyxy=torch.tensor([c[0] for c in candidates]).reshape(-1, 4),
            conf=torch.tensor([c[1] for c in candidates]),
            cls=torch.zeros(len(candidates))))]
    instance.detector = SimpleNamespace(predict=predict)
    instance.ocr = SimpleNamespace(infer=Mock(return_value=dict(value='000', reason=None, source='character_cnn')))
    return instance


def test_full_frame_yolo_gate_before_window_localization_and_cnn(monkeypatch):
    r = runtime({640: [([20, 20, 180, 100], .8)]})
    locator = Mock(return_value={'hdg': (10, 10, 30, 20), 'alt': (70, 10, 50, 20)})
    monkeypatch.setattr(module, 'detect_mcp_readouts', locator)
    result = r.infer(Image.new('RGB', (200, 120)))
    assert result['rois'] == {'hdg': [30, 30, 60, 50], 'alt': [90, 30, 140, 50]}
    assert locator.call_args.args[0].shape == (80, 160, 3)
    assert [call.args[0].size for call in r.ocr.infer.call_args_list] == [(30, 20), (50, 20)]
    assert result['detector_imgsz'] == 640
    assert result['pipeline'] == 'yolo11n_character_cnn'
    assert result['apple_vision_enabled'] is False


@pytest.mark.parametrize('candidates,reason', [
    ([([20, 20, 180, 100], .49)], 'LOW_OR_MISSING_PANEL_SCORE'),
    ([([0, 20, 180, 100], .9)], 'CLIPPED_OR_IMPLAUSIBLE_PANEL'),
    ([([10, 10, 80, 50], .9), ([110, 60, 180, 100], .4)], 'AMBIGUOUS_PANELS'),
])
def test_rejected_yolo_never_falls_back_to_ocr(monkeypatch, candidates, reason):
    r = runtime({640: candidates, 960: candidates})
    locator = Mock(side_effect=AssertionError('must not localize rejected panels'))
    monkeypatch.setattr(module, 'detect_mcp_readouts', locator)
    result = r.infer(Image.new('RGB', (200, 120)))
    assert result['rois'] is None
    assert result['hdg']['value'] is None and result['alt']['value'] is None
    assert result['reason'] == reason
    locator.assert_not_called()
    r.ocr.infer.assert_not_called()


def test_missing_glyph_windows_stay_missing(monkeypatch):
    r = runtime({640: [([20, 20, 180, 100], .9)]})
    monkeypatch.setattr(module, 'detect_mcp_readouts', lambda frame: {})
    result = r.infer(Image.new('RGB', (200, 120)))
    assert result['reason'] == 'READOUTS_MISSING_OR_AMBIGUOUS'
    r.ocr.infer.assert_not_called()


def test_manual_rois_share_cnn_and_preserve_zero(monkeypatch):
    r = runtime({})
    monkeypatch.setattr(module, 'get_runtime', lambda: r)
    result = module.read_fields(Image.new('RGB', (200, 120)), {'HDG': [20, 20, 50, 40], 'ALT': [80, 20, 130, 40]})
    assert result['fields']['heading']['value'] == 0
    assert result['fields']['heading']['source'] == 'character_cnn'
    result = r.read(Image.new('RGB', (200, 120)), {'hdg': [-1, 0, 30, 20]})
    assert all(field['value'] is None for field in result.values())


def test_second_scale_cannot_bypass_detected_ambiguity(monkeypatch):
    r = runtime({960: [([10, 10, 80, 50], .9), ([110, 60, 180, 100], .4)],
                 640: [([20, 20, 180, 100], .9)]})
    locator = Mock(return_value={'hdg': (10, 10, 30, 20), 'alt': (70, 10, 50, 20)})
    monkeypatch.setattr(module, 'detect_mcp_readouts', locator)
    assert r.infer(Image.new('RGB', (200, 120)))['reason'] == 'AMBIGUOUS_PANELS'
    locator.assert_not_called()
    r.ocr.infer.assert_not_called()


def test_saved_model_selection_is_portable_and_explicit_override_is_independent(monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(module, '__file__', str(tmp_path/'vision/yolo_cnn_runtime.py'))
    for key in ('RADAR_YOLO_WEIGHTS', 'RADAR_YOLO_SHA256', 'RADAR_CHARACTER_CHECKPOINT', 'RADAR_CHARACTER_SHA256'):
        monkeypatch.delenv(key, raising=False)
    (tmp_path/'.demo').mkdir()
    (tmp_path/'.demo/active-vision.json').write_text(json.dumps(dict(
        yolo_checkpoint='local/yolo.pt', yolo_sha256='saved-yolo',
        checkpoint='local/cnn.pt', sha256='saved-cnn')))
    selected = module.model_configuration()
    assert selected['yolo'] == (tmp_path/'local/yolo.pt', 'saved-yolo')
    assert selected['cnn'] == (tmp_path/'local/cnn.pt', 'saved-cnn')
    monkeypatch.setenv('RADAR_YOLO_WEIGHTS', str(tmp_path/'override.pt'))
    assert module.model_configuration()['yolo'] == (tmp_path/'override.pt', None)
    monkeypatch.setenv('RADAR_YOLO_SHA256', 'explicit-hash')
    assert module.model_configuration()['yolo'][1] == 'explicit-hash'
    (tmp_path/'runner').mkdir()
    monkeypatch.chdir(tmp_path/'runner')
    monkeypatch.setenv('RADAR_YOLO_WEIGHTS', '../override.pt')
    assert module.model_configuration()['yolo'][0].resolve() == tmp_path/'override.pt'
