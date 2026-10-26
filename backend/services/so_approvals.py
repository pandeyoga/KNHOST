"""F5 — Unified Approval SSOT pada Sales Order (`pending_approvals[]`).

Satu sumber kebenaran untuk SEMUA persetujuan SO: `nilai` (threshold nilai order),
`kredit` (over-credit / bypass blokir kredit), `special_price` (harga khusus).
Aturan inti (KEPUTUSAN OWNER §2.4):
  SO TIDAK boleh naik ke stage **Approved** sampai SEMUA entri `pending_approvals`
  berstatus `approved`. Koleksi detail (`price_approvals`, `credit_overrides`) tetap
  dipakai sebagai bukti/rincian, tapi STATUS keputusan DICERMINKAN di sini (1 SSOT).

ADDITIVE & idempotent: field `pending_approvals` embedded di dokumen `sales_orders`
(bukan koleksi baru). `so_status.derive_stage_substatus` membaca daftar ini untuk
menurunkan sub-status (menunggu_approval_nilai/kredit/harga).
"""
from typing import Any, Dict, List, Optional, Tuple
from core_utils import new_id, now_iso

APPROVAL_TYPES = {"nilai", "kredit", "special_price", "pembayaran_sampel", "makloon"}

# Hirarki role approver — SATU sumber: `backend/role_registry.py` (FASE E-8/E8.1).
# Dulu angkanya ditulis ulang di sini dan di `config_service.role_satisfies`, jadi
# menambah peran `sales_admin`/`finance` berarti dua tempat harus diingat.
from role_registry import ROLE_RANK  # noqa: E402  (dipakai di bawah)

TYPE_LABELS = {
    "nilai": "Approval Nilai Order",
    "kredit": "Approval Kredit (Over-limit)",
    "special_price": "Approval Harga Khusus",
    "pembayaran_sampel": "Persetujuan Pembayaran Sample",
}


def make_approval(
    atype: str,
    required_role: str = "manager",
    reason: str = "",
    requested_by: str = "",
    requested_by_id: str = "",
    ref_id: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Bangun 1 entri pending_approval (status awal `pending`)."""
    entry = {
        "id": new_id("soappr"),
        "type": atype if atype in APPROVAL_TYPES else "nilai",
        "required_role": required_role or "manager",
        "status": "pending",
        "reason": (reason or "").strip(),
        "requested_by": requested_by or "",
        "requested_by_id": requested_by_id or "",
        "requested_at": now_iso(),
        "decided_by": None,
        "decided_by_id": None,
        "decided_at": None,
        "decision_notes": "",
        "evidence": [],
        "ref_id": ref_id,
    }
    entry.update(extra)
    return entry


# F-09 (uji pra-UAT 2026-10-21) — tipe yang boleh diajukan ulang sesudah DITOLAK. Pengajuan baru
# untuk kunci yang sama menggantikan penolakan lama; tanpa ini `has_rejected` mengunci SO selamanya.
RESUBMITTABLE_TYPES = {"special_price", "kredit"}


def _resubmit_key(p: Dict[str, Any]) -> tuple:
    """Kunci "pengajuan yang sama": harga khusus per produk (dan per item Pesanan Khusus — UAT 24 Okt P2.2: dua item
    OD ber-SKU sama adalah dua baris nego berbeda), kredit per tipe."""
    if p.get("type") != "special_price":
        return (p.get("type"), None, None)
    return (p.get("type"), p.get("product_id"), p.get("special_order_item_id") or "")


def _mark_superseded(p: Dict[str, Any], by_id: str) -> None:
    # Keputusan lama (decided_by/at, decision_notes) TIDAK ditimpa — riwayat tetap utuh.
    p.update({"status": "superseded", "previous_status": "rejected",
              "superseded_by": by_id, "superseded_at": now_iso()})


def supersede_rejected(pa: List[Dict[str, Any]], new_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tandai entri `rejected` berkunci sama dengan `new_entry` sebagai `superseded` (in-place)."""
    if new_entry.get("type") not in RESUBMITTABLE_TYPES:
        return []
    key = _resubmit_key(new_entry)
    out = [p for p in pa if p is not new_entry and p.get("status") == "rejected" and _resubmit_key(p) == key]
    for p in out:
        _mark_superseded(p, new_entry["id"])
    return out


def repair_resubmitted_rejections(pa: List[Dict[str, Any]]) -> int:
    """Data sebelum F-09: penolakan yang SUDAH diikuti pengajuan berkunci sama ditandai
    `superseded` oleh entri sesudahnya (in-place, idempoten). Penolakan tanpa pengajuan
    ulang dibiarkan — tetap memblokir (KN-D02)."""
    n = 0
    for i, p in enumerate(pa):
        if p.get("status") != "rejected" or p.get("type") not in RESUBMITTABLE_TYPES:
            continue
        nxt = next((q for q in pa[i + 1:] if _resubmit_key(q) == _resubmit_key(p)), None)
        if nxt:
            _mark_superseded(p, nxt.get("id"))
            n += 1
    return n


def cancel_for_removed_products(pa: List[Dict[str, Any]], product_ids, reason: str,
                                actor_name: str = "") -> List[Dict[str, Any]]:
    """Keputusan owner 2026-10-21 (lanjutan F-09) — baris dihapus dari pesanan (Override SO / batal item OD)
    → entri harga khusus produk itu yang masih MENUNGGU atau DITOLAK dibatalkan (in-place). Tanpa ini entri
    menunggu tak bisa disetujui ("produk sudah tidak ada") dan entri ditolak mengunci SO selamanya karena
    produknya tak bisa diajukan ulang. Riwayat keputusan lama tidak ditimpa; yang sudah disetujui dibiarkan."""
    ids = {str(p) for p in product_ids if p}
    out: List[Dict[str, Any]] = []
    for p in pa:
        if p.get("type") == "special_price" and str(p.get("product_id")) in ids and p.get("status") in ("pending", "rejected"):
            p.update({"status": "cancelled", "previous_status": p.get("status"), "cancel_reason": reason,
                      "cancelled_by": actor_name, "cancelled_at": now_iso()})
            out.append(p)
    return out


async def cancel_price_docs(database, entries: List[Dict[str, Any]], reason: str, actor_name: str = "") -> None:
    """Dokumen `price_approvals` milik entri yang dibatalkan: yang masih menunggu ikut `cancelled`;
    yang sudah ditolak tetap `rejected` (riwayat keputusan, sama dengan F-09)."""
    ids = [e.get("ref_id") for e in entries if e.get("ref_id")]
    if ids:
        await database.price_approvals.update_many(
            {"id": {"$in": ids}, "status": "pending"},
            {"$set": {"status": "cancelled", "cancel_reason": reason, "cancelled_by": actor_name,
                      "cancelled_at": now_iso(), "updated_at": now_iso()}})


# ─── Fase 4 · R8 (26 Okt 2026) — SO MATI ─────────────────────────────────────────────────────────────────────────
# Batal/kedaluwarsa dulu tidak menyentuh `pending_approvals`: entri tetap `pending` selamanya, muncul di Pusat
# Persetujuan & bisa "disetujui" (data acuan: KANDA/SO-00001 & KSC/SOS-00003 kedaluwarsa, KSC/SOS-00013 batal).
# Status mati = SATU definisi `approval_backlog_service.SO_DEAD_STATUSES` (antrean, KPI, Pusat Persetujuan).

#: Transisi yang MEMATIKAN SO (entri menunggu ditutup). `done` tidak: pesanan selesai bukan pesanan batal.
DEAD_TRANSITIONS = ("cancelled", "expired", "rejected", "void")
_DEAD_WORD = {"cancelled": "dibatalkan", "expired": "kedaluwarsa", "rejected": "ditolak", "void": "dibatalkan",
              "done": "selesai"}
_DEAD_REASON = {"cancelled": "Pesanan dibatalkan", "expired": "Reservasi pesanan kedaluwarsa",
                "rejected": "Pesanan ditolak", "void": "Pesanan dibatalkan (void)"}


def dead_statuses() -> Tuple[str, ...]:
    from services.approval_backlog_service import SO_DEAD_STATUSES  # impor malas: modul ini tetap murni
    return tuple(SO_DEAD_STATUSES)


def closed_order_message(order: Dict[str, Any]) -> str:
    """Kalimat 409 bila SO sudah mati (keputusan persetujuan tidak berlaku lagi); "" bila SO masih hidup."""
    st = (order or {}).get("status") or ""
    if st not in dead_statuses():
        return ""
    tail = "" if st == "done" else " Buat pesanan baru bila masih diperlukan."
    return (f"Pesanan {(order or {}).get('number') or ''} sudah {_DEAD_WORD.get(st, st)} — persetujuannya tidak "
            f"berlaku lagi dan tidak bisa diputuskan.{tail}")


def dead_order_patch(order: Dict[str, Any], new_status: str, reason: str = "",
                     actor_name: str = "") -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """($set tambahan, entri yang ditutup) untuk transisi SO ke status mati.

    Entri yang masih MENUNGGU → `cancelled` (+ `previous_status`, alasan, pelaku); keputusan lama (approved/rejected/
    superseded) tidak disentuh — riwayat utuh. `has_backorder` → False: baris pendingan SO mati tidak menunggu barang
    lagi (`backorders` tetap sebagai riwayat). Status lain → ({}, [])."""
    if new_status not in DEAD_TRANSITIONS:
        return {}, []
    why = (reason or "").strip() or _DEAD_REASON.get(new_status, "Pesanan ditutup")
    pa = [dict(p) for p in (order or {}).get("pending_approvals") or []]
    closed: List[Dict[str, Any]] = []
    for p in pa:
        if p.get("status") == "pending":
            p.update({"status": "cancelled", "previous_status": "pending", "cancel_reason": why,
                      "cancelled_by": actor_name, "cancelled_at": now_iso()})
            closed.append(p)
    patch: Dict[str, Any] = {"has_backorder": False}
    if closed:
        patch["pending_approvals"] = pa
        patch.update(approval_fields({**(order or {}), "pending_approvals": pa}, require_validation=False))
    return patch, closed


async def close_detail_docs(database, closed: List[Dict[str, Any]], reason: str, actor_name: str = "") -> None:
    """Dokumen rincian entri yang ditutup ikut `cancelled` bila masih `pending` (yang sudah diputus dibiarkan).
    Tanpa ini override kredit SO mati yang kelak di-ACC lewat layar Pelanggan bisa TERPAKAI pesanan lain."""
    await cancel_price_docs(database, [e for e in closed if e.get("type") == "special_price"], reason, actor_name)
    cro = [e.get("ref_id") for e in closed if e.get("type") == "kredit" and e.get("ref_id")]
    if cro:
        await database.credit_overrides.update_many(
            {"id": {"$in": cro}, "status": "pending"},
            {"$set": {"status": "cancelled", "cancel_reason": reason, "cancelled_by": actor_name,
                      "cancelled_at": now_iso(), "updated_at": now_iso()}})


def summarize(order: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkas state gate approval dari `pending_approvals`."""
    pa: List[Dict[str, Any]] = order.get("pending_approvals") or []
    pending = [p for p in pa if p.get("status") == "pending"]
    rejected = [p for p in pa if p.get("status") == "rejected"]
    req_role: Optional[str] = None
    best = 0
    for p in pending:
        r = p.get("required_role")
        if ROLE_RANK.get(r, 0) > best:
            best = ROLE_RANK.get(r, 0)
            req_role = r
    return {
        "total": len(pa),
        "has_pending": bool(pending),
        "has_rejected": bool(rejected),
        "all_resolved": len(pending) == 0,           # tak ada yang menunggu keputusan
        "all_approved": len(pending) == 0 and len(rejected) == 0,
        "pending_count": len(pending),
        "rejected_count": len(rejected),
        "required_role": req_role,
        "pending_types": [p.get("type") for p in pending],
    }


def require_validation_default(settings: Optional[Dict[str, Any]]) -> bool:
    """Apakah SO wajib divalidasi admin/manager sebelum Confirmed (KEPUTUSAN OWNER §1.7).
    Default WAJIB (True); bisa dimatikan via settings.sales.require_so_validation=False."""
    s = (settings or {}).get("sales", {}) if settings else {}
    return bool(s.get("require_so_validation", True))


def approval_fields(order: Dict[str, Any], require_validation: bool = True) -> Dict[str, Any]:
    """Hitung `approval_required` + `required_approval_role` dari pending_approvals
    digabung kebijakan validasi admin. Dipakai $set ke dokumen SO."""
    s = summarize(order)
    requires = s["has_pending"]
    req_role = s["required_role"]
    if require_validation and not requires:
        # Validasi admin tetap diperlukan walau tak ada approval spesifik (siap_disahkan).
        requires = True
        req_role = req_role or order.get("required_approval_role") or "manager"
    return {
        "approval_required": bool(requires),
        "required_approval_role": req_role,
    }


def all_approved(order: Dict[str, Any]) -> bool:
    """True bila tak ada entri pending/rejected (boleh naik ke Approved)."""
    return summarize(order)["all_approved"]


def public_view(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Daftar pending_approvals diperkaya label untuk FE (read-only)."""
    out: List[Dict[str, Any]] = []
    for p in (order.get("pending_approvals") or []):
        d = dict(p)
        d["type_label"] = TYPE_LABELS.get(p.get("type"), p.get("type"))
        d["evidence"] = [a for a in (p.get("evidence") or []) if not a.get("is_deleted")]
        out.append(d)
    return out


async def backfill_pending_approvals(database) -> Dict[str, int]:
    """F5 — sinkronkan SSOT `pending_approvals` untuk SO lama (ADDITIVE & idempotent).

    - SO 'open' (reserved/waiting_approval/waiting_stock/draft) dengan `approval_required`
      tapi belum punya entri pending → buat 1 entri `nilai` (validasi admin) supaya muncul
      di Pusat Persetujuan & konsisten dgn model F5.
    - Pastikan field `pending_approvals` (list) & `credit_hold` (bool) selalu ada.
    TIDAK mengubah SO yang sudah punya pending_approvals. Aman dijalankan berkali-kali.
    """
    OPEN = ("reserved", "waiting_approval", "waiting_stock", "draft")
    updated = 0
    total = 0
    async for o in database.sales_orders.find({}, {"_id": 0}):
        total += 1
        pa = o.get("pending_approvals")
        sets: Dict[str, Any] = {}
        if pa is None:
            pa = []
            sets["pending_approvals"] = pa
        if "credit_hold" not in o:
            sets["credit_hold"] = False
        if (((o.get("status") == "waiting_approval")
                or (o.get("status") in OPEN and o.get("approval_required")))
                and not any(p.get("status") == "pending" for p in pa)):
            pa = list(pa) + [make_approval(
                "nilai", required_role=o.get("required_approval_role") or "manager",
                reason="Validasi nilai order (sinkronisasi F5).",
                requested_by=o.get("sales_name", ""),
                amount=float(o.get("grand_total", o.get("total_amount", 0)) or 0))]
            sets["pending_approvals"] = pa
        if sets:
            sets["updated_at"] = now_iso()
            await database.sales_orders.update_one({"id": o["id"]}, {"$set": sets})
            updated += 1
    return {"updated": updated, "total": total}


async def backfill_resubmitted_rejections(database, apply: bool = False) -> Dict[str, Any]:
    """F-09 — perbaiki SO terbuka yang terkunci penolakan yang sudah diajukan ulang
    (pola KSC/SO-00039). `apply=False` hanya melaporkan. SO TIDAK dinaikkan otomatis:
    Manajer tetap menekan Setujui (kini tidak lagi 409 APPROVAL_REJECTED)."""
    OPEN = ("reserved", "waiting_approval", "waiting_stock", "draft")
    found: List[Dict[str, Any]] = []
    query = {"status": {"$in": list(OPEN)}, "pending_approvals.status": "rejected"}
    async for o in database.sales_orders.find(query, {"_id": 0, "id": 1, "number": 1, "pending_approvals": 1}):
        pa = list(o.get("pending_approvals") or [])
        n = repair_resubmitted_rejections(pa)
        if not n:
            continue
        found.append({"id": o["id"], "number": o.get("number"), "superseded": n,
                      "still_rejected": summarize({"pending_approvals": pa})["rejected_count"]})
        if apply:
            await database.sales_orders.update_one(
                {"id": o["id"]}, {"$set": {"pending_approvals": pa, "updated_at": now_iso()}})
    return {"applied": apply, "orders": found}
