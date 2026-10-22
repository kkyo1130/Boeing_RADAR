import importlib.util
from pathlib import Path
import struct
import wave
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("radar_audio_prepare", ROOT / "communication/radar_audio/audio.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def test_pcm_segments_and_silence(tmp_path):
    path = tmp_path / "input.wav"
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        target.writeframes(b"\0\0" * 32001)
    segments = list(audio.prepare(path, tmp_path / "segments", seconds=1))
    assert len(segments) == 3
    assert [s["offset_seconds"] for s in segments] == [0, 1, 2]
    assert len({s["segment_id"] for s in segments}) == 3
    assert all(s["quality_reasons"] == ["silence"] for s in segments)
    assert all("speaker_overlap" in s["unchecked"] for s in segments)


def test_clipped_and_bad_format(tmp_path):
    path = tmp_path / "input.wav"
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        target.writeframes(struct.pack('<h', 32767) * 16000)
    assert list(audio.prepare(path, tmp_path / "segments"))[0]["quality_reasons"] == ["clipped_audio"]
    with pytest.raises(ValueError):
        list(audio.prepare(path, tmp_path / "segments", seconds=0))
