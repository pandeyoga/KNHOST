"""KP-T3 — Aturan Persetujuan: buang pilihan palsu, tampilkan jenjang efektif per PT (docs/blueprint/unit/KP-T3.md).

Satu database per modul; tes berjalan berurutan dan sebagian memakai keadaan tes sebelumnya (ditulis per tes).
Benih lingkungan B (hitungan tangan dari `config_service.DEFAULT_APPROVAL_RULES` dan `DEFAULT_GLOBAL_SETTINGS`):
  SO  grup: [0, ∞) tanpa persetujuan                             → 1 baris
  PO  grup: [0, 100 jt) tanpa persetujuan · [100 jt, ∞) Manajer   → 2 baris
  PR  grup: [0, 50 jt) tanpa persetujuan  · [50 jt, ∞) Manajer    → 2 baris
  `approval.extra_levels` grup: PO ≥ 500 jt → Admin "Direksi"
PT seed: `ent_ksc`, `ent_kanda`. Akun admin seed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import role_registry
from services import config_resolver as resolver
from services import config_service as cs

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kpt3_aturan_persetujuan.py"
JT = 1_000_000
SNAPSHOT: dict = {}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt3_aturan_persetujuan", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _efektif(klien, h, entity_id, doc_type=""):
    params = {"entity_id": entity_id}
    if doc_type:
        params["doc_type"] = doc_type
    return await klien.get("/api/approval-rules/effective", headers=h, params=params)


def _satu(r, doc_type):
    assert r.status_code == 200, r.text
    rows = [d for d in r.json()["doc_types"] if d["doc_type"] == doc_type]
    assert len(rows) == 1, r.json()
    return rows[0]


def _kode(warnings):
    return [w["code"] for w in warnings]


def _cek_po_grup(dt):
    """Harapan U5 (dipakai juga U7): aturan grup PO benih + jenjang tambahan Direksi."""
    assert dt["source"] == "grup", dt
    assert [(t["min_amount"], t["max_amount"], t["required_role"]) for t in dt["tiers"]] == [
        (0, 100 * JT, ""), (100 * JT, None, "manager")]
    assert all(t["level"] == 1 and t["role_known"] for t in dt["tiers"])
    assert [t["required_role_label"] for t in dt["tiers"]] == ["Tanpa persetujuan", "Manajer"]
    assert len(dt["extra_levels"]) == 1, dt["extra_levels"]
    ex = dt["extra_levels"][0]
    assert (ex["min_amount"], ex["role"], ex["label"], ex["role_label"], ex["role_known"], ex["source"]) == (
        500 * JT, "admin", "Direksi", "Admin", True, "grup")
    assert ex["level"] == 2
    assert dt["unused_group_rules"] == []
    assert dt["warnings"] == []


# ── U3 — benih tanpa `discount` (harus pertama: tes lain menambah aturan) ──────────────────────────────────────────────
async def test_KPT3_U3_benih_tanpa_diskon(klien, kepala_admin):
    r = await klien.get("/api/approval-rules", headers=kepala_admin)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [x for x in rows if x["doc_type"] == "discount"] == []
    # 1 SO + 2 PO + 2 PR = 5
    assert len(rows) == 5, [(x["doc_type"], x["min_amount"]) for x in rows]
    assert sorted(x["doc_type"] for x in rows) == ["purchase_order"] * 2 + ["purchase_requisition"] * 2 + ["sales_order"]
    for x in rows:
        assert x["role_known"] is True
        assert x["required_role_label"] == ("Manajer" if x["required_role"] == "manager" else "Tanpa persetujuan")


# ── U1 — peran `owner` ditolak ─────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT3_U1_peran_owner_ditolak(klien, kepala_admin, db):
    n0 = await db.approval_rules.count_documents({})
    r = await klien.post("/api/approval-rules", headers=kepala_admin,
                         json={"doc_type": "purchase_order", "min_amount": 0, "required_role": "owner"})
    assert r.status_code == 400, r.text
    assert _detail(r).startswith("Peran penyetuju tidak dikenal"), _detail(r)
    assert await db.approval_rules.count_documents({}) == n0


# ── U2 — jenis `discount` ditolak ──────────────────────────────────────────────────────────────────────────────────────
async def test_KPT3_U2_jenis_diskon_ditolak(klien, kepala_admin, db):
    n0 = await db.approval_rules.count_documents({})
    r = await klien.post("/api/approval-rules", headers=kepala_admin,
                         json={"doc_type": "discount", "min_amount": 0, "max_amount": 10})
    assert r.status_code == 400, r.text
    assert _detail(r).startswith("Jenis aturan 'Diskon (%)' sudah tidak dipakai"), _detail(r)
    r = await klien.post("/api/approval-rules", headers=kepala_admin,
                         json={"doc_type": "invoice", "min_amount": 0, "max_amount": 10})
    assert r.status_code == 400, r.text
    assert _detail(r) == ("Jenis dokumen tidak dikenal. Pilihan: Pesanan Penjualan, Pesanan Pembelian, "
                          "Permintaan Pembelian.")
    assert await db.approval_rules.count_documents({}) == n0


# ── U5 — jenjang efektif PO di ent_ksc (aturan grup benih) ─────────────────────────────────────────────────────────────
async def test_KPT3_U5_jenjang_efektif_grup(klien, kepala_admin):
    r = await _efektif(klien, kepala_admin, "ent_ksc", "purchase_order")
    dt = _satu(r, "purchase_order")
    assert r.json()["entity_id"] == "ent_ksc"
    assert r.json()["entity_name"] and r.json()["entity_name"] != "ent_ksc"   # nama PT, bukan id teknis (L1)
    assert len(r.json()["doc_types"]) == 1
    _cek_po_grup(dt)
    SNAPSHOT["U5"] = dt


# ── U4 — skrip migrasi: `owner` → `manager` (keputusan mesin tidak berubah); `discount` dipensiunkan ─────────────────
async def test_KPT3_U4_migrasi_owner_dan_diskon(db):
    from core_utils import new_id, now_iso
    # Fixture (sisip langsung): aturan SO grup ber-`owner`; aturan SO benih dinonaktifkan; satu aturan `discount` lama;
    # satu jenjang tambahan ber-peran tak dikenal di PT ent_kanda (hanya dilaporkan).
    await db.approval_rules.update_many({"doc_type": "sales_order", "entity_id": "all"}, {"$set": {"active": False}})
    rid = new_id("aprule")
    await db.approval_rules.insert_one({"id": rid, "doc_type": "sales_order", "entity_id": "all", "min_amount": 0,
                                        "max_amount": None, "required_role": "owner", "sort": 1, "active": True,
                                        "created_at": now_iso(), "updated_at": now_iso()})
    did = new_id("aprule")
    await db.approval_rules.insert_one({"id": did, "doc_type": "discount", "entity_id": "all", "min_amount": 10,
                                        "max_amount": None, "required_role": "manager", "sort": 2, "active": True,
                                        "is_percent": True, "created_at": now_iso(), "updated_at": now_iso()})
    ada_doc = await db.system_settings.find_one({"scope": "ent_kanda"}, {"_id": 0})
    await db.system_settings.update_one(
        {"scope": "ent_kanda"},
        {"$set": {"approval.extra_levels.purchase_order": [{"min_amount": 900 * JT, "role": "direktur"}]}},
        upsert=True)
    try:
        sebelum = await cs.evaluate_approval("sales_order", 1000, "ent_ksc")
        assert sebelum["required_role"] == "owner"
        assert role_registry.role_satisfies("manager", sebelum["required_role"]) is True
        assert role_registry.role_satisfies("sales", sebelum["required_role"]) is False

        mod = _skrip()
        lapor = await mod.jalankan(tulis=False)          # bawaan: hanya lapor, tidak menulis
        assert [x["id"] for x in lapor["diskon"]] == [did]
        assert [(x["id"], x["required_role"]) for x in lapor["peran_tak_dikenal"]] == [(rid, "owner")]
        assert [(x["scope"], x["doc_type"], x["baris"], x["role"]) for x in lapor["jenjang_tambahan"]] == [
            ("ent_kanda", "purchase_order", 1, "direktur")]
        assert (await db.approval_rules.find_one({"id": rid}))["required_role"] == "owner"
        assert (await db.approval_rules.find_one({"id": did}))["active"] is True

        hasil = await mod.jalankan(tulis=True)
        assert hasil["ditulis"] == {"diskon": 1, "peran_tak_dikenal": 1}
        aturan = await db.approval_rules.find_one({"id": rid}, {"_id": 0})
        assert aturan["required_role"] == "manager" and aturan["migrated_from_role"] == "owner"
        diskon = await db.approval_rules.find_one({"id": did}, {"_id": 0})
        assert diskon["active"] is False and diskon["retired_reason"] == "Jenis aturan tidak dipakai mesin"
        assert await db.approval_rules.count_documents({"id": did}) == 1          # tidak dihapus
        kanda = await db.system_settings.find_one({"scope": "ent_kanda"}, {"_id": 0})
        assert kanda["approval"]["extra_levels"]["purchase_order"][0]["role"] == "direktur"   # tidak diubah

        sesudah = await cs.evaluate_approval("sales_order", 1000, "ent_ksc")
        assert sesudah["required_role"] == "manager"
        assert role_registry.role_satisfies("manager", sesudah["required_role"]) is True
        assert role_registry.role_satisfies("sales", sesudah["required_role"]) is False

        ulang = await mod.jalankan(tulis=True)          # idempoten
        assert ulang["ditulis"] == {"diskon": 0, "peran_tak_dikenal": 0}
    finally:
        if ada_doc is None:
            await db.system_settings.delete_one({"scope": "ent_kanda"})
        else:
            await db.system_settings.update_one({"scope": "ent_kanda"},
                                                {"$unset": {"approval.extra_levels.purchase_order": ""}})


# ── U6 — aturan khusus PT ent_kanda: peringatan celah & lebih longgar dari grup ────────────────────────────────────────
async def test_KPT3_U6_aturan_pt_lebih_longgar(klien, kepala_admin):
    r = await klien.post("/api/approval-rules", headers=kepala_admin,
                         json={"doc_type": "purchase_order", "entity_id": "ent_kanda", "min_amount": 500 * JT,
                               "required_role": "admin"})
    assert r.status_code == 200, r.text
    assert r.json()["id"]
    assert r.json().get("warnings"), r.json()
    assert {"celah", "lebih_longgar_dari_grup"} <= set(_kode(r.json()["warnings"]))
    p = await klien.patch(f"/api/approval-rules/{r.json()['id']}", headers=kepala_admin,
                          json={"description": "Direksi untuk PO besar"})
    assert p.status_code == 200, p.text
    assert {"celah", "lebih_longgar_dari_grup"} <= set(_kode(p.json().get("warnings") or []))

    dt = _satu(await _efektif(klien, kepala_admin, "ent_kanda", "purchase_order"), "purchase_order")
    assert dt["source"] == "pt"
    assert [(t["min_amount"], t["max_amount"], t["required_role"]) for t in dt["tiers"]] == [(500 * JT, None, "admin")]
    assert len(dt["unused_group_rules"]) == 2
    w = {x["code"]: x for x in dt["warnings"]}
    # celah: aturan PT hanya mencakup [500 jt, ∞) → [0, 500 jt) tidak tercakup
    assert (w["celah"]["from_amount"], w["celah"]["to_amount"]) == (0, 500 * JT)
    # lebih longgar: ruas [100 jt, 500 jt) — grup menuntut Manajer, PT tidak menuntut siapa pun.
    # Ruas [0, 100 jt) tidak (grup pun tanpa persetujuan); [500 jt, ∞) tidak (PT menuntut Admin).
    ll = w["lebih_longgar_dari_grup"]
    assert (ll["from_amount"], ll["to_amount"]) == (100 * JT, 500 * JT)
    assert "Manajer" in ll["message"]
    assert "Rp100.000.000" in ll["message"] and "Rp500.000.000" in ll["message"]


# ── U7 — PT lain tidak berubah ─────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT3_U7_pt_lain_tetap(klien, kepala_admin):
    dt = _satu(await _efektif(klien, kepala_admin, "ent_ksc", "purchase_order"), "purchase_order")
    _cek_po_grup(dt)
    if "U5" in SNAPSHOT:
        assert dt == SNAPSHOT["U5"]


# ── U8 — mesin tidak diubah: PO Rp200 jt di ent_kanda lolos, di ent_ksc menuntut Manajer ───────────────────────────────
async def test_KPT3_U8_mesin_tidak_berubah(klien, kepala_admin):
    hasil = {}
    for ent in ("ent_kanda", "ent_ksc"):
        r = await klien.get("/api/settings/evaluate-approval", headers=kepala_admin,
                            params={"doc_type": "purchase_order", "amount": 200 * JT, "entity_id": ent})
        assert r.status_code == 200, r.text
        hasil[ent] = r.json()
    assert hasil["ent_kanda"]["requires_approval"] is False
    assert hasil["ent_ksc"]["required_role"] == "manager"


# ── U9 — tumpang tindih rentang ────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT3_U9_tumpang_tindih(klien, kepala_admin, db):
    await db.approval_rules.update_many({"doc_type": "sales_order", "entity_id": "all"}, {"$set": {"active": False}})
    for body in ({"doc_type": "sales_order", "min_amount": 0, "max_amount": 50 * JT, "required_role": "", "sort": 1},
                 {"doc_type": "sales_order", "min_amount": 30 * JT, "required_role": "manager", "sort": 2}):
        r = await klien.post("/api/approval-rules", headers=kepala_admin, json=body)
        assert r.status_code == 200, r.text
    dt = _satu(await _efektif(klien, kepala_admin, "ent_ksc", "sales_order"), "sales_order")
    assert dt["source"] == "grup"
    tt = [x for x in dt["warnings"] if x["code"] == "tumpang_tindih"]
    # [0, 50 jt) ∩ [30 jt, ∞) = [30 jt, 50 jt)
    assert [(x["from_amount"], x["to_amount"]) for x in tt] == [(30 * JT, 50 * JT)]
    assert "celah" not in _kode(dt["warnings"])


# ── U10 — satu fungsi pemilih aturan untuk layar dan mesin ─────────────────────────────────────────────────────────────
async def test_KPT3_U10_pool_sama_dengan_mesin(db):
    nilai = (0, 1, 49_999_999, 50 * JT, 99_999_999, 100 * JT, 499_999_999, 500 * JT)
    pasangan = [(d, n, e) for d in ("purchase_order", "purchase_requisition") for n in nilai
                for e in ("ent_ksc", "ent_kanda")]
    pasangan += [("sales_order", n, "ent_ksc") for n in (0, 30 * JT, 40 * JT, 50 * JT)]
    assert len(pasangan) == 36   # 8 nilai × 2 jenis × 2 PT + 4 nilai SO (lihat laporan: spesifikasi menulis 20)
    sama = 0
    for doc_type, amount, ent in pasangan:
        pool = await cs.approval_pool(doc_type, ent)
        dari_pool = cs.required_role_for(pool["rules"], amount) or None
        mesin = (await cs.evaluate_approval(doc_type, amount, ent))["required_role"]
        assert dari_pool == mesin, (doc_type, amount, ent, dari_pool, mesin)
        sama += 1
    assert sama == len(pasangan)
    # Pemilihan sumber sama dengan U6/U8: ent_kanda PO memakai aturan PT, ent_ksc PO memakai aturan grup.
    assert (await cs.approval_pool("purchase_order", "ent_kanda"))["source"] == "pt"
    assert (await cs.approval_pool("purchase_order", "ent_ksc"))["source"] == "grup"


# ── U11 — isi `approval.extra_levels` diperiksa saat disimpan ──────────────────────────────────────────────────────────
async def test_KPT3_U11_jenjang_tambahan_peran_tak_dikenal(klien, kepala_admin):
    ctx = {"entity_id": "ent_ksc"}
    awal = await resolver.value_of("approval.extra_levels", ctx)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "approval.extra_levels", "value": {"purchase_order": [{"min_amount": 1, "role": "direktur"}]},
        "scope_type": "global", "scope_id": "", "reason": "uji KP-T3"}]})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Jenjang tambahan baris 1: peran “direktur” tidak ada."
    assert await resolver.value_of("approval.extra_levels", ctx) == awal
    # Nilai minimal harus angka ≥ 0.
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "approval.extra_levels", "value": {"purchase_order": [{"min_amount": -5, "role": "admin"}]},
        "scope_type": "global", "scope_id": "", "reason": "uji KP-T3"}]})
    assert r.status_code == 400, r.text
    assert await resolver.value_of("approval.extra_levels", ctx) == awal


# ── U12 — izin: Sopir 403, peran Tanpa Acuan ber-`settings.view` 200 ───────────────────────────────────────────────────
async def test_KPT3_U12_izin_lihat(klien, akun, sesi, peran_sopir, peran_tanpa_acuan):
    sopir = await akun(peran_sopir)
    r = await _efektif(klien, await sesi(sopir), "ent_ksc")
    assert r.status_code == 403, r.text
    assert "settings.view" not in _detail(r)
    rid = await peran_tanpa_acuan({"settings": ["view"]}, label="Lihat Pengaturan KPT3")
    u = await akun(rid)
    r = await _efektif(klien, await sesi(u), "ent_ksc")
    assert r.status_code == 200, r.text
    assert [d["doc_type"] for d in r.json()["doc_types"]] == ["sales_order", "purchase_order", "purchase_requisition"]


# ── U13 — PT di luar cakupan pengguna ditolak ──────────────────────────────────────────────────────────────────────────
async def test_KPT3_U13_pt_di_luar_cakupan(klien, akun, sesi, kepala_admin):
    peran = (await klien.get("/api/access/roles/sales", headers=kepala_admin)).json()
    perms = {k: list(v) for k, v in (peran.get("permissions") or {}).items()}
    perms["settings"] = sorted(set(perms.get("settings") or []) | {"view"})
    r = await klien.patch("/api/access/roles/sales", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    u = await akun("sales", entitas=("ent_ksc",))
    h = await sesi(u)
    assert (await _efektif(klien, h, "ent_ksc")).status_code == 200
    r = await _efektif(klien, h, "ent_kanda")
    assert r.status_code == 403, r.text
