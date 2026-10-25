"""Keputusan pemilik 26 Okt 2026 (audit UI tahap 2) — wilayah D3, uji LEWAT HTTP (butuh backend ter-restart).

* K-11 — MD hanya membaca kelompok Pusat Pengaturan R&D (registry/effective/explain/history); admin tidak berubah.
* K-11 — papan PO Custom di beranda sales hanya pelanggan miliknya (`owner_scoped`), Admin Sample ditolak memutus SORD.
* K-12 — ringkasan permintaan desain (`/design-requests`) membawa `due_soon`.
* K-14 — alasan < 5 huruf ditolak (tolak spesifikasi R&D, kembalikan penggajian).
* K-16 — labdip produk baru tanpa handfeel ACC: tanpa alasan 400; dengan alasan 200 + `chain_override` + riwayat.

Jalankan: cd /app/backend && python -m pytest tests/test_uat26_d3_http.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
ENT = "ent_ksc"


def _login(email, entity=ENT):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"akun {email} tidak bisa masuk: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}, r.json()["user"]


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")[0]


@pytest.fixture(scope="module")
def md():
    return _login("md@kainnusantara.id")[0]


# ── K-11 · Pusat Pengaturan MD ───────────────────────────────────────────────
def test_k11_md_reads_only_rnd_config(md, admin):
    reg = requests.get(f"{BASE}/config/registry", headers=md, timeout=30).json()
    gids = [g["id"] for g in reg["groups"]]
    assert gids and gids[0] == "rnd" and set(gids) <= {"rnd", "persetujuan"}, gids
    assert reg["caps"]["read_scope"]
    assert all(e["group"] == "rnd" or e["key"].startswith("approval.matrix") or e["key"].startswith("approval.po_custom")
               for e in reg["entries"])
    assert requests.get(f"{BASE}/config/effective", headers=md, params={"group": "pajak"}, timeout=30).status_code == 403
    eff = requests.get(f"{BASE}/config/effective", headers=md, params={"q": "ppn"}, timeout=30).json()
    assert all(i["group"] in ("rnd", "persetujuan") for i in eff["items"])
    assert requests.get(f"{BASE}/config/explain", headers=md, params={"key": "rnd.kpi_weight_design"},
                        timeout=30).status_code == 200
    hist = requests.get(f"{BASE}/config/history", headers=md, timeout=30).json()
    assert all(r.get("group") in ("rnd", "persetujuan") for r in hist["rows"])
    # Admin tetap membaca semua kelompok.
    areg = requests.get(f"{BASE}/config/registry", headers=admin, timeout=30).json()
    assert len(areg["groups"]) > len(gids) and not areg["caps"].get("read_scope")


# ── K-11 · papan PO Custom sales & Admin Sample ──────────────────────────────
def test_k11_sales_home_board_is_owner_scoped():
    sales, user = _login("sales@kainnusantara.id")
    data = requests.get(f"{BASE}/home/sales", headers=sales, timeout=60).json()
    board = next((b for b in data.get("waiting_boards") or [] if b["key"] == "special_order"), None)
    assert board is not None and board.get("owner_scoped") is True
    own = set(DB.customers.distinct("id", {"$or": [{"assigned_sales_id": user["id"]}, {"sales_team.sales_id": user["id"]}]}))
    for row in board["rows"]:
        doc = DB.special_orders.find_one({"id": row["id"]}, {"_id": 0, "customer_id": 1, "created_by": 1})
        assert doc["customer_id"] in own or doc.get("created_by") in (user["id"], user.get("email")), row["number"]


def test_k11_sample_admin_cannot_decide_special_order():
    sa, _ = _login("sampleadmin@kainnusantara.id")
    od = DB.special_orders.find_one({"status": "pending_approval", "entity_id": ENT}, {"_id": 0, "id": 1})
    if not od:
        pytest.skip("tidak ada PO custom menunggu di data acuan")
    r = requests.post(f"{BASE}/special-orders/{od['id']}/approve", headers=sa, json={"notes": "uji"}, timeout=30)
    assert r.status_code == 403, r.text


# ── K-12 ─────────────────────────────────────────────────────────────────────
def test_k12_design_requests_summary_has_due_soon():
    dsg, _ = _login("designer@kainnusantara.id")
    r = requests.get(f"{BASE}/design-requests", headers=dsg, params={"mine": "true", "page": 1, "page_size": 1}, timeout=30)
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert {"open", "overdue", "due_soon", "revision", "due_soon_days"} <= set(s)


# ── K-14 ─────────────────────────────────────────────────────────────────────
def test_k14_short_reason_rejected(admin):
    spec = DB.md_specs.find_one({"status": "review"}, {"_id": 0, "id": 1})
    if spec:
        r = requests.post(f"{BASE}/rnd/specs/{spec['id']}/reject", headers=admin, json={"reason": "abcd"}, timeout=30)
        assert r.status_code == 422, r.text
    run = DB.hr_payroll_runs.find_one({"status": "pending_approval"}, {"_id": 0, "id": 1})
    if run:
        r = requests.post(f"{BASE}/hr/payroll/runs/{run['id']}/reject", headers=admin, json={"reason": "abcd"}, timeout=30)
        assert r.status_code == 422, r.text


# ── K-16 ─────────────────────────────────────────────────────────────────────
def _labdip(admin, **extra):
    body = {"sample_types": ["labdip"], "title": f"UJI-D3-{T} labdip", "unit": "meter", "qty_requested": 2,
            "color_target": {"name": "Biru Uji D3", "hex": "#123456", "pantone_code": "19-4052 TCX"},
            "spec": {"target": {"fabric_type": "woven", "gramasi": 150}, "sku_hint": f"TST-D3-{uuid.uuid4().hex[:5]}"},
            **extra}
    return requests.post(f"{BASE}/rnd/samples", headers=admin, json=body, timeout=60)


def test_k16_labdip_without_handfeel_acc_with_reason(admin):
    r = _labdip(admin)
    assert r.status_code == 400 and "HANDFEEL" in r.text and "alasan" in r.text.lower()
    r2 = _labdip(admin, chain_override_reason="abcd")
    assert r2.status_code == 400
    why = "kain sama dengan produk berjalan, hanya warna baru"
    r3 = _labdip(admin, chain_override_reason=why)
    assert r3.status_code == 200, r3.text
    s = r3.json()
    assert s["chain_override"]["missing"] == "handfeel_acc" and s["chain_override"]["reason"] == why
    assert any(t.get("event") == "chain_override" and t.get("note") == why for t in s.get("timeline") or [])
    log = DB.audit_logs.find_one({"action": "rnd_sample_created", "entity_id": s["id"]}, {"_id": 0})
    assert log is None or log.get("reason") == why
    DB.md_samples.delete_one({"id": s["id"]})
    if s.get("spec_id"):
        DB.md_specs.delete_one({"id": s["spec_id"]})
