"""L10 LN-101 — opname per roll: snapshot scope node → scan → rekonsiliasi → finalisasi.

Memakai sesi `cycle_count_sessions` yang sama (field `roll_count`), bukan engine kedua.
Cutoff/delta: snapshot dibekukan saat scope dipilih; tiap scan menyimpan saldo LIVE roll saat
discan. Selisih = fisik − live-saat-scan, sehingga gerakan yang sudah diposting tidak diulang.
Roll yang berubah sesudah discan → wajib hitung ulang (CAS gagal), bukan ditimpa.
Hilang / roll asing mengikuti SOP OPS-01 (hitung ulang → ACC); tanpa batas nilai kerugian (owner 2026-10-19).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso
from db import db
from services.location_service import flatten_bins
from services.roll_service import PHYSICAL_ROLL_STATUSES, rebuild_balance

EPS = 0.001
TAGS = ("ok", "damaged", "unreadable")
KIND_LABEL = {
    "matched": "Cocok", "missing": "Tidak ditemukan (hilang)", "wrong_address": "Salah alamat/rak",
    "qty_diff": "Qty fisik berbeda", "tag_damaged": "Tag rusak", "unreadable": "Tag tidak terbaca (input manual)",
    "foreign": "Roll asing (bukan scope)", "unknown": "Kode tidak dikenal", "moved_after_cutoff": "Bergerak setelah snapshot",
    "delta_in": "Masuk scope setelah snapshot",
}
# OPS-01 (keputusan owner 2026-10-18): hilang → wajib hitung ulang lalu dihapus saat ACC; roll asing gudang
# yang sama → alamat dipindah ke tempat ditemukan; kode tak dikenal → roll baru saat ACC; penyetuju =
# inventory.approve_count; belum ada batas nilai kerugian tambahan.
APPLY_KINDS = {"wrong_address", "qty_diff", "foreign"}
ROLL_FIELDS = {"_id": 0, "id": 1, "roll_no": 1, "rfid_epc": 1, "product_id": 1, "owner_entity_id": 1, "warehouse_id": 1,
               "bin_id": 1, "bin_code": 1, "length_remaining": 1, "unit": 1, "status": 1, "unit_cost": 1, "base_unit_cost": 1}


def scope_bins(wh: Dict[str, Any], node_id: str) -> List[Dict[str, Any]]:
    bins = flatten_bins(wh)
    if not node_id:
        return bins
    hit = [b for b in bins if node_id in (b["bin_id"], b["zone_id"], b["rack_id"], b["level_id"])]
    if not hit:
        raise HTTPException(status_code=400, detail=f"Node lokasi '{node_id}' tidak ada di gudang {wh.get('name', '')}.")
    return hit


def _node_label(b: Dict[str, Any], node_id: str) -> str:
    parts = [(b["zone_id"], b["zone"]), (b["rack_id"], b["rack"]), (b["level_id"], b["level"]), (b["bin_id"], b["code"])]
    names = []
    for nid, name in parts:
        if name:
            names.append(name)
        if nid == node_id:
            break
    return " › ".join(names)


async def _relocation_block(roll: Dict[str, Any], bin_id: str) -> Optional[str]:
    """Koreksi alamat tetap lewat aturan penempatan yang sama dengan putaway (jalur tunggal)."""
    from services import placement_rules as pr
    if (roll.get("active_movement") or {}).get("id"):
        return "Roll sedang dalam perpindahan berjalan — selesaikan perpindahan dulu."
    if float(roll.get("length_reserved") or 0) > EPS:
        return "Roll punya reservasi potong — konfirmasi potong dulu."
    wh = await db.warehouses.find_one({"id": roll["warehouse_id"]}, {"_id": 0}) or {}
    node = pr.resolve_bin(wh, bin_id)
    if not node:
        return "Bin tujuan tidak ada di master gudang."
    prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0}) or {}
    res = await pr.evaluate(wh, node, roll, prod)
    if res["function"] == "qc" and not pr.is_held(roll):
        return "Roll tersedia ditemukan di area QC/karantina — tindak lanjuti lewat QC/putaway, bukan koreksi opname."
    if res["blocks"]:
        return "Aturan bin menolak: " + "; ".join(res["blocks"][:3])
    return None


async def make_snapshot(session: Dict[str, Any], node_id: str, owners: Optional[List[str]]) -> Dict[str, Any]:
    wh = await db.warehouses.find_one({"id": session["warehouse_id"]}, {"_id": 0}) or {}
    bins = scope_bins(wh, node_id)
    q: Dict[str, Any] = {"warehouse_id": session["warehouse_id"], "status": {"$in": PHYSICAL_ROLL_STATUSES},
                         "length_remaining": {"$gt": 0}, "bin_id": {"$in": [b["bin_id"] for b in bins]}}
    if owners is not None:
        q["owner_entity_id"] = {"$in": owners}
    rolls = await db.inventory_rolls.find(q, ROLL_FIELDS).to_list(20000)
    return {
        "node_id": node_id, "node_label": _node_label(bins[0], node_id) if node_id else "Seluruh gudang",
        "bin_ids": [b["bin_id"] for b in bins], "snapshot_at": now_iso(), "owners": owners,
        "expected": [{"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "product_id": r.get("product_id"),
                      "owner_entity_id": r.get("owner_entity_id", ""), "bin_id": r.get("bin_id"),
                      "qty": float(r.get("length_remaining") or 0), "unit": r.get("unit", ""), "status": r.get("status")}
                     for r in rolls],
        "scans": [], "duplicates": 0,
    }


async def find_roll(code: str) -> Optional[Dict[str, Any]]:
    c = (code or "").strip()
    if not c:
        return None
    return await db.inventory_rolls.find_one({"$or": [{"id": c}, {"roll_no": c}, {"rfid_epc": c}]}, ROLL_FIELDS)


def classify_scan(rc: Dict[str, Any], scan: Dict[str, Any], warehouse_id: str) -> List[str]:
    kinds: List[str] = []
    if scan.get("tag") == "damaged":
        kinds.append("tag_damaged")
    if scan.get("tag") == "unreadable":
        kinds.append("unreadable")
    if not scan.get("roll_id"):
        return kinds + ["unknown"]
    exp = {e["roll_id"]: e for e in rc["expected"]}
    if scan["roll_id"] not in exp:
        same_place = scan.get("live_warehouse_id") == warehouse_id and scan.get("live_bin_id") == scan.get("bin_id") \
            and scan.get("live_bin_id") in rc["bin_ids"]
        if same_place:
            return kinds + ["delta_in"]
        kinds.append("foreign")
    elif scan.get("bin_id") != scan.get("live_bin_id"):
        kinds.append("wrong_address")
    if scan.get("measured_qty") is not None and abs(float(scan["measured_qty"]) - float(scan.get("live_qty") or 0)) > EPS:
        kinds.append("qty_diff")
    return kinds or ["matched"]


async def reconcile(session: Dict[str, Any]) -> Dict[str, Any]:
    rc = session.get("roll_count") or {}
    if not rc:
        return {"enabled": False}
    scanned = {s["roll_id"] for s in rc["scans"] if s.get("roll_id")}
    lines = [{**s, "kinds": classify_scan(rc, s, session["warehouse_id"])} for s in rc["scans"]]
    missing, moved = [], []
    left = [e for e in rc["expected"] if e["roll_id"] not in scanned]
    live = {r["id"]: r for r in await db.inventory_rolls.find({"id": {"$in": [e["roll_id"] for e in left]}}, ROLL_FIELDS).to_list(20000)}
    recounts, madj = rc.get("missing_recounts") or {}, rc.get("missing_adjustments") or {}
    for e in left:
        r = live.get(e["roll_id"]) or {}
        if e["roll_id"] in madj:   # sudah dihapus lewat OPS-01 — tetap tampil sebagai hilang
            missing.append({**e, "recount": recounts.get(e["roll_id"]), "adjustment": madj[e["roll_id"]]})
            continue
        gone = (r.get("warehouse_id") != session["warehouse_id"] or r.get("bin_id") != e["bin_id"]
                or r.get("status") not in PHYSICAL_ROLL_STATUSES or float(r.get("length_remaining") or 0) <= EPS
                or abs(float(r.get("length_remaining") or 0) - float(e["qty"])) > EPS)
        row = {**e, "live_bin_id": r.get("bin_id"), "live_status": r.get("status"), "live_qty": float(r.get("length_remaining") or 0),
               "recount": recounts.get(e["roll_id"])}
        (moved if gone else missing).append(row)
    counts: Dict[str, int] = {k: 0 for k in KIND_LABEL}
    for ln in lines:
        for k in ln["kinds"]:
            counts[k] += 1
    counts["missing"], counts["moved_after_cutoff"] = len(missing), len(moved)
    return {"enabled": True, "node_id": rc["node_id"], "node_label": rc.get("node_label"), "snapshot_at": rc["snapshot_at"],
            "expected_rolls": len(rc["expected"]), "scanned_rolls": len(scanned), "duplicates": rc.get("duplicates", 0),
            "lines": lines, "missing": missing, "moved_after_cutoff": moved, "counts": counts, "labels": KIND_LABEL,
            "policy": ("SOP opname (OPS-01): roll hilang wajib dihitung ulang dulu, baru dihapus dari stok saat disetujui; "
                       "roll asing dari gudang yang sama dipindah ke alamat tempat ditemukan; kode tak dikenal dibuat roll baru "
                       "setelah penyetuju menetapkan produk & pemilik.")}


async def _movement(roll: Dict[str, Any], qty: float, mtype: str, ref: str, extra: Dict[str, Any]) -> None:
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
        "owner_entity_id": roll.get("owner_entity_id", ""), "movement_type": mtype, "quantity": qty,
        "unit": roll.get("unit", ""), "roll_id": roll["id"], "qty_rolls": 0, "source_document": ref,
        "unit_cost": float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0), "timestamp": now_iso(), **extra})


# ─── AUD-WMS-01 — catatan operasi bertahap per baris (tahan restart, idempoten) ──────────────────────────────
# Urutan: (1) catatan operasi `roll_count.ops.<kunci>` ditulis di sesi (token, lease, snapshot roll, syarat CAS,
# perubahan, rencana pergerakan & jurnal) → (2) roll diubah lewat CAS SEKALIGUS diberi penanda `count_op` = token →
# (3) pergerakan, jurnal, saldo agregat → (4) operasi ditandai selesai & penanda dicabut. Retry sesudah gangguan di
# batas mana pun membaca catatan itu: roll yang membawa token SENDIRI = perubahan milik sendiri → lanjutkan (3)–(4);
# roll tanpa token → CAS dicoba dengan syarat yang sama (gagal = roll diubah transaksi lain → recount). Lease
# memastikan hanya satu pemroses yang melanjutkan; lease dilepas saat error dan kedaluwarsa bila proses mati.
OPS = "roll_count.ops"
LEASE_TTL = 120   # detik
BUSY = "Baris ini sedang diproses pemroses lain (atau proses sebelumnya terhenti < 2 menit lalu) — finalisasi lagi sebentar lagi."


def _cutoff(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


async def _movement_once(roll: Dict[str, Any], qty: float, mtype: str, ref: str, extra: Dict[str, Any]) -> None:
    """Pergerakan sekali per (ref, jenis, roll) — aman diulang saat melanjutkan operasi yang terputus."""
    if not await db.inventory_movements.find_one({"source_document": ref, "movement_type": mtype, "roll_id": roll["id"]},
                                                 {"_id": 1}):
        await _movement(roll, qty, mtype, ref, extra)


async def _cas_op(op: Dict[str, Any]) -> bool:
    cas = {"id": op["roll"]["id"], **op["cas"], "status": {"$in": PHYSICAL_ROLL_STATUSES}}
    res = await db.inventory_rolls.update_one(cas, {"$set": {**op["upd"], "count_op": op["token"]}})
    return res.modified_count == 1


async def _owned(op: Dict[str, Any]) -> bool:
    return bool(await db.inventory_rolls.find_one({"id": op["roll"]["id"], "count_op": op["token"]}, {"_id": 1}))


async def _take_lease(session_id: str, key: str, op: Dict[str, Any]) -> Optional[str]:
    lid, path = new_id("lse"), f"{OPS}.{key}"
    res = await db.cycle_count_sessions.update_one(
        {"id": session_id, f"{path}.token": op["token"], f"{path}.status": "pending",
         "$or": [{f"{path}.lease": None}, {f"{path}.lease.at": {"$lt": _cutoff(LEASE_TTL)}}]},
        {"$set": {f"{path}.lease": {"id": lid, "at": now_iso()}}})
    return lid if res.modified_count == 1 else None


async def _drop_lease(session_id: str, key: str, lid: str) -> None:
    await db.cycle_count_sessions.update_one({"id": session_id, f"{OPS}.{key}.lease.id": lid},
                                             {"$set": {f"{OPS}.{key}.lease": None}})


async def _drop_op(session_id: str, key: str, token: str) -> None:
    await db.cycle_count_sessions.update_one({"id": session_id, f"{OPS}.{key}.token": token}, {"$unset": {f"{OPS}.{key}": ""}})


async def _finish_op(session: Dict[str, Any], key: str, op: Dict[str, Any]) -> Dict[str, Any]:
    """Langkah SESUDAH roll berubah. Tiap langkah idempoten: pergerakan dicek per ref, jurnal idempoten per
    source_id, rebuild saldo selalu aman — jadi dapat diulang sampai tuntas."""
    from services import gl_service as gl
    ref, roll, out = op["ref"], op["roll"], dict(op["result"])
    for m in op.get("movements") or []:
        await _movement_once(roll, float(m["qty"]), m["type"], ref, m.get("extra") or {})
    jr = op.get("journal")
    if jr:
        je = await gl.post_cycle_count_variance(source_id=ref, entity_id=roll.get("owner_entity_id", ""),
                                                amount_signed=float(jr["amount_signed"]), label=jr.get("label") or ref)
        if not je:   # sudah diposting pada percobaan sebelumnya (atau nilainya nol)
            je = await db.journal_entries.find_one({"source_type": "cycle_count_variance", "source_id": ref,
                                                    "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
        out["journal_id"] = (je or {}).get("id")
    if op.get("rebuild"):
        await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll.get("owner_entity_id", ""))
    await db.cycle_count_sessions.update_one({"id": session["id"], f"{OPS}.{key}.token": op["token"]},
                                             {"$set": {f"{OPS}.{key}.status": "done", f"{OPS}.{key}.result": out,
                                                       f"{OPS}.{key}.lease": None, f"{OPS}.{key}.done_at": now_iso()}})
    await db.inventory_rolls.update_one({"id": roll["id"], "count_op": op["token"]}, {"$unset": {"count_op": ""}})
    return out


async def _drive(session: Dict[str, Any], key: str, op: Dict[str, Any], lid: str, conflict: str) -> Dict[str, Any]:
    """Pemegang lease: pastikan roll berubah TEPAT sekali, lalu tuntaskan sisa langkah."""
    try:
        if not await _owned(op) and not await _cas_op(op):
            await _drop_op(session["id"], key, op["token"])
            return {"status": "recount", "message": conflict, "at": now_iso()}
        return await _finish_op(session, key, op)
    except Exception:
        await _drop_lease(session["id"], key, lid)
        raise


async def _resume_op(session: Dict[str, Any], key: str, conflict: str) -> Optional[Dict[str, Any]]:
    """Hasil operasi milik sendiri (selesai/dilanjutkan) — None bila tidak ada catatan untuk baris ini."""
    sess = await db.cycle_count_sessions.find_one({"id": session["id"]}, {"_id": 0, f"{OPS}.{key}": 1}) or {}
    op = ((sess.get("roll_count") or {}).get("ops") or {}).get(key)
    if not op:
        return None
    if op.get("status") == "done":
        await db.inventory_rolls.update_one({"id": op["roll"]["id"], "count_op": op["token"]}, {"$unset": {"count_op": ""}})
        return op["result"]
    lid = await _take_lease(session["id"], key, op)
    if not lid:
        return {"status": "recount", "message": BUSY, "at": now_iso()}
    return await _drive(session, key, op, lid, conflict)


async def _apply_op(session: Dict[str, Any], key: str, cas_fields: Dict[str, Any], upd: Dict[str, Any],
                    op: Dict[str, Any], conflict: str) -> Dict[str, Any]:
    lid = new_id("lse")
    op = {**op, "cas": cas_fields, "upd": upd, "token": new_id("cop"), "status": "pending", "at": now_iso(),
          "lease": {"id": lid, "at": now_iso()}}
    res = await db.cycle_count_sessions.update_one({"id": session["id"], f"{OPS}.{key}": {"$exists": False}},
                                                   {"$set": {f"{OPS}.{key}": op}})
    if res.modified_count != 1:
        return {"status": "recount", "message": BUSY, "at": now_iso()}
    return await _drive(session, key, op, lid, conflict)


async def apply_scan(session: Dict[str, Any], scan: Dict[str, Any], kinds: List[str], actor: str) -> Dict[str, Any]:
    """Satu baris scan → koreksi alamat dan/atau qty (CAS terhadap saldo live saat scan). Idempoten per baris;
    AUD-WMS-01: gangguan sesudah roll berubah dilanjutkan oleh retry (lihat catatan operasi di atas)."""
    ref = f"{session['id']}:roll:{scan['roll_id']}"
    key = f"scan_{scan['roll_id']}"
    resumed = await _resume_op(session, key, "Roll berubah sesudah discan — hitung ulang roll ini.")
    if resumed is not None:
        return resumed
    if "foreign" in kinds and not scan.get("live_warehouse_id"):
        return {"status": "exception", "message": "Roll milik badan usaha di luar akses Anda — serahkan ke penyetuju yang berwenang.", "at": now_iso()}
    cas = {"id": scan["roll_id"], "length_remaining": scan["live_qty"], "bin_id": scan["live_bin_id"],
           "status": {"$in": PHYSICAL_ROLL_STATUSES}}
    roll = await db.inventory_rolls.find_one(cas, {**ROLL_FIELDS, "active_movement": 1, "length_reserved": 1,
                                                   "inspection": 1, "grade": 1, "lot": 1})
    if not roll:
        return {"status": "recount", "message": "Roll berubah sesudah discan — hitung ulang roll ini.", "at": now_iso()}
    if "foreign" in kinds and roll.get("warehouse_id") != session["warehouse_id"]:
        return {"status": "exception", "message": "Roll tercatat di gudang lain — pindahkan lewat transfer, bukan koreksi opname.", "at": now_iso()}
    if "wrong_address" in kinds or "foreign" in kinds:
        kinds = list(kinds) + ["wrong_address"]
        block = await _relocation_block(roll, scan["bin_id"])
        if block:
            return {"status": "exception", "message": block, "at": now_iso()}
    roll = {k: v for k, v in roll.items() if k in ROLL_FIELDS}
    upd: Dict[str, Any] = {"updated_at": now_iso()}
    out: Dict[str, Any] = {"status": "applied", "at": now_iso(), "by": actor}
    movements: List[Dict[str, Any]] = []
    if "wrong_address" in kinds:
        b = next((x for x in flatten_bins(await db.warehouses.find_one({"id": roll["warehouse_id"]}, {"_id": 0}) or {})
                  if x["bin_id"] == scan["bin_id"]), None)
        upd.update({"bin_id": scan["bin_id"], "bin_code": (b or {}).get("code", "")})
        out["relocated"] = {"from": roll.get("bin_id"), "to": scan["bin_id"]}
        movements.append({"qty": 0.0, "type": "cycle_count_relocation",
                          "extra": {"from_bin_id": roll.get("bin_id"), "to_bin_id": scan["bin_id"]}})
    diff = 0.0
    if "qty_diff" in kinds:
        diff = round(float(scan["measured_qty"]) - float(scan["live_qty"]), 4)
        upd["length_remaining"] = round(float(scan["measured_qty"]), 4)
        if upd["length_remaining"] <= EPS:
            upd["status"] = "consumed"
    journal = None
    if abs(diff) > EPS:
        cost = float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
        out.update({"qty_diff": diff, "value": round(diff * cost, 2), "journal_id": None})
        movements.append({"qty": diff, "type": "cycle_count_adjustment", "extra": {}})
        journal = {"amount_signed": round(diff * cost, 2),
                   "label": f"Opname {session.get('name', session['id'])} · {roll.get('roll_no')}"}
    return await _apply_op(session, key, {"length_remaining": scan["live_qty"], "bin_id": scan["live_bin_id"]}, upd,
                           {"ref": ref, "roll": roll, "movements": movements, "journal": journal,
                            "rebuild": abs(diff) > EPS, "result": out},
                           "Roll berubah bersamaan — hitung ulang roll ini.")


async def write_off_missing(session: Dict[str, Any], e: Dict[str, Any], actor: str) -> Dict[str, Any]:
    """OPS-01 — roll hilang yang SUDAH dihitung ulang → keluar stok + jurnal kerugian (sekali per roll).
    AUD-WMS-01: memakai catatan operasi bertahap yang sama dengan `apply_scan`."""
    ref = f"{session['id']}:missing:{e['roll_id']}"
    key = f"missing_{e['roll_id']}"
    resumed = await _resume_op(session, key, "Roll berubah sejak snapshot — tidak dihapus, hitung ulang.")
    if resumed is not None:
        return resumed
    cas = {"id": e["roll_id"], "warehouse_id": session["warehouse_id"], "bin_id": e["bin_id"],
           "length_remaining": e["qty"], "status": {"$in": PHYSICAL_ROLL_STATUSES}}
    roll = await db.inventory_rolls.find_one(cas, {**ROLL_FIELDS, "length_reserved": 1, "active_movement": 1})
    if not roll:
        return {"status": "recount", "message": "Roll berubah sejak snapshot — tidak dihapus, hitung ulang.", "at": now_iso()}
    if roll.get("status") in ("reserved", "committed", "picked", "packed") or float(roll.get("length_reserved") or 0) > EPS \
            or (roll.get("active_movement") or {}).get("id"):
        return {"status": "exception", "message": "Roll hilang masih dialokasikan/dipesan atau sedang dipindah — "
                "lepas alokasi pesanan dulu, baru dihapus.", "at": now_iso()}
    roll = {k: v for k, v in roll.items() if k in ROLL_FIELDS}
    cost = float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
    value = -round(float(e["qty"]) * cost, 2)
    upd = {"length_remaining": 0.0, "status": "consumed", "updated_at": now_iso(),
           "lost_in_count": {"session_id": session["id"], "qty": e["qty"], "by": actor, "at": now_iso()}}
    op = {"ref": ref, "roll": roll, "rebuild": True,
          "movements": [{"qty": -float(e["qty"]), "type": "cycle_count_write_off", "extra": {"qty_rolls": -1}}],
          "journal": {"amount_signed": value,
                      "label": f"Opname {session.get('name', session['id'])} · hilang {roll.get('roll_no')}"},
          "result": {"status": "applied", "written_off": e["qty"], "value": value, "journal_id": None,
                     "at": now_iso(), "by": actor}}
    return await _apply_op(session, key, {"warehouse_id": session["warehouse_id"], "bin_id": e["bin_id"],
                                          "length_remaining": e["qty"]}, upd, op, "Roll berubah bersamaan — tidak dihapus.")


async def create_found_roll(session: Dict[str, Any], scan: Dict[str, Any], spec: Dict[str, Any], actor: str,
                            zero_cost_reason: str) -> Dict[str, Any]:
    """OPS-01 — kode tak dikenal → roll baru (produk & pemilik ditetapkan penyetuju) + jurnal surplus."""
    from services import gl_service as gl
    from services import stock_count_service as scs
    from services.roll_service import create_inbound_roll
    qty = float(spec.get("qty") or scan.get("measured_qty") or 0)
    cost, basis = await scs.surplus_unit_cost(spec["product_id"], session["warehouse_id"], spec["owner_entity_id"])
    if cost <= 0 and not zero_cost_reason:
        return {"status": "exception", "message": "Tidak ada biaya acuan — isi alasan biaya nol.", "at": now_iso()}
    # AUD-WMS-01 — identitas roll deterministik per (sesi, baris scan): retry sesudah gangguan (mis. jurnal gagal)
    # mengembalikan roll yang SAMA, bukan membuat roll kedua; jurnal idempoten per source_id.
    rid = "roll_" + hashlib.sha1(f"{session['id']}:found:{scan['id']}".encode()).hexdigest()[:12]
    roll = await create_inbound_roll(spec["product_id"], session["warehouse_id"], spec["owner_entity_id"], round(qty, 2),
                                     roll_id=rid, bin_id=scan["bin_id"], acquired_via="cycle_count_found", ref_id=session["id"],
                                     created_by=actor, unit_cost=cost, lot=f"OPN-{session['id'][-8:].upper()}",
                                     lot_source="adjustment", lot_source_ref={"type": "cycle_count_found", "session_id": session["id"], "code": scan["code"]})
    await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"opname_found_code": scan["code"]}})
    src = f"{session['id']}:found:{scan['id']}"
    je = await gl.post_cycle_count_variance(source_id=src, entity_id=spec["owner_entity_id"],
                                            amount_signed=round(qty * cost, 2),
                                            label=f"Opname {session.get('name', session['id'])} · ditemukan {scan['code']}")
    if not je:   # sudah diposting pada percobaan sebelumnya
        je = await db.journal_entries.find_one({"source_type": "cycle_count_variance", "source_id": src,
                                                "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
    return {"status": "applied", "new_roll_id": roll["id"], "new_roll_no": roll.get("roll_no"), "qty": qty, "unit_cost": cost,
            "cost_basis": basis, "value": round(qty * cost, 2), "journal_id": (je or {}).get("id"), "at": now_iso(), "by": actor}
