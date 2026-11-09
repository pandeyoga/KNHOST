#!/usr/bin/env python3
"""PREP-H — pekerja transaksi gate RFID V2 TERPISAH dari proses API (opsional; rekomendasi produksi).

Proses API dijalankan dengan `KN_GATE_TXN_INPROCESS=0` (close hanya mengantre: `gate_txn_state = pending`), lalu
pekerja ini menyapu antrean di proses sendiri: lintasan pending / error yang jatuh tempo / processing basi →
transaksi gudang (tiba PA, terima transfer, bukti keluar per trip) + antrean periksa. Aman dijalankan lebih dari satu
(klaim CAS + sewa yang diperpanjang); per perangkat tetap berurutan.

    cd /app/backend && python /app/scripts/gate_txn_worker.py [--interval 0.5] [--once]

Butuh lingkungan backend yang sama (MONGO_URL, DB_NAME, .env). Berhenti dengan Ctrl+C / SIGTERM.
"""
import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


async def main(interval: float, once: bool) -> None:
    from services import gate_txn_service as gt
    log = logging.getLogger('gate_txn_worker')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:   # Windows
            pass
    log.info('pekerja transaksi gate mulai (pemilik %s, interval %.1f dtk)', gt.OWNER, interval)
    while not stop.is_set():
        try:
            res = await gt.sweep()
            if res['processed']:
                log.info('diproses %s lintasan dari %s reader', res['processed'], res['devices'])
        except Exception as exc:  # noqa: BLE001 — pekerja tidak boleh mati; sapuan berikut mengulang
            log.warning('sapuan gagal: %s', exc)
        if once:
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--interval', type=float, default=0.5, help='jeda antar sapuan (detik)')
    ap.add_argument('--once', action='store_true', help='satu sapuan lalu keluar')
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    asyncio.run(main(a.interval, a.once))
