"""AG-T3 serah-terima (b) — draf PO kartu lama dijalankan lewat endpoint layar `POST /api/purchase-orders`.

    python -m pytest backend/tests_mem/test_AGT3_pengalihan.py -n 0 -q        # dari root repo

Langkah kerja 6–7 spesifikasi (`docs/blueprint/unit/AG-T3.md`): tiap PO dari kartu `draft_po` dikirim lewat pintu aplikasi
sendiri (izin & PT pengguna) dengan kunci idempotensi `<id kartu>:<urutan>` dan aturan hasil-sebagian AG-T1; pemanggilan
`_create_po_core` langsung dicabut. Pengingat ke sales tetap `create_notification` (satu-satunya pengecualian: tidak ada
endpoint layarnya). Uji Tanya KN lama untuk draf PO (`test_AGT1_kartu.py`) tetap hijau.

Persiapan (FIXTURE, disisip langsung): pemasok T1/T2 milik `ent_ksc`, produk Q1 (sumber T1) dan Q2 (sumber T2), satu gudang
bersama. Kartu disiapkan & disetujui lewat ALUR API (`POST /api/ai/tools/propose_action`, `POST /api/ai/actions/{id}/confirm`)
oleh admin seed, `X-Entity-Id: ent_ksc`.
Hitungan: Q1 (T1) + Q2 (T2) → 2 kelompok pemasok → 2 panggilan `POST /api/purchase-orders` → 2 PO, kunci `<id>:0`, `<id>:1`.
"""
import ast
import datetime
import re
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
T1, T2, Q1, Q2, WH = "sup_agt3_t1", "sup_agt3_t2", "prd_agt3_q1", "prd_agt3_q2", "wh_agt3_bersama"
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
async def siap(db):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.suppliers.insert_many([
        {"id": T1, "code": "T1", "name": "Pemasok AGT3 Satu", "entity_id": KSC, "status": "active", "created_at": now},
        {"id": T2, "code": "T2", "name": "Pemasok AGT3 Dua", "entity_id": KSC, "status": "active", "created_at": now}])
    await db.products.insert_many([
        {"id": Q1, "sku": "AGT3-Q1", "name": "Kain AGT3 Satu", "base_unit": "meter", "is_active": True, "status": "active",
         "created_at": now},
        {"id": Q2, "sku": "AGT3-Q2", "name": "Kain AGT3 Dua", "base_unit": "meter", "is_active": True, "status": "active",
         "created_at": now}])
    await db.supplier_items.insert_many([
        {"id": "si_agt3_q1", "product_id": Q1, "supplier_id": T1, "entity_id": KSC, "price": 10_000},
        {"id": "si_agt3_q2", "product_id": Q2, "supplier_id": T2, "entity_id": KSC, "price": 20_000}])
    await db.warehouses.insert_one({"id": WH, "code": "AGT3-B", "name": "Gudang AGT3 Bersama", "active": True,
                                    "is_active": True, "sharing_mode": "shared"})
    return True


async def _kartu(klien, h, alasan):
    r = await klien.post("/api/ai/tools/propose_action", headers=h, json={
        "action_type": "draft_po", "reason": alasan,
        "items": [{"product_id": Q1, "quantity": 10}, {"product_id": Q2, "quantity": 20}]})
    assert r.status_code == 200, r.text
    return r.json()["proposal_id"]


async def _po(db, alasan):
    return await db.purchase_orders.find({"notes": {"$regex": re.escape(alasan)}}, {"_id": 0}).to_list(20)


async def test_AGT3_b1_draf_po_lewat_endpoint_layar_berkunci_per_po(klien, db, kepala_admin, siap, monkeypatch):
    import routers.purchase_orders as po_mod
    lewat_endpoint = []
    # Endpoint terdaftar di router saat aplikasi dibuat; pengintai dipasang di fungsi inti yang dipanggilnya.
    asli_inti = po_mod._create_po_core

    async def _inti(payload, actor, **kw):
        lewat_endpoint.append(kw.get("active_entity_id"))
        return await asli_inti(payload, actor, **kw)
    monkeypatch.setattr(po_mod, "_create_po_core", _inti)
    alasan = f"uji AG-T3 b1 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, alasan)
    r = await klien.post(f"/api/ai/actions/{pid}/confirm", headers=kepala_admin, json={"edits": None})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "confirmed" and len(d["result"]) == 2, d
    pos = await _po(db, alasan)
    assert len(pos) == 2 and {p["entity_id"] for p in pos} == {KSC}
    assert sorted(p["po_number"] for p in pos) == sorted(d["result"])
    assert lewat_endpoint == [KSC, KSC]                 # dua kali lewat endpoint, PT dari header PT kartu
    kunci = await db.idempotency_keys.find({"key": {"$regex": f"^{re.escape(pid)}:"}}, {"_id": 0}).to_list(10)
    assert sorted(k["key"] for k in kunci) == [f"{pid}:0", f"{pid}:1"]
    assert {k["path"] for k in kunci} == {"/api/purchase-orders"}


async def test_AGT3_b2_kirim_ulang_kunci_sama_satu_po(klien, db, kepala_admin, siap):
    """Awalan `/api/purchase-orders` ber-idempotensi: kunci kartu yang sama → jawaban pertama, tidak ada PO kedua."""
    body = {"supplier_id": T1, "warehouse_id": WH, "created_by": "uji", "notes": f"uji AG-T3 b2 {uuid.uuid4().hex[:6]}",
            "items": [{"product_id": Q1, "quantity": 3, "unit": "meter", "price": 10_000, "expected_grade": "A"}]}
    h = {**kepala_admin, "Idempotency-Key": f"aiact_uji_{uuid.uuid4().hex[:6]}:0"}
    r1 = await klien.post("/api/purchase-orders", headers=h, json=body)
    r2 = await klien.post("/api/purchase-orders", headers=h, json=body)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r2.headers.get("X-Idempotent-Replay") == "true" and r1.json()["id"] == r2.json()["id"]
    assert await db.purchase_orders.count_documents({"notes": body["notes"]}) == 1


async def test_AGT3_b3_gagal_di_tengah_hasil_sebagian_tetap(klien, db, kepala_admin, siap, monkeypatch):
    """Aturan hasil-sebagian AG-T1 lewat endpoint: PO ke-2 ditolak pintu (400) → kartu `failed`, PO ke-1 tetap tercatat."""
    import routers.purchase_orders as po_mod
    asli, n = po_mod._create_po_core, {"k": 0}

    async def _palsu(*a, **kw):
        n["k"] += 1
        if n["k"] == 2:
            raise HTTPException(status_code=400, detail="Periode tertutup")
        return await asli(*a, **kw)
    monkeypatch.setattr(po_mod, "_create_po_core", _palsu)
    alasan = f"uji AG-T3 b3 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, alasan)
    r = await klien.post(f"/api/ai/actions/{pid}/confirm", headers=kepala_admin, json={"edits": None})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "failed" and len(d["result"]) == 1 and "Periode tertutup" in d["error"], d
    assert len(await _po(db, alasan)) == 1
    r = await klien.post(f"/api/ai/actions/{pid}/confirm", headers=kepala_admin, json={"edits": None})
    assert r.status_code == 409


def test_AGT3_b4_tidak_ada_jalan_pintas_pembuat_po():
    """Statik: `ai_actions` tidak lagi memanggil `_create_po_core`; `create_notification` hanya di pengingat ke sales."""
    src = (BACKEND / "services" / "ai_actions.py").read_text(encoding="utf-8")
    pohon = ast.parse(src)
    nama = {getattr(n, "attr", getattr(n, "id", "")) for n in ast.walk(pohon) if isinstance(n, (ast.Name, ast.Attribute))}
    assert "_create_po_core" not in nama
    pemakai = [f.name for f in ast.walk(pohon) if isinstance(f, ast.AsyncFunctionDef)
               and any(getattr(n, "id", getattr(n, "attr", "")) == "create_notification" for n in ast.walk(f))]
    assert pemakai == ["_exec_reminders"]
    from services.ai_cards import write_allowed
    assert write_allowed("POST", "/api/purchase-orders") and not write_allowed("POST", "/api/purchase-orders/x/approve")
