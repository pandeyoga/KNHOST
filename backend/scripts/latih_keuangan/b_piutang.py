"""Bagian A · PIUTANG — data awal skenario F05–F06 per peserta (lewat ENDPOINT RESMI), plus satu prep SUSULAN untuk F04.

F05 Rencana & Denda — pelanggan KEDUA peserta ("Latihan NN · Toko Kain Cicilan NN", supaya tidak mengganggu alokasi
                      "Tertua dulu" pelanggan utama di F04) dengan satu SO terkirim yang dicicil dua kali. Rencana
                      cicilannya disusun Admin Penjualan (izin `payment_plan.create`; Finance hanya melihat & mengubah):
                      Cicilan 1 (50 %) jatuh tempo 20 hari lalu — BELUM dibayar → telat, bahan nota denda;
                      Cicilan 2 (sisanya) jatuh tempo 10 hari lagi. Tanggal lampau memang boleh untuk rencana buatan
                      orang (kesepakatan lama yang baru dicatat) — TIDAK ada tulisan langsung ke database.
F06 Kredit & Plafon — Sales (pemegang pelanggan utama) mengajukan izin kredit Rp 50.000.000 berlingkup pelanggan; masuk
                      antrean "Menunggu keputusan" bersama pengajuan profil kredit saat pelanggan dibuat. Peserta
                      (Finance) hanya membaca; Manajer yang memutus.

SUSULAN (bukan PREPS — dijalankan PELATIH sesudah peserta menyelesaikan F04 langkah 1–5, karena pesanan baru yang sudah
ada lebih awal akan menyerap kelebihan bayar F04 lewat alokasi "Tertua dulu"):

    cd backend && python -m scripts.latih_keuangan.b_piutang --berikut 1-6      # peserta 01–06
    cd backend && python -m scripts.latih_keuangan.b_piutang --berikut 2        # satu peserta

→ SO terkirim baru untuk pelanggan utama peserta (kunci kartu `b_piutang:so_berikut`), dipakai F04 langkah 6–7
("Pakai titipan"). Peserta yang belum punya titipan dilewati dengan pesan.

Satu-satunya tulisan langsung = `lc.tag` (penanda latihan, tidak mengubah angka). Aman di VPS: tanpa id lokal.
"""
from pathlib import Path
from typing import Any, Dict, List

try:   # dijalankan langsung (`python -m …b_piutang --berikut`): muat backend/.env SEBELUM `db` diimpor (tidak menimpa)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass

from db import db  # noqa: E402
from scripts.seed_demo_transaksi_kn import days, make_so, push_so

from .konteks import KSC, PREFIX, LatihCtx, Peserta

#: F05 — Cicilan 1 jatuh tempo sekian hari LALU (telat), Cicilan 2 sekian hari LAGI.
TELAT_HARI = 20
SISA_HARI = 10
#: F06 — nominal izin kredit yang diajukan sales.
IZIN_NOMINAL = 50_000_000


def nama_cicilan(p: Peserta) -> str:
    return f"{PREFIX} {p.kode} · Toko Kain Cicilan {p.kode}"


async def _pelanggan_cicilan(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    nama = nama_cicilan(p)
    c = await db.customers.find_one({"name": nama}, {"_id": 0})
    if c:
        return c
    adm = await lc.admin()
    sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    c = await adm.post("/customers", {
        "name": nama, "pic_name": f"Pak Cicilan {p.kode}", "phone": f"0813888{p.no:05d}", "city": "Bandung",
        "address": f"Jl. Latihan Cicilan No. {p.no}, Bandung", "type": "Wholesale", "segment": "Wholesale",
        "credit_limit": 300_000_000, "assigned_sales_id": sales["id"], "entity_id": KSC,
        "payment_profile": {"default_method": "tempo", "term_days": 30}}, entity=KSC)
    await lc.tag("customers", c["id"], p, "pelanggan_cicilan")
    return await db.customers.find_one({"id": c["id"]}, {"_id": 0})


async def cicilan(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F05 — SO terkirim pelanggan kedua + rencana 2× cicilan (Admin Penjualan); cicilan 1 sudah telat 20 hari."""
    cust = await _pelanggan_cicilan(lc, p)
    so = await make_so(lc, "sales", cust["name"], KSC, "woven", 1, 1)
    so = await push_so(lc, so, KSC, "delivered", "salesadmin", "warehouse")
    await lc.tag("sales_orders", so["id"], p, "so_cicilan")
    so = await lc.so(so["id"])
    total = round(float(so.get("grand_total") or 0), 2)
    satu = round(total / 2)                      # cicilan bulat rupiah; sisa (termasuk ,5) di cicilan 2
    dua = round(total - satu, 2)
    sa = await lc.u("salesadmin")
    plan = await sa.post("/payment-plans", {
        "doc_type": "sales_order", "doc_id": so["id"], "mode": "custom",
        "note": f"Kesepakatan cicilan pelanggan latihan {p.kode}: 2× bayar",
        "lines": [
            {"kind": "installment", "label": "Cicilan 1 (50%)", "basis": "amount", "amount": satu,
             "due_rule": "fixed_date", "due_date": days(-TELAT_HARI)},
            {"kind": "installment", "label": "Cicilan 2 (pelunasan)", "basis": "amount", "amount": dua,
             "due_rule": "fixed_date", "due_date": days(SISA_HARI)}]}, entity=KSC)
    await lc.tag("payment_plans", plan["id"], p, "rencana_cicilan")
    return {"pelanggan": cust["name"], "pelanggan_id": cust["id"], "so": so.get("number"), "so_id": so["id"],
            "total": total, "rencana": plan.get("number"), "rencana_id": plan["id"],
            "cicilan_1": satu, "jatuh_tempo_1": days(-TELAT_HARI), "cicilan_2": dua, "jatuh_tempo_2": days(SISA_HARI)}


async def izin_kredit(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F06 — Sales mengajukan izin kredit Rp 50 jt (lingkup pelanggan) untuk pelanggan utama peserta."""
    cust = await lc.customer_of(p)
    ada = await db.credit_overrides.find_one({"customer_id": cust["id"], "status": "pending"}, {"_id": 0})
    if not ada:
        sales = await lc.u("sales")
        ada = await sales.post(f"/customers/{cust['id']}/credit-override", {
            "customer_id": cust["id"], "amount": IZIN_NOMINAL, "scope": "pelanggan", "reason_code": "cr_riwayat_baik",
            "reason": f"Latihan {p.kode}: pelanggan minta tambahan plafon sementara untuk pesanan musim ramai",
            "entity_id": KSC}, entity=KSC)
        await lc.tag("credit_overrides", ada["id"], p, "izin_kredit")
    return {"pelanggan": cust["name"], "izin_id": ada["id"], "nominal": float(ada.get("amount") or IZIN_NOMINAL),
            "lingkup": ada.get("scope", "pelanggan"), "status": ada.get("status", "pending"),
            "pengaju": ada.get("requested_by_name") or ada.get("requested_by") or "sales"}


PREPS = [("cicilan", cicilan), ("izin_kredit", izin_kredit)]


# ── SUSULAN F04 (dijalankan pelatih, lihat kepala modul) ─────────────────────────────────────────────────────────────
async def so_berikut(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F04 langkah 6–7 — tagihan BERIKUTNYA pelanggan utama (SO terkirim baru) untuk dibayar dengan titipan."""
    from .a_dasar import _so_terkirim
    cust = await lc.customer_of(p)
    titipan = round(float((cust or {}).get("deposit_balance") or 0), 2)
    if titipan <= 0.01:
        raise RuntimeError(f"peserta {p.kode} belum punya titipan (F04 langkah 1–5 belum selesai) — dilewati")
    out = await _so_terkirim(lc, p, "so_berikut", "woven")
    return {**out, "titipan_saat_dibuat": titipan}


def _nomor(teks: str) -> List[int]:
    out: List[int] = []
    for bagian in teks.split(","):
        bagian = bagian.strip()
        if "-" in bagian:
            a, b = bagian.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        elif bagian:
            out.append(int(bagian))
    return out


async def _susulan(nomor: List[int]) -> int:
    from core_utils import now_iso
    from scripts.demo_api import Api
    cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
    api = Api()
    lc = LatihCtx(api, cst)
    gagal = 0
    try:
        for no in nomor:
            p = Peserta(no)
            state = (await db.migrations.find_one({"id": "pelatihan_keuangan"}, {"_id": 0}) or {}).get("peserta", {})
            if "b_piutang:so_berikut" in state.get(p.kode, {}):
                print(f"— Peserta {p.kode}: so_berikut sudah ada {state[p.kode]['b_piutang:so_berikut'].get('so')}")
                continue
            try:
                res = await so_berikut(lc, p)
            except Exception as e:  # noqa: BLE001
                gagal += 1
                print(f"— Peserta {p.kode}: ✗ {e}")
                continue
            await db.migrations.update_one({"id": "pelatihan_keuangan"}, {"$set": {
                f"peserta.{p.kode}.b_piutang:so_berikut": res, "updated_at": now_iso()}}, upsert=True)
            print(f"— Peserta {p.kode}: ✓ so_berikut {res['so']} total {res['total']} (titipan {res['titipan_saat_dibuat']})")
    finally:
        import asyncio
        await asyncio.sleep(1)
        await api.close()
    return gagal


if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    ap = argparse.ArgumentParser(description="Susulan F04: tagihan berikutnya untuk dibayar dengan titipan.")
    ap.add_argument("--berikut", required=True, help="nomor peserta, mis. 2 · 1-6 · 1,3,5")
    a = ap.parse_args()
    sys.exit(1 if asyncio.run(_susulan(_nomor(a.berikut))) else 0)
