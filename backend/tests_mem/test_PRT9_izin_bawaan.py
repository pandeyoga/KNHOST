"""PR-T9 — perubahan izin peran bawaan bertahan setelah server dinyalakan ulang (docs/blueprint/unit/PR-T9.md).

"Nyalakan ulang" = `await bootstrap.run_bootstrap()`. Satu database per modul; urutan uji penting dan sengaja:
basis data baru (U1, U2, U6) → reset lengkap (U12) → pencabutan bertahan (U3, U13, U4, U5) → peran kustom mengikuti
peran dasar (U8–U10, U14, U11) → butir migrasi baru (U7) → tiruan instalasi lama (U15).
`matriks_bawaan_sebelum_PRT9.json` dibuat dari kode SEBELUM unit ini (izin efektif peran bawaan di basis data baru).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import bootstrap
from permissions_config import DEFAULT_PERMISSIONS

pytestmark = pytest.mark.anyio

SEBELUM = json.loads((Path(__file__).parent / "data" / "matriks_bawaan_sebelum_PRT9.json").read_text())
SIMPAN: dict = {}
# Tambahan izin bawaan yang SENGAJA dibuat unit sesudah PR-T9 (berkas "sebelum" tetap foto kode sebelum PR-T9).
TAMBAHAN_SESUDAH = {r: {"inventory": {"configure"}, "goods_receipt": {"configure"}, "makloon": {"configure"}}
                    for r in ("admin", "manager")}   # KF-T1
for _r in ("admin", "manager", "finance"):   # PK-17 — kelola rekening kas & bank
    TAMBAHAN_SESUDAH.setdefault(_r, {})["cash"] = {"configure"}
for _r in DEFAULT_PERMISSIONS:   # PR-T2 — izin pengganti gerbang nama peran (sumber daya & aksi baru, templat asisten)
    for _res, _acts in bootstrap._prt2_default_pairs(_r).items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_acts)
# Butir di `migrations_applied`: 15 butir PR-T9 + `prt2:gerbang-peran` (PR-T2) + `prt4:sifat-peran` dan
# `prt4:izin-kpi-sales` (PR-T4) + `prt5:katalog` (PR-T5) + `crt1:izin-kredit` (CR-T1 — `customer.manage_credit` dibuang).
# PK-22 — + `pk22:izin-penggajian` (pemegang `hr.manage_payroll` diberi `payroll.*`).
JUMLAH_MIGRASI = 21
# Pencabutan izin bawaan yang SENGAJA dibuat unit sesudah PR-T9.
DICABUT_SESUDAH = {r: {"vendor_bill": {"view"}, "landed_cost": {"view"}, "input_tax": {"view"}}
                   for r in ("warehouse", "warehouse_admin")}   # PK-17 (IA-02)
for _r in ("admin", "manager", "sales_admin", "finance"):   # PR-T4 — KPI & komisi sales lain (dulu nama peran)
    TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault("order", set()).add("view_sales_kpi")
# PR-T5 (PR-07) — 14 pasangan yang tidak pernah diperiksa server dihapus dari katalog (termasuk sumber daya `sales_pov`).
import permissions_config as _pc  # noqa: E402
for _r, _perms in SEBELUM.items():
    for _res, _act in _pc.PRT5_REMOVED_PAIRS:
        if _act in (_perms.get(_res) or []):
            DICABUT_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).add(_act)
# KP-T4 (K-47) — Finance menyetujui/menolak tagihan vendor kampanye (dulu lewat nama peran, pintu tanpa izin).
TAMBAHAN_SESUDAH.setdefault("finance", {}).setdefault("vendor_bill", set()).update({"approve", "reject"})
# PK-45 — pesanan tanpa PPN (K-33). Izin kredit PK-45 `customer.manage_credit` dicabut CR-T1 (blok CR-T1 di bawah).
for _r, _tambah in {"admin": {"order": {"tax_override"}},
                    "manager": {"order": {"tax_override"}}}.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# MN-T1 (K-09, K-17) — Finance melihat & membayar hutang, Finance & Manajer mencairkan uang muka
# (`permissions_config.MNT1_DEFAULT_PAIRS`).
for _r, _tambah in _pc.MNT1_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# PK-38 (K-17, IA-12) — Finance membayar kontrabon (view + pay; bukan verify/approve).
TAMBAHAN_SESUDAH.setdefault("finance", {}).setdefault("contra_bon", set()).update({"view", "pay"})
# KP-T8 (KP-32, K-47) — kunci integrasi dijaga izin sendiri `integration.manage` (bawaan Admin; `KPT8_DEFAULT_PAIRS`).
for _r, _tambah in _pc.KPT8_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# PK-30 (IC-10) — harga/PPN antar-PT di luar kontrak: Admin & Manajer (`permissions_config.PK30_OVERRIDE_TERMS_ROLES`).
for _r in _pc.PK30_OVERRIDE_TERMS_ROLES:
    TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault("interco", set()).add("override_terms")
# PM-T1 (K-34) — Admin & Manajer menyetujui perubahan rekening kas/bank (`cash.approve`, `PMT1_DEFAULT_PAIRS`).
for _r, _tambah in _pc.PMT1_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# CR-T1 (K-27–K-29) — profil kredit pelanggan: lihat & ajukan (Admin, Manajer, Finance, Admin Sales, Sales), putus (Admin,
# Manajer; Sales tidak — K-28) — `permissions_config.CRT1_DEFAULT_PAIRS`.
for _r, _tambah in _pc.CRT1_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# AG-T2 (K-45) — Asisten Keuangan `ai_finance.view`: Admin, Manajer, Finance (`permissions_config.AGT2_DEFAULT_PAIRS`).
for _r, _tambah in _pc.AGT2_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# PK-24 (IA-05, K-17) — bayar reimburse & terima pengembalian sisa uang muka `cash_settlement.pay`: Admin, Manajer,
# Finance; `cash_advance.disburse` Manajer & Finance sudah dari MN-T1 (`permissions_config.PK24_DEFAULT_PAIRS`).
for _r, _tambah in _pc.PK24_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)
# PK-22 (FY-09, K-41) — lima izin penggajian `payroll.*`: Admin, Manajer (`permissions_config.PK22_DEFAULT_PAIRS`).
for _r, _tambah in _pc.PK22_DEFAULT_PAIRS.items():
    for _res, _aksi in _tambah.items():
        TAMBAHAN_SESUDAH.setdefault(_r, {}).setdefault(_res, set()).update(_aksi)


def _himpunan(perms: dict) -> dict:
    return {k: set(v) for k, v in (perms or {}).items() if v}


async def _peran(klien, h, rid: str) -> dict:
    r = await klien.get(f"/api/access/roles/{rid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _nyalakan_ulang() -> None:
    await bootstrap.run_bootstrap()


async def test_U01_izin_efektif_sama_dengan_sebelum(klien, kepala_admin):
    r = await klien.get("/api/access/roles", headers=kepala_admin)
    roles = {x["id"]: x for x in r.json()["roles"]}
    assert len(SEBELUM) == 13
    for rid, perms in SEBELUM.items():
        sekarang = _himpunan(roles[rid]["permissions"])
        for res, acts in TAMBAHAN_SESUDAH.get(rid, {}).items():
            sekarang[res] = sekarang.get(res, set()) - acts
        for res, acts in DICABUT_SESUDAH.get(rid, {}).items():
            assert not (sekarang.get(res, set()) & acts), (rid, res)
            sekarang[res] = sekarang.get(res, set()) | acts
        assert {k: v for k, v in sekarang.items() if v} == _himpunan(perms), rid


async def test_U02_sales_kwitansi_dari_bawaan_tidak_bertanda_diubah(klien, kepala_admin):
    s = await _peran(klien, kepala_admin, "sales")
    assert sorted(s["permissions"]["ar_receipt"]) == ["create", "view"]
    assert s["modified"] is False
    assert s["modified_parts"] == []


async def test_U06_start_biasa_tidak_menulis(db):
    awal = await db.permission_settings.find_one({"id": "default"})
    await _nyalakan_ulang()
    await _nyalakan_ulang()
    akhir = await db.permission_settings.find_one({"id": "default"})
    assert akhir["updated_at"] == awal["updated_at"]
    assert len(akhir["migrations_applied"]) == JUMLAH_MIGRASI
    assert len(set(akhir["migrations_applied"])) == JUMLAH_MIGRASI


async def test_U12_kembalikan_bawaan_ikut_menu(klien, kepala_admin):
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin, json={"hidden_views": ["finance-cases"]})
    assert r.status_code == 200, r.text
    f = await _peran(klien, kepala_admin, "finance")
    assert f["modified"] is True
    assert f["modified_parts"] == ["menu"]
    r = await klien.post("/api/access/roles/finance/reset", headers=kepala_admin)
    assert r.status_code == 200, r.text
    f = await _peran(klien, kepala_admin, "finance")
    assert f["hidden_views"] == []
    assert f["modified"] is False


async def test_U03_pencabutan_admin_bertahan(klien, kepala_admin):
    r = await klien.patch("/api/access/roles/sales", headers=kepala_admin, json={"levels": {"ar": "none"}})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    s = await _peran(klien, kepala_admin, "sales")
    assert "ar_receipt" not in s["permissions"], s["permissions"].get("ar_receipt")


async def test_U13_kembalikan_bawaan_lalu_start(klien, kepala_admin):
    r = await klien.post("/api/access/roles/sales/reset", headers=kepala_admin)
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    s = await _peran(klien, kepala_admin, "sales")
    assert sorted(s["permissions"]["ar_receipt"]) == ["create", "view"]
    assert s["modified"] is False


async def test_U04_tambahan_admin_bertahan(klien, kepala_admin):
    g = await _peran(klien, kepala_admin, "warehouse")
    perms = {k: list(v) for k, v in g["permissions"].items()}
    perms["order"] = sorted(set(perms.get("order", [])) | {"confirm"})
    r = await klien.patch("/api/access/roles/warehouse", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    g = await _peran(klien, kepala_admin, "warehouse")
    assert "confirm" in g["permissions"]["order"]


async def test_U05_finance_tanpa_persetujuan_bertahan(klien, kepala_admin):
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin, json={"levels": {"approval": "none"}})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    f = await _peran(klien, kepala_admin, "finance")
    assert "approval" not in f["permissions"]


async def test_U08_peran_kustom_tanpa_perubahan_ikut_izin_baru(klien, kepala_admin, monkeypatch):
    r = await klien.post("/api/access/roles", headers=kepala_admin,
                         json={"label": "Sales Senior", "base_role": "sales", "description": "uji PR-T9"})
    assert r.status_code == 200, r.text
    SIMPAN["senior"] = r.json()["id"]
    r = await klien.post("/api/access/roles", headers=kepala_admin,
                         json={"label": "Sales Sempit", "base_role": "sales", "levels": {"logistics": "view"},
                               "description": "uji PR-T9"})
    assert r.status_code == 200, r.text
    SIMPAN["sempit"] = r.json()["id"]
    monkeypatch.setitem(DEFAULT_PERMISSIONS["sales"], "vehicle_log",
                        list(DEFAULT_PERMISSIONS["sales"]["vehicle_log"]) + ["update"])
    await _nyalakan_ulang()
    s = await _peran(klien, kepala_admin, "sales")
    sr = await _peran(klien, kepala_admin, SIMPAN["senior"])
    assert "update" in s["permissions"]["vehicle_log"]
    assert "update" in sr["permissions"]["vehicle_log"]
    assert sr["pending_from_base_count"] == 0


async def test_U09_peran_kustom_yang_modulnya_diubah_tertunda(klien, kepala_admin):
    sp = await _peran(klien, kepala_admin, SIMPAN["sempit"])
    assert "update" not in (sp["permissions"].get("vehicle_log") or [])
    assert sp["pending_from_base"] == {"vehicle_log": ["update"]}
    assert sp["pending_from_base_count"] == 1


async def test_U10_ikuti_peran_dasar(klien, kepala_admin):
    r = await klien.post(f"/api/access/roles/{SIMPAN['sempit']}/follow-base", headers=kepala_admin, json={})
    assert r.status_code == 200, r.text
    assert "update" in r.json()["permissions"]["vehicle_log"]
    assert r.json()["pending_from_base_count"] == 0
    r = await klien.post(f"/api/access/roles/{SIMPAN['sempit']}/follow-base", headers=kepala_admin, json={})
    assert r.status_code == 400, r.text
    assert r.json()["detail"].startswith("Tidak ada izin baru")


async def test_U14_tanpa_izin_ubah_peran_ditolak(klien, akun, sesi, peran_tanpa_acuan, peran_sopir):
    rid = await peran_tanpa_acuan({"permission": ["view"]}, label="Hanya Lihat Peran")
    for peran in (rid, peran_sopir):
        u = await akun(peran)
        r = await klien.post(f"/api/access/roles/{SIMPAN['sempit']}/follow-base", headers=await sesi(u), json={})
        assert r.status_code == 403, (peran, r.text)


async def test_U11_manajer_kosong_tidak_ikut(klien, kepala_admin, peran_manajer_kosong, monkeypatch):
    kosong = await peran_manajer_kosong()
    monkeypatch.setitem(DEFAULT_PERMISSIONS["manager"], "uom", list(DEFAULT_PERMISSIONS["manager"]["uom"]) + ["update"])
    await _nyalakan_ulang()
    m = await _peran(klien, kepala_admin, "manager")
    k = await _peran(klien, kepala_admin, kosong)
    assert "update" in m["permissions"]["uom"]
    assert not k["permissions"].get("uom")
    assert "update" in (k["pending_from_base"].get("uom") or [])


async def test_U07_butir_migrasi_baru_sekali_jalan(klien, kepala_admin, db, monkeypatch):
    butir = {"id": "revoke:sales:vehicle_log", "kind": "revoke", "role": "sales", "resource": "vehicle_log"}
    monkeypatch.setattr(bootstrap, "PERMISSION_MIGRATIONS",
                        list(getattr(bootstrap, "PERMISSION_MIGRATIONS", [])) + [butir], raising=False)
    await _nyalakan_ulang()
    s = await _peran(klien, kepala_admin, "sales")
    assert "vehicle_log" not in s["permissions"]
    perms = {k: list(v) for k, v in s["permissions"].items()}
    perms["vehicle_log"] = ["view"]
    r = await klien.patch("/api/access/roles/sales", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    s = await _peran(klien, kepala_admin, "sales")
    assert s["permissions"]["vehicle_log"] == ["view"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert rec["migrations_applied"].count("revoke:sales:vehicle_log") == 1


async def test_U15_instalasi_lama_garis_dasar(klien, kepala_admin, db):
    await db.permission_settings.update_one({"id": "default"}, {
        "$unset": {"migrations_applied": "", "matrix.sales.ar_receipt": ""},
        "$set": {"defaults_applied.sales.ar_receipt": ["view"]}})
    await _nyalakan_ulang()
    s = await _peran(klien, kepala_admin, "sales")
    assert "ar_receipt" not in s["permissions"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert "create" in rec["defaults_applied"]["sales"]["ar_receipt"]
    assert len(rec["migrations_applied"]) == JUMLAH_MIGRASI
