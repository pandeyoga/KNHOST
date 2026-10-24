"""23 Okt 2026 — penelusuran UI/UX alur Pesanan Khusus (OD) end-to-end: regresi perbaikan backend.

* Rincian OD menyebut NAMA orang (created_by_name / approved_by_name / status_history[].user_name), bukan email.
* Persetujuan OD tercatat di riwayat status (dulu riwayat berhenti di "Menunggu Persetujuan").
* Fase OD = tahap paling awal yang belum selesai: OD printing+labdip dengan desain belum ACC → "design",
  sample labdip yang berjalan bersamaan → `phase_parallel` (dulu lini masa mencentang "Desain berjalan" selesai).
* Proofing otomatis saat desain di-ACC tercatat atas nama PEMBUAT OD (Sales), bukan Manajer penyetuju desain
  (dulu pemisahan tugas melarang Manajer itu meng-ACC spesifikasi proofing → hanya Admin tersisa).
* MD boleh memutus pemenang sample (keputusan pemilik UAT v3) dan spesifikasi yang belum di-ACC otomatis
  diajukan ke antrean ACC Manajer (dulu tetap Draf: tak ada yang diberi tahu, SKU tak pernah lahir).
* SPK QC retur pelanggan tidak masuk antrean MD "SPK inspeksi tanpa acuan sample".
"""
import asyncio
import os
import struct
import sys
import uuid
import zlib

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
TAG = uuid.uuid4().hex[:6]
CREATED = []
_LOOP = asyncio.new_event_loop()


def _run(coro):
    """Klien Motor global terikat ke loop pertama yang memakainya (lihat test_return_per_roll._run)."""
    sys.path.insert(0, "/app/backend")
    from db import db as _db
    loop = _db.client._io_loop
    if loop is None or loop.is_closed():
        loop = _db.client._io_loop = _LOOP
    return loop.run_until_complete(coro)


def _png():
    raw = b"".join(b"\x00" + bytes([10, 20, 30]) * 4 for _ in range(4))

    def ch(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _user(email):
    return DB.users.find_one({"email": email}, {"_id": 0, "id": 1, "name": 1, "email": 1})


@pytest.fixture(scope="module")
def H():
    return {k: _login(f"{k}@kainnusantara.id") for k in ("sales", "manager", "md", "admin")}


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    ods = [o["id"] for o in DB.special_orders.find({"id": {"$in": CREATED}}, {"id": 1})]
    smp = list(DB.md_samples.find({"special_order_id": {"$in": ods}}, {"spec_id": 1, "id": 1}))
    spec_ids = [s.get("spec_id") for s in smp if s.get("spec_id")]
    for o in DB.special_orders.find({"id": {"$in": ods}}, {"items.spec_id": 1, "spec_id": 1}):
        spec_ids += [i.get("spec_id") for i in o.get("items") or [] if i.get("spec_id")] + [o.get("spec_id")]
    DB.supplier_contracts.delete_many({"refs.doc_id": {"$in": [s["id"] for s in smp]}})
    DB.md_samples.delete_many({"special_order_id": {"$in": ods}})
    DB.md_specs.delete_many({"id": {"$in": [x for x in spec_ids if x]}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ods}})
    DB.design_gallery.delete_many({"id": {"$regex": f"^dsgn_TEST_od23_{TAG}"}})
    DB.special_orders.delete_many({"id": {"$in": ods}})
    DB.inspections.delete_many({"id": f"ins_TEST_od23_{TAG}"})
    # lepaskan ikatan klien Motor ke loop modul ini — modul tes berikutnya (mis. iter219, asyncio.run) mengikat ulang
    from db import db as _db
    if _db.client._io_loop is _LOOP:
        _db.client._io_loop = None


def _create_od(H, items):
    body = {"customer_id": CUST, "title": f"TEST_OD23_{TAG}", "entity_id": ENT, "expected_delivery": "2026-12-31",
            "items": items, "submit_for_approval": True}
    r = requests.post(f"{BASE}/special-orders", json=body, headers=H["sales"], timeout=30)
    assert r.status_code in (200, 201), r.text
    CREATED.append(r.json()["id"])
    return r.json()


def _tpl():
    return [t["id"] for t in DB.product_templates.find({"status": "active"}, {"id": 1}).sort("name", 1).limit(2)]


@pytest.fixture(scope="module")
def od_two_types(H):
    """OD Sales: item A labdip + item B printing, disetujui Manajer."""
    a, b = _tpl()
    od = _create_od(H, [
        {"source_type": "parent_product", "source_template_id": a, "description": "TEST A labdip", "request_types": ["labdip"], "quantity": 10},
        {"source_type": "parent_product", "source_template_id": b, "description": "TEST B printing", "request_types": ["printing"], "quantity": 10}])
    r = requests.post(f"{BASE}/special-orders/{od['id']}/approve", json={"notes": ""}, headers=H["manager"], timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def test_detail_menyebut_nama_dan_riwayat_persetujuan(H, od_two_types):
    sales, mgr = _user("sales@kainnusantara.id"), _user("manager@kainnusantara.id")
    d = requests.get(f"{BASE}/special-orders/{od_two_types['id']}", headers=H["admin"], timeout=30).json()
    assert d["created_by_name"] == sales["name"]
    assert d.get("approved_by_name") == mgr["name"]
    hist = d["status_history"]
    assert hist[0].get("user_name") == sales["name"]
    approved = [h for h in hist if h.get("status") == "confirmed" and h.get("note") == "Disetujui"]
    assert approved and approved[0].get("user_name") == mgr["name"], hist
    # respons aksi (_fresh) juga membawa nama — layar tidak kembali menampilkan email setelah Setujui
    assert od_two_types.get("created_by_name") == sales["name"]


def test_fase_desain_dengan_sampling_paralel(H, od_two_types):
    d = requests.get(f"{BASE}/special-orders/{od_two_types['id']}", headers=H["admin"], timeout=30).json()
    ch = d["chain"]
    assert ch["design_request"] and ch["design_request"]["status"] not in ("approved", "cancelled")
    assert ch["design_request"].get("status_label") == "Menunggu penugasan"
    assert any(s["status"] != "cancelled" for s in ch["samples"])
    assert ch["phase"] == "design", ch["phase"]
    assert ch["phase_parallel"] == ["sampling"]


def test_proofing_otomatis_atas_nama_pembuat_od(H, od_two_types):
    od = DB.special_orders.find_one({"id": od_two_types["id"]}, {"_id": 0})
    item_b = od["items"][1]
    design = {"id": f"dsgn_TEST_od23_{TAG}", "code": f"TOD23-{TAG}", "request_id": item_b["design_request_id"], "version": 1}
    DB.design_gallery.insert_one({**design, "status": "approved", "entity_id": ENT, "title": "TEST od23"})
    sys.path.insert(0, "/app/backend")
    from services import special_order_phase2 as p2  # noqa: E402
    mgr = _user("manager@kainnusantara.id")
    sample = _run(p2.on_design_approved(dict(design), {**mgr, "role": "manager"}))
    assert sample
    sales = _user("sales@kainnusantara.id")
    smp = DB.md_samples.find_one({"id": sample["id"]}, {"_id": 0, "created_by": 1, "spec_id": 1})
    spec = DB.md_specs.find_one({"id": smp["spec_id"]}, {"_id": 0, "created_by": 1})
    assert smp["created_by"] == sales["name"], smp
    assert spec["created_by"] == sales["name"], spec
    # riwayat OD tetap mencatat siapa yang memicu (Manajer meng-ACC desain)
    hist = DB.special_orders.find_one({"id": od["id"]}, {"_id": 0, "status_history": 1})["status_history"]
    assert hist[-1]["user"] == mgr["email"] and "proofing" in hist[-1]["note"]


def test_md_putus_pemenang_spesifikasi_diajukan_otomatis(H):
    a, _ = _tpl()
    od = _create_od(H, [{"source_type": "parent_product", "source_template_id": a, "description": "TEST labdip MD",
                         "request_types": ["labdip"], "quantity": 10}])
    assert requests.post(f"{BASE}/special-orders/{od['id']}/approve", json={}, headers=H["manager"], timeout=60).status_code == 200
    sid = DB.special_orders.find_one({"id": od["id"]}, {"_id": 0, "sample_ids": 1})["sample_ids"][0]
    sup = DB.suppliers.find_one({"name": {"$regex": "Grey Mandiri"}}, {"_id": 0, "id": 1}) or \
        DB.suppliers.find_one({"status": {"$ne": "inactive"}}, {"_id": 0, "id": 1})
    md_h = H["md"]
    # UAT 24 Okt (P3.5) — labdip wajib ber-Pantone saat dikirim ke supplier (warna OD dari Pustaka → lengkapi Pantone).
    ct = (DB.md_samples.find_one({"id": sid}, {"_id": 0, "color_target": 1}) or {}).get("color_target") or {}
    if ct.get("color_id"):
        DB.color_library.update_one({"id": ct["color_id"], "pantone_code": {"$in": [None, ""]}},
                                    {"$set": {"pantone_code": "19-4052 TCX"}})
    else:
        DB.md_samples.update_one({"id": sid}, {"$set": {"color_target.pantone_code": "19-4052 TCX"}})
    r = requests.post(f"{BASE}/rnd/samples/{sid}/send", headers=md_h,
                      json={"supplier_ids": [sup["id"]], "type_codes": ["labdip"]}, timeout=30)
    assert r.status_code == 200, r.text
    rid = [x for x in r.json()["rounds"] if x.get("supplier_id") == sup["id"]][0]["id"]
    assert requests.post(f"{BASE}/rnd/samples/{sid}/rounds/{rid}/attachments", headers=md_h,
                         files={"file": ("bukti.png", _png(), "image/png")}, timeout=30).status_code == 200
    r = requests.post(f"{BASE}/rnd/samples/{sid}/rounds/{rid}/submit", headers=md_h, timeout=30, json={
        "note": "TEST hasil", "performed_by_user_id": _user("md@kainnusantara.id")["id"],
        "measurements": {"delta_e": 0.8, "colorfastness_wash": 4, "colorfastness_rub": 4}})
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE}/rnd/samples/{sid}/rounds/{rid}/assess", headers=md_h, timeout=30,
                      json={"result": "acc", "score": 90, "note": "ok"})
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE}/rnd/samples/{sid}/decide", headers=md_h, timeout=60, json={
        "supplier_id": sup["id"], "reason_code": "warna_paling_dekat", "price": 39000,
        "supplier_color_name": "Navy 07", "supplier_color_code": "NV-07", "approve_spec": False,
        "supplier_item_name": "Twill Katun 30s"})
    assert r.status_code == 200, r.text            # dulu 400: "Peran 'md' tidak berwenang memutus pemenang"
    dec = r.json()["decision"]
    assert not dec.get("master_error"), dec.get("master_error")
    assert dec.get("spec_submitted") is True
    assert dec.get("supplier_item_name") == "Twill Katun 30s"   # dulu dibuang skema (field tak dikenal)
    spec_id = DB.md_samples.find_one({"id": sid}, {"_id": 0, "spec_id": 1})["spec_id"]
    assert DB.md_specs.find_one({"id": spec_id}, {"_id": 0, "status": 1})["status"] == "review"
    # muncul di antrean ACC Manajer (Pusat Persetujuan · design_acc)
    q = requests.get(f"{BASE}/approvals/my-queue?stage=design_acc", headers=H["manager"], timeout=30)
    assert q.status_code == 200, q.text
    body = q.json()
    rows = body.get("items") if isinstance(body, dict) else body
    mine = [x for x in rows or [] if x.get("id") == spec_id]
    assert mine and mine[0].get("can_decide") is True, mine   # Sales pembuat ≠ Manajer → tidak terblokir SoD


def test_antrean_acuan_md_tanpa_spk_retur(H):
    DB.inspections.insert_one({"id": f"ins_TEST_od23_{TAG}", "number": f"KSC/INS-T{TAG}", "kind": "return_customer",
                               "status": "draft", "entity_id": ENT, "baseline_sample_id": "", "created_at": "2026-10-23T00:00:00+00:00"})
    d = requests.get(f"{BASE}/md/desk", headers=H["md"], timeout=30).json()
    acuan = next(q for q in d["queues"] if q["id"] == "acuan")
    assert f"ins_TEST_od23_{TAG}" not in {r.get("ref_id") for r in acuan.get("rows") or []}


def test_od_siap_hanya_setelah_semua_po_diterima():
    """OD multi-item: PO item pertama selesai TIDAK menandai OD Siap selama PO item kedua belum diterima."""
    sys.path.insert(0, "/app/backend")
    from services import special_order_phase2 as p2  # noqa: E402
    od_id = f"sord_TEST_od23_ready_{TAG}"
    CREATED.append(od_id)
    DB.special_orders.insert_one({"id": od_id, "number": f"TEST-{TAG}", "status": "in_production", "entity_id": ENT,
                                  "status_history": [], "title": f"TEST_OD23_{TAG}"})
    po_a, po_b = f"po_TEST_od23_a_{TAG}", f"po_TEST_od23_b_{TAG}"
    DB.purchase_orders.insert_many([{"id": po_a, "special_order_id": od_id, "status": "completed", "entity_id": ENT},
                                    {"id": po_b, "special_order_id": od_id, "status": "pending", "entity_id": ENT}])
    try:
        assert _run(p2.mark_ready_if_all_received(od_id)) is False
        assert DB.special_orders.find_one({"id": od_id})["status"] == "in_production"
        DB.purchase_orders.update_one({"id": po_b}, {"$set": {"status": "completed"}})
        assert _run(p2.mark_ready_if_all_received(od_id)) is True
        assert DB.special_orders.find_one({"id": od_id})["status"] == "ready"
    finally:
        DB.purchase_orders.delete_many({"id": {"$in": [po_a, po_b]}})


def test_od_selesai_saat_so_ditandai_diterima_tanpa_logistik():
    """UAT 23 Okt — SO hasil OD ditutup lewat "Tandai Diterima (Selesai)" (tanpa bukti terima Logistik) → OD ikut Selesai;
    dulu OD tertinggal "Dikirim" selamanya. Surat jalan saat OD sudah Siap → langsung Dikirim (tanpa ready→ready)."""
    sys.path.insert(0, "/app/backend")
    from services import special_order_phase2 as p2  # noqa: E402
    od_id, so_id = f"sord_TEST_od23_done_{TAG}", f"so_TEST_od23_done_{TAG}"
    CREATED.append(od_id)
    DB.special_orders.insert_one({"id": od_id, "number": f"TESTD-{TAG}", "status": "ready", "entity_id": ENT,
                                  "status_history": [], "title": f"TEST_OD23_{TAG}", "linked_sales_order_id": so_id})
    DB.sales_orders.insert_one({"id": so_id, "number": f"TEST_SO-{so_id}", "status": "shipped", "entity_id": ENT})
    try:
        _run(p2.on_shipment_dispatched(so_id))
        assert DB.special_orders.find_one({"id": od_id})["status"] == "shipped"
        _run(p2.on_delivered(so_id))                       # SO belum Selesai, belum ada bukti terima → tetap Dikirim
        assert DB.special_orders.find_one({"id": od_id})["status"] == "shipped"
        DB.sales_orders.update_one({"id": so_id}, {"$set": {"status": "done"}})
        _run(p2.on_delivered(so_id))
        assert DB.special_orders.find_one({"id": od_id})["status"] == "done"
    finally:
        DB.sales_orders.delete_one({"id": so_id})


def test_pengadaan_otomatis_menunggu_manajer_untuk_sku_baru(monkeypatch):
    """Kunci harga oleh peran yang tidak berwenang merilis SKU baru → item 'menunggu Manajer', bukan galat."""
    sys.path.insert(0, "/app/backend")
    from services import special_order_fulfillment as ful  # noqa: E402
    od_id = f"sord_TEST_od23_pend_{TAG}"
    CREATED.append(od_id)
    DB.special_orders.insert_one({"id": od_id, "number": f"TESTP-{TAG}", "status": "confirmed", "entity_id": ENT,
                                  "title": f"TEST_OD23_{TAG}", "pricing": {"locked": True}})
    # Bentuk baris = `needs()` ASLI (tanpa `active_docs` — itu hanya diisi `progress()`); dulu tiruan memuat
    # `active_docs` sehingga KeyError di jalur nyata (UAT 23 Okt, SORD-261023-0003) tidak tertangkap.
    item = {"key": "soi_x", "line_no": 1, "product_sku": "RND-TEST", "product_lifecycle": "disetujui", "state": {"docs": []}}
    called = []

    async def fake_needs(od):
        return [item]

    async def fake_realize(*a, **k):
        called.append(a)
        return {}
    monkeypatch.setattr(ful, "needs", fake_needs)
    monkeypatch.setattr(ful, "realize", fake_realize)
    out = _run(ful.realize_all(DB.special_orders.find_one({"id": od_id}, {"_id": 0}), {"role": "sales_admin", "name": "t"}))
    assert not called and not out["errors"]
    assert out["pending"] == ["Item 1: SKU baru RND-TEST"]
    doc = DB.special_orders.find_one({"id": od_id})
    assert "Menunggu Manajer" in doc.get("procurement_note", "") and not doc.get("procurement_error")
    # Manajer (berwenang merilis) → item diproses
    out = _run(ful.realize_all(DB.special_orders.find_one({"id": od_id}, {"_id": 0}), {"role": "manager", "name": "m"}))
    assert called and not out["pending"]


def test_tenggat_desain_dan_perkiraan_tiba_po():
    """Tenggat DSR = hari ini + SLA ronde (≤ tenggat kirim); tiba PO = hari ini + lead time kontrak (+ peringatan)."""
    from datetime import date, timedelta
    sys.path.insert(0, "/app/backend")
    from services import special_order_routing as routing  # noqa: E402
    from services import special_order_fulfillment as ful  # noqa: E402
    from services.logistics_service import today_wib  # noqa: E402
    today = date.fromisoformat(today_wib())
    far = (today + timedelta(days=60)).isoformat()
    near = (today + timedelta(days=3)).isoformat()
    due = _run(routing._design_due({"expected_delivery": far}, ENT))   # noqa: SLF001
    assert today < date.fromisoformat(due) < date.fromisoformat(far)
    assert _run(routing._design_due({"expected_delivery": near}, ENT)) == near   # noqa: SLF001 — tidak melewati tenggat
    cid = f"sct_TEST_od23_{TAG}"
    DB.supplier_contracts.insert_one({"id": cid, "lead_time_days": 10, "entity_id": ENT})
    try:
        eta, warn = _run(ful._po_eta({"expected_delivery": far}, {"contract_id": cid, "supplier_id": ""}))   # noqa: SLF001
        assert eta == (today + timedelta(days=10)).isoformat() and warn == ""
        eta, warn = _run(ful._po_eta({"expected_delivery": near}, {"contract_id": cid, "supplier_id": ""}))   # noqa: SLF001
        assert eta > near and "melewati tenggat" in warn
        eta, warn = _run(ful._po_eta({"expected_delivery": far}, {"contract_id": "", "supplier_id": ""}))   # noqa: SLF001
        assert eta == far and warn == ""   # tanpa lead time → tenggat kirim (perilaku lama)
    finally:
        DB.supplier_contracts.delete_one({"id": cid})


def test_kontrak_sample_tanpa_produk_tidak_berlaku_umum():
    """Kontrak dari keputusan sample yang SKU-nya belum lahir tidak dipakai untuk produk lain supplier yang sama."""
    sys.path.insert(0, "/app/backend")
    from services import contract_service as cs  # noqa: E402
    sup = f"sup_TEST_od23_{TAG}"
    DB.supplier_contracts.insert_many([
        {"id": f"sct_TEST_od23_s_{TAG}", "contract_type": "purchase", "partner_id": sup, "status": "active", "entity_id": ENT,
         "product_id": "", "sample_ref": "KSC/SMP-TEST", "tariff_rate": 39000, "tariff_basis": "meter"},
        {"id": f"sct_TEST_od23_g_{TAG}", "contract_type": "purchase", "partner_id": sup, "status": "active", "entity_id": ENT,
         "product_id": "", "tariff_rate": 50000, "tariff_basis": "kg"}])
    try:
        got = _run(cs.resolve_active(partner_id=sup, contract_type="purchase", product_id="prod_lain", entity_id=ENT))
        assert got and got["id"] == f"sct_TEST_od23_g_{TAG}", got   # kontrak umum (non-sample) tetap berlaku
        DB.supplier_contracts.delete_one({"id": f"sct_TEST_od23_g_{TAG}"})
        assert _run(cs.resolve_active(partner_id=sup, contract_type="purchase", product_id="prod_lain", entity_id=ENT)) is None
    finally:
        DB.supplier_contracts.delete_many({"partner_id": sup})
