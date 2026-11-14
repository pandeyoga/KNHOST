"""FINANCE — Anggaran (Budget) vs Komitmen vs Realisasi + Budget Control (R6.3).

Akses: permission resource **"budget"** (admin: penuh; manager: view/create/update).
Koleksi `budgets` (+ `fin_budget_rules`) ter-scope per entitas. Respons OBJEK telanjang (kontrak KN3).

Endpoint:
- GET    /api/finance/budgets                  → daftar anggaran (filter year, dimension)
- POST   /api/finance/budgets                  → buat anggaran (dimension account|category)
- PATCH  /api/finance/budgets/{budget_id}      → ubah anggaran (+ `reason`; PK-39: riwayat sebelum/sesudah)
- DELETE /api/finance/budgets/{budget_id}      → hapus anggaran (`?reason=`; PK-39: riwayat `deleted`)
- GET    /api/finance/budgets/{budget_id}/history → PK-39: riwayat pagu (terbaru dulu)
- GET    /api/finance/budget-vs-actual         → anggaran vs komitmen vs realisasi + alert + rules
- GET    /api/finance/budget-keys              → pilihan kunci (akun COA / kategori beban)
- GET    /api/finance/budget-rules             → kebijakan over-budget per entitas (PK-39: `mode` dari Pusat Pengaturan)
- PUT    /api/finance/budget-rules             → set sakelar lain (admin); `mode` → 400 (diatur di Pusat Pengaturan)
- POST   /api/finance/budget-check             → pratinjau sisa anggaran utk nominal tertentu
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel, Field

from dependencies import require_permission, audit
from entity_scope import entity_ctx, guard_doc, resolve_list_scope, scope_meta
from schemas import BudgetCreate, BudgetUpdate
from services import budget_service as budget
from services import cash_advance_service as ca_svc
from services import gl_service

router = APIRouter(prefix="/api")


class BudgetRulesIn(BaseModel):
    entity_id: Optional[str] = None
    mode: Optional[str] = None                     # PK-39 — ditolak 400: mode = pengaturan `budget.mode`
    warn_threshold_pct: Optional[float] = Field(None, ge=0, le=100)
    unbudgeted_action: Optional[str] = None        # allow | warn | block
    enforce_po_create: Optional[bool] = None
    enforce_po_approve: Optional[bool] = None


class BudgetCheckIn(BaseModel):
    entity_id: Optional[str] = None
    dimension: str = "account"
    key: str = ""
    amount: float = 0
    date: Optional[str] = ""
    # PK-39 — pratinjau form kas: `source="cash_out"` + `category` → sasaran dihitung server (akun lawan kas keluar).
    source: str = ""
    category: str = ""


async def _scope(request: Request, entity_id: Optional[str]) -> Dict[str, Any]:
    ctx = await entity_ctx(request)
    return resolve_list_scope("budgets", {}, ctx, entity_id)


async def _entity_or_active(request: Request, entity_id: Optional[str]) -> str:
    ctx = await entity_ctx(request)
    eid = entity_id or ctx.active_entity_id or "ent_ksc"
    if eid == "all":
        eid = ctx.active_entity_id or "ent_ksc"
    if eid not in (ctx.allowed_entity_ids or [eid]):
        raise HTTPException(status_code=403, detail="Entitas di luar akses Anda.")
    return eid


@router.get("/finance/budgets")
async def list_budgets(
    request: Request,
    year: Optional[int] = Query(None),
    dimension: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    await require_permission(request, "budget", "view")
    scope = await _scope(request, entity_id)
    return await budget.list_budgets(scope, year, dimension)


@router.post("/finance/budgets")
async def create_budget(request: Request, payload: BudgetCreate) -> Dict[str, Any]:
    actor = await require_permission(request, "budget", "create")
    entity_id = await _entity_or_active(request, payload.entity_id)
    try:
        doc = await budget.create_budget(payload.model_dump(), entity_id, actor)
    except budget.DuplicateBudget as e:   # PK-39 (FY-12) — pagu kembar, juga dari indeks unik saat bersamaan
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "budget_created", "budget", doc["id"],
                {"dimension": doc["dimension"], "key": doc["key"], "amount": doc["amount"]},
                scope_entity_id=entity_id)
    return doc


@router.patch("/finance/budgets/{budget_id}")
async def update_budget(request: Request, budget_id: str, patch: BudgetUpdate) -> Dict[str, Any]:
    actor = await require_permission(request, "budget", "update")
    scope = await _scope(request, None)
    body = patch.model_dump(exclude_none=True)
    reason = str(body.pop("reason", "") or "").strip()
    try:   # PK-39 (FY-12) — layanan menulis riwayat pagu + jejak audit bernilai sebelum/sesudah (dulu kosong)
        res = await budget.update_budget(budget_id, body, scope, actor, reason)
    except budget.DuplicateBudget as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not res:
        raise HTTPException(status_code=404, detail="Anggaran tidak ditemukan.")
    return res


@router.delete("/finance/budgets/{budget_id}")
async def delete_budget(request: Request, budget_id: str, reason: str = Query("")) -> Dict[str, Any]:
    actor = await require_permission(request, "budget", "delete")
    scope = await _scope(request, None)
    ok = await budget.delete_budget(budget_id, scope, actor, (reason or "").strip())   # + riwayat & jejak audit
    if not ok:
        raise HTTPException(status_code=404, detail="Anggaran tidak ditemukan.")
    return {"ok": True, "deleted": budget_id}


@router.get("/finance/budgets/{budget_id}/history")
async def budget_history(request: Request, budget_id: str) -> List[Dict[str, Any]]:
    """PK-39 (FY-12) — riwayat pagu terbaru dulu (buat · ubah · hapus; sebelum/sesudah, alasan, oleh)."""
    await require_permission(request, "budget", "view")
    eid, rows = await budget.budget_history(budget_id)
    # Dijaga PT pagu (penugasan akun; pagu yang sudah dihapus dijaga lewat PT di riwayatnya).
    await guard_doc(request, "budgets", {"entity_id": eid} if eid is not None else None, strict=False,
                    not_found="Pagu tidak ditemukan.")
    return rows


@router.get("/finance/budget-vs-actual")
async def budget_vs_actual(
    request: Request,
    year: int = Query(...),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    await require_permission(request, "budget", "view")
    ctx = await entity_ctx(request)
    # Realisasi & komitmen diturunkan dari jurnal/PO/LPJ → scope dgn koleksi ber-entity_id.
    scope = resolve_list_scope("journal_entries", {}, ctx, entity_id)
    rules_entity = entity_id if (entity_id and entity_id != "all") else (ctx.active_entity_id or "")
    return {**(await budget.budget_vs_actual(scope, year, entity_id_for_rules=rules_entity)),
            "scope_meta": await scope_meta(ctx, entity_id)}   # PK-16


@router.get("/finance/budget-keys")
async def budget_keys(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Pilihan kunci anggaran: akun COA (income/expense/inventory) + kategori beban."""
    await require_permission(request, "budget", "view")
    await gl_service.seed_default_coa()
    accts = await gl_service.list_accounts(active_only=True, entity_id=entity_id or None)
    accounts = [{"code": a["code"], "name": a["name"], "type": a.get("type", "")}
                for a in accts if a.get("is_postable")
                and (a.get("type") in ("income", "expense") or a.get("code", "").startswith("1-13"))]
    accounts.sort(key=lambda x: x["code"])
    cats = await ca_svc.list_expense_categories(active_only=True, entity_id=entity_id or "")
    categories = [{"code": c.get("code", ""), "label": c.get("label", ""),
                   "account_code": c.get("account_code", "")} for c in cats]
    eid = entity_id if entity_id and entity_id != "all" else ((await entity_ctx(request)).active_entity_id or "")
    return {"accounts": accounts, "categories": categories,
            "default_po_account": await budget.inventory_account(eid)}   # PK-39 — pemetaan persediaan PT


@router.get("/finance/budget-rules")
async def get_budget_rules(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "budget", "view")
    eid = await _entity_or_active(request, entity_id)
    return await budget.get_rules(eid)


@router.put("/finance/budget-rules")
async def set_budget_rules(request: Request, payload: BudgetRulesIn) -> Dict[str, Any]:
    actor = await require_permission(request, "budget", "configure")
    eid = await _entity_or_active(request, payload.entity_id)
    if payload.mode is not None:   # PK-39 (K-12) — satu editor mode: Pusat Pengaturan (`budget.mode`)
        raise HTTPException(status_code=400, detail=budget.mode_moved_message())
    try:
        res = await budget.set_rules(eid, payload.model_dump(exclude_none=True), actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "budget_rules_updated", "budget", eid,
                {k: res.get(k) for k in ("warn_threshold_pct", "unbudgeted_action", "enforce_po_create",
                                         "enforce_po_approve")})
    return res


@router.post("/finance/budget-check")
async def check_budget(request: Request, payload: BudgetCheckIn) -> Dict[str, Any]:
    """Pratinjau kontrol anggaran (dipakai UI PO sebelum submit)."""
    await require_permission(request, "budget", "view")
    eid = await _entity_or_active(request, payload.entity_id)
    dimension, key, amount = payload.dimension, payload.key, payload.amount
    if payload.source == "cash_out":
        targets = await budget.cash_budget_targets({"direction": "out", "ref_type": "", "entity_id": eid,
                                                    "category": payload.category, "amount": payload.amount})
        if not targets:   # akun lawan bukan beban → kas keluar ini tidak diperiksa
            return {"applies": False, "entity_id": eid}
        dimension, key, amount = targets[0]["dimension"], targets[0]["key"], targets[0]["amount"]
    elif payload.source:
        raise HTTPException(status_code=400, detail="Jenis pratinjau anggaran tidak dikenal.")
    try:
        return {"applies": True, **await budget.check_budget(eid, dimension, key, amount, date=payload.date or "")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
