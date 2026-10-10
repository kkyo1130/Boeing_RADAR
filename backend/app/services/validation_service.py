from app.core.enums import ClearanceStatus as Status

def compare(expected, actual):
    return [{"field": field, "expected": expected[key], "actual": actual[key]}
            for key, field in (("altitude", "ALT"), ("heading", "HDG"))
            if expected[key] != actual[key]]

def validate(atc, readback=None, cockpit=None):
    if readback is None:
        return Status.WAITING_READBACK, []
    errors = compare(atc, readback)
    if errors:
        return Status.READBACK_ERROR, errors
    if cockpit is None:
        return Status.WAITING_COCKPIT, []
    errors = compare(atc, cockpit)
    return (Status.SETTING_ERROR, errors) if errors else (Status.VERIFIED, [])
