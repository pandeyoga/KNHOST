"""F-06 (uji pra-UAT 2026-10-21, keputusan owner Q-01a) — POD semua Surat Jalan menutup SO otomatis.

Reproduksi LG-00001/2 (ulang SO-00084): pengiriman Logistik ditandai *Terkirim* (foto POD + nama penerima), tetapi SO
tetap `shipped` ("Dikirim") — hanya hook Pesanan Khusus yang dipanggil. Kini: SO `shipped` yang SEMUA Surat Jalan
aktifnya ber-POD (kurir/sopir atau serah terima ambil sendiri) otomatis `done`, aktor = petugas POD; SJ yang belum
ber-POD menahan penutupan (progres tampil di detail SO).
Alur nyata lewat API akun peran (data acuan). Jalankan:
  cd /app/backend && python -m pytest tests/test_f06_pod_closes_so.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402 — helper alur SO sampai siap kirim

DB = base.DB
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                       ("mgr", "manager@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                       ("wh", "warehouse@kainnusantara.id"), ("whadm", "wh.admin@kainnusantara.id"),
                                       ("adm", "admin@kainnusantara.id"))}


def _photo(api, did, kind):
    import requests
    r = requests.post(f"{base.BASE}/logistics/deliveries/{did}/photos", headers=api.h,
                      data={"kind": kind, "note": "uji F-06"}, files={"file": (f"{kind}.png", PNG, "image/png")}, timeout=60)
    assert r.status_code == 200, r.text[:300]


def _deliver(u, ship_ids, receiver="Bu Rina (uji F-06)"):
    """Ekspedisi: buat pengiriman → foto muat → Dimuat → Berangkat → foto POD → Terkirim (Admin Gudang)."""
    c, d = u["whadm"].call("POST", "/logistics/deliveries", {
        "shipment_ids": ship_ids, "mode": "expedition", "courier_name": "JNE", "tracking_no": "RESI-F06-UJI"})
    assert c == 200, d
    _photo(u["whadm"], d["id"], "load")
    for to in ("loaded", "in_transit"):
        c, b = u["whadm"].call("POST", f"/logistics/deliveries/{d['id']}/transition", {"to": to})
        assert c == 200, (to, b)
    _photo(u["whadm"], d["id"], "pod")
    c, b = u["whadm"].call("POST", f"/logistics/deliveries/{d['id']}/transition",
                           {"to": "delivered", "receiver_name": receiver})
    assert c == 200, b
    return d


def _status(so_id):
    return DB.sales_orders.find_one({"id": so_id}, {"_id": 0, "status": 1, "delivered_by": 1, "delivered_via": 1})


def test_pod_semua_sj_menutup_so_otomatis(u):
    so, tasks = base._ready_to_ship(u, "NET30")
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    assert _status(so["id"])["status"] == "shipped"
    ships = [s["id"] for s in DB.shipments.find({"order_id": so["id"]}, {"_id": 0, "id": 1})]
    c, p = u["sadm"].call("GET", f"/sales-orders/{so['id']}/pod-progress")
    assert c == 200 and p["total"] == len(ships) and p["with_pod"] == 0 and not p["complete"], p

    _deliver(u, ships)
    st = _status(so["id"])
    assert st["status"] == "done", st                                         # dulu tetap "shipped"
    assert st["delivered_via"] == "pod" and st["delivered_by"], st
    assert DB.audit_logs.find_one({"action": "order_delivered", "entity_id": so["id"], "after.via": "pod_auto"}) \
        or DB.audit_logs.find_one({"action": "order_delivered", "entity_id": so["id"]}), "audit penutupan hilang"
    assert DB.inventory_rolls.count_documents({"reserved_ref.id": so["id"], "status": "in_transit_sales"}) == 0
    c, b = u["sadm"].call("POST", f"/sales-orders/{so['id']}/mark-delivered")
    assert c == 409, b                                                        # sudah tertutup — tidak dobel


def test_sj_belum_pod_menahan_penutupan(u):
    so, tasks = base._ready_to_ship(u, "NET30")
    t = tasks[0]
    qty = float(DB.wms_tasks.find_one({"id": t["id"]}, {"_id": 0, "picked_qty": 1})["picked_qty"])
    c, b = u["wh"].call("POST", f"/outbound/tasks/{t['id']}/dispatch", params={"ship_qty": round(qty / 2, 2)})
    assert c == 200, b
    first = b["shipment"]["id"]
    c, b = u["whadm"].call("POST", f"/outbound/so/{so['id']}/loading-check/override",   # manifest berubah (RF-06)
                           {"reason": "uji F-06 kirim sisa tanpa perangkat RFID - validasi manual"})
    assert c == 200, b
    for c, b in base._dispatch(u, tasks):                                     # sisa (dan tugas gudang lain bila ada)
        assert c == 200, b
    assert _status(so["id"])["status"] == "shipped"
    ships = [s["id"] for s in DB.shipments.find({"order_id": so["id"]}, {"_id": 0, "id": 1})]
    assert len(ships) >= 2, ships

    _deliver(u, [first])
    assert _status(so["id"])["status"] == "shipped"                           # SJ lain belum ber-POD
    c, p = u["sadm"].call("GET", f"/sales-orders/{so['id']}/pod-progress")
    assert p["with_pod"] == 1 and p["total"] == len(ships) and len(p["missing"]) == len(ships) - 1, p

    _deliver(u, [s for s in ships if s != first])
    assert _status(so["id"])["status"] == "done"


def test_pelacak_so_menunjuk_pod_di_logistik(u):
    so, tasks = base._ready_to_ship(u, "CBD")
    base._pay(u, so, so["grand_total"])
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    c, tr = u["whadm"].call("GET", "/desks/so-tracker", params={"desk": "warehouse_admin"})
    assert c == 200, tr
    row = next(x for x in tr["rows"] if x["id"] == so["id"])
    assert "POD" in row["next_step"] and "logistics" in row["owner_roles"] and row["action"] == "Catat POD", row
