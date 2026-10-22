"""Kontrak bersama retur PER ROLL (permintaan pemilik 23 Okt 2026) — dipakai retur pelanggan, retur ke supplier dan
retur antar-PT supaya ketiganya mencatat alasan, kondisi, checklist & keputusan roll dengan bentuk yang sama.

Modul ini sengaja tanpa impor skema lain: `schemas.py` mengimpor ulang `schemas_purchasing`/`schemas_interco`,
jadi model bersama harus tinggal di modul daun supaya tidak terjadi impor melingkar.
"""
from typing import List

from pydantic import BaseModel


class ReturnRollDetail(BaseModel):
    """Detail klaim satu roll: alasan, kondisi & checklist."""
    reason:          str = ""
    condition:       str = "ok"      # ok | damaged
    hangtag_missing: bool = False
    cut_by_customer: bool = False    # retur jual: dipotong pelanggan · retur supplier/antar-PT: roll sudah dipotong
    note:            str = ""


class ReturnRollDecisionIn(BaseModel):
    roll_id: str
    decision: str                    # accept | reject
    reason: str = ""


class ReturnRollDecisionsIn(BaseModel):
    decisions: List[ReturnRollDecisionIn]


class SupplierRollRejectIn(BaseModel):
    """Roll yang DITOLAK supplier saat ia menerima sebagian retur (RMA)."""
    roll_id: str
    reason: str = ""
