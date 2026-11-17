"""Uji adversarial pelatihan 18 Nov (agen D) — pesan untuk pengguna yang KALAH balapan klaim dokumen.

Dua pengguna (Finance + Manajer) membayar tagihan yang sama hampir bersamaan: uangnya aman (satu menang), tetapi yang
kalah membaca "Aksi 'ap_pay_vendor_bill' atas dokumen ini sedang/pernah berjalan (mulai 2026-11-17T19:05:45.335365+00:00)
dan belum selesai. Muat ulang; bila tetap menggantung, admin dapat melepasnya lewat Kunci Saga." — kode aksi mentah,
jam UTC mentah, dan istilah teknis. Pesan baru: siapa yang sedang memproses, jam WIB, dan langkah yang jelas. Kode
`SAGA_IN_PROGRESS`/`STATE_CHANGED` dan data `lock` tetap (dibaca layar Kunci Saga & uji balapan).
"""
from __future__ import annotations

import re

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.anyio


async def test_pesan_kalah_klaim_tanpa_kode_mentah(db):
    from services import atomic_claim as saga
    await db.vendor_bills.insert_one({"id": "vb_klaim_adv", "status": "posted", "bill_number": "VB-ADV"})
    await saga.claim("vendor_bills", "vb_klaim_adv", "ap_pay_vendor_bill", precondition={"status": "posted"},
                     actor="Rina Manajer")
    with pytest.raises(HTTPException) as e:
        await saga.claim("vendor_bills", "vb_klaim_adv", "ap_pay_vendor_bill", precondition={"status": "posted"},
                         actor="Peserta 97")
    d = e.value.detail
    assert e.value.status_code == 409 and d["code"] == "SAGA_IN_PROGRESS" and d["lock"]["by"] == "Rina Manajer"
    msg = d["message"]
    assert "ap_pay_vendor_bill" not in msg and "+00:00" not in msg and not re.search(r"\d{4}-\d{2}-\d{2}T", msg)
    assert "Rina Manajer" in msg and "WIB" in msg and "muat ulang" in msg.lower(), msg


async def test_pesan_status_berubah_tanpa_kode_mentah(db):
    from services import atomic_claim as saga
    await db.vendor_bills.insert_one({"id": "vb_klaim_adv2", "status": "paid", "bill_number": "VB-ADV2"})
    with pytest.raises(HTTPException) as e:
        await saga.claim("vendor_bills", "vb_klaim_adv2", "ap_pay_vendor_bill", precondition={"status": "posted"})
    d = e.value.detail
    assert e.value.status_code == 409 and d["code"] == "STATE_CHANGED" and d["current_status"] == "paid"
    assert "ap_pay_vendor_bill" not in d["message"] and "Muat ulang" in d["message"], d["message"]
