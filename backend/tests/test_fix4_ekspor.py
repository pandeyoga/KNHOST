"""FIX-4 (audit WMS-RFID 9 Nov 2026) — tombol baku "Unduh" daftar → Pusat Export (K-B4-07 · K-B3b-04).

Uji HTTP terhadap server hidup (stack sementara, salinan DB data acuan 8 Nov). Menutup & menjaga:
  * B3b EXP-01 — daftar WMS-RFID bisa diunduh XLSX lewat mesin Pusat Export (`POST /export-center/quick`), isi =
                 saringan + cari + cakupan daftar (PT, lokasi kerja / `X-Location-Scope`), ≤ 50.000 baris langsung.
  * B3b EXP-03 — CSV daftar berdialek Excel Indonesia (`;`, BOM, desimal koma) — bukan CSV koma buatan layar.
  * B3b EXP-04 — kolom saringan id mentah (`default=False`) tidak ikut kolom bawaan berkas.
  * B3b EXP-05 — dataset dokumen WMS-RFID baru (PA, perbaikan, job cetak, insiden, perangkat, lintasan, opname RFID).
  * K-B3b-04  — peran `warehouse` boleh mengunduh dataset GUDANG saja (daftar putih), dipagari lokasi tugasnya.
Pelaksana: `cd /app/backend && KN_DEMO_PW=<sandi demo> python -m pytest -q -p no:cacheprovider -n0 tests/test_fix4_ekspor.py`.
"""
import csv
import io
import os
import time

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
PW = os.environ.get("KN_DEMO_PW", "")
if not PW:
    pytest.skip("set KN_DEMO_PW (sandi akun demo data acuan) untuk menjalankan uji FIX-4", allow_module_level=True)
ACC = {"admin": "admin@kainnusantara.id", "jkt": "warehouse@kainnusantara.id",
       "soreang": "warehouse.soreang@kainnusantara.id", "rcm": "warehouse.rancamalang@kainnusantara.id",
       "whadmin": "wh.admin@kainnusantara.id"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    yield cli[os.environ.get("DB_NAME", "test_database")]
    cli.close()


@pytest.fixture(scope="module")
def tok():
    out = {}
    for k, email in ACC.items():
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=30)
        assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
        out[k] = r.json()["token"]
    return out


def H(t, ent=None, loc=None):
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    if ent:
        h["X-Entity-Id"] = ent
    if loc is not None:
        h["X-Location-Scope"] = loc
    return h


def quick(t, body, **hdr):
    return requests.post(f"{API}/export-center/quick", json=body, headers=H(t, **hdr), timeout=180)


def sheet_rows(content):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(content), read_only=True)
    names = wb.sheetnames
    data = [list(r) for r in wb[names[1]].iter_rows(values_only=True)]
    info = {r[0]: r[1] for r in wb[names[0]].iter_rows(values_only=True) if r and r[0]}
    return names, data, info


def csv_rows(content):
    text = content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text), delimiter=";"))


# ─── EXP-01 — XLSX langsung, lembar Ringkasan, paritas dengan daftar ─────────────
class TestQuickXlsx:
    def test_grn_xlsx_matches_list_and_has_summary(self, tok):
        lst = requests.get(f"{API}/goods-receipts", params={"limit": 500}, headers=H(tok["admin"]), timeout=60)
        assert lst.status_code == 200
        r = quick(tok["admin"], {"dataset": "goods_receipts", "format": "xlsx", "entity_scope": "work",
                                 "label": "kedatangan"})
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith(XLSX)
        assert "kedatangan_" in r.headers.get("content-disposition", "")
        names, data, info = sheet_rows(r.content)
        assert names[0] == "Ringkasan" and names[1].startswith("Data")
        assert "Lokasi" in info and info.get("Dataset", "").startswith("Kedatangan")
        assert len(data) - 1 == len(lst.json()) == int(r.headers["x-export-rows"])

    def test_status_filter_and_search_follow_list(self, tok, db):
        g = db.goods_receipts.find_one({}, {"_id": 0, "number": 1, "status": 1})
        if not g:
            pytest.skip("data acuan tanpa GRN")
        term = g["number"][-4:]
        lst = requests.get(f"{API}/goods-receipts", params={"limit": 500, "status": g["status"], "q": term},
                           headers=H(tok["admin"]), timeout=60).json()
        r = quick(tok["admin"], {"dataset": "goods_receipts", "format": "xlsx", "entity_scope": "work", "search": term,
                                 "filter": {"op": "and", "items": [{"field": "status", "cmp": "in", "value": [g["status"]]}]}})
        assert r.status_code == 200, r.text[:300]
        _n, data, info = sheet_rows(r.content)
        assert len(data) - 1 == len(lst) >= 1
        assert term in str(info.get("Filter"))

    def test_filter_only_columns_not_in_default_file(self, tok):
        r = quick(tok["admin"], {"dataset": "goods_receipts", "format": "xlsx", "entity_scope": "work"})
        _n, data, _i = sheet_rows(r.content)
        header = data[0]
        assert "No. GRN" in header and "No. SJ" in header
        assert not any("(saringan)" in str(h) for h in header), header

    def test_outbound_tasks_parity(self, tok):
        lst = requests.get(f"{API}/outbound/tasks", headers=H(tok["jkt"]), timeout=60)
        assert lst.status_code == 200
        rows = lst.json() if isinstance(lst.json(), list) else lst.json().get("items", [])
        r = quick(tok["jkt"], {"dataset": "wms_tasks", "format": "csv", "entity_scope": "work",
                               "filter": {"op": "and", "items": [{"field": "flow_type", "cmp": "eq", "value": "outbound"}]}})
        assert r.status_code == 200, r.text[:300]
        assert len(csv_rows(r.content)) - 1 == len(rows)


# ─── EXP-03 — CSV dialek Excel Indonesia ─────────────────────────────────────────
class TestCsvDialect:
    def test_csv_semicolon_bom_decimal_comma(self, tok, db):
        r = quick(tok["admin"], {"dataset": "inventory_rolls", "format": "csv", "entity_scope": "all",
                                 "columns": ["roll_no", "length_remaining"],
                                 "filter": {"op": "and", "items": [{"field": "length_remaining", "cmp": "gt", "value": 0}]},
                                 "sort": [{"key": "roll_no", "dir": "asc"}]}, ent="all")
        if r.status_code == 202:
            pytest.skip("terlalu banyak roll untuk unduh langsung di data ini")
        assert r.status_code == 200, r.text[:300]
        assert r.content.startswith(b"\xef\xbb\xbf"), "CSV wajib ber-BOM UTF-8"
        head = r.content.decode("utf-8-sig").split("\r\n")[0]
        assert head == "No. roll;Sisa"
        body = r.content.decode("utf-8-sig")
        frac = db.inventory_rolls.find_one({"length_remaining": {"$gt": 0}, "$expr": {"$ne": [
            {"$floor": "$length_remaining"}, "$length_remaining"]}}, {"_id": 0, "roll_no": 1})
        if frac:
            line = next((ln for ln in body.split("\r\n") if ln.startswith(frac["roll_no"] + ";")), "")
            assert "," in line, line


# ─── K-B3b-04 — peran gudang: dataset gudang saja, berpagar lokasi ───────────────
class TestWarehouseRole:
    def test_operator_can_export_warehouse_dataset(self, tok):
        r = quick(tok["jkt"], {"dataset": "wms_tasks", "format": "xlsx", "entity_scope": "work"})
        assert r.status_code == 200, f"petugas gudang tidak bisa mengunduh daftar gudang: {r.status_code} {r.text[:200]}"

    def test_operator_blocked_from_sales_dataset(self, tok):
        r = quick(tok["jkt"], {"dataset": "sales_orders", "format": "xlsx"})
        assert r.status_code == 403
        assert "gudang" in r.text.lower()

    def test_operator_blocked_from_roll_value_history(self, tok):
        r = quick(tok["jkt"], {"dataset": "roll_cost_history", "format": "xlsx"})
        assert r.status_code == 403

    def test_fenced_operator_rows_inside_location(self, tok, db):
        user = db.users.find_one({"email": ACC["soreang"]}, {"_id": 0, "location_site_ids": 1, "location_warehouse_ids": 1})
        sites = (user or {}).get("location_site_ids") or []
        whs = set((user or {}).get("location_warehouse_ids") or [])
        if sites:
            whs |= {w["id"] for w in db.warehouses.find({"site_id": {"$in": sites}}, {"_id": 0, "id": 1})}
        if not whs:
            pytest.skip("akun Soreang tanpa lokasi kerja di data ini")
        for loc in ("", "all"):
            r = quick(tok["soreang"], {"dataset": "inventory_rolls", "format": "csv", "entity_scope": "work",
                                       "columns": ["roll_no", "warehouse_id"]}, loc=loc)
            if r.status_code == 202:
                continue
            assert r.status_code == 200, r.text[:300]
            rows = csv_rows(r.content)[1:]
            outside = [x for x in rows if x and x[1] not in whs]
            assert not outside, f"baris di luar lokasi tugas (X-Location-Scope={loc!r}): {outside[:3]}"

    def test_location_choice_narrows_export(self, tok, db):
        user = db.users.find_one({"email": ACC["rcm"]}, {"_id": 0, "location_site_ids": 1})
        whs = [w["id"] for w in db.warehouses.find({"site_id": {"$in": (user or {}).get("location_site_ids") or []}},
                                                    {"_id": 0, "id": 1})]
        if not whs:
            pytest.skip("akun Rancamalang tanpa lokasi kerja")
        wh = whs[0]
        r = quick(tok["rcm"], {"dataset": "wms_tasks", "format": "csv", "entity_scope": "work",
                               "columns": ["product_name", "warehouse_id"]}, loc=f"wh:{wh}")
        assert r.status_code == 200, r.text[:300]
        assert all(x[1] == wh for x in csv_rows(r.content)[1:] if x)


# ─── EXP-05 — dataset dokumen WMS-RFID baru ──────────────────────────────────────
class TestNewDatasets:
    NEW = {"putaway_orders", "repair_orders", "rfid_print_jobs", "rfid_incidents", "rfid_devices", "rfid_passages",
           "rfid_cycle_counts"}

    def test_datasets_listed_for_admin_and_operator(self, tok):
        for who in ("admin", "jkt"):
            r = requests.get(f"{API}/export-center/datasets", headers=H(tok[who]), timeout=30)
            assert r.status_code == 200, r.text[:200]
            ids = {d["id"] for d in r.json()["datasets"]}
            assert self.NEW <= ids, (who, self.NEW - ids)

    def test_shared_rfid_collections_not_emptied_by_entity_scope(self, tok, db):
        total = db.rfid_passages.count_documents({})
        r = quick(tok["admin"], {"dataset": "rfid_passages", "format": "csv"}, ent="all")
        assert r.status_code == 200, r.text[:300]
        assert len(csv_rows(r.content)) - 1 == total

    # Dataset yang dipakai tombol Unduh di layar (kontrak statik juga dijaga verify_ui_standard G-UI-07b).
    USED = {"goods_receipts": "created_at", "wms_tasks": "created_at", "inventory_rolls": None,
            "inventory_movements": "timestamp", "inventory_balances": None, "inventory_lots": "created_at",
            "warehouse_transfers": "created_at", "warehouses": None, "cycle_count_sessions": "created_at",
            "inspections": "created_at", "rfid_tags": "encoded_at", "logistics_deliveries": "created_at",
            "putaway_orders": "created_at", "repair_orders": "created_at", "rfid_print_jobs": "created_at",
            "rfid_incidents": "created_at", "rfid_devices": None, "rfid_passages": "started_at",
            "rfid_cycle_counts": "created_at", "sales_orders": "created_at", "sales_returns": "created_at",
            "purchase_returns": "created_at", "interco_returns": "created_at", "makloon_orders": "created_at"}

    def test_every_list_dataset_exports_with_search_and_sort(self, tok):
        bad = []
        for ds, sort in self.USED.items():
            body = {"dataset": ds, "format": "csv", "entity_scope": "work" if ds in (
                "goods_receipts", "wms_tasks", "putaway_orders", "warehouse_transfers", "cycle_count_sessions",
                "logistics_deliveries") else "active", "search": "a"}
            if sort:
                body["sort"] = [{"key": sort, "dir": "desc"}]
            r = quick(tok["admin"], body)
            if r.status_code not in (200, 202):
                bad.append((ds, r.status_code, r.text[:160]))
        assert not bad, bad

    def test_putaway_orders_export(self, tok, db):
        r = quick(tok["admin"], {"dataset": "putaway_orders", "format": "xlsx", "entity_scope": "work"}, loc="all")
        assert r.status_code == 200, r.text[:300]
        _n, data, _i = sheet_rows(r.content)
        assert data[0][0] == "No. PA"


# ─── ≤ 50.000 langsung, lebih → job + notifikasi ─────────────────────────────────
class TestLargeExportJob:
    def test_over_limit_returns_job_then_notifies(self, tok, db):
        if db.inventory_movements.estimated_document_count() <= 50_000:
            pytest.skip("data < 50.000 mutasi")
        r = quick(tok["admin"], {"dataset": "inventory_movements", "format": "csv", "entity_scope": "all",
                                 "columns": ["timestamp", "movement_type"]}, ent="all")
        assert r.status_code == 202, r.text[:300]
        body = r.json()
        assert body["mode"] == "job" and body["total"] > 50_000 and body["limit"] == 50_000
        jid = body["job"]["id"]
        for _ in range(90):
            j = requests.get(f"{API}/export-center/jobs/{jid}", headers=H(tok["admin"]), timeout=30).json()
            if j["status"] in ("done", "failed"):
                break
            time.sleep(2)
        assert j["status"] == "done", j
        assert j["written_rows"] == body["total"]
        n = db.notifications.find_one({"ref": jid, "type": "export_ready"}) or db.notifications.find_one({"ref": jid})
        assert n, "notifikasi 'Unduhan siap' tidak dibuat"
