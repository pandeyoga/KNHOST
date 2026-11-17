"""PK-47 — lima cacat kecil dari uji sapuan endpoint (docs/blueprint/unit/PK-47.md).

Fixture: PT uji `ent_uji_t` (CV, `is_test`), barang `prd_y` (yard, gramasi 150, lebar 1.5), PO `po_a` (ent_ksc, tingkat
manager), `po_c`/`po_d` (ent_kanda, tingkat finance), `po_e` (ent_kanda, tingkat manager); akun `fin` (penyetuju PO
hanya ent_ksc — K-FIN-01: peran kustom tanpa acuan berizin PO, karena Finance kini lintas PT seperti Manajer), `sopir`.
"""
from __future__ import annotations

import datetime

import pytest

from pembantu import jumlah

pytestmark = pytest.mark.anyio


def _po(pid: str, ent: str, peran: str) -> dict:
    return {"id": pid, "po_number": pid.upper(), "status": "waiting_approval", "approval_status": "pending",
            "required_approval_role": peran, "entity_id": ent, "created_by_id": "usr_orang_lain",
            "created_by": "Orang Lain", "version": 1, "total_amount": 250_000_000, "subtotal": 250_000_000,
            "supplier_id": "sup_x", "supplier_name": "Pemasok Uji", "lines": [], "timeline": [],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}


@pytest.fixture(scope="module")
async def siap(db, akun, sesi, peran_sopir, peran_tanpa_acuan):
    await db.business_entities.insert_one({"id": "ent_uji_t", "status": "active", "is_test": True, "type": "CV",
                                           "legal_name": "CV Uji Sapuan", "short_name": "Uji Sapuan",
                                           "doc_prefix": "UJT", "created_at": "2026-11-13T00:00:00+00:00"})
    await db.products.insert_one({"id": "prd_y", "sku": "PRD-Y", "name": "Kain Yard Uji", "base_unit": "yard",
                                  "gramasi": 150, "lebar": 1.5, "status": "active", "category": "Uji",
                                  "created_at": "2026-11-13T00:00:00+00:00"})
    await db.purchase_orders.insert_many([_po("po_a", "ent_ksc", "manager"), _po("po_c", "ent_kanda", "finance"),
                                          _po("po_d", "ent_kanda", "finance"), _po("po_e", "ent_kanda", "manager")])
    # K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance bawaan kini lintas PT (setara Manajer), jadi pagar PT penugasan
    # diuji dengan peran kustom tanpa acuan yang memegang izin setujui/tolak PO (bawaan: tidak lintas PT).
    fin = await akun(await peran_tanpa_acuan({"purchase_order": ["view", "approve", "reject"]},
                                             label="Penyetuju PO satu PT"), entitas=("ent_ksc",))
    sopir = await akun(peran_sopir)
    return {"fin": await sesi(fin), "sopir": await sesi(sopir)}


async def _jumlah_daftar(klien, h, **params) -> int:
    r = await klien.get("/api/entities", headers=h, params={"limit": 500, **params})
    assert r.status_code == 200, r.text
    return len(r.json())


async def test_U01_hitung_pt_sama_dengan_daftar(klien, kepala_admin, siap):
    r = await klien.get("/api/entities/count", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == await _jumlah_daftar(klien, kepala_admin)


async def test_U02_hitung_termasuk_pt_uji(klien, kepala_admin, siap):
    dasar = (await klien.get("/api/entities/count", headers=kepala_admin)).json()["count"]
    r = await klien.get("/api/entities/count", headers=kepala_admin, params={"include_test": "true"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == dasar + 1


async def test_U03_hitung_semua_status(klien, kepala_admin, siap):
    r = await klien.get("/api/entities/count", headers=kepala_admin, params={"status": "all", "include_test": "true"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == await jumlah("business_entities", {})


async def test_U04_hitung_cari_dan_jenis(klien, kepala_admin, siap):
    r = await klien.get("/api/entities/count", headers=kepala_admin, params={"include_test": "true", "q": "Uji Sapuan"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1
    r = await klien.get("/api/entities/count", headers=kepala_admin, params={"include_test": "true", "type": "CV"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == await _jumlah_daftar(klien, kepala_admin, include_test="true", type="CV")


async def test_U05_hitung_dijaga_izin_sejak_PRT3(klien, siap):
    # PK-47 U5 dulu "200 (cukup login)". Unit PR-T3 (S5, docs/blueprint/unit/PR-T3.md) memberi penghitung ini gerbang
    # `entity.view` — pemanggilnya hanya layar Badan Usaha & Akses — sehingga Sopir kini 403 (lihat hasil/PR-T3.md).
    r = await klien.get("/api/entities/count", headers=siap["sopir"])
    assert r.status_code == 403, r.text


async def test_U06_baca_satu_barang(klien, kepala_admin, siap):
    r = await klien.get("/api/products/prd_y", headers=kepala_admin)
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["id"], b["base_unit"], b["gramasi"], b["lebar"]) == ("prd_y", "yard", 150, 1.5)
    assert "hpp" not in b and "price_source" not in b


async def test_U07_barang_tidak_ada(klien, kepala_admin, siap):
    r = await klien.get("/api/products/tidak_ada", headers=kepala_admin)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Produk tidak ditemukan"


async def test_U08_baca_barang_butuh_izin_lihat(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, siap):
    p = await peran_tanpa_acuan({"product": ["view"]}, label="Lihat Barang")
    r = await klien.get("/api/products/prd_y", headers=await sesi(await akun(p)))
    assert r.status_code == 200, r.text
    r = await klien.get("/api/products/prd_y", headers=await sesi(await akun(await peran_manajer_kosong())))
    assert r.status_code == 403, r.text


async def test_U09_rute_pemilik_sales_tidak_tertelan(klien, kepala_admin, siap):
    r = await klien.get("/api/products/sales-owners", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


async def test_U10_rekap_klaim_makloon(klien, akun, sesi, peran_tanpa_acuan, siap):
    p = await peran_tanpa_acuan({"accounting": ["view"]}, label="Lihat Akuntansi")
    r = await klien.get("/api/makloon-claims/recap", headers=await sesi(await akun(p)))
    assert r.status_code == 200, r.text
    r = await klien.get("/api/makloon-claims/recap", headers=siap["sopir"])
    assert r.status_code == 403, r.text


async def test_U11_setuju_po_pt_lain_ditolak(klien, db, siap):
    r = await klien.get("/api/purchase-orders/po_c", headers=siap["fin"])
    assert r.status_code == 404, r.text
    r = await klien.post("/api/purchase-orders/po_c/approve", headers=siap["fin"], json={})
    assert r.status_code == 404, r.text
    d = await db.purchase_orders.find_one({"id": "po_c"})
    assert d["status"] == "waiting_approval" and not d.get("approved_by")


async def test_U12_tolak_po_pt_lain_ditolak(klien, db, siap):
    r = await klien.post("/api/purchase-orders/po_d/reject", headers=siap["fin"], json={"reason": "uji tolak"})
    assert r.status_code == 404, r.text
    assert (await db.purchase_orders.find_one({"id": "po_d"}))["status"] == "waiting_approval"


async def test_U13_setuju_po_pt_sendiri_tetap(klien, db, sesi, siap):
    r = await klien.post("/api/purchase-orders/po_a/approve", headers=await sesi("manager@kainnusantara.id"), json={})
    assert r.status_code == 200, r.text
    assert (await db.purchase_orders.find_one({"id": "po_a"}))["status"] == "pending"


async def test_U14_kode_setuju_mengikuti_kode_baca(klien, sesi, siap):
    h = await sesi("manager@kainnusantara.id", entitas="ent_ksc")
    baca = await klien.get("/api/purchase-orders/po_e", headers=h)
    setuju = await klien.post("/api/purchase-orders/po_e/approve", headers=h, json={})
    assert baca.status_code in (200, 404), baca.text
    assert setuju.status_code == baca.status_code, (baca.status_code, setuju.text)


async def test_U15_setuju_po_tidak_ada(klien, kepala_admin, siap):
    r = await klien.post("/api/purchase-orders/tidak_ada/approve", headers=kepala_admin, json={})
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Purchase Order tidak ditemukan"


async def test_U16_setuju_retur_antar_pt_tidak_ada(klien, kepala_admin, siap):
    r = await klien.post("/api/interco/returns/tidak_ada/approve", headers=kepala_admin, json={"note": ""})
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Dokumen retur tidak ditemukan."


async def test_U17_setuju_retur_tanpa_izin(klien, siap):
    r = await klien.post("/api/interco/returns/tidak_ada/approve", headers=siap["sopir"], json={"note": ""})
    assert r.status_code == 403, r.text
