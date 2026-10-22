"""Retur PER ROLL (permintaan pemilik 23 Okt 2026).

* Alasan, kondisi, checklist (hangtag hilang / sudah dipotong pelanggan) & foto dicatat per roll.
* Pemegang `sales_return.decide_rolls` (bawaan Admin, Manajer, Admin Sales — dapat diatur di matriks akses) boleh
  menolak roll tertentu sebelum ACC; roll ditolak keluar dari retur (qty, nilai, checklist) dan bebas diklaim lagi.

Tes ini TIDAK meninggalkan data di DB (DB lokal = data acuan UAT): dokumen uji sementara dihapus di `finally`, dan
permintaan API yang diuji gagal sebelum menulis (izin / validasi).
Jalankan: cd /app/backend && python -m pytest tests/test_return_per_roll.py -p no:randomly -n 0 -q
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
    """Klien Motor global terikat ke loop PERTAMA yang memakainya — bila modul tes lain dalam satu sesi pytest sudah
    mengikatnya ke loop miliknya, pakai loop itu (loop baru → "attached to a different loop")."""
    from db import db as _db
    loop = _db.client._io_loop
    if loop is None or loop.is_closed():
        loop = _db.client._io_loop = _LOOP
    return loop.run_until_complete(coro_fn())


def _ret(tag, status="pending_approval", order_id=""):
    return {"id": f"sret_uji_pr_{tag}", "number": f"UJI/SRET-PR-{tag}", "entity_id": base.ENT, "order_id": order_id,
            "status": status, "customer_id": base.CUST, "condition_flags": {"replacement_proof": True},
            "items": [{"product_id": "prod_uji_pr", "product_name": "Kain uji", "unit": "yard", "quantity_returned": 30,
                       "qty_rolls": 2, "roll_ids": [f"r1_{tag}", f"r2_{tag}"],
                       "roll_qtys": {f"r1_{tag}": 10, f"r2_{tag}": 20}, "condition": "damaged",
                       "reason": "hangtag lepas; sudah dipotong",
                       "roll_details": {f"r1_{tag}": {"reason": "hangtag lepas", "condition": "ok", "hangtag_missing": True},
                                        f"r2_{tag}": {"reason": "sudah dipotong", "condition": "damaged",
                                                      "cut_by_customer": True}}}]}


@pytest.fixture()
def temp_return():
    tag = uuid.uuid4().hex[:6]
    made = []

    def make(**kw):
        doc = _ret(tag, **kw)
        DB.sales_returns.insert_one(dict(doc))
        made.append(doc["id"])
        return doc, tag
    yield make
    DB.sales_returns.delete_many({"id": {"$in": made}})


def test_izin_bawaan_decide_rolls_manajer_admin_sales_bukan_sales():
    from permissions_config import DEFAULT_PERMISSIONS
    from access_modules import ACTION_LABEL
    for role in ("admin", "manager", "sales_admin"):
        assert "decide_rolls" in DEFAULT_PERMISSIONS[role]["sales_return"], role
    assert "decide_rolls" not in DEFAULT_PERMISSIONS["sales"].get("sales_return", [])
    assert ACTION_LABEL["decide_rolls"]   # tampil di matriks akses → bisa diberikan ke peran kustom


def test_api_sales_tanpa_izin_ditolak_admin_sales_wajib_alasan(temp_return):
    doc, tag = temp_return()
    c, b = base.Api("sales@kainnusantara.id").call(
        "POST", f"/sales-returns/{doc['id']}/roll-decisions", {"decisions": [{"roll_id": f"r2_{tag}", "decision": "reject"}]})
    assert c == 403, b
    sadm = base.Api("salesadmin@kainnusantara.id")
    c, b = sadm.call("POST", f"/sales-returns/{doc['id']}/roll-decisions",
                     {"decisions": [{"roll_id": f"r2_{tag}", "decision": "reject", "reason": "ok"}]})
    assert c == 400 and "Alasan tolak" in str(b), b
    c, b = sadm.call("POST", f"/sales-returns/{doc['id']}/roll-decisions",
                     {"decisions": [{"roll_id": "roll_bukan_klaim", "decision": "reject", "reason": "sudah dipotong"}]})
    assert c == 400 and "tidak termasuk klaim" in str(b), b
    assert DB.sales_returns.find_one({"id": doc["id"]})["items"][0]["roll_ids"] == [f"r1_{tag}", f"r2_{tag}"]


def test_api_keputusan_roll_hanya_sebelum_acc(temp_return):
    doc, tag = temp_return(status="approved")
    c, b = base.Api("salesadmin@kainnusantara.id").call(
        "POST", f"/sales-returns/{doc['id']}/roll-decisions",
        {"decisions": [{"roll_id": f"r2_{tag}", "decision": "reject", "reason": "sudah dipotong"}]})
    assert c == 400 and "sebelum retur disetujui" in str(b), b


def test_api_foto_per_roll_harus_roll_klaim(temp_return):
    doc, _tag = temp_return()
    c, b = base.Api("sales@kainnusantara.id").call(
        "POST", f"/sales-returns/{doc['id']}/attachments", None,
        files={"file": ("x.jpg", b"\xff\xd8\xff\xe0" + b"0" * 32, "image/jpeg")}, data={"roll_id": "roll_bukan_klaim"})
    assert c == 400 and "bukan roll klaim" in str(b), b
    assert not DB.sales_returns.find_one({"id": doc["id"]}).get("attachments")


def test_tolak_satu_roll_qty_checklist_alasan_dan_klaim_ikut_turun(temp_return):
    from services import return_rolls_service as rrs
    doc, tag = temp_return()
    out = _run(lambda: rrs.decide_rolls(doc, [{"roll_id": f"r1_{tag}", "decision": "accept"},
                                              {"roll_id": f"r2_{tag}", "decision": "reject", "reason": "kain sudah dipotong"}],
                                        {"name": "Admin Sales Uji", "role": "sales_admin"}))
    it = out["items"][0]
    assert out["status"] == "pending_approval"
    assert it["roll_ids"] == [f"r1_{tag}"] and it["roll_qtys"] == {f"r1_{tag}": 10}
    assert it["quantity_returned"] == 10 and it["qty_rolls"] == 1
    assert it["rejected_rolls"][0]["roll_id"] == f"r2_{tag}" and it["rejected_rolls"][0]["qty"] == 20
    assert it["roll_details"][f"r2_{tag}"]["decision"] == "reject"          # detail klaim roll ditolak tetap tersimpan
    assert it["roll_details"][f"r1_{tag}"]["decision"] == "accept"
    assert it["reason"] == "hangtag lepas" and it["condition"] == "ok"     # ringkasan baris = roll yang masih diklaim
    assert out["condition_flags"] == {"hangtag_missing": True, "cut_by_customer": False, "replacement_proof": True}
    assert out["roll_decision_log"][-1]["role"] == "sales_admin"


def test_tolak_semua_roll_retur_ditolak(temp_return):
    from services import return_rolls_service as rrs
    doc, tag = temp_return()
    out = _run(lambda: rrs.decide_rolls(doc, [{"roll_id": f"r1_{tag}", "decision": "reject", "reason": "hangtag hilang"},
                                              {"roll_id": f"r2_{tag}", "decision": "reject", "reason": "sudah dipotong"}],
                                        {"name": "Manajer Uji", "role": "manager"}))
    assert out["status"] == "rejected" and "Semua roll klaim ditolak" in out["reject_reason"]
    assert out["items"][0]["settle_outcome"] == "reject"


def test_roll_ditolak_bebas_diklaim_lagi(temp_return):
    from services import return_rolls_service as rrs
    tag = uuid.uuid4().hex[:6]
    so_id, sj_id = f"so_uji_pr_{tag}", f"sj_uji_pr_{tag}"
    doc, rtag = temp_return(order_id=so_id)
    DB.shipments.insert_one({"id": sj_id, "order_id": so_id, "status": "delivered", "product_id": "prod_uji_pr",
                             "rolls": [{"roll_id": f"r1_{rtag}", "length": 10}, {"roll_id": f"r2_{rtag}", "length": 20}]})
    try:
        rem = lambda: {r["roll_id"]: r["remaining"] for r in _run(lambda: rrs.returnable(so_id))["rolls"]}  # noqa: E731
        assert rem() == {f"r1_{rtag}": 0, f"r2_{rtag}": 0}
        _run(lambda: rrs.decide_rolls(doc, [{"roll_id": f"r2_{rtag}", "decision": "reject", "reason": "sudah dipotong"}],
                                      {"name": "Admin Sales Uji", "role": "sales_admin"}))
        assert rem() == {f"r1_{rtag}": 0, f"r2_{rtag}": 20}
    finally:
        DB.shipments.delete_one({"id": sj_id})


def test_buat_retur_detail_per_roll_dirapikan_dan_flag_dokumen():
    from services.return_rolls_service import condition_flags_of, normalize_roll_details
    it = {"roll_ids": ["a", "b"], "reason": "", "condition": "ok",
          "roll_details": {"a": {"reason": " noda ", "condition": "damaged", "hangtag_missing": 1},
                           "b": {"reason": "kelebihan kirim", "cut_by_customer": True},
                           "x": {"reason": "bukan klaim", "cut_by_customer": True}}}
    normalize_roll_details(it)
    assert set(it["roll_details"]) == {"a", "b"}                     # roll di luar klaim dibuang
    assert it["roll_details"]["a"]["reason"] == "noda" and it["roll_details"]["a"]["hangtag_missing"] is True
    assert it["condition"] == "damaged" and it["reason"] == "noda; kelebihan kirim"
    assert condition_flags_of([it], {}) == {"hangtag_missing": True, "cut_by_customer": True, "replacement_proof": False}
