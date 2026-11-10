from vision.label_mcp import split_for_group, yolo_bbox
from vision.train_mcp_yolo import validate_dataset

def test_bbox_conversion():
    assert yolo_bbox(100, 50, 200, 100, 1000, 500) == (.2, .2, .2, .2)

def test_session_split_stable():
    assert split_for_group("session-1", 42) == split_for_group("session-1", 42)

def test_bbox_invalid():
    import pytest
    with pytest.raises(ValueError):
        yolo_bbox(999, 50, 200, 100, 1000, 500)

def test_missing_dataset(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        validate_dataset(tmp_path)
