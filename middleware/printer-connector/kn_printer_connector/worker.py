"""Worker per printer — satu identitas (device key), satu ledger, satu printer fisik. Berjalan sekuensial:
lapor hasil tertunda → lanjutkan job aktif → klaim job baru. Tidak ada cetak ulang otomatis.

Urutan per label (ledger): INTENT → start diterima ERP (STARTED) → SENDING (durable) → kirim → SENT →
hasil (OUTCOME) → dilaporkan (REPORTED). ERP tidak terjangkau → tidak ada label baru dimulai (start barrier),
hasil tersimpan lokal dan dikirim saat tersambung.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import VERSION
from . import ledger as L
from .config import ConnectorConfig, PrinterConfig
from .erp import ErpClient, ErpError, ErpUnavailable
from .printer import PrinterStatus, PrinterUnavailable, ZplTcpPrinter

DEFAULT_POLICIES = {"lease_seconds": 300, "renew_before_s": 90, "poll_interval_s": 5, "telemetry_interval_s": 30,
                    "status_probe_timeout_s": 3, "outcome_timeout_s": 45, "pause_wait_s": 600}
LEASE_LOST = ("LEASE_CONFLICT", "JOB_CLOSED", "VERSION_CONFLICT")


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _utc() -> datetime:
    return datetime.now(timezone.utc)


class SingleInstanceLock:
    """Kunci berkas eksklusif per printer — dua connector tidak boleh memakai ledger/printer yang sama."""

    def __init__(self, path: str):
        self.path = path
        self.fh = None

    def acquire(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.fh = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
            raise RuntimeError(f"Connector lain sedang memakai {os.path.dirname(self.path)} — hentikan dulu.")

    def release(self) -> None:
        if self.fh:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            self.fh.close()
            self.fh = None


class PrinterWorker(threading.Thread):
    def __init__(self, pcfg: PrinterConfig, ccfg: ConnectorConfig, *, erp: Any = None, printer: Any = None,
                 ledger: Optional[L.Ledger] = None, hooks: Optional[Dict[str, Callable[..., Any]]] = None,
                 lock: bool = True):
        super().__init__(name=f"printer-{pcfg.name}", daemon=True)
        self.pcfg, self.ccfg = pcfg, ccfg
        base = os.path.join(ccfg.data_dir, pcfg.name)
        self.lock = SingleInstanceLock(os.path.join(base, "connector.lock")) if lock else None
        if self.lock:
            self.lock.acquire()
        self.ledger = ledger or L.Ledger(os.path.join(base, "ledger.sqlite3"))
        self.instance_id = self.ledger.instance_id()
        self.erp = erp or ErpClient(ccfg.erp_url, pcfg.device_key, self.instance_id, verify_tls=ccfg.verify_tls,
                                    timeout_s=ccfg.http_timeout_s)
        self.printer = printer or ZplTcpPrinter(pcfg.host, pcfg.port, pcfg.connect_timeout_s, pcfg.io_timeout_s)
        self.log = logging.getLogger(f"kn.printer.{pcfg.name}")
        self.hooks = hooks or {}
        self.stop_event = threading.Event()
        self.policies = dict(DEFAULT_POLICIES)
        if ccfg.poll_interval_s:
            self.policies["poll_interval_s"] = float(ccfg.poll_interval_s)
        if ccfg.telemetry_interval_s:
            self.policies["telemetry_interval_s"] = float(ccfg.telemetry_interval_s)
        self.config_loaded_at = 0.0
        self.last_telemetry = 0.0
        self.last_probe = 0.0
        self.last_status: Optional[PrinterStatus] = None
        self.last_confirmed_output_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self.erp_reachable = False
        self.model: Optional[str] = None
        self.started = time.monotonic()
        self.backoff = 1.0

    # ── siklus hidup ──
    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            self.run_forever()
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.ledger.close()
        except Exception:  # noqa: BLE001
            pass
        if self.lock:
            self.lock.release()

    def run_forever(self) -> None:
        rec = self.ledger.recover_after_crash()
        if rec:
            self.log.warning("Pulih dari crash: %d label terkirim tanpa hasil → dilaporkan TIDAK PASTI, tidak dicetak "
                             "ulang", len(rec))
        while not self.stop_event.is_set():
            try:
                did = self.step()
                self.backoff = 1.0
                if did in ("idle", "printer_not_ready", "lease_wait"):
                    self.stop_event.wait(float(self.policies["poll_interval_s"]))
            except ErpUnavailable as e:
                self.erp_reachable = False
                self.last_error = f"ERP tidak terjangkau: {e}"
                self.log.warning("%s — coba lagi %.0f s (antrean tertahan, hasil disimpan lokal)", self.last_error,
                                 self.backoff)
                self.stop_event.wait(self.backoff)
                self.backoff = min(self.backoff * 2, 60.0)
            except ErpError as e:
                self.last_error = str(e)
                self.log.error("ERP menolak: %s", e)
                self.stop_event.wait(min(30.0, float(self.policies["poll_interval_s"]) * 3))
            except Exception as e:  # noqa: BLE001
                self.last_error = f"galat tak terduga: {e}"
                self.log.exception("galat tak terduga")
                self.stop_event.wait(5.0)

    # ── satu langkah (dipakai juga oleh uji) ──
    def step(self) -> str:
        if not self.config_loaded_at:
            self._load_config()                    # tanpa config pertama: tunggu ERP (backoff)
        elif time.monotonic() - self.config_loaded_at > 600:
            try:
                self._load_config()
            except ErpUnavailable:
                self.erp_reachable = False
        try:
            self._maybe_telemetry()
        except ErpUnavailable:
            self.erp_reachable = False
        try:
            self.report_pending()
        except ErpUnavailable:
            self.erp_reachable = False         # hasil tetap di ledger; label yang sudah "started" boleh lanjut
        job = self.ledger.active_job()
        if job:
            return self._process(job)
        return self._claim()

    def _load_config(self) -> None:
        cfg = self.erp.config()
        self.erp_reachable = True
        for k, v in (cfg.get("policies") or {}).items():
            if k in self.policies and not (k == "poll_interval_s" and self.ccfg.poll_interval_s) and \
                    not (k == "telemetry_interval_s" and self.ccfg.telemetry_interval_s):
                self.policies[k] = v
        self.config_loaded_at = time.monotonic()
        if self.model is None:
            self.model = self.printer.identify() if hasattr(self.printer, "identify") else None

    def _probe(self) -> PrinterStatus:
        st = self.printer.status(float(self.policies["status_probe_timeout_s"]))
        self.last_probe = time.monotonic()
        changed = not self.last_status or self.last_status.state != st.state
        self.last_status = st
        if changed:
            self.log.info("status printer: %s %s", st.state, st.detail)
            self.last_telemetry = 0.0   # kirim segera bila berubah
        return st

    def _maybe_telemetry(self, force: bool = False, probe: bool = True) -> None:
        """Heartbeat connector + status printer. `probe=False` saat label sedang dicetak (satu koneksi printer)."""
        interval = float(self.policies["telemetry_interval_s"])
        if not force and time.monotonic() - self.last_telemetry < interval:
            return
        st = self.last_status
        if probe and (st is None or time.monotonic() - self.last_probe >= interval):
            st = self._probe()
        if st is None:
            st = PrinterStatus(reachable=False, state="unknown", detail="belum dicek")
        body = {"connector": {"version": VERSION, "host": socket.gethostname(), "instance_id": self.instance_id,
                              "uptime_s": int(time.monotonic() - self.started), "ledger": self.ledger.counts(),
                              "last_error": self.last_error},
                "printer": {**st.as_telemetry(), "model": self.model,
                            "last_confirmed_output_at": self.last_confirmed_output_at}}
        self.erp.telemetry(body)
        self.erp_reachable = True
        self.last_telemetry = time.monotonic()

    # ── hasil ──
    def report_pending(self) -> int:
        rows = self.ledger.pending_results()
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault((r["job_id"], r["attempt_id"]), []).append(r)
        sent = 0
        for (job_id, attempt_id), items in groups.items():
            body = [{"result_event_id": r["result_event_id"], "item_id": r["item_id"],
                     "print_status": r["print_status"], "encode_status": r["encode_status"],
                     "payload_sha256": r["payload_sha256"], "evidence": json.loads(r["evidence_json"] or "{}")}
                    for r in items]
            try:
                res = self.erp.results(job_id, attempt_id, body)
            except ErpError as e:
                if e.status in (403, 404):  # job hilang/di luar gudang: bukti tetap di ledger, berhenti mengulang
                    for r in items:
                        self.ledger.transition(job_id, r["item_id"], attempt_id, L.REPORTED,
                                               last_error=f"ditolak ERP {e.status}: {e.message}"[:300])
                    self.ledger.log("ERROR", f"hasil ditolak ERP: {e}", job_id)
                    continue
                raise
            if self.hooks.get("after_results_sent"):
                self.hooks["after_results_sent"](job_id, attempt_id, res)
            for ack in res.get("acks") or []:
                st = ack.get("status")
                if st in ("accepted", "duplicate") or (st == "rejected" and not ack.get("retryable")):
                    err = None if st != "rejected" else json.dumps(ack.get("error"))[:300]
                    self.ledger.transition(job_id, ack["item_id"], attempt_id, L.REPORTED,
                                           from_states=[L.OUTCOME], last_error=err)
                    sent += 1
                    if st == "rejected":
                        self.log.warning("hasil item %s ditolak: %s", ack["item_id"], ack.get("error"))
        return sent

    # ── klaim ──
    def _claim(self) -> str:
        res = self.erp.claim(1)
        self.erp_reachable = True
        st = _parse(res.get("server_time"))
        offset = (st - _utc()).total_seconds() if st else 0.0
        for c in res.get("conflicts") or []:
            self.log.error("KONFLIK: %s (job %s)", c.get("message"), c.get("job_id"))
        jobs = res.get("jobs") or []
        if not jobs:
            return "idle"
        for job in jobs:
            att = (job.get("lease") or {}).get("attempt_id")
            if self.ledger.has_attempt(job["id"], att):
                self.ledger.set_lease(job["id"], att, (job.get("lease") or {}).get("expires_at"))
                continue
            self.ledger.upsert_job(job, offset)
            if job.get("redelivered"):
                # ERP mengenal attempt ini tetapi ledger lokal TIDAK (ledger hilang) → item started = tidak pasti
                for it in job.get("items") or []:
                    if it.get("status") == "started" and it.get("attempt_id") == att:
                        self.ledger.ensure_item(job["id"], att, it, L.SKIPPED)
                        self.ledger.record_outcome(job["id"], it["item_id"], att, "unknown",
                                                   "unknown" if job.get("kind") == "rfid_tag" else "not_applicable",
                                                   {"source": "connector_recovery",
                                                    "detail": "Ledger lokal tidak punya catatan attempt ini — hasil "
                                                              "fisik tidak diketahui, TIDAK dicetak ulang."})
            self.ledger.log("INFO", f"klaim job {job.get('job_number')} attempt {att} "
                                    f"({'ulang' if job.get('redelivered') else 'baru'})", job["id"])
            self.log.info("klaim job %s (%d label)", job.get("job_number"), len(job.get("items") or []))
        return "claimed"

    # ── lease ──
    def _lease_remaining(self, job: Dict[str, Any]) -> float:
        exp = _parse(job.get("lease_expires_at"))
        if not exp:
            return 0.0
        return (exp - _utc()).total_seconds() - float(job.get("server_offset_s") or 0.0)

    def _ensure_lease(self, job: Dict[str, Any]) -> str:
        left = self._lease_remaining(job)
        if left > float(self.policies["renew_before_s"]):
            return "ok"
        try:
            r = self.erp.renew(job["job_id"], job["attempt_id"])
        except ErpUnavailable:
            return "ok" if left > 5 else "lease_wait"
        except ErpError as e:
            if e.code in LEASE_LOST or e.status in (403, 404):
                return "lost"
            raise
        self.ledger.set_lease(job["job_id"], job["attempt_id"], (r.get("lease") or {}).get("expires_at"))
        job["lease_expires_at"] = (r.get("lease") or {}).get("expires_at")
        if left <= 0:  # lease sempat habis: pastikan item belum diputuskan operator sebelum mencetak lagi
            state = self.erp.attempt(job["job_id"], job["attempt_id"])
            for it in state.get("items") or []:
                row = self.ledger.item(job["job_id"], it["item_id"], job["attempt_id"])
                if row and row["state"] in L.NOT_SENT and (it.get("resolution") or it.get("status") not in
                                                           ("pending", "started")):
                    self.ledger.transition(job["job_id"], it["item_id"], job["attempt_id"], L.SKIPPED,
                                           last_error=f"ERP: item {it.get('status')} / diputuskan operator")
        return "ok"

    # ── proses job aktif ──
    def _process(self, job: Dict[str, Any]) -> str:
        expected = json.loads(job.get("expected_json") or "{}")
        rfid = job.get("kind") == "rfid_tag"
        did = "progress"
        for it in self.ledger.items(job["job_id"], job["attempt_id"]):
            if self.stop_event.is_set():
                return "stopping"
            if it["state"] in (L.OUTCOME, L.REPORTED, L.SKIPPED):
                continue
            lease = self._ensure_lease(job)
            if lease == "lost":
                self.ledger.finish_job(job["job_id"], job["attempt_id"], "lease_lost",
                                       "lease diambil alih / job ditutup ERP")
                self.log.warning("lease job %s hilang — label yang belum dimulai dilepas ke ERP", job.get("job_number"))
                return "lease_lost"
            if lease == "lease_wait":
                return "lease_wait"
            st = self._probe()
            if not st.ready:
                try:
                    self._maybe_telemetry(force=True, probe=False)
                except ErpUnavailable:
                    self.erp_reachable = False
                return "printer_not_ready"
            iid, att = it["item_id"], job["attempt_id"]
            if it["state"] == L.CLAIMED:
                self.ledger.transition(job["job_id"], iid, att, L.INTENT, from_states=[L.CLAIMED])
            if it["state"] in (L.CLAIMED, L.INTENT):
                try:
                    res = self.erp.start(job["job_id"], att, [iid], job.get("revision"))
                except ErpError as e:
                    if e.code in LEASE_LOST or e.code == "LEASE_EXPIRED" or e.status in (403, 404):
                        if e.code == "LEASE_EXPIRED":
                            job["lease_expires_at"] = None
                            return "lease_wait"
                        self.ledger.finish_job(job["job_id"], att, "aborted", e.code)
                        return "aborted"
                    raise
                if not any(a.get("item_id") == iid for a in res.get("accepted") or []):
                    rej = next((r for r in res.get("rejected") or [] if r.get("item_id") == iid), {})
                    self.ledger.transition(job["job_id"], iid, att, L.SKIPPED, last_error=json.dumps(rej)[:300])
                    continue
                self.ledger.transition(job["job_id"], iid, att, L.STARTED, from_states=[L.CLAIMED, L.INTENT])
            if not it.get("zpl"):
                self.ledger.record_outcome(job["job_id"], iid, att, "unknown", "unknown" if rfid else "not_applicable",
                                           {"source": "connector", "detail": "payload tidak ada di ledger"})
                continue

            def _sending(iid=iid, att=att):
                if not self.ledger.transition(job["job_id"], iid, att, L.SENDING, from_states=[L.STARTED]):
                    raise RuntimeError("status ledger berubah — batal kirim")

            def _sent(iid=iid, att=att):
                self.ledger.transition(job["job_id"], iid, att, L.SENT, from_states=[L.SENDING])
                if self.hooks.get("after_sent"):
                    self.hooks["after_sent"](job, iid)

            try:
                out = self.printer.print_item(
                    it["zpl"], rfid=rfid, epc=it.get("epc"), expected=expected, on_sending=_sending, on_sent=_sent,
                    outcome_timeout_s=float(self.policies["outcome_timeout_s"]),
                    pause_wait_s=float(self.policies["pause_wait_s"]),
                    probe_timeout_s=float(self.policies["status_probe_timeout_s"]), stop=self.stop_event,
                    on_state=self._on_state)
            except PrinterUnavailable as e:
                self.last_error = str(e)
                self.log.warning("label %s belum dikirim: %s", it.get("roll_no"), e)
                return "printer_not_ready"
            self.ledger.record_outcome(job["job_id"], iid, att, out.print_status, out.encode_status, out.evidence)
            self.ledger.log("INFO" if out.result == "confirmed" else "WARN",
                            f"label {it.get('roll_no')}: cetak={out.print_status} encode={out.encode_status}",
                            job["job_id"], iid)
            if out.result == "confirmed":
                self.last_confirmed_output_at = _utc().isoformat()
            try:
                self.report_pending()
            except ErpUnavailable:
                pass  # tersimpan lokal; dikirim saat tersambung
        if all(r["state"] in (L.REPORTED, L.SKIPPED) for r in self.ledger.items(job["job_id"], job["attempt_id"])):
            self.ledger.finish_job(job["job_id"], job["attempt_id"], "done")
            return "job_done"
        return did

    def _on_state(self, st: PrinterStatus) -> None:
        if not self.last_status or self.last_status.state != st.state:
            self.last_status = st
            self.log.info("status printer saat mencetak: %s", st.state)
            try:
                self._maybe_telemetry(force=True, probe=False)
            except ErpUnavailable:
                pass
        self.last_status = st
