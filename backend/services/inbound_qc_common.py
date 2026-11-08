"""Aturan barang MASUK GUDANG yang dipakai bersama jalur PO (`inbound_complete_service.complete_task`) dan hasil
langkah terakhir Order Makloon (`makloon_receipt_qc`).

Diekstrak (bukan disalin) supaya dua pintu barang masuk memberi SATU jawaban untuk tiga pertanyaan:
  1. Masuk karantina QC dulu? — `purchasing.qc_on_receipt` (bawaan aktif, per badan usaha pemilik barang).
  2. Tahap journey awal roll? — gudang yang juga GUDANG SIMPAN (`storage`/`material`, termasuk gedung tunggal yang
     merangkap transit — P9-K1, PREP-C 8 Nov) → langsung `stored` (cukup penempatan bin, tanpa PA antar gedung);
     gudang transit / penerimaan pusat / staging / inspeksi / tanpa peran → `received_transit` (antre tag & putaway).
     Routing awal `store`.
  3. SPK inspeksi otomatis untuk tugas QC — idempoten (`inspection_service.ensure_for_qc_task`); kegagalannya
     DICATAT di hasil (`inspection_error`) dan terlihat sebagai temuan INV-QC-02, bukan ditelan diam-diam.
  4. PREP-C (K-GDG-10) — sesudah barang LEPAS ke stok tersedia (QC lulus / GRN tanpa QC) sistem menyiapkan DRAF
     Putaway Order per gedung tujuan (`auto_draft_after_release`, best-effort & idempoten).
"""
import logging
from typing import Any, Dict, Iterable, List, Optional

from core_utils import now_iso
from db import db

logger = logging.getLogger(__name__)

TRANSIT_ROLES = {"transit", "central_inbound", "staging", "inspection"}
STORAGE_ROLES = {"storage", "material"}


async def qc_on_receipt_enabled(entity_id: str) -> bool:
    """Setelan `purchasing.qc_on_receipt` efektif untuk badan usaha pemilik barang (bawaan True)."""
    from services.config_service import get_effective_settings
    cfg = await get_effective_settings(entity_id)
    return bool((cfg.get("purchasing", {}) or {}).get("qc_on_receipt", True))


def stage_for_roles(roles: Optional[Iterable[str]]) -> str:
    """P9-K1 (gedung tunggal = transit + simpan): peran simpan MENANG — roll baru langsung `stored` di gedung itu,
    karena tidak ada gedung simpan lain yang menjadi tujuan PA (dulu tertahan `received_transit` selamanya)."""
    roles = set(roles or [])
    if roles & STORAGE_ROLES:
        return "stored"
    return "received_transit" if (not roles or roles & TRANSIT_ROLES) else "stored"


async def initial_journey_stage(warehouse_id: str) -> str:
    """Tahap journey awal roll yang baru diterima di gudang ini (lihat docstring modul, butir 2)."""
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "roles": 1}) or {}
    return stage_for_roles(wh.get("roles"))


def journey(stage: str) -> Dict[str, Any]:
    return {"stage": stage, "routing": "store", "updated_at": now_iso()}


async def ensure_inspection(task: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """FASE I — SPK inspeksi lahir otomatis untuk tugas `qc_pending` → {"inspection": …} | {"inspection_error": …}."""
    try:
        from services import inspection_service as _ins
        spk = await _ins.ensure_for_qc_task(task, actor)
        return {"inspection": {"id": spk.get("id", ""), "number": spk.get("number", ""),
                               "lines": len(spk.get("lines") or [])}}
    except Exception as exc:  # noqa: BLE001 — dicatat & dikembalikan (INV-QC-02), tidak menggagalkan penerimaan
        logger.error("FASE I: SPK inspeksi GAGAL dibuat untuk task %s: %s", task.get("id"), exc)
        return {"inspection_error": str(exc)}


async def auto_draft_after_release(roll_ids: Optional[List[str]], trigger: Dict[str, Any],
                                   actor_name: str = "") -> Dict[str, Any]:
    """PREP-C (K-GDG-10) — draf Putaway Order otomatis untuk roll yang baru tersedia. Best-effort: kegagalannya
    DICATAT di hasil (`error`) dan log, tidak menggagalkan keputusan QC / penerimaan (dokumen sumber sudah final)."""
    ids = [r for r in dict.fromkeys(roll_ids or []) if r]
    if not ids:
        return {"drafts": [], "skipped": 0}
    try:
        from services import putaway_draft_service as _pad
        return await _pad.auto_draft(ids, {**trigger, "by": actor_name}, "")   # pembuat draf = Sistem
    except Exception as exc:  # noqa: BLE001
        logger.error("PREP-C: draf putaway otomatis GAGAL (%s %s): %s", trigger.get("type"), trigger.get("id"), exc)
        return {"drafts": [], "error": str(exc)[:300]}
