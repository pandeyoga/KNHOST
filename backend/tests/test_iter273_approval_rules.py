"""ITER-273 — Aturan Persetujuan: kontrak baca (skema mesin) + integrasi mesin evaluate.

KP-T4 (disesuaikan — perilaku yang sengaja diubah): `POST/PATCH/DELETE /api/approval-rules` dimatikan (410). Validasi &
integrasi mesin kini lewat `PUT/DELETE /api/approval-policies/{doc_kind}` (satu tabel kebijakan); baca daftar lama tetap.
"""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"
ENTITY = "ent_ksc"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": "admin@kainnusantara.id",
                                          "password": "demo12345"}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    if not token:
        pytest.fail(f"no token in login response: {r.text[:300]}")
    s.headers.update({"Authorization": f"Bearer {token}", "X-Entity-Id": ENTITY})
    return s


# ── GET list: skema mesin & sort ─────────────────────────────────────────────
class TestListContract:
    def test_list_has_engine_schema_and_sorted(self, client):
        r = client.get(f"{API}/approval-rules", timeout=30)
        assert r.status_code == 200, r.text[:300]
        rules = r.json()
        assert isinstance(rules, list)
        # KP-T3 — dua baris benih `discount` dibuang (dan tidak lagi ditampilkan): 1 SO + 2 PO + 2 PR = 5.
        assert len(rules) >= 5, f"expected >=5 seed rules, got {len(rules)}"
        for rule in rules:
            assert "_id" not in rule
            for f in ("id", "doc_type", "min_amount", "required_role", "sort", "active"):
                assert f in rule, f"missing {f} in {rule}"
            assert "max_amount" in rule
            # KP-T3 — jenis yang tidak dinilai mesin tidak ditampilkan; peran = registry (label + role_known).
            assert rule["doc_type"] in ["sales_order", "purchase_order", "purchase_requisition"]
            assert "required_role_label" in rule and isinstance(rule["role_known"], bool)
            assert isinstance(rule["active"], bool)
            # tidak ada skema paralel yang bocor
            assert "threshold_min" not in rule and "is_active" not in rule
        keys = [(x["doc_type"], x["sort"]) for x in rules]
        assert keys == sorted(keys), f"not sorted by doc_type,sort: {keys}"

    def test_seed_rules_all_active(self, client):
        rules = client.get(f"{API}/approval-rules", timeout=30).json()
        seeded = [r for r in rules if not (r.get("description") or "").startswith("TEST_")]
        inactive = [r["id"] for r in seeded if r["active"] is False]
        assert not inactive, f"seed rules inactive: {inactive}"

    def test_filter_by_doc_type(self, client):
        r = client.get(f"{API}/approval-rules?doc_type=purchase_order", timeout=30)
        assert r.status_code == 200
        assert all(x["doc_type"] == "purchase_order" for x in r.json())
        # KP-T3 — aturan `discount` lama tidak ditampilkan
        assert client.get(f"{API}/approval-rules?doc_type=discount", timeout=30).json() == []


# ── KP-T4 — jalur tulis lama dimatikan; validasi di jalur baru ───────────────
PINDAH = "Aturan Persetujuan kini diatur per jenis dokumen"


class TestJalurLamaDimatikan:
    def test_post_patch_delete_410(self, client):
        rid = client.get(f"{API}/approval-rules", timeout=30).json()[0]["id"]
        for r in (client.post(f"{API}/approval-rules", json={"doc_type": "sales_order", "min_amount": 0}, timeout=30),
                  client.patch(f"{API}/approval-rules/{rid}", json={"min_amount": 1}, timeout=30),
                  client.delete(f"{API}/approval-rules/{rid}", timeout=30)):
            assert r.status_code == 410, f"{r.status_code}: {r.text[:200]}"
            assert r.json()["detail"].startswith(PINDAH)


class TestValidationBaru:
    def _put(self, client, kind, levels, version=0, reason="TEST_iter273"):
        return client.put(f"{API}/approval-policies/{kind}", json={
            "entity_id": ENTITY, "expected_version": version, "reason": reason, "levels": levels}, timeout=30)

    def test_bad_doc_kind_400(self, client):
        assert self._put(client, "invoice", []).status_code == 400

    def test_bad_role_400(self, client):
        r = self._put(client, "sales_order.nilai", [{"level": 1, "tiers": [{"min_amount": 0, "roles": ["supervisor"]}]}])
        assert r.status_code == 400 and r.json()["detail"] == "Peran “supervisor” tidak ada.", r.text[:200]

    def test_max_le_min_400(self, client):
        r = self._put(client, "sales_order.nilai",
                      [{"level": 1, "tiers": [{"min_amount": 500, "max_amount": 500, "roles": ["manager"]}]}])
        assert r.status_code == 400, r.text[:200]

    def test_no_reason_400(self, client):
        r = self._put(client, "sales_order.nilai", [{"level": 1, "tiers": [{"min_amount": 0, "roles": []}]}],
                      reason="")
        assert r.status_code == 400 and r.json()["detail"] == "Alasan perubahan wajib diisi.", r.text[:200]


# ── INTEGRASI MESIN: aturan dari layar harus dibaca evaluate_approval ────────
class TestEngineIntegration:
    def test_rule_drives_evaluate_and_removal_restores(self, client):
        base = client.get(f"{API}/settings/evaluate-approval",
                          params={"doc_type": "sales_order", "amount": 1500, "entity_id": ENTITY}, timeout=30)
        assert base.status_code == 200, base.text[:300]
        baseline = base.json()
        view = client.get(f"{API}/approval-policies", params={"entity_id": ENTITY, "doc_kind": "sales_order.nilai"},
                          timeout=30).json()["kinds"][0]
        version = view["version"] if view["source"] == "pt" else 0
        r = client.put(f"{API}/approval-policies/sales_order.nilai", json={
            "entity_id": ENTITY, "expected_version": version, "reason": "TEST_iter273_engine",
            "levels": [{"level": 1, "tiers": [{"min_amount": 0, "max_amount": 1000, "roles": []},
                                              {"min_amount": 1000, "max_amount": 2000, "roles": ["admin"]},
                                              {"min_amount": 2000, "max_amount": None, "roles": []}]}]}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        try:
            ev = client.get(f"{API}/settings/evaluate-approval",
                            params={"doc_type": "sales_order", "amount": 1500, "entity_id": ENTITY}, timeout=30)
            assert ev.status_code == 200, ev.text[:300]
            data = ev.json()
            assert data["requires_approval"] is True, data
            assert data["required_role"] == "admin", data
        finally:
            d = client.delete(f"{API}/approval-policies/sales_order.nilai",
                              params={"entity_id": ENTITY, "reason": "TEST_iter273 pulihkan"}, timeout=30)
            assert d.status_code == 200
        after = client.get(f"{API}/settings/evaluate-approval",
                           params={"doc_type": "sales_order", "amount": 1500, "entity_id": ENTITY}, timeout=30).json()
        assert after.get("required_role") == baseline.get("required_role"), f"baseline {baseline} vs after {after}"
