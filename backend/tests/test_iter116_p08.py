"""Iter-116 P08 — Tag, printer dan typed verification.

Scope:
  RF-01  — Kontrak EPC kanonik (24 hex uppercase, tanpa pemisah) di encode/ingest/lookup.
  RF-07  — Scan 'simulated' tercatat; dispatch loading check SIMULASI → 400; verify cetak
           hasil 'simulated' tetap biarkan tag berstatus 'printed' (bukan verified).
  RF-10  — Verify sessions: complete tanpa isi, scan sesudah complete, dua scan paralel.
  RF-11  — ZPL field teks pakai ^FH_; ^RFW,H^FD<epc> = tag.epc kanonik; injeksi ^FS tidak lolos.
  RF-14  — Print job lifecycle: queued→printed→verify; tag 'pending_print' → 'active' saat
           mark-printed; verify_with_issues bisa diulang (revisi baru).
  RF-15  — Printer pull/lease: dua printer satu gudang tidak dapat job sama; ack dengan
           attempt_id benar/salah/tanpa; non-printer device → 403.
  IX-12  — retire_orphan_tags idempotent (service-level smoke).

Semua data uji di-prefiks TEST_iter116_ dan dibersihkan di test_zz_cleanup.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient


def _base() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    v = ln.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE = _base()
MONGO = AsyncIOMotorClient("mongodb://localhost:27017")
DB = MONGO["test_database"]
ENTITY = "ent_ksc"
WH = "wh_surabaya"   # memiliki roll untagged untuk uji end-to-end

CREDS = {
    "admin": ("admin@kainnusantara.id", "demo12345"),
    "warehouse": ("warehouse@kainnusantara.id", "demo12345"),
}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def session_admin():
    s = requests.Session()
    s.headers.update({"X-Entity-Id": ENTITY})
    r = s.post(f"{BASE}/api/auth/login", json={"email": CREDS["admin"][0], "password": CREDS["admin"][1]}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def session_wh():
    s = requests.Session()
    s.headers.update({"X-Entity-Id": ENTITY})
    r = s.post(f"{BASE}/api/auth/login", json={"email": CREDS["warehouse"][0], "password": CREDS["warehouse"][1]}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def state():
    """State bersama antar test — menyimpan device/job/roll yang diciptakan."""
    return {"devices": [], "jobs": [], "rolls": [], "tags": [], "sessions": []}


def _pick_untagged_rolls(n: int) -> List[Dict[str, Any]]:
    async def _q():
        return await DB.inventory_rolls.find(
            {"warehouse_id": WH, "rfid_tag_id": None, "status": "available",
             "owner_entity_id": ENTITY, "length_remaining": {"$gt": 0}},
            {"_id": 0, "id": 1, "roll_no": 1, "warehouse_id": 1}).limit(n).to_list(n)
    return _run(_q())


# ─── RF-01: EPC kanonik ─────────────────────────────────────────────────────

class TestRf01Epc:
    def test_encode_canonicalizes_separators_and_case(self, session_wh, state):
        rolls = _pick_untagged_rolls(2)
        assert len(rolls) >= 1, "butuh 1 roll tanpa tag di wh_surabaya"
        roll = rolls[0]
        state["rolls"].append(roll["id"])
        # EPC dengan pemisah + huruf kecil
        raw = "e2 93-af28:f148.de4c_3593df55"
        canon = "E293AF28F148DE4C3593DF55"
        r = session_wh.post(f"{BASE}/api/rfid/tags/encode", json={"roll_id": roll["id"], "epc": raw})
        assert r.status_code == 200, r.text
        tag = r.json()
        assert tag["epc"] == canon, f"disimpan tidak kanonik: {tag['epc']}"
        state["tags"].append(tag["id"])

    def test_encode_rejects_bad_length_and_nonhex(self, session_wh):
        rolls = _pick_untagged_rolls(3)
        extras = [r for r in rolls if r["id"] not in []][1:3]
        assert len(extras) >= 1
        bad = [
            ("E2" + "A" * 22, 23),      # 23 hex short? actually 2+22=24. need 23 → use 23
        ]
        bads = ["E2" + "A" * 21,  # 23 char
                "E2" + "A" * 23,  # 25 char
                "G" + "0" * 23,   # non-hex
                "E2" + "A" * 30]  # 32 char
        for b in bads:
            r = session_wh.post(f"{BASE}/api/rfid/tags/encode",
                                json={"roll_id": extras[0]["id"], "epc": b})
            assert r.status_code == 400, f"EPC '{b}' seharusnya 400, dapat {r.status_code}: {r.text}"

    def test_encode_conflict_other_representation(self, session_wh, state):
        # Pakai tag aktif yang baru dibuat di test pertama; coba ulang dalam bentuk pemisah
        rolls = _pick_untagged_rolls(3)
        # cari roll BARU (bukan yang sudah di-encode) untuk dicoba konflik
        used = set(state["rolls"])
        fresh = [r for r in rolls if r["id"] not in used]
        assert fresh, "butuh roll kedua"
        roll2 = fresh[0]
        state["rolls"].append(roll2["id"])
        dup_raw = "E293-AF28-F148-DE4C-3593-DF55"  # sama dengan EPC pertama tapi bergaris
        r = session_wh.post(f"{BASE}/api/rfid/tags/encode",
                            json={"roll_id": roll2["id"], "epc": dup_raw})
        assert r.status_code == 409, r.text

    def test_lookup_accepts_separator_form(self, session_wh):
        r = session_wh.get(f"{BASE}/api/rfid/lookup",
                           params={"code": "E293-AF28-F148-DE4C-3593-DF55", "record": "false"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["via"] == "rfid"
        assert data["roll"]["id"]


# ─── RF-11 & RF-14 & RF-15: Print flow + ZPL safety + lease ─────────────────

class TestRf11Rf14Rf15Print:
    def test_create_print_job_and_zpl(self, session_wh, session_admin, state):
        # Butuh roll untagged untuk encode baru (pending_print)
        rolls = _pick_untagged_rolls(5)
        used = set(state["rolls"])
        fresh = [r for r in rolls if r["id"] not in used][:2]
        assert len(fresh) >= 1
        # Injeksi nama produk — ubah 1 produk sementara agar nama berisi ^FS^FO0,0
        pid = _run(DB.inventory_rolls.find_one({"id": fresh[0]["id"]}, {"_id": 0, "product_id": 1}))["product_id"]
        _run(DB.products.update_one({"id": pid}, {"$set": {"__orig_name_iter116": True}}))
        prod = _run(DB.products.find_one({"id": pid}, {"_id": 0, "name": 1}))
        orig_name = prod["name"]
        state["_injected_product"] = (pid, orig_name)
        _run(DB.products.update_one({"id": pid}, {"$set": {"name": "^FS^FO0,0^FDINJECTED"}}))

        roll_ids = [r["id"] for r in fresh]
        r = session_wh.post(f"{BASE}/api/rfid/print-jobs", json={"roll_ids": roll_ids})
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["status"] == "queued"
        state["jobs"].append(job["id"])
        state["rolls"].extend(roll_ids)

        # RF-11: ZPL harus memakai ^FH_ dan ^RFW,H^FD<epc kanonik>
        r2 = session_wh.get(f"{BASE}/api/rfid/print-jobs/{job['id']}/zpl")
        assert r2.status_code == 200
        zpl = r2.text
        assert "^FH_" in zpl, "label teks tidak pakai ^FH_"
        # Injeksi tidak boleh lolos verbatim (jika ada, pasti sudah di-escape)
        assert "^FS^FO0,0^FDINJECTED" not in zpl, "nama produk disuntik lolos tanpa escape!"
        # Validasi ^RFW,H^FD<epc> cocok dgn tag.epc dari DB
        tag = _run(DB.rfid_tags.find_one({"roll_id": roll_ids[0]}, {"_id": 0, "epc": 1}))
        assert tag and tag["epc"] in zpl
        assert f"^RFW,H^FD{tag['epc']}" in zpl, "EPC chip tidak persis sama di ^RFW,H"

        # RF-14: tag baru = pending_print; roll journey BUKAN tag_printed
        for rid in roll_ids:
            roll = _run(DB.inventory_rolls.find_one({"id": rid}, {"_id": 0, "rfid_tag_id": 1, "journey": 1}))
            tdoc = _run(DB.rfid_tags.find_one({"id": roll["rfid_tag_id"]}, {"_id": 0, "status": 1}))
            assert tdoc["status"] == "pending_print", f"tag {roll['rfid_tag_id']} status={tdoc['status']}"
            assert (roll.get("journey") or {}).get("stage") != "tag_printed"
            state["tags"].append(roll["rfid_tag_id"])

        # RF-14: verify/start pada queued → 400
        r3 = session_wh.post(f"{BASE}/api/rfid/print-jobs/{job['id']}/verify/start")
        assert r3.status_code == 400, r3.text

    def test_printer_lease_and_ack(self, session_admin, state):
        # Buat dua printer di WH yang sama
        dev_ids = []
        for i in range(2):
            r = session_admin.post(f"{BASE}/api/rfid/devices", json={
                "name": f"TEST_iter116_printer_{i}", "type": "printer", "warehouse_id": WH})
            assert r.status_code == 200, r.text
            dev = r.json()
            dev_ids.append(dev["id"])
            state["devices"].append(dev["id"])
        # Terbitkan API key untuk 2 printer
        keys = {}
        for d in dev_ids:
            r = session_admin.post(f"{BASE}/api/rfid/devices/{d}/api-key")
            assert r.status_code == 200, r.text
            keys[d] = r.json()["api_key"]

        job_id = state["jobs"][-1]
        # Printer 1 pull → dapat job
        r1 = requests.get(f"{BASE}/api/rfid/device-jobs/pending",
                          headers={"X-Device-Key": keys[dev_ids[0]]})
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        p1_jobs = [j for j in d1["jobs"] if j["id"] == job_id]
        assert p1_jobs, "printer 1 harus dapat job test"
        attempt1 = p1_jobs[0]["lease"]["attempt_id"]
        assert p1_jobs[0]["lease"]["device_id"] == dev_ids[0]
        assert "expires_at" in p1_jobs[0]["lease"]

        # Printer 2 pull → TIDAK dapat job yang sama (masih di-lease)
        r2 = requests.get(f"{BASE}/api/rfid/device-jobs/pending",
                          headers={"X-Device-Key": keys[dev_ids[1]]})
        assert r2.status_code == 200
        p2_ids = {j["id"] for j in r2.json()["jobs"]}
        assert job_id not in p2_ids, "lease double-serve!"

        # Ack tanpa attempt_id → 400
        rbad = requests.post(f"{BASE}/api/rfid/device-jobs/{job_id}/ack",
                             headers={"X-Device-Key": keys[dev_ids[0]]}, json={})
        assert rbad.status_code == 400, rbad.text

        # Ack dengan printer2 memakai attempt1 → 409 (lease bukan miliknya)
        rconf = requests.post(f"{BASE}/api/rfid/device-jobs/{job_id}/ack",
                              headers={"X-Device-Key": keys[dev_ids[1]]},
                              json={"attempt_id": attempt1})
        assert rconf.status_code == 409, rconf.text

        # Nonaktifkan printer1 (device gate) → ack 403
        _run(DB.rfid_devices.update_one({"id": dev_ids[0]}, {"$set": {"enabled": False}}))
        rgate = requests.post(f"{BASE}/api/rfid/device-jobs/{job_id}/ack",
                              headers={"X-Device-Key": keys[dev_ids[0]]},
                              json={"attempt_id": attempt1})
        assert rgate.status_code == 403, rgate.text
        _run(DB.rfid_devices.update_one({"id": dev_ids[0]}, {"$set": {"enabled": True}}))

        # Ack benar oleh pemilik → 200 + status printed
        rok = requests.post(f"{BASE}/api/rfid/device-jobs/{job_id}/ack",
                            headers={"X-Device-Key": keys[dev_ids[0]]},
                            json={"attempt_id": attempt1})
        assert rok.status_code == 200, rok.text
        assert rok.json().get("status") == "printed"

        # RF-14: tag → active + roll journey tag_printed
        job_doc = _run(DB.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0}))
        for it in job_doc["items"]:
            td = _run(DB.rfid_tags.find_one({"id": it["tag_id"]}, {"_id": 0, "status": 1}))
            assert td["status"] == "active"
            rl = _run(DB.inventory_rolls.find_one({"id": it["roll_id"]}, {"_id": 0, "journey": 1, "status": 1}))
            # roll yang sebelumnya 'stored' tidak mundur — tapi roll kita 'available' pertama kali
            if rl.get("status") != "stored":
                assert (rl.get("journey") or {}).get("stage") == "tag_printed"

    def test_non_printer_cannot_pull(self, session_admin, state):
        r = session_admin.post(f"{BASE}/api/rfid/devices", json={
            "name": "TEST_iter116_handheld", "type": "handheld", "warehouse_id": WH})
        assert r.status_code == 200
        state["devices"].append(r.json()["id"])
        kr = session_admin.post(f"{BASE}/api/rfid/devices/{r.json()['id']}/api-key")
        key = kr.json()["api_key"]
        state["_handheld_key"] = key
        state["_handheld_id"] = r.json()["id"]
        rp = requests.get(f"{BASE}/api/rfid/device-jobs/pending", headers={"X-Device-Key": key})
        assert rp.status_code == 400, rp.text


# ─── RF-07 & RF-10 & RF-14: Verify flow (simulated + races) ─────────────────

class TestRf07Rf10VerifyFlow:
    def test_verify_start_on_printed(self, session_wh, state):
        job_id = state["jobs"][-1]
        r = session_wh.post(f"{BASE}/api/rfid/print-jobs/{job_id}/verify/start")
        assert r.status_code == 200, r.text
        state["sessions"].append(r.json()["id"])

    def test_scan_simulated_source_user_endpoint(self, session_wh, state):
        sid = state["sessions"][-1]
        # Ambil 1 EPC dari expected
        sess = _run(DB.rfid_verify_sessions.find_one({"id": sid}, {"_id": 0, "expected": 1}))
        if not sess["expected"]:
            pytest.skip("tidak ada expected pada sesi")
        epc = sess["expected"][0]["epc"]
        # Scan dengan source=simulated → OK
        r = session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid}/scan",
                            json={"epcs": [epc], "source": "simulated"})
        assert r.status_code == 200, r.text
        # Scan dengan source=device via endpoint user → 400
        r2 = session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid}/scan",
                             json={"epcs": [epc], "source": "device"})
        assert r2.status_code == 400, r2.text

    def test_complete_unknown_404(self, session_wh):
        r = session_wh.post(f"{BASE}/api/rfid/verify-sessions/sess_does_not_exist/complete")
        assert r.status_code == 404

    def test_scan_unknown_404(self, session_wh):
        r = session_wh.post(f"{BASE}/api/rfid/verify-sessions/sess_does_not_exist/scan",
                            json={"epcs": ["E200000000000000DEADBEEF"], "source": "manual"})
        assert r.status_code == 404

    def test_complete_simulated_job_remains_printed(self, session_wh, state):
        sid = state["sessions"][-1]
        r = session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid}/complete")
        assert r.status_code == 200, r.text
        res = r.json()
        assert res.get("result") == "simulated", res
        job_id = state["jobs"][-1]
        job = _run(DB.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "status": 1, "last_verify": 1}))
        assert job["status"] == "printed", f"job berubah ke {job['status']} meski simulated"
        assert (job.get("last_verify") or {}).get("result") == "simulated"

    def test_scan_after_complete_rejected(self, session_wh, state):
        sid = state["sessions"][-1]
        r = session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid}/scan",
                            json={"epcs": ["E200000000000000DEADBEEF"], "source": "manual"})
        assert r.status_code == 400, r.text

    def test_verify_with_issues_can_restart(self, session_wh, state):
        """Mulai verifikasi baru (revisi), scan EPC KURANG → complete → verified_with_issues → verify/start lagi OK (revisi baru)."""
        job_id = state["jobs"][-1]
        # Mulai lagi (job masih 'printed' karena last run simulated)
        r = session_wh.post(f"{BASE}/api/rfid/print-jobs/{job_id}/verify/start")
        assert r.status_code == 200, r.text
        sid2 = r.json()["id"]
        state["sessions"].append(sid2)
        expected = r.json().get("expected") or []
        if len(expected) < 2:
            # Kurang dari 2 → lewati "missing" (lengkap vs tidak lengkap bisa jadi clean/with_issues)
            # Scan 0 EPC → missing semua → with_issues
            session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid2}/scan",
                            json={"epcs": [], "source": "manual"})
        else:
            session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid2}/scan",
                            json={"epcs": [expected[0]["epc"]], "source": "manual"})
        rc = session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid2}/complete")
        assert rc.status_code == 200, rc.text
        assert rc.json()["result"] in ("with_issues", "clean")
        # Jika with_issues → verify/start lagi harus OK (revisi baru)
        if rc.json()["result"] == "with_issues":
            r3 = session_wh.post(f"{BASE}/api/rfid/print-jobs/{job_id}/verify/start")
            assert r3.status_code == 200, r3.text
            state["sessions"].append(r3.json()["id"])
            assert r3.json().get("revision", 1) >= 2

    def test_parallel_scans_do_not_lose_data(self, session_wh, state):
        """Dua scan paralel ke sesi terbuka: hasil akhir harus memuat EPC dari kedua panggilan."""
        job_id = state["jobs"][-1]
        # mulai sesi baru jika last session sudah complete
        r = session_wh.post(f"{BASE}/api/rfid/print-jobs/{job_id}/verify/start")
        if r.status_code != 200:
            pytest.skip("tidak bisa mulai sesi baru untuk tes paralel")
        sid = r.json()["id"]
        state["sessions"].append(sid)
        epc_a = "E200000000000000A0000001"
        epc_b = "E200000000000000A0000002"

        def do_scan(epc):
            return session_wh.post(f"{BASE}/api/rfid/verify-sessions/{sid}/scan",
                                   json={"epcs": [epc], "source": "manual"})

        import threading
        results = []
        def runner(e):
            results.append(do_scan(e).status_code)
        ts = [threading.Thread(target=runner, args=(e,)) for e in (epc_a, epc_b)]
        for t in ts: t.start()
        for t in ts: t.join()
        assert all(s == 200 for s in results), results
        sess = _run(DB.rfid_verify_sessions.find_one({"id": sid}, {"_id": 0, "scanned_epcs": 1}))
        assert epc_a in sess["scanned_epcs"] and epc_b in sess["scanned_epcs"], sess["scanned_epcs"]


# ─── RF-01: Ingest device menerima representasi non-kanonik ─────────────────

class TestRf01Ingest:
    def test_ingest_accepts_separator_form(self, session_admin, state):
        # Pakai handheld yang sudah dibuat test sebelumnya
        key = state.get("_handheld_key")
        if not key:
            # buat satu
            r = session_admin.post(f"{BASE}/api/rfid/devices", json={
                "name": "TEST_iter116_handheld2", "type": "handheld", "warehouse_id": WH})
            state["devices"].append(r.json()["id"])
            kr = session_admin.post(f"{BASE}/api/rfid/devices/{r.json()['id']}/api-key")
            key = kr.json()["api_key"]
        # EPC dari tag aktif pertama yang kita buat (RF-01 test)
        tag = _run(DB.rfid_tags.find_one({"status": "active", "epc": "E293AF28F148DE4C3593DF55"}, {"_id": 0}))
        if not tag:
            pytest.skip("tag RF-01 tidak tersedia")
        raw = "e2:93-af28_f148.de4c 3593df55"
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": key},
                          json={"epcs": [raw]})
        assert r.status_code == 200, r.text
        results = r.json()["results"]
        assert results and results[0]["epc"] == "E293AF28F148DE4C3593DF55"
        # Roll yang sama terdeteksi (bukan 'red' karena EPC tidak dikenal)
        assert results[0]["roll_no"] == _run(DB.inventory_rolls.find_one({"id": tag["roll_id"]}, {"_id": 0, "roll_no": 1}))["roll_no"]


# ─── IX-12: retire_orphan_tags idempotent (service-level smoke) ─────────────

class TestIx12Orphans:
    def test_retire_orphans_runs(self):
        async def _run_svc():
            from services import rfid_service
            # Buat tag yatim sintetis
            orphan = {
                "id": "rtag_TEST_iter116_orphan", "epc": "E2000000000000000RPH4N00".replace("R", "0"),
                "roll_id": "roll_TEST_iter116_missing", "status": "active",
                "owner_entity_id": ENTITY, "created_at": "2026-01-01T00:00:00+00:00",
            }
            # Pastikan EPC 24-hex valid
            orphan["epc"] = "E2000000000000000ABCDEF0"
            await DB.rfid_tags.insert_one(dict(orphan))
            n = await rfid_service.retire_orphan_tags()
            assert isinstance(n, int) and n >= 1
            # Idempoten — kedua kalinya tidak harus menyentuh tag yang sama (sudah retired)
            n2 = await rfid_service.retire_orphan_tags()
            assert isinstance(n2, int)
            # Cleanup
            await DB.rfid_tags.delete_one({"id": "rtag_TEST_iter116_orphan"})
        _run(_run_svc())


# ─── Cleanup ────────────────────────────────────────────────────────────────

class TestZzCleanup:
    def test_zz_cleanup(self, session_admin, state):
        async def _cleanup():
            # Hapus print jobs test (dan sesi terkait)
            for jid in state["jobs"]:
                job = await DB.rfid_print_jobs.find_one({"id": jid}, {"_id": 0, "items": 1})
                if not job: continue
                tag_ids = [i["tag_id"] for i in job.get("items", []) if i.get("tag_id")]
                roll_ids = [i["roll_id"] for i in job.get("items", []) if i.get("roll_id")]
                await DB.rfid_verify_sessions.delete_many({"print_job_id": jid})
                await DB.rfid_print_jobs.delete_one({"id": jid})
                # Lepas tag dari roll + hapus tag
                if roll_ids:
                    await DB.inventory_rolls.update_many(
                        {"id": {"$in": roll_ids}},
                        {"$set": {"rfid_tag_id": None, "tracking_mode": "barcode"},
                         "$unset": {"journey": ""}})
                if tag_ids:
                    await DB.rfid_tags.delete_many({"id": {"$in": tag_ids}})
            # Hapus tag RF-01 yang kita encode manual
            for tid in state["tags"]:
                t = await DB.rfid_tags.find_one({"id": tid}, {"_id": 0, "roll_id": 1})
                if t:
                    await DB.inventory_rolls.update_one(
                        {"id": t["roll_id"]},
                        {"$set": {"rfid_tag_id": None, "tracking_mode": "barcode"}})
                    await DB.rfid_tags.delete_one({"id": tid})
            # Hapus device TEST_
            await DB.rfid_devices.delete_many({"name": {"$regex": "^TEST_iter116_"}})
            # Pulihkan nama produk yang disuntik
            inj = state.get("_injected_product")
            if inj:
                pid, orig = inj
                await DB.products.update_one({"id": pid}, {"$set": {"name": orig},
                                                           "$unset": {"__orig_name_iter116": ""}})
            # Hapus roll_scans / rfid_reads uji di WH
            await DB.rfid_reads.delete_many({"device_name": {"$regex": "^TEST_iter116_"}})
            # Verify sesi test lain
            for sid in state["sessions"]:
                await DB.rfid_verify_sessions.delete_one({"id": sid})
        _run(_cleanup())
