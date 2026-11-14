"""PK-32 (FX-12, FX-13, FX-14, FX-15) — satu pembuat nota kredit/debit: satu status, batas total, nilai efektif, dan
pendapatan yang benar-benar diakui. Spesifikasi `docs/blueprint/unit/PK-32.md`.

Persiapan bersama (fixture, disisipkan langsung): PT `ent_ksc`; pelanggan `c1`; rekening Bank `rek_pk32_b`; produk
`p1`; tiap uji membuat pesanannya sendiri 100 m × Rp 10.000 = Rp 1.000.000 tanpa PPN (`tax_override="non_ppn"`, harga
dihitung `config_service.compute_order_pricing` — mesin yang sama dengan pratinjau amandemen), biaya roll Rp 6.000 per
meter (potret biaya di surat jalan). "Terkirim" = surat jalan fixture lalu jurnalnya lewat
`gl_service.post_order_revenue_and_cogs` (fungsi yang dipanggil tombol kirim; tombol kirim gudang menuntut tag RFID —
gerbang H7, tidak disentuh). "Koreksi" = amandemen metode nota lewat API (`POST /api/amendments`) yang disetujui akun
kedua (`POST /api/amendments/{id}/decision`). Kwitansi U3 dan U6 lewat API (`POST /api/ar-receipts`).

Hitung tangan (contoh angka `00` §9):
  U1  kirim 100 m: Dr 1-1200 1.000.000 / Cr 4-1000 1.000.000. Koreksi 10.000 → 8.000: nota 1 = 100 × 2.000 = 200.000;
      terkirim penuh → porsi 1 → dijurnal max(0, 1.000.000 − 1 × 800.000) = 200.000: Dr 4-1000 200.000 / Cr 1-1200
      200.000; sisa tagihan 1.000.000 − 200.000 = 800.000. Retur 100 m pada harga efektif 8.000 → nota 2 = 800.000:
      Dr 4-1000 800.000 / Cr 1-1200 800.000; HPP balik 100 × 6.000 = 600.000 (Dr 1-1300 / Cr 5-1000). Σ nota =
      1.000.000 = 100 %; 1-1200 pesanan 1.000.000 − 200.000 − 800.000 = 0; pendapatan 1.000.000 − 1.000.000 = 0.
  U2  lanjutan U1: koreksi 8.000 → 7.500 (50.000) → Σ 1.000.000 + 50.000 > 1.000.000 → 409.
  U3  kwitansi 1.000.000 sebelum kirim → Dr kas / Cr 2-1400 1.000.000. Koreksi → 8.000: porsi 0 → dijurnal
      max(0, 0 − 0) = 0, tertangguh 200.000; terbayar 1.000.000 − nilai efektif baru 800.000 = kelebihan 200.000 (uang
      muka); sisa tagihan 0 → alokasi 0; tanpa jurnal (`not_required`).
  U4  lanjutan U3: kirim 100 m → pendapatan nilai efektif 800.000 (Dr 1-1200 / Cr 4-1000); reklas uang muka
      min(1.000.000, 800.000) = 800.000 (Dr 2-1400 / Cr 1-1200) → 2-1400 1.000.000 − 800.000 = 200.000; 1-1200 0.
  U5  kirim 40 m: Dr 1-1200 400.000 / Cr 4-1000 400.000 (porsi 0,4). Koreksi → 8.000: dijurnal 400.000 − 0,4 × 800.000
      = 80.000, tertangguh 120.000 → Dr 4-1000 80.000 / Cr 1-1200 80.000; alokasi min(200.000, sisa 1.000.000) =
      200.000 = 80.000 (`nota_koreksi`) + 120.000 (`nota_tangguh`). Kirim 60 m (penutup): 800.000 − (400.000 − 80.000)
      = 480.000. Akhir: pendapatan 400.000 − 80.000 + 480.000 = 800.000; 1-1200 = 800.000 = sisa tagihan 1.000.000 −
      200.000; ruang piutang kwitansi = 800.000.
  U6  terkirim penuh; koreksi 10.000 → 11.000 = nota debit 100 × 1.000 = 100.000: porsi 1 → Dr 1-1200 100.000 /
      Cr 4-1000 100.000; tagihan tambahan 100.000; nilai tagihan 1.100.000 → kwitansi 1.100.001 ditolak, 1.100.000
      diterima; umur piutang 1.100.000.
  U7  belum dikirim: nota debit 100.000 → porsi 0 → tanpa jurnal; kirim 100 m (penutup) → 1.100.000 − 0 = 1.100.000.
"""
from __future__ import annotations

import importlib.util
import itertools
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, saldo_akun

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
HARGA, QTY, BIAYA = 10_000, 100, 6_000
PIUTANG, PENDAPATAN, PPN_OUT, UANG_MUKA, SALDO_KREDIT, PERSEDIAAN, HPP = (
    "1-1200", "4-1000", "2-1200", "2-1400", "2-1450", "1-1300", "5-1000")
REPO = Path(__file__).resolve().parents[2]
_n = itertools.count(1)
#: pesanan yang dipakai uji lanjutan (U2 ← U1)
BAG: Dict[str, Any] = {}

#: serah-terima (a) — pembuat lama belum memakai mesin nota; tanda dicabut di serah-terima (b)
B_FX12 = pytest.mark.xfail(strict=True, reason="FX-12 — menunggu serah-terima (b): pembuat lama belum memakai mesin nota")
B_FX13 = pytest.mark.xfail(strict=True, reason="FX-13 — menunggu serah-terima (b): pembuat lama belum memakai mesin nota")
B_FX14 = pytest.mark.xfail(strict=True, reason="FX-14 — menunggu serah-terima (b): pendapatan belum memakai nilai efektif")
B_FX15 = pytest.mark.xfail(strict=True, reason="FX-15 — menunggu serah-terima (b): nota debit amandemen belum ditagihkan")


def uid(awalan: str) -> str:
    return f"{awalan}_pk32_{uuid.uuid4().hex[:8]}"


def baris(jes) -> Dict[str, Tuple[float, float]]:
    """{akun: (debit, kredit)} — gabungan jurnal."""
    out: Dict[str, Tuple[float, float]] = {}
    for je in jes if isinstance(jes, list) else [jes]:
        for ln in je["lines"]:
            d, c = out.get(ln["account_code"], (0.0, 0.0))
            out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2),
                                       round(c + float(ln.get("credit") or 0), 2))
    return out


async def jurnal(db, source_type: str, source_id: str = "", order_id: str = "") -> List[dict]:
    q: Dict[str, Any] = {"source_type": source_type, "status": {"$ne": "void"}}
    if source_id:
        q["source_id"] = source_id
    if order_id:
        q["ref.order_id"] = order_id
    return await db.journal_entries.find(q, {"_id": 0}).to_list(50)


async def saldo(kode: str) -> float:
    return round(await saldo_akun(kode, KSC), 2)


async def saldo_semua() -> Dict[str, float]:
    return {k: await saldo(k) for k in (PIUTANG, PENDAPATAN, UANG_MUKA, SALDO_KREDIT)}


async def selisih(awal: Dict[str, float]) -> Dict[str, float]:
    kini = await saldo_semua()
    return {k: round(kini[k] - awal[k], 2) for k in awal}


# ── Fixture bersama ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def dunia(db, akun, sesi):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    pid, wid, cus = uid("prd"), uid("wh"), "c1"
    await db.products.insert_one({"id": pid, "name": "Kain Uji PK-32", "sku": f"SKU-{pid}", "base_unit": "meter",
                                  "harga_pokok": BIAYA, "price": HARGA, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji PK-32", "entity_id": KSC, "is_active": True,
                                    "created_at": now_iso()})
    if not await db.customers.find_one({"id": cus}):
        await db.customers.insert_one({"id": cus, "name": "Toko c1 PK-32", "entity_id": KSC, "status": "active",
                                       "deposit_balance": 0.0})
    await db.bank_accounts.insert_one({"id": "rek_pk32_b", "name": "BCA KSC PK32", "entity_id": KSC,
                                       "account_type": "bank", "cash_type": "kas_besar", "is_active": True,
                                       "opening_balance": 0})
    kedua = await akun("admin")
    return {"pid": pid, "wid": wid, "cus": cus, "h2": await sesi(kedua)}


async def pesanan(db, dunia, *, harga: float = HARGA, qty: float = QTY, status: str = "confirmed") -> dict:
    from services import config_service
    i = next(_n)
    pr = await config_service.compute_order_pricing(
        [{"product_id": dunia["pid"], "product_name": "Kain Uji PK-32", "sku": "SKU-PK32", "quantity": qty,
          "base_quantity": qty, "unit": "meter", "price": harga}], entity_id=KSC, tax_override="non_ppn")
    so = {"id": uid("so"), "number": f"SO/PK32/{i:03d}", "entity_id": KSC, "customer_id": dunia["cus"],
          "customer_name": "Toko c1 PK-32", "status": status, "payment_term_code": "NET30", "payment_method": "kredit",
          "tax_override": "non_ppn", "allocations": [{"warehouse_id": dunia["wid"], "product_id": dunia["pid"],
                                                       "qty": qty}],
          "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "created_at": now_iso(),
          **{k: pr[k] for k in ("items", "total_amount", "net_subtotal", "dpp", "ppn_rate", "ppn_mode", "ppn_amount",
                                "grand_total", "order_discount_percent", "tax_snapshot")}}
    assert so["grand_total"] == harga * qty and so["ppn_amount"] == 0, pr
    await db.sales_orders.insert_one(dict(so))
    return so


async def kirim(db, dunia, so: dict, qty: float, *, penutup: bool) -> dict:
    """Surat jalan `qty` m (potret biaya 6.000/m) lalu jurnalnya lewat alur kirim."""
    from services import gl_service
    shp = {"id": uid("shp"), "shipment_no": f"SJ/PK32/{uuid.uuid4().hex[:5]}", "entity_id": KSC,
           "order_id": so["id"], "order_number": so["number"], "product_id": dunia["pid"],
           "warehouse_id": dunia["wid"], "qty": qty, "unit": "meter",
           "rolls": [{"roll_id": uid("r"), "length": qty, "unit_cost": BIAYA, "extended_cost": qty * BIAYA}],
           "status": "dispatched", "created_at": now_iso(), "gl_status": "pending"}
    await db.shipments.insert_one(dict(shp))
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "shipped" if penutup else "partially_shipped"}})
    await gl_service.post_order_revenue_and_cogs(so["id"])
    return shp


async def koreksi(klien, h1, h2, so: dict, harga_baru: float, pid: str):
    """Amandemen harga lewat API, disetujui akun kedua. → (jawaban putusan, id amandemen)."""
    r = await klien.post("/api/amendments", headers=h1, json={
        "doc_type": "sales_order", "doc_id": so["id"], "reason_code": "price_correction", "note": "uji PK-32",
        "changes": [{"product_id": pid, "field": "price", "to": harga_baru}]})
    assert r.status_code == 200, r.text
    amd = r.json()
    assert amd["status"] == "pending_approval" and amd["method"] in ("credit_note", "debit_note"), amd
    d = await klien.post(f"/api/amendments/{amd['id']}/decision", headers=h2, json={"action": "approve", "note": "uji"})
    return d, amd["id"]


async def nota_dari(db, amd_id: str) -> dict:
    return await db.credit_notes.find_one({"amendment_id": amd_id}, {"_id": 0})


async def so_kini(db, so: dict) -> dict:
    return await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})


def sisa(o: dict) -> float:
    from services.customer_service import _order_grand_total, _order_paid
    return round(_order_grand_total(o) - _order_paid(o), 2)


async def kwitansi(klien, h, dunia, so: dict, amount: float):
    return await klien.post("/api/ar-receipts", headers=h, json={
        "customer_id": dunia["cus"], "amount": amount, "method": "transfer", "entity_id": KSC,
        "use_deposit_amount": 0, "account_id": "rek_pk32_b",
        "allocations": [{"order_id": so["id"], "amount": amount}]})


async def amandemen_fixture(db, so: dict, pid: str, *, dari: float, ke: float) -> str:
    """Amandemen nota yang sudah diterapkan (fixture serah-terima (a): fungsi baru dipanggil langsung)."""
    aid = uid("amd")
    await db.doc_amendments.insert_one({
        "id": aid, "number": f"AMD/{aid[-6:]}", "doc_type": "sales_order", "doc_id": so["id"], "entity_id": KSC,
        "method": "credit_note" if ke < dari else "debit_note", "status": "applied", "created_at": now_iso(),
        "changes": [{"product_id": pid, "product_name": "Kain Uji PK-32", "field": "price", "from": dari, "to": ke}]})
    return aid


# ═══ U13 — pembaca status lama ══════════════════════════════════════════════════════════════════════════════════════
async def test_PK32_U13_status_lama_dibaca_kosakata_baru(klien, kepala_admin, db, dunia):
    so = await pesanan(db, dunia, status="shipped")
    a, b = uid("cn"), uid("cn")
    await db.credit_notes.insert_many([
        {"id": a, "number": f"CN-PK32-LAMA-{a[-4:]}", "kind": "credit_note", "source": "amendment", "status": "offset",
         "order_id": so["id"], "entity_id": KSC, "customer_id": dunia["cus"], "gross_amount": 50_000,
         "debit_note_offset": 50_000, "created_at": now_iso()},
        {"id": b, "number": f"CN-PK32-LAMA-{b[-4:]}", "status": "posted", "return_id": uid("sr"),
         "order_id": so["id"], "entity_id": KSC, "customer_id": dunia["cus"], "gross_amount": 20_000,
         "settlement": "ar", "created_at": now_iso()}])
    r = await klien.get("/api/credit-notes", headers=kepala_admin, params={"customer_id": dunia["cus"]})
    assert r.status_code == 200, r.text
    by = {x["id"]: x for x in r.json()["items"]}
    assert (by[a]["status"], by[a]["kind"]) == ("posted", "credit_note"), by[a]
    assert (by[b]["status"], by[b]["kind"], by[b]["source"]) == ("posted", "credit_note", "sales_return"), by[b]
    one = (await klien.get(f"/api/credit-notes/{a}", headers=kepala_admin)).json()
    assert one["status"] == "posted" and one["status_label"] == "Selesai", one
    assert (await db.credit_notes.find_one({"id": a}))["status"] == "offset"   # data tidak diubah


# ═══ U14 — skrip migrasi nota debit lama ═════════════════════════════════════════════════════════════════════════════
def _skrip():
    jalur = REPO / "scripts" / "migrasi_pk32_nota_debit_menunggu.py"
    spec = importlib.util.spec_from_file_location("migrasi_pk32", jalur)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_PK32_U14_skrip_migrasi_nota_debit_menunggu(db, dunia, capsys):
    # FIXTURE: keadaan sebelum PK-32 — pesanan terkirim penuh (jurnal 1.000.000) + nota debit 100.000 menunggu
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    dn = uid("dn")
    await db.credit_notes.insert_one({
        "id": dn, "number": f"DN-PK32-LAMA-{dn[-4:]}", "kind": "debit_note", "source": "amendment", "status": "issued",
        "order_id": so["id"], "order_number": so["number"], "customer_id": dunia["cus"], "entity_id": KSC,
        "net_amount": 100_000, "ppn_amount": 0, "gross_amount": 100_000, "direction": "increase",
        "billing_status": "awaiting_billing_rule", "open_amount": 100_000, "reason_label": "Koreksi harga",
        "lines": [{"product_id": dunia["pid"], "field": "price", "from": 10_000, "to": 11_000}],
        "created_at": now_iso()})
    skrip = _skrip()
    assert await skrip.jalankan([]) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():   # cetakan untuk laporan (pytest -s)
        print("\n=== CETAKAN SKRIP MIGRASI PK-32 (baca-saja) ===\n" + keluar)
    assert re.search(rf"Nota debit DN-PK32-LAMA-{dn[-4:]} · pesanan {re.escape(so['number'])} · PT {KSC} · "
                     r"open_amount 100\.000", keluar), keluar
    assert "Ringkasan: 1 nota debit menunggu ditagih · total 100.000" in keluar, keluar
    assert (await db.credit_notes.find_one({"id": dn}))["billing_status"] == "awaiting_billing_rule"   # baca-saja
    assert await skrip.jalankan(["--apply"]) == 0
    with capsys.disabled():
        print("\n=== --apply ===\n" + capsys.readouterr().out)
    n = await db.credit_notes.find_one({"id": dn}, {"_id": 0})
    assert (n["billing_status"], n["status"], n["gl_status"]) == ("billed", "posted", "posted"), n
    jd = await jurnal(db, "amendment_debit_note", dn)
    assert len(jd) == 1 and baris(jd) == {PIUTANG: (100_000, 0), PENDAPATAN: (0, 100_000)}, jd
    o = await so_kini(db, so)
    assert [(x["debit_note_id"], x["gross"]) for x in o["extra_billing_lines"]] == [(dn, 100_000)]
    assert sisa(o) == 1_100_000
    assert await skrip.jalankan(["--apply"]) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():
        print("\n=== --apply (jalan ketiga) ===\n" + keluar)
    assert "Ringkasan: 0 nota debit menunggu ditagih · total 0" in keluar and "Tanpa perubahan" in keluar, keluar


# ═══ U1–U2 — batas total nota kredit dan harga efektif retur (FX-12) ═══════════════════════════════════════════════
async def retur_barang(db, dunia, so: dict, qty: float) -> str:
    sr = uid("sr")
    await db.sales_returns.insert_one({
        "id": sr, "number": f"RJ/PK32/{sr[-6:]}", "entity_id": KSC, "status": "inspected", "order_id": so["id"],
        "order_number": so["number"], "customer_id": dunia["cus"], "customer_name": "Toko c1 PK-32",
        "attachments": [{"id": "att_pk32", "name": "foto.jpg"}], "created_at": now_iso(),
        "items": [{"product_id": dunia["pid"], "product_name": "Kain Uji PK-32", "quantity_returned": qty,
                   "unit": "meter", "condition": "ok", "reason": "salah warna", "inspection": {"grade": "A"}}]})
    return sr


@B_FX12
async def test_PK32_U1_koreksi_lalu_retur_harga_efektif(klien, kepala_admin, db, dunia):
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    awal = await saldo_semua()
    d, amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 8_000, dunia["pid"])
    assert d.status_code == 200, d.text
    n1 = await nota_dari(db, amd)
    assert (n1["gross_amount"], n1["source"], n1["kind"], n1["status"]) == (200_000, "amendment", "credit_note",
                                                                           "posted"), n1
    assert (n1["revenue_reversed_net"], n1["deferred_net"], n1["gl_status"]) == (200_000, 0, "posted"), n1
    assert n1["effects"] == {"allocation": "done", "store_credit": "skipped", "journal": "done"}, n1
    j1 = await jurnal(db, "amendment_credit_note", n1["id"])
    assert len(j1) == 1 and baris(j1) == {PENDAPATAN: (200_000, 0), PIUTANG: (0, 200_000)}, j1
    assert sisa(await so_kini(db, so)) == 800_000
    # retur 100 m kondisi baik, pengurang piutang → harga efektif 8.000
    sr = await retur_barang(db, dunia, so, QTY)
    r = await klien.post(f"/api/sales-returns/{sr}/settle", headers=kepala_admin, json={"outcome": "refund"})
    assert r.status_code == 200, r.text
    n2 = await db.credit_notes.find_one({"return_id": sr}, {"_id": 0})
    assert (n2["gross_amount"], n2["cogs_amount"], n2["source"], n2["status"]) == (800_000, 600_000, "sales_return",
                                                                                   "posted"), n2
    assert n2["lines"][0]["unit_price"] == 8_000, n2["lines"]
    j2 = await jurnal(db, "sales_return", sr)
    assert len(j2) == 1 and baris(j2) == {PENDAPATAN: (800_000, 0), PIUTANG: (0, 800_000), PERSEDIAAN: (600_000, 0),
                                          HPP: (0, 600_000)}, j2
    from services import credit_note_service as cns
    assert await cns.credit_total(so["id"]) == 1_000_000
    beda = await selisih(awal)
    assert (beda[PIUTANG], beda[PENDAPATAN]) == (-1_000_000, -1_000_000), beda   # 1.000.000 lahir saat kirim → 0
    o = await so_kini(db, so)
    assert sisa(o) == 0 and o["payment_status"] == "paid", o.get("payments")
    BAG["u1"] = o


@B_FX12
async def test_PK32_U2_koreksi_melebihi_nilai_pesanan_ditolak(klien, kepala_admin, db, dunia):
    so = BAG.get("u1")
    assert so, "lanjutan U1"
    sebelum = await db.credit_notes.count_documents({"order_id": so["id"]})
    d, amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 7_500, dunia["pid"])
    assert d.status_code == 409, d.text
    assert "melebihi nilai pesanan" in d.json()["detail"] and "Rp 1.050.000" in d.json()["detail"], d.text
    assert await db.credit_notes.count_documents({"order_id": so["id"]}) == sebelum
    assert (await db.doc_amendments.find_one({"id": amd}))["status"] == "pending_approval"


# ═══ U3–U5 — pendapatan hanya dibalik sebesar yang sudah diakui (FX-14) ════════════════════════════════════════════
@B_FX14
async def test_PK32_U3_U4_dibayar_sebelum_kirim_lalu_kirim(klien, kepala_admin, db, dunia):
    so = await pesanan(db, dunia)
    awal = await saldo_semua()
    r = await kwitansi(klien, kepala_admin, dunia, so, 1_000_000)
    assert r.status_code == 200, r.text
    assert (await selisih(awal))[UANG_MUKA] == 1_000_000   # Dr kas / Cr 2-1400
    d, amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 8_000, dunia["pid"])
    assert d.status_code == 200, d.text
    n = await nota_dari(db, amd)
    assert (n["gross_amount"], n["revenue_reversed_net"], n["deferred_net"], n["excess_payment"]) == (
        200_000, 0, 200_000, 200_000), n
    assert (n["gl_status"], n["status"], n["ar_applied"]) == ("not_required", "posted", 0), n
    assert await jurnal(db, "amendment_credit_note", n["id"]) == []
    assert not await db.store_credit_ledger.find_one({"ref_type": "credit_note", "ref_id": n["id"]})
    beda = await selisih(awal)
    assert (beda[PENDAPATAN], beda[SALDO_KREDIT]) == (0, 0), beda
    # U4 — kirim 100 m
    shp = await kirim(db, dunia, so, QTY, penutup=True)
    jr = await jurnal(db, "shipment_revenue", shp["id"])
    assert len(jr) == 1 and baris(jr) == {PIUTANG: (800_000, 0), PENDAPATAN: (0, 800_000)}, jr
    rk = await jurnal(db, "advance_reclass", order_id=so["id"])
    assert baris(rk) == {UANG_MUKA: (800_000, 0), PIUTANG: (0, 800_000)}, rk
    beda = await selisih(awal)
    assert (beda[UANG_MUKA], beda[PIUTANG], beda[PENDAPATAN]) == (200_000, 0, 800_000), beda


@B_FX14
async def test_PK32_U5_terkirim_sebagian_lalu_kirim_sisa(klien, kepala_admin, db, dunia):
    from services import gl_service
    so = await pesanan(db, dunia)
    awal = await saldo_semua()
    await kirim(db, dunia, so, 40, penutup=False)
    assert (await selisih(awal))[PENDAPATAN] == 400_000
    d, amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 8_000, dunia["pid"])
    assert d.status_code == 200, d.text
    n = await nota_dari(db, amd)
    assert (n["shipped_share"], n["revenue_reversed_net"], n["deferred_net"]) == (0.4, 80_000, 120_000), n
    assert baris(await jurnal(db, "amendment_credit_note", n["id"])) == {PENDAPATAN: (80_000, 0), PIUTANG: (0, 80_000)}
    o = await so_kini(db, so)
    rows = sorted((p["amount"], p.get("gl_bucket")) for p in o["payments"] if p.get("receipt_id") == n["id"])
    assert rows == [(80_000, "nota_koreksi"), (120_000, "nota_tangguh")], o["payments"]
    shp = await kirim(db, dunia, so, 60, penutup=True)
    jr = await jurnal(db, "shipment_revenue", shp["id"])
    assert baris(jr) == {PIUTANG: (480_000, 0), PENDAPATAN: (0, 480_000)}, jr
    beda = await selisih(awal)
    o = await so_kini(db, so)
    assert (beda[PENDAPATAN], beda[PIUTANG], sisa(o)) == (800_000, 800_000, 800_000), (beda, o["payments"])
    assert await gl_service.order_ar_room(so["id"]) == 800_000   # kwitansi berikutnya mengkredit 1-1200 penuh
    rec = await gl_service.order_revenue_recognized(so["id"])
    assert (rec["revenue"], rec["ar"]) == (800_000, 800_000), rec


# ═══ U6–U7 — nota debit kenaikan harga menjadi tagihan (FX-15, K-14) ═══════════════════════════════════════════════
@B_FX15
async def test_PK32_U6_nota_debit_terkirim_penuh(klien, kepala_admin, db, dunia):
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    d, amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 11_000, dunia["pid"])
    assert d.status_code == 200, d.text
    n = await nota_dari(db, amd)
    assert (n["kind"], n["gross_amount"], n["billing_status"], n["status"], n["gl_status"]) == (
        "debit_note", 100_000, "billed", "posted", "posted"), n
    jd = await jurnal(db, "amendment_debit_note", n["id"])
    assert len(jd) == 1 and baris(jd) == {PIUTANG: (100_000, 0), PENDAPATAN: (0, 100_000)}, jd
    assert jd[0]["ref"]["order_id"] == so["id"]
    o = await so_kini(db, so)
    xb = o["extra_billing_lines"]
    assert [(x["debit_note_id"], x["gross"], x["net"], x["ppn"]) for x in xb] == [(n["id"], 100_000, 100_000, 0)], xb
    assert xb[0]["due_date"] and o["grand_total"] == 1_000_000 and sisa(o) == 1_100_000
    # umur piutang memakai nilai tagihan (pembaca sisa tagihan yang dialihkan)
    from services import ar_aging_service
    det = await ar_aging_service.customer_aging_detail(dunia["cus"])
    row = next(x for x in det["items"] if x["order_id"] == so["id"])
    assert (row["grand_total"], row["outstanding"], row.get("ar_ledger")) == (1_100_000, 1_100_000, 1_100_000), row
    r = await kwitansi(klien, kepala_admin, dunia, so, 1_100_001)
    assert r.status_code == 400 and "melebihi sisa tagihan" in r.text, r.text
    r = await kwitansi(klien, kepala_admin, dunia, so, 1_100_000)
    assert r.status_code == 200, r.text
    o = await so_kini(db, so)
    assert (sisa(o), o["payment_status"]) == (0, "paid")


async def test_PK32_U7_nota_debit_sebelum_kirim(db, dunia):
    from services import credit_note_service as cns
    so = await pesanan(db, dunia)
    awal = await saldo_semua()
    n = await cns.issue(kind="debit_note", source="amendment", order=so, number=f"DN-PK32-{next(_n)}",
                        net=100_000, ppn=0, actor=AKTOR_UJI, refs={"reason_label": "Koreksi harga"},
                        lines=[{"product_id": dunia["pid"], "field": "price", "from": 10_000, "to": 11_000}])
    n = await cns.settle(n["id"], AKTOR_UJI)
    assert (n["status"], n["gl_status"], n["billing_status"]) == ("posted", "not_required", "billed"), n
    assert await jurnal(db, "amendment_debit_note", n["id"]) == []
    assert sisa(await so_kini(db, so)) == 1_100_000
    shp = await kirim(db, dunia, so, QTY, penutup=True)
    jr = await jurnal(db, "shipment_revenue", shp["id"])
    assert baris(jr) == {PIUTANG: (1_100_000, 0), PENDAPATAN: (0, 1_100_000)}, jr
    assert (await selisih(awal))[PENDAPATAN] == 1_100_000


# ═══ U8–U10 — nota yang gagal di tengah terlihat dan bisa diulang (FX-13) ══════════════════════════════════════════
@B_FX13
async def test_PK32_U8_jurnal_amandemen_gagal_lalu_ulang(klien, kepala_admin, db, dunia, paksa_jurnal_gagal):
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    async with paksa_jurnal_gagal("sisip", source_type="amendment_credit_note") as gagal:
        d, amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 8_000, dunia["pid"])
    assert d.status_code == 200 and len(gagal) == 1, d.text
    n = await nota_dari(db, amd)
    assert (n["status"], n["gl_status"], n["effects"]["allocation"], n["effects"]["journal"]) == (
        "issued", "failed", "done", "pending"), n
    panel = (await klien.get("/api/finance/posting-failures", headers=kepala_admin,
                             params={"kind": "credit_note", "page_size": 200})).json()
    assert n["id"] in {x["id"] for x in panel["rows"]}, panel
    r = await klien.post(f"/api/finance/posting-failures/credit_note/{n['id']}/retry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    n = await nota_dari(db, amd)
    assert (n["status"], n["gl_status"]) == ("posted", "posted"), n
    j = await jurnal(db, "amendment_credit_note", n["id"])
    assert len(j) == 1 and baris(j) == {PENDAPATAN: (200_000, 0), PIUTANG: (0, 200_000)}, j
    o = await so_kini(db, so)
    assert len([p for p in o["payments"] if p.get("receipt_id") == n["id"]]) == 1


async def nota_batal_item(db, dunia, *, diakui: bool) -> Tuple[dict, dict]:
    """Pesanan 2 baris A 700.000 + B 300.000; B dibatalkan (pesanan → 700.000) → nota batal item `pending_finance`
    300.000 lewat pembuatnya (`od_cancel_credit_note.create`). `diakui` = pendapatan sudah dijurnal di tingkat pesanan
    (fixture jurnal `sales_order` Dr 1-1200 1.000.000 / Cr 4-1000 1.000.000)."""
    from services import gl_service, od_cancel_credit_note as occn
    sebelum = await pesanan(db, dunia)
    sebelum["grand_total"] = 1_000_000
    line_b = {"product_id": uid("pb"), "product_name": "Kain B", "quantity": 30, "unit": "meter", "price": 10_000,
              "line_total": 300_000}
    await db.sales_orders.update_one({"id": sebelum["id"]}, {"$set": {
        "grand_total": 700_000, "total_amount": 700_000, "net_subtotal": 700_000, "status": "shipped",
        "items": [{**sebelum["items"][0], "quantity": 70, "base_quantity": 70, "line_total": 700_000,
                   "subtotal": 700_000}]}})
    if diakui:
        await gl_service._insert_entry(
            lines=[{"account_code": PIUTANG, "debit": 1_000_000, "credit": 0.0},
                   {"account_code": PENDAPATAN, "debit": 0.0, "credit": 1_000_000}],
            description=f"pendapatan {sebelum['number']} (fixture)", date=now_iso(), source_type="sales_order",
            source_id=sebelum["id"], entity_id=KSC, created_by="uji")
    note = await occn.create(sebelum, {"grand_total": 700_000, "ppn_amount": 0}, line_b, "pelanggan batal",
                             "uji", "sudah dikirim", uid("odi"))
    return sebelum, note


@B_FX13
async def test_PK32_U9_batal_item_jurnal_gagal_lalu_ulang(klien, kepala_admin, db, dunia, paksa_jurnal_gagal):
    so, note = await nota_batal_item(db, dunia, diakui=True)
    assert note["status"] == "pending_finance"
    async with paksa_jurnal_gagal("sisip", source_type="amendment_credit_note"):
        r = await klien.post(f"/api/credit-notes/{note['id']}/finance-review", headers=kepala_admin,
                             json={"action": "issue", "note": "terbitkan"})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["gl_status"]) == ("issued", "failed"), r.json()
    r = await klien.post(f"/api/finance/posting-failures/credit_note/{note['id']}/retry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    n = await db.credit_notes.find_one({"id": note["id"]}, {"_id": 0})
    assert (n["status"], n["gl_status"]) == ("posted", "posted"), n
    j = await jurnal(db, "amendment_credit_note", note["id"])
    assert len(j) == 1 and baris(j) == {PENDAPATAN: (300_000, 0), PIUTANG: (0, 300_000)}, j


@B_FX13
async def test_PK32_U10_batal_item_tanpa_pendapatan_diakui(klien, kepala_admin, db, dunia):
    so, note = await nota_batal_item(db, dunia, diakui=False)
    r = await klien.post(f"/api/credit-notes/{note['id']}/finance-review", headers=kepala_admin,
                         json={"action": "issue", "note": "terbitkan"})
    assert r.status_code == 200, r.text
    n = await db.credit_notes.find_one({"id": note["id"]}, {"_id": 0})
    assert (n["status"], n["gl_status"]) == ("posted", "not_required"), n
    assert await jurnal(db, "amendment_credit_note", note["id"]) == []
    assert not [p for p in (await so_kini(db, so)).get("payments") or [] if p.get("receipt_id") == note["id"]]


# ═══ U11 — retur per roll memakai harga efektif (FX-12) ═════════════════════════════════════════════════════════════
@B_FX12
async def test_PK32_U11_retur_per_roll_harga_efektif(klien, kepala_admin, db, dunia):
    from services import return_roll_settlement_service as rrs
    so = await pesanan(db, dunia)
    shp = await kirim(db, dunia, so, QTY, penutup=True)
    d, _amd = await koreksi(klien, kepala_admin, dunia["h2"], so, 8_000, dunia["pid"])
    assert d.status_code == 200, d.text
    rid = shp["rolls"][0]["roll_id"]
    sr = uid("sr")
    await db.sales_returns.insert_one({
        "id": sr, "number": f"RJ/PK32/{sr[-6:]}", "entity_id": KSC, "status": "inspected", "order_id": so["id"],
        "order_number": so["number"], "customer_id": dunia["cus"], "customer_name": "Toko c1 PK-32",
        "created_at": now_iso(), "roll_locations": {rid: {"stage": "received", "warehouse_id": dunia["wid"]}},
        "items": [{"product_id": dunia["pid"], "product_name": "Kain Uji PK-32", "quantity_returned": 50,
                   "unit": "meter", "condition": "ok", "reason": "salah warna", "roll_ids": [rid],
                   "roll_qtys": {rid: 50},
                   "inspection": {"grade": "A", "roll_results": {rid: {"grade": "A", "actual_qty": 50,
                                                                       "condition": "ok"}}}}]})
    ret = await db.sales_returns.find_one({"id": sr}, {"_id": 0})
    plan = await rrs.plan_event(ret, [{"roll_id": rid, "outcome": "refund"}])
    assert (plan["gross_amount"], plan["lines"][0]["unit_price"]) == (400_000, 8_000), plan["lines"]
    # Lapis B = langkah nota kredit penyelesaian (`issue_settlement_note`, dipanggil `_apply`); penyelesaian utuh lewat
    # API memakai pembaruan larik bertapis yang tidak didukung database tiruan (lihat laporan PK-27).
    ev = {"id": uid("rst"), "seq": 1, "status": "posting", "plan": plan, "restocked": []}
    await db.sales_returns.update_one({"id": sr}, {"$push": {"settlements": ev}})
    ret = await db.sales_returns.find_one({"id": sr}, {"_id": 0})
    n = await rrs.issue_settlement_note(ret, ev["id"], plan, AKTOR_UJI)
    assert (n["gross_amount"], n["source"], n["status"], n["gl_status"]) == (400_000, "sales_return_roll", "posted",
                                                                            "posted"), n
    o = await so_kini(db, so)
    assert sisa(o) == 1_000_000 - 200_000 - 400_000


# ═══ U12 — satu penyisip & penjaga posting (statik) ═════════════════════════════════════════════════════════════════
@B_FX13
async def test_PK32_U12_satu_penyisip_dan_penjaga_posting():
    import json
    import subprocess
    import sys
    rx = re.compile(r"credit_notes\s*\.\s*insert_(one|many)|\[\s*[\"']credit_notes[\"']\s*\]\s*\.\s*insert_")
    luar = []
    for f in (REPO / "backend").rglob("*.py"):
        rel = f.relative_to(REPO / "backend").as_posix()
        if rel.startswith(("tests_mem/", "tests/")) or f.name.startswith("test_") or rel == "services/credit_note_service.py":
            continue
        if rx.search(f.read_text(encoding="utf-8")):
            luar.append(rel)
    assert luar == [], luar
    garis = json.loads((REPO / "scripts/guardrails/baselines/posting_coverage.json").read_text(encoding="utf-8"))
    nota = [r for r in garis.get("panggilan") or [] if "amendment" in r.get("fungsi_gl", "")
            or "od_cancel" in r.get("lokasi", "")] + [k for k in garis.get("fungsi") or {} if "amendment" in k]
    assert nota == [], nota
    out = subprocess.run([sys.executable, str(REPO / "scripts/guardrails/verify_posting_coverage.py")],
                         capture_output=True, text=True, cwd=REPO)
    assert out.returncode == 0, out.stdout + out.stderr


# ═══ Serah-terima (a) — mesin dipanggil langsung dengan angka U1, U3, U5 ═══════════════════════════════════════════
async def test_PK32_a_U1_mesin_terkirim_penuh(db, dunia):
    from services import amendment_service, credit_note_service as cns, gl_service
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    so = await so_kini(db, so)
    sp = await cns.recognition_split(so, 200_000, 0, -1)
    assert (sp["porsi_terkirim"], sp["sekarang_net"], sp["deferred_net"]) == (1.0, 200_000, 0), sp
    await cns.assert_cap(so, 1_000_000)
    with pytest.raises(cns.CreditNoteError) as e:
        await cns.assert_cap(so, 1_000_000.02)
    assert e.value.status_code == 409 and "melebihi nilai pesanan Rp 1.000.000" in e.value.detail, e.value.detail
    await amandemen_fixture(db, so, dunia["pid"], dari=10_000, ke=8_000)
    n = await cns.issue(kind="credit_note", source="amendment", order=so, number=f"CN-PK32-{next(_n)}",
                        net=200_000, ppn=0, actor=AKTOR_UJI, refs={"reason_label": "Koreksi harga"},
                        lines=[{"product_id": dunia["pid"], "field": "price", "from": 10_000, "to": 8_000}])
    assert (n["status"], n["gl_status"], n["effects"]) == ("issued", "pending", {
        "allocation": "pending", "store_credit": "pending", "journal": "pending"}), n
    assert (n["revenue_reversed_net"], n["ar_part"], n["store_credit_part"], n["allocation_amount"],
            n["allocation_deferred"], n["excess_payment"]) == (200_000, 200_000, 0, 200_000, 0, 0), n
    n = await cns.settle(n["id"], AKTOR_UJI)
    assert (n["status"], n["gl_status"], n["ar_applied"]) == ("posted", "posted", 200_000), n
    assert baris(await jurnal(db, "amendment_credit_note", n["id"])) == {PENDAPATAN: (200_000, 0), PIUTANG: (0, 200_000)}
    o = await so_kini(db, so)
    assert [(p["amount"], p["gl_bucket"], p["kind"]) for p in o["payments"]] == [(200_000, "nota_koreksi", "nota_kredit")]
    assert sisa(o) == 800_000 and await cns.settle(n["id"], AKTOR_UJI) == n   # aman diulang
    eff = await gl_service.order_effective_totals(o)
    assert eff == {"grand": 800_000, "ppn": 0, "net": 800_000}, eff
    eo = await amendment_service.effective_order(o)
    assert (eo["items"][0]["price"], eo["items"][0]["line_total"], eo["grand_total"]) == (8_000, 800_000, 800_000)
    assert o["grand_total"] == 1_000_000   # dokumen asal tidak diubah
    await cns.assert_cap(o, 800_000)
    with pytest.raises(cns.CreditNoteError):
        await cns.assert_cap(o, 800_000.02)


async def test_PK32_a_U3_mesin_dibayar_belum_dikirim(db, dunia):
    from services import credit_note_service as cns
    so = await pesanan(db, dunia)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {
        "payments": [{"id": uid("pay"), "kind": "kas", "amount": 1_000_000, "receipt_id": uid("arc"),
                      "gl_bucket": "advance", "method": "transfer", "date": now_iso()}],
        "paid_total": 1_000_000, "payment_status": "paid"}})
    so = await so_kini(db, so)
    n = await cns.issue(kind="credit_note", source="amendment", order=so, number=f"CN-PK32-{next(_n)}",
                        net=200_000, ppn=0, actor=AKTOR_UJI, lines=[])
    assert (n["revenue_reversed_net"], n["deferred_net"], n["excess_payment"], n["allocation_amount"],
            n["shipped_share"]) == (0, 200_000, 200_000, 0, 0), n
    n = await cns.settle(n["id"], AKTOR_UJI)
    assert (n["status"], n["gl_status"], n["effects"]) == ("posted", "not_required", {
        "allocation": "skipped", "store_credit": "skipped", "journal": "skipped"}), n
    assert await jurnal(db, "amendment_credit_note", n["id"]) == []


async def test_PK32_a_U5_mesin_terkirim_sebagian(db, dunia):
    from services import credit_note_service as cns
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, 40, penutup=False)
    so = await so_kini(db, so)
    n = await cns.issue(kind="credit_note", source="amendment", order=so, number=f"CN-PK32-{next(_n)}",
                        net=200_000, ppn=0, actor=AKTOR_UJI, lines=[])
    assert (n["shipped_share"], n["revenue_reversed_net"], n["deferred_net"], n["ar_part"],
            n["allocation_amount"], n["allocation_deferred"]) == (0.4, 80_000, 120_000, 80_000, 200_000, 120_000), n
    n = await cns.settle(n["id"], AKTOR_UJI)
    assert baris(await jurnal(db, "amendment_credit_note", n["id"])) == {PENDAPATAN: (80_000, 0), PIUTANG: (0, 80_000)}
    o = await so_kini(db, so)
    assert sorted((p["amount"], p["gl_bucket"]) for p in o["payments"]) == [(80_000, "nota_koreksi"),
                                                                             (120_000, "nota_tangguh")]
    assert sisa(o) == 800_000


async def test_PK32_a_nota_debit_dan_batal(db, dunia, paksa_jurnal_gagal):
    from services import credit_note_service as cns
    from services.customer_service import _order_grand_total
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, penutup=True)
    so = await so_kini(db, so)
    async with paksa_jurnal_gagal("sisip", source_type="amendment_debit_note"):
        n = await cns.issue(kind="debit_note", source="amendment", order=so, number=f"DN-PK32-{next(_n)}",
                            net=100_000, ppn=0, actor=AKTOR_UJI, lines=[])
        assert (n["revenue_added_net"], n["deferred_net"]) == (100_000, 0), n
        n = await cns.settle(n["id"], AKTOR_UJI)
    assert (n["status"], n["gl_status"], n["effects"]["allocation"]) == ("issued", "failed", "done"), n
    o = await so_kini(db, so)
    assert _order_grand_total(o) == 1_100_000 and len(o["extra_billing_lines"]) == 1
    with pytest.raises(cns.CreditNoteError) as e:   # sudah menambah tagihan → tidak bisa dibatalkan
        await cns.void(n["id"], "salah ketik nota", AKTOR_UJI)
    assert e.value.status_code == 409 and "tidak bisa dibatalkan" in e.value.detail
    n = await cns.settle(n["id"], AKTOR_UJI)
    assert (n["status"], n["gl_status"]) == ("posted", "posted"), n
    assert len((await so_kini(db, so))["extra_billing_lines"]) == 1   # ulang tidak menambah baris
    # batal: alasan wajib; nota yang belum berefek boleh dibatalkan
    m = await cns.issue(kind="credit_note", source="od_item_cancel", order=so, number=f"CN-PK32-{next(_n)}",
                        net=50_000, ppn=0, actor=AKTOR_UJI, lines=[], status="pending_finance")
    with pytest.raises(cns.CreditNoteError) as e:
        await cns.void(m["id"], "abc", AKTOR_UJI)
    assert e.value.status_code == 400 and e.value.detail == "Alasan pembatalan nota wajib (minimal 5 huruf)."
    v = await cns.void(m["id"], "disepakati tanpa pengembalian", AKTOR_UJI)
    assert (v["status"], v["status_label"]) == ("void", "Batal")
