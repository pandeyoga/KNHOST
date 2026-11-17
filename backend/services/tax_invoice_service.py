"""Faktur Pajak Jual (tax_invoices) service — Sub-fase 1.9.

Terbitkan Faktur Pajak dari Sales Order (MANUAL, OPSIONAL — pajak tidak wajib).
- Hanya entitas PKP + transaksi kena pajak (ppn_amount > 0).
- Penomoran HYBRID: internal FKT-##### + NSFP resmi 16-digit (diisi menyusul) + kode_transaksi.
- Status: normal | pengganti (revisi) | batal. Snapshot penjual (entitas) & pembeli (customer).
- DPP/PPN diambil dari snapshot pajak order (Fase 1B). Render dokumen defensif (.get()).

TX-T2 (TX-05, K-32) — pemicu faktur per PT (`tax.pemicu_faktur`: `pesanan` bawaan = perilaku lama · `surat_jalan`):
- status `draf` (draf otomatis per surat jalan / dokumen pajak retur, diterbitkan orang lewat `issue_draft`, dibuang lewat
  `discard_draft`); `doc_kind` `faktur` · `retur`; `trigger` `pesanan` · `surat_jalan` · `retur`;
- `active_key` (PK-40) diperluas: `so:{order}` · `sj:{order}:{nomor surat jalan}` · `retur:{nota kredit}` · `ic:{…}` —
  dimiliki dokumen hidup (`draf`, `normal`, `pengganti`);
- angka draf per surat jalan dan dokumen retur diambil dari JURNAL sumbernya (akun pemetaan PT), bukan dihitung ulang,
  supaya Σ dokumen pajak selalu bisa dicocokkan dengan akun PPN keluaran (`output_reconciliation`).
"""
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from db import db
from core_utils import new_id, now_iso, safe_doc, next_doc_number
from services.input_tax_service import normalize_nsfp
from services.book_date import tanggal_buku

ELIGIBLE_ORDER_STATUSES = {"confirmed", "partially_picked", "picked",
                          "partially_shipped", "shipped", "done"}
# TX-T1 — daftar kode transaksi yang sah kini pengaturan per PT (`tax.kode_transaksi_diizinkan`, bawaan = daftar lama
# 01/02/03/04/06/07/08/09) dan bawaannya `tax.kode_transaksi_bawaan[_dpp_nilai_lain]` (01 / 04) — lihat
# `tax_config_service.default_kode` dan `periksa_kode`.
STATUS_CODE = {"normal": "0", "pengganti": "1"}


def _money(v: Any) -> str:
    try:
        return "Rp " + f"{float(v or 0):,.0f}".replace(",", ".")
    except Exception:
        return "Rp 0"


async def _next_faktur_no(entity_id: Optional[str] = None) -> str:
    return await next_doc_number("tax_invoices", "number", "FKT-", entity_id=entity_id)


def _entity_is_pkp(entity: Dict[str, Any], order: Dict[str, Any]) -> bool:
    if entity and entity.get("default_tax_mode") == "ppn":
        return True
    return bool(order.get("is_pkp")) and float(order.get("ppn_amount", 0) or 0) > 0


def saringan_keluaran_aktif() -> Dict[str, Any]:
    """PK-45 (TX-01) — saringan faktur keluaran yang DIJUMLAH (rekap PPN): bukan batal dan belum punya pengganti.

    Faktur asli yang sudah diganti tidak dihitung (penggantinya yang dihitung). Bila penggantinya dibatalkan,
    `cancel_tax_invoice` mengosongkan `replaced_by_id` faktur asli sehingga faktur asli dihitung lagi.
    `replaced_by_id: None` juga cocok untuk dokumen tanpa field itu. Daftar/riwayat faktur TIDAK memakai saringan ini.

    TX-T2 — himpunan status baru: hanya faktur TERBIT (`normal`/`pengganti`); `draf`, `diganti`, `batal` tidak dihitung.
    Dokumen pajak retur (`doc_kind: retur`) dijumlah terpisah (`saringan_retur_aktif`, pengurang). Data tanpa `doc_kind`
    = faktur. `replaced_by_id: None` tetap: faktur antar-PT asal yang diganti (layar Antar Entitas, tidak disentuh
    TX-T2) masih berstatus `normal` ber-`replaced_by_id`.
    """
    return {"status": {"$in": list(STATUS_TERBIT)}, "replaced_by_id": None, "doc_kind": {"$ne": "retur"}}


def saringan_retur_aktif() -> Dict[str, Any]:
    """TX-T2 — dokumen pajak retur yang DIJUMLAH rekap PPN (pengurang keluaran): sudah terbit (`normal`)."""
    return {"doc_kind": "retur", "status": "normal"}


# ── PK-40 (SL-13) — keunikan faktur dijamin INDEKS, bukan "cari dulu, lalu sisip" ───────────────────────────────────
# `active_key` hanya ada pada faktur AKTIF (bukan batal, belum diganti): `so:{order_id}` / `ic:{interco_pair_id}` →
# indeks unik parsial `uq_fkt_active`. `nsfp_key` = digit NSFP faktur aktif ber-NSFP → `uq_fkt_nsfp` (lintas PT).
# Pola yang sama di `tax_invoices_in` (`vb:{vendor_bill_id}` / `ic:…`, status `recorded`). Pencarian sebelum tulis tetap
# ada sebagai jalan cepat (pesan rapi); `DuplicateKeyError` dari indeks dipetakan ke 409 berpesan sama.
KUNCI_FAKTUR = {"active_key": "", "nsfp_key": ""}   # untuk `$unset`
PESAN_NSFP_DIPAKAI = "Nomor seri {nsfp} sudah dipakai faktur {nomor}. Periksa nomor serinya."

# ── TX-T2 (K-32) — kosakata & pesan ─────────────────────────────────────────────────────────────────────────────────
#: Pengaturan pemicu faktur per PT (`config_catalog_core.py`). Bawaan `pesanan` = perilaku sebelum TX-T2 (H5).
KUNCI_PEMICU = "tax.pemicu_faktur"
#: Status dokumen yang memegang `active_key` (dokumen hidup) dan status yang sudah terbit (dihitung rekap).
STATUS_HIDUP = ("draf", "normal", "pengganti")
STATUS_TERBIT = ("normal", "pengganti")
PESAN_PEMICU_SJ = "PT ini menerbitkan faktur per surat jalan. Terbitkan dari antrean draf."
PESAN_SUDAH_PER_SJ = "Pesanan ini sudah punya faktur per surat jalan ({nomor}). Terbitkan dari antrean draf."
PESAN_SUDAH_PER_PESANAN = "Pesanan ini sudah punya faktur per pesanan ({nomor})."
PESAN_BUKAN_DRAF = "Dokumen ini bukan draf."
PESAN_BUKAN_TERBIT = "Dokumen ini masih draf. Terbitkan atau buang drafnya dulu."
PESAN_DRAF_NSFP = "Dokumen ini masih draf. Nomor seri diisi saat menerbitkan."
PESAN_DRAF_BATAL = "Dokumen ini masih draf. Pakai Buang draf (alasan wajib)."
PESAN_ALASAN_BUANG = "Alasan membuang draf wajib diisi."
PESAN_DATA_KURANG = "Lengkapi data pajak pelanggan dulu: {daftar}."
PESAN_RETUR_TIDAK_DIGANTI = ("Dokumen pajak retur tidak bisa diganti. Batalkan dokumennya, lalu bangun ulang drafnya "
                             "dari nota kreditnya.")
PESAN_PILIH_PT = "Pilih satu PT."
#: `data_incomplete` → teks pesan terbit (TX-T1 `tax_config_service.data_incomplete`).
TEKS_KURANG = {"identitas_pajak": "identitas pajak", "alamat_pajak": "alamat pajak"}
#: Field angka & rujukan sumber dokumen per surat jalan / retur — disalin apa adanya ke faktur pengganti.
FIELD_SUMBER_DOKUMEN = ("doc_kind", "trigger", "shipment_no", "shipment_ids", "credit_note_id", "credit_note_number",
                        "ref_tax_invoice_id", "ref_tax_invoice_number", "journal_entry_ids", "items", "total_amount",
                        "discount_total", "net_subtotal", "dpp", "dpp_nilai_lain", "ppn_rate", "effective_rate",
                        "ppn_mode", "ppn_amount", "grand_total", "tax_snapshot")


def kunci_aktif_keluaran(fkt: Dict[str, Any]) -> Dict[str, str]:
    """Field kunci faktur keluaran menurut keadaannya: faktur tidak aktif → `{}` (kuncinya harus dicabut).

    TX-T2 — pemilik kunci = dokumen hidup (`draf`, `normal`, `pengganti`); `diganti`/`batal` tidak. Kosakata:
    `ic:{pair}` (antar-PT) · `retur:{nota kredit}` (dokumen pajak retur) · `sj:{pesanan}:{nomor surat jalan}` (faktur per
    surat jalan) · `so:{pesanan}` (faktur per pesanan, termasuk data lama tanpa `trigger`)."""
    if fkt.get("status") in ("batal", "diganti") or fkt.get("replaced_by_id"):
        return {}
    out: Dict[str, str] = {}
    if fkt.get("interco_pair_id"):
        out["active_key"] = f"ic:{fkt['interco_pair_id']}"
    elif fkt.get("doc_kind") == "retur" and fkt.get("credit_note_id"):
        out["active_key"] = f"retur:{fkt['credit_note_id']}"
    elif fkt.get("trigger") == "surat_jalan" and fkt.get("order_id") and fkt.get("shipment_no"):
        out["active_key"] = f"sj:{fkt['order_id']}:{fkt['shipment_no']}"
    elif fkt.get("order_id"):
        out["active_key"] = f"so:{fkt['order_id']}"
    digits = normalize_nsfp(fkt.get("nsfp"))
    if digits:
        out["nsfp_key"] = digits
    return out


def pesan_nsfp(nsfp: Optional[str], nomor: str) -> str:
    return PESAN_NSFP_DIPAKAI.format(nsfp=(nsfp or "").strip(), nomor=nomor or "-")


async def _pemakai_nsfp(digits: str, kecuali: tuple = ()) -> Optional[Dict[str, Any]]:
    """Jalan cepat: faktur keluaran aktif LAIN yang memegang NSFP ini (penjaminnya indeks `uq_fkt_nsfp`)."""
    if not digits:
        return None
    q: Dict[str, Any] = {"nsfp_key": digits}
    if kecuali:
        q["id"] = {"$nin": list(kecuali)}
    return await db.tax_invoices.find_one(q, {"_id": 0, "id": 1, "number": 1})


async def galat_kunci_kembar(coll: str, exc: DuplicateKeyError, kunci: Dict[str, str], *, kecuali_id: str,
                             nsfp: Optional[str], pesan_aktif: Callable[[str], str]) -> Optional[HTTPException]:
    """`DuplicateKeyError` dari `uq_*_active`/`uq_*_nsfp` → 409 berpesan; indeks lain (mis. nomor) → `None` (dilempar
    ulang pemanggil). Penyebab = dokumen lain yang memegang kunci itu, atau `keyPattern` galat yang menyebut field itu
    (`keyPattern` saja tidak cukup: database tiruan mengisinya keliru)."""
    from indexes import is_duplicate_on
    for field in ("active_key", "nsfp_key"):
        val = kunci.get(field)
        if not val:
            continue
        holder = await db[coll].find_one({field: val, "id": {"$ne": kecuali_id}}, {"_id": 0, "number": 1})
        if holder or is_duplicate_on(exc, field):
            nomor = (holder or {}).get("number", "")
            return HTTPException(status_code=409,
                                 detail=pesan_nsfp(nsfp, nomor) if field == "nsfp_key" else pesan_aktif(nomor))
    return None


def _pesan_sudah_terbit(nomor: str) -> str:
    return f"Faktur Pajak sudah diterbitkan untuk order ini ({nomor}). Gunakan Pengganti untuk revisi."


async def _masa_terbuka(entity_id: Optional[str], tanggal: Any, aksi: str) -> None:
    from services.tax_center_service import assert_masa_terbuka   # impor di dalam: hindari lingkar impor
    await assert_masa_terbuka(entity_id, tanggal, aksi=aksi)


def format_nsfp_display(fkt: Dict[str, Any]) -> str:
    """Kode & Nomor Seri Faktur Pajak resmi: {kode}{status_code}.{NNN-NN.NNNNNNNN}."""
    kode = fkt.get("kode_transaksi", "01")
    scode = STATUS_CODE.get(fkt.get("status", "normal"), "0")
    serial = (fkt.get("nsfp") or "").strip()
    if serial:
        digits = "".join(ch for ch in serial if ch.isdigit())
        if len(digits) >= 13:
            body = digits[-13:]
            return f"{kode}{scode}.{body[:3]}-{body[3:5]}.{body[5:]}"
        return serial
    return f"{kode}{scode}.___-__.________ (NSFP belum diisi)"


def _primary_address(customer: Dict[str, Any]) -> Dict[str, Any]:
    addrs = customer.get("addresses", []) or []
    for a in addrs:
        if a.get("is_primary"):
            return a
    return addrs[0] if addrs else {}


def _build_items(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for it in order.get("items", []):
        out.append({
            "product_name": it.get("product_name", ""),
            "sku": it.get("sku", ""),
            "quantity": float(it.get("quantity", 0) or 0),
            "unit": it.get("unit", ""),
            "price": float(it.get("price", 0) or 0),
            "subtotal": float(it.get("subtotal", 0) or 0),
            "discount_amount": float(it.get("discount_amount", 0) or 0),
            "line_total": float(it.get("line_total", it.get("subtotal", 0)) or 0),
        })
    return out


def _snapshot_from_order(order: Dict[str, Any], entity: Dict[str, Any],
                        customer: Dict[str, Any]) -> Dict[str, Any]:
    addr = _primary_address(customer)
    seller_addr = f"{entity.get('address','')}, {entity.get('city','')}".strip(", ")
    cust_addr = f"{addr.get('address','')}, {addr.get('city','')}".strip(", ")
    return {
        "entity_id": order.get("entity_id"),
        "seller_name": entity.get("legal_name", "Kain Nusantara"),
        "seller_npwp": entity.get("npwp", ""),
        "seller_address": seller_addr,
        "customer_id": customer.get("id", order.get("customer_id")),
        "customer_name": order.get("customer_name", customer.get("name", "")),
        "customer_npwp": customer.get("npwp", ""),
        "customer_address": cust_addr,
        "has_customer_npwp": bool(customer.get("npwp")),
        "items": _build_items(order),
        "total_amount": float(order.get("total_amount", 0) or 0),
        "discount_total": float(order.get("discount_total", 0) or 0),
        "net_subtotal": float(order.get("net_subtotal", 0) or 0),
        "dpp": float(order.get("dpp", 0) or 0),
        "dpp_nilai_lain": bool(order.get("dpp_nilai_lain")),
        "effective_rate": float(order.get("effective_rate", order.get("ppn_rate", 0)) or 0),
        "ppn_rate": float(order.get("ppn_rate", 0) or 0),
        "ppn_mode": order.get("ppn_mode", "excluded"),
        "ppn_amount": float(order.get("ppn_amount", 0) or 0),
        "grand_total": float(order.get("grand_total", 0) or 0),
        "is_pkp": True,
        **_potret_pajak(order, customer),
    }


def _potret_pajak(order: Dict[str, Any], customer: Dict[str, Any]) -> Dict[str, Any]:
    """TX-T1 (D3) — "Aturan pajak saat terbit" (potret pesanan; pesanan lama = aturan lama) + potret data pajak pembeli
    + kekurangannya. Penerbitan TIDAK ditolak karena data belum lengkap (antrean lengkapi data = TX-T2)."""
    from services import tax_config_service as tcs
    ctax = tcs.customer_tax(customer, order.get("customer_name", ""))
    return {"tax_snapshot": tcs.potret_dokumen(order), "customer_tax": ctax, "data_incomplete": tcs.data_incomplete(ctax)}


async def _aturan_kode(entity_id: Optional[str]) -> Dict[str, Any]:
    """Pengaturan kode transaksi PT hari ini (tanggal terbit faktur)."""
    from services.tax_config_service import tax_settings
    return await tax_settings(entity_id or "")


def _kode_sah(kode: str, aturan: Dict[str, Any]) -> str:
    from services.tax_config_service import periksa_kode
    try:
        return periksa_kode(kode, aturan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


async def _load_order_entity_customer(order_id: str):
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    entity = safe_doc(await db.business_entities.find_one(
        {"id": order.get("entity_id")}, {"_id": 0})) or {}
    customer = safe_doc(await db.customers.find_one(
        {"id": order.get("customer_id")}, {"_id": 0})) or {}
    return order, entity, customer


def _validate_eligibility(order: Dict[str, Any], entity: Dict[str, Any], kode: str, aturan: Dict[str, Any]):
    if order.get("status") not in ELIGIBLE_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Faktur Pajak hanya untuk order terkonfirmasi ke atas (status sekarang: {order.get('status')}).")
    _kode_sah(kode, aturan)   # TX-T1 — kode sah = daftar kode PT (`tax.kode_transaksi_diizinkan`)
    if not _entity_is_pkp(entity, order):
        raise HTTPException(
            status_code=400,
            detail="Entitas non-PKP — Faktur Pajak tidak dapat diterbitkan (pajak tidak wajib untuk entitas ini).")
    if float(order.get("ppn_amount", 0) or 0) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Order tanpa PPN — Faktur Pajak hanya untuk transaksi kena pajak.")


async def issue_tax_invoice(order_id: str, kode_transaksi: Optional[str],
                           faktur_date: Optional[str], nsfp: Optional[str],
                           actor_name: str) -> Dict[str, Any]:
    """Terbitkan Faktur Pajak (status normal) dari order. Idempotent: 1 faktur aktif/order.

    TX-T2 (K-32) — hanya untuk PT berpemicu `pesanan` (`tax.pemicu_faktur`); PT per surat jalan → 409 (faktur lahir
    sebagai draf per surat jalan). Pesanan yang sudah punya dokumen per surat jalan juga ditolak (satu pesanan tidak
    punya faktur per pesanan sekaligus faktur per surat jalan)."""
    from services.config_resolver import value_of
    order, entity, customer = await _load_order_entity_customer(order_id)
    if await value_of(KUNCI_PEMICU, {"entity_id": order.get("entity_id") or ""}) != "pesanan":
        raise HTTPException(status_code=409, detail=PESAN_PEMICU_SJ)
    # F-10 — DPP Nilai Lain → kode bawaan "saat DPP nilai lain"; TX-T1: kode pelanggan → bawaan PT (pengaturan).
    from services.tax_config_service import default_kode, potret_dokumen
    aturan = await _aturan_kode(order.get("entity_id"))
    kode = (kode_transaksi or default_kode(potret_dokumen(order) or order, customer, aturan)).strip()
    _validate_eligibility(order, entity, kode, aturan)
    existing = await db.tax_invoices.find_one(   # jalan cepat; penjaminnya indeks `uq_fkt_active` (PK-40)
        {"order_id": order_id, "status": {"$nin": ["batal", "diganti"]}, "doc_kind": {"$ne": "retur"}}, {"_id": 0})
    if existing and existing.get("trigger") == "surat_jalan":
        raise HTTPException(status_code=409, detail=PESAN_SUDAH_PER_SJ.format(nomor=existing.get("number", "")))
    if existing:
        raise HTTPException(status_code=409, detail=_pesan_sudah_terbit(existing.get("number")))
    fdate = faktur_date or now_iso()
    await _masa_terbuka(order.get("entity_id"), fdate, "penerbitan faktur")   # PK-40 — PERIKSA sebelum tulis
    nsfp_raw = (nsfp or "").strip()
    dup = await _pemakai_nsfp(normalize_nsfp(nsfp_raw))
    if dup:
        raise HTTPException(status_code=409, detail=pesan_nsfp(nsfp_raw, dup.get("number")))
    fkt = {
        "id": new_id("fkt"),
        "number": await _next_faktur_no(order.get("entity_id")),
        "nsfp": nsfp_raw,
        "kode_transaksi": kode,
        "status": "normal",
        "doc_kind": "faktur", "trigger": "pesanan",   # TX-T2 — asal dokumen
        "replaces_id": None, "replaced_by_id": None, "cancel_reason": "",
        "faktur_date": fdate,
        "order_id": order_id, "order_number": order.get("number", ""),
        "created_by": actor_name, "created_at": now_iso(), "updated_at": now_iso(),
        "issued_at": now_iso(), "issued_by": actor_name,
        **_snapshot_from_order(order, entity, customer),
    }
    fkt.update(kunci_aktif_keluaran(fkt))
    try:
        await db.tax_invoices.insert_one(dict(fkt))
    except DuplicateKeyError as exc:   # PK-40 — dua terbit bersamaan: yang kalah 409
        err = await galat_kunci_kembar("tax_invoices", exc, fkt, kecuali_id=fkt["id"], nsfp=nsfp_raw,
                                       pesan_aktif=_pesan_sudah_terbit)
        if err:
            raise err from exc
        raise
    from services import doc_refs_service as _refs
    await _refs.safe_link(("tax_invoice", fkt["id"]), ("sales_order", order_id),
                          "parent", note="faktur pajak atas pesanan")
    return safe_doc(fkt)


async def set_nsfp(fkt_id: str, nsfp: str, kode_transaksi: Optional[str]) -> Dict[str, Any]:
    fkt = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not fkt:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    if fkt.get("status") == "batal":
        raise HTTPException(status_code=400, detail="Faktur Pajak batal tidak bisa diubah.")
    if fkt.get("status") == "draf":   # TX-T2 — nomor seri draf diisi saat diterbitkan (`issue_draft`)
        raise HTTPException(status_code=409, detail=PESAN_DRAF_NSFP)
    await _masa_terbuka(fkt.get("entity_id"), fkt.get("faktur_date"), "perubahan nomor seri")   # PK-40
    nsfp_raw = (nsfp or "").strip()
    upd: Dict[str, Any] = {"nsfp": nsfp_raw, "updated_at": now_iso()}
    if kode_transaksi and kode_transaksi.strip() != (fkt.get("kode_transaksi") or ""):
        # TX-T1 — kode BARU harus ada di daftar kode PT; kode yang sudah tercetak di faktur tetap boleh dipakai walau
        # sesudahnya dikeluarkan dari daftar (faktur itu sah saat terbit).
        upd["kode_transaksi"] = _kode_sah(kode_transaksi, await _aturan_kode(fkt.get("entity_id")))
    # PK-40 — faktur aktif ber-NSFP memegang `nsfp_key`; NSFP kosong / faktur sudah diganti → kunci dicabut.
    kunci = kunci_aktif_keluaran({**fkt, "nsfp": nsfp_raw})
    ops: Dict[str, Any] = {"$set": upd}
    if kunci.get("nsfp_key"):
        dup = await _pemakai_nsfp(kunci["nsfp_key"], kecuali=(fkt_id,))
        if dup:
            raise HTTPException(status_code=409, detail=pesan_nsfp(nsfp_raw, dup.get("number")))
        upd["nsfp_key"] = kunci["nsfp_key"]
    else:
        ops["$unset"] = {"nsfp_key": ""}
    try:
        await db.tax_invoices.update_one({"id": fkt_id}, ops)
    except DuplicateKeyError as exc:
        err = await galat_kunci_kembar("tax_invoices", exc, {"nsfp_key": kunci.get("nsfp_key", "")}, kecuali_id=fkt_id,
                                       nsfp=nsfp_raw, pesan_aktif=_pesan_sudah_terbit)
        if err:
            raise err from exc
        raise
    return safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))


async def replace_tax_invoice(fkt_id: str, reason: Optional[str],
                             kode_transaksi: Optional[str], nsfp: Optional[str],
                             actor_name: str) -> Dict[str, Any]:
    """Buat Faktur Pajak PENGGANTI (revisi). Original ditandai replaced."""
    original = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not original:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    if original.get("source_type") == "interco":
        # FASE G-6b — faktur pajak INTERNAL tidak lahir dari pesanan penjualan, jadi
        # jalur pengganti ini tidak bisa memuat ordernya. Arahkan ke layarnya sendiri
        # (kalau tidak, pengguna cuma melihat 404 "Order tidak ditemukan").
        raise HTTPException(
            status_code=400,
            detail=("Faktur pajak internal antar-PT diganti dari layar Antar Entitas "
                    "(Pembelian → Hutang Supplier → Antar Entitas → buka transaksinya → "
                    "tombol Faktur Pengganti), supaya pasangan faktur masukan di PT "
                    "pembeli ikut diperbarui."))
    if original.get("status") == "batal":
        raise HTTPException(status_code=400, detail="Faktur Pajak batal tidak bisa diganti.")
    if original.get("status") == "draf":   # TX-T2 — draf belum terbit: terbitkan atau buang
        raise HTTPException(status_code=409, detail=PESAN_BUKAN_TERBIT)
    if original.get("doc_kind") == "retur":   # TX-T2 — bentuk resmi dokumen retur menunggu konsultan pajak
        raise HTTPException(status_code=409, detail=PESAN_RETUR_TIDAK_DIGANTI)
    if original.get("replaced_by_id") or original.get("status") == "diganti":
        raise HTTPException(status_code=409, detail="Faktur ini sudah pernah diganti.")
    # PK-40 — masa faktur asli DAN masa hari ini (tanggal pengganti) harus belum dilaporkan.
    await _masa_terbuka(original.get("entity_id"), original.get("faktur_date"), "penggantian faktur")
    await _masa_terbuka(original.get("entity_id"), None, "penggantian faktur")
    order, entity, customer = await _load_order_entity_customer(original["order_id"])
    from services.tax_config_service import default_kode, potret_dokumen
    aturan = await _aturan_kode(order.get("entity_id"))
    kode = (kode_transaksi or original.get("kode_transaksi")
            or default_kode(potret_dokumen(order) or order, customer, aturan)).strip()
    _validate_eligibility(order, entity, kode, aturan)
    nsfp_raw = (nsfp or "").strip()
    dup = await _pemakai_nsfp(normalize_nsfp(nsfp_raw), kecuali=(original["id"],))   # NSFP asli boleh dipakai lagi
    if dup:
        raise HTTPException(status_code=409, detail=pesan_nsfp(nsfp_raw, dup.get("number")))
    new_id_ = new_id("fkt")
    kunci_asli = kunci_aktif_keluaran(original)
    status_asli = original.get("status") or "normal"
    # PK-40 (1) Klaim faktur asli: hanya satu penggantian yang menang; kuncinya dilepas untuk pengganti.
    # TX-T2 — faktur asal menjadi `diganti` (keluar dari rekap dengan status yang jelas); status sebelumnya disimpan
    # untuk dipulihkan bila penggantinya dibatalkan.
    klaim = await db.tax_invoices.update_one(
        {"id": original["id"], "replaced_by_id": None, "status": {"$in": list(STATUS_TERBIT)}},
        {"$set": {"replaced_by_id": new_id_, "status": "diganti", "status_before_replaced": status_asli,
                  "updated_at": now_iso()}, "$unset": dict(KUNCI_FAKTUR)})
    if not klaim.matched_count:
        raise HTTPException(status_code=409, detail="Faktur ini sudah pernah diganti.")
    try:   # (2) sisip pengganti ber-`active_key`
        new_fkt = {
            "id": new_id_,
            "number": await _next_faktur_no(order.get("entity_id")),
            "nsfp": nsfp_raw,
            "kode_transaksi": kode,
            "status": "pengganti",
            "replaces_id": original["id"], "replaced_by_id": None,
            "cancel_reason": "", "replace_reason": (reason or "").strip(),
            "faktur_date": now_iso(),
            "order_id": original["order_id"], "order_number": order.get("number", ""),
            "created_by": actor_name, "created_at": now_iso(), "updated_at": now_iso(),
            "issued_at": now_iso(), "issued_by": actor_name,
            **_snapshot_from_order(order, entity, customer),
        }
        # TX-T2 — faktur per surat jalan: pengganti memuat angka & rujukan sumber faktur asalnya (dari jurnal surat
        # jalan), bukan angka seluruh pesanan. Faktur per pesanan: perilaku lama (potret pesanan) + penanda asal.
        if original.get("trigger") == "surat_jalan":
            new_fkt.update({k: original[k] for k in FIELD_SUMBER_DOKUMEN if k in original})
        else:
            new_fkt.update({"doc_kind": "faktur", "trigger": "pesanan"})
        new_fkt.update(kunci_aktif_keluaran(new_fkt))
        await db.tax_invoices.insert_one(dict(new_fkt))
    except Exception as exc:  # noqa: BLE001 — (3) sisip gagal → faktur asli dikembalikan, galat diteruskan
        try:
            await db.tax_invoices.update_one({"id": original["id"], "replaced_by_id": new_id_},
                                             {"$set": {"replaced_by_id": None, "status": status_asli,
                                                       "updated_at": now_iso(), **kunci_asli},
                                              "$unset": {"status_before_replaced": ""}})
        except Exception as exc2:  # noqa: BLE001
            print(f"[tax_invoice] faktur asli {original['id']} gagal dikembalikan: {exc2}")
        if isinstance(exc, DuplicateKeyError):
            err = await galat_kunci_kembar("tax_invoices", exc, {"nsfp_key": normalize_nsfp(nsfp_raw)},
                                           kecuali_id=new_id_, nsfp=nsfp_raw, pesan_aktif=_pesan_sudah_terbit)
            if err:
                raise err from exc
        raise
    from services import doc_refs_service as _refs
    await _refs.safe_link(("tax_invoice", new_fkt["id"]), ("sales_order", original["order_id"]),
                          "parent", note="faktur pengganti atas pesanan")
    await _refs.safe_link(("tax_invoice", new_fkt["id"]), ("tax_invoice", original["id"]),
                          "replaces", note=(reason or "faktur pengganti").strip())
    return safe_doc(new_fkt)


async def cancel_tax_invoice(fkt_id: str, reason: str, actor_name: str) -> Dict[str, Any]:
    fkt = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not fkt:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    if fkt.get("status") == "batal":
        raise HTTPException(status_code=400, detail="Faktur Pajak sudah batal.")
    if fkt.get("status") == "draf":   # TX-T2 — draf dibuang lewat `discard_draft` (alasan tercatat sebagai buang)
        raise HTTPException(status_code=409, detail=PESAN_DRAF_BATAL)
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan pembatalan wajib diisi.")
    await _masa_terbuka(fkt.get("entity_id"), fkt.get("faktur_date"), "pembatalan faktur")   # PK-40
    # PK-40 — bila faktur ini pengganti, faktur asli aktif lagi dan mendapat kembali `active_key`/`nsfp_key`. NSFP asli
    # yang sementara itu dipakai faktur aktif lain → tolak sebelum menulis (bukan diam-diam tanpa kunci).
    asli = None
    if fkt.get("replaces_id") and not fkt.get("replaced_by_id"):   # pengganti yang sudah diganti lagi: asli tetap
        asli = await db.tax_invoices.find_one({"id": fkt["replaces_id"], "replaced_by_id": fkt_id}, {"_id": 0})
    # TX-T2 — faktur asal `diganti` kembali ke status sebelum diganti (data lama sebelum migrasi: status tersimpan).
    status_pulih = ((asli or {}).get("status_before_replaced")
                    or ((asli or {}).get("status") if (asli or {}).get("status") != "diganti" else "normal"))
    kunci_asli = kunci_aktif_keluaran({**asli, "replaced_by_id": None, "status": status_pulih}) if asli else {}
    if kunci_asli.get("nsfp_key"):
        dup = await _pemakai_nsfp(kunci_asli["nsfp_key"], kecuali=(fkt_id, asli["id"]))
        if dup:
            raise HTTPException(status_code=409, detail=pesan_nsfp(asli.get("nsfp"), dup.get("number")))
    res = await db.tax_invoices.update_one(
        {"id": fkt_id, "status": {"$ne": "batal"}},
        {"$set": {"status": "batal", "cancel_reason": reason.strip(), "updated_at": now_iso()},
         "$unset": dict(KUNCI_FAKTUR)})
    if not res.matched_count:
        raise HTTPException(status_code=400, detail="Faktur Pajak sudah batal.")
    # bila faktur ini pengganti, lepas tanda replaced di originalnya agar bisa diterbitkan ulang
    if asli:
        try:
            await db.tax_invoices.update_one(
                {"id": asli["id"], "replaced_by_id": fkt_id},
                {"$set": {"replaced_by_id": None, "status": status_pulih, "updated_at": now_iso(), **kunci_asli},
                 "$unset": {"status_before_replaced": ""}})
        except DuplicateKeyError as exc:   # balapan sangat sempit: faktur aktif lain memegang kuncinya → asli tetap
            print(f"[tax_invoice] faktur asli {asli['id']} tidak diaktifkan lagi (kunci dipegang faktur lain): {exc}")
    return safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))


# ═══ TX-T2 (TX-05, K-32) — draf per surat jalan, dokumen pajak retur, terbit/buang draf, pencocokan PPN ═════════════
_EPS = 0.005
#: Jurnal pendapatan per surat jalan (dan pembaliknya) — sumber angka draf faktur per surat jalan.
_SJ_JURNAL = ("shipment_revenue", "shipment_revenue_reversal")
_SJ_MATI = ("cancelled", "void")


async def _kode_akun(entity_id: Optional[str]) -> Tuple[set, set]:
    """Akun PEMETAAN PT (bukan kode tetap) untuk PPN keluaran dan pendapatan penjualan: semua kode yang pernah dipakai
    kebutuhan itu bagi PT ini (`gl_mapping_service.known_codes`), supaya jurnal lama dan baru sama-sama terbaca."""
    from services.gl_mapping_service import known_codes
    eid = entity_id or None
    return (set(await known_codes("penjualan.ppn_keluaran", eid)), set(await known_codes("penjualan.pendapatan", eid)))


def _mutasi(lines: Any, codes: set, *, sisi: str = "kredit") -> float:
    """Σ (kredit − debit) — atau (debit − kredit) bila `sisi="debit"` — baris jurnal pada akun `codes`."""
    total = 0.0
    for ln in lines or []:
        if ln.get("account_code") in codes:
            cr, dr = float(ln.get("credit") or 0), float(ln.get("debit") or 0)
            total += (cr - dr) if sisi == "kredit" else (dr - cr)
    return total


def _layak_pajak(order: Dict[str, Any], entity: Dict[str, Any]) -> bool:
    """Pesanan ber-PPN di PT PKP (aturan yang sama dengan penerbitan per pesanan) dan potretnya bukan "bukan PKP"."""
    from services.tax_config_service import potret_dokumen
    if float(order.get("ppn_amount", 0) or 0) <= 0 or not _entity_is_pkp(entity, order):
        return False
    return (potret_dokumen(order) or {}).get("is_pkp") is not False


async def _faktur_per_pesanan(order_id: str) -> Optional[Dict[str, Any]]:
    """Faktur HIDUP ber-pemicu pesanan (termasuk faktur lama tanpa `trigger`) milik pesanan ini."""
    return await db.tax_invoices.find_one(
        {"order_id": order_id, "status": {"$in": list(STATUS_HIDUP)}, "doc_kind": {"$ne": "retur"},
         "trigger": {"$ne": "surat_jalan"}}, {"_id": 0, "id": 1, "number": 1})


async def _dokumen_draf(order: Dict[str, Any], entity: Dict[str, Any], customer: Dict[str, Any], *, trigger: str,
                        doc_kind: str, harga_jual: float, ppn: float, extra: Dict[str, Any], actor: str,
                        kode: str = "") -> Dict[str, Any]:
    """Isi dokumen draf dari angka JURNAL sumbernya: harga jual & PPN apa adanya; `dpp` = harga jual × pembilang ÷
    penyebut potret pesanan bila pesanan memakai DPP nilai lain (selain itu = harga jual), dibulatkan dengan cara bulat
    potret pesanan (`round_money`, TX-T1 D5). Penjual/pembeli/potret pajak = `_snapshot_from_order`."""
    from services.tax_config_service import default_kode, round_money
    snap = _snapshot_from_order(order, entity, customer)
    potret = snap.get("tax_snapshot") or {}
    satuan = potret.get("pembulatan_satuan") or "dua_desimal"
    hj, ppn_ = round_money(harga_jual, satuan), round_money(ppn, satuan)
    dpp = hj
    if potret.get("dpp_nilai_lain") and int(potret.get("dpp_penyebut") or 0):
        dpp = round_money(hj * int(potret["dpp_pembilang"]) / int(potret["dpp_penyebut"]), satuan)
    if not kode:
        kode = default_kode(potret or order, customer, await _aturan_kode(order.get("entity_id")))
    now = now_iso()
    doc: Dict[str, Any] = {
        "id": new_id("fkt"), "number": "", "nsfp": "",   # nomor FKT diambil saat disisip (`_sisip_draf`)
        "kode_transaksi": kode, "status": "draf", "doc_kind": doc_kind, "trigger": trigger,
        "replaces_id": None, "replaced_by_id": None, "cancel_reason": "", "discard_reason": "",
        "order_id": order.get("id"), "order_number": order.get("number", ""),
        "created_by": actor or "system", "created_at": now, "updated_at": now,
        "drafted_at": now, "issued_at": "", "issued_by": "",
        **snap,
        "total_amount": hj, "discount_total": 0.0, "net_subtotal": hj, "dpp": dpp, "ppn_amount": ppn_,
        "grand_total": round(hj + ppn_, 2),
    }
    doc.update(extra)
    doc.update(kunci_aktif_keluaran(doc))
    return doc


async def _sisip_draf(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Sisip draf (nomor FKT diambil di sini — penyegaran/panggilan ulang tidak menghabiskan nomor); kalah balapan pada
    indeks `uq_fkt_active` → dokumen pemegang kuncinya (tanpa galat)."""
    if not doc.get("number"):
        doc["number"] = await _next_faktur_no(doc.get("entity_id"))
    try:
        await db.tax_invoices.insert_one(dict(doc))
    except DuplicateKeyError:
        ada = await db.tax_invoices.find_one({"active_key": doc.get("active_key")}, {"_id": 0})
        if ada:
            return safe_doc(ada), False
        raise
    return safe_doc(doc), True


async def _jurnal_surat_jalan(shipment_ids: List[str], entity_id: str) -> Dict[str, Any]:
    """Angka jurnal pendapatan surat jalan (pembalik ikut, saling meniadakan): PPN = Σ kredit − debit akun PPN keluaran,
    harga jual = Σ kredit − debit akun pendapatan, per surat jalan dan total; tanggal buku jurnal terakhir."""
    ppn_codes, rev_codes = await _kode_akun(entity_id)
    out: Dict[str, Any] = {"ppn": 0.0, "rev": 0.0, "rev_by_ship": {}, "ids": [], "numbers": [], "date": ""}
    async for je in db.journal_entries.find(
            {"source_type": {"$in": list(_SJ_JURNAL)}, "source_id": {"$in": list(shipment_ids)},
             "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1, "source_id": 1, "lines": 1, "date": 1}):
        rev = _mutasi(je.get("lines"), rev_codes)
        out["ppn"] += _mutasi(je.get("lines"), ppn_codes)
        out["rev"] += rev
        out["rev_by_ship"][je.get("source_id")] = out["rev_by_ship"].get(je.get("source_id"), 0.0) + rev
        out["ids"].append(je.get("id"))
        out["numbers"].append(je.get("number", ""))
        out["date"] = max(out["date"], str(je.get("date") or ""))
    out["ppn"], out["rev"] = round(out["ppn"], 2), round(out["rev"], 2)
    return out


def _baris_surat_jalan(order: Dict[str, Any], ships: List[Dict[str, Any]], rev_by_ship: Dict[str, float]
                       ) -> List[Dict[str, Any]]:
    """Baris barang draf = isi surat jalan (qty keluar); nilai baris = pendapatan jurnal surat jalan itu."""
    by_pid = {it.get("product_id"): it for it in order.get("items") or []}
    out = []
    for sh in ships:
        it = by_pid.get(sh.get("product_id")) or {}
        qty, price = float(sh.get("qty") or 0), float(it.get("price") or 0)
        out.append({"product_name": sh.get("product_name") or it.get("product_name", ""),
                    "sku": sh.get("sku") or it.get("sku", ""), "quantity": qty,
                    "unit": sh.get("unit") or it.get("unit", ""), "price": price, "subtotal": round(qty * price, 2),
                    "discount_amount": 0.0, "line_total": round(float(rev_by_ship.get(sh.get("id")) or 0), 2),
                    "shipment_id": sh.get("id")})
    return out


async def _tautkan(fkt: Dict[str, Any], *pasangan: Tuple[Tuple[str, str], str, str]) -> None:
    from services import doc_refs_service as _refs
    for dst, rel, note in pasangan:
        if dst[1]:
            await _refs.safe_link(("tax_invoice", fkt["id"]), dst, rel, note=note)


async def _draf_surat_jalan(order_id: str, shipment_no: str, *, actor: str = "system"
                            ) -> Tuple[Optional[Dict[str, Any]], str]:
    """Inti `draft_for_shipment` (pemicu PT sudah diperiksa pemanggil). → (dokumen, hasil) dengan hasil `dibuat` ·
    `diperbarui` · `ada` · atau alasan dilewati (`bukan_pkp`, `berfaktur_pesanan`, `dibuang`, `tanpa_surat_jalan`,
    `belum_berjurnal`, `tanpa_ppn`, `tanpa_pesanan`)."""
    try:
        order, entity, customer = await _load_order_entity_customer(order_id)
    except HTTPException:
        return None, "tanpa_pesanan"
    if not _layak_pajak(order, entity):
        return None, "bukan_pkp"
    if await _faktur_per_pesanan(order_id):   # ASUMSI spesifikasi: pesanan berfaktur per pesanan tidak diberi draf
        return None, "berfaktur_pesanan"
    key = f"sj:{order_id}:{shipment_no}"
    hidup = safe_doc(await db.tax_invoices.find_one({"active_key": key}, {"_id": 0}))
    if hidup and hidup.get("status") != "draf":
        return hidup, "ada"
    if not hidup and await db.tax_invoices.find_one(   # ASUMSI spesifikasi: draf yang dibuang tidak dibuat ulang
            {"order_id": order_id, "shipment_no": shipment_no, "trigger": "surat_jalan", "status": "batal",
             "discard_reason": {"$nin": ["", None]}}, {"_id": 0, "id": 1}):
        return None, "dibuang"
    ships = [s async for s in db.shipments.find(
        {"order_id": order_id, "shipment_no": shipment_no, "status": {"$nin": list(_SJ_MATI)}}, {"_id": 0}
    ).sort("created_at", 1)]
    if not ships:
        return None, "tanpa_surat_jalan"
    jr = await _jurnal_surat_jalan([s["id"] for s in ships], order.get("entity_id") or "")
    if not jr["ids"]:
        return None, "belum_berjurnal"
    if jr["ppn"] <= _EPS:
        return None, "tanpa_ppn"
    extra = {"shipment_no": shipment_no, "shipment_ids": [s["id"] for s in ships], "journal_entry_ids": jr["ids"],
             "journal_entry_numbers": jr["numbers"], "items": _baris_surat_jalan(order, ships, jr["rev_by_ship"]),
             "faktur_date": jr["date"] or now_iso()}
    baru = await _dokumen_draf(order, entity, customer, trigger="surat_jalan", doc_kind="faktur",
                               harga_jual=jr["rev"], ppn=jr["ppn"], extra=extra, actor=actor)
    if hidup:   # draf yang sama: angkanya disegarkan bila surat jalan bertambah baris / jurnalnya berubah
        angka = ("ppn_amount", "net_subtotal", "total_amount", "dpp", "grand_total", "shipment_ids",
                 "journal_entry_ids", "items", "faktur_date")
        beda = {k: baru[k] for k in angka if hidup.get(k) != baru[k]}
        if not beda:
            return hidup, "ada"
        await db.tax_invoices.update_one({"id": hidup["id"], "status": "draf"},
                                         {"$set": {**beda, "updated_at": now_iso()}})
        return safe_doc(await db.tax_invoices.find_one({"id": hidup["id"]}, {"_id": 0})), "diperbarui"
    doc, dibuat = await _sisip_draf(baru)
    if dibuat:
        await _tautkan(doc, (("sales_order", order_id), "parent", "draf faktur pajak atas pesanan"),
                       (("shipment", ships[0]["id"]), "references", f"draf faktur pajak surat jalan {shipment_no}"))
    return doc, ("dibuat" if dibuat else "ada")


async def draft_for_shipment(order_id: str, shipment_no: str, *, actor: str = "system") -> Optional[Dict[str, Any]]:
    """TX-T2 — draf faktur per surat jalan. Hanya bila pemicu PT pesanan (`tax.pemicu_faktur`) = `surat_jalan`, pesanan
    ber-PPN di PT PKP, dan pesanan belum punya faktur hidup ber-pemicu pesanan. Idempoten lewat `active_key`
    `sj:{pesanan}:{nomor surat jalan}`. Angka dari JURNAL surat jalan itu (akun pemetaan PT): PPN = Σ kredit akun PPN
    keluaran, harga jual = Σ kredit pendapatan, `dpp` = harga jual × pembilang ÷ penyebut potret pesanan; baris barang =
    isi surat jalan. → dokumen hidup surat jalan itu (draf baru/yang ada, atau faktur yang sudah terbit) atau None."""
    from services.config_resolver import value_of
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "entity_id": 1})
    if not order:
        return None
    if await value_of(KUNCI_PEMICU, {"entity_id": order.get("entity_id") or ""}) != "surat_jalan":
        return None
    doc, _hasil = await _draf_surat_jalan(order_id, shipment_no, actor=actor)
    return doc


async def _jurnal_nota(note: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Jurnal nota kredit (hasil `settle`): `journal_entry_id` nota; nota amandemen lama tanpa penanda → sumbernya."""
    jid = note.get("journal_entry_id") or ""
    q: Dict[str, Any] = {"id": jid} if jid else {"source_type": "amendment_credit_note", "source_id": note.get("id")}
    return [je async for je in db.journal_entries.find({**q, "status": {"$ne": "void"}},
                                                        {"_id": 0, "id": 1, "number": 1, "lines": 1, "date": 1})]


async def _faktur_rujukan(note: Dict[str, Any], order_id: str, terbit: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Faktur asal dokumen retur: faktur per surat jalan yang roll-nya dikembalikan (roll nota / retur asal ada di
    potret roll surat jalan), selain itu faktur hidup terbaru pesanan itu."""
    rids = set()
    for ln in note.get("lines") or []:
        rids |= {r for r in ([ln.get("roll_id")] + list(ln.get("roll_ids") or [])) if r}
    if note.get("return_id"):
        ret = await db.sales_returns.find_one({"id": note["return_id"]}, {"_id": 0, "items": 1}) or {}
        for it in ret.get("items") or []:
            rids |= {r for r in ([it.get("roll_id")] + list(it.get("roll_ids") or [])) if r}
    if rids:
        sh = await db.shipments.find_one({"order_id": order_id, "rolls.roll_id": {"$in": sorted(rids)}},
                                         {"_id": 0, "shipment_no": 1})
        cocok = [f for f in terbit if sh and f.get("trigger") == "surat_jalan"
                 and f.get("shipment_no") == sh.get("shipment_no")]
        if cocok:
            return cocok[0]
    return sorted(terbit, key=lambda f: (str(f.get("faktur_date") or ""), str(f.get("created_at") or "")))[-1]


def _baris_nota(note: Dict[str, Any], harga_jual: float) -> List[Dict[str, Any]]:
    rows = [ln for ln in note.get("lines") or [] if ln.get("product_name") and (ln.get("quantity") or ln.get("qty"))]
    if not rows:
        return [{"product_name": f"Retur atas nota {note.get('number', '')}".strip(), "sku": "", "quantity": 1.0,
                 "unit": "", "price": round(harga_jual, 2), "subtotal": round(harga_jual, 2), "discount_amount": 0.0,
                 "line_total": round(harga_jual, 2)}]
    out = []
    for ln in rows:
        qty, price = float(ln.get("quantity") or ln.get("qty") or 0), float(ln.get("price") or 0)
        total = float(ln.get("line_total") or ln.get("subtotal") or qty * price)
        out.append({"product_name": ln.get("product_name", ""), "sku": ln.get("sku", ""), "quantity": qty,
                    "unit": ln.get("unit", ""), "price": price, "subtotal": round(qty * price, 2),
                    "discount_amount": 0.0, "line_total": round(total, 2)})
    return out


async def _draf_retur(credit_note: Dict[str, Any], *, actor: str = "system") -> Tuple[Optional[Dict[str, Any]], str]:
    from services.credit_note_service import note_kind, note_status
    note = credit_note or {}
    if note.get("id"):
        note = safe_doc(await db.credit_notes.find_one({"id": note["id"]}, {"_id": 0})) or note
    if note_kind(note) != "credit_note" or note_status(note) not in ("issued", "posted"):
        return None, "bukan_nota_kredit_terbit"
    try:
        order, entity, customer = await _load_order_entity_customer(note.get("order_id") or "")
    except HTTPException:
        return None, "tanpa_pesanan"
    if not _layak_pajak(order, entity):
        return None, "bukan_pkp"
    terbit = [f async for f in db.tax_invoices.find(
        {"order_id": order["id"], "doc_kind": {"$ne": "retur"}, "status": {"$in": list(STATUS_TERBIT)},
         "replaced_by_id": None}, {"_id": 0})]
    if not terbit:   # ASUMSI spesifikasi: dokumen retur hanya untuk pesanan yang punya faktur terbit
        return None, "tanpa_faktur_terbit"
    jes = await _jurnal_nota(note)
    ppn_codes, rev_codes = await _kode_akun(order.get("entity_id") or "")
    ppn = round(sum(_mutasi(je.get("lines"), ppn_codes, sisi="debit") for je in jes), 2)
    rev = round(sum(_mutasi(je.get("lines"), rev_codes, sisi="debit") for je in jes), 2)
    if ppn <= _EPS:
        return None, "tanpa_ppn" if jes else "belum_berjurnal"
    hidup = safe_doc(await db.tax_invoices.find_one({"active_key": f"retur:{note['id']}"}, {"_id": 0}))
    if hidup:
        return hidup, "ada"
    if await db.tax_invoices.find_one({"credit_note_id": note["id"], "status": "batal",
                                       "discard_reason": {"$nin": ["", None]}}, {"_id": 0, "id": 1}):
        return None, "dibuang"
    ref = await _faktur_rujukan(note, order["id"], terbit)
    extra = {"credit_note_id": note["id"], "credit_note_number": note.get("number", ""),
             "ref_tax_invoice_id": ref.get("id"), "ref_tax_invoice_number": ref.get("number", ""),
             "shipment_no": ref.get("shipment_no", "") if ref.get("trigger") == "surat_jalan" else "",
             "journal_entry_ids": [je["id"] for je in jes], "journal_entry_numbers": [je.get("number", "") for je in jes],
             "items": _baris_nota(note, rev), "faktur_date": max(str(je.get("date") or "") for je in jes) or now_iso()}
    baru = await _dokumen_draf(order, entity, customer, trigger="retur", doc_kind="retur", harga_jual=rev, ppn=ppn,
                               extra=extra, actor=actor, kode=str(ref.get("kode_transaksi") or ""))
    doc, dibuat = await _sisip_draf(baru)
    if dibuat:
        await _tautkan(doc, (("sales_order", order["id"]), "parent", "dokumen pajak retur atas pesanan"),
                       (("credit_note", note["id"]), "issued_by", "dokumen pajak retur dari nota kredit"),
                       (("tax_invoice", ref.get("id", "")), "references", "faktur asal dokumen retur"))
    return doc, ("dibuat" if dibuat else "ada")


async def draft_for_credit_note(credit_note: Dict[str, Any], *, actor: str = "system") -> Optional[Dict[str, Any]]:
    """TX-T2 — draf dokumen pajak retur (`doc_kind: retur`) untuk nota kredit ber-PPN (mesin PK-32) atas pesanan yang
    punya faktur terbit: `ppn_amount` = PPN yang dibalik jurnal nota itu (Σ debit akun PPN keluaran pemetaan PT),
    harga jual = pendapatan yang dibalik, `ref_tax_invoice_id` = faktur surat jalan terkait atau faktur hidup terbaru
    pesanan. Idempoten lewat `active_key` `retur:{nota}`. Bentuk resmi, penomoran, dan kapan wajib: konfirmasi
    konsultan pajak (ASUMSI spesifikasi: lahir sebagai draf yang diterbitkan orang). → dokumen atau None."""
    doc, _hasil = await _draf_retur(credit_note, actor=actor)
    return doc


async def issue_draft(fkt_id: str, actor: Dict[str, Any], *, faktur_date: Optional[str] = None,
                      nsfp: Optional[str] = None, kode_transaksi: Optional[str] = None) -> Dict[str, Any]:
    """TX-T2 — `draf` → `normal`. PERIKSA: dokumen masih draf (409), data pajak pembeli SAAT INI lengkap (409 berdaftar),
    kode transaksi sah untuk PT (400), masa pajak tanggal faktur belum dilaporkan (PK-40, 409), NSFP belum dipakai
    (409), dan — untuk draf per surat jalan — pesanan tidak berfaktur per pesanan. Ubah bersyarat `status: draf`."""
    from services import tax_config_service as tcs
    fkt = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not fkt:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    if fkt.get("status") != "draf":
        raise HTTPException(status_code=409, detail=PESAN_BUKAN_DRAF)
    customer = safe_doc(await db.customers.find_one({"id": fkt.get("customer_id")}, {"_id": 0})) or {}
    ctax = tcs.customer_tax(customer, fkt.get("customer_name", "")) if customer else (fkt.get("customer_tax") or {})
    kurang = tcs.data_incomplete(ctax)
    if kurang:
        raise HTTPException(status_code=409, detail=PESAN_DATA_KURANG.format(
            daftar=", ".join(TEKS_KURANG.get(k, k) for k in kurang)))
    if fkt.get("trigger") == "surat_jalan":
        pesanan = await _faktur_per_pesanan(fkt.get("order_id") or "")
        if pesanan:
            raise HTTPException(status_code=409, detail=PESAN_SUDAH_PER_PESANAN.format(nomor=pesanan.get("number", "")))
    aturan = await _aturan_kode(fkt.get("entity_id"))
    kode = _kode_sah((kode_transaksi or fkt.get("kode_transaksi") or "").strip(), aturan)
    fdate = (faktur_date or "").strip() or fkt.get("faktur_date") or now_iso()
    await _masa_terbuka(fkt.get("entity_id"), fdate, "penerbitan faktur")   # PK-40 — PERIKSA sebelum tulis
    nsfp_raw = (nsfp or "").strip()
    dup = await _pemakai_nsfp(normalize_nsfp(nsfp_raw), kecuali=(fkt_id,))
    if dup:
        raise HTTPException(status_code=409, detail=pesan_nsfp(nsfp_raw, dup.get("number")))
    now = now_iso()
    upd: Dict[str, Any] = {"status": "normal", "faktur_date": fdate, "kode_transaksi": kode, "nsfp": nsfp_raw,
                           "customer_tax": ctax, "data_incomplete": [], "issued_at": now,
                           "issued_by": (actor or {}).get("name", ""), "updated_at": now}
    if customer:
        upd.update({"customer_npwp": customer.get("npwp", ""), "has_customer_npwp": bool(customer.get("npwp"))})
    upd.update(kunci_aktif_keluaran({**fkt, **upd}))
    try:
        res = await db.tax_invoices.update_one({"id": fkt_id, "status": "draf"}, {"$set": upd})
    except DuplicateKeyError as exc:
        err = await galat_kunci_kembar("tax_invoices", exc, {"nsfp_key": upd.get("nsfp_key", "")}, kecuali_id=fkt_id,
                                       nsfp=nsfp_raw, pesan_aktif=_pesan_sudah_terbit)
        if err:
            raise err from exc
        raise
    if not res.matched_count:
        raise HTTPException(status_code=409, detail=PESAN_BUKAN_DRAF)
    return safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))


async def discard_draft(fkt_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """TX-T2 — `draf` → `batal` dengan alasan wajib (`discard_reason`); kunci dicabut. Sumbernya tampil di pencocokan
    ("Surat jalan tanpa faktur" / "Retur tanpa dokumen pajak") dan tidak dibuat ulang otomatis."""
    fkt = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not fkt:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    if fkt.get("status") != "draf":
        raise HTTPException(status_code=409, detail=PESAN_BUKAN_DRAF)
    alasan = (reason or "").strip()
    if not alasan:
        raise HTTPException(status_code=400, detail=PESAN_ALASAN_BUANG)
    now = now_iso()
    res = await db.tax_invoices.update_one(
        {"id": fkt_id, "status": "draf"},
        {"$set": {"status": "batal", "discard_reason": alasan, "cancel_reason": alasan, "discarded_at": now,
                  "discarded_by": (actor or {}).get("name", ""), "updated_at": now}, "$unset": dict(KUNCI_FAKTUR)})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail=PESAN_BUKAN_DRAF)
    return safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))


def _batas_masa(period: str) -> Tuple[str, str]:
    """Rentang tanggal buku jurnal masa `YYYY-MM` (sama dengan pembanding buku besar rekap PPN, PK-40)."""
    import calendar
    y, m = int(period[:4]), int(period[5:7])
    return f"{period}-01", f"{period}-{calendar.monthrange(y, m)[1]:02d}T23:59:59.999999"


def _periksa_masa(period: str) -> str:
    p = (period or "").strip()
    if len(p) != 7 or p[4] != "-" or not (p[:4] + p[5:]).isdigit() or not 1 <= int(p[5:]) <= 12:
        raise HTTPException(status_code=400, detail="Masa pajak harus berbentuk TTTT-BB, mis. 2026-11.")
    return p


async def rebuild_drafts(entity_id: str, period: str, *, actor: str = "system") -> Dict[str, Any]:
    """TX-T2 — bangun ulang draf masa itu untuk satu PT, idempoten: surat jalan berjurnal pada masa itu (bila pemicu PT
    = `surat_jalan`) dan nota kredit ber-PPN berjurnal pada masa itu. Draf yang dibuang tidak dibuat ulang.
    → `{created, skipped, reasons}`."""
    from services.config_resolver import value_of
    period = _periksa_masa(period)
    awal, akhir = _batas_masa(period)
    created, skipped = 0, 0
    alasan: Dict[str, int] = {}

    def _catat(hasil: str) -> None:
        nonlocal created, skipped
        if hasil == "dibuat":
            created += 1
        else:
            skipped += 1
            alasan[hasil] = alasan.get(hasil, 0) + 1

    if await value_of(KUNCI_PEMICU, {"entity_id": entity_id}) == "surat_jalan":
        sids = [je.get("source_id") async for je in db.journal_entries.find(
            {"entity_id": entity_id, "source_type": "shipment_revenue", "status": {"$ne": "void"},
             "date": {"$gte": awal, "$lte": akhir}}, {"_id": 0, "source_id": 1})]
        pasangan = set()
        async for sh in db.shipments.find({"id": {"$in": sids}}, {"_id": 0, "order_id": 1, "shipment_no": 1}):
            if sh.get("order_id") and sh.get("shipment_no"):
                pasangan.add((sh["order_id"], sh["shipment_no"]))
        for oid, no in sorted(pasangan):
            _doc, hasil = await _draf_surat_jalan(oid, no, actor=actor)
            _catat(hasil)
    jids = [je.get("id") async for je in db.journal_entries.find(
        {"entity_id": entity_id, "status": {"$ne": "void"}, "date": {"$gte": awal, "$lte": akhir},
         "source_type": {"$in": ["sales_return", "amendment_credit_note"]}}, {"_id": 0, "id": 1})]
    async for cn in db.credit_notes.find({"entity_id": entity_id, "journal_entry_id": {"$in": jids}}, {"_id": 0}):
        _doc, hasil = await _draf_retur(cn, actor=actor)
        _catat(hasil)
    return {"period": period, "created": created, "skipped": skipped, "reasons": alasan}


# ── Pencocokan PPN keluaran per PT per masa ──────────────────────────────────────────────────────────────────────────
def _unit_dokumen(d: Dict[str, Any]) -> Tuple[tuple, Dict[str, Any]]:
    """Satuan pencocokan dokumen pajak: antar-PT per pasangan, retur per nota kredit, faktur per surat jalan per
    (pesanan, nomor surat jalan), faktur per pesanan per pesanan."""
    if d.get("interco_pair_id"):
        return ("ic", d["interco_pair_id"]), {"jenis": "antar_pt", "label": d.get("order_number", "")}
    if d.get("doc_kind") == "retur":
        return ("retur", d.get("credit_note_id") or d["id"]), {
            "jenis": "retur", "credit_note_id": d.get("credit_note_id", ""),
            "credit_note_number": d.get("credit_note_number", ""), "order_id": d.get("order_id", ""),
            "order_number": d.get("order_number", "")}
    if d.get("trigger") == "surat_jalan":
        return ("sj", d.get("order_id"), d.get("shipment_no")), {
            "jenis": "surat_jalan", "order_id": d.get("order_id", ""), "order_number": d.get("order_number", ""),
            "shipment_no": d.get("shipment_no", "")}
    return ("so", d.get("order_id")), {"jenis": "pesanan", "order_id": d.get("order_id", ""),
                                       "order_number": d.get("order_number", "")}


async def _mode_pesanan(order_id: str, pemicu_pt: str, cache: Dict[str, Any]) -> Dict[str, Any]:
    """Satuan jurnal pesanan: `so` bila pesanan punya faktur per pesanan yang terbit, `sj` bila punya dokumen per surat
    jalan atau PT-nya berpemicu surat jalan, selain itu `so`."""
    if order_id in cache:
        return cache[order_id]
    o = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "number": 1}) or {}
    per_pesanan = await db.tax_invoices.find_one(
        {"order_id": order_id, "doc_kind": {"$ne": "retur"}, "trigger": {"$ne": "surat_jalan"},
         "status": {"$in": list(STATUS_TERBIT)}}, {"_id": 0, "id": 1})
    per_sj = await db.tax_invoices.find_one({"order_id": order_id, "trigger": "surat_jalan"}, {"_id": 0, "id": 1})
    mode = "so" if per_pesanan else ("sj" if per_sj or pemicu_pt == "surat_jalan" else "so")
    cache[order_id] = {"mode": mode, "number": o.get("number", "")}
    return cache[order_id]


async def _unit_jurnal(je: Dict[str, Any], pemicu_pt: str, cache: Dict[str, Any]
                       ) -> Optional[Tuple[tuple, Dict[str, Any]]]:
    """Satuan pencocokan jurnal ber-PPN keluaran menurut sumbernya; None = sumber yang tidak dikenal (belum terjelaskan:
    jurnal manual, penyesuaian, dll.). Pembalik (`*_reversal`) masuk satuan jurnal asalnya."""
    st = str(je.get("source_type") or "")
    base = st[:-len("_reversal")] if st.endswith("_reversal") else st
    sid, ref = str(je.get("source_id") or ""), je.get("ref") or {}
    if base in ("shipment_revenue", "sales_order", "amendment_debit_note"):
        if base == "shipment_revenue":
            sh = await db.shipments.find_one({"id": sid}, {"_id": 0, "order_id": 1, "shipment_no": 1}) or {}
            oid, no = ref.get("order_id") or sh.get("order_id") or "", sh.get("shipment_no") or ""
        else:
            oid, no = (sid if base == "sales_order" else ref.get("order_id") or ""), ""
        if not oid:
            return None
        info = await _mode_pesanan(oid, pemicu_pt, cache)
        if info["mode"] == "sj" and no:
            return ("sj", oid, no), {"jenis": "surat_jalan", "order_id": oid, "order_number": info["number"],
                                     "shipment_no": no}
        return ("so", oid), {"jenis": "pesanan", "order_id": oid, "order_number": info["number"]}
    if base in ("amendment_credit_note", "sales_return"):
        asal = je.get("id")
        if st.endswith("_reversal") and ref.get("reverses_entry_id"):
            asal = ref["reverses_entry_id"]
        note = await db.credit_notes.find_one({"journal_entry_id": asal}, {"_id": 0, "id": 1, "number": 1,
                                                                            "order_id": 1, "order_number": 1})
        if not note and base == "amendment_credit_note":
            note = await db.credit_notes.find_one({"id": sid}, {"_id": 0, "id": 1, "number": 1, "order_id": 1,
                                                               "order_number": 1})
        nid = (note or {}).get("id") or f"jurnal:{asal}"
        return ("retur", nid), {"jenis": "retur", "credit_note_id": (note or {}).get("id", ""),
                                "credit_note_number": (note or {}).get("number", ""),
                                "order_id": (note or {}).get("order_id", ""),
                                "order_number": (note or {}).get("order_number", "")}
    if base == "interco_return":
        return ("retur_ic", sid.split(":")[0]), {"jenis": "retur_antar_pt", "label": je.get("source_label", "")}
    if base == "interco_transaction":
        return ("ic", sid.split(":")[0]), {"jenis": "antar_pt", "label": je.get("source_label", "")}
    return None


async def output_reconciliation(entity_id: str, period: str) -> Dict[str, Any]:
    """TX-T2 — pencocokan PPN keluaran satu PT satu masa.

    `faktur_ppn` = Σ PPN faktur terbit (`normal`/`pengganti`, belum diganti; antar-PT ikut) bermasa itu; `retur_ppn` =
    Σ PPN dokumen pajak retur `normal`; `gl_ppn` = kredit − debit akun `penjualan.ppn_keluaran` (pemetaan PT, semua kode
    yang pernah dipakai) pada jurnal tidak batal bertanggal buku masa itu; `difference` = `gl_ppn` − (`faktur_ppn` −
    `retur_ppn`). Selisih dijelaskan per satuan sumber (surat jalan / pesanan / nota kredit / pasangan antar-PT):
    `surat_jalan_tanpa_faktur` (jurnal > dokumen), `faktur_tanpa_jurnal` (dokumen > jurnal, termasuk dokumen retur
    tanpa jurnal), `retur_tanpa_dokumen` (PPN dibalik jurnal nota > dokumen retur). Tiap baris membawa `effect` = sumbangan
    bertandanya ke `difference`. `unexplained` = `difference` − Σ `effect` = Σ PPN jurnal bersumber tak dikenal
    (`unexplained_journals`)."""
    from services.config_resolver import value_of
    from services.input_tax_service import period_of, _jendela_masa
    period = _periksa_masa(period)
    ppn_codes, _rev = await _kode_akun(entity_id)
    pemicu = str(await value_of(KUNCI_PEMICU, {"entity_id": entity_id}))
    awal, akhir = _batas_masa(period)
    units: Dict[tuple, Dict[str, Any]] = {}
    lain: List[Dict[str, Any]] = []
    cache: Dict[str, Any] = {}
    gl_ppn = 0.0

    def _slot(key: tuple, meta: Dict[str, Any]) -> Dict[str, Any]:
        return units.setdefault(key, {**meta, "gl": 0.0, "doc": 0.0, "journals": [], "documents": []})

    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "entity_id": entity_id, "lines.account_code": {"$in": sorted(ppn_codes)},
             "date": {"$gte": awal, "$lte": akhir}},
            {"_id": 0, "id": 1, "number": 1, "date": 1, "source_type": 1, "source_id": 1, "source_label": 1,
             "ref": 1, "lines": 1, "description": 1}):
        net = round(_mutasi(je.get("lines"), ppn_codes), 2)
        if abs(net) <= _EPS:
            continue
        gl_ppn += net
        u = await _unit_jurnal(je, pemicu, cache)
        j = {"id": je.get("id"), "number": je.get("number", ""), "date": je.get("date", ""),
             "source_type": je.get("source_type", ""), "amount": net}
        if u is None:
            lain.append({**j, "description": je.get("description", "")})
            continue
        s = _slot(*u)
        s["gl"] += net
        s["journals"].append(j)
    faktur_ppn = retur_ppn = 0.0
    q = {"entity_id": entity_id, "status": {"$in": list(STATUS_TERBIT)}, "replaced_by_id": None,
         "faktur_date": _jendela_masa(period)}
    async for d in db.tax_invoices.find(q, {"_id": 0}):
        if period_of(d.get("faktur_date") or "") != period:
            continue
        if d.get("doc_kind") == "retur" and d.get("status") != "normal":
            continue
        ppn = round(float(d.get("ppn_amount") or 0), 2)
        retur = d.get("doc_kind") == "retur"
        if retur:
            retur_ppn += ppn
        else:
            faktur_ppn += ppn
        s = _slot(*_unit_dokumen(d))
        s["doc"] += -ppn if retur else ppn
        s["documents"].append({"id": d["id"], "number": d.get("number", ""), "status": d.get("status", ""),
                               "doc_kind": "retur" if retur else "faktur", "ppn_amount": ppn})
    gl_ppn, faktur_ppn, retur_ppn = round(gl_ppn, 2), round(faktur_ppn, 2), round(retur_ppn, 2)
    difference = round(gl_ppn - (faktur_ppn - retur_ppn), 2)
    causes: Dict[str, List[Dict[str, Any]]] = {"surat_jalan_tanpa_faktur": [], "faktur_tanpa_jurnal": [],
                                               "retur_tanpa_dokumen": []}
    for s in units.values():
        effect = round(s["gl"] - s["doc"], 2)
        if abs(effect) <= _EPS:
            continue
        row = {k: v for k, v in s.items() if k not in ("gl", "doc")}
        row.update({"gl_ppn": round(s["gl"], 2), "doc_ppn": round(abs(s["doc"]), 2), "amount": round(abs(effect), 2),
                    "effect": effect})
        jenis = s["jenis"]
        if jenis in ("pesanan", "surat_jalan", "antar_pt"):
            causes["surat_jalan_tanpa_faktur" if effect > 0 else "faktur_tanpa_jurnal"].append(row)
        elif jenis == "retur":
            causes["retur_tanpa_dokumen" if effect < 0 else "faktur_tanpa_jurnal"].append(row)
        elif effect < 0:   # retur antar-PT: belum punya dokumen pajak (di luar lingkup TX-T2)
            causes["retur_tanpa_dokumen"].append(row)
        else:
            lain += [{**j, "description": "retur antar-PT"} for j in s["journals"]]
    for rows in causes.values():
        rows.sort(key=lambda r: (str(r.get("order_number") or r.get("label") or ""), str(r.get("shipment_no") or "")))
    explained = round(sum(r["effect"] for rows in causes.values() for r in rows), 2)
    return {"entity_id": entity_id, "period": period, "faktur_ppn": faktur_ppn, "retur_ppn": retur_ppn,
            "gl_ppn": gl_ppn, "difference": difference, "causes": causes,
            "unexplained": round(difference - explained, 2), "unexplained_journals": lain,
            "accounts": sorted(ppn_codes), "trigger": pemicu}


async def _pt_pemicu(trigger: str) -> List[str]:
    """PT PKP yang pemicu fakturnya = `trigger` (nilai efektif per PT)."""
    from services.config_resolver import value_of
    out = []
    async for ent in db.business_entities.find({"default_tax_mode": "ppn"}, {"_id": 0, "id": 1}):
        if await value_of(KUNCI_PEMICU, {"entity_id": ent["id"]}) == trigger:
            out.append(ent["id"])
    return out


async def job_tax_draft_backfill() -> Dict[str, Any]:
    """TX-T2 — job harian pemulih kait: (1) surat jalan berjurnal pendapatan pada PT berpemicu `surat_jalan` yang belum
    punya dokumen pajak apa pun → draf per surat jalan; (2) nota kredit ber-PPN yang sudah berjurnal tanpa dokumen pajak
    retur apa pun → draf dokumen retur. Kegagalan satu sumber tidak menghentikan sumber lain. Draf yang dibuang tidak
    dibuat ulang (sumbernya punya dokumen `batal`)."""
    import logging
    log = logging.getLogger(__name__)
    hasil: Dict[str, Any] = {"surat_jalan": 0, "retur": 0, "gagal": 0, "diperiksa": 0}
    for eid in await _pt_pemicu("surat_jalan"):
        sids = [je.get("source_id") async for je in db.journal_entries.find(
            {"entity_id": eid, "source_type": "shipment_revenue", "status": {"$ne": "void"}}, {"_id": 0, "source_id": 1})]
        pasangan = set()
        async for sh in db.shipments.find({"id": {"$in": sids}}, {"_id": 0, "order_id": 1, "shipment_no": 1}):
            if sh.get("order_id") and sh.get("shipment_no"):
                pasangan.add((sh["order_id"], sh["shipment_no"]))
        for oid, no in sorted(pasangan):
            hasil["diperiksa"] += 1
            if await db.tax_invoices.find_one({"order_id": oid, "shipment_no": no}, {"_id": 0, "id": 1}):
                continue
            try:
                _doc, h = await _draf_surat_jalan(oid, no)
                hasil["surat_jalan"] += int(h == "dibuat")
            except Exception as exc:  # noqa: BLE001 — satu sumber gagal tidak menghentikan pemulihan sumber lain
                hasil["gagal"] += 1
                log.warning("[tax_draft_backfill] draf surat jalan %s/%s gagal: %s", oid, no, exc)
    async for cn in db.credit_notes.find({"kind": {"$in": ["credit_note", None]}, "status": "posted",
                                          "journal_entry_id": {"$nin": ["", None]}}, {"_id": 0}):
        hasil["diperiksa"] += 1
        if await db.tax_invoices.find_one({"credit_note_id": cn["id"]}, {"_id": 0, "id": 1}):
            continue
        try:
            _doc, h = await _draf_retur(cn)
            hasil["retur"] += int(h == "dibuat")
        except Exception as exc:  # noqa: BLE001
            hasil["gagal"] += 1
            log.warning("[tax_draft_backfill] draf retur nota %s gagal: %s", cn.get("number"), exc)
    return {"ok": True, **hasil}


async def output_reconciliation_periods() -> List[Tuple[str, str]]:
    """(PT, masa) yang perlu dicocokkan (INV-TAX-OUT-01): PT PKP yang punya faktur terbit atau jurnal PPN keluaran."""
    from services.input_tax_service import period_of
    out = set()
    async for ent in db.business_entities.find({"default_tax_mode": "ppn"}, {"_id": 0, "id": 1}):
        eid = ent["id"]
        for d in await db.tax_invoices.distinct("faktur_date", {"entity_id": eid,
                                                                "status": {"$in": list(STATUS_TERBIT)}}):
            if d:
                out.add((eid, period_of(d)))
        ppn_codes, _rev = await _kode_akun(eid)
        for d in await db.journal_entries.distinct("date", {"entity_id": eid, "status": {"$ne": "void"},
                                                            "lines.account_code": {"$in": sorted(ppn_codes)}}):
            if d:
                out.add((eid, str(d)[:7]))
    return sorted(out)


def _faktor(fkt: Dict[str, Any]) -> str:
    """TX-T1 — pecahan DPP nilai lain dari potret faktur (faktur lama: aturan lama)."""
    from services.tax_config_service import faktor_teks
    return faktor_teks(fkt.get("tax_snapshot"))


async def render_faktur_html(fkt_id: str) -> str:
    fkt = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not fkt:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    rows = "".join(
        f"<tr><td style='text-align:center'>{i + 1}</td>"
        f"<td>{it.get('product_name', '')} <small style='color:#666'>({it.get('sku', '')})</small><br>"
        f"<small style='color:#666'>{it.get('quantity', 0)} {it.get('unit', '')} × {_money(it.get('price', 0))}</small></td>"
        f"<td style='text-align:right'>{_money(it.get('line_total', 0))}</td></tr>"
        for i, it in enumerate(fkt.get("items", []))
    ) or "<tr><td colspan='3'>-</td></tr>"
    status = fkt.get("status", "normal")
    banner = ""
    if status == "pengganti":
        banner = ("<div class='banner pengganti'><strong>FAKTUR PAJAK PENGGANTI</strong> — "
                  f"revisi atas faktur sebelumnya. {fkt.get('replace_reason', '')}</div>")
    elif status == "batal":
        banner = ("<div class='banner batal'><strong>FAKTUR PAJAK DIBATALKAN</strong> — "
                  f"{fkt.get('cancel_reason', '')}</div>")
    elif status == "draf":   # TX-T2 — draf belum diterbitkan
        banner = ("<div class='banner pengganti'><strong>DRAF — BELUM DITERBITKAN</strong> — "
                  "periksa lalu terbitkan dari layar Faktur Keluaran.</div>")
    elif status == "diganti":   # TX-T2 — faktur asal yang sudah diganti
        banner = ("<div class='banner batal'><strong>FAKTUR PAJAK SUDAH DIGANTI</strong> — "
                  "lihat faktur penggantinya.</div>")
    judul = "FAKTUR PAJAK"
    if fkt.get("doc_kind") == "retur":   # TX-T2 — nama & bentuk resmi: konfirmasi konsultan pajak
        judul = "DOKUMEN PAJAK RETUR"
        banner += (f"<div class='banner pengganti'>Atas nota kredit {fkt.get('credit_note_number', '')} · faktur asal "
                   f"{fkt.get('ref_tax_invoice_number', '') or '-'}.</div>")
    # Tanggal faktur = tanggal buku WIB. Dulu 10 huruf pertama stempel UTC: faktur yang diterbitkan pukul 00.00–07.00
    # WIB tercetak bertanggal KEMARIN (masa pajaknya sudah WIB lewat `period_of`).
    try:
        fd = tanggal_buku(fkt.get("faktur_date") or fkt.get("created_at") or None)
    except ValueError:
        fd = (fkt.get("faktur_date", "") or "")[:10]
    npwp_note = "" if fkt.get("has_customer_npwp") else \
        "<p style='color:#B23B14;font-size:11px'>* NPWP pembeli belum diisi.</p>"
    html = f"""
    <html><head><title>Faktur Pajak {fkt.get('number', '')}</title>
    <style>
      @page {{size:A4 portrait;margin:14mm}} body{{font-family:Arial,sans-serif;color:#111;font-size:13px}}
      .head{{text-align:center;border-bottom:2px solid #111;padding-bottom:10px;margin-bottom:14px}}
      .head h1{{margin:0;font-size:20px;letter-spacing:1px}}
      .serial{{font-size:15px;font-weight:bold;margin-top:6px}}
      .meta{{display:flex;justify-content:space-between;margin:14px 0}}
      .box{{width:48%}} .box h3{{margin:0 0 4px;font-size:12px;color:#0058CC;text-transform:uppercase}}
      table{{width:100%;border-collapse:collapse;margin-top:8px}}
      td,th{{border:1px solid #ccc;padding:8px}} th{{background:#f3f3f3;text-align:left}}
      .totals{{margin-top:12px;width:55%;margin-left:45%}}
      .totals td{{border:none;padding:3px 8px}} .totals .grand{{font-weight:bold;font-size:15px;border-top:2px solid #111}}
      .banner{{padding:8px;margin:10px 0;border-radius:4px;font-size:12px}}
      .banner.pengganti{{background:#FFF3CD;border:1px solid #FFC107}}
      .banner.batal{{background:#FDE2E2;border:1px solid #E53935;color:#9B1C1C}}
      .sign{{margin-top:40px;text-align:right}} footer{{margin-top:28px;border-top:1px solid #ddd;padding-top:10px;color:#666;font-size:11px}}
    </style></head><body>
      <div class="head">
        <h1>{judul}</h1>
        <div class="serial">Kode dan Nomor Seri Faktur Pajak: {format_nsfp_display(fkt)}</div>
        <div style="font-size:11px;color:#666">No. Internal: {fkt.get('number', '')} · Tanggal: {fd}</div>
      </div>
      {banner}
      <div class="meta">
        <div class="box"><h3>Pengusaha Kena Pajak (Penjual)</h3>
          <p><strong>{fkt.get('seller_name', '')}</strong><br>{fkt.get('seller_address', '')}<br>
          NPWP: {fkt.get('seller_npwp', '-')}</p></div>
        <div class="box"><h3>Pembeli Barang Kena Pajak</h3>
          <p><strong>{fkt.get('customer_name', '')}</strong><br>{fkt.get('customer_address', '')}<br>
          NPWP: {fkt.get('customer_npwp', '') or '-'}</p>{npwp_note}</div>
      </div>
      <table><thead><tr><th style="width:34px">No.</th><th>Nama Barang Kena Pajak / Jasa Kena Pajak</th>
        <th style="width:150px;text-align:right">Harga Jual</th></tr></thead>
        <tbody>{rows}</tbody></table>
      <table class="totals">
        <tr><td>Harga Jual (Bruto)</td><td style="text-align:right">{_money(fkt.get('total_amount', 0))}</td></tr>
        <tr><td>Dikurangi Potongan Harga</td><td style="text-align:right">{_money(fkt.get('discount_total', 0))}</td></tr>
        <tr><td>Dasar Pengenaan Pajak (DPP{(' — Nilai Lain ' + _faktor(fkt)) if fkt.get('dpp_nilai_lain') else ''})</td><td style="text-align:right">{_money(fkt.get('dpp', 0))}</td></tr>
        <tr><td>PPN ({fkt.get('ppn_rate', 0)}%)</td><td style="text-align:right">{_money(fkt.get('ppn_amount', 0))}</td></tr>
        <tr class="grand"><td>Total</td><td style="text-align:right">{_money(fkt.get('grand_total', 0))}</td></tr>
      </table>
      <div class="sign"><p>{(fkt.get('seller_address', '').split(',')[-1] or '').strip()}, {fd}</p>
        <br/><br/><p><strong>_______________________</strong></p>
        <p style="font-size:11px">{fkt.get('seller_name', '')}</p></div>
      <footer>Dokumen Faktur Pajak dibuat oleh Kain Nusantara ERP. NSFP resmi diisi setelah alokasi dari DJP/Coretax (e-Faktur).</footer>
    </body></html>
    """
    return html
