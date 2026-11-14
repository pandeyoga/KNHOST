"""FASE G-6 — Layanan **TRANSAKSI ANTAR ENTITAS** (jual-beli antar-PT dalam grup).

Antar-PT diperlakukan **jual-beli**, bukan pindah gudang. Setiap transaksi lahir
sebagai **dokumen kembar**:
  * PT penjual (`role="seller"`)  — SO + Surat Jalan + Invoice internal
  * PT pembeli (`role="buyer"`)   — PO internal + Vendor Bill internal
Keduanya menunjuk `pair_id` yang sama. Barang fisiknya tetap berjalan lewat jalur
`warehouse_transfers` yang sudah ada (lapisan gudang).

**Invarian yang dijaga di sini:**
  * INV-IC-01 — setiap transaksi punya pasangan jurnal seimbang di DUA buku.
  * INV-IC-02 — IC-AR penjual = IC-AP pembeli untuk pasangan entitas (setelah settlement).
  * INV-IC-04 — `interco_accounts` == Σ transaksi − Σ settlement (tidak drift).
  * INV-IC-05 — PPN keluaran penjual == PPN masukan pembeli (bila ber-PPN); nol bila
                mode `tanpa_ppn`.

Keputusan pemilik (mengikat, 2026-07-30):
  1. Harga = `fixed_price` dari kontrak internal (`supplier_contracts` dengan
     `partner_kind="entity"`). Bila belum ada kontrak untuk barang → transaksi DITOLAK.
  2. PPN per-PT lewat config `antar_entitas.ppn_mode`.
  3. Settlement sewaktu-waktu (tanpa job penjadwal).
"""
from __future__ import annotations

from datetime import datetime, timezone
import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

from core_utils import (
    DEFAULT_ENTITY_ID, MoneyDecimal, new_id, next_doc_number, now_iso, parse_decimal,
    rupiah, safe_doc,
)
from db import db
from services import dual_qty_service as _dual  # FASE U — dua satuan (roll + ukuran)
from services import config_resolver
from services import gl_service
from services import roll_cost_history as _cost_history
from services.costing_service import wac_for_product

EPS = 0.01

# ── Koleksi ──────────────────────────────────────────────────────────────────
COLL_ICT = "interco_transactions"
COLL_ICA = "interco_accounts"
COLL_ICS = "interco_settlements"

# FASE E-8 (E8.10b#4) — Admin Sales boleh MELEPAS SENDIRI transaksi antar-PT di BAWAH ambang (keputusan pemilik:
# penahannya nilai rupiah, bukan jabatan). KP-T4 — daftar `SELF_SERVE_BELOW_THRESHOLD` pindah ke Aturan Persetujuan
# (jenis `interco`, rentang di bawah ambang; baris bawaan `approval_policy_service.BAWAAN_ANTAR_PT_TANPA_ACC`).

# ── Status siklus ────────────────────────────────────────────────────────────
STATUSES = ("draft", "confirmed", "shipped", "received", "invoiced", "settled",
            "returned", "disputed", "cancelled")
STATUS_LABEL = {
    "draft": "Draf",
    "confirmed": "Dikonfirmasi",
    "shipped": "Dikirim",
    "received": "Diterima",
    "invoiced": "Difakturkan",
    "settled": "Lunas",
    # FASE G-6b — seluruh nilainya sudah kembali lewat retur antar-PT (bukan
    # dibatalkan: dokumen & jurnalnya tetap ada, hanya sudah tidak berutang).
    "returned": "Diretur Penuh",
    "disputed": "Sengketa",
    "cancelled": "Dibatalkan",
}
OPEN_STATUSES = ("confirmed", "shipped", "received", "invoiced")

PRICING_MODES = ("fixed_price", "at_cost", "cost_plus_pct")
PPN_MODES = ("ikut_pkp", "tanpa_ppn", "dengan_ppn")


class IntercoConflict(Exception):
    """PK-06 — konflik keadaan (sisa berubah, jurnal transaksi masih gagal, kunci dipakai ulang) → 409."""


class IntercoError(Exception):
    """Pelanggaran aturan bisnis antar-PT (dipetakan ke HTTP 400 di router)."""


class IntercoForbidden(IntercoError):
    """PK-30 (IC-10) — harga/PPN di luar kontrak tanpa izin `interco.override_terms` → HTTP 403."""


class IntercoLengthMismatch(IntercoError, IntercoConflict):
    """PK-30 (IC-02) — panjang roll ≠ jumlah dokumen pada mode `tolak` → HTTP 409 (tetap sebuah `IntercoError`)."""


#: PK-30 — kunci pengaturan "Bila panjang roll beda dari pesanan antar-PT" (dibaca dengan PT PENJUAL).
KUNCI_SELISIH_PANJANG = "antar_entitas.selisih_panjang"
#: PK-30 — toleransi pembulatan harga satuan (bukan aturan bisnis): selisih ≤ setengah sen = harga yang sama.
_HARGA_EPS = 0.005
PESAN_TANPA_IZIN_HARGA = ("Anda belum punya akses untuk mengubah harga atau PPN antar-PT di luar kontrak. Minta Admin "
                          "menambahkan akses 'Transaksi Antar Badan Usaha'.")
PESAN_ALASAN_HARGA = "Alasan mengubah harga atau PPN wajib diisi (minimal 5 huruf)."


# ═══════════════════════════════════════════════════════════════════════════
# Utils
# ═══════════════════════════════════════════════════════════════════════════
def _today() -> str:
    from services.book_date import tanggal_buku   # PK-37 — "hari ini" = tanggal buku WIB (dulu tanggal UTC)
    return tanggal_buku()


async def _entity_snapshot(entity_id: str) -> Dict[str, str]:
    if not entity_id:
        return {"id": "", "name": "", "is_pkp": False}
    ent = await db.business_entities.find_one(
        {"id": entity_id},
        {"_id": 0, "name": 1, "legal_name": 1, "short_name": 1,
         "is_pkp": 1, "default_tax_mode": 1, "npwp": 1}) or {}
    # PKP flag: prefer explicit `is_pkp`; fallback to default_tax_mode == "ppn".
    is_pkp = ent.get("is_pkp")
    if is_pkp is None:
        is_pkp = (ent.get("default_tax_mode") or "").lower() == "ppn"
    name = ent.get("name") or ent.get("legal_name") or ent.get("short_name") or ""
    return {
        "id": entity_id,
        "name": name,
        "is_pkp": bool(is_pkp),
        "npwp": ent.get("npwp", ""),
    }


async def _product_snapshot(product_id: str) -> Dict[str, str]:
    if not product_id:
        return {"sku": "", "name": "", "base_unit": ""}
    p = await db.products.find_one({"id": product_id},
                                   {"_id": 0, "sku": 1, "name": 1, "base_unit": 1}) or {}
    return {"sku": p.get("sku", ""), "name": p.get("name", ""),
            "base_unit": p.get("base_unit", "")}


async def _config(key: str, entity_id: str = "") -> Any:
    ctx = {"entity_id": entity_id} if entity_id else None
    return await config_resolver.value_of(key, ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Resolusi harga & pajak (keputusan pemilik #1 & #2)
# ═══════════════════════════════════════════════════════════════════════════
async def _find_active_internal_contract(seller_entity_id: str, buyer_entity_id: str,
                                         product_id: str) -> Optional[Dict[str, Any]]:
    """Cari kontrak internal aktif (partner_kind=entity) untuk barang tertentu.

    Kontrak internal disimpan di `supplier_contracts` dengan:
      * `entity_id` = PT penjual (yang punya kontrak jual internal)
      * `partner_kind` = "entity"
      * `partner_id` = PT pembeli
      * `product_id` = barang
      * `status` = "active"
    """
    today = _today()
    # Bila ada LEBIH DARI SATU kontrak aktif untuk pasangan PT × barang yang sama
    # (mis. harga demo lalu harga baru), yang berlaku adalah yang PALING BARU.
    # Sebelumnya dipakai `find_one` tanpa urutan, jadi harga yang menang mengikuti
    # urutan penyimpanan dokumen — tidak bisa dijelaskan ke siapa pun dan bisa
    # berubah sendiri. Harga barang tidak boleh bergantung pada urutan insert.
    docs = await db.supplier_contracts.find({
        "entity_id": seller_entity_id,
        "partner_kind": "entity",
        "partner_id": buyer_entity_id,
        "product_id": product_id,
        "status": "active",
    }, {"_id": 0}).to_list(200)
    if not docs:
        return None
    docs.sort(key=lambda d: (str(d.get("valid_from") or ""),
                             str(d.get("created_at") or ""),
                             str(d.get("contract_number") or "")), reverse=True)
    doc = next((d for d in docs
                if not ((d.get("valid_from") or "") > today
                        or ((d.get("valid_to") or "") and (d.get("valid_to") or "") < today))),
               None)
    if not doc:
        return None
    return doc


async def _resolve_price(seller_entity_id: str, buyer_entity_id: str, product_id: str,
                        override_price: Optional[float], pricing_mode: str) -> Dict[str, Any]:
    """Kembalikan harga per unit + sumbernya. RAISE bila fixed_price tanpa kontrak."""
    if override_price is not None and override_price > 0:
        return {"unit_price": round(float(override_price), 2), "source": "override",
                "contract_id": ""}
    contract = await _find_active_internal_contract(
        seller_entity_id, buyer_entity_id, product_id)
    if pricing_mode == "fixed_price":
        if not contract:
            snap = await _product_snapshot(product_id)
            raise IntercoError(
                f"Barang {snap['sku'] or product_id} belum punya harga internal di kontrak "
                f"aktif untuk pasangan PT ini. Buat kontrak internal (partner_kind='entity') "
                f"dengan harga tetap sebelum menerbitkan transaksi.")
        rate = float(contract.get("tariff_rate") or 0)
        if rate <= 0:
            raise IntercoError(
                f"Kontrak internal {contract.get('contract_number', '')} tidak mencantumkan "
                f"harga (tariff_rate). Lengkapi kontrak sebelum menerbitkan transaksi.")
        return {"unit_price": round(rate, 2), "source": "fixed_price",
                "contract_id": contract.get("id", "")}
    if pricing_mode == "at_cost":
        wac = await wac_for_product(product_id, entity_id=seller_entity_id,
                                    use_cache=False)
        cost = round(float(wac.get("wac") or 0), 2)
        if cost <= 0:
            raise IntercoError(
                f"HPP untuk barang di PT penjual belum tersedia. Tidak bisa menerbitkan "
                f"transaksi 'at_cost' tanpa nilai persediaan.")
        return {"unit_price": cost, "source": "at_cost",
                "contract_id": contract.get("id") if contract else ""}
    if pricing_mode == "cost_plus_pct":
        wac = await wac_for_product(product_id, entity_id=seller_entity_id,
                                    use_cache=False)
        cost = float(wac.get("wac") or 0)
        margin_pct = float((contract or {}).get("ppi") or 0)  # simpan margin_pct di kontrak.ppi
        if cost <= 0:
            raise IntercoError("HPP barang belum tersedia untuk mode cost_plus_pct.")
        price = round(cost * (1.0 + margin_pct / 100.0), 2)
        return {"unit_price": price, "source": "cost_plus_pct",
                "contract_id": contract.get("id") if contract else ""}
    raise IntercoError(f"Mode harga '{pricing_mode}' tidak dikenal.")


async def _resolve_tax(seller_entity_id: str, ppn_mode: str) -> Dict[str, Any]:
    """Tarif PPN efektif untuk transaksi. INV-IC-05: kedua sisi harus sama besar."""
    seller = await _entity_snapshot(seller_entity_id)
    if ppn_mode == "tanpa_ppn":
        return {"apply": False, "rate": 0.0, "reason": "config tanpa_ppn"}
    if ppn_mode == "dengan_ppn":
        return {"apply": True, **await _interco_rate(seller_entity_id), "reason": "config dengan_ppn"}
    # ikut_pkp (bawaan)
    if seller.get("is_pkp"):
        return {"apply": True, **await _interco_rate(seller_entity_id), "reason": "penjual PKP"}
    return {"apply": False, "rate": 0.0, "reason": "penjual non-PKP"}


async def _interco_rate(seller_entity_id: str) -> Dict[str, Any]:
    """Temuan lama #16 — tarif antar-PT = aturan pajak penjualan PT penjual (12% × DPP 11/12),
    kecuali ada tarif flat khusus di `antar_entitas.ppn_rate_percent` (> 0).
    `rate` = tarif EFEKTIF atas harga (dipakai semua hitungan rupiah); nominal & flag DPP untuk faktur."""
    flat = float(await _config("antar_entitas.ppn_rate_percent", seller_entity_id) or 0)
    if flat > 0:
        return {"rate": flat, "rate_nominal": flat, "dpp_nilai_lain": False}
    from services.config_service import get_effective_settings
    tax = (await get_effective_settings(seller_entity_id)).get("tax", {})
    nominal = float(tax.get("ppn_rate") or 0) or 12.0
    nl = bool(tax.get("dpp_nilai_lain", False)) if tax.get("ppn_rate") else True
    return {"rate": round(nominal * (11.0 / 12.0 if nl else 1.0), 4), "rate_nominal": nominal, "dpp_nilai_lain": nl}


# ═══════════════════════════════════════════════════════════════════════════
# CREATE / lifecycle
# ═══════════════════════════════════════════════════════════════════════════
async def _next_number(entity_id: str) -> str:
    return await next_doc_number(COLL_ICT, "number", "IC-", entity_id=entity_id)


def _totals_from_items(items: List[Dict[str, Any]], tax_rate: float, tax_apply: bool
                       ) -> Dict[str, float]:
    subtotal = round(sum(float(it["quantity"]) * float(it["unit_price"]) for it in items), 2)
    tax = round(subtotal * (tax_rate / 100.0), 2) if tax_apply else 0.0
    return {"subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2)}


async def _assert_may_release(actor_user: Optional[Dict[str, Any]], grand: float,
                             seller_entity_id: str) -> None:
    """Gerbang WEWENANG melepas transaksi antar-PT (dipakai `create(submit_now)` & `confirm`).

    FASE E-8 (E8.10b#4) — DUA CACAT LAMA yang ditutup di sini:

    1. **Peringkat peran adalah angka ajaib.** Dulu tertulis dua kali sebagai
       `{"warehouse":0,"sales":0,"manager":1,"admin":2}`. Dua peran baru E-8 TIDAK ADA
       di peta itu, jadi `sales_admin` jatuh ke peringkat 0 — sama dengan gudang —
       dan setiap "Ambil dari PT lain" ditolak dengan *"butuh persetujuan minimal peran
       manager"*. Sekarang peringkat dibaca dari `role_registry` (INV-ROLE-01).

    2. **Admin Sales terkunci padahal pemilik memberinya wewenang penuh.** Keputusan
       pemilik E8.10b#4: keputusan pemenuhan (termasuk ambil dari PT lain) adalah
       wewenang PENUH Admin Sales **tanpa** persetujuan manajer; satu-satunya penahan
       adalah **ambang rupiah** di Pusat Pengaturan. Karena itu di bawah ambang,
       `sales_admin` memenuhi gerbang nilai-kecil; di atas ambang ia WAJIB naik ke
       peran bernilai besar seperti peran lain. Ambangnya tetap hidup dan bisa
       diturunkan pemilik kapan pun tanpa deploy — bukan pintu yang dibuka permanen.
    """
    # KP-T4 — siapa yang boleh melepas dibaca dari Aturan Persetujuan (jenis `interco`, PT penjual, nilai transaksi):
    # baris bawaannya = ambang `antar_entitas.*` lama (di bawah ambang ≥ peran persetujuan + Admin Sales; di atasnya
    # ≥ peran bernilai besar). Izin `interco.approve` diperiksa router konfirmasi; jalur `create(submit_now)` hanya
    # menilai peran, seperti dulu.
    from services import approval_policy_service as _aps
    res = await _aps.can_decide("interco", seller_entity_id or None, float(grand or 0), actor_user or {},
                                check_permission=False)
    if not res["allowed"]:
        raise IntercoError(res["message"] + " Simpan dulu sebagai draf, lalu minta persetujuan.")


async def _terms_override(actor_user: Optional[Dict[str, Any]], actor: str, reason: Any, *,
                          pricing: Optional[Dict[str, str]], ppn: Optional[Dict[str, str]],
                          lines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """PK-30 (IC-10) — harga/mode di luar kontrak & pengaturan PT penjual: izin `interco.override_terms` lalu alasan
    ≥ 5 huruf (keduanya sebelum dokumen lahir). Tanpa penyimpangan → None (tidak ada yang diperiksa/dicatat)."""
    if not (pricing or ppn or lines):
        return None
    from dependencies import has_permission
    if not actor_user or not await has_permission(actor_user, "interco", "override_terms"):
        raise IntercoForbidden(PESAN_TANPA_IZIN_HARGA)
    alasan = str(reason or "").strip()
    if len(alasan) < 5:
        raise IntercoError(PESAN_ALASAN_HARGA)
    return {"by": actor or actor_user.get("name", ""), "by_id": actor_user.get("id", ""), "reason": alasan,
            "at": now_iso(), "pricing_mode": pricing, "ppn_mode": ppn, "lines": lines}


async def create(payload: Dict[str, Any], actor: str = "",
                 actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    seller = (payload.get("seller_entity_id") or "").strip()
    buyer = (payload.get("buyer_entity_id") or "").strip()
    if not seller or not buyer:
        raise IntercoError("PT penjual dan PT pembeli wajib dipilih.")
    if seller == buyer:
        raise IntercoError("PT penjual dan PT pembeli harus berbeda.")

    items_in = payload.get("items") or []
    if not items_in:
        raise IntercoError("Minimal satu barang harus dimasukkan.")

    # PK-30 (IC-10) — nilai STANDAR = pengaturan PT penjual; isi permintaan yang berbeda = penyimpangan.
    std_pricing = await _config("antar_entitas.pricing_mode", seller) or "fixed_price"
    pricing_req = (payload.get("pricing_mode") or "").strip().lower()
    pricing_mode = pricing_req or std_pricing
    if pricing_mode not in PRICING_MODES:
        raise IntercoError(f"Mode harga '{pricing_mode}' tidak dikenal.")

    std_ppn = await _config("antar_entitas.ppn_mode", seller) or "ikut_pkp"
    ppn_req = (payload.get("ppn_mode") or "").strip().lower()
    ppn_mode = ppn_req or std_ppn
    if ppn_mode not in PPN_MODES:
        raise IntercoError(f"Mode PPN '{ppn_mode}' tidak dikenal.")

    tax = await _resolve_tax(seller, ppn_mode)

    # Resolusi harga per baris
    items: List[Dict[str, Any]] = []
    harga_menyimpang: List[Dict[str, Any]] = []
    for it in items_in:
        pid = (it.get("product_id") or "").strip()
        qty = float(it.get("quantity") or 0)
        if not pid or qty <= 0:
            raise IntercoError("Setiap baris wajib produk & jumlah > 0.")
        override = it.get("unit_price")
        override_val = float(override) if override not in (None, "", 0) else None
        if override_val is None:
            pr = await _resolve_price(seller, buyer, pid, None, pricing_mode)
        else:
            # PK-30 — harga ketikan dibandingkan dengan harga standar mode ini (kontrak belum ada = tidak ada standar).
            try:
                std = await _resolve_price(seller, buyer, pid, None, pricing_mode)
            except IntercoError:
                std = None
            if std is not None and abs(round(override_val, 2) - float(std["unit_price"])) <= _HARGA_EPS:
                pr = std
            else:
                pr = await _resolve_price(seller, buyer, pid, override_val, pricing_mode)
                harga_menyimpang.append({"product_id": pid,
                                         "standard_price": float(std["unit_price"]) if std else None,
                                         "used_price": float(pr["unit_price"])})
        snap = await _product_snapshot(pid)
        items.append({
            "product_id": pid,
            "sku": snap["sku"],
            "product_name": snap["name"],
            "quantity": round(qty, 4),
            "unit": snap["base_unit"],
            "unit_price": pr["unit_price"],
            "price_source": pr["source"],
            "contract_id": pr["contract_id"],
            "line_subtotal": round(qty * pr["unit_price"], 2),
            "notes": (it.get("notes") or "").strip(),
            "preferred_roll_ids": [str(x) for x in (it.get("preferred_roll_ids") or []) if x],   # P10.2
            # FASE U — dua satuan pada jual-beli antar-PT (roll + ukuran).
            **(await _dual.stamp({"unit": snap["base_unit"], **it})),
        })

    totals = _totals_from_items(items, tax["rate"], tax["apply"])
    seller_snap = await _entity_snapshot(seller)
    buyer_snap = await _entity_snapshot(buyer)
    # PK-30 (IC-10) — PERIKSA sebelum nomor & dokumen: penyimpangan butuh izin + alasan; penjual non-PKP tanpa PPN.
    terms_override = await _terms_override(
        actor_user, actor, payload.get("override_reason"),
        pricing={"standar": std_pricing, "dipakai": pricing_mode} if pricing_req and pricing_req != std_pricing
        else None,
        ppn={"standar": std_ppn, "dipakai": ppn_mode} if ppn_req and ppn_req != std_ppn else None,
        lines=harga_menyimpang)
    if tax["apply"] and not seller_snap["is_pkp"]:
        raise IntercoError(f"PT penjual {seller_snap['name'] or seller} bukan PKP, jadi transaksi ini tidak boleh "
                           "memungut PPN. Pilih mode PPN \"Tanpa PPN\".")
    pair_id = new_id("icp")
    seller_id = new_id("ict")
    buyer_id = new_id("ict")
    number_s = await _next_number(seller)
    number_b = await _next_number(buyer)
    doc_date = payload.get("doc_date") or _today()
    due_date = payload.get("due_date") or ""
    submit_now = bool(payload.get("submit_now"))

    # Bila submit_now → periksa ambang persetujuan (samakan gerbang dengan confirm()).
    if submit_now:
        await _assert_may_release(actor_user, float(totals["total"]), seller)

    status = "confirmed" if submit_now else "draft"
    ts = now_iso()
    submit_ts = ts if submit_now else ""

    common = {
        "pair_id": pair_id,
        "seller_entity_id": seller,
        "seller_entity_name": seller_snap["name"],
        "buyer_entity_id": buyer,
        "buyer_entity_name": buyer_snap["name"],
        "counterpart_number": "",  # diisi setelah insert (nomor kembar)
        "items": items,
        "subtotal": totals["subtotal"],
        "tax_apply": tax["apply"],
        "tax_rate": tax["rate"],
        "tax_rate_nominal": tax.get("rate_nominal", tax["rate"]),
        "tax_dpp_nilai_lain": bool(tax.get("dpp_nilai_lain")),
        "tax_amount": totals["tax"],
        "grand_total": totals["total"],
        "pricing_mode": pricing_mode,
        "ppn_mode": ppn_mode,
        # PK-30 (IC-10) — potret status PKP kedua PT saat dibuat + penyimpangan harga/PPN (D3: keputusan + potret).
        "seller_is_pkp": bool(seller_snap["is_pkp"]),
        "buyer_is_pkp": bool(buyer_snap["is_pkp"]),
        "tax_warning": "pembeli_non_pkp" if tax["apply"] and not buyer_snap["is_pkp"] else "",
        "terms_override": terms_override,
        "contract_id": (payload.get("contract_id") or "").strip(),
        # FASE E-7 (E7d) & E8.12/E9.2 — ASAL PERMINTAAN menempel di transaksinya.
        # Tanpa kolom ini, pertanyaan "transaksi antar-PT ini untuk pesanan siapa?"
        # hanya bisa dijawab dari catatan bebas — dan papan pending SO tidak bisa
        # menampilkan janji barang dari PT lain.
        "source_request_id": (payload.get("source_request_id") or "").strip(),
        "source_request_number": (payload.get("source_request_number") or "").strip(),
        "source_order_id": (payload.get("source_order_id") or "").strip(),
        "source_order_number": (payload.get("source_order_number") or "").strip(),
        "doc_date": doc_date,
        "due_date": due_date,
        "notes": (payload.get("notes") or "").strip(),
        "status": status,
        "confirmed_at": submit_ts,
        "confirmed_by": actor if submit_now else "",
        "settled_amount": 0.0,          # akumulasi settlement
        "created_at": ts,
        "created_by": actor,
        "updated_at": ts,
        "updated_by": actor,
    }
    seller_doc = {
        **common,
        "id": seller_id,
        "number": number_s,
        "role": "seller",
        "entity_id": seller,  # scope
        "counterpart_id": buyer_id,
    }
    buyer_doc = {
        **common,
        "id": buyer_id,
        "number": number_b,
        "role": "buyer",
        "entity_id": buyer,
        "counterpart_id": seller_id,
    }
    seller_doc["counterpart_number"] = number_b
    buyer_doc["counterpart_number"] = number_s

    from services import line_scope as _lines            # FASE L
    await _lines.stamp_doc(db, seller_doc)
    await _lines.stamp_doc(db, buyer_doc)
    if submit_now:
        # PK-06 (IC-01) — akun & periode KEDUA PT diperiksa sebelum dokumen lahir; gagal → tidak ada yang tersimpan.
        from services import twin_journal as _twin
        if float(totals["total"]) > EPS:
            await _twin.preflight_twin(source_type="interco_transaction", base_id=pair_id, date=now_iso(),
                                       sides=_confirm_sides(seller_doc, buyer_doc))
            seller_doc["gl_status"] = buyer_doc["gl_status"] = "pending"
        else:
            seller_doc["gl_status"] = buyer_doc["gl_status"] = "not_required"
    await db[COLL_ICT].insert_many([seller_doc, buyer_doc])
    await _link_refs(pair_id)
    if terms_override:
        from dependencies import audit as _audit
        await _audit(actor or terms_override["by"], "interco_terms_overridden", "interco_transaction", pair_id,
                     {"numbers": [number_s, number_b], **terms_override}, reason=terms_override["reason"],
                     scope_entity_id=seller)

    gl_res: Dict[str, Any] = {}
    if submit_now:
        # Auto-post GL saat confirmed (US2/US3) — per sisi, tahan-gagal (PK-06)
        gl_res = await repost_gl(pair_id, actor)
        await _update_account_balance(seller, buyer)
        # US7/INV-IC-03 — margin antar-PT langsung dieliminasi di laporan grup.
        await _sync_group_elimination(pair_id)

    out = await get_by_pair(pair_id)
    if submit_now:
        out["gl"] = gl_res
        out["warning"] = await _gl_warning(gl_res, pair_id)
    return out


async def get_by_pair(pair_id: str) -> Optional[Dict[str, Any]]:
    docs = await db[COLL_ICT].find({"pair_id": pair_id}, {"_id": 0}).to_list(2)
    if not docs:
        return None
    seller = next((d for d in docs if d.get("role") == "seller"), docs[0])
    buyer = next((d for d in docs if d.get("role") == "buyer"), docs[-1] if len(docs) > 1 else None)
    return {"pair_id": pair_id, "seller": safe_doc(seller),
            "buyer": safe_doc(buyer) if buyer else None}


async def get_one(interco_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        return None
    pair = await get_by_pair(doc["pair_id"])
    return pair


async def list_transactions(scope_entity_ids: List[str], entity_id: str = "",
                            status: str = "", role: str = "",
                            limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"entity_id": {"$in": scope_entity_ids} if scope_entity_ids else None}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    if status:
        q["status"] = status
    if role in ("seller", "buyer"):
        q["role"] = role
    if q.get("entity_id") is None:
        q.pop("entity_id")
    rows = await db[COLL_ICT].find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [safe_doc(r) for r in rows]


# ── Aksi siklus ──────────────────────────────────────────────────────────────
async def _pair_docs(pair_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    docs = await db[COLL_ICT].find({"pair_id": pair_id}, {"_id": 0}).to_list(2)
    if len(docs) != 2:
        raise IntercoError("Pasangan dokumen tidak lengkap.")
    seller = next(d for d in docs if d.get("role") == "seller")
    buyer = next(d for d in docs if d.get("role") == "buyer")
    return seller, buyer


async def _set_pair_status(pair_id: str, status: str, actor: str,
                           extra: Optional[Dict[str, Any]] = None) -> None:
    upd = {"status": status, "updated_at": now_iso(), "updated_by": actor}
    if extra:
        upd.update(extra)
    await db[COLL_ICT].update_many({"pair_id": pair_id}, {"$set": upd})


async def confirm(interco_id: str, actor_user: Dict[str, Any]) -> Dict[str, Any]:
    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Transaksi tidak ditemukan.")
    if doc["status"] != "draft":
        raise IntercoError(f"Hanya draf yang bisa dikonfirmasi (status sekarang: {STATUS_LABEL.get(doc['status'], doc['status'])}).")

    grand = float(doc.get("grand_total") or 0)
    await _assert_may_release(actor_user, grand, doc["seller_entity_id"])

    # PK-06 (IC-01) — PERIKSA jurnal kedua PT dulu (tanpa tulisan), baru status berubah.
    from services import atomic_claim as _saga
    from services import twin_journal as _twin
    pair_id = doc["pair_id"]
    seller, buyer = await _pair_docs(pair_id)
    name = actor_user.get("name", "")
    if grand > EPS:
        await _twin.preflight_twin(source_type="interco_transaction", base_id=pair_id, date=now_iso(),
                                   sides=_confirm_sides(seller, buyer))
    claimed = await _saga.claim(COLL_ICT, seller["id"], "interco_confirm", precondition={"status": "draft"},
                                actor=name)
    token = claimed[_saga.LOCK]["token"]
    await _set_pair_status(pair_id, "confirmed", name,
                           {"confirmed_at": now_iso(), "confirmed_by": name,
                            "gl_status": "pending" if grand > EPS else "not_required"})
    gl_res = await repost_gl(pair_id, name) if grand > EPS else {}
    await _saga.release(COLL_ICT, seller["id"], token)
    await _update_account_balance(doc["seller_entity_id"], doc["buyer_entity_id"])
    await _sync_group_elimination(pair_id)
    out = await get_by_pair(pair_id)
    out["gl"] = gl_res
    out["warning"] = await _gl_warning(gl_res, pair_id)
    return out


async def ship(interco_id: str, actor: str) -> Dict[str, Any]:
    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Transaksi tidak ditemukan.")
    if doc["status"] != "confirmed":
        raise IntercoError("Hanya transaksi terkonfirmasi yang bisa dikirim.")
    await _set_pair_status(doc["pair_id"], "shipped", actor,
                           {"shipped_at": now_iso(), "shipped_by": actor})
    return await get_by_pair(doc["pair_id"])


async def receive(interco_id: str, actor: str) -> Dict[str, Any]:
    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Transaksi tidak ditemukan.")
    if doc["status"] not in ("confirmed", "shipped"):
        raise IntercoError(
            "Transaksi harus dikonfirmasi lebih dulu sebelum barangnya bisa diterima "
            f"(status sekarang: {STATUS_LABEL.get(doc['status'], doc['status'])}).")
    # Penerimaan MENGGERAKKAN persediaan pembeli (transit → persediaan). Karena itu
    # ia hanya sah bila barangnya benar-benar berpindah lewat tugas gudang — kalau
    # tidak, GL persediaan naik untuk barang yang tidak ada di gudang mana pun.
    task = await db.warehouse_transfers.find_one(
        {"interco_pair_id": doc["pair_id"], "status": "completed"},
        {"_id": 0, "code": 1})
    if not task:
        raise IntercoError(
            "Barangnya belum berpindah di gudang. Terbitkan **Tugas Gudang** dan minta "
            "gudang menyetujuinya — status 'Diterima' akan tercatat otomatis beserta "
            "jurnal penerimaan (persediaan pembeli naik saat barangnya benar-benar ada).")
    await _set_pair_status(doc["pair_id"], "received", actor,
                           {"received_at": now_iso(), "received_by": actor})
    await post_gl_on_delivery(doc["pair_id"], actor)
    await _sync_group_elimination(doc["pair_id"])
    return await get_by_pair(doc["pair_id"])


async def invoice(interco_id: str, actor: str) -> Dict[str, Any]:
    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Transaksi tidak ditemukan.")
    if doc["status"] not in ("received", "shipped"):
        raise IntercoError("Faktur internal hanya bisa diterbitkan setelah barang dikirim/diterima.")
    await _set_pair_status(doc["pair_id"], "invoiced", actor,
                           {"invoiced_at": now_iso(), "invoiced_by": actor})
    return await get_by_pair(doc["pair_id"])


async def cancel(interco_id: str, actor: str, reason: str = "") -> Dict[str, Any]:
    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Transaksi tidak ditemukan.")
    if doc["status"] in ("settled",):
        raise IntercoError("Transaksi yang sudah lunas tidak bisa dibatalkan.")
    if doc["status"] in ("shipped", "received", "invoiced"):
        raise IntercoError("Transaksi yang sudah dikirim tidak bisa dibatalkan begitu saja — buat retur.")
    if doc["status"] == "cancelled":
        raise IntercoError("Transaksi ini sudah dibatalkan.")
    reason = (reason or "").strip()
    was_posted = doc["status"] == "confirmed"
    if was_posted and len(reason) < 5:
        # G-1 — koreksi WAJIB ber-alasan: jurnal yang sudah terbit hanya boleh
        # dibalik dengan sebab yang tercatat, bukan dihapus senyap.
        raise IntercoError(
            "Transaksi yang sudah dikonfirmasi hanya bisa dibatalkan dengan ALASAN "
            "(minimal 5 huruf) karena jurnalnya akan dibalik di kedua buku.")
    tugas = await db.warehouse_transfers.find_one(
        {"interco_pair_id": doc["pair_id"],
         "status": {"$nin": ["rejected", "cancelled"]}},
        {"_id": 0, "code": 1, "status": 1})
    if tugas and tugas.get("status") == "completed":
        raise IntercoError(
            f"Barangnya sudah berpindah lewat tugas gudang {tugas.get('code')} — "
            f"batalkan lewat retur, bukan pembatalan dokumen.")

    await _set_pair_status(doc["pair_id"], "cancelled", actor,
                           {"cancelled_at": now_iso(), "cancelled_by": actor,
                            "cancel_reason": reason})
    reversed_count = 0
    if was_posted:
        reversed_count = await _reverse_gl_for_pair(doc["pair_id"], actor, reason)
    if tugas:
        # Tugas gudang yang masih menunggu persetujuan wajib ikut batal supaya
        # roll penjual tidak terkunci selamanya.
        try:
            from services.roll_service import release_transfer_rolls
            await db.warehouse_transfers.update_one(
                {"interco_pair_id": doc["pair_id"], "status": "waiting_approval"},
                {"$set": {"status": "cancelled", "updated_at": now_iso(),
                          "rejected_reason": f"Transaksi antar-PT dibatalkan: {reason}"}})
            tr = await db.warehouse_transfers.find_one(
                {"interco_pair_id": doc["pair_id"], "status": "cancelled"}, {"_id": 0, "id": 1})
            if tr:
                await release_transfer_rolls(tr["id"])
                # Layar harus jujur: tugasnya sudah batal, bukan "menunggu gudang".
                await db[COLL_ICT].update_many(
                    {"pair_id": doc["pair_id"]},
                    {"$set": {"warehouse_transfer_status": "cancelled",
                              "updated_at": now_iso()}})
        except Exception as exc:  # noqa: BLE001
            print(f"[interco] gagal membatalkan tugas gudang: {exc}")
    await _update_account_balance(doc["seller_entity_id"], doc["buyer_entity_id"])
    await _sync_group_elimination(doc["pair_id"])
    res = await get_by_pair(doc["pair_id"])
    res["reversed_journals"] = reversed_count
    return res


# ═══════════════════════════════════════════════════════════════════════════
# GL POSTING (INV-IC-01, INV-IC-05)
# ═══════════════════════════════════════════════════════════════════════════
def _confirm_sides(seller: Dict[str, Any], buyer: Dict[str, Any]) -> List[Any]:
    """Rencana jurnal KONFIRMASI dengan HARGA JUAL (bukan sekadar at-cost). Baris tidak berubah dari kode lama.

    Buku PENJUAL:  Dr 1-1250 IC-AR = grand_total · Cr 4-1000 Pendapatan = subtotal · Cr 2-1200 PPN Keluaran = PPN
    Buku PEMBELI:  Dr 1-1310 Persediaan Dalam Perjalanan = subtotal · Dr 1-1500 PPN Masukan = PPN · Cr 2-1250 IC-AP

    **HPP penjual & masuknya persediaan pembeli TIDAK diposting di sini** — itu mengikuti BARANGNYA
    (`post_gl_on_delivery`, saat tugas gudang selesai).
    """
    from services.twin_journal import TwinSide
    pair_id = seller["pair_id"]
    subtotal = float(seller.get("subtotal") or 0)
    tax_amt = float(seller.get("tax_amount") or 0)
    grand = float(seller.get("grand_total") or 0)
    code = seller.get("number") or pair_id
    ent_s, ent_b = seller["seller_entity_id"], seller["buyer_entity_id"]
    lines_s: List[Dict[str, Any]] = [
        {"account_code": gl_service.ACC_IC_AR, "debit": grand, "credit": 0.0,
         "description": f"Piutang antar-PT {code} → {buyer.get('buyer_entity_name', ent_b)}"},
        {"account_code": gl_service.ACC_PENDAPATAN, "debit": 0.0, "credit": subtotal,
         "description": f"Pendapatan antar-PT {code}"},
    ]
    if tax_amt > EPS:
        lines_s.append({"account_code": gl_service.ACC_PPN_OUT, "debit": 0.0, "credit": tax_amt,
                        "description": f"PPN Keluaran antar-PT {code}"})
    lines_b: List[Dict[str, Any]] = [
        {"account_code": gl_service.ACC_PERSEDIAAN_TRANSIT, "debit": subtotal, "credit": 0.0,
         "description": (f"Barang antar-PT dalam perjalanan {buyer.get('number', '')} "
                         f"← {seller.get('seller_entity_name', ent_s)}")},
    ]
    if tax_amt > EPS:
        lines_b.append({"account_code": gl_service.ACC_PPN_IN, "debit": tax_amt, "credit": 0.0,
                        "description": f"PPN Masukan antar-PT {code}"})
    lines_b.append({"account_code": gl_service.ACC_IC_AP, "debit": 0.0, "credit": grand,
                    "description": f"Utang antar-PT {buyer.get('number', '')}"})
    return [
        TwinSide("seller", ent_s, lines_s, f"Penjualan antar-PT {code}", code, (COLL_ICT, seller["id"])),
        TwinSide("buyer", ent_b, lines_b, f"Pembelian antar-PT {buyer.get('number', '')}",
                 buyer.get("number", code), (COLL_ICT, buyer["id"])),
    ]


async def repost_gl(pair_id: str, actor: str = "") -> Dict[str, Dict[str, str]]:
    """PK-06 — terbitkan jurnal konfirmasi yang KURANG (per sisi, idempoten). Dipakai konfirmasi & panel Posting Gagal."""
    from services import twin_journal as _twin
    seller, buyer = await _pair_docs(pair_id)
    if float(seller.get("grand_total") or 0) <= EPS:
        await db[COLL_ICT].update_many({"pair_id": pair_id}, {"$set": {"gl_status": "not_required"}})
        return {}
    date = seller.get("confirmed_at") or seller.get("created_at") or now_iso()
    return await _twin.post_twin(source_type="interco_transaction", base_id=pair_id, date=date,
                                 sides=_confirm_sides(seller, buyer), created_by=actor or "system")


async def _gl_warning(gl_res: Dict[str, Dict[str, str]], pair_id: str) -> str:
    from services import twin_journal as _twin
    if not gl_res:
        return ""
    seller, buyer = await _pair_docs(pair_id)
    return await _twin.warning_for(gl_res, _confirm_sides(seller, buyer))


async def _post_gl_for_pair(pair_id: str, actor: str) -> None:
    """Pemanggil lama → `repost_gl` (PK-06: per sisi, tanpa penjaga "penjual ATAU pembeli")."""
    await repost_gl(pair_id, actor)


async def post_gl_on_delivery(pair_id: str, actor: str,
                              cost_override: Optional[float] = None) -> Dict[str, Any]:
    """Jurnal yang MENGIKUTI BARANG — diposting saat perpindahan fisik selesai.

    Buku PENJUAL (barang keluar):
      Dr 5-1000 HPP            = HPP (WAC) barang yang keluar
        Cr 1-1300 Persediaan     = HPP

    Buku PEMBELI (barang masuk):
      Dr 1-1300 Persediaan     = harga beli internal (nilai roll yang dinilai ulang)
        Cr 1-1310 Persediaan Dalam Perjalanan = nilai yang sama

    Dengan pemisahan ini, GL 1-1300 kedua PT **selalu** sejalan dengan subledger roll
    (INV-GL-DRIFT bersih), dan "barang sudah dibeli tapi belum datang" punya tempat
    sendiri yang jujur di neraca pembeli.

    Idempotent via source_id `{pair}:cogs` (penjual) & `{pair}:receipt` (pembeli).
    """
    seller, buyer = await _pair_docs(pair_id)
    out: Dict[str, Any] = {"cogs": 0.0, "receipt": 0.0}
    code = seller.get("number") or pair_id
    date = now_iso()
    ent_s = seller["seller_entity_id"]
    ent_b = seller["buyer_entity_id"]

    # ── HPP penjual: biaya NYATA roll yang keluar (specific identification).
    # Memakai WAC × qty membuat GL 1-1300 penjual selalu selisih tipis dari subledger
    # (roll punya harga perolehan masing-masing). Karena tugas gudang tahu roll mana
    # yang berpindah, biayanya dihitung dari roll itu; WAC hanya cadangan terakhir.
    if not await gl_service._already_posted("interco_transaction", f"{pair_id}:cogs"):
        if cost_override is not None and cost_override > EPS:
            total_cost = round(float(cost_override), 2)
        else:
            total_cost = 0.0
            for it in seller.get("items", []):
                wac = await wac_for_product(it["product_id"], entity_id=ent_s, use_cache=False)
                total_cost += float(it["quantity"]) * float(wac.get("wac") or 0)
        total_cost = round(total_cost, 2)
        if total_cost > EPS:
            lines_c = gl_service._balanced_pair(
                gl_service.ACC_HPP, gl_service.ACC_PERSEDIAAN, total_cost,
                f"HPP antar-PT {code} (barang keluar gudang)")
            await gl_service._insert_entry(
                lines=lines_c, description=f"HPP antar-PT {code}",
                date=date, source_type="interco_transaction",
                source_id=f"{pair_id}:cogs", entity_id=ent_s,
                created_by=actor or "system", source_label=code,
            )
            out["cogs"] = total_cost

    # ── Penerimaan pembeli: transit → persediaan
    if not await gl_service._already_posted("interco_transaction", f"{pair_id}:receipt"):
        subtotal = round(float(seller.get("subtotal") or 0), 2)
        if subtotal > EPS:
            lines_r = gl_service._balanced_pair(
                gl_service.ACC_PERSEDIAAN, gl_service.ACC_PERSEDIAAN_TRANSIT, subtotal,
                f"Penerimaan barang antar-PT {buyer.get('number', '')} (harga beli internal)")
            await gl_service._insert_entry(
                lines=lines_r,
                description=f"Penerimaan barang antar-PT {buyer.get('number', '')}",
                date=date, source_type="interco_transaction",
                source_id=f"{pair_id}:receipt", entity_id=ent_b,
                created_by=actor or "system", source_label=buyer.get("number", code),
            )
            out["receipt"] = subtotal
    return out


# ═══════════════════════════════════════════════════════════════════════════
# SALDO ANTAR-PT (interco_accounts) — INV-IC-04
# ═══════════════════════════════════════════════════════════════════════════
def ica_ar_id(seller_entity_id: str, buyer_entity_id: str) -> str:
    """Id baris PIUTANG milik PT penjual untuk arah dagang penjual→pembeli."""
    return f"ica_{seller_entity_id}_{buyer_entity_id}_ar"


def ica_ap_id(buyer_entity_id: str, seller_entity_id: str) -> str:
    """Id baris UTANG milik PT pembeli untuk arah dagang penjual→pembeli."""
    return f"ica_{buyer_entity_id}_{seller_entity_id}_ap"


def ica_pair_key(seller_entity_id: str, buyer_entity_id: str) -> str:
    """Kunci ARAH DAGANG (penjual>pembeli) — penjodoh piutang↔utang (INV-IC-02)."""
    return f"{seller_entity_id}>{buyer_entity_id}"


async def _update_account_balance(seller_entity_id: str, buyer_entity_id: str) -> None:
    """Recompute saldo pasangan PT dari transaksi terbuka & settlement.

    Untuk ARAH DAGANG (seller→buyer) ada dua baris — satu per sudut pandang buku:
      * `ica_{seller}_{buyer}_ar` — piutang (receivable) di buku PT penjual.
      * `ica_{buyer}_{seller}_ap` — utang (payable) di buku PT pembeli.
    INV-IC-02: dua baris ini harus sama besar.

    KN-G6-ICA-CLOBBER (ditutup di sesi ini) — dulu id-nya `ica_{X}_{Y}` TANPA
    penanda peran, sehingga **piutang arah A→B dan utang arah B→A menempati SATU
    dokumen yang sama**. Begitu pasangan PT yang sama berdagang DUA ARAH — hal
    yang normal terjadi lewat Permintaan Internal ("stok saya habis, kirim dari
    PT sebelah") — recompute arah kedua MENIMPA saldo arah pertama dan utang yang
    nyata **hilang dari layar tanpa satu pun pesan**. Terukur pada data demo:
    utang CV Kanda Suka ke KSC Rp 1.766.010 menjadi Rp 0 hanya karena Kanda
    menerbitkan transaksi arah balik. Sejak sekarang identitas baris memuat arah
    dagang DAN peran, jadi dua arah hidup berdampingan.
    """
    docs = await db[COLL_ICT].find({
        "seller_entity_id": seller_entity_id,
        "buyer_entity_id": buyer_entity_id,
        "role": "seller",
        "status": {"$in": list(OPEN_STATUSES) + ["settled"]},
    }, {"_id": 0}).to_list(1000)
    open_docs = [d for d in docs if d.get("status") in OPEN_STATUSES]
    gross = sum(float(d.get("grand_total") or 0) for d in open_docs)
    settled = sum(float(d.get("settled_amount") or 0) for d in open_docs)
    # FASE G-6b — barang yang DIRETUR mengurangi utang antar-PT persis seperti
    # pelunasan (nilai dokumen sendiri TIDAK pernah diedit — append-only).
    returned = sum(float(d.get("returned_amount") or 0) for d in open_docs)
    outstanding = round(gross - settled - returned, 2)
    seller_snap = await _entity_snapshot(seller_entity_id)
    buyer_snap = await _entity_snapshot(buyer_entity_id)
    ts = now_iso()
    # Umur saldo dihitung dari AKTIVITAS NYATA (dokumen & settlement), bukan dari
    # `updated_at` baris ini — lihat KN-G6-IDLE-FAKE di memory/BUG_REGISTRY.md.
    try:
        from services import interco_reminder as _rem
        activity = await _rem.last_activity_at(seller_entity_id, buyer_entity_id)
    except Exception as exc:  # noqa: BLE001 — hanya penanda umur, bukan uang
        print(f"[interco] hitung aktivitas terakhir gagal: {exc}")
        activity = ""
    # Sisi penjual = piutang (receivable)
    ica_ar = ica_ar_id(seller_entity_id, buyer_entity_id)
    pair_key = ica_pair_key(seller_entity_id, buyer_entity_id)
    await db[COLL_ICA].update_one(
        {"id": ica_ar},
        {"$set": {
            "id": ica_ar,
            # Scope PT pemilik baris ini (F0-C: setiap koleksi ber-`entity_id`
            # ikut aturan isolasi lintas-PT; tanpa ini baris saldo tak bisa
            # ditapis per buku dan gate scoping memerah).
            "entity_id": seller_entity_id,
            "from_entity_id": seller_entity_id,
            "from_entity_name": seller_snap["name"],
            "to_entity_id": buyer_entity_id,
            "to_entity_name": buyer_snap["name"],
            # Arah dagang disimpan EKSPLISIT — layar & invarian tidak perlu
            # menyimpulkannya dari peran (sumber KN-G6-ICA-CLOBBER dulu).
            "pair_key": pair_key,
            "seller_entity_id": seller_entity_id,
            "seller_entity_name": seller_snap["name"],
            "buyer_entity_id": buyer_entity_id,
            "buyer_entity_name": buyer_snap["name"],
            "role": "receivable",
            "open_count": len(open_docs),
            "gross_amount": round(gross, 2),
            "settled_amount": round(settled, 2),
            "returned_amount": round(returned, 2),
            "outstanding": outstanding,
            "last_activity_at": activity,
            "updated_at": ts,
        }}, upsert=True,
    )
    # Sisi pembeli = utang (payable) — cerminan angka yang sama, arah terbalik.
    ica_ap = ica_ap_id(buyer_entity_id, seller_entity_id)
    await db[COLL_ICA].update_one(
        {"id": ica_ap},
        {"$set": {
            "id": ica_ap,
            "entity_id": buyer_entity_id,
            "from_entity_id": buyer_entity_id,
            "from_entity_name": buyer_snap["name"],
            "to_entity_id": seller_entity_id,
            "to_entity_name": seller_snap["name"],
            "pair_key": pair_key,
            "seller_entity_id": seller_entity_id,
            "seller_entity_name": seller_snap["name"],
            "buyer_entity_id": buyer_entity_id,
            "buyer_entity_name": buyer_snap["name"],
            "role": "payable",
            "open_count": len(open_docs),
            "gross_amount": round(gross, 2),
            "settled_amount": round(settled, 2),
            "returned_amount": round(returned, 2),
            "outstanding": outstanding,
            "last_activity_at": activity,
            "updated_at": ts,
        }}, upsert=True,
    )
    # Baris warisan tanpa penanda peran (skema sebelum KN-G6-ICA-CLOBBER ditutup)
    # dibuang begitu arahnya dihitung ulang, supaya layar tidak menampilkan angka
    # kembar yang sudah tidak dipelihara siapa pun.
    await db[COLL_ICA].delete_many({"id": {"$in": [
        f"ica_{seller_entity_id}_{buyer_entity_id}",
        f"ica_{buyer_entity_id}_{seller_entity_id}",
    ]}})


async def _live_pair_outstanding() -> Dict[Any, Dict[str, Any]]:
    """Σ dokumen TERBUKA per arah dagang (penjual, pembeli) — rumus sama dengan `_update_account_balance`."""
    out: Dict[Any, Dict[str, Any]] = {}
    async for d in db[COLL_ICT].find({"role": "seller", "status": {"$in": list(OPEN_STATUSES)}},
                                     {"_id": 0, "seller_entity_id": 1, "buyer_entity_id": 1, "grand_total": 1,
                                      "settled_amount": 1, "returned_amount": 1}):
        k = (d.get("seller_entity_id"), d.get("buyer_entity_id"))
        a = out.setdefault(k, {"open_count": 0, "gross_amount": 0.0, "settled_amount": 0.0,
                               "returned_amount": 0.0, "outstanding": 0.0})
        a["open_count"] += 1
        a["gross_amount"] = round(a["gross_amount"] + float(d.get("grand_total") or 0), 2)
        a["settled_amount"] = round(a["settled_amount"] + float(d.get("settled_amount") or 0), 2)
        a["returned_amount"] = round(a["returned_amount"] + float(d.get("returned_amount") or 0), 2)
        a["outstanding"] = round(a["gross_amount"] - a["settled_amount"] - a["returned_amount"], 2)
    return out


async def list_accounts(scope_entity_ids: List[str]) -> List[Dict[str, Any]]:
    """Saldo antar-PT untuk semua pasangan yang menyentuh scope."""
    if not scope_entity_ids:
        return []
    q = {"$or": [{"from_entity_id": {"$in": scope_entity_ids}},
                 {"to_entity_id": {"$in": scope_entity_ids}}]}
    rows = await db[COLL_ICA].find(q, {"_id": 0}).sort("outstanding", -1).to_list(1000)
    # UAT 24 Okt (audit UI tahap 2) — G1-31: baris saldo adalah CACHE yang dihitung ulang hanya saat dokumen
    # berubah lewat layanan ini. Di data acuan cache KSC→CST tertinggal (Rp 7.015.200, 2 dokumen) padahal dokumen
    # terbuka saat ini 1 (Rp 6.993.000 — angka yang sama dengan Jadwal Bayar). Angka yang DITAMPILKAN kini dibaca
    # langsung dari dokumen terbuka dengan rumus yang sama (`_update_account_balance`); cache tidak ditulis di GET.
    live = await _live_pair_outstanding()
    for r in rows:
        k = (r.get("seller_entity_id"), r.get("buyer_entity_id"))
        if not all(k):
            continue
        cur = live.get(k, {"open_count": 0, "gross_amount": 0.0, "settled_amount": 0.0,
                           "returned_amount": 0.0, "outstanding": 0.0})
        if abs(float(r.get("outstanding") or 0) - cur["outstanding"]) > EPS \
                or int(r.get("open_count") or 0) != cur["open_count"]:
            r["cached_outstanding"] = r.get("outstanding")
            r.update(cur)
    rows.sort(key=lambda r: -float(r.get("outstanding") or 0))
    reminder_days = int(await _config("antar_entitas.settlement_reminder_days") or 30)
    today = datetime.now(timezone.utc)
    for r in rows:
        # Umur = sejak AKTIVITAS NYATA terakhir (dokumen/settlement). `updated_at`
        # hanya cadangan untuk baris lama yang belum punya `last_activity_at`.
        upd = r.get("last_activity_at") or r.get("updated_at") or ""
        aging = 0
        if upd:
            try:
                raw = str(upd)
                if len(raw) == 10:
                    raw = f"{raw}T00:00:00+00:00"
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                aging = max(0, (today - dt).days)
            except Exception:
                aging = 0
        r["aging_days"] = aging
        r["reminder_limit_days"] = reminder_days
        r["reminder_active"] = (r.get("outstanding", 0) > EPS and aging >= reminder_days)
    return [safe_doc(r) for r in rows]


async def get_account(from_entity_id: str, to_entity_id: str,
                      role: str = "payable") -> Dict[str, Any]:
    """Satu baris saldo dari sudut pandang `from_entity_id` terhadap `to_entity_id`.

    `role="payable"` (bawaan) menjawab **"berapa utang `from` kepada `to`?"** —
    itu pertanyaan yang dipakai tombol Ingatkan & Buat Settlement. `role="receivable"`
    menjawab kebalikannya (piutang `from` atas `to`). Peran WAJIB ikut karena satu
    pasangan PT bisa berdagang dua arah sekaligus; tanpa peran, jawabannya ambigu
    (akar KN-G6-ICA-CLOBBER).
    """
    role = (role or "payable").strip().lower()
    if role not in ("payable", "receivable"):
        raise IntercoError("Peran saldo antar-PT hanya 'payable' atau 'receivable'.")
    suffix = "ap" if role == "payable" else "ar"
    ica_id = f"ica_{from_entity_id}_{to_entity_id}_{suffix}"
    row = await db[COLL_ICA].find_one({"id": ica_id}, {"_id": 0})
    if not row:
        # Basis data yang belum dimigrasikan masih memakai id tanpa penanda peran.
        row = await db[COLL_ICA].find_one(
            {"id": f"ica_{from_entity_id}_{to_entity_id}", "role": role}, {"_id": 0})
    if not row:
        return {"id": ica_id, "from_entity_id": from_entity_id,
                "to_entity_id": to_entity_id, "role": role,
                "outstanding": 0.0, "open_count": 0}
    return safe_doc(row)


# ═══════════════════════════════════════════════════════════════════════════
# SETTLEMENT / NETTING (US6, pola kontrabon G-7)
# ═══════════════════════════════════════════════════════════════════════════
async def create_settlement(payload: Dict[str, Any], actor: str = "", idempotency_key: str = "") -> Dict[str, Any]:
    """PK-06 (IC-08) — pelunasan antar-PT: PERIKSA (validasi, rekening kedua PT, jurnal kedua buku) → NIAT (settlement
    `pending`, id tetap dari kunci) → EFEK 1 (sisa tiap dokumen, CAS + `settlement_ids`) → EFEK 2 (kas kembar) →
    JURNAL per sisi (tahan-gagal) → SELESAI. Kunci sama → hasil yang sama; diulang dari langkah yang belum tuntas."""
    payer = (payload.get("payer_entity_id") or "").strip()
    payee = (payload.get("payee_entity_id") or "").strip()
    if not payer or not payee or payer == payee:
        raise IntercoError("Pilih PT pembayar dan PT penerima yang berbeda.")
    settle_id = new_id("ics")
    if idempotency_key:
        import hashlib
        settle_id = "ics_" + hashlib.sha256(f"{payer}|{idempotency_key}".encode()).hexdigest()[:24]
        existing = await db[COLL_ICS].find_one({"id": settle_id}, {"_id": 0})
        if existing:
            if existing.get("status") == "posted":
                return safe_doc(existing)
            if existing.get("status") == "cancelled":
                raise IntercoConflict("Pelunasan dengan kunci ini sudah dibatalkan. Muat ulang lalu ulangi.")
            return await _run_settlement(existing, actor)
    picks = payload.get("transactions") or []
    if not picks:
        raise IntercoError("Minimal satu transaksi harus dipilih untuk settlement.")

    pay_cfg = await payment_settings(payer)
    method_req = (payload.get("method") or "transfer").strip().lower()
    if method_req == "netting" and not pay_cfg["allow_netting"]:
        raise IntercoError("Netting dinonaktifkan: pembayaran antar-PT dilakukan penuh per transaksi tanpa saling "
                           "hapus (LN-024). Pilih metode transfer/kas.")
    total_applied = 0.0
    applied_rows: List[Dict[str, Any]] = []
    for p in picks:
        ict_id = (p.get("interco_id") or "").strip()
        seller_doc = await db[COLL_ICT].find_one({"id": ict_id, "role": "seller"}, {"_id": 0})
        if not seller_doc:
            raise IntercoError(f"Transaksi {ict_id} tidak ditemukan.")
        if seller_doc["seller_entity_id"] != payee or seller_doc["buyer_entity_id"] != payer:
            raise IntercoError(
                f"Transaksi {seller_doc.get('number')} bukan milik pasangan PT ini "
                f"(butuh penjual={payee}, pembeli={payer}).")
        counterpart = await db[COLL_ICT].find_one({"id": seller_doc.get("counterpart_id")}, {"_id": 0, "gl_status": 1})
        if seller_doc.get("gl_status") == "failed" or (counterpart or {}).get("gl_status") == "failed":
            raise IntercoConflict(f"Transaksi {seller_doc.get('number')} masih punya jurnal yang gagal terbit. "
                                  "Ulangi dulu dari Keuangan › Posting Gagal.")
        if seller_doc["status"] not in OPEN_STATUSES:
            raise IntercoError(
                f"Transaksi {seller_doc.get('number')} berstatus "
                f"{STATUS_LABEL.get(seller_doc['status'], seller_doc['status'])}, "
                f"tidak bisa dilunaskan lagi.")
        remaining = round(float(seller_doc.get("grand_total") or 0) -
                          float(seller_doc.get("settled_amount") or 0) -
                          float(seller_doc.get("returned_amount") or 0), 2)
        if remaining <= EPS:
            raise IntercoError(
                f"Transaksi {seller_doc.get('number')} sudah lunas "
                f"(atau seluruh nilainya sudah diretur).")
        req = p.get("applied_amount")
        applied = float(req) if req not in (None, "", 0) else remaining
        if applied > remaining + EPS:
            raise IntercoError(
                f"Nilai yang diterapkan {rupiah(applied)} melebihi sisa transaksi "
                f"{seller_doc.get('number')} ({rupiah(remaining)}).")
        if pay_cfg["require_full_payment"] and applied < remaining - EPS:
            raise IntercoError(
                f"Transaksi {seller_doc.get('number')} harus dibayar penuh ({rupiah(remaining)}); "
                "pembayaran sebagian antar-PT tidak diizinkan (LN-024).")
        applied = round(applied, 2)
        total_applied += applied
        applied_rows.append({
            "interco_id": ict_id,
            "counterpart_id": seller_doc.get("counterpart_id"),
            "pair_id": seller_doc.get("pair_id"),
            "number": seller_doc.get("number"),
            "counterpart_number": seller_doc.get("counterpart_number"),
            "grand_total": float(seller_doc.get("grand_total") or 0),
            "previous_settled": float(seller_doc.get("settled_amount") or 0),
            "previous_status": seller_doc.get("status", ""),
            "applied_amount": applied,
            "applied_at": None,
        })

    total_applied = round(total_applied, 2)
    if total_applied <= EPS:
        raise IntercoError("Total settlement harus > 0.")

    settle_date = payload.get("settle_date") or _today()
    method = (payload.get("method") or "transfer").strip().lower()
    # F-08 (audit 2026-09-02) — netting hanya sah bila PEMBAYAR juga punya PIUTANG ke
    # penerima (arah balik). Tanpa itu IC-AP bersaldo debit & IC-AR bersaldo kredit.
    if method == "netting":
        reverse_open = await db[COLL_ICT].find({
            "seller_entity_id": payer, "buyer_entity_id": payee, "role": "seller",
            "status": {"$in": list(OPEN_STATUSES)}}, {"_id": 0}).sort("created_at", 1).to_list(1000)
        ar_reverse = round(sum(
            float(d.get("grand_total") or 0) - float(d.get("settled_amount") or 0)
            - float(d.get("returned_amount") or 0) for d in reverse_open), 2)
        if total_applied > ar_reverse + EPS:
            raise IntercoError(
                f"Netting {rupiah(total_applied)} melebihi piutang balik {payer}→{payee} "
                f"yang terbuka ({rupiah(ar_reverse)}). Pilih metode transfer/kas, atau "
                f"batasi netting sebesar piutang balik.")
    else:
        reverse_open = []
    payer_snap = await _entity_snapshot(payer)
    payee_snap = await _entity_snapshot(payee)
    # F-08 (residual) — netting MENGKONSUMSI piutang balik FIFO, supaya dua netting berturut
    # tidak bisa melampaui piutang balik secara kumulatif & sub-ledger selaras dengan GL.
    netted_against: List[Dict[str, Any]] = []
    if method == "netting":
        remaining = total_applied
        for rd in reverse_open:
            if remaining <= EPS:
                break
            outstanding = round(float(rd.get("grand_total") or 0) - float(rd.get("settled_amount") or 0)
                                - float(rd.get("returned_amount") or 0), 2)
            take = round(min(remaining, outstanding), 2)
            if take <= EPS:
                continue
            netted_against.append({"interco_id": rd["id"], "pair_id": rd.get("pair_id"),
                                   "number": rd.get("number"), "applied_amount": take,
                                   "previous_status": rd.get("status", ""), "applied_at": None})
            remaining = round(remaining - take, 2)

    payer_acc = payee_acc = ""
    if method != "netting":
        payer_acc = await _settle_account(payer, (payload.get("bank_account_id") or "").strip())
        payee_acc = await _settle_account(payee, "")
    doc = {
        "id": settle_id,
        "number": "",
        "entity_id": payer,      # scope: PT yang membayar
        "payer_entity_id": payer,
        "payer_entity_name": payer_snap["name"],
        "payee_entity_id": payee,
        "payee_entity_name": payee_snap["name"],
        "settle_date": settle_date,
        "method": method,
        "bank_account_id": payer_acc,
        "payer_account_id": payer_acc,
        "payee_account_id": payee_acc,
        "notes": (payload.get("notes") or "").strip(),
        "applied": applied_rows,
        "netted_against": netted_against,
        "total_applied": total_applied,
        "status": "pending",
        "gl_status": "pending",
        "idempotency_key": idempotency_key,
        "created_at": now_iso(),
        "created_by": actor,
    }
    # PERIKSA jurnal kedua buku sebelum apa pun tertulis (periode tertutup / akun nonaktif → 409).
    from services import twin_journal as _twin
    await _twin.preflight_twin(source_type="interco_settlement", base_id=settle_id, date=settle_date,
                               sides=_settlement_sides(doc))
    doc["number"] = await next_doc_number(COLL_ICS, "number", "ICS-", entity_id=payer)
    await db[COLL_ICS].insert_one(dict(doc))
    return await _run_settlement(doc, actor)


class _SettleRowRejected(Exception):
    pass


async def _settle_account(entity_id: str, account_id: str) -> str:
    """Rekening kas/bank PT itu: yang dipilih (wajib milik PT & aktif) atau rekening bawaannya."""
    from services.interco_money_service import default_cash_account
    nama = (await _entity_snapshot(entity_id))["name"]
    if account_id:
        acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "entity_id": 1, "is_active": 1})
        if not acc or acc.get("is_active") is False or acc.get("entity_id") != entity_id:
            raise IntercoError(f"Rekening itu bukan milik {nama} atau sudah nonaktif.")
        return account_id
    aid = await default_cash_account(entity_id)
    if not aid:
        raise IntercoError(f"{nama} belum punya rekening kas/bank aktif. Tambahkan di Keuangan › Kas & Bank.")
    return aid


async def _apply_settlement_rows(doc: Dict[str, Any], actor: str) -> None:
    """EFEK 1 — naikkan `settled_amount` tiap dokumen kembar SEKALI per settlement (CAS + `settlement_ids`).
    Satu baris ditolak → semua yang sudah dinaikkan settlement ini dikembalikan, lalu `_SettleRowRejected`."""
    from pymongo import ReturnDocument
    sid = doc["id"]
    groups = [("applied", r) for r in doc.get("applied", [])] + [("netted_against", r) for r in doc.get("netted_against", [])]
    amount_by_pair: Dict[str, float] = {}
    status_by_pair: Dict[str, str] = {}
    for _, r in groups:
        amount_by_pair[r["pair_id"]] = round(amount_by_pair.get(r["pair_id"], 0.0) + float(r["applied_amount"]), 2)
        status_by_pair.setdefault(r["pair_id"], r.get("previous_status") or "confirmed")
    idx = {"applied": 0, "netted_against": 0}
    for field, row in groups:
        i = idx[field]
        idx[field] += 1
        if row.get("applied_at"):
            continue
        amt = float(row["applied_amount"])
        # Urutan TETAP (id terurut): dua settlement yang berebut pasangan sama selalu bertemu di dokumen yang sama
        # lebih dulu, sehingga tepat satu yang lolos — bukan masing-masing menang di satu sisi lalu sama-sama batal.
        ids = sorted(d["id"] for d in await db[COLL_ICT].find({"pair_id": row["pair_id"]}, {"_id": 0, "id": 1}).to_list(4))
        for _id in ids:
            res = await db[COLL_ICT].find_one_and_update(
                {"id": _id, "status": {"$in": list(OPEN_STATUSES)}, "settlement_ids": {"$ne": sid},
                 "$expr": {"$lte": [{"$add": [{"$ifNull": ["$settled_amount", 0]}, {"$ifNull": ["$returned_amount", 0]},
                                              amt]}, {"$add": [{"$ifNull": ["$grand_total", 0]}, EPS]}]}},
                {"$inc": {"settled_amount": amt}, "$addToSet": {"settlement_ids": sid},
                 "$set": {"updated_at": now_iso(), "updated_by": actor}},
                projection={"_id": 0}, return_document=ReturnDocument.AFTER)
            if not res:
                if await db[COLL_ICT].find_one({"id": _id, "settlement_ids": sid}, {"_id": 0, "id": 1}):
                    continue
                async for d in db[COLL_ICT].find({"settlement_ids": sid}, {"_id": 0, "id": 1, "pair_id": 1}):
                    await db[COLL_ICT].update_one({"id": d["id"]}, {
                        "$inc": {"settled_amount": -amount_by_pair.get(d["pair_id"], 0.0)},
                        "$pull": {"settlement_ids": sid},
                        "$set": {"status": status_by_pair.get(d["pair_id"], "confirmed"), "updated_at": now_iso()},
                        "$unset": {"settled_at": ""}})
                raise _SettleRowRejected(row.get("number") or row["pair_id"])
            if float(res.get("settled_amount") or 0) + float(res.get("returned_amount") or 0) \
                    >= float(res.get("grand_total") or 0) - EPS and res.get("status") != "settled":
                await db[COLL_ICT].update_one({"id": _id}, {"$set": {"status": "settled", "settled_at": now_iso()}})
        await db[COLL_ICS].update_one({"id": sid}, {"$set": {f"{field}.{i}.applied_at": now_iso()}})
        row["applied_at"] = now_iso()


async def _run_settlement(doc: Dict[str, Any], actor: str) -> Dict[str, Any]:
    from services import twin_journal as _twin
    sid = doc["id"]
    payer, payee = doc["payer_entity_id"], doc["payee_entity_id"]
    try:
        await _apply_settlement_rows(doc, actor)
    except _SettleRowRejected as exc:
        await db[COLL_ICS].update_one({"id": sid}, {"$set": {
            "status": "cancelled", "cancel_reason": f"sisa transaksi {exc} berubah saat diproses",
            "updated_at": now_iso()}})
        raise IntercoConflict(f"Sisa transaksi {exc} berubah saat diproses. Tidak ada yang tercatat; muat ulang lalu "
                              "ulangi.") from exc
    # EFEK 2 — uang benar-benar berpindah: kas kembar (netting tidak membuat kas)
    if doc.get("method") != "netting" and not doc.get("cash_out_id"):
        from services import interco_money_service as icm
        cash = await icm.twin_cash(
            out_entity=payer, in_entity=payee, amount=float(doc["total_applied"]), category="pelunasan antar-PT",
            description=f"Pelunasan antar-PT {doc.get('number')} ({doc.get('payer_entity_name')} → "
                        f"{doc.get('payee_entity_name')})",
            ref_type="interco_settlement", ref_id=sid, actor=actor or "system", txn_date=doc.get("settle_date", ""),
            out_account_id=doc.get("payer_account_id", ""), in_account_id=doc.get("payee_account_id", ""))
        doc["cash_out_id"], doc["cash_in_id"] = cash["out"].get("id", ""), cash["in"].get("id", "")
        await db[COLL_ICS].update_one({"id": sid}, {"$set": {"cash_out_id": doc["cash_out_id"],
                                                             "cash_in_id": doc["cash_in_id"]}})
    gl_res = await repost_settlement_gl(sid, actor)
    await db[COLL_ICS].update_one({"id": sid}, {"$set": {"status": "posted", "updated_at": now_iso()}})

    # Refresh saldo pasangan (payee=penjual, payer=pembeli) + arah balik bila netting (F-08).
    await _update_account_balance(payee, payer)
    if doc.get("netted_against"):
        await _update_account_balance(payer, payee)
    # US7/INV-IC-03 — sisa IC-AR/IC-AP yang dieliminasi ikut mengecil setelah settlement.
    for row in doc.get("applied", []) + doc.get("netted_against", []):
        if row.get("pair_id"):
            await _sync_group_elimination(row["pair_id"])
    # US10 — jejak dua arah: settlement MELUNASI transaksi-transaksi ini.
    try:
        from services import doc_refs_service as _refs
        for row in doc.get("applied", []):
            for _id in (row["interco_id"], row.get("counterpart_id")):
                if _id:
                    await _refs.safe_link(("interco_settlement", sid), ("interco_transaction", _id), "settles",
                                          note=f"Settlement antar-PT {doc.get('number')}")
    except Exception as exc:  # noqa: BLE001
        print(f"[interco] tautan settlement gagal: {exc}")
    out = safe_doc(await db[COLL_ICS].find_one({"id": sid}, {"_id": 0}))
    out["gl"] = gl_res
    out["warning"] = await _twin.warning_for(gl_res, _settlement_sides(out))
    return out


#: KF-T2 — enam kunci Pusat Pengaturan jadwal bayar antar-PT (dulu dibaca langsung dari dokumen pengaturan).
PAYMENT_SETTING_KEYS = ("allow_netting", "require_full_payment", "cutoff_day", "payment_day", "basis", "reminder_days")


async def payment_settings(entity_id: str = "") -> Dict[str, Any]:
    """Aturan jadwal bayar antar-PT untuk PT pembayar ini (lapisan global → PT). `cutoff_day`/`payment_day` 0 dan
    `basis` "" = belum diatur → `None`, arti yang dipakai jadwal dan pengingat hari ini."""
    ctx = {"entity_id": entity_id or ""}
    out = {k: await config_resolver.value_of(f"interco_payment.{k}", ctx) for k in PAYMENT_SETTING_KEYS}
    for k in ("cutoff_day", "payment_day"):
        out[k] = int(out[k]) if out[k] not in (None, "", 0) else None
    out["basis"] = out["basis"] or None
    out["allow_netting"] = bool(out["allow_netting"])
    out["require_full_payment"] = bool(out["require_full_payment"])
    return out


_BASIS = {"invoice": ("invoiced_at", "Tanggal invoice"), "receipt": ("received_at", "Tanggal barang diterima"),
          "document": ("doc_date", "Tanggal dokumen")}


def _period_for(day: str, cutoff: int, pay_day: Optional[int]) -> Dict[str, str]:
    """Transaksi s.d. tanggal cutoff → periode bulan itu; setelahnya → bulan berikutnya."""
    import calendar
    from datetime import date as _d
    d = _d.fromisoformat(day[:10])
    y, m = (d.year, d.month) if d.day <= cutoff else ((d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1))
    last = calendar.monthrange(y, m)[1]
    pay = min(int(pay_day), last) if pay_day else last
    return {"period": f"{y:04d}-{m:02d}", "pay_date": f"{y:04d}-{m:02d}-{pay:02d}"}


async def payment_schedule(scope_entity_ids: List[str], payer: str = "", payee: str = "") -> Dict[str, Any]:
    """LN-024 — daftar utang antar-PT PER TRANSAKSI (tidak digabung/netting). Periode bayar hanya diisi bila
    cutoff & basis sudah dikonfigurasi; bila belum (KLX-03 pending) tanggal tidak diasumsikan."""
    q: Dict[str, Any] = {"role": "seller", "status": {"$in": list(OPEN_STATUSES)},
                         "buyer_entity_id": {"$in": scope_entity_ids}}
    if payer:
        q["buyer_entity_id"] = payer
    if payee:
        q["seller_entity_id"] = payee
    docs = await db[COLL_ICT].find(q, {"_id": 0}).sort("created_at", 1).to_list(2000)
    cfg = await payment_settings(payer)
    basis = _BASIS.get(cfg.get("basis") or "")
    ready = bool(basis and cfg.get("cutoff_day"))
    cfg_by_payer: Dict[str, Dict[str, Any]] = {}   # KLX-03 — pengaturan boleh per PT pembayar
    today = _today()
    rows = []
    for d in docs:
        pcfg = cfg_by_payer.get(d["buyer_entity_id"])
        if pcfg is None:
            pcfg = cfg_by_payer[d["buyer_entity_id"]] = await payment_settings(d["buyer_entity_id"])
        pbasis = _BASIS.get(pcfg.get("basis") or "")
        pready = bool(pbasis and pcfg.get("cutoff_day"))
        remaining = round(float(d.get("grand_total") or 0) - float(d.get("settled_amount") or 0)
                          - float(d.get("returned_amount") or 0), 2)
        if remaining <= EPS:
            continue
        bdate = (d.get(pbasis[0]) or "") if pbasis else ""
        row = {"interco_id": d["id"], "number": d.get("number"), "counterpart_number": d.get("counterpart_number"),
               "payer_entity_id": d["buyer_entity_id"], "payer_entity_name": d.get("buyer_entity_name", ""),
               "payee_entity_id": d["seller_entity_id"], "payee_entity_name": d.get("seller_entity_name", ""),
               "status": d.get("status"), "grand_total": float(d.get("grand_total") or 0), "remaining": remaining,
               "received_at": d.get("received_at") or "", "invoiced_at": d.get("invoiced_at") or "",
               "doc_date": d.get("doc_date") or (d.get("created_at") or "")[:10], "due_date": d.get("due_date") or "",
               "basis_date": bdate, "period": None, "pay_date": None}
        if pready and bdate:
            row.update(_period_for(bdate, int(pcfg["cutoff_day"]), pcfg.get("payment_day")))
            row["basis_label"] = pbasis[1]
        row["age_days"] = (_dt.date.fromisoformat(today) - _dt.date.fromisoformat(row["doc_date"][:10])).days \
            if row["doc_date"] else None
        rows.append(row)
    pairs: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = f"{r['payer_entity_id']}>{r['payee_entity_id']}"
        p = pairs.setdefault(k, {"payer_entity_id": r["payer_entity_id"], "payer_entity_name": r["payer_entity_name"],
                                 "payee_entity_id": r["payee_entity_id"], "payee_entity_name": r["payee_entity_name"],
                                 "count": 0, "remaining": 0.0})
        p["count"] += 1
        p["remaining"] = round(p["remaining"] + r["remaining"], 2)
    return {"rows": rows, "pairs": list(pairs.values()), "config": cfg,
            "cutoff_status": "configured" if (ready or any(r.get("period") for r in rows)) else "not_configured",
            "basis_label": basis[1] if basis else None, "netting": "disabled" if not cfg["allow_netting"] else "allowed",
            "note": None if ready else "Cutoff & acuan periode pembayaran belum diatur — periode bayar & pengingat "
                                       "belum jalan. Atur di bagian Aturan jadwal bayar di bawah (semua PT atau per "
                                       "PT pembayar)."}


async def job_interco_payment_reminder() -> Dict[str, Any]:
    """LN-024 — pengingat ke finance PT PEMBAYAR N hari sebelum tanggal bayar (hanya bila cutoff dikonfigurasi)."""
    from services.notification_service import create_notification
    entities = [e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(100)]
    today = _dt.date.fromisoformat(_today())
    sent, skipped = 0, 0
    for payer in entities:
        cfg = await payment_settings(payer)
        days = int(cfg.get("reminder_days") or 0)
        sch = await payment_schedule(entities, payer=payer)
        if sch["cutoff_status"] != "configured" or days <= 0:
            skipped += len(sch["rows"])
            continue
        for r in sch["rows"]:
            if not r.get("pay_date"):
                continue
            left = (_dt.date.fromisoformat(r["pay_date"]) - today).days
            if 0 <= left <= days:
                n = await create_notification(
                    notif_type="interco_payment_due", severity="warning" if left <= 1 else "info",
                    title=f"Bayar antar-PT {r['pay_date']}: {r['number']}",
                    body=(f"{r['payer_entity_name']} → {r['payee_entity_name']} · {rupiah(r['remaining'])} "
                          f"(penuh, per transaksi) · {'hari ini' if left == 0 else f'{left} hari lagi'}. "
                          "Cutoff mengikuti pengaturan pembayaran antar-PT."),
                    link="interco-transactions", entity_id=payer, recipient_role="finance",
                    ref=f"{r['interco_id']}:{r['pay_date']}", dedupe=True, dedupe_scope="ever")
                sent += 1 if n else 0
    return {"created": sent, "skipped_pending_cutoff": skipped, "detail": f"{sent} pengingat bayar antar-PT dikirim"}


def _settlement_sides(doc: Dict[str, Any]) -> List[Any]:
    """Rencana jurnal settlement (baris sama dengan kode lama).

    netting : Payer Dr IC-AP / Cr IC-AR · Payee Dr IC-AP / Cr IC-AR (saling hapus piutang/utang antar-PT)
    transfer/cash : Payer Dr IC-AP / Cr Kas Besar · Payee Dr Kas Besar / Cr IC-AR (uang benar-benar berpindah)
    """
    from services.twin_journal import TwinSide
    total = round(float(doc.get("total_applied") or 0), 2)
    sid, label = doc["id"], doc.get("number") or doc["id"]
    payer_ent, payee_ent = doc["payer_entity_id"], doc["payee_entity_id"]
    if doc.get("method", "netting") == "netting":
        lp = gl_service._balanced_pair(gl_service.ACC_IC_AP, gl_service.ACC_IC_AR, total,
                                       f"Netting antar-PT {label} → {doc.get('payee_entity_name', '')}")
        le = gl_service._balanced_pair(gl_service.ACC_IC_AP, gl_service.ACC_IC_AR, total,
                                       f"Netting antar-PT {label} ← {doc.get('payer_entity_name', '')}")
        dp = de = f"Settlement antar-PT (netting) {label}"
    else:
        cash_acc = gl_service.ACC_KAS_BESAR
        lp = gl_service._balanced_pair(gl_service.ACC_IC_AP, cash_acc, total,
                                       f"Bayar utang antar-PT {label} → {doc.get('payee_entity_name', '')}")
        le = gl_service._balanced_pair(cash_acc, gl_service.ACC_IC_AR, total,
                                       f"Terima pelunasan antar-PT {label} ← {doc.get('payer_entity_name', '')}")
        dp, de = f"Bayar utang antar-PT {label}", f"Terima pelunasan antar-PT {label}"
    return [TwinSide("payer", payer_ent, lp, dp, label, (COLL_ICS, sid), "_payer"),
            TwinSide("payee", payee_ent, le, de, label, (COLL_ICS, sid), "_payee")]


async def repost_settlement_gl(settlement_id: str, actor: str = "") -> Dict[str, Dict[str, str]]:
    """PK-06 — terbitkan jurnal settlement yang KURANG per sisi; ringkasan `gl_status` di dokumen."""
    from services import twin_journal as _twin
    doc = await db[COLL_ICS].find_one({"id": settlement_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Settlement tidak ditemukan.")
    if float(doc.get("total_applied") or 0) <= EPS:
        await db[COLL_ICS].update_one({"id": settlement_id}, {"$set": {"gl_status": "not_required"}})
        return {}
    res = await _twin.post_twin(source_type="interco_settlement", base_id=settlement_id,
                                date=doc.get("settle_date") or now_iso(), sides=_settlement_sides(doc),
                                created_by=actor or "system")
    errs = [v["error"] for v in res.values() if v["status"] == "failed"]
    await db[COLL_ICS].update_one({"id": settlement_id}, {"$set": {
        "gl_status": "failed" if errs else "posted", "gl_error": "; ".join(errs)[:500]}})
    return res


async def _post_gl_settlement(doc: Dict[str, Any], actor: str) -> None:
    """Pemanggil lama → `repost_settlement_gl` (PK-06: per sisi, tanpa penjaga "payer ATAU payee")."""
    await repost_settlement_gl(doc["id"], actor)


async def list_settlements(scope_entity_ids: List[str], entity_id: str = "",
                           limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if entity_id and entity_id != "all":
        q["$or"] = [{"payer_entity_id": entity_id}, {"payee_entity_id": entity_id}]
    elif scope_entity_ids:
        q["$or"] = [{"payer_entity_id": {"$in": scope_entity_ids}},
                    {"payee_entity_id": {"$in": scope_entity_ids}}]
    rows = await db[COLL_ICS].find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [safe_doc(r) for r in rows]


async def get_settlement(sid: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db[COLL_ICS].find_one({"id": sid}, {"_id": 0}))


# ═══════════════════════════════════════════════════════════════════════════
# META & SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
def net_positions(accs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keputusan pemilik K-07 (26 Okt) — posisi BERSIH dua arah per pasangan PT (netting) = angka utama utang/piutang
    antar-PT. Setiap arah dagang (penjual → pembeli) dihitung SEKALI (baris piutang penjual & utang pembeli adalah
    cermin angka yang sama), lalu dua arah pasangan yang sama saling dikurangkan. Jadwal bayar per dokumen tetap
    rincian (bruto)."""
    directed: Dict[Any, float] = {}
    names: Dict[str, str] = {}
    for a in accs:
        role = a.get("role")
        seller, buyer = a.get("seller_entity_id"), a.get("buyer_entity_id")
        if not (seller and buyer):   # baris lama tanpa arah eksplisit → turunkan dari peran
            if role == "receivable":
                seller, buyer = a.get("from_entity_id"), a.get("to_entity_id")
            elif role == "payable":
                seller, buyer = a.get("to_entity_id"), a.get("from_entity_id")
        if not (seller and buyer) or seller == buyer:
            continue
        if a.get("from_entity_id") and a.get("from_entity_name"):
            names[a["from_entity_id"]] = a["from_entity_name"]
        if a.get("to_entity_id") and a.get("to_entity_name"):
            names[a["to_entity_id"]] = a["to_entity_name"]
        directed[(buyer, seller)] = round(float(a.get("outstanding") or 0), 2)   # buyer berutang ke seller
    out: List[Dict[str, Any]] = []
    seen = set()
    for (debtor, creditor) in list(directed.keys()):
        key = tuple(sorted((debtor, creditor)))
        if key in seen:
            continue
        seen.add(key)
        a, b = key
        a_owes_b = directed.get((a, b), 0.0)
        b_owes_a = directed.get((b, a), 0.0)
        net = round(a_owes_b - b_owes_a, 2)
        if abs(net) <= EPS and a_owes_b <= EPS and b_owes_a <= EPS:
            continue
        d, c = (a, b) if net >= 0 else (b, a)
        out.append({"debtor_entity_id": d, "debtor_entity_name": names.get(d, d),
                    "creditor_entity_id": c, "creditor_entity_name": names.get(c, c),
                    "net": abs(net),
                    "gross_debtor_owes": directed.get((d, c), 0.0),
                    "gross_creditor_owes": directed.get((c, d), 0.0)})
    out.sort(key=lambda r: -r["net"])
    return out


async def summary(scope_entity_ids: List[str], entity_id: str = "") -> Dict[str, Any]:
    """Ringkasan untuk layar (US5): saldo aktif + jumlah dokumen open + settlement bulan ini."""
    accs = await list_accounts(scope_entity_ids)
    total_receivable = sum(a.get("outstanding", 0) for a in accs
                           if a.get("role") == "receivable" and
                           (not entity_id or a.get("from_entity_id") == entity_id or entity_id == "all"))
    total_payable = sum(a.get("outstanding", 0) for a in accs
                        if a.get("role") == "payable" and
                        (not entity_id or a.get("from_entity_id") == entity_id or entity_id == "all"))
    open_docs = await db[COLL_ICT].count_documents({
        "entity_id": {"$in": scope_entity_ids} if scope_entity_ids else {"$exists": True},
        "status": {"$in": list(OPEN_STATUSES)},
    })
    # K-07 — posisi bersih (netting dua arah) dari sudut pandang PT aktif; mode gabungan: Σ posisi bersih semua pasangan.
    pairs = net_positions(accs)
    one = entity_id if entity_id and entity_id != "all" else ""
    if one:
        pairs = [p for p in pairs if one in (p["debtor_entity_id"], p["creditor_entity_id"])]
        net_payable = sum(p["net"] for p in pairs if p["debtor_entity_id"] == one)
        net_receivable = sum(p["net"] for p in pairs if p["creditor_entity_id"] == one)
    else:
        net_payable = net_receivable = sum(p["net"] for p in pairs)
    return {
        # Angka utama (K-07): posisi bersih dua arah.
        "net_payable": round(net_payable, 2),
        "net_receivable": round(net_receivable, 2),
        "net_pairs": pairs,
        "net_basis": "Posisi bersih dua arah per pasangan PT (netting); rincian per dokumen di Jadwal Bayar",
        # Rincian (bruto per arah dagang / dokumen terbuka).
        "total_receivable": round(total_receivable, 2),
        "total_payable": round(total_payable, 2),
        "open_documents": open_docs,
        "pair_count": len(accs),
        "statuses": [{"value": s, "label": STATUS_LABEL[s]} for s in STATUSES],
    }


async def meta() -> Dict[str, Any]:
    return {
        "statuses": [{"value": s, "label": STATUS_LABEL[s]} for s in STATUSES],
        "pricing_modes": [
            {"value": "fixed_price", "label": "Harga tetap dari kontrak internal"},
            {"value": "at_cost", "label": "Sesuai HPP penjual"},
            {"value": "cost_plus_pct", "label": "HPP + persen margin"},
        ],
        "ppn_modes": [
            {"value": "ikut_pkp", "label": "Ikut status PKP penjual"},
            {"value": "tanpa_ppn", "label": "Tanpa PPN"},
            {"value": "dengan_ppn", "label": "Dengan PPN (paksa)"},
        ],
        "settlement_methods": [
            {"value": "netting", "label": "Netting (saling hapus, tanpa uang)"},
            {"value": "transfer", "label": "Transfer bank"},
            {"value": "cash", "label": "Kas"},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# ELIMINASI KONSOLIDASI (US7 / INV-IC-03) — dijaga OTOMATIS
# ═══════════════════════════════════════════════════════════════════════════
async def _sync_group_elimination(pair_id: str) -> None:
    """Selaraskan entri eliminasi grup untuk satu pair.

    KENAPA OTOMATIS: margin antar-PT WAJIB hilang di laporan grup selama barang
    belum terjual keluar (INV-IC-03). Kalau ini hanya bisa dijalankan lewat
    tombol, laporan konsolidasi akan salah setiap kali orang lupa menekannya —
    dan "lupa" bukan kesalahan yang boleh membuat laba grup menggelembung.
    Tombol manual di layar Konsolidasi Grup tetap ada untuk data lama/backfill.

    Kegagalan di sini TIDAK boleh menggagalkan transaksi bisnisnya (jurnal per-PT
    sudah sah); dicatat ke log supaya tetap terlihat.
    """
    try:
        from services import consolidation_service as _cons
        await _cons.sync_g6_for_pair(pair_id)
    except Exception as exc:  # noqa: BLE001 — pelengkap laporan, bukan syarat transaksi
        print(f"[interco] sync eliminasi grup gagal untuk {pair_id}: {exc}")


async def _link_refs(pair_id: str) -> None:
    """Tautan dokumen DUA ARAH (G-4/US10): dokumen kembar saling menunjuk."""
    try:
        from services import doc_refs_service as _refs
        seller, buyer = await _pair_docs(pair_id)
        await _refs.safe_link(("interco_transaction", seller["id"]),
                              ("interco_transaction", buyer["id"]), "child",
                              note="Dokumen kembar antar-PT (PO internal ↔ SO/SJ/Invoice)")
    except Exception as exc:  # noqa: BLE001
        print(f"[interco] tautan dokumen kembar gagal {pair_id}: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# PEMBALIKAN JURNAL SAAT BATAL (G-1: koreksi ber-alasan, bukan hapus senyap)
# ═══════════════════════════════════════════════════════════════════════════
async def _reverse_gl_for_pair(pair_id: str, actor: str, reason: str) -> int:
    """Balik jurnal pair yang SUDAH diposting (Dr↔Cr ditukar), idempotent.

    Pembatalan transaksi yang sudah dikonfirmasi tidak boleh menyisakan
    pendapatan & piutang antar-PT di buku. Kita TIDAK menghapus jurnal lama
    (audit trail) melainkan menerbitkan jurnal pembalik ber-alasan.
    """
    posted = 0
    for suffix in ("seller", "cogs", "buyer", "receipt"):
        src_id = f"{pair_id}:{suffix}"
        je = await db.journal_entries.find_one(
            {"source_type": "interco_transaction", "source_id": src_id,
             "status": "posted"}, {"_id": 0})
        if not je:
            continue
        if await gl_service._already_posted("interco_transaction", f"{src_id}:reversal"):
            continue
        rev_lines = [{
            "account_code": l["account_code"],
            "debit": float(l.get("credit") or 0),
            "credit": float(l.get("debit") or 0),
            "description": f"PEMBALIKAN: {l.get('description', '')}".strip(),
        } for l in je.get("lines", [])]
        await gl_service._insert_entry(
            lines=rev_lines,
            description=f"Pembalikan {je.get('description', '')} — alasan: {reason}",
            date=now_iso(), source_type="interco_transaction",
            source_id=f"{src_id}:reversal", entity_id=je.get("entity_id", ""),
            created_by=actor or "system", source_label=je.get("source_label", ""),
        )
        posted += 1
    return posted


# ═══════════════════════════════════════════════════════════════════════════
# JURNAL PER-PAIR (dipakai Detail Panel — "tunjukkan buktinya di dua buku")
# ═══════════════════════════════════════════════════════════════════════════
async def pair_journal(pair_id: str) -> Dict[str, Any]:
    """Kumpulkan SEMUA bukti akuntansi satu pair untuk ditampilkan di layar.

    Sebelumnya frontend menebak-nebak lewat `/api/gl/entries` (endpoint yang tidak
    pernah ada) sehingga blok jurnal DIAM-DIAM kosong. Satu endpoint khusus
    membuat layar menampilkan bukti yang sama dengan yang dipakai invarian.
    """
    async def _je(source_id: str) -> Optional[Dict[str, Any]]:
        return await db.journal_entries.find_one(
            {"source_type": "interco_transaction", "source_id": source_id},
            {"_id": 0})

    seller_je = await _je(f"{pair_id}:seller")
    buyer_je = await _je(f"{pair_id}:buyer")
    cogs_je = await _je(f"{pair_id}:cogs")
    receipt_je = await _je(f"{pair_id}:receipt")
    reversals = await db.journal_entries.find(
        {"source_type": "interco_transaction",
         "source_id": {"$regex": f"^{pair_id}:.*:reversal$"}}, {"_id": 0}).to_list(20)

    # Settlement yang menyentuh pair ini → jurnal kedua buku
    settlements = await db[COLL_ICS].find(
        {"applied.pair_id": pair_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    settlement_jes: List[Dict[str, Any]] = []
    for s in settlements:
        for side in ("payer", "payee"):
            je = await db.journal_entries.find_one(
                {"source_type": "interco_settlement", "source_id": f"{s['id']}:{side}"},
                {"_id": 0})
            if je:
                settlement_jes.append({**je, "settlement_number": s.get("number", ""),
                                       "side": side})

    eliminations = await db.intercompany_eliminations.find(
        {"source_g6_pair_id": pair_id}, {"_id": 0}).to_list(20)

    transfers = await db.warehouse_transfers.find(
        {"$or": [{"interco_pair_id": pair_id},
                 {"interco_return_pair_id": {"$in": [
                     r["return_pair_id"] for r in await db.interco_returns.find(
                         {"origin_pair_id": pair_id, "role": "returner"},
                         {"_id": 0, "return_pair_id": 1}).to_list(50)]}}]},
        {"_id": 0, "id": 1, "code": 1, "status": 1, "items": 1, "created_at": 1,
         "approved_at": 1, "approved_by": 1, "je_intercompany": 1,
         "interco_return_number": 1,
         "source_entity_id": 1, "dest_entity_id": 1}).to_list(20)

    # ── FASE G-6b: retur antar-PT (dokumen + jurnalnya) ─────────────────────
    returns = await db.interco_returns.find(
        {"origin_pair_id": pair_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return_jes: List[Dict[str, Any]] = []
    seen_rp = {r["return_pair_id"] for r in returns}
    for rp in sorted(seen_rp):
        for suffix in ("seller", "buyer", "goods_out", "goods_in"):
            je = await db.journal_entries.find_one(
                {"source_type": "interco_return", "source_id": f"{rp}:{suffix}"},
                {"_id": 0})
            if je:
                return_jes.append({**je, "return_pair_id": rp, "block": suffix})

    # ── FASE G-6b: faktur pajak internal (keluaran + masukan) ───────────────
    tax_out = await db.tax_invoices.find(
        {"interco_pair_id": pair_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    tax_in = await db.tax_invoices_in.find(
        {"interco_pair_id": pair_id}, {"_id": 0}).sort("created_at", -1).to_list(20)

    return {
        "pair_id": pair_id,
        "seller": safe_doc(seller_je) if seller_je else None,
        "buyer": safe_doc(buyer_je) if buyer_je else None,
        "cogs": safe_doc(cogs_je) if cogs_je else None,
        "receipt": safe_doc(receipt_je) if receipt_je else None,
        "reversals": [safe_doc(r) for r in reversals],
        "settlement_entries": [safe_doc(j) for j in settlement_jes],
        "settlements": [safe_doc(s) for s in settlements],
        "eliminations": [safe_doc(e) for e in eliminations],
        "warehouse_tasks": [safe_doc(t) for t in transfers],
        "returns": [safe_doc(r) for r in returns],
        "return_entries": [safe_doc(j) for j in return_jes],
        "tax_invoices_out": [safe_doc(t) for t in tax_out],
        "tax_invoices_in": [safe_doc(t) for t in tax_in],
    }


# ═══════════════════════════════════════════════════════════════════════════
# PK-30 (IC-02, K-07) — PANJANG AKTUAL: roll antar-PT dikirim utuh, dokumen & jurnal mengikuti panjangnya
# ═══════════════════════════════════════════════════════════════════════════
def _angka(q: float) -> str:
    """Panjang untuk kalimat pengguna: 130 → "130", 130.5 → "130,5"."""
    s = f"{round(float(q), 2):.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


async def _actual_lengths(transfer_id: str) -> Dict[str, float]:
    """Panjang aktual per produk = Σ `length_remaining` roll yang direservasi tugas gudang ini."""
    out: Dict[str, float] = {}
    async for r in db.inventory_rolls.find({"reserved_ref.id": transfer_id},
                                           {"_id": 0, "product_id": 1, "length_remaining": 1}):
        out[r["product_id"]] = round(out.get(r["product_id"], 0.0) + float(r.get("length_remaining") or 0), 4)
    return out


def _ordered_by_product(doc: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for it in doc.get("items") or []:
        out[it["product_id"]] = round(out.get(it["product_id"], 0.0) + float(it.get("quantity") or 0), 4)
    return out


def _first_difference(doc: Dict[str, Any], actual: Dict[str, float]) -> Optional[Tuple[str, float, float, str]]:
    """(produk, aktual, pesanan, satuan) baris pertama yang panjangnya berbeda > QTY_EPS; None bila semua sama."""
    from services.tolerances import QTY_EPS
    units = {it["product_id"]: it.get("unit") or "meter" for it in doc.get("items") or []}
    for pid, ordered in _ordered_by_product(doc).items():
        got = float(actual.get(pid, ordered))
        if abs(got - ordered) > QTY_EPS:
            return pid, got, ordered, units.get(pid, "meter")
    return None


def _adjusted_doc_fields(doc: Dict[str, Any], actual: Dict[str, float]) -> Dict[str, Any]:
    """Baris & total baru menurut panjang aktual (rumus `_totals_from_items`, tarif & sakelar PPN dokumen).

    Satu produk di beberapa baris: selisih panjangnya dibebankan ke baris TERAKHIR produk itu."""
    from services.tolerances import QTY_EPS
    ordered = _ordered_by_product(doc)
    last_idx = {it["product_id"]: i for i, it in enumerate(doc.get("items") or [])}
    items: List[Dict[str, Any]] = []
    lines: List[Dict[str, Any]] = []
    for i, it in enumerate(doc.get("items") or []):
        new = dict(it)
        pid = it["product_id"]
        if last_idx[pid] == i and pid in actual and abs(float(actual[pid]) - ordered[pid]) > QTY_EPS:
            q_from = float(it.get("quantity") or 0)
            q_to = round(q_from + float(actual[pid]) - ordered[pid], 4)
            new["quantity_ordered"] = float(it.get("quantity_ordered", q_from))
            new["quantity"] = q_to
            new["line_subtotal"] = round(q_to * float(it.get("unit_price") or 0), 2)
            lines.append({"product_id": pid, "from_qty": round(ordered[pid], 4), "to_qty": round(float(actual[pid]), 4)})
        items.append(new)
    totals = _totals_from_items(items, float(doc.get("tax_rate") or 0), bool(doc.get("tax_apply")))
    from_sub, from_tax = float(doc.get("subtotal") or 0), float(doc.get("tax_amount") or 0)
    from_total = float(doc.get("grand_total") or 0)
    return {"items": items, "subtotal": totals["subtotal"], "tax_amount": totals["tax"],
            "grand_total": totals["total"], "lines": lines,
            "from_subtotal": round(from_sub, 2), "to_subtotal": totals["subtotal"],
            "delta_subtotal": round(totals["subtotal"] - from_sub, 2),
            "delta_tax": round(totals["tax"] - from_tax, 2),
            "delta_total": round(totals["total"] - from_total, 2)}


def _adjust_sides(seller: Dict[str, Any], buyer: Dict[str, Any], adj: Dict[str, Any]) -> List[Any]:
    """Rencana jurnal PENYESUAIAN PANJANG dua sisi (kunci `{pair}:adj:seller` / `{pair}:adj:buyer`, status `_adj`).

    Roll lebih panjang (selisih total > 0):
      Penjual  Dr 1-1250 selisih total · Cr 4-1000 selisih DPP · Cr 2-1200 selisih PPN
      Pembeli  Dr 1-1310 selisih DPP · Dr 1-1500 selisih PPN · Cr 2-1250 selisih total
    Roll lebih pendek: arah yang sama dibalik, nilai mutlak. Selisih total 0 → tidak ada jurnal.
    """
    from services.twin_journal import TwinSide
    d_sub, d_tax, d_tot = (float(adj.get("delta_subtotal") or 0), float(adj.get("delta_tax") or 0),
                           float(adj.get("delta_total") or 0))
    if abs(d_tot) <= EPS:
        return []
    naik = d_tot > 0
    s_, t_, g_ = abs(d_sub), abs(d_tax), abs(d_tot)
    code = seller.get("number") or seller["pair_id"]
    ket = f"Penyesuaian panjang roll antar-PT {code}"

    def _l(acc: str, amount: float, debit: bool, desc: str) -> Dict[str, Any]:
        return {"account_code": acc, "debit": amount if debit else 0.0, "credit": 0.0 if debit else amount,
                "description": desc}

    lines_s = [_l(gl_service.ACC_IC_AR, g_, naik, f"Piutang antar-PT {code} — {ket.lower()}"),
               _l(gl_service.ACC_PENDAPATAN, s_, not naik, f"Pendapatan antar-PT {code} — {ket.lower()}")]
    if t_ > EPS:
        lines_s.append(_l(gl_service.ACC_PPN_OUT, t_, not naik, f"PPN Keluaran antar-PT {code} — {ket.lower()}"))
    num_b = buyer.get("number", code)
    lines_b = [_l(gl_service.ACC_PERSEDIAAN_TRANSIT, s_, naik, f"Barang antar-PT dalam perjalanan {num_b} — "
                                                               f"{ket.lower()}")]
    if t_ > EPS:
        lines_b.append(_l(gl_service.ACC_PPN_IN, t_, naik, f"PPN Masukan antar-PT {num_b} — {ket.lower()}"))
    lines_b.append(_l(gl_service.ACC_IC_AP, g_, not naik, f"Utang antar-PT {num_b} — {ket.lower()}"))
    return [
        TwinSide("seller", seller["seller_entity_id"], lines_s, ket, code, (COLL_ICT, seller["id"]), "_adj"),
        TwinSide("buyer", seller["buyer_entity_id"], lines_b, f"Penyesuaian panjang roll antar-PT {num_b}", num_b,
                 (COLL_ICT, buyer["id"]), "_adj"),
    ]


def _delivery_lines(seller: Dict[str, Any], buyer: Dict[str, Any], cost_out: float, receipt: float
                    ) -> List[Tuple[str, str, List[Dict[str, Any]]]]:
    """Baris jurnal HPP penjual & penerimaan pembeli (`post_gl_on_delivery`) untuk pemeriksaan awal."""
    out = []
    code = seller.get("number") or seller["pair_id"]
    if cost_out > EPS:
        out.append(("cogs", seller["seller_entity_id"], gl_service._balanced_pair(
            gl_service.ACC_HPP, gl_service.ACC_PERSEDIAAN, round(cost_out, 2), f"HPP antar-PT {code}")))
    if receipt > EPS:
        out.append(("receipt", seller["buyer_entity_id"], gl_service._balanced_pair(
            gl_service.ACC_PERSEDIAAN, gl_service.ACC_PERSEDIAAN_TRANSIT, round(receipt, 2),
            f"Penerimaan barang antar-PT {buyer.get('number', '')}")))
    return out


async def precheck_warehouse_task(transfer: Dict[str, Any], *, periksa_jurnal: bool = True) -> Dict[str, Any]:
    """PERIKSA sebelum tugas gudang antar-PT disetujui (tanpa tulisan apa pun).

    1. Panjang aktual per produk = Σ panjang roll yang direservasi tugas ini; berbeda dari jumlah dokumen > QTY_EPS →
       `differs`. Mode `antar_entitas.selisih_panjang` PT PENJUAL = `tolak` + berbeda → `IntercoLengthMismatch` (409).
    2. (`periksa_jurnal`) Jurnal penyesuaian dua sisi (bila berbeda) lewat `twin_journal.preflight_twin`, lalu jurnal
       HPP penjual & penerimaan pembeli lewat `gl_service.preflight_entry` — semuanya bertanggal hari ini (WIB).
    → `{"actual": {product_id: qty}, "differs": bool}`. Dipakai `create_warehouse_task` (tanpa periksa jurnal).
    """
    from services import twin_journal as _twin
    pair_id = transfer.get("interco_pair_id") or ""
    seller, buyer = await _pair_docs(pair_id)
    actual = await _actual_lengths(transfer["id"])
    beda = _first_difference(seller, actual)
    if beda:
        mode = await _config(KUNCI_SELISIH_PANJANG, seller["seller_entity_id"])
        if mode == "tolak":
            _pid, got, ordered, unit = beda
            raise IntercoLengthMismatch(
                f"Panjang roll yang dipilih ({_angka(got)} {unit}) tidak sama dengan jumlah pada transaksi antar-PT "
                f"({_angka(ordered)} {unit}). Pilih roll lain, atau ubah pengaturan \"Bila panjang roll beda dari "
                "pesanan antar-PT\".")
    out = {"actual": actual, "differs": bool(beda)}
    if not periksa_jurnal:
        return out
    date = _today()
    adj = _adjusted_doc_fields(seller, actual) if beda and not seller.get("length_adjustment") else None
    if adj:
        await _twin.preflight_twin(source_type="interco_transaction", base_id=f"{pair_id}:adj", date=date,
                                   sides=_adjust_sides(seller, buyer, adj))
    cost_out = 0.0
    async for r in db.inventory_rolls.find({"reserved_ref.id": transfer["id"]},
                                           {"_id": 0, "length_remaining": 1, "unit_cost": 1, "base_unit_cost": 1}):
        cost_out += float(r.get("length_remaining") or 0) * float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
    receipt = float(adj["subtotal"]) if adj else float(seller.get("subtotal") or 0)
    for suffix, ent, lines in _delivery_lines(seller, buyer, cost_out, receipt):
        if await gl_service._already_posted("interco_transaction", f"{pair_id}:{suffix}"):
            continue
        await gl_service.preflight_entry(lines=lines, entity_id=ent, date=date, source_type="interco_transaction")
    return out


async def apply_length_adjustment(pair_id: str, actual: Dict[str, float], transfer: Dict[str, Any],
                                  actor: str) -> Dict[str, Any]:
    """Sesuaikan KEDUA dokumen ke panjang aktual + jurnal penyesuaian dua sisi (aman diulang).

    * Dokumen sudah ber-`length_adjustment` → dikembalikan apa adanya (`adjusted: False`); jurnal yang kurang diulang
      lewat `repost_length_adjustment` (panel Posting Gagal, jenis `interco_adj`).
    * Panjang sama → tidak ada yang ditulis.
    * Selain itu: `quantity_ordered`/`quantity`/`line_subtotal`, `subtotal`/`tax_amount`/`grand_total`, dan
      `length_adjustment` ditulis bersyarat (belum ber-`length_adjustment`) pada kedua dokumen; lalu `post_twin`
      `{pair}:adj` (sisi gagal → `gl_status_adj: failed`, tidak melempar); faktur pajak internal yang sudah terbit
      ditandai perlu pengganti; saldo antar-PT dihitung ulang.
    """
    from services import twin_journal as _twin
    seller, buyer = await _pair_docs(pair_id)
    prev = seller.get("length_adjustment")
    if prev:
        if prev.get("transfer_id") != transfer.get("id"):
            print(f"[interco] {pair_id}: sudah disesuaikan untuk tugas {prev.get('transfer_id')} — dilewati")
        return {"adjusted": False, "length_adjustment": prev, "gl": {}}
    if not _first_difference(seller, actual):
        return {"adjusted": False, "length_adjustment": None, "gl": {}}
    f = _adjusted_doc_fields(seller, actual)
    adj = {"transfer_id": transfer.get("id", ""), "from_subtotal": f["from_subtotal"], "to_subtotal": f["to_subtotal"],
           "delta_subtotal": f["delta_subtotal"], "delta_tax": f["delta_tax"], "delta_total": f["delta_total"],
           "lines": f["lines"], "by": actor or "system", "at": now_iso()}
    sides_preview = _adjust_sides(seller, buyer, adj)
    res = await db[COLL_ICT].update_many(
        {"pair_id": pair_id, "length_adjustment": {"$exists": False}},
        {"$set": {"items": f["items"], "subtotal": f["subtotal"], "tax_amount": f["tax_amount"],
                  "grand_total": f["grand_total"], "length_adjustment": adj,
                  "gl_status_adj": "pending" if sides_preview else "not_required",
                  "updated_at": now_iso(), "updated_by": actor or "system"}})
    if not res.modified_count:
        seller, _ = await _pair_docs(pair_id)
        return {"adjusted": False, "length_adjustment": seller.get("length_adjustment"), "gl": {}}
    seller, buyer = await _pair_docs(pair_id)
    gl_res = await repost_length_adjustment(pair_id, actor)
    if abs(adj["delta_total"]) > EPS:
        try:
            from services import interco_tax_service as _tax
            await _tax.flag_needs_replacement(
                pair_id, note=(f"Nilai transaksi disesuaikan ke panjang roll yang dikirim "
                               f"({rupiah(adj['from_subtotal'])} → {rupiah(adj['to_subtotal'])})."))
        except Exception as exc:  # noqa: BLE001 — penanda faktur, bukan syarat dokumen
            print(f"[interco] tandai faktur pengganti gagal {pair_id}: {exc}")
    await _update_account_balance(seller["seller_entity_id"], seller["buyer_entity_id"])
    return {"adjusted": True, "length_adjustment": adj, "gl": gl_res,
            "warning": await _twin.warning_for(gl_res, _adjust_sides(seller, buyer, adj)) if gl_res else ""}


async def repost_length_adjustment(pair_id: str, actor: str = "") -> Dict[str, Dict[str, str]]:
    """Terbitkan jurnal penyesuaian panjang yang KURANG (per sisi, idempoten; panel Posting Gagal `interco_adj`)."""
    from services import twin_journal as _twin
    seller, buyer = await _pair_docs(pair_id)
    adj = seller.get("length_adjustment") or {}
    if not adj:
        return {}
    sides = _adjust_sides(seller, buyer, adj)
    if not sides:
        await db[COLL_ICT].update_many({"pair_id": pair_id}, {"$set": {"gl_status_adj": "not_required"}})
        return {}
    return await _twin.post_twin(source_type="interco_transaction", base_id=f"{pair_id}:adj",
                                 date=adj.get("at") or now_iso(), sides=sides, created_by=actor or "system")


# ═══════════════════════════════════════════════════════════════════════════
# JEMBATAN GUDANG (US8) — barang fisik tetap lewat tugas gudang, TANPA dobel jurnal
# ═══════════════════════════════════════════════════════════════════════════
async def create_warehouse_task(interco_id: str, actor: str) -> Dict[str, Any]:
    """Terbitkan tugas gudang (`warehouse_transfers` inter_entity) untuk satu pair.

    MASALAH NYATA yang ditutup: sebelum ini, memindahkan barangnya berarti membuat
    transfer antar-PT terpisah yang **memposting jurnal at-cost M-3 lagi** — jadi
    IC-AR/IC-AP & persediaan tercatat DUA KALI untuk satu barang. Sekarang tugas
    gudang menyimpan `interco_pair_id`; saat disetujui gudang:
      * kepemilikan roll berpindah (jalur gudang yang sudah ada, satu mutasi saja),
      * jurnal at-cost M-3 **dilewati** (G-6 sudah memposting harga jual),
      * nilai roll di pembeli **dinilai ulang** ke harga beli internal (harga
        perolehannya yang sah) sehingga GL 1-1300 == subledger,
      * status pair maju ke `shipped` → `received`.
    """
    from fastapi import HTTPException
    from services.roll_service import reserve_rolls_for_transfer, release_transfer_rolls

    doc = await db[COLL_ICT].find_one({"id": interco_id}, {"_id": 0})
    if not doc:
        raise IntercoError("Transaksi tidak ditemukan.")
    if doc["status"] in ("draft", "cancelled"):
        raise IntercoError(
            "Konfirmasi transaksinya dulu — tugas gudang hanya untuk transaksi "
            "yang sudah dikonfirmasi (barang tidak boleh berjalan tanpa dokumen sah).")
    pair_id = doc["pair_id"]
    seller, buyer = await _pair_docs(pair_id)

    existing = await db.warehouse_transfers.find_one(
        {"interco_pair_id": pair_id, "status": {"$nin": ["rejected", "cancelled"]}},
        {"_id": 0, "code": 1, "status": 1})
    if existing:
        raise IntercoError(
            f"Tugas gudang {existing.get('code')} sudah ada untuk transaksi ini "
            f"(status {existing.get('status')}).")

    transfer_id = new_id("trn")
    # FASE E-1 (E1.7) — nomor per badan usaha PENJUAL (pemilik tugas gudangnya).
    code = await next_doc_number("warehouse_transfers", "code", "TRF-",
                                 entity_id=seller.get("seller_entity_id") or None)
    items_out: List[Dict[str, Any]] = []
    wh_ids: List[str] = []
    try:
        for it in seller.get("items", []):
            # UAT 24 Okt — P10.2 roll PILIHAN dipakai utuh (P10-K2: kirim utuh, tanpa dipotong); P10.6 hanya roll di
            # gudang yang BOLEH dipakai PT pembeli (gudang bersama / khusus pembeli) — ganti pemilik di tempat tanpa kirim.
            reserved = await reserve_rolls_for_transfer(
                it["product_id"], seller["seller_entity_id"],
                float(it["quantity"]), transfer_id,
                roll_ids=it.get("preferred_roll_ids") or None,
                usable_for_entity=seller.get("buyer_entity_id") or "", whole_rolls=bool(it.get("preferred_roll_ids")))
            roll_refs = [{
                "roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"),
                "warehouse_id": r.get("warehouse_id"),
                "length": float(r.get("length_remaining", 0) or 0),
            } for r in reserved]
            for r in reserved:
                if r.get("warehouse_id"):
                    wh_ids.append(r["warehouse_id"])
            items_out.append({
                "product_id": it["product_id"], "qty": round(float(it["quantity"]), 2),
                "unit": it.get("unit", "meter"), "sku": it.get("sku", ""),
                "product_name": it.get("product_name", ""),
                "lots": sorted({r.get("lot") for r in reserved if r.get("lot")}),
                "rolls": roll_refs,
                "interco_unit_price": float(it.get("unit_price") or 0),
            })
    except HTTPException as exc:
        await release_transfer_rolls(transfer_id)
        raise IntercoError(str(exc.detail)) from exc
    except Exception:
        await release_transfer_rolls(transfer_id)
        raise

    primary_wh = wh_ids[0] if wh_ids else ""
    transfer = {
        "id": transfer_id,
        "code": code,
        "transfer_kind": "inter_entity",
        "entity_id": seller["seller_entity_id"],   # FASE E-0 (L14)
        "source_entity_id": seller["seller_entity_id"],
        "dest_entity_id": seller["buyer_entity_id"],
        "source_warehouse_id": primary_wh,
        "dest_warehouse_id": primary_wh,
        "status": "waiting_approval",
        "items": items_out,
        "transfer_price": float(seller.get("subtotal") or 0),
        # P10.5 — SO peminta (dari permintaan internal): barang pindahan dicadangkan ke SO INI, bukan SO lain yang lebih lama.
        "linked_order_id": (buyer or {}).get("source_order_id") or seller.get("source_order_id") or None,
        # ── Jembatan G-6 (kunci anti dobel-posting) ──────────────────────────
        "interco_pair_id": pair_id,
        "interco_id": seller["id"],
        "interco_number": seller.get("number", ""),
        "notes": (f"Perpindahan fisik untuk transaksi antar-PT "
                  f"{seller.get('number', '')} ↔ {buyer.get('number', '')}"),
        "requested_by": actor or "system",
        "approved_by": None, "approved_at": None,
        "rejected_by": None, "rejected_at": None, "rejected_reason": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    from services import line_scope as _lines            # FASE L
    await _lines.stamp_doc(db, transfer)
    await db.warehouse_transfers.insert_one(dict(transfer))
    await db[COLL_ICT].update_many(
        {"pair_id": pair_id},
        {"$set": {"warehouse_transfer_id": transfer_id,
                  "warehouse_transfer_code": code,
                  "warehouse_transfer_status": "waiting_approval",
                  "updated_at": now_iso()}})
    try:
        from services import doc_refs_service as _refs
        await _refs.safe_link(("interco_transaction", seller["id"]),
                              ("warehouse_transfer", transfer_id), "child",
                              note="Perpindahan fisik barang antar-PT")
    except Exception as exc:  # noqa: BLE001
        print(f"[interco] tautan tugas gudang gagal: {exc}")
    return safe_doc(transfer)


async def on_warehouse_task_executed(transfer: Dict[str, Any], actor: str) -> Dict[str, Any]:
    """Dipanggil `routers/transfers.py` sesudah kepemilikan roll berpindah.

    Tiga hal yang WAJIB terjadi supaya buku tetap benar:
      1. Roll di pembeli dinilai ulang ke **harga beli internal** (kalau tidak,
         GL 1-1300 pembeli (harga jual) selamanya beda dari subledger (HPP penjual)).
      2. Status pair maju `shipped` → `received` (jejak waktu nyata, bukan tombol manual).
      3. Jurnal at-cost M-3 TIDAK diposting — itu tugas pemanggil (lihat komentar
         di `approve_transfer`); di sini kita hanya mencatat alasannya.
    """
    pair_id = transfer.get("interco_pair_id") or ""
    if not pair_id:
        return {"revalued_rolls": 0, "status": ""}
    seller, buyer = await _pair_docs(pair_id)
    price_map = {it["product_id"]: float(it.get("unit_price") or 0)
                 for it in seller.get("items", [])}
    revalued = 0
    rolls = await db.inventory_rolls.find(
        {"acquired.ref_id": transfer["id"],
         "owner_entity_id": transfer.get("dest_entity_id")},
        {"_id": 0, "id": 1, "product_id": 1, "unit_cost": 1, "base_unit_cost": 1,
         "length_remaining": 1, "roll_no": 1, "owner_entity_id": 1}).to_list(10000)
    # Biaya NYATA yang keluar dari buku penjual = Σ(panjang × harga perolehan roll)
    # — dihitung SEBELUM roll dinilai ulang ke harga beli internal.
    cost_out = round(sum(float(r.get("length_remaining") or 0) *
                         float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
                         for r in rolls), 2)
    for r in rolls:
        new_cost = price_map.get(r["product_id"])
        if new_cost is None or new_cost <= 0:
            continue
        _upd = await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": {
            "unit_cost": round(new_cost, 2),
            "base_unit_cost": round(new_cost, 2),
            "cost_basis": {
                "source": "interco_purchase",
                "interco_pair_id": pair_id,
                "interco_number": seller.get("number", ""),
                "previous_unit_cost": float(r.get("unit_cost") or 0),
                "at": now_iso(),
            },
            "updated_at": now_iso(),
        }})
        # T7 DIBAYAR (2026-06c): jejak nilai ditulis SESUDAH pembaruannya tersimpan.
        if _upd.modified_count:
            await _cost_history.record(
                r, round(new_cost, 2), "interco_purchase_revalue", actor=actor,
                ref_type="interco", ref_id=pair_id, ref_number=seller.get("number", ""))
        revalued += 1

    ts = now_iso()
    stamp: Dict[str, Any] = {"warehouse_transfer_status": "completed",
                             "updated_at": ts, "updated_by": actor}
    if seller.get("status") == "confirmed":
        stamp.update({"shipped_at": ts, "shipped_by": actor})
    if seller.get("status") in ("confirmed", "shipped"):
        stamp.update({"received_at": ts, "received_by": actor, "status": "received"})
    await db[COLL_ICT].update_many({"pair_id": pair_id}, {"$set": stamp})

    # Jurnal yang MENGIKUTI BARANG (HPP penjual + transit→persediaan pembeli),
    # lalu eliminasi grup dihitung ulang karena HPP-nya baru sekarang diketahui.
    gl_delivery = await post_gl_on_delivery(pair_id, actor, cost_override=cost_out)
    await _sync_group_elimination(pair_id)
    # FASE E-9 (E9.1) — barangnya kini BENAR-BENAR ada di gudang pembeli, jadi pesanan
    # pelanggan yang menunggu stok wajib terpenuhi OTOMATIS.
    fulfilled = await _auto_fulfill_after_interco_receipt(seller, transfer, actor)
    return {"revalued_rolls": revalued, "status": stamp.get("status", seller.get("status")),
            "pair_id": pair_id, "gl_delivery": gl_delivery, "auto_fulfill": fulfilled}


async def _auto_fulfill_after_interco_receipt(
        seller: Dict[str, Any], transfer: Dict[str, Any], actor: str) -> Dict[str, Any]:
    """E9.1 — penerimaan barang antar-PT memicu pemenuhan backorder pembeli.

    CACAT YANG DITUTUP: `auto_fulfill_backorders()` dulu hanya dipanggil dari
    penerimaan barang PO supplier (`routers/inbound_receiving.py`) dan pelepasan QC.
    Pembelian internal — yang justru DILAKUKAN UNTUK sebuah pesanan pelanggan —
    tidak memicu apa pun, jadi pesanan itu tetap "menunggu stok" walaupun barangnya
    sudah masuk gudang, dan Admin Sales harus mengalokasikan manual (padahal ia
    tidak punya isyarat bahwa barangnya sudah datang).

    Pemberitahuan dikirim ke Admin Sales — mengabari, bukan meminta persetujuan.
    Kegagalan di sini TIDAK boleh membatalkan perpindahan barang: dokumen & jurnal
    sudah sah, pemenuhan bisa diulang lewat alokasi manual.
    """
    buyer_entity = seller.get("buyer_entity_id") or ""
    out: Dict[str, Any] = {"orders_touched": 0, "orders_completed": 0,
                           "qty_fulfilled": 0.0, "products": []}
    if not buyer_entity:
        return out
    try:
        from services.backorder_service import _fill_order, auto_fulfill_backorders
    except Exception as exc:  # noqa: BLE001
        print(f"[interco] mesin pemenuhan backorder tak tersedia: {exc}")
        return out
    # UAT 24 Okt (P10.5) — roll yang dipindah UNTUK SO peminta dicadangkan ke SO itu DULU. Dulu semua masuk antrean
    # FIFO umum, sehingga SO lain yang lebih lama bisa "menyerobot" roll yang sengaja dipilih untuk pesanan ini.
    linked = transfer.get("linked_order_id") or seller.get("source_order_id") or ""
    linked_so = (await db.sales_orders.find_one({"id": linked, "entity_id": buyer_entity}, {"_id": 0})
                 if linked else None)
    for it in seller.get("items", []):
        pid = it.get("product_id")
        if not pid:
            continue
        if linked_so:
            moved = [r["id"] async for r in db.inventory_rolls.find(
                {"acquired.ref_id": transfer.get("id"), "owner_entity_id": buyer_entity, "product_id": pid,
                 "status": "available"}, {"_id": 0, "id": 1})]
            if moved:
                try:
                    r1 = await _fill_order(linked_so, pid, buyer_entity, actor_name=actor or "system",
                                           reason="Barang antar-PT tiba untuk SO peminta", roll_ids=moved)
                    if r1.get("got", 0) > 0:
                        out["orders_touched"] += 1
                        out["orders_completed"] += 1 if r1.get("completed") else 0
                        out["qty_fulfilled"] = round(out["qty_fulfilled"] + float(r1["got"]), 2)
                        out["linked_order_id"] = linked
                    linked_so = await db.sales_orders.find_one({"id": linked}, {"_id": 0})
                except Exception as exc:  # noqa: BLE001 — barang sudah pindah; sisanya lewat antrean umum
                    print(f"[interco] cadangan ke SO peminta {linked} gagal: {exc}")
        try:
            res = await auto_fulfill_backorders(pid, buyer_entity)
        except Exception as exc:  # noqa: BLE001 — barang sudah pindah; jangan dibatalkan
            print(f"[interco] pemenuhan otomatis {pid} gagal: {exc}")
            continue
        out["orders_touched"] += int(res.get("orders_touched") or 0)
        out["orders_completed"] += int(res.get("orders_completed") or 0)
        out["qty_fulfilled"] = round(out["qty_fulfilled"] +
                                     float(res.get("qty_fulfilled") or 0), 2)
        if res.get("orders_touched"):
            out["products"].append({"product_id": pid,
                                    "qty_fulfilled": float(res.get("qty_fulfilled") or 0)})
    if out["orders_touched"]:
        try:
            from services import notification_service as notif
            src = (seller.get("source_order_number") or "").strip()
            ekor = f" Pesanan pemicunya: {src}." if src else ""
            await notif.create_notification(
                notif_type="interco_receipt_auto_fulfilled",
                title=(f"Barang dari {seller.get('seller_entity_name', 'PT lain')} masuk — "
                       f"{out['orders_touched']} pesanan terpenuhi otomatis"),
                body=(f"Barang {seller.get('number', '')} dari "
                      f"{seller.get('seller_entity_name', '')} sudah diterima gudang "
                      f"({transfer.get('code', '')}). {out['orders_touched']} pesanan yang "
                      f"tadinya menunggu stok kini ter-reservasi "
                      f"({out['orders_completed']} terpenuhi penuh, total "
                      f"{out['qty_fulfilled']:,.2f} unit).{ekor} Tidak ada alokasi manual "
                      f"yang perlu Anda lakukan — silakan periksa lalu lanjutkan prosesnya."),
                severity="info", link="pending-so", entity_id=buyer_entity or None,
                recipient_role="sales_admin",
                ref=f"icfulfill:{seller.get('pair_id', '')}")
        except Exception as exc:  # noqa: BLE001
            print(f"[interco] notifikasi pemenuhan otomatis gagal: {exc}")
    return out


async def supply_for_order(order_id: str, buyer_entity_id: str = "") -> List[Dict[str, Any]]:
    """E9.2 — janji pasokan ANTAR-PT untuk satu pesanan pelanggan.

    Dipakai layar pesanan supaya Admin Sales tahu "kekurangannya diambil dari PT mana,
    lewat dokumen apa". Hanya transaksi yang MEMANG menyebut pesanan ini
    (`source_order_id`) yang dilaporkan — sistem tidak menebak-nebak: janji yang tidak
    tertaut cukup tampil di Papan Pending SO sebagai pasokan tingkat produk.
    """
    if not order_id:
        return []
    q: Dict[str, Any] = {"role": "buyer", "source_order_id": order_id}
    if buyer_entity_id:
        q["buyer_entity_id"] = buyer_entity_id
    docs = await db[COLL_ICT].find(q, {
        "_id": 0, "id": 1, "number": 1, "status": 1, "items": 1, "doc_date": 1,
        "due_date": 1, "seller_entity_id": 1, "seller_entity_name": 1,
        "warehouse_transfer_status": 1, "warehouse_transfer_code": 1,
        "source_request_number": 1, "pair_id": 1,
    }).sort("created_at", 1).to_list(200)
    out: List[Dict[str, Any]] = []
    for d in docs:
        out.append({
            "interco_id": d.get("id", ""),
            "pair_id": d.get("pair_id", ""),
            "number": d.get("number", ""),
            "status": d.get("status", ""),
            "status_label": STATUS_LABEL.get(d.get("status", ""), d.get("status", "")),
            "from_entity_id": d.get("seller_entity_id", ""),
            "from_entity_name": d.get("seller_entity_name", ""),
            "eta": d.get("due_date") or d.get("doc_date") or "",
            "warehouse_transfer_status": d.get("warehouse_transfer_status", ""),
            "warehouse_transfer_code": d.get("warehouse_transfer_code", ""),
            "source_request_number": d.get("source_request_number", ""),
            "goods_arrived": d.get("status") in ("received", "invoiced", "settled"),
            "items": [{
                "product_id": it.get("product_id", ""),
                "sku": it.get("sku", ""),
                "product_name": it.get("product_name", ""),
                "quantity": round(float(it.get("quantity") or 0), 2),
                "unit": it.get("unit", ""),
            } for it in d.get("items", [])],
        })
    return out
