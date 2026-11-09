"""PREP-F — printer label RFID CP30EN (tanpa perangkat): lease stabil, start barrier, hasil per label, job parsial,
antrean tindak lanjut, pemulihan efek sesudah ACK tersimpan, cetak ulang teks vs ganti tag, izin, idempotensi,
templat 70 × 22 mm, profil printer, telemetri (connector ≠ printer), kompatibilitas kontrak lama.

HTTP nyata (device key + sesi pengguna) ke backend yang berjalan + Mongo langsung untuk menyiapkan/memeriksa data.
Data uji bertanda TEST_PF_<tag> (gudang, printer, roll, tag) — dibersihkan di akhir.
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_f_printer.py
"""
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import rfid_label_template as tpl  # noqa: E402
from services import rfid_print_service as rps  # noqa: E402
from services import rfid_printer_protocol as prn  # noqa: E402
from services import rfid_service  # noqa: E402

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
WH = f"wh_TEST_PF_{TAG}"
WH2 = f"wh_TEST_PF2_{TAG}"
_N = {"n": 0}
DEVICES = []
STATE = {}


def _nx():
    _N["n"] += 1
    return _N["n"]


def _login(email):
    for pw in ("demo12345", "demo1234"):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            return r.json()["token"]
    pytest.skip(f"login {email} gagal")


def _h(token):
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": STATE["ent"]}


@pytest.fixture(scope="module", autouse=True)
def seed():
    try:
        requests.get(f"{API}/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    prod = DB.products.find_one({"status": {"$ne": "inactive"}, "sku": {"$exists": True}}, {"_id": 0, "id": 1})
    src = DB.inventory_rolls.find_one({"status": "available"}, {"_id": 0, "owner_entity_id": 1})
    STATE["product_id"] = prod["id"]
    STATE["ent"] = src["owner_entity_id"]
    for wid in (WH, WH2):
        DB.warehouses.insert_one({"id": wid, "name": f"Gudang Uji PF {wid[-4:]}", "code": f"PF{wid[-6:]}",
                                  "roles": ["storage"], "sharing_mode": "shared", "active": True})
    STATE["admin"] = _login("admin@kainnusantara.id")
    yield
    devs = [d["id"] for d in DEVICES]
    rolls = [r["id"] for r in DB.inventory_rolls.find({"warehouse_id": {"$in": [WH, WH2]}}, {"id": 1})]
    jobs = [j["id"] for j in DB.rfid_print_jobs.find({"warehouse_id": {"$in": [WH, WH2]}}, {"id": 1})]
    DB.rfid_verify_sessions.delete_many({"print_job_id": {"$in": jobs}})
    DB.rfid_verify_sessions.delete_many({"id": {"$regex": f"^rvs_TEST_PF_{TAG}"}})
    DB.rfid_print_jobs.delete_many({"id": {"$in": jobs}})
    DB.rfid_tags.delete_many({"roll_id": {"$in": rolls}})
    DB.rfid_tags.delete_many({"id": {"$regex": f"^rtag_TEST_PF_{TAG}"}})
    DB.rfid_tag_events.delete_many({"roll_id": {"$in": rolls}})
    DB.roll_label_prints.delete_many({"roll_id": {"$in": rolls}})
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.rfid_devices.delete_many({"id": {"$in": devs}})
    DB.warehouses.delete_many({"id": {"$in": [WH, WH2]}})
    DB.audit_logs.delete_many({"entity_id": {"$in": jobs + rolls}, "action": {
        "$in": ["rfid_print_item_resolved", "rfid_tag_replaced", "roll_label_text_reprint"]}})


def make_printer(wh=WH, caps=None, profile=None):
    n = _nx()
    key = f"dk_TEST_PF_{TAG}_{n}"
    dev = {"id": f"rdev_TEST_PF_{TAG}_{n}", "code": f"PF-{TAG}-{n}", "name": f"CP30EN Uji {n}", "type": "printer",
           "warehouse_id": wh, "enabled": True, "status": "offline", "api_key_hash": hashlib.sha256(key.encode()).hexdigest()}
    if caps:
        dev["capabilities"] = caps
    if profile:
        dev["printer_profile"] = profile
    DB.rfid_devices.insert_one(dict(dev))
    dev["key"] = key
    DEVICES.append(dev)
    return dev


def make_roll(wh=WH, status="available", **extra):
    rid = f"roll_TEST_PF_{TAG}_{_nx()}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"PF{TAG[:4]}-{_N['n']:04d}".upper(), "warehouse_id": wh,
                                   "status": status, "owner_entity_id": STATE["ent"], "product_id": STATE["product_id"],
                                   "length_remaining": 25.5, "length_initial": 25.5, "unit": "yard",
                                   "lot": f"LOT-{TAG[:4]}", "grade": "A", **extra})
    return rid


def create_job(n=1, wh=WH, rolls=None):
    rolls = rolls or [make_roll(wh) for _ in range(n)]
    r = requests.post(f"{API}/rfid/print-jobs", headers=_h(STATE["admin"]), json={"roll_ids": rolls}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def dh(dev, instance=None):
    h = {"X-Device-Key": dev["key"]}
    if instance:
        h["X-Connector-Instance"] = instance
    return h


def claim(dev, instance=None):
    r = requests.post(f"{API}/rfid/device-jobs/claim", headers=dh(dev), json={"limit": 5, "instance_id": instance},
                      timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def job_of(res, job_id):
    return next((j for j in res["jobs"] if j["id"] == job_id), None)


def start(dev, job_id, att, item_ids, instance=None):
    return requests.post(f"{API}/rfid/device-jobs/{job_id}/attempts/{att}/start", headers=dh(dev),
                         json={"item_ids": item_ids, "instance_id": instance}, timeout=60)


def results(dev, job_id, att, rows):
    return requests.post(f"{API}/rfid/device-jobs/{job_id}/attempts/{att}/results", headers=dh(dev),
                         json={"results": rows}, timeout=60)


def res_row(it, ps="confirmed", es="confirmed", rid=None, **ev):
    return {"result_event_id": rid or f"res_{uuid.uuid4().hex[:10]}", "item_id": it["item_id"], "print_status": ps,
            "encode_status": es, "payload_sha256": it.get("payload_sha256"), "evidence": {"source": "test", **ev}}


def db_job(job_id):
    return DB.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0})


def tag_status(tag_id):
    return (DB.rfid_tags.find_one({"id": tag_id}, {"_id": 0, "status": 1}) or {}).get("status")


def isolate_queue(dev):
    """Printer uji di gudang uji sendiri → hanya melihat job uji; kosongkan sisa job gudang ini."""
    DB.rfid_print_jobs.update_many({"warehouse_id": dev["warehouse_id"], "status": {"$in": ["queued", "printing"]}},
                                   {"$set": {"status": "failed"}, "$unset": {"lease": ""}})


# ─── Templat 70 × 22 mm ──────────────────────────────────────────────────────
def test_template_70x22_dots_and_zpl():
    p203 = tpl.normalize_profile(None)
    p300 = tpl.normalize_profile({"dpi": 300})
    w203, h203 = tpl.label_dims(p203)
    w300, h300 = tpl.label_dims(p300)
    assert (w203, h203) == (round(70 * 203 / 25.4), round(22 * 203 / 25.4)) == (559, 176)
    assert (w300, h300) == (827, 260)
    snap = tpl.sample_snapshot()
    lay = tpl.layout(snap, p203)
    assert not lay["warnings"], lay["warnings"]
    for e in lay["elements"]:
        right = e["x"] + (e.get("size") or 0)
        bottom = e["y"] + (e.get("h") or e.get("size") or 0)
        assert right <= w203 and bottom <= h203, e
        if e["type"] == "text":   # perkiraan lebar teks (0,62 × lebar font) muat di kolom teks
            assert len(e["text"]) * e["w"] * 0.62 <= e["width"] + 1, e
    z = tpl.render_zpl(snap, p203)
    assert "^PW559" in z and "^LL176" in z and f"^RFW,H^FD{snap['epc']}^FS" in z and "^HV9,24" in z and "^FH_" in z
    assert "^BQN,2," in z and "MA,RL-2611-000123" in z
    assert "^RFW" not in tpl.render_zpl(snap, p203, rfid=False)
    z300 = tpl.render_zpl(snap, p300)
    assert "^PW827" in z300 and "^LL260" in z300
    long = {**snap, "product_name": "Kain Batik Tulis Mega Mendung Premium Super Panjang Sekali Warna Biru Laut"}
    lay2 = tpl.layout(long, p203)
    assert "title" in lay2["truncated"]
    with pytest.raises(ValueError):
        tpl.normalize_profile({"dpi": 600})
    with pytest.raises(ValueError):
        tpl.normalize_profile({"rfid_position": "X9"})
    rv = tpl.render_zpl(snap, tpl.normalize_profile({"encode_report": "rv", "rfid_position": "F4", "rfid_tries": 2}))
    assert "^RS8,F4,,2,N" in rv and "^RVE" in rv and "^HV" not in rv


def test_allocate_epc_never_reuses_any_status(monkeypatch):
    used = f"E2{TAG.upper()}{'0' * 13}1"[:24]
    DB.rfid_tags.insert_one({"id": f"rtag_TEST_PF_{TAG}_ret", "epc": used, "status": "retired", "roll_id": None})
    seq = iter([used, used, f"E2{TAG.upper()}{'0' * 13}2"[:24]])
    monkeypatch.setattr(rfid_service, "generate_epc", lambda: next(seq))
    assert run(rps.allocate_epc()) == f"E2{TAG.upper()}{'0' * 13}2"[:24]


# ─── Job, item, lease stabil ─────────────────────────────────────────────────
def test_job_items_have_ids_digest_and_pending_tags():
    job = create_job(2)
    assert job["status"] == "queued" and job["revision"] == 1
    for it in job["items"]:
        assert it["item_id"].startswith("rpi_") and it["status"] == "pending"
        assert it["payload_sha256"] == hashlib.sha256(it["zpl"].encode()).hexdigest()
        assert len(it["epc"]) == 24 and f"^RFW,H^FD{it['epc']}" in it["zpl"] and "^PW559" in it["zpl"]
        assert tag_status(it["tag_id"]) == "pending_print"
    ev = DB.rfid_tag_events.find_one({"tag_id": job["items"][0]["tag_id"], "event": "encoded"})
    assert ev and ev["job_id"] == job["id"]
    # EPC yang sama tidak boleh ada di dua job terbuka
    r = requests.post(f"{API}/rfid/print-jobs", headers=_h(STATE["admin"]), json={"roll_ids": [job["items"][0]["roll_id"]]},
                      timeout=60)
    assert r.status_code == 409, r.text


def test_stable_lease_redelivery_and_instance_conflict():
    a, b = make_printer(), make_printer()
    isolate_queue(a)
    job = create_job(2)
    r1 = claim(a, "inst-A")
    j1 = job_of(r1, job["id"])
    assert j1 and not j1["redelivered"] and j1["print_attempts"] == 1
    att = j1["lease"]["attempt_id"]
    r2 = claim(a, "inst-A")                       # polling ulang saat mencetak
    j2 = job_of(r2, job["id"])
    assert j2["redelivered"] and j2["lease"]["attempt_id"] == att and j2["print_attempts"] == 1
    assert [i["zpl"] for i in j2["items"]] == [i["zpl"] for i in j1["items"]]
    assert db_job(job["id"])["print_attempts"] == 1
    assert job_of(claim(b, "inst-B"), job["id"]) is None          # printer lain tidak dapat job yang di-lease
    r3 = claim(a, "inst-OTHER")                   # connector kedua dengan key sama
    assert job_of(r3, job["id"]) is None and any(c["job_id"] == job["id"] for c in r3["conflicts"])
    assert DB.rfid_devices.find_one({"id": a["id"]})["connector_conflict"]["instance_id"] == "inst-OTHER"
    # legacy GET pending (tanpa instance) juga tidak mencuri lease milik instance A
    rg = requests.get(f"{API}/rfid/device-jobs/pending", headers=dh(a), timeout=60).json()
    assert job_of(rg, job["id"]) is None
    STATE["lease_case"] = (a, b, job, att)


def test_renew_keeps_attempt_and_other_printer_cannot():
    a, b, job, att = STATE["lease_case"]
    before = db_job(job["id"])["lease"]["expires_at"]
    r = requests.post(f"{API}/rfid/device-jobs/{job['id']}/attempts/{att}/renew", headers=dh(a),
                      json={"instance_id": "inst-A"}, timeout=60)
    assert r.status_code == 200, r.text
    lease = r.json()["lease"]
    assert lease["attempt_id"] == att and lease["expires_at"] >= before and lease["renew_count"] == 1
    rb = requests.post(f"{API}/rfid/device-jobs/{job['id']}/attempts/{att}/renew", headers=dh(b), json={}, timeout=60)
    assert rb.status_code in (403, 409)
    ri = requests.post(f"{API}/rfid/device-jobs/{job['id']}/attempts/{att}/renew", headers=dh(a),
                       json={"instance_id": "inst-X"}, timeout=60)
    assert ri.status_code == 409 and ri.json()["detail"]["code"] == "LEASE_CONFLICT"


def test_start_barrier_idempotent_and_stale_started_not_reclaimed():
    a, b, job, att = STATE["lease_case"]
    full = db_job(job["id"])
    it0 = full["items"][0]
    s1 = start(a, job["id"], att, [it0["item_id"]], "inst-A")
    assert s1.status_code == 200 and s1.json()["accepted"][0]["replay"] is False
    s2 = start(a, job["id"], att, [it0["item_id"]], "inst-A")
    assert s2.json()["accepted"][0]["replay"] is True
    assert db_job(job["id"])["status"] == "printing"
    assert start(b, job["id"], att, [it0["item_id"]]).status_code == 409
    # lease habis saat label sedang dicetak → TIDAK dialihkan ke printer lain
    DB.rfid_print_jobs.update_one({"id": job["id"]}, {"$set": {"lease.expires_at": "2000-01-01T00:00:00+00:00"}})
    assert job_of(claim(b, "inst-B"), job["id"]) is None
    fu = requests.get(f"{API}/rfid/printers/follow-up", headers=_h(STATE["admin"]), params={"warehouse_id": WH},
                      timeout=60).json()
    row = next(x for x in fu["items"] if x["item_id"] == it0["item_id"])
    assert row["reason"] == "stale_started"
    # start item baru dengan lease habis ditolak (renew dulu), tetapi HASIL attempt asal tetap diterima
    rs = start(a, job["id"], att, [full["items"][1]["item_id"]], "inst-A")
    assert rs.status_code == 409 and rs.json()["detail"]["code"] == "LEASE_EXPIRED"
    rr = results(a, job["id"], att, [res_row({**it0, "payload_sha256": it0["payload_sha256"]})])
    assert rr.status_code == 200 and rr.json()["acks"][0]["status"] == "accepted", rr.text
    assert tag_status(it0["tag_id"]) == "active"
    # renew memulihkan lease yang belum diambil alih → item kedua bisa dimulai
    rn = requests.post(f"{API}/rfid/device-jobs/{job['id']}/attempts/{att}/renew", headers=dh(a),
                       json={"instance_id": "inst-A"}, timeout=60)
    assert rn.status_code == 200
    assert start(a, job["id"], att, [full["items"][1]["item_id"]], "inst-A").status_code == 200


def test_reclaim_unstarted_job_is_new_attempt_and_traceable():
    a, b = make_printer(), make_printer()
    isolate_queue(a)
    job = create_job(1)
    att_a = job_of(claim(a), job["id"])["lease"]["attempt_id"]
    DB.rfid_print_jobs.update_one({"id": job["id"]}, {"$set": {"lease.expires_at": "2000-01-01T00:00:00+00:00"}})
    jb = job_of(claim(b), job["id"])
    assert jb and jb["lease"]["attempt_id"] != att_a and jb["print_attempts"] == 2
    att = db_job(job["id"])["attempts"]
    assert att[-1]["kind"] == "reclaim" and att[-1]["previous_attempt_id"] == att_a and att[-1]["device_id"] == b["id"]
    it = db_job(job["id"])["items"][0]
    r = start(a, job["id"], att_a, [it["item_id"]])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LEASE_CONFLICT"
    r2 = requests.post(f"{API}/rfid/device-jobs/{job['id']}/attempts/{att_a}/renew", headers=dh(a), json={}, timeout=60)
    assert r2.status_code == 409


# ─── Hasil per label, parsial, idempotensi ───────────────────────────────────
def _printed_job(n, dev=None):
    dev = dev or make_printer()
    isolate_queue(dev)
    job = create_job(n)
    att = job_of(claim(dev), job["id"])["lease"]["attempt_id"]
    items = db_job(job["id"])["items"]
    assert start(dev, job["id"], att, [i["item_id"] for i in items]).status_code == 200
    return dev, job, att, items


def test_per_label_results_partial_and_follow_up():
    dev, job, att, items = _printed_job(4)
    rows = [res_row(items[0]), res_row(items[1], "confirmed", "failed", error_code="RFID_WRITE"),
            res_row(items[2], "unknown", "unknown", detail="timeout"),
            res_row(items[3], readback_epc=items[3]["epc"])]
    r = results(dev, job["id"], att, rows)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [a["item_status"] for a in body["acks"]] == ["confirmed", "failed", "unknown", "confirmed"]
    assert body["job_status"] == "needs_review" and body["counts"]["confirmed"] == 2
    assert [tag_status(i["tag_id"]) for i in items] == ["active", "pending_print", "pending_print", "active"]
    roll = DB.inventory_rolls.find_one({"id": items[0]["roll_id"]})
    assert roll["journey"]["stage"] == "tag_printed"
    assert DB.inventory_rolls.find_one({"id": items[1]["roll_id"]}).get("journey", {}).get("stage") != "tag_printed"
    assert DB.roll_label_prints.count_documents({"job_id": job["id"]}) == 2
    # ulangan id sama = duplikat; id sama isi beda = konflik idempotensi
    d = results(dev, job["id"], att, [rows[0]]).json()["acks"][0]
    assert d["status"] == "duplicate"
    bad = dict(rows[0], print_status="failed")
    c = results(dev, job["id"], att, [bad]).json()["acks"][0]
    assert c["status"] == "rejected" and c["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    # confirmed tidak dimundurkan oleh hasil lain → ditandai bertentangan (tinjauan)
    late = results(dev, job["id"], att, [res_row(items[0], "failed", "failed")]).json()["acks"][0]
    assert late["status"] == "accepted" and late["item_status"] == "confirmed" and late["conflict"]
    # validasi
    v = results(dev, job["id"], att, [res_row(items[0], "confirmed", "not_applicable")]).json()["acks"][0]
    assert v["status"] == "rejected" and v["error"]["code"] == "SCHEMA_INVALID"
    pm = results(dev, job["id"], att, [dict(res_row(items[2], "confirmed", "confirmed"), payload_sha256="0" * 64)])
    assert pm.json()["acks"][0]["error"]["code"] == "PAYLOAD_MISMATCH"
    assert DB.roll_label_prints.count_documents({"job_id": job["id"]}) == 2
    fu = requests.get(f"{API}/rfid/printers/follow-up", headers=_h(STATE["admin"]), params={"warehouse_id": WH},
                      timeout=60).json()
    mine = {x["item_id"]: x["reason"] for x in fu["items"] if x["job_id"] == job["id"]}
    assert mine == {items[0]["item_id"]: "conflict", items[1]["item_id"]: "failed", items[2]["item_id"]: "unknown"}
    st = requests.get(f"{API}/rfid/device-jobs/{job['id']}/attempts/{att}", headers=dh(dev), timeout=60).json()
    assert st["lease_owned"] is False or st["job_status"] == "needs_review"
    assert [i["status"] for i in st["items"]] == ["confirmed", "failed", "unknown", "confirmed"]
    STATE["partial"] = (dev, job, att, items)


def test_readback_mismatch_is_failed_and_unknown_upgrade():
    dev, job, att, items = _printed_job(2)
    wrong = "F" + items[0]["epc"][1:]
    a = results(dev, job["id"], att, [res_row(items[0], readback_epc=wrong)]).json()["acks"][0]
    assert a["item_status"] == "failed"
    u = results(dev, job["id"], att, [res_row(items[1], "unknown", "unknown")]).json()["acks"][0]
    assert u["item_status"] == "unknown"
    up = results(dev, job["id"], att, [res_row(items[1])]).json()["acks"][0]      # bukti baru dari attempt sama
    assert up["item_status"] == "confirmed" and tag_status(items[1]["tag_id"]) == "active"


def test_results_require_start_and_matching_attempt():
    dev = make_printer()
    isolate_queue(dev)
    job = create_job(1)
    att = job_of(claim(dev), job["id"])["lease"]["attempt_id"]
    it = db_job(job["id"])["items"][0]
    a = results(dev, job["id"], att, [res_row(it)]).json()["acks"][0]
    assert a["status"] == "rejected" and a["error"]["code"] == "NOT_STARTED"
    other = make_printer(WH2)
    assert results(other, job["id"], att, [res_row(it)]).status_code == 403


# ─── Tindak lanjut operator (izin + bukti) ───────────────────────────────────
def test_resolve_requires_permission_and_c72_evidence():
    dev, job, att, items = STATE["partial"]
    unknown = items[2]
    url = f"{API}/rfid/print-jobs/{job['id']}/items/{unknown['item_id']}/resolve"
    staff = _login("warehouse.soreang@kainnusantara.id")
    r = requests.post(url, headers={"Authorization": f"Bearer {staff}"},
                      json={"action": "confirm_success", "note": "sudah dicek", "evidence_type": "c72_scan"}, timeout=60)
    assert r.status_code == 403
    adm = _h(STATE["admin"])
    r = requests.post(url, headers=adm, json={"action": "confirm_success", "note": "dilihat ada", "evidence_type": "visual_check"},
                      timeout=60)
    assert r.status_code == 400 and "Pindai C72" in r.text
    r = requests.post(url, headers=adm, json={"action": "confirm_success", "note": "dipindai", "evidence_type": "c72_scan"},
                      timeout=60)
    assert r.status_code == 400 and "belum pernah terbaca" in r.text
    DB.rfid_verify_sessions.insert_one({"id": f"rvs_TEST_PF_{TAG}_x", "kind": "print_verify", "status": "open",
                                        "scanned_epcs": [unknown["epc"]], "scan_sources": ["device"],
                                        "updated_at": datetime.now(timezone.utc).isoformat()})
    r = requests.post(url, headers=adm, json={"action": "confirm_success", "note": "C72 membaca EPC", "evidence_type": "c72_scan",
                                              "evidence_ref": "sesi uji"}, timeout=60)
    assert r.status_code == 200, r.text
    assert tag_status(unknown["tag_id"]) == "active"
    it = next(i for i in db_job(job["id"])["items"] if i["item_id"] == unknown["item_id"])
    assert it["status"] == "confirmed" and it["resolution"]["evidence"]["read"]["source"] == "verify_session"
    assert it["effects"] == "done"
    assert DB.audit_logs.find_one({"action": "rfid_print_item_resolved", "entity_id": job["id"]})
    r = requests.post(url, headers=adm, json={"action": "confirm_failed", "note": "coba putuskan lagi", "evidence_type": "other"}, timeout=60)
    assert r.status_code == 409          # sudah diputuskan


def test_resolve_failed_reprint_new_epc_old_retired_and_conflict_keep():
    dev, job, att, items = STATE["partial"]
    adm = _h(STATE["admin"])
    failed = items[1]
    r = requests.post(f"{API}/rfid/print-jobs/{job['id']}/items/{failed['item_id']}/resolve", headers=adm,
                      json={"action": "reprint", "note": "label VOID dimusnahkan", "evidence_type": "visual_check"}, timeout=60)
    assert r.status_code == 200, r.text
    rj = r.json()["reprint_job"]
    assert rj["epc"] != failed["epc"]
    old = DB.rfid_tags.find_one({"id": failed["tag_id"]})
    assert old["status"] == "retired" and old["retire_reason"] == "print_failed" and old["replaced_by_tag_id"]
    roll = DB.inventory_rolls.find_one({"id": failed["roll_id"]})
    assert roll["rfid_tag_id"] == old["replaced_by_tag_id"] and tag_status(roll["rfid_tag_id"]) == "pending_print"
    newjob = db_job(rj["id"])
    assert newjob["reprint_of"]["item_id"] == failed["item_id"] and newjob["source"] == "reprint"
    # konflik pada item terkonfirmasi: pertahankan sukses (bukti C72) → tinjauan tertutup
    DB.rfid_verify_sessions.update_one({"id": f"rvs_TEST_PF_{TAG}_x"}, {"$addToSet": {"scanned_epcs": items[0]["epc"]}})
    r = requests.post(f"{API}/rfid/print-jobs/{job['id']}/items/{items[0]['item_id']}/resolve", headers=adm,
                      json={"action": "confirm_success", "note": "hasil gagal itu salah baca", "evidence_type": "c72_scan"},
                      timeout=60)
    assert r.status_code == 200, r.text
    j = db_job(job["id"])
    assert j["review_open"] == 0 and j["status"] == "partial", (j["status"], j["counts"])
    hist = requests.get(f"{API}/rfid/rolls/{failed['roll_id']}/tag-history", headers=adm, timeout=60).json()
    assert {t["status"] for t in hist["tags"]} == {"retired", "pending_print"}
    assert "retired" in {e["event"] for e in hist["events"]}


def test_verify_partial_job_expects_only_confirmed_labels():
    dev, job, att, items = STATE["partial"]
    adm = _h(STATE["admin"])
    s = requests.post(f"{API}/rfid/print-jobs/{job['id']}/verify/start", headers=adm, timeout=60)
    assert s.status_code == 200, s.text
    sess = s.json()
    expected = {e["epc"] for e in sess["expected"]}
    assert expected == {items[0]["epc"], items[2]["epc"], items[3]["epc"]}          # gagal (#2) tidak diharapkan
    requests.post(f"{API}/rfid/verify-sessions/{sess['id']}/scan", headers=adm, json={"epcs": list(expected)}, timeout=60)
    c = requests.post(f"{API}/rfid/verify-sessions/{sess['id']}/complete", headers=adm, timeout=60)
    assert c.status_code == 200 and c.json()["result"] == "clean"
    assert db_job(job["id"])["status"] == "verified"


# ─── Pemulihan efek sesudah status tersimpan (RACC-30) ───────────────────────
def test_effects_failure_after_durable_result_is_recovered_without_reprint(monkeypatch):
    dev, job, att, items = _printed_job(2)
    calls = {"n": 0}
    real = rps._item_effects

    async def boom(j, its):
        calls["n"] += 1
        raise RuntimeError("galat simulasi sesudah status tersimpan")

    monkeypatch.setattr(rps, "_item_effects", boom)
    dev_doc = DB.rfid_devices.find_one({"id": dev["id"]}, {"_id": 0})
    rows = [res_row(i) for i in items]
    out = run(prn.report_results(dev_doc, job["id"], att, rows))
    assert out["effects_pending"] and calls["n"] == 1
    j = db_job(job["id"])
    assert [i["status"] for i in j["items"]] == ["confirmed", "confirmed"] and j["effects_pending"]
    assert all(i["effects"] == "pending" for i in j["items"]) and j.get("effects_error")
    assert [tag_status(i["tag_id"]) for i in items] == ["pending_print", "pending_print"]
    monkeypatch.setattr(rps, "_item_effects", real)
    # jalur 1: connector mengirim ulang hasil yang SAMA (ACK hilang) → efek dilengkapi, tanpa cetak ulang
    r = results(dev, job["id"], att, [rows[0]])
    assert r.json()["acks"][0]["status"] == "duplicate"
    assert tag_status(items[0]["tag_id"]) == "active"
    # jalur 2: sapuan otomatis saat printer menarik antrean / endpoint pemulihan
    rec = requests.post(f"{API}/rfid/printers/recover-effects", headers=_h(STATE["admin"]), params={"warehouse_id": WH},
                        timeout=60)
    assert rec.status_code == 200
    assert [tag_status(i["tag_id"]) for i in items] == ["active", "active"]
    j = db_job(job["id"])
    assert not j["effects_pending"] and all(i["effects"] == "done" for i in j["items"]) and "effects_error" not in j
    assert DB.roll_label_prints.count_documents({"job_id": job["id"]}) == 2      # tidak ganda
    assert DB.rfid_tag_events.count_documents({"event": "activated", "job_id": job["id"]}) == 2


def test_legacy_ack_compat_effects_pending_replay():
    dev = make_printer()
    isolate_queue(dev)
    job = create_job(2)
    pend = requests.get(f"{API}/rfid/device-jobs/pending", headers=dh(dev), timeout=60).json()
    lj = job_of(pend, job["id"])
    att = lj["lease"]["attempt_id"]
    assert all(z["zpl"].startswith("^XA") and "^RFW" in z["zpl"] for z in lj["items"])
    # simulasi crash: status printed tersimpan, efek belum (tag masih pending_print)
    r = requests.post(f"{API}/rfid/device-jobs/{job['id']}/ack", headers=dh(dev), json={"attempt_id": att}, timeout=60)
    assert r.status_code == 200 and r.json()["status"] == "printed"
    j = db_job(job["id"])
    assert all(i["status"] == "confirmed" and i["evidence"]["source"] == "legacy_job_ack" for i in j["items"])
    tid = j["items"][0]["tag_id"]
    DB.rfid_tags.update_one({"id": tid}, {"$set": {"status": "pending_print"}})
    DB.rfid_print_jobs.update_one({"id": job["id"]}, {"$set": {"items.0.effects": "pending", "effects_pending": True}})
    rep = requests.post(f"{API}/rfid/device-jobs/{job['id']}/ack", headers=dh(dev), json={"attempt_id": att}, timeout=60)
    assert rep.status_code == 200 and rep.json()["replay"] and rep.json()["effects_recovered"] == 1
    assert tag_status(tid) == "active"
    # job yang sedang dicetak per label menolak ACK tingkat job
    dev2, job2, att2, _ = _printed_job(1)
    r2 = requests.post(f"{API}/rfid/device-jobs/{job2['id']}/ack", headers=dh(dev2), json={"attempt_id": att2}, timeout=60)
    assert r2.status_code == 409


def test_mark_printed_manual_marks_items():
    job = create_job(1)
    r = requests.post(f"{API}/rfid/print-jobs/{job['id']}/mark-printed", headers=_h(STATE["admin"]), timeout=60)
    assert r.status_code == 200 and r.json()["status"] == "printed"
    it = db_job(job["id"])["items"][0]
    assert it["status"] == "confirmed" and it["evidence"]["source"] == "operator_manual" and it["effects"] == "done"
    # FIX-3b (B2b RFID-3, keputusan K-B2b-13) — tandai tercetak manual = bukti CETAK, bukan bukti CHIP: tag tetap
    # `pending_print` sampai EPC-nya terbaca di sesi verifikasi.
    assert it["encode_status"] == "unverified" and tag_status(it["tag_id"]) == "pending_print"
    _verify_epcs(job["id"], [it["epc"]])
    assert tag_status(it["tag_id"]) == "active"


# ─── Cetak ulang teks vs ganti tag ───────────────────────────────────────────
def _verify_epcs(job_id, epcs):
    """FIX-3b (RFID-3) — bukti chip: sesi verifikasi membaca EPC → tag `pending_print` menjadi `active`."""
    v = requests.post(f"{API}/rfid/print-jobs/{job_id}/verify/start", headers=_h(STATE["admin"]), timeout=60)
    assert v.status_code == 200, v.text
    s = requests.post(f"{API}/rfid/verify-sessions/{v.json()['id']}/scan", headers=_h(STATE["admin"]),
                      json={"epcs": epcs}, timeout=60)
    assert s.status_code == 200, s.text
    c = requests.post(f"{API}/rfid/verify-sessions/{v.json()['id']}/complete", headers=_h(STATE["admin"]), timeout=60)
    assert c.status_code == 200, c.text


def _active_roll(stage="stored"):
    rid = make_roll()
    job = create_job(rolls=[rid])
    requests.post(f"{API}/rfid/print-jobs/{job['id']}/mark-printed", headers=_h(STATE["admin"]), timeout=60)
    _verify_epcs(job["id"], [DB.rfid_tags.find_one({"roll_id": rid})["epc"]])
    tag = DB.rfid_tags.find_one({"roll_id": rid, "status": "active"})
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"journey.stage": stage, "journey.verified_tag_id": tag["id"]}})
    return rid, tag


def test_text_reprint_keeps_epc_without_chip_write():
    rid, tag = _active_roll()
    dev = make_printer()
    isolate_queue(dev)
    r = requests.post(f"{API}/rfid/rolls/{rid}/reprint-label", headers=_h(STATE["admin"]),
                      json={"reason_code": "text_damaged", "note": "teks pudar kena air"}, timeout=60)
    assert r.status_code == 200, r.text
    job = r.json()
    it = job["items"][0]
    assert job["kind"] == "text_reprint" and it["epc"] == tag["epc"] and it["tag_id"] is None
    assert "^RFW" not in it["zpl"] and tag["epc"][-8:] in it["zpl"]
    jd = job_of(claim(dev), job["id"])
    att = jd["lease"]["attempt_id"]
    assert jd["expected_responses"]["readback"] is False
    start(dev, job["id"], att, [it["item_id"]])
    a = results(dev, job["id"], att, [res_row(db_job(job["id"])["items"][0], "confirmed", "not_applicable")]).json()
    assert a["acks"][0]["item_status"] == "confirmed" and a["job_status"] == "printed"
    assert tag_status(tag["id"]) == "active" and DB.inventory_rolls.find_one({"id": rid})["rfid_tag_id"] == tag["id"]
    assert DB.roll_label_prints.find_one({"job_id": job["id"], "kind": "text_reprint"})
    # tanpa tag aktif → ditolak (gunakan cetak tag / ganti tag)
    bare = make_roll()
    r = requests.post(f"{API}/rfid/rolls/{bare}/reprint-label", headers=_h(STATE["admin"]),
                      json={"reason_code": "text_lost", "note": "label hilang"}, timeout=60)
    assert r.status_code == 400
    # izin: cetak ulang teks = wms:print (staf gudang punya), ganti tag = wms:approve (staf gudang tidak)
    from permissions_config import DEFAULT_PERMISSIONS  # noqa: E402
    assert "print" in DEFAULT_PERMISSIONS["warehouse"]["wms"] and "approve" not in DEFAULT_PERMISSIONS["warehouse"]["wms"]


def test_replace_tag_new_epc_old_retired_stage_kept():
    rid, tag = _active_roll("stored")
    adm = _h(STATE["admin"])
    staff = _login("warehouse.soreang@kainnusantara.id")
    r = requests.post(f"{API}/rfid/rolls/{rid}/replace-tag", headers={"Authorization": f"Bearer {staff}"},
                      json={"reason_code": "damaged", "note": "tag sobek"}, timeout=60)
    assert r.status_code == 403
    r = requests.post(f"{API}/rfid/rolls/{rid}/replace-tag", headers=adm, json={"reason_code": "damaged", "note": "x"},
                      timeout=60)
    assert r.status_code == 422          # catatan min. 5 huruf
    r = requests.post(f"{API}/rfid/rolls/{rid}/replace-tag", headers=adm,
                      json={"reason_code": "damaged", "note": "tag sobek terkena forklift"}, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["old_tag"]["epc"] == tag["epc"] and body["new_tag"]["epc"] != tag["epc"]
    old = DB.rfid_tags.find_one({"id": tag["id"]})
    assert old["status"] == "retired" and old["retire_reason"] == "replaced:damaged"
    assert old["replaced_by_tag_id"] == body["new_tag"]["id"]
    roll = DB.inventory_rolls.find_one({"id": rid})
    assert roll["rfid_tag_id"] == body["new_tag"]["id"] and roll["journey"]["stage"] == "stored"
    assert "verified_tag_id" not in roll["journey"]
    assert body["job"]["source"] == "retag" and db_job(body["job"]["id"])["replaces_epc"] == tag["epc"]
    # tag baru masih dalam antrean → ganti lagi ditolak sampai job selesai
    r = requests.post(f"{API}/rfid/rolls/{rid}/replace-tag", headers=adm,
                      json={"reason_code": "lost", "note": "salah klik lagi"}, timeout=60)
    assert r.status_code == 409
    assert DB.audit_logs.find_one({"action": "rfid_tag_replaced", "entity_id": rid})
    # EPC lama tidak pernah terbit lagi
    assert DB.rfid_tags.count_documents({"epc": tag["epc"]}) == 1


def test_replace_tag_blocked_during_active_movement():
    rid, tag = _active_roll()
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"active_movement": {"id": "mv_TEST", "number": "TRF-UJI"}}})
    r = requests.post(f"{API}/rfid/rolls/{rid}/replace-tag", headers=_h(STATE["admin"]),
                      json={"reason_code": "damaged", "note": "tag rusak saat transfer"}, timeout=60)
    assert r.status_code == 409 and "TRF-UJI" in r.text
    assert tag_status(tag["id"]) == "active"


# ─── Profil printer, pratinjau, telemetri ────────────────────────────────────
def test_profile_300dpi_rerenders_at_claim_and_permissions():
    dev = make_printer()
    isolate_queue(dev)
    adm = {"Authorization": f"Bearer {STATE['admin']}"}
    bad = requests.put(f"{API}/rfid/printers/{dev['id']}/profile", headers=adm, json={"profile": {"dpi": 600}}, timeout=60)
    assert bad.status_code == 400
    wh = _login("wh.admin@kainnusantara.id")
    r = requests.put(f"{API}/rfid/printers/{dev['id']}/profile", headers={"Authorization": f"Bearer {wh}"},
                     json={"profile": {"dpi": 300}}, timeout=60)
    assert r.status_code == 403
    r = requests.put(f"{API}/rfid/printers/{dev['id']}/profile", headers=adm,
                     json={"profile": {"dpi": 300, "offset_x_dots": 12, "rfid_position": "F2"},
                           "connection": {"host": "192.168.10.21", "port": 9100}}, timeout=60)
    assert r.status_code == 200 and r.json()["profile"]["dpi"] == 300
    job = create_job(1)
    jd = job_of(claim(dev), job["id"])
    z = jd["items"][0]["zpl"]
    assert "^PW827" in z and "^LH12,0" in z and "^RS8,F2" in z
    assert jd["items"][0]["payload_sha256"] == hashlib.sha256(z.encode()).hexdigest()
    cfg = requests.get(f"{API}/rfid/printer-agent/config", headers=dh(dev), timeout=60).json()
    assert cfg["printer_profile"]["dpi"] == 300 and cfg["contract"] == "kn-printer-1"
    pv = requests.post(f"{API}/rfid/printers/label-preview", headers=_h(STATE["admin"]),
                       json={"job_id": job["id"], "item_id": jd["items"][0]["item_id"], "device_id": dev["id"]}, timeout=60)
    assert pv.status_code == 200 and pv.json()["layout"]["width_dots"] == 827 and pv.json()["zpl"].startswith("^XA")


def test_telemetry_separates_connector_from_printer_and_flags_double_connector():
    dev = make_printer()
    t = requests.post(f"{API}/rfid/printer-agent/telemetry", headers=dh(dev), json={
        "instance_id": "inst-1", "connector": {"version": "0.1.0", "host": "PC-GUDANG", "ledger": {"pending_results": 2}},
        "printer": {"state": "paper_out", "reachable": True, "detail": "kertas habis"}}, timeout=60)
    assert t.status_code == 200 and not t.json()["conflict"]
    ps = requests.get(f"{API}/rfid/printer-status", headers=_h(STATE["admin"]), params={"warehouse_id": WH}, timeout=60).json()
    p = next(x for w in ps["warehouses"] for x in w["printers"] if x["id"] == dev["id"])
    assert p["online"] is True and p["printer_state"] == "paper_out" and p["printer_ready"] is False
    assert p["connector"]["host"] == "PC-GUDANG"
    t2 = requests.post(f"{API}/rfid/printer-agent/telemetry", headers=dh(dev), json={
        "instance_id": "inst-2", "connector": {}, "printer": {"state": "ready", "reachable": True}}, timeout=60)
    assert t2.json()["conflict"] is True
    q = requests.get(f"{API}/rfid/printers/queue", headers=_h(STATE["admin"]), params={"warehouse_id": WH}, timeout=60)
    assert q.status_code == 200 and "status_counts" in q.json()


def test_device_endpoints_auth_and_type_guards():
    assert requests.post(f"{API}/rfid/device-jobs/claim", json={}, timeout=30).status_code == 401
    assert requests.get(f"{API}/rfid/printer-agent/config", headers={"X-Device-Key": "dk_nope"}, timeout=30).status_code == 401
    gate_key = f"dk_TEST_PF_{TAG}_gate"
    gid = f"rdev_TEST_PF_{TAG}_gate"
    DB.rfid_devices.insert_one({"id": gid, "code": f"PFG-{TAG}", "name": "Gate uji", "type": "gate", "direction": "in",
                                "warehouse_id": WH, "enabled": True, "api_key_hash": hashlib.sha256(gate_key.encode()).hexdigest()})
    DEVICES.append({"id": gid})
    assert requests.post(f"{API}/rfid/device-jobs/claim", headers={"X-Device-Key": gate_key}, json={},
                         timeout=30).status_code == 400
    assert requests.post(f"{API}/rfid/printer-agent/telemetry", headers={"X-Device-Key": gate_key}, json={},
                         timeout=30).status_code == 400
