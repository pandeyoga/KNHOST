"""MN-T3 — satu form pembayaran, kartu pelanggan, kartu pemasok (docs/blueprint/unit/MN-T3.md, uji lapis B U3, U4,
U8–U14; U1, U2, U5, U6, U15, U16 = uji komponen jest `features/__tests__/mnt3SatuForm.test.js`; U7 = statik
`test_MNT3_U7_satu_pintu_layar.py`; U17 = penjaga; U18 = uji jalan integrator).

Persiapan (FIXTURE = disisipkan langsung; ALUR = lewat API):
  * pelanggan **C** (`ent_ksc`, milik sales `sales@kainnusantara.id`) dengan satu pesanan bersisa 8.000.000 — FIXTURE;
    pelanggan **C3** berbentuk sama khusus U3 (supaya kwitansi U3 tidak mengubah hitungan U11) — FIXTURE;
    pelanggan **D** (`ent_ksc`) pengecoh ber-denda & ber-kasus — FIXTURE;
  * satu kwitansi C 1.000.000 + kas masuk + jurnalnya (bentuk `_post_cash_transaction`) — FIXTURE;
  * nota denda C dan D, kasus keuangan C dan D — FIXTURE;
  * pemasok **S** (`ent_ksc`): tagihan terposting T1 7.000.000 dan T2 3.000.000 — FIXTURE; T2 dibayar 2.000.000 lewat
    `POST /api/vendor-bills/{T2}/pay` — ALUR; pemasok **S4** (khusus U4): tagihan 7.000.000 dan satu kontrabon
    disetujui berisi tagihan 4.000.000 — FIXTURE; rekening bank `ent_ksc` lewat `POST /api/bank-accounts` — ALUR.
  * Isi permintaan form A dan form B = berkas bersama `frontend/src/features/finance/payments/__tests__/fixtures/
    mnt3_isi_form.json` (jest memastikan form mengirim isi itu persis).

Hitung tangan:
  U3   C3 (pesanan sudah dikirim) bersisa 8.000.000; kwitansi 5.000.000 "tertua dulu" (tanpa `allocations`) →
       seluruhnya ke satu-satunya pesanan → sisa 8.000.000 − 5.000.000 = 3.000.000; rekening kwitansi = rekening yang
       dipilih form; jurnal kas Dr kas/bank 5.000.000 / Cr 1-1200 Piutang 5.000.000 (contoh angka `00` §9).
  U4   S4: bayar tagihan 7.000.000 penuh → satu kas keluar 7.000.000 dari rekening dipilih; sisa 0 → `paid`. Kontrabon
       berisi tagihan 4.000.000 tanpa potongan → bersih 4.000.000; bayar 4.000.000 → satu kas keluar; tagihannya lunas.
  U12  saldo hutang S = 7.000.000 + 3.000.000 − 2.000.000 = 8.000.000; pembayaran = 1 baris 2.000.000.
  U14  S punya 2 tagihan → 2 baris; pemasok lain tanpa tagihan → 0 baris.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
SALES = "sales@kainnusantara.id"
S: dict = {}
FIXTURE_FORM = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "features", "finance",
                            "payments", "__tests__", "fixtures", "mnt3_isi_form.json")
NOMINAL_KUNCI = {"credit_limit", "ar_outstanding", "ar_ledger", "outstanding", "exposure", "overdue_amount",
                 "available_credit", "deposit_balance", "lifetime_value", "grand_total", "paid", "amount"}


def _id(awal: str) -> str:
    return f"{awal}_mnt3_{uuid.uuid4().hex[:8]}"


def _isi(nama: str, ganti: dict) -> dict:
    with open(FIXTURE_FORM, encoding="utf-8") as fh:
        body = json.load(fh)[nama]
    return {k: (ganti.get(v, v) if isinstance(v, str) else v) for k, v in body.items()}


async def _pelanggan(db, nama: str, *, ent: str = KSC, sales_id: str = "") -> str:
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": nama, "code": cid[-6:].upper(), "entity_id": ent,
                                   "status": "active", "assigned_sales_id": sales_id, "payment_profile": {},
                                   "deposit_balance": 0.0, "credit_limit": 50 * JT})
    return cid


async def _pesanan(db, cid: str, nama: str, total: float, *, status: str = "confirmed") -> dict:
    so = {"id": _id("so"), "number": f"SO-MNT3-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": cid,
          "customer_name": nama, "status": status, "grand_total": float(total), "total_amount": float(total),
          "payments": [], "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "NET30",
          "created_at": now_iso(), "items": []}
    await db.sales_orders.insert_one(dict(so))
    return so


def _tagihan(bid: str, sup: str, total: float, *, ent: str = KSC) -> dict:
    return {"id": bid, "bill_number": f"VB-{bid[-6:].upper()}", "entity_id": ent, "supplier_id": sup,
            "supplier_name": f"Pemasok {sup[-4:]}", "status": "posted", "grand_total": float(total),
            "subtotal": float(total), "amount_paid": 0.0, "payments": [], "timeline": [], "po_id": None,
            "bill_date": "2026-11-01", "due_date": "2026-12-01", "created_at": now_iso()}


@pytest.fixture(scope="module")
async def data(klien, db, kepala_admin):
    if S:
        return S
    sales = await db.users.find_one({"email": SALES}, {"_id": 0})
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "name": "BCA Operasional MN-T3", "account_number": "777-000-0303",
        "holder_name": "PT Kain Suka Cita", "purposes": ["penerimaan_pelanggan"], "payment_method_codes": ["transfer"],
        "entity_id": KSC})
    assert r.status_code == 200, r.text
    rek = r.json()["id"]
    c = await _pelanggan(db, "Toko C MN-T3", sales_id=sales["id"])
    so_c = await _pesanan(db, c, "Toko C MN-T3", 8 * JT)
    c3 = await _pelanggan(db, "Toko C3 MN-T3", sales_id=sales["id"])
    # C3 sudah dikirim (piutang): kwitansinya mengkredit akun piutang, bukan uang muka pesanan belum dikirim.
    so_c3 = await _pesanan(db, c3, "Toko C3 MN-T3", 8 * JT, status="shipped")
    d = await _pelanggan(db, "Toko D MN-T3")
    from services import gl_service as gl
    # FIXTURE — surat jalan C3 + jurnal pengakuan (Dr 1-1200 Piutang 8.000.000 / Cr 4-1000 Penjualan) bentuk
    # `post_shipment_revenue`: piutangnya sudah lahir, sehingga kwitansi U3 mengkredit piutang (bukan uang muka).
    shp = _id("shp")
    await db.shipments.insert_one({"id": shp, "shipment_no": "SJ-MNT3-1", "order_id": so_c3["id"], "entity_id": KSC,
                                   "status": "dispatched", "created_at": now_iso()})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": 8.0 * JT, "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": 8.0 * JT}],
                           description="uji MN-T3 surat jalan C3", date=now_iso(), source_type="shipment_revenue",
                           source_id=shp, entity_id=KSC, created_by="system", source_label="SJ-MNT3-1",
                           ref={"order_id": so_c3["id"], "order_number": so_c3["number"]})
    # FIXTURE — kwitansi C 1.000.000 + kas masuk + jurnal (Dr kas / Cr piutang), tidak dialokasikan ke pesanan C.
    rid, tid = _id("arr"), _id("cash")
    await db.ar_receipts.insert_one({"id": rid, "number": "KW-MNT3-1", "customer_id": c, "customer_name": "Toko C MN-T3",
                                     "entity_id": KSC, "amount": 1.0 * JT, "method": "transfer",
                                     "receipt_date": now_iso(), "status": "posted", "allocations": [],
                                     "created_at": now_iso()})
    await db.cash_transactions.insert_one({"id": tid, "number": "KAS-KW-MNT3-1", "ref_type": "ar_receipt",
                                           "ref_id": rid, "entity_id": KSC, "direction": "in", "amount": 1.0 * JT,
                                           "status": "posted", "txn_date": now_iso()[:10], "account_id": rek})
    await gl._insert_entry(lines=[{"account_code": "1-1100", "debit": 1.0 * JT, "credit": 0.0},
                                  {"account_code": "1-1200", "debit": 0.0, "credit": 1.0 * JT}],
                           description="uji MN-T3 kwitansi C", date=now_iso(), source_type="cash_transaction",
                           source_id=tid, entity_id=KSC, created_by="system", source_label="KAS-KW-MNT3-1", ref={})
    for cus, nama in ((c, "Toko C MN-T3"), (d, "Toko D MN-T3")):
        await db.penalties.insert_one({"id": _id("pen"), "number": f"DN-{cus[-5:]}", "entity_id": KSC,
                                       "customer_id": cus, "customer_name": nama, "status": "draft",
                                       "amount": 50_000.0, "created_at": now_iso()})
        await db.finance_cases.insert_one({"id": _id("fcs"), "number": f"KS-{cus[-5:]}", "entity_id": KSC,
                                           "customer_id": cus, "status": "open", "case_type": "lebih_bayar",
                                           "amount": 100_000.0, "created_at": now_iso()})
    # Pemasok S (U12–U14) dan S4 (U4).
    sup, sup4, sup_lain = _id("sup"), _id("sup"), _id("sup")
    for sid in (sup, sup4, sup_lain):
        await db.suppliers.insert_one({"id": sid, "name": f"Pemasok {sid[-4:]}", "code": sid[-6:].upper(),
                                       "entity_id": KSC, "status": "active"})
    t1, t2 = _tagihan(_id("vb"), sup, 7 * JT), _tagihan(_id("vb"), sup, 3 * JT)
    t4, t4k = _tagihan(_id("vb"), sup4, 7 * JT), _tagihan(_id("vb"), sup4, 4 * JT)
    await db.vendor_bills.insert_many([dict(t1), dict(t2), dict(t4), dict(t4k)])
    from services import contra_bon_service as cbs
    cbid = _id("cbn")
    cb = cbs.recompute({"id": cbid, "number": "CB-MNT3-1", "entity_id": KSC, "supplier_id": sup4,
                        "supplier_name": t4k["supplier_name"], "status": "approved", "created_at": now_iso(),
                        "timeline": [], "payments": [], "decisions": [], "deductions": [],
                        "bills": [{"bill_id": t4k["id"], "bill_number": t4k["bill_number"],
                                   "applied_amount": t4k["grand_total"], "settled_amount": 0.0, "po_id": None}]})
    await db.contra_bons.insert_one(dict(cb))
    # ALUR — T2 dibayar 2.000.000.
    r = await klien.post(f"/api/vendor-bills/{t2['id']}/pay", headers={**kepala_admin, "Idempotency-Key": _id("k")},
                         json={"amount": 2.0 * JT, "paid_at": now_iso()[:10], "bank_account_id": rek,
                               "method": "transfer"})
    assert r.status_code == 200, r.text
    S.update({"rek": rek, "C": c, "SO_C": so_c, "C3": c3, "SO_C3": so_c3, "D": d, "S": sup, "S4": sup4,
              "S_lain": sup_lain, "T1": t1["id"], "T2": t2["id"], "T4": t4["id"], "T4K": t4k["id"], "CB": cbid})
    return S


# ─── Form A / form B → pintu yang sudah ada ─────────────────────────────────────────────────────────────────────────

async def test_MNT3_U3_isi_form_terima_ke_pintu_kwitansi(klien, db, kepala_admin, data):
    body = _isi("terima", {"{C}": data["C3"], "{REK}": data["rek"], "{TANGGAL_ISO}": now_iso()})
    r = await klien.post("/api/ar-receipts", headers={**kepala_admin, "Idempotency-Key": _id("k")}, json=body)
    assert r.status_code == 200, r.text
    rows = await db.ar_receipts.find({"customer_id": data["C3"], "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)
    assert len(rows) == 1, rows
    so = await db.sales_orders.find_one({"id": data["SO_C3"]["id"]}, {"_id": 0})
    # 8.000.000 − 5.000.000 = 3.000.000
    assert round(float(so["grand_total"]) - float(so.get("paid_total") or 0), 2) == 3 * JT
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rows[0]["id"]}, {"_id": 0})
    assert kas and kas["account_id"] == data["rek"], kas
    # Contoh angka (`00` §9): kwitansi 5.000.000 → kas masuk 5.000.000 → jurnal Dr kas/bank 5.000.000 / Cr piutang
    # 5.000.000 → sisa piutang pesanan 8.000.000 − 5.000.000 = 3.000.000.
    assert kas["amount"] == 5 * JT
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"]}, {"_id": 0})
    assert je, "jurnal kas kwitansi tidak ada"
    debit = {ln["account_code"]: ln["debit"] for ln in je["lines"] if ln.get("debit")}
    kredit = {ln["account_code"]: ln["credit"] for ln in je["lines"] if ln.get("credit")}
    assert sum(debit.values()) == 5 * JT and kredit.get("1-1200") == 5 * JT, je["lines"]
    print("CONTOH_ANGKA", kas.get("number"), je.get("number"), debit, kredit)


async def test_MNT3_U4_isi_form_bayar_ke_pintu_tagihan_dan_kontrabon(klien, db, kepala_admin, data):
    hari = now_iso()[:10]
    body = _isi("bayar", {"{REK}": data["rek"], "{TANGGAL}": hari})
    r = await klien.post(f"/api/vendor-bills/{data['T4']}/pay", headers={**kepala_admin, "Idempotency-Key": _id("k")},
                         json=body)
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find({"ref_id": data["T4"]}, {"_id": 0}).to_list(10)
    assert len(kas) == 1 and kas[0]["account_id"] == data["rek"] and kas[0]["amount"] == 7 * JT, kas
    assert (await db.vendor_bills.find_one({"id": data["T4"]}))["status"] == "paid"
    # Bentuk isi yang sama untuk kontrabon (nominal = sisa bersih kontrabon).
    body_cb = {**body, "amount": 4.0 * JT}
    r = await klien.post(f"/api/contra-bons/{data['CB']}/pay", headers={**kepala_admin, "Idempotency-Key": _id("k")},
                         json=body_cb)
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find({"ref_id": data["CB"]}, {"_id": 0}).to_list(10)
    assert len(kas) == 1 and kas[0]["account_id"] == data["rek"] and kas[0]["amount"] == 4 * JT, kas
    assert (await db.vendor_bills.find_one({"id": data["T4K"]}))["status"] == "paid"


# ─── Kartu pelanggan ───────────────────────────────────────────────────────────────────────────────────────────────

def _nominal_terisi(obj, jalur="") -> list:
    """Kunci nominal piutang/plafon yang bernilai angka bukan nol di mana pun dalam jawaban."""
    temu = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in NOMINAL_KUNCI and isinstance(v, (int, float)) and not isinstance(v, bool) and v:
                temu.append(f"{jalur}.{k}")
            temu += _nominal_terisi(v, f"{jalur}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            temu += _nominal_terisi(v, f"{jalur}[{i}]")
    return temu


async def test_MNT3_U8_customer_view_saja_tanpa_nominal(klien, data, peran_tanpa_acuan, akun, sesi):
    rid = await peran_tanpa_acuan({"customer": ["view"]}, label="MN-T3 lihat pelanggan")
    h = await sesi(await akun(rid))
    r = await klien.get(f"/api/customers/{data['C']}/360", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["name"] == "Toko C MN-T3" and j["id"] == data["C"]
    assert j["sections_allowed"] == []
    assert j.get("credit") is None and j.get("payments") is None and j.get("order_history") is None
    assert _nominal_terisi(j) == [], _nominal_terisi(j)


async def test_MNT3_U8b_admin_semua_bagian(klien, kepala_admin, data):
    j = (await klien.get(f"/api/customers/{data['C']}/360", headers=kepala_admin)).json()
    assert j["sections_allowed"] == ["ringkasan", "tagihan", "pembayaran", "denda_kasus", "tindak_lanjut",
                                     "rekening_koran", "riwayat"]
    assert j["credit"]["credit_limit"] is not None and isinstance(j["order_history"], list)


async def test_MNT3_U9_sales_lain_ditolak(klien, data, akun, sesi):
    h = await sesi(await akun("sales"))
    r = await klien.get(f"/api/customers/{data['C']}/360", headers=h)
    assert r.status_code == 403, r.text
    h_pemilik = await sesi(SALES)
    assert (await klien.get(f"/api/customers/{data['C']}/360", headers=h_pemilik)).status_code == 200


async def test_MNT3_U10_pt_lain_tanpa_angka(klien, data, akun, sesi):
    h = await sesi(await akun("finance", entitas=(KANDA,)), entitas=KANDA)
    r = await klien.get(f"/api/customers/{data['C']}/360", headers=h)
    assert r.status_code in (403, 404), r.text
    assert "1000000" not in r.text and "8000000" not in r.text
    r = await klien.get("/api/ar-receipts", headers=h, params={"customer_id": data["C"]})
    assert r.status_code == 200 and r.json() == [], r.text


async def test_MNT3_U11_saringan_pelanggan(klien, kepala_admin, data):
    r = await klien.get("/api/ar-receipts", headers=kepala_admin, params={"customer_id": data["C"]})
    rows = r.json()
    assert len(rows) == 1 and rows[0]["amount"] == 1 * JT, rows
    r = await klien.get("/api/penalties", headers=kepala_admin, params={"customer_id": data["C"]})
    items = r.json()["items"]
    assert items and {p["customer_id"] for p in items} == {data["C"]}, items


async def test_MNT3_X1_kasus_per_pelanggan(klien, kepala_admin, data):
    """Parameter baru `customer_id` pada `GET /api/finance-cases` (bagian Denda & Kasus)."""
    rows = (await klien.get("/api/finance-cases", headers=kepala_admin, params={"customer_id": data["C"]})).json()
    assert rows and {c["customer_id"] for c in rows} == {data["C"]}, rows
    semua = (await klien.get("/api/finance-cases", headers=kepala_admin)).json()
    assert data["D"] in {c["customer_id"] for c in semua}


# ─── Kartu pemasok ─────────────────────────────────────────────────────────────────────────────────────────────────

async def test_MNT3_U12_kartu_pemasok_hutang_dan_pembayaran(klien, kepala_admin, data):
    r = await klien.get(f"/api/suppliers/{data['S']}/360", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    # 7.000.000 + 3.000.000 − 2.000.000 = 8.000.000
    assert j["payables"]["outstanding"] == 8 * JT, j["payables"]
    assert j["payables"]["entity_id"] == KSC and j["payables"]["by_entity"][0]["outstanding"] == 8 * JT
    # Cek layar integrator: label PT = nama dari `business_entities`, bukan kode mentah ("PT ent_ksc" di kepala kartu).
    assert all(e["label"] != e["entity_id"] for e in j["scope_entities"]), j["scope_entities"]
    assert j["payables"]["by_entity"][0]["label"] != KSC, j["payables"]["by_entity"]
    assert [p["amount"] for p in j["payments"]] == [2 * JT]
    assert {b["id"] for b in j["bills"]} == {data["T1"], data["T2"]}
    assert j["contra_bons"] == [] and j["landed_costs"] == []
    assert set(j["sections_allowed"]) >= {"ringkasan", "tagihan", "kontrabon", "pembayaran", "lainnya"}


async def test_MNT3_U13_supplier_view_saja_bagian_keuangan_null(klien, data, peran_tanpa_acuan, akun, sesi):
    rid = await peran_tanpa_acuan({"supplier": ["view"]}, label="MN-T3 lihat pemasok")
    h = await sesi(await akun(rid))
    r = await klien.get(f"/api/suppliers/{data['S']}/360", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("payables", "bills", "contra_bons", "payments", "landed_costs"):
        assert j[k] is None, k
    assert j["sections_allowed"] == ["lainnya"]
    assert j.get("vendor_bills") is None and (j.get("finance") or {}).get("ap_outstanding") is None
    assert all(d.get("doc_type") != "vendor_bill" for d in j.get("documents") or [])


async def test_MNT3_U14_tagihan_per_pemasok(klien, kepala_admin, data):
    r = await klien.get("/api/vendor-bills", headers=kepala_admin, params={"supplier_id": data["S"]})
    assert r.status_code == 200 and len(r.json()) == 2, r.text
    r = await klien.get("/api/vendor-bills", headers=kepala_admin, params={"supplier_id": data["S_lain"]})
    assert r.status_code == 200 and r.json() == [], r.text
