"""Iter 61 — Color Library backend tests (validasi PATCH, izin per peran, links, supplier-variants)."""
import os
import time
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ROLES = {
    "admin": ("admin@kainnusantara.id", "demo12345"),
    "manager": ("manager@kainnusantara.id", "demo12345"),
    "md": ("md@kainnusantara.id", "demo12345"),
    "sales": ("sales@kainnusantara.id", "demo12345"),
    "salesadmin": ("salesadmin@kainnusantara.id", "demo12345"),
    "warehouse": ("warehouse@kainnusantara.id", "demo12345"),
    "designer": ("designer@kainnusantara.id", "demo12345"),
    "finance": ("finance@kainnusantara.id", "demo12345"),
}


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in ROLES.items()}


@pytest.fixture(scope="module")
def hdr_admin(tokens):
    return {"Authorization": f"Bearer {tokens['admin']}"}


# ─── GET list & filter ───────────────────────────────────────────────
def test_list_default_active(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library", headers=hdr_admin, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    for row in data:
        assert row.get("status") == "active"
        assert row.get("hex", "").startswith("#")


def test_list_status_all_and_inactive(hdr_admin):
    r_all = requests.get(f"{BASE_URL}/api/color-library", params={"status": "all"}, headers=hdr_admin, timeout=30)
    r_active = requests.get(f"{BASE_URL}/api/color-library", params={"status": "active"}, headers=hdr_admin, timeout=30)
    assert r_all.status_code == 200 and r_active.status_code == 200
    assert len(r_all.json()) >= len(r_active.json())


def test_list_filter_q_family_system(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library", params={"q": "biru"}, headers=hdr_admin, timeout=30)
    assert r.status_code == 200
    r2 = requests.get(f"{BASE_URL}/api/color-library", params={"system": "KN"}, headers=hdr_admin, timeout=30)
    assert r2.status_code == 200
    for row in r2.json():
        assert row.get("system") == "KN"


# ─── Nearest ─────────────────────────────────────────────────────────
def test_nearest_ok(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library/nearest", params={"hex": "#1a2b3c", "limit": 3}, headers=hdr_admin, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body.get("query_hex") == "#1A2B3C"
    assert isinstance(body.get("results"), list)
    assert len(body["results"]) <= 3


def test_nearest_bad_hex_400(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library/nearest", params={"hex": "notahex"}, headers=hdr_admin, timeout=30)
    assert r.status_code == 400


# ─── Create validation ───────────────────────────────────────────────
def _mk_code():
    return f"TEST-{int(time.time() * 1000) % 10_000_000}"


created_ids = []


def test_create_valid_and_hex_norm(hdr_admin):
    code = _mk_code()
    r = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                      json={"code": code, "name": "TEST Warna A", "hex": "#aabbcc"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == code.upper()
    assert body["hex"].upper() == "#AABBCC"
    assert body["system"] == "KN"  # default when unknown/missing
    assert body["status"] == "active"
    created_ids.append(body["id"])


def test_create_unknown_system_falls_to_KN(hdr_admin):
    code = _mk_code() + "X"
    r = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                      json={"code": code, "name": "TEST Warna Sys", "hex": "#112233", "system": "FOO"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["system"] == "KN"
    created_ids.append(r.json()["id"])


def test_create_duplicate_code_400(hdr_admin):
    code = _mk_code() + "D"
    r = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                      json={"code": code, "name": "TEST Dup", "hex": "#334455"}, timeout=30)
    assert r.status_code == 200
    created_ids.append(r.json()["id"])
    # case-insensitive: sistem menyimpan uppercase; kirim lowercase harusnya juga bentrok
    r2 = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                       json={"code": code.lower(), "name": "TEST Dup2", "hex": "#556677"}, timeout=30)
    assert r2.status_code == 400
    assert "sudah digunakan" in r2.text.lower() or "digunakan" in r2.text.lower()


def test_create_missing_code_or_name_400(hdr_admin):
    r = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                      json={"code": "", "name": "TEST X", "hex": "#000000"}, timeout=30)
    assert r.status_code in (400, 422)
    r2 = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                       json={"code": _mk_code(), "name": "", "hex": "#000000"}, timeout=30)
    assert r2.status_code in (400, 422)


def test_create_bad_hex_400(hdr_admin):
    r = requests.post(f"{BASE_URL}/api/color-library", headers=hdr_admin,
                      json={"code": _mk_code() + "H", "name": "TEST Bad Hex", "hex": "zzz"}, timeout=30)
    assert r.status_code == 400


# ─── PATCH validation ────────────────────────────────────────────────
def _new_color(hdr):
    code = _mk_code() + "P"
    r = requests.post(f"{BASE_URL}/api/color-library", headers=hdr,
                      json={"code": code, "name": "TEST Patchable", "hex": "#010203"}, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    created_ids.append(cid)
    return cid


def test_patch_empty_name_400(hdr_admin):
    cid = _new_color(hdr_admin)
    r = requests.patch(f"{BASE_URL}/api/color-library/{cid}", headers=hdr_admin,
                       json={"name": "   "}, timeout=30)
    assert r.status_code == 400, r.text
    # nama tetap ada
    got = requests.get(f"{BASE_URL}/api/color-library", params={"status": "all"}, headers=hdr_admin, timeout=30).json()
    row = next(r for r in got if r["id"] == cid)
    assert row["name"] == "TEST Patchable"


def test_patch_bad_status_400(hdr_admin):
    cid = _new_color(hdr_admin)
    r = requests.patch(f"{BASE_URL}/api/color-library/{cid}", headers=hdr_admin,
                       json={"status": "hapus"}, timeout=30)
    assert r.status_code == 400
    # tetap active
    got = requests.get(f"{BASE_URL}/api/color-library", params={"status": "all"}, headers=hdr_admin, timeout=30).json()
    row = next(r for r in got if r["id"] == cid)
    assert row["status"] == "active"


def test_patch_bad_hex_400(hdr_admin):
    cid = _new_color(hdr_admin)
    r = requests.patch(f"{BASE_URL}/api/color-library/{cid}", headers=hdr_admin,
                       json={"hex": "xxxxxx"}, timeout=30)
    assert r.status_code == 400


def test_patch_not_found_404(hdr_admin):
    r = requests.patch(f"{BASE_URL}/api/color-library/col_zzz_noexist", headers=hdr_admin,
                       json={"name": "x"}, timeout=30)
    assert r.status_code == 404


def test_patch_valid_status_toggle(hdr_admin):
    cid = _new_color(hdr_admin)
    r = requests.patch(f"{BASE_URL}/api/color-library/{cid}", headers=hdr_admin,
                       json={"status": "inactive"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"
    r2 = requests.patch(f"{BASE_URL}/api/color-library/{cid}", headers=hdr_admin,
                        json={"status": "active"}, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"


# ─── DELETE (soft) ───────────────────────────────────────────────────
def test_delete_soft_and_404(hdr_admin):
    cid = _new_color(hdr_admin)
    r = requests.delete(f"{BASE_URL}/api/color-library/{cid}", headers=hdr_admin, timeout=30)
    assert r.status_code == 200
    assert r.json().get("deleted") is True
    got = requests.get(f"{BASE_URL}/api/color-library", params={"status": "all"}, headers=hdr_admin, timeout=30).json()
    row = next((r for r in got if r["id"] == cid), None)
    assert row is not None and row["status"] == "inactive"
    r2 = requests.delete(f"{BASE_URL}/api/color-library/col_zzz_noexist", headers=hdr_admin, timeout=30)
    assert r2.status_code == 404


# ─── Permissions per role ────────────────────────────────────────────
@pytest.mark.parametrize("role,expect_view", [
    ("admin", True), ("manager", True), ("md", True), ("sales", True),
    ("salesadmin", True), ("warehouse", True), ("designer", True),
    ("finance", False),
])
def test_view_permissions(tokens, role, expect_view):
    h = {"Authorization": f"Bearer {tokens[role]}"}
    r = requests.get(f"{BASE_URL}/api/color-library", headers=h, timeout=30)
    if expect_view:
        assert r.status_code == 200, f"{role} expected view → got {r.status_code}"
    else:
        assert r.status_code == 403, f"{role} expected 403 → got {r.status_code}"


@pytest.mark.parametrize("role,expect_create", [
    ("admin", True), ("manager", True), ("md", True), ("sales", True),
    ("salesadmin", False), ("warehouse", False), ("designer", False),
    ("finance", False),
])
def test_create_permissions(tokens, role, expect_create):
    h = {"Authorization": f"Bearer {tokens[role]}"}
    code = f"TEST-PERM-{role}-{int(time.time()*1000)%1_000_000}"
    r = requests.post(f"{BASE_URL}/api/color-library", headers=h,
                      json={"code": code, "name": f"TEST perm {role}", "hex": "#abcdef"}, timeout=30)
    if expect_create:
        assert r.status_code == 200, f"{role} expected create → {r.status_code} {r.text}"
        created_ids.append(r.json()["id"])
    else:
        assert r.status_code == 403, f"{role} expected 403 → {r.status_code}"


@pytest.mark.parametrize("role,expect_update", [
    ("admin", True), ("manager", True), ("md", True),
    ("sales", False), ("salesadmin", False), ("warehouse", False),
    ("designer", False), ("finance", False),
])
def test_update_permissions(tokens, hdr_admin, role, expect_update):
    cid = _new_color(hdr_admin)
    h = {"Authorization": f"Bearer {tokens[role]}"}
    r = requests.patch(f"{BASE_URL}/api/color-library/{cid}", headers=h,
                       json={"name": f"TEST update {role}"}, timeout=30)
    if expect_update:
        assert r.status_code == 200, f"{role} expected update → {r.status_code}"
    else:
        assert r.status_code == 403, f"{role} expected 403 → {r.status_code}"


@pytest.mark.parametrize("role,expect_delete", [
    ("admin", True), ("manager", True),
    ("md", False), ("sales", False), ("salesadmin", False),
    ("warehouse", False), ("designer", False), ("finance", False),
])
def test_delete_permissions(tokens, hdr_admin, role, expect_delete):
    cid = _new_color(hdr_admin)
    h = {"Authorization": f"Bearer {tokens[role]}"}
    r = requests.delete(f"{BASE_URL}/api/color-library/{cid}", headers=h, timeout=30)
    if expect_delete:
        assert r.status_code == 200
    else:
        assert r.status_code == 403


# ─── supplier-variants & links (baris nyata) ─────────────────────────
def test_supplier_variants_row_palembang(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library/supplier-variants", headers=hdr_admin, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    match = [x for x in rows if x.get("color_id") == "col_kn_blu_01"
             and x.get("supplier_name") == "Palembang Silk House"
             and x.get("supplier_color_name") == "Navy 07"
             and x.get("supplier_color_code") == "NV-07"]
    assert match, f"Row Palembang·Navy 07 tidak ditemukan. Contoh row: {rows[0] if rows else '-'}"
    row = match[0]
    assert row.get("color_code") == "KN-BLU-01"
    assert row.get("color_products_count", 0) >= 1
    skus = [p["sku"] for p in row.get("products") or []]
    assert "KTN-NVY-PSH-01" in skus, f"Products SKUs: {skus}"


def test_color_links_kn_blu_01(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library/col_kn_blu_01/links", headers=hdr_admin, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body.get("color", {}).get("code") == "KN-BLU-01"
    sv = body.get("supplier_variants") or []
    assert len(sv) >= 1
    with_prod = [v for v in sv if any(p.get("sku") == "KTN-NVY-PSH-01" for p in v.get("products") or [])]
    assert with_prod, "supplier_variant with KTN-NVY-PSH-01 not found"
    products = body.get("products") or []
    assert any(p.get("sku") == "KTN-NVY-PSH-01" for p in products)
    samples = body.get("samples") or []
    assert len(samples) >= 1


def test_color_links_404(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/color-library/tidak-ada/links", headers=hdr_admin, timeout=30)
    assert r.status_code == 404


def test_product_ktn_nvy_psh_01_dua_warna(hdr_admin):
    r = requests.get(f"{BASE_URL}/api/products", headers=hdr_admin,
                     params={"q": "KTN-NVY-PSH-01"}, timeout=30)
    assert r.status_code == 200
    rows = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("data") or []
    prod = next((p for p in rows if p.get("sku") == "KTN-NVY-PSH-01"), None)
    assert prod, f"Produk KTN-NVY-PSH-01 tidak ditemukan (got {len(rows)} rows)"
    assert (prod.get("color_ref") or {}).get("code") == "KN-BLU-01"
    sc = prod.get("supplier_colors") or []
    assert sc and sc[0].get("supplier_color_name") == "Navy 07"
    rnd = prod.get("rnd_supplier") or {}
    assert rnd.get("name") == "Palembang Silk House"


# ─── Cleanup ─────────────────────────────────────────────────────────
def test_zzz_cleanup(hdr_admin):
    """Hard-delete color TEST_ prefixes via Mongo (allowed per instructions)."""
    import asyncio, sys
    sys.path.insert(0, "/app/backend")
    from db import db  # type: ignore

    async def _run():
        res = await db.color_library.delete_many({"$or": [
            {"code": {"$regex": "^TEST-"}},
            {"id": {"$in": created_ids}},
        ]})
        return res.deleted_count

    n = asyncio.get_event_loop().run_until_complete(_run()) if False else asyncio.run(_run())
    print(f"cleaned {n} TEST_ colors")
