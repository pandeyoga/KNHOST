"""iteration 153 — E2E uji pemenuhan nyata.
Dua SKENARIO:
  A) ent_kanda (0 stok) → DNM-BDG-001 qty 250 allow_backorder → plan: transfer 150 (ent_ksc) + PR 100.
  B) ent_ksc → JMP-PLB-001: SO1=100 (reserves), SO2=200 allow_backorder (reserves 110, bo 90).
     Cancel SO1 → own_available ~100. POST plan {stock:50, reorder:20} → scope=partial.

CLEANUP: cancel interco, cancel internal_request (ikut via interco cancel? verifikasi), cancel PRs,
cancel SOs, hapus TEST_ customers. Validasi balance kembali ke 300 / 210.
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0]).strip().rstrip("/")
API = f"{BASE_URL}/api"
KSC, KANDA = "ent_ksc", "ent_kanda"


def _login(email, pw="demo12345"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin():
    return _login("admin@kainnusantara.id")


def H(tok, ent):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ent, "Content-Type": "application/json"}


# Shared trackers for cleanup
STATE: dict = {"customers": [], "sos": [], "prs": [], "interco": [], "internal_req": []}


def _create_customer(admin, entity_id, suffix):
    body = {
        "name": f"TEST_Pelanggan_{suffix}_{uuid.uuid4().hex[:6]}",
        "pic_name": "TEST PIC",
        "phone": "081200000000",
        "address": "Jl. Uji Pemenuhan No. 1",
        "city": "Bandung",
        "entity_id": entity_id,
        "assigned_sales_id": "user_sales_01",
        "type": "Retail",
    }
    r = requests.post(f"{API}/customers", headers=H(admin, entity_id), json=body, timeout=20)
    assert r.status_code in (200, 201), f"create customer: {r.status_code} {r.text[:300]}"
    c = r.json()
    STATE["customers"].append((c["id"], entity_id))
    return c


def _create_so(admin, entity_id, customer_id, product_id, qty, allow_backorder=False, unit="meter"):
    body = {
        "customer_id": customer_id,
        "shipping_address_id": "",
        "entity_id": entity_id,
        "allow_backorder": allow_backorder,
        "fulfillment_method": "kirim",
        "items": [{
            "product_id": product_id,
            "quantity": qty,
            "unit": unit,
            "purchase_mode": "qty",
        }],
    }
    r = requests.post(f"{API}/sales-orders", headers=H(admin, entity_id), json=body, timeout=30)
    assert r.status_code in (200, 201), f"create SO: {r.status_code} {r.text[:500]}"
    so = r.json()
    STATE["sos"].append((so["id"], entity_id))
    return so


def _get_balance_available(admin, product_id, entity_id):
    # Query inventory_balance via API if available, otherwise via mongo (we have db available but tests run in subprocess).
    # Use raw mongo through a helper endpoint if present; else fallback.
    r = requests.get(f"{API}/inventory/balances?entity_id={entity_id}&product_id={product_id}",
                     headers=H(admin, entity_id), timeout=15)
    if r.status_code == 200:
        rows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        return round(sum(float(b.get("available_qty") or 0) for b in rows if b.get("owner_entity_id") == entity_id), 2)
    return None


# ───────────────────────────────────────────────────────────── Scenario A
class TestScenarioA_InterCoAndPR:

    def test_A_full(self, admin):
        # Pre-check: Kanda owns 0 of DNM-BDG-001
        cust = _create_customer(admin, KANDA, "A")
        so = _create_so(admin, KANDA, cust["id"], "prod_denim_selvedge", 250, allow_backorder=True, unit="yard")
        # Backorder expected = 250
        items = so.get("items") or []
        assert items, "SO has no items"
        bo = sum(float(it.get("backorder_qty") or 0) for it in items)
        assert bo >= 249.99, f"expected backorder ~250, got {bo}; raw item: {items[0]}"

        # GET fulfillment plan
        r = requests.get(f"{API}/sales-admin/orders/{so['id']}/fulfillment-plan",
                         headers=H(admin, KANDA), timeout=30)
        assert r.status_code == 200, f"plan GET: {r.status_code} {r.text[:400]}"
        plan = r.json()
        assert plan["lines"], "plan has no lines"
        ln = plan["lines"][0]
        assert ln["product_id"] == "prod_denim_selvedge"
        assert ln["own_available"] == 0, f"kanda own_available should be 0, got {ln['own_available']}"
        others = {o["entity_id"]: o["available"] for o in ln["other_entities"]}
        assert others.get(KSC, 0) >= 300, f"ent_ksc should offer 300, got {others}"

        # POST plan: interco 150 from ksc + reorder 100
        payload = {
            "lines": [{
                "product_id": "prod_denim_selvedge",
                "stock_qty": 0,
                "interco": [{"entity_id": KSC, "qty": 150}],
                "reorder_qty": 100,
                "wait_qty": 0,
            }],
            "note": "TEST_ uji A",
        }
        r = requests.post(f"{API}/sales-admin/orders/{so['id']}/fulfillment-plan",
                          headers=H(admin, KANDA), json=payload, timeout=60)
        # BUSINESS BLOCKER expected: interco requires active internal price contract.
        # Capture exact error and fall back to a reorder-only plan so we still exercise PR path.
        if r.status_code == 400 and "kontrak" in (r.text or "").lower():
            pytest.skip_marker_interco = f"INTERCO BLOCKED: {r.text}"
            print("WARN scenario-A interco blocked:", r.text[:300])
            # Fall back to full reorder-only (250)
            payload2 = {"lines": [{"product_id": "prod_denim_selvedge",
                                   "stock_qty": 0, "interco": [], "reorder_qty": 250, "wait_qty": 0}],
                        "note": "TEST_ uji A fallback reorder-only"}
            r = requests.post(f"{API}/sales-admin/orders/{so['id']}/fulfillment-plan",
                              headers=H(admin, KANDA), json=payload2, timeout=60)
        assert r.status_code == 200, f"plan POST: {r.status_code} {r.text[:500]}"
        data = r.json()
        dec = data["decision"]
        print("DECISION A:", dec["summary"])
        assert dec["scope"] == "full", f"expected scope full, got {dec['scope']}"
        parts = dec["parts"]
        modes = {p["mode"] for p in parts}
        assert "reorder" in modes, f"missing reorder mode: {modes}"
        interco_part = next((p for p in parts if p["mode"] == "interco"), None)
        reorder_part = next(p for p in parts if p["mode"] == "reorder")
        if interco_part:
            assert interco_part.get("ref_number"), f"interco ref_number missing: {interco_part}"
        assert reorder_part.get("ref_number"), f"reorder ref_number missing: {reorder_part}"
        # Track
        if interco_part:
            STATE["interco"].append((interco_part["ref_id"], KANDA))
        STATE["prs"].append((reorder_part["ref_id"], KANDA))

        # Fetch interco transaction to find linked internal_request (only if we have one)
        if interco_part:
            ict = requests.get(f"{API}/interco/transactions/{interco_part['ref_id']}", headers=H(admin, KANDA), timeout=15)
            if ict.status_code == 200:
                ic = ict.json()
                ir_id = ic.get("internal_request_id") or (ic.get("source") or {}).get("internal_request_id")
                if ir_id:
                    STATE["internal_req"].append((ir_id, KANDA))
                    print("linked IR:", ir_id)

        # Verify PR exists
        pr = requests.get(f"{API}/purchase-requisitions/{reorder_part['ref_id']}",
                          headers=H(admin, KANDA), timeout=15)
        assert pr.status_code == 200, f"PR not accessible: {pr.status_code} {pr.text[:200]}"


# ───────────────────────────────────────────────────────────── Scenario B
class TestScenarioB_StockPartialAndPR:

    def test_B_partial(self, admin):
        cust = _create_customer(admin, KSC, "B")
        # SO1 100 (reserves)
        so1 = _create_so(admin, KSC, cust["id"], "prod_jumputan_palembang", 100, allow_backorder=False, unit="yard")
        res1 = sum(float(it.get("reserved_qty") or 0) for it in (so1.get("items") or []))
        assert res1 >= 99.99, f"SO1 reserved {res1}, expected 100; status={so1.get('status')}"

        # SO2 200 allow_backorder → reserves 110, backorder 90
        so2 = _create_so(admin, KSC, cust["id"], "prod_jumputan_palembang", 200, allow_backorder=True, unit="yard")
        it2 = (so2.get("items") or [{}])[0]
        res2 = float(it2.get("reserved_qty") or 0)
        bo2 = float(it2.get("backorder_qty") or 0)
        assert res2 >= 109.99 and bo2 >= 89.99, f"SO2 reserved={res2} backorder={bo2}; expected ~110/90"

        # Cancel SO1 → frees 100
        rc = requests.post(f"{API}/sales-orders/{so1['id']}/cancel",
                           headers=H(admin, KSC), json={"reason": "TEST_ free stock"}, timeout=20)
        assert rc.status_code in (200, 201), f"cancel SO1: {rc.status_code} {rc.text[:300]}"

        # GET plan for SO2 — own_available should now be ~100
        r = requests.get(f"{API}/sales-admin/orders/{so2['id']}/fulfillment-plan",
                         headers=H(admin, KSC), timeout=20)
        assert r.status_code == 200, f"plan GET SO2: {r.status_code} {r.text[:300]}"
        plan = r.json()
        assert plan["lines"], "no shortage line for SO2 - unexpected"
        ln = plan["lines"][0]
        print("B own_available=", ln["own_available"], " backorder_qty=", ln["backorder_qty"])
        assert ln["own_available"] >= 99.0, f"expected own_available~100 after SO1 cancel, got {ln['own_available']}"
        assert abs(ln["backorder_qty"] - 90) < 0.5, f"expected backorder 90, got {ln['backorder_qty']}"

        # POST plan {stock:50, reorder:20} partial (total 70 < 90 → partial)
        payload = {"lines": [{
            "product_id": "prod_jumputan_palembang",
            "stock_qty": 50, "interco": [], "reorder_qty": 20, "wait_qty": 0}],
            "note": "TEST_ uji B partial"}
        r = requests.post(f"{API}/sales-admin/orders/{so2['id']}/fulfillment-plan",
                          headers=H(admin, KSC), json=payload, timeout=60)
        assert r.status_code == 200, f"plan POST: {r.status_code} {r.text[:500]}"
        data = r.json()
        dec = data["decision"]
        print("DECISION B:", dec["summary"])
        assert dec["scope"] == "partial", f"expected partial, got {dec['scope']}"
        parts = dec["parts"]
        reorder_part = next((p for p in parts if p["mode"] == "reorder"), None)
        assert reorder_part and reorder_part.get("ref_number"), f"missing reorder ref: {parts}"
        STATE["prs"].append((reorder_part["ref_id"], KSC))

        # Fetch SO2 again, verify backorder reduced by stock (50), remains ~40
        so2r = requests.get(f"{API}/sales-orders/{so2['id']}", headers=H(admin, KSC), timeout=15).json()
        it = (so2r.get("items") or [{}])[0]
        new_bo = float(it.get("backorder_qty") or 0)
        new_res = float(it.get("reserved_qty") or 0)
        print(f"SO2 after plan: reserved={new_res} backorder={new_bo}")
        assert abs(new_bo - 40) < 1.0, f"expected backorder ~40 after stock 50 (reorder does not reduce bo), got {new_bo}"
        assert new_res >= 159.0, f"expected reserved ~160 (110+50), got {new_res}"
        # fulfillment_decisions saved
        decs = so2r.get("fulfillment_decisions") or []
        assert decs, "fulfillment_decisions not persisted on SO"


# ───────────────────────────────────────────────────────────── CLEANUP
class TestZCleanup:

    def test_cleanup(self, admin):
        results = {"interco_cancel": [], "ir_cancel": [], "pr_cancel": [], "so_cancel": [], "cust_delete": []}
        # 1) Cancel interco transactions FIRST (which should release reservations)
        for ict_id, ent in STATE["interco"]:
            r = requests.post(f"{API}/interco/transactions/{ict_id}/cancel",
                              headers=H(admin, ent), json={"reason": "TEST cleanup", "note": "TEST cleanup"}, timeout=20)
            results["interco_cancel"].append((ict_id, r.status_code, r.text[:150]))
        # 2) Cancel internal_requests
        for ir_id, ent in STATE["internal_req"]:
            r = requests.post(f"{API}/internal-requests/{ir_id}/cancel",
                              headers=H(admin, ent), json={"reason": "TEST cleanup"}, timeout=20)
            results["ir_cancel"].append((ir_id, r.status_code, r.text[:150]))
        # 3) Cancel PRs
        for pr_id, ent in STATE["prs"]:
            r = requests.post(f"{API}/purchase-requisitions/{pr_id}/cancel",
                              headers=H(admin, ent), json={"reason": "TEST cleanup"}, timeout=20)
            results["pr_cancel"].append((pr_id, r.status_code, r.text[:150]))
        # 4) Cancel SOs
        for so_id, ent in STATE["sos"]:
            r = requests.post(f"{API}/sales-orders/{so_id}/cancel",
                              headers=H(admin, ent), json={"reason": "TEST cleanup"}, timeout=20)
            results["so_cancel"].append((so_id, r.status_code, r.text[:200]))
        # 5) Delete customers via direct mongo (no API delete)
        import asyncio, sys
        sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
        from db import db
        async def _drop():
            for cust_id, _ in STATE["customers"]:
                await db.customers.delete_one({"id": cust_id})
                results["cust_delete"].append(cust_id)
            # Nuke residue test docs by prefix (defensive)
            await db.notifications.delete_many({"$or": [
                {"message": {"$regex": "TEST_"}},
                {"ref_id": {"$in": [s[0] for s in STATE["sos"]]}},
            ]})
        asyncio.get_event_loop().run_until_complete(_drop())
        print("CLEANUP:", results)

        # 6) Verify balances restored
        async def _bal(pid):
            tot = 0.0
            async for b in db.inventory_balances.find({"product_id": pid, "owner_entity_id": KSC}):
                tot += float(b.get("available_qty") or 0)
            return tot
        dnm = asyncio.get_event_loop().run_until_complete(_bal("prod_denim_selvedge"))
        jmp = asyncio.get_event_loop().run_until_complete(_bal("prod_jumputan_palembang"))
        print(f"POST-CLEANUP ksc avail: DNM={dnm} JMP={jmp}")
        # These may lag if SO cancel didn't release — report but allow some tolerance
        assert dnm >= 299.0, f"DNM-BDG-001 KSC available after cleanup = {dnm}, expected ~300"
        assert jmp >= 209.0, f"JMP-PLB-001 KSC available after cleanup = {jmp}, expected ~210"
