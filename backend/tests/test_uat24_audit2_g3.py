"""UAT 24 Okt (audit UI tahap 2) — grup G3 (gudang/inspeksi): perubahan backend tingkat layanan.

* G3-36 — angka notifikasi stok pendingan berformat id-ID (`alert_ops_service._qty`): dulu "0.02", "50.39".
* G3-17 — SPK baru tanpa kode lini dari dokumen sumber menurunkan lini dari master produk barisnya
  (`inspection_service.line_code_from_products`); campuran lini → kosong (tidak menebak).
* G3-18 — petugas inspeksi berkemampuan eksplisit didahulukan (`eligible_officers`), keanggotaan tidak berubah.
* G3-31 — papan "Barang ditahan QC": judul kosong → produk yang ditahan; note = roll · gudang
  (`approval_backlog_service.inspection_hold_extras` / `_apply_hold_extras`), bukan "Bagian Inspect".
* G3-32 — KPI stok per satuan: saldo produk tak terdaftar / tanpa satuan berlabel jujur
  (`routers.dashboard._units_for_products`), bukan "tanpa satuan".

Uji memanggil fungsi layanan langsung (tanpa HTTP) memakai event loop bersama `tests/_shared_loop.py`.
Jalankan: cd /app/backend && DB_NAME=kn_test_trial python -m pytest tests/test_uat24_audit2_g3.py -p no:randomly -n 0 -q
"""
import os
import sys

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import alert_ops_service as ops  # noqa: E402
from services import approval_backlog_service as backlog  # noqa: E402
from services import inspection_service as ins  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def test_g3_36_angka_notifikasi_format_id():
    assert ops._qty(0.02) == "0,02"
    assert ops._qty(50.39) == "50,39"
    assert ops._qty(1) == "1"
    assert ops._qty(1250.5) == "1.250,5"
    assert ops._qty(1234567.891) == "1.234.567,89"
    assert ops._qty(None) == "0" and ops._qty("x") == "0"


def test_g3_17_lini_spk_diturunkan_dari_produk():
    woven = [p["id"] for p in DB.products.find({"line_code": "woven"}, {"_id": 0, "id": 1}).limit(2)]
    knit = DB.products.find_one({"line_code": "knit"}, {"_id": 0, "id": 1})
    if not woven or not knit:
        import pytest
        pytest.skip("data acuan tanpa produk berlini woven/knit")
    assert run(ins.line_code_from_products(woven)) == "woven"
    assert run(ins.line_code_from_products(woven + [None, ""])) == "woven"
    assert run(ins.line_code_from_products([woven[0], knit["id"]])) == ""        # campuran → tidak menebak
    assert run(ins.line_code_from_products(["prod_tidak_ada_g3"])) == ""
    assert run(ins.line_code_from_products([])) == ""


def test_g3_18_petugas_berkemampuan_didahulukan():
    ent = (DB.entities.find_one({"id": "ent_ksc"}, {"_id": 0, "id": 1}) or {}).get("id") or "ent_ksc"
    officers = run(ins.eligible_officers(ent))
    flags = [bool(u.get("dedicated")) for u in officers]
    assert flags == sorted(flags, reverse=True), [(u.get("name"), u.get("role"), u.get("dedicated")) for u in officers]
    dedicated = run(ins.dedicated_officer_roles())
    assert "finance" not in dedicated


def test_g3_31_papan_barang_ditahan_menyebut_barang():
    roll = DB.inventory_rolls.find_one({"warehouse_id": {"$nin": [None, ""]}, "roll_no": {"$nin": [None, ""]}},
                                       {"_id": 0, "id": 1, "roll_no": 1, "warehouse_id": 1})
    wh = DB.warehouses.find_one({"id": roll["warehouse_id"]}, {"_id": 0, "name": 1}) or {}
    docs = [{"id": "ins_g3_a", "lines": [
                {"hold": True, "roll_id": roll["id"], "roll_no": roll["roll_no"], "article": "Batik Uji"},
                {"hold": False, "roll_id": "x", "roll_no": "RL-LOLOS", "article": "Lain"}]},
            {"id": "ins_g3_b", "lines": [{"hold": False, "roll_no": "RL-1"}]}]
    extra = run(backlog.inspection_hold_extras(docs))
    assert "ins_g3_b" not in extra                                   # tanpa baris ditahan → tidak diubah
    e = extra["ins_g3_a"]
    assert e["product"] == "Batik Uji"
    assert roll["roll_no"] in e["note"] and "RL-LOLOS" not in e["note"]
    if wh.get("name"):
        assert wh["name"] in e["note"]
    # judul kosong → produk; note tidak mengulang produk & tanpa " · —"
    row = {"title": "—", "note": "Bagian Inspect"}
    backlog._apply_hold_extras(row, e, with_note=True)
    assert row["title"] == "Batik Uji" and "Bagian Inspect" not in row["note"] and "—" not in row["note"]
    # judul sudah berisi (pemasok) → produk masuk ke note
    row2 = {"title": "PT Pemasok", "note": ""}
    backlog._apply_hold_extras(row2, e, with_note=True)
    assert row2["title"] == "PT Pemasok" and row2["note"].startswith("Batik Uji")
    # kartu "Paling Lama Menunggu" (tanpa note) tetap tanpa kolom note baru
    row3 = {"title": "—"}
    backlog._apply_hold_extras(row3, e, with_note=False)
    assert row3["title"] == "Batik Uji" and "note" not in row3


def test_g3_32_satuan_kpi_tanpa_label_tanpa_satuan():
    from routers import dashboard
    prod = DB.products.find_one({"base_unit": {"$nin": [None, ""]}}, {"_id": 0, "id": 1, "base_unit": 1})
    unit_of, unitless = run(dashboard._units_for_products([prod["id"], "prod_tidak_ada_g3"]))
    assert unit_of[prod["id"]] == prod["base_unit"]
    assert unitless == {"prod_tidak_ada_g3": dashboard.UNIT_UNKNOWN_PRODUCT}
    assert "tanpa satuan" not in (dashboard.UNIT_MISSING, dashboard.UNIT_UNKNOWN_PRODUCT)
