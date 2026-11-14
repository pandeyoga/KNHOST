"""PR-T5 — katalog izin dirapikan; modul akses dipecah (docs/blueprint/unit/PR-T5.md, uji U1–U13).

Satu basis data per modul; data berlanjut antar-tes. U14 (sapuan 13 peran bawaan) ada di `test_PRT5_sapuan.py`
(basis data sendiri). Peran uji baku `02_STANDAR.md` §6: "Tanpa Acuan" (dibuat lewat `POST /api/access/roles`),
"Manajer Kosong" (fixture `peran_manajer_kosong`), Sopir (`driver`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import bootstrap
from permissions_config import DEFAULT_PERMISSIONS

pytestmark = pytest.mark.anyio

AKAR = Path(__file__).resolve().parents[2]
PENJAGA = AKAR / "scripts" / "guardrails" / "verify_permission_checked.py"
LIMA = ("accounts", "roles", "entities", "settings", "scheduler")
SIMPAN: dict = {}


async def _buat(klien, h, label: str, **isi) -> dict:
    r = await klien.post("/api/access/roles", headers=h, json={"label": label, "base_role": "", **isi})
    assert r.status_code == 200, r.text
    return r.json()


async def _orang(klien, akun, sesi, rid: str) -> dict:
    return await sesi(await akun(rid))


async def _kustom(klien, kepala_admin) -> str:
    """Satu peran kustom sasaran PATCH (U5, U9) — dibuat sekali per modul."""
    if "kustom" not in SIMPAN:
        SIMPAN["kustom"] = (await _buat(klien, kepala_admin, "Sasaran Ubah PRT5",
                                        permissions={"order": ["view"]}))["id"]
    return SIMPAN["kustom"]


# ── U1 — katalog modul: lima modul baru, tanpa `admin` & `sales_profile`, tiap sumber daya tepat satu modul ─────────
async def test_PRT5_U1_katalog_modul(klien, kepala_admin):
    r = await klien.get("/api/access/modules", headers=kepala_admin)
    assert r.status_code == 200, r.text
    mods = r.json()["modules"]
    ids = [m["id"] for m in mods]
    assert "admin" not in ids and "sales_profile" not in ids, ids
    for mid in LIMA:
        assert mid in ids, mid
    hitung: dict = {}
    for m in mods:
        for res in m["resources"]:
            hitung[res] = hitung.get(res, 0) + 1
    assert {k: v for k, v in hitung.items() if v != 1} == {}
    semua = {res for perms in DEFAULT_PERMISSIONS.values() for res in perms}
    assert semua <= set(hitung), sorted(semua - set(hitung))
    assert "sales_pov" not in hitung


# ── U2 — "kelola akun" tidak lagi membawa peran dan penjadwal ────────────────────────────────────────────────────────
async def test_PRT5_U2_kelola_akun_tanpa_peran_dan_penjadwal(klien, kepala_admin, akun, sesi):
    rid = (await _buat(klien, kepala_admin, "Tanpa Acuan Akun", levels={"accounts": "manage"}))["id"]
    h = await _orang(klien, akun, sesi, rid)
    kode = [(await klien.get(j, headers=h)).status_code
            for j in ("/api/users", "/api/access/roles", "/api/scheduler/settings")]
    assert kode == [200, 403, 403], kode


# ── U3 — id lama `admin` diterima sebagai alias kelima modul; jawaban memakai id baru ───────────────────────────────
async def test_PRT5_U3_alias_admin(klien, kepala_admin):
    j = await _buat(klien, kepala_admin, "Lama", levels={"admin": "manage"})
    for res in ("user", "permission", "settings", "entity", "scheduler"):
        assert j["permissions"].get(res), res
    assert "admin" not in j["levels"], sorted(j["levels"])
    for mid in LIMA:
        assert j["levels"][mid]["level"] == "manage", (mid, j["levels"][mid])
    doc_levels = j["levels"]
    assert set(LIMA) <= set(doc_levels)


# ── U4 — migrasi sekali `prt5:katalog` membuang pasangan mati dari matriks tersimpan ───────────────────────────────
async def test_PRT5_U4_migrasi_membuang_pasangan_mati(klien, kepala_admin, db):
    # Fixture (disisipkan langsung): peran kustom ber-izin mati + garis dasar bawaan lama yang memuatnya.
    rid = "cr_uji_prt5_lama"
    await db.custom_roles.insert_one({"id": rid, "label": "Uji PRT5 Lama", "description": "fixture",
                                      "base_role": "", "levels": {"admin": "manage"},
                                      "pending_defaults": {"sales_pov": ["commercial"]},
                                      "created_at": "2026-11-01T00:00:00+00:00",
                                      "updated_at": "2026-11-01T00:00:00+00:00"})
    rec = await db.permission_settings.find_one({"id": "default"})
    matrix = rec["matrix"]
    matrix[rid] = {"order": ["view", "create", "print"], "reports": ["view", "export"],
                   "sales_pov": ["commercial"], "customer": ["view", "update"]}
    applied = rec.get("defaults_applied") or {}
    applied.setdefault("admin", {})["order"] = list(applied.get("admin", {}).get("order") or []) + ["print"]
    applied.setdefault("sales", {})["sales_pov"] = ["commercial"]
    await db.permission_settings.update_one({"id": "default"}, {
        "$set": {"matrix": matrix, "defaults_applied": applied},
        "$pull": {"migrations_applied": "prt5:katalog"}})
    await bootstrap.run_bootstrap()
    r = await klien.get(f"/api/access/roles/{rid}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    perms = r.json()["permissions"]
    assert "print" not in (perms.get("order") or []), perms.get("order")
    assert "export" not in (perms.get("reports") or []), perms.get("reports")
    assert "sales_pov" not in perms, perms
    assert sorted(perms["order"]) == ["create", "view"] and perms["reports"] == ["view"]
    assert sorted(perms["customer"]) == ["update", "view"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert "prt5:katalog" in rec["migrations_applied"]
    assert "print" not in (rec["defaults_applied"]["admin"].get("order") or [])
    assert "sales_pov" not in rec["defaults_applied"].get("sales", {})
    doc = await db.custom_roles.find_one({"id": rid})
    assert "admin" not in doc["levels"] and set(LIMA) <= set(doc["levels"]), doc["levels"]
    assert "sales_pov" not in (doc.get("pending_defaults") or {})


# ── U5 — aksi yang dihapus ditolak saat menyimpan izin rinci ─────────────────────────────────────────────────────────
async def test_PRT5_U5_aksi_terhapus_ditolak(klien, kepala_admin):
    rid = await _kustom(klien, kepala_admin)
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"permissions": {"order": ["view", "print"]}})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Aksi ['print'] tidak berlaku untuk “Pesanan Penjualan (SO)”."


# ── U6/U7 — Ringkasan laporan dijaga `reports.view`; kecepatan pesanan tetap `order.view` ──────────────────────────
async def test_PRT5_U6_ringkasan_butuh_izin_laporan(klien, kepala_admin, akun, sesi, peran_manajer_kosong,
                                                    peran_sopir):
    rid = (await _buat(klien, kepala_admin, "Tanpa Acuan Laporan", permissions={"reports": ["view"]}))["id"]
    kode = []
    for peran in (rid, await peran_manajer_kosong(), peran_sopir):
        kode.append((await klien.get("/api/reports/summary", headers=await _orang(klien, akun, sesi, peran))).status_code)
    assert kode == [200, 403, 403], kode


async def test_PRT5_U7_izin_pesanan_tanpa_laporan(klien, kepala_admin, akun, sesi):
    rid = (await _buat(klien, kepala_admin, "Tanpa Acuan Pesanan", permissions={"order": ["view"]}))["id"]
    h = await _orang(klien, akun, sesi, rid)
    kode = [(await klien.get(j, headers=h)).status_code
            for j in ("/api/reports/summary", "/api/reports/order-velocity")]
    assert kode == [403, 200], kode


# ── U8 — `md_quality.view` membuka daftar inspeksi ───────────────────────────────────────────────────────────────────
async def test_PRT5_U8_mutu_md_membuka_inspeksi(klien, kepala_admin, akun, sesi):
    rid = (await _buat(klien, kepala_admin, "Tanpa Acuan Mutu MD", permissions={"md_quality": ["view"]}))["id"]
    r = await klien.get("/api/inspections", headers=await _orang(klien, akun, sesi, rid))
    assert r.status_code == 200, r.text


# ── U9 — tingkat yang tidak berlaku untuk modul ditolak ──────────────────────────────────────────────────────────────
async def test_PRT5_U9_tingkat_tidak_berlaku_ditolak(klien, kepala_admin):
    rid = await _kustom(klien, kepala_admin)
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"levels": {"field_visibility": "view"}})
    assert r.status_code == 400, r.text
    assert r.json()["detail"].startswith("Tingkat “Lihat saja” tidak berlaku"), r.json()["detail"]
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"levels": {"approval": "manage"}})
    assert r.status_code == 400, r.text
    assert r.json()["detail"].startswith("Tingkat “Semua aksi” tidak berlaku"), r.json()["detail"]


async def test_PRT5_U9b_katalog_tingkat_pengecualian_dan_aksi_berisiko(klien, kepala_admin):
    """Bagian katalog yang dibaca editor: `levels_available`, `view_excludes`, `sensitive_actions`, label tingkat."""
    j = (await klien.get("/api/access/modules", headers=kepala_admin)).json()
    mods = {m["id"]: m for m in j["modules"]}
    assert mods["field_visibility"]["levels_available"] == ["none", "manage"]
    for mid in ("approval", "manager_home", "costing"):
        assert mods[mid]["levels_available"] == ["none", "view"], mid
    assert mods["penjualan"]["levels_available"] == ["none", "view", "manage"]
    assert "Periode & Tutup Buku" in mods["accounting"]["view_excludes"]
    assert "Amandemen Keuangan" in mods["finance_ops"]["view_excludes"]
    assert any(x.startswith("Harga Pesanan Khusus") for x in mods["penjualan"]["view_excludes"])
    assert mods["penjualan"]["view_excludes"] and not mods["customer"]["view_excludes"]
    assert mods["accounting"]["sensitive_actions"]["period"]["unlock"].startswith("membuka periode")
    assert "manage" in mods["settings"]["sensitive_actions"]["settings"]
    assert j["levels"]["manage"] == "Semua aksi"
    assert mods["field_visibility"]["group"] == "Gudang"
    assert mods["field_visibility"]["label"] == "Melihat grade, nomor lot & asal barang"
    assert [bool(mods[m].get("sensitive")) for m in LIMA] == [True, True, True, True, False]
    assert "pdf-templates" in mods["documents"]["nav"] and "settings-documents" in mods["documents"]["nav"]


# ── U10 — tingkat sebagian membawa jumlah aksi dipegang & total ──────────────────────────────────────────────────────
async def test_PRT5_U10_sebagian_dengan_jumlah_aksi(klien, kepala_admin):
    r = await klien.get("/api/access/roles/sales", headers=kepala_admin)
    assert r.status_code == 200, r.text
    lv = r.json()["levels"]["penjualan"]
    assert lv["level"] == "manage" and lv["partial"] is True, lv
    assert isinstance(lv["held"], int) and isinstance(lv["total"], int), lv
    assert lv["held"] < lv["total"], lv


# ── U11 — satu kamus label untuk semua sumber daya & aksi ────────────────────────────────────────────────────────────
async def test_PRT5_U11_kamus_label(klien, akun, sesi, peran_sopir):
    r = await klien.get("/api/access/labels", headers=await _orang(klien, akun, sesi, peran_sopir))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["resources"]["permission"] == "Peran & Hak Akses"
    tanpa = []
    for perms in DEFAULT_PERMISSIONS.values():
        for res, acts in perms.items():
            if res not in j["resources"]:
                tanpa.append(res)
            if res not in j["modules"]:
                tanpa.append(f"modul:{res}")
            tanpa += [f"{res}.{a}" for a in acts if a not in j["actions"] and f"{res}.{a}" not in j["actions"]]
    assert not tanpa, sorted(set(tanpa))
    assert j["modules"]["user"] == "Akun Pengguna"


# ── U12 — penjaga INV-PERM-01 ────────────────────────────────────────────────────────────────────────────────────────
async def test_PRT5_U12_penjaga_izin_diperiksa():
    for arg in ([], ["--self-test"]):
        p = subprocess.run([sys.executable, str(PENJAGA), *arg], cwd=AKAR, capture_output=True, text=True,
                           timeout=300)
        assert p.returncode == 0, (arg, p.stdout[-2000:], p.stderr[-2000:])


# ── U13 — menu meja peran butuh aksi tertentu, bukan sekadar "ada aksi pada sumber daya" ───────────────────────────
async def test_PRT5_U13_syarat_aksi_menu_meja(klien, kepala_admin, akun, sesi):
    rid = (await _buat(klien, kepala_admin, "Tanpa Acuan Lihat Pesanan", levels={"penjualan": "view"}))["id"]
    r = await klien.get("/api/auth/me", headers=await _orang(klien, akun, sesi, rid))
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["view_actions"]["sales-admin-desk"] == [["order", "confirm"]], me.get("view_actions")
    perms = me["permissions"]

    def terblokir(nid: str) -> bool:   # = `accessBlocks` di frontend/src/config/roles.js
        res = me["view_resources"].get(nid) or []
        if res and not any(perms.get(x) for x in res):
            return True
        need = (me.get("view_actions") or {}).get(nid) or []
        return bool(need) and not any(a in (perms.get(s) or []) for s, a in need)

    assert "sales-admin-desk" in me["view_resources"]
    assert terblokir("sales-admin-desk")
    assert not terblokir("sales-orders")
    r = await klien.post("/api/access/roles/preview", headers=kepala_admin, json={"role_id": rid})
    assert r.status_code == 200, r.text
    assert "sales-admin-desk" not in r.json()["screens"] and "sales-orders" in r.json()["screens"]


async def test_PRT5_U13b_beranda_dan_meja_saya_mengikuti_sifat_peran(klien, kepala_admin):
    """Menu `home` dan `my-desk` peran kustom mengikuti sifat peran (PR-T4), bukan modul."""
    tanpa = (await _buat(klien, kepala_admin, "Tanpa Acuan Menu", permissions={"customer": ["view"]}))["id"]
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Turunan Manajer Menu", "base_role": "manager", "levels": {"customer": "view"}})
    assert r.status_code == 200, r.text
    turunan = r.json()["id"]
    roles = {x["id"]: x for x in (await klien.get("/api/roles", headers=kepala_admin)).json()["roles"]}
    nav_t, nav_m = roles[tanpa]["nav"], roles[turunan]["nav"]
    assert "home" in nav_t["remove"] and "my-desk" in nav_t["remove"], nav_t
    assert "home" in nav_m["add"] and "my-desk" in nav_m["add"], nav_m
