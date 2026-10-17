#!/usr/bin/env python3
"""Export or independently validate SPEC-002 v2 schemas and fixture expectations.

Run with backend/.venv/bin/python from any working directory. No server or
hardware access; no application database is opened.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.observation_v2 import SCHEMA_MODELS  # noqa: E402


def rendered_schemas():
    rendered = {}
    for name, model in SCHEMA_MODELS.items():
        schema = model.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"urn:radar:contracts:{name}"
        rendered[name] = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    return rendered


def check():
    from jsonschema import Draft202012Validator, FormatChecker
    from pydantic import ValidationError

    validators = {}
    for name, rendered in rendered_schemas().items():
        path = ROOT / "contracts" / "schemas" / f"{name}.schema.json"
        if not path.exists() or path.read_text() != rendered:
            raise ValueError(f"schema out of date: {path.relative_to(ROOT)}")
        schema = json.loads(rendered)
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema, format_checker=FormatChecker())
    examples = ROOT / "contracts" / "examples" / "v2"
    manifest = json.loads((examples / "manifest.json").read_text())
    names = [case["file"] for case in manifest]
    if len(names) != len(set(names)):
        raise ValueError("duplicate fixture filename")
    actual = {p.name for p in examples.glob("*.json") if p.name != "manifest.json"}
    if actual != set(names):
        raise ValueError("all fixtures must appear in the manifest exactly once")
    for case in manifest:
        payload = json.loads((examples / case["file"]).read_text())
        name = case["schema"]
        structural = validators[name].is_valid(payload)
        try:
            SCHEMA_MODELS[name].model_validate(payload)
            semantic = True
        except ValidationError:
            semantic = False
        if structural != case["schema_valid"] or semantic != case["valid"]:
            raise ValueError(
                f"{case['file']}: schema={structural}, DTO={semantic}; "
                f"expected schema={case['schema_valid']}, DTO={case['valid']}"
            )
    print(f"PASS: {len(validators)} JSON Schemas, {len(manifest)} fixture expectations (Schema + DTO)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate checked-in schemas from DTOs")
    args = parser.parse_args()
    if args.write:
        folder = ROOT / "contracts" / "schemas"
        folder.mkdir(exist_ok=True)
        for name, rendered in rendered_schemas().items():
            (folder / f"{name}.schema.json").write_text(rendered)
        print(f"Wrote {len(SCHEMA_MODELS)} schemas")
    else:
        check()


if __name__ == "__main__":
    main()
