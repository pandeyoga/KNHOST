"""FIX-7 (butir 5) — masa simpan LOG TEKNIS yang tumbuh tanpa batas (job malam `log_retention`).

Produksi 9 Nov 2026: `sys_scheduler_runs` ±73 ribu dokumen dan terus tumbuh (±700–2.000 baris/hari: job tiap 2–5 menit
mencatat satu baris per jalan). Log teknis lain yang juga tumbuh tanpa batas: `sys_wa_outbox` (satu baris per pesan
WhatsApp), `sys_digest_claims` (klaim ringkasan harian per penerima). Semuanya data operasional sekali pakai: berguna
untuk menelusuri masalah beberapa minggu terakhir, bukan jejak bisnis.

Setelan (registri konfigurasi, `config_catalog_retention.py`; Pusat Pengaturan › Notifikasi & Pemberitahuan):
  * `ops.log_retention_mode`                    — `delete` (bawaan) · `dry_run` (hanya hitung) · `off`;
  * `ops.scheduler_runs_retention_days`         — riwayat job BERHASIL (bawaan 30 hari);
  * `ops.scheduler_runs_failed_retention_days`  — riwayat job GAGAL (bawaan 90 hari — lebih lama untuk ditelusuri);
  * `ops.wa_outbox_retention_days`              — kotak keluar WhatsApp (bawaan 90 hari; baris antre tidak dihapus);
  * `ops.digest_claims_retention_days`          — klaim ringkasan harian (bawaan 30 hari; kuncinya berisi tanggal).
Minimum 7 hari. Baris riwayat TERAKHIR tiap job penjadwal selalu disimpan (kolom "Terakhir jalan" tidak kosong untuk
job yang jarang jalan / dimatikan).

TIDAK PERNAH dihapus di sini (pagar `PROTECTED`, diuji): jejak audit bisnis `audit_logs`, `status_history` (field di
dokumen), jurnal & posting GL, mutasi stok, riwayat nilai roll, log kebersihan data (bisa dibalik), log persetujuan,
peristiwa tag RFID, pemakaian AI (dasar anggaran). Bukti gate RFID punya job sendiri (`rfid_evidence_retention`).

Kenapa job, bukan index TTL: cap waktu log ini teks ISO (TTL Mongo hanya untuk tanggal BSON); masa simpan bisa diubah
pengguna tanpa `collMod`; ada mode uji coba; penghapusan bertahap (per 2.000 baris, jeda singkat) agar VPS bersama
(cache Mongo 0,5 GB) tidak mendapat lonjakan tulis saat 70 ribu baris lama dihapus pertama kali.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db

logger = logging.getLogger(__name__)

MIN_DAYS = 7
BATCH = 2000
MAX_PER_RUN = 500_000          # batas per jalan (sisa dilanjutkan malam berikutnya)
MODES = ("delete", "dry_run", "off")

RULES: List[Dict[str, Any]] = [
    {"key": "scheduler_runs", "coll": "sys_scheduler_runs", "field": "started_at",
     "setting": "ops.scheduler_runs_retention_days", "default": 30, "where": {"status": {"$ne": "failed"}},
     "keep_latest_by": "job_id", "label": "Riwayat job penjadwal (berhasil)"},
    {"key": "scheduler_runs_failed", "coll": "sys_scheduler_runs", "field": "started_at",
     "setting": "ops.scheduler_runs_failed_retention_days", "default": 90, "where": {"status": "failed"},
     "keep_latest_by": "job_id", "label": "Riwayat job penjadwal (gagal)"},
    {"key": "wa_outbox", "coll": "sys_wa_outbox", "field": "created_at",
     "setting": "ops.wa_outbox_retention_days", "default": 90, "where": {"status": {"$nin": ["queued", "pending"]}},
     "label": "Kotak keluar WhatsApp"},
    {"key": "digest_claims", "coll": "sys_digest_claims", "field": "created_at",
     "setting": "ops.digest_claims_retention_days", "default": 30, "where": {}, "label": "Klaim ringkasan harian"},
]
DELETABLE = frozenset(r["coll"] for r in RULES)
PROTECTED = frozenset((
    "audit_logs", "journal_entries", "gl_postings", "inventory_movements", "inventory_rolls", "roll_cost_history",
    "data_hygiene_log", "data_hygiene_runs", "approval_matrix_log", "rfid_tag_events", "ai_usage_log", "notifications",
    "sales_orders", "purchase_orders", "hr_payroll_runs", "migrations",
))
assert not DELETABLE & PROTECTED


def _iso(dt: datetime) -> str:
    return dt.isoformat()   # format sama dengan `core_utils.now_iso()` → perbandingan teks benar


async def settings() -> Dict[str, Any]:
    from services.config_resolver import value_of
    out: Dict[str, Any] = {"mode": "delete", "days": {r["key"]: r["default"] for r in RULES}}
    try:
        mode = await value_of("ops.log_retention_mode")
        if mode not in (None, ""):
            out["mode"] = mode
    except Exception as exc:  # noqa: BLE001 — registri belum termuat → bawaan aman
        logger.warning("[log_retention] mode tidak terbaca, pakai bawaan: %s", exc)
    for r in RULES:
        try:
            v = await value_of(r["setting"])
            if v not in (None, ""):
                out["days"][r["key"]] = int(v)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[log_retention] %s tidak terbaca, pakai bawaan: %s", r["setting"], exc)
        out["days"][r["key"]] = max(MIN_DAYS, int(out["days"][r["key"]]))
    if out["mode"] not in MODES:
        out["mode"] = "dry_run"
    return out


async def _delete_batched(coll: str, q: Dict[str, Any], budget: int) -> int:
    assert coll in DELETABLE and coll not in PROTECTED, coll   # pagar terakhir
    deleted = 0
    while deleted < budget:
        ids = [d["_id"] async for d in db[coll].find(q, {"_id": 1}).limit(min(BATCH, budget - deleted))]
        if not ids:
            break
        res = await db[coll].delete_many({"_id": {"$in": ids}})
        deleted += res.deleted_count
        await asyncio.sleep(0.05)   # beri jeda: API & job lain tetap jalan
    return deleted


async def run(now: Optional[datetime] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    cfg = await settings()
    mode = mode or cfg["mode"]
    now = now or datetime.now(timezone.utc)
    out: Dict[str, Any] = {"mode": mode, "rules": [], "candidates": 0, "deleted": 0}
    if mode == "off":
        return out
    budget = MAX_PER_RUN
    for r in RULES:
        days = cfg["days"][r["key"]]
        cutoff = _iso(now - timedelta(days=days))
        queries: List[Dict[str, Any]] = []
        if r.get("keep_latest_by"):
            k = r["keep_latest_by"]
            # baris TERAKHIR tiap kunci (job) tidak pernah dihapus
            async for g in db[r["coll"]].aggregate([{"$match": r["where"]},
                                                    {"$group": {"_id": f"${k}", "last": {"$max": f"${r['field']}"}}}]):
                upto = min(cutoff, g["last"]) if isinstance(g.get("last"), str) else cutoff
                queries.append({**r["where"], k: g["_id"], r["field"]: {"$lt": upto}})
        else:
            queries.append({**r["where"], r["field"]: {"$lt": cutoff}})
        n_cand = 0
        n_del = 0
        for q in queries:
            n_cand += await db[r["coll"]].count_documents(q)
            if mode == "delete" and budget > 0:
                d = await _delete_batched(r["coll"], q, budget)
                n_del += d
                budget -= d
        out["rules"].append({"key": r["key"], "collection": r["coll"], "label": r["label"], "days": days,
                             "cutoff": cutoff, "candidates": n_cand, "deleted": n_del})
        out["candidates"] += n_cand
        out["deleted"] += n_del
    return out


async def job_log_retention() -> Dict[str, Any]:
    """Job penjadwal (malam). `scanned` = baris yang lewat masa simpan, `detail` = rincian per log."""
    res = await run()
    if res["mode"] == "off":
        return {"created": 0, "scanned": 0, "detail": "masa simpan log teknis mati (ops.log_retention_mode = off)"}
    parts = [f"{x['label']}: {x['deleted'] if res['mode'] == 'delete' else x['candidates']} "
             f"(> {x['days']} hari)" for x in res["rules"]]
    verb = "dihapus" if res["mode"] == "delete" else "akan dihapus (uji coba)"
    return {"created": 0, "scanned": res["candidates"], "detail": f"{verb} — " + "; ".join(parts)}
