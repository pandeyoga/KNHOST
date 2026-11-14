"""Skema input HRD H4 — Payroll."""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PayrollRunInput(BaseModel):
    entity_id: str
    period: str  # YYYY-MM


class PayRunInput(BaseModel):
    cash_account: Optional[str] = None  # kode akun kas/bank untuk disbursement
    account_id: str = ""               # PK-20 — rekening sumber (`bank_accounts`); kosong = rekening tunggal PT


class HrSettingsUpdate(BaseModel):
    settings: Dict[str, Any]
    scope: str = "entity"      # IX-06 — "entity" (badan usaha aktif) | "global" (peran lintas PT)
    reason: str = ""


class PayrollRejectInput(BaseModel):
    """Alasan pengembalian payroll ke draf — WAJIB (min 5 huruf, keputusan pemilik K-14 26 Okt)."""
    reason: str = Field(min_length=5, max_length=500)


class PayrollReasonInput(BaseModel):
    """PK-22 — alasan batal / void proses gaji (min 5 huruf, K-14). Panjang diperiksa layanan (pesan Indonesia)."""
    reason: str = Field(default="", max_length=500)


class RemittanceInput(BaseModel):
    """PK-22 (FY-07) — setoran kewajiban BPJS / PPh 21. PT = PT aktif (bukan isi permintaan, `02` N1)."""
    kind: str                      # "bpjs" | "pph21"
    period: str                    # YYYY-MM (masa gaji yang disetor)
    amount: float
    paid_date: str                 # YYYY-MM-DD = tanggal jurnal
    account_id: str = ""           # rekening sumber (`bank_accounts`); kosong = rekening tunggal PT jenis kas itu
    cash_type: str = "kas_besar"   # "kas_besar" (bank) | "kas_kecil"
    reference: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=500)
