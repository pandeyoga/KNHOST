"""PR-T6 U17 — kode jawaban Manajer seed (lintas PT bawaan) tidak berubah (docs/blueprint/unit/PR-T6.md).

`data/kode_sebelum_PRT6.json` dibuat dari kode SEBELUM unit ini (langkah kerja 1), di basis data tiruan baru, dengan
menjalankan modul ini ber-variabel lingkungan `KN_PRT6_TULIS_SEBELUM=1` (uji ditandai "dilewati" dan berkas ditulis).
Rute: `/api/customers`, `/api/customers/{id}/360` (pelanggan PT uji di luar penugasan tertulis manajer seed),
`/api/bank-accounts`, `/api/cash-transactions` (dengan satu rekening dan satu transaksi kas tingkat grup — cabang
"lintas PT" yang diganti butir 6), `/api/access/roles` (403), `/api/users`. Dicatat kode dan, untuk daftar, jumlah baris.
Modul sendiri (basis data sendiri).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from pembantu import pt_uji

pytestmark = pytest.mark.anyio

BERKAS_SEBELUM = Path(__file__).parent / "data" / "kode_sebelum_PRT6.json"
TULIS_SEBELUM = os.environ.get("KN_PRT6_TULIS_SEBELUM") == "1"
WAKTU = "2026-11-10T03:00:00+00:00"

RUTE: List[Tuple[str, str]] = [
    ("GET", "/api/customers"), ("GET", "/api/customers/cust_prt6_sapu/360"),
    ("GET", "/api/bank-accounts"), ("GET", "/api/cash-transactions"),
    ("GET", "/api/access/roles"), ("GET", "/api/users"),
]


async def _siapkan(db) -> None:
    """Fixture (sisip langsung): pelanggan di PT uji, rekening & transaksi kas tingkat grup (data lama E7.4)."""
    pt = await pt_uji("PRT6S")
    from services.entity_lifecycle_service import invalidate_status_cache
    invalidate_status_cache()
    await db.customers.insert_one({"id": "cust_prt6_sapu", "code": "CUST-PRT6S", "name": "Pelanggan PRT6 Sapu",
                                   "entity_id": pt, "status": "active", "segment": "retail",
                                   "created_at": WAKTU, "updated_at": WAKTU})
    await db.bank_accounts.insert_one({"id": "bank_prt6_grup", "name": "Rekening Grup Lama", "entity_id": "all",
                                       "type": "bank", "account_number": "000", "status": "active",
                                       "opening_balance": 0, "created_at": WAKTU})
    await db.cash_transactions.insert_one({"id": "cash_prt6_grup", "entity_id": "all", "cash_type": "kas_besar",
                                           "direction": "in", "amount": 1000, "status": "posted",
                                           "txn_date": "2026-11-01", "created_at": WAKTU})


async def sapu(klien, sesi) -> Dict[str, Dict[str, int]]:
    h = await sesi("manager@kainnusantara.id")
    out: Dict[str, Dict[str, int]] = {}
    for m, j in RUTE:
        r = await klien.request(m, j, headers=h)
        isi = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
        baris = isi if isinstance(isi, list) else (isi.get("items") if isinstance(isi, dict)
                                                   and isinstance(isi.get("items"), list) else None)
        out[f"{m} {j}"] = {"kode": r.status_code, **({"baris": len(baris)} if baris is not None else {})}
    return out


if TULIS_SEBELUM:   # hanya dikumpulkan dengan `KN_PRT6_TULIS_SEBELUM=1` (kode SEBELUM unit; langkah kerja 1)
    async def test_tulis_berkas_sebelum(klien, sesi, db):
        await _siapkan(db)
        BERKAS_SEBELUM.write_text(json.dumps({"manager": await sapu(klien, sesi)}, indent=1, sort_keys=True,
                                             ensure_ascii=False) + "\n")
        pytest.skip(f"berkas sebelum ditulis: {BERKAS_SEBELUM.name}")


@pytest.mark.skipif(TULIS_SEBELUM, reason="mode menulis berkas sebelum")
async def test_PRT6_U17_kode_jawaban_manajer_sama(klien, sesi, db):
    await _siapkan(db)
    sebelum = json.loads(BERKAS_SEBELUM.read_text())["manager"]
    sesudah = await sapu(klien, sesi)
    assert sesudah == sebelum
    assert sesudah["GET /api/access/roles"]["kode"] == 403   # Manajer bawaan tidak memegang `permission.view`
    assert sesudah["GET /api/customers/cust_prt6_sapu/360"]["kode"] == 200   # lintas PT bawaan
