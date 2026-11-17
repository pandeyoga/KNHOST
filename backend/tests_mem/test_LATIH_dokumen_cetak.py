"""Pelatihan Keuangan 18 Nov — audit DOKUMEN CETAK (docs/pelatihan/2026-11-18_keuangan/uji/dokumen/).

Perbaikan yang dijaga di sini:
  1. Nominal bersen dicetak apa adanya ("Rp 3.381.337,50") dan terbilang ikut membaca sen; dulu pembulatan bankir
     mencetak "Rp 3.381.338" dengan terbilang "… tiga puluh tujuh rupiah".
  2. Teks footer naskah di dalam string CSS: "&" dan tanda kutip tercetak apa adanya (dulu "&amp;", "&#34;").
  3. Surat Jalan / Daftar Kemasan / Surat Pengambilan: entri scan `dispatch` tidak menggandakan roll; nomor roll (RL-…)
     bukan id internal; tanggal & pembuat SJ dari dokumen pengiriman.
  4. Tagihan Supplier: baris barang, DPP ≠ 0, nomor PO (bukan id), jatuh tempo, terbayar & sisa.
  5. Faktur Komersial: jatuh tempo, sudah dibayar, sisa tagihan (dari baris tagihan Umur Piutang).
  6. Judul berbahasa Indonesia (Kwitansi, Tagihan Supplier).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


# ── 1. uang & terbilang ──────────────────────────────────────────────────────────────────────────────────────────────
def test_fmt_rp_mencetak_sen_bila_ada_tanpa_pembulatan_bankir():
    from services.pdf_engine import fmt_rp, set_document_currency
    set_document_currency("IDR")
    assert fmt_rp(3381337.5) == "Rp 3.381.337,50"
    assert fmt_rp(3381336.5) == "Rp 3.381.336,50"      # dulu "Rp 3.381.336" (setengah ke genap)
    assert fmt_rp(2792395.8333) == "Rp 2.792.395,83"
    assert fmt_rp(3381337) == "Rp 3.381.337"
    assert fmt_rp(3381337.004) == "Rp 3.381.337"
    assert fmt_rp(0) == "Rp 0" and fmt_rp(None) == "Rp 0" and fmt_rp("x") == "Rp 0"
    assert fmt_rp(-1500.5) == "-Rp 1.500,50" and fmt_rp(-0.001) == "Rp 0"
    assert fmt_rp(1234.5, "USD") == "$ 1,234.50"


def test_terbilang_membaca_sen_dan_sama_dengan_angka():
    from services.pdf_engine import terbilang
    assert terbilang(3381337.5) == ("Tiga juta tiga ratus delapan puluh satu ribu tiga ratus tiga puluh tujuh rupiah "
                                    "lima puluh sen")
    assert terbilang(3268672.5).endswith("enam ratus tujuh puluh dua rupiah lima puluh sen")
    assert terbilang(1864800) == "Satu juta delapan ratus enam puluh empat ribu delapan ratus rupiah"
    assert terbilang(0.07) == "Nol rupiah tujuh sen"
    assert terbilang(None) == "Nol rupiah"
    assert terbilang(1000.999) == "Seribu satu rupiah"   # dibulatkan ke sen dulu: Rp 1.001,00


# ── 2. footer & urutan terbilang ─────────────────────────────────────────────────────────────────────────────────────
def test_footer_naskah_aman_di_css_dan_terbilang_di_bawah_total():
    from services.pdf_engine import render_html
    from services.pdf_service import DEFAULT_TEMPLATE_CFG, merge_cfg
    cfg = merge_cfg(DEFAULT_TEMPLATE_CFG, {"footer_text": 'Kain & Co "Asli" </style><b>x'})
    html = render_html(cfg, {"company_name": "PT Uji", "address": "-"}, {
        "title": "Faktur", "number": "F-1", "totals": [{"label": "Total", "value": "Rp 1", "strong": True}],
        "terbilang": "Satu rupiah", "extra_tables": [{"title": "Jatuh Tempo & Sisa Tagihan", "columns": [], "items": []}]})
    assert 'content: "Kain & Co \\"Asli\\" \\3C /style\\3E \\3C b\\3E x"' in html
    assert "&amp;" not in html.split("</style>")[0] and html.count("</style>") == 1
    assert html.index("Total</span>") < html.index("Terbilang:") < html.index("Jatuh Tempo &amp; Sisa Tagihan")


# ── 3. dokumen gudang ────────────────────────────────────────────────────────────────────────────────────────────────
async def _kirim_satu_roll(db):
    await db.wms_tasks.insert_one({
        "id": "wms_latih_1", "order_id": "so_latih_1", "flow_type": "outbound", "product_name": "Kain Uji",
        "sku": "UJI-1", "unit": "yard", "quantity": 117.79, "picked_qty": 117.79, "warehouse_name": "Gudang Uji",
        "status": "dispatched", "scan_log": [
            {"scan_type": "pick", "actual_qty": 117.79, "roll_id": "roll_latih_1", "lot": "LOT-1", "bin_id": "B-1"},
            {"scan_type": "dispatch", "actual_qty": 117.79, "shipment_id": "shp_latih_1", "rolls": ["roll_latih_1"]},
            {"scan_type": "cutting_handoff", "from": "a", "to": "b"}]})
    await db.inventory_rolls.insert_one({"id": "roll_latih_1", "roll_no": "RL-90001", "length_initial": 117.79})
    await db.shipments.insert_one({"id": "shp_latih_1", "order_id": "so_latih_1", "shipment_no": "UJI/SJ-00001",
                                   "created_at": "2026-11-16T20:30:00+00:00", "created_by": "Eko Gudang"})
    return {"id": "so_latih_1", "number": "UJI/SO-00001", "customer_name": "Toko Uji", "status": "done",
            "created_by": "user_sales_01"}


async def test_surat_jalan_satu_roll_sekali_dengan_nomor_roll(db):
    from services import pdf_resolvers as pr
    so = await _kirim_satu_roll(db)
    rows, _ = await pr._wms_scan_rows(db, {"order_id": so["id"]}, "outbound")
    assert len(rows) == 1 and rows[0]["roll_no"] == "RL-90001" and rows[0]["qty"] == 117.79
    sj = await pr.resolve_delivery_note(so, db)
    tot = {t["label"]: t["value"] for t in sj["totals"]}
    assert tot == {"Total Roll": "1", "Total Kuantitas": "117,79 yard"}
    assert sj["number"] == "UJI/SJ-00001" and sj["items"][0]["roll"] == "RL-90001"
    assert sj["date"] == "17 Nov 2026"                       # 03.30 WIB tanggal 17 — dari pengiriman, bukan tanggal cetak
    assert sj["signatures"][-1]["name"] == "Eko Gudang"      # bukan id pengguna pembuat SO
    pl = await pr.resolve_packing_list(so, db)
    assert {t["label"]: t["value"] for t in pl["totals"]}["Total Koli/Roll"] == "1"
    pick = await pr.resolve_picking_list(so, db)
    assert len(pick["items"]) == 1 and pick["items"][0]["roll"] == "RL-90001"


# ── 4. tagihan supplier ──────────────────────────────────────────────────────────────────────────────────────────────
VB = {"id": "vbill_latih", "bill_number": "VB-09001", "supplier_invoice_no": "INV-S-1", "po_id": "po_internal_1",
      "po_number": "KSC/PO-09001", "supplier_id": "sup_tidak_ada", "supplier_name": "Pemasok Uji", "supplier_npwp": "",
      "bill_date": "2026-11-17T07:40:14+00:00", "due_date": "2026-12-17", "status": "posted",
      "payment_status": "partial", "items": [{"sku": "G-1", "product_name": "Grey Poplin", "quantity": 120,
                                              "billed_qty": 120, "unit": "yard", "price": 14000, "line_total": 1680000}],
      "total_amount": 1680000, "dpp": 1540000, "ppn_rate": 12, "ppn_mode": "excluded", "ppn_amount": 184800,
      "tax_snapshot": {"dpp_nilai_lain": True, "dpp_pembilang": 11, "dpp_penyebut": 12}, "grand_total": 1864800,
      "amount_paid": 864800, "outstanding": 1000000}


async def test_tagihan_supplier_lengkap(db):
    from services import pdf_resolvers as pr
    out = await pr.resolve_vendor_bill(dict(VB), db)
    assert out["title"] == "Tagihan Supplier"
    meta = {m["label"]: m["value"] for m in out["meta"]}
    assert meta["Ref PO"] == "KSC/PO-09001" and meta["Jatuh Tempo"] == "17 Des 2026" and meta["NPWP Supplier"] == "-"
    assert out["items"][0]["desc"] == "Grey Poplin" and out["items"][0]["qty"] == "120 yard"
    tot = {t["label"]: t["value"] for t in out["totals"]}
    assert tot["DPP (harga sebelum PPN)"] == "Rp 1.680.000" and tot["DPP nilai lain (11/12)"] == "Rp 1.540.000"
    assert tot["PPN 12% × DPP nilai lain"] == "Rp 184.800" and tot["Total (termasuk PPN)"] == "Rp 1.864.800"
    assert tot["Sudah dibayar"] == "Rp 864.800" and tot["Sisa hutang"] == "Rp 1.000.000"
    # pelunasan lewat kontrabon: `amount_paid` naik, field tersimpan `outstanding`/`payment_status` tertinggal
    lunas = await pr.resolve_vendor_bill({**VB, "status": "paid", "amount_paid": 1864800, "outstanding": 1864800,
                                          "payment_status": "unpaid"}, db)
    tot = {t["label"]: t["value"] for t in lunas["totals"]}
    assert tot["Sisa hutang"] == "Rp 0" and {m["label"]: m["value"] for m in lunas["meta"]}["Status Bayar"] == "paid"
    lama = await pr.resolve_vendor_bill({k: v for k, v in VB.items() if k not in ("items", "po_number")}, db)
    assert lama["items"][0]["net"] == "Rp 1.680.000" and "po_internal_1" not in str(lama)


# ── 5. faktur komersial ──────────────────────────────────────────────────────────────────────────────────────────────
async def test_faktur_jatuh_tempo_dibayar_sisa(db, monkeypatch):
    from services import pdf_resolvers as pr
    from services import report_basis as rb
    await db.customers.insert_one({"id": "cus_latih", "name": "Toko Uji"})
    so = {"id": "so_latih_f", "number": "UJI/SO-00002", "customer_id": "cus_latih", "customer_name": "Toko Uji",
          "status": "done", "payment_status": "partial", "items": [], "grand_total": 3164055, "ppn_amount": 0,
          "paid_total": 1265622, "payment_term_name": "Kredit NET 30 Hari"}

    async def baris(orders, customers, *, per):
        return {"so_latih_f": [{"label": "Surat jalan UJI/SJ-1", "jatuh_tempo": "2026-12-17", "nilai": 3164055,
                                "terbayar": 1265622, "sisa": 1898433}]}
    monkeypatch.setattr(rb, "baris_tagihan", baris)
    inv = await pr.resolve_invoice(dict(so), db)
    meta = {m["label"]: m["value"] for m in inv["meta"]}
    tot = {t["label"]: t["value"] for t in inv["totals"]}
    assert meta["Jatuh Tempo"] == "17 Des 2026"
    assert tot["Sudah dibayar"] == "Rp 1.265.622" and tot["Sisa tagihan"] == "Rp 1.898.433"
    assert [t for t in inv["totals"] if t.get("strong")][-1]["label"] == "Total"   # {{grand_total}} tetap total faktur
    assert inv["extra_tables"][0]["items"][0]["jt"] == "17 Des 2026"
    # pesanan tunai (bukan piutang) → tidak dicetak "Lunas"/sisa
    tunai = await pr.resolve_invoice({**so, "payment_term_code": "tunai"}, db)
    assert not any(t["label"] in ("Sudah dibayar", "Sisa tagihan") for t in tunai["totals"])
    assert "Jatuh Tempo" not in {m["label"] for m in tunai["meta"]} and not tunai["extra_tables"]


# ── 6. judul Indonesia ───────────────────────────────────────────────────────────────────────────────────────────────
async def test_judul_dan_label_berbahasa_indonesia(db):
    from services import pdf_resolvers as pr
    kw = await pr.resolve_ar_receipt({"number": "AR-1", "method": "transfer", "amount": 1000.5, "allocations": []}, db)
    assert kw["title"] == "Kwitansi" and kw["terbilang"] == "Seribu rupiah lima puluh sen"
    assert pr.DOC_REGISTRY["vendor_bill"]["label"] == "Tagihan Supplier"
    assert pr.DOC_REGISTRY["ar_receipt"]["label"] == "Kwitansi Penerimaan"
