"""Pengurai balasan printer ZPL: ~HS (host status), ~HQES (status galat), ^RVE (_+,n_ / _-,n_), ^HV (EPC[...]).

Format diambil dari bahasa ZPL Zebra — BELUM TERBUKTI di firmware CP30EN (lihat daftar uji meja). Pengurai sengaja
toleran: bila balasan tidak dikenal, hasilnya `None`/unknown — tidak pernah dianggap sukses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

STX, ETX = "\x02", "\x03"
_FRAME = re.compile(r"\x02(.*?)\x03", re.S)
_RV = re.compile(r"_([+-]),(\d+)_")
_HV = re.compile(r"EPC\[([0-9A-Fa-f]*)\]")
_HQES_ERR = re.compile(r"ERRORS:\s*(\d)\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})")
_HQES_WARN = re.compile(r"WARNINGS:\s*(\d)\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})")

# Bit galat grup 1 (~HQES, ZPL Zebra) — perkiraan; CP30EN wajib dicek.
ERROR_BITS = {0x1: "media_out", 0x2: "ribbon_out", 0x4: "head_open", 0x8: "cutter_fault",
              0x10: "head_over_temp", 0x20: "motor_over_temp", 0x40: "bad_head_element", 0x80: "head_detect_error"}


@dataclass
class HostStatus:
    paper_out: bool = False
    paused: bool = False
    formats_in_buffer: int = 0
    buffer_full: bool = False
    partial_format: bool = False
    head_up: bool = False
    ribbon_out: bool = False
    labels_remaining: int = 0
    label_length: Optional[int] = None
    raw: List[str] = field(default_factory=list)

    @property
    def idle(self) -> bool:
        return self.formats_in_buffer == 0 and self.labels_remaining == 0 and not self.partial_format

    @property
    def blocking_reason(self) -> Optional[str]:
        if self.paper_out:
            return "paper_out"
        if self.head_up:
            return "head_open"
        if self.ribbon_out:
            return "ribbon_out"
        if self.paused:
            return "paused"
        return None


def frames(data: str) -> List[str]:
    return [m.group(1) for m in _FRAME.finditer(data or "")]


def parse_hs(data: str) -> Optional[HostStatus]:
    """~HS → tiga bingkai STX…ETX. Bingkai 1: aaa,b(kertas habis),c(jeda),dddd(panjang),eee(format di buffer),
    f(buffer penuh),g,h(format parsial),…; bingkai 2: mmm,n,o(head up),p(ribbon habis),q,r,s,t,uuuuuuuu(sisa label),…"""
    fr = frames(data)
    if len(fr) < 2:
        return None
    a = [x.strip() for x in fr[0].split(",")]
    b = [x.strip() for x in fr[1].split(",")]
    try:
        return HostStatus(paper_out=a[1] == "1", paused=a[2] == "1", label_length=int(a[3] or 0),
                          formats_in_buffer=int(a[4] or 0), buffer_full=a[5] == "1",
                          partial_format=len(a) > 7 and a[7] == "1",
                          head_up=len(b) > 2 and b[2] == "1", ribbon_out=len(b) > 3 and b[3] == "1",
                          labels_remaining=int(b[8]) if len(b) > 8 and b[8].isdigit() else 0, raw=fr[:3])
    except (IndexError, ValueError):
        return None


def parse_hqes(data: str) -> Optional[Dict[str, object]]:
    m = _HQES_ERR.search(data or "")
    if not m:
        return None
    flags = int(m.group(3), 16)
    w = _HQES_WARN.search(data or "")
    return {"error": m.group(1) == "1" or flags != 0, "error_flags": flags,
            "errors": [name for bit, name in ERROR_BITS.items() if flags & bit] or (["other"] if flags else []),
            "warning_flags": int(w.group(3), 16) if w else 0}


def parse_rv(data: str) -> List[Dict[str, object]]:
    return [{"ok": m.group(1) == "+", "tries": int(m.group(2))} for m in _RV.finditer(data or "")]


def parse_hv(data: str) -> List[str]:
    return [m.group(1).upper() for m in _HV.finditer(data or "")]


def parse_hi(data: str) -> Optional[str]:
    fr = frames(data)
    return fr[0].strip() if fr else None
