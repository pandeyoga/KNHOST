"""KF-T7 — nilai bisnis yang ditulis mati menjadi pengaturan (docs/blueprint/unit/KF-T7.md): U1–U15 + tambahan.

Persiapan bersama: seed lingkungan B; akun admin (`kepala_admin`). Fixture sisip (langsung ke database tiruan):
pelanggan + pesanan + surat jalan (U3–U5), barang + saldo stok (U9), dokumen lama `system_settings{scope:
"special_order"}` (U8), baris Aturan Persetujuan pesanan khusus (U7). Alur lewat API: `PUT /api/config/values`
(simpan pengaturan), `POST /api/auth/login` (U10, U11). Tiap uji mengembalikan pengaturan yang diubahnya (`_pulihkan`).

Butir #7 (`approval.special_order_min_amount`) TIDAK berlaku di `303e709`: KP-T4 sudah menghapus `APPROVAL_THRESHOLD`
dan kapan pesanan khusus wajib disetujui dibaca dari Aturan Persetujuan per PT — U7 membuktikannya (lihat laporan).
"""
from __future__ import annotations

import io
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

import config_registry as registry

pytestmark = pytest.mark.anyio

BACKEND = Path(__file__).resolve().parents[1]
KSC, KANDA = "ent_ksc", "ent_kanda"

#: Tabel "Pengaturan" unit — 27 baris; `approval.special_order_min_amount` (#7) tidak didaftarkan (ditutup KP-T4).
BAWAAN: Dict[str, Any] = {
    "ar.overdue_block_days": 14, "ar.credit_warning_pct": 80,
    "sales.reservation_days": 3, "sales.group_sales_max_members": 2,
    "sales.special_order_margin_pct": 30, "sales.special_order_multi_item_min": 2,
    "inventory.low_stock_default_qty": 100, "notif.reservation_expiry_warn_hours": 24,
    "inventory.stock_analytics.trend_window_days": 30, "inventory.stock_analytics.trend_band_pct": 10,
    "inventory.split_roll_max_length": 150,
    "receiving.dn_profile_min_confirmed": 3, "receiving.dn_profile_min_share_pct": 80,
    "sales.sample_catalogue_base_qty": 1, "sales.sample_catalogue_soft_qty": 2,
    "qc.inspection_interval_yard": 15, "qc.inspection_min_points": 10,
    "finance.rounding_tolerance_rupiah": 1, "periode.suspense_reason_min_chars": 5,
    "qc.hold_reason_min_chars": 15, "putaway.close_reason_min_chars": 10,
    "keamanan.maks_salah_sandi": 5, "keamanan.lama_kunci_menit": 15, "keamanan.umur_sesi_jam": 24,
    "esign.otp_ttl_minutes": 10, "esign.max_attempts": 5,
}
#: Lapisan per kunci (kolom `scopes` tabel unit): hanya grup = pemakainya tidak mengenal PT (ASUMSI unit).
HANYA_GRUP = {"sales.special_order_multi_item_min", "inventory.low_stock_default_qty",
              "notif.reservation_expiry_warn_hours", "inventory.split_roll_max_length",
              "receiving.dn_profile_min_confirmed", "receiving.dn_profile_min_share_pct",
              "finance.rounding_tolerance_rupiah", "periode.suspense_reason_min_chars", "qc.hold_reason_min_chars",
              "putaway.close_reason_min_chars", "keamanan.maks_salah_sandi", "keamanan.lama_kunci_menit",
              "keamanan.umur_sesi_jam", "esign.otp_ttl_minutes", "esign.max_attempts"}
RISIKO_TINGGI = {"finance.rounding_tolerance_rupiah", "keamanan.maks_salah_sandi", "keamanan.lama_kunci_menit",
                 "keamanan.umur_sesi_jam"}


# ── pembantu ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _isi(key, value, scope_type="global", scope_id="", reason="uji KF-T7"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


async def _simpan(klien, h, key, value, scope_type="global", scope_id=""):
    r = await klien.put("/api/config/values", headers=h, json=_isi(key, value, scope_type, scope_id))
    assert r.status_code == 200, r.text
    return r


async def _pulihkan(klien, h, key, *pt):
    for eid in pt:
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": key, "scope_type": "entity", "scope_id": eid, "reason": "pulihkan"})
        assert r.status_code == 200, r.text
    r = await klien.post("/api/config/values/reset", headers=h,
                         json={"key": key, "scope_type": "global", "reason": "pulihkan"})
    assert r.status_code == 200, r.text


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _akun_bersandi(klien, h) -> Dict[str, str]:
    """Akun sales baru lewat `POST /api/users` (sandi diketahui) — untuk uji masuk (U10, U11)."""
    import secrets
    email = f"kft7.{secrets.token_hex(5)}@uji.id"
    sandi = "Kft7-" + secrets.token_urlsafe(10)
    r = await klien.post("/api/users", headers=h, json={"name": "Uji KF-T7", "email": email, "role": "sales",
                                                         "password": sandi, "home_entity_id": KSC,
                                                         "allowed_entity_ids": [KSC]})
    assert r.status_code == 200, r.text
    return {"email": email, "password": sandi}


async def _masuk(klien, email: str, sandi: str):
    """`POST /api/auth/login` tanpa kuki sisa (login mencabut sesi kuki lama di peramban yang sama)."""
    klien.cookies.clear()
    r = await klien.post("/api/auth/login", json={"email": email, "password": sandi})
    klien.cookies.clear()
    return r


async def _pelanggan_telat(db, cid: str, entity_id: str, *, telat_hari: int, total: float, plafon: float = 0.0):
    """Fixture: satu pelanggan kredit + satu pesanan belum lunas. `telat_hari` > 0 → surat jalan pertama dibuat
    sekian hari (+1 jam) lalu dengan syarat bayar 0 hari (jatuh tempo = tanggal surat jalan) → telat `telat_hari`
    hari penuh. `telat_hari` = 0 → belum dikirim (belum jatuh tempo, tidak telat)."""
    now = datetime.now(timezone.utc)
    cust = {"id": cid, "name": f"Pelanggan {cid}", "entity_id": entity_id, "credit_limit": plafon, "status": "active",
            "payment_profile": {}, "deposit_balance": 0, "created_at": _iso(now)}
    await db.customers.insert_one(dict(cust))
    await db.sales_orders.insert_one({
        "id": f"so_{cid}", "number": f"SO-{cid}", "customer_id": cid, "customer_name": cust["name"],
        "entity_id": entity_id, "status": "confirmed", "payment_status": "unpaid", "grand_total": total,
        "total_amount": total, "payments": [], "payment_term_days": 0, "payment_term_code": "NET30",
        "created_at": _iso(now - timedelta(days=telat_hari + 2))})
    if telat_hari > 0:
        await db.shipments.insert_one({"id": f"sj_{cid}", "shipment_no": f"SJ-{cid}", "order_id": f"so_{cid}",
                                       "status": "dispatched",
                                       "created_at": _iso(now - timedelta(days=telat_hari, hours=1))})
    return cust


async def _status_kredit(cust) -> str:
    from services.customer_service import compute_customer_credit
    return (await compute_customer_credit(cust))["status"]


async def _status_umur_piutang(cust) -> str:
    from services.ar_aging_service import aging_report
    rep = await aging_report(entity_id=cust["entity_id"])
    return next(r["credit_status"] for r in rep["customers"] if r["customer_id"] == cust["id"])


def _nama_kode(path: Path) -> set:
    """Nama (identifier) yang dipakai sebagai KODE di berkas — komentar dan teks diabaikan."""
    toks = tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline)
    return {t.string for t in toks if t.type == tokenize.NAME}


# ── U1 — 26 kunci terdaftar; bawaan = nilai hari ini ────────────────────────────────────────────────────────────────
def test_KFT7_U1_kunci_terdaftar_bawaan_sama_dengan_nilai_hari_ini():
    # 27 baris tabel; butir #7 tidak didaftarkan (KP-T4 — Aturan Persetujuan menjadi satu-satunya sumber).
    assert len(BAWAAN) == 26
    assert registry.get("approval.special_order_min_amount") is None
    for key, nilai in BAWAAN.items():
        e = registry.get(key)
        assert e is not None, key
        assert e["default"] == nilai and registry.default_of(key) == nilai, key
        assert e["status"] == "active" and e["permission"] == ["settings", "manage"], key
        assert e["scopes"] == (["global"] if key in HANYA_GRUP else ["global", "entity"]), key
        assert (e["risk"] == "high") == (key in RISIKO_TINGGI), key
        assert e["unit"] and e["consumers"] and e["section"], key
    # Kelompok baru "Keamanan akun & sesi" (dipetakan ke layar Integrasi & Sistem — U15).
    assert registry.get("keamanan.umur_sesi_jam")["group"] == "keamanan"
    assert "keamanan" in registry.GROUP_IDS


# ── U2 — konstanta tidak tersisa di berkas jangkar dan pemakainya ─────────────────────────────────────────────────
#: (nama konstanta, berkas di bawah backend/) — berkas = jangkar "Keadaan sekarang" + semua pemakainya (grep di HEAD).
#: `gate_review_actions.py` (MIN_REASON antrean gerbang RFID) sengaja TIDAK diperiksa (titik henti H7).
KONSTANTA = [
    ("OVERDUE_BLOCK_DAYS", ["services/ar_aging_service.py", "services/customer_service.py"]),
    ("WARNING_RATIO", ["services/ar_aging_service.py", "services/customer_service.py"]),
    ("MAX_GROUP_SALES", ["services/customer_service.py", "services/sales_order_helpers.py"]),
    ("APPROVAL_THRESHOLD", ["services/special_order_service.py", "routers/special_orders.py"]),
    ("DEFAULT_MARGIN_PCT", ["services/special_order_phase2.py"]),
    ("MULTI_ITEM_MIN", ["services/special_order_phase2.py", "routers/special_orders.py"]),
    ("LOW_STOCK_THRESHOLD", ["services/notification_service.py"]),
    ("LOW_STOCK_QTY", ["services/stock_availability.py", "services/stock_figures.py"]),
    ("TREND_WINDOW_DAYS", ["services/stock_analytics_service.py"]),
    ("TREND_BAND", ["services/stock_analytics_service.py"]),
    ("MAX_AVAILABLE_ROLL_LEN", ["services/roll_service.py"]),
    ("MIN_CONFIRMED", ["services/supplier_dn_profile_service.py", "services/goods_receipt_ocr_service.py"]),
    ("LOCALE_SHARE", ["services/supplier_dn_profile_service.py"]),
    ("CATALOGUE_BASE_QTY", ["services/sample_sale_service.py", "services/cutting_service.py",
                            "routers/sample_orders.py"]),
    ("CATALOGUE_SOFT_QTY", ["services/sample_sale_service.py", "services/cutting_service.py",
                            "routers/sample_orders.py"]),
    ("INTERVAL_YARD", ["services/qc_inspection_service.py", "services/inspection_service.py"]),
    ("MIN_INTERVALS", ["services/qc_inspection_service.py", "services/inspection_service.py"]),
    ("DEFAULT_FACTORS", ["services/return_grade_impairment.py"]),
    ("RETURN_ASSUMPTION_DEFAULTS", ["services/return_policy_service.py", "services/return_disposition_service.py"]),
    ("ROUNDING_TOLERANCE", ["services/gl_service.py"]),
    ("SUSPENSE_OVERRIDE_MIN_LEN", ["services/closing_service.py"]),
    ("MIN_REASON", ["services/inspection_service.py"]),
    ("MIN_CLOSE_REASON", ["services/putaway_arrival_service.py"]),
    ("MAX_LOGIN_ATTEMPTS", ["routers/auth.py"]),
    ("LOCKOUT_MINUTES", ["routers/auth.py"]),
    ("SESSION_TTL_HOURS", ["core_utils.py", "dependencies.py", "routers/auth.py", "bootstrap.py"]),
    ("OTP_TTL_MIN", ["services/esign_service.py"]),
    ("MAX_ATTEMPTS", ["services/esign_service.py"]),
]
#: Konstanta bernama khas: juga tidak boleh dipakai di berkas aplikasi mana pun (`grep -rn` di backend/ tanpa uji).
KHAS = {"OVERDUE_BLOCK_DAYS", "WARNING_RATIO", "MAX_GROUP_SALES", "APPROVAL_THRESHOLD", "DEFAULT_MARGIN_PCT",
        "MULTI_ITEM_MIN", "LOW_STOCK_THRESHOLD", "LOW_STOCK_QTY", "TREND_WINDOW_DAYS", "MAX_AVAILABLE_ROLL_LEN",
        "CATALOGUE_BASE_QTY", "CATALOGUE_SOFT_QTY", "RETURN_ASSUMPTION_DEFAULTS", "ROUNDING_TOLERANCE",
        "SUSPENSE_OVERRIDE_MIN_LEN", "MIN_CLOSE_REASON", "MAX_LOGIN_ATTEMPTS", "LOCKOUT_MINUTES", "SESSION_TTL_HOURS",
        "OTP_TTL_MIN"}


def test_KFT7_U2_konstanta_tidak_tersisa():
    sisa = [(n, f) for n, files in KONSTANTA for f in files if n in _nama_kode(BACKEND / f)]
    assert sisa == [], sisa
    lain = []
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith(("tests/", "tests_mem/", "scripts/")) or "__pycache__" in rel or "/test_" in f"/{rel}" \
                or rel.endswith("gate_review_actions.py"):
            continue
        lain += [(n, rel) for n in KHAS & _nama_kode(p)]
    assert lain == [], lain
    # Literal yang bukan konstanta bernama: masa reservasi 3 hari (#5), jendela 24 jam (#47), cadangan retur (#54).
    so = (BACKEND / "routers/sales_orders.py").read_text(encoding="utf-8")
    assert "timedelta(days=3)" not in so
    assert "(3 hari)" not in (BACKEND / "services/scheduler_service.py").read_text(encoding="utf-8")
    assert "timedelta(hours=24)" not in (BACKEND / "services/notification_service.py").read_text(encoding="utf-8")
    disp = (BACKEND / "services/return_disposition_service.py").read_text(encoding="utf-8")
    assert "or 21)" not in disp and "or 3)" not in disp


# ── U3 — hari telat yang memblokir, per PT ─────────────────────────────────────────────────────────────────────────
async def test_KFT7_U3_hari_telat_blokir_per_pt(klien, kepala_admin, db):
    from services.customer_service import credit_thresholds
    a = await _pelanggan_telat(db, "kft7_u3_ksc", KSC, telat_hari=10, total=1_000_000)
    b = await _pelanggan_telat(db, "kft7_u3_kanda", KANDA, telat_hari=10, total=1_000_000)
    assert await credit_thresholds(KSC) == {"block_days": 14, "warning_ratio": 0.8}
    # Awal: telat 10 hari ≤ 14 → peringatan (telat > 0), belum diblokir. Plafon 0 = tanpa plafon.
    assert await _status_kredit(a) == "warning" and await _status_kredit(b) == "warning"
    await _simpan(klien, kepala_admin, "ar.overdue_block_days", 7, "entity", KSC)
    assert await credit_thresholds(KSC) == {"block_days": 7, "warning_ratio": 0.8}
    assert await credit_thresholds(KANDA) == {"block_days": 14, "warning_ratio": 0.8}
    # Sesudah: KSC 10 > 7 → diblokir; KANDA 10 ≤ 14 → tetap peringatan (PT lain tidak ikut).
    assert await _status_kredit(a) == "blocked"
    assert await _status_kredit(b) == "warning"
    # U5 — umur piutang dan kartu pelanggan memberi status yang sama (satu pembaca ambang).
    assert await _status_umur_piutang(a) == "blocked"
    assert await _status_umur_piutang(b) == "warning"
    await _pulihkan(klien, kepala_admin, "ar.overdue_block_days", KSC)
    assert await _status_kredit(a) == "warning" and await _status_umur_piutang(a) == "warning"


# ── U4 — peringatan terhadap plafon, per PT ────────────────────────────────────────────────────────────────────────
async def test_KFT7_U4_persen_peringatan_plafon(klien, kepala_admin, db):
    c = await _pelanggan_telat(db, "kft7_u4", KSC, telat_hari=0, total=7_000_000, plafon=10_000_000)
    # 7 jt < 80 % × 10 jt = 8 jt dan tidak telat → aktif.
    assert await _status_kredit(c) == "active" and await _status_umur_piutang(c) == "active"
    await _simpan(klien, kepala_admin, "ar.credit_warning_pct", 60, "entity", KSC)
    # 7 jt ≥ 60 % × 10 jt = 6 jt → peringatan, di kedua pembaca.
    assert await _status_kredit(c) == "warning" and await _status_umur_piutang(c) == "warning"
    # Pemeriksaan kredit saat membuat pesanan memakai persen yang sama: proyeksi 7 jt + 0 → "warning".
    from services.customer_service import check_credit_for_order
    assert (await check_credit_for_order(c, 0))["level"] == "warning"
    await _pulihkan(klien, kepala_admin, "ar.credit_warning_pct", KSC)
    assert (await check_credit_for_order(c, 0))["level"] == "ok"


# ── U5 — satu pembaca: umur piutang dan kartu pelanggan sama (dirangkum di U3/U4) ──────────────────────────────────
async def test_KFT7_U5_umur_piutang_dan_kartu_pelanggan_satu_pembaca(klien, kepala_admin, db):
    import inspect
    from services import ar_aging_service, customer_service
    a = await _pelanggan_telat(db, "kft7_u5", KSC, telat_hari=10, total=500_000)
    for nilai, harap in ((7, "blocked"), (30, "warning")):
        await _simpan(klien, kepala_admin, "ar.overdue_block_days", nilai, "entity", KSC)
        assert await _status_kredit(a) == harap == await _status_umur_piutang(a), nilai
    await _pulihkan(klien, kepala_admin, "ar.overdue_block_days", KSC)
    # Kedua pembaca memakai `credit_thresholds` (satu-satunya yang membaca dua kunci kredit).
    assert "credit_thresholds" in inspect.getsource(ar_aging_service.aging_report)
    assert "credit_thresholds" in inspect.getsource(customer_service.compute_customer_credit)


# ── U6 — masa reservasi stok pesanan per PT ────────────────────────────────────────────────────────────────────────
async def test_KFT7_U6_masa_reservasi_per_pt(klien, kepala_admin):
    from services.inventory_service import reservation_expires_at
    now = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
    assert await reservation_expires_at(KSC, now) == now + timedelta(days=3)
    await _simpan(klien, kepala_admin, "sales.reservation_days", 5, "entity", KSC)
    assert await reservation_expires_at(KSC, now) == now + timedelta(days=5)
    assert await reservation_expires_at(KANDA, now) == now + timedelta(days=3)
    await _pulihkan(klien, kepala_admin, "sales.reservation_days", KSC)
    from services.scheduler_service import JOBS
    job = next(j for j in JOBS if j["id"] == "reservation_expiry")
    assert "(menurut pengaturan masa reservasi)" in job["description"]


# ── U7 — tidak berlaku: ambang pesanan khusus sudah di Aturan Persetujuan (KP-T4) ────────────────────────────────
async def test_KFT7_U7_tidak_berlaku_ambang_pesanan_khusus_di_aturan_persetujuan(db):
    from services import approval_policy_service as aps
    for f in ("services/special_order_service.py", "routers/special_orders.py"):
        assert "APPROVAL_THRESHOLD" not in _nama_kode(BACKEND / f), f
    assert "required_levels" in (BACKEND / "routers/special_orders.py").read_text(encoding="utf-8")
    # Fixture: baris Aturan Persetujuan pesanan khusus — KSC mulai Rp5 jt, KANDA mulai Rp10 jt (jenjang 1).
    rows = [{**aps._row("special_order", KSC, 1, ["manager", "admin"], min_amount=5_000_000), "id": "kft7_u7_ksc",
             "version": 1},
            {**aps._row("special_order", KANDA, 1, ["manager", "admin"], min_amount=10_000_000), "id": "kft7_u7_kd",
             "version": 1}]
    await db.approval_policies.insert_many([dict(r) for r in rows])
    try:
        # 8 jt: KSC wajib disetujui (8 jt ≥ 5 jt), KANDA tidak (8 jt < 10 jt); 12 jt: keduanya wajib.
        assert await aps.required_levels("special_order", KSC, 8_000_000)
        assert not await aps.required_levels("special_order", KANDA, 8_000_000)
        assert await aps.required_levels("special_order", KANDA, 12_000_000)
    finally:
        await db.approval_policies.delete_many({"id": {"$in": ["kft7_u7_ksc", "kft7_u7_kd"]}})


# ── U8 — migrasi margin pesanan khusus dari penyimpanan lama ──────────────────────────────────────────────────────
async def test_KFT7_U8_migrasi_margin_pesanan_khusus(klien, kepala_admin, db):
    from services import special_order_phase2 as p2
    # Tanpa dokumen lama (lifespan sudah menjalankan migrasi sekali): bawaan registry 30.
    assert await p2.default_margin_pct() == 30.0
    # Nilai lama tidak sah (di luar 0–500 %): tidak dipindah, server tetap jalan, penanda tidak dipasang.
    await db.system_settings.update_one({"scope": "special_order"}, {"$set": {"default_margin_pct": 999}}, upsert=True)
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$unset": {"kft7_margin_pesanan_khusus": ""}})
    assert await p2.migrasi_margin_lama() == {"ditulis": 0}
    assert not (await db.system_settings.find_one({"scope": "__migrations__"}) or {}).get("kft7_margin_pesanan_khusus")
    assert await p2.default_margin_pct() == 30.0
    await db.system_settings.update_one({"scope": "special_order"}, {"$set": {"default_margin_pct": 25}})
    hasil = await p2.migrasi_margin_lama()
    assert hasil == {"ditulis": 1}
    assert await p2.default_margin_pct() == 25.0
    assert await p2.default_margin_pct(KANDA) == 25.0          # lapisan grup → semua PT
    row = await db.config_values.find_one({"key": "sales.special_order_margin_pct", "scope_type": "global"},
                                          {"_id": 0}, sort=[("changed_at", -1)])
    assert row["reason"] == "Pindahan dari penyimpanan lama" and row["value"] == 25
    # Sekali jalan: penanda ada → tidak menulis lagi; dokumen lama tidak dihapus.
    assert await p2.migrasi_margin_lama() == {"ditulis": 0}
    assert (await db.system_settings.find_one({"scope": "special_order"}))["default_margin_pct"] == 25
    # Mesin tidak lagi membaca dokumen lama langsung: dokumen lama diubah → nilai tetap dari Pengaturan.
    await db.system_settings.update_one({"scope": "special_order"}, {"$set": {"default_margin_pct": 99}})
    assert await p2.default_margin_pct() == 25.0
    await _pulihkan(klien, kepala_admin, "sales.special_order_margin_pct")
    assert await p2.default_margin_pct() == 30.0
    await db.system_settings.delete_one({"scope": "special_order"})


# ── U9 — ambang stok menipis bila barang tanpa titik pesan ulang ──────────────────────────────────────────────────
async def test_KFT7_U9_stok_menipis_barang_tanpa_titik_pesan_ulang(klien, kepala_admin, db):
    from services.notification_service import generate_system_notifications
    pid = "kft7_u9_prod"
    await db.products.insert_one({"id": pid, "sku": "KFT7-U9", "name": "Kain U9", "status": "active",
                                  "base_unit": "yard", "entity_id": KSC, "reorder_point": 0})
    await db.inventory_balances.insert_one({"id": "kft7_u9_bal", "product_id": pid, "warehouse_id": "kft7_wh",
                                            "owner_entity_id": KSC, "on_hand_qty": 60, "available_qty": 60,
                                            "reserved_qty": 0})
    # Pemindai hanya membaca 300 barang aktif pertama: barang lain dinonaktifkan sementara (modul ini saja).
    lain = [p["id"] for p in await db.products.find({"status": "active", "id": {"$ne": pid}}, {"_id": 0, "id": 1})
            .to_list(None)]
    await db.products.update_many({"id": {"$in": lain}}, {"$set": {"status": "kft7_sementara"}})
    try:
        await db.notifications.delete_many({"ref": {"$regex": f"^low_stock:{pid}(#|$)"}})
        await generate_system_notifications()
        assert await db.notifications.count_documents({"ref": {"$regex": f"^low_stock:{pid}(#|$)"}}) > 0       # 60 < 100
        await _simpan(klien, kepala_admin, "inventory.low_stock_default_qty", 50)
        await db.notifications.delete_many({"ref": {"$regex": f"^low_stock:{pid}(#|$)"}})
        await generate_system_notifications()
        assert await db.notifications.count_documents({"ref": {"$regex": f"^low_stock:{pid}(#|$)"}}) == 0      # 60 ≥ 50
        # Titik pesan ulang barang tetap menang atas angka bawaan.
        await db.products.update_one({"id": pid}, {"$set": {"reorder_point": 80}})
        await generate_system_notifications()
        assert await db.notifications.count_documents({"ref": {"$regex": f"^low_stock:{pid}(#|$)"}}) > 0       # 60 < 80
        # "Stok rendah" papan stok/dasbor memakai angka yang sama (definisi tunggal K-04).
        from services.stock_availability import low_stock_qty, low_stock_summary
        assert await low_stock_qty() == 50
        assert (await low_stock_summary([KSC], limit=0))["threshold"] == 50
    finally:
        await db.products.update_many({"id": {"$in": lain}}, {"$set": {"status": "active"}})
        await _pulihkan(klien, kepala_admin, "inventory.low_stock_default_qty")


# ── U10 — batas salah sandi ────────────────────────────────────────────────────────────────────────────────────────
async def test_KFT7_U10_batas_salah_sandi(klien, kepala_admin):
    u = await _akun_bersandi(klien, kepala_admin)
    assert (await _masuk(klien, u["email"], u["password"])).status_code == 200   # akun & sandi sah
    await _simpan(klien, kepala_admin, "keamanan.maks_salah_sandi", 3)
    try:
        for _ in range(3):
            r = await _masuk(klien, u["email"], "salah-sandi")
            assert r.status_code == 401, r.text
        # Percobaan ke-4 (sandi benar) ditolak: akun terkunci sesudah 3 kali salah (dulu baru sesudah 5).
        r = await _masuk(klien, u["email"], u["password"])
        assert r.status_code == 429, r.text
    finally:
        await _pulihkan(klien, kepala_admin, "keamanan.maks_salah_sandi")


async def test_KFT7_U10b_lama_kunci_akun(klien, kepala_admin, db):
    u = await _akun_bersandi(klien, kepala_admin)
    await _simpan(klien, kepala_admin, "keamanan.lama_kunci_menit", 60)
    try:
        for _ in range(5):
            await _masuk(klien, u["email"], "salah")
        rec = await db.login_attempts.find_one({"identifier": {"$regex": f":{u['email'].lower()}$"}})
        sisa = rec["locked_until"].replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        assert timedelta(minutes=59) < sisa <= timedelta(minutes=60)
    finally:
        await _pulihkan(klien, kepala_admin, "keamanan.lama_kunci_menit")


# ── U11 — umur sesi masuk ──────────────────────────────────────────────────────────────────────────────────────────
async def test_KFT7_U11_umur_sesi_masuk(klien, kepala_admin, db):
    u = await _akun_bersandi(klien, kepala_admin)

    async def _sesi_baru():
        r = await _masuk(klien, u["email"], u["password"])
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        s = await db.sessions.find_one({"token": tok}, {"_id": 0})
        return tok, s["expires_at"].replace(tzinfo=timezone.utc), r.headers.get("set-cookie", "")

    lama_tok, lama_exp, _ = await _sesi_baru()
    assert abs(lama_exp - (datetime.now(timezone.utc) + timedelta(hours=24))) < timedelta(minutes=1)
    await _simpan(klien, kepala_admin, "keamanan.umur_sesi_jam", 2)
    try:
        tok, exp, cookie = await _sesi_baru()
        assert abs(exp - (datetime.now(timezone.utc) + timedelta(hours=2))) < timedelta(minutes=1)
        assert "Max-Age=7200" in cookie
        # Sesi yang dibuat sebelum perubahan tetap pada kedaluwarsa lamanya (dipakai pun tidak dipendekkan).
        r = await klien.get("/api/auth/me", headers={"Authorization": f"Bearer {lama_tok}"})
        assert r.status_code == 200, r.text
        s = await db.sessions.find_one({"token": lama_tok}, {"_id": 0})
        assert s["expires_at"].replace(tzinfo=timezone.utc) == lama_exp
    finally:
        await _pulihkan(klien, kepala_admin, "keamanan.umur_sesi_jam")


# ── U12 — jarak titik inspeksi per PT ──────────────────────────────────────────────────────────────────────────────
async def test_KFT7_U12_titik_inspeksi_per_pt(klien, kepala_admin):
    from services import qc_inspection_service as qc
    await _simpan(klien, kepala_admin, "qc.inspection_interval_yard", 10, "entity", KSC)
    try:
        assert qc.interval_count(200, **await qc.interval_rules(KSC)) == 20      # ⌈200 ÷ 10⌉
        assert qc.interval_count(200, **await qc.interval_rules(KANDA)) == 14    # ⌈200 ÷ 15⌉ = 14 ≥ 10
        assert qc.interval_count(90, **await qc.interval_rules(KANDA)) == 10     # ⌈90 ÷ 15⌉ = 6 → minimum 10
    finally:
        await _pulihkan(klien, kepala_admin, "qc.inspection_interval_yard", KSC)


# ── U13 — nilai di bawah minimum ditolak ───────────────────────────────────────────────────────────────────────────
async def test_KFT7_U13_nilai_di_bawah_minimum_ditolak(klien, kepala_admin):
    for key, salah in (("keamanan.maks_salah_sandi", 2), ("esign.max_attempts", 0), ("ar.credit_warning_pct", 0)):
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(key, salah))
        assert r.status_code == 400, (key, r.text)
        assert "paling kecil" in str(r.json().get("detail")), (key, r.text)


# ── U14 — putaran t1_config untuk 26 kunci ────────────────────────────────────────────────────────────────────────
def _contoh(e: Dict[str, Any]):
    """(nilai grup, nilai PT, nilai tak sah) — mengikuti `t1_config.py` (alt_value/bad_value)."""
    d, hi = e["default"], e["max"]
    v1 = d + 1 if d + 1 <= hi else d - 1
    v2 = v1 + 1 if v1 + 1 <= hi else v1 - 1
    return v1, v2, hi + 1000000


async def test_KFT7_U14_putaran_t1_config_26_kunci(klien, kepala_admin):
    from services.config_resolver import value_of
    for key in BAWAAN:
        e = registry.require(key)
        v1, v2, salah = _contoh(e)
        await _simpan(klien, kepala_admin, key, v1)
        assert await value_of(key) == v1, key
        r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": key})
        assert next(i for i in r.json()["items"] if i["key"] == key)["value"] == v1, key
        if "entity" in e["scopes"]:
            await _simpan(klien, kepala_admin, key, v2, "entity", KANDA)
            assert await value_of(key, {"entity_id": KANDA}) == v2, key
            assert await value_of(key, {"entity_id": KSC}) == v1, key            # PT lain tidak ikut
            await _pulihkan(klien, kepala_admin, key, KANDA)
        else:
            r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(key, v1, "entity", KANDA))
            assert r.status_code == 400, (key, r.text)                             # lapisan PT tidak didukung
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(key, salah))
        assert r.status_code == 400, (key, r.text)
        await _pulihkan(klien, kepala_admin, key)
        assert await value_of(key) == e["default"], key


# ── U15 — kelompok `keamanan` punya rumah; pemakai tersambung ─────────────────────────────────────────────────────
def test_KFT7_U15_kelompok_keamanan_punya_layar_dan_pemakai_tersambung(monkeypatch):
    import re
    js = (BACKEND.parent / "frontend/src/features/settings/config/configGroupViews.js").read_text(encoding="utf-8")
    views = dict(re.findall(r'"(settings-cfg-[a-z]+)":\s*\{[^}]*?groups:\s*\[([^\]]*)\]', js, re.S))
    rumah = [v for v, g in views.items() if "keamanan" in re.findall(r'"([a-z-]+)"', g)]
    assert rumah == ["settings-cfg-system"]
    from services import config_health
    monkeypatch.setattr(config_health, "BACKEND", str(BACKEND))                      # pola uji KF-T2/KF-T3
    monkeypatch.setattr(config_health, "FRONTEND", str(BACKEND.parent / "frontend/src"))
    rows = {r["key"]: r for r in config_health.report()["rows"]}
    rusak = {k: (rows[k]["consumers_stale"], rows[k]["consumers_missing"]) for k in BAWAAN
             if rows[k]["wiring_status"] != "OK"}
    assert rusak == {}, rusak


# ── Tambahan (02 §2.4 butir 2: nilai A → perilaku A, nilai B → perilaku B, PT lain tetap) ──────────────────────────
async def test_KFT7_T1_anggota_tim_sales_per_pt(klien, kepala_admin):
    from fastapi import HTTPException
    from services.customer_service import group_sales_max, normalize_sales_team
    tim = [{"sales_id": f"s{i}", "name": f"S{i}", "role": "pic" if i == 0 else "co", "split_pct": 0}
           for i in range(3)]
    with pytest.raises(HTTPException) as ex:
        normalize_sales_team(tim, "s0", "S0", max_members=await group_sales_max(KSC))
    assert "maksimal 2 orang" in str(ex.value.detail)
    await _simpan(klien, kepala_admin, "sales.group_sales_max_members", 3, "entity", KSC)
    try:
        out = normalize_sales_team(tim, "s0", "S0", max_members=await group_sales_max(KSC))
        assert len(out) == 3 and round(sum(m["split_pct"] for m in out), 2) == 100.0
        with pytest.raises(HTTPException):
            normalize_sales_team(tim, "s0", "S0", max_members=await group_sales_max(KANDA))
    finally:
        await _pulihkan(klien, kepala_admin, "sales.group_sales_max_members", KSC)


async def test_KFT7_T2_pesanan_khusus_multi_barang_dan_katalog_sample(klien, kepala_admin):
    from services import sample_sale_service as smp
    from services import special_order_phase2 as p2
    od = {"items": [{"id": "a"}, {"id": "b"}]}
    assert p2.is_multi_item(od, await p2.multi_item_min()) is True               # 2 ≥ 2
    await _simpan(klien, kepala_admin, "sales.special_order_multi_item_min", 3)
    assert p2.is_multi_item(od, await p2.multi_item_min()) is False              # 2 < 3
    await _pulihkan(klien, kepala_admin, "sales.special_order_multi_item_min")
    assert await smp.catalogue_qty(KSC) == {"base": 1.0, "soft": 2.0}
    await _simpan(klien, kepala_admin, "sales.sample_catalogue_base_qty", 1.5, "entity", KSC)
    try:
        assert await smp.catalogue_qty(KSC) == {"base": 1.5, "soft": 2.0}
        assert await smp.catalogue_qty(KANDA) == {"base": 1.0, "soft": 2.0}
    finally:
        await _pulihkan(klien, kepala_admin, "sales.sample_catalogue_base_qty", KSC)


async def test_KFT7_T3_tren_penjualan_dan_format_surat_jalan(klien, kepala_admin):
    from services import stock_analytics_service as sa
    from services import supplier_dn_profile_service as P
    r = await sa.trend_rules(KSC)
    assert r == {"trend_days": 30, "band": 0.1}
    assert sa.trend_of(1.0, 1.15, r["band"]) == "naik"                          # 1,15 > 1 + 0,10
    await _simpan(klien, kepala_admin, "inventory.stock_analytics.trend_band_pct", 20, "entity", KSC)
    try:
        assert sa.trend_of(1.0, 1.15, (await sa.trend_rules(KSC))["band"]) == "stabil"   # dalam ±20 %
        assert (await sa.trend_rules(KANDA))["band"] == 0.1
    finally:
        await _pulihkan(klien, kepala_admin, "inventory.stock_analytics.trend_band_pct", KSC)
    prof = {"number_locale": "id", "confirmed_count": 3}
    assert P.active_locale(prof, **await P.profile_rules()) == "id"
    await _simpan(klien, kepala_admin, "receiving.dn_profile_min_confirmed", 5)
    try:
        assert P.active_locale(prof, **await P.profile_rules()) == "unknown"     # 3 < 5 terkonfirmasi
    finally:
        await _pulihkan(klien, kepala_admin, "receiving.dn_profile_min_confirmed")
    rules = await P.profile_rules()
    assert P._decide_locale({"id": 4, "en": 1}, rules["min_share"]) == "id"      # 80 % ≥ 80 %


async def test_KFT7_T4_pembulatan_alasan_dan_reservasi_segera_berakhir(klien, kepala_admin, db):
    from services import closing_service, gl_service, inspection_service
    assert (await gl_service.inventory_reconciliation())["rounding_tolerance"] == 1
    await _simpan(klien, kepala_admin, "finance.rounding_tolerance_rupiah", 5)
    assert (await gl_service.inventory_reconciliation())["rounding_tolerance"] == 5
    await _pulihkan(klien, kepala_admin, "finance.rounding_tolerance_rupiah")
    assert await closing_service.suspense_reason_min_chars() == 5
    await _simpan(klien, kepala_admin, "periode.suspense_reason_min_chars", 8)
    assert await closing_service.suspense_reason_min_chars() == 8
    await _pulihkan(klien, kepala_admin, "periode.suspense_reason_min_chars")
    assert (await inspection_service.meta())["policy"]["min_reason_length"] == 15
    await _simpan(klien, kepala_admin, "qc.hold_reason_min_chars", 20)
    assert (await inspection_service.meta())["policy"]["min_reason_length"] == 20
    await _pulihkan(klien, kepala_admin, "qc.hold_reason_min_chars")
    # Reservasi berakhir 30 jam lagi: bawaan 24 jam → belum diingatkan; 48 jam → diingatkan.
    from services.notification_service import generate_system_notifications
    oid = "kft7_t4_so"
    await db.sales_orders.insert_one({"id": oid, "number": "SO-KFT7-T4", "customer_name": "Uji", "status": "reserved",
                                      "entity_id": KSC, "total_amount": 1, "pending_approvals": [],
                                      "reservation_expires_at": _iso(datetime.now(timezone.utc)
                                                                     + timedelta(hours=30))})
    try:
        await generate_system_notifications()
        assert await db.notifications.count_documents({"ref": {"$regex": f"^resv:{oid}(#|$)"}}) == 0
        await _simpan(klien, kepala_admin, "notif.reservation_expiry_warn_hours", 48)
        await generate_system_notifications()
        assert await db.notifications.count_documents({"ref": {"$regex": f"^resv:{oid}(#|$)"}}) > 0
    finally:
        await _pulihkan(klien, kepala_admin, "notif.reservation_expiry_warn_hours")
        await db.sales_orders.delete_one({"id": oid})
