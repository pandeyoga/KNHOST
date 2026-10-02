"""GRN Fase 4 — skrip evaluasi `tools/ocr_eval.py` dengan model tiruan (tanpa kunci, tanpa foto asli)."""
import asyncio
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, "/app/backend")
os.environ["OCR_ALLOW_MOCK"] = "1"
_LOOP = asyncio.new_event_loop()   # klien Motor terikat ke satu loop


def _goldset(tmp_path, answer):
    buf = io.BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(buf, "JPEG")
    (tmp_path / "S99_p1.jpg").write_bytes(buf.getvalue())
    (tmp_path / "S99.json").write_text(json.dumps(answer))
    return tmp_path


def _run(root, out):
    from tools import ocr_eval
    return _LOOP.run_until_complete(ocr_eval.run(root, "mock-sj_clear", "low", str(out)))


def test_eval_all_correct_passes_gate(tmp_path):
    root = _goldset(tmp_path, {"dn_number": "SJ-MOCK-CLEAR", "dn_date": "2026-06-10", "lines": [
        {"qty": 250, "unit": "yard", "rolls": 2, "po_ref": "KSC/PO-00014"}, {"is_non_stock": True}]})
    code = _run(root, tmp_path / "r.json")
    rep = json.loads((tmp_path / "r.json").read_text())
    assert code == 0 and rep["gate_pass"] is True
    assert rep["accuracy"]["dn_number"] == 1.0 and rep["accuracy"]["qty"] == 1.0 and rep["accuracy"]["non_stock"] == 1.0
    assert rep["wrong_unflagged"] == 0 and rep["cases"] == 1


def test_eval_reports_wrong_unflagged_line(tmp_path):
    root = _goldset(tmp_path, {"dn_number": "SJ-LAIN", "lines": [{"qty": 260, "unit": "yard", "rolls": 2}]})
    code = _run(root, tmp_path / "r.json")
    rep = json.loads((tmp_path / "r.json").read_text())
    assert code == 1 and rep["gate_pass"] is False
    assert rep["accuracy"]["dn_number"] == 0.0 and rep["accuracy"]["qty"] == 0.0
    assert rep["wrong_unflagged"] == 1 and "S99 baris 1" in rep["wrong_unflagged_detail"][0]
