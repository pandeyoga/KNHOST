"""FIX-2 (audit 9 Nov 2026 — B3a STK-1/2/6/13/14, SSOT-3/4, STK-4/8; B1 UI-40/UI-45/UI-46) — satu rumus angka stok +
aturan "dua angka" (LOKAL + GLOBAL) + rincian.

Dua lapis:
  A. SERVIS (in-process, data uji ber-prefiks `prod_TEST_FIX2`, dibersihkan sendiri) — pembaca lama vs definisi tunggal.
  B. API (data acuan, akun demo, HANYA GET kecuali `PUT /stock/my-site` yang dikembalikan) — per peran LOKAL vs GLOBAL.
Semua uji di sini GAGAL di kode sebelum FIX-2 (field/endpoint/angka lama) dan LULUS sesudahnya.

Jalankan (kontainer backend, DB salinan data acuan):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix2_stock_figures.py
"""
import asyncio
import os
import re

import pytest
import requests

from db import db

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
P = "prod_TEST_FIX2_a"
WH = "wh_jakarta"                 # gudang aktif terdaftar, site Jakarta
SITE_JKT = "site_54bed6261604"
SITE_SRG = "site_fd9f6aa41d36"
ENT = "ent_ksc"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _pw():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read())
    return m.group(1)


# ─────────────────────────── A. SERVIS ───────────────────────────
async def _wipe():
    await db.inventory_rolls.delete_many({"product_id": P})
    await db.inventory_balances.delete_many({"product_id": P})
    await db.material_reservations.delete_many({"product_id": P})
    await db.products.delete_many({"id": P})


@pytest.fixture()
def seeded():
    """3 roll KSC @Jakarta: 50 (10 dipesan potong) + 40 tersedia, 30 dialokasikan; cadangan makloon 30.
    Kebenaran: Tersedia = (50−10) + 40 − 30 = 50; Stok Fisik = 120; roll tersedia = 2."""
    from services.roll_service import rebuild_balance

    async def seed():
        await _wipe()
        await db.products.insert_one({"id": P, "sku": "TEST-FIX2-A", "name": "Uji FIX-2", "base_unit": "yard",
                                      "status": "active"})
        base = {"product_id": P, "warehouse_id": WH, "owner_entity_id": ENT, "unit": "yard", "lot": "L-FIX2",
                "created_at": "2026-11-09T00:00:00Z"}
        await db.inventory_rolls.insert_many([
            {**base, "id": "roll_TEST_FIX2_1", "roll_no": "RL-FIX2-1", "status": "available", "length_initial": 50,
             "length_remaining": 50, "length_reserved": 10,
             "length_reservations": [{"id": "lr1", "qty": 10, "status": "reserved", "ref": {"type": "sales_order", "id": "so_x"}}]},
            {**base, "id": "roll_TEST_FIX2_2", "roll_no": "RL-FIX2-2", "status": "available", "length_initial": 40,
             "length_remaining": 40},
            {**base, "id": "roll_TEST_FIX2_3", "roll_no": "RL-FIX2-3", "status": "committed", "length_initial": 30,
             "length_remaining": 30, "reserved_ref": {"type": "sales_order", "id": "so_y"}},
        ])
        await rebuild_balance(P, WH, ENT)
        await db.material_reservations.insert_one({"id": "mres_TEST_FIX2", "product_id": P, "owner_entity_id": ENT,
                                                   "qty": 30, "status": "active", "ref_type": "makloon_order",
                                                   "ref_id": "mko_TEST_FIX2"})
    run(seed())
    yield
    run(_wipe())


def test_ssot4_satu_definisi_tersedia_dikurangi_makloon(seeded):
    from services import stock_figures as sf
    segs = run(sf.segments([P]))
    t = sf.sum_segments(segs)
    assert t["available_qty"] == 50.0 and t["makloon_reserved_qty"] == 30.0 and t["available_rolls"] == 2
    assert t["on_hand_qty"] == 120.0


def test_stk13_pos_site_stock_tidak_menghitung_panjang_dipesan_potong(seeded):
    from services.site_stock_service import site_stock
    s = run(site_stock(SITE_JKT, ENT, [P]))[P]
    assert s["own_qty"] == 50.0, s          # dulu 90 (Σ length_remaining roll available mentah)


def test_stk6_ringkasan_sales_fisik_termasuk_dialokasikan_bebas_dikurangi_makloon(seeded):
    from services.sales_p04_service import sales_stock_summary
    out = run(sales_stock_summary(P, ENT))
    reg = next(r for r in out["rows"] if r["class"] == "regular")
    assert reg["physical"] == 120.0, reg     # dulu 90 (committed tidak dihitung)
    assert reg["free"] == 50.0, reg          # dulu 80 (cadangan makloon tidak dikurangi)
    assert reg["makloon_reserved"] == 30.0


def test_ssot4_katalog_entity_available_atp_dan_permintaan_internal_sama(seeded):
    from services import sales_stock_service as sss
    from services.stock_bucket_service import atp_detail
    from services.internal_request_service import availability
    prods = [{"id": P}]
    run(sss.apply_global(prods, ENT))
    assert prods[0]["entity_available_qty"] == 50.0 and prods[0]["available_qty"] == 50.0   # dulu 80
    assert run(atp_detail({"owner_entity_id": ENT}, P, ENT))["available"] == 50.0             # dulu 80
    assert run(availability(P, ENT))["own_available"] == 50.0                                 # dulu 80


def test_ssot4_pemilih_roll_memberi_angka_tersedia_tunggal(seeded):
    from services.roll_service import list_available_rolls
    out = run(list_available_rolls(P, ENT))
    assert out["available_total"] == 50.0 and out["makloon_reserved_qty"] == 30.0   # dulu field tidak ada


def test_keputusan2_tahan_inspeksi_jadi_blocked_dan_kembali_saat_lepas(seeded):
    from services.roll_hold_service import sync_inspection_hold
    from services import stock_figures as sf
    run(db.inventory_rolls.update_one({"id": "roll_TEST_FIX2_2"}, {"$set": {"inspection.hold": {
        "held": True, "reason": "Warna beda dari sample yang di-ACC — barang DITAHAN sampai MD Quality memutuskan."}}}))
    assert run(sync_inspection_hold("roll_TEST_FIX2_2")) == "blocked"
    r = run(db.inventory_rolls.find_one({"id": "roll_TEST_FIX2_2"}, {"_id": 0}))
    assert r["status"] == "blocked" and r["hold"]["source"] == "inspection" and r["hold"]["prev_status"] == "available"
    assert sf.sum_segments(run(sf.segments([P])))["available_qty"] == 10.0     # 40 − 30 makloon; roll 40 keluar
    run(db.inventory_rolls.update_one({"id": "roll_TEST_FIX2_2"}, {"$set": {"inspection.hold.held": False}}))
    assert run(sync_inspection_hold("roll_TEST_FIX2_2")) == "available"
    assert sf.sum_segments(run(sf.segments([P])))["available_qty"] == 50.0
    assert run(sync_inspection_hold("roll_TEST_FIX2_2")) is None               # idempoten


def test_keputusan4_horizon_atp_dari_setelan(monkeypatch):
    from services import atp_policy, config_resolver

    async def fake(key, ctx=None):
        return 30 if key == "stock.atp_horizon_days" else None
    monkeypatch.setattr(config_resolver, "value_of", fake)
    atp_policy.invalidate_horizon()
    assert run(atp_policy.horizon_days()) == 30
    assert atp_policy.within_horizon("2999-01-01") is False
    monkeypatch.undo()
    atp_policy.invalidate_horizon()
    assert run(atp_policy.horizon_days()) == 14       # bawaan


def test_po_open_base_qty_sisa_satuan_dasar():
    from services.stock_figures import po_open_base_qty
    assert po_open_base_qty({"quantity": 10, "quantity_base": 500, "received_qty": 2}) == 400.0
    assert po_open_base_qty({"quantity": 1500, "received_qty": 0}) == 1500.0
    assert po_open_base_qty({"quantity": 5, "received_qty": 5}) == 0.0


# ─────────────────────────── B. API (data acuan) ───────────────────────────
class Api:
    def __init__(self, email):
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": _pw()}, timeout=30)
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['token']}"}

    def get(self, path, **kw):
        r = requests.get(f"{BASE}{path}", headers=self.h, timeout=180, **kw)
        return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)

    def put(self, path, js):
        r = requests.put(f"{BASE}{path}", headers=self.h, json=js, timeout=60)
        return r.status_code, r.json()


@pytest.fixture(scope="module")
def u():
    return {k: Api(e) for k, e in (("adm", "admin@kainnusantara.id"), ("mgr", "manager@kainnusantara.id"),
                                  ("sales", "sales@kainnusantara.id"), ("kanda", "sales.kanda@kainnusantara.id"),
                                  ("srg", "warehouse.soreang@kainnusantara.id"))}


def _truth(pid, owners=None, sites=None):
    """Tersedia langsung dari roll (gudang dihitung) − cadangan makloon (gudang tersedia terbesar dulu)."""
    async def go():
        whs = {w["id"]: w async for w in db.warehouses.find({}, {"_id": 0})}
        ok = {k for k, w in whs.items() if w.get("active") is not False and w.get("is_test") is not True}
        seg = {}
        async for r in db.inventory_rolls.find({"product_id": pid, "status": "available"}, {"_id": 0}):
            if r["warehouse_id"] not in ok or (r.get("active_movement") or {}).get("id") \
                    or ((r.get("inspection") or {}).get("hold") or {}).get("held"):
                continue
            k = (r["owner_entity_id"], r["warehouse_id"])
            seg[k] = seg.get(k, 0.0) + float(r["length_remaining"] or 0) - float(r.get("length_reserved") or 0)
        async for m in db.material_reservations.find({"product_id": pid, "status": "active"}, {"_id": 0}):
            # FIX-9 — bagian cadangan yang terkunci di roll sudah ada di `length_reserved` roll di atas
            left = float(m["qty"] or 0) - float(m.get("locked_qty") or 0)
            for k in sorted([k for k in seg if k[0] == m["owner_entity_id"]], key=lambda k: (-seg[k], k[1])):
                cut = min(left, max(seg[k], 0))
                seg[k] -= cut
                left -= cut
        return round(sum(max(v, 0) for (o, w), v in seg.items()
                         if (owners is None or o in owners) and (sites is None or whs[w].get("site_id") in sites)), 2)
    return run(go())


def _pid(sku):
    return run(db.products.find_one({"sku": sku}, {"_id": 0, "id": 1}))["id"]


def test_dua_angka_global_sama_untuk_semua_peran_dan_lokal_per_cakupan(u):
    pid = _pid("DMO-GRY-KNT-001")                 # produk bercadangan makloon 300 kg (Kanda)
    glob = _truth(pid)
    seen = {}
    for k, api in u.items():
        st, body = api.get("/stock/figures", params={"product_ids": pid})
        assert st == 200, body
        f = body["items"][pid]
        assert f["global"]["qty"] == glob, (k, f, glob)
        seen[k] = (body["scope"], f)
    # sales Kanda: PT Kanda, tanpa site; petugas Soreang: PT Kanda × site Soreang; manajer: PT aktif (rumah) KSC
    assert seen["kanda"][0]["entity_ids"] == ["ent_kanda"] and seen["kanda"][0]["site_ids"] is None
    assert seen["kanda"][1]["local"]["qty"] == _truth(pid, {"ent_kanda"})
    assert seen["srg"][0]["site_ids"] == [SITE_SRG]
    assert seen["srg"][1]["local"]["qty"] == _truth(pid, {"ent_kanda"}, {SITE_SRG})
    assert seen["mgr"][1]["local"]["qty"] == _truth(pid, {ENT})
    assert seen["sales"][1]["local"]["qty"] == _truth(pid, {ENT})


def test_keputusan3_site_pos_tersimpan_di_server_menjadi_cakupan_lokal(u):
    api = u["kanda"]
    st, before = api.get("/stock/my-site")
    assert st == 200
    try:
        st, body = api.put("/stock/my-site", {"site_id": SITE_SRG})
        assert st == 200 and body["site_name"] == "Soreang"
        pid = _pid("DMO-GRY-KNT-001")
        st, fb = api.get("/stock/figures", params={"product_ids": pid})
        assert fb["scope"]["site_ids"] == [SITE_SRG] and "Soreang" in fb["scope"]["label"]
        assert fb["items"][pid]["local"]["qty"] == _truth(pid, {"ent_kanda"}, {SITE_SRG})
        assert api.put("/stock/my-site", {"site_id": "site_tidak_ada"})[0] == 400
    finally:
        api.put("/stock/my-site", {"site_id": before.get("site_id") or ""})


def test_rincian_per_pt_dan_per_site_berjumlah_global(u):
    pid = _pid("KNKNT0021-L-BEIX-XA-XX-XB")       # cadangan makloon 75 kg (KSC), multi-gudang
    st, d = u["adm"].get(f"/stock/figures/{pid}")
    assert st == 200, d
    g = _truth(pid)
    assert d["global"]["qty"] == g
    assert round(sum(x["available_qty"] for x in d["by_entity"]), 2) == g
    assert round(sum(x["available_qty"] for x in d["by_site"]), 2) == g
    keys = [r["key"] for r in d["global_status"]]
    assert keys[:3] == ["available", "makloon", "reserved"] and d["atp"]["horizon_days"] >= 1
    # petugas Soreang (PT Kanda): PT lain tampil sebagai angka saja
    st, d2 = u["srg"].get(f"/stock/figures/{pid}")
    assert st == 200 and any(not e["visible"] for e in d2["by_entity"])


def test_stk1_katalog_produk_varian_tidak_lagi_nol(u):
    pid = _pid("KNKNT0021-L-KHKX-XA-XX-XB")
    tpl = run(db.products.find_one({"id": pid}, {"_id": 0, "template_id": 1}))["template_id"]
    r = requests.get(f"{BASE}/product-templates/{tpl}/summary", headers={**u["adm"].h, "X-Entity-Id": "all"}, timeout=120)
    assert r.status_code == 200, r.text[:200]
    v = next(x for x in r.json()["variants"] if x["id"] == pid)
    assert v["available"] == _truth(pid) and v["available"] > 0      # dulu selalu 0
    assert v["stock_figures"]["global"]["qty"] == _truth(pid)


def test_stk14_ringkasan_rfid_menghitung_sungguhan(u):
    st, s = u["adm"].get("/rfid/summary")
    assert st == 200
    assert s["untagged_rolls"] > 5000                                    # dulu mentok 5000 (batas daftar)


def test_stk8_kpi_dasbor_semua_pt_dikurangi_makloon_per_pt(u):
    r = requests.get(f"{BASE}/dashboard", params={"entity_id": "all"}, headers={**u["adm"].h, "X-Entity-Id": "all"},
                     timeout=180)
    assert r.status_code == 200
    kg = r.json()["metrics"]["available_by_unit"]["kg"]
    dash_kanda = requests.get(f"{BASE}/dashboard", headers={**u["adm"].h, "X-Entity-Id": "ent_kanda"}, timeout=180).json()
    prod = next(p for p in dash_kanda["products"] if p.get("sku") == "DMO-GRY-KNT-001")
    plist = requests.get(f"{BASE}/products", headers={**u["adm"].h, "X-Entity-Id": "ent_kanda"}, timeout=180).json()
    pprod = next(p for p in plist if p.get("sku") == "DMO-GRY-KNT-001")
    # /products & /dashboard memberi stok PT yang SAMA untuk produk & PT yang sama (dulu 477,63 vs 177,63)
    assert prod["entity_available_qty"] == _truth(prod["id"], {"ent_kanda"}) == pprod["entity_available_qty"]
    # KPI "Semua PT" = Σ Tersedia per PT (cadangan makloon Kanda ikut dikurangi; dulu +300 kg)
    async def kg_truth():
        ids = [p["id"] async for p in db.products.find({"base_unit": "kg"}, {"_id": 0, "id": 1})]
        return ids
    kg_ids = run(kg_truth())
    from services import stock_figures as sf
    segs = [s for s in run(sf.segments(kg_ids)) if s["owner_entity_id"] in ("ent_ksc", "ent_kanda", "ent_82b52ed6ee8b")]
    assert abs(kg - round(sum(max(s["available_qty"], 0) for s in segs), 2)) < 0.05


def test_ui40_ui45_papan_stok_dua_angka_dan_cakupan_berlabel(u):
    st, rows = u["sales"].get("/inventory/status-board")
    assert st == 200 and rows
    r0 = rows[0]
    assert r0["stock_figures"]["local"]["state"] in ("habis", "rendah", "ada")
    assert r0["stock_scope_label"]
    # angka kolom milik PT sendiri (total_*) ≠ angka grup; grup tersedia sebagai global_total untuk baris kedua
    assert "global_total" in r0 and r0["detail_scope"] == "own_entity"


def test_ui46_antrean_penempatan_rak_berhalaman_dengan_total_sungguhan(u):
    st, q = u["adm"].get("/inventory/putaway/queue", params={"warehouse_id": WH, "limit": 50})
    assert st == 200
    assert q["limit"] == 50 and len(q["rolls"]) <= 50
    assert q["total"] >= len(q["rolls"]) and q["total_building"] >= q["total"]
    assert q["truncated"] == (q["total"] > len(q["rolls"]))
