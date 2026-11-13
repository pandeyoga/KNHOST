"""Skenario 2 — mereproduksi temuan audit pada database tiruan (kode KNHOST apa adanya)."""
import asyncio, traceback
import boot
from boot import db
from services import gl_service as gl, financial_statement_service as fs, closing_service as cs
from schemas_finance import JournalEntryCreate

A, B = "ent_a", "ent_b"
AKTOR = {"name": "audit", "id": "u1", "role": "admin"}

async def saldo(kode, ent):
    led = await gl.account_ledger(kode, scope={"entity_id": ent})
    return (led or {}).get("balance", 0.0)

async def main():
    await db.business_entities.insert_many([
        {"id": A, "code": "AAA", "name": "PT A", "legal_name": "PT A", "is_active": True},
        {"id": B, "code": "BBB", "name": "PT B", "legal_name": "PT B", "is_active": True}])
    await gl.seed_default_coa()

    print("\n[GL-07] Jurnal manual selisih 1 sen")
    try:
        p = JournalEntryCreate(date="2026-11-05", description="uji 1 sen", lines=[
            {"account_code": "6-2000", "debit": 1000.01, "credit": 0},
            {"account_code": "1-1100", "debit": 0, "credit": 1000.00}])
        j = await gl.create_manual_entry(p, AKTOR, entity_id=A)
        tb = await gl.trial_balance(scope={"entity_id": A})
        print(f"  DITERIMA {j['number']}: total debit {j['total_debit']:.2f} ≠ kredit {j['total_credit']:.2f}; "
              f"neraca saldo debit {tb['total_debit']:.2f} kredit {tb['total_credit']:.2f} → 'balanced'={tb['balanced']}")
    except Exception as e:
        print("  ditolak:", e)

    print("\n[IC-05] Jurnal manual: konteks PT A, isi permintaan menyebut PT B")
    p = JournalEntryCreate(date="2026-11-05", description="uji entitas", entity_id=B, lines=[
        {"account_code": "6-2000", "debit": 500000, "credit": 0},
        {"account_code": "1-1100", "debit": 0, "credit": 500000}])
    j = await gl.create_manual_entry(p, AKTOR, entity_id=A)
    print(f"  jurnal {j['number']} tersimpan di entitas: {j['entity_id']} (konteks pemanggil: {A})")

    print("\n[GL-01] Kas masuk 10 jt → dibalik manual → kasnya di-void dari dokumen")
    txn = {"id": "cash_uji1", "number": "AAA/CASH-00001", "cash_type": "kas_besar", "direction": "in",
           "amount": 10e6, "category": "penjualan", "description": "uji", "entity_id": A,
           "txn_date": "2026-11-06T03:00:00+00:00", "status": "posted", "ref_type": "", "ref_id": ""}
    await db.cash_transactions.insert_one(dict(txn))
    je1 = await gl.post_cash_transaction(txn)
    print(f"  jurnal kas {je1['number']}; saldo kas 1-1100 = {await saldo('1-1100', A):,.2f}")
    kas0 = await saldo("1-1100", A) - 10e6
    rev = await gl.reverse_entry(je1["id"], "2026-11-07", "uji pembalikan manual", AKTOR)
    print(f"  dibalik manual oleh {rev['number']}; saldo kas = {await saldo('1-1100', A):,.2f}")
    v = await gl.post_cash_void("cash_uji1", label="void uji")
    print(f"  void dokumen → jurnal pembalik kedua: {(v or {}).get('number')}; saldo kas = {await saldo('1-1100', A):,.2f} "
          f"(seharusnya kembali ke {kas0:,.2f})")
    try:
        r2 = await gl.reverse_entry(v["id"], "2026-11-08", "membalik jurnal pembalik otomatis", AKTOR)
        print(f"  jurnal pembalik otomatis ({v['source_type']}) juga BISA dibalik manual: {r2['number']}")
    except Exception as e:
        print("  membalik jurnal pembalik otomatis ditolak:", e)

    print("\n[IC-01] Jurnal antar-PT: akun utang antar-PT (2-1250) nonaktif di PT B")
    from services import interco_service as ics
    base = {"pair_id": "pair1", "status": "confirmed", "seller_entity_id": A, "buyer_entity_id": B,
            "subtotal": 20e6, "tax_amount": 2.2e6, "grand_total": 22.2e6, "confirmed_at": "2026-11-06T04:00:00+00:00",
            "seller_entity_name": "PT A", "buyer_entity_name": "PT B", "items": []}
    await db.interco_transactions.insert_many([
        {**base, "id": "ict_s", "role": "seller", "entity_id": A, "number": "AAA/IC-00001"},
        {**base, "id": "ict_b", "role": "buyer", "entity_id": B, "number": "BBB/IC-00001"}])
    await db.gl_accounts.insert_one({"id": "gla_ovr", "code": "2-1250", "name": "Utang Antar-Perusahaan (IC-AP)",
        "type": "liability", "normal_balance": "credit", "parent_code": "2-1000", "is_postable": True,
        "is_active": False, "entity_id": B})
    try:
        await ics._post_gl_for_pair("pair1", "audit")
        print("  kedua jurnal terbit")
    except Exception as e:
        print("  gagal di tengah:", type(e).__name__, "-", str(e)[:70])
    async def sisi():
        return sorted([x["source_id"].split(":")[1] async for x in db.journal_entries.find(
            {"source_type": "interco_transaction", "status": {"$ne": "void"}}, {"_id": 0, "source_id": 1})])
    print("  jurnal yang ada:", await sisi(), f"| piutang antar-PT di A = {await saldo('1-1250', A):,.2f}"
          f" | utang antar-PT di B = {await saldo('2-1250', B):,.2f}")
    await db.gl_accounts.update_one({"id": "gla_ovr"}, {"$set": {"is_active": True}})   # penyebab diperbaiki
    await ics._post_gl_for_pair("pair1", "audit")                                          # diulang
    print("  setelah akun diaktifkan lagi dan posting diulang:", await sisi(),
          f"| utang antar-PT di B = {await saldo('2-1250', B):,.2f}")

    print("\n[GL-04] Menutup periode yang belum berakhir (2026-12)")
    try:
        rec = await cs.close_period("month", "2026-12", AKTOR, A)
        print(f"  DITERIMA: status {rec['status']}, periode {rec['start_date']}..{rec['end_date']}")
        try:
            await gl._insert_entry(lines=[{"account_code": "6-2000", "debit": 1e6, "credit": 0},
                                          {"account_code": "1-1100", "debit": 0, "credit": 1e6}],
                description="operasional 5 Des", date="2026-12-05T02:00:00+00:00", source_type="uji_audit",
                source_id="des1", entity_id=A, created_by="audit")
            print("  jurnal operasional Desember diterima")
        except Exception as e:
            print("  jurnal operasional bertanggal Desember kini ditolak:", type(e).__name__)
    except Exception as e:
        print("  ditolak:", e)

    print("\n[IV-01] Landed cost 3 jt untuk PO berisi 2 roll: satu sudah terjual, satu masih di gudang")
    from services import landed_cost_service as lcs
    from services.roll_service import roll_value_cents
    roll = lambda i, st, rem: {"id": i, "roll_no": i, "product_id": "p1", "status": st, "owner_entity_id": A,
        "entity_id": A, "length_initial": 100.0, "length_remaining": rem, "unit_cost": 10000.0,
        "base_unit_cost": 10000.0, "acquired": {"ref_id": "po1", "ref_type": "purchase_order"}}
    await db.inventory_rolls.insert_many([roll("r_jual", "delivered", 0.0), roll("r_stok", "available", 100.0)])
    nilai = lambda rs: sum(roll_value_cents(r) for r in rs) / 100
    async def sub():
        return nilai([r async for r in db.inventory_rolls.find({"owner_entity_id": A}, {"_id": 0})])
    await gl._insert_entry(lines=[{"account_code": "1-1300", "debit": 1e6, "credit": 0},
                                  {"account_code": "3-2900", "debit": 0, "credit": 1e6}],
        description="saldo awal roll stok", date="2026-11-01", source_type="uji_audit", source_id="inv0",
        entity_id=A, created_by="audit")
    s0, g0 = await sub(), await saldo("1-1300", A)
    rolls = await lcs.resolve_target_rolls(["po1"], A)
    alloc = lcs.compute_allocation(rolls, 3e6, "length")
    n = await lcs.apply_allocation_to_rolls("LC-UJI-1", alloc["allocations"])
    await gl.post_landed_cost({"id": "lc1", "entity_id": A}, amount=alloc["allocated_total"], label="LC-UJI-1")
    s1, g1 = await sub(), await saldo("1-1300", A)
    print(f"  roll yang dialokasi: {[a['roll_no'] for a in alloc['allocations']]} ({n} diperbarui)")
    print(f"  nilai roll (buku pembantu) naik {s1 - s0:,.2f}; akun persediaan 1-1300 naik {g1 - g0:,.2f}; "
          f"selisih yang mengendap = {(g1 - g0) - (s1 - s0):,.2f}")

asyncio.run(main())
