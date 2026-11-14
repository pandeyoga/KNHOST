"""FASE G-6b — **FAKTUR PAJAK INTERNAL** untuk transaksi antar-PT ber-PPN.

MASALAH NYATA
-------------
G-6 sudah menghitung PPN antar-PT dengan benar **di jurnal** (PPN Keluaran di buku
penjual == PPN Masukan di buku pembeli, INV-IC-05). Tetapi jurnal bukan dokumen
pajak. Kalau PT KSC menjual ke CV Kanda ber-PPN 11%, kedua PT tetap wajib punya
**faktur pajak yang bisa dicetak, dilaporkan, dan direkap** — penjual sebagai
Faktur Pajak Keluaran, pembeli sebagai Faktur Pajak Masukan yang dikreditkan.
Sebelum modul ini, PPN antar-PT tidak pernah muncul di **Pusat Pajak** (rekap
`vat_summary` hanya melihat `tax_invoices` dari pesanan penjualan dan
`tax_invoices_in` dari tagihan supplier) → posisi PPN kurang/lebih bayar tiap PT
SALAH untuk semua transaksi internal.

DESAIN (kenapa begini)
----------------------
* **Tidak membuat koleksi baru.** Dokumen internal masuk ke koleksi pajak yang
  SUDAH ADA — `tax_invoices` (keluaran) & `tax_invoices_in` (masukan) — dengan
  penanda `source_type="interco"` + `interco_pair_id`. Konsekuensi langsung:
  rekap `vat_summary`, layar Pusat Pajak, dan Faktur Masukan otomatis ikut
  memperhitungkannya tanpa satu baris kode tambahan di sana.
* **Kembar, seperti dokumen G-6 lainnya.** Satu dokumen per PT, saling menunjuk
  (`counterpart_faktur_id`) + `refs` dua arah ke transaksinya (G-4).
* **Angka diambil dari transaksi, bukan diketik ulang.** DPP = subtotal −
  subtotal yang sudah diretur; PPN = tax_amount − PPN yang sudah diretur
  (lihat `interco_return_service`). Jadi faktur pajak tidak pernah lebih besar
  dari nilai yang benar-benar terjadi.
* **Retur mengubah angka pajak** ⇒ faktur yang sudah terbit ditandai
  `needs_replacement` dan layar menawarkan **Faktur Pengganti** (praktik
  e-Faktur), bukan diam-diam mengedit dokumen yang sudah terbit.

Invarian: **INV-IC-07** (di `scripts/verify_data_integrity.py`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core_utils import new_id, next_doc_number, now_iso, rupiah, safe_doc, timeline_entry
from db import db
from services import interco_service as ics
from services.input_tax_service import kunci_aktif_masukan, next_input_number, normalize_nsfp, period_of

EPS = 0.01
COLL_OUT = "tax_invoices"       # Faktur Pajak Keluaran (penjual)
COLL_IN = "tax_invoices_in"     # Faktur Pajak Masukan (pembeli)

# Faktur pajak mengikuti FAKTUR INTERNAL — jadi hanya sah setelah dokumen
# dagangnya terbit (status `invoiced`) atau sudah lunas.
ISSUABLE_STATUSES = ("invoiced", "settled")
ACTIVE_OUT = ("normal", "pengganti")
ACTIVE_IN = ("recorded",)


class IntercoTaxError(Exception):
    """Pelanggaran aturan faktur pajak internal (→ HTTP 400 di router)."""


# ═══════════════════════════════════════════════════════════════════════════
# Utilitas
# ═══════════════════════════════════════════════════════════════════════════
async def _entity_full(entity_id: str) -> Dict[str, Any]:
    ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0}) or {}
    name = ent.get("legal_name") or ent.get("name") or ent.get("short_name") or ""
    addr = ", ".join([p for p in [ent.get("address", ""), ent.get("city", "")] if p])
    return {"id": entity_id, "name": name, "npwp": ent.get("npwp", ""), "address": addr}


def _faktor_dpp(seller: Dict[str, Any]) -> Tuple[int, int]:
    """TX-T1 — faktor DPP nilai lain transaksi: potret saat transaksi dibuat (`tax_dpp_pembilang/penyebut`, dibaca dari
    `tax_config_service.tax_settings` PT penjual); transaksi lama tanpa potret = aturan lama 11/12."""
    from services.tax_config_service import potret_lama
    p, q = seller.get("tax_dpp_pembilang"), seller.get("tax_dpp_penyebut")
    if p and q:
        return int(p), int(q)
    lama = potret_lama({"ppn_rate": 0, "ppn_mode": "excluded"})
    return lama["dpp_pembilang"], lama["dpp_penyebut"]


def _faktur_dpp(seller: Dict[str, Any], harga_jual: float) -> float:
    """Temuan lama #16 — DPP faktur ikut rezim penjualan (DPP Nilai Lain bila berlaku; TX-T1: faktor dari potret)."""
    if not seller.get("tax_dpp_nilai_lain"):
        return harga_jual
    p, q = _faktor_dpp(seller)
    return round(harga_jual * (p / q), 2)


def _net_amounts(seller: Dict[str, Any]) -> Dict[str, float]:
    """Nilai pajak BERSIH: nilai dokumen dikurangi bagian yang sudah diretur."""
    dpp = round(float(seller.get("subtotal") or 0)
                - float(seller.get("returned_subtotal") or 0), 2)
    ppn = round(float(seller.get("tax_amount") or 0)
                - float(seller.get("returned_tax") or 0), 2)
    return {"dpp": max(dpp, 0.0), "ppn": max(ppn, 0.0),
            "total": round(max(dpp, 0.0) + max(ppn, 0.0), 2)}


def _items_for_faktur(seller: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in seller.get("items", []):
        qty = float(it.get("quantity") or 0)
        price = float(it.get("unit_price") or 0)
        out.append({
            "product_name": it.get("product_name", ""),
            "sku": it.get("sku", ""),
            "quantity": qty,
            "unit": it.get("unit", ""),
            "price": price,
            "subtotal": round(qty * price, 2),
            "discount_amount": 0.0,
            "line_total": round(qty * price, 2),
        })
    return out


async def _active_out(pair_id: str) -> Optional[Dict[str, Any]]:
    return await db[COLL_OUT].find_one(
        {"interco_pair_id": pair_id, "status": {"$in": list(ACTIVE_OUT)},
         "replaced_by_id": None},
        {"_id": 0})


async def _active_in(pair_id: str) -> Optional[Dict[str, Any]]:
    return await db[COLL_IN].find_one(
        {"interco_pair_id": pair_id, "status": {"$in": list(ACTIVE_IN)}},
        {"_id": 0})


# ═══════════════════════════════════════════════════════════════════════════
# STATE untuk layar (kenapa tombol aktif / kenapa tidak)
# ═══════════════════════════════════════════════════════════════════════════
async def state(pair_id: str) -> Dict[str, Any]:
    """Keadaan faktur pajak internal satu pair + ALASAN bila belum bisa terbit.

    Layar WAJIB bisa menjelaskan kenapa tombolnya mati — bukan sekadar mati.
    """
    seller, buyer = await ics._pair_docs(pair_id)
    out = await _active_out(pair_id)
    inn = await _active_in(pair_id)
    net = _net_amounts(seller)

    reason = ""
    if not seller.get("tax_apply") or float(seller.get("tax_amount") or 0) <= EPS:
        reason = ("Transaksi ini TANPA PPN (mode "
                  f"'{seller.get('ppn_mode', 'ikut_pkp')}' / penjual non-PKP) — "
                  "tidak ada faktur pajak yang perlu diterbitkan.")
    elif seller.get("status") not in ISSUABLE_STATUSES:
        reason = ("Terbitkan **Faktur Internal** dulu (tombol di baris transaksi). "
                  "Faktur pajak mengikuti faktur dagangnya, bukan sebaliknya.")
    elif net["ppn"] <= EPS:
        reason = ("Seluruh nilai transaksi sudah diretur — tidak ada DPP yang tersisa "
                  "untuk difakturkan.")

    needs_replacement = bool(
        out and (abs(float(out.get("dpp") or 0) - _faktur_dpp(seller, net["dpp"])) > EPS
                 or abs(float(out.get("ppn_amount") or 0) - net["ppn"]) > EPS))

    return {
        "pair_id": pair_id,
        "tax_apply": bool(seller.get("tax_apply")),
        "tax_rate": float(seller.get("tax_rate") or 0),
        "ppn_mode": seller.get("ppn_mode", ""),
        "net_dpp": net["dpp"],
        "net_ppn": net["ppn"],
        "net_total": net["total"],
        "out": safe_doc(out) if out else None,
        "in": safe_doc(inn) if inn else None,
        "can_issue": bool(not out and not reason),
        "blocked_reason": reason,
        "needs_replacement": needs_replacement,
        "seller_entity_name": seller.get("seller_entity_name", ""),
        "buyer_entity_name": seller.get("buyer_entity_name", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
# TERBITKAN (kembar: keluaran penjual + masukan pembeli)
# ═══════════════════════════════════════════════════════════════════════════
async def _masa_terbuka(seller: Dict[str, Any], tanggal: Any, aksi: str) -> None:
    """PK-40 — masa pajak `tanggal` di PT penjual (keluaran) dan PT pembeli (masukan) harus belum dilaporkan."""
    from services.tax_center_service import assert_masa_terbuka
    for eid in dict.fromkeys([seller.get("seller_entity_id"), seller.get("buyer_entity_id")]):
        await assert_masa_terbuka(eid, tanggal, aksi=aksi)


def _sudah_terbit(nomor: str) -> str:
    return (f"Faktur pajak internal {nomor} sudah terbit untuk transaksi ini. Gunakan **Faktur Pengganti** bila "
            "angkanya berubah.")


async def issue(pair_id: str, actor: str = "", nsfp: str = "",
                kode_transaksi: str = "01", faktur_date: str = "",
                replaces: Optional[Dict[str, Any]] = None,
                replace_reason: str = "", cancel_in: Optional[Dict[str, Any]] = None,
                ) -> Dict[str, Any]:
    """Terbitkan PASANGAN faktur pajak internal untuk satu transaksi antar-PT.

    PK-40 (SL-13): keluaran & masukan ber-`active_key` `ic:{pair_id}` (+ `nsfp_key`); keunikan dijamin indeks
    `uq_fkt_*`/`uq_fpm_*`. Pengganti: faktur asli DIKLAIM dulu (kuncinya dilepas), faktur masukan lama (`cancel_in`)
    dibatalkan, baru pasangan baru disisip; sisip gagal → keadaan lama dikembalikan.
    """
    from pymongo.errors import DuplicateKeyError
    from services import tax_invoice_service as tis
    seller, buyer = await ics._pair_docs(pair_id)
    st = await state(pair_id)
    if st["blocked_reason"]:
        raise IntercoTaxError(st["blocked_reason"])
    if replaces is None and st["out"]:
        raise IntercoTaxError(_sudah_terbit(st['out'].get('number')))

    net = _net_amounts(seller)
    fdate = faktur_date or seller.get("invoiced_at") or now_iso()
    await _masa_terbuka(seller, fdate, "penggantian faktur" if replaces is not None else "penerbitan faktur")
    nsfp_raw = (nsfp or "").strip()
    dup = await tis._pemakai_nsfp(normalize_nsfp(nsfp_raw), kecuali=((replaces or {}).get("id", ""),))
    if dup:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=tis.pesan_nsfp(nsfp_raw, dup.get("number")))
    ent_s = await _entity_full(seller["seller_entity_id"])
    ent_b = await _entity_full(seller["buyer_entity_id"])
    items = _items_for_faktur(seller)
    rate = float(seller.get("tax_rate") or 0)
    nominal = float(seller.get("tax_rate_nominal") or rate)
    is_pengganti = replaces is not None

    out_id = new_id("fkt")
    in_id = new_id("fpm")
    out_number = await next_doc_number(COLL_OUT, "number", "FKT-",
                                      entity_id=seller["seller_entity_id"])
    in_number = await next_input_number(seller["buyer_entity_id"])   # KP-T5 — PT pembeli (faktur masukan)

    shared_tax = {
        "interco_pair_id": pair_id,
        "interco_seller_id": seller["id"],
        "interco_buyer_id": buyer["id"],
        "interco_seller_number": seller.get("number", ""),
        "interco_buyer_number": buyer.get("number", ""),
        "source_type": "interco",
        "is_internal": True,
        "dpp": _faktur_dpp(seller, net["dpp"]),
        "harga_jual": net["dpp"],
        "ppn_rate": nominal,
        "ppn_mode": "excluded",
        "ppn_amount": net["ppn"],
        "grand_total": net["total"],
        # TX-T1 — "Aturan pajak saat terbit": tarif & faktor dari transaksi; hitungan antar-PT dibulatkan per dokumen
        # ke dua desimal (`interco_service._totals_from_items`, tidak diatur Pusat Pengaturan).
        "tax_snapshot": {"ppn_rate": nominal, "dpp_nilai_lain": bool(seller.get("tax_dpp_nilai_lain")),
                         "dpp_pembilang": _faktor_dpp(seller)[0], "dpp_penyebut": _faktor_dpp(seller)[1],
                         "ppn_mode": "excluded", "pembulatan_tingkat": "dokumen", "pembulatan_satuan": "dua_desimal",
                         "is_pkp": True, "berlaku_pada": str(seller.get("created_at") or "")},
    }

    # ── Buku PENJUAL: Faktur Pajak KELUARAN ──────────────────────────────
    out_doc: Dict[str, Any] = {
        "id": out_id,
        "number": out_number,
        "nsfp": nsfp_raw,
        "kode_transaksi": (kode_transaksi or "01").strip(),
        "status": "pengganti" if is_pengganti else "normal",
        "replaces_id": (replaces or {}).get("id"),
        "replaced_by_id": None,
        "cancel_reason": "",
        "replace_reason": (replace_reason or "").strip(),
        "faktur_date": fdate,
        # Dokumen internal tidak lahir dari pesanan penjualan — `order_id` kosong,
        # `order_number` memakai nomor transaksi antar-PT supaya layar tetap jujur.
        "order_id": "",
        "order_number": seller.get("number", ""),
        "entity_id": seller["seller_entity_id"],
        "seller_name": ent_s["name"],
        "seller_npwp": ent_s["npwp"],
        "seller_address": ent_s["address"],
        "customer_id": ent_b["id"],
        "customer_name": ent_b["name"],
        "customer_npwp": ent_b["npwp"],
        "customer_address": ent_b["address"],
        "has_customer_npwp": bool(ent_b["npwp"]),
        "items": items,
        "total_amount": float(seller.get("subtotal") or 0),
        "discount_total": round(float(seller.get("returned_subtotal") or 0), 2),
        "net_subtotal": net["dpp"],
        "dpp_nilai_lain": bool(seller.get("tax_dpp_nilai_lain")),
        "effective_rate": rate,
        "is_pkp": True,
        "counterpart_faktur_id": in_id,
        "counterpart_faktur_number": in_number,
        "created_by": actor or "system",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **shared_tax,
    }

    # ── Buku PEMBELI: Faktur Pajak MASUKAN ───────────────────────────────
    in_doc: Dict[str, Any] = {
        "id": in_id,
        "number": in_number,
        "nsfp": nsfp_raw or out_number,   # tanpa NSFP DJP → pakai nomor faktur internal
        "nsfp_digits": normalize_nsfp(nsfp_raw),
        "kode_transaksi": (kode_transaksi or "01").strip(),
        "status": "recorded",
        "faktur_date": fdate,
        "period": period_of(fdate),
        "entity_id": seller["buyer_entity_id"],
        # Lawan transaksi = PT penjual (diperlakukan seperti supplier di buku pembeli).
        "supplier_id": seller["seller_entity_id"],
        "supplier_name": ent_s["name"],
        "supplier_npwp": ent_s["npwp"],
        "vendor_bill_id": "",
        "bill_number": buyer.get("number", ""),
        "supplier_invoice_no": seller.get("number", ""),
        "po_id": "",
        "po_number": buyer.get("number", ""),
        "counterpart_faktur_id": out_id,
        "counterpart_faktur_number": out_number,
        "notes": ("Faktur Pajak Masukan internal (antar-PT) — pasangan dari "
                  f"{out_number} di buku {ent_s['name']}."),
        "timeline": [timeline_entry(
            "recorded", "Faktur Pajak Masukan internal dicatat", actor or "system",
            f"{seller.get('number', '')} · DPP {rupiah(net['dpp'])} · "
            f"PPN {rupiah(net['ppn'])}")],
        "created_by": actor or "system",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **shared_tax,
    }

    # PK-40 — kunci aktif kedua dokumen kembar.
    out_doc.update(tis.kunci_aktif_keluaran(out_doc))
    in_doc.update(kunci_aktif_masukan(in_doc))

    kunci_asli = tis.kunci_aktif_keluaran(replaces) if is_pengganti else {}
    if is_pengganti:   # (1) klaim faktur asli: hanya satu penggantian yang menang
        klaim = await db[COLL_OUT].update_one(
            {"id": replaces["id"], "replaced_by_id": None, "status": {"$in": list(ACTIVE_OUT)}},
            {"$set": {"replaced_by_id": out_id, "updated_at": now_iso()}, "$unset": dict(tis.KUNCI_FAKTUR)})
        if not klaim.matched_count:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Faktur ini sudah pernah diganti.")
    if cancel_in:      # (2) faktur masukan lama dibatalkan (kuncinya dicabut) sebelum pasangan baru lahir
        await db[COLL_IN].update_one(
            {"id": cancel_in["id"], "status": {"$in": list(ACTIVE_IN)}},
            {"$set": {"status": "cancelled", "cancel_reason": f"Diganti: {replace_reason}",
                      "cancelled_by": actor or "system", "cancelled_at": now_iso(), "updated_at": now_iso()},
             "$unset": dict(tis.KUNCI_FAKTUR),
             "$push": {"timeline": timeline_entry(
                 "replaced", "Diganti faktur masukan baru", actor or "system", replace_reason)}})
    out_masuk = False
    try:               # (3) sisip pasangan baru
        await db[COLL_OUT].insert_one(dict(out_doc))
        out_masuk = True
        await db[COLL_IN].insert_one(dict(in_doc))
    except Exception as exc:  # noqa: BLE001 — kembalikan keadaan sebelum aksi ini, lalu teruskan galatnya
        await _kembalikan(out_doc["id"] if out_masuk else "", replaces, out_id, kunci_asli, cancel_in)
        if isinstance(exc, DuplicateKeyError):
            coll, doc = (COLL_IN, in_doc) if out_masuk else (COLL_OUT, out_doc)
            err = await tis.galat_kunci_kembar(coll, exc, doc, kecuali_id=doc["id"], nsfp=nsfp_raw,
                                               pesan_aktif=_sudah_terbit)
            if err:
                raise err from exc
        raise

    await _stamp_pair(pair_id, out_doc, in_doc)
    await _link(pair_id, seller, buyer, out_doc, in_doc)
    return {"out": safe_doc(out_doc), "in": safe_doc(in_doc)}


async def _kembalikan(out_baru_id: str, replaces: Optional[Dict[str, Any]], out_id: str,
                      kunci_asli: Dict[str, str], cancel_in: Optional[Dict[str, Any]]) -> None:
    """PK-40 — kompensasi bila sisip pasangan gagal: buang faktur keluaran yang baru lahir (belum dirujuk apa pun),
    kembalikan faktur asli dan faktur masukan lama ke keadaan aktifnya."""
    try:
        if out_baru_id:
            await db[COLL_OUT].delete_one({"id": out_baru_id})
        if replaces:
            await db[COLL_OUT].update_one({"id": replaces["id"], "replaced_by_id": out_id},
                                          {"$set": {"replaced_by_id": None, "updated_at": now_iso(), **kunci_asli}})
        if cancel_in:
            kunci_in = kunci_aktif_masukan({**cancel_in, "status": "recorded"})
            await db[COLL_IN].update_one(
                {"id": cancel_in["id"], "status": "cancelled"},
                {"$set": {"status": "recorded", "updated_at": now_iso(), **kunci_in},
                 "$unset": {"cancel_reason": "", "cancelled_by": "", "cancelled_at": ""}, "$pop": {"timeline": 1}})
    except Exception as exc:  # noqa: BLE001
        print(f"[interco_tax] kompensasi gagal ({out_id}): {exc}")


async def _stamp_pair(pair_id: str, out_doc: Optional[Dict[str, Any]],
                      in_doc: Optional[Dict[str, Any]], status: str = "issued") -> None:
    """Cap nomor faktur pajak di KEDUA dokumen kembar (biar terlihat di daftar)."""
    upd: Dict[str, Any] = {
        "tax_faktur_status": status,
        "tax_faktur_out_id": (out_doc or {}).get("id", ""),
        "tax_faktur_out_number": (out_doc or {}).get("number", ""),
        "tax_faktur_in_id": (in_doc or {}).get("id", ""),
        "tax_faktur_in_number": (in_doc or {}).get("number", ""),
        "updated_at": now_iso(),
    }
    await db[ics.COLL_ICT].update_many({"pair_id": pair_id}, {"$set": upd})


async def _link(pair_id: str, seller: Dict[str, Any], buyer: Dict[str, Any],
                out_doc: Dict[str, Any], in_doc: Dict[str, Any]) -> None:
    try:
        from services import doc_refs_service as _refs
        await _refs.safe_link(("tax_invoice", out_doc["id"]),
                              ("interco_transaction", seller["id"]), "parent",
                              note="Faktur pajak keluaran atas transaksi antar-PT")
        await _refs.safe_link(("input_tax_invoice", in_doc["id"]),
                              ("interco_transaction", buyer["id"]), "parent",
                              note="Faktur pajak masukan atas transaksi antar-PT")
        await _refs.safe_link(("tax_invoice", out_doc["id"]),
                              ("input_tax_invoice", in_doc["id"]), "child",
                              note="Pasangan faktur pajak internal (keluaran ↔ masukan)")
    except Exception as exc:  # noqa: BLE001 — jejak, bukan syarat sah dokumen
        print(f"[interco_tax] tautan dokumen gagal {pair_id}: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# PENGGANTI & BATAL (append-only: dokumen lama tidak pernah diedit)
# ═══════════════════════════════════════════════════════════════════════════
async def replace(pair_id: str, reason: str, actor: str = "") -> Dict[str, Any]:
    """Terbitkan Faktur Pajak PENGGANTI memakai angka bersih terbaru (sesudah retur)."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise IntercoTaxError(
            "Alasan penggantian faktur pajak wajib diisi (minimal 5 huruf) — "
            "dokumen pajak tidak boleh berubah tanpa sebab yang tercatat.")
    out = await _active_out(pair_id)
    if not out:
        raise IntercoTaxError("Belum ada faktur pajak internal yang bisa diganti.")
    inn = await _active_in(pair_id)
    # PK-40 — masa faktur asli (kedua PT) harus belum dilaporkan; masa pengganti diperiksa `issue`. PERIKSA sebelum
    # tulisan apa pun: faktur masukan lama baru dibatalkan di dalam `issue` sesudah faktur asli diklaim.
    seller, _ = await ics._pair_docs(pair_id)
    await _masa_terbuka(seller, out.get("faktur_date"), "penggantian faktur")
    return await issue(pair_id, actor=actor, nsfp=out.get("nsfp", ""),
                       kode_transaksi=out.get("kode_transaksi", "01"),
                       replaces=out, replace_reason=reason, cancel_in=inn)


async def cancel(pair_id: str, reason: str, actor: str = "") -> Dict[str, Any]:
    """Batalkan pasangan faktur pajak internal (wajib alasan)."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise IntercoTaxError("Alasan pembatalan faktur pajak wajib diisi (minimal 5 huruf).")
    out = await _active_out(pair_id)
    inn = await _active_in(pair_id)
    if not out and not inn:
        raise IntercoTaxError("Tidak ada faktur pajak internal aktif untuk transaksi ini.")
    # PK-40 — masa faktur keluaran (PT penjual) dan masukan (PT pembeli) harus belum dilaporkan.
    from services.tax_center_service import assert_masa_terbuka
    if out:
        await assert_masa_terbuka(out.get("entity_id"), out.get("faktur_date"), aksi="pembatalan faktur")
    if inn:
        await assert_masa_terbuka(inn.get("entity_id"), inn.get("faktur_date"), aksi="pembatalan faktur")
    if out:
        await db[COLL_OUT].update_one(
            {"id": out["id"]},
            {"$set": {"status": "batal", "cancel_reason": reason, "updated_at": now_iso()},
             "$unset": {"active_key": "", "nsfp_key": ""}})
    if inn:
        await db[COLL_IN].update_one(
            {"id": inn["id"]},
            {"$set": {"status": "cancelled", "cancel_reason": reason,
                      "cancelled_by": actor or "system", "cancelled_at": now_iso(),
                      "updated_at": now_iso()},
             "$unset": {"active_key": "", "nsfp_key": ""},
             "$push": {"timeline": timeline_entry(
                 "cancelled", "Faktur masukan internal dibatalkan", actor or "system", reason)}})
    await _stamp_pair(pair_id, None, None, status="cancelled")
    return await state(pair_id)


# ═══════════════════════════════════════════════════════════════════════════
# RETUR → tandai faktur perlu pengganti (tidak diedit diam-diam)
# ═══════════════════════════════════════════════════════════════════════════
async def flag_needs_replacement(pair_id: str, note: str = "") -> None:
    out = await _active_out(pair_id)
    if not out:
        return
    await db[COLL_OUT].update_one(
        {"id": out["id"]},
        {"$set": {"needs_replacement": True,
                  "needs_replacement_note": note or "Ada retur antar-PT sesudah faktur terbit.",
                  "updated_at": now_iso()}})
    await db[ics.COLL_ICT].update_many(
        {"pair_id": pair_id},
        {"$set": {"tax_faktur_status": "needs_replacement", "updated_at": now_iso()}})
