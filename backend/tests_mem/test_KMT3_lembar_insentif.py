"""KM-T3 — Lembar Insentif: dokumen keputusan dengan nominal diketik dan angka dasar dipotret (lingkungan B).

Spesifikasi `docs/blueprint/unit/KM-T3.md`, uji penerimaan U1–U15 (U16 = lapis A `tests/test_bp_KMT3_lembar_bersamaan_mongo.py`;
U17 = uji jalan peramban oleh integrator; komponen layar di `features/__tests__/kmt3LembarInsentif.test.js`).

Fixture **F3** di `ent_kanda` (non-PKP, tahun buku kalender) = fixture F2 KM-T2 (`test_KMT2_capaian.py`): pesanan, surat
jalan, retur & nota kredit DISISIPKAN langsung; jurnal pendapatan lewat `gl_service.post_order_revenue_and_cogs` /
`post_sales_return`; kwitansi lewat `ar_receipt_service.create_receipt`; target lewat `incentive_targets.save_target`;
komponen lewat `incentive_targets.create_component`; fakta lewat `incentive_facts.rebuild`. Lembar lewat API.

Angka capaian F3 (hitung tangan di `test_KMT2_capaian.py`, diulang di sini):
  Andi Okt 2026: target omzet 800 jt · omzet 1.000 jt (OA1 terkirim 12 Okt) · target cair 750 jt · uang masuk 700 jt
                 (RA1) · realisasi harga 1.000 / 1.160 = 86,21 → 86,2 %
  Andi 2026-Q3 : 2.400 jt · 2.600 jt (OA0 14 Agu) · 2.250 jt · 2.300 jt (RA0 10 Sep) · 2.600 / 2.953,6 = 88,03 → 88,0 %
  Budi Okt 2026: 500 jt · 500 jt (OB1) · 450 jt · 500 + 20 = 520 jt (RB1, RB0) · 100,0 %
Nominal (DIKETIK, U1): Andi BLN 2.000.000 + Andi TW 3.000.000 + Budi BLN 3.500.000 = 8.500.000.
U7: Budi dikoreksi 3.500.000 → 3.000.000 → total 2.000.000 + 3.000.000 + 3.000.000 = 8.000.000.
U4: nota kredit retur 50 jt atas OA1 bertanggal 25 Okt → omzet bersih Andi Okt sekarang 1.000 − 50 = 950 jt; potret tetap
    1.000 jt; selisih −50.000.000.
U5: nota kredit retur 30 jt atas OA0 bertanggal 20 Sep → omzet bersih Andi Sep 0 − 30 jt = −30.000.000 (sebelumnya 0).
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI

pytestmark = pytest.mark.anyio

KANDA, KSC = "ent_kanda", "ent_ksc"
PRD = "prd_kmt3_kain"
CA, CB = "cus_kmt3_andi", "cus_kmt3_budi"
OA0, OA1, OB0, OB1 = "so_kmt3_oa0", "so_kmt3_oa1", "so_kmt3_ob0", "so_kmt3_ob1"
REK = "rek_kmt3_b"
URL = "/api/incentive/sheets"
#: Keadaan bersama antar-uji (modul berjalan berurutan di satu pekerja, `--dist loadscope`).
K: Dict[str, Any] = {}


def _iso(tgl: str, jam: str = "03:00:00") -> str:
    return f"{tgl}T{jam}+00:00"


def _item(qty: int, list_price: float) -> Dict[str, Any]:
    return {"product_id": PRD, "sku": "KMT3-01", "product_name": "Kain Uji KM-T3", "quantity": qty, "base_quantity": qty,
            "unit": "yard", "base_unit": "yard", "price": 50_000, "line_total": qty * 50_000, "list_price": list_price,
            "list_price_source": "entity", "global_price": 60_000, "floor_price": 45_000, "unit_cost": 35_000,
            "price_source": "entity", "category": "Katun", "line_code": "woven"}


async def _pesanan_terkirim(db, gl, so_id: str, cust: str, sales_id: str, qty: int, list_price: float,
                            dibuat: str, dikirim: str) -> None:
    nomor = f"SO/KMT3/{so_id[-3:].upper()}"
    await db.sales_orders.insert_one({
        "id": so_id, "number": nomor, "entity_id": KANDA, "customer_id": cust, "customer_name": f"Toko {cust[-4:]}",
        "status": "shipped", "payment_term_code": "NET30", "items": [_item(qty, list_price)], "subtotal": qty * 50_000,
        "grand_total": qty * 50_000, "ppn_amount": 0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
        "sales_team": [{"sales_id": sales_id, "role": "pic", "split_pct": 100.0}],
        "created_at": _iso(dibuat), "updated_at": now_iso()})
    await db.shipments.insert_one({"id": f"shp_{so_id}", "shipment_no": f"SJ/KMT3/{so_id[-3:].upper()}",
                                   "entity_id": KANDA, "order_id": so_id, "order_number": nomor, "product_id": PRD,
                                   "qty": qty, "unit": "yard", "status": "dispatched", "created_at": _iso(dikirim)})
    await gl.post_order_revenue_and_cogs(so_id)


async def _retur(db, so_id: str, cust: str, nilai: int, tgl: str, kode: str) -> None:
    """Nota kredit retur atas pesanan `so_id` bertanggal `tgl` + jurnal lewat fungsi posting asli; fakta dibangun ulang."""
    from services import gl_service as gl
    from services import incentive_facts
    ret = {"id": f"sr_kmt3_{kode}", "number": f"RJ/KMT3/{kode}", "entity_id": KANDA, "order_id": so_id,
           "order_number": f"SO/KMT3/{so_id[-3:].upper()}", "customer_id": cust, "status": "settled",
           "approved_at": _iso(tgl), "items": [], "credit_note_id": f"cn_kmt3_{kode}", "created_at": _iso(tgl, "02:00:00")}
    await db.sales_returns.insert_one(dict(ret))
    await db.credit_notes.insert_one({
        "id": f"cn_kmt3_{kode}", "number": f"CN/KMT3/{kode}", "return_id": ret["id"], "order_id": so_id,
        "order_number": ret["order_number"], "customer_id": cust, "entity_id": KANDA,
        "lines": [{"product_id": PRD, "quantity": nilai // 50_000, "unit": "yard", "unit_price": 50_000,
                   "line_total": nilai}],
        "net_amount": nilai, "ppn_amount": 0, "gross_amount": nilai, "cogs_amount": nilai * 7 // 10,
        "settlement": "ar", "status": "posted", "created_at": _iso(tgl, "04:00:00")})
    await gl.post_sales_return(ret, return_net=nilai, return_ppn=0, return_cogs=nilai * 7 // 10,
                               credit_note_number=f"CN/KMT3/{kode}")
    await incentive_facts.rebuild()


@pytest.fixture(scope="module")
async def f3(db, akun, sesi, peran_tanpa_acuan):
    from services import ar_receipt_service as ars
    from services import config_resolver as resolver
    from services import gl_service as gl
    from services import incentive_facts
    from services import incentive_targets as itg
    await resolver.set_value("payment.variance_tolerance_rupiah", 0, scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T3")
    await db.bank_accounts.insert_one({"id": REK, "name": "BCA Kanda KM-T3", "entity_id": KANDA, "account_type": "bank",
                                       "cash_type": "kas_besar", "is_active": True, "opening_balance": 0})
    andi = await akun("sales", entitas=(KANDA,))
    budi = await akun("sales", entitas=(KANDA,))
    for u, nama in ((andi, "Andi"), (budi, "Budi")):
        await db.users.update_one({"id": u["id"]}, {"$set": {"name": nama}})
        u["name"] = nama
    await db.products.insert_one({"id": PRD, "name": "Kain Uji KM-T3", "sku": "KMT3-01", "base_unit": "yard",
                                  "price": 60_000, "category": "Katun", "line_code": "woven", "is_active": True})
    await db.customers.insert_many([
        {"id": CA, "name": "Toko Andi KM-T3", "entity_id": KANDA, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": andi["id"], "created_at": _iso("2026-01-05"),
         "sales_team": [{"sales_id": andi["id"], "role": "pic", "split_pct": 100.0}]},
        {"id": CB, "name": "Toko Budi KM-T3", "entity_id": KANDA, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": budi["id"], "created_at": _iso("2026-10-02"),
         "sales_team": [{"sales_id": budi["id"], "role": "pic", "split_pct": 100.0}]}])
    await _pesanan_terkirim(db, gl, OA0, CA, andi["id"], 52_000, 56_800, "2026-08-03", "2026-08-14")
    await _pesanan_terkirim(db, gl, OA1, CA, andi["id"], 20_000, 58_000, "2026-09-28", "2026-10-12")
    await _pesanan_terkirim(db, gl, OB0, CB, budi["id"], 400, 50_000, "2026-09-15", "2026-09-20")
    await _pesanan_terkirim(db, gl, OB1, CB, budi["id"], 10_000, 50_000, "2026-10-05", "2026-10-09")
    for cust, so, nilai, tgl in ((CA, OA0, 2_300_000_000, "2026-09-10"), (CA, OA1, 700_000_000, "2026-10-20"),
                                 (CB, OB1, 500_000_000, "2026-10-15"), (CB, OB0, 20_000_000, "2026-10-16")):
        await ars.create_receipt({"customer_id": cust, "entity_id": KANDA, "amount": nilai, "method": "transfer",
                                  "account_id": REK, "allocations": [{"order_id": so, "amount": nilai}],
                                  "receipt_date": tgl}, AKTOR_UJI)
    for sid, pt, p, omzet, cair in ((andi["id"], "month", "2026-10", 800e6, 750e6),
                                    (andi["id"], "quarter", "2026-Q3", 2_400e6, 2_250e6),
                                    (budi["id"], "month", "2026-10", 500e6, 450e6)):
        await itg.save_target(KANDA, {"sales_id": sid, "period_type": pt, "period": p, "target_sales_amount": omzet,
                                      "target_collection_amount": cair}, AKTOR_UJI)
    bln = await itg.create_component(KANDA, {"code": "BLN", "name": "Insentif Bulanan", "basis_period_type": "month",
                                             "columns": ["omzet", "pencairan", "harga"]}, AKTOR_UJI)
    tw = await itg.create_component(KANDA, {"code": "TW", "name": "Insentif Triwulan", "basis_period_type": "quarter",
                                            "columns": ["omzet", "pencairan"]}, AKTOR_UJI)
    mati = await itg.create_component(KANDA, {"code": "LAMA", "name": "Insentif Lama", "basis_period_type": "month",
                                              "columns": ["omzet"], "is_active": False}, AKTOR_UJI)
    await incentive_facts.rebuild()
    sa = await akun(await peran_tanpa_acuan({"incentive": ["prepare"]}, label="Penyiap Lembar KM-T3"), entitas=(KANDA,))
    mgr = await akun("manager", entitas=(KANDA,))
    adm = await akun("admin", entitas=(KANDA,))
    return {"andi": andi, "budi": budi, "bln": bln, "tw": tw, "mati": mati, "sa": sa, "mgr": mgr, "adm": adm,
            "h_sa": await sesi(sa, entitas=KANDA), "h_mgr": await sesi(mgr, entitas=KANDA),
            "h_adm": await sesi(adm, entitas=KANDA)}


def _baris(f3, siapa: str, komp: str, pt: str, p: str) -> Dict[str, str]:
    return {"sales_id": f3[siapa]["id"], "component_id": f3[komp]["id"], "basis_period_type": pt, "basis_period": p}


def _line(sheet: Dict[str, Any], f3, siapa: str, komp: str, p: str) -> Dict[str, Any]:
    rows = [x for x in sheet["lines"] if x["sales_id"] == f3[siapa]["id"] and x["component_id"] == f3[komp]["id"]
            and x["basis_period"] == p and not x.get("is_adjustment")]
    assert len(rows) == 1, sheet["lines"]
    return rows[0]


async def _buat(klien, h, pay: str, lines: List[Dict[str, str]], **extra):
    return await klien.post(URL, headers=h, json={"pay_period": pay, "lines": lines, **extra})


async def _nominal(klien, h, sheet_id: str, line_id: str, amount, **extra):
    return await klien.patch(f"{URL}/{sheet_id}/lines/{line_id}", headers=h, json={"amount": amount, **extra})


def _z6(r) -> str:
    d = r.json()["detail"]
    assert d.startswith("Anda belum punya akses untuk") and "'Kinerja & Insentif'" in d, d
    assert not re.search(r"incentive\.|[a-z]+_[a-z]+", d), d
    return d


# ═══ U1 — buat lembar, potret, nominal diketik ══════════════════════════════════════════════════════════════════════
async def test_KMT3_U1_buat_lembar_potret_dan_nominal(klien, f3):
    r = await _buat(klien, f3["h_sa"], "2026-11", [_baris(f3, "andi", "bln", "month", "2026-10"),
                                                     _baris(f3, "andi", "tw", "quarter", "2026-Q3"),
                                                     _baris(f3, "budi", "bln", "month", "2026-10")])
    assert r.status_code == 200, r.text
    s = r.json()
    assert (s["status"], s["status_label"], s["entity_id"], s["pay_period"]) == ("draft", "Draf", KANDA, "2026-11")
    assert s["number"].startswith("KANDA/LIN-"), s["number"]
    # server tidak pernah mengisi nominal
    assert [x["amount"] for x in s["lines"]] == [None, None, None]
    assert s["totals"] == {"lines": 3, "amount": 0}
    a = _line(s, f3, "andi", "bln", "2026-10")
    p = a["snapshot"]
    assert (p["omzet"], p["target_sales"], p["uang_masuk"], p["realisasi_harga_pct"]) == (
        1_000_000_000, 800_000_000, 700_000_000, 86.2), p
    assert (p["retur"], p["omzet_bersih"], p["pct_omzet"], p["target_collection"], p["pct_pencairan"]) == (
        0, 1_000_000_000, 125.0, 750_000_000, 93.3), p
    assert (p["definition"]["dasar_omzet"], p["definition_version"] >= 1, len(p["fingerprint"])) == ("terkirim", True, 64)
    assert p["source_counts"] == {"omzet": 1, "retur": 0, "uang_masuk": 1}
    assert (a["basis_label"], a["component_name"], a["sales_name"]) == ("Okt 2026", "Insentif Bulanan", "Andi")
    assert "margin_pct" not in p   # penyiap tanpa `incentive.view_margin`
    tw = _line(s, f3, "andi", "tw", "2026-Q3")["snapshot"]
    assert (tw["target_sales"], tw["omzet"], tw["target_collection"], tw["uang_masuk"], tw["realisasi_harga_pct"]) == (
        2_400_000_000, 2_600_000_000, 2_250_000_000, 2_300_000_000, 88.0), tw
    assert _line(s, f3, "andi", "tw", "2026-Q3")["basis_label"] == "Triwulan III 2026"
    b = _line(s, f3, "budi", "bln", "2026-10")["snapshot"]
    assert (b["target_sales"], b["omzet"], b["target_collection"], b["uang_masuk"], b["realisasi_harga_pct"]) == (
        500_000_000, 500_000_000, 450_000_000, 520_000_000, 100.0), b
    # nominal diketik penyiap
    for siapa, komp, per, nominal in (("andi", "bln", "2026-10", 2_000_000), ("andi", "tw", "2026-Q3", 3_000_000),
                                      ("budi", "bln", "2026-10", 3_500_000)):
        r = await _nominal(klien, f3["h_sa"], s["id"], _line(s, f3, siapa, komp, per)["id"], nominal)
        assert r.status_code == 200, r.text
        s = r.json()
    assert s["totals"] == {"lines": 3, "amount": 8_500_000}   # 2 + 3 + 3,5 jt
    assert sorted(s["active_keys"]) == sorted(f"{x['sales_id']}|{x['component_id']}|{x['basis_period']}"
                                              for x in s["lines"])
    K["u1"] = s


async def test_KMT3_U1_galat_isian(klien, f3):
    h = f3["h_sa"]
    r = await _buat(klien, h, "2026-11", [_baris(f3, "andi", "mati", "month", "2026-10")])
    assert (r.status_code, r.json()["detail"]) == (400, "Komponen ini tidak aktif di PT yang sedang dibuka."), r.text
    r = await _buat(klien, h, "2026-11", [_baris(f3, "andi", "tw", "month", "2026-10")])
    assert r.status_code == 400 and "berperiode dasar triwulanan" in r.json()["detail"], r.text
    r = await _buat(klien, h, "2026-13", [])
    assert (r.status_code, r.json()["detail"]) == (400, "Periode bayar harus satu bulan, contoh: 2026-11."), r.text
    # Semua PT: tulis ditolak (mode gabungan hanya baca)
    r = await klien.post(URL, headers={**f3["h_mgr"], "X-Entity-Id": "all"}, json={"pay_period": "2026-11"})
    assert r.status_code in (403, 409), r.text
    # sales PT lain (N2): akun yang tidak ditugaskan di PT ini
    r = await _buat(klien, h, "2026-11", [{**_baris(f3, "andi", "bln", "month", "2026-10"), "sales_id": "usr_tidak_ada"}])
    assert (r.status_code, r.json()["detail"]) == (400, "Akun ini tidak ditugaskan di PT yang sedang dibuka."), r.text


# ═══ U2 — ajukan; lembar diajukan tidak bisa diubah ═════════════════════════════════════════════════════════════════
async def test_KMT3_U2_ajukan_lalu_kunci(klien, f3):
    s = K["u1"]
    r = await klien.post(f"{URL}/{s['id']}/submit", headers=f3["h_sa"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["submitted_by"]["id"]) == ("submitted", f3["sa"]["id"])
    r = await _nominal(klien, f3["h_sa"], s["id"], s["lines"][0]["id"], 1_000_000)
    assert (r.status_code, r.json()["detail"]) == (409, f"Lembar {s['number']} berstatus Diajukan, jadi tidak bisa diubah.")
    r = await klien.post(f"{URL}/{s['id']}/lines", headers=f3["h_sa"], json=_baris(f3, "budi", "tw", "quarter", "2026-Q3"))
    assert r.status_code == 409, r.text
    K["u1"] = j


# ═══ U14 — antrean Pusat Persetujuan ════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U14_antrean_pusat_persetujuan(klien, f3):
    r = await klien.get("/api/approvals/backlog", headers=f3["h_mgr"])
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["all_items"] if x["key"] == "incentive_sheet")
    assert (row["count"], row["label"], row["view"]) == (1, "Lembar insentif menunggu pengesahan", "incentive-sheets"), row


# ═══ U3 — sahkan (bawaan satu orang); tidak menjurnal ═══════════════════════════════════════════════════════════════
async def test_KMT3_U3_sahkan_tanpa_jurnal(klien, db, f3):
    s = K["u1"]
    n_jurnal = await db.journal_entries.count_documents({})
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f3["h_mgr"], json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["status_label"], j["approved_by"]["id"], j["totals"]["amount"]) == (
        "approved", "Disahkan", f3["mgr"]["id"], 8_500_000)
    assert await db.journal_entries.count_documents({}) == n_jurnal   # unit ini tidak menjurnal (KM-T4)
    assert [h["to_status"] for h in j["history"]] == ["draft", "submitted", "approved"]
    # pemegang `incentive.view_margin` melihat margin di potret
    assert _line(j, f3, "andi", "bln", "2026-10")["snapshot"]["margin_pct"] == 30.0
    r = await _nominal(klien, f3["h_sa"], s["id"], s["lines"][0]["id"], 1)
    assert (r.status_code, r.json()["detail"]) == (409, f"Lembar {s['number']} berstatus Disahkan, jadi tidak bisa diubah.")
    K["u1"] = j


# ═══ U8 — satu (sales, komponen, periode dasar) sekali ══════════════════════════════════════════════════════════════
async def test_KMT3_U8_baris_kembar_lintas_lembar(klien, f3):
    r = await _buat(klien, f3["h_sa"], "2026-11", [_baris(f3, "andi", "bln", "month", "2026-10")])
    assert (r.status_code, r.json()["detail"]) == (
        409, f"Andi · Insentif Bulanan · Okt 2026 sudah ada di lembar {K['u1']['number']}."), r.text
    # di lembar yang sama juga ditolak
    r = await _buat(klien, f3["h_sa"], "2026-11", [_baris(f3, "budi", "tw", "quarter", "2026-Q2"),
                                                     _baris(f3, "budi", "tw", "quarter", "2026-Q2")])
    assert r.status_code == 409 and "Budi · Insentif Triwulan · Triwulan II 2026 sudah ada di lembar" in r.json()["detail"]


# ═══ U15 — ekspor Excel ═════════════════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U15_ekspor(klien, f3):
    from openpyxl import load_workbook
    r = await klien.get(f"{URL}/{K['u1']['id']}/export", headers=f3["h_mgr"])
    assert r.status_code == 200, r.text
    assert "lembar-insentif-KANDA-LIN-" in r.headers.get("content-disposition", "")
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Lembar", "Potret"]
    rows = [[c.value for c in row] for row in wb["Lembar"].iter_rows()]
    kepala = next(i for i, x in enumerate(rows) if x[0] == "Sales")
    akhir = next(i for i, x in enumerate(rows) if x[0] == "Total")
    data = rows[kepala + 1:akhir]
    assert len(data) == 3 and sorted(x[8] for x in data) == [2_000_000, 3_000_000, 3_500_000], data
    assert rows[akhir][8] == 8_500_000
    potret = [[c.value for c in row] for row in wb["Potret"].iter_rows()]
    assert any(1_000_000_000 in x for x in potret[1:]), potret
    assert "Margin (%)" in potret[0]
    # tanpa `incentive.view_margin`: kolom margin tidak ikut
    r = await klien.get(f"{URL}/{K['u1']['id']}/export", headers=f3["h_sa"])
    assert r.status_code == 200
    assert "Margin (%)" not in [c.value for c in load_workbook(io.BytesIO(r.content))["Potret"][1]]


# ═══ U4 — data sumber berubah sesudah disahkan: potret tetap, `drift` tampil ════════════════════════════════════════
async def test_KMT3_U4_potret_tetap_drift_tampil(klien, db, f3):
    await _retur(db, OA1, CA, 50_000_000, "2026-10-25", "U4")
    r = await klien.get(f"{URL}/{K['u1']['id']}", headers=f3["h_mgr"])
    assert r.status_code == 200, r.text
    j = r.json()
    a = _line(j, f3, "andi", "bln", "2026-10")
    assert (a["snapshot"]["omzet_bersih"], a["snapshot"]["retur"]) == (1_000_000_000, 0)
    d = [x for x in j["drift"] if x["line_id"] == a["id"] and x["field"] == "omzet_bersih"]
    assert len(d) == 1 and (d[0]["snapshot"], d[0]["current"], d[0]["diff"]) == (
        1_000_000_000, 950_000_000, -50_000_000), j["drift"]
    # baris lain tidak berubah (retur di Oktober, Andi; triwulan III tidak tersentuh)
    assert {x["line_id"] for x in j["drift"]} == {a["id"]}, j["drift"]
    assert j["status"] == "approved" and j["totals"]["amount"] == 8_500_000


# ═══ U11 — definisi berubah sesudah disahkan: potret tetap ══════════════════════════════════════════════════════════
async def test_KMT3_U11_definisi_berubah_potret_tetap(klien, f3):
    from services import config_resolver as resolver
    v0 = _line(K["u1"], f3, "andi", "bln", "2026-10")["snapshot"]["definition_version"]
    await resolver.set_value("insentif.dasar_omzet", "pesanan", scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T3 U11")
    try:
        r = await klien.get("/api/incentive/definitions/current", headers=f3["h_mgr"])
        assert r.json()["version"] == v0 + 1   # versi baru PT lahir
        r = await klien.get(f"{URL}/{K['u1']['id']}", headers=f3["h_mgr"])
        assert r.status_code == 200, r.text
        for x in r.json()["lines"]:
            assert (x["snapshot"]["definition_version"], x["snapshot"]["definition"]["dasar_omzet"]) == (v0, "terkirim")
    finally:
        await resolver.clear_layer("insentif.dasar_omzet", scope_type="entity", scope_id=KANDA, actor="uji",
                                   reason="uji KM-T3 U11 selesai")


# ═══ U5 — segarkan angka dasar lembar draf ══════════════════════════════════════════════════════════════════════════
async def test_KMT3_U5_segarkan_draf(klien, db, f3):
    r = await _buat(klien, f3["h_sa"], "2026-11", [_baris(f3, "andi", "bln", "month", "2026-09")])
    assert r.status_code == 200, r.text
    s = r.json()
    ln = _line(s, f3, "andi", "bln", "2026-09")
    assert (ln["snapshot"]["omzet_bersih"], ln["snapshot"]["uang_masuk"]) == (0, 2_300_000_000)
    r = await klien.post(f"{URL}/{s['id']}/refresh", headers=f3["h_sa"])
    assert r.status_code == 200 and r.json()["changed"] == [], r.text   # belum ada yang berubah
    await _retur(db, OA0, CA, 30_000_000, "2026-09-20", "U5")
    r = await klien.post(f"{URL}/{s['id']}/refresh", headers=f3["h_sa"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["changed"] == [ln["id"]], j
    p = _line(j["sheet"], f3, "andi", "bln", "2026-09")["snapshot"]
    assert (p["retur"], p["omzet_bersih"], p["source_counts"]["retur"]) == (30_000_000, -30_000_000, 1), p
    assert p["fingerprint"] != ln["snapshot"]["fingerprint"]
    # lembar yang sudah disahkan tidak bisa disegarkan
    r = await klien.post(f"{URL}/{K['u1']['id']}/refresh", headers=f3["h_sa"])
    assert r.status_code == 409, r.text
    K["u5"] = j["sheet"]


# ═══ U6 — kontrol dua orang (K-25) ══════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U6_dua_orang(klien, f3):
    from services import config_resolver as resolver
    from services import dual_control as dc
    r = await _buat(klien, f3["h_mgr"], "2026-11", [_baris(f3, "budi", "bln", "month", "2026-07")])
    assert r.status_code == 200, r.text
    s = r.json()
    assert (await _nominal(klien, f3["h_mgr"], s["id"], s["lines"][0]["id"], 750_000)).status_code == 200
    assert (await klien.post(f"{URL}/{s['id']}/submit", headers=f3["h_mgr"])).status_code == 200
    await resolver.set_value("kontrol.lembar_insentif.min_orang", "2", scope_type="entity", scope_id=KANDA,
                             actor="uji", reason="uji KM-T3 U6")
    try:
        r = await klien.post(f"{URL}/{s['id']}/approve", headers=f3["h_mgr"], json={})
        assert (r.status_code, r.json()["detail"]) == (403, dc.pesan_tolak("lembar_insentif")), r.text
        r = await klien.post(f"{URL}/{s['id']}/approve", headers=f3["h_adm"], json={})
        assert r.status_code == 200 and r.json()["approved_by"]["id"] == f3["adm"]["id"], r.text
    finally:
        await resolver.clear_layer("kontrol.lembar_insentif.min_orang", scope_type="entity", scope_id=KANDA,
                                   actor="uji", reason="uji KM-T3 U6 selesai")
    assert await dc.butuh_orang_kedua("lembar_insentif", KANDA, 750_000) is False   # bawaan satu orang


# ═══ U7 — pemutus mengoreksi nominal (wajib catatan) ════════════════════════════════════════════════════════════════
async def test_KMT3_U7_koreksi_pemutus(klien, f3):
    r = await _buat(klien, f3["h_sa"], "2026-10", [_baris(f3, "andi", "bln", "month", "2026-08"),
                                                     _baris(f3, "andi", "tw", "quarter", "2026-Q2"),
                                                     _baris(f3, "budi", "bln", "month", "2026-08")])
    assert r.status_code == 200, r.text
    s = r.json()
    for siapa, komp, per, nominal in (("andi", "bln", "2026-08", 2_000_000), ("andi", "tw", "2026-Q2", 3_000_000),
                                      ("budi", "bln", "2026-08", 3_500_000)):
        s = (await _nominal(klien, f3["h_sa"], s["id"], _line(s, f3, siapa, komp, per)["id"], nominal)).json()
    assert (await klien.post(f"{URL}/{s['id']}/submit", headers=f3["h_sa"])).status_code == 200
    budi = _line(s, f3, "budi", "bln", "2026-08")["id"]
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f3["h_mgr"],
                         json={"corrections": [{"line_id": budi, "amount": 3_000_000}]})
    assert (r.status_code, r.json()["detail"]) == (400, "Beri catatan untuk setiap nominal yang dikoreksi."), r.text
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f3["h_mgr"],
                         json={"corrections": [{"line_id": budi, "amount": 3_000_000, "note": "pencairan belum penuh"}]})
    assert r.status_code == 200, r.text
    j = r.json()
    b = next(x for x in j["lines"] if x["id"] == budi)
    assert (b["amount"], b["amount_prepared"], b["approver_note"]) == (3_000_000, 3_500_000, "pencairan belum penuh")
    assert j["totals"]["amount"] == 8_000_000 and j["status"] == "approved"


# ═══ U9 — baris penyesuaian ═════════════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U9_baris_penyesuaian(klien, f3):
    r = await _buat(klien, f3["h_sa"], "2026-12", [])
    assert r.status_code == 200, r.text
    s = r.json()
    u1_andi = _line(K["u1"], f3, "andi", "bln", "2026-10")
    r = await klien.get(f"{URL}/adjustable-lines", headers=f3["h_sa"], params={"sales_id": f3["andi"]["id"]})
    assert r.status_code == 200 and u1_andi["id"] in [x["line_id"] for x in r.json()["items"]], r.text
    adj = {**_baris(f3, "andi", "bln", "month", "2026-10"), "is_adjustment": True, "amount": -500_000,
           "note": "retur 25 Okt", "adjusts": {"sheet_id": K["u1"]["id"], "line_id": u1_andi["id"]}}
    r = await klien.post(f"{URL}/{s['id']}/lines", headers=f3["h_sa"], json=adj)
    assert r.status_code == 200, r.text
    j = r.json()
    x = j["lines"][0]
    assert (x["is_adjustment"], x["amount"], x["adjusts"]["sheet_number"], j["active_keys"]) == (
        True, -500_000, K["u1"]["number"], []), x
    assert j["totals"] == {"lines": 1, "amount": -500_000}
    r = await klien.post(f"{URL}/{s['id']}/lines", headers=f3["h_sa"], json={**adj, "adjusts": None})
    assert (r.status_code, r.json()["detail"]) == (
        400, "Baris penyesuaian harus merujuk baris lembar yang sudah disahkan dan diberi catatan."), r.text
    r = await klien.post(f"{URL}/{s['id']}/lines", headers=f3["h_sa"], json={**adj, "note": ""})
    assert r.status_code == 400, r.text
    # rujukan ke lembar yang belum disahkan (U5, draf) juga ditolak
    r = await klien.post(f"{URL}/{s['id']}/lines", headers=f3["h_sa"],
                         json={**adj, "adjusts": {"sheet_id": K["u5"]["id"], "line_id": K["u5"]["lines"][0]["id"]}})
    assert r.status_code == 400, r.text
    r = await klien.post(f"{URL}/{s['id']}/lines", headers=f3["h_sa"],
                         json={**_baris(f3, "andi", "bln", "month", "2026-10"), "amount": -1})
    assert (r.status_code, r.json()["detail"]) == (400, "Nominal negatif hanya untuk baris penyesuaian."), r.text
    K["u9"] = j


# ═══ U10 — kembalikan (alasan wajib) ════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U10_kembalikan(klien, f3):
    s = K["u9"]
    assert (await klien.post(f"{URL}/{s['id']}/submit", headers=f3["h_sa"])).status_code == 200
    n0 = len((await klien.get(f"{URL}/{s['id']}", headers=f3["h_mgr"])).json()["history"])
    r = await klien.post(f"{URL}/{s['id']}/return", headers=f3["h_mgr"], json={"reason": "cek Budi"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "draft" and len(j["history"]) == n0 + 1
    h = j["history"][-1]
    assert (h["action"], h["reason"], h["from_status"], h["to_status"], h["by_id"]) == (
        "return", "cek Budi", "submitted", "draft", f3["mgr"]["id"]), h
    assert "submitted_by" not in j
    assert (await klien.post(f"{URL}/{s['id']}/submit", headers=f3["h_sa"])).status_code == 200
    r = await klien.post(f"{URL}/{s['id']}/return", headers=f3["h_mgr"], json={"reason": "x"})
    assert r.status_code in (400, 422) and r.json()["detail"] == "Tulis alasan minimal 5 huruf.", r.text
    assert (await klien.get(f"{URL}/{s['id']}", headers=f3["h_mgr"])).json()["status"] == "submitted"


async def test_KMT3_ajukan_tanpa_nominal_dan_batal(klien, f3):
    r = await _buat(klien, f3["h_sa"], "2026-12", [_baris(f3, "budi", "tw", "quarter", "2026-Q3")])
    s = r.json()
    r = await klien.post(f"{URL}/{s['id']}/submit", headers=f3["h_sa"])
    assert (r.status_code, r.json()["detail"]) == (400, "Isi nominal semua baris sebelum mengajukan."), r.text
    r = await klien.post(f"{URL}/{s['id']}/cancel", headers=f3["h_sa"], json={"reason": "x"})
    assert r.status_code == 400, r.text
    r = await klien.post(f"{URL}/{s['id']}/cancel", headers=f3["h_sa"], json={"reason": "salah periode"})
    assert r.status_code == 200 and (r.json()["status"], r.json()["active_keys"]) == ("cancelled", []), r.text
    # baris yang sama boleh dibuat lagi sesudah lembarnya dibatalkan
    r = await _buat(klien, f3["h_sa"], "2026-12", [_baris(f3, "budi", "tw", "quarter", "2026-Q3")])
    assert r.status_code == 200, r.text
    # daftar: saringan status, tanpa potret
    r = await klien.get(URL, headers=f3["h_sa"], params={"status": "cancelled"})
    assert r.status_code == 200 and r.json()["total"] == 1, r.text
    assert all("snapshot" not in x for it in r.json()["items"] for x in it["lines"])
    r = await klien.get(URL, headers=f3["h_mgr"], params={"pay_period": "2026-11", "page_size": 2})
    assert r.status_code == 200 and r.json()["total"] >= 3 and len(r.json()["items"]) == 2, r.text


# ═══ U12 — izin dari katalog ════════════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U12_izin(klien, akun, sesi, peran_manajer_kosong, peran_sopir, f3):
    r = await _buat(klien, f3["h_sa"], "2027-01", [])   # Tanpa Acuan + `incentive.prepare` saja
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    r = await klien.post(f"{URL}/{K['u9']['id']}/approve", headers=f3["h_sa"], json={})
    assert r.status_code == 403, r.text
    assert "mengesahkan lembar insentif" in _z6(r)
    for peran in (await peran_manajer_kosong(), peran_sopir):
        h = await sesi(await akun(peran, entitas=(KANDA,)), entitas=KANDA)
        for metode, url in (("get", URL), ("get", f"{URL}/{sid}"), ("post", URL)):
            r = await getattr(klien, metode)(url, headers=h, **({"json": {"pay_period": "2027-01"}} if metode == "post"
                                                                 else {}))
            assert r.status_code == 403, (peran, url, r.text)
            _z6(r)


# ═══ U13 — lembar PT lain ═══════════════════════════════════════════════════════════════════════════════════════════
async def test_KMT3_U13_lembar_pt_lain(klien, kepala_admin, f3):
    r = await klien.post(URL, headers={**kepala_admin, "X-Entity-Id": KSC}, json={"pay_period": "2026-11"})
    assert r.status_code == 200 and r.json()["entity_id"] == KSC, r.text
    ksc = r.json()
    for metode, url in (("get", f"{URL}/{ksc['id']}"), ("post", f"{URL}/{ksc['id']}/submit"),
                        ("get", f"{URL}/{ksc['id']}/export")):
        r = await getattr(klien, metode)(url, headers=f3["h_mgr"])
        assert r.status_code in (403, 404), (url, r.text)
    r = await klien.get(f"{URL}/{ksc['id']}", headers={**kepala_admin, "X-Entity-Id": KSC})
    assert r.json()["status"] == "draft"
    # daftar PT Kanda tidak memuat lembar KSC
    r = await klien.get(URL, headers=f3["h_mgr"], params={"page_size": 100})
    assert ksc["id"] not in [x["id"] for x in r.json()["items"]]


# ═══ Katalog: izin bawaan, kontrol dua orang, nomor, antrean ════════════════════════════════════════════════════════
async def test_KMT3_katalog():
    import approval_kinds
    import config_registry
    import doc_number_kinds as dnk
    import indexes
    from access_modules import ACTION_LABEL, MODULE_BY_ID
    from config_catalog_kontrol import AKSI_BY_ID
    from permissions_config import DEFAULT_PERMISSIONS
    for role, acts in (("admin", {"prepare", "approve"}), ("manager", {"prepare", "approve"}),
                       ("sales_admin", {"prepare"}), ("finance", {"prepare"})):
        assert acts <= set(DEFAULT_PERMISSIONS[role]["incentive"]), role
    assert "approve" not in DEFAULT_PERMISSIONS["finance"]["incentive"]
    assert "incentive" not in DEFAULT_PERMISSIONS["sales"] or not ({"prepare", "approve"}
                                                                   & set(DEFAULT_PERMISSIONS["sales"]["incentive"]))
    assert (ACTION_LABEL["incentive.prepare"], ACTION_LABEL["incentive.approve"]) == (
        "Siapkan lembar insentif", "Sahkan lembar insentif")
    assert "incentive-sheets" in MODULE_BY_ID["incentive"]["nav"]
    a = AKSI_BY_ID["lembar_insentif"]
    assert (a["label"], a["awal"], a["punya_nominal"]) == ("Pengesahan lembar insentif", "1", True)
    m = config_registry.require("kontrol.lembar_insentif.min_orang")
    b = config_registry.require("kontrol.lembar_insentif.batas_nominal")
    assert (m["default"], b["default"]) == ("1", 0)
    assert "services/incentive_sheet_service.py:approve_sheet" in m["consumers"]
    assert dnk.lookup("incentive_sheets", "number", "LIN-")[0]["kind"] == "lin"
    assert ("incentive_sheets", "number") in indexes.UNIQUE_DOC_NUMBER_FIELDS
    assert any(i["name"] == "uq_isheet_active_key" for i in indexes.REQUIRED_UNIQUE_INDEXES)
    assert approval_kinds.APPROVAL_KINDS["incentive_sheet"]["permissions"] == ("incentive.approve",)
