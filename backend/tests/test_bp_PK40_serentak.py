"""PK-40 U2 & U6 — di MongoDB ASLI (lingkungan A): keunikan faktur pajak dijamin indeks, bukan "cari dulu, lalu sisip".

U2: dua `POST /api/sales-orders/{SO}/tax-invoice` BERSAMAAN → tepat satu 200 dan satu 409; satu faktur aktif
    (`active_key = so:{SO}`). Diulang beberapa putaran (pesanan baru tiap putaran) supaya kedua permintaan sungguh
    melewati jalan cepat bersamaan sedikitnya sekali.
U6: dua `POST /api/input-tax-invoices` BERSAMAAN untuk dua tagihan pemasok ber-PPN dengan NSFP sama → tepat satu 200 dan
    satu 409 (pesan "Nomor seri … sudah dipakai faktur …").
U0: kelima indeks unik wajib PK-40 terpasang; sisipan kembar langsung ke database ditolak `DuplicateKeyError`.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`, kode PK-40, dinyalakan ulang supaya indeks
terbentuk). Pesanan dan tagihan uji DISISIP langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) sebagai FIXTURE,
terbit/catat lewat API, lalu dihapus. Tidak untuk database berisi data nyata.
"""
import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests
from pymongo.errors import DuplicateKeyError

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
ENT = "ent_ksc"
PUTARAN = 5


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _bersamaan(fns):
    with ThreadPoolExecutor(len(fns)) as ex:
        return [f.result() for f in [ex.submit(fn) for fn in fns]]


def _pesanan(oid):
    # DPP 1.000.000, PPN 11% = 110.000 (hitungan tangan).
    return {"id": oid, "number": oid.upper(), "entity_id": ENT, "customer_id": f"cus_pk40_{TAG}",
            "customer_name": "Toko Uji PK-40", "status": "confirmed", "subtotal": 1_000_000, "dpp": 1_000_000,
            "net_subtotal": 1_000_000, "ppn_amount": 110_000, "ppn_rate": 11, "grand_total": 1_110_000, "is_pkp": True,
            "items": [{"product_name": "Kain Uji", "quantity": 10, "unit": "m", "price": 100_000, "line_total": 1_000_000}],
            "payments": [], "created_at": NOW}


def _tagihan(bid):
    return {"id": bid, "bill_number": bid.upper(), "entity_id": ENT, "status": "posted", "supplier_id": "sup_pk40",
            "supplier_name": "Pemasok Uji PK-40", "dpp": 500_000, "ppn_amount": 55_000, "grand_total": 555_000,
            "bill_date": NOW[:10], "created_at": NOW}


@pytest.fixture(scope="module")
def h():
    return _login()


@pytest.fixture(scope="module", autouse=True)
def bersihkan():
    yield
    DB.tax_invoices.delete_many({"order_id": {"$regex": f"^so_pk40_{TAG}"}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_pk40_{TAG}"}})
    DB.tax_invoices_in.delete_many({"vendor_bill_id": {"$regex": f"^vb_pk40_{TAG}"}})
    DB.vendor_bills.delete_many({"id": {"$regex": f"^vb_pk40_{TAG}"}})
    DB.tax_invoices.delete_many({"id": {"$regex": f"^fkt_pk40_{TAG}"}})


def test_U0_indeks_unik_terpasang_dan_menolak_kembar():
    for coll, names in (("tax_invoices", ("uq_fkt_active", "uq_fkt_nsfp")),
                        ("tax_invoices_in", ("uq_fpm_active", "uq_fpm_nsfp")), ("tax_period_locks", ("uq_tax_period",))):
        info = DB[coll].index_information()
        for n in names:
            assert info.get(n, {}).get("unique") is True, (coll, n)
    DB.tax_invoices.insert_one({"id": f"fkt_pk40_{TAG}_a", "number": f"PK40-{TAG}-A", "status": "normal",
                                "active_key": f"so:so_pk40_{TAG}_x"})
    with pytest.raises(DuplicateKeyError):
        DB.tax_invoices.insert_one({"id": f"fkt_pk40_{TAG}_b", "number": f"PK40-{TAG}-B", "status": "normal",
                                    "active_key": f"so:so_pk40_{TAG}_x"})


def test_U2_terbit_bersamaan_satu_faktur_aktif(h):
    for i in range(PUTARAN):
        oid = f"so_pk40_{TAG}_{i}"
        DB.sales_orders.insert_one(_pesanan(oid))
        url = f"{BASE}/sales-orders/{oid}/tax-invoice"
        rs = _bersamaan([lambda: requests.post(url, headers=h, json={}, timeout=60)] * 2)
        kode = sorted(r.status_code for r in rs)
        assert kode == [200, 409], [(r.status_code, r.text[:200]) for r in rs]
        kalah = next(r for r in rs if r.status_code == 409).json()["detail"]
        assert kalah.startswith("Faktur Pajak sudah diterbitkan untuk order ini"), kalah
        assert DB.tax_invoices.count_documents({"order_id": oid, "status": {"$ne": "batal"}}) == 1
        assert DB.tax_invoices.count_documents({"active_key": f"so:{oid}"}) == 1


def test_U6_faktur_masukan_bersamaan_nsfp_sama(h):
    nsfp = f"010.000-26.{int(TAG, 16) % 100_000_000:08d}"
    b1, b2 = f"vb_pk40_{TAG}_1", f"vb_pk40_{TAG}_2"
    DB.vendor_bills.insert_many([_tagihan(b1), _tagihan(b2)])

    def catat(bid):
        return lambda: requests.post(f"{BASE}/input-tax-invoices", headers=h, timeout=60,
                                     json={"vendor_bill_id": bid, "nsfp": nsfp})
    rs = _bersamaan([catat(b1), catat(b2)])
    assert sorted(r.status_code for r in rs) == [200, 409], [(r.status_code, r.text[:200]) for r in rs]
    kalah = next(r for r in rs if r.status_code == 409).json()["detail"]
    assert kalah.startswith(f"Nomor seri {nsfp} sudah dipakai faktur ") and kalah.endswith("Periksa nomor serinya."), kalah
    digits = "".join(c for c in nsfp if c.isdigit())
    assert DB.tax_invoices_in.count_documents({"nsfp_key": digits}) == 1
    # Tagihan yang kalah tidak tertinggal terkunci (klaim dilepas) — bisa dicatat dengan NSFP lain.
    kalah_bid = b1 if rs[0].status_code == 409 else b2
    r = requests.post(f"{BASE}/input-tax-invoices", headers=h, timeout=60,
                      json={"vendor_bill_id": kalah_bid, "nsfp": f"010.000-26.{(int(TAG, 16) + 1) % 100_000_000:08d}"})
    assert r.status_code == 200, r.text
