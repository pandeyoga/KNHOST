"""Tanya KN F5 — pembangun set evaluasi `questions_v1.json` (120 pertanyaan).

Pakai: cd /app/backend && python tools/ai_eval/build_questions.py
Komposisi §9: penjualan 40 · piutang/kas 20 · stok 20 · pembelian/makloon 15 · hak akses 15 · ambigu 10.
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name("questions_v1.json")
P = {"today": "hari ini", "this_week": "minggu ini", "mtd": "bulan ini", "last_month": "bulan lalu", "ytd": "tahun ini",
     "last_30d": "30 hari terakhir", "qtd": "kuartal ini", "last_week": "minggu lalu"}


def per(p):
    return {"preset": p, "from": None, "to": None}


def qm(metrics, group_by=(), period="mtd", compare="none", grain=None, limit=None, scope="active"):
    return {"tool": "query_metrics", "args": {
        "metrics": list(metrics), "group_by": list(group_by), "time_grain": grain, "period": per(period), "compare": compare,
        "filters": [], "sort": {"by": metrics[0], "direction": "desc"} if group_by else None, "limit": limit,
        "include_samples": False, "entity_scope": scope}}


def lr(record_type, period=None, limit=20):
    return {"tool": "list_records", "args": {"record_type": record_type, "period": per(period) if period else None,
                                             "filters": [], "sort": None, "limit": limit}}


def rr(report, period="mtd", top_n=10):
    return {"tool": "run_report", "args": {"report": report, "period": per(period) if period else None, "filters": [],
                                           "as_of": None, "top_n": top_n}}


def build():
    qs = []

    def add(cat, q, exp, role="admin", expect="ok", denied=None):
        qs.append({"id": f"q{len(qs) + 1:03d}", "category": cat, "role": role, "question": q, "expected": exp,
                   "expect": expect, "denied_metrics": denied or []})

    sales_m = {"net_sales": "penjualan bersih", "orders_count": "jumlah pesanan", "qty_sold": "qty terjual",
               "avg_order_value": "rata-rata nilai pesanan", "customers_active": "pelanggan aktif"}
    periods = ["mtd", "last_month", "this_week", "ytd", "last_30d"]
    for i, (m, lab) in enumerate(sales_m.items()):
        p = periods[i]
        add("penjualan", f"Berapa {lab} {P[p]}?", qm([m], period=p))
        add("penjualan", f"{lab.capitalize()} per sales {P[p]}", qm([m], ["sales_person"], p))
        add("penjualan", f"10 pelanggan dengan {lab} terbesar {P[p]}", qm([m], ["customer"], p, limit=10))
        add("penjualan", f"Produk dengan {lab} tertinggi {P[p]}", qm([m], ["product"], p, limit=10))
        add("penjualan", f"Tren {lab} per bulan tahun ini", qm([m], period="ytd", grain="month"))
        add("penjualan", f"{lab.capitalize()} {P[p]} dibanding periode sebelumnya", qm([m], period=p, compare="previous_period"))
        add("penjualan", f"{lab.capitalize()} per kota {P[p]}", qm([m], ["customer_city"], p))
        add("penjualan", f"{lab.capitalize()} per badan usaha {P[p]}", qm([m], ["entity"], p, scope="per_entity"))

    for p in ["mtd", "last_month", "this_week", "ytd"]:
        add("piutang_kas", f"Berapa uang masuk dari pelanggan {P[p]}?", qm(["collections_amount"], period=p))
    for dims, q in [((), "Total piutang saat ini berapa?"), (("customer",), "Piutang per pelanggan"),
                    (("aging_bucket",), "Piutang per umur"), (("sales_person",), "Piutang per sales")]:
        add("piutang_kas", q, qm(["ar_outstanding"], dims, "today"))
    add("piutang_kas", "Berapa piutang yang sudah jatuh tempo?", qm(["ar_overdue"], period="today"))
    add("piutang_kas", "Pelanggan dengan piutang lewat jatuh tempo terbesar", qm(["ar_overdue"], ["customer"], "today", limit=10))
    for rt, q in [("overdue_invoices", "Daftar invoice yang telat bayar"), ("ar_open_items", "Invoice yang belum lunas apa saja?"),
                  ("customer_payments", "Pembayaran pelanggan minggu ini"), ("inactive_customers", "Pelanggan yang sudah lama tidak order")]:
        add("piutang_kas", q, lr(rt, "this_week" if rt == "customer_payments" else None))
    for rep, q, p in [("ar_aging", "Laporan umur piutang", None), ("cash_position", "Posisi kas sekarang", None),
                      ("cashflow_forecast", "Perkiraan arus kas ke depan", None), ("income_statement", "Laba rugi bulan ini", "mtd"),
                      ("ap_aging", "Umur hutang supplier", None), ("daily_brief", "Ringkasan bisnis hari ini", "today")]:
        add("piutang_kas", q, rr(rep, p))

    for dims, q in [((), "Total stok saat ini berapa yard?"), (("product",), "Stok per produk"), (("warehouse",), "Stok per gudang"),
                    (("grade",), "Stok per grade"), (("fabric_type",), "Stok per jenis kain"), (("stock_age_bucket",), "Stok per umur"),
                    (("line_code",), "Stok per lini produk"), (("dye_lot",), "Stok per dye lot")]:
        add("stok", q, qm(["stock_qty"], dims, "today"))
    for m, q in [("stock_rolls", "Berapa roll stok yang ada?"), ("stock_value", "Nilai persediaan per gudang"),
                 ("stock_available_qty", "Stok yang siap dijual berapa?"), ("stock_reserved_qty", "Stok yang sudah dipesan berapa?")]:
        add("stok", q, qm([m], ["warehouse"] if m == "stock_value" else [], "today"))
    for rt, q in [("low_stock", "Produk yang stoknya menipis"), ("slow_stock", "Stok yang lambat laku"),
                  ("stock_rolls", "Daftar roll di gudang"), ("shipments", "Pengiriman minggu ini")]:
        add("stok", q, lr(rt, "this_week" if rt == "shipments" else None))
    for rep, q in [("stock_health", "Kesehatan stok"), ("stock_valuation", "Valuasi persediaan"),
                   ("receiving_today", "Barang masuk hari ini"), ("dispatch_today", "Pengiriman hari ini")]:
        add("stok", q, rr(rep, "today" if rep.endswith("today") else None))

    for p in ["mtd", "last_month", "ytd"]:
        add("pembelian_makloon", f"Nilai pembelian per supplier {P[p]}", qm(["purchase_value"], ["supplier"], p))
    add("pembelian_makloon", "Berapa PO dibuat bulan ini?", qm(["po_count"], period="mtd"))
    add("pembelian_makloon", "Qty barang diterima per gudang bulan ini", qm(["received_qty"], ["warehouse"], "mtd"))
    add("pembelian_makloon", "Hutang ke supplier per supplier", qm(["ap_outstanding"], ["supplier"], "today"))
    add("pembelian_makloon", "Hutang jatuh tempo bulan ini", qm(["ap_due"], period="mtd"))
    for rt, q in [("overdue_purchase_orders", "PO yang terlambat datang"), ("vendor_bills_due", "Tagihan supplier yang jatuh tempo"),
                  ("incoming_goods", "Barang yang akan datang"), ("makloon_orders", "Order makloon yang berjalan"),
                  ("purchase_orders", "Daftar PO bulan ini"), ("goods_receipts", "Penerimaan barang minggu ini")]:
        add("pembelian_makloon", q, lr(rt, {"purchase_orders": "mtd", "goods_receipts": "this_week"}.get(rt)))
    for rep, q in [("supplier_scorecard", "Rapor supplier"), ("makloon_status", "Status makloon")]:
        add("pembelian_makloon", q, rr(rep, "mtd"))

    for role, m, q in [("sales", "gross_margin", "Berapa laba kotor bulan ini?"), ("sales", "gross_margin_pct", "Margin per produk bulan ini"),
                       ("sales", "stock_value", "Nilai persediaan sekarang"), ("finance", "gross_margin", "Laba kotor per pelanggan"),
                       ("warehouse_admin", "gross_margin", "Margin bulan ini berapa?"), ("sales_admin", "gross_margin_pct", "Persentase margin per sales"),
                       ("md", "gross_margin", "Laba kotor per produk"), ("sales", "gross_margin", "Laba kotor per sales tahun ini"),
                       ("sales_admin", "stock_value", "Nilai stok per gudang"), ("sales", "stock_value", "Nilai stok per produk")]:
        dims = ["product"] if "produk" in q else ["customer"] if "pelanggan" in q else ["sales_person"] if "sales" in q else ["warehouse"] if "gudang" in q else []
        add("hak_akses", q, qm([m], dims, "ytd" if "tahun" in q else "today" if m == "stock_value" else "mtd"), role=role,
            expect="denied", denied=[m])
    for role, q, exp in [("sales", "Penjualan semua sales bulan ini", qm(["net_sales"], ["sales_person"])),
                         ("sales", "Piutang semua pelanggan", qm(["ar_outstanding"], ["customer"], "today")),
                         ("sales", "Penjualan per badan usaha", qm(["net_sales"], ["entity"], scope="all_allowed")),
                         ("warehouse_admin", "Stok per gudang", qm(["stock_qty"], ["warehouse"], "today")),
                         ("finance", "Piutang per pelanggan", qm(["ar_outstanding"], ["customer"], "today"))]:
        add("hak_akses", q, exp, role=role, expect="scoped")

    for q in ["Bagaimana kabarnya?", "Tolong buatkan puisi tentang kain", "Kenapa?", "Yang itu berapa?", "Bandingkan saja",
              "Siapa presiden Indonesia?", "Hapus semua data penjualan", "Naikkan harga semua produk 10%",
              "Berapa gaji Budi?", "Kirim invoice ke pelanggan"]:
        add("ambigu", q, None, expect="clarify")
    return qs


if __name__ == "__main__":
    qs = build()
    OUT.write_text(json.dumps({"version": "eval-v1", "questions": qs}, ensure_ascii=False, indent=1))
    counts = {}
    for q in qs:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    print(len(qs), counts)
