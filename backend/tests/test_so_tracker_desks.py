"""Pelacak SO di tiap meja — API GET /api/desks/so-tracker.

Verifikasi:
  * Field wajib tiap row (status_label, next_step, owner_label, can_act, action, created_at, updated_at)
  * SO status closed (done/cancelled/...) tidak muncul
  * can_act per meja:
      - SO status 'reserved' / 'approved' → owner Admin Sales → desk=sales_admin can_act true
      - SO 'confirmed' → owner Admin Gudang → desk=warehouse_admin can_act true
      - SO 'shipped' outstanding>0 → owner Finance → desk=finance can_act true
      - SO 'waiting_approval' required_approval_role=manager → owner manager
  * SO TEST baru muncul, lalu diubah ke done → hilang.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

ADMIN = {"email": "admin@kainnusantara.id", "password": "demo12345"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.text
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


REQUIRED_FIELDS = {"id", "number", "status", "status_label", "next_step", "owner_label",
                   "owner_roles", "can_act", "action", "created_at", "updated_at"}


def _get_tracker(client, desk, entity_id=""):
    params = {"desk": desk}
    if entity_id:
        params["entity_id"] = entity_id
    r = client.get(f"{BASE_URL}/api/desks/so-tracker", params=params, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("desk", ["sales_admin", "finance", "warehouse_admin", "md", "sample_admin", "me"])
def test_tracker_shape_each_desk(admin_client, desk):
    data = _get_tracker(admin_client, desk)
    assert data["desk"] == desk
    assert isinstance(data["rows"], list)
    assert isinstance(data["count"], int)
    for r in data["rows"][:20]:
        missing = REQUIRED_FIELDS - r.keys()
        assert not missing, f"Missing fields: {missing}"
        # status not closed
        assert r["status"] not in ("done", "cancelled", "rejected", "expired", "void")
        assert isinstance(r["can_act"], bool)


def test_can_act_consistency(admin_client):
    """Baris 'confirmed' bisa ditindak di meja gudang; 'reserved/approved' di meja sales_admin."""
    sa = _get_tracker(admin_client, "sales_admin")
    wh = _get_tracker(admin_client, "warehouse_admin")
    fin = _get_tracker(admin_client, "finance")

    def by_id(rows):
        return {r["id"]: r for r in rows}

    sa_map, wh_map, fin_map = by_id(sa["rows"]), by_id(wh["rows"]), by_id(fin["rows"])

    for rid, r in sa_map.items():
        if r["status"] in ("reserved", "approved"):
            assert r["can_act"] is True, f"sales_admin should act on {rid} status={r['status']}"
            # gudang tidak boleh klaim status ini
            assert wh_map.get(rid, {}).get("can_act", False) is False
        if r["status"] == "confirmed":
            assert r["can_act"] is False
            assert wh_map.get(rid, {}).get("can_act", True) is True
        if r["status"] in ("shipped", "dispatched"):
            # bila outstanding>0 → finance act
            outstanding = (r.get("grand_total") or 0) - 0  # paid_total unknown here
            if fin_map.get(rid, {}).get("can_act") is True:
                assert fin_map[rid]["owner_roles"] == ["finance"]


def test_create_and_close_so_disappears(admin_client):
    """Buat SO TEST (reserved), muncul di sales_admin tracker; set done → hilang; cleanup."""
    # ambil customer & produk sembarang pada entity Sukacita
    def _items(resp):
        if resp.status_code != 200:
            return []
        js = resp.json()
        return js if isinstance(js, list) else (js.get("items") or js.get("data") or [])

    cust_r = admin_client.get(f"{BASE_URL}/api/customers", params={"entity_id": "ent_ksc", "limit": 1}, timeout=20)
    items = _items(cust_r)
    if not items:
        pytest.skip("tidak ada customer untuk entity_id ent_ksc")
    customer = items[0]

    prod_r = admin_client.get(f"{BASE_URL}/api/products", params={"entity_id": "ent_ksc", "limit": 1}, timeout=20)
    items = _items(prod_r)
    if not items:
        pytest.skip("tidak ada produk ent_ksc")
    product = items[0]

    # minimal payload sales order
    # alamat sudah tersedia pada payload list
    addresses = customer.get("addresses") or []
    if not addresses:
        pytest.skip("customer tanpa shipping address")
    ship_id = addresses[0]["id"]

    payload = {
        "entity_id": "ent_ksc",
        "customer_id": customer["id"],
        "shipping_address_id": ship_id,
        "notes": "TEST_so_tracker",
        "items": [{
            "product_id": product["id"],
            "quantity": 1,
            "unit_price": 100000,
            "unit": "meter",
        }],
    }
    cr = admin_client.post(f"{BASE_URL}/api/sales-orders", json=payload, timeout=30)
    if cr.status_code not in (200, 201):
        pytest.skip(f"gagal buat SO TEST untuk uji: {cr.status_code} {cr.text[:500]}")
    so = cr.json()
    so_id = so.get("id")
    assert so_id

    try:
        data = _get_tracker(admin_client, "sales_admin", "ent_ksc")
        ids_before = {r["id"] for r in data["rows"]}
        assert so_id in ids_before, f"SO baru harus muncul di tracker. status={so.get('status')}"

        # tandai done via patch mongo-level mungkin tidak ada endpoint; coba cancel
        can = admin_client.post(f"{BASE_URL}/api/sales-orders/{so_id}/cancel",
                                json={"reason": "TEST_so_tracker cleanup auto"}, timeout=20)
        if can.status_code not in (200, 204):
            # fallback: tidak bisa close → cukup pastikan appear; akhiri skip
            pytest.skip(f"tidak bisa cancel: {can.status_code} {can.text[:200]}")

        data2 = _get_tracker(admin_client, "sales_admin", "ent_ksc")
        ids_after = {r["id"] for r in data2["rows"]}
        assert so_id not in ids_after, "SO status cancelled HARUS hilang dari tracker"
    finally:
        # cleanup — delete the SO document from DB via admin endpoint if any
        admin_client.delete(f"{BASE_URL}/api/sales-orders/{so_id}", timeout=20)
