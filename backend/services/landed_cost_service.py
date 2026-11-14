"""Landed Cost service (Fase 5.4 — P0-5).

Mengalokasikan biaya tambahan impor/angkut (freight, bea masuk, asuransi,
handling) ke HPP per ROLL (`inventory_rolls.unit_cost`). Roll = SSOT fisik
(KN_15) sehingga HPP melekat di roll, bukan di balance proyeksi.

Model HPP (additive, mendukung banyak voucher):
  unit_cost(final) = base_unit_cost + Σ(landed_per_unit dari tiap voucher)
  landed_cost_total(roll) = Σ(alloc_amount per voucher)

Basis alokasi:
  - value    : bobot = base_unit_cost × length_initial (nilai roll)  [default 1a]
  - quantity : bobot = length_initial (panjang)
Fallback aman: bila Σbobot value = 0 (roll belum punya base cost) → pakai
basis quantity; bila masih 0 → bagi rata.

Lifecycle voucher: draft → pending_approval → applied (→ paid) | cancelled.
Aplikasi ke HPP HANYA terjadi saat APPROVE (idempotent: status 'applied'
tidak bisa di-apply ulang). Pembuat ≠ approver (SoD).
"""
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso, to_cents, from_cents
from services import roll_cost_history
from services.roll_service import OFFSITE_OWNED_STATUS_TO_BUCKET, roll_value_cents

ACTIVE_VOUCHER_STATUSES = {"draft", "pending_approval", "applied", "paid"}
PAYABLE_VOUCHER_STATUSES = {"applied", "paid"}
COST_CATEGORIES = {"freight", "duty", "insurance", "handling", "other"}

# PK-26 (IV-01, K-05) — GOLONGAN roll saat voucher disetujui menentukan ke mana biaya masuk dibukukan:
#   persediaan → nilai roll di gudang naik (1-1300); wip → roll di mitra makloon (1-1350, sama dengan kirim bahan);
#   keluar     → roll sudah meninggalkan PT (terkirim/retur ke pemasok/antar-PT): bagiannya langsung beban periode
#                berjalan (pengaturan `inventory.landed_cost_porsi_terjual`: HPP atau akun biaya masuk pembelian).
# Status di luar dua daftar (mis. `receiving`) = persediaan — sama dengan perilaku sebelum PK-26.
TREATMENT_PERSEDIAAN, TREATMENT_WIP, TREATMENT_KELUAR = "persediaan", "wip", "keluar"
WIP_ROLL_STATUSES = frozenset(OFFSITE_OWNED_STATUS_TO_BUCKET)          # {"subcon"} — satu sumber dengan bucket roll
OUT_ROLL_STATUSES = frozenset({"in_transit_sales", "delivered", "returned_supplier", "in_transit_intercompany"})
#: golongan → kunci Pemetaan Akun baris debit (P9: akun dari pemetaan per PT, bukan kode tetap)
TREATMENT_ACCOUNT_KEY = {TREATMENT_PERSEDIAAN: "persediaan.persediaan", TREATMENT_WIP: "makloon.wip_subcon"}
#: nilai `inventory.landed_cost_porsi_terjual` → kunci Pemetaan Akun baris porsi keluar (tanpa akun/kunci baru)
EXPENSE_ACCOUNT_KEY = {"hpp": "persediaan.hpp", "varians": "pembelian.landed_cost"}


def treatment_of(roll: Dict[str, Any]) -> str:
    """Golongan satu roll: `persediaan` · `wip` · `keluar` (dari `status` roll)."""
    status = (roll or {}).get("status") or ""
    if status in WIP_ROLL_STATUSES:
        return TREATMENT_WIP
    if status in OUT_ROLL_STATUSES:
        return TREATMENT_KELUAR
    return TREATMENT_PERSEDIAAN


def split_allocation(rolls: List[Dict[str, Any]], allocations: List[Dict[str, Any]],
                     allocated_total: float) -> Dict[str, Any]:
    """PK-26 — pecah nominal voucher menjadi porsi persediaan, makloon (WIP), dan beban. Murni (tanpa tulisan).

    `rolls` = dokumen roll SEBELUM biaya dinaikkan (`apply_allocation_to_rolls`). Per alokasi roll golongan persediaan/
    wip: kenaikan = `to_cents(sisa × (biaya + per_unit)) − roll_value_cents(roll)` — persis kenaikan nilai roll yang
    dihitung rekonsiliasi sesudah `$inc unit_cost`. Roll keluar = 0. Sisa (`allocated_total` − Σ kenaikan) = beban:
    memuat roll keluar, bagian roll hidup yang sudah susut (panjang awal − sisa), dan pembulatan.

    Kenaikan satu roll yang melebihi alokasinya tepat 1 sen = pembulatan dua nilai yang masing-masing dibulatkan ke sen
    (biaya roll yang sudah memuat landed cost lama berpecahan sen), bukan kenaikan nyata: dibatasi ke alokasinya supaya
    persetujuan tidak ditolak. Lebih dari itu (sisa > panjang awal = data roll rusak) dibiarkan → beban negatif →
    `ValueError` (persetujuan 409 tanpa tulisan)."""
    by_id = {r.get("id"): r for r in rolls or []}
    sen = {TREATMENT_PERSEDIAAN: 0, TREATMENT_WIP: 0}
    per_roll: List[Dict[str, Any]] = []
    for a in allocations or []:
        r = by_id.get(a.get("roll_id")) or {}
        golongan = treatment_of(r)
        naik = 0
        if golongan != TREATMENT_KELUAR:
            biaya = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
            sesudah = to_cents(float(r.get("length_remaining") or 0) * (biaya + float(a.get("per_unit") or 0)))
            naik = sesudah - roll_value_cents(r)
            jatah = to_cents(a.get("alloc_amount") or 0)
            if 0 < naik - jatah <= 1:
                naik = jatah
            sen[golongan] += naik
        per_roll.append({"roll_id": a.get("roll_id"), "treatment": golongan, "capitalized_amount": from_cents(naik)})
    beban = to_cents(allocated_total) - sen[TREATMENT_PERSEDIAAN] - sen[TREATMENT_WIP]
    if beban < 0:
        raise ValueError("Hitungan pembebanan landed cost negatif")
    return {"inventory_amount": from_cents(sen[TREATMENT_PERSEDIAAN]), "wip_amount": from_cents(sen[TREATMENT_WIP]),
            "expensed_amount": from_cents(beban), "per_roll": per_roll}


async def expensed_to_for(entity_id: str) -> str:
    """Pengaturan `inventory.landed_cost_porsi_terjual` untuk PT voucher (`hpp` · `varians`; bawaan K-05 `hpp`)."""
    from services.config_resolver import value_of
    nilai = await value_of("inventory.landed_cost_porsi_terjual", {"entity_id": entity_id or ""})
    return nilai if nilai in EXPENSE_ACCOUNT_KEY else "hpp"


def capitalization_of(split: Dict[str, Any], expensed_to: str) -> Dict[str, Any]:
    """Potret `capitalization` voucher (`02` D3: ditulis sekali bersama status `applied`, tidak dihitung ulang)."""
    return {"inventory_amount": split["inventory_amount"], "wip_amount": split["wip_amount"],
            "expensed_amount": split["expensed_amount"],
            "expensed_to": expensed_to if expensed_to in EXPENSE_ACCOUNT_KEY else "hpp", "computed_at": now_iso()}


def with_treatment(allocations: List[Dict[str, Any]], split: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris alokasi voucher yang disetujui + `treatment` dan `capitalized_amount` dari hasil `split_allocation`."""
    per = {p["roll_id"]: p for p in split.get("per_roll") or []}
    out = []
    for a in allocations or []:
        p = per.get(a.get("roll_id")) or {}
        out.append({**a, "treatment": p.get("treatment", TREATMENT_PERSEDIAAN),
                    "capitalized_amount": p.get("capitalized_amount", 0.0)})
    return out


def preview_treatment(rolls: List[Dict[str, Any]], allocations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pratinjau alokasi + `treatment` (hanya tampilan saat voucher dibuat; persetujuan menghitung ulang)."""
    by_id = {r.get("id"): r for r in rolls or []}
    return [{**a, "treatment": treatment_of(by_id.get(a.get("roll_id")) or {})} for a in allocations or []]


async def next_voucher_number(entity_id: Optional[str] = None) -> str:
    """KN-A12 — sequence ATOMIK bersama (find_one_and_update $inc), bukan 'nomor tertinggi + 1'.
    KP-T5 — `entity_id` = PT dokumennya (N1): bawaan tetap deret bersama; berlaku bila grup memilih per PT."""
    from core_utils import next_doc_number
    return await next_doc_number("landed_cost_vouchers", "voucher_number", "LCV-", width=5, entity_id=entity_id or None,
                                 scheme="shared", kind="lcv")


def total_cost_of(cost_lines: List[Dict[str, Any]]) -> float:
    return round(sum(float(c.get("amount", 0) or 0) for c in (cost_lines or [])), 2)


def voucher_financials(v: Dict[str, Any]) -> Dict[str, Any]:
    total = round(float(v.get("total_cost", 0) or 0), 2)
    paid = round(float(v.get("amount_paid", 0) or 0), 2)
    outstanding = round(max(total - paid, 0.0), 2)
    if v.get("status") not in PAYABLE_VOUCHER_STATUSES:
        payment_status = "n/a"
    elif paid <= 0.01:
        payment_status = "unpaid"
    elif outstanding <= 0.01:
        payment_status = "paid"
    else:
        payment_status = "partial"
    return {"total_cost": total, "amount_paid": paid, "outstanding": outstanding,
            "payment_status": payment_status}


async def resolve_target_rolls(po_ids: List[str], entity_id: str = "") -> List[Dict[str, Any]]:
    """Roll yang diterima dari PO terkait (acquired.ref_id == po_id). HPP melekat
    di roll → semua roll dari PO ikut dialokasi, kecuali yang sudah scrapped."""
    if not po_ids:
        return []
    query: Dict[str, Any] = {"acquired.ref_id": {"$in": list(po_ids)},
                             "status": {"$nin": ["scrapped", "cancelled"]}}
    if entity_id and entity_id != "all":
        query["owner_entity_id"] = entity_id
    rolls = await db.inventory_rolls.find(query, {"_id": 0}).to_list(5000)
    # FN-01 — target = SELURUH fragmen fisik (disjoint by length_initial): potongan lama yang tak
    # mewarisi acquired.ref_id ikut disertakan, sehingga tidak perlu propagasi ke turunan.
    seen = {r["id"] for r in rolls}
    frontier = list(seen)
    while frontier:
        kids = await db.inventory_rolls.find(
            {"$or": [{"parent_roll_id": {"$in": frontier}}, {"root_roll_id": {"$in": frontier}}],
             "id": {"$nin": list(seen)}, "status": {"$nin": ["scrapped", "cancelled"]}}, {"_id": 0}).to_list(5000)
        kids = [k for k in kids if not entity_id or entity_id == "all" or k.get("owner_entity_id") == entity_id]
        rolls += kids
        frontier = [k["id"] for k in kids]
        seen.update(frontier)
    # Dokumen roll TIDAK menyimpan nama produk (hanya `product_id`), sedangkan tabel
    # alokasi di layar menampilkan `product_name || product_id` → selama ini pemilik
    # membaca **`prod_batik_mega`** di kolom Produk, bukan "Batik Mega Mendung Premium".
    # Kelas bug yang sama dengan kebocoran `ent_ksc` yang ditutup FASE P7 (INV-UI-02):
    # id teknis tak boleh sampai ke mata pengguna. Namanya dilengkapi di SINI supaya
    # pratinjau alokasi maupun alokasi yang sudah diterapkan sama-sama benar.
    pids = {r.get("product_id") for r in rolls if r.get("product_id")}
    if pids:
        prods = {p["id"]: p for p in await db.products.find(
            {"id": {"$in": list(pids)}}, {"_id": 0, "id": 1, "name": 1, "sku": 1}).to_list(5000)}
        for r in rolls:
            p = prods.get(r.get("product_id")) or {}
            if not r.get("product_name"):
                r["product_name"] = p.get("name", "")
            if not r.get("sku"):
                r["sku"] = p.get("sku", "")
    return rolls


def _roll_base_unit_cost(r: Dict[str, Any]) -> float:
    """Base HPP per unit roll (sebelum landed cost). Fallback ke unit_cost-landed."""
    b = r.get("base_unit_cost")
    if b is not None:
        return float(b or 0)
    uc = r.get("unit_cost")
    return float(uc or 0)


def compute_allocation(rolls: List[Dict[str, Any]], total_cost: float, basis: str = "value") -> Dict[str, Any]:
    """Alokasikan total_cost ke daftar roll. Return {basis, allocations, total_weight}.
    Pembulatan: sisa selisih dibebankan ke roll terakhir agar Σalloc == total_cost."""
    total_cost = round(float(total_cost or 0), 2)
    rolls = [r for r in rolls if float(r.get("length_initial", 0) or 0) > 0]
    n = len(rolls)
    result_basis = basis if basis in ("value", "quantity") else "value"

    def weight_for(r: Dict[str, Any], b: str) -> float:
        ln = float(r.get("length_initial", 0) or 0)
        if b == "value":
            return _roll_base_unit_cost(r) * ln
        return ln  # quantity

    weights = [weight_for(r, result_basis) for r in rolls]
    tw = round(sum(weights), 6)
    if result_basis == "value" and tw <= 0:
        # roll belum punya base cost → fallback ke basis kuantitas
        result_basis = "quantity"
        weights = [weight_for(r, "quantity") for r in rolls]
        tw = round(sum(weights), 6)
    if tw <= 0:  # masih 0 → bagi rata
        weights = [1.0 for _ in rolls]
        tw = float(n) if n else 1.0

    allocations: List[Dict[str, Any]] = []
    running = 0.0
    for i, r in enumerate(rolls):
        ln = float(r.get("length_initial", 0) or 0)
        if i == n - 1:
            alloc = round(total_cost - running, 2)
        else:
            alloc = round(total_cost * (weights[i] / tw), 2)
            running = round(running + alloc, 2)
        per_unit = round(alloc / ln, 6) if ln > 0 else 0.0
        cur_uc = float(r.get("unit_cost") or 0)
        allocations.append({
            "roll_id": r["id"],
            "roll_no": r.get("roll_no", ""),
            "product_id": r.get("product_id", ""),
            "product_name": r.get("product_name", ""),
            "sku": r.get("sku", ""),
            "length": round(ln, 2),
            "weight": round(weights[i], 4),
            "base_unit_cost": round(_roll_base_unit_cost(r), 4),
            "current_unit_cost": round(cur_uc, 4),
            "alloc_amount": alloc,
            "per_unit": per_unit,
            "new_unit_cost": round(cur_uc + per_unit, 4),
        })
    return {"basis": result_basis, "allocations": allocations,
            "total_weight": round(tw, 4), "roll_count": n,
            "allocated_total": round(sum(a["alloc_amount"] for a in allocations), 2)}


async def apply_allocation_to_rolls(voucher_number: str, allocations: List[Dict[str, Any]]) -> int:
    """Terapkan alokasi ke roll (additive). $inc unit_cost(+per_unit) &
    landed_cost_total(+alloc), $push landed_cost_refs. Idempotensi dijaga di router
    (status voucher). Return jumlah roll terupdate."""
    updated = 0
    for a in allocations:
        # Riwayat nilai roll (2026-06) — HPP roll naik karena biaya masuk; jejaknya
        # dibaca layar detail roll & bukti tuduhan selisih.
        before = await db.inventory_rolls.find_one(
            {"id": a["roll_id"]},
            {"_id": 0, "id": 1, "roll_no": 1, "unit_cost": 1, "base_unit_cost": 1,
             "length_remaining": 1, "owner_entity_id": 1, "entity_id": 1})
        # FN-01 — tiap fragmen menerima alokasinya SENDIRI tepat sekali per voucher (guard
        # landed_cost_refs = idempotent retry). Propagasi KN-B17 ke turunan dihapus: turunan kini
        # sudah menjadi target alokasi sendiri (resolve_target_rolls), jadi propagasi = hitung ganda.
        res = await db.inventory_rolls.update_one(
            {"id": a["roll_id"], "landed_cost_refs": {"$ne": voucher_number}},
            {"$inc": {"unit_cost": a["per_unit"], "landed_cost_total": a["alloc_amount"]},
             "$set": {"updated_at": now_iso()},
             "$push": {"landed_cost_refs": voucher_number}})
        # T7 DIBAYAR (2026-06c): jejak ditulis SESUDAH nilainya benar-benar berubah.
        if before and res.modified_count:
            await roll_cost_history.record(
                before, float(before.get("unit_cost") or 0) + float(a["per_unit"]),
                "landed_cost_allocation", actor="voucher biaya masuk",
                ref_type="landed_cost_voucher", ref_id="",
                ref_number=voucher_number)
        updated += res.modified_count
    return updated


async def attach_allocation_names(vouchers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lengkapi nama produk pada baris alokasi voucher yang SUDAH tersimpan.

    Alokasi yang dibuat sebelum perbaikan ini hanya menyimpan `product_id`, dan layar
    dulu mencetak id itu apa adanya sebagai cadangan (`prod_batik_mega` di kolom
    Produk). Melengkapinya saat DIBACA membuat dokumen lama ikut tampil benar tanpa
    migrasi data, dan tidak ada satu pun tempat lain yang perlu tahu soal ini.
    """
    pids = {a.get("product_id") for v in vouchers
            for a in (v.get("allocations") or []) + (v.get("allocation_preview") or [])
            if a.get("product_id")}
    if not pids:
        return vouchers
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list(pids)}}, {"_id": 0, "id": 1, "name": 1, "sku": 1}).to_list(5000)}
    for v in vouchers:
        for key in ("allocations", "allocation_preview"):
            for a in (v.get(key) or []):
                prod = prods.get(a.get("product_id")) or {}
                if not a.get("product_name"):
                    a["product_name"] = prod.get("name", "")
                if not a.get("sku"):
                    a["sku"] = prod.get("sku", "")
    return vouchers


async def build_landed_cost_context(po: Dict[str, Any]) -> Dict[str, Any]:
    """Konteks untuk form: roll yang diterima dari PO + nilai dasar (base value)."""
    rolls = await resolve_target_rolls([po["id"]], po.get("entity_id", ""))
    rows = []
    total_base_value = 0.0
    total_length = 0.0
    for r in rolls:
        ln = float(r.get("length_initial", 0) or 0)
        buc = _roll_base_unit_cost(r)
        bv = round(buc * ln, 2)
        total_base_value += bv
        total_length += ln
        rows.append({
            "roll_id": r["id"], "roll_no": r.get("roll_no", ""),
            "product_id": r.get("product_id", ""), "product_name": r.get("product_name", ""),
            "sku": r.get("sku", ""), "length": round(ln, 2), "unit": r.get("unit", "meter"),
            "base_unit_cost": round(buc, 4), "base_value": bv,
            "current_unit_cost": round(float(r.get("unit_cost") or 0), 4),
            "dye_lot": r.get("dye_lot", ""), "status": r.get("status", ""),
        })
    return {
        "po_id": po["id"], "po_number": po.get("po_number", ""),
        "supplier_name": po.get("supplier_name", ""), "entity_id": po.get("entity_id", ""),
        "roll_count": len(rows), "total_length": round(total_length, 2),
        "total_base_value": round(total_base_value, 2), "rolls": rows,
    }
