"""UAT 24 Okt (audit UI tahap 2) — grup G4 (pembelian, kontrak & harga internal, makloon).

Uji tingkat layanan (tanpa HTTP) memakai event loop BERSAMA `tests/_shared_loop.py`. Semua uji di berkas ini
HANYA MEMBACA data acuan (tidak menulis ke DB).
Jalankan: cd /app/backend && python -m pytest tests/test_audit_ui2_g4.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import contract_service as cs  # noqa: E402
from services import interco_price_service as ips  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def test_g4_07_stats_internal_count():
    """G4-07 — statistik kontrak menyertakan hitungan jenis `internal` (dipakai tab "Harga Internal")
    dan jumlah per jenis = total (KPI tidak lagi ikut tersaring tab)."""
    ent = (DB.supplier_contracts.find_one({"contract_type": "internal"}, {"_id": 0, "entity_id": 1}) or {}).get("entity_id")
    if not ent:
        pytest.skip("data acuan tanpa kontrak harga internal")
    st = run(cs.stats({"entity_id": ent}))
    assert st["internal"] == DB.supplier_contracts.count_documents({"entity_id": ent, "contract_type": "internal"})
    assert st["total"] == st["makloon"] + st["purchase"] + st["internal"]


def test_g4_08_tile_matches_editor():
    """G4-08 — ubin ringkasan & editor massal memakai himpunan "ber-stok" yang sama:
    missing(ubin) = total(editor) dan stocked(ubin) = belum + sudah (editor)."""
    summary = run(ips.summary())
    pairs = [p for p in summary["pairs"] if p["stocked"]][:4]
    if not pairs:
        pytest.skip("data acuan tanpa barang ber-stok")
    for p in pairs:
        m = run(ips.missing(p["seller_entity_id"], p["buyer_entity_id"], only_stock=True))
        label = f"{p['seller_name']} → {p['buyer_name']}"
        assert m["total"] == p["missing"], label
        assert m["candidates"] == p["stocked"], label
        assert m["total"] + m["priced"] == m["candidates"], label


def test_g4_10_merge_suggestions_exclude_group_entity_and_name_warehouse():
    """G4-10 — saran gabung PR tidak pernah menyarankan supplier badan usaha grup (PO-nya pasti ditolak),
    menyertakan kode supplier & nama gudang tujuan (pembeda dua saran berlokasi sama), dan kuncinya unik."""
    from services import pr_sourcing_service as prs
    groups = run(prs.merge_suggestions({}))
    group_sids = {s["id"] for s in DB.suppliers.find(
        {"$or": [{"partner_kind": "entity"}, {"group_entity_id": {"$nin": [None, ""]}}]}, {"_id": 0, "id": 1})}
    keys = set()
    for g in groups:
        assert g["supplier_id"] not in group_sids, g["supplier_name"]
        assert "warehouse_name" in g and "supplier_code" in g
        key = (g["entity_id"], g["warehouse_id"], g["supplier_id"])
        assert key not in keys
        keys.add(key)


def test_g4_12_void_po_realizations_pure():
    """G4-12 — realisasi baris PR ke PO yang batal dikurangi dari `realized_qty` & ditandai `voided`;
    realisasi ke PO lain tidak tersentuh; panggilan kedua idempoten."""
    from services import pr_sourcing_service as prs
    pr = {"items": [
        {"line_no": 1, "quantity": 100, "realized_qty": 100, "fulfillment_mode": "purchase",
         "realizations": [{"type": "purchase_order", "ref_id": "po_A", "ref_number": "KSC/PO-1", "qty": 60},
                          {"type": "purchase_order", "ref_id": "po_B", "ref_number": "KSC/PO-2", "qty": 40}]},
        {"line_no": 2, "quantity": 10, "realized_qty": 10, "fulfillment_mode": "purchase",
         "realizations": [{"type": "purchase_order", "ref_id": "po_A", "ref_number": "KSC/PO-1", "qty": 10}]},
    ]}
    lines, qty, number = prs._void_po_realizations(pr, "po_A", actor="uji", reason="PO batal")
    assert (lines, qty, number) == (2, 70.0, "KSC/PO-1")
    assert pr["items"][0]["realized_qty"] == 40 and pr["items"][1]["realized_qty"] == 0
    assert prs.compute_realization(pr)["realization_status"] == "partially_realized"
    assert prs._void_po_realizations(pr, "po_A", actor="uji", reason="") == (0, 0.0, "")


def test_g4_12_release_po_realizations_db():
    """G4-12 (MENULIS DB — dokumen uji sendiri, dibersihkan): PR `converted` yang PO-nya batal kembali
    `approved`, baris terbuka lagi, po_id dikosongkan, riwayat mencatat pembatalan PO."""
    import uuid
    from services import pr_sourcing_service as prs
    tag = uuid.uuid4().hex[:6]
    pr_id, po_id = f"pr_TEST_G4_{tag}", f"po_TEST_G4_{tag}"
    DB.purchase_requisitions.insert_one({
        "id": pr_id, "number": f"TEST/PR-G4-{tag}", "status": "converted", "po_id": po_id,
        "po_number": f"TEST/PO-G4-{tag}", "timeline": [],
        "items": [{"line_no": 1, "product_id": "x", "quantity": 5, "realized_qty": 5, "fulfillment_mode": "purchase",
                   "realizations": [{"type": "purchase_order", "ref_id": po_id,
                                     "ref_number": f"TEST/PO-G4-{tag}", "qty": 5}]}]})
    try:
        out = run(prs.release_po_realizations(po_id, actor_name="uji", reason="uji G4-12"))
        assert len(out) == 1
        doc = DB.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
        assert doc["status"] == "approved" and doc["po_id"] == "" and doc["po_ids"] == []
        assert doc["items"][0]["realized_qty"] == 0 and doc["items"][0]["realizations"][0]["voided"] is True
        assert doc["timeline"][-1]["event"] == "po_released"
        assert run(prs.release_po_realizations(po_id, actor_name="uji")) == []   # idempoten
    finally:
        DB.purchase_requisitions.delete_one({"id": pr_id})


def test_g4_24_reorder_ignores_orphan_warehouse_balances():
    """G4-24 — "Tersedia" saran reorder = Σ available_qty saldo gudang yang ADA di master (saldo yatim gudang uji
    yang sudah dihapus tidak ikut; data acuan: Ulos Batak Ragidup 29 dari `wh_TEST_F1_…`)."""
    from services import purchase_requisition_service as prs
    res = run(prs.reorder_suggestions("ent_ksc"))
    known = {w["id"] for w in DB.warehouses.find({}, {"_id": 0, "id": 1})}
    for row in res["items"][:25]:
        exp = sum(float(b.get("available_qty") or 0) for b in DB.inventory_balances.find(
            {"owner_entity_id": "ent_ksc", "product_id": row["product_id"]}, {"_id": 0, "available_qty": 1, "warehouse_id": 1})
            if b.get("warehouse_id") in known)
        # K-04 (keputusan pemilik 26 Okt 2026) — definisi tunggal = papan stok: cadangan makloon aktif ikut dikurangi.
        mk = sum(float(m.get("qty") or 0) for m in DB.material_reservations.find(
            {"status": "active", "owner_entity_id": "ent_ksc", "product_id": row["product_id"]}, {"_id": 0, "qty": 1}))
        assert abs(float(row["available"]) - max(exp - mk, 0.0)) < 0.01, row["sku"]
