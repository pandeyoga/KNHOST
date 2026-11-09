import kn
W = "warehouse.soreang"
PID = "prod_97ef39b63081"
SUP = "sup_a47057e2dfc2"
SRG = "site_fd9f6aa41d36"
c, po2 = kn.call("admin", "POST", "/purchase-orders", {"supplier_id": SUP, "ship_to_site_id": SRG,
                 "items": [{"product_id": PID, "quantity": 50, "unit": "yard", "price": 21000, "expected_grade": "A", "qty_rolls": 1}],
                 "notes": "B2A alur C KSC ke Soreang"}, entity="ent_ksc")
print(kn.db.warehouses.find_one({"id": "wh_40e831c5bb53"}, {"_id": 0, "sharing_mode": 1, "entity_ids": 1, "ownership": 1,
                                                           "entity_id": 1, "owner_entity_id": 1}))
for e in ("ent_ksc", "ent_kanda", "ent_82b52ed6ee8b"):
    print(e, [w.get("code") for w in kn.db.warehouses.find({"$or": [{"sharing_mode": {"$in": [None, "shared"]}}, {"entity_ids": e}]}, {"_id": 0, "code": 1})][:30])
print("RCM sharing:", list(kn.db.warehouses.find({"site_id": {"$in": ["site_c0c8400b0017", "site_fd9f6aa41d36", "site_54bed6261604"]}},
                                                 {"_id": 0, "code": 1, "sharing_mode": 1, "entity_ids": 1})))
