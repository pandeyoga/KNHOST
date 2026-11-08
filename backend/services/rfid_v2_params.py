"""PREP-D1 — parameter lintasan per gate di profil commissioning BERVERSI (bukan konstanta kode).

Semua nilai bawaan di bawah = **TITIK AWAL KALIBRASI** dari tabel audit §8.3
(`docs/rfid/AUDIT_MIDDLEWARE_RFID_2026-11-08.md`), bukan aturan. Keputusan K-RFID-03 (uji meja SDK),
K-RFID-05 (setelan reader & kabel) dan K-RFID-08 (target uji) masih TERBUKA → angka wajib diukur di lokasi.
Mengubah parameter = menerbitkan `config_version` baru (profil immutable per versi; lintasan lama tetap dinilai
dengan versi yang dipakainya).

Parameter yang dipakai SERVER: ambang RSSI per antena, `auto_match`, `manual_binding_ttl_s`, `rf_fallback_review`.
Sisanya (pre-buffer, tail, debounce, batas waktu, cadangan RF, bucket) didistribusikan ke agent 0.5 (paket E).
"""
import copy
from typing import Any, Dict, Optional

CALIBRATION_NOTE = "titik awal kalibrasi — belum diuji lokasi (K-RFID-03/05/08 terbuka)"

DEFAULTS: Dict[str, Any] = {
    "calibration_status": "initial",
    "pre_buffer_ms": 3000,           # label depan 2,9–4,6 m ÷ 1,39 m/s
    "tail_ms": 1500,                 # ekor setelah sinar B pulih
    "min_block_ms": 50,              # debounce sinar
    "entry_timeout_ms": 10000,       # A terpotong tanpa B → CANCELLED
    "max_passage_ms": 30000,         # lintasan terlalu lama → TIMEOUT (REVIEW)
    "stable_interval_ms": 3000,      # cadangan RF: tidak ada EPC kuat baru → tutup
    "bucket_ms": 250,                # lebar bucket TagSummary
    "rf_fallback_group_size": 3,     # cadangan RF: rombongan EPC kuat non-latar pembuka lintasan
    "rf_fallback_window_ms": 1500,   # cadangan RF: jendela rombongan
    "rssi_strong_dbm": {},           # ambang per antena {antenna_id: dBm}
    "rssi_default_strong_dbm": -65.0,  # roll di gate ±40–60 cm vs rak ≥ 3 m ≈ 15 dB lebih lemah
    "background_retention_s": 86400,   # masa simpan daftar latar
    "auto_match": True,              # AUD-MW-15 — dokumen selalu dibuat sebelum barang lewat
    "manual_binding_ttl_s": 14400,   # binding manual kedaluwarsa (lupa ganti → tidak menahan muatan berikutnya)
    "rf_fallback_review": True,      # lintasan cadangan RF/sensor rusak = REVIEW sampai terkalibrasi
}

_BOUNDS = {
    "pre_buffer_ms": (0, 10000), "tail_ms": (0, 10000), "min_block_ms": (1, 1000),
    "entry_timeout_ms": (1000, 60000), "max_passage_ms": (5000, 120000), "stable_interval_ms": (500, 10000),
    "bucket_ms": (50, 2000), "rf_fallback_group_size": (1, 100), "rf_fallback_window_ms": (100, 10000),
    "background_retention_s": (60, 604800), "manual_binding_ttl_s": (60, 604800),
}


def effective(gate: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Parameter efektif gate = bawaan ⊕ `passage_parameters` profil. Tidak pernah mengubah profil asli."""
    out = copy.deepcopy(DEFAULTS)
    own = (gate or {}).get("passage_parameters") or {}
    for key, value in own.items():
        if key in DEFAULTS:
            out[key] = copy.deepcopy(value)
    out["is_default"] = {k: k not in own for k in DEFAULTS}
    out["note"] = CALIBRATION_NOTE if out.get("calibration_status") != "calibrated" else "terkalibrasi"
    return out


def strong_threshold(params: Dict[str, Any], antenna: Optional[str]) -> float:
    per = params.get("rssi_strong_dbm") or {}
    value = per.get(str(antenna)) if antenna is not None else None
    return float(value if value is not None else params.get("rssi_default_strong_dbm", DEFAULTS["rssi_default_strong_dbm"]))


def validate(parameters: Dict[str, Any]) -> Optional[str]:
    """Pesan galat (Bahasa Indonesia) atau None. Skema kontrak juga memeriksa saat profil diterbitkan."""
    if not isinstance(parameters, dict):
        return "Parameter gate wajib objek."
    for key, value in parameters.items():
        if key not in DEFAULTS:
            return f"Parameter '{key}' tidak dikenal."
        if key in _BOUNDS:
            lo, hi = _BOUNDS[key]
            if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
                return f"Parameter '{key}' wajib bilangan bulat {lo}–{hi}."
    for key in ("auto_match", "rf_fallback_review"):
        if key in parameters and not isinstance(parameters[key], bool):
            return f"Parameter '{key}' wajib ya/tidak."
    if parameters.get("calibration_status", "initial") not in ("initial", "calibrated"):
        return "Status kalibrasi hanya 'initial' atau 'calibrated'."
    per = parameters.get("rssi_strong_dbm", {})
    if not isinstance(per, dict) or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not -120 <= v <= 0
                                        for v in per.values()):
        return "Ambang RSSI per antena wajib angka −120 s.d. 0 dBm."
    dflt = parameters.get("rssi_default_strong_dbm", -65.0)
    if not isinstance(dflt, (int, float)) or isinstance(dflt, bool) or not -120 <= dflt <= 0:
        return "Ambang RSSI bawaan wajib −120 s.d. 0 dBm."
    return None


def derive_config(cfg: Dict[str, Any], gate_id: str, new_version: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Profil baru (versi baru) dari profil aktif dengan `passage_parameters` gate diganti."""
    out = copy.deepcopy(cfg)          # server_time & enabled ikut (wajib skema DeviceConfig; dibuang saat disimpan)
    out["enabled"] = True
    out["config_version"] = new_version
    for g in out.get("logical_gates") or []:
        if g.get("logical_gate_id") == gate_id:
            g["passage_parameters"] = copy.deepcopy(parameters)
    return out
