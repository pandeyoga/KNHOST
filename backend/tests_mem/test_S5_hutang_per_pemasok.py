"""S5 (pelatihan keuangan 18 Nov) — Hutang per Pemasok: `GET /api/vendor-bills/payables/by-supplier` (+ `/{id}`)
dan bayar beberapa tagihan sekaligus lewat pintu yang ada (`POST /api/vendor-bills/{id}/pay`, PK-05), satu kunci per
tagihan. Uji komponen layar: `frontend/src/features/__tests__/latihS5PerPihak.test.js`; uji jalan:
`docs/pelatihan/2026-11-18_keuangan/uji/situasi/S5_per_pihak.js`.

Persiapan (FIXTURE = disisipkan langsung; ALUR = lewat API):
  * rekening `rek_s5` (`ent_ksc`) — FIXTURE.
  * pemasok **P** (`ent_ksc`): T1 4.000.000 jatuh tempo 45 hari lalu · T2 1.000.000 jatuh tempo 20 hari lagi ·
    T3 2.500.000 jatuh tempo 20 hari lagi, dipegang kontrabon KB-S5 (disetujui) · T9 600.000 LUNAS — FIXTURE;
    retur beli P disetujui potong hutang (nota debit) 300.000 — FIXTURE.
  * pemasok **Q**: tagihan `ent_ksc` 3.000.000 jatuh tempo 100 hari lalu · tagihan `ent_kanda` 2.000.000 belum jatuh
    tempo — FIXTURE.

Hitung tangan:
  U1  KSC: P = T1 + T2 + T3 = 4.000.000 + 1.000.000 + 2.500.000 = 7.500.000 (T9 lunas tidak dihitung);
      umur P: 31–60 hari = 4.000.000 (T1, lewat 45 hari), belum jatuh tempo = 3.500.000 (T2 + T3); lewat = 4.000.000;
      dipegang kontrabon = 1 tagihan 2.500.000; nota debit belum dipotong = 300.000.
      Q (KSC) = 3.000.000 di "> 90 hari". Total KSC = 7.500.000 + 3.000.000 = 10.500.000 = total ringkasan Hutang ›
      Tagihan (pembaca sama). Urutan: lewat terbesar dulu → P (4.000.000) lalu Q (3.000.000).
  U2  Semua PT: Q dua baris (KSC 3.000.000 · Kanda 2.000.000), tidak dijumlah.
  U5  Bayar T1 4.000.000 + T2 1.000.000 dari rek_s5 (dua kunci) → dua kas keluar, dua jurnal; hutang 2-1100 turun
      5.000.000; sisa P = 2.500.000 (T3, lewat kontrabon). Kirim ulang T1 dengan kunci sama → tidak ada kas baru.
"""
from __future__ import annotations

import datetime

import pytest

from core_utils import now_iso
from pembantu import jumlah, saldo_akun

pytestmark = pytest.mark.anyio

JT = 1_000_000
KSC, KANDA = "ent_ksc", "ent_kanda"


def _tgl(hari: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=hari)).isoformat()


def _tagihan(bid: str, sup: str, nama: str, total: float, due: str, *, ent: str = KSC, status: str = "posted",
             paid: float = 0.0) -> dict:
    return {"id": bid, "bill_number": f"VB-{bid[-4:].upper()}", "entity_id": ent, "supplier_id": sup,
            "supplier_name": nama, "status": status, "grand_total": float(total), "subtotal": float(total),
            "amount_paid": float(paid), "payment_status": "paid" if status == "paid" else "unpaid", "payments": [],
            "timeline": [], "po_id": None, "po_number": f"PO-{bid[-4:].upper()}", "bill_date": _tgl(-60),
            "due_date": due, "created_at": now_iso()}


@pytest.fixture(scope="module")
async def data(db):
    from services import contra_bon_service as cbs
    await db.bank_accounts.insert_one({"id": "rek_s5", "name": "BCA Operasional S5", "entity_id": KSC,
                                       "account_type": "bank", "cash_type": "bank", "is_active": True,
                                       "opening_balance": 0})
    for sid, nama in (("sup_s5p", "Pemasok P S5"), ("sup_s5q", "Pemasok Q S5")):
        await db.suppliers.insert_one({"id": sid, "name": nama, "code": sid.upper(), "entity_id": KSC,
                                       "status": "active", "payment_term_code": "NET30"})
    t1 = _tagihan("vb_s5t1", "sup_s5p", "Pemasok P S5", 4 * JT, _tgl(-45))
    t2 = _tagihan("vb_s5t2", "sup_s5p", "Pemasok P S5", 1 * JT, _tgl(20))
    t3 = _tagihan("vb_s5t3", "sup_s5p", "Pemasok P S5", 2.5 * JT, _tgl(20))
    t9 = _tagihan("vb_s5t9", "sup_s5p", "Pemasok P S5", 0.6 * JT, _tgl(-10), status="paid", paid=0.6 * JT)
    q1 = _tagihan("vb_s5q1", "sup_s5q", "Pemasok Q S5", 3 * JT, _tgl(-100))
    q2 = _tagihan("vb_s5q2", "sup_s5q", "Pemasok Q S5", 2 * JT, _tgl(10), ent=KANDA)
    await db.vendor_bills.insert_many([dict(b) for b in (t1, t2, t3, t9, q1, q2)])
    cb = cbs.recompute({"id": "cbn_s5", "number": "KB-S5", "entity_id": KSC, "supplier_id": "sup_s5p",
                        "supplier_name": "Pemasok P S5", "status": "approved", "created_at": now_iso(),
                        "timeline": [], "payments": [], "decisions": [], "deductions": [],
                        "bills": [{"bill_id": t3["id"], "bill_number": t3["bill_number"],
                                   "applied_amount": t3["grand_total"], "settled_amount": 0.0, "po_id": None}]})
    await db.contra_bons.insert_one(dict(cb))
    await db.purchase_returns.insert_one({"id": "pr_s5", "number": "RB-S5", "debit_note_number": "ND-S5",
                                          "supplier_id": "sup_s5p", "entity_id": KSC, "status": "approved",
                                          "supplier_outcome": "ap_credit", "grand_total": 300_000.0,
                                          "total_amount": 270_270.0, "po_number": "PO-S5", "created_at": now_iso()})
    return {"P": "sup_s5p", "Q": "sup_s5q", "T1": t1["id"], "T2": t2["id"], "T3": t3["id"]}


def _baris(j: dict, sid: str, ent: str = KSC) -> dict:
    rows = [r for r in j["rows"] if r["supplier_id"] == sid and r["entity_id"] == ent]
    assert len(rows) == 1, j["rows"]
    return rows[0]


async def test_S5_U1_daftar_per_pemasok_ksc(klien, kepala_admin, data):
    r = await klien.get("/api/vendor-bills/payables/by-supplier", headers=kepala_admin, params={"entity_id": KSC})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["combined"] is False
    p = _baris(j, data["P"])
    assert p["bill_count"] == 3 and p["outstanding"] == 7.5 * JT
    assert p["aging"] == {"not_due": 3.5 * JT, "1-30": 0.0, "31-60": 4 * JT, "61-90": 0.0, ">90": 0.0}
    assert p["overdue"] == 4 * JT and p["max_days_past_due"] == 45 and p["nearest_due"] == _tgl(-45)
    assert p["held_count"] == 1 and p["held_outstanding"] == 2.5 * JT
    assert p["debit_notes"] == 300_000.0 and p["debit_note_count"] == 1 and p["advance"] == 0.0
    q = _baris(j, data["Q"])
    assert q["outstanding"] == 3 * JT and q["aging"][">90"] == 3 * JT
    ids = [x["supplier_id"] for x in j["rows"]]
    assert ids.index(data["P"]) < ids.index(data["Q"])          # lewat jatuh tempo terbesar dulu
    s = (await klien.get("/api/vendor-bills/payables/summary", headers=kepala_admin, params={"entity_id": KSC})).json()
    assert j["totals"]["outstanding"] == s["total_outstanding"]  # satu pembaca tagihan terbuka
    assert j["totals"]["aging"] == s["aging"]


async def test_S5_U2_semua_pt_tidak_dijumlah(klien, kepala_admin, data):
    j = (await klien.get("/api/vendor-bills/payables/by-supplier", headers=kepala_admin,
                         params={"entity_id": "all"})).json()
    assert j["combined"] is True
    assert _baris(j, data["Q"], KSC)["outstanding"] == 3 * JT
    assert _baris(j, data["Q"], KANDA)["outstanding"] == 2 * JT
    assert _baris(j, data["Q"], KANDA)["entity_label"] != KANDA   # nama PT, bukan kode


async def test_S5_U3_rincian_pemasok(klien, kepala_admin, data):
    r = await klien.get(f"/api/vendor-bills/payables/by-supplier/{data['P']}", headers=kepala_admin,
                        params={"entity_id": KSC})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [b["bill_id"] for b in j["bills"]] == [data["T1"], data["T2"], data["T3"]]   # jatuh tempo terdekat dulu
    t1, t3 = j["bills"][0], j["bills"][2]
    assert t1["aging_bucket"] == "31-60" and t1["days_past_due"] == 45 and t1["contra_bon"] is None
    assert t3["contra_bon"]["number"] == "KB-S5"
    assert t1["payment_tolerance"] is not None
    assert [c["number"] for c in j["contra_bons"]] == ["KB-S5"] and j["contra_bons"][0]["payable"] is True
    assert [c["ref_number"] for c in j["credits"]] == ["ND-S5"] and j["credits"][0]["amount"] == 300_000.0
    assert j["totals"]["payable_direct"] == 5 * JT and j["totals"]["held"] == 2.5 * JT
    assert j["totals"]["outstanding"] == 7.5 * JT and j["totals"]["overdue"] == 4 * JT
    r404 = await klien.get("/api/vendor-bills/payables/by-supplier/sup_tidak_ada", headers=kepala_admin)
    assert r404.status_code == 404


async def test_S5_U4_izin(klien, data, akun, sesi, peran_tanpa_acuan):
    lihat = await peran_tanpa_acuan({"vendor_bill": ["view"]}, label="S5 lihat tagihan")
    h = await sesi(await akun(lihat))
    assert (await klien.get("/api/vendor-bills/payables/by-supplier", headers=h)).status_code == 200
    j = (await klien.get(f"/api/vendor-bills/payables/by-supplier/{data['P']}", headers=h)).json()
    assert j["contra_bons"] is None and len(j["bills"]) == 3   # tanpa contra_bon.view: kontrabon tidak dikirim
    tanpa = await peran_tanpa_acuan({"contra_bon": ["view"]}, label="S5 tanpa tagihan")
    h2 = await sesi(await akun(tanpa))
    assert (await klien.get("/api/vendor-bills/payables/by-supplier", headers=h2)).status_code == 403
    assert (await klien.get(f"/api/vendor-bills/payables/by-supplier/{data['P']}", headers=h2)).status_code == 403


async def test_S5_U5_bayar_beberapa_lewat_pintu_yang_ada(klien, kepala_admin, db, data):
    h0 = await saldo_akun("2-1100", KSC)
    body = {"paid_at": now_iso()[:10], "bank_account_id": "rek_s5", "method": "transfer",
            "notes": "Bayar beberapa tagihan sekaligus"}
    kunci = {data["T1"]: "vbpay-s5-t1", data["T2"]: "vbpay-s5-t2"}
    for bid, nominal in ((data["T1"], 4 * JT), (data["T2"], 1 * JT)):
        r = await klien.post(f"/api/vendor-bills/{bid}/pay", json={**body, "amount": nominal},
                             headers={**kepala_admin, "Idempotency-Key": kunci[bid]})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paid"
    kas = await db.cash_transactions.find({"ref_id": {"$in": list(kunci)}, "status": {"$ne": "void"}},
                                          {"_id": 0}).to_list(None)
    assert sorted(k["amount"] for k in kas) == [1 * JT, 4 * JT]
    for k in kas:
        assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": k["id"]}) == 1
    # 2-1100 bersaldo normal kredit: dua pembayaran mendebit hutang → saldo turun 5.000.000.
    assert round(await saldo_akun("2-1100", KSC) - h0, 2) == -5 * JT
    # Kirim ulang T1 dengan kunci yang sama (klik ganda / jaringan putus) → diputar ulang, tidak ada kas baru.
    r = await klien.post(f"/api/vendor-bills/{data['T1']}/pay", json={**body, "amount": 4 * JT},
                         headers={**kepala_admin, "Idempotency-Key": kunci[data["T1"]]})
    assert r.status_code == 200, r.text
    assert await jumlah("cash_transactions", {"ref_id": data["T1"], "status": {"$ne": "void"}}) == 1
    # Tagihan yang dipegang kontrabon tetap ditolak pintu bayar langsung (layar menulis "Bayar lewat kontrabon").
    r = await klien.post(f"/api/vendor-bills/{data['T3']}/pay", json={**body, "amount": 2.5 * JT},
                         headers={**kepala_admin, "Idempotency-Key": "vbpay-s5-t3"})
    assert r.status_code == 409 and "kontrabon" in r.text
    j = (await klien.get("/api/vendor-bills/payables/by-supplier", headers=kepala_admin,
                         params={"entity_id": KSC})).json()
    p = _baris(j, data["P"])
    assert p["outstanding"] == 2.5 * JT and p["bill_count"] == 1 and p["overdue"] == 0.0
