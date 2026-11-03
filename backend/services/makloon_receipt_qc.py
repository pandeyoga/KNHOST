"""Hasil langkah TERAKHIR Order Makloon = barang masuk gudang, diperlakukan seperti barang PO.

Kasus klien: 20 roll Esmica Blue dicelup hitam di mitra; Esmica Hitam 20 roll "datang dari pabrik sebagai barang
baru". Dulu `receive_step` melahirkan roll hasil langsung `available` — tanpa karantina QC, tanpa SPK inspeksi, tanpa
tahap journey — sehingga barang yang belum diperiksa bisa langsung dipesan pelanggan dan tidak pernah lewat antrean
tag/putaway. Modul ini menyamakannya dengan jalur PO (`inbound_complete_service`) lewat aturan bersama
`inbound_qc_common`:

  * `purchasing.qc_on_receipt` (SATU kunci yang sama dengan PO — barang jadi yang masuk gudang tetap barang masuk;
    dua kunci berarti dua kebijakan yang bisa saling bertentangan tanpa disadari) → roll `quarantine` + tugas QC
    `wms_tasks` (flow inbound, `source_type=makloon_order`, satu per produk × gudang) + SPK inspeksi otomatis
    (jenis "Inspeksi Hasil Makloon"). Rilis QC yang ada (`qc_service.process_qc_decision` lewat SPK / antrean)
    lalu menjalankan backorder & pesanan khusus seperti PO.
  * Tahap journey awal sesuai peran gudang tujuan (`received_transit` / `stored`), routing `store` → roll muncul di
    antrean tag RFID / verifikasi label / putaway yang sama dengan roll PO.
  * Tag RFID otomatis (`receiving.auto_rfid_on_scan`): roll makloon tidak lahir dari scan label (GRN mencatatnya
    manual), jadi EPC dibuat saat roll hasil lahir — kunci & fungsi yang sama dengan jalur scan PO.

Langkah TENGAH (output N = input N+1) sengaja TIDAK disentuh: `issue_step` langkah berikutnya mengambil roll
`available`; karantina di tengah rantai akan menghentikan SPK sampai QC memutus barang setengah jadi yang memang
belum menjadi barang gudang. Barang sisa langkah tengah juga tidak (sisa bahan milik sendiri yang sudah lolos QC
saat pertama masuk).
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import now_iso
from db import db
from services import inbound_qc_common as iqc

logger = logging.getLogger(__name__)

FLOW_SERVICE = "service_only"
SOURCE_TYPE = "makloon_order"


def require_unit(unit: Any, sku: Any) -> str:
    """Penjaga satuan jalur makloon: satuan kosong → 400 (dulu jatuh diam-diam ke "meter")."""
    u = str(unit or "").strip()
    if not u:
        raise HTTPException(status_code=400, detail=(
            f"Satuan dasar produk {sku or '(tanpa SKU)'} belum diisi di master produk — lengkapi dulu."))
    return u


async def receipt_units(step: Dict[str, Any], out_prod: Dict[str, Any], actual_by: float) -> Tuple[str, str]:
    """(satuan roll output, satuan roll sisa) — dihitung SEBELUM klaim penerimaan (400 tanpa efek samping)."""
    out_unit = require_unit(step.get("output_unit") or out_prod.get("base_unit"),
                            out_prod.get("sku") or step.get("output_sku") or step.get("output_product_id"))
    by_unit = ""
    if actual_by > 0:
        by_pid = step.get("byproduct_product_id") or ""
        by_prod = (await db.products.find_one({"id": by_pid}, {"_id": 0, "sku": 1, "base_unit": 1}) or {}
                   ) if by_pid else out_prod
        by_unit = require_unit(step.get("input_unit") or step.get("output_unit") or by_prod.get("base_unit"),
                               by_prod.get("sku") or by_pid or step.get("input_sku"))
    return out_unit, by_unit


def is_final_fabric_step(order: Dict[str, Any], seq: int) -> bool:
    """Tidak ada langkah KAIN sesudah `seq` (langkah jasa murni di belakangnya tidak menerima kain)."""
    return not any(int(s.get("seq") or 0) > int(seq) and str(s.get("material_flow") or "moves") != FLOW_SERVICE
                   for s in order.get("steps") or [])


async def receipt_policy(order: Dict[str, Any], step: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    final = is_final_fabric_step(order, int(step.get("seq") or 0))
    qc = final and await iqc.qc_on_receipt_enabled(entity_id)
    lot_status = ""
    if qc:   # sama dengan PO: lot penerimaan berstatus kebijakan lot (bawaan "karantina")
        from services import lot_service as _lots
        lot_status = (await _lots.get_settings(entity_id)).get("status_on_receipt", "karantina")
    return {"final": final, "qc": qc, "roll_status": "quarantine" if qc else "available",
            "lot_status": lot_status, "stages": {}}


def task_id_for(mko_id: str, seq: int, product_id: str, warehouse_id: str) -> str:
    """Id tugas QC DETERMINISTIK (retry penerimaan menemukan tugas yang sama, tidak membuat kembar)."""
    return "wms_mko_" + hashlib.sha1(f"{mko_id}|{seq}|{product_id}|{warehouse_id}".encode()).hexdigest()[:16]


async def mark_roll(roll: Dict[str, Any], policy: Dict[str, Any], mko_id: str, seq: int) -> None:
    """Roll hasil langkah terakhir: journey awal + penaut tugas QC (idempoten — aman diulang saat retry)."""
    if not policy.get("final"):
        return
    wh = roll.get("warehouse_id") or ""
    if wh not in policy["stages"]:
        policy["stages"][wh] = await iqc.initial_journey_stage(wh)
    upd: Dict[str, Any] = {"journey": iqc.journey(policy["stages"][wh]), "updated_at": now_iso()}
    if policy.get("qc"):
        upd["qc_task_id"] = task_id_for(mko_id, seq, roll["product_id"], wh)
    await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": upd})


async def open_receipt_tasks(order: Dict[str, Any], step: Dict[str, Any], policy: Dict[str, Any],
                             roll_ids: List[str], data: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    """Tugas QC `qc_pending` per (produk × gudang) untuk roll karantina langkah terakhir (idempoten)."""
    state: Dict[str, Any] = {"final_step": True, "required": bool(policy.get("qc")), "task_ids": [],
                             "inspections": [], "stages": dict(policy.get("stages") or {}), "at": now_iso()}
    if not policy.get("qc") or not roll_ids:
        return state
    rolls = await db.inventory_rolls.find({"id": {"$in": list(roll_ids)}, "qc_task_id": {"$nin": [None, ""]}},
                                          {"_id": 0}).to_list(len(roll_ids) + 5)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rolls:
        groups.setdefault(r["qc_task_id"], []).append(r)
    from services import doc_refs_service as _refs
    for tid, rs in sorted(groups.items()):
        r0 = rs[0]
        qty = round(sum(float(r.get("length_remaining") or 0) for r in rs), 2)
        live = {"quantity": qty, "received_qty": qty, "expected_qty": qty, "quarantine_qty": qty,
                "qty_rolls": len(rs), "updated_at": now_iso()}
        cur = await db.wms_tasks.find_one({"id": tid}, {"_id": 0, "id": 1, "status": 1})
        if cur:
            if cur.get("status") == "qc_pending":
                await db.wms_tasks.update_one({"id": tid, "status": "qc_pending"}, {"$set": live})
            state["task_ids"].append(tid)
            continue
        prod = await db.products.find_one({"id": r0["product_id"]}, {"_id": 0, "name": 1, "sku": 1}) or {}
        wh = await db.warehouses.find_one({"id": r0["warehouse_id"]}, {"_id": 0, "name": 1, "city": 1}) or {}
        await db.wms_tasks.insert_one({
            "id": tid, "entity_id": order["entity_id"], "owner_entity_id": order["entity_id"],
            "flow_type": "inbound", "source_type": SOURCE_TYPE, "task_subtype": "makloon_receipt",
            "mko_id": order["id"], "mko_number": order.get("mko_number", ""), "step_seq": int(step["seq"]),
            "makloon_id": step.get("makloon_id", ""), "supplier_name": step.get("makloon_name", ""),
            "special_order_id": order.get("special_order_id") or "",
            "receipt_role": "byproduct" if r0["product_id"] != step.get("output_product_id") else "output",
            "po_id": "", "po_number": "", "product_id": r0["product_id"], "product_name": prod.get("name", ""),
            "sku": prod.get("sku", ""), "unit": r0.get("unit", ""), "line_code": order.get("line_code") or "",
            "warehouse_id": r0["warehouse_id"], "warehouse_name": wh.get("name", ""),
            "warehouse_city": wh.get("city", ""), "expected_rolls": len(rs),
            "lot": r0.get("lot", ""), "lot_ids": sorted({r.get("lot_id") for r in rs if r.get("lot_id")}),
            "grn_id": data.get("grn_id") or "", "grn_number": data.get("grn_number") or "",
            "supplier_dn_number": (data.get("supplier_dn") or "").strip(),
            "status": "qc_pending", "stages": ["qc_pending", "completed"], "qc_status": "pending",
            "scan_log": [], "escalation": None, "bin_id": "", "batch": "", "roll_id": "",
            "created_by": actor_name, "created_at": now_iso(), **live})
        await _refs.safe_link(("grn", tid), ("makloon_order", order["id"]), "parent",
                              note=f"QC hasil langkah {step['seq']}")
        state["task_ids"].append(tid)
    return state


async def after_receipt(order: Dict[str, Any], seq: int, roll_ids: List[str], actor_name: str) -> Dict[str, Any]:
    """SESUDAH penerimaan tersimpan (best-effort, tidak membatalkan penerimaan): SPK inspeksi per tugas QC +
    tag RFID otomatis. Hasilnya ditulis ke `steps[].receipt_qc` supaya layar MKO menyebut nomor SPK-nya."""
    step = next((s for s in order.get("steps") or [] if int(s.get("seq") or 0) == int(seq)), {})
    state = dict(step.get("receipt_qc") or {})
    actor = {"name": actor_name, "id": ""}
    if state.get("required"):
        found = []
        for tid in state.get("task_ids") or []:
            task = await db.wms_tasks.find_one({"id": tid}, {"_id": 0})
            if task:
                found.append({"task_id": tid, **await iqc.ensure_inspection(task, actor)})
        state["inspections"] = found
    try:
        from services.receiving_roll_service import receiving_cfg
        if roll_ids and bool(await receiving_cfg("auto_rfid_on_scan", order["entity_id"])):
            from services import rfid_service as _rfid
            tagged = 0
            for rid in roll_ids:
                try:
                    await _rfid.encode_tag(rid, [order["entity_id"]], actor_name=actor_name)
                    tagged += 1
                except HTTPException as exc:   # sudah ber-tag (retry) / bukan fisik → petugas tag manual
                    logger.info("Auto-RFID roll makloon %s dilewati: %s", rid, exc.detail)
            state["rfid_tagged"] = tagged
    except Exception as exc:  # noqa: BLE001 — tag otomatis pelengkap; gagal → antrean tag manual
        logger.warning("Auto-RFID hasil makloon %s gagal: %s", order.get("id"), exc)
    await db.makloon_orders.update_one({"id": order["id"]}, {"$set": {"steps.$[s].receipt_qc": state}},
                                       array_filters=[{"s.seq": step.get("seq", seq)}])
    return state


async def annotate_detail(order: Dict[str, Any]) -> None:
    """Layar MKO: langkah issued tahu apakah hasilnya akan dikarantina; langkah received tahu status QC-nya."""
    qc_cache: Optional[bool] = None
    for s in order.get("steps") or []:
        if s.get("status") == "issued" and str(s.get("material_flow") or "moves") != FLOW_SERVICE:
            final = is_final_fabric_step(order, int(s.get("seq") or 0))
            if final and qc_cache is None:
                qc_cache = await iqc.qc_on_receipt_enabled(order.get("entity_id") or "")
            s["receipt_qc_expected"] = bool(final and qc_cache)
        rq = s.get("receipt_qc") or {}
        if rq.get("task_ids"):
            rows = {t["id"]: t async for t in db.wms_tasks.find(
                {"id": {"$in": rq["task_ids"]}}, {"_id": 0, "id": 1, "status": 1, "qc_status": 1, "sku": 1,
                                                  "quantity": 1, "unit": 1, "qty_rolls": 1})}
            rq["tasks"] = [rows[t] for t in rq["task_ids"] if t in rows]
