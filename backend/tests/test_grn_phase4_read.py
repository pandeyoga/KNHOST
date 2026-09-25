"""GRN Fase 4 — alur `POST /goods-receipts/{id}/read` memakai model TIRUAN (env OCR_ALLOW_MOCK=1, model `mock-*`).

Membuktikan: pemetaan SJ → kepala & baris bertarget, greige diabaikan, non-stok, log biaya `ai_usage_log`, pembaca kedua
saat ragu + sorotan beda, angka ambigu memblokir start-count, OCR mati/anggaran habis → read_failed, klik ganda aman.
"""
import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, "/app/backend/tests")
import test_grn_phase2 as _p2  # noqa: E402
from test_grn_phase2 import BASE, _ok, _supplier  # noqa: E402

admin, wh, mdb, env = _p2.admin, _p2.wh, _p2.mdb, _p2.env   # fixture dipakai ulang

KEYS = {"receiving.ocr_enabled": True, "receiving.ocr_model_primary": "mock-sj_clear",
        "receiving.ocr_model_second": "mock-sj_doubt_second", "receiving.ocr_monthly_budget_usd": 75}
DEFAULTS = {"receiving.ocr_enabled": False, "receiving.ocr_model_primary": "gpt-6-sol",
            "receiving.ocr_model_second": "gpt-5.6-sol", "receiving.ocr_monthly_budget_usd": 75}


def _cfg(s, values):
    items = [{"key": k, "value": v, "scope_type": "global", "reason": "TEST_ uji OCR fase 4"} for k, v in values.items()]
    _ok(s.put(f"{BASE}/config/values", json={"items": items}))


@pytest.fixture()
def ocr(admin, mdb):
    if os.environ.get("OCR_ALLOW_MOCK") != "1" and "OCR_ALLOW_MOCK" not in open("/app/backend/.env").read():
        pytest.skip("OCR_ALLOW_MOCK tidak aktif")
    before = set(mdb.ai_usage_log.distinct("id"))
    _cfg(admin, KEYS)
    yield lambda v: _cfg(admin, v)
    _cfg(admin, DEFAULTS)
    mdb.ai_usage_log.delete_many({"id": {"$nin": list(before)}})


def _grn_with_photo(admin, mdb, task):
    g = _ok(admin.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": _supplier(mdb, task),
                                                       "warehouse_id": task["warehouse_id"]}))
    buf = io.BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(buf, "JPEG")
    res = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/files", files={"file": ("sj.jpg", buf.getvalue(), "image/jpeg")},
                         data={"expected_version": str(g["version"])}))
    return res["grn"]


def test_read_clear_maps_header_lines_and_logs_cost(admin, wh, mdb, env, ocr):
    _, clone = env
    t = clone(park_seed=True)
    mdb.purchase_orders.update_one({"id": t["po_id"]}, {"$set": {"po_number": "KSC/PO-00014"}})
    g = _grn_with_photo(admin, mdb, t)
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}))
    assert g["status"] == "review" and g["extraction"]["read_failed"] is False, g["extraction"]
    assert g["dn"]["number"] == "SJ-MOCK-CLEAR" and g["dn"]["source"] == "ocr" and g["dn"]["date"] == "2026-06-10"
    assert g["extraction"]["prompt_version"] == "sj-v2"
    l1, l2 = g["lines"]
    assert l1["target"]["task_id"] == t["id"] and l1["match"]["status"] in ("probable", "exact")
    assert l1["declared"]["qty"] == 250 and l1["declared"]["unit"] == "yard" and l1["declared"]["rolls"] == 2
    assert l1["converted"]["qty"] == 250 and l1["decision"] == "accept" and l1["checks"]["qty_parse"] == "ok"
    assert l2["is_non_stock"] is True and l2["target"] is None
    assert len(g["extraction"]["runs"]) == 1       # jelas → pembaca kedua tidak dipanggil
    logs = list(mdb.ai_usage_log.find({"ref_id": g["id"]}))
    assert len(logs) == 1 and logs[0]["status"] == "ok" and logs[0]["cost_usd"] == 0.0 and logs[0]["pages"] == 1
    # klik ganda → status sudah review → 409, tanpa log baru
    assert admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}).status_code == 409
    assert mdb.ai_usage_log.count_documents({"ref_id": g["id"]}) == 1
    # hitung buta: penghitung tidak menerima hasil ekstraksi
    blind = _ok(wh.get(f"{BASE}/goods-receipts/{g['id']}"))
    assert "extraction" not in blind and "declared" not in blind["lines"][0]
    usage = _ok(admin.get(f"{BASE}/goods-receipts/usage"))
    assert any(r["model"] == "mock-sj_clear" and r["calls"] >= 1 for r in usage["rows"])
    assert wh.get(f"{BASE}/goods-receipts/usage").status_code == 403
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))


def test_read_doubtful_calls_second_reader_and_blocks_ambiguous(admin, mdb, env, ocr):
    _, clone = env
    t = clone(park_seed=True)
    mdb.purchase_orders.update_one({"id": t["po_id"]}, {"$set": {"po_number": "KSC/PO-00014"}})
    ocr({"receiving.ocr_model_primary": "mock-sj_doubt"})
    g = _grn_with_photo(admin, mdb, t)
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}))
    assert [r["role"] for r in g["extraction"]["runs"]] == ["primary", "second"]
    assert {d["field"] for d in g["extraction"]["header_diff"]} == {"dn_number"}
    ln = g["lines"][0]
    assert ln["checks"]["qty_parse"] == "ambiguous" and ln["declared"]["qty"] is None
    assert any(d["field"] == "qty:delivered_length" for d in ln["checks"]["second_reader_diff"])
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]})
    assert r.status_code == 400 and "ragu" in r.json()["detail"]["message"]
    # manusia memperbaiki qty → centang, lalu boleh mulai hitung
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/lines/1", json={
        "expected_version": g["version"], "declared": {"qty": 1250, "unit": "yard", "rolls": 2}}))
    assert g["lines"][0]["checks"]["qty_parse"] == "ok"
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))


def test_read_disabled_and_budget_exhausted(admin, mdb, env, ocr):
    _, clone = env
    t = clone()
    g = _grn_with_photo(admin, mdb, t)
    ocr({"receiving.ocr_enabled": False})
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]})
    assert r.status_code == 400
    ocr({"receiving.ocr_enabled": True, "receiving.ocr_monthly_budget_usd": 0.5})
    mdb.ai_usage_log.insert_one({"id": "aiu_test_budget", "at": "2999-01-01", "feature": "ocr_dn", "entity_id": "ent_ksc",
                                 "cost_usd": 1.0, "status": "ok", "model": "x"})
    try:
        mdb.ai_usage_log.update_one({"id": "aiu_test_budget"}, {"$set": {"at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()}})
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}))
        assert g["status"] == "review" and g["extraction"]["read_failed"] is True
        assert g["extraction"]["error_code"] == "OCR_BUDGET"
    finally:
        mdb.ai_usage_log.delete_one({"id": "aiu_test_budget"})
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))
