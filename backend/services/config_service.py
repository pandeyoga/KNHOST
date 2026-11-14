"""Config service (Fase 1A) — Configuration Foundation.

Prinsip user: SEMUA CONFIGURABLE, TIDAK ADA HARDCODE.
- `system_settings`  (prefix set_)    : pengaturan global + override per-entitas
- `payment_terms`    (prefix pterm_)  : term pembayaran (tunai/kredit/DP/bertahap)
- `approval_rules`   (prefix aprule_) : matriks approval per dokumen/entitas/threshold

config_service menyediakan resolver "effective settings" (global di-override entitas),
kalkulasi pajak (PPN excluded/included), dan evaluasi approval.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso, new_id, DEFAULT_ENTITY_ID

GLOBAL_SCOPE = "global"


def _reg_default(key: str) -> Any:
    """KF-T2 (KF-06) — cadangan kode = bawaan registry (`config_registry.default_of`). Diimpor lambat (pola
    `saring_bagi_pembaca`) supaya memuat modul ini tidak ikut memuat seluruh katalog registry."""
    from config_registry import default_of
    return default_of(key)


# Default global settings (seed sekali, lalu editable dari Admin → Pengaturan)
DEFAULT_GLOBAL_SETTINGS: Dict[str, Any] = {
    # LN-083 — ASUMSI sementara (menunggu owner KLR-08/KLR-09); nilai dapat diubah di Pengaturan.
    # KF-T2 — kunci `returns.*` kini di registry (`config_catalog_ops.py`). Tabel harga per grade TIDAK ditulis di sini:
    # bawaannya hanya di registry (`returns.grade_price_factors`), supaya tidak ada salinan kedua yang daun-daunnya
    # (`A`, `B1`, …) tidak bisa dicocokkan gate wiring dengan pembacanya.
    "returns": {"customer_window_days": 21, "supplier_window_days": 21,
                "bill_first": True,
                "supplier_reminder_days": 3},
    # LN-024 — pembayaran antar-PT: penuh per transaksi, tanpa netting; KLX-03: cutoff/tanggal bayar/acuan configurable.
    # KF-T2 — "belum diatur" ditulis sama dengan bawaan registry (0 / ""), bukan None; artinya tidak berubah.
    "interco_payment": {"allow_netting": False, "require_full_payment": True,
                        "cutoff_day": 0, "payment_day": 0, "basis": "", "reminder_days": 3},
    "tax": {
        "ppn_rate": 12.0,            # % — tarif resmi UU HPP (sejak 2025)
        # F-10 Coretax — DPP Nilai Lain = 11/12 × harga jual (PMK 131/2024) untuk barang
        # non-mewah → PPN efektif 11%. Configurable per entitas via override scope.
        "dpp_nilai_lain": True,
        "ppn_mode": "excluded",     # excluded = ditambah saat invoice | included
        "efaktur_enabled": True,    # PKP terbit Faktur Pajak
        # EPIC 7 — Pajak: butir PPh/withholding CONFIGURABLE per tax-plan perusahaan.
        # basis: "payroll" (otomatis dari payroll pph21) | "omzet" (rate% × peredaran)
        #        | "manual" (rekam DPP → rate% × DPP). enabled → tampil di rekap.
        "pph_items": [
            {"code": "pph21", "name": "PPh 21 — Karyawan", "rate": 0.0, "basis": "payroll", "enabled": True},
            {"code": "pph23", "name": "PPh 23 — Jasa/Sewa", "rate": 2.0, "basis": "manual", "enabled": True},
            {"code": "pph_final_pp23", "name": "PPh Final UMKM (PP23)", "rate": 0.5, "basis": "omzet", "enabled": False},
        ],
    },
    "finance": {
        "base_currency": "IDR",
        "fiscal_year_end_month": 12,
        "default_payment_term_code": "NET30",
    },
    "sales": {
        "quotation_enabled": False,
        "allow_partial_shipment": True,
        # Diskon manual DIHAPUS — potongan harga hanya via Harga Khusus (special-price).
        "allow_order_discount": False,
        "allow_item_discount": False,
        # AS-01 (catatan demo 2026-09) — persetujuan NILAI manajer setelah Admin Sales
        # DITIADAKAN: alur = Sales membuat → Admin Sales verifikasi → Admin Sales
        # konfirmasi. Persetujuan KREDIT & HARGA KHUSUS jalurnya terpisah dan TETAP.
        "require_so_validation": False,
    },
    "inventory": {
        "default_uom": "meter",
        "min_cut_qty": 0.5,
        # Stock Analytics — K-05 (keputusan pemilik 26 Okt 2026): kelas laju jual HANYA dari moving average
        # penjualan (SO hidup) dengan peringkat persentil per satuan. Ambang lama fast/slow_max_days (hari sejak
        # jual terakhir) tidak dipakai lagi.
        "stock_analytics": {
            "velocity_window_days": 90,  # jendela moving average qty terjual per hari
            "best_seller_pct": 20,       # persen teratas (per satuan) = Best seller
            "slow_moving_pct": 20,       # persen terbawah di antara SKU terjual = Slow moving
            "new_sku_age_days": 90,      # SKU berumur < N hari = Baru (tidak diperingkat)
        },
        # Reorder/ROP (Fase 5) — usulan ROP dinamis berbasis kecepatan jual.
        # ROP disarankan = rata2 jual harian × (lead_time + safety_days).
        "reorder": {
            "velocity_window_days": 90,
            "safety_days": 7,
        },
        "intercompany_transfer_required": True,  # KN_15 D-? — jual stok entitas lain wajib transfer
    },
    # Fase 3 — Purchasing (Procurement)
    "purchasing": {
        "receive_tolerance_percent": 2.0,   # toleransi qty terima vs PO (benang ±2%)
        "require_supplier_master": False,    # True = PO wajib pilih supplier master
        "qc_on_receipt": True,               # Depth #3a — barang masuk → karantina dulu (inspeksi QC)
        "price_deviation_approval_percent": 10.0,  # Depth #3 — harga PO > price-list +X% → wajib approval
        "allow_item_discount": True,         # P0-1 — izinkan diskon per item pada PO
        "allow_order_discount": True,        # P0-1 — izinkan diskon level order pada PO
        "bill_qty_tolerance_percent": 0.0,   # P0-2 — toleransi qty tagih vs diterima/dipesan (3-way)
        "bill_price_tolerance_percent": 5.0, # P0-2 — toleransi harga bill vs harga PO
    },
    # Fase 6.2 (P1) — QC 4-Point Inspection (grade dari poin defect; configurable)
    "qc": {
        "grade_thresholds": {"a_max": 20.0, "b_max": 40.0},  # poin ≤a_max=A, ≤b_max=B, >b_max=C
        "four_point_enabled": True,          # aktifkan inspeksi 4-point per roll saat QC
    },
    # Fase 7.1 (P2) — Multi-Level Sequential Approval (tingkat tambahan di atas L1 dari approval_rules)
    "approval": {
        # extra_levels[doc_type] = level tambahan (L2, L3, …) yang aktif bila amount ≥ min_amount.
        # Default PO: ≥500jt butuh persetujuan Direksi (role admin) SETELAH Manager (L1).
        "extra_levels": {
            "purchase_order": [
                {"min_amount": 500000000, "role": "admin", "label": "Direksi"},
            ],
        },
    },
    # Sub-fase 1.7 — Allocation Policy (KN_15 §6.0) — CONFIGURABLE + CLARITY
    "allocation": {
        "mode": "auto",                                            # auto | assisted | manual
        "roll_pick_sales": True,   # bila False: role SALES tidak boleh pilih roll saat checkout
        "makloon_reserve_mode": "block",   # W2-REQ-07 — block | approve (stok cadangan makloon)
        "priority_order": ["owner", "lot", "location", "roll_efficiency"],  # owner selalu HARD #1
        "lot_mode": "prefer_single",                               # prefer_single | strict_single | allow_mixed
        "lot_selection": "fifo",                                   # fifo (fefo = alias lama) | smallest_fit | largest_fit
        "location_pref": "single_warehouse",                       # single_warehouse | nearest_customer | fewest_splits
        "allow_intercompany": True,
        "allow_partial": True,
        "dye_lot_strict": False,                                   # P0-4 — paksa 1 dye lot (tekstil)
    },
    # EPIC 0 (F4) — UI feature flags (config-driven; dipakai sidebar "Segera Hadir")
    "ui": {
        "show_coming_soon": True,        # tampilkan grup "Segera Hadir" di sidebar
        "coming_soon_collapsed": True,   # grup "Segera Hadir" default ter-collapse
    },
    # EPIC 0 (F5) — Role-home registry (landing view per role; configurable)
    "role_home": {
        "admin": "admin",
        "manager": "reports",
        "sales": "sales",
        "warehouse": "operations",
    },
    # EPIC 7A — AR / Piutang aging + denda (late fee) — ESTIMASI informasional (tidak posting)
    "ar": {
        "denda_rate_pct_per_month": 2.0,   # % per bulan (prorata per 30 hari) atas saldo overdue
        "grace_days": 0,                   # masa tenggang sebelum denda dihitung
        "aging_buckets": [30, 60, 90],     # ambang hari aging (1-30 / 31-60 / 61-90 / 90+)
    },
    # EPIC 4 — Incentive Engine v2 (strategy + mekanik diskon default + margin cap)
    "commission": {
        "strategy": "per_sku",            # per_sku (v2, default) | achievement_tiered (arsip)
        "incentive_unit": "meter",        # UOM dasar per_unit_amount
        "default_margin_cap_pct": 50.0,   # komisi per-line ≤ X% margin line (margin-aware, EPIC3 WAC)
        "discount_threshold_type": "pct", # pct | rp_per_unit — basis ambang diskon
        "discount_threshold": 10.0,       # ambang diskon line (>= → mekanik aktif)
        "discount_mechanic": "tier_factor",  # tier_factor | potong_rp | cutoff
        "discount_factor": 0.5,           # tier_factor: komisi × faktor bila diskon > ambang
        "discount_potong_rp": 0.0,        # potong_rp: kurangi per_unit_amount (Rp/unit) bila > ambang
    },
}

DEFAULT_PAYMENT_TERMS: List[Dict[str, Any]] = [
    {"code": "CASH",  "name": "Tunai / POS",          "type": "cash",        "net_days": 0,  "dp_percent": 0,  "installment_count": 0, "sort": 1},
    {"code": "NET7",  "name": "Kredit NET 7 Hari",    "type": "credit",      "net_days": 7,  "dp_percent": 0,  "installment_count": 0, "sort": 2},
    {"code": "NET14", "name": "Kredit NET 14 Hari",   "type": "credit",      "net_days": 14, "dp_percent": 0,  "installment_count": 0, "sort": 3},
    {"code": "NET30", "name": "Kredit NET 30 Hari",   "type": "credit",      "net_days": 30, "dp_percent": 0,  "installment_count": 0, "sort": 4},
    {"code": "DP50",  "name": "DP 50% + Pelunasan",   "type": "dp",          "net_days": 14, "dp_percent": 50, "installment_count": 0, "sort": 5},
    {"code": "INST3", "name": "Bertahap 3x",          "type": "installment", "net_days": 30, "dp_percent": 0,  "installment_count": 3, "sort": 6},
    # K-4 (feedback klien 2026-09) — termin yang dipakai klien: CBD & tempo 2/3 bulan.
    {"code": "CBD",   "name": "CBD — Bayar Sebelum Kirim", "type": "cash",     "net_days": 0,  "dp_percent": 100, "installment_count": 0, "sort": 7},
    {"code": "NET60", "name": "Tempo 2 Bulan (NET 60)",  "type": "credit",      "net_days": 60, "dp_percent": 0,  "installment_count": 0, "sort": 8},
    {"code": "NET90", "name": "Tempo 3 Bulan (NET 90)",  "type": "credit",      "net_days": 90, "dp_percent": 0,  "installment_count": 0, "sort": 9},
]

DEFAULT_APPROVAL_RULES: List[Dict[str, Any]] = [
    # AS-01 (2026-09) — SO tidak lagi menuntut persetujuan NILAI manajer pada nominal
    # berapa pun (bawaan). Pemilik bisa memasang ambang lagi di Pusat Pengaturan →
    # Persetujuan & Ambang. Kredit & harga khusus tidak lewat tabel ini.
    {"doc_type": "sales_order",    "entity_id": "all", "min_amount": 0,         "max_amount": None,       "required_role": "",        "sort": 1},
    # KP-T3 — dua baris `discount` dibuang: tidak ada pemanggil penilai ber-`doc_type` itu (potongan harga diatur lewat
    # Harga Khusus). Data lama dipensiunkan skrip `scripts/migrate_kpt3_aturan_persetujuan.py`.
    {"doc_type": "purchase_order", "entity_id": "all", "min_amount": 0,         "max_amount": 100000000, "required_role": "",        "sort": 1},
    {"doc_type": "purchase_order", "entity_id": "all", "min_amount": 100000000, "max_amount": None,       "required_role": "manager", "sort": 2},
    {"doc_type": "purchase_requisition", "entity_id": "all", "min_amount": 0,         "max_amount": 50000000,  "required_role": "",        "sort": 1},
    {"doc_type": "purchase_requisition", "entity_id": "all", "min_amount": 50000000,  "max_amount": None,       "required_role": "manager", "sort": 2},
]


# ── Seed defaults (idempotent) ───────────────────────────────────────────────

async def seed_config_defaults() -> Dict[str, int]:
    created = {"settings": 0, "payment_terms": 0, "approval_rules": 0}
    if await db.system_settings.count_documents({"scope": GLOBAL_SCOPE}) == 0:
        await db.system_settings.insert_one({
            "id": new_id("set"), "scope": GLOBAL_SCOPE,
            **DEFAULT_GLOBAL_SETTINGS,
            "created_at": now_iso(), "updated_at": now_iso(),
        })
        created["settings"] = 1
    if await db.payment_terms.count_documents({}) == 0:
        await db.payment_terms.insert_many([
            # FASE E-4 (E4.3) — lahir sebagai baris GLOBAL (`entity_id="all"`): berlaku
            # untuk semua badan usaha sampai ada yang menimpanya dengan "Buat khusus".
            {"id": new_id("pterm"), "entity_id": "all", **t, "active": True,
             "created_at": now_iso(), "updated_at": now_iso()} for t in DEFAULT_PAYMENT_TERMS
        ])
        created["payment_terms"] = len(DEFAULT_PAYMENT_TERMS)
    else:
        # K-4 — basis data lama: tambahkan termin bawaan yang belum ada (idempoten, tidak menimpa).
        have = {t["code"] for t in await db.payment_terms.find({"entity_id": "all"}, {"_id": 0, "code": 1}).to_list(200)}
        missing = [t for t in DEFAULT_PAYMENT_TERMS if t["code"] not in have]
        if missing:
            await db.payment_terms.insert_many([
                {"id": new_id("pterm"), "entity_id": "all", **t, "active": True,
                 "created_at": now_iso(), "updated_at": now_iso()} for t in missing])
            created["payment_terms"] = len(missing)
    if await db.approval_rules.count_documents({}) == 0:
        await db.approval_rules.insert_many([
            {"id": new_id("aprule"), "is_percent": r.get("is_percent", False), "active": True,
             "created_at": now_iso(), "updated_at": now_iso(),
             **{k: v for k, v in r.items() if k != "is_percent"}} for r in DEFAULT_APPROVAL_RULES
        ])
        created["approval_rules"] = len(DEFAULT_APPROVAL_RULES)
    return created


# ── Effective settings (global di-override per-entitas) ──────────────────────

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


#: KF-T1 — jalur dokumen pengaturan yang belum ada di registry tetapi dibaca layar semua pengguna. KF-T2 — `returns` dan
#: `interco_payment` dicabut: kuncinya kini di registry dengan `sensitif_baca=False`.
BUKA_SEMENTARA = ("scope", "tax.is_pkp")


def saring_bagi_pembaca(doc: Dict[str, Any]) -> Dict[str, Any]:
    """KF-T1 — salinan dokumen pengaturan yang hanya memuat daun TIDAK sensitif (untuk pengguna tanpa
    `settings.view`): daun yang dicakup entri registry ber-`sensitif_baca == False`, atau jalurnya di
    `BUKA_SEMENTARA`. Wadah yang menjadi kosong dibuang."""
    import config_registry as registry

    def buka(path: str) -> bool:
        if any(path == p or path.startswith(p + ".") for p in BUKA_SEMENTARA):
            return True
        entry = registry.covers(path)
        return bool(entry) and entry.get("sensitif_baca") is False

    def jalan(node: Any, prefix: str) -> Any:
        if isinstance(node, dict) and not (prefix and buka(prefix)):
            out = {}
            for k, v in node.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                hasil = jalan(v, path)
                if hasil is not _BUANG:
                    out[k] = hasil
            return out if out else _BUANG
        return node if (prefix and buka(prefix)) else _BUANG

    hasil = jalan(doc or {}, "")
    return {} if hasil is _BUANG else hasil


_BUANG = object()


async def get_global_settings() -> Dict[str, Any]:
    # KF-T3 (KF-09) — perubahan berjadwal yang sudah jatuh tempo diterapkan dulu (nol kueri bila tidak ada jadwal), supaya
    # semua pembaca lama (`get_effective_settings` dkk.) tidak tertinggal sampai layar Pengaturan dibuka.
    from services.config_resolver import ensure_due_applied
    await ensure_due_applied()
    doc = await db.system_settings.find_one({"scope": GLOBAL_SCOPE}, {"_id": 0})
    if not doc:
        await seed_config_defaults()
        doc = await db.system_settings.find_one({"scope": GLOBAL_SCOPE}, {"_id": 0})
    return doc or {"scope": GLOBAL_SCOPE, **DEFAULT_GLOBAL_SETTINGS}


async def get_effective_settings(entity_id: Optional[str] = None) -> Dict[str, Any]:
    stored = await get_global_settings()
    # Deep-merge default kode (sumber kebenaran key terbaru) ← stored global (nilai user menang).
    # Ini memastikan key default baru (mis. purchasing.price_deviation_approval_percent)
    # otomatis tersedia & configurable walau doc lama belum memuatnya.
    default_sections = {k: v for k, v in DEFAULT_GLOBAL_SETTINGS.items() if isinstance(v, dict)}
    stored_sections = {k: v for k, v in stored.items() if isinstance(v, dict)}
    sections = _deep_merge(default_sections, stored_sections)
    if entity_id and entity_id != "all":
        override = await db.system_settings.find_one({"scope": entity_id}, {"_id": 0})
        if override:
            ov_sections = {k: v for k, v in override.items() if isinstance(v, dict)}
            sections = _deep_merge(sections, ov_sections)
        # entitas PKP/non-PKP mempengaruhi pajak efektif
        entity = await db.business_entities.find_one({"id": entity_id}, {"_id": 0})
        if entity:
            is_pkp = (entity.get("default_tax_mode") == "ppn")
            sections.setdefault("tax", {})
            sections["tax"] = dict(sections.get("tax", {}))
            sections["tax"]["is_pkp"] = is_pkp
            if not is_pkp:
                sections["tax"]["ppn_rate"] = 0.0
                sections["tax"]["efaktur_enabled"] = False
    else:
        sections.setdefault("tax", {})
        sections["tax"] = dict(sections.get("tax", {}))
        sections["tax"]["is_pkp"] = True
    return {"scope": entity_id or "all", **sections}


async def default_payment_term_code(entity_id: Optional[str] = None) -> str:
    """KF-T3 (KP-11) — termin bawaan pesanan baru UNTUK PT ITU (lapisan PT Pusat Pengaturan berlaku).

    Dulu pesanan membaca dokumen grup `system_settings` langsung, sehingga nilai khusus PT diabaikan."""
    from services.config_resolver import value_of
    ent = entity_id if entity_id and entity_id != "all" else ""
    return str(await value_of("finance.default_payment_term_code", {"entity_id": ent})
               or _reg_default("finance.default_payment_term_code"))


# ── Kalkulasi pajak (PPN) ────────────────────────────────────────────────────

async def compute_tax(subtotal: float, entity_id: Optional[str] = None,
                      mode_override: Optional[str] = None, *, at: Optional[datetime] = None,
                      snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """PPN per entitas. F-10 Coretax: dpp_nilai_lain=True → DPP = pembilang/penyebut × harga jual,
    PPN = tarif × DPP (efektif tarif × pembilang/penyebut dari harga jual).
    `mode_override` ("included"/"excluded") memaksa harga termasuk/belum termasuk PPN (PB-01).

    TX-T1 — `snapshot` diberikan → dihitung DARI POTRET dokumen (hitung ulang dokumen yang sudah ada); selain itu dari
    aturan PT pada waktu `at` (`tax_config_service.tax_settings`: `tax.ppn_rate`, `tax.dpp_nilai_lain`, `tax.ppn_mode`,
    faktor & cara bulat; bawaan: sekarang). Dengan kunci pada bawaannya hasilnya persis sama dengan sebelum unit ini."""
    from services import tax_config_service as tcs
    aturan = dict(snapshot) if snapshot else tcs.potret(await tcs.tax_settings(entity_id or "", at))
    mode = aturan["ppn_mode"]
    if (mode_override or "").strip().lower() in ("included", "excluded"):
        mode = mode_override.strip().lower()
    return ppn_breakdown(subtotal, aturan["ppn_rate"], mode, aturan["is_pkp"], aturan["dpp_nilai_lain"], aturan=aturan)


def ppn_breakdown(subtotal: float, rate: float, mode: str, is_pkp: bool, use_nl: bool,
                  aturan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """KF-T4 (KF-UX-04) — rumus PPN MURNI: dipakai `compute_tax` (mesin) dan "Coba dulu" Pengaturan (simulator `tax`),
    supaya keduanya selalu memberi angka yang sama. F-10 Coretax: `use_nl` → DPP = pembilang/penyebut × harga jual.

    TX-T1 — faktor dan cara bulat dari `aturan` (potret `tax_snapshot`); tanpa `aturan` = aturan sebelum unit ini
    (11/12, dua desimal — `tax_config_service.potret_lama`). Satu fungsi bulat: `tax_config_service.round_money`."""
    from services.tax_config_service import potret_lama, round_money
    a = aturan or potret_lama({"ppn_rate": rate, "ppn_mode": mode})
    satuan = a["pembulatan_satuan"]
    rate = float(rate or 0)
    subtotal = round(float(subtotal or 0), 2)
    if not is_pkp or rate <= 0:
        return {"ppn_rate": 0.0, "effective_rate": 0.0, "dpp_nilai_lain": False,
                "ppn_mode": mode, "is_pkp": is_pkp, "dpp": subtotal, "harga_jual": subtotal,
                "ppn_amount": 0.0, "grand_total": subtotal}
    dpp_factor = int(a["dpp_pembilang"]) / int(a["dpp_penyebut"]) if use_nl else 1.0
    eff_rate = rate * dpp_factor
    if mode == "included":
        if satuan == "dua_desimal":   # urutan sebelum TX-T1 (harga jual dulu), persis
            harga_jual = round_money(subtotal / (1 + eff_rate / 100), satuan)
            ppn = round(subtotal - harga_jual, 2)
        else:                         # PPN dulu supaya PPN bulat dan harga jual + PPN = subtotal
            ppn = round_money(subtotal - subtotal / (1 + eff_rate / 100), satuan)
            harga_jual = round(subtotal - ppn, 2)
        grand = subtotal
    else:  # excluded (default)
        harga_jual = subtotal
        ppn = round_money(subtotal * eff_rate / 100, satuan)
        grand = round(subtotal + ppn, 2)   # total = harga + PPN (D5: tidak dibulatkan lagi)
    dpp = round_money(harga_jual * dpp_factor, satuan)
    return {"ppn_rate": rate, "effective_rate": round(eff_rate, 4), "dpp_nilai_lain": use_nl,
            "ppn_mode": mode, "is_pkp": is_pkp, "dpp": dpp, "harga_jual": harga_jual,
            "ppn_amount": ppn, "grand_total": grand}


async def migrate_tax_regime() -> None:
    """F-10 — migrasi rezim PPN 11% flat → 12% + DPP Nilai Lain 11/12 (idempotent).
    Rupiah tak berubah (efektif tetap 11%). Scope dgn tarif custom → flag False eksplisit
    agar default baru tidak mengubah perilakunya."""
    await db.system_settings.update_many(
        {"tax.ppn_rate": 11.0, "tax.dpp_nilai_lain": {"$exists": False}},
        {"$set": {"tax.ppn_rate": 12.0, "tax.dpp_nilai_lain": True, "updated_at": now_iso()}})
    await db.system_settings.update_many(
        {"tax": {"$exists": True}, "tax.dpp_nilai_lain": {"$exists": False}},
        {"$set": {"tax.dpp_nilai_lain": False, "updated_at": now_iso()}})


# ── Evaluasi approval (matriks configurable) ─────────────────────────────────

# ── KP-T3 — satu pemilih aturan untuk mesin DAN layar "Jenjang yang berlaku" ──────────────────────────────────────────
#: Jenis dokumen yang benar-benar dinilai mesin (pemanggil `evaluate_approval`/`build_approval_chain`). `discount`
#: dipensiunkan KP-T3: tidak ada pemanggil ber-`doc_type` itu; potongan harga diatur lewat Harga Khusus.
APPROVAL_DOC_TYPES: Dict[str, str] = {
    "sales_order": "Pesanan Penjualan",
    "purchase_order": "Pesanan Pembelian",
    "purchase_requisition": "Permintaan Pembelian",
}
_INF = float("inf")


async def approval_pool(doc_type: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """KP-T3 — aturan yang dinilai untuk (jenis dokumen, PT): aturan aktif urut `sort`; aturan khusus PT bila ada
    SATU saja, selain itu aturan grup. Logikanya persis yang dulu ada di dalam `evaluate_approval` (mesin tidak
    berubah); layar memakai fungsi yang sama. KP-T4 memakainya sebagai sumber migrasi tabel kebijakan."""
    rules = await db.approval_rules.find(
        {"doc_type": doc_type, "active": True}, {"_id": 0}
    ).sort("sort", 1).to_list(200)
    scoped = [r for r in rules if r.get("entity_id") == entity_id] if entity_id else []
    group = [r for r in rules if r.get("entity_id") in (None, "all")]
    if scoped:
        return {"source": "grup" if entity_id == "all" else "pt", "rules": scoped, "group_rules": group}
    return {"source": "grup" if group else "kosong", "rules": group, "group_rules": group}


def _bounds(rule: Dict[str, Any]) -> tuple:
    lo = float(rule.get("min_amount", 0) or 0)
    hi = rule.get("max_amount")
    return lo, (float(hi) if hi is not None else _INF)


def _rule_for(rules: List[Dict[str, Any]], amount: float) -> Optional[Dict[str, Any]]:
    """Aturan pertama (urutan `rules`) yang `min_amount ≤ nilai < max_amount`; tidak ada → None."""
    amount = float(amount or 0)
    for r in rules:
        lo, hi = _bounds(r)
        if lo <= amount < hi or (amount == hi == _INF):
            return r
    return None


def required_role_for(rules: List[Dict[str, Any]], amount: float) -> str:
    """KP-T3 — peran yang dituntut untuk satu nilai menurut `rules`; tidak ada aturan yang cocok → `""`."""
    r = _rule_for(rules, amount)
    return (r.get("required_role") or "") if r else ""


def validate_extra_levels(value: Any) -> Any:
    """KP-T3 — pemeriksa isi `approval.extra_levels` (dipanggil `config_resolver.set_value` untuk kunci ini):
    dikelompokkan per jenis dokumen; tiap baris ber-`role` peran yang dikenal dan `min_amount` angka ≥ 0.
    Melempar `ValueError` berpesan siap tampil."""
    import math
    from role_registry import is_role
    if not isinstance(value, dict):
        raise ValueError("Jenjang tambahan harus dikelompokkan per jenis dokumen.")
    for doc_type, rows in value.items():
        if not isinstance(rows, list):
            jenis = APPROVAL_DOC_TYPES.get(doc_type, doc_type)
            raise ValueError(f"Jenjang tambahan {jenis} harus berupa daftar baris.")
        for n, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f"Jenjang tambahan baris {n}: isinya tidak sah.")
            role = str(row.get("role") or "").strip()
            if not role:
                raise ValueError(f"Jenjang tambahan baris {n}: peran belum dipilih.")
            if not is_role(role):
                raise ValueError(f"Jenjang tambahan baris {n}: peran “{role}” tidak ada.")
            raw = row.get("min_amount", 0)
            try:
                num = float(raw if raw not in (None, "") else 0)
            except (TypeError, ValueError):
                num = float("nan")
            if isinstance(raw, bool) or not math.isfinite(num) or num < 0:
                raise ValueError(f"Jenjang tambahan baris {n}: nilai minimal harus angka ≥ 0.")
    return value


def _rp(x: float) -> str:
    v = round(float(x or 0), 2)
    if v == int(v):
        return "Rp" + f"{int(v):,}".replace(",", ".")
    return "Rp" + f"{v:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _rentang(a: float, b: float) -> str:
    return f"≥ {_rp(a)}" if b == _INF else f"{_rp(a)} s/d < {_rp(b)}"


def _num(x: float) -> Any:
    """Batas untuk JSON: tak terhingga → None; bilangan bulat → int."""
    if x == _INF:
        return None
    return int(x) if float(x) == int(x) else x


def _segments(rule_sets: List[List[Dict[str, Any]]]) -> List[tuple]:
    """Ruas [a, b) di antara semua batas min/max himpunan aturan (mulai 0, berakhir tak terhingga)."""
    pts = {0.0, _INF}
    for rules in rule_sets:
        for r in rules:
            lo, hi = _bounds(r)
            pts.update((max(lo, 0.0), hi))
    pts = sorted(pts)
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _merge(segs: List[tuple]) -> List[tuple]:
    """Gabung ruas bersebelahan yang membawa kunci sama: [(a, b, kunci)] → [(a, b, kunci)]."""
    out: List[list] = []
    for a, b, key in segs:
        if out and out[-1][1] == a and out[-1][2] == key:
            out[-1][1] = b
        else:
            out.append([a, b, key])
    return [tuple(x) for x in out]


def _tier_warnings(doc_type: str, source: str, rules: List[Dict[str, Any]],
                   group_rules: List[Dict[str, Any]], extra_levels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from role_registry import role_label
    warnings: List[Dict[str, Any]] = []
    if not rules:
        return warnings
    segs = _segments([rules])
    cover = [(a, b, sum(1 for r in rules if _bounds(r)[0] <= a < _bounds(r)[1])) for a, b in segs]
    for a, b, _ in _merge([(a, b, True) for a, b, n in cover if n == 0]):
        warnings.append({"code": "celah", "from_amount": _num(a), "to_amount": _num(b),
                         "message": (f"Nilai {_rentang(a, b)} tidak tercakup aturan, sehingga lolos tanpa "
                                     "persetujuan.")})
    for a, b, _ in _merge([(a, b, True) for a, b, n in cover if n > 1]):
        warnings.append({"code": "tumpang_tindih", "from_amount": _num(a), "to_amount": _num(b),
                         "message": (f"Rentang {_rentang(a, b)} tercakup lebih dari satu aturan. Yang dipakai "
                                     "aturan berurutan paling kecil.")})
    if source == "pt" and group_rules:
        longgar = []
        for a, b in _segments([rules, group_rules]):
            g_role = required_role_for(group_rules, a)
            if g_role and not required_role_for(rules, a):
                longgar.append((a, b, g_role))
        jenis = APPROVAL_DOC_TYPES.get(doc_type, doc_type)
        for a, b, g_role in _merge(longgar):
            warnings.append({"code": "lebih_longgar_dari_grup", "from_amount": _num(a), "to_amount": _num(b),
                             "message": (f"PT ini punya aturan sendiri, jadi aturan grup untuk {jenis} tidak "
                                         f"dipakai. Akibatnya nilai {_rentang(a, b)} lolos tanpa persetujuan, padahal "
                                         f"aturan grup menuntut {role_label(g_role)}.")})
    for t in rules:
        role = t.get("required_role") or ""
        if role and not _role_known(role):
            lo, hi = _bounds(t)
            warnings.append({"code": "peran_tak_dikenal", "from_amount": _num(lo), "to_amount": _num(hi),
                             "message": (f"Aturan ini menunjuk peran “{role}” yang tidak ada. Mesin "
                                         "memperlakukannya sama dengan Manajer.")})
    for lv in extra_levels:
        if not lv["role_known"]:
            warnings.append({"code": "peran_tak_dikenal", "from_amount": lv["min_amount"], "to_amount": None,
                             "message": (f"Jenjang tambahan ≥ {_rp(lv['min_amount'] or 0)} menunjuk peran "
                                         f"“{lv['role']}” yang tidak ada. Mesin memperlakukannya sama dengan "
                                         "Manajer.")})
    return warnings


def _role_known(role: str) -> bool:
    from role_registry import is_role
    return not role or is_role(role)


def role_view(role: str) -> Dict[str, Any]:
    """KP-T3 — label peran penyetuju untuk layar: kosong = "Tanpa persetujuan"; peran tak dikenal ditandai."""
    from role_registry import role_label
    role = role or ""
    return {"required_role_label": role_label(role) if role else "Tanpa persetujuan",
            "role_known": _role_known(role)}


async def effective_tiers(doc_type: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """KP-T3 — jenjang yang SUNGGUH berlaku untuk (jenis dokumen, PT), dari sumber yang sama dengan mesin:
    tingkat 1 = `approval_pool` (seperti `evaluate_approval`); tingkat 2+ = `approval.extra_levels` efektif PT
    (seperti `build_approval_chain`, hanya aktif di atas tingkat 1). Ditambah peringatan celah, tumpang tindih,
    aturan PT yang lebih longgar dari grup, dan peran tak dikenal."""
    from role_registry import role_label
    from services.config_resolver import resolve
    ent = entity_id if entity_id and entity_id != "all" else None
    pool = await approval_pool(doc_type, ent)
    rules = pool["rules"]
    tiers = [{"level": 1, "rule_id": r.get("id"), "sort": r.get("sort"),
              "min_amount": _num(_bounds(r)[0]), "max_amount": _num(_bounds(r)[1]),
              "required_role": r.get("required_role") or "", **role_view(r.get("required_role") or "")}
             for r in rules]

    settings = await get_effective_settings(ent)
    raw_extra = (((settings.get("approval") or {}).get("extra_levels") or {}).get(doc_type) or [])
    res = await resolve("approval.extra_levels", {"entity_id": ent or ""})
    ex_src = "grup"
    if res["source_layer"] in ("entity", "legacy_entity") and doc_type in (res.get("value") or {}):
        ex_src = "pt"   # lapisan PT menimpa daftar jenis dokumen ini; jenis lain tetap mewarisi grup
    extra_levels: List[Dict[str, Any]] = []
    for lv in raw_extra if isinstance(raw_extra, list) else []:
        if not isinstance(lv, dict):
            continue
        role = str(lv.get("role") or "").strip()
        if not role:
            continue    # mesin melewati baris tanpa peran
        try:
            min_amt = float(lv.get("min_amount", 0) or 0)
        except (TypeError, ValueError):
            min_amt = 0.0
        extra_levels.append({"level": len(extra_levels) + 2, "min_amount": _num(min_amt), "role": role,
                             "role_label": role_label(role), "label": lv.get("label") or role.title(),
                             "role_known": _role_known(role), "source": ex_src})

    unused = []
    if pool["source"] == "pt":
        unused = [{"rule_id": r.get("id"), "min_amount": _num(_bounds(r)[0]), "max_amount": _num(_bounds(r)[1]),
                   "required_role": r.get("required_role") or "",
                   "required_role_label": role_view(r.get("required_role") or "")["required_role_label"]}
                  for r in pool["group_rules"]]
    return {"doc_type": doc_type, "label": APPROVAL_DOC_TYPES.get(doc_type, doc_type), "source": pool["source"],
            "tiers": tiers, "extra_levels": extra_levels, "unused_group_rules": unused,
            "warnings": _tier_warnings(doc_type, pool["source"], rules, pool["group_rules"], extra_levels)}
# ── /KP-T3 ───────────────────────────────────────────────────────────────────────────────────────────────────────────


async def evaluate_approval(doc_type: str, amount: float, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Apakah dokumen butuh persetujuan pada nilai itu (jenjang 1).

    KP-T4 — pembungkus `approval_policy_service.required_levels` (satu tabel kebijakan `approval_policies`; tanpa baris
    tersimpan → baris bawaan dari `approval_rules` lewat `approval_pool`, keputusan sama). `required_role` = nilai
    kompatibel untuk tampilan/notifikasi lama (`compat_role`), BUKAN penentu siapa yang boleh memutus — itu
    `approval_policy_service.can_decide` di pintunya."""
    from services import approval_policy_service as aps
    kind = aps.DOC_TYPE_KIND.get(doc_type)
    levels = await aps.required_levels(kind, entity_id, amount) if kind else []
    if levels:
        l1 = levels[0]
        return {"requires_approval": True, "required_role": aps.compat_role(l1) or None,
                "rule_id": l1["rule_id"] or None, "doc_type": doc_type, "roles": l1["roles"],
                "any_holder": l1["any_holder"]}
    return {"requires_approval": False, "required_role": None, "rule_id": None, "doc_type": doc_type}


async def build_approval_chain(doc_type: str, amount: float, entity_id: Optional[str] = None,
                               force_level1_role: Optional[str] = None) -> Dict[str, Any]:
    """Fase 7.1 — RANTAI persetujuan berjenjang (multi-level sequential).

    KP-T4 — pembungkus `approval_policy_service.chain_for`: jenjang dari tabel kebijakan (jenjang di atas 1 hanya bila
    jenjang 1 berlaku). `force_level1_role` (dipertahankan untuk pemanggil lama; nilainya tidak lagi dibaca) = paksa
    persetujuan walau nilai di bawah ambang (penyimpangan harga / lewat kontrak PO) → jenjang 1 dari jenis
    `purchase_order.deviasi_harga`. Tiap jenjang menyimpan potret `roles`, `rule_id`, `policy_kind` (D3).

    Return:
      requires_approval: bool
      required_role:     nilai kompatibel jenjang pertama (tampilan/notifikasi lama)
      approval_chain:    [{level, required_role, label, roles, rule_id, policy_kind, status:'pending', …}]
    """
    from services import approval_policy_service as aps
    kind = aps.DOC_TYPE_KIND.get(doc_type)
    force = "purchase_order.deviasi_harga" if (force_level1_role and doc_type == "purchase_order") else ""
    chain = await aps.chain_for(kind, entity_id, amount, force_kind=force) if kind else []
    return {
        "requires_approval": bool(chain),
        "required_role": chain[0]["required_role"] if chain else None,
        "approval_chain": chain,
        "rule_id": (chain[0]["rule_id"] or None) if chain else None,
        "doc_type": doc_type,
    }


def current_pending_level(chain: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Level pending pertama dalam rantai (None bila semua approved)."""
    for lv in chain or []:
        if lv.get("status") != "approved":
            return lv
    return None


# ── Pricing engine (Fase 1B) — diskon + PPN, INVARIAN-SAFE ───────────────────
# PENTING (verify_data_integrity L4): item.subtotal = price×quantity (GROSS) dan
# order.total_amount = Σ subtotal (GROSS) HARUS dipertahankan. Diskon & pajak
# disimpan di FIELD TERPISAH (discount_amount/line_total/net_subtotal/dpp/ppn/
# grand_total) sehingga invarian akuntansi lama tetap valid.

def _clamp_pct(v: float) -> float:
    try:
        return max(0.0, min(100.0, float(v or 0)))
    except (TypeError, ValueError):
        return 0.0


async def compute_order_pricing(
    raw_items: List[Dict[str, Any]],
    entity_id: Optional[str] = None,
    order_discount_percent: float = 0.0,
    settings: Optional[Dict[str, Any]] = None,
    cfg_section: str = "sales",
    tax_override: Optional[str] = None,
    ppn_mode_override: Optional[str] = None,
    *,
    at: Optional[datetime] = None,
    snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Hitung breakdown harga order: gross subtotal, diskon item, diskon order,
    DPP, PPN, grand total. Menghormati toggle settings.{cfg_section}.allow_*_discount &
    PKP/non-PKP entitas. `raw_items` = list {price, quantity, discount_percent?, ...}.

    Parameter:
      - cfg_section: bagian settings sumber toggle diskon ("sales" | "purchasing").
      - tax_override: paksa mode pajak ("non_ppn" → tanpa PPN; "ppn" → ikut rate config;
        None/"" → ikut compute_tax dari config entitas).
      - TX-T1 `at`: tanggal dokumen untuk aturan pajak PT (dokumen baru); `snapshot`: potret aturan dokumen yang
        dihitung ulang (`tax_config_service.potret_dokumen`). Hasil memuat `tax_snapshot` (D3, tidak dihitung ulang).
        `pembulatan_tingkat == "baris"` → PPN tiap baris (`items[].ppn_amount`) lalu dijumlah.

    Mengembalikan dict siap-simpan (items diperkaya + agregat). INVARIAN-SAFE:
      - item.subtotal = price × quantity   (GROSS, tak terpengaruh diskon)
      - total_amount  = Σ item.subtotal    (GROSS)
      - net_subtotal  = DPP base = total_amount − items_discount − order_discount
    """
    s = settings or await get_effective_settings(entity_id)
    disc_cfg = s.get(cfg_section, {}) or {}
    # KF-T2 (KF-06) — cadangan = bawaan registry bagian itu (`sales` False, `purchasing` True; dulu selalu True).
    allow_item = bool(disc_cfg.get("allow_item_discount", _reg_default(f"{cfg_section}.allow_item_discount")))
    allow_order = bool(disc_cfg.get("allow_order_discount", _reg_default(f"{cfg_section}.allow_order_discount")))

    priced_items: List[Dict[str, Any]] = []
    gross_total = 0.0
    items_discount_total = 0.0
    for it in raw_items:
        price = round(float(it.get("price", 0) or 0), 2)
        qty = float(it.get("quantity", 0) or 0)
        subtotal = round(price * qty, 2)                      # GROSS — invarian
        disc_pct = _clamp_pct(it.get("discount_percent", 0)) if allow_item else 0.0
        disc_amt = round(subtotal * disc_pct / 100.0, 2)
        line_total = round(subtotal - disc_amt, 2)
        enriched = dict(it)
        enriched.pop("ppn_amount", None)   # TX-T1 — PPN baris hanya ada bila dibulatkan per baris (diisi di bawah)
        enriched.update({
            "price": price, "subtotal": subtotal,
            "discount_percent": disc_pct, "discount_amount": disc_amt,
            "line_total": line_total,
        })
        priced_items.append(enriched)
        gross_total += subtotal
        items_discount_total += disc_amt

    gross_total = round(gross_total, 2)
    items_discount_total = round(items_discount_total, 2)
    after_item = round(gross_total - items_discount_total, 2)
    order_disc_pct = _clamp_pct(order_discount_percent) if allow_order else 0.0
    order_disc_amt = round(after_item * order_disc_pct / 100.0, 2)
    net_subtotal = round(after_item - order_disc_amt, 2)      # = DPP base

    from services import tax_config_service as tcs
    aturan = dict(snapshot) if snapshot else tcs.potret(await tcs.tax_settings(entity_id or "", at))
    if (tax_override or "").strip().lower() == "non_ppn":
        # Supplier non-PKP / transaksi tanpa PPN → tanpa Faktur Pajak Masukan.
        tax = {"ppn_rate": 0.0, "effective_rate": 0.0, "dpp_nilai_lain": False,
               "ppn_mode": "excluded", "is_pkp": False, "dpp": net_subtotal,
               "harga_jual": net_subtotal, "ppn_amount": 0.0, "grand_total": net_subtotal}
        aturan.update({"ppn_rate": 0.0, "is_pkp": False})   # TX-T1 — potret pesanan tanpa PPN: bukan PKP
    else:
        tax = await compute_tax(net_subtotal, entity_id, mode_override=ppn_mode_override, snapshot=aturan)
        if aturan.get("pembulatan_tingkat") == "baris" and tax["ppn_amount"] > 0 and priced_items:
            tax = _ppn_per_baris(priced_items, net_subtotal, after_item, tax, aturan)
    aturan["ppn_mode"] = tax["ppn_mode"]
    return {
        "items": priced_items,
        "total_amount": gross_total,                          # GROSS (invarian)
        "items_discount_total": items_discount_total,
        "order_discount_percent": order_disc_pct,
        "order_discount_amount": order_disc_amt,
        "discount_total": round(items_discount_total + order_disc_amt, 2),
        "net_subtotal": net_subtotal,
        "dpp": tax["dpp"],
        "dpp_nilai_lain": tax.get("dpp_nilai_lain", False),
        "effective_rate": tax.get("effective_rate", tax["ppn_rate"]),
        "ppn_rate": tax["ppn_rate"],
        "ppn_mode": tax["ppn_mode"],
        "is_pkp": tax["is_pkp"],
        "ppn_amount": tax["ppn_amount"],
        "grand_total": tax["grand_total"],
        "tax_snapshot": aturan,
    }


def _ppn_per_baris(items: List[Dict[str, Any]], net_subtotal: float, after_item: float,
                   tax: Dict[str, Any], aturan: Dict[str, Any]) -> Dict[str, Any]:
    """TX-T1 — PPN dibulatkan PER BARIS lalu dijumlah (`tax.pembulatan_tingkat = baris`). Dasar tiap baris = nilai baris
    sesudah diskon baris; diskon pesanan dibagi sebanding nilai baris (baris terakhir menampung sisa pembulatan), supaya
    Σ dasar = DPP dasar dokumen. `items[].ppn_amount` diisi; DPP dihitung dari harga jual total."""
    from services.tax_config_service import round_money
    satuan = aturan["pembulatan_satuan"]
    totals = [float(it.get("line_total") or 0) for it in items]
    if abs(net_subtotal - after_item) < 0.005 or after_item <= 0:
        bases = totals
    else:
        bases = [round(t * net_subtotal / after_item, 2) for t in totals[:-1]]
        bases.append(round(net_subtotal - sum(bases), 2))
    ppn_total = 0.0
    for it, base in zip(items, bases):
        b = ppn_breakdown(base, tax["ppn_rate"], tax["ppn_mode"], tax["is_pkp"], tax["dpp_nilai_lain"], aturan=aturan)
        it["ppn_amount"] = b["ppn_amount"]
        ppn_total += b["ppn_amount"]
    ppn_total = round(ppn_total, 2)
    factor = int(aturan["dpp_pembilang"]) / int(aturan["dpp_penyebut"]) if tax["dpp_nilai_lain"] else 1.0
    if tax["ppn_mode"] == "included":
        harga_jual, grand = round(net_subtotal - ppn_total, 2), net_subtotal
    else:
        harga_jual, grand = net_subtotal, round(net_subtotal + ppn_total, 2)
    return {**tax, "ppn_amount": ppn_total, "harga_jual": harga_jual, "grand_total": grand,
            "dpp": round_money(harga_jual * factor, satuan)}


def role_satisfies(actor_role: str, required_role: Optional[str]) -> bool:
    """Cek apakah role aktor memenuhi required_role dari matriks approval.

    FASE E-8 (E8.1) — peringkat peran TIDAK lagi ditulis di sini. Dulu angkanya
    disalin di dua tempat (`so_approvals.ROLE_RANK`) sehingga menambah peran berarti
    dua tempat harus diingat. Sumber tunggal sekarang `backend/role_registry.py`.
    """
    from role_registry import role_satisfies as _rs
    return _rs(actor_role, required_role)


# ── Allocation Policy resolver (Sub-fase 1.7, KN_15 §6.0) ────────────────────
# Hierarki override: order > customer > system-settings(default). OWNER selalu HARD #1.

VALID_ALLOC = {
    "mode": {"auto", "assisted", "manual"},
    "lot_mode": {"prefer_single", "strict_single", "allow_mixed"},
    "lot_selection": {"fefo", "fifo", "smallest_fit", "largest_fit"},
    "location_pref": {"single_warehouse", "nearest_customer", "fewest_splits"},
    "makloon_reserve_mode": {"block", "approve"},
}


def _sanitize_alloc(policy: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    """Pastikan nilai enum valid; jika tidak, pakai base/default."""
    out = dict(base)
    for k, v in (policy or {}).items():
        if k in VALID_ALLOC:
            out[k] = v if v in VALID_ALLOC[k] else base.get(k)
        elif k in ("allow_intercompany", "allow_partial", "dye_lot_strict", "roll_pick_sales"):
            out[k] = bool(v)
        elif k == "priority_order" and isinstance(v, list) and v:
            # owner selalu #1 (HARD)
            rest = [x for x in v if x in ("lot", "location", "roll_efficiency")]
            out[k] = ["owner"] + [x for x in rest if x != "owner"]
        elif k in out:
            out[k] = v
    return out


async def get_allocation_policy(
    entity_id: Optional[str] = None,
    customer: Optional[Dict[str, Any]] = None,
    order_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Effective allocation policy: system(global+entity) → customer.allocation_policy → order_overrides."""
    s = await get_effective_settings(entity_id)
    base = dict(DEFAULT_GLOBAL_SETTINGS["allocation"])
    base = _sanitize_alloc(s.get("allocation", {}) or {}, base)
    # FASE G-0 — `inventory.intercompany_transfer_required` DULU tombol palsu (0 consumer).
    # Sekarang benar-benar mengikat: bila wajib transfer, alokasi TIDAK BOLEH memakai stok
    # milik entitas lain secara diam-diam — pengguna harus membuat Transaksi Antar-Entitas
    # lebih dulu sehingga laba/HPP setiap PT tetap benar.
    if bool((s.get("inventory", {}) or {}).get("intercompany_transfer_required",   # KF-T2 — cadangan registry
                                               _reg_default("inventory.intercompany_transfer_required"))):
        base["allow_intercompany"] = False
        base["intercompany_blocked_reason"] = (
            "Pengaturan 'Wajib transfer sebelum jual stok entitas lain' aktif — buat "
            "Transaksi Antar-Entitas dulu sebelum memakai stok milik PT lain.")
    if customer and isinstance(customer.get("allocation_policy"), dict):
        base = _sanitize_alloc(customer["allocation_policy"], base)
    # Customer lot_policy (KN_15 R4) → peta ke lot_mode bila ada
    cust_lot_policy = (customer or {}).get("lot_policy")
    lot_policy_map = {"strict_single": "strict_single", "prefer_single": "prefer_single", "allow_mixed": "allow_mixed"}
    if cust_lot_policy in lot_policy_map:
        base["lot_mode"] = lot_policy_map[cust_lot_policy]
    # P0-4 — customer flag "enforce_single_dye_lot" → paksa alokasi 1 dye lot.
    if (customer or {}).get("enforce_single_dye_lot"):
        base["dye_lot_strict"] = True
    if order_overrides:
        base = _sanitize_alloc(order_overrides, base)
    return base

