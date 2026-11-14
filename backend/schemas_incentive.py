"""KM-T1 — isi permintaan Meja Insentif: Target & Aturan (`routers/incentive.py`).

PT tidak pernah diambil dari isi permintaan (`02_STANDAR.md` §3.4 N1): target dan komponen milik PT konteks pengguna.
"""
from typing import List, Optional

from pydantic import BaseModel


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
