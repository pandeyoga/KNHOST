"""PK-31 — eliminasi konsolidasi per periode dari data BERTANGGAL; rantai A→B→C; refund retur setelah lunas.

Uji penerimaan U1–U14 (lapis B, database tiruan). U15 (indeks unik + dua refund bersamaan) di MongoDB asli:
`backend/tests/test_bp_PK31_unik_refund_bersamaan.py`. U16 (layar) = uji komponen
`frontend/src/features/__tests__/pk31KonsolidasiRefund.test.js` + uji jalan (lingkungan A).

Persiapan bersama (spesifikasi): PT uji AAA, BBB, CCC tanpa PPN antar-PT; harga internal S = 100.000.000, HPP penjual
C = 60.000.000, 1.000 m. Dokumen antar-PT, jurnal, tugas gudang, roll, dan surat jalan disisipkan sebagai FIXTURE
BERTANGGAL (uji tidak bergantung jam). Alur yang dijalankan lewat API/layanan ditulis "ALUR" di komentar.

Modul ini satu basis data untuk semua tes (fixture `aplikasi` bercakupan modul) — urutan tes = urutan berkas.
Uji lain (U6–U14) memakai pasangan dan/atau PT sendiri supaya angka U1–U5 tidak tercampur.
"""
import re

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jumlah, pt_uji, tutup_periode

JT = 1_000_000
PRD = "prd_pk31"
P1 = "pk31_p1"          # A→B: konfirmasi 28 Des 2026, barang pindah 5 Jan 2027 (U1–U5, U14)


# ── pembantu fixture ─────────────────────────────────────────────────────────────────────────────────────────────────
async def pt(kode):
    """`pt_uji` + buang cache status PT (fixture disisip langsung; penjaga `X-Entity-Id` membaca cache 20 detik)."""
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await pt_uji(kode)
    invalidate_status_cache()
    return eid


async def ent():
    return await pt("AAA"), await pt("BBB"), await pt("CCC")


async def je(entity, tanggal, baris, source_type, source_id):
    """Jurnal fixture bertanggal lewat pintu jurnal biasa (`_insert_entry`)."""
    from services import gl_service as gl
    return await gl._insert_entry(lines=[{"account_code": k, "debit": d, "credit": c} for k, d, c in baris],
                                  description=f"fixture {source_id}", date=tanggal, source_type=source_type,
                                  source_id=source_id, entity_id=entity, created_by="uji")


def pasangan(pid, penjual, pembeli, harga, *, qty=1000.0, status="received", tanggal="2026-12-28", nomor=None,
             produk=PRD):
    nomor = nomor or f"IC/{pid}"
    base = {"pair_id": pid, "seller_entity_id": penjual, "buyer_entity_id": pembeli,
            "seller_entity_name": f"PT {penjual}", "buyer_entity_name": f"PT {pembeli}",
            "items": [{"product_id": produk, "sku": "PK31", "product_name": "Kain PK31", "unit": "meter",
                       "quantity": qty, "unit_price": round(harga / qty, 2), "line_subtotal": harga}],
            "subtotal": harga, "tax_apply": False, "tax_rate": 0.0, "tax_amount": 0.0, "grand_total": harga,
            "settled_amount": 0.0, "returned_amount": 0.0, "status": status, "doc_date": tanggal,
            "confirmed_at": f"{tanggal}T03:00:00+00:00", "timeline": [], "created_at": f"{tanggal}T02:00:00+00:00",
            "created_by": "Orang Lain", "gl_status": "posted"}
    return [{**base, "id": f"{pid}_s", "number": nomor, "role": "seller", "entity_id": penjual,
             "counterpart_id": f"{pid}_b", "counterpart_number": f"{nomor}-B"},
            {**base, "id": f"{pid}_b", "number": f"{nomor}-B", "role": "buyer", "entity_id": pembeli,
             "counterpart_id": f"{pid}_s", "counterpart_number": nomor}]


async def jurnal_jual(pid, penjual, pembeli, harga, tanggal):
    """Jurnal konfirmasi (`{pair}:seller` / `{pair}:buyer`) — baris sama dengan `_confirm_sides` tanpa PPN."""
    await je(penjual, tanggal, [("1-1250", harga, 0), ("4-1000", 0, harga)], "interco_transaction", f"{pid}:seller")
    await je(pembeli, tanggal, [("1-1310", harga, 0), ("2-1250", 0, harga)], "interco_transaction", f"{pid}:buyer")


async def jurnal_barang(pid, penjual, pembeli, harga, hpp, tanggal):
    """Jurnal yang mengikuti barang (`{pair}:cogs` / `{pair}:receipt`) — baris sama dengan `post_gl_on_delivery`."""
    await je(penjual, tanggal, [("5-1000", hpp, 0), ("1-1300", 0, hpp)], "interco_transaction", f"{pid}:cogs")
    await je(pembeli, tanggal, [("1-1300", harga, 0), ("1-1310", 0, harga)], "interco_transaction", f"{pid}:receipt")


async def tugas_gudang(db, tid, pid, penjual, pembeli, rolls, tanggal):
    await db.warehouse_transfers.insert_one({
        "id": tid, "code": f"TRF-{tid}", "transfer_kind": "inter_entity", "interco_pair_id": pid,
        "status": "completed", "approved_at": f"{tanggal}T03:00:00+00:00", "entity_id": penjual,
        "source_entity_id": penjual, "dest_entity_id": pembeli,
        "items": [{"product_id": PRD, "qty": sum(x[1] for x in rolls), "unit": "meter",
                   "rolls": [{"roll_id": r, "length": ln} for r, ln in rolls]}],
        "created_at": f"{tanggal}T02:00:00+00:00", "updated_at": f"{tanggal}T03:00:00+00:00"})


def unsur_rantai(pid, penjual, pembeli, harga_m, biaya_lama_m, tanggal):
    return {"interco_pair_id": pid, "interco_number": f"IC/{pid}", "seller_entity_id": penjual,
            "buyer_entity_id": pembeli, "unit_price": harga_m, "previous_unit_cost": biaya_lama_m,
            "at": f"{tanggal}T03:00:00+00:00"}


def roll(rid, pemilik, panjang, biaya_m, rantai, *, status="available", induk=None):
    last = rantai[-1]
    return {"id": rid, "roll_no": rid.upper(), "product_id": PRD, "owner_entity_id": pemilik,
            "length_initial": panjang, "length_remaining": panjang, "unit": "meter", "status": status,
            "unit_cost": biaya_m, "base_unit_cost": biaya_m, "parent_roll_id": induk,
            "cost_basis": {"source": "interco_purchase", "interco_pair_id": last["interco_pair_id"],
                           "interco_number": last["interco_number"],
                           "previous_unit_cost": last["previous_unit_cost"], "at": last["at"], "chain": list(rantai)},
            "created_at": now_iso()}


def baris(entry):
    """Baris eliminasi sebagai {(akun, debit, kredit)} — urutan & keterangan diabaikan."""
    return {(ln["account_code"], round(float(ln.get("debit") or 0), 2), round(float(ln.get("credit") or 0), 2))
            for ln in entry["lines"]}


async def neto(db, entity, kode):
    """Σ debit − Σ kredit akun di buku satu PT (jurnal tidak-void)."""
    tot = 0.0
    async for j in db.journal_entries.find({"entity_id": entity, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in j.get("lines", []):
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


def mesin():
    from services import interco_elimination_engine as eng   # PK-31 — berkas baru (merah di kode lama: tidak ada)
    return eng


# ── Persiapan U1–U5: A→B, S 100 jt, C 60 jt, 1.000 m ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def data_p1(db):
    a, b, _c = await ent()
    await db.products.insert_one({"id": PRD, "name": "Kain PK31", "sku": "PK31", "base_unit": "meter",
                                  "status": "active"})
    # Saldo awal persediaan A: 1.000 m × Rp 60.000 = 60 jt (FIXTURE).
    await je(a, "2026-01-02", [("1-1300", 60 * JT, 0), ("3-2900", 0, 60 * JT)], "uji", "pk31_saldo_awal_a")
    await db.interco_transactions.insert_many(pasangan(P1, a, b, 100 * JT, nomor="AAA/IC-P1"))
    await jurnal_jual(P1, a, b, 100 * JT, "2026-12-28")                 # konfirmasi 28 Des 2026
    await jurnal_barang(P1, a, b, 100 * JT, 60 * JT, "2027-01-05")      # HPP & penerimaan 5 Jan 2027
    await tugas_gudang(db, "trn_pk31_p1", P1, a, b, [("roll_pk31_1", 1000.0)], "2027-01-05")
    await db.inventory_rolls.insert_one(roll("roll_pk31_1", b, 1000.0, 100_000,
                                             [unsur_rantai(P1, a, b, 100_000, 60_000, "2027-01-05")]))
    return a, b


async def test_PK31_U1_keadaan_akhir_desember_belum_diterima(db, data_p1):
    eng = mesin()
    st = await eng.pair_state(P1, "2026-12-31")
    # Hitungan tangan: pendapatan = kredit 4-1000 pada {pair}:seller ≤ 31 Des = 100 jt; jurnal {pair}:receipt baru
    # 5 Jan → belum diterima → laba belum terealisasi = seluruh pendapatan (barang masih "di perjalanan" di B).
    assert st["revenue"] == 100 * JT and st["cogs"] == 0
    assert st["delivered"] is False and st["unsold_ratio"] == 1
    assert st["urp"] == 100 * JT and st["ic_balance"] == 100 * JT
    e = await eng.period_entry(P1, "2026-12")
    assert e["effective_date"] == "2026-12-31" and e["period_key"] == "2026-12"
    assert baris(e) == {("4-1000", 100 * JT, 0), ("1-1310", 0, 100 * JT),
                        ("2-1250", 100 * JT, 0), ("1-1250", 0, 100 * JT)}
    assert e["balanced"] is True


async def test_PK31_U2_selisih_januari(db, data_p1):
    eng = mesin()
    st = await eng.pair_state(P1, "2027-01-31")
    # 31 Jan: HPP 60 jt (5 Jan), sudah diterima, 1.000 m pindah, 0 m terjual → u = 1; urp = (100 − 60) × 1 = 40 jt.
    assert (st["cogs"], st["delivered"], st["unsold_ratio"], st["urp"]) == (60 * JT, True, 1, 40 * JT)
    assert (st["moved_len"], st["sold_len"]) == (1000, 0)
    e = await eng.period_entry(P1, "2027-01")
    # Kumulatif 31 Jan: Dr 4-1000 100 · Cr 5-1000 60 · Cr 1-1300 40 · Dr 2-1250 100 · Cr 1-1250 100.
    # Kumulatif 31 Des: Dr 4-1000 100 · Cr 1-1310 100 · Dr 2-1250 100 · Cr 1-1250 100.
    # Selisih: 1-1310 +100 (Dr) · 5-1000 −60 (Cr) · 1-1300 −40 (Cr) → 100 = 60 + 40; 1-1250/2-1250 nol (tidak ada baris).
    assert baris(e) == {("1-1310", 100 * JT, 0), ("5-1000", 0, 60 * JT), ("1-1300", 0, 40 * JT)}


async def _ringkasan(klien, h, year, as_of):
    r = await klien.get(f"/api/finance/consolidation/summary?year={year}&as_of={as_of}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
async def kepala_ab(akun, sesi, peran_tanpa_acuan, data_p1):
    a, b = data_p1
    p = await peran_tanpa_acuan({"accounting": ["view"]}, label="Konsolidasi AB PK31")
    return await sesi(await akun(p, entitas=(a, b)), entitas=a)


async def test_PK31_U3_ringkasan_konsolidasi_dua_tahun(klien, kepala_ab, data_p1):
    # ALUR: GET ringkasan (pengguna bercakupan A+B). Buku A 2026: pendapatan 100; buku B: 1-1310 100 / 2-1250 100.
    s26 = await _ringkasan(klien, kepala_ab, 2026, "2026-12-31")
    # Laba konsolidasi 2026 = 100 jt (A) − 100 jt (eliminasi Des) = 0.
    assert s26["consolidated"]["net_income"] == 0, s26["consolidated"]
    # Aset grup 31 Des 2026 = A (1-1300 60 + 1-1250 100) + B (1-1310 100) − eliminasi (1-1310 100 + 1-1250 100) = 60 jt
    # = persediaan di A (satu-satunya aset grup di fixture ini).
    assert s26["consolidated"]["assets"] == 60 * JT and s26["balanced"] is True
    s27 = await _ringkasan(klien, kepala_ab, 2027, "2027-12-31")
    # 2027: HPP A −60 jt + eliminasi Jan (Cr 5-1000 60 jt) = 0.
    assert s27["consolidated"]["net_income"] == 0, s27["consolidated"]
    # Aset 31 Des 2027 = A 1-1250 100 + B 1-1300 100 − (1-1250 100 + 1-1300 40) = 60 jt (di B, nilai HPP asli penjual).
    assert s27["consolidated"]["assets"] == 60 * JT and s27["balanced"] is True


async def test_PK31_U4_laporan_tanggal_lama_tidak_berubah(klien, kepala_ab, db, data_p1):
    a, b = data_p1
    sebelum = [await _ringkasan(klien, kepala_ab, 2026, "2026-12-31"),
               await _ringkasan(klien, kepala_ab, 2027, "2027-01-31")]
    # FIXTURE: surat jalan B ke pelanggan 15 Mar 2027 — roll 1.000 m dipotong; potongan 500 m dikirim.
    await db.inventory_rolls.update_one({"id": "roll_pk31_1"}, {"$set": {"length_remaining": 500.0}})
    induk = await db.inventory_rolls.find_one({"id": "roll_pk31_1"}, {"_id": 0})
    await db.inventory_rolls.insert_one({**induk, "id": "roll_pk31_1b", "roll_no": "ROLL_PK31_1B",
                                         "length_initial": 500.0, "length_remaining": 500.0,
                                         "status": "in_transit_sales", "parent_roll_id": "roll_pk31_1"})
    await db.shipments.insert_one({"id": "shp_pk31_1", "shipment_no": "SJ-PK31-1", "entity_id": b,
                                   "order_id": "so_pk31", "product_id": PRD, "qty": 500.0, "status": "dispatched",
                                   "rolls": [{"roll_id": "roll_pk31_1b", "length": 500.0, "unit": "meter"}],
                                   "created_at": "2027-03-15T03:00:00+00:00"})
    sesudah = [await _ringkasan(klien, kepala_ab, 2026, "2026-12-31"),
               await _ringkasan(klien, kepala_ab, 2027, "2027-01-31")]
    for x, y in zip(sebelum, sesudah):
        for k in ("gross", "elimination", "consolidated"):
            assert x[k] == y[k], (k, x[k], y[k])
    assert sesudah[0]["consolidated"]["net_income"] == 0 and sesudah[0]["consolidated"]["assets"] == 60 * JT


async def test_PK31_U5_maret_separuh_terjual(db, data_p1):
    eng = mesin()
    if not await db.shipments.find_one({"id": "shp_pk31_1"}):   # U4 sudah menyisipkannya (dijalankan sendiri: sisipkan di sini)
        a, b = data_p1
        await db.inventory_rolls.update_one({"id": "roll_pk31_1"}, {"$set": {"length_remaining": 500.0}})
        induk = await db.inventory_rolls.find_one({"id": "roll_pk31_1"}, {"_id": 0})
        await db.inventory_rolls.insert_one({**induk, "id": "roll_pk31_1b", "length_initial": 500.0,
                                             "length_remaining": 500.0, "status": "in_transit_sales",
                                             "parent_roll_id": "roll_pk31_1"})
        await db.shipments.insert_one({"id": "shp_pk31_1", "entity_id": b, "status": "dispatched",
                                       "rolls": [{"roll_id": "roll_pk31_1b", "length": 500.0}],
                                       "created_at": "2027-03-15T03:00:00+00:00"})
    st = await eng.pair_state(P1, "2027-03-31")
    # 500 m keluar grup 15 Mar → u = 1 − 500/1.000 = 0,5; urp = (100 − 60) × 0,5 = 20 jt.
    assert (st["sold_len"], st["unsold_ratio"], st["urp"]) == (500, 0.5, 20 * JT)
    feb = await eng.period_entry(P1, "2027-02")
    assert feb["lines"] == []
    e = await eng.period_entry(P1, "2027-03")
    # Kumulatif Mar: Cr 5-1000 = 100 − 20 = 80, Cr 1-1300 20. Feb: Cr 5-1000 60, Cr 1-1300 40.
    # Selisih: 1-1300 +20 (Dr) · 5-1000 −20 (Cr).
    assert baris(e) == {("1-1300", 20 * JT, 0), ("5-1000", 0, 20 * JT)}


# ── U6: rantai A→B→C (ALUR on_warehouse_task_executed dua kali) ─────────────────────────────────────────────────────
async def _pindahkan(db, rid, tid, pid, penjual, pembeli, tanggal):
    """Seperti `roll_service.execute_ownership_transfer`: pemilik berganti, `acquired.ref_id` = tugas (FIXTURE)."""
    from services import interco_service as ics
    await tugas_gudang(db, tid, pid, penjual, pembeli, [(rid, 1000.0)], tanggal)
    await db.inventory_rolls.update_one({"id": rid}, {"$set": {
        "owner_entity_id": pembeli, "status": "available",
        "acquired": {"via": "transfer", "ref_id": tid, "date": f"{tanggal}T03:00:00+00:00"}}})
    tr = await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0})
    return await ics.on_warehouse_task_executed(tr, "uji")


async def test_PK31_U6_rantai_tiga_pt(db, data_p1):
    a, b, c = await ent()
    p6, p7 = "pk31_p6", "pk31_p7"
    await db.inventory_rolls.insert_one({"id": "roll_pk31_6", "roll_no": "R6", "product_id": PRD,
                                         "owner_entity_id": a, "length_initial": 1000.0, "length_remaining": 1000.0,
                                         "unit": "meter", "status": "reserved", "unit_cost": 60_000,
                                         "base_unit_cost": 60_000, "created_at": now_iso()})
    # A→B: S 100 jt, C 60 jt (4 → 5 Apr 2027)
    await db.interco_transactions.insert_many(pasangan(p6, a, b, 100 * JT, status="confirmed", tanggal="2027-04-04"))
    await jurnal_jual(p6, a, b, 100 * JT, "2027-04-04")
    await jurnal_barang(p6, a, b, 100 * JT, 60 * JT, "2027-04-05")
    await _pindahkan(db, "roll_pk31_6", "trn_pk31_6", p6, a, b, "2027-04-05")
    # B→C: seluruh roll, harga 120 jt; HPP B = 1.000 × Rp 100.000 = 100 jt (1 → 2 Mei 2027)
    await db.interco_transactions.insert_many(pasangan(p7, b, c, 120 * JT, status="confirmed", tanggal="2027-05-01"))
    await jurnal_jual(p7, b, c, 120 * JT, "2027-05-01")
    await jurnal_barang(p7, b, c, 120 * JT, 100 * JT, "2027-05-02")
    await _pindahkan(db, "roll_pk31_6", "trn_pk31_7", p7, b, c, "2027-05-02")

    r = await db.inventory_rolls.find_one({"id": "roll_pk31_6"}, {"_id": 0})
    rantai = r["cost_basis"]["chain"]
    assert [x["interco_pair_id"] for x in rantai] == [p6, p7]
    assert (rantai[0]["seller_entity_id"], rantai[0]["buyer_entity_id"], rantai[0]["unit_price"],
            rantai[0]["previous_unit_cost"]) == (a, b, 100_000, 60_000)
    assert (rantai[1]["seller_entity_id"], rantai[1]["buyer_entity_id"], rantai[1]["unit_price"],
            rantai[1]["previous_unit_cost"]) == (b, c, 120_000, 100_000)
    assert r["cost_basis"]["interco_pair_id"] == p7   # tingkat atas tetap = perpindahan terakhir

    eng = mesin()
    s6 = await eng.pair_state(p6, "2027-06-30")
    s7 = await eng.pair_state(p7, "2027-06-30")
    # Barang masih di C (di dalam grup) → A→B belum terealisasi: u = 1, urp = 100 − 60 = 40 jt. Hari ini (kode lama)
    # `unsold_ratio` A→B = 0 karena roll bertanda A→B tidak lagi dimiliki B.
    assert (s6["unsold_ratio"], s6["urp"]) == (1, 40 * JT)
    assert (s7["revenue"], s7["cogs"], s7["urp"]) == (120 * JT, 100 * JT, 20 * JT)
    assert s6["urp"] + s7["urp"] == 120 * JT - 60 * JT   # laba grup belum terealisasi 60 jt = 120 − 60


async def test_PK31_U6b_rapor_margin_satu_rumus(db, data_p1):
    from services import interco_margin as icm
    u = await icm.unsold_ratio("pk31_p6", as_of="2027-06-30")
    assert (u["ratio"], u["qty_base"], u["qty_remaining"]) == (1, 1000, 1000)   # kode lama: rasio 0


# ── U7: jual di bawah HPP ─────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK31_U7_rugi_tidak_dieliminasi(db, data_p1):
    from services import interco_margin as icm
    eng = mesin()
    a, b, _c = await ent()
    p8 = "pk31_p8"
    await db.interco_transactions.insert_many(pasangan(p8, a, b, 50 * JT, tanggal="2027-04-10"))
    await jurnal_jual(p8, a, b, 50 * JT, "2027-04-10")
    await jurnal_barang(p8, a, b, 50 * JT, 60 * JT, "2027-04-12")
    await tugas_gudang(db, "trn_pk31_8", p8, a, b, [("roll_pk31_8", 1000.0)], "2027-04-12")
    await db.inventory_rolls.insert_one(roll("roll_pk31_8", b, 1000.0, 50_000,
                                             [unsur_rantai(p8, a, b, 50_000, 60_000, "2027-04-12")]))
    st = await eng.pair_state(p8, "2027-06-30")
    # (50 − 60) × 1 = −10 jt → rugi tidak dieliminasi: urp = max(−10, 0) = 0.
    assert (st["revenue"], st["cogs"], st["urp"]) == (50 * JT, 60 * JT, 0)
    e = await eng.period_entry(p8, "2027-04")
    assert baris(e) == {("4-1000", 50 * JT, 0), ("5-1000", 0, 50 * JT), ("2-1250", 50 * JT, 0), ("1-1250", 0, 50 * JT)}
    assert not [x for x in e["lines"] if x["account_code"] in ("1-1300", "1-1310")]
    rap = await icm.margin_report(entity_id=a, as_of="2027-06-30")
    row = next(x for x in rap["rows"] if x["pair_id"] == p8)
    assert (row["unrealized_loss"], row["eliminated_unrealized"], row["elimination_gap"]) == (10 * JT, 0, 0)


# ── U8: bulan beku tidak ditimpa ──────────────────────────────────────────────────────────────────────────────────────
async def test_PK31_U8_bulan_beku_dan_stale(db, data_p1):
    eng = mesin()
    d, e_ = await pt("DDD"), await pt("EEE")   # A dan B uji ini (PT sendiri supaya penutupan tidak meluas)
    p5 = "pk31_p5"
    await db.interco_transactions.insert_many(pasangan(p5, d, e_, 30 * JT, status="confirmed", tanggal="2026-12-10"))
    await jurnal_jual(p5, d, e_, 30 * JT, "2026-12-10")
    tutup = [await tutup_periode(d, "2026-12"), await tutup_periode(e_, "2026-12")]
    try:
        r1 = await eng.sync_period("2026-12")
        simpan = await db.intercompany_eliminations.find_one({"source_g6_pair_id": p5, "period_key": "2026-12"},
                                                             {"_id": 0})
        assert simpan and simpan["frozen"] is True, r1
        assert baris(simpan) == {("4-1000", 30 * JT, 0), ("1-1310", 0, 30 * JT),
                                 ("2-1250", 30 * JT, 0), ("1-1250", 0, 30 * JT)}
        # FIXTURE: jurnal mundur ke Des (sisip langsung — periode tertutup) menambah pendapatan pasangan 5 jt.
        await db.journal_entries.insert_one({
            "id": "je_pk31_mundur", "number": "JE-PK31-MUNDUR", "date": "2026-12-20", "status": "posted",
            "entity_id": d, "source_type": "interco_transaction", "source_id": f"{p5}:adj:seller",
            "lines": [{"account_code": "1-1250", "debit": 5 * JT, "credit": 0},
                      {"account_code": "4-1000", "debit": 0, "credit": 5 * JT}],
            "total_debit": 5 * JT, "total_credit": 5 * JT, "created_at": now_iso()})
        r2 = await eng.sync_period("2026-12")
        sesudah = await db.intercompany_eliminations.find_one({"source_g6_pair_id": p5, "period_key": "2026-12"},
                                                              {"_id": 0})
        assert sesudah["frozen"] is True and baris(sesudah) == baris(simpan)
        assert sesudah.get("updated_at") == simpan.get("updated_at")
        assert any(s["pair_id"] == p5 and s["period_key"] == "2026-12" for s in r2["stale"]), r2
        hitung = await eng.period_entry(p5, "2026-12")
        assert ("4-1000", 35 * JT, 0) in baris(hitung)   # hitung ulang memang berbeda (35 jt)
    finally:
        for c in tutup:
            await db.period_closings.delete_one({"id": c["id"]})
        await db.journal_entries.delete_one({"id": "je_pk31_mundur"})


# ── U9: persen kepemilikan (K-10) ────────────────────────────────────────────────────────────────────────────────────
async def test_PK31_U9_bagian_non_pengendali(klien, akun, sesi, peran_tanpa_acuan, db):
    f, g = await pt("FFF"), await pt("GGG")   # A dan B uji ini; tanpa transaksi antar-PT
    await db.business_entities.update_one({"id": g}, {"$set": {"ownership_pct": 80}})
    await je(f, "2027-01-02", [("1-1100", 170 * JT, 0), ("3-1000", 0, 170 * JT)], "uji", "pk31_u9_modal_f")
    await je(f, "2027-02-01", [("1-1100", 30 * JT, 0), ("4-1000", 0, 30 * JT)], "uji", "pk31_u9_laba_f")
    await je(g, "2027-01-02", [("1-1100", 40 * JT, 0), ("3-1000", 0, 40 * JT)], "uji", "pk31_u9_modal_g")
    await je(g, "2027-02-01", [("1-1100", 10 * JT, 0), ("4-1000", 0, 10 * JT)], "uji", "pk31_u9_laba_g")
    p = await peran_tanpa_acuan({"accounting": ["view"]}, label="Konsolidasi FG PK31")
    h = await sesi(await akun(p, entitas=(f, g)), entitas=f)
    s = await _ringkasan(klien, h, 2027, "2027-12-31")
    rows = {r["entity_id"]: r for r in s["entities"]}
    assert (rows[f]["ownership_pct"], rows[g]["ownership_pct"]) == (100, 80)
    assert (rows[f]["net_income"], rows[g]["net_income"], rows[f]["equity"], rows[g]["equity"]) == \
        (30 * JT, 10 * JT, 200 * JT, 50 * JT)
    k = s["consolidated"]
    # NCI laba = 10 jt × 20 % = 2 jt; NCI ekuitas = 50 jt × 20 % = 10 jt; induk = 40 − 2 = 38 jt; 250 − 10 = 240 jt.
    assert (k["nci_net_income"], k["nci_equity"]) == (2 * JT, 10 * JT)
    assert (k["net_income_parent"], k["equity_parent"]) == (38 * JT, 240 * JT)


# ── U10–U13: retur setelah lunas → utang refund ──────────────────────────────────────────────────────────────────────
RF = "pk31_rf"


@pytest.fixture(scope="module")
async def data_rf(klien, kepala_admin, db):
    s, b = await pt("RFS"), await pt("RFB")
    await db.bank_accounts.insert_many([
        {"id": "rek_pk31_s", "name": "Bank RFS", "entity_id": s, "account_type": "bank", "cash_type": "kas_besar",
         "is_active": True},
        {"id": "rek_pk31_b", "name": "Bank RFB", "entity_id": b, "account_type": "bank", "cash_type": "kas_besar",
         "is_active": True}])
    docs = pasangan(RF, s, b, 10 * JT, status="draft", tanggal="2026-11-02", nomor="RFS/IC-RF")
    for d in docs:
        d["items"] = []
        d.pop("gl_status", None)
    await db.interco_transactions.insert_many(docs)
    # ALUR: konfirmasi lalu pelunasan penuh lewat API (PK-06).
    r = await klien.post(f"/api/interco/transactions/{RF}_s/confirm", headers=kepala_admin, json={"note": ""})
    assert r.status_code == 200 and not r.json().get("warning"), r.text
    r = await klien.post("/api/interco/settlements", headers={**kepala_admin, "X-Entity-Id": b}, json={
        "payer_entity_id": b, "payee_entity_id": s, "transactions": [{"interco_id": f"{RF}_s"}],
        "settle_date": "2026-11-05", "method": "transfer", "bank_account_id": "rek_pk31_b"})
    assert r.status_code == 200, r.text
    assert {d["status"] async for d in db.interco_transactions.find({"pair_id": RF})} == {"settled"}
    return s, b


def retur_fixture(rp, origin, s, b, total):
    base = {"return_pair_id": rp, "pair_id": rp, "origin_pair_id": origin, "origin_number": "RFS/IC-RF",
            "seller_entity_id": s, "buyer_entity_id": b, "seller_entity_name": "PT RFS", "buyer_entity_name": "PT RFB",
            "subtotal": total, "tax_apply": False, "tax_rate": 0.0, "tax_amount": 0.0, "grand_total": total,
            "status": "draft", "items": [], "timeline": [], "created_by": "Orang Lain", "created_at": now_iso()}
    return [{**base, "id": f"{rp}_ret", "role": "returner", "entity_id": b, "number": f"RB/{rp}"},
            {**base, "id": f"{rp}_rcv", "role": "receiver", "entity_id": s, "number": f"RK/{rp}"}]


async def _saldo_ica(klien, h, penjual, pembeli):
    r = await klien.get("/api/interco/accounts", headers=h)
    assert r.status_code == 200, r.text
    return next(x for x in r.json() if x.get("role") == "receivable" and x.get("seller_entity_id") == penjual
                and x.get("buyer_entity_id") == pembeli)


async def test_PK31_U10_retur_setelah_lunas_menjadi_utang_refund(klien, kepala_admin, db, data_rf):
    from services import interco_return_service as icret
    s, b = data_rf
    await db.interco_returns.insert_many(retur_fixture("pk31_rp", RF, s, b, 4 * JT))
    await icret.approve("pk31_rp_ret", AKTOR_UJI)   # ALUR: setujui retur (pembuat "Orang Lain" ≠ penyetuju)
    js = {j["source_id"]: baris(j) for j in await db.journal_entries.find(
        {"source_type": "interco_return", "source_id": {"$regex": "^pk31_rp:"}}, {"_id": 0}).to_list(5)}
    assert js == {"pk31_rp:seller": {("4-1000", 4 * JT, 0), ("1-1250", 0, 4 * JT)},
                  "pk31_rp:buyer": {("2-1250", 4 * JT, 0), ("1-1310", 0, 4 * JT)}}
    # refund_due = max(0, retur 4 jt + lunas 10 jt − nilai 10 jt) = 4 jt, pada KEDUA dokumen kembar.
    docs = await db.interco_transactions.find({"pair_id": RF}, {"_id": 0}).to_list(2)
    assert [d.get("refund_due") for d in docs] == [4 * JT, 4 * JT], docs
    row = await _saldo_ica(klien, {**kepala_admin, "X-Entity-Id": s}, s, b)
    assert (row["outstanding"], row["refund_outstanding"]) == (0, 4 * JT), row
    # Saldo 1-1250 A: konfirmasi +10 − pelunasan 10 − retur 4 = −4 jt = −refund_outstanding.
    assert await neto(db, s, "1-1250") == -row["refund_outstanding"]


async def _refund(klien, h, s, b, *, key=None, jumlah_rp=None, tanggal="2026-11-10", rek="rek_pk31_s"):
    hh = {**h, "X-Entity-Id": s}
    if key:
        hh["Idempotency-Key"] = key
    pick = {"interco_id": f"{RF}_s"}
    if jumlah_rp is not None:
        pick["applied_amount"] = jumlah_rp
    return await klien.post("/api/interco/refunds", headers=hh, json={
        "payer_entity_id": s, "payee_entity_id": b, "transactions": [pick], "settle_date": tanggal,
        "method": "transfer", "bank_account_id": rek, "notes": "uji PK-31"})


async def test_PK31_U12_melebihi_sisa_dan_bukan_cakupan(klien, kepala_admin, akun, sesi, peran_tanpa_acuan, db,
                                                       data_rf):
    s, b = data_rf
    r = await _refund(klien, kepala_admin, s, b, jumlah_rp=5 * JT)
    assert r.status_code == 400 and "melebihi sisa pengembalian dana" in r.text, r.text
    p = await peran_tanpa_acuan({"interco": ["view", "settle"], "interco_finance": ["view"]}, label="Refund B PK31")
    h_b = await sesi(await akun(p, entitas=(b,)), entitas=b)
    r = await klien.post("/api/interco/refunds", headers=h_b, json={
        "payer_entity_id": s, "payee_entity_id": b, "transactions": [{"interco_id": f"{RF}_s"}],
        "settle_date": "2026-11-10", "method": "transfer"})
    assert r.status_code == 403 and "mencatat pengembalian dana" in r.text, r.text
    r = await _refund(klien, kepala_admin, s, s)
    assert r.status_code == 400 and "berbeda" in r.text, r.text
    assert {float(d.get("refund_paid") or 0) async for d in db.interco_transactions.find({"pair_id": RF})} == {0.0}


async def test_PK31_U13_periode_pembeli_tertutup(klien, kepala_admin, db, data_rf):
    s, b = data_rf
    c = await tutup_periode(b, "2026-11")
    try:
        r = await _refund(klien, kepala_admin, s, b, key="pk31-u13")
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409 and re.search("ditutup", r.text, re.I), r.text
    assert {float(d.get("refund_paid") or 0) async for d in db.interco_transactions.find({"pair_id": RF})} == {0.0}
    assert await jumlah("interco_settlements", {"kind": "refund"}) == 0
    assert await jumlah("cash_transactions", {"entity_id": s, "direction": "out", "ref_type": "interco_settlement",
                                              "category": {"$regex": "pengembalian dana"}}) == 0
    assert await jumlah("journal_entries", {"entity_id": s, "source_type": "interco_settlement", "lines": {
        "$elemMatch": {"account_code": "1-1250", "debit": {"$gt": 0}}}}) == 0


async def test_PK31_U11_refund_dicatat_sekali(klien, kepala_admin, db, data_rf):
    s, b = data_rf
    r = await _refund(klien, kepala_admin, s, b, key="pk31-u11")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["kind"] == "refund" and out["status"] == "posted" and out["refund_outstanding"] == 0, out
    sid = out["id"]
    js = {j["source_id"]: (j["entity_id"], baris(j)) for j in await db.journal_entries.find(
        {"source_type": "interco_settlement", "source_id": {"$regex": f"^{sid}:"}}, {"_id": 0}).to_list(5)}
    assert js == {f"{sid}:payer": (s, {("1-1250", 4 * JT, 0), ("1-1100", 0, 4 * JT)}),
                  f"{sid}:payee": (b, {("1-1100", 4 * JT, 0), ("2-1250", 0, 4 * JT)})}
    kas = await db.cash_transactions.find({"ref_id": sid}, {"_id": 0}).to_list(5)
    assert sorted((k["entity_id"], k["direction"], k["amount"]) for k in kas) == sorted(
        [(s, "out", 4 * JT), (b, "in", 4 * JT)])
    assert next(k for k in kas if k["direction"] == "out")["account_id"] == "rek_pk31_s"
    docs = await db.interco_transactions.find({"pair_id": RF}, {"_id": 0}).to_list(2)
    assert [d["refund_paid"] for d in docs] == [4 * JT, 4 * JT]
    assert await neto(db, s, "1-1250") == 0 and await neto(db, b, "2-1250") == 0
    row = await _saldo_ica(klien, {**kepala_admin, "X-Entity-Id": s}, s, b)
    assert (row["outstanding"], row["refund_outstanding"]) == (0, 0)
    ulang = await _refund(klien, kepala_admin, s, b, key="pk31-u11")       # kunci sama → jawaban sama, tanpa tulisan
    assert ulang.status_code == 200 and ulang.json()["id"] == sid
    r2 = await _refund(klien, kepala_admin, s, b, key="pk31-u11-lagi")     # permintaan baru → tidak ada sisa
    assert r2.status_code == 409 and "tidak punya sisa pengembalian dana" in r2.text, r2.text
    assert await jumlah("interco_settlements", {"kind": "refund"}) == 1
    assert await jumlah("cash_transactions", {"ref_id": sid}) == 2


# ── U14: skrip migrasi (database tiruan = data acuan uji; data nyata = H3) ──────────────────────────────────────────
def _skrip():
    import importlib.util
    from pathlib import Path
    jalur = Path(__file__).resolve().parents[2] / "scripts" / "migrasi_pk31_eliminasi_per_periode.py"
    spec = importlib.util.spec_from_file_location("migrasi_pk31", jalur)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_PK31_U14_skrip_migrasi(db, data_p1, capsys):
    a, b = data_p1
    if not await db.shipments.find_one({"id": "shp_pk31_1"}):
        pytest.fail("butuh surat jalan U4/U5")
    # FIXTURE: entri lama SATU per pasangan tanpa period_key, seperti yang ditulis sinkron lama saat barang diterima
    # (u = 1): Dr 4-1000 100 · Cr 5-1000 60 · Cr 1-1300 40 · Dr 2-1250 100 · Cr 1-1250 100, efektif 28 Des 2026.
    await db.intercompany_eliminations.delete_many({"source_g6_pair_id": P1})
    lama = [("4-1000", 100 * JT, 0), ("5-1000", 0, 60 * JT), ("1-1300", 0, 40 * JT), ("2-1250", 100 * JT, 0),
            ("1-1250", 0, 100 * JT)]
    await db.intercompany_eliminations.insert_one({
        "id": "icelim_pk31_lama", "name": "Eliminasi otomatis antar-PT AAA/IC-P1", "entity_from": a, "entity_to": b,
        "effective_date": "2026-12-28", "auto_generated": True, "source_g6_pair_id": P1,
        "lines": [{"account_code": k, "debit": d, "credit": c} for k, d, c in lama],
        "total_debit": 200 * JT, "total_credit": 200 * JT, "balanced": True,
        "impact": {"revenue": -100 * JT, "cogs": -60 * JT, "opex": 0, "assets": -140 * JT, "liabilities": -100 * JT,
                   "equity": 0}, "created_at": now_iso()})
    skrip = _skrip()
    assert await skrip.jalankan([], db=db) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():   # cetakan untuk laporan (pytest -s): wajib dilihat pemilik sebelum (b) digabung
        print("\n=== CETAKAN SKRIP MIGRASI PK-31 (baca-saja) ===\n" + keluar)
    blok = keluar.split(f"({P1})", 1)[1].split("\nPasangan ", 1)[0]
    # Dampak laba-rugi P1. Lama: 2026 = −100 + 60 = −40 jt; 2027 = 0. Baru: Des −100; Jan +60; Mar +20 (500 m terjual
    # 15 Mar, U4) → 2026 −100 jt, 2027 +80 jt. Selisih 2026 = −60 jt; 2027 = +80 jt (spesifikasi menulis +60 jt —
    # itu angka TANPA surat jalan Maret; lihat "Usulan koreksi" di laporan PK-31).
    assert re.search(r"2026: lama -40\.000\.000 · baru -100\.000\.000 · selisih -60\.000\.000", blok), blok
    assert re.search(r"2027: lama 0 · baru 80\.000\.000 · selisih \+80\.000\.000", blok), blok
    assert await db.intercompany_eliminations.find_one({"id": "icelim_pk31_lama"})   # baca-saja: tidak berubah
    assert await skrip.jalankan(["--apply"], db=db) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():
        print("\n=== --apply ===\n" + keluar.splitlines()[-1])
    assert not await db.intercompany_eliminations.find_one({"source_g6_pair_id": P1, "period_key": {"$exists": False}})
    bulan = sorted([e["period_key"] async for e in db.intercompany_eliminations.find(
        {"source_g6_pair_id": P1, "period_key": {"$exists": True}}, {"_id": 0})])
    assert bulan == ["2026-12", "2027-01", "2027-03"]
    assert await skrip.jalankan(["--apply"], db=db) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():
        print("\n=== --apply (jalan ketiga) ===\n" + keluar.splitlines()[-1])
    assert "Tanpa perubahan" in keluar, keluar[-1500:]


# ── Serah-terima (b): pemanggil dialihkan, indeks unik, invarian ─────────────────────────────────────────────────────
async def test_PK31_b_kait_transaksi_menulis_entri_per_bulan(db, data_p1):
    # ALUR (U6): `on_warehouse_task_executed` → `_sync_group_elimination` → `sync_period(pair_id)`.
    rows = [e async for e in db.intercompany_eliminations.find({"source_g6_pair_id": "pk31_p6"}, {"_id": 0})]
    assert rows and all(e.get("period_key") for e in rows), rows
    assert sorted(e["period_key"] for e in rows) == ["2027-04"]
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in rows[0]["lines"]} == {
        ("4-1000", 100 * JT, 0), ("5-1000", 0, 60 * JT), ("1-1300", 0, 40 * JT), ("2-1250", 100 * JT, 0),
        ("1-1250", 0, 100 * JT)}
    from services import consolidation_service as cons   # tombol "Sinkron Antar-PT" = pembangun ulang yang sama
    r = await cons.sync_g6_ic_eliminations(as_of="2027-06-30")
    assert r["created"] + r["updated"] == 0 and r["pairs_seen"] >= 5, r


async def test_PK31_b_indeks_unik_terdaftar():
    import indexes
    it = next(x for x in indexes.REQUIRED_UNIQUE_INDEXES
              if (x["collection"], x["name"]) == ("intercompany_eliminations", "uq_pair_period"))
    assert it["keys"] == [("source_g6_pair_id", 1), ("period_key", 1)]
    assert set(it["partial"]) == {"source_g6_pair_id", "period_key"}


def _vdi():
    import importlib
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("verify_data_integrity")


async def _inv_ic(db, capsys):
    await _vdi().layer_interco_invariants(db)
    return re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)


def _baris_inv(keluar, kode):
    return [x for x in keluar.splitlines() if kode in x and ("[PASS]" in x or "[FAIL]" in x)]


async def test_PK31_b_invarian_ic03_ic04(db, data_p1, data_rf, capsys):
    from services import interco_elimination_engine as eng
    from services import interco_service as ics
    # Pembangun ulang saldo pasangan PT untuk fixture yang disisip langsung (D2).
    async for s in db.interco_transactions.find({"role": "seller"}, {"_id": 0}):
        await ics._update_account_balance(s["seller_entity_id"], s["buyer_entity_id"])
    await eng.sync_period()
    keluar = await _inv_ic(db, capsys)
    for kode in ("INV-IC-03", "INV-IC-04"):
        b = _baris_inv(keluar, kode)
        assert b and "[PASS]" in b[0], keluar[-3000:]
    # INV-IC-04 merah: refund_paid dokumen penjual digeser (FIXTURE) → refund_outstanding & 1-1250 tidak cocok.
    await db.interco_transactions.update_one({"id": f"{RF}_s"}, {"$set": {"refund_paid": 3 * JT}})
    try:
        b = _baris_inv(await _inv_ic(db, capsys), "INV-IC-04")
        assert b and "[FAIL]" in b[0] and "refund_outstanding" in b[0], b
    finally:
        await db.interco_transactions.update_one({"id": f"{RF}_s"}, {"$set": {"refund_paid": 4 * JT}})
    # INV-IC-03 merah: entri bulan beku berbeda dari hitung ulang (jurnal mundur FIXTURE).
    d, e_ = await pt("DDD"), await pt("EEE")
    tutup = [await tutup_periode(d, "2026-12"), await tutup_periode(e_, "2026-12")]
    try:
        await eng.sync_period("2026-12", pair_id="pk31_p5")
        await db.journal_entries.insert_one({
            "id": "je_pk31_mundur2", "number": "JE-PK31-MUNDUR2", "date": "2026-12-20", "status": "posted",
            "entity_id": d, "source_type": "interco_transaction", "source_id": "pk31_p5:adj:seller",
            "lines": [{"account_code": "1-1250", "debit": 5 * JT, "credit": 0},
                      {"account_code": "4-1000", "debit": 0, "credit": 5 * JT}],
            "total_debit": 5 * JT, "total_credit": 5 * JT, "created_at": now_iso()})
        b = _baris_inv(await _inv_ic(db, capsys), "INV-IC-03")
        assert b and "[FAIL]" in b[0] and "beku" in b[0], b
    finally:
        for c in tutup:
            await db.period_closings.delete_one({"id": c["id"]})
        await db.journal_entries.delete_one({"id": "je_pk31_mundur2"})
        await eng.sync_period(pair_id="pk31_p5")
