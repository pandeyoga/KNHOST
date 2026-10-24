"""UAT 24 Okt — fase F5 (ANALISIS_TEMUAN_UAT_23OKT.md P7 Perbaikan, P12 sorotan POS, P16.2 PDF di Jejak Dokumen,
P17 pratinjau lampiran tanpa token di URL).

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_f5.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402 — loop tempat klien Motor terikat

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
ENT = "ent_ksc"
ROLLS: list = []
REPAIRS: list = []


def _login(email, entity=ENT):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}


ADMIN = _login("admin@kainnusantara.id")
SALES = _login("sales@kainnusantara.id")


def _roll(length=100.0, uc=20000.0):
    src = DB.inventory_rolls.find_one({"owner_entity_id": ENT, "status": "available", "unit_cost": {"$gt": 0},
                                       "length_reserved": {"$in": [None, 0]}}, {"_id": 0})
    rid = f"roll_TEST_F5_{T}_{len(ROLLS)}"
    doc = {**src, "id": rid, "roll_no": f"TF5-{T}-{len(ROLLS)}", "length_remaining": length, "length_initial": length,
           "length_reserved": 0, "length_reservations": [], "reserved_ref": None, "earmarked_for": None, "unit_cost": uc,
           "base_unit_cost": uc, "grade": "A", "lot": f"LOT-{T}", "status": "available", "repair_open": "",
           "bucket_ref": None, "repair_history": []}
    DB.inventory_rolls.insert_one(doc)
    ROLLS.append(rid)
    from services.roll_service import rebuild_balance
    run(rebuild_balance(doc["product_id"], doc["warehouse_id"], doc["owner_entity_id"]))   # saldo ikut roll uji
    return doc


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    ids = list(ROLLS) + [r["id"] for r in DB.inventory_rolls.find({"parent_roll_id": {"$in": ROLLS}}, {"id": 1})]
    segs = {(r["product_id"], r["warehouse_id"], r["owner_entity_id"]) for r in DB.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0})}
    DB.inventory_rolls.delete_many({"id": {"$in": ids}})
    DB.inventory_movements.delete_many({"source_document": {"$in": REPAIRS}})
    DB.journal_entries.delete_many({"source_type": "repair_order", "source_id": {"$in": REPAIRS}})
    DB.repair_orders.delete_many({"id": {"$in": REPAIRS}})
    from services.roll_service import rebuild_balance
    for p, w, o in segs:
        run(rebuild_balance(p, w, o))


def _create(rolls, **kw):
    body = {"kind": "perbaikan", "partner_type": "internal", "roll_ids": [r["id"] for r in rolls],
            "cost": {"basis": "per_unit", "rate": 1000}, **kw}
    r = requests.post(f"{BASE}/repair-orders", headers=ADMIN, json=body)
    assert r.status_code == 200, r.text
    REPAIRS.append(r.json()["id"])
    return r.json()


def _bal_available(r):
    b = DB.inventory_balances.find_one({"product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
                                        "owner_entity_id": r["owner_entity_id"]}, {"available_qty": 1}) or {}
    return float(b.get("available_qty") or 0)


# ─── P7 — Perbaikan ─────────────────────────────────────────────────────────
def test_p7_kirim_keluar_atp_terima_susut_grade_lot_baru_biaya_dikapitalisasi_berjurnal():
    a, b = _roll(100, 20000), _roll(50, 20000)
    ro = _create([a, b], partner_type="makloon",
                 partner_id=DB.makloons.find_one({"status": "active"}, {"id": 1})["id"],
                 cost={"basis": "per_unit", "rate": 1000, "other_costs": [{"label": "Ongkos kirim", "amount": 50000}]})
    assert ro["status"] == "draft" and ro["cost_estimate"] == 150 * 1000 + 50000 and ro["number"].startswith("KSC/RPR")
    before = _bal_available(a)
    r = requests.post(f"{BASE}/repair-orders/{ro['id']}/send", headers=ADMIN)
    assert r.status_code == 200, r.text
    rolls = {x["id"]: x for x in DB.inventory_rolls.find({"id": {"$in": [a["id"], b["id"]]}}, {"_id": 0})}
    assert all(x["status"] == "wip" and x["repair_open"] == ro["id"] for x in rolls.values())
    assert round(before - _bal_available(a), 2) == 150.0                     # keluar dari stok jual
    # roll yang sedang diperbaiki tidak bisa masuk dokumen perbaikan lain
    r2 = requests.post(f"{BASE}/repair-orders", headers=ADMIN, json={"roll_ids": [a["id"]], "kind": "perbaikan"})
    assert r2.status_code == 400
    r = requests.post(f"{BASE}/repair-orders/{ro['id']}/receive", headers=ADMIN, json={
        "actual_cost": 196000, "lines": [{"roll_id": a["id"], "qty_out": 98, "grade": "B", "dye_lot": f"DL-{T}"},
                                         {"roll_id": b["id"], "qty_out": 49, "grade": "A", "dye_lot": ""}]})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "done" and done["total_shrink"] == 3.0 and done["actual_cost"] == 196000
    ra = DB.inventory_rolls.find_one({"id": a["id"]}, {"_id": 0})
    assert ra["status"] == "available" and ra["length_remaining"] == 98 and ra["grade"] == "B" and ra["lot"] == f"DL-{T}"
    # P7-K1 — nilai lama (100 × 20.000) + alokasi biaya (196.000 × 98/147) dibagi qty hasil
    assert abs(ra["unit_cost"] - (100 * 20000 + 196000 * 98 / 147) / 98) < 0.01
    assert ra["repair_history"][-1]["number"] == done["number"]
    je = DB.journal_entries.find_one({"source_type": "repair_order", "source_id": ro["id"]}, {"_id": 0})
    acc = {ln["account_code"]: (ln["debit"], ln["credit"]) for ln in je["lines"]}
    assert acc["1-1300"] == (196000, 0) and acc["2-1100"] == (0, 196000)
    assert DB.inventory_movements.count_documents({"source_document": ro["id"], "movement_type": "repair_loss"}) == 2


def test_p7_celup_ulang_ganti_sku_jadi_roll_anak_dan_batal_mengembalikan_roll():
    a = _roll(80, 15000)
    target = DB.products.find_one({"status": "active", "id": {"$ne": a["product_id"]}, "base_unit": a.get("unit")},
                                  {"_id": 0, "id": 1, "sku": 1}) or DB.products.find_one({"status": "active", "id": {"$ne": a["product_id"]}}, {"_id": 0, "id": 1, "sku": 1})
    r = requests.post(f"{BASE}/repair-orders", headers=ADMIN, json={"kind": "celup_ulang", "roll_ids": [a["id"]]})
    assert r.status_code == 400 and "warna tujuan" in r.text
    ro = _create([a], kind="celup_ulang", target_color="Navy", target_product_id=target["id"], cost={"basis": "lumpsum", "rate": 0})
    assert requests.post(f"{BASE}/repair-orders/{ro['id']}/send", headers=ADMIN).status_code == 200
    r = requests.post(f"{BASE}/repair-orders/{ro['id']}/receive", headers=ADMIN,
                      json={"lines": [{"roll_id": a["id"], "qty_out": 78, "grade": "A", "dye_lot": f"NV-{T}"}]})
    assert r.status_code == 200, r.text
    child = DB.inventory_rolls.find_one({"parent_roll_id": a["id"]}, {"_id": 0})
    assert child["product_id"] == target["id"] and child["length_remaining"] == 78 and child["status"] == "available"
    assert DB.inventory_rolls.find_one({"id": a["id"]}, {"status": 1})["status"] == "consumed"
    assert not DB.journal_entries.find_one({"source_type": "repair_order", "source_id": ro["id"]})   # biaya 0 → tanpa jurnal
    # Batal dari Dikirim → roll kembali ke status semula & stok jual
    c = _roll(30, 10000)
    ro2 = _create([c])
    requests.post(f"{BASE}/repair-orders/{ro2['id']}/send", headers=ADMIN)
    r = requests.post(f"{BASE}/repair-orders/{ro2['id']}/cancel", headers=ADMIN, json={"reason": "salah pilih roll"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    rc = DB.inventory_rolls.find_one({"id": c["id"]}, {"_id": 0})
    assert rc["status"] == "available" and not rc.get("repair_open")


def test_p7_izin_sales_tidak_bisa_membuat_perbaikan():
    assert requests.get(f"{BASE}/repair-orders", headers=SALES).status_code == 403


# ─── P12 — sorotan POS ──────────────────────────────────────────────────────
def test_p12_terlaris_bisa_dimatikan_berjendela_waktu_dan_saringan_visibilitas():
    from services import config_resolver as cfg
    from services import pos_recommendation_service as pos
    try:
        run(cfg.set_value("pos.best_sellers.enabled", False, scope_type="entity", scope_id=ENT, actor="uji", reason="uji F5"))
        assert requests.get(f"{BASE}/pos/best-sellers", headers=ADMIN).json() == []
        assert requests.get(f"{BASE}/pos/highlights-config", headers=ADMIN).json()["best_sellers"]["enabled"] is False
    finally:
        run(cfg.set_value("pos.best_sellers.enabled", True, scope_type="entity", scope_id=ENT, actor="uji", reason="uji F5"))
    rows = requests.get(f"{BASE}/pos/best-sellers", headers=ADMIN).json()
    assert all(r["window_days"] == 90 for r in rows)
    p = {"status": "active", "lifecycle": "produksi", "exclusive_customer_id": "c_pemilik", "exclusive_allow_customer_ids": ["c_lama"]}
    assert pos.visible_for(p, "c_pemilik") and pos.visible_for(p, "c_lama")
    assert not pos.visible_for(p, "c_lain") and not pos.visible_for(p, "")
    assert not pos.visible_for({"status": "inactive"}, "") and pos.visible_for({"status": "active"}, "")


def test_p12_produk_unggulan_tampil_sampai_tanggal_akhir():
    prod = DB.products.find_one({"status": "active", "exclusive_customer_id": {"$in": [None, ""]},
                                 "lifecycle": {"$in": [None, "", "produksi"]}}, {"_id": 0, "id": 1})
    snap = DB.products.find_one({"id": prod["id"]}, {"_id": 0, "is_featured": 1, "featured_until": 1, "featured_rank": 1, "featured_note": 1})
    try:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = requests.post(f"{BASE}/pos/featured/{prod['id']}", headers=ADMIN,
                          json={"is_featured": True, "rank": 0, "until": tomorrow, "note": f"Promo {T}"})
        assert r.status_code == 200, r.text
        assert requests.post(f"{BASE}/pos/featured/{prod['id']}", headers=SALES, json={"is_featured": True}).status_code == 403
        feat = requests.get(f"{BASE}/pos/featured", headers=ADMIN).json()
        assert any(x["product_id"] == prod["id"] and x["featured_note"] == f"Promo {T}" for x in feat)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        requests.post(f"{BASE}/pos/featured/{prod['id']}", headers=ADMIN, json={"is_featured": True, "until": yesterday})
        assert all(x["product_id"] != prod["id"] for x in requests.get(f"{BASE}/pos/featured", headers=ADMIN).json())
    finally:
        DB.products.update_one({"id": prod["id"]}, {"$set": {k: snap.get(k) for k in ("is_featured", "featured_until", "featured_rank", "featured_note")}})


def test_p12_rekomendasi_pelanggan_bukan_barang_yang_sudah_dibeli():
    so = DB.sales_orders.find_one({"entity_id": ENT, "status": {"$nin": ["cancelled", "draft"]}, "customer_id": {"$nin": [None, ""]}},
                                  {"_id": 0, "customer_id": 1})
    r = requests.get(f"{BASE}/pos/recommendations", headers=ADMIN, params={"customer_id": so["customer_id"]})
    assert r.status_code == 200, r.text
    bought = {it.get("product_id") for o in DB.sales_orders.find({"customer_id": so["customer_id"]}, {"items.product_id": 1})
              for it in o.get("items") or []}
    assert all(x["product_id"] not in bought and x["reason"] and x["available_qty"] > 0 for x in r.json())


# ─── P16.2 & P17 ─────────────────────────────────────────────────────────────
def test_p16_node_jejak_membawa_jenis_pdf_dan_p17_tanpa_token_di_url():
    from services import doc_refs_service as refs
    from services.return_attachment_service import disposition
    assert refs.node_of("purchase_order", {"id": "x"})["pdf_doc_type"] == "purchase_order"
    assert refs.node_of("makloon_order", {"id": "x"})["pdf_doc_type"] == "makloon_spk"
    assert refs.node_of("payment_plan", {"id": "x"})["pdf_doc_type"] == ""
    tok = ADMIN["Authorization"].split(" ", 1)[1]
    for url in (f"{BASE}/sales-orders/x/approvals/y/evidence/z/download", f"{BASE}/price-approvals/x/attachments/y/download"):
        assert requests.get(url, params={"auth": tok}).status_code == 401          # token di URL tidak lagi diterima
    assert disposition({"content_type": "image/jpeg", "filename": "a.jpg"}).startswith("inline")
    assert disposition({"content_type": "image/jpeg", "filename": "a.jpg"}, download=True).startswith("attachment")
    assert disposition({"content_type": "application/pdf", "filename": "a.pdf"}).startswith("attachment")
