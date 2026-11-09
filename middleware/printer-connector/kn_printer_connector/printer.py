"""Adapter printer ZPL lewat TCP (port 9100) — readiness (~HS/~HQES), kirim satu label, tunggu hasil.

Prinsip: penyerahan byte ke socket hanya berarti TERKIRIM, bukan tercetak. Hasil dinilai dari status printer
(buffer kosong, tanpa galat) dan balasan RFID (^HV baca balik EPC / ^RVE). Timeout atau balasan tak dikenal =
`unknown` — tidak pernah dianggap sukses. Semua perintah & format balasan BELUM TERBUKTI di CP30EN.
"""
from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from . import zpl_status as zs


class PrinterUnavailable(Exception):
    """Tidak tersambung / tidak siap SEBELUM payload dikirim — item belum menyentuh printer, aman dicoba lagi."""


@dataclass
class PrinterStatus:
    reachable: bool
    state: str                      # ready | printing | paused | paper_out | ribbon_out | head_open | error | offline | unknown
    detail: str = ""
    hs: Optional[zs.HostStatus] = None
    hqes: Optional[Dict[str, Any]] = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def ready(self) -> bool:
        return self.reachable and self.state == "ready"

    def as_telemetry(self) -> Dict[str, Any]:
        flags = {}
        if self.hs:
            flags = {"paper_out": self.hs.paper_out, "paused": self.hs.paused, "head_up": self.hs.head_up,
                     "ribbon_out": self.hs.ribbon_out, "formats_in_buffer": self.hs.formats_in_buffer,
                     "labels_remaining": self.hs.labels_remaining}
        if self.hqes:
            flags["error_flags"] = self.hqes.get("error_flags")
            flags["errors"] = self.hqes.get("errors")
        return {"state": self.state, "reachable": self.reachable, "detail": self.detail, "flags": flags,
                "checked_at": self.checked_at}


@dataclass
class Outcome:
    print_status: str               # confirmed | failed | unknown
    encode_status: str              # confirmed | failed | unknown | not_applicable
    evidence: Dict[str, Any]

    @property
    def result(self) -> str:
        if self.print_status == "failed" or self.encode_status == "failed":
            return "failed"
        if self.print_status == "confirmed" and self.encode_status in ("confirmed", "not_applicable"):
            return "confirmed"
        return "unknown"


def classify(hs: Optional[zs.HostStatus], hqes: Optional[Dict[str, Any]]) -> str:
    if hs is None:
        return "unknown"
    reason = hs.blocking_reason
    if reason:
        return reason
    if hqes and hqes.get("error"):
        errs = hqes.get("errors") or []
        return "paper_out" if "media_out" in errs else "head_open" if "head_open" in errs else \
            "ribbon_out" if "ribbon_out" in errs else "error"
    return "ready" if hs.idle else "printing"


class ZplTcpPrinter:
    def __init__(self, host: str, port: int = 9100, connect_timeout_s: float = 3.0, io_timeout_s: float = 5.0):
        self.host, self.port = host, port
        self.connect_timeout, self.io_timeout = connect_timeout_s, io_timeout_s

    def _connect(self) -> socket.socket:
        try:
            s = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as e:
            raise PrinterUnavailable(f"tidak tersambung ke {self.host}:{self.port} ({e})")
        s.settimeout(0.3)
        return s

    @staticmethod
    def _read_for(sock: socket.socket, seconds: float, until: Optional[Callable[[str], bool]] = None) -> str:
        buf, end = "", time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                if until and until(buf):
                    break
                continue
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            if until and until(buf):
                break
        return buf

    def _probe(self, sock: socket.socket, timeout: float) -> PrinterStatus:
        sock.sendall(b"~HS")
        raw = self._read_for(sock, timeout, lambda b: b.count(zs.ETX) >= 3)
        hs = zs.parse_hs(raw)
        hqes = None
        if hs is not None:
            sock.sendall(b"~HQES")
            hqes = zs.parse_hqes(self._read_for(sock, min(timeout, 1.5), lambda b: zs.ETX in b))
        state = classify(hs, hqes)
        return PrinterStatus(reachable=True, state=state, hs=hs, hqes=hqes,
                             detail="" if hs else "printer tidak menjawab ~HS (format status tidak dikenal/timeout)")

    def status(self, timeout: float = 3.0) -> PrinterStatus:
        try:
            sock = self._connect()
        except PrinterUnavailable as e:
            return PrinterStatus(reachable=False, state="offline", detail=str(e))
        try:
            return self._probe(sock, timeout)
        except OSError as e:
            return PrinterStatus(reachable=False, state="offline", detail=f"putus saat cek status ({e})")
        finally:
            sock.close()

    def identify(self, timeout: float = 2.0) -> Optional[str]:
        try:
            sock = self._connect()
        except PrinterUnavailable:
            return None
        try:
            sock.sendall(b"~HI")
            return zs.parse_hi(self._read_for(sock, timeout, lambda b: zs.ETX in b))
        except OSError:
            return None
        finally:
            sock.close()

    def print_item(self, zpl: str, *, rfid: bool, epc: Optional[str], expected: Dict[str, Any],
                   on_sending: Callable[[], Any], on_sent: Callable[[], Any], outcome_timeout_s: float = 45.0,
                   pause_wait_s: float = 600.0, probe_timeout_s: float = 3.0,
                   stop: Optional[threading.Event] = None,
                   on_state: Optional[Callable[[PrinterStatus], Any]] = None) -> Outcome:
        """Kirim SATU label lalu tunggu hasilnya. `on_sending` dipanggil (dan harus durable) SEBELUM byte pertama."""
        sock = self._connect()  # gagal → PrinterUnavailable (belum terkirim)
        try:
            pre = self._probe(sock, probe_timeout_s)
            if not pre.ready:
                raise PrinterUnavailable(f"printer belum siap ({pre.state}) {pre.detail}".strip())
            on_sending()
            try:
                sock.sendall(zpl.encode("utf-8"))
            except OSError as e:
                return Outcome("unknown", "unknown" if rfid else "not_applicable",
                               {"source": "connector", "detail": f"putus saat mengirim payload ({e})",
                                "printer_state": "offline"})
            on_sent()
            return self._await_outcome(sock, rfid=rfid, epc=epc, expected=expected, timeout=outcome_timeout_s,
                                       pause_wait=pause_wait_s, probe_timeout=probe_timeout_s, stop=stop,
                                       on_state=on_state)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _await_outcome(self, sock: socket.socket, *, rfid: bool, epc: Optional[str], expected: Dict[str, Any],
                       timeout: float, pause_wait: float, probe_timeout: float, stop: Optional[threading.Event],
                       on_state: Optional[Callable[[PrinterStatus], Any]]) -> Outcome:
        want_hv = rfid and bool(expected.get("readback"))
        want_rv = rfid and bool(expected.get("encode_result"))
        replies = ""
        deadline = time.monotonic() + timeout
        paused_since: Optional[float] = None
        done, last_state, disconnected, seen_busy = False, "printing", False, False
        idle_seen_at: Optional[float] = None
        sent_at = time.monotonic()
        while time.monotonic() < deadline and not (stop and stop.is_set()):
            try:
                replies += self._read_for(sock, 0.4)
                sock.sendall(b"~HS")
                raw = self._read_for(sock, probe_timeout, lambda b: b.count(zs.ETX) >= 3)
            except OSError:
                disconnected = True
                break
            # balasan RFID dapat datang bercampur dengan bingkai status
            replies += zs._FRAME.sub("", raw)  # noqa: SLF001
            hs = zs.parse_hs(raw)
            st = PrinterStatus(reachable=True, state=classify(hs, None), hs=hs,
                               detail="" if hs else "tidak ada jawaban ~HS")
            last_state = st.state
            if on_state:
                on_state(st)
            if hs is None:
                continue
            if hs.blocking_reason:
                if paused_since is None:
                    paused_since = time.monotonic()
                    deadline = max(deadline, paused_since + pause_wait)   # tunggu operator memasang kertas, dll.
                continue
            paused_since = None
            got = (bool(zs.parse_hv(replies)) or not want_hv) and (bool(zs.parse_rv(replies)) or not want_rv)
            t = time.monotonic()
            if not hs.idle:
                seen_busy, idle_seen_at = True, None
                continue
            # ~HS bisa dijawab SEBELUM format selesai diterima printer → "idle" palsu. Selesai hanya bila printer
            # pernah terlihat sibuk / balasan RFID datang, atau sesudah jeda minimum (uji meja: cek perilaku CP30EN).
            idle_seen_at = idle_seen_at or t
            if (want_hv or want_rv) and got and (seen_busy or t - sent_at > 1.0):
                done = True
                break
            if not (want_hv or want_rv) and (seen_busy or t - sent_at > 1.5):
                done = True
                break
            if t - idle_seen_at > 2.5:   # diam tanpa balasan RFID: cetak dianggap selesai, encode tidak pasti
                done = True
                break
        try:
            replies += self._read_for(sock, 0.3)
        except OSError:
            pass
        hv, rv = zs.parse_hv(replies), zs.parse_rv(replies)
        ev: Dict[str, Any] = {"source": "printer_status", "printer_state": last_state, "busy_observed": seen_busy,
                              "duplicate_replies": len(hv) > 1 or len(rv) > 1}
        if hv:
            ev["readback_epc"] = hv[0]
            ev["source"] = "printer_readback"
        if rv:
            ev["encode_result"] = rv[0]
        print_status = "confirmed" if done else "unknown"
        if not done:
            ev["detail"] = ("koneksi printer putus sebelum hasil diketahui" if disconnected else
                            f"hasil tidak diketahui dalam batas waktu (status terakhir: {last_state})")
        if not rfid:
            return Outcome(print_status, "not_applicable", ev)
        parts = []
        if want_rv:
            parts.append(("confirmed" if rv[0]["ok"] else "failed") if rv else "unknown")
        if want_hv:
            parts.append(("confirmed" if hv[0] == (epc or "").upper() else "failed") if hv else "unknown")
        if not parts:
            parts.append("confirmed" if done and expected.get("confirm_without_readback") else "unknown")
        enc = "failed" if "failed" in parts else "confirmed" if all(p == "confirmed" for p in parts) else "unknown"
        if enc == "failed":
            ev["detail"] = (ev.get("detail", "") + " | encode gagal / EPC baca balik berbeda — label VOID, musnahkan "
                            "sesuai SOP").strip(" |")
        return Outcome(print_status, enc, ev)
