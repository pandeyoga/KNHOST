"""Skema input HRD H4 — Payroll."""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PayrollRunInput(BaseModel):
    entity_id: str
    period: str  # YYYY-MM


class PayRunInput(BaseModel):
    cash_account: Optional[str] = None  # kode akun kas/bank untuk disbursement


class HrSettingsUpdate(BaseModel):
    settings: Dict[str, Any]
    scope: str = "entity"      # IX-06 — "entity" (badan usaha aktif) | "global" (peran lintas PT)
    reason: str = ""


class PayrollRejectInput(BaseModel):
    """Alasan pengembalian payroll ke draf — WAJIB (min 5 huruf, keputusan pemilik K-14 26 Okt)."""
    reason: str = Field(min_length=5, max_length=500)
