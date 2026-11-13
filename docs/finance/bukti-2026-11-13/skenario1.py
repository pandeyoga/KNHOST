"""Skenario 1 — laporan inti di atas jurnal contoh; bandingkan dengan hitungan tangan."""
import asyncio, json
import boot
from boot import db
from services import gl_service as gl, financial_statement_service as fs, closing_service as cs

A, B = "ent_a", "ent_b"
hasil = []
def cek(nama, dapat, harap):
    ok = abs(float(dapat) - float(harap)) < 0.005
    hasil.append(ok)
    print(f"  {'OK  ' if ok else 'BEDA'} {nama}: laporan={dapat:,.2f} hitung-tangan={harap:,.2f}")

async def je(ent, tgl, baris, ket, sid):
    return await gl._insert_entry(lines=[{"account_code": c, "debit": d, "credit": k} for c, d, k in baris],
        description=ket, date=tgl, source_type="uji_audit", source_id=sid, entity_id=ent, created_by="audit")

async def main():
    await db.business_entities.insert_many([
        {"id": A, "code": "AAA", "name": "PT A", "legal_name": "PT A", "is_active": True},
        {"id": B, "code": "BBB", "name": "PT B", "legal_name": "PT B", "is_active": True}])
    await gl.seed_default_coa()
    # ── PT A, Oktober 2026
    await je(A, "2026-10-01", [("1-1100", 100e6, 0), ("3-1000", 0, 100e6)], "Setor modal", "a1")
    await je(A, "2026-10-05", [("1-1300", 60e6, 0), ("2-1100", 0, 60e6)], "Beli persediaan kredit", "a2")
    await je(A, "2026-10-10", [("1-1200", 55.5e6, 0), ("4-1000", 0, 50e6), ("2-1200", 0, 5.5e6)], "Jual kredit + PPN", "a3")
    await je(A, "2026-10-10", [("5-1000", 30e6, 0), ("1-1300", 0, 30e6)], "HPP", "a4")
    await je(A, "2026-10-20", [("6-2000", 4e6, 0), ("1-1100", 0, 4e6)], "Sewa tunai", "a5")
    await je(A, "2026-10-25", [("1-1100", 20e6, 0), ("1-1200", 0, 20e6)], "Terima piutang", "a6")
    # jual antar-PT A→B (20 jt + PPN 2,2 jt; HPP 12 jt)
    await je(A, "2026-10-15", [("1-1250", 22.2e6, 0), ("4-1000", 0, 20e6), ("2-1200", 0, 2.2e6)], "Jual antar-PT", "a7")
    await je(A, "2026-10-15", [("5-1000", 12e6, 0), ("1-1300", 0, 12e6)], "HPP antar-PT", "a8")
    await je(B, "2026-10-15", [("1-1300", 20e6, 0), ("1-1500", 2.2e6, 0), ("2-1250", 0, 22.2e6)], "Beli antar-PT", "b1")
    # kejadian 1 Nov 00:30 WIB = 31 Okt 17:30 UTC (stempel now_iso() berbentuk UTC)
    await je(A, "2026-10-31T17:30:00+00:00", [("6-3000", 1e6, 0), ("1-1100", 0, 1e6)], "Utilitas (1 Nov 00:30 WIB)", "a9")
    # ── November
    await je(A, "2026-11-03", [("1-1100", 10e6, 0), ("4-1000", 0, 10e6)], "Jual tunai Nov", "a10")
    await je(A, "2026-11-03", [("5-1000", 6e6, 0), ("1-1300", 0, 6e6)], "HPP Nov", "a11")

    sa = {"entity_id": A}
    print("\n[1] Laba-Rugi PT A Oktober (2026-10-01..2026-10-31)")
    pl = await fs.income_statement("2026-10-01", "2026-10-31", sa)
    cek("Pendapatan", pl["revenue_total"], 70e6)
    cek("HPP", pl["cogs_total"], 42e6)
    cek("Laba kotor", pl["gross_profit"], 28e6)
    cek("Beban operasional (sewa saja bila ikut tanggal WIB)", pl["opex_total"], 4e6)
    cek("Laba bersih (bila ikut tanggal WIB)", pl["net_income"], 24e6)

    print("\n[2] Neraca PT A per 2026-10-31 (hitung tangan memakai tanggal seperti tersimpan)")
    bs = await fs.balance_sheet("2026-10-31", scope=sa)
    cek("Total aset", bs["assets_total"], 115e6 + 35.5e6 + 22.2e6 + 18e6)
    cek("Total kewajiban", bs["liabilities_total"], 60e6 + 7.7e6)
    cek("Ekuitas (modal + laba berjalan)", bs["equity_total"], 100e6 + 23e6)
    print("     seimbang menurut laporan:", bs["balanced"])

    print("\n[3] Neraca saldo PT A per 2026-10-31")
    tb = await gl.trial_balance("2026-10-31", sa)
    cek("Total saldo debit", tb["total_debit"], 115e6 + 35.5e6 + 22.2e6 + 18e6 + 42e6 + 4e6 + 1e6)
    cek("Total saldo kredit", tb["total_credit"], 60e6 + 7.7e6 + 100e6 + 70e6)

    print("\n[4] Buku besar Kas PT A per 2026-10-31")
    led = await gl.account_ledger("1-1100", "2026-10-31", sa)
    cek("Saldo kas", led["balance"], 115e6)

    print("\n[5] Mode gabungan (tanpa filter entitas) — Laba-Rugi Oktober")
    plall = await fs.income_statement("2026-10-01", "2026-10-31", {})
    cek("Pendapatan gabungan vs konsolidasi sebenarnya (penjualan ke luar saja)", plall["revenue_total"], 50e6)
    bsall = await fs.balance_sheet("2026-10-31", scope={})
    cek("Persediaan+aset gabungan vs konsolidasi (tanpa piutang antar-PT & laba dalam stok 8 jt)",
        bsall["assets_total"], (115e6 + 35.5e6 + 18e6) + (20e6 - 8e6) + 2.2e6)

    print("\n[6] Tutup buku Oktober PT A, lalu laporan yang sama")
    rec = await cs.close_period("month", "2026-10", {"name": "audit", "id": "u1", "role": "admin"}, A)
    print("     laba bersih yang ditutup:", f"{rec['net_income']:,.2f}", "| jurnal penutup:", rec["journal_entry_number"])
    pl2 = await fs.income_statement("2026-10-01", "2026-10-31", sa)
    cek("Laba-Rugi Oktober tidak berubah setelah ditutup", pl2["net_income"], pl["net_income"])
    bs2 = await fs.balance_sheet("2026-10-31", scope=sa)
    cek("Ekuitas total tetap", bs2["equity_total"], bs["equity_total"])
    cek("Laba berjalan menjadi 0 setelah ditutup", bs2["equity"]["current_earnings"], 0)
    re_ = next((l["amount"] for l in bs2["equity"]["lines"] if l["code"] == "3-2000"), 0)
    cek("Laba ditahan = laba Oktober", re_, pl["net_income"])
    print("     neraca seimbang:", bs2["balanced"])
    try:
        await je(A, "2026-10-28", [("6-2000", 1e6, 0), ("1-1100", 0, 1e6)], "Mundur ke periode tertutup", "a12")
        print("  BEDA jurnal mundur ke Oktober DITERIMA"); hasil.append(False)
    except Exception as e:
        print("  OK   jurnal mundur ke Oktober ditolak:", type(e).__name__); hasil.append(True)

    print("\n[7] Laba-Rugi Jan–Nov PT A (melewati jurnal penutup)")
    ply = await fs.income_statement("2026-01-01", "2026-11-30", sa)
    cek("Laba bersih kumulatif = Okt + Nov", ply["net_income"], pl["net_income"] + 4e6)
    bs3 = await fs.balance_sheet("2026-11-30", scope=sa)
    print("     neraca 30 Nov seimbang:", bs3["balanced"], "| ekuitas:", f"{bs3['equity_total']:,.2f}")
    print(f"\nRINGKAS: {sum(hasil)} cocok, {len(hasil) - sum(hasil)} berbeda dari hitungan tangan")

asyncio.run(main())
