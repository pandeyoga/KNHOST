"""PREP-B — mode "pendaftaran awal gedung" (KEPUTUSAN_GATE_RFID §8, K-OPN-01..05): siklus sesi.

Sesi = dokumen `cycle_count_sessions` ber-`mode: "registration"` (mesin opname yang sama: klaim saga, catatan operasi
bertahap per roll, jurnal `cycle_count_variance`), dengan status sendiri:
  draft → running (pembekuan aktif) → pending_approval → approved | approved_with_exceptions | rejected.
FIX-3a (keputusan koordinator "persetujuan dua langkah") — `pending_approval` punya dua langkah bila setelan
`registration.finance_approval` aktif (bawaan): (1) gudang menyetujui HITUNGAN (`registration.count_approval`, baris
terkunci) → (2) Finance menyetujui NILAI & JURNAL (orang berbeda, izin `inventory.approve_value`) → baru roll lama dihapus
& jurnal diposting. "Kembalikan" membatalkan persetujuan hitungan.
Baris lapangan (roll + tag yang akan lahir) disimpan di koleksi `initial_registration_lines` (lihat
`initial_registration_lines.py`) — satu baris per roll fisik, EPC unik selama baris hidup (indeks unik parsial).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, next_doc_number, now_iso, safe_doc
from db import db
from services import initial_registration_plan as plan_svc
from services import registration_freeze as rfz
from services import cycle_count_state as ccs   # FIX-10 — tabel transisi sesi pendaftaran awal + riwayat status

LINES = "initial_registration_lines"   # sama dengan initial_registration_plan.LINES
FREEZE_MODES = {"warehouse": "Beku penuh (gedung kecil)", "zone": "Beku per zona/rak (gedung besar)"}
EPC_MODES = {"read": "EPC bawaan tag dibaca", "system": "EPC dibuat sistem (ditulis ke tag)"}
OPEN = ("draft", "running", "pending_approval")
STATUS_LABEL = {"draft": "Draf", "running": "Berjalan", "pending_approval": "Menunggu persetujuan",
                "approved": "Disetujui", "approved_with_exceptions": "Disetujui — ada pengecualian", "rejected": "Ditolak"}
_INDEX_READY = False


async def ensure_indexes() -> None:
    """Indeks unik parsial: EPC unik antar baris HIDUP semua sesi; satu roll lama dicocokkan ke satu baris."""
    global _INDEX_READY
    if _INDEX_READY:
        return
    await db[LINES].create_index("epc", name="uq_reg_live_epc", unique=True, partialFilterExpression={"live": True})
    await db[LINES].create_index("match_key", name="uq_reg_match", unique=True,
                                 partialFilterExpression={"match_key": {"$type": "string"}})
    await db[LINES].create_index([("session_id", 1), ("status", 1)], name="reg_session_status")
    await db.registration_area_status.create_index("key", name="uq_reg_area", unique=True)
    _INDEX_READY = True


def allowed_owners(ctx) -> Optional[List[str]]:
    return None if getattr(ctx, "view_all", False) else list(ctx.allowed_entity_ids or [])


def assert_status(session: Dict[str, Any], *statuses: str) -> None:
    if session.get("mode") != "registration":
        raise HTTPException(status_code=400, detail="Sesi ini bukan sesi pendaftaran awal gedung.")
    if session.get("status") not in statuses:
        raise HTTPException(status_code=400, detail=(
            f"Sesi berstatus '{STATUS_LABEL.get(session.get('status'), session.get('status'))}' — aksi ini hanya untuk "
            + " / ".join(STATUS_LABEL.get(s, s) for s in statuses) + "."))


async def create_session(payload: Dict[str, Any], actor: Dict[str, Any], ctx) -> Dict[str, Any]:
    from services import warehouse_scope_service as whscope
    fm, em = payload.get("freeze_mode") or "zone", payload.get("epc_mode") or "read"
    if fm not in FREEZE_MODES:
        raise HTTPException(status_code=400, detail="Mode pembekuan harus 'warehouse' (beku penuh) atau 'zone' (per zona/rak).")
    if em not in EPC_MODES:
        raise HTTPException(status_code=400, detail="Mode EPC harus 'read' (EPC bawaan tag) atau 'system' (EPC dibuat sistem).")
    node_ids = [n.strip() for n in payload.get("node_ids") or [] if n and n.strip()]
    if fm == "zone" and not node_ids:
        raise HTTPException(status_code=400, detail="Beku per zona wajib memilih zona/rak cakupan.")
    wh = await whscope.assert_usable(payload.get("warehouse_id") or "", ctx.active_entity_id,
                                     action="melakukan pendaftaran awal stok di sini")
    scope = plan_svc.scope_of(wh, node_ids)
    if not scope["bin_ids"]:
        raise HTTPException(status_code=400, detail="Cakupan tidak memuat bin — lengkapi struktur rak/bin gudang dulu.")
    await ensure_indexes()
    label = ", ".join(scope["labels"])
    session = {
        "id": new_id("cc"), "mode": "registration",
        "number": await next_doc_number("cycle_count_sessions", "number", "REG-", entity_id=ctx.active_entity_id),
        "entity_id": ctx.active_entity_id, "warehouse_id": wh["id"], "warehouse_name": wh.get("name", ""),
        "warehouse_city": wh.get("city", ""), "status": "draft", "items": [],
        "name": (payload.get("name") or "").strip() or f"Pendaftaran awal {wh.get('name', '')} {datetime.now(timezone.utc):%Y%m%d}",
        "notes": (payload.get("notes") or "").strip(),
        "registration": {"freeze_mode": fm, "epc_mode": em, "node_ids": node_ids, "node_labels": scope["labels"],
                         "full_scope": scope["full"], "bin_ids": scope["bin_ids"], "racks": scope["racks"],
                         "rack_marks": {}, "costs": {}, "groups": {}, "writeoffs": {}},
        "freeze": {"active": False, "mode": fm, "warehouse_id": wh["id"], "bin_ids": scope["bin_ids"], "label": label},
        "status_history": ccs.initial_history("draft", actor["name"], "reg_create"),   # FIX-10
        "created_by": actor["name"], "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.cycle_count_sessions.insert_one(dict(session))
    return safe_doc(session)


def _overlaps(mine: Dict[str, Any], other: Dict[str, Any]) -> bool:
    a, b = mine.get("freeze") or {}, other.get("freeze") or {}
    if "warehouse" in (a.get("mode"), b.get("mode")):
        return True
    return bool(set(a.get("bin_ids") or []) & set(b.get("bin_ids") or []))


async def start_session(session: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """draft → running: cakupan dihitung ulang dari struktur terkini, pembekuan dinyalakan (K-OPN-03)."""
    assert_status(session, "draft")
    reg = session["registration"]
    wh = await db.warehouses.find_one({"id": session["warehouse_id"]}, {"_id": 0}) or {}
    scope = plan_svc.scope_of(wh, reg.get("node_ids") or [])
    since = now_iso()
    fr = {"active": True, "mode": reg["freeze_mode"], "warehouse_id": session["warehouse_id"],
          "bin_ids": scope["bin_ids"], "label": ", ".join(scope["labels"]), "since": since, "by": actor["name"]}
    for other in await rfz.active_freezes([session["warehouse_id"]]):
        if other["id"] != session["id"] and _overlaps({"freeze": fr}, other):
            raise HTTPException(status_code=409, detail=f"Cakupan beririsan dengan sesi pendaftaran '{other.get('name')}' "
                                f"yang sedang berjalan ({rfz.area_label(other)}). Selesaikan sesi itu dulu.")
    if not await ccs.transition(session["id"], "reg_start", "running", actor_name=actor["name"], set_fields={
            "freeze": fr, "registration.bin_ids": scope["bin_ids"], "registration.racks": scope["racks"],
            "registration.node_labels": scope["labels"], "registration.started_at": since,
            "registration.started_by": actor["name"]}):
        raise HTTPException(status_code=409, detail="Sesi baru saja berubah — muat ulang.")
    # Balapan dua 'mulai' bersamaan: yang lebih belakangan mengalah (dikembalikan ke draf).
    for other in await rfz.active_freezes([session["warehouse_id"]]):
        if other["id"] != session["id"] and _overlaps({"freeze": fr}, other) \
                and ((other.get("freeze") or {}).get("since"), other["id"]) < (since, session["id"]):
            await ccs.transition(session["id"], "reg_start_rollback", "draft", actor_name=actor["name"],
                                 set_fields={"freeze.active": False},
                                 note=f"kalah balapan mulai dengan sesi '{other.get('name')}'")
            raise HTTPException(status_code=409, detail=f"Sesi '{other.get('name')}' baru saja memulai area yang sama — muat ulang.")
    return await load(session["id"])


async def load(session_id: str) -> Dict[str, Any]:
    return safe_doc(await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0}))


async def progress(session: Dict[str, Any]) -> Dict[str, Any]:
    """Progres per rak: roll terdaftar, rak ditandai selesai, baris belum dipetakan / tag belum ditulis."""
    reg = session.get("registration") or {}
    rows = await db[LINES].aggregate([
        {"$match": {"session_id": session["id"], "status": {"$in": ["draft", "applied"]}}},
        {"$group": {"_id": "$rack_id", "n": {"$sum": 1},
                    "unmapped": {"$sum": {"$cond": [{"$in": ["$product_id", ["", None]]}, 1, 0]}},
                    "unverified": {"$sum": {"$cond": ["$length_verified", 0, 1]}},
                    "pending_write": {"$sum": {"$cond": [{"$eq": ["$tag_state", "pending_write"]}, 1, 0]}}}}]).to_list(2000)
    by_rack = {r["_id"] or "-": r for r in rows}
    marks = reg.get("rack_marks") or {}
    racks = [{**r, "lines": (by_rack.get(r["rack_id"]) or {}).get("n", 0), "done": bool(marks.get(r["rack_id"])),
              **({"done_at": marks[r["rack_id"]].get("at"), "done_by": marks[r["rack_id"]].get("by")} if marks.get(r["rack_id"]) else {})}
             for r in reg.get("racks") or []]
    tot = lambda f: sum(int(r.get(f) or 0) for r in rows)  # noqa: E731
    return {"racks": racks, "racks_total": len(racks), "racks_done": sum(1 for r in racks if r["done"]),
            "lines": tot("n"), "unmapped": tot("unmapped"), "unverified_length": tot("unverified"),
            "pending_write": tot("pending_write")}


async def finance_step_required(entity_id: str) -> bool:
    """Setelan `registration.finance_approval` (bawaan AKTIF) per badan usaha sesi."""
    from services.config_resolver import value_of
    v = await value_of("registration.finance_approval", {"entity_id": entity_id or ""})
    return True if v is None else bool(v)


def approval_step(session: Dict[str, Any], finance_required: bool) -> str:
    """'' (bukan menunggu) · 'count' (menunggu gudang menyetujui hitungan) · 'finance' (menunggu Finance)."""
    if session.get("status") != "pending_approval":
        return ""
    if not finance_required:
        return "single"
    return "finance" if (session.get("registration") or {}).get("count_approval") else "count"


async def approve_count(session: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Langkah 1 (gudang): hitungan disetujui → baris terkunci, angka rekonsiliasi dibekukan untuk Finance."""
    assert_status(session, "pending_approval")
    if not await finance_step_required(session.get("entity_id") or ""):
        raise HTTPException(status_code=400, detail="Persetujuan dua langkah tidak aktif — langsung setujui sesi.")
    if (session.get("registration") or {}).get("count_approval"):
        raise HTTPException(status_code=409, detail="Hitungan sesi ini sudah disetujui gudang — menunggu Finance.")
    rec = await plan_svc.reconcile(session)
    if rec["unmapped"]:
        raise HTTPException(status_code=400, detail=(
            f"{len(rec['unmapped'])} baris 'produk belum dikenali' — petakan ke produk atau batalkan barisnya sebelum "
            "hitungan disetujui."))
    ca = {"by": actor.get("name", ""), "by_id": actor.get("id", ""), "at": now_iso(), "reason": reason,
          "totals": rec.get("totals") or {}}
    res = await db.cycle_count_sessions.update_one(
        {"id": session["id"], "status": "pending_approval", "registration.count_approval": {"$exists": False},
         "saga_lock": {"$exists": False}},
        {"$set": {"registration.count_approval": ca, "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Sesi baru saja berubah — muat ulang.")
    return await load(session["id"])


def assert_lines_editable(session: Dict[str, Any]) -> None:
    """Sesudah gudang menyetujui hitungan, baris terkunci (Finance menilai angka yang sudah final)."""
    if session.get("status") == "pending_approval" and (session.get("registration") or {}).get("count_approval"):
        raise HTTPException(status_code=409, detail=(
            "Hitungan sesi ini sudah disetujui gudang — baris terkunci. 'Kembalikan' sesi bila baris perlu diubah."))


async def assert_finance_ready(session: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Langkah 2 (Finance): hanya sesudah hitungan disetujui gudang, oleh orang yang BERBEDA."""
    if session.get("status") != "pending_approval" or not await finance_step_required(session.get("entity_id") or ""):
        return   # status lain → penolakan status baku dari `approve` (400), bukan galat langkah
    ca = (session.get("registration") or {}).get("count_approval")
    if not ca:
        raise HTTPException(status_code=400, detail=(
            "Langkah 1 belum: gudang belum menyetujui HITUNGAN sesi ini (Setujui hitungan). Nilai & jurnal disetujui "
            "Finance sesudahnya."))
    if (ca.get("by_id") and ca.get("by_id") == actor.get("id")) or (not ca.get("by_id") and ca.get("by") == actor.get("name")):
        raise HTTPException(status_code=403, detail=(
            "Persetujuan nilai & jurnal wajib oleh orang yang berbeda dari penyetuju hitungan (dua langkah)."))


async def detail(session: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in session.items() if k not in ("roll_count",)}
    reg = dict(out.get("registration") or {})
    reg.pop("bin_ids", None)
    fr = dict(out.get("freeze") or {})
    fr["bin_count"] = len(fr.pop("bin_ids", None) or [])
    out.update({"registration": reg, "freeze": fr, "progress": await progress(session),
                "status_label": STATUS_LABEL.get(session.get("status"), session.get("status")),
                "freeze_mode_label": FREEZE_MODES.get(reg.get("freeze_mode"), ""),
                "epc_mode_label": EPC_MODES.get(reg.get("epc_mode"), "")})
    fin = await finance_step_required(session.get("entity_id") or "")
    out.update({"finance_approval_required": fin, "approval_step": approval_step(session, fin)})
    return out


async def mark_rack(session: Dict[str, Any], rack_id: str, done: bool, actor: Dict[str, Any]) -> Dict[str, Any]:
    assert_status(session, "running")
    if rack_id not in {r["rack_id"] for r in (session.get("registration") or {}).get("racks") or []}:
        raise HTTPException(status_code=400, detail="Rak ini di luar cakupan sesi.")
    upd = {"$set": {f"registration.rack_marks.{rack_id}": {"by": actor["name"], "at": now_iso()}}} if done \
        else {"$unset": {f"registration.rack_marks.{rack_id}": ""}}
    await db.cycle_count_sessions.update_one({"id": session["id"], "status": "running"}, upd)
    return await progress(await load(session["id"]))


async def submit(session: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """running → pending_approval. Biaya rata-rata per kelompok DIBEKUKAN (K-OPN-02) supaya angka penyetuju tetap."""
    assert_status(session, "running")
    plan = await plan_svc.build_plan({**session, "registration": {**session["registration"], "costs": {}}})
    costs = {g["key"]: {"cost": g["unit_cost"], "basis": g["cost_basis"], "at": now_iso()}
             for g in plan["groups"] if g["new"]}
    if not await ccs.transition(session["id"], "reg_submit", "pending_approval", actor_name=actor["name"], set_fields={
            "registration.costs": costs, "registration.submitted_at": now_iso(),
            "registration.submitted_by": actor["name"]}):
        raise HTTPException(status_code=409, detail="Sesi baru saja berubah — muat ulang.")
    return await load(session["id"])


async def return_to_running(session: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    assert_status(session, "pending_approval")
    if (session.get("registration") or {}).get("groups"):
        raise HTTPException(status_code=409, detail="Sebagian produk sudah disetujui — selesaikan persetujuan, jangan dikembalikan.")
    if not await ccs.transition(session["id"], "reg_return", "running", actor_name=actor["name"], note=reason,
                                extra_filter={"saga_lock": {"$exists": False}},
                                set_fields={"registration.returned": {"by": actor["name"], "at": now_iso(),
                                                                      "reason": reason}},
                                unset=["registration.count_approval"]):   # FIX-3a — persetujuan hitungan gugur
        raise HTTPException(status_code=409, detail="Sesi sedang disetujui / baru saja berubah — muat ulang.")
    return await load(session["id"])


async def reject(session: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Tolak (final): pembekuan dilepas, baris dibatalkan (EPC bebas lagi). Stok tidak berubah."""
    assert_status(session, *OPEN)
    if (session.get("registration") or {}).get("groups"):
        raise HTTPException(status_code=409, detail="Sebagian produk sudah disetujui — sesi tidak bisa ditolak lagi.")
    done = await ccs.transition(session["id"], "reg_reject", "rejected", actor_name=actor["name"], note=reason,
                                frm=list(OPEN), extra_filter={"saga_lock": {"$exists": False}},
                                set_fields={"freeze.active": False, "freeze.released_at": now_iso(),
                                            "rejected_by": actor["name"], "rejected_at": now_iso(),
                                            "rejection_reason": reason})
    if not done:
        raise HTTPException(status_code=409, detail="Sesi sedang disetujui / baru saja berubah — muat ulang.")
    await db[LINES].update_many({"session_id": session["id"], "status": "draft"},
                                {"$set": {"status": "void", "live": False, "voided_reason": "sesi ditolak"},
                                 "$unset": {"match_key": ""}})
    return await load(session["id"])
