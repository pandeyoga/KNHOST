"""CR-T3 serah-terima (a) — izin kredit bernominal, berlingkup, bermasa berlaku, diputus menurut jenjang dan kontrol dua
orang; sembilan kunci (U4–U6, U15, U16; `docs/blueprint/unit/CR-T3.md`).

Alur lewat API: pengajuan (`POST /api/customers/{id}/credit-override`), keputusan (`POST /api/credit-overrides/{id}/decision`),
pengaturan (`services.config_resolver`), peran uji baku (`POST /api/access/roles`). Fixture SISIP: G1 (`pembantu_crt3`),
`valid_until` digeser ke kemarin (U5 — waktu tidak bisa dimundurkan lewat API).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pembantu_crt3 import JUTA, KANDA, KSC, atur, cabut, g1, kode

pytestmark = pytest.mark.anyio

KUNCI_CRT3 = ("ar.periksa_kredit_pesanan_dibuat", "ar.periksa_kredit_pesanan_diubah", "ar.periksa_kredit_lepas_gudang",
              "ar.periksa_kredit_surat_jalan", "ar.eksposur_pesanan_belum_kirim", "ar.eksposur_giro_belum_cair",
              "ar.eksposur_titipan_mengurangi", "ar.izin_kredit_masa_berlaku_hari", "finance.tahan_kirim_tunai")
SIMPAN: dict = {}


@pytest.fixture(scope="module")
async def orang(akun, sesi):
    sls = await akun("sales", entitas=(KANDA, KSC))
    mgr = await akun("manager", entitas=(KANDA, KSC))
    mgr2 = await akun("manager", entitas=(KANDA, KSC))
    return {"sls": sls, "mgr": mgr, "h_sls": await sesi(sls, entitas=KANDA), "h_mgr": await sesi(mgr, entitas=KANDA),
            "h_mgr2": await sesi(mgr2, entitas=KANDA)}


async def _aju(klien, h, cid, jumlah, *, scope="pelanggan", alasan="cr_riwayat_baik", **lain):
    return await klien.post(f"/api/customers/{cid}/credit-override", headers=h,
                            json={"customer_id": cid, "amount": jumlah, "scope": scope, "reason_code": alasan,
                                  "reason": "Pelanggan lama, bayar lancar", **lain})


async def _putus(klien, h, oid, keputusan="approve"):
    return await klien.post(f"/api/credit-overrides/{oid}/decision", headers=h,
                            json={"decision": keputusan, "reason": "uji CR-T3"})


# ── U4 — izin pelanggan Rp 3 jt, masa berlaku 3 hari, dipakai satu pesanan ──────────────────────────────────────────
async def test_CRT3_U4_izin_pelanggan_bermasa_berlaku_dipakai(klien, db, orang):
    from services import credit_gate as cg
    f = await g1(db, sales_id=orang["sls"]["id"])
    await atur("ar.izin_kredit_masa_berlaku_hari", 3, KANDA)
    try:
        r = await _aju(klien, orang["h_sls"], f["cid"], 3 * JUTA)
        assert r.status_code == 200, r.text
        izin = r.json()
        assert (izin["status"], izin["scope"], izin["amount"], izin["remaining_amount"], izin["entity_id"]) == \
            ("pending", "pelanggan", 3 * JUTA, 3 * JUTA, KANDA)
        assert izin["reason_code"] == "cr_riwayat_baik" and izin["reason_label"] == "Riwayat bayar baik"
        r = await _putus(klien, orang["h_mgr"], izin["id"])
        assert r.status_code == 200, r.text
    finally:
        await cabut("ar.izin_kredit_masa_berlaku_hari", KANDA)
    d = r.json()
    putus = datetime.fromisoformat(d["decided_at"])
    assert datetime.fromisoformat(d["valid_until"]) == putus + timedelta(days=3)
    assert d["status"] == "approved" and d["remaining_amount"] == 3 * JUTA
    # pesanan Rp 3.000.000: 7.500.000 + 3.000.000 = 10.500.000 > 10.000.000 → tahan; izin bersisa 3 jt ≥ 3 jt → lolos
    h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="pesanan_dibuat", order_amount=3 * JUTA,
                          term_code="NET30")
    assert h["raw_result"] == "tahan" and h["result"] == "lolos" and h["override"]["id"] == izin["id"]
    assert await cg.use_override(izin["id"], "so_crt3_u4", 3 * JUTA) is True
    sesudah = await db.credit_overrides.find_one({"id": izin["id"]})
    assert sesudah["remaining_amount"] == 0 and len(sesudah["used_by"]) == 1
    assert sesudah["used_by"][0]["order_id"] == "so_crt3_u4" and sesudah["used_by"][0]["amount"] == 3 * JUTA
    assert await cg.use_override(izin["id"], "so_crt3_u4", 3 * JUTA) is True        # idempoten per pesanan
    assert await cg.use_override(izin["id"], "so_crt3_u4b", 1) is False             # sisa 0
    SIMPAN["u4"] = {"cid": f["cid"], "izin": izin["id"]}


# ── U5 — izin lewat `valid_until` → pesanan tetap tahan ─────────────────────────────────────────────────────────────
async def test_CRT3_U5_izin_kedaluwarsa_tidak_melepas(klien, db, orang):
    from services import credit_gate as cg
    f = await g1(db, sales_id=orang["sls"]["id"])
    r = await _aju(klien, orang["h_sls"], f["cid"], 3 * JUTA)
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    assert (await _putus(klien, orang["h_mgr"], oid)).status_code == 200
    kemarin = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await db.credit_overrides.update_one({"id": oid}, {"$set": {"valid_until": kemarin}})   # FIXTURE
    h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="pesanan_dibuat", order_amount=3 * JUTA,
                          term_code="NET30")
    assert h["result"] == "tahan" and h["override"] is None
    assert await cg.use_override(oid, "so_crt3_u5", 3 * JUTA) is False
    rows = (await klien.get("/api/credit-overrides", headers=orang["h_mgr"], params={"customer_id": f["cid"]})).json()
    assert [(x["id"], x["expired"], x["usable"]) for x in rows] == [(oid, True, False)]
    assert (await klien.get("/api/credit-overrides", headers=orang["h_mgr"],
                            params={"customer_id": f["cid"], "valid": "1"})).json() == []


# ── U6 — nominal 0 → 400; kontrol dua orang = 2 → pengaju memutus sendiri 403 ────────────────────────────────────────
async def test_CRT3_U6_nominal_nol_dan_dua_orang(klien, db, orang):
    f = await g1(db, sales_id=orang["sls"]["id"])
    n = await db.credit_overrides.count_documents({})
    r = await _aju(klien, orang["h_sls"], f["cid"], 0)
    assert (r.status_code, r.json()["detail"]) == (400, "Nominal izin wajib lebih dari 0."), r.text
    assert await db.credit_overrides.count_documents({}) == n
    # Menyimpang (laporan): aksi kontrol izin kredit = `lewat_batas_kredit` (KF-T6), berlabel "Izin kredit"
    await atur("kontrol.lewat_batas_kredit.min_orang", "2", KANDA)
    try:
        r = await _aju(klien, orang["h_mgr"], f["cid"], 1 * JUTA)
        assert r.status_code == 200, r.text
        oid = r.json()["id"]
        r = await _putus(klien, orang["h_mgr"], oid)
        assert r.status_code == 403, r.text
        assert r.json()["detail"].startswith("Izin kredit harus diputuskan orang lain")
        assert (await db.credit_overrides.find_one({"id": oid}))["status"] == "pending"
        assert (await _putus(klien, orang["h_mgr2"], oid)).status_code == 200
    finally:
        await cabut("kontrol.lewat_batas_kredit.min_orang", KANDA)
    # sudah diputus → 409
    r = await _putus(klien, orang["h_mgr2"], oid, "reject")
    assert (r.status_code, r.json()["detail"]) == (409, "Izin kredit ini sudah diputus atau kedaluwarsa.")


async def test_CRT3_U6b_isian_pengajuan(klien, db, orang):
    """Lingkup pesanan wajib berpesanan; alasan wajib dari master; "Lainnya" wajib catatan."""
    f = await g1(db, sales_id=orang["sls"]["id"])
    r = await _aju(klien, orang["h_sls"], f["cid"], JUTA, scope="pesanan")
    assert (r.status_code, r.json()["detail"]) == (400, "Izin lingkup pesanan wajib menyebut pesanannya.")
    r = await _aju(klien, orang["h_sls"], f["cid"], JUTA, alasan="")
    assert (r.status_code, r.json()["detail"]) == (400, "Pilih alasan izin kredit.")
    r = await klien.post(f"/api/customers/{f['cid']}/credit-override", headers=orang["h_sls"],
                         json={"amount": JUTA, "reason_code": "cr_lain", "reason": ""})
    assert r.status_code == 400 and "Lainnya" in r.json()["detail"]
    r = await _aju(klien, orang["h_sls"], f["cid"], JUTA, scope="pesanan", order_id=f["o2"])
    assert r.status_code == 200, r.text
    assert (r.json()["scope"], r.json()["order_id"]) == ("pesanan", f["o2"])
    pil = (await klien.get("/api/credit-override-reasons", headers=orang["h_sls"])).json()
    assert [p["code"] for p in pil] == sorted(["cr_riwayat_baik", "cr_jaminan", "cr_lain"],
                                              key=lambda c: {"cr_riwayat_baik": "Riwayat bayar baik",
                                                             "cr_jaminan": "Ada jaminan atau giro mundur",
                                                             "cr_lain": "Lainnya (jelaskan di catatan)"}[c])


async def test_CRT3_izin_pesanan_hanya_pesanannya(db, klien, orang):
    """Lingkup pesanan: hanya melepas pesanan ber-`order_id` sama (pesanan baru tidak)."""
    from services import credit_gate as cg
    f = await g1(db, sales_id=orang["sls"]["id"], terbuka=3 * JUTA)
    r = await _aju(klien, orang["h_sls"], f["cid"], 3 * JUTA, scope="pesanan", order_id=f["o2"])
    assert r.status_code == 200, r.text
    assert (await _putus(klien, orang["h_mgr"], r.json()["id"])).status_code == 200
    # pesanan baru 2 jt: 6 + 3 − 0,5 + 2 = 10,5 jt > 10 jt → tahan; izin lingkup pesanan O2 tidak berlaku
    h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="pesanan_dibuat", order_amount=2 * JUTA)
    assert h["result"] == "tahan" and h["override"] is None
    # pesanan O2 sendiri (periksa ulang): 6 + 3 − 0,5 = 8,5 jt; tanpa O2 = 5,5 jt → tidak tahan → peringatan
    h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="periksa_ulang", order_id=f["o2"])
    assert h["result"] == "peringatan" and h["exposure"]["this_order"] == 3 * JUTA, h["reasons"]


# ── U15 — izin dari peran: Tanpa Acuan + approve → 200; Manajer Kosong 403; Sopir 403 ───────────────────────────────
async def test_CRT3_U15_izin_dari_peran(klien, db, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir,
                                        orang):
    f = await g1(db, sales_id=orang["sls"]["id"])
    ids = []
    for _ in range(3):
        r = await _aju(klien, orang["h_sls"], f["cid"], JUTA)
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    tanpa = await akun(await peran_tanpa_acuan({"credit_override": ["approve"]}), entitas=(KANDA,))
    kosong = await akun(await peran_manajer_kosong(), entitas=(KANDA,))
    sopir = await akun(peran_sopir, entitas=(KANDA,))
    r = await _putus(klien, await sesi(tanpa, entitas=KANDA), ids[0])
    assert r.status_code == 200, r.text
    r = await _putus(klien, await sesi(kosong, entitas=KANDA), ids[1])
    assert r.status_code == 403, r.text
    r = await _putus(klien, await sesi(sopir, entitas=KANDA), ids[2])
    assert r.status_code == 403, r.text
    # melihat dan mengajukan: izin sendiri (Z1); tanpa izin → 403 berkalimat (Z6)
    lihat = await akun(await peran_tanpa_acuan({"credit_override": ["view"]}), entitas=(KANDA,))
    h_lihat = await sesi(lihat, entitas=KANDA)
    r = await klien.get("/api/credit-overrides", headers=h_lihat)
    assert r.status_code == 200 and {x["id"] for x in r.json()} >= set(ids), r.text
    r = await klien.get("/api/credit-overrides", headers=await sesi(kosong, entitas=KANDA))
    assert r.status_code == 403 and "Pengawasan Tim Sales & Kredit" in r.json()["detail"], r.text
    aju = await akun(await peran_tanpa_acuan({"credit_override": ["create"], "customer": ["view"]}), entitas=(KANDA,))
    r = await _aju(klien, await sesi(aju, entitas=KANDA), f["cid"], JUTA)
    assert r.status_code == 200, r.text
    r = await _aju(klien, await sesi(sopir, entitas=KANDA), f["cid"], JUTA)
    assert r.status_code == 403, r.text


async def test_CRT3_izin_bawaan_setara():
    """`02` §3.2 — izin bawaan setara akses hari ini: view = pemegang `customer.view`, create = pemegang `order.create`."""
    import permissions_config as pc
    for peran, izin in pc.DEFAULT_PERMISSIONS.items():
        co = set(izin.get("credit_override") or [])
        assert ("view" in co) == ("view" in (izin.get("customer") or [])), peran
        assert ("create" in co) == ("create" in (izin.get("order") or [])), peran
    # K-FIN-01 (pemilik 17 Nov): Finance memegang semua izin bawaan Manajer, termasuk memutus izin kredit.
    assert {p for p, i in pc.DEFAULT_PERMISSIONS.items() if "approve" in (i.get("credit_override") or [])} == \
        {"admin", "manager", "finance"}


# ── U16 — putaran `t1_config` sembilan kunci ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kunci", KUNCI_CRT3)
async def test_CRT3_U16_putaran_kunci(klien, kepala_admin, kunci):
    from test_KFT8_putaran_pengaturan import putaran
    gagal = await putaran(klien, kepala_admin, kunci)
    assert not gagal, "\n".join(gagal)


async def test_CRT3_kunci_terdaftar_sesuai_spesifikasi():
    import config_registry as registry
    for k in KUNCI_CRT3:
        e = registry.require(k)
        assert e["group"] == "pembayaran-pelanggan" and tuple(e["scopes"]) == ("global", "entity"), k
        assert e["risk"] == "high" and e["requires_reason"] is True, k
        assert tuple(e["permission"]) == ("credit_profile", "approve"), k
    bawaan = {k: registry.require(k)["default"] for k in KUNCI_CRT3}
    assert bawaan == {"ar.periksa_kredit_pesanan_dibuat": True, "ar.periksa_kredit_pesanan_diubah": False,
                      "ar.periksa_kredit_lepas_gudang": False, "ar.periksa_kredit_surat_jalan": False,
                      "ar.eksposur_pesanan_belum_kirim": True, "ar.eksposur_giro_belum_cair": True,
                      "ar.eksposur_titipan_mengurangi": True, "ar.izin_kredit_masa_berlaku_hari": 0,
                      "finance.tahan_kirim_tunai": False}
    e = registry.require("ar.izin_kredit_masa_berlaku_hari")
    assert (e["min"], e["max"], e["unit"]) == (0, 90, "hari")


async def test_CRT3_dua_pesanan_bersamaan_satu_izin(db):
    """Padanan lapis B U17 (database tiruan: tidak membuktikan perilaku bersamaan MongoDB asli — `00` §9)."""
    import asyncio
    from services import credit_gate as cg
    from pembantu_crt3 import uid
    oid = uid("cro")
    await db.credit_overrides.insert_one({"id": oid, "customer_id": "cus_x", "entity_id": KANDA, "status": "approved",
                                          "scope": "pelanggan", "amount": 3 * JUTA, "remaining_amount": 3 * JUTA,
                                          "valid_until": "", "used_by": []})
    hasil = await asyncio.gather(cg.use_override(oid, "so_a", 3 * JUTA), cg.use_override(oid, "so_b", 3 * JUTA))
    assert sorted(hasil) == [False, True]
    d = await db.credit_overrides.find_one({"id": oid})
    assert d["remaining_amount"] == 0 and len(d["used_by"]) == 1
    # pesanan yang gagal dibuat sesudah izin dipakai → pemakaian dikembalikan
    await cg.release_use(oid, d["used_by"][0]["order_id"])
    d = await db.credit_overrides.find_one({"id": oid})
    assert d["remaining_amount"] == 3 * JUTA and d["used_by"] == []


async def test_CRT3_izin_lama_nol_dianggap_kedaluwarsa(db):
    """Izin lama bernominal 0 yang belum dipakai (dulu "tanpa batas") tidak melepas tahan."""
    from services import credit_gate as cg
    f = await g1(db)
    from pembantu_crt3 import uid
    await db.credit_overrides.insert_one({"id": uid("cro"), "customer_id": f["cid"], "entity_id": KANDA,
                                          "status": "approved", "amount": 0, "decided_at": "2026-10-01"})
    h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="pesanan_dibuat", order_amount=3 * JUTA)
    assert h["result"] == "tahan" and h["override"] is None and kode(h) == ["LEWAT_PLAFON"]
