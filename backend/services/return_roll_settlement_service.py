"""UAT 23 Okt (permintaan pemilik) — PENYELESAIAN RETUR PER ROLL, boleh bertahap.

Tiap roll klaim diputus sendiri:
  · Pengembalian Dana / Store Credit / Tukar Barang — roll kembali ke stok (karantina) dengan qty aktual QC;
  · Cutloss — qty cacat dari catatan MD per roll (potongan baik kembali ke pelanggan lewat pecah roll MD);
  · Diskon — nominal keputusan Finance; kain tetap / dikirim balik ke pelanggan;
  · Tolak klaim — tanpa kompensasi; kain dikirim balik ke pelanggan.
Satu PENYELESAIAN (event) boleh mencampur outcome dan tidak harus memuat semua roll — sisanya diputus di penyelesaian
berikutnya. Retur baru berstatus selesai bila semua roll sudah diputus (seragam → status lama, campuran → `settled`).

Uang per penyelesaian = SATU Nota Kredit berbaris per roll. Nilainya memotong sisa tagihan SO asal lebih dulu (LN-091,
urutan: nego → pengembalian dana → store credit → tukar barang, supaya saldo tukar barang tersisa paling akhir),
sisanya ke tujuan outcome-nya: refund kas · saldo pelanggan · pengurang piutang. Jurnal per penyelesaian
(source_id `<retur>:<penyelesaian>`), mutasi kas & saldo ber-ref yang sama → idempoten & bisa dibalik per penyelesaian.
"""
from typing import Any, Dict, List, Optional, Tuple

from core_utils import new_id, now_iso, rupiah
from db import db
from services import gl_service
from services import return_state as st

OUTCOMES: Dict[str, Dict[str, Any]] = {
    "refund": {"label": "Pengembalian Dana", "group": "refund", "family": "refund", "stock": True},
    "store_credit": {"label": "Store Credit", "group": "store_credit", "family": "credit", "stock": True},
    "exchange": {"label": "Tukar Barang", "group": "exchange", "family": "credit", "stock": True},
    "cutloss": {"label": "Cutloss", "group": "nego", "family": "nego", "stock": False},
    "discount": {"label": "Diskon", "group": "nego", "family": "nego", "stock": False},
    "reject": {"label": "Tolak klaim", "group": "", "family": "reject", "stock": False},
}
FAMILY_STATE = {"refund": st.REFUND_SETTLED, "credit": st.CREDIT_SETTLED, "nego": st.NEGO_SETTLED}
FAMILY_OUTCOME = {"refund": st.OUTCOME_REFUND, "credit": st.OUTCOME_STORE_CREDIT, "nego": st.OUTCOME_NEGO}
# Urutan pemotongan sisa tagihan SO asal (LN-091): saldo tukar barang dipertahankan paling akhir.
BILL_ORDER = ("nego", "refund", "store_credit", "exchange")
OPEN_STATUSES = ("inspected", "approved")


class RollSettlementError(ValueError):
    pass


def is_roll_mode(ret: Dict[str, Any]) -> bool:
    """Penyelesaian per roll berlaku bila SEMUA baris retur menunjuk roll klaim (retur lama tanpa roll = jalur lama)."""
    items = ret.get("items") or []
    return bool(items) and all(it.get("roll_ids") for it in items)


async def roll_rows(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Roll klaim + pilihan outcome yang SAH saat ini (dengan alasan bila belum bisa)."""
    from services.return_journey_service import physical_warehouse
    comp = ret.get("compensation") or {}
    decided = comp.get("status") == "decided"
    comp_lines = comp.get("lines") or [] if decided else []
    allowed_types = (ret.get("policy_snapshot") or {}).get("allowed_return_types")
    exchange_ok = not allowed_types or "penggantian" in allowed_types
    settled = ret.get("roll_outcomes") or {}
    status = ret.get("status")
    ids = [r for it in ret.get("items") or [] for r in (it.get("roll_ids") or [])]
    nos = {r["id"]: r async for r in db.inventory_rolls.find({"id": {"$in": ids}},
                                                              {"_id": 0, "id": 1, "roll_no": 1, "status": 1})}
    cut_by_roll: Dict[str, List[Dict[str, Any]]] = {}
    for c in ret.get("cutloss") or []:
        if c.get("roll_id"):
            cut_by_roll.setdefault(c["roll_id"], []).append(c)
    rows: List[Dict[str, Any]] = []
    for i, it in enumerate(ret.get("items") or []):
        insp = it.get("inspection") or {}
        results = insp.get("roll_results") or {}
        pid = it.get("product_id", "")
        for rid in it.get("roll_ids") or []:
            rr = results.get(rid) or {}
            claim = round(float((it.get("roll_qtys") or {}).get(rid) or 0), 4)
            actual = round(float(rr["actual_qty"]) if rr.get("actual_qty") is not None else claim, 4)
            wh = physical_warehouse(ret, rid)
            cuts = cut_by_roll.get(rid, [])
            cut_qty = round(sum(float(c.get("qty_base") or 0) for c in cuts), 4)
            split_done = any((c.get("split") or {}).get("status") == "done" for c in cuts)
            prev = settled.get(rid) or {}
            qc_ok = bool(rr) and status == "inspected"
            stock_why = ("Roll sudah dipecah (cutloss) — hanya bisa diselesaikan sebagai Cutloss." if split_done else
                         "Barang roll ini belum diterima gudang (scan Terima/Tiba)." if not wh else
                         "QC roll ini belum selesai." if not qc_ok else "")
            cut_line = any(x.get("product_id") == pid and x.get("kind") == "cutloss" for x in comp_lines)
            disc_line = next((x for x in comp_lines if x.get("product_id") == pid and x.get("kind") == "discount"), None)
            cut_why = ("Catat qty cacat roll ini dulu (MD, panel Cutloss & diskon)." if cut_qty <= 0 else
                       "Nilai cutloss belum diputus Finance." if not cut_line else
                       "QC roll ini belum selesai." if status != "inspected" else "")
            disc_why = ("Roll sudah dipecah (cutloss) — hanya bisa diselesaikan sebagai Cutloss." if split_done else
                        "Nominal diskon barang ini belum diputus Finance." if not disc_line else
                        "Diskon barang ini sudah dipakai di penyelesaian sebelumnya." if (disc_line or {}).get("used_by") else
                        "Sebelum QC hanya diskon dari foto/video (bukti terlampir di keputusan Finance)."
                        if status == "approved" and not (disc_line or {}).get("evidence_ids") else "")
            opts = []
            for v, why in (("refund", stock_why), ("store_credit", stock_why),
                           ("exchange", stock_why or ("" if exchange_ok else "Kebijakan retur tidak mengizinkan tukar barang.")),
                           ("cutloss", cut_why), ("discount", disc_why),
                           ("reject", "Roll sudah dipecah (cutloss) — hanya bisa diselesaikan sebagai Cutloss." if split_done else "")):
                opts.append({"value": v, "label": OUTCOMES[v]["label"], "ok": not why, "why": why})
            rows.append({
                "roll_id": rid, "roll_no": rr.get("roll_no") or (nos.get(rid) or {}).get("roll_no", rid),
                "item_index": i, "product_id": pid, "product_name": it.get("product_name", ""), "unit": it.get("unit", ""),
                "claim_qty": claim, "actual_qty": actual, "grade": rr.get("grade", ""),
                "condition": rr.get("condition") or it.get("condition", "ok"), "received_at": wh,
                "cut_qty": cut_qty, "cut_treatment": next((c.get("treatment") for c in cuts if c.get("treatment")), ""),
                "split_done": split_done, "settled": prev, "options": [] if prev else opts})
    return rows


async def _net_price(order: Dict[str, Any], pid: str) -> float:
    from services.return_compensation_service import _net_unit_price
    return await _net_unit_price(order, pid)


async def plan_event(ret: Dict[str, Any], decisions: List[Dict[str, Any]], payout: str = "",
                     refund_account_code: str = "") -> Dict[str, Any]:
    """Hitung satu penyelesaian TANPA menulis apa pun: baris per roll, Nota Kredit, pembagian, jurnal."""
    from services import return_service as rs
    if ret.get("status") not in OPEN_STATUSES:
        raise RollSettlementError(f"Retur berstatus '{ret.get('status')}' — penyelesaian hanya sesudah disetujui/QC.")
    if not is_roll_mode(ret):
        raise RollSettlementError("Retur ini tidak menunjuk roll — pakai penyelesaian per barang.")
    rows = {r["roll_id"]: r for r in await roll_rows(ret)}
    chosen: List[Tuple[Dict[str, Any], str]] = []
    for d in decisions or []:
        rid, oc = d.get("roll_id", ""), (d.get("outcome") or "").strip()
        if not oc:
            continue   # roll ini belum diputus pada penyelesaian ini
        row = rows.get(rid)
        if not row:
            raise RollSettlementError("Roll bukan roll klaim retur ini.")
        if row["settled"]:
            raise RollSettlementError(f"Roll {row['roll_no']} sudah diputus di penyelesaian ke-{row['settled'].get('seq')}.")
        opt = next((o for o in row["options"] if o["value"] == oc), None)
        if not opt:
            raise RollSettlementError(f"Outcome '{oc}' tidak dikenal.")
        if not opt["ok"]:
            raise RollSettlementError(f"{row['roll_no']}: {opt['why']}")
        chosen.append((row, oc))
    if not chosen:
        raise RollSettlementError("Pilih outcome minimal untuk satu roll.")
    if payout not in ("", "refund", "store_credit"):
        raise RollSettlementError("Kompensasi cutloss/diskon: refund | store_credit | kosong (kurangi piutang SO asal).")

    order = await db.sales_orders.find_one({"id": ret["order_id"]}, {"_id": 0}) or {}
    comp_lines = (ret.get("compensation") or {}).get("lines") or []
    # Diskon Finance per barang dibagi ke roll diskon barang itu menurut qty aktual.
    disc_rolls: Dict[str, List[Dict[str, Any]]] = {}
    for row, oc in chosen:
        if oc == "discount":
            disc_rolls.setdefault(row["product_id"], []).append(row)
    eff: List[Tuple[Dict[str, Any], str, Dict[str, Any]]] = []
    for row, oc in chosen:
        if oc == "reject":
            continue
        item = {"product_id": row["product_id"], "product_name": row["product_name"], "unit": row["unit"],
                "condition": row["condition"], "reason": OUTCOMES[oc]["label"]}
        if OUTCOMES[oc]["stock"]:
            item["quantity_returned"] = row["actual_qty"]
        elif oc == "cutloss":
            price = await _net_price(order, row["product_id"])
            item.update(quantity_returned=row["cut_qty"], credit_amount=round(row["cut_qty"] * price, 2))
        else:
            line = next(x for x in comp_lines if x.get("product_id") == row["product_id"] and x.get("kind") == "discount")
            peers = disc_rolls[row["product_id"]]
            tot = sum(r["actual_qty"] for r in peers) or len(peers)
            share = (row["actual_qty"] or 1) / tot
            item.update(quantity_returned=round(float(line["qty"]) * share, 4),
                        credit_amount=round(float(line["amount"]) * share, 2))
        if float(item["quantity_returned"] or 0) <= 0:
            raise RollSettlementError(f"{row['roll_no']}: qty penyelesaian 0 — periksa qty aktual / qty cacat.")
        eff.append((row, oc, item))

    fig = await rs._cn_figures(ret, [x[2] for x in eff], post_stock=False) if eff else \
        {"order": order, "lines": [], "net": 0.0, "ppn": 0.0, "gross": 0.0, "ppn_rate": float(order.get("ppn_rate") or 0)}
    eid = ret.get("entity_id", "")
    group_net: Dict[str, float] = {g: 0.0 for g in BILL_ORDER}
    lines, cogs = [], 0.0
    for (row, oc, item), ln in zip(eff, fig["lines"]):
        c = 0.0
        if OUTCOMES[oc]["stock"] and row["condition"] != "damaged":
            c = round(row["actual_qty"] * await gl_service._avg_unit_cost(row["product_id"], eid), 2)
        cogs += c
        group_net[OUTCOMES[oc]["group"]] += ln["line_total"]
        lines.append({**ln, "roll_id": row["roll_id"], "roll_no": row["roll_no"], "outcome": oc,
                      "outcome_label": OUTCOMES[oc]["label"], "cogs": c})
    net, ppn, gross = fig["net"], fig["ppn"], fig["gross"]
    frac = (ppn / net) if net > 0 else 0.0
    group_gross: Dict[str, float] = {}
    for g in BILL_ORDER:
        group_gross[g] = round(group_net[g] * (1 + frac), 2)
    resid = round(gross - sum(group_gross.values()), 2)
    if resid and gross > 0:   # selisih pembulatan PPN ke kelompok terbesar
        top = max(group_gross, key=group_gross.get)
        group_gross[top] = round(group_gross[top] + resid, 2)

    open_amt = round(float(order.get("grand_total") or 0) - sum(float(p.get("amount") or 0) for p in order.get("payments") or []), 2)
    from services.return_policy_service import return_assumptions
    bill_first = bool((await return_assumptions(eid)).get("bill_first", True))
    cap = max(open_amt, 0.0) if order else 0.0
    bill: Dict[str, float] = {}
    for g in BILL_ORDER:
        eligible = (g == "nego" and payout == "") or bill_first
        take = round(min(group_gross[g], cap), 2) if eligible and group_gross[g] > 0 else 0.0
        bill[g], cap = take, round(cap - take, 2)
    rest = {g: round(group_gross[g] - bill[g], 2) for g in BILL_ORDER}
    nego_dest = {"": "ar", "refund": "cash", "store_credit": "store_credit"}[payout]
    cash = rest["refund"] + (rest["nego"] if nego_dest == "cash" else 0.0)
    saldo = rest["store_credit"] + rest["exchange"] + (rest["nego"] if nego_dest == "store_credit" else 0.0)
    ar_rest = rest["nego"] if nego_dest == "ar" else 0.0
    bill_total = round(sum(bill.values()), 2)
    problem = ""
    if ar_rest > 0.01:
        problem = (f"Sisa tagihan {ret.get('order_number') or 'SO asal'} hanya {rupiah(max(open_amt, 0))} — kompensasi "
                   f"cutloss/diskon {rupiah(group_gross['nego'])} melebihinya. Pilih 'Jadi saldo' atau 'Refund tunai'.")
    cash_acc = (refund_account_code or "1-1100")
    split = [x for x in (
        {"kind": "source_bill", "label": f"Potong sisa tagihan {ret.get('order_number') or 'SO asal'}", "amount": bill_total},
        {"kind": "cash", "label": "Refund tunai ke pelanggan", "amount": round(cash, 2)},
        {"kind": "store_credit", "label": "Jadi saldo pelanggan" + (" (termasuk saldo tukar barang)" if rest["exchange"] > 0 else ""),
         "amount": round(saldo, 2)},
    ) if x["amount"] > 0]
    credits = [(gl_service.ACC_PIUTANG, bill_total + ar_rest, "Pengurang piutang"),
               (cash_acc, cash, "Refund tunai"),
               (gl_service.ACC_STORE_CREDIT, saldo, "Saldo kredit pelanggan (store credit)")]
    raw = gl_service.sales_return_settlement_lines(net=net, ppn=ppn, cogs=cogs, credits=credits,
                                                   label="(nomor Nota Kredit saat terbit)")
    from services import gl_mapping_service as _glm
    journal = await _glm.remap_lines(raw, eid, "sales_return")
    names = await gl_service._account_names([ln["account_code"] for ln in journal])
    cost_codes = {await gl_service.account_for("persediaan.persediaan", eid), await gl_service.account_for("persediaan.hpp", eid)}
    for ln in journal:
        ln["account_name"] = names.get(ln["account_code"], "")
        ln["cost"] = ln["account_code"] in cost_codes
    per_roll = []
    by_roll_line = {ln["roll_id"]: ln for ln in lines}
    for row, oc in chosen:
        ln = by_roll_line.get(row["roll_id"]) or {}
        back = 0.0
        if oc == "cutloss":
            back = round(max(row["actual_qty"] - row["cut_qty"], 0.0), 4)
        elif oc in ("discount", "reject") and row["received_at"]:
            back = row["actual_qty"]
        per_roll.append({"roll_id": row["roll_id"], "roll_no": row["roll_no"], "item_index": row["item_index"],
                         "product_id": row["product_id"], "product_name": row["product_name"], "unit": row["unit"],
                         "outcome": oc, "outcome_label": OUTCOMES[oc]["label"], "actual_qty": row["actual_qty"],
                         "qty_stock": row["actual_qty"] if OUTCOMES[oc]["stock"] else 0.0,
                         "qty_cut": row["cut_qty"] if oc == "cutloss" else 0.0, "cut_treatment": row["cut_treatment"],
                         "qty_back": back, "credit_qty": ln.get("quantity", 0.0), "unit_price": ln.get("unit_price", 0.0),
                         "credit_amount": ln.get("line_total", 0.0), "cogs": ln.get("cogs", 0.0),
                         "received_at": row["received_at"], "condition": row["condition"]})
    return {"rolls": per_roll, "lines": lines, "net_amount": net, "ppn_amount": ppn, "gross_amount": gross,
            "ppn_rate": fig.get("ppn_rate", 0.0), "cogs_amount": round(cogs, 2), "split": split, "journal": journal,
            "problem": problem, "payout": payout, "refund_account_code": cash_acc if cash > 0 else "",
            "bill_total": bill_total, "cash_total": round(cash, 2), "saldo_total": round(saldo, 2), "ar_rest": round(ar_rest, 2),
            "exchange_credit": rest["exchange"], "order_number": ret.get("order_number", ""), "source_open": max(open_amt, 0.0),
            "source_bill_checked": True, "post_stock": any(r["qty_stock"] > 0 for r in per_roll),
            "basis": "Harga transaksi neto SO asal × qty aktual QC (stok) · qty cacat (cutloss) · nominal Finance (diskon)"}


def _final_status(ret: Dict[str, Any], outcomes: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], str]:
    """(status akhir, outcome) bila SEMUA roll klaim sudah diputus; (None, "") bila masih ada yang belum."""
    ids = [r for it in ret.get("items") or [] for r in (it.get("roll_ids") or [])]
    if any(r not in outcomes for r in ids):
        return None, ""
    fams = {OUTCOMES[o["outcome"]]["family"] for o in outcomes.values()} - {"reject"}
    if not fams:
        return st.REJECTED, st.OUTCOME_REJECT
    if len(fams) == 1:
        f = next(iter(fams))
        return FAMILY_STATE[f], FAMILY_OUTCOME[f]
    return st.SETTLED_MIXED, "mixed"


async def execute(return_id: str, decisions: List[Dict[str, Any]], actor: Dict[str, Any], *, payout: str = "",
                  refund_account_code: str = "", decision_note: str = "", notes: str = "",
                  attachment_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    from services import atomic_claim as saga
    ret = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise RollSettlementError("Retur tidak ditemukan")
    if any(e.get("status") == "posting" for e in ret.get("settlements") or []):
        raise RollSettlementError("Ada penyelesaian yang belum tuntas — tekan 'Lengkapi' dulu.")
    plan = await plan_event(ret, decisions, payout, refund_account_code)
    if plan["problem"]:
        raise RollSettlementError(plan["problem"])
    seq = int(ret.get("settlement_seq") or 0) + 1
    await saga.claim("sales_returns", return_id, "sales_return_roll_settle",
                     precondition={"status": ret["status"], "settlement_seq": ret.get("settlement_seq")},
                     actor=actor.get("name", ""))
    event = {"id": new_id("rst"), "seq": seq, "status": "posting", "at": now_iso(), "by": actor.get("name", ""),
             "by_role": actor.get("role", ""), "decision_note": (decision_note or "").strip(), "notes": notes or "",
             "attachment_ids": list(attachment_ids or []), "payout": payout, "plan": plan, "restocked": []}
    await db.sales_returns.update_one({"id": return_id}, {"$push": {"settlements": event},
                                                         "$set": {"settlement_seq": seq, "updated_at": now_iso()}})
    try:
        return await _apply(return_id, event["id"], actor)
    except Exception as exc:   # noqa: BLE001 — kunci dibiarkan (terlihat di Kunci Saga), penyelesaian bisa dilengkapi
        await saga.mark_failed("sales_returns", return_id, str(exc))
        raise


async def complete(return_id: str, settlement_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Lengkapi penyelesaian yang terhenti di tengah (efek idempoten: stok, Nota Kredit, tagihan, jurnal, kas, saldo)."""
    ret = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    ev = next((e for e in (ret or {}).get("settlements") or [] if e["id"] == settlement_id), None)
    if not ev:
        raise RollSettlementError("Penyelesaian tidak ditemukan")
    if ev.get("status") == "done":
        return ret
    from services import atomic_claim as saga
    await saga.release("sales_returns", return_id)
    await saga.claim("sales_returns", return_id, "sales_return_roll_settle_complete", actor=actor.get("name", ""))
    return await _apply(return_id, settlement_id, actor)


async def _apply(return_id: str, settlement_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import atomic_claim as saga
    from services import return_service as rs
    ret = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    ev = next(e for e in ret.get("settlements") or [] if e["id"] == settlement_id)
    plan, seq, now = ev["plan"], ev["seq"], now_iso()
    label = f"{ret.get('number', '')}/P{seq}"
    ref_id = f"{return_id}:{settlement_id}"
    # 1) Roll yang kembali ke stok → karantina (per roll; tercatat agar tidak dua kali).
    done_rolls = set(ev.get("restocked") or [])
    for r in plan["rolls"]:
        if r["qty_stock"] <= 0 or r["roll_id"] in done_rolls:
            continue
        it = (ret.get("items") or [])[r["item_index"]]
        insp = it.get("inspection") or {}
        item = {**it, "roll_ids": [r["roll_id"]], "roll_qtys": {r["roll_id"]: (it.get("roll_qtys") or {}).get(r["roll_id"], r["actual_qty"])},
                "quantity_returned": r["actual_qty"], "condition": r["condition"],
                "inspection": {**insp, "grade": ((insp.get("roll_results") or {}).get(r["roll_id"]) or {}).get("grade") or insp.get("grade"),
                               "roll_actuals": {r["roll_id"]: r["actual_qty"]}}}
        await rs._restock_returned_items(ret, [item], now, owner_entity_id=ret.get("entity_id", ""))
        await db.sales_returns.update_one({"id": return_id, "settlements.id": settlement_id},
                                          {"$addToSet": {"settlements.$.restocked": r["roll_id"]},
                                           "$unset": {"quarantine_released": ""}})
    # 2) Nota Kredit (satu per penyelesaian).
    cn = await db.credit_notes.find_one({"return_id": return_id, "settlement_id": settlement_id, "status": {"$ne": "void"}}, {"_id": 0})
    if not cn and plan["gross_amount"] > 0:
        cn = {"id": new_id("cn"), "number": await rs.next_credit_note_number(),
              "return_id": return_id, "return_number": ret.get("number", ""), "order_id": ret["order_id"],
              "order_number": ret.get("order_number", ""), "customer_id": ret.get("customer_id"),
              "customer_name": ret.get("customer_name", ""), "entity_id": ret.get("entity_id", ""),
              "return_type": ret.get("return_type", "retur"), "settlement_id": settlement_id, "settlement_seq": seq,
              "lines": plan["lines"], "net_amount": plan["net_amount"], "ppn_rate": plan["ppn_rate"],
              "ppn_amount": plan["ppn_amount"], "gross_amount": plan["gross_amount"], "cogs_amount": plan["cogs_amount"],
              "settlement": "per_roll", "split": plan["split"], "bill_scope": "source_order", "ar_applied": 0,
              "excess_amount": round(plan["gross_amount"] - plan["bill_total"], 2),
              "refund_account_code": plan["refund_account_code"], "outcome": "per_roll", "status": "posted",
              "created_by": actor.get("name", ""), "created_at": now, "updated_at": now}
        await db.credit_notes.insert_one(dict(cn))
        try:
            from services import doc_refs_service as _refs
            await _refs.safe_link(("credit_note", cn["id"]), ("sales_order", ret["order_id"]), "corrects",
                                  note="Nota kredit atas retur pesanan ini")
            await _refs.safe_link(("credit_note", cn["id"]), ("sales_return", return_id), "issued_by",
                                  note="Diterbitkan oleh retur pelanggan (penyelesaian per roll)")
        except Exception:   # noqa: BLE001 — jejak dokumen, bukan syarat sah
            pass
    if cn:
        # 3) Potong sisa tagihan SO asal.
        if plan["bill_total"] > 0 and not float(cn.get("ar_applied") or 0):
            from services import ar_receipt_service as _ar
            await _ar.apply_from_case(ret["order_id"], plan["bill_total"], cn["id"], cn["number"], method="credit_note")
            await db.credit_notes.update_one({"id": cn["id"]}, {"$set": {"ar_applied": plan["bill_total"]}})
        # 4) Jurnal.
        credits = [(gl_service.ACC_PIUTANG, plan["bill_total"] + plan["ar_rest"], "Pengurang piutang"),
                   (plan["refund_account_code"] or "1-1100", plan["cash_total"], "Refund tunai"),
                   (gl_service.ACC_STORE_CREDIT, plan["saldo_total"], "Saldo kredit pelanggan (store credit)")]
        je = await gl_service.post_sales_return_settlement(
            ret, settlement_id, net=plan["net_amount"], ppn=plan["ppn_amount"], cogs=plan["cogs_amount"],
            credits=credits, label=cn["number"])
        await db.credit_notes.update_one({"id": cn["id"]}, {"$set": {"gl_status": "posted" if je else "not_required",
                                                                  "journal_entry_id": (je or {}).get("id", "")}})
        # 5) Refund kas.
        if plan["cash_total"] > 0:
            from services import cash_ledger
            await cash_ledger.record_return_cash(
                direction="out", amount=plan["cash_total"], account_code=plan["refund_account_code"] or "1-1100",
                category="Refund Retur Jual", description=f"Refund tunai retur {label} → {ret.get('customer_name', '')}",
                entity_id=ret.get("entity_id", ""), ref_type="sales_return", ref_id=ref_id,
                journal_entry_id=(je or {}).get("id", ""), created_by=actor.get("name", ""))
        # 6) Saldo pelanggan.
        if plan["saldo_total"] > 0:
            from services import store_credit_service as _sc
            await _sc.issue(customer_id=ret.get("customer_id"), entity_id=ret.get("entity_id", ""),
                            amount=plan["saldo_total"], ref_type="sales_return", ref_id=ref_id, ref_number=cn["number"],
                            actor=actor.get("name", ""), je_id=(je or {}).get("id", ""),
                            customer_name=ret.get("customer_name", ""))
    # 7) Tandai roll, status retur, tukar barang, diskon terpakai.
    ret = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    outcomes = dict(ret.get("roll_outcomes") or {})
    for r in plan["rolls"]:
        outcomes[r["roll_id"]] = {"settlement_id": settlement_id, "seq": seq, "outcome": r["outcome"],
                                  "outcome_label": r["outcome_label"], "credit_amount": r["credit_amount"],
                                  "qty_stock": r["qty_stock"], "qty_cut": r["qty_cut"], "qty_back": r["qty_back"],
                                  "back_pending": r["qty_back"] > 0 and r["outcome"] in ("discount", "reject")}
    final, outcome = _final_status(ret, outcomes)
    cns = [c async for c in db.credit_notes.find({"return_id": return_id, "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1, "gross_amount": 1})]
    upd: Dict[str, Any] = {
        "roll_outcomes": outcomes, "settlements.$[ev].status": "done", "settlements.$[ev].done_at": now,
        "settlements.$[ev].credit_note_id": (cn or {}).get("id", ""), "settlements.$[ev].credit_note_number": (cn or {}).get("number", ""),
        "credit_note_ids": [c["id"] for c in cns], "credit_note_number": ", ".join(c["number"] for c in cns),
        "credit_note_amount": round(sum(float(c.get("gross_amount") or 0) for c in cns), 2),
        "credit_note_id": (cn or {}).get("id") or ret.get("credit_note_id", ""), "updated_at": now}
    if any(r["outcome"] == "exchange" for r in plan["rolls"]):
        # Pengganti tetap berhak walau nilai tukar habis memotong tagihan SO asal yang belum lunas (saldo 0 → ditagih penuh).
        upd["exchange_pending"] = True
        upd["exchange_credit_open"] = round(float(ret.get("exchange_credit_open") or 0) + plan["exchange_credit"], 2)
    used = {r["product_id"] for r in plan["rolls"] if r["outcome"] == "discount"}
    comp = ret.get("compensation") or {}
    if used and comp.get("lines"):
        upd["compensation.lines"] = [{**x, "used_by": settlement_id} if x.get("kind") == "discount" and x.get("product_id") in used
                                     and not x.get("used_by") else x for x in comp["lines"]]
    if final:
        upd.update({"status": final, "outcome": outcome, "settled_by": actor.get("name", ""), "settled_at": now,
                    "settlement": {"outcome": outcome, "mode": "per_roll", "settled_at": now, "settled_by": actor.get("name", ""),
                                   "events": seq, "gross_amount": upd["credit_note_amount"]}})
        if final == st.REJECTED:
            upd.update({"rejected_by": actor.get("name", ""), "rejected_at": now,
                        "reject_reason": "Semua roll ditolak saat penyelesaian"})
    await db.sales_returns.update_one({"id": return_id}, {**saga.finish_set(upd)},
                                      array_filters=[{"ev.id": settlement_id}])
    if final and ret.get("status") == "approved":
        from services import inspection_service as ins
        await ins.close_unneeded_return_spk(return_id, actor, "Diselesaikan tanpa QC fisik (diskon dari foto/video / klaim ditolak)")
    return await db.sales_returns.find_one({"id": return_id}, {"_id": 0})


async def reverse_all(ret: Dict[str, Any], actor: str, reason: str) -> Dict[str, Any]:
    """Koreksi penyelesaian per roll: balik SEMUA penyelesaian (jurnal, kas, saldo, tagihan SO, Nota Kredit, roll stok).
    Retur yang sudah selesai → batal (seperti jalur lama); yang baru sebagian → kembali bisa diputus."""
    from services import atomic_claim as saga
    from services import return_identity_service as _rid
    from services import store_credit_service as _sc
    from services.roll_service import rebuild_balance
    rid = ret["id"]
    if ret.get("quarantine_released"):
        raise RollSettlementError("Roll retur sudah dilepas dari karantina — koreksi otomatis tidak aman.")
    rolls = await db.inventory_rolls.find({"return_id": rid, "origin_type": "return"}, {"_id": 0}).to_list(500)
    for r in rolls:
        lbl = r.get("roll_no") or r.get("id")
        if r.get("status") != "quarantine":
            raise RollSettlementError(f"Roll {lbl} sudah tidak di karantina (status '{r.get('status')}').")
        if r.get("committed_to") or r.get("reserved_ref") or r.get("earmarked_for"):
            raise RollSettlementError(f"Roll {lbl} sudah dipesan/dikomit ke transaksi lain.")
    events = [e for e in ret.get("settlements") or [] if e.get("status") == "done"]
    for e in events:
        info = await db.store_credit_ledger.find_one({"type": "issue", "ref_type": "sales_return", "ref_id": f"{rid}:{e['id']}",
                                                     "status": {"$ne": "void"}}, {"_id": 0})
        if info:
            bal = await _sc.balance(info["customer_id"], info.get("entity_id", ""))
            if bal + 0.01 < float(info.get("amount") or 0):
                raise RollSettlementError("Saldo dari retur ini sudah dipakai (mis. pesanan pengganti). Batalkan pemakaiannya dulu.")
    await saga.claim("sales_returns", rid, "sales_return_roll_reverse", precondition={"reversed": {"$ne": True}}, actor=actor)
    now = now_iso()
    rev_jes: List[Dict[str, Any]] = []
    for e in events:
        ref_id = f"{rid}:{e['id']}"
        rev_jes += await gl_service.reverse_document("sales_return", ref_id, reason=reason or "Koreksi penyelesaian retur", actor_name=actor)
        await db.cash_transactions.update_many({"ref_type": "sales_return", "ref_id": ref_id, "status": {"$ne": "void"}},
                                               {"$set": {"status": "void", "voided_by": actor, "void_reason": reason, "updated_at": now}})
        await _sc.void_issue_entry(return_id=ref_id, reason=reason, actor=actor)
    async for cn in db.credit_notes.find({"return_id": rid, "settlement_id": {"$exists": True}, "status": {"$ne": "void"}}, {"_id": 0}):
        if float(cn.get("ar_applied") or 0) > 0:
            from services import ar_receipt_service as _ar
            await _ar.unapply_for_case(ret["order_id"], float(cn["ar_applied"]), cn["id"], cn["number"],
                                       method="credit_note_void", note="nota kredit dibatalkan")
        await db.credit_notes.update_one({"id": cn["id"]}, {"$set": {"status": "void", "reversed": True, "reversed_at": now,
                                                                  "reversal_reason": reason, "updated_at": now}})
    combos = set()
    for r in rolls:
        if r.get("returned_identity"):
            await _rid.restore_identity_roll(r, now)
        else:
            await db.inventory_rolls.delete_one({"id": r["id"]})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r.get("product_id"), "warehouse_id": r.get("warehouse_id"),
            "owner_entity_id": r.get("owner_entity_id"), "type": "return_reversal_out", "movement_type": "return_reversal_out",
            "direction": "out", "quantity": round(float(r.get("length_remaining", r.get("length", 0)) or 0), 2),
            "unit": r.get("unit") or "", "roll_id": r["id"], "qty_rolls": 1, "ref_type": "sales_return", "ref_id": rid,
            "notes": f"Koreksi penyelesaian retur {ret.get('number', rid)} — roll {r.get('roll_no') or r['id']} dibatalkan",
            "source_document": rid, "timestamp": now})
        if r.get("product_id") and r.get("warehouse_id"):
            combos.add((r["product_id"], r["warehouse_id"], r.get("owner_entity_id", "")))
    for (pid, wid, eid) in combos:
        await rebuild_balance(pid, wid, eid)
    fully = ret.get("status") in st.SETTLED_STATES
    comp = ret.get("compensation") or {}
    upd: Dict[str, Any] = {"roll_outcomes": {}, "exchange_pending": False, "exchange_credit_open": 0.0,
                           "credit_note_ids": [], "credit_note_number": "", "credit_note_amount": 0.0, "credit_note_id": "",
                           "settlements_reversed": (ret.get("settlements_reversed") or [])
                           + [{**e, "reversed_at": now, "reversed_by": actor} for e in events],
                           "settlements": [], "reversal_je_ids": [j.get("id") for j in rev_jes], "updated_at": now}
    if comp.get("lines"):
        upd["compensation.lines"] = [{k: v for k, v in x.items() if k != "used_by"} for x in comp["lines"]]
    if fully:
        st.assert_transition(ret["status"], st.CANCELLED)
        upd.update({"status": st.CANCELLED, "reversed": True, "reversed_by": actor, "reversed_at": now, "reversal_reason": reason})
    await db.sales_returns.update_one({"id": rid}, saga.finish_set(upd))
    out = await db.sales_returns.find_one({"id": rid}, {"_id": 0})
    out["_reversal_summary"] = {"reversal_jes": len(rev_jes), "rolls_removed": len(rolls), "outcome": ret.get("outcome", ""),
                                "settlements": len(events)}
    return out


async def back_shipment(ret: Dict[str, Any], roll_ids: List[str], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Surat jalan pengembalian roll ke pelanggan untuk outcome Diskon / Tolak klaim yang barangnya sempat diterima
    gudang. Roll tidak pernah kembali ke persediaan (milik pelanggan) → tanpa jurnal."""
    from services.shipment_service import _next_shipment_no
    outcomes = ret.get("roll_outcomes") or {}
    pend = [r for r in roll_ids if (outcomes.get(r) or {}).get("back_pending")]
    if not pend:
        raise RollSettlementError("Tidak ada roll Diskon/Tolak yang menunggu dikirim balik.")
    entity = ret.get("entity_id", "")
    no = await _next_shipment_no(entity)
    docs = {r["id"]: r async for r in db.inventory_rolls.find({"id": {"$in": pend}}, {"_id": 0, "id": 1, "roll_no": 1, "unit": 1})}
    rolls = [{"roll_id": r, "roll_no": (docs.get(r) or {}).get("roll_no", ""), "qty": outcomes[r]["qty_back"],
              "unit": (docs.get(r) or {}).get("unit", "")} for r in pend]
    doc = {"id": new_id("shp"), "shipment_no": no, "kind": "return_back", "entity_id": entity, "order_id": "",
           "ref_order_id": ret.get("order_id", ""), "ref_order_number": ret.get("order_number", ""), "return_id": ret["id"],
           "return_number": ret.get("number", ""), "customer_id": ret.get("customer_id", ""),
           "customer_name": ret.get("customer_name", ""), "rolls": rolls, "quantity": round(sum(x["qty"] for x in rolls), 2),
           "status": "dispatched", "created_by": actor.get("name", ""), "created_at": now_iso(), "logistics_id": ""}
    await db.shipments.insert_one(dict(doc))
    upd = {f"roll_outcomes.{r}.back_pending": False for r in pend}
    upd.update({f"roll_outcomes.{r}.back_shipment_no": no for r in pend})
    upd.update({f"roll_locations.{r}.stage": "returned_to_customer" for r in pend})
    upd["updated_at"] = now_iso()
    await db.sales_returns.update_one({"id": ret["id"]}, {"$set": upd})
    doc.pop("_id", None)
    return doc
