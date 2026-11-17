"""Pelatihan 18 Nov — uji variasi V7 (setoran gaji & pajak): akrual insentif PT·periode = Σ komisi SEMUA proses gaji
yang diposting (reguler + susulan), bukan komisi proses terakhir saja.

Dulu proses susulan kedua di bulan yang sama "mengoreksi" akrual ke komisi susulan itu (mis. 300.000 → 200.000) padahal
jurnal gajinya tetap mendebit Hutang Insentif 200.000 → Beban Insentif kurang 300.000 dan 2-1500 bersaldo debit."""
import datetime

import pytest

from pembantu import pt_uji as _pt_uji

OKT = "2026-10"
HARI_INI = datetime.datetime(2026, 11, 3, 3, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def _hari_ini_3_nov():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


async def _proses(db, eid, tag, komisi, run_type):
    rid = f"prun_v7_{tag}_{eid}".replace("-", "")
    slip = {"id": f"{rid}_s0", "number": f"SLIP-{tag}", "run_id": rid, "entity_id": eid, "period": OKT, "status": "approved",
            "employee_id": f"emp_{rid}", "employee_name": "Sales V7", "salary_earnings": 0.0, "commission": komisi,
            "gross": komisi, "tax_gross": komisi, "bpjs_emp_total": 0.0, "bpjs_er_total": 0.0, "pph21": 0.0, "net": komisi}
    tot = {"employees": 1, "salary_earnings": 0.0, "commission": komisi, "gross": komisi, "bpjs_emp": 0.0, "bpjs_er": 0.0,
           "pph21": 0.0, "net": komisi}
    run = {"id": rid, "number": f"PAY-{tag}", "entity_id": eid, "period": OKT, "status": "approved", "run_type": run_type,
           "commission_mode": "accrue_then_settle", "totals": tot, "gl_posted": False, "journal_id": "",
           "journal_number": "", "submitted_by": "Uji", "submitted_by_id": "usr_uji_pengaju",
           "created_at": "2026-11-01T01:00:00+00:00"}
    await db.hr_payroll_runs.insert_one(dict(run))
    await db.hr_payslips.insert_one(dict(slip))
    return run


async def _saldo(db, eid, kode):
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": eid, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


async def test_akrual_insentif_menjumlah_proses_susulan(klien, db, sesi):
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji("V7A")
    invalidate_status_cache()
    h = await sesi("admin@kainnusantara.id", entitas=eid)
    reg = await _proses(db, eid, "reg", 300_000.0, "regular")
    sus = await _proses(db, eid, "sus", 200_000.0, "susulan")
    for run in (reg, sus):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h)
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    # Beban insentif Oktober = 300.000 + 200.000; Hutang Insentif kembali nol (diakru = dilunasi slip).
    assert await _saldo(db, eid, "6-5000") == 500_000
    assert await _saldo(db, eid, "2-1500") == 0
    # Posting ulang (idempoten) tidak menambah koreksi.
    from services import posting_registry
    n0 = await db.journal_entries.count_documents({"entity_id": eid, "source_type": {"$regex": "^incentive_accrual"}})
    await posting_registry.post_payroll(await db.hr_payroll_runs.find_one({"id": sus["id"]}, {"_id": 0}), "uji")
    assert await db.journal_entries.count_documents(
        {"entity_id": eid, "source_type": {"$regex": "^incentive_accrual"}}) == n0
