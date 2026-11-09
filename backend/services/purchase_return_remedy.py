"""FIX-6 (keputusan pemilik 10 Nov 2026, D2 · audit B2a FLW-IN-11) — TOLAK QC + RETUR KE SUPPLIER dipilih PER KASUS.

Saat roll ditolak QC dengan tindakan "retur ke supplier", penolak WAJIB memilih penyelesaiannya (beralasan, K-14,
beraudit) — tercatat di dokumen retur beli (`remedy`) dan dieksekusi saat retur beli DISETUJUI:

* **Ganti barang** (`replace`) — supplier mengirim pengganti. PO DIBUKA LAGI: `received_qty` baris dikurangi qty yang
  diretur (`replaced_qty` mencatatnya), status PO → `partial`, dan tugas terima SISA (`waiting_goods`) lahir untuk qty
  itu (`goods_receipt_close_service.ensure_remainder_task`, ditandai `replacement_for_return`). Hutang TIDAK berubah
  (tagihan tetap untuk qty penuh). Jurnal: PEMBALIK GR-IR Dr GR-IR / Cr Persediaan (neto) — barang pengganti nanti
  diposting GR baru (Dr Persediaan / Cr GR-IR) sehingga GR-IR seimbang dengan tagihan supplier.
* **Potong tagihan** (`bill_cut`) — tidak ada pengganti; tagihan supplier dikurangi lewat dokumen retur beli yang
  sudah ada (Nota Debit): `returned_amount` PO (AP) naik sebesar nilai bruto, `returned_qty` baris mencatat qty yang
  diretur sehingga 3-way match tagihan = diterima − diretur. Jurnal:
    - PO SUDAH ditagih (tagihan supplier diposting) → Dr Hutang (bruto) / Cr Persediaan (neto) / Cr PPN Masukan (jalur
      Nota Debit lama, `gl_service.post_purchase_return`);
    - PO BELUM ditagih → PEMBALIK GR-IR Dr GR-IR / Cr Persediaan (neto, tanpa PPN — PPN baru diakui saat tagihan).
  PO yang sudah diterima penuh → DITUTUP KURANG (`closed_short`, rekonsiliasi `po_close_settlement_service`); PO yang
  masih menunggu qty lain tetap terbuka (tidak menunggu pengganti untuk qty yang diretur).

Pembalikan saat retur beli DIKOREKSI (reverse): `undo()` mengembalikan `received_qty`/`replaced_qty`/`returned_qty`,
membatalkan tugas pengganti yang belum menerima barang (bila sudah menerima → koreksi DITOLAK), dan memulihkan status
PO sebelum retur. Retur yang DITOLAK sebelum disetujui (`on_reject`): roll tolak QC kembali sebagai barang rusak.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core_utils import new_id, now_iso
from db import db

REMEDIES: Dict[str, str] = {"replace": "Ganti barang", "bill_cut": "Potong tagihan"}
REMEDY_HINT: Dict[str, str] = {
    "replace": "PO dibuka lagi dengan tugas terima sisa sebesar qty yang diretur; tagihan supplier tetap.",
    "bill_cut": "PO ditutup kurang; tagihan supplier dikurangi (Nota Debit) dengan jurnal pembalik GR-IR.",
}
EPS = 0.001


def validate_choice(choice: Any, reason: Any) -> Dict[str, Any]:
    """Pilihan wajib + alasan K-14 (≥ 5 huruf). ValueError berbahasa Indonesia bila tidak sah."""
    c = str(choice or "").strip().lower()
    if c not in REMEDIES:
        raise ValueError("Pilih penyelesaian retur ke supplier: 'Ganti barang' (PO dibuka lagi, tugas terima sisa) atau "
                         "'Potong tagihan' (PO ditutup kurang, tagihan dikurangi).")
    from input_rules import reason_problem
    msg = reason_problem(reason, label="Alasan pilihan retur ke supplier")
    if msg:
        raise ValueError(msg)
    return {"choice": c, "label": REMEDIES[c], "reason": str(reason).strip()}


async def record_choice(pret: Dict[str, Any], remedy: Dict[str, Any], actor: Dict[str, Any],
                        task: Dict[str, Any]) -> Dict[str, Any]:
    rec = {**remedy, "hint": REMEDY_HINT[remedy["choice"]], "by": actor.get("name", ""), "by_id": actor.get("id", ""),
           "at": now_iso(), "task_id": task.get("id", ""), "po_applied": False}
    await db.purchase_returns.update_one({"id": pret["id"]}, {"$set": {"remedy": rec}})
    from dependencies import audit
    await audit(actor.get("name", ""), "purchase_return_remedy_chosen", "purchase_return", pret["id"],
                {"number": pret.get("number", ""), "choice": rec["choice"], "po_number": pret.get("po_number", ""),
                 "task_id": rec["task_id"]}, reason=rec["reason"], scope_entity_id=pret.get("entity_id") or "")
    return rec


async def po_billed(po_id: str) -> bool:
    if not po_id:
        return False
    return bool(await db.vendor_bills.find_one({"po_id": po_id, "status": {"$in": ["posted", "paid"]}},
                                               {"_id": 0, "id": 1}))


def _line(ret: Dict[str, Any]) -> Dict[str, Any]:
    it = (ret.get("items") or [{}])[0]
    return {"product_id": it.get("product_id", ""), "qty": round(float(it.get("quantity") or 0), 4),
            "unit": it.get("unit", "")}


def _timeline(event: str, title: str, actor: str, note: str) -> Dict[str, Any]:
    from core_utils import timeline_entry
    return timeline_entry(event, title, actor, note)


async def apply_on_approve(ret: Dict[str, Any], actor: str) -> Dict[str, Any]:
    """Eksekusi pilihan saat retur beli DISETUJUI: AP (potong tagihan), jurnal, efek PO. Idempoten per efek."""
    from services import gl_service
    rem = dict(ret.get("remedy") or {})
    choice = rem.get("choice")
    ln = _line(ret)
    po_id = ret.get("po_id") or ""
    gross = round(float(ret.get("grand_total") or (float(ret.get("total_amount") or 0)
                                                    + float(ret.get("ppn_amount") or 0))), 2)
    net = round(float(ret.get("total_amount") or 0), 2)
    label = ret.get("debit_note_number") or ret.get("number", "")
    billed = await po_billed(po_id)
    out: Dict[str, Any] = {"choice": choice}
    # 1) AP — hanya potong tagihan (AP turun sebesar bruto, satu kali).
    if choice == "bill_cut" and po_id and not ret.get("ap_adjusted"):
        await db.purchase_returns.update_one({"id": ret["id"], "ap_adjusted": {"$ne": True}}, {"$set": {"ap_adjusted": True}})
        await db.purchase_orders.update_one({"id": po_id}, {"$inc": {"returned_amount": gross}, "$set": {"updated_at": now_iso()}})
        from routers.purchase_orders import recompute_po_payment_status
        await recompute_po_payment_status(po_id)
    elif choice == "replace":
        await db.purchase_returns.update_one({"id": ret["id"]}, {"$set": {"ap_adjusted": False}})
    # 2) Jurnal — pembalik GR-IR neto (ganti barang / belum ditagih) atau Nota Debit ke Hutang (sudah ditagih).
    if choice == "bill_cut" and billed:
        je = await gl_service.post_purchase_return(ret, amount=gross, ppn=float(ret.get("ppn_amount") or 0),
                                                   label=label, outcome="ap_credit")
        out["gl_mode"] = "debit_note_ap"
    else:
        je = await gl_service.post_purchase_return_grir(ret, net=net, label=label, reason=REMEDIES.get(choice, ""))
        out["gl_mode"] = "grir_reversal_net"
    out["journal_entry_id"] = (je or {}).get("id", "")
    # 3) PO — sekali (`remedy.po_applied`).
    if po_id and not rem.get("po_applied"):
        out.update(await (_reopen_for_replacement(ret, ln, actor) if choice == "replace"
                          else _close_short_for_bill_cut(ret, ln, actor)))
    return out


async def _reopen_for_replacement(ret: Dict[str, Any], ln: Dict[str, Any], actor: str) -> Dict[str, Any]:
    from services.goods_receipt_close_service import ensure_remainder_task
    po_id, pid, qty = ret["po_id"], ln["product_id"], ln["qty"]
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}) or {}
    prev = po.get("status", "")
    if prev in ("cancelled", "rejected"):
        await _mark_applied(ret, {"po_effect": "po_tidak_aktif", "po_prev_status": prev})
        return {"po_effect": "po_tidak_aktif"}
    res = await db.purchase_orders.update_one(
        {"id": po_id, "items": {"$elemMatch": {"product_id": pid, "received_qty": {"$gte": qty - EPS}}}},
        {"$inc": {"items.$.received_qty": -qty, "items.$.replaced_qty": qty},
         "$set": {"updated_at": now_iso()},
         "$push": {"timeline": _timeline("reopened", "PO dibuka lagi — ganti barang",
                                         actor, f"Retur {ret.get('number', '')}: {qty:g} {ln['unit']} diganti supplier")}})
    if not res.modified_count:
        raise ValueError("Qty diterima baris PO lebih kecil dari qty yang diretur — periksa PO sebelum menyetujui.")
    if prev in ("completed", "closed_short", "receiving", "partial", "pending"):
        await db.purchase_orders.update_one({"id": po_id, "status": prev}, {"$set": {"status": "partial"}})
    rt = await ensure_remainder_task(po_id, pid, actor, (ret.get("remedy") or {}).get("task_id", ""))
    tid = rt.get("task_id", "")
    if rt.get("reason") == "exists" and tid:
        # Tugas aktif lama (qty lain masih ditunggu) — harapannya ikut naik sebesar sisa baris PO.
        await db.wms_tasks.update_one({"id": tid, "status": {"$in": ["waiting_goods", "receiving"]}},
                                      {"$set": {"expected_qty": rt.get("remaining"), "updated_at": now_iso()}})
    if tid:
        await db.wms_tasks.update_one({"id": tid}, {"$set": {"replacement_for_return": {
            "id": ret["id"], "number": ret.get("number", ""), "qty": qty, "created": bool(rt.get("created"))}}})
    eff = {"po_effect": "dibuka_lagi", "po_prev_status": prev, "replacement_task_id": tid,
           "replacement_task_created": bool(rt.get("created")), "qty": qty}
    await _mark_applied(ret, eff)
    return eff


async def _close_short_for_bill_cut(ret: Dict[str, Any], ln: Dict[str, Any], actor: str) -> Dict[str, Any]:
    po_id, pid, qty = ret["po_id"], ln["product_id"], ln["qty"]
    await db.purchase_orders.update_one({"id": po_id, "items.product_id": pid},
                                        {"$inc": {"items.$.returned_qty": qty}, "$set": {"updated_at": now_iso()}})
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}) or {}
    prev = po.get("status", "")
    eff: Dict[str, Any] = {"po_prev_status": prev, "qty": qty}
    if prev == "completed":
        reason = f"Potong tagihan — retur {ret.get('number', '')}: {(ret.get('remedy') or {}).get('reason', '')}"
        done = await db.purchase_orders.update_one(
            {"id": po_id, "status": "completed"},
            {"$set": {"status": "closed_short", "short_close_reason": reason, "short_closed_by": actor,
                      "short_closed_at": now_iso(), "short_close_source": {"type": "purchase_return", "id": ret["id"],
                                                                           "number": ret.get("number", "")}},
             "$push": {"timeline": _timeline("closed_short", "PO ditutup kurang — potong tagihan", actor, reason)}})
        if done.modified_count:
            eff["po_effect"] = "ditutup_kurang"
            try:
                from services import po_close_settlement_service as _pcs
                fresh = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
                await _pcs.record_on_close(fresh, actor)
            except Exception:   # noqa: BLE001 — rekonsiliasi tindak lanjut, bukan syarat sahnya retur
                pass
    else:
        eff["po_effect"] = "po_tetap_terbuka" if prev not in ("closed_short", "cancelled") else f"po_{prev}"
    await _mark_applied(ret, eff)
    return eff


async def _mark_applied(ret: Dict[str, Any], eff: Dict[str, Any]) -> None:
    await db.purchase_returns.update_one({"id": ret["id"]}, {"$set": {
        "remedy.po_applied": True, "remedy.po_applied_at": now_iso(), "remedy.po_result": eff}})


async def assert_can_undo(ret: Dict[str, Any]) -> None:
    """Guard koreksi: tugas pengganti yang SUDAH menerima barang tidak bisa dibatalkan otomatis."""
    rem = ret.get("remedy") or {}
    res = rem.get("po_result") or {}
    if rem.get("choice") == "replace" and res.get("replacement_task_id"):
        t = await db.wms_tasks.find_one({"id": res["replacement_task_id"]}, {"_id": 0, "status": 1, "received_qty": 1})
        if t and (t.get("status") not in ("waiting_goods", "cancelled") or float(t.get("received_qty") or 0) > EPS):
            raise ValueError("Barang pengganti untuk retur ini sudah mulai diterima — koreksi otomatis tidak aman. "
                             "Selesaikan penerimaan pengganti, lalu koreksi selisihnya lewat retur/opname.")


async def undo(ret: Dict[str, Any], actor: str, reason: str) -> Dict[str, Any]:
    """Balik efek PO pilihan tolak QC (dipanggil `purchase_return_service.reverse_settlement` sesudah guard)."""
    rem = ret.get("remedy") or {}
    res = rem.get("po_result") or {}
    po_id = ret.get("po_id") or ""
    if not rem.get("po_applied") or not po_id:
        return {}
    ln = _line(ret)
    qty = float(res.get("qty") or ln["qty"])
    out: Dict[str, Any] = {}
    if rem.get("choice") == "replace":
        tid = res.get("replacement_task_id")
        if tid and res.get("replacement_task_created"):
            from services import inbound_task_state as _its
            await _its.transition(tid, "cancel", "cancelled", actor_name=actor, from_status=["waiting_goods"],
                                  set_fields={"cancel_reason": f"Retur {ret.get('number', '')} dikoreksi: {reason}",
                                              "cancelled_by": actor, "cancelled_at": now_iso()},
                                  note=reason, prev_status="waiting_goods")
        await db.purchase_orders.update_one(
            {"id": po_id, "items.product_id": ln["product_id"]},
            {"$inc": {"items.$.received_qty": qty, "items.$.replaced_qty": -qty}, "$set": {"updated_at": now_iso()},
             "$push": {"timeline": _timeline("reopen_reversed", "Ganti barang dibatalkan", actor, reason)}})
        prev = res.get("po_prev_status")
        if prev and prev != "partial":
            await db.purchase_orders.update_one({"id": po_id, "status": "partial"}, {"$set": {"status": prev}})
        out = {"po_restored": prev, "replacement_task_cancelled": bool(tid and res.get("replacement_task_created"))}
    else:
        await db.purchase_orders.update_one(
            {"id": po_id, "items.product_id": ln["product_id"]},
            {"$inc": {"items.$.returned_qty": -qty}, "$set": {"updated_at": now_iso()}})
        if res.get("po_effect") == "ditutup_kurang":
            await db.purchase_orders.update_one(
                {"id": po_id, "status": "closed_short", "short_close_source.id": ret["id"]},
                {"$set": {"status": res.get("po_prev_status") or "completed"},
                 "$unset": {"short_close_source": "", "close_settlement": ""},
                 "$push": {"timeline": _timeline("closed_short_reversed", "Tutup kurang dibatalkan", actor, reason)}})
        out = {"po_restored": res.get("po_prev_status")}
    await db.purchase_returns.update_one({"id": ret["id"]}, {"$set": {"remedy.po_applied": False,
                                                                     "remedy.undone_at": now_iso(),
                                                                     "remedy.undo_result": out}})
    return out


async def on_reject(ret: Dict[str, Any], actor: str, reason: str) -> int:
    """Retur dari TOLAK QC ditolak SEBELUM disetujui: roll yang sudah dipisah `returned_supplier` kembali ke gudang
    sebagai barang RUSAK (tetap persediaan; jurnal retur belum pernah ada → subledger kembali = GL)."""
    if ret.get("source") != "qc_reject" or not ret.get("stock_adjusted"):
        return 0
    from services.roll_service import rebuild_balance
    n, segs = 0, set()
    async for r in db.inventory_rolls.find({"status": "returned_supplier", "returned_ref.id": ret["id"]}, {"_id": 0}):
        res = await db.inventory_rolls.update_one(
            {"id": r["id"], "status": "returned_supplier"},
            {"$set": {"status": "damaged", "returned_ref": None, "qc_return_rejected": {
                "return_id": ret["id"], "number": ret.get("number", ""), "reason": reason, "by": actor,
                "at": now_iso()}, "updated_at": now_iso()}})
        if not res.modified_count:
            continue
        n += 1
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r.get("product_id"), "warehouse_id": r.get("warehouse_id"),
            "owner_entity_id": r.get("owner_entity_id"), "type": "qc_return_rejected_back",
            "movement_type": "qc_return_rejected_back", "direction": "in",
            "quantity": round(float(r.get("length_remaining") or 0), 2), "unit": r.get("unit", ""), "roll_id": r["id"],
            "qty_rolls": 1, "ref_type": "purchase_return", "ref_id": ret["id"], "source_document": ret.get("number", ""),
            "notes": f"Retur beli {ret.get('number', '')} ditolak — barang tolak QC tetap di gudang sebagai rusak",
            "timestamp": now_iso()})
        segs.add((r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id")))
    for pid, wid, eid in segs:
        await rebuild_balance(pid, wid, eid)
    return n
