"""Uji bantahan reviewer B1 — PK-15 (SL-03, SL-04). Lapis B; cp ke backend/tests_mem/ lalu jalankan dengan -n 0."""
import asyncio

import pytest

from test_PK15_titipan_biaya_bank import (BASE, E1, _alokasi, _baris, _baris_doc, _jurnal_alokasi, _kas_baris, _saldo,
                                          _siap, _terbayar, dasar)  # noqa: F401

pytestmark = pytest.mark.anyio


async def test_SL03_bersamaan_dua_alokasi_melebihi_sisa(klien, db, kepala_admin):
    lid, so = await _siap(klien, db, kepala_admin)
    t0 = await _saldo(db, "2-1950")
    r1, r2 = await asyncio.gather(_alokasi(klien, kepala_admin, lid, [(so["x"], 6_000_000)]),
                                  _alokasi(klien, kepala_admin, lid, [(so["y"], 4_000_000), (so["x"], 2_000_000)]))
    b = await _baris_doc(db, lid)
    js = await _jurnal_alokasi(db, lid)
    dibayar = await _terbayar(db, so["x"]) + await _terbayar(db, so["y"])
    print("BERSAMAAN", r1.status_code, r2.status_code, "sisa", b["holding_remaining"], "jurnal", len(js),
          "dibayar", dibayar, [x["status"] for x in b["holding_allocated"]])
    assert b["holding_remaining"] >= 0
    assert round(10_000_000 - b["holding_remaining"], 2) == dibayar == sum(j["total_debit"] for j in js)
    assert await _saldo(db, "2-1950") - t0 == dibayar
    assert all(x["status"] == "done" for x in b["holding_allocated"]) and "saga_lock" not in b


async def test_SL03_batas_tiga_alokasi_berurutan_lalu_lebih_satu_rupiah(klien, db, kepala_admin):
    lid, so = await _siap(klien, db, kepala_admin)
    for amt in (1_000_000, 2_000_000, 3_000_000):
        r = await _alokasi(klien, kepala_admin, lid, [(so["x"], amt)])
        assert r.status_code == 200, r.text
    js = await _jurnal_alokasi(db, lid)
    assert len(js) == 3 and len({j["source_id"] for j in js}) == 3
    r = await _alokasi(klien, kepala_admin, lid, [(so["y"], 4_000_001)])
    assert r.status_code in (400, 409), r.text
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 2_000_001)])   # melebihi sisa tagihan so_x (8 jt)
    assert r.status_code in (400, 409), r.text
    assert len(await _jurnal_alokasi(db, lid)) == 3
    assert (await _baris_doc(db, lid))["holding_remaining"] == 4_000_000


async def test_SL03_koreksi_batal_titipan_sesudah_alokasi_sebagian(klien, db, kepala_admin):
    lid, so = await _siap(klien, db, kepala_admin)
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 3_000_000)])
    assert r.status_code == 200, r.text
    t0 = await _saldo(db, "2-1950")
    r = await klien.post(f"{BASE}/{lid}/holding/cancel", headers=kepala_admin, json={"reason": "uji batal reviewer"})
    b = await _baris_doc(db, lid)
    print("BATAL_TITIPAN", r.status_code, r.text[:200], "status", b["status"], "sisa", b.get("holding_remaining"),
          "Δ2-1950", await _saldo(db, "2-1950") - t0, "terbayar", await _terbayar(db, so["x"]))
    # Yang sudah dialokasikan tidak boleh hilang jejak: bila batal diterima, pesanan tetap terbayar 3 jt DAN
    # jurnal alokasinya tetap ada; bila ditolak, tidak ada yang berubah.
    assert await _terbayar(db, so["x"]) == 3_000_000 and len(await _jurnal_alokasi(db, lid)) == 1
    if r.status_code == 200:
        assert await _saldo(db, "2-1950") - t0 in (0, 7_000_000)
    else:
        assert await _saldo(db, "2-1950") - t0 == 0


async def test_SL04_bersamaan_dua_catat_biaya(klien, db, kepala_admin):
    lid = await _baris(db, "out", 30_000, "2026-11-07")
    r1, r2 = await asyncio.gather(
        klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"}),
        klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"}))
    kas = await _kas_baris(db, lid)
    print("BIAYA_BERSAMAAN", r1.status_code, r2.status_code, "kas", len(kas))
    assert sorted([r1.status_code, r2.status_code])[0] == 200
    assert len(kas) == 1
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                                     "status": {"$ne": "void"}}) == 1
    assert "saga_lock" not in await _baris_doc(db, lid)


async def test_SL04_koreksi_dua_putaran_lepas_catat(klien, db, kepala_admin):
    from services import bank_recon_service as brs
    akun = (await brs.load_cfg(E1))["charge_acc"]
    b0 = await _saldo(db, akun)
    lid = await _baris(db, "out", 40_000, "2026-11-08")
    for i in range(3):
        r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"})
        assert r.status_code == 200, (i, r.text)
        if i < 2:
            r = await klien.post(f"{BASE}/{lid}/unmatch", headers=kepala_admin, json={"reason": f"putaran {i} uji"})
            assert r.status_code == 200, (i, r.text)
            assert await _saldo(db, akun) - b0 == 0, f"sesudah lepas putaran {i} beban belum nol"
    kas = await _kas_baris(db, lid)
    semua = await db.cash_transactions.count_documents({"ref_type": "bank_statement_line", "ref_id": lid})
    print("PUTARAN", "kas hidup", len(kas), "kas total", semua, "Δbeban", await _saldo(db, akun) - b0)
    assert len(kas) == 1 and await _saldo(db, akun) - b0 == 40_000


async def test_SL04_ulang_catat_pada_baris_sudah_tertaut(klien, db, kepala_admin):
    lid = await _baris(db, "in", 12_345, "2026-11-09")
    r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "interest"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "interest"})
    assert r.status_code in (400, 409), r.text
    r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"})
    assert r.status_code in (400, 409), r.text
    assert len(await _kas_baris(db, lid)) == 1
