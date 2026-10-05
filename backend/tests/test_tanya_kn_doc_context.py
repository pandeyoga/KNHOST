"""Tanya dari Dokumen — get_document untuk retur, tagihan supplier, order makloon + batas hak akses."""
import requests

BASE = "http://localhost:8001/api"


def _s(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


def _doc(s, dt, number):
    return s.post(f"{BASE}/ai/tools/get_document", json={"doc_type": dt, "number": number}, timeout=30)


def test_vendor_bill_has_payment_summary():
    d = _doc(_s("admin@kainnusantara.id"), "vendor_bill", "VB-00006").json()["document"]
    assert {"grand_total", "amount_paid", "outstanding", "payment_status", "bill_date"} <= d.keys()
    assert abs(d["grand_total"] - d["amount_paid"] - d["outstanding"]) < 0.01


def test_returns_and_makloon_documents():
    s = _s("admin@kainnusantara.id")
    sr = _doc(s, "sales_return", "SRET-00001").json()["document"]
    assert sr["number"] == "SRET-00001" and "milestones" in sr and sr["items"]
    pr = _doc(s, "purchase_return", "PRET-00002").json()["document"]
    assert pr["number"] == "PRET-00002" and "reason" in pr
    mk = _doc(s, "makloon_order", "MKO-00001").json()["document"]
    assert mk["steps"] and "stage_label" in mk["steps"][0] and "tariff" not in mk["steps"][0]


def test_sales_role_cannot_open_supplier_documents():
    # makloon_order.view memang dimiliki sales (pantau produksi) — Tanya KN mengikuti izin layar yang sama.
    s = _s("sales@kainnusantara.id")
    for dt, n in (("vendor_bill", "VB-00006"), ("purchase_return", "PRET-00002")):
        r = _doc(s, dt, n)
        assert r.status_code == 400 and "tidak tersedia" in r.json()["detail"], (dt, r.text)


def test_new_context_types_accepted():
    import sys
    sys.path.insert(0, "/app/backend")
    from services.ai_chat_service import context_prefix
    for t in ("sales_return", "purchase_return", "vendor_bill", "makloon_order"):
        assert "DOC-1" in context_prefix({"type": t, "id": "x1", "label": "DOC-1"})
