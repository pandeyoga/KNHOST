import importlib.util
import json
import tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("snapshot", root / "verify-snapshot.py")
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows = [
    {"kind":"snapshot_header","schema_version":1},
    {"table":"passages","record":{"id":"p1"}},
    {"table":"events","record":{"id":"e1","passage":"p1"}},
    {"kind":"snapshot_end","complete":True,"record_count":2},
]
with tempfile.TemporaryDirectory(dir=root / "tests") as folder:
    file = Path(folder)/"fixture.jsonl"
    file.write_text("\n".join(map(json.dumps,rows)),encoding="utf-8")
    assert module.verify(file)["events"] == 1
    for invalid in [rows[:-1],rows+rows[-1:],rows[:2]+[rows[2],rows[2]]+[rows[3]], [rows[0],rows[2],{"kind":"snapshot_end","complete":True,"record_count":1}]]:
        file.write_text("\n".join(map(json.dumps,invalid)),encoding="utf-8")
        try: module.verify(file)
        except AssertionError: pass
        else: raise AssertionError("Invalid snapshot was accepted")
print("PASS: 5 snapshot integrity cases")
