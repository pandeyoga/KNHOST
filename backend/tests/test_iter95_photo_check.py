"""Iter95 — /api/goods-receipts/photo-check endpoint tests."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ENT = "ent_ksc"
FIX = "/app/tests/fixtures_sj"


def _token(email, pw="demo12345"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_token('admin@kainnusantara.id')}", "X-Entity-Id": ENT}


def _post(headers, path, mime):
    with open(path, "rb") as fh:
        r = requests.post(f"{BASE}/api/goods-receipts/photo-check",
                          headers=headers,
                          files={"file": (os.path.basename(path), fh, mime)},
                          timeout=90)
    return r


def test_photo_check_good(admin_headers):
    r = _post(admin_headers, f"{FIX}/n_d.jpeg", "image/jpeg")
    assert r.status_code == 200, r.text
    j = r.json()
    print("GOOD:", j)
    assert j["checked"] is True
    for k in ("is_document", "cut_off_sides", "blurry", "glare_or_shadow", "legibility", "advice"):
        assert k in j
    assert j["legibility"] in ("jelas", "sebagian", "buruk")
    # Should be a good doc — legibility jelas & not blurry
    assert j["blurry"] is False
    assert j["legibility"] in ("jelas", "sebagian")


def test_photo_check_blur(admin_headers):
    r = _post(admin_headers, f"{FIX}/q_blur.jpg", "image/jpeg")
    assert r.status_code == 200, r.text
    j = r.json()
    print("BLUR:", j)
    assert j["checked"] is True
    assert j["blurry"] is True or j["legibility"] == "buruk"


def test_photo_check_cut(admin_headers):
    r = _post(admin_headers, f"{FIX}/q_cut.jpg", "image/jpeg")
    assert r.status_code == 200, r.text
    j = r.json()
    print("CUT:", j)
    assert j["checked"] is True
    assert "bawah" in (j.get("cut_off_sides") or [])


def test_photo_check_non_image(admin_headers):
    # Send a text file
    r = requests.post(f"{BASE}/api/goods-receipts/photo-check",
                      headers=admin_headers,
                      files={"file": ("note.txt", b"hello world not an image", "text/plain")},
                      timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    print("NON_IMAGE:", j)
    assert j["checked"] is False
    assert j["reason"] == "not_image"


def test_usage_log_photo_check(admin_headers):
    # After calls above, ai_usage_log should have role=photo_check entries for this entity
    # Verify via list endpoint indirectly — we just check the endpoint responded ok.
    # Instead, hit /api/goods-receipts/usage (approve perm) — admin has approve.
    r = requests.get(f"{BASE}/api/goods-receipts/usage",
                     headers=admin_headers, timeout=30)
    # This aggregates feature=ocr_dn regardless of role, so should be 200.
    assert r.status_code == 200, r.text


def test_photo_check_no_permission():
    # Try with a role that lacks goods_receipt:create — e.g. sales user if exists.
    try:
        tok = _token("sales@kainnusantara.id")
    except AssertionError:
        pytest.skip("sales user not seeded")
    r = requests.post(f"{BASE}/api/goods-receipts/photo-check",
                      headers={"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT},
                      files={"file": ("x.txt", b"x", "text/plain")}, timeout=30)
    print("NO_PERM:", r.status_code, r.text[:200])
    assert r.status_code == 403
