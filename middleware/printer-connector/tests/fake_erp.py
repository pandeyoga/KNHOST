"""ERP tiruan (dalam proses) yang meniru semantik kontrak `kn-printer-1` sisi server — untuk uji connector tanpa
backend. Uji ujung-ke-ujung dengan ERP sungguhan ada di `backend/tests/test_prep_f_connector_e2e.py`."""
from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from kn_printer_connector.erp import ErpError, ErpUnavailable

EXPECTED = {"readback": True, "readback_header": "EPC[", "readback_term": "]", "encode_result": False,
            "confirm_without_readback": False}


def zpl_for(epc: str, n: int) -> str:
    return (f"^XA^CI28^PW560^LL176^RS8,,,1,N^RFW,H^FD{epc}^FS^RFR,H^FN9^FS^FH_^HV9,24,EPC[,]_0D_0A,L^FS"
            f"^FO10,10^A0N,26,22^FH_^FDRoll R{n:04d}^FS^PQ1^XZ")


def make_job(n_items: int, kind: str = "rfid_tag", job_id: Optional[str] = None) -> Dict[str, Any]:
    jid = job_id or f"rpj_{uuid.uuid4().hex[:8]}"
    items = []
    for i in range(n_items):
        epc = ("E2" + uuid.uuid4().hex[:22]).upper()
        z = zpl_for(epc, i + 1) if kind == "rfid_tag" else z_text(i + 1)
        items.append({"item_id": f"rpi_{jid[-6:]}_{i}", "roll_no": f"R{i + 1:04d}", "epc": epc if kind == "rfid_tag" else None,
                      "zpl": z, "payload_sha256": hashlib.sha256(z.encode()).hexdigest(), "status": "pending",
                      "attempt_id": None, "results": [], "resolution": None})
    return {"id": jid, "job_number": f"PJ-{jid[-4:]}", "kind": kind, "revision": 1, "status": "queued",
            "items": items, "lease": None, "attempts": 0}


def z_text(n: int) -> str:
    return f"^XA^CI28^PW560^LL176^FO10,10^A0N,26,22^FH_^FDRoll R{n:04d}^FS^PQ1^XZ"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeErp:
    def __init__(self, jobs: List[Dict[str, Any]], device_id: str = "rdev_A", lease_seconds: int = 300,
                 policies: Optional[Dict[str, Any]] = None):
        self.jobs = {j["id"]: j for j in jobs}
        self.device_id = device_id
        self.lease_seconds = lease_seconds
        self.offline = False
        self.drop_results_response = 0       # >0: proses hasil lalu "hilangkan" respons (ACK hilang) sebanyak n kali
        self.calls: List[str] = []
        self.telemetry_log: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.policies = {"poll_interval_s": 0.05, "telemetry_interval_s": 0.3, "renew_before_s": 5,
                         "outcome_timeout_s": 2.5, "pause_wait_s": 8, "status_probe_timeout_s": 0.6,
                         "lease_seconds": lease_seconds, **(policies or {})}

    def _gate(self, name: str) -> None:
        self.calls.append(name)
        if self.offline:
            raise ErpUnavailable("simulasi offline")

    def config(self) -> Dict[str, Any]:
        self._gate("config")
        return {"device_id": self.device_id, "policies": self.policies, "printer_profile": {"dpi": 203}}

    def telemetry(self, body: Dict[str, Any]) -> Dict[str, Any]:
        self._gate("telemetry")
        self.telemetry_log.append(body)
        return {"ok": True}

    def _view(self, j: Dict[str, Any], redelivered: bool) -> Dict[str, Any]:
        return {"id": j["id"], "job_number": j["job_number"], "kind": j["kind"], "revision": j["revision"],
                "lease": dict(j["lease"]), "redelivered": redelivered, "expected_responses":
                    EXPECTED if j["kind"] == "rfid_tag" else {"readback": False, "encode_result": False},
                "items": [{**{k: it[k] for k in ("item_id", "roll_no", "epc", "zpl", "payload_sha256", "status",
                                                  "attempt_id")}, "printable": it["status"] == "pending"}
                          for it in j["items"]]}

    def claim(self, limit: int = 1) -> Dict[str, Any]:
        self._gate("claim")
        with self.lock:
            now = _now()
            out = []
            for j in self.jobs.values():
                lease = j.get("lease")
                if lease and lease["device_id"] == self.device_id and lease["expires"] > now and \
                        j["status"] in ("queued", "printing"):
                    out.append(self._view(j, True))
            for j in self.jobs.values():
                if len(out) >= limit:
                    break
                lease = j.get("lease")
                if j["status"] not in ("queued", "printing") or any(i["status"] == "started" for i in j["items"]):
                    continue
                if lease and lease["expires"] > now:
                    continue
                if not any(i["status"] == "pending" for i in j["items"]):
                    continue
                exp = now + timedelta(seconds=self.lease_seconds)
                j["lease"] = {"device_id": self.device_id, "attempt_id": f"patt_{uuid.uuid4().hex[:10]}",
                              "expires_at": exp.isoformat(), "expires": exp}
                j["attempts"] += 1
                out.append(self._view(j, False))
            return {"jobs": [{**v, "lease": {k: x for k, x in v["lease"].items() if k != "expires"}} for v in out],
                    "server_time": now.isoformat(), "conflicts": []}

    def _job(self, job_id: str, attempt_id: str, lease: bool = True) -> Dict[str, Any]:
        j = self.jobs.get(job_id)
        if not j:
            raise ErpError(404, "NOT_FOUND", "job")
        if lease:
            ls = j.get("lease") or {}
            if ls.get("attempt_id") != attempt_id:
                raise ErpError(409, "LEASE_CONFLICT", "lease")
            if ls["expires"] < _now():
                raise ErpError(409, "LEASE_EXPIRED", "expired")
        return j

    def renew(self, job_id: str, attempt_id: str) -> Dict[str, Any]:
        self._gate("renew")
        with self.lock:
            j = self.jobs.get(job_id)
            if not j or (j.get("lease") or {}).get("attempt_id") != attempt_id:
                raise ErpError(409, "LEASE_CONFLICT", "lease")
            exp = _now() + timedelta(seconds=self.lease_seconds)
            j["lease"].update(expires=exp, expires_at=exp.isoformat())
            return {"ok": True, "lease": {"attempt_id": attempt_id, "expires_at": exp.isoformat()}}

    def attempt(self, job_id: str, attempt_id: str) -> Dict[str, Any]:
        self._gate("attempt")
        j = self.jobs[job_id]
        return {"items": [{"item_id": i["item_id"], "status": i["status"], "attempt_id": i["attempt_id"],
                           "resolution": i.get("resolution")} for i in j["items"]]}

    def start(self, job_id: str, attempt_id: str, item_ids: List[str], revision: Optional[int]) -> Dict[str, Any]:
        self._gate("start")
        with self.lock:
            j = self._job(job_id, attempt_id)
            acc, rej = [], []
            for iid in item_ids:
                it = next(i for i in j["items"] if i["item_id"] == iid)
                if it["status"] == "started" and it["attempt_id"] == attempt_id:
                    acc.append({"item_id": iid, "replay": True})
                elif it["status"] == "pending":
                    it.update(status="started", attempt_id=attempt_id)
                    j["status"] = "printing"
                    acc.append({"item_id": iid, "replay": False})
                else:
                    rej.append({"item_id": iid, "code": "ITEM_NOT_PENDING"})
            return {"accepted": acc, "rejected": rej}

    def results(self, job_id: str, attempt_id: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        self._gate("results")
        with self.lock:
            j = self.jobs[job_id]
            acks = []
            for r in results:
                it = next(i for i in j["items"] if i["item_id"] == r["item_id"])
                prev = next((x for x in it["results"] if x["result_event_id"] == r["result_event_id"]), None)
                if prev:
                    acks.append({"item_id": it["item_id"], "result_event_id": r["result_event_id"], "status": "duplicate"})
                    continue
                if it["attempt_id"] != attempt_id:
                    acks.append({"item_id": it["item_id"], "status": "rejected", "error": {"code": "ATTEMPT_MISMATCH"}})
                    continue
                ps, es = r["print_status"], r["encode_status"]
                outcome = "failed" if "failed" in (ps, es) else "confirmed" if ps == "confirmed" and es in (
                    "confirmed", "not_applicable") else "unknown"
                it["results"].append(r)
                if it["status"] in ("started", "unknown") and (it["status"] == "started" or outcome != "unknown"):
                    it["status"] = outcome
                acks.append({"item_id": it["item_id"], "result_event_id": r["result_event_id"], "status": "accepted",
                             "item_status": it["status"]})
            if all(i["status"] not in ("pending", "started") for i in j["items"]):
                j["status"] = "done"
                j["lease"] = None
            if self.drop_results_response > 0:
                self.drop_results_response -= 1
                raise ErpUnavailable("respons hasil hilang (simulasi ACK hilang)")
            return {"acks": acks}

    # bantuan uji
    def statuses(self, job_id: str) -> List[str]:
        return [i["status"] for i in self.jobs[job_id]["items"]]
