"""INV-REF-02 + INV-AMD-01 (data latihan 18 Nov, sapuan baca-saja): KSC/AMD-00005 (nota debit, `auto_applied`) —
`sales_order → doc_amendment` (`amended_by`) dan `credit_note → doc_amendment` (`issued_by`) hanya satu arah; amandemen
"tanpa jejak ke dokumen asal" (tidak punya `amends`).

Akar: `amendment_service._apply` menulis `"refs": (amd.get("refs") or []) + refs` dengan `$set` dari SALINAN amandemen
yang dibaca sebelum penerapan. Selama penerapan `_apply_note` menautkan nota ↔ amandemen dan amandemen ↔ pesanan lewat
`doc_refs_service` (`$push` dua arah); `$set` salinan menimpa tautan balik itu dan menambah baris tak baku
(`issued` → `debit_note`, `applied_to` — relasi yang sudah dicabut dari kosakata). Hasil penerapan sudah disimpan di
`result_refs`; `refs` milik `doc_refs_service`.

Langkah ulang (API): pesanan terkirim penuh → amandemen naik harga (nota debit) → disetujui akun kedua → amandemen tidak
menyebut nota yang diterbitkannya dengan jenis baku (`credit_note`), nota menunjuk amandemen satu arah.
"""
from __future__ import annotations

import pytest

from test_PK32_nota_kredit import QTY, dunia, kirim, koreksi, nota_dari, pesanan  # noqa: F401 — fixture `dunia`

pytestmark = pytest.mark.anyio


async def _refs(db, coll: str, doc_id: str) -> list:
    return (await db[coll].find_one({"id": doc_id}, {"_id": 0, "refs": 1}) or {}).get("refs") or []


async def test_nota_debit_amandemen_tautan_dua_arah(klien, kepala_admin, db, dunia):  # noqa: F811
    from services import doc_refs_service as dr
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    d, amd_id = await koreksi(klien, kepala_admin, dunia["h2"], so, 11_000, dunia["pid"])
    assert d.status_code == 200, d.text
    n = await nota_dari(db, amd_id)
    assert n and n["kind"] == "debit_note", n

    amd_refs = await _refs(db, "doc_amendments", amd_id)
    nota_refs = await _refs(db, "credit_notes", n["id"])
    so_refs = await _refs(db, "sales_orders", so["id"])
    # nota → amandemen (issued_by) ada; amandemen WAJIB membalasnya dengan jenis baku `credit_note` (kode lama: hilang,
    # diganti `issued` → `debit_note` yang tidak dikenali peta relasi)
    assert any(r["rel"] == "issued_by" and r["doc_id"] == amd_id for r in nota_refs), nota_refs
    assert any(r["rel"] == "issued" and r["doc_type"] == "credit_note" and r["doc_id"] == n["id"]
               for r in amd_refs), amd_refs
    # amandemen ↔ pesanan dua arah (INV-AMD-01: amandemen punya `amends`)
    assert any(r["rel"] == "amends" and r["doc_id"] == so["id"] for r in amd_refs), amd_refs
    assert any(r["rel"] == "amended_by" and r["doc_id"] == amd_id for r in so_refs), so_refs
    # tidak ada relasi di luar kosakata dua arah
    assert all(r["rel"] in dr.REL_INVERSE for r in amd_refs), amd_refs
    # hasil penerapan tetap tercatat di field hasil
    a = await db.doc_amendments.find_one({"id": amd_id}, {"_id": 0, "result_refs": 1, "status": 1})
    assert a["status"] in ("applied", "auto_applied") and [r["doc_id"] for r in a["result_refs"]] == [n["id"]], a
