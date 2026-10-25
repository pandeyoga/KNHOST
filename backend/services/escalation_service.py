"""R6.6 — ESKALASI BERTINGKAT alert yang belum ditindak.

MASALAH: alert penting bisa terabaikan (tidak dibaca) tanpa ada yang menaikkan ke atasan.

SOLUSI: job berkala memindai notifikasi **belum dibaca** dengan severity >= ambang yang
sudah melewati batas waktu (`after_hours`) lalu membuat notifikasi ESKALASI baru untuk
level di atasnya:

    sales / warehouse  →  manager  →  admin  →  (berhenti)

DESAIN
- Notifikasi induk ditandai `escalation_level=1` + `escalated_to` + `escalated_at`
  sehingga TIDAK pernah dieskalasi dua kali (idempotent, tanpa perlu dedupe waktu).
- Notifikasi eskalasi adalah notifikasi biasa (severity **critical**) sehingga:
  (a) tampil di bell penerima level atas, (b) tetap dikirim WhatsApp seketika walau
  mode pengiriman = Ringkasan (critical bypass), (c) bisa dieskalasi lagi ke level
  berikutnya oleh job yang sama → rantai otomatis, dibatasi `max_level`.
- Aksi inline (mis. approve PO) ikut disalin agar atasan bisa langsung menindak.
- Notifikasi yang sudah ditujukan ke `admin` tidak punya level di atasnya → dilewati.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from db import db
from core_utils import now_iso
from services.notification_service import create_notification
from services.wa_alert_service import SEVERITY_RANK, raw_settings
from role_registry import base_or_self, role_in, role_label  # peran acuan dikenali (keputusan owner 2026-10-21)

logger = logging.getLogger("alerts.escalation")

# Rantai eskalasi peran (role penerima notifikasi → role di atasnya).
ESCALATION_CHAIN = {
    "sales": "manager",
    "warehouse": "manager",
    "manager": "admin",
    "all": "admin",
    "": "admin",
}
TOP_ROLES = ("admin",)
MAX_PER_RUN = 40          # pagar anti-flood per eksekusi

DEFAULT_ESCALATION = {
    "enabled": True,
    "after_hours": 8,       # batas waktu belum ditindak (1..72)
    "min_severity": "warning",
    "max_level": 2,         # kedalaman rantai maksimum (1..3)
}


async def effective_config() -> Dict[str, Any]:
    st = await raw_settings()
    return {**DEFAULT_ESCALATION, **(st.get("escalation") or {})}


def _hours_ago(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _age_hours(created_at: str) -> float:
    try:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)


def _source_key(n: Dict[str, Any]) -> str:
    """Kunci DOKUMEN/peristiwa sumber sebuah notifikasi.

    UAT 24 Okt (audit UI tahap 2, G5-57) — `create_addressed` mengirim SATU salinan per orang dengan ref
    `<ref>#<user_id>`. Dulu tiap salinan dieskalasi sendiri-sendiri → admin menerima 2–10 kartu "ESKALASI" yang
    sama berurutan untuk satu PO custom. Semua salinan berbagi ref dasar yang sama, jadi eskalasinya satu.
    """
    base = str(n.get("ref") or "").split("#", 1)[0]
    return f"{n.get('type', '')}:{base}" if base else f"id:{n.get('id', '')}"


def _recipient(n: Dict[str, Any], users: Dict[str, Dict[str, Any]]) -> tuple:
    """(peran penerima efektif, frasa manusia untuk "oleh …"). Salinan per orang memakai peran orangnya."""
    uid = n.get("recipient_user")
    if uid:
        u = users.get(uid) or {}
        role = u.get("role") or ""
        name = str(u.get("name") or "").strip()
        label = role_label(role) if role else ""
        who = f"{name} ({label})" if name and label else (name or label or "penerima")
        return role, who
    role = n.get("recipient_role") or "all"
    return role, ("semua penerima" if role in ("all", "") else role_label(role))


def plan_escalations(candidates, users: Dict[str, Dict[str, Any]], *, min_rank: int,
                     max_level: int) -> Dict[str, Any]:
    """Rencana eskalasi MURNI (tanpa DB, mudah diuji): satu eskalasi per (sumber, kedalaman, peran tujuan).

    Return `{"groups": [{lead, siblings, next_role, depth, who, key}], "skipped_top", "skipped_depth"}`;
    `siblings` = salinan lain dari sumber yang sama → ikut ditandai sudah dieskalasi tanpa kartu baru.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    skipped_top = skipped_depth = 0
    for n in candidates:
        if SEVERITY_RANK.get(n.get("severity", "info"), 1) < min_rank:
            continue
        role, who = _recipient(n, users)
        if role_in(role, TOP_ROLES):
            skipped_top += 1
            continue
        next_role = ESCALATION_CHAIN.get(role) or ESCALATION_CHAIN.get(base_or_self(role))
        if not next_role and n.get("recipient_user"):
            next_role = "admin"   # salinan per orang dulu selalu naik ke admin (peran "") — perilaku dipertahankan
        if not next_role:
            skipped_top += 1
            continue
        depth = int(n.get("escalation_depth", 0) or 0) + 1
        if depth > max_level:
            skipped_depth += 1
            continue
        key = f"{_source_key(n)}|{depth}|{next_role}"
        if key in groups:
            groups[key]["siblings"].append(n)
            continue
        groups[key] = {"lead": n, "siblings": [], "next_role": next_role, "depth": depth, "who": who, "key": key}
    return {"groups": list(groups.values()), "skipped_top": skipped_top, "skipped_depth": skipped_depth}


async def _mark_escalated(notifs, next_role: str, escal_id: str) -> None:
    ids = [x.get("id") for x in notifs if x.get("id")]
    if ids:
        await db.notifications.update_many({"id": {"$in": ids}}, {"$set": {
            "escalation_level": 1,
            "escalated_at": now_iso(),
            "escalated_to": next_role,
            "escalation_notif_id": escal_id,
        }})


async def job_escalation_scan() -> Dict[str, Any]:
    """Naikkan alert penting yang belum dibaca melewati batas waktu ke level di atasnya."""
    cfg = await effective_config()
    if not cfg.get("enabled", True):
        return {"created": 0, "scanned": 0, "detail": "eskalasi dinonaktifkan di pengaturan"}

    after_hours = float(cfg.get("after_hours", 8) or 8)
    max_level = int(cfg.get("max_level", 2) or 2)
    min_rank = SEVERITY_RANK.get(cfg.get("min_severity", "warning"), 2)
    cutoff = _hours_ago(after_hours)

    candidates = await db.notifications.find({
        "read": False,
        "read_by.0": {"$exists": False},   # siaran yang sudah dibaca seseorang = sudah ditangani
        "created_at": {"$lt": cutoff},
        "$or": [{"escalation_level": {"$exists": False}}, {"escalation_level": 0}],
    }, {"_id": 0}).sort("created_at", 1).to_list(500)

    uids = sorted({n.get("recipient_user") for n in candidates if n.get("recipient_user")})
    users: Dict[str, Dict[str, Any]] = {}
    if uids:
        users = {u["id"]: u for u in await db.users.find(
            {"id": {"$in": uids}}, {"_id": 0, "id": 1, "role": 1, "name": 1}).to_list(len(uids))}
    plan = plan_escalations(candidates, users, min_rank=min_rank, max_level=max_level)
    skipped_top, skipped_depth = plan["skipped_top"], plan["skipped_depth"]

    created = merged = 0
    for g in plan["groups"]:
        if created >= MAX_PER_RUN:
            break
        n, next_role, depth = g["lead"], g["next_role"], g["depth"]
        copies = [n, *g["siblings"]]
        # Sumber yang sama sudah dieskalasi di run sebelumnya (salinan lain) → gabungkan, jangan buat kartu baru.
        prior = await db.notifications.find_one(
            {"type": "escalation", "escalated_from_key": g["key"]}, {"_id": 0, "id": 1})
        if prior:
            await _mark_escalated(copies, next_role, prior["id"])
            merged += len(copies)
            continue
        age = _age_hours(n.get("created_at", ""))
        note = await create_notification(
            notif_type="escalation",
            ref=f"escal:{_source_key(n)}:{depth}:{next_role}",
            title=f"ESKALASI: {n.get('title', '')}",
            # UAT 24 Okt (audit UI tahap 2, G5-10) — dulu "… oleh all." (kode peran mentah).
            body=(f"Belum ditindak {age:.0f} jam (batas {after_hours:.0f} jam) oleh "
                  f"{g['who']}. {n.get('body', '')}"),
            severity="critical",
            link=n.get("link", ""),
            entity_id=n.get("entity_id"),
            recipient_role=next_role,
            action_type=n.get("action_type", ""),
            action_id=n.get("action_id", ""),
            action_role=next_role,
            dedupe_scope="day",
        )
        if not note:
            continue
        # Jejak rantai pada notifikasi eskalasi + tandai induk (dan salinan per orangnya) agar tidak berulang.
        await db.notifications.update_one({"id": note["id"]}, {"$set": {
            "escalation_depth": depth,
            "escalated_from": n.get("id"),
            "escalated_from_role": n.get("recipient_role") or "",
            "escalated_from_key": g["key"],
        }})
        await _mark_escalated(copies, next_role, note["id"])
        merged += len(g["siblings"])
        created += 1

    detail = (f"{created} alert dieskalasi (>{after_hours:.0f} jam belum dibaca) "
              f"dari {len(candidates)} kandidat"
              + (f" · {merged} salinan digabung ke eskalasi yang sama" if merged else "")
              + (f" · {skipped_top} sudah di level tertinggi" if skipped_top else "")
              + (f" · {skipped_depth} melewati batas level" if skipped_depth else ""))
    return {"created": created, "scanned": len(candidates), "merged": merged, "detail": detail}


async def escalation_stats() -> Dict[str, Any]:
    """KPI ringkas untuk UI: jumlah eskalasi hari ini + yang masih menunggu."""
    day = now_iso()[:10]
    today = await db.notifications.count_documents(
        {"type": "escalation", "created_at": {"$gte": day}})
    open_esc = await db.notifications.count_documents({"type": "escalation", "read": False})
    cfg = await effective_config()
    pending = await db.notifications.count_documents({
        "read": False,
        "created_at": {"$lt": _hours_ago(float(cfg.get("after_hours", 8) or 8))},
        "$or": [{"escalation_level": {"$exists": False}}, {"escalation_level": 0}],
        "severity": {"$in": [s for s, r in SEVERITY_RANK.items()
                             if r >= SEVERITY_RANK.get(cfg.get("min_severity", "warning"), 2)]},
        "recipient_role": {"$nin": list(TOP_ROLES)},
    })
    return {"today": today, "open": open_esc, "pending_next_scan": pending,
            "enabled": bool(cfg.get("enabled", True)),
            "after_hours": cfg.get("after_hours", 8),
            "min_severity": cfg.get("min_severity", "warning"),
            "max_level": cfg.get("max_level", 2)}
