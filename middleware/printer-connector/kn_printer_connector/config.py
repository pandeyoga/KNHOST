"""Konfigurasi connector (JSON). Device key TIDAK ditulis di berkas konfigurasi bila bisa: pakai variabel lingkungan
(`device_key_env`) atau berkas kunci terlindung ACL (`device_key_file`). `device_key` langsung hanya untuk uji."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

_NAME = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


@dataclass
class PrinterConfig:
    name: str
    host: str
    port: int = 9100
    device_key: str = field(default="", repr=False)
    connect_timeout_s: float = 3.0
    io_timeout_s: float = 5.0

    def masked_key(self) -> str:
        return ("…" + self.device_key[-4:]) if self.device_key else "(kosong)"


@dataclass
class ConnectorConfig:
    erp_url: str
    data_dir: str
    printers: List[PrinterConfig]
    verify_tls: bool = True
    http_timeout_s: float = 15.0
    log_level: str = "INFO"
    poll_interval_s: Optional[float] = None    # None = ikut kebijakan ERP
    telemetry_interval_s: Optional[float] = None


class ConfigError(ValueError):
    pass


def _read_key(p: dict, base_dir: str) -> str:
    if p.get("device_key_env"):
        v = os.environ.get(p["device_key_env"], "")
        if not v:
            raise ConfigError(f"Printer {p.get('name')}: variabel lingkungan {p['device_key_env']} kosong")
        return v.strip()
    if p.get("device_key_file"):
        path = p["device_key_file"]
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError as e:
            raise ConfigError(f"Printer {p.get('name')}: berkas kunci tidak terbaca ({e})")
    if p.get("device_key"):
        return str(p["device_key"]).strip()
    raise ConfigError(f"Printer {p.get('name')}: device_key_env / device_key_file wajib diisi")


def load(path: str) -> ConnectorConfig:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"Konfigurasi tidak terbaca: {e}")
    return from_dict(raw, os.path.dirname(os.path.abspath(path)))


def from_dict(raw: dict, base_dir: str = ".") -> ConnectorConfig:
    url = str(raw.get("erp_url") or "").rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ConfigError("erp_url wajib (mis. https://erp.contoh.id/api)")
    if not url.endswith("/api"):
        url = url + "/api"
    printers = []
    names = set()
    for p in raw.get("printers") or []:
        name = str(p.get("name") or "")
        if not _NAME.match(name):
            raise ConfigError(f"Nama printer tidak valid: {name!r} (huruf/angka . _ -, maks 40)")
        if name in names:
            raise ConfigError(f"Nama printer ganda: {name}")
        names.add(name)
        if not p.get("host"):
            raise ConfigError(f"Printer {name}: host (IP printer) wajib")
        port = int(p.get("port") or 9100)
        if not 1 <= port <= 65535:
            raise ConfigError(f"Printer {name}: port tidak valid")
        printers.append(PrinterConfig(name=name, host=str(p["host"]), port=port, device_key=_read_key(p, base_dir),
                                      connect_timeout_s=float(p.get("connect_timeout_s") or 3.0),
                                      io_timeout_s=float(p.get("io_timeout_s") or 5.0)))
    if not printers:
        raise ConfigError("Minimal satu printer di 'printers'")
    data_dir = raw.get("data_dir") or os.path.join(base_dir, "data")
    return ConnectorConfig(erp_url=url, data_dir=str(data_dir), printers=printers,
                           verify_tls=bool(raw.get("verify_tls", True)),
                           http_timeout_s=float(raw.get("http_timeout_s") or 15.0),
                           log_level=str(raw.get("log_level") or "INFO").upper(),
                           poll_interval_s=raw.get("poll_interval_s"),
                           telemetry_interval_s=raw.get("telemetry_interval_s"))
