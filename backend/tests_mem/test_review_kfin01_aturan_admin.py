"""Review adversarial K-FIN-01 (commit 790464b) — **pilihan Admin di Aturan Persetujuan tidak boleh ditimpa**.

Temuan R-KF-01: K-FIN-01 menambah Finance ke baris yang menyebut Manajer di `approval_policy_service._row`. Fungsi itu
dipakai juga oleh `_parse_levels` (isi `PUT /api/approval-policies/{jenis}` dari layar Pengaturan › Aturan Persetujuan),
sehingga Admin TIDAK BISA menyimpan baris "Manajer saja": Finance (dan peran kustom ber-dasar Finance) selalu ditambahkan
diam-diam, lalu `can_decide` meloloskan Finance. Keputusan pemilik ("untuk sekarang …") adalah nilai BAWAAN; mengubahnya
per baris adalah pengaturan Admin (02_STANDAR §2) dan migrasi K-FIN-01 sendiri berjanji "perubahan Admin sesudahnya
bertahan".

Hitung tangan: PUT tagihan pemasok (grup) jenjang 1 = [Manajer, Admin] → baris tersimpan [admin, manager]; Finance yang
memegang izin setujui tagihan → `can_decide` ditolak ("Peran Anda belum tercantum"). Baris bawaan (belum disimpan) tetap
menyebut Finance.
"""
import pytest

pytestmark = pytest.mark.anyio


async def test_R_KF_01_bawaan_tetap_menyebut_finance(db):
    from services import approval_policy_service as aps
    rows = await aps.default_rows_for("vendor_bill", "all")
    assert all("finance" in r["roles"] for r in rows if "manager" in r["roles"]), rows


async def test_R_KF_01_admin_menyimpan_manajer_saja(klien, kepala_admin, db):
    from services import approval_policy_service as aps
    r = await klien.put("/api/approval-policies/vendor_bill", headers=kepala_admin, json={
        "entity_id": "all", "reason": "uji review K-FIN-01: Manajer saja",
        "levels": [{"level": 1, "tiers": [{"min_amount": 0, "roles": ["manager", "admin"]}]}]})
    assert r.status_code == 200, r.text
    tersimpan = await db.approval_policies.find({"doc_kind": "vendor_bill", "entity_id": "all", "active": True},
                                                {"_id": 0}).to_list(None)
    assert [sorted(x["roles"]) for x in tersimpan] == [["admin", "manager"]], [x["roles"] for x in tersimpan]
    fin = {"id": "uji_fin_rkf", "name": "Uji Finance", "role": "finance"}
    res = await aps.can_decide("vendor_bill", "ent_ksc", 5_000_000, fin)
    assert not res["allowed"] and res["code"] == "batas", res
    mgr = {"id": "uji_mgr_rkf", "name": "Uji Manajer", "role": "manager"}
    assert (await aps.can_decide("vendor_bill", "ent_ksc", 5_000_000, mgr))["allowed"]

    # Admin menambahkan Finance secara eksplisit → tersimpan dan berlaku.
    r = await klien.put("/api/approval-policies/vendor_bill", headers=kepala_admin, json={
        "entity_id": "all", "reason": "uji review K-FIN-01: Finance ikut",
        "levels": [{"level": 1, "tiers": [{"min_amount": 0, "roles": ["manager", "admin", "finance"]}]}]})
    assert r.status_code == 200, r.text
    assert (await aps.can_decide("vendor_bill", "ent_ksc", 5_000_000, fin))["allowed"]


async def test_R_KF_03_migrasi_menyebut_peran_kustom_berdasar_finance(klien, kepala_admin, db):
    """R-KF-03 — `migrate_kfin01_approval_policies` berjalan di `run_bootstrap`, SEBELUM `server.lifespan` memuat peran
    kustom ke registry (`custom_role_service.sync_registry`). Docstring-nya berjanji peran kustom ber-dasar Finance ikut
    disebut, tetapi pada start sungguhan `role_registry.setara_untuk` belum mengenal peran kustom sama sekali → baris
    tersimpan hanya mendapat Finance bawaan, dan penanda sekali-jalan membuatnya tidak pernah diperbaiki."""
    import bootstrap
    import role_registry as reg
    from services.custom_role_service import list_custom, sync_registry
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Finance Cabang RKF", "base_role": "finance", "description": "uji review K-FIN-01"})
    assert r.status_code == 200, r.text
    cid = (r.json().get("role") or r.json())["id"]
    await db.approval_policies.insert_one({
        "id": "apol_rkf3", "doc_kind": "landed_cost", "entity_id": "all", "level": 1, "label": "Persetujuan",
        "min_amount": 0, "max_amount": None, "roles": ["admin", "manager"], "any_holder": False, "sort": 1,
        "active": True, "source": "migrasi"})
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$unset": {"kfin01_aturan_persetujuan": ""}})
    reg.register_custom_roles([])   # keadaan registry saat `run_bootstrap` di proses yang baru start
    try:
        await bootstrap.migrate_kfin01_approval_policies()
    finally:
        await sync_registry()
    assert cid in [c["id"] for c in await list_custom()]
    roles = (await db.approval_policies.find_one({"id": "apol_rkf3"}))["roles"]
    assert {"admin", "manager", "finance", cid} <= set(roles), roles
    assert len(roles) == len(set(roles)), roles
