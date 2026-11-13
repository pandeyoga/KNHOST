"""PK-02 U3 (bagian a) — modul ini mengotori database; modul isolasi_b harus mulai bersih."""


async def test_U3a_kotori_database(db):
    await db.uji_jejak.insert_one({"id": "jejak"})
    await db.users.delete_one({"email": "sales@kainnusantara.id"})
    assert await db.uji_jejak.count_documents({}) == 1
    assert await db.users.count_documents({}) == 3
