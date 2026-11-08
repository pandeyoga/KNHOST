"""Ledger SQLite lokal per printer — niat → mulai diterima ERP → sedang dikirim → terkirim → hasil → terlapor.

Aturan keselamatan (inti RACC-26):
  · `SENDING` ditulis DURABLE sebelum byte pertama ke printer. Sesudah crash, item `SENDING`/`SENT` tanpa hasil
    menjadi `unknown` ("terkirim tanpa hasil") — TIDAK PERNAH dikirim ulang otomatis.
  · Item `CLAIMED`/`INTENT`/`STARTED` belum menyentuh printer → aman dilanjutkan.
  · Hasil (`OUTCOME`) dikirim ulang ke ERP dengan `result_event_id` yang sama sampai diakui (`REPORTED`).
Kunci unik (job_id, item_id, attempt_id).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT NOT NULL, attempt_id TEXT NOT NULL, job_number TEXT, kind TEXT, revision INTEGER,
  expected_json TEXT, state TEXT NOT NULL, claimed_at TEXT, lease_expires_at TEXT, server_offset_s REAL,
  done_at TEXT, note TEXT, PRIMARY KEY (job_id, attempt_id));
CREATE TABLE IF NOT EXISTS items (
  job_id TEXT NOT NULL, item_id TEXT NOT NULL, attempt_id TEXT NOT NULL, seq INTEGER, roll_no TEXT, epc TEXT,
  payload_sha256 TEXT, zpl TEXT, state TEXT NOT NULL, print_status TEXT, encode_status TEXT, evidence_json TEXT,
  result_event_id TEXT, intent_at TEXT, start_at TEXT, sending_at TEXT, sent_at TEXT, outcome_at TEXT,
  reported_at TEXT, last_error TEXT, PRIMARY KEY (job_id, item_id, attempt_id));
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, level TEXT, job_id TEXT,
  item_id TEXT, message TEXT);
"""
# Urutan status item di ledger
CLAIMED, INTENT, STARTED, SENDING, SENT, OUTCOME, REPORTED, SKIPPED = (
    "CLAIMED", "INTENT", "STARTED", "SENDING", "SENT", "OUTCOME", "REPORTED", "SKIPPED")
NOT_SENT = (CLAIMED, INTENT, STARTED)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Ledger:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")   # durable: tulisan SENDING selamat dari mati listrik
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self.db.close()

    # ── meta ──
    def instance_id(self) -> str:
        """ID instance connector — TETAP lintas restart (lease stabil untuk instance yang sama)."""
        with self._lock:
            row = self.db.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()
            if row:
                return row["value"]
            iid = f"conn_{uuid.uuid4().hex[:16]}"
            self.db.execute("INSERT INTO meta(key,value) VALUES('instance_id',?)", (iid,))
            return iid

    def log(self, level: str, message: str, job_id: str = "", item_id: str = "") -> None:
        with self._lock:
            self.db.execute("INSERT INTO events(at,level,job_id,item_id,message) VALUES(?,?,?,?,?)",
                            (now(), level, job_id, item_id, message[:1000]))

    # ── job ──
    def upsert_job(self, job: Dict[str, Any], server_offset_s: float = 0.0) -> None:
        lease = job.get("lease") or {}
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute(
                    "INSERT INTO jobs(job_id,attempt_id,job_number,kind,revision,expected_json,state,claimed_at,"
                    "lease_expires_at,server_offset_s) VALUES(?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(job_id,attempt_id) DO UPDATE SET lease_expires_at=excluded.lease_expires_at, "
                    "revision=excluded.revision",
                    (job["id"], lease.get("attempt_id"), job.get("job_number"), job.get("kind"), job.get("revision"),
                     json.dumps(job.get("expected_responses") or {}), "active", now(), lease.get("expires_at"),
                     server_offset_s))
                for seq, it in enumerate(job.get("items") or []):
                    st = CLAIMED if it.get("printable") else SKIPPED
                    self.db.execute(
                        "INSERT OR IGNORE INTO items(job_id,item_id,attempt_id,seq,roll_no,epc,payload_sha256,zpl,state)"
                        " VALUES(?,?,?,?,?,?,?,?,?)",
                        (job["id"], it["item_id"], lease.get("attempt_id"), seq, it.get("roll_no"), it.get("epc"),
                         it.get("payload_sha256"), it.get("zpl") or "", st))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def set_lease(self, job_id: str, attempt_id: str, expires_at: str) -> None:
        with self._lock:
            self.db.execute("UPDATE jobs SET lease_expires_at=? WHERE job_id=? AND attempt_id=?",
                            (expires_at, job_id, attempt_id))

    def has_attempt(self, job_id: str, attempt_id: str) -> bool:
        with self._lock:
            return bool(self.db.execute("SELECT 1 FROM jobs WHERE job_id=? AND attempt_id=?",
                                        (job_id, attempt_id)).fetchone())

    def active_job(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.db.execute("SELECT * FROM jobs WHERE state='active' ORDER BY claimed_at LIMIT 1").fetchone()
            return dict(row) if row else None

    def finish_job(self, job_id: str, attempt_id: str, state: str = "done", note: str = "") -> None:
        with self._lock:
            self.db.execute("UPDATE jobs SET state=?, done_at=?, note=? WHERE job_id=? AND attempt_id=?",
                            (state, now(), note[:300], job_id, attempt_id))

    # ── item ──
    def items(self, job_id: str, attempt_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.db.execute(
                "SELECT * FROM items WHERE job_id=? AND attempt_id=? ORDER BY seq", (job_id, attempt_id))]

    def item(self, job_id: str, item_id: str, attempt_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self.db.execute("SELECT * FROM items WHERE job_id=? AND item_id=? AND attempt_id=?",
                                (job_id, item_id, attempt_id)).fetchone()
            return dict(r) if r else None

    def ensure_item(self, job_id: str, attempt_id: str, it: Dict[str, Any], state: str) -> None:
        with self._lock:
            self.db.execute("INSERT OR IGNORE INTO items(job_id,item_id,attempt_id,seq,roll_no,epc,payload_sha256,zpl,"
                            "state) VALUES(?,?,?,?,?,?,?,?,?)",
                            (job_id, it["item_id"], attempt_id, 9999, it.get("roll_no"), it.get("epc"),
                             it.get("payload_sha256"), "", state))

    def transition(self, job_id: str, item_id: str, attempt_id: str, to: str, *, from_states: Optional[List[str]] = None,
                   **fields: Any) -> bool:
        """Ubah status item secara atomik (prasyarat `from_states`). Kembali False bila prasyarat tidak cocok."""
        stamp = {INTENT: "intent_at", STARTED: "start_at", SENDING: "sending_at", SENT: "sent_at",
                 OUTCOME: "outcome_at", REPORTED: "reported_at"}.get(to)
        sets = ["state=?"]
        vals: List[Any] = [to]
        if stamp:
            sets.append(f"{stamp}=?")
            vals.append(now())
        for k, v in fields.items():
            sets.append(f"{k}=?")
            vals.append(json.dumps(v) if k == "evidence_json" and not isinstance(v, str) else v)
        sql = f"UPDATE items SET {', '.join(sets)} WHERE job_id=? AND item_id=? AND attempt_id=?"
        vals += [job_id, item_id, attempt_id]
        if from_states:
            sql += f" AND state IN ({','.join('?' * len(from_states))})"
            vals += list(from_states)
        with self._lock:
            cur = self.db.execute(sql, vals)
            return cur.rowcount == 1

    def record_outcome(self, job_id: str, item_id: str, attempt_id: str, print_status: str, encode_status: str,
                       evidence: Dict[str, Any]) -> str:
        """Simpan hasil + result_event_id STABIL (dipakai ulang sampai ERP mengakui)."""
        rid = f"res_{attempt_id[-12:]}_{item_id[-16:]}_{uuid.uuid4().hex[:8]}"
        self.transition(job_id, item_id, attempt_id, OUTCOME, print_status=print_status, encode_status=encode_status,
                        evidence_json=evidence, result_event_id=rid)
        return rid

    def pending_results(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.db.execute(
                "SELECT * FROM items WHERE state=? ORDER BY outcome_at", (OUTCOME,))]

    def recover_after_crash(self) -> List[Dict[str, Any]]:
        """Item yang sedang/selesai dikirim tanpa hasil → unknown (bukan dikirim ulang)."""
        with self._lock:
            rows = [dict(r) for r in self.db.execute(
                "SELECT * FROM items WHERE state IN (?,?)", (SENDING, SENT))]
        for r in rows:
            detail = ("Connector berhenti saat payload sedang dikirim" if r["state"] == SENDING
                      else "Connector berhenti setelah payload terkirim, sebelum hasil diketahui")
            self.record_outcome(r["job_id"], r["item_id"], r["attempt_id"], "unknown",
                                "unknown" if r.get("epc") else "not_applicable",
                                {"source": "connector_recovery", "detail": detail + " — TIDAK dicetak ulang otomatis."})
            self.log("WARN", f"pulih crash: {r['roll_no']} {detail}", r["job_id"], r["item_id"])
        return rows

    def counts(self) -> Dict[str, int]:
        with self._lock:
            out = {r["state"]: r["n"] for r in self.db.execute("SELECT state, COUNT(*) n FROM items GROUP BY state")}
            unk = self.db.execute("SELECT COUNT(*) n FROM items WHERE print_status='unknown' OR encode_status='unknown'"
                                  ).fetchone()["n"]
            act = self.db.execute("SELECT COUNT(*) n FROM jobs WHERE state='active'").fetchone()["n"]
        return {"pending_results": out.get(OUTCOME, 0), "reported": out.get(REPORTED, 0), "unknown_items": unk,
                "sending": out.get(SENDING, 0) + out.get(SENT, 0), "active_jobs": act}

    def events_tail(self, n: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,))]
