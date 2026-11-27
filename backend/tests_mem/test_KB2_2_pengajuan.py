"""KB-2 Tugas 2 (C6) — kas keluar manual di atas batas PT menjadi **pengajuan** (`cash_out_requests`, nomor `PKK-`) yang
baru terbit sebagai kas + jurnal sesudah orang kedua menyetujuinya.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` §5.2, §6, §7 (butir 7.8: 1, 3, 4, 5, 6).
Ketetapan pengendali Tugas 2: nomor `PKK-` urut per PT; Batal oleh pengaju (`cash.create`) atau pemegang `cash.delete`
selama menunggu; Tolak `cash.approve`, alasan wajib, bukan pengaju; Setujui memeriksa ulang rekening, periode, kategori,
anggaran (gagal → 409 berkalimat, tetap menunggu, tanpa kas) — batas TIDAK dinilai ulang; pengajuan menunggu tidak
terhitung di saldo kas, daftar/ringkasan Transaksi Kas, maupun buku kas rekening.
"""
from __future__ import annotations

import asyncio
import itertools
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from pembantu import AKTOR_UJI, pt_uji, saldo_akun

pytestmark = pytest.mark.anyio

URL = "/api/cash-transactions"
URL_P = "/api/cash-out-requests"
KAS_BANK, SEWA, OPERASIONAL = "1-1100", "6-2000", "6-4000"
PESAN_ORANG_KEDUA = ("Kas keluar manual ini harus disetujui orang lain: Anda yang mengajukannya. Minta orang lain yang "
                     "berizin menyetujui kas. Admin dapat menaikkan batas atau mengubah aturan ini di Pengaturan › "
                     "Persetujuan › Kontrol dua orang.")
PESAN_ALASAN = "Alasan penolakan wajib diisi (minimal 5 huruf)."
PESAN_KUNCI_BEDA = "Kunci idempotensi sudah dipakai untuk isi permintaan yang berbeda."
PENYETUJU = {"id": "usr_kb22_setuju", "name": "Dodi Penyetuju KB22", "role": "finance", "email": "dodi.kb22@uji.id"}
PENYETUJU2 = {"id": "usr_kb22_setuju2", "name": "Sari Penyetuju KB22", "role": "finance", "email": "sari.kb22@uji.id"}
_urut = itertools.count(1)
_PERAN: dict = {}


@pytest.fixture(scope="module", autouse=True)
def _peran_segar(klien):
    """`_PERAN` menyimpan id peran uji yang hanya ada di database modul yang membuatnya (tiap modul mulai dari database
    kosong). Dikosongkan sebelum DAN sesudah modul ini, supaya urutan modul apa pun di satu proses (KB2_3/KB2_4 lalu
    KB2_2, atau sebaliknya) tidak memakai id peran dari database modul lain."""
    _PERAN.clear()
    yield
    _PERAN.clear()


def _hari(geser: int = 0) -> str:
    from services.book_date import tanggal_buku
    return (date.fromisoformat(tanggal_buku()) + timedelta(days=geser)).isoformat()


async def _rekening(eid: str, nama: str, jenis_akun: str = "bank", jenis_kas: str = "", awal: float = 0.0) -> str:
    from schemas_finance import BankAccountCreate
    from services import bank_service
    acc = await bank_service.create_account(
        BankAccountCreate(name=nama, account_type=jenis_akun, cash_type=jenis_kas, entity_id=eid,
                          opening_balance=awal), AKTOR_UJI)
    return acc["id"]


async def _peran(peran_tanpa_acuan, nama: str, izin: dict) -> str:
    if nama not in _PERAN:
        _PERAN[nama] = await peran_tanpa_acuan(izin, label=f"KB22 {nama}")
    return _PERAN[nama]


async def _pt(akun, sesi, peran_tanpa_acuan) -> dict:
    """PT uji baru (akun per rekening belum aktif): BCA (bank, saldo awal 50 jt) dan KT (kas tunai kas besar, 10 jt),
    plus orang-orangnya: `aju` (lihat, buat, setujui — supaya penolakan dua orang yang teruji, bukan izin), `aju2`
    (lihat, buat), `setuju` & `setuju2` (lihat, setujui), `hapus` (lihat, batal), `lihat`."""
    from services.entity_lifecycle_service import invalidate_status_cache
    kode = f"KB22P{next(_urut)}"
    eid = await pt_uji(kode)
    rek = {"BCA": await _rekening(eid, f"BCA {kode}", awal=50_000_000),
           "KT": await _rekening(eid, f"Kas Toko {kode}", "cash", "kas_besar", awal=10_000_000)}
    invalidate_status_cache()
    peran = {"aju": await _peran(peran_tanpa_acuan, "Aju", {"cash": ["view", "create", "approve"]}),
             "aju2": await _peran(peran_tanpa_acuan, "Aju Saja", {"cash": ["view", "create"]}),
             "setuju": await _peran(peran_tanpa_acuan, "Setujui", {"cash": ["view", "approve"]}),
             "hapus": await _peran(peran_tanpa_acuan, "Batal", {"cash": ["view", "delete"]}),
             "lihat": await _peran(peran_tanpa_acuan, "Lihat", {"cash": ["view"]})}
    orang = {}
    for k, p in (("aju", "aju"), ("aju2", "aju2"), ("setuju", "setuju"), ("setuju2", "setuju"), ("hapus", "hapus"),
                 ("lihat", "lihat")):
        u = await akun(peran[p], entitas=(eid,))
        orang[k] = {"u": u, "h": await sesi(u, entitas=eid)}
    return {"id": eid, "kode": kode, "rek": rek, "o": orang}


def _isi(pt: dict, nominal: float, arah: str = "out", rek: str = "BCA", **lain) -> dict:
    return {"cash_type": "kas_besar", "direction": arah, "amount": nominal, "category": "operasional",
            "description": f"uji KB22 {nominal}", "account_id": pt["rek"][rek], **lain}


async def _kirim(klien, pt: dict, nominal: float, siapa: str = "aju", kunci: str = "", **lain):
    h = dict(pt["o"][siapa]["h"])
    if kunci:
        h["Idempotency-Key"] = kunci
    return await klien.post(URL, headers=h, json=_isi(pt, nominal, **lain))


async def _ajukan(klien, pt: dict, nominal: float, **lain) -> dict:
    r = await _kirim(klien, pt, nominal, **lain)
    assert r.status_code == 202, r.text
    return r.json()["request"]


async def _atur(key: str, nilai, eid: str) -> None:
    from services import config_resolver as resolver
    await resolver.set_value(key, nilai, scope_type="entity", scope_id=eid, reason="uji KB22 kontrol", actor="uji")


async def _potret(klien, db, pt: dict) -> dict:
    """Semua angka yang TIDAK boleh berubah oleh pengajuan menunggu."""
    from services import bank_service
    h = pt["o"]["lihat"]["h"]
    ring = (await klien.get(f"{URL}/summary", headers=h)).json()
    daftar = (await klien.get(URL, headers=h, params={"page": 1, "page_size": 100})).json()
    rek = {x["id"]: x for x in (await klien.get("/api/bank-accounts", headers=h)).json()}
    return {"akun_kas": round(await saldo_akun(KAS_BANK, pt["id"]), 2),
            "buku_bca": round((await bank_service.account_ledger(pt["rek"]["BCA"]))["balance"], 2),
            "saldo_rek_bca": round(float(rek[pt["rek"]["BCA"]].get("balance") or 0), 2),
            "ringkasan": (ring["kas_besar"]["balance"], ring["kas_besar"]["out"], ring["kas_besar"]["count"],
                          ring["counts"]["all"]),
            "daftar": daftar["total"],
            "kas": await db.cash_transactions.count_documents({"entity_id": pt["id"]}),
            "jurnal": await db.journal_entries.count_documents({"entity_id": pt["id"]})}


async def _kas_pengajuan(db, rid: str) -> list:
    return [t async for t in db.cash_transactions.find({"ref_type": "manual", "ref_id": rid}, {"_id": 0})]


async def _ditolak(coro, status: int, pesan: str = "") -> HTTPException:
    with pytest.raises(HTTPException) as e:
        await coro
    assert e.value.status_code == status, e.value.detail
    if pesan:
        assert e.value.detail == pesan, e.value.detail
    return e.value


def _aktor(pt: dict, siapa: str) -> dict:
    u = pt["o"][siapa]["u"]
    return {k: u[k] for k in ("id", "name", "role", "email")}


# ═══ 1. Batas: = batas langsung, di atas batas = pengajuan tanpa kas/jurnal; kas masuk tidak terkena ═════════════════
async def test_KB2_2_U1_batas_langsung_dan_pengajuan(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    r = await _kirim(klien, pt, 1_000_000)                       # = batas → langsung
    assert r.status_code == 200, r.text
    kas = r.json()
    assert (kas["direction"], kas["amount"], kas["ref_type"], kas["status"]) == ("out", 1_000_000.0, "manual", "posted")
    assert kas["journal_entry_number"]
    sebelum = await _potret(klien, db, pt)
    r = await _kirim(klien, pt, 1_000_001)                       # di atas batas → pengajuan
    assert r.status_code == 202, r.text
    p = r.json()["request"]
    assert p["number"] == f"{pt['kode']}/PKK-00001", p["number"]
    assert (p["status"], p["status_label"], p["direction"], p["amount"], p["cash_type"]) == (
        "menunggu_persetujuan", "Menunggu persetujuan", "out", 1_000_001.0, "kas_besar")
    assert (p["account_id"], p["category"], p["entity_id"]) == (pt["rek"]["BCA"], "operasional", pt["id"])
    assert p["pengaju"] == {"id": pt["o"]["aju"]["u"]["id"], "name": pt["o"]["aju"]["u"]["name"]}
    assert p["cash_id"] == "" and [j["aksi"] for j in p["jejak"]] == ["ajukan"]
    assert await _kas_pengajuan(db, p["id"]) == []
    assert await _potret(klien, db, pt) == sebelum               # saldo, buku kas rekening, ringkasan, daftar, jurnal
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert d["status"] == "menunggu_persetujuan" and d["txn_date"]
    # Nomor urut per PT
    p2 = await _ajukan(klien, pt, 3_000_000)
    assert p2["number"] == f"{pt['kode']}/PKK-00002"
    # Kas MASUK di atas batas → langsung seperti sekarang
    r = await _kirim(klien, pt, 5_000_000, arah="in")
    assert r.status_code == 200 and r.json()["direction"] == "in", r.text


# ═══ 2. Pengaturan per PT: min_orang "2" = semua kas keluar manual; batas PT diubah ═════════════════════════════════
async def test_KB2_2_U2_min_orang_dua_dan_batas_pt(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    await _atur("kontrol.kas_keluar_manual.min_orang", "2", pt["id"])
    r = await _kirim(klien, pt, 10_000)
    assert r.status_code == 202 and r.json()["request"]["amount"] == 10_000.0, r.text
    r = await _kirim(klien, pt, 10_000, arah="in")                # kas masuk tetap langsung
    assert r.status_code == 200, r.text
    await _atur("kontrol.kas_keluar_manual.min_orang", "1", pt["id"])
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 5_000_000, pt["id"])
    r = await _kirim(klien, pt, 2_000_000)
    assert r.status_code == 200 and r.json()["amount"] == 2_000_000.0, r.text
    r = await _kirim(klien, pt, 5_000_000)
    assert r.status_code == 200, r.text
    r = await _kirim(klien, pt, 5_000_001)
    assert r.status_code == 202, r.text
    # PT lain tetap memakai bawaan Rp 1.000.000
    pt2 = await _pt(akun, sesi, peran_tanpa_acuan)
    r = await _kirim(klien, pt2, 2_000_000)
    assert r.status_code == 202, r.text


# ═══ 3. Idempotency-Key: kiriman ulang = pengajuan yang sama (menunggu & sesudah disetujui), bukan kas langsung ═══
async def test_KB2_2_U3_kunci_idempoten_sama(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    kunci = "kb22-u3-kunci-1"
    r1 = await _kirim(klien, pt, 2_500_000, kunci=kunci)
    assert r1.status_code == 202, r1.text
    p = r1.json()["request"]
    # 202 tidak disimpan penyangga idempotensi (keadaan terkini dijawab layanan)
    assert r1.headers.get("X-Idempotency-Retry") == "true"
    assert await db.idempotency_keys.count_documents({"key": kunci, "status": "done"}) == 0
    r2 = await _kirim(klien, pt, 2_500_000, kunci=kunci)          # kiriman ulang selagi menunggu
    assert r2.status_code == 202 and r2.json()["request"]["id"] == p["id"], r2.text
    assert r2.json()["request"]["number"] == p["number"]
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 1
    # Isi berbeda dengan kunci yang sama → 409, tidak ada pengajuan kedua
    r = await _kirim(klien, pt, 2_600_000, kunci=kunci)
    assert r.status_code == 409 and r.json()["detail"] == PESAN_KUNCI_BEDA, r.text
    # Disetujui orang lain, lalu kunci sama dikirim ulang (batas PT pun dinaikkan) → pengajuan sama + tautan kas
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200 and r.json()["status"] == "disetujui", r.text
    cash_id = r.json()["cash_id"]
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 10_000_000, pt["id"])
    r3 = await _kirim(klien, pt, 2_500_000, kunci=kunci)
    assert r3.status_code == 202, r3.text
    j = r3.json()["request"]
    assert (j["id"], j["status"], j["cash_id"]) == (p["id"], "disetujui", cash_id) and j["cash_number"]
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 1
    assert [t["id"] for t in await _kas_pengajuan(db, p["id"])] == [cash_id]
    # bukan kas langsung
    assert await db.cash_transactions.count_documents({"ref_type": "manual", "ref_id": kunci}) == 0
    # Orang lain (izin sama) mengirim kunci yang sama di PT yang sama → tetap pengajuan yang sama
    h = {**pt["o"]["aju2"]["h"], "Idempotency-Key": kunci}
    r = await klien.post(URL, headers=h, json=_isi(pt, 2_500_000))
    assert r.status_code == 202 and r.json()["request"]["id"] == p["id"], r.text
    # Dua ajukan bersamaan berkunci sama (layanan) → satu pengajuan
    isi = {"cash_type": "kas_besar", "account_id": pt["rek"]["BCA"], "amount": 4_000_000.0, "category": "operasional",
           "description": "bersamaan", "txn_date": _hari(), "sidik": "s1"}
    hasil = await asyncio.gather(cors.ajukan(isi, _aktor(pt, "aju"), pt["id"], "kb22-u3-bersamaan"),
                                 cors.ajukan(isi, _aktor(pt, "aju"), pt["id"], "kb22-u3-bersamaan"))
    assert hasil[0]["id"] == hasil[1]["id"]
    assert await db.cash_out_requests.count_documents({"idempotency_key": "kb22-u3-bersamaan"}) == 1


async def test_KB2_2_U3b_kunci_kas_langsung_tetap_kas_yang_sama(klien, db, akun, sesi, peran_tanpa_acuan):
    """Kunci yang sudah menjadi kas LANGSUNG (di bawah batas) lalu batas PT diturunkan: kiriman ulangnya (orang lain /
    sesudah rekaman penyangga kedaluwarsa) tetap kas yang sama — tidak ada pengajuan di samping kas itu."""
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    kunci = "kb22-u3b-langsung"
    r = await _kirim(klien, pt, 800_000, kunci=kunci)
    assert r.status_code == 200, r.text
    kas_id = r.json()["id"]
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 500_000, pt["id"])
    h = {**pt["o"]["aju2"]["h"], "Idempotency-Key": kunci}
    r = await klien.post(URL, headers=h, json=_isi(pt, 800_000))
    assert r.status_code == 200 and r.json()["id"] == kas_id, r.text
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 0
    assert await db.cash_transactions.count_documents({"ref_type": "manual", "ref_id": kunci}) == 1


async def _keluar_berkunci(db, kunci: str) -> int:
    return await db.cash_transactions.count_documents({"ref_type": "manual", "ref_id": kunci, "direction": "out"})


# ═══ 3c. Perbaikan putaran 1 (Critical) — kunci kas MASUK / PT lain / isi lain tidak membuka kas keluar langsung ═
async def test_KB2_2_U3c_kunci_kas_masuk_tidak_meloloskan_kas_keluar(klien, db, akun, sesi, peran_tanpa_acuan):
    """Kunci yang dipakai kas MASUK lalu dikirim lagi untuk kas KELUAR di atas batas → 202 pengajuan, nol kas keluar
    langsung: (a) oleh orang lain; (b) oleh orang yang sama tanpa X-Entity-Id (PT dari isian); (c) oleh orang yang sama
    dengan X-Entity-Id PT lain miliknya (rekaman penyangga idempotensi berbeda di ketiganya)."""
    pt, lain = await _pt(akun, sesi, peran_tanpa_acuan), await _pt(akun, sesi, peran_tanpa_acuan)
    dua_pt = await akun(await _peran(peran_tanpa_acuan, "Aju", {"cash": ["view", "create", "approve"]}),
                        entitas=(pt["id"], lain["id"]))
    for varian in ("orang_lain", "tanpa_header", "header_pt_lain"):
        kunci = f"kb22-u3c-{varian}"
        r = await _kirim(klien, pt, 10_000, kunci=kunci, arah="in")
        assert r.status_code == 200 and r.json()["direction"] == "in", (varian, r.text)
        isi = {**_isi(pt, 5_000_000), "entity_id": pt["id"]}
        if varian == "orang_lain":
            h = {**pt["o"]["aju2"]["h"], "Idempotency-Key": kunci}
        elif varian == "tanpa_header":
            h = {k: v for k, v in pt["o"]["aju"]["h"].items() if k != "X-Entity-Id"}
            h["Idempotency-Key"] = kunci
        else:
            h = {**(await sesi(dua_pt, entitas=lain["id"])), "Idempotency-Key": kunci}
        r = await klien.post(URL, headers=h, json=isi)
        assert r.status_code in (202, 409), (varian, r.text)
        if r.status_code == 202:
            p = r.json()["request"]
            assert (p["status"], p["entity_id"], p["amount"]) == ("menunggu_persetujuan", pt["id"], 5_000_000.0)
        assert await _keluar_berkunci(db, kunci) == 0, varian
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 3


async def test_KB2_2_U3d_kunci_kas_keluar_pt_lain_dan_isi_lain(klien, db, akun, sesi, peran_tanpa_acuan):
    """Kunci kas keluar langsung PT A dipakai di PT B di atas batas → pengajuan PT B. Kunci kas keluar langsung yang
    dikirim ulang dengan isi lain (sesudah batas diturunkan) → 409, bukan kas kedua dan bukan pengajuan di sampingnya;
    kas lama tanpa sidik (sebelum perbaikan) dicocokkan per nominal/rekening/kategori/tanggal."""
    from services import cash_out_request_service as cors
    pa, pb = await _pt(akun, sesi, peran_tanpa_acuan), await _pt(akun, sesi, peran_tanpa_acuan)
    kunci = "kb22-u3d-lintas-pt"
    r = await _kirim(klien, pa, 800_000, kunci=kunci)
    assert r.status_code == 200 and r.json()["direction"] == "out", r.text
    kas_a = r.json()["id"]
    r = await _kirim(klien, pb, 2_000_000, kunci=kunci)
    assert r.status_code == 202 and r.json()["request"]["entity_id"] == pb["id"], r.text
    assert await db.cash_transactions.count_documents({"ref_id": kunci, "entity_id": pb["id"]}) == 0
    assert [t["id"] async for t in db.cash_transactions.find({"ref_id": kunci}, {"_id": 0, "id": 1})] == [kas_a]
    # Isi lain dengan kunci kas keluar langsung yang sama (batas PT A diturunkan di bawah nominalnya)
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 500_000, pa["id"])
    h = {**pa["o"]["aju2"]["h"], "Idempotency-Key": kunci}
    for beda in ({"amount": 900_000}, {"category": "sewa"}, {"account_id": pa["rek"]["KT"]}, {"txn_date": _hari(-1)}):
        r = await klien.post(URL, headers=h, json={**_isi(pa, 800_000), **beda})
        assert r.status_code == 409 and r.json()["detail"] == PESAN_KUNCI_BEDA, (beda, r.text)
    r = await klien.post(URL, headers=h, json=_isi(pa, 800_000))        # isi sama → kas yang sama
    assert r.status_code == 200 and r.json()["id"] == kas_a, r.text
    assert await db.cash_out_requests.count_documents({"entity_id": pa["id"]}) == 0
    assert await _keluar_berkunci(db, kunci) == 1
    # Kas lama tanpa sidik: cocok per nominal, rekening, kategori (dan tanggal bila dikirim). Kiriman tanpa X-Entity-Id
    # (PT dari isian) = rekaman penyangga lain, jadi yang menjawab layanan, bukan rekaman 200 di atas.
    await db.cash_transactions.update_one({"id": kas_a}, {"$unset": {"sidik_kiriman": ""}})

    def _tanpa_entitas(siapa):
        return {**{k: v for k, v in pa["o"][siapa]["h"].items() if k != "X-Entity-Id"}, "Idempotency-Key": kunci}

    isi = {**_isi(pa, 800_000), "entity_id": pa["id"]}
    r = await klien.post(URL, headers=_tanpa_entitas("aju"), json={**isi, "category": "sewa"})
    assert r.status_code == 409 and r.json()["detail"] == PESAN_KUNCI_BEDA, r.text
    r = await klien.post(URL, headers=_tanpa_entitas("aju"), json=isi)
    assert r.status_code == 200 and r.json()["id"] == kas_a, r.text
    # Kas langsung yang sudah dibatalkan tidak dihitung: kiriman ulang di atas batas → pengajuan
    await db.cash_transactions.update_one({"id": kas_a}, {"$set": {"status": "void"}})
    r = await klien.post(URL, headers=_tanpa_entitas("aju2"), json=isi)
    assert r.status_code == 202, r.text
    assert await _keluar_berkunci(db, kunci) == 1
    assert cors.PESAN_KUNCI_BEDA == PESAN_KUNCI_BEDA


# ═══ 4. Orang kedua: pengaju tidak menyetujui sendiri; Admin pun tidak (bawaan admin-tetap) ═════════════════════════
async def test_KB2_2_U4_setujui_sendiri_403_dan_admin_tetap(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin):
    import config_registry as registry
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    assert "kas_keluar_manual" in registry.require("kontrol.admin_tetap_dua_orang")["default"]
    p = await _ajukan(klien, pt, 1_500_000)
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["aju"]["h"])
    assert r.status_code == 403 and r.json()["detail"] == PESAN_ORANG_KEDUA, r.text
    # Admin yang mengajukan juga butuh orang kedua (kas_keluar_manual di bawaan kontrol.admin_tetap_dua_orang)
    ha = {**kepala_admin, "X-Entity-Id": pt["id"]}
    r = await klien.post(URL, headers=ha, json=_isi(pt, 1_500_000))
    assert r.status_code == 202, r.text
    pa = r.json()["request"]
    r = await klien.post(f"{URL_P}/{pa['id']}/approve", headers=ha)
    assert r.status_code == 403 and r.json()["detail"] == PESAN_ORANG_KEDUA, r.text
    for x in (p, pa):
        assert (await db.cash_out_requests.find_one({"id": x["id"]}))["status"] == "menunggu_persetujuan"
        assert await _kas_pengajuan(db, x["id"]) == []
    # Tetap pengaturan: daftar admin-tetap PT tanpa kas_keluar_manual → Admin boleh memutuskan sendiri (tercatat)
    await _atur("kontrol.admin_tetap_dua_orang", ["susut_makloon"], pt["id"])
    r = await klien.post(f"{URL_P}/{pa['id']}/approve", headers=ha)
    assert r.status_code == 200 and r.json()["status"] == "disetujui", r.text
    # Pengaju biasa tetap tidak bisa (pengecualian hanya untuk Admin) — juga sesudah batas PT dinaikkan di atas nominal
    # pengajuan: batas tidak dinilai ulang saat disetujui (§7.8.3), pengajuan tidak pernah terbit sendiri.
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 10_000_000, pt["id"])
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["aju"]["h"])
    assert r.status_code == 403 and r.json()["detail"] == PESAN_ORANG_KEDUA, r.text
    assert (await db.cash_out_requests.find_one({"id": p["id"]}))["status"] == "menunggu_persetujuan"
    # Rincian membawa penilaian kontrol (tombol Setujui jujur di layar)
    r = await klien.get(f"{URL_P}/{p['id']}", headers=pt["o"]["aju"]["h"])
    assert r.status_code == 200 and r.json()["kontrol"]["ditolak"] is True, r.text
    r = await klien.get(f"{URL_P}/{p['id']}", headers=pt["o"]["setuju"]["h"])
    assert r.json()["kontrol"]["ditolak"] is False and r.json()["kontrol"]["dua_orang"] is True


# ═══ 5. Setujui orang lain → kas manual ber-ref pengajuan, tanggal = tanggal diajukan, pembuat kas = pengaju ═════════
async def test_KB2_2_U5_setujui_orang_lain_kas_terbit(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    tgl = _hari(-2)
    p = await _ajukan(klien, pt, 1_750_000, txn_date=tgl)
    assert p["txn_date"] == tgl
    sebelum = await _potret(klien, db, pt)
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200, r.text
    j = r.json()
    setuju = pt["o"]["setuju"]["u"]
    assert (j["status"], j["status_label"], j["disetujui_oleh"], j["disetujui_oleh_id"]) == (
        "disetujui", "Disetujui", setuju["name"], setuju["id"])
    [kas] = await _kas_pengajuan(db, p["id"])
    assert j["cash_id"] == kas["id"] and j["cash_number"] == kas["number"]
    assert (kas["ref_type"], kas["ref_id"], kas["direction"], kas["amount"], kas["txn_date"]) == (
        "manual", p["id"], "out", 1_750_000.0, tgl)
    assert (kas["account_id"], kas["category"], kas["description"], kas["cash_type"]) == (
        pt["rek"]["BCA"], "operasional", "uji KB22 1750000", "kas_besar")
    assert kas["created_by"] == pt["o"]["aju"]["u"]["name"]           # pembuat kas = pengaju
    assert (kas["disetujui_oleh"], kas["disetujui_oleh_id"], kas["cash_out_request_number"]) == (
        setuju["name"], setuju["id"], p["number"])
    assert kas["gl_status"] == "posted" and j["kas"]["gl_status"] == "posted" and j["kas"]["journal_number"]
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"]}, {"_id": 0})
    assert je["date"][:10] == tgl
    assert sorted((ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]) == sorted(
        [(OPERASIONAL, 1_750_000.0, 0.0), (KAS_BANK, 0.0, 1_750_000.0)])
    sesudah = await _potret(klien, db, pt)
    assert round(sesudah["akun_kas"] - sebelum["akun_kas"], 2) == -1_750_000.0
    assert round(sesudah["buku_bca"] - sebelum["buku_bca"], 2) == -1_750_000.0
    assert sesudah["kas"] - sebelum["kas"] == 1 and sesudah["daftar"] - sebelum["daftar"] == 1
    assert [x["aksi"] for x in j["jejak"]] == ["ajukan", "setujui"]
    # Kas yang terbit = kas manual biasa: bisa dibatalkan dari Transaksi Kas; pengajuan tetap `disetujui`
    r = await klien.post(f"{URL}/{kas['id']}/void", headers=pt["o"]["hapus"]["h"], json={"reason": "uji batal kas"})
    assert r.status_code == 200 and r.json()["status"] == "void", r.text
    assert (await db.cash_out_requests.find_one({"id": p["id"]}))["status"] == "disetujui"


# ═══ 6. Setujui ganda → satu kas ═════════════════════════════════════════════════════════════════════════════════════
async def test_KB2_2_U6_setujui_ganda_satu_kas(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 2_000_000)
    hasil = await asyncio.gather(cors.setujui(p["id"], PENYETUJU), cors.setujui(p["id"], PENYETUJU2),
                                 return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    assert len(ok) == 1, hasil
    assert all(isinstance(h, HTTPException) and h.status_code == 409 for h in hasil if not isinstance(h, dict)), hasil
    assert len(await _kas_pengajuan(db, p["id"])) == 1
    e = await _ditolak(cors.setujui(p["id"], PENYETUJU), 409)
    assert e.detail == f"Pengajuan kas keluar {p['number']} sudah disetujui, jadi tidak bisa disetujui lagi.", e.detail
    assert len(await _kas_pengajuan(db, p["id"])) == 1
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert d["status"] == "disetujui" and not d.get("saga_lock")


# ═══ 7. Setujui × Batal di sela PERIKSA dan KLAIM (pola Pindah Dana T4 U13) → utuh salah satu ═══════════════════════
def _sela_sekali(mod, monkeypatch, nama: str, aksi):
    """Bungkus `mod.<nama>`: sesudah fungsi aslinya, jalankan `aksi()` SEKALI (orang lain bertindak tepat di sela
    PERIKSA dan KLAIM). Hasil/galat aksi disimpan di `jejak["hasil"]`."""
    asli, jejak = getattr(mod, nama), {}

    async def _bungkus(*a, **kw):
        hasil = await asli(*a, **kw)
        if "hasil" not in jejak:
            jejak["hasil"] = None
            try:
                jejak["hasil"] = await aksi()
            except HTTPException as exc:
                jejak["hasil"] = exc
        return hasil

    monkeypatch.setattr(mod, nama, _bungkus)
    return jejak


async def test_KB2_2_U7a_batal_di_sela_setujui(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch):
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 1_200_000)
    sebelum = await _potret(klien, db, pt)
    sela = _sela_sekali(cors, monkeypatch, "_periksa_terbit", lambda: cors.batal(p["id"], _aktor(pt, "aju")))
    await _ditolak(cors.setujui(p["id"], PENYETUJU), 409,
                   f"Pengajuan kas keluar {p['number']} sudah dibatalkan, jadi tidak bisa disetujui.")
    assert isinstance(sela["hasil"], dict) and sela["hasil"]["status"] == "dibatalkan", sela
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert (d["status"], d.get("saga_lock"), d.get("cash_id")) == ("dibatalkan", None, "")
    assert await _kas_pengajuan(db, p["id"]) == []
    assert await _potret(klien, db, pt) == sebelum


async def test_KB2_2_U7b_setujui_di_sela_batal(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch):
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 1_300_000)
    sela = _sela_sekali(cors, monkeypatch, "_tolak_bila_kas_terbit", lambda: cors.setujui(p["id"], PENYETUJU))
    e = await _ditolak(cors.batal(p["id"], _aktor(pt, "aju")), 409)
    assert e.detail.startswith(f"Pengajuan kas keluar {p['number']} sudah disetujui, jadi tidak bisa dibatalkan."), \
        e.detail
    assert isinstance(sela["hasil"], dict) and sela["hasil"]["status"] == "disetujui", sela
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert (d["status"], d.get("saga_lock")) == ("disetujui", None) and d.get("dibatalkan_oleh") is None
    kas = await _kas_pengajuan(db, p["id"])
    assert len(kas) == 1 and kas[0]["status"] == "posted" and d["cash_id"] == kas[0]["id"]


# ═══ 8. Periode tertutup saat disetujui → 409 berkalimat, tetap menunggu, tanpa kas ═════════════════════════════════
async def test_KB2_2_U8_periode_tertutup_saat_disetujui(klien, db, akun, sesi, peran_tanpa_acuan):
    from pembantu import tutup_periode
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    lalu = (date.fromisoformat(_hari()).replace(day=1) - timedelta(days=1)).isoformat()
    p = await _ajukan(klien, pt, 1_100_000, txn_date=lalu)
    c = await tutup_periode(pt["id"], lalu[:7])
    try:
        e = await _ditolak(cors.setujui(p["id"], PENYETUJU), 409)
        assert "DITUTUP" in e.detail and e.detail.endswith(
            f"Pengajuan {p['number']} tetap menunggu — batalkan lalu ajukan ulang dengan tanggal di periode yang "
            "terbuka."), e.detail
        d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
        assert (d["status"], d.get("saga_lock"), d["cash_id"]) == ("menunggu_persetujuan", None, "")
        assert await _kas_pengajuan(db, p["id"]) == []
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    hasil = await cors.setujui(p["id"], PENYETUJU)                 # periode dibuka lagi → bisa disetujui
    assert hasil["status"] == "disetujui" and len(await _kas_pengajuan(db, p["id"])) == 1


# ═══ 9. Anggaran: tidak dicadangkan; diperiksa lagi saat disetujui (mode blokir) → 409, tetap menunggu ══════════════
async def test_KB2_2_U9_anggaran_blokir_saat_disetujui(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import budget_service as bs
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    hari = _hari()
    await bs.create_budget({"year": int(hari[:4]), "month": int(hari[5:7]), "dimension": "account", "key": SEWA,
                            "amount": 3_000_000}, pt["id"], AKTOR_UJI)
    await _atur("budget.mode", "blokir", pt["id"])
    a = await _ajukan(klien, pt, 2_000_000, category="sewa", txn_date=hari)
    b = await _ajukan(klien, pt, 2_000_000, category="sewa", txn_date=hari)   # tidak dicadangkan: lolos saat diajukan
    assert a["budget_check"]["blocked"] is False and a["budget_check"]["when"] == "cash_out"
    assert (await cors.setujui(a["id"], PENYETUJU))["status"] == "disetujui"
    e = await _ditolak(cors.setujui(b["id"], PENYETUJU), 409)
    assert e.detail.startswith("Anggaran terlampaui:"), e.detail
    assert e.detail.endswith(f"Pengajuan {b['number']} tetap menunggu."), e.detail
    d = await db.cash_out_requests.find_one({"id": b["id"]}, {"_id": 0})
    assert (d["status"], d.get("saga_lock")) == ("menunggu_persetujuan", None)
    assert await _kas_pengajuan(db, b["id"]) == []
    # Kas langsung pun tertahan anggaran seperti sebelumnya (400 saat dicatat)
    r = await _kirim(klien, pt, 2_000_000, category="sewa", txn_date=hari)
    assert r.status_code == 400 and r.json()["detail"].startswith("Anggaran terlampaui"), r.text


# ═══ 10. Tolak & Batal ═══════════════════════════════════════════════════════════════════════════════════════════════
async def test_KB2_2_U10_tolak_dan_batal(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 1_400_000)
    hs = pt["o"]["setuju"]["h"]
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=hs, json={"alasan": ""})
    assert r.status_code == 400 and r.json()["detail"] == PESAN_ALASAN, r.text
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=hs, json={"alasan": "abc"})
    assert r.status_code == 400 and r.json()["detail"] == PESAN_ALASAN, r.text
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=pt["o"]["aju"]["h"], json={"alasan": "tolak sendiri"})
    assert r.status_code == 403 and r.json()["detail"] == (
        "Pengajuan ini Anda ajukan sendiri, jadi tidak bisa Anda tolak. Pakai Batal bila tidak jadi."), r.text
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=hs, json={"alasan": "tidak ada nota"})
    assert r.status_code == 200, r.text
    j = r.json()
    setuju = pt["o"]["setuju"]["u"]
    assert (j["status"], j["alasan_tolak"], j["ditolak_oleh"], j["ditolak_oleh_id"]) == (
        "ditolak", "tidak ada nota", setuju["name"], setuju["id"])
    assert [x["aksi"] for x in j["jejak"]] == ["ajukan", "tolak"] and await _kas_pengajuan(db, p["id"]) == []
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=hs, json={"alasan": "tidak ada nota"})
    assert r.status_code == 409 and r.json()["detail"] == (
        f"Pengajuan kas keluar {p['number']} sudah ditolak, jadi tidak bisa ditolak lagi."), r.text
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=hs)
    assert r.status_code == 409, r.text
    # Batal oleh pengaju → dibatalkan
    q = await _ajukan(klien, pt, 1_600_000, siapa="aju2")
    r = await klien.post(f"{URL_P}/{q['id']}/cancel", headers=pt["o"]["aju2"]["h"], json={"alasan": "salah rekening"})
    assert r.status_code == 200, r.text
    aju2 = pt["o"]["aju2"]["u"]
    assert (r.json()["status"], r.json()["dibatalkan_oleh"], r.json()["alasan_batal"]) == (
        "dibatalkan", aju2["name"], "salah rekening")
    r = await klien.post(f"{URL_P}/{q['id']}/cancel", headers=pt["o"]["aju2"]["h"], json={})
    assert r.status_code == 409 and r.json()["detail"] == (
        f"Pengajuan kas keluar {q['number']} sudah dibatalkan, jadi tidak bisa dibatalkan lagi."), r.text
    # Batal oleh pemegang `cash.create` lain (bukan pengaju) → 403; oleh pemegang `cash.delete` → boleh (tanpa isi)
    s = await _ajukan(klien, pt, 1_700_000, siapa="aju2")
    r = await klien.post(f"{URL_P}/{s['id']}/cancel", headers=pt["o"]["aju"]["h"], json={})
    assert r.status_code == 403 and r.json()["detail"] == (
        "Hanya pengaju atau pemegang akses membatalkan kas yang bisa membatalkan pengajuan ini."), r.text
    r = await klien.post(f"{URL_P}/{s['id']}/cancel", headers=pt["o"]["hapus"]["h"])
    assert r.status_code == 200 and r.json()["status"] == "dibatalkan", r.text
    # Batal sesudah disetujui → 409 (kasnya dibatalkan dari Transaksi Kas)
    t = await _ajukan(klien, pt, 1_800_000, siapa="aju2")
    setuju_hasil = await cors.setujui(t["id"], PENYETUJU)
    r = await klien.post(f"{URL_P}/{t['id']}/cancel", headers=pt["o"]["aju2"]["h"], json={})
    assert r.status_code == 409 and r.json()["detail"] == (
        f"Pengajuan kas keluar {t['number']} sudah disetujui, jadi tidak bisa dibatalkan. Batalkan kasnya "
        f"({setuju_hasil['cash_number']}) dari Transaksi Kas bila perlu."), r.text
    assert len(await _kas_pengajuan(db, t["id"])) == 1


# ═══ 11. Rute: izin, daftar, rincian, cakupan PT ═════════════════════════════════════════════════════════════════════
async def test_KB2_2_U11_rute_izin_dan_cakupan_pt(klien, db, akun, sesi, peran_tanpa_acuan):
    pt, lain = await _pt(akun, sesi, peran_tanpa_acuan), await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 1_250_000)
    asing = await _ajukan(klien, lain, 1_250_000)
    hl = pt["o"]["lihat"]["h"]
    r = await klien.get(URL_P, headers=hl)
    assert r.status_code == 200, r.text
    j = r.json()
    assert {k for k in j} >= {"items", "total", "page", "page_size", "has_more", "statuses"}
    assert [x["id"] for x in j["items"]] == [p["id"]]
    assert [s["value"] for s in j["statuses"]] == ["menunggu_persetujuan", "disetujui", "ditolak", "dibatalkan"]
    r = await klien.get(URL_P, headers=hl, params={"q": p["number"], "status": "menunggu_persetujuan"})
    assert [x["id"] for x in r.json()["items"]] == [p["id"]]
    r = await klien.get(URL_P, headers=hl, params={"status": "disetujui"})
    assert r.json()["items"] == []
    r = await klien.get(f"{URL_P}/{p['id']}", headers=hl)
    assert r.status_code == 200 and r.json()["number"] == p["number"] and r.json()["kas"] is None, r.text
    r = await klien.get(f"{URL_P}/pkk_tidak_ada", headers=hl)
    assert r.status_code == 404 and r.json()["detail"] == "Pengajuan kas keluar tidak ditemukan."
    # Izin: setujui/tolak = cash.approve; batal = cash.create (pengaju) atau cash.delete
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["aju2"]["h"])
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.approve", r.text
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=pt["o"]["aju2"]["h"], json={"alasan": "uji izin"})
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.approve", r.text
    r = await klien.post(f"{URL_P}/{p['id']}/cancel", headers=hl, json={})
    assert r.status_code == 403, r.text
    r = await klien.post(URL, headers=hl, json=_isi(pt, 1_250_000))
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.create", r.text
    # PT lain: tidak terlihat, tidak bisa diputus
    r = await klien.get(f"{URL_P}/{asing['id']}", headers=hl)
    assert r.status_code in (403, 404), r.text
    for aksi, isi in (("approve", None), ("reject", {"alasan": "uji PT lain"}), ("cancel", {})):
        r = await klien.post(f"{URL_P}/{asing['id']}/{aksi}", headers=pt["o"]["setuju"]["h"], json=isi)
        assert r.status_code in (403, 404), (aksi, r.text)
    assert (await db.cash_out_requests.find_one({"id": asing["id"]}))["status"] == "menunggu_persetujuan"
    r = await klien.get(URL_P, headers=hl, params={"entity_id": lain["id"]})
    assert r.status_code == 403 or r.json()["items"] == [], r.text


# ═══ 12. Kas ditolak di tengah terbit → tetap menunggu (terbit_error), Setujui lagi tanpa kas ganda ══════════════════
async def test_KB2_2_U12_terbit_terhenti_diulang(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch):
    from services import cash_ledger
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 2_200_000)
    asli = cash_ledger.create_cash

    async def _palsu(**kw):
        raise cash_ledger.CashRejected("Rekening BCA baru saja dinonaktifkan.")

    monkeypatch.setattr(cash_ledger, "create_cash", _palsu)
    e = await _ditolak(cors.setujui(p["id"], PENYETUJU), 409)
    assert e.detail == (f"Kas pengajuan {p['number']} belum terbit: Rekening BCA baru saja dinonaktifkan. "
                        "Pengajuan tetap menunggu; ulangi lewat Setujui atau batalkan pengajuan ini."), e.detail
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert (d["status"], d["terbit_error"], d.get("saga_lock")) == (
        "menunggu_persetujuan", "Rekening BCA baru saja dinonaktifkan.", None)
    monkeypatch.setattr(cash_ledger, "create_cash", asli)
    hasil = await cors.setujui(p["id"], PENYETUJU)
    assert (hasil["status"], hasil["terbit_error"]) == ("disetujui", "")
    assert len(await _kas_pengajuan(db, p["id"])) == 1


# ═══ 13. Rekening dinonaktifkan / kategori ditutup sesudah diajukan → Setujui ditolak berkalimat ════════════════════
async def test_KB2_2_U13_periksa_ulang_rekening_dan_kategori(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 1_900_000, rek="KT")
    await db.bank_accounts.update_one({"id": pt["rek"]["KT"]}, {"$set": {"is_active": False, "status": "inactive"}})
    try:
        e = await _ditolak(cors.setujui(p["id"], PENYETUJU), 409)
        assert "bukan rekening aktif" in e.detail and e.detail.endswith(f"Pengajuan {p['number']} tetap menunggu."), \
            e.detail
    finally:
        await db.bank_accounts.update_one({"id": pt["rek"]["KT"]}, {"$set": {"is_active": True, "status": "active"}})
    q = await _ajukan(klien, pt, 1_900_000)
    await db.cash_out_requests.update_one({"id": q["id"]}, {"$set": {"category": "pembelian"}})   # data lama
    e = await _ditolak(cors.setujui(q["id"], PENYETUJU), 409)
    assert e.detail.startswith("Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual"), e.detail
    for x in (p, q):
        assert (await db.cash_out_requests.find_one({"id": x["id"]}))["status"] == "menunggu_persetujuan"
        assert await _kas_pengajuan(db, x["id"]) == []


# ═══ 14. Katalog, penomoran, indeks, cakupan PT ══════════════════════════════════════════════════════════════════════
async def test_KB2_2_U14_katalog_nomor_indeks(aplikasi):
    import config_registry as registry
    import doc_number_kinds
    import indexes
    from config_catalog_kontrol import AKSI_BY_ID
    from entity_scope import SCOPED_COLLECTIONS
    a = AKSI_BY_ID["kas_keluar_manual"]
    assert (a["kelompok"], a["awal"], a["punya_nominal"], a["bagian"]) == ("C", "1", True, "Buku besar")
    assert a["titik"] == ("routers/cash.py:create_cash_transaction", "services/cash_out_request_service.py:setujui")
    assert registry.require("kontrol.kas_keluar_manual.min_orang")["default"] == "1"
    b = registry.require("kontrol.kas_keluar_manual.batas_nominal")
    assert (b["default"], b["min"], b["unit"]) == (1000000, 0, "Rp")
    assert "kas_keluar_manual" in registry.require("kontrol.admin_tetap_dua_orang")["default"]
    k = next(x for x in doc_number_kinds.KINDS_LIST if x["kind"] == "pkk")
    assert (k["collection"], k["field"], k["identity_prefix"]) == ("cash_out_requests", "number", "PKK-")
    assert ("cash_out_requests", "number") in indexes.UNIQUE_DOC_NUMBER_FIELDS
    assert "cash_out_requests" in indexes.ID_INDEX_COLLECTIONS
    ix = next(i for i in indexes.REQUIRED_UNIQUE_INDEXES if i["name"] == "uq_cor_idem_key")
    assert ix["collection"] == "cash_out_requests" and ix["keys"] == [("entity_id", 1), ("idempotency_key", 1)]
    assert "cash_out_requests" in SCOPED_COLLECTIONS
    from idempotency import is_idempotent_path
    assert is_idempotent_path("/api/cash-out-requests/pkk_x/approve")


# ═══ 15. Gelombang perbaikan akhir (R1) — kiriman ulang berkunci sama berbalapan dengan anulir kas lamanya ══════════
def _anulir_di_sela(db, monkeypatch, kas_id: str) -> dict:
    """Anulir kas `kas_id` tepat di dalam `create_cash`: panggilan `periksa_rekening` KEDUA milik `create_cash` (yang
    pertama milik rute) — sela antara pencocokan kas lama di rute dan pencarian id kas di `create_cash`."""
    from services import cash_ledger as cl
    asli, hit = cl.periksa_rekening, {"n": 0}

    async def _palsu(*a, **k):
        hit["n"] += 1
        if hit["n"] == 2:
            await db.cash_transactions.update_one({"id": kas_id}, {"$set": {"status": "void"}})
        return await asli(*a, **k)

    monkeypatch.setattr(cl, "periksa_rekening", _palsu)
    return hit


@pytest.mark.parametrize("tanpa_sidik", [False, True], ids=["bersidik", "kas_lama_tanpa_sidik"])
async def test_KB2_2_U15a_kirim_ulang_berbalapan_anulir_tidak_membuat_kas_baru(
        klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch, tanpa_sidik):
    """Kas keluar langsung Rp 800.000 (batas lama), batas PT diturunkan ke Rp 500.000, lalu kunci yang sama dikirim
    ulang sementara kas lamanya dianulir di sela → 409 "sudah dibatalkan", BUKAN kas keluar baru di atas batas tanpa
    orang kedua (dulu: id generasi berikutnya `…#2`, terjurnal, nol pengajuan). Kas lama tanpa sidik dicocokkan per
    isi."""
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    kunci = f"kb22-u15a-{int(tanpa_sidik)}"
    r = await _kirim(klien, pt, 800_000, kunci=kunci)
    assert r.status_code == 200, r.text
    kas_id, nomor = r.json()["id"], r.json()["number"]
    if tanpa_sidik:
        await db.cash_transactions.update_one({"id": kas_id}, {"$unset": {"sidik_kiriman": ""}})
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 500_000, pt["id"])
    jurnal0 = await db.journal_entries.count_documents({"entity_id": pt["id"]})
    hit = _anulir_di_sela(db, monkeypatch, kas_id)
    r = await klien.post(URL, headers={**pt["o"]["aju2"]["h"], "Idempotency-Key": kunci}, json=_isi(pt, 800_000))
    assert hit["n"] == 2, hit                       # anulir benar-benar terjadi di dalam `create_cash`
    assert r.status_code == 409 and r.json()["detail"] == (
        f"Transaksi kas {nomor} untuk transaksi manual ini sudah dibatalkan. Muat ulang lalu periksa."), r.text
    assert await db.cash_transactions.count_documents(
        {"ref_type": "manual", "ref_id": kunci, "status": {"$ne": "void"}}) == 0
    assert await _keluar_berkunci(db, kunci) == 1   # hanya kas lama (dianulir)
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 0
    assert await db.journal_entries.count_documents({"entity_id": pt["id"]}) == jurnal0
    # Kiriman ulang berikutnya (rekaman penyangga lain: PT dari isian) → kas lama sudah dibatalkan → pengajuan (orang
    # kedua), tetap bukan kas langsung.
    h = {**{k: v for k, v in pt["o"]["aju2"]["h"].items() if k != "X-Entity-Id"}, "Idempotency-Key": kunci}
    r = await klien.post(URL, headers=h, json={**_isi(pt, 800_000), "entity_id": pt["id"]})
    assert r.status_code == 202 and r.json()["request"]["status"] == "menunggu_persetujuan", r.text
    assert await _keluar_berkunci(db, kunci) == 1


# ═══ 15b. Minor 1 — id pengajuan dan kunci klien tidak boleh bertabrakan (awalan `pkk_` milik id pengajuan) ═════════
async def test_KB2_2_U15b_kunci_id_pengajuan_menunggu_ditolak(klien, db, akun, sesi, peran_tanpa_acuan):
    """(B) Kunci = id pengajuan MENUNGGU: dulu kas kecil keluar/masuk ber-`ref_id` pengajuan itu tercatat, sehingga
    Setujui (409 "sudah tercatat dengan nominal Rp 10.000"), Tolak, dan Batal macet. Kini kunci berawalan `pkk_` ditolak
    400 sebelum pemeriksaan apa pun: tanpa kas, tanpa pengajuan; pengajuannya tetap bisa disetujui."""
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 3_000_000, kunci="kb22-u15b-menunggu")
    assert p["id"].startswith("pkk_")
    sebelum = await _potret(klien, db, pt)
    for arah, siapa in (("out", "aju2"), ("in", "aju")):   # satu orang per arah: rekaman penyangga idempotensi sendiri
        for kunci in (p["id"], "pkk_" + "0" * 12, "  PKK_lain  "):
            r = await _kirim(klien, pt, 10_000, siapa=siapa, kunci=kunci, arah=arah)
            assert r.status_code == 400 and r.json()["detail"] == cors.PESAN_KUNCI_DICADANGKAN, (arah, kunci, r.text)
    assert cors.PESAN_KUNCI_DICADANGKAN == (
        'Kunci idempotensi berawalan "pkk_" dipakai untuk id pengajuan kas keluar. Kirim ulang dengan kunci lain.')
    assert await _potret(klien, db, pt) == sebelum
    assert await _kas_pengajuan(db, p["id"]) == []
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 1
    # Pengajuan tidak macet: Setujui menuntaskannya dengan kas pengajuan sendiri.
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200 and r.json()["status"] == "disetujui" and r.json()["terbit_error"] == "", r.text
    assert [t["id"] for t in await _kas_pengajuan(db, p["id"])] == [r.json()["cash_id"]]


async def test_KB2_2_U15c_kunci_id_pengajuan_disetujui_ditolak(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch):
    """(E, varian R1 tanpa batas yang diturunkan) Kunci = id pengajuan DISETUJUI, isi sama: dulu dicocokkan ke kas
    pengajuannya (kas yang sama), dan bila kas itu dianulir di sela terbit kas langsung Rp 3.000.000 tanpa orang kedua
    (tanpa nomor PKK, pengajuan menunjuk kas yang dianulir). Kini ditolak 400 — tanpa maupun dengan anulir di sela."""
    from services import cash_out_request_service as cors
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 3_000_000, kunci="kb22-u15c")
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200, r.text
    kas_id = r.json()["cash_id"]
    # Kunci id pengajuan yang sudah disetujui, isi sama: ditolak — tanpa anulir maupun dengan anulir di sela.
    # Tanpa X-Entity-Id (PT dari isian) = rekaman penyangga idempotensi baru: yang menjawab rute, bukan rekaman lama.
    isi = {**_isi(pt, 3_000_000, description=p["description"]), "entity_id": pt["id"]}

    def _tanpa_entitas(siapa):
        return {**{k: v for k, v in pt["o"][siapa]["h"].items() if k != "X-Entity-Id"}, "Idempotency-Key": p["id"]}

    hit = _anulir_di_sela(db, monkeypatch, kas_id)
    r = await klien.post(URL, headers=_tanpa_entitas("aju"), json=isi)
    assert r.status_code == 400 and r.json()["detail"] == cors.PESAN_KUNCI_DICADANGKAN, r.text
    assert hit["n"] == 0                              # ditolak sebelum rekening diperiksa: tidak ada sela
    monkeypatch.undo()
    r = await klien.post(URL, headers=_tanpa_entitas("aju2"), json=isi)
    assert r.status_code == 400 and r.json()["detail"] == cors.PESAN_KUNCI_DICADANGKAN, r.text
    assert [t["id"] for t in await _kas_pengajuan(db, p["id"])] == [kas_id]
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert (d["status"], d["cash_id"]) == ("disetujui", kas_id)
    assert (await db.cash_transactions.find_one({"id": kas_id}))["status"] == "posted"


# ═══ 16. Minor 6 (T2-M3) — Setujui dengan jurnal gagal: kas tetap tercatat (Posting Gagal), pengajuan disetujui ═════
async def test_KB2_2_U16_setujui_jurnal_gagal_kas_tetap_tercatat(
        klien, db, akun, sesi, peran_tanpa_acuan, paksa_jurnal_gagal):
    from services import cash_ledger
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 3_000_000, kunci="kb22-u16")
    jurnal0 = await db.journal_entries.count_documents({"entity_id": pt["id"]})
    async with paksa_jurnal_gagal("akun", entity_id=pt["id"], kode_akun=OPERASIONAL):
        r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200, r.text
    j = r.json()
    [kas] = await _kas_pengajuan(db, p["id"])
    assert (j["status"], j["cash_id"], j["cash_number"], j["terbit_error"]) == (
        "disetujui", kas["id"], kas["number"], "")
    assert (kas["status"], kas["gl_status"], kas["amount"]) == ("posted", "failed", 3_000_000.0) and kas["gl_error"]
    assert j["kas"]["gl_status"] == "failed" and j["kas"]["journal_number"] == ""
    d = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
    assert d.get("saga_lock") is None and d["status"] == "disetujui"
    assert await db.journal_entries.count_documents({"entity_id": pt["id"]}) == jurnal0
    # Ulang posting (akun dipulihkan) → jurnal kas terbit; pengajuan menampilkan jurnalnya, tanpa kas kedua.
    await cash_ledger.ensure_posted(kas["id"])
    r = await klien.get(f"{URL_P}/{p['id']}", headers=pt["o"]["lihat"]["h"])
    assert r.json()["kas"]["gl_status"] == "posted" and r.json()["kas"]["journal_number"], r.text
    assert len(await _kas_pengajuan(db, p["id"])) == 1


# ═══ 17. Important 2 — kunci saga yang menggantung (proses mati di tengah Setujui) bisa dilepas di Kunci Saga ════════
async def test_KB2_2_U17_kunci_menggantung_dilepas_lewat_kunci_saga(
        klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from routers.saga_locks import LOCKED_COLLECTIONS
    from services import atomic_claim, cash_ledger, saga_lock_watch
    from services import cash_out_request_service as cors
    for koleksi in ("cash_out_requests", "fund_transfers", "cash_account_cutovers"):
        assert koleksi in LOCKED_COLLECTIONS, koleksi
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 2_400_000, kunci="kb22-u17")
    # Proses mati SESUDAH kas tercatat (restart/deploy di tengah persetujuan): `finally` tidak sempat melepas kunci.
    asli = cash_ledger.create_cash

    async def _mati(**kw):
        await asli(**kw)
        raise RuntimeError("proses mati (uji)")

    async def _tanpa_lepas(*a, **k):
        return None

    monkeypatch.setattr(cash_ledger, "create_cash", _mati)
    monkeypatch.setattr(atomic_claim, "release", _tanpa_lepas)
    with pytest.raises(RuntimeError):
        await cors.setujui(p["id"], PENYETUJU)
    monkeypatch.undo()
    [kas] = await _kas_pengajuan(db, p["id"])
    lama = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    await db.cash_out_requests.update_one({"id": p["id"]}, {"$set": {"saga_lock.started_at": lama}})
    hs = pt["o"]["setuju"]["h"]
    # Layar: baris "sedang diproses"; Setujui → 409 yang menunjuk Kunci Saga
    r = await klien.get(URL_P, headers=hs, params={"status": "menunggu_persetujuan"})
    assert [x["dalam_proses"] for x in r.json()["items"] if x["id"] == p["id"]] == [True], r.text
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=hs)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SAGA_IN_PROGRESS", r.text
    assert "Pengaturan › Kunci Saga" in r.json()["detail"]["message"]
    # Kunci Saga: terlihat (dengan nomor PKK), dipantau, efek hilir (kas pengajuan) terlihat saat diperiksa
    r = await klien.get("/api/saga-locks", headers=kepala_admin)
    assert r.status_code == 200, r.text
    baris = [x for x in r.json() if x["collection"] == "cash_out_requests" and x["id"] == p["id"]]
    assert len(baris) == 1 and baris[0]["number"] == p["number"] and baris[0]["status"] == "menunggu_persetujuan"
    assert baris[0]["saga_lock"]["action"] == "cash_out_request_issue"
    macet = await saga_lock_watch.stuck_locks(10)
    assert [(x["collection"], x["entity_id"]) for x in macet if x["id"] == p["id"]] == [("cash_out_requests", pt["id"])]
    r = await klien.get(f"/api/saga-locks/cash_out_requests/{p['id']}/inspect", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["active"] is False, r.text
    assert {"collection": "cash_transactions", "count": 1, "samples": [kas["number"]]} in r.json()["effects"], r.json()
    r = await klien.post(f"/api/saga-locks/cash_out_requests/{p['id']}/release", headers=kepala_admin,
                         json={"reason": "uji KB22 proses mati di tengah"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SAGA_EFFECTS_PRESENT", r.text
    r = await klien.post(f"/api/saga-locks/cash_out_requests/{p['id']}/release", headers=kepala_admin,
                         json={"reason": "uji KB22 proses mati di tengah", "acknowledge_effects": True})
    assert r.status_code == 200 and r.json()["released"] is True, r.text
    # Sesudah dilepas: Setujui lagi menuntaskan pengajuan dengan kas yang SAMA (tanpa kas ganda)
    r = await klien.get(URL_P, headers=hs, params={"status": "menunggu_persetujuan"})
    assert [x["dalam_proses"] for x in r.json()["items"] if x["id"] == p["id"]] == [False], r.text
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=hs)
    assert r.status_code == 200 and r.json()["status"] == "disetujui" and r.json()["cash_id"] == kas["id"], r.text
    assert [t["id"] for t in await _kas_pengajuan(db, p["id"])] == [kas["id"]]
    # Kas & Bank 1: Pindah Dana dan Pindah Saldo Kas per Rekening ikut terlihat dan bisa dilepas
    for koleksi, did in (("fund_transfers", "ft_uji_kb22_u17"), ("cash_account_cutovers", "cut_uji_kb22_u17")):
        await db[koleksi].insert_one({"id": did, "number": f"UJI/{koleksi}", "status": "menunggu",
                                      "entity_id": pt["id"],
                                      "saga_lock": {"action": "uji", "by": "uji", "started_at": lama, "token": "lk_u"}})
        r = await klien.get("/api/saga-locks", headers=kepala_admin)
        assert [x["id"] for x in r.json() if x["collection"] == koleksi] == [did], r.text
        r = await klien.post(f"/api/saga-locks/{koleksi}/{did}/release", headers=kepala_admin,
                             json={"reason": "uji KB22 kunci menggantung"})
        assert r.status_code == 200, r.text
        assert "saga_lock" not in (await db[koleksi].find_one({"id": did}))


# ═══ 18. Minor 2 — Unduh CSV "Semua hasil filter" (`fetchAll`, page_size = MAX_PAGE_SIZE 200) tidak lagi 422 ═════════
async def test_KB2_2_U18_daftar_menerima_ukuran_halaman_unduh(klien, db, akun, sesi, peran_tanpa_acuan):
    from pagination import MAX_PAGE_SIZE
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 3_000_000, kunci="kb22-u18")
    hl = pt["o"]["lihat"]["h"]
    for url in (URL_P, "/api/fund-transfers"):
        r = await klien.get(url, headers=hl, params={"status": "menunggu_persetujuan", "entity_id": pt["id"],
                                                     "page": 1, "page_size": MAX_PAGE_SIZE})
        assert r.status_code == 200 and r.json()["page_size"] == MAX_PAGE_SIZE, (url, r.text)
        r = await klien.get(url, headers=hl, params={"page": 1, "page_size": MAX_PAGE_SIZE + 1})
        assert r.status_code == 422, (url, r.text)
    r = await klien.get(URL_P, headers=hl, params={"status": "menunggu_persetujuan", "page_size": MAX_PAGE_SIZE})
    assert [x["id"] for x in r.json()["items"]] == [p["id"]] and r.json()["has_more"] is False
