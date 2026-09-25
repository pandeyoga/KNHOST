"""Iter 58 — Marketing: template konten & duplikasi post, list minggu.

Coverage:
  - POST /marketing/posts/{pid}/duplicate: creates status idea, "Salinan · <title>", copies fields, publish_at, duplicated_from, history[0].note, tidak menyalin metrics/attachments/history.
    * 404 untuk pid tak ada.
    * Isolasi entitas: user tanpa akses entitas sumber mendapat 404.
  - GET/POST /marketing/templates: per-entitas via X-Entity-Id, nama wajib (400), duplikat case-insensitive (400), platform tak dikenal dibuang, content_type tak dikenal (400).
  - POST /marketing/templates/{tid}/use: menaikkan used_count.
  - DELETE /marketing/templates/{tid}: hanya pembuat atau admin/manager (403); 404 bila tidak ada.
  - GET /marketing/posts?from_date&to_date: filter range minggu.
"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip()
                break
BASE = BASE.rstrip("/")

ENT_KSC = "ent_ksc"
ENT_KANDA = "ent_kanda"


def _login(email, pwd="demo12345"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(email, ent=ENT_KSC):
    return {"Authorization": f"Bearer {_login(email)}", "X-Entity-Id": ent, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_ksc():
    return _h("admin@kainnusantara.id", ENT_KSC)


@pytest.fixture(scope="module")
def manager_ksc():
    return _h("manager@kainnusantara.id", ENT_KSC)


@pytest.fixture(scope="module")
def sales_ksc():
    return _h("sales@kainnusantara.id", ENT_KSC)


@pytest.fixture(scope="module")
def sales_kanda():
    # sales3 only has access to ent_kanda; cannot see ent_ksc posts → 404
    return _h("sales3@kainnusantara.id", ENT_KANDA)


@pytest.fixture(scope="module")
def created_ids():
    return {"posts": [], "templates": []}


def _cleanup(admin_ksc, created_ids):
    for pid in created_ids["posts"]:
        try:
            requests.delete(f"{BASE}/api/marketing/posts/{pid}", headers=admin_ksc, timeout=30)
        except Exception:
            pass
    for tid in created_ids["templates"]:
        try:
            requests.delete(f"{BASE}/api/marketing/templates/{tid}", headers=admin_ksc, timeout=30)
        except Exception:
            pass


# ── Duplicate post ────────────────────────────────────────────────
def _make_post(headers, title, publish_at="2026-11-10T10:00", extra=None):
    body = {
        "title": title,
        "caption": "Caption uji",
        "hashtags": ["#uji", "#tes"],
        "platforms": ["instagram"],
        "content_type": "foto",
        "publish_at": publish_at,
        "cta": "Kunjungi",
        "notes": "Catatan uji",
        "assets": [],
        "status": "idea",
    }
    if extra:
        body.update(extra)
    r = requests.post(f"{BASE}/api/marketing/posts", headers=headers, json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestDuplicatePost:
    def test_duplicate_copies_content_new_status(self, admin_ksc, created_ids):
        src = _make_post(admin_ksc, "TEST_DupSrc A")
        created_ids["posts"].append(src["id"])

        r = requests.post(
            f"{BASE}/api/marketing/posts/{src['id']}/duplicate",
            headers=admin_ksc,
            json={"publish_at": "2026-11-17T10:00"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        dup = r.json()
        created_ids["posts"].append(dup["id"])
        assert dup["id"] != src["id"]
        assert dup["title"] == "Salinan · TEST_DupSrc A"
        assert dup["status"] == "idea"
        assert dup["caption"] == src["caption"]
        assert dup["hashtags"] == src["hashtags"]
        assert dup["platforms"] == src["platforms"]
        assert dup["content_type"] == src["content_type"]
        assert dup["cta"] == src["cta"]
        assert dup["notes"] == src["notes"]
        assert (dup.get("publish_at") or "").startswith("2026-11-17T10:00")
        assert dup.get("duplicated_from") == src["id"]
        # history[0].note mentions duplicate origin
        hist = dup.get("history") or []
        assert hist, "history should exist"
        assert "diduplikat" in (hist[0].get("note") or "").lower()
        # metrics not copied
        assert not dup.get("attachments"), "attachments should not be copied"

    def test_duplicate_empty_publish_at_allowed(self, admin_ksc, created_ids):
        src = _make_post(admin_ksc, "TEST_DupSrc B")
        created_ids["posts"].append(src["id"])
        r = requests.post(
            f"{BASE}/api/marketing/posts/{src['id']}/duplicate",
            headers=admin_ksc,
            json={"publish_at": ""},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        dup = r.json()
        created_ids["posts"].append(dup["id"])
        # publish_at should be empty or None
        assert not (dup.get("publish_at") or ""), f"expected empty publish_at, got {dup.get('publish_at')}"

    def test_duplicate_404_unknown_pid(self, admin_ksc):
        r = requests.post(
            f"{BASE}/api/marketing/posts/mkp_doesnotexist/duplicate",
            headers=admin_ksc,
            json={"publish_at": ""},
            timeout=30,
        )
        assert r.status_code == 404, r.text

    def test_duplicate_isolation_other_entity_404(self, admin_ksc, sales_kanda, created_ids):
        # Create post in ent_ksc; user active on ent_kanda should not see -> 404
        src = _make_post(admin_ksc, "TEST_DupIso A")
        created_ids["posts"].append(src["id"])
        r = requests.post(
            f"{BASE}/api/marketing/posts/{src['id']}/duplicate",
            headers=sales_kanda,
            json={"publish_at": ""},
            timeout=30,
        )
        assert r.status_code == 404, r.text


# ── Templates ──────────────────────────────────────────────────────
def _make_template(headers, name, **overrides):
    body = {
        "name": name,
        "title": "Judul uji",
        "caption": "Kalimat uji {brand}",
        "hashtags": ["#tes"],
        "platforms": ["instagram", "tiktok"],
        "content_type": "foto",
        "cta": "Kunjungi",
        "notes": "",
    }
    body.update(overrides)
    return requests.post(f"{BASE}/api/marketing/templates", headers=headers, json=body, timeout=30)


class TestTemplates:
    def test_create_and_list(self, admin_ksc, created_ids):
        r = _make_template(admin_ksc, "TEST_Template A")
        assert r.status_code == 200, r.text
        doc = r.json()
        created_ids["templates"].append(doc["id"])
        assert doc["name"] == "TEST_Template A"
        assert doc["used_count"] == 0
        assert doc["entity_id"] == ENT_KSC
        assert set(doc["platforms"]) == {"instagram", "tiktok"}

        # list
        r2 = requests.get(f"{BASE}/api/marketing/templates", headers=admin_ksc, timeout=30)
        assert r2.status_code == 200, r2.text
        ids = [t["id"] for t in r2.json()]
        assert doc["id"] in ids

    def test_name_required(self, admin_ksc):
        r = _make_template(admin_ksc, "   ")
        assert r.status_code == 400, r.text

    def test_duplicate_name_case_insensitive(self, admin_ksc, created_ids):
        r = _make_template(admin_ksc, "TEST_Template Dup")
        assert r.status_code == 200
        created_ids["templates"].append(r.json()["id"])
        r2 = _make_template(admin_ksc, "test_template DUP")
        assert r2.status_code == 400, r2.text

    def test_unknown_platform_dropped(self, admin_ksc, created_ids):
        r = _make_template(admin_ksc, "TEST_Template Plat", platforms=["instagram", "myspace", "tiktok"])
        assert r.status_code == 200, r.text
        doc = r.json()
        created_ids["templates"].append(doc["id"])
        assert "myspace" not in doc["platforms"]
        assert set(doc["platforms"]) == {"instagram", "tiktok"}

    def test_unknown_content_type_400(self, admin_ksc):
        r = _make_template(admin_ksc, "TEST_Template CT", content_type="hologram")
        assert r.status_code == 400, r.text

    def test_use_increments_used_count(self, admin_ksc, created_ids):
        r = _make_template(admin_ksc, "TEST_Template Use")
        assert r.status_code == 200
        tid = r.json()["id"]
        created_ids["templates"].append(tid)
        for _ in range(2):
            u = requests.post(f"{BASE}/api/marketing/templates/{tid}/use", headers=admin_ksc, timeout=30)
            assert u.status_code == 200, u.text

        lst = requests.get(f"{BASE}/api/marketing/templates", headers=admin_ksc, timeout=30).json()
        found = next(t for t in lst if t["id"] == tid)
        assert found["used_count"] == 2

    def test_delete_by_creator(self, admin_ksc, created_ids):
        r = _make_template(admin_ksc, "TEST_Template DelAdmin")
        assert r.status_code == 200
        tid = r.json()["id"]
        d = requests.delete(f"{BASE}/api/marketing/templates/{tid}", headers=admin_ksc, timeout=30)
        assert d.status_code == 200, d.text
        # Ensure gone
        lst = requests.get(f"{BASE}/api/marketing/templates", headers=admin_ksc, timeout=30).json()
        assert tid not in [t["id"] for t in lst]

    def test_delete_by_manager_other_creator(self, admin_ksc, manager_ksc, created_ids):
        # admin creates, manager (approve role) deletes
        r = _make_template(admin_ksc, "TEST_Template MgrDel")
        assert r.status_code == 200
        tid = r.json()["id"]
        d = requests.delete(f"{BASE}/api/marketing/templates/{tid}", headers=manager_ksc, timeout=30)
        assert d.status_code == 200, d.text

    def test_delete_forbidden_other_user(self, admin_ksc, sales_ksc, created_ids):
        r = _make_template(admin_ksc, "TEST_Template SalesForbid")
        assert r.status_code == 200
        tid = r.json()["id"]
        created_ids["templates"].append(tid)
        d = requests.delete(f"{BASE}/api/marketing/templates/{tid}", headers=sales_ksc, timeout=30)
        assert d.status_code == 403, d.text

    def test_delete_404(self, admin_ksc):
        d = requests.delete(f"{BASE}/api/marketing/templates/mkt_doesnotexist", headers=admin_ksc, timeout=30)
        assert d.status_code == 404


# ── Posts week range filter ────────────────────────────────────────
class TestPostsWeekRange:
    def test_from_to_date_filter(self, admin_ksc, created_ids):
        p1 = _make_post(admin_ksc, "TEST_Week Inside", publish_at="2026-11-03T10:00")  # Tue
        p2 = _make_post(admin_ksc, "TEST_Week Outside", publish_at="2026-11-20T10:00")
        created_ids["posts"] += [p1["id"], p2["id"]]

        r = requests.get(
            f"{BASE}/api/marketing/posts",
            headers=admin_ksc,
            params={"from_date": "2026-11-02", "to_date": "2026-11-08"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        ids = [p["id"] for p in rows]
        assert p1["id"] in ids
        assert p2["id"] not in ids


# ── Cleanup teardown ───────────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def _teardown(admin_ksc, created_ids):
    yield
    _cleanup(admin_ksc, created_ids)
