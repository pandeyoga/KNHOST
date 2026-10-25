"""Keputusan pemilik 26 Okt (audit UI tahap 2) — D4 sisa lintas wilayah: uji lewat HTTP (butuh server backend terbaru).

Dijalankan koordinator setelah restart backend (data acuan `scripts/dev_restore_demo.sh`):
  cd /app/backend && python -m pytest tests/test_decisions_d4_http.py -p no:randomly -n 0 -q

* K-03 — `/sales-orders/stats/summary` `by_status[*].grand_total` (kartu tahap layar Pesanan) = Σ grand_total daftar.
* K-03 — `/sales-orders/{id}/verification` `order_preview.totals`: bruto − diskon = net; net + PPN = total (PPN di luar
  harga); membawa `dpp`, `dpp_nilai_lain`, `ppn_mode`.
* K-03 — antrean SO/PO Meja Admin Sales / Finance / Admin Gudang berlabel "Total (termasuk PPN)" & nilai = grand_total.
* K-01 — `/sales/kpi` (Performa Saya) piutang & lewat tempo = `/ar/aging?sales_id=` (definisi layar Piutang).
Semua uji hanya MEMBACA (tanpa menulis data).
"""
import os

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
TOTAL_LABEL = "Total (termasuk PPN)"


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


ADMIN = _login("admin@kainnusantara.id")


def _get(path, h=ADMIN, **params):
    r = requests.get(f"{BASE}{path}", headers=h, params=params or None, timeout=120)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r.json()


def _grand(o):
    g = o.get("grand_total")
    return float(g if g is not None else (o.get("total_amount") or 0))


# ─── K-03 — kartu tahap layar Pesanan ──────────────────────────────────────────────────────────────────────────
def test_k03_stats_by_status_grand_total_equals_list():
    s = _get("/sales-orders/stats/summary")
    per: dict = {}
    page, n = 1, 0
    while True:
        env = _get("/sales-orders", page=page, page_size=200)
        for o in env["items"]:
            per[o.get("status")] = per.get(o.get("status"), 0.0) + _grand(o)
            n += 1
        if not env.get("has_more"):
            break
        page += 1
    assert n == s["total_orders"], (n, s["total_orders"])
    for st, v in s["by_status"].items():
        assert "grand_total" in v and "total_amount" in v, (st, v)
        assert abs(v["grand_total"] - round(per.get(st, 0.0), 2)) < 1, (st, v["grand_total"], per.get(st))


# ─── K-03 — pratinjau verifikasi & antrean meja ────────────────────────────────────────────────────────────────
def _queues(path):
    return {q["id"]: q for q in _get(path).get("queues") or []}


def test_k03_verification_preview_totals_consistent():
    sa = _queues("/sales-admin/desk")
    rows = sa["perlu_verifikasi"]["rows"][:8]
    assert rows, "antrean perlu_verifikasi kosong — cek data acuan"
    for row in rows:
        t = _get(f"/sales-orders/{row['ref_id']}/verification")["order_preview"]["totals"]
        for k in ("gross_subtotal", "net_subtotal", "discount_total", "dpp", "dpp_nilai_lain", "ppn_mode",
                  "ppn_amount", "ppn_rate", "grand_total", "is_pkp"):
            assert k in t, (row["number"], k)
        assert abs(t["gross_subtotal"] - t["discount_total"] - t["net_subtotal"]) < 0.02, (row["number"], t)
        if t["ppn_amount"] > 0 and t["ppn_mode"] == "excluded":
            assert abs(t["net_subtotal"] + t["ppn_amount"] - t["grand_total"]) < 0.02, (row["number"], t)
        assert t["dpp_nilai_lain"] in (True, False, None)


def test_k03_desk_so_po_queues_labelled_and_valued_incl_ppn():
    sa = _queues("/sales-admin/desk")
    fin = _queues("/finance/desk")
    wh = _queues("/warehouse-admin/desk")
    targets = [(sa, q) for q in ("perlu_verifikasi", "siap_dikonfirmasi", "menunggu_manajer", "siap_cetak_dokumen",
                                 "harga_ditolak")] + [(fin, "siap_faktur_pajak"), (fin, "sample_acc_bayar"), (wh, "inbound")]
    checked = 0
    for desk, qid in targets:
        assert desk[qid]["value_label"] == TOTAL_LABEL, (qid, desk[qid]["value_label"])
        coll = "purchase_orders" if qid == "inbound" else "sales_orders"
        for r in desk[qid]["rows"][:10]:
            doc = DB[coll].find_one({"id": r["ref_id"]}, {"_id": 0, "grand_total": 1, "total_amount": 1, "total": 1})
            assert doc, (qid, r["ref_id"])
            g = doc.get("grand_total")
            want = float(g if g is not None else (doc.get("total_amount") or doc.get("total") or 0))
            assert abs(r["value"] - round(want, 2)) < 0.01, (qid, r["number"], r["value"], want)
            checked += 1
    assert checked > 0, "tidak ada baris SO/PO di meja — cek data acuan"
    assert sa["perlu_dipenuhi"]["value_label"] == "Kurang"           # antrean non-dokumen tidak berubah


# ─── K-01 — Performa Saya = layar Piutang ─────────────────────────────────────────────────────────────────────
def test_k01_sales_kpi_ar_and_overdue_equal_aging_per_sales():
    sales_ids = DB.customers.distinct("assigned_sales_id", {"entity_id": ENT, "assigned_sales_id": {"$nin": [None, ""]}})
    assert sales_ids, "tidak ada pelanggan ber-sales di data acuan"
    for sid in sales_ids:
        k = _get("/sales/kpi", sales_id=sid, entity_id=ENT)
        a = _get("/ar/aging", sales_id=sid)["totals"]
        assert abs(k["ar_outstanding"] - a["total"]) < 1, (sid, k["ar_outstanding"], a["total"])
        assert abs(k["overdue_amount"] - a["overdue"]) < 1, (sid, k["overdue_amount"], a["overdue"])
