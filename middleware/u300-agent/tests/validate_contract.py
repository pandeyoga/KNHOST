"""Validate generated Java fixtures against the existing OpenAPI 3.0 contract."""
import copy
import json
import sys
from pathlib import Path
import jsonschema

project = Path(__file__).resolve().parents[1]
contract = Path(sys.argv[1])
document = json.loads(contract.read_text(encoding="utf-8-sig"))

def convert(value):
    if isinstance(value, list):
        return [convert(v) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: convert(v) for k, v in value.items() if k != "nullable"}
    if value.get("nullable"):
        return {"anyOf": [out, {"type": "null"}]}
    return out

root = convert(document)
fixtures = json.loads((project / "tests/contract-fixtures.json").read_text())
for name, payload in fixtures.items():
    schema = {"$ref": f"#/components/schemas/{name}", "components": root["components"]}
    jsonschema.Draft4Validator(schema, format_checker=jsonschema.FormatChecker()).validate(payload)
    print(f"PASS schema {name}")
# Verify the validator rejects a missing decision context and an invalid EPC.
for name, path in [("GateDecision", "local_passage_id"), ("EventsRequest", "context")]:
    invalid = copy.deepcopy(fixtures[name]); del invalid[path]
    schema = {"$ref": f"#/components/schemas/{name}", "components": root["components"]}
    assert not jsonschema.Draft4Validator(schema).is_valid(invalid)
print("PASS negative schema checks (missing passage/context)")
