"""F-10 (uji pra-UAT 2026-10-21, keputusan owner Q-02) — termin CBD/DP menahan pengiriman.

Reproduksi SO-00041/SO-00084: termin *CBD — Bayar Sebelum Kirim*, belum dibayar → konfirmasi → pick → dispatch 200.
Kini: blok keras (409) sampai `paid_total ≥ dp_percent × grand_total`; pengecualian hanya oleh pemegang
`order.release_unpaid` (Finance/Manager/Admin) dengan alasan wajib & teraudit; gerbang dapat dimatikan per PT lewat
Pusat Pengaturan (`finance.dispatch_payment_gate`). Status tahan tampil di Barang Keluar, meja Gudang & pelacak SO.

Alur nyata lewat API akun peran (data acuan): Sales buat SO → Admin Sales verifikasi/konfirmasi → Gudang potong
(bila ada reservasi potong) & pick → Admin Gudang override loading check (tanpa perangkat RFID) → kirim.
Pembayaran dicatat Finance lewat Uang Masuk (`/ar-receipts`).
Jalankan: cd /app/backend && python -m pytest tests/test_f10_cbd_dp_dispatch_gate.py -p no:randomly -n 0 -q
"""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
PW = "demo12345"   # F-01 — satu sandi untuk semua akun seed


class Api:
    def __init__(self, email):
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PW}, timeout=30)
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}

    def call(self, method, path, js=None, **kw):
        r = requests.request(method, f"{BASE}{path}", json=js, headers=self.h, timeout=120, **kw)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text[:300]


@pytest.fixture(scope="module")
def u():
    return {k: Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                  ("mgr", "manager@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                  ("wh", "warehouse@kainnusantara.id"), ("whadm", "wh.admin@kainnusantara.id"),
                                  ("adm", "admin@kainnusantara.id"))}


def _product():
    """Produk KSC dengan ≥2 roll tersedia & bebas reservasi (qty kecil → satu roll / satu potong)."""
    pipeline = [{"$match": {"owner_entity_id": ENT, "status": "available", "length_remaining": {"$gt": 20},
                            "length_reserved": {"$not": {"$gt": 0}}}},
                {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gte": 3}}}, {"$limit": 200}]
    for g in DB.inventory_rolls.aggregate(pipeline):
        p = DB.products.find_one({"id": g["_id"], "is_active": {"$ne": False}, "base_unit": "yard"}, {"_id": 0, "id": 1})
        if p:
            return p["id"]
    pytest.skip("stok roll uji tidak cukup — jalankan restore data acuan")


def _ready_to_ship(u, term):
    """SO bertermin `term` sampai barang ter-pick & loading check di-override → tinggal kirim."""
    pid = _product()
    c, so = u["sales"].call("POST", "/sales-orders", {
        "customer_id": CUST, "shipping_address_id": "", "entity_id": ENT, "payment_term_code": term,
        "items": [{"product_id": pid, "quantity": 12.5, "unit": "yard"}], "confirm_mixed_lot": True,
        "fulfillment_method": "kirim", "qc_request": "none"})
    assert c == 200, so
    assert so["payment_term_code"] == term
    assert u["sadm"].call("POST", f"/sales-orders/{so['id']}/verify", {"note": "uji F-10"})[0] == 200
    c, b = u["sadm"].call("POST", f"/sales-orders/{so['id']}/submit-for-approval")
    assert c == 200, b
    if b.get("status") == "waiting_approval":
        c, b = u["mgr"].call("POST", f"/sales-orders/{so['id']}/approve")
        assert c == 200, b
    c, b = u["sadm"].call("POST", f"/sales-orders/{so['id']}/confirm")
    assert c == 200, b
    c, pc = u["wh"].call("GET", "/inventory/pending-cuts", params={"order_id": so["id"]})
    assert c == 200, pc
    for i in pc.get("items") or []:
        c, b = u["wh"].call("POST", f"/inventory/rolls/{i['roll_id']}/reservations/{i['reservation_id']}/cut",
                            {"actual_length": i["qty"], "waste": 0, "note": "uji F-10"})
        assert c == 200, b
        kid = b["child"]   # gudang tanpa RFID: identitas roll anak lewat label
        c, b = u["wh"].call("POST", f"/inventory/rolls/{kid['id']}/verify-identity", {"scanned_code": kid["roll_no"]})
        assert c == 200, b
    c, full = u["sadm"].call("GET", f"/sales-orders/{so['id']}")
    assert c == 200, full
    rolls = [r for a in full.get("allocations") or [] for r in a.get("rolls") or []]
    c, tasks = u["wh"].call("GET", "/outbound/tasks")
    tl = [t for t in tasks if t.get("order_id") == so["id"]]
    assert tl and rolls, ("tugas/alokasi tidak terbentuk", tl, rolls)
    by_wh = {t["warehouse_id"]: t for t in tl}
    for r in rolls:
        roll = DB.inventory_rolls.find_one({"id": r["roll_id"]}, {"_id": 0, "warehouse_id": 1})
        c, b = u["wh"].call("POST", f"/outbound/tasks/{by_wh[roll['warehouse_id']]['id']}/scan-pick",
                            params={"actual_qty": r["length"], "roll_id": r["roll_id"]})
        assert c == 200, (r, b)
    c, b = u["whadm"].call("POST", f"/outbound/so/{so['id']}/loading-check/override",
                           {"reason": "uji F-10 tanpa perangkat RFID - validasi manual"})
    assert c in (200, 400), b
    fresh = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "grand_total": 1, "number": 1, "order_number": 1})
    return {**so, **fresh}, tl


def _dispatch(u, tasks):
    out = []
    for t in tasks:
        out.append(u["wh"].call("POST", f"/outbound/tasks/{t['id']}/dispatch"))
    return out


def _pay(u, so, amount):
    c, b = u["fin"].call("POST", "/ar-receipts", {
        "customer_id": CUST, "amount": round(amount, 2), "method": "transfer", "entity_id": ENT,
        "notes": "uji F-10", "allocations": [{"order_id": so["id"], "amount": round(amount, 2)}]})
    assert c == 200, b
    return b


def test_cbd_belum_bayar_tertahan_lalu_lunas_boleh_kirim_dan_alasan_tampil_di_gudang(u):
    so, tasks = _ready_to_ship(u, "CBD")
    c, b = _dispatch(u, tasks)[0]
    assert c == 409, b                                                       # dulu 200 (SJ terbit tanpa bayar)
    assert "Tertahan pembayaran" in b["detail"] and "CBD" in b["detail"], b
    assert DB.shipments.count_documents({"order_id": so["id"]}) == 0

    c, g = u["wh"].call("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
    assert c == 200 and g["blocked"] and g["dp_percent"] == 100 and abs(g["required"] - so["grand_total"]) < 0.01, g
    c, ts = u["wh"].call("GET", "/outbound/tasks")                          # Barang Keluar: alasan tampil di daftar
    row = next(t for t in ts if t["id"] == tasks[0]["id"])
    assert row["payment_hold"]["blocked"] and "kurang" in row["payment_hold"]["message"], row["payment_hold"]
    c, desk = u["whadm"].call("GET", "/warehouse-admin/desk")                 # Meja Admin Gudang
    out = next(q for q in desk["queues"] if q["id"] == "outbound")
    r = next(x for x in out["rows"] if x["ref_id"] == tasks[0]["id"])
    assert r["badge"] == "tertahan bayar" and r["payment_blocked"] and "tertahan bayar CBD" in r["subtitle"], r
    c, me = u["wh"].call("GET", "/desks/me")                                 # Meja Saya Staf Gudang
    q = next(q for q in me["queues"] if q["id"] == "tugas_wms")
    r = next(x for x in q["rows"] if x["ref_id"] == tasks[0]["id"])
    assert r["badge"] == "tertahan bayar", r
    c, tr = u["fin"].call("GET", "/desks/so-tracker", params={"desk": "finance"})   # pelacak: bola di Finance
    assert c == 200, tr
    t = next((x for x in tr["rows"] if x["id"] == so["id"]), None)
    assert t and t["owner_roles"] == ["finance"] and t["can_act"] and "termin CBD" in t["next_step"], t

    _pay(u, so, so["grand_total"] / 2)
    c, b = _dispatch(u, tasks)[0]
    assert c == 409 and "kurang" in b["detail"], b                           # setengah belum cukup untuk CBD
    _pay(u, so, so["grand_total"] / 2)
    for c, b in _dispatch(u, tasks):
        assert c == 200, b
    assert DB.shipments.count_documents({"order_id": so["id"]}) == len(tasks)


def test_dp50_49_persen_tertahan_50_persen_boleh(u):
    so, tasks = _ready_to_ship(u, "DP50")
    _pay(u, so, so["grand_total"] * 0.49)
    c, b = _dispatch(u, tasks)[0]
    assert c == 409 and "50%" in b["detail"], b
    _pay(u, so, so["grand_total"] * 0.01 + 1)
    c, g = u["wh"].call("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
    assert not g["blocked"] and g["shortfall"] == 0, g
    for c, b in _dispatch(u, tasks):
        assert c == 200, b


def test_pengecualian_berizin_alasan_wajib_teraudit_dan_bisa_dicabut(u):
    so, tasks = _ready_to_ship(u, "CBD")
    path = f"/sales-orders/{so['id']}/dispatch-payment-release"
    c, b = u["wh"].call("POST", path, {"reason": "gudang ingin kirim"})
    assert c == 403, b                                                       # gudang tidak memegang izin
    c, b = u["sales"].call("POST", path, {"reason": "sales ingin kirim"})
    assert c == 403, b
    c, b = u["fin"].call("POST", path, {"reason": "ok"})
    assert c == 400 and "Alasan" in b["detail"], b                           # alasan wajib
    c, b = u["fin"].call("POST", path, {"reason": "Pelanggan lama, transfer sore ini - bukti menyusul"})
    assert c == 200 and b["released"] and not b["blocked"], b
    assert b["released"]["by_role"] == "finance" and b["released"]["shortfall_at_release"] > 0, b
    assert DB.audit_logs.find_one({"action": "dispatch_payment_released", "entity_id": so["id"]}), "audit hilang"
    c, b = u["fin"].call("POST", path, {"reason": "Pelanggan lama, transfer sore ini"})
    assert c == 409, b                                                       # tidak dobel

    c, b = u["mgr"].call("POST", path + "/revoke", {"reason": "Transfer batal, tahan dulu"})
    assert c == 200 and b["blocked"] and not b["released"], b
    assert DB.audit_logs.find_one({"action": "dispatch_payment_release_revoked", "entity_id": so["id"]})
    c, b = _dispatch(u, tasks)[0]
    assert c == 409, b                                                       # dicabut → tertahan lagi

    c, b = u["mgr"].call("POST", path, {"reason": "Disetujui direksi - pelanggan prioritas"})
    assert c == 200, b
    for c, b in _dispatch(u, tasks):
        assert c == 200, b
    hist = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "dispatch_payment_release_history": 1})
    assert len(hist["dispatch_payment_release_history"]) == 1, hist


def test_gerbang_dapat_dimatikan_per_pt_di_pusat_pengaturan(u):
    so, tasks = _ready_to_ship(u, "CBD")
    key = "finance.dispatch_payment_gate"
    c, b = u["adm"].call("PUT", "/config/values", {"items": [{
        "key": key, "value": "off", "scope_type": "entity", "scope_id": ENT, "reason": "uji F-10 matikan gerbang"}]})
    assert c == 200, b
    try:
        c, g = u["wh"].call("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
        assert c == 200 and not g["applies"] and g["mode"] == "off", g
        for c, b in _dispatch(u, tasks):
            assert c == 200, b
    finally:
        c, b = u["adm"].call("POST", "/config/values/clear", {"key": key, "scope_type": "entity", "scope_id": ENT,
                                                             "reason": "uji F-10 kembalikan"})
        assert c == 200, b
    c, g = u["wh"].call("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
    assert g["mode"] == "block", g


def test_termin_kredit_tidak_tertahan(u):
    so, tasks = _ready_to_ship(u, "NET30")
    c, g = u["wh"].call("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
    assert c == 200 and not g["applies"] and not g["blocked"], g
    for c, b in _dispatch(u, tasks):
        assert c == 200, b
