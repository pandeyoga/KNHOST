"""Keputusan pemilik 26 Okt (audit UI tahap 2) — D1 Keuangan: uji tingkat layanan (tanpa HTTP).

* K-15 — tutup buku DIBLOKIR saat Suspense ≠ 0; hanya admin menembus dengan alasan ≥ 5 huruf (tercatat di record).
* K-01 — piutang Control Tower/Beranda = SEMUA pelanggan dari laporan aging (sub-buku), rincian per sales + "Tanpa sales".
* K-02 — "Kas & Bank" = saldo buku besar akun kas+bank; transaksi kas tanpa rekening dihitung sebagai penjelas selisih.
* K-07 — posisi bersih dua arah per pasangan PT (netting) = angka utama; bruto per arah tetap rincian.
* K-03 — PDF: DPP (harga sebelum PPN) · DPP nilai lain (11/12) · PPN · Total (termasuk PPN); Pusat Dokumen = total ber-PPN.

Memakai event loop BERSAMA `tests/_shared_loop.py`; data uji berawalan TEST_D1_ + akhiran acak, dibersihkan per uji.
Jalankan: cd /app/backend && python -m pytest tests/test_decisions_d1_finance.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6]


# ─── K-15 — gerbang Suspense tutup buku ────────────────────────────────────────────────────────────────────────
def _fake_suspense(monkeypatch, value):
    from services import gl_service

    async def fake(entity_id, as_of=""):
        return value
    monkeypatch.setattr(gl_service, "suspense_balance", fake)


def test_k15_gate_rules(monkeypatch):
    from services import closing_service as cs
    _fake_suspense(monkeypatch, 0.0)
    assert run(cs.check_suspense_gate("ent_x", "2019-03-31")) is None          # nol → lolos tanpa alasan
    _fake_suspense(monkeypatch, 1500.0)
    with pytest.raises(cs.SuspenseNotZero) as e:
        run(cs.check_suspense_gate("ent_x", "2019-03-31"))
    assert "Suspense" in str(e.value) and e.value.balance == 1500.0
    with pytest.raises(cs.SuspenseOverrideForbidden):                          # alasan dari non-admin
        run(cs.check_suspense_gate("ent_x", "2019-03-31", "salah posting bank", can_override=False))
    with pytest.raises(ValueError) as e2:                                       # < 5 huruf
        run(cs.check_suspense_gate("ent_x", "2019-03-31", "abc", can_override=True))
    assert not isinstance(e2.value, cs.SuspenseNotZero)
    ok = run(cs.check_suspense_gate("ent_x", "2019-03-31", "  mutasi bank belum dikenali  ", can_override=True,
                                    actor_name="Admin"))
    assert ok["reason"] == "mutasi bank belum dikenali" and ok["suspense_balance"] == 1500.0 and ok["by"] == "Admin"


def test_k15_close_period_blocked_then_admin_override_recorded(monkeypatch):
    from services import closing_service as cs
    eid = f"ent_TEST_D1_{TAG}"
    actor = {"name": "TEST_D1 Admin", "role": "admin"}
    _fake_suspense(monkeypatch, -2500.0)
    try:
        pv = run(cs.preview("month", "2019-03", eid))
        assert pv["suspense_blocks_close"] is True and pv["suspense_override_min_len"] == 5
        with pytest.raises(cs.SuspenseNotZero):
            run(cs.close_period("month", "2019-03", actor, eid))
        assert DB.period_closings.count_documents({"entity_id": eid}) == 0       # tidak ada penutupan lahir
        assert DB.period_close_locks.count_documents({"_id": eid}) == 0          # kunci dilepas
        rec = run(cs.close_period("month", "2019-03", actor, eid, suspense_override_reason="selisih kurs belum diklasifikasi",
                                  can_override_suspense=True))
        assert rec["status"] == "closed"
        assert rec["suspense_override"]["reason"] == "selisih kurs belum diklasifikasi"
        assert rec["suspense_override"]["suspense_balance"] == -2500.0
        saved = DB.period_closings.find_one({"id": rec["id"]}, {"_id": 0})
        assert saved["suspense_override"]["by"] == "TEST_D1 Admin"
        # Suspense nol → penutupan biasa, tanpa catatan tembus.
        _fake_suspense(monkeypatch, 0.0)
        rec2 = run(cs.close_period("month", "2019-04", actor, eid))
        assert rec2["suspense_override"] is None
    finally:
        DB.period_closings.delete_many({"entity_id": eid})
        DB.journal_entries.delete_many({"entity_id": eid})
        DB.period_close_locks.delete_many({"_id": eid})


# ─── K-01 — piutang semua pelanggan (sumber layar Piutang) ────────────────────────────────────────────────────
def test_k01_ar_all_customers_uses_aging_and_groups_without_sales(monkeypatch):
    from services import ar_aging_service as aging
    from services import home_service as hs
    calls = []

    async def fake_aging(entity_id=None, sales_id=None, as_of=None):
        calls.append(entity_id)
        return {"totals": {"total": 2000.0, "overdue": 1193.25, "ar_ledger": 1200.0, "exposure": 800.0,
                           "customers": 3},
                "customers": [
                    {"customer_id": "c1", "assigned_sales_id": "u1", "assigned_sales_name": "Budi",
                     "outstanding": 500.0, "overdue": 100.0},
                    {"customer_id": "c2", "assigned_sales_id": "", "assigned_sales_name": "",
                     "outstanding": 1193.25, "overdue": 1093.25},
                    {"customer_id": "c3", "assigned_sales_id": "u1", "assigned_sales_name": "Budi",
                     "outstanding": 306.75, "overdue": 0.0}]}
    monkeypatch.setattr(aging, "aging_report", fake_aging)
    out = run(hs.ar_all_customers("ent_ksc"))
    assert calls == ["ent_ksc"]
    assert out["outstanding"] == 2000.0 and out["overdue"] == 1193.25
    assert out["ar_ledger"] == 1200.0 and out["exposure"] == 800.0
    assert out["scope"] == "semua pelanggan" and "sub-buku" in out["source_label"].lower()
    rows = {r["sales_name"]: r for r in out["by_sales"]}
    assert rows["Tanpa sales"]["has_sales"] is False and rows["Tanpa sales"]["overdue_amount"] == 1093.25
    assert rows["Budi"]["ar_outstanding"] == 806.75 and rows["Budi"]["overdue_customers"] == 1
    assert out["by_sales"][0]["sales_name"] == "Tanpa sales"        # urut lewat tempo terbesar dulu
    assert out["overdue_customers"] == 2
    run(hs.ar_all_customers("all"))
    assert calls[-1] is None                                         # mode gabungan → tanpa saringan entitas


# ─── K-02 — posisi kas buku besar + transaksi tanpa rekening ──────────────────────────────────────────────────
def test_k02_cash_position_gl_and_unlinked_transactions():
    from services import bank_service as bs
    eid = f"ent_TEST_D1_{TAG}"
    jes = [{"id": f"je_TEST_D1_{TAG}_{i}", "entity_id": eid, "status": "posted", "date": "2026-10-01T00:00:00",
            "lines": [{"account_code": code, "debit": amt, "credit": 0.0},
                      {"account_code": "3-2900", "debit": 0.0, "credit": amt}]}
           for i, (code, amt) in enumerate([("1-1100", 1_000_000.0), ("1-1110", 250_000.0)])]
    txns = [  # 2 tanpa rekening (kas besar → tidak ada rekening tunggal → belum tertaut), 1 kas kecil terserap rekening
        {"id": f"cash_TEST_D1_{TAG}_a", "entity_id": eid, "cash_type": "kas_besar", "direction": "in", "amount": 300.0},
        {"id": f"cash_TEST_D1_{TAG}_b", "entity_id": eid, "cash_type": "kas_besar", "direction": "out", "amount": 100.0,
         "account_id": ""},
        {"id": f"cash_TEST_D1_{TAG}_c", "entity_id": eid, "cash_type": "kas_kecil", "direction": "in", "amount": 50.0},
        {"id": f"cash_TEST_D1_{TAG}_v", "entity_id": eid, "cash_type": "kas_besar", "direction": "in", "amount": 999.0,
         "status": "void"},
    ]
    acc = {"id": f"bank_TEST_D1_{TAG}", "entity_id": eid, "name": "TEST_D1 Kas Kecil", "account_type": "cash",
           "cash_type": "kas_kecil", "opening_balance": 0}
    DB.journal_entries.insert_many([dict(j) for j in jes])
    DB.cash_transactions.insert_many([dict(t) for t in txns])
    DB.bank_accounts.insert_one(dict(acc))
    try:
        pos = run(bs.cash_position([eid]))
        assert pos["gl_total"] == 1_250_000.0
        assert {a["code"] for a in pos["gl_accounts"]} >= {"1-1100", "1-1110"}
        assert pos["unlinked"] == {"count": 2, "inflow": 300.0, "outflow": 100.0, "net": 200.0}
        empty = run(bs.cash_position([]))                              # cakupan kosong tidak galat
        assert empty["gl_total"] == 0.0 and empty["unlinked"]["count"] == 0
    finally:
        DB.journal_entries.delete_many({"entity_id": eid})
        DB.cash_transactions.delete_many({"entity_id": eid})
        DB.bank_accounts.delete_many({"entity_id": eid})


# ─── K-07 — posisi bersih dua arah ─────────────────────────────────────────────────────────────────────────────
def _ica(rid, role, frm, to, seller, buyer, amt):
    return {"id": rid, "role": role, "entity_id": frm, "from_entity_id": frm, "from_entity_name": f"PT {frm[-6:]}",
            "to_entity_id": to, "to_entity_name": f"PT {to[-6:]}", "seller_entity_id": seller, "buyer_entity_id": buyer,
            "outstanding": amt, "open_count": 1}


def test_k07_net_positions_pure():
    from services.interco_service import net_positions
    a, b = "ent_A", "ent_B"
    rows = [_ica("1", "receivable", a, b, a, b, 1000.0), _ica("2", "payable", b, a, a, b, 1000.0),   # B berutang A
            _ica("3", "receivable", b, a, b, a, 300.0), _ica("4", "payable", a, b, b, a, 300.0)]     # A berutang B
    out = net_positions(rows)
    assert len(out) == 1
    p = out[0]
    assert (p["debtor_entity_id"], p["creditor_entity_id"]) == (b, a)
    assert p["net"] == 700.0 and p["gross_debtor_owes"] == 1000.0 and p["gross_creditor_owes"] == 300.0
    # baris lama tanpa arah eksplisit diturunkan dari peran; satu arah saja → bersih = bruto
    legacy = [{"role": "payable", "from_entity_id": a, "to_entity_id": b, "outstanding": 50.0}]
    assert net_positions(legacy)[0]["net"] == 50.0 and net_positions(legacy)[0]["debtor_entity_id"] == a


def test_k07_summary_net_from_active_entity_perspective():
    from services import interco_service as ics
    a, b = f"ent_TEST_D1a_{TAG}", f"ent_TEST_D1b_{TAG}"
    docs = [  # dokumen terbuka (sumber angka hidup list_accounts): A jual ke B 1.000; B jual ke A 300
        {"id": f"ict_TEST_D1_{TAG}_1", "role": "seller", "seller_entity_id": a, "buyer_entity_id": b, "entity_id": a,
         "status": "received", "grand_total": 1000.0, "settled_amount": 0, "returned_amount": 0},
        {"id": f"ict_TEST_D1_{TAG}_2", "role": "seller", "seller_entity_id": b, "buyer_entity_id": a, "entity_id": b,
         "status": "received", "grand_total": 300.0, "settled_amount": 0, "returned_amount": 0},
    ]
    accs = [_ica(f"ica_TEST_D1_{TAG}_1", "receivable", a, b, a, b, 1000.0),
            _ica(f"ica_TEST_D1_{TAG}_2", "payable", b, a, a, b, 1000.0),
            _ica(f"ica_TEST_D1_{TAG}_3", "receivable", b, a, b, a, 300.0),
            _ica(f"ica_TEST_D1_{TAG}_4", "payable", a, b, b, a, 300.0)]
    DB.interco_transactions.insert_many([dict(d) for d in docs])
    DB.interco_accounts.insert_many([dict(x) for x in accs])
    try:
        sa = run(ics.summary([a], a))
        assert sa["net_receivable"] == 700.0 and sa["net_payable"] == 0.0
        assert sa["total_receivable"] == 1000.0 and sa["total_payable"] == 300.0     # bruto tetap ada (rincian)
        sb = run(ics.summary([b], b))
        assert sb["net_payable"] == 700.0 and sb["net_receivable"] == 0.0
        assert sb["net_pairs"][0]["debtor_entity_id"] == b
    finally:
        DB.interco_transactions.delete_many({"id": {"$in": [d["id"] for d in docs]}})
        DB.interco_accounts.delete_many({"id": {"$in": [x["id"] for x in accs]}})


# ─── K-03 — baris total PDF & ringkasan Pusat Dokumen ─────────────────────────────────────────────────────────
SO_NL = {"number": "KSC/SO-1", "net_subtotal": 202318.4, "dpp": 185458.53, "dpp_nilai_lain": True, "ppn_rate": 12.0,
         "ppn_mode": "excluded", "ppn_amount": 22255.02, "grand_total": 224573.42, "total_amount": 202318.4}


def test_k03_total_rows_nilai_lain_and_plain():
    from services import pdf_resolvers as pr
    rows = pr._total_rows(SO_NL)
    assert [r["label"] for r in rows] == ["DPP (harga sebelum PPN)", "DPP nilai lain (11/12)",
                                          "PPN 12% × DPP nilai lain", "Total (termasuk PPN)"]
    assert rows[0]["value"] == pr.fmt_rp(202318.4) and rows[1]["value"] == pr.fmt_rp(185458.53)
    assert rows[-1]["strong"] and rows[-1]["value"] == pr.fmt_rp(224573.42)
    plain = pr._total_rows({"net_subtotal": 1000, "ppn_rate": 11, "ppn_amount": 110, "grand_total": 1110,
                            "dpp": 1000, "dpp_nilai_lain": False})
    assert [r["label"] for r in plain] == ["DPP (harga sebelum PPN)", "PPN 11%", "Total (termasuk PPN)"]
    assert pr._total_rows({"net_subtotal": 500, "ppn_amount": 0, "grand_total": 500}) == [
        {"label": "Total", "value": pr.fmt_rp(500), "strong": True}]
    inc = pr._total_rows({"net_subtotal": 1110, "ppn_rate": 11, "ppn_amount": 110, "grand_total": 1110,
                          "ppn_mode": "included"})
    assert inc[0]["value"] == pr.fmt_rp(1000) and inc[1]["label"] == "PPN 11% (sudah termasuk dalam harga)"
    # PO lama tanpa bendera: DPP = 11/12 × harga sebelum PPN → dikenali sebagai DPP nilai lain
    po = {"net_subtotal": 120_000_000, "dpp": 110_000_000, "ppn_rate": 12, "ppn_amount": 13_200_000,
          "grand_total": 133_200_000}
    assert [r["label"] for r in pr._total_rows(po)][1] == "DPP nilai lain (11/12)"


def test_k03_invoice_and_tax_invoice_use_same_rows():
    from services import pdf_resolvers as pr
    inv = run(pr.resolve_invoice({**SO_NL, "items": []}, None))
    assert [t["label"] for t in inv["totals"]][-1] == "Total (termasuk PPN)"
    assert any(t["label"] == "DPP nilai lain (11/12)" for t in inv["totals"])
    fp = run(pr.resolve_tax_invoice({**SO_NL, "items": [], "number": "FP-1"}, None))
    assert [t["label"] for t in fp["totals"]] == [t["label"] for t in pr._total_rows(SO_NL)]


def test_k03_document_center_amount_includes_ppn():
    from routers.pdf import _summarize_doc
    s = _summarize_doc({**SO_NL, "customer_name": "Toko", "created_at": "2026-10-25T05:53:59+00:00",
                        "status": "confirmed"})
    assert s["amount"] == 224573.42 and s["amount_includes_ppn"] is True
    assert s["amount_dpp"] == 202318.4 and s["ppn_amount"] == 22255.02 and s["dpp_nilai_lain"] == 185458.53
    # dokumen tanpa grand_total (mis. kwitansi) → rantai lama, tanpa rincian PPN
    r = _summarize_doc({"receipt_number": "AR-1", "amount": 5000})
    assert r["amount"] == 5000 and r["amount_includes_ppn"] is False and r["dpp_nilai_lain"] is None


# ─── K-14 (permintaan D3) — alasan balik jurnal minimal 5 huruf ──────────────────────────────────────────────
def test_k14_gl_reverse_reason_min_five_letters():
    from services import gl_service
    eid = f"ent_TEST_D1_{TAG}"
    je_id = f"je_TEST_D1_{TAG}_rev"
    DB.journal_entries.insert_one({"id": je_id, "entity_id": eid, "status": "posted", "date": "2026-10-01T00:00:00",
                                   "source_type": "manual",
                                   "lines": [{"account_code": "1-1100", "debit": 10.0, "credit": 0.0},
                                             {"account_code": "3-2900", "debit": 0.0, "credit": 10.0}]})
    try:
        with pytest.raises(ValueError) as e:
            run(gl_service.reverse_entry(je_id, "2026-10-26", "abcd", {"name": "TEST_D1"}))
        assert "5 huruf" in str(e.value)
    finally:
        DB.journal_entries.delete_many({"entity_id": eid})
