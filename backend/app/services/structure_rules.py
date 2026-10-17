"""Bounded English grammar and numeric checks, with no AI/provider/DB calls.

This rechecks an extraction against the SAME transcript. It cannot establish
that ASR heard the audio correctly or serve as an independent safety channel.
"""
from datetime import datetime
import re

from app.schemas.structure_rules import RuleCheck, StructurePolicy, StructureResult

DIGITS = dict(zip(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"), range(10)))
DIGITS.update(oh=0, niner=9)


def normalize(value):
    return " ".join(re.sub(r"[,.]", " ", value.casefold()).split())


def digits(value):
    if re.fullmatch(r"[0-9]+", value):
        return value
    words = value.split()
    if words and all(word in DIGITS for word in words):
        return "".join(str(DIGITS[word]) for word in words)
    return None


def feet(value):
    direct = digits(value)
    if direct is not None:
        return int(direct)
    match = re.fullmatch(r"(one|two|three|four|five|six|seven|eight|nine) thousand(?: (one|two|three|four|five|six|seven|eight|nine) hundred)?", value)
    if match:
        return DIGITS[match[1]]*1000 + (DIGITS[match[2]]*100 if match[2] else 0)
    return None


def parse_command(command):
    """Consume the entire supported command; never drop unknown trailing words."""
    if len(command) > 2048:
        return {}, [(None, "NEEDS_REVIEW", "COMMAND_EXCEEDS_PARSER_LIMIT")]
    altitude = r"(?:climb and maintain|descend and maintain|maintain) (?P<alt>.+?)"
    heading = r"(?:turn (?:left|right) )?heading (?P<hdg>.+)"
    match = re.fullmatch(altitude+r"(?: (?:and )?"+heading+r")?", command)
    if not match:
        match = re.fullmatch(heading, command)
    if not match:
        return {}, [(None, "NEEDS_REVIEW", "UNSUPPORTED_SYNTAX")]
    values, issues = {}, []
    groups = match.groupdict()
    if groups.get("alt") is not None:
        text = groups["alt"]
        fl = re.fullmatch(r"(?:flight level |fl(?:\s+|(?=[0-9])))(.+)", text)
        ft = re.fullmatch(r"(.+) feet", text)
        if fl:
            number = digits(fl[1])
            if number is None or len(number) != 3:
                issues.append(("ALT", "INVALID", "FL_REQUIRES_THREE_DIGITS"))
            else:
                values["ALT"] = int(number)*100
        elif ft:
            number = feet(ft[1])
            if number is None:
                issues.append(("ALT", "NEEDS_REVIEW", "UNSUPPORTED_ALTITUDE_NUMBER"))
            else:
                values["ALT"] = number
        else:
            issues.append(("ALT", "NEEDS_REVIEW", "ALTITUDE_UNIT_NOT_EXPLICIT"))
    if groups.get("hdg") is not None:
        number = digits(groups["hdg"])
        if number is None:
            issues.append(("HDG", "NEEDS_REVIEW", "UNSUPPORTED_HEADING_NUMBER"))
        elif not 1 <= len(number) <= 3 or int(number) > 359:
            issues.append(("HDG", "INVALID", "HEADING_OUT_OF_RANGE"))
        else:
            values["HDG"] = int(number)
    return values, issues


def check_structure(data, *, target_callsign, registry, segment, instruction_id,
                    previous_targets, policy: StructurePolicy | None):
    checks, derived = [], {}

    def add(rule, status, reason, field=None):
        checks.append(RuleCheck(rule=rule, field=field, result=status, reason=reason))

    def finish():
        status = next((status for status in ("INVALID", "NEEDS_REVIEW")
            if any(check.result == status for check in checks)), "PASS")
        return StructureResult(observation_id=data["observation_id"], flight_id=data["flight_id"],
            segment_id=data["segment_id"], attempt_id=data["attempt_id"], result=status,
            policy_ref=policy.policy_ref if policy else None, derived_values=derived, checks=checks)

    context_keys = ("flight_id", "segment_id", "atc_input_id", "attempt_id")
    expected_role = "ATC" if data["source"] == "ATC" else "PILOT"
    if any(data[key] != segment[key] for key in context_keys) or segment["role"] != expected_role or (
        data["source"] == "READBACK" and data["instruction_id"] != instruction_id):
        add("context", "INVALID", "REGISTERED_CONTEXT_MISMATCH")
    else:
        add("context", "PASS", "REGISTERED_CONTEXT_MATCH")
    if not segment["complete"]:
        add("sequence", "NEEDS_REVIEW", "CAPTURE_INCOMPLETE")
    if data.get("observed_at") is None:
        add("sequence", "NEEDS_REVIEW", "CAPTURE_TIME_UNKNOWN")
    else:
        observed = datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
        started = datetime.fromisoformat(segment["started_at"].replace("Z", "+00:00"))
        ended = datetime.fromisoformat(segment["ended_at"].replace("Z", "+00:00"))
        processed = datetime.fromisoformat(data["processed_at"].replace("Z", "+00:00"))
        if observed != started or processed < ended:
            add("sequence", "INVALID", "CAPTURE_PROCESSING_ORDER_CONFLICT")
        else:
            add("sequence", "PASS", "CAPTURE_PROCESSING_ORDER_MATCH")
    call = data["callsign"]
    transcript = data.get("transcript")
    if not transcript:
        add("grammar", "NEEDS_REVIEW", "TRANSCRIPT_UNAVAILABLE")
        return finish()
    text = normalize(transcript)
    matches = [(canonical, alias, normalize(raw)) for canonical, aliases in registry.items()
        for alias, raw in aliases.items() if text.startswith(normalize(raw)+" ")]
    if len(matches) != 1:
        add("callsign", "NEEDS_REVIEW", "CALLSIGN_PREFIX_NOT_UNIQUE", "CALLSIGN")
        return finish()
    canonical, alias, raw = matches[0]
    if call["validity"] != "VALID":
        add("callsign", "NEEDS_REVIEW", "CALLSIGN_UNREADABLE", "CALLSIGN")
    elif call["value"] != canonical or call["alias_key"] != alias or normalize(call["raw_text"] or "") != raw:
        add("callsign", "INVALID", "CALLSIGN_EXTRACTION_CONFLICT", "CALLSIGN")
    elif canonical != target_callsign:
        add("callsign", "NEEDS_REVIEW", "CALLSIGN_OUT_OF_TARGET", "CALLSIGN")
    else:
        add("callsign", "PASS", "REGISTERED_CALLSIGN_MATCH", "CALLSIGN")
    command = text[len(raw)+1:]
    if re.search(r"\b(if|after|before|until|when|then|unless)\b", command):
        add("conditions", "NEEDS_REVIEW", "UNSUPPORTED_CONDITION_OR_SEQUENCE")
        return finish()
    derived, issues = parse_command(command)
    for field, status, reason in issues:
        add("grammar", status, reason, field)
    if not issues:
        add("grammar", "PASS", "SUPPORTED_COMPLETE_COMMAND")
    fields = data["fields"]
    if data["mention_status"] != "KNOWN":
        add("scope", "NEEDS_REVIEW", "MENTION_SCOPE_UNKNOWN")
    elif set(data["mentioned_fields"]) != set(fields) or len(data["mentioned_fields"]) != len(fields):
        add("scope", "INVALID", "MENTION_FIELD_SET_CONFLICT")
    elif not issues and set(derived) != set(fields):
        add("scope", "INVALID", "TRANSCRIPT_FIELD_SET_CONFLICT")
    else:
        add("scope", "PASS", "MENTION_FIELD_SET_MATCH")
    for name, field in fields.items():
        if name not in ("ALT", "HDG"):
            add("range", "INVALID", "UNSUPPORTED_FIELD")
            continue
        value = field["value"]
        if field["validity"] != "VALID" or value is None:
            add("value", "NEEDS_REVIEW", "FIELD_UNREADABLE", name)
            continue
        if type(value) is not int or value < 0 or (name == "HDG" and value > 359):
            add("range", "INVALID", "VALUE_OUT_OF_RANGE", name)
            continue
        if field["unit"] != ("ft" if name == "ALT" else "deg"):
            add("unit", "INVALID", "NORMALIZED_UNIT_CONFLICT", name)
            continue
        raw_text = field.get("raw_text")
        raw_value, raw_issues = None, []
        if raw_text and len(raw_text) <= 128:
            raw = normalize(raw_text)
            if name == "ALT" and (re.match(r"(?:flight level\b|fl(?:\s|[0-9]))", raw) or raw.endswith(" feet")):
                raw_values, raw_issues = parse_command("maintain " + raw)
                raw_value = raw_values.get("ALT")
            elif name == "ALT":
                raw_value = feet(raw)
            else:
                number = digits(raw)
                raw_value = int(number) if number is not None else None
        if raw_issues:
            for _, status, raw_reason in raw_issues:
                add("raw_field", status, raw_reason, name)
        elif raw_value is None:
            add("raw_field", "NEEDS_REVIEW", "RAW_FIELD_TEXT_UNSUPPORTED_OR_MISSING", name)
        elif raw_value != value:
            add("raw_field", "INVALID", "RAW_FIELD_VALUE_CONFLICT", name)
        else:
            add("raw_field", "PASS", "RAW_FIELD_VALUE_MATCH", name)
        if name in derived and derived[name] != value:
            add("extraction", "INVALID", "TRANSCRIPT_VALUE_CONFLICT", name)
        elif name in derived:
            add("extraction", "PASS", "TRANSCRIPT_VALUE_MATCH", name)
        if name == "ALT":
            if policy is None or policy.max_altitude_ft is None:
                add("ceiling", "NEEDS_REVIEW", "ALTITUDE_CEILING_NOT_CONFIGURED", name)
            elif value > policy.max_altitude_ft:
                add("ceiling", "INVALID", "ALTITUDE_EXCEEDS_CONFIGURED_CEILING", name)
            else:
                add("ceiling", "PASS", "WITHIN_CONFIGURED_CEILING", name)
        if data["source"] != "ATC":
            continue  # ATC/readback numeric equality belongs to WI-02.
        limit = None if policy is None else (policy.max_altitude_change_ft if name == "ALT" else policy.max_heading_change_deg)
        previous = previous_targets.get(name)
        if limit is None:
            add("change", "NEEDS_REVIEW", "CHANGE_LIMIT_NOT_CONFIGURED", name)
        elif previous is None:
            add("change", "PASS", "INITIAL_TARGET_NO_CHANGE_BASELINE", name)
        else:
            delta = abs(value-previous["value"])
            if name == "HDG":
                delta = min(delta, 360-delta)
            add("change", "NEEDS_REVIEW" if delta > limit else "PASS",
                "ABRUPT_TARGET_CHANGE" if delta > limit else "WITHIN_CONFIGURED_CHANGE", name)
    return finish()
