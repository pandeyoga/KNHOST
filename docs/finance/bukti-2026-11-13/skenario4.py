"""Skenario 4 — Arus Kas dan Perubahan Ekuitas vs hitungan tangan (RP-06)."""
import asyncio
import boot
from boot import db
from services import gl_service as gl, financial_statement_service as fs
from services import cash_flow_service as cf, equity_statement_service as eq

A = "ent_a"

async def je(tgl, baris, ket, sid, st="uji_audit"):
    return await gl._insert_entry(lines=[{"account_code": c, "debit": d, "credit": k} for c, d, k in baris],
        description=ket, date=tgl, source_type=st, source_id=sid, entity_id=A, created_by="audit")

def seksi(r):
    return {k: r[k]["total"] for k in ("operating", "investing", "financing") if k in r}

async def main():
    await db.business_entities.insert_one({"id": A, "code": "AAA", "name": "PT A", "legal_name": "PT A", "is_active": True})
    await gl.seed_default_coa()
    await je("2026-09-30", [("1-1100", 1000, 0), ("3-1000", 0, 1000)], "Setor modal (sebelum periode)", "m1")
    await je("2026-09-30", [("1-2100", 100, 0), ("1-1100", 0, 100)], "Beli mesin 100 (sebelum periode)", "m2")
    await je("2026-09-30", [("6-6000", 20, 0), ("1-2900", 0, 20)], "Akumulasi susut 20 (sebelum periode)", "m3")
    # Oktober
    await je("2026-10-05", [("1-1100", 300, 0), ("4-1000", 0, 300)], "Jual tunai 300", "o1")
    await je("2026-10-06", [("6-2000", 50, 0), ("1-1100", 0, 50)], "Sewa tunai 50", "o2")
    await je("2026-10-10", [("1-1100", 130, 0), ("1-2900", 20, 0), ("1-2100", 0, 100), ("4-9100", 0, 50)],
             "Jual mesin: kas 130, nilai buku 80, laba 50", "o3")
    await je("2026-10-12", [("1-1100", 500, 0), ("2-1250", 0, 500)], "Terima pinjaman dari PT lain 500", "o4")
    await je("2026-10-15", [("1-1100", 200, 0), ("3-2900", 0, 200)], "Saldo awal rekening baru 200", "o5")
    sa = {"entity_id": A}
    r = await cf.cash_flow_statement("2026-10-01", "2026-10-31", sa)
    s = seksi(r)
    print("Arus kas Oktober menurut laporan :", {k: round(v, 2) for k, v in s.items() if v is not None})
    print(f"  kas awal {r['begin_cash']:,.2f} + perubahan {r['net_change']:,.2f} = kas akhir {r['end_cash']:,.2f}"
          f" | kas akhir buku besar {r['end_cash_actual']:,.2f} | cocok: {r['reconciled']}")
    print("Hitungan tangan (klasifikasi baku): operasi +250 (jual 300 − sewa 50); investasi +130 (hasil jual mesin);"
          " pendanaan +500 (pinjaman); saldo awal rekening 200 = bagian kas awal, bukan arus periode")
    led = await gl.account_ledger("1-1100", "2026-10-31", sa)
    print(f"Saldo kas buku besar 31 Okt: {led['balance']:,.2f} (900 awal + 300 − 50 + 130 + 500 + 200 = 1.980)")
    e = await eq.equity_statement("2026-10-01", "2026-10-31", sa)
    bs = await fs.balance_sheet("2026-10-31", scope=sa)
    print(f"Perubahan ekuitas: awal {e['begin_total']:,.2f} + mutasi {e['movement_total']:,.2f} = akhir {e['end_total']:,.2f}"
          f" | ekuitas di neraca {bs['equity_total']:,.2f} | laba periode {e['net_income']:,.2f}")

asyncio.run(main())
