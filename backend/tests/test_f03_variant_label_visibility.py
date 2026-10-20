"""F-03 (uji pra-UAT 2026-10-21) — grade/LOT/asal tidak boleh bocor ke Sales lewat `variant_label`.

Reproduksi: akun sales `GET /api/products?q=DENIM TENCEL` → "Impor · 01 · A", "Impor · 1 · A · LOT A";
`GET /api/sales-orders/frequent-products` → "Lokal · TAUPE · A". Middleware visibilitas menyamarkan
nama & SKU tetapi tidak `variant_label`. Kini segmen asal/grade/LOT dibuang sesuai field_visibility;
peran berhak (Admin, Admin Sales) tetap menerima label utuh.
Jalankan: cd /app/backend && python -m pytest tests/test_f03_variant_label_visibility.py -p no:randomly -n 0 -q
"""
import os
import re
import sys

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
PW = {"admin@kainnusantara.id": "demo12345", "wh.admin@kainnusantara.id": "demo12345"}
CUST = "cust_toko_kain"
SECRET_KEYS = ("grade", "lot", "origin")
NONE_LABELS = {"", "Tidak ada"}


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PW.get(email, "demo1234")}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _rows(body):
    rows = body.get("items", body) if isinstance(body, dict) else body
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _secret_segments(pid):
    p = DB.products.find_one({"id": pid}, {"_id": 0, "variant_attrs": 1}) or {}
    va = p.get("variant_attrs") or {}
    return {str(va[k]) for k in SECRET_KEYS if va.get(k) not in (None,)} - NONE_LABELS


def _leaks(rows):
    out = []
    for r in rows:
        label, pid = r.get("variant_label"), r.get("id") or r.get("product_id")
        if not label or not pid:
            continue
        segs = label.split(" · ")
        bad = [s for s in segs if s in _secret_segments(pid) or re.match(r"^LOT\s+\S+$", s)]
        if bad:
            out.append((pid, label, bad))
    return out


ENDPOINTS = ["/products?q=DENIM TENCEL&limit=200", "/products?limit=200",
             f"/sales-orders/frequent-products?customer_id={CUST}&limit=24"]


@pytest.fixture(scope="module")
def sales():
    return _login("sales@kainnusantara.id")


def test_sales_tidak_menerima_grade_lot_asal_di_variant_label(sales):
    seen = 0
    for ep in ENDPOINTS:
        r = requests.get(f"{BASE}{ep}", headers=sales, timeout=60)
        assert r.status_code == 200, (ep, r.text[:200])
        rows = _rows(r.json())
        seen += sum(1 for x in rows if x.get("variant_label"))
        assert not _leaks(rows), (ep, _leaks(rows)[:5])
    assert seen, "tidak ada baris ber-variant_label — data acuan belum di-restore?"
    # warna (segmen yang bukan rahasia) tetap ada
    rows = _rows(requests.get(f"{BASE}/products?q=DENIM TENCEL TAUPE&limit=50", headers=sales, timeout=60).json())
    taupe = [x for x in rows if (DB.products.find_one({"id": x["id"]}, {"_id": 0, "variant_attrs": 1}) or {})
             .get("variant_attrs", {}).get("color") == "TAUPE"]
    assert taupe and all(x["variant_label"] == "TAUPE" for x in taupe), [x.get("variant_label") for x in taupe]


@pytest.mark.parametrize("email", ["admin@kainnusantara.id", "salesadmin@kainnusantara.id"])
def test_peran_berhak_tetap_menerima_label_lengkap(email):
    h = _login(email)
    for ep in ENDPOINTS:
        r = requests.get(f"{BASE}{ep}", headers=h, timeout=60)
        assert r.status_code == 200, (ep, r.text[:200])
        for x in _rows(r.json()):
            if x.get("variant_label") and x.get("id", "").startswith("prod"):
                full = DB.products.find_one({"id": x["id"]}, {"_id": 0, "variant_label": 1})
                assert x["variant_label"] == full["variant_label"], (ep, x["id"])


# ─── Unit: redact() pada label varian ────────────────────────────────────────────────────────────

def _redact(row, hidden):
    from services.field_visibility import redact
    return redact(row, set(hidden))


IMPORT_LOT = {"product_id": "prod_x", "variant_label": "Impor · 1 · A · LOT A",
              "variant_attrs": {"origin": "Impor", "color": "1", "grade": "A", "customer": "Tidak ada", "lot": "LOT A"}}


@pytest.mark.parametrize("hidden,expected", [
    (("grade", "lot", "origin"), "1"),
    (("grade",), "Impor · 1 · LOT A"),
    (("lot",), "Impor · 1 · A"),
    (("origin",), "1 · A · LOT A"),
])
def test_redact_label_mengikuti_atribut_tersembunyi(hidden, expected):
    assert _redact(dict(IMPORT_LOT), hidden)["variant_label"] == expected


def test_redact_label_tanpa_variant_attrs_dan_warna_mirip_grade():
    # baris ringan tanpa variant_attrs: grade dari SKU, LOT dari pola "LOT x"
    row = {"product_id": "prod_y", "sku": "KNWVN0015-L-TAUX-XB-XX-LB", "variant_label": "Lokal · B · B · LOT B"}
    out = _redact(row, ("grade", "lot"))
    assert out["variant_label"] == "Lokal · B", out          # warna "B" tetap, grade "B" & LOT dibuang
    assert _redact(dict(IMPORT_LOT), ())["variant_label"] == IMPORT_LOT["variant_label"]
