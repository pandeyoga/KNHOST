"""FIX-6 (keputusan pemilik 10 Nov 2026, D5 · audit B2a FLW-IN-09) — barang RETUR PENJUALAN MASUK STOK saat dipindai.

Dulu pindai "diterima" di gudang hanya mencatat lokasi di dokumen retur (`roll_locations`); roll tetap `delivered`
("di pelanggan") sampai retur DISELESAIKAN (settle) — berhari-hari stok fisik di gudang tidak terlihat dan opname
menyebutnya surplus. Sekarang pindai diterima langsung membuat roll menjadi KARANTINA RETUR di gudang pindai:

* status `quarantine` + `qc_status = "return_received"` → di angka stok FIX-2 (`stock_figures`) masuk kelompok
  "Ditahan / QC" (bukan Tersedia, tidak bisa dipesan/dijual) — tidak ada rumus stok baru;
* NILAI NOL (`unit_cost`/`base_unit_cost` = 0): nilai & jurnal (Dr Persediaan / Cr HPP) TETAP ditetapkan saat
  penyelesaian (settle) — subledger persediaan (Σ roll × biaya) tetap sama dengan GL 1-1300 sepanjang waktu, dan WAC
  tidak terseret (roll tanpa biaya tidak ikut rata-rata);
* settle MENILAI roll yang sama (`finalize`, dipanggil `return_identity_service.restock_identity`) — tidak ada roll
  kedua, mutasi masuk kedua, atau jurnal ganda; koreksi qty hasil QC dicatat sebagai mutasi `return_qc_adjust`.

Roll utuh (status `delivered`, klaim ≥ panjang terkirim) = roll yang SAMA (id/nomor/tag RFID tetap; keadaan "di
pelanggan" disimpan di `return_restore`); klaim sebagian = roll ANAK bernomor induk (lot retur `RTN-<nomor retur>`).

TABEL TRANSISI `return_intake.state` (daftar-izin; tulisan CAS pada state asal):

    —/delivered ─pindai terima─▶ received   (karantina retur, nilai 0, mutasi `return_quarantine_in`)
    received    ─tiba di gudang lain─▶ received   (pindah gudang: mutasi keluar/masuk, saldo kedua gudang)
    received    ─settle masuk stok─▶ valued     (nilai WAC + jurnal Nota Kredit; qty = hasil QC)
    received    ─retur ditolak / roll ditolak / outcome tanpa stok / dipecah cutloss─▶ reversed
                 (roll utuh kembali "di pelanggan", anak dihapus; mutasi `return_reversal_out`)
    valued      ─koreksi penyelesaian per roll yang membuka retur lagi─▶ received (nilai 0 bersama jurnal yang dibalik)
    valued      ─reverse penyelesaian (retur batal)─▶ reversed (jalur lama `restore_identity_roll` / hapus anak)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import new_id, now_iso
from db import db
from services import roll_state as _rs   # FIX-10 (SSOT-1) — satu penulis status roll
from services.tolerances import QTY_EPS

_log = logging.getLogger(__name__)

KEY = "return_intake"
QC_STATUS = "return_received"
TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "receive": {"from": ("",), "to": "received"},
    "move": {"from": ("received",), "to": "received"},
    "value": {"from": ("received",), "to": "valued"},
    "reverse": {"from": ("received",), "to": "reversed"},
    "unvalue": {"from": ("valued",), "to": "received"},
}
# Field roll "di pelanggan" yang dipulihkan bila karantina retur dibalik (roll utuh).
RESTORE_KEYS = ("status", "warehouse_id", "owner_entity_id", "length", "length_remaining", "grade", "condition",
                "defects", "inspection", "unit_cost", "base_unit_cost", "landed_cost_total", "reserved_ref",
                "earmarked_for", "committed_to", "origin_type", "origin_ref", "qc_status", "journey", "acquired",
                "delivered_at", "bin_id")
# Field template settle yang ikut ke roll ANAK saat dinilai (lot retur, jejak asal barang, perolehan).
_CHILD_TEMPLATE_SKIP = {"id", "roll_no", "warehouse_id", "created_at", "journey", "length", "length_initial",
                        "length_remaining", "status", "qc_status", "rfid_tag_id", "unit"}


def state_of(roll: Optional[Dict[str, Any]]) -> str:
    return str(((roll or {}).get(KEY) or {}).get("state") or "")


def is_unvalued(roll: Optional[Dict[str, Any]]) -> bool:
    """Roll karantina retur yang BELUM dinilai (sebelum settle) — tidak boleh dilepas/dipindah kepemilikan/diretur."""
    return state_of(roll) == "received" and (roll or {}).get("status") == "quarantine"


def _assert(action: str, current: str) -> None:
    spec = TRANSITIONS[action]
    if current not in spec["from"]:
        raise ValueError(f"Karantina retur: aksi '{action}' tidak sah dari keadaan '{current or '—'}'.")


async def find_open(return_id: str, source_roll_id: str) -> Optional[Dict[str, Any]]:
    """Roll karantina retur (belum dinilai) milik retur ini untuk roll klaim `source_roll_id`."""
    return await db.inventory_rolls.find_one(
        {f"{KEY}.return_id": return_id, f"{KEY}.source_roll_id": source_roll_id, f"{KEY}.state": "received",
         "status": "quarantine"}, {"_id": 0})


def _claims(ret: Dict[str, Any]) -> Dict[str, Tuple[int, Dict[str, Any], float]]:
    out: Dict[str, Tuple[int, Dict[str, Any], float]] = {}
    for i, it in enumerate(ret.get("items") or []):
        q = it.get("roll_qtys") or {}
        for rid in it.get("roll_ids") or []:
            out[rid] = (i, it, float(q.get(rid) or 0))
    return out


async def _stage_for(warehouse_id: str) -> str:
    from services import inbound_qc_common as _iqc
    return await _iqc.initial_journey_stage(warehouse_id)


async def _movement(roll: Dict[str, Any], ret: Dict[str, Any], mtype: str, direction: str, qty: float,
                    warehouse_id: str, notes: str, doc_no: str = "") -> None:
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": roll.get("product_id"), "warehouse_id": warehouse_id,
        "owner_entity_id": roll.get("owner_entity_id") or ret.get("entity_id", ""), "type": mtype,
        "movement_type": mtype, "direction": direction, "quantity": round(abs(float(qty or 0)), 2),
        "unit": roll.get("unit") or "", "roll_id": roll["id"], "qty_rolls": 1, "lot": roll.get("lot", ""),
        "ref_type": "sales_return", "ref_id": ret["id"], "source_document": doc_no or ret.get("number", ret["id"]),
        "notes": notes, "timestamp": now_iso()})


async def _rebuild(segs: Iterable[Tuple[str, str, str]]) -> None:
    from services.roll_service import rebuild_balance
    for pid, wid, eid in {s for s in segs if s[0] and s[1]}:
        await rebuild_balance(pid, wid, eid)


async def receive(ret: Dict[str, Any], roll_ids: List[str], warehouse_id: str, actor: str,
                  doc_no: str = "") -> Dict[str, Any]:
    """Pindai DITERIMA → roll klaim masuk karantina retur di gudang pindai (idempoten per roll)."""
    claims = _claims(ret)
    owner = ret.get("entity_id", "")
    stage = await _stage_for(warehouse_id)
    now = now_iso()
    done: List[Dict[str, Any]] = []
    segs = set()
    for rid in dict.fromkeys(roll_ids or []):
        if rid not in claims:
            continue
        if await db.inventory_rolls.find_one({f"{KEY}.return_id": ret["id"], f"{KEY}.source_roll_id": rid,
                                              f"{KEY}.state": {"$in": ["received", "valued"]}}, {"_id": 0, "id": 1}):
            continue   # sudah masuk karantina retur (pindai ulang / percobaan ulang)
        _assert("receive", "")
        _i, item, claim = claims[rid]
        orig = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
        if not orig:
            continue
        base = {"return_id": ret["id"], "return_number": ret.get("number", ""), "source_roll_id": rid,
                "state": "received", "qty": 0.0, "warehouse_id": warehouse_id, "doc_no": doc_no,
                "received_at": now, "received_by": actor}
        live = {"status": "quarantine", "qc_status": QC_STATUS, "warehouse_id": warehouse_id, "owner_entity_id": owner,
                "bin_id": None, "unit_cost": 0.0, "base_unit_cost": 0.0, "landed_cost_total": 0.0,
                "reserved_ref": None, "earmarked_for": None, "committed_to": None, "origin_type": "return",
                "origin_ref": ret["id"], "return_id": ret["id"], "condition": item.get("condition", "ok"),
                "journey": {"stage": stage, "routing": "store", "updated_at": now}, "updated_at": now}
        whole = (orig.get("status") == "delivered"
                 and (claim <= 0 or claim >= float(orig.get("length_remaining") or 0) - QTY_EPS))
        if whole:
            qty = float(orig.get("length_remaining") or 0)
            snap = {k: orig.get(k) for k in RESTORE_KEYS}
            res = await _rs.transition(
                rid, live["status"], from_="delivered", actor=actor, action="return_receive",
                reason=f"retur {ret.get('number', '')} diterima — karantina retur",
                ref={"type": "sales_return", "id": ret["id"], "no": ret.get("number", "")},
                extra_set={**{k: v for k, v in live.items() if k not in ("status", "updated_at")},
                           KEY: {**base, "mode": "whole", "qty": round(qty, 2)}, "returned_identity": True,
                           "return_restore": snap, "acquired": {"via": "return", "ref_id": ret["id"], "date": now}},
                push={"acquired_history": orig.get("acquired") or {}}, rebuild=False, return_doc=True)   # saldo: segs
            if not res:
                continue   # roll berubah bersamaan — penyelesaian tetap memakai jalur lama (tanpa jurnal ganda)
            doc = res
        else:
            qty = round(claim, 2)
            if qty <= 0:
                continue
            from services import lot_service as _lots
            from services.return_identity_service import _insert_return_child
            import domain_registry as _dr
            prod = await db.products.find_one({"id": orig.get("product_id")}, {"_id": 0}) or {}
            lot = await _lots.resolve_or_create(
                product_id=orig.get("product_id"), owner_entity_id=owner, warehouse_id=warehouse_id,
                lot_code=f"RTN-{ret.get('number', '')}", source="return",
                source_ref={"type": "sales_return", "id": ret["id"], "number": ret.get("number", "")},
                status="karantina", actor="Retur Jual")
            child = {**live, "id": new_id("roll"), "product_id": orig.get("product_id"),
                     "unit": orig.get("unit") or prod.get("base_unit") or "meter", "grade": orig.get("grade") or "A",
                     "defects": [], "length": qty, "length_initial": qty, "length_remaining": qty,
                     "lot": lot.get("lot_number", ""), "lot_id": lot.get("id", ""), "parent_roll_id": rid,
                     "root_roll_id": orig.get("root_roll_id") or rid, "rfid_tag_id": None, "is_remnant": False,
                     "tracking_mode": orig.get("tracking_mode") or "barcode",
                     "acquired": {"via": "return", "ref_id": ret["id"], "date": now},
                     "return_history": list(orig.get("return_history") or []),
                     **_dr.roll_domain_snapshot(prod),
                     KEY: {**base, "mode": "child", "qty": qty}, "created_at": now}
            doc = await _insert_return_child(child, orig.get("roll_no") or "")
        await _movement(doc, ret, "return_quarantine_in", "in", doc[KEY]["qty"], warehouse_id,
                        f"Retur {ret.get('number', '')} dipindai diterima → karantina retur (nilai saat penyelesaian)",
                        doc_no)
        segs.add((doc.get("product_id"), warehouse_id, owner))
        done.append({"roll_id": doc["id"], "roll_no": doc.get("roll_no", ""), "source_roll_id": rid,
                     "mode": doc[KEY]["mode"], "qty": doc[KEY]["qty"]})
    await _rebuild(segs)
    return {"received": done}


async def move(ret: Dict[str, Any], roll_ids: List[str], warehouse_id: str, actor: str, doc_no: str = "") -> Dict[str, Any]:
    """Pindai TIBA di gudang lain (kirim → tiba sebelum settle) → roll karantina retur ikut pindah gudang."""
    stage = await _stage_for(warehouse_id)
    moved, segs = [], set()
    for rid in dict.fromkeys(roll_ids or []):
        r = await find_open(ret["id"], rid)
        if not r or r.get("warehouse_id") == warehouse_id:
            continue
        _assert("move", state_of(r))
        res = await db.inventory_rolls.find_one_and_update(
            {"id": r["id"], "status": "quarantine", f"{KEY}.state": "received", "warehouse_id": r.get("warehouse_id")},
            {"$set": {"warehouse_id": warehouse_id, "bin_id": None, f"{KEY}.warehouse_id": warehouse_id,
                      "journey": {"stage": stage, "routing": "store", "updated_at": now_iso()}, "updated_at": now_iso()}},
            projection={"_id": 0}, return_document=True)
        if not res:
            continue
        qty = float(r.get("length_remaining") or 0)
        await _movement(r, ret, "return_quarantine_out", "out", qty, r.get("warehouse_id", ""),
                        f"Retur {ret.get('number', '')}: karantina retur dikirim ke gudang lain", doc_no)
        await _movement(res, ret, "return_quarantine_in", "in", qty, warehouse_id,
                        f"Retur {ret.get('number', '')}: karantina retur tiba", doc_no)
        segs |= {(r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id", "")),
                 (r.get("product_id"), warehouse_id, r.get("owner_entity_id", ""))}
        moved.append(r["id"])
    await _rebuild(segs)
    return {"moved": moved}


async def reverse(ret: Dict[str, Any], source_roll_ids: Optional[List[str]], actor: str, why: str) -> Dict[str, Any]:
    """Balik karantina retur yang BELUM dinilai (semua roll retur ini, atau hanya roll klaim tertentu).
    Roll utuh → keadaan "di pelanggan" dipulihkan (`return_restore`); roll anak → dihapus. Idempoten."""
    q: Dict[str, Any] = {f"{KEY}.return_id": ret["id"], f"{KEY}.state": "received", "status": "quarantine"}
    if source_roll_ids is not None:
        if not source_roll_ids:
            return {"reversed": []}
        q[f"{KEY}.source_roll_id"] = {"$in": list(source_roll_ids)}
    now = now_iso()
    out, segs = [], set()
    async for r in db.inventory_rolls.find(q, {"_id": 0}):
        _assert("reverse", state_of(r))
        info = r.get(KEY) or {}
        if info.get("mode") == "whole":
            snap = dict(r.get("return_restore") or {})
            hist = list(r.get("acquired_history") or [])
            back_to = snap.pop("status", None) or "delivered"
            snap.pop("updated_at", None)
            n = await _rs.transition(
                r["id"], back_to, from_="quarantine", actor=actor, action="return_receive_reverse",
                reason=f"karantina retur {ret.get('number', '')} dibalik: {why}",
                ref={"type": "sales_return", "id": ret["id"], "no": ret.get("number", "")},
                extra_filter={f"{KEY}.state": "received"},
                extra_set={**snap, "acquired_history": hist[:-1] if hist else [], f"{KEY}.state": "reversed",
                           f"{KEY}.reversed_at": now, f"{KEY}.reversed_by": actor, f"{KEY}.reverse_reason": why},
                unset=["return_restore", "returned_identity", "return_id"], rebuild=False)   # saldo: segs
        else:
            n = (await db.inventory_rolls.delete_one({"id": r["id"], "status": "quarantine",
                                                    f"{KEY}.state": "received"})).deleted_count
        if not n:
            continue
        await _movement(r, ret, "return_reversal_out", "out", float(r.get("length_remaining") or 0),
                        r.get("warehouse_id", ""), f"Karantina retur {ret.get('number', '')} dibalik: {why}")
        segs.add((r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id", "")))
        out.append({"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "source_roll_id": info.get("source_roll_id"),
                    "mode": info.get("mode")})
    await _rebuild(segs)
    if out:
        _log.info("[return-intake] %s: %d roll karantina retur dibalik (%s)", ret.get("number"), len(out), why)
    return {"reversed": out}


async def finalize(ret: Dict[str, Any], intake: Dict[str, Any], live: Dict[str, Any], template: Dict[str, Any],
                   hist: Dict[str, Any], actual: float, now: str) -> Optional[Tuple[Dict[str, Any], float, float]]:
    """Settle MENILAI roll karantina retur: qty = hasil QC, grade/cacat QC, biaya WAC (template settle), riwayat retur.
    → (dokumen roll, qty, qty saat pindai) atau None bila roll berubah bersamaan (pemanggil memakai jalur lama)."""
    _assert("value", state_of(intake))
    info = intake.get(KEY) or {}
    # FIX-10 — `status` tidak ditulis ulang di sini: CAS di bawah sudah menjamin karantina (status tidak berubah).
    upd = {k: v for k, v in live.items() if k not in ("warehouse_id", "journey", "status")}
    if info.get("mode") == "child":
        upd = {**{k: v for k, v in template.items() if k not in _CHILD_TEMPLATE_SKIP}, **upd}
        upd["length_initial"] = actual
    upd.update({"length": actual, "length_remaining": actual, "qc_status": template.get("qc_status") or "pending_release",
                f"{KEY}.state": "valued", f"{KEY}.valued_at": now, f"{KEY}.valued_qty": actual, "updated_at": now})
    upd.pop(KEY, None)
    res = await db.inventory_rolls.find_one_and_update(
        {"id": intake["id"], "status": "quarantine", f"{KEY}.state": "received"},
        {"$set": upd, "$push": {"return_history": hist}}, projection={"_id": 0}, return_document=True)
    if not res:
        return None
    return res, actual, float(intake.get("length_remaining") or info.get("qty") or 0)


async def unvalue(roll: Dict[str, Any], actor: str, why: str) -> bool:
    """Koreksi penyelesaian per roll yang MEMBUKA retur lagi: roll tetap karantina retur (barang masih di gudang),
    nilainya kembali nol bersama jurnal Nota Kredit yang dibalik pemanggil."""
    if state_of(roll) != "valued":
        return False
    _assert("unvalue", "valued")
    hist = list(roll.get("return_history") or [])
    if hist and hist[-1].get("return_id") == (roll.get(KEY) or {}).get("return_id"):
        hist = hist[:-1]
    res = await db.inventory_rolls.update_one(
        {"id": roll["id"], "status": "quarantine", f"{KEY}.state": "valued"},
        {"$set": {"unit_cost": 0.0, "base_unit_cost": 0.0, "landed_cost_total": 0.0, "qc_status": QC_STATUS,
                  "return_history": hist, f"{KEY}.state": "received", f"{KEY}.unvalued_at": now_iso(),
                  f"{KEY}.unvalued_by": actor, f"{KEY}.unvalue_reason": why, "updated_at": now_iso()}})
    return bool(res.modified_count)


def warehouse_of_roll(ret: Dict[str, Any], roll_id: str) -> str:
    loc = (ret.get("roll_locations") or {}).get(roll_id) or {}
    return loc.get("warehouse_id", "") if loc.get("stage") in ("received", "arrived") else ""
