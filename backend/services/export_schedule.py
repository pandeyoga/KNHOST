"""L11 — Export terjadwal: template berjalan mingguan/bulanan dengan identitas & hak PEMILIK saat itu."""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core_utils import now_iso
from db import db
from dependencies import permission_matrix
from services.ai_schedules import ScheduleError, ctx_for
from services.ai_schedules import next_run as _next_weekly_or_daily
from services.analytics_time import now_wib

log = logging.getLogger("export_schedule")


def next_run(cfg: Dict[str, Any], after: Optional[datetime] = None) -> str:
    if cfg["frequency"] == "weekly":
        return _next_weekly_or_daily("weekly", int(cfg.get("weekday") or 0), cfg["time"], after)
    now = (after or now_wib()).astimezone(now_wib().tzinfo)
    h, m = (int(x) for x in cfg["time"].split(":"))
    cand = now.replace(day=int(cfg.get("day_of_month") or 1), hour=h, minute=m, second=0, microsecond=0)
    if cand <= now:
        y, mo = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        cand = cand.replace(year=y, month=mo)
    return cand.astimezone(timezone.utc).isoformat()


def rolling_period(frequency: str, today: date) -> Dict[str, str]:
    """Minggu lalu (Senin–Minggu) atau bulan lalu penuh, tanggal WIB inklusif."""
    if frequency == "weekly":
        start = today - timedelta(days=today.weekday() + 7)
        return {"date_from": start.isoformat(), "date_to": (start + timedelta(days=6)).isoformat()}
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return {"date_from": last_prev.replace(day=1).isoformat(), "date_to": last_prev.isoformat()}


def build(cfg: Dict[str, Any], ctx) -> Dict[str, Any]:
    try:
        h, m = (int(x) for x in cfg["time"].split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except (ValueError, AssertionError):
        raise HTTPException(status_code=422, detail="Jam jadwal harus HH:MM")
    out = {**cfg, "time": f"{h:02d}:{m:02d}", "entity_id": ctx.active_entity_id, "view_all": bool(ctx.view_all),
           "updated_at": now_iso()}
    out["next_run_at"] = next_run(out) if out.get("active") else ""
    return out


async def _owner(t: Dict[str, Any]) -> Dict[str, Any]:
    user = await db.users.find_one({"id": t["user_id"]}, {"_id": 0, "password": 0, "password_hash": 0})
    if not user or user.get("status", "active") != "active":
        raise ScheduleError("Pemilik template tidak aktif.")
    acts = ((await permission_matrix()).get(user.get("role"), {}) or {}).get("data_export") or []
    if "export" not in acts:
        raise ScheduleError("Pemilik template tidak lagi punya izin export.")
    return user


async def run_template(t: Dict[str, Any], trigger: str = "schedule") -> Dict[str, Any]:
    from routers.export_center import create_job_for
    from services.notification_service import create_notification
    s = t["schedule"]
    try:
        user = await _owner(t)
        ctx = await ctx_for(user, s["entity_id"], bool(s.get("view_all")))
        spec = dict(t["spec"])
        if s.get("period", "previous") == "previous" and spec.get("date_field"):
            spec.update(rolling_period(s["frequency"], now_wib().date()))
        job = await create_job_for(user, ctx, spec, t["format"], t.get("rows_per_sheet") or 1_000_000,
                                   trigger=trigger, template_id=t["id"])
        await db.export_templates.update_one({"id": t["id"]}, {"$set": {
            "last_scheduled_job": job["id"], "last_schedule_error": "", "last_run_at": now_iso()},
            "$inc": {"run_count": 1}})
        return job
    except (ScheduleError, HTTPException) as exc:
        msg = exc.detail.get("message") if isinstance(getattr(exc, "detail", None), dict) else str(getattr(exc, "detail", exc))
        await db.export_templates.update_one({"id": t["id"]}, {"$set": {"last_schedule_error": msg}})
        await create_notification(notif_type="export_schedule", title=f"Export terjadwal gagal: {t['name']}",
                                  body=msg[:500], severity="warning", link="export-center", entity_id=s.get("entity_id"),
                                  recipient_user=t["user_id"], recipient_role="", ref=t["id"], dedupe=False)
        raise HTTPException(status_code=409, detail={"code": "SCHEDULE_FAILED", "message": msg})


async def job_export_schedule_dispatch() -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    due = await db.export_templates.find({"schedule.active": True, "schedule.next_run_at": {"$lte": now, "$ne": ""}},
                                         {"_id": 0}).to_list(100)
    ran = 0
    for t in due:
        nxt = next_run(t["schedule"])
        claimed = await db.export_templates.update_one(
            {"id": t["id"], "schedule.next_run_at": t["schedule"]["next_run_at"]}, {"$set": {"schedule.next_run_at": nxt}})
        if not claimed.modified_count:
            continue
        try:
            await run_template(t)
            ran += 1
        except HTTPException:
            pass
        except Exception:  # noqa: BLE001 — satu template gagal tidak menghentikan dispatcher
            log.exception("template %s gagal", t["id"])
    return {"scanned": len(due), "created": ran, "detail": f"{ran} export terjadwal dibuat"}
