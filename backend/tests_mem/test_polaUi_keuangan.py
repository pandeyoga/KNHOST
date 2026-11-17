"""Pola UI gelombang Keuangan (docs/blueprint/04_POLA_UI.md · masukan pemilik 16 Nov M32/M36) — dua tambahan BACA saja.

* M36 — kartu "Dokumen terbuka" di layar Antar-PT menyaring daftar beberapa status sekaligus: `GET /interco/transactions
  ?status=a,b` → `$in` (satu status tetap persis seperti dulu).
* M32 — "Piutang Terbesar" di Beranda Keuangan membuka kartu pelanggan: baris `ar.top` membawa `customer_id`.
"""
from services import ar_aging_service, finance_tower_service
from services.interco_service import COLL_ICT


def _ict(nomor: int, status: str) -> dict:
    return {"id": f"ict_ui_{nomor}", "number": f"KSC/ICT-UI{nomor:03d}", "entity_id": "ent_ksc", "role": "seller",
            "status": status, "pair_id": f"pair_ui_{nomor}", "grand_total": 1000.0 * nomor,
            "created_at": f"2026-11-{10 + nomor:02d}T00:00:00+00:00"}


async def test_M36_status_banyak_disaring_server(klien, db, kepala_admin):
    status = ["draft", "confirmed", "shipped", "received", "invoiced", "settled", "cancelled"]
    await db[COLL_ICT].insert_many([_ict(i, s) for i, s in enumerate(status, start=1)])
    ambil = lambda st: klien.get("/api/interco/transactions", headers=kepala_admin,  # noqa: E731
                                 params={"entity_id": "ent_ksc", "status": st})
    r = await ambil("confirmed,shipped,received,invoiced")
    assert r.status_code == 200, r.text
    assert sorted(x["status"] for x in r.json()) == ["confirmed", "invoiced", "received", "shipped"]
    assert [x["status"] for x in (await ambil("draft")).json()] == ["draft"]          # satu status: seperti dulu
    assert len((await ambil("")).json()) == len(status)                              # kosong: semua
    assert len((await ambil(",")).json()) == len(status)                             # koma saja: tidak menyaring


async def test_M32_piutang_terbesar_membawa_customer_id(aplikasi, monkeypatch):
    async def palsu(*_a, **_k):
        return {"totals": {"total": 500.0}, "bucket_labels": [],
                "customers": [{"customer_id": "cust_ui_1", "customer_name": "Toko Kain", "outstanding": 500.0,
                               "overdue": 0.0, "oldest_days": 3}]}
    monkeypatch.setattr(ar_aging_service, "aging_report", palsu)
    hasil = await finance_tower_service.finance_tower({"entity_id": "ent_ksc"}, entity_id="ent_ksc")
    assert hasil["ar"]["top"] == [{"customer_id": "cust_ui_1", "customer_name": "Toko Kain", "outstanding": 500.0,
                                   "overdue": 0.0, "oldest_days": 3}]
