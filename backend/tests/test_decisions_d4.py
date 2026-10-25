"""Keputusan pemilik 26 Okt (audit UI tahap 2) — D4 sisa lintas wilayah: uji tingkat layanan (tanpa HTTP).

* K-03 — pratinjau pesanan (`so_verify_service.order_preview`): totals membawa bruto · diskon · DPP · DPP nilai lain ·
  mode PPN, sehingga layar bisa menulis Subtotal (bruto) − Diskon = DPP; DPP + PPN = Total (termasuk PPN). Dulu
  "Subtotal" = net_subtotal (sudah dipotong diskon) lalu "Diskon" lagi → diskon tampak terpotong dua kali.
* K-03 — antrean SO/PO di Meja Admin Sales / Finance / Admin Gudang berlabel "Total (termasuk PPN)" dan nilainya
  memang `grand_total` (termasuk PPN), bukan total bruto.
* K-01 — "lewat tempo" `compute_customer_credit` (Performa Saya, papan tim, Customer 360, status kredit) = definisi
  layar Piutang: mulai 1 hari penuh setelah jatuh tempo (dulu sejak detik pertama).

Event loop BERSAMA `tests/_shared_loop.py`; data uji ber-entitas/ber-id `TEST_D4_*` + akhiran acak, dibersihkan per uji.
Jalankan: cd /app/backend && python -m pytest tests/test_decisions_d4.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TOTAL_LABEL = "Total (termasuk PPN)"


def _tag() -> str:
    return uuid.uuid4().hex[:6]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ─── K-03 — pratinjau pesanan: diskon tidak lagi terhitung dua kali ─────────────────────────────────────────────
def _priced_order(monkeypatch, *, mode="excluded", nl=True, tag=""):
    """SO sintetis yang dihitung MESIN HARGA ASLI (`compute_order_pricing`) — hanya setelan pajak yang dipatok."""
    from services import config_service as cs

    async def fake_settings(entity_id=None):
        return {"tax": {"ppn_rate": 12.0, "ppn_mode": mode, "is_pkp": True, "dpp_nilai_lain": nl},
                "sales": {"allow_item_discount": True, "allow_order_discount": True}}
    monkeypatch.setattr(cs, "get_effective_settings", fake_settings)
    raw = [{"product_id": f"TEST_D4_p1_{tag}", "product_name": "Kain uji A", "sku": "UJI-A", "unit": "yard",
            "price": 10000, "quantity": 100, "discount_percent": 10},
           {"product_id": f"TEST_D4_p2_{tag}", "product_name": "Kain uji B", "sku": "UJI-B", "unit": "yard",
            "price": 5000, "quantity": 40}]
    priced = run(cs.compute_order_pricing(raw, f"TEST_D4_ent_{tag}", order_discount_percent=5))
    return {"id": f"TEST_D4_so_{tag}", "number": f"TEST-D4-{tag}", "entity_id": f"TEST_D4_ent_{tag}",
            "customer_name": "Toko Uji D4", "status": "reserved", **priced}


def test_k03_preview_totals_excluded_nilai_lain(monkeypatch):
    from services import so_verify_service as sv
    order = _priced_order(monkeypatch, tag=_tag())
    t = run(sv.order_preview(order))["totals"]
    # Bruto 1.000.000 + 200.000; diskon barang 100.000 + diskon pesanan 5% × 1.100.000 = 55.000.
    assert t["gross_subtotal"] == 1_200_000.0
    assert t["discount_total"] == 155_000.0
    assert t["net_subtotal"] == 1_045_000.0
    assert round(t["gross_subtotal"] - t["discount_total"], 2) == t["net_subtotal"]          # Subtotal − Diskon = DPP
    assert t["dpp_nilai_lain"] is True and t["ppn_mode"] == "excluded"
    assert t["dpp"] == round(1_045_000 * 11 / 12, 2)                                          # DPP nilai lain (11/12)
    assert t["ppn_amount"] == round(t["dpp"] * 0.12, 2)                                       # PPN 12% × DPP nilai lain
    assert round(t["net_subtotal"] + t["ppn_amount"], 2) == t["grand_total"]                  # DPP + PPN = Total
    # Bukti cacat lama: "Subtotal" (= net) − "Diskon" + PPN ≠ Total → diskon dibaca terpotong dua kali.
    old_reading = t["net_subtotal"] - t["discount_total"] + t["ppn_amount"]
    assert abs(old_reading - t["grand_total"]) == t["discount_total"]


def test_k03_preview_totals_included_and_legacy(monkeypatch):
    from services import so_verify_service as sv
    order = _priced_order(monkeypatch, mode="included", nl=False, tag=_tag())
    t = run(sv.order_preview(order))["totals"]
    assert t["ppn_mode"] == "included" and t["dpp_nilai_lain"] is False
    # Harga sudah termasuk PPN: bruto − diskon = Total; DPP (harga sebelum PPN) + PPN = Total.
    assert round(t["gross_subtotal"] - t["discount_total"], 2) == t["grand_total"]
    assert round((t["grand_total"] - t["ppn_amount"]) + t["ppn_amount"], 2) == t["grand_total"]
    assert t["ppn_amount"] > 0
    # Dokumen lama tanpa bendera dpp_nilai_lain / tanpa total bruto: None (layar mengenali sendiri) & bruto = net + diskon.
    legacy = {k: v for k, v in order.items() if k not in ("dpp_nilai_lain", "total_amount")}
    tl = run(sv.order_preview(legacy))["totals"]
    assert tl["dpp_nilai_lain"] is None
    assert tl["gross_subtotal"] == round(tl["net_subtotal"] + tl["discount_total"], 2)


# ─── K-03 — antrean meja: label "Total (termasuk PPN)" & nilainya grand_total ──────────────────────────────────
def _so(ent, tag, suffix, status, *, net=1_000_000.0, ppn=110_000.0, extra=None):
    d = {"id": f"TEST_D4_{suffix}_{tag}", "number": f"TEST-D4-{suffix}-{tag}", "entity_id": ent,
         "customer_id": f"TEST_D4_c_{tag}", "customer_name": "Toko Uji D4", "customer_city": "Bandung",
         "sales_name": "Sales Uji", "status": status, "order_type": "regular",
         "total_amount": net + 200_000.0, "discount_total": 200_000.0, "net_subtotal": net,
         "ppn_amount": ppn, "ppn_rate": 11.0, "grand_total": round(net + ppn, 2), "is_pkp": True,
         "created_at": _iso(datetime.now(timezone.utc) - timedelta(days=2)), "items": []}
    d.update(extra or {})
    return d


def test_k03_work_desk_so_po_queues_total_incl_ppn():
    from services import work_desk_service as wd
    tag = _tag()
    ent = f"TEST_D4_ent_{tag}"
    sos = [_so(ent, tag, "rsv", "reserved"),
           _so(ent, tag, "cfm", "confirmed"),
           _so(ent, tag, "zero", "reserved", extra={"grand_total": 0.0, "ppn_amount": 0.0}),   # diskon 100%
           _so(ent, tag, "smp", "reserved", net=50_000.0, ppn=5_500.0,
               extra={"order_type": "sample", "sample_billing": "paid", "sample_payment_status": "awaiting_approval"})]
    po = {"id": f"TEST_D4_po_{tag}", "po_number": f"TEST-D4-PO-{tag}", "entity_id": ent, "status": "pending",
          "supplier_name": "Supplier Uji", "total_amount": 2_000_000.0, "net_subtotal": 2_000_000.0,
          "ppn_amount": 220_000.0, "grand_total": 2_220_000.0, "items": [],
          "created_at": _iso(datetime.now(timezone.utc) - timedelta(days=1))}
    DB.sales_orders.insert_many([dict(x) for x in sos])
    DB.purchase_orders.insert_one(dict(po))
    actor = {"id": f"TEST_D4_u_{tag}", "name": "Uji D4", "role": "admin"}
    scope = {"entity_id": ent}
    try:
        sa = {q["id"]: q for q in run(wd.sales_admin_desk(actor, scope, [ent]))["queues"]}
        fin = {q["id"]: q for q in run(wd.finance_desk(actor, scope, [ent]))["queues"]}
        wh = {q["id"]: q for q in run(wd.warehouse_admin_desk(actor, scope, [ent]))["queues"]}
        for qid in ("perlu_verifikasi", "siap_dikonfirmasi", "menunggu_manajer", "siap_cetak_dokumen", "harga_ditolak"):
            assert sa[qid]["value_label"] == TOTAL_LABEL, (qid, sa[qid]["value_label"])
        assert fin["siap_faktur_pajak"]["value_label"] == TOTAL_LABEL
        assert fin["sample_acc_bayar"]["value_label"] == TOTAL_LABEL
        assert wh["inbound"]["value_label"] == TOTAL_LABEL
        # antrean non-dokumen tidak ikut berubah label
        assert sa["perlu_dipenuhi"]["value_label"] == "Kurang" and fin["uang_masuk"]["value_label"] == "Nilai"

        ver = {r["number"]: r["value"] for r in sa["perlu_verifikasi"]["rows"]}
        assert ver[f"TEST-D4-rsv-{tag}"] == 1_110_000.0                     # grand_total (DPP 1 jt + PPN), bukan bruto 1,2 jt
        assert ver[f"TEST-D4-zero-{tag}"] == 0.0                            # dulu `grand_total or total_amount` → bruto
        cetak = {r["number"]: r["value"] for r in sa["siap_cetak_dokumen"]["rows"]}
        assert cetak[f"TEST-D4-cfm-{tag}"] == 1_110_000.0
        faktur = {r["number"]: r["value"] for r in fin["siap_faktur_pajak"]["rows"]}
        assert faktur[f"TEST-D4-cfm-{tag}"] == 1_110_000.0
        smp = {r["number"]: r["value"] for r in fin["sample_acc_bayar"]["rows"]}
        assert smp[f"TEST-D4-smp-{tag}"] == 55_500.0
        inbound = {r["number"]: r["value"] for r in wh["inbound"]["rows"]}
        assert inbound[f"TEST-D4-PO-{tag}"] == 2_220_000.0                  # PO termasuk PPN Masukan
        assert wd._doc_total({"total_amount": 9.0}) == 9.0                  # dokumen lama tanpa grand_total
    finally:
        DB.sales_orders.delete_many({"entity_id": ent})
        DB.purchase_orders.delete_many({"entity_id": ent})


# ─── K-01 — "lewat tempo" Performa Saya = definisi layar Piutang (≥ 1 hari) ────────────────────────────────────
def test_k01_overdue_starts_one_full_day_after_due():
    from services import customer_service as cs
    from services import sales_force_service as sf
    from services import ar_aging_service as ag
    tag = _tag()
    ent = f"TEST_D4_ent_{tag}"
    sales_id = f"TEST_D4_sales_{tag}"
    cust = {"id": f"TEST_D4_c_{tag}", "name": "Toko Uji D4", "entity_id": ent, "assigned_sales_id": sales_id,
            "credit_limit": 0, "status": "active", "created_at": _iso(datetime.now(timezone.utc))}
    now = datetime.now(timezone.utc)
    base = {"entity_id": ent, "customer_id": cust["id"], "customer_name": cust["name"], "status": "shipped",
            "payment_status": "unpaid", "payment_term_days": 0, "order_type": "regular", "payments": [],
            "created_at": _iso(now - timedelta(days=5))}
    so_today = {**base, "id": f"TEST_D4_sot_{tag}", "number": f"TEST-D4-T-{tag}", "grand_total": 300_000.0,
                "total_amount": 300_000.0}
    so_late = {**base, "id": f"TEST_D4_sol_{tag}", "number": f"TEST-D4-L-{tag}", "grand_total": 700_000.0,
               "total_amount": 700_000.0}
    # Jatuh tempo = SJ pertama + termin 0 hari: satu jatuh tempo 3 jam lalu (hari H), satu 2 hari lalu.
    sjs = [{"id": f"TEST_D4_sj1_{tag}", "order_id": so_today["id"], "entity_id": ent, "status": "dispatched",
            "created_at": _iso(now - timedelta(hours=3))},
           {"id": f"TEST_D4_sj2_{tag}", "order_id": so_late["id"], "entity_id": ent, "status": "dispatched",
            "created_at": _iso(now - timedelta(days=2, hours=1))}]
    DB.customers.insert_one(dict(cust))
    DB.sales_orders.insert_many([dict(so_today), dict(so_late)])
    DB.shipments.insert_many([dict(x) for x in sjs])
    try:
        cc = run(cs.compute_customer_credit(dict(cust), ent))
        assert cc["ar_outstanding"] == 1_000_000.0
        assert cc["overdue_amount"] == 700_000.0, cc      # hari H (3 jam lewat) BELUM lewat tempo — dulu 1.000.000
        assert cc["max_overdue_days"] == 2
        assert cc["status"] == "warning"
        kpi = run(sf.sales_kpi(sales_id, None, ent))
        assert kpi["overdue_amount"] == 700_000.0         # Performa Saya "Lewat Jatuh Tempo"
        rep = run(ag.aging_report(ent, sales_id))
        assert rep["totals"]["overdue"] == kpi["overdue_amount"]            # = layar Piutang
        assert rep["totals"]["total"] == kpi["ar_outstanding"]
        # Hanya tagihan hari-H: tidak lewat tempo & status kredit tidak "warning" (sama dgn `_credit_status` aging).
        DB.sales_orders.update_one({"id": so_late["id"]}, {"$set": {"payment_status": "paid"}})
        cc2 = run(cs.compute_customer_credit(dict(cust), ent))
        assert cc2["overdue_amount"] == 0.0 and cc2["max_overdue_days"] == 0 and cc2["status"] == "active", cc2
        chk = run(cs.check_credit_for_order(dict(cust), 100_000))
        assert not any("tunggakan" in r for r in chk["reasons"]), chk["reasons"]
    finally:
        DB.customers.delete_many({"id": cust["id"]})
        DB.sales_orders.delete_many({"entity_id": ent})
        DB.shipments.delete_many({"entity_id": ent})
