"""Kas & Bank 3 Tugas 1 — fondasi: akun 1-1105/1-1290/6-9200, jenis kas `kas_kasir`, pengaturan opname, kontrol
`selisih_kas`, bidang rekening `dana_tetap` & `location_id`, jenis kas terkunci.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.1, §5.2 butir 1, §7.

Persiapan (FIXTURE kecuali disebut ALUR):
  * `ent_ksc` TIDAK PERNAH dinyalakan di modul ini (PT mode lama). Rekening dibuat lewat ALUR `POST /api/bank-accounts`,
    kas lewat ALUR `POST /api/cash-transactions`.
  * `ent_kanda` dinyalakan (`cash_account_mode.nyalakan`, FIXTURE) — PT mode akun per rekening.
  * `ent_uji_kb3m` — PT uji dengan pemetaan PT `kas_bank.kas_kasir` → akun PT 1-1106.
  * Lokasi kerja `warehouse_sites` disisip langsung (FIXTURE).

REGRESI (bukti sebelum/sesudah): `BARIS_LAMA` di bawah direkam dari kode SEBELUM Tugas 1 (komit fa711aa) dengan
`KB3_REKAM=<berkas.json>`; uji membandingkan baris jurnal, posisi kas, ringkasan kas, pemilih refund, dan bidang jenis
kas rekening persis sama.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
REPO = Path(__file__).resolve().parents[2]
REKAM = os.environ.get("KB3_REKAM", "")
_rekaman: dict = {}
SIMPAN: dict = {}
LOKASI_A, LOKASI_B = "site_kb3_soreang", "site_kb3_cimahi"


def _baris(je: dict, nomor: str = "") -> list:
    """Baris jurnal ternormalisasi: nomor dokumen kas di keterangan diganti `<NO>`."""
    out = []
    for ln in je["lines"]:
        d = dict(ln)
        if nomor:
            d["description"] = d.get("description", "").replace(nomor, "<NO>")
        out.append(d)
    return out


def _cocok(nama: str, nyata) -> None:
    if REKAM:
        _rekaman[nama] = nyata
        with open(REKAM, "w", encoding="utf-8") as f:
            json.dump(_rekaman, f, ensure_ascii=False, indent=1, sort_keys=True)
        return
    assert nyata == BARIS_LAMA[nama], f"{nama}: {json.dumps(nyata, ensure_ascii=False)}"


def _jenis(rek: dict) -> dict:
    return {k: rek.get(k) for k in ("account_type", "cash_type", "cash_type_source", "opening_balance",
                                    "gl_account_code")}


async def _rekening(klien, h, status: int = 200, **isi) -> dict:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], **isi}
    if body["account_type"] == "cash":
        body.update(bank_name="", payment_method_codes=["cash"])
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == status, r.text
    return r.json()


async def _jurnal_sumber(db, source_type: str, source_id: str) -> dict:
    jes = await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


def _set(je: dict) -> set:
    return {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}


async def _kas_manual(klien, h, status: int = 200, **isi) -> dict:
    r = await klien.post("/api/cash-transactions", headers=h, json=isi)
    assert r.status_code == status, r.text
    return r.json()


@pytest.fixture(scope="module")
async def lama(klien, db, kepala_admin, sesi):
    """ALUR: rekening `ent_ksc` (mode lama) Kas Kecil tunai saldo awal 600.000 + BCA saldo awal 4.000.000, kas keluar
    kecil 120.000 dan kas masuk bank 900.000. `ent_kanda` dinyalakan (FIXTURE) lalu rekening kas kecil 250.000 + bank
    1.500.000 (ALUR)."""
    from services import cash_account_mode as mode
    h = kepala_admin
    tunai = await _rekening(klien, h, name="Kas Kecil KB3 KSC", account_type="cash", entity_id=KSC,
                            opening_balance=600_000)
    bank = await _rekening(klien, h, name="BCA KB3 KSC", account_number="910-1", entity_id=KSC,
                           holder_name="PT Kain Suka Cita", opening_balance=4_000_000)
    keluar = await _kas_manual(klien, h, cash_type="kas_kecil", direction="out", amount=120_000, category="sewa",
                               description="Sewa kios KB3", account_id=tunai["id"], entity_id=KSC)
    masuk = await _kas_manual(klien, h, cash_type="kas_besar", direction="in", amount=900_000, category="modal",
                              description="Setoran modal KB3", account_id=bank["id"], entity_id=KSC)
    await mode.nyalakan(KANDA, "Uji KB3")
    hk = await sesi("admin@kainnusantara.id", entitas=KANDA)
    tunai_k = await _rekening(klien, hk, name="Kas Kecil KB3 Kanda", account_type="cash", entity_id=KANDA,
                              opening_balance=250_000)
    bank_k = await _rekening(klien, hk, name="BCA KB3 Kanda", account_number="920-1", entity_id=KANDA,
                             opening_balance=1_500_000)
    return {"h": h, "hk": hk, "tunai": tunai, "bank": bank, "keluar": keluar, "masuk": masuk,
            "tunai_k": tunai_k, "bank_k": bank_k}


# ═══ Regresi: rekening kas kecil / kas besar dan semua jurnal kasnya sama dengan sebelum Tugas 1 ═══════════════════
async def test_KB3_1_U1a_rekening_dan_jurnal_mode_lama_sama(db, lama):
    _cocok("rekening_lama", {"tunai": _jenis(lama["tunai"]), "bank": _jenis(lama["bank"])})
    _cocok("saldo_awal_tunai", _baris(await _jurnal_sumber(db, "bank_opening_balance", lama["tunai"]["id"])))
    _cocok("saldo_awal_bank", _baris(await _jurnal_sumber(db, "bank_opening_balance", lama["bank"]["id"])))
    k, m = lama["keluar"], lama["masuk"]
    assert (k["cash_type"], k["account_code"], m["cash_type"], m["account_code"]) == (
        "kas_kecil", "1-1110", "kas_besar", "1-1100")
    _cocok("kas_keluar_kecil", _baris(await _jurnal_sumber(db, "cash_transaction", k["id"]), k["number"]))
    _cocok("kas_masuk_bank", _baris(await _jurnal_sumber(db, "cash_transaction", m["id"]), m["number"]))


async def test_KB3_1_U1b_rekening_dan_jurnal_mode_per_rekening_sama(db, lama):
    _cocok("rekening_aktif", {"tunai": _jenis(lama["tunai_k"]), "bank": _jenis(lama["bank_k"])})
    _cocok("saldo_awal_tunai_aktif", _baris(await _jurnal_sumber(db, "bank_opening_balance", lama["tunai_k"]["id"])))
    _cocok("saldo_awal_bank_aktif", _baris(await _jurnal_sumber(db, "bank_opening_balance", lama["bank_k"]["id"])))


async def test_KB3_1_U1c_posisi_ringkasan_dan_pemilih_refund_sama(klien, lama):
    from services import bank_service
    pos = await bank_service.cash_position([KSC])
    _cocok("posisi_kas", {"gl_accounts": pos["gl_accounts"], "gl_total": pos["gl_total"]})
    r = await klien.get("/api/cash-transactions/summary", headers=lama["h"], params={"entity_id": KSC})
    assert r.status_code == 200, r.text
    _cocok("ringkasan_kas", {k: r.json()[k] for k in ("kas_kecil", "kas_besar", "kas_kecil_per_entity")})
    r = await klien.get("/api/gl/cash-accounts", headers=lama["h"])
    assert r.status_code == 200, r.text
    _cocok("pemilih_refund", r.json())


# ═══ Akun bawaan, kunci pemetaan, induk sub-akun, label ═══════════════════════════════════════════════════════════
async def test_KB3_1_U2_akun_bawaan_dan_kunci_pemetaan(db, lama):
    from services import cash_account_mode as mode, cash_ledger, gl_mapping_registry as reg, gl_service as gl
    assert (gl.ACC_KAS_KASIR, gl.ACC_PIUTANG_KURANG_KAS, gl.ACC_SELISIH_KAS) == ("1-1105", "1-1290", "6-9200")
    bagan = {c: (n, t, p, ok) for c, n, t, p, ok in gl.DEFAULT_COA}
    assert bagan["1-1105"] == ("Kas Kasir", "asset", "1-1000", True)
    assert bagan["1-1290"] == ("Piutang Karyawan – Kekurangan Kas", "asset", "1-1000", True)
    assert bagan["6-9200"] == ("Selisih Kas", "expense", "6-0000", True)
    for kode in ("1-1105", "1-1290", "6-9200"):
        assert await db.gl_accounts.find_one({"code": kode, "entity_id": None}), kode
    assert [c for c, *_ in gl.DEFAULT_COA].count("1-1105") == 1
    for key, awal in (("kas_bank.kas_kasir", "1-1105"), ("kas_bank.selisih_kas", "6-9200"),
                      ("kas_bank.piutang_kurang_kas", "1-1290")):
        e = reg.require(key)
        assert (e["default"], e["remap"], e["module"]) == (awal, True, "kas_bank"), key
        assert reg.REMAP_BY_DEFAULT[awal] == key
    assert set(reg.require("kas_bank.selisih_kas")["allowed_types"]) == {"expense", "income"}
    assert mode.INDUK == {"kas_besar": "1-1100", "kas_kecil": "1-1110", "kas_kasir": "1-1105"}
    assert cash_ledger.CASH_TYPE_LABEL["kas_kasir"] == "Kas kasir"
    assert (cash_ledger.cash_type_for("1-1105"), cash_ledger.cash_type_for("1-1110"),
            cash_ledger.cash_type_for("1-1100"), cash_ledger.cash_type_for("")) == (
        "kas_kasir", "kas_kecil", "kas_besar", "kas_besar")
    from services import bank_service as bs
    assert bs.CASH_TYPES == {"kas_kecil", "kas_besar", "kas_kasir"}
    assert bs.account_cash_type({"account_type": "cash", "cash_type": "kas_kasir"}) == "kas_kasir"
    assert bs.account_cash_type({"account_type": "cash"}) == "kas_kecil"
    assert bs.account_cash_type({"account_type": "bank"}) == "kas_besar"
    assert await gl.akun_kas(KSC, "", "kas_kasir") == "1-1105"


# ═══ C1 — rekening kas kasir di PT mode lama ═══════════════════════════════════════════════════════════════════════
async def test_KB3_1_U3_kas_kasir_pt_mode_lama(klien, db, lama):
    from services import bank_service as bs, cash_ledger, gl_service as gl, report_basis as rb
    h = lama["h"]
    kasir = await _rekening(klien, h, name="Kas Kasir Toko KB3", account_type="cash", cash_type="kas_kasir",
                            entity_id=KSC, opening_balance=300_000)
    assert (kasir["cash_type"], kasir.get("gl_account_code") or "") == ("kas_kasir", "")
    assert (kasir["dana_tetap"], kasir["location_id"]) == (0.0, "")
    je = await _jurnal_sumber(db, "bank_opening_balance", kasir["id"])
    assert _set(je) == {("1-1105", 300_000.0, 0.0), ("3-2900", 0.0, 300_000.0)}
    kas = await _kas_manual(klien, h, cash_type="kas_kasir", direction="in", amount=200_000,
                            category="penjualan tunai", description="Tunai toko KB3", account_id=kasir["id"],
                            entity_id=KSC)
    assert (kas["cash_type"], kas["account_code"]) == ("kas_kasir", "1-1105")
    assert ("1-1105", 200_000.0, 0.0) in _set(await _jurnal_sumber(db, "cash_transaction", kas["id"]))
    # Rekening kas kasir tunggal PT dikenali pembantu yang ada; jenis dari rekening, bukan pemanggil.
    assert await bs.sole_account_id(KSC, "kas_kasir") == kasir["id"]
    rek = await cash_ledger.periksa_rekening(KSC, "", "kas_kasir")
    assert (rek["account_id"], rek["cash_type"], rek["account_code"]) == (kasir["id"], "kas_kasir", "1-1105")
    assert await gl.akun_kas(KSC, kasir["id"], "kas_kasir") == "1-1105"
    assert await cash_ledger.jenis_kas_akun(KSC, "1-1105") == "kas_kasir"
    # Pembaca kas ikut kas kasir: kumpulan akun kas, posisi kas, saldo rekening, ringkasan kas.
    assert "1-1105" in await rb.kode_kas(KSC)
    pos = await bs.cash_position([KSC])
    assert {ln["code"]: ln["balance"] for ln in pos["gl_accounts"]}["1-1105"] == 500_000.0
    saldo = {a["id"]: a["balance"] for a in await bs.list_accounts(entity_id=KSC)}
    assert saldo[kasir["id"]] == 500_000.0
    r = await klien.get("/api/cash-transactions/summary", headers=h, params={"entity_id": KSC})
    assert r.status_code == 200, r.text
    assert (r.json()["kas_kasir"]["balance"], r.json()["counts"]["kas_kasir"]) == (500_000.0, 1)
    r = await klien.get("/api/cash-transactions", headers=h, params={"entity_id": KSC, "cash_type": "kas_kasir"})
    assert [t["id"] for t in r.json()] == [kas["id"]]
    # Jurnal induk yang memakai akun kas kecil tidak boleh mendarat di rekening kas kasir (buku kas ≠ buku besar).
    with pytest.raises(cash_ledger.CashRejected) as e:
        await cash_ledger.create_cash(entity_id=KSC, direction="out", amount=10_000, ref_type="sales_return",
                                      ref_id="rt_kb3_x", account_id=kasir["id"], cash_type="kas_kecil",
                                      journal_by_parent="je_kb3_x", actor="uji")
    pt = await cash_ledger._nama_pt(KSC)
    assert str(e.value.detail) == f"Rekening Kas Kasir Toko KB3 bukan rekening Kas Kecil {pt}.", e.value.detail
    SIMPAN["kasir_ksc"] = kasir


async def test_KB3_1_U3b_pindah_dana_dari_kas_kasir(db, lama):
    """Saldo kas kasir dipindah lewat Pindah Dana (cara memindah saldo rekening, spesifikasi §5.1): kas kirim di
    rekening kasir berakun 1-1105; buku kas rekening = saldo akun 1-1105 PT itu."""
    from services import bank_service as bs, fund_transfer_service as fts
    from pembantu import saldo_akun
    kasir = SIMPAN["kasir_ksc"]
    doc = await fts.buat({"entity_id": KSC, "rekening_asal_id": kasir["id"], "rekening_tujuan_id": lama["bank"]["id"],
                          "nominal": 100_000, "catatan": "setor uang kasir"}, AKTOR_UJI)
    assert doc["status"] == "selesai", doc
    kas = {t["seq"]: t async for t in db.cash_transactions.find({"ref_type": "fund_transfer", "ref_id": doc["id"]},
                                                                  {"_id": 0})}
    assert (kas["kirim"]["cash_type"], kas["kirim"]["account_code"]) == ("kas_kasir", "1-1105")
    je = await _jurnal_sumber(db, "cash_transaction", kas["kirim"]["id"])
    assert ("1-1105", 0.0, 100_000.0) in _set(je)
    buku = {a["id"]: a["balance"] for a in await bs.list_accounts(entity_id=KSC)}
    assert buku[kasir["id"]] == await saldo_akun("1-1105", KSC) == 400_000.0


async def test_KB3_1_U4_kas_kasir_dengan_pemetaan_pt(db):
    from schemas_finance import GLAccountCreate
    from services import cash_ledger, gl_mapping_service as glm, gl_service as gl, report_basis as rb
    pt = await pt_uji("KB3M")
    await gl.create_account(GLAccountCreate(code="1-1106", name="Kas Kasir KB3M", type="asset",
                                            parent_code="1-1000"), entity_id=pt)
    await glm.set_mapping("kas_bank.kas_kasir", pt, "1-1106", "uji KB3 pemetaan PT", AKTOR_UJI)
    await db.bank_accounts.insert_one({"id": "rek_kb3m", "name": "Kasir KB3M", "entity_id": pt,
                                       "account_type": "cash", "cash_type": "kas_kasir", "is_active": True,
                                       "opening_balance": 0.0, "created_at": now_iso()})
    kas = await cash_ledger.create_cash(entity_id=pt, direction="in", amount=75_000, ref_type="manual",
                                        ref_id="kb3_u4", account_id="rek_kb3m", category="penjualan tunai",
                                        description="Tunai KB3M", actor="uji")
    je = await _jurnal_sumber(db, "cash_transaction", kas["id"])
    kasln = next(ln for ln in je["lines"] if ln["debit"])
    assert (kasln["account_code"], kasln.get("mapping_key")) == ("1-1106", "kas_bank.kas_kasir")
    assert {"1-1105", "1-1106"} <= await rb.kode_kas(pt)


async def test_KB3_1_U13_pemilih_bayar_ongkir_tanpa_kas_kasir(db, lama):
    """Perbaikan putaran 1 (tinjauan T1, Important) — pemilih akun bayar ongkir retur (`pay_accounts`, berawalan 1-11)
    tidak menawarkan akun kas kasir: jurnal ongkir menulis akun itu langsung tanpa dokumen kas. PT tanpa kas kasir →
    daftar PERSIS sama dengan sebelum Tugas 1 (direkam dari fa711aa); PT dengan pemetaan `kas_bank.kas_kasir` → templat
    1-1105 dan akun pemetaannya (1-1106, U4) tidak ditawarkan dan ditolak `save`."""
    from services import gl_service as gl, return_logistics_service as rl
    daftar = await rl.pay_accounts(await pt_uji("KB3N"))
    _cocok("bayar_ongkir_pt_tanpa_kasir", daftar)
    assert await gl.akun_kas_kasir() == {"1-1105"}
    pm = await pt_uji("KB3M")
    assert await gl.akun_kas_kasir(pm) == {"1-1105", "1-1106"}
    assert await rl.pay_accounts(pm) == daftar
    for kode in ("1-1105", "1-1106"):
        ret = {"id": f"sr_kb3_ong_{kode}", "number": f"RJ/KB3/ONG/{kode}", "entity_id": pm, "customer_name": "Toko KB3"}
        with pytest.raises(ValueError) as e:
            await rl.save(ret, [{"type": "customer_return", "mode": "third_party", "bearer": "company",
                                 "amount": 40_000, "pay_account_code": kode}], AKTOR_UJI, True)
        assert str(e.value) == f"Akun pembayaran {kode} bukan akun kas/bank/hutang yang aktif", str(e.value)
        assert not await db.journal_entries.find_one({"source_type": rl.SOURCE, "ref.return_id": ret["id"]})


# ═══ C1 — rekening kas kasir di PT mode akun per rekening ══════════════════════════════════════════════════════════
async def test_KB3_1_U5_kas_kasir_pt_aktif_ke_subakun(klien, db, lama):
    from services import bank_service as bs
    hk = lama["hk"]
    kasir = await _rekening(klien, hk, name="Kas Kasir KB3 Kanda", account_type="cash", cash_type="kas_kasir",
                            entity_id=KANDA, opening_balance=400_000)
    assert kasir["gl_account_code"] == "1-1105-01"
    akun = await db.gl_accounts.find_one({"code": "1-1105-01", "entity_id": KANDA}, {"_id": 0})
    assert (akun["parent_code"], akun["bank_account_id"], akun["is_cash"]) == ("1-1105", kasir["id"], True)
    je = await _jurnal_sumber(db, "bank_opening_balance", kasir["id"])
    assert _set(je) == {("1-1105-01", 400_000.0, 0.0), ("3-2900", 0.0, 400_000.0)}
    kas = await _kas_manual(klien, hk, cash_type="kas_kasir", direction="out", amount=50_000, category="operasional",
                            description="Ongkos KB3 Kanda", account_id=kasir["id"], entity_id=KANDA)
    assert (kas["cash_type"], kas["account_code"]) == ("kas_kasir", "1-1105-01")
    pos = {ln["code"]: ln["balance"] for ln in (await bs.cash_position([KANDA]))["gl_accounts"]}
    buku = {a["id"]: a["balance"] for a in await bs.list_accounts(entity_id=KANDA)}
    assert pos["1-1105-01"] == buku[kasir["id"]] == 350_000.0
    assert "1-1105" not in pos   # mode per rekening: kas kasir tidak menyentuh akun induk
    SIMPAN["kasir_kanda"] = kasir


# ═══ Jenis kas: isian sah, terkunci sesudah punya kas ══════════════════════════════════════════════════════════════
async def test_KB3_1_U6_jenis_kas_tidak_sah_ditolak(klien, db, lama):
    h = lama["h"]
    n0 = await db.bank_accounts.count_documents({})
    r = await _rekening(klien, h, 400, name="BCA Kasir Tolak", account_number="930-1", cash_type="kas_kasir",
                        entity_id=KSC)
    assert r["detail"] == "Kas kasir hanya untuk rekening kas tunai, bukan rekening bank.", r
    r = await _rekening(klien, h, 400, name="Kas Ngawur", account_type="cash", cash_type="kas_toko", entity_id=KSC)
    assert r["detail"] == "Jenis kas harus kas kecil, kas kasir, atau kas besar.", r
    assert await db.bank_accounts.count_documents({}) == n0
    r = await klien.patch(f"/api/bank-accounts/{lama['bank']['id']}", headers=h, json={"cash_type": "kas_kasir"})
    assert (r.status_code, r.json()["detail"]) == (400, "Kas kasir hanya untuk rekening kas tunai, bukan rekening "
                                                         "bank."), r.text


async def test_KB3_1_U7_jenis_kas_terkunci_bila_punya_kas(klien, db, lama):
    h = lama["h"]
    # Rekening tanpa kas dan tanpa saldo awal (PT mode lama) → jenis kas boleh diganti.
    baru = await _rekening(klien, h, name="Kas Cadangan KB3", account_type="cash", entity_id=KSC)
    r = await klien.patch(f"/api/bank-accounts/{baru['id']}", headers=h, json={"cash_type": "kas_kasir"})
    assert r.status_code == 200, r.text
    assert (await db.bank_accounts.find_one({"id": baru["id"]}))["cash_type"] == "kas_kasir"
    ch = await db.bank_account_changes.find_one({"account_id": baru["id"], "action": "ubah"}, {"_id": 0})
    assert ch["changes"] == [{"field": "cash_type", "from": "kas_kecil", "to": "kas_kasir"}]
    # Rekening yang sudah punya transaksi kas → 400 berkalimat, tidak berubah.
    tunai = lama["tunai"]
    r = await klien.patch(f"/api/bank-accounts/{tunai['id']}", headers=h, json={"cash_type": "kas_kasir"})
    assert (r.status_code, r.json()["detail"]) == (400, (
        "Jenis kas rekening Kas Kecil KB3 KSC tidak bisa diubah karena rekening ini sudah punya transaksi kas. "
        "Pindahkan saldonya lewat Pindah Dana ke rekening baru dengan jenis kas yang benar.")), r.text
    assert (await db.bank_accounts.find_one({"id": tunai["id"]}))["cash_type"] == "kas_kecil"
    # Saldo awal saja (sudah terjurnal) juga mengunci.
    awal = await _rekening(klien, h, name="Kas Awal KB3", account_type="cash", entity_id=KSC, opening_balance=10_000)
    r = await klien.patch(f"/api/bank-accounts/{awal['id']}", headers=h, json={"cash_type": "kas_kasir"})
    assert r.status_code == 400 and "sudah punya transaksi kas" in r.json()["detail"], r.text
    # PT mode per rekening: akun buku besar rekening dibuat menurut jenis kasnya → terkunci walau belum ada kas.
    hk = lama["hk"]
    kosong = await _rekening(klien, hk, name="Kas Kecil Kosong KB3", account_type="cash", entity_id=KANDA)
    r = await klien.patch(f"/api/bank-accounts/{kosong['id']}", headers=hk, json={"cash_type": "kas_kasir"})
    assert (r.status_code, r.json()["detail"]) == (400, (
        f"Jenis kas rekening Kas Kecil Kosong KB3 tidak bisa diubah karena akun buku besarnya "
        f"({kosong['gl_account_code']}) dibuat untuk jenis kas itu. Nonaktifkan rekening ini lalu buat rekening baru "
        f"dengan jenis kas yang benar.")), r.text
    # Daftar rekening memberi tahu layar mana yang terkunci.
    daftar = {a["id"]: a for a in (await klien.get("/api/bank-accounts", headers=h,
                                                   params={"entity_id": KSC})).json()}
    assert (daftar[tunai["id"]]["jenis_kas_terkunci"], daftar[awal["id"]]["jenis_kas_terkunci"],
            daftar[baru["id"]]["jenis_kas_terkunci"]) == (True, True, False)


# ═══ C2 — dana tetap & lokasi di rekening ══════════════════════════════════════════════════════════════════════════
async def test_KB3_1_U8_dana_tetap_dan_lokasi_saat_dibuat(klien, db, lama):
    from services.cash_ledger import _nama_pt
    await db.warehouse_sites.insert_many([{"id": LOKASI_A, "name": "Soreang KB3", "created_at": now_iso()},
                                          {"id": LOKASI_B, "name": "Cimahi KB3", "created_at": now_iso()}])
    h = lama["h"]
    kecil = await _rekening(klien, h, name="Kas Kecil Soreang KB3", account_type="cash", cash_type="kas_kecil",
                            entity_id=KSC, dana_tetap=2_000_000, location_id=LOKASI_A)
    simpan = await db.bank_accounts.find_one({"id": kecil["id"]}, {"_id": 0})
    assert (simpan["dana_tetap"], simpan["location_id"]) == (2_000_000.0, LOKASI_A)
    daftar = {a["id"]: a for a in (await klien.get("/api/bank-accounts", headers=h,
                                                   params={"entity_id": KSC})).json()}
    assert (daftar[kecil["id"]]["dana_tetap"], daftar[kecil["id"]]["location_id"],
            daftar[kecil["id"]]["location_name"]) == (2_000_000.0, LOKASI_A, "Soreang KB3")
    assert (daftar[lama["tunai"]["id"]]["dana_tetap"], daftar[lama["tunai"]["id"]]["location_id"]) == (0.0, "")
    # Rekening LAMA (FIXTURE: dokumen tanpa bidang baru) terbaca dana tetap 0, tanpa lokasi; dokumennya tidak ditulis.
    await db.bank_accounts.insert_one({"id": "rek_kb3_lama", "name": "Kas Lama KB3", "entity_id": KSC,
                                       "account_type": "cash", "cash_type": "kas_kecil", "is_active": True,
                                       "opening_balance": 0.0, "created_at": now_iso()})
    daftar = {a["id"]: a for a in (await klien.get("/api/bank-accounts", headers=h,
                                                   params={"entity_id": KSC})).json()}
    assert (daftar["rek_kb3_lama"]["dana_tetap"], daftar["rek_kb3_lama"]["location_id"],
            daftar["rek_kb3_lama"]["location_name"]) == (0.0, "", "")
    simpan_lama = await db.bank_accounts.find_one({"id": "rek_kb3_lama"}, {"_id": 0})
    assert not {"dana_tetap", "location_id"} & set(simpan_lama), simpan_lama
    # Kas kasir boleh berlokasi; lokasi yang sama boleh untuk kas kasir.
    kasir = await _rekening(klien, h, name="Kas Kasir Soreang KB3", account_type="cash", cash_type="kas_kasir",
                            entity_id=KSC, location_id=LOKASI_A)
    assert kasir["location_id"] == LOKASI_A
    n0 = await db.bank_accounts.count_documents({})
    r = await klien.post("/api/bank-accounts", headers=h, json={
        "name": "Kas Minus", "account_type": "cash", "payment_method_codes": ["cash"], "entity_id": KSC,
        "dana_tetap": -1})
    assert r.status_code == 422, r.text
    r = await _rekening(klien, h, 400, name="Kasir Berdana", account_type="cash", cash_type="kas_kasir",
                        entity_id=KSC, dana_tetap=500_000)
    assert r["detail"] == "Dana tetap hanya untuk rekening kas kecil.", r
    r = await _rekening(klien, h, 400, name="BCA Berlokasi", account_number="940-1", entity_id=KSC,
                        location_id=LOKASI_A)
    assert r["detail"] == "Lokasi hanya untuk rekening kas kasir dan kas kecil.", r
    r = await _rekening(klien, h, 400, name="Kas Lokasi Hilang", account_type="cash", entity_id=KSC,
                        location_id="site_tidak_ada")
    assert r["detail"] == "Lokasi kerja yang dipilih tidak ditemukan.", r
    r = await _rekening(klien, h, 400, name="Kas Kecil Soreang Dua", account_type="cash", entity_id=KSC,
                        location_id=LOKASI_A)
    assert r["detail"] == (f"Lokasi Soreang KB3 sudah punya rekening kas kecil Kas Kecil Soreang KB3 di "
                           f"{await _nama_pt(KSC)}. Satu lokasi hanya untuk satu rekening kas kecil."), r
    assert await db.bank_accounts.count_documents({}) == n0
    # PT lain boleh punya kas kecil di lokasi yang sama.
    lain = await _rekening(klien, lama["hk"], name="Kas Kecil Soreang Kanda", account_type="cash", entity_id=KANDA,
                           location_id=LOKASI_A)
    assert lain["location_id"] == LOKASI_A
    SIMPAN["kecil_soreang"] = kecil


async def test_KB3_1_U9_ubah_dana_tetap_dan_lokasi(klien, db, lama):
    h = lama["h"]
    kecil = SIMPAN["kecil_soreang"]
    r = await klien.patch(f"/api/bank-accounts/{kecil['id']}", headers=h,
                          json={"dana_tetap": 3_000_000, "location_id": LOKASI_B})
    assert r.status_code == 200, r.text
    assert (r.json()["dana_tetap"], r.json()["location_id"]) == (3_000_000.0, LOKASI_B)
    ch = await db.bank_account_changes.find_one({"account_id": kecil["id"], "action": "ubah"}, {"_id": 0},
                                                sort=[("created_at", -1)])
    assert ch["changes"] == [{"field": "dana_tetap", "from": 2_000_000.0, "to": 3_000_000.0},
                             {"field": "location_id", "from": LOKASI_A, "to": LOKASI_B}]
    r = await klien.patch(f"/api/bank-accounts/{kecil['id']}", headers=h, json={"dana_tetap": -5})
    assert r.status_code == 422, r.text
    r = await klien.patch(f"/api/bank-accounts/{SIMPAN['kasir_ksc']['id']}", headers=h, json={"dana_tetap": 100})
    assert (r.status_code, r.json()["detail"]) == (400, "Dana tetap hanya untuk rekening kas kecil."), r.text
    r = await klien.patch(f"/api/bank-accounts/{lama['bank']['id']}", headers=h, json={"location_id": LOKASI_B})
    assert (r.status_code, r.json()["detail"]) == (400, "Lokasi hanya untuk rekening kas kasir dan kas kecil."), r.text
    # Dana tetap di rekening lama (tanpa bidang) lewat ubah rekening: hanya rekening itu yang tertulis.
    r = await klien.patch("/api/bank-accounts/rek_kb3_lama", headers=h, json={"dana_tetap": 1_000_000})
    assert r.status_code == 200 and r.json()["dana_tetap"] == 1_000_000.0, r.text
    assert (await db.bank_accounts.find_one({"id": "rek_kb3_lama"}))["dana_tetap"] == 1_000_000.0
    assert (await db.bank_accounts.find_one({"id": lama["tunai"]["id"]}))["dana_tetap"] == 0.0


async def test_KB3_1_U10_dana_tetap_ikut_kontrol_dua_orang(klien, db, akun, sesi, lama):
    from services import config_resolver as resolver
    kecil = SIMPAN["kecil_soreang"]
    mgr = await akun("manager", entitas=(KSC,))
    h_mgr = await sesi(mgr)
    kosong = await _rekening(klien, lama["h"], name="Kas Ganti Jenis KB3", account_type="cash", entity_id=KSC)
    await resolver.set_value("kontrol.ubah_rekening.min_orang", "2", scope_type="entity", scope_id=KSC, actor="uji",
                             reason="uji KB3")
    try:
        r = await klien.patch(f"/api/bank-accounts/{kecil['id']}", headers=h_mgr, json={"dana_tetap": 2_500_000})
        assert r.status_code == 202, r.text
        ch = r.json()["change"]
        assert ch["changes"] == [{"field": "dana_tetap", "from": 3_000_000.0, "to": 2_500_000.0}]
        assert (await db.bank_accounts.find_one({"id": kecil["id"]}))["dana_tetap"] == 3_000_000.0
        r = await klien.get("/api/bank-account-changes", headers=lama["h"], params={"status": "menunggu"})
        row = next(x for x in r.json()["items"] if x["id"] == ch["id"])
        assert row["label_changes"][0]["label"] == "Dana tetap"
        r = await klien.post(f"/api/bank-account-changes/{ch['id']}/decision", headers=lama["h"],
                             json={"decision": "approve", "note": "sesuai memo"})
        assert r.status_code == 200, r.text
        assert (await db.bank_accounts.find_one({"id": kecil["id"]}))["dana_tetap"] == 2_500_000.0
        # Jenis kas juga field peka: diajukan, diterapkan hanya bila rekening belum punya kas saat disetujui.
        r = await klien.patch(f"/api/bank-accounts/{kosong['id']}", headers=h_mgr, json={"cash_type": "kas_kasir"})
        assert r.status_code == 202, r.text
        cid = r.json()["change"]["id"]
        await db.cash_transactions.insert_one({"id": "cash_kb3_sela", "entity_id": KSC, "account_id": kosong["id"],
                                               "cash_type": "kas_kecil", "direction": "in", "amount": 1.0,
                                               "status": "posted", "created_at": now_iso()})
        r = await klien.post(f"/api/bank-account-changes/{cid}/decision", headers=lama["h"],
                             json={"decision": "approve", "note": "uji"})
        assert r.status_code == 400 and "sudah punya transaksi kas" in r.json()["detail"], r.text
        assert (await db.bank_accounts.find_one({"id": kosong["id"]}))["cash_type"] == "kas_kecil"
        assert (await db.bank_account_changes.find_one({"id": cid}))["status"] == "menunggu"
    finally:
        await resolver.set_value("kontrol.ubah_rekening.min_orang", "1", scope_type="entity", scope_id=KSC,
                                 actor="uji", reason="pulihkan uji KB3")


async def test_KB3_1_U10b_penyetuju_rekening_baru_melihat_jenis_kas(klien, db, akun, sesi, lama):
    """Tinjauan akhir Important 4 — rekening baru yang menunggu orang kedua memuat JENIS KAS di daftar perubahan:
    menyetujui satu kas kasir memindahkan bawaan penerimaan tunai PT (R4) dan jenisnya terkunci begitu ada kas, jadi
    penyetuju harus melihatnya. Rekening tunai tanpa jenis = kas kecil (jenis yang akan berlaku); rekening bank tanpa
    jenis tidak memuat baris jenis kas (seperti dulu)."""
    from services import config_resolver as resolver
    mgr = await akun("manager", entitas=(KSC,))
    h_mgr = await sesi(mgr)
    await resolver.set_value("kontrol.ubah_rekening.min_orang", "2", scope_type="entity", scope_id=KSC, actor="uji",
                             reason="uji KB3 jenis kas rekening baru")
    n0 = await db.bank_accounts.count_documents({})
    diajukan = []
    try:
        r = await _rekening(klien, h_mgr, 202, name="Kas Kasir Diajukan KB3", account_type="cash",
                            cash_type="kas_kasir", entity_id=KSC, location_id=LOKASI_A)
        ch = r["change"]
        diajukan.append(ch["id"])
        bidang = {c["field"]: c for c in ch["changes"]}
        assert bidang["cash_type"] == {"field": "cash_type", "from": None, "to": "kas_kasir"}, ch["changes"]
        assert bidang["location_id"]["to"] == LOKASI_A
        r = await klien.get("/api/bank-account-changes", headers=lama["h"], params={"status": "menunggu"})
        row = next(x for x in r.json()["items"] if x["id"] == ch["id"])
        assert {"field": "cash_type", "from": None, "to": "kas_kasir", "label": "Jenis kas"} in row["label_changes"]
        # Tunai tanpa jenis → jenis yang akan berlaku (kas kecil) tetap terlihat; dana tetap ikut.
        r = await _rekening(klien, h_mgr, 202, name="Kas Kecil Diajukan KB3", account_type="cash", entity_id=KSC,
                            dana_tetap=750_000)
        diajukan.append(r["change"]["id"])
        bidang = {c["field"]: c["to"] for c in r["change"]["changes"]}
        assert (bidang["cash_type"], bidang["dana_tetap"]) == ("kas_kecil", 750_000.0), r["change"]["changes"]
        # Rekening bank tanpa jenis kas: tanpa baris jenis kas (perilaku lama).
        r = await _rekening(klien, h_mgr, 202, name="BCA Diajukan KB3", account_number="950-1", entity_id=KSC,
                            holder_name="PT Kain Suka Cita")
        diajukan.append(r["change"]["id"])
        assert "cash_type" not in {c["field"] for c in r["change"]["changes"]}, r["change"]["changes"]
        assert await db.bank_accounts.count_documents({}) == n0   # belum ada rekening yang dibuat
    finally:
        for cid in diajukan:
            await klien.post(f"/api/bank-account-changes/{cid}/decision", headers=lama["h"],
                             json={"decision": "reject", "note": "uji KB3 selesai"})
        await resolver.set_value("kontrol.ubah_rekening.min_orang", "1", scope_type="entity", scope_id=KSC,
                                 actor="uji", reason="pulihkan uji KB3")


# ═══ Pengaturan & kontrol ══════════════════════════════════════════════════════════════════════════════════════════
async def test_KB3_1_U11_pengaturan_opname_dan_kontrol_selisih(db, lama):
    import config_registry as registry
    from services import bank_service as bs, config_resolver as resolver
    from config_catalog_kontrol import ADMIN_TETAP_DUA_ORANG_AWAL, AKSI_BY_ID
    for key, awal in (("kas.opname_kasir_hari", 1), ("kas.opname_kas_kecil_hari", 7),
                      ("kas.opname_kas_besar_hari", 7)):
        e = registry.require(key)
        assert (e["default"], e["type"], e["unit"], e["scopes"], e["group"], e["section"]) == (
            awal, "duration", "hari", ["global", "entity"], "bank-kasus", "opname-kas"), key
        assert "services/bank_service.py:hari_opname" in e["consumers"]
    assert bs.KUNCI_OPNAME_HARI == {"kas_kasir": "kas.opname_kasir_hari", "kas_kecil": "kas.opname_kas_kecil_hari",
                                    "kas_besar": "kas.opname_kas_besar_hari"}
    assert [await bs.hari_opname(KSC, ct) for ct in ("kas_kasir", "kas_kecil", "kas_besar")] == [1, 7, 7]
    await resolver.set_value("kas.opname_kas_kecil_hari", 3, scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KB3")
    assert (await bs.hari_opname(KANDA, "kas_kecil"), await bs.hari_opname(KSC, "kas_kecil")) == (3, 7)
    a = AKSI_BY_ID["selisih_kas"]
    assert (a["awal"], a["punya_nominal"], a["kelompok"]) == ("2", False, "B")
    e = registry.require("kontrol.selisih_kas.min_orang")
    assert (e["default"], e["section"]) == ("2", "dua-orang-kas")
    assert registry.get("kontrol.selisih_kas.batas_nominal") is None
    assert "selisih_kas" in ADMIN_TETAP_DUA_ORANG_AWAL
    assert "selisih_kas" in registry.require("kontrol.admin_tetap_dua_orang")["default"]


# ═══ Penjaga statis INV-CASH-02 ikut menjaga 1-1105 ════════════════════════════════════════════════════════════════
def test_KB3_1_U12_penjaga_akun_kas_menjaga_kas_kasir():
    sys.path.insert(0, str(REPO / "scripts" / "guardrails"))
    import verify_akun_kas_satu_pintu as g
    assert {"1-1100", "1-1110", "1-1105"} <= g.KODE_KAS
    assert "ACC_KAS_KASIR" in g.NAMA_KAS and "kas_bank.kas_kasir" in g.KUNCI_KAS
    bersih = {"services/gl_service.py": g._GL}
    assert g._mini({**bersih, "services/a.py": "def baris(n):\n    return [{'account_code': '1-1105', 'debit': n}]\n"}
                   ).violations
    assert g._mini({**bersih, "services/a.py": "from services import gl_service as gl\n"
                    "def baris(n):\n    return [{'account_code': gl.ACC_KAS_KASIR, 'debit': n}]\n"}).violations
    assert g._mini({**bersih, "services/a.py": "async def akun(gl, e):\n    return await gl.account_for("
                    "'kas_bank.kas_kasir', e)\n"}).violations
    skrip = REPO / "scripts/guardrails/verify_akun_kas_satu_pintu.py"
    swa = subprocess.run([sys.executable, str(skrip), "--self-test"], capture_output=True, text=True, cwd=REPO)
    assert swa.returncode == 0 and "1-1105" in swa.stdout, swa.stdout + swa.stderr
    nyata = subprocess.run([sys.executable, str(skrip)], capture_output=True, text=True, cwd=REPO)
    assert nyata.returncode == 0 and "0 pelanggaran" in nyata.stdout, nyata.stdout + nyata.stderr


#: Direkam dari kode SEBELUM Tugas 1 (fa711aa) dengan `KB3_REKAM` — jangan disunting tangan.
BARIS_LAMA: dict = {'kas_keluar_kecil': [{'account_code': '6-2000',
                                         'account_name': 'Beban Sewa',
                                         'credit': 0.0,
                                         'debit': 120000.0,
                                         'description': '<NO> · Sewa kios KB3'},
                                        {'account_code': '1-1110',
                                         'account_name': 'Kas Kecil',
                                         'credit': 120000.0,
                                         'debit': 0.0,
                                         'description': '<NO> · Sewa kios KB3'}],
                   'kas_masuk_bank': [{'account_code': '1-1100',
                                       'account_name': 'Kas Besar / Bank',
                                       'credit': 0.0,
                                       'debit': 900000.0,
                                       'description': '<NO> · Setoran modal KB3'},
                                      {'account_code': '3-1000',
                                       'account_name': 'Modal Disetor',
                                       'credit': 900000.0,
                                       'debit': 0.0,
                                       'description': '<NO> · Setoran modal KB3'}],
                   'pemilih_refund': [{'code': '1-1100', 'name': 'Kas Besar / Bank'},
                                      {'code': '1-1110', 'name': 'Kas Kecil'},
                                      {'code': '1-1150', 'name': 'Kas & Bank Transit (Dana Dalam Perjalanan)'}],
                   'posisi_kas': {'gl_accounts': [{'balance': 104900000.0, 'code': '1-1100',
                                                   'name': 'Kas Besar / Bank'},
                                                  {'balance': 8230000.0, 'code': '1-1110', 'name': 'Kas Kecil'}],
                                  'gl_total': 113130000.0},
                   'rekening_aktif': {'bank': {'account_type': 'bank',
                                               'cash_type': 'kas_besar',
                                               'cash_type_source': 'explicit',
                                               'gl_account_code': '1-1100-01',
                                               'opening_balance': 1500000.0},
                                      'tunai': {'account_type': 'cash',
                                                'cash_type': 'kas_kecil',
                                                'cash_type_source': 'explicit',
                                                'gl_account_code': '1-1110-01',
                                                'opening_balance': 250000.0}},
                   'rekening_lama': {'bank': {'account_type': 'bank',
                                              'cash_type': 'kas_besar',
                                              'cash_type_source': 'explicit',
                                              'gl_account_code': None,
                                              'opening_balance': 4000000.0},
                                     'tunai': {'account_type': 'cash',
                                               'cash_type': 'kas_kecil',
                                               'cash_type_source': 'explicit',
                                               'gl_account_code': None,
                                               'opening_balance': 600000.0}},
                   'ringkasan_kas': {'kas_besar': {'balance': 104900000.0,
                                                   'count': 2,
                                                   'in': 100900000.0,
                                                   'opening': 4000000.0,
                                                   'out': 0},
                                     'kas_kecil': {'balance': 8230000.0,
                                                   'count': 4,
                                                   'in': 10000000.0,
                                                   'opening': 600000.0,
                                                   'out': 2370000.0},
                                     'kas_kecil_per_entity': {'ent_ksc': {'balance': 8230000.0, 'in': 10000000.0,
                                                                          'out': 2370000.0}}},
                   'saldo_awal_bank': [{'account_code': '1-1100',
                                        'account_name': 'Kas Besar / Bank',
                                        'credit': 0.0,
                                        'debit': 4000000.0,
                                        'description': 'Saldo awal BCA KB3 KSC'},
                                       {'account_code': '3-2900',
                                        'account_name': 'Ekuitas Saldo Awal',
                                        'credit': 4000000.0,
                                        'debit': 0.0,
                                        'description': 'Saldo awal BCA KB3 KSC'}],
                   'saldo_awal_bank_aktif': [{'account_code': '1-1100-01',
                                              'account_name': 'BCA KB3 Kanda',
                                              'credit': 0.0,
                                              'debit': 1500000.0,
                                              'description': 'Saldo awal BCA KB3 Kanda'},
                                             {'account_code': '3-2900',
                                              'account_name': 'Ekuitas Saldo Awal',
                                              'credit': 1500000.0,
                                              'debit': 0.0,
                                              'description': 'Saldo awal BCA KB3 Kanda'}],
                   'saldo_awal_tunai': [{'account_code': '1-1110',
                                         'account_name': 'Kas Kecil',
                                         'credit': 0.0,
                                         'debit': 600000.0,
                                         'description': 'Saldo awal Kas Kecil KB3 KSC'},
                                        {'account_code': '3-2900',
                                         'account_name': 'Ekuitas Saldo Awal',
                                         'credit': 600000.0,
                                         'debit': 0.0,
                                         'description': 'Saldo awal Kas Kecil KB3 KSC'}],
                   'saldo_awal_tunai_aktif': [{'account_code': '1-1110-01',
                                               'account_name': 'Kas Kecil KB3 Kanda',
                                               'credit': 0.0,
                                               'debit': 250000.0,
                                               'description': 'Saldo awal Kas Kecil KB3 Kanda'},
                                              {'account_code': '3-2900',
                                               'account_name': 'Ekuitas Saldo Awal',
                                               'credit': 250000.0,
                                               'debit': 0.0,
                                               'description': 'Saldo awal Kas Kecil KB3 Kanda'}]}


#: Perbaikan putaran 1 — `return_logistics_service.pay_accounts` PT uji tanpa kas kasir, direkam dari fa711aa.
BARIS_LAMA["bayar_ongkir_pt_tanpa_kasir"] = [
    {'code': '1-1100', 'kind': 'kas_bank', 'name': 'Kas Besar / Bank'},
    {'code': '1-1110', 'kind': 'kas_bank', 'name': 'Kas Kecil'},
    {'code': '1-1150', 'kind': 'kas_bank', 'name': 'Kas & Bank Transit (Dana Dalam Perjalanan)'},
    {'code': '2-1100', 'kind': 'hutang', 'name': 'Hutang Usaha'},
    {'code': '2-1150', 'kind': 'hutang', 'name': 'Hutang Belum Ditagih (GR/IR)'},
    {'code': '2-1200', 'kind': 'hutang', 'name': 'PPN Keluaran'},
    {'code': '2-1250', 'kind': 'hutang', 'name': 'Utang Antar-Perusahaan (IC-AP)'},
    {'code': '2-1300', 'kind': 'hutang', 'name': 'Hutang Pajak Lainnya'},
    {'code': '2-1400', 'kind': 'hutang', 'name': 'Uang Muka Pelanggan'},
    {'code': '2-1450', 'kind': 'hutang', 'name': 'Saldo Kredit Pelanggan (Store Credit)'},
    {'code': '2-1500', 'kind': 'hutang', 'name': 'Hutang Insentif Penjualan'},
    {'code': '2-1600', 'kind': 'hutang', 'name': 'Hutang Gaji'},
    {'code': '2-1650', 'kind': 'hutang', 'name': 'Hutang Reimburse Karyawan'},
    {'code': '2-1700', 'kind': 'hutang', 'name': 'Hutang BPJS'},
    {'code': '2-1800', 'kind': 'hutang', 'name': 'Hutang PPh 21'},
    {'code': '2-1900', 'kind': 'hutang', 'name': 'Kewajiban Lancar Lainnya'},
    {'code': '2-1950', 'kind': 'hutang', 'name': 'Titipan Dana Belum Teridentifikasi'},
]
