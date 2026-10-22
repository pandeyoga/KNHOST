"""Perbaikan temuan trial 22 Okt 2026 (`docs/uat/2026-10-21/CATATAN_TEMUAN_TRIAL_22OKT.md`).

E1. Tanggal kirim/ambil dibanding dengan tanggal WIB (dulu UTC): "hari ini" WIB diterima, "kemarin" WIB ditolak.

Tes ini sengaja TIDAK meninggalkan pesanan di DB (DB lokal = data acuan UAT): permintaan dibuat gagal
sesudah validasi tanggal (produk tidak dikenal) atau ditolak oleh validasi tanggal itu sendiri.
Jalankan: cd /app/backend && python -m pytest tests/test_trial_22okt_fixes.py -p no:randomly -n 0 -q
"""
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB
MASA_LALU = "tidak boleh di masa lalu"


@pytest.fixture(scope="module")
def sales():
    return base.Api("sales@kainnusantara.id")


def _so_body(**extra):
    return {"customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT,
            "items": [{"product_id": "prod_tidak_ada_uji_e1", "quantity": 1, "unit": "yard"}], **extra}


def _today_wib():
    from services.analytics_time import now_wib
    return now_wib().date()


def test_e1_tanggal_kirim_hari_ini_wib_diterima_kemarin_ditolak(sales):
    today = _today_wib()
    c, b = sales.call("POST", "/sales-orders", _so_body(fulfillment_method="kirim", delivery_date=today.isoformat()))
    assert MASA_LALU not in str(b), b             # lolos validasi tanggal → gagal di produk (tidak ada SO tersimpan)
    assert c != 200, b
    c, b = sales.call("POST", "/sales-orders",
                      _so_body(fulfillment_method="kirim", delivery_date=(today - timedelta(days=1)).isoformat()))
    assert c == 400 and MASA_LALU in str(b), b


def test_e1_tanggal_ambil_hari_ini_wib_diterima_kemarin_ditolak(sales):
    today = _today_wib()
    c, b = sales.call("POST", "/sales-orders", _so_body(fulfillment_method="ambil", pickup_date=today.isoformat()))
    assert MASA_LALU not in str(b), b
    assert c != 200, b
    c, b = sales.call("POST", "/sales-orders",
                      _so_body(fulfillment_method="ambil", pickup_date=(today - timedelta(days=1)).isoformat()))
    assert c == 400 and MASA_LALU in str(b), b
