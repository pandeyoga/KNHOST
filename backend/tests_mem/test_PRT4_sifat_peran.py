"""PR-T4 — cakupan data, halaman awal, kategori kerja, dan alamat notifikasi sebagai sifat peran yang bisa diatur
(docs/blueprint/unit/PR-T4.md). U13 ada di `test_PRT4_sapuan.py` (basis data sendiri).

Persiapan bersama (fixture `siap`): PT uji `ent_uji_prt4` tanpa pelanggan seed; dua akun sales `sA`, `sB` (PT itu) masing-
masing satu pelanggan dan satu pesanan (fixture sisip). Peran uji baku `02` §6: "Tanpa Acuan" (fixture
`peran_tanpa_acuan`), "Manajer Kosong", Sopir. "Nyalakan ulang" = `bootstrap.run_bootstrap()` + `sync_registry()`.
Urutan uji penting (satu database per modul): U6/U7 mengubah peran Sales lalu mengembalikannya.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import bootstrap
from pembantu import pt_uji

pytestmark = pytest.mark.anyio

BACKEND = Path(__file__).resolve().parent.parent
WAKTU = "2026-11-10T03:00:00+00:00"

# Kolom "Nilai bila tidak disimpan" (tabel Data) untuk 13 peran bawaan.
HOME_BAWAAN = {"admin": "admin-home", "manager": "manager-home", "sales_admin": "sales-admin-desk",
               "finance": "finance-desk", "sales": "sales-home", "warehouse": "operations",
               "designer": "design-requests", "driver": "logistics", "md": "md-desk",
               "warehouse_admin": "warehouse-admin-desk", "sample_admin": "sample-admin-desk",
               "md_quality": "inspections", "qc": "inspections"}
KATEGORI_BAWAAN = {"sales": "sales", "driver": "sopir", "designer": "desainer", "warehouse": "gudang",
                   "admin": "pengawas", "manager": "pengawas"}
MILIK_SENDIRI_BAWAAN = {"sales", "driver", "designer"}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _nyalakan_ulang() -> None:
    from services.custom_role_service import sync_registry
    await bootstrap.run_bootstrap()
    await sync_registry()


@pytest.fixture(scope="module")
async def siap(klien, akun, sesi, db, kepala_admin):
    pt = await pt_uji("PRT4")
    from services.entity_lifecycle_service import invalidate_status_cache
    invalidate_status_cache()   # PT baru harus dikenali penjaga X-Entity-Id
    sA = await akun("sales", entitas=(pt,), email="prt4.sa@uji.id")
    sB = await akun("sales", entitas=(pt,), email="prt4.sb@uji.id")
    for kode, s in (("A", sA), ("B", sB)):
        await db.customers.insert_one({
            "id": f"cust_prt4_{kode}", "code": f"CUST-PRT4{kode}", "name": f"Pelanggan PRT4 {kode}",
            "entity_id": pt, "assigned_sales_id": s["id"], "assigned_sales_name": s["name"], "status": "active",
            "segment": "retail", "created_at": WAKTU, "updated_at": WAKTU})
        await db.sales_orders.insert_one({
            "id": f"so_prt4_{kode}", "number": f"SO-PRT4-{kode}", "entity_id": pt, "order_type": "regular",
            "customer_id": f"cust_prt4_{kode}", "customer_name": f"Pelanggan PRT4 {kode}", "created_by": s["id"],
            "sales_id": s["id"], "sales_name": s["name"], "status": "waiting_approval", "items": [],
            "grand_total": 1_000_000, "created_at": WAKTU, "updated_at": WAKTU})
    adm = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    return {"pt": pt, "sA": sA, "sB": sB, "adm_pt": await sesi(adm, entitas=pt), "adm": kepala_admin}


async def _peran(klien, h, rid: str) -> dict:
    r = await klien.get(f"/api/access/roles/{rid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _sifat(klien, h, rid: str, traits: dict):
    return await klien.patch(f"/api/access/roles/{rid}", headers=h, json={"traits": traits})


async def _pelanggan(klien, h) -> list:
    r = await klien.get("/api/customers", headers=h)
    assert r.status_code == 200, r.text
    return sorted(c["id"] for c in r.json())


# ─── Serah-terima (a) ─────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PRT4_U1_sifat_bawaan_13_peran(klien, kepala_admin):
    r = await klien.get("/api/access/roles", headers=kepala_admin)
    assert r.status_code == 200, r.text
    roles = {x["id"]: x for x in r.json()["roles"]}
    assert set(HOME_BAWAAN) <= set(roles)
    for rid, home in HOME_BAWAAN.items():
        t = roles[rid].get("traits")
        assert t == {"data_scope": "milik_sendiri" if rid in MILIK_SENDIRI_BAWAAN else "semua", "home_view": home,
                     "kategori_kerja": KATEGORI_BAWAAN.get(rid, ""), "notify_like": []}, (rid, t)
        assert roles[rid]["traits_default"] == t, rid
        assert roles[rid]["traits_overridden"] == [], rid
        assert roles[rid].get("home_view_fallback") is False, rid
    # Pilihan halaman awal: Meja Finance terbuka untuk Finance, mati untuk Sopir (izin bawaan).
    pilih = {c["view"]: c for c in roles["finance"]["home_choices"]}
    assert pilih["finance-desk"]["allowed"] is True and pilih["finance-desk"]["label"] == "Meja Finance"
    assert {c["view"]: c for c in roles["driver"]["home_choices"]}["finance-desk"]["allowed"] is False
    # GET /api/roles memuat sifat efektif.
    pub = {x["id"]: x for x in (await klien.get("/api/roles", headers=kepala_admin)).json()["roles"]}
    assert pub["sales"]["data_scope"] == "milik_sendiri" and pub["sales"]["kategori_kerja"] == "sales"
    assert pub["driver"]["home_view"] == "logistics" and pub["driver"]["home_nav_id"] == "logistics"


async def test_PRT4_U8_halaman_awal_butuh_izin(klien, kepala_admin, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"customer": ["view"]}, label="Tanpa Acuan U8")
    r = await _sifat(klien, kepala_admin, rid, {"home_view": "finance-desk"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Halaman awal “Meja Finance” butuh akses yang belum dimiliki peran ini."
    r = await _sifat(klien, kepala_admin, rid, {"home_view": "hr-my-profile"})
    assert r.status_code == 200, r.text
    assert r.json()["traits"]["home_view"] == "hr-my-profile"
    assert "home_view" in r.json()["traits_overridden"]
    pub = {x["id"]: x for x in (await klien.get("/api/roles", headers=kepala_admin)).json()["roles"]}
    assert pub[rid]["home_view"] == "hr-my-profile" and pub[rid]["home_nav_id"] == "hr-my-profile"
    # Isian tak dikenal → 400 dengan kalimat spesifikasi.
    r = await _sifat(klien, kepala_admin, rid, {"data_scope": "sebagian"})
    assert r.status_code == 400 and _detail(r) == "Cakupan data “sebagian” tidak dikenal."
    r = await _sifat(klien, kepala_admin, rid, {"kategori_kerja": "kasir"})
    assert r.status_code == 400 and _detail(r) == "Kategori kerja “kasir” tidak dikenal."
    r = await _sifat(klien, kepala_admin, rid, {"notify_like": [rid]})
    assert r.status_code == 400 and _detail(r) == "Alamat notifikasi hanya boleh peran bawaan."
    # Halaman awal tersimpan yang syaratnya dicabut → Profil Saya + penanda.
    r = await _sifat(klien, kepala_admin, rid, {"home_view": "sales-home"})
    assert r.status_code == 400   # belum memegang order.view
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"permissions": {"customer": ["view"], "order": ["view"]},
                                "traits": {"home_view": "sales-home"}})
    assert r.status_code == 200, r.text
    assert r.json()["traits"]["home_view"] == "sales-home" and r.json()["home_view_fallback"] is False
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"permissions": {"customer": ["view"]}})
    assert r.status_code == 200, r.text
    assert r.json()["traits"]["home_view"] == "hr-my-profile" and r.json()["home_view_fallback"] is True
    # Nilai null = kembali ke turunan.
    r = await _sifat(klien, kepala_admin, rid, {"home_view": None})
    assert r.status_code == 200, r.text
    assert "home_view" not in r.json()["traits_overridden"] and r.json()["home_view_fallback"] is False


async def test_PRT4_U8b_admin_terkunci_dan_versi_memuat_sifat(klien, kepala_admin, peran_tanpa_acuan):
    r = await _sifat(klien, kepala_admin, "admin", {"data_scope": "milik_sendiri"})
    assert r.status_code == 403, r.text
    rid = await peran_tanpa_acuan({"customer": ["view"]}, label="Tanpa Acuan Versi")
    v1 = (await _peran(klien, kepala_admin, rid))["version"]
    assert (await _sifat(klien, kepala_admin, rid, {"kategori_kerja": "sales"})).status_code == 200
    assert (await _peran(klien, kepala_admin, rid))["version"] != v1


async def test_PRT4_U14_tidak_bisa_memberi_cakupan_lebih_luas(klien, kepala_admin, peran_tanpa_acuan, akun, sesi):
    pelaku = await peran_tanpa_acuan({"permission": ["view", "update"], "customer": ["view"]},
                                     label="Tanpa Acuan U14")
    assert (await _sifat(klien, kepala_admin, pelaku, {"data_scope": "milik_sendiri"})).status_code == 200
    sasaran = await peran_tanpa_acuan({"customer": ["view"]}, label="Sasaran U14")
    h = await sesi(await akun(pelaku))
    r = await _sifat(klien, h, sasaran, {"data_scope": "semua"})
    assert r.status_code == 403, r.text
    assert _detail(r) == "Anda tidak bisa memberi cakupan data lebih luas dari cakupan peran Anda sendiri."
    r = await _sifat(klien, h, sasaran, {"data_scope": "milik_sendiri"})
    assert r.status_code == 200, r.text
    # Membuat peran baru tanpa peran dasar (bawaan "semua") juga lebih luas → 403; dengan cakupan sendiri → 200.
    r = await klien.post("/api/access/roles", headers=h, json={"label": "Buatan U14", "permissions": {"customer": ["view"]}})
    assert r.status_code == 403, r.text
    r = await klien.post("/api/access/roles", headers=h, json={"label": "Buatan U14", "permissions": {"customer": ["view"]},
                                                              "traits": {"data_scope": "milik_sendiri"}})
    assert r.status_code == 200, r.text
    assert r.json()["traits"]["data_scope"] == "milik_sendiri"


async def test_PRT4_U15_migrasi_peran_desain_tanpa_acuan(klien, kepala_admin, db):
    rid = "cr_desain_lama_prt4"
    await db.custom_roles.insert_one({"id": rid, "label": "Desain Lama PRT4", "description": "fixture sisip",
                                      "base_role": "", "levels": {}, "created_at": WAKTU, "updated_at": WAKTU})
    await db.permission_settings.update_one({"id": "default"}, {"$set": {f"matrix.{rid}": {"design_request": ["view"]}},
                                                                "$pull": {"migrations_applied": "prt4:sifat-peran"}})
    await db.custom_roles.insert_one({"id": "cr_desain_pesanan_prt4", "label": "Desain Pesanan PRT4", "base_role": "",
                                      "levels": {}, "created_at": WAKTU, "updated_at": WAKTU})
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.cr_desain_pesanan_prt4": {
        "design_request": ["view"], "order": ["view"]}}})
    await _nyalakan_ulang()
    p = await _peran(klien, kepala_admin, rid)
    assert p["traits"]["data_scope"] == "milik_sendiri"
    assert "data_scope" in p["traits_overridden"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert rec["role_traits"][rid]["data_scope"] == "milik_sendiri"
    assert "prt4:sifat-peran" in rec["migrations_applied"]
    # Yang juga memegang order.view tidak disentuh (hari ini melihat semua pesanan).
    assert "cr_desain_pesanan_prt4" not in (rec.get("role_traits") or {})
    assert (await _peran(klien, kepala_admin, "cr_desain_pesanan_prt4"))["traits"]["data_scope"] == "semua"


# ─── Serah-terima (b) ─────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PRT4_U2_cakupan_milik_sendiri_peran_tanpa_acuan(klien, kepala_admin, peran_tanpa_acuan, akun, sesi,
                                                               siap):
    rid = await peran_tanpa_acuan({"customer": ["view"]}, label="Tanpa Acuan U2")
    h = await sesi(await akun(rid, entitas=(siap["pt"],)), entitas=siap["pt"])
    assert await _pelanggan(klien, h) == ["cust_prt4_A", "cust_prt4_B"]
    assert (await _sifat(klien, kepala_admin, rid, {"data_scope": "milik_sendiri"})).status_code == 200
    assert await _pelanggan(klien, h) == []


async def test_PRT4_U3_peran_berdasar_sales_ikut_daftar_pilih(klien, akun, siap, db):
    r = await klien.post("/api/access/roles", headers=siap["adm"], json={"label": "Sales Senior", "base_role": "sales"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    sS = await akun(rid, entitas=(siap["pt"],), email="prt4.ss@uji.id")
    siap["sS"] = sS
    if "traits" in r.json():   # kode baru: kategori kerja turunan peran dasar
        assert r.json()["traits"]["kategori_kerja"] == "sales"
    r = await klien.get("/api/sales-users", headers=siap["adm_pt"])
    assert r.status_code == 200, r.text
    assert sS["id"] in {u["id"] for u in r.json()}
    r = await klien.post("/api/customers/cust_prt4_A/reassign", headers=siap["adm_pt"],
                         json={"assigned_sales_id": sS["id"], "reason": "uji PR-T4"})
    assert r.status_code == 200, r.text
    await db.customers.update_one({"id": "cust_prt4_A"}, {"$set": {"assigned_sales_id": siap["sA"]["id"]}})


async def test_PRT4_U4_papan_peringkat_semua_akun_kategori_sales(klien, siap, db):
    # KM-T5 — papan peringkat = daftar sales PT (`incentive_targets.sales_roster`): akun aktif berkategori sales yang
    # ditugaskan di PT papan; dulu semua akun berkategori sales seluruh grup. Dibaca dengan PT uji PR-T4 aktif.
    r = await klien.get("/api/sales/leaderboard", headers=siap["adm_pt"])
    assert r.status_code == 200, r.text
    # Berkategori sales = peran Sales + peran kustom yang (turunan dari) peran dasar Sales; tidak ada yang diubah Admin.
    kategori = ["sales", *[c["id"] async for c in db.custom_roles.find({"base_role": "sales"}, {"id": 1})]]
    harap = await db.users.count_documents({"role": {"$in": kategori}, "status": "active",
                                            "$or": [{"allowed_entity_ids": siap["pt"]}, {"home_entity_id": siap["pt"]}]})
    assert harap >= 3   # sA + sB + sS
    assert len(r.json()) == harap
    assert siap["sS"]["id"] in {x["sales_id"] for x in r.json()}


async def test_PRT4_U5_kurir_tanpa_acuan_sebagai_sopir(klien, kepala_admin, akun, sesi, siap, db):
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Kurir", "permissions": {"logistics": ["view", "update"]},
        "traits": {"kategori_kerja": "sopir", "data_scope": "milik_sendiri"}})
    assert r.status_code == 200, r.text
    kr = await akun(r.json()["id"], entitas=(siap["pt"],), email="prt4.kr@uji.id")
    r = await klien.get("/api/logistics/drivers", headers=siap["adm_pt"])
    assert r.status_code == 200, r.text
    assert kr["id"] in {u["id"] for u in r.json()}
    await db.logistics_deliveries.insert_one({
        "id": "dlv_prt4_1", "number": "DLV-PRT4-1", "entity_id": siap["pt"], "status": "in_transit",
        "driver_user_id": siap["sA"]["id"], "shipment_ids": [], "created_at": WAKTU, "updated_at": WAKTU})
    r = await klien.post("/api/logistics/deliveries/dlv_prt4_1/positions", headers=await sesi(kr, entitas=siap["pt"]),
                         json={"location": "Jl. Uji", "note": "uji PR-T4"})
    assert r.status_code == 403, r.text
    assert _detail(r).startswith("Pengiriman ini bukan tugas Anda")


async def test_PRT4_U6_sales_diperluas_bertahan_nyala_ulang(klien, kepala_admin, sesi, siap):
    hA = await sesi(siap["sA"], entitas=siap["pt"])
    assert await _pelanggan(klien, hA) == ["cust_prt4_A"]
    r = await _sifat(klien, kepala_admin, "sales", {"data_scope": "semua"})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    assert await _pelanggan(klien, hA) == ["cust_prt4_A", "cust_prt4_B"]
    assert "data_scope" in (await _peran(klien, kepala_admin, "sales"))["traits_overridden"]
    assert (await _sifat(klien, kepala_admin, "sales", {"data_scope": None})).status_code == 200
    assert await _pelanggan(klien, hA) == ["cust_prt4_A"]


async def test_PRT4_U7_cakupan_tim_lewat_kepala_unit(klien, kepala_admin, sesi, siap, db):
    await db.hr_employees.insert_many([
        {"id": "emp_prt4_a", "name": "Karyawan sA", "user_id": siap["sA"]["id"], "entity_id": siap["pt"],
         "department_id": "org_prt4_tim", "status": "active"},
        {"id": "emp_prt4_b", "name": "Karyawan sB", "user_id": siap["sB"]["id"], "entity_id": siap["pt"],
         "department_id": "org_prt4_tim", "status": "active"}])
    await db.hr_org_units.insert_one({"id": "org_prt4_tim", "name": "Tim Sales PRT4", "unit_type": "department",
                                      "parent_id": "", "head_employee_id": "emp_prt4_a", "entity_id": siap["pt"]})
    assert (await _sifat(klien, kepala_admin, "sales", {"data_scope": "tim"})).status_code == 200
    try:
        assert await _pelanggan(klien, await sesi(siap["sA"], entitas=siap["pt"])) == ["cust_prt4_A", "cust_prt4_B"]
        assert await _pelanggan(klien, await sesi(siap["sB"], entitas=siap["pt"])) == ["cust_prt4_B"]
        r = await klien.get("/api/sales-orders", headers=await sesi(siap["sA"], entitas=siap["pt"]))
        assert sorted(o["id"] for o in r.json()) == ["so_prt4_A", "so_prt4_B"]
    finally:
        assert (await _sifat(klien, kepala_admin, "sales", {"data_scope": None})).status_code == 200


async def test_PRT4_U9_ikut_menerima_notifikasi_peran_lain(klien, kepala_admin, peran_tanpa_acuan, akun, sesi, db):
    await db.notifications.insert_one({"id": "ntf_prt4_wh", "type": "info", "title": "Uji PR-T4 gudang", "body": "",
                                       "recipient_role": "warehouse", "recipient_user": "", "entity_id": "ent_ksc",
                                       "severity": "info", "read": False, "created_at": WAKTU})
    rid = await peran_tanpa_acuan({"customer": ["view"]}, label="Tanpa Acuan U9")
    h = await sesi(await akun(rid))

    async def ids():
        r = await klien.get("/api/notifications", headers=h)
        assert r.status_code == 200, r.text
        return {n["id"] for n in r.json()}

    assert "ntf_prt4_wh" not in await ids()
    assert (await _sifat(klien, kepala_admin, rid, {"notify_like": ["warehouse"]})).status_code == 200
    assert "ntf_prt4_wh" in await ids()


async def test_PRT4_U10_peran_berdasar_manajer_bukan_pelaksana_giliran(klien, kepala_admin):
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Manajer Cabang", "base_role": "manager", "permissions": {"order": ["view", "deliver"]}})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    from services.turn_notification_service import turn_roles
    # Aturan giliran berizin order.deliver (TURN_MAP tidak memuatnya — aturan uji dibentuk sama dengan isi TURN_MAP).
    roles = await turn_roles({"roles": ("warehouse",), "permission": ("order", "deliver"), "title": "uji"})
    assert "warehouse" in roles
    assert rid not in roles and "manager" not in roles
    # Aturan yang memang menyebut manajer tetap sampai ke peran yang ikut menerima notifikasi Manajer.
    roles = await turn_roles({"roles": ("manager",), "permission": ("order", "deliver"), "title": "uji"})
    assert "manager" in roles and rid in roles


async def test_PRT4_U11_meja_saya_dari_kategori(klien, kepala_admin, peran_tanpa_acuan, akun, sesi):
    rid = await peran_tanpa_acuan({"customer": ["view"]}, label="Tanpa Acuan U11")
    h = await sesi(await akun(rid))
    r = await klien.get("/api/desks/me", headers=h)
    assert r.status_code == 404, r.text
    assert "cr_" not in _detail(r)
    assert _detail(r) == "Peran Anda belum punya meja kerja. Buka menu yang tersedia di samping."
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={
        "permissions": {"customer": ["view"], "wms": ["view"]}, "traits": {"kategori_kerja": "gudang"}})
    assert r.status_code == 200, r.text
    r = await klien.get("/api/desks/me", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Meja Operator Gudang"


async def test_PRT4_U12_kpi_sales_lain_butuh_izin(klien, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir, akun,
                                                  sesi, siap):
    rid = await peran_tanpa_acuan({"order": ["view", "view_sales_kpi"]}, label="Tanpa Acuan U12")
    jalur = f"/api/sales/kpi?sales_id={siap['sA']['id']}&entity_id={siap['pt']}"
    ta = await akun(rid, entitas=(siap["pt"],))
    r = await klien.get(jalur, headers=await sesi(ta, entitas=siap["pt"]))
    assert r.status_code == 200, r.text
    assert r.json()["sales_id"] == siap["sA"]["id"] and r.json()["orders_count"] == 1
    for peran in (await peran_manajer_kosong(), peran_sopir):
        u = await akun(peran, entitas=(siap["pt"],))
        r = await klien.get(jalur, headers=await sesi(u, entitas=siap["pt"]))
        assert r.status_code == 403, (peran, r.text)
    # Tanpa order.view_sales_kpi: permintaan KPI sales lain = KPI dirinya (perilaku lama untuk peran non-pengawas).
    rid2 = await peran_tanpa_acuan({"order": ["view"]}, label="Tanpa Acuan U12b")
    u2 = await akun(rid2, entitas=(siap["pt"],))
    r = await klien.get(jalur, headers=await sesi(u2, entitas=siap["pt"]))
    assert r.status_code == 200 and r.json()["sales_id"] == u2["id"]


# U16 — tidak ada cek nama peran di jangkar tabel 1 dan kueri `users.role` persis di jangkar tabel 2.
TABEL_1 = {
    "services/sales_ownership.py": ["is_owner_locked"],
    "services/customer_service.py": ["scope_query", "can_collect_customer", "collection_worklist"],
    # KM-T5 — `list_targets` (GET /api/sales-targets) dihapus.
    "routers/crm.py": ["list_credit_overrides", "get_credit_override", "_kpi_scope", "list_incentives"],
    "routers/crm_omnichannel.py": ["_read_scope", "_guard_lead_owner", "delete_interaction"],
    "routers/customers.py": ["create_customer"],
    "routers/admin.py": ["import_customers"],
    "routers/price_approvals.py": ["list_price_approvals", "price_approval_stats"],
    "routers/sample_orders.py": ["cancel_sample"],
    "routers/sales_orders.py": ["create_order"],
    "routers/design_requests.py": ["_own_only"],
    "services/export_engine.py": ["_role_whitelist", "_owner_clause"],
    "routers/logistics.py": ["_guard_driver_write"],
    "routers/warehouses.py": ["list_warehouses"],
    "services/location_scope.py": ["warehouse_ids_for"],
    "services/analytics_engine.py": ["build_scope"],
    "services/analytics_facts.py": ["attribute_sales"],
    "services/hr_payroll_service.py": ["_commission_for"],
    "services/logistics_service.py": ["_assert_driver_valid"],
    "services/product_exclusivity.py": ["is_restricted_role"],
    "dependencies.py": ["current_user"],
    "services/stock_figures.py": ["_work_site_ids"],
}
#: `can_access_customer` — hanya bagian sales (admin/manajer lolos sebelum cek PT = PR-T6, di luar lingkup).
TABEL_1_SALES_SAJA = {"services/customer_service.py": ["can_access_customer"]}
TABEL_2 = {
    "routers/crm.py": ["list_sales_users", "reassign_customer", "create_incentive"],   # KM-T5 — create_target dihapus
    "routers/customers.py": ["create_customer"],
    "routers/products.py": ["list_sales_owners"],
    "routers/admin.py": ["import_customers", "export_customers"],
    "services/sales_force_service.py": ["leaderboard"],
    "services/gl_service.py": ["post_incentive_accrual"],
    "services/product_exclusivity.py": ["normalize"],
    "services/logistics_service.py": ["list_drivers"],
    "services/design_request_service.py": ["designers"],
}
KONSTANTA_DIHAPUS = ["OWNER_LOCKED_ROLES", "FULL_VIEW_ROLES", "DESIGN_FULL_VIEW", "MASTER_SCOPE_ROLES", "SCOPED_ROLES",
                     "SALES_ROLES"]
_ROLE_PERSIS = re.compile(r"""["']role["']\s*:\s*["'](sales|driver|designer)["']""")


def _sumber_fungsi(berkas: str, nama: str) -> str:
    src = (BACKEND / berkas).read_text()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nama:
            return ast.get_source_segment(src, n) or ""
    raise AssertionError(f"{berkas}: fungsi {nama} tidak ditemukan")


async def test_PRT4_U16_tidak_ada_nama_peran_di_jangkar():
    sisa = []
    for berkas, fungsi in TABEL_1.items():
        for nama in fungsi:
            if "role_in(" in _sumber_fungsi(berkas, nama):
                sisa.append(f"{berkas}:{nama} role_in(")
    for berkas, fungsi in TABEL_1_SALES_SAJA.items():
        for nama in fungsi:
            if re.search(r"""role_in\([^\n]*\(\s*["']sales["']""", _sumber_fungsi(berkas, nama)):
                sisa.append(f"{berkas}:{nama} role_in(…sales)")
    for berkas, fungsi in TABEL_2.items():
        for nama in fungsi:
            if _ROLE_PERSIS.search(_sumber_fungsi(berkas, nama)):
                sisa.append(f"{berkas}:{nama} role persis")
    for p in BACKEND.rglob("*.py"):
        if "tests" in p.parts or "tests_mem" in p.parts:
            continue
        for k in KONSTANTA_DIHAPUS:
            if re.search(rf"^\s*{k}\s*[:=]", p.read_text(), re.M):
                sisa.append(f"{p.relative_to(BACKEND)}: {k}")
    assert not sisa, sisa
