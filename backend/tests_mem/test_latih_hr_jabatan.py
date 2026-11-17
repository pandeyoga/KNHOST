"""Latihan Keuangan 17 Nov — backfill karyawan dari akun: Finance tidak lagi tercatat sebagai "Manajer"."""
import pytest

import bootstrap

pytestmark = pytest.mark.anyio


async def test_backfill_jabatan_per_peran(db):
    await db.business_entities.insert_one({"id": "ent_latih_hr", "status": "active", "name": "PT Uji HR"})
    for i, role in enumerate(["finance", "sales_admin", "qc", "manager"]):
        await db.users.insert_one({"id": f"u_latih_hr_{i}", "role": role, "status": "active", "name": f"U{i}",
                                   "email": f"u{i}@hr.test", "home_entity_id": "ent_latih_hr"})
    await bootstrap.seed_hr_foundation()
    emp = {e["user_id"]: e async for e in db.hr_employees.find({"user_id": {"$regex": "^u_latih_hr_"}}, {"_id": 0})}
    assert emp["u_latih_hr_0"]["position_id"] == "orgu_ent_latih_hr_keuangan_akunting"
    assert emp["u_latih_hr_1"]["position_id"] == "orgu_ent_latih_hr_keuangan_staf_admin"
    assert emp["u_latih_hr_2"]["position_id"] == ""            # tanpa pemetaan → tanpa jabatan, bukan "Manajer"
    assert emp["u_latih_hr_3"]["position_id"] == "orgu_ent_latih_hr_manajemen_manajer"
