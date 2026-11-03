"""Aturan barang MASUK GUDANG yang dipakai bersama jalur PO (`inbound_complete_service.complete_task`) dan hasil
langkah terakhir Order Makloon (`makloon_receipt_qc`).

Diekstrak (bukan disalin) supaya dua pintu barang masuk memberi SATU jawaban untuk tiga pertanyaan:
  1. Masuk karantina QC dulu? — `purchasing.qc_on_receipt` (bawaan aktif, per badan usaha pemilik barang).
  2. Tahap journey awal roll? — gudang transit / penerimaan pusat / staging / tanpa peran → `received_transit`
     (antre tag & putaway), gudang simpan murni → langsung `stored` (UAT 24 Okt P9.3). Routing awal `store`.
  3. SPK inspeksi otomatis untuk tugas QC — idempoten (`inspection_service.ensure_for_qc_task`); kegagalannya
     DICATAT di hasil (`inspection_error`) dan terlihat sebagai temuan INV-QC-02, bukan ditelan diam-diam.
"""
import logging
from typing import Any, Dict, Iterable, Optional

from core_utils import now_iso
from db import db

logger = logging.getLogger(__name__)

TRANSIT_ROLES = {"transit", "central_inbound", "staging"}


async def qc_on_receipt_enabled(entity_id: str) -> bool:
    """Setelan `purchasing.qc_on_receipt` efektif untuk badan usaha pemilik barang (bawaan True)."""
    from services.config_service import get_effective_settings
    cfg = await get_effective_settings(entity_id)
    return bool((cfg.get("purchasing", {}) or {}).get("qc_on_receipt", True))


def stage_for_roles(roles: Optional[Iterable[str]]) -> str:
    roles = set(roles or [])
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
