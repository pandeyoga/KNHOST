"""PK-41 serah-terima (a) — dasar hitung laporan pendukung (`services/report_basis.py`), diuji LANGSUNG ke fungsinya.

docs/blueprint/unit/PK-41.md langkah kerja 1: aturan baris tagihan (data U1, U2, U4), `hari_antara` (U13),
`golongan_arus_kas` (jurnal U7, U8), `label_kelompok_umur` (U14), dan `kode_kas` (U9). Laporan lama belum disentuh.

Fixture (disisipkan langsung): pesanan, pelanggan, jurnal pendapatan per surat jalan (`gl_service._insert_entry`
ber-`source_type` `shipment_revenue` + `ref.order_id`), baris `payments[]`. Satuan angka: ribu rupiah. Termin 30 hari
(`payment_term_days` = 30). PT `ent_ksc`.

Hitung tangan:
  U1  pesanan 100; surat jalan 40 tgl 2026-09-01 (Dr 1-1200 40); belum bayar; per 2026-11-15 →
      jatuh tempo 2026-09-01 + 30 = 2026-10-01; lewat 2026-11-15 − 2026-10-01 = 45 hari; sisa 40;
      belum dikirim 100 − 40 − 0 = 60 (tanpa jatuh tempo, lewat 0).
  U2  pesanan 100; bayar 30 tgl 2026-09-01; surat jalan 50 tgl 2026-09-10; per 2026-09-20 →
      baris terkirim 50 − 30 = 20 (jatuh tempo 2026-10-10, lewat −20); belum dikirim 100 − 50 − 0 = 50.
  U4  pesanan 100 terkirim penuh 2026-10-01; bayar 40 (15 Okt) dan 60 (5 Nov); `payment_status` paid.
      per 2026-10-31: terbayar 40 → sisa 60, jatuh tempo 2026-10-31, lewat 0; per 2026-11-10: terbayar 100 → kosong.
  U13 jam dibekukan 2026-11-19 20.00 WIB (= 13.00 UTC) → hari ini WIB 2026-11-19; jatuh tempo 2026-11-20:
      hari_antara(hari ini, jatuh tempo) = 1 dan hari_antara(jatuh tempo, hari ini) = −1.
  U7  jual tunai 300 dan sewa 50 → aturan akun lama (None); `fixed_asset_disposal` (kas 130, 1-2900 20, 1-2100 100,
      4-9100 50) → investing; `interco_loan` Dr kas / Cr 2-1250 → financing (peminjam); Dr 1-1250 / Cr kas →
      investing (pemberi pinjaman); `bank_opening_balance` → saldo_awal.
  U8  `bank_opening_balance` 500 → saldo_awal (bukan pendanaan).
  U9  `kas_bank.kas_besar` dipetakan ke 1-1101 untuk PT uji → 1-1101 termasuk akun kas PT itu (dan 1-1100, 1-1110).
  U14 batas [15, 45, 90] → "Belum jatuh tempo", "1–15 hari", "16–45 hari", "46–90 hari", "> 90 hari".
"""
from __future__ import annotations

import datetime
import uuid

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
RB = 1000   # satuan uji: ribu rupiah


def _id(awal: str) -> str:
    return f"{awal}_pk41a_{uuid.uuid4().hex[:8]}"


async def _pelanggan(db) -> dict:
    c = {"id": _id("cus"), "name": "Toko PK41", "entity_id": KSC, "status": "active", "payment_profile": {},
         "deposit_balance": 0}
    await db.customers.insert_one(dict(c))
    return c


async def _pesanan(db, cus: dict, total: float, *, payments=(), payment_status="unpaid", status="partially_shipped"):
    so = {"id": _id("so"), "number": f"SO-PK41-{uuid.uuid4().hex[:4]}", "entity_id": KSC, "customer_id": cus["id"],
          "customer_name": cus["name"], "status": status, "grand_total": float(total), "total_amount": float(total),
          "payments": [dict(p) for p in payments], "payment_status": payment_status, "payment_term_days": 30,
          "payment_term_code": "NET30", "created_at": "2026-08-25T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    return so


async def _kirim(so: dict, nilai: float, tanggal: str, nomor: str) -> dict:
    """Fixture: jurnal pendapatan satu surat jalan (Dr piutang / Cr pendapatan) seperti `post_shipment_revenue`."""
    from services import gl_service as gl
    shid = _id("sj")
    return await gl._insert_entry(
        lines=[{"account_code": "1-1200", "debit": nilai, "credit": 0.0},
               {"account_code": "4-1000", "debit": 0.0, "credit": nilai}],
        description=f"Pengakuan penjualan {so['number']} · {nomor}", date=tanggal, source_type="shipment_revenue",
        source_id=shid, entity_id=KSC, created_by="uji", source_label=nomor,
        ref={"order_id": so["id"], "order_number": so["number"]})


def _bayar(nilai: float, tanggal: str) -> dict:
    return {"id": _id("pay"), "kind": "kas", "amount": nilai, "method": "transfer", "date": tanggal,
            "created_at": tanggal}


async def _baris(so: dict, cus: dict, per: str) -> list:
    from services.report_basis import baris_tagihan
    return (await baris_tagihan([so], {cus["id"]: cus}, per=per))[so["id"]]


def _ringkas(rows: list) -> list:
    return [(r["sumber"], r["jatuh_tempo"], r["nilai"], r["terbayar"], r["sisa"], r["hari_lewat"]) for r in rows]


# ── U1 — piutang per surat jalan: hanya bagian terkirim yang berumur ─────────────────────────────────────────────────
async def test_PK41_U1_baris_per_surat_jalan(db):
    cus = await _pelanggan(db)
    so = await _pesanan(db, cus, 100 * RB)
    je = await _kirim(so, 40 * RB, "2026-09-01", "SJ-PK41-U1")
    rows = await _baris(so, cus, "2026-11-15")
    assert _ringkas(rows) == [("surat_jalan", "2026-10-01", 40 * RB, 0.0, 40 * RB, 45),
                              ("belum_dikirim", None, 60 * RB, 0.0, 60 * RB, 0)]
    sj = rows[0]
    assert (sj["tanggal"], sj["ref_number"], sj["ref_id"], sj["jurnal_id"]) == (
        "2026-09-01", "SJ-PK41-U1", je["source_id"], je["id"])
    assert rows[1]["ref_id"] == so["id"]


# ── U2 — bayar sebelum kirim: dialokasikan ke surat jalan; sisa pesanan = belum dikirim ─────────────────────────────
async def test_PK41_U2_bayar_dialokasikan_ke_surat_jalan(db):
    cus = await _pelanggan(db)
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(30 * RB, "2026-09-01")], payment_status="partial")
    await _kirim(so, 50 * RB, "2026-09-10", "SJ-PK41-U2")
    rows = await _baris(so, cus, "2026-09-20")
    assert _ringkas(rows) == [("surat_jalan", "2026-10-10", 50 * RB, 30 * RB, 20 * RB, -20),
                              ("belum_dikirim", None, 50 * RB, 0.0, 50 * RB, 0)]
    assert sum(r["sisa"] for r in rows) == 70 * RB


# ── U4 — posisi per tanggal: pembayaran sesudah `per` belum dihitung; status lunas tidak membuang pesanan ────────────
async def test_PK41_U4_posisi_per_tanggal(db):
    cus = await _pelanggan(db)
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(40 * RB, "2026-10-15"), _bayar(60 * RB, "2026-11-05")],
                        payment_status="paid", status="shipped")
    await _kirim(so, 100 * RB, "2026-10-01", "SJ-PK41-U4")
    assert _ringkas(await _baris(so, cus, "2026-10-31")) == [("surat_jalan", "2026-10-31", 100 * RB, 40 * RB, 60 * RB, 0)]
    assert await _baris(so, cus, "2026-11-10") == []


async def test_PK41_U4b_jurnal_sesudah_per_belum_terkirim(db):
    """Surat jalan bertanggal sesudah `per` belum ikut: seluruh pesanan masih "belum dikirim"."""
    cus = await _pelanggan(db)
    so = await _pesanan(db, cus, 100 * RB)
    await _kirim(so, 100 * RB, "2026-10-01", "SJ-PK41-U4B")
    assert _ringkas(await _baris(so, cus, "2026-09-30")) == [("belum_dikirim", None, 100 * RB, 0.0, 100 * RB, 0)]


async def test_PK41_U4c_pesanan_mati_dan_tunai_tidak_ikut(db):
    from services.report_basis import baris_tagihan
    cus = await _pelanggan(db)
    batal = await _pesanan(db, cus, 100 * RB, status="cancelled")
    tunai = await _pesanan(db, cus, 100 * RB)
    await db.sales_orders.update_one({"id": tunai["id"]}, {"$set": {"payment_profile_method": "tunai"}})
    tunai["payment_profile_method"] = "tunai"
    assert await baris_tagihan([batal, tunai], {cus["id"]: cus}, per="2026-11-15") == {}


async def test_PK41_U4d_uang_muka_mengurangi_belum_dikirim(db):
    """Bayar 70 sebelum kirim 30: baris surat jalan lunas (dibuang), uang muka 40 mengurangi belum dikirim 70 → 30."""
    cus = await _pelanggan(db)
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(70 * RB, "2026-09-01")], payment_status="partial")
    await _kirim(so, 30 * RB, "2026-09-05", "SJ-PK41-U4D")
    rows = await _baris(so, cus, "2026-09-30")
    assert _ringkas(rows) == [("belum_dikirim", None, 30 * RB, 0.0, 30 * RB, 0)]
    assert rows[0]["uang_muka"] == 40 * RB


async def test_PK41_U4e_bayar_ke_jatuh_tempo_tertua(db):
    """Dua surat jalan 40 (1 Sep) dan 60 (1 Okt), bayar 50 → SJ pertama lunas, SJ kedua sisa 60 − 10 = 50."""
    cus = await _pelanggan(db)
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(50 * RB, "2026-10-05")], payment_status="partial")
    await _kirim(so, 60 * RB, "2026-10-01", "SJ-PK41-U4E2")
    await _kirim(so, 40 * RB, "2026-09-01", "SJ-PK41-U4E1")
    rows = await _baris(so, cus, "2026-11-15")
    assert _ringkas(rows) == [("surat_jalan", "2026-10-31", 60 * RB, 10 * RB, 50 * RB, 15)]
    assert rows[0]["ref_number"] == "SJ-PK41-U4E2"


# ── U13 — satu penghitung hari, tanggal kalender WIB ────────────────────────────────────────────────────────────────
async def test_PK41_U13_hari_antara_berlawanan_tanda(monkeypatch):
    from services import book_date
    from services.report_basis import hari_antara
    assert hari_antara("2026-11-19", "2026-11-20") == 1
    beku = datetime.datetime(2026, 11, 19, 13, 0, tzinfo=datetime.timezone.utc)   # 20.00 WIB
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)
    hari_ini = book_date.tanggal_buku()
    assert hari_ini == "2026-11-19"
    assert hari_antara(hari_ini, "2026-11-20") == 1
    assert hari_antara("2026-11-20", hari_ini) == -1
    assert hari_antara(None, "2026-11-20") == 1          # kosong = hari ini WIB
    # stempel UTC 18.00 tgl 19 = 01.00 WIB tgl 20 → tanggal kalender WIB yang dipakai, bukan tanggal UTC
    assert hari_antara("2026-11-19T18:00:00+00:00", "2026-11-20") == 0


# ── U7, U8 — golongan arus kas menurut jenis transaksi ──────────────────────────────────────────────────────────────
def _je(st: str, baris) -> dict:
    return {"source_type": st, "lines": [{"account_code": k, "debit": d, "credit": c} for k, d, c in baris]}


async def test_PK41_U7_golongan_arus_kas(aplikasi):
    from services import financial_statement_service as fs
    from services.report_basis import golongan_arus_kas
    amap = await fs._accounts_map({"entity_id": KSC})
    kas = {"1-1100", "1-1110"}
    g = lambda st, b: golongan_arus_kas(_je(st, b), kas, amap)   # noqa: E731
    assert g("sales_order", [("1-1100", 300, 0), ("4-1000", 0, 300)]) is None
    assert g("cash_transaction", [("6-2000", 50, 0), ("1-1100", 0, 50)]) is None
    assert g("fixed_asset_disposal", [("1-1100", 130, 0), ("1-2900", 20, 0), ("1-2100", 0, 100), ("4-9100", 0, 50)]) \
        == "investing"
    assert g("interco_loan", [("1-1100", 500, 0), ("2-1250", 0, 500)]) == "financing"
    assert g("interco_loan", [("1-1250", 500, 0), ("1-1100", 0, 500)]) == "investing"
    assert g("interco_loan_repayment", [("2-1250", 100, 0), ("1-1100", 0, 100)]) == "financing"
    assert g("interco_loan_repayment", [("1-1100", 100, 0), ("1-1250", 0, 100)]) == "investing"
    assert g("bank_opening_balance", [("1-1100", 200, 0), ("3-2900", 0, 200)]) == "saldo_awal"
    # aturan 2 lewat akun: jurnal apa pun yang memuat aset tidak lancar → seluruh kasnya investasi
    assert g("manual", [("1-2100", 70, 0), ("6-2000", 5, 0), ("1-1100", 0, 75)]) == "investing"


async def test_PK41_U8_saldo_awal_bukan_pendanaan(aplikasi):
    from services.report_basis import golongan_arus_kas
    for st in ("bank_opening_balance", "bank_opening_adjustment"):
        assert golongan_arus_kas(_je(st, [("1-1100", 500, 0), ("3-2900", 0, 500)]), {"1-1100"}, {}) == "saldo_awal"


# ── U9 — akun kas dari pemetaan akun, bukan kode ditulis mati ───────────────────────────────────────────────────────
async def test_PK41_U9_kode_kas_dari_pemetaan(db):
    from services import gl_mapping_service as glm
    from services.report_basis import kode_kas
    eid = await pt_uji("P41K")
    if not await db.gl_accounts.find_one({"code": "1-1101"}):
        await db.gl_accounts.insert_one({
            "id": _id("gla"), "code": "1-1101", "name": "Bank Uji PK-41", "type": "asset", "normal_balance": "debit",
            "parent_code": "1-1000", "is_postable": True, "is_active": True, "entity_id": None,
            "created_at": now_iso()})
    assert "1-1101" not in await kode_kas({"entity_id": eid})
    await glm.set_mapping("kas_bank.kas_besar", eid, "1-1101", "uji PK-41 akun bank PT", AKTOR_UJI)
    kas = await kode_kas({"entity_id": eid})
    assert {"1-1100", "1-1101", "1-1110"} <= kas
    assert "1-1101" not in await kode_kas({"entity_id": KSC})   # pemetaan PT lain tidak ikut


# ── U14 — judul kolom umur dari pengaturan ──────────────────────────────────────────────────────────────────────────
def test_PK41_U14_label_kelompok_umur():
    from services.report_basis import label_kelompok_umur
    assert [b["label"] for b in label_kelompok_umur([15, 45, 90])] == [
        "Belum jatuh tempo", "1–15 hari", "16–45 hari", "46–90 hari", "> 90 hari"]
    assert [b["key"] for b in label_kelompok_umur([15, 45, 90])] == ["current", "b1_30", "b31_60", "b61_90", "b90_plus"]
    assert [b["label"] for b in label_kelompok_umur([])] == [
        "Belum jatuh tempo", "1–30 hari", "31–60 hari", "61–90 hari", "> 90 hari"]   # bawaan registri [30, 60, 90]
    # dua batas: kolom ketiga tidak pernah dipakai `_bucket` → tidak dikembalikan
    assert [(b["key"], b["label"]) for b in label_kelompok_umur([14, 30])] == [
        ("current", "Belum jatuh tempo"), ("b1_30", "1–14 hari"), ("b31_60", "15–30 hari"), ("b90_plus", "> 30 hari")]


def test_PK41_U14b_label_sejalan_dengan_kelompok():
    """Label kolom = kolom tempat `_bucket` menaruh hari itu (batas [15, 45, 90])."""
    from services.ar_aging_service import _bucket
    from services.report_basis import label_kelompok_umur
    lab = {b["key"]: b["label"] for b in label_kelompok_umur([15, 45, 90])}
    for hari, label in ((0, "Belum jatuh tempo"), (1, "1–15 hari"), (15, "1–15 hari"), (16, "16–45 hari"),
                        (46, "46–90 hari"), (90, "46–90 hari"), (91, "> 90 hari")):
        assert lab[_bucket(hari, [15, 45, 90])] == label
