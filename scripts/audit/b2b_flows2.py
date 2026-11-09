"""B2b — skenario SAMPEL, potong sampel vs reservasi SO, transfer keluar, perbaikan (stack audit, DB salinan)."""
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/scripts/audit")
from b2b_lib import DB, api, diff, free_rolls, save, show  # noqa: E402
import b2b_flows as F  # noqa: E402
from b2b_flows import E, WH, PID, WHJ, RESULTS, mk_so, to_confirmed, so_doc, roll_no, verdict, task_of, state, step  # noqa: E402,F401

P2 = "prod_9565dac7dcfa"     # KSC @ Jakarta, kg
GATE_WH = "wh_adc8726d019e"  # RCM-WOVEN (gedung simpan, physical_gate)


def roll(rid, f=None):
    p = {"_id": 0, "id": 1, "status": 1, "length_remaining": 1, "length_reserved": 1, "length_reservations": 1,
         "warehouse_id": 1, "reserved_ref": 1, "is_remnant": 1, "transfer_prior_status": 1, "transfer_ref": 1,
         "bin_id": 1, "is_sample_cut": 1, "cut": 1, "rfid_tag_id": 1}
    return DB.inventory_rolls.find_one({"id": rid}, f or p)


def s_sample():
    """SO sampel gratis → confirm → tugas sample_cut → potong sampel MELANGGAR reservasi potong SO lain (POT-01)
    → potong SO 409; batal sampel sesudah potong → serah-terima Cutting tetap jalan (SMP-01)."""
    R = free_rolls(P2, E, WH, n=1, min_len=15)[0]
    L = R["length_remaining"]
    take = round(L - 1.5, 2)
    _, _, A = mk_so([(R["id"], take)], pid=P2, item_extra={"target_quantity": take, "rounding_choice": "exact_cut"})
    print("   roll R", R["id"], "panjang", L, "dipesan SO-A", roll(R["id"])["length_reserved"])
    body = {"order_type": "sample", "sample_billing": "free"}
    _, js, S = mk_so([], purchase_mode="qty", qty=2, pid=P2, extra=body,
                     item_extra={"is_sample": True, "sample_kind": "standard", "unit": "kg"})
    print("   SO sampel", S, so_doc(S) and so_doc(S)["status"])
    step("konfirmasi sampel", S, lambda: api("POST", f"/sample-orders/{S}/confirm", ent=E, note="confirm sampel"))
    st = task_of(S, sub="sample")
    print("   tugas sampel:", [(t["id"], t["status"], t.get("warehouse_id"), t.get("quantity")) for t in st])
    t = st[0]["id"]
    vis_hp = api("GET", "/wms/tasks", who=WHJ, ent=E, params={"flow_type": "outbound"}, quiet=True)[1]
    vis_desk = api("GET", "/outbound/tasks", who=WHJ, ent=E, quiet=True)[1]
    in_hp = any((x.get("id") == t) for x in (vis_hp if isinstance(vis_hp, list) else vis_hp.get("tasks", vis_hp.get("items", []))))
    in_desk = any((x.get("id") == t) for x in (vis_desk if isinstance(vis_desk, list) else vis_desk.get("tasks", vis_desk.get("items", []))))
    print(f"   tugas sampel tampil di /wms/tasks={in_hp} · /outbound/tasks={in_desk}")
    RESULTS["SMP-VIS"] = {"wms_tasks": in_hp, "outbound_tasks": in_desk}
    step("potong sampel 2 dari roll yang dipesan SO-A", S, lambda: api(
        "POST", f"/outbound/tasks/{t}/cut-sample", who=WHJ, ent=E,
        body={"roll_id": R["id"], "epc": "", "actual_length": 2, "reason": "uji B2b roll dipesan SO lain"}), [R["id"]])
    rr = roll(R["id"])
    print("   R sesudah potong sampel:", {k: rr.get(k) for k in ("length_remaining", "length_reserved", "status", "is_remnant")})
    bal = DB.inventory_balances.find_one({"product_id": P2, "warehouse_id": WH, "owner_entity_id": E},
                                         {"_id": 0, "available_qty": 1, "reserved_qty": 1, "on_hand_qty": 1})
    rsv = [x for x in rr.get("length_reservations") or [] if (x.get("ref") or {}).get("id") == A][0]
    c, js = api("POST", f"/inventory/rolls/{R['id']}/reservations/{rsv['id']}/cut", who=WHJ, ent=E,
                body={"actual_length": rsv["qty"], "waste": 0, "note": "uji B2b"}, note="potong SO-A sesudah sampel")
    verdict("POT-01", rr["length_remaining"] < (rr.get("length_reserved") or 0) and c >= 400,
            f"sisa {rr['length_remaining']} < dipesan {rr.get('length_reserved')}; potong SO-A → {c} {str(js)[:140]}; saldo {bal}")
    # SMP-01: batal SO sampel sesudah dipotong lalu serah-terima Cutting
    step("batal SO sampel", S, lambda: api("POST", f"/sales-orders/{S}/cancel", ent=E, body={"reason": "uji B2b batal sampel"}))
    kid = DB.inventory_rolls.find_one({"parent_roll_id": R["id"], "is_sample_cut": True}, {"_id": 0, "id": 1, "status": 1,
                                                                                         "warehouse_id": 1, "reserved_ref": 1})
    tk = DB.wms_tasks.find_one({"id": t}, {"_id": 0, "status": 1})
    c2, js2 = api("POST", f"/cutting/tasks/{t}/receive", ent=E, body={"to_warehouse_id": "wh_bandung"},
                  note="serah-terima Cutting tugas batal")
    kid2 = roll(kid["id"]) if kid else None
    verdict("SMP-01", c2 < 400, f"tugas {tk}; anak sebelum {kid}; serah-terima {c2} {str(js2)[:120]}; anak sesudah "
            f"{ {k: (kid2 or {}).get(k) for k in ('status', 'warehouse_id', 'bin_id')} }")
    RESULTS["SMP_SO"] = {"A": A, "S": S, "R": R["id"]}


def s_sord():
    """Pesanan sampel berbayar: confirm sebelum bayar (409), approve-payment oleh sales (403) & finance, confirm, cancel."""
    body = {"order_type": "sample", "sample_billing": "paid"}
    _, js, S = mk_so([], purchase_mode="qty", qty=2, pid=P2, extra=body,
                     item_extra={"is_sample": True, "sample_kind": "standard", "unit": "kg", "sample_price": 50000})
    d = DB.sales_orders.find_one({"id": S}, {"_id": 0, "status": 1, "sample_payment_status": 1, "pending_approvals": 1})
    print("   SORD", S, d["status"], d.get("sample_payment_status"), [(p.get("type"), p.get("status")) for p in d.get("pending_approvals") or []])
    c1, _ = api("POST", f"/sample-orders/{S}/confirm", ent=E, note="confirm sebelum bayar")
    c2, _ = api("POST", f"/sample-orders/{S}/approve-payment", who="sales@kainnusantara.id", ent=E,
                body={"note": "uji B2b"}, note="approve-payment oleh sales")
    c3, _ = api("POST", f"/sample-orders/{S}/approve-payment", who="finance@kainnusantara.id", ent=E,
                body={"note": "uji B2b bayar"}, note="approve-payment oleh finance")
    c3b, _ = api("POST", f"/sample-orders/{S}/approve-payment", who="finance@kainnusantara.id", ent=E,
                 body={"note": "uji B2b bayar ulang"}, note="approve-payment ulang")
    c4, _ = api("POST", f"/sample-orders/{S}/confirm", ent=E, note="confirm sesudah bayar")
    n = DB.wms_tasks.count_documents({"order_id": S})
    c5, js5 = api("POST", f"/sample-orders/{S}/cancel", ent=E, body={"note": "uji B2b batal"}, note="batal lewat sample-orders")
    c6, js6 = api("POST", f"/sales-orders/{S}/cancel", ent=E, body={"reason": "uji B2b batal sampel"}, note="batal lewat SO")
    d2 = DB.sales_orders.find_one({"id": S}, {"_id": 0, "status": 1, "sample_payment_status": 1})
    tk = [t["status"] for t in DB.wms_tasks.find({"order_id": S}, {"status": 1})]
    verdict("SORD", c1 >= 400 and c2 == 403 and c3 < 400 and c4 < 400,
            f"confirm-sebelum-bayar {c1}, sales {c2}, finance {c3}/{c3b}, confirm {c4} (tugas {n}), cancel sampel {c5}, "
            f"cancel SO {c6}; akhir {d2}, tugas {tk}")


def _mk_transfer(rids, dest=GATE_WH, so_id=None, who="admin@kainnusantara.id"):
    pid = DB.inventory_rolls.find_one({"id": rids[0]}, {"product_id": 1})["product_id"]
    body = {"source_warehouse_id": WH, "dest_warehouse_id": dest, "owner_entity_id": E, "notes": "AUDIT-B2B-TRF",
            "items": [{"product_id": pid, "qty": 0, "roll_ids": rids}]}
    if so_id:
        body["sales_order_id"] = so_id
    c, js = api("POST", "/transfers", who=who, ent=E, body=body, note="buat transfer")
    return js.get("id") if isinstance(js, dict) else None


def _xstate(T, rids):
    t = DB.warehouse_transfers.find_one({"id": T}, {"_id": 0, "id": 1, "status": 1, "transfer_status": 1,
                                                   "completion_basis": 1, "exceptions": 1, "gate_exits": 1})
    return {"t": {T: t}, "rolls": {r: roll(r) for r in rids},
            "c": {"c": {"mov": DB.inventory_movements.count_documents({"source_document": {"$regex": T}}),
                        "sess": DB.rfid_v2_doc_sessions.count_documents({"doc_id": T}) if "rfid_v2_doc_sessions" in DB.list_collection_names() else -1}}}


def _xstep(label, T, rids, fn):
    a = _xstate(T, rids)
    r = fn()
    b = _xstate(T, rids)
    show(diff(a, b), label)
    return r


def _dispatch_transfer(T, rids):
    _xstep("setujui", T, rids, lambda: api("POST", f"/transfers/{T}/approve", ent=E, body={"approved_by": "uji B2b"}))
    for s in ("picking", "staging", "dispatched"):
        _xstep(f"status {s}", T, rids, lambda s=s: api("POST", f"/transfers/{T}/status", ent=E, body={"status": s}))


def s_transfer():
    """Transfer Jakarta → RCM-WOVEN: buat → setujui → kirim → terima sebagian (1 diterima, 1 rusak) → sisa → selesai;
    roll transit dialokasikan SO? (K-GDG-09); transfer 0 roll diterima → completed (TRF-02)."""
    rs = free_rolls(P2, E, WH, n=5, min_len=10)
    rids = [r["id"] for r in rs[:3]]
    T = _mk_transfer(rids)
    print("   transfer", T)
    _dispatch_transfer(T, rids)
    # K-GDG-09: roll in_transit_transfer bisa dialokasikan SO?
    c, js = api("POST", "/sales-orders/preview-allocation", ent=E, body={"items": [{"product_id": P2, "quantity": 5, "unit": "kg"}],
                                                                         "entity_id": E, "customer_id": "cust_butik_bali"})
    picked = str(js)
    hit = [r for r in rids if r in picked]
    _, js2, S = mk_so([(rids[0], 0)], pid=P2)
    verdict("K-GDG-09", not hit and not S, f"pratinjau alokasi memakai roll transit: {hit}; SO roll transit eksplisit → "
            f"{'SO ' + S if S else str(js2)[:160]}")
    _xstep("terima sebagian (1 ok, 1 rusak)", T, rids, lambda: api("POST", f"/transfers/{T}/receive", ent=E, body={
        "lines": [{"roll_id": rids[0], "outcome": "received"}, {"roll_id": rids[1], "outcome": "damaged", "note": "sobek uji B2b"}],
        "note": "uji"}))
    _xstep("terima ulang roll sama", T, rids, lambda: api("POST", f"/transfers/{T}/receive", ent=E, body={
        "lines": [{"roll_id": rids[0], "outcome": "received"}], "note": "ulang"}))
    _xstep("terima sisa", T, rids, lambda: api("POST", f"/transfers/{T}/receive", ent=E, body={
        "lines": [{"code": roll_no(rids[2]), "outcome": "received"}], "note": "sisa"}))
    t = DB.warehouse_transfers.find_one({"id": T}, {"_id": 0, "status": 1, "transfer_status": 1, "completion_basis": 1})
    verdict("TRF-HAPPY", t.get("status") == "completed" or t.get("transfer_status") == "completed", f"{t}")
    # TRF-02: 2 roll → kirim → exception return_to_source keduanya
    r2 = [r["id"] for r in rs[3:5]]
    T2 = _mk_transfer(r2)
    _dispatch_transfer(T2, r2)
    for r in r2:
        c, js = api("POST", f"/transfers/{T2}/exceptions", ent=E, body={"kind": "other", "roll_id": r, "reason": "uji B2b kembali"})
        exc = (js or {}).get("exception", js) if isinstance(js, dict) else {}
        eid = exc.get("id") if isinstance(exc, dict) else None
        if not eid:
            doc = DB.warehouse_transfers.find_one({"id": T2}, {"exceptions": 1})
            eid = [e["id"] for e in doc.get("exceptions") or [] if e.get("roll_id") == r][-1]
        _xstep(f"kembalikan ke asal {r}", T2, r2, lambda eid=eid: api("POST", f"/transfers/{T2}/exceptions/{eid}/resolve", ent=E,
                                                                      body={"action": "return_to_source", "reason": "uji B2b kembali"}))
    t2 = DB.warehouse_transfers.find_one({"id": T2}, {"_id": 0, "status": 1, "transfer_status": 1, "completion_basis": 1})
    verdict("TRF-02", "completed" in (t2.get("status"), t2.get("transfer_status")), f"transfer 0 roll diterima: {t2}")
    RESULTS["TRF"] = {"T": T, "T2": T2}


def s_transfer_cancel():
    """Batal transfer saat dispatched: roll di jalan langsung available di asal; sesi gate tidak ditutup (TRF-04)."""
    rs = free_rolls(P2, E, WH, n=2, min_len=10)
    rids = [r["id"] for r in rs]
    T = _mk_transfer(rids)
    _dispatch_transfer(T, rids)
    _xstep("batal saat dispatched", T, rids, lambda: api("DELETE", f"/transfers/{T}", ent=E, params={"reason": "uji B2b batal transit"}))
    st = [(roll(r)["status"], roll(r)["warehouse_id"][-7:], roll(r).get("transfer_prior_status")) for r in rids]
    verdict("TRF-04", all(s[0] == "available" for s in st), f"roll sesudah batal di jalan: {st}")


def s_repair():
    """Perbaikan internal: buat → kirim → terima (grade B, qty susut) → ulang terima (idempoten?) ; batal sesudah kirim."""
    rs = free_rolls(P2, E, WH, n=3, min_len=5)
    rid = rs[0]["id"]
    c, ro = api("POST", "/repair-orders", ent=E, body={"kind": "perbaikan", "partner_type": "internal", "roll_ids": [rid],
                                                     "cost": {"basis": "lumpsum", "rate": 10000}, "notes": "uji B2b"}, note="buat RO")
    RO = ro.get("id") if isinstance(ro, dict) else None
    r0 = roll(rid)
    c, js = api("POST", f"/repair-orders/{RO}/send", ent=E, body={}, note="kirim RO")
    r1 = roll(rid)
    j0 = DB.journal_entries.count_documents({"source_id": RO})
    L = r1.get("length_remaining") or r0["length_remaining"]
    c2, js2 = api("POST", f"/repair-orders/{RO}/receive", ent=E, body={"lines": [{"roll_id": rid, "qty_out": round(L - 0.5, 2), "grade": "B"}],
                                                                     "actual_cost": 10000}, note="terima RO")
    r2 = roll(rid, {"_id": 0, "status": 1, "length_remaining": 1, "grade": 1, "warehouse_id": 1})
    j1 = DB.journal_entries.count_documents({"source_id": RO})
    c3, js3 = api("POST", f"/repair-orders/{RO}/receive", ent=E, body={"lines": [{"roll_id": rid, "qty_out": round(L - 0.5, 2), "grade": "B"}],
                                                                     "actual_cost": 10000}, note="terima RO ULANG")
    j2 = DB.journal_entries.count_documents({"source_id": RO})
    d = DB.repair_orders.find_one({"id": RO}, {"_id": 0, "status": 1, "gate_exits": 1})
    print(f"   roll: {r0['status']} → kirim {r1['status']} → terima {r2}; jurnal {j0}→{j1}→{j2}; RO {d}")
    verdict("REP-FLOW", c2 < 400 and c3 >= 400 and j2 == j1, f"terima {c2}, ulang {c3} {str(js3)[:120]}; jurnal {j0}/{j1}/{j2}")
    # batal sesudah kirim
    rid2 = rs[1]["id"]
    c, ro2 = api("POST", "/repair-orders", ent=E, body={"kind": "perbaikan", "partner_type": "internal", "roll_ids": [rid2],
                                                      "cost": {"basis": "lumpsum", "rate": 0}, "notes": "uji B2b batal"})
    RO2 = ro2.get("id")
    api("POST", f"/repair-orders/{RO2}/send", ent=E, body={})
    c4, js4 = api("POST", f"/repair-orders/{RO2}/cancel", ent=E, body={"reason": "uji B2b batal sesudah kirim"}, note="batal RO terkirim")
    print("   batal sesudah kirim:", c4, str(js4)[:160], "roll", roll(rid2, {"_id": 0, "status": 1, "warehouse_id": 1}))
    RESULTS["REP"] = {"RO": RO, "RO2": RO2, "batal_terkirim": c4}


SCN = {k[2:]: v for k, v in globals().items() if k.startswith("s_")}

if __name__ == "__main__":
    for n in sys.argv[1:]:
        print(f"\n===== {n} =====  {datetime.now(timezone.utc).isoformat()}")
        try:
            SCN[n]()
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            RESULTS[n + "_ERR"] = repr(ex)
    print("\nHASIL:", RESULTS)
    save("flows2_" + "_".join(sys.argv[1:]), RESULTS)
