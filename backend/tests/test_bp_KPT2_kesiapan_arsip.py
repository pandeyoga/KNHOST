"""KP-T2 — di MongoDB ASLI (lingkungan A) dengan data acuan: kesiapan 16 butir, ulangi penyiapan bersamaan, dampak arsip.

Butir U1–U17 diuji di lingkungan B (`backend/tests_mem/test_KPT2_kesiapan_arsip.py`). Berkas ini pelengkap yang hanya
sah di MongoDB asli: (1) data acuan (`scripts/dev_restore_demo.sh`) — semua PT aktif mendapat 16 butir berurutan, tanpa
baris ke layar "Integrasi & Audit", dan kesiapan PT yang dicetak (`-s`) untuk laporan unit; (2) beberapa "Ulangi
penyiapan" BERSAMAAN atas PT yang sama → semua 200 dan penanda lapisan `system_settings{scope: id}` tetap satu dokumen
(upsert; database tiruan tidak menguji balapan, `00_ATURAN_EKSEKUSI.md` §9); (3) pratinjau dampak arsip `ent_kanda`
memuat `employees` dan lima `checks` tanpa menulis apa pun.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); pembacaan dan pembersihan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). PT uji dibuat lewat API lalu dihapus beserta penanda, lapisan pengaturan, pemasok
antar-PT, dan jejaknya. Tidak untuk database berisi data nyata (titik henti H3).
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
URUTAN = ["provisioning", "address", "tax", "doc_prefix", "users", "finance_user", "warehouses", "bank_account",
          "cash_account", "gl_mappings", "period", "payment_term", "prices", "opening_balance", "branding", "signers"]


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_KPT2_A_kesiapan_16_butir_di_data_acuan():
    h = _login()
    rows = requests.get(f"{BASE}/entities", headers=h, params={"status": "active"}, timeout=30)
    assert rows.status_code == 200, rows.text
    for e in rows.json():
        r = requests.get(f"{BASE}/entities/{e['id']}/readiness", headers=h, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert [i["key"] for i in d["items"]] == URUTAN, e["id"]
        assert not [i for i in d["items"] if i.get("view") == "admin"], e["id"]
        print(f"\n{e['id']}: {d['ready']}/{d['total']} — belum: "
              + ", ".join(f"{i['key']} ({i['detail']})" for i in d["items"] if not i["ready"]))


def test_KPT2_A_ulangi_penyiapan_bersamaan_satu_penanda():
    h = _login()
    tag = str(int(time.time()))[-6:]
    r = requests.post(f"{BASE}/entities", headers=h, timeout=60, json={
        "legal_name": f"PT Uji Penyiapan KPT2 {tag}", "short_name": f"KPT2P{tag}", "doc_prefix": f"KP{tag}",
        "type": "PT", "default_tax_mode": "non_ppn"})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    try:
        assert DB.business_entities.find_one({"id": eid})["provisioning"]["coa"] is True
        DB.system_settings.delete_many({"scope": eid})
        with ThreadPoolExecutor(max_workers=6) as ex:
            hasil = list(ex.map(lambda _: requests.post(f"{BASE}/entities/{eid}/provisioning/retry", headers=h,
                                                        timeout=60), range(6)))
        assert [x.status_code for x in hasil] == [200] * 6, [x.text for x in hasil]
        assert DB.system_settings.count_documents({"scope": eid}) == 1
        prov = DB.business_entities.find_one({"id": eid})["provisioning"]
        assert (prov["coa"], prov["config_layer"], prov["group_partners"]) == (True, True, True), prov
    finally:
        DB.business_entities.delete_one({"id": eid})
        DB.system_settings.delete_many({"scope": eid})
        DB.config_values.delete_many({"scope_id": eid})
        DB.suppliers.delete_many({"$or": [{"entity_id": eid}, {"group_entity_id": eid}]})
        DB.audit_logs.delete_many({"entity_id": eid})


def test_KPT2_A_dampak_arsip_kanda_tidak_menulis():
    h = _login()
    sebelum = DB.business_entities.find_one({"id": "ent_kanda"}, {"_id": 0})
    r = requests.get(f"{BASE}/entities/ent_kanda/deactivation-impact", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d["employees"], int)
    assert [c["key"] for c in d["checks"]] == ["pengguna", "dokumen", "saldo", "karyawan", "periode"]
    assert d["can_archive"] == (not d["blockers"])
    assert DB.business_entities.find_one({"id": "ent_kanda"}, {"_id": 0}) == sebelum
    print("\nent_kanda checks:", [(c["key"], c["ok"], c["detail"]) for c in d["checks"]])
