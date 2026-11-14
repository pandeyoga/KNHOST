"""PR-T6 — layar Peran & Hak Akses dan Akun & Akses menjawab "peran ini akhirnya bisa apa" (docs/blueprint/unit/PR-T6.md).

U1–U16 di sini; U17 (kode jawaban Manajer seed sebelum/sesudah) di `test_PRT6_sapuan.py` (basis data sendiri).
Peran uji baku `02` §6: "Tanpa Acuan" (`peran_tanpa_acuan`), "Manajer Kosong" (`peran_manajer_kosong`), Sopir.
Satu database per modul: uji yang mengubah peran bawaan (Finance, Manajer) mengembalikannya di akhir uji itu.
Fixture yang disisipkan langsung ke database: karyawan HR (U11), akun dengan penugasan PT kedua (U13), pelanggan di PT
uji (U10). Sisanya alur lewat API.
"""
from __future__ import annotations

import re

import pytest

import server
from pembantu import pt_uji

pytestmark = pytest.mark.anyio

WAKTU = "2026-11-10T03:00:00+00:00"
POLA_KODE = re.compile(r"[a-z_]+\.[a-z_]+")


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _h_peran(akun, sesi, peran: str, **kw):
    return await sesi(await akun(peran, **kw))


async def _peran(klien, h, rid: str) -> dict:
    r = await klien.get(f"/api/access/roles/{rid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _roles_publik(klien, h) -> dict:
    r = await klien.get("/api/roles", headers=h)
    assert r.status_code == 200, r.text
    return {x["id"]: x for x in r.json()["roles"]}


# ── Pesan penolakan (Z6) ───────────────────────────────────────────────────────────────────────────────────────────
async def test_PRT6_U1_pesan_penolakan_kalimat_dan_header(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({}, label="Tanpa Acuan PRT6 Kosong")
    h = await _h_peran(akun, sesi, rid)
    r = await klien.get("/api/goods-receipts", headers=h)
    assert r.status_code == 403, r.text
    assert _detail(r) == ("Anda belum punya akses untuk melihat Kedatangan Barang. "
                          "Minta Admin menambahkan akses 'Operasi Gudang'.")
    assert "goods_receipt.view" not in _detail(r)
    assert r.headers.get("X-Permission-Denied") == "goods_receipt.view"


async def test_PRT6_U2_sapuan_sopir_tanpa_kode_di_pesan_403(klien, akun, sesi, peran_sopir):
    h = await _h_peran(akun, sesi, peran_sopir)
    jalur = sorted({rt.path for rt in server.app.routes
                    if "GET" in (getattr(rt, "methods", None) or set()) and rt.path.startswith("/api/")})
    assert len(jalur) > 300
    salah = []
    for p in jalur:
        url = re.sub(r"\{[^}]+\}", "x", p)
        r = await klien.get(url, headers=h)
        if r.status_code != 403:
            continue
        try:
            det = _detail(r)
        except Exception:   # noqa: BLE001 — jawaban bukan JSON
            det = r.text
        if POLA_KODE.search(det) or "Permission" in det or "Role" in det or "cr_" in det:
            salah.append((p, det[:160]))
    assert not salah, salah


# ── Ringkasan peran, pratinjau, menu peran bawaan ─────────────────────────────────────────────────────────────────
async def test_PRT6_U3_ringkasan_peran_berizin(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                               peran_sopir):
    ta = await peran_tanpa_acuan({"permission": ["view"]}, label="Tanpa Acuan PRT6 Lihat")
    mk = await peran_manajer_kosong()
    kode = []
    for rid in (ta, mk, peran_sopir):
        r = await klien.get("/api/access/roles/sales/summary", headers=await _h_peran(akun, sesi, rid))
        kode.append(r.status_code)
        if rid == ta:
            assert r.status_code == 200, r.text
            s = r.json()
    assert kode == [200, 403, 403]
    assert s["data_scope"]["value"] == "milik_sendiri"
    assert s["home"]["view"] == "sales-home"
    assert s["data_scope"]["label"] == "Milik sendiri"
    assert {"home", "data_scope", "kategori", "cross_entity", "approvals", "modules", "risky",
            "follows_base"} <= set(s)
    penjualan = next(m for m in s["modules"] if m["id"] == "penjualan")
    halaman = next(p for p in penjualan["pages"] if p["label"] == "Pesanan Penjualan (SO)")
    assert "Lihat" in halaman["can"] and "Kirim tanpa lunas (pengecualian termin CBD/DP)" in halaman["cannot"]


async def test_PRT6_U4_pratinjau_memuat_ringkasan_dan_menu_tambahan(klien, kepala_admin):
    r = await klien.post("/api/access/roles/preview", headers=kepala_admin,
                         json={"role_id": "sales", "levels": {"hr": "view"}})
    assert r.status_code == 200, r.text
    j = r.json()
    hr = next((m for m in j["summary"]["modules"] if m["id"] == "hr"), None)
    assert hr is not None and hr["level"] == "view", j["summary"]["modules"]
    assert "hrd" in j["nav_added"]
    assert "turn_alerts" in j and "screens" in j   # jawaban lama tetap


async def test_PRT6_U5_menu_tambahan_peran_bawaan_kosong_saat_pasang(klien, kepala_admin):
    roles = await _roles_publik(klien, kepala_admin)
    bawaan = [x for x in roles.values() if not x["custom"]]
    assert len(bawaan) == 13
    for x in bawaan:
        assert x["nav"] == {"add": [], "remove": []}, (x["id"], x["nav"])


async def test_PRT6_U6_menu_peran_bawaan_bertambah_dari_izin(klien, kepala_admin):
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin, json={"levels": {"hr": "view"}})
    assert r.status_code == 200, r.text
    try:
        add = (await _roles_publik(klien, kepala_admin))["finance"]["nav"]["add"]
        assert "hrd" in add and "hr-people" in add, add
    finally:
        assert (await klien.post("/api/access/roles/finance/reset", headers=kepala_admin)).status_code == 200


# ── Peran dasar & lintas PT ───────────────────────────────────────────────────────────────────────────────────────
async def _buat_peran(klien, h, label: str, base: str, **extra) -> str:
    r = await klien.post("/api/access/roles", headers=h, json={"label": label, "base_role": base, **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_PRT6_U7_ganti_peran_dasar_tanpa_mengubah_izin(klien, kepala_admin):
    k = await _buat_peran(klien, kepala_admin, "K PRT6", "finance")
    awal = await _peran(klien, kepala_admin, k)
    r = await klien.patch(f"/api/access/roles/{k}", headers=kepala_admin, json={"base_role": "sales"})
    assert r.status_code == 200, r.text
    sesudah = await _peran(klien, kepala_admin, k)
    assert sesudah["base_role"] == "sales"
    assert sesudah["permissions"] == awal["permissions"]
    assert sesudah["traits"]["data_scope"] == "milik_sendiri"
    assert sesudah["cross_entity"] == awal["cross_entity"]   # lintas PT tidak ikut berganti (dipatok)


async def test_PRT6_U8_peran_dasar_ditolak(klien, kepala_admin):
    r = await klien.patch("/api/access/roles/manager", headers=kepala_admin, json={"base_role": "sales"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Peran dasar hanya bisa diatur pada peran kustom."
    k = await _buat_peran(klien, kepala_admin, "K PRT6 Dua", "finance")
    r = await klien.patch(f"/api/access/roles/{k}", headers=kepala_admin, json={"base_role": "admin"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Peran Admin tidak bisa dijadikan peran dasar."
    r = await klien.patch(f"/api/access/roles/{k}", headers=kepala_admin, json={"base_role": "tidak_ada"})
    assert (r.status_code, _detail(r)) == (400, "Peran dasar tidak dikenal.")
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={"label": "K PRT6 Admin", "base_role": "admin"})
    assert (r.status_code, _detail(r)) == (400, "Peran Admin tidak bisa dijadikan peran dasar.")
    assert (await _peran(klien, kepala_admin, k))["base_role"] == "finance"


async def test_PRT6_U9_lintas_pt_peran_kustom_eksplisit(klien, akun, db, kepala_admin):
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin, json={"cross_entity": True})
    assert r.status_code == 200, r.text
    try:
        kasir = await _buat_peran(klien, kepala_admin, "Kasir PRT6", "finance")
        p = await _peran(klien, kepala_admin, kasir)
        assert p["cross_entity"] is True and p["cross_entity_default"] is True   # bawaan = nilai efektif Finance
        a = await akun(kasir, entitas=("ent_ksc", "ent_kanda"))
        r = await klien.patch(f"/api/access/roles/{kasir}", headers=kepala_admin, json={"cross_entity": False})
        assert r.status_code == 200, r.text
        tinjau = r.json()["accounts_to_review"]
        assert [x["id"] for x in tinjau] == [a["id"]]
        assert len(tinjau[0]["allowed_entities"]) == 2 and all("ent_" not in x for x in tinjau[0]["allowed_entities"])
        assert (await _peran(klien, kepala_admin, kasir))["cross_entity"] is False
        assert (await db.users.find_one({"id": a["id"]}))["allowed_entity_ids"] == ["ent_ksc", "ent_kanda"]
    finally:
        await klien.post("/api/access/roles/finance/reset", headers=kepala_admin)


async def test_PRT6_U10_manajer_tanpa_lintas_pt_ditolak_pelanggan_pt_lain(klien, sesi, db, kepala_admin):
    pt = await pt_uji("PRT6")
    from services.entity_lifecycle_service import invalidate_status_cache
    invalidate_status_cache()
    await db.customers.insert_one({"id": "cust_prt6_lain", "code": "CUST-PRT6", "name": "Pelanggan PRT6",
                                   "entity_id": pt, "status": "active", "segment": "retail",
                                   "created_at": WAKTU, "updated_at": WAKTU})
    mgr = await db.users.find_one({"email": "manager@kainnusantara.id"}, {"_id": 0})
    assert pt not in (mgr.get("allowed_entity_ids") or [])
    r = await klien.patch("/api/access/roles/manager", headers=kepala_admin, json={"cross_entity": False})
    assert r.status_code == 200, r.text
    try:
        r = await klien.get("/api/customers/cust_prt6_lain/360", headers=await sesi(mgr))
        assert r.status_code == 403, r.text
    finally:
        r = await klien.patch("/api/access/roles/manager", headers=kepala_admin, json={"cross_entity": True})
        assert r.status_code == 200, r.text


# ── Akun ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PRT6_U11_tautan_karyawan_lama_dibersihkan(klien, db, kepala_admin):
    for e in ("e1", "e2"):
        await db.hr_employees.insert_one({"id": f"emp_prt6_{e}", "code": f"PRT6-{e.upper()}", "name": f"Karyawan {e}",
                                          "entity_id": "ent_ksc", "status": "active", "user_id": "",
                                          "created_at": WAKTU})
    r = await klien.post("/api/users", headers=kepala_admin, json={
        "name": "Akun Prt Enam", "email": "akun.prt6@uji.id", "role": "sales", "password": "rahasia123",
        "employee_id": "emp_prt6_e1", "home_entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    x = r.json()["id"]
    assert (await db.hr_employees.find_one({"id": "emp_prt6_e1"}))["user_id"] == x
    r = await klien.patch(f"/api/users/{x}", headers=kepala_admin, json={"data": {"employee_id": "emp_prt6_e2"}})
    assert r.status_code == 200, r.text
    assert not (await db.hr_employees.find_one({"id": "emp_prt6_e1"})).get("user_id")
    assert (await db.hr_employees.find_one({"id": "emp_prt6_e2"}))["user_id"] == x
    r = await klien.patch(f"/api/users/{x}", headers=kepala_admin, json={"data": {"employee_id": ""}})
    assert r.status_code == 200, r.text
    assert not (await db.hr_employees.find_one({"id": "emp_prt6_e2"})).get("user_id")


async def test_PRT6_U12_sandi_wajib_minimal_8(klien, db, kepala_admin):
    dasar = {"name": "Tanpa Sandi", "email": "tanpa.sandi.prt6@uji.id", "role": "sales", "home_entity_id": "ent_ksc"}
    r = await klien.post("/api/users", headers=kepala_admin, json=dasar)
    assert r.status_code in (400, 422), r.text
    r = await klien.post("/api/users", headers=kepala_admin, json={**dasar, "password": "1234567"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Kata sandi minimal 8 karakter."
    assert not await db.users.find_one({"email": dasar["email"]})


async def test_PRT6_U13_pindah_massal_lewat_ubah_akun(klien, akun, sesi, db, kepala_admin):
    # Fixture: dua akun Gudang dengan penugasan PT kedua (+ satu id PT yang sudah tidak aktif — dibuang saat dihitung ulang).
    g = [await akun("warehouse", entitas=("ent_ksc", "ent_kanda")) for _ in range(2)]
    for a in g:
        await db.users.update_one({"id": a["id"]}, {"$push": {"allowed_entity_ids": "ent_tidak_aktif_prt6"}})
        await sesi(a)
    seed = await db.users.find_one({"email": "warehouse@kainnusantara.id"}, {"_id": 0, "id": 1})
    ids = sorted([seed["id"], *[a["id"] for a in g]])
    sebelum = await db.audit_logs.count_documents({"action": "user_updated", "entity_id": {"$in": ids}})
    r = await klien.post("/api/access/roles/warehouse/move-users", headers=kepala_admin, json={"to_role": "sales"})
    assert r.status_code == 200, r.text
    assert sorted(r.json()["user_ids"]) == ids
    for a in g:
        u = await db.users.find_one({"id": a["id"]})
        assert u["role"] == "sales"
        assert u["allowed_entity_ids"] == ["ent_ksc", "ent_kanda"]   # aturan Sales: PT utama + penugasan yang sah
        assert await db.sessions.count_documents({"user_id": a["id"]}) == 0
    sesudah = await db.audit_logs.count_documents({"action": "user_updated", "entity_id": {"$in": ids}})
    assert sesudah - sebelum == len(ids)
    assert await db.audit_logs.count_documents({"action": "role_users_moved", "entity_id": "warehouse"}) == 1
    # kembalikan akun seed Gudang (uji lain di modul ini tidak bergantung padanya, tetapi data seed tetap utuh)
    await db.users.update_one({"id": seed["id"]}, {"$set": {"role": "warehouse"}})


async def test_PRT6_U14_riwayat_peran_dari_selisih(klien, kepala_admin):
    awal = (await _peran(klien, kepala_admin, "sales"))["permissions"]
    tanpa = {k: [a for a in v if not (k == "order" and a == "cancel")] for k, v in awal.items()}
    assert "cancel" in awal["order"]
    for izin in (tanpa, awal):
        r = await klien.patch("/api/access/roles/sales", headers=kepala_admin, json={"permissions": izin})
        assert r.status_code == 200, r.text
    r = await klien.get("/api/access/roles/sales/history", headers=kepala_admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2, items
    baru, lama = items   # terbaru dulu
    assert lama["at"] <= baru["at"]
    assert lama["removed"] == ["Pesanan Penjualan (SO): Batalkan"] and lama["added"] == []
    assert "Pesanan Penjualan (SO): Batalkan" in baru["added"] and baru["removed"] == []
    assert lama["action_label"] and lama["actor"] and isinstance(lama["users"], int)


async def test_PRT6_U15_bisa_dihapus_dihitung_dari_semua_akun(klien, akun, db, kepala_admin):
    rid = await _buat_peran(klien, kepala_admin, "Peran Nonaktif PRT6", "sales")
    a = await akun(rid)
    await db.users.update_one({"id": a["id"]}, {"$set": {"status": "inactive"}})
    p = await _peran(klien, kepala_admin, rid)
    assert p["deletable"] is False
    assert p["users_inactive"] == 1
    assert p["users"] == 0


async def test_PRT6_U16_menu_tersembunyi_saat_membuat(klien, kepala_admin):
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Sembunyi PRT6", "base_role": "finance", "hidden_views": ["finance-cases"]})
    assert r.status_code == 200, r.text
    assert r.json()["hidden_views"] == ["finance-cases"]
    assert (await _peran(klien, kepala_admin, r.json()["id"]))["hidden_views"] == ["finance-cases"]


# ── Tambahan: bagian server uji jalan U18/U19 (padanan lapis B; uji jalan peramban di lingkungan A) ─────────────────
async def test_PRT6_U18b_server_peran_dasar_dan_salin_hak_akses(klien, kepala_admin):
    izin = (await _peran(klien, kepala_admin, "sales_admin"))["permissions"]
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "U18 PRT6", "base_role": "sales", "permissions": izin})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    s = (await klien.get(f"/api/access/roles/{rid}/summary", headers=kepala_admin)).json()
    assert s["data_scope"]["label"] == "Milik sendiri"
    assert s["approvals"] == {"follows_rank_of": "Sales"}   # database tiruan: `approval_policies` belum berisi
    assert any(pg["can"] and pg["cannot"] for m in s["modules"] for pg in m["pages"])
    assert "Data yang terlihat mengikuti Sales" in s["follows_base"]
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"base_role": "finance"})
    assert r.status_code == 200, r.text
    h = (await klien.get(f"/api/access/roles/{rid}/history", headers=kepala_admin)).json()["items"]
    assert [x["action"] for x in h] == ["role_access_updated", "custom_role_created"]
    assert "Peran dasar: Sales → Finance" in h[0]["other"] and h[0]["added"] == [] and h[0]["removed"] == []
    assert h[1]["action_label"] == "Peran dibuat" and "Peran dasar: Sales" in h[1]["other"]


async def test_PRT6_U19b_server_peran_lihat_saja(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"permission": ["view"]}, label="U19 PRT6 Lihat")
    h = await _h_peran(akun, sesi, rid)
    for jalur in ("/api/access/roles", "/api/access/roles/sales/summary", "/api/access/roles/sales/history"):
        assert (await klien.get(jalur, headers=h)).status_code == 200, jalur
    r = await klien.patch("/api/access/roles/sales", headers=h, json={"levels": {"hr": "view"}})
    assert r.status_code == 403, r.text
    assert _detail(r) == ("Anda belum punya akses untuk mengubah Peran & Hak Akses. "
                          "Minta Admin menambahkan akses 'Peran & Hak Akses'.")
    assert r.headers.get("X-Permission-Denied") == "permission.update"
