"""KM-T1 — isi permintaan Meja Insentif: Target & Aturan (`routers/incentive.py`).

PT tidak pernah diambil dari isi permintaan (`02_STANDAR.md` §3.4 N1): target dan komponen milik PT konteks pengguna.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class IncentiveTargetSave(BaseModel):
    sales_id: str
    period_type: str
    period: str
    target_sales_amount: float = 0
    target_collection_amount: float = 0
    target_new_customers: Optional[int] = 0
    notes: Optional[str] = ""


class IncentiveTargetCopy(BaseModel):
    period_type: str
    from_period: str
    to_period: str


class IncentiveComponentCreate(BaseModel):
    code: str
    name: str
    basis_period_type: str
    columns: List[str]
    taxable: Optional[bool] = True
    is_active: Optional[bool] = True


class IncentiveComponentUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    basis_period_type: Optional[str] = None
    columns: Optional[List[str]] = None
    taxable: Optional[bool] = None
    is_active: Optional[bool] = None


class IncentiveFactRebuild(BaseModel):
    date_from: Optional[str] = None


# ── KM-T3 — Lembar Insentif ──────────────────────────────────────────────────────────────────────────────────────────
#: Batas nominal di lapis skema (layanan memeriksa ulang: rupiah bulat, negatif hanya baris penyesuaian).
NOMINAL_MAKS = 1_000_000_000_000


class IncentiveSheetLineRef(BaseModel):
    """Baris yang langsung dipotret saat lembar dibuat (nominal diketik sesudahnya)."""
    sales_id: str
    component_id: str
    basis_period_type: str
    basis_period: str


class IncentiveSheetCreate(BaseModel):
    pay_period: str
    title: Optional[str] = ""
    lines: Optional[List[IncentiveSheetLineRef]] = None


class IncentiveSheetAdjustRef(BaseModel):
    sheet_id: str
    line_id: str


class IncentiveSheetLineAdd(BaseModel):
    sales_id: Optional[str] = None
    component_id: Optional[str] = None
    basis_period_type: Optional[str] = None
    basis_period: Optional[str] = None
    amount: Optional[float] = Field(None, ge=-NOMINAL_MAKS, le=NOMINAL_MAKS)
    note: Optional[str] = ""
    is_adjustment: bool = False
    adjusts: Optional[IncentiveSheetAdjustRef] = None


class IncentiveSheetLinePatch(BaseModel):
    amount: Optional[float] = Field(None, ge=-NOMINAL_MAKS, le=NOMINAL_MAKS)
    note: Optional[str] = None


class IncentiveSheetCorrection(BaseModel):
    line_id: str
    amount: float = Field(..., ge=-NOMINAL_MAKS, le=NOMINAL_MAKS)
    note: Optional[str] = ""


class IncentiveSheetApprove(BaseModel):
    corrections: Optional[List[IncentiveSheetCorrection]] = None


class IncentiveSheetReason(BaseModel):
    reason: Optional[str] = ""
