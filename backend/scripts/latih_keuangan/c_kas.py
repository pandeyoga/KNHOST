"""Bagian B · KAS & BANK — data awal skenario F07–F10 per peserta (lewat ENDPOINT RESMI).

F07 Kas Kecil      — pengajuan dana (PD) karyawan yang SUDAH disetujui berjenjang (atasan → pimpinan → keuangan),
                     siap dicairkan peserta dari Kas Toko, lalu dipertanggungjawabkan (LPJ) dan sisanya diterima kembali.
F08 Titipan Sales  — PT Sukacita memakai mode "titipan" untuk tunai yang diterima sales; sales menagih tunai pesanan baru
                     milik pelanggan peserta (kwitansi → titipan di tangan sales) lalu mengajukan setoran ke kasir.
                     Peserta (Finance) menerima setoran itu ke Kas Toko.
F10 Rekonsiliasi   — penerimaan transfer pelanggan peserta ke BCA Operasional KSC (dicatat dengan akun peserta sendiri),
                     bahan mutasi bank yang dicocokkan otomatis. Baris mutasi lain berasal dari transaksi peserta di F09.

Semua lewat endpoint resmi (`lc.u`, `lc.admin`, `lc.peserta_user`). Satu-satunya tulisan langsung = `lc.tag` (penanda
latihan, tidak mengubah angka). Aman di VPS: rekening dicari dari data (bukan id lokal).
"""
from typing import Any, Dict

from db import db
from scripts.seed_demo_transaksi_kn import make_so, push_so

from .konteks import KSC, LatihCtx, Peserta

#: Mode tunai sales PT Sukacita untuk latihan F08 (Pusat Pengaturan › Uang masuk › Kwitansi).
MODE_TITIPAN = "titipan"
#: F07 — nominal PD (satu baris uang jalan) — sama untuk semua peserta.
PD_NOMINAL = 500_000


async def _rekening(jenis: str) -> Dict[str, Any]:
    """Rekening aktif PT Sukacita: `bank` (BCA Operasional KSC) atau `cash` (Kas Toko KSC) — dari data, bukan id tetap."""
    return await db.bank_accounts.find_one({"entity_id": KSC, "account_type": jenis, "is_active": {"$ne": False}},
                                           {"_id": 0}, sort=[("created_at", 1)])


async def pd_kas_kecil(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F07 — PD karyawan (akun sales@, divisi Penjualan) disetujui atasan (manajer), pimpinan & keuangan (admin).

    Peserta mencairkannya (Kas Toko), membuat LPJ + bukti, lalu menerima kembali sisanya."""
    sales, mgr, adm = await lc.u("sales"), await lc.u("manager"), await lc.admin()
    ca = await sales.post("/cash-advances", {
        "entity_id": KSC, "divisi": "Penjualan", "kegiatan": f"Latihan {p.kode} · Kunjungan {p.pelanggan.split('· ')[-1]}",
        "tanggal_pengajuan": "", "payment_method": "cash", "account_label": "Kas Toko",
        "lines": [{"description": "Uang jalan kunjungan pelanggan (bensin, tol, parkir, fotokopi katalog)",
                   "qty": 1, "satuan": "paket", "unit_price": PD_NOMINAL, "catatan": ""}],
        "catatan": f"Data latihan keuangan peserta {p.kode}"}, entity=KSC)
    await sales.post(f"/cash-advances/{ca['id']}/submit", {}, entity=KSC)
    # Jenjang dari Aturan Persetujuan (bawaan: Atasan = manajer/admin · Pimpinan = admin · Keuangan = admin).
    for who in (mgr, adm, adm):
        cur = await db.cash_advances.find_one({"id": ca["id"]}, {"_id": 0, "status": 1})
        if cur.get("status") == "approved":
            break
        await who.post(f"/cash-advances/{ca['id']}/approve", {"note": "Disetujui (data latihan)"}, entity=KSC)
    ca = await db.cash_advances.find_one({"id": ca["id"]}, {"_id": 0})
    if ca.get("status") != "approved":
        raise RuntimeError(f"PD {ca.get('number')} belum disetujui penuh (status {ca.get('status')})")
    await lc.tag("cash_advances", ca["id"], p, "pd_kas_kecil")
    return {"pd": ca["number"], "pd_id": ca["id"], "nominal": round(float(ca.get("total_amount") or 0), 2),
            "pemohon": ca.get("created_by", ""), "status": ca["status"]}


async def _mode_titipan(lc: LatihCtx) -> None:
    """Nyalakan mode "titipan" untuk PT Sukacita (lapisan PT) bila belum — sekali untuk semua peserta.

    Hanya berlaku bagi pencatat kwitansi TANPA izin `cash.create` (sales); Finance tetap kas langsung."""
    from services.config_resolver import value_of
    if str(await value_of("pembayaran.sales_terima_tunai", {"entity_id": KSC}) or "") == MODE_TITIPAN:
        return
    adm = await lc.admin()
    await adm.put("/config/values", {"items": [{
        "key": "pembayaran.sales_terima_tunai", "value": MODE_TITIPAN, "scope_type": "entity", "scope_id": KSC,
        "reason": "Pelatihan keuangan 18 Nov 2026 — skenario F08 Titipan Sales (tunai sales disetor ke kasir)"}]},
        entity=KSC)


async def _so_baru(lc: LatihCtx, p: Peserta, peran: str) -> Dict[str, Any]:
    so = await make_so(lc, "sales", p.pelanggan, KSC, "woven", 1, 1)
    so = await push_so(lc, so, KSC, "delivered", "salesadmin", "warehouse")
    await lc.tag("sales_orders", so["id"], p, peran)
    return await lc.so(so["id"])


async def titipan_sales(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F08 — pesanan baru terkirim; sales menagih TUNAI penuh (kwitansi → titipan di tangan sales) lalu menyetor."""
    await _mode_titipan(lc)
    so = await _so_baru(lc, p, "titipan_sales")
    total = round(float(so.get("grand_total") or 0), 2)
    sales = await lc.u("sales")
    rc = await sales.post("/ar-receipts", {
        "customer_id": so["customer_id"], "amount": total, "method": "cash", "entity_id": KSC,
        "notes": f"Tagih tunai di toko — Latihan {p.kode}", "allocations": [{"order_id": so["id"], "amount": total}]},
        entity=KSC)
    rc = await db.ar_receipts.find_one({"id": rc["id"]}, {"_id": 0})
    hold = await db.cash_holdings.find_one({"receipt_id": rc["id"]}, {"_id": 0})
    if not hold:
        raise RuntimeError(f"Kwitansi {rc.get('number')} tidak menjadi titipan — mode tunai PT Sukacita bukan 'titipan'?")
    dep = await sales.post("/cash-deposits", {
        "amount": total, "holding_ids": [hold["id"]],
        "note": f"Setoran tunai Latihan {p.kode} · Toko Kain Peserta {p.kode}"}, entity=KSC)
    for coll, did in (("ar_receipts", rc["id"]), ("cash_holdings", hold["id"]), ("cash_deposits", dep["id"])):
        await lc.tag(coll, did, p, "titipan_sales")
    return {"so": so["number"], "so_id": so["id"], "kwitansi": rc.get("number"), "titipan": hold.get("number"),
            "titipan_id": hold["id"], "setoran": dep.get("number"), "setoran_id": dep["id"], "nominal": total,
            "penyetor": dep.get("holder_name", "")}


async def kwitansi_transfer(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F10 — pelanggan peserta mentransfer pelunasan pesanan baru ke BCA; kwitansinya dicatat dengan akun PESERTA."""
    bank = await _rekening("bank")
    if not bank:
        raise RuntimeError("PT Sukacita belum punya rekening bank aktif")
    so = await _so_baru(lc, p, "kwitansi_transfer")
    total = round(float(so.get("grand_total") or 0), 2)
    me = await lc.peserta_user(p)
    rc = await me.post("/ar-receipts", {
        "customer_id": so["customer_id"], "amount": total, "method": "transfer", "entity_id": KSC,
        "account_id": bank["id"], "reference_no": f"TRF-LTH{p.kode}-{so['number'][-5:]}",
        "notes": f"Transfer pelunasan {so['number']} — Latihan {p.kode}",
        "allocations": [{"order_id": so["id"], "amount": total}]}, entity=KSC)
    rc = await db.ar_receipts.find_one({"id": rc["id"]}, {"_id": 0})
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc["id"], "status": {"$ne": "void"}},
                                              {"_id": 0})
    await lc.tag("ar_receipts", rc["id"], p, "kwitansi_transfer")
    kode = await db.payment_codes.find_one({"order_id": so["id"], "status": {"$ne": "batal"}}, {"_id": 0, "code": 1})
    return {"so": so["number"], "so_id": so["id"], "kode_bayar": (kode or {}).get("code", ""),
            "kwitansi": rc.get("number"), "kas": (kas or {}).get("number", ""),
            "kas_id": (kas or {}).get("id", ""), "nominal": total, "rekening": bank.get("name", ""),
            "tanggal": str((kas or {}).get("txn_date") or "")[:10]}


PREPS = [("pd_kas_kecil", pd_kas_kecil), ("titipan_sales", titipan_sales), ("kwitansi_transfer", kwitansi_transfer)]
