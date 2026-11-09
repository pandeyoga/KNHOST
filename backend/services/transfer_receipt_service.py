"""P03 (IMP-26/27) + sisa P02 — transfer terkait SO, penerimaan AKTUAL per roll, exception, cek ulang aturan tujuan.

- Roll berkomitmen SO dipindah tanpa reservasi kedua (`transfer_ref`), komitmen tetap selama perjalanan.
- Penerimaan per roll (CAS, idempoten): hanya roll yang benar-benar diterima menjadi stok fisik tujuan.
- Aturan gudang tujuan dievaluasi ULANG saat terima; pelanggaran = exception terkontrol (supervisor + alasan → hold).
- Exception (hilang, roll salah, rusak, aturan) ber-PIC/alasan; "Selesai" hanya bila tidak ada roll di perjalanan.
- PREP-D2 — gate IN V2 gedung bermode gate memanggil `receive` per lintasan (aktor = gate, CAS per roll idempoten);
  transfer selesai menutup sesi dokumen gate (`gate_txn_service.safe_close`).
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso
from services import placement_rules as pr
from services import roll_state as _rs   # FIX-10 (SSOT-1) — satu penulis status roll
from services.roll_service import (held_cas, owned_by_transfer, rebuild_balance, so_still_open,
                                   transfer_held_rolls)

DONE = {"completed", "rejected", "cancelled"}
EXC_KINDS = {"missing", "wrong_roll", "damaged", "rule_violation", "other"}


def _roll_ids(transfer: Dict[str, Any]) -> List[str]:
    return [x["roll_id"] for it in transfer.get("items") or [] for x in it.get("rolls") or [] if x.get("roll_id")]


SO_HELD = ("reserved", "committed")   # roll berkomitmen ke SO (sebelum / sesudah dikonfirmasi)
# Hanya SO yang tugas gudangnya BELUM mulai diambil: alokasi & tugas "created" ikut pindah ke gudang tujuan.
SO_TRANSFERABLE = {"reserved", "waiting_approval", "approved", "confirmed", "waiting_stock"}

def _reason(text: str, label: str = "Alasan") -> str:
    t = (text or "").strip()
    if len(t) < 5:
        raise HTTPException(status_code=400, detail=f"{label} wajib diisi (minimal 5 karakter).")
    return t


# ─── Transfer terkait SO (IMP-26) ──────────────────────────────────────────────
async def so_options(source_warehouse_id: str, allowed: List[str]) -> List[Dict[str, Any]]:
    """SO yang punya roll berkomitmen (reserved) di gudang asal."""
    # Cek UI UAT v3 (S10) — roll SO terkonfirmasi berstatus "committed"; dulu hanya "reserved" → transfer pemenuhan SO tak pernah bisa dipakai.
    q: Dict[str, Any] = {"warehouse_id": source_warehouse_id, "status": {"$in": list(SO_HELD)},
                         "reserved_ref.type": "sales_order"}
    if allowed:
        q["owner_entity_id"] = {"$in": allowed}
    rows = await db.inventory_rolls.aggregate([
        {"$match": q}, {"$group": {"_id": "$reserved_ref.id", "rolls": {"$sum": 1}}}]).to_list(500)
    out = []
    for r in rows:
        so = await db.sales_orders.find_one({"id": r["_id"]}, {"_id": 0, "id": 1, "number": 1, "customer_name": 1,
                                                               "status": 1, "entity_id": 1})
        if so and so.get("status") in SO_TRANSFERABLE:
            out.append({**so, "rolls_here": r["rolls"]})
    return sorted(out, key=lambda s: s.get("number") or "")


async def so_rolls(so_id: str, source_warehouse_id: str) -> List[Dict[str, Any]]:
    rows = await db.inventory_rolls.find(
        {"reserved_ref.id": so_id, "warehouse_id": source_warehouse_id, "status": {"$in": list(SO_HELD)}},
        {"_id": 0}).to_list(2000)
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": list({r["product_id"] for r in rows})}},
                                                        {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}).to_list(500)}
    out = []
    for r in rows:
        busy = await _active_transfer_of(r)
        p = prods.get(r["product_id"], {})
        out.append({"roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"), "product_id": r["product_id"],
                    "sku": p.get("sku", ""), "product_name": p.get("name", ""), "unit": r.get("unit") or p.get("base_unit"),
                    "length": float(r.get("length_remaining") or 0), "grade": r.get("grade", "A"),
                    "in_transfer": busy.get("code") if busy else ""})
    return out


async def _active_transfer_of(roll: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tid = (roll.get("transfer_ref") or {}).get("id")
    if not tid:
        return None
    return await db.warehouse_transfers.find_one({"id": tid, "status": {"$nin": list(DONE)}}, {"_id": 0, "id": 1, "code": 1})


async def validate_so_link(so_id: str, owner: str) -> Dict[str, Any]:
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "id": 1, "number": 1, "status": 1, "entity_id": 1,
                                                        "customer_name": 1})
    if not so:
        raise HTTPException(status_code=404, detail="SO yang ditautkan tidak ditemukan.")
    if not await so_still_open(so_id):
        raise HTTPException(status_code=400, detail=f"SO {so.get('number')} sudah {so.get('status')} — tidak bisa dipenuhi lewat transfer.")
    if owner and so.get("entity_id") and so["entity_id"] != owner:
        raise HTTPException(status_code=400, detail=(
            f"Roll milik badan usaha lain dari SO {so.get('number')}. Pindah fisik tidak menggantikan jual-beli "
            "internal — buat transaksi antar-PT dulu."))
    return so


async def attach_committed_rolls(transfer_id: str, so_id: str, roll_ids: List[str], source_wh: str,
                                 product_id: str) -> List[Dict[str, Any]]:
    """Roll reserved untuk SO → ditandai milik transfer TANPA melepas/mengulang reservasi (CAS)."""
    out: List[Dict[str, Any]] = []
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "number": 1, "status": 1}) or {}
    if so.get("status") not in SO_TRANSFERABLE:
        raise HTTPException(status_code=409, detail=(
            f"SO {so.get('number', '')} sudah mulai diambil gudang — kirim dari gudang asal atau batalkan pengambilan dulu."))
    rows = await db.inventory_rolls.find({"id": {"$in": roll_ids}}, {"_id": 0}).to_list(len(roll_ids))
    by_id = {r["id"]: r for r in rows}
    try:
        for rid in roll_ids:
            r = by_id.get(rid)
            if not r or r.get("product_id") != product_id:
                raise HTTPException(status_code=409, detail="Sebagian roll tidak ditemukan untuk produk ini — muat ulang.")
            if r.get("status") not in SO_HELD or (r.get("reserved_ref") or {}).get("id") != so_id:
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} tidak (lagi) berkomitmen ke SO ini.")
            if r.get("warehouse_id") != source_wh:
                raise HTTPException(status_code=400, detail=f"Roll {r.get('roll_no')} tidak berada di gudang asal.")
            busy = await _active_transfer_of(r)
            if busy:
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} sudah ada di transfer {busy.get('code')}.")
            res = await db.inventory_rolls.update_one(
                {**held_cas(r), "transfer_ref": r.get("transfer_ref"), "active_movement": None},
                {"$set": {"transfer_ref": {"type": "wh_transfer", "id": transfer_id, "so_id": so_id}, "updated_at": now_iso()}})
            if not res.matched_count:
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} baru saja berubah — muat ulang.")
            out.append(r)
    except HTTPException:
        await db.inventory_rolls.update_many({"transfer_ref.id": transfer_id, "id": {"$in": [x["id"] for x in out]}},
                                             {"$set": {"transfer_ref": None}})
        raise
    return out


async def _rehome_allocation(so_id: str, roll: Dict[str, Any], dest: Dict[str, Any], transfer: Dict[str, Any]) -> None:
    """Komitmen SO ikut pindah alamat: baris alokasi & tugas outbound (belum mulai) pindah ke gudang tujuan."""
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "allocations": 1})
    allocs = list((so or {}).get("allocations") or [])
    src = next((a for a in allocs if any(x.get("roll_id") == roll["id"] for x in a.get("rolls") or [])), None)
    if not src or src.get("warehouse_id") == dest["id"]:
        return
    entry = next(x for x in src["rolls"] if x.get("roll_id") == roll["id"])
    src["rolls"] = [x for x in src["rolls"] if x.get("roll_id") != roll["id"]]
    ln = float(entry.get("length") or roll.get("length_remaining") or 0)
    src["quantity"] = round(max(float(src.get("quantity") or 0) - ln, 0.0), 2)
    dst = next((a for a in allocs if a.get("product_id") == src["product_id"] and a.get("warehouse_id") == dest["id"]
                and a.get("owner_entity_id") == src.get("owner_entity_id") and a.get("via_transfer_id") == transfer["id"]), None)
    if not dst:
        dst = {**{k: v for k, v in src.items() if k not in ("id", "rolls", "quantity")}, "id": new_id("alloc"),
               "warehouse_id": dest["id"], "warehouse_name": dest.get("name", ""), "warehouse_city": dest.get("city", ""),
               "rolls": [], "quantity": 0.0, "via_transfer_id": transfer["id"],
               "allocation_explanation": f"Dipindah dari {src.get('warehouse_name', '')} lewat transfer {transfer.get('code')}."}
        allocs.append(dst)
    dst["rolls"].append(entry)
    dst["quantity"] = round(float(dst["quantity"]) + ln, 2)
    allocs = [a for a in allocs if a.get("rolls")]
    await db.sales_orders.update_one({"id": so_id}, {"$set": {"allocations": allocs, "updated_at": now_iso()},
                                                     "$addToSet": {"linked_transfer_ids": transfer["id"]}})
    src_task = await db.wms_tasks.find_one({"allocation_id": src["id"], "flow_type": "outbound", "status": "created"}, {"_id": 0})
    if not src_task:
        return
    left = round(float(src_task.get("quantity") or 0) - ln, 2)
    if left <= 0.01:
        await db.wms_tasks.update_one({"id": src_task["id"]}, {"$set": {"status": "cancelled", "quantity": 0.0,
                                      "cancel_reason": f"Roll dipindah ke {dest.get('name')} ({transfer.get('code')})",
                                      "updated_at": now_iso()}})
    else:
        await db.wms_tasks.update_one({"id": src_task["id"]}, {"$set": {"quantity": left, "updated_at": now_iso()}})
    got = await db.wms_tasks.find_one_and_update({"allocation_id": dst["id"], "flow_type": "outbound", "status": "created"},
                                                 [{"$set": {"quantity": {"$round": [{"$add": ["$quantity", ln]}, 2]},
                                                            "updated_at": now_iso()}}])
    if not got:
        await db.wms_tasks.insert_one({**src_task, "id": new_id("wms"), "allocation_id": dst["id"], "quantity": round(ln, 2),
                                       "picked_qty": 0.0, "shipped_qty": 0.0, "warehouse_id": dest["id"],
                                       "warehouse_name": dest.get("name", ""), "warehouse_city": dest.get("city", ""),
                                       "bin_id": "", "scan_log": [], "status": "created", "via_transfer_id": transfer["id"],
                                       "created_at": now_iso(), "updated_at": now_iso()})


# ─── Penerimaan aktual per roll (IMP-27) ───────────────────────────────────────
async def _exception(transfer_id: str, kind: str, actor: Dict[str, Any], **kw) -> Dict[str, Any]:
    exc = {"id": new_id("tex"), "kind": kind, "status": kw.pop("status", "open"), "roll_id": kw.pop("roll_id", ""),
           "roll_no": kw.pop("roll_no", ""), "code": kw.pop("code", ""), "reason": kw.pop("reason", ""),
           "evidence": kw.pop("evidence", ""), "by": actor.get("name", ""), "by_id": actor.get("id", ""),
           "at": now_iso(), **kw}
    await db.warehouse_transfers.update_one({"id": transfer_id}, {"$push": {"exceptions": exc}, "$set": {"updated_at": now_iso()}})
    return exc


def _open_exc(transfer: Dict[str, Any], kind: str, roll_id: str) -> Optional[Dict[str, Any]]:
    return next((e for e in transfer.get("exceptions") or [] if e.get("status") == "open" and e.get("kind") == kind
                 and e.get("roll_id") == roll_id), None)


async def _find_roll(transfer: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    ids = _roll_ids(transfer)
    key = (ref or "").strip()
    if not key:
        return None
    r = await db.inventory_rolls.find_one({"id": {"$in": ids}, "$or": [{"id": key}, {"roll_no": key}]}, {"_id": 0})
    if r:
        return r
    tag = await db.rfid_tags.find_one({"$or": [{"epc": key}, {"code": key}, {"tag_code": key}], "roll_id": {"$in": ids},
                                       "status": {"$in": ["active", "pending_print"]}},   # FIX-3b (RFID-2)
                                      {"_id": 0, "roll_id": 1})
    return await db.inventory_rolls.find_one({"id": tag["roll_id"]}, {"_id": 0}) if tag else None


# ─── FIX-5 (PREP-H §9) — memo SATU panggilan terima (dulu ±18 kueri per roll) ─────────────────────────────────
#: Saldo segmen (produk × gudang × PT) dibangun ulang tiap N roll mendarat + di akhir panggilan (dulu 2× PER ROLL,
#: masing-masing membaca SEMUA roll segmen + menghitung ulang semua lot segmen). Batas N menjaga saldo basi bila
#: proses mati di tengah tetap kecil (roll sudah pindah, saldo menyusul pada rebuild segmen berikutnya).
REBUILD_EVERY = 100
TAG_LIVE = ["active", "pending_print"]   # FIX-3b (RFID-2) — sama dengan `_find_roll`


class _ReceiptMemo:
    """Roll transfer, produk, pelanggaran aturan gudang tujuan, status SO, tahap journey tujuan — dibaca SEKALI per
    panggilan `receive`; segmen saldo yang tersentuh dikumpulkan lalu dibangun ulang per `REBUILD_EVERY` roll.
    Tidak ada cache lintas permintaan (SSOT tetap dokumen roll): CAS per roll tetap memutuskan."""

    def __init__(self, transfer: Dict[str, Any], dest: Dict[str, Any]):
        self.transfer, self.dest = transfer, dest
        self.ids = _roll_ids(transfer)
        self.idset = set(self.ids)
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.by_ref: Dict[str, str] = {}          # ref (roll_no / EPC / kode tag) → roll_id
        self.products: Dict[str, Dict[str, Any]] = {}
        self.viol: Dict[Any, List[str]] = {}
        self.so_open: Dict[str, bool] = {}
        self.stage: Optional[str] = None
        self.segments: set = set()
        self.landed_since_flush = 0

    async def prefetch(self, refs: List[str]) -> None:
        keys = [k for k in dict.fromkeys((r or "").strip() for r in refs) if k]
        direct = [k for k in keys if k in self.idset]
        if direct:
            async for r in db.inventory_rolls.find({"id": {"$in": direct}}, {"_id": 0}):
                self.by_id[r["id"]] = r
        rest = [k for k in keys if k not in self.by_id]
        if rest and self.ids:
            async for r in db.inventory_rolls.find({"roll_no": {"$in": rest}, "id": {"$in": self.ids}}, {"_id": 0}):
                self.by_id.setdefault(r["id"], r)
                self.by_ref.setdefault(r.get("roll_no"), r["id"])
        rest = [k for k in rest if k not in self.by_ref]
        if rest and self.ids:
            tag_rolls: List[str] = []
            async for t in db.rfid_tags.find({"$or": [{"epc": {"$in": rest}}, {"code": {"$in": rest}},
                                                      {"tag_code": {"$in": rest}}],
                                              "roll_id": {"$in": self.ids}, "status": {"$in": TAG_LIVE}},
                                             {"_id": 0, "roll_id": 1, "epc": 1, "code": 1, "tag_code": 1}):
                for k in (t.get("epc"), t.get("code"), t.get("tag_code")):
                    if k in rest:
                        self.by_ref.setdefault(k, t["roll_id"])
                tag_rolls.append(t["roll_id"])
            need = [r for r in dict.fromkeys(tag_rolls) if r not in self.by_id]
            if need:
                async for r in db.inventory_rolls.find({"id": {"$in": need}}, {"_id": 0}):
                    self.by_id[r["id"]] = r
        pids = list({r.get("product_id") for r in self.by_id.values() if r.get("product_id")})
        if pids:
            async for p in db.products.find({"id": {"$in": pids}}, {"_id": 0}):
                self.products[p["id"]] = p

    def find_roll(self, ref: str) -> Optional[Dict[str, Any]]:
        key = (ref or "").strip()
        if not key:
            return None
        rid = key if key in self.by_id else self.by_ref.get(key)
        return self.by_id.get(rid) if rid else None

    def remember(self, roll: Dict[str, Any]) -> None:
        """Keadaan roll sesudah ditulis panggilan ini (baris ganda di permintaan yang sama → "sudah")."""
        self.by_id[roll["id"]] = roll

    async def product(self, pid: str) -> Dict[str, Any]:
        if pid not in self.products:
            self.products[pid] = await db.products.find_one({"id": pid}, {"_id": 0}) or {}
        return self.products[pid]

    async def violations(self, roll: Dict[str, Any], prod: Dict[str, Any]) -> List[str]:
        # `warehouse_violations` hanya bergantung pada gudang tujuan, pemilik, produk & grade roll.
        key = (roll.get("owner_entity_id"), roll.get("product_id"), roll.get("grade", "A"))
        if key not in self.viol:
            self.viol[key] = await pr.warehouse_violations(self.dest, roll, prod)
        return list(self.viol[key])

    async def so_still_open(self, so_id: str) -> bool:
        if so_id not in self.so_open:
            self.so_open[so_id] = await so_still_open(so_id)
        return self.so_open[so_id]

    async def journey_stage(self) -> str:
        if self.stage is None:
            from services import inbound_qc_common as _iqc
            self.stage = await _iqc.initial_journey_stage(self.dest["id"])
        return self.stage

    async def touched(self, product_id: str, warehouses: set, owner: str) -> None:
        for w in warehouses:
            self.segments.add((product_id, w, owner))
        self.landed_since_flush += 1
        if self.landed_since_flush >= REBUILD_EVERY:
            await self.flush()

    async def flush(self) -> None:
        segs, self.segments, self.landed_since_flush = self.segments, set(), 0
        for pid, wid, own in sorted(segs, key=lambda s: tuple(str(x) for x in s)):
            await rebuild_balance(pid, wid, own)


async def _land(roll: Dict[str, Any], transfer: Dict[str, Any], dest: Dict[str, Any], status_kind: str,
                actor: Dict[str, Any], memo: Optional[_ReceiptMemo] = None) -> Optional[Dict[str, Any]]:
    """in_transit_transfer → fisik di tujuan (CAS). None bila sudah diproses (retry).
    FIX-5 — dengan `memo`: status SO & tahap journey dibaca sekali per panggilan; saldo dibangun ulang per kelompok
    roll (`_ReceiptMemo.flush`), bukan dua kali per roll. Tanpa `memo` perilaku lama (dipakai jalur lain)."""
    so_id = (roll.get("transfer_ref") or {}).get("so_id")
    keep = bool(so_id) and (await memo.so_still_open(so_id) if memo else await so_still_open(so_id))
    # komitmen SO kembali ke status asalnya (reserved / committed) saat tiba
    # FIX-3a (B2a STM-IN-04) — "diterima ditahan" (pelanggaran aturan + pengecualian supervisor) memakai SATU
    # representasi tahan: status `blocked` + `hold{held, prev_status}` (dilepas lewat `roll_hold_service.release_roll`).
    # Dulu status `hold` tersendiri tanpa jalan keluar (dan `hold` di tempat lain berarti soft-hold pesanan).
    status = {"damaged": "damaged", "hold": "blocked"}.get(status_kind) or (
        (roll.get("transfer_prior_status") if roll.get("transfer_prior_status") in SO_HELD else "reserved") if keep else "available")
    src_wh = roll["warehouse_id"]
    _set: Dict[str, Any] = {
        "warehouse_id": dest["id"], "status": status, "reserved_ref": roll.get("reserved_ref") if keep else None,
        "transfer_ref": None, "transfer_prior_status": None, "bin_id": None, "bin_code": "",
        "last_transfer": {"ref_id": transfer["id"], "code": transfer.get("code"), "from_warehouse_id": src_wh,
                          "date": now_iso(), "received_by": actor.get("name"), "outcome": status_kind},
        "updated_at": now_iso()}
    if status_kind == "hold":
        _set["hold"] = {"held": True, "reason": f"Diterima dengan pengecualian aturan gudang (transfer {transfer.get('code')})",
                        "by": actor.get("name", ""), "at": now_iso(), "prev_status": "available", "source": "transfer_rule"}
    # FIX-3a (B2a FLW-IN-19) — tahap fisik dihitung ulang sesuai PERAN gudang tujuan (transit → menunggu putaway,
    # gudang simpan → tersimpan); dulu `journey` tidak disentuh (data lama: kosong).
    try:
        if memo:
            stage = await memo.journey_stage()
        else:
            from services import inbound_qc_common as _iqc
            stage = await _iqc.initial_journey_stage(dest["id"])
        _set["journey"] = {**(roll.get("journey") or {}), "stage": stage,
                           "routing": (roll.get("journey") or {}).get("routing") or "store", "updated_at": now_iso(),
                           "via": "transfer_in"}
    except Exception:  # noqa: BLE001 — tahap fisik tidak boleh menggagalkan penerimaan
        pass
    cas = {k: v for k, v in held_cas(roll).items() if k not in ("id", "status")}
    if not await _rs.transition(
            roll["id"], status, from_=roll["status"], reason=f"transfer {transfer.get('code') or ''} diterima ({status_kind})",
            actor=actor.get("name", ""), action="transfer_receive",
            ref={"type": "warehouse_transfer", "id": transfer["id"], "no": transfer.get("code", "")},
            extra_filter=cas, extra_set={k: v for k, v in _set.items() if k not in ("status", "updated_at")},
            rebuild=False):   # saldo: memo.flush / rebuild di bawah (kedua gudang)
        return None
    if memo:
        memo.remember({**roll, **_set})
    await db.rfid_tags.update_many({"roll_id": roll["id"], "status": "active"},
                                   {"$set": {"warehouse_id": dest["id"], "updated_at": now_iso()}})
    qty = round(float(roll.get("length_remaining") or 0), 2)
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": dest["id"],
        "owner_entity_id": roll["owner_entity_id"], "movement_type": "transfer_in", "quantity": qty,
        "unit": roll.get("unit", "meter"), "lot": roll.get("lot", ""), "batch": roll.get("batch", ""),
        "roll_id": roll["id"], "qty_rolls": 1, "receipt_outcome": status_kind, "by": actor.get("name"),
        "source_document": f"transfer_{transfer.get('code')}", "timestamp": now_iso()})
    if memo:
        await memo.touched(roll["product_id"], {src_wh, dest["id"]}, roll["owner_entity_id"])
    else:
        for w in {src_wh, dest["id"]}:
            await rebuild_balance(roll["product_id"], w, roll["owner_entity_id"])
    if keep and status in SO_HELD:
        await _rehome_allocation(so_id, roll, dest, transfer)
    return {**roll, "warehouse_id": dest["id"], "status": status, "bin_id": None}


async def _refresh_status(transfer_id: str, actor_name: str = "") -> Dict[str, Any]:
    t = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    in_transit = await transfer_held_rolls(transfer_id, ["in_transit_transfer"])
    received = await db.inventory_rolls.count_documents({"last_transfer.ref_id": transfer_id})
    if t["status"] == "returning":
        # FIX-3b (FLW-OUT-11) — semua roll sudah diterima kembali di asal → `cancelled` (basis returned_to_source);
        # penanda `transfer_prior_status` dibersihkan oleh `_land`.
        if not in_transit:
            from services import status_history as _sh
            t = await db.warehouse_transfers.find_one_and_update(
                {"id": transfer_id, "status": "returning"},
                {"$set": {"status": "cancelled", "cancelled_at": now_iso(),
                          "cancelled_by": (t.get("return_requested") or {}).get("by", actor_name),
                          "cancelled_reason": (t.get("return_requested") or {}).get("reason", ""),
                          "completion_basis": "returned_to_source", "updated_at": now_iso()},
                 "$push": {"status_history": _sh.entry("cancelled", user=actor_name, note="semua roll kembali ke asal")}},
                projection={"_id": 0}, return_document=True) or t
            if t.get("status") == "cancelled":
                from services import gate_txn_service as _gt
                await _gt.safe_close("wh_transfer", transfer_id, ("out", "in"), "transfer_cancelled")
        return t
    if t["status"] in ("dispatched", "partially_received"):
        new = "completed" if not in_transit else ("partially_received" if received else "dispatched")
        if new == "completed" and not received and await db.inventory_rolls.count_documents(
                {"returned_from_transfer.ref_id": transfer_id}):
            # FIX-3a (B2a FLW-IN-10, keputusan D10) — 0 roll diterima, semua kembali ke asal → `returned` (selaras PA),
            # bukan `completed` "actual_receipt" yang menyesatkan laporan transfer selesai.
            new = "returned"
        upd = {"status": new, "updated_at": now_iso()}
        if new == "completed":
            upd.update({"completed_at": now_iso(), "completion_basis": "actual_receipt"})
        elif new == "returned":
            upd.update({"returned_at": now_iso(), "completion_basis": "all_returned"})
        _ops: Dict[str, Any] = {"$set": upd}
        if new != t["status"]:   # FIX-3a (STM-IN-07) — jejak status seragam (bentuk SSOT)
            from services import status_history as _sh
            _ops["$push"] = {"status_history": _sh.entry(new, user=actor_name, note="penerimaan transfer")}
        t = await db.warehouse_transfers.find_one_and_update({"id": transfer_id, "status": t["status"]}, _ops,
                                                             projection={"_id": 0}, return_document=True) or t
        if new in ("completed", "returned") and t.get("status") == new:
            # PREP-D2 (K-RFID-10) — transfer selesai diterima → sesi gate OUT (asal) & IN (tujuan) dinilai; roll yang
            # tidak terbaca gate & tidak dilengkapi jalur lain → antrean periksa. Best-effort, tidak menggagalkan terima.
            from services import gate_txn_service as _gt
            await _gt.safe_close("wh_transfer", transfer_id, ("out", "in"), "transfer_completed")
    return t


async def receive(transfer: Dict[str, Any], body: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    if transfer.get("transfer_kind") == "inter_entity":
        raise HTTPException(status_code=400, detail="Transfer antar badan usaha tidak memindah fisik — tidak ada penerimaan.")
    if transfer["status"] not in ("dispatched", "partially_received", "returning"):
        raise HTTPException(status_code=400, detail="Penerimaan hanya untuk transfer yang sudah dikirim (dalam perjalanan).")
    if transfer["status"] == "returning":
        # FIX-3b (FLW-OUT-11, K-B2b-03) — transfer dibatalkan di jalan: roll DITERIMA KEMBALI di gudang ASAL.
        transfer = {**transfer, "dest_warehouse_id": transfer["source_warehouse_id"], "_returning": True}
    dest = await db.warehouses.find_one({"id": transfer["dest_warehouse_id"]}, {"_id": 0})
    node = pr.resolve_bin(dest, body.bin_id) if body.bin_id else None
    if body.bin_id and not node:
        raise HTTPException(status_code=400, detail="Bin/staging tujuan tidak ada di gudang tujuan.")
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal
    await _rfz.assert_transfer_movable(transfer, "in", to_bin_id=((node or {}).get("bin") or {}).get("id", ""))
    override = (body.rule_exception_reason or "").strip()
    if override:
        pr.assert_supervisor(actor, "memberi pengecualian aturan gudang saat terima")
        _reason(override, "Alasan pengecualian aturan")
    results: List[Dict[str, Any]] = []
    # Validasi SEMUA baris dulu — tidak ada roll yang mendarat bila satu baris tidak sah.
    for ln in body.lines:
        if ln.outcome not in ("received", "damaged"):
            raise HTTPException(status_code=400, detail="Kondisi tiba hanya 'received' (baik) atau 'damaged' (rusak).")
        if ln.outcome == "damaged":
            _reason(ln.note, "Keterangan kerusakan")
    # FIX-5 (PREP-H §9) — roll/produk/aturan dibaca sekali untuk semua baris; saldo dibangun ulang per kelompok
    # (`_ReceiptMemo.flush`, juga saat galat di tengah). Urutan, CAS per roll, dan hasil per baris tidak berubah.
    memo = _ReceiptMemo(transfer, dest)
    await memo.prefetch([ln.roll_id or ln.code for ln in body.lines])
    try:
        await _receive_lines(transfer, body, actor, dest, node, override, memo, results)
    finally:
        await memo.flush()
    await db.warehouse_transfers.update_one({"id": transfer["id"]}, {"$push": {"receipt_events": {
        "id": new_id("trc"), "by": actor.get("name"), "at": now_iso(), "note": (body.note or "")[:300],
        "bin_id": body.bin_id or "", "results": [{k: r.get(k) for k in ("ref", "roll_id", "result")} for r in results]}}})
    t = await _refresh_status(transfer["id"], actor.get("name", ""))
    # FIX-3a (B2a FLW-IN-19) — roll tersedia yang tiba di gedung TRANSIT → draf Putaway Order otomatis (K-GDG-10),
    # sama dengan barang lepas QC. Best-effort & idempoten per penerimaan.
    _avail = [r["roll_id"] for r in results if r.get("result") == "received" and r.get("status") == "available"]
    if _avail:
        try:
            from services import inbound_qc_common as _iqc
            pd = await _iqc.auto_draft_after_release(
                _avail, {"type": "transfer_in", "id": f"{transfer['id']}:{len(transfer.get('receipt_events') or [])}",
                         "number": transfer.get("code", "")}, actor.get("name", ""))
            if pd:
                return {"results": results, "transfer_status": t["status"], "summary": await summary(t), "putaway_draft": pd}
        except Exception:  # noqa: BLE001
            pass
    return {"results": results, "transfer_status": t["status"], "summary": await summary(t)}


async def _cas_lost(roll_id: str, transfer_id: str) -> Dict[str, str]:
    """FIX-5 — CAS mendarat kalah (roll berubah sesudah dibaca di awal panggilan): klasifikasi dari keadaan SEGAR,
    sama dengan yang dihasilkan pembacaan per baris dulu."""
    r = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0}) or {}
    if (r.get("last_transfer") or {}).get("ref_id") == transfer_id and r.get("status") != "in_transit_transfer":
        return {"result": "already", "message": "Sudah diproses petugas lain (tidak menambah stok)."}
    if r.get("status") != "in_transit_transfer" or not owned_by_transfer(r, transfer_id):
        return {"result": "not_in_transit", "message": f"Roll berstatus {r.get('status')} — bukan dalam perjalanan transfer ini."}
    return {"result": "already", "message": "Sudah diproses petugas lain (tidak menambah stok)."}


async def _receive_lines(transfer: Dict[str, Any], body: Any, actor: Dict[str, Any], dest: Dict[str, Any],
                         node: Optional[Dict[str, Any]], override: str, memo: _ReceiptMemo,
                         results: List[Dict[str, Any]]) -> None:
    for ln in body.lines:
        ref = ln.roll_id or ln.code
        roll = memo.find_roll(ref)
        if not roll:
            exc = await _exception(transfer["id"], "wrong_roll", actor, code=ref, reason=ln.note or "Roll tidak ada di transfer ini",
                                   status="open")
            results.append({"ref": ref, "result": "wrong_roll", "exception_id": exc["id"],
                            "message": "Roll ini bukan bagian transfer — tidak dimasukkan ke stok."})
            continue
        base = {"ref": ref, "roll_id": roll["id"], "roll_no": roll.get("roll_no")}
        if (roll.get("last_transfer") or {}).get("ref_id") == transfer["id"] and roll.get("status") != "in_transit_transfer":
            results.append({**base, "result": "already", "message": "Sudah diterima sebelumnya (tidak menambah stok)."})
            continue
        if roll.get("status") != "in_transit_transfer" or not owned_by_transfer(roll, transfer["id"]):
            results.append({**base, "result": "not_in_transit", "message": f"Roll berstatus {roll.get('status')} — bukan dalam perjalanan transfer ini."})
            continue
        prod = await memo.product(roll["product_id"])
        kind = "damaged" if ln.outcome == "damaged" else "received"
        viol = await memo.violations(roll, prod)
        if viol and kind == "received":
            if not override:
                if not _open_exc(transfer, "rule_violation", roll["id"]):
                    await _exception(transfer["id"], "rule_violation", actor, roll_id=roll["id"], roll_no=roll.get("roll_no"),
                                     reason=" | ".join(viol[:3]), system=True)
                results.append({**base, "result": "blocked_rules", "violations": viol,
                                "message": "Aturan gudang tujuan menolak roll ini — tetap dalam perjalanan sampai supervisor memutuskan."})
                continue
            kind = "hold"
        landed = await _land(roll, transfer, dest, kind, actor, memo=memo)
        if not landed:
            results.append({**base, **await _cas_lost(roll["id"], transfer["id"])})
            continue
        if kind == "damaged":
            await _exception(transfer["id"], "damaged", actor, roll_id=roll["id"], roll_no=roll.get("roll_no"),
                             reason=_reason(ln.note, "Keterangan kerusakan"), evidence=ln.evidence or "",
                             committed_so=(roll.get("transfer_ref") or {}).get("so_id") or "")
        if kind == "hold":
            for e in transfer.get("exceptions") or []:
                if e.get("status") == "open" and e.get("kind") == "rule_violation" and e.get("roll_id") == roll["id"]:
                    await _resolve_exc(transfer["id"], e["id"], "received_hold", override, actor)
            if not _open_exc(transfer, "rule_violation", roll["id"]):
                await _exception(transfer["id"], "rule_violation", actor, roll_id=roll["id"], roll_no=roll.get("roll_no"),
                                 reason=" | ".join(viol[:3]), status="resolved", resolution="received_hold",
                                 resolution_reason=override, resolved_by=actor.get("name"), resolved_at=now_iso())
        row = {**base, "result": kind, "status": landed["status"]}
        if node and landed["status"] not in ("damaged", "hold", "blocked"):
            from services.location_service import place_roll
            try:
                p = await place_roll(landed, dest, node, actor=actor, cas={"status": landed["status"]})
                row["bin_code"] = p["bin_code"]
            except HTTPException as exc:
                row["placement_error"] = exc.detail if isinstance(exc.detail, str) else (exc.detail or {}).get("message")
        results.append(row)


# ─── Exception & pemulihan ─────────────────────────────────────────────────────
async def _resolve_exc(transfer_id: str, exc_id: str, resolution: str, reason: str, actor: Dict[str, Any]) -> None:
    await db.warehouse_transfers.update_one(
        {"id": transfer_id, "exceptions.id": exc_id},
        {"$set": {"exceptions.$.status": "resolved", "exceptions.$.resolution": resolution,
                  "exceptions.$.resolution_reason": reason, "exceptions.$.resolved_by": actor.get("name"),
                  "exceptions.$.resolved_at": now_iso(), "updated_at": now_iso()}})


async def report(transfer: Dict[str, Any], body: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    if body.kind not in EXC_KINDS - {"rule_violation", "damaged"}:
        raise HTTPException(status_code=400, detail="Jenis exception: missing, wrong_roll, atau other.")
    if transfer["status"] not in ("dispatched", "partially_received"):
        raise HTTPException(status_code=400, detail="Exception penerimaan hanya untuk transfer dalam perjalanan.")
    reason = _reason(body.reason)
    roll = await _find_roll(transfer, body.roll_id) if body.roll_id else None
    if body.kind == "missing":
        if not roll or roll.get("status") != "in_transit_transfer":
            raise HTTPException(status_code=400, detail="Roll hilang harus roll transfer ini yang masih dalam perjalanan.")
        if _open_exc(transfer, "missing", roll["id"]):
            raise HTTPException(status_code=409, detail="Roll ini sudah dilaporkan hilang.")
    exc = await _exception(transfer["id"], body.kind, actor, roll_id=(roll or {}).get("id", ""),
                           roll_no=(roll or {}).get("roll_no", ""), code=body.code or "", reason=reason,
                           evidence=body.evidence or "")
    return {"exception": exc, "summary": await summary(await db.warehouse_transfers.find_one({"id": transfer["id"]}, {"_id": 0}))}


async def resolve(transfer: Dict[str, Any], exc_id: str, body: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    pr.assert_supervisor(actor, "menyelesaikan exception transfer")
    exc = next((e for e in transfer.get("exceptions") or [] if e["id"] == exc_id), None)
    if not exc or exc.get("status") != "open":
        raise HTTPException(status_code=404, detail="Exception terbuka tidak ditemukan.")
    reason = _reason(body.reason)
    if body.action == "return_to_source":
        roll = await db.inventory_rolls.find_one({"id": exc.get("roll_id")}, {"_id": 0}) if exc.get("roll_id") else None
        if not roll or roll.get("status") != "in_transit_transfer" or not owned_by_transfer(roll, transfer["id"]):
            raise HTTPException(status_code=400, detail="Roll exception ini tidak lagi dalam perjalanan.")
        so_id = (roll.get("transfer_ref") or {}).get("so_id")
        keep = bool(so_id) and await so_still_open(so_id)
        cas = {k: v for k, v in held_cas(roll).items() if k not in ("id", "status")}
        back = await _rs.transition(
            roll["id"], "reserved" if keep else "available", from_=roll["status"],
            reason=f"exception transfer: kembali ke gudang asal — {reason}", actor=actor.get("name", ""),
            action="transfer_return_to_source",
            ref={"type": "warehouse_transfer", "id": transfer["id"], "no": transfer.get("code", "")},
            extra_filter=cas, extra_set={"reserved_ref": roll.get("reserved_ref") if keep else None, "transfer_ref": None,
                                         "returned_from_transfer": {"ref_id": transfer["id"], "at": now_iso(),
                                                                    "reason": reason}},
            rebuild=False)   # saldo dibangun di bawah
        if back:
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
                "owner_entity_id": roll["owner_entity_id"], "movement_type": "transfer_cancelled",
                "quantity": round(float(roll.get("length_remaining") or 0), 2), "unit": roll.get("unit", "meter"),
                "lot": roll.get("lot", ""), "roll_id": roll["id"], "qty_rolls": 1, "by": actor.get("name"),
                "source_document": f"transfer_{transfer.get('code')}:kembali", "timestamp": now_iso()})
            await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll["owner_entity_id"])
    elif body.action != "close_note":
        raise HTTPException(status_code=400, detail="Tindakan: return_to_source atau close_note.")
    if body.action == "close_note" and exc["kind"] in ("missing", "rule_violation"):
        raise HTTPException(status_code=400, detail=(
            "Roll hilang/ditolak aturan tidak bisa ditutup dengan catatan saja — terima roll itu (dengan pengecualian) "
            "atau kembalikan ke gudang asal. Penghapusan stok hilang menunggu keputusan Finance (DEC-13)."))
    await _resolve_exc(transfer["id"], exc_id, body.action, reason, actor)
    t = await _refresh_status(transfer["id"], actor.get("name", ""))
    return {"transfer_status": t["status"], "summary": await summary(t)}


# ─── Ringkasan (sumber kebenaran = dokumen roll) ───────────────────────────────
async def summary(transfer: Dict[str, Any]) -> Dict[str, Any]:
    ids = _roll_ids(transfer)
    rolls = {r["id"]: r for r in await db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids) + 1)}
    refs = {x["roll_id"]: (it, x) for it in transfer.get("items") or [] for x in it.get("rolls") or []}
    rows, counts = [], {}
    for rid in ids:
        r = rolls.get(rid) or {}
        it, x = refs[rid]
        lt = r.get("last_transfer") or {}
        if r.get("status") == "in_transit_transfer" and owned_by_transfer(r, transfer["id"]):
            state = "in_transit"
        elif lt.get("ref_id") == transfer["id"]:
            state = {"damaged": "received_damaged", "hold": "received_hold"}.get(lt.get("outcome"), "received")
        elif (r.get("returned_from_transfer") or {}).get("ref_id") == transfer["id"]:
            state = "returned"
        elif owned_by_transfer(r, transfer["id"]) and r.get("status") == "reserved":
            state = "waiting_dispatch"
        else:
            state = "legacy_completed" if transfer["status"] == "completed" else "released"
        counts[state] = counts.get(state, 0) + 1
        rows.append({"roll_id": rid, "roll_no": x.get("roll_no"), "lot": x.get("lot"), "length": x.get("length"),
                     "unit": it.get("unit"), "sku": it.get("sku"), "product_name": it.get("product_name"), "state": state,
                     "status": r.get("status"), "warehouse_id": r.get("warehouse_id"), "bin_code": r.get("bin_code") or "",
                     "committed_so": (x.get("committed_so") or ""), "received_by": lt.get("received_by") if lt.get("ref_id") == transfer["id"] else ""})
    legacy = transfer["status"] == "completed" and not transfer.get("receipt_events") and transfer.get("transfer_kind") != "inter_entity"
    dest = await db.warehouses.find_one({"id": transfer.get("dest_warehouse_id")}, {"_id": 0}) or {}
    bins = [{"id": n["bin"]["id"], "code": n["bin"].get("code", ""), "path": n["path"],
             "function": pr.effective(dest, n)["function"]} for n in pr.flatten_nodes(dest)] if dest else []
    bins.sort(key=lambda b: (b["function"] != "staging", b["code"]))
    exc = transfer.get("exceptions") or []
    return {"rolls": rows, "counts": counts, "total": len(ids),
            "exceptions": exc, "open_exceptions": sum(1 for e in exc if e.get("status") == "open"),
            "legacy_note": ("Transfer lama: hanya status 'Selesai' yang tercatat, tanpa bukti penerimaan per roll."
                            if legacy else ""),
            "receipt_events": transfer.get("receipt_events") or [], "dest_bins": bins[:300],
            "sales_order_id": transfer.get("sales_order_id") or "", "sales_order_number": transfer.get("sales_order_number") or ""}


# ─── Sisa P02: transfer antar badan usaha memakai evaluator yang sama ──────────
async def interco_violations(transfer: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ownership-in-place: barang tetap di gudangnya tetapi pemiliknya berganti → gudang itu wajib boleh
    dipakai badan usaha TUJUAN (shared/dedicated) dan lolos rules gudang."""
    out: List[Dict[str, Any]] = []
    whs: Dict[str, Any] = {}
    for it in transfer.get("items") or []:
        prod = await db.products.find_one({"id": it["product_id"]}, {"_id": 0}) or {}
        for x in it.get("rolls") or []:
            r = await db.inventory_rolls.find_one({"id": x["roll_id"]}, {"_id": 0})
            if not r:
                continue
            wid = r.get("warehouse_id")
            if wid not in whs:
                whs[wid] = await db.warehouses.find_one({"id": wid}, {"_id": 0}) or {}
            v = await pr.warehouse_violations(whs[wid], {**r, "owner_entity_id": transfer.get("dest_entity_id")}, prod)
            if v:
                out.append({"roll_id": r["id"], "roll_no": r.get("roll_no"), "warehouse": whs[wid].get("name", wid),
                            "violations": v})
    return out
