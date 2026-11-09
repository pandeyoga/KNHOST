"""B2b — skenario alur keluar (SO → alokasi → ambil → cek muat → kirim → logistik → POD) + cabang & probe anomali.

Jalankan di kontainer stack audit (DB salinan): python /app/scripts/audit/b2b_flows.py <skenario> [...]
Setiap langkah: panggilan API (dicatat) + potret DB sebelum/sesudah (SO, roll, tugas, SJ, logistik, hitungan
mutasi/jurnal/doc_refs/audit/notifikasi). Keluaran: stdout ringkas + /tmp/b2b/<skenario>.json
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/scripts/audit")
from b2b_lib import DB, LOG, api, diff, free_rolls, save, show  # noqa: E402

E = "ent_ksc"
WH = "wh_jakarta"
PID = "prod_9539d954dbd6"   # KSC @ Jakarta, kg, ±59 roll tersedia
CUST, ADDR = "cust_toko_kain", "addr_001"
ADM = "admin@kainnusantara.id"
WHJ = "warehouse@kainnusantara.id"
WHADM = "wh.admin@kainnusantara.id"
RESULTS = {}
_CUST_OK = {}


def so_doc(so_id):
    return DB.sales_orders.find_one({"id": so_id}, {"_id": 0, "id": 1, "order_no": 1, "status": 1, "allocations": 1,
                                                   "items.product_id": 1, "items.quantity": 1, "items.reserved_qty": 1,
                                                   "items.backorder_qty": 1, "backorders": 1, "has_backorder": 1,
                                                   "fulfillment": 1, "saga_lock": 1, "loading_checks": 1,
                                                   "loading_check": 1, "verification.status": 1, "stage": 1,
                                                   "sub_status": 1, "pending_approvals": 1})


def state(so_id, roll_ids=()):
    so = so_doc(so_id) or {}
    rid = set(roll_ids)
    for a in so.get("allocations") or []:
        for r in a.get("rolls") or []:
            rid.add(r.get("roll_id") if isinstance(r, dict) else r)
    q = {"$or": [{"id": {"$in": list(rid)}}, {"reserved_ref.id": so_id}, {"parent_roll_id": {"$in": list(rid)}},
                 {"length_reservations.ref.id": so_id}]}
    from b2b_lib import ROLL_F
    rolls = {r["id"]: r for r in DB.inventory_rolls.find(q, ROLL_F)}
    tasks = {t["id"]: t for t in DB.wms_tasks.find({"order_id": so_id}, {"_id": 0, "id": 1, "status": 1, "quantity": 1,
                                                                        "picked_qty": 1, "shipped_qty": 1,
                                                                        "escalation.status": 1, "task_subtype": 1,
                                                                        "warehouse_id": 1, "cancel_reason": 1})}
    ships = {s["id"]: s for s in DB.shipments.find({"order_id": so_id}, {"_id": 0, "id": 1, "shipment_no": 1, "status": 1,
                                                                       "logistics_status": 1, "gl_status": 1,
                                                                       "rolls.roll_id": 1, "quantity": 1})}
    sh_ids = list(ships)
    dels = {d["id"]: d for d in DB.logistics_deliveries.find({"shipment_ids": {"$in": sh_ids}} if sh_ids else {"id": "-"},
                                                             {"_id": 0, "id": 1, "status": 1, "delivery_no": 1})}
    ref_ids = [so_id] + list(tasks) + sh_ids
    rid_all = list(rolls)
    mv = {}
    for m in DB.inventory_movements.find({"$or": [{"source_document": {"$in": ref_ids}},
                                                  {"roll_id": {"$in": rid_all}}]}, {"movement_type": 1}):
        mv[m.get("movement_type")] = mv.get(m.get("movement_type"), 0) + 1
    dr = sum(len((d or {}).get("doc_refs") or []) for d in
             list(DB.sales_orders.find({"id": so_id}, {"doc_refs": 1})) +
             list(DB.wms_tasks.find({"order_id": so_id}, {"doc_refs": 1})) +
             list(DB.shipments.find({"order_id": so_id}, {"doc_refs": 1})))
    cnt = {
        "mov": mv,
        "jrn": DB.journal_entries.count_documents({"$or": [{"source_id": {"$in": ref_ids}}, {"ref.order_id": so_id}]}),
        "doc_refs": dr,
        "audit": DB.audit_logs.count_documents({"entity_id": {"$in": ref_ids}}),
        "notif": DB.notifications.count_documents({"$or": [{"ref.id": {"$in": ref_ids}}, {"link": {"$regex": so_id}}]}),
        "rsv_sessions": DB.rfid_verify_sessions.count_documents({"order_id": so_id}),
        "status_history": len((DB.sales_orders.find_one({"id": so_id}, {"status_history": 1}) or {}).get("status_history") or []),
    }
    return {"so": {so_id: so}, "rolls": rolls, "tasks": tasks, "ships": ships, "dels": dels, "cnt": {"c": cnt}}


def step(label, so_id, fn, roll_ids=()):
    a = state(so_id, roll_ids) if so_id else None
    res = fn()
    b = state(so_id, roll_ids) if so_id else None
    if so_id:
        d = diff(a, b, keys=None)
        show(d, label)
    return res


def mk_so(rolls, who=ADM, ent=E, purchase_mode="roll", qty=None, extra=None, item_extra=None, pid=PID):
    if purchase_mode == "roll":
        item = {"product_id": pid, "quantity": round(sum(t for _, t in rolls), 2), "unit": "kg", "purchase_mode": "roll",
                "roll_lines": [{"roll_id": r, "take_qty": t} for r, t in rolls]}
    else:
        item = {"product_id": pid, "quantity": qty, "unit": "kg"}
    item.update(item_extra or {})
    cands = _CUST_OK.get(ent) or [(c["id"], (c.get("addresses") or [{}])[0].get("id"))
                                   for c in DB.customers.find({"entity_id": ent, "status": "active"},
                                                              {"_id": 0, "id": 1, "addresses.id": 1}).limit(40)]
    for cid, aid in cands:
        body = {"customer_id": cid, "shipping_address_id": aid, "entity_id": ent, "items": [item],
                "confirm_mixed_lot": True, "payment_term_code": "NET30", "fulfillment_method": "kirim"}
        body.update(extra or {})
        c, js = api("POST", "/sales-orders", who=who, ent=ent, body=body, note=f"buat SO ({cid})")
        if c == 409 and isinstance(js, dict) and isinstance(js.get("detail"), dict) \
                and js["detail"].get("code") == "CREDIT_BLOCKED":
            continue
        if c < 400:
            _CUST_OK[ent] = [(cid, aid)]
        break
    so_id = js.get("id") if isinstance(js, dict) else None
    if so_id:
        print("   SO", so_id, js.get("order_no"), js.get("status"))
    return c, js, so_id


def to_confirmed(so_id, ent=E):
    s = so_doc(so_id)["status"]
    api("POST", f"/sales-orders/{so_id}/verify", ent=ent, body={"note": "audit B2b"}, note="verifikasi admin")
    if s in ("reserved", "waiting_stock"):
        api("POST", f"/sales-orders/{so_id}/submit-for-approval", ent=ent, note="ajukan")
    if so_doc(so_id)["status"] == "waiting_approval":
        api("POST", f"/sales-orders/{so_id}/approve", ent=ent, note="setujui")
    c, js = api("POST", f"/sales-orders/{so_id}/confirm", ent=ent, note="konfirmasi")
    print("   status SO:", so_doc(so_id)["status"])
    return c


def task_of(so_id, sub=None):
    q = {"order_id": so_id, "flow_type": "outbound"}
    if sub == "sample":
        q["task_subtype"] = "sample_cut"
    elif sub is None:
        q["task_subtype"] = {"$ne": "sample_cut"}
    return list(DB.wms_tasks.find(q, {"_id": 0}))


def roll_no(rid):
    return DB.inventory_rolls.find_one({"id": rid}, {"roll_no": 1})["roll_no"]


def pick(t, rid, qty, who=WHJ, ent=E, note="scan-pick"):
    return api("POST", f"/outbound/tasks/{t}/scan-pick", who=who, ent=ent,
               params={"actual_qty": qty, "roll_id": roll_no(rid) if rid else ""}, note=note)


def loading_override(so_id, ent=E, wh=WH):
    return api("POST", f"/outbound/so/{so_id}/loading-check/override", ent=ent,
               body={"reason": "uji audit B2b override", "warehouse_id": wh}, note="cek muat override")


def verdict(key, ok, txt):
    RESULTS[key] = {"terbukti": ok, "ket": txt}
    print(f"  >>> {key}: {'TERBUKTI' if ok else 'tidak terbukti'} — {txt}")


# ---------------------------------------------------------------- skenario
def s_happy():
    """Alur lurus: SO 2 roll utuh → setujui → konfirmasi → ambil (pindai roll) → cek muat → kirim → logistik → POD."""
    fr = free_rolls(PID, E, WH, n=2, min_len=10)
    rl = [(r["id"], r["length_remaining"]) for r in fr]
    c, js, so = mk_so(rl)
    step("SO dibuat", None, lambda: None)
    step("ke confirmed", so, lambda: to_confirmed(so), [r for r, _ in rl])
    tasks = task_of(so)
    print("   tugas:", [(t["id"], t["status"], t["quantity"]) for t in tasks])
    t = tasks[0]["id"]
    step("pick-list", so, lambda: api("GET", f"/outbound/tasks/{t}/pick-list", who=WHJ, ent=E))
    for r, ln in rl:
        step(f"scan-pick {r}", so, lambda r=r, ln=ln: pick(t, r, ln), [x for x, _ in rl])
    lc_session_flow(so, [r for r, _ in rl], refresh_probe=True)
    _ship_and_deliver(so, t, rl)
    return so


def lc_session_flow(so, rids, refresh_probe=False, wh=WH):
    """Cek muat. refresh_probe: mulai sesi DULU lalu tulis tag (simulasi) → sesi tidak menyegarkan expected."""
    if refresh_probe:
        step("cek muat mulai (sebelum tag)", so, lambda: api("POST", f"/outbound/so/{so}/loading-check/start", who=WHJ,
                                                             ent=E, params={"warehouse_id": wh}))
        sess = DB.rfid_verify_sessions.find_one({"order_id": so, "status": "open"}, {"_id": 0, "id": 1, "untagged": 1})
        step("simulasi tag", so, lambda: api("POST", f"/outbound/so/{so}/loading-check/simulate-tags", ent=E,
                                             body={"warehouse_id": wh}))
        tags = [x.get("epc") for x in DB.rfid_tags.find({"roll_id": {"$in": rids}, "status": "active"}, {"epc": 1})]
        api("POST", f"/outbound/loading-check/{sess['id']}/scan", who=WHJ, ent=E, body={"epcs": tags, "source": "device"})
        c, js = api("POST", f"/outbound/loading-check/{sess['id']}/complete", who=WHJ, ent=E)
        res = (so_doc(so).get("loading_checks") or {}).get(wh, {})
        verdict("LC-REFRESH", res.get("result") == "with_issues",
                f"sesi dimulai sebelum roll bertag → hasil {res.get('result')} extra={len(res.get('extra') or [])} "
                f"untagged_unresolved={res.get('untagged_unresolved')}")
    else:
        api("POST", f"/outbound/so/{so}/loading-check/simulate-tags", ent=E, body={"warehouse_id": wh})
    step("cek muat mulai", so, lambda: api("POST", f"/outbound/so/{so}/loading-check/start", who=WHJ, ent=E,
                                           params={"warehouse_id": wh}))
    sess = DB.rfid_verify_sessions.find_one({"order_id": so, "status": "open"}, {"_id": 0, "id": 1, "untagged": 1})
    if sess:
        tags = [x.get("epc") for x in DB.rfid_tags.find({"roll_id": {"$in": rids}, "status": "active"}, {"epc": 1})]
        step("pindai EPC", so, lambda: api("POST", f"/outbound/loading-check/{sess['id']}/scan", who=WHJ, ent=E,
                                           body={"epcs": tags, "source": "device"}))
        step("cek muat selesai", so, lambda: api("POST", f"/outbound/loading-check/{sess['id']}/complete", who=WHJ, ent=E))
        print("   hasil cek muat:", ((so_doc(so).get("loading_checks") or {}).get(wh) or {}).get("result"))


def _ship_and_deliver(so, t, rl):
    step("kirim (dispatch)", so, lambda: api("POST", f"/outbound/tasks/{t}/dispatch", who=WHJ, ent=E))
    sh = list(DB.shipments.find({"order_id": so}, {"_id": 0, "id": 1}))
    if not sh:
        verdict("HAPPY", False, "SJ tidak terbit")
        return so
    shp = sh[0]["id"]
    c, d = step("buat pengiriman", so, lambda: api("POST", "/logistics/deliveries", ent=E, body={
        "shipment_ids": [shp], "mode": "expedition", "courier_name": "JNE", "tracking_no": "RESI-B2B-1", "shipping_cost": 0}))
    L = d.get("id") if isinstance(d, dict) else None
    jpg = b"\xff\xd8\xff\xe0" + b"0" * 2000 + b"\xff\xd9"
    step("foto muat", so, lambda: api("POST", f"/logistics/deliveries/{L}/photos", ent=E, data={"kind": "load"},
                                      files={"file": ("m.jpg", jpg, "image/jpeg")}))
    step("muat", so, lambda: api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "loaded"}))
    step("berangkat", so, lambda: api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "in_transit"}))
    step("GPS", so, lambda: api("POST", f"/logistics/deliveries/{L}/positions", ent=E,
                                body={"location": "Tol Cipularang KM 90", "lat": -6.6, "lng": 107.4, "note": ""}))
    step("foto POD", so, lambda: api("POST", f"/logistics/deliveries/{L}/photos", ent=E, data={"kind": "pod"},
                                     files={"file": ("p.jpg", jpg, "image/jpeg")}))
    step("diterima (POD)", so, lambda: api("POST", f"/logistics/deliveries/{L}/transition", ent=E,
                                           body={"to": "delivered", "receiver_name": "Budi", "note": ""}))
    step("selesai", so, lambda: api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "completed"}))
    s = so_doc(so)["status"]
    rs = [DB.inventory_rolls.find_one({"id": r}, {"status": 1})["status"] for r, _ in rl]
    verdict("HAPPY", s == "done" and all(x == "delivered" for x in rs), f"SO={s}, roll={rs}")
    RESULTS["HAPPY_SO"] = so
    return so


def s_anom01():
    """Resolve eskalasi ber-qty pada tugas partially_shipped melepas roll yang sudah dikirim."""
    fr = free_rolls(PID, E, WH, n=2, min_len=10)
    rl = [(r["id"], r["length_remaining"]) for r in fr]
    a, b = rl
    _, _, so = mk_so(rl)
    to_confirmed(so)
    t = task_of(so)[0]["id"]
    pick(t, a[0], a[1])
    loading_override(so)
    step("kirim sebagian (roll A)", so, lambda: api("POST", f"/outbound/tasks/{t}/dispatch", who=WHJ, ent=E,
                                                     params={"ship_qty": a[1]}), [a[0], b[0]])
    print("   tugas:", DB.wms_tasks.find_one({"id": t}, {"_id": 0, "status": 1, "shipped_qty": 1, "picked_qty": 1}))
    step("eskalasi", so, lambda: api("POST", f"/outbound/tasks/{t}/escalate", who=WHJ, ent=E,
                                      params={"reason": "Stok fisik roll B kurang"}), [a[0], b[0]])
    step("resolve adjusted_qty=A", so, lambda: api("POST", f"/outbound/tasks/{t}/resolve-escalation", ent=E,
                                                    params={"adjusted_qty": a[1], "resolution_notes": "uji B2b"}),
         [a[0], b[0]])
    ra = DB.inventory_rolls.find_one({"id": a[0]}, {"_id": 0, "status": 1, "reserved_ref": 1})
    in_sj = DB.shipments.count_documents({"order_id": so, "rolls.roll_id": a[0]})
    tk = DB.wms_tasks.find_one({"id": t}, {"_id": 0, "status": 1, "shipped_qty": 1, "quantity": 1})
    verdict("ANOM-01", ra["status"] == "available" and in_sj > 0,
            f"roll A di SJ ({in_sj}) berstatus {ra['status']}; tugas {tk}")


def s_anom02():
    """(a) eskalasi → batal SO → resolve (tanpa qty) menghidupkan tugas batal; (b) eskalasi → pick → kirim → resolve."""
    fr = free_rolls(PID, E, WH, n=2, min_len=10)
    _, _, so = mk_so([(fr[0]["id"], fr[0]["length_remaining"])])
    to_confirmed(so)
    t = task_of(so)[0]["id"]
    api("POST", f"/outbound/tasks/{t}/escalate", who=WHJ, ent=E, params={"reason": "Roll tidak ketemu di rak"})
    step("batal SO", so, lambda: api("POST", f"/sales-orders/{so}/cancel", ent=E, body={"reason": "uji batal B2b"}))
    step("resolve tanpa qty", so, lambda: api("POST", f"/outbound/tasks/{t}/resolve-escalation", ent=E,
                                               params={"resolution_notes": "uji B2b"}))
    st = DB.wms_tasks.find_one({"id": t})["status"]
    verdict("ANOM-02a", st != "cancelled", f"tugas SO batal sesudah resolve = {st}")
    # (b)
    r2 = fr[1]
    _, _, so2 = mk_so([(r2["id"], r2["length_remaining"])])
    to_confirmed(so2)
    t2 = task_of(so2)[0]["id"]
    api("POST", f"/outbound/tasks/{t2}/escalate", who=WHJ, ent=E, params={"reason": "Selisih qty label"})
    c1, _ = pick(t2, r2["id"], r2["length_remaining"], note="scan-pick saat escalated")
    loading_override(so2)
    c2, _ = api("POST", f"/outbound/tasks/{t2}/dispatch", who=WHJ, ent=E, note="dispatch saat eskalasi pending")
    step("resolve sesudah kirim", so2, lambda: api("POST", f"/outbound/tasks/{t2}/resolve-escalation", ent=E,
                                                   params={"resolution_notes": "uji B2b"}))
    st2 = DB.wms_tasks.find_one({"id": t2})["status"]
    verdict("ANOM-02b", c1 == 200 and c2 == 200, f"pick {c1}, dispatch {c2} saat escalated; status akhir {st2}")


def s_anom03():
    """Override SO approved: roll committed tidak terlihat → reservasi ganda / backorder palsu."""
    fr = free_rolls(PID, E, WH, n=2, min_len=10)
    _, _, so = mk_so([], purchase_mode="qty", qty=round(fr[0]["length_remaining"] + fr[1]["length_remaining"], 2) - 1)
    to_confirmed(so)
    api("POST", f"/sales-orders/{so}/verify", ent=E, body={"note": ""})
    ctx = api("GET", f"/sales-orders/{so}/override-context", ent=E)
    q0 = so_doc(so)["items"][0]["quantity"]
    step("override qty +20", so, lambda: api("POST", f"/sales-orders/{so}/override", ent=E, body={
        "header": {"notes": "uji"}, "lines": [{"product_id": PID, "quantity": q0 + 20}], "add_items": [],
        "note": "uji override B2b naik"}))
    held = list(DB.inventory_rolls.find({"reserved_ref.id": so}, {"_id": 0, "id": 1, "status": 1, "length_remaining": 1}))
    tot = round(sum(r["length_remaining"] for r in held), 2)
    alloc = round(sum(a.get("quantity", 0) for a in so_doc(so).get("allocations") or []), 2)
    verdict("ANOM-03", tot > q0 + 20 + 0.01 or abs(tot - alloc) > 0.01,
            f"qty baru {q0 + 20}; roll dipegang SO {len(held)} = {tot} ({sorted(set(r['status'] for r in held))}); Σ alokasi {alloc}")
    RESULTS["ANOM03_SO"] = so


def s_anom08():
    """SO draft + Ganti Roll memegang roll; batal tidak melepas."""
    fr = free_rolls(PID, E, WH, n=2, min_len=10)
    _, _, so = mk_so([(fr[0]["id"], fr[0]["length_remaining"])])
    step("lepas reservasi → draft", so, lambda: api("POST", f"/sales-orders/{so}/release-reservation", ent=E))
    step("Ganti Roll di draft", so, lambda: api("POST", f"/sales-orders/{so}/items/{PID}/reallocate", ent=E,
                                                 body={"roll_lines": [{"roll_id": fr[1]["id"], "take_qty": 0}]}), [fr[1]["id"]])
    step("batal SO draft", so, lambda: api("POST", f"/sales-orders/{so}/cancel", ent=E, body={"reason": "uji batal draft"}),
         [fr[1]["id"]])
    r = DB.inventory_rolls.find_one({"id": fr[1]["id"]}, {"_id": 0, "status": 1, "reserved_ref": 1})
    verdict("ANOM-08", (r.get("reserved_ref") or {}).get("id") == so, f"SO {so_doc(so)['status']}; roll {r}")


def s_anom11_12():
    """Pindai roll sama dua kali; kirim sebagian memecah roll (anak tanpa tag)."""
    fr = free_rolls(PID, E, WH, n=2, min_len=20)
    r = fr[0]
    _, _, so = mk_so([(r["id"], r["length_remaining"])])
    to_confirmed(so)
    t = task_of(so)[0]["id"]
    h = round(r["length_remaining"] / 2, 2)
    c1, _ = pick(t, r["id"], h, note="pick ke-1 roll sama")
    c2, _ = pick(t, r["id"], h, note="pick ke-2 roll sama")
    loading_override(so)
    c3, js = api("POST", f"/outbound/tasks/{t}/dispatch", who=WHJ, ent=E, note="dispatch sesudah pick ganda")
    verdict("ANOM-11", c1 == 200 and c2 == 200 and c3 >= 400, f"pick {c1},{c2}; dispatch {c3} {str(js)[:160]}")
    # ANOM-12: pick sebagian lalu kirim sebagian
    r2 = fr[1]
    _, _, so2 = mk_so([(r2["id"], r2["length_remaining"])])
    to_confirmed(so2)
    t2 = task_of(so2)[0]["id"]
    part = round(r2["length_remaining"] * 0.4, 2)
    pick(t2, r2["id"], part, note="pick sebagian roll")
    loading_override(so2)
    step("kirim sebagian", so2, lambda: api("POST", f"/outbound/tasks/{t2}/dispatch", who=WHJ, ent=E,
                                            params={"ship_qty": part}), [r2["id"]])
    kids = list(DB.inventory_rolls.find({"parent_roll_id": r2["id"]}, {"_id": 0, "id": 1, "status": 1, "rfid_tag_id": 1,
                                                                       "cut": 1, "length_remaining": 1}))
    verdict("ANOM-12", any(k["status"] == "in_transit_sales" and not k.get("rfid_tag_id") for k in kids),
            f"anak: {kids}")


def s_cancel():
    """Batal di tengah: sesudah alokasi potong (reservasi panjang), sesudah approve, sesudah pick, sesudah kirim."""
    fr = free_rolls(PID, E, WH, n=4, min_len=20)
    # B-1 potong dari roll
    r = fr[0]
    take = round(r["length_remaining"] / 3, 2)
    c, js, so = mk_so([(r["id"], take)], item_extra={"target_quantity": take, "rounding_choice": "exact_cut"})
    rr = DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0, "status": 1, "length_reserved": 1, "length_reservations": 1})
    print("   roll potong sesudah SO:", rr)
    step("batal sesudah reservasi potong", so, lambda: api("POST", f"/sales-orders/{so}/cancel", ent=E,
                                                           body={"reason": "uji batal potong"}), [r["id"]])
    rr2 = DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0, "status": 1, "length_reserved": 1, "length_reservations": 1})
    verdict("BATAL-POTONG", not rr2.get("length_reserved") and not any(
        x.get("status") in ("reserved", "committed") and (x.get("ref") or {}).get("id") == so
        for x in rr2.get("length_reservations") or []), f"roll sesudah batal {rr2}")
    # B-2/B-3 sesudah pick
    r = fr[1]
    _, _, so = mk_so([(r["id"], r["length_remaining"])])
    to_confirmed(so)
    t = task_of(so)[0]["id"]
    pick(t, r["id"], r["length_remaining"])
    step("batal sesudah pick", so, lambda: api("POST", f"/sales-orders/{so}/cancel", ent=E, body={"reason": "uji batal pick"}),
         [r["id"]])
    tk = DB.wms_tasks.find_one({"id": t}, {"_id": 0, "status": 1, "picked_qty": 1})
    rr = DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0, "status": 1, "reserved_ref": 1, "bin_id": 1})
    putback = DB.wms_tasks.count_documents({"source_id": so, "flow_type": {"$in": ["putback", "inbound", "putaway"]}})
    verdict("ANOM-20", rr["status"] == "available" and putback == 0,
            f"tugas {tk}; roll {rr}; tugas kembalikan-ke-rak {putback}")
    # B-4 sesudah kirim
    r = fr[2]
    _, _, so = mk_so([(r["id"], r["length_remaining"])])
    to_confirmed(so)
    t = task_of(so)[0]["id"]
    pick(t, r["id"], r["length_remaining"])
    loading_override(so)
    api("POST", f"/outbound/tasks/{t}/dispatch", who=WHJ, ent=E)
    c, js = api("POST", f"/sales-orders/{so}/cancel", ent=E, body={"reason": "uji batal sesudah kirim"})
    verdict("BATAL-SESUDAH-KIRIM-DITOLAK", c >= 400, f"{c} {str(js)[:150]}")


def s_anom04():
    """Backorder sesudah kirim sebagian: tidak terisi lagi; POD per SJ tidak memindah roll."""
    fr = free_rolls(PID, E, WH, n=3, min_len=10)
    # SO X memegang 1 roll; SO Y minta lebih dari sisa tersedia → backorder (pakai qty mode besar)
    avail = sum(r["length_remaining"] for r in DB.inventory_rolls.find(
        {"product_id": PID, "owner_entity_id": E, "status": "available", "active_movement": None,
         "length_reserved": {"$in": [None, 0]}}, {"length_remaining": 1}))
    print("   tersedia total", round(avail, 2))
    _, js, so = mk_so([], purchase_mode="qty", qty=round(avail + 30, 2), extra={"allow_backorder": True})
    d = so_doc(so)
    print("   SO", d["status"], "backorders", [(b.get("qty") or b.get("quantity"), b.get("status")) for b in d.get("backorders") or []])
    to_confirmed(so)
    ts = task_of(so)
    print("   tugas", len(ts))
    RESULTS["ANOM04_SO"] = so
    # ambil & kirim satu tugas sebagian saja (1 roll) lalu POD
    t = ts[0]
    rid = (DB.inventory_rolls.find_one({"reserved_ref.id": so, "warehouse_id": t["warehouse_id"]}, {"id": 1, "length_remaining": 1}))
    pick(t["id"], rid["id"], rid["length_remaining"])
    loading_override(so, wh=t["warehouse_id"])
    api("POST", f"/outbound/tasks/{t['id']}/dispatch", who=WHJ, ent=E, params={"ship_qty": rid["length_remaining"]})
    print("   SO sesudah kirim sebagian:", so_doc(so)["status"])
    shp = DB.shipments.find_one({"order_id": so}, {"id": 1})["id"]
    c, dd = api("POST", "/logistics/deliveries", ent=E, body={"shipment_ids": [shp], "mode": "expedition",
                                                              "courier_name": "JNE", "tracking_no": "RESI-B2B-4", "shipping_cost": 0})
    L = dd["id"]
    jpg = b"\xff\xd8\xff\xe0" + b"0" * 2000 + b"\xff\xd9"
    api("POST", f"/logistics/deliveries/{L}/photos", ent=E, data={"kind": "load"}, files={"file": ("m.jpg", jpg, "image/jpeg")})
    api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "loaded"})
    api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "in_transit"})
    api("POST", f"/logistics/deliveries/{L}/photos", ent=E, data={"kind": "pod"}, files={"file": ("p.jpg", jpg, "image/jpeg")})
    step("POD SJ-1", so, lambda: api("POST", f"/logistics/deliveries/{L}/transition", ent=E,
                                     body={"to": "delivered", "receiver_name": "Budi"}), [rid["id"]])
    r1 = DB.inventory_rolls.find_one({"id": rid["id"]}, {"_id": 0, "status": 1})
    verdict("ANOM-05", r1["status"] == "in_transit_sales", f"roll SJ ber-POD = {r1['status']}; SO {so_doc(so)['status']}")
    # backorder: coba rencana pemenuhan dari stok
    c, js = api("POST", f"/sales-admin/orders/{so}/fulfillment-plan", ent=E, body={
        "lines": [{"product_id": PID, "stock_qty": 5, "stock_roll_ids": [], "interco": [], "reorder_qty": 0, "wait_qty": 0}],
        "note": "uji B2b"})
    verdict("ANOM-04", c >= 400 or so_doc(so)["status"] == "partially_shipped",
            f"rencana pemenuhan {c} {str(js)[:160]}; SO {so_doc(so)['status']}")


def s_anom10_16():
    """SO backorder murni dikonfirmasi tanpa tugas; tugas bisa dibuat akun PT lain."""
    pid = "prod_79be16ccc9b2"   # sedikit roll
    avail = list(DB.inventory_rolls.find({"product_id": pid, "owner_entity_id": E, "status": "available"}, {"length_remaining": 1}))
    print("   roll tersedia", len(avail))
    _, js, so = mk_so([], purchase_mode="qty", qty=100000, extra={"allow_backorder": True}, pid=pid)
    if not so:
        return
    d = so_doc(so)
    print("   SO", d["status"])
    to_confirmed(so)
    n = DB.wms_tasks.count_documents({"order_id": so})
    print("   status", so_doc(so)["status"], "tugas", n)
    verdict("ANOM-10", so_doc(so)["status"] == "confirmed", f"status {so_doc(so)['status']}, tugas {n}")
    # ANOM-16: akun gudang Soreang (PT Kanda) membuat tugas untuk SO KSC
    c, js = api("POST", f"/wms/tasks/outbound-from-order/{so}", who="warehouse.soreang@kainnusantara.id", ent="ent_kanda",
                note="PT lain bikin tugas")
    c2, js2 = api("GET", f"/outbound/so/{so}/loading-check", who="warehouse.soreang@kainnusantara.id", ent="ent_kanda",
                  params={"warehouse_id": WH}, note="PT lain baca cek muat")
    verdict("ANOM-16", c < 400 or c2 < 400, f"outbound-from-order {c} {str(js)[:120]}; loading-check GET {c2} {str(js2)[:120]}")


def s_anom17():
    """Sales PT KSC membuat SO untuk PT lain (entity_id payload)."""
    fr = free_rolls("prod_d87bc5aa1635", "ent_82b52ed6ee8b", "wh_fe25df27918e", n=1)
    cust = DB.customers.find_one({"entity_id": "ent_82b52ed6ee8b", "status": "active"}, {"id": 1, "addresses.id": 1}) or {}
    body = {"customer_id": cust.get("id", CUST), "shipping_address_id": (cust.get("addresses") or [{"id": ADDR}])[0]["id"],
            "entity_id": "ent_82b52ed6ee8b", "items": [{"product_id": "prod_d87bc5aa1635", "quantity": fr[0]["length_remaining"],
                                                         "unit": "kg"}], "payment_term_code": "NET30", "confirm_mixed_lot": True}
    u = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "entity_ids": 1, "role": 1, "entity_id": 1})
    print("   akun sales:", u)
    c, js = api("POST", "/sales-orders", who="sales@kainnusantara.id", ent="ent_ksc", body=body, note="SO PT lain via payload")
    so = js.get("id") if isinstance(js, dict) else None
    ent = so_doc(so).get("entity_id") if so else None
    if so:
        ent = DB.sales_orders.find_one({"id": so}, {"entity_id": 1})["entity_id"]
    verdict("ANOM-17", c < 400 and ent == "ent_82b52ed6ee8b", f"{c} SO {so} entity {ent} {str(js)[:150] if c >= 400 else ''}")


def confirm_cuts(so, waste=0.0, who=WHJ, verify=True):
    out = []
    for r in DB.inventory_rolls.find({"length_reservations.ref.id": so}, {"_id": 0, "id": 1, "length_reservations": 1}):
        for x in r["length_reservations"]:
            if (x.get("ref") or {}).get("id") != so or x.get("status") not in ("reserved", "committed"):
                continue
            c, js = api("POST", f"/inventory/rolls/{r['id']}/reservations/{x['id']}/cut", who=who, ent=E,
                        body={"actual_length": x["qty"], "waste": waste, "note": "uji B2b"}, note="konfirmasi potong")
            child = (js or {}).get("child") or (js or {}).get("child_roll") or {}
            cid = child.get("id") if isinstance(child, dict) else None
            if not cid:
                k = DB.inventory_rolls.find_one({"parent_roll_id": r["id"]}, {"id": 1, "roll_no": 1}, sort=[("created_at", -1)])
                cid = k and k["id"]
            if verify and cid:
                api("POST", f"/inventory/rolls/{cid}/verify-identity", who=who, ent=E,
                    body={"scanned_code": roll_no(cid)}, note="verifikasi identitas anak")
            out.append((r["id"], x["qty"], cid))
    return out


def s_cut():
    """Potong untuk SO: reservasi panjang → potong fisik (dengan susut) → anak → ambil → kirim."""
    fr = free_rolls(PID, E, WH, n=1, min_len=10)
    r = fr[0]
    take = round(r["length_remaining"] / 2, 2)
    _, _, so = mk_so([(r["id"], take)], item_extra={"target_quantity": take, "rounding_choice": "exact_cut"})
    to_confirmed(so)
    jr0 = DB.journal_entries.count_documents({"source_id": {"$regex": r["id"]}})
    a = state(so, [r["id"]])
    cuts = confirm_cuts(so, waste=0.3)
    b = state(so, [r["id"]])
    show(diff(a, b), "potong + susut 0,3")
    par = DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0, "length_remaining": 1, "status": 1, "length_reserved": 1,
                                                      "is_remnant": 1, "grade": 1})
    kid = DB.inventory_rolls.find_one({"id": cuts[0][2]}, {"_id": 0, "status": 1, "length_remaining": 1, "rfid_tag_id": 1,
                                                         "cut": 1, "reserved_ref": 1, "lot": 1, "unit_cost": 1})
    mv = list(DB.inventory_movements.find({"roll_id": {"$regex": r["id"]}, "movement_type": {"$in": ["roll_cut", "cut_waste", "cut"]}},
                                          {"_id": 0, "movement_type": 1, "quantity": 1}))
    jr = DB.journal_entries.count_documents({"$or": [{"source_id": {"$in": [r["id"], cuts[0][2]]}},
                                                     {"description": {"$regex": "susut|waste|cut", "$options": "i"},
                                                      "created_at": {"$gte": a["so"][so] and "2026-11-09"}}]})
    print("   induk", par, "\n   anak", kid, "\n   mutasi", mv, "jurnal susut/potong", jr, "(sebelum", jr0, ")")
    verdict("CUT-WASTE-GL", not any(m["movement_type"] == "cut_waste" for m in mv) or jr == 0,
            f"mutasi {mv}; jurnal terkait potong {jr}")
    verdict("CUT-REMNANT", not par.get("is_remnant"), f"sisa induk {par}")
    t = task_of(so)[0]["id"]
    pick(t, cuts[0][2], kid["length_remaining"], note="pick anak potongan")
    loading_override(so)
    step("kirim anak", so, lambda: api("POST", f"/outbound/tasks/{t}/dispatch", who=WHJ, ent=E), [r["id"], cuts[0][2]])
    RESULTS["CUT_SO"] = so


def _small_product(lo=3, hi=6):
    for a in DB.inventory_rolls.aggregate([
            {"$match": {"owner_entity_id": E, "warehouse_id": WH, "status": "available", "active_movement": None,
                        "length_reserved": {"$in": [None, 0]}, "hold.held": {"$ne": True}, "unit": "kg"}},
            {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gte": lo, "$lte": hi}}}]):
        busy = DB.inventory_rolls.count_documents({"product_id": a["_id"], "owner_entity_id": E,
                                                   "$or": [{"length_reserved": {"$gt": 0}}, {"status": {"$ne": "available"}}]})
        others = DB.inventory_rolls.count_documents({"product_id": a["_id"], "owner_entity_id": E, "warehouse_id": {"$ne": WH},
                                                     "status": "available"})
        if others == 0:
            return a["_id"], busy
    return None, None


def s_backorder():
    """ANOM-04/05/10/16: backorder sesudah kirim sebagian; konfirmasi backorder murni tanpa tugas."""
    P = sys.argv[-1] if sys.argv[-1].startswith("prod_") else "prod_e0ef67f3c8c8"   # KSC: 4 roll JKT + 7 roll RCM-RETUR
    rs = list(DB.inventory_rolls.find({"product_id": P, "owner_entity_id": E, "status": "available", "active_movement": None,
                                       "length_reserved": {"$in": [None, 0]}, "hold.held": {"$ne": True}},
                                      {"_id": 0, "id": 1, "length_remaining": 1, "warehouse_id": 1}).sort("length_remaining", 1))
    print("   produk", P, "roll bebas", [(r["warehouse_id"][-6:], r["length_remaining"]) for r in rs])
    R1 = next(r for r in rs if r["warehouse_id"] == WH)
    rest = [r for r in rs if r["id"] != R1["id"]]
    _, _, X = mk_so([(R1["id"], R1["length_remaining"])], pid=P)
    q = round(sum(r["length_remaining"] for r in rest), 2) + 10
    _, _, Y = mk_so([], purchase_mode="qty", qty=q, extra={"allow_backorder": True}, pid=P)
    print("   Y", so_doc(Y)["status"], so_doc(Y).get("backorders"))
    _, _, Z = mk_so([], purchase_mode="qty", qty=5, extra={"allow_backorder": True}, pid=P)
    print("   Z (backorder murni)", so_doc(Z)["status"])
    to_confirmed(Y)
    to_confirmed(Z)
    nz = DB.wms_tasks.count_documents({"order_id": Z})
    verdict("ANOM-10a", so_doc(Z)["status"] == "confirmed" and nz == 0, f"Z status {so_doc(Z)['status']} tugas {nz}")
    confirm_cuts(Y)
    print("   tugas Y per gudang:", [(t["warehouse_id"], t["quantity"]) for t in task_of(Y)])
    for t in task_of(Y):
        for r in DB.inventory_rolls.find({"reserved_ref.id": Y, "warehouse_id": t["warehouse_id"]}, {"id": 1, "length_remaining": 1}):
            pick(t["id"], r["id"], r["length_remaining"], note=f"pick oleh petugas Jakarta di {t['warehouse_id']}")
        loading_override(Y, wh=t["warehouse_id"])
        api("POST", f"/outbound/tasks/{t['id']}/dispatch", who=WHJ, ent=E, note=f"dispatch {t['warehouse_id']}")
    print("   Y sesudah kirim:", so_doc(Y)["status"], so_doc(Y).get("fulfillment"))
    step("batal X (bebaskan R1)", X, lambda: api("POST", f"/sales-orders/{X}/cancel", ent=E, body={"reason": "uji bebaskan stok"}))
    yb, zb = so_doc(Y).get("backorders"), so_doc(Z).get("backorders")
    c, js = api("POST", f"/sales-admin/orders/{Y}/fulfillment-plan", ent=E, body={
        "lines": [{"product_id": P, "stock_qty": 10, "stock_roll_ids": [], "interco": [], "reorder_qty": 0, "wait_qty": 0}],
        "note": "uji B2b"}, note="rencana pemenuhan Y (partially_shipped)")
    verdict("ANOM-04", c >= 400, f"{c} {str(js)[:200]}; Y {so_doc(Y)['status']}")
    c2, js2 = api("POST", f"/sales-admin/orders/{Z}/fulfillment-plan", ent=E, body={
        "lines": [{"product_id": P, "stock_qty": 5, "stock_roll_ids": [], "interco": [], "reorder_qty": 0, "wait_qty": 0}],
        "note": "uji B2b"}, note="rencana pemenuhan Z (confirmed, tanpa tugas)")
    nz2 = DB.wms_tasks.count_documents({"order_id": Z})
    held = [(x["id"], x["status"]) for x in DB.inventory_rolls.find({"$or": [{"reserved_ref.id": Z}, {"length_reservations.ref.id": Z}]}, {"id": 1, "status": 1})]
    verdict("ANOM-10b", c2 < 400 and nz2 == 0 and held, f"Z {so_doc(Z)['status']} roll {held} tugas {nz2}")
    c3, js3 = api("POST", f"/wms/tasks/outbound-from-order/{Z}", who="warehouse.soreang@kainnusantara.id", ent="ent_kanda",
                  note="akun PT Kanda melahirkan tugas SO KSC")
    verdict("ANOM-16", c3 < 400 and DB.wms_tasks.count_documents({"order_id": Z}) > 0,
            f"{c3} tugas Z sekarang {DB.wms_tasks.count_documents({'order_id': Z})}; {str(js3)[:120]}")
    # POD Y
    shp = [s["id"] for s in DB.shipments.find({"order_id": Y}, {"id": 1})][:1]
    c, dd = api("POST", "/logistics/deliveries", ent=E, body={"shipment_ids": shp, "mode": "expedition", "courier_name": "JNE",
                                                              "tracking_no": "RESI-B2B-Y", "shipping_cost": 0})
    L = dd["id"]
    jpg = b"\xff\xd8\xff\xe0" + b"0" * 2000 + b"\xff\xd9"
    api("POST", f"/logistics/deliveries/{L}/photos", ent=E, data={"kind": "load"}, files={"file": ("m.jpg", jpg, "image/jpeg")})
    api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "loaded"})
    api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "in_transit"})
    api("POST", f"/logistics/deliveries/{L}/photos", ent=E, data={"kind": "pod"}, files={"file": ("p.jpg", jpg, "image/jpeg")})
    api("POST", f"/logistics/deliveries/{L}/transition", ent=E, body={"to": "delivered", "receiver_name": "Budi"})
    st = sorted({x["status"] for x in DB.inventory_rolls.find({"id": {"$in": [r["roll_id"] for s in DB.shipments.find({"order_id": Y}) for r in s.get("rolls", [])]}}, {"status": 1})})
    verdict("ANOM-05", "in_transit_sales" in st, f"roll SJ Y sesudah POD = {st}; Y {so_doc(Y)['status']}")
    RESULTS["BO"] = {"X": X, "Y": Y, "Z": Z, "P": P}


SCN = {k[2:]: v for k, v in globals().items() if k.startswith("s_")}

if __name__ == "__main__":
    names = sys.argv[1:] or ["happy"]
    for n in names:
        print(f"\n===== {n} =====  {datetime.now(timezone.utc).isoformat()}")
        try:
            SCN[n]()
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            RESULTS[n + "_ERR"] = repr(ex)
    print("\nHASIL:", RESULTS)
    save("flows_" + "_".join(names), RESULTS)
