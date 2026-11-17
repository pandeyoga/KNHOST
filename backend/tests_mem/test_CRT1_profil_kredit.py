"""CR-T1 — profil kredit per pelanggan per PT, diubah hanya lewat pengajuan (docs/blueprint/unit/CR-T1.md, U1–U15 + U16b).

Persiapan (alur lewat API): pelanggan **P1** (`ent_ksc`, penanggung jawab Sales seed) dan **P2** (`ent_kanda`) dibuat
Admin lewat `POST /api/customers`; akun seed `adm`, `mgr`, `sls`. Pengaturan lewat `PUT /api/config/values` (dipulihkan
di akhir tiap uji). Fixture SISIP (langsung ke database tiruan): pesanan + surat jalan untuk piutang telat (U7–U9),
tanggal `limit_valid_until` kemarin (U11 — layar/server menolak tanggal lampau), pelanggan lama ber-plafon & diblokir (U14).

Urutan uji penting (satu database per modul): U2 → U4 membangun profil P1; U5/U6 memakai kontrol dua orang; U7–U9 status
kredit; U10 pengajuan terbuka & isian tidak sah; U11 plafon kedaluwarsa; U12 izin; U13 usulan plafon saat pelanggan dibuat;
U15 plafon bawaan PT; U14 (migrasi, memasang penanda yang mematikan cadangan data lama) TERAKHIR.
Hitungan tangan ditulis di tiap uji (masukan → langkah → hasil).
"""
from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
ROOT = Path(__file__).resolve().parents[2]
PESAN_TERBUKA = "Masih ada pengajuan perubahan kredit yang menunggu keputusan untuk pelanggan ini."
SIMPAN: dict = {}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _pelanggan_baru(klien, h, nama: str, entitas: str, sales_id: str, **extra) -> dict:
    body = {"name": nama, "pic_name": "Andi", "phone": "081234567801", "city": "Bandung",
            "address": "Jl. Uji Kredit No. 1", "entity_id": entitas, "assigned_sales_id": sales_id, **extra}
    r = await klien.post("/api/customers", headers={**h, "X-Entity-Id": entitas}, json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
async def uji(klien, db, sesi, kepala_admin):
    sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
    p1 = await _pelanggan_baru(klien, kepala_admin, "Toko Kredit Satu", KSC, sales["id"])
    p2 = await _pelanggan_baru(klien, kepala_admin, "Toko Kredit Dua", KANDA, sales["id"])
    return {"adm": kepala_admin, "adm_k": {**kepala_admin, "X-Entity-Id": KANDA},
            "mgr": await sesi("manager@kainnusantara.id"),
            "mgr_k": await sesi("manager@kainnusantara.id", entitas=KANDA),
            "sls": await sesi("sales@kainnusantara.id"), "sales": sales, "P1": p1["id"], "P2": p2["id"]}


async def _profil(klien, h, cid: str, entitas: str = "") -> dict:
    r = await klien.get(f"/api/customers/{cid}/credit-profile", headers=h,
                        params={"entity_id": entitas} if entitas else None)
    assert r.status_code == 200, r.text
    return r.json()


async def _ajukan(klien, h, cid: str, changes: dict, reason: str = "Tinjauan kredit berkala", **extra):
    return await klien.post(f"/api/customers/{cid}/credit-profile-requests", headers=h,
                            json={"changes": changes, "reason": reason, **extra})


async def _putus(klien, h, rid: str, decision: str = "approve", note: str = ""):
    return await klien.post(f"/api/credit-profile-requests/{rid}/decision", headers=h,
                            json={"decision": decision, "note": note})


async def _ajukan_setujui(klien, uji, cid: str, changes: dict, h_aju=None, h_putus=None) -> dict:
    r = await _ajukan(klien, h_aju or uji["mgr"], cid, changes)
    assert r.status_code == 200, r.text
    r2 = await _putus(klien, h_putus or uji["mgr"], r.json()["id"])
    assert r2.status_code == 200, r2.text
    return r2.json()


async def _simpan(klien, h, key, value, scope_type="entity", scope_id=KSC):
    r = await klien.put("/api/config/values", headers=h, json={"items": [
        {"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": "uji CR-T1"}]})
    assert r.status_code == 200, r.text


async def _cabut(klien, h, key, scope_id=KSC):
    r = await klien.post("/api/config/values/clear", headers=h,
                         json={"key": key, "scope_type": "entity", "scope_id": scope_id, "reason": "pulihkan"})
    assert r.status_code == 200, r.text


async def _jurnal_kirim(oid: str, entitas: str, nilai: float, tanggal: str, sj: str) -> None:
    """PK-41 (K-16) — fixture jurnal pendapatan surat jalan (Dr piutang / Cr pendapatan, bentuk `post_shipment_revenue`):
    piutang kini berumur per surat jalan BERJURNAL, jadi fixture "sudah dikirim" memuat jurnalnya juga."""
    from services import gl_service as gl
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": nilai, "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": nilai}],
                           description=f"Pengakuan penjualan {oid} · {sj}", date=tanggal, source_type="shipment_revenue",
                           source_id=sj, entity_id=entitas, created_by="uji", source_label=sj,
                           ref={"order_id": oid, "order_number": f"SO-{oid}"})


async def _pesanan(db, cid: str, entitas: str, *, total: float, telat_hari: int, oid: str) -> None:
    """Fixture: satu pesanan kredit belum lunas. `telat_hari` > 0 → surat jalan pertama sekian hari (+1 jam) lalu dengan
    syarat bayar 0 hari (jatuh tempo = tanggal surat jalan) → telat `telat_hari` hari penuh; 0 → belum dikirim."""
    now = datetime.now(timezone.utc)
    await db.sales_orders.insert_one({
        "id": oid, "number": f"SO-{oid}", "customer_id": cid, "customer_name": cid, "entity_id": entitas,
        "status": "confirmed", "payment_status": "unpaid", "grand_total": total, "total_amount": total,
        "payments": [], "payment_term_days": 0, "payment_term_code": "NET30",
        "created_at": _iso(now - timedelta(days=telat_hari + 2))})
    if telat_hari > 0:
        await db.shipments.insert_one({"id": f"sj_{oid}", "shipment_no": f"SJ-{oid}", "order_id": oid,
                                       "status": "dispatched",
                                       "created_at": _iso(now - timedelta(days=telat_hari, hours=1))})
        # PK-41 — jurnal pendapatan surat jalan bertanggal buku WIB `telat_hari` hari lalu (syarat 0 hari → telat tepat)
        from services.book_date import tanggal_buku
        tgl = (datetime.fromisoformat(tanggal_buku()) - timedelta(days=telat_hari)).date().isoformat()
        await _jurnal_kirim(oid, entitas, total, tgl, f"sj_{oid}")


async def _status(klien, h, cid: str) -> dict:
    r = await klien.get(f"/api/customers/{cid}/credit-status", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ── U1 — PATCH tidak mengubah plafon maupun status blokir (sudah hijau sejak PK-45) ─────────────────────────────────
async def test_CRT1_U1_patch_sales_tidak_mengubah_kredit(klien, db, uji):
    r = await klien.patch(f"/api/customers/{uji['P1']}", headers=uji["sls"],
                          json={"data": {"credit_limit": 99_000_000, "status": "blocked"}})
    assert r.status_code == 200, r.text
    c = await db.customers.find_one({"id": uji["P1"]}, {"_id": 0})
    assert (c["credit_limit"], c["status"]) == (0, "active")
    assert await db.customer_credit_profiles.count_documents({}) == 0
    assert await db.credit_profile_requests.count_documents({}) == 0


# ── U2 — Sales mengajukan; profil efektif belum berubah ─────────────────────────────────────────────────────────────
async def test_CRT1_U2_sales_mengajukan(klien, uji):
    r = await _ajukan(klien, uji["sls"], uji["P1"], {"limit_mode": "khusus", "credit_limit": 50_000_000},
                      reason="Naik kelas grosir")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "diajukan" and j["entity_id"] == KSC and j["number"].endswith("PKR-00001")
    assert j["credit_snapshot"]["credit_limit"] == 0          # potret saat diajukan (D3)
    SIMPAN["u2"] = j["id"]
    p = await _profil(klien, uji["sls"], uji["P1"])
    assert p["effective"]["limit_source"] == "bawaan_pt"
    assert p["effective"]["credit_limit"] == 0                  # ar.default_credit_limit bawaan 0 = tanpa batas
    assert p["pending_request"]["id"] == j["id"] and p["profile"] is None


# ── U3 — Sales tidak memutus (K-28) ─────────────────────────────────────────────────────────────────────────────────
async def test_CRT1_U3_sales_tidak_memutus(klien, db, uji):
    r = await _putus(klien, uji["sls"], SIMPAN["u2"])
    assert r.status_code == 403, r.text
    assert "'Uang Masuk, Piutang & Faktur Pajak'" in r.json()["detail"]
    assert (await db.credit_profile_requests.find_one({"id": SIMPAN["u2"]}))["status"] == "diajukan"


# ── U4 — Manajer menyetujui → profil khusus versi 1, riwayat 1 baris ───────────────────────────────────────────────
async def test_CRT1_U4_manajer_menyetujui(klien, uji):
    r = await _putus(klien, uji["mgr"], SIMPAN["u2"])
    assert r.status_code == 200, r.text
    assert r.json()["request"]["status"] == "disetujui"
    p = await _profil(klien, uji["sls"], uji["P1"])
    assert p["effective"]["credit_limit"] == 50_000_000 and p["effective"]["limit_source"] == "khusus"
    assert p["profile"]["version"] == 1 and p["profile"]["last_request_id"] == SIMPAN["u2"]
    assert len(p["history"]) == 1
    ch = {c["field"]: c for c in p["history"][0]["changes"]}
    assert ch["credit_limit"]["from"] is None and ch["credit_limit"]["to"] == 50_000_000
    assert p["pending_request"] is None
    # Kotak ringkasan kartu pelanggan membaca plafon yang BERLAKU (bukan `customers.credit_limit`, tetap 0).
    r = await klien.get(f"/api/customers/{uji['P1']}/360", headers=uji["sls"])
    assert r.status_code == 200, r.text
    assert r.json()["credit"]["credit_limit"] == 50_000_000 and r.json()["credit"]["limit_source"] == "khusus"
    assert r.json()["credit_limit"] == 0


# ── U5 — dua orang pada ent_ksc ─────────────────────────────────────────────────────────────────────────────────────
async def test_CRT1_U5_dua_orang_pt_ksc(klien, db, uji):
    await _simpan(klien, uji["adm"], "kontrol.ubah_profil_kredit.min_orang", "2")
    try:
        r = await _ajukan(klien, uji["mgr"], uji["P1"], {"credit_limit": 60_000_000})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        r1 = await _putus(klien, uji["mgr"], rid)
        assert r1.status_code == 403, r1.text
        assert "harus diputuskan orang lain" in r1.json()["detail"]
        assert (await db.credit_profile_requests.find_one({"id": rid}))["status"] == "diajukan"
        r2 = await _putus(klien, uji["adm"], rid)
        assert r2.status_code == 200, r2.text
        assert r2.json()["effective"]["credit_limit"] == 60_000_000
    finally:
        await _cabut(klien, uji["adm"], "kontrol.ubah_profil_kredit.min_orang")


# ── U6 — PT lain tidak ikut (ent_kanda tetap satu orang) ────────────────────────────────────────────────────────────
async def test_CRT1_U6_pt_lain_satu_orang(klien, uji):
    await _simpan(klien, uji["adm"], "kontrol.ubah_profil_kredit.min_orang", "2")
    try:
        r = await _ajukan(klien, uji["mgr_k"], uji["P2"], {"limit_mode": "khusus", "credit_limit": 100_000_000})
        assert r.status_code == 200, r.text
        assert r.json()["entity_id"] == KANDA
        r2 = await _putus(klien, uji["mgr_k"], r.json()["id"])
        assert r2.status_code == 200, r2.text
    finally:
        await _cabut(klien, uji["adm"], "kontrol.ubah_profil_kredit.min_orang")


# ── U7 — hari blokir bawaan PT (KF-T7) dibaca lewat profil efektif ─────────────────────────────────────────────────
async def test_CRT1_U7_hari_blokir_bawaan_pt(klien, db, uji):
    # P1, P2: sisa 1.000.000 jatuh tempo 10 hari lalu. ent_ksc: 7 hari → 10 > 7 diblokir; ent_kanda bawaan 14 → 10 ≤ 14
    # peringatan (telat ≥ 1 hari). Plafon (60 jt / 100 jt) tidak tercapai: 1 jt < 80 % plafon.
    await _pesanan(db, uji["P1"], KSC, total=1_000_000, telat_hari=10, oid="so_crt1_u7_p1")
    await _pesanan(db, uji["P2"], KANDA, total=1_000_000, telat_hari=10, oid="so_crt1_u7_p2")
    await _simpan(klien, uji["adm"], "ar.overdue_block_days", 7)
    try:
        s1, s2 = await _status(klien, uji["adm"], uji["P1"]), await _status(klien, uji["adm"], uji["P2"])
        assert s1["credit"]["status"] == "blocked" and s1["level"] == "blocked"
        assert s2["credit"]["status"] == "warning"
        p = await _profil(klien, uji["adm"], uji["P1"], KSC)
        assert (p["effective"]["overdue_block_days"], p["effective"]["block_days_source"]) == (7, "bawaan_pt")
        p = await _profil(klien, uji["adm_k"], uji["P2"], KANDA)
        assert (p["effective"]["overdue_block_days"], p["effective"]["block_days_source"]) == (14, "bawaan_pt")
    finally:
        await _cabut(klien, uji["adm"], "ar.overdue_block_days")


# ── U8 — hari blokir khusus pelanggan menimpa bawaan PT ────────────────────────────────────────────────────────────
async def test_CRT1_U8_hari_blokir_khusus(klien, uji):
    await _simpan(klien, uji["adm"], "ar.overdue_block_days", 7)
    try:
        assert (await _status(klien, uji["adm"], uji["P1"]))["credit"]["status"] == "blocked"
        res = await _ajukan_setujui(klien, uji, uji["P1"], {"overdue_block_days": 30})
        assert res["effective"]["block_days_source"] == "khusus" and res["effective"]["overdue_block_days"] == 30
        s = await _status(klien, uji["adm"], uji["P1"])   # 10 ≤ 30 → peringatan (telat ≥ 1 hari)
        assert s["credit"]["status"] == "warning" and s["credit"]["block_days_source"] == "khusus"
    finally:
        await _cabut(klien, uji["adm"], "ar.overdue_block_days")


# ── U9 — persen peringatan PT terhadap plafon khusus ───────────────────────────────────────────────────────────────
async def test_CRT1_U9_persen_peringatan(klien, db, uji):
    from services.customer_service import compute_customer_credit
    await db.sales_orders.update_one({"id": "so_crt1_u7_p1"}, {"$set": {"payment_status": "paid"}})
    await _pesanan(db, uji["P1"], KSC, total=8_500_000, telat_hari=0, oid="so_crt1_u9")
    await _ajukan_setujui(klien, uji, uji["P1"], {"credit_limit": 10_000_000})
    cust = await db.customers.find_one({"id": uji["P1"]}, {"_id": 0})
    # 8.500.000 ≥ 80 % × 10.000.000 = 8.000.000 → peringatan.
    c = await compute_customer_credit(cust)
    assert (c["credit_limit"], c["ar_outstanding"], c["status"]) == (10_000_000, 8_500_000, "warning")
    await _simpan(klien, uji["adm"], "ar.credit_warning_pct", 90)
    try:
        # 8.500.000 < 90 % × 10.000.000 = 9.000.000 → aktif.
        assert (await compute_customer_credit(cust))["status"] == "active"
        from services.ar_aging_service import aging_report
        rep = await aging_report(entity_id=KSC)
        row = next(r for r in rep["customers"] if r["customer_id"] == uji["P1"])
        assert (row["credit_status"], row["credit_limit"], row["limit_source"]) == ("active", 10_000_000, "khusus")
    finally:
        await _cabut(klien, uji["adm"], "ar.credit_warning_pct")
    assert (await compute_customer_credit(cust))["status"] == "warning"


# ── U10 — satu pengajuan terbuka; isian tidak sah ditolak 400 ──────────────────────────────────────────────────────
async def test_CRT1_U10_terbuka_dan_isian_tidak_sah(klien, db, akun, sesi, uji):
    r = await _ajukan(klien, uji["sls"], uji["P1"], {"credit_limit": 12_000_000})
    assert r.status_code == 200, r.text
    terbuka = r.json()["id"]
    n0 = await db.credit_profile_requests.count_documents({})
    r = await _ajukan(klien, uji["sls"], uji["P1"], {"credit_limit": 15_000_000})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == PESAN_TERBUKA
    r = await _ajukan(klien, uji["mgr_k"], uji["P2"], {"credit_limit": -1})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Isian tidak sah: Plafon kredit — harus angka nol atau lebih."
    r = await _ajukan(klien, uji["mgr_k"], uji["P2"], {"allowed_term_codes": ["XX99"]})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Isian tidak sah: Termin yang diizinkan — kode termin tidak dikenal: XX99."
    # Isian tidak sah lain dari tabel Galat: tanggal lampau, khusus tanpa angka, alasan < 5 huruf.
    kemarin = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    for isi, alasan, pesan in (
            ({"limit_valid_until": kemarin}, "Tinjauan kredit", "Isian tidak sah: Berlaku sampai — tanggal sudah lewat."),
            ({"limit_mode": "khusus", "credit_limit": None}, "Tinjauan kredit",
             "Isian tidak sah: Plafon kredit — wajib diisi untuk plafon khusus."),
            ({"credit_limit": 1_000}, "12 .", "Alasan pengajuan wajib diisi (minimal 5 huruf).")):
        r = await _ajukan(klien, uji["mgr_k"], uji["P2"], isi, reason=alasan)
        assert r.status_code == 400, (isi, r.text)
        assert r.json()["detail"] == pesan, isi
    assert await db.credit_profile_requests.count_documents({}) == n0
    # Pembatalan: Sales lain (tanpa izin memutus) tidak boleh; pengaju sendiri boleh, alasan wajib.
    lain = await sesi(await akun("sales"))
    r = await klien.post(f"/api/credit-profile-requests/{terbuka}/cancel", headers=lain,
                         json={"reason": "Bukan milik saya"})
    assert r.status_code == 403, r.text
    r = await klien.post(f"/api/credit-profile-requests/{terbuka}/cancel", headers=uji["sls"], json={"reason": ".."})
    assert r.status_code == 400, r.text
    r = await klien.post(f"/api/credit-profile-requests/{terbuka}/cancel", headers=uji["sls"],
                         json={"reason": "Salah ketik plafon"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "dibatalkan"
    r = await _putus(klien, uji["mgr"], terbuka)
    assert r.status_code == 409 and r.json()["detail"] == "Pengajuan ini sudah diputus."


# ── U11 — plafon khusus kedaluwarsa kembali ke bawaan PT ───────────────────────────────────────────────────────────
async def test_CRT1_U11_plafon_kedaluwarsa(klien, db, uji):
    kemarin = (datetime.now(timezone.utc) + timedelta(hours=7) - timedelta(days=1)).date().isoformat()
    await db.customer_credit_profiles.update_one({"customer_id": uji["P1"], "entity_id": KSC},
                                                 {"$set": {"limit_valid_until": kemarin}})   # fixture sisip
    try:
        p = await _profil(klien, uji["sls"], uji["P1"])
        assert p["effective"]["credit_limit"] == 0 and p["effective"]["limit_source"] == "kedaluwarsa"
        assert p["effective"]["khusus_credit_limit"] == 10_000_000
    finally:
        await db.customer_credit_profiles.update_one({"customer_id": uji["P1"], "entity_id": KSC},
                                                     {"$set": {"limit_valid_until": ""}})


# ── U12 — izin baru (02 §3.2 butir 4) ──────────────────────────────────────────────────────────────────────────────
async def test_CRT1_U12_izin_peran_uji_baku(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                           peran_sopir, uji):
    h = await sesi(await akun(await peran_tanpa_acuan({"credit_profile": ["view"]}, label="Lihat Kredit")))
    r = await klien.get(f"/api/customers/{uji['P1']}/credit-profile", headers=h)
    assert r.status_code == 200, r.text
    r = await _ajukan(klien, h, uji["P1"], {"credit_limit": 1_000_000})
    assert r.status_code == 403, r.text
    assert r.json()["detail"].startswith("Anda belum punya akses untuk mengajukan perubahan kredit.")
    for peran in (await peran_manajer_kosong(), peran_sopir):
        r = await klien.get(f"/api/customers/{uji['P1']}/credit-profile", headers=await sesi(await akun(peran)))
        assert r.status_code == 403, (peran, r.text)
    # Tanpa Acuan + update dan approve: mengajukan lalu memutus (bawaan satu orang).
    h2 = await sesi(await akun(await peran_tanpa_acuan(
        {"credit_profile": ["view", "update", "approve"], "customer": ["view"]}, label="Putus Kredit")))
    r = await _ajukan(klien, h2, uji["P1"], {"credit_limit": 11_000_000})
    assert r.status_code == 200, r.text
    r = await _putus(klien, h2, r.json()["id"])
    assert r.status_code == 200, r.text


# ── U13 — plafon di form pelanggan baru menjadi pengajuan ──────────────────────────────────────────────────────────
async def test_CRT1_U13_plafon_saat_pelanggan_dibuat(klien, db, uji):
    r = await klien.post("/api/customers", headers=uji["sls"], json={
        "name": "Toko Baru Kredit", "pic_name": "Sinta", "phone": "081234567813", "city": "Bandung",
        "address": "Jl. Uji Kredit No. 13", "credit_limit": 25_000_000})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert (await db.customers.find_one({"id": cid}))["credit_limit"] == 0
    reqs = [x async for x in db.credit_profile_requests.find({"customer_id": cid}, {"_id": 0})]
    assert len(reqs) == 1 and reqs[0]["status"] == "diajukan" and reqs[0]["entity_id"] == KSC
    ch = {c["field"]: c["to"] for c in reqs[0]["changes"]}
    assert ch == {"limit_mode": "khusus", "credit_limit": 25_000_000}
    assert reqs[0]["reason"] == "Plafon diusulkan saat pelanggan dibuat"
    assert reqs[0]["requested_by_id"] == uji["sales"]["id"]
    assert r.json()["credit_profile_request"]["id"] == reqs[0]["id"]


# ── U15 — plafon bawaan PT: putaran pengaturan + perilaku per PT ───────────────────────────────────────────────────
async def test_CRT1_U15_plafon_bawaan_pt(klien, db, uji):
    from test_KFT8_putaran_pengaturan import putaran
    gagal = await putaran(klien, uji["adm"], "ar.default_credit_limit")
    assert not gagal, "\n".join(gagal)
    p3 = await _pelanggan_baru(klien, uji["adm"], "Toko Tanpa Plafon Satu", KSC, uji["sales"]["id"])
    p4 = await _pelanggan_baru(klien, uji["adm"], "Toko Tanpa Plafon Dua", KANDA, uji["sales"]["id"])
    await _simpan(klien, uji["adm"], "ar.default_credit_limit", 5_000_000)
    try:
        e3 = (await _profil(klien, uji["adm"], p3["id"], KSC))["effective"]
        e4 = (await _profil(klien, uji["adm_k"], p4["id"], KANDA))["effective"]
        assert (e3["credit_limit"], e3["limit_source"]) == (5_000_000, "bawaan_pt")
        assert (e4["credit_limit"], e4["limit_source"]) == (0, "bawaan_pt")
        # Piutang 5.000.000 ≥ plafon bawaan 5.000.000 → terblokir di ent_ksc (contoh kunci).
        await _pesanan(db, p3["id"], KSC, total=5_000_000, telat_hari=0, oid="so_crt1_u15")
        assert (await _status(klien, uji["adm"], p3["id"]))["credit"]["status"] == "blocked"
    finally:
        await _cabut(klien, uji["adm"], "ar.default_credit_limit")
    e3 = (await _profil(klien, uji["adm"], p3["id"], KSC))["effective"]
    assert (e3["credit_limit"], e3["limit_source"]) == (0, "bawaan_pt")


# ── U16b — dua pengajuan bersamaan (lapis B; lapis A = backend/tests/test_bp_CRT1_profil_kredit.py) ────────────────
async def test_CRT1_U16b_dua_pengajuan_bersamaan(klien, db, uji):
    p = await _pelanggan_baru(klien, uji["adm"], "Toko Bersamaan", KSC, uji["sales"]["id"])
    hasil = await asyncio.gather(*(_ajukan(klien, uji["mgr"], p["id"], {"credit_limit": 1_000_000 * (i + 1)})
                                   for i in range(2)))
    assert sorted(r.status_code for r in hasil) == [200, 409], [r.text for r in hasil]
    assert await db.credit_profile_requests.count_documents({"customer_id": p["id"], "status": "diajukan"}) == 1


# ── Jalur lama (D8), status aktif/nonaktif kembali lewat PATCH, izin lama dicabut ──────────────────────────────────
async def test_CRT1_jalur_lama_dimatikan(klien, db, uji):
    r = await klien.put(f"/api/customers/{uji['P1']}/credit", headers=uji["adm"],
                        json={"credit_limit": 1, "status": "blocked", "reason": "uji jalur lama"})
    assert r.status_code == 410, r.text
    assert r.json()["detail"] == "Plafon dan blokir kredit diubah lewat pengajuan perubahan kredit."
    r = await klien.patch(f"/api/customers/{uji['P2']}", headers=uji["adm_k"], json={"data": {"status": "inactive"}})
    assert r.status_code == 200, r.text
    assert (await db.customers.find_one({"id": uji["P2"]}))["status"] == "inactive"
    r = await klien.patch(f"/api/customers/{uji['P2']}", headers=uji["adm_k"], json={"data": {"status": "active"}})
    assert r.status_code == 200 and (await db.customers.find_one({"id": uji["P2"]}))["status"] == "active"
    from permissions_config import DEFAULT_PERMISSIONS
    assert all("manage_credit" not in (p.get("customer") or []) for p in DEFAULT_PERMISSIONS.values())
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    assert all("manage_credit" not in ((p or {}).get("customer") or []) for p in rec["matrix"].values())
    assert "crt1:izin-kredit" in rec["migrations_applied"]
    for peran, harus in (("admin", {"view", "update", "approve"}), ("manager", {"view", "update", "approve"}),
                         # K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance setara Manajer: + `approve`.
                         ("finance", {"view", "update", "approve"}), ("sales_admin", {"view", "update"}),
                         ("sales", {"view", "update"})):
        assert set(rec["matrix"][peran].get("credit_profile") or []) == harus, peran


async def test_CRT1_izin_lama_tersimpan_dibersihkan_saat_menyala(klien, db, kepala_admin, uji):
    """Instalasi yang sudah menerima `customer.manage_credit` (PK-45) dinyalakan ulang: pasangan itu dibuang sekali dari
    matriks tersimpan sehingga editor peran bisa menyimpan lagi; `credit_profile.*` sampai lewat izin bawaan baru."""
    import bootstrap
    rec = await db.permission_settings.find_one({"id": "default"})
    matrix = rec["matrix"]
    for peran in ("admin", "manager", "finance"):
        matrix[peran]["customer"] = list(matrix[peran].get("customer") or ["view"]) + ["manage_credit"]
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": matrix},
                                                                "$pull": {"migrations_applied": "crt1:izin-kredit"}})
    await bootstrap.run_bootstrap()
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    assert all("manage_credit" not in ((p or {}).get("customer") or []) for p in rec["matrix"].values())
    r = await klien.get("/api/access/roles/finance", headers=kepala_admin)
    assert r.status_code == 200, r.text
    perms = r.json()["permissions"]
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin,
                          json={"permissions": perms, "expected_version": r.json().get("version")})
    assert r.status_code == 200, r.text   # dulu (pasangan basi tersimpan): 400 "Aksi ['manage_credit'] tidak berlaku"


# ── Kontrol dua orang terdaftar; pintu ber-kunci idempotensi ───────────────────────────────────────────────────────
def test_CRT1_kontrol_dan_idempotensi_terdaftar():
    import config_registry as registry
    from config_catalog_kontrol import AKSI_BY_ID
    from idempotency import is_idempotent_path
    a = AKSI_BY_ID["ubah_profil_kredit"]
    assert (a["label"], a["kelompok"], a["awal"], a["punya_nominal"]) == ("Ubah profil kredit pelanggan", "C", "1", True)
    assert registry.require("kontrol.ubah_profil_kredit.min_orang")["default"] == "1"
    assert registry.require("kontrol.ubah_profil_kredit.batas_nominal")["default"] == 0
    e = registry.require("ar.default_credit_limit")
    assert (e["group"], e["type"], e["default"], e["min"], e["max"], e["unit"]) == \
        ("pembayaran-pelanggan", "money", 0, 0, 1_000_000_000_000, "Rp")
    assert tuple(e["scopes"]) == ("global", "entity") and tuple(e["permission"]) == ("credit_profile", "approve")
    assert (e["risk"], e["requires_reason"], e["label"]) == ("high", True, "Plafon bawaan pelanggan baru")
    for path in ("/api/customers/cus_x/credit-profile-requests", "/api/credit-profile-requests/cpr_1/decision",
                 "/api/credit-profile-requests/cpr_1/cancel"):
        assert is_idempotent_path(path), path
    assert not is_idempotent_path("/api/customers/cus_x")


# ── U14 — migrasi data lama (TERAKHIR: memasang penanda yang mematikan cadangan data lama) ─────────────────────────
async def test_CRT1_U14_migrasi_data_lama(klien, db, uji, capsys):
    from services import credit_profile_service as cps
    await db.customers.insert_one({"id": "cus_crt1_lama", "name": "Toko Lama", "entity_id": KSC,
                                   "credit_limit": 15_000_000, "status": "blocked", "payment_profile": {},
                                   "created_at": _iso(datetime.now(timezone.utc))})   # fixture sisip
    # Sebelum migrasi: cadangan data lama — nilai yang sama dengan hasil migrasi.
    e = await cps.effective("cus_crt1_lama", KSC)
    assert (e["credit_limit"], e["limit_source"], e["credit_status"]) == (15_000_000, "data_lama", "blokir_manual")
    # Skrip mode lapor (bawaan / --dry-run) tidak menulis apa pun.
    spec = importlib.util.spec_from_file_location("migrate_credit_profiles", ROOT / "scripts/migrate_credit_profiles.py")
    skrip = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skrip)
    assert await skrip.jalankan(["--dry-run"]) == 0
    assert "Mode lapor: 1 profil akan dibuat, 1 pelanggan dibuka" in capsys.readouterr().out
    assert await db.customer_credit_profiles.count_documents({"customer_id": "cus_crt1_lama"}) == 0
    assert (await db.customers.find_one({"id": "cus_crt1_lama"}))["status"] == "blocked"
    # Putaran tulis pertama.
    h1 = await cps.migrasi_data_lama(tulis=True)
    assert (h1["profil_dibuat"], h1["status_dibuka"]) == (1, 1)
    prof = [p async for p in db.customer_credit_profiles.find({"customer_id": "cus_crt1_lama"}, {"_id": 0})]
    assert len(prof) == 1
    p = prof[0]
    assert (p["entity_id"], p["limit_mode"], p["credit_limit"], p["credit_status"], p["block_reason"]) == \
        (KSC, "khusus", 15_000_000, "blokir_manual", "Dipindahkan dari status pelanggan")
    c = await db.customers.find_one({"id": "cus_crt1_lama"}, {"_id": 0})
    assert (c["status"], c["credit_limit"]) == ("active", 15_000_000)   # credit_limit tidak dihapus
    e = await cps.effective("cus_crt1_lama", KSC)
    assert (e["credit_limit"], e["limit_source"], e["credit_status"]) == (15_000_000, "khusus", "blokir_manual")
    # Putaran kedua tidak mengubah apa pun.
    h2 = await cps.migrasi_data_lama(tulis=True)
    assert (h2["profil_dibuat"], h2["status_dibuka"]) == (0, 0)
    assert [x async for x in db.customer_credit_profiles.find({"customer_id": "cus_crt1_lama"}, {"_id": 0})] == prof
