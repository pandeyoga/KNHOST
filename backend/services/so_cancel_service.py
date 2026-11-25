"""services/so_cancel_service.py — permintaan batal pesanan + persetujuan (BTP-2).

Rancangan `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` §5.1–§5.4, §5.8 (keputusan pemilik
A2-1…A2-5, 25 Nov 2026). Dulu pemegang `order.cancel` membatalkan pesanan langsung, termasuk pesanan yang sudah dibayar
atau yang barangnya sudah disiapkan gudang. Sekarang satu pintu:

* `submit` — jalur masuk tunggal (`POST /sales-orders/{id}/cancel`; Tugas 4 menambah tutup sisa). Menilai
  `needs_approval` (pengaturan `sales.cancel_approval_when` + Aturan Persetujuan jenis `sales_order.batal`):
    - tidak wajib → eksekusi langsung (perilaku lama, 200);
    - wajib dan pengaju lolos aturan memutus → disetujui sendiri (`self_approved=True`), eksekusi di permintaan yang
      sama (200);
    - selain itu → `cancel_request` menunggu (202) + notifikasi ke pemegang izin `order.approve_cancel`.
* `decide` (setujui/tolak), `withdraw` (tarik), `void_pending` (pesanan mati lewat jalur lain, mis. kedaluwarsa).
* Siapa boleh memutus (`can_decide`): izin + rentang nominal (`approval_policy_service`), akses PT, **bukan sales
  pesanan** (`sales_id` / anggota `sales_team` — bukan `created_by`, bukan cakupan tim) dan bukan pengaju.

Data (§5.1): satu objek aktif `sales_orders.cancel_request`; putusan/penarikan/void memindahkan objek final ke riwayat
`cancel_requests[]` ($push) dan mengosongkan yang aktif ($unset). Semua transisi bersyarat
`{"cancel_request.status": "pending", "cancel_request.id": <id>}`. Selama eksekusi persetujuan berjalan, objek aktif
diberi penanda `deciding` (sewa singkat bertoken) supaya setujui/tolak/tarik yang datang bersamaan kalah 409 dan
eksekusi berjalan sekali.

Eksekutor per aksi: `EXECUTORS` (`execute_cancel` = isi lama endpoint batal, tanpa perubahan perilaku). Penilai per
aksi: `ASSESSORS` (status boleh + nominal dasar kebijakan + kelebihan uang, opsional `preview`). Tugas 4 menambah
`"close_remaining"` di keduanya.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso, rupiah, safe_doc
from db import db

logger = logging.getLogger(__name__)

KIND = "sales_order.batal"                      # approval_kinds.APPROVAL_KINDS (Tugas 1)
NOTIF_REQUEST = "permintaan_batal_pesanan"
NOTIF_DECIDED = "permintaan_batal_diputus"
ACTION_TYPE = "so_cancel_request"
# Tautan notifikasi = layar Pesanan Penjualan: modul `penjualan` memuat sumber daya `order`, jadi SIAPA PUN pemegang
# `order.approve_cancel` (Finance, Manager, peran kustom tanpa acuan) boleh membukanya (penyaring relevansi tautan,
# `notification_scope`). `approval-inbox` tidak: ia milik modul Pusat Persetujuan/Harga/Pembelian.
LINK = "orders"
MESSAGE_PENDING = "Permintaan diajukan — menunggu persetujuan."
STATUSES = ("pending", "approved", "rejected", "withdrawn", "void")
ACTION_LABEL = {"cancel": "pembatalan", "close_remaining": "tutup sisa"}
FAIL_MESSAGE = {"cancel": "Pembatalan belum bisa dijalankan — coba lagi atau hubungi Admin.",
                "close_remaining": "Tutup sisa belum bisa dijalankan — coba lagi atau hubungi Admin."}
DONE_LABEL = {"cancel": "pesanan dibatalkan", "close_remaining": "sisa pesanan ditutup"}
BASIS_LABEL = {"paid": "sudah ada pembayaran", "prepared": "barang sudah disiapkan gudang",
               "excess": "ada kelebihan uang yang pindah ke titipan"}
CANCEL_BLOCKED = ("done", "cancelled", "expired", "partially_shipped", "shipped")
TASK_INACTIVE = ("dispatched", "completed", "cancelled")
TASK_PREPARED = ("packing", "staging")
ROLL_HELD_MOVING = ("committed", "picked", "packed")   # roll sisa yang sudah bergerak tetapi belum berangkat
# Batas TEKNIS (bukan aturan bisnis): penanda `deciding` yang lebih tua dari ini dianggap milik proses yang mati,
# sehingga permintaan tidak tertahan selamanya (setara kunci saga yang dilepas admin).
DECIDING_STALE_MINUTES = 10


# ── Identitas & bentuk ──────────────────────────────────────────────────────────────────────────────────────────────
def is_order_sales(order: Dict[str, Any], actor: Dict[str, Any]) -> bool:
    """Aktor = sales pesanan (`sales_id`) atau anggota tim penjualannya (`sales_team[].sales_id`, K-21).

    Sengaja BUKAN `sales_ownership.owns`: `created_by` tidak dihitung (Manager/Admin yang menginput atas nama sales tetap
    boleh memutus) dan cakupan "tim" tidak dihitung (supervisor boleh memutus pesanan anggotanya) — rancangan §5.3."""
    uid = str((actor or {}).get("id") or "")
    if not uid:
        return False
    o = order or {}
    return uid == str(o.get("sales_id") or "") or any(
        uid == str(m.get("sales_id") or "") for m in (o.get("sales_team") or []) if isinstance(m, dict))


def _public(req: Dict[str, Any]) -> Dict[str, Any]:
    """Objek permintaan tanpa penanda proses internal."""
    return {k: v for k, v in (req or {}).items() if k != "deciding"}


def _actor_name(actor: Dict[str, Any]) -> str:
    return str((actor or {}).get("name") or (actor or {}).get("email") or "")


def _pending_message(order: Dict[str, Any], req: Dict[str, Any]) -> str:
    label = ACTION_LABEL.get(req.get("action") or "cancel", "pembatalan")
    oleh = f" oleh {req.get('requested_by')}" if req.get("requested_by") else ""
    return (f"Pesanan {order.get('number') or ''} sudah punya permintaan {label} yang menunggu keputusan "
            f"(diajukan{oleh}). Tunggu keputusannya atau tarik permintaan itu dulu.").replace("  ", " ")


async def _load(order_id: str) -> Dict[str, Any]:
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    return order


async def pending_of(order_id: str) -> Optional[Dict[str, Any]]:
    """Permintaan batal/tutup sisa yang sedang menunggu untuk pesanan ini, atau None."""
    o = await db.sales_orders.find_one({"id": order_id, "cancel_request.status": "pending"},
                                       {"_id": 0, "cancel_request": 1})
    return _public(o["cancel_request"]) if o else None


MESSAGE_HELD = "Pesanan sedang diajukan batal/tutup sisa — tunggu keputusan."
HELD_LABEL = "Ditahan: menunggu keputusan batal"


async def assert_not_pending(order_id: str) -> None:
    """Pintu tahan (A2-4, §5.5/§5.6a): kirim, ambil, maju tahap, eskalasi tutup-sisa, dan batal item Pesanan Khusus
    ditolak 409 selama ada permintaan batal/tutup sisa menunggu. Satu teks untuk semua pintu; tidak mengubah apa pun."""
    if order_id and await pending_of(order_id):
        raise HTTPException(status_code=409, detail=MESSAGE_HELD)


async def held_orders(order_ids: List[str]) -> set:
    """Id pesanan (dari `order_ids`) yang punya permintaan menunggu — SATU kueri untuk seluruh halaman daftar."""
    ids = [i for i in dict.fromkeys(order_ids) if i]
    if not ids:
        return set()
    rows = await db.sales_orders.find({"id": {"$in": ids}, "cancel_request.status": "pending"},
                                      {"_id": 0, "id": 1}).to_list(len(ids))
    return {r["id"] for r in rows}


# ── Eksekusi batal (isi lama `POST /sales-orders/{id}/cancel`) ──────────────────────────────────────────────────────
async def _assert_cancellable(order: Dict[str, Any]) -> None:
    if order["status"] in CANCEL_BLOCKED:
        raise HTTPException(status_code=409, detail="Order tidak bisa dibatalkan (sudah terkirim sebagian/penuh atau terminal)")
    # P16 (SALE-03) — Faktur Pajak aktif sudah/akan dilaporkan (NSFP); membatalkan SO diam-diam
    # meninggalkan PPN Keluaran tanpa transaksi. Batalkan Faktur Pajaknya dulu (beralasan).
    fkt = await db.tax_invoices.find_one({"order_id": order["id"], "status": {"$ne": "batal"}},
                                         {"_id": 0, "number": 1})
    if fkt:
        raise HTTPException(status_code=409, detail=(
            f"Pesanan ini sudah punya Faktur Pajak aktif ({fkt.get('number')}). "
            "Batalkan Faktur Pajak tersebut dulu (menu Faktur Pajak → Batalkan, alasan wajib), "
            "lalu batalkan pesanan."))


async def execute_cancel(order_id: str, actor: Dict[str, Any], reason: str, request_id: str = "") -> Dict[str, Any]:
    """Batalkan pesanan — isi lama endpoint batal sesudah pemeriksaan izin/kepemilikan/alasan, TANPA perubahan
    perilaku. Status & Faktur Pajak diperiksa lagi di sini (keadaan bisa berubah selama permintaan menunggu)."""
    from dependencies import audit
    from services.roll_service import release_order_rolls
    from services.sales_order_helpers import so_transition as _transition
    order = await _load(order_id)
    await _assert_cancellable(order)
    # T-01 Opsi B (INV-ATOMIC-01) — klaim SO sebelum roll dilepas + task gudang dibatalkan
    # + jurnal dibalik (3 koleksi tanpa transaksi). Kunci dicabut oleh `so_transition`.
    from services import atomic_claim as _saga
    await _saga.claim("sales_orders", order_id, "order_cancel",
                      precondition={"status": order["status"]}, actor=actor["name"])
    # FIX-3b — (STM-OUT-4) roll SELALU dilepas untuk status non-terminal mana pun, termasuk `draft` (Ganti Roll pada
    # draf dulu meninggalkan roll `reserved` untuk pesanan mati). (FLW-OUT-4) roll yang SUDAH diambil dari rak →
    # "kembalikan ke rak" (bin dikosongkan, antrean Penempatan Rak), bukan langsung tampil di bin asal yang kosong.
    picked_ids: List[str] = []
    async for t in db.wms_tasks.find({"order_id": order_id, "flow_type": "outbound",
                                      "status": {"$nin": ["dispatched", "cancelled", "completed"]}},
                                     {"_id": 0, "scan_log": 1, "roll_id": 1, "task_subtype": 1}):
        picked_ids += [e.get("roll_id") for e in t.get("scan_log") or []
                       if e.get("scan_type") == "pick" and e.get("roll_id")]
        if t.get("task_subtype") == "sample_cut" and t.get("roll_id"):
            picked_ids.append(t["roll_id"])
    await release_order_rolls(order_id, return_to_rack_ids=picked_ids, why=f"SO dibatalkan: {reason}")
    result = await _transition(order_id, [order["status"]], "cancelled", actor["name"], "order_cancelled",
                               {"cancel_reason": reason, "cancelled_by": actor["name"], "cancelled_at": now_iso(),
                                # penanda eksekusi permintaan ini (bukan jalur batal lain) — dibaca `_execute_and_finalize`
                                **({"cancel_request_id": request_id} if request_id else {})})
    # S3 (pelatihan 18 Nov) — uang muka yang sudah diterima pesanan ini menjadi TITIPAN pelanggan (tanpa jurnal:
    # sama-sama 2-1400). Dulu tertinggal di pesanan mati: tidak bisa dikembalikan maupun dipakai pesanan lain.
    from services import ar_receipt_service as _ar
    try:
        result["advance_to_deposit"] = await _ar.uang_muka_pesanan_batal_ke_titipan(order_id, actor, reason)
    except Exception as exc:  # noqa: BLE001 — pesanan sudah batal; pemindahan aman diulang (dicatat untuk Finance)
        logger.error("Uang muka pesanan batal %s gagal dipindah ke titipan: %s", order_id, exc)
        result["advance_to_deposit"] = 0.0
        result["advance_to_deposit_error"] = "Uang muka pesanan ini belum terpindah ke titipan pelanggan — hubungi Finance."
    if result.get("advance_to_deposit"):
        await audit(actor["name"], "advance_moved_to_deposit", "sales_order", order_id,
                    {"amount": result["advance_to_deposit"], "customer_id": order.get("customer_id", ""),
                     "reason": reason})
    # 2026-10 — dokumen pemenuhan (transfer/PR) dari keputusan Admin Sales TIDAK ikut batal otomatis:
    # disebut di respons agar ditindaklanjuti, dan sales pemilik diberi tahu di aplikasi.
    result["open_fulfillment_refs"] = sorted({p.get("ref_number") for d in (order.get("fulfillment_decisions") or [])
                                              for p in (d.get("parts") or []) if p.get("ref_number")})
    from services.so_override_service import notify_sales
    await notify_sales(order, actor, f"{order.get('number')} dibatalkan oleh {actor['name']}",
                       f"Alasan: {reason or '-'}")
    # S-4 (Gelombang 2) — batalkan task picking gudang yang masih aktif utk order ini
    # (antrean gudang bersih; barang order batal tidak ikut disiapkan).
    # FIX-3b (STM-OUT-2) — lewat tabel transisi (CAS daftar-izin); eskalasi yang menunggu ikut ditutup.
    from services import outbound_task_state as _ots
    n_cancelled = await _ots.cancel_for_order(order_id, actor["name"], "SO dibatalkan")
    if n_cancelled:
        await audit(actor["name"], "outbound_tasks_cancelled", "sales_order", order_id,
                    {"count": n_cancelled, "reason": "SO dibatalkan",
                     "return_to_rack": len(picked_ids)})
    # Gelombang 1 F-1 — jurnal balik otomatis bila order sudah berjurnal (best-effort).
    try:
        from services import gl_service
        await gl_service.reverse_order_journals(order_id, reason="order dibatalkan",
                                                actor_name=actor["name"])
    except Exception as exc:  # noqa: BLE001 — pesanan sudah batal; galat jurnal balik dicatat, tidak menggagalkan
        logger.error("Gagal reversal GL utk order %s: %s", order_id, exc)
    if order.get("replacement_for_return"):
        from services import return_replacement_service as rpl
        await rpl.on_replacement_cancelled(order, actor)
    if order.get("sample_billing") == "paid" and order.get("sample_payment_status") in ("approved", "reapproval_required"):
        # FIX-3b (B2b CUT-6) — sample berbayar yang dibatalkan: status bayar tidak lagi "disetujui"; Finance diberi tahu
        # untuk pengembalian/pembatalan tagihan.
        await db.sales_orders.update_one({"id": order_id}, {"$set": {
            "sample_payment_status": "refund_pending", "sample_payment_cancelled_at": now_iso(),
            "sample_payment_cancel_reason": reason}})
        result["sample_payment_status"] = "refund_pending"
        try:
            from services import notification_service as _ns
            await _ns.create_notification(
                notif_type="sample_payment_refund", ref=f"sample_refund:{order_id}",
                title=f"Sample berbayar {order.get('number', '')} dibatalkan",
                body=f"{order.get('customer_name', '')} — pembayaran sample perlu dikembalikan/dibatalkan. Alasan: {reason}"[:400],
                severity="warning", link="sample-orders", entity_id=order.get("entity_id") or None,
                recipient_role="finance")
        except Exception:  # noqa: BLE001
            pass
    return result


async def _assess_cancel(order: Dict[str, Any]) -> Dict[str, Any]:
    """Batal penuh: status boleh + Faktur Pajak (409 bila tidak) · nominal dasar = `grand_total` (§5.2)."""
    await _assert_cancellable(order)
    return {"amount": float(order.get("grand_total") or 0), "excess": 0.0}


#: Eksekutor per aksi — `(order_id, actor, reason, request_id="") -> hasil`; `request_id` (bila eksekusi atas nama
#: permintaan) ditulis ke pesanan sebagai penanda. Tugas 4 menambah `"close_remaining"`.
EXECUTORS: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {"cancel": execute_cancel}
#: Penilai per aksi — `(order) -> {"amount", "excess"[, "preview"]}`; 409 bila aksi tidak mungkin untuk pesanan itu.
ASSESSORS: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {"cancel": _assess_cancel}


def _check_action(action: str) -> str:
    a = str(action or "").strip()
    if a not in EXECUTORS or a not in ASSESSORS:
        raise HTTPException(status_code=400, detail=f"Aksi '{a}' tidak dikenal atau belum tersedia.")
    return a


# ── Kapan wajib persetujuan (§5.2) ──────────────────────────────────────────────────────────────────────────────────
async def prepared_basis(order: Dict[str, Any], remaining_only: bool = False) -> bool:
    """"Barang sudah disiapkan" (§5.2): roll pesanan berstatus di luar `reserved`/`available` (pola
    `so_line_cancel_service.check`) ATAU tugas ambil aktif yang sudah mencatat ambil (`scan_log` pick, `picked_qty > 0`)
    atau sudah `packing`/`staging`.

    `remaining_only=True` (tutup sisa) menilai bagian SISA saja: roll yang sudah berangkat (`in_transit_sales`,
    `delivered`) tidak dihitung, dan tugas aktif dihitung bila mengambil lebih dari yang sudah dikirimnya."""
    oid = (order or {}).get("id")
    if not oid:
        return False
    roll_status = {"$in": list(ROLL_HELD_MOVING)} if remaining_only else {"$nin": ["reserved", "available"]}
    if await db.inventory_rolls.find_one({"reserved_ref.id": oid, "status": roll_status}, {"_id": 0, "id": 1}):
        return True
    tasks = await db.wms_tasks.find(
        {"order_id": oid, "flow_type": "outbound", "status": {"$nin": list(TASK_INACTIVE)}},
        {"_id": 0, "status": 1, "picked_qty": 1, "shipped_qty": 1, "scan_log": 1}).to_list(500)
    for t in tasks:
        if t.get("status") in TASK_PREPARED:
            return True
        picked = float(t.get("picked_qty") or 0)
        if remaining_only:
            if picked > float(t.get("shipped_qty") or 0) + 1e-9:
                return True
        elif picked > 0 or any((e or {}).get("scan_type") == "pick" for e in t.get("scan_log") or []):
            return True
    return False


async def needs_approval(order: Dict[str, Any], action: str, *, amount: float,
                         excess: float = 0.0) -> Dict[str, Any]:
    """`{"needs", "basis", "amount"}`. `basis` = alasan wajib-setuju untuk layar: batal → `paid` (`paid_total > 0`);
    tutup sisa → `excess` (kelebihan uang ke titipan > 0); keduanya → `prepared` (`prepared_basis`, tutup sisa atas
    bagian sisa). `needs` = pengaturan `sales.cancel_approval_when` menyatakan wajib (`selalu`, atau
    `dibayar_atau_disiapkan` dengan `basis` tidak kosong) DAN Aturan Persetujuan memberi jenjang untuk `amount`."""
    from services import approval_policy_service as aps
    from services.nilai_pengaturan import nilai
    ent = (order or {}).get("entity_id") or ""
    basis: List[str] = []
    if action == "close_remaining":
        if float(excess or 0) > 0:
            basis.append("excess")
        if await prepared_basis(order, remaining_only=True):
            basis.append("prepared")
    else:
        if float((order or {}).get("paid_total") or 0) > 0:
            basis.append("paid")
        if await prepared_basis(order):
            basis.append("prepared")
    when = str(await nilai("sales.cancel_approval_when", ent)).strip().lower()
    required = when == "selalu" or (when != "tidak_pernah" and bool(basis))
    amt = round(float(amount or 0), 2)
    needs = bool(required and await aps.required_levels(KIND, ent, amt))
    return {"needs": needs, "basis": basis, "amount": amt}


# ── Siapa boleh memutus (§5.3) ──────────────────────────────────────────────────────────────────────────────────────
async def _decide_check(order: Dict[str, Any], amount: float, actor: Dict[str, Any],
                        requester_id: Optional[str] = None) -> Dict[str, Any]:
    from entity_scope import allowed_entities_for
    from services import approval_policy_service as aps
    ent = order.get("entity_id") or ""
    levels = await aps.required_levels(KIND, ent, amount) or [{"level": 1}]
    for lv in levels:   # satu keputusan = final: aktor wajib lolos SETIAP jenjang yang berlaku untuk nominal itu
        res = await aps.can_decide(KIND, ent, amount, actor, int(lv.get("level") or 1))
        if not res["allowed"]:
            return {"allowed": False, "message": res["message"]}
    if ent and ent not in await allowed_entities_for(actor):
        return {"allowed": False, "message": f"Pesanan {order.get('number') or ''} milik PT yang tidak Anda tangani."}
    if is_order_sales(order, actor):
        return {"allowed": False, "message": (f"Anda sales pesanan {order.get('number') or ''} — permintaan pada pesanan "
                                              "Anda sendiri diputus penyetuju lain.")}
    if requester_id and str(actor.get("id") or "") == str(requester_id):
        return {"allowed": False, "message": "Anda yang mengajukan permintaan ini — keputusannya diambil penyetuju lain."}
    return {"allowed": True, "message": ""}


async def can_decide(order: Dict[str, Any], req: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """`{"allowed", "message"}` — izin `order.approve_cancel` + rentang nominal Aturan Persetujuan + akses PT + bukan
    sales pesanan + bukan pengaju."""
    return await _decide_check(order, float((req or {}).get("amount") or 0), actor,
                               requester_id=str((req or {}).get("requested_by_id") or "") or None)


async def check(order: Dict[str, Any], action: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Untuk dialog: `{"needs_approval", "basis", "can_self_approve", "amount"}` (+ `preview` bila penilai aksi
    menyediakannya). `can_self_approve` hanya bermakna saat `needs_approval`."""
    a = _check_action(action)
    assessed = await ASSESSORS[a](order)
    v = await needs_approval(order, a, amount=assessed["amount"], excess=float(assessed.get("excess") or 0))
    can_self = bool(v["needs"]) and (await _decide_check(order, v["amount"], actor))["allowed"]
    out = {"needs_approval": v["needs"], "basis": v["basis"], "can_self_approve": can_self, "amount": v["amount"]}
    if "preview" in assessed:
        out["preview"] = assessed["preview"]
    return out


# ── Tulisan bersyarat ────────────────────────────────────────────────────────────────────────────────────────────────
def _stale_cutoff() -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=DECIDING_STALE_MINUTES)).isoformat()


def _free_marker() -> Dict[str, Any]:
    return {"$or": [{"cancel_request.deciding": {"$exists": False}},
                    {"cancel_request.deciding.at": {"$lt": _stale_cutoff()}}]}


async def _claim_new(order: Dict[str, Any], req: Dict[str, Any]) -> None:
    """Pasang permintaan baru: klaim atomik (prasyarat status sama seperti dibaca + belum ada permintaan menunggu),
    lalu tulisan akhir yang mencabut kuncinya. Kalah → 409 berpesan."""
    from services import atomic_claim as _saga
    try:
        await _saga.claim("sales_orders", order["id"], "cancel_request_submit",
                          precondition={"status": order["status"], "cancel_request.status": {"$ne": "pending"}},
                          actor=req.get("requested_by") or "")
    except HTTPException:
        cur = await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0, "number": 1, "cancel_request": 1}) or {}
        if (cur.get("cancel_request") or {}).get("status") == "pending":
            raise HTTPException(status_code=409, detail=_pending_message(cur, cur["cancel_request"]))
        raise
    await db.sales_orders.update_one({"id": order["id"]}, _saga.finish_set({"cancel_request": req}))


async def _mark_deciding(order_id: str, req_id: str, actor: Dict[str, Any]) -> str:
    token = new_id("lk")
    res = await db.sales_orders.update_one(
        {"id": order_id, "cancel_request.status": "pending", "cancel_request.id": req_id, **_free_marker()},
        {"$set": {"cancel_request.deciding": {"by": _actor_name(actor), "by_id": actor.get("id") or "",
                                              "at": now_iso(), "token": token}}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail=("Permintaan ini sudah diputus, ditarik, atau sedang diproses "
                                                     "penyetuju lain. Muat ulang untuk melihat keadaannya."))
    return token


async def _release_marker(order_id: str, req_id: str, token: str, *, drop: bool) -> None:
    """Lepas penanda milik pemanggil; `drop` = buang permintaannya sekalian (disetujui sendiri yang gagal)."""
    q = {"id": order_id, "cancel_request.id": req_id, "cancel_request.deciding.token": token}
    unset = {"cancel_request": ""} if drop else {"cancel_request.deciding": ""}
    await db.sales_orders.update_one(q, {"$unset": unset})


def _final(req: Dict[str, Any], status: str, actor_name: str, actor_id: str, note: str, **extra: Any) -> Dict[str, Any]:
    return {**_public(req), "status": status, "decided_by": actor_name, "decided_by_id": actor_id,
            "decided_at": now_iso(), "decision_note": note, **extra}


async def _close(order_id: str, req: Dict[str, Any], final: Dict[str, Any], *, token: str = "",
                 respect_marker: bool = True) -> bool:
    """Pindahkan permintaan aktif ke riwayat (bersyarat menunggu + id sama [+ penanda milik pemanggil / bebas])."""
    q: Dict[str, Any] = {"id": order_id, "cancel_request.status": "pending", "cancel_request.id": req["id"]}
    if token:
        q["cancel_request.deciding.token"] = token
    elif respect_marker:
        q.update(_free_marker())
    res = await db.sales_orders.update_one(q, {"$push": {"cancel_requests": final}, "$unset": {"cancel_request": ""}})
    return bool(res.matched_count)


def _summary(result: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("status", "advance_to_deposit", "advance_to_deposit_error", "open_fulfillment_refs",
            "sample_payment_status")
    return {k: result.get(k) for k in keys if k in (result or {})}


def _keep_pending(exc: HTTPException, still_pending: bool) -> HTTPException:
    tail = " Permintaan tetap menunggu keputusan." if still_pending else ""
    d = exc.detail
    if isinstance(d, dict):
        d = {**d, "message": f"{d.get('message') or ''}{tail}".strip()}
    else:
        d = f"{d or 'Eksekusi gagal.'}{tail}"
    return HTTPException(status_code=exc.status_code, detail=d)   # kode asli (403/404/400…); 409 tetap 409


class _SudahTereksekusi(Exception):
    """Eksekutor gagal SESUDAH pesanan terlanjur berubah: putusan sudah dicatat `approved`; pemanggil menuntaskan
    notifikasi/audit lalu melempar ulang galat aslinya."""

    def __init__(self, final: Dict[str, Any], original: Exception) -> None:
        super().__init__(str(original))
        self.final, self.original = final, original


async def _execute_and_finalize(order_id: str, req: Dict[str, Any], actor: Dict[str, Any], token: str, note: str,
                                *, self_approved: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Jalankan eksekutor aksi lalu catat putusan `approved`. Gagal → penanda dilepas, permintaan tetap menunggu
    (persetujuan) atau dibuang (disetujui sendiri: tidak pernah menunggu siapa pun), 409 berpesan."""
    name, uid = _actor_name(actor), str(actor.get("id") or "")
    try:
        result = await EXECUTORS[req["action"]](order_id, actor, req["reason"], request_id=req["id"])
    except Exception as exc:
        cur = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "status": 1, "cancel_request_id": 1}) or {}
        if (req["action"] == "cancel" and cur.get("status") == "cancelled"
                and cur.get("cancel_request_id") == req["id"]):
            # Pesanan TERLANJUR batal oleh eksekusi permintaan ini (penanda `cancel_request_id`, bukan waktu): putusan
            # tetap dicatat (riwayat jujur); notifikasi/audit dituntaskan pemanggil.
            final = _final(req, "approved", name, uid, note, self_approved=self_approved,
                           result={"status": "cancelled", "error": str(exc)[:300]})
            await _close(order_id, req, final, token=token)
            logger.error("Eksekusi permintaan %s pesanan %s gagal SESUDAH pesanan batal: %s", req["id"], order_id, exc)
            raise _SudahTereksekusi(final, exc) from exc
        await _release_marker(order_id, req["id"], token, drop=self_approved)
        if self_approved:
            raise
        if cur.get("status") in ("cancelled", "expired"):
            # Pesanan mati lewat jalur lain selama permintaan menunggu → permintaan ditutup, tidak ada yang dieksekusi.
            word = "dibatalkan" if cur.get("status") == "cancelled" else "kedaluwarsa"
            await void_pending(order_id, f"Pesanan sudah {word} lewat jalur lain.", name)
            raise HTTPException(status_code=409, detail=(f"Pesanan ini sudah {word} lewat jalur lain — permintaan "
                                                         "ditutup tanpa dieksekusi.")) from exc
        still = (await pending_of(order_id) or {}).get("id") == req["id"]
        if isinstance(exc, HTTPException):
            raise _keep_pending(exc, still) from exc
        logger.error("Eksekusi permintaan %s pesanan %s gagal: %s", req["id"], order_id, exc)
        raise _keep_pending(HTTPException(status_code=409, detail=FAIL_MESSAGE.get(req["action"], FAIL_MESSAGE["cancel"])),
                            still) from exc
    final = _final(req, "approved", name, uid, note, self_approved=self_approved, result=_summary(result))
    if not await _close(order_id, req, final, token=token):
        logger.error("Putusan permintaan %s pesanan %s tidak tercatat (penanda hilang)", req["id"], order_id)
    # Potret pesanan hasil eksekusi diambil SEBELUM putusan dicatat: samakan dengan yang tersimpan.
    result = {k: v for k, v in result.items() if k != "cancel_request"}
    if "cancel_requests" in result or "status" in result:
        result["cancel_requests"] = [*(result.get("cancel_requests") or []), final]
    return result, final


# ── Notifikasi (§5.8) ───────────────────────────────────────────────────────────────────────────────────────────────
async def _notify_pending(order: Dict[str, Any], req: Dict[str, Any]) -> None:
    from services import notification_service as ns
    label = ACTION_LABEL.get(req["action"], "pembatalan")
    alasan = []
    for b in req.get("approval_basis") or []:
        alasan.append(f"{BASIS_LABEL['paid']} {rupiah(order.get('paid_total') or 0)}" if b == "paid"
                      else BASIS_LABEL.get(b, b))
    wajib = f" Perlu persetujuan karena {', '.join(alasan)}." if alasan else ""
    try:
        notes = await ns.create_addressed(
            permission=("order", "approve_cancel"), entity_id=order.get("entity_id") or None,
            notif_type=NOTIF_REQUEST, ref=f"{NOTIF_REQUEST}:{req['id']}",
            title=f"Permintaan {label} {order.get('number') or ''} menunggu persetujuan",
            body=(f"{order.get('customer_name') or '-'} — {rupiah(req.get('amount') or 0)}. Diajukan "
                  f"{req.get('requested_by') or '-'}: {req.get('reason') or '-'}.{wajib}")[:400],
            severity="warning", link=LINK, action_type=ACTION_TYPE, action_id=req["id"])
        # Pengaju & sales pesanan yang memegang `order.approve_cancel` (peran kustom) tidak boleh memutus (403): tombol
        # setujui di lonceng mereka pasti gagal — notifikasinya langsung ditutup.
        mati = [n["id"] for n in notes or [] if n.get("id") and n.get("recipient_user")
                and (str(n["recipient_user"]) == str(req.get("requested_by_id") or "")
                     or is_order_sales(order, {"id": n["recipient_user"]}))]
        if mati:
            await db.notifications.update_many(
                {"id": {"$in": mati}},
                {"$set": {"read": True, "read_at": now_iso(), "resolved_at": now_iso(),
                          "resolution": "bukan penyetuju permintaan ini", "resolved_by": "system"}})
    except Exception as exc:  # noqa: BLE001 — permintaan sudah tercatat & terhitung antrean; notifikasi pelengkap
        logger.warning("Notifikasi permintaan batal %s gagal: %s", req["id"], exc)


async def _notify_decided(order: Dict[str, Any], final: Dict[str, Any]) -> None:
    from services import notification_service as ns
    label = ACTION_LABEL.get(final["action"], "pembatalan")
    setuju = final["status"] == "approved"
    users = [final.get("requested_by_id"), order.get("sales_id"),
             *[m.get("sales_id") for m in order.get("sales_team") or [] if isinstance(m, dict)]]
    users = [str(u) for u in dict.fromkeys(users) if u and str(u) != str(final.get("decided_by_id") or "")]
    if not users:
        return
    hasil = DONE_LABEL.get(final["action"], "pesanan dibatalkan") if setuju else "pesanan berjalan seperti biasa"
    catatan = f" Catatan: {final.get('decision_note')}" if final.get("decision_note") else ""
    try:
        await ns.create_addressed(
            also_users=tuple(users), entity_id=order.get("entity_id") or None,
            notif_type=NOTIF_DECIDED, ref=f"{NOTIF_DECIDED}:{final['id']}",
            title=(f"Permintaan {label} {order.get('number') or ''} "
                   f"{'disetujui' if setuju else 'ditolak'} oleh {final.get('decided_by') or '-'}"),
            body=f"{order.get('customer_name') or '-'} — {hasil}.{catatan}"[:400],
            severity="info" if setuju else "warning", link=LINK)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notifikasi putusan permintaan batal %s gagal: %s", final["id"], exc)


async def _resolve(req_id: str, outcome: str, actor_name: str) -> None:
    from services import notification_service as ns
    await ns.resolve_action(ACTION_TYPE, req_id, outcome=outcome, actor=actor_name)


# ── Pintu ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def submit(order_id: str, action: str, actor: Dict[str, Any], reason: str) -> Tuple[int, Dict[str, Any]]:
    """Jalur masuk batal/tutup sisa (izin, kepemilikan, dan alasan sudah diperiksa pemanggil).

    200 + hasil eksekusi (tanpa persetujuan, atau disetujui sendiri — tercatat `self_approved` di `cancel_requests[]`),
    atau 202 + `{"request", "order_status", "message"}`."""
    from dependencies import audit
    a = _check_action(action)
    order = await _load(order_id)
    cur = order.get("cancel_request") or {}
    if cur.get("status") == "pending":
        raise HTTPException(status_code=409, detail=_pending_message(order, cur))
    assessed = await ASSESSORS[a](order)
    verdict = await needs_approval(order, a, amount=assessed["amount"], excess=float(assessed.get("excess") or 0))
    name, uid = _actor_name(actor), str(actor.get("id") or "")
    if not verdict["needs"]:
        result = await EXECUTORS[a](order_id, actor, reason)
        await void_pending(order_id, f"{DONE_LABEL.get(a, 'pesanan dibatalkan').capitalize()} langsung oleh {name}.",
                           name)
        return 200, result
    req = {"id": new_id("scr"), "action": a, "status": "pending", "reason": reason,
           "requested_by": name, "requested_by_id": uid, "requested_at": now_iso(),
           "needs_approval": True, "approval_basis": list(verdict["basis"]), "amount": verdict["amount"],
           "decided_by": "", "decided_by_id": "", "decided_at": "", "decision_note": "", "self_approved": False,
           "result": {}}
    if (await _decide_check(order, verdict["amount"], actor))["allowed"]:
        token = new_id("lk")
        await _claim_new(order, {**req, "deciding": {"by": name, "by_id": uid, "at": now_iso(), "token": token}})
        audit_data = {"request_id": req["id"], "action": a, "self_approved": True, "amount": req["amount"],
                      "approval_basis": req["approval_basis"]}
        try:
            result, final = await _execute_and_finalize(order_id, req, actor, token, "", self_approved=True)
        except _SudahTereksekusi as done:   # pesanan terlanjur berubah: putusan tercatat, audit tetap ditulis
            await audit(name, "so_cancel_request_approved", "sales_order", order_id,
                        {**audit_data, "execution_error": True}, reason)
            raise done.original from done
        await audit(name, "so_cancel_request_approved", "sales_order", order_id, audit_data, reason)
        return 200, result
    await _claim_new(order, req)
    await audit(name, "so_cancel_request_submitted", "sales_order", order_id,
                {"request_id": req["id"], "action": a, "amount": req["amount"],
                 "approval_basis": req["approval_basis"]}, reason)
    await _notify_pending(order, req)
    return 202, {"request": _public(req), "order_status": order["status"], "message": MESSAGE_PENDING}


async def decide(order_id: str, actor: Dict[str, Any], decision: str, note: str) -> Dict[str, Any]:
    """Setujui (`approve`) atau tolak (`reject`, alasan wajib) permintaan yang menunggu. Setujui menjalankan eksekutor
    aksi (status & Faktur Pajak diperiksa lagi); eksekusi gagal → permintaan tetap menunggu, 409 berpesan."""
    from dependencies import audit
    from input_rules import MAX_REASON_LEN, reason_problem
    d = str(decision or "").strip().lower()
    if d not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="Keputusan harus 'approve' (setujui) atau 'reject' (tolak).")
    note = str(note or "").strip()
    if d == "reject":
        msg = reason_problem(note, label="Alasan penolakan")
        if msg:
            raise HTTPException(status_code=422, detail=msg)
    elif len(note) > MAX_REASON_LEN:
        raise HTTPException(status_code=422, detail=f"Catatan terlalu panjang (maksimal {MAX_REASON_LEN} karakter).")
    order = await _load(order_id)
    req = order.get("cancel_request") or {}
    if req.get("status") != "pending":
        raise HTTPException(status_code=409, detail=("Tidak ada permintaan pembatalan/tutup sisa yang menunggu keputusan "
                                                     "untuk pesanan ini — mungkin sudah diputus atau ditarik."))
    chk = await can_decide(order, req, actor)
    if not chk["allowed"]:
        raise HTTPException(status_code=403, detail=chk["message"])
    name, uid = _actor_name(actor), str(actor.get("id") or "")
    if d == "reject":
        final = _final(req, "rejected", name, uid, note, self_approved=False)
        if not await _close(order_id, req, final):
            raise HTTPException(status_code=409, detail=("Permintaan ini sudah diputus, ditarik, atau sedang diproses "
                                                         "penyetuju lain. Muat ulang untuk melihat keadaannya."))
        await _resolve(req["id"], "ditolak", name)
        await audit(name, "so_cancel_request_rejected", "sales_order", order_id,
                    {"request_id": req["id"], "action": req.get("action")}, note)
        await _notify_decided(order, final)
        return {"request": final, "order_status": order["status"],
                "message": "Permintaan ditolak — pesanan berjalan seperti biasa."}
    token = await _mark_deciding(order_id, req["id"], actor)
    audit_data = {"request_id": req["id"], "action": req.get("action"), "self_approved": False,
                  "amount": req.get("amount"), "requested_by": req.get("requested_by")}
    try:
        result, final = await _execute_and_finalize(order_id, req, actor, token, note, self_approved=False)
    except _SudahTereksekusi as done:
        # Pesanan terlanjur berubah lalu eksekutor gagal: putusan sudah tercatat `approved` — tutup notifikasi
        # "menunggu persetujuan", audit, dan beri tahu pengaju sebelum galat aslinya dilempar ulang.
        await _resolve(req["id"], "disetujui (eksekusi bergalat)", name)
        await audit(name, "so_cancel_request_approved", "sales_order", order_id,
                    {**audit_data, "execution_error": True}, note)
        await _notify_decided(order, done.final)
        raise done.original from done
    await _resolve(req["id"], "disetujui", name)
    await audit(name, "so_cancel_request_approved", "sales_order", order_id, audit_data, note)
    await _notify_decided(order, final)
    return {"request": final, "order_status": result.get("status") or "", "result": result,
            "message": f"Permintaan disetujui — {DONE_LABEL.get(req.get('action'), 'pesanan dibatalkan')}."}


async def withdraw(order_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Tarik permintaan yang menunggu (pengaju atau pemegang `order.cancel` atas pesanan itu — dijaga endpoint)."""
    from dependencies import audit
    order = await _load(order_id)
    req = order.get("cancel_request") or {}
    if req.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Tidak ada permintaan yang menunggu keputusan untuk ditarik.")
    name = _actor_name(actor)
    final = _final(req, "withdrawn", name, str(actor.get("id") or ""), "")
    if not await _close(order_id, req, final):
        raise HTTPException(status_code=409, detail=("Permintaan ini sudah diputus atau sedang diproses penyetuju. "
                                                     "Muat ulang untuk melihat keadaannya."))
    await _resolve(req["id"], "ditarik pengaju", name)
    await audit(name, "so_cancel_request_withdrawn", "sales_order", order_id,
                {"request_id": req["id"], "action": req.get("action")})
    return {"request": final, "order_status": order["status"],
            "message": "Permintaan ditarik — pesanan berjalan seperti biasa."}


async def void_pending(order_id: str, reason: str, actor_name: str = "system") -> bool:
    """Pesanan mati lewat jalur lain (kedaluwarsa, batal langsung) → permintaan menunggu ditutup `void` beralasan.
    Aman diulang (False bila tidak ada yang menunggu)."""
    o = await db.sales_orders.find_one({"id": order_id, "cancel_request.status": "pending"},
                                       {"_id": 0, "cancel_request": 1})
    if not o:
        return False
    req = o["cancel_request"]
    if not await _close(order_id, req, _final(req, "void", actor_name, "", reason), respect_marker=False):
        return False
    await _resolve(req["id"], f"ditutup: {reason}"[:120], actor_name)
    from dependencies import audit
    await audit(actor_name, "so_cancel_request_void", "sales_order", order_id,
                {"request_id": req["id"], "action": req.get("action")}, reason)
    return True


async def list_requests(scope_q: Dict[str, Any], status: str = "pending") -> List[Dict[str, Any]]:
    """Antrean penyetuju (Ruling R1): satu baris per permintaan pada pesanan dalam cakupan `scope_q`."""
    st = str(status or "pending").strip().lower()
    if st not in STATUSES:
        raise HTTPException(status_code=400, detail=f"Status permintaan '{st}' tidak dikenal.")
    field = "cancel_request.status" if st == "pending" else "cancel_requests.status"
    rows = await db.sales_orders.find(
        {"$and": [scope_q or {}, {field: st}]},
        {"_id": 0, "id": 1, "number": 1, "customer_name": 1, "entity_id": 1, "cancel_request": 1,
         "cancel_requests": 1}).to_list(500)
    out: List[Dict[str, Any]] = []
    for o in rows:
        reqs = [o.get("cancel_request") or {}] if st == "pending" else \
            [r for r in o.get("cancel_requests") or [] if r.get("status") == st]
        for r in reqs:
            out.append({"request_id": r.get("id"), "order_id": o.get("id"), "number": o.get("number") or "",
                        "customer_name": o.get("customer_name") or "", "entity_id": o.get("entity_id") or "",
                        "action": r.get("action") or "cancel", "amount": float(r.get("amount") or 0),
                        "reason": r.get("reason") or "", "requested_by": r.get("requested_by") or "",
                        "requested_at": r.get("requested_at") or "",
                        "approval_basis": list(r.get("approval_basis") or [])})
    out.sort(key=lambda x: x["requested_at"])
    return out
