"""L01 LN-012 — API master grade. Hak terpisah: lihat · tambah · ubah · aktif/nonaktif."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from dependencies import audit, require_permission
from services import grade_master_service as gm

router = APIRouter(prefix="/api")


class GradeIn(BaseModel):
    code: str = Field(..., max_length=2)
    name: str = Field(..., max_length=60)
    rank: int
    description: Optional[str] = ""
    max_points: Optional[float] = None
    active: bool = True


class GradePatch(BaseModel):
    name: Optional[str] = Field(None, max_length=60)
    rank: Optional[int] = None
    description: Optional[str] = None
    max_points: Optional[float] = None


class GradeActiveIn(BaseModel):
    active: bool
    reason: str = Field(..., max_length=300)


@router.get("/master/grades")
async def list_grades(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "grade_master", "view")
    return await gm.list_all()


@router.post("/master/grades")
async def create_grade(payload: GradeIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "grade_master", "create")
    row = await gm.create(payload.model_dump(), actor.get("name", ""))
    await audit(actor.get("name", ""), "create", "md_grades", row["code"], {"rank": row["rank"]})
    return row


@router.patch("/master/grades/{code}")
async def update_grade(code: str, payload: GradePatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "grade_master", "update")
    row = await gm.update(code, payload.model_dump(exclude_unset=True), actor.get("name", ""))
    await audit(actor.get("name", ""), "update", "md_grades", code.upper(), payload.model_dump(exclude_unset=True))
    return row


@router.post("/master/grades/{code}/active")
async def set_grade_active(code: str, payload: GradeActiveIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "grade_master", "activate")
    row = await gm.set_active(code, payload.active, payload.reason, actor.get("name", ""))
    await audit(actor.get("name", ""), "activate" if payload.active else "deactivate", "md_grades",
                code.upper(), {"reason": payload.reason})
    return row
