"""MN-T1 — menu keuangan dan SDM: pindah dan kelompokkan tanpa mengubah isi layar (docs/blueprint/unit/MN-T1.md).

Lapis B (database tiruan): U4 (izin ↔ endpoint utama tiap view pada tabel lama → baru), U11 (menu peran kustom dari
modul pemilik `order`), U12 (`hidden_views` berisi id grup `kas-aset` yang hilang), U13 (izin bawaan Finance menurut
K-09/K-17). Tabel bantu `frontend/src/config/__tests__/fixtures/view_main_permission.json` = sumber yang sama dengan uji
komponen U3. Uji komponen U1–U3, U5–U10 di jest (`config/__tests__/mnt1MenuKeuangan.test.js`).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

TABEL = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "__tests__" / "fixtures"
                    / "view_main_permission.json").read_text(encoding="utf-8"))["views"]
#: (view, sumber daya, aksi, endpoint) — satu baris per pasangan izin alternatif.
BARIS = [(v, r, a, (t.get("endpoint_per_izin") or {}).get(f"{r}.{a}", t["endpoint"]))
         for v, t in sorted(TABEL.items()) for r, a in t["izin"]]


@pytest.fixture(scope="module")
async def kepala_untuk(klien, akun, sesi, peran_tanpa_acuan):
    """Sesi akun berperan kustom Tanpa Acuan yang memegang TEPAT satu pasangan izin (satu peran per pasangan)."""
    simpan: dict = {}

    async def _kepala(res: str, act: str) -> dict:
        if (res, act) not in simpan:
            rid = await peran_tanpa_acuan({res: [act]}, label=f"Tanpa Acuan {res}.{act}")
            simpan[(res, act)] = await sesi(await akun(rid))
        return simpan[(res, act)]
    return _kepala


async def test_MNT1_U04_satu_pasangan_izin_membuka_endpoint_utama(klien, kepala_untuk):
    # Tiap baris tabel bantu: peran Tanpa Acuan berizin tepat satu pasangan → GET endpoint utama view itu tidak 403.
    assert len(BARIS) >= 40
    ditolak = []
    for view, res, act, ep in BARIS:
        r = await klien.get(ep, headers=await kepala_untuk(res, act))
        if r.status_code == 403:
            ditolak.append(f"{view} · {res}.{act} · {ep} → 403 {r.text[:120]}")
    assert ditolak == []


async def test_MNT1_U04b_manajer_kosong_ditolak_tiap_baris(klien, akun, sesi, peran_manajer_kosong):
    h = await sesi(await akun(await peran_manajer_kosong()))
    lolos = []
    for view, res, act, ep in BARIS:
        r = await klien.get(ep, headers=h)
        if r.status_code != 403:
            lolos.append(f"{view} · {ep} → {r.status_code}")
    assert lolos == []


async def test_MNT1_U11_modul_pesanan_lihat_saja_membuka_piutang_penagihan(klien, kepala_admin):
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Tanpa Acuan Pesanan Lihat", "base_role": "", "description": "peran uji",
        "levels": {"penjualan": "view"}})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    # Menu peran kustom = `nav` di `GET /api/roles` (dibaca `roles.registerDynamicRoles` di layar).
    r = await klien.get("/api/roles", headers=kepala_admin)
    assert r.status_code == 200, r.text
    lst = r.json()["roles"] if isinstance(r.json(), dict) else r.json()
    add = set(next(x for x in lst if x["id"] == rid)["nav"]["add"])
    assert {"keuangan", "ar-aging", "collection-worklist"} <= add, sorted(add)
    assert "vendor-bills" not in add
    # SDM › Kinerja & Insentif › Kinerja Sales dulu dibuka modul pemilik `order` (endpoint /api/sales/kpi = order.view).
    # KM-T5 — tab Kinerja Sales dicabut (alias ke Capaian, modul Kinerja & Insentif) → modul ini tidak lagi membuka hub SDM.
    assert not ({"hrd", "hr-kpi-hub", "sales-performance"} & add), sorted(add)


async def test_MNT1_U12_hidden_views_kas_aset_dibuang_saat_dimuat(klien, db, kepala_admin):
    # Fixture: peran kustom yang menyimpan id grup `kas-aset` (dihapus unit ini) di `hidden_views` — ditulis langsung.
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Penyembunyi Kas & Aset", "base_role": "finance", "description": "peran uji"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    await db.permission_settings.update_one({"id": "default"},
                                            {"$set": {f"hidden_views.{rid}": ["finance-cases", "kas-aset"]}})
    r = await klien.get(f"/api/access/roles/{rid}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["hidden_views"] == ["finance-cases"]
    # Menyimpan ulang daftar yang dimuat (alur editor peran) tidak 400 "Menu/tab tidak dikenal".
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"hidden_views": r.json()["hidden_views"]})
    assert r.status_code == 200, r.text
    lst = (await klien.get("/api/access/roles", headers=kepala_admin)).json()["roles"]
    assert next(x for x in lst if x["id"] == rid)["hidden_views"] == ["finance-cases"]


async def test_MNT1_U13_finance_melihat_hutang_dan_mencairkan_uang_muka(klien, db, akun, sesi):
    keu = await akun("finance")
    h = await sesi(keu)
    for ep in ("/api/vendor-bills", "/api/contra-bons"):
        r = await klien.get(ep, headers=h)
        assert r.status_code == 200, (ep, r.status_code, r.text)
    # Fixture: PD berstatus disetujui di PT akun itu (disisipkan langsung).
    ca = {"id": f"ca_mnt1_{uuid.uuid4().hex[:6]}", "number": f"PD-MNT1-{uuid.uuid4().hex[:5]}", "entity_id": "ent_ksc",
          "status": "approved", "lines": [{"description": "bensin", "amount": 150000}], "total_amount": 150000,
          "approvals": [], "kegiatan": "uji MN-T1", "created_by": keu["name"], "created_by_id": keu["id"],
          "created_at": now_iso()}
    await db.cash_advances.insert_one(dict(ca))
    # PK-20 — kas wajib berekening: fixture satu rekening Kas Kecil milik PT itu (rekening tunggal → dipakai otomatis).
    if not await db.bank_accounts.find_one({"entity_id": "ent_ksc", "cash_type": "kas_kecil"}):
        await db.bank_accounts.insert_one({"id": f"rek_mnt1_{uuid.uuid4().hex[:6]}", "name": "Kas Kecil (uji MN-T1)",
                                           "account_type": "cash", "cash_type": "kas_kecil", "entity_id": "ent_ksc",
                                           "is_active": True})
    r = await klien.post(f"/api/cash-advances/{ca['id']}/disburse", headers=h, json={"cash_type": "kas_kecil", "note": "uji"})
    assert r.status_code != 403, r.text          # harapan spesifikasi
    assert r.status_code == 200, r.text          # di database tiruan: pencairan tercatat
    assert (await db.cash_advances.find_one({"id": ca["id"]}))["status"] != "approved"


async def test_MNT1_U13b_izin_bawaan_finance_dan_manajer(klien, kepala_admin):
    f = (await klien.get("/api/access/roles/finance", headers=kepala_admin)).json()["permissions"]
    assert {"view", "pay"} <= set(f["vendor_bill"]) and {"view", "pay"} <= set(f["contra_bon"])
    assert "disburse" in f["cash_advance"]
    assert {"view", "create"} <= set(f["cash"]) and "view" in f["accounting"]          # K-09 (sudah ada)
    assert not ({"create", "void", "manage"} & set(f["accounting"]))                   # Buku Besar lihat saja
    m = (await klien.get("/api/access/roles/manager", headers=kepala_admin)).json()["permissions"]
    assert "disburse" in m["cash_advance"]
