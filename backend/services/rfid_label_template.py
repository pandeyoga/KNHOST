"""PREP-F — templat label RFID 70 × 22 mm untuk printer Chainway CP30EN (+ pratinjau).

Satu fungsi tata letak (`layout`) menghasilkan elemen ber-satuan dot yang dipakai DUA kali:
  · dirender ke ZPL (`render_zpl`) untuk printer, dan
  · dikirim apa adanya ke UI sebagai pratinjau SVG (perkiraan) — pratinjau tidak bisa menyimpang dari ZPL.

Profil printer (per perangkat, `rfid_devices.printer_profile`) mengatur dpi 203/300, ukuran media, geser (offset),
posisi inlay (`^RS` p), jumlah percobaan encode, mode galat, dan cara printer melaporkan hasil encode.

PERINGATAN (asumsi bertanda): seluruh perintah RFID — `^RS`, `^RFW,H`, `^RFR`+`^HV` (baca balik), `^RVE`
(laporan hasil encode) — diambil dari bahasa ZPL Zebra dan BELUM TERBUKTI di firmware CP30EN. Lebar huruf font 0
juga perkiraan konservatif. Semua masuk daftar uji meja di `docs/rfid/hasil/PREP-F-PRINTER-CP30EN.md`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from services.epc import canonical_epc, display_epc
from services.zpl_text import zpl_field

TEMPLATE_ID = "rfid_70x22"
TEMPLATE_VERSION = 1
BASE_DPI = 203

DEFAULT_PROFILE: Dict[str, Any] = {
    "template": TEMPLATE_ID,
    "dpi": 203,                    # 203 | 300 (cek label pabrik / ~HI saat uji meja)
    "label_width_mm": 70.0,
    "label_height_mm": 22.0,
    "offset_x_dots": 0,            # ^LH x — geser seluruh isi ke kanan (0..200)
    "offset_y_dots": 0,            # ^LH y — geser ke bawah (0..200)
    "label_top": 0,                # ^LT −120..120 — penyetelan halus vertikal
    "darkness": None,              # ^MD −30..30 (None = setelan printer)
    "print_speed": None,           # ^PR 1..14 (None = setelan printer)
    "rfid_position": "",           # ^RS p: "" = bawaan printer; mis. "F0", "B4" (mm) atau angka dot (firmware lama)
    "rfid_tries": 1,               # ^RS n 1..10 — 1 = satu label per item (hasil per item jelas)
    "rfid_error_mode": "N",        # ^RS e: N lanjut | P jeda | E mode galat
    "void_length_dots": None,      # ^RS v — panjang cetakan VOID (None = bawaan)
    "encode_report": "hv",         # none | hv (^RFR+^HV baca balik EPC) | rv (^RVE _+,n_/_-,n_) | hv+rv
    "confirm_without_readback": False,  # encode_report=none: True → tanpa galat dianggap encode terkonfirmasi
    "qr_magnification": None,      # None = otomatis dari tinggi label
    "media_rfid": True,            # media berinlay: label cetak ulang teks membawa chip kosong (lihat laporan)
}

ENCODE_REPORTS = ("none", "hv", "rv", "hv+rv")
ERROR_MODES = ("N", "P", "E")
_HV_FIELD = 9
HV_HEADER = "EPC["
HV_TERM = "]"


def normalize_profile(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Profil tervalidasi + nilai bawaan. Nilai di luar batas DITOLAK (ValueError), tidak dipotong diam-diam."""
    p = dict(DEFAULT_PROFILE)
    for k, v in (raw or {}).items():
        if k in DEFAULT_PROFILE:
            p[k] = v
    try:
        p["dpi"] = int(p["dpi"])
        p["label_width_mm"] = float(p["label_width_mm"])
        p["label_height_mm"] = float(p["label_height_mm"])
        p["offset_x_dots"] = int(p["offset_x_dots"] or 0)
        p["offset_y_dots"] = int(p["offset_y_dots"] or 0)
        p["label_top"] = int(p["label_top"] or 0)
        p["rfid_tries"] = int(p["rfid_tries"] or 1)
        p["darkness"] = None if p["darkness"] in (None, "") else int(p["darkness"])
        p["print_speed"] = None if p["print_speed"] in (None, "") else int(p["print_speed"])
        p["void_length_dots"] = None if p["void_length_dots"] in (None, "") else int(p["void_length_dots"])
        p["qr_magnification"] = None if p["qr_magnification"] in (None, "") else int(p["qr_magnification"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"Profil printer tidak valid: {e}")
    checks = [
        (p["dpi"] in (203, 300), "dpi harus 203 atau 300"),
        (20 <= p["label_width_mm"] <= 110, "lebar label 20–110 mm"),
        (10 <= p["label_height_mm"] <= 100, "tinggi label 10–100 mm"),
        (0 <= p["offset_x_dots"] <= 200 and 0 <= p["offset_y_dots"] <= 200, "offset 0–200 dot"),
        (-120 <= p["label_top"] <= 120, "label top −120..120"),
        (1 <= p["rfid_tries"] <= 10, "jumlah percobaan encode 1–10"),
        (p["rfid_error_mode"] in ERROR_MODES, "mode galat RFID N/P/E"),
        (p["encode_report"] in ENCODE_REPORTS, f"laporan encode salah satu {', '.join(ENCODE_REPORTS)}"),
        (p["darkness"] is None or -30 <= p["darkness"] <= 30, "darkness −30..30"),
        (p["print_speed"] is None or 1 <= p["print_speed"] <= 14, "kecepatan 1–14"),
        (p["qr_magnification"] is None or 1 <= p["qr_magnification"] <= 10, "pembesaran QR 1–10"),
    ]
    for ok, msg in checks:
        if not ok:
            raise ValueError(f"Profil printer tidak valid: {msg}")
    pos = str(p.get("rfid_position") or "").strip().upper()
    if pos and not (pos.isdigit() or (pos[0] in "FB" and pos[1:].isdigit())):
        raise ValueError("Profil printer tidak valid: posisi inlay kosong, angka dot, atau F/B + mm (mis. F0, B4)")
    p["rfid_position"] = pos
    p["confirm_without_readback"] = bool(p["confirm_without_readback"])
    p["media_rfid"] = bool(p["media_rfid"])
    p["template"] = TEMPLATE_ID
    return p


def profile_key(profile: Dict[str, Any]) -> str:
    """Sidik profil (12 hex) — tercatat per item supaya payload yang dicetak bisa ditelusuri ke profil."""
    blob = json.dumps({k: profile.get(k) for k in sorted(DEFAULT_PROFILE)}, sort_keys=True, default=str)
    return hashlib.sha256(f"{TEMPLATE_VERSION}|{blob}".encode()).hexdigest()[:12]


def label_dims(profile: Dict[str, Any]) -> Tuple[int, int]:
    dpmm = profile["dpi"] / 25.4
    return round(profile["label_width_mm"] * dpmm), round(profile["label_height_mm"] * dpmm)


def _qr_modules(data: str) -> int:
    """Perkiraan konservatif versi QR (mode byte, koreksi galat M): versi v → 17 + 4v modul."""
    n = len(data.encode("utf-8"))
    for v, cap in ((1, 14), (2, 26), (3, 42), (4, 62), (5, 84)):
        if n <= cap:
            return 17 + 4 * v
    return 17 + 4 * 6


def _fit(text: str, max_chars: int) -> Tuple[str, bool]:
    t = " ".join(str(text or "").split())
    return (t, False) if len(t) <= max_chars else (t[:max(1, max_chars)].rstrip(), True)


def _fmt_qty(qty: Any, unit: str) -> str:
    try:
        q = float(qty or 0)
    except (TypeError, ValueError):
        q = 0.0
    return f"{q:g} {unit or ''}".strip()


def label_content(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Isi terbaca manusia dari snapshot item (dibekukan saat job dibuat)."""
    epc = snapshot.get("epc") or ""
    return {
        "title": snapshot.get("product_name") or snapshot.get("sku") or "",
        "sku": snapshot.get("sku") or "",
        "roll_no": snapshot.get("roll_no") or "",
        "lot": snapshot.get("lot") or "-",
        "qty": _fmt_qty(snapshot.get("qty"), snapshot.get("unit") or ""),
        "grade": snapshot.get("grade") or "",
        "epc": epc,
        "epc_tail": (epc[-8:] if epc else ""),
    }


# Lebar rata-rata glif font 0 ≈ 0,62 × parameter lebar (perkiraan konservatif — wajib dicek di uji meja).
_GLYPH = 0.62


def layout(snapshot: Dict[str, Any], profile: Dict[str, Any], *, rfid: bool = True) -> Dict[str, Any]:
    """Tata letak label (dot) — dasar 203 dpi, diskalakan untuk 300 dpi."""
    W, H = label_dims(profile)
    s = profile["dpi"] / BASE_DPI
    m = round(8 * s)
    c = label_content(snapshot)
    qr_data = c["roll_no"] or c["epc"]
    modules = _qr_modules(qr_data)
    mag = profile.get("qr_magnification") or max(2, min(round(6 * s), (H - 2 * m) // modules))
    qr = modules * mag
    elements: List[Dict[str, Any]] = [{
        "type": "qr", "x": m, "y": max(m, (H - qr) // 2), "size": qr, "mag": mag, "data": qr_data,
        "label": "QR nomor roll"}]
    x0 = m + qr + round(12 * s)
    tw = W - x0 - m
    epc_line = f"EPC ..{c['epc_tail']}" if c["epc_tail"] else "EPC -"
    if c["grade"]:
        epc_line += f"  G {c['grade']}"
    rows = [  # (teks, tinggi, lebar, y dasar 203 dpi, peran)
        (c["title"], 26, 22, 10, "title"),
        (c["sku"], 22, 18, 40, "sku"),
        (f"Roll {c['roll_no']}", 26, 24, 66, "roll_no"),
        (f"Lot {c['lot']} | {c['qty']}", 22, 18, 98, "lot_qty"),
        (epc_line, 20, 16, 126, "epc"),
    ]
    truncated: List[str] = []
    for text, fh, fw, y, role in rows:
        fh_s, fw_s = round(fh * s), round(fw * s)
        max_chars = max(4, int(tw // (fw_s * _GLYPH)))
        t, cut = _fit(text, max_chars)
        if cut:
            truncated.append(role)
        elements.append({"type": "text", "x": x0, "y": round(y * s), "h": fh_s, "w": fw_s, "text": t,
                         "max_chars": max_chars, "role": role, "width": tw})
    bottom = max(e["y"] + (e.get("h") or e.get("size") or 0) for e in elements)
    warnings = []
    if bottom > H - m // 2:
        warnings.append(f"Isi label melewati tinggi media ({bottom} > {H} dot) — periksa profil/ukuran label.")
    if x0 + 40 > W:
        warnings.append("Kolom teks terlalu sempit — kecilkan QR (pembesaran) atau perlebar label.")
    if truncated:
        warnings.append("Teks terpotong agar muat: " + ", ".join(truncated))
    return {"template": TEMPLATE_ID, "template_version": TEMPLATE_VERSION, "dpi": profile["dpi"],
            "width_dots": W, "height_dots": H, "width_mm": profile["label_width_mm"],
            "height_mm": profile["label_height_mm"], "offset_x_dots": profile["offset_x_dots"],
            "offset_y_dots": profile["offset_y_dots"], "rfid": rfid, "elements": elements,
            "truncated": truncated, "warnings": warnings, "epc_display": display_epc(c["epc"]) if c["epc"] else ""}


def _rfid_block(epc_hex: str, profile: Dict[str, Any]) -> List[str]:
    rs = ["8", profile["rfid_position"] or "",
          "" if profile["void_length_dots"] is None else str(profile["void_length_dots"]),
          str(profile["rfid_tries"]), profile["rfid_error_mode"]]
    out = [f"^RS{','.join(rs).rstrip(',')}"]
    if "rv" in profile["encode_report"]:
        out.append("^RVE")
    out.append(f"^RFW,H^FD{epc_hex}^FS")
    if "hv" in profile["encode_report"]:
        out.append(f"^RFR,H^FN{_HV_FIELD}^FS")
        out.append(f"^FH_^HV{_HV_FIELD},24,{HV_HEADER},{HV_TERM}_0D_0A,L^FS")
    return out


def render_zpl(snapshot: Dict[str, Any], profile: Dict[str, Any], *, rfid: bool = True) -> str:
    """ZPL satu label. `rfid=False` → label teks saja (cetak ulang teks / label QR) TANPA perintah tulis chip."""
    lay = layout(snapshot, profile, rfid=rfid)
    lines = ["^XA", "^CI28", f"^PW{lay['width_dots']}", f"^LL{lay['height_dots']}",
             f"^LH{profile['offset_x_dots']},{profile['offset_y_dots']}"]
    if profile["label_top"]:
        lines.append(f"^LT{profile['label_top']}")
    if profile["darkness"] is not None:
        lines.append(f"^MD{profile['darkness']}")
    if profile["print_speed"] is not None:
        lines.append(f"^PR{profile['print_speed']}")
    if rfid:
        lines += _rfid_block(canonical_epc(snapshot.get("epc")), profile)
    for e in lay["elements"]:
        if e["type"] == "qr":
            lines.append(f"^FO{e['x']},{e['y']}^BQN,2,{e['mag']}^FH_^FDMA,{zpl_field(e['data'], 60)}^FS")
        else:
            lines.append(f"^FO{e['x']},{e['y']}^A0N,{e['h']},{e['w']}^FH_^FD{zpl_field(e['text'], e['max_chars'])}^FS")
    lines.append("^PQ1")
    lines.append("^XZ")
    return "\n".join(lines)


def payload_sha256(zpl: str) -> str:
    return hashlib.sha256(zpl.encode("utf-8")).hexdigest()


def expected_responses(profile: Dict[str, Any], rfid: bool) -> Dict[str, Any]:
    """Untuk connector: balasan host yang ditunggu per label (tergantung profil). Disertakan di job & config."""
    if not rfid:
        return {"readback": False, "encode_result": False}
    return {"readback": "hv" in profile["encode_report"], "readback_header": HV_HEADER, "readback_term": HV_TERM,
            "encode_result": "rv" in profile["encode_report"],
            "confirm_without_readback": profile["confirm_without_readback"]}


def sample_snapshot() -> Dict[str, Any]:
    return {"product_name": "Batik Mega Mendung Premium", "sku": "BTK-MEGA-001", "roll_no": "RL-2611-000123",
            "lot": "LOT-2611-0042", "qty": 52.5, "unit": "yard", "grade": "A",
            "epc": "E2" + "0" * 14 + "12345678"}


def dot_budget(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Hitungan dot untuk laporan/UI: 70 mm @203 dpi ≈ 559–560 dot, @300 dpi ≈ 827 dot."""
    W, H = label_dims(profile)
    return {"dpi": profile["dpi"], "width_dots": W, "height_dots": H,
            "dots_per_mm": round(profile["dpi"] / 25.4, 3),
            "exact_width": round(profile["label_width_mm"] * profile["dpi"] / 25.4, 1),
            "exact_height": round(profile["label_height_mm"] * profile["dpi"] / 25.4, 1)}


__all__ = ["DEFAULT_PROFILE", "normalize_profile", "profile_key", "layout", "render_zpl", "payload_sha256",
           "expected_responses", "sample_snapshot", "dot_budget", "label_dims"]
