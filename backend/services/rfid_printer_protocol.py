"""PREP-F — protokol perangkat printer label RFID (connector PC gudang ↔ ERP), kontrak `kn-printer-1`.

Kompatibel dengan kontrak lama (`GET /rfid/device-jobs/pending` + `POST …/ack` tingkat job) dan menambah:
  · lease STABIL — tarik ulang oleh printer (dan instance connector) pemilik lease → attempt SAMA, tanpa spool ulang,
    tanpa menaikkan `print_attempts`; instance connector lain dengan key sama → konflik (tidak dikirimi);
  · perpanjang lease (`renew`) tanpa mengganti attempt; reclaim hanya bila lease habis DAN tidak ada item `started`;
  · start barrier per item (`start`) — item `started` tidak pernah dialihkan otomatis ke printer lain;
  · hasil PER LABEL (`results`) idempoten per `result_event_id`; job parsial; hasil bertentangan → tinjauan;
  · status attempt untuk pemulihan connector sesudah crash / ACK hilang;
  · config profil printer & telemetri (kesehatan PRINTER terpisah dari heartbeat CONNECTOR).
Semua bukti fisik (cetak/encode) berasal dari connector; ERP tidak pernah menyimpulkan sukses dari HTTP/socket.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db
from core_utils import new_id, now_iso, safe_doc
from services import rfid_label_template as tpl
from services import rfid_print_service as rps

CONTRACT = "kn-printer-1"
LEASE_SECONDS = 300
KIND_CAPABILITY = {"rfid_tag": "rfid", "qr_label": "qr", "text_reprint": "rfid"}
POLICIES = {"lease_seconds": LEASE_SECONDS, "renew_before_s": 90, "poll_interval_s": 5, "heartbeat_interval_s": 30,
            "telemetry_interval_s": 30, "status_probe_timeout_s": 3, "outcome_timeout_s": 45,
            "pause_wait_s": 600, "max_jobs_per_claim": 1}
PRINTER_STATES = ("ready", "printing", "paused", "paper_out", "ribbon_out", "head_open", "rfid_error", "error",
                  "offline", "unknown")
MAX_RESULTS_PER_ITEM = 20


def _err(status: int, code: str, message: str, retryable: bool = False) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, "retryable": retryable})


def _caps(device: Dict[str, Any]) -> List[str]:
    return list(device.get("capabilities") or ["rfid", "qr"])


def _assert_printer(device: Dict[str, Any], *, pull: bool = False) -> None:
    if device.get("type") != "printer":
        if pull:
            raise HTTPException(status_code=400, detail="Device bukan printer")
        raise HTTPException(status_code=403, detail="Hanya device printer yang boleh mengakui cetak")


def device_profile(device: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return tpl.normalize_profile(device.get("printer_profile"))
    except ValueError:
        return tpl.normalize_profile(None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job_view(job: Dict[str, Any], profile: Dict[str, Any], *, redelivered: bool) -> Dict[str, Any]:
    """Bentuk job untuk connector: item + payload yang BOLEH dicetak (hanya item pending membawa ZPL baru)."""
    rfid = job.get("kind") in rps.RFID_WRITE_KINDS
    items = []
    for it in job.get("items") or []:
        row = {k: it.get(k) for k in ("item_id", "roll_id", "roll_no", "tag_id", "epc", "sku", "product_name", "lot",
                                      "qty", "unit", "status", "attempt_id", "payload_sha256", "profile_key")}
        row["zpl"] = it.get("zpl", "")
        row["printable"] = it.get("status") == "pending"
        items.append(row)
    started = any(i.get("status") == "started" for i in job.get("items") or [])
    return safe_doc({
        "id": job["id"], "job_number": job.get("job_number"), "kind": job.get("kind"), "revision": job.get("revision") or 1,
        "warehouse_id": job.get("warehouse_id"), "owner_entity_id": job.get("owner_entity_id"),
        "status": job.get("status"), "lease": job.get("lease"), "print_attempts": job.get("print_attempts", 0),
        "items": items, "item_count": job.get("item_count", len(items)), "redelivered": redelivered,
        "attempt_state": "started" if started else "claimed",
        "expected_responses": tpl.expected_responses(profile, rfid), "created_at": job.get("created_at")})


async def _render_for_claim(job: Dict[str, Any], profile: Dict[str, Any], attempt_id: str) -> Dict[str, Any]:
    """Payload dirender dari SNAPSHOT item (bukan data roll terbaru) dengan profil printer pengklaim."""
    if job.get("kind") not in rps.PROFILE_KINDS:
        return job
    pkey = tpl.profile_key(profile)
    items, changed = [], False
    for it in job.get("items") or []:
        if it.get("status") == "pending" and it.get("profile_key") != pkey:
            zpl = rps.render_item(job["kind"], it, profile)
            it = {**it, "zpl": zpl, "payload_sha256": tpl.payload_sha256(zpl), "profile_key": pkey}
            changed = True
        items.append(it)
    if not changed:
        return job
    res = await db.rfid_print_jobs.find_one_and_update(
        {"id": job["id"], "lease.attempt_id": attempt_id, "items.status": {"$nin": ["started"]}},
        {"$set": {"items": items}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    return res or job


async def claim_jobs(device: Dict[str, Any], limit: int = 5, instance_id: Optional[str] = None) -> Dict[str, Any]:
    """RF-15 + PREP-F — klaim lease atomik per job. Tarik ulang oleh pemilik lease = attempt SAMA (redelivered)."""
    _assert_printer(device, pull=True)
    limit = max(1, min(int(limit or 5), 5))
    instance_id = (instance_id or "").strip()[:80] or None
    try:  # pemulihan efek yang tertunda di gudang ini (crash di antara status & efek) — murah, idempoten
        await rps.recover_pending_effects(device.get("warehouse_id"), limit=10)
    except Exception:  # noqa: BLE001
        pass
    kinds = [k for k, c in KIND_CAPABILITY.items() if c in _caps(device)]
    profile = device_profile(device)
    now = _now()
    now_s = now.isoformat()
    jobs: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    seen: List[str] = []
    # 1) redelivery — job yang lease-nya MASIH milik printer ini (attempt tetap, tidak spool ulang, tidak +percobaan)
    async for job in db.rfid_print_jobs.find(
            {"warehouse_id": device.get("warehouse_id"), "lease.device_id": device["id"],
             "lease.expires_at": {"$gte": now_s}, "status": {"$in": list(rps.OPEN_PRINT_PHASE)}},
            {"_id": 0}).sort("created_at", 1).limit(limit):
        seen.append(job["id"])
        if (job["lease"].get("instance_id") or None) != instance_id:
            conflicts.append({"job_id": job["id"], "code": "LEASE_OTHER_INSTANCE",
                              "message": "Job sedang dikerjakan connector lain dengan key printer yang sama."})
            continue
        job = await rps.ensure_item_ids(job)
        jobs.append(_job_view(job, profile, redelivered=True))
    if conflicts:
        await db.rfid_devices.update_one({"id": device["id"]}, {"$set": {"connector_conflict": {
            "at": now_s, "instance_id": instance_id, "jobs": [c["job_id"] for c in conflicts]}}})
    # 2) klaim baru — queued/printing tanpa lease hidup DAN tanpa item started (item started tidak dialihkan)
    while len(jobs) < limit:
        attempt_id = new_id("patt")
        lease = {"device_id": device["id"], "device_name": device.get("name") or device.get("code"),
                 "attempt_id": attempt_id, "claimed_at": now_s, "instance_id": instance_id,
                 "expires_at": (now + timedelta(seconds=LEASE_SECONDS)).isoformat(), "renew_count": 0}
        prev = await db.rfid_print_jobs.find_one_and_update(
            {"warehouse_id": device.get("warehouse_id"), "status": {"$in": list(rps.OPEN_PRINT_PHASE)},
             "kind": {"$in": kinds}, "id": {"$nin": seen}, "items.status": {"$nin": ["started"]},
             "$or": [{"lease": {"$exists": False}}, {"lease.expires_at": {"$lt": now_s}}]},
            {"$set": {"lease": lease}, "$inc": {"print_attempts": 1}},
            sort=[("created_at", 1)], projection={"_id": 0, "id": 1, "lease": 1}, return_document=ReturnDocument.BEFORE)
        if not prev:
            break
        seen.append(prev["id"])
        old = prev.get("lease") or {}
        await db.rfid_print_jobs.update_one({"id": prev["id"], "lease.attempt_id": attempt_id}, {"$push": {"attempts": {
            "$each": [{"attempt_id": attempt_id, "device_id": device["id"], "device_name": lease["device_name"],
                       "instance_id": instance_id, "claimed_at": now_s, "kind": "reclaim" if old else "claim",
                       "previous_attempt_id": old.get("attempt_id"), "previous_device_id": old.get("device_id"),
                       "previous_expired_at": old.get("expires_at")}], "$slice": -30}}})
        job = await db.rfid_print_jobs.find_one({"id": prev["id"]}, {"_id": 0})
        job = await rps.ensure_item_ids(job)
        job = await _render_for_claim(job, profile, attempt_id)
        jobs.append(_job_view(job, profile, redelivered=False))
    return {"count": len(jobs), "jobs": jobs, "lease_seconds": LEASE_SECONDS, "server_time": now_s,
            "contract": CONTRACT, "conflicts": conflicts}


async def _load_for_device(device: Dict[str, Any], job_id: str, *, zpl: bool = False) -> Dict[str, Any]:
    _assert_printer(device)
    job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0} if zpl else {"_id": 0, "items.zpl": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Print job tidak ditemukan")
    if job.get("warehouse_id") != device.get("warehouse_id"):
        raise HTTPException(status_code=403, detail="Job bukan milik gudang device ini")
    return job


def _assert_lease(job: Dict[str, Any], device: Dict[str, Any], attempt_id: str, instance_id: Optional[str],
                  *, allow_expired: bool = False) -> Dict[str, Any]:
    lease = job.get("lease") or {}
    if lease.get("device_id") != device["id"] or lease.get("attempt_id") != attempt_id:
        raise _err(409, "LEASE_CONFLICT", "Lease job bukan milik printer/attempt ini — tanyakan status attempt.")
    if (lease.get("instance_id") or None) != ((instance_id or "").strip()[:80] or None):
        raise _err(409, "LEASE_CONFLICT", "Lease milik connector lain (instance berbeda) dengan key printer yang sama.")
    if not allow_expired and (lease.get("expires_at") or "") < now_iso():
        raise _err(409, "LEASE_EXPIRED", "Lease job kedaluwarsa — perpanjang (renew) dulu.", retryable=True)
    return lease


async def renew_lease(device: Dict[str, Any], job_id: str, attempt_id: str,
                      instance_id: Optional[str] = None) -> Dict[str, Any]:
    """Perpanjang lease attempt yang SAMA. Lease habis yang belum diklaim ulang printer lain masih bisa dipulihkan."""
    job = await _load_for_device(device, job_id)
    _assert_lease(job, device, attempt_id, instance_id, allow_expired=True)
    if job.get("status") not in rps.OPEN_PRINT_PHASE:
        raise _err(409, "JOB_CLOSED", f"Job sudah berstatus {job.get('status')} — tidak perlu lease.")
    exp = (_now() + timedelta(seconds=LEASE_SECONDS)).isoformat()
    won = await db.rfid_print_jobs.find_one_and_update(
        {"id": job_id, "lease.attempt_id": attempt_id, "lease.device_id": device["id"]},
        {"$set": {"lease.expires_at": exp, "lease.renewed_at": now_iso()}, "$inc": {"lease.renew_count": 1}},
        projection={"_id": 0, "lease": 1}, return_document=ReturnDocument.AFTER)
    if not won:
        raise _err(409, "LEASE_CONFLICT", "Lease berubah bersamaan (diklaim ulang) — tanyakan status attempt.")
    return {"ok": True, "lease": won["lease"], "server_time": now_iso()}


async def start_items(device: Dict[str, Any], job_id: str, attempt_id: str, item_ids: List[str],
                      job_revision: Optional[int] = None, instance_id: Optional[str] = None) -> Dict[str, Any]:
    """Start barrier: niat cetak per item tersimpan durable SEBELUM printer menerima payload. Idempoten."""
    job = await _load_for_device(device, job_id)
    _assert_lease(job, device, attempt_id, instance_id)
    if job.get("status") not in rps.OPEN_PRINT_PHASE:
        raise _err(409, "JOB_CLOSED", f"Job sudah berstatus {job.get('status')}.")
    if job_revision is not None and int(job_revision) != int(job.get("revision") or 1):
        raise _err(409, "VERSION_CONFLICT", "Revisi job berubah sejak diklaim — tarik ulang job.")
    if not item_ids:
        raise _err(400, "SCHEMA_INVALID", "item_ids wajib")
    by_id = {i.get("item_id"): i for i in job.get("items") or []}
    accepted, rejected = [], []
    for iid in list(dict.fromkeys(item_ids))[:200]:
        it = by_id.get(iid)
        if not it:
            rejected.append({"item_id": iid, "code": "NOT_FOUND"})
            continue
        if it.get("status") == "started" and it.get("attempt_id") == attempt_id:
            accepted.append({"item_id": iid, "replay": True, "payload_sha256": it.get("payload_sha256")})
            continue
        if it.get("status") != "pending":
            rejected.append({"item_id": iid, "code": "ITEM_NOT_PENDING", "status": it.get("status")})
            continue
        res = await db.rfid_print_jobs.update_one(
            {"id": job_id, "lease.attempt_id": attempt_id},
            {"$set": {"items.$[it].status": "started", "items.$[it].attempt_id": attempt_id,
                      "items.$[it].started_at": now_iso(), "items.$[it].start_device_id": device["id"],
                      "status": "printing", "updated_at": now_iso()}},
            array_filters=[{"it.item_id": iid, "it.status": "pending"}])
        if res.modified_count == 1:
            accepted.append({"item_id": iid, "replay": False, "payload_sha256": it.get("payload_sha256")})
        else:
            rejected.append({"item_id": iid, "code": "ITEM_NOT_PENDING", "status": "changed"})
    if accepted:
        await rps.refresh_job(job_id)
    return {"accepted": accepted, "rejected": rejected, "server_time": now_iso()}


def _outcome(print_status: str, encode_status: str, rfid: bool) -> str:
    if print_status == "failed" or encode_status == "failed":
        return "failed"
    if print_status == "confirmed" and (encode_status == "confirmed" or (not rfid and encode_status == "not_applicable")):
        return "confirmed"
    return "unknown"


async def report_results(device: Dict[str, Any], job_id: str, attempt_id: str,
                         results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Hasil PER LABEL. Diterima dari attempt yang memulai item walau lease sudah habis (bukti tidak boleh hilang).
    Duplikat `result_event_id` = idempoten; isi berbeda dengan id sama = IDEMPOTENCY_CONFLICT."""
    job = await _load_for_device(device, job_id)
    rfid = job.get("kind") in rps.RFID_WRITE_KINDS
    if not results:
        raise _err(400, "SCHEMA_INVALID", "results wajib")
    acks: List[Dict[str, Any]] = []
    confirmed_now: List[str] = []
    for r in results[:200]:
        rid = str(r.get("result_event_id") or "").strip()[:100]
        iid = r.get("item_id")
        ps, es = r.get("print_status"), r.get("encode_status")
        ack: Dict[str, Any] = {"result_event_id": rid, "item_id": iid}
        if not rid or ps not in rps.PRINT_STATUSES or es not in rps.ENCODE_STATUSES or (rfid and es == "not_applicable"):
            acks.append({**ack, "status": "rejected", "error": {"code": "SCHEMA_INVALID", "message": (
                "result_event_id/print_status/encode_status tidak valid" + (
                    " (label RFID wajib status encode)" if rfid and es == "not_applicable" else ""))}})
            continue
        for _ in range(4):  # CAS per item (status sekarang) — balapan dengan keputusan operator diulang
            cur = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})
            it = next((i for i in (cur or {}).get("items") or [] if i.get("item_id") == iid), None)
            if not it:
                ack.update(status="rejected", error={"code": "NOT_FOUND", "message": "Item tidak ditemukan"})
                break
            prev = next((x for x in it.get("results") or [] if x.get("result_event_id") == rid), None)
            if prev:
                same = (prev.get("print_status"), prev.get("encode_status"), prev.get("payload_sha256")) == (
                    ps, es, r.get("payload_sha256") or prev.get("payload_sha256"))
                if same:
                    ack.update(status="duplicate", item_status=it.get("status"))
                    if it.get("status") == "confirmed" and it.get("effects") != "done":
                        confirmed_now.append(iid)   # ulangan hasil = jalur pemulihan efek (tanpa cetak ulang)
                else:
                    ack.update(status="rejected", error={"code": "IDEMPOTENCY_CONFLICT",
                                                         "message": "result_event_id sama dengan isi berbeda"})
                break
            if it.get("attempt_id") != attempt_id or it.get("status") == "pending":
                ack.update(status="rejected", error={"code": "ATTEMPT_MISMATCH" if it.get("status") != "pending"
                                                     else "NOT_STARTED",
                                                     "message": "Item tidak dimulai oleh attempt ini (start dulu)."})
                break
            if r.get("payload_sha256") and it.get("payload_sha256") and r["payload_sha256"] != it["payload_sha256"]:
                ack.update(status="rejected", error={"code": "PAYLOAD_MISMATCH",
                                                     "message": "Digest payload berbeda dari item ERP."})
                break
            outcome = _outcome(ps, es, rfid)
            current = it.get("status")
            evidence = {"source": str((r.get("evidence") or {}).get("source") or "connector")[:40],
                        "detail": str((r.get("evidence") or {}).get("detail") or "")[:300],
                        "error_code": (r.get("evidence") or {}).get("error_code"),
                        "readback_epc": (r.get("evidence") or {}).get("readback_epc"),
                        "printer_state": (r.get("evidence") or {}).get("printer_state")}
            if rfid and evidence.get("readback_epc") and ps == "confirmed" and es == "confirmed" \
                    and str(evidence["readback_epc"]).upper() != (it.get("epc") or "").upper():
                outcome, es = "failed", "failed"   # chip berisi EPC lain → label tidak sah
                evidence["detail"] = (evidence["detail"] + " | EPC baca balik berbeda dari ERP").strip(" |")
            entry = {"result_event_id": rid, "attempt_id": attempt_id, "print_status": ps, "encode_status": es,
                     "payload_sha256": r.get("payload_sha256") or it.get("payload_sha256"), "evidence": evidence,
                     "at": now_iso(), "outcome": outcome, "device_id": device["id"]}
            st: Dict[str, Any] = {"updated_at": now_iso()}
            if it.get("resolution"):
                entry["late_after_resolution"] = True
                if outcome != current:
                    st["items.$[it].conflict"] = True
            elif current in ("started", "unknown") and (current == "started" or outcome != "unknown"):
                st.update({"items.$[it].status": outcome, "items.$[it].print_status": ps,
                           "items.$[it].encode_status": es, "items.$[it].result_at": now_iso(),
                           "items.$[it].evidence": evidence})
                if outcome == "confirmed":
                    st["items.$[it].effects"] = "pending"
            elif current in ("confirmed", "failed") and outcome != current:
                st["items.$[it].conflict"] = True        # confirmed tidak dimundurkan otomatis oleh hasil lain
            res = await db.rfid_print_jobs.update_one(
                {"id": job_id}, {"$set": st, "$push": {"items.$[it].results": {"$each": [entry],
                                                                               "$slice": -MAX_RESULTS_PER_ITEM}}},
                array_filters=[{"it.item_id": iid, "it.status": current,
                                "it.results.result_event_id": {"$ne": rid}}])
            if res.modified_count == 1:
                new_status = st.get("items.$[it].status", current)
                ack.update(status="accepted", item_status=new_status, conflict=bool(st.get("items.$[it].conflict")))
                if new_status == "confirmed":
                    confirmed_now.append(iid)
                break
        else:
            ack.update(status="rejected", error={"code": "RETRY", "message": "Item berubah bersamaan — kirim ulang"},
                       retryable=True)
        acks.append(ack)
    effects_pending = False
    if confirmed_now:
        try:
            await rps.apply_item_effects(job_id, list(dict.fromkeys(confirmed_now)))
        except Exception:  # noqa: BLE001 — hasil sudah durable; sapuan/ulangan hasil melengkapi efek
            effects_pending = True
    job = await rps.refresh_job(job_id)
    return {"acks": acks, "job_status": job.get("status"), "counts": job.get("counts"),
            "effects_pending": effects_pending or bool(job.get("effects_pending")), "server_time": now_iso()}


async def attempt_state(device: Dict[str, Any], job_id: str, attempt_id: str) -> Dict[str, Any]:
    """Status attempt untuk pemulihan connector (crash / ACK hilang): item, hasil tercatat, lease, efek."""
    job = await _load_for_device(device, job_id)
    lease = job.get("lease") or {}
    mine = lease.get("attempt_id") == attempt_id and lease.get("device_id") == device["id"]
    items = []
    for it in job.get("items") or []:
        items.append({"item_id": it.get("item_id"), "status": it.get("status"), "attempt_id": it.get("attempt_id"),
                      "started_by_this_attempt": it.get("attempt_id") == attempt_id,
                      "payload_sha256": it.get("payload_sha256"), "print_status": it.get("print_status"),
                      "encode_status": it.get("encode_status"), "conflict": bool(it.get("conflict")),
                      "resolution": (it.get("resolution") or {}).get("action"),
                      "result_event_ids": [x.get("result_event_id") for x in it.get("results") or []],
                      "effects": it.get("effects")})
    return {"job_id": job_id, "attempt_id": attempt_id, "job_status": job.get("status"),
            "revision": job.get("revision") or 1, "lease_owned": mine,
            "lease_live": mine and (lease.get("expires_at") or "") >= now_iso(), "lease": lease if mine else None,
            "items": items, "effects_pending": bool(job.get("effects_pending")), "server_time": now_iso()}


async def legacy_ack(device: Dict[str, Any], job_id: str, attempt_id: Optional[str]) -> Dict[str, Any]:
    """RF-15 — ACK tingkat job (kontrak lama). Status + item `confirmed` + efek tertunda disimpan ATOMIK, lalu efek
    diterapkan; gagal efek → dipulihkan oleh ulangan ACK yang sama / sapuan (tanpa cetak ulang)."""
    _assert_printer(device)
    job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Print job tidak ditemukan")
    if job.get("warehouse_id") != device.get("warehouse_id"):
        raise HTTPException(status_code=403, detail="Job bukan milik gudang device ini")
    if not attempt_id:
        raise HTTPException(status_code=400, detail="attempt_id wajib (dari pull antrean)")
    if job.get("status") != "queued":
        if job.get("printed_attempt_id") == attempt_id:
            recovered = 0
            try:
                recovered = (await rps.apply_item_effects(job_id))["applied"]
            except Exception:  # noqa: BLE001
                return {"ok": True, "status": job["status"], "replay": True, "effects_pending": True}
            return {"ok": True, "status": job["status"], "replay": True, "effects_recovered": recovered}
        if job.get("status") == "printing":
            raise HTTPException(status_code=409, detail=(
                "Job sedang dicetak per label (start/results) — laporkan hasil per label, bukan ACK job."))
        raise HTTPException(status_code=409, detail=f"Job sudah berstatus {job['status']}")
    lease = job.get("lease") or {}
    if lease.get("device_id") != device["id"] or lease.get("attempt_id") != attempt_id:
        raise HTTPException(status_code=409, detail="Lease job bukan milik printer/attempt ini")
    now = now_iso()
    if (lease.get("expires_at") or "") < now:
        raise HTTPException(status_code=409, detail="Lease job kedaluwarsa — tarik ulang antrean")
    job = await rps.ensure_item_ids(job)
    st = rps._confirm_all_update("legacy_job_ack", {
        "status": "printed", "printed_at": now, "printed_by_device": device["id"], "printed_attempt_id": attempt_id,
        "printed_via": "device", "effects_pending": True, "updated_at": now})
    if job.get("kind") not in rps.RFID_WRITE_KINDS:
        st["items.$[p].encode_status"] = "not_applicable"
    won = await db.rfid_print_jobs.find_one_and_update(
        {"id": job_id, "status": "queued", "lease.attempt_id": attempt_id, "lease.device_id": device["id"]},
        {"$set": st, "$unset": {"lease": ""}}, array_filters=[{"p.status": {"$in": ["pending", None]}}],
        projection={"_id": 0, "items.zpl": 0})
    if not won:
        raise HTTPException(status_code=409, detail="Job berubah bersamaan — tarik ulang antrean")
    try:
        await rps.apply_item_effects(job_id)
    except Exception:  # noqa: BLE001 — status durable; efek dipulihkan (ulangan ACK / sapuan)
        await rps.refresh_job(job_id)
        return {"ok": True, "status": "printed", "effects_pending": True}
    await rps.refresh_job(job_id)
    return {"ok": True, "status": "printed"}


async def agent_config(device: Dict[str, Any]) -> Dict[str, Any]:
    _assert_printer(device, pull=True)
    profile = device_profile(device)
    return {"contract": CONTRACT, "device_id": device["id"], "device_code": device.get("code"),
            "device_name": device.get("name"), "warehouse_id": device.get("warehouse_id"),
            "enabled": device.get("enabled") is not False, "capabilities": _caps(device),
            "printer_profile": profile, "profile_key": tpl.profile_key(profile),
            "expected_responses": tpl.expected_responses(profile, True), "policies": POLICIES,
            "server_time": now_iso()}


async def telemetry(device: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    """Heartbeat connector + kesehatan printer (dua hal berbeda). Instance lain dengan key sama → ditandai konflik."""
    _assert_printer(device, pull=True)
    now = now_iso()
    conn = body.get("connector") or {}
    prn = body.get("printer") or {}
    inst = str(body.get("instance_id") or conn.get("instance_id") or "")[:80] or None
    state = prn.get("state") if prn.get("state") in PRINTER_STATES else "unknown"
    upd: Dict[str, Any] = {
        "status": "online", "last_heartbeat": now,
        "connector_health": {"at": now, "instance_id": inst, "version": str(conn.get("version") or "")[:40],
                             "host": str(conn.get("host") or "")[:80], "uptime_s": conn.get("uptime_s"),
                             "erp_reachable": True, "ledger": conn.get("ledger") or {},
                             "last_error": str(conn.get("last_error") or "")[:300] or None},
        "printer_health": {"at": now, "checked_at": prn.get("checked_at") or now, "state": state,
                           "reachable": bool(prn.get("reachable")), "flags": prn.get("flags") or {},
                           "detail": str(prn.get("detail") or "")[:300], "model": str(prn.get("model") or "")[:80],
                           "last_confirmed_output_at": prn.get("last_confirmed_output_at")}}
    prev = await db.rfid_devices.find_one({"id": device["id"]}, {"_id": 0, "connector_health": 1})
    pinst = ((prev or {}).get("connector_health") or {}).get("instance_id")
    pat = ((prev or {}).get("connector_health") or {}).get("at") or ""
    if pinst and inst and pinst != inst and pat >= (_now() - timedelta(seconds=120)).isoformat():
        upd["connector_conflict"] = {"at": now, "instances": [pinst, inst],
                                     "message": "Dua connector memakai key printer yang sama"}
    await db.rfid_devices.update_one({"id": device["id"], "enabled": {"$ne": False}}, {"$set": upd})
    return {"ok": True, "server_time": now, "device_id": device["id"],
            "conflict": bool(upd.get("connector_conflict"))}
