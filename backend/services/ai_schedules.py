"""Tanya KN F4 — laporan terjadwal (in-app) + pemeliharaan harian (retensi sesi chat).

Dispatcher `ai_schedule_dispatch` (scheduler_service, tiap 5 menit) mengklaim jadwal jatuh tempo dengan CAS pada
`next_run_at`, lalu menjalankan template dengan identitas & hak akses PEMILIK jadwal.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso
from db import db
from services import ai_templates
from services.ai_narrative import narrate
from services.analytics_time import now_wib
from services.config_resolver import value_of

logger = logging.getLogger(__name__)
FREQS = ("daily", "weekly")


class ScheduleError(Exception):
    pass


def next_run(freq: str, weekday: int, hhmm: str, after: Optional[datetime] = None) -> str:
    """Kejadian berikut (WIB) setelah `after` → ISO UTC. weekday 0=Senin."""
    now = (after or now_wib()).astimezone(now_wib().tzinfo)
    h, m = (int(x) for x in hhmm.split(":"))
    cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if freq == "weekly":
        cand += timedelta(days=(weekday - cand.weekday()) % 7)
        if cand <= now:
            cand += timedelta(days=7)
    elif cand <= now:
        cand += timedelta(days=1)
    return cand.astimezone(timezone.utc).isoformat()


def validate(payload: Dict[str, Any], role: str) -> Dict[str, Any]:
    tpl = ai_templates.BY_ID.get(payload.get("template_id") or "")
    if not tpl or (role != "admin" and role not in tpl["roles"]):
        raise ScheduleError("Template tidak ditemukan untuk peran Anda.")
    freq = payload.get("frequency") or "daily"
    hhmm = str(payload.get("time") or "07:00")
    try:
        h, m = (int(x) for x in hhmm.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60 and freq in FREQS
    except (ValueError, AssertionError) as exc:
        raise ScheduleError("Frekuensi atau jam tidak valid (HH:MM, harian/mingguan).") from exc
    params = {k: v for k, v in (payload.get("params") or {}).items() if k in ("period", "days", "days_ahead", "product") and v}
    for p in tpl["params"]:
        if p.get("required") and not params.get(p["name"]):
            raise ScheduleError(f"Parameter '{p['name']}' wajib diisi.")
    weekday = int(payload.get("weekday") or 0) % 7
    return {"template_id": tpl["id"], "title": (payload.get("title") or tpl["title"]).strip()[:120], "params": params,
            "frequency": freq, "weekday": weekday, "time": f"{h:02d}:{m:02d}", "channel": "in_app",
            "next_run_at": next_run(freq, weekday, f"{h:02d}:{m:02d}")}


async def ctx_for(user: Dict[str, Any], entity_id: str, view_all: bool):
    from entity_scope import CROSS_ENTITY_ROLES, EntityContext, all_active_entity_ids, resolve_allowed_entities
    home = user.get("home_entity_id") or entity_id
    if user.get("role") in CROSS_ENTITY_ROLES:
        allowed = resolve_allowed_entities(user.get("role"), home, await all_active_entity_ids())
    else:
        allowed = user.get("allowed_entity_ids") or [home]
    if entity_id not in allowed:
        raise ScheduleError("Pemilik jadwal tidak lagi punya akses ke badan usaha jadwal ini.")
    return EntityContext(user=user, active_entity_id=entity_id, allowed_entity_ids=allowed, view_all=view_all and len(allowed) > 1)


async def run_schedule(sched: Dict[str, Any], trigger: str = "schedule") -> Dict[str, Any]:
    from services.notification_service import create_notification
    run = {"id": new_id("airun"), "schedule_id": sched["id"], "user_id": sched["user_id"], "template_id": sched["template_id"],
           "title": sched["title"], "trigger": trigger, "created_at": now_iso()}
    try:
        user = await db.users.find_one({"id": sched["user_id"]}, {"_id": 0, "password": 0, "password_hash": 0})
        roles = await value_of("ai.enabled_roles") or []
        if not user or user.get("status", "active") != "active" or (user.get("role") != "admin" and user.get("role") not in roles):
            raise ScheduleError("Pemilik jadwal tidak aktif atau tidak lagi boleh memakai asisten.")
        ctx = await ctx_for(user, sched["entity_id"], bool(sched.get("view_all")))
        out = await ai_templates.run(sched["template_id"], sched.get("params") or {}, user, ctx, use_cache=False)
        shown = [out["results"][r] for r in dict.fromkeys(b["result_id"] for b in out["blocks"])]
        narr = await narrate(ai_templates.BY_ID[sched["template_id"]], shown, user)
        run.update(status="ok", template=out["template"], params=out["params"], blocks=out["blocks"],
                   result_ids=list(out["results"]), warnings=out["warnings"],
                   narrative=(narr or {}).get("text"), narrative_source=(narr or {}).get("source"))
        body = (narr or {}).get("text") or "Laporan siap. Buka Tanya KN untuk grafik dan tabel lengkap."
        await create_notification(notif_type="ai_report", title=f"Laporan terjadwal: {sched['title']}", body=body[:1200],
                                  link="tanya-kn", entity_id=sched["entity_id"], recipient_user=sched["user_id"],
                                  recipient_role="",  # GN-16 — laporan pribadi, bukan siaran
                                  ref=run["id"], dedupe=False)
    except ScheduleError as exc:
        run.update(status="error", error=str(exc))
    except Exception as exc:  # noqa: BLE001 — satu jadwal gagal tidak menghentikan dispatcher
        logger.exception("jadwal %s gagal", sched["id"])
        run.update(status="error", error=f"Gagal: {exc}")
    await db.ai_schedule_runs.insert_one(dict(run))
    await db.ai_schedules.update_one({"id": sched["id"]}, {"$set": {"last_run_at": run["created_at"], "last_status": run["status"],
                                                                    "last_error": run.get("error", ""), "last_run_id": run["id"]}})
    run.pop("_id", None)
    return run


async def job_ai_schedule_dispatch() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    due: List[Dict[str, Any]] = await db.ai_schedules.find({"active": True, "next_run_at": {"$lte": now.isoformat()}},
                                                            {"_id": 0}).to_list(200)
    ran = 0
    for s in due:
        nxt = next_run(s["frequency"], s.get("weekday", 0), s["time"], now_wib())
        claimed = await db.ai_schedules.update_one({"id": s["id"], "next_run_at": s["next_run_at"]}, {"$set": {"next_run_at": nxt}})
        if claimed.modified_count:
            await run_schedule(s)
            ran += 1
    return {"scanned": len(due), "created": ran, "detail": f"{ran} laporan terjadwal dikirim"}


async def job_ai_maintenance() -> Dict[str, Any]:
    days = int(await value_of("ai.chat_retention_days") or 180)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    res = await db.ai_chat_sessions.delete_many({"updated_at": {"$lt": cutoff}})
    runs = await db.ai_schedule_runs.delete_many({"created_at": {"$lt": cutoff}})
    return {"scanned": res.deleted_count + runs.deleted_count, "created": 0,
            "detail": f"{res.deleted_count} sesi chat & {runs.deleted_count} riwayat laporan > {days} hari dihapus"}
