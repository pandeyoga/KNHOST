"""PREP-H — transaksi gate di pekerja latar, penilaian ber-memo (tanpa N+1), masa simpan bukti.

Lewat endpoint DEVICE sungguhan (envelope simulator D1) + layanan langsung (proses uji = pemroses kedua, sah karena
klaim CAS). Skenario:
  * close mengembalikan keputusan TANPA menunggu transaksi; pekerja latar menuntaskannya (terima transfer per roll);
  * close ganda BERSAMAAN → satu keputusan, satu klaim per roll, satu buku transaksi;
  * pemroses mati di tengah (sewa basi) → job ulang mengambil alih, tidak ada terima/gerak ganda;
  * transaksi gagal → error + jeda bertahap → berhenti otomatis → "Ulangi transaksi" (force) menuntaskan;
  * memo `GateLookup` vs query per roll → keputusan IDENTIK untuk 10 jenis kasus, query memo terbatas;
  * retensi: uji coba tidak mengubah apa pun; arsip JSONL.gz lalu hapus HANYA bukti mentah lintasan lama yang
    tuntas; keputusan/klaim/sesi/kasus/buku tidak tersentuh; kasus terbuka & transaksi gagal ditahan.
Jalankan: cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_h_gate_worker.py
"""
import copy
import gzip
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _prep_h_bed import API, DB, ENT, Bed  # noqa: E402
from _shared_loop import run  # noqa: E402
from services.rfid_v2_common import digest  # noqa: E402

B = Bed("H")


@pytest.fixture(scope="module", autouse=True)
def seed():
    try:
        requests.get(f"{API}/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    B.setup()
    yield
    B.teardown()


def _go(k, epcs, extra=()):
    built = B.build(k, epcs, extra=extra)
    B.send_events(k, built)
    return built


# ── 1. close tidak menunggu transaksi; pekerja latar menuntaskan ─────────────────────────────────────
def test_close_returns_decision_before_transaction_worker_completes():
    tid, rs = B.transfer(60)
    built = _go("in", [r["epc"] for r in rs])
    t0 = time.perf_counter()
    r = B.close("in", built)
    ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200 and r.json()["verdict"] == "GREEN", r.text
    pid = B.pid("in", built["passage_id"])
    row = B.wait_state(pid)
    assert row["gate_txn_state"] == "done" and row["gate_txn_attempts"] == 1
    t = DB.warehouse_transfers.find_one({"id": tid})
    assert t["status"] == "completed" and len(t["receipt_events"]) == 1
    assert DB.inventory_rolls.count_documents({"id": {"$in": [x["id"] for x in rs]}, "warehouse_id": B.wh_gate}) == 60
    led = list(DB.rfid_v2_gate_txn.find({"passage": pid}))
    assert len(led) == 1 and led[0]["state"] == "done" and led[0]["attempts"] == 1
    print(f"close 60 roll (transfer IN, transaksi di latar): {ms:.0f} ms")


# ── 2. close ganda BERSAMAAN: satu keputusan, satu klaim per roll, satu buku ─────────────────────────
def test_concurrent_double_close_single_decision_and_ledger():
    sid, rs = B.shipment(120)
    built = _go("out", [r["epc"] for r in rs])
    B.prepare_close(built)
    out, codes = [], []

    def go():
        for _ in range(30):   # agent mengulang EVIDENCE_PENDING (keputusan sedang dihitung close lain)
            resp = B.close("out", built)
            if resp.status_code != 503:
                out.append(resp)
                return
            codes.append(resp.json()["detail"]["code"])
            time.sleep(0.3)
    threads = [threading.Thread(target=go) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(out) == 4 and all(x.status_code == 200 for x in out), [x.text for x in out]
    assert len({x.json()["decision_id"] for x in out}) == 1 and out[0].json()["verdict"] == "GREEN"
    assert set(codes) <= {"EVIDENCE_PENDING"}
    pid = B.pid("out", built["passage_id"])
    assert DB.rfid_v2_crossings.count_documents({"passage": pid}) == 120
    B.wait_state(pid)
    led = list(DB.rfid_v2_gate_txn.find({"passage": pid}))
    assert len(led) == 1 and led[0]["attempts"] == 1
    exits = DB.shipments.find_one({"id": sid})["gate_exits"]
    assert len(exits) == 1 and exits[0]["count"] == 120


# ── 3. pemroses mati di tengah (sewa basi) → job ulang mengambil alih tanpa terima ganda ─────────────
def test_stale_worker_recovered_by_retry_job_without_double_receipt():
    from services import gate_txn_service as gt
    tid, rs = B.transfer(30)
    built = _go("in", [r["epc"] for r in rs])
    assert B.close("in", built).status_code == 200
    pid = B.pid("in", built["passage_id"])
    B.wait_state(pid)
    moves = DB.inventory_movements.count_documents({"roll_id": {"$in": [r["id"] for r in rs]}})
    # Pemroses mati SESUDAH roll diterima, SEBELUM menandai selesai: lintasan & buku tertinggal "processing" basi.
    old = (datetime.now(timezone.utc) - timedelta(seconds=gt.STALE_S + 60)).isoformat().replace("+00:00", "Z")
    DB.rfid_v2_passages.update_one({"_id": pid}, {"$set": {"gate_txn_state": "processing", "gate_txn_lease_until": old,
                                                          "gate_txn_owner": "mati:1"}})
    DB.rfid_v2_gate_txn.update_many({"passage": pid}, {"$set": {"state": "processing", "started_at": old}})
    res = run(gt.job_rfid_gate_txn_retry())
    assert res["created"] >= 1, res
    row = DB.rfid_v2_passages.find_one({"_id": pid})
    assert row["gate_txn_state"] == "done" and row["gate_txn_attempts"] == 2
    led = DB.rfid_v2_gate_txn.find_one({"passage": pid})
    assert led["state"] == "done" and led["attempts"] == 2 and len(led["summary"]["already"]) == 30   # idempoten
    t = DB.warehouse_transfers.find_one({"id": tid})
    assert t["status"] == "completed" and len(t["receipt_events"]) == 1
    assert DB.inventory_movements.count_documents({"roll_id": {"$in": [r["id"] for r in rs]}}) == moves   # tanpa gerak ganda


# ── 4. gagal → jeda bertahap → berhenti otomatis → Ulangi (force) ───────────────────────────────────
def test_error_backoff_give_up_then_forced_retry():
    from services import gate_txn_service as gt
    tid, rs = B.transfer(5)
    built = _go("in", [r["epc"] for r in rs])
    r = B.close("in", built)
    assert r.status_code == 200 and r.json()["verdict"] == "GREEN"
    pid = B.pid("in", built["passage_id"])
    B.wait_state(pid)
    # Dokumen sumber "hilang" di antara keputusan & transaksi (masukan transaksi menunjuk transfer yang tidak ada).
    real = DB.rfid_v2_passages.find_one({"_id": pid})["gate_txn_input"]
    bogus = copy.deepcopy(real)
    bogus["sources"][0]["source_ref"]["source_id"] = f"trf_TEST_H_{B.tag}_hilang"
    DB.rfid_v2_passages.update_one({"_id": pid}, {"$set": {"gate_txn_input": bogus, "gate_txn_state": "pending",
                                                          "gate_txn_attempts": 0}})
    run(gt.sweep())
    row = DB.rfid_v2_passages.find_one({"_id": pid})
    assert row["gate_txn_state"] == "error" and row["gate_txn_attempts"] == 1 and not row["gate_txn_gave_up"]
    nxt = datetime.fromisoformat(row["gate_txn_next_at"].replace("Z", "+00:00"))
    assert 20 <= (nxt - datetime.now(timezone.utc)).total_seconds() <= gt.BACKOFF_S[0] + 5
    run(gt.sweep())                                                   # belum jatuh tempo → tidak diambil
    assert DB.rfid_v2_passages.find_one({"_id": pid})["gate_txn_attempts"] == 1
    DB.rfid_v2_passages.update_one({"_id": pid}, {"$set": {"gate_txn_attempts": len(gt.BACKOFF_S),
                                                          "gate_txn_next_at": "2000-01-01T00:00:00Z"}})
    run(gt.sweep())                                                   # percobaan ke-7 gagal → berhenti otomatis
    row = DB.rfid_v2_passages.find_one({"_id": pid})
    assert row["gate_txn_state"] == "error" and row["gate_txn_gave_up"] and row["gate_txn_next_at"] is None
    run(gt.sweep())
    assert DB.rfid_v2_passages.find_one({"_id": pid})["gate_txn_attempts"] == len(gt.BACKOFF_S) + 1
    assert run(gt.queue_summary([B.wh_gate]))["gave_up"] >= 1
    DB.rfid_v2_passages.update_one({"_id": pid}, {"$set": {"gate_txn_input": real}})   # dokumen kembali → Ulangi (force)
    dev = DB.rfid_devices.find_one({"id": B.dev["in"]}, {"_id": 0, "api_key_hash": 0})
    results = run(gt.post_close(dev, pid, force=True))
    assert results and results[0]["state"] == "done", results
    got = (results[0].get("arrived") or []) + (results[0].get("already") or [])
    assert sorted(got) == sorted(r["roll_no"] for r in rs)                              # buku sumber asli tetap "done"
    assert DB.rfid_v2_passages.find_one({"_id": pid})["gate_txn_state"] == "done"
    assert DB.warehouse_transfers.find_one({"id": tid})["status"] == "completed"


# ── 5. memo GateLookup vs query per roll: keputusan IDENTIK, query memo terbatas ─────────────────────
def _decide(k, epcs, prefetch, extra=()):
    from services import rfid_v2_core as core
    from services import rfid_v2_policy as policy
    cfg = DB.rfid_v2_configs.find_one({"_id": digest([B.dev[k], "h-v1"])})["config"]
    g = cfg["logical_gates"][0]
    built = B.build(k, epcs, extra=extra)
    sums = [{"summary": s, "quarantine": None} for b in built["batches"] for s in b.get("tag_summaries") or []]
    old = policy.PREFETCH
    policy.PREFETCH = prefetch
    try:
        return run(policy.decide(body=built["close"], gate=g, params=core.gate_params(g), pid=f"pid-{B.tag}-cmp",
                                 warehouse=B.wh_gate, events=[], summaries=sums, binding_entries=None, binding_reasons=[],
                                 transport_reasons=[], overflow=0, device_id=B.dev[k]))
    finally:
        policy.PREFETCH = old


def _shape(res):
    # Urutan alasan antar-roll di jalur lama mengikuti urutan selesai query paralel (asyncio.gather) → dibandingkan
    # sebagai daftar terurut; isi (kode, level, pesan, roll) wajib sama persis.
    def key(i):
        return (i["level"], i["code"], i.get("epc") or "", i.get("roll_id") or "", i.get("message") or "")
    return {"verdict": res["verdict"], "reasons": sorted(res["reasons"].items, key=key),
            "codes": sorted(res["reasons"].codes()),
            "matched": sorted((rid, ref["source_id"]) for rid, ref in res["matched"]), "counts": res["counts"],
            "claimable": res["claimable"], "binding_mode": res["binding_mode"],
            "entries": sorted((e["source_ref"]["source_id"], tuple(e["roll_ids"])) for e in res["entries"])}


def test_prefetch_decisions_identical_across_cases():
    cases = {}
    sid, rs = B.shipment(25)
    stray = B.rolls(1, wh=B.wh_gate)[0]
    qr = B.rolls(1, wh=B.wh_gate, status="quarantine")[0]
    cases["out_green"] = ("out", [r["epc"] for r in rs], ())
    cases["out_foreign_quarantine_unknown"] = ("out", [r["epc"] for r in rs[:5]],
                                               (stray["epc"], qr["epc"], "E2FF" + B.tag.upper() + "0" * 12))
    _, rs_dead = B.shipment(3, so_status="cancelled")
    cases["out_so_cancelled"] = ("out", [r["epc"] for r in rs_dead], ())
    sid2, rs2 = B.shipment(4)
    for r in rs2[:2]:   # klaim milik lintasan lain → REPLAY_EXIT merah
        DB.rfid_v2_crossings.insert_one({"_id": digest(["shipment", sid2, "out", r["id"]]), "passage": f"pid-other-{B.tag}",
                                         "roll_id": r["id"], "source_type": "shipment", "source_id": sid2, "direction": "out",
                                         "at": "2026-01-01T00:00:00Z", "device_id": "x", "gate_id": "G1"})
    cases["out_replay"] = ("out", [r["epc"] for r in rs2], ())
    mko, step_ref = f"mko_TEST_H_{B.tag}_{B.nx()}", f"iss_TEST_H_{B.tag}_{B.nx()}"
    DB.makloon_orders.insert_one({"id": mko, "mko_number": f"MKO-H-{B.tag}-{B.nx()}", "status": "in_progress", "entity_id": ENT,
                                  "steps": [{"seq": 1, "status": "issued", "issue_ref": step_ref, "from_warehouse_id": B.wh_gate,
                                             "makloon_name": "Mitra Celup Uji"}]})
    mk = B.rolls(3, wh=B.wh_gate, status="subcon", bucket_ref={"type": "subcon", "id": step_ref, "mko_id": mko, "step": 1})
    cases["out_makloon"] = ("out", [r["epc"] for r in mk], ())
    rpr = f"rpr_TEST_H_{B.tag}_{B.nx()}"
    rp = B.rolls(2, wh=B.wh_gate, status="wip", repair_open=rpr)
    DB.repair_orders.insert_one({"id": rpr, "number": f"RPR-H-{B.tag}-{B.nx()}", "status": "sent", "partner_name": "Mitra Uji",
                                 "entity_id": ENT, "lines": [{"roll_id": r["id"], "warehouse_id": B.wh_gate} for r in rp]})
    cases["out_repair"] = ("out", [r["epc"] for r in rp], ())
    _, rt = B.transfer(12)
    _, rt_other = B.transfer(2, dest=B.wh_other)
    cases["in_transfer_wrong_destination"] = ("in", [r["epc"] for r in rt + rt_other], ())
    so_l, trf_l = f"so_TEST_H_{B.tag}_{B.nx()}", f"trf_TEST_H_{B.tag}_{B.nx()}"
    DB.sales_orders.insert_one({"id": so_l, "number": so_l, "status": "in_progress", "entity_id": ENT})
    linked = B.rolls(2, status="in_transit_transfer", reserved_ref={"type": "sales_order", "id": so_l},
                     transfer_ref={"type": "wh_transfer", "id": trf_l, "so_id": so_l})
    DB.warehouse_transfers.insert_one({"id": trf_l, "code": f"TRF-H-{B.tag}-{B.nx()}", "status": "dispatched",
                                       "transfer_kind": "warehouse", "source_warehouse_id": B.wh_src, "dest_warehouse_id": B.wh_gate,
                                       "owner_entity_id": ENT, "entity_id": ENT,
                                       "items": [{"product_id": B.product(), "rolls": [{"roll_id": r["id"]} for r in linked]}]})
    cases["in_linked_transfer"] = ("in", [r["epc"] for r in linked], ())
    cases["in_local_and_no_document"] = ("in", [stray["epc"]], ())
    _, big = B.shipment(300)
    cases["out_big"] = ("out", [r["epc"] for r in big], ())
    for name, (k, epcs, extra) in cases.items():
        a, b = _decide(k, epcs, True, extra), _decide(k, epcs, False, extra)
        assert _shape(a) == _shape(b), name
        assert a["lookup_queries"] is not None and b["lookup_queries"] is None
    big_res = _decide("out", [r["epc"] for r in big], True)
    assert big_res["verdict"] == "GREEN" and big_res["counts"]["matched"] == 300
    assert big_res["lookup_queries"] <= 12, big_res["lookup_queries"]   # dulu ±4 query × 300 roll (N+1)
    replay = _decide("out", [r["epc"] for r in rs2], True)
    assert replay["verdict"] == "RED" and "REPLAY_EXIT" in replay["reasons"].codes()


# ── 6. masa simpan bukti: uji coba, arsip → hapus, yang dilindungi utuh ─────────────────────────────
def _old_passage(dev, days_ago, n_sum=6, **extra):
    lp = f"h-ret-{B.tag}-{B.nx()}"
    pid = digest([dev, lp])
    at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
    DB.rfid_v2_passages.insert_one({"_id": pid, "device_id": dev, "local_passage_id": lp, "gate_id": "G1", "warehouse_id": B.wh_gate,
                                    "state": "FINAL", "event_count": 1, "summary_count": n_sum, "edge_count": 2, "overflow": {},
                                    "created_at": at, "decision": {"verdict": "GREEN", "decision_id": lp},
                                    "gate_txn_state": "done", "gate_txn_input": {"sources": []}, **extra})
    DB.rfid_v2_summaries.insert_many([{"_id": digest([pid, "summary", str(i)]), "passage": pid, "received_at": at,
                                       "summary": {"epc": f"E{i}", "peak_rssi": -50}} for i in range(n_sum)])
    DB.rfid_v2_edges.insert_many([{"_id": digest([pid, "edge", str(i)]), "passage": pid, "received_at": at,
                                   "edge": {"sensor": "A"}} for i in range(2)])
    DB.rfid_v2_events.insert_one({"_id": digest([pid, "event", "1"]), "passage": pid, "received_at": at, "event": {"epc": "E1"}})
    DB.rfid_v2_event_ids.insert_one({"_id": digest([dev, lp, "ev"]), "passage": pid, "fingerprint": "f"})
    DB.rfid_v2_crossings.insert_one({"_id": digest(["ret", pid]), "passage": pid, "roll_id": "r", "source_type": "shipment",
                                     "source_id": f"shp-ret-{B.tag}", "direction": "out", "at": at, "device_id": dev})
    DB.rfid_v2_gate_txn.insert_one({"_id": digest(["gate_txn", pid]), "passage": pid, "state": "done", "device_id": dev})
    return pid


def test_retention_dry_run_then_archive_protects_decisions():
    from services import rfid_v2_retention as ret
    from services.gate_review_service import passage_case_id
    dev = B.dev["out"]
    ok = _old_passage(dev, 120)
    held_case = _old_passage(dev, 120)
    DB.rfid_v2_reviews.insert_one({"_id": passage_case_id(held_case), "passage": held_case, "status": "open", "kind": "passage",
                                   "device_id": dev, "warehouse_id": B.wh_gate, "created_at": "2026-01-01T00:00:00Z"})
    held_txn = _old_passage(dev, 120, gate_txn_state="error", gate_txn_next_at=None, gate_txn_gave_up=True)
    young = _old_passage(dev, 10)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    DB.rfid_reads.insert_many([{"id": f"rread_H_{B.tag}_g", "device_id": dev, "read_type": "gate_out", "timestamp": old_ts, "epc": "E1"},
                               {"id": f"rread_H_{B.tag}_h", "device_id": dev, "read_type": "handheld", "timestamp": old_ts, "epc": "E1"}])
    scope = {"device_id": dev}
    protected = {c: DB[c].count_documents({}) for c in ret.PROTECTED}
    dry = run(ret.run(mode="dry_run", days=90, legacy_days=180, scope=scope, trigger="uji"))
    assert dry["evidence"]["passages"] == 1 and dry["evidence"]["docs"]["rfid_v2_summaries"] == 6
    assert dry["evidence"]["held_open_review"] == 1 and dry["legacy_reads"]["docs"] == 1
    assert DB.rfid_v2_summaries.count_documents({"passage": ok}) == 6                      # uji coba: tidak ada perubahan
    res = run(ret.run(mode="archive", days=90, legacy_days=180, scope=scope, trigger="uji"))
    ev = res["evidence"]
    assert ev["passages"] == 1 and ev["deleted"] == {"rfid_v2_summaries": 6, "rfid_v2_events": 1, "rfid_v2_edges": 2,
                                                     "rfid_v2_overflow": 0, "rfid_v2_event_ids": 1}
    for c in ret.EVIDENCE:
        assert DB[c].count_documents({"passage": ok}) == 0
    for pid in (held_case, held_txn, young):
        assert DB.rfid_v2_summaries.count_documents({"passage": pid}) == 6                # ditahan / masih muda
    row = DB.rfid_v2_passages.find_one({"_id": ok})
    assert row["decision"]["verdict"] == "GREEN" and row.get("evidence_archived_at") and row["evidence_archive"]["file"]
    assert {c: DB[c].count_documents({}) for c in ret.PROTECTED} == protected               # keputusan/klaim/kasus/buku utuh
    root = Path(os.environ.get("LOCAL_STORAGE_DIR", "/data/uploads"))
    with gzip.open(root / row["evidence_archive"]["file"], "rt") as fh:
        lines = [json.loads(x) for x in fh]
    assert len(lines) == 10 and {x["c"] for x in lines} == {"rfid_v2_summaries", "rfid_v2_events", "rfid_v2_edges", "rfid_v2_event_ids"}
    assert all(x["d"]["passage"] == ok for x in lines)
    assert DB.rfid_reads.find_one({"id": f"rread_H_{B.tag}_g"}) is None and DB.rfid_reads.find_one({"id": f"rread_H_{B.tag}_h"})
    again = run(ret.run(mode="archive", days=90, legacy_days=180, scope=scope, trigger="uji"))
    assert again["evidence"]["passages"] == 0 and again["legacy_reads"]["docs"] == 0           # idempoten
    assert run(ret.run(mode="off", scope=scope))["detail"].startswith("Masa simpan bukti gate dimatikan")
    for rel in ev["files"] + res["legacy_reads"]["files"]:                                    # berkas uji dibuang
        (root / rel).unlink(missing_ok=True)


def test_registry_settings_and_jobs_registered():
    import config_registry
    from services import scheduler_service as sch
    keys = {e["key"]: e for e in config_registry.all_entries()}
    assert keys["rfid.evidence_retention_mode"]["default"] == "archive"
    assert keys["rfid.evidence_retention_days"]["default"] == 90
    assert keys["rfid.legacy_reads_retention_days"]["default"] == 180
    ids = {j["id"]: j for j in sch.JOBS}
    assert ids["rfid_gate_txn_retry"]["interval_minutes"] == 2
    assert (ids["rfid_evidence_retention"]["hour"], ids["rfid_evidence_retention"]["minute"]) == (2, 30)
