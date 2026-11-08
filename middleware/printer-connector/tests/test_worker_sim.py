"""Connector + simulator printer TCP + ERP tiruan — skenario RACC-21…30 yang bisa dibuktikan tanpa perangkat."""
import threading
import time

import pytest

from fake_erp import FakeErp, make_job
from kn_printer_connector import ledger as L
from kn_printer_connector.config import ConnectorConfig, PrinterConfig
from kn_printer_connector.erp import ErpUnavailable
from kn_printer_connector.worker import PrinterWorker
from zpl_printer_sim import SimPrinter


class Crash(Exception):
    pass


@pytest.fixture
def sim():
    s = SimPrinter(print_delay_s=0.05).start()
    yield s
    s.stop()


def _worker(tmp_path, sim, erp, hooks=None):
    pc = PrinterConfig(name="P1", host="127.0.0.1", port=sim.port, device_key="dk_test", connect_timeout_s=1,
                       io_timeout_s=1)
    cc = ConnectorConfig(erp_url="http://fake/api", data_dir=str(tmp_path), printers=[pc])
    return PrinterWorker(pc, cc, erp=erp, hooks=hooks)


def _drain(w, erp, job_id, max_steps=80, ok_states=("confirmed", "failed", "unknown")):
    for _ in range(max_steps):
        try:
            w.step()
        except ErpUnavailable:
            time.sleep(0.05)
        if all(s in ok_states for s in erp.statuses(job_id)) and not w.ledger.pending_results():
            return
    raise AssertionError(f"tidak selesai: {erp.statuses(job_id)}")


def test_happy_path_each_epc_written_once(tmp_path, sim):
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed"] * 3
    assert sim.printed_epcs() == [i["epc"] for i in job["items"]]       # urut, sekali per EPC
    assert sim.received == 3
    assert erp.telemetry_log and erp.telemetry_log[-1]["printer"]["state"] in ("ready", "printing")
    w.close()


def test_partial_batch_7_ok_2_failed_1_unknown(tmp_path, sim):
    """RACC-25 — 10 label: encode gagal #4,#7 (VOID), #10 macet (timeout → tidak pasti). Hanya yang terbukti diakui."""
    sim.set_fault(encode_fail={4, 7}, hang={10})
    job = make_job(10)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"], max_steps=200)
    st = erp.statuses(job["id"])
    assert st.count("confirmed") == 7 and st.count("failed") == 2 and st.count("unknown") == 1, st
    assert st[3] == st[6] == "failed" and st[9] == "unknown"
    assert sim.received == 10                                            # tidak ada label yang dikirim dua kali
    unknown = job["items"][9]["results"][-1]
    assert unknown["print_status"] == "unknown" and "batas waktu" in unknown["evidence"]["detail"]
    sim.release_hang()
    w.close()


def test_stuck_printer_blocks_next_label_until_idle(tmp_path, sim):
    """Label #2 macet → tidak pasti; label #3 TIDAK dikirim selama printer belum diam; sesudah lepas, #3 dicetak
    dan #2 (yang ternyata keluar) tetap 'tidak pasti' untuk diputuskan operator — tidak dikirim ulang."""
    sim.set_fault(hang={2})
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    for _ in range(30):
        w.step()
        if erp.statuses(job["id"])[1] == "unknown":
            break
    for _ in range(3):
        w.step()
    assert erp.statuses(job["id"]) == ["confirmed", "unknown", "pending"] and sim.received == 2
    sim.release_hang()
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "unknown", "confirmed"] and sim.received == 3
    assert len(sim.labels) == 3
    w.close()


def test_crash_after_send_reports_unknown_without_reprint(tmp_path, sim):
    """RACC-26 — crash sesudah payload ke printer, sebelum hasil. Restart: item dilaporkan tidak pasti, TIDAK dikirim ulang."""
    job = make_job(4)
    erp = FakeErp([job])
    state = {"n": 0}

    def after_sent(_job, iid):
        state["n"] += 1
        if state["n"] == 2:
            raise Crash("listrik padam")

    w = _worker(tmp_path, sim, erp, hooks={"after_sent": after_sent})
    with pytest.raises(Crash):
        for _ in range(20):
            w.step()
    w.close()
    time.sleep(0.3)
    assert sim.received == 2
    w2 = _worker(tmp_path, sim, erp)
    rec = w2.ledger.recover_after_crash()
    assert [r["item_id"] for r in rec] == [job["items"][1]["item_id"]]
    _drain(w2, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "unknown", "confirmed", "confirmed"]
    assert sim.received == 4                                             # item #2 tidak dikirim ulang
    ev = job["items"][1]["results"][-1]["evidence"]
    assert ev["source"] == "connector_recovery"
    w2.close()


def test_lost_result_ack_is_retried_with_same_event_id(tmp_path, sim):
    """RACC-26 — label selesai tetapi respons ERP hilang → kirim ulang hasil (id sama), tanpa cetak ulang."""
    job = make_job(2)
    erp = FakeErp([job])
    erp.drop_results_response = 2
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "confirmed"]
    assert sim.received == 2
    assert all(len(i["results"]) == 1 for i in job["items"])           # duplikat tidak menambah hasil
    assert erp.calls.count("results") >= 3
    w.close()


def test_offline_erp_holds_queue_then_resumes(tmp_path, sim):
    """ERP putus: tidak ada label baru dimulai (start barrier); hasil tertahan lokal; lanjut saat tersambung."""
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    w.step()                       # config + klaim
    w.step()                       # label 1 dicetak & dilaporkan
    printed_before = sim.received
    erp.offline = True
    for _ in range(4):
        try:
            w.step()
        except ErpUnavailable:
            pass
    assert sim.received <= printed_before + 1                         # label yang sudah 'started' boleh selesai
    held = sim.received
    for _ in range(3):
        try:
            w.step()
        except ErpUnavailable:
            pass
    assert sim.received == held                                        # tidak ada start baru saat offline
    erp.offline = False
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed"] * 3 and sim.received == 3
    w.close()


def test_paper_out_waits_then_continues(tmp_path, sim):
    sim.set_fault(paper_out_after=1)
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    done = threading.Event()

    def operator():  # operator memasang kertas ±1 dtk sesudah printer melapor kertas habis
        while not done.is_set() and not sim.paper_out:
            time.sleep(0.05)
        time.sleep(1.0)
        sim.reload_paper()

    t = threading.Thread(target=operator, daemon=True)
    t.start()
    _drain(w, erp, job["id"], max_steps=120)
    done.set()
    assert erp.statuses(job["id"]) == ["confirmed"] * 3
    assert any(b["printer"]["state"] == "paper_out" for b in erp.telemetry_log), "kertas habis tidak dilaporkan"
    assert sim.received == 3
    w.close()


def test_connection_drop_mid_job_is_unknown_not_resent(tmp_path, sim):
    """Putus di tengah job: label #2 → tidak pasti; label berikutnya lanjut; #2 tidak dikirim ulang otomatis."""
    sim.set_fault(drop_at=2)
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "unknown", "confirmed"]
    assert sim.received == 3 and len(sim.labels) == 2
    w.close()


def test_duplicate_printer_replies_and_readback_mismatch(tmp_path, sim):
    sim.set_fault(duplicate_results=True, readback_mismatch={2})
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "failed", "confirmed"]
    ev = job["items"][0]["results"][0]["evidence"]
    assert ev["duplicate_replies"] is True and ev["readback_epc"] == job["items"][0]["epc"]
    w.close()


def test_printer_silent_or_head_open_never_starts(tmp_path, sim):
    sim.set_fault(status_mute=True)
    job = make_job(2)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    for _ in range(4):
        w.step()
    assert erp.statuses(job["id"]) == ["pending", "pending"] and sim.received == 0
    sim.set_fault(status_mute=False, head_open=True)
    for _ in range(3):
        w.step()
    assert erp.statuses(job["id"]) == ["pending", "pending"] and "start" not in erp.calls
    sim.set_fault(head_open=False)
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "confirmed"]
    w.close()


def test_lost_ledger_redelivery_reports_started_item_unknown(tmp_path, sim):
    """Ledger lokal hilang: ERP mengirim ulang attempt yang sama; item 'started' → tidak pasti, sisanya dicetak."""
    job = make_job(3)
    erp = FakeErp([job])
    w = _worker(tmp_path / "a", sim, erp)
    w.step()   # klaim
    att = job["lease"]["attempt_id"]
    erp.start(job["id"], att, [job["items"][0]["item_id"]], 1)        # item 1 dimulai oleh "ledger lama"
    w.close()
    w2 = _worker(tmp_path / "b", sim, erp)                              # ledger baru, kosong
    _drain(w2, erp, job["id"])
    assert erp.statuses(job["id"]) == ["unknown", "confirmed", "confirmed"]
    assert sim.received == 2
    w2.close()


def test_single_instance_lock(tmp_path, sim):
    erp = FakeErp([])
    w = _worker(tmp_path, sim, erp)
    with pytest.raises(RuntimeError):
        _worker(tmp_path, sim, erp)
    w.close()


def test_text_label_without_rfid(tmp_path, sim):
    job = make_job(2, kind="text_reprint")
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"])
    assert erp.statuses(job["id"]) == ["confirmed", "confirmed"]
    assert sim.printed_epcs() == []                                     # tidak ada chip yang ditulis
    assert all(i["results"][0]["encode_status"] == "not_applicable" for i in job["items"])
    w.close()


def test_ledger_states_end_reported(tmp_path, sim):
    job = make_job(2)
    erp = FakeErp([job])
    w = _worker(tmp_path, sim, erp)
    _drain(w, erp, job["id"])
    att = job["items"][0]["attempt_id"]
    states = [i["state"] for i in w.ledger.items(job["id"], att)]
    assert states == [L.REPORTED, L.REPORTED]
    assert w.ledger.counts()["pending_results"] == 0
    w.close()
