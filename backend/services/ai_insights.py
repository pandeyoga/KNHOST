"""Tanya KN — peringatan anomali otomatis (tanpa model; angka & penyebab dihitung server).

Tiap pagi: penjualan turun per sales, piutang mulai macet, stok akan habis, PO supplier terlambat.
Hasil → koleksi `ai_insights` (tab Peringatan) + notifikasi lonceng ke peran yang berwenang.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso
from services import analytics_engine as engine
from services.analytics_time import now_wib
from services.config_resolver import value_of

MGMT = ("admin", "manager")
_NET = {"$multiply": ["$net_alloc", {"$ifNull": ["$split", 1]}]}


def _rp(v: float) -> str:
    return "Rp " + f"{round(v):,}".replace(",", ".")


async def _sales_drop(eid: str, drop_pct: int) -> List[Dict[str, Any]]:
    today = now_wib().date()
    d7, d35 = (today - timedelta(days=7)).isoformat(), (today - timedelta(days=35)).isoformat()
    per: Dict[str, Dict[str, Any]] = {}
    async for r in db.fact_sales_lines.aggregate([
        {"$match": {"entity_id": eid, "is_live": True, "is_sample": False, "date_wib": {"$gte": d35}}},
        {"$group": {"_id": {"s": "$sales_id", "c": "$customer_id"}, "sn": {"$first": "$sales_name"}, "cn": {"$first": "$customer_name"},
                    "cur": {"$sum": {"$cond": [{"$gte": ["$date_wib", d7]}, _NET, 0]}},
                    "prev": {"$sum": {"$cond": [{"$lt": ["$date_wib", d7]}, _NET, 0]}}}}]):
        s = per.setdefault(r["_id"]["s"] or "", {"name": r.get("sn") or "—", "cur": 0.0, "prev": 0.0, "cust": []})
        s["cur"] += r["cur"]
        s["prev"] += r["prev"] / 4
        s["cust"].append({"customer": r.get("cn"), "delta": r["cur"] - r["prev"] / 4})
    out = []
    for sid, s in per.items():
        if s["prev"] <= 0 or s["cur"] >= s["prev"] * (1 - drop_pct / 100):
            continue
        pct = round((s["cur"] - s["prev"]) / s["prev"] * 100, 1)
        top = sorted(s["cust"], key=lambda c: c["delta"])[:3]
        why = "; ".join(f"{c['customer']} {_rp(c['delta'])}" for c in top if c["delta"] < 0)
        out.append({"kind": "sales_drop", "subject": sid, "severity": "warning" if pct > -60 else "critical",
                    "title": f"Penjualan {s['name']} turun {abs(pct)}%",
                    "body": f"7 hari terakhir {_rp(s['cur'])} vs rata-rata mingguan 4 minggu sebelumnya {_rp(s['prev'])}. "
                            + (f"Penyumbang penurunan terbesar: {why}." if why else ""),
                    "items": [{"label": c["customer"], "value": round(c["delta"], 2)} for c in top],
                    "question": f"Kenapa penjualan {s['name']} turun 7 hari terakhir dibanding 4 minggu sebelumnya? Rinci per pelanggan.",
                    "audience_roles": list(MGMT), "audience_users": [sid] if sid else []})
    return out


async def _ar_bad(eid: str) -> List[Dict[str, Any]]:
    from services.ai_tools import _ar_orders
    sc = engine.Scope(user={"role": "admin"}, entity_ids=[eid], sales_only=None, line_q={}, policy={})
    per: Dict[str, Dict[str, Any]] = {}
    for o in await _ar_orders(sc, True, 5000):
        c = per.setdefault(o["customer"], {"amt": 0.0, "max": 0, "new": 0})
        c["amt"] += float(o["outstanding"] or 0)
        c["max"] = max(c["max"], int(o["days_overdue"] or 0))
        c["new"] += 1 if int(o["days_overdue"] or 0) <= 7 else 0
    if not per:
        return []
    top = sorted(per.items(), key=lambda kv: -kv[1]["amt"])[:5]
    fresh = sum(1 for c in per.values() if c["new"])
    heavy = [n for n, c in per.items() if c["max"] > 30]
    total = sum(c["amt"] for c in per.values())
    return [{"kind": "ar_overdue", "subject": "all", "severity": "critical" if heavy else "warning",
             "title": f"Piutang lewat tempo {_rp(total)} di {len(per)} pelanggan",
             "body": f"{fresh} pelanggan baru mulai terlambat minggu ini; {len(heavy)} pelanggan terlambat > 30 hari. "
                     f"Terbesar: " + "; ".join(f"{n} {_rp(c['amt'])} ({c['max']} hari)" for n, c in top) + ".",
             "items": [{"label": n, "value": round(c["amt"], 2)} for n, c in top],
             "question": "Siapa saja pelanggan dengan piutang lewat jatuh tempo, dan siapkan pengingat penagihan ke sales masing-masing.",
             "audience_roles": list(MGMT) + ["finance"], "audience_users": []}]


async def _stock_out(eid: str, cover_days: int) -> List[Dict[str, Any]]:
    from services.ai_forecast import demand_rows
    rows = [r for r in await demand_rows([eid], {}, 4) if r["days_cover"] < cover_days]
    if not rows:
        return []
    rows.sort(key=lambda r: r["days_cover"])
    return [{"kind": "stock_out", "subject": "all", "severity": "critical" if rows[0]["days_cover"] < 3 else "warning",
             "title": f"{len(rows)} produk diperkirakan habis dalam {cover_days} hari",
             "body": "Berdasarkan rata-rata penjualan 12 minggu: " + "; ".join(
                 f"{r['product']} sisa {r['available']:g} {r['unit']} (±{r['days_cover']:g} hari, saran pesan {r['suggested_qty']:g})"
                 for r in rows[:5]) + ".",
             "items": [{"label": r["product"], "value": r["days_cover"]} for r in rows[:5]],
             "question": "Produk apa yang akan habis dalam 2 minggu ke depan dan berapa saran jumlah pesan ulangnya? Siapkan draf PO.",
             "audience_roles": list(MGMT) + ["warehouse_admin"], "audience_users": []}]


async def _late_po(eid: str) -> List[Dict[str, Any]]:
    today = now_wib().date().isoformat()
    rows = []
    async for po in db.purchase_orders.find({"entity_id": eid, "status": {"$in": ["pending", "approved", "receiving", "partially_received", "sent"]},
                                             "expected_delivery_date": {"$lt": today, "$gt": ""}},
                                            {"_id": 0, "po_number": 1, "supplier_name": 1, "expected_delivery_date": 1}):
        late = (now_wib().date() - date.fromisoformat(str(po["expected_delivery_date"])[:10])).days
        rows.append({"label": f"{po.get('po_number')} · {po.get('supplier_name')}", "value": late})
    if not rows:
        return []
    rows.sort(key=lambda r: -r["value"])
    return [{"kind": "po_late", "subject": "all", "severity": "critical" if rows[0]["value"] > 14 else "warning",
             "title": f"{len(rows)} PO supplier terlambat datang",
             "body": "Terlambat terlama: " + "; ".join(f"{r['label']} ({r['value']} hari)" for r in rows[:5]) + ".",
             "items": rows[:5], "question": "PO supplier mana yang terlambat datang dan bagaimana performa tepat waktu supplier tersebut?",
             "audience_roles": list(MGMT), "audience_users": []}]


async def scan(entity_id: Optional[str] = None) -> Dict[str, Any]:
    from services.notification_service import create_addressed
    drop = int(await value_of("ai.anomaly_drop_pct") or 30)
    cover = int(await value_of("ai.anomaly_cover_days") or 14)
    eids = [entity_id] if entity_id else await db.business_entities.distinct("id", {"active": {"$ne": False}})
    day, found, notified = now_wib().date().isoformat(), 0, 0
    for eid in eids:
        items = (await _sales_drop(eid, drop)) + (await _ar_bad(eid)) + (await _stock_out(eid, cover)) + (await _late_po(eid))
        for it in items:
            key = f"{eid}:{it['kind']}:{it['subject']}:{day}"
            doc = {**it, "key": key, "entity_id": eid, "date": day, "updated_at": now_iso()}
            res = await db.ai_insights.update_one({"key": key}, {"$set": doc, "$setOnInsert": {"id": new_id("ains"), "created_at": now_iso()}},
                                                  upsert=True)
            found += 1
            if res.upserted_id is None:
                continue
            sent = await create_addressed(roles=tuple(it["audience_roles"]), also_users=tuple(it["audience_users"]), entity_id=eid,
                                          notif_type="ai_insight", title=it["title"], body=it["body"], severity=it["severity"],
                                          link="tanya-kn", ref=key, dedupe_scope="day")
            notified += len(sent)
    return {"entities": len(eids), "insights": found, "notified": notified}


async def list_for(user: Dict[str, Any], entity_ids: List[str], days: int = 7) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"entity_id": {"$in": entity_ids}, "date": {"$gte": (now_wib().date() - timedelta(days=days)).isoformat()}}
    if user.get("role") != "admin":
        q["$or"] = [{"audience_roles": user.get("role")}, {"audience_users": user["id"]}]
    return await db.ai_insights.find(q, {"_id": 0}).sort([("date", -1), ("severity", 1)]).to_list(100)


async def job_ai_anomaly_scan() -> Dict[str, Any]:
    if not await value_of("ai.anomaly_enabled"):
        return {"scanned": 0, "created": 0, "detail": "Dilewati (ai.anomaly_enabled mati)"}
    r = await scan()
    return {"scanned": r["entities"], "created": r["insights"], "detail": f"{r['insights']} peringatan · {r['notified']} notifikasi"}
