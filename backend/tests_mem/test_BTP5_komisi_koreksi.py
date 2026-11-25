"""BTP-5 — komisi atas barang yang tidak jadi dikirim DIPOTONG di bulan penutupan + saldo potongan terbawa (A1-6).

Rancangan `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` §5.9 (keputusan pemilik A1-6, 25 Nov):
bulan yang sudah berakrual TIDAK berubah; koreksi = baris negatif di bulan penutupan (potret aturan baris yang sama),
tidak dipotong batas margin/nol; total bulan negatif → sisa terbawa ke bulan berikutnya sebagai saldo potongan per
sales per PT; titipan yang dipakai pesanan lain = komisi pesanan itu biasa; pesanan batal sebelum ada uang = hilang.
Mesin: `sales_force_service.compute_commission` (strategi `per_sku` bawaan, pengali capaian bawaan mati = ×1).

Dua jalur pesanan:
  * ALUR NYATA (U1, U4, U7) — tutup sisa lewat `so_close_remaining_service.execute_close_remaining` atas pesanan CBD
    yang dibayar lewat `/api/ar-receipts` dan dikirim 40 m lewat `shipment_service.dispatch_task` (pola BTP-4), batal
    lewat `so_cancel_service.execute_cancel` (pola S3). Tanggal baris bayar/penarikan ditulis ulang ke tanggal tetap
    (jam dinding uji bisa bulan apa saja).
  * SISIP LANGSUNG (U2, U3, U5, U6, U8, U9) — dokumen berbentuk keluaran Tugas 2/4: pesanan `closed_short` +
    `commission_basis`, baris bayar negatif `moved_to_deposit`, penanda `advance_to_deposit.deposit_done`.

Hitung tangan (tarif artikel Rp 3.500/m dipotret di baris, pengali harga ×1, capaian ×1):
  U1  CBD 100 m × 100.000 + PPN 11 % = 11.100.000 dibayar 15 Okt → Oktober 100 × 3.500 = 350.000 (diakru). Kirim 40 m,
      tutup sisa 20 Nov: 6.660.000 → titipan (baris −6.660.000). Oktober dihitung ulang = 350.000 (akrual ulang tanpa
      jurnal koreksi). November: koreksi −6.660.000 / 11.100.000 = 0,6 × 100 m = −60 m × 3.500 = −210.000; total bulan
      max(0, −210.000) = 0, saldo dibawa −210.000.
  U2  batas margin 50 %: 100 m @50.000, HPP 49.000 → margin 1.000/m, batas 500/m. Oktober 100 m → 50.000 (dibatasi).
      Tutup sisa 40 m: November koreksi −60 m × 500 = −30.000 (negatif, besar = komisi yang dulu dihitung untuk 60 m).
      Oktober + November = 20.000 = komisi 40 m. Dasar lama (tanpa rincian baris di `commission_basis`) = angka sama.
  U3  saldo: sales X — U2 tanpa batas margin: Oktober 350.000; November koreksi −210.000, total 0, dibawa −210.000.
      Sales Y bayar November 10 m → 35.000 (akrual November tidak nol). Akrual November → potret beku memuat
      `carry_out` X −210.000. Desember X dibayar 100 m → 350.000 + saldo −210.000 = 140.000. "Semua PT" sama.
  U4  batal sesudah bayar: 100 m @50.000 (tanpa PPN) = 5.000.000 dibayar 15 Okt (diakru 350.000), batal 20 Nov
      (seluruhnya ke titipan) → Oktober tetap 350.000; November koreksi −100 m = −350.000 ("koreksi_batal").
  U5  batal tanpa pembayaran → tidak ada di bulan mana pun (tanpa rincian, tanpa proyeksi).
  U6  pesanan batal ber-pembayaran TANPA `advance_to_deposit` (batal lama) → tetap dikecualikan.
  U7  bayar & tutup sisa bulan yang sama (November): 100 m dibayar, 60 m ke titipan → komisi 40 m = 140.000, saldo 0,
      tanpa baris koreksi (bersih dalam bulan itu).
  U8  titipan dipakai pesanan lain: A 100 m dibayar Okt (350.000), batal 20 Nov → koreksi −350.000; B 60 m dibayar dari
      titipan 22 Nov → 60 × 3.500 = 210.000 biasa. November mentah −140.000 → total 0, dibawa −140.000. Oktober +
      November − saldo = 210.000 = komisi B sekali (tanpa dobel).
  U9  pesanan ber-titipan tutup sisa dihitung "Semua PT" → sama dengan per PT.

    cd backend && python -m pytest tests_mem/test_BTP5_komisi_koreksi.py -n 0 -q
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
KANDA = "ent_kanda"
OKT, NOV, DES = "2026-10", "2026-11", "2026-12"
TARIF = 3_500.0
HARGA = 100_000.0
ARTIKEL = {"id": "tpl_btp5", "nama": "Batik BTP5", "kode": "BTK-BTP5"}
TGL_BAYAR_OKT = "2026-10-15T03:00:00+00:00"
TGL_BAYAR_NOV = "2026-11-05T03:00:00+00:00"
TGL_TUTUP = "2026-11-20T03:00:00+00:00"
#: R16 — Oktober difinalkan (gaji/akrual) 5 Nov, SEBELUM peristiwa 20 Nov (bulan bayar final → tidak berubah).
FINAL_OKT = "2026-11-05T03:00:00+00:00"


def _id(awal: str) -> str:
    return f"{awal}_btp5_{uuid.uuid4().hex[:8]}"


def _potret(pt: Dict[str, Any], *, cap: float = 0.0) -> Dict[str, Any]:
    from services.commission_rules import potret
    tarif = {"id": "irate_btp5", "asal_tingkat": "artikel", "asal_lingkup": "pt", "per_unit_amount": TARIF,
             "margin_cap_pct": cap}
    return potret(tarif, pt, artikel=ARTIKEL, sumber="pesanan", waktu=now_iso())


@pytest.fixture(scope="module")
async def f(klien, db, kepala_admin):
    from services.commission_rules import aturan_pt
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional BTP5", "account_number": "741-559-6666",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    pid, wid = _id("prd"), _id("wh")
    await db.products.insert_one({"id": pid, "name": "Kain Uji BTP5", "sku": "SKU-BTP5", "base_unit": "meter",
                                  "harga_pokok": 60_000, "price": HARGA, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji BTP5", "entity_id": KSC, "is_active": True,
                                    "created_at": now_iso()})
    admin = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    return {"h": kepala_admin, "pid": pid, "wid": wid, "pt": await aturan_pt(KSC), "admin": admin}


async def _sales(db, akun, kode: str, ent: str = KSC) -> Dict[str, Any]:
    u = await akun("sales", entitas=(ent,))
    cus = f"cus_btp5_{kode}_{uuid.uuid4().hex[:6]}"
    await db.customers.insert_one({"id": cus, "name": f"Toko BTP5 {kode}", "entity_id": ent, "status": "active",
                                   "assigned_sales_id": u["id"],
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    return {**u, "cus": cus}


async def _komisi(sid: str, period: str, ent: str = KSC) -> Dict[str, Any]:
    from services import sales_force_service as sfs
    return await sfs.compute_commission(sid, period, ent)


async def _saldo(db, ent: str, sid: str, bulan: str) -> Optional[Dict[str, Any]]:
    """Catatan saldo potongan komisi (R13 — satu tempat): `commission_carry_balances` per (PT, sales, bulan)."""
    return await db.commission_carry_balances.find_one({"entity_id": ent, "sales_id": sid, "period": bulan}, {"_id": 0})


def _inti(h: Dict[str, Any]) -> Dict[str, Any]:
    """Bagian hasil yang dibayar (tanpa KPI yang ikut nilai pesanan sekarang; tanpa baris rincian bernilai 0 milik
    pesanan hidup yang belum dibayar di periode itu — perilaku mesin sejak dulu)."""
    out = {k: h.get(k) for k in ("total_incentive", "commission", "commission_raw", "carry_in", "carry_out")}
    out["breakdown"] = [r for r in h["breakdown"] if r["commission"] or r["qty_base"]]
    return out


def _koreksi(h: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [r for r in h["breakdown"] if str(r.get("price_reason", "")).startswith("koreksi_")]


KHUSUS = ("koreksi_batal", "koreksi_tutup_sisa", "potongan_terbawa", "potongan_dibawa")


def _biasa(h: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [r for r in h["breakdown"] if r.get("price_reason") not in KHUSUS and (r["commission"] or r["qty_base"])]


async def _tulis_tanggal(db, so_id: str, *, bayar: Optional[str] = None, pindah: Optional[str] = None,
                         dibuat: Optional[str] = None) -> None:
    """Jam dinding uji bisa bulan apa saja: baris bayar (positif) → `bayar`, baris ke titipan → `pindah`; waktu
    peristiwa (`closed_short.at` / `cancelled_at`, bila ada) ikut `pindah`."""
    o = await db.sales_orders.find_one({"id": so_id}, {"_id": 0})
    rows = []
    for p in o.get("payments") or []:
        p = dict(p)
        tgl = pindah if p.get("moved_to_deposit") else bayar
        if tgl:
            p["created_at"], p["date"] = tgl, tgl
        rows.append(p)
    patch: Dict[str, Any] = {"payments": rows}
    if dibuat:
        patch["created_at"] = dibuat
    if pindah and o.get("closed_short"):
        patch["closed_short.at"] = pindah
    if pindah and o.get("cancelled_at"):
        patch["cancelled_at"] = pindah
    await db.sales_orders.update_one({"id": so_id}, {"$set": patch})


async def _finalkan(db, ent: str, sid: str, bulan: str, waktu: str = FINAL_OKT) -> None:
    """R16 — catat bahwa komisi `bulan` sales itu di PT itu difinalkan pada `waktu` (jam dinding uji tidak bisa dipakai
    untuk urutan waktu bertanggal tetap). Catatan yang sudah ada (dari akrual/gaji) hanya diganti `finalized_at`-nya;
    tanpa catatan → catatan finalisasi tanpa jurnal (bulan bertotal 0, selalu berlaku)."""
    q = {"entity_id": ent, "sales_id": sid, "period": bulan}
    if not await db.commission_carry_balances.find_one(q):
        await db.commission_carry_balances.insert_one({
            "id": _id("cmsb"), **q, "carry_out": 0.0, "carry_in": 0.0, "commission_raw": 0.0, "total": 0.0,
            "source": "uji", "journal_id": "", "recorded_at": waktu, "recorded_by": "uji"})
    await db.commission_carry_balances.update_one(q, {"$set": {"finalized_at": waktu}})


async def _bayar_api(klien, f, so: Dict[str, Any], jumlah: float) -> None:
    r = await klien.post("/api/ar-receipts", headers=f["h"], json={
        "customer_id": so["customer_id"], "amount": jumlah, "method": "transfer", "entity_id": KSC,
        "reference_no": f"TRF-{so['number']}-{uuid.uuid4().hex[:4]}",
        "allocations": [{"order_id": so["id"], "amount": jumlah}]})
    assert r.status_code == 200, r.text


async def _cbd_kirim_40(klien, db, f, sales: Dict[str, Any], monkeypatch) -> Dict[str, Any]:
    """Pesanan CBD 100 m dibayar penuh lewat kwitansi, 40 m dikirim lewat `dispatch_task` (jurnal Surat Jalan nyata);
    status `partially_shipped`. Baris berpotret tarif artikel Rp 3.500/m. Pola
    `test_BTP4_tutup_sisa._kirim_sebagian`."""
    from services import config_service
    from services import shipment_service as shs
    items = [{"product_id": f["pid"], "product_name": "Kain Uji BTP5", "sku": "SKU-BTP5", "quantity": 100.0,
              "base_quantity": 100.0, "unit": "meter", "base_unit": "meter", "price": HARGA,
              "commission_rule": _potret(f["pt"])}]
    pr = await config_service.compute_order_pricing(items, entity_id=KSC)
    a1, a2 = _id("alc"), _id("alc")
    so = {"id": _id("so"), "number": f"SO-BTP5-{uuid.uuid4().hex[:5]}", "entity_id": KSC,
          "customer_id": sales["cus"], "customer_name": "Toko BTP5", "status": "confirmed", "payment_term_code": "CBD",
          "allocations": [{"id": a1, "product_id": f["pid"], "warehouse_id": f["wid"], "quantity": 40.0},
                          {"id": a2, "product_id": f["pid"], "warehouse_id": f["wid"], "quantity": 60.0}],
          "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "sales_id": sales["id"],
          "sales_name": sales["name"], "created_at": now_iso(), **pr}
    await db.sales_orders.insert_one(dict(so))
    assert round(so["grand_total"], 2) == 11_100_000, "hitung tangan: 100 m × 100.000 + PPN 11 %"
    await _bayar_api(klien, f, so, 11_100_000)
    roll = {"id": _id("roll"), "roll_no": f"R-{uuid.uuid4().hex[:5]}", "product_id": f["pid"],
            "warehouse_id": f["wid"], "owner_entity_id": KSC, "status": "picked", "length": 40.0,
            "length_remaining": 40.0, "unit": "meter", "lot": "L1", "bin_id": "bin_a",
            "reserved_ref": {"type": "sales_order", "id": so["id"]}, "unit_cost": 60_000, "created_at": now_iso()}
    await db.inventory_rolls.insert_one(dict(roll))

    def _tugas(jumlah: float, ambil: float, status: str, alc: str) -> dict:
        return {"id": _id("wt"), "flow_type": "outbound", "source_type": "sales_order", "status": status,
                "quantity": jumlah, "picked_qty": ambil, "shipped_qty": 0.0, "order_id": so["id"],
                "order_number": so["number"], "allocation_id": alc, "product_id": f["pid"],
                "product_name": "Kain Uji BTP5", "warehouse_id": f["wid"], "entity_id": KSC, "unit": "meter",
                "stages": ["created", "picking", "packing", "staging", "dispatched"], "scan_log": [],
                "created_at": now_iso()}
    t1, t2 = _tugas(40.0, 40.0, "packing", a1), _tugas(60.0, 0.0, "created", a2)
    await db.wms_tasks.insert_many([dict(t1), dict(t2)])

    async def _kirim_roll(order_id, product_id, warehouse_id, jumlah, roll_ids=None):
        await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"status": "in_transit_sales"}})
        return {"shipped": float(jumlah), "rolls": [{"roll_id": roll["id"], "length": float(jumlah),
                                                     "unit_cost": 60_000, "extended_cost": float(jumlah) * 60_000}]}
    monkeypatch.setattr(shs, "ship_order_rolls", _kirim_roll)
    _t, shp = await shs.dispatch_task(t1, 40.0, "Gudang Uji")
    assert shp["gl_status"] == "posted", shp
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert o["status"] == "partially_shipped", o["status"]
    return o


async def _tutup_sisa(db, f, so_id: str) -> Dict[str, Any]:
    from services.so_close_remaining_service import execute_close_remaining
    await execute_close_remaining(so_id, f["admin"], "Pelanggan hanya mau 40 m")
    await _tulis_tanggal(db, so_id, pindah=TGL_TUTUP)
    o = await db.sales_orders.find_one({"id": so_id}, {"_id": 0})
    assert o["status"] == "shipped" and o["closed_short"]["commission_basis"]["grand_total"] == 11_100_000
    tarik = [p for p in o["payments"] if p.get("moved_to_deposit")]
    assert len(tarik) == 1 and round(tarik[0]["amount"], 2) == -6_660_000 and o["advance_to_deposit"]["deposit_done"]
    return o


def _baris(qty: float, bersih: float, *, pid: str, cap: float = 0.0, pt: Dict[str, Any], **lain) -> Dict[str, Any]:
    b = {"product_id": pid, "sku": f"SKU-{pid[-4:].upper()}", "product_name": f"Kain {pid}", "quantity": qty,
         "base_quantity": qty, "unit": "meter", "base_unit": "meter", "price": bersih, "line_total": qty * bersih,
         "discount_percent": 0, "unit_cost": 0, "price_source": "entity", "commission_rule": _potret(pt, cap=cap)}
    b.update(lain)
    return b


def _bayar(jumlah: float, tgl: str, **lain) -> Dict[str, Any]:
    return {"id": _id("pay"), "kind": "receipt", "amount": jumlah, "created_at": tgl, "date": tgl, **lain}


def _pindah(so_id: str, jumlah: float, sumber: str, tgl: str = TGL_TUTUP) -> Dict[str, Any]:
    return {"id": _id("pay"), "kind": "deposit", "amount": -jumlah, "receipt_id": f"{sumber}:{so_id}",
            "gl_bucket": "advance", "moved_to_deposit": True, "withdrawal": True, "created_at": tgl, "date": tgl}


async def _sisip_tutup_sisa(db, sales: Dict[str, Any], f, *, qty: float = 100.0, kirim: float = 40.0,
                            bersih: float = 50_000.0, cap: float = 0.0, unit_cost: float = 0.0,
                            tgl_bayar: str = TGL_BAYAR_OKT, dasar_lama: bool = False, tgl_tutup: str = TGL_TUTUP,
                            ent: str = KSC, bayar: Optional[List[tuple]] = None) -> Dict[str, Any]:
    """Pesanan CBD (tanpa PPN) berbentuk keluaran Tugas 4: baris turun ke `kirim`, `closed_short.commission_basis`
    berisi dasar ASLI, kelebihan → titipan (baris −). `dasar_lama` = bentuk `commission_basis` sebelum rincian baris."""
    pid = _id("prd")
    so_id = _id("so")
    asli = _baris(qty, bersih, pid=pid, cap=cap, unit_cost=unit_cost, pt=f["pt"])
    kini = {**asli, "quantity": kirim, "base_quantity": kirim, "line_total": kirim * bersih,
            "subtotal": kirim * bersih, "quantity_ordered_original": qty, "base_quantity_ordered_original": qty}
    gt_asli, gt_baru = qty * bersih, kirim * bersih
    dasar = {"product_id": pid, "base_quantity": qty}
    if not dasar_lama:
        dasar.update({"quantity": qty, "price": bersih, "discount_percent": 0, "line_total": qty * bersih})
    doc = {"id": so_id, "number": f"SO-BTP5-{so_id[-4:].upper()}", "entity_id": ent, "customer_id": sales["cus"],
           "status": "shipped", "items": [kini], "grand_total": gt_baru, "subtotal": gt_baru,
           "payments": [*[_bayar(j, t) for j, t in (bayar or [(gt_asli, tgl_bayar)])],
                        _pindah(so_id, gt_asli - gt_baru, "tutup_sisa_titipan", tgl_tutup)],
           "advance_to_deposit": {"amount": gt_asli - gt_baru, "deposit_done": True, "source_id":
                                  f"tutup_sisa_titipan:{so_id}", "kata": "sisa ditutup", "at": tgl_tutup},
           "closed_short": {"at": tgl_tutup, "by": "Uji", "reason": "uji", "request_id": "",
                            "grand_total_before": gt_asli, "grand_total_after": gt_baru,
                            "commission_basis": {"grand_total": gt_asli, "items": [dasar]}},
           "created_at": (bayar[0][1] if bayar else tgl_bayar), "updated_at": now_iso()}
    await db.sales_orders.insert_one(dict(doc))
    return doc


async def _sisip(db, sales: Dict[str, Any], f, *, qty: float = 100.0, bersih: float = 50_000.0,
                 status: str = "completed", payments: Optional[List[Dict[str, Any]]] = None,
                 dibuat: str = "2026-10-05T03:00:00+00:00", so_id: str = "", ent: str = KSC,
                 **lain) -> Dict[str, Any]:
    so_id = so_id or _id("so")
    doc = {"id": so_id, "number": f"SO-BTP5-{so_id[-4:].upper()}", "entity_id": ent, "customer_id": sales["cus"],
           "status": status, "items": [_baris(qty, bersih, pid=_id("prd"), pt=f["pt"])], "grand_total": qty * bersih,
           "subtotal": qty * bersih, "payments": payments or [], "created_at": dibuat, "updated_at": now_iso(), **lain}
    await db.sales_orders.insert_one(dict(doc))
    return doc


# ═══ U1 — tutup sisa (alur nyata): bulan asal tetap, koreksi di bulan penutupan ═════════════════════════════════════
async def test_BTP5_tutup_sisa_bulan_asal_tetap(klien, db, akun, f, monkeypatch):
    from services import gl_service as gl
    s = await _sales(db, akun, "u1")
    o = await _cbd_kirim_40(klien, db, f, s, monkeypatch)
    await _tulis_tanggal(db, o["id"], bayar=TGL_BAYAR_OKT, dibuat="2026-10-05T03:00:00+00:00")
    okt = await _komisi(s["id"], OKT)
    assert okt["total_incentive"] == 350_000, "100 m × 3.500 dibayar penuh Oktober"
    await gl.post_incentive_accrual(KSC, OKT, "Uji BTP5", date="2026-10-31")
    await _finalkan(db, KSC, s["id"], OKT)   # R16 — Oktober final 5 Nov, sebelum tutup sisa 20 Nov (kasus d)

    o = await _tutup_sisa(db, f, o["id"])
    assert o["items"][0]["base_quantity"] == 40 and round(o["grand_total"], 2) == 4_440_000
    sesudah = await _komisi(s["id"], OKT)
    assert _inti(sesudah) == _inti(okt), "bulan yang sudah berakrual tidak berubah"
    assert await gl.post_incentive_accrual(KSC, OKT, "Uji BTP5", date="2026-10-31") is None, "tanpa jurnal koreksi"

    nov = await _komisi(s["id"], NOV)
    kor = _koreksi(nov)
    assert len(kor) == 1, nov["breakdown"]
    k = kor[0]
    assert (k["price_reason"], k["qty_base"], k["commission"], k["rate"]) == ("koreksi_tutup_sisa", -60, -210_000, 3500)
    assert o["number"] in k["price_reason_label"] and "sisa" in k["price_reason_label"].lower()
    assert (k["order_id"], k["order_number"], k["name"], k["sku"]) == (o["id"], o["number"], "Batik BTP5", "BTK-BTP5")
    assert nov["commission_raw"] == -210_000
    assert (nov["total_incentive"], nov["commission"], nov["carry_in"], nov["carry_out"]) == (0, 0, 0, -210_000)
    assert round(sum(r["commission"] for r in nov["breakdown"]), 2) == nov["total_incentive"], nov["breakdown"]


# ═══ U2 — batas margin: koreksi tetap negatif (besar = komisi yang dulu dihitung) ══════════════════════════════════
@pytest.mark.parametrize("dasar_lama", [False, True], ids=["dasar_rinci", "dasar_lama"])
async def test_BTP5_koreksi_tidak_dipotong_margin(db, akun, f, dasar_lama):
    s = await _sales(db, akun, "u2")
    await _sisip_tutup_sisa(db, s, f, cap=50.0, unit_cost=49_000, dasar_lama=dasar_lama)
    await _finalkan(db, KSC, s["id"], OKT)
    okt = await _komisi(s["id"], OKT)
    assert okt["total_incentive"] == 50_000 and _biasa(okt)[0]["capped"] is True, okt["breakdown"]
    assert _biasa(okt)[0]["qty_base"] == 100, "bulan asal dihitung dari dasar ASLI"
    nov = await _komisi(s["id"], NOV)
    k = _koreksi(nov)
    assert len(k) == 1 and (k[0]["qty_base"], k[0]["commission"]) == (-60, -30_000), nov["breakdown"]
    assert k[0]["commission"] < 0, "koreksi tidak dipotong nol / batas margin"
    assert okt["total_incentive"] + nov["commission_raw"] == 20_000, "= komisi 40 m yang terkirim (dibatasi)"
    assert (nov["total_incentive"], nov["carry_out"]) == (0, -30_000)


async def test_BTP5_hitung_koreksi_murni(f):
    from services.commission_rules import hitung_baris, hitung_koreksi
    line = _baris(100, 50_000, pid="prd_btp5_murni", cap=50.0, unit_cost=49_000, pt=f["pt"])
    kw = {"bobot": 0.5, "biaya": 49_000.0, "biaya_diketahui": True, "pengali_capaian": 1.0}
    h = hitung_baris(line["commission_rule"], line, fraksi=0.6, **kw)
    k = hitung_koreksi(line["commission_rule"], line, fraksi=-0.6, **kw)
    assert set(k) == set(h)
    assert (k["komisi"], k["qty_dasar_terbayar"], k["dibatasi"]) == (-h["komisi"], -h["qty_dasar_terbayar"], True)
    assert k["komisi"] == -15_000, "60 m × batas 500/m × bobot 0,5"


# ═══ U3 — saldo potongan terbawa ke bulan berikutnya ═══════════════════════════════════════════════════════════════
async def test_BTP5_saldo_terbawa(db, akun, f):
    from services import gl_service as gl
    x, y = await _sales(db, akun, "u3x"), await _sales(db, akun, "u3y")
    await _sisip_tutup_sisa(db, x, f)
    await _finalkan(db, KSC, x["id"], OKT)
    await _sisip(db, y, f, qty=10, payments=[_bayar(500_000, TGL_BAYAR_NOV)], dibuat=TGL_BAYAR_NOV)
    nov = await _komisi(x["id"], NOV)
    assert (nov["commission_raw"], nov["total_incentive"], nov["carry_in"], nov["carry_out"]) == (
        -210_000, 0, 0, -210_000)
    dibawa = [r for r in nov["breakdown"] if r.get("price_reason") == "potongan_dibawa"]
    assert len(dibawa) == 1 and dibawa[0]["commission"] == 210_000, nov["breakdown"]
    assert round(sum(r["commission"] for r in nov["breakdown"]), 2) == 0

    akr = await gl.post_incentive_accrual(KSC, NOV, "Uji BTP5", date="2026-11-30")
    assert akr, "akrual November ada (sales Y berkomisi)"
    pot = await db.commission_period_rules.find_one({"entity_id": KSC, "period": NOV}, {"_id": 0})
    baris = {r["sales_id"]: r for r in pot["sales"]}
    assert baris[x["id"]]["total"] == 0 and baris[y["id"]]["total"] == 35_000
    sx = await _saldo(db, KSC, x["id"], NOV)
    assert (sx["carry_out"], sx["commission_raw"], sx["total"], sx["source"], sx["journal_id"]) == (
        -210_000, -210_000, 0, "akrual", akr["id"])
    assert (await _saldo(db, KSC, y["id"], NOV))["carry_out"] == 0, "bulan final tercatat juga tanpa saldo (R16)"

    await _sisip(db, x, f, payments=[_bayar(5_000_000, "2026-12-05T03:00:00+00:00")],
                 dibuat="2026-12-01T03:00:00+00:00")
    des = await _komisi(x["id"], DES)
    assert (des["commission_raw"], des["carry_in"], des["total_incentive"], des["carry_out"]) == (
        350_000, -210_000, 140_000, 0)
    terbawa = [r for r in des["breakdown"] if r.get("price_reason") == "potongan_terbawa"]
    assert len(terbawa) == 1 and terbawa[0]["commission"] == -210_000 and "November 2026" in terbawa[0]["name"]
    assert round(sum(r["commission"] for r in des["breakdown"]), 2) == des["total_incentive"]
    semua = await _komisi(x["id"], DES, "all")
    assert (semua["carry_in"], semua["total_incentive"], semua["carry_out"]) == (-210_000, 140_000, 0)
    # bulan beku November tidak berubah sesudah Desember dihitung
    assert _inti(await _komisi(x["id"], NOV)) == _inti(nov)


# ═══ U4 — batal sesudah bayar (alur nyata) ═══════════════════════════════════════════════════════════════════════
async def test_BTP5_batal_sesudah_bayar(klien, db, akun, f):
    from services import gl_service as gl
    from services.so_cancel_service import execute_cancel
    s = await _sales(db, akun, "u4")
    so = await _sisip(db, s, f, status="confirmed", payment_term_code="CBD", payment_status="unpaid", paid_total=0.0)
    await _bayar_api(klien, f, so, 5_000_000)
    await _tulis_tanggal(db, so["id"], bayar=TGL_BAYAR_OKT)
    okt = await _komisi(s["id"], OKT)
    assert okt["total_incentive"] == 350_000
    await gl.post_incentive_accrual(KSC, OKT, "Uji BTP5", date="2026-10-31")
    await _finalkan(db, KSC, s["id"], OKT)   # R16 — Oktober final 5 Nov, sebelum batal 20 Nov (kasus b)

    hasil = await execute_cancel(so["id"], f["admin"], "Pelanggan membatalkan sesudah bayar")
    assert round(float(hasil.get("advance_to_deposit") or 0), 2) == 5_000_000, hasil
    await _tulis_tanggal(db, so["id"], pindah=TGL_TUTUP)
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert o["status"] == "cancelled" and o["advance_to_deposit"]["deposit_done"] is True
    assert _inti(await _komisi(s["id"], OKT)) == _inti(okt), "bulan yang sudah berakrual tidak berubah"
    assert await gl.post_incentive_accrual(KSC, OKT, "Uji BTP5", date="2026-10-31") is None

    nov = await _komisi(s["id"], NOV)
    k = _koreksi(nov)
    assert len(k) == 1 and (k[0]["price_reason"], k[0]["qty_base"], k[0]["commission"]) == (
        "koreksi_batal", -100, -350_000), nov["breakdown"]
    assert o["number"] in k[0]["price_reason_label"] and "batal" in k[0]["price_reason_label"].lower()
    assert _biasa(nov) == [] and nov["projection_full"] == 0, "pesanan batal tidak diproyeksikan"
    assert (nov["total_incentive"], nov["carry_out"]) == (0, -350_000)


# ═══ U5 — batal sebelum ada uang: hilang dari semua bulan ═════════════════════════════════════════════════════════
async def test_BTP5_batal_sebelum_bayar_hilang(db, akun, f):
    from services.so_cancel_service import execute_cancel
    s = await _sales(db, akun, "u5")
    so = await _sisip(db, s, f, status="confirmed", dibuat="2026-11-02T03:00:00+00:00")
    hasil = await execute_cancel(so["id"], f["admin"], "Pelanggan membatalkan sebelum bayar")
    assert float(hasil.get("advance_to_deposit") or 0) == 0
    for bulan in (OKT, NOV, DES):
        h = await _komisi(s["id"], bulan)
        assert (h["breakdown"], h["total_incentive"], h["projection_full"]) == ([], 0, 0), (bulan, h["breakdown"])
        assert (h["commission_raw"], h["carry_out"]) == (0, 0)


# ═══ U6 — batal lama (tanpa penanda titipan) tetap dikecualikan ════════════════════════════════════════════════════
async def test_BTP5_batal_lama_tanpa_penanda_tetap_dikecualikan(db, akun, f):
    s = await _sales(db, akun, "u6")
    await _sisip(db, s, f, status="cancelled", payments=[_bayar(5_000_000, TGL_BAYAR_OKT)])
    for bulan in (OKT, NOV):
        h = await _komisi(s["id"], bulan)
        assert (h["breakdown"], h["total_incentive"], h["carry_out"]) == ([], 0, 0), (bulan, h["breakdown"])


# ═══ U7 — bayar dan tutup sisa di bulan yang sama (alur nyata) ═══════════════════════════════════════════════════
async def test_BTP5_bayar_dan_tutup_bulan_sama(klien, db, akun, f, monkeypatch):
    s = await _sales(db, akun, "u7")
    o = await _cbd_kirim_40(klien, db, f, s, monkeypatch)
    await _tulis_tanggal(db, o["id"], bayar=TGL_BAYAR_NOV, dibuat="2026-11-02T03:00:00+00:00")
    await _tutup_sisa(db, f, o["id"])
    nov = await _komisi(s["id"], NOV)
    assert (nov["total_incentive"], nov["commission_raw"], nov["carry_out"]) == (140_000, 140_000, 0)
    assert _koreksi(nov) == [], "uang masuk & keluar di bulan yang sama = bersih, tanpa baris koreksi"
    b = _biasa(nov)
    assert len(b) == 1 and (b[0]["qty_base"], b[0]["commission"]) == (40, 140_000), nov["breakdown"]
    assert nov["projection_full"] == 140_000, "proyeksi = barang yang terkirim"
    assert (await _komisi(s["id"], OKT))["total_incentive"] == 0


# ═══ U8 — titipan dipakai pesanan lain: komisi pesanan baru biasa, tanpa dobel ═════════════════════════════════════
async def test_BTP5_titipan_dipakai_pesanan_lain(db, akun, f):
    s = await _sales(db, akun, "u8")
    a_id = _id("so")
    a = await _sisip(db, s, f, status="cancelled", so_id=a_id, cancelled_at=TGL_TUTUP,
                     payments=[_bayar(5_000_000, TGL_BAYAR_OKT), _pindah(a_id, 5_000_000, "batal_titipan")],
                     advance_to_deposit={"amount": 5_000_000, "deposit_done": True, "kata": "dibatalkan"})
    await _finalkan(db, KSC, s["id"], OKT)
    b = await _sisip(db, s, f, qty=60, dibuat="2026-11-21T03:00:00+00:00",
                     payments=[_bayar(3_000_000, "2026-11-22T03:00:00+00:00", kind="deposit",
                                      receipt_id=f"titipan:{s['cus']}")])
    okt = await _komisi(s["id"], OKT)
    assert okt["total_incentive"] == 350_000
    nov = await _komisi(s["id"], NOV)
    biasa = _biasa(nov)
    assert len(biasa) == 1 and (biasa[0]["qty_base"], biasa[0]["commission"]) == (60, 210_000), nov["breakdown"]
    k = _koreksi(nov)
    assert len(k) == 1 and (k[0]["order_id"], k[0]["commission"]) == (a["id"], -350_000)
    assert (nov["commission_raw"], nov["total_incentive"], nov["carry_out"]) == (-140_000, 0, -140_000)
    assert okt["total_incentive"] + nov["total_incentive"] + nov["carry_out"] == 210_000, "= komisi B sekali"
    assert b["id"] != a["id"]


# ═══ U9 — "Semua PT" = jumlah per PT ═══════════════════════════════════════════════════════════════════════════════
async def test_BTP5_semua_pt_sama_dengan_per_pt(db, akun, f):
    s = await _sales(db, akun, "u9")
    await _sisip_tutup_sisa(db, s, f)
    await _finalkan(db, KSC, s["id"], OKT)
    for bulan in (OKT, NOV):
        pt, semua = await _komisi(s["id"], bulan), await _komisi(s["id"], bulan, "all")
        assert (semua["total_incentive"], semua["commission_raw"], semua["carry_out"]) == (
            pt["total_incentive"], pt["commission_raw"], pt["carry_out"]), bulan


# ═══ R13 — saldo potongan tersimpan di SATU tempat (`commission_carry_balances`) di semua jalur finalisasi bulan ═════
def _tgl(bulan: str, hari: int = 15) -> str:
    return f"{bulan}-{hari:02d}T03:00:00+00:00"


@pytest.fixture(scope="module")
async def gaji(db, sesi):
    """PT Kanda khusus uji gaji modul ini: karyawan isi awal dinonaktifkan (pola KA12), sesi admin di PT itu."""
    await db.hr_employees.update_many({"entity_id": KANDA}, {"$set": {"status": "inactive"}})
    return {"h": await sesi("admin@kainnusantara.id", entitas=KANDA)}


async def _karyawan(db, sales: Dict[str, Any]) -> None:
    await db.hr_employees.insert_one({
        "id": _id("emp"), "code": f"EMP-{_id('k')[-8:].upper()}", "name": sales["name"], "entity_id": KANDA,
        "user_id": sales["id"], "status": "active", "base_salary": 5_000_000, "allowances": [], "ptkp_status": "TK0",
        "bpjs_kes_enabled": False, "bpjs_tk_enabled": False, "join_date": "2025-01-01",
        "created_at": "2025-01-01T00:00:00+00:00"})


async def _buat_gaji(klien, h: Dict[str, str], bulan: str) -> Dict[str, Any]:
    """Proses gaji reguler PT Kanda `bulan` dibuat (slip & komisinya dihitung sekarang, status draf)."""
    r = await klien.post("/api/hr/payroll/runs", headers=h, json={"entity_id": KANDA, "period": bulan,
                                                                  "run_type": "regular"})
    assert r.status_code == 200, r.text
    return r.json()


async def _gaji(klien, h: Dict[str, str], bulan: str) -> Dict[str, Any]:
    """Proses gaji reguler PT Kanda `bulan`: buat → ajukan → setujui → posting (akrual komisi dari slip)."""
    return await _sahkan_gaji(klien, h, await _buat_gaji(klien, h, bulan))


async def _sahkan_gaji(klien, h: Dict[str, str], run: Dict[str, Any]) -> Dict[str, Any]:
    """Ajukan → setujui → posting proses gaji yang sudah dibuat."""
    for aksi in ("submit", "approve"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h, json={})
        assert r.status_code == 200, r.text
        run = r.json()
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h, json={})
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    return run


async def _jurnal_gaji(db, run: Dict[str, Any]) -> Dict[str, Any]:
    from services import gl_service as gl
    je = await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": await gl.payroll_source_id(run),
                                            "status": {"$ne": "void"}}, {"_id": 0})
    assert je, "jurnal gaji ada"
    return je


async def _akrual_hidup(db, ent: str, bulan: str) -> Optional[Dict[str, Any]]:
    return await db.journal_entries.find_one({"source_type": "incentive_accrual", "source_id": f"{ent}:{bulan}",
                                              "status": {"$ne": "void"}}, {"_id": 0})


async def test_BTP5_saldo_lewat_slip_gaji_total_nol(klien, db, akun, f, gaji):
    """Gaji September PT Kanda: komisi slip semua 0 (P2 habis dipotong koreksi) → tidak ada akrual, saldo tetap dicatat
    dari hasil mesin slip; Oktober membacanya."""
    p2 = await _sales(db, akun, "a2", KANDA)
    await _karyawan(db, p2)
    await _sisip_tutup_sisa(db, p2, f, ent=KANDA, tgl_bayar=_tgl("2026-08"), tgl_tutup=_tgl("2026-09", 20))
    await _finalkan(db, KANDA, p2["id"], "2026-08", _tgl("2026-09", 5))
    run = await _gaji(klien, gaji["h"], "2026-09")
    slip = next(s for s in run["payslips"] if s["user_id"] == p2["id"])
    assert slip["commission"] == 0 and slip["commission_engine"]["carry_out"] == -210_000, slip.get("commission_engine")
    assert await _akrual_hidup(db, KANDA, "2026-09") is None, "Σ komisi slip 0 → tanpa jurnal akrual"
    sp = await _saldo(db, KANDA, p2["id"], "2026-09")
    jg = await _jurnal_gaji(db, run)   # R17 — finalisasi tanpa akrual bertaut jurnal GAJI
    assert sp and (sp["carry_out"], sp["source"], sp["journal_id"]) == (-210_000, "slip_gaji", jg["id"])
    okt = await _komisi(p2["id"], OKT, KANDA)
    assert (okt["carry_in"], okt["total_incentive"], okt["carry_out"]) == (-210_000, 0, -210_000)


async def test_BTP5_saldo_lewat_slip_gaji(klien, db, akun, f, gaji):
    """Gaji November PT Kanda: P (koreksi −210.000, slip 0) + Q (35.000) → akrual dari slip 35.000; saldo P dicatat
    dari slip; Desember P dibayar 100 m → 350.000 − 210.000 = 140.000."""
    p, q = await _sales(db, akun, "a_p", KANDA), await _sales(db, akun, "a_q", KANDA)
    for s in (p, q):
        await _karyawan(db, s)
    await _sisip_tutup_sisa(db, p, f, ent=KANDA)
    await _finalkan(db, KANDA, p["id"], OKT)
    await _sisip(db, q, f, qty=10, ent=KANDA, payments=[_bayar(500_000, TGL_BAYAR_NOV)], dibuat=TGL_BAYAR_NOV)
    run = await _gaji(klien, gaji["h"], NOV)
    slip = {s["user_id"]: s for s in run["payslips"]}
    assert slip[p["id"]]["commission"] == 0 and slip[q["id"]]["commission"] == 35_000
    assert (slip[p["id"]]["commission_engine"]["carry_out"], slip[p["id"]]["commission_engine"]["commission_raw"]) == (
        -210_000, -210_000)
    akr = await _akrual_hidup(db, KANDA, NOV)
    assert akr and akr["total_debit"] == 35_000
    sp = await _saldo(db, KANDA, p["id"], NOV)
    assert sp and (sp["carry_out"], sp["source"], sp["journal_id"]) == (-210_000, "slip_gaji", akr["id"])
    await _sisip(db, p, f, ent=KANDA, payments=[_bayar(5_000_000, _tgl(DES, 5))], dibuat=_tgl(DES, 1))
    des = await _komisi(p["id"], DES, KANDA)
    assert (des["carry_in"], des["total_incentive"], des["carry_out"]) == (-210_000, 140_000, 0)


async def test_BTP5_saldo_bulan_total_nol_tanpa_jurnal(db, akun, f):
    """Akrual manual Februari: total PT 0 (R hanya berkoreksi) → tanpa jurnal, saldo tetap dicatat; Maret membacanya."""
    from services import gl_service as gl
    r = await _sales(db, akun, "b_r")
    await _sisip_tutup_sisa(db, r, f, tgl_bayar=_tgl("2026-01"), tgl_tutup=_tgl("2026-02", 20))
    await _finalkan(db, KSC, r["id"], "2026-01", _tgl("2026-02", 5))
    assert await gl.post_incentive_accrual(KSC, "2026-02", "Uji BTP5", date="2026-02-28") is None
    assert await _akrual_hidup(db, KSC, "2026-02") is None
    sr = await _saldo(db, KSC, r["id"], "2026-02")
    assert sr and (sr["carry_out"], sr["total"], sr["journal_id"], sr["source"]) == (-210_000, 0, "", "akrual")
    mar = await _komisi(r["id"], "2026-03")
    assert (mar["carry_in"], mar["total_incentive"], mar["carry_out"]) == (-210_000, 0, -210_000), "dibawa terus"


async def test_BTP5_koreksi_akrual_memperbarui_saldo(db, akun, f):
    """Mei diakru (S koreksi −210.000, T 35.000). Bayar susulan bertanggal Mei untuk S → akrual Mei diulang → saldo
    tersimpan ikut (−35.000, lalu habis), dan saldo masuk Juni mengikuti."""
    from services import gl_service as gl
    s, t = await _sales(db, akun, "c_s"), await _sales(db, akun, "c_t")
    await _sisip_tutup_sisa(db, s, f, tgl_bayar=_tgl("2026-04"), tgl_tutup=_tgl("2026-05", 20))
    await _finalkan(db, KSC, s["id"], "2026-04", _tgl("2026-05", 5))
    await _sisip(db, t, f, qty=10, payments=[_bayar(500_000, _tgl("2026-05", 10))], dibuat=_tgl("2026-05", 1))
    akr = await gl.post_incentive_accrual(KSC, "2026-05", "Uji BTP5", date="2026-05-31")
    assert akr and akr["total_debit"] == 35_000
    assert (await _saldo(db, KSC, s["id"], "2026-05"))["carry_out"] == -210_000
    assert (await _komisi(s["id"], "2026-06"))["carry_in"] == -210_000

    await _sisip(db, s, f, qty=50, payments=[_bayar(2_500_000, _tgl("2026-05", 25))], dibuat=_tgl("2026-05", 24))
    assert await gl.post_incentive_accrual(KSC, "2026-05", "Uji BTP5", date="2026-05-31") is None, "total PT tetap"
    ss = await _saldo(db, KSC, s["id"], "2026-05")
    assert (ss["carry_out"], ss["commission_raw"], ss["journal_id"]) == (-35_000, -35_000, akr["id"])
    assert (await _komisi(s["id"], "2026-06"))["carry_in"] == -35_000

    await _sisip(db, s, f, qty=100, payments=[_bayar(5_000_000, _tgl("2026-05", 26))], dibuat=_tgl("2026-05", 24))
    adj = await gl.post_incentive_accrual(KSC, "2026-05", "Uji BTP5", date="2026-05-31")
    assert adj and adj["source_type"] == "incentive_accrual_adj" and adj["total_debit"] == 315_000
    assert (await _saldo(db, KSC, s["id"], "2026-05"))["carry_out"] == 0, "saldo habis ikut tercatat"
    jun = await _komisi(s["id"], "2026-06")
    assert (jun["carry_in"], [r for r in jun["breakdown"] if r.get("price_reason") == "potongan_terbawa"]) == (0, [])


async def test_BTP5_akrual_dianulir_saldo_tidak_dibaca(db, akun, f):
    """Akrual Agustus dianulir → saldonya tidak dibaca lagi (September saldo masuk 0) sampai Agustus diakru ulang."""
    from services import gl_service as gl
    u, v = await _sales(db, akun, "d_u"), await _sales(db, akun, "d_v")
    await _sisip_tutup_sisa(db, u, f, tgl_bayar=_tgl("2026-07"), tgl_tutup=_tgl("2026-08", 20))
    await _finalkan(db, KSC, u["id"], "2026-07", _tgl("2026-08", 5))
    await _sisip(db, v, f, qty=10, payments=[_bayar(500_000, _tgl("2026-08", 10))], dibuat=_tgl("2026-08", 1))
    j1 = await gl.post_incentive_accrual(KSC, "2026-08", "Uji BTP5", date="2026-08-31")
    assert j1 and (await _komisi(u["id"], "2026-09"))["carry_in"] == -210_000
    await db.journal_entries.update_one({"id": j1["id"]}, {"$set": {"status": "void", "voided_by": "uji"}})
    sep = await _komisi(u["id"], "2026-09")
    assert (sep["carry_in"], sep["total_incentive"]) == (0, 0), "akrual dianulir: saldonya tidak dibaca"
    j2 = await gl.post_incentive_accrual(KSC, "2026-08", "Uji BTP5", date="2026-08-31")
    assert j2 and j2["id"] != j1["id"] and j2["source_type"] == "incentive_accrual"
    assert (await _saldo(db, KSC, u["id"], "2026-08"))["journal_id"] == j2["id"]
    assert (await _komisi(u["id"], "2026-09"))["carry_in"] == -210_000


# ═══ R16 — bulan bayar yang belum final saat batal / tutup sisa memakai dasar SESUDAH peristiwa ═══════════════════
TGL_PERISTIWA = "2026-11-02T03:00:00+00:00"   # batal / tutup sisa 2 Nov
FINAL_SESUDAH = "2026-11-05T03:00:00+00:00"   # gaji Oktober diposting 5 Nov (SESUDAH peristiwa)


async def test_BTP5_R16a_batal_bulan_bayar_belum_final(db, akun, f):
    """(a) Dibayar 28 Okt, batal 2 Nov, gaji Oktober diposting 5 Nov: Oktober tidak membayar komisi pesanan yang sudah
    batal, dan tidak ada baris koreksi di bulan mana pun."""
    s = await _sales(db, akun, "r16a")
    a_id = _id("so")
    await _sisip(db, s, f, status="cancelled", so_id=a_id, cancelled_at=TGL_PERISTIWA,
                 payments=[_bayar(5_000_000, _tgl(OKT, 28)), _pindah(a_id, 5_000_000, "batal_titipan", TGL_PERISTIWA)],
                 advance_to_deposit={"amount": 5_000_000, "deposit_done": True, "kata": "dibatalkan",
                                     "at": TGL_PERISTIWA, "done_at": TGL_PERISTIWA})
    await _finalkan(db, KSC, s["id"], OKT, FINAL_SESUDAH)
    for bulan in (OKT, NOV):
        h = await _komisi(s["id"], bulan)
        assert (h["breakdown"], h["total_incentive"], h["commission_raw"], h["projection_full"]) == ([], 0, 0, 0), (
            bulan, h["breakdown"])


async def test_BTP5_R16c_tutup_sisa_bulan_bayar_belum_final(db, akun, f):
    """(c) Dibayar 15 Okt, tutup sisa 2 Nov (40 dari 100 m), Oktober difinalkan 5 Nov: Oktober dihitung dengan dasar
    BARU (40 m = 140.000), tanpa koreksi di November."""
    s = await _sales(db, akun, "r16c")
    await _sisip_tutup_sisa(db, s, f, tgl_tutup=TGL_PERISTIWA)
    await _finalkan(db, KSC, s["id"], OKT, FINAL_SESUDAH)
    okt = await _komisi(s["id"], OKT)
    b = _biasa(okt)
    assert len(b) == 1 and (b[0]["qty_base"], b[0]["commission"]) == (40, 140_000), okt["breakdown"]
    assert okt["total_incentive"] == 140_000
    nov = await _komisi(s["id"], NOV)
    assert (_koreksi(nov), nov["total_incentive"], nov["carry_out"]) == ([], 0, 0), nov["breakdown"]


async def test_BTP5_R16e_bayar_terpisah_bulan_final_dan_belum(db, akun, f):
    """(e) 100 m @50.000 (5 jt), 40 m terkirim, tutup sisa 2 Nov (nilai baru 2 jt). September final (5 Okt), Oktober
    belum final saat tutup sisa (5 Nov).
      e1  DP 2,5 jt Sep + 2,5 jt Okt: Sep 50 m = 175.000 (tetap); Okt 0 (nilai baru sudah habis dipakai bayar Sep);
          Nov koreksi −(50 m − 40 m) = −35.000. Total 140.000 = 40 m.
      e2  DP 1 jt Sep + 4 jt Okt: Sep 20 m = 70.000; Okt dasar baru 1 jt / 2 jt × 40 m = 20 m = 70.000; Nov tanpa
          koreksi (20 m asli = 20 m baru). Total 140.000 = 40 m."""
    final_sep = "2026-10-05T03:00:00+00:00"
    hasil = {}
    for kode, sep, okt in (("e1", 2_500_000, 2_500_000), ("e2", 1_000_000, 4_000_000)):
        s = await _sales(db, akun, f"r16{kode}")
        await _sisip_tutup_sisa(db, s, f, tgl_tutup=TGL_PERISTIWA,
                                bayar=[(sep, _tgl("2026-09")), (okt, _tgl(OKT))])
        await _finalkan(db, KSC, s["id"], "2026-09", final_sep)
        await _finalkan(db, KSC, s["id"], OKT, FINAL_SESUDAH)
        hasil[kode] = {b: await _komisi(s["id"], b) for b in ("2026-09", OKT, NOV)}
    e1, e2 = hasil["e1"], hasil["e2"]
    assert [e1[b]["commission_raw"] for b in ("2026-09", OKT, NOV)] == [175_000, 0, -35_000]
    k = _koreksi(e1[NOV])
    assert len(k) == 1 and (k[0]["qty_base"], k[0]["commission"]) == (-10, -35_000), e1[NOV]["breakdown"]
    assert [e2[b]["commission_raw"] for b in ("2026-09", OKT, NOV)] == [70_000, 70_000, 0]
    assert _koreksi(e2[NOV]) == [] and [(r["qty_base"]) for r in _biasa(e2[OKT])] == [20]
    for h in (e1, e2):
        assert round(sum(h[b]["commission_raw"] for b in h), 2) == 140_000, "Σ = komisi 40 m yang terkirim"


# ═══ R17 — mode gaji `pay_on_invoice`: saldo dicatat dari slip, bertaut jurnal gaji ═══════════════════════════════
async def test_BTP5_R17_saldo_mode_pay_on_invoice(klien, db, akun, f, gaji):
    """PT Kanda bermode `pay_on_invoice` (komisi slip dibebankan langsung lewat jurnal gaji, tanpa akrual). Gaji Juni:
    P3 berkoreksi −210.000 → slip 0, saldo dicatat bertaut jurnal gaji → Juli saldo masuk −210.000. Proses gaji Juni
    dianulir (jurnal gajinya dibalik) → catatannya tidak dibaca (Juli 0)."""
    from services import config_resolver as resolver
    mode = "hr.payroll_commission_mode"
    p3 = await _sales(db, akun, "r17", KANDA)
    await _karyawan(db, p3)
    await _sisip_tutup_sisa(db, p3, f, ent=KANDA, tgl_bayar=_tgl("2026-05"), tgl_tutup=_tgl("2026-06", 20))
    await _finalkan(db, KANDA, p3["id"], "2026-05", _tgl("2026-06", 5))
    await resolver.set_value(mode, "pay_on_invoice", scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji BTP5 R17")
    try:
        run = await _gaji(klien, gaji["h"], "2026-06")
        assert run["commission_mode"] == "pay_on_invoice"
        slip = next(s for s in run["payslips"] if s["user_id"] == p3["id"])
        assert slip["commission"] == 0 and slip["commission_engine"]["carry_out"] == -210_000
        assert await _akrual_hidup(db, KANDA, "2026-06") is None, "mode tanpa akrual"
        jg = await _jurnal_gaji(db, run)
        sp = await _saldo(db, KANDA, p3["id"], "2026-06")
        assert sp and (sp["carry_out"], sp["source"], sp["journal_id"]) == (-210_000, "slip_gaji", jg["id"])
        assert (await _komisi(p3["id"], "2026-07", KANDA))["carry_in"] == -210_000

        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", headers=gaji["h"],
                             json={"reason": "Uji anulir gaji BTP5"})
        assert r.status_code == 200 and r.json()["status"] == "void", r.text
        jul = await _komisi(p3["id"], "2026-07", KANDA)
        assert (jul["carry_in"], jul["total_incentive"]) == (0, 0), "gaji dianulir: saldonya tidak dibaca"
    finally:
        await resolver.set_value(mode, "accrue_then_settle", scope_type="entity", scope_id=KANDA, actor="uji",
                                 reason="uji BTP5 R17 selesai")


# ═══ R19 — waktu final = saat angka yang difinalkan dihitung; finalisasi ulang sesudah anulir ════════════════════
async def _slip_dihitung_pada(db, run_id: str, sid: str, waktu: str) -> None:
    """Jam dinding uji tidak bisa dipakai untuk urutan bertanggal tetap: `computed_at` slip sales itu diganti
    `waktu`."""
    res = await db.hr_payslips.update_one({"run_id": run_id, "user_id": sid, "commission_engine": {"$exists": True}},
                                          {"$set": {"commission_engine.computed_at": waktu}})
    assert res.matched_count == 1


async def _batalkan_sintetis(db, so_id: str, waktu: str, jumlah: float) -> None:
    """Bentuk keluaran batal sesudah bayar (Tugas 2 + S3): status batal, uang muka → titipan (baris −, penanda)."""
    await db.sales_orders.update_one({"id": so_id}, {
        "$set": {"status": "cancelled", "cancelled_at": waktu,
                 "advance_to_deposit": {"amount": jumlah, "deposit_done": True, "kata": "dibatalkan", "at": waktu,
                                        "done_at": waktu, "source_id": f"batal_titipan:{so_id}"}},
        "$push": {"payments": _pindah(so_id, jumlah, "batal_titipan", waktu)}})


async def test_BTP5_R19_N1_slip_dihitung_sebelum_peristiwa(klien, db, akun, f, gaji):
    """N1 — slip Oktober dihitung 1 Nov (pesanan masih hidup: 100 m = 350.000), pesanan batal 3 Nov, gaji (mode akru)
    diposting sesudahnya: Oktober final sejak 1 Nov → Oktober = yang dibayar slip (350.000), November berkoreksi
    −350.000 (saldo dibawa −350.000). Σ Okt + Nov + saldo = 0."""
    s = await _sales(db, akun, "n1", KANDA)
    await _karyawan(db, s)
    so = await _sisip(db, s, f, ent=KANDA, payments=[_bayar(5_000_000, TGL_BAYAR_OKT)])
    run = await _buat_gaji(klien, gaji["h"], OKT)
    assert next(x for x in run["payslips"] if x["user_id"] == s["id"])["commission"] == 350_000
    dihitung, batal = "2026-11-01T03:00:00+00:00", "2026-11-03T03:00:00+00:00"
    await _slip_dihitung_pada(db, run["id"], s["id"], dihitung)
    await _batalkan_sintetis(db, so["id"], batal, 5_000_000)
    await _sahkan_gaji(klien, gaji["h"], run)
    rec = await _saldo(db, KANDA, s["id"], OKT)
    assert (rec["finalized_at"], rec["source"], rec["total"]) == (dihitung, "slip_gaji", 350_000)
    assert rec["journal_id"] == (await _akrual_hidup(db, KANDA, OKT))["id"], "mode akru: finalisasi = akrual dari slip"
    okt = await _komisi(s["id"], OKT, KANDA)
    assert okt["total_incentive"] == 350_000, "Oktober = yang dibayar slip"
    nov = await _komisi(s["id"], NOV, KANDA)
    k = _koreksi(nov)
    assert len(k) == 1 and (k[0]["price_reason"], k[0]["commission"]) == ("koreksi_batal", -350_000), nov["breakdown"]
    assert (nov["total_incentive"], nov["carry_out"]) == (0, -350_000)
    assert okt["total_incentive"] + nov["total_incentive"] + nov["carry_out"] == 0


async def test_BTP5_R19_N2_anulir_lalu_gaji_ulang(klien, db, akun, f, gaji):
    """N2 (mode `pay_on_invoice`) — gaji Juli dihitung 3 Agu & diposting (pesanan X 350.000), X batal 10 Agu → Agustus
    berkoreksi −350.000. Gaji Juli dianulir → koreksi hilang. Proses Juli baru dihitung sesudah batal (X = 0) dan
    diposting → finalisasi lama tidak berlaku lagi, waktu final ditimpa (sesudah batal) → Agustus TANPA koreksi; Juli 0,
    saldo 0."""
    from services import config_resolver as resolver
    mode = "hr.payroll_commission_mode"
    s = await _sales(db, akun, "n2", KANDA)
    await _karyawan(db, s)
    so = await _sisip(db, s, f, ent=KANDA, payments=[_bayar(5_000_000, _tgl("2026-07"))],
                      dibuat=_tgl("2026-07", 1))
    await resolver.set_value(mode, "pay_on_invoice", scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji BTP5 R19")
    try:
        run1 = await _buat_gaji(klien, gaji["h"], "2026-07")
        assert next(x for x in run1["payslips"] if x["user_id"] == s["id"])["commission"] == 350_000
        await _slip_dihitung_pada(db, run1["id"], s["id"], _tgl("2026-08", 3))
        run1 = await _sahkan_gaji(klien, gaji["h"], run1)
        assert (await _saldo(db, KANDA, s["id"], "2026-07"))["finalized_at"] == _tgl("2026-08", 3)
        await _batalkan_sintetis(db, so["id"], _tgl("2026-08", 10), 5_000_000)
        agu = await _komisi(s["id"], "2026-08", KANDA)
        assert [r["commission"] for r in _koreksi(agu)] == [-350_000], "Juli final sebelum batal → koreksi"

        r = await klien.post(f"/api/hr/payroll/runs/{run1['id']}/void", headers=gaji["h"],
                             json={"reason": "Uji anulir gaji BTP5 R19"})
        assert r.status_code == 200 and r.json()["status"] == "void", r.text
        assert _koreksi(await _komisi(s["id"], "2026-08", KANDA)) == [], "gaji dianulir: Juli belum final"

        run2 = await _buat_gaji(klien, gaji["h"], "2026-07")
        assert next(x for x in run2["payslips"] if x["user_id"] == s["id"])["commission"] == 0, "X sudah batal"
        run2 = await _sahkan_gaji(klien, gaji["h"], run2)
        rec = await _saldo(db, KANDA, s["id"], "2026-07")
        assert rec["journal_id"] == (await _jurnal_gaji(db, run2))["id"]
        assert rec["finalized_at"] > _tgl("2026-08", 10), "finalisasi lama tidak berlaku → waktu final ditimpa"
        agu = await _komisi(s["id"], "2026-08", KANDA)
        assert (_koreksi(agu), agu["total_incentive"], agu["carry_in"], agu["carry_out"]) == ([], 0, 0, 0)
        assert (await _komisi(s["id"], "2026-07", KANDA))["total_incentive"] == 0
    finally:
        await resolver.set_value(mode, "accrue_then_settle", scope_type="entity", scope_id=KANDA, actor="uji",
                                 reason="uji BTP5 R19 selesai")


async def test_BTP5_R19_N2_anulir_lalu_akrual_ulang(db, akun, f):
    """N2 jalur akrual manual — Maret diakru (X 350.000, angka dihitung 1 Apr), X batal 10 Apr → April berkoreksi.
    Akrual Maret dianulir lalu diakru ulang sesudah batal (X = 0, total PT 0 → tanpa jurnal) → waktu final ditimpa →
    April TANPA koreksi; Maret 0."""
    from services import gl_service as gl
    s = await _sales(db, akun, "n2b")
    so = await _sisip(db, s, f, payments=[_bayar(5_000_000, _tgl("2026-03"))], dibuat=_tgl("2026-03", 1))
    j1 = await gl.post_incentive_accrual(KSC, "2026-03", "Uji BTP5", date="2026-03-31")
    assert j1 and j1["total_debit"] == 350_000
    await _finalkan(db, KSC, s["id"], "2026-03", _tgl("2026-04", 1))   # angka akrual dihitung 1 Apr
    await _batalkan_sintetis(db, so["id"], _tgl("2026-04", 10), 5_000_000)
    assert [r["commission"] for r in _koreksi(await _komisi(s["id"], "2026-04"))] == [-350_000]

    await db.journal_entries.update_one({"id": j1["id"]}, {"$set": {"status": "void", "voided_by": "uji"}})
    assert await gl.post_incentive_accrual(KSC, "2026-03", "Uji BTP5", date="2026-03-31") is None, "total PT 0"
    rec = await _saldo(db, KSC, s["id"], "2026-03")
    assert rec["journal_id"] == "" and rec["finalized_at"] > _tgl("2026-04", 10), "waktu final ditimpa"
    apr = await _komisi(s["id"], "2026-04")
    assert (_koreksi(apr), apr["total_incentive"], apr["carry_out"]) == ([], 0, 0)
    assert (await _komisi(s["id"], "2026-03"))["total_incentive"] == 0
