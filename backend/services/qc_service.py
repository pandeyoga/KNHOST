"""Depth #3a — QC Hold / Quarantine saat Goods Receipt.

Alur: barang masuk (GR) → roll `quarantine` (BUKAN langsung available) → inspektur
QC memutuskan per task:
  - ACCEPT (qty): quarantine → available, lalu auto-fulfill backorder.
  - REJECT (qty): pilih disposisi
      • "damaged"  → quarantine → `damaged` (tetap di gudang, tercatat)
      • "return"   → quarantine → `returned_supplier` (keluar on_hand) + buat
                      Purchase Return / Nota Debit (stock_adjusted=True) ke supplier.

SSOT-safe (KN_15 §3.4): semua transisi di LEVEL ROLL (split bila parsial); balance
di-rebuild dari rolls sehingga invarian `on_hand == Σ bucket` & `balance == Σ rolls`
tetap utuh. TIDAK pernah $inc balance langsung.
"""
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso, new_id, DEFAULT_ENTITY_ID, safe_doc
from services.roll_service import rebuild_balance, insert_child_roll

RETURNED_STATUS = "returned_supplier"  # terminal — tidak masuk bucket fisik manapun


async def get_quarantine_rolls(task_id: str) -> List[Dict[str, Any]]:
    return await db.inventory_rolls.find(
        {"qc_task_id": task_id, "status": "quarantine", "length_remaining": {"$gt": 0}},
        {"_id": 0},
    ).to_list(1000)


async def quarantine_qty_for_task(task_id: str) -> float:
    rolls = await get_quarantine_rolls(task_id)
    return round(sum(float(r.get("length_remaining", 0) or 0) for r in rolls), 2)


async def _consume_quarantine(
    qrolls: List[Dict[str, Any]], qty: float, target_status: str,
    owner: str, ref: Dict[str, Any], mov_type: str, extra_set: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pindahkan `qty` dari roll quarantine (in-place list) → `target_status`.
    Split roll bila parsial. Catat movement. Return {moved_qty, rolls:[...]}."""
    remaining = round(float(qty), 2)
    moved_rolls: List[Dict[str, Any]] = []
    for roll in qrolls:
        if remaining <= 0.01:
            break
        rlen = float(roll.get("length_remaining", 0) or 0)
        if rlen <= 0.01:
            continue
        take = round(min(rlen, remaining), 2)
        set_doc = {"status": target_status, "updated_at": now_iso()}
        if extra_set:
            set_doc.update(extra_set)
        if take >= rlen - 0.01:
            # seluruh roll bertransisi
            await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": set_doc})
            roll["length_remaining"] = 0.0
            moved_id, moved_len = roll["id"], rlen
        else:
            # parsial → kurangi parent (tetap quarantine), buat child target_status
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(rlen - take, 2),
                          "length_initial": round(float(roll["length_initial"]) - take, 2),
                          "updated_at": now_iso()}},
            )
            child = dict(roll)
            child.pop("_id", None)
            child.update({
                "id": new_id("roll"),
                "length_initial": round(take, 2),
                "length_remaining": round(take, 2),
                "is_remnant": False,
                "created_at": now_iso(), "updated_at": now_iso(),
                **set_doc,
            })
            child = await insert_child_roll(child, roll)
            roll["length_remaining"] = round(rlen - take, 2)
            moved_id, moved_len = child["id"], take
        await db.inventory_movements.insert_one({
            "id": new_id("mov"),
            "product_id": roll["product_id"],
            "warehouse_id": roll["warehouse_id"],
            "owner_entity_id": owner,
            "movement_type": mov_type,
            "quantity": round(moved_len, 2),
            "unit": roll.get("unit", "meter"),
            "lot": roll.get("lot", ""),
            "roll_id": moved_id,
            # FASE U — satu baris mutasi menunjuk SATU roll fisik.
            "qty_rolls": (1 if moved_id else None),
            "ref_type": ref.get("type"),
            "ref_id": ref.get("id"),
            "source_document": ref.get("doc", ""),
            "timestamp": now_iso(),
        })
        moved_rolls.append({"roll_id": moved_id, "lot": roll.get("lot", ""), "length": round(moved_len, 2)})
        remaining = round(remaining - take, 2)
    return {"moved_qty": round(qty - max(remaining, 0.0), 2), "rolls": moved_rolls}


async def _next_return_number() -> str:
    from services.purchase_return_service import next_return_number
    return await next_return_number()


async def _purchase_qty_of_pieces(product: Dict[str, Any], qrolls: List[Dict[str, Any]], base_qty: float,
                                  po_unit: str) -> float:
    """W2-014 — qty dasar QC (panjang roll) → qty SATUAN HARGA PO, per potongan yg akan ditolak
    (urutan sama dgn _consume_quarantine). Berat potongan = berat terukur roll proporsional panjang."""
    from services.uom_service import load_fixed_factors, convert, kg_per_base_unit, _norm
    factors = await load_fixed_factors()
    base_u = product.get("base_unit", "meter")
    if _norm(po_unit) == _norm(base_u):
        return round(base_qty, 3)
    remaining, total = round(float(base_qty), 2), 0.0
    for r in qrolls:
        if remaining <= 0.01:
            break
        rlen = float(r.get("length_remaining", 0) or 0)
        if rlen <= 0.01:
            continue
        take = round(min(rlen, remaining), 2)
        if _norm(po_unit) == "kg":
            w = float(r.get("weight_kg") or 0)
            total += (w * take / rlen) if w > 0 else take * kg_per_base_unit(product, factors)
        else:
            total += convert(product, take, base_u, po_unit, factors, precision=4)
        remaining = round(remaining - take, 2)
    return round(total, 3)


async def _create_qc_return(task: Dict[str, Any], po: Optional[Dict[str, Any]], qty: float,
                            reason: str, created_by: str,
                            qrolls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Buat dokumen Purchase Return (Nota Debit) untuk barang QC-reject yang
    dikembalikan ke supplier. stock_adjusted=True karena roll SUDAH dipindah
    ke returned_supplier oleh QC (approval hanya menerbitkan DN + kurangi AP)."""
    product = safe_doc(await db.products.find_one({"id": task["product_id"]}, {"_id": 0})) or {}
    price = 0.0
    po_unit = ""
    if po:
        for it in po.get("items", []):
            if it.get("product_id") == task["product_id"]:
                price = float(it.get("price", 0) or 0)
                po_unit = it.get("unit") or ""
                break
    if price <= 0:
        price = float(product.get("price", 0) or 0)
    base_unit = product.get("base_unit", "meter")
    unit = po_unit or task.get("unit") or base_unit
    qty_base = round(qty, 2)
    qty_purchase = await _purchase_qty_of_pieces(product, list(qrolls or []), qty_base, unit) if qrolls else qty_base
    subtotal = round(price * qty_purchase, 2)
    # P19 QC-04 — PPN ikut dibalik seperti retur manual (KN-B21); dulu retur QC penuh menyisakan hutang PPN
    from services.purchase_return_service import po_ppn_rate
    ppn_rate = po_ppn_rate(po)
    ppn_amount = round(subtotal * ppn_rate / 100.0, 2)
    number = await _next_return_number()
    now = now_iso()
    doc = {
        "id": new_id("pret"), "number": number,
        "supplier_id": (po or {}).get("supplier_id", ""),
        "supplier_name": (po or {}).get("supplier_name", ""),
        "po_id": (po or {}).get("id", task.get("po_id")),
        "po_number": (po or {}).get("po_number", task.get("po_number", "")),
        "warehouse_id": task["warehouse_id"],
        "warehouse_name": task.get("warehouse_name", ""),
        "entity_id": (po or {}).get("entity_id", DEFAULT_ENTITY_ID),
        "items": [{
            "product_id": task["product_id"], "sku": product.get("sku", ""),
            "product_name": product.get("name", task.get("product_name", "")),
            "quantity": qty_purchase, "unit": unit,
            "qty_base": qty_base, "unit_base": base_unit,
            "price": price, "subtotal": subtotal,
            "reason": reason or "QC reject", "condition": "rejected_qc",
        }],
        "total_amount": subtotal,
        "ppn_rate": ppn_rate, "ppn_amount": ppn_amount, "grand_total": round(subtotal + ppn_amount, 2),
        "reason": reason or "Ditolak saat inspeksi QC penerimaan",
        "notes": f"Auto dari QC penerimaan task {task['id']}",
        "source": "qc_reject",
        "status": "pending_approval", "stock_adjusted": True,
        "debit_note_number": "",
        "created_by": created_by, "approved_by": None, "approved_at": None,
        "rejected_by": None, "rejected_at": None, "reject_reason": None,
        "created_at": now, "updated_at": now,
    }
    await db.purchase_returns.insert_one(dict(doc))
    from services import doc_refs_service as _refs
    if doc.get("po_id"):
        await _refs.safe_link(("purchase_return", doc["id"]), ("purchase_order", doc["po_id"]),
                              "reverses", note="retur hasil penolakan QC")
    return safe_doc(doc)


QC_MODES = ("all", "sampling")


def plan_sample_size(n_rolls: int, pct: float, min_rolls: int) -> int:
    """PG01 — ukuran sampel = max(min, ceil(pct% × n)), dibatasi jumlah roll."""
    import math
    if n_rolls <= 0:
        return 0
    return max(1, min(n_rolls, max(int(min_rolls or 1), math.ceil(n_rolls * float(pct or 0) / 100.0))))


def roll_inspected(r: Dict[str, Any]) -> bool:
    return bool((r.get("inspection") or {}).get("inspected_at")) or r.get("grade_source") == "manager_override"


async def qc_coverage(task: Dict[str, Any]) -> Dict[str, Any]:
    """PG01 — rencana (Cek semua / Sampling) + cakupan inspeksi aktual per task QC."""
    plan = task.get("qc_plan") or {"mode": "all"}
    rolls = await db.inventory_rolls.find({"qc_task_id": task["id"]},
                                          {"_id": 0, "id": 1, "inspection": 1, "grade_source": 1}).to_list(None)
    n = len(rolls)
    inspected = sum(1 for r in rolls if roll_inspected(r))
    if plan.get("mode") == "sampling":
        required = plan_sample_size(n, plan.get("sample_pct", 10), plan.get("sample_min", 1))
    else:
        required = n
    return {"mode": plan.get("mode", "all"), "sample_pct": plan.get("sample_pct"), "sample_min": plan.get("sample_min"),
            "planned_by": plan.get("planned_by"), "planned_at": plan.get("planned_at"),
            "total_rolls": n, "inspected_rolls": inspected, "required_rolls": required,
            "coverage_pct": round(100.0 * inspected / n, 1) if n else 0.0, "met": inspected >= required}


async def set_qc_plan(task: Dict[str, Any], mode: str, sample_pct: float, sample_min: int,
                      actor: Dict[str, Any]) -> Dict[str, Any]:
    if task.get("status") != "qc_pending":
        raise ValueError("Rencana QC hanya dapat diubah selama task menunggu QC.")
    if mode not in QC_MODES:
        raise ValueError("Mode QC harus 'all' (Cek semua) atau 'sampling'.")
    plan: Dict[str, Any] = {"mode": mode, "planned_by": actor.get("name", ""), "planned_at": now_iso()}
    if mode == "sampling":
        if not (0 < float(sample_pct or 0) <= 100):
            raise ValueError("Persentase sampel harus 1–100%.")
        if int(sample_min or 0) < 1:
            raise ValueError("Minimal roll sampel harus ≥ 1.")
        plan.update(sample_pct=float(sample_pct), sample_min=int(sample_min))
    await db.wms_tasks.update_one({"id": task["id"], "status": "qc_pending"},
                                  {"$set": {"qc_plan": plan, "updated_at": now_iso()},
                                   "$push": {"qc_plan_history": plan}})
    return await qc_coverage({**task, "qc_plan": plan})


async def process_qc_decision(
    task: Dict[str, Any], accept_qty: float, reject_qty: float,
    reject_disposition: str, reason: str, actor: Dict[str, Any],
    accept_grade: str = "A", defects: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Proses keputusan QC untuk 1 inbound task. Lihat docstring modul.

    P0-4 — `accept_grade` & `defects` ditanam ke roll yang lolos (available)
    sebagai grade aktual hasil inspeksi tekstil."""
    task_id = task["id"]
    product_id = task["product_id"]
    warehouse_id = task["warehouse_id"]

    po = None
    owner = DEFAULT_ENTITY_ID
    if task.get("po_id"):
        po = safe_doc(await db.purchase_orders.find_one({"id": task["po_id"]}, {"_id": 0}))
        owner = (po or {}).get("entity_id") or DEFAULT_ENTITY_ID

    # Fase A · PS-09/D-01 — grade hasil inspeksi WAJIB nilai enum resmi (A|A1|A2|B|BS).
    from services import grade_service
    accept_grade = grade_service.normalize_or_raise(accept_grade or "A", "Grade diterima")

    # QC-06 — roll yang DITAHAN wajib dilepas dulu (keputusan tidak boleh melompati tahanan)
    from services.roll_hold_service import held_rolls_for_task
    held = await held_rolls_for_task(task_id)
    if held:
        raise ValueError("Roll " + ", ".join(str(r.get("roll_no") or r["id"]) for r in held)
                         + " sedang DITAHAN — lepas tahanan dulu sebelum keputusan QC.")

    qrolls = await get_quarantine_rolls(task_id)
    total_q = round(sum(float(r.get("length_remaining", 0) or 0) for r in qrolls), 2)
    if total_q <= 0.01:
        raise ValueError("Tidak ada stok karantina untuk task ini.")

    accept_qty = round(float(accept_qty or 0), 2)
    reject_qty = round(float(reject_qty or 0), 2)
    if accept_qty < 0 or reject_qty < 0:
        raise ValueError("Qty tidak boleh negatif.")
    if accept_qty + reject_qty <= 0.01:
        raise ValueError("Tentukan qty terima dan/atau tolak.")
    if accept_qty + reject_qty > total_q + 0.05:
        raise ValueError(
            f"Total terima+tolak ({round(accept_qty + reject_qty, 2)}) melebihi qty karantina ({total_q}).")
    if reject_qty > 0.01 and reject_disposition not in ("damaged", "return"):
        raise ValueError("Disposisi reject harus 'damaged' atau 'return'.")
    # IX-15 — task QC terminal hanya bila SELURUH qty karantina punya disposisi
    if accept_qty + reject_qty < total_q - 0.05:
        raise ValueError(
            f"Keputusan QC wajib mencakup seluruh qty karantina ({total_q}); "
            f"sisa {round(total_q - accept_qty - reject_qty, 2)} belum diputuskan.")
    # PG01 — cakupan inspeksi sesuai rencana (Cek semua / Sampling) sebelum mutasi apa pun
    coverage = await qc_coverage(task)
    if not coverage["met"]:
        raise ValueError(
            f"Inspeksi belum memenuhi rencana '{'Cek semua' if coverage['mode'] == 'all' else 'Sampling'}': "
            f"{coverage['inspected_rolls']}/{coverage['required_rolls']} roll wajib diinspeksi.")

    doc_ref = task.get("po_number") or task_id
    result: Dict[str, Any] = {
        "task_id": task_id, "product_id": product_id, "warehouse_id": warehouse_id,
        "accepted_qty": 0.0, "rejected_qty": 0.0,
        "reject_disposition": reject_disposition if reject_qty > 0.01 else None,
        "purchase_return": None,
    }

    # Snapshot grade sebelum konsumsi (untuk riwayat before → after, PS-09).
    _grade_before = {r["id"]: (r.get("grade") or "") for r in qrolls if r.get("id")}

    # Sesi 12 — klaim saga SESUDAH semua validasi, SEBELUM roll karantina dikonsumsi/retur/balance.
    from services import atomic_claim as _saga
    await _saga.claim("wms_tasks", task_id, "qc_decision", actor=actor.get("name", ""),
                      precondition={"status": "qc_pending"})
    try:
        result, set_fields = await _apply_qc_decision(task, po, owner, qrolls, _grade_before, accept_qty, reject_qty,
                                                      reject_disposition, reason, actor, accept_grade, defects, result, doc_ref)
    except Exception as e:
        await _saga.mark_failed("wms_tasks", task_id, str(e))
        raise
    # PG01 — cakupan tercatat: keputusan sampel berlaku eksplisit untuk sisa lot
    set_fields["qc_coverage"] = {**coverage, "decision_applies_to_uninspected": coverage["inspected_rolls"] < coverage["total_rolls"]}
    result["qc_coverage"] = set_fields["qc_coverage"]
    if set_fields["qc_coverage"]["decision_applies_to_uninspected"] and result.get("roll_ids"):
        # QC-06 — tandai roll yang diputuskan lewat hasil sampel (tidak diinspeksi langsung)
        await db.inventory_rolls.update_many(
            {"id": {"$in": result["roll_ids"]}, "inspection.inspected_at": {"$exists": False}},
            {"$set": {"qc_via_sampling": {"task_id": task_id, "at": now_iso(),
                                          "inspected_rolls": coverage["inspected_rolls"],
                                          "total_rolls": coverage["total_rolls"]}}})
    # 5) Update task — status + jejak QC + cabut kunci (tulisan akhir saga)
    await db.wms_tasks.update_one({"id": task_id}, _saga.finish_set(set_fields))
    return result


async def _apply_qc_decision(task, po, owner, qrolls, _grade_before, accept_qty, reject_qty,
                             reject_disposition, reason, actor, accept_grade, defects, result, doc_ref):
    from services import grade_service
    task_id = task["id"]
    product_id = task["product_id"]
    warehouse_id = task["warehouse_id"]

    # 1) ACCEPT → available
    if accept_qty > 0.01:
        acc = await _consume_quarantine(
            qrolls, accept_qty, "available", owner,
            {"type": "qc_inspection", "id": task_id, "doc": doc_ref},
            mov_type="qc_accept",
            extra_set={"qc_task_id": None, "qc_passed_at": now_iso(),
                       "grade": accept_grade, "qc_grade": accept_grade,
                       "grade_source": "qc_inspection", "grade_updated_at": now_iso(),
                       "defects": list(defects or [])},
        )
        result["accepted_qty"] = acc["moved_qty"]
        result["accept_grade"] = accept_grade
        result.setdefault("roll_ids", []).extend(r["roll_id"] for r in acc.get("rolls", []) if r.get("roll_id"))
        # PS-09 — jejak perubahan grade per roll yang lolos QC (before → after).
        for _r in acc.get("rolls", []) or []:
            _rid = _r.get("roll_id") or ""
            _before = _grade_before.get(_rid, "")
            if not _rid or _before == accept_grade:
                continue
            await db.inventory_rolls.update_one(
                {"id": _rid},
                {"$push": {"grade_history": grade_service.history_entry(
                    _before, accept_grade, "qc_inspection",
                    f"Keputusan QC {doc_ref}: diterima {acc['moved_qty']}",
                    actor, {"lot": _r.get("lot", "")})}})

    # 2) REJECT → damaged | returned_supplier (+ Nota Debit)
    if reject_qty > 0.01:
        if reject_disposition == "damaged":
            rej = await _consume_quarantine(
                qrolls, reject_qty, "damaged", owner,
                {"type": "qc_inspection", "id": task_id, "doc": doc_ref},
                mov_type="qc_reject_damaged",
                extra_set={"qc_task_id": None, "qc_rejected_at": now_iso(),
                           "reject_reason": reason or "QC reject"},
            )
            result["rejected_qty"] = rej["moved_qty"]
            result.setdefault("roll_ids", []).extend(r["roll_id"] for r in rej.get("rolls", []) if r.get("roll_id"))
        else:  # return
            pret = await _create_qc_return(task, po, reject_qty, reason, actor.get("name", "system"), qrolls=qrolls)
            rej = await _consume_quarantine(
                qrolls, reject_qty, RETURNED_STATUS, owner,
                {"type": "purchase_return", "id": pret["id"], "doc": pret["number"]},
                mov_type="qc_reject_return",
                extra_set={"qc_task_id": None, "qc_rejected_at": now_iso(),
                           "returned_ref": {"type": "purchase_return", "id": pret["id"]},
                           "reject_reason": reason or "QC reject"},
            )
            result["rejected_qty"] = rej["moved_qty"]
            result.setdefault("roll_ids", []).extend(r["roll_id"] for r in rej.get("rolls", []) if r.get("roll_id"))
            result["purchase_return"] = {"id": pret["id"], "number": pret["number"],
                                         "supplier_name": pret.get("supplier_name", "")}

    # 3) Rebuild balance segmen terdampak
    await rebuild_balance(product_id, warehouse_id, owner)

    # 4) Auto-fulfill backorder bila ada stok baru available
    if result["accepted_qty"] > 0.01:
        from services.backorder_service import auto_fulfill_backorders
        await auto_fulfill_backorders(product_id, owner)
        # Fase 4 OD — stok pesanan khusus lolos QC → lanjutkan otomatisasi pengiriman OD.
        try:
            from services import special_order_phase2 as _p2
            od = await db.special_orders.find_one({"$or": [{"pricing.product_id": product_id}, {"linked_product_id": product_id}],
                                                   "status": {"$in": ["in_production", "ready"]}}, {"_id": 0, "id": 1})
            if od:
                await _p2.on_goods_received(od["id"])
        except Exception as exc:  # noqa: BLE001
            if od:
                await db.special_orders.update_one({"id": od["id"]}, {"$set": {"shipping_error": str(exc)}})

    # 5) Update task — status + jejak QC
    if result["accepted_qty"] > 0.01:
        new_status = "completed"
    else:
        new_status = "qc_rejected"
    qc_result = ("passed" if result["rejected_qty"] <= 0.01
                 else ("rejected" if result["accepted_qty"] <= 0.01 else "partial"))
    result["task_status"] = new_status
    result["qc_status"] = qc_result
    return result, {
        "status": new_status,
        "qc_status": qc_result,
        "qc_accept_qty": result["accepted_qty"],
        "qc_reject_qty": result["rejected_qty"],
        "qc_reject_disposition": result["reject_disposition"],
        "qc_reason": reason or "",
        "qc_by": actor.get("name", "system"),
        "qc_at": now_iso(),
        "updated_at": now_iso(),
    }
