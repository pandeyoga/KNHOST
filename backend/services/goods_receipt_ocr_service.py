"""GRN Fase 4 — baca surat jalan dengan OpenAI: praproses, panggil, pembaca kedua, log biaya, rem anggaran, pemetaan.

`read_grn`: klaim CAS `draft → reading`; selalu berakhir di `review` (berhasil ATAU `extraction.read_failed`).
"""
import base64
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso
from db import db
from dependencies import audit
from entity_scope import EntityContext
from services import dn_rules as R
from services.config_resolver import value_of
from services.goods_receipt_service import _convert, cas, load, norm_dn, open_pos, require_status
from services.ocr_openai_client import OcrError, extract
from services.ocr_sj_v2 import PROMPT_VERSION

STALE_READING_MIN = 5


async def ocr_config(entity_id: str) -> Dict[str, Any]:
    e, g = {"entity_id": entity_id}, {}
    keys = ["ocr_enabled", "ocr_model_primary", "ocr_model_second", "ocr_second_reader_mode", "ocr_reasoning_effort",
            "ocr_max_output_tokens", "ocr_image_max_side", "ocr_max_pages", "ocr_extract_packing_list",
            "ocr_monthly_budget_usd", "ocr_budget_warn_pct", "ocr_price_table", "client_po_patterns",
            "min_photo_short_side_px"]
    out = {k: await value_of(f"receiving.{k}", e if k in ("ocr_enabled", "ocr_extract_packing_list",
                                                           "client_po_patterns") else g) for k in keys}
    pt = out["ocr_price_table"]
    out["ocr_price_table"] = json.loads(pt) if isinstance(pt, str) and pt.strip() else (pt or {})
    out["client_po_patterns"] = list(out["client_po_patterns"] or R.DEFAULT_PO_PATTERNS)
    return out


def cost_usd(usage: Dict[str, int], model: str, table: Dict[str, Any]) -> float:
    p = table.get(model) or {}
    fresh = max(0, usage.get("input", 0) - usage.get("cached_input", 0))
    return round((fresh * float(p.get("in", 0)) + usage.get("cached_input", 0) * float(p.get("cached_in", 0))
                  + usage.get("output", 0) * float(p.get("out", 0))) / 1_000_000, 6)


def _month_start() -> str:
    n = datetime.now(timezone.utc)
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


async def month_spend() -> float:
    rows = await db.ai_usage_log.aggregate([
        {"$match": {"feature": "ocr_dn", "at": {"$gte": _month_start()}}},
        {"$group": {"_id": None, "c": {"$sum": "$cost_usd"}}}]).to_list(1)
    return float(rows[0]["c"]) if rows else 0.0


async def _log(grn: Dict[str, Any], run_id: str, model: str, role: str, status: str, code: str,
               usage: Dict[str, int], latency: int, cfg: Dict[str, Any], actor: str, pages: int) -> float:
    c = cost_usd(usage, model, cfg["ocr_price_table"])
    await db.ai_usage_log.insert_one({
        "id": new_id("aiu"), "at": now_iso(), "entity_id": grn["entity_id"], "feature": "ocr_dn", "ref_id": grn["id"],
        "run_id": run_id, "model": model, "role": role, "status": status, "error_code": code, "usage": usage,
        "cost_usd": c, "price_version": cfg["ocr_price_table"].get("price_version", ""), "latency_ms": latency,
        "pages": pages, "actor": actor})
    return c


async def _budget_guard(cfg: Dict[str, Any], entity_id: str) -> None:
    spent, budget = await month_spend(), float(cfg["ocr_monthly_budget_usd"] or 0)
    if budget and spent >= budget:
        raise OcrError("OCR_BUDGET", f"Anggaran OCR bulan ini habis (US${spent:.2f} dari US${budget:.2f}). Isi manual.")
    warn = float(cfg["ocr_budget_warn_pct"] or 0)
    ref = f"ocr_budget:{_month_start()[:7]}"
    if budget and warn and spent >= budget * warn / 100 and not await db.notifications.find_one({"ref": ref}):
        from services.notification_service import create_notification
        await create_notification(notif_type="ocr_budget", severity="warning", entity_id=entity_id, recipient_role="admin",
                                  title="Anggaran OCR surat jalan hampir habis",
                                  body=f"Terpakai US${spent:.2f} dari US${budget:.2f} bulan ini.", ref=ref,
                                  link="/?view=goods-receipts")


# ── praproses ─────────────────────────────────────────────────────────────────
def _jpeg_part(img: Any, max_side: int) -> Dict[str, Any]:
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
            "detail": "high"}


async def prepare_pages(grn: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, bool]:
    from services import storage_service as st
    docs = [((await st.get_object(f["path"]))[0], f["content_type"])
            for f in sorted(grn.get("files") or [], key=lambda x: x["page"])]
    return pages_from_bytes(docs, cfg)


def pages_from_bytes(docs: List[Tuple[bytes, str]], cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, bool]:
    """[(bytes, content_type)] → bagian input OpenAI. PDF: lapisan teks ≥ 50 karakter dikirim sebagai teks."""
    from PIL import Image
    parts: List[Dict[str, Any]] = []
    text_used = False
    for data, content_type in docs:
        if content_type == "application/pdf":
            import fitz
            with fitz.open(stream=data, filetype="pdf") as doc:
                for i, page in enumerate(doc, 1):
                    txt = page.get_text() or ""
                    if len(txt.strip()) >= 50:
                        parts.append({"type": "input_text", "text": f"[Halaman {len(parts) + 1} — lapisan teks PDF]\n{txt}"})
                        text_used = True
                    else:
                        pix = page.get_pixmap(dpi=200)
                        parts.append(_jpeg_part(Image.open(io.BytesIO(pix.tobytes("png"))), int(cfg["ocr_image_max_side"])))
        else:
            with Image.open(io.BytesIO(data)) as im:
                parts.append(_jpeg_part(im, int(cfg["ocr_image_max_side"])))
    if len(parts) > int(cfg["ocr_max_pages"] or 5):
        raise OcrError("OCR_PAGES", f"Maksimal {cfg['ocr_max_pages']} halaman per pembacaan.")
    return parts, len(parts), text_used


# ── pemetaan hasil → GRN ─────────────────────────────────────────────────────
def _doubtful(data: Dict[str, Any], lines: List[Dict[str, Any]], totals_bad: List[Any]) -> bool:
    if not (data.get("header") or {}).get("dn_number") or totals_bad:
        return True
    return any(ln["read"].get("legibility") != "clear" or ln["read"].get("handwritten_correction")
               or ln["checks"].get("qty_parse") != "ok" for ln in lines if not ln.get("is_non_stock"))


def _parse_quantities(raw_lines: List[Dict[str, Any]], totals: List[Dict[str, Any]], locale: str) -> None:
    """Isi `value`/`candidates`/`status` per angka; ambiguitas diselesaikan total tercetak per satuan."""
    for ln in raw_lines:
        for q in ln.get("quantities") or []:
            p = R.parse_doc_number(q.get("qty_text"), locale)
            q["value"], q["candidates"], q["status"] = p["value"], p["candidates"], R.qty_status(q, p)
    for t in totals:
        tv = t.get("qty") if t.get("qty") is not None else R.parse_doc_number(t.get("qty_text")).get("value")
        col = [q for ln in raw_lines for q in ln.get("quantities") or []
               if q.get("unit") == t.get("unit") and str(q.get("role", "")).startswith("delivered")]
        if not col or not any(q["status"] in ("ambiguous", "mismatch") for q in col):
            continue
        cands = [q["candidates"] if q["status"] == "ambiguous" else ([q["value"], q["qty"]] if q["status"] == "mismatch"
                 else [q["value"]]) for q in col]
        pick = R.resolve_by_total([[c for c in cs if c is not None] for cs in cands], tv)
        if pick:
            for q, v in zip(col, pick):
                q["value"], q["status"], q["resolved_by"] = v, "ok", "total"


async def _context(grn: Dict[str, Any]) -> Dict[str, Any]:
    pos = await open_pos(grn["entity_id"], grn["partner_id"]) if grn["partner_type"] == "supplier" else []
    full = await db.purchase_orders.find({"id": {"$in": [p["id"] for p in pos]}},
                                         {"_id": 0, "id": 1, "po_number": 1, "legacy_number": 1}).to_list(500)
    tasks = await db.wms_tasks.find({"po_id": {"$in": [p["id"] for p in pos]}, "flow_type": "inbound",
                                     "status": {"$in": ["waiting_goods", "receiving", "qc_check", "put_away"]}},
                                    {"_id": 0}).to_list(500)
    items = await db.supplier_items.find({"supplier_id": grn["partner_id"], "status": "active"},
                                         {"_id": 0, "product_id": 1, "supplier_sku": 1}).to_list(2000)
    prof = await db.supplier_dn_profiles.find_one({"entity_id": grn["entity_id"], "partner_id": grn["partner_id"]},
                                                  {"_id": 0}) or {}
    ent = (await db.entities.find_one({"id": grn["entity_id"]}, {"_id": 0}) or
           await db.business_entities.find_one({"id": grn["entity_id"]}, {"_id": 0}) or {})
    return {"pos": full, "tasks": tasks, "items": items, "profile": prof, "entity": ent}


async def map_extraction(grn: Dict[str, Any], data: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """JSON `sj-v2` → {dn, lines, warnings, totals_bad}. Tidak pernah memilih target bila kandidat > 1."""
    from services.goods_receipt_service import resolve_target
    ctx = await _context(grn)
    prof = ctx["profile"]
    locale = prof.get("number_locale", "unknown") if int(prof.get("confirmed_count") or 0) >= 3 else "unknown"
    h = data.get("header") or {}
    raw_lines = [dict(x) for x in data.get("lines") or []]
    _parse_quantities(raw_lines, data.get("totals") or [], locale)
    totals_bad = R.check_totals(raw_lines, data.get("totals") or [])
    date = h.get("dn_date") or ""
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        date = ""
    dn = {"number": (h.get("dn_number") or "").strip(), "number_norm": norm_dn(h.get("dn_number")), "date": date,
          "date_text": h.get("dn_date_text") or "", "supplier_name_printed": h.get("supplier_name_printed") or "",
          "recipient_name": h.get("recipient_name") or "", "po_refs": h.get("po_refs") or [],
          "other_refs": h.get("other_refs") or [], "vehicle_plate": h.get("vehicle_plate") or "",
          "annotations": data.get("annotations") or [], "source": "ocr", "edited_fields": []}
    warnings: List[str] = list(data.get("warnings") or [])
    if not data.get("is_delivery_document", True) or data.get("doc_kind") in ("packing_list", "lainnya"):
        warnings.append(f"Dokumen terbaca sebagai '{data.get('doc_kind')}', bukan surat jalan — periksa foto.")
    if R.name_mismatch(dn["supplier_name_printed"], [grn["partner_name"], *(prof.get("aliases") or [])]):
        warnings.append(f"Nama pengirim di SJ '{dn['supplier_name_printed']}' berbeda dari mitra {grn['partner_name']}.")
    ent_names = [ctx["entity"].get(k) for k in ("legal_name", "name") if ctx["entity"].get(k)]
    if ent_names and R.name_mismatch(dn["recipient_name"], ent_names, 0.7):
        warnings.append(f"SJ ini ditujukan ke '{dn['recipient_name']}', Anda di entitas {ent_names[0]}.")
    for tb in totals_bad:
        warnings.append(f"Jumlah baris {tb['sum']:g} {tb['unit']} ≠ total tercetak {tb['printed']:g} {tb['unit']}.")
    lines: List[Dict[str, Any]] = []
    head_po = R.match_po([*dn["po_refs"], *[a.get("text") for a in dn["annotations"]]], ctx["pos"], cfg["client_po_patterns"])
    for i, rl in enumerate(raw_lines, 1):
        read = {k: rl.get(k) for k in ("item_code", "description", "color", "design_code", "lot", "grade", "po_ref",
                                       "row_text", "legibility", "handwritten_correction")}
        read.update({"quantities": rl.get("quantities") or [], "source": "ocr"})
        line = {"line_no": i, "page": rl.get("page") or 1, "is_non_stock": bool(rl.get("is_non_stock")), "read": read,
                "target": None, "counted": {"qty": 0, "rolls": 0, "weight_kg": 0, "roll_ids": [], "makloon_rolls": []},
                "recon": None, "posted": {"status": "pending", "at": "", "error": "", "result_ref": ""},
                "checks": {"qty_parse": "ok", "totals_ok": not totals_bad, "second_reader_diff": []},
                "match": {"status": "none", "method": "", "score": 0.0, "candidates": []}}
        if not line["is_non_stock"]:
            pm = R.match_po([rl.get("po_ref")], ctx["pos"], cfg["client_po_patterns"]) if rl.get("po_ref") else head_po
            if pm["status"] == "none" and rl.get("po_ref"):
                pm = head_po
            po_tasks = [t for t in ctx["tasks"] if t.get("po_id") == pm["po_id"]] if pm["po_id"] else []
            m = R.match_line(read, po_tasks, ctx["items"]) if po_tasks else {
                "status": "ambiguous" if pm["candidates"] else "none", "method": f"po_{pm['status']}", "score": 0.0,
                "task_id": "", "candidates": pm["candidates"]}
            line["match"] = {k: m[k] for k in ("status", "method", "score", "candidates")}
            line["match"]["po_match"] = pm["status"]
            if m.get("task_id"):
                class _T:  # noqa: N801 — bentuk minimal GRNTargetIn
                    type, task_id, mko_id, step_seq = "po_task", m["task_id"], "", None
                try:
                    line["target"] = await resolve_target(grn, _T)
                except HTTPException as exc:
                    line["match"]["status"], line["match"]["error"] = "ambiguous", str(exc.detail)
        tunit = (line["target"] or {}).get("unit", "")
        d = R.pick_declared(read["quantities"], tunit)
        import domain_registry as _dr
        grade = (rl.get("grade") or "").strip()
        norm_grade = _dr.normalize_grade(grade) if grade else ""
        if grade and not norm_grade:
            warnings.append(f"Baris {i}: grade '{grade}' tidak dikenal — isi manual.")
        line["declared"] = {"qty": d["qty"], "unit": d["unit"], "rolls": d["rolls"], "weight_kg": d["weight_kg"],
                            "weight_basis": d["weight_basis"], "grade": norm_grade or "", "lot": rl.get("lot") or "",
                            "source": "ocr", "alt_lengths": d["alt_lengths"]}
        line["checks"]["qty_parse"] = d["qty_parse"]
        line["decision"] = "accept" if (line["is_non_stock"] or line["target"]) else "pending"
        await _convert(line)
        lines.append(line)
    return {"dn": dn, "lines": lines, "warnings": warnings, "totals_bad": totals_bad}


def second_reader_diff(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[int, List[Dict[str, Any]]]]:
    """Beda header & per baris (berdasarkan urutan). Tidak ada pemungutan suara otomatis."""
    ha, hb = a.get("header") or {}, b.get("header") or {}
    head = [{"field": f, "primary": ha.get(f), "second": hb.get(f)} for f in ("dn_number", "dn_date", "po_refs")
            if (norm_dn(str(ha.get(f))) if f != "po_refs" else sorted(ha.get(f) or [])) !=
            (norm_dn(str(hb.get(f))) if f != "po_refs" else sorted(hb.get(f) or []))]
    per: Dict[int, List[Dict[str, Any]]] = {}
    la, lb = a.get("lines") or [], b.get("lines") or []
    for i in range(max(len(la), len(lb))):
        x, y = (la[i] if i < len(la) else {}), (lb[i] if i < len(lb) else {})
        diffs = [{"field": f, "primary": x.get(f), "second": y.get(f)} for f in ("description", "po_ref", "lot", "grade")
                 if (x.get(f) or "") != (y.get(f) or "")]
        qa = {q.get("role"): q.get("qty_text") for q in x.get("quantities") or []}
        qb = {q.get("role"): q.get("qty_text") for q in y.get("quantities") or []}
        diffs += [{"field": f"qty:{r}", "primary": qa.get(r), "second": qb.get(r)} for r in set(qa) | set(qb) if qa.get(r) != qb.get(r)]
        if diffs:
            per[i + 1] = diffs
    return head, per


# ── alur baca ────────────────────────────────────────────────────────────────
async def read_grn(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext) -> Dict[str, Any]:
    grn = await load(grn_id, ctx)
    require_status(grn, ["draft"], "Baca otomatis")
    cfg = await ocr_config(grn["entity_id"])
    if not cfg["ocr_enabled"]:
        raise HTTPException(status_code=400, detail="Baca otomatis (OCR) belum aktif untuk badan usaha ini. Isi manual.")
    if not grn.get("files"):
        raise HTTPException(status_code=400, detail="Unggah foto surat jalan dulu.")
    grn = await cas(grn, ["draft"], expected_version, {"status": "reading", "reading_started_at": now_iso()})
    run_id, runs, set_ = new_id("ocr"), [], {}
    pages = 0
    try:
        await _budget_guard(cfg, grn["entity_id"])
        parts, pages, text_used = await prepare_pages(grn, cfg)
        common = {"reasoning_effort": cfg["ocr_reasoning_effort"], "max_output_tokens": int(cfg["ocr_max_output_tokens"]),
                  "extract_packing_list": bool(cfg["ocr_extract_packing_list"])}
        model = cfg["ocr_model_primary"]
        try:
            r1 = await extract(parts, pages, model=model, **common)
        except OcrError as e:
            await _log(grn, run_id, model, "primary", "failed", e.code, e.usage, e.latency_ms, cfg, actor["name"], pages)
            raise
        c1 = await _log(grn, run_id, model, "primary", "ok", "", r1["usage"], r1["latency_ms"], cfg, actor["name"], pages)
        runs.append({"run_id": run_id, "model": model, "role": "primary", "status": "ok", "cost_usd": c1,
                     "latency_ms": r1["latency_ms"], "at": now_iso()})
        mapped = await map_extraction(grn, r1["data"], cfg)
        head_diff: List[Dict[str, Any]] = []
        mode = cfg["ocr_second_reader_mode"]
        if mode == "always" or (mode == "on_doubt" and _doubtful(r1["data"], mapped["lines"], mapped["totals_bad"])):
            m2 = cfg["ocr_model_second"]
            try:
                r2 = await extract(parts, pages, model=m2, **common)
                c2 = await _log(grn, run_id, m2, "second", "ok", "", r2["usage"], r2["latency_ms"], cfg, actor["name"], pages)
                runs.append({"run_id": run_id, "model": m2, "role": "second", "status": "ok", "cost_usd": c2,
                             "latency_ms": r2["latency_ms"], "at": now_iso()})
                head_diff, per = second_reader_diff(r1["data"], r2["data"])
                for ln in mapped["lines"]:
                    ln["checks"]["second_reader_diff"] = per.get(ln["line_no"], [])
            except OcrError as e:
                await _log(grn, run_id, m2, "second", "failed", e.code, e.usage, e.latency_ms, cfg, actor["name"], pages)
                runs.append({"run_id": run_id, "model": m2, "role": "second", "status": "failed", "error_code": e.code,
                             "at": now_iso()})
                mapped["warnings"].append(f"Pembaca kedua gagal ({e.code}) — periksa baris yang ragu secara manual.")
        set_ = {"dn": mapped["dn"], "lines": mapped["lines"],
                "extraction": {"read_failed": False, "error_code": "", "error_message": "", "text_layer_used": text_used,
                               "prompt_version": PROMPT_VERSION, "warnings": mapped["warnings"], "header_diff": head_diff,
                               "doc_kind": r1["data"].get("doc_kind"), "totals": r1["data"].get("totals") or [],
                               "raw": r1["data"], "runs": (grn.get("extraction") or {}).get("runs", []) + runs}}
    except OcrError as e:
        set_ = {"extraction": {**(grn.get("extraction") or {}), "read_failed": True, "error_code": e.code,
                               "error_message": e.message, "prompt_version": PROMPT_VERSION,
                               "runs": (grn.get("extraction") or {}).get("runs", []) + runs + [
                                   {"run_id": run_id, "role": "primary", "status": "failed", "error_code": e.code,
                                    "at": now_iso()}]}}
    doc = await cas(grn, ["reading"], None, {**set_, "status": "review"})
    await audit(actor["name"], "grn_read", "goods_receipt", grn_id,
                {"read_failed": doc["extraction"]["read_failed"], "error_code": doc["extraction"].get("error_code", ""),
                 "pages": pages, "runs": len(runs)}, scope_entity_id=grn["entity_id"])
    return doc


async def sweep_stale(grn: Dict[str, Any]) -> Dict[str, Any]:
    """Penyapu malas: `reading` > 5 menit (proses mati) → `review` + read_failed."""
    started = grn.get("reading_started_at") or grn.get("updated_at") or ""
    if grn.get("status") != "reading" or not started:
        return grn
    if datetime.fromisoformat(started) > datetime.now(timezone.utc) - timedelta(minutes=STALE_READING_MIN):
        return grn
    ext = {**(grn.get("extraction") or {}), "read_failed": True, "error_code": "OCR_TIMEOUT",
           "error_message": "Pembacaan terhenti lebih dari 5 menit. Coba lagi atau isi manual."}
    try:
        return await cas(grn, ["reading"], grn["version"], {"status": "review", "extraction": ext})
    except HTTPException:
        return await db.goods_receipts.find_one({"id": grn["id"]}, {"_id": 0})


async def usage_summary(month: str, ctx: EntityContext) -> Dict[str, Any]:
    month = month or _month_start()[:7]
    ents = ctx.allowed_entity_ids if ctx.view_all else [ctx.active_entity_id]
    rows = await db.ai_usage_log.aggregate([
        {"$match": {"feature": "ocr_dn", "entity_id": {"$in": ents}, "at": {"$regex": f"^{month}"}}},
        {"$group": {"_id": {"model": "$model", "entity_id": "$entity_id"}, "calls": {"$sum": 1},
                    "ok": {"$sum": {"$cond": [{"$eq": ["$status", "ok"]}, 1, 0]}},
                    "input": {"$sum": "$usage.input"}, "cached_input": {"$sum": "$usage.cached_input"},
                    "output": {"$sum": "$usage.output"}, "reasoning": {"$sum": "$usage.reasoning"},
                    "cost_usd": {"$sum": "$cost_usd"}, "pages": {"$sum": "$pages"}}}]).to_list(200)
    cfg = await ocr_config(ctx.active_entity_id or "")
    spent = sum(r["cost_usd"] for r in rows)
    budget = float(cfg["ocr_monthly_budget_usd"] or 0)
    global_spent = await month_spend() if month == _month_start()[:7] else spent
    return {"month": month, "budget_usd": budget, "spent_usd": round(spent, 4),
            "remaining_usd": round(max(0.0, budget - global_spent), 4) if budget else None,
            "rows": [{**r["_id"], **{k: v for k, v in r.items() if k != "_id"},
                      "cost_usd": round(r["cost_usd"], 4),
                      "cost_per_page": round(r["cost_usd"] / r["pages"], 4) if r["pages"] else None} for r in rows]}
