"""FASE E-8 (E8.14 · US12) — **PERJALANAN PESANAN** (read-only, untuk sales lapangan).

KENAPA BERKAS INI ADA (temuan A2 `ANALISIS_DOMAIN_SALES.md`)
===========================================================
Pertanyaan yang paling sering diterima sales dari pelanggan hanya satu: *"pesanan
saya sekarang di mana?"* Untuk menjawabnya, sales harus membuka **lima layar milik
domain lain** — Operasi Gudang (403 untuk sales), Pengiriman, Faktur, Kwitansi, dan
Pembelian — atau menelepon orang gudang. Akibatnya menu "Operasi WMS" dipasang untuk
sales "biar bisa lihat", padahal `/api/wms/tasks` menolaknya dengan 403: menu mati
yang mengajari pengguna bahwa error itu normal.

Modul ini menjawab pertanyaan itu dengan **satu endpoint read-only** yang menyusun
tahapan dari dokumen yang sudah ada. Tidak ada koleksi baru, tidak ada status baru,
dan **tidak ada akses ke layar gudang** — sales membaca hasilnya, bukan mesinnya.

TAHAPAN (bahasa pelanggan, bukan nama kolom)
--------------------------------------------
``dipesan → diverifikasi → disetujui → dikonfirmasi → disiapkan → dikirim →
  diterima → ditagih → dibayar``

Tiap tahap membawa: sudah/belum, waktu, oleh siapa, dan satu kalimat penjelas.
Tahap yang belum tercapai TIDAK disembunyikan — justru itu yang ingin dilihat sales
("berhenti di mana?").

SUMBER PEMENUHAN IKUT DITAMPILKAN (US12)
----------------------------------------
Bila kekurangan barang dipenuhi lewat jalan lain, jawabannya harus terbaca di sini:
*"kekurangan 200 yard dipenuhi lewat `PO-00012`"* atau *"diambil dari PT Kain Suka
Cita lewat `KANDA/IC-00005`"*. Datanya dari `sales_orders.fulfillment_decision`
(ditulis Admin Sales di Meja Admin Sales) — jadi keputusan orang lain terlihat oleh
sales tanpa perlu izin tambahan.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import safe_doc

STATUS_BATAL = ("cancelled", "expired")


def _step(key: str, label: str, done: bool, at: str = "", by: str = "",
          detail: str = "", state: str = "") -> Dict[str, Any]:
    return {"key": key, "label": label, "done": bool(done), "at": at or "",
            "by": by or "", "detail": detail or "",
            "state": state or ("done" if done else "pending")}


def _fmt_qty(v: Any) -> str:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return "0"
    return f"{f:g}"


async def _outbound_tasks(order_id: str) -> List[Dict[str, Any]]:
    rows = await db.wms_tasks.find(
        {"order_id": order_id},
        {"_id": 0, "id": 1, "status": 1, "product_name": 1, "quantity": 1, "picked_qty": 1,
         "unit": 1, "warehouse_name": 1, "completed_at": 1, "created_at": 1, "updated_at": 1,
         "flow_type": 1, "task_subtype": 1}
    ).sort("created_at", 1).to_list(100)
    return [safe_doc(r) for r in rows if (r.get("flow_type") or "") != "inbound"]


async def _shipments(order_id: str) -> List[Dict[str, Any]]:
    rows = await db.shipments.find(
        {"order_id": order_id},
        {"_id": 0, "id": 1, "shipment_no": 1, "status": 1, "qty": 1, "unit": 1,
         "product_name": 1, "created_at": 1, "warehouse_name": 1, "is_partial": 1}
    ).sort("created_at", 1).to_list(100)
    return [safe_doc(r) for r in rows]


async def _logistics(order_id: str) -> List[Dict[str, Any]]:
    from services import logistics_service as lg
    return await lg.for_order(order_id)


async def _tax_invoices(order_id: str) -> List[Dict[str, Any]]:
    rows = await db.tax_invoices.find(
        {"order_id": order_id},
        {"_id": 0, "id": 1, "number": 1, "status": 1, "faktur_date": 1,
         "ppn_amount": 1, "grand_total": 1}
    ).sort("faktur_date", 1).to_list(50)
    return [safe_doc(r) for r in rows]


async def _receipts(order_id: str) -> List[Dict[str, Any]]:
    """Kwitansi AR yang mengalokasikan uang ke pesanan ini."""
    rows = await db.ar_receipts.find(
        {"allocations.order_id": order_id},
        {"_id": 0, "id": 1, "number": 1, "receipt_date": 1, "method": 1,
         "allocations": 1, "status": 1}
    ).sort("receipt_date", 1).to_list(100)
    out = []
    for r in rows:
        applied = sum(float(a.get("applied") or 0)
                      for a in (r.get("allocations") or [])
                      if a.get("order_id") == order_id)
        d = safe_doc(r)
        d.pop("allocations", None)
        d["applied"] = round(applied, 2)
        out.append(d)
    return out


async def _fulfillment_block(order: Dict[str, Any]) -> Dict[str, Any]:
    """Sumber pemenuhan kekurangan — kalimat yang bisa dibacakan ke pelanggan."""
    dec = order.get("fulfillment_decision") or {}
    label_mode = {"interco": "Diambil dari badan usaha grup lain",
                  "reorder": "Dipesan ulang ke supplier",
                  "wait": "Ditahan menunggu barang masuk"}
    kurang: List[Dict[str, Any]] = []
    try:
        from services import stock_bucket_service as sbs
        board = await sbs.pending_so_board({"entity_id": order.get("entity_id")})
        kurang = [b for b in board if b.get("order_id") == order.get("id")]
    except Exception:  # noqa: BLE001 — perjalanan pesanan tak boleh gagal karena papan stok
        kurang = []

    kalimat = ""
    if dec:
        kalimat = dec.get("summary") or label_mode.get(dec.get("mode", ""), "")
    elif kurang:
        total = sum(float(b.get("backorder_qty") or 0) for b in kurang)
        unit = (kurang[0].get("unit") or "").strip()
        kalimat = (f"Kekurangan {_fmt_qty(total)} {unit} belum diputuskan "
                   "— menunggu keputusan Admin Sales.").replace("  ", " ")
    return {
        "decision": dec or None,
        "mode_label": label_mode.get(dec.get("mode", ""), "") if dec else "",
        "ref_number": dec.get("ref_number", "") if dec else "",
        "ref_type": dec.get("ref_type", "") if dec else "",
        "sentence": kalimat,
        "shortages": [{"product_name": b.get("product_name", ""),
                       "backorder_qty": float(b.get("backorder_qty") or 0),
                       "unit": b.get("unit", ""),
                       "promise_date": b.get("promise_date", "") or "",
                       "coverage": b.get("coverage", "")} for b in kurang],
    }


async def _ledger_split(order: Dict[str, Any], sisa: float) -> Dict[str, float]:
    """L02 LN-023-T01 — sisa tagihan = piutang ledger (sudah diakui) + eksposur (belum dikirim)."""
    from services.ar_aging_service import recognized_by_order, split_outstanding
    rec = await recognized_by_order([order["id"]])
    return split_outstanding(order, max(sisa, 0.0), rec.get(order["id"], 0.0))


# F-07 — tugas outbound yang barangnya SUDAH disiapkan (ter-pick) — termasuk yang sudah dikirim. Dulu hanya
# completed/done/picked dihitung, sehingga SO yang sudah dikirim tampil "Disiapkan gudang 0/1".
TASK_PREPARED = ("picked", "packing", "staging", "dispatched", "partially_shipped", "completed", "done")
TASK_IGNORED = ("cancelled",)


async def _audit_stamp(order_id: str, actions: tuple) -> tuple:
    """Pesanan lama tanpa `approved_at`/`confirmed_at`: waktu & pelaku diambil dari jejak audit transisinya."""
    row = await db.audit_logs.find_one({"entity_id": order_id, "action": {"$in": list(actions)}},
                                       {"_id": 0, "timestamp": 1, "actor": 1}, sort=[("timestamp", 1)])
    return ((row or {}).get("timestamp", ""), (row or {}).get("actor", ""))


async def journey(order: Dict[str, Any]) -> Dict[str, Any]:
    """Susun perjalanan satu pesanan. Read-only — tidak menyentuh dokumen apa pun."""
    oid = order.get("id", "")
    status = str(order.get("status") or "")
    dibatalkan = status in STATUS_BATAL

    tasks = await _outbound_tasks(oid)
    kirim = await _shipments(oid)
    faktur = await _tax_invoices(oid)
    kwitansi = await _receipts(oid)
    pemenuhan = await _fulfillment_block(order)

    ver = order.get("verification") or {}
    grand = float(order.get("grand_total") or order.get("total_amount") or 0)
    dibayar = float(order.get("paid_total") or 0)
    sisa = 0.0 if dibatalkan else round(max(0.0, grand - dibayar), 2)
    # KEB-PDPT — kebijakan pendapatan: uang muka yang masih kewajiban vs sudah diakui.
    from services import gl_service as _gl
    pendapatan_diakui = await _gl.order_revenue_posted(oid)
    uang_muka_tertahan = await _gl.order_advance_unrecognized(order)
    diakui_rp = (await _gl.order_revenue_recognized(oid))["ar"] if pendapatan_diakui else 0.0

    tasks = [t for t in tasks if t.get("status") not in TASK_IGNORED]
    selesai_task = [t for t in tasks if t.get("status") in TASK_PREPARED]
    appr_at, appr_by = order.get("approved_at", ""), order.get("approved_by", "")
    if not appr_at and status not in ("draft", "pending", "reserved", "waiting_approval", "waiting_stock", ""):
        _at, _by = await _audit_stamp(oid, ("order_approved", "order_auto_approved", "so_approved",
                                             "sample_payment_approved"))
        appr_at, appr_by = _at, appr_by or _by
    conf_at, conf_by = order.get("confirmed_at", ""), order.get("confirmed_by", "")
    if not conf_at and tasks:
        _at, _by = await _audit_stamp(oid, ("order_confirmed", "sample_forwarded_to_warehouse"))
        conf_at, conf_by = _at, conf_by or _by
    terkirim = [s for s in kirim if s.get("status") in ("dispatched", "delivered", "shipped")]
    faktur_aktif = [f for f in faktur if f.get("status") != "batal"]

    steps: List[Dict[str, Any]] = [
        _step("dipesan", "Dipesan", True, order.get("created_at", ""),
              order.get("sales_name") or "",
              f"{len(order.get('items') or [])} baris pesanan"),
        _step("diverifikasi", "Diverifikasi Admin Sales",
              ver.get("status") == "verified", ver.get("at", ""), ver.get("by", ""),
              ("Kelengkapan administratif diperiksa"
               if ver.get("status") == "verified"
               else "Belum diperiksa Admin Sales")),
        _step("disetujui", "Disetujui",
              bool(order.get("approved_at")) or status in (
                  "approved", "confirmed", "partially_picked", "picked",
                  "partially_shipped", "shipped", "done"),
              appr_at, appr_by,
              ("Menunggu keputusan " + str(order.get("required_approval_role") or "manajer")
               if status == "waiting_approval" else "")),
        _step("dikonfirmasi", "Dikonfirmasi (tugas gudang lahir)",
              bool(order.get("confirmed_at")) or status in (
                  "confirmed", "partially_picked", "picked",
                  "partially_shipped", "shipped", "done"),
              conf_at, conf_by,
              f"{len(tasks)} tugas gudang" if tasks else ""),
        _step("disiapkan", "Disiapkan gudang",
              bool(tasks) and len(selesai_task) == len(tasks),
              (max((t.get("completed_at") or t.get("updated_at") or "") for t in selesai_task) if selesai_task else ""), "",
              (f"{len(selesai_task)}/{len(tasks)} tugas gudang selesai" if tasks
               else "Belum ada tugas gudang")),
        _step("dikirim", "Dikirim",
              bool(terkirim), (terkirim[-1].get("created_at", "") if terkirim else ""), "",
              (" · ".join(s.get("shipment_no", "") for s in terkirim[:3])
               if terkirim else "Belum ada surat jalan")),
        _step("diterima", "Diterima pelanggan", status == "done",
              order.get("delivered_at") or order.get("dispatched_at", ""), order.get("delivered_by", ""),
              "Pesanan selesai" if status == "done" else ""),
        # F-08 (uji pra-UAT 2026-10-21) — dokumen tagihan resmi = FAKTUR KOMERSIAL (PDF dari SO, tersedia sejak barang
        # dikirim — pendapatan & piutang diakui per Surat Jalan). Faktur Pajak hanya pelengkap PKP (wewenang Finance),
        # bukan syarat "ditagih". Dulu langkah ini = ada Faktur Pajak, sehingga pesanan lunas pun tampil "belum ditagih".
        _step("ditagih", "Ditagih (Faktur Komersial)", bool(terkirim) and not dibatalkan,
              (min(s.get("created_at", "") for s in terkirim) if terkirim else ""), "",
              ((f"Faktur Komersial {order.get('number') or order.get('order_number') or ''} — PDF di detail pesanan"
                if terkirim else "Faktur Komersial terbit saat barang dikirim (Surat Jalan pertama)")
               + (" · Faktur Pajak " + " · ".join(f.get("number", "") for f in faktur_aktif[:3]) if faktur_aktif
                  else (" · Faktur Pajak: belum (wewenang Finance)" if order.get("tax_mode") == "ppn" else "")))),
        _step("dibayar", "Dibayar", not dibatalkan and sisa <= 0.009 and grand > 0,
              (kwitansi[-1].get("receipt_date", "") if kwitansi else ""), "",
              ("Pesanan dibatalkan — tidak ada tagihan" if dibatalkan
               else "Lunas" if (sisa <= 0.009 and grand > 0)
               else f"Sisa tagihan {sisa:,.0f}".replace(",", "."))),
    ]

    if dibatalkan:
        for s in steps:
            if not s["done"]:
                s["state"] = "cancelled"

    tercapai = [s for s in steps if s["done"]]
    kini = next((s for s in steps if not s["done"]), None)

    return {
        "order_id": oid,
        "order_number": order.get("number", ""),
        "customer_name": order.get("customer_name", ""),
        "sales_name": order.get("sales_name", ""),
        "entity_id": order.get("entity_id", ""),
        "status": status,
        "stage": order.get("stage", ""),
        "sub_status": order.get("sub_status") or [],
        "cancelled": dibatalkan,
        "grand_total": grand,
        "paid_total": dibayar,
        "outstanding": sisa,
        **(await _ledger_split(order, sisa)),
        "revenue_recognized": pendapatan_diakui,
        "revenue_recognized_total": round(diakui_rp, 2),
        "revenue_recognized_pct": round(100.0 * diakui_rp / grand, 1) if grand > 0 else 0.0,
        "advance_unrecognized": uang_muka_tertahan,
        "progress": {"done": len(tercapai), "total": len(steps),
                     "percent": round(100.0 * len(tercapai) / len(steps), 1)},
        "current_step": (kini or {}).get("key", "") if not dibatalkan else "dibatalkan",
        "current_label": ((kini or {}).get("label", "Selesai") if not dibatalkan
                          else "Dibatalkan"),
        "steps": steps,
        "fulfillment": pemenuhan,
        "warehouse_tasks": tasks,
        "shipments": kirim,
        "logistics": await _logistics(oid),   # FB-02 — pelacakan pengiriman
        "tax_invoices": faktur,
        # F-08 — Faktur Komersial (dokumen tagihan resmi, PDF jenis `invoice` dari SO ini)
        "commercial_invoice": {"doc_type": "invoice", "available": bool(terkirim) and not dibatalkan,
                               "number": order.get("number") or order.get("order_number") or ""},
        "receipts": kwitansi,
    }


async def journey_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        return None
    return await journey(order)
