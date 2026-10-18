"""Sampel Uji OCR — `/api/ocr-samples`: kumpulan SJ nyata + kunci jawaban untuk mengukur ketepatan baca."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

from dependencies import audit, require_permission
from entity_scope import entity_ctx
from services import ocr_sample_service as svc

router = APIRouter(prefix="/api/ocr-samples")
M = "goods_receipt"


class SampleFromGrnIn(BaseModel):
    label: str = ""


class SamplePatchIn(BaseModel):
    label: Optional[str] = None
    answer: Optional[Dict[str, Any]] = None


class RunIn(BaseModel):
    sample_ids: List[str] = []


async def _ctx(request: Request, action: str):
    actor = await require_permission(request, M, action)
    ctx = await entity_ctx(request)
    return actor, ctx, ctx.active_entity_id or ""


@router.get("")
async def list_samples(request: Request) -> List[Dict[str, Any]]:
    _, _, ent = await _ctx(request, "view")
    return await svc.list_samples(ent)


@router.post("/from-grn/{grn_id}")
async def from_grn(grn_id: str, body: SampleFromGrnIn, request: Request) -> Dict[str, Any]:
    actor, ctx, ent = await _ctx(request, "review")
    doc = await svc.create_from_grn(grn_id, body.label, actor, ctx)
    await audit(actor["name"], "ocr_sample_created", "ocr_sample", doc["id"], {"grn_id": grn_id}, scope_entity_id=ent)
    return doc


@router.get("/runs")
async def list_runs(request: Request) -> List[Dict[str, Any]]:
    _, _, ent = await _ctx(request, "view")
    return await svc.list_runs(ent)


@router.post("/runs")
async def start_run(body: RunIn, request: Request) -> Dict[str, Any]:
    actor, _, ent = await _ctx(request, "review")
    run = await svc.start_run(ent, body.sample_ids, actor["name"])
    await audit(actor["name"], "ocr_sample_run_started", "ocr_sample_run", run["id"], {"samples": run["total"]}, scope_entity_id=ent)
    return run


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> Dict[str, Any]:
    _, _, ent = await _ctx(request, "view")
    return await svc.get_run(run_id, ent)


@router.patch("/{sample_id}")
async def patch_sample(sample_id: str, body: SamplePatchIn, request: Request) -> Dict[str, Any]:
    actor, _, ent = await _ctx(request, "review")
    doc = await svc.update(sample_id, ent, body.label, body.answer)
    await audit(actor["name"], "ocr_sample_updated", "ocr_sample", sample_id, {"answer": body.answer is not None}, scope_entity_id=ent)
    return doc


@router.delete("/{sample_id}")
async def delete_sample(sample_id: str, request: Request) -> Dict[str, Any]:
    actor, _, ent = await _ctx(request, "review")
    await svc.delete(sample_id, ent)
    await audit(actor["name"], "ocr_sample_deleted", "ocr_sample", sample_id, {}, scope_entity_id=ent)
    return {"ok": True}


@router.get("/{sample_id}/files/{page}")
async def sample_file(sample_id: str, page: int, request: Request) -> Response:
    _, _, ent = await _ctx(request, "view")
    data, ct = await svc.file_bytes(sample_id, ent, page)
    return Response(content=data, media_type=ct, headers={"Cache-Control": "private, max-age=300"})
