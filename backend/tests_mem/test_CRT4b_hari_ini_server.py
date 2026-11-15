"""CR-T4b (T4-01) — "hari ini" akrual denda dari Umur Piutang = tanggal buku server WIB, bukan `?today=` dari klien.

Celah: `POST /api/ar/aging/{customer_id}/accrue-penalties` menerima `?today=` dan meneruskannya ke
`penalty_service.accrue_customer` (hari telat + kunci periode nota) serta ke rincian umur piutang di jawabannya. PK-08
sudah menutup kelas yang sama di `POST /api/payment-plans/{plan_id}/accrue`; celah ini ditemukan saat CR-T4.

FIXTURE (disisip langsung, bentuk D1 CR-T4): PT `ent_kanda`; kunci denda bawaan registry (`ar.denda_rate_pct_per_month`
2, `ar.grace_days` 0, `payment.penalty_mode` `draft`, `payment.penalty_base` `installment`, `payment.penalty_cap_pct` 0,
`payment.penalty_min_amount` 10.000); pelanggan baru per uji; pesanan Rp 5.000.000 NET30 terkirim penuh 1 Sep 2026
(surat jalan + jurnal `shipment_revenue`) → kait CR-T2 membentuk jadwal `term` satu baris 5.000.000 jatuh tempo
2026-10-01. "Hari ini" server dibekukan lewat `book_date._sekarang` (satu-satunya jam hari ini WIB) — bukan lewat HTTP.

ALUR (API): `POST /api/ar/aging/{customer_id}/accrue-penalties` sebagai Admin, dengan dan tanpa `?today=`.

Hitung tangan (rumus harian PK-08: dasar × tarif × hari kena denda ÷ 30):
  U1 server 31 Okt 2026 → telat 30 hari: 5.000.000 × 2 % × 30 ÷ 30 = 100.000, kunci periode `2026-10-01|2026-10`.
     Pelanggan kembar dengan `?today=2099-01-01` harus sama persis. Kode lama: telat 26.390 hari →
     5.000.000 × 2 % × 26.390 ÷ 30 = 87.966.666,67 (batas 0 % = tanpa batas), kunci `2026-10-01|2099-01`.
  U2 server 20 Sep 2026 (belum jatuh tempo) + `?today=2099-01-01` → 0 nota. Kode lama: nota 87.966.666,67 lahir.
  U3 server 31 Okt 2026 + `?today=2026-09-15` (sebelum jatuh tempo) → tetap 100.000. Kode lama: 0 nota (klien bisa
     menekan denda dengan tanggal mundur).
  U4 kontrak: rute akrual denda tidak menyatakan parameter tanggal dari klien di OpenAPI.
"""
from __future__ import annotations

import datetime
import uuid

import pytest

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"
KANDA = "ent_kanda"
TGL = "2026-10-31"
MASA_DEPAN = "2099-01-01"
RUTE_AKRUAL = ("/api/ar/aging/{customer_id}/accrue-penalties", "/api/payment-plans/{plan_id}/accrue")
NAMA_TANGGAL = {"today", "as_of", "date", "tanggal", "hari_ini"}


def _id(awal: str) -> str:
    return f"{awal}_crt4b_{uuid.uuid4().hex[:8]}"


def _beku(monkeypatch, tanggal_wib: str, jam_wib: int = 10):
    """Bekukan "hari ini" (`services.book_date._sekarang`, satu-satunya jam hari ini WIB)."""
    from services import book_date
    d = datetime.date.fromisoformat(tanggal_wib)
    beku = datetime.datetime(d.year, d.month, d.day, jam_wib, 0, tzinfo=book_date.WIB).astimezone(datetime.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)


def _jam(tanggal: str) -> str:
    return f"{tanggal}T03:00:00+00:00"   # 10.00 WIB


@pytest.fixture(scope="module")
async def adm(sesi):
    return await sesi(ADMIN, entitas=KANDA)


async def _d1(db) -> dict:
    """Pelanggan baru + pesanan NET30 terkirim penuh 1 Sep 2026 → jadwal `term` satu baris jatuh tempo 2026-10-01."""
    from services import billing_schedule_service as bss
    from services import gl_service as gl
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": f"Toko CR-T4b {cid[-4:]}", "entity_id": KANDA,
                                   "status": "active", "payment_profile": {}, "deposit_balance": 0.0})
    so = {"id": _id("so"), "number": f"SO-CRT4B-{uuid.uuid4().hex[:5]}", "entity_id": KANDA, "customer_id": cid,
          "customer_name": "Toko CR-T4b", "status": "shipped", "grand_total": 5_000_000.0,
          "total_amount": 5_000_000.0, "ppn_amount": 0.0, "payments": [], "paid_total": 0.0,
          "payment_status": "unpaid", "payment_term_code": "NET30", "payment_term_days": 30, "items": [],
          "created_at": _jam("2026-08-25"), "confirmed_at": _jam("2026-08-25")}
    await db.sales_orders.insert_one(dict(so))
    nomor = f"SJ-CRT4B-{uuid.uuid4().hex[:5]}"
    shid = _id("shp")
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": KANDA,
                                   "status": "dispatched", "created_at": _jam("2026-09-01")})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": 5_000_000.0, "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": 5_000_000.0}],
                           description=f"Pengakuan penjualan {so['number']} · {nomor}", date=_jam("2026-09-01"),
                           source_type="shipment_revenue", source_id=shid, entity_id=KANDA, created_by="system",
                           source_label=nomor, ref={"order_id": so["id"], "order_number": so["number"]})
    plan = await bss.on_shipment_posted(so["id"], nomor)
    assert plan and plan["origin"] == "term", plan
    [ln] = plan["lines"]
    assert (ln["amount"], ln["due_date"]) == (5_000_000.0, "2026-10-01"), ln
    return {"customer_id": cid, "plan": plan}


async def _akrual(klien, h, cid: str, today: str | None = None):
    params = {"today": today} if today is not None else None
    return await klien.post(f"/api/ar/aging/{cid}/accrue-penalties", headers=h, params=params)


async def _nota(db, cid: str) -> list:
    return [n async for n in db.penalties.find({"customer_id": cid}, {"_id": 0}).sort("period_key", 1)]


def _ringkas(nota: list) -> list:
    return [(n["amount"], n["days_late"], n["billable_days"], n["period_key"]) for n in nota]


# ═══ U1 — `?today=` masa depan tidak menambah denda; hasil = panggilan tanpa parameter ═══════════════════════════════
async def test_CRT4b_U1_today_masa_depan_diabaikan(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    a = await _d1(db)          # pembanding: tanpa parameter
    b = await _d1(db)          # klien mengirim tanggal masa depan
    ra = await _akrual(klien, adm, a["customer_id"])
    rb = await _akrual(klien, adm, b["customer_id"], MASA_DEPAN)
    assert ra.status_code == 200, ra.text
    assert rb.status_code == 200, rb.text
    harapan = [(100_000, 30, 30, "2026-10-01|2026-10")]
    assert _ringkas(await _nota(db, a["customer_id"])) == harapan
    assert _ringkas(await _nota(db, b["customer_id"])) == harapan
    ja, jb = ra.json(), rb.json()
    assert (ja["count"], jb["count"]) == (1, 1), (ja["count"], jb["count"])
    assert sum(p["amount"] for p in jb["penalties"]) <= sum(p["amount"] for p in ja["penalties"]) == 100_000
    # Rincian umur piutang di jawaban juga per tanggal server, bukan per `?today=`.
    [ia], [ib] = ja["detail"]["items"], jb["detail"]["items"]
    assert (ib["days_late"], ib["denda_estimate"]) == (ia["days_late"], ia["denda_estimate"]) == (30, 100_000), ib
    # Diulang di hari server yang sama dengan `?today=` lain: idempoten, tetap satu nota 100.000.
    rb2 = await _akrual(klien, adm, b["customer_id"], "2098-06-30")
    assert rb2.status_code == 200, rb2.text
    assert _ringkas(await _nota(db, b["customer_id"])) == harapan


# ═══ U2 — baris belum jatuh tempo menurut server: `?today=` masa depan tidak melahirkan nota ═════════════════════════
async def test_CRT4b_U2_belum_jatuh_tempo_tanpa_nota(db, klien, adm, monkeypatch):
    _beku(monkeypatch, "2026-09-20")
    f = await _d1(db)
    r = await _akrual(klien, adm, f["customer_id"], MASA_DEPAN)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0, r.json()["penalties"]
    assert await _nota(db, f["customer_id"]) == []


# ═══ U3 — `?today=` mundur tidak menekan denda yang sudah jatuh tempo menurut server ═════════════════════════════════
async def test_CRT4b_U3_today_mundur_tidak_menekan_denda(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    f = await _d1(db)
    r = await _akrual(klien, adm, f["customer_id"], "2026-09-15")
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1, r.json()
    assert _ringkas(await _nota(db, f["customer_id"])) == [(100_000, 30, 30, "2026-10-01|2026-10")]


# ═══ U4 — kontrak: rute akrual denda tidak menerima tanggal dari klien ═══════════════════════════════════════════════
async def test_CRT4b_U4_rute_akrual_tanpa_parameter_tanggal(aplikasi):
    paths = aplikasi.openapi()["paths"]
    akrual = {p for p in paths if "accrue" in p}
    assert set(RUTE_AKRUAL) <= akrual, sorted(akrual)
    for p in sorted(akrual):
        for metode, op in paths[p].items():
            nama = {prm["name"] for prm in op.get("parameters") or [] if prm.get("in") == "query"}
            assert not (nama & NAMA_TANGGAL), f"{metode.upper()} {p} menerima tanggal dari klien: {sorted(nama)}"
