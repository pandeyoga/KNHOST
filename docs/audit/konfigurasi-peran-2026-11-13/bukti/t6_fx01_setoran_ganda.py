"""T6 — FX-01 (audit keuangan): setoran karyawan pada kasus keuangan membuat kas dua kali? Dijalankan lewat API."""
import boot_app, asyncio, datetime, logging
import server, httpx
from db import db
logging.disable(logging.CRITICAL)
E1 = "ent_ksc"
def P(*a): print(*a, flush=True)
async def saldo(akun):
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": E1, "status": {"$ne": "void"}}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0); k += float(ln.get("credit") or 0)
    return d - k
async def main():
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        from services import amendment_service
        await amendment_service.ensure_reasons()   # label alasan baku (di data acuan sudah ada)
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "t", "user_id": admin["id"], "expires_at": now + datetime.timedelta(hours=8)})
        await db.customers.insert_one({"id": "cus_x", "name": "Toko Uji", "entity_id": E1, "status": "active"})
        await db.sales_orders.insert_one({"id": "so_x", "number": "SO-UJI-1", "entity_id": E1, "customer_id": "cus_x", "customer_name": "Toko Uji",
            "status": "confirmed", "grand_total": 10000000, "payments": [], "payment_status": "unpaid", "created_at": now.isoformat()})
        await db.bank_accounts.insert_one({"id": "ba_x", "name": "Bank Uji", "account_type": "bank", "cash_type": "kas_besar", "entity_id": E1, "is_active": True, "opening_balance": 0})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            H = {"Authorization": "Bearer t", "X-Entity-Id": E1}
            r = await c.post("/api/finance-cases", json={"case_type": "rekening_pribadi_karyawan", "amount": 10000000, "customer_id": "cus_x",
                "order_ids": ["so_x"], "attachments": [{"name": "bukti.pdf", "path": "uji/bukti.pdf"}]}, headers=H)
            P("buat kasus:", r.status_code, str(r.json())[:160] if r.status_code != 200 else r.json().get("number"))
            if r.status_code != 200: return
            K = r.json()["id"]
            r = await c.post(f"/api/finance-cases/{K}/resolve", json={"action": "akui_dipegang_karyawan", "reason_code": "case_employee_account",
                "amount": 10000000, "order_id": "so_x", "employee_name": "Budi"}, headers=H)
            P("langkah 1 (akui dipegang karyawan):", r.status_code, str(r.json().get("detail", r.json().get("status")))[:160])
            P("  saldo 1-1280 (piutang titipan karyawan):", await saldo("1-1280"))
            r = await c.post(f"/api/finance-cases/{K}/resolve", json={"action": "setor_dari_karyawan", "reason_code": "case_employee_account",
                "amount": 10000000, "account_id": "ba_x"}, headers=H)
            P("langkah 2 (setor 10.000.000):", r.status_code, str(r.json().get("detail", r.json().get("status")))[:200])
            kas = [k async for k in db.cash_transactions.find({"ref_type": "finance_case", "ref_id": K}, {"_id": 0, "id": 1, "amount": 1, "direction": 1, "contra_account_code": 1})]
            P("  transaksi kas untuk kasus ini:", len(kas), [(k["direction"], k["amount"], k.get("contra_account_code")) for k in kas])
            P("  jumlah kas masuk:", sum(k["amount"] for k in kas if k["direction"] == "in"), "| seharusnya 10.000.000")
            P("  saldo 1-1280 sesudah setor:", await saldo("1-1280"), "| seharusnya 0")
asyncio.run(main())
