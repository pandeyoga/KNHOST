"""PS-20 (D-14) — **Penegakan matriks persetujuan divisi** + antrean "Persetujuan Saya".

Sebelum fase ini matriks approver PS-17 hanya RUJUKAN tampilan. Modul ini menjadikannya
MENGIKAT dengan satu jalur keputusan untuk empat tahap (design_acc, sample_acc,
po_custom, purchase_request) sehingga tidak ada dua sumber kebenaran:

  • `evaluate()`  — murni: boleh/tidak + alasan (dipakai UI untuk menonaktifkan tombol).
  • `guard()`     — sama dengan evaluate, tetapi MELEMPAR 403 bila mode `enforce`.
  • `record()`    — tulis jejak ke koleksi `approval_matrix_log` + `audit_logs`.
  • `my_queue()`  — antrean lintas-tahap: apa yang menunggu keputusan SAYA.

KP-T4 — SIAPA yang boleh memutus tiap tahap (dan mulai nominal berapa) dibaca dari SATU tabel kebijakan
`approval_policies` (`services/approval_policy_service.py`; tahap → jenis dokumen di `STAGE_KIND`). Daftar peran per
tingkat di `config_divisions.APPROVER_MATRIX` dan kunci `approval.matrix_*` / `approval.po_custom_direksi_min` tidak
dipakai lagi (nilainya membentuk baris bawaan). Pemisahan tugas tetap `kontrol.<aksi>.*` (KF-T6, `STAGE_AKSI`).

Catatan: "Direksi" = peran **admin** (keputusan pemilik) — tidak ada peran baru.
"""
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from config_divisions import (APPROVER_MATRIX, STAGE_BY_ID, role_label, roles_label,
                              stage_label)
from core_utils import new_id, now_iso, safe_doc
from db import db
logger = logging.getLogger(__name__)


LOG_COLL = "approval_matrix_log"

# KP-T4 — kunci `approval.matrix_enforcement|scope|effective_from` (mode/cakupan matriks) tidak dipakai lagi: penegakan
# selalu dari Aturan Persetujuan. `approval.matrix_sod` sudah tidak dipakai sejak KF-T6 (alias `settings()["sod"]`).

# KP-T4 — tahap matriks → jenis dokumen Aturan Persetujuan (`approval_kinds.APPROVAL_KINDS`).
STAGE_KIND = {"design_acc": "rnd_spec", "sample_acc": "rnd_sample", "po_custom": "special_order",
              "purchase_request": "purchase_requisition", "makloon_claim": "makloon_claim"}

# KF-T6 — tahap matriks → aksi kontrol dua orang (`config_catalog_kontrol.KONTROL_AKSI`).
STAGE_AKSI = {"design_acc": "acc_desain", "sample_acc": "acc_sample", "po_custom": "po_custom",
              "purchase_request": "permintaan_pembelian"}



# ─── Kebijakan ──────────────────────────────────────────────────────
def _as_bool(v: Any, default: bool = True) -> bool:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on", "aktif")


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


async def settings(entity_id: str = "") -> Dict[str, Any]:
    """Ringkasan kebijakan untuk layar (Pusat Persetujuan / Divisi). KP-T4 — penegakan selalu dari Aturan Persetujuan
    (mode/cakupan matriks lama tidak dipakai lagi); `po_custom_direksi_min` = batas bawah jenjang 2 pesanan khusus di
    tabel (0 bila tidak ada jenjang 2)."""
    # KF-T6 — alias: "pemisahan tugas aktif" = salah satu tahap matriks butuh orang kedua di PT ini.
    from services import dual_control as _dc
    from services import approval_policy_service as _aps
    sod = False
    for _aksi in STAGE_AKSI.values():
        if await _dc.butuh_orang_kedua(_aksi, entity_id or ""):
            sod = True
            break
    rows = (await _aps.rows_for("special_order", entity_id or None))["rows"]
    j2 = sorted([_as_float(r.get("min_amount")) for r in rows if int(r.get("level") or 1) == 2
                 and (r.get("roles") or r.get("any_holder"))])
    return {
        "mode": "enforce", "scope": "all_pending", "effective_from": "", "sod": sod,
        "po_custom_direksi_min": j2[0] if j2 else 0.0,
        "mode_label": "Ditegakkan (Aturan Persetujuan)",
        "scope_label": "Semua dokumen (termasuk yang menunggu)",
    }


# ─── Tingkat persetujuan per tahap (KP-T4: dari Aturan Persetujuan) ─────────────────────
async def levels_for(stage: str, amount: float = 0.0, entity_id: str = "") -> List[Dict[str, Any]]:
    """Tingkat yang BERLAKU untuk satu dokumen menurut Aturan Persetujuan (jenis `STAGE_KIND[stage]`)."""
    from services import approval_policy_service as _aps
    kind = STAGE_KIND.get(stage)
    lv = await _aps.required_levels(kind, entity_id or None, _as_float(amount)) if kind else []
    return [{"level": x["level"], "label": x["label"], "roles": list(x["roles"]), "any_holder": x["any_holder"],
             "roles_label": ("Semua pemegang akses" if x["any_holder"] else roles_label(list(x["roles"]))),
             "rule_id": x["rule_id"], "policy_kind": kind, "min_amount": 0.0} for x in lv]


def build_chain(levels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rantai tersimpan dokumen baru: potret `roles` + id baris kebijakan (D3)."""
    return [{"level": lv["level"], "label": lv["label"], "roles": lv["roles"],
             "rule_id": lv.get("rule_id", ""), "policy_kind": lv.get("policy_kind", ""),
             "status": "pending", "approved_by": "", "approved_by_id": "",
             "approved_at": ""} for lv in levels]


def pending_level(chain: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for lv in chain or []:
        if lv.get("status") != "approved":
            return lv
    return None


def chain_summary(chain: List[Dict[str, Any]]) -> Dict[str, Any]:
    done = sum(1 for lv in (chain or []) if lv.get("status") == "approved")
    cur = pending_level(chain or [])
    return {"levels_total": len(chain or []), "levels_done": done,
            "current_level": (cur or {}).get("level", 0),
            "current_label": (cur or {}).get("label", ""),
            "current_roles": list((cur or {}).get("roles") or []),
            "complete": cur is None}


# ─── Pemisahan tugas (SoD) ───────────────────────────────────────────
_REQUESTER_FIELDS = ("created_by", "created_by_id", "created_by_email", "submitted_by",
                     "submitted_by_id", "requested_by", "requested_by_id", "requester")


def is_requester(doc: Dict[str, Any], actor: Dict[str, Any]) -> bool:
    """True bila `actor` adalah pengaju/pembuat dokumen (cocok id, nama, atau email)."""
    mine = {str((actor or {}).get(k) or "").strip().lower()
            for k in ("id", "name", "email")} - {""}
    if not mine:
        return False
    theirs = set()
    for f in _REQUESTER_FIELDS:
        v = (doc or {}).get(f)
        if isinstance(v, str) and v.strip():
            theirs.add(v.strip().lower())
    # Pesanan khusus menyimpan pembuat di status_history[0].user (email)
    hist = (doc or {}).get("status_history") or []
    if hist and isinstance(hist[0], dict) and hist[0].get("user"):
        theirs.add(str(hist[0]["user"]).strip().lower())
    return bool(mine & theirs)


def is_admin(actor: Dict[str, Any]) -> bool:
    """2026-10 — keputusan pemilik: admin melewati SEMUA persetujuan & boleh menyetujui sendiri."""
    return str((actor or {}).get("role") or "").strip().lower() == "admin"


# KF-T6 — `admin_override` dan `sod_blocked` (pemisahan tugas lama, 15 pemanggil) dihapus: semua titik kini memanggil
# `services/dual_control.tolak_bila_pelaku_sama` (pengecualian Admin = `kontrol.admin_boleh_sendiri`, dicatat di jejak).


# ─── Inti keputusan ───────────────────────────────────────────────
async def evaluate(stage: str, actor: Dict[str, Any], doc: Dict[str, Any],
                   cfg: Dict[str, Any], amount: Optional[float] = None,
                   level: Optional[Dict[str, Any]] = None, action: str = "approve") -> Dict[str, Any]:
    """Boleh atau tidak seseorang memutuskan tahap ini sekarang — KP-T4: `approval_policy_service.can_decide`
    (peran tercantum di Aturan Persetujuan untuk jenis, PT, nilai, jenjang). Izin pintu diperiksa routernya."""
    from services import approval_policy_service as _aps
    st = STAGE_BY_ID.get(stage) or {}
    amt = _as_float(amount if amount is not None else (doc or {}).get("total_amount"), 0.0)
    ent = (doc or {}).get("entity_id") or ""
    lv_all = await levels_for(stage, amt, ent)
    chain = (doc or {}).get("approval_chain") or []
    cur = level or pending_level(chain) or (lv_all[0] if lv_all else {"level": 1, "label": "Persetujuan",
                                                                         "roles": []})
    kind = STAGE_KIND.get(stage, "")
    dec = await _aps.can_decide(kind, ent or None, amt, actor or {}, int(cur.get("level") or 1),
                                action=action, check_permission=False, snapshot_roles=cur.get("roles"))
    res: Dict[str, Any] = {
        "stage": stage, "stage_label": st.get("label") or stage_label(stage),
        "mode": cfg.get("mode"), "scope": cfg.get("scope"),
        "level": cur.get("level", 1), "level_label": cur.get("label", ""),
        "roles": list(cur.get("roles") or []), "roles_label": ", ".join(dec.get("who") or []),
        "levels": lv_all, "levels_total": len(lv_all) or 1,
        "amount": amt, "enforced": True, "allowed": bool(dec["allowed"]),
        "reasons": [] if dec["allowed"] else [{"code": "role", "message": dec["message"]}],
        "skip_reason": "",
    }
    # KF-T6 — pemisahan tugas TIDAK dinilai di sini: `guard` memanggil `dual_control` (aksi = `STAGE_AKSI`).
    res["blocked"] = not res["allowed"]
    return res


async def guard(stage: str, actor: Dict[str, Any], doc: Dict[str, Any],
                entity_id: str = "", amount: Optional[float] = None,
                level: Optional[Dict[str, Any]] = None,
                action: str = "approve") -> Dict[str, Any]:
    """Penjaga endpoint: 403 bila peran tidak tercantum di Aturan Persetujuan (satu pesan, dari tabel). Dicatat."""
    cfg = await settings(entity_id)
    res = await evaluate(stage, actor, {**(doc or {}), "entity_id": entity_id or (doc or {}).get("entity_id", "")},
                         cfg, amount=amount, level=level, action=action)
    res["config"] = cfg
    if not res.get("allowed"):
        detail = " ".join(r["message"] for r in res.get("reasons") or [])
        await record(stage=stage, action=action, actor=actor, doc=doc, entity_id=entity_id,
                     level=res.get("level", 1), level_label=res.get("level_label", ""),
                     outcome="ditolak sistem", note=detail, enforced=True,
                     violation=True, reasons=res.get("reasons") or [])
        raise HTTPException(status_code=403, detail=detail)
    # KF-T6 — pengaju ≠ pemutus: satu pembantu, aksi tahap ini (berlaku juga untuk menolak, seperti sebelumnya).
    if stage in STAGE_AKSI:
        from services import dual_control as _dc
        amt = _as_float(amount if amount is not None else (doc or {}).get("total_amount")
                        or (doc or {}).get("total_est_amount"), 0.0)
        await _dc.tolak_bila_pelaku_sama(STAGE_AKSI[stage], doc or {}, actor or {}, entity_id, nominal=amt)
    return res


# ─── Jejak persetujuan ────────────────────────────────────────────
async def record(*, stage: str, action: str, actor: Dict[str, Any], doc: Dict[str, Any],
                 entity_id: str = "", level: int = 1, level_label: str = "",
                 outcome: str = "", note: str = "", enforced: bool = True,
                 violation: bool = False,
                 reasons: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    st = STAGE_BY_ID.get(stage) or {}
    # FASE E-7 — stempel entitas WAJIB ada: jejak tanpa entitas akan terbaca semua PT
    # (dan membuat gate kepatuhan memerah karena dokumen ter-scope tanpa field entitas).
    # Urutan: yang dikirim pemanggil → dokumennya → badan usaha aktif pelaku.
    _ent = entity_id or (doc or {}).get("entity_id") or ""
    if not _ent:
        try:
            from request_context import get_active_entity
            _ent = get_active_entity() or ""
        except Exception:  # noqa: BLE001 — jangan pernah menggagalkan pencatatan jejak
            _ent = ""
    entry = {
        "id": new_id("amlog"),
        "entity_id": _ent,
        "stage": stage, "stage_label": st.get("label") or stage_label(stage),
        "doc_type": st.get("doc_type") or "", "doc_label": st.get("doc_label") or "",
        "doc_id": (doc or {}).get("id") or "", "doc_number": (doc or {}).get("number") or "",
        "amount": _as_float((doc or {}).get("total_amount")
                            or (doc or {}).get("total_est_amount")
                            or (doc or {}).get("target_price"), 0.0),
        "action": action, "level": int(level or 1), "level_label": level_label,
        "actor_id": (actor or {}).get("id", ""), "actor_name": (actor or {}).get("name", ""),
        "actor_role": (actor or {}).get("role", ""),
        "requester": (doc or {}).get("created_by") or (doc or {}).get("submitted_by") or "",
        "outcome": outcome, "note": note[:600], "enforced": bool(enforced),
        "violation": bool(violation),
        "reasons": [r.get("code", "") for r in (reasons or [])],
        "created_at": now_iso(),
    }
    await db[LOG_COLL].insert_one(dict(entry))
    try:  # jejak ganda di audit_logs supaya muncul di Master Data & Audit
        from dependencies import audit
        await audit(entry["actor_name"], f"approval_matrix_{action}",
                    st.get("collection") or "approval_matrix", entry["doc_id"],
                    {"stage": stage, "level": entry["level"], "outcome": outcome,
                     "violation": entry["violation"]}, reason=note[:400])
    except Exception as exc:  # noqa: BLE001 — jejak utama sudah tersimpan
        logger.warning("[record] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return safe_doc(entry)


async def log(entity_id: str = "", stage: str = "", limit: int = 50,
              only_violations: bool = False) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    if stage:
        q["stage"] = stage
    if only_violations:
        q["violation"] = True
    rows = await db[LOG_COLL].find(q, {"_id": 0}).sort("created_at", -1).to_list(
        max(1, min(int(limit or 50), 300)))
    return [safe_doc(r) for r in rows]


# ─── Antrean "Persetujuan Saya" ──────────────────────────────────────
def _days_waiting(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
    except Exception:  # noqa: BLE001
        return 0


def _scope(entity_id: str) -> Dict[str, Any]:
    return {} if (not entity_id or entity_id == "all") else {"entity_id": entity_id}


def _looks_like_account(v: str) -> bool:
    """Nilai pengaju yang merupakan KUNCI akun (email / id `user_…`), bukan nama orang."""
    s = (v or "").strip()
    return "@" in s or s.startswith("user_")


async def _person_names(values: List[str]) -> Dict[str, str]:
    """Fase 4 · R5 — email/id akun → NAMA orang (satu kueri). Nilai yang sudah berupa nama tidak disentuh.

    Kolom pengaju Matriks divisi dulu menampilkan "admin@kainnusantara.id": `special_orders.created_by` menyimpan
    EMAIL pembuat, dokumen lain menyimpan nama. Layar menebak nama dari bagian depan email (hanya pemegang
    `user.view` yang bisa memetakan) — kini server yang menerjemahkan untuk semua peran.
    """
    keys = sorted({str(v).strip() for v in values if _looks_like_account(str(v or ""))})
    if not keys:
        return {}
    emails = [k.lower() for k in keys if "@" in k]
    ids = [k for k in keys if "@" not in k]
    out: Dict[str, str] = {}
    try:
        users = await db.users.find({"$or": [{"email": {"$in": emails}}, {"id": {"$in": ids}}]},
                                    {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(len(keys) + 5)
    except Exception as exc:  # noqa: BLE001 — nama hanya hiasan; antrean tetap harus tampil
        logger.warning("[my_queue] nama pengaju gagal dibaca: %s", exc)
        return {}
    by_email = {str(u.get("email") or "").lower(): u.get("name") or "" for u in users}
    by_id = {str(u.get("id") or ""): u.get("name") or "" for u in users}
    for k in keys:
        name = by_email.get(k.lower()) if "@" in k else by_id.get(k)
        if name:
            out[k] = name
    return out


async def my_queue(actor: Dict[str, Any], entity_id: str = "",
                   stage: str = "") -> Dict[str, Any]:
    """Semua dokumen yang MENUNGGU keputusan, lintas 4 tahap matriks.

    Setiap baris membawa `can_decide` + `block_reasons` supaya UI bisa menonaktifkan
    tombol dengan alasan yang jujur (bukan menyembunyikan pekerjaan).
    """
    cfg = await settings(entity_id)
    base = _scope(entity_id)
    items: List[Dict[str, Any]] = []
    from services import dual_control as _dc

    async def _add(stage_id: str, doc: Dict[str, Any], *, title: str, amount: float,
                   requester: str, since: str, ready: bool = True,
                   ready_note: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
        st = STAGE_BY_ID[stage_id]
        ev = await evaluate(stage_id, actor, doc, cfg, amount=amount)   # KP-T4 — Aturan Persetujuan
        reasons = list(ev.get("reasons") or [])
        can = bool(ev.get("allowed"))
        # KF-T6 — pengaju ≠ pemutus dari `dual_control` (penilaian tanpa efek; I/O hanya untuk dokumen milik aktor).
        aksi = STAGE_AKSI.get(stage_id) or ("klaim_makloon" if stage_id == "makloon_claim" else "")
        pengaju = [requester] if stage_id == "makloon_claim" else None
        if aksi and _dc.pelaku_sama(doc, actor or {}, pengaju):
            dc = await _dc.periksa(aksi, doc, actor or {}, doc.get("entity_id", "") or entity_id,
                                   nominal=_as_float(amount), pengaju=pengaju)
            if dc["ditolak"]:
                can = False
                reasons = reasons + [{"code": "sod", "message": dc["pesan"]}]
        if not ready:
            can = False
            reasons = reasons + [{"code": "not_ready", "message": ready_note}]
        items.append({
            "stage": stage_id, "stage_label": st["label"], "doc_type": st["doc_type"],
            "doc_label": st["doc_label"], "view": st["view"],
            "id": doc.get("id", ""), "number": doc.get("number", ""), "title": title,
            "amount": _as_float(amount), "requester": requester,
            "created_at": since, "days_waiting": _days_waiting(since),
            "entity_id": doc.get("entity_id", ""),
            "level": ev.get("level", 1), "level_label": ev.get("level_label", ""),
            "levels_total": ev.get("levels_total", 1),
            "required_roles": ev.get("roles", []),
            "required_roles_label": ev.get("roles_label", ""),
            "approval_chain": doc.get("approval_chain") or [],
            "ready": bool(ready),
            "can_decide": can, "block_reasons": [r["message"] for r in reasons],
            "enforced": ev.get("enforced", True), "skip_reason": ev.get("skip_reason", ""),
            **(extra or {}),
        })

    want = (stage or "").strip()

    if not want or want == "design_acc":
        for d in await db.md_specs.find({**base, "status": "review"}, {"_id": 0}
                                        ).sort("created_at", -1).to_list(200):
            await _add("design_acc", d, title=d.get("title") or "(tanpa judul)",
                       amount=_as_float(d.get("target_price")),
                       requester=d.get("submitted_by") or d.get("created_by") or "",
                       since=d.get("submitted_at") or d.get("created_at") or "")

    if not want or want == "sample_acc":
        cur = db.md_samples.find({**base, "status": {"$in": ["in_progress", "assessed"]}},
                                 {"_id": 0}).sort("created_at", -1)
        for d in await cur.to_list(200):
            if (d.get("decision") or {}).get("supplier_id"):
                continue
            rounds = d.get("rounds") or []
            ready = any(r.get("result") == "acc" for r in rounds)
            await _add("sample_acc", d, title=d.get("title") or d.get("spec_number") or "",
                       amount=_as_float(d.get("cost_total")),
                       requester=d.get("created_by") or "",
                       since=d.get("created_at") or "", ready=ready,
                       ready_note=("Belum ada round yang ACC — nilai dulu hasil sample "
                                   "sebelum memilih pemenang."),
                       extra={"rounds": len(rounds),
                              # FASE S — daftar jenis (labdip + handfeel), bukan satu
                              # kata. Antrean keputusan menyebut PEKERJAAN apa yang
                              # menunggu; satu kata akan menyembunyikan separuhnya.
                              "sample_types": [str(t).strip().lower()
                                               for t in (d.get("sample_types") or [])
                                               if str(t or "").strip()]
                              or ([str(d.get("sample_type") or "").strip().lower()]
                                  if d.get("sample_type") else [])})

    if not want or want == "purchase_request":
        for d in await db.purchase_requisitions.find(
                {**base, "status": "pending_approval"}, {"_id": 0}
        ).sort("created_at", -1).to_list(200):
            await _add("purchase_request", d,
                       title=(d.get("reason") or f"{len(d.get('items') or [])} item kebutuhan"),
                       amount=_as_float(d.get("total_est_amount")),
                       requester=d.get("created_by") or "",
                       since=d.get("created_at") or "",
                       extra={"warehouse_name": d.get("warehouse_name", ""),
                              "lines": len(d.get("items") or [])})

    if not want or want == "po_custom":
        for d in await db.special_orders.find({**base, "status": "pending_approval"},
                                              {"_id": 0}
                                              ).sort("created_at", -1).to_list(200):
            ci = d.get("custom_item") or {}
            await _add("po_custom", d,
                       title=ci.get("description") or "Pesanan khusus",
                       amount=_as_float(d.get("total_amount")),
                       requester=d.get("created_by") or "",
                       since=d.get("created_at") or "",
                       extra={"customer_name": d.get("customer_name", ""),
                              "quantity": _as_float(ci.get("quantity")),
                              "unit": ci.get("unit", "")})

    if not want or want == "makloon_claim":
        cur = db.makloon_orders.find({**base, "steps.claim.status": "pending_approval"},
                                     {"_id": 0}).sort("updated_at", -1)
        for d in await cur.to_list(200):
            for s in d.get("steps") or []:
                cl = s.get("claim") or {}
                if cl.get("status") != "pending_approval":
                    continue
                doc = {**d, "number": d.get("mko_number", ""), "created_by": cl.get("proposed_by", "")}
                await _add("makloon_claim", doc,
                           title=(f"Langkah {s.get('seq')} · {s.get('makloon_name') or 'mitra'} · "
                                  f"{(cl.get('action') or '').replace('_', ' ')} · "
                                  f"{cl.get('message') or cl.get('reason') or ''}").strip(" ·"),
                           amount=_as_float(cl.get("amount")),
                           requester=cl.get("proposed_by") or "",
                           since=cl.get("proposed_at") or cl.get("opened_at") or d.get("updated_at") or "",
                           extra={"step_seq": int(s.get("seq") or 0),
                                  "claim_action": cl.get("action", ""),
                                  "claim_reason": cl.get("reason", ""),
                                  "makloon_name": s.get("makloon_name", ""),
                                  "shortfall_qty": _as_float(cl.get("shortfall_qty")),
                                  "unit": cl.get("unit", "")})

    # Fase 4 · R5 — pengaju tampil sebagai NAMA orang; email/id asli tetap ada (`requester_account`) untuk tooltip.
    names = await _person_names([it["requester"] for it in items])
    for it in items:
        raw = str(it.get("requester") or "").strip()
        it["requester_account"] = raw if _looks_like_account(raw) else ""
        it["requester"] = it["requester_name"] = names.get(raw, raw)
    items.sort(key=lambda x: (not x["can_decide"], -x["days_waiting"], x["stage"]))
    counts = {s["stage"]: 0 for s in APPROVER_MATRIX}
    actionable = 0
    for it in items:
        counts[it["stage"]] = counts.get(it["stage"], 0) + 1
        if it["can_decide"]:
            actionable += 1
    return {
        "items": items, "total": len(items), "actionable": actionable,
        "counts": counts, "config": cfg,
        "stages": [{"stage": s["stage"], "label": s["label"], "doc_label": s["doc_label"],
                    "view": s["view"], "count": counts.get(s["stage"], 0)}
                   for s in APPROVER_MATRIX],
        "actor": {"name": (actor or {}).get("name", ""), "role": (actor or {}).get("role", ""),
                  "role_label": role_label((actor or {}).get("role", ""))},
    }


async def matrix(entity_id: str = "") -> Dict[str, Any]:
    """Matriks + kebijakan penegakan (untuk layar Divisi & Persetujuan / Pusat Persetujuan)."""
    cfg = await settings(entity_id)
    from services import approval_policy_service as _aps
    stages: List[Dict[str, Any]] = []
    for s in APPROVER_MATRIX:
        view = await _aps.policy_view(STAGE_KIND[s["stage"]], entity_id or None)
        lv = []
        for x in view["levels"]:
            t = next((t for t in x["tiers"] if t["roles"] or t["any_holder"]), None)
            if t:
                lv.append({"level": x["level"], "label": x["label"], "roles": t["roles"],
                           "roles_label": ", ".join(t["role_labels"]) or "Semua pemegang akses",
                           "min_amount": t["min_amount"] or 0})
        stages.append({**{k: s[k] for k in ("stage", "label", "approvers", "note",
                                            "doc_type", "doc_label", "view")},
                       "levels": lv, "policy_kind": STAGE_KIND[s["stage"]],
                       "binding": True,
                       "endpoints": _ENDPOINTS.get(s["stage"], [])})
    return {"stages": stages, "config": cfg,
            "approver_matrix": APPROVER_MATRIX}


_ENDPOINTS = {
    "design_acc": ["POST /api/rnd/specs/{id}/approve", "POST /api/rnd/specs/{id}/reject"],
    "sample_acc": ["POST /api/rnd/samples/{id}/decide"],
    "po_custom": ["POST /api/special-orders/{id}/approve",
                  "POST /api/special-orders/{id}/reject"],
    "purchase_request": ["POST /api/purchase-requisitions/{id}/approve",
                         "POST /api/purchase-requisitions/{id}/reject"],
    "makloon_claim": ["POST /api/makloon-orders/{id}/claim/approve",
                      "POST /api/makloon-orders/{id}/claim/reject"],
}


# ─── Bantuan khusus PO Custom (2 tingkat) ─────────────────────────────────
async def special_order_chain(doc: Dict[str, Any], entity_id: str = "") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Rantai persetujuan pesanan khusus (dibuat sekali, lalu dipakai apa adanya)."""
    ent = entity_id or (doc or {}).get("entity_id", "")
    cfg = await settings(ent)
    chain = (doc or {}).get("approval_chain")
    if not chain:   # KP-T4 — jenjang dari Aturan Persetujuan (jenis `special_order`)
        chain = build_chain(await levels_for("po_custom", _as_float((doc or {}).get("total_amount")), ent))
    return chain, cfg
