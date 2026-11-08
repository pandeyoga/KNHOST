"""PREP-B (K-OPN-03) — pembekuan gerakan roll selama pendaftaran awal gedung.

Sesi pendaftaran (`cycle_count_sessions.mode == "registration"`) yang BERJALAN / MENUNGGU PERSETUJUAN membekukan:
  · `warehouse` (gedung kecil — beku penuh): semua gerakan roll DARI atau KE gudang itu;
  · `zone` (gedung besar — beku per zona/rak): gerakan roll dari/ke bin di node cakupan sesi. Zona lain tetap melayani.
Penanda beku hidup di dokumen sesi (`freeze` = {active, mode, warehouse_id, bin_ids, label, since}) — satu sumber,
dilepas saat sesi disetujui/ditolak.

Titik gerak memanggil SATU fungsi `assert_*` di bawah (kait satu baris) → 409 `REGISTRATION_FREEZE` berbahasa Indonesia
yang menyebut sesi & area. Penulisan oleh persetujuan pendaftaran itu sendiri TIDAK lewat titik gerak (CAS langsung).

Barang masuk baru lewat GRN tetap DITERIMA (roll lahir tanpa bin, di luar cakupan rekonsiliasi karena lahir sesudah
sesi mulai); PENEMPATAN-nya ke bin beku ditolak oleh kait `place_roll` sampai sesi selesai — taruh di area
penerimaan/zona lain dulu.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException

from db import db

ACTIVE_Q: Dict[str, Any] = {"mode": "registration", "freeze.active": True}
FREEZE_CODE = "REGISTRATION_FREEZE"
_ROLL_PROJ = {"_id": 0, "id": 1, "roll_no": 1, "warehouse_id": 1, "bin_id": 1}


async def active_freezes(warehouse_ids: Iterable[str]) -> List[Dict[str, Any]]:
    ids = sorted({w for w in warehouse_ids if w})
    if not ids:
        return []
    return await db.cycle_count_sessions.find(
        {**ACTIVE_Q, "warehouse_id": {"$in": ids}},
        {"_id": 0, "id": 1, "name": 1, "warehouse_id": 1, "warehouse_name": 1, "freeze": 1}).to_list(50)


def hits(f: Dict[str, Any], warehouse_id: str, bin_id: Optional[str]) -> bool:
    fr = f.get("freeze") or {}
    if not warehouse_id or f.get("warehouse_id") != warehouse_id:
        return False
    if fr.get("mode") == "warehouse":
        return True
    return bool(bin_id) and bin_id in set(fr.get("bin_ids") or [])


def area_label(f: Dict[str, Any]) -> str:
    fr = f.get("freeze") or {}
    wh = f.get("warehouse_name") or f.get("warehouse_id") or ""
    if fr.get("mode") == "warehouse":
        return f"gudang {wh} (beku penuh)"
    return f"zona {fr.get('label') or '-'} di gudang {wh}"


def _deny(f: Dict[str, Any], action: str, what: str) -> None:
    raise HTTPException(status_code=409, detail={
        "code": FREEZE_CODE, "session_id": f.get("id"),
        "message": (f"{action[:1].upper()}{action[1:]} ditolak: {what} berada di {area_label(f)} yang sedang dibekukan "
                    f"untuk pendaftaran awal stok (sesi {f.get('name') or f.get('id')}). Tunggu sesi itu disetujui/ditolak, "
                    "atau pakai roll/bin di luar area beku.")})


async def _check(points: List[Tuple[str, Optional[str], str]], action: str) -> None:
    """points = [(warehouse_id, bin_id|None, uraian)]; 409 pada titik pertama yang kena pembekuan."""
    freezes = await active_freezes(p[0] for p in points)
    if not freezes:
        return
    for wh, bin_id, what in points:
        for f in freezes:
            if hits(f, wh, bin_id):
                _deny(f, action, what)


def _roll_points(rolls: Iterable[Dict[str, Any]]) -> List[Tuple[str, Optional[str], str]]:
    return [(r.get("warehouse_id") or "", r.get("bin_id"), f"roll {r.get('roll_no') or r.get('id')}") for r in rolls if r]


async def assert_movable(*, action: str, roll: Optional[Dict[str, Any]] = None, roll_id: str = "",
                         to_warehouse_id: str = "", to_bin_id: str = "") -> None:
    """Satu roll (asal) dan/atau tujuan (gudang/bin). `to_bin_id` tanpa `to_warehouse_id` = gudang roll."""
    if roll is None and roll_id:
        roll = await db.inventory_rolls.find_one({"id": roll_id}, _ROLL_PROJ)
    points = _roll_points([roll] if roll else [])
    dest_wh = to_warehouse_id or (roll or {}).get("warehouse_id") or ""
    if to_bin_id or to_warehouse_id:
        points.append((dest_wh, to_bin_id or None, f"tujuan {'bin ' + to_bin_id if to_bin_id else 'gudang'}"))
    await _check(points, action)


async def assert_rolls_movable(rolls: Iterable[Dict[str, Any]], action: str, *, to_warehouse_id: str = "") -> None:
    points = _roll_points(rolls)
    if to_warehouse_id:
        points.append((to_warehouse_id, None, "gudang tujuan"))
    await _check(points, action)


async def assert_order_movable(order: Dict[str, Any], action: str) -> None:
    """Perintah putaway: roll di gudang asal + gudang tujuan (tiba tanpa bin → hanya beku penuh yang menolak)."""
    ids = [i.get("roll_id") for i in order.get("items") or [] if i.get("roll_id")]
    rolls = await db.inventory_rolls.find({"id": {"$in": ids}}, _ROLL_PROJ).to_list(2000) if ids else []
    await assert_rolls_movable(rolls, action, to_warehouse_id=order.get("to_warehouse_id") or "")


async def assert_task_movable(task: Dict[str, Any], action: str, *, roll_id: str = "", bin_id: str = "") -> None:
    """Tugas outbound: roll yang dipindai/dipick (atau roll pesanan di gudang itu) + bin yang disebut."""
    wh = task.get("warehouse_id") or ""
    if not await active_freezes([wh]):
        return
    ids = [roll_id] if roll_id else [e.get("roll_id") for e in task.get("scan_log") or []
                                     if e.get("scan_type") == "pick" and e.get("roll_id")]
    q: Dict[str, Any] = {"id": {"$in": ids}} if ids else {
        "reserved_ref.id": task.get("order_id") or "-", "product_id": task.get("product_id"), "warehouse_id": wh}
    points = _roll_points(await db.inventory_rolls.find(q, _ROLL_PROJ).to_list(2000))
    if bin_id:
        points.append((wh, bin_id, f"bin {bin_id}"))
    if not points:   # belum ada roll tertentu → hanya beku penuh yang menolak
        points.append((wh, None, f"gudang tugas {task.get('warehouse_name') or wh}"))
    await _check(points, action)


async def assert_transfer_movable(transfer: Dict[str, Any], phase: str, *, to_bin_id: str = "") -> None:
    """Transfer gudang. phase `out` (siapkan/kirim dari asal) · `in` (terima di tujuan)."""
    if phase == "in":
        await assert_movable(action="penerimaan transfer gudang", to_warehouse_id=transfer.get("dest_warehouse_id") or "",
                             to_bin_id=to_bin_id)
        return
    src = transfer.get("source_warehouse_id") or ""
    if not await active_freezes([src]):
        return
    tid = transfer.get("id")
    rolls = await db.inventory_rolls.find(
        {"$or": [{"reserved_ref.type": "wh_transfer", "reserved_ref.id": tid}, {"transfer_ref.id": tid}]},
        _ROLL_PROJ).to_list(5000)
    points = _roll_points(rolls) or [(src, None, "gudang asal")]
    await _check(points, "pengiriman transfer gudang")


async def area_verification(warehouse_id: str) -> List[Dict[str, Any]]:
    """Area yang sudah 'terverifikasi pendaftaran' (dipakai gate/cutover): [{node_id, label, verified_at, session_id}]."""
    return await db.registration_area_status.find({"warehouse_id": warehouse_id}, {"_id": 0}).to_list(500)
