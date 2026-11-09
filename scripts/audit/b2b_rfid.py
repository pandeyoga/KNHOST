"""B2b — skenario RFID: siklus tag (EPC dipakai ulang, tandai tercetak tanpa bukti), gate V2 (reader dibuat di gedung
gate RCM-WOVEN, simulator saat mode simulasi PT MATI, lintasan nyata lewat device key, antrean periksa lintas lokasi),
gate lama, handheld (cakupan, batch idempoten, key handheld di /rfid/ingest). Stack audit saja (DB salinan)."""
import copy
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app/scripts/audit")
sys.path.insert(0, "/app/backend")
import requests  # noqa: E402
from b2b_lib import BASE, DB, api, free_rolls, save  # noqa: E402
from b2b_flows import E, WH, RESULTS, verdict, roll_no  # noqa: E402
from b2b_flows2 import P2, GATE_WH, _mk_transfer, _dispatch_transfer, roll  # noqa: E402
from services import rfid_v2_envelope as env  # noqa: E402

SITE_RCM = "site_c0c8400b0017"
WHJ = "warehouse@kainnusantara.id"
FIX = json.loads(Path("/app/backend/tests/fixtures/u300_contract.json").read_text())["DeviceConfig"]
V2 = f"{BASE}/rfid/v2"
ST = {}


def _mkdev(direction, wh=GATE_WH, site=SITE_RCM):
    code = f"G{direction.upper()}-B2B-{uuid.uuid4().hex[:4]}"
    c, d = api("POST", "/rfid/devices", body={"name": f"Gate {direction} uji B2b", "type": "gate", "direction": direction,
                                               "warehouse_id": wh, "code": code}, note=f"reader {direction}")
    dev = d.get("id") or (d.get("device") or {}).get("id")
    c, k = api("POST", f"/rfid/devices/{dev}/api-key", note="key")
    key = k.get("api_key") or k.get("key")
    cfg = copy.deepcopy(FIX)
    cfg.update(device_id=dev, warehouse_id=wh, site_id=site, config_version="b2b-v1")
    g = cfg["logical_gates"][0]
    g.update(logical_gate_id="G1", warehouse_id=wh, site_id=site, direction=direction, antenna_ids=["1", "2", "3"],
             completion_basis="document_session")
    api("PUT", f"/rfid/v2/ops/devices/{dev}/config", body=cfg, note="terbitkan profil V2")
    return {"id": dev, "key": key, "direction": direction}


def r_setup():
    din, dout = _mkdev("in"), _mkdev("out")
    c, js = api("PATCH", f"/warehouses/{GATE_WH}", body={"data": {"gate_config": {
        "has_gate": True, "confirm_mode": "gate", "physical_gate": True,
        "pairs": [{"name": "Gate B2B", "in_device_id": din["id"], "out_device_id": dout["id"], "layout": "terpisah"}]}}},
        note="tautkan pasangan gate")
    c, gp = api("GET", f"/warehouses/{GATE_WH}/gate-policy")
    print("   gate-policy:", {k: gp.get(k) for k in ("effective_mode", "gate_ready", "device_ids_in", "device_ids_out")})
    ST.update(din=din, dout=dout)
    json.dump(ST, open("/tmp/b2b/rfid_state.json", "w"))
    return din, dout


def _load():
    ST.update(json.load(open("/tmp/b2b/rfid_state.json")))


def _encode(rid):
    c, js = api("POST", "/rfid/tags/encode", who=WHJ, ent=E, body={"roll_id": rid}, note="encode tag")
    t = DB.rfid_tags.find_one({"roll_id": rid, "status": {"$in": ["active", "pending_print"]}}, {"_id": 0, "id": 1, "epc": 1, "status": 1})
    return t


def _sim(dev, scenario, st, sid, who="admin@kainnusantara.id"):
    c, js = api("POST", f"/rfid/v2/ops/devices/{dev}/simulate", who=who, body={
        "scenario": scenario, "logical_gate_id": "G1", "source_type": st, "source_id": sid, "roll_limit": 200},
        note=f"simulator {scenario}")
    p = (js.get("passages") or [{}])[-1] if isinstance(js, dict) else {}
    dec = p.get("decision") or {}
    return c, js, dec


def _real(dev, scenario, epcs, extra=()):
    h = {"X-Device-Key": dev["key"]}
    cfg = requests.get(f"{V2}/device/config", headers=h, timeout=30).json()
    g = cfg["logical_gates"][0]
    b = env.build_passage(scenario=scenario, gate_id=g["logical_gate_id"], config_version=cfg["config_version"],
                          hardware_profile_id=cfg["hardware_profile_id"], direction=g["direction"],
                          antennas=g["antenna_ids"], doc_epcs=epcs, extra_strong=extra)
    for body in b["batches"]:
        r = requests.post(f"{V2}/events", headers=h, json=body, timeout=30)
        assert r.status_code == 200, r.text
    r = requests.post(f"{V2}/passages/{b['passage_id']}/close", json=b["close"], timeout=120,
                      headers=dict(h, **{"Idempotency-Key": "c-" + b["passage_id"]}))
    js = r.json()
    print(f"  [{r.status_code}] lintasan NYATA {scenario} → {json.dumps((js.get('decision') or js), default=str)[:300]}")
    return r.status_code, js


def r_g01():
    """Simulasi PT MATI: simulator di reader nyata memasang klaim → lintasan nyata berikutnya merah (G-01/G-02)."""
    _load()
    api("PUT", "/config/values", body={"items": [{"key": "wms.rfid_simulation", "value": False, "scope_type": "entity",
                                                    "scope_id": E, "reason": "uji audit B2b G-01 (stack sementara)"}]},
        note="MATIKAN mode simulasi KSC")
    rs = free_rolls(P2, E, WH, n=2, min_len=10)
    rids = [r["id"] for r in rs]
    tags = [_encode(r) for r in rids]
    epcs = [t["epc"] for t in tags]
    T = _mk_transfer(rids, dest=GATE_WH)
    _dispatch_transfer(T, rids)
    cr0 = DB.rfid_v2_crossings.count_documents({"source_id": T})
    c, js, dec = _sim(ST["din"]["id"], "full_load", "wh_transfer", T)
    cr = list(DB.rfid_v2_crossings.find({"source_id": T}, {"_id": 0, "roll_id": 1, "simulated": 1, "passage": 1, "at": 1}))
    st = [roll(r)["status"] for r in rids]
    td = DB.warehouse_transfers.find_one({"id": T}, {"_id": 0, "status": 1, "gate_arrivals": 1})
    print("   simulasi:", dec.get("verdict"), dec.get("reason_codes"), "| klaim", len(cr), cr[:1], "| roll", st,
          "| transfer", td.get("status"), "gate_arrivals", len(td.get("gate_arrivals") or []))
    ok_no_stock = all(s == "in_transit_transfer" for s in st)
    verdict("G-01a", ok_no_stock and len(cr) > cr0, f"stok tidak dipindah ({st}) TETAPI klaim crossing dipasang: {len(cr)}; "
            f"gate_arrivals {len(td.get('gate_arrivals') or [])}")
    print("   tunggu 130 dtk (lewat jendela bawaan muatan 120 dtk) lalu lintasan NYATA dengan EPC yang sama …")
    time.sleep(130)
    c, real = _real(ST["din"], "full_load", epcs)
    d = real.get("decision") or {}
    st2 = [roll(r)["status"] for r in rids]
    verdict("G-01b", d.get("verdict") == "RED", f"lintasan nyata sesudah simulasi: {d.get('verdict')} {d.get('reason_codes')}; "
            f"latched={d.get('latched')}; roll {st2}")
    # G-02: simulator merah mengunci reader nyata tanpa notifikasi
    n0 = DB.notifications.count_documents({"type": {"$regex": "rfid_gate"}})
    c, js, dec = _sim(ST["din"]["id"], "foreign_roll", "wh_transfer", T)
    gs = requests.get(f"{V2}/device/gate-state", headers={"X-Device-Key": ST["din"]["key"]}, params={"logical_gate_id": "G1"}).json()
    n1 = DB.notifications.count_documents({"type": {"$regex": "rfid_gate"}})
    verdict("G-02", bool(gs.get("latched") or gs.get("latch")), f"simulator foreign_roll {dec.get('verdict')}; gate-state reader "
            f"nyata latched={gs.get('latched')} ; notifikasi rfid_gate {n0}→{n1}")
    ST.update(T=T, rids=rids, epcs=epcs)
    json.dump(ST, open("/tmp/b2b/rfid_state.json", "w"))
    api("PUT", "/config/values", body={"items": [{"key": "wms.rfid_simulation", "value": True, "scope_type": "entity",
                                                    "scope_id": E, "reason": "pulihkan setelan uji B2b"}]}, note="pulihkan simulasi KSC")


def r_g07():
    """Antrean periksa/sesi lintas PT & lokasi (G-07)."""
    _load()
    for who, ent in [("warehouse.soreang@kainnusantara.id", "ent_kanda"), ("warehouse@kainnusantara.id", E),
                     ("wh.admin@kainnusantara.id", "ent_kanda"), ("warehouse.rancamalang@kainnusantara.id", "ent_82b52ed6ee8b")]:
        c, js = api("GET", "/rfid/v2/ops/reviews", who=who, ent=ent, params={"status": "open"}, quiet=True)
        rows = js.get("items") or js.get("reviews") or js.get("rows") or (js if isinstance(js, list) else [])
        whs = sorted({r.get("warehouse_id") for r in rows})
        c2, js2 = api("GET", "/rfid/v2/ops/reviews/summary", who=who, ent=ent, quiet=True)
        c3, js3 = api("GET", f"/rfid/v2/ops/devices/{ST['din']['id']}/sessions", who=who, ent=ent, quiet=True)
        print(f"   {who.split('@')[0]:24s} reviews {c} n={len(rows)} gudang={whs} | summary {c2} {str(js2)[:90]} | sesi reader RCM {c3}")
        RESULTS.setdefault("G-07", []).append({"who": who, "reviews": c, "n": len(rows), "whs": whs, "summary": c2, "sessions": c3})


def r_g03():
    """Gate lama: /rfid/gate/simulate (wms.scan) menulis gate_exit nyata (G-03)."""
    sj_rolls = [x["roll_id"] for s in DB.shipments.find({"warehouse_id": WH, "status": "dispatched"}, {"rolls.roll_id": 1})
                .sort("created_at", -1).limit(30) for x in s.get("rolls") or []]
    t = DB.rfid_tags.find_one({"status": "active", "roll_id": {"$in": [r["id"] for r in DB.inventory_rolls.find(
        {"id": {"$in": sj_rolls}, "status": "in_transit_sales", "gate_exit": None}, {"id": 1})]}}, {"_id": 0, "roll_id": 1, "epc": 1})
    rid = t["roll_id"]
    before = roll(rid, {"_id": 0, "gate_exit": 1, "status": 1})
    inc0 = DB.rfid_incidents.count_documents({}) if "rfid_incidents" in DB.list_collection_names() else 0
    c, js = api("POST", "/rfid/gate/simulate", who=WHJ, ent=E, body={"device_id": "rdev_891088a797f4", "roll_id": rid},
                note="gate lama simulate oleh petugas")
    after = roll(rid, {"_id": 0, "gate_exit": 1, "status": 1})
    inc1 = DB.rfid_incidents.count_documents({}) if "rfid_incidents" in DB.list_collection_names() else 0
    verdict("G-03", c < 400 and after.get("gate_exit") != before.get("gate_exit"),
            f"{c}; roll {rid} gate_exit {before.get('gate_exit')} → {json.dumps(after.get('gate_exit'), default=str)[:160]}; insiden {inc0}→{inc1}; {str(js)[:160]}")


def r_t01():
    """EPC tag pensiun dipakai ulang untuk roll lain (T-01/T-02)."""
    rs = free_rolls(P2, E, WH, n=2, min_len=5)
    t1 = _encode(rs[0]["id"])
    c, js = api("DELETE", f"/rfid/tags/{t1['id']}", who=WHJ, ent=E, note="pensiunkan tag")
    st = DB.rfid_tags.find_one({"id": t1["id"]}, {"_id": 0, "status": 1})
    c2, js2 = api("POST", "/rfid/tags/encode", who=WHJ, ent=E, body={"roll_id": rs[1]["id"], "epc": t1["epc"]},
                  note="encode roll lain dengan EPC pensiun")
    docs = list(DB.rfid_tags.find({"epc": t1["epc"]}, {"_id": 0, "roll_id": 1, "status": 1}))
    c3, js3 = api("GET", "/rfid/lookup", who=WHJ, ent=E, params={"code": t1["epc"], "record": "false"}, quiet=True)
    verdict("T-01", c2 < 400 and len(docs) >= 2, f"tag lama {st}; encode ulang {c2}; dokumen EPC {docs}; lookup → "
            f"{(js3.get('roll') or {}).get('id') if isinstance(js3, dict) else js3}")


def r_p02():
    """Petugas (wms.scan/print) menandai job tercetak → tag aktif tanpa bukti chip (P-02)."""
    rid = DB.inventory_rolls.find_one({"product_id": P2, "owner_entity_id": E, "warehouse_id": WH, "status": "available",
                                       "rfid_tag_id": None, "length_reserved": {"$in": [None, 0]}}, {"id": 1})["id"]
    c, job = api("POST", "/rfid/print-jobs", who=WHJ, ent=E, body={"roll_ids": [rid]}, note="buat job cetak")
    jid = job.get("id") or (job.get("job") or {}).get("id")
    t0 = DB.rfid_tags.find_one({"roll_id": rid}, {"_id": 0, "status": 1, "epc": 1})
    c2, js2 = api("POST", f"/rfid/print-jobs/{jid}/mark-printed", who=WHJ, ent=E, body={}, note="tandai tercetak manual")
    t1 = DB.rfid_tags.find_one({"roll_id": rid}, {"_id": 0, "status": 1})
    j = DB.rfid_print_jobs.find_one({"id": jid}, {"_id": 0, "status": 1, "items.status": 1, "items.results": 1})
    verdict("P-02", c2 < 400 and t1["status"] == "active", f"tag {t0['status']} → {t1['status']}; job {json.dumps(j, default=str)[:260]}")


def r_handheld():
    """Handheld: perangkat Soreang; cakupan tugas per peran; batch idempoten; key handheld di /rfid/ingest (H-01)."""
    c, d = api("POST", "/handheld/devices", body={"name": "C72 Uji B2b", "warehouse_id": "wh_40e831c5bb53", "code": f"C72-B2B-{uuid.uuid4().hex[:4]}",
                                                   "scope_level": "site", "profile": {}, "base_url": ""}, note="daftar handheld Soreang")
    dev = (d.get("device") or {}).get("id")
    key = d.get("api_key")
    h = {"X-Device-Key": key}
    out = {}
    for who, ent in [("warehouse.soreang@kainnusantara.id", "ent_kanda"), ("warehouse@kainnusantara.id", E),
                     ("wh.admin@kainnusantara.id", E), ("driver@kainnusantara.id", E)]:
        c1, s = api("POST", "/handheld/session/start", who=who, ent=ent, headers=h, body={"app_version": "0.1.0-lab"}, quiet=True)
        c2, sm = api("GET", "/handheld/tasks/summary", who=who, ent=ent, headers=h, quiet=True)
        out[who] = (c1, (s.get("warehouses") if isinstance(s, dict) else None), c2, str(sm)[:200])
        print(f"   {who.split('@')[0]:24s} sesi {c1} gudang={s.get('warehouses') if isinstance(s, dict) else s} | ringkasan {c2} {str(sm)[:200]}")
    RESULTS["HH-SCOPE"] = out
    # tugas keluar yang terlihat petugas Soreang
    c, tl = api("GET", "/handheld/tasks", who="warehouse.soreang@kainnusantara.id", ent="ent_kanda", headers=h,
                params={"kind": "outbound_so", "limit": 100}, quiet=True)
    rows = tl.get("items") or tl.get("tasks") or []
    print("   outbound_so Soreang:", c, len(rows), [(r.get("doc_id"), r.get("entity_id") or r.get("pt")) for r in rows[:5]])
    # H-01: key handheld tanpa sesi pengguna di jalur lama /rfid/ingest
    epc = (DB.rfid_tags.find_one({"status": "active"}, {"epc": 1}) or {}).get("epc")
    r = requests.post(f"{BASE}/rfid/ingest", headers=h, json={"epcs": [epc]}, timeout=30)
    print(f"  [{r.status_code}] /rfid/ingest dengan key handheld TANPA Bearer → {r.text[:200]}")
    t = DB.rfid_tags.find_one({"epc": epc}, {"_id": 0, "last_seen_device_id": 1, "last_seen_at": 1})
    verdict("H-01", r.status_code < 400, f"{r.status_code}; tag last_seen {t}")
    ST.update(hh={"id": dev, "key": key})
    json.dump(ST, open("/tmp/b2b/rfid_state.json", "w"))


def r_hh_batch():
    """Batch transfer_in idempoten di gedung bersama RCM-WOVEN (handheld = cadangan gate): transfer KSC (dari r_g01)
    diterima lewat handheld oleh petugas Rancamalang (PT Cipta Sandang) / Admin Gudang (KSC)."""
    _load()
    c, d = api("POST", "/handheld/devices", body={"name": "C72 Uji B2b RCM", "warehouse_id": GATE_WH,
                                                   "code": f"C72-B2B-{uuid.uuid4().hex[:4]}", "scope_level": "site",
                                                   "profile": {}, "base_url": ""}, note="daftar handheld RCM")
    h = {"X-Device-Key": d.get("api_key")}
    T, rids, epcs = ST["T"], ST["rids"], ST["epcs"]
    who = ent = hos = None
    for w, e in [("warehouse.rancamalang@kainnusantara.id", "ent_82b52ed6ee8b"), ("wh.admin@kainnusantara.id", E)]:
        c, s = api("POST", "/handheld/session/start", who=w, ent=e, headers=h, body={"app_version": "0.1.0-lab"}, quiet=True)
        c, tl = api("GET", "/handheld/tasks", who=w, ent=e, headers=h, params={"kind": "transfer_in", "limit": 100}, quiet=True)
        ids = [x.get("doc_id") or x.get("id") for x in (tl.get("items") or tl.get("tasks") or [])] if isinstance(tl, dict) else []
        print(f"   {w.split('@')[0]} transfer_in KSC tampil? {T in ids} ({len(ids)} dok)")
        RESULTS.setdefault("HH-TRF-VIS", {})[w] = T in ids
        if T in ids and who is None:
            who, ent, hos = w, e, (s.get("operator_session") or {}).get("id")
    c, ex = api("GET", f"/handheld/tasks/transfer_in/{T}/expected", who=who, ent=ent, headers=h, quiet=True)
    ver = ex.get("version") if isinstance(ex, dict) else None
    body = {"client_batch_id": f"b2b-trf-{uuid.uuid4().hex[:8]}", "kind": "transfer_in", "doc_id": T, "operator_session_id": hos,
            "snapshot_version": ver, "device_time": datetime.now(timezone.utc).isoformat(), "clock_offset_ms": 0, "clock_synced": True,
            "reads": [{"epc": epcs[0], "rssi": -50.0, "count": 3}, {"epc": "E2FFFFFFFFFFFFFFFFFFFF01"}], "labels": [], "simulated": False}
    c1, r1 = api("POST", "/handheld/batches", who=who, ent=ent, headers=h, body=body, note="batch ke-1")
    c2, r2 = api("POST", "/handheld/batches", who=who, ent=ent, headers=h, body=dict(body, device_time=datetime.now(timezone.utc).isoformat()), note="kirim ulang sama")
    c3, r3 = api("POST", "/handheld/batches", who=who, ent=ent, headers=h, body=dict(body, reads=[{"epc": epcs[1]}]), note="ID sama isi beda")
    body4 = dict(body, client_batch_id=f"b2b-trf-{uuid.uuid4().hex[:8]}", operator_session_id=None, reads=[{"epc": epcs[1]}])
    c4, r4 = api("POST", "/handheld/batches", who=who, ent=ent, headers=h, body=body4, note="tanpa operator_session_id (H-08)")
    st = [roll(r)["status"] + "@" + roll(r)["warehouse_id"][-6:] for r in rids]
    t = DB.warehouse_transfers.find_one({"id": T}, {"_id": 0, "status": 1})
    verdict("HH-IDEMP", c1 == 200 and isinstance(r2, dict) and r2.get("replay") is True and c3 == 409,
            f"operator {who}; b1 {c1} {str(r1)[:140]} | ulang {c2} replay={r2.get('replay') if isinstance(r2, dict) else r2} | beda isi {c3} | "
            f"tanpa sesi {c4} {str(r4)[:100]} | roll {st} | transfer {t}")


def r_g04():
    """Transfer ke gedung gate: lintasan IN sebagian (simulasi PT menyala) → batal transfer → sesi dokumen tetap terbuka?"""
    _load()
    rs = [r for r in free_rolls(P2, E, WH, n=6, min_len=5) if not r.get("rfid_tag_id")][:2]
    rids = [r["id"] for r in rs]
    [_encode(r) for r in rids]
    T = _mk_transfer(rids, dest=GATE_WH)
    _dispatch_transfer(T, rids)
    api("POST", f"/rfid/v2/ops/devices/{ST['din']['id']}/gate-latch/acknowledge", who="wh.admin@kainnusantara.id", ent=E,
        body={"note": "uji B2b buka kunci"}, note="buka kunci gate")
    c, js, dec = _sim(ST["din"]["id"], "partial_trip", "wh_transfer", T)
    s0 = DB.rfid_v2_doc_sessions.find_one({"source_ref.source_id": T}, {"_id": 0, "status": 1, "counts": 1})
    st0 = [roll(r)["status"] for r in rids]
    c, js = api("DELETE", f"/transfers/{T}", ent=E, params={"reason": "uji B2b batal sesudah gate"}, note="batal transfer")
    s1 = DB.rfid_v2_doc_sessions.find_one({"source_ref.source_id": T}, {"_id": 0, "status": 1, "counts": 1})
    st1 = [(roll(r)["status"], roll(r)["warehouse_id"][-6:]) for r in rids]
    verdict("G-04", (s1 or {}).get("status") == "open", f"simulasi {dec.get('verdict')}; roll sesudah lintasan {st0}; batal {c} {str(js)[:120]}; "
            f"sesi {s0} → {s1}; roll akhir {st1}")


def r_vis():
    """Siapa melihat tugas keluar apa (jenis, PT, gudang) di /wms/tasks (HP) & /outbound/tasks (desktop)."""
    from collections import Counter
    for who in ["warehouse@kainnusantara.id", "warehouse.soreang@kainnusantara.id", "warehouse.rancamalang@kainnusantara.id",
                "wh.admin@kainnusantara.id", "manager@kainnusantara.id", "salesadmin@kainnusantara.id", "driver@kainnusantara.id"]:
        row = {}
        for path, params in [("/wms/tasks", {"flow_type": "outbound"}), ("/outbound/tasks", None)]:
            c, js = api("GET", path, who=who, params=params, quiet=True)
            items = js if isinstance(js, list) else (js.get("tasks") or js.get("items") or []) if isinstance(js, dict) else []
            ids = [t.get("id") for t in items]
            docs = list(DB.wms_tasks.find({"id": {"$in": ids}}, {"_id": 0, "task_subtype": 1, "entity_id": 1, "warehouse_id": 1, "status": 1, "source_type": 1}))
            row[path] = {"code": c, "n": len(items), "jenis": dict(Counter(d.get("task_subtype") or d.get("source_type") or "-" for d in docs)),
                         "pt": dict(Counter(d.get("entity_id") for d in docs)), "gudang": len({d.get("warehouse_id") for d in docs}),
                         "status": dict(Counter(d.get("status") for d in docs).most_common(4))}
        print(f"   {who.split('@')[0]:22s} HP {row['/wms/tasks']} | desk {row['/outbound/tasks']}")
        RESULTS.setdefault("VIS", {})[who] = row


SCN = {k[2:]: v for k, v in globals().items() if k.startswith("r_")}

if __name__ == "__main__":
    for n in sys.argv[1:]:
        print(f"\n===== {n} =====  {datetime.now(timezone.utc).isoformat()}")
        try:
            SCN[n]()
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            RESULTS[n + "_ERR"] = repr(ex)
    print("\nHASIL:", json.dumps(RESULTS, default=str)[:3000])
    save("rfid_" + "_".join(sys.argv[1:]), RESULTS)
