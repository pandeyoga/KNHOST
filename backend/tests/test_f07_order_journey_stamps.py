"""F-07 (uji pra-UAT 2026-10-21) — Perjalanan SO: tahap berstempel waktu & pelaku, "Disiapkan gudang" benar.

Reproduksi: SO yang sudah selesai menampilkan *Disiapkan gudang 0/1* (tugas berstatus `dispatched` tidak dihitung)
dan langkah *Disetujui* / *Dikonfirmasi* tanpa waktu & pelaku (transisi tidak menyimpan `approved_at/by`,
`confirmed_at/by`). Kini `so_transition` menstempel tahap kunci, dan perjalanan menghitung tugas yang sudah
disiapkan/dikirim; pesanan lama memakai jejak audit transisinya.
Alur nyata lewat API akun peran (data acuan). Jalankan:
  cd /app/backend && python -m pytest tests/test_f07_order_journey_stamps.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f06_pod_closes_so as f06  # noqa: E402 — helper kirim & POD
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                       ("mgr", "manager@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                       ("wh", "warehouse@kainnusantara.id"), ("whadm", "wh.admin@kainnusantara.id"),
                                       ("adm", "admin@kainnusantara.id"))}


def _steps(u, so_id):
    c, j = u["sadm"].call("GET", f"/sales-orders/{so_id}/journey")
    assert c == 200, j
    return {s["key"]: s for s in j["steps"]}


def test_perjalanan_so_selesai_lengkap_dengan_waktu_pelaku_dan_disiapkan(u):
    so, tasks = base._ready_to_ship(u, "NET30")
    doc = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "approved_at": 1, "approved_by": 1,
                                                      "confirmed_at": 1, "confirmed_by": 1})
    assert doc.get("approved_at") and doc.get("approved_by"), doc          # dulu: tidak tersimpan
    assert doc.get("confirmed_at") and doc.get("confirmed_by"), doc
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    ships = [s["id"] for s in DB.shipments.find({"order_id": so["id"]}, {"_id": 0, "id": 1})]
    f06._deliver(u, ships)
    st = _steps(u, so["id"])
    for key in ("disetujui", "dikonfirmasi"):
        assert st[key]["done"] and st[key]["at"] and st[key]["by"], st[key]
    assert st["dikonfirmasi"]["by"] == "Rina Kartika" or st["dikonfirmasi"]["by"], st["dikonfirmasi"]
    n = len(tasks)
    assert st["disiapkan"]["done"] and st["disiapkan"]["detail"] == f"{n}/{n} tugas gudang selesai", st["disiapkan"]
    assert st["disiapkan"]["at"], st["disiapkan"]
    assert st["diterima"]["done"] and st["diterima"]["by"], st["diterima"]


def test_pesanan_lama_tanpa_stempel_memakai_jejak_audit(u):
    so, tasks = base._ready_to_ship(u, "NET30")
    DB.sales_orders.update_one({"id": so["id"]}, {"$unset": {"approved_at": "", "approved_by": "",
                                                             "confirmed_at": "", "confirmed_by": ""}})
    st = _steps(u, so["id"])
    assert st["disetujui"]["at"] and st["disetujui"]["by"], st["disetujui"]
    assert st["dikonfirmasi"]["at"] and st["dikonfirmasi"]["by"], st["dikonfirmasi"]
