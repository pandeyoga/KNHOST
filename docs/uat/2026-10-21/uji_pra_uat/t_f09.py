SO = "so_02ddf6c44854"
sadm = Api("salesadmin@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
c, ctx = sadm.get(f"/sales-orders/{SO}/override-context"); step("override-context", c, short(ctx, 400), (200, 400, 403, 409))
c, b = sadm.post(f"/sales-orders/{SO}/override", {"lines": [{"product_id": "prod_bffe7f853835", "quantity": 105}], "note": "UAT ubah qty setelah harga ditolak"})
step("sadm: override qty 110->105", c, {k: b.get(k) for k in ("status", "sub_status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403, 409))
c, so = mgr.get(f"/sales-orders/{SO}")
print("pa:", [(p["type"], p["status"]) for p in so.get("pending_approvals", [])], so.get("status"))
c, b = sadm.post(f"/sales-orders/{SO}/submit-for-approval"); step("submit ulang", c, {k: b.get(k) for k in ("status", "sub_status")} if isinstance(b, dict) and "status" in b else b, (200, 409))
c, b = mgr.post(f"/sales-orders/{SO}/approve"); step("CEK: approve setelah override", c, {k: b.get(k) for k in ("status",)} if isinstance(b, dict) and "status" in b else b, (200, 409))
