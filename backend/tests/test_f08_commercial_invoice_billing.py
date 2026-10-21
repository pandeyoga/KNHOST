"""F-08 (uji pra-UAT 2026-10-21) — dokumen tagihan resmi = Faktur Komersial; "Ditagih" tidak lagi = Faktur Pajak.

Reproduksi: SO lunas tanpa Faktur Pajak tampil "Ditagih: Belum ada faktur pajak" (langkah Ditagih = Faktur Pajak) dan
daftar invoice SO kosong. Kini langkah *Ditagih (Faktur Komersial)* selesai saat Surat Jalan pertama terbit (pendapatan &
piutang diakui per SJ) dan perjalanan membawa `commercial_invoice` (PDF jenis `invoice` dari SO, unduh di panel).
Jalankan: cd /app/backend && python -m pytest tests/test_f08_commercial_invoice_billing.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                       ("mgr", "manager@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                       ("wh", "warehouse@kainnusantara.id"), ("whadm", "wh.admin@kainnusantara.id"))}


def _journey(u, so_id):
    c, j = u["sales"].call("GET", f"/sales-orders/{so_id}/journey")
    assert c == 200, j
    return j, {s["key"]: s for s in j["steps"]}


def test_ditagih_faktur_komersial_saat_dikirim(u):
    so, tasks = base._ready_to_ship(u, "NET30")
    j, st = _journey(u, so["id"])
    assert not st["ditagih"]["done"] and "Faktur Komersial" in st["ditagih"]["label"], st["ditagih"]
    assert j["commercial_invoice"]["available"] is False
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    j, st = _journey(u, so["id"])
    assert st["ditagih"]["done"] and st["ditagih"]["at"], st["ditagih"]          # dulu: menunggu Faktur Pajak
    assert "Faktur Komersial" in st["ditagih"]["detail"], st["ditagih"]
    ci = j["commercial_invoice"]
    assert ci["available"] and ci["doc_type"] == "invoice" and ci["number"], ci
    r = base.requests.get(f"{base.BASE}/pdf/render/invoice/{so['id']}", headers=u["sales"].h, timeout=120)
    assert r.status_code == 200 and r.content[:4] == b"%PDF", (r.status_code, r.text[:200])   # PDF bisa diunduh sales
