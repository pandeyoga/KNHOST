"""AG-T1 (AG-01, AG-02, AG-04, AG-05) — kartu tindakan Tanya KN, pencarian bersaring PT, skema alat, masa berlaku kartu.

    python -m pytest backend/tests_mem/test_AGT1_kartu.py -n 0 -q        # dari root repo

Persiapan bersama (FIXTURE, disisipkan langsung): pemasok S1 dan S2 milik `ent_ksc`, S3 milik `ent_kanda`, S4 ber-entitas
`all`; produk P1 (sumber S1) dan P2 (sumber S2); satu gudang bersama (boleh dipakai `ent_ksc`) dan satu gudang khusus
`ent_kanda`. Kartu disiapkan lewat ALUR API `POST /api/ai/tools/propose_action` dengan `X-Entity-Id: ent_ksc` oleh admin
seed (`kepala_admin`), kecuali U9 (akun peran kustom: admin seed selalu boleh semua PT, jadi PT-nya tidak bisa dicabut).
Kartu "data lama" (U6, U7, U6b) disisipkan langsung (fixture).

U4 (dua setujui bersamaan) hanya sah di MongoDB asli: `backend/tests/test_bp_AGT1_kartu_bersamaan.py`.
"""
import ast
import datetime
import json
import re
import uuid
from pathlib import Path

import mongomock.collection as _mc
import pytest
from fastapi import HTTPException

import config_registry as registry
from services.config_resolver import value_of

KSC, KANDA = "ent_ksc", "ent_kanda"
S1, S2, S3, S4 = "sup_agt1_s1", "sup_agt1_s2", "sup_agt1_s3", "sup_agt1_s4"
P1, P2 = "prd_agt1_p1", "prd_agt1_p2"
WH_BERSAMA, WH_KANDA = "wh_agt1_bersama", "wh_agt1_kanda"
KUNCI = "ai.kartu_masa_berlaku_jam"
BACKEND = Path(__file__).resolve().parents[1]
SIMPAN: dict = {}


def _iso(jam_lalu: float = 0.0) -> str:
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=jam_lalu)).isoformat()


def _detail(r) -> str:
    try:
        d = r.json().get("detail")
    except ValueError:
        return r.text
    return d if isinstance(d, str) else str(d)


@pytest.fixture(scope="module")
async def siap(db):
    sekarang = _iso()
    await db.suppliers.insert_many([
        {"id": S1, "code": "S1", "name": "Sumber Satu", "entity_id": KSC, "status": "active", "created_at": sekarang},
        {"id": S2, "code": "S2", "name": "Sumber Dua", "entity_id": KSC, "status": "active", "created_at": sekarang},
        {"id": S3, "code": "S3", "name": "Sumber Tiga", "entity_id": KANDA, "status": "active", "created_at": sekarang},
        {"id": S4, "code": "S4", "name": "Sumber Grup", "entity_id": "all", "status": "active", "created_at": sekarang},
    ])
    await db.products.insert_many([
        {"id": P1, "sku": "AGT1-P1", "name": "Kain AGT1 Satu", "base_unit": "meter", "is_active": True,
         "status": "active", "created_at": sekarang},
        {"id": P2, "sku": "AGT1-P2", "name": "Kain AGT1 Dua", "base_unit": "meter", "is_active": True,
         "status": "active", "created_at": sekarang},
    ])
    await db.supplier_items.insert_many([
        {"id": "si_agt1_p1", "product_id": P1, "supplier_id": S1, "entity_id": KSC, "price": 10_000},
        {"id": "si_agt1_p2", "product_id": P2, "supplier_id": S2, "entity_id": KSC, "price": 20_000},
    ])
    await db.warehouses.insert_many([
        {"id": WH_BERSAMA, "code": "AGT1-B", "name": "Gudang AGT1 Bersama", "active": True, "is_active": True,
         "sharing_mode": "shared"},
        {"id": WH_KANDA, "code": "AGT1-K", "name": "Gudang AGT1 Khusus Kanda", "active": True, "is_active": True,
         "sharing_mode": "dedicated", "entity_ids": [KANDA]},
    ])
    return True


async def _kartu(klien, h, items, alasan: str) -> str:
    r = await klien.post("/api/ai/tools/propose_action", headers=h,
                         json={"action_type": "draft_po", "items": items, "reason": alasan})
    assert r.status_code == 200, r.text
    return r.json()["proposal_id"]


async def _jumlah_po(db, alasan: str) -> int:
    # PO dari kartu bercatatan "Disiapkan Tanya KN · {alasan}" (`ai_actions._exec_po`); alasan unik per uji.
    return await db.purchase_orders.count_documents({"notes": {"$regex": re.escape(alasan)}})


async def _setujui(klien, h, pid, edits=None):
    return await klien.post(f"/api/ai/actions/{pid}/confirm", headers=h, json={"edits": edits})


def _kartu_lama(pid, user_id, entity_id, jam_lalu, status="pending", **extra):
    """Dokumen kartu bentuk lama (sebelum AG-T1: tanpa `expires_at`) — FIXTURE."""
    return {"id": pid, "type": "draft_po", "status": status, "title": "Draf purchase order", "reason": "uji data lama",
            "note": "", "payload": {"pos": [{"supplier_id": S1, "supplier_name": "Sumber Satu", "warehouse_id": WH_BERSAMA,
                                             "warehouse_name": "Gudang AGT1 Bersama",
                                             "items": [{"product_id": P1, "product_name": "Kain AGT1 Satu",
                                                        "quantity": 3, "unit": "meter", "price": 10_000,
                                                        "price_source": "", "expected_grade": "A"}]}]},
            "user_id": user_id, "user_name": "Budi Santoso", "entity_id": entity_id, "session_id": "",
            "created_at": _iso(jam_lalu), **extra}


async def _admin(db):
    return await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})


# ── U1 · U2 — gagal di tengah berakhir `failed`, tidak bisa diulang ───────────────────────────────────────────────────
async def test_AGT1_U1_gagal_di_tengah_berakhir_failed(klien, kepala_admin, db, siap, monkeypatch):
    """Hitungan: P1 (sumber S1) + P2 (sumber S2) → 2 kelompok pemasok → 2 panggilan pembuat PO. Panggilan ke-1 berhasil
    (1 PO tersimpan), panggilan ke-2 dipaksa 400 "Periode tertutup" → kartu `failed`, `result` = 1 nomor, PO = 1."""
    import routers.purchase_orders as po_mod
    alasan = f"uji AG-T1 U1 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 10}, {"product_id": P2, "quantity": 20}],
                       alasan)
    SIMPAN["u1"] = (pid, alasan)
    asli, n = po_mod._create_po_core, {"k": 0}

    async def _palsu(*a, **kw):
        n["k"] += 1
        if n["k"] == 2:
            raise HTTPException(status_code=400, detail="Periode tertutup")
        return await asli(*a, **kw)

    monkeypatch.setattr(po_mod, "_create_po_core", _palsu)
    r = await _setujui(klien, kepala_admin, pid)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "failed", d
    assert len(d["result"]) == 1, d
    assert "Periode tertutup" in d["error"], d
    assert await _jumlah_po(db, alasan) == 1
    simpan = await db.ai_action_proposals.find_one({"id": pid}, {"_id": 0})
    assert simpan["status"] == "failed" and len(simpan["result"]) == 1 and simpan.get("finished_at")


async def test_AGT1_U2_kartu_gagal_tidak_bisa_diulang(klien, kepala_admin, db, siap):
    pid, alasan = SIMPAN["u1"]
    r = await _setujui(klien, kepala_admin, pid)
    assert r.status_code == 409, r.text
    assert _detail(r) == "Draf ini sudah diproses"
    assert await _jumlah_po(db, alasan) == 1                  # sebelum perbaikan: 2 atau lebih
    r = await klien.post(f"/api/ai/actions/{pid}/dismiss", headers=kepala_admin)
    assert r.status_code == 409, r.text


# ── U3 — setujui dua kali berurutan ──────────────────────────────────────────────────────────────────────────────────
async def test_AGT1_U3_setujui_dua_kali_satu_po(klien, kepala_admin, db, siap):
    alasan = f"uji AG-T1 U3 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 5}], alasan)
    r = await _setujui(klien, kepala_admin, pid)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed" and len(r.json()["result"]) == 1
    r = await _setujui(klien, kepala_admin, pid)
    assert r.status_code == 409, r.text
    assert await _jumlah_po(db, alasan) == 1


# ── U5 · U6 · U7 — masa berlaku kartu ────────────────────────────────────────────────────────────────────────────────
async def test_AGT1_U5_kartu_kedaluwarsa_ditolak(klien, kepala_admin, db, siap):
    alasan = f"uji AG-T1 U5 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 5}], alasan)
    await db.ai_action_proposals.update_one({"id": pid}, {"$set": {"expires_at": _iso(1 / 60)}})   # 1 menit lalu
    r = await _setujui(klien, kepala_admin, pid)
    assert r.status_code == 409, r.text
    assert _detail(r) == "Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi."
    assert (await db.ai_action_proposals.find_one({"id": pid}))["status"] == "expired"
    assert await _jumlah_po(db, alasan) == 0


async def test_AGT1_U5b_abaikan_kartu_kedaluwarsa_pesan_sama(klien, kepala_admin, db, siap):
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 5}], f"uji AG-T1 U5b {uuid.uuid4().hex[:6]}")
    await db.ai_action_proposals.update_one({"id": pid}, {"$set": {"expires_at": _iso(1 / 60)}})
    r = await klien.post(f"/api/ai/actions/{pid}/dismiss", headers=kepala_admin)
    assert r.status_code == 409, r.text
    assert _detail(r) == "Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi."
    assert (await db.ai_action_proposals.find_one({"id": pid}))["status"] == "expired"


async def test_AGT1_U5c_kartu_baru_punya_masa_berlaku(klien, kepala_admin, db, siap):
    """Kartu baru: `expires_at` = `created_at` + 24 jam (bawaan pengaturan); GET menyebut PT kartu."""
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 5}], f"uji AG-T1 U5c {uuid.uuid4().hex[:6]}")
    doc = await db.ai_action_proposals.find_one({"id": pid}, {"_id": 0})
    dibuat = datetime.datetime.fromisoformat(doc["created_at"])
    assert datetime.datetime.fromisoformat(doc["expires_at"]) - dibuat == datetime.timedelta(hours=24)
    r = await klien.get(f"/api/ai/actions/{pid}", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert r.json()["entity_name"] == "Sukacita"


async def test_AGT1_U6_kartu_lama_tanpa_masa_berlaku_kedaluwarsa(klien, kepala_admin, db, siap):
    """Hitungan: dibuat 30 jam lalu, masa berlaku bawaan 24 jam → 30 > 24 → `expired` saat dibaca."""
    adm = await _admin(db)
    await db.ai_action_proposals.insert_one(_kartu_lama("aiact_agt1_u6", adm["id"], KSC, 30))
    r = await klien.get("/api/ai/actions/aiact_agt1_u6", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "expired"
    assert (await db.ai_action_proposals.find_one({"id": "aiact_agt1_u6"}))["status"] == "expired"


async def test_AGT1_U7_masa_berlaku_per_pt(klien, kepala_admin, db, siap):
    """`ai.kartu_masa_berlaku_jam` = 48 khusus ent_ksc. Kartu 30 jam lalu: ent_ksc 30 < 48 → `pending`;
    ent_kanda memakai bawaan 24 → 30 > 24 → `expired`."""
    adm = await _admin(db)
    await db.ai_action_proposals.insert_many([_kartu_lama("aiact_agt1_u7k", adm["id"], KSC, 30),
                                              _kartu_lama("aiact_agt1_u7d", adm["id"], KANDA, 30)])
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": KUNCI, "value": 48, "scope_type": "entity", "scope_id": KSC, "reason": "uji AG-T1 U7"}]})
    assert r.status_code == 200, r.text
    try:
        r = await klien.get("/api/ai/actions/aiact_agt1_u7k", headers=kepala_admin)
        assert r.status_code == 200 and r.json()["status"] == "pending", r.text
        r = await klien.get("/api/ai/actions/aiact_agt1_u7d", headers={**kepala_admin, "X-Entity-Id": KANDA})
        assert r.status_code == 200 and r.json()["status"] == "expired", r.text
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin, json={
            "key": KUNCI, "scope_type": "entity", "scope_id": KSC, "reason": "pulihkan sesudah uji AG-T1 U7"})


async def test_AGT1_U6b_proses_mati_menjadi_gagal(klien, kepala_admin, db, siap):
    """Kartu `running` yang tidak berubah > 10 menit (batas teknis) = proses mati → `failed` saat dibaca."""
    adm = await _admin(db)
    await db.ai_action_proposals.insert_one(_kartu_lama("aiact_agt1_u6b", adm["id"], KSC, 1, status="running",
                                                        updated_at=_iso(11 / 60)))
    r = await klien.get("/api/ai/actions/aiact_agt1_u6b", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "failed"
    assert r.json()["error"] == "Proses berhenti sebelum selesai. Periksa daftar PO sebelum meminta draf baru."
    r = await _setujui(klien, kepala_admin, "aiact_agt1_u6b")
    assert r.status_code == 409, r.text


# ── U8 · U9 · U10 — kartu hanya untuk PT tempat ia disiapkan ─────────────────────────────────────────────────────────
async def test_AGT1_U8_pt_aktif_berbeda_atau_semua_pt_409(klien, kepala_admin, db, siap):
    alasan = f"uji AG-T1 U8 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 5}], alasan)
    for ent in (KANDA, "all"):
        r = await _setujui(klien, {**kepala_admin, "X-Entity-Id": ent}, pid)
        assert r.status_code == 409, (ent, r.text)
        assert _detail(r) == "Draf ini disiapkan untuk Sukacita. Pindah ke PT itu lalu setujui lagi.", ent
        assert (await db.ai_action_proposals.find_one({"id": pid}))["status"] == "pending"
    assert await _jumlah_po(db, alasan) == 0


async def test_AGT1_U9_pt_kartu_dicabut_dari_akses_403(klien, akun, sesi, db, siap, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"ai": ["view"], "purchase_order": ["view", "create"]}, label="Pembuat PO AG-T1")
    u = await akun(rid, entitas=(KSC, KANDA))
    alasan = f"uji AG-T1 U9 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, await sesi(u, entitas=KSC), [{"product_id": P1, "quantity": 5}], alasan)
    await db.users.update_one({"id": u["id"]}, {"$set": {"allowed_entity_ids": [KANDA], "home_entity_id": KANDA}})
    r = await _setujui(klien, await sesi(u, entitas=KANDA), pid)
    assert r.status_code == 403, r.text
    assert _detail(r) == "Anda tidak lagi punya akses ke PT draf ini."
    r = await _setujui(klien, await sesi(u, entitas=KSC), pid)       # pagar PT permintaan (entity_ctx) tetap 403
    assert r.status_code == 403, r.text
    assert (await db.ai_action_proposals.find_one({"id": pid}))["status"] == "pending"
    assert await _jumlah_po(db, alasan) == 0


async def test_AGT1_U10_siapkan_dalam_mode_semua_pt_ditolak(klien, kepala_admin, db, siap):
    sebelum = await db.ai_action_proposals.count_documents({})
    r = await klien.post("/api/ai/tools/propose_action", headers={**kepala_admin, "X-Entity-Id": "all"},
                         json={"action_type": "draft_po", "items": [{"product_id": P1, "quantity": 5}],
                               "reason": "uji AG-T1 U10"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Pilih satu PT dulu. Tindakan tidak bisa disiapkan dalam mode Semua PT."
    assert await db.ai_action_proposals.count_documents({}) == sebelum


# ── U11 — galat isian tidak mengubah status ──────────────────────────────────────────────────────────────────────────
async def test_AGT1_U11_galat_isian_sebelum_klaim(klien, kepala_admin, db, siap, monkeypatch):
    """Semua qty 0 → 400 dan status TIDAK PERNAH berubah (pengintai mencatat tiap `$set.status` ke koleksi kartu: kode lama
    mengklaim `running` dulu lalu memulihkan `pending`). Lalu qty 5 → 200 `confirmed`."""
    alasan = f"uji AG-T1 U11 {uuid.uuid4().hex[:6]}"
    pid = await _kartu(klien, kepala_admin, [{"product_id": P1, "quantity": 5}], alasan)
    tulis: list = []
    for nama in ("find_one_and_update", "update_one", "update_many"):
        asli = getattr(_mc.Collection, nama)

        def _intai(self, flt, upd, *a, _asli=asli, **kw):
            if self.name == "ai_action_proposals" and isinstance(upd, dict):
                st = (upd.get("$set") or {}).get("status")
                if st:
                    tulis.append(st)
            return _asli(self, flt, upd, *a, **kw)
        monkeypatch.setattr(_mc.Collection, nama, _intai)
    r = await _setujui(klien, kepala_admin, pid, {"pos": [{"items": [{"quantity": 0}]}]})
    assert r.status_code == 400, r.text
    assert tulis == [], tulis
    assert (await db.ai_action_proposals.find_one({"id": pid}))["status"] == "pending"
    monkeypatch.undo()
    r = await _setujui(klien, kepala_admin, pid, {"pos": [{"items": [{"quantity": 5}]}]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert await _jumlah_po(db, alasan) == 1


# ── U12 · U13 — pencarian asisten hanya data PT pengguna ─────────────────────────────────────────────────────────────
async def test_AGT1_U12_cari_pemasok_bersaring_pt(klien, akun, sesi, db, siap):
    h = await sesi(await akun("sales", entitas=(KSC,)))
    r = await klien.post("/api/ai/tools/find_entities", headers=h, json={"kind": "supplier", "query": "s"})
    assert r.status_code == 200, r.text
    ids = {c["id"] for c in r.json()["candidates"]}
    assert {S1, S2, S4} <= ids, ids
    assert S3 not in ids, ids
    pt = {d["id"]: d["entity_id"] async for d in db.suppliers.find({"id": {"$in": list(ids)}})}
    assert set(pt.values()) <= {KSC, "all"}, pt                # pemasok seed milik PT lain juga tidak muncul


async def test_AGT1_U13_cari_gudang_dan_sales_bersaring_pt(klien, akun, sesi, siap):
    sales_ksc = await akun("sales", entitas=(KSC,))
    sales_kanda = await akun("sales", entitas=(KANDA,))
    h = await sesi(sales_ksc)
    r = await klien.post("/api/ai/tools/find_entities", headers=h, json={"kind": "warehouse", "query": "gudang agt1"})
    assert r.status_code == 200, r.text
    ids = {c["id"] for c in r.json()["candidates"]}
    assert WH_BERSAMA in ids and WH_KANDA not in ids, ids
    r = await klien.post("/api/ai/tools/find_entities", headers=h, json={"kind": "sales_person", "query": "uji sales"})
    assert r.status_code == 200, r.text
    ids = {c["id"] for c in r.json()["candidates"]}
    assert sales_ksc["id"] in ids and sales_kanda["id"] not in ids, ids


async def test_AGT1_U13b_batas_hasil_dihormati(klien, kepala_admin, siap):
    """`limit` 1–20, bawaan 5. Kueri "sumber" cocok dengan S1, S2, S4 (cakupan ent_ksc) → limit 2 → 2 kandidat."""
    r = await klien.post("/api/ai/tools/find_entities", headers=kepala_admin,
                         json={"kind": "supplier", "query": "sumber", "limit": 2})
    assert r.status_code == 200, r.text
    assert len(r.json()["candidates"]) == 2
    r = await klien.post("/api/ai/tools/find_entities", headers=kepala_admin,
                         json={"kind": "supplier", "query": "sumber", "limit": 999})
    assert len(r.json()["candidates"]) == 3


# ── U14 — skema alat = yang dilayani kode (uji statik) ───────────────────────────────────────────────────────────────
def _enum(tools, tool, param):
    t = next(x for x in tools if x["name"] == tool)
    return t["parameters"]["properties"][param]["enum"]


def _kunci_dict_dalam(fungsi: ast.AST, jangkar: str) -> set:
    """Kunci literal dict pertama di badan `fungsi` yang memuat kunci `jangkar` (tabel pelayanan)."""
    for node in ast.walk(fungsi):
        if isinstance(node, ast.Dict):
            kunci = [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if jangkar in kunci:
                return set(kunci)
    raise AssertionError(f"tabel ber-kunci {jangkar!r} tidak ditemukan")


def _layanan_ai_tools() -> dict:
    """Nilai yang DILAYANI `services/ai_tools.py`, dibaca dari kodenya (AST, tanpa menjalankan apa pun)."""
    pohon = ast.parse((BACKEND / "services" / "ai_tools.py").read_text(encoding="utf-8"))
    fn = {n.name: n for n in pohon.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    laporan = _kunci_dict_dalam(fn["run_report"], "daily_brief")
    for node in ast.walk(fn["run_report"]):      # `if rep in ("cash_position", …)` — laporan keuangan
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In) and isinstance(node.comparators[0], ast.Tuple):
            nilai = {e.value for e in node.comparators[0].elts if isinstance(e, ast.Constant)}
            if "cash_position" in nilai:
                laporan |= nilai
    return {"get_document.doc_type": _kunci_dict_dalam(fn["get_document"], "sales_order"),
            "find_entities.kind": _kunci_dict_dalam(fn["find_entities"], "customer"),
            "run_report.report": laporan}


def test_AGT1_U14_enum_skema_sama_dengan_yang_dilayani():
    from services import ai_actions
    from services import ai_ops_metrics as ops
    tools = json.loads((BACKEND / "data" / "ai" / "tools_kn_analitik_v1.json").read_text(encoding="utf-8"))
    layan = _layanan_ai_tools()
    tawar = {"get_document.doc_type": _enum(tools, "get_document", "doc_type"),
             "find_entities.kind": _enum(tools, "find_entities", "kind"),
             "run_report.report": _enum(tools, "run_report", "report")}
    beda = {k: sorted(set(v) - layan[k]) for k, v in tawar.items() if set(v) - layan[k]}
    assert beda == {}, f"skema menawarkan nilai tanpa pelaksana: {beda}"
    assert {k: len(v) for k, v in tawar.items()} == {"get_document.doc_type": 7, "find_entities.kind": 5,
                                                     "run_report.report": 18}
    assert {k: set(v) for k, v in tawar.items()} == layan                      # dan sebaliknya: yang dilayani ditawarkan
    assert set(_enum(tools, "ops_metrics", "kind")) == set(ops.KINDS)
    assert set(_enum(tools, "propose_action", "action_type")) == set(ai_actions.TYPES)


# ── U17 — putaran pengaturan `ai.kartu_masa_berlaku_jam` (02 §2.4 butir 1) ───────────────────────────────────────────
def _isi(value, scope_type="global", scope_id=""):
    return {"items": [{"key": KUNCI, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": "uji AG-T1 U17"}]}


async def test_AGT1_U17_putaran_t1_config(klien, kepala_admin, siap):
    e = registry.require(KUNCI)
    assert (e["group"], e["type"], e["default"], e["min"], e["max"], e["unit"]) == ("sistem", "int", 24, 1, 168, "jam")
    assert e["scopes"] == ["global", "entity"] and e["permission"] == ["settings", "manage"]
    assert (e["risk"], e["requires_reason"], e["status"]) == ("low", False, "active")
    assert e["label"] == "Kartu tindakan asisten berlaku selama (jam)"
    assert e["consumers"] == ["services/ai_actions.py:propose_action", "services/ai_actions.py:_masa_berlaku"]
    assert await value_of(KUNCI) == 24
    try:
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(36))
        assert r.status_code == 200, r.text
        assert await value_of(KUNCI) == 36 and await value_of(KUNCI, {"entity_id": KSC}) == 36
        r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
        assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] == 36
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(12, "entity", KANDA))
        assert r.status_code == 200, r.text
        assert await value_of(KUNCI, {"entity_id": KANDA}) == 12
        assert await value_of(KUNCI, {"entity_id": KSC}) == 36                 # PT lain tidak ikut
        for salah in (0, 200):
            r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(salah))
            assert r.status_code == 400, (salah, r.text)
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin, json={
            "key": KUNCI, "scope_type": "entity", "scope_id": KANDA, "reason": "pulihkan sesudah uji AG-T1"})
        await klien.post("/api/config/values/reset", headers=kepala_admin, json={
            "key": KUNCI, "scope_type": "global", "reason": "pulihkan sesudah uji AG-T1"})
    assert await value_of(KUNCI) == 24 and await value_of(KUNCI, {"entity_id": KANDA}) == 24


async def test_AGT1_U17b_nilai_berlaku_saat_kartu_dibuat(klien, kepala_admin, db, siap):
    """Uji perilaku (02 §2.4 butir 2): 6 jam untuk ent_kanda → kartu Kanda berlaku 6 jam, kartu KSC tetap 24 jam."""
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(6, "entity", KANDA))
    assert r.status_code == 200, r.text
    try:
        hasil = {}
        for ent in (KANDA, KSC):
            pid = await _kartu(klien, {**kepala_admin, "X-Entity-Id": ent}, [{"product_id": P1, "quantity": 1}],
                               f"uji AG-T1 U17b {ent}")
            d = await db.ai_action_proposals.find_one({"id": pid}, {"_id": 0})
            hasil[ent] = datetime.datetime.fromisoformat(d["expires_at"]) - datetime.datetime.fromisoformat(d["created_at"])
        assert hasil == {KANDA: datetime.timedelta(hours=6), KSC: datetime.timedelta(hours=24)}
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin, json={
            "key": KUNCI, "scope_type": "entity", "scope_id": KANDA, "reason": "pulihkan sesudah uji AG-T1"})
