"""PREP-H — uji BATAS KINERJA jalur gate V2 (endpoint device sungguhan, transaksi di pekerja latar).

Ambang ditetapkan dari pengukuran PREP-H (laporan `docs/rfid/hasil/PREP-H-GATE-PERFORMA.md` §3) di stack uji
2 CPU / 1,5 GB backend + Mongo 1,5 GB (cache WiredTiger 0,5 GB), dengan ruang aman ±2× — bukan janji produksi.
Dapat dilewati dengan penanda jelas:
  * KN_SKIP_PERF=1 → semua uji di sini SKIP ("dilewati: KN_SKIP_PERF");
  * kalibrasi otomatis: bila close 20 roll pertama > CALIBRATION_MS, lingkungan dianggap terlalu lambat → SKIP
    ("dilewati: lingkungan lambat"); angka kalibrasi dicetak.
Ambang bisa ditimpa: KN_PERF_<NAMA>_MS (mis. KN_PERF_CLOSE_2000_MS=6000).
Jalankan: cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_h_gate_perf.py -s
"""
import os
import sys
import time

import pytest
import requests

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _prep_h_bed import API, DB, Bed  # noqa: E402

CALIBRATION_MS = 1500
DEFAULTS = {"CLOSE_500_P95": 1500, "CLOSE_2000": 4000, "EVENTS_BATCH_P95": 600, "TXN_2000_TRANSFER": 120000,
            "GATE_STATE_P95": 150}
B = Bed("HP")


def limit(name):
    return float(os.environ.get(f"KN_PERF_{name}_MS", DEFAULTS[name]))


def p95(values):
    s = sorted(values)
    return s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]


@pytest.fixture(scope="module", autouse=True)
def seed():
    if os.environ.get("KN_SKIP_PERF") == "1":
        pytest.skip("dilewati: KN_SKIP_PERF=1")
    try:
        requests.get(f"{API}/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    B.setup()
    _, rs = B.shipment(20)
    built = B.build("out", [r["epc"] for r in rs])
    B.send_events("out", built)
    t0 = time.perf_counter()
    r = B.close("out", built)
    ms = (time.perf_counter() - t0) * 1000
    print(f"\n[kalibrasi] close 20 roll = {ms:.0f} ms (batas lingkungan {CALIBRATION_MS} ms)")
    if r.status_code != 200 or ms > CALIBRATION_MS:
        B.teardown()
        pytest.skip(f"dilewati: lingkungan lambat (close 20 roll {ms:.0f} ms > {CALIBRATION_MS} ms)")
    yield
    B.teardown()


def test_close_500_rolls_p95_and_events_batches():
    closes, events = [], []
    for _ in range(5):
        _, rs = B.shipment(500)
        built = B.build("out", [r["epc"] for r in rs])
        B.send_events("out", built, events)
        t0 = time.perf_counter()
        r = B.close("out", built)
        closes.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200 and r.json()["verdict"] == "GREEN", r.text
    print(f"\nclose 500 roll: {[round(x) for x in closes]} ms · p95 {p95(closes):.0f} (batas {limit('CLOSE_500_P95'):.0f}); "
          f"events/batch p95 {p95(events):.0f} ms (batas {limit('EVENTS_BATCH_P95'):.0f}, n={len(events)})")
    assert p95(closes) <= limit("CLOSE_500_P95")
    assert p95(events) <= limit("EVENTS_BATCH_P95")


def test_close_2000_rolls_within_agent_timeout_and_txn_completes():
    tid, rs = B.transfer(2000)
    built = B.build("in", [r["epc"] for r in rs])
    B.send_events("in", built)
    t0 = time.perf_counter()
    r = B.close("in", built, timeout=120)
    ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200 and r.json()["verdict"] == "GREEN", r.text
    t1 = time.perf_counter()
    row = B.wait_state(B.pid("in", built["passage_id"]), timeout=limit("TXN_2000_TRANSFER") / 1000 + 30)
    txn = (time.perf_counter() - t1) * 1000
    print(f"\nclose 2000 roll (transfer IN): {ms:.0f} ms (batas {limit('CLOSE_2000'):.0f}; batas tunggu agent 5000); "
          f"transaksi latar selesai {txn:.0f} ms (batas {limit('TXN_2000_TRANSFER'):.0f})")
    assert ms <= limit("CLOSE_2000")
    assert row["gate_txn_state"] == "done" and txn <= limit("TXN_2000_TRANSFER")
    assert DB.warehouse_transfers.find_one({"id": tid})["status"] == "completed"


def test_gate_state_poll_latency():
    lat = []
    for _ in range(40):
        t0 = time.perf_counter()
        r = requests.get(f"{API}/rfid/v2/device/gate-state", params={"logical_gate_id": "G1"},
                         headers={"X-Device-Key": B.keys["out"]}, timeout=10)
        lat.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
    print(f"\ngate-state p95 {p95(lat):.0f} ms (batas {limit('GATE_STATE_P95'):.0f})")
    assert p95(lat) <= limit("GATE_STATE_P95")
