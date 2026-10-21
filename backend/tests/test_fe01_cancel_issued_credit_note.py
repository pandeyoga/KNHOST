"""FE-01 lanjutan — keputusan owner 2026-10-21: batal item Pesanan Khusus pada SO yang SUDAH TERBIT (dibayar /
berfaktur / pendapatan dijurnal) → baris keluar dari SO dan sistem membuat NOTA KREDIT otomatis berstatus
"Menunggu Finance"; pemegang izin finance_amendment.review_credit_note (bawaan Finance) boleh mengoreksi nilainya, menerbitkan, atau membatalkannya.
Barang baris itu tetap harus belum keluar gudang (roll terpick/terkirim → jalur retur, tidak berubah).

Proses bisnis lewat API (OD → ACC pelanggan → kunci harga → SO → batal item). Status "sudah dibayar" disiapkan
langsung di dokumen SO (fixture: pembayaran penuh) — kwitansi bukan objek uji.
Jalankan: cd /app/backend && python -m pytest tests/test_fe01_cancel_issued_credit_note.py -p no:randomly -n 0 -q
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_fe01_od_cancel_item as fe  # noqa: E402
from test_fe01_od_cancel_item import H, cleanup_od  # noqa: E402,F401 — fixture modul FE-01

BASE, DB = fe.BASE, fe.DB


def _so_paid(H):  # noqa: F811
    od = fe._approved(H, [fe.PA, fe.PB, fe.PC], qtys=(100, 120, 140))
    items = od["items"]
    for it, p, c in zip(items, (fe.PA, fe.PB, fe.PC), (10, 20, 30)):
        fe._decide(it, p, c)
    assert requests.post(f"{BASE}/special-orders/{od['id']}/customer-decision", json={"decision": "acc"},
                         headers=H["admin"]).status_code == 200
    assert requests.post(f"{BASE}/special-orders/{od['id']}/lock-price", json={"margin_pct": 30, "auto_po": False},
                         headers=H["admin"]).status_code == 200
    cv = requests.post(f"{BASE}/special-orders/{od['id']}/convert-to-so", json={}, headers=H["admin"])
    assert cv.status_code == 200, cv.text
    so = cv.json()["sales_order"]
    DB.sales_orders.update_one({"id": so["id"]}, {"$set": {"paid_total": so["grand_total"], "payment_status": "paid"}})
    return od, items, DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})


def _review(h, cn_id, body):
    return requests.post(f"{BASE}/credit-notes/{cn_id}/finance-review", headers=h, json=body)


def test_batal_item_so_terbit_nota_kredit_menunggu_finance_koreksi_terbit_batal(H):  # noqa: F811
    od, (i1, i2, i3), so = _so_paid(H)
    r = fe._cancel(H, od["id"], i2["id"], reason="Pelanggan batal item 2 sesudah bayar")
    assert r.status_code == 200, r.text
    cn = r.json()["credit_note"]
    after = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert fe.PB["id"] not in [i["product_id"] for i in after["items"]]                    # baris keluar dari pengiriman
    doc = DB.credit_notes.find_one({"id": cn["id"]}, {"_id": 0})
    assert doc["status"] == "pending_finance" and doc["source"] == "od_item_cancel" and doc["kind"] == "credit_note"
    assert doc["order_id"] == so["id"] and doc["special_order_id"] == od["id"]
    assert round(doc["gross_amount"], 2) == round(so["grand_total"] - after["grand_total"], 2) > 0
    assert round(doc["excess_payment"], 2) == round(so["grand_total"] - after["grand_total"], 2)   # dibayar penuh
    assert doc["lines"][0]["product_id"] == fe.PB["id"] and doc["revenue_recognized"] is False
    assert "CN-" in doc["number"]
    trail = requests.get(f"{BASE}/amendments/doc/sales_order/{so['id']}", headers=H["admin"]).json()
    assert cn["id"] in {n["id"] for n in trail["notes"]}                                     # tampil di jejak SO

    fin = fe.m._login("finance@kainnusantara.id")
    sales = fe.m._login("sales@kainnusantara.id")
    desk = requests.get(f"{BASE}/finance/desk", headers=fin).json()                         # antrean Meja Finance
    q = next(x for x in desk["queues"] if x["id"] == "nota_batal_item")
    assert any(r.get("credit_note_id") == cn["id"] and r["order_id"] == so["id"] for r in q["rows"])
    assert _review(sales, cn["id"], {"action": "issue"}).status_code == 403                 # bukan Finance
    assert _review(fin, cn["id"], {"action": "adjust", "gross_amount": doc["gross_amount"] - 1000,
                                   "note": "x"}).status_code == 400                          # alasan wajib
    adj = _review(fin, cn["id"], {"action": "adjust", "gross_amount": doc["gross_amount"] - 1000,
                                  "note": "Potongan biaya pembatalan disepakati"})
    assert adj.status_code == 200, adj.text
    a = adj.json()
    assert round(a["gross_amount"], 2) == round(doc["gross_amount"] - 1000, 2) and a["corrections"][0]["reason"]
    assert round(a["net_amount"] + a["ppn_amount"], 2) == round(a["gross_amount"], 2)
    assert _review(fin, cn["id"], {"action": "adjust", "gross_amount": doc["gross_amount"] + 1,
                                   "note": "lebih besar dari nilai baris"}).status_code == 400   # tidak melebihi nilai batal
    iss = _review(fin, cn["id"], {"action": "issue", "note": "OK"})
    assert iss.status_code == 200 and iss.json()["status"] == "issued" and iss.json()["issued_by"]
    assert not iss.json().get("journal_entry_id")                         # pendapatan belum diakui → tanpa jurnal
    assert _review(fin, cn["id"], {"action": "void", "note": "terlambat dibatalkan"}).status_code == 409

    r3 = fe._cancel(H, od["id"], i3["id"], reason="Pelanggan batal item 3 sesudah bayar")
    assert r3.status_code == 200, r3.text
    cn3 = r3.json()["credit_note"]["id"]
    v = _review(fin, cn3, {"action": "void", "note": "Diganti barang lain, tidak ada pengembalian dana"})
    assert v.status_code == 200 and v.json()["status"] == "void" and v.json()["void_reason"]
    assert _review(fin, cn3, {"action": "issue"}).status_code == 409


def test_batal_item_so_terbit_tanpa_pembayaran_tidak_membuat_nota(H):  # noqa: F811
    od = fe._approved(H, [fe.PA, fe.PB], qtys=(100, 200))
    i1, i2 = od["items"]
    fe._decide(i1, fe.PA, 10)
    fe._decide(i2, fe.PB, 30)
    requests.post(f"{BASE}/special-orders/{od['id']}/customer-decision", json={"decision": "acc"}, headers=H["admin"])
    requests.post(f"{BASE}/special-orders/{od['id']}/lock-price", json={"margin_pct": 30, "auto_po": False}, headers=H["admin"])
    so = requests.post(f"{BASE}/special-orders/{od['id']}/convert-to-so", json={}, headers=H["admin"]).json()["sales_order"]
    r = fe._cancel(H, od["id"], i2["id"])
    assert r.status_code == 200, r.text
    assert r.json().get("credit_note") is None                                   # belum terbit → cukup hitung ulang SO
    assert DB.credit_notes.count_documents({"order_id": so["id"]}) == 0


def test_pendapatan_historis_diakui_nota_terbit_berjurnal_dan_kredit_pelanggan(H):  # noqa: F811
    od, (i1, i2, i3), so = _so_paid(H)
    je_id = f"je_TEST_FE01CN_{so['id'][-6:]}"
    DB.journal_entries.insert_one({"id": je_id, "source_type": "sales_order", "source_id": so["id"], "status": "posted",
                                   "entity_id": so.get("entity_id"), "lines": [], "description": "TEST pendapatan historis"})
    cn_id = None
    try:
        r = fe._cancel(H, od["id"], i3["id"], reason="Pelanggan batal item 3 (pendapatan historis)")
        assert r.status_code == 200, r.text
        cn_id = r.json()["credit_note"]["id"]
        assert DB.credit_notes.find_one({"id": cn_id})["revenue_recognized"] is True
        fin = fe.m._login("finance@kainnusantara.id")
        iss = _review(fin, cn_id, {"action": "issue", "note": "Jurnal koreksi pendapatan"})
        assert iss.status_code == 200, iss.text
        doc = iss.json()
        assert doc["status"] == "issued" and doc["accounting"] == "revenue_correction" and doc["journal_entry_id"]
        je = DB.journal_entries.find_one({"id": doc["journal_entry_id"]})
        debit = round(sum(ln["debit"] for ln in je["lines"]), 2)
        assert je["source_type"] == "amendment_credit_note" and debit == round(doc["gross_amount"], 2)
        assert doc["ar_applied"] == 0 and doc["store_credit_amount"] == round(doc["gross_amount"], 2)   # sudah lunas → kredit pelanggan
    finally:
        DB.journal_entries.delete_many({"$or": [{"id": je_id}, {"source_type": "amendment_credit_note", "source_id": cn_id or "-"}]})
        if cn_id:
            DB.store_credit_ledger.delete_many({"ref_id": cn_id})
            DB.store_credits.delete_many({"ref_id": cn_id})
