"""F-11-layar lanjutan — keputusan owner 2026-10-21 (putaran 3).

1. Antrean "Retur menunggu terima / QC" di Meja Operator Gudang (`/desks/me`) dan Meja Admin Gudang
   (`/warehouse-admin/desk`): retur approved/inspecting — himpunan sama dengan daftar retur Gudang/QC —
   dengan langkah berikutnya per retur (scan terima → menunggu QC → sedang QC), tanpa nilai uang.
2. Gudang/QC boleh MENGUNDUH foto/video bukti keluhan selama retur di tahap kerja mereka; lampiran lain
   (PDF) tetap untuk pemegang `sales_return.view`; pagar badan usaha sama dengan detail retur.
Proses bisnis lewat API (Sales ajukan → Manajer setujui → Gudang scan → QC). Memakai fixture & helper tes
F-11-layar (akun peran bersandi `scripts.demo_api.DEMO_PASSWORD`).
Jalankan: cd /app/backend && python -m pytest tests/test_f11_layar_keputusan_lanjutan.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f11_layar_return_screen_access as base  # noqa: E402
from test_f11_layar_return_screen_access import hs, pool  # noqa: E402,F401 — fixture modul dipakai ulang

BASE, JKT = base.BASE, base.JKT
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture(scope="module")
def whadm():
    return base._login("wh.admin@kainnusantara.id", "demo12345")   # Admin Gudang (bootstrap)


def _queue(h, path="/desks/me"):
    r = requests.get(f"{BASE}{path}", headers=h)
    assert r.status_code == 200, r.text
    return next((q for q in r.json()["queues"] if q["id"] == "retur_terima_qc"), None)


def _row(q, rid):
    return next((x for x in q["rows"] if x["ref_id"] == rid), None)


def _upload(h, rid, name, data, ctype):
    r = requests.post(f"{BASE}/sales-returns/{rid}/attachments", headers=h, files={"file": (name, data, ctype)})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ─── 1. Antrean meja Gudang ────────────────────────────────────────────────────────────────────
def test_antrean_retur_terima_qc_di_meja_gudang_mengikuti_langkah(hs, pool, whadm):  # noqa: F811 — fixture modul F-11-layar
    roll = pool[0]
    waiting = base._create(hs, pool[1], qty=2, approve=False)          # belum disetujui → tidak masuk antrean
    rid = base._create(hs, roll, qty=3)
    q = _queue(hs["wh"])
    assert q and q["value_kind"] == "count" and q["total_value"] == 0
    row = _row(q, rid)
    assert row and row["subtitle"].startswith("Menunggu scan terima · 0/1") and row["action"] == "Terima", row
    assert row["value"] == 0 and "Rp" not in row["subtitle"] and _row(q, waiting) is None
    adm = _queue(whadm, "/warehouse-admin/desk")                   # Meja Admin Gudang memuat antrean sama
    assert adm and _row(adm, rid)
    assert base._scan(hs["wh"], rid, "received", [roll["roll_no"]], JKT).status_code == 200
    assert _row(_queue(hs["wh"]), rid)["subtitle"] == "Barang sudah di gudang — menunggu QC"
    assert requests.post(f"{BASE}/sales-returns/{rid}/inspect/start", headers=hs["qc"], json={}).status_code == 200
    row = _row(_queue(hs["wh"]), rid)
    assert row["subtitle"] == "Sedang diperiksa QC" and row["badge"] == "inspecting"
    r = requests.post(f"{BASE}/sales-returns/{rid}/inspect/complete", headers=hs["qc"],
                      json={"inspections": [{"index": 0, "grade": "A", "condition": "ok"}]})
    assert r.status_code == 200, r.text
    assert _row(_queue(hs["wh"]), rid) is None                          # inspected → keluar dari antrean


# ─── 2. Unduh foto bukti untuk Gudang/QC ───────────────────────────────────────────────────────
def test_gudang_qc_unduh_foto_bukti_tetapi_bukan_pdf(hs, pool):  # noqa: F811 — fixture modul F-11-layar
    rid = base._create(hs, pool[2], qty=2, approve=False)
    img = _upload(hs["sales"], rid, "bukti-cacat.png", PNG, "image/png")
    pdf = _upload(hs["sales"], rid, "surat-pelanggan.pdf", PDF, "application/pdf")
    url = lambda a: f"{BASE}/sales-returns/{rid}/attachments/{a}/download"  # noqa: E731
    for k in ("wh", "qc"):                                                # sebelum disetujui: di luar tahap kerja
        assert requests.get(url(img), headers=hs[k]).status_code == 403
    assert requests.post(f"{BASE}/sales-returns/{rid}/approve", headers=hs["mgr"], json={"notes": ""}).status_code == 200
    for k in ("wh", "qc"):
        r = requests.get(url(img), headers=hs[k])
        assert r.status_code == 200 and r.content == PNG, (k, r.status_code)
        assert requests.get(url(pdf), headers=hs[k]).status_code == 403   # lampiran non-foto tetap tertutup
    for k in ("sales", "fin"):                                            # pemegang sales_return.view tidak berubah
        assert requests.get(url(pdf), headers=hs[k]).status_code == 200
    assert requests.get(url(img), headers=hs["des"]).status_code == 403   # Desainer tetap 403
    other = {**hs["sales"], "X-Entity-Id": "ent_kanda"}                    # pagar badan usaha seperti detail
    r = requests.get(url(img), headers=other)
    assert r.status_code in (403, 404), r.status_code
