"""PK-02 U3 (bagian b) — tiap modul mulai dari seed awal, apa pun yang dilakukan modul lain."""
from pembantu import jumlah


async def test_U3b_mulai_bersih(aplikasi):
    assert await jumlah("uji_jejak", {}) == 0
    assert await jumlah("users", {}) == 4
