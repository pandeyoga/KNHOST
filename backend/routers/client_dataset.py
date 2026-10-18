"""L01 LN-011 — impor dataset client (artikel · tahap · jenis kain · supplier/warna)."""
from typing import Any, Dict, List

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response

from dependencies import audit, require_permission
from services import client_dataset_service as cds

router = APIRouter(prefix="/api/client-dataset")


@router.get("/template")
async def template(request: Request) -> Response:
    await require_permission(request, "product", "import")
    ex = ["KNKNT0005", "ALICE KNIT (94139 - 45)", "", "finished", "knit", "Knitting", "10",
          "Kanda Fabric", "AK-94139", "Alice Knit", "Hitam", "BLK-01", "Hitam Pekat"]
    body = ",".join(cds.TEMPLATE_HEADER) + "\n" + ",".join(f'"{v}"' for v in ex) + "\n"
    return Response(content=body.encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=template_dataset_client.csv"})


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "import")
    rows = cds.parse(await file.read(), file.filename or "")
    report = await cds.dry_run(rows)
    batch = await cds.save_batch(rows, report, file.filename or "", actor.get("name", ""))
    return {**batch, "report": {k: v for k, v in report.items() if k != "plan"}}


@router.get("/batches")
async def batches(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "import")
    return await cds.list_batches()


@router.get("/batches/{batch_id}")
async def batch(batch_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "import")
    b = await cds.get_batch(batch_id)
    if b.get("report"):
        b["report"].pop("plan", None)
    return b


@router.post("/batches/{batch_id}/commit")
async def commit(batch_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "import")
    out = await cds.commit(batch_id, actor.get("name", ""))
    await audit(actor.get("name", ""), "client_dataset_commit", "client_dataset_imports", batch_id, out["summary"])
    return out


@router.post("/batches/{batch_id}/rollback")
async def rollback(batch_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "import")
    out = await cds.rollback(batch_id, actor.get("name", ""))
    await audit(actor.get("name", ""), "client_dataset_rollback", "client_dataset_imports", batch_id, {})
    return out
