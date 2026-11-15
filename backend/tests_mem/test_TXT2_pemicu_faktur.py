"""TX-T2 (TX-05, K-32) — pemicu faktur pajak yang bisa diatur, draf otomatis per surat jalan, dokumen pajak retur, dan
pencocokan PPN keluaran. Spesifikasi `docs/blueprint/unit/TX-T2.md`.

Fixture T1 (DISISIP langsung, kecuali disebut): PT `ent_ksc` (PKP, tarif 12 % × DPP nilai lain 11/12 = efektif 11 %),
pelanggan `cus_txt2` (NPWP + alamat lengkap) dan `cus_txt2_kosong` (tanpa NPWP/NIK, beralamat), produk 100.000/m.
Pesanan dihitung `config_service.compute_order_pricing` (mesin harga yang sama dengan checkout) lalu disisip berstatus
`confirmed`. "Kirim" = surat jalan fixture lalu jurnalnya lewat `gl_service.post_order_revenue_and_cogs` (fungsi yang
dipanggil tombol kirim; tombol kirim gudang menuntut tag RFID — gerbang H7, tidak disentuh). Pemicu PT diubah lewat API
(`PUT /api/config/values`); terbit/buang/bangun ulang/pencocokan lewat API; `draft_for_shipment`/`draft_for_credit_note`
dipanggil langsung (serah-terima (a): kaitnya di (b)).

Hitung tangan (contoh angka `00` §9):
  T1  100 m × 100.000 = harga jual 10.000.000; DPP 10.000.000 × 11/12 = 9.166.666,67; PPN 12 % × DPP = 1.100.000;
      total 11.100.000.
  SJ-1 (40 m, porsi 0,4): jurnal Dr 1-1200 4.440.000 / Cr 4-1000 4.000.000 / Cr 2-1200 440.000.
      Draf: PPN 440.000 (Σ kredit 2-1200), harga jual 4.000.000 (Σ kredit 4-1000), DPP 4.000.000 × 11 ÷ 12 =
      3.666.666,666… → 3.666.666,67 (dua desimal, potret pesanan); total 4.440.000.
  SJ-2 (60 m, penutup): sisa 10.000.000 − 4.000.000 = 6.000.000; PPN 1.100.000 − 440.000 = 660.000.
      Σ faktur SJ-1 + SJ-2 = 440.000 + 660.000 = 1.100.000 = PPN pesanan.
  U5  faktur terbit masa itu 440.000; buku besar 440.000 + 660.000 = 1.100.000; selisih 1.100.000 − 440.000 = 660.000
      = PPN jurnal SJ-2 yang belum berfaktur → seluruhnya "surat jalan tanpa faktur"; belum terjelaskan 0.
  U6  + jurnal manual Cr 2-1200 50.000 → buku besar 1.150.000; selisih 710.000; terjelaskan 660.000; belum 50.000.
  U9  nota kredit retur 10 m atas SJ-1: harga jual 1.000.000 + PPN 110.000 → jurnal Dr 4-1000 1.000.000 / Dr 2-1200
      110.000 / Cr 1-1200 1.110.000; dokumen retur PPN 110.000; rekap keluaran 440.000 − 110.000 = 330.000.
"""
from __future__ import annotations

import importlib
import itertools
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jumlah, jurnal, pt_uji

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
HARGA, QTY = 100_000, 100
PIUTANG, PENDAPATAN, PPN_OUT = "1-1200", "4-1000", "2-1200"
KUNCI = "tax.pemicu_faktur"
REPO = Path(__file__).resolve().parents[2]
_n = itertools.count(1)
#: keadaan berlanjut antar-uji (satu modul = satu pekerja, `--dist loadscope`)
BAG: Dict[str, Any] = {}


def uid(awalan: str) -> str:
    return f"{awalan}_txt2_{uuid.uuid4().hex[:8]}"


def baris(jes) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for je in jes if isinstance(jes, list) else [jes]:
        for ln in je["lines"]:
            d, c = out.get(ln["account_code"], (0.0, 0.0))
            out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2),
                                       round(c + float(ln.get("credit") or 0), 2))
    return out


def _vdi():
    sys.path.insert(0, str(REPO / "scripts"))
    return importlib.import_module("verify_data_integrity")


async def _invarian(db, capsys) -> List[str]:
    """Baris keluaran INV-TAX-OUT-01 dari `scripts/verify_data_integrity.py` (lapisan faktur, database tiruan)."""
    capsys.readouterr()
    await _vdi().layer_tax_invoice_invariants(db)
    keluar = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    return [ln.strip() for ln in keluar.splitlines() if "INV-TAX-OUT-01" in ln or "≤1 faktur aktif" in ln
            or "field kunci aktif" in ln]


# ── Fixture bersama ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def dunia(db, akun, sesi, kepala_admin):
    pid, wid = uid("prd"), uid("wh")
    await db.products.insert_one({"id": pid, "name": "Kain Uji TX-T2", "sku": "SKU-TXT2", "base_unit": "meter",
                                  "harga_pokok": 60_000, "price": HARGA, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji TX-T2", "entity_id": KSC, "is_active": True,
                                    "created_at": now_iso()})
    alamat = [{"address": "Jl. Pajak 1", "city": "Bandung", "is_primary": True}]
    await db.customers.insert_many([
        {"id": "cus_txt2", "name": "Toko Pajak Lengkap", "entity_id": KSC, "status": "active",
         "npwp": "01.234.567.8-901.000", "addresses": alamat, "created_at": now_iso()},
        {"id": "cus_txt2_kosong", "name": "Toko Tanpa Identitas", "entity_id": KSC, "status": "active", "npwp": "",
         "addresses": alamat, "created_at": now_iso()}])
    pt3 = await pt_uji("TX2")
    await db.business_entities.update_one({"id": pt3}, {"$set": {"default_tax_mode": "ppn"}})   # PT PKP ketiga
    return {"pid": pid, "wid": wid, "pt3": pt3, "adm": kepala_admin}


async def pesanan(db, dunia, *, entity: str = KSC, customer: str = "cus_txt2", qty: float = QTY) -> dict:
    from services import config_service
    pr = await config_service.compute_order_pricing(
        [{"product_id": dunia["pid"], "product_name": "Kain Uji TX-T2", "sku": "SKU-TXT2", "quantity": qty,
          "base_quantity": qty, "unit": "meter", "price": HARGA}], entity_id=entity)
    i = next(_n)
    so = {"id": uid("so"), "number": f"SO/TXT2/{i:03d}", "entity_id": entity, "customer_id": customer,
          "customer_name": "Toko Pajak Lengkap" if customer == "cus_txt2" else "Toko Tanpa Identitas",
          "status": "confirmed", "payment_term_code": "NET30", "payment_method": "kredit",
          "allocations": [{"warehouse_id": dunia["wid"], "product_id": dunia["pid"], "qty": qty}],
          "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "created_at": now_iso(), **pr}
    await db.sales_orders.insert_one(dict(so))
    return so


async def kirim(db, dunia, so: dict, qty: float, nomor: str, *, penutup: bool) -> dict:
    """Surat jalan `qty` m lalu jurnalnya lewat alur kirim (`post_order_revenue_and_cogs`)."""
    from services import gl_service
    roll = uid("r")
    shp = {"id": uid("shp"), "shipment_no": nomor, "entity_id": so["entity_id"], "order_id": so["id"],
           "order_number": so["number"], "product_id": dunia["pid"], "product_name": "Kain Uji TX-T2",
           "sku": "SKU-TXT2", "warehouse_id": dunia["wid"], "qty": qty, "unit": "meter",
           "rolls": [{"roll_id": roll, "length": qty, "unit_cost": 60_000, "extended_cost": qty * 60_000}],
           "status": "dispatched", "created_at": now_iso(), "gl_status": "pending"}
    await db.shipments.insert_one(dict(shp))
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "shipped" if penutup else "partially_shipped"}})
    await gl_service.post_order_revenue_and_cogs(so["id"])
    return shp


async def pemicu(klien, h, nilai: str, pt: str = KSC, alasan: str = "uji TX-T2"):
    return await klien.put("/api/config/values", headers=h, json={"items": [
        {"key": KUNCI, "value": nilai, "scope_type": "entity", "scope_id": pt, "reason": alasan}]})


async def rekap(klien, h, masa: str, pt: str = KSC) -> dict:
    r = await klien.get("/api/tax/vat-summary", params={"period": masa, "entity_id": pt}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["keluaran"]


async def cocok(klien, h, masa: str, pt: str = KSC) -> dict:
    r = await klien.get("/api/tax/output-reconciliation", params={"period": masa, "entity_id": pt}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def terbitkan(klien, h, fkt_id: str, **isi):
    return await klien.post(f"/api/tax-invoices/{fkt_id}/issue", json=isi, headers=h)


# ═══ U1 — pemicu bawaan = perilaku hari ini ═════════════════════════════════════════════════════════════════════════
async def test_TXT2_U1_pemicu_bawaan_tanpa_draf_terbit_per_pesanan(klien, db, dunia):
    from services import tax_invoice_service as tis
    so = await pesanan(db, dunia, entity=dunia["pt3"])
    assert (so["ppn_amount"], so["grand_total"], so["net_subtotal"]) == (1_100_000, 11_100_000, 10_000_000), so
    await kirim(db, dunia, so, 40, "SJ-1", penutup=False)
    draf = getattr(tis, "draft_for_shipment", None)   # fungsi baru; kode lama tidak punya → tidak ada draf juga
    if draf is not None:
        assert await draf(so["id"], "SJ-1") is None
    assert await jumlah("tax_invoices", {"order_id": so["id"]}) == 0
    r = await klien.post(f"/api/sales-orders/{so['id']}/tax-invoice", json={}, headers=dunia["adm"])
    assert r.status_code == 200, r.text
    f = r.json()
    assert (f["status"], f["ppn_amount"], f["grand_total"], f["active_key"]) == (
        "normal", 1_100_000, 11_100_000, f"so:{so['id']}"), f


# ═══ U2/U3 — per surat jalan: draf dari jurnal, idempoten, terbit ════════════════════════════════════════════════════
async def test_TXT2_U2_pemicu_surat_jalan_draf_dari_jurnal(klien, db, dunia):
    from services import tax_invoice_service as tis
    r = await pemicu(klien, dunia["adm"], "surat_jalan")
    assert r.status_code == 200, r.text
    so = await pesanan(db, dunia)
    BAG["s1"] = so
    shp = await kirim(db, dunia, so, 40, "SJ-1", penutup=False)
    BAG["roll_sj1"] = shp["rolls"][0]["roll_id"]
    je = await db.journal_entries.find_one({"source_type": "shipment_revenue", "source_id": shp["id"]}, {"_id": 0})
    assert baris(je) == {PIUTANG: (4_440_000, 0), PENDAPATAN: (0, 4_000_000), PPN_OUT: (0, 440_000)}, je
    d = await tis.draft_for_shipment(so["id"], "SJ-1")
    assert d is not None
    assert (d["status"], d["doc_kind"], d["trigger"], d["ppn_amount"], d["net_subtotal"], d["dpp"], d["grand_total"],
            d["active_key"], d["shipment_no"], d["shipment_ids"]) == (
        "draf", "faktur", "surat_jalan", 440_000, 4_000_000, 3_666_666.67, 4_440_000, f"sj:{so['id']}:SJ-1", "SJ-1",
        [shp["id"]]), d
    assert [(it["quantity"], it["line_total"]) for it in d["items"]] == [(40, 4_000_000)]
    assert d["journal_entry_ids"] == [je["id"]]
    assert await jumlah("tax_invoices", {"order_id": so["id"]}) == 1
    BAG["masa"] = str(d["faktur_date"])[:7]
    BAG["d_sj1"] = d
    kel = await rekap(klien, dunia["adm"], BAG["masa"])
    assert (kel["ppn"], kel["count"]) == (0, 0), kel   # draf belum terbit: tidak dihitung


async def test_TXT2_U3_panggil_ulang_satu_draf_lalu_terbit(klien, db, dunia):
    from services import tax_invoice_service as tis
    so, d = BAG["s1"], BAG["d_sj1"]
    d2 = await tis.draft_for_shipment(so["id"], "SJ-1")
    assert d2["id"] == d["id"] and await jumlah("tax_invoices", {"order_id": so["id"]}) == 1
    r = await terbitkan(klien, dunia["adm"], d["id"])
    assert r.status_code == 200, r.text
    f = r.json()
    assert (f["status"], f["active_key"], f["ppn_amount"], f["data_incomplete"]) == (
        "normal", f"sj:{so['id']}:SJ-1", 440_000, []), f
    assert f["issued_at"] and f["issued_by"] and f["faktur_date"] == d["faktur_date"]
    BAG["f_sj1"] = f
    kel = await rekap(klien, dunia["adm"], BAG["masa"])
    assert (kel["ppn"], kel["count"]) == (440_000, 1), kel
    r = await terbitkan(klien, dunia["adm"], d["id"])
    assert r.status_code == 409 and r.json()["detail"] == "Dokumen ini bukan draf.", r.text


# ═══ U5/U6 — pencocokan PPN keluaran + INV-TAX-OUT-01 ════════════════════════════════════════════════════════════════
async def test_TXT2_U5_pencocokan_selisih_terjelaskan(klien, db, dunia, capsys):
    from services import tax_invoice_service as tis
    so = BAG["s1"]
    shp2 = await kirim(db, dunia, so, 60, "SJ-2", penutup=True)
    je2 = await db.journal_entries.find_one({"source_type": "shipment_revenue", "source_id": shp2["id"]}, {"_id": 0})
    assert baris(je2) == {PIUTANG: (6_660_000, 0), PENDAPATAN: (0, 6_000_000), PPN_OUT: (0, 660_000)}, je2
    d2 = await tis.draft_for_shipment(so["id"], "SJ-2")
    assert (d2["status"], d2["ppn_amount"], d2["net_subtotal"]) == ("draf", 660_000, 6_000_000), d2
    BAG["d_sj2"] = d2
    rec = await cocok(klien, dunia["adm"], BAG["masa"])
    assert (rec["faktur_ppn"], rec["retur_ppn"], rec["gl_ppn"], rec["difference"], rec["unexplained"]) == (
        440_000, 0, 1_100_000, 660_000, 0), rec
    sj = rec["causes"]["surat_jalan_tanpa_faktur"]
    assert [(x["order_id"], x["shipment_no"], x["amount"], x["effect"]) for x in sj] == [
        (so["id"], "SJ-2", 660_000, 660_000)], sj
    assert rec["causes"]["faktur_tanpa_jurnal"] == [] and rec["causes"]["retur_tanpa_dokumen"] == []
    assert "2-1200" in rec["accounts"]
    keluar = await _invarian(db, capsys)
    assert any(ln.startswith("[PASS]") and "INV-TAX-OUT-01" in ln for ln in keluar), keluar
    assert not any("belum terjelaskan" in ln for ln in keluar), keluar
    assert any("PASS" in ln and "≤1 faktur aktif" in ln for ln in keluar), keluar          # SJ-1 + SJ-2: dua kunci
    assert any("PASS" in ln and "field kunci aktif" in ln for ln in keluar), keluar


async def test_TXT2_U6_jurnal_manual_ppn_belum_terjelaskan(klien, db, dunia, capsys):
    je = await jurnal(KSC, now_iso(), [("1-1100", 50_000, 0), (PPN_OUT, 0, 50_000)], "PPN manual uji TX-T2",
                      uid("man"))
    try:
        rec = await cocok(klien, dunia["adm"], BAG["masa"])
        assert (rec["gl_ppn"], rec["difference"], rec["unexplained"]) == (1_150_000, 710_000, 50_000), rec
        assert [j["number"] for j in rec["unexplained_journals"]] == [je["number"]]
        ent = await db.business_entities.find_one({"id": KSC}, {"_id": 0})
        nama = ent.get("name") or ent.get("legal_name")
        from services.tax_center_service import bulan_tahun
        keluar = await _invarian(db, capsys)
        merah = [ln for ln in keluar if "belum terjelaskan" in ln]
        assert merah and nama in merah[0] and bulan_tahun(BAG["masa"]) in merah[0] and "Rp 50.000" in merah[0], keluar
        tingkat = "[FAIL]" if _vdi().INV_TAX_OUT_WAJIB else "[WARN]"   # (a) peringatan dulu; (b) wajib hijau
        assert merah[0].startswith(tingkat), merah
    finally:
        await db.journal_entries.update_one({"id": je["id"]}, {"$set": {"status": "void"}})
    rec = await cocok(klien, dunia["adm"], BAG["masa"])
    assert rec["unexplained"] == 0, rec


# ═══ U9 — dokumen pajak retur dari nota kredit (mesin PK-32) ════════════════════════════════════════════════════════
async def test_TXT2_U9_nota_kredit_ber_ppn_dokumen_retur(klien, db, dunia):
    from services import credit_note_service as cns, tax_invoice_service as tis
    so = await db.sales_orders.find_one({"id": BAG["s1"]["id"]}, {"_id": 0})
    rid = uid("ret")
    await db.sales_returns.insert_one({
        "id": rid, "number": "RET/TXT2/001", "entity_id": KSC, "order_id": so["id"], "order_number": so["number"],
        "customer_id": "cus_txt2", "status": "approved", "approved_at": now_iso(), "created_at": now_iso(),
        "items": [{"product_id": dunia["pid"], "quantity": 10, "roll_ids": [BAG["roll_sj1"]]}]})
    n = await cns.issue(kind="credit_note", source="sales_return", order=so, number="CN/TXT2/001", net=1_000_000,
                        ppn=110_000, actor=AKTOR_UJI, refs={"return_id": rid, "return_number": "RET/TXT2/001"},
                        lines=[{"product_id": dunia["pid"], "product_name": "Kain Uji TX-T2", "quantity": 10,
                                "unit": "meter", "price": HARGA, "line_total": 1_000_000,
                                "roll_ids": [BAG["roll_sj1"]]}],
                        extra={"settlement": "ar", "allocation_amount": 1_110_000, "ppn_rate": 12})
    n = await cns.settle(n["id"], AKTOR_UJI)
    assert (n["status"], n["gl_status"]) == ("posted", "posted"), n
    je = await db.journal_entries.find_one({"id": n["journal_entry_id"]}, {"_id": 0})
    assert baris(je) == {PENDAPATAN: (1_000_000, 0), PPN_OUT: (110_000, 0), PIUTANG: (0, 1_110_000)}, je
    d = await tis.draft_for_credit_note(n)
    assert d is not None
    assert (d["status"], d["doc_kind"], d["trigger"], d["ppn_amount"], d["net_subtotal"], d["dpp"], d["active_key"],
            d["credit_note_id"], d["ref_tax_invoice_id"]) == (
        "draf", "retur", "retur", 110_000, 1_000_000, 916_666.67, f"retur:{n['id']}", n["id"], BAG["f_sj1"]["id"]), d
    assert (await tis.draft_for_credit_note(n))["id"] == d["id"]   # idempoten
    r = await terbitkan(klien, dunia["adm"], d["id"])
    assert r.status_code == 200 and r.json()["status"] == "normal", r.text
    BAG["retur"] = r.json()
    kel = await rekap(klien, dunia["adm"], BAG["masa"])
    assert (kel["ppn"], kel["faktur_ppn"], kel["retur_ppn"]) == (330_000, 440_000, 110_000), kel
    rec = await cocok(klien, dunia["adm"], BAG["masa"])
    assert (rec["faktur_ppn"], rec["retur_ppn"], rec["gl_ppn"], rec["unexplained"]) == (
        440_000, 110_000, 990_000, 0), rec
    assert rec["causes"]["retur_tanpa_dokumen"] == [], rec


# ═══ U4 — dua faktur per surat jalan = PPN pesanan ══════════════════════════════════════════════════════════════════
async def test_TXT2_U4_surat_jalan_kedua_terbit_jumlah_sama_ppn_pesanan(klien, db, dunia):
    from services import tax_invoice_service as tis
    so = BAG["s1"]
    d2 = await tis.draft_for_shipment(so["id"], "SJ-2")
    assert d2["id"] == BAG["d_sj2"]["id"]
    r = await terbitkan(klien, dunia["adm"], d2["id"])
    assert r.status_code == 200 and r.json()["ppn_amount"] == 660_000, r.text
    fakturs = [f async for f in db.tax_invoices.find({"order_id": so["id"], "doc_kind": "faktur", "status": "normal"},
                                                     {"_id": 0})]
    assert sorted(f["ppn_amount"] for f in fakturs) == [440_000, 660_000]
    assert sum(f["ppn_amount"] for f in fakturs) == so["ppn_amount"] == 1_100_000
    rec = await cocok(klien, dunia["adm"], BAG["masa"])
    assert (rec["difference"], rec["unexplained"], rec["causes"]["surat_jalan_tanpa_faktur"]) == (0, 0, []), rec


# ═══ U8 — data pajak pelanggan belum lengkap ════════════════════════════════════════════════════════════════════════
async def test_TXT2_U8_data_pajak_belum_lengkap_ditolak_lalu_lengkap(klien, db, dunia):
    from services import tax_invoice_service as tis
    so = await pesanan(db, dunia, customer="cus_txt2_kosong")
    await kirim(db, dunia, so, QTY, "SJ-1", penutup=True)
    d = await tis.draft_for_shipment(so["id"], "SJ-1")
    assert d["data_incomplete"] == ["identitas_pajak"], d
    r = await terbitkan(klien, dunia["adm"], d["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Lengkapi data pajak pelanggan dulu: identitas pajak."
    assert (await db.tax_invoices.find_one({"id": d["id"]}))["status"] == "draf"
    r = await klien.patch("/api/customers/cus_txt2_kosong", json={"data": {"npwp": "09.876.543.2-109.000"}},
                          headers=dunia["adm"])
    assert r.status_code == 200, r.text
    r = await terbitkan(klien, dunia["adm"], d["id"])
    assert r.status_code == 200, r.text
    f = r.json()
    assert (f["status"], f["data_incomplete"], f["customer_tax"]["id_number"]) == (
        "normal", [], "09.876.543.2-109.000"), f


# ═══ U10/U11 — terbit per pesanan ditolak; uang muka belum bisa dipakai ═════════════════════════════════════════════
async def test_TXT2_U10_terbit_per_pesanan_ditolak_di_pt_per_surat_jalan(klien, db, dunia):
    r = await klien.post(f"/api/sales-orders/{BAG['s1']['id']}/tax-invoice", json={}, headers=dunia["adm"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "PT ini menerbitkan faktur per surat jalan. Terbitkan dari antrean draf."


async def test_TXT2_U11_pemicu_uang_muka_ditolak_saat_disimpan(klien, db, dunia):
    from services.config_resolver import value_of
    r = await pemicu(klien, dunia["adm"], "uang_muka")
    assert r.status_code == 400, r.text
    assert "belum bisa dipakai" in r.text and "uang muka" in r.text, r.text
    assert await value_of(KUNCI, {"entity_id": KSC}) == "surat_jalan"


# ═══ U12 — PT lain tidak berubah; non-PKP tidak pernah diberi draf ══════════════════════════════════════════════════
async def test_TXT2_U12_pt_lain_dan_non_pkp_tanpa_draf(klien, db, dunia):
    from services import tax_invoice_service as tis
    from services.config_resolver import value_of
    so3 = await pesanan(db, dunia, entity=dunia["pt3"])
    await kirim(db, dunia, so3, QTY, "SJ-1", penutup=True)
    assert await value_of(KUNCI, {"entity_id": dunia["pt3"]}) == "pesanan"
    assert await tis.draft_for_shipment(so3["id"], "SJ-1") is None
    r = await pemicu(klien, dunia["adm"], "surat_jalan", pt=KANDA)   # non-PKP sengaja diberi pemicu surat jalan
    assert r.status_code == 200, r.text
    try:
        sok = await pesanan(db, dunia, entity=KANDA)
        assert sok["ppn_amount"] == 0 and sok["is_pkp"] is False, sok
        await kirim(db, dunia, sok, QTY, "SJ-1", penutup=True)
        assert await tis.draft_for_shipment(sok["id"], "SJ-1") is None
        assert await jumlah("tax_invoices", {"order_id": {"$in": [so3["id"], sok["id"]]}}) == 0
    finally:
        r = await klien.post("/api/config/values/clear", headers=dunia["adm"], json={
            "key": KUNCI, "scope_type": "entity", "scope_id": KANDA, "reason": "uji TX-T2 selesai"})
        assert r.status_code == 200, r.text


# ═══ U13 — masa pajak dilaporkan ════════════════════════════════════════════════════════════════════════════════════
async def test_TXT2_U13_masa_dilaporkan_draf_tetap_draf(klien, db, dunia):
    from services import tax_invoice_service as tis
    from services.book_date import periode_buku
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, "SJ-1", penutup=True)
    d = await tis.draft_for_shipment(so["id"], "SJ-1")
    ini = periode_buku()
    y, m = int(ini[:4]), int(ini[5:])
    lalu = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    r = await klien.post(f"/api/tax/periods/{lalu}/lock", headers=dunia["adm"], json={"entity_id": KSC, "note": "uji"})
    assert r.status_code == 200, r.text
    try:
        r = await terbitkan(klien, dunia["adm"], d["id"], faktur_date=f"{lalu}-15")
        assert r.status_code == 409, r.text
        assert r.json()["detail"].startswith("Masa pajak ") and "sudah ditandai dilaporkan" in r.json()["detail"]
        assert (await db.tax_invoices.find_one({"id": d["id"]}))["status"] == "draf"
    finally:
        r = await klien.post(f"/api/tax/periods/{lalu}/unlock", headers=dunia["adm"],
                             json={"entity_id": KSC, "reason": "selesai uji TX-T2"})
        assert r.status_code == 200, r.text
    BAG["d_u13"] = d


# ═══ U14 — izin & PT ════════════════════════════════════════════════════════════════════════════════════════════════
async def test_TXT2_U14_izin_terbit_draf(klien, db, dunia, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                         peran_sopir):
    d = BAG["d_u13"]
    rid = await peran_tanpa_acuan({"tax_invoice": ["create"]}, label="Terbit Faktur TX-T2")
    mgr0 = await akun(await peran_manajer_kosong())
    sopir = await akun(peran_sopir)
    lain = await akun(rid, entitas=(KANDA,))
    for h, harap in ((await sesi(mgr0), (403,)), (await sesi(sopir), (403,)),
                     (await sesi(lain, entitas=KANDA), (403, 404))):
        r = await terbitkan(klien, h, d["id"])
        assert r.status_code in harap, r.text
        assert (await db.tax_invoices.find_one({"id": d["id"]}))["status"] == "draf"
    r = await terbitkan(klien, await sesi(await akun(rid)), d["id"])
    assert r.status_code == 200 and r.json()["status"] == "normal", r.text


# ═══ U16 — putaran pengaturan `tax.pemicu_faktur` ═══════════════════════════════════════════════════════════════════
async def test_TXT2_U16_putaran_pengaturan_pemicu(klien, db, dunia):
    import config_registry as registry
    from services.config_resolver import value_of
    e = registry.require(KUNCI)
    assert (e["type"], e["default"], tuple(e["scopes"]), e["risk"], e["requires_reason"], tuple(e["permission"]),
            e["group"], e["label"]) == ("enum", "pesanan", ("global", "entity"), "high", True,
                                        ("accounting", "manage"), "pajak-pembukuan", "Faktur pajak dibuat saat")
    assert [o["value"] for o in e["options"]] == ["pesanan", "surat_jalan", "uang_muka"]
    assert set(e["consumers"]) == {"services/tax_invoice_service.py:draft_for_shipment",
                                   "services/tax_invoice_service.py:issue_tax_invoice"}
    r = await pemicu(klien, dunia["adm"], "surat_jalan", pt=KANDA)
    assert r.status_code == 200, r.text
    assert (await value_of(KUNCI, {"entity_id": KANDA}), await value_of(KUNCI, {"entity_id": dunia["pt3"]})) == (
        "surat_jalan", "pesanan")
    r = await klien.post("/api/config/values/clear", headers=dunia["adm"], json={
        "key": KUNCI, "scope_type": "entity", "scope_id": KANDA, "reason": "uji TX-T2"})
    assert r.status_code == 200, r.text
    assert await value_of(KUNCI, {"entity_id": KANDA}) == "pesanan"
    r = await pemicu(klien, dunia["adm"], "harian", pt=KANDA)
    assert r.status_code == 400, r.text
    r = await pemicu(klien, dunia["adm"], "surat_jalan", pt=KANDA, alasan="")
    assert r.status_code == 400, r.text
    assert await value_of(KUNCI, {"entity_id": KANDA}) == "pesanan"


# ═══ Tambahan (a) — buang draf, bangun ulang, saringan, "Semua PT", aksi draf ════════════════════════════════════════
async def test_TXT2_a_buang_draf_alasan_wajib_tidak_dibuat_ulang(klien, db, dunia):
    from services import tax_invoice_service as tis
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, "SJ-9", penutup=True)
    d = await tis.draft_for_shipment(so["id"], "SJ-9")
    r = await klien.post(f"/api/tax-invoices/{d['id']}/discard", json={}, headers=dunia["adm"])
    assert r.status_code == 400 and r.json()["detail"] == "Alasan membuang draf wajib diisi.", r.text
    r = await klien.post(f"/api/tax-invoices/{d['id']}/discard", json={"reason": "pelanggan minta faktur gabungan"},
                         headers=dunia["adm"])
    assert r.status_code == 200, r.text
    b = await db.tax_invoices.find_one({"id": d["id"]}, {"_id": 0})
    assert (b["status"], b["discard_reason"], "active_key" in b) == ("batal", "pelanggan minta faktur gabungan", False)
    assert await tis.draft_for_shipment(so["id"], "SJ-9") is None
    r = await klien.post(f"/api/tax-invoices/{d['id']}/discard", json={"reason": "lagi"}, headers=dunia["adm"])
    assert r.status_code == 409 and r.json()["detail"] == "Dokumen ini bukan draf.", r.text
    rec = await cocok(klien, dunia["adm"], BAG["masa"])
    assert [x["amount"] for x in rec["causes"]["surat_jalan_tanpa_faktur"] if x["order_id"] == so["id"]] == [1_100_000]
    BAG["dibuang"] = so["id"]


async def test_TXT2_a_bangun_ulang_draf_idempoten(klien, db, dunia):
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, "SJ-1", penutup=True)   # surat jalan berjurnal tanpa draf (kait (b) belum ada)
    assert await jumlah("tax_invoices", {"order_id": so["id"]}) == 0
    r = await klien.post("/api/tax-invoices/drafts/rebuild", json={"period": BAG["masa"]}, headers=dunia["adm"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["created"] == 1 and j["reasons"].get("dibuang") == 1 and j["skipped"] >= 4, j
    assert await jumlah("tax_invoices", {"order_id": so["id"], "status": "draf", "trigger": "surat_jalan"}) == 1
    r = await klien.post("/api/tax-invoices/drafts/rebuild", json={"period": BAG["masa"]}, headers=dunia["adm"])
    assert r.status_code == 200 and r.json()["created"] == 0, r.text
    assert await jumlah("tax_invoices", {"order_id": so["id"]}) == 1
    r = await klien.post("/api/tax-invoices/drafts/rebuild", json={"period": "2026-13"}, headers=dunia["adm"])
    assert r.status_code == 400, r.text


async def test_TXT2_a_saringan_status_dan_jenis(klien, db, dunia):
    r = await klien.get("/api/tax-invoices", params={"status": "draf"}, headers=dunia["adm"])
    assert r.status_code == 200 and r.json() and {f["status"] for f in r.json()} == {"draf"}, r.text
    r = await klien.get("/api/tax-invoices", params={"doc_kind": "retur"}, headers=dunia["adm"])
    assert [f["id"] for f in r.json()] == [BAG["retur"]["id"]], r.text
    r = await klien.get("/api/tax-invoices", params={"doc_kind": "faktur", "order_id": BAG["s1"]["id"]},
                        headers=dunia["adm"])
    assert sorted(f["shipment_no"] for f in r.json()) == ["SJ-1", "SJ-2"], r.text


async def test_TXT2_a_pencocokan_semua_pt_ditolak(klien, db, dunia):
    r = await klien.get("/api/tax/output-reconciliation", params={"period": BAG["masa"], "entity_id": "all"},
                        headers=dunia["adm"])
    assert r.status_code == 400 and r.json()["detail"] == "Pilih satu PT.", r.text


async def test_TXT2_a_draf_tidak_lewat_batal_ganti_nsfp(klien, db, dunia):
    so = await pesanan(db, dunia)
    await kirim(db, dunia, so, QTY, "SJ-1", penutup=True)
    from services import tax_invoice_service as tis
    d = await tis.draft_for_shipment(so["id"], "SJ-1")
    for url, isi in ((f"/api/tax-invoices/{d['id']}/cancel", {"reason": "uji"}),
                     (f"/api/tax-invoices/{d['id']}/replace", {"reason": "uji"})):
        r = await klien.post(url, json=isi, headers=dunia["adm"])
        assert r.status_code == 409, (url, r.text)
    r = await klien.patch(f"/api/tax-invoices/{d['id']}/nsfp", json={"nsfp": "0100002699990001"}, headers=dunia["adm"])
    assert r.status_code == 409, r.text
    assert (await db.tax_invoices.find_one({"id": d["id"]}))["status"] == "draf"
    r = await klien.post(f"/api/tax-invoices/{BAG['retur']['id']}/replace", json={"reason": "uji"},
                         headers=dunia["adm"])
    assert r.status_code == 409, r.text   # dokumen retur tidak diganti (bentuk resmi: konsultan pajak)
