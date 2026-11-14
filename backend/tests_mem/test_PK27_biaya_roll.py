"""PK-27 (IV-02, IV-06, IV-07, IV-08) — biaya roll sejalan dengan buku besar pada scrap retur, retur beli, HPP surat
jalan, dan retur jual. Spesifikasi `docs/blueprint/unit/PK-27.md`.

Persiapan bersama (fixture, disisipkan langsung): PT `ent_ksc`; produk `p1` (U1–U9) dan `p2` (U10–U12, supaya rata-rata
tertimbang produknya terkendali); gudang & pemasok uji; roll disisipkan sebagai fixture dan, bila berstatus persediaan,
diberi jurnal saldo awal Dr 1-1300 / Cr 3-2900 senilai rollnya (`difference` rekonsiliasi tidak bergeser oleh fixture).
Akun fixture `5-9910 "Uji selisih retur"` (beban, aktif). "Terpetakan" = `retur.selisih_retur_beli` → 5-9910 lapisan
`ent_ksc` (`gl_mapping_service.set_mapping`, fixture).

Alur lewat API: lepas karantina & batal scrap (U1–U2), buat + setujui retur beli (U3–U6), selesaikan retur jual per
barang & per roll (U10–U12), daftar roll berbiaya 0 (U8, U13). Surat jalan U7/U10–U12: potret biaya dari
`roll_service.ship_order_rolls` (fungsi yang dipakai kirim) lalu surat jalan disisipkan dan HPP diposting dengan
`gl_service.post_order_revenue_and_cogs` — tombol kirim gudang menuntut tag RFID tiap roll (gerbang H7, tidak disentuh).
U9 = surat jalan lama tanpa potret (fixture). U14 = skrip migrasi pada database tiruan tersendiri. U15 = uji jalan layar.

Angka harapan dihitung tangan di komentar tiap uji (masukan → langkah → hasil). `difference` rekonsiliasi dibandingkan
sebelum/sesudah langkah: aplikasi uji (proses awal + seed) membawa selisih awal ent_ksc yang bukan dari unit ini.
"""
import importlib
import re
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jurnal
from services.book_date import tanggal_buku

KSC = "ent_ksc"
AKUN = "5-9910"
KUNCI = "retur.selisih_retur_beli"
PERSEDIAAN, HUTANG, PPN_IN, HPP, PIUTANG, PENDAPATAN, HAPUS = (
    "1-1300", "2-1100", "1-1500", "5-1000", "1-1200", "4-1000", "5-9500")
#: status roll yang dihitung rekonsiliasi 1-1300 (`gl_service.OWNED_ROLL_STATUSES`) — dasar jurnal saldo awal fixture
STOK = {"available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged",
        "in_transit_transfer"}
B = "PK-27 — menunggu serah-terima (b): pemanggil lama belum dialihkan ke jalur baru"
#: id dokumen yang dipakai uji lanjutan (U2 ← U1, U8 ← U7)
BAG: Dict[str, str] = {}


def uid(awalan: str) -> str:
    return f"{awalan}_pk27_{uuid.uuid4().hex[:8]}"


def baris(je) -> Dict[str, Tuple[float, float]]:
    """{akun: (debit, kredit)} — satu jurnal."""
    out: Dict[str, Tuple[float, float]] = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


async def jurnal_aktif(source_type: str, source_id: str) -> List[dict]:
    from db import db
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(20)


async def rekon(klien, h) -> float:
    """`difference` rekonsiliasi persediaan ent_ksc (`GET /api/gl/inventory-reconciliation`)."""
    r = await klien.get("/api/gl/inventory-reconciliation", headers=h)
    assert r.status_code == 200, r.text
    return next(x for x in r.json()["rows"] if x["entity_id"] == KSC)["difference"]


# ── Fixture bersama ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def bahan(db):
    p1, p2, wid, sid = uid("prd"), uid("prd"), uid("wh"), uid("sup")
    await db.products.insert_many([
        {"id": p1, "name": "Kain Uji PK-27", "sku": f"SKU-{p1}", "base_unit": "meter", "harga_pokok": 10_000,
         "price": 20_000, "is_active": True},
        {"id": p2, "name": "Kain Uji PK-27 Retur Jual", "sku": f"SKU-{p2}", "base_unit": "meter", "harga_pokok": 10_000,
         "price": 20_000, "is_active": True}])
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji PK-27", "entity_id": KSC, "is_active": True,
                                    "created_at": now_iso()})
    await db.suppliers.insert_one({"id": sid, "name": "Pemasok Uji PK-27", "is_active": True, "entity_id": KSC})
    if not await db.gl_accounts.find_one({"code": AKUN}):
        await db.gl_accounts.insert_one({
            "id": uid("gla"), "code": AKUN, "name": "Uji selisih retur", "type": "expense", "normal_balance": "debit",
            "parent_code": "5-0000", "is_postable": True, "is_active": True, "entity_id": None, "created_at": now_iso()})
    return {"p1": p1, "p2": p2, "wid": wid, "sid": sid}


async def roll(db, bahan, nama: str, *, panjang: float, biaya: float, dasar=None, status: str = "available",
               pid: str = "", saldo: bool = True, **lain) -> str:
    """Roll fixture + jurnal saldo awal Dr 1-1300 / Cr 3-2900 senilai roll bila statusnya dinilai rekonsiliasi."""
    rid = uid(nama)
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R27-{rid[-8:].upper()}", "product_id": pid or bahan["p1"], "warehouse_id": bahan["wid"],
        "owner_entity_id": KSC, "entity_id": KSC, "unit": "meter", "status": status, "length": panjang,
        "length_initial": panjang, "length_remaining": panjang, "unit_cost": biaya,
        "base_unit_cost": biaya if dasar is None else dasar, "grade": "A", "lot": "", "created_at": now_iso(), **lain})
    if saldo and status in STOK and panjang * biaya > 0:
        await jurnal(KSC, tanggal_buku(), [(PERSEDIAAN, round(panjang * biaya, 2), 0),
                                           ("3-2900", 0, round(panjang * biaya, 2))], "saldo awal roll uji PK-27",
                     uid("sa"))
    return rid


async def petakan() -> None:
    from services import gl_mapping_service as glm
    await glm.set_mapping(KUNCI, KSC, AKUN, "uji PK-27 terpetakan", AKTOR_UJI)


async def lepas_peta() -> None:
    from services import gl_mapping_service as glm
    if (await glm.resolve(KUNCI, KSC))["source"] == "entity":
        await glm.reset_mapping(KUNCI, KSC, "uji PK-27 lepas pemetaan", AKTOR_UJI)


@asynccontextmanager
async def terpetakan():
    await petakan()
    try:
        yield
    finally:
        await lepas_peta()


# ═══ U1–U2 — scrap roll retur dan batal scrap (IV-02) ═══════════════════════════════════════════════════════════════
@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U1_scrap_menolkan_biaya_roll(klien, kepala_admin, db, bahan):
    # Roll RTN 80 m × 12.000 (dasar 11.000) di karantina; saldo awal fixture Dr 1-1300 960.000.
    # Scrap → jurnal hapus-buku 80 × 12.000 = 960.000; nilai roll 960.000 → 0; saldo 1-1300 −960.000 → selisih tetap.
    sr = uid("sr")
    await db.sales_returns.insert_one({"id": sr, "number": f"RJ/PK27/{sr[-6:]}", "entity_id": KSC,
                                       "status": "refund_settled", "order_id": "", "items": [], "attachments": [],
                                       "created_at": now_iso()})
    rid = await roll(db, bahan, "rtn", panjang=80, biaya=12_000, dasar=11_000, status="quarantine",
                     origin_type="return", return_id=sr, qc_status="pending_release")
    BAG.update(u1_ret=sr, u1_roll=rid)
    awal = await rekon(klien, kepala_admin)
    r = await klien.post(f"/api/sales-returns/{sr}/quarantine/release", headers=kepala_admin,
                         json={"decisions": [{"roll_id": rid, "action": "scrap"}], "notes": "kain rusak berat"})
    assert r.status_code == 200, r.text
    jes = await jurnal_aktif("inventory_writeoff", rid)
    assert len(jes) == 1 and baris(jes[0]) == {HAPUS: (960_000, 0), PERSEDIAAN: (0, 960_000)}, jes
    rd = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert (rd["status"], rd["unit_cost"], rd["base_unit_cost"]) == ("damaged", 0, 0), rd
    assert (rd["writeoff_unit_cost"], rd["writeoff_base_unit_cost"]) == (12_000, 11_000), rd
    h = await db.roll_cost_history.find_one({"roll_id": rid, "reason": "scrap_writeoff"}, {"_id": 0})
    assert h and h["old_unit_cost"] == 12_000 and h["new_unit_cost"] == 0 and h["delta_value"] == -960_000, h
    assert await rekon(klien, kepala_admin) == awal


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U2_batal_scrap_memulihkan_biaya(klien, kepala_admin, db, bahan):
    # Lanjutan U1: pembalik Dr 1-1300 / Cr 5-9500 960.000; roll kembali `available` 12.000 (dasar 11.000) → selisih tetap.
    sr, rid = BAG["u1_ret"], BAG["u1_roll"]
    awal = await rekon(klien, kepala_admin)
    r = await klien.post(f"/api/sales-returns/{sr}/reverse-writeoff", headers=kepala_admin,
                         json={"reason": "salah putus scrap"})
    assert r.status_code == 200, r.text
    rev = await jurnal_aktif("inventory_writeoff_reversal", rid)
    assert len(rev) == 1 and baris(rev[0]) == {PERSEDIAAN: (960_000, 0), HAPUS: (0, 960_000)}, rev
    rd = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert (rd["status"], rd["unit_cost"], rd["base_unit_cost"]) == ("available", 12_000, 11_000), rd
    h = await db.roll_cost_history.find_one({"roll_id": rid, "reason": "scrap_writeoff_reversal"}, {"_id": 0})
    assert h and h["old_unit_cost"] == 0 and h["new_unit_cost"] == 12_000, h
    assert await rekon(klien, kepala_admin) == awal


# ═══ U3–U6 — retur beli dinilai pada nilai buku roll (IV-06) ════════════════════════════════════════════════════════
async def _po_ber_ppn_tertagih(db, bahan) -> dict:
    """PO ber-PPN 11 % (net 1.000.000, PPN 110.000) + faktur pemasok `posted` → retur mendebit hutang 2-1100."""
    po = uid("po")
    doc = {"id": po, "po_number": f"PO/PK27/{po[-6:]}", "entity_id": KSC, "status": "completed",
           "supplier_id": bahan["sid"], "supplier_name": "Pemasok Uji PK-27", "warehouse_id": bahan["wid"],
           "tax_mode": "ppn", "items": [{"line_id": "L1", "product_id": bahan["p1"], "unit": "meter", "quantity": 100,
                                         "price": 10_000, "line_total": 1_000_000, "received_qty": 100}],
           "total_amount": 1_000_000, "net_subtotal": 1_000_000, "dpp": 1_000_000, "ppn_amount": 110_000,
           "grand_total": 1_110_000, "created_at": now_iso()}
    await db.purchase_orders.insert_one(dict(doc))
    await db.vendor_bills.insert_one({"id": uid("vb"), "po_id": po, "entity_id": KSC, "status": "posted",
                                      "bill_number": f"VB/PK27/{po[-6:]}", "created_at": now_iso()})
    return doc


async def retur_beli(klien, h, db, bahan, *, harga: float) -> Tuple[dict, str]:
    """Roll `r` 50 m, dasar 10.000, biaya 10.500 (nilai buku 525.000) → retur beli 50 m @ `harga`, diajukan."""
    po = await _po_ber_ppn_tertagih(db, bahan)
    rid = await roll(db, bahan, "rb", panjang=50, biaya=10_500, dasar=10_000)
    r = await klien.post("/api/purchase-returns", headers=h, json={
        "supplier_id": bahan["sid"], "po_id": po["id"], "warehouse_id": bahan["wid"], "entity_id": KSC,
        "reason": "cacat", "submit_now": True,
        "items": [{"product_id": bahan["p1"], "quantity": 50, "unit": "meter", "price": harga, "roll_ids": [rid],
                   "reason": "cacat", "condition": "damaged"}]})
    assert r.status_code == 200, r.text
    ret = r.json()
    assert (ret["total_amount"], ret["ppn_amount"]) == (round(50 * harga, 2), round(50 * harga * 0.11, 2)), ret
    return ret, rid


async def setujui_retur_beli(klien, h, ret_id: str):
    return await klien.post(f"/api/purchase-returns/{ret_id}/approve", headers=h, json={})


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U3_retur_beli_nilai_buku_dan_selisih_terpetakan(klien, kepala_admin, db, bahan):
    # Nota 50 × 10.000 = 500.000 + PPN 11 % 55.000 = 555.000. Nilai buku 50 × 10.500 = 525.000; selisih = 525.000 −
    # 500.000 = 25.000 (Dr). Jurnal: Dr 2-1100 555.000 + Dr 5-9910 25.000 = 580.000 = Cr 1-1300 525.000 + Cr 1-1500 55.000.
    ret, rid = await retur_beli(klien, kepala_admin, db, bahan, harga=10_000)
    awal = await rekon(klien, kepala_admin)
    async with terpetakan():
        r = await setujui_retur_beli(klien, kepala_admin, ret["id"])
    assert r.status_code == 200, r.text
    jes = await jurnal_aktif("purchase_return", ret["id"])
    assert len(jes) == 1 and baris(jes[0]) == {
        HUTANG: (555_000, 0), AKUN: (25_000, 0), PERSEDIAAN: (0, 525_000), PPN_IN: (0, 55_000)}, jes
    d = await db.purchase_returns.find_one({"id": ret["id"]}, {"_id": 0})
    assert (d["book_value"], d["book_value_diff"], d["book_value_posted"]) == (525_000, 25_000, True), d
    assert d["book_value_rolls"] == [{"roll_id": rid, "qty": 50, "unit_cost": 10_500, "value": 525_000}], d
    assert await rekon(klien, kepala_admin) == awal


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U4_tanpa_pemetaan_jurnal_lama_selisih_tercatat(klien, kepala_admin, db, bahan):
    # Kunci belum terpetakan → jurnal lama: Dr 2-1100 555.000 / Cr 1-1300 500.000 / Cr 1-1500 55.000; selisih 25.000
    # hanya tercatat di dokumen (`book_value_posted=false`).
    ret, _ = await retur_beli(klien, kepala_admin, db, bahan, harga=10_000)
    r = await setujui_retur_beli(klien, kepala_admin, ret["id"])
    assert r.status_code == 200, r.text
    jes = await jurnal_aktif("purchase_return", ret["id"])
    assert len(jes) == 1 and baris(jes[0]) == {HUTANG: (555_000, 0), PERSEDIAAN: (0, 500_000), PPN_IN: (0, 55_000)}
    d = await db.purchase_returns.find_one({"id": ret["id"]}, {"_id": 0})
    assert (d["book_value"], d["book_value_diff"], d["book_value_posted"]) == (525_000, 25_000, False), d


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U5_harga_nota_di_atas_nilai_buku(klien, kepala_admin, db, bahan):
    # Nota 50 × 11.000 = 550.000 + PPN 60.500 = 610.500; selisih 525.000 − 550.000 = −25.000 (Cr).
    # Dr 2-1100 610.500 = Cr 1-1300 525.000 + Cr 1-1500 60.500 + Cr 5-9910 25.000.
    ret, _ = await retur_beli(klien, kepala_admin, db, bahan, harga=11_000)
    async with terpetakan():
        r = await setujui_retur_beli(klien, kepala_admin, ret["id"])
    assert r.status_code == 200, r.text
    jes = await jurnal_aktif("purchase_return", ret["id"])
    assert len(jes) == 1 and baris(jes[0]) == {
        HUTANG: (610_500, 0), PERSEDIAAN: (0, 525_000), PPN_IN: (0, 60_500), AKUN: (0, 25_000)}, jes
    d = await db.purchase_returns.find_one({"id": ret["id"]}, {"_id": 0})
    assert (d["book_value_diff"], d["book_value_posted"]) == (-25_000, True), d


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U6_jurnal_gagal_lalu_setujui_ulang(klien, kepala_admin, db, bahan, paksa_jurnal_gagal):
    # Pertama: stok & nota debit tercatat, jurnal gagal → `gl_status=failed`, nilai buku 525.000 sudah tersimpan.
    # Kedua: jurnal U3 dari nilai tersimpan; roll tidak dikonsumsi dua kali (satu mutasi keluar).
    ret, rid = await retur_beli(klien, kepala_admin, db, bahan, harga=10_000)
    async with terpetakan():
        async with paksa_jurnal_gagal("sisip", source_type="purchase_return") as gagal:
            r1 = await setujui_retur_beli(klien, kepala_admin, ret["id"])
        assert gagal and r1.status_code == 400 and "jurnal gagal" in r1.text, r1.text
        d = await db.purchase_returns.find_one({"id": ret["id"]}, {"_id": 0})
        assert (d["gl_status"], d["stock_adjusted"], d["book_value"]) == ("failed", True, 525_000), d
        r2 = await setujui_retur_beli(klien, kepala_admin, ret["id"])
    assert r2.status_code == 200, r2.text
    jes = await jurnal_aktif("purchase_return", ret["id"])
    assert len(jes) == 1 and baris(jes[0]) == {
        HUTANG: (555_000, 0), AKUN: (25_000, 0), PERSEDIAAN: (0, 525_000), PPN_IN: (0, 55_000)}, jes
    assert await db.inventory_movements.count_documents({"ref_id": ret["id"], "movement_type": "return_out"}) == 1
    assert (await db.inventory_rolls.find_one({"id": rid}))["status"] == "returned_supplier"
    d = await db.purchase_returns.find_one({"id": ret["id"]}, {"_id": 0})
    assert (d["gl_status"], d["book_value_posted"]) == ("posted", True), d


# ═══ U7–U9 — HPP surat jalan dari potret biaya roll (IV-07) ═════════════════════════════════════════════════════════
async def kirim(db, bahan, pid: str, rolls: List[Tuple[str, float, float]], *, harga: float = 20_000) -> dict:
    """Pesanan kredit tanpa PPN berisi `rolls` [(nama, panjang, biaya)] yang sudah diambil (`picked`), lalu dikirim
    dalam SATU surat jalan: potret biaya dari `roll_service.ship_order_rolls`, HPP lewat
    `gl_service.post_order_revenue_and_cogs` (sama dengan sesudah tombol kirim)."""
    from services import gl_service
    from services.roll_service import ship_order_rolls
    so = uid("so")
    ids = {n: await roll(db, bahan, n, panjang=p, biaya=c, pid=pid, status="picked",
                         reserved_ref={"type": "sales_order", "id": so}) for n, p, c in rolls}
    qty = sum(p for _, p, _ in rolls)
    num = f"SO/PK27/{so[-6:]}"
    await db.sales_orders.insert_one({
        "id": so, "number": num, "entity_id": KSC, "status": "shipped", "customer_id": "cus_pk27",
        "customer_name": "Pelanggan Uji PK-27", "payment_method": "kredit",
        "items": [{"product_id": pid, "product_name": "Kain Uji PK-27", "quantity": qty, "base_quantity": qty,
                   "unit": "meter", "price": harga, "line_total": qty * harga}],
        "allocations": [{"warehouse_id": bahan["wid"], "product_id": pid, "qty": qty}],
        "subtotal": qty * harga, "grand_total": qty * harga, "ppn_amount": 0, "payments": [], "created_at": now_iso()})
    res = await ship_order_rolls(so, pid, bahan["wid"], qty, roll_ids=list(ids.values()))
    shp = {"id": uid("shp"), "shipment_no": f"SJ/PK27/{so[-6:]}", "entity_id": KSC, "order_id": so,
           "order_number": num, "product_id": pid, "warehouse_id": bahan["wid"], "qty": qty, "unit": "meter",
           "rolls": res["rolls"], "status": "dispatched", "created_at": now_iso(), "gl_status": "pending"}
    await db.shipments.insert_one(dict(shp))
    await gl_service.post_order_revenue_and_cogs(so)
    return {"so": so, "number": num, "rolls": ids, "shipment": shp}


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U7_hpp_surat_jalan_memuat_roll_berbiaya_nol(db, bahan):
    # r1 100 m × 10.000 + r2 100 m × 0 = 1.000.000 (kode lama: rata-rata roll berbiaya > 0 = 10.000 × 200 = 2.000.000).
    from services import gl_service
    BAG["u8_shipped0"] = (await gl_service.zero_cost_rolls([KSC]))["shipped"]["total"]   # seed: dasar U8
    k = await kirim(db, bahan, bahan["p1"], [("r1", 100, 10_000), ("r2", 100, 0)])
    BAG.update(u7_roll=k["rolls"]["r2"], u7_sj=k["shipment"]["shipment_no"])
    assert [round(float(x["unit_cost"])) for x in k["shipment"]["rolls"]] == [10_000, 0]
    jes = await jurnal_aktif("shipment_cogs", k["shipment"]["id"])
    assert len(jes) == 1 and baris(jes[0]) == {HPP: (1_000_000, 0), PERSEDIAAN: (0, 1_000_000)}, jes


async def test_PK27_U8_daftar_roll_berbiaya_nol(klien, kepala_admin, db, bahan):
    # Lanjutan U7: `r2` (biaya 0) terkirim → `shipped` +1; satu roll `available` biaya 0 → `in_stock` +1. Roll scrap
    # yang sudah dihapus-buku (biaya 0, jurnal belum dibalik — keadaan U1 sesudah unit) tidak muncul. Data acuan uji
    # (seed) sudah memuat roll berbiaya 0 di ent_ksc → angka dibandingkan dengan sebelum fixture (lihat laporan).
    awal = (await klien.get("/api/gl/zero-cost-rolls", headers=kepala_admin)).json()
    nol = await roll(db, bahan, "nol", panjang=30, biaya=0)
    scrap = await roll(db, bahan, "scrap", panjang=40, biaya=0, status="damaged", saldo=False,
                       writeoff_je_id="je_pk27_scrap", writeoff_unit_cost=9_000, writeoff_base_unit_cost=9_000)
    r = await klien.get("/api/gl/zero-cost-rolls", headers=kepala_admin, params={"page_size": 200})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["page"], j["page_size"]) == (1, 200)
    stok = {x["roll_id"]: x for x in j["in_stock"]["items"]}
    assert j["in_stock"]["total"] == awal["in_stock"]["total"] + 1 == len(stok) and nol in stok, j["in_stock"]
    assert scrap not in stok and BAG.get("u1_roll") not in stok
    assert all(x["entity_id"] == KSC for x in j["in_stock"]["items"])
    assert stok[nol] == {"roll_id": nol, "roll_no": f"R27-{nol[-8:].upper()}", "product_name": "Kain Uji PK-27",
                         "entity_id": KSC, "length_remaining": 30, "status": "available"}
    rno = f"R27-{BAG['u7_roll'][-8:].upper()}"
    assert j["shipped"]["total"] == BAG["u8_shipped0"] + 1 == awal["shipped"]["total"], j["shipped"]
    sj = next(x for x in j["shipped"]["items"] if x["shipment_no"] == BAG["u7_sj"])
    assert (sj["roll_no"], sj["length"], sj["entity_id"]) == (rno, 100, KSC), sj
    assert sj["order_number"].startswith("SO/PK27/") and sj["shipped_at"]
    # halaman: page_size 200 maksimum, di atasnya 422; halaman jauh kosong tetapi total tetap dari kueri
    assert (await klien.get("/api/gl/zero-cost-rolls", headers=kepala_admin, params={"page_size": 201})).status_code == 422
    j2 = (await klien.get("/api/gl/zero-cost-rolls", headers=kepala_admin, params={"page": 1000})).json()
    assert j2["in_stock"]["items"] == [] and j2["in_stock"]["total"] == j["in_stock"]["total"]
    assert j2["shipped"]["items"] == [] and j2["shipped"]["total"] == j["shipped"]["total"]
    # PT lain (Kanda) tidak memuat roll KSC; "Semua PT" memuat PT dalam cakupan
    h_kanda = {**kepala_admin, "X-Entity-Id": "ent_kanda"}
    jk = (await klien.get("/api/gl/zero-cost-rolls", headers=h_kanda)).json()
    assert nol not in {x["roll_id"] for x in jk["in_stock"]["items"]}
    ja = (await klien.get("/api/gl/zero-cost-rolls", headers={**kepala_admin, "X-Entity-Id": "all"})).json()
    assert nol in {x["roll_id"] for x in ja["in_stock"]["items"]} and ja["shipped"]["total"] >= 1


async def test_PK27_U9_surat_jalan_lama_tanpa_potret_jalur_rata_rata(db, bahan):
    # Surat jalan lama (tanpa `rolls`): HPP = qty × rata-rata roll pesanan = 200 × (10.000 + 14.000) / 2 = 2.400.000.
    from services import gl_service
    so = uid("so")
    for n, c in (("l1", 10_000), ("l2", 14_000)):
        await roll(db, bahan, n, panjang=100, biaya=c, status="delivered", saldo=False,
                   reserved_ref={"type": "sales_order", "id": so})
    await db.sales_orders.insert_one({
        "id": so, "number": f"SO/PK27/{so[-6:]}", "entity_id": KSC, "status": "shipped", "customer_id": "cus_pk27",
        "items": [{"product_id": bahan["p1"], "quantity": 200, "base_quantity": 200, "unit": "meter", "price": 20_000,
                   "line_total": 4_000_000}], "grand_total": 4_000_000, "ppn_amount": 0, "payments": [],
        "created_at": now_iso()})
    shp = {"id": uid("shp"), "shipment_no": f"SJ/PK27/{so[-6:]}", "entity_id": KSC, "order_id": so,
           "product_id": bahan["p1"], "qty": 200, "unit": "meter", "status": "dispatched", "created_at": now_iso()}
    await db.shipments.insert_one(dict(shp))
    await gl_service.post_order_revenue_and_cogs(so)
    jes = await jurnal_aktif("shipment_cogs", shp["id"])
    assert len(jes) == 1 and baris(jes[0]) == {HPP: (2_400_000, 0), PERSEDIAAN: (0, 2_400_000)}, jes


# ═══ U10–U12 — barang retur pelanggan masuk lagi sebesar HPP saat dijual (IV-08) ════════════════════════════════════
async def _terkirim(db, bahan) -> dict:
    """Pesanan p2: r1 100 m × 10.000 + r2 100 m × 14.000, harga 20.000 tanpa PPN, terkirim (HPP 2.400.000) dan diterima
    pelanggan (fixture POD: `delivered`). Satu roll lain p2 `available` 100 m × 16.000 membuat rata-rata produk 16.000."""
    k = await kirim(db, bahan, bahan["p2"], [("r1", 100, 10_000), ("r2", 100, 14_000)])
    jes = await jurnal_aktif("shipment_cogs", k["shipment"]["id"])
    assert len(jes) == 1 and baris(jes[0]) == {HPP: (2_400_000, 0), PERSEDIAAN: (0, 2_400_000)}, jes
    await db.inventory_rolls.update_many({"id": {"$in": list(k["rolls"].values())}},
                                         {"$set": {"status": "delivered", "delivered_at": now_iso()}})
    if not await db.inventory_rolls.find_one({"product_id": bahan["p2"], "status": "available"}):
        await roll(db, bahan, "lain", panjang=100, biaya=16_000, pid=bahan["p2"])
    from services import costing_service
    costing_service._WAC_CACHE.clear()
    return k


async def _retur_jual(db, bahan, k, *, qty: float, roll_ids=(), per_roll: bool = False) -> str:
    sr = uid("sr")
    item = {"product_id": bahan["p2"], "product_name": "Kain Uji PK-27 Retur Jual", "quantity_returned": qty,
            "unit": "meter", "condition": "ok", "reason": "salah warna", "inspection": {"grade": "A"}}
    doc = {"id": sr, "number": f"RJ/PK27/{sr[-6:]}", "entity_id": KSC, "status": "inspected", "order_id": k["so"],
           "order_number": k["number"], "customer_id": "cus_pk27", "customer_name": "Pelanggan Uji PK-27",
           "attachments": [{"id": "att_pk27", "name": "foto.jpg"}], "created_at": now_iso()}
    if roll_ids:
        item.update(roll_ids=list(roll_ids), roll_qtys={r: qty for r in roll_ids})
    if per_roll:
        item["inspection"] = {"grade": "A", "roll_results": {
            r: {"grade": "A", "actual_qty": qty, "condition": "ok"} for r in roll_ids}}
        doc["roll_locations"] = {r: {"stage": "received", "warehouse_id": bahan["wid"]} for r in roll_ids}
    doc["items"] = [item]
    await db.sales_returns.insert_one(doc)
    return sr


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U10_retur_roll_dinilai_potret_surat_jalan(klien, kepala_admin, db, bahan):
    # Retur r2 100 m kondisi baik, selesai sebagai pengurang piutang: nota kredit 100 × 20.000 = 2.000.000
    # (Dr 4-1000 / Cr 1-1200). HPP balik = 100 × 14.000 (potret r2) = 1.400.000, bukan 100 × 16.000 (rata-rata kini).
    from services import costing_service
    k = await _terkirim(db, bahan)
    assert (await costing_service.wac_for_product(bahan["p2"], entity_id=KSC))["wac"] == 16_000   # rata-rata kini
    r2 = k["rolls"]["r2"]
    sr = await _retur_jual(db, bahan, k, qty=100, roll_ids=[r2])
    awal = await rekon(klien, kepala_admin)
    r = await klien.post(f"/api/sales-returns/{sr}/settle", headers=kepala_admin, json={"outcome": "refund"})
    assert r.status_code == 200, r.text
    cn = await db.credit_notes.find_one({"return_id": sr}, {"_id": 0})
    assert (cn["gross_amount"], cn["cogs_amount"]) == (2_000_000, 1_400_000), cn
    assert cn.get("cogs_source") == "surat_jalan", cn
    jes = await jurnal_aktif("sales_return", sr)
    assert len(jes) == 1 and baris(jes[0]) == {PENDAPATAN: (2_000_000, 0), PIUTANG: (0, 2_000_000),
                                               PERSEDIAAN: (1_400_000, 0), HPP: (0, 1_400_000)}, jes
    rd = await db.inventory_rolls.find_one({"id": r2}, {"_id": 0})
    assert (rd["status"], rd["unit_cost"], rd["base_unit_cost"]) == ("quarantine", 14_000, 14_000), rd
    assert await rekon(klien, kepala_admin) == awal


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U11_retur_tanpa_roll_rata_rata_surat_jalan(klien, kepala_admin, db, bahan):
    # Baris tanpa `roll_ids`, 50 m: biaya = Σ potret 2.400.000 ÷ 200 m = 12.000 → HPP balik 50 × 12.000 = 600.000.
    k = await _terkirim(db, bahan)
    sr = await _retur_jual(db, bahan, k, qty=50)
    r = await klien.post(f"/api/sales-returns/{sr}/settle", headers=kepala_admin, json={"outcome": "refund"})
    assert r.status_code == 200, r.text
    cn = await db.credit_notes.find_one({"return_id": sr}, {"_id": 0})
    assert (cn["gross_amount"], cn["cogs_amount"]) == (1_000_000, 600_000), cn
    assert cn.get("cogs_source") == "rata_surat_jalan", cn
    jes = await jurnal_aktif("sales_return", sr)
    assert len(jes) == 1 and baris(jes[0]) == {PENDAPATAN: (1_000_000, 0), PIUTANG: (0, 1_000_000),
                                               PERSEDIAAN: (600_000, 0), HPP: (0, 600_000)}, jes
    baru = await db.inventory_rolls.find_one({"return_id": sr, "origin_type": "return"}, {"_id": 0})
    assert (baru["unit_cost"], baru["length_remaining"]) == (12_000, 50), baru


@pytest.mark.xfail(strict=True, reason=B)
async def test_PK27_U12_penyelesaian_per_roll(db, bahan):
    # Penyelesaian per roll: r2 kembali ke stok → HPP balik 100 × 14.000 = 1.400.000 (bukan 1.600.000).
    # Lapis B = rencana penyelesaian (`plan_event`): angka rencana disalin apa adanya ke nota kredit (`cogs_amount`,
    # `cogs_source`, baris `cogs`) oleh `_apply`. Eksekusi penuh lewat API memakai pembaruan larik bertapis
    # (`array_filters`) yang tidak didukung database tiruan → lapis A `tests/test_bp_PK27_retur_per_roll_mongo.py`.
    from services import return_roll_settlement_service as rrs
    k = await _terkirim(db, bahan)
    r2 = k["rolls"]["r2"]
    sr = await _retur_jual(db, bahan, k, qty=100, roll_ids=[r2], per_roll=True)
    ret = await db.sales_returns.find_one({"id": sr}, {"_id": 0})
    plan = await rrs.plan_event(ret, [{"roll_id": r2, "outcome": "refund"}])
    assert (plan["cogs_amount"], plan["gross_amount"]) == (1_400_000, 2_000_000), plan
    assert [ln["cogs"] for ln in plan["lines"]] == [1_400_000], plan["lines"]
    hpp = {ln["account_code"]: (ln["debit"], ln["credit"]) for ln in plan["journal"] if ln["cost"]}
    assert hpp == {PERSEDIAAN: (1_400_000, 0), HPP: (0, 1_400_000)}, plan["journal"]
    assert plan.get("cogs_source") == "surat_jalan", plan


# ═══ U13 — izin daftar roll berbiaya 0 ═══════════════════════════════════════════════════════════════════════════════
async def test_PK27_U13_daftar_biaya_nol_butuh_accounting_view(klien, akun, sesi, peran_tanpa_acuan):
    tanpa = await peran_tanpa_acuan({"inventory": ["view"]})
    dengan = await peran_tanpa_acuan({"accounting": ["view"]})
    h0 = await sesi(await akun(tanpa))
    h1 = await sesi(await akun(dengan))
    assert (await klien.get("/api/gl/zero-cost-rolls", headers=h0)).status_code == 403
    assert (await klien.get("/api/gl/zero-cost-rolls", headers=h1)).status_code == 200


# ═══ U14 — skrip migrasi roll scrap lama (database tiruan tersendiri; data nyata = H3) ══════════════════════════════
def _skrip():
    import importlib.util
    jalur = Path(__file__).resolve().parents[2] / "scripts" / "migrasi_pk27_biaya_roll_scrap.py"
    spec = importlib.util.spec_from_file_location("migrasi_pk27", jalur)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_PK27_U14_skrip_migrasi_roll_scrap_lama(capsys):
    # FIXTURE: keadaan U1 SEBELUM unit — roll `damaged` 80 m × 12.000 ber-jurnal hapus-buku, biaya utuh (960.000).
    from mongomock_motor import AsyncMongoMockClient
    mdb = AsyncMongoMockClient()["uji_pk27_migrasi"]
    await mdb.inventory_rolls.insert_many([
        {"id": "roll_pk27_lama", "roll_no": "RTN-PK27-LAMA", "owner_entity_id": KSC, "status": "damaged",
         "unit": "meter", "length_remaining": 80, "unit_cost": 12_000, "base_unit_cost": 11_000,
         "writeoff_je_id": "je_pk27_lama", "writeoff_je_number": "JE-PK27-LAMA", "return_id": "sr_pk27_lama"},
        # dibalik / tanpa jurnal / sudah nol → bukan sasaran
        {"id": "roll_pk27_balik", "roll_no": "RTN-PK27-BALIK", "owner_entity_id": KSC, "status": "damaged",
         "length_remaining": 10, "unit_cost": 5_000, "writeoff_je_id": "je_b", "writeoff_reversed": True},
        {"id": "roll_pk27_rusak", "roll_no": "RTN-PK27-RUSAK", "owner_entity_id": KSC, "status": "damaged",
         "length_remaining": 10, "unit_cost": 5_000},
        {"id": "roll_pk27_nol", "roll_no": "RTN-PK27-NOL", "owner_entity_id": KSC, "status": "damaged",
         "length_remaining": 10, "unit_cost": 0, "base_unit_cost": 0, "writeoff_je_id": "je_n"}])
    skrip = _skrip()
    assert await skrip.jalankan([], db=mdb) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():   # cetakan untuk laporan (pytest -s)
        print("\n=== CETAKAN SKRIP MIGRASI PK-27 (baca-saja) ===\n" + keluar)
    assert re.search(r"Roll RTN-PK27-LAMA · PT ent_ksc · 80 meter × 12\.000 · nilai 960\.000", keluar), keluar
    assert "Ringkasan: 1 roll scrap masih bernilai · total 960.000" in keluar, keluar
    assert (await mdb.inventory_rolls.find_one({"id": "roll_pk27_lama"}))["unit_cost"] == 12_000   # baca-saja
    assert await skrip.jalankan(["--apply"], db=mdb) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():
        print("\n=== --apply ===\n" + keluar.splitlines()[-1])
    rd = await mdb.inventory_rolls.find_one({"id": "roll_pk27_lama"}, {"_id": 0})
    assert (rd["unit_cost"], rd["base_unit_cost"], rd["writeoff_unit_cost"], rd["writeoff_base_unit_cost"]) == (
        0, 0, 12_000, 11_000), rd
    hist = await mdb.roll_cost_history.find({}, {"_id": 0}).to_list(10)
    assert [(h["roll_id"], h["reason"], h["delta_value"]) for h in hist] == [("roll_pk27_lama", "scrap_writeoff", -960_000)]
    assert (await mdb.inventory_rolls.find_one({"id": "roll_pk27_balik"}))["unit_cost"] == 5_000
    assert await skrip.jalankan(["--apply"], db=mdb) == 0
    keluar = capsys.readouterr().out
    with capsys.disabled():
        print("\n=== --apply (jalan ketiga) ===\n" + keluar)
    assert "Ringkasan: 0 roll scrap masih bernilai · total 0" in keluar and "Tanpa perubahan" in keluar, keluar


# ═══ Serah-terima (a) — fungsi baru dipanggil langsung (pemanggil lama belum dialihkan) ═════════════════════════════
async def test_PK27_a_post_purchase_return_book_value(db, bahan):
    """`post_purchase_return(..., book_value=…)`: empat baris tabel spesifikasi Server butir 2. Tanpa `book_value` →
    jurnal lama. Dokumen retur fixture ber-PO yang sudah ditagih (debit hutang 2-1100)."""
    from services import gl_service as gl
    po = await _po_ber_ppn_tertagih(db, bahan)

    async def pasang(bv, *, amount=555_000.0, ppn=55_000.0):
        rid = uid("pret")
        je = await gl.post_purchase_return({"id": rid, "po_id": po["id"], "entity_id": KSC}, amount=amount, ppn=ppn,
                                           label=rid[-6:], book_value=bv)
        return baris(je)

    lama = {HUTANG: (555_000, 0), PERSEDIAAN: (0, 500_000), PPN_IN: (0, 55_000)}
    assert await pasang(None) == lama                       # retur lama tanpa nilai buku
    assert await pasang(525_000) == lama                    # kunci belum terpetakan → perilaku lama
    async with terpetakan():
        assert await pasang(500_000.004) == lama            # |selisih| ≤ 0,005 → tanpa baris selisih
        assert await pasang(525_000) == {HUTANG: (555_000, 0), AKUN: (25_000, 0), PERSEDIAAN: (0, 525_000),
                                         PPN_IN: (0, 55_000)}
        assert await pasang(525_000, amount=610_500, ppn=60_500) == {
            HUTANG: (610_500, 0), PERSEDIAAN: (0, 525_000), PPN_IN: (0, 60_500), AKUN: (0, 25_000)}
        # roll berbiaya 0 (nilai buku 0): seluruh nilai nota masuk akun selisih, persediaan tidak bergerak
        assert await pasang(0.0) == {HUTANG: (555_000, 0), PPN_IN: (0, 55_000), AKUN: (0, 500_000)}
    assert gl.purchase_return_book_diff(amount=555_000, ppn=55_000, book_value=525_000) == 25_000
    assert gl.purchase_return_book_diff(amount=610_500, ppn=60_500, book_value=525_000) == -25_000
    assert gl.purchase_return_book_diff(amount=555_000, ppn=55_000) is None


async def test_PK27_a_kunci_pemetaan_terdaftar_tanpa_bawaan(klien, kepala_admin):
    from services import gl_mapping_registry as reg
    e = reg.require(KUNCI)
    assert (e["default"], e["label"], e["remap"], e["required"], e["allowed_types"]) == (
        "", "Selisih nilai retur beli", False, True, ["expense", "income"])
    rows = {x["key"]: x for x in (await klien.get("/api/gl/account-mappings", headers=kepala_admin)).json()["rows"]}
    assert (rows[KUNCI]["account_code"], rows[KUNCI]["status"], rows[KUNCI]["source"]) == ("", "unset", "default")
    cands = (await klien.get(f"/api/gl/account-mappings/{KUNCI}/candidates", headers=kepala_admin)).json()
    kode = {c["code"] for c in (cands.get("items", cands) if isinstance(cands, dict) else cands)}
    assert AKUN in kode and "1-1300" not in kode


async def test_PK27_a_return_unit_cost_tiga_sumber(db, bahan):
    """`return_unit_cost` langsung (fixture surat jalan): potret roll · rata-rata surat jalan · rata-rata produk."""
    from services import costing_service
    from services.return_service import cogs_source_of, return_unit_cost
    so = uid("so")
    r1 = await roll(db, bahan, "s1", panjang=0, biaya=10_500, dasar=10_000, pid=bahan["p2"], status="delivered",
                    saldo=False)
    r2 = await roll(db, bahan, "s2", panjang=0, biaya=14_000, dasar=15_000, pid=bahan["p2"], status="delivered",
                    saldo=False)
    await db.shipments.insert_many([
        {"id": uid("shp"), "order_id": so, "product_id": bahan["p2"], "status": "dispatched", "created_at": "2026-11-01",
         "rolls": [{"roll_id": r1, "length": 100, "unit_cost": 10_000, "extended_cost": 1_000_000},
                   {"roll_id": r2, "length": 50, "unit_cost": 14_000}]},
        {"id": uid("shp"), "order_id": so, "product_id": bahan["p2"], "status": "cancelled", "created_at": "2026-11-02",
         "rolls": [{"roll_id": r1, "length": 100, "unit_cost": 99_000, "extended_cost": 9_900_000}]}])
    ret = {"id": uid("sr"), "order_id": so, "entity_id": KSC}
    it = {"product_id": bahan["p2"], "condition": "ok"}
    # (1) satu roll: potret r1 10.000; dasar dokumen roll 10.000 (≤ biaya)
    assert await return_unit_cost(ret, {**it, "roll_ids": [r1]}) == (10_000, 10_000, "surat_jalan")
    # (1) dua roll, qty dikembalikan 50 + 50: (50 × 10.000 + 50 × 14.000) / 100 = 12.000; dasar r2 15.000 > 14.000
    #     → dasar = 14.000 → (50 × 10.000 + 50 × 14.000) / 100 = 12.000
    assert await return_unit_cost(ret, {**it, "roll_ids": [r1, r2], "roll_qtys": {r1: 50, r2: 50}}) == (
        12_000, 12_000, "surat_jalan")
    # (1) per roll (`roll_id`) mengabaikan roll lain di baris
    assert (await return_unit_cost(ret, {**it, "roll_ids": [r1, r2]}, roll_id=r2))[0] == 14_000
    # (2) tanpa roll_ids: Σ extended (1.000.000 + 50 × 14.000) ÷ 150 m = 11.333,3333
    c, d, s = await return_unit_cost(ret, it)
    assert (round(c, 4), s) == (11_333.3333, "rata_surat_jalan") and d <= c
    # (3) roll tidak ada di potret pesanan → rata-rata produk saat ini (perilaku lama)
    costing_service._WAC_CACHE.clear()
    w = await costing_service.wac_for_product(bahan["p2"], entity_id=KSC)
    c, d, s = await return_unit_cost(ret, {**it, "roll_ids": ["roll_tidak_dikirim"]})
    assert (c, s) == (w["wac"], "wac") and d <= c
    # damaged → 0, sumber tetap dilaporkan
    assert await return_unit_cost(ret, {**it, "roll_ids": [r1], "condition": "damaged"}) == (0.0, 0.0, "surat_jalan")
    assert cogs_source_of(["surat_jalan", "rata_surat_jalan"]) == "rata_surat_jalan"
    assert cogs_source_of(["surat_jalan", "wac", ""]) == "wac" and cogs_source_of([]) == ""
