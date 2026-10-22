"""QC retur lewat SPK per roll (permintaan pemilik 23 Okt 2026, fase 2).

* SPK `return_customer` = satu baris per roll klaim (qty klaim per roll; baris tanpa roll tetap per barang).
* Isi baris retur: form 4-point yang sama, grade DIISI PETUGAS, kondisi & qty aktual; roll pelanggan tidak diubah;
  pagar: retur disetujui/sedang diinspeksi, roll masih diklaim, roll ITU sudah diterima gudang.
* Tutup SPK → hasil per roll menjadi hasil retur (grade terburuk per barang, `roll_results`, `roll_actuals`).

Tes ini TIDAK meninggalkan data di DB: dokumen retur sementara dihapus di `finally` (fungsi yang diuji hanya
menulis dokumen retur itu sendiri).
Jalankan: cd /app/backend && python -m pytest tests/test_return_spk_per_roll.py -p no:randomly -n 0 -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB
_LOOP = asyncio.new_event_loop()


def _run(coro_fn):
    """Klien Motor global terikat ke loop pertama yang memakainya (lihat test_return_per_roll)."""
    from db import db as _db
    loop = _db.client._io_loop
    if loop is None or loop.is_closed():
        loop = _db.client._io_loop = _LOOP
    return loop.run_until_complete(coro_fn())


@pytest.fixture()
def ret():
    tag = uuid.uuid4().hex[:6]
    doc = {"id": f"sret_uji_spk_{tag}", "number": f"UJI/SRET-SPK-{tag}", "entity_id": base.ENT, "status": "approved",
           "order_id": "", "items": [
               {"product_id": "prod_uji_spk", "product_name": "Kain uji", "unit": "yard", "quantity_returned": 30,
                "roll_ids": [f"r1_{tag}", f"r2_{tag}"], "roll_qtys": {f"r1_{tag}": 10, f"r2_{tag}": 20},
                "roll_details": {f"r1_{tag}": {"reason": "noda", "cut_by_customer": True}}},
               {"product_id": "prod_uji_spk2", "product_name": "Kain tanpa roll", "unit": "yard",
                "quantity_returned": 5}],
           "roll_locations": {f"r1_{tag}": {"stage": "received"}}}
    DB.sales_returns.insert_one(dict(doc))
    try:
        yield doc, tag
    finally:
        DB.sales_returns.delete_one({"id": doc["id"]})


def test_baris_spk_per_roll_qty_klaim_dan_baris_tanpa_roll(ret):
    from services import inspection_service as ins
    doc, tag = ret
    lines = _run(lambda: ins._lines_from_return_rolls(doc))
    assert [ln["roll_id"] for ln in lines] == [f"r1_{tag}", f"r2_{tag}", ""]
    assert [ln["quantity"] for ln in lines] == [10, 20, 5]            # dulu baris retur selalu 0 (field salah)
    assert [ln["return_item_index"] for ln in lines] == [0, 0, 1]
    assert lines[0]["claim"] == {"reason": "noda", "cut_by_customer": True}


def test_isi_baris_retur_pagar_penerimaan_grade_dan_status(ret):
    from services import inspection_service as ins
    doc, tag = ret
    spk = {"kind": "return_customer", "ref_doc_id": doc["id"]}
    actor = {"name": "QC Uji"}
    line2 = {"roll_id": f"r2_{tag}", "roll_no": "RL-2", "quantity": 20}
    with pytest.raises(ins.InspectionError, match="Scan terima roll ini"):
        _run(lambda: ins._inspect_return_roll(spk, line2, {"grade": "A"}, actor, "qc"))
    line1 = {"roll_id": f"r1_{tag}", "roll_no": "RL-1", "quantity": 10, "claim": {"condition": "damaged"}}
    with pytest.raises(ins.InspectionError, match="Pilih grade"):
        _run(lambda: ins._inspect_return_roll(spk, line1, {"defects": [{"point_value": 2, "count": 1}]}, actor, "qc"))
    assert DB.sales_returns.find_one({"id": doc["id"]})["status"] == "approved"   # gagal → status tak berubah
    out = _run(lambda: ins._inspect_return_roll(
        spk, line1, {"grade": "B", "defects": [{"point_value": 2, "count": 3}], "actual_qty": 9.5}, actor, "qc"))
    assert out["points_snapshot"] == 6 and out["grade_after"] == "B" and out["actual_qty"] == 9.5
    assert out["condition"] == "damaged"                              # bawaan = kondisi klaim pelanggan
    assert out["grade_rule"]["grade_source"] == "user"
    assert DB.sales_returns.find_one({"id": doc["id"]})["status"] == "inspecting"   # roll pertama → sedang diinspeksi
    DB.sales_returns.update_one({"id": doc["id"]}, {"$pull": {"items.0.roll_ids": f"r1_{tag}"}})
    with pytest.raises(ins.InspectionError, match="tidak termasuk klaim"):
        _run(lambda: ins._inspect_return_roll(spk, line1, {"grade": "A"}, actor, "qc"))


def test_tutup_spk_hasil_per_roll_menjadi_hasil_retur(ret):
    from services import return_service as rs
    doc, tag = ret
    DB.sales_returns.update_one({"id": doc["id"]}, {"$set": {
        "roll_locations": {f"r1_{tag}": {"stage": "received"}, f"r2_{tag}": {"stage": "received"}},
        "goods_arrived_at": "2026-10-23T08:00:00+00:00"}})
    lines = [
        {"roll_id": f"r1_{tag}", "roll_no": "RL-1", "quantity": 10, "grade_after": "A", "points_snapshot": 2,
         "defects": [{"point_value": 1, "count": 2}], "condition": "ok", "actual_qty": 9.8, "qc_by": "QC Uji"},
        {"roll_id": f"r2_{tag}", "roll_no": "RL-2", "quantity": 20, "grade_after": "B", "points_snapshot": 6,
         "defects": [{"point_value": 2, "count": 3}], "condition": "minor", "qc_by": "QC Uji"},
        {"roll_id": "", "return_item_index": 1, "quantity": 5, "grade_after": "A", "condition": "ok", "actual_qty": 5},
    ]
    with pytest.raises(ValueError, match="belum diperiksa"):
        _run(lambda: rs.complete_inspection_from_spk(doc["id"], lines[:1] + lines[2:], "QC Uji"))
    out = _run(lambda: rs.complete_inspection_from_spk(doc["id"], lines, "QC Uji"))
    assert out["status"] == "inspected"
    insp = out["items"][0]["inspection"]
    assert insp["grade"] == "B" and insp["points"] == 8 and insp["condition"] == "minor"   # terburuk per barang
    assert insp["roll_actuals"] == {f"r1_{tag}": 9.8, f"r2_{tag}": 20}
    assert insp["roll_results"][f"r1_{tag}"]["grade"] == "A" and insp["roll_results"][f"r2_{tag}"]["grade"] == "B"
    assert insp["source"] == "spk" and insp["accepted_qty"] == 29.8
    assert out["items"][1]["inspection"]["grade"] == "A"


def test_spk_retur_bisa_ditutup_petugas_qc_dan_lahir_saat_acc():
    """Kontrak izin & rute: QC (`qc.release`) menutup SPK retur; ACC retur memanggil `ensure_return_spk`."""
    import inspect as _inspect
    from routers import inspections as r_ins
    from routers import sales_returns as r_sr
    assert "KIND_RETURN_CUSTOMER" in _inspect.getsource(r_ins.finish_inspection)
    assert "ensure_return_spk" in _inspect.getsource(r_sr.approve_return)
