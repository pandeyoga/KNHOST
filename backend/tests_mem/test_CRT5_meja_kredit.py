"""CR-T5 — daftar kerja "Kredit & Plafon" (enam antrean), janji bayar, rekening koran pelanggan, naskah pengingat
(docs/blueprint/unit/CR-T5.md, tabel "Uji penerimaan" U1–U15; U16 = uji jalan layar oleh integrator).

FIXTURE R1 (disisipkan langsung — dicatat sebagai fixture, bukan alur): PT `ent_kanda`, pelanggan P, satu pesanan S1.
Jurnal akun piutang (1-1200) dalam bentuk pembuatnya:
  1 Okt  surat jalan SJ-1  `shipment_revenue` (ref.order_id = S1)          Dr 400.000
  15 Okt kwitansi KW-1     `cash_transaction` (ref_type ar_receipt)         Cr 400.000
  20 Okt surat jalan SJ-2  `shipment_revenue`                               Dr 600.000
  25 Okt nota kredit NK-1  `amendment_credit_note` (ref.order_id = S1)      Cr 100.000
  5 Nov  kwitansi KW-2     `cash_transaction`                               Cr 500.000
Pengecoh: surat jalan pelanggan lain Q di PT yang sama (Dr 250.000) dan jurnal manual piutang tanpa pelanggan
(Dr 70.000) — keduanya TIDAK boleh tampil di rekening koran P.

Hitung tangan:
  U1  Okt: saldo awal 0 (tidak ada jurnal P sebelum 1 Okt); berjalan 0 + 400.000 = 400.000 → − 400.000 = 0 →
      + 600.000 = 600.000 → − 100.000 = 500.000; saldo akhir 500.000 = Σ jurnal piutang P ≤ 31 Okt
      (400.000 + 600.000 − 400.000 − 100.000).
  U2  Nov: saldo awal = 500.000 (Σ sebelum 1 Nov); satu baris kwitansi Cr 500.000; saldo akhir 500.000 − 500.000 = 0.
  U3  `ent_ksc`: tidak ada jurnal P → baris kosong, saldo 0. Konteks "Semua PT" → 400 "Pilih satu PT…".
  U6  Janji 500.000 untuk 10 Nov dicatat 6 Nov. 8 Nov: 8 ≤ 10 → menunggu. 12 Nov tanpa kwitansi: 12 > 10 dan Σ kwitansi
      6–10 Nov = 0 < 500.000 → ingkar. Pembanding P2: janji 300.000 untuk 9 Nov, kwitansi 300.000 tgl 7 Nov → ditepati;
      urutan 12 Nov = ingkar (P, 10 Nov) DULU, baru ditepati (P2, 9 Nov) walau tanggalnya lebih awal. Kwitansi P
      500.000 tgl 9 Nov (6 ≤ 9 ≤ 10) → Σ 500.000 ≥ 500.000 → ditepati.
  U9  Hari uji 20 Nov; jendela = hari ini + 3 = 23 Nov. Baris P9: 300.000 jatuh tempo 10 Nov (−10, telat 10),
      100.000 jatuh tempo 22 Nov (+2), 200.000 jatuh tempo 25 Nov (+5, di luar jendela) → 2 baris, total 400.000,
      telat terlama 10.
  U10 Hari uji 20 Nov; jendela kaji ulang = + 14 hari = 4 Des. Plafon berakhir 30 Nov (+10, mendekati), 19 Nov (−1,
      lewat), 30 Des (+40, di luar) → 2 baris: lewat dulu, lalu mendekati.
  U15 Naskah = dua baris U9 (jatuh tempo tertua dulu), total 300.000 + 100.000 = 400.000.
"""
from __future__ import annotations

import datetime
import uuid

import pytest

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"
KSC, KANDA = "ent_ksc", "ent_kanda"
S: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_crt5_{uuid.uuid4().hex[:8]}"


def _beku(monkeypatch, tanggal_wib: str, jam_wib: int = 10):
    """Bekukan "hari ini" (`services.book_date._sekarang`, satu-satunya jam hari ini WIB)."""
    from services import book_date
    d = datetime.date.fromisoformat(tanggal_wib)
    beku = datetime.datetime(d.year, d.month, d.day, jam_wib, 0, tzinfo=book_date.WIB).astimezone(datetime.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)


def _jam(tanggal: str) -> str:
    return f"{tanggal}T03:00:00+00:00"   # 10.00 WIB


def _geser(tanggal: str, hari: int) -> str:
    return (datetime.date.fromisoformat(tanggal) + datetime.timedelta(days=hari)).isoformat()


async def _pelanggan(db, eid: str, nama: str, **extra) -> str:
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": nama, "entity_id": eid, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": "", **extra})
    return cid


async def _pesanan(db, cid: str, eid: str, total: float, *, nama: str = "Toko CR-T5", status: str = "partially_shipped",
                   **extra) -> dict:
    so = {"id": _id("so"), "number": f"SO-CRT5-{uuid.uuid4().hex[:5]}", "entity_id": eid, "customer_id": cid,
          "customer_name": nama, "status": status, "grand_total": float(total), "total_amount": float(total),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30",
          "payment_term_days": 30, "items": [], "created_at": _jam("2026-09-25"), "confirmed_at": _jam("2026-09-25"),
          **extra}
    await db.sales_orders.insert_one(dict(so))
    return so


async def _jurnal(lines, *, tanggal: str, source_type: str, source_id: str, eid: str, label: str, ref=None):
    from services import gl_service as gl
    return await gl._insert_entry(lines=lines, description=f"uji CR-T5 {label}", date=_jam(tanggal),
                                  source_type=source_type, source_id=source_id, entity_id=eid, created_by="system",
                                  source_label=label, ref=ref or {})


async def _kirim(db, so: dict, nilai: float, tanggal: str, nomor: str) -> dict:
    """Surat jalan + jurnal pengakuan (Dr piutang / Cr pendapatan) — bentuk `gl_service.post_shipment_revenue`."""
    shid = _id("shp")
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": so["entity_id"],
                                   "status": "dispatched", "created_at": _jam(tanggal)})
    return await _jurnal([{"account_code": "1-1200", "debit": float(nilai), "credit": 0.0},
                          {"account_code": "4-1000", "debit": 0.0, "credit": float(nilai)}],
                         tanggal=tanggal, source_type="shipment_revenue", source_id=shid, eid=so["entity_id"],
                         label=nomor, ref={"order_id": so["id"], "order_number": so["number"]})


async def _kwitansi(db, cid: str, eid: str, nilai: float, tanggal: str, nomor: str, *, jurnal: bool = True) -> str:
    """Kwitansi + kas masuk (ref_type ar_receipt) + jurnal kas Dr kas / Cr piutang — bentuk `_post_cash_transaction`."""
    rid, tid = _id("arr"), _id("cash")
    await db.ar_receipts.insert_one({"id": rid, "number": nomor, "customer_id": cid, "entity_id": eid,
                                     "amount": float(nilai), "method": "transfer", "receipt_date": tanggal,
                                     "status": "posted", "created_at": _jam(tanggal)})
    if jurnal:
        await db.cash_transactions.insert_one({"id": tid, "number": f"KAS-{nomor}", "ref_type": "ar_receipt",
                                               "ref_id": rid, "entity_id": eid, "direction": "in",
                                               "amount": float(nilai), "status": "posted", "txn_date": tanggal})
        await _jurnal([{"account_code": "1-1100", "debit": float(nilai), "credit": 0.0},
                       {"account_code": "1-1200", "debit": 0.0, "credit": float(nilai)}],
                      tanggal=tanggal, source_type="cash_transaction", source_id=tid, eid=eid, label=f"KAS-{nomor}")
    return rid


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan: dict = {}

    async def _h(eid: str):
        if eid not in simpan:
            simpan[eid] = await sesi(ADMIN, entitas=eid)
        return simpan[eid]
    return _h


@pytest.fixture(scope="module")
async def r1(db):
    if "P" in S:
        return S
    cid = await _pelanggan(db, KANDA, "Toko P CR-T5")
    s1 = await _pesanan(db, cid, KANDA, 1_000_000, nama="Toko P CR-T5")
    await _kirim(db, s1, 400_000, "2026-10-01", "SJ-CRT5-1")
    await _kwitansi(db, cid, KANDA, 400_000, "2026-10-15", "KW-CRT5-1")
    await _kirim(db, s1, 600_000, "2026-10-20", "SJ-CRT5-2")
    nid = _id("cn")
    await db.credit_notes.insert_one({"id": nid, "number": "NK-CRT5-1", "order_id": s1["id"], "entity_id": KANDA,
                                      "customer_id": cid, "status": "posted", "created_at": _jam("2026-10-25")})
    await _jurnal([{"account_code": "4-1000", "debit": 100_000.0, "credit": 0.0},
                   {"account_code": "1-1200", "debit": 0.0, "credit": 100_000.0}],
                  tanggal="2026-10-25", source_type="amendment_credit_note", source_id=nid, eid=KANDA,
                  label="NK-CRT5-1", ref={"order_id": s1["id"], "order_number": s1["number"]})
    await _kwitansi(db, cid, KANDA, 500_000, "2026-11-05", "KW-CRT5-2")
    # pengecoh: pelanggan lain di PT yang sama + jurnal manual piutang tanpa pelanggan
    q = await _pelanggan(db, KANDA, "Toko Q CR-T5")
    sq = await _pesanan(db, q, KANDA, 250_000, nama="Toko Q CR-T5")
    await _kirim(db, sq, 250_000, "2026-10-10", "SJ-CRT5-Q")
    await _jurnal([{"account_code": "1-1200", "debit": 70_000.0, "credit": 0.0},
                   {"account_code": "4-9000", "debit": 0.0, "credit": 70_000.0}],
                  tanggal="2026-10-12", source_type="manual", source_id=_id("mj"), eid=KANDA, label="JM-CRT5")
    S.update(P=cid, S1=s1, Q=q)
    return S


async def _rk(klien, h, cid, **params):
    return await klien.get(f"/api/customers/{cid}/statement", headers=h, params=params)


# ═══ U1–U4 — rekening koran dari baris jurnal akun piutang ═══════════════════════════════════════════════════════════
async def test_CRT5_U1_rekening_koran_oktober(r1, klien, adm, db):
    r = await _rk(klien, await adm(KANDA), r1["P"], entity_id=KANDA, **{"from": "2026-10-01", "to": "2026-10-31"})
    assert r.status_code == 200, r.text
    st = r.json()
    assert (st["from"], st["to"], st["opening_balance"], st["closing_balance"]) == \
        ("2026-10-01", "2026-10-31", 0, 500_000)
    rows = st["rows"]
    assert [(x["date"], x["doc_type"], x["doc_number"], x["debit"], x["credit"], x["balance"]) for x in rows] == [
        ("2026-10-01", "surat_jalan", "SJ-CRT5-1", 400_000, 0, 400_000),
        ("2026-10-15", "kwitansi", "KW-CRT5-1", 0, 400_000, 0),
        ("2026-10-20", "surat_jalan", "SJ-CRT5-2", 600_000, 0, 600_000),
        ("2026-10-25", "nota_kredit", "NK-CRT5-1", 0, 100_000, 500_000),
    ]
    assert all(x["je_id"] for x in rows)
    # saldo akhir = Σ jurnal akun piutang milik P ≤ 31 Okt (dihitung langsung dari jurnalnya)
    ids = {x["je_id"] for x in rows}
    total = 0.0
    async for je in db.journal_entries.find({"id": {"$in": sorted(ids)}}, {"_id": 0, "lines": 1}):
        total += sum(float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
                     for ln in je["lines"] if ln["account_code"] == "1-1200")
    assert round(total, 2) == st["closing_balance"] == 400_000 + 600_000 - 400_000 - 100_000
    assert st["customer"]["id"] == r1["P"] and st["entity"]["id"] == KANDA
    assert st["penalties"] == {"opening_balance": 0, "rows": [], "closing_balance": 0}


async def test_CRT5_U2_rekening_koran_november(r1, klien, adm):
    r = await _rk(klien, await adm(KANDA), r1["P"], entity_id=KANDA, **{"from": "2026-11-01", "to": "2026-11-30"})
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["opening_balance"] == 500_000 and st["closing_balance"] == 0
    assert [(x["doc_type"], x["doc_number"], x["credit"], x["balance"]) for x in st["rows"]] == \
        [("kwitansi", "KW-CRT5-2", 500_000, 0)]


async def test_CRT5_U3_pt_lain_tidak_tercampur_dan_semua_pt_ditolak(r1, klien, adm, sesi):
    r = await _rk(klien, await adm(KANDA), r1["P"], entity_id=KSC, **{"from": "2026-10-01", "to": "2026-10-31"})
    assert r.status_code == 200, r.text
    st = r.json()
    assert (st["rows"], st["opening_balance"], st["closing_balance"]) == ([], 0, 0)
    semua = await sesi(ADMIN, entitas="all")
    r = await _rk(klien, semua, r1["P"], **{"from": "2026-10-01", "to": "2026-10-31"})
    assert r.status_code == 400 and r.json()["detail"] == "Pilih satu PT untuk rekening koran.", r.text


async def test_CRT5_U4_pdf_rekening_koran(r1, klien, adm, db):
    r = await klien.get(f"/api/customers/{r1['P']}/statement.pdf", headers=await adm(KANDA),
                        params={"format": "html", "entity_id": KANDA, "from": "2026-10-01", "to": "2026-10-31"})
    assert r.status_code == 200, r.text
    ent = await db.business_entities.find_one({"id": KANDA}, {"_id": 0})
    nama_pt = ent.get("legal_name") or ent.get("name")
    for teks in ("Rekening Koran Pelanggan", nama_pt, "Saldo akhir", "500.000"):
        assert teks in r.text, teks


# ═══ U5, U6 — janji bayar ═════════════════════════════════════════════════════════════════════════════════════════
async def test_CRT5_U5_janji_tanpa_tanggal_atau_lampau_ditolak(r1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-06")
    h = await adm(KANDA)
    cid = await _pelanggan(db, KANDA, "Toko U5 CR-T5")
    dasar = {"customer_id": cid, "note": "janji transfer", "outcome": "promised"}
    r = await klien.post(f"/api/customers/{cid}/followups", headers=h, json={**dasar, "promise_amount": 500_000})
    assert r.status_code == 400 and r.json()["detail"] == "Tanggal janji bayar wajib diisi.", r.text
    r = await klien.post(f"/api/customers/{cid}/followups", headers=h,
                         json={**dasar, "promise_date": "2026-11-05", "promise_amount": 500_000})
    assert r.status_code == 400 and r.json()["detail"] == "Tanggal janji bayar tidak boleh di masa lalu.", r.text
    r = await klien.post(f"/api/customers/{cid}/followups", headers=h, json={**dasar, "promise_date": "2026-11-10"})
    assert r.status_code == 400 and r.json()["detail"] == "Nominal janji bayar wajib lebih dari nol.", r.text
    assert await db.collection_followups.count_documents({"customer_id": cid}) == 0
    # hasil lain tidak menuntut tanggal/nominal janji
    r = await klien.post(f"/api/customers/{cid}/followups", headers=h,
                         json={"customer_id": cid, "note": "dihubungi", "outcome": "contacted"})
    assert r.status_code == 200, r.text


async def _janji(klien, h, db, cid, tanggal, nominal, dicatat):
    r = await klien.post(f"/api/customers/{cid}/followups", headers=h,
                         json={"customer_id": cid, "note": "janji transfer", "outcome": "promised",
                               "promise_date": tanggal, "promise_amount": nominal})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert (doc["promise_date"], doc["promise_amount"]) == (tanggal, nominal)
    # fixture: tanggal catatan = hari uji (stempel `created_at` memakai jam sistem, bukan jam beku)
    await db.collection_followups.update_one({"id": doc["id"]}, {"$set": {"created_at": _jam(dicatat)}})
    return doc["id"]


async def _antrean(klien, h, nama, **params):
    r = await klien.get("/api/credit-desk", headers=h, params={"queue": nama, **params})
    assert r.status_code == 200, r.text
    return r.json()


async def test_CRT5_U6_status_janji_dihitung_saat_dibaca(r1, klien, adm, db, monkeypatch):
    h = await adm(KANDA)
    _beku(monkeypatch, "2026-11-06")
    p = await _pelanggan(db, KANDA, "Toko U6 CR-T5")
    p2 = await _pelanggan(db, KANDA, "Toko U6b CR-T5")
    a = await _janji(klien, h, db, p, "2026-11-10", 500_000, "2026-11-06")
    b = await _janji(klien, h, db, p2, "2026-11-09", 300_000, "2026-11-06")
    await _kwitansi(db, p2, KANDA, 300_000, "2026-11-07", "KW-CRT5-U6b", jurnal=False)

    def mine(res):
        return [x for x in res["items"] if x["id"] in (a, b)]

    _beku(monkeypatch, "2026-11-08")
    rows = mine(await _antrean(klien, h, "janji_bayar"))
    assert {x["id"]: x["status"] for x in rows} == {a: "menunggu", b: "ditepati"}
    _beku(monkeypatch, "2026-11-12")
    rows = mine(await _antrean(klien, h, "janji_bayar"))
    assert [(x["id"], x["status"]) for x in rows] == [(a, "ingkar"), (b, "ditepati")]
    assert rows[0]["promise_amount"] == 500_000 and rows[0]["promise_date"] == "2026-11-10"
    await _kwitansi(db, p, KANDA, 500_000, "2026-11-09", "KW-CRT5-U6", jurnal=False)
    rows = mine(await _antrean(klien, h, "janji_bayar"))
    assert {x["id"]: x["status"] for x in rows} == {a: "ditepati", b: "ditepati"}
    S["U6"] = (a, b)


# ═══ U7–U14 — antrean & ringkasan ══════════════════════════════════════════════════════════════════════════════════
async def test_CRT5_U7_menunggu_keputusan_dua_jenis(r1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-20")
    h = await adm(KANDA)
    awal = (await _antrean(klien, h, "menunggu_keputusan"))["total"]
    c7 = await _pelanggan(db, KANDA, "Toko U7 CR-T5")
    c7b = await _pelanggan(db, KANDA, "Toko U7b CR-T5")
    co = {"id": _id("cro"), "customer_id": c7, "customer_name": "Toko U7 CR-T5", "order_id": "", "amount": 2_000_000.0,
          "reason": "PO besar sudah dikonfirmasi", "entity_id": KANDA, "status": "pending", "requested_by": "Sales Uji",
          "requested_by_id": "usr_x", "created_at": _jam("2026-11-10")}
    await db.credit_overrides.insert_one(dict(co))
    cpr = {"id": _id("cpr"), "number": "PKR-CRT5-1", "customer_id": c7b, "customer_name": "Toko U7b CR-T5",
           "entity_id": KANDA, "changes": [{"field": "credit_limit", "from": None, "to": 20_000_000}],
           "reason": "Omzet naik dua kali", "status": "diajukan", "requested_by": "Sales Uji",
           "requested_by_id": "usr_x", "created_at": _jam("2026-11-15")}
    await db.credit_profile_requests.insert_one(dict(cpr))
    res = await _antrean(klien, h, "menunggu_keputusan")
    assert awal == 0 and res["total"] == 2, res
    rows = [x for x in res["items"] if x["id"] in (co["id"], cpr["id"])]
    assert [(x["kind"], x["customer_id"], x["amount"]) for x in rows] == [
        ("izin_kredit", c7, 2_000_000), ("ubah_profil", c7b, 20_000_000)]   # tertua dulu
    assert rows[0]["age_days"] == 10 and rows[1]["age_days"] == 5
    assert rows[0]["summary"] and rows[1]["summary"]
    S["U7"] = (co["id"], cpr["id"])


async def test_CRT5_U8_pesanan_ditahan(r1, klien, adm, db):
    h = await adm(KANDA)
    c8 = await _pelanggan(db, KANDA, "Toko U8 CR-T5")
    so = await _pesanan(db, c8, KANDA, 3_000_000, nama="Toko U8 CR-T5", status="waiting_approval", credit_hold=True,
                        pending_approvals=[{"id": "apr_crt5", "type": "kredit", "status": "pending",
                                            "reason": "Over-limit kredit: eksposur melewati plafon.",
                                            "requested_at": _jam("2026-11-18")}])
    res = await _antrean(klien, h, "ditahan")
    rows = [x for x in res["items"] if x.get("order_id") == so["id"]]
    assert len(rows) == 1, res
    row = rows[0]
    assert (row["kind"], row["customer_id"], row["order_number"], row["amount"]) == \
        ("pesanan_ditahan", c8, so["number"], 3_000_000)
    assert row["message"] == "Over-limit kredit: eksposur melewati plafon."


async def test_CRT5_U9_jatuh_tempo_per_pelanggan(r1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-20")
    h = await adm(KANDA)
    c9 = await _pelanggan(db, KANDA, "Toko P9 CR-T5")
    so = await _pesanan(db, c9, KANDA, 600_000, nama="Toko P9 CR-T5", status="confirmed")
    lines = [{"seq": i + 1, "line_id": _id("pln"), "kind": "installment", "label": f"Cicilan {i + 1}", "amount": amt,
              "due_date": due, "source_type": "manual", "source_id": "", "status": "open"}
             for i, (amt, due) in enumerate([(300_000, _geser("2026-11-20", -10)), (100_000, _geser("2026-11-20", 2)),
                                             (200_000, _geser("2026-11-20", 5))])]
    await db.payment_plans.insert_one({"id": _id("ppl"), "number": "RB-CRT5-9", "doc_type": "sales_order",
                                       "doc_id": so["id"], "doc_number": so["number"], "customer_id": c9,
                                       "customer_name": "Toko P9 CR-T5", "entity_id": KANDA, "status": "active",
                                       "origin": "manual", "mode": "installment", "lines": lines,
                                       "created_at": _jam("2026-10-01")})
    res = await _antrean(klien, h, "jatuh_tempo")
    rows = [x for x in res["items"] if x["customer_id"] == c9]
    assert len(rows) == 1, res
    row = rows[0]
    assert (row["line_count"], row["total_outstanding"], row["max_days_late"]) == (2, 400_000, 10)
    assert [(ln["outstanding"], ln["due_date"]) for ln in row["lines"]] == \
        [(300_000, "2026-11-10"), (100_000, "2026-11-22")]
    assert row["next_due_date"] == "2026-11-22" and row["oldest_due_date"] == "2026-11-10"
    lates = [x["max_days_late"] for x in res["items"]]
    assert lates == sorted(lates, reverse=True)   # telat terlama dulu
    S.update(P9=c9, SO9=so)


async def test_CRT5_U10_kaji_ulang(r1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-20")
    h = await adm(KANDA)
    ids = []
    for nama, hari in (("K1", 10), ("K2", -1), ("K3", 40)):
        cid = await _pelanggan(db, KANDA, f"Toko {nama} CR-T5")
        ids.append(cid)
        await db.customer_credit_profiles.insert_one({
            "id": _id("ccp"), "customer_id": cid, "entity_id": KANDA, "limit_mode": "khusus",
            "credit_limit": 5_000_000.0, "limit_valid_until": _geser("2026-11-20", hari), "credit_status": "normal",
            "version": 1, "created_at": _jam("2026-09-01")})
    res = await _antrean(klien, h, "kaji_ulang")
    rows = [x for x in res["items"] if x["customer_id"] in ids]
    assert [(x["customer_id"], x["kind"], x["state"], x["valid_until"]) for x in rows] == [
        (ids[1], "plafon", "lewat", "2026-11-19"), (ids[0], "plafon", "mendekati", "2026-11-30")], res
    assert all(x["rejections_90d"] == 0 for x in rows)


async def test_CRT5_U11_ringkasan_sama_dengan_total(r1, klien, adm, monkeypatch):
    _beku(monkeypatch, "2026-11-20")
    h = await adm(KANDA)
    r = await klien.get("/api/credit-desk/summary", headers=h)
    assert r.status_code == 200, r.text
    ring = r.json()
    nama = ("menunggu_keputusan", "ditahan", "jatuh_tempo", "janji_bayar", "kaji_ulang", "denda")
    assert set(nama) <= set(ring)
    for n in nama:
        assert ring[n] == (await _antrean(klien, h, n))["total"], n
    assert ring["menunggu_keputusan"] == 2 and ring["kaji_ulang"] >= 2 and ring["ditahan"] >= 1


async def test_CRT5_U12_pt_lain_tidak_melihat(r1, klien, adm):
    res = await _antrean(klien, await adm(KSC), "menunggu_keputusan")
    assert res["total"] == 0 and res["items"] == []
    r = await klien.get("/api/credit-desk", headers=await adm(KANDA), params={"queue": "tidak_ada"})
    assert r.status_code == 400 and r.json()["detail"] == "Antrean tidak dikenal.", r.text


async def test_CRT5_U14_peran_uji_baku(r1, klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    tanpa = await akun(await peran_tanpa_acuan({"credit_profile": ["view"]}), entitas=(KANDA,))
    r = await klien.get("/api/credit-desk", headers=await sesi(tanpa, entitas=KANDA), params={"queue": "denda"})
    assert r.status_code == 200, r.text
    r = await klien.get("/api/credit-desk/summary", headers=await sesi(tanpa, entitas=KANDA))
    assert r.status_code == 200, r.text
    kosong = await akun(await peran_manajer_kosong(), entitas=(KANDA,))
    sopir = await akun(peran_sopir, entitas=(KANDA,))
    for u in (kosong, sopir):
        h = await sesi(u, entitas=KANDA)
        r = await klien.get("/api/credit-desk", headers=h, params={"queue": "denda"})
        assert r.status_code == 403, r.text
        r = await klien.get("/api/credit-desk/summary", headers=h)
        assert r.status_code == 403, r.text


async def test_CRT5_U15_naskah_pengingat(r1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-20")
    ent = await db.business_entities.find_one({"id": KANDA}, {"_id": 0})
    nama_pt = ent.get("legal_name") or ent.get("name")
    r = await klien.get(f"/api/customers/{S['P9']}/reminder-text", headers=await adm(KANDA),
                        params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    no = S["SO9"]["number"]
    assert r.json()["text"] == (
        "Yth. Toko P9 CR-T5,\n"
        f"Berikut tagihan {nama_pt} yang sudah atau akan jatuh tempo:\n"
        f"- {no} · Rp 300.000 · jatuh tempo 10 November 2026\n"
        f"- {no} · Rp 100.000 · jatuh tempo 22 November 2026\n"
        "Total: Rp 400.000\n"
        "Mohon konfirmasi pembayarannya. Terima kasih.")


async def test_CRT5_U13_sales_hanya_pelanggan_miliknya(r1, klien, akun, sesi, db):
    sls = await akun("sales", entitas=(KANDA,))
    p13 = await _pelanggan(db, KANDA, "Toko U13 CR-T5", assigned_sales_id=sls["id"])
    o13 = await _pelanggan(db, KANDA, "Toko U13 lain CR-T5")
    for cid, nama in ((p13, "Toko U13 CR-T5"), (o13, "Toko U13 lain CR-T5")):
        await db.credit_profile_requests.insert_one({
            "id": _id("cpr"), "number": f"PKR-{cid[-4:]}", "customer_id": cid, "customer_name": nama,
            "entity_id": KANDA, "changes": [{"field": "credit_limit", "from": None, "to": 7_000_000}],
            "reason": "Omzet naik dua kali", "status": "diajukan", "requested_by": "Uji",
            "requested_by_id": "usr_y", "created_at": _jam("2026-11-16")})
    res = await _antrean(klien, await sesi(sls, entitas=KANDA), "menunggu_keputusan")
    assert [x["customer_id"] for x in res["items"]] == [p13] and res["total"] == 1, res


# ═══ Tambahan — kotak Eksposur (L6) dan antrean denda (usul CR-T4) ════════════════════════════════════════════════
async def test_CRT5_X1_kotak_eksposur_baris_berlabel(r1, klien, adm):
    r = await klien.get(f"/api/customers/{r1['P']}/exposure", headers=await adm(KANDA), params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    ex = r.json()
    labels = [x["label"] for x in ex["rows"]]
    assert labels == ["Piutang barang terkirim", "Pesanan belum dikirim", "Giro belum cair", "Titipan & saldo kredit",
                      "Eksposur", "Plafon", "Sisa plafon"]
    assert ex["penalty"]["label"] == "Denda belum dibayar (tidak mengurangi plafon)"
    rows = {x["key"]: x for x in ex["rows"]}
    # L6 — baris dihitung = yang dipakai mesin: dengan gerbang kredit (CR-T3) = kunci `ar.eksposur_*` PT itu; tanpa
    # gerbang = perilaku `compute_customer_credit` (belum dikirim ya, giro & titipan tidak). Baris tak dihitung → teks.
    import importlib.util
    import config_registry
    from services.nilai_pengaturan import nilai
    ada_gerbang = importlib.util.find_spec("services.credit_gate") is not None
    for b, kunci, bawaan in (("belum_kirim", "ar.eksposur_pesanan_belum_kirim", True),
                             ("giro", "ar.eksposur_giro_belum_cair", False),
                             ("titipan", "ar.eksposur_titipan_mengurangi", False)):
        harap = bool(await nilai(kunci, KANDA)) if ada_gerbang and config_registry.get(kunci) else bawaan
        assert rows[b]["counted"] is harap, b
        assert rows[b]["note"] == ("" if harap else "tidak dihitung"), b
    hitung = rows["terkirim"]["amount"] + sum(
        (-1 if b == "titipan" else 1) * rows[b]["amount"] for b in ("belum_kirim", "giro", "titipan") if rows[b]["counted"])
    assert rows["eksposur"]["amount"] == round(hitung, 2)
    if ada_gerbang:   # satu pemilik angka eksposur (`02` D1): sama dengan gerbang kredit
        from services import credit_gate
        res = await credit_gate.evaluate(customer_id=r1["P"], entity_id=KANDA, checkpoint=credit_gate.PERIKSA_ULANG)
        assert rows["eksposur"]["amount"] == res["exposure"]["total"]


async def test_CRT5_X2_antrean_denda_menandai_jadwal_void(r1, klien, adm, db):
    h = await adm(KANDA)
    cid = await _pelanggan(db, KANDA, "Toko X2 CR-T5")
    plan_id = _id("ppl")
    await db.payment_plans.insert_one({"id": plan_id, "doc_type": "sales_order", "doc_id": _id("so"),
                                       "customer_id": cid, "entity_id": KANDA, "status": "void", "origin": "term",
                                       "lines": [], "created_at": _jam("2026-10-01")})
    pid = _id("pnl")
    await db.penalties.insert_one({"id": pid, "number": "DN-DENDA-CRT5", "entity_id": KANDA, "customer_id": cid,
                                   "customer_name": "Toko X2 CR-T5", "plan_id": plan_id, "doc_number": "SO-X2",
                                   "amount": 25_000.0, "status": "draft", "created_at": _jam("2026-11-01")})
    res = await _antrean(klien, h, "denda")
    rows = [x for x in res["items"] if x["id"] == pid]
    assert len(rows) == 1 and rows[0]["plan_void"] is True, res
