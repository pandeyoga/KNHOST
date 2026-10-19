"""T1 seed — Pesanan Khusus TEST dengan PO aktif (supplier) untuk uji UI pembatalan dokumen (LN-033 T08). --clear untuk hapus."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_l03_ln033_fulfillment as m  # noqa: E402

if "--clear" in sys.argv:
    ids = [o["id"] for o in m.DB.special_orders.find({"title": {"$regex": "^TEST_LN033_T1UI"}}, {"id": 1})]
    m.OD_IDS.extend(ids)
    gen = m.cleanup.__wrapped__() if hasattr(m.cleanup, "__wrapped__") else None
    if gen:
        next(gen, None); next(gen, None)
    print("cleared", ids)
    sys.exit(0)

m.TAG = "T1UI"
H = {"admin": m._login("admin@kainnusantara.id", "demo12345")}
od_id, (k1,) = m._od(H, [m.P_SUP])
m.DB.special_orders.update_one({"id": od_id}, {"$set": {"title": "TEST_LN033_T1UI"}})
r = m._realize(H, od_id, k1)
print(r.status_code, od_id, k1, r.json().get("result", {}).get("doc", {}).get("number"))
od = m.DB.special_orders.find_one({"id": od_id}, {"_id": 0, "number": 1})
print("number", od.get("number"))
