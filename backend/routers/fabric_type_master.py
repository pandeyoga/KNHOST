"""L01 — API master jenis kain (tambah dari laporan impor)."""
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from dependencies import audit, current_user, require_any_permission
from services import fabric_type_master_service as fts

router = APIRouter(prefix="/api")


class FabricTypeIn(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=60)
    control_uom: str
    description: str = ""


@router.get("/master/fabric-types")
async def list_fabric_types(request: Request) -> List[Dict[str, Any]]:
    await current_user(request)
    return await fts.list_all()


@router.post("/master/fabric-types")
async def create_fabric_type(payload: FabricTypeIn, request: Request) -> Dict[str, Any]:
    actor = await require_any_permission(request, [("product", "import"), ("settings", "manage")])
    row = await fts.create(payload.model_dump(), actor.get("name", ""))
    await audit(actor.get("name", ""), "create", "md_fabric_types", row["code"], {"control_uom": row["control_uom"]})
    return row
