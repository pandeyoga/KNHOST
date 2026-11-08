"""PREP-A (K-OPN-06) — lembar perbaikan master produk: unduh → pratinjau → terapkan → batalkan + `superseded_by`.

Data uji ditanam langsung (produk/induk/SO bertanda `TPA<tag>`) dan DIHAPUS di akhir. Butuh backend yang sudah
memuat kode PREP-A (HTTP) + Mongo yang sama (pymongo, untuk menanam & memeriksa).

Cakupan:
  * fungsi murni: normalisasi nama, typo satu huruf (angka wajib sama), kelompok duplikat, baca CSV/XLSX;
  * unduh lembar (XLSX & CSV ber-BOM), kolom tindakan, saran duplikat, dokumen terbuka; izin `product.export`;
  * pratinjau galat: SKU tak dikenal, tindakan tak dikenal, kolom wajib kosong, kode_benar sudah dipakai, siklus,
    target nonaktif, ID/SKU tak cocok, baris ganda, dokumen terbuka (nomor SO disebut) — TANPA menulis apa pun;
  * terapkan GANTI_NAMA / GANTI_KODE (produk baru + alias supplier pindah + harga PT disalin) / GABUNG_KE (termasuk ke
    kode baru di lembar yang sama) / NONAKTIFKAN; tanda tangan berubah → 409;
  * efek `superseded_by`: `/products` menyaring, `include_superseded`, petunjuk SKU lama, `resolve_active`;
  * batalkan (alasan wajib): semua dipulihkan, produk baru belum dipakai dihapus; yang sudah dipakai dinonaktifkan;
  * izin: sales 403 pratinjau, manager unduh boleh tapi terapkan 403.

Jalankan: cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_a_master_cleanup.py
"""
import csv
import io
import os
import sys
import uuid

import openpyxl
import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _shared_loop import run  # noqa: E402
from services import master_cleanup_refs as refs  # noqa: E402
from services import master_cleanup_sheet as sheet  # noqa: E402
from services import product_supersede as ps  # noqa: E402

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6].upper()
PFX = f"TPA{TAG}"
TPL = f"ptpl_{PFX}"
T0 = "2026-11-01T00:00:00+00:00"


def P(n):
    return f"prod_{PFX}_{n}"


def SKU(n):
    return f"{PFX}-{n}"


def _login(who):
    s = requests.Session()
    s.headers.update({"X-Entity-Id": "ent_ksc"})
    r = s.post(f"{BASE}/auth/login", json={"email": f"{who}@kainnusantara.id", "password": "demo12345"}, timeout=60)
    assert r.status_code == 200, r.text[:200]
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def _prod(n, name, **kw):
    d = {"id": P(n), "sku": SKU(n), "name": name, "category": "Uji PREP-A", "stage": "finished", "fabric_type": "woven",
         "line_code": "woven", "base_unit": "meter", "status": "active", "lifecycle": "produksi", "price": 10000,
         "color": f"Warna {n}", "color_code": f"C{n}", "grade": "A", "gramasi": 120, "lebar": 150,
         "template_id": TPL, "template_name": "Artikel Uji PREP-A", "catalog_version": 2,
         "variant_key": f"vk_{PFX}_{n}", "variant_attrs": {"color": f"Warna {n}"}, "created_at": T0, "updated_at": T0}
    d.update(kw)
    return d


def _cleanup():
    ids = [d["id"] for d in DB.products.find({"$or": [{"id": {"$regex": f"^prod_{PFX}"}}, {"sku": {"$regex": f"^{PFX}"}}]},
                                             {"id": 1})]
    DB.products.delete_many({"id": {"$in": ids}})
    DB.product_templates.delete_many({"id": TPL})
    DB.sales_orders.delete_many({"id": f"so_{PFX}"})
    DB.supplier_items.delete_many({"id": f"sit_{PFX}"})
    DB.entity_prices.delete_many({"$or": [{"id": f"epr_{PFX}"}, {"product_id": {"$in": ids}}]})
    bids = [b["id"] for b in DB.master_cleanup_batches.find({"note": {"$regex": PFX}}, {"id": 1})]
    DB.master_cleanup_batches.delete_many({"id": {"$in": bids}})
    DB.audit_logs.delete_many({"$or": [{"entity_id": {"$in": ids + bids}}]})


@pytest.fixture(scope="module", autouse=True)
def seed():
    _cleanup()
    DB.product_templates.insert_one({"id": TPL, "name": "Artikel Uji PREP-A", "status": "active", "axes": [],
                                     "stage": "finished", "fabric_type": "woven", "base_unit": "meter",
                                     "line_code": "woven", "created_at": T0, "updated_at": T0})
    DB.products.insert_many([
        _prod(1, "Kain Uji Satu Salahketik"),            # GANTI_NAMA
        _prod(2, "Kain Uji Dua", sku=f"{PFX}-2-SALAH"),  # GANTI_KODE → {PFX}-2
        _prod(3, "Kain Uji Tiga"),                       # GABUNG_KE 4
        _prod(4, "Kain Uji Empat"),                      # induk
        _prod(5, "Kain Uji Lima"),                       # NONAKTIFKAN
        _prod(6, "Kain Uji Enam"),                       # punya SO terbuka
        _prod(7, "Kain Uji Tujuh"),                      # GABUNG_KE kode baru {PFX}-2
        _prod(8, "Kain Uji Delapan"), _prod(9, "Kain Uji Sembilan"),   # siklus
        _prod(10, "Kain Uji Sepuluh", status="inactive"),              # target nonaktif
        _prod(11, "Kain Uji Sebelas"),                                 # atribut kanonik sama → calon duplikat
        _prod(12, "Kain Uji  sebelas", color="Warna 11", color_code="C11"),
    ])
    DB.sales_orders.insert_one({"id": f"so_{PFX}", "number": f"SO-{PFX}-01", "status": "confirmed", "entity_id": "ent_ksc",
                                "items": [{"product_id": P(6), "sku": SKU(6), "quantity": 5}], "created_at": T0})
    DB.supplier_items.insert_one({"id": f"sit_{PFX}", "supplier_id": f"sup_{PFX}", "supplier_sku": f"S-{PFX}",
                                  "product_id": P(2), "sku": f"{PFX}-2-SALAH", "status": "active", "created_at": T0})
    DB.entity_prices.insert_one({"id": f"epr_{PFX}", "product_id": P(2), "entity_id": "ent_ksc", "sell_price": 12000,
                                 "status": "active", "created_at": T0})
    yield
    _cleanup()


@pytest.fixture(scope="module")
def adm():
    return _login("admin")


# ─── fungsi murni ────────────────────────────────────────────────────────────
def test_normalisasi_dan_typo():
    assert refs.norm_name("Alice  Knit (94139-45) 10 A") == refs.norm_name("alice knit 94139 - 45 10A")
    assert refs.one_edit_apart("katunsatu", "katunsatu".replace("u", "o", 1))
    assert refs.one_edit_apart("katunsatu", "katunsat")
    assert not refs.one_edit_apart("katunsatu", "katunsatu")
    assert not refs.one_edit_apart("katunsatu", "kotonsatu")


def test_kelompok_duplikat_atribut_dan_nama():
    base = {"stage": "finished", "fabric_type": "woven", "line_code": "woven", "color_code": "C1", "grade": "A",
            "base_unit": "meter", "status": "active"}
    rows = [{**base, "id": "a", "sku": "A1", "name": "Rayon Kawung Navy", "template_id": "t1"},
            {**base, "id": "b", "sku": "B1", "name": "Rayon  Kawung navy", "template_id": "t2"},
            {**base, "id": "c", "sku": "C1", "name": "Rayon Kawong Navy", "template_id": "t3"},
            {**base, "id": "d", "sku": "D1", "name": "Rayon Kawung Navy 121", "template_id": "t4"},
            {**base, "id": "e", "sku": "E1", "name": "Rayon Kawung Navy 120", "template_id": "t5"}]
    g = refs.duplicate_groups(rows, {"b": 5})
    assert g["a"]["group"] == g["b"]["group"] == g["c"]["group"]
    assert g["b"]["is_parent"] and g["a"]["parent_sku"] == "B1"           # pemakaian terbanyak = saran induk
    assert "d" not in g and "e" not in g                                    # angka beda ≠ typo


def test_baca_csv_dan_xlsx():
    out = io.StringIO()
    out.write("# petunjuk\r\n")
    w = csv.writer(out, delimiter=";")
    w.writerow(["id", "sku", "nama", "tindakan", "kode_benar"])
    w.writerow(["p1", "'-AB", "x", "ganti kode", "10023"])
    rows = sheet.parse_sheet(("﻿" + out.getvalue()).encode(), "a.csv")
    assert rows == [{"row": 3, "id": "p1", "sku": "-AB", "tindakan": "ganti kode", "kode_benar": "10023"}]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Produk"
    ws.append(["id", "sku", "tindakan", "kode_benar"])
    ws.append(["p2", "X", "GANTI_KODE", 10023.0])
    buf = io.BytesIO()
    wb.save(buf)
    rows = sheet.parse_sheet(buf.getvalue(), "a.xlsx")
    assert rows[0]["kode_benar"] == "10023" and rows[0]["row"] == 2
    with pytest.raises(Exception):
        sheet.parse_sheet(b"id,nama\n1,x\n", "a.csv")


# ─── unduh ───────────────────────────────────────────────────────────────────
def test_unduh_xlsx_dan_csv(adm):
    r = adm.get(f"{BASE}/master-governance/cleanup/sheet", timeout=120)
    assert r.status_code == 200, r.text[:300]
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Produk", "Petunjuk"]
    rows = list(wb["Produk"].iter_rows(values_only=True))
    head = list(rows[0])
    for c in ("id", "sku", "artikel", "kode_warna", "gramasi", "lebar", "stok_ringkas", "dok_terbuka_nomor",
              "kelompok_duplikat", "saran_kode_induk", "tindakan", "nama_benar", "kode_benar", "digantikan_oleh_sku", "catatan"):
        assert c in head, c
    mine = {x[1]: dict(zip(head, x)) for x in rows[1:] if str(x[1]).startswith(PFX)}
    assert mine[SKU(6)]["dok_terbuka"] == 1 and f"SO-{PFX}-01" in mine[SKU(6)]["dok_terbuka_nomor"]
    assert mine[SKU(11)]["kelompok_duplikat"] and mine[SKU(11)]["kelompok_duplikat"] == mine[SKU(12)]["kelompok_duplikat"]
    assert mine[SKU(1)]["artikel"] == "Artikel Uji PREP-A"
    r = adm.get(f"{BASE}/master-governance/cleanup/sheet", params={"format": "csv"}, timeout=120)
    assert r.status_code == 200 and r.content[:3] == b"\xef\xbb\xbf"
    back = sheet.parse_sheet(r.content, "lembar.csv")          # lembar CSV sendiri terbaca ulang
    assert back[0]["row"] == 5 and {x["sku"] for x in back} >= {SKU(1), SKU(6)}   # 3 baris petunjuk + kepala


# ─── pratinjau galat ─────────────────────────────────────────────────────────
def _upload(sess, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Produk"
    cols = ["id", "sku", "tindakan", "nama_benar", "kode_benar", "digantikan_oleh_sku", "catatan"]
    ws.append(cols)
    for r in rows:
        ws.append([r.get(c, "") for c in cols])
    buf = io.BytesIO()
    wb.save(buf)
    return sess.post(f"{BASE}/master-governance/cleanup/preview", timeout=120,
                     files={"file": ("lembar.xlsx", buf.getvalue(), sheet_media())})


def sheet_media():
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_pratinjau_galat_tanpa_menulis(adm):
    before = list(DB.products.find({"id": {"$regex": f"^prod_{PFX}"}}, {"_id": 0}).sort("id", 1))
    r = _upload(adm, [
        {"sku": f"{PFX}-TIDAKADA", "tindakan": "NONAKTIFKAN"},
        {"sku": SKU(1), "tindakan": "HAPUS"},
        {"sku": SKU(3), "tindakan": "GANTI_KODE"},
        {"sku": SKU(5), "tindakan": "ganti kode", "kode_benar": SKU(4).lower()},   # beda huruf tetap terpakai
        {"sku": SKU(8), "tindakan": "GABUNG_KE", "digantikan_oleh_sku": SKU(9)},
        {"sku": SKU(9), "tindakan": "GABUNG_KE", "digantikan_oleh_sku": SKU(8)},
        {"sku": SKU(11), "tindakan": "GABUNG_KE", "digantikan_oleh_sku": SKU(10)},
        {"id": P(1), "sku": SKU(4), "tindakan": "GANTI_NAMA", "nama_benar": "x"},
        {"sku": SKU(12), "tindakan": "NONAKTIFKAN"}, {"sku": SKU(12), "tindakan": "NONAKTIFKAN"},
        {"sku": SKU(6), "tindakan": "GANTI_KODE", "kode_benar": f"{PFX}-6B"},
        {"sku": SKU(7), "tindakan": "GANTI_NAMA"},
    ])
    assert r.status_code == 200, r.text[:300]
    pv = r.json()
    assert not pv["can_apply"] and pv["summary"]["errors"] >= 11
    err = {x["row"]: " ".join(x["errors"]) for x in pv["rows"]}
    assert "tidak dikenal" in err[2]
    assert "Tindakan 'HAPUS' tidak dikenal" in err[3]
    assert "kode_benar untuk GANTI_KODE" in err[4]
    assert "sudah dipakai" in err[5] and "GABUNG_KE" in err[5]
    assert "Siklus" in err[6] and "Siklus" in err[7]
    assert "nonaktif" in err[8]
    assert "tidak cocok" in err[9]
    assert "sudah punya tindakan di baris 10" in err[11]
    assert f"SO SO-{PFX}-01" in err[12] and "dokumen terbuka" in err[12]
    assert "nama_benar untuk GANTI_NAMA" in err[13]
    after = list(DB.products.find({"id": {"$regex": f"^prod_{PFX}"}}, {"_id": 0}).sort("id", 1))
    assert before == after                                                   # pratinjau tidak menulis apa pun


# ─── terapkan + efek + batalkan ──────────────────────────────────────────────
VALID = [
    {"id": P(1), "sku": SKU(1), "tindakan": "GANTI_NAMA", "nama_benar": "Kain Uji Satu"},
    {"id": P(2), "sku": f"{PFX}-2-SALAH", "tindakan": "GANTI_KODE", "kode_benar": SKU(2), "catatan": "kode salah"},
    {"id": P(3), "sku": SKU(3), "tindakan": "GABUNG_KE", "digantikan_oleh_sku": SKU(4)},
    {"id": P(5), "sku": SKU(5), "tindakan": "NONAKTIFKAN"},
    {"id": P(7), "sku": SKU(7), "tindakan": "GABUNG_KE", "digantikan_oleh_sku": SKU(2)},
    {"id": P(4), "sku": SKU(4), "tindakan": "PERTAHANKAN"},
]
STATE = {}


def test_pratinjau_valid_lalu_terapkan(adm):
    pv = _upload(adm, VALID).json()
    assert pv["can_apply"], pv
    s = pv["summary"]
    assert (s["GANTI_NAMA"], s["GANTI_KODE"], s["GABUNG_KE"], s["NONAKTIFKAN"], s["pertahankan"]) == (1, 1, 2, 1, 1)
    body = {"actions": pv["actions"], "preview_signature": pv["preview_signature"], "note": f"Uji {PFX}"}
    assert adm.post(f"{BASE}/master-governance/cleanup/apply", json={**body, "note": "x"}, timeout=60).status_code == 422
    assert adm.post(f"{BASE}/master-governance/cleanup/apply", json={**body, "preview_signature": "basi"},
                    timeout=60).status_code == 409
    r = adm.post(f"{BASE}/master-governance/cleanup/apply", json=body, timeout=120)
    assert r.status_code == 200, r.text[:400]
    b = r.json()
    assert b["status"] == "applied" and b["changed"] == 5 and not b.get("saga_lock"), b
    STATE["batch"] = b["id"]
    p1 = DB.products.find_one({"id": P(1)})
    assert p1["name"] == "Kain Uji Satu" and p1["name_history"][-1]["batch"] == b["id"] and p1["sku"] == SKU(1)
    old2 = DB.products.find_one({"id": P(2)})
    new2 = DB.products.find_one({"sku": SKU(2)})
    assert old2["sku"] == f"{PFX}-2-SALAH" and old2["status"] == "inactive" and old2["superseded_by"] == new2["id"]
    assert new2["status"] == "active" and new2["template_id"] == TPL and new2["variant_key"] == f"vk_{PFX}_2"
    assert new2["price"] == 10000 and new2["replaces_skus"] == [f"{PFX}-2-SALAH"] and new2["color_code"] == "C2"
    assert DB.supplier_items.find_one({"id": f"sit_{PFX}"})["product_id"] == new2["id"]
    assert DB.entity_prices.find_one({"product_id": new2["id"]})["sell_price"] == 12000
    assert DB.entity_prices.find_one({"id": f"epr_{PFX}"})["product_id"] == P(2)     # harga lama tidak diubah
    assert DB.products.find_one({"id": P(3)})["superseded_by"] == P(4)
    assert DB.products.find_one({"id": P(7)})["superseded_by"] == new2["id"]
    p5 = DB.products.find_one({"id": P(5)})
    assert p5["status"] == "inactive" and not p5.get("superseded_by")
    STATE["new2"] = new2["id"]


def test_efek_superseded_pemilih_dan_petunjuk(adm):
    ids = {p["id"] for p in adm.get(f"{BASE}/products", timeout=120).json()}
    assert P(3) not in ids and P(2) not in ids and P(4) in ids and STATE["new2"] in ids
    ids_all = {p["id"] for p in adm.get(f"{BASE}/products", params={"include_superseded": "true"}, timeout=120).json()}
    assert P(3) in ids_all
    h = adm.get(f"{BASE}/master-governance/supersede-hint", params={"q": f"{PFX}-2-salah"}, timeout=60).json()
    assert h and h[0]["superseded_by"]["sku"] == SKU(2) and f"digantikan oleh {SKU(2)}" in h[0]["message"]
    assert run(ps.resolve_active(P(7)))["id"] == STATE["new2"]
    assert run(ps.resolve_active(P(4)))["id"] == P(4)
    dash = {p["id"]: p for p in adm.get(f"{BASE}/dashboard", timeout=120).json()["products"]}
    assert dash[P(3)]["superseded_by_sku"] == SKU(4)                       # riwayat/stok tetap melihat SKU lama


def test_izin(adm):
    sales, mgr = _login("sales"), _login("manager")
    assert _upload(sales, VALID).status_code == 403
    assert mgr.get(f"{BASE}/master-governance/cleanup/sheet", timeout=120).status_code == 200
    assert mgr.post(f"{BASE}/master-governance/cleanup/apply", json={}, timeout=60).status_code == 403
    assert sales.post(f"{BASE}/master-governance/cleanup/batches/{STATE['batch']}/rollback",
                      json={"reason": "uji izin"}, timeout=60).status_code == 403
    assert any(b["id"] == STATE["batch"] for b in adm.get(f"{BASE}/master-governance/cleanup/batches", timeout=60).json())


def test_batalkan_memulihkan_semua(adm):
    bid = STATE["batch"]
    assert adm.post(f"{BASE}/master-governance/cleanup/batches/{bid}/rollback", json={"reason": "x"},
                    timeout=60).status_code == 422
    r = adm.post(f"{BASE}/master-governance/cleanup/batches/{bid}/rollback", json={"reason": f"Uji batal {PFX}"}, timeout=120)
    assert r.status_code == 200, r.text[:400]
    b = r.json()
    assert b["status"] == "rolled_back" and not b["rollback_skipped"], b
    assert DB.products.find_one({"id": P(1)})["name"] == "Kain Uji Satu Salahketik"
    for n in (2, 3, 5, 7):
        p = DB.products.find_one({"id": P(n)})
        assert p["status"] == "active" and not p.get("superseded_by") and not p.get("last_cleanup_batch"), n
    assert DB.products.find_one({"id": P(2)})["variant_key"] == f"vk_{PFX}_2"
    assert DB.products.find_one({"id": STATE["new2"]}) is None                 # belum dipakai → dihapus
    assert DB.supplier_items.find_one({"id": f"sit_{PFX}"})["product_id"] == P(2)
    assert DB.entity_prices.count_documents({"product_id": STATE["new2"]}) == 0
    assert adm.post(f"{BASE}/master-governance/cleanup/batches/{bid}/rollback", json={"reason": "kedua kali"},
                    timeout=60).status_code == 409


def test_batalkan_produk_baru_yang_sudah_dipakai_dinonaktifkan(adm):
    pv = _upload(adm, [VALID[1]]).json()
    b = adm.post(f"{BASE}/master-governance/cleanup/apply", timeout=120, json={
        "actions": pv["actions"], "preview_signature": pv["preview_signature"], "note": f"Uji pakai {PFX}"}).json()
    nid = DB.products.find_one({"sku": SKU(2)})["id"]
    DB.sales_orders.update_one({"id": f"so_{PFX}"}, {"$push": {"items": {"product_id": nid, "quantity": 1}}})
    r = adm.post(f"{BASE}/master-governance/cleanup/batches/{b['id']}/rollback", json={"reason": f"Uji batal {PFX}"},
                 timeout=120).json()
    assert r["status"] == "rolled_back" and "dinonaktifkan" in r["rollback_done"][0]["result"], r
    new = DB.products.find_one({"id": nid})
    assert new["status"] == "inactive" and new["superseded_by"] == P(2) and new["variant_key"] != f"vk_{PFX}_2"
    old = DB.products.find_one({"id": P(2)})
    assert old["status"] == "active" and old["variant_key"] == f"vk_{PFX}_2"
