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


# ─── Diteruskan ke retur SUPPLIER & retur ANTAR-PT (23 Okt) ─────────────────────────────────────────────────────
def _pret(tag, status="pending_approval", **extra):
    return {"id": f"pret_uji_pr_{tag}", "number": f"UJI/PRET-{tag}", "entity_id": base.ENT, "status": status,
            "supplier_name": "Supplier Uji", "ppn_rate": 11.0, "warehouse_id": "wh_uji",
            "items": [{"product_id": "prod_uji_pr", "unit": "yard", "price": 1000.0, "quantity": 30.0,
                       "subtotal": 30000.0, "reason": "cacat", "condition": "damaged",
                       "roll_ids": [f"a_{tag}", f"b_{tag}"], "roll_qtys": {f"a_{tag}": 10.0, f"b_{tag}": 20.0},
                       "rolls": [{"roll_id": f"a_{tag}", "roll_no": "RL-A", "lot": "L1", "length_remaining": 10.0},
                                 {"roll_id": f"b_{tag}", "roll_no": "RL-B", "lot": "L2", "length_remaining": 20.0}],
                       "roll_details": {f"a_{tag}": {"reason": "noda", "condition": "damaged"},
                                        f"b_{tag}": {"reason": "belang", "condition": "damaged",
                                                     "cut_by_customer": True}}}],
            "total_amount": 30000.0, "ppn_amount": 3300.0, "grand_total": 33300.0, **extra}


@pytest.fixture()
def temp_pret():
    made = []

    def make(**kw):
        tag = uuid.uuid4().hex[:6]
        doc = _pret(tag, **kw)
        DB.purchase_returns.insert_one(dict(doc))
        made.append(doc["id"])
        return doc, tag
    yield make
    DB.purchase_returns.delete_many({"id": {"$in": made}})


def test_supplier_izin_decide_rolls_dan_validasi(temp_pret):
    from permissions_config import DEFAULT_PERMISSIONS
    for role in ("admin", "manager"):
        assert "decide_rolls" in DEFAULT_PERMISSIONS[role]["purchase_return"]
        assert "decide_rolls" in DEFAULT_PERMISSIONS[role]["interco"]
    assert "decide_rolls" not in DEFAULT_PERMISSIONS["warehouse"].get("purchase_return", [])
    doc, tag = temp_pret()
    c, b = base.Api("warehouse@kainnusantara.id").call(
        "POST", f"/purchase-returns/{doc['id']}/roll-decisions", {"decisions": [{"roll_id": f"b_{tag}", "decision": "reject"}]})
    assert c == 403, b
    c, b = base.Api("manager@kainnusantara.id").call(
        "POST", f"/purchase-returns/{doc['id']}/roll-decisions",
        {"decisions": [{"roll_id": f"b_{tag}", "decision": "reject", "reason": "ok"}]})
    assert c == 400 and "Alasan tolak" in str(b), b
    c, b = base.Api("warehouse@kainnusantara.id").call(
        "POST", f"/purchase-returns/{doc['id']}/attachments", None,
        files={"file": ("x.jpg", b"\xff\xd8\xff\xe0" + b"0" * 32, "image/jpeg")}, data={"roll_id": "roll_bukan_klaim"})
    assert c == 400 and "bukan roll klaim" in str(b), b


def test_supplier_tolak_satu_roll_nilai_ppn_dihitung_ulang(temp_pret):
    from services import purchase_return_service as prs
    doc, tag = temp_pret()
    out = _run(lambda: prs.decide_rolls(doc["id"], [{"roll_id": f"b_{tag}", "decision": "reject",
                                                     "reason": "roll sudah dipotong, tidak bisa diklaim"}],
                                        {"name": "Manajer Uji", "role": "manager"}))
    it = out["items"][0]
    assert out["status"] == "pending_approval"
    assert it["roll_ids"] == [f"a_{tag}"] and [r["roll_id"] for r in it["rolls"]] == [f"a_{tag}"]
    assert it["quantity"] == 10 and it["subtotal"] == 10000 and it["lots"] == ["L1"]
    assert out["total_amount"] == 10000 and out["ppn_amount"] == 1100 and out["grand_total"] == 11100
    assert it["reason"] == "cacat"                       # kode alasan retur supplier tidak ditimpa kalimat roll
    out = _run(lambda: prs.decide_rolls(doc["id"], [{"roll_id": f"a_{tag}", "decision": "reject",
                                                     "reason": "noda bisa dicuci, simpan"}],
                                        {"name": "Manajer Uji", "role": "manager"}))
    assert out["status"] == "rejected" and "Semua roll retur ditolak" in out["reject_reason"]


def test_supplier_terima_sebagian_roll_tolakan_menunggu_barang_kembali(temp_pret):
    from services import purchase_return_service as prs
    doc, tag = temp_pret(status="approved", supplier_flow=True, supplier_status="shipped_supplier")
    with pytest.raises(ValueError, match="menolak SEMUA roll"):
        _run(lambda: prs._apply_supplier_rejections(
            doc, [{"roll_id": f"a_{tag}", "reason": "supplier bilang bukan cacat"},
                  {"roll_id": f"b_{tag}", "reason": "sudah dipotong pembeli"}], "Admin Uji"))
    out = _run(lambda: prs._apply_supplier_rejections(
        doc, [{"roll_id": f"b_{tag}", "reason": "sudah dipotong pembeli"}], "Admin Uji"))
    assert out["items"][0]["roll_ids"] == [f"a_{tag}"] and out["grand_total"] == 11100
    rej = out["items"][0]["rejected_rolls"][0]
    assert rej["by_supplier"] is True and rej["roll_id"] == f"b_{tag}"
    assert out["supplier_partial"] is True
    assert out["supplier_rejected_rolls"][0]["roll_id"] == f"b_{tag}"
    assert not out["supplier_rejected_rolls"][0]["goods_back_at"]


def _icr_pair(tag, mandatory=False):
    common = {"return_pair_id": f"icrp_uji_{tag}", "pair_id": f"icrp_uji_{tag}", "status": "draft",
              "seller_entity_id": "ent_seller_uji", "buyer_entity_id": base.ENT, "tax_apply": True, "tax_rate": 11.0,
              "mandatory_accept": mandatory, "timeline": [],
              "items": [{"product_id": "prod_uji_pr", "sku": "UJI", "unit": "yard", "quantity": 30.0, "unit_price": 2000.0,
                         "line_subtotal": 60000.0, "roll_ids": [f"a_{tag}", f"b_{tag}"],
                         "roll_qtys": {f"a_{tag}": 10.0, f"b_{tag}": 20.0},
                         "roll_details": {f"a_{tag}": {"reason": "warna beda"}, f"b_{tag}": {"reason": "kelebihan"}}}],
              "subtotal": 60000.0, "tax_amount": 6600.0, "grand_total": 66600.0, "qty_total": 30.0}
    return [{**common, "id": f"icr_uji_r_{tag}", "role": "returner", "entity_id": base.ENT},
            {**common, "id": f"icr_uji_s_{tag}", "role": "receiver", "entity_id": "ent_seller_uji"}]


@pytest.fixture()
def temp_icr():
    made = []

    def make(**kw):
        tag = uuid.uuid4().hex[:6]
        docs = _icr_pair(tag, **kw)
        DB.interco_returns.insert_many([dict(d) for d in docs])
        made.append(docs[0]["return_pair_id"])
        return docs[0], tag
    yield make
    DB.interco_returns.delete_many({"return_pair_id": {"$in": made}})


def test_antar_pt_tolak_roll_kedua_dokumen_kembar_ikut(temp_icr):
    from services import interco_return_service as icr
    doc, tag = temp_icr()
    pair = _run(lambda: icr.decide_rolls(doc["id"], [{"roll_id": f"b_{tag}", "decision": "reject",
                                                      "reason": "roll ini masih bagus, simpan"}],
                                         {"name": "Manajer Uji", "role": "manager"}))
    for side in ("returner", "receiver"):
        d = pair[side]
        assert d["items"][0]["roll_ids"] == [f"a_{tag}"] and d["items"][0]["quantity"] == 10
        assert d["subtotal"] == 20000 and d["tax_amount"] == 2200 and d["grand_total"] == 22200 and d["qty_total"] == 10
        assert d["status"] == "draft"
    pair = _run(lambda: icr.decide_rolls(doc["id"], [{"roll_id": f"a_{tag}", "decision": "reject",
                                                      "reason": "batal semua roll"}],
                                         {"name": "Manajer Uji", "role": "manager"}))
    assert pair["returner"]["status"] == "cancelled" and pair["receiver"]["status"] == "cancelled"


def test_antar_pt_wajib_terima_penjual_tidak_bisa_tolak(temp_icr):
    from services import interco_return_service as icr
    doc, tag = temp_icr(mandatory=True)
    with pytest.raises(icr.IntercoReturnError, match="WAJIB DITERIMA"):
        _run(lambda: icr.decide_rolls(doc["id"], [{"roll_id": f"b_{tag}", "decision": "reject",
                                                   "reason": "tidak mau terima"}],
                                      {"name": "Penjual Uji", "role": "manager"}, can_reject=False))
    pair = _run(lambda: icr.decide_rolls(doc["id"], [{"roll_id": f"b_{tag}", "decision": "accept"}],
                                         {"name": "Penjual Uji", "role": "manager"}, can_reject=False))
    assert pair["receiver"]["items"][0]["roll_details"][f"b_{tag}"]["decision"] == "accept"


def test_pagar_pihak_retur_antar_pt_membaca_dokumen_kembar(temp_icr):
    """Dulu `_guard_party` membaca objek PASANGAN {returner, receiver} → tak ada kolom pihak → selalu lolos."""
    doc, tag = temp_icr()
    DB.interco_returns.update_many({"return_pair_id": doc["return_pair_id"]},
                                   {"$set": {"seller_entity_id": "ent_luar_uji_a", "buyer_entity_id": "ent_luar_uji_b",
                                             "entity_id": "ent_luar_uji_b"}})
    c, b = base.Api("manager@kainnusantara.id").call(
        "POST", f"/interco/returns/{doc['id']}/roll-decisions",
        {"decisions": [{"roll_id": f"b_{tag}", "decision": "accept"}]})
    assert c == 404, b
