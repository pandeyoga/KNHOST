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


async def test_backfill_kode_dari_deret_resmi(db):
    """K-SDM-01 — kode karyawan hasil backfill memakai deret resmi, sehingga "Tambah Karyawan" sesudahnya tidak bentrok.
    Dulu backfill memberi "jumlah karyawan + 1" di luar deret → kode berikutnya dari deret sudah terpakai (500)."""
    from services.hr_service import next_employee_code
    await db.business_entities.insert_one({"id": "ent_latih_kd", "status": "active", "name": "PT Uji Kode"})
    # Karyawan lama berkode di depan hitungan (ada kode yang pernah dihapus): cara lama "jumlah + 1" jatuh tepat di
    # kode ini → bentrok indeks unik.
    n = await db.hr_employees.count_documents({})
    kode_lama = f"EMP-{n + 2:05d}"
    assert not await db.hr_employees.find_one({"code": kode_lama})
    await db.hr_employees.insert_one({"id": "emp_lama_kd", "code": kode_lama, "name": "Lama",
                                      "user_id": "", "entity_id": "ent_latih_kd", "status": "active"})
    for i in range(3):
        await db.users.insert_one({"id": f"u_latih_kd_{i}", "role": "finance", "status": "active", "name": f"K{i}",
                                   "email": f"k{i}@kd.test", "home_entity_id": "ent_latih_kd"})
    await bootstrap.seed_hr_foundation()
    kode = [e["code"] async for e in db.hr_employees.find({}, {"_id": 0, "code": 1})]
    assert len(kode) == len(set(kode))
    baru = await next_employee_code("ent_latih_kd")
    assert baru not in kode
