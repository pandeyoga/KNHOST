"""KA-8 — API layar tarif per artikel: daftar kategori/artikel/varian, ubah banyak, Excel, simulasi.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.2, §6.6. Fixture DISISIP langsung (PT `ent_ksc`):

  Artikel aktif   Batik Mega (BTK-M8, kategori KA8Batik, varian merah & biru) · Batik Parang (BTK-P8, KA8Batik)
                  · Lurik Sawo (LRK-S8, KA8Lurik) · Batik Lawas (BTK-L8, status archived — tidak tampil).
  Tarif           kategori KA8Batik Rp 3.000 (Semua PT) · artikel Mega Rp 3.500 (PT ini, batas margin 0) ·
                  varian biru Rp 4.000 (PT ini).

Hitung tangan simulasi (U7, periode 2026-11, fraksi terbayar 1): pesanan dipotret saat tarif artikel Mega 3.500 →
100 yd × 3.500 = 350.000 (sekarang). Draf tarif artikel Mega 4.000 → 100 × 4.000 = 400.000 (dengan perubahan).
"""
from __future__ import annotations

import io
from typing import Any, Dict

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
PERIODE = "2026-11"
MEGA, PARANG, LURIK, LAWAS = "tpl_ka8_mega", "tpl_ka8_prg", "tpl_ka8_lrk", "tpl_ka8_lws"
MRH, BRU = "prd_ka8_mega_mrh", "prd_ka8_mega_bru"


def _rate(rid: str, ent: str, rk: str, per_unit: float, **lain) -> Dict[str, Any]:
    d = {"id": rid, "entity_id": ent, "category": "KA8Batik", "template_id": "", "product_id": "", "rate_key": rk,
         "per_unit_amount": per_unit, "margin_cap_pct": 0.0, "status": "active", "created_at": now_iso()}
    d.update(lain)
    return d


@pytest.fixture(scope="module")
async def f8(db):
    await db.product_templates.insert_many([
        {"id": MEGA, "name": "Batik Mega", "sku_prefix": "BTK-M8", "category": "KA8Batik", "status": "active"},
        {"id": PARANG, "name": "Batik Parang", "sku_prefix": "BTK-P8", "category": "KA8Batik", "status": "active"},
        {"id": LURIK, "name": "Lurik Sawo", "sku_prefix": "LRK-S8", "category": "KA8Lurik", "status": "active"},
        {"id": LAWAS, "name": "Batik Lawas", "sku_prefix": "BTK-L8", "category": "KA8Batik", "status": "archived"}])
    await db.products.insert_many([
        {"id": MRH, "sku": "BTK-M8-MRH", "name": "Batik Mega Merah", "category": "KA8Batik", "template_id": MEGA,
         "base_unit": "yard", "status": "active", "is_active": True},
        {"id": BRU, "sku": "BTK-M8-BRU", "name": "Batik Mega Biru", "category": "KA8Batik", "template_id": MEGA,
         "base_unit": "yard", "status": "active", "is_active": True},
        {"id": "prd_ka8_prg", "sku": "BTK-P8-01", "name": "Batik Parang 01", "category": "KA8Batik",
         "template_id": PARANG, "base_unit": "yard", "status": "active", "is_active": True},
        {"id": "prd_ka8_lrk", "sku": "LRK-S8-01", "name": "Lurik Sawo 01", "category": "KA8Lurik", "template_id": LURIK,
         "base_unit": "yard", "status": "active", "is_active": True}])
    await db.incentive_rates.insert_many([
        _rate("irate_ka8_kat", "all", "kategori:KA8Batik", 3000.0, margin_cap_pct=50.0),
        _rate("irate_ka8_mega", KSC, f"artikel:{MEGA}", 3500.0, template_id=MEGA, target_name="Batik Mega",
              target_code="BTK-M8"),
        _rate("irate_ka8_bru", KSC, f"varian:{BRU}", 4000.0, product_id=BRU, target_name="Batik Mega Biru",
              target_code="BTK-M8-BRU")])
    return True


def _item(r: Dict[str, Any], template_id: str) -> Dict[str, Any]:
    return next(i for i in r.json()["items"] if i["template_id"] == template_id)


async def test_KA8_U0_daftar_kategori(klien, kepala_admin, f8):
    r = await klien.get(f"/api/incentive-rates/categories?entity_id={KSC}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    items = {i["category"]: i for i in r.json()["items"]}
    assert [i["category"] for i in r.json()["items"]] == sorted(items)          # urut nama
    b = items["KA8Batik"]
    assert b["rate"] == {"per_unit_amount": 3000.0, "margin_cap_pct": 50.0, "asal_lingkup": "semua_pt",
                         "rate_id": "irate_ka8_kat"}
    assert (b["articles"], b["articles_own_rate"]) == (2, 1)     # arsip tidak dihitung; hanya Mega bertarif sendiri
    assert items["KA8Lurik"]["rate"] is None and items["KA8Lurik"]["articles"] == 1


async def test_KA8_U1_daftar_artikel_tarif_efektif(klien, kepala_admin, f8):
    r = await klien.get(f"/api/incentive-rates/articles?entity_id={KSC}&category=KA8Batik", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["total"], j["page"], j["page_size"]) == (2, 1, 50)           # Batik Lawas (arsip) tidak tampil
    assert [i["name"] for i in j["items"]] == ["Batik Mega", "Batik Parang"]
    mega, parang = _item(r, MEGA), _item(r, PARANG)
    assert (mega["code"], mega["category"], mega["own_rate_id"], mega["variant_exceptions"]) == (
        "BTK-M8", "KA8Batik", "irate_ka8_mega", 1)
    assert mega["rate"] == {"per_unit_amount": 3500.0, "margin_cap_pct": 0.0, "asal_tingkat": "artikel",
                            "asal_lingkup": "pt", "rate_id": "irate_ka8_mega"}
    assert parang["own_rate_id"] is None and parang["variant_exceptions"] == 0
    assert (parang["rate"]["per_unit_amount"], parang["rate"]["asal_tingkat"], parang["rate"]["asal_lingkup"]) == (
        3000.0, "kategori", "semua_pt")
    # cari + halaman: tidak ada pemotongan diam-diam
    r = await klien.get(f"/api/incentive-rates/articles?entity_id={KSC}&search=btk-p8", headers=kepala_admin)
    assert [i["name"] for i in r.json()["items"]] == ["Batik Parang"]
    r = await klien.get(f"/api/incentive-rates/articles?entity_id={KSC}&page=2&page_size=2", headers=kepala_admin)
    assert (r.json()["total"], len(r.json()["items"]), r.json()["page"]) == (3, 1, 2)
    # Lurik tanpa tarif sama sekali
    lurik = _item(await klien.get(f"/api/incentive-rates/articles?entity_id={KSC}&category=KA8Lurik",
                                  headers=kepala_admin), LURIK)
    assert lurik["rate"] is None


async def test_KA8_U2_varian_ikut_artikel(klien, kepala_admin, f8):
    r = await klien.get(f"/api/incentive-rates/articles/{MEGA}/variants?entity_id={KSC}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    v = {i["product_id"]: i for i in r.json()["items"]}
    assert (v[MRH]["follows"], v[MRH]["rate"]["per_unit_amount"], v[MRH]["sku"]) == ("artikel", 3500.0, "BTK-M8-MRH")
    assert (v[BRU]["follows"], v[BRU]["rate"]["per_unit_amount"]) == ("varian", 4000.0)    # tarif sendiri
    r = await klien.get(f"/api/incentive-rates/articles/{PARANG}/variants?entity_id={KSC}", headers=kepala_admin)
    assert [i["follows"] for i in r.json()["items"]] == ["kategori"]
    r = await klien.get(f"/api/incentive-rates/articles/{LURIK}/variants?entity_id={KSC}", headers=kepala_admin)
    assert [(i["follows"], i["rate"]) for i in r.json()["items"]] == [("tanpa_tarif", None)]
    r = await klien.get(f"/api/incentive-rates/articles/tpl_tak_ada/variants?entity_id={KSC}", headers=kepala_admin)
    assert (r.status_code, r.json()["detail"]) == (404, "Artikel tidak ditemukan.")


async def test_KA8_U3_ubah_banyak(klien, kepala_admin, db, f8):
    r = await klien.post("/api/incentive-rates/bulk", headers=kepala_admin,
                         json={"entity_id": KSC, "template_ids": [MEGA, PARANG], "per_unit_amount": 3600,
                               "reason": "Kenaikan Desember KA8"})
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 1, "updated": 1}          # Mega sudah bertarif → ubah; Parang baru
    mega = await db.incentive_rates.find_one({"id": "irate_ka8_mega"})
    prg = await db.incentive_rates.find_one({"entity_id": KSC, "rate_key": f"artikel:{PARANG}"})
    assert (mega["per_unit_amount"], mega["margin_cap_pct"]) == (3600, 0.0)        # batas margin lama tidak disentuh
    assert prg["per_unit_amount"] == 3600 and prg["category"] == "KA8Batik" and prg["target_code"] == "BTK-P8"
    assert prg["margin_cap_pct"] == 50.0                                           # bawaan PT untuk tarif baru
    logs = await db.audit_logs.find({"entity_type": "incentive_rate", "reason": "Kenaikan Desember KA8"}).to_list(10)
    assert sorted(x["entity_id"] for x in logs) == sorted(["irate_ka8_mega", prg["id"]])
    # artikel tidak dikenal → 400, tak ada yang berubah
    r = await klien.post("/api/incentive-rates/bulk", headers=kepala_admin,
                         json={"entity_id": KSC, "template_ids": [LURIK, "tpl_tak_ada"], "per_unit_amount": 1})
    assert (r.status_code, r.json()["detail"]) == (400, "Artikel tidak ditemukan.")
    assert await db.incentive_rates.count_documents({"rate_key": f"artikel:{LURIK}"}) == 0
    r = await klien.post("/api/incentive-rates/bulk", headers=kepala_admin,
                         json={"entity_id": KSC, "template_ids": [LURIK], "per_unit_amount": -5})
    assert r.status_code == 400, r.text
    # kembalikan Mega 3.500 untuk uji berikut
    await db.incentive_rates.update_one({"id": "irate_ka8_mega"}, {"$set": {"per_unit_amount": 3500.0}})
    await db.incentive_rates.delete_one({"id": prg["id"]})


async def test_KA8_U4_izin(klien, f8, peran_tanpa_acuan, sesi, akun):
    rid = await peran_tanpa_acuan({"sales_force": ["view"]}, label="Lihat tarif KA8")
    h = await sesi(await akun(rid, entitas=(KSC,)), entitas=KSC)
    r = await klien.get(f"/api/incentive-rates/articles?entity_id={KSC}", headers=h)
    assert r.status_code == 200, r.text
    for rute, isi in (("bulk", {"entity_id": KSC, "template_ids": [MEGA], "per_unit_amount": 1}),
                      ("import/apply", {"entity_id": KSC, "rows": [{"template_id": MEGA, "per_unit_amount": 1}]})):
        r = await klien.post(f"/api/incentive-rates/{rute}", headers=h, json=isi)
        assert r.status_code == 403, (rute, r.text)
    r = await klien.post("/api/incentive-rates/import/preview", headers=h, data={"entity_id": KSC},
                         files={"file": ("t.xlsx", b"x", "application/octet-stream")})
    assert r.status_code == 403, r.text
    for rute in ("categories", "export"):
        assert (await klien.get(f"/api/incentive-rates/{rute}?entity_id={KSC}", headers=h)).status_code == 200


def _muat(isi: bytes):
    from openpyxl import load_workbook
    return load_workbook(io.BytesIO(isi))


def _unggah(ws_wb) -> bytes:
    buf = io.BytesIO()
    ws_wb.save(buf)
    return buf.getvalue()


async def _pratinjau(klien, h, isi: bytes):
    return await klien.post("/api/incentive-rates/import/preview", headers=h, data={"entity_id": KSC},
                            files={"file": ("tarif.xlsx", isi, "application/vnd.openxmlformats-officedocument."
                                                              "spreadsheetml.sheet")})


async def test_KA8_U5_excel_unduh_unggah(klien, kepala_admin, db, f8):
    r = await klien.get(f"/api/incentive-rates/export?entity_id={KSC}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"] and ".xlsx" in r.headers["content-disposition"]
    wb = _muat(r.content)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert list(rows[0]) == ["Kode artikel", "Nama artikel", "Kategori", "Kode varian", "Tarif per satuan dasar",
                             "Batas margin %", "Asal tarif"]
    kode = {(r_[0], r_[3]): r_ for r_ in rows[1:]}
    assert (BTK := kode[("BTK-M8", None)])[4] == 3500 and BTK[6] == "Tarif artikel (PT ini)"
    assert kode[("BTK-M8", "BTK-M8-BRU")][4] == 4000                       # pengecualian varian = satu baris sendiri
    assert kode[("BTK-P8", None)][4] == 3000 and kode[("BTK-P8", None)][6] == "Tarif kategori (Semua PT)"
    assert ("BTK-L8", None) not in kode                                    # arsip tidak diekspor
    # ubah satu tarif (Parang 3000 → 3300) → pratinjau
    for row in ws.iter_rows(min_row=2):
        if row[0].value == "BTK-P8" and row[3].value is None:
            row[4].value = 3300
    r = await _pratinjau(klien, kepala_admin, _unggah(wb))
    assert r.status_code == 200, r.text
    hasil = {(x["kode_artikel"], x["kode_varian"]): x for x in r.json()["rows"]}
    p = hasil[("BTK-P8", "")]
    assert (p["status"], p["lama"], p["baru"], p["template_id"], p["product_id"]) == ("baru", 3000, 3300, PARANG, "")
    assert {x["status"] for k, x in hasil.items() if k != ("BTK-P8", "")} == {"sama"}
    assert await db.incentive_rates.count_documents({"rate_key": f"artikel:{PARANG}"}) == 0    # pratinjau tak menulis
    # ubah tarif Mega 3500 → 3550: status "ubah"
    for row in ws.iter_rows(min_row=2):
        if row[0].value == "BTK-M8" and row[3].value is None:
            row[4].value = 3550
    r = await _pratinjau(klien, kepala_admin, _unggah(wb))
    mega = {(x["kode_artikel"], x["kode_varian"]): x for x in r.json()["rows"]}[("BTK-M8", "")]
    assert (mega["status"], mega["lama"], mega["baru"]) == ("ubah", 3500, 3550)
    # terapkan hanya baris Mega
    r = await klien.post("/api/incentive-rates/import/apply", headers=kepala_admin,
                         json={"entity_id": KSC, "reason": "Unggah Excel KA8",
                               "rows": [{"template_id": MEGA, "per_unit_amount": 3550}]})
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 0, "updated": 1}
    assert (await db.incentive_rates.find_one({"id": "irate_ka8_mega"}))["per_unit_amount"] == 3550
    await db.incentive_rates.update_one({"id": "irate_ka8_mega"}, {"$set": {"per_unit_amount": 3500.0}})


async def test_KA8_U6_excel_kode_tak_dikenal(klien, kepala_admin, db, f8):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Kode artikel", "Nama artikel", "Kategori", "Kode varian", "Tarif per satuan dasar", "Batas margin %",
               "Asal tarif"])
    ws.append(["XX-999", "Entah", "KA8Batik", None, 1000, None, ""])
    ws.append(["BTK-P8", "Batik Parang", "KA8Batik", None, 3300, None, ""])
    ws.append(["BTK-P8", "Batik Parang", "KA8Batik", "TAK-ADA", 3300, None, ""])
    ws.append(["BTK-P8", "Batik Parang", "KA8Batik", None, "abc", None, ""])
    r = await _pratinjau(klien, kepala_admin, _unggah(wb))
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert [x["baris"] for x in rows] == [2, 3, 4, 5]
    assert (rows[0]["status"], rows[0]["pesan"]) == ("galat", "Artikel XX-999 tidak ditemukan.")
    assert rows[1]["status"] == "baru"
    assert (rows[2]["status"], rows[2]["pesan"]) == ("galat", "Varian TAK-ADA tidak ditemukan.")
    assert rows[3]["status"] == "galat"
    # apply tanpa baris galat; baris tanpa id sah ditolak seluruhnya
    r = await klien.post("/api/incentive-rates/import/apply", headers=kepala_admin,
                         json={"entity_id": KSC, "rows": [{"template_id": PARANG, "per_unit_amount": 3300},
                                                          {"per_unit_amount": 1000}]})
    assert r.status_code == 400, r.text
    assert await db.incentive_rates.count_documents({"rate_key": f"artikel:{PARANG}"}) == 0
    r = await klien.post("/api/incentive-rates/import/apply", headers=kepala_admin,
                         json={"entity_id": KSC, "rows": [{"template_id": PARANG, "per_unit_amount": 3300}]})
    assert r.json() == {"created": 1, "updated": 0}, r.text
    await db.incentive_rates.delete_one({"entity_id": KSC, "rate_key": f"artikel:{PARANG}"})
    # berkas bukan xlsx → 400
    r = await _pratinjau(klien, kepala_admin, b"bukan excel")
    assert r.status_code == 400, r.text


async def test_KA8_U7_simulasi(klien, kepala_admin, db, akun, f8):
    from services.commission_rules import potret_pesanan
    sales = await akun("sales", entitas=(KSC,))
    await db.customers.insert_one({"id": "cus_ka8", "name": "Toko KA8", "entity_id": KSC, "status": "active",
                                   "assigned_sales_id": sales["id"]})
    item = {"product_id": MRH, "sku": "BTK-M8-MRH", "product_name": "Batik Mega Merah", "category": "KA8Batik",
            "quantity": 100, "base_quantity": 100, "unit": "yard", "base_unit": "yard", "price": 50_000,
            "line_total": 5_000_000, "discount_percent": 0, "unit_cost": 0, "price_source": "entity"}
    prods = {p["id"]: p async for p in db.products.find({"id": MRH}, {"_id": 0})}
    await potret_pesanan(KSC, [item], prods)           # potret: tarif artikel Mega 3.500 (PT ini)
    await db.sales_orders.insert_one({
        "id": "so_ka8", "number": "SO/KA8/0001", "entity_id": KSC, "customer_id": "cus_ka8", "status": "completed",
        "items": [item], "subtotal": 5_000_000, "grand_total": 5_000_000,
        "payments": [{"amount": 5_000_000, "created_at": "2026-11-10T03:00:00+00:00"}],
        "created_at": "2026-11-02T03:00:00+00:00", "updated_at": now_iso()})
    badan = {"entity_id": KSC, "sales_id": sales["id"], "period": PERIODE,
             "draft_rates": [{"template_id": MEGA, "per_unit_amount": 4000, "margin_cap_pct": 0}]}
    r = await klien.post("/api/incentive-rates/simulate", headers=kepala_admin, json=badan)
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["sekarang"]["total_incentive"], j["dengan_perubahan"]["total_incentive"]) == (350_000, 400_000)
    assert j["dengan_perubahan"]["breakdown"][0]["rate"] == 4000
    assert j["catatan"] == ("Perubahan tarif berlaku untuk pesanan yang dibuat sesudah disimpan. Kolom kanan menunjukkan "
                            "angka bila pesanan bulan ini dibuat dengan aturan baru.")
    # simulasi tidak menulis apa pun
    assert (await db.incentive_rates.find_one({"id": "irate_ka8_mega"}))["per_unit_amount"] == 3500
    assert (await db.sales_orders.find_one({"id": "so_ka8"}))["items"][0]["commission_rule"]["tarif"]["per_unit_amount"] == 3500
    # draf kategori (tarif artikel Mega masih menang) → tetap 350.000; draf varian merah 5.000 → 500.000
    r = await klien.post("/api/incentive-rates/simulate", headers=kepala_admin,
                         json={**badan, "draft_rates": [{"category": "KA8Batik", "per_unit_amount": 9000}]})
    assert r.json()["dengan_perubahan"]["total_incentive"] == 350_000
    r = await klien.post("/api/incentive-rates/simulate", headers=kepala_admin,
                         json={**badan, "draft_rates": [{"product_id": MRH, "per_unit_amount": 5000}]})
    assert r.json()["dengan_perubahan"]["total_incentive"] == 500_000
    # draf tidak sah → 400; mode Semua PT → 400
    r = await klien.post("/api/incentive-rates/simulate", headers=kepala_admin,
                         json={**badan, "draft_rates": [{"template_id": MEGA, "product_id": MRH, "per_unit_amount": 1}]})
    assert r.status_code == 400, r.text
    r = await klien.post("/api/incentive-rates/simulate", headers=kepala_admin, json={**badan, "entity_id": "all"})
    assert r.status_code == 400, r.text
