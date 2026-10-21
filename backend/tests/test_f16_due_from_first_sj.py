"""F-16 (uji pra-UAT 2026-10-21, keputusan owner Q-05a) — jatuh tempo piutang dari Surat Jalan PERTAMA.

Reproduksi: jatuh tempo = tanggal SO + termin; SO backorder / menunggu ACC / belum dikirim dan SO CBD tampil
"30 hari lagi" di daftar tagih (Meja Finance "Jatuh tempo") dan umur piutang.
Kini: dasar = tanggal SJ pertama, lama termin = kode termin SO (CBD 0 hari, NET30 30 hari); SO yang belum dikirim
tidak masuk daftar jatuh tempo (umur piutang: "belum dikirim", kolom belum jatuh tempo, tanpa denda).
Alur nyata lewat API akun peran (data acuan). Jalankan:
  cd /app/backend && python -m pytest tests/test_f16_due_from_first_sj.py -p no:randomly -n 0 -q
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402 — helper alur SO sampai siap kirim

DB = base.DB


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                       ("mgr", "manager@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                       ("wh", "warehouse@kainnusantara.id"), ("whadm", "wh.admin@kainnusantara.id"),
                                       ("adm", "admin@kainnusantara.id"))}


def _backdate(so_id, days):
    """SO dibuat `days` hari lalu (pesanan lama yang baru dikirim hari ini)."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    DB.sales_orders.update_one({"id": so_id}, {"$set": {"created_at": ts}})


def _worklist(u):
    c, rows = u["fin"].call("GET", "/collection-worklist")
    assert c == 200, rows
    return {r["order_id"]: r for r in rows}


def _first_sj_date(so_id):
    s = DB.shipments.find_one({"order_id": so_id}, {"_id": 0, "created_at": 1}, sort=[("created_at", 1)])
    return datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")).date()


def test_belum_dikirim_tidak_masuk_daftar_jatuh_tempo(u):
    so, _tasks = base._ready_to_ship(u, "NET30")          # dikonfirmasi & ter-pick, BELUM dikirim
    _backdate(so["id"], 40)                                # dulu: 40 hari lalu + 30 → "telat 10 hari"
    rows = _worklist(u)
    assert so["id"] not in rows, rows.get(so["id"])
    c, det = u["fin"].call("GET", f"/ar/aging/{base.CUST}")
    assert c == 200, det
    it = next(x for x in det["items"] if x["order_id"] == so["id"])
    assert it["due_date"] == "" and it["due_basis"] == "not_shipped" and it["bucket"] == "current", it
    assert it["days_late"] == 0 and not it.get("overdue"), it


def test_jatuh_tempo_dari_sj_pertama_bukan_tanggal_so(u):
    so, tasks = base._ready_to_ship(u, "NET30")
    _backdate(so["id"], 20)                                # dulu: jatuh tempo = 20 hari lalu + 30 = 10 hari lagi
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    expect = _first_sj_date(so["id"]) + timedelta(days=30)
    row = _worklist(u)[so["id"]]
    assert row["due_date"] == expect.isoformat() and not row["overdue"], row
    c, det = u["fin"].call("GET", f"/ar/aging/{base.CUST}")
    it = next(x for x in det["items"] if x["order_id"] == so["id"])
    assert it["due_date"] == expect.isoformat() and it["due_basis"] == "first_sj", it


def test_cbd_jatuh_tempo_mengikuti_termin_bukan_30_hari(u):
    so, tasks = base._ready_to_ship(u, "CBD")
    c, b = u["fin"].call("POST", f"/sales-orders/{so['id']}/dispatch-payment-release",
                         {"reason": "uji F-16: kirim dulu, bayar menyusul"})
    assert c == 200, b
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    row = _worklist(u)[so["id"]]
    assert row["due_date"] == _first_sj_date(so["id"]).isoformat(), row       # CBD: 0 hari sesudah kirim
    assert row["days_late"] >= 0, row                                          # dulu: "30 hari lagi" (-30)
