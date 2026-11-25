"""BTP-4 — tutup sisa pesanan yang dikirim sebagian (nilai = yang dibukukan per Surat Jalan, kelebihan → titipan).

Rancangan `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` §5.2 (wajib-setuju tutup sisa =
kelebihan uang ke titipan ATAU barang sisa sudah disiapkan; nominal = nilai sisa) dan §5.6 "Tutup sisa" langkah 1–8
(keputusan pemilik A1-1…A1-5). Pesanan `partially_shipped` yang sisanya tidak diinginkan pelanggan ditutup: jumlah
baris turun ke yang terkirim, nilai pesanan DIPAKSA sama dengan pendapatan + PPN jurnal Surat Jalan (tanpa jurnal baru),
roll sisa dilepas, tugas gudang sisa dibatalkan, backorder ditutup, kelebihan uang muka pindah ke titipan pelanggan.

Pesanan dibangun lewat alur nyata: harga dari `config_service.compute_order_pricing`, "kirim" = `shipment_service.
dispatch_task` (jurnal Surat Jalan nyata lewat `post_order_revenue_and_cogs`); hanya pemindahan roll fisik
(`ship_order_rolls`, gerbang roll/RFID) diganti tiruan yang memindah roll ke `in_transit_sales`.

Hitung tangan (PT `ent_ksc` PKP: PPN 12 % × DPP nilai lain 11/12 = efektif 11 %): 100 m × 100.000 = 10.000.000; PPN
1.100.000; total 11.100.000. Kirim 40 m (porsi 0,4): jurnal Dr 1-1200 4.440.000 / Cr 4-1000 4.000.000 / Cr 2-1200
440.000. Sesudah tutup sisa: nilai pesanan 4.440.000; nilai sisa 6.660.000.

    cd backend && python -m pytest tests_mem/test_BTP4_tutup_sisa.py -n 0 -q
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
HARGA = 100_000.0
NOTIF_FINANCE = "titipan_pesanan_batal"
PESAN_202 = "Permintaan diajukan — menunggu persetujuan."


def _id(awal: str) -> str:
    return f"{awal}_btp4_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional BTP4", "account_number": "741-559-4444",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    pid, wid = _id("prd"), _id("wh")
    await db.products.insert_one({"id": pid, "name": "Kain Uji BTP4", "sku": "SKU-BTP4", "base_unit": "meter",
                                  "harga_pokok": 60_000, "price": HARGA, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji BTP4", "entity_id": KSC, "is_active": True,
                                    "created_at": now_iso()})
    sales, finance, manager = await akun("sales"), await akun("finance"), await akun("manager")
    return {"h": kepala_admin, "pid": pid, "wid": wid,
            "sales": sales, "hs": await sesi(sales), "fin": finance, "hf": await sesi(finance),
            "mgr": manager, "hm": await sesi(manager)}


async def _bayar(klien, siap, so: dict, jumlah: float) -> None:
    r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
        "customer_id": so["customer_id"], "amount": jumlah, "method": "transfer", "entity_id": KSC,
        "reference_no": f"TRF-{so['number']}-{uuid.uuid4().hex[:4]}",
        "allocations": [{"order_id": so["id"], "amount": jumlah}]})
    assert r.status_code == 200, r.text


async def _kirim_sebagian(klien, db, siap, monkeypatch, *, qty: float = 100.0, kirim: float = 40.0,
                          termin: str = "NET30", bayar_awal: float = 0.0, bayar_sesudah: float = 0.0,
                          ambil_sisa: float = 0.0, satu_tugas: bool = False, backorder: float = 0.0,
                          unit: str = "meter", base_qty: Optional[float] = None,
                          items: Optional[List[Dict[str, Any]]] = None, gl_harus_posted: bool = True,
                          **lain) -> Dict[str, Any]:
    """Pesanan `partially_shipped` lewat alur nyata: harga mesin harga, kirim `kirim` m lewat `dispatch_task`."""
    from services import config_service
    from services import shipment_service as shs
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Uji BTP4 · Toko Kain", "entity_id": KSC, "status": "active",
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    base = float(base_qty if base_qty is not None else qty)
    items = items or [{"product_id": siap["pid"], "product_name": "Kain Uji BTP4", "sku": "SKU-BTP4",
                       "quantity": qty, "base_quantity": base, "unit": unit, "base_unit": "meter", "price": HARGA}]
    pr = await config_service.compute_order_pricing(items, entity_id=KSC)
    sisa = round(base - kirim - backorder, 2)
    a1, a2 = _id("alc"), _id("alc")
    so = {"id": _id("so"), "number": f"SO-BTP4-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": cus,
          "customer_name": "Uji BTP4 · Toko Kain", "status": "confirmed", "payment_term_code": termin,
          "allocations": [{"id": a1, "product_id": siap["pid"], "warehouse_id": siap["wid"], "quantity": kirim},
                          {"id": a2, "product_id": siap["pid"], "warehouse_id": siap["wid"], "quantity": sisa}],
          "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "sales_id": siap["sales"]["id"],
          "sales_name": siap["sales"]["name"], "created_at": now_iso(), **pr}
    if backorder:
        so.update({"has_backorder": True, "backorders": [
            {"id": _id("bo"), "product_id": siap["pid"], "backorder_qty": backorder, "reserved_qty": 0.0,
             "status": "waiting_stock", "created_at": now_iso()}]})
    so.update(lain)
    await db.sales_orders.insert_one(dict(so))
    if bayar_awal:
        await _bayar(klien, siap, so, bayar_awal)

    def _roll(panjang: float, status: str) -> dict:
        return {"id": _id("roll"), "roll_no": f"R-{uuid.uuid4().hex[:5]}", "product_id": siap["pid"],
                "warehouse_id": siap["wid"], "owner_entity_id": KSC, "status": status, "length": panjang,
                "length_remaining": panjang, "unit": "meter", "lot": "L1", "bin_id": "bin_a",
                "reserved_ref": {"type": "sales_order", "id": so["id"]}, "unit_cost": 60_000,
                "created_at": now_iso()}
    r1 = _roll(kirim, "picked")
    # C1 (tinjauan akhir, R27) — roll sisa pesanan yang sudah disetujui berstatus `committed` (semua jalur persetujuan
    # pesanan meng-commit roll); `committed` BUKAN "disiapkan". Diambil dari rak (`ambil_sisa`) → `picked`.
    r2 = _roll(sisa, "picked" if ambil_sisa else "committed")
    await db.inventory_rolls.insert_many([dict(r1), dict(r2)])

    def _tugas(jumlah: float, ambil: float, status: str, alc: str, rolls: List[str]) -> dict:
        return {"id": _id("wt"), "flow_type": "outbound", "source_type": "sales_order", "status": status,
                "quantity": jumlah, "picked_qty": ambil, "shipped_qty": 0.0, "order_id": so["id"],
                "order_number": so["number"], "allocation_id": alc, "product_id": siap["pid"],
                "product_name": "Kain Uji BTP4", "warehouse_id": siap["wid"], "entity_id": KSC, "unit": "meter",
                "stages": ["created", "picking", "packing", "staging", "dispatched"],
                "scan_log": [{"id": _id("scan"), "scan_type": "pick", "roll_id": rid, "actual_qty": 1.0}
                             for rid in rolls], "created_at": now_iso()}
    if satu_tugas:
        t1 = _tugas(round(base - backorder, 2), kirim, "picking", a1, [r1["id"]])
        t2 = None
    else:
        t1 = _tugas(kirim, kirim, "packing", a1, [r1["id"]])
        t2 = _tugas(sisa, ambil_sisa, "picking" if ambil_sisa else "created", a2, [r2["id"]] if ambil_sisa else [])
    await db.wms_tasks.insert_many([dict(t) for t in (t1, t2) if t])

    async def _kirim_roll(order_id, product_id, warehouse_id, jumlah, roll_ids=None):
        await db.inventory_rolls.update_one({"id": r1["id"]}, {"$set": {"status": "in_transit_sales"}})
        keluar = {"roll_id": r1["id"], "length": float(jumlah), "unit_cost": 60_000,
                  "extended_cost": float(jumlah) * 60_000}
        return {"shipped": float(jumlah), "rolls": [keluar]}

    monkeypatch.setattr(shs, "ship_order_rolls", _kirim_roll)
    _t, shp = await shs.dispatch_task(t1, kirim, "Gudang Uji")
    assert shp["gl_status"] == "posted" or not gl_harus_posted, shp
    if bayar_sesudah:
        await _bayar(klien, siap, so, bayar_sesudah)
    o = await _so(db, so)
    assert o["status"] == "partially_shipped", o["status"]
    return {"so": o, "t1": t1, "t2": t2, "r1": r1, "r2": r2, "cus": cus, "shp": shp}


async def _so(db, so) -> dict:
    return await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})


async def _tutup(klien, h, so, alasan: str = "Pelanggan tidak jadi mengambil sisanya"):
    return await klien.post(f"/api/sales-orders/{so['id']}/close-remaining", headers=h, json={"reason": alasan})


async def _jumlah_jurnal(db) -> int:
    return await db.journal_entries.count_documents({})


async def _dibukukan(so) -> Dict[str, float]:
    from services import gl_service
    return await gl_service.order_revenue_recognized(so["id"])


async def _piutang_buku(db, so: dict) -> float:
    """Saldo 1-1200 Piutang dari jurnal pesanan ini (Surat Jalan, reklas uang muka; bukan `void`)."""
    tot = 0.0
    async for je in db.journal_entries.find({"status": {"$ne": "void"}, "$or": [
            {"ref.order_id": so["id"]}, {"source_id": so["id"]}]}, {"_id": 0, "lines": 1}):
        tot += sum(float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
                   for ln in je.get("lines") or [] if ln.get("account_code") == "1-1200")
    return round(tot, 2)


async def _titipan(db, cus: str) -> float:
    c = await db.customers.find_one({"id": cus}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance") or 0), 2)


def _teks(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _ditolak(klien, db, siap, so: dict, kata: str) -> None:
    """Tutup sisa → 409 berpesan `kata`; pesanan tidak berubah satu field pun."""
    sebelum = await _so(db, so)
    jurnal = await _jumlah_jurnal(db)
    r = await _tutup(klien, siap["hs"], so)
    assert r.status_code == 409, r.text
    assert kata.lower() in _teks(r).lower(), _teks(r)
    assert await _so(db, so) == sebelum, "pesanan tidak boleh berubah"
    assert await _jumlah_jurnal(db) == jurnal


# ── Alur utama ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_BTP4_tempo_jumlah_turun_ke_terkirim(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    so = k["so"]
    assert (await db.inventory_rolls.find_one({"id": k["r2"]["id"]}, {"_id": 0}))["status"] == "committed"
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=siap["hs"],
                        params={"action": "close_remaining"})
    assert r.status_code == 200, r.text
    assert (r.json()["needs_approval"], r.json()["basis"]) == (False, []), "C1 — sisa `committed` bukan disiapkan"
    assert round(so["grand_total"], 2) == 11_100_000, "hitung tangan: 100 m × 100.000 + PPN 11 %"
    buku = await _dibukukan(so)
    assert (buku["revenue"], buku["ppn"]) == (4_000_000, 440_000), buku
    jurnal = await _jumlah_jurnal(db)

    r = await _tutup(klien, siap["hs"], so, "Pelanggan hanya mau 40 m")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "shipped"
    o = await _so(db, so)
    it = o["items"][0]
    assert len(o["items"]) == 1
    assert it["quantity"] == 40 and it["base_quantity"] == 40
    assert it["quantity_ordered_original"] == 100 and it["base_quantity_ordered_original"] == 100
    assert round(o["grand_total"], 2) == round(buku["revenue"] + buku["ppn"], 2) == 4_440_000
    assert round(o["ppn_amount"], 2) == 440_000 and round(o["approval_amount"], 2) == 4_440_000
    assert round(o["net_subtotal"], 2) == 4_000_000 and round(it["line_total"], 2) == 4_000_000
    assert await _jumlah_jurnal(db) == jurnal, "tutup sisa tidak membuat jurnal"
    assert o["status"] == "shipped"
    cs = o["closed_short"]
    assert cs["reason"] == "Pelanggan hanya mau 40 m" and cs["by"] and cs["at"]
    assert cs["commission_basis"]["grand_total"] == 11_100_000
    # BTP-5 — dasar komisi = isian baris ASLI yang dibaca hitungan komisi (jumlah, harga, diskon, nilai baris)
    assert cs["commission_basis"]["items"] == [{"product_id": siap["pid"], "base_quantity": 100, "quantity": 100,
                                                "price": HARGA, "discount_percent": 0, "line_total": 10_000_000}]
    r2 = await db.inventory_rolls.find_one({"id": k["r2"]["id"]}, {"_id": 0})
    assert r2["status"] == "available" and not r2.get("reserved_ref"), "roll sisa dilepas"
    r1 = await db.inventory_rolls.find_one({"id": k["r1"]["id"]}, {"_id": 0})
    assert r1["status"] == "in_transit_sales", "roll yang sudah di Surat Jalan tidak pernah dilepas"
    t2 = await db.wms_tasks.find_one({"id": k["t2"]["id"]}, {"_id": 0})
    assert t2["status"] == "cancelled", "tugas sisa dibatalkan"
    t1 = await db.wms_tasks.find_one({"id": k["t1"]["id"]}, {"_id": 0})
    assert t1["status"] == "dispatched" and t1["shipped_qty"] == 40
    assert o["payment_status"] == "unpaid" and o["fulfillment"]["remaining_qty"] == 0
    assert await _piutang_buku(db, so) == round(o["grand_total"] - o["paid_total"], 2) == 4_440_000, \
        "piutang buku = sisa tagihan pesanan"


async def test_BTP4_plafon_kembali(klien, db, siap, monkeypatch):
    from services import customer_balance_service as cbs
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    sebelum = (await cbs.compute(k["cus"], KSC))["open_orders_amount"]
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 200, r.text
    sesudah = (await cbs.compute(k["cus"], KSC))["open_orders_amount"]
    assert round(sebelum - sesudah, 2) == 6_660_000, (sebelum, sesudah)
    tersimpan = await cbs.get(k["cus"], KSC)
    assert round(float(tersimpan["open_orders_amount"]), 2) == round(sesudah, 2), "saldo tersimpan disegarkan"


async def test_BTP4_cbd_kelebihan_ke_titipan(klien, db, siap, monkeypatch):
    from services import gl_service
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, termin="CBD", bayar_awal=11_100_000)
    so = k["so"]
    awal = await _titipan(db, k["cus"])
    jurnal = await _jumlah_jurnal(db)
    assert await gl_service.order_advance_unrecognized(so) == 6_660_000, "uang muka belum diakui = kelebihan"

    r = await _tutup(klien, siap["hs"], so, "Pelanggan membatalkan sisa 60 m")
    assert r.status_code == 202, r.text
    j = r.json()
    assert j["message"] == PESAN_202 and j["order_status"] == "partially_shipped"
    req = j["request"]
    assert req["action"] == "close_remaining" and "excess" in req["approval_basis"]
    assert round(float(req["amount"]), 2) == 6_660_000, "nominal kebijakan = nilai sisa"
    assert (await _so(db, so))["status"] == "partially_shipped", "belum ditutup selama menunggu"

    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/decision", headers=siap["hf"],
                         json={"decision": "approve", "note": "Kelebihan jadi titipan"})
    assert r.status_code == 200, r.text
    assert r.json()["order_status"] == "shipped"
    o = await _so(db, so)
    assert o["status"] == "shipped" and o["closed_short"]["request_id"] == req["id"]
    assert o["cancel_request_id"] == req["id"]
    assert await _titipan(db, k["cus"]) == round(awal + 6_660_000, 2), "titipan naik tepat nilai 60 m"
    assert await gl_service.order_advance_unrecognized(o) == 0, "tidak ada sisa menggantung di 2-1400"
    assert await _jumlah_jurnal(db) == jurnal, "tanpa jurnal baru"
    assert round(o["paid_total"], 2) == round(o["grand_total"], 2) == 4_440_000 and o["payment_status"] == "paid"
    assert await _piutang_buku(db, so) == 0, "piutang buku = sisa tagihan pesanan (lunas lewat reklas uang muka)"
    tarik = [p for p in o["payments"] if p.get("moved_to_deposit")]
    assert len(tarik) == 1 and round(tarik[0]["amount"], 2) == -6_660_000
    assert o["advance_to_deposit"]["deposit_done"] is True
    h = o["cancel_requests"][-1]
    assert h["status"] == "approved" and round(float(h["result"]["advance_to_deposit"]), 2) == 6_660_000
    rows = await db.notifications.find({"type": NOTIF_FINANCE, "ref": {"$regex": f"^{NOTIF_FINANCE}:{so['id']}"}},
                                       {"_id": 0}).to_list(50)
    assert siap["fin"]["id"] in {n["recipient_user"] for n in rows}, rows
    assert all("sisa ditutup" in f"{n['title']} {n['body']}" for n in rows)


async def test_BTP4_tempo_sudah_bayar_terkirim_tidak_wajib_setuju(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, bayar_sesudah=4_440_000)
    so = k["so"]
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=siap["hs"],
                        params={"action": "close_remaining"})
    assert r.status_code == 200, r.text
    assert r.json()["needs_approval"] is False and r.json()["basis"] == []
    assert r.json()["preview"]["excess_to_deposit"] == 0
    r = await _tutup(klien, siap["hs"], so)
    assert r.status_code == 200, r.text
    o = await _so(db, so)
    assert o["status"] == "shipped" and not o.get("cancel_request") and not o.get("cancel_requests")
    assert o["payment_status"] == "paid" and not o.get("advance_to_deposit")


async def test_BTP4_sisa_disiapkan_wajib_setuju_dan_roll_kembali_ke_rak(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, ambil_sisa=10.0)
    so = k["so"]
    r = await _tutup(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    assert r.json()["request"]["approval_basis"] == ["prepared"]
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/decision", headers=siap["hm"],
                         json={"decision": "approve", "note": ""})
    assert r.status_code == 200, r.text
    r2 = await db.inventory_rolls.find_one({"id": k["r2"]["id"]}, {"_id": 0})
    assert r2["status"] == "available" and (r2.get("return_to_rack") or {}).get("order_id") == so["id"]
    assert not r2.get("bin_id"), "roll yang sudah diambil masuk antrean Penempatan Rak"


async def test_BTP4_tugas_terkirim_sebagian_ditutup_ke_terkirim(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, satu_tugas=True)
    t1 = await db.wms_tasks.find_one({"id": k["t1"]["id"]}, {"_id": 0})
    assert t1["status"] == "partially_shipped"
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 200, r.text
    t1 = await db.wms_tasks.find_one({"id": k["t1"]["id"]}, {"_id": 0})
    assert t1["status"] == "dispatched" and t1["quantity"] == 40 and t1["shipped_qty"] == 40, t1
    assert (await _so(db, k["so"]))["status"] == "shipped"


async def test_BTP4_backorder_ikut_ditutup(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, backorder=20.0)
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 200, r.text
    o = await _so(db, k["so"])
    assert o["status"] == "shipped" and o["has_backorder"] is False
    bo = o["backorders"][0]
    assert bo["backorder_qty"] == 0 and bo["status"] == "closed" and bo["closed_qty"] == 20


async def test_BTP4_satuan_jual_berbeda(klien, db, siap, monkeypatch):
    """Baris dijual per yard (100 yard = 91,44 m): jumlah baru = terkirim dasar × quantity/base_quantity."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, qty=100.0, base_qty=91.44, unit="yard")
    so = k["so"]
    r = await _tutup(klien, siap["hs"], so)
    assert r.status_code == 200, r.text
    o = await _so(db, so)
    it = o["items"][0]
    assert it["base_quantity"] == 40 and it["unit"] == "yard"
    assert abs(it["quantity"] - 40 * 100 / 91.44) < 1e-4, it["quantity"]
    assert it["quantity_ordered_original"] == 100 and it["base_quantity_ordered_original"] == 91.44
    buku = await _dibukukan(so)
    assert round(o["grand_total"], 2) == round(buku["revenue"] + buku["ppn"], 2)
    assert abs(it["subtotal"] - round(it["price"] * it["quantity"], 2)) <= 0.01, "subtotal = harga × jumlah"
    assert round(it["subtotal"] - it["discount_amount"], 2) == round(it["line_total"], 2)


async def test_BTP4_preview(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, termin="CBD", bayar_awal=11_100_000)
    so = k["so"]
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=siap["hs"],
                        params={"action": "close_remaining"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["needs_approval"] is True and j["basis"] == ["excess"] and j["can_self_approve"] is False
    assert round(j["amount"], 2) == 6_660_000
    p = j["preview"]
    assert p["allowed"] is True and p["blockers"] == []
    assert p["lines"] == [{"product_id": siap["pid"], "product_name": "Kain Uji BTP4", "unit": "meter",
                           "qty_ordered": 100, "qty_shipped": 40}]
    assert (p["grand_total_before"], p["grand_total_after"]) == (11_100_000, 4_440_000)
    assert (p["remaining_value"], p["excess_to_deposit"]) == (6_660_000, 6_660_000)
    assert await _so(db, so) == so, "pratinjau tidak mengubah apa pun"


# ── Penolak (versi pertama, §5.6 langkah 1 · §7 butir 9) ─────────────────────────────────────────────────────────────
async def test_BTP4_tolak_faktur_pajak_per_pesanan(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.tax_invoices.insert_one({"id": _id("fkt"), "number": "FKT-BTP4-001", "order_id": k["so"]["id"],
                                      "entity_id": KSC, "status": "normal", "doc_kind": "faktur", "trigger": "pesanan",
                                      "items": [{"product_name": "Kain Uji BTP4", "quantity": 100}]})
    await _ditolak(klien, db, siap, k["so"], "Faktur Pajak")


async def test_BTP4_cek_batal_tutup_sisa_terhalang_200_dengan_daftar_penghalang(klien, db, siap, monkeypatch):
    """R21 — dialog butuh daftar penghalang: cancel-check 200 + preview.allowed=False; pengajuan tetap 409."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.tax_invoices.insert_one({"id": _id("fkt"), "number": "FKT-BTP4-003", "order_id": k["so"]["id"],
                                      "entity_id": KSC, "status": "normal", "doc_kind": "faktur", "trigger": "pesanan",
                                      "items": [{"product_name": "Kain Uji BTP4", "quantity": 100}]})
    r = await klien.get(f"/api/sales-orders/{k['so']['id']}/cancel-check", headers=siap["hs"],
                        params={"action": "close_remaining"})
    assert r.status_code == 200, r.text
    p = r.json()["preview"]
    assert p["allowed"] is False and p["blockers"] and "faktur pajak" in " ".join(p["blockers"]).lower()
    assert r.json()["needs_approval"] is False
    await _ditolak(klien, db, siap, k["so"], "Faktur Pajak")


async def test_BTP4_faktur_per_surat_jalan_lolos(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.tax_invoices.insert_one({"id": _id("fkt"), "number": "FKT-BTP4-002", "order_id": k["so"]["id"],
                                      "entity_id": KSC, "status": "normal", "doc_kind": "faktur",
                                      "trigger": "surat_jalan", "shipment_no": k["shp"]["shipment_no"],
                                      "items": [{"product_name": "Kain Uji BTP4", "quantity": 40,
                                                 "shipment_id": k["shp"]["id"]}]})
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 200, r.text


async def test_BTP4_tolak_nota_amandemen(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.credit_notes.insert_one({"id": _id("cn"), "number": "CN-BTP4-001", "kind": "credit_note",
                                      "source": "amendment", "status": "issued", "order_id": k["so"]["id"],
                                      "entity_id": KSC, "gross_amount": 100_000, "ppn_amount": 11_000})
    await _ditolak(klien, db, siap, k["so"], "nota")


async def test_BTP4_tolak_tagihan_tambahan(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch,
                              extra_billing_lines=[{"id": _id("ebl"), "gross": 55_500, "ppn": 5_500}])
    await _ditolak(klien, db, siap, k["so"], "tagihan tambahan")


async def test_BTP4_tolak_jurnal_per_pesanan(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.journal_entries.insert_one({"id": _id("je"), "number": "JE-BTP4-LAMA", "source_type": "sales_order",
                                         "source_id": k["so"]["id"], "entity_id": KSC, "status": "posted",
                                         "date": now_iso(), "lines": []})
    await _ditolak(klien, db, siap, k["so"], "per pesanan")


async def test_BTP4_tolak_terkirim_lebih_dari_dipesan(klien, db, siap, monkeypatch):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.wms_tasks.update_one({"id": k["t1"]["id"]},
                                  {"$set": {"quantity": 120.0, "shipped_qty": 120.0, "picked_qty": 120.0}})
    await _ditolak(klien, db, siap, k["so"], "lebih banyak dari yang dipesan")


async def test_BTP4_tolak_produk_sama_dua_baris(klien, db, siap, monkeypatch):
    baris = [{"product_id": siap["pid"], "product_name": "Kain Uji BTP4", "sku": "SKU-BTP4", "quantity": q,
              "base_quantity": q, "unit": "meter", "base_unit": "meter", "price": HARGA} for q in (50.0, 50.0)]
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, items=baris)
    await _ditolak(klien, db, siap, k["so"], "lebih dari satu baris")


async def test_BTP4_tolak_pesanan_khusus_belum_terkirim_penuh(klien, db, siap, monkeypatch):
    baris = [{"product_id": siap["pid"], "product_name": "Kain Uji BTP4", "sku": "SKU-BTP4", "quantity": 100.0,
              "base_quantity": 100.0, "unit": "meter", "base_unit": "meter", "price": HARGA,
              "special_order_item_id": _id("odi")}]
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, items=baris)
    await _ditolak(klien, db, siap, k["so"], "Batal item Pesanan Khusus")


async def test_BTP4_tolak_status_bukan_terkirim_sebagian(klien, db, siap):
    from services import config_service
    pr = await config_service.compute_order_pricing(
        [{"product_id": siap["pid"], "product_name": "Kain Uji BTP4", "quantity": 10, "base_quantity": 10,
          "unit": "meter", "price": HARGA}], entity_id=KSC)
    so = {"id": _id("so"), "number": f"SO-BTP4-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": _id("cus"),
          "customer_name": "Uji BTP4", "status": "confirmed", "payment_term_code": "NET30", "payments": [],
          "paid_total": 0.0, "payment_status": "unpaid", "sales_id": siap["sales"]["id"], "created_at": now_iso(),
          **pr}
    await db.sales_orders.insert_one(dict(so))
    await _ditolak(klien, db, siap, so, "dikirim sebagian")


async def test_BTP4_selisih_hitung_ulang_ditolak(klien, db, siap, monkeypatch):
    """Diskon pesanan berjenjang dipaksa SESUDAH Surat Jalan berjurnal (10 % karena pesanan ≥ 100 m): hitung ulang
    40 m dengan mesin harga ≠ yang dibukukan lebih dari Rp 1/baris → ditolak, pesanan tidak berubah."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.system_settings.update_one({"scope": KSC}, {"$set": {"sales.allow_order_discount": True}}, upsert=True)
    try:
        await db.sales_orders.update_one({"id": k["so"]["id"]}, {"$set": {"order_discount_percent": 10.0}})
        await _ditolak(klien, db, siap, k["so"], "dibukukan")
    finally:
        await db.system_settings.update_one({"scope": KSC}, {"$unset": {"sales.allow_order_discount": ""}})


async def test_BTP4_tanpa_izin_ditolak(klien, db, siap, monkeypatch, akun, sesi):
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    gudang = await akun("warehouse")
    r = await _tutup(klien, await sesi(gudang), k["so"])
    assert r.status_code == 403, r.text
    r = await _tutup(klien, siap["hs"], k["so"], "")
    assert r.status_code in (400, 422), r.text


# ── Saga & penanda eksekusi ──────────────────────────────────────────────────────────────────────────────────────────
async def test_BTP4_tugas_sedang_dikirim_ditolak_tanpa_perubahan(klien, db, siap, monkeypatch):
    """Tugas sisa sedang dipegang proses kirim (kunci saga) → 409; pesanan, tugas, roll tidak berubah; kunci dilepas."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    kunci = {"action": "dispatch", "by": "Gudang Lain", "started_at": now_iso(), "token": "lk_lain"}
    await db.wms_tasks.update_one({"id": k["t2"]["id"]}, {"$set": {"saga_lock": kunci}})
    sebelum = await _so(db, k["so"])
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 409, r.text
    assert "sedang diproses" in _teks(r)
    assert await _so(db, k["so"]) == sebelum, "pesanan tidak berubah dan kuncinya dilepas"
    t2 = await db.wms_tasks.find_one({"id": k["t2"]["id"]}, {"_id": 0})
    assert t2["status"] == "created" and t2["saga_lock"]["token"] == "lk_lain"
    assert (await db.inventory_rolls.find_one({"id": k["r2"]["id"]}, {"_id": 0}))["status"] == "committed"


async def test_BTP4_galat_sesudah_ditutup_putusan_tetap_tercatat(klien, db, siap, monkeypatch):
    """Eksekutor gagal SESUDAH pesanan tertutup → putusan tetap `approved` (penanda `cancel_request_id`), permintaan
    tidak tertinggal menunggu, galat asli diteruskan."""
    from services import so_cancel_service, so_close_remaining_service as scr
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, termin="CBD", bayar_awal=11_100_000)
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]

    asli = scr._sesudah

    async def _rusak(*a, **kw):   # langkah sesudah berjalan (jadwal, audit, notifikasi) lalu galat menyusul
        await asli(*a, **kw)
        raise RuntimeError("uji: langkah sesudah gagal")
    monkeypatch.setattr(scr, "_sesudah", _rusak)
    fin = await db.users.find_one({"id": siap["fin"]["id"]}, {"_id": 0})
    with pytest.raises(RuntimeError):
        await so_cancel_service.decide(k["so"]["id"], fin, "approve", "")
    o = await _so(db, k["so"])
    assert o["status"] == "shipped" and o["cancel_request_id"] == req_id and "cancel_request" not in o
    h = o["cancel_requests"][-1]
    assert h["id"] == req_id and h["status"] == "approved" and h["result"]["status"] == "shipped"


# ── Perbaikan tinjauan 1 (I1–I3) ─────────────────────────────────────────────────────────────────────────────────────
async def _jadwal_ikut_nilai(db, so: dict) -> Dict[str, Any]:
    """Jadwal tagihan termin pesanan yang sisanya ditutup — setara INV-PAY-01/02 untuk satu pesanan: Σ baris = nilai
    baru = `billed_total`; terbayar per baris ≤ nominal; Σ terbayar ≤ kas nyata pesanan."""
    from services import payment_plan_service as plans
    o = await _so(db, so)
    p = await plans.get_active("sales_order", so["id"])
    assert p and p["origin"] == "term", p
    jumlah = round(sum(float(ln.get("amount") or 0) for ln in p["lines"]), 2)
    assert jumlah == round(o["grand_total"], 2) == round(float(p["billed_total"]), 2), (jumlah, o["grand_total"], p)
    assert all(float(ln.get("paid_amount") or 0) <= float(ln.get("amount") or 0) + 0.01 for ln in p["lines"])
    assert round(sum(float(ln.get("paid_amount") or 0) for ln in p["lines"]), 2) <= plans.source_paid(o) + 0.01
    return p


async def _setujui(klien, siap, so: dict):
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/decision", headers=siap["hf"],
                         json={"decision": "approve", "note": "Kelebihan jadi titipan"})
    assert r.status_code == 200, r.text


async def test_BTP4_jadwal_tagihan_cbd_ikut_nilai_baru(klien, db, siap, monkeypatch):
    """I1 — CBD dibayar 11,1 jt, 40 m terkirim: sesudah tutup sisa uang muka 100 % = nilai baru 4,44 jt, lunas; jadwal
    tidak lagi menagih 6,66 jt."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, termin="CBD", bayar_awal=11_100_000)
    assert (await _tutup(klien, siap["hs"], k["so"])).status_code == 202
    await _setujui(klien, siap, k["so"])
    p = await _jadwal_ikut_nilai(db, k["so"])
    assert [(ln["kind"], ln["amount"], ln["paid_amount"], ln["status"]) for ln in p["lines"]] == \
        [("dp", 4_440_000, 4_440_000, "paid")]
    assert p["status"] == "closed", "tidak ada baris bersisa bila terbayar = nilai"


async def test_BTP4_jadwal_tagihan_dp50_ikut_nilai_baru(klien, db, siap, monkeypatch, capsys):
    """I1 — DP50 dibayar 5,55 jt, 40 m terkirim: uang muka 50 % × 4,44 jt = 2,22 jt + Surat Jalan penutup 2,22 jt,
    keduanya lunas (kelebihan 1,11 jt ke titipan). Pemeriksaan INV-PAY-01/02 `verify_data_integrity` hijau untuk semua
    jadwal modul ini (termasuk pesanan tutup sisa uji-uji sebelumnya)."""
    import importlib
    import re
    import sys
    from pathlib import Path
    k = await _kirim_sebagian(klien, db, siap, monkeypatch, termin="DP50", bayar_awal=5_550_000)
    awal = await _titipan(db, k["cus"])
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 202, r.text
    await _setujui(klien, siap, k["so"])
    assert await _titipan(db, k["cus"]) == round(awal + 1_110_000, 2)
    p = await _jadwal_ikut_nilai(db, k["so"])
    assert [(ln["kind"], ln["amount"], ln["paid_amount"], ln["status"]) for ln in p["lines"]] == \
        [("dp", 2_220_000, 2_220_000, "paid"), ("shipment", 2_220_000, 2_220_000, "paid")]
    assert p["status"] == "closed"
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    capsys.readouterr()
    await vdi.layer_payment_penalty_invariants(db)
    keluar = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    baris = [ln.strip() for ln in keluar.splitlines() if "INV-PAY-01" in ln or "INV-PAY-02" in ln]
    assert len(baris) == 2 and all(ln.startswith("[PASS]") for ln in baris), baris


async def test_BTP4_jadwal_tempo_tidak_berubah_bentuk(klien, db, siap, monkeypatch):
    """Pesanan tempo tanpa uang muka: jadwal tetap satu baris per Surat Jalan senilai jurnalnya (= nilai baru)."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    assert (await _tutup(klien, siap["hs"], k["so"])).status_code == 200
    p = await _jadwal_ikut_nilai(db, k["so"])
    assert [(ln["kind"], ln["amount"], ln["status"]) for ln in p["lines"]] == [("shipment", 4_440_000, "open")]


async def test_BTP4_tolak_rencana_cicilan_manual(klien, db, siap, monkeypatch):
    """I2 (keputusan implementer R10) — rencana cicilan buatan orang tidak diubah mesin → tutup sisa ditolak."""
    from pembantu import AKTOR_UJI
    from services import payment_plan_service as plans
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    rencana = await plans.create_plan("sales_order", k["so"]["id"], {"mode": "custom", "lines": [
        {"kind": "installment", "label": "Cicilan 1", "amount": 5_550_000, "due_date": "2026-12-01"},
        {"kind": "installment", "label": "Cicilan 2", "amount": 5_550_000, "due_date": "2027-01-01"}]}, AKTOR_UJI)
    assert rencana["origin"] != "term"
    await _ditolak(klien, db, siap, k["so"], "Sesuaikan atau batalkan rencana cicilan dulu (Finance), lalu tutup sisa.")


@pytest.mark.parametrize("gl_status", ["failed", "pending"])
async def test_BTP4_tolak_surat_jalan_belum_berjurnal(klien, db, siap, monkeypatch, paksa_jurnal_gagal, gl_status):
    """I3 — jurnal pendapatan Surat Jalan gagal (atau belum dicoba): nilai yang dibukukan belum lengkap → ditolak."""
    async with paksa_jurnal_gagal("sisip", source_type="shipment_revenue") as gagal:
        k = await _kirim_sebagian(klien, db, siap, monkeypatch, gl_harus_posted=False)
    assert gagal and k["shp"]["gl_status"] == "failed", k["shp"]
    if gl_status == "pending":
        await db.shipments.update_one({"id": k["shp"]["id"]}, {"$set": {"gl_status": "pending"}})
    await _ditolak(klien, db, siap, k["so"], f"Surat Jalan {k['shp']['shipment_no']} belum berjurnal pendapatan")


async def test_BTP4_surat_jalan_tanpa_jurnal_not_required_lolos(klien, db, siap, monkeypatch):
    """I3 — Surat Jalan yang memang tidak perlu jurnal (`gl_status = not_required`, nilai nol) tidak menghalangi."""
    k = await _kirim_sebagian(klien, db, siap, monkeypatch)
    await db.shipments.insert_one({"id": _id("shp"), "shipment_no": "SJ-BTP4-NOL", "entity_id": KSC,
                                   "order_id": k["so"]["id"], "order_number": k["so"]["number"],
                                   "product_id": siap["pid"], "qty": 0.0, "unit": "meter", "status": "dispatched",
                                   "gl_status": "not_required", "created_at": now_iso()})
    r = await _tutup(klien, siap["hs"], k["so"])
    assert r.status_code == 200, r.text
