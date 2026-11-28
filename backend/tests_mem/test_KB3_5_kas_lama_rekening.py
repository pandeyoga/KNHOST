"""Kas & Bank 3 — perbaikan temuan tangkapan A (ketetapan pengendali R7): kas lama TANPA rekening tidak boleh bergeser
saat rekening kedua sejenis lahir.

Masalah (data acuan PT KSC): kas lama tanpa `account_id` dihitung ke rekening yang menjadi SATU-SATUNYA rekening aktif PT
untuk jenis kasnya (`bank_service._txns_for` + `sole_account_id`). Begitu rekening kas kecil kedua dibuat, kartu Kas Toko
turun Rp 7.750.000 (akun 1-1110 tetap), opname memotret saldo tergeser, usulan isi ulang dana tetap naik.

Perbaikan: sebelum rekening kedua sejenis aktif (dibuat langsung / lewat persetujuan dua orang, diaktifkan kembali, jenis
kasnya diubah, jenis kas diisi dari riwayat), kas lama itu DITETAPKAN ke rekening tunggal yang lama
(`bank_service.tetapkan_kas_tanpa_rekening`) — tanpa jurnal. Keadaan ambigu yang sudah terlanjur (≥ 2 rekening + kas tanpa
rekening) menahan opname & isi ulang dana tetap rekening jenis itu dengan 409 berkalimat.

Persiapan (FIXTURE kecuali disebut ALUR): PT uji per uji (`pt_uji`), pengguna Admin/Manajer PT itu (`akun` + `sesi`).
Rekening lewat ALUR `POST /api/bank-accounts`; kas ber-rekening lewat pintu kas `cash_ledger.create_cash` (ALUR layanan);
kas LAMA tanpa rekening disisip langsung + jurnalnya lewat `gl_service.post_cash_durable` (FIXTURE, pola KB1-3). Opname,
dana tetap, batal kas lewat ALUR HTTP.

Hitung tangan (= data acuan KSC): Kas Toko saldo awal 25.000.000 + kas ber-rekening +400.000 + kas lama tanpa rekening
(+10.000.000 −1.500.000 −750.000 = bersih 7.750.000) = 33.150.000. Dana tetap Kas Toko 40.000.000 → usulan isi ulang
40.000.000 − 33.150.000 = 6.850.000. BCA saldo awal 100.000.000 + kas lama kas besar tanpa rekening +100.000.000 =
200.000.000 (BCA rekening kas besar tunggal).
"""
from __future__ import annotations

import asyncio
import itertools
import uuid

import pytest

from core_utils import now_iso
from pembantu import pt_uji, saldo_akun

pytestmark = pytest.mark.anyio

KK = "kas_kecil"
_urut = itertools.count(1)
KAS_TOKO, BERSIH, AWAL_TOKO, DANA = 33_150_000.0, 7_750_000.0, 25_000_000, 40_000_000


def _pesan_ditetapkan(n: int, bersih: str, rekening: str) -> str:
    return f"{n} kas lama tanpa rekening (bersih {bersih}) ditetapkan ke {rekening} supaya saldonya tidak bergeser."


def _pesan_belum_pasti(jenis: str, pt: str, n: int, bersih: str, m: int) -> str:
    return (f"Saldo buku rekening {jenis} {pt} belum pasti: {n} kas lama tanpa rekening (bersih {bersih}) tidak ikut "
            f"rekening mana pun karena PT punya {m} rekening {jenis}. Minta admin menetapkan rekening kas lama itu dulu.")


async def _pt(akun, sesi, awal: str) -> dict:
    """PT uji + Admin & Manajer PT itu (FIXTURE)."""
    from services.entity_lifecycle_service import invalidate_status_cache
    kode = f"{awal}{next(_urut)}"
    eid = await pt_uji(kode)
    invalidate_status_cache()
    adm = await akun("admin", entitas=(eid,))
    mgr = await akun("manager", entitas=(eid,))
    return {"id": eid, "kode": kode, "nama": f"Uji {kode.upper()}", "adm": adm, "h": await sesi(adm, entitas=eid),
            "mgr": mgr, "hm": await sesi(mgr, entitas=eid), "rek": {}}


async def _rekening(klien, h, eid: str, nama: str, jenis_kas: str = KK, status: int = 200, **isi) -> dict:
    """ALUR `POST /api/bank-accounts`. `jenis_kas="bank"` → rekening bank (kas besar)."""
    if jenis_kas == "bank":
        body = {"name": nama, "account_type": "bank", "bank_name": "BCA", "account_number": uuid.uuid4().hex[:8],
                "entity_id": eid, **isi}
    else:
        body = {"name": nama, "account_type": "cash", "cash_type": jenis_kas, "entity_id": eid, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == status, r.text
    return r.json()


async def _kas_berekening(eid: str, rekening: str, arah: str, nominal: float) -> dict:
    """ALUR layanan — pintu kas tunggal, rujukan manual."""
    from services import cash_ledger
    return await cash_ledger.create_cash(entity_id=eid, direction=arah, amount=nominal, ref_type="manual",
                                         ref_id=f"man_{uuid.uuid4().hex[:10]}", account_id=rekening, category="modal",
                                         description="Uji KB3-5 kas ber-rekening", actor="Uji")


_ABSEN = object()


async def _kas_lama(db, eid: str, jenis_kas: str, arah: str, nominal: float, *, akun=_ABSEN, status: str = "posted",
                    jurnal: bool = True) -> dict:
    """FIXTURE — kas LAMA tanpa rekening (sebelum PK-20). `akun` = isi `account_id` (tanpa kunci / None / ""); `jurnal`
    = jurnal kasnya diterbitkan sekarang (akun jenis kas lama) lewat `post_cash_durable`."""
    from services import gl_service as gl
    kid = f"cash_lama_{uuid.uuid4().hex[:10]}"
    t = {"id": kid, "number": f"CASH-L{uuid.uuid4().hex[:6]}", "entity_id": eid, "cash_type": jenis_kas,
         "direction": arah, "amount": nominal, "category": "lain", "description": "Kas lama KB3-5", "ref_type": "manual",
         "ref_id": f"lama_{kid}", "status": status, "gl_status": "pending", "txn_date": now_iso(),
         "created_at": now_iso(), "updated_at": now_iso()}
    if akun is not _ABSEN:
        t["account_id"] = akun
    await db.cash_transactions.insert_one(dict(t))
    if jurnal:
        await gl.post_cash_durable(t)
    return await db.cash_transactions.find_one({"id": kid}, {"_id": 0})


async def _kas_lama_toko(db, eid: str) -> list:
    """Tiga kas lama kas kecil tanpa rekening (data acuan CASH-00002..4): tanpa kunci, None, "" → bersih 7.750.000."""
    return [await _kas_lama(db, eid, KK, "in", 10_000_000),
            await _kas_lama(db, eid, KK, "out", 1_500_000, akun=None),
            await _kas_lama(db, eid, KK, "out", 750_000, akun="")]


async def _acuan(klien, db, akun, sesi, awal: str, *, kas_besar: bool = True) -> dict:
    """PT seperti data acuan KSC: BCA (saldo awal 100 jt), Kas Toko kas kecil (saldo awal 25 jt, dana tetap 40 jt,
    +400.000 ber-rekening), 3 kas lama kas kecil tanpa rekening; kendali: kas lama kas kecil BATAL tanpa rekening, kas
    lama kas besar tanpa rekening +100 jt (`kas_besar`)."""
    pt = await _pt(akun, sesi, awal)
    eid = pt["id"]
    pt["rek"]["BCA"] = (await _rekening(klien, pt["h"], eid, f"BCA {pt['kode']}", "bank",
                                        opening_balance=100_000_000))["id"]
    pt["rek"]["TOKO"] = (await _rekening(klien, pt["h"], eid, f"Kas Toko {pt['kode']}", opening_balance=AWAL_TOKO,
                                         dana_tetap=DANA))["id"]
    await _kas_berekening(eid, pt["rek"]["TOKO"], "in", 400_000)
    pt["lama"] = await _kas_lama_toko(db, eid)
    pt["batal"] = await _kas_lama(db, eid, KK, "in", 999_000, status="void", jurnal=False)
    if kas_besar:
        pt["lama_kb"] = await _kas_lama(db, eid, "kas_besar", "in", 100_000_000)
    return pt


async def _saldo(klien, pt: dict) -> dict:
    r = await klien.get("/api/bank-accounts", headers=pt["h"], params={"entity_id": pt["id"]})
    assert r.status_code == 200, r.text
    return {a["id"]: a["balance"] for a in r.json()}


async def _kas(db, kid: str) -> dict:
    return await db.cash_transactions.find_one({"id": kid}, {"_id": 0})


def _tanpa_penetapan(t: dict) -> dict:
    return {k: v for k, v in t.items() if k not in ("account_id", "rekening_ditetapkan", "updated_at")}


async def _buku_besar(db, eid: str) -> tuple:
    """Potret buku besar PT: saldo akun kas & jumlah + isi jurnal (tanpa `_id`)."""
    jes = await db.journal_entries.find({"entity_id": eid}, {"_id": 0}).sort("id", 1).to_list(None)
    return (await saldo_akun("1-1110", eid), await saldo_akun("1-1100", eid), len(jes), jes)


def _tertukar(je: dict) -> list:
    return sorted((ln["account_code"], ln["credit"], ln["debit"]) for ln in je["lines"])


def _baris(je: dict) -> list:
    return sorted((ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"])


async def _jurnal(db, source_type: str, kid: str) -> dict:
    jes = await db.journal_entries.find({"source_type": source_type, "source_id": kid, "status": {"$ne": "void"}},
                                        {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


async def _batal_kas(klien, pt: dict, kid: str) -> None:
    r = await klien.post(f"/api/cash-transactions/{kid}/void", headers=pt["h"], json={"reason": "uji KB3-5 batal"})
    assert r.status_code == 200, r.text


async def _dua_orang(eid: str, nilai: str) -> None:
    from services import config_resolver as resolver
    await resolver.set_value("kontrol.ubah_rekening.min_orang", nilai, scope_type="entity", scope_id=eid,
                             actor="uji", reason="uji KB3-5")


async def _periksa_ditetapkan(db, pt: dict, sebelum: list, *, alasan: str) -> None:
    """Tiga kas lama → `account_id` Kas Toko + jejak; nominal/tanggal/status/kode akun tidak berubah."""
    for lama in sebelum:
        t = await _kas(db, lama["id"])
        assert t["account_id"] == pt["rek"]["TOKO"], t
        j = t["rekening_ditetapkan"]
        assert (j["oleh"], j["oleh_id"], j["alasan"]) == (pt["adm"]["name"], pt["adm"]["id"], alasan), j
        assert j["pada"]
        assert _tanpa_penetapan(t) == _tanpa_penetapan(lama)


# ═══ U1 — rekening kas kecil kedua dibuat langsung ═══════════════════════════════════════════════════════════════════
async def test_KB3_5_U1_rekening_kedua_dibuat_langsung_kas_lama_tetap(klien, db, akun, sesi):
    from services import bank_service as bs
    pt = await _acuan(klien, db, akun, sesi, "KB35L")
    eid, toko = pt["id"], pt["rek"]["TOKO"]
    lain = await _pt(akun, sesi, "KB35X")                                  # PT lain: kas lama kas kecil tanpa rekening
    await _rekening(klien, lain["h"], lain["id"], f"Kas Toko {lain['kode']}")
    kas_lain = await _kas_lama(db, lain["id"], KK, "in", 5_000_000)
    sebelum = await _saldo(klien, pt)
    assert (sebelum[toko], sebelum[pt["rek"]["BCA"]]) == (KAS_TOKO, 200_000_000.0)
    buku = await _buku_besar(db, eid)
    r = await klien.get("/api/bank-accounts/position", headers=pt["h"], params={"entity_id": eid})
    assert r.json()["unlinked"]["count"] == 0, r.text

    baru = await _rekening(klien, pt["h"], eid, f"Kas Kecil Gudang {pt['kode']}")
    nama_toko = f"Kas Toko {pt['kode']}"
    assert baru["kas_lama_ditetapkan"] == {
        "jumlah": 3, "bersih": BERSIH, "rekening_id": toko, "rekening_nama": nama_toko,
        "pesan": _pesan_ditetapkan(3, "Rp 7.750.000", nama_toko)}, baru
    assert "kas_lama_tertinggal" not in baru
    sesudah = await _saldo(klien, pt)
    assert (sesudah[toko], sesudah[baru["id"]], sesudah[pt["rek"]["BCA"]]) == (KAS_TOKO, 0.0, 200_000_000.0)
    await _periksa_ditetapkan(db, pt, pt["lama"], alasan=(
        f"Rekening kas kecil kedua Kas Kecil Gudang {pt['kode']} dibuat — kas lama tanpa rekening tetap di {nama_toko}"))
    # Kendali: kas batal, kas jenis lain, kas PT lain tidak tersentuh.
    assert await _kas(db, pt["batal"]["id"]) == pt["batal"]
    assert await _kas(db, pt["lama_kb"]["id"]) == pt["lama_kb"]
    assert await _kas(db, kas_lain["id"]) == kas_lain
    # Tanpa jurnal: buku besar persis sama; posisi tetap tanpa kas tak tertaut.
    assert await _buku_besar(db, eid) == buku
    r = await klien.get("/api/bank-accounts/position", headers=pt["h"], params={"entity_id": eid})
    assert r.json()["unlinked"]["count"] == 0, r.text
    jejak = await db.audit_logs.find_one({"action": "kas_lama_rekening_ditetapkan", "entity_id": toko}, {"_id": 0})
    assert jejak and jejak["after"]["jumlah"] == 3 and sorted(jejak["after"]["kas_ids"]) == sorted(
        t["id"] for t in pt["lama"]), jejak
    # Idempoten: rekening ketiga / panggilan ulang tidak menulis apa pun.
    ketiga = await _rekening(klien, pt["h"], eid, f"Kas Kecil Cimahi {pt['kode']}")
    assert "kas_lama_ditetapkan" not in ketiga
    ulang = await bs.tetapkan_kas_tanpa_rekening(eid, KK, pt["adm"], rekening_baru="uji")
    assert (ulang["jumlah"], ulang["bersih"]) == (0, 0.0)
    assert (await _saldo(klien, pt))[toko] == KAS_TOKO


# ═══ U2 — lewat persetujuan dua orang: rekening baru diajukan Manajer, disetujui Admin ══════════════════════════════
async def test_KB3_5_U2_rekening_kedua_lewat_persetujuan_dua_orang(klien, db, akun, sesi):
    pt = await _acuan(klien, db, akun, sesi, "KB35P")
    eid, toko = pt["id"], pt["rek"]["TOKO"]
    await _dua_orang(eid, "2")
    aju = await _rekening(klien, pt["hm"], eid, f"Kas Kecil Gudang {pt['kode']}", status=202)
    # Diajukan saja: belum ada yang ditetapkan, saldo tidak berubah.
    for lama in pt["lama"]:
        assert not (await _kas(db, lama["id"])).get("account_id")
    assert (await _saldo(klien, pt))[toko] == KAS_TOKO
    r = await klien.post(f"/api/bank-account-changes/{aju['change']['id']}/decision", headers=pt["h"],
                         json={"decision": "approve", "note": "uji KB3-5"})
    assert r.status_code == 200, r.text
    j = r.json()
    nama_toko = f"Kas Toko {pt['kode']}"
    harap = {"jumlah": 3, "bersih": BERSIH, "rekening_id": toko, "rekening_nama": nama_toko,
             "pesan": _pesan_ditetapkan(3, "Rp 7.750.000", nama_toko)}
    assert j["kas_lama_ditetapkan"] == harap and j["account"]["kas_lama_ditetapkan"] == harap, j
    sesudah = await _saldo(klien, pt)
    assert (sesudah[toko], sesudah[j["account"]["id"]]) == (KAS_TOKO, 0.0)
    await _periksa_ditetapkan(db, pt, pt["lama"], alasan=(
        f"Rekening kas kecil kedua Kas Kecil Gudang {pt['kode']} dibuat — kas lama tanpa rekening tetap di {nama_toko}"))
    await _dua_orang(eid, "1")


async def _acuan_cadangan(klien, db, akun, sesi, awal: str) -> dict:
    """Rekening kas kecil Cadangan dibuat lalu DINONAKTIFKAN sebelum Kas Toko dibuat (Kas Toko jadi tunggal), lalu kas
    lama toko (FIXTURE)."""
    pt = await _pt(akun, sesi, awal)
    eid = pt["id"]
    cad = await _rekening(klien, pt["h"], eid, f"Kas Kecil Cadangan {pt['kode']}")
    r = await klien.patch(f"/api/bank-accounts/{cad['id']}", headers=pt["h"], json={"is_active": False})
    assert r.status_code == 200 and "kas_lama_ditetapkan" not in r.json(), r.text
    pt["rek"]["CAD"] = cad["id"]
    pt["rek"]["TOKO"] = (await _rekening(klien, pt["h"], eid, f"Kas Toko {pt['kode']}", opening_balance=AWAL_TOKO))["id"]
    await _kas_berekening(eid, pt["rek"]["TOKO"], "in", 400_000)
    pt["lama"] = await _kas_lama_toko(db, eid)
    assert (await _saldo(klien, pt))[pt["rek"]["TOKO"]] == KAS_TOKO
    return pt


# ═══ U3 — rekening kas kecil diaktifkan kembali (langsung, lalu lewat persetujuan) ═══════════════════════════════════
async def test_KB3_5_U3_rekening_diaktifkan_kembali(klien, db, akun, sesi):
    pt = await _acuan_cadangan(klien, db, akun, sesi, "KB35A")
    toko, cad = pt["rek"]["TOKO"], pt["rek"]["CAD"]
    nama_toko = f"Kas Toko {pt['kode']}"
    r = await klien.patch(f"/api/bank-accounts/{cad}", headers=pt["h"], json={"is_active": True})
    assert r.status_code == 200, r.text
    assert r.json()["kas_lama_ditetapkan"] == {
        "jumlah": 3, "bersih": BERSIH, "rekening_id": toko, "rekening_nama": nama_toko,
        "pesan": _pesan_ditetapkan(3, "Rp 7.750.000", nama_toko)}, r.text
    sesudah = await _saldo(klien, pt)
    assert (sesudah[toko], sesudah[cad]) == (KAS_TOKO, 0.0)
    await _periksa_ditetapkan(db, pt, pt["lama"], alasan=(
        f"Rekening kas kecil kedua Kas Kecil Cadangan {pt['kode']} diaktifkan kembali — kas lama tanpa rekening tetap "
        f"di {nama_toko}"))


async def test_KB3_5_U3b_diaktifkan_kembali_lewat_persetujuan(klien, db, akun, sesi):
    pt = await _acuan_cadangan(klien, db, akun, sesi, "KB35B")
    eid, toko, cad = pt["id"], pt["rek"]["TOKO"], pt["rek"]["CAD"]
    await _dua_orang(eid, "2")
    r = await klien.patch(f"/api/bank-accounts/{cad}", headers=pt["hm"], json={"is_active": True})
    assert r.status_code == 202, r.text
    assert not (await _kas(db, pt["lama"][0]["id"])).get("account_id")
    r = await klien.post(f"/api/bank-account-changes/{r.json()['change']['id']}/decision", headers=pt["h"],
                         json={"decision": "approve", "note": "uji KB3-5"})
    assert r.status_code == 200, r.text
    assert r.json()["kas_lama_ditetapkan"]["jumlah"] == 3 and r.json()["kas_lama_ditetapkan"]["rekening_id"] == toko
    sesudah = await _saldo(klien, pt)
    assert (sesudah[toko], sesudah[cad]) == (KAS_TOKO, 0.0)
    for lama in pt["lama"]:
        assert (await _kas(db, lama["id"]))["account_id"] == toko
    await _dua_orang(eid, "1")


# ═══ U4 — jenis kas rekening diubah menjadi kas kecil ═══════════════════════════════════════════════════════════════
async def test_KB3_5_U4_jenis_kas_diubah_ke_kas_kecil(klien, db, akun, sesi):
    pt = await _pt(akun, sesi, "KB35J")
    eid = pt["id"]
    pt["rek"]["TOKO"] = (await _rekening(klien, pt["h"], eid, f"Kas Toko {pt['kode']}", opening_balance=AWAL_TOKO))["id"]
    besar = await _rekening(klien, pt["h"], eid, f"Kas Besar Toko {pt['kode']}", "kas_besar")
    await _kas_berekening(eid, pt["rek"]["TOKO"], "in", 400_000)
    pt["lama"] = await _kas_lama_toko(db, eid)
    toko, nama_toko = pt["rek"]["TOKO"], f"Kas Toko {pt['kode']}"
    assert (await _saldo(klien, pt))[toko] == KAS_TOKO
    r = await klien.patch(f"/api/bank-accounts/{besar['id']}", headers=pt["h"], json={"cash_type": KK})
    assert r.status_code == 200, r.text
    assert r.json()["cash_type"] == KK and r.json()["kas_lama_ditetapkan"]["jumlah"] == 3, r.text
    sesudah = await _saldo(klien, pt)
    assert (sesudah[toko], sesudah[besar["id"]]) == (KAS_TOKO, 0.0)
    await _periksa_ditetapkan(db, pt, pt["lama"], alasan=(
        f"Rekening kas kecil kedua Kas Besar Toko {pt['kode']} terbentuk karena jenis kasnya diubah — kas lama tanpa "
        f"rekening tetap di {nama_toko}"))


# ═══ U5 — tanpa kas lama: tidak ada tulisan; rekening pertama sejenis tidak menetapkan apa pun ══════════════════════
async def test_KB3_5_U5_tanpa_kas_lama_tidak_ada_tulisan(klien, db, akun, sesi):
    pt = await _pt(akun, sesi, "KB35T")
    eid = pt["id"]
    bca = await _rekening(klien, pt["h"], eid, f"BCA {pt['kode']}", "bank", opening_balance=1_000_000)
    lama_kb = await _kas_lama(db, eid, "kas_besar", "in", 3_000_000)        # jenis lain: BCA tunggal kas besar
    pertama = await _rekening(klien, pt["h"], eid, f"Kas Toko {pt['kode']}")   # rekening kas kecil pertama (0 → 1)
    assert "kas_lama_ditetapkan" not in pertama
    await _kas_berekening(eid, pertama["id"], "in", 250_000)
    kas_sebelum = await db.cash_transactions.find({"entity_id": eid}, {"_id": 0}).sort("id", 1).to_list(None)
    jejak = await db.audit_logs.count_documents({"action": "kas_lama_rekening_ditetapkan"})
    kedua = await _rekening(klien, pt["h"], eid, f"Kas Kecil Gudang {pt['kode']}")
    assert "kas_lama_ditetapkan" not in kedua and "kas_lama_tertinggal" not in kedua, kedua
    assert await db.cash_transactions.find({"entity_id": eid}, {"_id": 0}).sort("id", 1).to_list(None) == kas_sebelum
    assert await db.audit_logs.count_documents({"action": "kas_lama_rekening_ditetapkan"}) == jejak
    assert await _kas(db, lama_kb["id"]) == lama_kb
    sesudah = await _saldo(klien, pt)
    assert (sesudah[pertama["id"]], sesudah[kedua["id"]], sesudah[bca["id"]]) == (250_000.0, 0.0, 4_000_000.0)


# ═══ U6 — buku besar tetap; batal kas lama sesudah penetapan → pembalik ke akun yang sama (PT mode lama) ═════════════
async def test_KB3_5_U6_batal_kas_lama_sesudah_penetapan_akun_sama_mode_lama(klien, db, akun, sesi):
    from services import gl_service as gl
    pt = await _acuan(klien, db, akun, sesi, "KB35V", kas_besar=False)
    eid, toko = pt["id"], pt["rek"]["TOKO"]
    tanpa_jurnal = await _kas_lama(db, eid, KK, "out", 200_000, jurnal=False)   # kas lama yang jurnalnya belum terbit
    asal = await _jurnal(db, "cash_transaction", pt["lama"][0]["id"])
    buku = await _buku_besar(db, eid)
    await _rekening(klien, pt["h"], eid, f"Kas Kecil Gudang {pt['kode']}")
    assert (await _kas(db, tanpa_jurnal["id"]))["account_id"] == toko
    assert await _buku_besar(db, eid) == buku                                 # penetapan tanpa jurnal
    assert (await _saldo(klien, pt))[toko] == KAS_TOKO - 200_000
    # Kas berjurnal: pembalik = baris jurnal asal tertukar (akun kas lama 1-1110).
    await _batal_kas(klien, pt, pt["lama"][0]["id"])
    balik = await _jurnal(db, "cash_transaction_void", pt["lama"][0]["id"])
    assert _baris(balik) == _tertukar(asal) and "1-1110" in {ln["account_code"] for ln in balik["lines"]}, balik
    # Kas tanpa jurnal: jurnal asal diterbitkan saat batal → akun yang sama dengan kas tanpa rekening (1-1110).
    akun_tanpa_rekening = await gl.akun_kas(eid, "", KK)
    await _batal_kas(klien, pt, tanpa_jurnal["id"])
    asal2 = await _jurnal(db, "cash_transaction", tanpa_jurnal["id"])
    balik2 = await _jurnal(db, "cash_transaction_void", tanpa_jurnal["id"])
    assert akun_tanpa_rekening == "1-1110" and akun_tanpa_rekening in {ln["account_code"] for ln in asal2["lines"]}
    assert _baris(balik2) == _tertukar(asal2), balik2
    assert await saldo_akun("1-1110", eid) == buku[0] - 10_000_000
    assert (await _saldo(klien, pt))[toko] == KAS_TOKO - 10_000_000


# ═══ U7 — PT mode akun per rekening: kas lama sebelum PT menyala TIDAK ditetapkan (pembaliknya akan pindah akun) ══════
async def test_KB3_5_U7_mode_per_rekening_kas_pra_penanda_tidak_ditetapkan(klien, db, akun, sesi):
    from services import cash_account_mode as mode
    from services import gl_service as gl
    pt = await _pt(akun, sesi, "KB35M")
    eid = pt["id"]
    pra = [await _kas_lama(db, eid, KK, "in", 2_000_000), await _kas_lama(db, eid, KK, "out", 500_000, akun="")]
    await mode.nyalakan(eid, "Uji KB3-5")
    toko = (await _rekening(klien, pt["h"], eid, f"Kas Toko {pt['kode']}"))["id"]
    sub = (await db.bank_accounts.find_one({"id": toko}))["gl_account_code"]
    assert sub == "1-1110-01"
    await _kas_berekening(eid, toko, "in", 100_000)
    pasca = await _kas_lama(db, eid, KK, "out", 300_000)                     # tercatat sesudah PT menyala, jurnal 1-1110
    pt["rek"]["TOKO"] = toko
    assert (await _saldo(klien, pt))[toko] == 1_300_000.0
    # Bukti alasan pengecualian: bila kas pra-penanda diberi rekening, pembaliknya dialihkan ke sub-akun rekening.
    asal_pra = await _jurnal(db, "cash_transaction", pra[0]["id"])
    assert await gl.baris_kas_rekening(asal_pra) == {}
    await db.cash_transactions.update_one({"id": pra[0]["id"]}, {"$set": {"account_id": toko}})
    alih = await gl.baris_kas_rekening(asal_pra)
    assert [v["akun"] for v in alih.values()] == [sub], alih
    await db.cash_transactions.update_one({"id": pra[0]["id"]}, {"$unset": {"account_id": ""}})
    assert await gl.baris_kas_rekening(asal_pra) == {}
    buku = (await saldo_akun("1-1110", eid), await saldo_akun(sub, eid), await db.journal_entries.count_documents(
        {"entity_id": eid}))

    kedua = await _rekening(klien, pt["h"], eid, f"Kas Kecil Gudang {pt['kode']}")
    nama_toko = f"Kas Toko {pt['kode']}"
    assert kedua["kas_lama_ditetapkan"] == {
        "jumlah": 1, "bersih": -300_000.0, "rekening_id": toko, "rekening_nama": nama_toko,
        "pesan": _pesan_ditetapkan(1, "-Rp 300.000", nama_toko)}, kedua
    assert kedua["kas_lama_tertinggal"] == {
        "jumlah": 2, "bersih": 1_500_000.0,
        "pesan": (f"2 kas lama tanpa rekening (bersih Rp 1.500.000) tidak bisa ditetapkan otomatis ke {nama_toko}: "
                  f"{pt['nama']} sudah memakai akun buku besar per rekening, sedangkan jurnal kas itu milik akun kas "
                  f"lama. Opname dan isi ulang rekening kas kecil {pt['nama']} ditahan sampai admin menetapkan rekening "
                  f"kas lama itu.")}, kedua
    assert (await _kas(db, pasca["id"]))["account_id"] == toko
    for t in pra:
        assert await _kas(db, t["id"]) == t
    assert (await saldo_akun("1-1110", eid), await saldo_akun(sub, eid), await db.journal_entries.count_documents(
        {"entity_id": eid})) == buku   # tanpa jurnal
    # Keadaan ambigu → opname rekening kas kecil ditahan.
    r = await klien.post("/api/cash-counts", headers=pt["h"], json={"account_id": toko, "jumlah_fisik": 0})
    assert r.status_code == 409 and r.json()["detail"] == _pesan_belum_pasti(
        "kas kecil", pt["nama"], 2, "Rp 1.500.000", 2), r.text
    # Batal kas yang ditetapkan (pasca-penanda) dan yang tidak (pra-penanda) → pembalik = baris asal tertukar.
    for t in (pasca, pra[1]):
        asal = await _jurnal(db, "cash_transaction", t["id"])
        await _batal_kas(klien, pt, t["id"])
        balik = await _jurnal(db, "cash_transaction_void", t["id"])
        assert _baris(balik) == _tertukar(asal) and "1-1110" in {ln["account_code"] for ln in balik["lines"]}, balik


# ═══ U8 — keadaan ambigu yang sudah terlanjur: opname & isi ulang ditahan 409, posisi tetap tampil ═══════════════════
async def test_KB3_5_U8_keadaan_ambigu_opname_dan_isi_ulang_ditahan(klien, db, akun, sesi):
    pt = await _pt(akun, sesi, "KB35G")
    eid = pt["id"]
    bca = (await _rekening(klien, pt["h"], eid, f"BCA {pt['kode']}", "bank", opening_balance=100_000_000))["id"]
    toko = (await _rekening(klien, pt["h"], eid, f"Kas Toko {pt['kode']}", opening_balance=AWAL_TOKO,
                            dana_tetap=DANA))["id"]
    gudang = (await _rekening(klien, pt["h"], eid, f"Kas Kecil Gudang {pt['kode']}"))["id"]
    kasir = (await _rekening(klien, pt["h"], eid, f"Kas Kasir {pt['kode']}", "kas_kasir"))["id"]
    lama = await _kas_lama_toko(db, eid)          # FIXTURE: data sebelum perbaikan (dua rekening kas kecil sudah ada)
    pesan = _pesan_belum_pasti("kas kecil", pt["nama"], 3, "Rp 7.750.000", 2)
    n_opname = await db.cash_counts.count_documents({})
    for rid in (toko, gudang):
        r = await klien.post("/api/cash-counts", headers=pt["h"], json={"account_id": rid, "jumlah_fisik": 1})
        assert r.status_code == 409 and r.json()["detail"] == pesan, r.text
    assert await db.cash_counts.count_documents({}) == n_opname
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{toko}", headers=pt["h"])
    assert r.status_code == 200, r.text
    pos = r.json()
    assert (pos["bisa_isi_ulang"], pos["alasan_isi_ulang"], pos["saldo_buku"]) == (False, pesan, 25_000_000.0), pos
    r = await klien.post(f"/api/kas-kecil/dana-tetap/{toko}/isi-ulang", headers=pt["h"],
                         json={"sumber_account_id": bca})
    assert r.status_code == 409 and r.json()["detail"] == pesan, r.text
    assert await db.fund_transfers.count_documents({"entity_id": eid}) == 0
    # Jenis lain tidak ditahan: opname kas kasir berjalan.
    r = await klien.post("/api/cash-counts", headers=pt["h"], json={"account_id": kasir, "jumlah_fisik": 0})
    assert r.status_code == 200 and r.json()["status"] == "selesai", r.text
    # Tanpa perbaikan otomatis: kas lama tetap tanpa rekening.
    for t in lama:
        assert await _kas(db, t["id"]) == t


# ═══ U9 — sesudah penetapan opname memotret saldo yang benar; usulan isi ulang tidak naik ═══════════════════════════
async def test_KB3_5_U9_opname_dan_dana_tetap_sesudah_penetapan(klien, db, akun, sesi):
    pt = await _acuan(klien, db, akun, sesi, "KB35O")
    toko = pt["rek"]["TOKO"]
    await _rekening(klien, pt["h"], pt["id"], f"Kas Kecil Gudang {pt['kode']}")
    r = await klien.post("/api/cash-counts", headers=pt["h"], json={"account_id": toko, "jumlah_fisik": KAS_TOKO})
    assert r.status_code == 200, r.text
    assert (r.json()["saldo_buku"], r.json()["selisih"], r.json()["status"]) == (KAS_TOKO, 0.0, "selesai"), r.text
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{toko}", headers=pt["h"])
    pos = r.json()
    assert (pos["saldo_buku"], pos["usulan_isi_ulang"], pos["bisa_isi_ulang"]) == (KAS_TOKO, 6_850_000.0, True), pos


# ═══ U10 — dua pembuatan rekening bersamaan: keduanya menetapkan ke rekening lama yang sama, tepat sekali ═══════════
async def test_KB3_5_U10_dua_pembuatan_bersamaan(klien, db, akun, sesi):
    pt = await _acuan(klien, db, akun, sesi, "KB35R", kas_besar=False)
    eid, toko = pt["id"], pt["rek"]["TOKO"]
    hasil = await asyncio.gather(*(klien.post("/api/bank-accounts", headers=pt["h"], json={
        "name": f"Kas Kecil {n} {pt['kode']}", "account_type": "cash", "cash_type": KK, "entity_id": eid})
        for n in ("Gudang", "Cimahi")))
    assert [r.status_code for r in hasil] == [200, 200], [r.text for r in hasil]
    ditetapkan = [r.json()["kas_lama_ditetapkan"] for r in hasil if "kas_lama_ditetapkan" in r.json()]
    assert sum(d["jumlah"] for d in ditetapkan) == 3 and {d["rekening_id"] for d in ditetapkan} == {toko}, ditetapkan
    saldo = await _saldo(klien, pt)
    assert (saldo[toko], saldo[hasil[0].json()["id"]], saldo[hasil[1].json()["id"]]) == (KAS_TOKO, 0.0, 0.0)
    for t in pt["lama"]:
        assert (await _kas(db, t["id"]))["account_id"] == toko


# ═══ U11 — rekening bank kedua: kas lama kas besar tanpa rekening tetap di bank lama ═════════════════════════════════
async def test_KB3_5_U11_rekening_bank_kedua(klien, db, akun, sesi):
    pt = await _acuan(klien, db, akun, sesi, "KB35K")
    bca, nama_bca = pt["rek"]["BCA"], f"BCA {pt['kode']}"
    mandiri = await _rekening(klien, pt["h"], pt["id"], f"Mandiri {pt['kode']}", "bank")
    assert mandiri["kas_lama_ditetapkan"] == {
        "jumlah": 1, "bersih": 100_000_000.0, "rekening_id": bca, "rekening_nama": nama_bca,
        "pesan": _pesan_ditetapkan(1, "Rp 100.000.000", nama_bca)}, mandiri
    t = await _kas(db, pt["lama_kb"]["id"])
    assert t["account_id"] == bca and t["rekening_ditetapkan"]["alasan"] == (
        f"Rekening kas besar kedua Mandiri {pt['kode']} dibuat — kas lama tanpa rekening tetap di {nama_bca}")
    saldo = await _saldo(klien, pt)
    assert (saldo[bca], saldo[mandiri["id"]], saldo[pt["rek"]["TOKO"]]) == (200_000_000.0, 0.0, KAS_TOKO)
    for lama in pt["lama"]:                                                    # jenis lain (kas kecil) tidak tersentuh
        assert await _kas(db, lama["id"]) == lama


# ═══ U12 — jenis kas rekening lama diisi dari riwayat (proses awal) membentuk rekening kas besar kedua ═══════════════
async def test_KB3_5_U12_isi_jenis_kas_dari_riwayat(klien, db, akun, sesi):
    from services import bank_service as bs
    pt = await _pt(akun, sesi, "KB35H")
    eid = pt["id"]
    bca = (await _rekening(klien, pt["h"], eid, f"BCA {pt['kode']}", "bank", opening_balance=1_000_000))["id"]
    lama_kb = await _kas_lama(db, eid, "kas_besar", "in", 3_000_000)
    rid = f"bank_lama_{uuid.uuid4().hex[:8]}"                                  # rekening tunai lama tanpa jenis kas
    await db.bank_accounts.insert_one({"id": rid, "name": f"Kas Lama {pt['kode']}", "account_type": "cash",
                                       "entity_id": eid, "opening_balance": 0, "is_active": True,
                                       "created_at": now_iso()})
    for _ in range(2):   # riwayat mayoritas kas besar → jenis kas diisi kas besar
        await db.cash_transactions.insert_one({"id": f"cash_h_{uuid.uuid4().hex[:8]}", "entity_id": eid,
                                               "account_id": rid, "cash_type": "kas_besar", "direction": "in",
                                               "amount": 1.0, "status": "posted", "created_at": now_iso()})
    pt["rek"]["BCA"] = bca
    assert (await _saldo(klien, pt))[bca] == 4_000_000.0
    assert await bs.backfill_cash_type() >= 1
    assert (await db.bank_accounts.find_one({"id": rid}))["cash_type"] == "kas_besar"
    t = await _kas(db, lama_kb["id"])
    assert t["account_id"] == bca and t["rekening_ditetapkan"]["oleh"] == "Sistem", t
    assert (await _saldo(klien, pt))[bca] == 4_000_000.0


# ═══ U13 — pencairan panjar lama tanpa rekening yang masih terbuka ikut ditetapkan: saldo tetap, panjar ikut rekening ══
async def test_KB3_5_U13_panjar_lama_tanpa_rekening_ikut_rekening(klien, db, akun, sesi):
    """Akibat penetapan pada dana tetap: pencairan PD lama tanpa rekening (belum LPJ) dulu disebut di
    `panjar_tanpa_rekening` (tidak dihitung ke rekening mana pun) padahal keluarnya sudah mengurangi saldo Kas Toko
    (rekening tunggal). Sesudah ditetapkan ke Kas Toko, sisa panjarnya dihitung sebagai panjar belum LPJ Kas Toko.
    Hitung tangan: saldo 33.150.000 − 300.000 = 32.850.000 (tetap); usulan sebelum = 40.000.000 − 32.850.000 − 0 =
    7.150.000; sesudah = 40.000.000 − 32.850.000 − 300.000 = 6.850.000 (saldo + panjar + usulan = dana tetap)."""
    pt = await _acuan(klien, db, akun, sesi, "KB35D", kas_besar=False)
    eid, toko = pt["id"], pt["rek"]["TOKO"]
    ca = f"ca_kb35_{uuid.uuid4().hex[:8]}"
    await db.cash_advances.insert_one({"id": ca, "number": f"PD-L{ca[-5:]}", "entity_id": eid, "status": "disbursed",
                                       "kegiatan": "uji KB3-5", "total_amount": 300_000.0, "created_by": "Uji",
                                       "created_at": now_iso()})
    kas_pd = await _kas_lama(db, eid, KK, "out", 300_000)
    await db.cash_transactions.update_one({"id": kas_pd["id"]}, {"$set": {"ref_type": "cash_advance", "ref_id": ca}})
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{toko}", headers=pt["h"])
    pos = r.json()
    assert (pos["saldo_buku"], pos["panjar_belum_lpj"], pos["usulan_isi_ulang"]) == (32_850_000.0, 0.0, 7_150_000.0)
    assert (pos["panjar_tanpa_rekening"]["jumlah"], pos["panjar_tanpa_rekening"]["total"]) == (1, 300_000.0), pos
    baru = await _rekening(klien, pt["h"], eid, f"Kas Kecil Gudang {pt['kode']}")
    assert (baru["kas_lama_ditetapkan"]["jumlah"], baru["kas_lama_ditetapkan"]["bersih"]) == (4, 7_450_000.0), baru
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{toko}", headers=pt["h"])
    pos = r.json()
    assert (pos["saldo_buku"], pos["panjar_belum_lpj"], pos["usulan_isi_ulang"]) == (32_850_000.0, 300_000.0,
                                                                                     6_850_000.0), pos
    assert pos["panjar_tanpa_rekening"]["jumlah"] == 0 and pos["bisa_isi_ulang"] is True, pos
