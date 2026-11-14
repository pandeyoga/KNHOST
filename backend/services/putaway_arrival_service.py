"""PREP-C (K-GDG-10, K-RFID-10 — keputusan pemilik 8 Nov 2026) — TIBA BERTAHAP Putaway Order per trip.

Satu panggilan `confirm_arrival_trip` = SATU trip (satu muatan stacker / satu lintasan gate / satu sesi handheld):
roll yang EPC/labelnya terbaca & masih menunggu → tiba (mutasi out/in, saldo, BTG pertama); roll yang belum terbaca
TETAP menunggu (bukan exception). Status `partially_received` selama masih ada roll menunggu. Dokumen ditutup bila
semua roll tiba, atau sisanya DIPUTUSKAN lewat `close_remaining`: kembali ke transit (`return_transit`) atau
pengecualian (`exception`, diselesaikan lewat resolve-exception).

Aturan yang dijaga:
* Idempoten: trip dengan `passage_id` (gate) / `client_trip_id` (handheld) yang sama tidak dicatat dua kali; EPC yang
  sudah tiba = "sudah"; roll yang pindah di percobaan yang mati di tengah DIADOPSI (`last_pa_landed`, mutasi ber-id
  deterministik — jalur `_land_items` yang sama dengan konfirmasi lama).
* Klaim saga (`atomic_claim`) sebelum roll/tag/mutasi ditulis; tulisan akhir `finish_set` mencabut kunci; gagal di
  tengah → kunci dilepas supaya trip ulang MELANJUTKAN.
* Status akhir tanpa satu pun roll tiba = `returned` (semua kembali ke transit) / `exception` — tidak pernah
  `completed` dengan 0 tiba (celah analisis 27 Okt).

Fungsi untuk paket gate: `confirm_arrival_trip(order_id, epcs, source={"type": "gate", "passage_id": ...} |
{"type": "handheld"}, actor)`. PREP-D2 — DISAMBUNGKAN: lintasan gate IN V2 yang diputuskan di gedung bermode gate
memanggilnya lewat `gate_txn_service` (idempoten per lintasan); PA yang mencapai status akhir menutup sesi dokumen
gate (`gate_txn_service.safe_close`, K-RFID-10: roll yang tidak terbaca gate & tidak dilengkapi handheld → antrean periksa).
"""
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import HTTPException

from core_utils import new_id, next_doc_number, now_iso
from db import db
from services import putaway_order_service as pa
from services.epc import try_canonical
from services.rfid_print_service import set_journey

SOURCES = ("gate", "handheld", "manual")
SOURCE_LABEL = {"gate": "Gate IN", "handheld": "Handheld", "manual": "Manual (tanpa scan)"}
TERMINAL = ("completed", "completed_with_exception", "exception", "returned")
CLOSE_ACTIONS = ("return_transit", "exception")
# KF-T7 (#66) — panjang minimum alasan menutup sisa PA (dulu konstanta 10): pengaturan `putaway.close_reason_min_chars`.
MAX_TRIP_READS = 2000


def final_status(items: List[Dict[str, Any]]) -> Optional[str]:
    """Status PA dari status item. None = belum ada yang terjadi (status lama dipertahankan)."""
    st = {i.get("status") for i in items}
    if "pending" in st:
        return "partially_received" if st & {"arrived", "exception", "returned_transit"} else None
    if "exception" in st:
        return "completed_with_exception" if "arrived" in st else "exception"
    return "completed" if "arrived" in st else "returned"


def _counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    return {"arrived_count": sum(1 for i in items if i.get("status") == "arrived"),
            "exception_count": sum(1 for i in items if i.get("status") == "exception"),
            "pending_count": sum(1 for i in items if i.get("status") == "pending"),
            "returned_count": sum(1 for i in items if i.get("status") == "returned_transit")}


def norm_source(source: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = dict(source or {})
    kind = str(src.get("type") or "handheld").strip().lower()
    if kind not in SOURCES:
        raise HTTPException(status_code=400, detail="Sumber trip harus 'gate', 'handheld', atau 'manual'.")
    out: Dict[str, Any] = {"type": kind}
    if kind == "gate":
        pid = str(src.get("passage_id") or "").strip()
        if not pid:
            raise HTTPException(status_code=400, detail="Trip dari gate wajib membawa passage_id lintasan.")
        out["passage_id"] = pid[:80]
        for k in ("device_id", "local_passage_id", "review_case_id"):   # PREP-D2 — jejak lintasan / kasus antrean
            if src.get(k):
                out[k] = str(src[k])[:80]
    if str(src.get("client_trip_id") or "").strip():
        out["client_trip_id"] = str(src["client_trip_id"]).strip()[:80]
    return out


def trip_key(src: Dict[str, Any]) -> str:
    return src.get("passage_id") or src.get("client_trip_id") or ""


def _existing_trip(order: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    return next((t for t in order.get("arrival_trips") or []
                 if (t.get("source") or {}).get("passage_id") == key
                 or (t.get("source") or {}).get("client_trip_id") == key), None)


def read_keys(epcs: Optional[List[str]]) -> List[Set[str]]:
    """Tiap bacaan → bentuk pembanding: teks apa adanya (label QR = nomor roll) + bentuk kanonik EPC RFID."""
    out: List[Set[str]] = []
    for e in (epcs or [])[:MAX_TRIP_READS]:
        raw = str(e or "").strip().upper()
        if not raw:
            continue
        canon = try_canonical(raw)
        out.append({raw, canon} if canon else {raw})
    return out


async def land_matching(order: Dict[str, Any], epcs: Optional[List[str]], actor_name: str,
                        reason: str) -> Dict[str, List[Any]]:
    """Daratkan item MENUNGGU yang terbaca (`epcs=None` = semua menunggu). Item menunggu yang rollnya ternyata
    sudah pindah untuk PA ini (percobaan sebelumnya mati di tengah) ikut diadopsi. Mengubah `order["items"]`."""
    pending = [i for i in order["items"] if i.get("status") == "pending"]
    adopted = {r["id"] async for r in db.inventory_rolls.find(
        {"id": {"$in": [i["roll_id"] for i in pending]}, "last_pa_landed": order["id"]}, {"_id": 0, "id": 1})}
    known = {(i.get("epc") or "").upper(): i for i in order["items"] if i.get("epc")}
    hit: Set[str] = set()
    already, unknown = [], []
    for keys in read_keys(epcs):
        it = next((known[k] for k in keys if k in known), None)
        if it is None:
            unknown.append(sorted(keys)[0])
        elif it.get("status") != "pending":
            if it["roll_no"] not in already:
                already.append(it["roll_no"])
        else:
            hit.add(it["roll_id"])
    cands = [i for i in pending if epcs is None or i["roll_id"] in hit or i["roll_id"] in adopted]
    landed = await pa._land_items(order, cands, actor_name, reason)
    failed = [i for i in cands if i.get("status") == "exception"]
    if failed:
        await set_journey([i["roll_id"] for i in failed], "gate_exception",
                          {"exception_reason": "Roll berubah / tujuan tidak lagi sah saat tiba",
                           "putaway_order_id": order["id"]})
    return {"arrived": landed, "already": already, "unknown": unknown[:50], "failed": failed}


async def mark_pending(order: Dict[str, Any], action: str, actor_name: str, reason: str) -> List[Dict[str, Any]]:
    """Putuskan semua item yang MASIH menunggu: `exception` (cek ulang handheld) atau `return_transit`."""
    pend = [i for i in order["items"] if i.get("status") == "pending"]
    if not pend:
        return []
    if action == "exception":
        for i in pend:
            i["status"] = "exception"
            i["exception_reason"] = reason or "EPC tidak terbaca saat konfirmasi tiba"
        await set_journey([i["roll_id"] for i in pend], "gate_exception",
                          {"exception_reason": "EPC tidak terbaca / roll berubah saat konfirmasi tiba",
                           "putaway_order_id": order["id"]})
        return pend
    await pa.return_items_to_transit(order, pend, actor_name)
    return pend


async def finish_update(order: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    """Field akhir PA sesudah trip/penutupan: status turunan item, hitungan, BTG pertama, waktu konfirmasi."""
    items = order["items"]
    status = final_status(items) or order["status"]
    now = now_iso()
    upd: Dict[str, Any] = {"items": items, "status": status, **_counts(items), "updated_at": now}
    if any(i.get("status") == "arrived" for i in items) and not order.get("btg_number"):
        upd["btg_number"] = await next_doc_number("putaway_orders", "btg_number", "BTG")
    if status in TERMINAL:
        upd.update({"confirmed_at": now, "confirmed_by": actor_name})
    return upd


async def _load(order_id: str, scope_ids: Optional[List[str]]) -> Dict[str, Any]:
    if scope_ids is not None:
        return await pa._get(order_id, scope_ids)
    order = await db.putaway_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Putaway Order tidak ditemukan")
    return order


def _actor_name(actor: Union[str, Dict[str, Any], None]) -> str:
    if isinstance(actor, dict):
        return actor.get("name") or "Sistem"
    return str(actor or "Sistem")


def _trip_doc(order: Dict[str, Any], src: Dict[str, Any], res: Dict[str, List[Any]], actor_name: str,
              reads: int) -> Dict[str, Any]:
    n = len(order.get("arrival_trips") or []) + 1
    return {"id": new_id("patrip"), "trip_no": n, "source": src, "source_label": SOURCE_LABEL[src["type"]],
            "reads": reads, "arrived_roll_ids": [i["roll_id"] for i in res["arrived"]],
            "arrived_roll_nos": [i["roll_no"] for i in res["arrived"]],
            "failed_roll_nos": [i["roll_no"] for i in res["failed"]],
            "already_roll_nos": res["already"], "unknown_epcs": res["unknown"],
            "by": actor_name, "at": now_iso()}


async def confirm_arrival_trip(order_id: str, epcs: Optional[List[str]],
                               source: Optional[Dict[str, Any]] = None,
                               actor: Union[str, Dict[str, Any], None] = None,
                               scope_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """SATU trip tiba. `source`: {"type": "gate", "passage_id": …} | {"type": "handheld"[, "client_trip_id"]}.
    Hasil = dokumen PA + `trip` (ringkasan trip ini; None bila tidak ada roll baru) + `duplicate_trip`."""
    actor_name = _actor_name(actor)
    order = await _load(order_id, scope_ids)
    src = norm_source(source)
    if src["type"] == "manual":
        raise HTTPException(status_code=400, detail="Konfirmasi manual tanpa scan memakai konfirmasi tiba (semua) ber-alasan.")
    if not read_keys(epcs):
        raise HTTPException(status_code=400, detail="Trip tanpa EPC/label terbaca — tidak ada yang dicatat.")
    key = trip_key(src)
    # FIX-3a (B2a FLW-IN-16) — trip yang SAMA (client_trip_id/passage_id) dijawab sebagai duplikat idempoten SEBELUM
    # cek status: antrean offline HP yang mengulang trip penutup PA tidak lagi menerima 400 untuk aksi yang tercatat.
    dup = _existing_trip(order, key)
    if dup:
        return {**order, "trip": dup, "duplicate_trip": True}
    if order["status"] not in pa.ARRIVAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"PA berstatus {order['status']} — tidak menerima trip tiba.")
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal (integrasi)
    await _rfz.assert_order_movable(order, "mencatat trip tiba perintah putaway")
    from services import atomic_claim as _saga
    fresh = await _saga.claim("putaway_orders", order_id, "putaway_arrival_trip",
                              precondition={"status": {"$in": list(pa.ARRIVAL_STATUSES)}}, actor=actor_name)
    trip = None
    try:
        dup = _existing_trip(fresh, key)
        if dup:   # trip yang sama baru saja selesai di antara baca & klaim
            await _saga.release("putaway_orders", order_id)
            return {**fresh, "trip": dup, "duplicate_trip": True}
        res = await land_matching(fresh, epcs, actor_name, f"trip {SOURCE_LABEL[src['type']]}")
        upd = await finish_update(fresh, actor_name)
        upd["last_trip_at"] = now_iso()
        if not fresh.get("dispatched_at") and (res["arrived"] or res["failed"]):
            # FIX-3a (B2a FLW-IN-15, keputusan D7) — "Kirim" opsional: trip tiba pertama mengisi `dispatched_at`.
            upd["dispatched_at"] = now_iso()
            upd["dispatched_by"] = fresh.get("dispatched_by") or actor_name
            upd["dispatch_implicit"] = True
        op = _saga.finish_set(upd)
        if res["arrived"] or res["failed"]:
            trip = _trip_doc(fresh, src, res, actor_name, len(epcs or []))
            for i in res["arrived"]:
                i.update({"arrived_trip_no": trip["trip_no"], "arrived_via": src["type"]})
            op["$push"] = {"arrival_trips": trip}
        else:
            trip = None
        await db.putaway_orders.update_one({"id": order_id}, op)
    except BaseException:
        await _saga.release("putaway_orders", order_id)
        raise
    out = await _load(order_id, scope_ids)
    await gate_session_hook(out)
    out["trip"] = trip or {"arrived_roll_nos": [], "already_roll_nos": res["already"], "unknown_epcs": res["unknown"],
                           "message": "Tidak ada roll baru yang tiba pada trip ini."}
    out["duplicate_trip"] = False
    return out


async def gate_session_hook(order: Dict[str, Any]) -> None:
    """PREP-D2 (K-RFID-10) — PA berstatus akhir → sesi dokumen gate IN (tujuan) & OUT (asal) ditutup. Best-effort."""
    if order.get("status") in TERMINAL:
        from services import gate_txn_service as _gt
        await _gt.safe_close("putaway", order["id"], ("in", "out"), "putaway_closed")


async def close_remaining(order_id: str, action: str, reason: str, scope_ids: Optional[List[str]],
                          actor: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
    """Tutup PA: roll yang MASIH menunggu diputuskan — `return_transit` (kembali siap-putaway di gudang asal) atau
    `exception` (cek ulang handheld lewat resolve-exception). Alasan wajib (minimal `putaway.close_reason_min_chars`
    huruf, bawaan 10)."""
    actor_name = _actor_name(actor)
    order = await _load(order_id, scope_ids)
    if order["status"] not in pa.ARRIVAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"PA berstatus {order['status']} — tidak ada sisa yang bisa diputuskan.")
    if action not in CLOSE_ACTIONS:
        raise HTTPException(status_code=400, detail="Keputusan sisa harus 'return_transit' atau 'exception'.")
    why = (reason or "").strip()
    from services.nilai_pengaturan import nilai
    minimal = int(await nilai("putaway.close_reason_min_chars"))
    if len(why) < minimal:
        raise HTTPException(status_code=400, detail=f"Alasan menutup PA wajib (minimal {minimal} huruf).")
    if not any(i.get("status") == "pending" for i in order["items"]):
        raise HTTPException(status_code=400, detail="Tidak ada roll yang masih menunggu di PA ini.")
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal (integrasi)
    await _rfz.assert_order_movable(order, "menutup sisa perintah putaway")
    from services import atomic_claim as _saga
    fresh = await _saga.claim("putaway_orders", order_id, "putaway_close_remaining",
                              precondition={"status": {"$in": list(pa.ARRIVAL_STATUSES)}}, actor=actor_name)
    try:
        await land_matching(fresh, [], actor_name, "adopsi sebelum tutup")   # roll yang sudah pindah diadopsi
        decided = await mark_pending(fresh, action, actor_name, f"Ditutup: {why}")
        upd = await finish_update(fresh, actor_name)
        upd["closed_remaining"] = {"action": action, "reason": why, "by": actor_name, "at": now_iso(),
                                   "rolls": [i["roll_no"] for i in decided]}
        await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set(upd))
    except BaseException:
        await _saga.release("putaway_orders", order_id)
        raise
    out = await _load(order_id, scope_ids)
    await gate_session_hook(out)
    return out
