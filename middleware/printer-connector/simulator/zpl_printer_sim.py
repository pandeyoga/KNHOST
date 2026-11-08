"""Simulator printer ZPL RFID (TCP) — pengganti CP30EN untuk uji connector & alur ERP tanpa perangkat.

Meniru (BUKAN bukti perilaku CP30EN): penerimaan format `^XA…^XZ` ke buffer, cetak berurutan, `^RFW,H` (tulis
EPC ke "chip"), `^RVE` (balasan `_+,n_`/`_-,n_`), `^RFR`+`^HV` (baca balik `EPC[…]`), `~HS`, `~HQES`, `~HI`, `~JA`.

Gangguan yang bisa diatur (`faults`, nomor = urutan format yang DITERIMA, mulai 1):
  paper_out_after=N        sesudah N label tercetak → kertas habis + jeda (format tertahan di buffer)
  encode_fail={3,6}        tulis chip gagal → label VOID, ^RV '-', ^HV kosong
  readback_mismatch={4}    chip berisi EPC lain (baca balik berbeda)
  hang={9}                 label macet: tidak pernah selesai sampai `release_hang()` (uji timeout → tidak pasti)
  drop_at=N                koneksi diputus saat format ke-N diterima (`drop_prints=True` → label tetap tercetak)
  duplicate_results=True   balasan ^RV/^HV dikirim dua kali
  status_mute=True         tidak menjawab ~HS/~HQES (uji timeout status)
  head_open=True           kepala terbuka (tidak siap)

Pakai manual:  python simulator/zpl_printer_sim.py --port 9100 --encode-fail 3,6 --paper-out-after 5
"""
from __future__ import annotations

import argparse
import re
import socket
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

STX, ETX = "\x02", "\x03"
_RFW = re.compile(r"\^RFW,H(?:,[^\^]*)?\^FD([0-9A-Fa-f]+)\^FS")
_FD = re.compile(r"\^FD(.*?)\^FS", re.S)
_TILDE = ("~HQES", "~HS", "~HI", "~JA")


class SimPrinter:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, dpi: int = 203, print_delay_s: float = 0.15,
                 faults: Optional[Dict[str, Any]] = None, model: str = "CP30-SIM"):
        self.host, self.port, self.dpi, self.delay, self.model = host, port, dpi, print_delay_s, model
        self.faults: Dict[str, Any] = dict(faults or {})
        self.cv = threading.Condition()
        self.queue: Deque[Tuple[int, str, Any]] = deque()
        self.current: Optional[int] = None
        self.received = 0
        self.labels: List[Dict[str, Any]] = []
        self.chips: List[str] = []
        self.paper_out = False
        self.paused = False
        self.head_open = bool(self.faults.get("head_open"))
        self.rv_enabled = False
        self._released: set = set()
        self._srv: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        self.connections = 0

    # ── kontrol uji ──
    def set_fault(self, **kw: Any) -> None:
        with self.cv:
            self.faults.update(kw)
            if "head_open" in kw:
                self.head_open = bool(kw["head_open"])
            self.cv.notify_all()

    def reload_paper(self) -> None:
        with self.cv:
            self.paper_out = False
            self.paused = False
            self.faults.pop("paper_out_after", None)
            self.cv.notify_all()

    def release_hang(self) -> None:
        with self.cv:
            self._released |= set(self.faults.get("hang") or [])
            self.cv.notify_all()

    def printed_epcs(self) -> List[str]:
        return [lb["chip_epc"] for lb in self.labels if lb.get("chip_epc")]

    # ── server ──
    def start(self) -> "SimPrinter":
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(8)
        self.port = self._srv.getsockname()[1]
        for target in (self._accept_loop, self._print_loop):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def stop(self) -> None:
        self._stop.set()
        with self.cv:
            self.cv.notify_all()
        if self._srv:
            try:
                self._srv.close()
            except OSError:
                pass

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _status_frames(self) -> str:
        with self.cv:
            in_buf = len(self.queue)
            remaining = 1 if self.current is not None else 0
            paused = 1 if (self.paused or self.paper_out) else 0
            f1 = f"030,{1 if self.paper_out else 0},{paused},0176,{in_buf:03d},0,0,0,000,0,0,0"
            f2 = f"000,0,{1 if self.head_open else 0},0,0,2,6,0,{remaining:08d},1,000"
        return f"{STX}{f1}{ETX}\r\n{STX}{f2}{ETX}\r\n{STX}1234,0{ETX}\r\n"

    def _hqes(self) -> str:
        flags = (0x1 if self.paper_out else 0) | (0x4 if self.head_open else 0)
        return (f"{STX}\r\n  PRINTER STATUS\r\n    ERRORS:         {1 if flags else 0} 00000000 {flags:08X}\r\n"
                f"    WARNINGS:       0 00000000 00000000\r\n{ETX}\r\n")

    def _serve(self, conn: socket.socket) -> None:
        conn.settimeout(0.5)
        buf = ""
        alive = {"open": True}
        try:
            while not self._stop.is_set() and alive["open"]:
                try:
                    chunk = conn.recv(65536)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk.decode("utf-8", "replace")
                buf = self._consume(buf, conn, alive)
        finally:
            alive["open"] = False
            try:
                conn.close()
            except OSError:
                pass

    def _send(self, conn: socket.socket, alive: Dict[str, bool], text: str) -> None:
        if not alive.get("open"):
            return
        try:
            conn.sendall(text.encode("utf-8"))
        except OSError:
            alive["open"] = False

    def _consume(self, buf: str, conn: socket.socket, alive: Dict[str, bool]) -> str:
        while buf:
            buf = buf.lstrip("\r\n ")
            if not buf:
                return ""
            if buf.startswith("~"):
                cmd = next((c for c in _TILDE if buf.startswith(c)), None)
                if not cmd:
                    if len(buf) < 5:
                        return buf
                    buf = buf[1:]
                    continue
                buf = buf[len(cmd):]
                if self.faults.get("status_mute") and cmd in ("~HS", "~HQES"):
                    continue
                if cmd == "~HS":
                    self._send(conn, alive, self._status_frames())
                elif cmd == "~HQES":
                    self._send(conn, alive, self._hqes())
                elif cmd == "~HI":
                    self._send(conn, alive, f"{STX}{self.model},V0.1-SIM,{self.dpi},8192KB{ETX}\r\n")
                elif cmd == "~JA":
                    with self.cv:
                        self.queue.clear()
                continue
            start = buf.find("^XA")
            if start < 0:
                return buf[-2:] if buf.endswith("^") else ""
            end = buf.find("^XZ", start)
            if end < 0:
                return buf[start:]
            fmt = buf[start:end + 3]
            buf = buf[end + 3:]
            with self.cv:
                self.received += 1
                n = self.received
                drop = self.faults.get("drop_at") == n
                if not drop or self.faults.get("drop_prints"):
                    self.queue.append((n, fmt, (conn, alive) if not drop else None))
                    self.cv.notify_all()
            if drop:
                alive["open"] = False
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                return ""
        return buf

    def _print_loop(self) -> None:
        while not self._stop.is_set():
            with self.cv:
                while not self._stop.is_set() and (not self.queue or self.paper_out or self.paused or self.head_open):
                    self.cv.wait(0.2)
                if self._stop.is_set():
                    return
                poa = self.faults.get("paper_out_after")
                if poa is not None and len(self.labels) >= int(poa):
                    self.paper_out = True
                    self.paused = True
                    continue
                n, fmt, target = self.queue.popleft()
                self.current = n
            if n in set(self.faults.get("hang") or []):
                with self.cv:
                    while n not in self._released and not self._stop.is_set():
                        self.cv.wait(0.2)
            time.sleep(self.delay)
            self._print(n, fmt, target)
            with self.cv:
                self.current = None
                self.cv.notify_all()

    def _print(self, n: int, fmt: str, target: Any) -> None:
        m = _RFW.search(fmt)
        epc = m.group(1).upper() if m else None
        rv = "^RVE" in fmt or self.rv_enabled
        if "^RVE" in fmt:
            self.rv_enabled = True
        hv = "^HV" in fmt
        fail = epc is not None and n in set(self.faults.get("encode_fail") or [])
        chip = None
        if epc and not fail:
            chip = epc
            if n in set(self.faults.get("readback_mismatch") or []):
                chip = ("F" + epc[1:]) if epc[0] != "F" else ("E" + epc[1:])
        texts = [t for t in _FD.findall(fmt) if t and not re.fullmatch(r"[0-9A-Fa-f]{24}", t)]
        rec = {"n": n, "epc_expected": epc, "chip_epc": chip, "void": fail, "texts": texts,
               "at": datetime.now(timezone.utc).isoformat(), "zpl": fmt}
        with self.cv:
            self.labels.append(rec)
            if chip:
                self.chips.append(chip)
        if target is None:
            return
        conn, alive = target
        out = ""
        if epc is not None and rv:
            out += f"_{'-' if fail else '+'},1_"
        if epc is not None and hv:
            out += f"EPC[{'' if fail else chip}]\r\n"
        if out:
            self._send(conn, alive, out * (2 if self.faults.get("duplicate_results") else 1))


def main() -> None:
    ap = argparse.ArgumentParser(description="Simulator printer ZPL RFID")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9100)
    ap.add_argument("--dpi", type=int, default=203)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--paper-out-after", type=int)
    ap.add_argument("--encode-fail", default="")
    ap.add_argument("--hang", default="")
    ap.add_argument("--drop-at", type=int)
    ap.add_argument("--duplicate-results", action="store_true")
    a = ap.parse_args()
    nums = lambda s: {int(x) for x in s.split(",") if x.strip()}  # noqa: E731
    faults: Dict[str, Any] = {"encode_fail": nums(a.encode_fail), "hang": nums(a.hang),
                              "duplicate_results": a.duplicate_results}
    if a.paper_out_after is not None:
        faults["paper_out_after"] = a.paper_out_after
    if a.drop_at:
        faults["drop_at"] = a.drop_at
    sim = SimPrinter(a.host, a.port, a.dpi, a.delay, faults).start()
    print(f"Simulator printer ZPL di {a.host}:{sim.port} (Ctrl+C untuk berhenti)")
    seen = 0
    try:
        while True:
            time.sleep(0.5)
            while seen < len(sim.labels):
                lb = sim.labels[seen]
                seen += 1
                print(f"label #{lb['n']}: EPC chip={lb['chip_epc'] or '-'} {'VOID ' if lb['void'] else ''}"
                      f"teks={' | '.join(lb['texts'][:4])}")
    except KeyboardInterrupt:
        sim.stop()


if __name__ == "__main__":
    main()
