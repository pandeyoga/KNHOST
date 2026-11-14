"""PR-T2 — wewenang dari izin, bukan nama peran acuan (docs/blueprint/unit/PR-T2.md), serah-terima (b).

Peran uji baku `02_STANDAR.md` §6 dibuat lewat API SESUDAH proses awal (jadi sesudah migrasi): "Tanpa Acuan" (hanya izin
yang diuji), "Manajer Kosong" (acuan Manajer, semua modul "Tidak ada"), Sopir. `mgr` = manajer seed, `adm` = admin seed.
"Nyalakan ulang" = `bootstrap.run_bootstrap()` + `custom_role_service.sync_registry()` (urutan `server.lifespan`).
Di kode lama uji ini merah: izin pengganti belum dikenal katalog (400 saat peran dibuat) dan gerbang nama peran
menolak peran kustom tanpa acuan / meloloskan Manajer Kosong.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import bootstrap

pytestmark = pytest.mark.anyio

BACKEND = Path(__file__).resolve().parents[1]
SIMPAN: dict = {}


async def _nyalakan_ulang() -> None:
    from services.custom_role_service import sync_registry
    await bootstrap.run_bootstrap()
    await sync_registry()


async def _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir):
    """Header sesi Manajer Kosong dan Sopir (diperiksa LEBIH DULU: di kode lama Manajer Kosong lolos lewat nama peran)."""
    return [await sesi(await akun(rid)) for rid in (await peran_manajer_kosong(), peran_sopir)]


async def _tanpa_acuan(akun, sesi, peran_tanpa_acuan, izin: dict, label: str):
    return await sesi(await akun(await peran_tanpa_acuan(izin, label=label)))


async def _kode(klien, metode: str, jalur: str, headers, json=None) -> int:
    return (await klien.request(metode, jalur, headers=headers, json=json)).status_code


async def test_U01_hpp(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, sopir = await _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    assert [await _kode(klien, "GET", "/api/costing/wac", h) for h in (mk, sopir)] == [403, 403]
    ta = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan, {"costing": ["view"]}, "TA HPP")
    assert await _kode(klien, "GET", "/api/costing/wac", ta) == 200


async def test_U02_beranda_manajer(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, sopir = await _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    assert [await _kode(klien, "GET", "/api/home/manager", h) for h in (mk, sopir)] == [403, 403]
    ta = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan, {"manager_home": ["view"]}, "TA Beranda")
    assert await _kode(klien, "GET", "/api/home/manager", ta) == 200


async def test_U03_papan_peringkat_dan_tarif(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    jalur = ("/api/sales/leaderboard", "/api/incentive-rates")
    mk, sopir = await _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    assert [[await _kode(klien, "GET", j, h) for j in jalur] for h in (mk, sopir)] == [[403, 403], [403, 403]]
    ta = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan, {"sales_force": ["view"]}, "TA Tim Sales")
    assert [await _kode(klien, "GET", j, ta) for j in jalur] == [200, 200]


async def test_U04_target_sales(klien, db, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, _ = await _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    isi = {"sales_id": sales["id"], "period_type": "month", "period": "2026-11", "target_sales_amount": 1000000}
    assert await _kode(klien, "POST", "/api/sales-targets", mk, {**isi, "target_sales_amount": 5}) == 403
    ta = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan, {"sales_force": ["view", "update"]}, "TA Target")
    assert await _kode(klien, "POST", "/api/sales-targets", ta, isi) == 200
    assert await db.sales_targets.count_documents({"sales_id": sales["id"], "period": "2026-11"}) == 1
    doc = await db.sales_targets.find_one({"sales_id": sales["id"], "period": "2026-11"})
    assert doc["target_sales_amount"] == 1000000   # tulisan Manajer Kosong tidak sampai


async def test_U05_kebersihan_data(klien, akun, sesi, peran_tanpa_acuan):
    h = await sesi(await akun(await peran_tanpa_acuan({"system_tools": ["view"]}, label="TA Kebersihan")))
    for j in ("/api/data-hygiene/summary", "/api/data-hygiene/log", "/api/data-hygiene/preview",
              "/api/data-hygiene/unverified-locations", "/api/turn-notifications/map"):
        assert await _kode(klien, "GET", j, h) == 200, j
    assert await _kode(klien, "POST", "/api/data-hygiene/run", h) == 403   # butuh `system_tools.configure`


async def test_U06_asisten(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    mk, sopir = await _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    assert [await _kode(klien, "GET", "/api/ai/status", h) for h in (mk, sopir)] == [403, 403]
    ta = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan, {"ai": ["view"]}, "TA Asisten")
    assert await _kode(klien, "GET", "/api/ai/status", ta) == 200
    assert await _kode(klien, "GET", "/api/ai/usage", ta) == 403   # butuh `ai.manage`


async def test_U07_templat_per_izin(klien, akun, sesi, peran_tanpa_acuan):
    h = await sesi(await akun(await peran_tanpa_acuan({"ai": ["view"], "ai_template": ["daily_brief"]},
                                                      label="TA Templat")))
    r = await klien.get("/api/ai/templates", headers=h)
    assert r.status_code == 200, r.text
    assert [t["id"] for t in r.json()["templates"]] == ["daily_brief"]


async def test_U08_divisi_rnd(klien, akun, sesi, kepala_admin, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"rnd": ["view"]}, label="TA Divisi")
    h = await sesi(await akun(rid))
    assert await _kode(klien, "GET", "/api/rnd/divisions", h) == 403
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"permissions": {"rnd": ["view", "manage_org"]}})
    assert r.status_code == 200, r.text
    assert await _kode(klien, "GET", "/api/rnd/divisions", h) == 200


async def test_U09_rapor_desainer(klien, akun, sesi, peran_tanpa_acuan):
    h = await sesi(await akun(await peran_tanpa_acuan({"rnd": ["view", "report"]}, label="TA Rapor")))
    assert await _kode(klien, "GET", "/api/rnd/reports/designer-kpi", h) == 200
    assert await _kode(klien, "GET", "/api/rnd/sla/board", h) == 200


async def test_U10_cabut_perangkat(klien, akun, sesi, peran_tanpa_acuan):
    h = await sesi(await akun(await peran_tanpa_acuan({"rfid_device": ["revoke"]}, label="TA Cabut Perangkat")))
    r = await klien.post("/api/handheld/devices/x/revoke", headers=h, json={"reason": "HP hilang di gudang"})
    assert r.status_code == 404, r.text   # lolos gerbang izin; perangkat memang tidak ada
    assert await _kode(klien, "POST", "/api/handheld/devices/x/enable", h) == 403   # butuh `rfid_device.configure`


async def test_U16_setujui_konten(klien, akun, sesi, kepala_admin, peran_tanpa_acuan):
    r = await klien.post("/api/marketing/posts", headers=kepala_admin,
                         json={"title": "Uji PR-T2", "caption": "Koleksi baru minggu ini", "status": "draft",
                               "platforms": ["instagram"]})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    if r.json().get("status") != "draft":
        r = await klien.post(f"/api/marketing/posts/{pid}/transition", headers=kepala_admin, json={"to": "draft"})
        assert r.status_code == 200, r.text
    r = await klien.post(f"/api/marketing/posts/{pid}/transition", headers=kepala_admin, json={"to": "review"})
    assert r.status_code == 200, r.text
    rid = await peran_tanpa_acuan({"marketing": ["view", "update"]}, label="TA Marketing")
    h = await sesi(await akun(rid))
    r = await klien.post(f"/api/marketing/posts/{pid}/transition", headers=h, json={"to": "approved"})
    assert r.status_code == 400 and "menyetujui konten" in r.text, r.text
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin,
                          json={"permissions": {"marketing": ["view", "update", "approve"]}})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/marketing/posts/{pid}/transition", headers=h, json={"to": "approved"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


async def test_U15_require_role_hilang():
    pola = re.compile(r"\brequire_role\(")
    temuan = []
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith(("tests/", "tests_mem/")) or "/tests/" in rel or p.name.startswith("test_"):
            continue
        for i, baris in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            kode = baris.split("#", 1)[0]
            if pola.search(kode) and not kode.lstrip().startswith(("\"", "'", "*", "-")):
                temuan.append(f"{rel}:{i}")
    assert temuan == []
    with pytest.raises(ImportError):
        from dependencies import require_role  # noqa: F401


async def test_U13_pencabutan_hpp_bertahan(klien, db, kepala_admin, sesi):
    # Fixture sisip: satu pesanan berkolom biaya (HPP/margin) di PT seed.
    await db.sales_orders.insert_one({
        "id": "so_uji_prt2", "number": "KSC/SO-UJI-PRT2", "entity_id": "ent_ksc", "status": "confirmed",
        "customer_id": "cus_uji", "customer_name": "Pelanggan Uji", "order_type": "regular",
        "items": [{"product_id": "prd_uji", "quantity": 1, "price": 50000, "unit_cost": 30000,
                   "margin": 20000, "margin_pct": 40.0}],
        "created_at": "2026-11-01T00:00:00+00:00", "updated_at": "2026-11-01T00:00:00+00:00"})
    mgr = await sesi("manager@kainnusantara.id")

    async def _pesanan():
        r = await klien.get("/api/sales-orders", headers=mgr)
        assert r.status_code == 200, r.text
        j = r.json()
        rows = j.get("items", j) if isinstance(j, dict) else j
        return next(o for o in rows if o["id"] == "so_uji_prt2")

    assert (await _pesanan())["items"][0].get("unit_cost") == 30000   # sebelum dicabut: HPP terlihat
    m = (await klien.get("/api/access/roles/manager", headers=kepala_admin)).json()
    perms = {k: list(v) for k, v in m["permissions"].items() if k != "costing"}
    r = await klien.patch("/api/access/roles/manager", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    assert await _kode(klien, "GET", "/api/costing/wac", mgr) == 403
    item = (await _pesanan())["items"][0]
    assert "unit_cost" not in item and "margin" not in item and "margin_pct" not in item
    m = (await klien.get("/api/access/roles/manager", headers=kepala_admin)).json()
    assert "costing" not in m["permissions"]   # pencabutan bertahan setelah start
    r = await klien.post("/api/access/roles/manager/reset", headers=kepala_admin)
    assert r.status_code == 200, r.text


async def test_tabel1_kunci_pengaturan_layar_lama(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    """Dua baris terakhir tabel "Endpoint": pemeriksa yang sama dengan `PUT /api/config/values` (izin kunci)."""
    mk, _ = await _kosong_dan_sopir(akun, sesi, peran_manajer_kosong, peran_sopir)
    # `/api/lots*` dijaga dulu oleh lapisan tengah `field_visibility.lot` (Keadaan sekarang #4) — tetap.
    assert await _kode(klien, "PUT", "/api/lots/settings", mk, {"enforcement_mode": "warn"}) == 403
    r = await klien.put("/api/supplier-contracts/policy", headers=mk, json={"contract_mode": "warn"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == ("Anda belum punya akses untuk mengubah pengaturan ini. Minta Admin menambahkan "
                                  "akses 'Pengaturan'.")
    lot = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan,
                             {"inventory": ["view", "configure"], "field_visibility": ["lot"]}, "TA Lot")
    assert await _kode(klien, "PUT", "/api/lots/settings", lot, {"enforcement_mode": "warn"}) == 200
    mkl = await _tanpa_acuan(akun, sesi, peran_tanpa_acuan, {"makloon": ["view", "configure"]}, "TA Makloon")
    assert await _kode(klien, "PUT", "/api/supplier-contracts/policy", mkl, {"contract_mode": "warn"}) == 200
    assert await _kode(klien, "PUT", "/api/supplier-contracts/policy", lot, {"contract_mode": "warn"}) == 403


async def test_tabel2_contoh_P_saja_ditolak_P_plus_izin_baru_lolos(klien, akun, sesi, kepala_admin, peran_tanpa_acuan):
    """Contoh baris P+N tabel "Gerbang di dalam handler": izin P saja → 403; P + izin pengganti → lolos gerbang
    (404/400 karena dokumen uji tidak ada, bukan 403)."""
    kasus = [
        ({"internal_request": ["view"]}, {"internal_request": ["view", "convert"]},
         "GET", "/api/internal-requests/pin_tidak_ada/sources", None),
        ({"accounting": ["view", "manage"]}, {"accounting": ["view", "manage", "reopen"]},
         "POST", "/api/finance/closing/pc_tidak_ada/reopen", None),
        ({"goods_receipt": ["view", "approve"]}, {"goods_receipt": ["view", "approve", "configure"]},
         "PUT", "/api/goods-receipts/mode", {"entity_id": "ent_ksc", "mode": "legacy",
                                             "reason": "uji pengalihan gerbang nama peran ke izin"}),
    ]
    for i, (p_saja, p_baru, metode, jalur, isi) in enumerate(kasus):
        rid = await peran_tanpa_acuan(p_saja, label=f"TA Tabel2 {i}")
        h = await sesi(await akun(rid))
        assert await _kode(klien, metode, jalur, h, isi) == 403, jalur
        r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"permissions": p_baru})
        assert r.status_code == 200, r.text
        assert await _kode(klien, metode, jalur, h, isi) != 403, jalur
