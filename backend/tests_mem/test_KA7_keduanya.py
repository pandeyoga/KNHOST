"""KA-7 — sumber insentif "Keduanya dibayar" (`auto_and_sheet`): komisi mesin DAN Lembar Insentif sama-sama masuk gaji.

Spesifikasi `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.5. Fixture mengikuti `test_KMT4_insentif_gaji.py`
(`f4`): `ent_kanda` diset `auto_and_sheet` lewat `config_resolver.set_value` (beralasan); satu karyawan, Andi (gaji pokok
5.000.000, TK0, BPJS mati), tertaut ke akun sales. Komisi mesin: 1.000 m × Rp 500 (batas margin 0) = 500.000 (pola KM-T5
`_data_mesin`). Lembar Insentif Andi "Insentif Bulanan" Okt 2026 = 2.000.000, diajukan lalu disahkan.

U4 (sebelum gaji): akrual manual = komisi mesin saja 500.000; gaji sesudahnya mengakru Σ komisi mesin slip 500.000 = sama
→ tidak ada jurnal koreksi `incentive_accrual_adj` (tidak ada akrual ganda).

Hitung tangan (U3): slip = komisi mesin 500.000 + baris INSENTIF 2.000.000 → komisi slip 2.500.000. Akrual mesin hanya
500.000 (jurnal `incentive_accrual`, Dr 6-5000 / Cr 2-1500); lembar sudah berjurnal 2.000.000 saat disahkan (Dr 6-5000 /
Cr 2-1500). Kredit 2-1500 = 2.000.000 + 500.000 = 2.500.000; jurnal gaji Dr 2-1500 2.500.000 → saldo 2-1500 sesudah
gaji = 0.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List

import pytest

from pembantu import AKTOR_UJI

pytestmark = pytest.mark.anyio

KANDA = "ent_kanda"
URL = "/api/incentive/sheets"
MODE = "hr.payroll_commission_mode"
UTC = datetime.timezone.utc
JAM = {"now": datetime.datetime(2026, 11, 5, 3, 0, tzinfo=UTC)}   # 5 Nov 2026 10.00 WIB
K: Dict[str, Any] = {}


@pytest.fixture(scope="module", autouse=True)
def _jam():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: JAM["now"])
        yield


@pytest.fixture(scope="module")
async def f7(db, akun, sesi):
    from services import config_resolver as resolver
    from services import incentive_targets as itg
    await resolver.set_value(MODE, "auto_and_sheet", scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KA-7")
    await db.hr_employees.update_many({"entity_id": KANDA}, {"$set": {"status": "inactive"}})
    andi = await akun("sales", entitas=(KANDA,))
    await db.users.update_one({"id": andi["id"]}, {"$set": {"name": "Andi"}})
    andi["name"] = "Andi"
    await db.hr_employees.insert_one({
        "id": "emp_ka7_andi", "code": "EMP-KA7-ANDI", "name": "Andi", "entity_id": KANDA, "user_id": andi["id"],
        "status": "active", "base_salary": 5_000_000, "allowances": [], "ptkp_status": "TK0",
        "bpjs_kes_enabled": False, "bpjs_tk_enabled": False, "join_date": "2025-01-01",
        "created_at": "2025-01-01T00:00:00+00:00"})
    komp = await itg.create_component(KANDA, {"code": "BLN", "name": "Insentif Bulanan", "basis_period_type": "month",
                                              "columns": ["omzet"]}, AKTOR_UJI)
    # komisi mesin: tarif Rp 500 per meter (batas margin 0), pesanan 1.000 m lunas 10 Nov 2026
    await db.incentive_rates.insert_one({"id": "rate_ka7", "entity_id": KANDA, "category": "KA7", "per_unit_amount": 500.0,
                                         "margin_cap_pct": 0.0, "discount_threshold": 100.0,
                                         "discount_threshold_type": "pct", "discount_mechanic": "tier_factor",
                                         "discount_factor": 1.0, "status": "active"})
    await db.customers.insert_one({"id": "cus_ka7", "name": "Toko KA-7", "entity_id": KANDA, "status": "active",
                                   "assigned_sales_id": andi["id"]})
    await db.sales_orders.insert_one({
        "id": "so_ka7", "number": "SO/KA7/1", "entity_id": KANDA, "customer_id": "cus_ka7", "status": "completed",
        "items": [{"product_id": "prd_ka7", "sku": "KA7", "category": "KA7", "product_name": "Kain KA-7",
                   "quantity": 1000, "base_quantity": 1000, "unit": "meter", "price": 50_000, "line_total": 50_000_000,
                   "discount_percent": 0, "unit_cost": 30_000}],
        "subtotal": 50_000_000, "grand_total": 50_000_000,
        "payments": [{"amount": 50_000_000, "created_at": "2026-11-10T03:00:00+00:00"}],
        "created_at": "2026-11-02T03:00:00+00:00"})
    return {"andi": andi, "komp": komp, "h": await sesi("admin@kainnusantara.id", entitas=KANDA)}


async def _saldo(db, eid: str, kode: str) -> float:
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": eid, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


# ═══ U1 — pilihan terdaftar ═════════════════════════════════════════════════════════════════════════════════════════
async def test_KA7_U1_pilihan_terdaftar(klien, kepala_admin):
    import config_registry as registry
    opsi = {o["value"]: o["label"] for o in registry.require(MODE)["options"]}
    assert "keduanya" in opsi["auto_and_sheet"].lower(), opsi
    item = {"key": MODE, "value": "auto_and_sheet", "scope_type": "entity", "scope_id": KANDA,
            "reason": "uji pilihan KA-7"}
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [item]})
    assert r.status_code == 200, r.text


# ═══ U2 — lembar tertaut ke gaji dan buku besar ═════════════════════════════════════════════════════════════════════
async def test_KA7_U2_lembar_tertaut(klien, db, f7):
    h = f7["h"]
    r = await klien.post(URL, headers=h, json={"pay_period": "2026-11", "lines": [
        {"sales_id": f7["andi"]["id"], "component_id": f7["komp"]["id"], "basis_period_type": "month",
         "basis_period": "2026-10"}]})
    assert r.status_code == 200, r.text
    s = r.json()
    r = await klien.patch(f"{URL}/{s['id']}/lines/{s['lines'][0]['id']}", headers=h, json={"amount": 2_000_000})
    assert r.status_code == 200, r.text
    r = await klien.post(f"{URL}/{s['id']}/submit", headers=h, json={})
    assert r.status_code == 200, r.text
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=h, json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["payroll_linked"], j["gl_status"]) == ("approved", True, "posted"), j
    K["lembar"] = j


# ═══ U4 — akrual manual boleh, SEBELUM gaji: hanya komisi mesin 500.000; gaji sesudahnya tidak mengakru lagi ══════════
async def test_KA7_U4_akrual_manual_sebelum_gaji(klien, db, f7):
    r = await klien.get("/api/sales/incentive/gl-status", headers=f7["h"], params={"period": "2026-11"})
    assert r.status_code == 200, r.text
    assert (r.json()["mode"], r.json()["estimate"]) == ("auto_and_sheet", 500_000), r.json()
    r = await klien.post("/api/sales/incentive/post-gl", headers=f7["h"], params={"period": "2026-11"})
    assert r.status_code == 200, r.text
    assert (r.json()["created"], r.json()["amount"]) == (True, 500_000), r.json()   # bukan 2.500.000 (lembar tidak ikut)
    K["akrual_manual"] = r.json()["journal_id"]


# ═══ U3 — gaji memuat komisi mesin DAN lembar ═══════════════════════════════════════════════════════════════════════
async def test_KA7_U3_gaji_memuat_keduanya(klien, db, f7):
    h = f7["h"]
    r = await klien.post("/api/hr/payroll/runs", headers=h, json={"entity_id": KANDA, "period": "2026-11",
                                                                  "run_type": "regular"})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["commission_mode"] == "auto_and_sheet"
    for aksi in ("submit", "approve"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h, json={})
        assert r.status_code == 200, r.text
        run = r.json()
    slip = [s for s in run["payslips"] if s["employee_name"] == "Andi"][0]
    ins = [c for c in slip["components"] if c["code"] == "INSENTIF"]
    assert [(c["label"], c["amount"]) for c in ins] == [("Insentif Bulanan — Okt 2026", 2_000_000)], slip["components"]
    assert slip["commission"] == 2_500_000, slip["commission"]   # 500.000 mesin + 2.000.000 lembar
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h, json={})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "posted", run
    akr = await db.journal_entries.find({"source_type": "incentive_accrual", "entity_id": KANDA,
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)
    assert len(akr) == 1 and akr[0]["total_debit"] == 500_000, akr   # hanya komisi mesin, bukan 2.500.000
    assert akr[0]["id"] == K["akrual_manual"]                         # akrual manual U4 dipakai, bukan akrual kedua
    assert await db.journal_entries.count_documents({"source_type": "incentive_accrual_adj", "entity_id": KANDA}) == 0
    gaji = await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": run["id"]}, {"_id": 0})
    dr_hutang = sum(ln["debit"] for ln in gaji["lines"] if ln["account_code"] == "2-1500")
    assert dr_hutang == 2_500_000, gaji["lines"]
    assert await _saldo(db, KANDA, "2-1500") == 0
    l1 = await db.incentive_sheets.find_one({"id": K["lembar"]["id"]}, {"_id": 0})
    assert l1["status"] == "paid", l1["status"]


# ═══ U5 — halaman komisi tidak 409 ══════════════════════════════════════════════════════════════════════════════════
async def test_KA7_U5_komisi_tidak_409(klien, f7):
    r = await klien.get("/api/sales/commission", headers=f7["h"], params={"period": "2026-11"})
    assert r.status_code == 200, r.text


# ═══ U6 — beranda admin: campuran ═══════════════════════════════════════════════════════════════════════════════════
async def test_KA7_U6_beranda_admin_campuran(klien, f7):
    from services.home_service import LABEL_CAMPURAN
    r = await klien.get("/api/home/admin", headers=f7["h"])
    assert r.status_code == 200, r.text
    assert r.json()["incentive_payout_label"] == LABEL_CAMPURAN, r.json()["incentive_payout_label"]
