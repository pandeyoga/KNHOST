"""Skenario 3 — tutup periode yang belum berakhir; membalik jurnal pembalik otomatis; denda dibayar dua kali."""
import asyncio
import boot
from boot import db
from services import gl_service as gl, closing_service as cs
from core_utils import now_iso

A = "ent_a"
AKTOR = {"name": "audit", "id": "u1", "role": "admin"}

async def saldo(kode):
    led = await gl.account_ledger(kode, scope={"entity_id": A})
    return (led or {}).get("balance", 0.0)

async def main():
    await db.business_entities.insert_one({"id": A, "code": "AAA", "name": "PT A", "legal_name": "PT A", "is_active": True})
    await gl.seed_default_coa()
    hari_ini = now_iso()[:10]
    bulan_ini, bulan_depan = hari_ini[:7], "2026-12"
    print(f"hari ini (UTC): {hari_ini}")

    print("\n[FX-02] Denda 100 rb: terbit, bayar 60 rb, bayar lagi 40 rb")
    await gl.post_penalty_issue(penalty_id="pen1", entity_id=A, amount=100000, label="denda uji")
    j1 = await gl.post_penalty_payment(penalty_id="pen1", entity_id=A, amount=60000)
    j2 = await gl.post_penalty_payment(penalty_id="pen1", entity_id=A, amount=40000)
    print(f"  bayar-1 → jurnal {(j1 or {}).get('number')}; bayar-2 → jurnal {(j2 or {}).get('number')}; "
          f"saldo piutang denda 1-1270 = {await saldo('1-1270'):,.2f} (seharusnya 0)")

    print("\n[GL-01b] Membalik secara manual jurnal pembalik otomatis")
    txn = {"id": "cash_x", "number": "AAA/CASH-00009", "cash_type": "kas_besar", "direction": "out", "amount": 2e6,
           "category": "operasional", "description": "uji", "entity_id": A, "txn_date": now_iso(),
           "status": "posted", "ref_type": "", "ref_id": ""}
    await db.cash_transactions.insert_one(dict(txn))
    j = await gl.post_cash_transaction(txn)
    v = await gl.post_cash_void("cash_x", label="void uji")
    print(f"  jurnal kas {j['number']} → pembalik otomatis {v['number']} (source_type={v['source_type']}); kas = {await saldo('1-1100'):,.2f}")
    try:
        r = await gl.reverse_entry(v["id"], hari_ini, "uji balik pembalik", AKTOR)
        print(f"  pembalik otomatis DIBALIK manual oleh {r['number']}; kas = {await saldo('1-1100'):,.2f} "
              f"(dokumen kas berstatus void, tetapi buku besar kembali berkurang 2 jt)")
    except Exception as e:
        print("  ditolak:", e)

    print(f"\n[GL-04] Menutup bulan berjalan ({bulan_ini}) dan bulan depan ({bulan_depan})")
    for key in (bulan_ini, bulan_depan):
        try:
            rec = await cs.close_period("month", key, AKTOR, A, suspense_override_reason="uji audit tutup periode",
                                        can_override_suspense=True)
            print(f"  {key}: DITERIMA ({rec['start_date']}..{rec['end_date']}), laba ditutup {rec['net_income']:,.2f}")
        except Exception as e:
            print(f"  {key}: ditolak —", str(e)[:120])
    try:
        await gl._insert_entry(lines=[{"account_code": "6-2000", "debit": 1e6, "credit": 0},
                                      {"account_code": "1-1100", "debit": 0, "credit": 1e6}],
            description="jurnal otomatis hari ini", date=now_iso(), source_type="uji_audit", source_id="hari_ini",
            entity_id=A, created_by="audit")
        print("  jurnal bertanggal hari ini masih diterima")
    except Exception as e:
        print("  jurnal otomatis bertanggal HARI INI kini ditolak:", type(e).__name__)

asyncio.run(main())
