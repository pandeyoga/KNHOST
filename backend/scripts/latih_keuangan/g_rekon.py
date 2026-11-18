"""Bagian B+ · REKONSILIASI BANK LANJUTAN — data buku per peserta untuk skenario R1–R9 (lewat ENDPOINT RESMI).

Skenario memakai rekening koran **Excel (.xlsx)** yang dibuat dari kartu ini oleh
`scripts/buat_mutasi_bank_latihan.py` (satu berkas per skenario + satu berkas lengkap). Semua transaksi buku di bawah
dicatat ke **BCA Operasional KSC** dengan akun PESERTA (kecuali pesanan & tagihan yang memang dibuat peran lain):

R1 Kode bayar        — kwitansi transfer; berita transfer memuat kode bayar → cocok otomatis.
R2 Usulan            — kwitansi transfer; berita transfer hanya nama pelanggan → usulan (skor 75), ditautkan manual.
R3 Bayar pemasok     — tagihan pemasok dibayar dari BCA; berita transfer memuat nomor tagihan → cocok otomatis.
R4 Pecah (1:N)       — dua kwitansi transfer; pelanggan mengirim SATU transfer untuk keduanya.
R5 Gabung (N:1)      — satu kwitansi transfer; pelanggan mengirim DUA transfer (60 % + 40 %).
R6 Biaya & bunga     — tanpa data buku (bank memotong/menambah sendiri).
R7 Titipan           — pesanan terkirim BELUM dibayar; setoran tanpa nama dititipkan lalu dialokasikan ke pesanan ini.
R8 Lepas & R9 Impor ulang memakai data R2 & R1.

Nominal kwitansi dirancang BERBEDA per skenario dan berakhiran nomor peserta (`_nominal`): rekening BCA dipakai bersama,
dan pesanan latihan umumnya bernilai sama (produk & qty sama) — tanpa ini usulan R2 seri dengan kwitansi R4/R5 dan
pasangan "yang benar" tidak bisa dipastikan. Kwitansi di bawah total pesanan = bayar sebagian (sisa piutang tetap).

Pesanan R1/R2/R4/R5/R7 memakai PELANGGAN REKONSILIASI tersendiri ("Latihan NN · Toko Rekon Peserta NN", dibuat di sini
lewat API seperti `a_dasar:mitra`): kwitansi sebagian & pesanan titipan menyisakan piutang, dan sisa itu tidak boleh
mengubah angka piutang pelanggan latihan utama yang dipakai materi lain (F02–F06, S1–S5).

OPSIONAL: tidak ikut seed bawaan; jalankan dengan `--hanya ...,g_rekon` (lihat `seed_pelatihan_keuangan_kn.preps`).
Aman dijalankan ulang (kunci kartu yang sudah ada dilewati). Satu-satunya tulisan langsung = `lc.tag` (penanda latihan).
"""
from typing import Any, Dict

from db import db
from scripts.seed_demo_transaksi_kn import make_so, push_so

from .a_dasar import _tagihan
from .c_kas import _rekening
from .konteks import KSC, LatihCtx, Peserta

#: hanya dijalankan bila diminta lewat --hanya (seed_pelatihan_keuangan_kn.preps)
OPSIONAL = True


def pelanggan_rekon(p: Peserta) -> str:
    return f"Latihan {p.kode} · Toko Rekon Peserta {p.kode}"


async def _pelanggan(lc: LatihCtx, p: Peserta) -> str:
    """Pelanggan rekonsiliasi peserta (dibuat sekali, isian sama dengan pelanggan latihan `a_dasar:mitra`)."""
    nama = pelanggan_rekon(p)
    if not await db.customers.find_one({"name": nama}, {"_id": 1}):
        adm = await lc.admin()
        sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
        c = await adm.post("/customers", {
            "name": nama, "pic_name": f"Bu Peserta {p.kode}", "phone": f"0813778{p.no:05d}", "city": "Bandung",
            "address": f"Jl. Latihan Rekonsiliasi No. {p.no}, Bandung", "type": "Wholesale", "segment": "Wholesale",
            "credit_limit": 300_000_000, "assigned_sales_id": sales["id"], "entity_id": KSC,
            "payment_profile": {"default_method": "tempo", "term_days": 30}}, entity=KSC)
        await lc.tag("customers", c["id"], p, "pelanggan_rekon")
    return nama


async def _bca() -> Dict[str, Any]:
    bank = await _rekening("bank")
    if not bank:
        raise RuntimeError("PT Sukacita belum punya rekening bank aktif")
    return bank


async def _so_terkirim(lc: LatihCtx, p: Peserta, peran: str) -> Dict[str, Any]:
    so = await make_so(lc, "sales", await _pelanggan(lc, p), KSC, "woven", 1, 1)
    so = await push_so(lc, so, KSC, "delivered", "salesadmin", "warehouse")
    await lc.tag("sales_orders", so["id"], p, peran)
    return await lc.so(so["id"])


def _nominal(total: float, fraksi: float, p: Peserta, akhiran: int = 0) -> float:
    """`fraksi` × total pesanan dibulatkan ke ribuan, lalu + `akhiran` (bawaan nomor peserta: Rp …061 untuk peserta 61).
    1.0 = lunas."""
    if fraksi >= 1:
        return round(total, 2)
    return float(min(round(total, 2), round(total * fraksi / 1000) * 1000 + (akhiran or p.no)))


async def _kwitansi_bca(lc: LatihCtx, p: Peserta, so: Dict[str, Any], peran: str, fraksi: float = 1.0,
                        akhiran: int = 0) -> Dict[str, Any]:
    """Kwitansi transfer `so` ke BCA (penuh atau sebagian, lihat `_nominal`), dicatat akun peserta → kas masuk di BCA."""
    bank = await _bca()
    total = _nominal(float(so.get("grand_total") or 0), fraksi, p, akhiran)
    me = await lc.peserta_user(p)
    rc = await me.post("/ar-receipts", {
        "customer_id": so["customer_id"], "amount": total, "method": "transfer", "entity_id": KSC,
        "account_id": bank["id"], "reference_no": f"TRF-LTH{p.kode}-{so['number'][-5:]}",
        "notes": f"Transfer {'pelunasan' if fraksi >= 1 else 'sebagian'} {so['number']} — Latihan {p.kode}",
        "allocations": [{"order_id": so["id"], "amount": total}]}, entity=KSC)
    rc = await db.ar_receipts.find_one({"id": rc["id"]}, {"_id": 0})
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc["id"], "status": {"$ne": "void"}},
                                              {"_id": 0})
    if not kas:
        raise RuntimeError(f"Kwitansi {rc.get('number')} tidak melahirkan transaksi kas")
    await lc.tag("ar_receipts", rc["id"], p, peran)
    kode = await db.payment_codes.find_one({"order_id": so["id"], "status": {"$ne": "batal"}}, {"_id": 0, "code": 1})
    return {"so": so["number"], "so_id": so["id"], "kode_bayar": (kode or {}).get("code", ""),
            "kwitansi": rc.get("number"), "kas": kas.get("number", ""), "kas_id": kas["id"], "nominal": total,
            "tanggal": str(kas.get("txn_date") or "")[:10]}


async def kode_bayar(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """R1 — kwitansi transfer pesanan baru; berita transfer di rekening koran memuat kode bayar pesanan."""
    k = await _kwitansi_bca(lc, p, await _so_terkirim(lc, p, "rekon_kode_bayar"), "rekon_kode_bayar")
    if not k["kode_bayar"]:
        raise RuntimeError(f"Pesanan {k['so']} tidak punya kode bayar")
    return k


async def tanpa_kode(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """R2 — kwitansi transfer; berita transfer hanya menyebut nama pelanggan (tanpa kode, tanpa nomor dokumen)."""
    return await _kwitansi_bca(lc, p, await _so_terkirim(lc, p, "rekon_tanpa_kode"), "rekon_tanpa_kode", 0.9)


async def bayar_pemasok(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """R3 — tagihan pemasok peserta (PO → terima → tagihan) dibayar penuh dari BCA oleh akun peserta."""
    bank = await _bca()
    # Harga per peserta berbeda supaya nominal transfer keluar tidak kembar antarpeserta di rekening bersama.
    tg = await _tagihan(lc, p, "rekon_bayar_pemasok", 50, 13_000 + p.no * 10)
    me = await lc.peserta_user(p)
    await me.post(f"/vendor-bills/{tg['tagihan_id']}/pay", {
        "amount": tg["total"], "method": "transfer", "bank_account_id": bank["id"],
        "notes": f"Bayar {tg['tagihan']} — Latihan {p.kode}"}, entity=KSC)
    vb = await db.vendor_bills.find_one({"id": tg["tagihan_id"]}, {"_id": 0})
    pay = next((x for x in reversed(vb.get("payments") or []) if x.get("cash_txn_id")), None)
    if not pay:
        raise RuntimeError(f"Pembayaran {tg['tagihan']} tidak melahirkan transaksi kas")
    kas = await db.cash_transactions.find_one({"id": pay["cash_txn_id"]}, {"_id": 0})
    sup = await lc.supplier_of(p)
    return {"po": tg["po"], "tagihan": tg["tagihan"], "tagihan_id": tg["tagihan_id"], "faktur_supplier": tg["faktur_supplier"],
            "pemasok": sup.get("name", ""), "kas": kas.get("number", ""), "kas_id": kas["id"], "nominal": tg["total"],
            "tanggal": str(kas.get("txn_date") or "")[:10], "status": vb.get("status")}


async def pecah(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """R4 — dua pesanan, dua kwitansi transfer terpisah; di bank hanya SATU transfer sebesar jumlah keduanya.

    Akhiran kwitansi kedua = nomor peserta × 100 (…061 dan …6100 untuk peserta 61): jumlah keduanya hanya bisa dibentuk
    dari pasangan milik peserta ini — dengan akhiran sama-sama nomor peserta, kwitansi peserta 60 + 62 berjumlah persis
    sama dengan pasangan peserta 61, dan layar Pecah menawarkan kombinasi yang salah di rekening bersama."""
    a = await _kwitansi_bca(lc, p, await _so_terkirim(lc, p, "rekon_pecah"), "rekon_pecah", 0.7)
    b = await _kwitansi_bca(lc, p, await _so_terkirim(lc, p, "rekon_pecah"), "rekon_pecah", 0.45, p.no * 100)
    return {"kwitansi_1": a["kwitansi"], "kas_1": a["kas"], "kas_1_id": a["kas_id"], "nominal_1": a["nominal"],
            "kwitansi_2": b["kwitansi"], "kas_2": b["kas"], "kas_2_id": b["kas_id"], "nominal_2": b["nominal"],
            "nominal": round(a["nominal"] + b["nominal"], 2), "tanggal": a["tanggal"]}


async def gabung(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """R5 — satu kwitansi transfer; di bank DUA transfer (± 60 % dibulatkan ribuan, lalu sisanya)."""
    k = await _kwitansi_bca(lc, p, await _so_terkirim(lc, p, "rekon_gabung"), "rekon_gabung", 0.8)
    bagian_1 = float(round(k["nominal"] * 0.6 / 1000) * 1000)
    return {**k, "bagian_1": bagian_1, "bagian_2": round(k["nominal"] - bagian_1, 2)}


async def titipan(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """R7 — pesanan terkirim BELUM dibayar. Setoran tanpa nama di rekening koran dititipkan, lalu dialokasikan ke sini."""
    so = await _so_terkirim(lc, p, "rekon_titipan")
    total = round(float(so.get("grand_total") or 0), 2)
    return {"so": so["number"], "so_id": so["id"], "pelanggan": pelanggan_rekon(p), "customer_id": so["customer_id"],
            "total_pesanan": total, "nominal": _nominal(total, 0.65, p)}   # nominal setoran = dialokasikan ke pesanan


PREPS = [("kode_bayar", kode_bayar), ("tanpa_kode", tanpa_kode), ("bayar_pemasok", bayar_pemasok),
         ("pecah", pecah), ("gabung", gabung), ("titipan", titipan)]
