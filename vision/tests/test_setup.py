import json
import sys
from types import SimpleNamespace

import pytest

from radar_vision import setup


def test_manual_roi_config_is_based_on_image_size_not_screen_values(tmp_path, monkeypatch):
    boxes = iter([(20, 40, 100, 30), (150, 40, 60, 30), (250, 40, 60, 30)])
    cv = SimpleNamespace(
        imread=lambda path: SimpleNamespace(shape=(720, 1280, 3)),
        selectROI=lambda *args, **kwargs: next(boxes),
        destroyWindow=lambda title: None, destroyAllWindows=lambda: None,
    )
    monkeypatch.setattr(setup, "opencv", lambda: cv)
    output = tmp_path / "config.json"
    monkeypatch.setattr(sys, "argv", ["setup", "--image", "frame.png", "--output", str(output), "--speed"])
    setup.main()
    config = json.loads(output.read_text())
    assert config["image_size"] == [1280, 720]
    assert config["altitude"] == {"roi": [20, 40, 120, 70], "unit": "feet"}
    assert config["heading"]["unit"] == "degrees"
    assert config["speed"]["unit"] == "knots"


def test_cancelled_roi_does_not_overwrite_existing_config(tmp_path, monkeypatch):
    cv = SimpleNamespace(
        imread=lambda path: SimpleNamespace(shape=(720, 1280, 3)),
        selectROI=lambda *args, **kwargs: (0, 0, 0, 0),
        destroyWindow=lambda title: None, destroyAllWindows=lambda: None,
    )
    monkeypatch.setattr(setup, "opencv", lambda: cv)
    output = tmp_path / "config.json"
    output.write_text("original")
    monkeypatch.setattr(sys, "argv", ["setup", "--image", "frame.png", "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 2
    assert output.read_text() == "original"
