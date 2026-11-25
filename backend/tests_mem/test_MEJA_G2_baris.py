"""Meja gelombang 2 · Tugas 6 — baris antrean Keuangan membawa id dokumen untuk pratinjau di pop-up meja.

`denda_draft` membawa `doc_type`/`doc_id` (dokumen dasar nota denda); `selisih_bayar` membawa `order_ids`
(`variance.target_order_ids`). Isian lain tidak berubah.
"""
from __future__ import annotations

import uuid

import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio


def _baris(desk_json, qid, ref_id):
    return next(x for q in desk_json["queues"] if q["id"] == qid for x in q["rows"] if x["ref_id"] == ref_id)


async def test_denda_draft_membawa_dokumen_dasar(klien, db, kepala_admin):
    pid = f"pnl_g2_{uuid.uuid4().hex[:8]}"
    await db.penalties.insert_one({
        "id": pid, "number": "DN-G2-1", "entity_id": "ent_ksc", "customer_id": "cus_g2", "customer_name": "Toko Denda",
        "doc_type": "sales_order", "doc_id": "so_g2_dasar", "doc_number": "SO-G2", "amount": 25_000.0,
        "status": "draft", "created_at": now_iso()})
    row = _baris((await klien.get("/api/finance/desk", headers=kepala_admin)).json(), "denda_draft", pid)
    assert (row["doc_type"], row["doc_id"]) == ("sales_order", "so_g2_dasar")
    assert row["subtitle"] == "atas SO-G2" and row["value"] == 25_000.0


async def test_selisih_bayar_membawa_order_ids(klien, db, kepala_admin):
    rc = f"arc_g2_{uuid.uuid4().hex[:8]}"
    await db.ar_receipts.insert_one({
        "id": rc, "number": "KW-G2-1", "entity_id": "ent_ksc", "status": "posted", "customer_id": "cus_g2",
        "customer_name": "Toko Selisih", "receipt_date": now_iso(), "created_at": now_iso(),
        "amount": 1000.0, "total_funds": 1000.0, "applied_total": 0.0, "unapplied_amount": 1000.0, "allocations": [],
        "variance": {"direction": "over", "delta": 1000.0, "expected": 0.0, "needs_decision": True,
                     "target_order_ids": ["so_a", "so_b"], "decision_id": ""}})
    row = _baris((await klien.get("/api/finance/desk", headers=kepala_admin)).json(), "selisih_bayar", rc)
    assert row["order_ids"] == ["so_a", "so_b"]
    assert row["ref_type"] == "ar_receipt" and row["ref_id"] == rc
