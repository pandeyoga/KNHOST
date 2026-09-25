"""GRN Fase 4 — evaluasi OCR surat jalan terhadap set emas (foto TIDAK disimpan di repo).

Folder `OCR_GOLDSET_DIR`: per SJ satu kunci jawaban `<kode>.json` + halaman `<kode>*.jpg|jpeg|png|pdf` (urut nama).
Kunci jawaban:
  {"dn_number": "…", "dn_date": "YYYY-MM-DD",
   "lines": [{"qty": 994, "unit": "yard", "rolls": 8, "po_ref": "3374/SCB/0926", "is_non_stock": false}, …]}

Pakai:  cd /app/backend && OCR_GOLDSET_DIR=/path python -m tools.ocr_eval [--model gpt-6-sol] [--effort low] [--json out.json]
Laporan: akurasi per field (nomor SJ, tanggal, qty, satuan, roll, PO per baris), baris salah yang TIDAK ditandai, biaya per lembar.
Gerbang lanjut (§5 Fase 4): qty & satuan ≥ 95%, nomor SJ ≥ 98%, baris salah tak ditandai ≤ 1%.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from services import dn_rules as R  # noqa: E402
from services.goods_receipt_ocr_service import _parse_quantities, cost_usd, ocr_config, pages_from_bytes  # noqa: E402
from services.goods_receipt_service import norm_dn  # noqa: E402
from services.ocr_openai_client import OcrError, extract  # noqa: E402

EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
GATE = {"dn_number": 0.98, "qty": 0.95, "unit": 0.95}


def cases(root: Path) -> List[Dict[str, Any]]:
    out = []
    for key in sorted(root.glob("*.json")):
        pages = sorted(p for p in root.iterdir() if p.stem.startswith(key.stem) and p.suffix.lower() in EXT)
        if pages:
            out.append({"code": key.stem, "answer": json.loads(key.read_text()), "pages": pages})
    return out


def _flagged(line: Dict[str, Any], qty_parse: str) -> bool:
    return (line.get("legibility") != "clear" or bool(line.get("handwritten_correction")) or qty_parse != "ok")


def _core(txt: Any) -> str:
    cores = R.po_cores([txt], R.DEFAULT_PO_PATTERNS)
    return cores[0] if cores else norm_dn(str(txt or ""))


def score_case(ans: Dict[str, Any], data: Dict[str, Any], tally: Dict[str, List[int]], bad: List[str], code: str) -> None:
    h = data.get("header") or {}
    tally["dn_number"].append(int(norm_dn(h.get("dn_number")) == norm_dn(ans.get("dn_number"))))
    if ans.get("dn_date"):
        tally["dn_date"].append(int((h.get("dn_date") or "") == ans["dn_date"]))
    lines = [dict(x) for x in data.get("lines") or []]
    _parse_quantities(lines, data.get("totals") or [], "unknown")
    for i, exp in enumerate(ans.get("lines") or []):
        got = lines[i] if i < len(lines) else {}
        if exp.get("is_non_stock"):
            tally["non_stock"].append(int(bool(got.get("is_non_stock"))))
            continue
        d = R.pick_declared(got.get("quantities") or [], exp.get("unit") or "")
        ok = {"qty": d["qty"] is not None and abs(float(d["qty"]) - float(exp["qty"])) < 0.01,
              "unit": d["unit"] == exp.get("unit"),
              "rolls": exp.get("rolls") is None or d["rolls"] == exp.get("rolls"),
              "po_ref": not exp.get("po_ref") or _core(got.get("po_ref")) == _core(exp["po_ref"])}
        for k, v in ok.items():
            tally[k].append(int(v))
        wrong = not all(ok.values())
        tally["lines"].append(1)
        if wrong and not _flagged(got, d["qty_parse"]):
            tally["wrong_unflagged"].append(1)
            bad.append(f"{code} baris {i + 1}: {ok} — dibaca {d['qty']} {d['unit']} / {d['rolls']} roll")


async def run(root: Path, model: str, effort: str, out_json: str) -> int:
    cfg = await ocr_config("")
    model = model or cfg["ocr_model_primary"]
    tally: Dict[str, List[int]] = {k: [] for k in ("dn_number", "dn_date", "qty", "unit", "rolls", "po_ref",
                                                   "non_stock", "lines", "wrong_unflagged")}
    bad: List[str] = []
    cost, pages_total, failed = 0.0, 0, []
    for c in cases(root):
        parts, n, _ = pages_from_bytes([(p.read_bytes(), EXT[p.suffix.lower()]) for p in c["pages"]], cfg)
        try:
            r = await extract(parts, n, model=model, reasoning_effort=effort or cfg["ocr_reasoning_effort"],
                              max_output_tokens=int(cfg["ocr_max_output_tokens"]), extract_packing_list=False)
        except OcrError as e:
            failed.append(f"{c['code']}: {e.code} {e.message}")
            continue
        cost += cost_usd(r["usage"], model, cfg["ocr_price_table"])
        pages_total += n
        score_case(c["answer"], r["data"], tally, bad, c["code"])
        print(f"  {c['code']}: {n} lembar · {r['latency_ms']} ms")
    acc = {k: (round(sum(v) / len(v), 4) if v else None) for k, v in tally.items() if k not in ("lines", "wrong_unflagged")}
    n_lines = len(tally["lines"])
    report = {"model": model, "effort": effort or cfg["ocr_reasoning_effort"], "cases": len(cases(root)), "failed": failed,
              "accuracy": acc, "lines": n_lines, "wrong_unflagged": len(tally["wrong_unflagged"]),
              "wrong_unflagged_rate": round(len(tally["wrong_unflagged"]) / n_lines, 4) if n_lines else None,
              "cost_usd": round(cost, 4), "cost_per_page": round(cost / pages_total, 5) if pages_total else None,
              "wrong_unflagged_detail": bad}
    report["gate_pass"] = bool(n_lines) and all((acc.get(k) or 0) >= v for k, v in GATE.items()) and \
        (report["wrong_unflagged_rate"] or 0) <= 0.01
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if out_json:
        Path(out_json).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if report["gate_pass"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="")
    ap.add_argument("--effort", default="", choices=["", "none", "low", "medium"])
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    root = Path(os.environ.get("OCR_GOLDSET_DIR", ""))
    if not root.is_dir():
        print("Set OCR_GOLDSET_DIR ke folder set emas (foto + JSON kunci jawaban).")
        return 2
    return asyncio.run(run(root, a.model, a.effort, a.json))


if __name__ == "__main__":
    sys.exit(main())
