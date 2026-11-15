"""PK-43 — Empat alur layar keuangan diselesaikan tanpa pindah menu (docs/blueprint/unit/PK-43.md, uji U1–U3, U5–U14).

Lapis B (database tiruan). Persiapan = FIXTURE (disisipkan langsung ke database), kecuali permintaan yang diuji:
  * transaksi antar-PT terbuka `ICT-1` (`ent_ksc` penjual → `ent_kanda` pembeli) total 22.200.000, `settled_amount`
    5.000.000 (dokumen kembar penjual + pembeli); rekening `ba_ksc` milik `ent_ksc`, `ba_kanda` milik `ent_kanda`;
  * jurnal akun `6-2000` di PT uji `PK43L` (U5–U7) lewat `gl_service._insert_entry`;
  * tagihan pemasok `vb1` + jurnalnya, jurnal manual, surat jalan PT lain (U8–U9);
  * daftar periksa tutup buku (U10–U14) di PT uji masing-masing; "hari ini" dibekukan 14 November 2026
    (`closing_service._today_wib`).
"""
from __future__ import annotations

import pytest

from core_utils import now_iso
from pembantu import jumlah, jurnal, pt_uji as _pt_uji
from services import closing_service as cs
from services import gl_service as gl

pytestmark = pytest.mark.anyio

JT = 1_000_000
KSC, KANDA = "ent_ksc", "ent_kanda"
HARI_INI = "2026-11-14"
CEKLIS = "/api/finance/closing/checklist"


async def pt_uji(kode: str) -> str:
    """PT uji + cache status PT dibuang (fixture disisip langsung; cache 20 detik)."""
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji(kode)
    invalidate_status_cache()
    return eid


def pasangan(pid, penjual, pembeli, total, lunas=0.0, status="confirmed", nomor=""):
    base = {"pair_id": pid, "seller_entity_id": penjual, "buyer_entity_id": pembeli,
            "seller_entity_name": "PT Penjual", "buyer_entity_name": "PT Pembeli", "subtotal": total,
            "tax_amount": 0.0, "grand_total": total, "settled_amount": lunas, "returned_amount": 0.0,
            "status": status, "items": [], "timeline": [], "doc_date": "2026-10-05", "due_date": "2026-11-04",
            "created_at": "2026-10-05T03:00:00+00:00", "created_by": "uji"}
    no = nomor or f"S/{pid}"
    return [{**base, "id": f"{pid}_s", "number": no, "role": "seller", "entity_id": penjual,
             "counterpart_id": f"{pid}_b", "counterpart_number": f"B/{pid}"},
            {**base, "id": f"{pid}_b", "number": f"B/{pid}", "role": "buyer", "entity_id": pembeli,
             "counterpart_id": f"{pid}_s", "counterpart_number": no}]


@pytest.fixture(scope="module")
async def siap(db):
    await db.bank_accounts.insert_many([
        {"id": "ba_ksc", "name": "Bank KSC", "entity_id": KSC, "account_type": "bank", "cash_type": "kas_besar",
         "is_active": True},
        {"id": "ba_kanda", "name": "Bank Kanda", "entity_id": KANDA, "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True}])
    await db.interco_transactions.insert_many(pasangan("ict1", KSC, KANDA, 22_200_000, 5 * JT, nomor="ICT-1"))
    return True


def _hari_ini(monkeypatch, tanggal: str = HARI_INI) -> None:
    monkeypatch.setattr(cs, "_today_wib", lambda: tanggal, raising=False)


# ── (1) Kandidat pelunasan antar-PT ─────────────────────────────────────────────────────────────────────────────────
async def test_PK43_U1_pembayar_melihat_tagihan_terbuka(klien, akun, sesi, siap, peran_tanpa_acuan):
    # 22.200.000 − 5.000.000 (sudah dilunasi) − 0 (retur) = 17.200.000
    rid = await peran_tanpa_acuan({"interco_finance": ["view"]}, label="PK43 Keuangan Antar-PT")
    h = await sesi(await akun(rid, entitas=(KANDA,)), entitas=KANDA)
    r = await klien.get("/api/interco/payment-schedule", headers=h,
                        params={"payer_entity_id": KANDA, "payee_entity_id": KSC})
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert [x["number"] for x in rows] == ["ICT-1"]
    assert rows[0]["outstanding"] == 17_200_000
    assert rows[0]["settleable"] is True


async def test_PK43_U2_pt_ketiga_ditolak(klien, akun, sesi, siap, peran_tanpa_acuan):
    ketiga = await pt_uji("PK43X")
    rid = await peran_tanpa_acuan({"interco_finance": ["view"]}, label="PK43 Keuangan PT Ketiga")
    h = await sesi(await akun(rid, entitas=(ketiga,)), entitas=ketiga)
    r = await klien.get("/api/interco/payment-schedule", headers=h,
                        params={"payer_entity_id": KANDA, "payee_entity_id": KSC})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Anda tidak ditugaskan di salah satu PT pada pasangan ini."


async def test_PK43_U3_rekening_bukan_milik_pembayar(klien, kepala_admin, siap):
    sebelum = await jumlah("interco_settlements", {})
    r = await klien.post("/api/interco/settlements", headers={**kepala_admin, "X-Entity-Id": KANDA,
                                                              "Idempotency-Key": "pk43-u3"},
                         json={"payer_entity_id": KANDA, "payee_entity_id": KSC, "method": "transfer",
                               "settle_date": "2026-11-10", "bank_account_id": "ba_ksc",
                               "transactions": [{"interco_id": "ict1_s", "applied_amount": 17_200_000}]})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Rekening bukan milik PT pembayar."
    assert await jumlah("interco_settlements", {}) == sebelum


# ── (2) Telusur laporan → akun → jurnal → dokumen ───────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def buku(siap):
    eid = await pt_uji("PK43L")
    await jurnal(eid, "2026-09-20", [("6-2000", 30, 0), ("1-1100", 0, 30)], "sewa September", "pk43_sep")
    await jurnal(eid, "2026-10-05", [("6-2000", 50, 0), ("1-1100", 0, 50)], "sewa Oktober", "pk43_okt")
    await jurnal(eid, "2026-10-20", [("1-1100", 10, 0), ("6-2000", 0, 10)], "koreksi sewa", "pk43_kor")
    return eid


async def test_PK43_U5_buku_besar_berentang_bersaldo_awal(klien, kepala_admin, buku):
    # saldo awal = saldo sebelum 1 Okt = Dr 30 (akun beban, saldo normal debit) → 30;
    # mutasi Okt: Dr 50, Cr 10 → saldo akhir 30 + 50 − 10 = 70.
    r = await klien.get("/api/gl/accounts/6-2000/ledger", headers={**kepala_admin, "X-Entity-Id": buku},
                        params={"start": "2026-10-01", "as_of": "2026-10-31"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["opening_balance"] == 30
    assert len(j["lines"]) == 2
    assert j["total_debit"] == 50 and j["total_credit"] == 10
    assert j["balance"] == 70
    assert j["period"] == {"start": "2026-10-01", "end": "2026-10-31"}
    # baris terbaru dulu; saldo berjalan berangkat dari saldo awal: 30 + 50 = 80, lalu 80 − 10 = 70
    assert [ln["running_balance"] for ln in j["lines"]] == [70, 80]
    assert {ln["source_id"] for ln in j["lines"]} == {"pk43_okt", "pk43_kor"}


async def test_PK43_U6_tanpa_start_seperti_sebelumnya(klien, kepala_admin, buku):
    # 30 + 50 − 10 = 70, tiga baris, tanpa saldo awal
    r = await klien.get("/api/gl/accounts/6-2000/ledger", headers={**kepala_admin, "X-Entity-Id": buku})
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["lines"]) == 3 and j["balance"] == 70
    assert "opening_balance" not in j


async def test_PK43_U7_daftar_jurnal_disaring_tanggal(klien, kepala_admin, buku):
    # jurnal yang menyentuh 6-2000 di Oktober: 5 Okt dan 20 Okt → 2 (jurnal 20 Sep di luar rentang)
    r = await klien.get("/api/gl/journal", headers={**kepala_admin, "X-Entity-Id": buku},
                        params={"account_code": "6-2000", "start": "2026-10-01", "end": "2026-10-31", "page": 1})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 2


async def test_PK43_U8_dokumen_sumber_jurnal(klien, db, kepala_admin, siap):
    await db.vendor_bills.insert_one({"id": "vb1", "bill_number": "KSC/VB-UJI43", "entity_id": KSC,
                                      "supplier_name": "Pemasok PK43", "grand_total": 1_110_000, "status": "posted",
                                      "created_at": now_iso()})
    je_vb = await gl._insert_entry(lines=[{"account_code": "1-1300", "debit": 1_000_000, "credit": 0},
                                          {"account_code": "2-1100", "debit": 0, "credit": 1_000_000}],
                                   description="tagihan pemasok uji", date="2026-10-12", source_type="vendor_bill",
                                   source_id="vb1", entity_id=KSC, created_by="uji")
    je_man = await gl._insert_entry(lines=[{"account_code": "6-2000", "debit": 5, "credit": 0},
                                           {"account_code": "1-1100", "debit": 0, "credit": 5}],
                                    description="jurnal manual uji", date="2026-10-12", source_type="manual",
                                    source_id="", entity_id=KSC, created_by="uji")
    h = {**kepala_admin, "X-Entity-Id": KSC}
    a = (await klien.get(f"/api/gl/journal/{je_vb['id']}", headers=h)).json()
    assert a["source_doc"]["doc_type"] == "vendor_bill"
    assert a["source_doc"]["number"] == "KSC/VB-UJI43"
    assert a["source_doc"]["link"]["focus_id"] == "vb1"
    assert a["source_doc"]["link"]["view"] == "vendor-bills"
    b = (await klien.get(f"/api/gl/journal/{je_man['id']}", headers=h)).json()
    assert b["source_doc"] is None


async def test_PK43_U9_dokumen_sumber_di_luar_pt_pelaku(klien, db, akun, sesi, siap, peran_tanpa_acuan):
    await db.shipments.insert_one({"id": "shp_pk43", "shipment_no": "KSC/SJ-UJI43", "entity_id": KSC,
                                   "order_id": "so_pk43", "status": "delivered", "created_at": now_iso()})
    baris = [{"account_code": "1-1200", "debit": 7, "credit": 0}, {"account_code": "4-1000", "debit": 0, "credit": 7}]
    # jurnal terbaca (buku `ent_kanda`), dokumennya milik `ent_ksc` → tautan dikosongkan
    je_baca = await gl._insert_entry(lines=baris, description="pendapatan kirim uji", date="2026-10-14",
                                     source_type="shipment_revenue", source_id="shp_pk43", entity_id=KANDA,
                                     created_by="uji")
    # `source_id` berakhiran lain: jurnal otomatis idempoten per (jenis, sumber)
    je_luar = await gl._insert_entry(lines=baris, description="pendapatan kirim uji", date="2026-10-14",
                                     source_type="shipment_revenue", source_id="shp_pk43:ksc", entity_id=KSC,
                                     created_by="uji")
    assert je_luar["entity_id"] == KSC
    rid = await peran_tanpa_acuan({"accounting": ["view"]}, label="PK43 Akuntansi Kanda")
    h = await sesi(await akun(rid, entitas=(KANDA,)), entitas=KANDA)
    r = await klien.get(f"/api/gl/journal/{je_baca['id']}", headers=h)
    assert r.status_code == 200, r.text
    sd = r.json()["source_doc"]
    assert sd and sd["number"] == "KSC/SJ-UJI43" and not sd.get("link")
    r = await klien.get(f"/api/gl/journal/{je_luar['id']}", headers=h)
    assert r.status_code == 404, r.text


# ── (4) Daftar periksa tutup buku ───────────────────────────────────────────────────────────────────────────────────
def _butir(j, key):
    hit = [it for it in j["items"] if it["key"] == key]
    assert hit, f"butir {key} tidak ada: {[it['key'] for it in j['items']]}"
    return hit[0]


async def _ceklis(klien, h, eid, period_key="2026-10", period_type="month"):
    r = await klien.get(CEKLIS, headers={**h, "X-Entity-Id": eid},
                        params={"period_type": period_type, "period_key": period_key, "entity_id": eid})
    assert r.status_code == 200, r.text
    return r.json()


async def test_PK43_U10_ceklis_posting_gagal_hanya_peringatan(klien, db, kepala_admin, monkeypatch):
    _hari_ini(monkeypatch)
    eid = await pt_uji("PK43C")
    await jurnal(eid, "2026-10-08", [("6-2000", 40, 0), ("1-1100", 0, 40)], "beban uji", "pk43c_1")
    await db.cash_transactions.insert_one({"id": "cash_pk43c", "number": "UJI/KAS-43", "entity_id": eid,
                                           "txn_date": "2026-10-15", "amount": 100_000, "direction": "out",
                                           "gl_status": "failed", "gl_error": "uji", "created_at": now_iso()})
    j = await _ceklis(klien, kepala_admin, eid)
    assert j["entity_id"] == eid and j["start_date"] == "2026-10-01" and j["end_date"] == "2026-10-31"
    assert j["period_label"] == "Oktober 2026"
    assert _butir(j, "periode_berakhir")["status"] == "ok"
    assert _butir(j, "suspense_nol")["status"] == "ok"
    pg = _butir(j, "posting_gagal")
    assert pg["status"] == "warning" and pg["value"] == 1
    assert pg["link"]["view"] == "posting-failures"
    assert _butir(j, "neraca_saldo")["status"] == "ok"
    assert j["can_close"] is True
    assert {it["status"] for it in j["items"]} <= {"ok", "warning", "blocking", "unknown"}


async def test_PK43_U11_suspense_menghalangi(klien, kepala_admin, monkeypatch):
    _hari_ini(monkeypatch)
    eid = await pt_uji("PK43S")
    await jurnal(eid, "2026-10-25", [("1-9999", 10 * JT, 0), ("1-1100", 0, 10 * JT)], "kas tak dikenal", "pk43s_1")
    j = await _ceklis(klien, kepala_admin, eid)
    sn = _butir(j, "suspense_nol")
    assert sn["status"] == "blocking" and sn["value"] == 10_000_000
    # MN-T2 — tautan butir ini kini membuka seksi Akun sementara di layar Tutup Buku (dulu tab Suspense di Jurnal).
    assert sn["link"] == {"view": "closing", "preset": {"seksi": "akun-sementara"}}
    assert j["can_close"] is False


async def test_PK43_U12_saldo_antar_pt_buku_vs_dokumen(klien, db, kepala_admin, monkeypatch):
    _hari_ini(monkeypatch)
    jual, beli = await pt_uji("PK43J"), await pt_uji("PK43B")
    await db.interco_transactions.insert_many(pasangan("ict12", jual, beli, 22_200_000, 5 * JT, nomor="ICT-12"))
    # buku penjual: Dr 1-1250 22,2 jt (konfirmasi) lalu Cr 5 jt (pelunasan) → 17,2 jt = sisa dokumen
    await jurnal(jual, "2026-10-05", [("1-1250", 22_200_000, 0), ("4-1000", 0, 22_200_000)], "antar-PT", "ict12_j")
    await jurnal(jual, "2026-10-10", [("1-1100", 5 * JT, 0), ("1-1250", 0, 5 * JT)], "pelunasan", "ict12_l")
    sebelum = _butir(await _ceklis(klien, kepala_admin, jual), "antar_pt_cocok")
    assert sebelum["status"] == "ok", sebelum
    # jurnal Dr piutang antar-PT 1 jt tanpa dokumen → buku 18,2 jt vs dokumen 17,2 jt, selisih 1 jt
    await jurnal(jual, "2026-10-28", [("1-1250", JT, 0), ("4-1000", 0, JT)], "tanpa dokumen", "pk43_tanpa")
    sesudah = _butir(await _ceklis(klien, kepala_admin, jual), "antar_pt_cocok")
    assert sesudah["status"] == "warning", sesudah
    assert sesudah["value"]["gl_receivable"] == 18_200_000
    assert sesudah["value"]["doc_receivable"] == 17_200_000
    assert "1.000.000" in sesudah["detail"]
    assert sesudah["link"]["view"] == "interco-transactions"


async def test_PK43_U13_bulan_berjalan_menghalangi(klien, kepala_admin, monkeypatch):
    _hari_ini(monkeypatch)
    eid = await pt_uji("PK43N")
    j = await _ceklis(klien, kepala_admin, eid, period_key="2026-11")
    assert _butir(j, "periode_berakhir")["status"] == "blocking"
    assert j["can_close"] is False


async def test_PK43_U14_izin_daftar_periksa(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, monkeypatch):
    _hari_ini(monkeypatch)
    eid = await pt_uji("PK43P")
    tanpa = await akun(await peran_tanpa_acuan({"accounting": ["view"]}, label="PK43 Tanpa Acuan"), entitas=(eid,))
    r = await klien.get(CEKLIS, headers=await sesi(tanpa, entitas=eid),
                        params={"period_type": "month", "period_key": "2026-10", "entity_id": eid})
    assert r.status_code == 200, r.text
    kosong = await akun(await peran_manajer_kosong(), entitas=(eid,))
    r = await klien.get(CEKLIS, headers=await sesi(kosong, entitas=eid),
                        params={"period_type": "month", "period_key": "2026-10", "entity_id": eid})
    assert r.status_code == 403, r.text


# ── Tambahan (bentuk jawaban & penolakan yang disebut spesifikasi) ─────────────────────────────────────────────────
URUTAN_BULANAN = ["periode_berakhir", "tidak_bentrok", "suspense_nol", "posting_gagal", "neraca_saldo", "stok_cocok",
                  "bank_cocok", "antar_pt_cocok", "buka_periode_aktif", "penyusutan", "gaji"]


async def test_PK43_tambahan_urutan_butir_dan_tahunan(klien, kepala_admin, monkeypatch):
    _hari_ini(monkeypatch)
    eid = await pt_uji("PK43T")
    j = await _ceklis(klien, kepala_admin, eid)
    assert [it["key"] for it in j["items"]] == URUTAN_BULANAN
    assert _butir(j, "gaji")["status"] == "ok" and _butir(j, "gaji")["detail"] == "Tidak ada penggajian periode ini"
    t = await _ceklis(klien, kepala_admin, eid, period_key="2025", period_type="year")
    assert [it["key"] for it in t["items"]] == URUTAN_BULANAN[:-2]   # penyusutan & gaji hanya bulanan


async def test_PK43_tambahan_semua_pt_dan_periode_tidak_sah(klien, kepala_admin):
    r = await klien.get(CEKLIS, headers={**kepala_admin, "X-Entity-Id": "all"},
                        params={"period_type": "month", "period_key": "2026-10"})
    assert r.status_code == 400 and r.json()["detail"] == "Pilih satu PT untuk melihat daftar periksa tutup buku."
    r = await klien.get(CEKLIS, headers=kepala_admin, params={"period_type": "month", "period_key": "x",
                                                              "entity_id": KSC})
    assert r.status_code == 400, r.text


async def test_PK43_tambahan_butir_gagal_dihitung_tidak_menggagalkan_lainnya(klien, kepala_admin, monkeypatch):
    from services import closing_checklist as ceklis
    _hari_ini(monkeypatch)

    async def _rusak(*a, **kw):
        raise RuntimeError("uji: neraca saldo rusak")
    monkeypatch.setattr(gl, "trial_balance", _rusak)
    eid = await pt_uji("PK43U")
    j = await _ceklis(klien, kepala_admin, eid)
    ns = _butir(j, "neraca_saldo")
    assert ns["status"] == "unknown" and "neraca saldo rusak" in ns["detail"]
    assert _butir(j, "suspense_nol")["status"] == "ok" and len(j["items"]) == len(ceklis.CHECKS)


async def test_PK43_tambahan_kandidat_berjurnal_gagal_tidak_bisa_dilunasi(klien, db, kepala_admin, siap):
    await db.interco_transactions.insert_many(pasangan("ict_gagal", KSC, KANDA, 3 * JT, nomor="ICT-GAGAL"))
    await db.interco_transactions.update_one({"id": "ict_gagal_b"}, {"$set": {"gl_status": "failed"}})
    r = await klien.get("/api/interco/payment-schedule", headers={**kepala_admin, "X-Entity-Id": KANDA},
                        params={"payer_entity_id": KANDA, "payee_entity_id": KSC})
    baris = {x["number"]: x for x in r.json()["rows"]}
    assert baris["ICT-GAGAL"]["settleable"] is False and "Posting Gagal" in baris["ICT-GAGAL"]["settle_block_reason"]
    assert baris["ICT-1"]["settleable"] is True


async def test_PK43_tambahan_jurnal_antar_pt_ke_dokumen_sisinya(klien, kepala_admin, siap):
    # jurnal kembar antar-PT berkunci "{pair_id}:{sisi}" → dokumen pasangan di buku PT jurnal itu (pembeli = B/ict1)
    je = await gl._insert_entry(lines=[{"account_code": "1-1310", "debit": 9, "credit": 0},
                                       {"account_code": "2-1250", "debit": 0, "credit": 9}],
                                description="antar-PT uji", date="2026-10-05", source_type="interco_transaction",
                                source_id="ict1:buyer", entity_id=KANDA, created_by="uji")
    sd = (await klien.get(f"/api/gl/journal/{je['id']}", headers={**kepala_admin, "X-Entity-Id": KANDA})).json()["source_doc"]
    assert sd["doc_id"] == "ict1_b" and sd["number"] == "B/ict1"
    assert sd["link"]["view"] == "interco-transactions" and sd["link"]["focus_id"] == "ict1_b"
