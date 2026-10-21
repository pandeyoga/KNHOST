"""U-2 (2026-09) — Meja kerja untuk 6 peran tersisa: admin, manager, sales, warehouse, designer, driver.

Pola sama dengan Meja Admin Sales/Finance/MD/Gudang (`_queue`/`_row`), ditambah antrean
"Giliran saya" dari notifikasi giliran (turn) yang belum dibaca — sehingga setiap peran
membuka satu layar tiap pagi dan melihat apa yang menunggu keputusannya.
"""
from typing import Any, Dict, List

from db import db
from services.work_desk_service import _queue, _row, _age_days

ROLES = ("admin", "manager", "sales", "warehouse", "designer", "driver")
LABEL = {"admin": "Meja Admin", "manager": "Meja Manajer", "sales": "Meja Sales", "warehouse": "Meja Operator Gudang",
         "designer": "Meja Desainer", "driver": "Meja Pengemudi"}


def _scope_q(scope: Dict[str, Any], ids: List[str]) -> Dict[str, Any]:
    """`scope` = filter entitas hasil resolve_list_scope (sudah berupa query Mongo)."""
    return dict(scope or {})


async def _turn_queue(actor: Dict[str, Any]) -> Dict[str, Any]:
    notes = await db.notifications.find(
        {"recipient_user": actor["id"], "type": "turn", "read": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    rows, seen = [], set()
    for n in notes:
        key = n.get("action_id") or n.get("id")
        if key in seen:   # L10 LN-102-T02 — satu dokumen = satu baris walau notifikasinya berulang
            continue
        seen.add(key)
        coll, doc_id = (str(n.get("action_id") or ":").split(":", 1) + [""])[:2]
        rows.append(_row(ref_type=coll.rstrip("s") if coll.endswith("s") else coll, ref_id=doc_id,
                         number=str(n.get("title", "")).split(":")[-1].strip(), title=n.get("title", ""),
                         subtitle=n.get("body", ""), age_days=_age_days(n.get("created_at")),
                         badge=n.get("severity", "info"), action="Buka", action_kind="open",
                         extra={"link": n.get("link", ""), "notification_id": n.get("id")}))
    return _queue("giliran_saya", "Giliran saya", "Dokumen yang berpindah tahap dan kini menunggu tindakan Anda.",
                  rows, action_label="Buka", owner="me", value_kind="count", value_label="Item")


def _so_rows(docs: List[Dict[str, Any]], action: str) -> List[Dict[str, Any]]:
    return [_row(ref_type="sales_order", ref_id=o["id"], number=o.get("number", ""), title=o.get("customer_name", "—"),
                 subtitle=f"{o.get('status')} · {o.get('sales_name') or o.get('created_by') or '—'}",
                 value=o.get("grand_total") or o.get("total_amount") or 0, age_days=_age_days(o.get("updated_at") or o.get("created_at")),
                 badge=o.get("status", ""), action=action) for o in docs]


async def _find(coll: str, q: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
    return await db[coll].find(q, {"_id": 0}).sort("updated_at", -1).limit(limit).to_list(limit)


async def manager_queues(scope, ids) -> List[Dict[str, Any]]:
    sq = _scope_q(scope, ids)
    so = await _find("sales_orders", {**sq, "status": "waiting_approval"})
    po = await _find("purchase_orders", {**sq, "status": "waiting_approval"})
    sr = await _find("sales_returns", {**sq, "status": "pending_approval"})
    pr = await _find("purchase_returns", {**sq, "status": "pending_approval"})
    pa = await _find("price_approvals", {**sq, "status": "pending"})
    return [
        _queue("so_acc", "Pesanan penjualan menunggu ACC", "Setujui atau tolak — sales & pelanggan menunggu.", _so_rows(so, "Putuskan"), action_label="Putuskan", owner="manager"),
        _queue("po_acc", "Pesanan pembelian menunggu ACC", "PO di atas ambang persetujuan.",
               [_row(ref_type="purchase_order", ref_id=o["id"], number=o.get("po_number") or o.get("number", ""), title=o.get("supplier_name", "—"),
                     value=o.get("grand_total") or o.get("total_amount") or 0, age_days=_age_days(o.get("created_at")), badge=o.get("status", ""), action="Putuskan") for o in po],
               action_label="Putuskan", owner="manager"),
        _queue("retur_acc", "Retur menunggu ACC", "Retur penjualan & pembelian yang perlu keputusan.",
               [_row(ref_type="sales_return", ref_id=o["id"], number=o.get("number", ""), title=o.get("customer_name", "—"), value=o.get("total_amount") or 0,
                     age_days=_age_days(o.get("created_at")), badge="retur penjualan", action="Putuskan") for o in sr]
               + [_row(ref_type="purchase_return", ref_id=o["id"], number=o.get("number", ""), title=o.get("supplier_name", "—"), value=o.get("total_amount") or 0,
                       age_days=_age_days(o.get("created_at")), badge="retur pembelian", action="Putuskan") for o in pr],
               action_label="Putuskan", owner="manager"),
        _queue("harga_khusus", "Permintaan harga khusus", "Harga di bawah pricelist yang diajukan sales.",
               [_row(ref_type="price_approval", ref_id=o["id"], number=o.get("number") or o["id"], title=o.get("customer_name", "—"),
                     value=o.get("requested_price") or 0, age_days=_age_days(o.get("created_at")), badge=o.get("status", ""), action="Putuskan") for o in pa],
               action_label="Putuskan", owner="manager"),
    ]


async def sales_queues(actor, scope, ids) -> List[Dict[str, Any]]:
    sq = _scope_q(scope, ids)
    mine = {"$or": [{"sales_id": actor["id"]}, {"created_by": actor["id"]}, {"created_by": actor.get("email")}, {"created_by": actor.get("name")}]}
    waiting = await _find("sales_orders", {**sq, **mine, "order_type": {"$ne": "sample"}, "status": {"$in": ["waiting_approval", "waiting_stock"]}})
    approved = await _find("sales_orders", {**sq, **mine, "order_type": {"$ne": "sample"}, "status": "approved"})
    rejected = await _find("sales_orders", {**sq, **mine, "order_type": {"$ne": "sample"}, "status": {"$in": ["rejected", "cancelled"]}, "updated_at": {"$gte": _days_ago(7)}})
    samples = await _find("sales_orders", {**sq, **mine, "order_type": "sample", "status": {"$nin": ["done", "cancelled", "expired", "rejected"]}})
    return [
        _queue("so_menunggu", "Pesanan saya menunggu", "Menunggu ACC manajer atau stok — pantau, jangan janji tanggal kirim dulu.", _so_rows(waiting, "Lihat"), action_label="Lihat", owner="sales"),
        _queue("so_konfirmasi", "Disetujui — konfirmasi ke pelanggan", "Kabari pelanggan; admin sales akan memproses.", _so_rows(approved, "Lihat"), action_label="Lihat", owner="sales"),
        _queue("so_ditolak", "Ditolak / dibatalkan (7 hari)", "Hubungi pelanggan & ajukan ulang bila perlu.", _so_rows(rejected, "Lihat"), action_label="Lihat", owner="sales"),
        _queue("sampel_saya", "Pesanan sample saya", "Pesanan berisi baris sample yang sedang dipotong / disiapkan gudang.",
               _so_rows(samples, "Lihat"), action_label="Lihat", owner="sales", value_kind="count", value_label="Item"),
    ]


def _task_qty(t: Dict[str, Any]) -> str:
    """Temuan 2026-10-19D — tugas terima menyimpan qty di expected_qty; jangan tampilkan '0.0 yard'."""
    q = float(t.get("quantity") or t.get("expected_qty") or t.get("total_qty") or 0)
    return f"{q:g} {t.get('unit', '')}".strip() if q > 0 else ""


async def warehouse_queues(scope, ids) -> List[Dict[str, Any]]:
    sq = _scope_q(scope, ids)
    # KN-D07 — status yang NYATA ditulis mesin tugas gudang (created/scheduled/picking/packing/
    # staging/escalated/qc_check/put_away/receiving/partially_shipped); 'pending' tidak pernah ada.
    tasks = await _find("wms_tasks", {**sq, "status": {"$in": ["created", "scheduled", "picking", "packing", "staging",
                                                              "escalated", "qc_check", "put_away", "receiving",
                                                              "partially_shipped"]},
                                      "task_subtype": {"$ne": "sample_cut"}})
    po = await _find("purchase_orders", {**sq, "status": {"$in": ["pending", "receiving"]}})
    samples = await _find("wms_tasks", {**sq, "task_subtype": "sample_cut", "status": {"$in": ["created", "picking"]}, "picked_qty": {"$in": [0, 0.0, None]}})
    # F-10 — SO bertermin CBD/DP yang belum dibayar: baris diberi lencana "tertahan bayar" + kekurangannya.
    from services import dispatch_payment_gate as _gate
    holds = await _gate.holds_for_orders(t.get("order_id") for t in tasks if t.get("flow_type") == "outbound")
    return [
        _queue("tugas_wms", "Tugas gudang (terima, picking & kirim)", "Kerjakan urut umur tugas.",
               [_row(ref_type="wms_task", ref_id=t["id"], number=t.get("number") or t.get("order_number") or t.get("po_number") or t.get("ref_number") or t["id"],
                     title=t.get("customer_name") or t.get("product_name") or t.get("type", "tugas"),
                     subtitle=" · ".join(x for x in (t.get("flow_type") or t.get("type", ""), _task_qty(t),
                                                     _gate.desk_note(holds.get(t.get("order_id")))) if x),
                     age_days=_age_days(t.get("created_at")),
                     badge="tertahan bayar" if _gate.desk_note(holds.get(t.get("order_id"))) else t.get("status", ""),
                     action="Kerjakan",
                     extra={"flow_type": t.get("flow_type") or "", "po_id": t.get("po_id") or "",
                            "payment_blocked": bool(_gate.desk_note(holds.get(t.get("order_id"))))}) for t in tasks],
               action_label="Kerjakan", owner="warehouse", value_kind="count", value_label="Tugas"),
        _queue("po_terima", "PO menunggu penerimaan", "Barang pemasok yang akan/sedang diterima.",
               [_row(ref_type="purchase_order", ref_id=o["id"], number=o.get("po_number") or o.get("number", ""), title=o.get("supplier_name", "—"),
                     value=o.get("grand_total") or 0, age_days=_age_days(o.get("updated_at")), badge=o.get("status", ""), action="Terima") for o in po],
               action_label="Terima", owner="warehouse"),
        _queue("sampel_potong", "Sample untuk dipotong", "Permintaan potong sample dari pesanan sales — pindai roll, potong, catat panjang.",
               [_row(ref_type="wms_task", ref_id=t["id"], number=t.get("order_number", ""), title=t.get("customer_name", "—"), subtitle=t.get("product_name", ""),
                     age_days=_age_days(t.get("created_at")), badge=t.get("status", ""), action="Potong") for t in samples],
               action_label="Potong", owner="warehouse", value_kind="count", value_label="Item"),
        await return_receipt_qc_queue(scope),
    ]


def _return_step(r: Dict[str, Any]) -> tuple:
    """(keterangan langkah, label tombol) untuk satu retur di antrean terima/QC — tanpa nilai uang."""
    from services.return_journey_service import receipt_progress
    if r.get("status") == "inspecting":
        return "Sedang diperiksa QC", "Buka"
    p = receipt_progress(r)
    if p["ready_for_qc"]:
        return "Barang sudah di gudang — menunggu QC", "Buka"
    if p["in_transit"]:
        return f"{p['in_transit']} roll dalam perjalanan ke gudang tujuan — scan tiba", "Scan tiba"
    if p["rolls"] and p["at_warehouse"] < p["rolls"]:
        return f"Menunggu scan terima · {p['at_warehouse']}/{p['rolls']} roll diterima", "Terima"
    return "Menunggu barang sampai (baris tanpa roll)", "Terima"


async def return_receipt_qc_queue(scope, owner: str = "warehouse") -> Dict[str, Any]:
    """Keputusan owner 2026-10-21 — antrean "Retur menunggu terima / QC" di meja Gudang: retur pelanggan
    yang sudah disetujui (`approved`) atau sedang QC (`inspecting`) — himpunan yang SAMA dengan daftar
    retur Gudang/QC (F-11-layar). Tanpa nilai uang; terlama di atas."""
    from services.return_operator_view import LIST_STATES
    docs = await _find("sales_returns", {**_scope_q(scope, []), "status": {"$in": list(LIST_STATES)}})
    rows = []
    for r in docs:
        step, act = _return_step(r)
        rows.append(_row(ref_type="sales_return", ref_id=r["id"], number=r.get("number") or r.get("return_number") or r["id"],
                         title=r.get("customer_name") or "—", subtitle=step, value=0,
                         age_days=_age_days(r.get("approved_at") or r.get("updated_at") or r.get("created_at")),
                         badge=r.get("status", ""), action=act))
    rows.sort(key=lambda x: -x["age_days"])
    return _queue("retur_terima_qc", "Retur menunggu terima / QC",
                  "Retur pelanggan yang sudah disetujui: scan terima barang (atau tiba di gudang tujuan), lalu QC memeriksa.",
                  rows, action_label="Buka", owner=owner, value_kind="count", value_label="Retur")


async def designer_queues(actor, scope, ids) -> List[Dict[str, Any]]:
    sq = _scope_q(scope, ids)
    # KN-D06 — `approved` = SELESAI & di-ACC (bukan pekerjaan). Backlog nyata desainer:
    # assigned / in_progress / revision; yang belum ditugaskan = submitted tanpa assignee.
    mine = await _find("design_requests", {**sq, "assigned_to": actor["id"], "status": {"$in": ["assigned", "in_progress", "revision"]}})
    unassigned = await _find("design_requests", {**sq, "status": {"$in": ["submitted", "assigned"]}, "$or": [{"assigned_to": ""}, {"assigned_to": None}]})
    rows = lambda docs, act: [_row(ref_type="design_request", ref_id=d["id"], number=d.get("number", ""), title=d.get("customer_name") or d.get("brief", "")[:60],  # noqa: E731
                                   subtitle=d.get("target_type", ""), age_days=_age_days(d.get("requested_at") or d.get("created_at")), badge=d.get("status", ""), action=act) for d in docs]
    return [
        _queue("desain_saya", "Desain yang saya kerjakan", "Selesaikan & serahkan ke MD.", rows(mine, "Kerjakan"), action_label="Kerjakan", owner="designer", value_kind="count", value_label="Item"),
        _queue("desain_bebas", "Belum ditugaskan", "Permintaan desain yang disetujui tapi belum ada desainernya.", rows(unassigned, "Ambil"), action_label="Ambil", owner="designer", value_kind="count", value_label="Item"),
    ]


async def driver_queues(actor, scope, ids) -> List[Dict[str, Any]]:
    sq = _scope_q(scope, ids)
    # KN-C08 — `shipments.status` hanya pernah bernilai 'dispatched'; penyerahan barang
    # ditulis ke `logistics_status='delivered'`. Tanpa filter itu setiap Surat Jalan yang
    # pernah terbit tampil sebagai "kiriman hari ini" selamanya.
    ships = await _find("shipments", {**sq, "status": {"$in": ["dispatched", "in_transit", "ready"]},
                                      "logistics_status": {"$nin": ["delivered", "cancelled", "failed"]}})
    mine = [s for s in ships if not s.get("driver_id") or s.get("driver_id") == actor["id"] or s.get("driver_name") == actor.get("name")]
    return [
        _queue("kiriman", "Kiriman hari ini", "Antar & tandai terkirim (foto bukti bila ada).",
               [_row(ref_type="shipment", ref_id=s["id"], number=s.get("number", ""), title=s.get("customer_name") or s.get("destination", "—"),
                     subtitle=s.get("address") or s.get("city", ""), age_days=_age_days(s.get("dispatched_at") or s.get("created_at")), badge=s.get("status", ""), action="Antar") for s in mine],
               action_label="Antar", owner="driver", value_kind="count", value_label="Kiriman"),
    ]


def _days_ago(n: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


async def role_desk(role: str, actor: Dict[str, Any], scope: Dict[str, Any], ids: List[str]) -> Dict[str, Any]:
    queues = [await _turn_queue(actor)]
    if role == "manager":
        queues += await manager_queues(scope, ids)
    elif role == "sales":
        queues += await sales_queues(actor, scope, ids)
    elif role == "warehouse":
        queues += await warehouse_queues(scope, ids)
    elif role == "designer":
        queues += await designer_queues(actor, scope, ids)
    elif role == "driver":
        queues += await driver_queues(actor, scope, ids)
    elif role == "admin":
        queues += await manager_queues(scope, ids)
        queues += await warehouse_queues(scope, ids)
    return {"role": role, "title": LABEL.get(role, "Meja Saya"), "queues": queues,
            "total_items": sum(len(q["rows"]) for q in queues), "generated_at": _days_ago(0)}
