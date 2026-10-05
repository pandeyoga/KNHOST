"""P20f — DESIGN-04 (pemindahan desainer tidak membocorkan berkas/PII; akses tulis mengikuti penugasan) ·
DOC-03 (approval PO berjenjang: keputusan bersamaan/basi/sesudah amandemen ditolak 409).

Usage: cd /app/backend && python ../audit/iterations/2026-10-04-P20-partial-api/repro_p20f.py
Self-clean: user sintetis, permintaan/desain/PO/task uji dihapus; nomor & saldo dipulihkan.
"""
import base64
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import bcrypt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://localhost:8001/api"
ENT = "ent_ksc"
T = f"TEST_P20F_{uuid.uuid4().hex[:6]}"
PWD = "Synthetic#12345"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["users", "design_requests", "design_gallery", "purchase_orders", "wms_tasks", "notifications", "audit_logs",
       "doc_refs", "timeline_events", "approval_requests", "uploads", "auth_sessions", "sessions", "login_attempts"]
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:400]})


def login(email, pwd="demo12345"):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


def synth(role):
    uid = f"user_{T}_{role}".lower()
    email = f"{uid}@synthetic.test"
    db.users.insert_one({"id": uid, "email": email, "name": f"{T} {role}", "role": role, "status": "active",
                         "home_entity_id": ENT, "allowed_entity_ids": [ENT],
                         "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()})
    return uid, login(email, PWD)


def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.url} → {r.status_code} {r.text[:300]}"
    return r.json()


def design04(adm):
    a = login("designer@kainnusantara.id")
    a_id = db.users.find_one({"email": "designer@kainnusantara.id"})["id"]
    b_id, b = synth("designer")
    meta = ok(adm.get(f"{BASE}/design-requests/meta"))
    pat = (meta.get("categories", {}).get("pattern") or [{}])[0].get("code", "")
    dsg = (meta.get("categories", {}).get("design") or [{}])[0].get("code", "")
    cust = db.customers.find_one({"entity_id": ENT}, {"_id": 0, "id": 1, "name": 1})
    req = ok(adm.post(f"{BASE}/design-requests", json={"category_code": pat, "design_category_code": dsg, "assigned_to": a_id,
                                                      "submit_now": True, "brief": f"{T} motif", "source": "customer",
                                                      "customer_id": cust["id"]}))
    ref = ok(adm.post(f"{BASE}/design-requests/{req['id']}/references", files={"file": (f"{T}.png", PNG, "image/png")}))
    cd = ok(a.post(f"{BASE}/design-requests/{req['id']}/create-design", json={"title": f"{T} Motif"}))
    gid = cd["design"]["id"]
    up_a = a.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}a.png", PNG, "image/png")})
    up_b0 = b.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}b.png", PNG, "image/png")})
    check("DESIGN-04", "sebelum dipindah: A (penerima tugas) bisa unggah ke desainnya; B ditolak 403 (permintaan & desain)",
          up_a.status_code == 200 and up_b0.status_code == 403 and b.get(f"{BASE}/design-requests/{req['id']}").status_code == 403,
          (up_a.status_code, up_b0.status_code, up_b0.text[:120]))
    re = adm.post(f"{BASE}/design-requests/{req['id']}/assign", json={"assigned_to": b_id})
    ra = a.get(f"{BASE}/design-requests/{req['id']}")
    rr = a.get(f"{BASE}/design-requests/{req['id']}/references/{ref['id']}")
    la = ok(a.get(f"{BASE}/design-requests"))
    check("DESIGN-04", "sesudah dipindah ke B: A ditolak 403 membuka permintaan (berisi nama pelanggan) & berkas referensinya; daftar A bersih",
          re.status_code == 200 and ra.status_code == 403 and rr.status_code == 403
          and all(x["id"] != req["id"] for x in la.get("items", [])), (re.status_code, ra.status_code, rr.status_code))
    w = {"upload": a.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}c.png", PNG, "image/png")}).status_code,
         "kind": a.post(f"{BASE}/design-gallery/{gid}/files-kind/artwork", files={"file": (f"{T}d.png", PNG, "image/png")}).status_code,
         "submit": a.post(f"{BASE}/design-gallery/{gid}/lifecycle/submit", json={"note": "x"}).status_code,
         "colorway": a.post(f"{BASE}/design-gallery/{gid}/colorways", json={"name": "Merah", "colors": [{"hex": "#ff0000"}]}).status_code,
         "update": a.put(f"{BASE}/design-gallery/{gid}", json={"title": f"{T} ubah"}).status_code}
    check("DESIGN-04", "A tidak lagi bisa menulis desain itu (unggah, berkas berjenis, ajukan, colorway, ubah) → semua 403",
          set(w.values()) == {403}, w)
    rb = b.get(f"{BASE}/design-requests/{req['id']}")
    rbf = b.get(f"{BASE}/design-requests/{req['id']}/references/{ref['id']}")
    ub = b.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}e.png", PNG, "image/png")})
    lb = ok(b.get(f"{BASE}/design-requests"))
    check("DESIGN-04", "B (penerima baru) membuka permintaan & referensi, bisa unggah ke desain, tugas muncul di daftarnya",
          rb.status_code == rbf.status_code == ub.status_code == 200 and any(x["id"] == req["id"] for x in lb.get("items", [])),
          (rb.status_code, rbf.status_code, ub.status_code))
    g = ok(a.get(f"{BASE}/design-gallery/{gid}"))
    check("DESIGN-04", "galeri bersama tetap terbaca A tetapi TANPA PII pelanggan (nama/id pelanggan tidak ikut di dokumen desain)",
          cust["name"] not in json.dumps(g) and cust["id"] not in json.dumps(g), [k for k in g if "customer" in k])
    up_adm = adm.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}f.png", PNG, "image/png")})
    check("DESIGN-04", "admin/manager (rnd.manage) tetap bisa menulis desain mana pun", up_adm.status_code == 200, up_adm.status_code)


def make_po(adm, qty, price=100000):
    sup = db.suppliers.find_one({"name": "Cirebon Craft", "entity_id": ENT})["id"]
    po = ok(adm.post(f"{BASE}/purchase-orders", json={"supplier_id": sup, "warehouse_id": "wh_jakarta", "notes": f"{T} PO",
                                                     "items": [{"product_id": "prod_batik_mega", "quantity": qty, "unit": "yard",
                                                                "price": price, "expected_grade": "A"}]}))
    return db.purchase_orders.find_one({"id": (po.get("po") or po)["id"]}, {"_id": 0})


def doc03(adm):
    mgr = login("manager@kainnusantara.id")
    _, m2 = synth("manager")
    _, a2 = synth("admin")
    po = make_po(adm, 6000)
    chain = po.get("approval_chain") or []
    check("DOC-03", "PO 600 jt → rantai 2 tingkat (manager → direksi/admin), menunggu tingkat 1",
          po["status"] == "waiting_approval" and len(chain) == 2 and po.get("approval_level_current") == 1, (po["status"], chain))
    with ThreadPoolExecutor(2) as ex:
        rs = list(ex.map(lambda s: s.post(f"{BASE}/purchase-orders/{po['id']}/approve", json={"expected_version": 1}), [mgr, m2]))
    p1 = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    check("DOC-03", "dua manajer menyetujui tingkat 1 bersamaan → tepat 1×200 + 1×409; lanjut ke tingkat 2",
          sorted(r.status_code for r in rs) == [200, 409] and p1["approval_level_current"] == 2, [r.status_code for r in rs])
    winner = mgr if rs[0].status_code == 200 else m2
    again = winner.post(f"{BASE}/purchase-orders/{po['id']}/approve", json={"expected_version": 1})
    check("DOC-03", "penyetuju tingkat 1 tak bisa menandatangani tingkat 2 (403)", again.status_code == 403, (again.status_code, again.text[:100]))
    am = adm.post(f"{BASE}/purchase-orders/{po['id']}/amend", json={"reason": f"{T} harga naik", "items": [
        {"product_id": "prod_batik_mega", "quantity": 6000, "unit": "yard", "price": 101000, "expected_grade": "A"}]})
    p2 = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    check("DOC-03", "amandemen saat tingkat 2 menunggu → versi naik, rantai diulang dari tingkat 1 (persetujuan lama gugur)",
          am.status_code == 200 and p2["version"] == 2 and p2["approval_level_current"] == 1
          and all(lv["status"] == "pending" for lv in p2["approval_chain"]), (am.status_code, am.text[:120], p2.get("version")))
    stale = a2.post(f"{BASE}/purchase-orders/{po['id']}/approve", json={"expected_version": 1})
    stale_rj = a2.post(f"{BASE}/purchase-orders/{po['id']}/reject", json={"reason": "lama", "expected_version": 1})
    check("DOC-03", "keputusan atas versi basi (v1) — setujui maupun tolak — ditolak 409 tanpa mengubah PO",
          stale.status_code == stale_rj.status_code == 409 and "v1" in stale.text
          and db.purchase_orders.find_one({"id": po["id"]})["status"] == "waiting_approval", (stale.status_code, stale_rj.status_code))
    with ThreadPoolExecutor(2) as ex:
        f1 = ex.submit(lambda: mgr.post(f"{BASE}/purchase-orders/{po['id']}/approve", json={"expected_version": 2}))
        f2 = ex.submit(lambda: m2.post(f"{BASE}/purchase-orders/{po['id']}/reject", json={"reason": f"{T} tolak", "expected_version": 2}))
        codes = [f1.result().status_code, f2.result().status_code]
    p3 = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    consistent = (codes == [200, 409] and p3["status"] == "waiting_approval" and p3["approval_level_current"] == 2) or \
                 (codes == [409, 200] and p3["status"] == "rejected")
    check("DOC-03", "setujui vs tolak bersamaan → tepat satu menang, status akhir konsisten dengan pemenangnya",
          consistent, (codes, p3["status"], p3.get("approval_level_current")))
    po2 = make_po(adm, 6000)
    ok(mgr.post(f"{BASE}/purchase-orders/{po2['id']}/approve", json={"expected_version": 1}))
    fin = a2.post(f"{BASE}/purchase-orders/{po2['id']}/approve", json={"expected_version": 1})
    late = m2.post(f"{BASE}/purchase-orders/{po2['id']}/reject", json={"reason": f"{T} telat"})
    late_am_po = db.purchase_orders.find_one({"id": po2["id"]}, {"_id": 0})
    tasks = db.wms_tasks.count_documents({"po_id": po2["id"], "flow_type": "inbound"})
    check("DOC-03", "disetujui penuh (2 tingkat, orang berbeda) → pending + task inbound; tolak terlambat 409, status tetap",
          fin.status_code == 200 and late.status_code == 409 and late_am_po["status"] == "pending" and tasks >= 1,
          (fin.status_code, late.status_code, late_am_po["status"], tasks))
    with ThreadPoolExecutor(2) as ex:
        f1 = ex.submit(lambda: adm.post(f"{BASE}/purchase-orders/{po2['id']}/amend", json={"reason": f"{T} a1", "notes": "a1"}))
        f2 = ex.submit(lambda: adm.post(f"{BASE}/purchase-orders/{po2['id']}/amend", json={"reason": f"{T} a2", "notes": "a2"}))
        codes = sorted([f1.result().status_code, f2.result().status_code])
    p4 = db.purchase_orders.find_one({"id": po2["id"]}, {"_id": 0})
    check("DOC-03", "dua amandemen bersamaan → 1×200 + 1×409; versi naik tepat 1 (tak ada amandemen yang menimpa diam-diam)",
          codes == [200, 409] and p4["version"] == 2 and len(p4.get("amendments") or []) == 1, (codes, p4.get("version")))


def main():
    full = snapshot_stock(["number_sequences", "inventory_balances", "suppliers", "permission_settings"])
    ids = snapshot_new_ids(NEW)
    adm = login("admin@kainnusantara.id")
    try:
        for fn in (design04, doc03):
            try:
                fn(adm)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", f"eksekusi {fn.__name__}", False, repr(exc)[:300])
    finally:
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
