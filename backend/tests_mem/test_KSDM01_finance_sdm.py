"""K-SDM-01 — Finance mengerjakan SDM & penggajian (keputusan pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga").

Izin bawaan baru `permissions_config.KSDM01_DEFAULT_PAIRS`: Finance memegang `hr.view/create/update/view_pii/
manage_attendance/manage_payroll` dan `payroll.create/post` (di samping `payroll.pay`, PY-T4). Pemisahan tugas: Finance
menyiapkan & memposting, Manajer mengesahkan & membatalkan (`payroll.approve/void`); `hr.delete`, `hr.manage_org`,
`hr.manage_settings` tetap Admin/Manajer.

U1  bawaan peran Finance di basis data baru = pasangan di atas, tanpa approve/void/delete/manage_org/manage_settings.
U2  alur HTTP di PT uji: Finance menambah karyawan (gaji pokok, PTKP, NPWP, rekening) → memasukkan masukan gaji
    (menunggu) → tidak bisa mengesahkan masukan (403 berkalimat) → Manajer mengesahkan → Finance membuat proses susulan
    & mengajukan → tidak bisa mengesahkan (403) → Manajer mengesahkan → Finance memposting (jurnal seimbang Beban Gaji
    6-1000 = Hutang Gaji 2-1600 + Hutang PPh 21 2-1800) → Finance tidak bisa menganulir (403).
U3  instalasi lama: matriks & `defaults_applied` tanpa pasangan K-SDM-01 → start → pasangan tiba; Admin mencabut SDM
    Finance → start → pencabutan bertahan; kembalikan bawaan → pasangan kembali.
"Hari ini" dibekukan 3 Nov 2026 (`services.book_date._sekarang`), masa gaji Oktober 2026.
"""
import datetime

import pytest

import bootstrap
from pembantu import pt_uji as _pt_uji

pytestmark = pytest.mark.anyio

OKT = "2026-10"
HARI_INI = datetime.datetime(2026, 11, 3, 3, 0, tzinfo=datetime.timezone.utc)   # 3 Nov 2026 10.00 WIB
SDM = {"view", "create", "update", "view_pii", "manage_attendance", "manage_payroll"}
GAJI = {"create", "post", "pay"}
MODUL = "Minta Admin menambahkan akses 'SDM & Penggajian'"


@pytest.fixture(scope="module", autouse=True)
def _hari_ini_3_nov():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


async def _finance(klien, h) -> dict:
    r = await klien.get("/api/access/roles/finance", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_KSDM01_U1_bawaan_finance(klien, kepala_admin):
    from permissions_config import DEFAULT_PERMISSIONS, KSDM01_DEFAULT_PAIRS
    assert set(KSDM01_DEFAULT_PAIRS["finance"]["hr"]) == SDM
    assert set(DEFAULT_PERMISSIONS["finance"]["payroll"]) == GAJI
    f = (await _finance(klien, kepala_admin))["permissions"]
    assert set(f["hr"]) == SDM, f.get("hr")
    assert set(f["payroll"]) == GAJI, f.get("payroll")
    assert not set(f["payroll"]) & {"approve", "void"}
    assert not set(f["hr"]) & {"delete", "manage_org", "manage_settings"}
    m = (await klien.get("/api/access/roles/manager", headers=kepala_admin)).json()["permissions"]
    assert {"approve", "void"} <= set(m["payroll"])   # Manajer tetap pemutus


async def test_KSDM01_U2_finance_siapkan_dan_posting_manajer_sahkan(klien, db, akun, sesi):
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji("SDM1")
    invalidate_status_cache()
    fin = await sesi(await akun("finance", entitas=(eid,)), entitas=eid)
    mgr = await sesi(await akun("manager", entitas=(eid,)), entitas=eid)

    r = await klien.post("/api/hr/employees", headers=fin, json={
        "name": "andi pratama", "entity_id": eid, "join_date": "2026-10-01", "ptkp_status": "K1",
        "npwp": "09.254.294.3-407.000", "bank_name": "BCA", "bank_acc_no": "1234567890",
        "bank_acc_name": "Andi Pratama", "base_salary": 7_500_000})
    assert r.status_code == 200, r.text
    emp = r.json()
    assert (emp["name"], emp["ptkp_status"], emp["base_salary"]) == ("Andi Pratama", "K1", 7_500_000)
    r = await klien.get(f"/api/hr/employees/{emp['id']}/compensation", headers=fin)   # hr.view + hr.view_pii
    assert r.status_code == 200, r.text

    r = await klien.post("/api/hr/payroll/inputs", headers=fin, json={
        "employee_id": emp["id"], "component_code": "RAPEL", "pay_period": OKT, "amount": 7_000_000,
        "label": "Rapel gaji", "reason": "Uji K-SDM-01"})
    assert r.status_code == 200, r.text
    inp = r.json()
    assert inp["status"] == "pending"
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/approve", headers=fin, json={})
    assert r.status_code == 403 and MODUL in r.json()["detail"], r.text
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/approve", headers=mgr, json={})
    assert r.status_code == 200, r.text

    r = await klien.post("/api/hr/payroll/runs", headers=fin, json={"entity_id": eid, "period": OKT, "run_type": "susulan"})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "draft" and run["totals"]["employees"] == 1
    assert (await klien.post(f"/api/hr/payroll/runs/{run['id']}/submit", headers=fin, json={})).status_code == 200
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/approve", headers=fin, json={})
    assert r.status_code == 403 and MODUL in r.json()["detail"], r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/approve", headers=mgr, json={})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=fin, json={})
    assert r.status_code == 200, r.text
    run = await db.hr_payroll_runs.find_one({"id": run["id"]}, {"_id": 0})
    assert run["status"] == "posted" and run["journal_id"], run
    je = await db.journal_entries.find_one({"id": run["journal_id"]}, {"_id": 0})
    deb = {l["account_code"]: l["debit"] for l in je["lines"] if l.get("debit")}
    kre = {l["account_code"]: l["credit"] for l in je["lines"] if l.get("credit")}
    t = run["totals"]
    assert round(sum(deb.values()), 2) == round(sum(kre.values()), 2) == round(t["gross"], 2)
    assert deb == {"6-1000": t["gross"]}, deb
    assert kre.get("2-1600") == t["net"] and kre.get("2-1800", 0) == t["pph21"] > 0, kre
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", headers=fin, json={"reason": "uji pemisahan tugas"})
    assert r.status_code == 403 and MODUL in r.json()["detail"], r.text


async def test_KSDM01_U3_instalasi_lama_menerima_pasangan_dan_pencabutan_bertahan(klien, db, kepala_admin):
    rec = await db.permission_settings.find_one({"id": "default"})
    m, ap = rec["matrix"]["finance"], rec["defaults_applied"]["finance"]
    m.pop("hr", None), ap.pop("hr", None)
    m["payroll"], ap["payroll"] = ["pay"], ["pay"]   # bentuk sebelum K-SDM-01 (PY-T4)
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.finance": m,
                                                                         "defaults_applied.finance": ap}})
    await bootstrap.run_bootstrap()
    f = (await _finance(klien, kepala_admin))["permissions"]
    assert set(f["hr"]) == SDM and set(f["payroll"]) == GAJI, (f.get("hr"), f.get("payroll"))
    rec = await db.permission_settings.find_one({"id": "default"})
    assert set(rec["defaults_applied"]["finance"]["hr"]) == SDM

    perms = {k: list(v) for k, v in f.items() if k != "hr"}   # Admin mencabut SDM Finance
    r = await klien.patch("/api/access/roles/finance", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await bootstrap.run_bootstrap()
    assert "hr" not in (await _finance(klien, kepala_admin))["permissions"]
    r = await klien.post("/api/access/roles/finance/reset", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert set((await _finance(klien, kepala_admin))["permissions"]["hr"]) == SDM


async def test_KSDM01_U4_kode_karyawan_melewati_kode_terpakai(klien, db, akun, sesi):
    """Audit pelatihan 18 Nov — pengisi karyawan dari akun (proses awal) memberi kode "jumlah + 1" di luar deret atomik;
    "Tambah Karyawan" berikutnya dulu mendapat kode yang sudah terpakai (MongoDB asli: 500 indeks unik `uq_code`,
    layar "Tidak bisa menghubungi server"). Kini kode terpakai dilewati."""
    fin = await sesi(await akun("finance"), entitas="ent_ksc")
    r = await klien.post("/api/hr/employees", headers=fin, json={"name": "Kode Satu", "entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    n = int(r.json()["code"].split("-")[1])
    luar = [f"EMP-{n + i:05d}" for i in (1, 2, 3)]   # tiruan pengisi proses awal (tanpa deret)
    await db.hr_employees.insert_many([{"id": f"emp_luar_{c}", "code": c, "name": f"Akun {c}", "entity_id": "ent_ksc",
                                        "status": "active"} for c in luar])
    r = await klien.post("/api/hr/employees", headers=fin, json={"name": "Kode Dua", "entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    assert r.json()["code"] == f"EMP-{n + 4:05d}", r.json()["code"]
    assert await db.hr_employees.count_documents({"code": r.json()["code"]}) == 1
