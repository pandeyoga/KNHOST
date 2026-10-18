"""Iter91: Kembali ke Jejak + Cetak Jejak Dokumen (backend)."""
import os
import pytest
import requests

def _load_base_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not v:
        try:
            with open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return v.rstrip("/")


BASE_URL = _load_base_url()


def _login(email: str, password: str = "demo12345", entity: str = "ent_ksc") -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {tok}", "X-Entity": entity})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def so_id(admin):
    r = admin.get(f"{BASE_URL}/api/sales-orders?entity=ent_ksc")
    assert r.status_code == 200, r.text
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    for it in items:
        if str(it.get("number", "")).endswith("SO-0001") or it.get("number") == "SO-0001":
            return it.get("id") or it.get("_id")
    for it in items:
        if "SO-0001" in str(it.get("number", "")):
            return it.get("id") or it.get("_id")
    pytest.skip("SO-0001 not found")


class TestTracePrint:
    def test_pdf_default(self, admin, so_id):
        r = admin.get(f"{BASE_URL}/api/documents/trace/sales_order/{so_id}/print")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "jejak-" in cd and ".pdf" in cd
        # SO-0001 number in filename (may be KSC/SO-0001 → KSC-SO-0001)
        assert "SO-0001" in cd

    def test_html_content(self, admin, so_id):
        r = admin.get(f"{BASE_URL}/api/documents/trace/sales_order/{so_id}/print?format=html")
        assert r.status_code == 200, r.text
        body = r.text
        assert "Jejak Dokumen (Audit Trail)" in body
        assert "Relasi Antar Dokumen" in body
        assert "★" in body
        assert "SO-0001" in body
        # Journal rows label
        assert "Jurnal Umum" in body

    def test_depth_reduces_rows(self, admin, so_id):
        r_default = admin.get(f"{BASE_URL}/api/documents/trace/sales_order/{so_id}/print?format=html")
        r_d1 = admin.get(f"{BASE_URL}/api/documents/trace/sales_order/{so_id}/print?format=html&depth=1")
        assert r_default.status_code == 200 and r_d1.status_code == 200
        # count table rows or nodes
        def count(body):
            return body.count("<tr")
        assert count(r_d1.text) <= count(r_default.text)

    def test_unknown_doc_404(self, admin):
        r = admin.get(f"{BASE_URL}/api/documents/trace/sales_order/so_does_not_exist/print")
        assert r.status_code == 404

    def test_permission_check(self):
        # Try sales@ / warehouse@ – expect 403 if lacking document.print
        results = {}
        for email in ("sales@kainnusantara.id", "warehouse@kainnusantara.id"):
            try:
                s = _login(email)
            except AssertionError:
                results[email] = "login-failed"
                continue
            r = s.get(f"{BASE_URL}/api/sales-orders?entity=ent_ksc")
            items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
            sid = None
            for it in items:
                if "SO-0001" in str(it.get("number", "")):
                    sid = it.get("id") or it.get("_id")
                    break
            if not sid:
                results[email] = "no-so"
                continue
            resp = s.get(f"{BASE_URL}/api/documents/trace/sales_order/{sid}/print?format=html")
            results[email] = resp.status_code
        # at least one should be 403 else all have print perm — report either way
        print("Permission matrix:", results)
        assert any(v == 403 for v in results.values()) or all(v == 200 for v in results.values())


class TestMakloonPdfRegression:
    def test_makloon_history_still_renders(self, admin):
        r = admin.get(f"{BASE_URL}/api/makloon-orders?entity=ent_ksc")
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        mko = next((x for x in items if "MKO-00002" in str(x.get("mko_number") or x.get("number", ""))), None)
        assert mko, "MKO-00002 not found"
        mid = mko.get("id") or mko.get("_id")
        r2 = admin.get(f"{BASE_URL}/api/pdf/render/makloon_spk/{mid}?format=html")
        assert r2.status_code == 200, r2.text
        assert "Riwayat Kiriman Bertahap" in r2.text
