"""FASE E — SOURCING PR: routing `purchase|makloon` + realisasi PR → PO / Order Makloon.

Masalah nyata: satu Purchase Requisition sering **campur** — sebagian barang dibeli jadi
(beli-putus ke supplier), sebagian lagi diproduksi lewat **makloon** (kirim bahan ke mitra).
Sebelum Fase E, PR hanya bisa dikonversi 1× menjadi 1 PO untuk SEMUA baris, sehingga tim
purchasing memecah PR manual & jejak kebutuhan → realisasi hilang.

Yang disediakan modul ini:
  * `fulfillment_mode` per BARIS PR (`purchase` | `makloon`), default `purchase`
    (backward-compatible untuk data lama).
  * **Realisasi parsial**: `realize_to_po` (pilih baris) & `realize_to_makloon` (per baris),
    keduanya **idempotent-aman** (baris yang sudah penuh terealisasi ditolak).
  * Status realisasi **turunan** (tidak pernah disimpan ganda):
    `open` → `partially_realized` → `realized` (PR.status jadi `converted` saat penuh).
  * PO hasil realisasi membawa **jejak sourcing**: `contract_id` (kontrak pembelian),
    `supplier_item_id` + `supplier_sku` + nama versi supplier, dan `expected_grade`.
  * `makloon_prefill` — 1 klik dari PR: menurunkan bahan/mitra/kontrak dari **resep proses**
    (reverse lookup output → input) sehingga Wizard Makloon terbuka sudah terisi.

Invarian (verify_data_integrity L4-SRC): INV-SRC-01..05.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from core_utils import (DEFAULT_ENTITY_ID, new_id, next_doc_number, now_iso, parse_decimal,
                        rupiah, safe_doc, timeline_entry)
from db import db
from services import contract_service as cs
from services import supplier_item_service as sis
from services.config_service import compute_order_pricing, evaluate_approval

FULFILLMENT_MODES = ("purchase", "makloon")
REALIZATION_STATUSES = ("open", "partially_realized", "realized")
EPS = 0.001


class SourcingError(ValueError):
    """Pelanggaran aturan sourcing PR (dipetakan ke HTTP 400/409 di router).

    Turunan `ValueError` agar jalur lama (`convert_to_po` / router yang menangkap
    `ValueError`) tetap mengembalikan **400 yang bisa ditindak**, bukan 500."""


# ═══════════════════════════════════════════════════════════════════════════
# 1. NORMALISASI & STATUS TURUNAN
# ═══════════════════════════════════════════════════════════════════════════
def normalize_mode(value: Any) -> str:
    mode = (str(value or "purchase")).strip().lower()
    if mode in ("beli", "buy", "pembelian"):
        mode = "purchase"
    if mode in ("maklon", "subcon", "subkontrak"):
        mode = "makloon"
    if mode not in FULFILLMENT_MODES:
        raise SourcingError(
            f"Mode pemenuhan '{value}' tidak dikenal. Pilihan: {', '.join(FULFILLMENT_MODES)}.")
    return mode


def ensure_line_shape(pr: Dict[str, Any]) -> bool:
    """Isi `line_no` / `fulfillment_mode` / `realized_qty` untuk PR lama (in-place).

    Return True bila ada perubahan (pemanggil yang menyimpan)."""
    changed = False
    for idx, it in enumerate(pr.get("items") or [], start=1):
        if not it.get("line_no"):
            it["line_no"] = idx
            changed = True
        if not it.get("fulfillment_mode"):
            it["fulfillment_mode"] = "purchase"
            changed = True
        if it.get("realized_qty") is None:
            it["realized_qty"] = 0.0
            changed = True
        if it.get("realizations") is None:
            it["realizations"] = []
            changed = True
    return changed


def compute_realization(pr: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkas realisasi PR — SSOT turunan dari `items[].realized_qty`."""
    items = pr.get("items") or []
    total_qty = round(sum(float(it.get("quantity") or 0) for it in items), 3)
    done_qty = round(sum(min(float(it.get("realized_qty") or 0),
                            float(it.get("quantity") or 0)) for it in items), 3)
    lines_done = sum(1 for it in items
                     if float(it.get("realized_qty") or 0) >= float(it.get("quantity") or 0) - EPS
                     and float(it.get("quantity") or 0) > 0)
    if not items or done_qty <= EPS:
        status = "open"
    elif lines_done >= len([i for i in items if float(i.get("quantity") or 0) > 0]):
        status = "realized"
    else:
        status = "partially_realized"
    return {
        "realization_status": status,
        "realized_lines": lines_done, "total_lines": len(items),
        "realized_qty": done_qty, "total_qty": total_qty,
        "realized_pct": round((done_qty / total_qty * 100), 2) if total_qty else 0.0,
        "purchase_lines": sum(1 for it in items if it.get("fulfillment_mode") == "purchase"),
        "makloon_lines": sum(1 for it in items if it.get("fulfillment_mode") == "makloon"),
    }


async def _save_realization(pr: Dict[str, Any], *, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    summary = compute_realization(pr)
    sets: Dict[str, Any] = {
        "items": pr["items"],
        "realization": summary,
        "realization_status": summary["realization_status"],
        "po_ids": sorted({r["ref_id"] for it in pr["items"] for r in (it.get("realizations") or [])
                          if r.get("type") == "purchase_order" and not r.get("voided")}),   # G4-12
        "makloon_order_ids": sorted({r["ref_id"] for it in pr["items"] for r in (it.get("realizations") or [])
                                     if r.get("type") == "makloon_order"}),
        "timeline": pr.get("timeline") or [],
        "updated_at": now_iso(),
    }
    if summary["realization_status"] == "realized":
        sets["status"] = "converted"
        sets["converted_at"] = pr.get("converted_at") or now_iso()
    if extra:
        sets.update(extra)
    # KN-B03 — tulisan akhir sekaligus mencabut kunci saga (bila ada) supaya realisasi
    # berikutnya bisa berjalan; tanpa kunci pun `$unset` tidak berdampak.
    await db.purchase_requisitions.update_one({"id": pr["id"]}, {"$set": sets, "$unset": {"saga_lock": ""}})
    return safe_doc(await db.purchase_requisitions.find_one({"id": pr["id"]}, {"_id": 0}))


async def _load_pr(pr_id: str) -> Dict[str, Any]:
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr:
        raise SourcingError("PR tidak ditemukan.")
    ensure_line_shape(pr)
    return pr


def _so_ids_of_pr(pr: Dict[str, Any]) -> List[str]:
    """Pesanan penjualan yang MELAHIRKAN permintaan pembelian ini (P-0).

    Sumbernya jejak yang sudah ada — bukan tebakan: `restock_service` menulis
    `source="so_repeat"` + `source_ref_id=<so_id>` di kepala PR, dan baris PR bisa
    membawa `source_ref_id` sendiri untuk PR campur. Dikembalikan sebagai daftar
    tanpa duplikat supaya papan PO bisa merunut Nama Sales tanpa mengetik apa pun.
    """
    out: List[str] = []
    kepala = (pr.get("source_ref_id") or "").strip()
    if kepala and (pr.get("source") or "") in ("so_repeat", "so"):
        out.append(kepala)
    for it in pr.get("items") or []:
        sid = (it.get("source_ref_id") or "").strip()
        if sid and sid not in out:
            out.append(sid)
    return out


async def _sales_of_so_ids(so_ids: List[str]) -> Dict[str, str]:
    """Runut **Nama Sales** dari pesanan penjualan yang melahirkan PO ini (P-0).

    Ini bagian yang membuat rantai PO→PR→SO ADA GUNANYA: papan PO (FASE P) memuat
    kolom **Nama Sales**, dan sebelum ini kolom itu mustahil diisi tanpa mengetik
    ulang — terukur **0/14** PO menyimpan `pr_id` (DRIFT D3).

    DUA ATURAN YANG SENGAJA:
    1. **Di-snapshot saat PO lahir**, bukan dihitung saat dibaca. Kalau akun sales
       kelak dinonaktifkan atau namanya berubah, PO lama tetap menyebut siapa yang
       benar-benar menjual — prinsip "snapshot historis" yang sama dipakai kategori
       & harga di dokumen lain.
    2. **KOSONG kalau memang tidak ada**, bukan diisi nama pembuat PO. PO pembelian
       rutin (stok menipis, reorder) TIDAK punya sales — memaksa isinya akan membuat
       papan PO berbohong, dan itu lebih buruk daripada sel kosong yang jujur.

    `sales_orders` menyimpan `created_by` = **id pengguna** (bukan nama) dan
    `sales_name` = nama tampilan; keduanya dipakai apa adanya, tidak ditebak.
    """
    if not so_ids:
        return {"sales_user_id": "", "sales_name": ""}
    rows = await db.sales_orders.find(
        {"id": {"$in": list(so_ids)}},
        {"_id": 0, "id": 1, "created_by": 1, "sales_name": 1, "created_at": 1},
    ).to_list(50)
    if not rows:
        return {"sales_user_id": "", "sales_name": ""}
    # Kalau satu PR menggabungkan beberapa SO, pakai yang TERTUA (pesanan pemicu).
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    for r in rows:
        nama = (r.get("sales_name") or "").strip()
        uid = (r.get("created_by") or "").strip()
        if nama or uid:
            return {"sales_user_id": uid, "sales_name": nama}
    return {"sales_user_id": "", "sales_name": ""}


#: Field asal-dokumen yang WAJIB ada di SETIAP PO, apa pun jalur lahirnya (P-0).
#: Ditulis eksplisit supaya papan PO (FASE P) tidak perlu membedakan "field tidak ada"
#: dari "tidak ada sales-nya" — dua hal yang tampak sama di layar tetapi beda artinya.
PO_ORIGIN_EMPTY: Dict[str, Any] = {
    "pr_id": "", "pr_number": "", "source": "", "source_so_ids": [],
    "sales_user_id": "", "sales_name": "",
}


async def po_origin_from_pr(pr: Optional[Dict[str, Any]], *,
                            source: str = "pr") -> Dict[str, Any]:
    """SATU definisi "PO ini asalnya dari mana & siapa sales-nya" (P-0).

    Dipakai KETIGA jalur lahirnya PO — realisasi PR (`realize_to_po`), award RFQ
    (`rfq_service.award`), dan PO manual (`routers/purchase_orders`) — supaya
    ketiganya tidak bisa diam-diam berbeda. Sebelum P-0 hanya jalur PR yang menulis
    `pr_id`, jadi isi kolom papan PO bergantung pintu masuknya: cacat yang gejalanya
    bukan galat melainkan **kolom yang kosong untuk sebagian dokumen saja**.

    `pr` None/kosong → seluruh field ADA tetapi kosong (bukan tidak ada).
    """
    if not pr:
        return dict(PO_ORIGIN_EMPTY)
    so_ids = _so_ids_of_pr(pr)
    return {
        "pr_id": pr.get("id", ""), "pr_number": pr.get("number", ""),
        "source": source, "source_so_ids": so_ids,
        **await _sales_of_so_ids(so_ids),
    }



def _open_lines(pr: Dict[str, Any], mode: str, line_nos: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    want = {int(n) for n in (line_nos or [])}
    out = []
    for it in pr.get("items") or []:
        if it.get("fulfillment_mode") != mode:
            continue
        remaining = float(it.get("quantity") or 0) - float(it.get("realized_qty") or 0)
        if remaining <= EPS:
            continue
        if want and int(it.get("line_no") or 0) not in want:
            continue
        out.append(it)
    return out


def _record(it: Dict[str, Any], *, kind: str, ref_id: str, ref_number: str,
            qty: float, actor: str) -> None:
    it.setdefault("realizations", []).append({
        "type": kind, "ref_id": ref_id, "ref_number": ref_number,
        "qty": round(float(qty), 3), "at": now_iso(), "by": actor,
    })
    it["realized_qty"] = round(float(it.get("realized_qty") or 0) + float(qty), 3)


# ═══════════════════════════════════════════════════════════════════════════
# 2. REALISASI → PURCHASE ORDER (baris `purchase`)
# ═══════════════════════════════════════════════════════════════════════════
async def resolve_line_sourcing(*, supplier_id: str, product_id: str, qty: float,
                                entity_id: str, est_price: float = 0.0,
                                unit: str = "") -> Dict[str, Any]:
    """Gabungkan kontrak pembelian + barang supplier → harga, satuan, nama & grade.

    Prioritas harga: **kontrak pembelian** → est_price PR → barang supplier (`last_price`)
    → price-list supplier → harga produk. Semua langkah dicatat di `explain[]` agar auditable.
    """
    explain: List[str] = []
    out: Dict[str, Any] = {"price": 0.0, "unit": unit or "", "source": "",
                           "contract_id": "", "contract_number": "",
                           "supplier_item_id": "", "supplier_sku": "",
                           "supplier_item_name": "", "supplier_uom": "",
                           "supplier_conv_factor": 0, "expected_grade": "", "explain": explain}
    contract = await cs.resolve_active(partner_id=supplier_id, contract_type="purchase",
                                       product_id=product_id, entity_id=entity_id)
    sup_item = await sis.resolve_for_product(supplier_id=supplier_id, product_id=product_id,
                                            entity_id=entity_id)
    if sup_item:
        out.update({"supplier_item_id": sup_item["id"], "supplier_sku": sup_item["supplier_sku"],
                    "supplier_item_name": sup_item.get("supplier_item_name", ""),
                    # FASE F-1 — satuan & faktor versi supplier diteruskan ke baris PO
                    # supaya penerimaan bisa menerima qty dalam satuan supplier.
                    "supplier_uom": sup_item.get("supplier_uom", ""),
                    "supplier_conv_factor": sup_item.get("conv_factor", 0)})
        if sup_item.get("expected_grade"):
            out["expected_grade"] = sup_item["expected_grade"]
        explain.append(f"Barang supplier: {sup_item['supplier_sku']} — "
                       f"{sup_item.get('supplier_item_name') or '-'} "
                       f"(1 {sup_item.get('supplier_uom')} = {sup_item.get('conv_factor')} "
                       f"{sup_item.get('base_unit')})")
    if contract:
        rate = parse_decimal(contract.get("tariff_rate"), 2)
        out.update({"contract_id": contract["id"], "contract_number": contract.get("contract_number", "")})
        if contract.get("expected_grade"):
            out["expected_grade"] = contract["expected_grade"]
        if rate > 0:
            out.update({"price": rate, "source": "contract",
                        "unit": contract.get("tariff_basis") or out["unit"]})
            explain.append(f"Harga dari kontrak {contract.get('contract_number')}: "
                           f"{rupiah(rate)} / {contract.get('tariff_basis')}")
        moq = parse_decimal(contract.get("moq"))
        if moq > 0 and qty < moq:
            explain.append(f"⚠️ Qty {qty:g} di bawah MOQ kontrak {moq:g} — konfirmasi ke supplier.")
            out["below_moq"] = True
    if out["price"] <= 0 and est_price > 0:
        out.update({"price": round(est_price, 2), "source": "pr_estimate"})
        explain.append(f"Harga memakai estimasi PR: {rupiah(est_price)}")
    if out["price"] <= 0 and sup_item and parse_decimal(sup_item.get("last_price"), 2) > 0:
        out.update({"price": parse_decimal(sup_item["last_price"], 2), "source": "supplier_item",
                    "unit": sup_item.get("supplier_uom") or out["unit"]})
        explain.append(f"Harga terakhir barang supplier: {rupiah(out['price'])} / {out['unit']}")
    if out["price"] <= 0:
        from services.supplier_service import resolve_price
        resolved = await resolve_price(supplier_id, product_id, qty)
        # Hanya entri price-list sungguhan; fallback master produk di resolve_price ditangani langkah berikut (berkonversi).
        if resolved.get("found") and float(resolved.get("price", 0) or 0) > 0:
            out.update({"price": round(float(resolved["price"]), 2), "source": "price_list"})
            if resolved.get("unit"):
                out["unit"] = resolved["unit"]
            explain.append(f"Harga dari price-list supplier: {rupiah(out['price'])}")
    if out["price"] <= 0:
        prod = await db.products.find_one({"id": product_id}, {"_id": 0}) or {}
        fallback = float(prod.get("harga_pokok") or 0) or float(prod.get("price") or 0)
        base_unit = prod.get("base_unit") or "meter"
        # Trial 22 Okt (D3) — harga master = per SATUAN DASAR; baris PO memakai satuan dokumen → konversi.
        if fallback > 0 and out["unit"] and out["unit"] != base_unit:
            from services import uom_rules_service as _uomr
            try:
                f = float((await _uomr.convert_with_trail(prod, 1, out["unit"], base_unit))["factor"])
                explain.append(f"Harga master {rupiah(fallback)}/{base_unit} → {rupiah(fallback * f)}/{out['unit']}")
                fallback = fallback * f
            except _uomr.UomRuleError:
                out["unit"] = base_unit   # tanpa faktor: biarkan per satuan dasar (pemanggil mengonversi qty)
        out.update({"price": round(fallback, 2), "source": "product_master"})
        explain.append(f"Harga dari master produk: {rupiah(fallback)} / {out['unit'] or base_unit}")
    return out


async def price_in_unit(prod: Dict[str, Any], price: float, price_unit: str, doc_unit: str,
                        explain: Optional[List[str]] = None) -> float:
    """Trial 22 Okt (D3) — harga per `price_unit` → harga per `doc_unit` (satuan baris PO). 400-style error via
    UomRuleError bila tak ada faktor; pemanggil memutuskan pesan."""
    if price <= 0 or not price_unit or not doc_unit or price_unit == doc_unit:
        return price
    from services import uom_rules_service as _uomr
    f = float((await _uomr.convert_with_trail(prod, 1, doc_unit, price_unit))["factor"])
    if explain is not None:
        explain.append(f"Harga {rupiah(price)}/{price_unit} → {rupiah(price * f)}/{doc_unit}")
    return round(price * f, 2)


async def realize_to_po(pr_id: str, *, supplier_id: str, actor: Dict[str, Any],
                        warehouse_id: str = "", line_nos: Optional[List[int]] = None,
                        expected_delivery_date: str = "", notes: str = "") -> Dict[str, Any]:
    """Realisasikan baris PR ber-mode `purchase` menjadi **satu PO** (kasus satu PR dari `realize_many_to_po`).

    Baris `makloon` DIABAIKAN (dipenuhi via Order Makloon) sehingga PR campur tidak
    lagi harus dipecah manual. PR menjadi `converted` hanya bila SEMUA baris terealisasi.
    """
    return await realize_many_to_po([{"pr_id": pr_id, "line_nos": line_nos or []}], supplier_id=supplier_id,
                                    actor=actor, warehouse_id=warehouse_id,
                                    expected_delivery_date=expected_delivery_date, notes=notes)


async def merge_suggestions(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """UAT 24 Okt (P15.2) — kelompok PR approved yang masih punya baris PEMBELIAN terbuka, per (badan usaha, lokasi
    tujuan, supplier). Supplier = `preferred_supplier_id` PR, atau supplier yang layak untuk SEMUA barangnya (kontrak
    aktif / barang supplier) bila PR belum menyebut supplier. Hanya kelompok ≥ 2 PR yang disarankan."""
    from fastapi import HTTPException as _HE
    from services import site_receiving_service as srs
    today = now_iso()[:10]
    groups: Dict[tuple, Dict[str, Any]] = {}
    # UAT 24 Okt (audit UI tahap 2) — G4-10: supplier badan usaha grup (partner_kind=entity) TIDAK disarankan —
    # PO gabungannya pasti ditolak `assert_supplier_not_group_entity` (dulu saran "CV Cipta Sandang" membuka
    # pop-up gabung dengan supplier kosong). Dokumen supplier di-cache sekali untuk nama & kode.
    sup_cache: Dict[str, Dict[str, Any]] = {}

    async def _sup(sid: str) -> Dict[str, Any]:
        if sid not in sup_cache:
            sup_cache[sid] = (await db.suppliers.find_one(
                {"id": sid}, {"_id": 0, "name": 1, "code": 1, "partner_kind": 1, "group_entity_id": 1,
                              "status": 1})) or {}
        return sup_cache[sid]

    def _buyable(doc: Dict[str, Any]) -> bool:
        return bool(doc) and doc.get("partner_kind") != "entity" and not doc.get("group_entity_id") \
            and doc.get("status") != "inactive"

    async for pr in db.purchase_requisitions.find({**query, "status": {"$in": ["approved", "converted"]}}, {"_id": 0}):
        ensure_line_shape(pr)
        lines = _open_lines(pr, "purchase")
        lines = [it for it in lines if it.get("product_id")]
        if not lines:
            continue
        ent = pr.get("entity_id") or DEFAULT_ENTITY_ID
        try:
            dest = await srs.resolve_destination(ent, pr.get("ship_to_site_id", ""), pr.get("warehouse_id", ""))
        except _HE:
            continue
        sups = [pr["preferred_supplier_id"]] if pr.get("preferred_supplier_id") else []
        if not sups:
            pids = [it["product_id"] for it in lines]
            sets = []
            for pid in pids:
                ok = {c["partner_id"] async for c in db.supplier_contracts.find(
                    {"product_id": pid, "status": "active", "contract_type": "purchase",
                     "$or": [{"valid_to": {"$in": [None, ""]}}, {"valid_to": {"$gte": today}}]}, {"_id": 0, "partner_id": 1})}
                ok |= {si["supplier_id"] async for si in db.supplier_items.find({"product_id": pid, "status": "active"},
                                                                               {"_id": 0, "supplier_id": 1})}
                sets.append(ok)
            sups = sorted(set.intersection(*sets)) if sets else []
        sups = [sid for sid in sups if _buyable(await _sup(sid))]
        if not sups:
            continue
        value = round(sum((float(it["quantity"]) - float(it.get("realized_qty") or 0)) * float(it.get("est_price") or 0)
                          for it in lines), 2)
        row = {"pr_id": pr["id"], "number": pr.get("number", ""), "needed_by_date": pr.get("needed_by_date", ""),
               "lines": len(lines), "est_value": value, "preferred": bool(pr.get("preferred_supplier_id")),
               "skus": sorted({it.get("sku") or it["product_id"] for it in lines})}
        for sid in sups:
            g = groups.setdefault((ent, dest["warehouse"]["id"], sid), {
                "entity_id": ent, "warehouse_id": dest["warehouse"]["id"], "site_id": dest.get("site_id", ""),
                "site_name": dest.get("site_name") or dest["warehouse"].get("name", ""),
                # G4-10 — nama gudang tujuan = pembeda dua saran berlokasi sama (kunci kelompok memakai gudang).
                "warehouse_name": dest["warehouse"].get("name", ""), "supplier_id": sid, "prs": []})
            g["prs"].append(row)
    out = []
    for (ent, wid, sid), g in groups.items():
        if len(g["prs"]) < 2:
            continue
        sdoc = await _sup(sid)
        dates = sorted(d for d in (p["needed_by_date"] for p in g["prs"]) if d)
        shared_sku = len({s for p in g["prs"] for s in p["skus"]}) < sum(len(p["skus"]) for p in g["prs"])
        g.update({"supplier_name": sdoc.get("name") or sid, "supplier_code": sdoc.get("code", ""),
                  "pr_count": len(g["prs"]),
                  "est_value": round(sum(p["est_value"] for p in g["prs"]), 2),
                  "needed_from": dates[0] if dates else "", "needed_to": dates[-1] if dates else "",
                  "shared_sku": shared_sku,
                  "score": len(g["prs"]) * 10 + (5 if shared_sku else 0) + sum(1 for p in g["prs"] if p["preferred"])})
        out.append(g)
    out.sort(key=lambda g: (-g["score"], -g["est_value"]))
    return out


async def realize_many_to_po(pr_refs: List[Dict[str, Any]], *, supplier_id: str, actor: Dict[str, Any],
                             warehouse_id: str = "", ship_to_site_id: str = "",
                             expected_delivery_date: str = "", notes: str = "") -> Dict[str, Any]:
    """UAT 24 Okt (P15.1) — GABUNG beberapa PR (badan usaha, lokasi tujuan & supplier sama) menjadi SATU PO.

    Baris SKU kembar dari PR berbeda dilebur menjadi SATU baris PO (KN-B15) ber-`pr_allocations[]`; tiap PR mencatat
    realisasinya sebesar alokasinya dan menaut ke PO. Semua PR diklaim atomik (gagal satu → semua dilepas).
    """
    from routers.purchase_orders import _create_inbound_tasks_for_po
    from services import grade_service
    from services import po_board_service as _board      # FASE P — papan PO per lini
    from services.supplier_service import assess_price_deviation
    from services.config_service import get_effective_settings

    seen_ids: List[str] = []
    for ref in pr_refs or []:
        if ref.get("pr_id") and ref["pr_id"] not in seen_ids:
            seen_ids.append(ref["pr_id"])
    if not seen_ids:
        raise SourcingError("Pilih minimal satu PR.")
    want_lines = {r["pr_id"]: list(r.get("line_nos") or []) for r in pr_refs if r.get("pr_id")}
    multi = len(seen_ids) > 1
    from services import special_order_link as _odl
    prs: List[Dict[str, Any]] = []
    lines_by_pr: Dict[str, List[Dict[str, Any]]] = {}
    for pid in seen_ids:
        pr = await _load_pr(pid)
        # PR dari Pesanan Khusus yang lahir sebelum SKU R&D ada → baris diisi SKU hasil R&D (bukan "non-katalog").
        if await _odl.repair_pr_lines(pr):
            pr = await _load_pr(pid)
        tag = f"{pr.get('number')}: " if multi else ""
        if pr.get("status") not in ("approved", "converted"):
            raise SourcingError(
                f"{tag}Hanya PR 'approved' yang bisa direalisasikan (status sekarang: {pr.get('status')}).")
        plines = _open_lines(pr, "purchase", want_lines.get(pid))
        if not plines:
            raise SourcingError(f"{tag}Tidak ada baris PEMBELIAN yang masih perlu direalisasikan "
                                "(sudah terealisasi atau semua baris ber-mode makloon).")
        if [it for it in plines if not it.get("product_id")]:
            raise SourcingError(f"{tag}Ada baris tanpa produk katalog. Bila berasal dari Pesanan Khusus, selesaikan ACC "
                                "spesifikasi di R&D agar SKU lahir; selain itu pilih produk untuk baris tersebut dulu.")
        prs.append(pr)
        lines_by_pr[pid] = plines
    pr = prs[0]
    if multi:
        ents = {p.get("entity_id") or DEFAULT_ENTITY_ID for p in prs}
        if len(ents) > 1:
            raise SourcingError("PR yang dipilih milik badan usaha berbeda — satu PO hanya untuk satu badan usaha.")
        prefs = {p.get("preferred_supplier_id") for p in prs if p.get("preferred_supplier_id")}
        if not supplier_id and len(prefs) == 1:
            supplier_id = next(iter(prefs))
        if supplier_id and prefs - {supplier_id}:
            others = ", ".join(p["number"] for p in prs if p.get("preferred_supplier_id") not in ("", None, supplier_id))
            raise SourcingError(f"PR {others} ditujukan ke supplier lain — gabung hanya PR untuk supplier yang sama.")

    supplier_id = supplier_id or pr.get("preferred_supplier_id", "")
    if not supplier_id:
        raise SourcingError("Supplier wajib dipilih untuk realisasi ke PO.")
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not supplier:
        raise SourcingError("Supplier tidak ditemukan.")
    # FASE E-7 (E7.2) — KEBOCORAN yang terbukti sesi 2026-08-11: `POST /purchase-orders`
    # sudah dipagari, tetapi PR → `convert-to-po`/`realize-po` memanggil fungsi INI
    # langsung sehingga PO biasa ke badan usaha grup tetap lahir (bukti: KSC/PO-00013).
    # Pagar dipasang di lapis service supaya SEMUA pintu (router PR, convert, realisasi
    # per-baris) ikut terjaga — bukan ditambal satu-satu di setiap router.
    # HTTPException 409 SENGAJA (bukan SourcingError) supaya kalimat menuntunnya utuh
    # sampai ke pengguna; router hanya menangkap SourcingError.
    from services import group_partner_service as _grp
    await _grp.assert_supplier_not_group_entity(
        supplier, doc_label="Pesanan Pembelian (PO) hasil realisasi PR")
    entity_id = pr.get("entity_id") or DEFAULT_ENTITY_ID
    # UAT 24 Okt (P9) — tujuan PO = lokasi PR (atau lokasi gudang pilihan) → gudang penerimaan aktif lokasi itu.
    from fastapi import HTTPException as _HE
    from services import site_receiving_service as srs
    async def _dest_of(p: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if ship_to_site_id or warehouse_id:
                return await srs.resolve_destination(entity_id, ship_to_site_id if not warehouse_id else "", warehouse_id)
            return await srs.resolve_destination(entity_id, p.get("ship_to_site_id", ""), p.get("warehouse_id", ""))
        except _HE as exc:
            raise SourcingError(str(exc.detail) if exc.status_code != 400 or "wajib" not in str(exc.detail)
                                else "Lokasi kirim wajib dipilih untuk realisasi ke PO.")
    _dest = await _dest_of(pr)
    if multi and not (ship_to_site_id or warehouse_id):
        for p in prs[1:]:
            d2 = await _dest_of(p)
            if d2["warehouse"]["id"] != _dest["warehouse"]["id"]:
                raise SourcingError(f"PR {pr['number']} dikirim ke {_dest.get('site_name') or _dest['warehouse']['name']}, "
                                    f"{p['number']} ke {d2.get('site_name') or d2['warehouse']['name']} — satu PO hanya "
                                    "untuk satu lokasi tujuan.")
    warehouse = _dest["warehouse"]
    warehouse_id = warehouse["id"]
    raw_items: List[Dict[str, Any]] = []
    used_contracts: set = set()
    used_items: List[tuple] = []
    # P15.1 — baris dari banyak PR dilebur per produk (satu produk = satu baris PO, KN-B15), alokasi per PR dicatat.
    merged: Dict[str, Dict[str, Any]] = {}
    for p in prs:
        for it in lines_by_pr[p["id"]]:
            q = round(float(it["quantity"]) - float(it.get("realized_qty") or 0), 3)
            m = merged.setdefault(it["product_id"], {"product_id": it["product_id"], "unit": it.get("unit") or "",
                                                     "est_price": 0.0, "qty": 0.0, "allocations": [], "line_no": it.get("line_no")})
            if (it.get("unit") or "") != m["unit"]:
                raise SourcingError(f"{it.get('sku') or it['product_id']}: satuan di {p['number']} ({it.get('unit')}) beda dari "
                                    f"PR lain ({m['unit']}) — samakan satuannya atau realisasikan terpisah.")
            m["qty"] = round(m["qty"] + q, 3)
            m["est_price"] = m["est_price"] or float(it.get("est_price") or 0)
            m["allocations"].append({"pr_id": p["id"], "pr_number": p.get("number", ""), "line_no": it.get("line_no"),
                                     "qty": q})
    for it in merged.values():
        prod = await db.products.find_one({"id": it["product_id"]}, {"_id": 0})
        if not prod:
            raise SourcingError(f"Produk {it['product_id']} tidak ditemukan.")
        qty = it["qty"]
        base_unit = prod.get("base_unit") or "meter"
        doc_unit = it.get("unit") or base_unit
        src = await resolve_line_sourcing(
            supplier_id=supplier_id, product_id=prod["id"], qty=qty, entity_id=entity_id,
            est_price=float(it.get("est_price") or 0), unit=doc_unit)
        # Trial 22 Okt (D1/D4) — baris PO tetap dalam SATUAN PR (dulu label satuan ikut sumber harga, mis. satuan
        # supplier, sementara angkanya masih qty PR → 1.000 yard berlabel meter). Harga per satuan sumber dikonversi
        # ke satuan baris; satuan & qty dasar + jejak konversi disimpan seperti PO manual.
        from services import uom_rules_service as _uomr
        try:
            price = await price_in_unit(prod, float(src["price"] or 0), src["unit"] or doc_unit, doc_unit, src["explain"])
            trail = await _uomr.convert_with_trail(prod, qty, doc_unit, base_unit, context="purchase_order")
        except _uomr.UomRuleError as exc:
            raise SourcingError(f"{prod.get('sku', '')}: {exc}") from exc
        row = {
            "product_id": prod["id"], "sku": prod["sku"], "product_name": prod["name"],
            "quantity": qty, "unit": doc_unit,
            "base_unit": base_unit, "quantity_base": trail["base_qty"], "uom_trail": trail,
            "price": price, "discount_percent": 0, "received_qty": 0.0,
            # FASE E — jejak sourcing pada baris PO
            "contract_id": src["contract_id"], "contract_number": src["contract_number"],
            "supplier_item_id": src["supplier_item_id"], "supplier_sku": src["supplier_sku"],
            "supplier_item_name": src["supplier_item_name"],
            "supplier_uom": src.get("supplier_uom", ""),
            "supplier_conv_factor": src.get("supplier_conv_factor", 0),
            "price_source": src["source"], "sourcing_explain": src["explain"],
            "pr_line_no": it.get("line_no"),
            "pr_allocations": it["allocations"],
            "pr_ids": sorted({a["pr_id"] for a in it["allocations"]}),
        }
        if src["expected_grade"]:
            row["expected_grade"] = src["expected_grade"]
            row["expected_grade_source"] = "supplier_contract" if src["contract_id"] else "supplier_item"
        raw_items.append(row)
        if src["contract_id"]:
            used_contracts.add(src["contract_id"])
        if src["supplier_item_id"]:
            used_items.append((src["supplier_item_id"], src["price"]))   # harga per satuan barang supplier

    from services.po_line_guard import duplicate_line_message
    _dup_msg = duplicate_line_message([r["product_id"] for r in raw_items])  # KN-B15 jalur PR→PO
    if _dup_msg:
        raise SourcingError(_dup_msg)
    pricing = await compute_order_pricing(raw_items, entity_id, 0.0, cfg_section="purchasing")
    items = pricing["items"]
    total_amount = pricing["total_amount"]
    grand_total = pricing["grand_total"]

    appr = await evaluate_approval("purchase_order", total_amount, entity_id)
    needs_approval = appr["requires_approval"]
    required_role = appr["required_role"]
    approval_reason = "amount_threshold" if needs_approval else ""
    settings = await get_effective_settings(entity_id)
    threshold = float(settings.get("purchasing", {}).get("price_deviation_approval_percent", 10.0) or 10.0)
    price_deviation = await assess_price_deviation(supplier_id, items, threshold)
    if price_deviation["flagged"]:
        needs_approval = True
        required_role = required_role or "manager"
        approval_reason = "price_deviation" if not approval_reason else "amount_threshold+price_deviation"

    sup_contact = " | ".join([x for x in [supplier.get("pic_name", ""), supplier.get("phone", "")] if x])
    now = now_iso()
    actor_name = actor.get("name", "Admin")
    # P-0 — runut asal dokumen & Nama Sales SEBELUM PO dibentuk, lewat SATU definisi
    # bersama (`po_origin_from_pr`) yang juga dipakai jalur award RFQ & PO manual.
    _origin = await po_origin_from_pr(pr, source="pr")
    so_union = sorted({s for p in prs for s in _so_ids_of_pr(p)})
    if multi:
        _origin.update({"source_so_ids": so_union, **await _sales_of_so_ids(so_union)})
    numbers = [p["number"] for p in prs]
    po = {
        "id": new_id("po"),
        "po_number": await next_doc_number("purchase_orders", "po_number", "PO-", entity_id=entity_id),
        "supplier_id": supplier_id, "supplier_name": supplier.get("name", ""),
        "supplier_contact": sup_contact, "supplier_npwp": supplier.get("npwp", ""),
        "warehouse_id": warehouse_id, "warehouse_name": warehouse["name"],
        "warehouse_city": warehouse.get("city", ""),
        "ship_to_site_id": _dest["site_id"], "ship_to_site_name": _dest["site_name"],
        "items": items, "total_amount": total_amount, "entity_id": entity_id,
        "items_discount_total": pricing["items_discount_total"],
        "order_discount_percent": pricing["order_discount_percent"],
        "order_discount_amount": pricing["order_discount_amount"],
        "discount_total": pricing["discount_total"],
        "net_subtotal": pricing["net_subtotal"],
        "dpp": pricing["dpp"], "ppn_rate": pricing["ppn_rate"],
        "ppn_mode": pricing["ppn_mode"], "is_pkp": pricing["is_pkp"],
        "ppn_amount": pricing["ppn_amount"], "grand_total": grand_total, "tax_mode": "",
        "expected_delivery_date": expected_delivery_date or pr.get("needed_by_date", ""),
        "notes": notes or f"Dari {', '.join(numbers)}",
        "status": "waiting_approval" if needs_approval else "pending",
        "approval_required": needs_approval, "required_approval_role": required_role,
        "approval_status": "pending" if needs_approval else "not_required",
        "approval_amount": total_amount,
        "approval_reason": approval_reason, "price_deviation": price_deviation,
        "amount_paid": 0.0, "returned_amount": 0.0, "outstanding": round(grand_total, 2),
        "payment_status": "unpaid", "payments": [],
        "source_pr_id": pr["id"], "source_pr_number": pr["number"],
        "source_pr_line_nos": [it.get("line_no") for it in lines_by_pr[pr["id"]]],
        # P15.1 — PO gabungan: SEMUA PR asal (`pr_id` tetap PR pertama demi pembaca lama).
        "pr_ids": [p["id"] for p in prs], "pr_numbers": numbers,
        "source_pr_lines": {p["id"]: [it.get("line_no") for it in lines_by_pr[p["id"]]] for p in prs},
        "merged_from_prs": multi,
        # P-0 (prasyarat FASE P, 2026-08-20) — nama field KANONIK untuk rantai
        # PO → PR → SO. Sebelum ini hanya ada `source_pr_*` yang **tidak pernah
        # dibaca siapa pun**, sehingga papan PO tidak bisa menjawab "PO ini untuk
        # pesanan siapa" dan kolom Nama Sales akan selamanya kosong.
        # `source_so_ids` diturunkan dari PR (PR hasil "ulangi pesanan" menyimpan
        # `source="so_repeat"` + `source_ref_id`), bukan diketik.
        "pr_id": pr["id"], "pr_number": pr["number"], "source": "pr",
        "source_so_ids": so_union,
        # P-0 — kolom "Nama Sales" papan PO: DIRUNUT dari SO asal, tidak diketik.
        # Sengaja KOSONG untuk PO pembelian rutin (lihat `_sales_of_so_ids`).
        **_origin,
        # FASE P — papan PO per lini: progres tahap ADA sejak PO lahir (kosong).
        **_board.PO_BOARD_EMPTY,
        "contract_ids": sorted(used_contracts),
        # R6.3 — Budget Control: tag anggaran (default akun Persediaan bila tak di-tag)
        "budget_dimension": "", "budget_key": "",
        "version": 1, "amendments": [],
        "timeline": (
            [timeline_entry("created", f"PO dibuat dari {', '.join(numbers)}", actor_name,
                            f"{len(items)} item · {rupiah(total_amount)}")]
            + ([timeline_entry("submitted_for_approval", f"Menunggu persetujuan {required_role}",
                               actor_name,
                               f"deviasi harga +{price_deviation['max_deviation_pct']}%"
                               if price_deviation["flagged"] else "nilai melebihi batas")]
               if needs_approval else [])
        ),
        "created_by": actor_name, "created_by_id": actor.get("id", ""),
        "created_at": now, "updated_at": now,
    }
    # Fase A · PS-09/D-19 — grade: hormati grade dari kontrak/barang supplier, sisanya diturunkan.
    await grade_service.stamp_expected_grade(po["items"], allow_derive=True, context="PO dari PR")
    # R6.3 — Budget Control: PO hasil realisasi PR WAJIB tunduk aturan anggaran yang sama
    #        dengan PO manual (mode off/warn/block per entitas).
    from services import budget_service
    try:
        budget_check = await budget_service.enforce_po_budget(po, "po_create", actor)
    except ValueError as exc:
        raise SourcingError(str(exc)) from exc
    po["budget_check"] = budget_check
    if budget_check.get("warnings"):
        po["timeline"].append(timeline_entry(
            "budget_warning", "Peringatan anggaran", actor_name,
            " · ".join(budget_check["warnings"])[:400]))
    # KN-B03 — klaim ATOMIK PR sebelum PO nyata dibuat: dua realisasi bersamaan → tepat
    # satu PO (yang lain 409), bukan dua PO + tugas gudang ganda dengan PR mencatat satu.
    from services import atomic_claim as _saga
    claimed: List[tuple] = []
    try:
        for p in prs:
            got = await _saga.claim("purchase_requisitions", p["id"], "pr_realize_to_po",
                                    precondition={"status": p.get("status")}, actor=actor.get("name", ""))
            claimed.append((p["id"], (got.get(_saga.LOCK) or {}).get("token", "")))
    except Exception:
        for cid, tok in claimed:   # P15.1 — gagal klaim satu PR → lepas semua yang sudah diklaim
            await _saga.release("purchase_requisitions", cid, tok)
        raise
    from services import line_scope as _lines            # FASE L
    await _lines.stamp_doc(db, po)
    await db.purchase_orders.insert_one(dict(po))
    # FASE G-4 — PO hasil realisasi PR menaut ke PR-nya (dua arah).
    from services import doc_refs_service as _refs
    for p in prs:
        await _refs.safe_link(("purchase_order", po["id"]),
                              ("purchase_requisition", p["id"]), "parent",
                              note="realisasi permintaan pembelian" + (" (PO gabungan)" if multi else ""))
    if not needs_approval:
        await _create_inbound_tasks_for_po(po)
    else:
        from services.notification_service import notify_po_awaiting_approval
        await notify_po_awaiting_approval(po)

    for cid in used_contracts:
        await cs.mark_used(cid)
    for sid, price in used_items:
        await sis.mark_used(sid, price)

    updated_all: List[Dict[str, Any]] = []
    for p in prs:
        plines = lines_by_pr[p["id"]]
        for it in plines:
            _record(it, kind="purchase_order", ref_id=po["id"], ref_number=po["po_number"],
                    qty=float(it["quantity"]) - float(it.get("realized_qty") or 0), actor=actor_name)
        p.setdefault("timeline", []).append(timeline_entry(
            "realized_po", f"{len(plines)} baris direalisasi ke {po['po_number']}"
            + (f" (gabungan {', '.join(numbers)})" if multi else ""), actor_name, f"{rupiah(total_amount)}"))
        updated_all.append(await _save_realization(p, extra={
            "po_id": p.get("po_id") or po["id"],
            "po_number": p.get("po_number") or po["po_number"],
            "converted_by": actor_name,
        }))
    return {"pr": updated_all[0], "prs": updated_all, "po": safe_doc(po)}


# UAT 24 Okt (audit UI tahap 2) — G4-12: PO yang DIBATALKAN/DITOLAK dulu tidak mengembalikan baris PR-nya,
# sehingga PR tetap "Jadi PO" menunjuk PO mati (terbukti: route `POST /purchase-orders/{id}/cancel` hanya
# mengubah PO & tugas gudang). Dua fungsi di bawah membalik realisasinya; router PO perlu memanggil
# `release_po_realizations` setelah PO batal/ditolak (lihat laporan G4 — berkas router bukan milik G4).
PO_DEAD_STATUSES = ("cancelled", "rejected")


def _void_po_realizations(pr: Dict[str, Any], po_id: str, *, actor: str, reason: str) -> tuple:
    """Tandai realisasi baris PR ke `po_id` sebagai batal (`voided`) & kurangi `realized_qty`.
    Murni (tanpa DB) — dikembalikan (jumlah baris, qty dilepas, nomor PO)."""
    lines, qty, number = 0, 0.0, ""
    for it in pr.get("items") or []:
        for r in it.get("realizations") or []:
            if r.get("type") != "purchase_order" or r.get("ref_id") != po_id or r.get("voided"):
                continue
            q = float(r.get("qty") or 0)
            it["realized_qty"] = round(max(float(it.get("realized_qty") or 0) - q, 0.0), 3)
            r.update({"voided": True, "voided_at": now_iso(), "voided_by": actor, "voided_reason": reason})
            lines += 1
            qty += q
            number = r.get("ref_number") or number
    return lines, round(qty, 3), number


async def release_po_realizations(po_id: str, *, actor_name: str = "Sistem", reason: str = "",
                                  event: str = "dibatalkan") -> List[Dict[str, Any]]:
    """PO batal/ditolak → baris PR yang direalisasikan ke PO itu kembali TERBUKA; PR `converted` kembali
    `approved` (bisa direalisasikan lagi) dengan catatan di riwayat. Idempoten (realisasi `voided` dilewati).
    Juga menangani PR hasil award RFQ yang hanya menyimpan `po_id` tanpa catatan realisasi baris."""
    out: List[Dict[str, Any]] = []
    async for pr in db.purchase_requisitions.find(
            {"$or": [{"items.realizations.ref_id": po_id}, {"po_id": po_id}]}, {"_id": 0}):
        ensure_line_shape(pr)
        lines, qty, number = _void_po_realizations(pr, po_id, actor=actor_name, reason=reason)
        if not lines and pr.get("po_id") != po_id:
            continue
        number = number or pr.get("po_number") or "PO"
        pr.setdefault("timeline", []).append(timeline_entry(
            "po_released", f"{number} {event} — "
            + (f"{lines} baris kembali terbuka" if lines else "PR kembali bisa direalisasikan"),
            actor_name, reason or ""))
        extra: Dict[str, Any] = {}
        if pr.get("status") == "converted" and compute_realization(pr)["realization_status"] != "realized":
            extra["status"] = "approved"
        if pr.get("po_id") == po_id:
            alive = [r for it in pr["items"] for r in it.get("realizations") or []
                     if r.get("type") == "purchase_order" and not r.get("voided")]
            extra["po_id"] = alive[-1]["ref_id"] if alive else ""
            extra["po_number"] = alive[-1].get("ref_number", "") if alive else ""
        out.append(await _save_realization(pr, extra=extra))
    return out


async def reconcile_dead_po_realizations(query: Optional[Dict[str, Any]] = None, *,
                                         actor_name: str = "Sistem (rekonsiliasi PR)") -> List[str]:
    """Perbaikan data lama: PR yang masih menunjuk PO batal/ditolak dilepas lewat `release_po_realizations`.
    Mengembalikan nomor PR yang berubah."""
    dead = {p["id"]: p.get("status") async for p in db.purchase_orders.find(
        {"status": {"$in": list(PO_DEAD_STATUSES)}}, {"_id": 0, "id": 1, "status": 1})}
    if not dead:
        return []
    changed: List[str] = []
    flt = {**(query or {}), "$or": [{"items.realizations": {"$elemMatch": {
        "type": "purchase_order", "ref_id": {"$in": list(dead)}, "voided": {"$ne": True}}}},
        {"po_id": {"$in": list(dead)}}]}
    po_ids: set = set()
    async for pr in db.purchase_requisitions.find(flt, {"_id": 0, "po_id": 1, "items.realizations": 1}):
        if pr.get("po_id") in dead:
            po_ids.add(pr["po_id"])
        for it in pr.get("items") or []:
            for r in it.get("realizations") or []:
                if r.get("type") == "purchase_order" and r.get("ref_id") in dead and not r.get("voided"):
                    po_ids.add(r["ref_id"])
    for pid in sorted(po_ids):
        ev = "ditolak" if dead[pid] == "rejected" else "dibatalkan"
        for doc in await release_po_realizations(pid, actor_name=actor_name, event=ev,
                                                 reason="PO sudah tidak berlaku (rekonsiliasi)"):
            changed.append(doc.get("number", ""))
    return changed


# ═══════════════════════════════════════════════════════════════════════════
# 3. REALISASI → ORDER MAKLOON (baris `makloon`)
# ═══════════════════════════════════════════════════════════════════════════
async def makloon_prefill(pr_id: str, line_no: int) -> Dict[str, Any]:
    """Turunkan payload Wizard Makloon dari baris PR (1 klik dari PR).

    Cara kerja: baris PR menyebut **produk yang dibutuhkan** (output). Resep proses
    di-cari terbalik (`output_product_id == produk baris`) untuk mendapat bahan input,
    jenis proses, mitra default & yield → qty bahan dihitung dari target output.
    """
    pr = await _load_pr(pr_id)
    line = next((it for it in pr["items"] if int(it.get("line_no") or 0) == int(line_no)), None)
    if not line:
        raise SourcingError(f"Baris {line_no} tidak ada pada {pr['number']}.")
    if line.get("fulfillment_mode") != "makloon":
        raise SourcingError(f"Baris {line_no} ber-mode '{line.get('fulfillment_mode')}' — "
                            "prefill makloon hanya untuk baris ber-mode 'makloon'.")
    if not line.get("product_id"):
        raise SourcingError("Baris non-katalog tidak bisa diprefill — tentukan produk output dulu.")
    remaining = round(float(line["quantity"]) - float(line.get("realized_qty") or 0), 3)
    if remaining <= EPS:
        raise SourcingError(f"Baris {line_no} sudah terealisasi penuh.")

    entity_id = pr.get("entity_id") or DEFAULT_ENTITY_ID
    out_prod = await db.products.find_one({"id": line["product_id"]}, {"_id": 0}) or {}
    explain: List[str] = [f"Kebutuhan {pr['number']} baris {line_no}: "
                          f"{remaining:g} {line.get('unit') or out_prod.get('base_unit')} "
                          f"{out_prod.get('name')}"]
    recipe = await db.process_recipes.find_one(
        {"output_product_id": line["product_id"], "status": "active",
         "entity_id": {"$in": [entity_id, "", None]}}, {"_id": 0})
    if not recipe:
        recipe = await db.process_recipes.find_one(
            {"output_product_id": line["product_id"]}, {"_id": 0})
    if not recipe:
        return {
            "pr_id": pr_id, "pr_number": pr["number"], "line_no": line_no,
            "ready": False,
            "reason": (f"Belum ada Resep Proses yang menghasilkan '{out_prod.get('name')}'. "
                       "Buat resep dulu (Pembelian → Master Pembelian → Resep Proses) "
                       "agar bahan, mitra & yield bisa dihitung otomatis."),
            "target_output_qty": remaining, "output_product_id": line["product_id"],
            "explain": explain,
        }

    yield_factor = parse_decimal(recipe.get("yield_factor")) or 1.0
    waste_pct = parse_decimal(recipe.get("waste_pct"))
    effective = yield_factor * (1 - waste_pct / 100.0)
    if effective <= 0:
        effective = yield_factor or 1.0
    # P05 ACC-33 — bulatkan ke ATAS dari nilai mentah; round() lebih dulu bisa membulatkan ke bawah
    material_qty = round(math.ceil(round(remaining / effective * 100, 6)) / 100, 2)
    explain.append(f"Resep '{recipe.get('name')}': yield {yield_factor:g} × susut {waste_pct:g}% "
                   f"→ faktor efektif {effective:.4f}")
    explain.append(f"Bahan dibutuhkan ≈ {remaining:g} ÷ {effective:.4f} = {material_qty:g}")

    in_prod = await db.products.find_one({"id": recipe.get("input_product_id")}, {"_id": 0}) or {}
    makloon_id = recipe.get("default_makloon_id") or ""
    process_type = recipe.get("process_type") or ""
    contract = await cs.resolve_active(partner_id=makloon_id, contract_type="makloon",
                                       process_type=process_type,
                                       product_id=line["product_id"],
                                       input_product_id=recipe.get("input_product_id") or "",
                                       entity_id=entity_id) if makloon_id else None
    if contract:
        explain.append(f"Kontrak aktif {contract.get('contract_number')} — tarif "
                       f"{contract.get('tariff_basis')} @ {rupiah(parse_decimal(contract.get('tariff_rate')))}"
                       f" · susut {parse_decimal(contract.get('shrinkage_pct')):g}%")
    else:
        explain.append("Belum ada kontrak aktif untuk mitra default — tarif/susut memakai resep/kebijakan.")

    makloon_name = ""
    if makloon_id:
        mk = await db.makloons.find_one({"id": makloon_id}, {"_id": 0, "name": 1})
        makloon_name = (mk or {}).get("name", "")
    byp_prod: Dict[str, Any] = {}
    if recipe.get("byproduct_product_id"):
        byp_prod = await db.products.find_one(
            {"id": recipe.get("byproduct_product_id")}, {"_id": 0, "name": 1}) or {}
    return {
        "pr_id": pr_id, "pr_number": pr["number"], "line_no": line_no, "ready": True,
        "target_output_qty": remaining,
        "recipe": {"id": recipe.get("id"), "name": recipe.get("name"),
                   "process_type": process_type, "yield_factor": yield_factor,
                   "waste_pct": waste_pct},
        "contract": {"id": (contract or {}).get("id", ""),
                     "number": (contract or {}).get("contract_number", ""),
                     "tariff_basis": (contract or {}).get("tariff_basis", ""),
                     "tariff_rate": parse_decimal((contract or {}).get("tariff_rate"), 2)} if contract
        else {"id": "", "number": ""},
        "explain": explain,
        # Payload siap kirim ke POST /api/makloon-orders (bisa diedit user di wizard)
        "payload": {
            "mode": "process_only",
            "material_product_id": recipe.get("input_product_id") or "",
            "material_sku": in_prod.get("sku", ""),
            "material_name": in_prod.get("name", ""),
            "material_qty": material_qty,
            "material_unit": in_prod.get("base_unit", ""),
            "from_warehouse_id": pr.get("warehouse_id") or "",
            "target_warehouse_id": pr.get("warehouse_id") or "",
            "entity_id": entity_id,
            "pr_id": pr_id, "pr_number": pr["number"], "pr_line_no": line_no,
            "notes": f"Realisasi {pr['number']} baris {line_no} — {out_prod.get('name')}",
            "steps": [{
                "process_type": process_type,
                "makloon_id": makloon_id, "makloon_name": makloon_name,
                "recipe_id": recipe.get("id") or "",
                "contract_id": (contract or {}).get("id", ""),
                "input_product_id": recipe.get("input_product_id") or "",
                # Nama/satuan disertakan agar Wizard Makloon bisa MENAMPILKAN produk
                # hasil yang sudah ter-prefill (tanpa ini kolom "Produk Hasil" tampak
                # kosong & ringkasan rantai menampilkan "?" walau data sudah benar).
                "input_name": in_prod.get("name", ""),
                "input_sku": in_prod.get("sku", ""),
                "input_unit": in_prod.get("base_unit", ""),
                "output_product_id": line["product_id"],
                "output_name": out_prod.get("name", ""),
                "output_sku": out_prod.get("sku", ""),
                "output_unit": out_prod.get("base_unit") or line.get("unit") or "",
                "byproduct_product_id": recipe.get("byproduct_product_id") or "",
                "byproduct_name": byp_prod.get("name", ""),
            }],
        },
    }


async def realize_to_makloon(pr_id: str, line_no: int, payload: Dict[str, Any],
                             actor: Dict[str, Any]) -> Dict[str, Any]:
    """Buat Order Makloon dari baris PR ber-mode `makloon` & catat realisasinya."""
    from services.makloon_order_service import create_makloon_order

    pr = await _load_pr(pr_id)
    if pr.get("status") not in ("approved", "converted"):
        raise SourcingError(
            f"Hanya PR 'approved' yang bisa direalisasikan (status sekarang: {pr.get('status')}).")
    line = next((it for it in pr["items"] if int(it.get("line_no") or 0) == int(line_no)), None)
    if not line:
        raise SourcingError(f"Baris {line_no} tidak ada pada {pr['number']}.")
    if line.get("fulfillment_mode") != "makloon":
        raise SourcingError(f"Baris {line_no} ber-mode '{line.get('fulfillment_mode')}' — "
                            "pakai realisasi ke PO untuk baris pembelian.")
    remaining = round(float(line["quantity"]) - float(line.get("realized_qty") or 0), 3)
    if remaining <= EPS:
        raise SourcingError(f"Baris {line_no} sudah terealisasi penuh.")

    body = dict(payload or {})
    if not body.get("steps"):
        pre = await makloon_prefill(pr_id, line_no)
        if not pre.get("ready"):
            raise SourcingError(pre.get("reason") or "Prefill makloon tidak tersedia.")
        body = dict(pre["payload"])
    entity_id = body.get("entity_id") or pr.get("entity_id") or DEFAULT_ENTITY_ID
    body.update({"pr_id": pr_id, "pr_number": pr["number"], "pr_line_no": line_no})
    # Output akhir rantai WAJIB = produk baris PR (jejak kebutuhan → realisasi tak putus).
    last_out = (body["steps"][-1] or {}).get("output_product_id")
    if last_out and last_out != line.get("product_id"):
        raise SourcingError(
            "Output langkah terakhir harus sama dengan produk yang diminta PR "
            f"(baris {line_no}: {line.get('product_name')}).")
    from services import material_reservation_service as _mres
    await _mres.reserve_for_pr(pr_id, actor.get("name", ""))   # W2-REQ-07 — PR lama tanpa reservasi
    order = await create_makloon_order(body, entity_id=entity_id,
                                       actor_name=actor.get("name", "Admin"))
    await _mres.transfer_to_mko(pr_id, line_no, order)
    await _mres.reserve_for_mko(order, actor.get("name", ""))   # P05 — PR tanpa resep: kunci saat MKO lahir
    expected = parse_decimal((order.get("forecast") or {}).get("expected_finished_qty"), 3)
    covered = min(remaining, expected) if expected > 0 else remaining
    _record(line, kind="makloon_order", ref_id=order["id"], ref_number=order.get("mko_number", ""),
            qty=covered, actor=actor.get("name", "Admin"))
    pr.setdefault("timeline", []).append(timeline_entry(
        "realized_makloon", f"Baris {line_no} direalisasi ke {order.get('mko_number')}",
        actor.get("name", "Admin"),
        f"estimasi {expected:g} {order.get('final_output_unit') or ''}"))
    updated = await _save_realization(pr, extra={"converted_by": actor.get("name", "Admin")})
    return {"pr": updated, "makloon_order": order,
            "covered_qty": covered, "expected_output_qty": expected}


# ═══════════════════════════════════════════════════════════════════════════
# 4. RINGKASAN UNTUK UI
# ═══════════════════════════════════════════════════════════════════════════
async def sourcing_view(pr_id: str) -> Dict[str, Any]:
    """Ringkasan realisasi + aksi yang tersedia per baris (dipakai panel detail PR)."""
    pr = await _load_pr(pr_id)
    lines = []
    for it in pr["items"]:
        remaining = round(float(it.get("quantity") or 0) - float(it.get("realized_qty") or 0), 3)
        lines.append({
            "line_no": it.get("line_no"), "product_id": it.get("product_id"),
            "sku": it.get("sku"), "product_name": it.get("product_name"),
            "quantity": float(it.get("quantity") or 0), "unit": it.get("unit"),
            "fulfillment_mode": it.get("fulfillment_mode") or "purchase",
            "realized_qty": float(it.get("realized_qty") or 0),
            "remaining_qty": max(remaining, 0.0),
            "realizations": it.get("realizations") or [],
            "can_realize": remaining > EPS and pr.get("status") in ("approved", "converted"),
        })
    return {"pr_id": pr_id, "number": pr.get("number"), "status": pr.get("status"),
            "summary": compute_realization(pr), "lines": lines}
