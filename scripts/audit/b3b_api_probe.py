#!/usr/bin/env python3
"""Audit B3b (2026-11-09) — uji masukan buruk lewat API (form WMS-RFID).

**HANYA untuk stack sementara milik auditor** (mis. `kn-tmp-b3b-*`, DB `test_database` hasil restore snapshot).
Skrip ini MENGUBAH data (membuat/menolak/menutup dokumen) — JANGAN dijalankan ke stack bersama / produksi.

Cara pakai (di dalam kontainer backend sementara):
    KN_PROBE_PW=<sandi demo> MONGO_URL=mongodb://localhost:27017 DB_NAME=test_database \
        python /app/scripts/audit/b3b_api_probe.py --base http://localhost:8001 --out /tmp/b3b_probe.json

Setiap uji mencatat: nama, peran, metode+path, payload, kode status, potongan respons, dan PENILAIAN:
  * `DITERIMA_SEHARUSNYA_DITOLAK` — server menerima masukan buruk (temuan)
  * `DITOLAK_BENAR`               — server menolak (4xx) dengan wajar
  * `GALAT_SERVER`                — 5xx (temuan: masukan buruk merusak server)
  * `LEWATI`                      — data prasyarat tidak tersedia
Sandi tidak pernah dicetak; diambil dari env `KN_PROBE_PW`.
"""
import argparse
import json
import os
import sys
import time

import requests
from pymongo import MongoClient

TIMEOUT = 40


class Probe:
    def __init__(self, base, db):
        self.base = base.rstrip("/")
        self.db = db
        self.sessions = {}
        self.results = []

    # ── sesi ───────────────────────────────────────────────────────────────────
    def login(self, role, email=None):
        if role in self.sessions:
            return self.sessions[role]
        q = {"email": email} if email else {"role": role, "is_active": {"$ne": False}}
        u = self.db.users.find_one(q, {"_id": 0, "email": 1, "role": 1, "default_entity_id": 1, "entity_ids": 1})
        if not u:
            return None
        r = requests.post(f"{self.base}/api/auth/login", json={"email": u["email"], "password": os.environ["KN_PROBE_PW"]},
                          timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"login gagal {role}: {r.status_code}", file=sys.stderr)
            return None
        data = r.json()
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {data['token']}"
        ent = (data.get("entity_context") or {}).get("active_entity_id") or u.get("default_entity_id") or ""
        if ent:
            s.headers["X-Entity-Id"] = ent
        s.kn_user = {"email": u["email"], "role": u["role"], "entity": ent, "id": (data.get("user") or {}).get("id")}
        self.sessions[role] = s
        return s

    # ── satu uji ──────────────────────────────────────────────────────────────
    def run(self, name, role, method, path, *, json_body=None, params=None, expect="tolak", note="", check=None):
        s = self.login(role)
        if s is None:
            self.results.append({"name": name, "role": role, "verdict": "LEWATI", "why": "akun peran tidak ada / login gagal"})
            return None
        t0 = time.time()
        try:
            r = s.request(method, f"{self.base}{path}", json=json_body, params=params, timeout=TIMEOUT)
        except Exception as e:  # noqa: BLE001
            self.results.append({"name": name, "role": role, "method": method, "path": path, "verdict": "GALAT_KONEKSI",
                                 "why": str(e)[:200]})
            return None
        body = r.text[:600]
        if r.status_code >= 500:
            verdict = "GALAT_SERVER"
        elif expect == "tolak":
            verdict = "DITOLAK_BENAR" if 400 <= r.status_code < 500 else "DITERIMA_SEHARUSNYA_DITOLAK"
        else:  # expect == "info" — catat saja, penilaian lewat `check`
            verdict = "INFO"
        extra = None
        if check and r.status_code < 300:
            try:
                extra = check(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
            except Exception as e:  # noqa: BLE001
                extra = f"cek gagal: {e}"
        self.results.append({"name": name, "role": role, "user_role": s.kn_user["role"], "method": method, "path": path,
                             "payload": json_body, "params": params, "status": r.status_code, "verdict": verdict,
                             "response": body, "check": extra, "note": note, "ms": int((time.time() - t0) * 1000)})
        return r

    def skip(self, name, why):
        self.results.append({"name": name, "verdict": "LEWATI", "why": why})


def one(db, coll, q, proj=None, sort=None):
    cur = db[coll].find(q, {"_id": 0, **(proj or {})})
    if sort:
        cur = cur.sort(sort)
    for d in cur.limit(1):
        return d
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--out", default="/tmp/b3b_probe.json")
    a = ap.parse_args()
    if not os.environ.get("KN_PROBE_PW"):
        sys.exit("set KN_PROBE_PW")
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
    P = Probe(a.base, db)
    WH = "warehouse"          # peran operator gudang (bukan supervisor)
    WA = "warehouse_admin"
    AD = "admin"
    MG = "manager"

    wh_user = P.login(WH)
    ent = wh_user.kn_user["entity"] if wh_user else ""
    wh = one(db, "warehouses", {"active": {"$ne": False}, "zones.0": {"$exists": True}}, {"id": 1, "code": 1, "zones": 1})
    wh_id = (wh or {}).get("id", "")
    roll = one(db, "inventory_rolls", {"status": "available", "warehouse_id": wh_id, "owner_entity_id": ent} if ent else
               {"status": "available"}, {"id": 1, "product_id": 1, "grade": 1, "roll_no": 1, "owner_entity_id": 1, "bin_id": 1})
    prod_id = (roll or {}).get("product_id") or (one(db, "products", {}, {"id": 1}) or {}).get("id", "")

    # ── 0. Pola umum: kunci asing dibuang diam-diam (extra=ignore) ───────────────────
    r = P.run("extra-key dibuang (transfer)", WH, "POST", "/api/transfers",
              json_body={"source_warehouse_id": wh_id, "dest_warehouse_id": wh_id, "items": [],
                         "notes": "uji b3b", "requested_by": "Direktur Utama", "kunci_asing": "harus-ditolak"},
              note="dua hal: (a) kunci asing diterima? (b) requested_by dari klien disimpan?")

    # ── 1. Penerimaan / QC ───────────────────────────────────────────────────────────
    t_in = one(db, "wms_tasks", {"flow_type": "inbound", "status": {"$in": ["waiting_goods", "receiving"]}},
               {"id": 1, "product_id": 1, "expected_qty": 1, "quantity": 1, "warehouse_id": 1, "entity_id": 1})
    if t_in:
        P.run("scan-receive bin & roll fiktif", WH, "POST", f"/api/inbound/tasks/{t_in['id']}/scan-receive",
              json_body={"product_id": t_in.get("product_id"), "doc_qty": 1, "bin_id": "BIN-FIKTIF-B3B", "roll_id": "ROLL-FIKTIF-B3B"},
              note="bin_id/roll_id teks bebas tanpa validasi master")
        P.run("scan-receive doc_qty negatif", WH, "POST", f"/api/inbound/tasks/{t_in['id']}/scan-receive",
              json_body={"product_id": t_in.get("product_id"), "doc_qty": -5})
        P.run("escalate alasan 1 huruf (query)", WH, "POST", f"/api/inbound/tasks/{t_in['id']}/escalate", params={"reason": "x"})
        P.run("resolve-escalation qty negatif", MG, "POST", f"/api/inbound/tasks/{t_in['id']}/resolve-escalation",
              params={"adjusted_qty": -10, "resolution_notes": "uji b3b"})
    else:
        P.skip("inbound probes", "tidak ada tugas inbound terbuka")
    t_qc = one(db, "wms_tasks", {"flow_type": "inbound", "status": "qc_pending"}, {"id": 1, "quarantine_qty": 1, "entity_id": 1})
    if t_qc:
        q = float(t_qc.get("quarantine_qty") or 1)
        P.run("qc-decision tolak tanpa alasan", WH, "POST", f"/api/inbound/tasks/{t_qc['id']}/qc-decision",
              json_body={"accept_qty": 0, "reject_qty": q, "reject_disposition": "damaged", "reason": ""})
    # baca roll QC tugas PT lain
    other_task = one(db, "wms_tasks", {"flow_type": "inbound", "entity_id": {"$nin": [ent, "", None]}}, {"id": 1, "entity_id": 1})
    if other_task:
        P.run("GET qc rolls tugas PT lain", WH, "GET", f"/api/inbound/qc/tasks/{other_task['id']}/rolls",
              note=f"tugas milik {other_task.get('entity_id')} dibaca oleh pengguna PT {ent}")
        P.run("GET qc plan tugas PT lain (pembanding)", WH, "GET", f"/api/inbound/qc/tasks/{other_task['id']}/plan")
    if roll:
        P.run("grade-override alasan 1 huruf", WA, "POST", f"/api/inventory/rolls/{roll['id']}/grade-override",
              json_body={"grade": "B", "reason": "x"})
    other_user = one(db, "users", {"role": {"$in": ["qc", "warehouse_admin", "md_quality"]}}, {"id": 1, "role": 1})
    if wh_id:
        P.run("random-check assigned_to dibuang", WA, "POST", "/api/inspections/random-check",
              json_body={"warehouse_id": wh_id, "count": 1, "assigned_to": (other_user or {}).get("id", "user_lain")},
              expect="info", check=lambda d: {"assigned_to_tersimpan": (d.get("assigned_to") if isinstance(d, dict) else None),
                                              "diminta": (other_user or {}).get("id")})
    P.run("master grade max_points negatif", AD, "POST", "/api/master/grades",
          json_body={"code": "Z9", "name": "Uji B3b", "rank": 98, "max_points": -5})
    po = one(db, "purchase_orders", {"status": {"$in": ["partial", "partially_received", "approved", "sent"]}}, {"id": 1, "status": 1})
    if po:
        P.run("tutup PO alasan kosong", AD, "POST", f"/api/purchase-orders/{po['id']}/close", json_body={"reason": ""})
    P.run("GET goods-receipts limit=-1", WA, "GET", "/api/goods-receipts", params={"limit": -1})
    P.run("GET goods-receipts limit=100000", WA, "GET", "/api/goods-receipts", params={"limit": 100000}, expect="info",
          check=lambda d: {"baris": len(d) if isinstance(d, list) else len((d or {}).get("items") or [])})
    grn = one(db, "goods_receipts", {"status": {"$in": ["draft", "review", "reading", "counting"]}}, {"id": 1, "version": 1, "status": 1})
    if grn:
        v = grn.get("version", 0)
        P.run("GRN dn nomor 5000 huruf & tanggal ngawur", WA, "PATCH", f"/api/goods-receipts/{grn['id']}/dn",
              json_body={"expected_version": v, "number": "N" * 5000, "date": "bukan-tanggal"})
        grn2 = db.goods_receipts.find_one({"id": grn["id"]}, {"_id": 0, "version": 1})
        P.run("GRN tolak alasan 5 spasi", WA, "POST", f"/api/goods-receipts/{grn['id']}/reject",
              json_body={"expected_version": (grn2 or {}).get("version", v), "reason": "     "})
    else:
        P.skip("GRN probes", "tidak ada GRN draf")

    # ── 2. Lokasi / gudang / transfer / opname / stok awal ────────────────────────────
    if wh_id:
        occ = db.inventory_rolls.count_documents({"warehouse_id": wh_id, "bin_id": {"$nin": [None, ""]},
                                                  "status": {"$in": ["available", "reserved", "quarantine"]}})
        P.run("PATCH gudang zones=[] (bypass PUT /structure)", WH, "PATCH", f"/api/warehouses/{wh_id}",
              json_body={"data": {"zones": []}}, note=f"gudang berisi {occ} roll ber-bin; peran operator (bukan supervisor)")
        P.run("PATCH gudang name kosong", WH, "PATCH", f"/api/warehouses/{wh_id}", json_body={"data": {"name": ""}})
        P.run("PATCH gudang lat 999", WH, "PATCH", f"/api/warehouses/{wh_id}", json_body={"data": {"lat": 999, "lng": -999}})
    P.run("POST lokasi nama regex rusak", WA, "POST", "/api/warehouse-sites", json_body={"name": "Gudang (Baru"})
    P.run("GET repair-orders q=(", WA, "GET", "/api/repair-orders", params={"q": "("})
    cc = one(db, "cycle_count_sessions", {"status": {"$in": ["open", "draft", "in_progress"]}, "mode": {"$ne": "registration"}},
             {"id": 1, "warehouse_id": 1})
    if cc and prod_id:
        P.run("opname item bin teks bebas", WH, "POST", f"/api/cycle-count/sessions/{cc['id']}/items",
              json_body={"product_id": prod_id, "bin_id": "A1-01-FIKTIF"}, expect="info",
              check=lambda d: {"bin_id": (d or {}).get("bin_id") if isinstance(d, dict) else None,
                               "expected_qty": (d or {}).get("expected_qty") if isinstance(d, dict) else None})
        P.run("opname tolak alasan kosong", MG, "POST", f"/api/cycle-count/sessions/{cc['id']}/reject", json_body={"reason": "a"})
    tr = one(db, "warehouse_transfers", {"status": {"$in": ["waiting_approval", "draft"]}}, {"id": 1})
    if tr:
        P.run("transfer tolak alasan kosong", MG, "POST", f"/api/transfers/{tr['id']}/reject",
              json_body={"reason": "", "rejected_by": "Orang Lain"})
    if wh_id and prod_id:
        P.run("stok awal satuan/grade/bin ngawur", AD, "POST", "/api/inventory/initial-stock",
              json_body={"product_id": prod_id, "warehouse_id": wh_id, "lot": "LOT-B3B", "quantity": 0, "unit": "hasta",
                         "grade": "ZZ", "bin_id": "bin_tidak_ada"})
    lot = one(db, "inventory_lots", {"status": {"$in": ["active", "open", None]}}, {"id": 1})
    if lot:
        P.run("lot status alasan kosong", WA, "POST", f"/api/lots/{lot['id']}/status", json_body={"status": "hold", "reason": ""})

    # ── 3. Barang keluar / potong / kirim / retur / makloon ───────────────────────────
    t_out = one(db, "wms_tasks", {"flow_type": "outbound", "status": {"$in": ["picking", "packing", "staging", "created", "released"]},
                                  "task_subtype": {"$ne": "sample_cut"}}, {"id": 1, "status": 1, "quantity": 1})
    if t_out:
        P.run("scan-pick tanpa roll", WH, "POST", f"/api/outbound/tasks/{t_out['id']}/scan-pick", params={"actual_qty": 0.5},
              note="alur cepat HP: pick tanpa pindai roll")
        P.run("dispatch ship_qty=nan", WH, "POST", f"/api/outbound/tasks/{t_out['id']}/dispatch", params={"ship_qty": "nan"})
        P.run("escalate outbound alasan 1 huruf", WH, "POST", f"/api/outbound/tasks/{t_out['id']}/escalate", params={"reason": "x"})
    shp = one(db, "shipments", {"logistics_status": {"$in": [None, "", "unassigned"]}}, {"id": 1})
    if shp:
        P.run("pengiriman ongkir negatif", WA, "POST", "/api/logistics/deliveries",
              json_body={"mode": "courier", "shipment_ids": [shp["id"]], "shipping_cost": -100000, "courier_name": "x"})
    sr = one(db, "sales_returns", {"status": {"$in": ["submitted", "pending_approval", "draft"]}}, {"id": 1})
    if sr:
        P.run("retur jual tolak alasan 1 huruf", MG, "POST", f"/api/sales-returns/{sr['id']}/reject", json_body={"notes": "a"})
    sr2 = one(db, "sales_returns", {"status": {"$in": ["approved", "in_transit", "inspecting"]}}, {"id": 1})
    if sr2:
        P.run("milestone retur oleh peran gudang", WH, "POST", f"/api/sales-returns/{sr2['id']}/milestone",
              json_body={"milestone": "goods_arrived"}, expect="info", note="tombol tampil bagi gudang; server?")
    mko = one(db, "makloon_orders", {"status": {"$in": ["draft", "confirmed", "issued", "in_process"]}}, {"id": 1})
    if mko:
        P.run("MKO batal alasan 1 huruf", MG, "POST", f"/api/makloon-orders/{mko['id']}/cancel", json_body={"reason": "a"})
    pr = one(db, "purchase_returns", {"status": {"$in": ["submitted", "pending_approval"]}}, {"id": 1})
    if pr:
        P.run("retur beli tolak alasan kosong", MG, "POST", f"/api/purchase-returns/{pr['id']}/reject", json_body={"notes": ""})

    # ── 4. RFID & pengaturan ─────────────────────────────────────────────────────────
    if wh_id:
        r = P.run("perangkat arah/status ngawur", AD, "POST", "/api/rfid/devices",
                  json_body={"name": "Uji B3b", "type": "gate", "direction": "samping", "warehouse_id": wh_id,
                             "status": "rusak", "location": "Zona Fiktif"})
        dev_id = None
        try:
            dev_id = (r.json() or {}).get("id") if r is not None and r.status_code < 300 else None
        except Exception:  # noqa: BLE001
            pass
        dev = {"id": dev_id} if dev_id else one(db, "rfid_devices", {}, {"id": 1})
        if dev:
            P.run("perangkat 'online' memalsukan heartbeat", AD, "PATCH", f"/api/rfid/devices/{dev['id']}",
                  json_body={"status": "online"}, expect="info",
                  check=lambda d: {"last_heartbeat": (d or {}).get("last_heartbeat") if isinstance(d, dict) else None})
    if roll:
        P.run("print-job kind ngawur", WA, "POST", "/api/rfid/print-jobs", json_body={"roll_ids": [roll["id"]], "kind": "qr"},
              expect="tolak")
    inc = one(db, "rfid_incidents", {"status": {"$ne": "resolved"}}, {"id": 1})
    if inc:
        P.run("insiden selesai tanpa catatan", WA, "POST", f"/api/rfid/incidents/{inc['id']}/resolve", json_body={"note": ""})
    else:
        P.skip("insiden selesai tanpa catatan", "tidak ada insiden terbuka")
    P.run("setelan regex pola PO rusak", AD, "PUT", "/api/config/values",
          json_body={"items": [{"key": "receiving.client_po_patterns", "value": ["(?P<core>\\d{3"], "scope_type": "global",
                                "scope_id": "", "reason": "uji b3b regex"}]})
    P.run("setelan ocr_max_pages negatif", AD, "PUT", "/api/config/values",
          json_body={"items": [{"key": "receiving.ocr_max_pages", "value": -1, "scope_type": "global", "scope_id": "",
                                "reason": "uji b3b batas"}]})
    P.run("setelan alasan 1 huruf", AD, "PUT", "/api/config/values",
          json_body={"items": [{"key": "receiving.mode", "value": "legacy", "scope_type": "global", "scope_id": "", "reason": "x"}]})
    P.run("PUT /settings lama inventory dict bebas", AD, "PUT", "/api/settings",
          json_body={"scope": "global", "inventory": {"min_cut_qty": -5}})
    rdev = one(db, "rfid_devices", {"protocol": "v2"}, {"id": 1})
    if rdev:
        P.run("simulator roll_limit bukan angka", AD, "POST", f"/api/rfid/v2/ops/devices/{rdev['id']}/simulate",
              json_body={"scenario": "green", "roll_limit": "abc"})
    case = one(db, "rfid_v2_reviews", {"status": "open"}, {"_id": 1})
    if case:
        P.run("antrean periksa tutup kasus alasan titik", WA, "POST", f"/api/rfid/v2/ops/reviews/{case['_id']}/dismiss",
              json_body={"reason": "....."}, note="K-14 'huruf' vs hitungan karakter")

    out = {"base": a.base, "db": db.name, "user_entity": ent, "warehouse_id": wh_id, "results": P.results}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    from collections import Counter
    print(dict(Counter(r["verdict"] for r in P.results)))
    for r in P.results:
        print(f"{r['verdict']:28} {r.get('status', ''):>4} {r['name']}")


if __name__ == "__main__":
    main()
