"""CLI: `python -m kn_printer_connector <perintah> --config config.json`

  run        jalankan connector (layanan)
  check      periksa konfigurasi, jangkauan ERP (config) dan status tiap printer (~HS) — tanpa mencetak
  ledger     tampilkan ringkasan ledger lokal + 30 kejadian terakhir per printer
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import VERSION
from . import ledger as L
from .config import ConfigError, load
from .erp import ErpClient, ErpError, ErpUnavailable
from .printer import ZplTcpPrinter


def _check(cfg) -> int:
    ok = True
    for p in cfg.printers:
        print(f"== {p.name} ({p.host}:{p.port}) key {p.masked_key()}")
        led = L.Ledger(os.path.join(cfg.data_dir, p.name, "ledger.sqlite3"))
        try:
            erp = ErpClient(cfg.erp_url, p.device_key, led.instance_id(), verify_tls=cfg.verify_tls,
                            timeout_s=cfg.http_timeout_s)
            c = erp.config()
            prof = c.get("printer_profile") or {}
            print(f"   ERP ok — device {c.get('device_code')} gudang {c.get('warehouse_id')} profil "
                  f"{prof.get('dpi')} dpi {prof.get('label_width_mm')}×{prof.get('label_height_mm')} mm "
                  f"laporan encode {prof.get('encode_report')}")
        except (ErpUnavailable, ErpError) as e:
            ok = False
            print(f"   ERP GAGAL: {e}")
        finally:
            led.close()
        pr = ZplTcpPrinter(p.host, p.port, p.connect_timeout_s, p.io_timeout_s)
        st = pr.status()
        print(f"   printer: {st.state} {st.detail}")
        ident = pr.identify() if st.reachable else None
        print(f"   ~HI: {ident or '(tidak ada jawaban)'}")
        ok = ok and st.reachable
    return 0 if ok else 1


def _ledger(cfg) -> int:
    for p in cfg.printers:
        path = os.path.join(cfg.data_dir, p.name, "ledger.sqlite3")
        if not os.path.exists(path):
            print(f"== {p.name}: ledger belum ada")
            continue
        led = L.Ledger(path)
        print(f"== {p.name}: instance {led.instance_id()} — {json.dumps(led.counts())}")
        for e in reversed(led.events_tail(30)):
            print(f"   {e['at']} {e['level']:5} {e['job_id'] or '-':>24} {e['message']}")
        led.close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kn_printer_connector", description=f"KN Printer Connector {VERSION}")
    ap.add_argument("command", choices=["run", "check", "ledger", "version"])
    ap.add_argument("--config", default=os.environ.get("KN_CONNECTOR_CONFIG", "config.json"))
    a = ap.parse_args(argv)
    if a.command == "version":
        print(VERSION)
        return 0
    try:
        cfg = load(a.config)
    except ConfigError as e:
        print(f"Konfigurasi salah: {e}", file=sys.stderr)
        return 2
    if a.command == "check":
        return _check(cfg)
    if a.command == "ledger":
        return _ledger(cfg)
    from .service import run
    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
