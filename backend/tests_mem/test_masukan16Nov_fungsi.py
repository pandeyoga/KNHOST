"""Masukan pemilik 16 Nov 2026 — perbaikan fungsi (docs/blueprint/masukan-pemilik/2026-11-16_TINDAK_LANJUT.md).

M33  pilihan lokasi di bilah atas mengikuti PT aktif (gudang khusus PT lain tidak ditawarkan).
M7   pilihan lokasi = AREA; gudang ber-area tidak ditawarkan satu per satu (kecuali petugas berpagar).
M31  baris kartu meja membawa waktu masuk antrean (`at`).
Meja Saya — giliran yang dokumennya sudah pindah tahap tidak tampil; lencana = tahap, bukan "Info".
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


async def _gudang(db) -> None:
    await db.warehouse_sites.insert_one({"id": "site_uji_rcm", "name": "Rancamalang Uji"})
    for i, (mode, ents, site) in enumerate([("shared", [], "site_uji_rcm"), ("dedicated", ["ent_ksc"], "site_uji_rcm"),
                                            ("dedicated", ["ent_kanda"], "site_uji_rcm"),
                                            ("dedicated", ["ent_kanda"], "")]):
        await db.warehouses.insert_one({"id": f"wh_uji_{i}", "code": f"UJI-{i}", "name": f"Gudang Uji {i}",
                                        "sharing_mode": mode, "entity_ids": ents, "site_id": site, "active": True})


async def test_M33_M7_pilihan_lokasi_ikut_pt_dan_berupa_area(klien, kepala_admin, db):
    await _gudang(db)
    ksc = (await klien.get("/api/location-scope", headers={**kepala_admin, "X-Entity-Id": "ent_ksc"})).json()
    nilai = [o["value"] for o in ksc["options"]]
    assert "site:site_uji_rcm" in nilai
    lbl = next(o["label"] for o in ksc["options"] if o["value"] == "site:site_uji_rcm")
    assert "(2 gedung)" in lbl   # bersama + khusus KSC; gudang khusus Kanda tidak dihitung
    assert not any(v.startswith("wh:wh_uji_") for v in nilai)   # gudang ber-area tidak ditawarkan satu-satu
    kanda = (await klien.get("/api/location-scope", headers={**kepala_admin, "X-Entity-Id": "ent_kanda"})).json()
    nk = [o["value"] for o in kanda["options"]]
    assert "wh:wh_uji_3" in nk   # gudang tanpa area tetap bisa dipilih sendiri
    lblk = next(o["label"] for o in kanda["options"] if o["value"] == "site:site_uji_rcm")
    assert "(2 gedung)" in lblk
    assert "wh:wh_uji_3" not in nilai   # khusus Kanda tidak muncul di KSC


async def test_M31_baris_meja_membawa_waktu_masuk(klien, kepala_admin):
    r = await klien.get("/api/sales-admin/desk", headers=kepala_admin)
    assert r.status_code == 200, r.text
    rows = [row for q in r.json().get("queues", []) for row in q.get("rows", [])]
    assert rows, "data seed harus punya baris meja"
    assert any(row.get("at") for row in rows)
    assert all(row["at"][:4].isdigit() for row in rows if row.get("at"))   # tanggal ISO, bukan objek mentah


async def test_giliran_lama_disembunyikan_lencana_tahap(klien, sesi, db):
    from services.role_desk_service import _turn_queue
    admin = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    so = {"id": "so_uji_giliran", "number": "SO-UJI-1", "status": "confirmed"}
    await db.sales_orders.insert_one(dict(so))
    await db.notifications.insert_many([
        {"id": "ntf_uji_lama", "recipient_user": admin["id"], "type": "turn", "read": False,
         "ref": f"turn:sales_orders:{so['id']}:status_lain_uji#{admin['id']}", "title": "Giliran Anda — Uji: X",
         "action_id": f"sales_orders:{so['id']}", "created_at": "2026-10-01T00:00:00+00:00", "severity": "info"},
        {"id": "ntf_uji_kini", "recipient_user": admin["id"], "type": "turn", "read": False,
         "ref": f"turn:sales_orders:{so['id']}:{so['status']}#{admin['id']}", "title": "Giliran Anda — Uji: Y",
         "action_id": f"sales_orders:{so['id']}x", "created_at": "2026-11-15T00:00:00+00:00", "severity": "info"},
    ])
    q = await _turn_queue(admin)
    ids = [r.get("notification_id") for r in q["rows"]]
    assert "ntf_uji_lama" not in ids   # dokumen sudah tidak di tahap itu
    row = next(r for r in q["rows"] if r.get("notification_id") == "ntf_uji_kini")
    assert row["badge"] != "info" and row["at"].startswith("2026-11-15")


async def test_M30_eskalasi_jadi_kartu_perlu_keputusan(klien, kepala_admin, sesi, db):
    """M30 — tugas gudang dieskalasi tampil di kartu "Perlu keputusan" (pemegang wms.approve), tidak di antrean kerja."""
    await db.wms_tasks.insert_one({"id": "wt_uji_esk", "number": "WT-ESK-1", "status": "escalated", "flow_type": "inbound",
                                   "entity_id": "ent_ksc", "supplier_name": "Pemasok Uji",
                                   "escalation": {"reason": "Qty kurang 3 roll", "escalated_at": "2026-11-10T00:00:00+00:00"},
                                   "created_at": "2026-11-09T00:00:00+00:00"})
    r = await klien.get("/api/desks/me", headers=kepala_admin)
    assert r.status_code == 200, r.text
    qs = {q["id"]: q for q in r.json()["queues"]}
    assert "eskalasi_keputusan" in qs
    row = next(x for x in qs["eskalasi_keputusan"]["rows"] if x["ref_id"] == "wt_uji_esk")
    assert row["ref_type"] == "wms_escalation" and "Qty kurang" in row["subtitle"] and row["at"].startswith("2026-11-10")
    assert all(x["ref_id"] != "wt_uji_esk" for x in qs.get("tugas_wms", {}).get("rows", []))
    gudang = await sesi("warehouse@kainnusantara.id")
    r2 = await klien.get("/api/desks/me", headers=gudang)
    assert "eskalasi_keputusan" not in {q["id"] for q in r2.json()["queues"]}   # petugas tanpa izin putus


async def test_M5_meja_md_lengkap(klien, kepala_admin, db):
    """M5 — Meja MD memuat SPK makloon berjalan, menunggu faktur mitra, PO bahan, dan PR disetujui belum direalisasi."""
    await db.makloon_orders.insert_one({"id": "mko_uji_m5", "mko_number": "KSC/MKO-UJI5", "status": "in_process",
                                        "entity_id": "ent_ksc", "final_output_name": "Kain Uji M5",
                                        "steps": [{"makloon_name": "Mitra Uji", "status": "issued"}],
                                        "planned_service_cost": 750000, "created_at": "2026-11-12T00:00:00+00:00"})
    await db.vendor_bills.insert_one({"id": "vb_uji_m5", "bill_number": "VBM-UJI5", "makloon_order_id": "mko_uji_m5",
                                      "status": "awaiting_invoice", "entity_id": "ent_ksc", "supplier_name": "Mitra Uji",
                                      "net_amount": 500000, "step_seq": 1, "created_at": "2026-11-13T00:00:00+00:00"})
    await db.purchase_orders.insert_one({"id": "po_uji_m5", "po_number": "KSC/PO-UJI5", "status": "pending",
                                         "source": "pr", "source_pr_number": "PR-UJI5", "entity_id": "ent_ksc",
                                         "supplier_name": "Pemasok Uji", "grand_total": 1000000,
                                         "created_at": "2026-11-14T00:00:00+00:00"})
    await db.purchase_requisitions.insert_one({"id": "pr_uji_m5", "number": "PR-UJI5", "status": "approved",
                                               "realization_status": "open", "entity_id": "ent_ksc",
                                               "reason": "Restock uji", "created_by": "Uji MD",
                                               "preferred_supplier_name": "Pemasok Uji", "total_est_amount": 900000,
                                               "items": [], "created_at": "2026-11-11T00:00:00+00:00"})
    r = await klien.get("/api/md/desk", headers=kepala_admin)
    assert r.status_code == 200, r.text
    qs = {q["id"]: q for q in r.json()["queues"]}
    jalan = next(x for x in qs["makloon_jalan"]["rows"] if x["ref_id"] == "mko_uji_m5")
    assert "Mitra Uji" in jalan["subtitle"]
    faktur = next(x for x in qs["makloon_faktur"]["rows"] if x["ref_id"] == "mko_uji_m5")
    assert faktur["number"] == "KSC/MKO-UJI5" and faktur["value"] == 500000
    assert any(x["ref_id"] == "po_uji_m5" for x in qs["po_bahan"]["rows"])
    pr = next(x for x in qs["pr"]["rows"] if x["ref_id"] == "pr_uji_m5")
    assert pr["title"] == "Restock uji" and "Pemasok Uji" in pr["subtitle"] and "Uji MD" in pr["subtitle"]
    assert pr["value"] == 900000


async def test_M21_riwayat_harga_beli(klien, kepala_admin, db):
    await db.sales_orders.insert_many([
        {"id": "so_uji_m21a", "number": "SO-M21A", "customer_id": "cust_uji_m21", "status": "done",
         "entity_id": "ent_ksc", "created_at": "2026-11-01T00:00:00+00:00",
         "items": [{"product_id": "prod_uji_m21", "quantity": 10, "unit": "yard", "price": 90000,
                    "normal_price": 100000, "price_source": "special_approval"}]},
        {"id": "so_uji_m21b", "number": "SO-M21B", "customer_id": "cust_uji_m21", "status": "cancelled",
         "entity_id": "ent_ksc", "created_at": "2026-11-02T00:00:00+00:00",
         "items": [{"product_id": "prod_uji_m21", "quantity": 5, "unit": "yard", "price": 80000}]},
    ])
    r = await klien.get("/api/customer-prices/purchase-history", headers=kepala_admin,
                        params={"customer_id": "cust_uji_m21", "product_id": "prod_uji_m21"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [i["so_number"] for i in items] == ["SO-M21A"]   # pesanan batal tidak dihitung
    assert items[0]["price"] == 90000 and items[0]["price_source_label"] == "Harga khusus"


async def test_M42_jejak_dokumen_tanpa_kata_cari_berisi_daftar(klien, kepala_admin):
    r = await klien.get("/api/documents/trace-search", headers=kepala_admin, params={"q": ""})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "tanpa kata cari harus menampilkan dokumen terbaru"
    tanggal = [str(n.get("date") or "") for n in rows]
    assert tanggal == sorted(tanggal, reverse=True)


async def test_M19_sales_pj_jatuh_ke_pic_tim(db):
    from services.customer_service import enrich_customer
    c = await enrich_customer({"id": "cust_uji_m19", "name": "Toko M19",
                               "sales_team": [{"user_id": "u1", "name": "Ayu PIC", "role": "pic", "split_pct": 100}]},
                              with_credit=False)
    assert c["assigned_sales_name"] == "Ayu PIC"
