"""L04 LN-043 — komitmen bahan makloon: cadangan vs fisik, batal sesudah issue, hasil aktual vs forecast.

Memakai pola MKO-00004 (data acuan seed_p05_kn, ent_ksc, wh_jakarta; bahan ±1050 yard di 21 roll).
Data uji berlabel TEST_P05ACC (dibersihkan oleh restore_local_demo.sh bila perlu).
"""
import pytest
import requests

import test_p05_acceptance_acc31_33_34 as P
from test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _free, adm, output_is_makloon  # noqa: F401

S = {}


@pytest.fixture(scope="module", autouse=True)
def _cleanup(adm):  # noqa: F811
    yield
    for o in DB.makloon_orders.find({"notes": {"$regex": "^TEST_P05ACC LN043"}, "status": {"$nin": ["cancelled", "completed"]}},
                                    {"_id": 0, "id": 1}):
        requests.post(f"{BASE}/api/makloon-orders/{o['id']}/cancel", json={"reason": "TEST_P05ACC bersih"}, headers=adm, timeout=60)


def _ledger(h, mko_id):
    r = requests.get(f"{BASE}/api/makloon-orders/{mko_id}/material-ledger", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _out_free(pid, wh):
    return round(sum(float(r.get("length_remaining") or 0) for r in DB.inventory_rolls.find(
        {"product_id": pid, "warehouse_id": wh, "status": {"$in": ["available", "quarantine", "hold"]}},
        {"_id": 0, "length_remaining": 1})), 2)


def test_t01_commit_600_then_partial_issue(adm):  # noqa: F811
    t = P._tpl()
    pid, wh = t["material_product_id"], t["from_warehouse_id"]
    free0 = _free(pid, wh)
    if free0 < 700:
        pytest.skip(f"stok bahan {free0} < 700")
    commit0 = _free(pid, wh) - P._reserved_active(pid)
    mko = _create(adm, 600, "LN043-T01")
    S["t01"] = mko
    led = _ledger(adm, mko["id"])
    act0 = led["reservation"]["active"]
    assert act0 == pytest.approx(min(600, commit0), abs=0.05) and led["material"]["issued"] == 0
    assert act0 + led["reservation"]["shortage"] == pytest.approx(600, abs=0.01)
    assert _free(pid, wh) == pytest.approx(free0)                              # komitmen ≠ fisik keluar
    assert led["stock_now"]["free_for_new_commitment"] == pytest.approx(led["stock_now"]["available_physical"] - led["stock_now"]["reserved_all_orders"], abs=0.01)
    assert any(x.startswith("Dicadangkan") and "fisik tidak berkurang" in x for x in led["explain"])
    r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue",
                      json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 300}, headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    led = _ledger(adm, mko["id"])
    assert led["material"]["issued"] == pytest.approx(300) and led["material"]["at_partner"] == pytest.approx(300)
    assert led["reservation"]["active"] == pytest.approx(max(act0 - 300, 0), abs=0.01)
    assert led["reservation"]["consumed_by_issue"] == pytest.approx(min(300, act0), abs=0.01)
    assert _free(pid, wh) == pytest.approx(free0 - 300, abs=0.05)             # fisik turun TEPAT saat issue
    assert led["reconciled"] is True


def test_t03_actual_output_differs_from_forecast(adm):  # noqa: F811
    mko = S["t01"]
    step = DB.makloon_orders.find_one({"id": mko["id"]})["steps"][0]
    out_pid, twh = step["output_product_id"], mko.get("target_warehouse_id") or P._tpl()["from_warehouse_id"]
    mat_free = _free(P._tpl()["material_product_id"], P._tpl()["from_warehouse_id"])
    out0 = _out_free(out_pid, twh)
    actual = round(float(step["expected_output_qty"]) - 7.5, 2)
    body = {"step_seq": 1, "actual_output_qty": actual,
            "rolls": [{"lot": "TEST_P05ACC-LN043", "length": round(actual / 2, 2), "grade": "A"},
                      {"lot": "TEST_P05ACC-LN043", "length": round(actual - round(actual / 2, 2), 2), "grade": "A"}]}
    r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/receive", json=body, headers=adm, timeout=90)
    assert r.status_code == 200, r.text[:400]
    led = _ledger(adm, mko["id"])
    st = led["steps"][0]
    assert st["actual_output"] == pytest.approx(actual) and st["output_variance"] == pytest.approx(-7.5, abs=0.01)
    assert st["consumed"] == pytest.approx(300) and st["at_partner"] == 0 and led["reconciled"] is True
    assert _out_free(out_pid, twh) == pytest.approx(out0 + actual, abs=0.05)      # stok = fakta aktual
    assert _free(P._tpl()["material_product_id"], P._tpl()["from_warehouse_id"]) == pytest.approx(mat_free, abs=0.05)
    r2 = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/receive", json=body, headers=adm, timeout=90)
    assert r2.status_code in (400, 409)                                           # tanpa pengurangan/penambahan ganda
    assert _out_free(out_pid, twh) == pytest.approx(out0 + actual, abs=0.05)


def test_t02_cancel_after_issue_partial_return_and_loss(adm):  # noqa: F811
    t = P._tpl()
    pid, wh = t["material_product_id"], t["from_warehouse_id"]
    mko = _create(adm, 100, "LN043-T02")
    r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue",
                      json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 100}, headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    free_after_issue = _free(pid, wh)
    r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_P05ACC batal sesudah issue"},
                      headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert _free(pid, wh) == pytest.approx(free_after_issue, abs=0.05)            # batal ≠ stok kembali otomatis
    led = _ledger(adm, mko["id"])
    assert led["material"]["at_partner"] == pytest.approx(100) and led["steps"][0]["awaiting_return"] is True
    assert led["reservation"]["active"] == 0
    rolls = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()["rolls"]
    assert len(rolls) >= 2, rolls
    back, lost = rolls[0], rolls[1:]
    r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material",
                      json={"reason": "TEST_P05ACC sebagian kembali", "roll_ids": [back["id"]]}, headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert _free(pid, wh) == pytest.approx(free_after_issue + back["length_remaining"], abs=0.05)
    r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/material-loss",
                      json={"reason": "TEST_P05ACC hilang di mitra", "roll_ids": [x["id"] for x in lost]}, headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    led = _ledger(adm, mko["id"])
    st = led["steps"][0]
    lost_qty = round(sum(x["length_remaining"] for x in lost), 2)
    # tiga saldo dapat direkonsiliasi: kembali + susut (disetujui/menunggu) + masih di mitra = dikirim
    assert st["returned"] == pytest.approx(back["length_remaining"], abs=0.01)
    assert st["issued"] == pytest.approx(st["returned"] + st["lost"] + st["at_partner"] + st["consumed"], abs=0.01)
    assert st["lost"] + st["at_partner"] == pytest.approx(lost_qty, abs=0.01)
    assert led["reconciled"] is True
    loss = next((x for x in DB.makloon_orders.find_one({"id": mko["id"]})["steps"][0].get("material_losses") or []
                 if x.get("status") == "pending_approval"), None)
    if loss:   # susut di atas toleransi menunggu persetujuan: rol tetap "di mitra" sampai diputus
        assert st["loss_pending_approval"] == pytest.approx(lost_qty, abs=0.01)
        mgr = P._login("manager@kainnusantara.id")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/material-loss/{loss['id']}/decide",
                          json={"approve": True, "note": "TEST_P05ACC setuju", "settle": "tagih_ganti"}, headers=mgr, timeout=60)
        assert r.status_code == 200, r.text[:300]
        st = _ledger(adm, mko["id"])["steps"][0]
    assert st["lost"] == pytest.approx(lost_qty, abs=0.01) and st["at_partner"] == 0 and st["reconciled"] is True
    assert _free(pid, wh) == pytest.approx(free_after_issue + back["length_remaining"], abs=0.05)   # susut tak kembali ke stok
