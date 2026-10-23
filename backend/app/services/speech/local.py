"""Local faster-whisper, no invented confidence."""
import math


class LocalWhisper:
    def __init__(self, model_path, device="cpu"):
        from pathlib import Path
        if not Path(model_path).is_dir():
            raise ValueError("Supply an existing local faster-whisper model directory")
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_path, device=device, compute_type="int8",
                                  local_files_only=True)

    def transcribe(self, path):
        segments, info = self.model.transcribe(str(path), language="en", beam_size=5,
                                               condition_on_previous_text=False, vad_filter=True,
                                               initial_prompt=("Air traffic control phraseology: climb and maintain, "
                                                   "descend and maintain, feet, flight level, turn left, turn right, "
                                                   "heading. Numbers: zero, one, two, three, four, five, six, "
                                                   "seven, eight, nine, thousand, hundred."))
        rows = list(segments)
        speech = [s for s in rows if math.isfinite(s.no_speech_prob) and 0 <= s.no_speech_prob < .6]
        score = (min(math.exp(min(0., s.avg_logprob)) for s in speech)
                 if speech and all(math.isfinite(s.avg_logprob) for s in speech) else None)
        return {"transcript": " ".join(s.text.strip() for s in speech),
                "model_score": score, "score_calibrated": False,
                "segments": [{"start": s.start, "end": s.end, "text": s.text,
                              "no_speech_prob": s.no_speech_prob} for s in rows]}
