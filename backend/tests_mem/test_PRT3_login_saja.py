"""PR-T3 — endpoint yang hanya butuh login: dipilah dan dijaga (docs/blueprint/unit/PR-T3.md), uji U1–U13.

Peran uji baku `02_STANDAR.md` §6: "Tanpa Acuan" (hanya izin yang diuji), "Manajer Kosong" (acuan Manajer, semua modul
"Tidak ada"), Sopir. `sls` = sales seed, `adm` = admin seed. U14 dan U15 (sapuan 13 peran bawaan dan dasbor Manajer,
dibandingkan dengan berkas "sebelum") ada di `test_PRT3_sapuan.py` — modul sendiri supaya basis datanya bersih.
Di kode lama uji U1–U9 dan U13 merah: rute itu cukup dengan login (Sopir 200, isi lengkap).
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

import pytest

pytestmark = pytest.mark.anyio

#: S2 — kunci baris `GET /api/entities` bagi peran tanpa `entity.view`: 11 kunci spesifikasi + 3 kunci yang dipakai
#: layar non-Admin (langkah kerja 5): `is_group` (pemilih PT Tutup Buku, Buka Periode, Suspense, Eliminasi),
#: `write_locked` dan `city` (pemilih badan usaha di kepala aplikasi: saringan dan pencarian).
KUNCI_S2 = {"id", "code", "name", "short_name", "legal_name", "type", "is_pkp", "currency", "status", "doc_prefix",
            "logo_url", "is_group", "write_locked", "city"}


async def _kode(klien, metode: str, jalur: str, headers, json=None) -> int:
    return (await klien.request(metode, jalur, headers=headers, json=json)).status_code


async def _ta(akun, sesi, peran_tanpa_acuan, izin: Dict[str, List[str]], label: str) -> Dict[str, str]:
    return await sesi(await akun(await peran_tanpa_acuan(izin, label=label)))


async def _mk_sopir(akun, sesi, peran_manajer_kosong, peran_sopir) -> Tuple[Dict[str, str], Dict[str, str]]:
    return await sesi(await akun(await peran_manajer_kosong())), await sesi(await akun(peran_sopir))


async def _fixture_u5(db) -> str:
    """Fixture U5 (disisipkan langsung): satu pesanan aktif dan satu pelanggan milik `sales@` di `ent_ksc`."""
    sls = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not await db.customers.find_one({"id": "cust_uji_prt3"}):
        await db.customers.insert_one({"id": "cust_uji_prt3", "code": "CUJ-PRT3", "name": "Pelanggan Uji PR-T3",
                                       "entity_id": "ent_ksc", "assigned_sales_id": sls["id"], "status": "active",
                                       "created_at": now})
    if not await db.sales_orders.find_one({"id": "so_uji_prt3"}):
        await db.sales_orders.insert_one({"id": "so_uji_prt3", "number": "KSC/SO-PRT3-1", "entity_id": "ent_ksc",
                                          "customer_id": "cust_uji_prt3", "customer_name": "Pelanggan Uji PR-T3",
                                          "sales_id": sls["id"], "created_by": sls["id"], "status": "approved",
                                          "items": [], "total": 0, "created_at": now})
    return sls["id"]


# ── U1 — S4 daftar sales ──────────────────────────────────────────────────────
async def test_PRT3_U1_daftar_sales_berizin(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, sopir = await _mk_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    ta = await _ta(akun, sesi, peran_tanpa_acuan, {"customer": ["view"]}, "TA U1 pelanggan")
    assert [await _kode(klien, "GET", "/api/sales-users", h) for h in (ta, mk, sopir)] == [200, 403, 403]
    # salah satu dari tiga izin cukup (S4)
    for izin in ({"order": ["view"]}, {"sales_force": ["view"]}):
        h = await _ta(akun, sesi, peran_tanpa_acuan, izin, f"TA U1 {next(iter(izin))}")
        assert await _kode(klien, "GET", "/api/sales-users", h) == 200, izin
    detail = (await klien.get("/api/sales-users", headers=sopir)).json()["detail"]
    assert "Minta Admin menambahkan akses" in detail and "customer.view" not in detail   # pesan bentuk Z6


# ── U2 — S3 target dan skema insentif ────────────────────────────────────────
async def test_PRT3_U2_target_dan_insentif_tersaring(klien, akun, sesi, db, kepala_admin, peran_tanpa_acuan,
                                                     peran_sopir):
    sls = await sesi("sales@kainnusantara.id")
    sls_doc = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    sales2 = await akun("sales")
    # Alur: adm membuat satu skema insentif untuk `sls` dan untuk sales kedua (periode sama). KM-T5 — `GET`/`POST
    # /api/sales-targets` dihapus (target lewat `/api/incentive/targets`, izin `incentive.*`); saringan S3 diuji pada
    # skema insentif yang tersisa.
    for sid in (sls_doc["id"], sales2["id"]):
        r = await klien.post("/api/sales-incentives", headers=kepala_admin,
                             json={"sales_id": sid, "period": "2026-11", "basis": "sales"})
        assert r.status_code == 200, r.text
    sopir = await sesi(await akun(peran_sopir))
    ta_o = await _ta(akun, sesi, peran_tanpa_acuan, {"order": ["view"]}, "TA U2 pesanan")
    ta_os = await _ta(akun, sesi, peran_tanpa_acuan, {"order": ["view"], "sales_force": ["view"]}, "TA U2 tim sales")
    for jalur in ("/api/sales-incentives?period=2026-11",):
        assert await _kode(klien, "GET", jalur, sopir) == 403, jalur
        mine = (await klien.get(jalur, headers=sls)).json()
        assert [r["sales_id"] for r in mine] == [sls_doc["id"]], jalur          # 1 baris: miliknya
        assert (await klien.get(jalur, headers=ta_o)).json() == [], jalur        # 0 baris: bukan pengawas
        semua = (await klien.get(jalur, headers=ta_os)).json()                   # 2 baris: pemegang sales_force.view
        assert sorted(r["sales_id"] for r in semua) == sorted([sls_doc["id"], sales2["id"]]), jalur
        # admin seed (pengawas) tetap melihat semua, dan saringan `sales_id` tetap berlaku untuknya
        assert len((await klien.get(jalur, headers=kepala_admin)).json()) == 2, jalur
        one = (await klien.get(f"{jalur}&sales_id={sales2['id']}", headers=kepala_admin)).json()
        assert [r["sales_id"] for r in one] == [sales2["id"]], jalur
        # sales tidak bisa membuka milik orang lain lewat `sales_id`
        other = (await klien.get(f"{jalur}&sales_id={sales2['id']}", headers=sls)).json()
        assert [r["sales_id"] for r in other] == [sls_doc["id"]], jalur


# ── U3 — S2 daftar badan usaha ───────────────────────────────────────────────
async def test_PRT3_U3_daftar_pt_tersaring(klien, akun, sesi, kepala_admin, peran_sopir):
    sopir = await sesi(await akun(peran_sopir))
    r_s = await klien.get("/api/entities?with_readiness=true", headers=sopir)
    r_a = await klien.get("/api/entities", headers=kepala_admin)
    assert r_s.status_code == 200 and r_a.status_code == 200
    rows_s, rows_a = r_s.json(), r_a.json()
    assert len(rows_s) == len(rows_a) >= 2
    for row in rows_s:
        assert set(row) == KUNCI_S2, sorted(set(row) ^ KUNCI_S2)
    assert all("user_count" in row for row in rows_a)
    assert {r["id"] for r in rows_s} == {r["id"] for r in rows_a}


# ── U4 — S5 rincian badan usaha ──────────────────────────────────────────────
async def test_PRT3_U4_rincian_pt_berizin(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, sopir = await _mk_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    ta = await _ta(akun, sesi, peran_tanpa_acuan, {"entity": ["view"]}, "TA U4 badan usaha")
    jalur = ("/api/entities/ent_ksc", "/api/entities/ent_ksc/readiness")
    assert [[await _kode(klien, "GET", j, h) for j in jalur] for h in (ta, mk, sopir)] == [[200, 200], [403, 403],
                                                                                          [403, 403]]
    # penghitung ikut S5
    assert [await _kode(klien, "GET", "/api/entities/count", h) for h in (ta, mk, sopir)] == [200, 403, 403]


# ── U5, U6 — S1 dasbor ───────────────────────────────────────────────────────
async def test_PRT3_U5_dasbor_sopir_kosong(klien, akun, sesi, db, peran_sopir):
    await _fixture_u5(db)
    r = await klien.get("/api/dashboard", headers=await sesi(await akun(peran_sopir)))
    assert r.status_code == 200, r.text
    j = r.json()
    for bagian in ("orders", "customers", "products", "warehouses"):
        assert j[bagian] == [], bagian
    m = j["metrics"]
    assert m["active_orders"] == 0 and m["customers"] == 0 and m["products"] == 0 and m["warehouses"] == 0
    # angka stok tanpa `inventory.view`: kuncinya tetap ada, isinya kosong / 0
    assert (m["available_qty"], m["reserved_qty"], m["available_rolls"]) == (0, 0, 0)
    assert m["available_by_unit"] == {} and m["reserved_by_unit"] == {} and m["unitless_product_ids"] == []
    assert j["stock_scope"] == {}


async def test_PRT3_U6_dasbor_hanya_bagian_berizin(klien, akun, sesi, db, peran_tanpa_acuan):
    await _fixture_u5(db)
    ta = await _ta(akun, sesi, peran_tanpa_acuan, {"order": ["view"]}, "TA U6 pesanan")
    j = (await klien.get("/api/dashboard", headers=ta)).json()
    assert [o["id"] for o in j["orders"]] == ["so_uji_prt3"]
    assert j["metrics"]["active_orders"] == 1
    assert j["customers"] == [] and j["products"] == [] and j["warehouses"] == []
    # bagian lain mengikuti izinnya sendiri (S1)
    tb = await _ta(akun, sesi, peran_tanpa_acuan, {"customer": ["view"], "product": ["view"], "warehouse": ["view"]},
                   "TA U6 master")
    j = (await klien.get("/api/dashboard", headers=tb)).json()
    assert j["orders"] == [] and j["metrics"]["active_orders"] == 0
    assert j["customers"] and j["products"] and j["warehouses"]
    assert j["metrics"]["available_by_unit"] == {} and j["stock_scope"] == {}
    tc = await _ta(akun, sesi, peran_tanpa_acuan, {"inventory": ["view"]}, "TA U6 stok")
    j = (await klien.get("/api/dashboard", headers=tc)).json()
    assert j["metrics"]["available_rolls"] > 0 and j["stock_scope"]
    assert j["products"] == []


# ── U7 — S6 buka periode ─────────────────────────────────────────────────────
async def test_PRT3_U7_riwayat_buka_periode(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, sopir = await _mk_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    ta = await _ta(akun, sesi, peran_tanpa_acuan, {"period": ["unlock"]}, "TA U7 buka periode")
    jalur = "/api/finance/period-unlocks"
    assert [await _kode(klien, "GET", jalur, h) for h in (ta, mk, sopir)] == [200, 403, 403]
    tb = await _ta(akun, sesi, peran_tanpa_acuan, {"accounting": ["view"]}, "TA U7 akuntansi")
    assert await _kode(klien, "GET", jalur, tb) == 200
    assert await _kode(klien, "GET", f"{jalur}/active", sopir) == 200      # banner tetap untuk semua


# ── U8 — S7 sumber harga PO ──────────────────────────────────────────────────
async def test_PRT3_U8_sumber_harga_po(klien, akun, sesi, peran_tanpa_acuan, peran_sopir):
    sopir = await sesi(await akun(peran_sopir))
    jalur = "/api/purchase-orders/resolve-sourcing?product_id=x"
    for izin in (["create"], ["update"]):
        ta = await _ta(akun, sesi, peran_tanpa_acuan, {"purchase_order": izin}, f"TA U8 {izin[0]}")
        assert await _kode(klien, "GET", jalur, ta) != 403, izin
    assert await _kode(klien, "GET", jalur, sopir) == 403
    lihat = await _ta(akun, sesi, peran_tanpa_acuan, {"purchase_order": ["view"]}, "TA U8 lihat")
    assert await _kode(klien, "GET", jalur, lihat) == 403


# ── U9 — S8 pemenuhan pesanan khusus ─────────────────────────────────────────
async def test_PRT3_U9_pemenuhan_od_gerbang_pertama(klien, akun, sesi, peran_tanpa_acuan, peran_sopir):
    sopir = await sesi(await akun(peran_sopir))
    route = ("/api/special-orders/tidak-ada/fulfillment/k/route", {"route": "buy", "reason": "uji PR-T3"})
    realize = ("/api/special-orders/tidak-ada/fulfillment/k/realize", {"warehouse_id": ""})
    # kode lama: 404 (dokumen dimuat dulu, izin baru diperiksa di layanan)
    assert await _kode(klien, "POST", route[0], sopir, route[1]) == 403
    assert await _kode(klien, "POST", realize[0], sopir, realize[1]) == 403
    ta = await _ta(akun, sesi, peran_tanpa_acuan, {"od_fulfillment": ["choose_route"]}, "TA U9 jalur")
    assert await _kode(klien, "POST", route[0], ta, route[1]) == 404
    assert await _kode(klien, "POST", realize[0], ta, realize[1]) == 403        # izin lain tidak ikut
    tb = await _ta(akun, sesi, peran_tanpa_acuan, {"od_fulfillment": ["realize"]}, "TA U9 realisasi")
    assert await _kode(klien, "POST", realize[0], tb, realize[1]) == 404


# ── U10 — tabel B baris 1: cetak label lot ───────────────────────────────────
async def test_PRT3_U10_label_lot_tetap_izin_lihat(klien, akun, sesi, kepala_admin, peran_tanpa_acuan):
    """Putusan baris ini menjadi "tetap" (asumsi spesifikasi gugur, lihat laporan): Admin Sales — pemegang
    `inventory.view` tanpa `label.generate` — membuka layar Lot & Silsilah (menu warisan Sales) yang memanggil
    `POST /api/lots/{id}/label` (tombol "Label / QR"). Endpoint ini hanya membangkitkan perintah cetak (tanpa tulis
    selain jejak audit). Uji ini menjaga putusan itu: tanpa `label.generate` tidak 403; dengan `label.generate` sama."""
    rid = await peran_tanpa_acuan({"inventory": ["view"], "field_visibility": ["lot"]}, label="TA U10 label")
    h = await sesi(await akun(rid))
    isi = {"format": "zpl", "qty": 1, "roll_id": ""}
    assert await _kode(klien, "POST", "/api/lots/tidak-ada/label", h, isi) == 404
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"permissions": {"inventory": ["view"], "field_visibility": ["lot"],
                                                "label": ["view", "generate"]}})
    assert r.status_code == 200, r.text
    assert await _kode(klien, "POST", "/api/lots/tidak-ada/label", h, isi) == 404
    tanpa_lihat = await _ta(akun, sesi, peran_tanpa_acuan, {"field_visibility": ["lot"]}, "TA U10 tanpa lihat")
    assert await _kode(klien, "POST", "/api/lots/tidak-ada/label", tanpa_lihat, isi) == 403


# ── U11 — pratinjau dan simulasi tidak menulis ───────────────────────────────
PRATINJAU: List[Tuple[str, str, Optional[Dict[str, Any]]]] = [
    ("POST", "/api/config/impact-preview", {"product_id": "{pid}", "new_price": 1000}),
    ("POST", "/api/sales-orders/preview-allocation", {"items": [{"product_id": "{pid}", "quantity": 1}],
                                                      "entity_id": "ent_ksc"}),
    ("POST", "/api/sales-orders/preview-lots", {"items": [{"product_id": "{pid}", "quantity": 1}],
                                                "entity_id": "ent_ksc"}),
    ("POST", "/api/sales-orders/preview-roll-reconcile", {"items": [], "entity_id": "ent_ksc"}),
    ("POST", "/api/sales-returns/cutloss/simulate", {"roll_length": 50, "defect_from": 10, "defect_to": 12,
                                                     "unit_price": 10000}),
    ("POST", "/api/sales-returns/discount/simulate", {"qty_affected": 2, "amount": 5000}),
    ("POST", "/api/supplier-contracts/resolve?product_id={pid}", None),
    ("POST", "/api/supplier-contracts/tariff-preview", {"product_id": "{pid}", "qty": 10}),
    ("POST", "/api/uom-conversions/convert", {"product_id": "{pid}", "qty": 10, "from_unit": "meter"}),
    ("POST", "/api/uom-conversions/check-variance", {"expected": 10, "actual": 9.8}),
    ("POST", "/api/access/roles/preview", {"base_role": "sales", "levels": {}}),
    ("POST", "/api/bank-reconciliation/preview", {"raw": "01/11/2026;Setoran;100000"}),
    ("POST", "/api/finance/budget-check", {"key": "6-1000", "amount": 1000}),
    ("POST", "/api/document-templates/{tid}/preview", {}),
    ("POST", "/api/suppliers/label-pattern/test", {"raw": "LOT123|10.5"}),
    ("POST", "/api/makloon-orders/estimate", {"input_product_id": "{pid}"}),
    ("POST", "/api/payment-plans/preview", {"doc_id": "tidak-ada"}),
    ("POST", "/api/payment-variances/assess", {"customer_id": "{cid}", "amount": 1000}),
    ("POST", "/api/pdf/templates/validate-script", {"script": "{{ number }}"}),
    ("POST", "/api/process-recipes/forecast", {"input_qty": 10}),
    ("POST", "/api/inbound/tasks/tidak-ada/preview-uom", {"doc_qty": 1, "doc_unit": "meter"}),
    ("POST", "/api/rfid/printers/label-preview", {}),
    ("POST", "/api/export-center/preview", {"dataset": "products"}),
]


def _isi(nilai: Any, ganti: Dict[str, str]) -> Any:
    if isinstance(nilai, dict):
        return {k: _isi(v, ganti) for k, v in nilai.items()}
    if isinstance(nilai, list):
        return [_isi(v, ganti) for v in nilai]
    if isinstance(nilai, str):
        for k, v in ganti.items():
            nilai = nilai.replace("{" + k + "}", v)
    return nilai


async def _hitung_semua(db) -> Dict[str, int]:
    return {n: await db[n].count_documents({}) for n in sorted(await db.list_collection_names())
            if n not in ("audit_logs", "sessions")}


async def test_PRT3_U11_pratinjau_tidak_menulis(klien, aplikasi, kepala_admin, db):
    from starlette.routing import Match
    pid = (await db.products.find_one({}, {"_id": 0, "id": 1}) or {}).get("id", "x")
    cid = (await db.customers.find_one({}, {"_id": 0, "id": 1}) or {}).get("id", "x")
    tid = (await db.document_templates.find_one({}, {"_id": 0, "id": 1}) or {}).get("id", "tidak-ada")
    ganti = {"pid": pid, "cid": cid, "tid": tid}
    assert len(PRATINJAU) == 23
    # pemanasan: proses awal yang malas (cache/indeks pertama kali) tidak boleh terhitung sebagai "tulis"
    for metode, jalur, isi in PRATINJAU:
        await klien.request(metode, _isi(jalur, ganti), headers=kepala_admin, json=_isi(isi, ganti))
    sebelum = await _hitung_semua(db)
    kode = {}
    for metode, jalur, isi in PRATINJAU:
        j = _isi(jalur, ganti)
        path = j.split("?")[0]
        ada = any(rt.matches({"type": "http", "path": path, "method": metode})[0] == Match.FULL
                  for rt in aplikasi.routes if hasattr(rt, "matches"))
        assert ada, f"rute tidak ada: {metode} {path}"
        kode[j] = await _kode(klien, metode, j, kepala_admin, _isi(isi, ganti))
        # isi kosong juga
        if isi:
            await klien.request(metode, j, headers=kepala_admin, json={})
    sesudah = await _hitung_semua(db)
    beda = {n: (sebelum.get(n), sesudah.get(n)) for n in set(sebelum) | set(sesudah) if sebelum.get(n) != sesudah.get(n)}
    assert not beda, (beda, kode)
    assert all(k != 403 for k in kode.values()), kode


# ── U12 — data rujukan, milik sendiri, sesi tetap terbuka ────────────────────
async def test_PRT3_U12_rute_login_saja_sah_tetap_terbuka(klien, akun, sesi, peran_sopir):
    sopir = await sesi(await akun(peran_sopir))
    for jalur in ("/api/enums", "/api/wilayah/provinces", "/api/notifications", "/api/roles", "/api/payment-terms",
                  "/api/auth/me", "/api/onboarding", "/api/stock/my-site"):
        assert await _kode(klien, "GET", jalur, sopir) != 403, jalur


# ── U13 — daftar endpoint login-saja yang sah ────────────────────────────────
async def test_PRT3_U13_daftar_login_only_menunjuk_rute(aplikasi):
    import login_only_endpoints as lo
    # + PR-T5: `GET /api/access/labels` (kamus label, data rujukan); + PM-T1: `GET /api/payment-methods` (cara bayar)
    # + PM-T4: `GET /api/cash-holdings/me/summary` (ringkasan titipan tunai milik sendiri)
    # + KM-T5: `GET /api/incentive/me` (kartu "Capaian & Insentif Saya", milik sendiri)
    assert len(lo.LOGIN_ONLY) == 53 + 1 + 1 + 1 + 1
    assert set(lo.LOGIN_ONLY.values()) <= {"milik_sendiri", "rujukan", "sesi"}
    rute = {(m, rt.path) for rt in aplikasi.routes for m in (getattr(rt, "methods", None) or ())}
    hilang = [k for k in lo.LOGIN_ONLY if k not in rute]
    assert not hilang, hilang
    # rute yang diberi izin / disaring oleh unit ini tidak boleh tercatat sebagai login-saja sah
    for k in (("GET", "/api/sales-users"), ("GET", "/api/sales-incentives"),   # KM-T5 — /api/sales-targets dihapus
              ("GET", "/api/dashboard"), ("GET", "/api/entities/{entity_id}"), ("GET", "/api/entities/count"),
              ("GET", "/api/finance/period-unlocks"), ("GET", "/api/purchase-orders/resolve-sourcing")):
        assert k not in lo.LOGIN_ONLY, k
    assert lo.LOGIN_ONLY[("GET", "/api/entities")] == "rujukan"
