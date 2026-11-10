from unittest.mock import Mock
import pytest
from vision.core import Recognition, Regions, Stabilizer, parse_reading, recognize
from vision.api_client import RadarClient

def test_parse_and_leading_zero():
    assert parse_reading("18000", "090", .9, .8) == Recognition(18000, 90, .8)
    assert parse_reading("18000", "360", .9, .9) is None
    assert parse_reading("18?00", "240", .9, .9) is None
    assert parse_reading("18000", "240", .9, .1) is None

def test_stabilizer_rejects_single_bad_frame():
    stable = Stabilizer(window=5, required=4)
    good = Recognition(18000, 240, .9)
    for item in [good, good, None, good]:
        assert stable.push(item) is None
    assert stable.push(good) == good

def test_stabilizer_rejects_conflicting_frames():
    stable = Stabilizer(window=3, required=3)
    for item in [Recognition(18000, 240, .9), Recognition(16000, 240, .9),
                 Recognition(18000, 240, .9)]:
        result = stable.push(item)
    assert result is None

def test_roi_and_reader():
    np = pytest.importorskip("numpy")
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    reader = Mock()
    reader.read.side_effect = [("18000", .9), ("240", .95)]
    result = recognize(image, Regions(heading=(0, 0, 50, 40),
                                      altitude=(50, 0, 80, 40)), reader)
    assert result == Recognition(18000, 240, .9)

def test_client_state_transitions():
    client = RadarClient("http://localhost:8000", "CLR-001")
    client.client = Mock()
    state = Mock()
    state.json.return_value = {"readback": {"altitude": 18000}, "cockpit": None,
                                "status": "WAITING_COCKPIT"}
    response = Mock()
    response.json.return_value = {"status": "SETTING_ERROR"}
    client.client.get.return_value = state
    client.client.post.return_value = response
    value = Recognition(16000, 240, .9)
    assert client.submit(value)["status"] == "SETTING_ERROR"
    assert client.client.post.call_args.args[0].endswith("/cockpit")
    assert client.submit(value) == {"skipped": "duplicate"}
    state.json.return_value = {"readback": {}, "cockpit": {}, "status": "SETTING_ERROR"}
    assert client.submit(Recognition(18000, 240, .9))["status"] == "SETTING_ERROR"
    assert client.client.post.call_args.args[0].endswith("/cockpit/reverify")

def test_client_refuses_before_readback():
    client = RadarClient("http://localhost:8000", "CLR-001")
    client.client = Mock()
    client.client.get.return_value.json.return_value = {
        "readback": None, "cockpit": None, "status": "WAITING_READBACK"}
    assert client.submit(Recognition(18000, 240, .9)) == {"skipped": "waiting_readback"}
    client.client.post.assert_not_called()
