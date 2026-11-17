"""Bagian C — HUTANG, PAJAK, SAMPLE BERBAYAR, SETORAN GAJI (F11–F15): data awal tambahan per peserta.

F11 (bayar tagihan), F12 (kontrabon) dan F13 (faktur pajak) memakai data `a_dasar` (tagihan_bayar, tagihan_kontrabon,
so_lunas) — tidak perlu data baru. Modul ini menyiapkan:

* `sample_berbayar` (F14) — Sales membuat **Pesanan Sample berbayar** (SOS) yang menunggu persetujuan bayar Finance.
  Pembelinya pelanggan KEDUA peserta ("Latihan NN · Butik Sample Peserta NN"), BUKAN pelanggan F02–F04, supaya kwitansi
  sample tidak ikut teralokasi "tertua dulu" ke SO piutang latihan bagian A (dan sebaliknya).
* `gaji_susulan` (F15) — (1) sekali per PT: proses gaji REGULER PT Sukacita Oktober 2026 (sudah disahkan data acuan)
  diposting Manajer, sehingga kewajiban BPJS & PPh 21 masa itu tercatat dan gajinya masuk antrean "Gaji siap dibayar";
  (2) per peserta: satu proses gaji **SUSULAN** Oktober 2026 (insentif tertinggal satu karyawan) dibuat, diajukan,
  disahkan dan diposting Manajer → tiap peserta punya satu gaji untuk DIBAYAR sendiri dan PPh 21-nya untuk DISETOR
  sendiri (proses reguler PT dipakai bersama — pembayarannya peragaan pelatih, lihat catatan pelatih F15).

Semua lewat endpoint resmi (Sales/Admin/Manajer). Aman dijalankan ulang: yang sudah ada dipakai lagi. Tanpa id lokal —
karyawan, produk, rekening dicari menurut data (berlaku juga di VPS).
"""
from typing import Any, Dict, List

from db import db

from .konteks import KSC, PREFIX, LatihCtx, Peserta

MASA_GAJI = "2026-10"      # masa gaji latihan (proses reguler data acuan: KSC/PAY-… Oktober 2026, sudah disahkan)
KOMPONEN_SUSULAN = "INSENTIF"   # komponen masukan yang boleh di proses susulan (data acuan PT)
QTY_SAMPLE = 3.0           # yard — di bawah batas sample woven standar (5 yard)


def pelanggan_sample(p: Peserta) -> str:
    return f"{PREFIX} {p.kode} · Butik Sample Peserta {p.kode}"


# ── F14 — Pesanan Sample berbayar ────────────────────────────────────────────────────────────────────────────────────
async def _pelanggan_sample(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    nama = pelanggan_sample(p)
    cust = await db.customers.find_one({"name": nama}, {"_id": 0})
    if cust:
        return cust
    adm = await lc.admin()
    sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    c = await adm.post("/customers", {
        "name": nama, "pic_name": f"Ibu Butik {p.kode}", "phone": f"0815777{p.no:05d}", "city": "Bandung",
        "address": f"Jl. Butik Latihan No. {p.no}, Bandung", "type": "Retail", "segment": "Retail",
        "credit_limit": 10_000_000, "assigned_sales_id": sales["id"], "entity_id": KSC,
        "payment_profile": {"default_method": "transfer", "term_days": 0}}, entity=KSC)
    await lc.tag("customers", c["id"], p, "pelanggan_sample")
    return await db.customers.find_one({"id": c["id"]}, {"_id": 0})


async def _produk_sample(lc: LatihCtx) -> Dict[str, Any]:
    """Produk jadi woven ber-stok di PT Sukacita (batas sample woven 5 yard) — dicari dari data, bukan id tetap."""
    for p in await lc.stocked(KSC, "woven", 10, 30):
        if str(p.get("fabric_type") or "woven").lower() == "woven" and (p.get("base_unit") or "yard") == "yard":
            return p
    raise RuntimeError("tidak ada produk woven ber-stok di PT Sukacita untuk sample")


async def sample_berbayar(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F14 — SOS berbayar (menunggu ACC bayar Finance) untuk pelanggan kedua peserta."""
    cust = await _pelanggan_sample(lc, p)
    ada = await db.sales_orders.find_one({"customer_id": cust["id"], "order_type": "sample", "sample_billing": "paid",
                                          "status": {"$nin": ["cancelled", "expired"]}}, {"_id": 0},
                                         sort=[("created_at", -1)])
    if not ada:
        prod = await _produk_sample(lc)
        s = await lc.u("sales")
        so = await s.post("/sales-orders", {
            "customer_id": cust["id"], "shipping_address_id": (cust.get("addresses") or [{}])[0].get("id", ""),
            "entity_id": KSC, "order_type": "sample", "sample_billing": "paid",
            "items": [{"product_id": prod["id"], "quantity": QTY_SAMPLE, "unit": "yard", "base_quantity": QTY_SAMPLE,
                       "is_sample": True, "sample_kind": "standard"}],
            "notes": f"Sample berbayar latihan peserta {p.kode} — pelanggan transfer dulu, Finance setujui bayar"},
            entity=KSC)
        await lc.tag("sales_orders", so["id"], p, "sample_berbayar")
        ada = await lc.so(so["id"])
    return {"sos": ada.get("number"), "sos_id": ada["id"], "pelanggan": cust["name"], "pelanggan_id": cust["id"],
            "total": round(float(ada.get("grand_total") or 0), 2), "status": ada.get("status"),
            "status_bayar_sample": ada.get("sample_payment_status")}


# ── F15 — Gaji siap dibayar + setoran ────────────────────────────────────────────────────────────────────────────────
async def _run_doc(run_id: str) -> Dict[str, Any]:
    return await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})


async def _sampai_posted(mgr, run: Dict[str, Any]) -> Dict[str, Any]:
    """Ajukan → sahkan → posting (Manajer) dari status mana pun yang masih bisa maju."""
    if run["status"] == "draft":
        await mgr.post(f"/hr/payroll/runs/{run['id']}/submit", {}, entity=KSC)
        run = await _run_doc(run["id"])
    if run["status"] == "pending_approval":
        await mgr.post(f"/hr/payroll/runs/{run['id']}/approve", {}, entity=KSC)
        run = await _run_doc(run["id"])
    if run["status"] == "approved":
        await mgr.post(f"/hr/payroll/runs/{run['id']}/post-gl", {}, entity=KSC)
        run = await _run_doc(run["id"])
    return run


async def _reguler_terposting(mgr) -> Dict[str, Any]:
    """Sekali per PT: proses reguler masa latihan (disahkan data acuan) diposting → kewajiban BPJS & PPh 21 tercatat."""
    run = await db.hr_payroll_runs.find_one({"entity_id": KSC, "period": MASA_GAJI, "run_type": {"$in": ["regular", None]},
                                             "status": {"$nin": ["cancelled", "void"]}}, {"_id": 0})
    if not run:
        run = await mgr.post("/hr/payroll/runs", {"entity_id": KSC, "period": MASA_GAJI, "run_type": "regular"}, entity=KSC)
        run = await _run_doc(run["id"])
    return await _sampai_posted(mgr, run)


async def _karyawan(p: Peserta, reg: Dict[str, Any]) -> Dict[str, Any]:
    """Satu karyawan yang ikut digaji di proses REGULER masa itu DAN kena PPh 21 (jadi insentif susulannya menambah PPh 21
    gabungan bulan yang bisa disetor peserta), bergiliran per nomor peserta (urut nama → sama di mesin mana pun). Akun
    latihan juga tercatat sebagai karyawan tanpa gaji pokok — mereka tidak ikut proses reguler, jadi tidak terpilih."""
    slips: List[Dict[str, Any]] = await db.hr_payslips.find(
        {"run_id": reg["id"], "pph21": {"$gt": 0}}, {"_id": 0, "employee_id": 1, "employee_name": 1}
    ).sort("employee_name", 1).to_list(500)
    if not slips:
        raise RuntimeError(f"proses reguler {reg.get('number')} tidak punya slip")
    s = slips[p.no % len(slips)]
    return {"id": s["employee_id"], "name": s.get("employee_name", "")}


async def gaji_susulan(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F15 — proses gaji SUSULAN milik peserta (terposting, menunggu dibayar) + proses reguler PT terposting."""
    mgr = await lc.u("manager")
    reg = await _reguler_terposting(mgr)
    tanda = f"Latihan F15 peserta {p.kode}"
    run = None
    inp = await db.hr_pay_inputs.find_one({"entity_id": KSC, "reason": tanda, "status": {"$ne": "cancelled"}}, {"_id": 0})
    if inp and inp.get("used_run_id"):
        run = await _run_doc(inp["used_run_id"])
    if not run:
        if not inp:
            emp = await _karyawan(p, reg)
            inp = await mgr.post("/hr/payroll/inputs", {
                "employee_id": emp["id"], "component_code": KOMPONEN_SUSULAN, "pay_period": MASA_GAJI,
                "amount": 750_000 + p.no * 1_000, "label": "Insentif tertinggal (susulan)", "reason": tanda}, entity=KSC)
        if inp.get("status") == "pending":
            await mgr.post(f"/hr/payroll/inputs/{inp['id']}/approve", {}, entity=KSC)
        run = await mgr.post("/hr/payroll/runs", {"entity_id": KSC, "period": MASA_GAJI, "run_type": "susulan"}, entity=KSC)
        run = await _run_doc(run["id"])
    await lc.tag("hr_payroll_runs", run["id"], p, "gaji_susulan")
    run = await _sampai_posted(mgr, run)
    t = run.get("totals") or {}
    slip = await db.hr_payslips.find_one({"run_id": run["id"]}, {"_id": 0, "employee_name": 1})
    return {"proses_gaji": run.get("number"), "proses_gaji_id": run["id"], "masa": MASA_GAJI, "jenis": "susulan",
            "karyawan": (slip or {}).get("employee_name", ""), "gaji_bersih": round(float(t.get("net") or 0), 2),
            "pph21": round(float(t.get("pph21") or 0), 2),
            "bpjs": round(float(t.get("bpjs_emp") or 0) + float(t.get("bpjs_er") or 0), 2), "status": run.get("status"),
            "proses_reguler": reg.get("number"), "status_reguler": reg.get("status")}


PREPS = [("sample_berbayar", sample_berbayar), ("gaji_susulan", gaji_susulan)]
