"""PREP-G — daftar tugas per jenis + unduhan "yang diharapkan" per dokumen untuk C72 (pencocokan di perangkat & offline).

Semua daftar disaring ke gudang efektif `HandheldCtx.warehouse_ids` (perangkat ∩ lokasi kerja pengguna) dan PT
dalam penugasan pengguna. Isi "yang diharapkan" diambil dari mesin yang SUDAH ADA (tidak ada logika kembar):
  putaway_in      → item Putaway Order (status tiba per roll)          · `putaway_orders.items`
  transfer_in     → ringkasan penerimaan transfer per roll             · `transfer_receipt_service.summary`
  outbound_so/_sample → sesi Final Loading Check SO × gudang          · `loading_check_service.start` (idempoten)
  cycle_count     → sesi opname RFID per gudang                        · `cycle_count_service.start` (idempoten)
  print_verify    → sesi verifikasi print job                          · `rfid_print_service.start_verify` (idempoten)
  cutting         → tugas potong sampel + roll calon (EPC) untuk identifikasi
  registration    → sesi Daftar Awal: bin cakupan, PT, satuan, EPC baris yang sudah ada

`version` = sidik STRUKTUR dokumen (anggota yang diharapkan + dokumen terbuka/tertutup), bukan progres pindai — perangkat
membandingkannya untuk tahu daftar lokalnya basi. Baris dibagi per halaman (`offset`/`limit`, maks 5000).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core_utils import now_iso, safe_doc
from db import db
from services.handheld_core import KINDS, HandheldCtx, digest, err

DONE_TASK = ["completed", "shipped", "dispatched", "cancelled", "done"]
PA_STATE = {"pending": "pending", "arrived": "done", "exception": "exception", "returned_transit": "returned"}
STATUS_LABEL = {
    "open": "Terbit", "in_transit": "Dalam Perjalanan", "partially_received": "Tiba sebagian", "dispatched": "Dalam Perjalanan",
    "printed": "Tercetak", "verified_with_issues": "Terverifikasi bermasalah", "running": "Berjalan", "created": "Baru",
    "picking": "Pengambilan", "packing": "Pengemasan", "packed": "Sudah Dikemas", "staging": "Siap muat",
    "completed": "Selesai", "completed_with_exception": "Selesai dengan pengecualian", "exception": "Pengecualian",
    "returned": "Kembali ke transit", "verified": "Terverifikasi", "cancelled": "Dibatalkan",
}
PAGE_MAX = 5000
SESSION_KINDS = ("outbound_so", "outbound_sample", "cycle_count", "print_verify")


def label(status: Optional[str]) -> str:
    return STATUS_LABEL.get(status or "", status or "-")


async def epc_map(roll_ids: List[str]) -> Dict[str, str]:
    """roll_id → EPC tag AKTIF yang tertaut (tag pending/retired tidak dihitung)."""
    if not roll_ids:
        return {}
    rolls = await db.inventory_rolls.find({"id": {"$in": roll_ids}, "rfid_tag_id": {"$nin": [None, ""]}},
                                          {"_id": 0, "id": 1, "rfid_tag_id": 1}).to_list(len(roll_ids) + 1)
    tags = {t["id"]: t["epc"] async for t in db.rfid_tags.find(
        {"id": {"$in": [r["rfid_tag_id"] for r in rolls]}, "status": "active"}, {"_id": 0, "id": 1, "epc": 1})}
    return {r["id"]: tags[r["rfid_tag_id"]] for r in rolls if r["rfid_tag_id"] in tags}


def split_doc(doc_id: str) -> Tuple[str, str]:
    """Dokumen cek muat = SO × gudang: `<order_id>~<warehouse_id>`."""
    if "~" not in (doc_id or ""):
        raise err(400, "DOC_ID_INVALID", "ID dokumen cek muat harus berbentuk <order_id>~<warehouse_id>.")
    a, b = doc_id.split("~", 1)
    return a, b


def _task(kind: str, doc_id: str, number: str, title: str, warehouse_id: str, status: str, ctx: HandheldCtx,
          expected: int = 0, done: int = 0, **extra: Any) -> Dict[str, Any]:
    return {"kind": kind, "kind_label": KINDS[kind]["label"], "doc_id": doc_id, "number": number or doc_id, "title": title,
            "warehouse_id": warehouse_id, "warehouse_name": ctx.wh_name(warehouse_id), "status": status,
            "status_label": label(status), "expected_count": expected, "done_count": done,
            "offline_allowed": kind != "cutting", **extra}


# ─── Daftar tugas ─────────────────────────────────────────────────────────────
async def list_tasks(ctx: HandheldCtx, kind: str, q: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 300))
    fn = {"putaway_in": _list_pa, "transfer_in": _list_transfer, "outbound_so": _list_outbound,
          "outbound_sample": _list_outbound, "cycle_count": _list_cycle, "print_verify": _list_print,
          "cutting": _list_cutting, "registration": _list_registration}[kind]
    rows = await fn(ctx, kind, limit)
    term = (q or "").strip().lower()
    if term:
        rows = [r for r in rows if term in " ".join(str(r.get(k) or "") for k in ("number", "title", "subtitle", "warehouse_name")).lower()]
    return rows[:limit]


async def _list_pa(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    from services.putaway_order_service import ARRIVAL_STATUSES
    rows = await db.putaway_orders.find(
        {"status": {"$in": list(ARRIVAL_STATUSES)}, "to_warehouse_id": {"$in": ctx.warehouse_ids},
         "owner_entity_id": {"$in": ctx.entity_ids}}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    out = []
    for o in rows:
        items = o.get("items") or []
        out.append(_task(kind, o["id"], o.get("pa_number"), f"Dari {o.get('from_warehouse_name') or o.get('from_warehouse_id')}",
                         o.get("to_warehouse_id"), o.get("status"), ctx, len(items),
                         sum(1 for i in items if i.get("status") == "arrived"),
                         subtitle=f"{sum(1 for i in items if i.get('status') == 'pending')} roll menunggu"))
    return out


async def _list_transfer(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    ents = ctx.entity_ids
    rows = await db.warehouse_transfers.find(
        {"status": {"$in": ["dispatched", "partially_received"]}, "dest_warehouse_id": {"$in": ctx.warehouse_ids},
         "transfer_kind": {"$ne": "inter_entity"},
         "$or": [{"entity_id": {"$in": ents}}, {"source_entity_id": {"$in": ents}}, {"dest_entity_id": {"$in": ents}}]},
        {"_id": 0}).sort("created_at", -1).to_list(limit)
    out = []
    for t in rows:
        n = sum(len(it.get("rolls") or []) for it in t.get("items") or [])
        out.append(_task(kind, t["id"], t.get("transfer_number") or t.get("number"),
                         f"Dari {t.get('source_warehouse_name') or t.get('source_warehouse_id')}", t.get("dest_warehouse_id"),
                         t.get("status"), ctx, n, 0, subtitle=f"{n} roll"))
    return out


async def _list_outbound(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    from services.loading_check_service import EXPECTED_STATUSES
    q: Dict[str, Any] = {"flow_type": "outbound", "warehouse_id": {"$in": ctx.warehouse_ids},
                         "entity_id": {"$in": ctx.entity_ids}, "status": {"$nin": DONE_TASK + ["scheduled"]}}
    if kind == "outbound_sample":
        q.update({"task_subtype": "sample_cut", "picked_qty": {"$gt": 0}})
    else:
        q["task_subtype"] = {"$ne": "sample_cut"}
        q["order_type"] = {"$ne": "sample"}
    groups: Dict[str, Dict[str, Any]] = {}
    async for t in db.wms_tasks.find(q, {"_id": 0, "order_id": 1, "order_number": 1, "warehouse_id": 1, "status": 1,
                                         "customer_name": 1, "product_name": 1}).sort("created_at", -1).limit(limit * 6):
        if not t.get("order_id"):
            continue
        g = groups.setdefault(f"{t['order_id']}~{t['warehouse_id']}", {"t": t, "statuses": set(), "lines": 0})
        g["statuses"].add(t.get("status"))
        g["lines"] += 1
    out = []
    for doc_id, g in list(groups.items())[:limit]:
        t = g["t"]
        expected = await db.inventory_rolls.count_documents(
            {"reserved_ref.type": "sales_order", "reserved_ref.id": t["order_id"], "warehouse_id": t["warehouse_id"],
             "status": {"$in": EXPECTED_STATUSES}, "length_remaining": {"$gt": 0}})
        st = sorted(g["statuses"] - {None})
        out.append(_task(kind, doc_id, t.get("order_number"), t.get("customer_name") or t.get("product_name") or "",
                         t["warehouse_id"], st[0] if len(st) == 1 else "picking", ctx, expected, 0,
                         subtitle=f"{g['lines']} baris · {expected} roll dialokasikan", order_id=t["order_id"]))
    return out


async def _list_cycle(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    from services.roll_service import PHYSICAL_ROLL_STATUSES
    out = []
    for w in ctx.warehouses[:limit]:
        ents = await cycle_entities(ctx, w["id"])
        if not ents:
            continue
        tagged = await db.inventory_rolls.count_documents(
            {"warehouse_id": w["id"], "owner_entity_id": {"$in": ents}, "status": {"$in": PHYSICAL_ROLL_STATUSES},
             "length_remaining": {"$gt": 0}, "rfid_tag_id": {"$nin": [None, ""]}})
        sess = await db.rfid_verify_sessions.find_one({"kind": "cycle_count", "warehouse_id": w["id"], "status": "open",
                                                       "scope_entity_ids": ents}, {"_id": 0, "id": 1, "created_at": 1})
        out.append(_task(kind, w["id"], w.get("code") or w["id"], f"Opname RFID · {w.get('name')}", w["id"],
                         "running" if sess else "open", ctx, tagged, 0,
                         subtitle=("Sesi berjalan" if sess else "Belum ada sesi") + f" · {tagged} roll bertag",
                         session_id=(sess or {}).get("id")))
    return out


async def _list_print(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    rows = await db.rfid_print_jobs.find(
        {"status": {"$in": ["printed", "verified_with_issues"]}, "kind": {"$ne": "qr_label"},
         "warehouse_id": {"$in": ctx.warehouse_ids}, "owner_entity_id": {"$in": ctx.entity_ids}},
        {"_id": 0, "items.zpl": 0}).sort("created_at", -1).to_list(limit)
    return [_task(kind, j["id"], j.get("job_number"), j.get("source") or "Label RFID", j.get("warehouse_id"), j.get("status"),
                  ctx, len(j.get("items") or []), 0, subtitle=f"{len(j.get('items') or [])} label") for j in rows]


async def _list_cutting(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    rows = await db.wms_tasks.find(
        {"task_subtype": "sample_cut", "status": {"$in": ["created", "picking"]}, "warehouse_id": {"$in": ctx.warehouse_ids},
         "entity_id": {"$in": ctx.entity_ids}, "$or": [{"picked_qty": {"$in": [0, None]}}, {"picked_qty": {"$exists": False}}]},
        {"_id": 0}).sort("created_at", 1).to_list(limit)
    return [_task(kind, t["id"], t.get("order_number"), f"{t.get('product_name')} · {t.get('quantity')} {t.get('unit')}",
                  t.get("warehouse_id"), t.get("status"), ctx, 1, 0, subtitle=t.get("customer_name") or "",
                  suggested_roll_no=t.get("suggested_roll_no")) for t in rows]


async def _list_registration(ctx: HandheldCtx, kind: str, limit: int) -> List[Dict[str, Any]]:
    rows = await db.cycle_count_sessions.find(
        {"mode": "registration", "status": "running", "warehouse_id": {"$in": ctx.warehouse_ids},
         "entity_id": {"$in": ctx.entity_ids + [None, ""]}},
        {"_id": 0, "id": 1, "number": 1, "name": 1, "warehouse_id": 1, "status": 1, "registration.epc_mode": 1}
    ).sort("created_at", -1).to_list(limit)
    out = []
    for s in rows:
        n = await db.initial_registration_lines.count_documents({"session_id": s["id"], "status": {"$in": ["draft", "applied"]}})
        mode = (s.get("registration") or {}).get("epc_mode")
        out.append(_task(kind, s["id"], s.get("number"), s.get("name") or "Daftar Awal", s["warehouse_id"], "running", ctx, 0, n,
                         subtitle=f"{n} roll terdaftar · EPC {'dibuat sistem' if mode == 'system' else 'bawaan tag'}",
                         epc_mode=mode))
    return out


# ─── Yang diharapkan per dokumen ──────────────────────────────────────────────
def _structure_version(kind: str, doc_id: str, closed: bool, rows: List[Dict[str, Any]], extra: Any = None) -> str:
    keys = sorted((r.get("roll_id") or "", r.get("epc") or "", r.get("state") if r.get("state") not in ("pending", "done") else "")
                  for r in rows)
    return digest([kind, doc_id, closed, keys, extra])[:20]


def _page(rows: List[Dict[str, Any]], offset: int, limit: int) -> List[Dict[str, Any]]:
    off = max(0, int(offset or 0))
    return rows[off:off + max(1, min(int(limit or PAGE_MAX), PAGE_MAX))]


async def expected(ctx: HandheldCtx, kind: str, doc_id: str, offset: int = 0, limit: int = PAGE_MAX,
                   start: bool = False) -> Dict[str, Any]:
    """`start=True` (sesi cek muat/opname/verifikasi) = mulai sesi bila belum ada — aksi eksplisit operator."""
    if kind in SESSION_KINDS:
        snap = await _exp_session(ctx, kind, doc_id, start)
    else:
        fn = {"putaway_in": _exp_pa, "transfer_in": _exp_transfer, "cutting": _exp_cutting,
              "registration": _exp_registration}[kind]
        snap = await fn(ctx, kind, doc_id)
    rows = snap.pop("rows")
    closed = bool(snap.get("closed"))
    snap.setdefault("untagged", [])
    counts = {"expected": len(rows), "done": sum(1 for r in rows if r.get("state") == "done"),
              "pending": sum(1 for r in rows if r.get("state") == "pending"), "untagged": len(snap["untagged"])}
    qty: Dict[str, float] = {}
    for r in rows:
        if r.get("unit") and isinstance(r.get("qty"), (int, float)):
            qty[r["unit"]] = round(qty.get(r["unit"], 0.0) + float(r["qty"]), 4)
    return {"kind": kind, "kind_label": KINDS[kind]["label"], "doc_id": doc_id, "server_time": now_iso(), "snapshot_at": now_iso(),
            "version": _structure_version(kind, doc_id, closed, rows, snap.get("version_extra")),
            "total_rows": len(rows), "offset": max(0, int(offset or 0)), "rows": _page(rows, offset, limit),
            "counts": counts, "qty_by_unit": qty, "complete_supported": KINDS[kind]["complete"],
            "offline_allowed": kind != "cutting" and not closed, **{k: v for k, v in snap.items() if k != "version_extra"}}


def _row(roll_id: str, roll_no: str, epc: str, state: str, **kw: Any) -> Dict[str, Any]:
    return {"roll_id": roll_id, "roll_no": roll_no or "", "epc": epc or "", "state": state, **kw}


async def _exp_pa(ctx: HandheldCtx, kind: str, doc_id: str) -> Dict[str, Any]:
    from services.putaway_order_service import ARRIVAL_STATUSES
    o = await db.putaway_orders.find_one({"id": doc_id}, {"_id": 0})
    if not o or o.get("owner_entity_id") not in ctx.entity_ids:
        raise err(404, "DOC_NOT_FOUND", "Putaway Order tidak ditemukan.")
    ctx.assert_warehouse(o.get("to_warehouse_id"), "gudang tujuan PA ini")
    rows = [_row(i["roll_id"], i.get("roll_no"), (i.get("epc") or "").upper(), PA_STATE.get(i.get("status"), i.get("status")),
                 sku=i.get("sku"), product_name=i.get("product_name"), qty=i.get("qty"), unit=i.get("unit"), lot=i.get("lot"),
                 grade=i.get("grade")) for i in o.get("items") or []]
    return {"rows": rows, "number": o.get("pa_number"), "title": f"Putaway {o.get('pa_number')}", "status": o.get("status"),
            "status_label": label(o.get("status")), "warehouse_id": o.get("to_warehouse_id"),
            "closed": o.get("status") not in ARRIVAL_STATUSES, "labels_allowed": True}


async def _transfer_doc(ctx: HandheldCtx, doc_id: str) -> Dict[str, Any]:
    t = await db.warehouse_transfers.find_one({"id": doc_id}, {"_id": 0})
    ents = {t.get("entity_id"), t.get("source_entity_id"), t.get("dest_entity_id")} - {None} if t else set()
    if not t or not (ents & set(ctx.entity_ids)):
        raise err(404, "DOC_NOT_FOUND", "Transfer tidak ditemukan.")
    if t.get("transfer_kind") == "inter_entity":
        raise err(400, "DOC_KIND_UNSUPPORTED", "Transfer antar badan usaha tidak memindah fisik — tidak ada penerimaan.")
    ctx.assert_warehouse(t.get("dest_warehouse_id"), "gudang tujuan transfer ini")
    return t


async def _exp_transfer(ctx: HandheldCtx, kind: str, doc_id: str) -> Dict[str, Any]:
    from services import transfer_receipt_service as trs
    t = await _transfer_doc(ctx, doc_id)
    summ = await trs.summary(t)
    epcs = await epc_map([r["roll_id"] for r in summ["rolls"]])
    state = {"in_transit": "pending", "received": "done", "received_damaged": "done", "received_hold": "done"}
    rows = [_row(r["roll_id"], r.get("roll_no"), epcs.get(r["roll_id"], ""), state.get(r["state"], r["state"]),
                 sku=r.get("sku"), product_name=r.get("product_name"), qty=r.get("length"), unit=r.get("unit"), lot=r.get("lot"))
            for r in summ["rolls"]]
    untagged = [{"roll_id": r["roll_id"], "roll_no": r["roll_no"], "reason": "tanpa tag aktif — pindai label"}
                for r in rows if not r["epc"] and r["state"] == "pending"]
    return {"rows": rows, "untagged": untagged, "number": t.get("transfer_number") or t.get("number") or doc_id,
            "title": f"Transfer dari {t.get('source_warehouse_name') or t.get('source_warehouse_id')}", "status": t.get("status"),
            "status_label": label(t.get("status")), "warehouse_id": t.get("dest_warehouse_id"),
            "closed": t.get("status") not in ("dispatched", "partially_received"), "labels_allowed": True,
            "bins": [b for b in summ.get("dest_bins") or []][:300]}


OPEN_SESSION_FIELDS = {"_id": 0, "scan_log": 0}


async def cycle_entities(ctx: HandheldCtx, warehouse_id: str) -> List[str]:
    """PT pengguna yang BOLEH memakai gudang ini (E4.1: gudang khusus PT lain = menghitung barang orang)."""
    from services.warehouse_scope_service import is_usable
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0}) or {}
    return sorted(e for e in set(ctx.entity_ids) if is_usable(wh, e))


async def find_session(ctx: HandheldCtx, kind: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """Sesi TERBUKA dokumen ini (tanpa membuat). `None` = belum ada / sudah selesai."""
    if kind in ("outbound_so", "outbound_sample"):
        order_id, wid = split_doc(doc_id)
        q: Dict[str, Any] = {"kind": "loading_check", "order_id": order_id, "status": "open", "warehouse_id": {"$in": [wid, None]}}
    elif kind == "cycle_count":
        q = {"kind": "cycle_count", "warehouse_id": doc_id, "status": "open", "scope_entity_ids": await cycle_entities(ctx, doc_id)}
    elif kind == "print_verify":
        q = {"print_job_id": doc_id, "status": "open"}
    else:
        return None
    return await db.rfid_verify_sessions.find_one(q, OPEN_SESSION_FIELDS)


async def start_session(ctx: HandheldCtx, kind: str, doc_id: str) -> Dict[str, Any]:
    """Buat/ambil sesi lewat layanan asal (idempoten: sesi terbuka yang ada dikembalikan)."""
    if kind in ("outbound_so", "outbound_sample"):
        from services import loading_check_service as lc
        order_id, wid = split_doc(doc_id)
        ctx.assert_warehouse(wid, "gudang pengiriman ini")
        return await lc.start(order_id, ctx.entity_ids, ctx.actor_name, wid)
    if kind == "cycle_count":
        from services import cycle_count_service as cc
        from services import warehouse_scope_service as whscope
        ctx.assert_warehouse(doc_id, "gudang ini")
        ents = await cycle_entities(ctx, doc_id)
        if not ents:   # pesan penolakan asal (gudang khusus PT lain)
            await whscope.assert_usable(doc_id, ctx.entity_ids[0] if ctx.entity_ids else None,
                                        action="melakukan stock opname RFID di sini")
        return await cc.start(doc_id, ents, ctx.actor_name)
    from services import rfid_print_service as rps
    job = await rps.get_print_job(doc_id, ctx.entity_ids)
    ctx.assert_warehouse(job.get("warehouse_id"), "print job ini")
    return await rps.start_verify(doc_id, ctx.entity_ids, ctx.actor_name)


async def doc_guard(ctx: HandheldCtx, kind: str, doc_id: str) -> Dict[str, Any]:
    """Penjaga dokumen sesi tanpa efek samping: judul, gudang, hasil terakhir."""
    if kind in ("outbound_so", "outbound_sample"):
        order_id, wid = split_doc(doc_id)
        ctx.assert_warehouse(wid, "gudang pengiriman ini")
        so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "entity_id": 1, "number": 1, "loading_checks": 1})
        if not so or (so.get("entity_id") and so["entity_id"] not in ctx.entity_ids):
            raise err(404, "DOC_NOT_FOUND", "SO tidak ditemukan.")
        last = (so.get("loading_checks") or {}).get(wid) or {}
        return {"number": so.get("number"), "title": f"Cek muat {so.get('number')}", "warehouse_id": wid,
                "last_result": {k: last.get(k) for k in ("result", "matched", "expected", "checked_at")} if last else None}
    if kind == "cycle_count":
        ctx.assert_warehouse(doc_id, "gudang ini")
        return {"number": ctx.wh_name(doc_id), "title": f"Opname RFID {ctx.wh_name(doc_id)}", "warehouse_id": doc_id}
    job = await db.rfid_print_jobs.find_one({"id": doc_id}, {"_id": 0, "items.zpl": 0})
    if not job or job.get("owner_entity_id") not in ctx.entity_ids:
        raise err(404, "DOC_NOT_FOUND", "Print job tidak ditemukan.")
    ctx.assert_warehouse(job.get("warehouse_id"), "print job ini")
    return {"number": job.get("job_number"), "title": f"Verifikasi {job.get('job_number')}",
            "warehouse_id": job.get("warehouse_id"), "job_status": job.get("status")}


def _session_rows(sess: Dict[str, Any]) -> List[Dict[str, Any]]:
    scanned = set(sess.get("scanned_epcs") or [])
    return [_row(e["roll_id"], e.get("roll_no"), e["epc"], "done" if e["epc"] in scanned else "pending", sku=e.get("sku"),
                 product_name=e.get("product_name")) for e in sess.get("expected") or []]


async def _exp_session(ctx: HandheldCtx, kind: str, doc_id: str, start: bool = False) -> Dict[str, Any]:
    head = await doc_guard(ctx, kind, doc_id)
    sess = await find_session(ctx, kind, doc_id)
    if not sess and start:
        sess = await start_session(ctx, kind, doc_id)
    if not sess:
        return {"rows": [], **head, "status": "not_started", "status_label": "Sesi belum dimulai", "session_id": None,
                "needs_start": True, "closed": False, "labels_allowed": False, "version_extra": None}
    resolved = set(sess.get("untagged_resolved") or [])
    untagged = [{**u, "resolved": u.get("roll_id") in resolved} for u in sess.get("untagged") or []]
    return {"rows": _session_rows(sess), **head, "status": sess.get("status"),
            "status_label": "Sesi terbuka" if sess.get("status") == "open" else label(sess.get("status")),
            "session_id": sess["id"], "needs_start": False, "closed": sess.get("status") != "open", "untagged": untagged,
            "untagged_total": sess.get("untagged_count", len(untagged)),
            "labels_allowed": kind in ("outbound_so", "outbound_sample"),
            "not_committed_count": sess.get("not_committed_count", 0), "version_extra": sess["id"]}


async def cutting_task(ctx: HandheldCtx, task_id: str) -> Dict[str, Any]:
    t = await db.wms_tasks.find_one({"id": task_id, "task_subtype": "sample_cut"}, {"_id": 0})
    if not t or t.get("entity_id") not in ctx.entity_ids:
        raise err(404, "DOC_NOT_FOUND", "Tugas potong sampel tidak ditemukan.")
    ctx.assert_warehouse(t.get("warehouse_id"), "tugas potong ini")
    return t


async def _exp_cutting(ctx: HandheldCtx, kind: str, doc_id: str) -> Dict[str, Any]:
    t = await cutting_task(ctx, doc_id)
    need = float(t.get("quantity") or 0)
    cands = await db.inventory_rolls.find(
        {"product_id": t["product_id"], "warehouse_id": t["warehouse_id"], "status": "available", "active_movement": None,
         "length_remaining": {"$gte": need - 0.001}}, {"_id": 0, "id": 1, "roll_no": 1, "length_remaining": 1, "unit": 1, "lot": 1,
                                                       "bin_code": 1}).sort("created_at", 1).to_list(200)
    epcs = await epc_map([c["id"] for c in cands])
    rows = [_row(c["id"], c.get("roll_no"), epcs.get(c["id"], ""), "pending", qty=c.get("length_remaining"), unit=c.get("unit"),
                 lot=c.get("lot"), bin_code=c.get("bin_code"), suggested=c["id"] == t.get("suggested_roll_id"),
                 sku=t.get("sku"), product_name=t.get("product_name")) for c in cands]
    rows.sort(key=lambda r: not r["suggested"])
    cut = t.get("status") not in ("created", "picking") or float(t.get("picked_qty") or 0) > 0
    return {"rows": rows, "number": t.get("order_number"), "title": f"Potong {t.get('product_name')}", "status": t.get("status"),
            "status_label": label(t.get("status")), "warehouse_id": t.get("warehouse_id"), "closed": cut, "labels_allowed": True,
            "task": {k: t.get(k) for k in ("id", "order_id", "order_number", "customer_name", "product_id", "product_name", "sku",
                                           "quantity", "unit", "suggested_roll_id", "suggested_roll_no", "status")},
            "version_extra": t.get("suggested_roll_id")}


async def registration_session(ctx: HandheldCtx, sid: str) -> Dict[str, Any]:
    s = safe_doc(await db.cycle_count_sessions.find_one({"id": sid, "mode": "registration"}, {"_id": 0}))
    if not s or (s.get("entity_id") and s["entity_id"] not in ctx.entity_ids):
        raise err(404, "DOC_NOT_FOUND", "Sesi Daftar Awal tidak ditemukan.")
    ctx.assert_warehouse(s.get("warehouse_id"), "sesi Daftar Awal ini")
    return s


async def _exp_registration(ctx: HandheldCtx, kind: str, doc_id: str) -> Dict[str, Any]:
    from services.location_service import flatten_bins
    s = await registration_session(ctx, doc_id)
    reg = s.get("registration") or {}
    wh = await db.warehouses.find_one({"id": s["warehouse_id"]}, {"_id": 0}) or {}
    keep = set(reg.get("bin_ids") or [])
    bins = [{"id": b["bin_id"], "code": b.get("code", ""), "rack_id": b.get("rack_id") or "-", "rack": b.get("rack", ""),
             "zone": b.get("zone", ""), "path": b.get("path", "")} for b in flatten_bins(wh) if b["bin_id"] in keep]
    lines = await db.initial_registration_lines.find({"session_id": doc_id, "status": {"$in": ["draft", "applied"]}},
                                                     {"_id": 0, "id": 1, "epc": 1, "bin_code": 1, "sku": 1, "tag_state": 1,
                                                      "matched_roll_id": 1}).to_list(20000)
    rows = [_row(ln.get("matched_roll_id") or "", "", ln["epc"], "done", line_id=ln["id"], bin_code=ln.get("bin_code"),
                 sku=ln.get("sku"), tag_state=ln.get("tag_state")) for ln in lines]
    owners = [{"id": e["id"], "name": e.get("name") or e.get("short_name") or e["id"]} async for e in db.entities.find(
        {"id": {"$in": ctx.entity_ids}}, {"_id": 0, "id": 1, "name": 1, "short_name": 1})] or [{"id": e, "name": e} for e in ctx.entity_ids]
    units = [u.get("aliases", [u.get("code", "").lower()])[0] async for u in db.uoms.find(
        {"status": {"$ne": "inactive"}, "base_type": {"$in": ["length", "weight"]}}, {"_id": 0, "aliases": 1, "code": 1})]
    return {"rows": rows, "number": s.get("number"), "title": s.get("name") or "Daftar Awal", "status": s.get("status"),
            "status_label": label(s.get("status")), "warehouse_id": s["warehouse_id"], "closed": s.get("status") != "running",
            "labels_allowed": False,
            "registration": {"epc_mode": reg.get("epc_mode"), "freeze_mode": reg.get("freeze_mode"), "bins": bins,
                             "owners": owners, "default_owner": s.get("entity_id") or (ctx.entity_ids[0] if ctx.entity_ids else ""),
                             "units": units or ["meter", "yard", "kg"], "grades": ["A", "B", "BS", "C"],
                             "racks_done": sorted((reg.get("rack_marks") or {}).keys())}}


async def catalog(ctx: HandheldCtx, q: str = "", limit: int = 3000) -> Dict[str, Any]:
    """Daftar produk aktif bersatuan dasar untuk form Daftar Awal (cache offline perangkat). Produk tergantikan disertakan
    dengan penunjuk penggantinya — server tetap mengikuti rantai `superseded_by` saat baris disimpan."""
    query: Dict[str, Any] = {"base_unit": {"$nin": [None, ""]}, "status": {"$nin": ["inactive", "archived", "deleted"]}}
    if q.strip():
        import re
        rx = re.escape(q.strip())
        query["$or"] = [{"sku": {"$regex": rx, "$options": "i"}}, {"name": {"$regex": rx, "$options": "i"}}]
    rows = await db.products.find(query, {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1, "category": 1,
                                          "superseded_by": 1}).sort("sku", 1).to_list(max(1, min(int(limit or 3000), 5000)))
    return {"server_time": now_iso(), "count": len(rows), "version": digest([(p["id"], p.get("sku"), p.get("base_unit")) for p in rows])[:16],
            "products": [{k: p.get(k) for k in ("id", "sku", "name", "base_unit", "category")} | (
                {"superseded_by": str(p["superseded_by"])} if p.get("superseded_by") else {}) for p in rows]}
