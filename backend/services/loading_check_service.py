"""FASE R4 — FINAL LOADING CHECK: sweep handheld vs manifest SO sebelum naik mobil.

Memakai koleksi `rfid_verify_sessions` yang sama (kind="loading_check") agar tidak
ada mesin kembar. Hasil terakhir disimpan di `sales_orders.loading_check`; dispatch
DIBLOKIR bila ada sesi terbuka atau hasil terakhir tidak bersih.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, safe_doc

EXPECTED_STATUSES = ["reserved", "committed", "picked", "packed", "allocated"]


async def _expected_rolls(order_id: str) -> List[Dict[str, Any]]:
    rolls = await db.inventory_rolls.find({
        "reserved_ref.type": "sales_order", "reserved_ref.id": order_id,
        "status": {"$in": EXPECTED_STATUSES}, "length_remaining": {"$gt": 0},
    }, {"_id": 0, "id": 1, "roll_no": 1, "rfid_tag_id": 1, "product_id": 1, "status": 1,
        "length_remaining": 1}).to_list(2000)
    return rolls


async def start(order_id: str, scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "id": 1, "number": 1,
                                                           "entity_id": 1})
    if not so:
        raise HTTPException(status_code=404, detail="SO tidak ditemukan")
    if so.get("entity_id") and so["entity_id"] not in scope_ids:
        raise HTTPException(status_code=403, detail="SO di luar entitas Anda")
    existing = await db.rfid_verify_sessions.find_one(
        {"kind": "loading_check", "order_id": order_id, "status": "open"}, {"_id": 0})
    if existing:
        return safe_doc(existing)
    from services.roll_service import assert_cut_identity_ready
    await assert_cut_identity_ready(order_id)  # WM-02 — potong dikonfirmasi & tag anak terverifikasi
    rolls = await _expected_rolls(order_id)
    if not rolls:
        raise HTTPException(status_code=400, detail="Tidak ada roll ter-alokasi untuk SO ini (pick dulu).")
    tag_ids = [r["rfid_tag_id"] for r in rolls if r.get("rfid_tag_id")]
    tags = {t["id"]: t for t in await db.rfid_tags.find(
        {"id": {"$in": tag_ids}, "status": "active"}, {"_id": 0}).to_list(2000)}
    expected, untagged = [], []
    for r in rolls:
        t = tags.get(r.get("rfid_tag_id"))
        if t:
            expected.append({"epc": t["epc"], "roll_id": r["id"], "roll_no": r.get("roll_no", ""),
                             "sku": t.get("sku", ""), "product_name": t.get("product_name", "")})
        else:  # RF-05 — tanpa tag / tag nonaktif / retired / tag_id menggantung
            untagged.append({"roll_id": r["id"], "roll_no": r.get("roll_no", ""),
                             "reason": "tag tidak aktif" if r.get("rfid_tag_id") else "tanpa tag"})
    sess = {
        "id": new_id("rvs"), "kind": "loading_check", "order_id": order_id,
        "so_number": so.get("number", ""), "print_job_id": None,
        "owner_entity_id": so.get("entity_id"), "warehouse_id": None,
        "expected": expected, "scanned_epcs": [], "missing": [], "extra": [],
        "untagged_count": len(untagged), "untagged": untagged, "untagged_resolved": [], "scan_sources": [],
        # Peringatan dini: roll expected yang BELUM committed akan lolos check tapi
        # tertahan saat dispatch (ship_order_rolls hanya kirim roll committed).
        "not_committed_count": sum(1 for r in rolls
                                   if r.get("status") in ("reserved", "allocated")),
        "status": "open", "created_at": now_iso(), "created_by": actor_name,
        "completed_at": None,
    }
    await db.rfid_verify_sessions.insert_one(dict(sess))
    return safe_doc(sess)


async def complete(session_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    from services.rfid_print_service import _verify_progress
    prog = await _verify_progress(session_id)
    if prog.get("kind") != "loading_check":
        raise HTTPException(status_code=400, detail="Bukan sesi loading check")
    if prog.get("owner_entity_id") and prog["owner_entity_id"] not in scope_ids:
        raise HTTPException(status_code=403, detail="Sesi di luar entitas Anda")
    if prog["status"] != "open":
        raise HTTPException(status_code=400, detail="Sesi sudah selesai")
    # INV-ATOMIC-01 — klaim sesi (status open) SESUDAH validasi, sebelum SO ditulis; finish_set.
    from services import atomic_claim as _saga
    from services.rfid_print_service import evidence_result
    await _saga.claim("rfid_verify_sessions", session_id, "loading_check_complete",
                      precondition={"status": "open"})
    prog = await _verify_progress(session_id)  # RF-10 — snapshot sesudah klaim; scan terlambat ditolak
    unresolved = [u for u in prog.get("untagged", []) if u["roll_id"] not in set(prog.get("untagged_resolved") or [])]
    # RF-07 — sesi berisi scan simulasi → 'simulated' (bukan bukti fisik; dispatch tetap terblokir)
    clean = evidence_result(prog, not prog["missing"] and not prog["extra"] and not unresolved)
    manifest = await _manifest(prog["order_id"])  # RF-06 — hasil terikat roll+panjang saat check
    now = now_iso()
    await db.sales_orders.update_one({"id": prog["order_id"]}, {"$set": {"loading_check": {
        "session_id": session_id, "result": clean,
        "matched": prog["matched_count"], "expected": prog["expected_count"],
        "missing": prog["missing"], "extra": prog["extra"], "untagged_unresolved": unresolved,
        "scan_sources": prog.get("scan_sources") or [], "manifest": manifest, "checked_at": now}}})
    await db.rfid_verify_sessions.update_one({"id": session_id}, _saga.finish_set({
        "status": "completed", "result": clean, "missing": prog["missing"],
        "extra": prog["extra"], "completed_at": now}))
    return await _verify_progress(session_id)


async def scan_label(session_id: str, code: str, scope_ids: List[str], reason: str = "",
                     actor: str = "") -> Dict[str, Any]:
    """RF-05 + W2-REQ-08 — roll tanpa tag hanya lolos lewat PENGECUALIAN berizin
    (`wms.untagged_override`, dicek router) dengan alasan; label = no. roll."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail=(
            "Roll tanpa tag wajib RFID — pengecualian lewat label butuh alasan (min. 5 karakter)."))
    sess = await db.rfid_verify_sessions.find_one({"id": session_id, "kind": "loading_check"}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Sesi loading check tidak ditemukan")
    if sess.get("owner_entity_id") and sess["owner_entity_id"] not in scope_ids:
        raise HTTPException(status_code=403, detail="Sesi di luar entitas Anda")
    norm = (code or "").strip().upper()
    hit = next((u for u in sess.get("untagged", []) if (u.get("roll_no") or "").strip().upper() == norm), None)
    if not hit:
        raise HTTPException(status_code=400, detail=f"Label '{code}' bukan roll tanpa-tag pada sesi ini.")
    res = await db.rfid_verify_sessions.update_one({"id": session_id, "status": "open", "saga_lock": {"$exists": False}},
                                                   {"$addToSet": {"untagged_resolved": hit["roll_id"]},
                                                    "$push": {"untagged_exceptions": {
                                                        "roll_id": hit["roll_id"], "roll_no": hit.get("roll_no", ""),
                                                        "reason": reason, "by": actor, "at": now_iso()}}})
    if res.matched_count != 1:
        raise HTTPException(status_code=400, detail="Sesi sudah selesai")
    return await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0})


async def _manifest(order_id: str) -> List[Dict[str, Any]]:
    return sorted(({"roll_id": r["id"], "length": round(float(r.get("length_remaining") or 0), 2)}
                   for r in await _expected_rolls(order_id)), key=lambda x: x["roll_id"])


async def warehouse_policy(warehouse_id: Optional[str]) -> str:
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "loading_check_policy": 1}) if warehouse_id else None
    return (wh or {}).get("loading_check_policy") or "optional"


async def override(order_id: str, reason: str, actor: str) -> Dict[str, Any]:
    """RF-04 — pengecualian berizin (wms.approve): dispatch tanpa sweep RFID, tetap terikat manifest."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Alasan override loading check wajib (min. 5 karakter).")
    if await db.rfid_verify_sessions.find_one({"kind": "loading_check", "order_id": order_id, "status": "open"}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="Masih ada sesi loading check terbuka — selesaikan dulu.")
    lc = {"session_id": None, "result": "override", "reason": reason, "by": actor,
          "manifest": await _manifest(order_id), "checked_at": now_iso()}
    await db.sales_orders.update_one({"id": order_id}, {"$set": {"loading_check": lc}})
    return lc


async def untagged_rolls(order_id: str, warehouse_id: Optional[str] = None) -> List[str]:
    """W2-REQ-08 — no. roll SO (gudang ini) yang belum punya tag RFID aktif."""
    q: Dict[str, Any] = {"reserved_ref.type": "sales_order", "reserved_ref.id": order_id,
                         "status": {"$in": EXPECTED_STATUSES}, "length_remaining": {"$gt": 0}}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    rolls = await db.inventory_rolls.find(q, {"_id": 0, "roll_no": 1, "rfid_tag_id": 1}).to_list(2000)
    tag_ids = [r["rfid_tag_id"] for r in rolls if r.get("rfid_tag_id")]
    active = {t["id"] for t in await db.rfid_tags.find(
        {"id": {"$in": tag_ids}, "status": "active"}, {"_id": 0, "id": 1}).to_list(2000)}
    return [r.get("roll_no", "") for r in rolls if r.get("rfid_tag_id") not in active]


async def dispatch_guard(order_id: Optional[str], warehouse_id: Optional[str] = None) -> None:
    """Blokir dispatch bila loading check terbuka / tidak bersih / basi (RF-06) / wajib tapi tidak ada (RF-04)."""
    if not order_id:
        return
    if await db.rfid_verify_sessions.find_one({"kind": "loading_check", "order_id": order_id, "status": "open"},
                                              {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="Final Loading Check masih berjalan — selesaikan dulu sebelum kirim.")
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "loading_check": 1})
    lc = (so or {}).get("loading_check")
    if not lc:
        if await warehouse_policy(warehouse_id) == "required":
            raise HTTPException(status_code=400, detail=(
                "Gudang ini mewajibkan Final Loading Check sebelum kirim — jalankan check (RFID / scan label) "
                "atau minta override berizin dengan alasan."))
        # W2-REQ-08 — semua roll wajib bertag aktif; tanpa check, roll tanpa tag tidak boleh berangkat.
        untagged = await untagged_rolls(order_id, warehouse_id)
        if untagged:
            raise HTTPException(status_code=400, detail=(
                f"{len(untagged)} roll belum bertag RFID aktif ({', '.join(untagged[:5])}) — cetak/verifikasi tag, "
                "atau jalankan Final Loading Check dengan pengecualian berizin."))
        return
    if lc.get("result") == "simulated":
        raise HTTPException(status_code=400, detail=(
            "Final Loading Check hanya berisi scan SIMULASI — bukan bukti fisik. Ulangi dengan handheld/scan "
            "nyata atau minta override berizin dengan alasan."))
    if lc.get("result") not in ("clean", "override"):
        raise HTTPException(status_code=400, detail=(
            f"Final Loading Check TIDAK BERSIH (missing {len(lc.get('missing') or [])}, "
            f"extra {len(lc.get('extra') or [])}, roll tanpa tag belum diverifikasi {len(lc.get('untagged_unresolved') or [])})"
            " — ulangi check atau perbaiki muatan sebelum kirim."))
    # RF-06 — roll siap kirim sekarang harus subset manifest saat check (roll & panjang sama).
    checked = {m["roll_id"]: m["length"] for m in (lc.get("manifest") or [])}
    changed = [m["roll_id"] for m in await _manifest(order_id) if checked.get(m["roll_id"]) != m["length"]]
    if lc.get("manifest") is None or changed:
        raise HTTPException(status_code=400, detail=(
            "Alokasi/roll berubah sesudah Final Loading Check"
            + (f" ({len(changed)} roll baru/berubah)" if changed else " (hasil lama tanpa manifest)")
            + " — ulangi check sebelum kirim."))

async def status_for_order(order_id: str) -> Dict[str, Any]:
    open_sess = await db.rfid_verify_sessions.find_one(
        {"kind": "loading_check", "order_id": order_id, "status": "open"}, {"_id": 0})
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "loading_check": 1})
    last = (so or {}).get("loading_check")
    log = []
    if last and last.get("session_id"):  # riwayat scan sesi terakhir (siapa, kapan, dari perangkat apa)
        done = await db.rfid_verify_sessions.find_one({"id": last["session_id"]}, {"_id": 0, "scan_log": 1})
        log = (done or {}).get("scan_log") or []
    return {"open_session": safe_doc(open_sess) if open_sess else None, "last_result": last, "last_scan_log": log}
