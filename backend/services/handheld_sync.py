"""PREP-G — kiriman batch C72 (idempoten) + penyelesaian dokumen + potong sampel.

Satu batch = hasil SATU pindai massal untuk SATU dokumen ("buka dokumen → baca massal → yang diharapkan vs terbaca →
konfirmasi sekali"), ditangkap online atau offline lalu disinkron. Aturan:
  * Idempoten per perangkat: `_id = <device_id>:batch:<client_batch_id>`. Kirim ulang badan yang SAMA → hasil tersimpan
    (`replay: true`); badan berbeda dengan ID sama → 409 IDEMPOTENCY_CONFLICT. Batch "processing" basi (> 60 dtk,
    proses mati di tengah) diproses ulang — layanan di bawahnya idempoten/CAS (trip PA ber-`client_trip_id`, sesi
    `$addToSet`, terima transfer "sudah diterima", baris Daftar Awal ber-EPC unik).
  * Server memvalidasi ULANG: status dokumen & roll sekarang (bukan cache perangkat). Penolakan bisnis yang pasti
    (dokumen sudah ditutup, roll berubah) disimpan sebagai hasil final `status: conflict` + rincian per item — HTTP 200,
    perangkat berhenti mengirim ulang & menampilkan konflik. Galat sementara (kunci saga, 5xx) TIDAK disimpan → retry.
  * Cap waktu perangkat (`device_time`, `captured_from/to`, per bacaan `first_seen/last_seen`) disimpan apa adanya +
    selisih jam server (`clock_skew_ms`). Waktu server tetap dipakai untuk efek bisnis.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import now_iso, safe_doc
from db import db
from dependencies import audit, has_permission
from services import handheld_tasks as tasks
from services.handheld_core import KINDS, HandheldCtx, assert_operator, digest, err, parse_ts

REQ = "handheld_requests"
STALE_S = 60
SCAN_CHUNK = 500          # normalize_reads (sesi verifikasi) memotong di 500 per panggilan
TRANSIENT = {"SAGA_IN_PROGRESS", "REQUEST_IN_PROGRESS"}


_IDX = {"ok": False}


async def _ensure_indexes() -> None:
    """Indeks jejak perangkat (daftar/aktivitas per perangkat, sesi operator terbuka)."""
    if _IDX["ok"]:
        return
    from services.handheld_core import OPS
    await db[REQ].create_index([("device_id", 1), ("created_at", -1)], name="hh_req_device")
    await db[OPS].create_index([("device_id", 1), ("ended_at", 1)], name="hh_ops_device")
    _IDX["ok"] = True


def _detail(exc: HTTPException) -> Dict[str, Any]:
    d = exc.detail
    if isinstance(d, dict):
        return {"code": d.get("code") or f"HTTP_{exc.status_code}", "message": d.get("message") or str(d)}
    return {"code": f"HTTP_{exc.status_code}", "message": str(d)}


async def once(ctx: HandheldCtx, scope: str, key: str, body: Any, fn: Callable[[], Awaitable[Dict[str, Any]]],
               meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Jalankan `fn` sekali per (perangkat, scope, key). Hasil final (termasuk penolakan bisnis) disimpan & diputar ulang."""
    key = (key or "").strip()
    if len(key) < 8 or len(key) > 80:
        raise err(400, "IDEMPOTENCY_KEY_REQUIRED", "ID permintaan klien wajib (8–80 karakter, stabil saat kirim ulang).")
    await _ensure_indexes()
    _id, dig = f"{ctx.device['id']}:{scope}:{key}", digest(body)
    for _ in range(2):
        cur = await db[REQ].find_one({"_id": _id})
        if cur:
            if cur.get("digest") != dig:
                raise err(409, "IDEMPOTENCY_CONFLICT", "ID permintaan ini sudah dipakai dengan isi berbeda — jangan ganti isi saat kirim ulang.")
            if cur.get("status") == "done":
                return {**cur["result"], "replay": True}
            age = time.time() - float(cur.get("started_ts") or 0)
            if age < STALE_S:
                raise err(409, "REQUEST_IN_PROGRESS", "Permintaan yang sama sedang diproses — coba lagi sebentar.", retryable=True)
            await db[REQ].update_one({"_id": _id}, {"$set": {"started_ts": time.time(), "retried_at": now_iso()}})
            break
        try:
            await db[REQ].insert_one({"_id": _id, "scope": scope, "key": key, "digest": dig, "status": "processing",
                                      "device_id": ctx.device["id"], "user_id": ctx.user["id"], "user_name": ctx.actor_name,
                                      "started_ts": time.time(), "created_at": now_iso(), **(meta or {})})
            break
        except DuplicateKeyError:
            continue
    t0 = time.monotonic()
    try:
        result = await fn()
    except HTTPException as exc:
        d = _detail(exc)
        if exc.status_code >= 500 or d["code"] in TRANSIENT or exc.status_code in (401, 429):
            await db[REQ].delete_one({"_id": _id, "status": "processing"})
            raise
        result = {"status": "conflict" if exc.status_code == 409 else "rejected", "error": {**d, "http_status": exc.status_code},
                  "items": [], "summary": {}}
    except BaseException:
        await db[REQ].delete_one({"_id": _id, "status": "processing"})
        raise
    result = {**result, "client_request_id": key, "server_time": now_iso()}
    await db[REQ].update_one({"_id": _id}, {"$set": {"status": "done", "result": result, "done_at": now_iso(),
                                                     "result_status": result.get("status"),
                                                     "processing_ms": int((time.monotonic() - t0) * 1000)}})
    return {**result, "replay": False}


# ─── Batch pindai ─────────────────────────────────────────────────────────────
def _canon(raw: str) -> str:
    from services.epc import try_canonical
    s = str(raw or "").strip()
    return try_canonical(s) or s.upper()


def _clock(body: Dict[str, Any]) -> Dict[str, Any]:
    dev = parse_ts(body.get("device_time"))
    skew = int((datetime.now(timezone.utc) - dev).total_seconds() * 1000) if dev else None
    return {"device_time": body.get("device_time"), "clock_skew_ms": skew, "clock_offset_ms": body.get("clock_offset_ms"),
            "clock_synced": body.get("clock_synced"), "captured_from": body.get("captured_from"),
            "captured_to": body.get("captured_to")}


async def submit_batch(ctx: HandheldCtx, body: Dict[str, Any]) -> Dict[str, Any]:
    kind = body.get("kind")
    if kind not in KINDS or kind == "cutting":
        raise err(400, "KIND_UNSUPPORTED", f"Jenis '{kind}' tidak menerima batch pindai.")
    await assert_operator(ctx, body.get("operator_session_id"), body.get("user_id"))
    reads = list(dict.fromkeys(_canon(r.get("epc")) for r in body.get("reads") or [] if str(r.get("epc") or "").strip()))
    labels = list(dict.fromkeys(str(x).strip().upper() for x in body.get("labels") or [] if str(x or "").strip()))
    meta = {"type": "batch", "kind": kind, "doc_id": body.get("doc_id"), "session_id": body.get("session_id"),
            "operator_session_id": body.get("operator_session_id"), "reads_count": len(reads), "labels_count": len(labels),
            "lines_count": len(body.get("lines") or []), **_clock(body),
            "reads": [{k: r.get(k) for k in ("epc", "rssi", "count", "first_seen", "last_seen")} for r in (body.get("reads") or [])[:2000]]}

    async def run() -> Dict[str, Any]:
        if body.get("simulated") and kind not in SESSION_KIND:
            raise err(409, "SIMULATION_NOT_ALLOWED", "Bacaan simulasi tidak boleh memindah stok (tiba/terima/daftar) — "
                                                     "matikan mode simulasi di perangkat.")
        if kind == "registration":
            from services import handheld_tags as tags
            out = await tags.process_lines(ctx, body)
        elif kind == "putaway_in":
            out = await _batch_pa(ctx, body, reads, labels)
        elif kind == "transfer_in":
            out = await _batch_transfer(ctx, body, reads, labels)
        else:
            out = await _batch_session(ctx, body, reads, labels)
        cur = await _current_version(ctx, kind, body)
        stale = bool(body.get("snapshot_version")) and cur is not None and cur != body.get("snapshot_version")
        await audit(ctx.actor_name, "handheld_batch", "handheld_batch", body.get("client_batch_id", ""),
                    {"kind": kind, "doc_id": body.get("doc_id"), "device": ctx.device.get("code"), "reads": len(reads),
                     "labels": len(labels), "status": out.get("status"), "summary": out.get("summary")}, source=ctx.source)
        return {"kind": kind, "doc_id": body.get("doc_id"), "snapshot_stale": stale, "current_version": cur, **out}

    return await once(ctx, "batch", body.get("client_batch_id", ""), _digest_body(body), run, meta)


def _digest_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """Isi yang menentukan efek bisnis (metadata jam/versi boleh berubah antar kiriman ulang tanpa konflik)."""
    return {k: body.get(k) for k in ("kind", "doc_id", "session_id", "labels", "lines", "bin_id", "label_reason", "user_id",
                                     "simulated")} | {
        "reads": sorted({_canon(r.get("epc")) for r in body.get("reads") or [] if r.get("epc")})}


async def _current_version(ctx: HandheldCtx, kind: str, body: Dict[str, Any]) -> Optional[str]:
    if kind == "registration":   # sesi besar (ribuan baris) — perangkat memuat ulang sendiri; tidak dihitung per batch
        return None
    try:
        snap = await tasks.expected(ctx, kind, body.get("doc_id", ""), 0, 1, start=False)
        return snap.get("version")
    except HTTPException:
        return None


def _item(ref: str, result: str, message: str = "", conflict: bool = False, **kw: Any) -> Dict[str, Any]:
    return {"ref": ref, "result": result, "conflict": conflict, "message": message, **kw}


def _summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {"total": len(items), "conflict": sum(1 for i in items if i["conflict"])}
    for i in items:
        out[i["result"]] = out.get(i["result"], 0) + 1
    return out


def _closed(status: str, label: str) -> Dict[str, Any]:
    return {"status": "conflict", "error": {"code": "DOC_CLOSED", "http_status": 409,
                                            "message": f"Dokumen sudah berstatus {label} — muat ulang dokumen; bukti tidak diterapkan."},
            "items": [], "summary": {}, "doc": {"status": status, "status_label": label}}


async def _batch_pa(ctx: HandheldCtx, body: Dict[str, Any], reads: List[str], labels: List[str]) -> Dict[str, Any]:
    from services import putaway_arrival_service as arr
    from services.putaway_order_service import ARRIVAL_STATUSES
    o = await db.putaway_orders.find_one({"id": body.get("doc_id")}, {"_id": 0})
    if not o or o.get("owner_entity_id") not in ctx.entity_ids:
        raise err(404, "DOC_NOT_FOUND", "Putaway Order tidak ditemukan.")
    ctx.assert_warehouse(o.get("to_warehouse_id"), "gudang tujuan PA ini")
    if o["status"] not in ARRIVAL_STATUSES:
        return _closed(o["status"], tasks.label(o["status"]))
    by_code = {(i.get("epc") or "").upper(): i for i in o.get("items") or [] if i.get("epc")}
    codes = reads + labels
    known = [c for c in codes if c in by_code]
    items = [_item(c, "extra", "Bukan roll PA ini (bacaan sekitar / roll lain) — diabaikan.") for c in codes if c not in by_code]
    trip: Dict[str, Any] = {}
    if known:
        out = await arr.confirm_arrival_trip(o["id"], known, {"type": "handheld", "client_trip_id": body["client_batch_id"]},
                                             ctx.user, ctx.entity_ids)
        trip = out.get("trip") or {}
        sets = {k: set(trip.get(k) or []) for k in ("arrived_roll_nos", "already_roll_nos", "failed_roll_nos")}
        for c in known:
            it = by_code[c]
            no = it.get("roll_no")
            if no in sets["arrived_roll_nos"]:
                items.append(_item(c, "arrived", "Tiba — tercatat di trip ini.", roll_id=it["roll_id"], roll_no=no))
            elif no in sets["failed_roll_nos"]:
                items.append(_item(c, "conflict", "Roll berubah / tujuan tidak lagi sah saat tiba — cek supervisor.", True,
                                   roll_id=it["roll_id"], roll_no=no))
            else:
                items.append(_item(c, "already", "Sudah tiba sebelumnya.", roll_id=it["roll_id"], roll_no=no))
        o = out
        await audit(ctx.actor_name, "putaway_arrival_trip", "putaway_order", o["id"],
                    {"arrived": len(trip.get("arrived_roll_nos") or []), "status": o.get("status"), "via": "handheld_c72",
                     "duplicate": out.get("duplicate_trip", False)}, source=ctx.source)
    items_doc = o.get("items") or []
    return {"status": "accepted", "items": items, "summary": _summary(items),
            "trip": {k: trip.get(k) for k in ("trip_no", "arrived_roll_nos", "already_roll_nos", "failed_roll_nos") if k in trip},
            "doc": {"status": o.get("status"), "status_label": tasks.label(o.get("status")), "expected": len(items_doc),
                    "done": sum(1 for i in items_doc if i.get("status") == "arrived"),
                    "pending": sum(1 for i in items_doc if i.get("status") == "pending")}}


async def _batch_transfer(ctx: HandheldCtx, body: Dict[str, Any], reads: List[str], labels: List[str]) -> Dict[str, Any]:
    from schemas import TransferReceiveIn, TransferReceiveLine
    from services import transfer_receipt_service as trs
    t = await tasks._transfer_doc(ctx, body.get("doc_id", ""))
    if t["status"] not in ("dispatched", "partially_received"):
        return _closed(t["status"], tasks.label(t["status"]))
    summ = await trs.summary(t)
    epcs = await tasks.epc_map([r["roll_id"] for r in summ["rolls"]])
    by_code: Dict[str, Dict[str, Any]] = {}
    for r in summ["rolls"]:
        if epcs.get(r["roll_id"]):
            by_code[epcs[r["roll_id"]]] = r
    by_label = {(r.get("roll_no") or "").upper(): r for r in summ["rolls"] if r.get("roll_no")}
    items, picked = [], {}
    for c in reads:
        if c in by_code:
            picked.setdefault(by_code[c]["roll_id"], c)
        else:
            items.append(_item(c, "extra", "Bukan roll transfer ini — diabaikan (tidak dicatat sebagai salah kirim)."))
    for c in labels:
        r = by_label.get(c)
        if not r:
            items.append(_item(c, "extra", "Label bukan roll transfer ini."))
        elif epcs.get(r["roll_id"]):
            items.append(_item(c, "needs_rfid", "Roll ini bertag RFID — baca tagnya, bukan labelnya.", roll_id=r["roll_id"],
                               roll_no=r.get("roll_no")))
        else:
            picked.setdefault(r["roll_id"], c)
    results: List[Dict[str, Any]] = []
    status = t["status"]
    ids = list(picked)
    for i in range(0, len(ids), 500):
        lines = [TransferReceiveLine(roll_id=rid) for rid in ids[i:i + 500]]
        out = await trs.receive(t, TransferReceiveIn(lines=lines, bin_id=str(body.get("bin_id") or ""),
                                                     note=f"Handheld C72 {ctx.device.get('code') or ''}".strip()), ctx.user)
        results += out["results"]
        status = out["transfer_status"]
        t = await db.warehouse_transfers.find_one({"id": t["id"]}, {"_id": 0})
    for r in results:
        ref = picked.get(r.get("roll_id"), r.get("ref"))
        res = r.get("result")
        if res in ("received", "hold", "damaged"):
            items.append(_item(ref, "received", "Diterima" + (" (ditahan aturan gudang)" if res == "hold" else "") + ".",
                               roll_id=r.get("roll_id"), roll_no=r.get("roll_no"), bin_code=r.get("bin_code")))
        elif res == "already":
            items.append(_item(ref, "already", r.get("message") or "Sudah diterima sebelumnya.", roll_id=r.get("roll_id"),
                               roll_no=r.get("roll_no")))
        else:
            items.append(_item(ref, "conflict", r.get("message") or res, True, roll_id=r.get("roll_id"), roll_no=r.get("roll_no"),
                               reason=res))
    if results:
        await audit(ctx.actor_name, "transfer_received", "transfer", t["id"],
                    {"results": [{k: r.get(k) for k in ("roll_no", "result")} for r in results], "status": status,
                     "via": "handheld_c72"}, source=ctx.source)
    return {"status": "accepted", "items": items, "summary": _summary(items),
            "doc": {"status": status, "status_label": tasks.label(status)}}


SESSION_KIND = {"outbound_so": "loading_check", "outbound_sample": "loading_check", "cycle_count": "cycle_count",
                "print_verify": "print_verify"}


async def _session_for(ctx: HandheldCtx, kind: str, doc_id: str, session_id: Optional[str]) -> Dict[str, Any]:
    """Sesi yang DIPAKAI perangkat (dari snapshot) — tidak pernah membuat sesi baru diam-diam."""
    await tasks.doc_guard(ctx, kind, doc_id)
    if not session_id:
        raise err(400, "SESSION_REQUIRED", "Batch sesi wajib membawa session_id dari snapshot dokumen.")
    sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0, "scan_log": 0})
    want = SESSION_KIND[kind]
    if not sess or (sess.get("kind") or ("print_verify" if sess.get("print_job_id") else "")) != want:
        raise err(404, "SESSION_NOT_FOUND", "Sesi tidak ditemukan untuk dokumen ini.")
    owner_doc = {"loading_check": lambda s: f"{s.get('order_id')}~{s.get('warehouse_id')}",
                 "cycle_count": lambda s: s.get("warehouse_id"), "print_verify": lambda s: s.get("print_job_id")}[want](sess)
    if owner_doc != doc_id and not (want == "loading_check" and sess.get("warehouse_id") is None
                                    and doc_id.startswith(f"{sess.get('order_id')}~")):
        raise err(409, "SESSION_MISMATCH", "Sesi ini milik dokumen lain.")
    return sess


async def _batch_session(ctx: HandheldCtx, body: Dict[str, Any], reads: List[str], labels: List[str]) -> Dict[str, Any]:
    from services import rfid_print_service as rps
    kind = body["kind"]
    sess = await _session_for(ctx, kind, body.get("doc_id", ""), body.get("session_id"))
    if sess.get("status") != "open":
        return _closed(sess.get("status") or "completed", "selesai (sesi ditutup)")
    expected = {e["epc"]: e for e in sess.get("expected") or []}
    already = set(sess.get("scanned_epcs") or [])
    prog = None
    source = "simulated" if body.get("simulated") else "device"   # RF-07: simulasi tidak pernah jadi hasil operasional
    for i in range(0, len(reads), SCAN_CHUNK):
        prog = await rps.scan_session(sess["id"], reads[i:i + SCAN_CHUNK], ctx.entity_ids, [SESSION_KIND[kind]], source,
                                      ctx.actor_name, ctx.device["id"], ctx.device.get("name") or ctx.device.get("code"))
    items = []
    for c in reads:
        e = expected.get(c)
        if e:
            items.append(_item(c, "already" if c in already else "matched", "", roll_id=e["roll_id"], roll_no=e.get("roll_no")))
        else:
            items.append(_item(c, "extra", "Tidak ada di daftar yang diharapkan (EPC asing / roll lain / salah lokasi)."))
    if labels:
        items += await _session_labels(ctx, sess, kind, labels, str(body.get("label_reason") or ""))
    if prog is None:
        prog = await rps._verify_progress(sess["id"])
    return {"status": "accepted", "items": items, "summary": _summary(items), "session_id": sess["id"],
            "doc": {"status": prog.get("status"), "expected": prog.get("expected_count"), "done": prog.get("matched_count"),
                    "pending": len(prog.get("missing") or []), "extra": len(prog.get("extra") or [])}}


async def _session_labels(ctx: HandheldCtx, sess: Dict[str, Any], kind: str, labels: List[str], reason: str) -> List[Dict[str, Any]]:
    """Cek muat: roll TANPA tag hanya lolos lewat pengecualian berizin `wms.untagged_override` + alasan (aturan asal)."""
    from services import loading_check_service as lc
    if kind not in ("outbound_so", "outbound_sample"):
        return [_item(c, "rejected", "Label tidak dipakai di jenis tugas ini — baca tag RFID.", True) for c in labels]
    if not await has_permission(ctx.user, "wms", "untagged_override"):
        return [_item(c, "needs_override", "Roll tanpa tag butuh pengecualian supervisor (izin wms.untagged_override).", True)
                for c in labels]
    out = []
    for c in labels:
        try:
            await lc.scan_label(sess["id"], c, ctx.entity_ids, reason, ctx.actor_name)
            out.append(_item(c, "exception_recorded", "Pengecualian roll tanpa tag tercatat."))
            await audit(ctx.actor_name, "loading_check_untagged_exception", "sales_order", sess.get("order_id", ""),
                        {"session_id": sess["id"], "code": c, "via": "handheld_c72"}, reason=reason.strip(), source=ctx.source)
        except HTTPException as exc:
            out.append(_item(c, "rejected", _detail(exc)["message"], True))
    return out


# ─── Penyelesaian dokumen ─────────────────────────────────────────────────────
async def complete(ctx: HandheldCtx, kind: str, doc_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if not KINDS[kind]["complete"]:
        raise err(400, "COMPLETE_NOT_SUPPORTED", "Dokumen jenis ini selesai sendiri dari trip/penerimaan per roll; sisa yang "
                                                 "tidak terbaca diputuskan supervisor di ERP.")
    await assert_operator(ctx, body.get("operator_session_id"), body.get("user_id"))

    async def run() -> Dict[str, Any]:
        from services import cycle_count_service as cc
        from services import loading_check_service as lc
        from services import rfid_print_service as rps
        sess = await _session_for(ctx, kind, doc_id, body.get("session_id"))
        if sess.get("status") != "open":
            prog = safe_doc(await rps._verify_progress(sess["id"]))
            return {"status": "accepted", "already_completed": True, "result": prog.get("result"), "session": _brief(prog)}
        if kind in ("outbound_so", "outbound_sample"):
            res = await lc.complete(sess["id"], ctx.entity_ids)
            await audit(ctx.actor_name, "loading_check_completed", "sales_order", res.get("order_id", ""),
                        {"result": res.get("result"), "missing": len(res.get("missing") or []),
                         "extra": len(res.get("extra") or []), "via": "handheld_c72"}, source=ctx.source)
            return {"status": "accepted", "result": res.get("result"), "session": _brief(res)}
        if kind == "cycle_count":
            res = await cc.complete(sess["id"], ctx.actor_name, ctx.entity_ids)
            await audit(ctx.actor_name, "rfid_cycle_count_completed", "rfid_cycle_count", res["id"],
                        {"cc_number": res.get("cc_number"), "accuracy": res.get("accuracy_pct"), "via": "handheld_c72"},
                        source=ctx.source)
            return {"status": "accepted", "result": "completed", "cycle_count": {k: res.get(k) for k in (
                "id", "cc_number", "accuracy_pct", "found_count", "missing_count", "extra_count", "metrics")}}
        res = await rps.complete_verify(sess["id"], ctx.entity_ids)
        await audit(ctx.actor_name, "rfid_verify_completed", "rfid_verify_session", sess["id"],
                    {"result": res.get("result"), "missing": len(res.get("missing") or []), "extra": len(res.get("extra") or []),
                     "via": "handheld_c72"}, source=ctx.source)
        return {"status": "accepted", "result": res.get("result"), "session": _brief(res)}

    return await once(ctx, "complete", body.get("client_request_id", ""), {"kind": kind, "doc_id": doc_id,
                                                                           "session_id": body.get("session_id")}, run,
                      {"type": "complete", "kind": kind, "doc_id": doc_id})


def _brief(prog: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": prog.get("id"), "status": prog.get("status"), "result": prog.get("result"),
            "expected": prog.get("expected_count"), "matched": prog.get("matched_count"),
            "missing": len(prog.get("missing") or []), "extra": len(prog.get("extra") or [])}


# ─── Potong sampel (mutasi lewat layanan asal) ────────────────────────────────
async def cut(ctx: HandheldCtx, task_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    from services import sample_sale_service as svc
    await assert_operator(ctx, body.get("operator_session_id"), body.get("user_id"))
    payload = {"roll_id": str(body.get("roll_id") or ""), "epc": str(body.get("epc") or ""),
               "actual_length": body.get("actual_length"), "reason": str(body.get("reason") or "")}

    async def run() -> Dict[str, Any]:
        await tasks.cutting_task(ctx, task_id)
        res = await svc.cut_sample_task(task_id, payload, ctx.user)
        c = res.get("cut") or {}
        await audit(ctx.actor_name, "sample_cut", "wms_task", task_id,
                    {"roll": c.get("cut_roll_no"), "child": c.get("child_roll_no"), "length": c.get("length"),
                     "so": c.get("sales_order_number"), "via": "handheld_c72"}, source=ctx.source)
        return {"status": "accepted", "cut": safe_doc(c), "child_needs_tag": True,
                "message": "Dipotong. Tempel tag baru di roll potongan lalu tulis EPC (menu Tulis tag)."}

    return await once(ctx, "cut", body.get("client_request_id", ""), {"task_id": task_id, **payload}, run,
                      {"type": "cut", "doc_id": task_id})
