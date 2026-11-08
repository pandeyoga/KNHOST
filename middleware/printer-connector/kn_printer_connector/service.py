"""Supervisor: muat konfigurasi, satu worker terisolasi per printer, log berotasi, berhenti rapi (Ctrl+C / NSSM)."""
from __future__ import annotations

import logging
import logging.handlers
import os
import signal
import threading
import time
from typing import List

from . import VERSION
from .config import ConnectorConfig
from .worker import PrinterWorker


class _NoSecrets(logging.Filter):
    """Pengaman: baris log yang memuat pola device key (dk_…) disamarkan."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "dk_" in msg:
            import re
            record.msg = re.sub(r"dk_[0-9a-fA-F]{6,}", "dk_***", msg)
            record.args = ()
        return True


def setup_logging(cfg: ConnectorConfig) -> None:
    logdir = os.path.join(cfg.data_dir, "logs")
    os.makedirs(logdir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.log_level, logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.handlers.RotatingFileHandler(os.path.join(logdir, "connector.log"), maxBytes=5_000_000,
                                              backupCount=10, encoding="utf-8")
    sh = logging.StreamHandler()
    for h in (fh, sh):
        h.setFormatter(fmt)
        h.addFilter(_NoSecrets())
        root.addHandler(h)


def run(cfg: ConnectorConfig) -> int:
    setup_logging(cfg)
    log = logging.getLogger("kn.connector")
    log.info("KN Printer Connector %s mulai — ERP %s, %d printer", VERSION, cfg.erp_url, len(cfg.printers))
    workers: List[PrinterWorker] = []
    for p in cfg.printers:
        try:
            w = PrinterWorker(p, cfg)
        except RuntimeError as e:
            log.error("printer %s tidak dijalankan: %s", p.name, e)
            continue
        log.info("printer %s → %s:%d (key %s, instance %s)", p.name, p.host, p.port, p.masked_key(), w.instance_id)
        workers.append(w)
    if not workers:
        log.error("tidak ada worker berjalan")
        return 2
    stop = threading.Event()

    def _stop(*_a):
        log.info("berhenti — menunggu label yang sedang dicetak selesai dicatat…")
        stop.set()
        for w in workers:
            w.stop()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)
    if hasattr(signal, "SIGBREAK"):  # Windows: NSSM mengirim Ctrl+Break/Ctrl+C
        signal.signal(signal.SIGBREAK, _stop)
    for w in workers:
        w.start()
    try:
        while not stop.is_set() and any(w.is_alive() for w in workers):
            time.sleep(1.0)
    finally:
        for w in workers:
            w.stop()
        for w in workers:
            w.join(timeout=90)
    log.info("selesai")
    return 0
