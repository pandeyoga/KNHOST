"""L11 LN-110/LN-113 — Pusat Export: dataset, preview, job export, unduh ber-izin ulang."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core_utils import new_id, now_iso
from db import db
from dependencies import audit, require_permission
from entity_scope import entity_ctx
from services import export_engine as eng
from services.export_registry import DATASETS, coverage
from services.storage_service import STORAGE_DIR

router = APIRouter(prefix="/api/export-center", tags=["export-center"])
log = logging.getLogger("export_center")
EXPORT_DIR = STORAGE_DIR / "exports"
JOB_TTL_HOURS = 24
_TASKS: set = set()


class ExportSpec(BaseModel):
    dataset: str
    columns: List[str] = Field(default_factory=list)
    filter: Optional[Dict[str, Any]] = None
    date_field: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    sort: List[Dict[str, str]] = Field(default_factory=list)
    entity_scope: str = "active"


class PreviewIn(ExportSpec):
    limit: int = Field(50, ge=1, le=200)


class JobIn(ExportSpec):
    format: str = Field("xlsx", pattern="^(xlsx|csv)$")
    rows_per_sheet: int = Field(eng.EXCEL_MAX_ROWS, ge=100, le=eng.EXCEL_MAX_ROWS)


def _public_col(c: Dict[str, Any]) -> Dict[str, Any]:
    return {k: c.get(k) for k in ("key", "label", "type", "source", "source_label", "filterable")}


@router.get("/datasets")
async def list_datasets(request: Request) -> Any:
    user = await require_permission(request, "data_export", "view")
    out, unavailable = [], []
    for ds in DATASETS:
        why = await eng.dataset_access(user, ds)
        if why:
            unavailable.append({"id": ds["id"], "label": ds["label"], "group": ds["group"], "reason": why})
            continue
        allowed, denied = await eng.resolve_columns(user, ds)
        out.append({"id": ds["id"], "label": ds["label"], "group": ds["group"], "grain": ds["grain"],
                    "key": ds["key"], "date_fields": [_public_col(d) for d in ds["date_fields"]],
                    "columns": [_public_col(c) for c in allowed],
                    "hidden_columns": [{"key": d["key"], "label": d["label"], "reason": d["reason"]} for d in denied],
                    "joins": [{"id": j["id"], "label": j["label"]} for j in ds.get("joins", [])]})
    return {"datasets": out, "unavailable": unavailable, "comparators": eng.CMP_LABEL,
            "limits": {"max_rows": eng.MAX_EXPORT_ROWS, "excel_rows_per_sheet": eng.EXCEL_MAX_ROWS,
                       "max_conditions": eng.MAX_CONDITIONS, "max_depth": eng.MAX_DEPTH}}


@router.get("/coverage")
async def get_coverage(request: Request) -> Any:
    await require_permission(request, "data_export", "view")
    return await coverage(db)


@router.post("/preview")
async def preview(payload: PreviewIn, request: Request) -> Any:
    user = await require_permission(request, "data_export", "view")
    ctx = await entity_ctx(request)
    plan = await eng.build_plan(payload.dict(), user, ctx)
    total = await eng.count(plan)
    rows = await eng.fetch(plan, 0, payload.limit)
    return {"columns": [_public_col(c) for c in plan["columns"]], "rows": rows, "total": total,
            "shown": len(rows), "truncated_preview": total > len(rows), "filter_text": plan["filter_text"],
            "date_text": plan["date_text"], "sort_text": plan["sort_text"], "entity_ids": plan["entity_ids"],
            "grain": plan["ds"]["grain"], "hidden_columns": plan["denied"]}


def _job_public(j: Dict[str, Any]) -> Dict[str, Any]:
    return {k: j.get(k) for k in ("id", "dataset", "dataset_label", "format", "status", "total_rows", "written_rows",
                                  "partitions", "file_name", "size", "created_at", "finished_at", "expires_at",
                                  "error", "filter_text", "date_text", "retry_of", "entity_ids", "columns")}


async def _run(job: Dict[str, Any], plan: Dict[str, Any], rows_per_sheet: int) -> None:
    await db.export_jobs.update_one({"id": job["id"]}, {"$set": {"status": "running"}})
    try:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = EXPORT_DIR / f"{job['id']}.{job['format']}"
        res = await eng.write_file(job, plan, str(path), rows_per_sheet)
        await db.export_jobs.update_one({"id": job["id"]}, {"$set": {
            "status": "done", **res, "file_path": str(path), "size": path.stat().st_size,
            "finished_at": now_iso(), "count_matches": res["written_rows"] == job["total_rows"]}})
    except Exception as exc:  # noqa: BLE001 — job gagal dicatat, bukan senyap
        log.exception("export job %s gagal", job["id"])
        await db.export_jobs.update_one({"id": job["id"]}, {"$set": {"status": "failed", "error": str(exc)[:300],
                                                                      "finished_at": now_iso()}})


async def _create_job(spec: Dict[str, Any], fmt: str, rows_per_sheet: int, request: Request,
                      retry_of: str = "") -> Dict[str, Any]:
    user = await require_permission(request, "data_export", "export")
    ctx = await entity_ctx(request)
    plan = await eng.build_plan(spec, user, ctx)
    total = await eng.count(plan)
    if total > eng.MAX_EXPORT_ROWS:
        raise HTTPException(status_code=413, detail={"code": "EXPORT_TOO_LARGE", "message": (
            f"{total:,} baris melebihi batas {eng.MAX_EXPORT_ROWS:,}. Persempit periode/filter; "
            "data tidak dipotong diam-diam.").replace(",", ".")})
    created = datetime.now(timezone.utc)
    ds = plan["ds"]
    job = {"id": new_id("exj"), "user_id": user["id"], "user_name": user.get("name", ""), "role": user.get("role"),
           "dataset": ds["id"], "dataset_label": ds["label"], "spec": spec, "format": fmt,
           "rows_per_sheet": rows_per_sheet, "columns": [c["key"] for c in plan["columns"]], "status": "queued",
           "total_rows": total, "written_rows": 0, "partitions": [], "entity_ids": plan["entity_ids"],
           "filter_text": plan["filter_text"], "date_text": plan["date_text"], "retry_of": retry_of,
           "file_name": f"{ds['id']}_{created.strftime('%Y%m%d_%H%M%S')}.{fmt}",
           "created_at": created.isoformat(), "expires_at": (created + timedelta(hours=JOB_TTL_HOURS)).isoformat()}
    await db.export_jobs.insert_one(dict(job))
    await audit(user.get("name", ""), "export.create", "export_jobs", job["id"],
                {"dataset": ds["id"], "columns": job["columns"], "rows": total, "format": fmt,
                 "entities": plan["entity_ids"], "retry_of": retry_of})
    task = asyncio.create_task(_run(job, plan, rows_per_sheet))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return _job_public(job)


@router.post("/jobs")
async def create_job(payload: JobIn, request: Request) -> Any:
    spec = payload.dict(exclude={"format", "rows_per_sheet"})
    return await _create_job(spec, payload.format, payload.rows_per_sheet, request)


@router.get("/jobs")
async def list_jobs(request: Request) -> Any:
    user = await require_permission(request, "data_export", "view")
    docs = await db.export_jobs.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    now = now_iso()
    for d in docs:
        if d["status"] == "done" and d.get("expires_at", "") < now:
            d["status"] = "expired"
    return {"items": [_job_public(d) for d in docs]}


async def _own_job(job_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    job = await db.export_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job or job.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Pekerjaan export tidak ditemukan")
    return job


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> Any:
    user = await require_permission(request, "data_export", "view")
    return _job_public(await _own_job(job_id, user))


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, request: Request) -> Any:
    user = await require_permission(request, "data_export", "export")
    job = await _own_job(job_id, user)
    # Spesifikasi lama divalidasi ulang dengan izin SAAT INI — retry tidak memperluas scope.
    return await _create_job(job["spec"], job["format"], job.get("rows_per_sheet") or eng.EXCEL_MAX_ROWS,
                             request, retry_of=job_id)


@router.get("/jobs/{job_id}/download")
async def download_job(job_id: str, request: Request) -> Any:
    user = await require_permission(request, "data_export", "export")
    job = await _own_job(job_id, user)
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail={"code": "JOB_NOT_READY", "message": "File belum siap"})
    if job.get("expires_at", "") < now_iso():
        raise HTTPException(status_code=410, detail={"code": "JOB_EXPIRED",
                                                     "message": "Masa unduh habis (24 jam). Jalankan ulang export."})
    # LN-113-T02 — hak diperiksa lagi saat unduh: dataset, kolom, dan badan usaha.
    ctx = await entity_ctx(request)
    from services.export_registry import DATASET_BY_ID
    ds = DATASET_BY_ID.get(job["dataset"])
    why = await eng.dataset_access(user, ds) if ds else "dataset dihapus"
    allowed = {c["key"] for c in (await eng.resolve_columns(user, ds))[0]} if ds and not why else set()
    lost_cols = [k for k in job["columns"] if k not in allowed]
    lost_ent = [e for e in job.get("entity_ids") or [] if e not in ctx.allowed_entity_ids]
    if why or lost_cols or lost_ent:
        await audit(user.get("name", ""), "export.download_denied", "export_jobs", job_id,
                    {"reason": why, "columns": lost_cols, "entities": lost_ent})
        raise HTTPException(status_code=403, detail={
            "code": "ACCESS_CHANGED", "message": "Hak akses Anda berubah sejak export dibuat; file tidak dapat diunduh.",
            "fields": lost_cols, "entities": lost_ent})
    path = Path(job.get("file_path") or "")
    if not path.is_file() or EXPORT_DIR not in path.parents:
        raise HTTPException(status_code=410, detail={"code": "FILE_GONE", "message": "File sudah tidak tersedia"})
    await audit(user.get("name", ""), "export.download", "export_jobs", job_id,
                {"dataset": job["dataset"], "rows": job.get("written_rows")})
    media = "text/csv" if job["format"] == "csv" else \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(str(path), media_type=media, filename=job["file_name"])
