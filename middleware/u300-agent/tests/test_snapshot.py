import importlib.util
import json
import tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("snapshot", root / "verify-snapshot.py")
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
v1 = [
    {"kind":"snapshot_header","schema_version":1},
    {"table":"passages","record":{"id":"p1"}},
    {"table":"events","record":{"id":"e1","passage":"p1"}},
    {"kind":"snapshot_end","complete":True,"record_count":2},
]
v2 = [
    {"kind":"snapshot_header","schema_version":2},
    {"table":"passages","record":{"id":"p1"}},
    {"table":"items","record":{"kind":"summary","id":"p1:E2:1","passage":"p1"}},
    {"table":"items","record":{"kind":"edge","id":"p1:g:0","passage":"p1"}},
    {"table":"events_v1_archive","record":{"id":"e1","passage":"p1"}},
    {"table":"bench","record":{"id":1,"run":"r","item":1}},
    {"kind":"snapshot_end","complete":True,"record_count":5},
]
cases = 0
with tempfile.TemporaryDirectory(dir=root / "tests") as folder:
    file = Path(folder)/"fixture.jsonl"
    for rows, check in [(v1, lambda r: r["events"] == 1), (v2, lambda r: r["items"] == 2 and r["events"] == 1)]:
        file.write_text("\n".join(map(json.dumps,rows)),encoding="utf-8")
        assert check(module.verify(file)); cases += 1
    invalids = [v1[:-1], v1+v1[-1:], v1[:2]+[v1[2],v1[2]]+[v1[3]], [v1[0],v1[2],{"kind":"snapshot_end","complete":True,"record_count":1}],
                v2[:3]+[v2[2]]+[{"kind":"snapshot_end","complete":True,"record_count":4}],
                [v2[0],{"table":"items","record":{"kind":"bogus","id":"x","passage":"p1"}},v2[1],{"kind":"snapshot_end","complete":True,"record_count":2}],
                [v1[0],v2[2],{"kind":"snapshot_end","complete":True,"record_count":1}]]
    for invalid in invalids:
        file.write_text("\n".join(map(json.dumps,invalid)),encoding="utf-8")
        try: module.verify(file)
        except AssertionError: pass
        else: raise AssertionError("Invalid snapshot was accepted")
        cases += 1
print(f"PASS: {cases} snapshot integrity cases")
