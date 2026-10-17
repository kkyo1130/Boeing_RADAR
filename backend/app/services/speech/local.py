"""Local faster-whisper, explicit small grammar, no invented confidence."""
import math
import re


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
                                               condition_on_previous_text=False, vad_filter=True)
        rows = list(segments)
        speech = [s for s in rows if math.isfinite(s.no_speech_prob) and 0 <= s.no_speech_prob < .6]
        score = (min(math.exp(min(0., s.avg_logprob)) for s in speech)
                 if speech and all(math.isfinite(s.avg_logprob) for s in speech) else None)
        return {"transcript": " ".join(s.text.strip() for s in speech),
                "model_score": score, "score_calibrated": False,
                "segments": [{"start": s.start, "end": s.end, "text": s.text,
                              "no_speech_prob": s.no_speech_prob} for s in rows]}


DIGITS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3",
          "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
          "nine": "9", "niner": "9"}


def structure(transcript, callsign):
    """Supported numeric grammar only. Unknown clauses force review rather than disappear."""
    text = re.sub(r"[,.!?]", " ", transcript.lower())
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    converted = []
    index = 0
    while index < len(words):
        if words[index] in DIGITS:
            digits = []
            while index < len(words) and words[index] in DIGITS:
                digits.append(DIGITS[words[index]])
                index += 1
            converted.append("".join(digits))
        else:
            converted.append(words[index])
            index += 1
    normalized = " ".join(converted)
    fields = {}
    actions = []
    spans = []
    patterns = {"altitude": r"(?:altitude|climb(?: and maintain)?|descend(?: and maintain)?|maintain)\s+(\d{1,5})(?:\s+feet)?",
                "heading": r"(?:heading|turn (?:left|right)(?: heading)?)\s+(\d{1,3})(?:\s+degrees)?"}
    for name, pattern in patterns.items():
        matches = list(re.finditer(pattern, normalized))
        valid = len(matches) == 1
        value = int(matches[0][1]) if valid else None
        if name == "heading" and value is not None and value > 359:
            valid = False
        fields[name] = {"value": value if valid else None,
                        "raw_text": matches[0][1] if len(matches) == 1 else None,
                        "reason": None if valid else "ambiguous_or_missing_number"}
        for match in matches:
            actions.append((match.start(), f"{name} {int(match[1])}"))
            spans.append(match.span())
    remainder = normalized
    for start, end in sorted(spans, reverse=True):
        remainder = remainder[:start] + " " + remainder[end:]
    # Callsign is supplied by operator but must independently occur in the transcript.
    parts = re.fullmatch(r"([a-zA-Z]+)([0-9]+)", callsign)
    call_pattern = (r"(?<!\w)" + re.escape(parts[1].lower()) + r"\s*" + parts[2] + r"(?!\w)"
                    if parts else r"(?<!\w)" + re.escape(callsign.lower()) + r"(?!\w)")
    found = bool(re.search(call_pattern, normalized))
    remainder = re.sub(call_pattern, " ", remainder)
    remainder = re.sub(r"\b(?:and|to|roger)\b", " ", remainder).strip()
    if remainder:
        for field in fields.values():
            if field["value"] is not None:
                field.update(value=None, reason="unsupported_speech_clause")
    return {"fields": fields, "speech": {"transcript": transcript,
        "callsign": callsign if found else None,
        "callsign_reason": None if found else "callsign_not_recognized",
        "role_basis": "operator_assigned_channel", "conditions": [remainder] if remainder else [],
        "ordered_actions": [a for _, a in sorted(actions)]},
        "mentioned": {"altitude": bool(re.search(r"\b(?:altitude|climb|descend|maintain)\b", normalized)),
                      "heading": bool(re.search(r"\b(?:heading|turn)\b", normalized))},
        "quality_reasons": ["unsupported_speech_clause"] if remainder else []}
