"""Pengurai balasan ZPL + ledger (pemulihan crash, idempotensi id hasil)."""
import os

from kn_printer_connector import ledger as L
from kn_printer_connector import zpl_status as zs
from kn_printer_connector.printer import classify

HS_IDLE = "\x02030,0,0,0176,000,0,0,0,000,0,0,0\x03\r\n\x02000,0,0,0,0,2,6,0,00000000,1,000\x03\r\n\x021234,0\x03\r\n"
HS_PAPER = "\x02030,1,1,0176,001,0,0,0,000,0,0,0\x03\r\n\x02000,0,0,0,0,2,6,0,00000000,1,000\x03\r\n\x021234,0\x03\r\n"
HS_BUSY = "\x02030,0,0,0176,002,0,0,0,000,0,0,0\x03\r\n\x02000,0,0,0,0,2,6,0,00000001,1,000\x03\r\n\x021234,0\x03\r\n"
HQES = "\x02\r\n  PRINTER STATUS\r\n    ERRORS:         1 00000000 00000005\r\n    WARNINGS:       0 00000000 00000000\r\n\x03"


def test_parse_hs_states():
    idle = zs.parse_hs(HS_IDLE)
    assert idle and idle.idle and not idle.blocking_reason
    paper = zs.parse_hs(HS_PAPER)
    assert paper.paper_out and paper.paused and paper.formats_in_buffer == 1 and paper.blocking_reason == "paper_out"
    busy = zs.parse_hs(HS_BUSY)
    assert not busy.idle and busy.labels_remaining == 1 and busy.formats_in_buffer == 2
    assert classify(idle, None) == "ready" and classify(busy, None) == "printing" and classify(paper, None) == "paper_out"
    assert zs.parse_hs("sampah") is None and classify(None, None) == "unknown"


def test_parse_hqes_rv_hv():
    q = zs.parse_hqes(HQES)
    assert q["error"] and set(q["errors"]) == {"media_out", "head_open"}
    assert zs.parse_rv("_+,1__-,3_") == [{"ok": True, "tries": 1}, {"ok": False, "tries": 3}]
    assert zs.parse_hv("EPC[e2001234]\r\nEPC[]\r\n") == ["E2001234", ""]


def test_ledger_crash_recovery_marks_unknown_never_resend(tmp_path):
    led = L.Ledger(os.path.join(tmp_path, "l.sqlite3"))
    job = {"id": "rpj_1", "kind": "rfid_tag", "revision": 1, "lease": {"attempt_id": "patt_1", "expires_at": "x"},
           "items": [{"item_id": f"i{n}", "epc": f"E2{n:022d}", "zpl": "^XA^XZ", "printable": True} for n in range(4)]}
    led.upsert_job(job)
    led.upsert_job(job)  # idempoten
    assert len(led.items("rpj_1", "patt_1")) == 4
    led.transition("rpj_1", "i0", "patt_1", L.STARTED)
    led.transition("rpj_1", "i1", "patt_1", L.SENDING)
    led.transition("rpj_1", "i2", "patt_1", L.SENT)
    rid = led.record_outcome("rpj_1", "i3", "patt_1", "confirmed", "confirmed", {"source": "x"})
    rec = led.recover_after_crash()
    assert {r["item_id"] for r in rec} == {"i1", "i2"}
    items = {i["item_id"]: i for i in led.items("rpj_1", "patt_1")}
    assert items["i0"]["state"] == L.STARTED            # belum menyentuh printer → aman dilanjutkan
    assert items["i1"]["state"] == L.OUTCOME and items["i1"]["print_status"] == "unknown"
    assert items["i2"]["state"] == L.OUTCOME and items["i2"]["encode_status"] == "unknown"
    assert items["i3"]["result_event_id"] == rid
    assert len(led.pending_results()) == 3
    # transisi berprasyarat menolak status yang tidak cocok
    assert not led.transition("rpj_1", "i1", "patt_1", L.SENDING, from_states=[L.STARTED])
    iid = led.instance_id()
    assert iid == led.instance_id()
    led.close()
