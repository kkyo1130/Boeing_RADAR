"""PCM WAV preparation and explicit, operator-labelled channels."""
import math
import struct
import wave
from pathlib import Path
from uuid import uuid4


def prepare(path, output, *, seconds=15):
    if not 1 <= seconds <= 30:
        raise ValueError("segment length must be 1..30 seconds")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "rb") as source:
        channels, width, rate, frames = (source.getnchannels(), source.getsampwidth(),
                                       source.getframerate(), source.getnframes())
        if channels not in (1, 2) or width != 2 or not 8000 <= rate <= 96000:
            raise ValueError("use 16-bit PCM WAV, mono/stereo, 8..96 kHz")
        if frames / rate > 600:
            raise ValueError("input exceeds 10 minutes")
        position = 0
        while raw := source.readframes(seconds * rate):
            values = struct.unpack("<" + "h" * (len(raw) // 2), raw)
            mono = [round(sum(values[i:i+channels]) / channels)
                    for i in range(0, len(values), channels)]
            rms = math.sqrt(sum(v*v for v in mono) / max(len(mono), 1)) / 32768
            clipped = sum(abs(v) >= 32700 for v in values) / max(len(values), 1)
            reasons = (["silence"] if rms < .002 else ["weak_signal"] if rms < .01 else [])
            if clipped > .01:
                reasons.append("clipped_audio")
            # Fixed windows deliberately make no claim to infer speaker identity or overlap.
            token = str(uuid4())
            target = output / f"{token}.wav"
            with wave.open(str(target), "wb") as destination:
                destination.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                destination.writeframes(struct.pack("<" + "h" * len(mono), *mono))
            yield {"segment_id": token, "path": str(target), "original": str(path),
                   "offset_seconds": position / rate, "duration_seconds": len(mono) / rate,
                   "rms": rms, "quality_reasons": reasons,
                   "unchecked": ["speaker_overlap", "background_noise", "warning_feedback"]}
            position += len(mono)


def record_microphone(path, seconds, device=None):
    if not 1 <= seconds <= 30:
        raise ValueError("microphone duration must be 1..30 seconds")
    import sounddevice as sd
    from datetime import datetime, timezone
    started = datetime.now(timezone.utc).isoformat()
    samples = sd.rec(round(seconds * 16000), samplerate=16000, channels=1,
                     dtype="int16", device=device, blocking=True)
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        target.writeframes(samples.tobytes())
    return started
