"""Keputusan owner 2026-10-21 (lanjutan ROLE-01) — default izin dipilih implementer, dapat diatur
di matriks izin:
* Antrean QC kedatangan: lihat = wms.view ATAU qc.view; putus karantina = wms.update ATAU qc.release.
* Kebijakan Retur & Asumsi Retur (bagian `returns` PUT /settings) = sales_return.policy.
* Master Entitas: izin tulis per jenis = izin domain layar khususnya (+ `can` per operasi di daftar).
Hanya memakai ID yang tidak ada (penjaga diuji tanpa mengubah data) kecuali satu PUT /settings yang
dipulihkan dari salinan DB. Butuh data acuan (`bash scripts/dev_restore_demo.sh`).
Jalankan: cd /app/backend && python -m pytest tests/test_role01_matrix_defaults.py -p no:randomly -n 0 -q
"""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {k: _login(e) for k, e in (("qc", "qc@kainnusantara.id"), ("manager", "manager@kainnusantara.id"),
                                      ("finance", "finance@kainnusantara.id"), ("mdq", "mdquality@kainnusantara.id"),
                                      ("sales", "sales@kainnusantara.id"))}


# ── QC kedatangan ──────────────────────────────────────────────────────────────
def test_qc_melihat_antrean_lewat_qc_view(H):
    assert requests.get(f"{BASE}/inbound/qc/queue", headers=H["qc"]).status_code == 200
    assert requests.get(f"{BASE}/inbound/qc/queue", headers=H["finance"]).status_code == 403


def test_qc_memutus_karantina_lewat_qc_release(H):
    url = f"{BASE}/inbound/tasks/tsk_tidak_ada/qc-decision"
    assert requests.post(url, json={}, headers=H["qc"]).status_code == 404        # lolos penjaga → dokumen tidak ada
    assert requests.post(url, json={}, headers=H["finance"]).status_code == 403


# ── Kebijakan & Asumsi Retur ───────────────────────────────────────────────────
def test_kebijakan_retur_pakai_sales_return_policy(H):
    url = f"{BASE}/sales-return-policies/srpol_tidak_ada"
    body = {"data": {"notes": "x"}}
    assert requests.patch(url, json=body, headers=H["manager"]).status_code == 404   # lolos penjaga
    assert requests.patch(url, json=body, headers=H["sales"]).status_code == 403


def test_asumsi_retur_manager_boleh_bagian_lain_tetap_entity_update(H):
    before = DB.system_settings.find_one({"scope": "global"}, {"_id": 0})
    try:
        eff = requests.get(f"{BASE}/settings/effective", headers=H["manager"]).json().get("returns") or {}
        r = requests.put(f"{BASE}/settings", json={"scope": "global", "returns": eff}, headers=H["manager"])
        assert r.status_code == 200, r.text
        # bagian lain (pajak) tetap butuh entity.update — Manager tidak punya
        assert requests.put(f"{BASE}/settings", json={"scope": "global", "tax": {}}, headers=H["manager"]).status_code == 403
        # payload campuran menuntut semua izin
        mixed = {"scope": "global", "returns": eff, "tax": {}}
        assert requests.put(f"{BASE}/settings", json=mixed, headers=H["manager"]).status_code == 403
        assert requests.put(f"{BASE}/settings", json={"scope": "global", "returns": eff}, headers=H["sales"]).status_code == 403
    finally:
        if before is None:
            DB.system_settings.delete_one({"scope": "global"})
        else:
            DB.system_settings.replace_one({"scope": "global"}, before)


# ── Master Entitas: izin per jenis ─────────────────────────────────────────────
@pytest.mark.parametrize("kind,manager_ok", [
    ("complaint-reasons", True),     # sales_return.policy
    ("expense-categories", True),    # cash_settlement.manage
    ("process-stages", True),        # process_recipe.update
    ("sample-types", True),          # rnd.manage
    ("payment-terms", False),        # entity.update — tetap Admin (sama dengan /payment-terms)
    ("document-templates", False),   # template.update — tetap Admin (sama dengan /document-templates)
    ("product-lines", False),        # product.update — Admin & MD
])
def test_master_entitas_izin_per_jenis(H, kind, manager_ok):
    lst = requests.get(f"{BASE}/entity-masters/{kind}", headers=H["manager"])
    assert lst.status_code == 200, lst.text
    assert lst.json()["can"]["update"] is manager_ok
    code = requests.patch(f"{BASE}/entity-masters/{kind}/row_tidak_ada", json={"data": {"notes": "x"}},
                          headers=H["manager"]).status_code
    assert (code != 403) is manager_ok, code
