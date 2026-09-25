"""GRN Fase 2 — skema Kedatangan Barang (Penerimaan berbasis Surat Jalan)."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from schemas_scan_label import ManualLabelIn


class GRNCreateIn(BaseModel):
    partner_type: Literal["supplier", "makloon"]
    partner_id: str = Field(..., min_length=1)
    warehouse_id: str = Field(..., min_length=1)
    po_ids: List[str] = []
    mko_ids: List[str] = []


class GRNVersionIn(BaseModel):
    expected_version: int = Field(..., ge=1)


class GRNReasonIn(GRNVersionIn):
    reason: str = Field(..., min_length=3)


class GRNDnPatch(GRNVersionIn):
    number: Optional[str] = None
    date: Optional[str] = None
    date_text: Optional[str] = None
    supplier_name_printed: Optional[str] = None
    recipient_name: Optional[str] = None
    po_refs: Optional[List[str]] = None
    other_refs: Optional[List[Dict[str, str]]] = None
    vehicle_plate: Optional[str] = None
    annotations: Optional[List[Dict[str, Any]]] = None


class GRNDeclared(BaseModel):
    qty: Optional[float] = Field(None, ge=0)
    unit: str = ""
    rolls: Optional[int] = Field(None, ge=0)
    weight_kg: Optional[float] = Field(None, ge=0)
    weight_basis: Optional[Literal["gross", "net", "unknown"]] = None
    grade: str = ""
    lot: str = ""


class GRNTargetIn(BaseModel):
    type: Literal["po_task", "mko_step"]
    task_id: str = ""
    mko_id: str = ""
    step_seq: Optional[int] = Field(None, ge=1)


class GRNLineIn(GRNVersionIn):
    declared: GRNDeclared = GRNDeclared()
    is_non_stock: bool = False
    target: Optional[GRNTargetIn] = None
    decision: Optional[Literal["accept", "reject_line", "pending"]] = None
    item_code: str = ""
    description: str = ""
    po_ref: str = ""
    role: Literal["output", "byproduct"] = "output"


class GRNExpectedRoll(BaseModel):
    length: Optional[float] = Field(None, ge=0)
    length_unit: str = ""
    weight_kg: Optional[float] = Field(None, ge=0)
    lot: str = ""
    grade: str = ""


class GRNLinePatch(GRNVersionIn):
    declared: Optional[GRNDeclared] = None
    is_non_stock: Optional[bool] = None
    target: Optional[GRNTargetIn] = None
    clear_target: bool = False
    decision: Optional[Literal["accept", "reject_line", "pending"]] = None
    item_code: Optional[str] = None
    description: Optional[str] = None
    po_ref: Optional[str] = None
    role: Optional[Literal["output", "byproduct"]] = None
    verified: Optional[bool] = None          # hasil OCR = usulan; manusia mencentang "sudah dicek"
    expected_rolls: Optional[List[GRNExpectedRoll]] = None   # Fase 6 — daftar roll packing list (bisa dikoreksi)


class GRNCatalogIn(GRNVersionIn):
    supplier_sku: str = Field(..., min_length=1)
    supplier_item_name: str = ""


class GRNModeIn(BaseModel):
    entity_id: str = Field(..., min_length=1)
    mode: Literal["legacy", "grn"]
    reason: str = Field(..., min_length=5)


class GRNProfilePatch(BaseModel):
    number_locale: Optional[Literal["id", "en", "unknown"]] = None
    add_alias: Optional[str] = None
    remove_alias: Optional[str] = None
    remove_item_key: Optional[str] = None


class GRNScanIn(BaseModel):
    raw: str = ""
    manual: Optional[ManualLabelIn] = None
    expected_version: Optional[int] = None


class GRNCountRollIn(BaseModel):
    length: float = Field(0, ge=0)
    weight_kg: float = Field(0, ge=0)
    lot: str = ""
    grade: str = "A"
    expected_seq: Optional[int] = None       # Fase 6 — roll packing list yang sedang diukur
    expected_version: Optional[int] = None


class GRNResolveIn(GRNVersionIn):
    action: Literal["accept_note", "claim_supplier", "claim_makloon", "reject_goods"]
    reason: str = Field(..., min_length=3)
