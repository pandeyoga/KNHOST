"""CR-T4 — denda berlapis PT → pelanggan → rencana, dihitung dari jadwal tagihan (docs/blueprint/unit/CR-T4.md, U1–U16).

FIXTURE D1 (disisip langsung, bentuk CR-T2): PT `ent_kanda`; kunci denda bawaan registry (`ar.denda_rate_pct_per_month`
2, `ar.grace_days` 0, `payment.penalty_mode` `draft`, `payment.penalty_base` `installment`, `payment.penalty_min_amount`
10.000); pelanggan P baru per uji; pesanan Rp 5.000.000 NET30 terkirim penuh 1 Sep 2026 (surat jalan + jurnal
`shipment_revenue` Dr piutang 5.000.000); kait CR-T2 `on_shipment_posted` membentuk jadwal `origin: term` satu baris
5.000.000 jatuh tempo 1 Sep + 30 = 2026-10-01, belum dibayar; pesanan TIDAK punya rencana cicilan. Tanggal uji dibekukan
(`book_date._sekarang`, satu-satunya jam hari ini WIB) ke 2026-10-31 → telat 30 hari.

ALUR (API): pengajuan & keputusan profil kredit (`POST /api/customers/{id}/credit-profile-requests`,
`POST /api/credit-profile-requests/{id}/decision`), Pusat Pengaturan (`PUT /api/config/values`), rencana bayar
(`POST /api/payment-plans`), terbit/bayar/bebas nota (`/api/penalties/...`), `GET /api/ar/aging/{id}`,
`GET /api/customers/{id}/penalty-policy`. Job harian dipanggil sebagai fungsi (`penalty_service.job_penalty_accrual`).

Hitung tangan (rumus harian PK-08: dasar × tarif × hari kena denda ÷ 30; hari kena denda = telat − tenggang):
  U1  5.000.000 × 2 % × 30 ÷ 30 = 100.000                        (semua unsur dari aturan grup)
  U2  5.000.000 × 1 % × 30 ÷ 30 = 50.000                         (tarif dari profil kredit pelanggan)
  U3  Q di ent_ksc bertarif PT 3 %: 5.000.000 × 3 % × 30 ÷ 30 = 150.000; P (ent_kanda) tetap 100.000
  U4  bebas s.d. 2026-12-31 → mode mati → tidak ada nota (pembanding tanpa bebas: 100.000)
  U5  bebas s.d. 2026-10-30 < 2026-10-31 → dibaca ikut PT → 100.000
  U6  rencana 0,5 % menimpa profil 1 %: 5.000.000 × 0,5 % × 30 ÷ 30 = 25.000
  U7  tenggang 10: 5.000.000 × 2 % × (30 − 10) ÷ 30 = 66.666,67
  U8  batas 1 %: hitungan mentah 100.000, batas 1 % × 5.000.000 = 50.000 → 50.000
  U9  sisa 5.000.000 − 2.000.000 = 3.000.000 × 2 % × 30 ÷ 30 = 60.000
  U10 sisa 400.000 × 2 % × 30 ÷ 30 = 8.000 < minimum 10.000 → tidak ada nota; taksiran umur piutang juga 0
  U11 nota 100.000 terbit (Dr 1-1270 100.000) → bayar 60.000 (Cr 1-1270 60.000) → bebas sisa 40.000 (Cr 1-1270 40.000)
      → saldo 1-1270 untuk nota itu 100.000 − 60.000 − 40.000 = 0
  U12 pengajuan bebas belum diputus → 100.000 lahir; disetujui, job 30 Nov → tidak ada nota baru, nota Oktober tetap
  U13 telat 45 hari (15 Nov): 5.000.000 × 2 % × 45 ÷ 30 = 150.000 (kode lama: 2 % × ceil(45/30) = 2 bulan → 200.000)
  U16 lapisan pelanggan `ar.denda_rate_pct_per_month` 1,5 → profil `khusus` bertarif 1,5; putaran kedua tanpa perubahan
"""
from __future__ import annotations

import datetime
import importlib
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"
KSC, KANDA = "ent_ksc", "ent_kanda"
REPO = Path(__file__).resolve().parents[2]
TGL = "2026-10-31"


def _id(awal: str) -> str:
    return f"{awal}_crt4_{uuid.uuid4().hex[:8]}"


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
    simpan: dict = {}

    async def _h(eid: str = KANDA):
        if eid not in simpan:
            simpan[eid] = await sesi(ADMIN, entitas=eid)
        return simpan[eid]
    return _h


async def _pelanggan(db, eid: str = KANDA, nama: str = "Toko CR-T4", sales_id: str = "") -> str:
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": f"{nama} {cid[-4:]}", "entity_id": eid, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": sales_id})
    return cid


async def _d1(db, cid: str, eid: str = KANDA, nilai: float = 5_000_000, *, dibayar: float = 0.0) -> dict:
    """Pesanan NET30 terkirim penuh 1 Sep 2026 + jurnal pendapatan → jadwal `term` satu baris jatuh tempo 2026-10-01."""
    from services import billing_schedule_service as bss
    from services import gl_service as gl
    from services import payment_plan_service as plans
    so = {"id": _id("so"), "number": f"SO-CRT4-{uuid.uuid4().hex[:5]}", "entity_id": eid, "customer_id": cid,
          "customer_name": "Toko CR-T4", "status": "shipped", "grand_total": float(nilai), "total_amount": float(nilai),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30",
          "payment_term_days": 30, "items": [], "created_at": _jam("2026-08-25"), "confirmed_at": _jam("2026-08-25")}
    await db.sales_orders.insert_one(dict(so))
    nomor = f"SJ-CRT4-{uuid.uuid4().hex[:5]}"
    shid = _id("shp")
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": eid,
                                   "status": "dispatched", "created_at": _jam("2026-09-01")})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(nilai), "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": float(nilai)}],
                           description=f"Pengakuan penjualan {so['number']} · {nomor}", date=_jam("2026-09-01"),
                           source_type="shipment_revenue", source_id=shid, entity_id=eid, created_by="system",
                           source_label=nomor, ref={"order_id": so["id"], "order_number": so["number"]})
    plan = await bss.on_shipment_posted(so["id"], nomor)
    if dibayar:
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {
            "payments": [{"id": _id("pay"), "amount": float(dibayar), "date": _jam("2026-09-20"), "method": "transfer"}],
            "paid_total": float(dibayar), "payment_status": "partial"}})
        plan = await plans.recompute_paid(plan["id"])
    assert plan and plan["origin"] == "term", plan
    [ln] = plan["lines"]
    assert (ln["amount"], ln["due_date"]) == (float(nilai), "2026-10-01"), ln
    return {"order": so, "plan": plan, "customer_id": cid}


async def _nota(db, plan_id: str) -> list:
    return [n async for n in db.penalties.find({"plan_id": plan_id}, {"_id": 0}).sort("period_key", 1)]


async def _ajukan(klien, h, cid: str, rule: dict, eid: str = KANDA, reason: str = "Kesepakatan dengan pelanggan"):
    return await klien.post(f"/api/customers/{cid}/credit-profile-requests", headers=h,
                            json={"entity_id": eid, "changes": {"penalty_rule": rule}, "reason": reason})


async def _putus(klien, h, rid: str, decision: str = "approve", note: str = ""):
    return await klien.post(f"/api/credit-profile-requests/{rid}/decision", headers=h,
                            json={"decision": decision, "note": note})


async def _aturan(klien, h, cid: str, rule: dict, eid: str = KANDA) -> dict:
    """Profil kredit pelanggan diberi `penalty_rule` lewat pengajuan + keputusan Admin (kontrol bawaan: satu orang)."""
    r = await _ajukan(klien, h, cid, rule, eid)
    assert r.status_code == 200, r.text
    r = await _putus(klien, h, r.json()["id"])
    assert r.status_code == 200, r.text
    return r.json()


async def _job():
    from services import penalty_service as pen
    return await pen.job_penalty_accrual()


# ═══ U1 — pesanan tanpa rencana cicilan: nota dari jadwal tagihan ═══════════════════════════════════════════════════
async def test_CRT4_U1_nota_dari_jadwal_tagihan(db, monkeypatch):
    from services import payment_plan_service as plans
    _beku(monkeypatch, TGL)
    f = await _d1(db, await _pelanggan(db))
    assert await plans.get_manual("sales_order", f["order"]["id"]) is None   # tidak punya rencana cicilan
    hasil = await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert (n["status"], n["amount"], n["days_late"], n["billable_days"], n["base_amount"]) == \
        ("draft", 100_000, 30, 30, 5_000_000), n
    assert n["doc_id"] == f["order"]["id"] and n["period_key"] == "2026-10-01|2026-10"
    src = n["policy_snapshot"]["sources"]
    assert src["rate_pct_per_month"] == "global" and src["mode"] == "global" and src["grace_days"] == "global", src
    assert hasil["scanned_plans"] >= 1 and hasil["created"] >= 1, hasil
    # idempoten: job kedua di hari yang sama tidak menambah nota
    await _job()
    assert len(await _nota(db, f["plan"]["id"])) == 1


# ═══ U2 — tarif khusus pelanggan dari profil kredit ═════════════════════════════════════════════════════════════════
async def test_CRT4_U2_tarif_khusus_pelanggan(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    await _aturan(klien, await adm(), cid, {"mode": "khusus", "rate_pct_per_month": 1})
    f = await _d1(db, cid)
    await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert n["amount"] == 50_000, n
    src = n["policy_snapshot"]["sources"]
    assert src["rate_pct_per_month"] == "pelanggan" and src["grace_days"] == "global", src
    assert n["policy_snapshot"]["rate_pct_per_month"] == 1


# ═══ U3 — tarif PT lain tidak mengubah PT ini ═══════════════════════════════════════════════════════════════════════
async def test_CRT4_U3_tarif_per_pt(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    h = await adm(KSC)
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": "ar.denda_rate_pct_per_month", "value": 3, "scope_type": "entity", "scope_id": KSC,
        "reason": "uji CR-T4"}]})
    assert r.status_code == 200, r.text
    try:
        p = await _d1(db, await _pelanggan(db, KANDA))
        q = await _d1(db, await _pelanggan(db, KSC), KSC)
        await _job()
        [np_] = await _nota(db, p["plan"]["id"])
        [nq] = await _nota(db, q["plan"]["id"])
        assert (nq["amount"], nq["entity_id"]) == (150_000, KSC), nq
        assert nq["policy_snapshot"]["sources"]["rate_pct_per_month"] == "pt"
        assert (np_["amount"], np_["entity_id"]) == (100_000, KANDA), np_
        assert np_["policy_snapshot"]["sources"]["rate_pct_per_month"] == "global"
    finally:
        r = await klien.post("/api/config/values/clear", headers=h, json={
            "key": "ar.denda_rate_pct_per_month", "scope_type": "entity", "scope_id": KSC, "reason": "pulihkan"})
        assert r.status_code == 200, r.text


# ═══ U4 / U5 — bebas denda beralasan dan bertanggal ═════════════════════════════════════════════════════════════════
async def test_CRT4_U4_bebas_denda_masih_berlaku(db, klien, adm, monkeypatch):
    from services import penalty_service as pen
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    await _aturan(klien, await adm(), cid, {"mode": "bebas", "reason": "Kesepakatan direksi",
                                            "valid_until": "2026-12-31"})
    pol = await pen.penalty_policy(KANDA, cid)
    assert pol["mode"] == "off" and pol["sources"]["mode"] == "pelanggan", pol
    assert pol["waiver"] == {"reason": "Kesepakatan direksi", "valid_until": "2026-12-31"}, pol
    f = await _d1(db, cid)
    pembanding = await _d1(db, await _pelanggan(db))   # pelanggan lain tanpa bebas denda, baris sama
    await _job()
    assert await _nota(db, f["plan"]["id"]) == []
    [n] = await _nota(db, pembanding["plan"]["id"])
    assert n["amount"] == 100_000


async def test_CRT4_U5_bebas_denda_sudah_lewat(db, klien, adm, monkeypatch):
    from services import penalty_service as pen
    _beku(monkeypatch, "2026-10-29")   # diajukan saat tanggal berakhirnya belum lewat
    cid = await _pelanggan(db)
    await _aturan(klien, await adm(), cid, {"mode": "bebas", "reason": "Kesepakatan direksi",
                                            "valid_until": "2026-10-30"})
    f = await _d1(db, cid)
    _beku(monkeypatch, TGL)
    pol = await pen.penalty_policy(KANDA, cid)
    assert pol["mode"] == "draft" and pol["waiver"] is None and pol["sources"]["mode"] == "global", pol
    await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert n["amount"] == 100_000


# ═══ U6 — aturan khusus rencana paling khusus ═══════════════════════════════════════════════════════════════════════
async def test_CRT4_U6_aturan_rencana_menimpa_pelanggan(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    await _aturan(klien, await adm(), cid, {"mode": "khusus", "rate_pct_per_month": 1})
    f = await _d1(db, cid)
    r = await klien.post("/api/payment-plans", headers=await adm(), json={
        "doc_type": "sales_order", "doc_id": f["order"]["id"], "mode": "custom",
        "lines": [{"seq": 1, "kind": "installment", "label": "Pelunasan", "basis": "amount", "amount": 5_000_000,
                   "due_rule": "fixed_date", "due_date": "2026-10-01"}],
        "penalty": {"rate_pct_per_month": 0.5}})
    assert r.status_code == 200, r.text
    rencana = r.json()
    assert rencana["origin"] == "manual" and rencana["penalty"]["rate_pct_per_month"] == 0.5
    await _job()
    assert await _nota(db, f["plan"]["id"]) == []      # jadwal term di-void "diganti rencana baru"
    [n] = await _nota(db, rencana["id"])
    assert n["amount"] == 25_000, n
    assert n["policy_snapshot"]["sources"]["rate_pct_per_month"] == "rencana"


async def test_CRT4_U6b_tarif_rencana_di_luar_batas_ditolak(db, klien, adm):
    cid = await _pelanggan(db)
    f = await _d1(db, cid)
    r = await klien.post("/api/payment-plans", headers=await adm(), json={
        "doc_type": "sales_order", "doc_id": f["order"]["id"], "mode": "custom",
        "lines": [{"seq": 1, "kind": "installment", "label": "Pelunasan", "basis": "amount", "amount": 5_000_000,
                   "due_rule": "fixed_date", "due_date": "2026-10-01"}],
        "penalty": {"rate_pct_per_month": 120}})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Tarif denda harus antara 0 dan 100 % per bulan."


# ═══ U7 / U8 — tenggang dan batas atas dari profil ══════════════════════════════════════════════════════════════════
async def test_CRT4_U7_tenggang_khusus_pelanggan(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    await _aturan(klien, await adm(), cid, {"mode": "khusus", "grace_days": 10})
    f = await _d1(db, cid)
    await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert (n["amount"], n["billable_days"], n["grace_days"]) == (66_666.67, 20, 10), n
    assert n["policy_snapshot"]["sources"]["grace_days"] == "pelanggan"
    assert n["policy_snapshot"]["sources"]["rate_pct_per_month"] == "global"


async def test_CRT4_U8_batas_atas_khusus_pelanggan(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    await _aturan(klien, await adm(), cid, {"mode": "khusus", "cap_pct": 1})
    f = await _d1(db, cid)
    await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert n["amount"] == 50_000 and n["policy_snapshot"]["sources"]["cap_pct"] == "pelanggan", n
    assert "100.000" in " ".join(n["explain"])   # hitungan mentah tetap tertulis


# ═══ U9 / U10 — dasar = sisa baris; minimum ════════════════════════════════════════════════════════════════════════
async def test_CRT4_U9_dasar_sisa_baris(db, monkeypatch):
    _beku(monkeypatch, TGL)
    f = await _d1(db, await _pelanggan(db), dibayar=2_000_000)
    assert f["plan"]["lines"][0]["paid_amount"] == 2_000_000
    await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert (n["amount"], n["base_amount"], n["base"]) == (60_000, 3_000_000, "installment"), n


async def test_CRT4_U10_di_bawah_minimum(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    f = await _d1(db, cid, nilai=400_000)
    await _job()
    assert await _nota(db, f["plan"]["id"]) == []
    # taksiran umur piutang memakai aturan yang sama → 0 (kode lama: 400.000 × 2 % × 1 bulan = 8.000)
    r = await klien.get(f"/api/ar/aging/{cid}", headers=await adm(), params={"as_of": TGL})
    assert r.status_code == 200, r.text
    [it] = r.json()["items"]
    assert it["denda_estimate"] == 0, it


# ═══ U11 — regresi PK-08: terbit, bayar sebagian, bebaskan → saldo piutang denda 0 ═════════════════════════════════
async def _saldo_1270(db, nid: str, kas_ids: list) -> float:
    d = k = 0.0
    q = {"status": {"$ne": "void"}, "entity_id": KANDA, "$or": [
        {"source_type": "penalty", "source_id": nid}, {"source_type": "penalty_reversal", "source_id": {"$regex": f"^{nid}:"}},
        {"source_type": "cash_transaction", "source_id": {"$in": kas_ids}}]}
    async for je in db.journal_entries.find(q):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == "1-1270":
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


async def test_CRT4_U11_bayar_lalu_bebas_saldo_nol(db, klien, adm):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    h = await adm()
    nid = _id("pnl")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Fixture setara nota U1 (100.000, draft) — disisip supaya uji ini tidak bergantung pada mesin akrual baru.
    await db.penalties.insert_one({
        "id": nid, "number": f"DN-DENDA-CRT4-{nid[-4:]}", "entity_id": KANDA, "doc_type": "sales_order",
        "doc_id": _id("so"), "doc_number": "SO-CRT4-U11", "plan_id": _id("pyp"), "line_seq": 1,
        "due_date": "2026-10-01", "period_key": "2026-10-01|2026-10", "customer_id": _id("cus"),
        "customer_name": "Toko CR-T4 U11", "base_amount": 5_000_000, "base": "installment", "amount": 100_000.0,
        "original_amount": 100_000.0, "days_late": 30, "billable_days": 30, "rate_pct_per_month": 2.0,
        "grace_days": 0, "cap_pct": 0, "status": "draft", "status_label": "Usulan", "paid_amount": 0.0,
        "je_id": "", "explain": [], "created_by": "uji", "created_at": now, "updated_at": now, "refs": []})
    rek = _id("ba")
    await db.bank_accounts.insert_one({"id": rek, "name": f"Bank Uji {rek}", "account_type": "bank",
                                       "cash_type": "kas_besar", "entity_id": KANDA, "is_active": True,
                                       "status": "active", "opening_balance": 0})
    r = await klien.post(f"/api/penalties/{nid}/issue", headers=h)
    assert r.status_code == 200, r.text
    assert await _saldo_1270(db, nid, []) == 100_000
    r = await klien.post(f"/api/penalties/{nid}/pay", headers=h, json={"amount": 60_000, "account_id": rek})
    assert r.status_code == 200, r.text
    kas = [k["id"] async for k in db.cash_transactions.find({"ref_type": "penalty", "ref_id": nid})]
    r = await klien.post(f"/api/penalties/{nid}/waive", headers=h,
                         json={"reason_code": "penalty_waiver", "note": "uji CR-T4"})
    assert r.status_code == 200, r.text
    assert await _saldo_1270(db, nid, kas) == 0
    p = await db.penalties.find_one({"id": nid})
    assert (p["status"], p["paid_amount"], p["waived_amount"]) == ("waived", 60_000, 40_000)


# ═══ U12 — pengajuan bebas belum diputus tidak berefek; sesudah disetujui tidak ada nota baru ══════════════════════
async def test_CRT4_U12_bebas_berlaku_sesudah_diputus(db, klien, akun, sesi, monkeypatch):
    _beku(monkeypatch, TGL)
    sls = await akun("sales", entitas=(KANDA,))
    h_sls = await sesi(sls, entitas=KANDA)
    h_mgr = await sesi("manager@kainnusantara.id", entitas=KANDA)
    cid = await _pelanggan(db, sales_id=sls["id"])
    f = await _d1(db, cid)
    r = await _ajukan(klien, h_sls, cid, {"mode": "bebas", "reason": "Kesepakatan direksi",
                                          "valid_until": "2026-12-31"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    await _job()
    [okt] = await _nota(db, f["plan"]["id"])
    assert (okt["amount"], okt["status"]) == (100_000, "draft")
    r = await _putus(klien, h_mgr, rid)
    assert r.status_code == 200, r.text
    _beku(monkeypatch, "2026-11-30")
    await _job()
    rows = await _nota(db, f["plan"]["id"])
    assert len(rows) == 1 and rows[0]["id"] == okt["id"], rows
    assert (rows[0]["amount"], rows[0]["status"], rows[0]["updated_at"]) == (100_000, "draft", okt["updated_at"])


# ═══ U13 — taksiran umur piutang = nota ════════════════════════════════════════════════════════════════════════════
async def test_CRT4_U13_taksiran_sama_dengan_nota(db, klien, adm, monkeypatch):
    _beku(monkeypatch, "2026-11-15")
    cid = await _pelanggan(db)
    f = await _d1(db, cid)
    r = await klien.get(f"/api/ar/aging/{cid}", headers=await adm(), params={"as_of": "2026-11-15"})
    assert r.status_code == 200, r.text
    j = r.json()
    [it] = j["items"]
    assert (it["days_late"], it["denda_estimate"]) == (45, 150_000), it
    assert j["totals"]["denda"] == 150_000
    await _job()
    [n] = await _nota(db, f["plan"]["id"])
    assert (n["amount"], n["days_late"], n["billable_days"]) == (150_000, 45, 45), n
    assert n["amount"] == it["denda_estimate"]


# ═══ U14 — lima kunci kehilangan lapisan pelanggan ═════════════════════════════════════════════════════════════════
LIMA_KUNCI = ("payment.penalty_mode", "payment.penalty_base", "payment.penalty_cap_pct",
              "ar.denda_rate_pct_per_month", "ar.grace_days")


async def test_CRT4_U14_lapisan_pelanggan_ditolak(db, klien, kepala_admin):
    import config_registry as registry
    from test_KFT8_putaran_pengaturan import putaran
    cid = await _pelanggan(db, KSC)
    sebelum = await db.config_values.count_documents({})
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "payment.penalty_mode", "value": "off", "scope_type": "customer", "scope_id": cid,
        "reason": "uji CR-T4"}]})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "“Denda telat: usulan atau langsung terbit” tidak bisa dibedakan per pelanggan."
    assert await db.config_values.count_documents({}) == sebelum
    for k in LIMA_KUNCI:
        e = registry.require(k)
        assert e["scopes"] == ["global", "entity"], k
        assert "per pelanggan dari kartu pelanggan" not in e["help"], k
        assert await putaran(klien, kepala_admin, k) == [], k


# ═══ U15 — izin endpoint baca aturan denda ═════════════════════════════════════════════════════════════════════════
async def test_CRT4_U15_izin_penalty_policy(db, klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                            peran_sopir):
    cid = await _pelanggan(db)
    u = await akun(await peran_tanpa_acuan({"penalty": ["view"]}, label="Lihat Denda CR-T4"), entitas=(KANDA,))
    r = await klien.get(f"/api/customers/{cid}/penalty-policy", headers=await sesi(u, entitas=KANDA),
                        params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j["effective"]) == {"mode", "rate_pct_per_month", "base", "cap_pct", "grace_days", "min_amount"}, j
    assert (j["effective"]["rate_pct_per_month"], j["effective"]["mode"], j["effective"]["min_amount"]) == \
        (2.0, "draft", 10_000.0)
    assert set(j["sources"]) >= set(j["effective"]) and j["waiver"] is None, j
    for peran in (await peran_manajer_kosong(), peran_sopir):
        u = await akun(peran, entitas=(KANDA,))
        r = await klien.get(f"/api/customers/{cid}/penalty-policy", headers=await sesi(u, entitas=KANDA),
                            params={"entity_id": KANDA})
        assert r.status_code == 403, (peran, r.text)


async def test_CRT4_U15b_validasi_pengajuan(db, klien, adm, monkeypatch):
    _beku(monkeypatch, TGL)
    cid = await _pelanggan(db)
    h = await adm()
    pesan_bebas = "Bebas denda wajib beralasan dan punya tanggal berakhir."
    for rule in ({"mode": "bebas", "valid_until": "2026-12-31"},
                 {"mode": "bebas", "reason": "Kesepakatan direksi"},
                 {"mode": "bebas", "reason": "ok", "valid_until": "2026-12-31"}):
        r = await _ajukan(klien, h, cid, rule)
        assert r.status_code == 400 and r.json()["detail"] == pesan_bebas, (rule, r.text)
    r = await _ajukan(klien, h, cid, {"mode": "khusus", "rate_pct_per_month": 101})
    assert r.status_code == 400 and r.json()["detail"] == "Tarif denda harus antara 0 dan 100 % per bulan.", r.text
    assert await db.credit_profile_requests.count_documents({"customer_id": cid}) == 0


# ═══ U16 — skrip migrasi lapisan pelanggan → profil kredit ═════════════════════════════════════════════════════════
async def test_CRT4_U16_migrasi_lapisan_pelanggan(db):
    from services import config_resolver as resolver
    sys.path.insert(0, str(REPO / "scripts"))
    skrip = importlib.import_module("migrate_penalty_customer_layer")
    cid = await _pelanggan(db, KANDA)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.config_values.insert_one({   # fixture: nilai lama lapisan pelanggan (diisi lewat layar KF-T5)
        "id": _id("cfgv"), "key": "ar.denda_rate_pct_per_month", "scope_type": "customer", "scope_id": cid,
        "value": 1.5, "prev_value": 2.0, "prev_source_layer": "code_default", "effective_from": "2026-01-01T00:00:00+00:00",
        "effective_to": "", "reason": "fixture lapisan pelanggan", "changed_by": "uji", "changed_by_id": "",
        "approved_by": "", "risk": "medium", "changed_at": "2026-01-01T00:00:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00", "applied_at": now})
    kering = await skrip.jalankan(tulis=False)
    assert [(x["customer_id"], x["changes"]) for x in kering["dipindah"] if x["customer_id"] == cid] == \
        [(cid, {"rate_pct_per_month": 1.5})], kering
    assert await db.customer_credit_profiles.find_one({"customer_id": cid}) is None   # baca-saja
    hasil = await skrip.jalankan(tulis=True)
    assert any(x["customer_id"] == cid for x in hasil["dipindah"]), hasil
    prof = await db.customer_credit_profiles.find_one({"customer_id": cid, "entity_id": KANDA}, {"_id": 0})
    assert prof["penalty_rule"]["mode"] == "khusus" and prof["penalty_rule"]["rate_pct_per_month"] == 1.5, prof
    rows = [r async for r in db.config_values.find({"key": "ar.denda_rate_pct_per_month", "scope_type": "customer",
                                                     "scope_id": cid}, {"_id": 0})]
    val, _win, _ = resolver._pick_effective(sorted(rows, key=lambda r: (r["effective_from"], r["created_at"])),
                                            datetime.datetime.now(datetime.timezone.utc))
    assert val is resolver._MISSING   # lapisan pelanggan kosong (nisan)
    versi = prof["version"]
    n_cfg = await db.config_values.count_documents({})
    ulang = await skrip.jalankan(tulis=True)
    assert all(x["customer_id"] != cid for x in ulang["dipindah"]), ulang
    assert await db.config_values.count_documents({}) == n_cfg
    assert (await db.customer_credit_profiles.find_one({"customer_id": cid}))["version"] == versi
    from services import penalty_service as pen
    pol = await pen.penalty_policy(KANDA, cid)
    assert pol["rate_pct_per_month"] == 1.5 and pol["sources"]["rate_pct_per_month"] == "pelanggan"
