"""Audit UI tahap 2 (UAT 24 Okt) — G5a: perubahan backend R&D / desain (uji tingkat layanan, tanpa HTTP).

* G5-46 — teks riwayat sample memakai "Ronde", label hasil & tanggal Indonesia (`_tgl_id`, `_jenis_label`).
* G5-48 — `labdip_history` mengembalikan permintaan TANPA putaran jenis itu (`waiting`) + `summary.samples_shown`,
  sehingga KPI "Permintaan" = baris yang tampil; `summary.samples` lama tetap (dipakai uji P05).
* G5-37 — `report_by_designer` memisahkan "Belum ditugaskan" ke `unassigned` (bukan baris desainer); total tetap
  menghitung semua permintaan.

Jalankan: cd /app/backend && python -m pytest tests/test_audit_ui2_g5a.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import design_request_service as dsr  # noqa: E402
from services import rnd_sample_service as smp  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
COLOR = f"clr_TEST_G5A_{TAG}"
ENT = f"ent_TEST_G5A_{TAG}"


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.md_samples.insert_many([
        # labdip draf — belum ada putaran → harus muncul di `waiting`
        {"id": f"smp_TEST_G5A_{TAG}_a", "number": f"T-{TAG}-A", "title": "Labdip draf", "status": "draft",
         "sample_types": ["labdip"], "color_target": {"color_id": COLOR}, "rounds": [], "created_at": "2026-10-20T00:00:00Z"},
        # labdip dengan satu putaran → baris `items`
        {"id": f"smp_TEST_G5A_{TAG}_b", "number": f"T-{TAG}-B", "title": "Labdip jalan", "status": "in_progress",
         "sample_types": ["labdip"], "color_target": {"color_id": COLOR}, "created_at": "2026-10-21T00:00:00Z",
         "rounds": [{"id": f"rnd_TEST_G5A_{TAG}", "round_no": 1, "type_code": "labdip", "supplier_id": "sup_x",
                     "supplier_name": "CV Uji", "due_date": "2026-10-30", "result": "acc", "score": 92}]},
        # handfeel saja (warna sama) — bukan labdip → tidak masuk `waiting` labdip
        {"id": f"smp_TEST_G5A_{TAG}_c", "number": f"T-{TAG}-C", "title": "Handfeel", "status": "draft",
         "sample_types": ["handfeel"], "color_target": {"color_id": COLOR}, "rounds": [], "created_at": "2026-10-22T00:00:00Z"},
    ])
    DB.design_requests.insert_many([
        {"id": f"dsr_TEST_G5A_{TAG}_1", "entity_id": ENT, "status": "submitted", "assigned_to": "", "assigned_name": ""},
        {"id": f"dsr_TEST_G5A_{TAG}_2", "entity_id": ENT, "status": "assigned", "assigned_to": f"usr_{TAG}",
         "assigned_name": "Desainer Uji"},
        {"id": f"dsr_TEST_G5A_{TAG}_3", "entity_id": ENT, "status": "approved", "assigned_to": f"usr_{TAG}",
         "assigned_name": "Desainer Uji"},
    ])
    yield
    DB.md_samples.delete_many({"id": {"$regex": f"^smp_TEST_G5A_{TAG}"}})
    DB.design_requests.delete_many({"entity_id": ENT})


def test_g5_46_label_helpers():
    assert smp._tgl_id("2026-10-30") == "30 Okt 2026"
    assert smp._tgl_id("2026-01-05T03:00:00Z") == "5 Jan 2026"
    assert smp._tgl_id("") == "—"
    assert smp._jenis_label("labdip") == "Labdip"
    assert smp._jenis_label("handfeel") == "Handfeel"
    assert smp._jenis_label("kode_lain") == "kode_lain"
    assert smp._RESULT_LABEL["acc"] == "ACC" and smp._RESULT_LABEL["tolak"] == "ditolak"


def test_g5_48_labdip_history_lists_waiting_requests():
    res = run(smp.labdip_history({}, color_id=COLOR))
    waiting = {w["sample_id"] for w in res["waiting"]}
    assert waiting == {f"smp_TEST_G5A_{TAG}_a"}, res["waiting"]
    assert [r["sample_id"] for r in res["items"]] == [f"smp_TEST_G5A_{TAG}_b"]
    s = res["summary"]
    assert s["samples"] == 3            # kompatibel: semua dokumen berwarna ini
    assert s["samples_shown"] == 2      # yang benar-benar tampil & bisa dibuka
    assert s["waiting"] == 1 and s["rounds"] == 1 and s["acc"] == 1


def test_g5_48_all_types_waiting_includes_every_roundless_request():
    res = run(smp.labdip_history({}, color_id=COLOR, type_code=""))
    assert {w["sample_id"] for w in res["waiting"]} == {f"smp_TEST_G5A_{TAG}_a", f"smp_TEST_G5A_{TAG}_c"}
    assert res["summary"]["samples_shown"] == 3


def test_g5_37_report_separates_unassigned():
    rep = run(dsr.report_by_designer({"entity_id": ENT}))
    assert [r["designer_id"] for r in rep["items"]] == [f"usr_{TAG}"]
    assert all(r["designer"] != "Belum ditugaskan" for r in rep["items"])
    assert rep["unassigned"] == {"requests": 1, "overdue": 0}
    assert rep["totals"]["requests"] == 3 and rep["totals"]["approved"] == 1
    mine = run(dsr.report_mine({"entity_id": ENT}, user_id=f"usr_{TAG}"))
    assert mine["rank"] == 1 and mine["total_designers"] == 1
