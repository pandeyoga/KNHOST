"""Roll service (Fase 0.5) — Roll-as-SSOT inventory engine.

Implementasi fondasi KN_15:
- `inventory_rolls` = SSOT fisik (1 dokumen = 1 roll). Prefix `roll_`.
- `inventory_balances` = PROYEKSI yang di-rebuild dari rolls (key 3-bagian:
  product_id + warehouse_id + owner_entity_id), bucket DETAIL (KN_15 §3.4).
- Reservasi terjadi di LEVEL ROLL (atomic find_one_and_update available→reserved),
  owner-scoped (roll hanya boleh dijual entitas pemiliknya).

Catatan: alokasi penuh (configurable policy + mixed-lot confirmation UI +
inter-company transfer) adalah Fase 1. Di sini fondasi: owner-scoped + FEFO +
single-warehouse preference + split roll saat reservasi parsial.
"""
from typing import Any, Dict, List, Optional, Tuple
import re
import logging
from fastapi import HTTPException
from pymongo import ReturnDocument
from db import db
from core_utils import now_iso, new_id, to_cents, DEFAULT_ENTITY_ID
from schemas import WAREHOUSE_PRIORITY
from services import movement_label_service as _mlabel   # E5.3/E-9 — nama singkat badan usaha
logger = logging.getLogger(__name__)

# ── INV-ROLL-01 — SATU sumber nomor roll ─────────────────────────────────────
# MASALAH YANG DISELESAIKAN (terukur pada data demo 2026-08-18, 59 roll):
#   Nomor roll dibuat di SEMBILAN tempat dengan EMPAT cara berbeda, dan tiga di
#   antaranya bisa menghasilkan nomor yang sama untuk kain yang BERBEDA:
#     1. `generate_rolls_from_balances` memakai penghitung LOKAL (`seq={"n":0}`)
#        → setiap pemanggilan memulai lagi dari `RL-00001`.
#     2. Penerimaan gudang memakai `count_documents({})+1` → begitu ada roll yang
#        dihapus/di-consume, atau ada roll ber-prefix lain (`RTN-`), nomornya
#        menabrak nomor yang sudah dipakai.
#     3. Potongan roll (cut/split) menyalin dokumen induk apa adanya
#        (`dict(roll)`) sehingga potongan MEWARISI nomor induknya.
#   Hasil terukur: 3 nomor dipakai oleh 10 roll — termasuk `RL-00002` yang
#   dipegang DUA badan usaha berbeda (KSC 140 yard & Kanda 7 yard) dan `RL-00042`
#   yang dipakai 4 roll. Operator yang memindai/mencari "RL-00002" tidak bisa tahu
#   kain mana yang ia pegang, dan nomor pada label fisik berhenti menjadi identitas.
#   Tak ada satu pun error/uji yang gagal karena nomor tak pernah dijaga unik.
ROLL_NO_PREFIX = "RL-"
_ROLL_SEQ_KEY = {"entity_id": "_global", "doc_type": "ROLL"}


async def next_roll_no(prefix: str = ROLL_NO_PREFIX, width: int = 5) -> str:
    """Nomor roll berikutnya dari sequence ATOMIK bersama (`number_sequences`).

    Deletion-safe (tidak menghitung dokumen) dan aman terhadap penerimaan paralel
    (`$inc` atomik), berbeda dari `count_documents()+1` yang dipakai sebelumnya.
    """
    key = dict(_ROLL_SEQ_KEY, prefix=prefix)
    q = {k: key[k] for k in ("entity_id", "doc_type")}
    q["prefix"] = prefix
    if not await db.number_sequences.find_one(q):
        # Inisialisasi sekali dari nomor tertinggi yang SUDAH ada supaya nomor baru
        # tidak menabrak data lama (termasuk data yang di-seed).
        top = 0
        pat = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        async for d in db.inventory_rolls.find(
                {"roll_no": {"$regex": f"^{re.escape(prefix)}[0-9]+$"}},
                {"_id": 0, "roll_no": 1}):
            m = pat.match(str(d.get("roll_no") or ""))
            if m:
                top = max(top, int(m.group(1)))
        await db.number_sequences.update_one(
            q, {"$setOnInsert": {**q, "last_no": top, "created_at": now_iso()}}, upsert=True)
    seq = await db.number_sequences.find_one_and_update(
        q, {"$inc": {"last_no": 1}, "$set": {"updated_at": now_iso()}},
        return_document=ReturnDocument.AFTER)
    return f"{prefix}{seq['last_no']:0{width}d}"


async def child_roll_no(parent_no: str) -> str:
    """Nomor untuk POTONGAN roll: `RL-00002-1`, `RL-00002-2`, …

    Potongan adalah kain FISIK baru (induknya tetap ada dengan panjang berkurang),
    jadi ia butuh label sendiri. Nomornya sengaja MEWARISI nomor induk sebagai awalan
    supaya asal potongan tetap terbaca di rak tanpa membuka aplikasi.
    """
    base = (parent_no or "").strip()
    if not base:
        return await next_roll_no()
    n = await db.inventory_rolls.count_documents(
        {"roll_no": {"$regex": f"^{re.escape(base)}-[0-9]+$"}}) + 1
    for _ in range(200):
        cand = f"{base}-{n}"
        if not await db.inventory_rolls.find_one({"roll_no": cand}, {"_id": 1}):
            return cand
        n += 1
    return await next_roll_no()


async def insert_child_roll(child: Dict[str, Any], parent: Dict[str, Any]) -> Dict[str, Any]:
    """Simpan POTONGAN roll dengan nomor & satuannya SENDIRI (INV-ROLL-01).

    SATU pintu untuk semua jalur cut/split (reservasi parsial, kirim sebagian,
    transfer sebagian, pindah bucket, keputusan QC). Sebelum ini setiap jalur
    memanggil `insert_one(dict(child))` sendiri — sembilan salinan yang semuanya
    lupa memberi nomor baru.
    """
    doc = dict(child)
    doc.pop("_id", None)
    # WM-02/WM-05 — reservasi panjang & klaim perpindahan milik INDUK, tidak ikut ke potongan.
    for k in ("length_reservations", "length_reserved", "active_movement"):
        doc.pop(k, None)
    if doc.get("status") != "available":
        doc["earmarked_for"] = None  # pegging hanya bermakna pada roll available (INV roll-pegging)
    doc["roll_no"] = await child_roll_no(parent.get("roll_no") or "")
    # P-1 (INV-RFID-01) — potongan adalah BENDA FISIK BARU: tidak mewarisi tag RFID induk.
    # Ia muncul di /rfid/untagged-rolls sampai gudang menempel tag sendiri.
    doc["rfid_tag_id"] = None
    if not doc.get("unit"):
        doc["unit"] = parent.get("unit") or "meter"
    # KN-B17 — jejak induk: biaya masuk (landed cost) yang datang SETELAH roll dipecah
    # harus ikut mendarat di potongannya (lihat landed_cost_service.apply_allocations).
    # AX-07 — parent LANGSUNG selalu roll yang dipotong (salinan dict(parent) membawa kakek)
    doc["parent_roll_id"] = parent.get("id")
    doc["root_roll_id"] = parent.get("root_roll_id") or parent.get("id")
    parent_w = _split_weight(doc, parent)
    # WM-01 — potongan bersamaan dapat memilih nomor yang sama; ulangi dengan nomor baru supaya
    # induk yang sudah dikurangi tidak kehilangan potongannya (DuplicateKey = stok hilang).
    from pymongo.errors import DuplicateKeyError
    for _ in range(20):
        try:
            await db.inventory_rolls.insert_one(dict(doc))
            await _set_parent_weight(parent, parent_w)
            return doc
        except DuplicateKeyError as exc:
            if "roll_no" not in str(exc):
                raise
            doc["roll_no"] = await child_roll_no(parent.get("roll_no") or "")
    doc["roll_no"] = await next_roll_no()
    await db.inventory_rolls.insert_one(dict(doc))
    await _set_parent_weight(parent, parent_w)
    return doc


def _split_weight(doc: Dict[str, Any], parent: Dict[str, Any]) -> Optional[float]:
    """W2-019 — konservasi berat saat split: hasil timbang induk TIDAK disalin utuh ke potongan.
    Potongan mendapat estimasi proporsional panjang (provenance tercatat); sisa tetap di induk."""
    pw = float(parent.get("weight_kg") or 0)
    plen = float(parent.get("length_remaining") or 0)
    clen = float(doc.get("length_remaining") or 0)
    if pw <= 0 or plen <= 0 or clen <= 0 or clen >= plen:
        return None
    cw = round(pw * clen / plen, 3)
    doc["weight_kg"] = cw
    doc["weight_provenance"] = {"type": "estimated_proportional", "from_roll_id": parent.get("id"),
                                "parent_weight_kg": pw, "parent_length": plen}
    if isinstance(doc.get("secondary_measures"), dict) and "kg" in doc["secondary_measures"]:
        doc["secondary_measures"] = {**doc["secondary_measures"], "kg": cw}
    return round(pw - cw, 3)


async def _set_parent_weight(parent: Dict[str, Any], weight: Optional[float]) -> None:
    if weight is None:
        return
    s: Dict[str, Any] = {"weight_kg": weight}
    if isinstance(parent.get("secondary_measures"), dict) and "kg" in parent["secondary_measures"]:
        s["secondary_measures.kg"] = weight
        parent["secondary_measures"] = {**parent["secondary_measures"], "kg": weight}
    parent["weight_kg"] = weight
    await db.inventory_rolls.update_one({"id": parent.get("id")}, {"$set": s})


# ── Taksonomi status (KN_15 §3.4) ────────────────────────────────────────────
# Bucket FISIK di gudang (menyusun on_hand)
from services.tolerances import QTY_EPS  # KN-A13 — toleransi bersama

# KN-A11 — SATU definisi "PO masih terbuka / stok dalam perjalanan" untuk papan Stok/ATP,
# Fulfillment Wizard, dan stock_bucket. `waiting_approval` sengaja TIDAK dihitung (belum
# pasti dibeli); `receiving` dihitung karena sisa yang belum diterima memang masih di jalan.
OPEN_PO_STATUSES = ["pending", "created", "approved", "sent", "receiving", "partial"]   # G3 D4-SUPPLY-01

PHYSICAL_STATUS_TO_BUCKET = {
    "available": "available_qty",
    "reserved": "reserved_qty",
    "committed": "committed_qty",
    "picked": "picked_qty",
    "packed": "packed_qty",
    "hold": "hold_qty",            # F2 — soft hold / pending SO (fisik di gudang, tak tersedia)
    "wip": "wip_qty",             # F2 — work-in-progress (sedang diproses/produksi)
    "quarantine": "quarantine_qty",
    "blocked": "blocked_qty",
    "damaged": "damaged_qty",
}
# KN-C05 — SATU sumber "stok fisik di gudang" untuk saldo gudang, rekonsiliasi GL, dan WAC.
PHYSICAL_ROLL_STATUSES = list(PHYSICAL_STATUS_TO_BUCKET.keys())
# Bucket OWNED tapi FISIK di luar gudang (masuk owned, BUKAN on_hand/at-warehouse)
OFFSITE_OWNED_STATUS_TO_BUCKET = {
    "subcon": "subcon_qty",       # M2 — WIP-at-vendor (makloon): owned, fisik di vendor, bukan ATP/on_hand
}
# Bucket TRANSIT/PIPELINE (di luar gudang fisik)
TRANSIT_STATUS_TO_BUCKET = {
    "in_transit_inbound": "in_transit_inbound_qty",
    "in_transit_transfer": "in_transit_transfer_qty",
    "in_transit_intercompany": "in_transit_intercompany_qty",
    "in_transit_sales": "in_transit_sales_qty",
}
ALL_BUCKETS = (list(PHYSICAL_STATUS_TO_BUCKET.values())
               + list(TRANSIT_STATUS_TO_BUCKET.values())
               + list(OFFSITE_OWNED_STATUS_TO_BUCKET.values()))
# Status roll yang menahan reservasi sebuah order (untuk release)
ORDER_HELD_STATUSES = ["reserved", "committed", "picked", "packed", "in_transit_sales"]

MAX_AVAILABLE_ROLL_LEN = 150.0  # potong sintetis available jadi roll realistis


def _domain_snapshot(prod: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Snapshot domain (stage/fabric_type) produk → roll (Fase A PS-02, R7 SSOT).

    Delegasi ke `domain_registry.roll_domain_snapshot` agar tidak ada logika
    domain yang digandakan di service (INV-DOMAIN-05).
    """
    import domain_registry as dr
    return dr.roll_domain_snapshot(prod)


async def to_base_qty(prod: Dict[str, Any], qty: float, unit: Optional[str]) -> float:
    """KN-B16/B27 — kuantitas dalam `unit` → satuan dasar produk (identitas bila sama/kosong).
    Faktor dari master UoM (uom_service); konversi yang tidak tersedia → 400 (tidak diam-diam 1×)."""
    from services import uom_service as _u
    base = _u._norm(prod.get("base_unit") or "meter")
    u = _u._norm(unit or base)
    if not u or u == base:
        return float(qty)
    fixed = await _u.load_fixed_factors()
    return _u.convert(prod, float(qty), u, base, fixed, precision=4)


# ── Rebuild proyeksi balance dari rolls ──────────────────────────────────────

async def rebuild_balance(product_id: str, warehouse_id: str, owner_entity_id: str) -> Dict[str, Any]:
    """Hitung ulang satu segmen balance (product × warehouse × owner) dari rolls."""
    seg = {"product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id}
    # GN-13 — tiket rebuild diambil SEBELUM membaca roll; hasil hanya ditulis bila tidak ada
    # rebuild yang lebih baru sudah menulis (tidak ada snapshot lama menimpa yang baru).
    tk = await db.inventory_balances.find_one_and_update(
        seg, {"$inc": {"rebuild_ticket": 1}, "$setOnInsert": {"id": new_id("bal")}},
        upsert=True, projection={"_id": 0, "rebuild_ticket": 1}, return_document=ReturnDocument.AFTER)
    my_ticket = int(tk.get("rebuild_ticket") or 0)
    rolls = await db.inventory_rolls.find(seg, {"_id": 0}).to_list(None)  # GN-12 — tanpa cap
    buckets = {b: 0.0 for b in ALL_BUCKETS}
    roll_counts = {b: 0 for b in ALL_BUCKETS}  # F2 (UoM SSOT) — jumlah roll per bucket
    # KN-B16 — saldo dijumlahkan dalam SATUAN DASAR produk: roll ber-unit lain (data lama /
    # impor) dikonversi, bukan dijumlahkan mentah bersama meter.
    _prod = await db.products.find_one({"id": product_id}, {"_id": 0, "base_unit": 1, "sku": 1, "uom_conversion": 1,
                                                            "kg_per_meter": 1, "gsm": 1, "width_cm": 1}) or {}
    _base = (_prod.get("base_unit") or "meter").lower()
    unconvertible = 0
    for r in rolls:
        status = r.get("status")
        length = float(r.get("length_remaining", 0) or 0)
        _ru = (r.get("unit") or _base).lower()
        if _ru != _base and length:
            try:
                length = await to_base_qty(_prod, length, _ru)
            except Exception as exc:  # noqa: BLE001
                # GN-13 — jangan campur panjang native ke bucket base unit; tandai saldo tidak valid
                logger.warning("[rebuild_balance] roll %s unit %s≠%s tak terkonversi: %s", r.get("id"), _ru, _base, exc)
                unconvertible += 1
                continue
        bucket = (PHYSICAL_STATUS_TO_BUCKET.get(status)
                  or TRANSIT_STATUS_TO_BUCKET.get(status)
                  or OFFSITE_OWNED_STATUS_TO_BUCKET.get(status))
        raw_len = float(r.get("length_remaining", 0) or 0)
        if bucket == "available_qty" and float(r.get("length_reserved") or 0) > 0 and raw_len > 0:
            # WM-02 — panjang yang dipesan (belum dipotong) masuk bucket status reservasinya.
            ratio = length / raw_len
            for x in r.get("length_reservations") or []:
                b = PHYSICAL_STATUS_TO_BUCKET.get(x.get("status") or "reserved", "reserved_qty")
                q = float(x.get("qty") or 0) * ratio
                buckets[b] += q
                length -= q
        if bucket:
            buckets[bucket] += length
            if length > QTY_EPS:
                roll_counts[bucket] += 1
    physical = sum(buckets[b] for b in PHYSICAL_STATUS_TO_BUCKET.values())
    on_order = await _on_order_qty(product_id, warehouse_id, owner_entity_id)
    in_transit_total = sum(buckets[b] for b in TRANSIT_STATUS_TO_BUCKET.values())
    offsite_owned = sum(buckets[b] for b in OFFSITE_OWNED_STATUS_TO_BUCKET.values())  # M2 — WIP di vendor
    owned = physical + in_transit_total + offsite_owned
    incoming = on_order + buckets["in_transit_inbound_qty"]
    # KN-D11 — ATP memakai rumus tunggal atp_policy: available + incoming(horizon) − backorder aktif.
    from services import atp_policy as _atp
    pending_demand = await _atp.pending_backorder_qty(product_id, owner_entity_id, warehouse_id)
    atp = _atp.compute_atp(buckets["available_qty"], incoming, pending_demand)
    # F2 (UoM SSOT) — jumlah roll fisik di gudang & roll yang tersedia dijual
    on_hand_roll_count = sum(roll_counts[b] for b in PHYSICAL_STATUS_TO_BUCKET.values())
    doc = {
        "product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id,
        **buckets,
        "on_hand_qty": round(physical, 2),
        "in_transit_qty": round(in_transit_total, 2),  # legacy alias (total transit)
        "on_order_qty": round(on_order, 2),
        "owned_qty": round(owned, 2),
        "incoming_qty": round(incoming, 2),
        "atp_qty": round(atp, 2),
        "pending_demand_qty": pending_demand,
        "roll_count": roll_counts["available_qty"],   # F2 — jumlah roll TERSEDIA (siap dijual)
        "on_hand_roll_count": on_hand_roll_count,       # F2 — jumlah roll fisik di gudang
        "roll_counts": roll_counts,                     # F2 — detail count per-bucket
        "unconvertible_roll_count": unconvertible,
        "projection_valid": unconvertible == 0,
        "rebuild_applied": my_ticket,
        "updated_at": now_iso(),
    }
    # round bucket
    for b in ALL_BUCKETS:
        doc[b] = round(doc[b], 2)
    await db.inventory_balances.update_one(
        {**seg, "$or": [{"rebuild_applied": {"$lt": my_ticket}}, {"rebuild_applied": {"$exists": False}}]},
        {"$set": doc})
    # FASE C — agregat lot ikut disegarkan dari roll segmen ini (split/merge/kirim roll
    # terjadi di banyak jalur; satu hook di sini menjaga INV-LOT-04 tetap hijau).
    lot_ids = {r.get("lot_id") for r in rolls if r.get("lot_id")}
    if lot_ids:
        try:
            from services import lot_service as _lots
            await _lots.recompute_many(list(lot_ids))
        except Exception as exc:  # noqa: BLE001 — proyeksi lot tidak boleh menggagalkan stok
            logger.warning("[rebuild_balance] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return doc


async def _on_order_qty(product_id: str, warehouse_id: str, owner_entity_id: str) -> float:
    """Qty pipeline dari purchase_orders yang belum jadi roll (status belum receiving selesai)."""
    pos = await db.purchase_orders.find(
        {"warehouse_id": warehouse_id, "status": {"$in": OPEN_PO_STATUSES}},
        {"_id": 0, "items": 1, "entity_id": 1, "expected_delivery_date": 1},
    ).to_list(500)
    from services import atp_policy as _atp
    total = 0.0
    for po in pos:
        if po.get("entity_id") and po.get("entity_id") != owner_entity_id:
            continue
        if not _atp.within_horizon(po.get("expected_delivery_date")):   # KN-D11 — horizon ATP tunggal
            continue
        for it in po.get("items", []):
            if it.get("product_id") == product_id:
                # KN-B14 — sisa pipeline = dipesan − sudah diterima, dalam SATUAN DASAR
                # (base_quantity bila ada; qty PO ber-satuan pesanan dikonversi proporsional).
                ordered = float(it.get("quantity", it.get("qty", 0)) or 0)
                base_ordered = float(it.get("base_quantity") or 0) or ordered
                received = float(it.get("received_qty", 0) or 0)
                factor = (base_ordered / ordered) if ordered > 0 else 1.0
                total += max(base_ordered - received * factor, 0.0)
    return total


async def rebuild_all_balances() -> int:
    """Drop semua balances lalu rebuild dari rolls (segmen unik)."""
    segments = await db.inventory_rolls.aggregate([
        {"$group": {"_id": {"p": "$product_id", "w": "$warehouse_id", "o": "$owner_entity_id"}}}
    ]).to_list(100000)
    await db.inventory_balances.delete_many({})
    for s in segments:
        k = s["_id"]
        await rebuild_balance(k["p"], k["w"], k["o"])
    return len(segments)


async def backfill_roll_counts() -> int:
    """F2 (UoM SSOT) — set `roll_count`/`on_hand_roll_count` pada balance yang ada,
    DIHITUNG dari rolls TANPA menyentuh qty bucket (additive + idempotent).
    Aman dipanggil di seed maupun sebagai migrasi terpisah."""
    balances = await db.inventory_balances.find(
        {}, {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1}
    ).to_list(100000)
    updated = 0
    for b in balances:
        q = {"product_id": b["product_id"], "warehouse_id": b["warehouse_id"],
             "owner_entity_id": b["owner_entity_id"]}
        rolls = await db.inventory_rolls.find(
            q, {"_id": 0, "status": 1, "length_remaining": 1}
        ).to_list(10000)
        roll_counts = {bk: 0 for bk in ALL_BUCKETS}
        for r in rolls:
            length = float(r.get("length_remaining", 0) or 0)
            bucket = (PHYSICAL_STATUS_TO_BUCKET.get(r.get("status"))
                      or TRANSIT_STATUS_TO_BUCKET.get(r.get("status"))
                      or OFFSITE_OWNED_STATUS_TO_BUCKET.get(r.get("status")))
            if bucket and length > 0:
                roll_counts[bucket] += 1
        on_hand_roll_count = sum(roll_counts[bk] for bk in PHYSICAL_STATUS_TO_BUCKET.values())
        await db.inventory_balances.update_one(q, {"$set": {
            "roll_count": roll_counts["available_qty"],
            "on_hand_roll_count": on_hand_roll_count,
            "roll_counts": roll_counts,
        }})
        updated += 1
    return updated


# ── Synthetic migration: balances lama → rolls (idempotent) ──────────────────

async def _lot_for_segment(product_id: str, warehouse_id: str) -> str:
    mv = await db.inventory_movements.find_one(
        {"product_id": product_id, "warehouse_id": warehouse_id, "lot": {"$nin": [None, ""]}},
        {"_id": 0, "lot": 1}, sort=[("timestamp", 1)],
    )
    return (mv or {}).get("lot") or "LOT-MIGRATED"


async def generate_rolls_from_balances(created_by: str = "seed") -> Dict[str, int]:
    """Generate inventory_rolls sintetis dari balances lama (KN_15 §11).

    Idempotent: skip bila inventory_rolls sudah berisi. Backfill owner_entity_id
    pada balances & movements, lalu rolls dibuat per bucket, balances di-rebuild.
    """
    if await db.inventory_rolls.count_documents({}) > 0:
        return {"rolls": 0, "skipped": 1}

    # 1) Backfill owner_entity_id pada movements lama (default entitas utama)
    await db.inventory_movements.update_many(
        {"owner_entity_id": {"$exists": False}}, {"$set": {"owner_entity_id": DEFAULT_ENTITY_ID}}
    )

    # 2) Map alokasi SO aktif per (product, warehouse) → list (order_id, qty)
    active_orders = await db.sales_orders.find(
        {"status": {"$in": ["reserved", "waiting_approval", "approved", "confirmed"]}},
        {"_id": 0, "id": 1, "entity_id": 1, "allocations": 1},
    ).to_list(2000)
    alloc_map: Dict[tuple, List[Dict[str, Any]]] = {}
    for o in active_orders:
        for a in o.get("allocations", []):
            key = (a.get("product_id"), a.get("warehouse_id"))
            alloc_map.setdefault(key, []).append({
                "order_id": o["id"],
                "owner": o.get("entity_id") or DEFAULT_ENTITY_ID,
                "qty": float(a.get("quantity", a.get("qty", 0)) or 0),
            })

    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    balances = await db.inventory_balances.find({}, {"_id": 0}).to_list(10000)
    roll_docs: List[Dict[str, Any]] = []
    seq = {"n": 0}

    def _make_roll(product_id, warehouse_id, owner, lot, length, status, reserved_ref=None, grade="A"):
        seq["n"] += 1
        prod = products.get(product_id, {})
        return {
            "id": new_id("roll"),
            "product_id": product_id,
            "owner_entity_id": owner,
            "ownership_type": "internal",
            "consignor_ref": None,
            "warehouse_id": warehouse_id,
            "bin_id": None,
            "lot": lot,
            "dye_lot": lot,
            "batch": lot.replace("LOT", "BATCH") if lot else "",
            "roll_no": "",   # diisi setelah semua dokumen dibangun (lihat di bawah)
            "length_initial": round(float(length), 2),
            "length_remaining": round(float(length), 2),
            "unit": prod.get("base_unit", "meter"),
            "grade": _norm_grade(prod.get("grade", grade)),
            # Fase A · PS-01/PS-02 — snapshot domain produk saat roll dibuat
            **_domain_snapshot(prod),
            "status": status,
            "tracking_mode": "barcode",
            "earmarked_for": None,
            "secondary_measures": None,
            "location_type": "warehouse_bin",
            "reserved_ref": reserved_ref,
            "base_unit_cost": round(float(prod.get("harga_pokok") or 0), 4),
            "unit_cost": (round(float(prod.get("harga_pokok") or 0), 4) or None),
            "landed_cost_total": 0.0,
            "acquired": {"via": "initial", "ref_id": "seed", "date": now_iso()},
            "rfid_tag_id": None,
            "is_remnant": False,
            "created_at": now_iso(), "updated_at": now_iso(),
            "created_by": created_by, "created_by_name": "System Seed",
        }

    for b in balances:
        product_id = b.get("product_id")
        warehouse_id = b.get("warehouse_id")
        owner = b.get("owner_entity_id") or DEFAULT_ENTITY_ID
        lot = await _lot_for_segment(product_id, warehouse_id)
        reserved_qty = float(b.get("reserved_qty", 0) or 0)
        available_qty = float(b.get("available_qty", 0) or 0)
        blocked_qty = float(b.get("blocked_qty", 0) or 0)
        picked_qty = float(b.get("picked_qty", 0) or 0)

        # Reserved rolls — distribusi ke SO aktif (link reserved_ref) lalu sisa generik
        remaining_reserved = reserved_qty
        for alloc in alloc_map.get((product_id, warehouse_id), []):
            if remaining_reserved <= 0.01:
                break
            take = min(alloc["qty"], remaining_reserved)
            if take <= 0.01:
                continue
            roll_docs.append(_make_roll(
                product_id, warehouse_id, owner, lot, take, "reserved",
                reserved_ref={"type": "sales_order", "id": alloc["order_id"]},
            ))
            remaining_reserved -= take
        if remaining_reserved > 0.01:
            roll_docs.append(_make_roll(
                product_id, warehouse_id, owner, lot, remaining_reserved, "reserved",
                reserved_ref={"type": "seed", "id": "seed"},
            ))

        # Blocked / picked rolls (jika ada di seed)
        if blocked_qty > 0.01:
            roll_docs.append(_make_roll(product_id, warehouse_id, owner, lot, blocked_qty, "blocked"))
        if picked_qty > 0.01:
            roll_docs.append(_make_roll(product_id, warehouse_id, owner, lot, picked_qty, "picked"))

        # Available rolls — potong jadi roll realistis
        remaining_avail = available_qty
        while remaining_avail > 0.01:
            take = min(remaining_avail, MAX_AVAILABLE_ROLL_LEN)
            roll_docs.append(_make_roll(product_id, warehouse_id, owner, lot, take, "available"))
            remaining_avail -= take

    if roll_docs:
        # INV-ROLL-01 — nomor dari sequence ATOMIK bersama. Dulu memakai penghitung
        # LOKAL (`seq={"n":0}`) yang selalu mulai dari `RL-00001`, sehingga setiap
        # pemanggilan kedua menghasilkan nomor yang MENABRAK roll yang sudah ada
        # (terukur: `RL-00042` dipakai 4 roll berbeda pada data demo).
        for d in roll_docs:
            d["roll_no"] = await next_roll_no()
        await db.inventory_rolls.insert_many(roll_docs)
        # FASE C (D-10) — roll hasil generator WAJIB punya lot kelas satu juga.
        # Dipakai satu jalur yang sama dengan migrasi (tanpa logika ganda).
        try:
            from services import lot_migration as _lotm
            await _lotm.backfill_missing(actor="seed")
        except Exception as exc:  # noqa: BLE001 — jangan gagalkan seeding
            logger.warning("[_make_roll] efek samping gagal diabaikan: %s", exc)  # KN-C10

    n_segments = await rebuild_all_balances()
    return {"rolls": len(roll_docs), "segments": n_segments, "skipped": 0}


# ── Reservasi level-roll (owner-scoped, FEFO, single-warehouse preference) ────

NO_LENGTH_RESERVED = {"$not": {"$gt": 0}}


def free_length(r: Dict[str, Any]) -> float:
    """WM-02 — panjang bebas = sisa fisik − panjang yang dipesan (reservasi belum dipotong)."""
    return round(float(r.get("length_remaining") or 0) - float(r.get("length_reserved") or 0), 4)


async def _reserve_length(roll: Dict[str, Any], take: float, order_id: str,
                          ref: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """WM-02 — reservasi PANJANG di roll induk (bukan roll anak). Fisik tetap satu roll bertag
    induk; roll anak baru lahir saat `confirm_cut`. CAS atomik terhadap panjang bebas."""
    take = round(float(take), 2)
    rsv = {"id": new_id("rsv"), "ref": dict(ref or {"type": "sales_order", "id": order_id}), "qty": take,
           "status": "reserved", "created_at": now_iso()}
    doc = await db.inventory_rolls.find_one_and_update(
        {"id": roll["id"], "status": "available",
         "$expr": {"$gte": [{"$subtract": ["$length_remaining", {"$ifNull": ["$length_reserved", 0]}]},
                            take - QTY_EPS]}},
        [{"$set": {"length_reservations": {"$concatArrays": [{"$ifNull": ["$length_reservations", []]}, [rsv]]},
                   "length_reserved": {"$round": [{"$add": [{"$ifNull": ["$length_reserved", 0]}, take]}, 2]},
                   "updated_at": now_iso()}}],
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:
        return None
    return {**doc, "reservation_id": rsv["id"], "reserved_length": take}


def _recompute_reserved_stage():
    return {"$set": {"length_reserved": {"$round": [{"$sum": "$length_reservations.qty"}, 2]}}}


async def confirm_cut(roll_id: str, reservation_id: str, actual_length: Optional[float] = None,
                      waste: float = 0.0, actor: str = "", mode: str = "manual",
                      note: str = "") -> Dict[str, Any]:
    """WM-02 — konfirmasi potong fisik: induk dikurangi (aktual + waste), roll anak lahir dengan
    reservasi yang sama, tanpa tag (wajib tag/verifikasi identitas baru sebelum muat)."""
    parent = await db.inventory_rolls.find_one(
        {"id": roll_id, "length_reservations.id": reservation_id}, {"_id": 0})
    if not parent:
        # G3 V3-CUT-01 — percobaan sebelumnya sudah mengurangi induk tapi mati sebelum anak lahir → lanjutkan.
        resumed = await db.inventory_rolls.find_one({"id": roll_id, "pending_cut_ops.op": reservation_id}, {"_id": 0})
        if resumed:
            op = next(x for x in resumed["pending_cut_ops"] if x["op"] == reservation_id)
            return await _finish_cut(resumed, op)
        raise HTTPException(status_code=404, detail="Reservasi potong tidak ditemukan / sudah dipotong")
    rsv = next(x for x in parent["length_reservations"] if x["id"] == reservation_id)
    actual = round(float(rsv["qty"] if actual_length is None else actual_length), 2)
    waste = round(float(waste or 0), 2)
    if actual <= 0 or waste < 0:
        raise HTTPException(status_code=400, detail="Panjang aktual harus > 0 dan waste ≥ 0")
    if actual > float(rsv["qty"]) + QTY_EPS:
        raise HTTPException(status_code=400, detail=(
            f"Panjang potong {actual} melebihi reservasi {rsv['qty']} — tambah reservasi dulu"))
    used = round(actual + waste, 2)
    cut = {"reservation_id": reservation_id, "reserved_qty": rsv["qty"], "actual_length": actual,
           "waste": waste, "mode": mode, "by": actor, "at": now_iso(), "note": note,
           "identity_verified": False}
    op = {"op": reservation_id, "child_id": f"roll_cut_{reservation_id}", "rsv": rsv, "cut": cut,
          "actual": actual, "waste": waste}
    # CAS: reservasi masih ada & panjang fisik cukup; pull + kurangi + catat operasi potong DURABLE
    # (pending_cut_ops) dalam SATU update → gagal sesudahnya selalu bisa dilanjutkan, tidak pernah hilang.
    upd = await db.inventory_rolls.find_one_and_update(
        {"id": roll_id, "length_reservations.id": reservation_id, "length_remaining": {"$gte": used - QTY_EPS}},
        [{"$set": {"length_reservations": {"$filter": {"input": "$length_reservations", "as": "r",
                                                       "cond": {"$ne": ["$$r.id", reservation_id]}}},
                   "length_remaining": {"$round": [{"$subtract": ["$length_remaining", used]}, 2]},
                   "length_initial": {"$round": [{"$subtract": ["$length_initial", actual]}, 2]},
                   "pending_cut_ops": {"$concatArrays": [{"$ifNull": ["$pending_cut_ops", []]}, [{"$literal": op}]]},
                   "updated_at": now_iso()}},
         _recompute_reserved_stage()],
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not upd:
        raise HTTPException(status_code=409, detail="Roll induk berubah / panjang fisik tidak cukup untuk dipotong")
    return await _finish_cut({**parent, **{k: upd[k] for k in ("length_remaining", "length_initial")}}, op, upd)


async def _finish_cut(parent: Dict[str, Any], op: Dict[str, Any],
                      upd: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tahap idempoten sesudah induk dikurangi: anak (id deterministik) + movement + cabut penanda."""
    rsv, cut, actual, waste, roll_id = op["rsv"], op["cut"], op["actual"], op["waste"], parent["id"]
    child = await db.inventory_rolls.find_one({"id": op["child_id"]}, {"_id": 0})
    if not child:
        child = dict(parent)
        for k in ("_id", "length_reservations", "length_reserved", "active_movement", "pending_cut_ops"):
            child.pop(k, None)
        child.update({
            "id": op["child_id"], "length_initial": actual, "length_remaining": actual,
            "status": rsv.get("status") or "reserved", "reserved_ref": rsv["ref"], "earmarked_for": None,
            "is_remnant": False, "cut": cut, "journey": {"stage": "cut_pending_tag", "updated_at": now_iso()},
            "created_at": now_iso(), "updated_at": now_iso()})
        child = await insert_child_roll(child, parent)
    base = {"product_id": parent["product_id"], "warehouse_id": parent["warehouse_id"],
            "owner_entity_id": parent.get("owner_entity_id"), "unit": parent.get("unit", "meter"),
            "lot": parent.get("lot", ""), "source_document": rsv["ref"]["id"], "timestamp": now_iso()}
    moves = [{**base, "id": f"mov_cut_{op['op']}", "movement_type": "roll_cut", "quantity": 0,
              "roll_id": child["id"], "parent_roll_id": roll_id, "qty_rolls": 1, "cut": cut}]
    if waste > 0:
        moves.append({**base, "id": f"mov_cutw_{op['op']}", "movement_type": "cut_waste", "quantity": -waste,
                      "roll_id": roll_id, "qty_rolls": None})
    for mv in moves:
        await db.inventory_movements.update_one({"id": mv["id"]}, {"$setOnInsert": mv}, upsert=True)
    await db.inventory_rolls.update_one({"id": roll_id}, {"$pull": {"pending_cut_ops": {"op": op["op"]}}})
    # Selisih reservasi − aktual kembali bebas di induk (reservasi sudah ditarik utuh).
    await rebuild_balance(parent["product_id"], parent["warehouse_id"], parent["owner_entity_id"])
    upd = upd or await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    return {"parent": upd, "child": child, "cut": cut}


async def unverified_cut_children(order_id: str, product_id: str = "", warehouse_id: str = "") -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"reserved_ref.id": order_id, "cut.identity_verified": False,
                         "status": {"$in": ORDER_HELD_STATUSES}, "length_remaining": {"$gt": 0}}
    if product_id:
        q["product_id"] = product_id
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    return await db.inventory_rolls.find(q, {"_id": 0, "id": 1, "roll_no": 1}).to_list(2000)


async def assert_cut_identity_ready(order_id: str, product_id: str = "", warehouse_id: str = "") -> None:
    """WM-02 — gate muat/kirim: tidak ada reservasi potong tertunda & semua roll anak sudah
    ber-tag + terverifikasi. Dipakai loading check dan dispatch (ship_order_rolls)."""
    pend = [p for p in await pending_cuts(order_id)
            if (not product_id or p["product_id"] == product_id)
            and (not warehouse_id or p["warehouse_id"] == warehouse_id)]
    if pend:
        raise HTTPException(status_code=409, detail=(
            f"{len(pend)} reservasi potong belum dikonfirmasi (roll induk "
            f"{', '.join(sorted({p['roll_no'] or '' for p in pend}))}). Potong fisik & konfirmasi dulu."))
    kids = await unverified_cut_children(order_id, product_id, warehouse_id)
    if kids:
        raise HTTPException(status_code=409, detail=(
            f"Roll anak {', '.join(sorted(k['roll_no'] or k['id'] for k in kids))} belum ber-tag/terverifikasi — "
            "cetak tag RFID baru & selesaikan verifikasi sebelum muat/kirim."))


async def mark_cut_identity_verified(roll_ids: List[str], via: str, ref_id: str = "") -> int:
    """WM-02 — identitas roll anak sah setelah tag barunya terbaca di sesi verifikasi."""
    if not roll_ids:
        return 0
    res = await db.inventory_rolls.update_many(
        {"id": {"$in": roll_ids}, "cut.identity_verified": False, "rfid_tag_id": {"$nin": [None, ""]}},
        {"$set": {"cut.identity_verified": True, "cut.verified_via": via, "cut.verified_ref": ref_id,
                  "cut.verified_at": now_iso(), "updated_at": now_iso()}})
    return res.modified_count


async def verify_cut_identity_by_label(roll_id: str, scanned_code: str, actor: str = "") -> Dict[str, Any]:
    """WM-02 — gudang tanpa RFID: identitas roll anak sah bila label/barcode yang dipindai = nomor roll."""
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0, "roll_no": 1, "cut": 1})
    if not roll or not roll.get("cut"):
        raise HTTPException(status_code=404, detail="Roll anak hasil potong tidak ditemukan")
    if roll["cut"].get("identity_verified") is not False:
        raise HTTPException(status_code=409, detail="Identitas roll ini sudah terverifikasi")
    code = (scanned_code or "").strip().upper()
    if not code or code != (roll.get("roll_no") or "").strip().upper():
        raise HTTPException(status_code=400, detail=(
            f"Kode label '{scanned_code}' tidak cocok dengan roll {roll.get('roll_no')} — pindai label roll yang benar."))
    now = now_iso()
    res = await db.inventory_rolls.update_one(
        {"id": roll_id, "cut.identity_verified": False},
        {"$set": {"cut.identity_verified": True, "cut.verified_via": "label_scan", "cut.verified_ref": code,
                  "cut.verified_by": actor, "cut.verified_at": now,
                  "journey.stage": "label_verified", "journey.updated_at": now, "updated_at": now}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Identitas roll ini sudah terverifikasi")
    return {"roll_id": roll_id, "roll_no": roll.get("roll_no"), "verified_via": "label_scan", "verified_at": now}


async def label_context(child: Dict[str, Any], parent: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Data tambahan label roll anak: nama produk, no. roll induk, no. dokumen reservasi."""
    prod = await db.products.find_one({"id": child.get("product_id")}, {"_id": 0, "name": 1, "sku": 1}) or {}
    if parent is None and child.get("parent_roll_id"):
        parent = await db.inventory_rolls.find_one({"id": child["parent_roll_id"]}, {"_id": 0, "roll_no": 1})
    ref = child.get("reserved_ref") or {}
    so = await db.sales_orders.find_one({"id": ref.get("id")}, {"_id": 0, "order_number": 1}) if ref.get("id") else None
    return {"product_name": prod.get("name", ""), "sku": prod.get("sku", ""),
            "parent_roll_no": (parent or {}).get("roll_no", ""), "ref_number": (so or {}).get("order_number", "")}


async def unverified_cut_list(scope_ids: List[str]) -> List[Dict[str, Any]]:
    rows = await db.inventory_rolls.find(
        {"cut.identity_verified": False, "owner_entity_id": {"$in": scope_ids}, "length_remaining": {"$gt": 0}},
        {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1, "length_remaining": 1, "unit": 1,
         "reserved_ref": 1, "rfid_tag_id": 1, "cut.at": 1, "parent_roll_id": 1, "lot": 1, "grade": 1,
         "dye_lot": 1}).to_list(500)
    for r in rows:
        r.update(await label_context(r))
    return rows


async def pending_cuts(order_id: Optional[str] = None, scope_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"length_reserved": {"$gt": 0}}
    if order_id:
        q["length_reservations.ref.id"] = order_id
    if scope_ids is not None:
        q["owner_entity_id"] = {"$in": scope_ids}
    out = []
    async for r in db.inventory_rolls.find(q, {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1,
                                               "owner_entity_id": 1, "length_remaining": 1, "length_reserved": 1,
                                               "length_reservations": 1, "unit": 1, "lot": 1}):
        for x in r.get("length_reservations") or []:
            if order_id and x["ref"]["id"] != order_id:
                continue
            out.append({"roll_id": r["id"], "roll_no": r.get("roll_no"), "reservation_id": x["id"],
                        "order_id": x["ref"]["id"], "qty": x["qty"], "status": x.get("status"),
                        "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
                        "owner_entity_id": r.get("owner_entity_id"),
                        "parent_length": r.get("length_remaining"), "unit": r.get("unit", "meter"),
                        "lot": r.get("lot", "")})
    return out


async def _reserve_single_roll(roll_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    return await db.inventory_rolls.find_one_and_update(
        {"id": roll_id, "status": "available", "length_reserved": NO_LENGTH_RESERVED},
        {"$set": {"status": "reserved", "reserved_ref": {"type": "sales_order", "id": order_id},
                  "earmarked_for": None, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )


async def _split_roll(roll: Dict[str, Any], take: float, order_id: str) -> Optional[Dict[str, Any]]:
    """Pecah roll available: kurangi sisa parent, buat child roll reserved sebesar `take`.

    S-9 (Gelombang 2) — ATOMIK: guard length_remaining pada update parent agar dua
    checkout bersamaan tidak double-ambil roll yang sama. Gagal guard → None (caller
    lanjut ke roll berikutnya)."""
    take = round(float(take), 2)
    # WM-01 — kurangi + bulatkan dalam SATU update atomik (pipeline). Dulu normalisasi
    # memakai nilai hasil baca terpisah sehingga bisa menimpa potongan konkuren lain.
    parent = await db.inventory_rolls.find_one_and_update(
        {"id": roll["id"], "status": "available", "length_remaining": {"$gte": take - 0.001}},
        [{"$set": {"length_remaining": {"$round": [{"$subtract": ["$length_remaining", take]}, 2]},
                   "length_initial": {"$round": [{"$subtract": ["$length_initial", take]}, 2]},
                   "updated_at": now_iso()}}],
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    if not parent:
        return None
    child = dict(roll)
    child.pop("_id", None)
    child.update({
        "id": new_id("roll"),
        "length_initial": take,
        "length_remaining": take,
        "status": "reserved",
        "reserved_ref": {"type": "sales_order", "id": order_id},
        "earmarked_for": None,
        "is_remnant": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    child = await insert_child_roll(child, roll)
    return child


# ── Policy-aware allocation planner (Sub-fase 1.7, KN_15 §6) ─────────────────

DEFAULT_ALLOCATION_POLICY: Dict[str, Any] = {
    "mode": "auto",
    "priority_order": ["owner", "lot", "location", "roll_efficiency"],
    "lot_mode": "prefer_single",
    "lot_selection": "fefo",
    "location_pref": "single_warehouse",
    "allow_intercompany": True,
    "allow_partial": True,
}


async def _available_rolls_for_order(product_id: str, owner_entity_id: str, order_id: str,
                                     customer_id: str = "") -> List[Dict[str, Any]]:
    """Roll available owner-scoped untuk dialokasikan ke `order_id`/`customer_id`.
    Menghormati EARMARK (pegging): roll yang di-earmark untuk demand LAIN dikecualikan;
    roll yang di-earmark untuk order/customer ini tetap masuk (diprioritaskan planner)."""
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "owner_entity_id": owner_entity_id, "status": "available",
         "length_remaining": {"$gt": 0}}, {"_id": 0},
    ).to_list(10000)
    out = []
    for r in rolls:
        if float(r.get("length_reserved") or 0) > 0:  # WM-02 — hanya panjang bebas yang dialokasikan
            r = {**r, "physical_length": r["length_remaining"], "length_remaining": free_length(r)}
            if r["length_remaining"] <= QTY_EPS:
                continue
        ear = r.get("earmarked_for")
        if ear and isinstance(ear, dict):
            etype, eid = ear.get("type"), ear.get("id")
            if etype == "order" and eid and eid != order_id:
                continue  # di-pegging untuk order lain
            if etype == "customer" and eid and eid != customer_id:
                continue  # di-pegging untuk customer lain
        out.append(r)
    return out


def _wh_rank_factory(warehouses: Dict[str, Any], city: str):
    priority = WAREHOUSE_PRIORITY.get(city, [city, "Jakarta", "Bandung", "Surabaya"])

    def rank(wid: str) -> int:
        c = warehouses.get(wid, {}).get("city", "")
        return priority.index(c) if c in priority else 99
    return rank


def _lot_age(rolls_in_lot: List[Dict[str, Any]]) -> str:
    return min((r.get("created_at", "") for r in rolls_in_lot), default="")


def _order_rolls_in_lot(rolls: List[Dict[str, Any]], wh_rank, location_pref: str) -> List[Dict[str, Any]]:
    """Urutkan roll dalam satu lot: roll yang di-pegging (untuk demand ini) dulu →
    location_pref → FEFO/roll-eff."""
    def key(r):
        earmarked_here = 0 if r.get("earmarked_for") else 1
        if location_pref == "fewest_splits":
            return (earmarked_here, -float(r["length_remaining"]), wh_rank(r["warehouse_id"]), r.get("created_at", ""))
        # single_warehouse & nearest_customer → cluster gudang prioritas dulu, FEFO, roll besar dulu
        return (earmarked_here, wh_rank(r["warehouse_id"]), r.get("created_at", ""), -float(r["length_remaining"]))
    return sorted(rolls, key=key)


def _lot_has_earmark(rolls_in_lot: List[Dict[str, Any]]) -> bool:
    return any(r.get("earmarked_for") for r in rolls_in_lot)


def _order_lots(lots: List[str], by_lot: Dict[str, List[Dict[str, Any]]],
                per_lot_available: Dict[str, float], lot_selection: str) -> List[str]:
    # Lot yang berisi roll di-pegging (untuk demand ini) selalu didahulukan.
    def peg_key(l):
        return 0 if _lot_has_earmark(by_lot[l]) else 1
    if lot_selection == "smallest_fit":
        return sorted(lots, key=lambda l: (peg_key(l), per_lot_available[l]))
    if lot_selection == "largest_fit":
        return sorted(lots, key=lambda l: (peg_key(l), -per_lot_available[l]))
    return sorted(lots, key=lambda l: (peg_key(l), _lot_age(by_lot[l])))  # fefo/fifo → lot tertua dulu


def _select_single_lot(lots_enough: List[str], by_lot, per_lot_available, lot_selection: str) -> str:
    # Bila ada lot pegged yang cukup, pilih dari situ dulu (pegging customer pakai stok-nya).
    pegged = [l for l in lots_enough if _lot_has_earmark(by_lot[l])]
    pool = pegged or lots_enough
    if lot_selection == "smallest_fit":
        return min(pool, key=lambda l: per_lot_available[l])
    if lot_selection == "largest_fit":
        return max(pool, key=lambda l: per_lot_available[l])
    return min(pool, key=lambda l: _lot_age(by_lot[l]))  # fefo/fifo


def _build_allocation_plan(rolls: List[Dict[str, Any]], quantity: float, city: str,
                           warehouses: Dict[str, Any], policy: Dict[str, Any],
                           order_id: str = "") -> Dict[str, Any]:
    """READ-ONLY: hasilkan urutan roll (`ordered_rolls`) + meta lot untuk 1 baris.
    Menerapkan R1/R2/R3/R4 + location_pref. Tidak memutasi DB."""
    lot_mode = policy.get("lot_mode", "prefer_single")
    lot_selection = policy.get("lot_selection", "fefo")
    location_pref = policy.get("location_pref", "single_warehouse")
    dye_strict = bool(policy.get("dye_lot_strict", False))
    wh_rank = _wh_rank_factory(warehouses, city)

    # P0-4 — bila dye_lot_strict: kelompokkan per DYE LOT aktual (tekstil) & paksa
    # lot tunggal (strict_single). Default: kelompokkan per `lot` generik (perilaku lama).
    if dye_strict:
        lot_mode = "strict_single"
        def _grp(r):
            return r.get("dye_lot") or r.get("lot") or "—"
    else:
        def _grp(r):
            return r.get("lot") or "—"

    by_lot: Dict[str, List[Dict[str, Any]]] = {}
    for r in rolls:
        by_lot.setdefault(_grp(r), []).append(r)
    per_lot_available = {lot: round(sum(float(x["length_remaining"]) for x in rs), 2)
                         for lot, rs in by_lot.items()}
    total_available = round(sum(per_lot_available.values()), 2)
    Q = round(float(quantity), 2)

    base = {"total_available": total_available, "lot_selection": lot_selection,
            "lot_mode_policy": lot_mode, "ordered_rolls": []}
    if Q <= 0.01 or total_available <= 0.01:
        return {**base, "reserved_qty": 0.0, "backorder_qty": round(max(Q, 0), 2),
                "lot_mode": "single", "lots_used": [], "requires_confirmation": False,
                "explanation": "Tidak ada stok tersedia." if total_available <= 0.01 else "Qty nol."}

    lots_enough = [lot for lot in by_lot if per_lot_available[lot] + 0.01 >= Q]
    ordered_rolls: List[Dict[str, Any]] = []

    if lots_enough:
        lot = _select_single_lot(lots_enough, by_lot, per_lot_available, lot_selection)
        ordered_rolls = _order_rolls_in_lot(by_lot[lot], wh_rank, location_pref)
        reason = f"Lot tunggal {lot} cukup (kebijakan {lot_selection.upper()})."
    elif lot_mode == "strict_single":
        best = max(by_lot, key=lambda l: per_lot_available[l])
        ordered_rolls = _order_rolls_in_lot(by_lot[best], wh_rank, location_pref)
        reason = (f"Kebijakan strict_single: hanya lot tunggal terbesar {best} "
                  f"({per_lot_available[best]}); sisa → backorder/shipment terpisah.")
    else:
        lots_ordered = _order_lots(list(by_lot.keys()), by_lot, per_lot_available, lot_selection)
        for lot in lots_ordered:
            ordered_rolls.extend(_order_rolls_in_lot(by_lot[lot], wh_rank, location_pref))
        reason = "Qty melebihi lot tunggal terbesar → pemenuhan lintas-lot (mixed)."

    # Simulasi konsumsi untuk tahu lot AKTUAL & qty terpenuhi (tanpa mutasi)
    effective = min(Q, total_available)
    consumed = 0.0
    lots_used: List[str] = []
    for r in ordered_rolls:
        if consumed + 0.01 >= effective:
            break
        rlen = float(r["length_remaining"])
        take = min(rlen, round(effective - consumed, 2))
        if take <= 0.01:
            continue
        consumed = round(consumed + take, 2)
        lt = r.get("lot") or "—"
        if lt not in lots_used:
            lots_used.append(lt)

    actual_lot_mode = "single" if len(lots_used) <= 1 else "mixed"
    requires_confirmation = (lot_mode == "prefer_single" and actual_lot_mode == "mixed")
    backorder = round(max(Q - consumed, 0.0), 2)
    if backorder > 0.01 and "backorder" not in reason:
        reason += f" Sisa {backorder} → backorder."
    if actual_lot_mode == "mixed":
        reason += f" Lot dipakai: {', '.join(lots_used)}."
    return {**base, "ordered_rolls": ordered_rolls, "reserved_qty": round(consumed, 2),
            "backorder_qty": backorder, "lot_mode": actual_lot_mode, "lots_used": lots_used,
            "requires_confirmation": requires_confirmation, "explanation": reason}


def _explain_allocation(qty: float, lots: List[str], wh: Dict[str, Any], owner: str,
                        order_lot_mode: str, policy: Dict[str, Any], plan: Dict[str, Any]) -> str:
    """CLARITY (KN_15 §6.0): kalimat penjelasan per sub-alokasi (per warehouse)."""
    lot_txt = lots[0] if len(lots) == 1 else (" + ".join(lots) if lots else "—")
    sel = policy.get("lot_selection", "fefo").upper()
    wh_name = wh.get("name", wh.get("id", "Gudang"))
    if len(lots) > 1:
        base = f"{qty} dari Lot {lot_txt} ({sel}) · {wh_name} — lintas-lot di gudang ini."
    else:
        base = f"{qty} dari Lot {lot_txt} ({sel}) · {wh_name} — lot tunggal."
    if order_lot_mode == "mixed" and len(lots) <= 1:
        base += " Bagian dari pemenuhan lintas-lot (baris mixed)."
    return base


async def preview_line_allocation(product_id: str, quantity: float, city: str,
                                  owner_entity_id: str, policy: Dict[str, Any],
                                  order_id: str = "", customer_id: str = "") -> Dict[str, Any]:
    """READ-ONLY: rencana alokasi 1 baris (tanpa reservasi) — untuk preview & konfirmasi mixed-lot."""
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    rolls = await _available_rolls_for_order(product_id, owner_entity_id, order_id, customer_id)
    pol = {**DEFAULT_ALLOCATION_POLICY, **(policy or {})}
    plan = _build_allocation_plan(rolls, quantity, city, warehouses, pol, order_id)
    return {
        "product_id": product_id,
        "requested_qty": round(float(quantity), 2),
        "reserved_qty": plan["reserved_qty"],
        "backorder_qty": plan["backorder_qty"],
        "lot_mode": plan["lot_mode"],
        "lots_used": plan["lots_used"],
        "requires_confirmation": plan["requires_confirmation"],
        "explanation": plan["explanation"],
        "total_available": plan["total_available"],
        "lot_selection": pol["lot_selection"],
        "lot_mode_policy": pol["lot_mode"],
        "dye_lot_strict": bool(pol.get("dye_lot_strict", False)),
    }


async def makloon_guard(product_id: str, owner_entity_id: str, total_available: float, quantity: float,
                        pol: Optional[Dict[str, Any]] = None, override: bool = False,
                        prompt: bool = False) -> Dict[str, Any]:
    """Stok yang dicadangkan untuk makloon (material_reservations aktif) tidak boleh dijanjikan ke sales.
    Mode `allocation.makloon_reserve_mode`: block (default) | approve (boleh dengan persetujuan manajer)."""
    from services import material_reservation_service as _mres
    protected = await _mres.reserved_by_others(product_id, owner_entity_id)
    out = {"sellable": round(total_available, 2), "protected": protected, "overlap": 0.0, "blocked": False}
    if protected <= QTY_EPS:
        return out
    sellable = round(max(total_available - protected, 0.0), 2)
    if quantity <= sellable + QTY_EPS:
        return {**out, "sellable": sellable}
    if (pol or {}).get("makloon_reserve_mode") == "approve":
        if override:
            return {**out, "overlap": round(min(quantity, total_available) - sellable, 2)}
        if prompt:
            raise HTTPException(status_code=409, detail={
                "code": "MAKLOON_RESERVED_APPROVAL",
                "message": (f"Stok bebas hanya {sellable:g} — {protected:g} dicadangkan untuk makloon. "
                            f"Lanjutkan memakai stok makloon dengan persetujuan manajer?"),
                "product_id": product_id, "free_qty": sellable, "makloon_reserved_qty": protected,
                "requested_qty": round(quantity, 2)})
    return {**out, "sellable": sellable, "blocked": True}


def makloon_block_detail(product_id: str, guard: Dict[str, Any], quantity: float) -> Dict[str, Any]:
    return {"code": "MAKLOON_RESERVED",
            "message": (f"Stok bebas hanya {guard['sellable']:g} dari {quantity:g} yang diminta — "
                        f"{guard['protected']:g} sudah dicadangkan untuk makloon. Kurangi jumlah atau "
                        f"aktifkan backorder."),
            "product_id": product_id, "free_qty": guard["sellable"],
            "makloon_reserved_qty": guard["protected"], "requested_qty": round(quantity, 2)}


async def allocate_and_reserve_rolls(
    product_id: str, quantity: float, city: str, owner_entity_id: str, order_id: str,
    allow_partial: bool = False, policy: Optional[Dict[str, Any]] = None, customer_id: str = "",
    makloon_override: bool = False, makloon_prompt: bool = False,
) -> List[Dict[str, Any]]:
    """Reservasi roll owner-scoped untuk 1 baris order — POLICY-AWARE (Sub-fase 1.7).

    Menerapkan KN_15 §6 (R1 single-lot preference, R2 mixed-lot exception, R3 lot
    selection fefo/fifo/smallest/largest, R4 lot_mode prefer_single/strict_single/
    allow_mixed) + location_pref. Mengembalikan daftar alokasi per warehouse
    (kompatibel struktur SO lama) + `lot_mode` & `allocation_explanation` (CLARITY).

    Sub-fase 1.6 — Backorder:
      - `allow_partial=False` (default): bila stok < quantity → 409.
      - `allow_partial=True`: reservasi hanya sebesar stok TERSEDIA; sisa = backorder.
    """
    pol = {**DEFAULT_ALLOCATION_POLICY, **(policy or {})}
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}

    rolls = await _available_rolls_for_order(product_id, owner_entity_id, order_id, customer_id)
    plan = _build_allocation_plan(rolls, quantity, city, warehouses, pol)
    guard = await makloon_guard(product_id, owner_entity_id, plan["total_available"], quantity, pol,
                                override=makloon_override, prompt=makloon_prompt)
    total_available = guard["sellable"]

    if total_available + QTY_EPS < quantity and not allow_partial:
        if guard["blocked"]:
            raise HTTPException(status_code=409, detail=makloon_block_detail(product_id, guard, quantity))
        raise HTTPException(
            status_code=409,
            detail=f"Stok milik entitas tidak mencukupi (tersedia {round(total_available,2)} dari {quantity}). "
                   f"Aktifkan backorder untuk memesan sisa stok yang akan datang.",
        )

    effective_qty = round(min(quantity, total_available), 2)
    if effective_qty <= QTY_EPS:
        return []  # full backorder (caller catat)

    remaining = effective_qty
    per_wh: Dict[str, Dict[str, Any]] = {}

    # Reservasi mengikuti URUTAN dari planner (R1/R2/R3 + location_pref).
    # KN-B28 / KN-A13 — toleransi kuantitas SAMA dengan pemotong roll (QTY_EPS), bukan 0,01:
    # dulu perencana bisa mereservasi roll utuh yang 0,009 lebih panjang dari yang diakui.
    for roll in plan["ordered_rolls"]:
        if remaining <= QTY_EPS:
            break
        rlen = float(roll["length_remaining"])
        wid = roll["warehouse_id"]
        bucket = per_wh.setdefault(wid, {"qty": 0.0, "rolls": [], "lots": set(), "dye_lots": set()})
        if rlen <= remaining + QTY_EPS and not roll.get("physical_length"):
            reserved = await _reserve_single_roll(roll["id"], order_id)
            if not reserved:
                continue  # keburu diambil order lain → lewati
            take = float(reserved["length_remaining"])
            bucket["rolls"].append({"roll_id": reserved["id"], "roll_no": reserved.get("roll_no"),
                                    "lot": reserved.get("lot"), "dye_lot": reserved.get("dye_lot") or reserved.get("lot"),
                                    "length": take})
            bucket["lots"].add(reserved.get("lot"))
            bucket["dye_lots"].add(reserved.get("dye_lot") or reserved.get("lot"))
            bucket["qty"] += take
            remaining -= take
        else:
            # WM-02 — reservasi PANJANG di induk; roll anak lahir saat potong fisik dikonfirmasi.
            take = round(min(rlen, remaining), 2)
            held = await _reserve_length(roll, take, order_id)
            if not held:
                continue  # keburu diambil order lain (CAS panjang bebas) → roll berikutnya
            bucket["rolls"].append({"roll_id": held["id"], "roll_no": held.get("roll_no"),
                                    "reservation_id": held["reservation_id"], "pending_cut": True,
                                    "lot": held.get("lot"), "dye_lot": held.get("dye_lot") or held.get("lot"),
                                    "length": take})
            bucket["lots"].add(held.get("lot"))
            bucket["dye_lots"].add(held.get("dye_lot") or held.get("lot"))
            bucket["qty"] += take
            remaining = round(remaining - take, 2)

    if remaining > 0.01 and not allow_partial:
        await release_order_rolls(order_id)
        raise HTTPException(status_code=409, detail="Stok berubah saat reservasi. Silakan refresh katalog.")

    # Lot mode aktual = gabungan lot lintas-warehouse (mixed bila >1 lot dipakai)
    all_lots = sorted({lot for info in per_wh.values() for lot in info["lots"] if lot})
    order_lot_mode = "single" if len(all_lots) <= 1 else "mixed"

    allocations: List[Dict[str, Any]] = []
    for wid, info in per_wh.items():
        wh = warehouses.get(wid, {})
        lots = sorted(x for x in info["lots"] if x)
        dye_lots = sorted(x for x in info["dye_lots"] if x)
        explanation = _explain_allocation(round(info["qty"], 2), lots, wh, owner_entity_id,
                                          order_lot_mode, pol, plan)
        allocations.append({
            "id": new_id("alloc"),
            "product_id": product_id,
            "warehouse_id": wid,
            "warehouse_name": wh.get("name", wid),
            "warehouse_city": wh.get("city", ""),
            "owner_entity_id": owner_entity_id,
            "quantity": round(info["qty"], 2),
            "lot": lots[0] if len(lots) == 1 else None,
            "lots": lots,
            "dye_lot": dye_lots[0] if len(dye_lots) == 1 else None,
            "dye_lots": dye_lots,
            "lot_mode": "single" if len(lots) <= 1 else "mixed",
            "allocation_explanation": explanation,
            "policy_lot_selection": pol["lot_selection"],
            "dye_lot_strict": bool(pol.get("dye_lot_strict", False)),
            "rolls": info["rolls"],
            "status": "allocated",
        })
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": product_id, "warehouse_id": wid,
            "owner_entity_id": owner_entity_id, "movement_type": "reservation",
            "quantity": round(info["qty"], 2), "unit": wh.get("unit", "meter"),
            "lot": lots[0] if lots else "", "roll_id": ",".join(r["roll_id"] for r in info["rolls"]),
            "source_document": order_id, "timestamp": now_iso(),
        })
        await rebuild_balance(product_id, wid, owner_entity_id)
    if allocations and guard["overlap"] > QTY_EPS:
        allocations[0]["makloon_overlap_qty"] = guard["overlap"]
    return allocations


async def release_order_rolls(order_id: str) -> float:
    """Lepas semua roll yang ter-reserve untuk order tertentu → kembali available.
    Mengembalikan total qty yang dilepas. Rebuild balance segmen terdampak."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "status": {"$in": ORDER_HELD_STATUSES}}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    total = 0.0
    # WM-02 — reservasi panjang (belum dipotong) cukup ditarik dari induk; tidak ada roll anak.
    async for p in db.inventory_rolls.find({"length_reservations.ref.id": order_id}, {"_id": 0}):
        mine = [x for x in p["length_reservations"] if x["ref"]["id"] == order_id]
        res = await db.inventory_rolls.update_one(
            {"id": p["id"]},
            [{"$set": {"length_reservations": {"$filter": {"input": "$length_reservations", "as": "r",
                                                           "cond": {"$ne": ["$$r.ref.id", order_id]}}},
                       "updated_at": now_iso()}}, _recompute_reserved_stage()])
        if res.modified_count:
            q = round(sum(float(x["qty"]) for x in mine), 2)
            total += q
            segments.add((p["product_id"], p["warehouse_id"], p["owner_entity_id"]))
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": p["product_id"], "warehouse_id": p["warehouse_id"],
                "owner_entity_id": p["owner_entity_id"], "movement_type": "release_reservation",
                "quantity": q, "unit": p.get("unit", "meter"), "lot": p.get("lot", ""), "roll_id": p["id"],
                "qty_rolls": None, "source_document": order_id, "timestamp": now_iso(),
                "note": "reservasi panjang (belum dipotong) dilepas"})
    if not held and not segments:
        return 0.0
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}},
        )
        total += float(r.get("length_remaining", 0) or 0)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
            "owner_entity_id": r["owner_entity_id"], "movement_type": "release_reservation",
            "quantity": round(float(r.get("length_remaining", 0) or 0), 2), "unit": r.get("unit", "meter"),
            "lot": r.get("lot", ""), "roll_id": r["id"],
 # FASE U — satu baris mutasi menunjuk SATU roll fisik.
 "qty_rolls": (1 if r["id"] else None), "source_document": order_id, "timestamp": now_iso(),
        })
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return round(total, 2)


async def release_order_rolls_partial(order_id: str, product_id: str, warehouse_id: str,
                                      qty: float) -> float:
    """S-6 (Gelombang 2) — lepas SEBAGIAN reservasi roll order utk satu produk+gudang.

    Dipakai saat manager menurunkan qty via eskalasi: roll kecil dilepas utuh dulu;
    sisa selisih dipecah dari roll ter-reserve (bagian lepasan kembali available).
    Mengembalikan total qty yang benar-benar dilepas."""
    qty = round(float(qty), 2)
    if qty <= 0:
        return 0.0
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "product_id": product_id, "warehouse_id": warehouse_id,
         "status": {"$in": ORDER_HELD_STATUSES}}, {"_id": 0},
    ).sort("length_remaining", 1).to_list(10000)
    remaining = qty
    released = 0.0
    segments = set()
    # WM-02 — kurangi reservasi panjang yang belum dipotong lebih dulu (tanpa fragmen roll).
    async for p in db.inventory_rolls.find(
            {"length_reservations.ref.id": order_id, "product_id": product_id, "warehouse_id": warehouse_id},
            {"_id": 0}):
        for x in sorted([x for x in p["length_reservations"] if x["ref"]["id"] == order_id], key=lambda x: x["qty"]):
            if remaining <= 0.01:
                break
            take = round(min(float(x["qty"]), remaining), 2)
            new_qty = round(float(x["qty"]) - take, 2)
            if new_qty <= QTY_EPS:
                pipe = [{"$set": {"length_reservations": {"$filter": {"input": "$length_reservations", "as": "r",
                                                                      "cond": {"$ne": ["$$r.id", x["id"]]}}}}}]
            else:
                pipe = [{"$set": {"length_reservations": {"$map": {"input": "$length_reservations", "as": "r", "in": {
                    "$cond": [{"$eq": ["$$r.id", x["id"]]}, {"$mergeObjects": ["$$r", {"qty": new_qty}]}, "$$r"]}}}}}]
            res = await db.inventory_rolls.update_one({"id": p["id"], "length_reservations.id": x["id"]},
                                                      pipe + [_recompute_reserved_stage()])
            if res.modified_count:
                remaining = round(remaining - take, 2)
                released = round(released + take, 2)
                segments.add((p["product_id"], p["warehouse_id"], p["owner_entity_id"]))
    for r in held:
        if remaining <= 0.01:
            break
        rlen = round(float(r.get("length_remaining", 0) or 0), 2)
        if rlen <= 0:
            continue
        if rlen <= remaining + 0.01:
            # lepas roll utuh
            await db.inventory_rolls.update_one(
                {"id": r["id"]},
                {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}})
            take = rlen
        else:
            # pecah: kurangi roll ter-reserve, buat roll available sebesar sisa selisih
            take = round(remaining, 2)
            await db.inventory_rolls.update_one(
                {"id": r["id"]},
                {"$set": {"length_remaining": round(rlen - take, 2),
                          "length_initial": round(float(r.get("length_initial", rlen)) - take, 2),
                          "updated_at": now_iso()}})
            fragment = dict(r)
            fragment.pop("_id", None)
            fragment.update({
                "id": new_id("roll"), "length_initial": take, "length_remaining": take,
                "status": "available", "reserved_ref": None, "earmarked_for": None,
                "created_at": now_iso(), "updated_at": now_iso(),
            })
            fragment = await insert_child_roll(fragment, r)
        remaining = round(remaining - take, 2)
        released = round(released + take, 2)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
            "owner_entity_id": r["owner_entity_id"], "movement_type": "release_reservation",
            "quantity": take, "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
            "roll_id": r["id"],
            # FASE U — satu baris mutasi menunjuk SATU roll fisik.
            "qty_rolls": (1 if r["id"] else None), "source_document": order_id, "timestamp": now_iso(),
            "note": "partial release (penyesuaian qty eskalasi)",
        })
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return released


async def set_order_rolls_status(order_id: str, new_status: str) -> int:
    """Ubah status roll milik order (mis. reserved→committed saat approve)."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "status": {"$in": ORDER_HELD_STATUSES}}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]}, {"$set": {"status": new_status, "updated_at": now_iso()}}
        )
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    n = len(held)
    if new_status in ORDER_HELD_STATUSES:  # WM-02 — status reservasi panjang ikut (bucket saldo)
        async for p in db.inventory_rolls.find({"length_reservations.ref.id": order_id}, {"_id": 0}):
            await db.inventory_rolls.update_one(
                {"id": p["id"]}, {"$set": {"length_reservations.$[r].status": new_status}},
                array_filters=[{"r.ref.id": order_id}])
            segments.add((p["product_id"], p["warehouse_id"], p["owner_entity_id"]))
            n += 1
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return n


# ── Pengiriman (Sub-fase 1.8): committed → in_transit_sales (SSOT-safe) ───────

SHIPPABLE_STATUSES = ["committed", "packed", "picked", "reserved"]


async def ship_order_rolls(order_id: str, product_id: str, warehouse_id: str, qty: float,
                           roll_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Kirim (dispatch) `qty` dari roll milik order utk segmen product×warehouse:
    committed/picked/packed/reserved → in_transit_sales (FEFO, split bila parsial).
    SSOT-safe (KN_15 §10): TIDAK pernah $inc balance — on_hand turun otomatis karena
    in_transit_sales adalah bucket TRANSIT (bukan fisik). rebuild_balance dipanggil.
    Return: {shipped: float, rolls: [{roll_id, lot, length, unit}]}."""
    qty = round(float(qty), 2)
    if qty <= 0:
        return {"shipped": 0.0, "rolls": []}
    # WM-02 lanjutan — roll anak wajib ADA fisik (potong dikonfirmasi) dan identitasnya terverifikasi
    # (tag RFID baru + sesi verifikasi) sebelum keluar. Tidak ada lagi potong otomatis saat dispatch.
    await assert_cut_identity_ready(order_id, product_id, warehouse_id)
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "product_id": product_id, "warehouse_id": warehouse_id,
         "status": {"$in": SHIPPABLE_STATUSES}, "length_remaining": {"$gt": 0}}, {"_id": 0},
    ).to_list(10000)
    held.sort(key=lambda r: (r.get("created_at", ""), float(r.get("length_remaining", 0))))
    if roll_ids:
        # AX-01 — hanya roll yang dipindai saat pick (identitas manifest), urut sesuai scan.
        order = {rid: i for i, rid in enumerate(roll_ids)}
        held = sorted((r for r in held if r["id"] in order), key=lambda r: order[r["id"]])
        if sum(float(r["length_remaining"]) for r in held) + 0.01 < qty:
            raise HTTPException(status_code=409, detail=(
                "Roll yang dipindai saat pick tidak cukup / tidak lagi milik order ini — pindai ulang roll yang dikirim."))
    total_avail = sum(float(r["length_remaining"]) for r in held)
    if total_avail + 0.01 < qty:
        raise HTTPException(
            status_code=409,
            detail=f"Roll commit untuk order tak cukup dikirim (tersedia {round(total_avail,2)} dari {qty}).")
    remaining = qty
    shipped_rolls: List[Dict[str, Any]] = []
    segments = set()
    for roll in held:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        take = min(rlen, remaining)
        if take >= rlen - 0.01:
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"status": "in_transit_sales", "shipped_at": now_iso(), "updated_at": now_iso()}})
            ship_id, ship_len = roll["id"], rlen
        else:
            parent_remaining = rlen - take
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(parent_remaining, 2),
                          "length_initial": round(float(roll["length_initial"]) - take, 2),
                          "updated_at": now_iso()}})
            child = dict(roll); child.pop("_id", None)
            child.update({
                "id": new_id("roll"), "length_initial": round(take, 2),
                "length_remaining": round(take, 2), "status": "in_transit_sales",
                "shipped_at": now_iso(), "is_remnant": False,
                "created_at": now_iso(), "updated_at": now_iso()})
            child = await insert_child_roll(child, roll)
            ship_id, ship_len = child["id"], take
        # FN-11 — biaya roll DIBEKUKAN saat dispatch (HPP shipment = Σ panjang × biaya roll keluar).
        uc = float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
        shipped_rolls.append({"roll_id": ship_id, "lot": roll.get("lot", ""),
                              "length": round(ship_len, 2), "unit": roll.get("unit", "meter"),
                              "unit_cost": round(uc, 4), "extended_cost": round(uc * ship_len, 2)})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
            "owner_entity_id": roll.get("owner_entity_id"), "movement_type": "outbound_ship",
            "quantity": -round(ship_len, 2), "unit": roll.get("unit", "meter"),
            "lot": roll.get("lot", ""), "roll_id": ship_id,
 # FASE U — satu baris mutasi menunjuk SATU roll fisik.
 "qty_rolls": (1 if ship_id else None), "source_document": order_id,
            "timestamp": now_iso()})
        segments.add((product_id, warehouse_id, roll["owner_entity_id"]))
        remaining -= take
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return {"shipped": round(qty - max(remaining, 0), 2), "rolls": shipped_rolls}


async def deliver_order_rolls(order_id: str) -> int:
    """Tandai terkirim/diterima (done): roll in_transit_sales order → 'delivered' (terminal,
    keluar dari owned_qty). rebuild_balance segmen terdampak."""
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "status": "in_transit_sales"}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    for r in rolls:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "delivered", "delivered_at": now_iso(), "updated_at": now_iso()}})
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return len(rolls)


# ── Inter-company ownership transfer (Sub-fase 1.5, KN_15 §7 + D3) ────────────

def _split_roll_for_ref(roll: Dict[str, Any], take: float, ref: Dict[str, Any]) -> Dict[str, Any]:
    """Bangun child-roll reserved sebesar `take` dengan reserved_ref generik (mis. transfer).
    (Caller wajib meng-update parent length & insert child — lihat reserve_rolls_for_transfer.)"""
    child = dict(roll)
    child.pop("_id", None)
    child.update({
        "id": new_id("roll"),
        "length_initial": round(take, 2),
        "length_remaining": round(take, 2),
        "status": "reserved",
        "reserved_ref": ref,
        "is_remnant": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return child


async def reserve_rolls_for_transfer(
    product_id: str, source_entity_id: str, quantity: float, transfer_id: str,
    roll_ids: Optional[List[str]] = None, prefer_origin_type: str = "",
) -> List[Dict[str, Any]]:
    """Reservasi roll milik entitas SUMBER (B) untuk inter-company transfer (FEFO, split).
    Set status=reserved, reserved_ref={type:'transfer', id:transfer_id} agar B tak dobel-jual.
    Mengembalikan daftar roll yang direservasi. Raise 409 bila stok B tak cukup.

    FASE E-9 (E9.4) — dua parameter baru menutup cacat "roll bagus terkirim balik":
      * `roll_ids` — kirim **roll yang ITU saja** (dipakai Retur Antar-PT: barang yang
        diretur pelanggan, bukan sembarang roll produk yang sama).
      * `prefer_origin_type` — utamakan roll ber-asal tertentu (mis. `"return"`, lot
        `RTN-*`) sebelum jatuh ke FEFO biasa.
    Tanpa keduanya, pemilihan FEFO per produk **mengirim roll bagus ke PT lain dan
    meninggalkan roll cacat di gudang sendiri** — nilainya beda, gradenya beda, dan
    pelanggan berikutnya yang menanggung akibatnya.
    """
    ref = {"type": "transfer", "id": transfer_id}
    q: Dict[str, Any] = {
        "product_id": product_id, "owner_entity_id": source_entity_id,
        "status": "available", "length_reserved": NO_LENGTH_RESERVED, "length_remaining": {"$gt": 0}}
    wanted = [rid for rid in (roll_ids or []) if rid]
    if wanted:
        q["id"] = {"$in": wanted}
    rolls = await db.inventory_rolls.find(q, {"_id": 0}).to_list(10000)
    if wanted:
        # Urutan mengikuti daftar yang diminta (keputusan manusia, bukan FEFO).
        rank = {rid: i for i, rid in enumerate(wanted)}
        rolls.sort(key=lambda r: rank.get(r["id"], 10**6))
        missing = [rid for rid in wanted if rid not in {r["id"] for r in rolls}]
        if missing:
            raise HTTPException(
                status_code=409,
                detail=(f"{len(missing)} roll yang dipilih tidak bisa dipakai: pastikan roll "
                        f"masih 'tersedia' dan milik badan usaha pengirim "
                        f"(id: {', '.join(missing[:3])})."))
    elif prefer_origin_type:
        rolls.sort(key=lambda r: (0 if r.get("origin_type") == prefer_origin_type else 1,
                                  r.get("created_at", ""),
                                  -float(r.get("length_remaining", 0) or 0)))
    else:
        # FEFO: lot tertua (created_at) dulu, roll besar dulu
        rolls.sort(key=lambda r: (r.get("created_at", ""), -float(r.get("length_remaining", 0))))

    total = sum(float(r["length_remaining"]) for r in rolls)
    if total + 0.01 < quantity:
        raise HTTPException(
            status_code=409,
            detail=(f"Roll yang dipilih tidak cukup untuk transfer (tersedia {round(total,2)} "
                    f"dari {quantity})." if wanted else
                    f"Stok entitas sumber tidak cukup untuk transfer (tersedia {round(total,2)} dari {quantity})."),
        )

    remaining = quantity
    reserved: List[Dict[str, Any]] = []
    for roll in rolls:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        if rlen <= remaining + 0.01:
            updated = await db.inventory_rolls.find_one_and_update(
                {"id": roll["id"], "status": "available", "length_reserved": NO_LENGTH_RESERVED},
                {"$set": {"status": "reserved", "reserved_ref": ref, "updated_at": now_iso()}},
                projection={"_id": 0}, return_document=ReturnDocument.AFTER,
            )
            if not updated:
                continue  # keburu diambil transaksi lain
            reserved.append(updated)
            remaining -= float(updated["length_remaining"])
        else:
            # roll lebih besar dari kebutuhan → split: kurangi parent, buat child reserved
            child = _split_roll_for_ref(roll, remaining, ref)
            parent_remaining = rlen - remaining
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(parent_remaining, 2),
                          "length_initial": round(float(roll["length_initial"]) - remaining, 2),
                          "updated_at": now_iso()}},
            )
            child = await insert_child_roll(child, roll)
            reserved.append(child)
            remaining = 0.0
            break

    if remaining > 0.01:
        # race condition → rollback reservasi parsial
        await release_transfer_rolls(transfer_id)
        raise HTTPException(status_code=409, detail="Stok sumber berubah saat reservasi transfer. Coba lagi.")

    segments = {(r["product_id"], r["warehouse_id"], r["owner_entity_id"]) for r in reserved}
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return reserved


async def execute_ownership_transfer(transfer: Dict[str, Any]) -> Dict[str, Any]:
    """Pindahkan kepemilikan roll yang direservasi transfer dari source→dest (S3: SAAT APPROVE).
    owner_entity_id B→E, acquired.via='transfer', status kembali 'available' (kini milik E).
    Catat movement ownership_transfer_out (B) + ownership_transfer_in (E). Rebuild balance kedua segmen.

    FASE G-6 — **lot ikut berpindah rumah**: sebuah lot milik satu PT tidak boleh
    berisi roll milik PT lain (INV-LOT-05 "lot tidak lintas pemilik"). Karena itu
    roll yang berpindah dimasukkan ke lot milik PT tujuan (dibuat sekali per
    transfer × produk) dengan **genealogi** menunjuk lot asal — jadi silsilah
    "kain ini asalnya dari lot mana di PT mana" tetap utuh.
    """
    transfer_id = transfer["id"]
    src = transfer["source_entity_id"]
    dst = transfer["dest_entity_id"]
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "transfer", "status": "reserved"},
        {"_id": 0},
    ).to_list(10000)
    # G3 D4-INTERCO-02 — SNAPSHOT biaya roll yang benar-benar berpindah SEBELUM kepemilikan pindah:
    # JE at-cost memakai biaya aktual roll (bukan WAC live sumber yang sudah tidak memuat roll ini).
    _cost: Dict[str, List[float]] = {}
    for r in held:
        q = float(r.get("length_remaining", 0) or 0)
        c = _cost.setdefault(r["product_id"], [0.0, 0.0])
        c[0] += q
        c[1] += q * float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
    for it in transfer.get("items") or []:
        c = _cost.get(it.get("product_id"))
        if c and c[0] > 0 and c[1] > 0 and "unit_cost_snapshot" not in it:
            it["unit_cost_snapshot"] = round(c[1] / c[0], 4)
    if _cost:
        await db.warehouse_transfers.update_one({"id": transfer_id}, {"$set": {"items": transfer.get("items") or []}})
    segments = set()
    moved = 0.0
    touched_lots: set = set()
    for r in held:
        qty = float(r.get("length_remaining", 0) or 0)
        new_lot_id, new_lot_number = await _rehome_lot_to_owner(r, dst, transfer)
        set_fields: Dict[str, Any] = {
            "owner_entity_id": dst, "status": "available", "reserved_ref": None,
            "acquired": {"via": "transfer", "ref_id": transfer_id, "date": now_iso()},
            "updated_at": now_iso(),
        }
        # FASE E-9 (E9.5) — `acquired` ditimpa setiap kali kepemilikan berpindah, dan
        # dulu itu MENGHAPUS jejak "barang ini dulu masuk lewat GRN/PO mana". Akibatnya
        # badan usaha penerima tidak bisa lagi meretur barangnya ke supplier aslinya.
        # Sekarang jejak lama disimpan sebagai riwayat (append-only) — field asal
        # (`supplier_id`/`po_id`/…) sendiri tidak pernah disentuh di sini.
        prev_acq = r.get("acquired") or {}
        if prev_acq:
            hist = list(r.get("acquired_history") or [])
            # Nama SINGKAT pemilik sebelumnya — bukan id teknisnya. Menyimpan
            # `ent_*` di sini membocorkan identitas badan usaha lawan ke setiap
            # layar yang menampilkan roll (E5.3); id presisinya sudah tercatat di
            # `inventory_movements` yang ter-scope.
            _prev_owner_name = await _mlabel.short_name_of(r.get("owner_entity_id", ""))
            hist.append({**{k: v for k, v in prev_acq.items() if k != "owner_entity_id"},
                         "owner_entity_name": _prev_owner_name,
                         "replaced_at": now_iso(),
                         "replaced_by_transfer": transfer.get("code", transfer_id)})
            set_fields["acquired_history"] = hist[-20:]
        if new_lot_id:
            if r.get("lot_id"):
                touched_lots.add(r["lot_id"])
            touched_lots.add(new_lot_id)
            set_fields["lot_id"] = new_lot_id
            if new_lot_number:
                set_fields["lot"] = new_lot_number
        await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": set_fields})
        # KN-B19 — kepemilikan tag RFID mengikuti roll (SCOPE_FIELD rfid_tags = owner_entity_id).
        await db.rfid_tags.update_many({"roll_id": r["id"], "status": "active"},
                                       {"$set": {"owner_entity_id": dst, "updated_at": now_iso()}})
        moved += qty
        base_mov = {
            "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
            "unit": r.get("unit", "meter"), "lot": r.get("lot", ""), "roll_id": r["id"],
            "from_owner_entity_id": src, "to_owner_entity_id": dst,
            "source_document": transfer.get("code", transfer_id), "timestamp": now_iso(),
        }
        await db.inventory_movements.insert_one({
            **base_mov, "id": new_id("mov"), "owner_entity_id": src,
            "movement_type": "ownership_transfer_out", "quantity": -round(qty, 2),
        })
        await db.inventory_movements.insert_one({
            **base_mov, "id": new_id("mov"), "owner_entity_id": dst,
            "movement_type": "ownership_transfer_in", "quantity": round(qty, 2),
        })
        segments.add((r["product_id"], r["warehouse_id"], src))
        segments.add((r["product_id"], r["warehouse_id"], dst))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    if touched_lots:
        try:
            from services import lot_service
            await lot_service.recompute_many(sorted(touched_lots))
        except Exception as exc:  # noqa: BLE001 — proyeksi lot, bukan syarat perpindahan
            print(f"[transfer] recompute lot gagal: {exc}")
    return {"moved_qty": round(moved, 2), "rolls": len(held)}


async def _rehome_lot_to_owner(roll: Dict[str, Any], dst_entity: str,
                               transfer: Dict[str, Any]) -> Tuple[str, str]:
    """Siapkan lot milik PT tujuan untuk sebuah roll yang berpindah kepemilikan.

    Idempoten per (transfer × produk × dye lot) lewat `resolve_or_create`, dan lot
    baru menaut lot asal sebagai INDUK sehingga penelusuran silsilah tidak putus.
    Bila roll memang tanpa lot, tidak ada yang perlu dilakukan.
    """
    if not roll.get("lot_id"):
        return "", ""
    try:
        from services import lot_service
        old = await db.inventory_lots.find_one({"id": roll["lot_id"]}, {"_id": 0})
        if not old:
            return "", ""
        if old.get("owner_entity_id") == dst_entity:
            return old["id"], old.get("lot_number", "")
        new_lot = await lot_service.resolve_or_create(
            product_id=roll["product_id"], owner_entity_id=dst_entity,
            warehouse_id=roll.get("warehouse_id", ""),
            source="transfer",
            source_ref={"type": "transfer", "id": transfer["id"],
                        "number": transfer.get("code", "")},
            supplier_lot=old.get("supplier_lot", ""),
            dye_lot=old.get("dye_lot", ""),
            supplier_id=old.get("supplier_id", ""),
            supplier_name=old.get("supplier_name", ""),
            status=old.get("lot_status", "released"),
            actor="Transfer Antar-PT",
            parent_lot_ids=[old["id"]])
        return new_lot["id"], new_lot.get("lot_number", "")
    except Exception as exc:  # noqa: BLE001
        print(f"[transfer] gagal menyiapkan lot PT tujuan: {exc}")
        return "", ""


async def release_transfer_rolls(transfer_id: str) -> float:
    """Lepas roll yang direservasi untuk transfer (reject/cancel) → kembali available milik sumber."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "transfer", "status": "reserved"},
        {"_id": 0},
    ).to_list(10000)
    segments = set()
    total = 0.0
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}},
        )
        total += float(r.get("length_remaining", 0) or 0)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return round(total, 2)


# ─── INTRA-ENTITY WAREHOUSE TRANSFER (roll-based, KN_15 §9 / KN_16 §7) ────────
# Owner TETAP (physical move antar-gudang milik entitas yang sama).
# Lifecycle roll: available → reserved (create) → in_transit_transfer (dispatch)
#                 → available@dest (complete). Batal → available@source.
INTRA_TRANSFER_HELD = ["reserved", "in_transit_transfer"]


async def resolve_stock_owner(product_id: str, warehouse_id: str, prefer_owner: str = "",
                              allowed_owners: Optional[List[str]] = None) -> str:
    """Tentukan owner stok di sebuah gudang (owner dgn available terbanyak).
    W2-006 — bila `allowed_owners` diberikan, ini kontrak OTORISASI: owner hasil wajib di dalamnya,
    dan `prefer_owner` dipertahankan walau tanpa stok (tidak pernah fallback ke owner lain)."""
    if allowed_owners is not None:
        if prefer_owner:
            if prefer_owner not in allowed_owners:
                raise HTTPException(status_code=403, detail="Anda tidak berwenang atas stok badan usaha ini.")
            return prefer_owner
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "warehouse_id": warehouse_id, "status": "available", "length_reserved": NO_LENGTH_RESERVED,
         "length_remaining": {"$gt": 0}},
        {"_id": 0, "owner_entity_id": 1, "length_remaining": 1},
    ).to_list(10000)
    agg: Dict[str, float] = {}
    for r in rolls:
        o = r.get("owner_entity_id") or DEFAULT_ENTITY_ID
        if allowed_owners is not None and o not in allowed_owners:
            continue
        agg[o] = agg.get(o, 0.0) + float(r.get("length_remaining", 0) or 0)
    if allowed_owners is not None and not agg:
        raise HTTPException(status_code=400, detail="Pilih badan usaha pemilik stok (tidak ada stok tersedia milik badan usaha Anda di gudang ini).")
    if prefer_owner and agg.get(prefer_owner, 0) > 0:
        return prefer_owner
    if agg:
        return max(agg, key=agg.get)
    return prefer_owner or DEFAULT_ENTITY_ID


async def reserve_rolls_for_wh_transfer(
    product_id: str, source_warehouse_id: str, owner_entity_id: str,
    quantity: float, transfer_id: str, roll_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Reservasi roll milik `owner` di gudang SUMBER untuk transfer antar-gudang (FEFO, split).
    available→reserved, reserved_ref={type:'wh_transfer', id}. Raise 409 bila stok kurang."""
    ref = {"type": "wh_transfer", "id": transfer_id}
    if roll_ids:
        # Operator memilih roll eksplisit (picker): pindahkan roll utuh, tanpa FEFO/split.
        # AX-04 — pilihan eksplisit divalidasi dimensi yang SAMA dengan jalur FEFO (termasuk owner)
        chosen = await db.inventory_rolls.find(
            {"id": {"$in": list(roll_ids)}, "product_id": product_id, "status": "available", "length_reserved": NO_LENGTH_RESERVED,
             "owner_entity_id": owner_entity_id, "length_remaining": {"$gt": 0}},
            {"_id": 0}).to_list(len(roll_ids))
        if len(chosen) != len(set(roll_ids)):
            raise HTTPException(status_code=409, detail="Sebagian roll yang dipilih tidak tersedia atau bukan milik badan usaha transfer. Muat ulang daftar roll.")
        wrong = [r["roll_no"] for r in chosen if r.get("warehouse_id") != source_warehouse_id]
        if wrong:
            raise HTTPException(status_code=400, detail=f"Roll {', '.join(map(str, wrong))} tidak berada di gudang asal.")
        out: List[Dict[str, Any]] = []
        for r in chosen:
            res = await db.inventory_rolls.update_one(
                {"id": r["id"], "status": "available", "length_reserved": NO_LENGTH_RESERVED, "owner_entity_id": owner_entity_id,
                 "warehouse_id": source_warehouse_id},
                {"$set": {"status": "reserved", "reserved_ref": ref, "updated_at": now_iso()}})
            if not res.matched_count:
                # lepas HANYA reservasi milik operasi ini (id yang barusan dipesan + ref sama)
                if out:
                    await db.inventory_rolls.update_many(
                        {"id": {"$in": [x["id"] for x in out]}, "status": "reserved", "reserved_ref": ref},
                        {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}})
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} baru saja diambil proses lain.")
            out.append(r)
        await rebuild_balance(product_id, source_warehouse_id, owner_entity_id)
        return out
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "warehouse_id": source_warehouse_id,
         "owner_entity_id": owner_entity_id, "status": "available", "length_reserved": NO_LENGTH_RESERVED,
         "length_remaining": {"$gt": 0}}, {"_id": 0},
    ).to_list(10000)
    rolls.sort(key=lambda r: (r.get("created_at", ""), -float(r.get("length_remaining", 0))))
    total = sum(float(r["length_remaining"]) for r in rolls)
    if total + 0.01 < quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Stok gudang sumber tidak cukup untuk transfer (tersedia {round(total,2)} dari {quantity}).",
        )
    remaining = quantity
    reserved: List[Dict[str, Any]] = []
    for roll in rolls:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        if rlen <= remaining + 0.01:
            updated = await db.inventory_rolls.find_one_and_update(
                {"id": roll["id"], "status": "available", "length_reserved": NO_LENGTH_RESERVED},
                {"$set": {"status": "reserved", "reserved_ref": ref, "updated_at": now_iso()}},
                projection={"_id": 0}, return_document=ReturnDocument.AFTER,
            )
            if not updated:
                continue
            reserved.append(updated)
            remaining -= float(updated["length_remaining"])
        else:
            child = _split_roll_for_ref(roll, remaining, ref)
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(rlen - remaining, 2),
                          "length_initial": round(float(roll["length_initial"]) - remaining, 2),
                          "updated_at": now_iso()}},
            )
            child = await insert_child_roll(child, roll)
            reserved.append(child)
            remaining = 0.0
            break
    if remaining > 0.01:
        await release_wh_transfer_rolls(transfer_id)
        raise HTTPException(status_code=409, detail="Stok sumber berubah saat reservasi transfer. Coba lagi.")
    for p, w, o in {(r["product_id"], r["warehouse_id"], r["owner_entity_id"]) for r in reserved}:
        await rebuild_balance(p, w, o)
    return reserved


async def dispatch_wh_transfer_rolls(transfer_id: str, source_document: str = "") -> Dict[str, Any]:
    """Kirim: roll reserved (ref wh_transfer) → in_transit_transfer. Movement transfer_out. Rebuild sumber."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "wh_transfer", "status": "reserved"},
        {"_id": 0},
    ).to_list(10000)
    segments = set()
    moved = 0.0
    for r in held:
        qty = float(r.get("length_remaining", 0) or 0)
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "in_transit_transfer", "updated_at": now_iso()}},
        )
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
            "owner_entity_id": r["owner_entity_id"], "movement_type": "transfer_out",
            "quantity": -round(qty, 2), "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
            "batch": r.get("batch", ""), "roll_id": r["id"],
 # FASE U — satu baris mutasi menunjuk SATU roll fisik.
 "qty_rolls": (1 if r["id"] else None),
            "source_document": source_document or transfer_id, "timestamp": now_iso(),
        })
        moved += qty
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return {"moved_qty": round(moved, 2), "rolls": len(held)}


async def receive_wh_transfer_rolls(transfer_id: str, dest_warehouse_id: str, source_document: str = "") -> Dict[str, Any]:
    """Terima: roll in_transit_transfer (ref wh_transfer) → warehouse_id=tujuan, status available, ref None.
    Movement transfer_in. Rebuild segmen sumber (lama) & tujuan (baru). Owner TETAP."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "wh_transfer", "status": "in_transit_transfer"},
        {"_id": 0},
    ).to_list(10000)
    segments = set()
    moved = 0.0
    for r in held:
        qty = float(r.get("length_remaining", 0) or 0)
        src_wh = r["warehouse_id"]
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            # AX-05 — owner tetap → asal perolehan (acquired) TIDAK ditimpa; bin gudang asal
            # tidak valid di gudang tujuan → kosong sampai putaway. Perpindahan tercatat di movement.
            {"$set": {"warehouse_id": dest_warehouse_id, "status": "available", "reserved_ref": None,
                      "bin_id": None, "last_transfer": {"ref_id": transfer_id, "from_warehouse_id": src_wh,
                                                        "date": now_iso()},
                      "updated_at": now_iso()}},
        )
        # KN-B19 — tag RFID ikut pindah gudang (seperti jalur putaway); dulu tertinggal di gudang lama.
        await db.rfid_tags.update_many({"roll_id": r["id"], "status": "active"},
                                       {"$set": {"warehouse_id": dest_warehouse_id, "updated_at": now_iso()}})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": dest_warehouse_id,
            "owner_entity_id": r["owner_entity_id"], "movement_type": "transfer_in",
            "quantity": round(qty, 2), "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
            "batch": r.get("batch", ""), "roll_id": r["id"],
 # FASE U — satu baris mutasi menunjuk SATU roll fisik.
 "qty_rolls": (1 if r["id"] else None),
            "source_document": source_document or transfer_id, "timestamp": now_iso(),
        })
        moved += qty
        segments.add((r["product_id"], src_wh, r["owner_entity_id"]))
        segments.add((r["product_id"], dest_warehouse_id, r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return {"moved_qty": round(moved, 2), "rolls": len(held)}


async def release_wh_transfer_rolls(transfer_id: str) -> float:
    """Batal/tolak transfer antar-gudang: roll reserved / in_transit_transfer → available (tetap di gudang asal).
    Untuk roll yang sudah in_transit (sudah dispatch), catat movement transfer_cancelled (+qty) agar ledger seimbang."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "wh_transfer",
         "status": {"$in": INTRA_TRANSFER_HELD}}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    total = 0.0
    for r in held:
        was_transit = r.get("status") == "in_transit_transfer"
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}},
        )
        if was_transit:
            qty = float(r.get("length_remaining", 0) or 0)
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
                "owner_entity_id": r["owner_entity_id"], "movement_type": "transfer_cancelled",
                "quantity": round(qty, 2), "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
                "roll_id": r["id"],
                # FASE U — satu baris mutasi menunjuk SATU roll fisik.
                "qty_rolls": (1 if r["id"] else None), "source_document": transfer_id, "timestamp": now_iso(),
            })
        total += float(r.get("length_remaining", 0) or 0)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return round(total, 2)


def _norm_grade(raw: Any) -> str:
    """Fase A · PS-09/D-01 — grade roll SELALU nilai enum resmi (fallback 'A')."""
    import domain_registry as dr
    return dr.normalize_grade(raw)["value"] or "A"

# ─── INBOUND ROLL & CYCLE-COUNT ADJUSTMENT (roll-based, SSOT-safe) ────────────
async def create_inbound_roll(
    product_id: str, warehouse_id: str, owner_entity_id: str, quantity: float, *,
    lot: str = "", batch: str = "", bin_id: Optional[str] = None, unit: Optional[str] = None,
    grade: str = "A", acquired_via: str = "manual_inbound", ref_id: str = "",
    created_by: str = "System", roll_no: str = "",
    is_remnant: bool = False, unit_cost: Optional[float] = None,
    status: str = "available", dye_lot: str = "",
    lot_source: str = "manual", lot_source_ref: Optional[Dict[str, Any]] = None,
    parent_lot_ids: Optional[List[str]] = None, supplier_lot: str = "",
    lot_status: str = "",
    roll_id: str = "",
) -> Dict[str, Any]:
    """Buat 1 roll `available` (SSOT) + movement + rebuild balance.
    Dipakai inbound manual (/wms/tasks) & surplus cycle-count — MENGGANTIKAN $inc balance.

    M2 (Makloon) — parameter opsional additive:
      - is_remnant: tandai roll sebagai barang sisa (byproduct) kembali ke KN.
      - unit_cost: override HPP per unit (mis. hasil makloon = WIP cost teralokasi).
      - status: override status awal roll (default 'available').
      - dye_lot: override dye_lot (default = lot).

    FASE C (D-10/D-26) — setiap roll WAJIB lahir dengan `lot_id` ke `inventory_lots`:
      - `lot` string yang dikirim pemanggil dipakai sebagai kode pencarian/jejak
        (`legacy_lot_codes`) sehingga tidak ada lot ganda saat dipanggil berulang;
      - `lot_source`/`lot_source_ref`/`parent_lot_ids` membentuk genealogi (mis.
        output makloon = anak dari lot bahan).
    """
    prod = await db.products.find_one({"id": product_id}, {"_id": 0}) or {}
    lot = lot or await _lot_for_segment(product_id, warehouse_id)
    from services import lot_service as _lots
    _lot_doc = await _lots.resolve_or_create(
        product_id=product_id, owner_entity_id=owner_entity_id,
        warehouse_id=warehouse_id, lot_code=lot, source=lot_source,
        source_ref=lot_source_ref or {"type": acquired_via, "id": ref_id, "number": ""},
        supplier_lot=supplier_lot, dye_lot=dye_lot or lot,
        status=lot_status or ("released" if status == "available" else "in_process"),
        actor=created_by, parent_lot_ids=parent_lot_ids)
    _uc = round(float(unit_cost), 4) if unit_cost is not None else round(float(prod.get("harga_pokok") or 0), 4)
    # KN-B27 — `unit` pemanggil DIHORMATI: kuantitas dikonversi ke satuan dasar produk
    # (dulu 100 yard lahir sebagai roll "100 meter" karena unit hanya menimpa label).
    # `unit=None` = kuantitas sudah dalam satuan dasar produk (identitas).
    qty_in = float(quantity)
    quantity = await to_base_qty(prod, qty_in, unit)
    # INV-GL-DRIFT — `unit_cost` pemanggil berlaku per satuan PEMANGGIL; bila kuantitas
    # dikonversi, biaya per satuan dasar ikut dikonversi agar NILAI roll tidak berubah.
    if unit_cost is not None and quantity > 0 and abs(quantity - qty_in) > 1e-9:
        _uc = round(float(unit_cost) * qty_in / quantity, 4)
    if roll_id:   # G3 V3-MKO-01 — identitas deterministik: retry mengembalikan roll yang sama
        existing = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
        if existing:
            return existing
    roll = {
        "id": roll_id or new_id("roll"), "product_id": product_id, "owner_entity_id": owner_entity_id,
        "ownership_type": "internal", "consignor_ref": None,
        "warehouse_id": warehouse_id, "bin_id": bin_id,
        "lot": _lot_doc["lot_number"], "lot_id": _lot_doc["id"],
        "supplier_lot": supplier_lot, "dye_lot": dye_lot or lot,
        "batch": batch or (lot.replace("LOT", "BATCH") if lot else ""),
        "roll_no": roll_no or await next_roll_no(),
        "length_initial": round(float(quantity), 2), "length_remaining": round(float(quantity), 2),
        "unit": prod.get("base_unit") or unit or "meter", "grade": _norm_grade(prod.get("grade", grade)),
        # Fase A · PS-01/PS-02 — snapshot stage & jenis kain dari master produk
        **_domain_snapshot(prod),
        "status": status, "tracking_mode": "barcode", "earmarked_for": None,
        "secondary_measures": None, "location_type": "warehouse_bin", "reserved_ref": None,
        "base_unit_cost": _uc,
        "unit_cost": (_uc or None),
        "landed_cost_total": 0.0,
        "acquired": {"via": acquired_via, "ref_id": ref_id, "date": now_iso()},
        "rfid_tag_id": None, "is_remnant": bool(is_remnant),
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": created_by, "created_by_name": created_by,
    }
    await db.inventory_rolls.insert_one(dict(roll))
    mov = {
        "id": f"mov_{roll['id']}" if roll_id else new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
        "owner_entity_id": owner_entity_id, "movement_type": acquired_via,
        "quantity": round(float(quantity), 2), "unit": prod.get("base_unit") or unit or "meter",
        "lot": _lot_doc["lot_number"], "lot_id": _lot_doc["id"],
        "batch": batch, "roll_id": roll["id"],
 # FASE U — satu baris mutasi menunjuk SATU roll fisik.
 "qty_rolls": (1 if roll["id"] else None),
        "source_document": ref_id, "timestamp": now_iso(),
    }
    await db.inventory_movements.update_one({"id": mov["id"]}, {"$setOnInsert": mov}, upsert=True)
    await _lots.recompute(_lot_doc["id"])
    await rebuild_balance(product_id, warehouse_id, owner_entity_id)
    return roll


def roll_value_cents(roll: Dict[str, Any]) -> int:
    """NILAI satu roll dalam SEN BULAT — SATU sumber untuk semua yang menghitung
    nilai persediaan (rekonsiliasi GL, penjelas selisih, true-up saldo awal).

    `length_remaining × (unit_cost | base_unit_cost)` dibulatkan SEKALI ke sen di
    sini; penjumlahan lintas roll lalu dilakukan sebagai bilangan bulat sehingga
    residu biner mustahil menumpuk (gap iterasi 256: Σ float meninggalkan Rp 0,01).
    """
    cost = float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
    length = float(roll.get("length_remaining") or 0)
    return to_cents(length * cost)


# ─── SALES REVAMP V2 — Reservasi roll EKSPLISIT (Beli per Roll + Rekonsiliasi) ───

async def supplier_refs_for_products(product_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Nama/kode barang versi supplier per produk (KN_18 A-09) — dipakai picker gudang & katalog MD."""
    ids = [p for p in set(product_ids) if p]
    if not ids:
        return {}
    rows = await db.supplier_items.find({"product_id": {"$in": ids}, "active": {"$ne": False}},
                                        {"_id": 0, "product_id": 1, "supplier_id": 1, "supplier_sku": 1,
                                         "supplier_item_name": 1, "supplier_color_code": 1, "supplier_uom": 1}).to_list(len(ids) * 20)
    sup = {s["id"]: s for s in await db.suppliers.find({"id": {"$in": list({r["supplier_id"] for r in rows})}},
                                                       {"_id": 0, "id": 1, "name": 1, "code": 1}).to_list(len(rows) or 1)}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        s = sup.get(r["supplier_id"], {})
        out.setdefault(r["product_id"], []).append({
            "supplier_id": r["supplier_id"], "supplier_name": s.get("name", ""), "supplier_code": s.get("code", ""),
            "supplier_sku": r.get("supplier_sku", ""), "supplier_item_name": r.get("supplier_item_name", ""),
            "supplier_color_code": r.get("supplier_color_code", ""), "supplier_uom": r.get("supplier_uom", "")})
    return out


async def list_available_rolls(product_id: str, owner_entity_id: str = "",
                               all_entities: bool = False, sort: str = "fefo",
                               skip: int = 0, limit: int = 0, warehouse_id: str = "") -> Dict[str, Any]:
    """Daftar roll available untuk PICKER (paginasi + FEFO). all_entities=True → lintas-entitas.
    Mengembalikan {items, total} (objek, bukan array telanjang) — khusus picker."""
    q: Dict[str, Any] = {"product_id": product_id, "status": "available", "length_remaining": {"$gt": 0}}
    if not all_entities and owner_entity_id:
        q["owner_entity_id"] = owner_entity_id
    if warehouse_id:
        q["warehouse_id"] = warehouse_id          # picker transfer/outbound: hanya roll di gudang sumber
    rolls = await db.inventory_rolls.find(q, {"_id": 0}).to_list(20000)
    # singkirkan roll yang di-earmark untuk demand lain (tetap tampil bila tak di-earmark)
    rolls = [r for r in rolls if not (isinstance(r.get("earmarked_for"), dict) and r["earmarked_for"].get("id"))]
    rolls = [r for r in rolls if free_length(r) > QTY_EPS]  # WM-02 — roll dipesan penuh tak ditawarkan
    if sort == "lifo":
        rolls.sort(key=lambda r: (r.get("created_at", ""), r.get("roll_no", "")), reverse=True)
    else:  # fefo (default) — tertua/lot paling lama dulu
        rolls.sort(key=lambda r: (r.get("lot", ""), r.get("created_at", ""), r.get("roll_no", "")))
    total = len(rolls)
    if limit and limit > 0:
        rolls = rolls[skip: skip + limit]
    elif skip:
        rolls = rolls[skip:]
    # enrich gudang + entitas (badge pembeda)
    wh = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1, "city": 1}).to_list(200)}
    ent = {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(200)}
    items = []
    for r in rolls:
        w = wh.get(r.get("warehouse_id"), {})
        e = ent.get(r.get("owner_entity_id"), {})
        ename = e.get("short_name") or e.get("name") or e.get("legal_name") or r.get("owner_entity_id", "")
        items.append({
            "id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"),
            "dye_lot": r.get("dye_lot") or r.get("lot"),
            # WM-02 — picker menawarkan PANJANG BEBAS (sisa fisik − reservasi potong tertunda)
            "length_remaining": round(free_length(r), 2),
            "physical_length": round(float(r.get("length_remaining", 0) or 0), 2),
            "length_reserved": round(float(r.get("length_reserved") or 0), 2),
            "warehouse_id": r.get("warehouse_id"), "warehouse_name": w.get("name", r.get("warehouse_id")),
            "warehouse_city": w.get("city", ""),
            "owner_entity_id": r.get("owner_entity_id"),
            "owner_entity_name": ename,
            "owner_entity_code": e.get("code", ""),
            "created_at": r.get("created_at", ""),
            "supplier_roll_no": r.get("supplier_roll_no", ""),
        })
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "base_unit": 1, "unit": 1, "name": 1, "sku": 1})
    return {"items": items, "total": total,
            "base_unit": (prod or {}).get("base_unit") or (prod or {}).get("unit") or "meter",
            "supplier_refs": (await supplier_refs_for_products([product_id])).get(product_id, [])}


async def reserve_specific_rolls(roll_lines: List[Dict[str, Any]], ref: Dict[str, Any],
                                 product_id: str = "") -> List[Dict[str, Any]]:
    """Reservasi EKSAK roll sesuai daftar [{roll_id, take_qty}] dgn reserved_ref generik.
    - take_qty >= length_remaining → reserve roll UTUH.
    - take_qty < length_remaining  → CUT: split roll, child sebesar take_qty di-reserve.
    Atomic per roll; rollback (lepas semua ref ini) bila ada yang gagal. Raise 409/400 jelas.
    Mengembalikan daftar roll ter-reserve (dokumen child untuk cut)."""
    reserved: List[Dict[str, Any]] = []
    segments = set()
    try:
        for line in (roll_lines or []):
            rid = line.get("roll_id") if isinstance(line, dict) else getattr(line, "roll_id", None)
            take_raw = line.get("take_qty") if isinstance(line, dict) else getattr(line, "take_qty", 0)
            if not rid:
                raise HTTPException(status_code=400, detail="roll_id wajib pada pilihan roll.")
            roll = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
            if not roll:
                raise HTTPException(status_code=404, detail=f"Roll {rid} tidak ditemukan.")
            if product_id and roll.get("product_id") != product_id:
                raise HTTPException(status_code=400, detail=f"Roll {roll.get('roll_no', rid)} bukan milik produk ini.")
            if roll.get("status") != "available":
                raise HTTPException(status_code=409, detail=f"Roll {roll.get('roll_no', rid)} sudah tidak tersedia.")
            rlen = round(float(roll.get("length_remaining", 0) or 0), 2)
            take = round(float(take_raw or 0), 2)
            has_rsv = float(roll.get("length_reserved") or 0) > 0
            if ref.get("type") == "sales_order" and (has_rsv or (0 < take < rlen - 0.01)):
                # WM-02 — beli sebagian roll (atau roll yang sudah dipesan sebagian) = reservasi
                # panjang di induk; roll anak lahir saat potong fisik dikonfirmasi.
                free = free_length(roll)
                take = free if take <= 0 else take
                if take > free + 0.01:
                    raise HTTPException(status_code=400, detail=(
                        f"Qty roll {roll.get('roll_no', rid)} ({take}) melebihi panjang bebas ({free})."))
                held = await _reserve_length(roll, take, ref["id"], ref)
                if not held:
                    raise HTTPException(status_code=409, detail=f"Roll {roll.get('roll_no', rid)} keburu diambil transaksi lain.")
                reserved.append({**held, "length_remaining": take, "pending_cut": True})
                segments.add((roll["product_id"], roll["warehouse_id"], roll["owner_entity_id"]))
                continue
            if has_rsv:
                raise HTTPException(status_code=409, detail=(
                    f"Roll {roll.get('roll_no', rid)} punya reservasi potong yang belum dikonfirmasi."))
            if take <= 0:
                take = rlen  # default: roll utuh
            if take > rlen + 0.01:
                raise HTTPException(status_code=400,
                                    detail=f"Qty roll {roll.get('roll_no', rid)} ({take}) melebihi sisa ({rlen}).")
            if take >= rlen - 0.01:
                updated = await db.inventory_rolls.find_one_and_update(
                    {"id": rid, "status": "available", "length_reserved": NO_LENGTH_RESERVED},
                    {"$set": {"status": "reserved", "reserved_ref": ref, "earmarked_for": None,
                              "updated_at": now_iso()}},
                    projection={"_id": 0}, return_document=ReturnDocument.AFTER,
                )
                if not updated:
                    raise HTTPException(status_code=409, detail=f"Roll {roll.get('roll_no', rid)} keburu diambil transaksi lain.")
                reserved.append(updated)
            else:
                # CUT: kurangi parent + buat child reserved sebesar take (atomic pada parent)
                upd = await db.inventory_rolls.find_one_and_update(
                    {"id": rid, "status": "available", "length_reserved": NO_LENGTH_RESERVED, "length_remaining": {"$gte": take}},
                    {"$set": {"length_remaining": round(rlen - take, 2),
                              "length_initial": round(float(roll.get("length_initial", rlen)) - take, 2),
                              "updated_at": now_iso()}},
                    projection={"_id": 0}, return_document=ReturnDocument.AFTER,
                )
                if not upd:
                    raise HTTPException(status_code=409, detail=f"Roll {roll.get('roll_no', rid)} keburu berubah. Coba lagi.")
                child = _split_roll_for_ref(roll, take, ref)
                child = await insert_child_roll(child, roll)
                reserved.append(child)
            segments.add((roll["product_id"], roll["warehouse_id"], roll["owner_entity_id"]))
    except HTTPException:
        await _release_rolls_by_ref_id(ref.get("id"))
        raise
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return reserved


async def _release_rolls_by_ref_id(ref_id: str) -> float:
    """Lepas semua roll reserved dengan reserved_ref.id == ref_id → available. (rollback umum)"""
    if not ref_id:
        return 0.0
    async for p in db.inventory_rolls.find({"length_reservations.ref.id": ref_id}, {"_id": 0, "id": 1}):
        await db.inventory_rolls.update_one(  # WM-02 — reservasi panjang ikut dilepas
            {"id": p["id"]},
            [{"$set": {"length_reservations": {"$filter": {"input": "$length_reservations", "as": "r",
                                                           "cond": {"$ne": ["$$r.ref.id", ref_id]}}}}},
             _recompute_reserved_stage()])
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": ref_id, "status": {"$in": ORDER_HELD_STATUSES}}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    total = 0.0
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}},
        )
        total += float(r.get("length_remaining", 0) or 0)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return round(total, 2)


def allocations_from_reserved_rolls(product_id: str, reserved_rolls: List[Dict[str, Any]],
                                    warehouses: Dict[str, Any], status: str = "allocated") -> List[Dict[str, Any]]:
    """Bangun struktur allocations (per warehouse × owner) dari daftar roll ter-reserve —
    kompatibel dengan output allocate_and_reserve_rolls (dipakai SO line)."""
    groups: Dict[tuple, Dict[str, Any]] = {}
    for r in reserved_rolls:
        key = (r["warehouse_id"], r["owner_entity_id"])
        g = groups.setdefault(key, {"qty": 0.0, "rolls": [], "lots": set(), "dye_lots": set()})
        ln = float(r.get("length_remaining", 0) or 0)
        g["rolls"].append({"roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"),
                           "dye_lot": r.get("dye_lot") or r.get("lot"), "length": round(ln, 2),
                           **({"pending_cut": True, "reservation_id": r.get("reservation_id")}
                              if r.get("pending_cut") else {})})
        g["lots"].add(r.get("lot"))
        g["dye_lots"].add(r.get("dye_lot") or r.get("lot"))
        g["qty"] += ln
    out = []
    for (wid, owner), info in groups.items():
        wh = warehouses.get(wid, {})
        lots = sorted(x for x in info["lots"] if x)
        dye_lots = sorted(x for x in info["dye_lots"] if x)
        out.append({
            "id": new_id("alloc"), "product_id": product_id, "warehouse_id": wid,
            "warehouse_name": wh.get("name", wid), "warehouse_city": wh.get("city", ""),
            "owner_entity_id": owner, "quantity": round(info["qty"], 2),
            "lot": lots[0] if len(lots) == 1 else None, "lots": lots,
            "dye_lot": dye_lots[0] if len(dye_lots) == 1 else None, "dye_lots": dye_lots,
            "lot_mode": "single" if len(lots) <= 1 else "mixed",
            "allocation_explanation": f"Pilihan roll manual ({len(info['rolls'])} roll) — {status}.",
            "rolls": info["rolls"], "status": status, "selection": "manual_roll",
        })
    return out


async def record_reservation_movements(product_id: str, reserved_rolls: List[Dict[str, Any]],
                                       order_id: str, warehouses: Dict[str, Any]) -> None:
    """Catat movement 'reservation' untuk roll yang dipilih manual (per warehouse×owner)."""
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in reserved_rolls:
        groups.setdefault((r["warehouse_id"], r["owner_entity_id"]), []).append(r)
    for (wid, owner), rolls_ in groups.items():
        wh = warehouses.get(wid, {})
        qty = round(sum(float(x.get("length_remaining", 0) or 0) for x in rolls_), 2)
        lots = sorted({x.get("lot") for x in rolls_ if x.get("lot")})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": product_id, "warehouse_id": wid,
            "owner_entity_id": owner, "movement_type": "reservation", "quantity": qty,
            "unit": wh.get("unit", "meter"), "lot": lots[0] if lots else "",
            "roll_id": ",".join(x["id"] for x in rolls_), "source_document": order_id,
            "timestamp": now_iso(),
        })



async def compute_roll_reconcile(product_id: str, target_qty: float, selling_entity_id: str = "",
                                 all_entities: bool = False) -> Dict[str, Any]:
    """SALES REVAMP V2 (FASE C2) — Rekonsiliasi roll untuk pesanan per-yard.

    Karena 1 roll = ±90–110 yd, kombinasi roll utuh (FEFO) jarang pas target. Hasilkan opsi:
      - round_up    : set roll utuh terkecil dgn total ≥ target (delta +).
      - round_down  : set roll utuh terbesar dgn total ≤ target (delta −).
      - exact_cut   : round_down (utuh) + POTONG 1 roll agar pas target (opsi terakhir).
      - exact_whole : bila kebetulan ada prefix yang pas (tak perlu rekonsiliasi).
    Bila stok roll < target → feasible=False + opsi take_all (sisanya backorder).
    """
    data = await list_available_rolls(product_id, selling_entity_id if not all_entities else "",
                                       all_entities=all_entities, sort="fefo", skip=0, limit=0)
    rolls = data["items"]
    for r in rolls:
        r["is_cross_entity"] = bool(selling_entity_id and r.get("owner_entity_id") != selling_entity_id)
    target = round(float(target_qty or 0), 2)
    total_available = round(sum(float(r["length_remaining"]) for r in rolls), 2)

    def lines(rs, cut=None):
        out = [{"roll_id": r["id"], "take_qty": round(float(r["length_remaining"]), 2)} for r in rs]
        if cut:
            out.append({"roll_id": cut["roll"]["id"], "take_qty": round(cut["take"], 2)})
        return out

    def snap(rs, cut=None):
        out = [{"roll_id": r["id"], "roll_no": r["roll_no"], "length": round(float(r["length_remaining"]), 2),
                "lot": r["lot"], "owner_entity_name": r["owner_entity_name"],
                "is_cross_entity": r.get("is_cross_entity", False), "cut": False} for r in rs]
        if cut:
            cr = cut["roll"]
            out.append({"roll_id": cr["id"], "roll_no": cr["roll_no"], "length": round(cut["take"], 2),
                        "lot": cr["lot"], "owner_entity_name": cr["owner_entity_name"],
                        "is_cross_entity": cr.get("is_cross_entity", False), "cut": True,
                        "roll_full_length": round(float(cr["length_remaining"]), 2)})
        return out

    if target <= 0:
        return {"product_id": product_id, "target_qty": target, "feasible": True,
                "total_available": total_available, "options": {}}

    # akumulasi FEFO sampai >= target
    up_rolls: List[Dict[str, Any]] = []
    cum = 0.0
    for r in rolls:
        up_rolls.append(r)
        cum += float(r["length_remaining"])
        if cum >= target - 0.01:
            break
    sum_up = round(cum, 2)

    options: Dict[str, Any] = {}
    if sum_up < target - 0.01:
        # tak cukup roll utuh untuk menutup target
        options["take_all"] = {"roll_lines": lines(rolls), "snapshot": snap(rolls),
                               "total_qty": total_available, "delta": round(total_available - target, 2),
                               "roll_count": len(rolls), "backorder_qty": round(target - total_available, 2)}
        return {"product_id": product_id, "target_qty": target, "feasible": False,
                "total_available": total_available, "options": options}

    options["round_up"] = {"roll_lines": lines(up_rolls), "snapshot": snap(up_rolls),
                           "total_qty": sum_up, "delta": round(sum_up - target, 2), "roll_count": len(up_rolls)}
    if abs(sum_up - target) < 0.01:
        options["exact_whole"] = options["round_up"]

    last = up_rolls[-1]
    down_rolls = up_rolls[:-1]
    sum_down = round(sum_up - float(last["length_remaining"]), 2)
    options["round_down"] = {"roll_lines": lines(down_rolls), "snapshot": snap(down_rolls),
                             "total_qty": sum_down, "delta": round(sum_down - target, 2), "roll_count": len(down_rolls)}
    cut_take = round(target - sum_down, 2)
    if 0.01 < cut_take < float(last["length_remaining"]) - 0.01:
        options["exact_cut"] = {"roll_lines": lines(down_rolls, {"roll": last, "take": cut_take}),
                                "snapshot": snap(down_rolls, {"roll": last, "take": cut_take}),
                                "total_qty": target, "delta": 0.0, "roll_count": len(down_rolls) + 1,
                                "cut_qty": cut_take, "cut_roll_no": last["roll_no"]}
    return {"product_id": product_id, "target_qty": target, "feasible": True,
            "total_available": total_available, "options": options}
