"""KA-12 — perbaikan tinjauan akhir komisi per artikel (API tarif): I4, I5, M3, M4, M7.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.2, §6.6, §6.7; ledger R19.

Fixture (DISISIP langsung, PT `ent_ksc`): artikel Songket A12 (`tpl_ka12_sa`), Songket B12 (`tpl_ka12_sb`), Songket C12
(`tpl_ka12_sc`), Songket D12 (`tpl_ka12_sd`), kategori `KA12Songket`; varian `prd_ka12_sa1` milik Songket A12.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
TPL = ("tpl_ka12_sa", "tpl_ka12_sb", "tpl_ka12_sc", "tpl_ka12_sd", "tpl_ka12_se", "tpl_ka12_sf", "tpl_ka12_sg")
KOLOM = ["Kode artikel", "Nama artikel", "Kategori", "Kode varian", "Tarif per satuan dasar", "Batas margin %",
         "Asal tarif", "ID artikel", "ID varian"]


@pytest.fixture(scope="module")
async def f12(db):
    await db.product_templates.insert_many([
        {"id": t, "name": f"Songket {t[-1].upper()}12", "sku_prefix": f"SKT-{t[-1].upper()}12", "category": "KA12Songket",
         "status": "active"} for t in TPL])
    await db.products.insert_one({"id": "prd_ka12_sa1", "sku": "SKT-A12-01", "name": "Songket A12 Merah",
                                  "category": "KA12Songket", "template_id": TPL[0], "status": "active",
                                  "is_active": True})
    return True


def _xlsx(baris: List[List[Any]]) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(KOLOM)
    for b in baris:
        ws.append(b)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _pratinjau(klien, h, isi: bytes):
    return await klien.post("/api/incentive-rates/import/preview", headers=h, data={"entity_id": KSC},
                            files={"file": ("tarif.xlsx", isi, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


# ═══ I4 — teks Excel dibaca cara Indonesia; batas margin 0–100 di server ═══════════════════════════════════════════
async def test_KA12_I4_teks_excel_cara_indonesia(klien, kepala_admin, f12):
    def b(i: int, tarif: Any, batas: Any = None) -> List[Any]:
        t = TPL[i]
        return [f"SKT-{t[-1].upper()}12", "", "KA12Songket", None, tarif, batas, "", t, None]
    isi = _xlsx([b(0, "3.500"), b(1, "3.500,5"), b(2, "3,5"), b(3, 3500), b(4, "Rp 3.500"), b(5, "3.5"),
                 b(6, "3,500")])
    r = await _pratinjau(klien, kepala_admin, isi)
    assert r.status_code == 200, r.text
    rows = {x["template_id"] or x["kode_artikel"]: x for x in r.json()["rows"]}
    assert [rows[TPL[i]]["baru"] for i in range(4)] == [3500, 3500.5, 3.5, 3500]        # sel angka tidak berubah
    assert all(rows[TPL[i]]["status"] == "baru" for i in range(4))
    for i, teks in ((4, "Rp 3.500"), (5, "3.5"), (6, "3,500")):
        x = rows[TPL[i]]
        assert x["status"] == "galat", x
        assert x["pesan"] == (f"Tarif per satuan dasar “{teks}” tidak terbaca. Tulis angka saja dengan titik "
                              "untuk ribuan dan koma untuk desimal, contoh 3.500 atau 3.500,5."), x["pesan"]
    # batas margin > 100: galat di pratinjau (teks maupun angka), 400 di API tunggal, ubah banyak, dan terap
    x = (await _pratinjau(klien, kepala_admin, _xlsx([b(0, 100, "150")]))).json()["rows"][0]
    assert (x["status"], x["pesan"]) == ("galat", "Batas margin % harus angka 0–100.")
    x = (await _pratinjau(klien, kepala_admin, _xlsx([b(0, 100, 100.5)]))).json()["rows"][0]
    assert x["status"] == "galat"
    for rute, isi_json in (("", {"entity_id": KSC, "template_id": TPL[0], "per_unit_amount": 1, "margin_cap_pct": 150}),
                           ("/bulk", {"entity_id": KSC, "template_ids": [TPL[0]], "per_unit_amount": 1,
                                      "margin_cap_pct": 150, "reason": "uji"}),
                           ("/import/apply", {"entity_id": KSC, "rows": [{"template_id": TPL[0], "per_unit_amount": 1,
                                                                          "margin_cap_pct": 150, "baris": 2}]})):
        r = await klien.post(f"/api/incentive-rates{rute}", headers=kepala_admin, json=isi_json)
        assert r.status_code == 400, (rute, r.text)
        assert r.json()["detail"].endswith("Batas margin harus angka 0–100."), (rute, r.text)


# ═══ I5a — PATCH selalu memvalidasi dokumen gabungan ════════════════════════════════════════════════════════════════
async def test_KA12_I5_patch_selalu_divalidasi(klien, kepala_admin, db, f12):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": TPL[1], "per_unit_amount": 2000})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    salah = (({"per_unit_amount": -5}, "Tarif harus berupa angka, tidak boleh negatif."),
             ({"per_unit_amount": "abc"}, "Tarif harus berupa angka, tidak boleh negatif."),
             ({"per_unit_amount": None}, "Tarif wajib diisi (angka, boleh 0)."),
             ({"margin_cap_pct": 150}, "Batas margin harus angka 0–100."),
             ({"discount_factor": 2}, "Faktor komisi saat diskon besar harus angka 0–1."),
             ({"discount_threshold": "10"}, "Ambang diskon harus berupa angka, tidak boleh negatif."),
             ({"discount_mechanic": "hangus_sebagian"}, None),
             ({"status": "dihapus"}, "Status tarif harus aktif atau nonaktif."),
             ({"price_bands": []}, "Pita pengali harga minimal berisi satu baris."))
    for isi, pesan in salah:
        r = await klien.patch(f"/api/incentive-rates/{rid}", headers=kepala_admin, json={"data": isi})
        assert r.status_code == 400, (isi, r.text)
        if pesan:
            assert r.json()["detail"] == pesan, (isi, r.json())
    d = await db.incentive_rates.find_one({"id": rid}, {"_id": 0})
    assert d["per_unit_amount"] == 2000 and d["status"] == "active"    # tidak ada yang tersimpan
    r = await klien.patch(f"/api/incentive-rates/{rid}", headers=kepala_admin,
                          json={"data": {"status": "inactive", "discount_mechanic": "cutoff", "margin_cap_pct": 100}})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["discount_mechanic"], r.json()["margin_cap_pct"]) == ("inactive", "cutoff", 100)


# ═══ I5b — satu tarif dibaca per id; daftar tanpa batas jumlah diam-diam ═════════════════════════════════════════════
async def test_KA12_I5b_baca_per_id_dan_daftar_utuh(klien, kepala_admin, db, akun, sesi, peran_tanpa_acuan, f12):
    pita = [{"sampai_pct": 3, "pengali": 0.8}, {"sampai_pct": None, "pengali": 0.5}]
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": TPL[2], "per_unit_amount": 900, "price_bands": pita})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    banyak = [{"id": f"irate_ka12_n{i}", "entity_id": "all", "category": f"N12{i:04d}",
               "rate_key": f"kategori:N12{i:04d}", "per_unit_amount": 1.0, "status": "active", "created_at": now_iso()}
              for i in range(1_005)]
    await db.incentive_rates.insert_many(banyak)
    await db.incentive_rates.insert_one({"id": "irate_ka12_akhir", "entity_id": "all", "category": "ZZZ12",
                                         "rate_key": "kategori:ZZZ12", "per_unit_amount": 1.0, "status": "active"})
    try:
        r = await klien.get(f"/api/incentive-rates/{rid}", headers=kepala_admin)
        assert r.status_code == 200 and r.json()["price_bands"] == pita, r.text
        assert (await klien.get("/api/incentive-rates/irate_tidak_ada", headers=kepala_admin)).status_code == 404
        # PT di luar penugasan → 404 (tidak membocorkan tarif PT lain)
        rol = await peran_tanpa_acuan({"sales_force": ["view"]}, label="Lihat tarif KA12")
        h_kanda = await sesi(await akun(rol, entitas=(KANDA,)), entitas=KANDA)
        assert (await klien.get(f"/api/incentive-rates/{rid}", headers=h_kanda)).status_code == 404
        # daftar tarif Semua PT (layar GroupRatesList): semua baris (lebih dari 1.000), termasuk urutan terakhir
        r = await klien.get("/api/incentive-rates", headers={**kepala_admin, "X-Entity-Id": "all"},
                            params={"entity_id": "all"})
        assert r.status_code == 200, r.text
        ids = {d["id"] for d in r.json()}
        assert len(ids) > 1_005 and "irate_ka12_akhir" in ids
    finally:
        await db.incentive_rates.delete_many({"id": {"$regex": "^irate_ka12_n"}})
        await db.incentive_rates.delete_one({"id": "irate_ka12_akhir"})


# ═══ M3 — wewenang lintas PT pada tarif tunggal ════════════════════════════════════════════════════════════════════
async def test_KA12_M3_wewenang_pt_dan_semua_pt(klien, kepala_admin, db, akun, sesi, peran_tanpa_acuan, f12):
    from routers.incentive_rates import PESAN_BUKAN_PT_ANDA, PESAN_SEMUA_PT
    rol = await peran_tanpa_acuan({"sales_force": ["view", "update", "delete"]}, label="Tarif satu PT KA12")
    h = await sesi(await akun(rol, entitas=(KSC,)), entitas=KSC)
    r = await klien.post("/api/incentive-rates", headers=h, json={"entity_id": "all", "template_id": TPL[3],
                                                                 "per_unit_amount": 10})
    assert r.status_code == 403, r.text       # pagar tulis ber-PT menolak lebih dulu; rute menolak dengan PESAN_SEMUA_PT
    r = await klien.post("/api/incentive-rates", headers=h, json={"entity_id": KANDA, "template_id": TPL[3],
                                                                 "per_unit_amount": 10})
    assert r.status_code == 403, r.text
    r = await klien.post("/api/incentive-rates", headers=h, json={"entity_id": KSC, "template_id": TPL[3],
                                                                 "per_unit_amount": 10})
    assert r.status_code == 200, r.text
    milik_ksc = r.json()["id"]
    # tarif Semua PT & tarif PT lain dibuat Admin (lintas PT) — pelaku satu PT tidak boleh mengubah / menghapusnya
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": "all", "template_id": TPL[3],
                                                                            "per_unit_amount": 20})
    assert r.status_code == 200, r.text
    grup = r.json()["id"]
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": KANDA, "template_id": TPL[3],
                                                                            "per_unit_amount": 30})
    assert r.status_code == 200, r.text
    kanda = r.json()["id"]
    for rid, pesan in ((grup, PESAN_SEMUA_PT), (kanda, PESAN_BUKAN_PT_ANDA)):
        r = await klien.patch(f"/api/incentive-rates/{rid}", headers=h, json={"data": {"per_unit_amount": 1}})
        assert (r.status_code, r.json()["detail"]) == (403, pesan), r.text
        r = await klien.delete(f"/api/incentive-rates/{rid}", headers=h, params={"reason": "uji"})
        assert (r.status_code, r.json()["detail"]) == (403, pesan), r.text
    # memindah tarif PT sendiri ke Semua PT juga ditolak
    r = await klien.patch(f"/api/incentive-rates/{milik_ksc}", headers=h, json={"data": {"entity_id": "all"}})
    assert r.status_code == 403, r.text
    r = await klien.patch(f"/api/incentive-rates/{milik_ksc}", headers=h, json={"data": {"per_unit_amount": 11}})
    assert r.status_code == 200, r.text
    assert (await klien.delete(f"/api/incentive-rates/{milik_ksc}", headers=h, params={"reason": "uji"})).status_code == 200
    for rid in (grup, kanda):
        assert (await klien.delete(f"/api/incentive-rates/{rid}", headers=kepala_admin)).status_code == 200


# ═══ M4 — POST ke sasaran bertarif nonaktif: diaktifkan & diubah, bukan 409 ═══════════════════════════════════════
async def test_KA12_M4_post_mengaktifkan_tarif_nonaktif(klien, kepala_admin, db, f12):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "product_id": "prd_ka12_sa1", "per_unit_amount": 700,
                               "margin_cap_pct": 30})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert (await klien.patch(f"/api/incentive-rates/{rid}", headers=kepala_admin,
                              json={"data": {"status": "inactive"}})).status_code == 200
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "product_id": "prd_ka12_sa1", "per_unit_amount": 750})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["id"], j["status"], j["per_unit_amount"], j["margin_cap_pct"]) == (rid, "active", 750, 30)
    assert await db.incentive_rates.count_documents({"entity_id": KSC, "rate_key": "varian:prd_ka12_sa1"}) == 1
    log = await db.audit_logs.find_one({"entity_id": rid, "action": "incentive_rate_updated"}, {"_id": 0},
                                       sort=[("timestamp", -1)])
    assert log is not None
    # tarif yang sudah aktif tetap 409
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "product_id": "prd_ka12_sa1", "per_unit_amount": 800})
    assert r.status_code == 409, r.text


# ═══ M7 — tarif baru tanpa isian diskon memakai kunci PT; tarif lama tetap nilainya sendiri ═════════════════════════
async def test_KA12_M7_tarif_baru_ikut_kunci_diskon_pt(klien, kepala_admin, db, f12):
    from services import config_resolver as resolver
    from services.commission_rate_service import KUNCI_DISKON, bawaan_tarif
    from services.commission_rules import potret_pesanan
    from config_registry import require
    assert not any(k in bawaan_tarif() for k in KUNCI_DISKON + ("margin_cap_pct",))
    # nilai bawaan registri = bawaan tulisan lama RatePayload → PT tanpa pengaturan sendiri tidak berubah angka
    assert [require(f"commission.{k}")["default"] for k in KUNCI_DISKON + ("default_margin_cap_pct",)] == [
        "pct", 10.0, "tier_factor", 0.5, 0.0, 50.0]
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": TPL[4], "per_unit_amount": 1000})
    assert r.status_code == 200, r.text
    baru = await db.incentive_rates.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert not any(k in baru for k in KUNCI_DISKON) and baru["margin_cap_pct"] == 50.0, baru
    lama = {"id": "irate_ka12_lama", "entity_id": KSC, "category": "KA12Songket", "template_id": TPL[5],
            "rate_key": f"artikel:{TPL[5]}", "per_unit_amount": 1000.0, "margin_cap_pct": 50.0,
            "discount_threshold_type": "pct", "discount_threshold": 10.0, "discount_mechanic": "tier_factor",
            "discount_factor": 0.5, "discount_potong_rp": 0.0, "status": "active", "created_at": now_iso()}
    await db.incentive_rates.insert_one(dict(lama))
    baris = [await resolver.set_value("commission.discount_threshold", 5.0, scope_type="entity", scope_id=KSC,
                                      actor="uji", reason="uji KA-12 M7"),
             await resolver.set_value("commission.default_margin_cap_pct", 40.0, scope_type="entity", scope_id=KSC,
                                      actor="uji", reason="uji KA-12 M7")]
    try:
        prods = {}
        for t in (TPL[4], TPL[5]):
            pid = f"prd_ka12_m7_{t[-1]}"
            await db.products.insert_one({"id": pid, "sku": pid.upper(), "name": pid, "category": "KA12Songket",
                                          "template_id": t, "status": "active"})
            prods[pid] = await db.products.find_one({"id": pid}, {"_id": 0})
        items = [{"product_id": pid, "category": "KA12Songket"} for pid in prods]
        await potret_pesanan(KSC, items, prods)
        t_baru, t_lama = items[0]["commission_rule"]["tarif"], items[1]["commission_rule"]["tarif"]
        assert t_baru["discount_threshold"] == 5.0            # tarif baru: kunci PT
        assert t_lama["discount_threshold"] == 10.0           # tarif lama: nilainya sendiri (anti-tujuan 1)
        r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                             json={"entity_id": KSC, "template_id": TPL[6], "per_unit_amount": 1})
        assert r.json()["margin_cap_pct"] == 40.0             # batas margin kosong = bawaan PT
    finally:
        await db.config_values.delete_many({"id": {"$in": [b["id"] for b in baris]}})
