"""Validate generated Java fixtures against the OpenAPI 3.0 contract (2.1.0).

Kunci fixture = nama skema, atau "NamaSkema#varian" untuk beberapa contoh skema yang sama (payload agent 0.5:
TagSummary, GpiEdge, PassageClose 2.1, GateDecision document_session/kuning/batal, Telemetry 0.5).
"""
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
print(f"Kontrak {document['info']['version']}")
fixtures = json.loads((project / "tests/contract-fixtures.json").read_text(encoding="utf-8"))

def validator(name):
    schema = {"$ref": f"#/components/schemas/{name}", "components": root["components"]}
    return jsonschema.Draft4Validator(schema, format_checker=jsonschema.FormatChecker())

passed = 0
for key, payload in fixtures.items():
    name = key.split("#")[0]
    validator(name).validate(payload)
    passed += 1
    print(f"PASS schema {key}")
print(f"PASS {passed} fixture payloads ({len({k.split('#')[0] for k in fixtures})} skema)")

# Validator harus menolak payload rusak (bukti skema benar-benar memeriksa).
negatives = [("GateDecision", lambda p: p.pop("local_passage_id")), ("EventsRequest", lambda p: p.pop("context"))]
if "TagSummary#latar" in fixtures:
    negatives += [
        ("TagSummary#latar", lambda p: p.pop("summary_id")),
        ("TagSummary#latar", lambda p: p.update(epc="e2-lowercase")),
        ("GpiEdge#a_blocked", lambda p: p.update(sensor="C")),
        ("PassageClose#photo_eye_exited", lambda p: p.update(close_reason="LEWAT")),
        ("PassageClose#photo_eye_exited", lambda p: p.update(sensor_health="rusak")),
        ("EventsRequest#ringkasan_photo_eye", lambda p: p.update(tag_summaries=[{}] * 501)),
        ("GateDecision#kuning", lambda p: p.update(indicator="ORANGE")),
    ]
for key, mutate in negatives:
    invalid = copy.deepcopy(fixtures[key])
    mutate(invalid)
    assert not validator(key.split("#")[0]).is_valid(invalid), f"Skema menerima payload rusak: {key}"
print(f"PASS {len(negatives)} negative schema checks")

# Template profil (docs/device-config.template.json) setelah kunci catatan "_..." dibuang harus lolos DeviceConfig 2.1;
# apa adanya (dengan catatan di tingkat atas) harus DITOLAK agar tidak terbit tanpa sengaja.
def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value

template = json.loads((project / "docs/device-config.template.json").read_text(encoding="utf-8"))
validator("DeviceConfig").validate(strip(template))
assert not validator("DeviceConfig").is_valid(template), "Template berisi catatan tidak boleh lolos skema"
params = strip(template)["logical_gates"][0]["passage_parameters"]
assert params["calibration_status"] == "initial", "Template wajib bertanda titik awal kalibrasi"
print("PASS template profil 2.1 (tanpa catatan) + penolakan template mentah")
