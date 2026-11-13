"""T10 — peran kustom beracuan Manajer TANPA izin apa pun menyetujui PO dan tagihan pemasok.

Gerbang persetujuan memakai pangkat peran (`role_registry.role_satisfies`), bukan izin. Peran kustom mewarisi pangkat
peran acuannya, sehingga mencabut semua modul di layar peran tidak mencabut wewenang menyetujui.

    python t10_setuju_tanpa_izin.py
"""
import boot_app  # noqa: F401
import asyncio
import datetime
import logging

import httpx
import server
from db import db

logging.disable(logging.CRITICAL)
E1, E2 = "ent_ksc", "ent_kanda"


async def main():
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "tok_admin", "user_id": admin["id"],
                                      "expires_at": now + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            HA = {"Authorization": "Bearer tok_admin", "X-Entity-Id": E1}
            mods = (await c.get("/api/access/modules", headers=HA)).json()
            mod_ids = [m["id"] for m in (mods.get("modules") if isinstance(mods, dict) else mods)]
            tok = {}
            tmpl_user = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
            for kode, label, base in (("kosong", "Uji Tanpa Acuan Kosong", ""), ("mgr0", "Uji Manajer Kosong", "manager")):
                r = await c.post("/api/access/roles", headers=HA, json={
                    "label": label, "base_role": base, "levels": {m: "none" for m in mod_ids}, "description": "uji T10"})
                j = r.json()
                rid = (j.get("role") or j).get("id")
                perms = (j.get("role") or j).get("permissions")
                print(f"peran {label}: id={rid} · jumlah izin={sum(len(v) for v in (perms or {}).values())}")
                u = {**tmpl_user, "id": f"usr_t10_{kode}", "email": f"t10_{kode}@x.id", "name": f"T10 {kode}",
                     "role": rid, "home_entity_id": E1, "allowed_entity_ids": [E1]}
                await db.users.insert_one(dict(u))
                await db.sessions.insert_one({"token": f"tok_{kode}", "user_id": u["id"],
                                              "expires_at": now + datetime.timedelta(hours=8)})
                tok[kode] = {"Authorization": f"Bearer tok_{kode}", "X-Entity-Id": E1}

            def po(pid, ent):
                return {"id": pid, "po_number": pid.upper(), "status": "waiting_approval", "approval_status": "pending",
                        "required_approval_role": "manager", "entity_id": ent, "created_by_id": "usr_orang_lain",
                        "created_by": "Orang Lain", "version": 1, "total_amount": 250_000_000, "subtotal": 250_000_000,
                        "supplier_id": "sup_x", "supplier_name": "Pemasok Uji", "lines": [], "timeline": [],
                        "created_at": now.isoformat()}

            await db.purchase_orders.insert_many([po("po_t10_a", E1), po("po_t10_b", E1), po("po_t10_c", E2)])
            print("\n-- PO Rp250.000.000 menunggu persetujuan tingkat 'manager'")
            r = await c.post("/api/purchase-orders/po_t10_a/approve", headers=tok["kosong"], json={})
            print("akun tanpa izin, tanpa acuan      :", r.status_code, str(r.json().get("detail"))[:90])
            r = await c.post("/api/purchase-orders/po_t10_a/approve", headers=tok["mgr0"], json={})
            d = await db.purchase_orders.find_one({"id": "po_t10_a"}, {"_id": 0, "status": 1, "approval_status": 1, "approved_by": 1})
            print("akun tanpa izin, beracuan Manajer :", r.status_code, "| di database:", d)
            r = await c.post("/api/purchase-orders/po_t10_b/reject", headers=tok["mgr0"], json={"reason": "uji tolak T10"})
            d = await db.purchase_orders.find_one({"id": "po_t10_b"}, {"_id": 0, "status": 1})
            print("tolak PO oleh akun yang sama      :", r.status_code, "| di database:", d)
            # Penjaga entitas: peran bawaan Finance TIDAK lintas PT. Akunnya hanya ditugaskan ke E1; PO milik E2
            # dengan tingkat persetujuan 'finance'. (Peran beracuan Manajer mewarisi sifat lintas PT, jadi tidak
            # dipakai untuk butir ini.)
            fin = {**tmpl_user, "id": "usr_t10_fin", "email": "t10_fin@x.id", "name": "T10 finance", "role": "finance",
                   "home_entity_id": E1, "allowed_entity_ids": [E1]}
            await db.users.insert_one(dict(fin))
            await db.sessions.insert_one({"token": "tok_fin", "user_id": fin["id"],
                                          "expires_at": now + datetime.timedelta(hours=8)})
            HF = {"Authorization": "Bearer tok_fin", "X-Entity-Id": E1}
            await db.purchase_orders.update_one({"id": "po_t10_c"}, {"$set": {"required_approval_role": "finance"}})
            r0 = await c.get("/api/purchase-orders/po_t10_c", headers=HF)
            r = await c.post("/api/purchase-orders/po_t10_c/approve", headers=HF, json={})
            d = await db.purchase_orders.find_one({"id": "po_t10_c"}, {"_id": 0, "status": 1, "entity_id": 1, "approved_by": 1})
            print(f"\n-- PO milik {E2}; akun Finance bawaan yang hanya ditugaskan ke {E1}")
            print("membaca PO itu                    :", r0.status_code, str(r0.json().get("detail", ""))[:70] if r0.status_code >= 400 else "")
            print("menyetujui PO itu                 :", r.status_code,
                  str(r.json().get("detail", ""))[:80] if r.status_code >= 400 else "", "| di database:", d)

            await db.vendor_bills.insert_one({
                "id": "vb_t10", "bill_number": "VB-T10", "status": "pending_approval", "approval_status": "pending",
                "required_approval_role": "manager", "entity_id": E1, "created_by_id": "usr_orang_lain",
                "supplier_id": "sup_x", "supplier_name": "Pemasok Uji", "total_amount": 75_000_000, "lines": [],
                "bill_date": "2026-11-13", "created_at": now.isoformat()})
            print("\n-- Tagihan pemasok Rp75.000.000 menunggu persetujuan")
            r = await c.post("/api/vendor-bills/vb_t10/approve", headers=tok["kosong"], json={})
            print("akun tanpa izin, tanpa acuan      :", r.status_code, str(r.json().get("detail"))[:90])
            r = await c.post("/api/vendor-bills/vb_t10/approve", headers=tok["mgr0"], json={})
            d = await db.vendor_bills.find_one({"id": "vb_t10"}, {"_id": 0, "status": 1, "approval_status": 1, "approved_by": 1})
            print("akun tanpa izin, beracuan Manajer :", r.status_code,
                  str(r.json().get("detail", ""))[:80] if r.status_code >= 400 else "", "| di database:", d)


asyncio.run(main())
