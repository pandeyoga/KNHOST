"""KF-T5 — di MongoDB ASLI (lingkungan A) dengan data acuan: aturan khusus per pelanggan/barang lewat API.

Unit ini tidak punya butir uji lapis A wajib selain uji jalan layar U14–U15 (U1–U13 di
`backend/tests_mem/test_KFT5_aturan_khusus.py`). Berkas ini pelengkap untuk data acuan (`scripts/dev_restore_demo.sh`):
(1) mencetak hitungan baris `config_values` ber-`scope_type` `customer`/`product` yang sudah ada (bagian RISIKO
spesifikasi — nilai yang dulu diisi lewat API kini terlihat); (2) satu aturan khusus ditulis untuk pelanggan dan barang
NYATA di data acuan lalu dicabut lagi (`POST /api/config/values/clear`); (3) penolakan sasaran tak ada / kunci lot.
Jalankan dengan `-s` untuk melihat hitungan. Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`);
pembacaan langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.
"""
import os

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ALASAN = "uji KF-T5 lapis A"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _butir(h, scope, sid, key, entity_id=""):
    param = "customer_id" if scope == "customer" else "product_id"
    r = requests.get(f"{BASE}/config/effective", headers=h, timeout=30,
                     params={"scope": scope, param: sid, "entity_id": entity_id})
    assert r.status_code == 200, r.text
    items = {it["key"]: it for it in r.json()["items"]}
    return items, items[key]


def test_KFT5_A_hitungan_lapisan_pelanggan_barang_di_data_acuan():
    for lapisan in ("customer", "product"):
        semua = DB.config_values.count_documents({"scope_type": lapisan})
        per_kunci = sorted(DB.config_values.distinct("key", {"scope_type": lapisan}))
        print(f"[KF-T5] config_values scope_type={lapisan}: {semua} baris; kunci: {per_kunci}")
    lot = DB.config_values.count_documents({"scope_type": "customer", "key": {"$in": [
        "allocation.lot_mode", "allocation.dye_lot_strict"]}})
    print(f"[KF-T5] baris lapisan pelanggan allocation.* (tidak lagi dibaca resolver): {lot}")


def test_KFT5_A_pelanggan_data_acuan_atur_lalu_kembali():
    h = _login()
    c = DB.customers.find_one({"entity_id": "ent_ksc", "status": {"$ne": "merged"}}, {"_id": 0, "id": 1, "name": 1})
    assert c, "data acuan tidak punya pelanggan ent_ksc"
    key = "ar.grace_days"
    items, awal = _butir(h, "customer", c["id"], key, "ent_ksc")
    assert len(items) == 8 and "inherited_value" in awal
    target = int(awal["inherited_value"] or 0) + 3
    try:
        r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [
            {"key": key, "value": target, "scope_type": "customer", "scope_id": c["id"], "reason": ALASAN}]})
        assert r.status_code == 200, r.text
        _, it = _butir(h, "customer", c["id"], key, "ent_ksc")
        assert it["layer_value"] == target and it["inherited_value"] == awal["inherited_value"]
        r = requests.get(f"{BASE}/config/layers", headers=h, params={"key": key, "scope_type": "customer"}, timeout=30)
        assert r.status_code == 200, r.text
        assert any(x["scope_id"] == c["id"] and x["scope_label"] == c["name"] and x["value"] == target
                   for x in r.json()["rows"])
    finally:
        requests.post(f"{BASE}/config/values/clear", headers=h, timeout=30, json={
            "key": key, "scope_type": "customer", "scope_id": c["id"], "reason": ALASAN})
    _, akhir = _butir(h, "customer", c["id"], key, "ent_ksc")
    assert akhir["layer_value"] == awal["layer_value"]


def test_KFT5_A_barang_data_acuan_atur_lalu_kembali():
    h = _login()
    p = DB.products.find_one({}, {"_id": 0, "id": 1, "name": 1})
    assert p, "data acuan tidak punya barang"
    key = "cutting.waste_limit_pct"
    items, awal = _butir(h, "product", p["id"], key, "ent_ksc")
    assert len(items) == 3
    try:
        r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [
            {"key": key, "value": 7, "scope_type": "product", "scope_id": p["id"], "reason": ALASAN}]})
        assert r.status_code == 200, r.text
        _, it = _butir(h, "product", p["id"], key, "ent_ksc")
        assert it["layer_value"] == 7
    finally:
        requests.post(f"{BASE}/config/values/clear", headers=h, timeout=30, json={
            "key": key, "scope_type": "product", "scope_id": p["id"], "reason": ALASAN})
    _, akhir = _butir(h, "product", p["id"], key, "ent_ksc")
    assert akhir["layer_value"] == awal["layer_value"]


def test_KFT5_A_penolakan_tanpa_baris_baru():
    h = _login()
    c = DB.customers.find_one({"entity_id": "ent_ksc"}, {"_id": 0, "id": 1})
    sebelum = DB.config_values.count_documents({})
    kasus = [("ar.grace_days", 5, "customer", "kft5_tidak_ada", 404, "Pelanggan tidak ditemukan."),
             ("cutting.waste_limit_pct", 5, "product", "kft5_tidak_ada", 404, "Barang tidak ditemukan."),
             ("allocation.lot_mode", "strict_single", "customer", c["id"], 400,
              "“Kebijakan campur lot” tidak bisa dibedakan per pelanggan."),
             ("ar.grace_days", 5, "supplier", "x", 400, "Aturan khusus per pemasok atau per dokumen belum tersedia.")]
    for key, val, lapisan, sid, kode, pesan in kasus:
        r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [
            {"key": key, "value": val, "scope_type": lapisan, "scope_id": sid, "reason": ALASAN}]})
        assert r.status_code == kode and r.json()["detail"] == pesan, (key, r.text)
    assert DB.config_values.count_documents({}) == sebelum
