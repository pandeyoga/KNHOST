"""PK-16 — laporan menyebut PT-nya; mode gabungan berlabel (docs/blueprint/unit/PK-16.md), sisi server U1–U7.

A = `ent_ksc`, B = `ent_kanda`. Angka dibaca sebagai SELISIH sebelum/sesudah fixture supaya data seed lain tidak ikut.
"""
from __future__ import annotations

import csv
import io

import pytest

from services import gl_service as gl

pytestmark = pytest.mark.anyio
A, B = "ent_ksc", "ent_kanda"
JT = 1_000_000


async def _j(eid, tanggal, baris, ket, src, source_type="manual"):
    return await gl._insert_entry(
        lines=[{"account_code": a, "account_name": a, "debit": d, "credit": k} for a, d, k in baris],
        description=ket, date=tanggal, source_type=source_type, source_id=src, entity_id=eid, created_by="uji")


def _h(h, ent):
    return {**h, "X-Entity-Id": ent}


async def _nama(db, eid, field="legal_name"):
    e = await db.business_entities.find_one({"id": eid}, {"_id": 0})
    return e.get(field) or e.get("name") or e.get("short_name")


async def _pendapatan_diakui(klien, h, dari, sampai):
    r = await klien.post("/api/ai/query", headers=h, json={
        "metrics": ["recognized_revenue"], "group_by": [], "time_grain": None,
        "period": {"preset": "custom", "from": dari, "to": sampai}, "compare": "none", "filters": [],
        "sort": {"by": None, "direction": "desc"}, "limit": None, "include_samples": False, "entity_scope": "active"})
    assert r.status_code == 200, r.text
    return float(r.json()["totals"].get("recognized_revenue") or 0)


async def test_U01_pendapatan_diakui_tanpa_jurnal_penutup(klien, kepala_admin):
    h = _h(kepala_admin, A)
    nov0 = await _pendapatan_diakui(klien, h, "2026-11-01", "2026-11-30")
    okt0 = await _pendapatan_diakui(klien, h, "2026-10-01", "2026-10-31")
    await _j(A, "2026-10-10T10:00:00", [("1-1100", 500, 0), ("4-1000", 0, 500)], "jual Okt", "pk16_u1a")
    await _j(A, "2026-10-31T23:59:59", [("4-1000", 500, 0), ("3-2000", 0, 500)], "penutup Okt", "pk16_u1c",
             source_type="closing")
    await _j(A, "2026-11-05T10:00:00", [("1-1100", 200, 0), ("4-1000", 0, 200)], "jual Nov", "pk16_u1b")
    assert await _pendapatan_diakui(klien, h, "2026-11-01", "2026-11-30") - nov0 == 200
    assert await _pendapatan_diakui(klien, h, "2026-10-01", "2026-10-31") - okt0 == 500


async def _laba_rugi(klien, h, **params):
    r = await klien.get("/api/finance/income-statement", headers=h,
                        params={"start": "2026-10-01", "end": "2026-10-31", **params})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
async def bersama(klien, kepala_admin):
    awal = {e: (await _laba_rugi(klien, _h(kepala_admin, e)))["revenue_total"] for e in (A, "all")}
    await _j(A, "2026-10-12T10:00:00", [("1-1200", 50 * JT, 0), ("4-1000", 0, 50 * JT)], "jual ke luar", "pk16_s1")
    await _j(A, "2026-10-15T10:00:00", [("1-1250", 20 * JT, 0), ("4-1000", 0, 20 * JT)], "jual ke B", "pk16_s2")
    await _j(B, "2026-10-15T10:00:00", [("1-1300", 20 * JT, 0), ("2-1250", 0, 20 * JT)], "beli dari A", "pk16_s3")
    return awal


async def test_U02_satu_pt(klien, db, kepala_admin, bersama):
    d = await _laba_rugi(klien, _h(kepala_admin, A))
    assert d["revenue_total"] - bersama[A] == 70 * JT
    m = d["scope_meta"]
    assert m["mode"] == "single" and m["entity_ids"] == [A] and m["label"] == await _nama(db, A)
    assert m["eliminated"] is False


async def test_U03_gabungan_berlabel(klien, db, kepala_admin, bersama):
    d = await _laba_rugi(klien, _h(kepala_admin, "all"))
    assert d["revenue_total"] - bersama["all"] == 70 * JT   # penjumlahan, tidak dieliminasi (K-15)
    m = d["scope_meta"]
    assert m["mode"] == "combined" and m["eliminated"] is False and len(m["entity_ids"]) > 1
    assert "belum dieliminasi" in m["label"]
    for e in m["entity_ids"]:
        assert await _nama(db, e, "short_name") in m["label"]
    assert "ent_" not in m["label"]


ENDPOINTS = [
    ("/api/finance/income-statement", {}), ("/api/finance/balance-sheet", {}), ("/api/finance/cash-flow", {}),
    ("/api/finance/equity-changes", {}), ("/api/gl/trial-balance", {}), ("/api/gl/summary", {}),
    ("/api/gl/accounts/1-1100/ledger", {}), ("/api/finance/bi", {"year": 2026}), ("/api/finance/tower", {}),
    ("/api/finance/profitability", {}), ("/api/finance/cashflow-forecast", {}),
    ("/api/finance/budget-vs-actual", {"year": 2026}), ("/api/cash-transactions/summary", {}),
]


@pytest.mark.parametrize("url,params", ENDPOINTS)
async def test_U04_semua_endpoint_bergabung_berlabel(klien, kepala_admin, url, params):
    r = await klien.get(url, headers=_h(kepala_admin, "all"), params=params)
    assert r.status_code == 200, r.text
    assert r.json()["scope_meta"]["mode"] == "combined"


async def test_U05_akun_satu_pt_minta_semua(klien, kepala_admin, akun, sesi, peran_tanpa_acuan, bersama):
    rid = await peran_tanpa_acuan({"accounting": ["view"]}, label="Lihat Akuntansi Kanda PK16")
    h = await sesi(await akun(rid, entitas=(B,)), entitas=B)
    d = await _laba_rugi(klien, h, entity_id="all")
    assert d["scope_meta"]["mode"] == "single" and d["scope_meta"]["entity_ids"] == [B]
    hanya_b = await _laba_rugi(klien, _h(kepala_admin, B))
    assert d["revenue_total"] == hanya_b["revenue_total"]


CSV = ["/api/finance/income-statement/export.csv", "/api/finance/balance-sheet/export.csv",
       "/api/finance/cash-flow/export.csv", "/api/finance/equity-changes/export.csv"]


@pytest.mark.parametrize("url", CSV)
async def test_U06_csv_baris_pt(klien, db, kepala_admin, url):
    r = await klien.get(url, headers=_h(kepala_admin, A), params={"start": "2026-10-01", "end": "2026-10-31"})
    assert r.status_code == 200, r.text
    baris = list(csv.reader(io.StringIO(r.text)))
    assert baris[1] == [f"PT: {await _nama(db, A)}"]
    assert baris[2] and baris[2][0]   # periode/tanggal turun satu baris
    r = await klien.get(url, headers=_h(kepala_admin, "all"), params={"start": "2026-10-01", "end": "2026-10-31"})
    baris = list(csv.reader(io.StringIO(r.text)))
    assert baris[1][0].startswith("Cakupan: Penjumlahan semua PT (")
    assert baris[1][0].endswith("— transaksi antar-PT belum dieliminasi")


async def test_U07_xlsx_profitabilitas(klien, db, kepala_admin):
    from openpyxl import load_workbook
    r = await klien.get("/api/finance/profitability/export.xlsx", headers=_h(kepala_admin, A))
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content)).worksheets[0]
    assert ws.cell(row=1, column=1).value == f"PT: {await _nama(db, A)}"
    r = await klien.get("/api/finance/profitability/export.xlsx", headers=_h(kepala_admin, "all"))
    ws = load_workbook(io.BytesIO(r.content)).worksheets[0]
    assert str(ws.cell(row=1, column=1).value).startswith("Cakupan: Penjumlahan semua PT")
