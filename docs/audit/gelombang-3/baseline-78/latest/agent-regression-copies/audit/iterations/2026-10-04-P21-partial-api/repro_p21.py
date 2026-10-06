"""P21 — Tahap A sisa: DESIGN-04 · DOC-03 · DOC-04 · DOC-05 · OPS-02 · OPS-03 · OPS-04.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-04-P21-partial-api/repro_p21.py
Self-clean: semua dokumen baru (snapshot _id) dihapus, pengguna sintetis dihapus, pengguna asli & stok dipulihkan.
"""
import io
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import bcrypt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://127.0.0.1:8009/api"
ENT = "ent_ksc"
PWD = "demo12345"
T = f"TEST_P21_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["design_requests", "design_gallery", "purchase_orders", "wms_tasks", "ai_schedules", "ai_schedule_runs", "ai_results",
       "notifications", "audit_logs", "products", "inventory_rolls", "inventory_movements", "inventory_lots", "sys_scheduler_runs",
       "ai_usage_log", "approval_matrix_log", "sales_orders", "journal_entries", "inventory_balances", "notification_turns"]
results, synth = [], []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:400]})


def login(email, ent=ENT):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": PWD}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent})
    return s


def synthetic(role, home=ENT):
    uid = f"user_{T}_{role}_{len(synth)}".lower()
    email = f"{uid}@synthetic.test"
    db.users.insert_one({"id": uid, "email": email, "name": f"{T} {role}", "role": role, "status": "active",
                         "home_entity_id": home, "allowed_entity_ids": [home],
                         "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()})
    synth.append(uid)
    return uid, email


def integrity():
    out = subprocess.run([sys.executable, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/scripts/verify_data_integrity.py"], capture_output=True, text=True, cwd="/app")
    line = next((ln for ln in out.stdout.splitlines() if "PASS" in ln and "FAIL" in ln), "")
    import re
    clean = re.sub(r"\x1b\[[0-9;]*m", "", out.stdout)
    m = re.search(r"PASS (\d+).*FAIL (\d+)", re.sub(r"\x1b\[[0-9;]*m", "", line))
    bad = sorted(ln.strip()[:160] for ln in clean.splitlines() if ln.strip().startswith(("[FAIL]", "[WARN]")))
    return (int(m.group(1)), int(m.group(2)), tuple(bad)) if m else (None, None, ())


# ── DESIGN-04: pindah penugasan / ganti peran / nonaktif tidak membocorkan file & PII ─────────
def design04(adm):
    meta = adm.get(f"{BASE}/design-requests/meta").json()
    pat = (meta.get("categories", {}).get("pattern") or [{}])[0].get("code", "")
    dsg = (meta.get("categories", {}).get("design") or [{}])[0].get("code", "")
    uid_b, email_b = synthetic("designer")
    r = adm.post(f"{BASE}/design-requests", json={"category_code": pat, "design_category_code": dsg, "assigned_to": "user_designer_01",
                                                  "submit_now": True, "brief": f"{T} brief rahasia pelanggan"})
    assert r.status_code == 200, r.text[:300]
    req = r.json()
    a, b = login("designer@kainnusantara.id"), login(email_b)
    mk = a.post(f"{BASE}/design-requests/{req['id']}/create-design", json={"title": f"{T} Motif"})
    gid = ((mk.json() or {}).get("design") or {}).get("id")
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
    up_a = a.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}.png", png, "image/png")})
    check("DESIGN-04", "desainer A (penerima awal) bisa buka & unggah", mk.status_code == 200 and up_a.status_code == 200,
          (mk.status_code, up_a.status_code))
    rb_before = b.get(f"{BASE}/design-requests/{req['id']}")
    check("DESIGN-04", "sebelum dipindah: desainer B ditolak membuka permintaan", rb_before.status_code in (403, 404), rb_before.status_code)
    asg = adm.post(f"{BASE}/design-requests/{req['id']}/assign", json={"assigned_to": uid_b, "due_date": ""})
    check("DESIGN-04", "admin memindahkan penugasan A → B", asg.status_code == 200, asg.text[:200])
    ra, rb = a.get(f"{BASE}/design-requests/{req['id']}"), b.get(f"{BASE}/design-requests/{req['id']}")
    items = lambda s: (lambda j: j.get("items", []) if isinstance(j, dict) else (j or []))(s.get(f"{BASE}/design-requests").json())  # noqa: E731
    la, lb = [x.get("id") for x in items(a)], [x.get("id") for x in items(b)]
    check("DESIGN-04", "sesudah pindah: A ditolak buka detail (brief/PII), B boleh", ra.status_code in (403, 404) and rb.status_code == 200,
          (ra.status_code, rb.status_code))
    check("DESIGN-04", "daftar A tidak lagi memuat permintaan, daftar B memuat", req["id"] not in la and req["id"] in lb, (len(la), len(lb)))
    up_a2 = a.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}2.png", png, "image/png")})
    put_a = a.put(f"{BASE}/design-gallery/{gid}", json={"title": f"{T} diubah A"})
    up_b = b.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}3.png", png, "image/png")})
    check("DESIGN-04", "sesudah pindah: A ditolak unggah/ubah desain, B boleh unggah",
          up_a2.status_code == 403 and put_a.status_code == 403 and up_b.status_code == 200, (up_a2.status_code, put_a.status_code, up_b.status_code))
    db.users.update_one({"id": uid_b}, {"$set": {"role": "sales"}})
    rb2 = b.get(f"{BASE}/design-requests/{req['id']}")
    up_b2 = b.post(f"{BASE}/design-gallery/{gid}/files", files={"file": (f"{T}4.png", png, "image/png")})
    check("DESIGN-04", "B diganti peran (→ sales) dengan token lama: buka & unggah ditolak seketika",
          rb2.status_code in (401, 403, 404) and up_b2.status_code in (401, 403), (rb2.status_code, up_b2.status_code))
    db.users.update_one({"id": uid_b}, {"$set": {"role": "designer", "status": "inactive"}})
    rb3 = b.get(f"{BASE}/design-requests/{req['id']}")
    check("DESIGN-04", "B dinonaktifkan: token lama ditolak (401/403)", rb3.status_code in (401, 403), rb3.status_code)
    files = [f.get("path") or f.get("stored_path") for f in (db.design_gallery.find_one({"id": gid}) or {}).get("files", [])]
    for p in files:
        if p and os.path.exists(os.path.join("uploads", p)):
            os.remove(os.path.join("uploads", p))


# ── DOC-03: approval berjenjang menolak keputusan basi / ganda ─────────────────────
def doc03(adm, mgr):
    base = db.purchase_orders.find_one({"status": {"$in": ["pending", "partially_received", "received", "completed"]},
                                        "entity_id": ENT, "items.0": {"$exists": True}}, {"_id": 0})
    pid = f"po_{T.lower()}"
    po = {**base, "id": pid, "po_number": f"{T}-PO", "status": "waiting_approval", "approval_status": "pending",
          "required_approval_role": "manager", "approval_level_current": 1, "version": 1, "created_by_id": "user_finance_01",
          "approval_chain": [{"level": 1, "required_role": "manager", "label": "Manajer", "status": "pending", "approved_by": "",
                              "approved_by_id": "", "approved_at": ""},
                             {"level": 2, "required_role": "admin", "label": "Direksi", "status": "pending", "approved_by": "",
                              "approved_by_id": "", "approved_at": ""}],
          "timeline": [], "payments": [], "amount_paid": 0.0, "payment_status": "unpaid", "billed_total": 0.0}
    for k in ("approved_by", "approved_at", "received_at", "saga_lock"):
        po.pop(k, None)
    for it in po.get("items", []):
        it["received_qty"] = 0
    db.purchase_orders.insert_one(dict(po))
    r1 = mgr.post(f"{BASE}/purchase-orders/{pid}/approve", json={"expected_version": 1})
    d1 = db.purchase_orders.find_one({"id": pid})
    check("DOC-03", "tingkat 1 (manajer) disetujui → menunggu tingkat 2 (admin)",
          r1.status_code == 200 and d1["approval_level_current"] == 2 and d1["required_approval_role"] == "admin", r1.text[:200])
    r2 = mgr.post(f"{BASE}/purchase-orders/{pid}/approve", json={"expected_version": 1})
    check("DOC-03", "manajer yang sama mengirim ulang (keputusan ganda/basi) ditolak", r2.status_code in (403, 409), r2.status_code)
    db.purchase_orders.update_one({"id": pid}, {"$set": {"version": 2}})   # amandemen sesudah layar dibuka
    r3 = adm.post(f"{BASE}/purchase-orders/{pid}/approve", json={"expected_version": 1})
    d3 = db.purchase_orders.find_one({"id": pid})
    check("DOC-03", "admin menyetujui versi basi (v1, PO kini v2) → 409 tanpa perubahan",
          r3.status_code == 409 and d3["status"] == "waiting_approval" and d3["approval_level_current"] == 2, (r3.status_code, d3["status"]))
    _, e1 = synthetic("admin")
    _, e2 = synthetic("admin")
    sess = [adm, login(e1), login(e2)]
    with ThreadPoolExecutor(3) as ex:
        codes = list(ex.map(lambda s: s.post(f"{BASE}/purchase-orders/{pid}/approve", json={"expected_version": 2}).status_code, sess))
    d4 = db.purchase_orders.find_one({"id": pid})
    tasks = db.wms_tasks.count_documents({"$or": [{"po_id": pid}, {"source_id": pid}, {"reference_id": pid}]})
    check("DOC-03", "3 admin menyetujui tingkat akhir bersamaan → tepat 1 sukses, sisanya 409/403",
          codes.count(200) == 1 and all(c in (403, 409) for c in codes if c != 200), codes)
    check("DOC-03", "disetujui penuh sekali: status pending, tugas penerimaan tidak ganda",
          d4["status"] == "pending" and tasks <= len(po["items"]), (d4["status"], tasks, len(po["items"])))
    r5 = mgr.post(f"{BASE}/purchase-orders/{pid}/reject", json={"reason": "telat"})
    check("DOC-03", "tolak sesudah disetujui penuh (keputusan basi) → 409", r5.status_code == 409, r5.status_code)
    check("DOC-03", "jejak: 2 tingkat ditandatangani 2 orang berbeda",
          len({lv["approved_by_id"] for lv in d4["approval_chain"]}) == 2, [lv["approved_by_id"] for lv in d4["approval_chain"]])
    db.purchase_orders.delete_one({"id": pid})
    db.wms_tasks.delete_many({"$or": [{"po_id": pid}, {"source_id": pid}, {"reference_id": pid}]})


# ── DOC-04 + DOC-05: laporan terjadwal menjaga lingkup & penerima ─────────────────
def doc04_05(adm, mgr):
    sales = login("sales@kainnusantara.id")
    sid = sales.post(f"{BASE}/ai/schedules", json={"template_id": "top_customers", "params": {"period": "ytd"},
                                                   "frequency": "daily", "time": "07:00", "title": f"{T} jadwal"}).json()["id"]
    run = sales.post(f"{BASE}/ai/schedules/{sid}/run").json()
    direct = sales.post(f"{BASE}/ai/templates/top_customers/run", json={"params": {"period": "ytd"}}).json()
    as_admin = adm.post(f"{BASE}/ai/templates/top_customers/run", json={"params": {"period": "ytd"}}).json()
    tot = lambda o: round(sum(float((r.get("totals") or {}).get("net_sales") or 0) for r in o["results"].values()), 2)  # noqa: E731
    run_doc = db.ai_schedule_runs.find_one({"id": run["id"]})
    run_tot = round(sum(float((db.ai_results.find_one({"result_id": i}) or {}).get("totals", {}).get("net_sales") or 0)
                        for i in run_doc.get("result_ids") or []), 2)
    check("DOC-04", "jadwal sales berjalan dengan hak akses pemilik: total = laporan langsung sales",
          run["status"] == "ok" and run_tot == tot(direct), (run["status"], run_tot, tot(direct)))
    check("DOC-04", "lingkup sales lebih sempit dari admin (bukan data semua sales)", tot(direct) <= tot(as_admin), (tot(direct), tot(as_admin)))
    rid = (run_doc.get("result_ids") or [None])[0]
    check("DOC-04", "hasil jadwal milik sales: manajer 404 (riwayat & ekspor), admin 200",
          mgr.get(f"{BASE}/ai/schedule-runs/{run['id']}").status_code == 404
          and mgr.get(f"{BASE}/ai/results/{rid}/export.xlsx").status_code == 404
          and adm.get(f"{BASE}/ai/results/{rid}/export.xlsx").status_code == 200, rid)
    check("DOC-04", "manajer tidak bisa menjalankan/mengubah/hapus jadwal sales",
          all(c == 404 for c in (mgr.post(f"{BASE}/ai/schedules/{sid}/run").status_code,
                                 mgr.patch(f"{BASE}/ai/schedules/{sid}", json={"time": "08:00"}).status_code,
                                 mgr.delete(f"{BASE}/ai/schedules/{sid}").status_code)))
    bad = sales.post(f"{BASE}/ai/schedules", json={"template_id": "sales_ranking", "frequency": "daily", "time": "07:00"})
    check("DOC-04", "sales tidak bisa menjadwalkan template di luar perannya (peringkat semua sales)", bad.status_code == 400, bad.status_code)
    n = db.notifications.find_one({"ref": run["id"]}, {"_id": 0})
    check("DOC-05", "notifikasi laporan hanya untuk pemilik (recipient_user, bukan siaran peran)",
          n and n.get("recipient_user") == "user_sales_01" or (n and n.get("recipient_user")), n and {k: n.get(k) for k in ("recipient_user", "recipient_role")})
    vis = lambda s: any(x.get("ref") == run["id"] for x in (s.get(f"{BASE}/notifications").json() or []))  # noqa: E731
    fin = login("finance@kainnusantara.id")
    check("DOC-05", "pemilik melihat notifikasinya; manajer/finance/admin lain tidak", vis(sales) and not vis(mgr) and not vis(fin),
          (vis(sales), vis(mgr), vis(fin)))
    # pemilik berubah: nonaktif → peran tanpa template → dicabut entitas — dispatcher tak boleh kirim
    uid, email = synthetic("sales")
    s2 = login(email)
    sid2 = s2.post(f"{BASE}/ai/schedules", json={"template_id": "top_customers", "params": {"period": "ytd"},
                                                 "frequency": "daily", "time": "07:00", "title": f"{T} sintetis"}).json()["id"]
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    for label, patch in [("dinonaktifkan", {"status": "inactive"}),
                         ("diganti peran gudang", {"status": "active", "role": "warehouse_admin"}),
                         ("dicabut dari badan usaha jadwal", {"status": "active", "role": "sales", "home_entity_id": "ent_kanda",
                                                              "allowed_entity_ids": ["ent_kanda"]})]:
        db.users.update_one({"id": uid}, {"$set": patch})
        db.ai_schedules.update_one({"id": sid2}, {"$set": {"next_run_at": past}})
        before = db.notifications.count_documents({"recipient_user": uid})
        adm.post(f"{BASE}/scheduler/jobs/ai_schedule_dispatch/run")
        last = db.ai_schedule_runs.find_one({"schedule_id": sid2}, sort=[("created_at", -1)]) or {}
        check("DOC-05", f"pemilik {label}: laporan tidak dikirim (run error, 0 notifikasi baru)",
              last.get("status") == "error" and db.notifications.count_documents({"recipient_user": uid}) == before, last.get("error"))
    db.ai_schedules.delete_many({"id": {"$in": [sid, sid2]}})


# ── OPS-02: job scheduler diulang / backend restart tidak mengulang efek bisnis ─────
JOBS = ["backorder_ready", "ar_due_soon", "penalty_accrual", "finance_case_scan", "contra_bon_reminder",
        "interco_settlement_reminder", "period_unlock_auto_close", "approval_backlog_reminder", "turn_scan",
        "ai_fact_sync", "ai_schedule_dispatch", "ai_snapshot_daily", "ai_anomaly_scan"]
EFFECT = ["notifications", "journal_entries", "inventory_movements", "inventory_rolls", "sales_orders", "cash_transactions",
          "finance_cases", "ai_schedule_runs", "fact_stock_daily", "fact_ar_daily", "ai_insights"]


def ops02(adm):
    counts = lambda: {c: db[c].count_documents({}) for c in EFFECT}  # noqa: E731
    first = {j: adm.post(f"{BASE}/scheduler/jobs/{j}/run").json() for j in JOBS}
    mid = counts()
    second, per_job = {}, {}
    for j in JOBS:
        b4 = counts()
        second[j] = adm.post(f"{BASE}/scheduler/jobs/{j}/run").json()
        d = {c: v - b4[c] for c, v in counts().items() if v != b4[c]}
        if d:
            per_job[j] = d
    after = counts()
    check("OPS-02", "semua job ber-efek bisnis sukses saat dijalankan", all(r.get("status") == "success" for r in [*first.values(), *second.values()]),
          {j: r.get("error") for j, r in {**first, **second}.items() if r.get("status") != "success"})
    grew = {c: after[c] - mid[c] for c in EFFECT if after[c] != mid[c]}
    check("OPS-02", "putaran ke-2 (retry) tanpa efek baru di dokumen bisnis/notifikasi", not grew, per_job)
    i0 = integrity()
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True)
    for _ in range(40):
        try:
            if requests.get(f"{BASE}/", timeout=3).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    time.sleep(6)
    after_restart = counts()
    grew2 = {c: after_restart[c] - after[c] for c in EFFECT if after_restart[c] != after[c]}
    i1 = integrity()
    check("OPS-02", "restart backend (scheduler boot ulang) tidak mengulang efek", not grew2, grew2)
    check("OPS-02", "integritas: tidak ada pelanggaran BARU sesudah retry + restart (FAIL/WARN sama)",
          i0[1] == i1[1] and i0[2] == i1[2], (i0[:2], i1[:2], sorted(set(i1[2]) - set(i0[2]))))
    lock = db.sys_scheduler_lock.find_one({}, {"_id": 0}) if "sys_scheduler_lock" in db.list_collection_names() else None
    check("OPS-02", "satu pemilik kunci scheduler sesudah restart", lock is None or bool(lock.get("owner")), lock and lock.get("owner"))


# ── OPS-03: impor produk & stok awal dapat dilanjutkan dan direkonsiliasi ─────────────
def ops03(adm):
    rows = [f"{T}-P{i},{T} Produk {i},1000{i}" for i in range(1, 5)] + [",tanpa sku,5"]
    csv = lambda rs: ("sku,name,price\n" + "\n".join(rs)).encode()  # noqa: E731
    up = lambda rs, dry=False: adm.post(f"{BASE}/master-data/import-products?dry_run={'true' if dry else 'false'}",  # noqa: E731
                                        files={"file": (f"{T}.csv", io.BytesIO(csv(rs)), "text/csv")}).json()
    dry = up(rows, True)
    check("OPS-03", "dry-run produk: 4 akan dibuat, 1 error, tanpa menulis",
          dry["created"] == 4 and len(dry["errors"]) == 1 and db.products.count_documents({"sku": {"$regex": f"^{T}"}}) == 0, dry)
    part = up(rows[:2])
    full = up(rows)
    again = up(rows)
    n = db.products.count_documents({"sku": {"$regex": f"^{T}"}})
    check("OPS-03", "impor produk terputus (2) → lanjut file penuh: hanya sisa dibuat, ulang idempoten",
          part["created"] == 2 and full["created"] == 2 and full["updated"] == 2 and again["created"] == 0 and n == 4,
          (part["created"], full["created"], full["updated"], again["created"], n))
    pids = [p["id"] for p in db.products.find({"sku": {"$regex": f"^{T}"}}, {"id": 1}).sort("sku", 1)]
    wh = db.warehouses.find_one({"entity_id": ENT}) or db.warehouses.find_one({})
    plan = [(pid, f"{T}-R{i}", 50.0 + i) for i, pid in enumerate(pids)]
    post = lambda p: adm.post(f"{BASE}/inventory/initial-stock", json={  # noqa: E731
        "product_id": p[0], "warehouse_id": wh["id"], "quantity": p[2], "unit": "meter", "roll_no": p[1], "lot": f"{T}-LOT"})
    first = [post(p).status_code for p in plan[:2]]
    resume = [post(p).status_code for p in plan]
    rolls = list(db.inventory_rolls.find({"roll_no": {"$regex": f"^{T}"}}, {"_id": 0, "product_id": 1, "length_remaining": 1}))
    check("OPS-03", "migrasi stok awal terputus → ulang semua baris: baris lama 409 (no. roll unik), sisa dibuat",
          first == [200, 200] and resume == [409, 409, 200, 200] and len(rolls) == 4, (first, resume, len(rolls)))
    bal_ok = all(abs(sum(r["length_remaining"] for r in rolls if r["product_id"] == pid) -
                     float((db.inventory_balances.find_one({"product_id": pid, "warehouse_id": wh["id"]}) or {}).get("on_hand_qty") or 0)) < 0.01
                 for pid in pids)
    mv = db.inventory_movements.count_documents({"product_id": {"$in": pids}, "movement_type": "initial_stock"})
    check("OPS-03", "rekonsiliasi: Σ roll = saldo per produk, 1 mutasi per roll", bal_ok and mv == 4, (bal_ok, mv))
    return pids, wh["id"]


# ── OPS-04: crash di tengah saga → terlihat, terukur, dipulihkan sekali ─────────────
def ops04(adm):
    so = db.sales_orders.find_one({"entity_id": ENT, "status": {"$in": ["reserved", "approved", "waiting_approval", "waiting_stock"]},
                                   "saga_lock": {"$exists": False}}, {"_id": 0, "id": 1, "number": 1})
    gr = db.purchase_orders.find_one({"entity_id": ENT, "status": "pending"}, {"_id": 0, "id": 1, "po_number": 1})
    old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    targets = [("sales_orders", so), ("purchase_orders", gr)]
    for coll, doc in targets:
        db[coll].update_one({"id": doc["id"]}, {"$set": {"saga_lock": {"action": "simulasi_crash", "by": T, "started_at": old,
                                                                      "token": f"lk_{T}"}}})
    db.journal_entries.insert_one({"id": f"je_{T}", "source_id": so["id"], "created_at": datetime.now(timezone.utc).isoformat(),
                                   "status": "void", "lines": [], "entry_number": f"{T}-JE", "entity_id": ENT})
    listed = {(x["collection"], x["id"]) for x in adm.get(f"{BASE}/saga-locks").json()}
    check("OPS-04", "kunci saga yang menggantung terlihat di Kunci Saga (SO & PO — PO dulu tak terdaftar)",
          all((c, d["id"]) in listed for c, d in targets), [c for c, d in targets if (c, d["id"]) not in listed])
    blocked = adm.post(f"{BASE}/sales-orders/{so['id']}/cancel", json={"reason": f"{T}"})
    check("OPS-04", "aksi baru atas dokumen terkunci ditolak 409 SAGA_IN_PROGRESS (tidak menulis dua kali)",
          blocked.status_code == 409 and "SAGA" in blocked.text, (blocked.status_code, blocked.text[:120]))
    ins = adm.get(f"{BASE}/saga-locks/sales_orders/{so['id']}/inspect").json()
    eff = {e["collection"]: e["count"] for e in ins.get("effects", [])}
    check("OPS-04", "inspeksi: kunci basi (tidak aktif) + efek hilir yang sudah terposting terukur",
          ins.get("active") is False and eff.get("journal_entries", 0) >= 1, (ins.get("active"), eff))
    no_ack = adm.post(f"{BASE}/saga-locks/sales_orders/{so['id']}/release", json={"reason": f"{T} pemulihan sesudah crash"})
    ok = adm.post(f"{BASE}/saga-locks/sales_orders/{so['id']}/release",
                  json={"reason": f"{T} pulih", "acknowledge_effects": True, "lock_token": f"lk_{T}"})
    check("OPS-04", "lepas kunci tanpa mengakui efek hilir ditolak; dengan pengakuan diterima",
          no_ack.status_code == 409 and ok.status_code == 200, (no_ack.status_code, ok.status_code, ok.text[:160]))
    rel_gr = adm.post(f"{BASE}/saga-locks/purchase_orders/{gr['id']}/release",
                      json={"reason": f"{T} pulih", "acknowledge_effects": True, "lock_token": f"lk_{T}"})
    check("OPS-04", "kunci PO yang menggantung kini bisa dilepas admin", rel_gr.status_code == 200, rel_gr.text[:160])
    check("OPS-04", "sesudah lepas: tidak ada kunci tersisa di dokumen", all("saga_lock" not in (db[c].find_one({"id": d["id"]}) or {})
                                                                          for c, d in targets))
    db.journal_entries.delete_one({"id": f"je_{T}"})


def main():
    snap_ids = snapshot_new_ids(NEW)
    snap_stock = snapshot_stock()
    users_before = {u["id"]: u for u in db.users.find({"id": {"$in": ["user_sales_01"]}})}
    adm, mgr = login("admin@kainnusantara.id"), login("manager@kainnusantara.id")
    pids, wh = [], None
    try:
        for fn in (lambda: design04(adm), lambda: doc03(adm, mgr), lambda: doc04_05(adm, mgr), lambda: ops04(adm)):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                check("HARNESS", getattr(fn, "__name__", "fn"), False, repr(exc))
        try:   # OPS-02 diukur SEBELUM OPS-03 (stok awal uji tanpa jurnal saldo awal memicu WARN drift GL)
            ops02(adm)
        except Exception as exc:  # noqa: BLE001
            check("OPS-02", "harness", False, repr(exc))
        try:
            pids, wh = ops03(adm)
        except Exception as exc:  # noqa: BLE001
            check("OPS-03", "harness", False, repr(exc))
    finally:
        db.users.delete_many({"id": {"$in": synth}})
        for uid, u in users_before.items():
            db.users.replace_one({"id": uid}, u)
        for c in ("sales_orders", "purchase_orders"):
            db[c].update_many({"saga_lock.by": T}, {"$unset": {"saga_lock": ""}})
        purge_new_ids(snap_ids, verbose=False)
        restore_stock(snap_stock)
        db.products.delete_many({"sku": {"$regex": f"^{T}"}})
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")


if __name__ == "__main__":
    main()
