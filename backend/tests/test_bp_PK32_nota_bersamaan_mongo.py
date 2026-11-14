"""PK-32 U15 — di MongoDB ASLI (lingkungan A): dua amandemen nota kredit bersamaan atas satu pesanan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan (fixture): pesanan U1 — 100 m × Rp 10.000 = Rp 1.000.000 tanpa PPN, terkirim penuh (jurnal pendapatan
`sales_order` Dr 1-1200 / Cr 4-1000 1.000.000), belum dibayar. Dua amandemen metode nota kredit menunggu persetujuan
(disisipkan langsung: pratinjau menolak dua usulan nota yang menunggu bersamaan), masing-masing −Rp 600.000 pada field
berbeda (harga 10.000 → 4.000 dan diskon baris 0 → 60 %) supaya pemeriksa "nilai dari" tidak menolak yang kedua.

  U15  setujui keduanya serentak → tepat satu nota terbit (600.000), yang lain 409 "…melebihi nilai pesanan…";
       Σ nota kredit pesanan ≤ 1.000.000; amandemen yang kalah kembali menunggu putusan.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KSC = "ent_ksc"
JT = 1_000_000


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dunia():
    tag = uuid.uuid4().hex[:8]
    so, pid = f"so_bp32_{tag}", f"prd_bp32_{tag}"
    DB.sales_orders.insert_one({
        "id": so, "number": f"SO-BP32-{tag}", "entity_id": KSC, "customer_id": f"cus_bp32_{tag}",
        "customer_name": f"Toko BP32 {tag}", "status": "shipped", "tax_override": "non_ppn",
        "items": [{"product_id": pid, "product_name": "Kain BP32", "quantity": 100, "base_quantity": 100,
                   "unit": "meter", "price": 10_000, "subtotal": JT, "line_total": JT, "discount_percent": 0}],
        "total_amount": float(JT), "net_subtotal": float(JT), "ppn_amount": 0.0, "grand_total": float(JT),
        "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30",
        "created_by": "Admin", "created_at": _now()})
    DB.journal_entries.insert_one({
        "id": f"je_bp32_{tag}", "number": f"JE-BP32-{tag}", "date": _now()[:10], "status": "posted",
        "source": "sales_order", "source_type": "sales_order", "source_id": so, "entity_id": KSC,
        "lines": [{"account_code": "1-1200", "debit": float(JT), "credit": 0.0},
                  {"account_code": "4-1000", "debit": 0.0, "credit": float(JT)}],
        "total_debit": float(JT), "total_credit": float(JT), "description": "fixture PK-32 U15",
        "created_by": "uji", "created_at": _now()})
    amds = []
    for field, dari, ke in (("price", 10_000, 4_000), ("discount_percent", 0, 60)):
        aid = f"amd_bp32_{field[:4]}_{tag}"
        DB.doc_amendments.insert_one({
            "id": aid, "number": f"AMD-BP32-{field[:4]}-{tag}", "status": "pending_approval", "method": "credit_note",
            "doc_type": "sales_order", "doc_id": so, "doc_number": f"SO-BP32-{tag}", "entity_id": KSC,
            "approval_permission": "finance_amendment.approve", "proposed_by": "Pengaju BP32",
            "proposed_by_id": f"usr_bp32_{tag}", "reason_code": "price_correction", "reason_label": "Koreksi harga",
            "impact": {"amount_before": float(JT), "amount_after": 400_000.0, "delta": -600_000.0},
            "before": {"grand_total": float(JT), "ppn_amount": 0.0}, "after": {"grand_total": 400_000.0,
                                                                            "ppn_amount": 0.0},
            "changes": [{"product_id": pid, "product_name": "Kain BP32", "field": field, "from": dari, "to": ke}],
            "policy_snapshot": {"admin_approval_above": 0, "issued_doc_policy": "note_only"},
            "requires_approval": True, "created_at": _now(), "proposed_at": _now()})
        amds.append(aid)
    return so, amds


def test_PK32_U15_dua_amandemen_nota_bersamaan():
    h = _login()
    for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
        so, amds = _dunia()
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda a: requests.post(f"{BASE}/amendments/{a}/decision", headers=h, timeout=60,
                                                      json={"action": "approve", "note": "uji U15"}), amds))
        codes = sorted(r.status_code for r in res)
        assert codes == [200, 409], [(r.status_code, r.text[:200]) for r in res]
        kalah = next(r for r in res if r.status_code == 409)
        assert "melebihi nilai pesanan" in kalah.json()["detail"], kalah.text
        notes = list(DB.credit_notes.find({"order_id": so, "status": {"$ne": "void"}}))
        assert len(notes) == 1 and notes[0]["gross_amount"] == 600_000, notes
        assert sum(n["gross_amount"] for n in notes) <= JT
        st = sorted(DB.doc_amendments.find_one({"id": a})["status"] for a in amds)
        assert st == ["applied", "pending_approval"], st
        order = DB.sales_orders.find_one({"id": so})
        assert not order.get("credit_note_lock"), order.get("credit_note_lock")
