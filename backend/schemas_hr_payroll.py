"""Skema input HRD H4 — Payroll."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PayrollRunInput(BaseModel):
    entity_id: str
    period: str  # YYYY-MM — format diperiksa layanan (PY-13: 400 "Periode harus berbentuk TTTT-BB, mis. 2026-10.")
    run_type: str = "regular"   # PY-T1 — "regular" | "thr" | "susulan"


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


class PayComponentCreate(BaseModel):
    """PY-T1 — komponen gaji baru PT aktif (`02` N1: PT = PT aktif, bukan isi permintaan)."""
    code: str = Field(max_length=30)
    name: str = Field(max_length=80)
    kind: str                                  # "pendapatan" | "potongan"
    calc: str = "masukan"                      # komponen baru: hanya "masukan" (PY-T2/PY-T3 menambah cara lain)
    bucket: str = ""                           # kosong = kolom bawaan jenisnya (other_earnings / other_deductions)
    taxable: Optional[bool] = None
    in_bpjs_base: bool = False                 # disimpan; belum dipakai mesin sampai PY-T3
    in_overtime_base: bool = False
    prorate: bool = False
    account_code: str = Field(default="", max_length=20)
    allowed_run_types: List[str] = ["regular", "susulan"]
    sort: int = 300
    is_active: bool = True


class PayComponentPatch(BaseModel):
    """PY-T1 — ubah komponen; field yang tidak dikirim tidak berubah."""
    code: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=80)
    kind: Optional[str] = None
    calc: Optional[str] = None
    bucket: Optional[str] = None
    taxable: Optional[bool] = None
    in_bpjs_base: Optional[bool] = None
    in_overtime_base: Optional[bool] = None
    prorate: Optional[bool] = None
    statutory_code: Optional[str] = None
    account_code: Optional[str] = Field(default=None, max_length=20)
    allowed_run_types: Optional[List[str]] = None
    sort: Optional[int] = None
    is_active: Optional[bool] = None


class PayInputCreate(BaseModel):
    """PY-T1 — masukan manual (`pending` sampai disahkan). PT = PT aktif."""
    employee_id: str
    component_code: str
    pay_period: str
    amount: float
    label: str = Field(default="", max_length=120)
    basis_period: str = ""
    reason: str = Field(default="", max_length=500)


class PayInputCancel(BaseModel):
    reason: str = Field(default="", max_length=500)


class HolidayCreate(BaseModel):
    """PY-T3 — hari libur PT aktif (`02` N1: PT = PT aktif). Format & isi diperiksa layanan (pesan Indonesia)."""
    date: str = Field(default="", max_length=20)
    name: str = Field(default="", max_length=200)
    kind: str = Field(default="", max_length=30)


class TaxOpeningInput(BaseModel):
    """PY-T3 (PY-12) — saldo awal pajak karyawan di PT aktif untuk satu tahun. Diperiksa layanan:
    400 "Jumlah masa harus 1 sampai 11."; nominal tidak negatif."""
    year: Any = None
    months: Any = None
    tax_gross: Any = 0
    pension_deduction: Any = 0
    pph21_withheld: Any = 0
    note: str = Field(default="", max_length=300)
