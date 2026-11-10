"""Bounded hints from the flight's registered aliases, never from recognition targets."""
import hashlib
import json
import re

MAX_ALIASES = 16
MAX_CHARACTERS = 400


def callsign_context(registry, revision):
    """Use the session snapshot equally for all registered aircraft; fail closed on overflow."""
    aliases = sorted({" ".join(raw.split()) for entries in registry.values() for raw in entries.values()}, key=str.casefold)
    source_hash = hashlib.sha256(json.dumps(registry, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    reason = None
    if not aliases:
        reason = "empty_registry"
    elif any(not re.fullmatch(r"[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*", alias) for alias in aliases):
        reason = "unsupported_alias_characters"
    elif len(aliases) > MAX_ALIASES or len(", ".join(aliases)) > MAX_CHARACTERS:
        reason = "context_budget_exceeded"
    return {"source": "flight_callsign_registry", "revision": revision,
            "registry_sha256": source_hash, "enabled": reason is None,
            "reason": reason, "aliases": aliases if reason is None else [],
            "hotwords": ", ".join(aliases) if reason is None else None}
