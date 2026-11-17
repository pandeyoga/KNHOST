"""K-FIN-01 — Finance memegang akses yang sama dengan Manajer (keputusan pemilik 17 Nov 2026 malam, kata-kata asli:
"untuk sekarang finance juga memiliki akses yang sama dengan manager dan jangan dipisah"). Menggantikan pembagian K-SDM-01.

Lapisan yang disamakan: izin bawaan (`permissions_config.KFIN01_*`, blok paling akhir), lintas badan usaha, kategori kerja
"pengawas" (Meja Saya = Meja Manajer), Aturan Persetujuan bawaan & tersimpan (baris yang menyebut Manajer ikut menyebut
Finance), dan gerbang nama peran lama (`role_registry.SETARA_PERAN` lewat `role_in`/`role_satisfies`). Yang SENGAJA tetap:
kontrol dua orang per PENGGUNA (`kontrol.<aksi>.min_orang`), peringkat Finance (2), dan baris persetujuan khusus Admin.

U1  bawaan: Finance ⊇ Manajer (semua sumber daya & aksi), kelebihan Finance hanya keputusan lamanya sendiri; menu modul;
    sifat peran; matriks efektif lewat API.
U2  Aturan Persetujuan: baris bawaan yang menyebut Manajer menyebut Finance, baris khusus Admin tidak; `can_decide`.
U3  instalasi lama (VPS): matriks & `defaults_applied` tanpa pasangan K-FIN-01 + baris Aturan Persetujuan tersimpan tanpa
    Finance → start → semua tiba; Admin mencabut satu pasangan → start → pencabutan bertahan; kembalikan bawaan → kembali.
U4  HTTP di PT uji: Finance mengesahkan masukan gaji & proses gaji, menganulir, membuat jurnal manual, dan membuka Meja
    Manajer — dengan kontrol dua orang menyala, Finance yang mengajukan proses TIDAK bisa mengesahkannya sendiri
    (Finance lain bisa).
"Hari ini" dibekukan 3 Nov 2026 (`services.book_date._sekarang`), masa gaji Oktober 2026.
"""
import datetime

import pytest

import bootstrap
from pembantu import pt_uji as _pt_uji

pytestmark = pytest.mark.anyio

OKT = "2026-10"
HARI_INI = datetime.datetime(2026, 11, 3, 3, 0, tzinfo=datetime.timezone.utc)   # 3 Nov 2026 10.00 WIB
#: Izin bawaan Finance yang TIDAK dimiliki Manajer — keputusan pemilik sebelum K-FIN-01 (GL-01/GL-08; harga internal 2026-10).
KELEBIHAN_FINANCE = {"gl_mapping": {"update"}, "interco_price": {"view", "set"}}


@pytest.fixture(scope="module", autouse=True)
def _hari_ini_3_nov():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


def _himpunan(perms: dict) -> dict:
    return {k: set(v) for k, v in (perms or {}).items() if v}


def _selisih(a: dict, b: dict) -> dict:
    """Pasangan di `a` yang tidak ada di `b`."""
    return {r: acts - b.get(r, set()) for r, acts in _himpunan(a).items() if acts - b.get(r, set())}


async def _peran(klien, h, rid: str) -> dict:
    r = await klien.get(f"/api/access/roles/{rid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ── U1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KFIN01_U1_finance_mencakup_manajer(klien, kepala_admin):
    import role_registry as reg
    from access_modules import nav_allowed_for_perms
    from permissions_config import DEFAULT_PERMISSIONS, KFIN01_DEFAULT_PAIRS, KFIN01_SETARA
    from services.role_desk_service import desk_of

    fin, mgr = DEFAULT_PERMISSIONS["finance"], DEFAULT_PERMISSIONS["manager"]
    # Blok K-FIN-01 harus tetap paling akhir: pasangan Manajer yang ditambahkan sesudahnya memerahkan baris ini.
    assert _selisih(mgr, _himpunan(fin)) == {}, _selisih(mgr, _himpunan(fin))
    assert _selisih(fin, _himpunan(mgr)) == KELEBIHAN_FINANCE
    assert KFIN01_SETARA == ("finance", "manager") and KFIN01_DEFAULT_PAIRS["finance"]
    assert {"approve", "void"} <= set(fin["payroll"]) and {"delete", "manage_org"} <= set(fin["hr"])
    assert {"create", "void", "manage"} <= set(fin["accounting"]) and {"unlock", "backdate"} <= set(fin["period"])
    for perms in (fin, mgr):   # tidak ada aksi ganda (salinan daftar, bukan alias)
        assert all(len(a) == len(set(a)) for a in perms.values())
    assert fin["payroll"] is not mgr["payroll"]

    # menu yang dibuka modul
    assert set(nav_allowed_for_perms(mgr)) <= set(nav_allowed_for_perms(fin))

    # sifat & registry
    assert reg.ROLES["finance"]["cross_entity"] is True and "finance" in reg.CROSS_ENTITY_ROLES
    assert reg.category_of("finance") == "pengawas" and desk_of({"role": "finance"}) == "manager"
    assert reg.role_in("finance", ("admin", "manager")) and not reg.role_in("manager", ("finance",))
    assert reg.role_satisfies("finance", "manager") and not reg.role_satisfies("finance", "admin")
    assert reg.rank_of("finance") == 2   # peringkat tetap: aturan "≥ finance" (bayar sample) tidak menyempit

    # matriks efektif lewat API (basis data baru)
    f = _himpunan((await _peran(klien, kepala_admin, "finance"))["permissions"])
    m = _himpunan((await _peran(klien, kepala_admin, "manager"))["permissions"])
    assert _selisih(m, f) == {}, _selisih(m, f)
    r = await klien.get("/api/roles", headers=kepala_admin)
    assert r.status_code == 200, r.text
    pub = {x["id"]: x for x in (r.json().get("roles") if isinstance(r.json(), dict) else r.json())}
    assert pub["finance"]["cross_entity"] is True and pub["finance"]["kategori_kerja"] == "pengawas"
    assert pub["finance"]["home_view"] == "finance-desk"   # halaman awal tetap Meja Finance (pilihan, bukan akses)


# ── U2 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KFIN01_U2_aturan_persetujuan_bawaan(db):
    from services import approval_policy_service as aps
    assert await db.approval_policies.count_documents({}) == 0
    rows = await aps.build_default_rows("all")
    dengan_manajer = [r for r in rows if "manager" in (r.get("roles") or [])]
    assert len(dengan_manajer) >= 15
    tanpa = [(r["doc_kind"], r["level"]) for r in dengan_manajer if "finance" not in r["roles"]]
    assert tanpa == [], tanpa
    hanya_admin = [r for r in rows if r.get("roles") == ["admin"]]
    assert hanya_admin and all("finance" not in r["roles"] for r in hanya_admin)

    fin = {"id": "uji_fin", "name": "Uji Finance", "role": "finance"}
    jt = 1_000_000
    for kind, amt in (("vendor_bill", 5 * jt), ("purchase_order", 150 * jt), ("sales_order.kredit", 10 * jt),
                      ("payment_variance.hapus_sisa", 1 * jt), ("cash_advance", 1 * jt)):
        res = await aps.can_decide(kind, "ent_ksc", amt, fin)
        assert res["allowed"], (kind, res)
    # Rentang khusus Admin tetap khusus Admin (Manajer pun tidak).
    for kind, amt, level in (("amendment", 60 * jt, 1), ("purchase_order", 600 * jt, 2), ("cash_advance", jt, 2)):
        for role in ("finance", "manager"):
            res = await aps.can_decide(kind, "ent_ksc", amt, {"id": f"uji_{role}", "role": role}, level)
            assert not res["allowed"], (kind, role, res)


# ── U3 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KFIN01_U3_instalasi_lama_menerima_dan_pencabutan_bertahan(klien, db, kepala_admin):
    from permissions_config import DEFAULT_PERMISSIONS, KFIN01_DEFAULT_PAIRS
    baru = KFIN01_DEFAULT_PAIRS["finance"]
    rec = await db.permission_settings.find_one({"id": "default"})
    m, ap = rec["matrix"]["finance"], rec["defaults_applied"]["finance"]
    for res, acts in baru.items():   # bentuk sebelum K-FIN-01: pasangan Manajer belum ada di matriks maupun buku catatan
        for tempat in (m, ap):
            sisa = [a for a in (tempat.get(res) or []) if a not in acts]
            if sisa:
                tempat[res] = sisa
            else:
                tempat.pop(res, None)
    assert "approve" not in (m.get("payroll") or []) and "accounting" in m and "create" not in m["accounting"]
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.finance": m,
                                                                         "defaults_applied.finance": ap}})
    # Aturan Persetujuan TERSIMPAN (migrasi KP-T4 sudah dijalankan di VPS) tanpa Finance + penanda migrasi belum ada.
    await db.approval_policies.insert_many([
        {"id": "apol_kfin_1", "doc_kind": "vendor_bill", "entity_id": "all", "level": 1, "label": "Persetujuan",
         "min_amount": 0, "max_amount": None, "roles": ["admin", "manager"], "any_holder": False, "sort": 1,
         "active": True, "source": "migrasi"},
        {"id": "apol_kfin_2", "doc_kind": "amendment", "entity_id": "all", "level": 1, "label": "Persetujuan",
         "min_amount": 50_000_000, "max_amount": None, "roles": ["admin"], "any_holder": False, "sort": 2,
         "active": True, "source": "migrasi"}])
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$unset": {"kfin01_aturan_persetujuan": ""}})

    await bootstrap.run_bootstrap()
    f = _himpunan((await _peran(klien, kepala_admin, "finance"))["permissions"])
    assert _selisih(_himpunan(DEFAULT_PERMISSIONS["manager"]), f) == {}
    rec = await db.permission_settings.find_one({"id": "default"})
    ap = _himpunan(rec["defaults_applied"]["finance"])
    assert all(set(acts) <= ap.get(res, set()) for res, acts in baru.items())
    assert (await db.approval_policies.find_one({"id": "apol_kfin_1"}))["roles"] == ["admin", "manager", "finance"]
    assert (await db.approval_policies.find_one({"id": "apol_kfin_2"}))["roles"] == ["admin"]
    jejak = await db.audit_logs.find_one({"action": "approval_policies_finance_added"}, {"_id": 0})
    assert jejak and "apol_kfin_1" in str(jejak), jejak
    # Penanda: jalan kedua tidak menyentuh baris yang sesudahnya diubah Admin.
    await db.approval_policies.update_one({"id": "apol_kfin_1"}, {"$set": {"roles": ["admin", "manager"]}})
    await bootstrap.run_bootstrap()
    assert (await db.approval_policies.find_one({"id": "apol_kfin_1"}))["roles"] == ["admin", "manager"]
    await db.approval_policies.delete_many({"id": {"$in": ["apol_kfin_1", "apol_kfin_2"]}})

    # Admin mencabut "Sahkan gaji" dari Finance → start → bertahan; kembalikan bawaan → kembali.
    perms = {k: sorted(v) for k, v in f.items()}
    perms["payroll"] = [a for a in perms["payroll"] if a != "approve"]
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await bootstrap.run_bootstrap()
    assert "approve" not in (await _peran(klien, kepala_admin, "finance"))["permissions"]["payroll"]
    r = await klien.post("/api/access/roles/finance/reset", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert "approve" in (await _peran(klien, kepala_admin, "finance"))["permissions"]["payroll"]


# ── U4 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KFIN01_U4_finance_bertindak_seperti_manajer_dua_orang_tetap(klien, db, akun, sesi, kepala_admin):
    from services.dual_control import pesan_tolak
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji("KFN1")
    invalidate_status_cache()
    fa = await akun("finance", entitas=(eid,))
    fin = await sesi(fa, entitas=eid)
    fin2 = await sesi(await akun("finance", entitas=(eid,)), entitas=eid)

    # Meja Saya = Meja Manajer (kategori kerja "pengawas").
    r = await klien.get("/api/desks/me", headers=fin)
    assert r.status_code == 200 and r.json()["role"] == "manager", r.text

    # Masukan gaji: Finance mengajukan dan mengesahkan (dulu 403 — K-SDM-01).
    r = await klien.post("/api/hr/employees", headers=fin, json={
        "name": "sari wulandari", "entity_id": eid, "join_date": "2026-10-01", "ptkp_status": "TK0",
        "bank_name": "BCA", "bank_acc_no": "9876543210", "bank_acc_name": "Sari Wulandari", "base_salary": 6_000_000})
    assert r.status_code == 200, r.text
    emp = r.json()
    r = await klien.post("/api/hr/payroll/inputs", headers=fin, json={
        "employee_id": emp["id"], "component_code": "RAPEL", "pay_period": OKT, "amount": 2_000_000,
        "label": "Rapel gaji", "reason": "Uji K-FIN-01"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/inputs/{r.json()['id']}/approve", headers=fin, json={})
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text

    # Kontrol dua orang (per PENGGUNA) menyala untuk pengesahan gaji di PT ini.
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "kontrol.proses_gaji.min_orang", "value": "2", "scope_type": "entity", "scope_id": eid,
        "reason": "uji K-FIN-01 dua orang"}]})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/hr/payroll/runs", headers=fin, json={"entity_id": eid, "period": OKT, "run_type": "susulan"})
    assert r.status_code == 200, r.text
    run = r.json()
    assert (await klien.post(f"/api/hr/payroll/runs/{run['id']}/submit", headers=fin, json={})).status_code == 200
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/approve", headers=fin, json={})
    assert r.status_code == 403 and r.json()["detail"] == pesan_tolak("proses_gaji"), r.text   # pengaju ≠ pengesah
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/approve", headers=fin2, json={})
    assert r.status_code == 200, r.text   # Finance lain mengesahkan (dulu hanya Manajer)
    # Dengan dua orang menyala, pengaju juga tidak memposting sendiri (perilaku KF-T6, butir K-33 laporan audit).
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=fin, json={})
    assert r.status_code == 403 and r.json()["detail"] == pesan_tolak("proses_gaji"), r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=fin2, json={})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", headers=fin, json={"reason": "uji K-FIN-01 anulir"})
    assert r.status_code == 200, r.text   # menganulir (dulu 403 — K-SDM-01)
    assert (await db.hr_payroll_runs.find_one({"id": run["id"]}, {"_id": 0}))["status"] == "void"

    # Jurnal manual (dulu Finance hanya melihat Buku Besar, K-09).
    from services.book_date import tanggal_buku
    r = await klien.post("/api/gl/journal", headers=fin, json={"date": tanggal_buku(), "description": "uji K-FIN-01",
                                                               "lines": [{"account_code": "6-2000", "debit": 1000, "credit": 0},
                                                                         {"account_code": "1-1100", "debit": 0, "credit": 1000}]})
    assert r.status_code == 200, r.text
    je = await db.journal_entries.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert je["entity_id"] == eid and je["created_by"] == fa["name"]
