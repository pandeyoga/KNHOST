"""PK-42 — daftar kwitansi & kas berhalaman, hitungan tab kas, dan rute tombol buat (docs/blueprint/unit/PK-42.md).

Fixture (disisipkan langsung ke database tiruan, bukan alur): `ar_receipts` dan `cash_transactions` PT `ent_ksc` dengan
`created_at`/`txn_date` berurutan menit demi menit, sehingga urutan "terbaru dulu" bisa dihitung tangan. Koleksi itu
dikosongkan dulu di tiap uji (database modul ini baru + seed awal; seed tidak membuat kwitansi/kas).
"""
from __future__ import annotations

import datetime
import itertools

import pytest

pytestmark = pytest.mark.anyio

AWAL = datetime.datetime(2026, 10, 1, 1, 0, tzinfo=datetime.timezone.utc)


def _waktu(i: int) -> str:
    return (AWAL + datetime.timedelta(minutes=i)).isoformat()


def _kwitansi(i: int, ent: str = "ent_ksc", **lain) -> dict:
    return {"id": f"rcp_pk42_{i:05d}", "number": f"KSC/AR-{i:05d}", "entity_id": ent, "customer_id": "cus_uji",
            "customer_name": lain.pop("customer_name", "Toko Uji"), "amount": 100_000, "method": "transfer",
            "status": "posted", "allocations": [], "receipt_date": _waktu(i), "created_at": _waktu(i), **lain}


def _kas(i: int, jenis: str, ent: str = "ent_ksc", **lain) -> dict:
    return {"id": f"cash_pk42_{i:05d}", "number": f"KSC/CASH-{i:05d}", "entity_id": ent, "cash_type": jenis,
            "direction": "out", "amount": 10_000, "category": lain.pop("category", "operasional"),
            "description": lain.pop("description", f"Belanja {i}"), "status": "posted",
            "txn_date": _waktu(i), "created_at": _waktu(i), **lain}


# ── U9 — riwayat kwitansi berhalaman ───────────────────────────────────────────────────────────────────────────────
async def test_PK42_U9_kwitansi_halaman_kedua(klien, db, kepala_admin):
    # 30 kwitansi ent_ksc, i = 0..29 (i lebih besar = lebih baru). Halaman 2 ukuran 25 → baris ke-26..30 urut terbaru:
    # i = 29-25 = 4, 3, 2, 1, 0 → 5 baris; 2 × 25 = 50 ≥ 30 → has_more salah.
    await db.ar_receipts.delete_many({})
    await db.ar_receipts.insert_many([_kwitansi(i) for i in range(30)])
    r = await klien.get("/api/ar-receipts", headers=kepala_admin, params={"page": 2, "page_size": 25})
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j, dict), f"jawaban bukan amplop halaman: {type(j).__name__}"
    assert (j["total"], j["page"], j["page_size"], j["has_more"]) == (30, 2, 25, False)
    assert [x["number"] for x in j["items"]] == [f"KSC/AR-{i:05d}" for i in (4, 3, 2, 1, 0)]
    r1 = (await klien.get("/api/ar-receipts", headers=kepala_admin, params={"page": 1, "page_size": 25})).json()
    assert r1["has_more"] is True and r1["items"][0]["number"] == "KSC/AR-00029"
    stamps = [x["created_at"] for x in r1["items"] + j["items"]]
    assert stamps == sorted(stamps, reverse=True)


async def test_PK42_U9b_kwitansi_cari_nomor_dan_pelanggan(klien, db, kepala_admin):
    # `q` mencari nomor dan nama pelanggan: 3 kwitansi "Toko Melati" + 1 bernomor ...-00777 di antara 10.
    await db.ar_receipts.delete_many({})
    rows = [_kwitansi(i) for i in range(10)]
    rows += [_kwitansi(100 + i, customer_name="Toko Melati") for i in range(3)] + [_kwitansi(777)]
    await db.ar_receipts.insert_many(rows)
    j = (await klien.get("/api/ar-receipts", headers=kepala_admin,
                         params={"page": 1, "page_size": 25, "q": "melati"})).json()
    assert j["total"] == 3 and {x["customer_name"] for x in j["items"]} == {"Toko Melati"}
    j = (await klien.get("/api/ar-receipts", headers=kepala_admin,
                         params={"page": 1, "page_size": 25, "q": "AR-00777"})).json()
    assert [x["number"] for x in j["items"]] == ["KSC/AR-00777"]


async def test_PK42_U9c_kwitansi_tanpa_halaman_tetap_larik(klien, db, kepala_admin):
    # Tanpa page/page_size bentuk jawaban tidak berubah: larik telanjang, terbaru dulu, hanya PT di kepala.
    await db.ar_receipts.delete_many({})
    await db.ar_receipts.insert_many([_kwitansi(i) for i in range(3)] + [_kwitansi(50, ent="ent_kanda")])
    r = await klien.get("/api/ar-receipts", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert [x["number"] for x in r.json()] == ["KSC/AR-00002", "KSC/AR-00001", "KSC/AR-00000"]


# ── U10 — tanpa halaman: kwitansi terbaru tidak terbuang ───────────────────────────────────────────────────────────
@pytest.fixture
def to_list_seperti_motor(monkeypatch):
    """`mongomock_motor` mengabaikan panjang `to_list(n)` (selalu semua baris), sedangkan Motor asli memotong di n.
    Batas itulah sumber masalah U10, jadi selama uji ini kursor tiruan dibuat memotong seperti Motor."""
    import mongomock_motor

    async def _to_list(self, length=None, *_a, **_kw):
        cur = self._AsyncCursor__cursor
        return list(cur) if length is None else list(itertools.islice(cur, int(length)))
    monkeypatch.setattr(mongomock_motor.AsyncCursor, "to_list", _to_list)


async def test_PK42_U10_kwitansi_terbaru_tidak_terbuang(klien, db, kepala_admin, to_list_seperti_motor):
    # 2.001 kwitansi; yang paling baru (i = 5000) disisipkan TERAKHIR. Kode lama: to_list(2000) tanpa urutan → 2.000
    # yang pertama disisipkan, baru diurutkan → baris pertama i = 1999, i = 5000 terbuang. Harapan: baris pertama = 5000.
    await db.ar_receipts.delete_many({})
    await db.ar_receipts.insert_many([_kwitansi(i) for i in range(2000)])
    await db.ar_receipts.insert_one(_kwitansi(5000))
    r = await klien.get("/api/ar-receipts", headers=kepala_admin)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2000                       # batas lama tetap
    assert rows[0]["number"] == "KSC/AR-05000"
    assert rows[-1]["number"] == "KSC/AR-00001"    # yang terbuang = paling lama (i = 0)


# ── U11 — daftar kas berhalaman + hitungan tab ─────────────────────────────────────────────────────────────────────
async def test_PK42_U11_kas_halaman_dan_hitungan_tab(klien, db, kepala_admin):
    # 501 transaksi: i = 0..299 kas kecil, i = 300..500 kas besar (201), + 4 yang dianulir (tidak dihitung).
    # Halaman 11 ukuran 50: 10 × 50 = 500 → sisa 1 baris = yang paling lama (i = 0, kas kecil).
    await db.cash_transactions.delete_many({})
    rows = [_kas(i, "kas_kecil") for i in range(300)] + [_kas(i, "kas_besar") for i in range(300, 501)]
    rows += [_kas(900 + i, "kas_kecil", status="void") for i in range(4)]
    await db.cash_transactions.insert_many(rows)
    r = await klien.get("/api/cash-transactions", headers=kepala_admin, params={"page": 11, "page_size": 50})
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j, dict), f"jawaban bukan amplop halaman: {type(j).__name__} (panjang {len(j)})"
    assert (j["total"], len(j["items"]), j["has_more"]) == (501, 1, False)
    assert j["items"][0]["number"] == "KSC/CASH-00000"
    s = await klien.get("/api/cash-transactions/summary", headers=kepala_admin)
    assert s.status_code == 200, s.text
    assert s.json().get("counts") == {"all": 501, "kas_kecil": 300, "kas_besar": 201}
    # Saringan jenis + halaman: kas besar halaman 5 ukuran 50 → 201 − 200 = 1 baris (i = 300, kas besar paling lama).
    j = (await klien.get("/api/cash-transactions", headers=kepala_admin,
                         params={"page": 5, "page_size": 50, "cash_type": "kas_besar"})).json()
    assert (j["total"], [x["number"] for x in j["items"]]) == (201, ["KSC/CASH-00300"])


async def test_PK42_U11b_kas_cari_dan_tanpa_halaman(klien, db, kepala_admin):
    await db.cash_transactions.delete_many({})
    rows = [_kas(i, "kas_kecil") for i in range(5)]
    rows += [_kas(10, "kas_kecil", description="Bayar listrik kantor"), _kas(11, "kas_besar", category="gaji")]
    await db.cash_transactions.insert_many(rows)
    cari = lambda q: klien.get("/api/cash-transactions", headers=kepala_admin,  # noqa: E731
                               params={"page": 1, "page_size": 50, "q": q})
    assert [x["number"] for x in (await cari("listrik")).json()["items"]] == ["KSC/CASH-00010"]
    assert [x["number"] for x in (await cari("gaji")).json()["items"]] == ["KSC/CASH-00011"]
    assert [x["number"] for x in (await cari("CASH-00003")).json()["items"]] == ["KSC/CASH-00003"]
    # Tanpa halaman: larik seperti dulu (terbaru dulu).
    r = await klien.get("/api/cash-transactions", headers=kepala_admin)
    assert isinstance(r.json(), list) and r.json()[0]["number"] == "KSC/CASH-00011" and len(r.json()) == 7


# ── Langkah 2 — rute tiap tombol buat ditolak pagar "Semua PT" (asumsi spesifikasi dipastikan) ───────────────────────
#: Tombol (testid) → rute akar yang dipanggil pop-up/form-nya (dibaca dari kode layar di HEAD).
RUTE_TOMBOL = {
    "gl-new-journal": "/api/gl/journal",
    "create-cash-button": "/api/cash-transactions",
    "create-vendor-bill-button": "/api/vendor-bills",
    "cb-new": "/api/contra-bons",
    "create-landed-cost-button": "/api/landed-costs",
    "it-create-button": "/api/input-tax-invoices",
    "add-asset-btn": "/api/fixed-assets",
    "budget-add-toggle": "/api/finance/budgets",
    "bank-add-toggle": "/api/bank-accounts",
    "ca-create-btn": "/api/cash-advances",
    "stl-create-btn": "/api/cash-advance-settlements",
}
#: Dicoret dari tabel UX-05: dokumen antar-PT memang tingkat grup (`entity_write_guard.GROUP_LEVEL_EXACT`) —
#: PT penjual/pembeli dan pembayar/penerima dipilih di form, bukan dari kepala aplikasi.
RUTE_DIIZINKAN = {
    "interco-create-btn": "/api/interco/transactions",
    "interco-open-settle-btn": "/api/interco/settlements",
}


async def test_PK42_rute_tombol_buat_semua_pt(klien, sesi):
    from entity_write_guard import MESSAGE
    h = await sesi("admin@kainnusantara.id", entitas="all")
    for tombol, rute in RUTE_TOMBOL.items():
        r = await klien.post(rute, headers=h, json={})
        assert r.status_code == 409 and r.json().get("detail") == MESSAGE, (tombol, rute, r.status_code, r.text[:200])
    for tombol, rute in RUTE_DIIZINKAN.items():
        r = await klien.post(rute, headers=h, json={})
        assert not (r.status_code == 409 and r.json().get("detail") == MESSAGE), (tombol, rute, r.text[:200])


# ── Unduh ▾ di pager mengikuti kotak cari daftar (jalur cari = endpoint daftarnya) ─────────────────────────────────
async def test_PK42_unduh_ikut_cari_daftar(aplikasi):
    # Tombol baku "Unduh ▾" (KN_37 §6) di dua daftar baru mengirim teks cari; registry dataset wajib mengenal jalur yang
    # sama dengan `q` endpoint, kalau tidak Pusat Export menolak 422 "belum mendukung pencarian teks".
    from services.export_engine import _search_clause
    from services.export_registry import DATASET_BY_ID
    from services.ar_receipt_service import RECEIPT_SEARCH_FIELDS
    from routers.cash import CASH_SEARCH_FIELDS
    for ds, fields in (("ar_receipts", RECEIPT_SEARCH_FIELDS), ("cash_transactions", CASH_SEARCH_FIELDS)):
        clause, teks = await _search_clause(DATASET_BY_ID[ds], "melati")
        assert sorted(next(iter(c)) for c in clause["$or"]) == sorted(fields), ds
        assert teks == "Cari “melati”"
