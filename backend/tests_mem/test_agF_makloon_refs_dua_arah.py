"""Gate merah lama INV-REF-02 (log gate 17 Nov): "2 relasi hanya satu arah" — `grn:wms_mko_…` → `makloon_order:mko_…`
(`parent`), tanpa tautan balik di SPK makloon.

Akar: `makloon_order_service.receive_step` menulis akhir penerimaan dengan `$set` SELURUH salinan pesanan di memori
(dulu `upd = {k: v for k, v in order.items() if k not in ("id", "_id")}`), termasuk `refs`. Salinan itu dibaca SEBELUM
`makloon_receipt_qc.open_receipt_tasks` menautkan tugas QC hasil (`doc_refs_service.safe_link` → `$push` ke
`makloon_orders.refs`), jadi tautan balik yang baru didorong tertimpa salinan lama. `refs` milik `doc_refs_service`.

Langkah ulang (API, MongoDB asli): SPK makloon satu langkah celup (langkah kain terakhir) → Kirim bahan → Terima hasil
dengan QC penerimaan aktif → tugas QC `wms_mko_…` menunjuk SPK sebagai induk, tetapi SPK tidak menyebut tugas itu.

Batas uji: `receive_step` utuh tidak bisa dijalankan di database tiruan (`_save_prog` memakai array filters — mongomock
`NotImplementedError`). Uji ini menjalankan URUTAN yang sama pada tingkat tulisan: salinan SPK dibaca → tugas QC bertaut
lewat `doc_refs_service.link` → tulisan akhir `$set` dari salinan (kode lama vs `_receive_final_set`).
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_agfmk_{uuid.uuid4().hex[:8]}"


async def _spk_dan_tugas(db) -> tuple:
    mko, tid = uid("mko"), "wms_mko_" + uuid.uuid4().hex[:16]
    await db.makloon_orders.insert_one({"id": mko, "mko_number": f"MKO/AGF/{mko[-6:]}", "entity_id": KSC,
                                        "status": "in_progress", "steps": [{"seq": 1, "status": "issued"}],
                                        "timeline": [], "saga_lock": {"token": "tok"},
                                        # SPK nyata hampir selalu sudah bertaut (pesanan khusus/PO/langkah sebelumnya):
                                        # salinan membawa `refs` lama → `$set` salinan menimpa tautan baru.
                                        "refs": [{"rel": "references", "doc_type": "special_order",
                                                  "doc_id": "spo_lama", "doc_number": "SPO-LAMA", "note": "",
                                                  "at": "2026-11-01T00:00:00+00:00"}]})
    await db.wms_tasks.insert_one({"id": tid, "entity_id": KSC, "owner_entity_id": KSC, "flow_type": "inbound",
                                   "task_subtype": "makloon_receipt", "mko_id": mko, "status": "qc_pending"})
    return mko, tid


async def _alur(db, susun_set) -> tuple:
    from services import doc_refs_service as refs
    mko, tid = await _spk_dan_tugas(db)
    salinan = await db.makloon_orders.find_one({"id": mko}, {"_id": 0})          # dibaca di awal penerimaan
    hasil = await refs.link(("grn", tid), ("makloon_order", mko), "parent", force=True)   # open_receipt_tasks
    assert hasil["linked"] == 2, hasil
    salinan["status"] = "completed"
    salinan["steps"][0]["status"] = "received"
    salinan.pop("saga_lock", None)
    await db.makloon_orders.update_one({"id": mko, "saga_lock.token": "tok"},
                                       {"$set": susun_set(salinan), "$unset": {"saga_lock": ""}})
    o = await db.makloon_orders.find_one({"id": mko}, {"_id": 0})
    t = await db.wms_tasks.find_one({"id": tid}, {"_id": 0})
    return o, t, tid, mko


async def test_kode_lama_menimpa_tautan_balik(db):
    """Bukti mekanisme: `$set` seluruh salinan (ekspresi lama) menghapus tautan yang didorong di tengah penerimaan."""
    o, t, tid, mko = await _alur(db, lambda order: {k: v for k, v in order.items() if k not in ("id", "_id")})
    assert any(x["rel"] == "parent" and x["doc_id"] == mko for x in t.get("refs") or [])
    assert not [x for x in o.get("refs") or [] if x["doc_id"] == tid]          # satu arah → INV-REF-02 merah


async def test_tulisan_akhir_penerimaan_tidak_menimpa_refs(db):
    from services import doc_refs_service as refs
    from services.makloon_order_service import _receive_final_set
    o, t, tid, mko = await _alur(db, _receive_final_set)
    assert o["status"] == "completed" and o["steps"][0]["status"] == "received" and "saga_lock" not in o
    assert any(x["rel"] == "parent" and x["doc_id"] == mko for x in t.get("refs") or [])
    balik = [x for x in o.get("refs") or [] if x["doc_type"] == "grn" and x["doc_id"] == tid]
    assert balik and balik[0]["rel"] == refs.REL_INVERSE["parent"], o.get("refs")
    assert any(x["doc_id"] == "spo_lama" for x in o["refs"])                  # tautan lama tetap ada
