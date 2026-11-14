"""R6.5 — Generator ALERT untuk Scheduler & Notifikasi (Kain Nusantara).

Semua alert dihitung dari DATA NYATA (TANPA mock):
- AR jatuh tempo    → `services/ar_aging_service.aging_report`
- AP jatuh tempo    → `vendor_bills` (posted) + term pembayaran supplier (`payment_terms`)
- Penyusutan aset   → `fin_fixed_assets` vs `fin_depreciation_entries` (periode tertinggal)
- Anggaran          → `services/budget_service.budget_vs_actual` (baris berstatus over/warning)
- Produksi          → `mfg_work_orders` dirilis/draft yang tertunda
- Operasi gudang    → `wms_tasks` outbound/inbound yang tertunda
- Event umum        → `services/notification_service.generate_system_notifications`

Setiap notifikasi ter-dedupe per (type, ref, **HARI**) → menjalankan job berulang
dalam hari yang sama TIDAK menduplikasi notifikasi (idempotent harian).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db
from services.notification_service import create_notification, generate_system_notifications
from services import reminder_policy as policy
from core_utils import rupiah

# KP-T7 (KP-20) — ambang & penerima kini pengaturan per PT (Pusat Pengaturan › Notifikasi), dibaca lewat
# `services/reminder_policy.py`: dulu konstanta AP_DUE_SOON_DAYS 7, WO_RELEASED_STALE_DAYS 3, WO_DRAFT_STALE_DAYS 7,
# TASK_STALE_DAYS 2, MAX_ALERTS_PER_JOB 40, dan `recipient_role="manager"/"warehouse"` di titik kirim.

TASK_OPEN_STATUSES = ["created", "pending", "picking", "packing", "qc_pending",
                      "waiting_goods", "receiving", "partially_shipped"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(iso: Any) -> Optional[datetime]:
    if isinstance(iso, datetime):
        return iso if iso.tzinfo else iso.replace(tzinfo=timezone.utc)
    if not iso or not isinstance(iso, str):
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _rp(v: Any) -> str:
    """Alias tipis ke `core_utils.rupiah` — satu sumber format uang untuk seluruh backend."""
    return rupiah(v)


def _period_prev_month() -> str:
    """Periode YYYY-MM bulan LALU (penyusutan biasanya dijalankan setelah tutup bulan)."""
    first_this = _now().replace(day=1)
    prev = first_this - timedelta(days=1)
    return prev.strftime("%Y-%m")


async def _active_entities() -> List[str]:
    ents = await db.business_entities.find(
        {"status": {"$ne": "inactive"}}, {"_id": 0, "id": 1}).to_list(50)
    return [e["id"] for e in ents if e.get("id")]


# ═══ JOB 1 — AR (piutang) jatuh tempo ════════════════════════════════════════
async def job_ar_overdue() -> Dict[str, Any]:
    from services.ar_aging_service import aging_report
    report = await aging_report()
    rows = [r for r in (report.get("customers") or []) if float(r.get("overdue", 0) or 0) > 0]
    rows.sort(key=lambda r: float(r.get("overdue", 0) or 0), reverse=True)
    created = 0
    maks = int(await policy.threshold("notif.max_alerts_per_run"))
    for r in rows[:maks]:
        days = int(r.get("oldest_days", 0) or 0)
        overdue = float(r.get("overdue", 0) or 0)
        sev = "critical" if days > 30 else "warning"
        body = (f"{_rp(overdue)} lewat jatuh tempo (tertua {days} hari) dari "
                f"{r.get('orders', 0)} order. Segera tagih / follow-up.")
        created += len(await policy.notify(
            "ar_overdue", None,
            notif_type="ar_overdue", ref=f"ar_overdue:{r.get('customer_id')}",
            title=f"Piutang jatuh tempo: {r.get('customer_name', '-')}",
            body=body, severity=sev, link="ar-aging",
            dedupe_scope="day",
        ))
        # Salinan untuk sales pemegang akun (bila ada) agar bisa langsung follow-up.
        sid = r.get("assigned_sales_id") or ""
        if sid:
            note2 = await create_notification(
                notif_type="ar_overdue", ref=f"ar_overdue_sales:{r.get('customer_id')}",
                title=f"Tagih piutang: {r.get('customer_name', '-')}",
                body=body, severity=sev, link="ar-aging",
                # FASE N (K2): salinan untuk pemegang akun — bukan siaran.
                recipient_role="",
                recipient_user=sid, dedupe_scope="day",
            )
            if note2:
                created += 1
    return {"created": created, "scanned": len(rows),
            "detail": f"{len(rows)} pelanggan overdue · total {_rp(report.get('totals', {}).get('overdue'))}"}


# ═══ JOB 2 — AP (hutang supplier) jatuh tempo ════════════════════════════════
async def _term_days_map(entity_id: str = "") -> Dict[str, int]:
    """Peta kode syarat bayar → net_days untuk SATU badan usaha.

    FASE E-4 (E4.3): syarat bayar berlapis (global + override badan usaha). Dulu
    fungsi ini membaca seluruh koleksi tanpa lapisan sehingga dua baris ber-kode
    sama saling menimpa secara acak — jatuh tempo AP bisa salah beberapa hari.
    """
    from services import entity_master_service as ems
    rows = await ems.effective_rows("payment-terms", entity_id)
    return {t.get("code", ""): int(t.get("net_days", 0) or 0) for t in rows if t.get("code")}


async def job_ap_due() -> Dict[str, Any]:
    bills = await db.vendor_bills.find(
        {"status": "posted"},
        {"_id": 0, "id": 1, "bill_number": 1, "bill_date": 1, "grand_total": 1, "total_amount": 1,
         "amount_paid": 1, "supplier_id": 1, "supplier_name": 1, "entity_id": 1}).to_list(5000)
    if not bills:
        return {"created": 0, "scanned": 0, "detail": "tidak ada tagihan supplier terposting"}
    sup_ids = [b.get("supplier_id") for b in bills if b.get("supplier_id")]
    sups = await db.suppliers.find(
        {"id": {"$in": sup_ids}}, {"_id": 0, "id": 1, "payment_term_code": 1}).to_list(2000)
    sup_term = {s["id"]: s.get("payment_term_code", "") for s in sups}
    # Peta syarat bayar dihitung PER BADAN USAHA (baris global + override-nya).
    tmaps: Dict[str, Dict[str, int]] = {}
    from services.analytics_time import now_wib, to_wib_date
    from services.vendor_bill_service import bill_financials
    today = now_wib().date()
    created, scanned = 0, 0
    batas_hari = policy.per_pt("notif.ap_due_soon_days")   # KP-T7 — per PT tagihan
    maks = int(await policy.threshold("notif.max_alerts_per_run"))
    for b in bills:
        # G3 D4-ALERT-AMT-01 — saldo dari SSOT AP (grand − dibayar); lunas tidak diperingatkan.
        fin = bill_financials(b)
        if fin["outstanding"] <= 0.01:
            continue
        # G3 D4-ALERT-DATE-01 — jatuh tempo = TANGGAL kalender WIB, selisih hari kalender.
        bds = to_wib_date(b.get("bill_date"))
        try:
            bd = datetime.strptime(bds, "%Y-%m-%d").date() if bds else None
        except ValueError:
            bd = None
        if not bd:
            continue
        ent = str(b.get("entity_id") or "")
        if ent not in tmaps:
            tmaps[ent] = await _term_days_map(ent)
        days = tmaps[ent].get(sup_term.get(b.get("supplier_id", ""), ""), 0)
        due = bd + timedelta(days=days)
        left = (due - today).days
        if left > int(await batas_hari(ent)):
            continue
        scanned += 1
        if scanned > maks:
            break
        overdue = left < 0
        sev = "critical" if overdue else "warning"
        when = f"LEWAT {abs(left)} hari" if overdue else ("jatuh tempo HARI INI" if left == 0
                                                          else f"jatuh tempo {left} hari lagi")
        created += len(await policy.notify(
            "ap_due", b.get("entity_id"),
            notif_type="ap_due", ref=f"ap_due:{b.get('id')}",
            title=f"Tagihan supplier {when}: {b.get('bill_number', '')}",
            body=(f"{b.get('supplier_name', '')} · sisa {_rp(fin['outstanding'])}"
                  + (f" dari {_rp(fin['grand_total'])}" if fin["amount_paid"] > 0.01 else "")
                  + f" · jatuh tempo {due.isoformat()} (term {days} hari)."),
            severity=sev, link="vendor-bills", dedupe_scope="day",
        ))
    return {"created": created, "scanned": scanned,
            "detail": f"{scanned} tagihan jatuh tempo dalam batas hari pengingat"}


# ═══ JOB 3 — Reminder penyusutan aset tetap ══════════════════════════════════
async def job_depreciation_due() -> Dict[str, Any]:
    period = _period_prev_month()
    assets = await db.fin_fixed_assets.find(
        {"status": "active"}, {"_id": 0, "id": 1, "number": 1, "name": 1,
                               "entity_id": 1, "monthly_depreciation": 1}).to_list(5000)
    if not assets:
        return {"created": 0, "scanned": 0, "detail": "belum ada aset tetap aktif"}
    done = await db.fin_depreciation_entries.find(
        {"period": period}, {"_id": 0, "asset_id": 1}).to_list(20000)
    done_ids = {d.get("asset_id") for d in done}
    pending = [a for a in assets if a.get("id") not in done_ids]
    if not pending:
        return {"created": 0, "scanned": len(assets),
                "detail": f"penyusutan periode {period} sudah lengkap"}
    total = sum(float(a.get("monthly_depreciation", 0) or 0) for a in pending)
    notes = await policy.notify(
        "depreciation_due", None,
        notif_type="depreciation_due", ref=f"dep_due:{period}",
        title=f"Penyusutan aset periode {period} belum dijalankan",
        body=(f"{len(pending)} aset aktif menunggu penyusutan (estimasi {_rp(total)}). "
              f"Buka Kas & Aset → Aset Tetap → Jalankan Penyusutan Bulanan."),
        severity="warning", link="fixed-assets",
        dedupe_scope="day",
    )
    return {"created": len(notes), "scanned": len(assets),
            "detail": f"{len(pending)} aset menunggu periode {period}"}


# ═══ JOB 4 — Peringatan anggaran (over / mendekati batas) ════════════════════
async def job_budget_alert() -> Dict[str, Any]:
    from services import budget_service
    year = _now().year
    created, scanned = 0, 0
    maks = int(await policy.threshold("notif.max_alerts_per_run"))
    for ent in await _active_entities():
        try:
            rep = await budget_service.budget_vs_actual({"entity_id": ent}, year, ent)
        except Exception:  # noqa: BLE001 — jangan gagalkan job karena 1 entitas
            continue
        for row in (rep.get("alerts") or []):
            scanned += 1
            if created >= maks:
                break
            over = row.get("status") == "over"
            pct = float(row.get("used_pct", 0) or 0)
            month = int(row.get("month", 0) or 0)
            per = f"{year}-{month:02d}" if month else str(year)
            created += len(await policy.notify(
                "budget_alert", ent,
                notif_type="budget_alert", ref=f"budget:{ent}:{row.get('key')}:{per}",
                title=(f"Anggaran {'TERLAMPAUI' if over else 'mendekati batas'}: "
                       f"{row.get('label') or row.get('key')}"),
                body=(f"Periode {per} · pemakaian {pct:.0f}% dari {_rp(row.get('budget'))} "
                      f"(realisasi {_rp(row.get('actual'))} + komitmen {_rp(row.get('committed'))}). "
                      f"Sisa {_rp(row.get('remaining'))}."),
                severity="critical" if over else "warning", link="budget",
                dedupe_scope="day",
            ))
    return {"created": created, "scanned": scanned,
            "detail": f"{scanned} baris anggaran over/mendekati batas"}


# ═══ JOB 5 — Work Order produksi tertunda ════════════════════════════════════
async def job_production_stalled() -> Dict[str, Any]:
    now = _now()
    wos = await db.mfg_work_orders.find(
        {"status": {"$in": ["draft", "released"]}}, {"_id": 0}).to_list(5000)
    created, scanned = 0, 0
    batas_rilis = policy.per_pt("notif.wo_released_stale_days")   # KP-T7 — per PT perintah kerja
    batas_draf = policy.per_pt("notif.wo_draft_stale_days")
    maks = int(await policy.threshold("notif.max_alerts_per_run"))
    for w in wos:
        status = w.get("status")
        ref_dt = _parse(w.get("released_at") if status == "released" else w.get("created_at"))
        if not ref_dt:
            continue
        age = (now - ref_dt).days
        limit = int(await (batas_rilis if status == "released" else batas_draf)(w.get("entity_id")))
        short = [p for p in (w.get("material_plan") or []) if not p.get("sufficient")]
        if age < limit and not short:
            continue
        scanned += 1
        if created >= maks:
            break
        if short:
            names = ", ".join((p.get("name") or p.get("material_product_id", "")) for p in short[:3])
            body = (f"{w.get('output_name', '')} {w.get('planned_qty', 0):g} {w.get('output_unit', '')} "
                    f"di {w.get('warehouse_name', '')} — BAHAN KURANG: {names}. "
                    f"Umur {age} hari sejak {'dirilis' if status == 'released' else 'dibuat'}.")
            sev = "critical"
        else:
            body = (f"{w.get('output_name', '')} {w.get('planned_qty', 0):g} {w.get('output_unit', '')} "
                    f"di {w.get('warehouse_name', '')} masih "
                    f"{'DIRILIS' if status == 'released' else 'DRAFT'} setelah {age} hari. "
                    f"Selesaikan atau batalkan.")
            sev = "warning"
        created += len(await policy.notify(
            "production_stalled", w.get("entity_id"),
            notif_type="production_stalled", ref=f"wo_stalled:{w.get('id')}",
            title=f"Work Order tertunda: {w.get('wo_number', '')}",
            body=body, severity=sev, link="production", dedupe_scope="day",
        ))
    return {"created": created, "scanned": scanned,
            "detail": f"{scanned} Work Order tertunda / bahan kurang"}


# ═══ JOB 6 — Tugas gudang (WMS) tertunda ═════════════════════════════════════
async def job_ops_stalled() -> Dict[str, Any]:
    # KP-T7 — batas hari per PT tugas: kueri memakai batas TERKECIL di antara grup + PT aktif, lalu tiap tugas disaring
    # dengan batas PT-nya (bawaan semua 2 → kueri & hasil sama dengan sebelum unit ini).
    batas = policy.per_pt("notif.warehouse_task_stale_days")
    terkecil = min([int(await batas(e)) for e in ["", *await policy.active_entity_ids()]])
    now = _now()
    cutoff = (now - timedelta(days=terkecil)).isoformat()
    tasks = await db.wms_tasks.find(
        {"status": {"$in": TASK_OPEN_STATUSES}, "created_at": {"$lt": cutoff}},
        {"_id": 0, "id": 1, "flow_type": 1, "warehouse_id": 1, "warehouse_name": 1,
         "order_number": 1, "entity_id": 1, "created_at": 1}).to_list(20000)
    tasks = [t for t in tasks
             if str(t.get("created_at") or "") < (now - timedelta(days=int(await batas(t.get("entity_id"))))).isoformat()]
    if not tasks:
        return {"created": 0, "scanned": 0,
                "detail": f"tidak ada tugas gudang menganggur > {terkecil} hari"}
    # Agregasi per (gudang, arah) agar tidak membanjiri bell dengan 1 notif per tugas.
    groups: Dict[tuple, Dict[str, Any]] = {}
    for t in tasks:
        key = (t.get("warehouse_id", ""), t.get("flow_type", ""), t.get("entity_id") or "")   # G3 D4-ALERT-WMS-01
        g = groups.setdefault(key, {"count": 0, "oldest": None, "orders": [],
                                    "warehouse_name": t.get("warehouse_name", ""),
                                    "entity_id": t.get("entity_id")})
        g["count"] += 1
        dt = _parse(t.get("created_at"))
        if dt and (g["oldest"] is None or dt < g["oldest"]):
            g["oldest"] = dt
        if t.get("order_number") and len(g["orders"]) < 4:
            g["orders"].append(t["order_number"])
    created = 0
    for (wid, flow, _ent), g in groups.items():   # G3 D4-ALERT-WMS-01 — key kini 3-tuple
        age = (now - g["oldest"]).days if g["oldest"] else int(await batas(g.get("entity_id")))
        arah = "Outbound (pengiriman)" if flow == "outbound" else "Inbound (penerimaan)"
        created += len(await policy.notify(
            "ops_stalled", g.get("entity_id"),
            notif_type="ops_stalled", ref=f"task_stalled:{wid}:{flow}",
            title=f"Tugas gudang tertunda: {g['warehouse_name'] or wid}",
            body=(f"{g['count']} tugas {arah} belum selesai (tertua {age} hari). "
                  + (f"Order: {', '.join(g['orders'])}." if g["orders"] else "")),
            severity="warning", link="operations", dedupe_scope="day",
        ))
    return {"created": created, "scanned": len(tasks),
            "detail": f"{len(tasks)} tugas menganggur di {len(groups)} gudang/arah"}


# ═══ JOB 7 — Pindai event umum (stok menipis, reservasi, approval) ═══════════
async def job_event_scan() -> Dict[str, Any]:
    created = await generate_system_notifications()
    return {"created": created, "scanned": 0,
            "detail": "stok menipis · reservasi kedaluwarsa · persetujuan SO/PO"}
