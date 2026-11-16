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
