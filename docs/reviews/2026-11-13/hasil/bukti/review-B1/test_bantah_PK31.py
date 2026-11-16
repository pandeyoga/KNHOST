"""Uji bantahan reviewer B1 — PK-31 (IC-03, IC-04, IC-07). Lapis B; cp ke backend/tests_mem/, jalankan -n 0 -s."""
# ruff: noqa: F811
import asyncio

import pytest

from pembantu import AKTOR_UJI, jumlah, tutup_periode
from test_PK31_eliminasi_periode import (JT, P1, PRD, RF, _refund, _saldo_ica, baris, data_p1, data_rf, ent,  # noqa: F401
                                         jurnal_barang, jurnal_jual, mesin, neto, pasangan, retur_fixture, roll,
                                         tugas_gudang, unsur_rantai)
from core_utils import now_iso

pytestmark = pytest.mark.anyio


async def _entri(db, pid):
    rows = await db.intercompany_eliminations.find({"source_g6_pair_id": pid}, {"_id": 0}).to_list(200)
    return {r.get("period_key"): baris(r) for r in rows}, len(rows)


# ── IC-03 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_IC03_ulang_sinkron_dua_kali_tidak_menggandakan(db, data_p1):
    eng = mesin()
    for pk in ("2026-12", "2027-01"):
        await eng.sync_period(pk, P1)
    e1, n1 = await _entri(db, P1)
    for pk in ("2026-12", "2027-01", "2026-12"):
        await eng.sync_period(pk, P1)
    e2, n2 = await _entri(db, P1)
    print("OBS sinkron ulang entri", n1, n2, sorted(k for k in e1 if k))
    assert n1 == n2 and e1 == e2
    assert len([k for k in e2 if k]) == len(set(k for k in e2 if k))


async def test_IC03_data_lama_kejadian_mundur_sesudah_bulan_beku(db, data_p1):
    """Bulan Jan 2027 ditutup di kedua PT, entri Jan tersimpan. Lalu surat jalan BERTANGGAL 20 Jan disisipkan
    belakangan. Entri Jan yang tersimpan tidak boleh berubah diam-diam; selisihnya harus terlihat (stale)."""
    a, b = data_p1
    eng = mesin()
    await eng.sync_period("2027-01", P1)
    sebelum, _ = await _entri(db, P1)
    c1, c2 = await tutup_periode(a, "2027-01"), await tutup_periode(b, "2027-01")
    try:
        beku = await eng.sync_period("2027-01", P1)   # sinkron sesudah tutup → entri dibekukan
        simpan = await db.intercompany_eliminations.find_one({"source_g6_pair_id": P1, "period_key": "2027-01"}, {"_id": 0})
        print("OBS sesudah tutup+sinkron: frozen", simpan.get("frozen"), {k: v for k, v in beku.items() if isinstance(v, int)})
        assert simpan["frozen"] is True
        await db.inventory_rolls.update_one({"id": "roll_pk31_1"}, {"$set": {"length_remaining": 500.0}})
        induk = await db.inventory_rolls.find_one({"id": "roll_pk31_1"}, {"_id": 0})
        await db.inventory_rolls.insert_one({**induk, "id": "roll_b1_mundur", "roll_no": "RB1M", "length_initial": 500.0,
                                             "length_remaining": 500.0, "status": "in_transit_sales",
                                             "parent_roll_id": "roll_pk31_1"})
        await db.shipments.insert_one({"id": "shp_b1_mundur", "shipment_no": "SJ-B1-M", "entity_id": b,
                                       "status": "dispatched", "rolls": [{"roll_id": "roll_b1_mundur", "length": 500.0}],
                                       "created_at": "2027-01-20T03:00:00+00:00"})
        hasil = await eng.sync_period("2027-01", P1)
        sesudah, _ = await _entri(db, P1)
        st = await eng.pair_state(P1, "2027-01-31")
        print("OBS mundur: hasil sinkron", {k: (v if not isinstance(v, list) else len(v)) for k, v in hasil.items()},
              "| entri Jan sama:", sebelum.get("2027-01") == sesudah.get("2027-01"), "| keadaan hitung-ulang urp", st["urp"])
        assert sebelum.get("2027-01") == sesudah.get("2027-01"), "entri bulan beku berubah sesudah kejadian mundur"
        assert any(x["pair_id"] == P1 and x["period_key"] == "2027-01" for x in hasil["stale"]), hasil
    finally:
        await db.period_closings.delete_one({"id": c1["id"]})
        await db.period_closings.delete_one({"id": c2["id"]})
        await db.shipments.delete_one({"id": "shp_b1_mundur"})
        await db.inventory_rolls.delete_one({"id": "roll_b1_mundur"})
        await db.inventory_rolls.update_one({"id": "roll_pk31_1"}, {"$set": {"length_remaining": 1000.0}})


# ── IC-04 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _pindah(db, rid, panjang, tid, pid, penjual, pembeli, tanggal):
    from services import interco_service as ics
    await tugas_gudang(db, tid, pid, penjual, pembeli, [(rid, panjang)], tanggal)
    await db.inventory_rolls.update_one({"id": rid}, {"$set": {
        "owner_entity_id": pembeli, "status": "available",
        "acquired": {"via": "transfer", "ref_id": tid, "date": f"{tanggal}T03:00:00+00:00"}}})
    return await ics.on_warehouse_task_executed(await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0}), "uji")


async def test_IC04_sebagian_rantai_separuh_ke_C_lalu_keluar_grup(db, data_p1):
    """A→B 1.000 m (S 100 jt, C 60 jt). B memotong: 500 m dijual ke C (60 jt; HPP B 50 jt), 500 m tetap di B.
    Lalu C menjual 250 m ke luar grup, kemudian sisanya. Hitung tangan:
      sesudah B→C: A→B urp = 40 jt × 1.000/1.000 = 40 jt; B→C urp = 10 jt.
      sesudah C jual 250 m: A→B urp = 40 × 750/1.000 = 30 jt; B→C urp = 10 × 250/500 = 5 jt.
      sesudah C jual 250 m lagi dan B jual 500 m: semua 0."""
    a, b, c = await ent()
    pa, pb = "b1_pa", "b1_pb"
    eng = mesin()
    await db.inventory_rolls.insert_one({"id": "roll_b1_a", "roll_no": "RB1A", "product_id": PRD, "owner_entity_id": a,
                                         "length_initial": 1000.0, "length_remaining": 1000.0, "unit": "meter",
                                         "status": "reserved", "unit_cost": 60_000, "base_unit_cost": 60_000,
                                         "created_at": now_iso()})
    await db.interco_transactions.insert_many(pasangan(pa, a, b, 100 * JT, status="confirmed", tanggal="2027-07-01"))
    await jurnal_jual(pa, a, b, 100 * JT, "2027-07-01")
    await jurnal_barang(pa, a, b, 100 * JT, 60 * JT, "2027-07-02")
    await _pindah(db, "roll_b1_a", 1000.0, "trn_b1_a", pa, a, b, "2027-07-02")
    # B memotong roll: anak 500 m (fixture potong — menyalin cost_basis induk seperti potong roll)
    induk = await db.inventory_rolls.find_one({"id": "roll_b1_a"}, {"_id": 0})
    await db.inventory_rolls.update_one({"id": "roll_b1_a"}, {"$set": {"length_remaining": 500.0}})
    await db.inventory_rolls.insert_one({**induk, "id": "roll_b1_c", "roll_no": "RB1C", "length_initial": 500.0,
                                         "length_remaining": 500.0, "status": "reserved", "parent_roll_id": "roll_b1_a"})
    await db.interco_transactions.insert_many(pasangan(pb, b, c, 60 * JT, qty=500.0, status="confirmed",
                                                       tanggal="2027-08-01"))
    await jurnal_jual(pb, b, c, 60 * JT, "2027-08-01")
    await jurnal_barang(pb, b, c, 60 * JT, 50 * JT, "2027-08-02")
    await _pindah(db, "roll_b1_c", 500.0, "trn_b1_c", pb, b, c, "2027-08-02")
    sa, sb = await eng.pair_state(pa, "2027-08-31"), await eng.pair_state(pb, "2027-08-31")
    print("OBS rantai sebagian (Agu) A→B urp", sa["urp"], "u", sa["unsold_ratio"], "| B→C urp", sb["urp"], "u", sb["unsold_ratio"])
    assert (sa["urp"], sb["urp"]) == (40 * JT, 10 * JT)
    # C jual 250 m keluar grup 10 Sep
    anak = await db.inventory_rolls.find_one({"id": "roll_b1_c"}, {"_id": 0})
    await db.inventory_rolls.update_one({"id": "roll_b1_c"}, {"$set": {"length_remaining": 250.0}})
    await db.inventory_rolls.insert_one({**anak, "id": "roll_b1_c1", "roll_no": "RB1C1", "length_initial": 250.0,
                                         "length_remaining": 250.0, "status": "in_transit_sales",
                                         "parent_roll_id": "roll_b1_c"})
    await db.shipments.insert_one({"id": "shp_b1_c1", "shipment_no": "SJ-B1-C1", "entity_id": c, "status": "dispatched",
                                   "rolls": [{"roll_id": "roll_b1_c1", "length": 250.0}],
                                   "created_at": "2027-09-10T03:00:00+00:00"})
    sa, sb = await eng.pair_state(pa, "2027-09-30"), await eng.pair_state(pb, "2027-09-30")
    print("OBS rantai sebagian (Sep) A→B urp", sa["urp"], "u", sa["unsold_ratio"], "| B→C urp", sb["urp"], "u", sb["unsold_ratio"])
    assert (sa["urp"], sb["urp"]) == (30 * JT, 5 * JT)
    # laporan tanggal lama (Agu) tidak ikut berubah
    sa0 = await eng.pair_state(pa, "2027-08-31")
    assert sa0["urp"] == 40 * JT
    # semua keluar grup 5 Okt: sisa C 250 m dan sisa B 500 m
    for rid, ent_id, sid, ln in (("roll_b1_c", c, "shp_b1_c2", 250.0), ("roll_b1_a", b, "shp_b1_a2", 500.0)):
        await db.inventory_rolls.update_one({"id": rid}, {"$set": {"status": "in_transit_sales"}})
        await db.shipments.insert_one({"id": sid, "shipment_no": sid.upper(), "entity_id": ent_id, "status": "dispatched",
                                       "rolls": [{"roll_id": rid, "length": ln}],
                                       "created_at": "2027-10-05T03:00:00+00:00"})
    sa, sb = await eng.pair_state(pa, "2027-10-31"), await eng.pair_state(pb, "2027-10-31")
    print("OBS rantai sebagian (Okt) A→B urp", sa["urp"], "| B→C urp", sb["urp"])
    assert (sa["urp"], sb["urp"]) == (0, 0)


# ── IC-07 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_IC07_sebagian_dan_bersamaan_refund(klien, kepala_admin, db, data_rf):
    from services import interco_return_service as icret
    s, b = data_rf
    r0 = await _refund(klien, kepala_admin, s, b, key="b1-tanpa-retur")     # belum ada retur → tidak ada sisa refund
    print("OBS refund tanpa retur", r0.status_code, r0.text[:120])
    assert r0.status_code in (400, 409), r0.text
    await db.interco_returns.insert_many(retur_fixture("b1_rp", RF, s, b, 4 * JT))
    await icret.approve("b1_rp_ret", AKTOR_UJI)
    r1 = await _refund(klien, kepala_admin, s, b, key="b1-sebagian", jumlah_rp=1.5 * JT)
    assert r1.status_code == 200, r1.text
    row = await _saldo_ica(klien, {**kepala_admin, "X-Entity-Id": s}, s, b)
    assert row["refund_outstanding"] == 2.5 * JT and await neto(db, s, "1-1250") == -2.5 * JT
    ra, rb = await asyncio.gather(_refund(klien, kepala_admin, s, b, key="b1-ganda-1", jumlah_rp=2.5 * JT),
                                  _refund(klien, kepala_admin, s, b, key="b1-ganda-2", jumlah_rp=2.5 * JT))
    row = await _saldo_ica(klien, {**kepala_admin, "X-Entity-Id": s}, s, b)
    n = await jumlah("interco_settlements", {"kind": "refund", "status": {"$ne": "void"}})
    print("OBS refund bersamaan", ra.status_code, rb.status_code, "sisa", row["refund_outstanding"], "dok refund", n,
          "1-1250 penjual", await neto(db, s, "1-1250"), "2-1250 pembeli", await neto(db, b, "2-1250"))
    assert sorted([ra.status_code, rb.status_code])[0] == 200 and sorted([ra.status_code, rb.status_code])[1] != 200
    assert row["refund_outstanding"] == 0 and n == 2
    assert await neto(db, s, "1-1250") == 0 and await neto(db, b, "2-1250") == 0
    docs = await db.interco_transactions.find({"pair_id": RF}, {"_id": 0}).to_list(2)
    assert [d["refund_paid"] for d in docs] == [4 * JT, 4 * JT]


async def test_IC07_koreksi_retur_kedua_melebihi_nilai(klien, kepala_admin, db, data_rf):
    """Retur kedua 7 jt atas transaksi 10 jt yang sudah diretur 4 jt: total retur tidak boleh melebihi nilai transaksi
    (kalau lolos, refund_due 11 jt > uang yang pernah diterima 10 jt)."""
    from services import interco_return_service as icret
    s, b = data_rf
    await db.interco_returns.insert_many(retur_fixture("b1_rp2", RF, s, b, 7 * JT))
    galat = ""
    try:
        await icret.approve("b1_rp2_ret", AKTOR_UJI)
    except Exception as exc:  # noqa: BLE001
        galat = f"{type(exc).__name__}: {str(getattr(exc, 'detail', exc))[:140]}"
    docs = await db.interco_transactions.find({"pair_id": RF}, {"_id": 0}).to_list(2)
    print("OBS retur melebihi", galat or "LOLOS", "refund_due", [d.get("refund_due") for d in docs],
          "returned", [d.get("returned_amount") for d in docs])
    assert all(float(d.get("refund_due") or 0) <= 10 * JT for d in docs)
