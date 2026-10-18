"""Sampel Uji OCR — foto SJ nyata + kunci jawaban yang dicek manusia, untuk mengukur ketepatan baca sebelum dipakai harian.

Koleksi `ocr_samples` (sampel) & `ocr_sample_runs` (hasil uji). Uji memakai jalur baca yang sama dengan GRN
(putar otomatis → petunjuk mitra → model utama), dicatat di `ai_usage_log` (feature `ocr_dn`, role `eval`) agar ikut rem anggaran.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso
from db import db
from services import dn_rules as R
from services import goods_receipt_ocr_service as go
from services.goods_receipt_service import norm_dn
from services.ocr_openai_client import OcrError, extract

logger = logging.getLogger(__name__)
GATE = {"dn_number": 0.98, "qty": 0.95, "unit": 0.95}
FIELDS = ("dn_number", "dn_date", "qty", "unit", "rolls", "po_ref")
_READY = ("review", "counting", "reconcile", "closing", "closed")


def _answer_line(ln: Dict[str, Any], patterns: List[str]) -> Dict[str, Any]:
    d, rd = ln.get("declared") or {}, ln.get("read") or {}
    cores = R.po_cores([rd.get("po_ref")] if rd.get("po_ref") else [rd.get(k) for k in ("description", "lot", "row_text")], patterns)
    return {"description": (rd.get("description") or "")[:120], "qty": d.get("qty"), "unit": d.get("unit") or "",
            "rolls": d.get("rolls"), "po_ref": cores[0] if cores else None, "is_non_stock": bool(ln.get("is_non_stock"))}


def clean_answer(a: Dict[str, Any]) -> Dict[str, Any]:
    lines = [{"description": str(x.get("description") or "")[:120], "qty": float(x["qty"]) if x.get("qty") not in (None, "") else None,
              "unit": str(x.get("unit") or ""), "rolls": int(x["rolls"]) if x.get("rolls") not in (None, "") else None,
              "po_ref": str(x.get("po_ref") or "").strip() or None, "is_non_stock": bool(x.get("is_non_stock"))}
             for x in a.get("lines") or []]
    return {"dn_number": str(a.get("dn_number") or "").strip(), "dn_date": str(a.get("dn_date") or "").strip(),
            "supplier_name": str(a.get("supplier_name") or "").strip(), "lines": lines}


async def create(entity_id: str, *, label: str, partner_id: str, partner_name: str, files: List[Dict[str, Any]],
                 answer: Dict[str, Any], actor: str, source_grn_id: str = "", source_grn_number: str = "") -> Dict[str, Any]:
    doc = {"id": new_id("ocs"), "entity_id": entity_id, "label": label.strip()[:120] or partner_name or "Sampel SJ",
           "partner_id": partner_id, "partner_name": partner_name, "files": files, "answer": clean_answer(answer),
           "source_grn_id": source_grn_id, "source_grn_number": source_grn_number, "last_result": None,
           "created_by": actor, "created_at": now_iso(), "updated_at": now_iso()}
    await db.ocr_samples.insert_one(dict(doc))
    return doc


async def create_from_grn(grn_id: str, label: str, actor: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
    from services.goods_receipt_service import load
    from services.supplier_dn_profile_service import record_corrections
    grn = await load(grn_id, ctx)
    if grn.get("status") not in _READY:
        raise HTTPException(status_code=400, detail="Sampel hanya dari kedatangan yang surat jalannya sudah dicek (Tinjau SJ ke atas).")
    if not grn.get("files"):
        raise HTTPException(status_code=400, detail="Kedatangan ini tidak punya foto surat jalan.")
    if await db.ocr_samples.find_one({"source_grn_id": grn_id}):
        raise HTTPException(status_code=409, detail="Kedatangan ini sudah dijadikan sampel uji.")
    cfg = await go.ocr_config(grn["entity_id"])
    dn = grn.get("dn") or {}
    answer = {"dn_number": dn.get("number"), "dn_date": dn.get("date"), "supplier_name": dn.get("supplier_name_printed"),
              "lines": [_answer_line(ln, cfg["client_po_patterns"]) for ln in grn.get("lines") or []
                        if ln.get("decision") != "reject_line"]}
    files = [{"page": f["page"], "path": f["path"], "content_type": f["content_type"]} for f in sorted(grn["files"], key=lambda x: x["page"])]
    await record_corrections(grn)   # koreksi manusia pada SJ ini langsung jadi petunjuk untuk mitra yang sama
    return await create(grn["entity_id"], label=label, partner_id=grn["partner_id"], partner_name=grn.get("partner_name", ""),
                        files=files, answer=answer, actor=actor["name"], source_grn_id=grn_id, source_grn_number=grn.get("number", ""))


async def _get(sample_id: str, entity_id: str) -> Dict[str, Any]:
    doc = await db.ocr_samples.find_one({"id": sample_id, "entity_id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Sampel uji tidak ditemukan.")
    return doc


async def list_samples(entity_id: str) -> List[Dict[str, Any]]:
    return await db.ocr_samples.find({"entity_id": entity_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


async def update(sample_id: str, entity_id: str, label: Optional[str], answer: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    await _get(sample_id, entity_id)
    set_: Dict[str, Any] = {"updated_at": now_iso()}
    if label is not None:
        set_["label"] = label.strip()[:120]
    if answer is not None:
        set_["answer"] = clean_answer(answer)
    await db.ocr_samples.update_one({"id": sample_id}, {"$set": set_})
    return await _get(sample_id, entity_id)


async def delete(sample_id: str, entity_id: str) -> None:
    await _get(sample_id, entity_id)
    await db.ocr_samples.delete_one({"id": sample_id})


async def file_bytes(sample_id: str, entity_id: str, page: int):
    from services import storage_service as st
    doc = await _get(sample_id, entity_id)
    f = next((x for x in doc["files"] if x["page"] == page), None)
    if not f:
        raise HTTPException(status_code=404, detail="Halaman tidak ada.")
    return (await st.get_object(f["path"]))[0], f["content_type"]


# ── penilaian ────────────────────────────────────────────────────────────────
def score(answer: Dict[str, Any], data: Dict[str, Any], patterns: List[str]) -> Dict[str, Any]:
    h = data.get("header") or {}
    checks: Dict[str, List[int]] = {k: [] for k in FIELDS}
    header = {"dn_number": {"expected": answer.get("dn_number"), "got": h.get("dn_number")},
              "dn_date": {"expected": answer.get("dn_date"), "got": h.get("dn_date")}}
    if answer.get("dn_number"):
        header["dn_number"]["ok"] = norm_dn(h.get("dn_number")) == norm_dn(answer["dn_number"])
        checks["dn_number"].append(int(header["dn_number"]["ok"]))
    if answer.get("dn_date"):
        header["dn_date"]["ok"] = (h.get("dn_date") or "") == answer["dn_date"]
        checks["dn_date"].append(int(header["dn_date"]["ok"]))
    got_lines = [dict(x) for x in data.get("lines") or [] if not x.get("is_non_stock")]
    go._parse_quantities(got_lines, data.get("totals") or [], "unknown")
    exp_lines = [x for x in answer.get("lines") or [] if not x.get("is_non_stock")]
    lines = []
    for i in range(max(len(exp_lines), len(got_lines))):
        exp = exp_lines[i] if i < len(exp_lines) else None
        got = got_lines[i] if i < len(got_lines) else None
        if exp is None:
            lines.append({"line_no": i + 1, "status": "extra", "got": (got.get("description") or "")[:80]})
            checks["qty"].append(0)
            continue
        if got is None:
            lines.append({"line_no": i + 1, "status": "missing", "expected": exp})
            checks["qty"].append(0)
            checks["unit"].append(0)
            continue
        d = R.pick_declared(got.get("quantities") or [], exp.get("unit") or "")
        row = [got.get("po_ref")] if got.get("po_ref") else [got.get(k) for k in ("description", "lot", "row_text")]
        cores = R.po_cores(row, patterns)
        ok = {"qty": d["qty"] is not None and exp.get("qty") is not None and abs(float(d["qty"]) - float(exp["qty"])) < 0.01,
              "unit": d["unit"] == exp.get("unit")}
        if exp.get("rolls") is not None:
            ok["rolls"] = d["rolls"] == exp["rolls"]
        if exp.get("po_ref"):
            want = (R.po_cores([exp["po_ref"]], patterns) or [norm_dn(exp["po_ref"])])[0]
            ok["po_ref"] = want in cores
        for k, v in ok.items():
            checks[k].append(int(v))
        lines.append({"line_no": i + 1, "status": "ok" if all(ok.values()) else "wrong", "ok": ok, "expected": exp,
                      "got": {"qty": d["qty"], "unit": d["unit"], "rolls": d["rolls"], "po_ref": cores[0] if cores else None,
                              "description": (got.get("description") or "")[:80]}})
    return {"header": header, "lines": lines, "checks": checks}


def aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    tally: Dict[str, List[int]] = {k: [] for k in FIELDS}
    for r in results:
        for k, v in ((r.get("score") or {}).get("checks") or {}).items():
            tally[k] += v
    acc = {k: (round(sum(v) / len(v), 4) if v else None) for k, v in tally.items()}
    done = [r for r in results if r.get("status") in ("ok", "failed")]
    return {"accuracy": acc, "counts": {k: [sum(v), len(v)] for k, v in tally.items()},
            "gate_pass": bool(done) and all(r["status"] == "ok" for r in done) and
            all((acc.get(k) or 0) >= v for k, v in GATE.items()), "gate": GATE}


# ── menjalankan uji ─────────────────────────────────────────────────────────
async def start_run(entity_id: str, sample_ids: List[str], actor: str) -> Dict[str, Any]:
    flt: Dict[str, Any] = {"entity_id": entity_id, **({"id": {"$in": sample_ids}} if sample_ids else {})}
    samples = await db.ocr_samples.find(flt, {"_id": 0, "id": 1, "label": 1}).to_list(200)
    if not samples:
        raise HTTPException(status_code=400, detail="Belum ada sampel uji untuk dijalankan.")
    if await db.ocr_sample_runs.find_one({"entity_id": entity_id, "status": "running"}):
        raise HTTPException(status_code=409, detail="Masih ada uji yang berjalan. Tunggu sampai selesai.")
    cfg = await go.ocr_config(entity_id)
    run = {"id": new_id("ocr_run"), "entity_id": entity_id, "status": "running", "model": cfg["ocr_model_primary"],
           "orient_model": cfg["ocr_orient_model"] if cfg["ocr_auto_orient"] else "", "total": len(samples), "done": 0,
           "cost_usd": 0.0, "results": [{"sample_id": s["id"], "label": s["label"], "status": "pending"} for s in samples],
           "summary": None, "created_by": actor, "created_at": now_iso(), "finished_at": ""}
    await db.ocr_sample_runs.insert_one(dict(run))
    asyncio.create_task(_run(run["id"], entity_id, actor))
    return run


async def _one(sample: Dict[str, Any], cfg: Dict[str, Any], run_id: str, actor: str) -> Dict[str, Any]:
    from services import storage_service as st
    from services.supplier_dn_profile_service import hints_for
    docs = [((await st.get_object(f["path"]))[0], f["content_type"]) for f in sorted(sample["files"], key=lambda x: x["page"])]
    parts, n, _ = await asyncio.to_thread(go.pages_from_bytes, docs, cfg)
    cost, orient = 0.0, []
    if cfg["ocr_auto_orient"] and cfg["ocr_orient_model"]:
        parts, orient = await go.auto_orient(parts, cfg["ocr_orient_model"])
        cost += sum(go.cost_usd(o["usage"], cfg["ocr_orient_model"], cfg["ocr_price_table"]) for o in orient)
    hints = await hints_for(sample["entity_id"], sample.get("partner_id") or "", exclude_grn_id=sample.get("source_grn_id") or "")
    model = cfg["ocr_model_primary"]
    r = await extract(parts, n, model=model, reasoning_effort=cfg["ocr_reasoning_effort"], hints=hints["text"],
                      max_output_tokens=int(cfg["ocr_max_output_tokens"]), extract_packing_list=False)
    c = go.cost_usd(r["usage"], model, cfg["ocr_price_table"])
    await db.ai_usage_log.insert_one({"id": new_id("aiu"), "at": now_iso(), "entity_id": sample["entity_id"], "feature": "ocr_dn",
                                      "ref_id": sample["id"], "run_id": run_id, "model": model, "role": "eval", "status": "ok",
                                      "error_code": "", "usage": r["usage"], "cost_usd": c + cost, "latency_ms": r["latency_ms"],
                                      "pages": n, "actor": actor})
    return {"status": "ok", "score": score(sample["answer"], r["data"], cfg["client_po_patterns"]), "cost_usd": round(c + cost, 5),
            "latency_ms": r["latency_ms"], "orientation": [o["rotate_cw"] for o in orient], "hints_corrections": hints["corrections"]}


async def _run(run_id: str, entity_id: str, actor: str) -> None:
    run = await db.ocr_sample_runs.find_one({"id": run_id}, {"_id": 0})
    cfg = await go.ocr_config(entity_id)
    results, total_cost = run["results"], 0.0
    for i, res in enumerate(results):
        sample = await db.ocr_samples.find_one({"id": res["sample_id"]}, {"_id": 0})
        try:
            if not sample:
                raise OcrError("OCR_SAMPLE", "Sampel sudah dihapus.")
            await go._budget_guard(cfg, entity_id)
            out = await _one(sample, cfg, run_id, actor)
        except OcrError as e:
            out = {"status": "failed", "error_code": e.code, "error": e.message}
        except Exception as e:  # noqa: BLE001 — satu sampel gagal tidak menghentikan uji
            logger.exception("uji sampel %s gagal", res["sample_id"])
            out = {"status": "failed", "error_code": "OCR_INTERNAL", "error": f"{type(e).__name__}: {str(e)[:160]}"}
        results[i] = {**res, **out}
        total_cost += out.get("cost_usd", 0.0)
        if sample and out["status"] == "ok":
            ok = sum(sum(v) for v in out["score"]["checks"].values())
            tot = sum(len(v) for v in out["score"]["checks"].values())
            await db.ocr_samples.update_one({"id": sample["id"]}, {"$set": {"last_result": {
                "run_id": run_id, "at": now_iso(), "ok": ok, "total": tot, "pct": round(100 * ok / tot, 1) if tot else None}}})
        await db.ocr_sample_runs.update_one({"id": run_id}, {"$set": {"results": results, "done": i + 1,
                                                                      "cost_usd": round(total_cost, 5)}})
    await db.ocr_sample_runs.update_one({"id": run_id}, {"$set": {"status": "done", "finished_at": now_iso(),
                                                                  "summary": aggregate(results)}})


async def list_runs(entity_id: str) -> List[Dict[str, Any]]:
    return await db.ocr_sample_runs.find({"entity_id": entity_id}, {"_id": 0, "results": 0}).sort("created_at", -1).to_list(30)


async def get_run(run_id: str, entity_id: str) -> Dict[str, Any]:
    doc = await db.ocr_sample_runs.find_one({"id": run_id, "entity_id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Hasil uji tidak ditemukan.")
    if doc["status"] == "running" and not doc.get("summary"):
        doc["summary"] = aggregate(doc["results"])
    return doc
