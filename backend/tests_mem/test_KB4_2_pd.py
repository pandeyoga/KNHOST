"""Kas & Bank 4 Tugas 2 (C7) — **pemegang** PD, batas PD terbuka per pemegang (`kas.pd_terbuka_maks`), **Batalkan PD**,
**tenggat LPJ** (`kas.lpj_tenggat_hari`, dipotret saat cair) dan pengingatnya (antrean Meja Keuangan, pemberitahuan H-1 &
lewat ke pembuat PD).

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.1, §5.2, §6, §7 (1–5) dan §7.9 (3–5).

Persiapan (FIXTURE kecuali disebut ALUR):
  * Rekening Kas Kecil `ent_ksc` & `ent_kanda` disisipkan langsung; karyawan HR disisipkan ke `hr_employees`.
  * Peran uji (`peran_tanpa_acuan`): Staf (buat/ubah/ajukan PD), Finance (sama — mengetik PD untuk karyawan), Penolak
    (`cash_advance.reject`), Pembuat lain (`cash_advance.create` saja), Lihat (`cash_advance.view` saja).
  * PD "lain" milik pemegang (dalam persetujuan / disetujui / cair / tuntas, PD lama tanpa `pemegang`) disisipkan
    langsung; LPJ terjurnal ber-sisa disisipkan langsung bila perlu.
  * ALUR: buat draf, ubah, ajukan, Batalkan, cairkan, LPJ (buat/ajukan/tolak/setujui), kembalikan sisa, bayar reimburse
    lewat API; daftar & rincian PD lewat API; antrean meja & penjadwal lewat layanan.
  * Penanda aktif tenggat (`system_settings.__migrations__`) dan `lpj_jatuh_tempo` PD digeser langsung (FIXTURE) untuk uji
    tenggat, antrean, dan pemberitahuan.

Hitung tangan tenggat: PD cair hari H (tanggal buku) → LPJ jatuh tempo H + 7; lewat mulai H + 8 (hari lewat = hari ini −
jatuh tempo). PD lama cair 30 hari lalu tanpa potret, fitur aktif hari ini → jatuh tempo hari ini + 7 (aman); fitur aktif
10 hari lalu → jatuh tempo 3 hari lalu (lewat 3 hari).
"""
from __future__ import annotations

import asyncio
import itertools
import uuid
from datetime import date, timedelta

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI
from services.book_date import tanggal_buku, tanggal_panjang

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
REK = {KSC: "rek_kb42_kk_ksc", KANDA: "rek_kb42_kk_kanda"}
HARI_INI = tanggal_buku()
K_MAKS, K_TENGGAT = "kas.pd_terbuka_maks", "kas.lpj_tenggat_hari"
KAR_A = {"id": "emp_kb42_a", "code": "KB42-A", "name": "Andi Sopir KB42"}
KAR_B = {"id": "emp_kb42_b", "code": "KB42-B", "name": "Budi Gudang KB42"}
KAR_KANDA = {"id": "emp_kb42_c", "code": "KB42-C", "name": "Citra Kanda KB42"}
KAR_KELUAR = {"id": "emp_kb42_d", "code": "KB42-D", "name": "Dedi Keluar KB42"}
PESAN_ALASAN_BATAL = "Alasan pembatalan wajib diisi (minimal 5 huruf)."
_urut = itertools.count(1)
_PERAN: dict = {}


def _tgl(n: int) -> str:
    return (date.fromisoformat(HARI_INI) + timedelta(days=n)).isoformat()


def _iso_hari(n: int) -> str:
    return f"{_tgl(n)}T03:00:00+00:00"


@pytest.fixture(scope="module", autouse=True)
def _peran_segar(klien):
    _PERAN.clear()
    yield
    _PERAN.clear()


@pytest.fixture(scope="module")
async def siap(db):
    for eid, rid in REK.items():
        if not await db.bank_accounts.find_one({"id": rid}):
            await db.bank_accounts.insert_one({"id": rid, "name": f"Kas Kecil {eid} (uji KB4-2)", "entity_id": eid,
                                               "account_type": "cash", "cash_type": "kas_kecil", "is_active": True})
    for k, eid, status in ((KAR_A, KSC, "active"), (KAR_B, KSC, "active"), (KAR_KANDA, KANDA, "active"),
                           (KAR_KELUAR, KSC, "resigned")):
        if not await db.hr_employees.find_one({"id": k["id"]}):
            await db.hr_employees.insert_one({**k, "entity_id": eid, "status": status, "created_at": now_iso()})
    return True


async def _peran(peran_tanpa_acuan, nama: str, izin: dict) -> str:
    if nama not in _PERAN:
        _PERAN[nama] = await peran_tanpa_acuan(izin, label=f"KB42 {nama}")
    return _PERAN[nama]


IZIN = {
    "staf": {"cash_advance": ["view", "create", "update", "submit"]},
    "finance": {"cash_advance": ["view", "create", "update", "submit"]},
    "penolak": {"cash_advance": ["view", "reject"]},
    "pembuat_lain": {"cash_advance": ["view", "create"]},
    "lihat": {"cash_advance": ["view"]},
}


async def _orang(akun, sesi, peran_tanpa_acuan, jenis: str, *, entitas=(KSC,), aktif: str = KSC):
    u = await akun(await _peran(peran_tanpa_acuan, jenis, IZIN[jenis]), entitas=entitas)
    return u, await sesi(u, entitas=aktif)


def _h(h: dict, eid: str) -> dict:
    return {**h, "X-Entity-Id": eid}


async def _draf(klien, h, nilai: float = 1_000_000, *, pemegang=None, entity: str = ""):
    body = {"kegiatan": "uji KB4-2", "divisi": "Umum", "payment_method": "cash",
            "lines": [{"description": "uang muka", "qty": 1, "unit_price": nilai}]}
    if pemegang is not None:
        body["pemegang"] = pemegang
    if entity:
        body["entity_id"] = entity
    r = await klien.post("/api/cash-advances", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _ajukan(klien, h, ca_id: str):
    return await klien.post(f"/api/cash-advances/{ca_id}/submit", headers=h)


async def _sisip(db, *, status: str, nilai: float = 1_000_000, pemegang=None, pembuat=None, entity: str = KSC,
                 jatuh_tempo: str = "", disbursed_at: str = "", tanpa_pemegang: bool = False) -> dict:
    """FIXTURE: PD berstatus `status` disisipkan langsung. `pemegang` = {jenis,id,nama}; `pembuat` = pengguna {id,name}."""
    p = pembuat or {"id": f"usr_kb42_{uuid.uuid4().hex[:6]}", "name": "Pembuat KB42"}
    ca = f"ca_kb42_{uuid.uuid4().hex[:8]}"
    doc = {"id": ca, "number": f"PD-KB42-{next(_urut):03d}", "entity_id": entity, "status": status,
           "kegiatan": "uji KB4-2", "divisi": "Umum",
           "lines": [{"description": "uang muka", "qty": 1, "unit_price": nilai, "amount": nilai}],
           "total_amount": float(nilai), "approvals": [], "payment_method": "cash",
           "created_by": p["name"], "created_by_id": p["id"], "created_at": now_iso(), "updated_at": now_iso()}
    if not tanpa_pemegang:
        doc["pemegang"] = pemegang or {"jenis": "pengguna", "id": p["id"], "nama": p["name"]}
    if status in ("disbursed", "settled"):
        doc["disbursement"] = {"cash_txn_id": "", "amount": float(nilai), "cash_type": "kas_kecil",
                               "disbursed_at": disbursed_at or now_iso(), "disbursed_by": "Uji"}
        if jatuh_tempo:
            doc["lpj_jatuh_tempo"] = jatuh_tempo
    await db.cash_advances.insert_one(doc)
    return doc


async def _lpj_terjurnal(db, pd: dict, *, sisa: float, status_sisa: str = "open") -> dict:
    """FIXTURE: LPJ terjurnal atas `pd` (PD → settled) dengan sisa uang muka `sisa` berstatus `status_sisa`."""
    sid = f"stl_kb42_{uuid.uuid4().hex[:8]}"
    total = float(pd["total_amount"]) - sisa
    await db.cash_advance_settlements.insert_one({
        "id": sid, "number": f"STL-KB42-{next(_urut):03d}", "entity_id": pd["entity_id"], "cash_advance_id": pd["id"],
        "cash_advance_number": pd["number"], "status": "posted_to_gl", "total_pengeluaran": total,
        "total_pettycash": float(pd["total_amount"]), "category_totals": {"transportasi": total},
        "hutang_reimburse": {"amount": 0, "status": "none"},
        "sisa_dikembalikan": {"amount": sisa, "status": status_sisa if sisa > 0 else "none"},
        "created_at": now_iso()})
    await db.cash_advances.update_one({"id": pd["id"]}, {"$set": {"status": "settled", "settled_by_stl_id": sid}})
    return {"id": sid}


async def _setel(klien, kepala, key: str, value, eid: str):
    r = await klien.put("/api/config/values", headers=kepala, json={"items": [
        {"key": key, "value": value, "scope_type": "entity", "scope_id": eid, "reason": "uji KB4-2"}]})
    assert r.status_code == 200, r.text


async def _pulihkan(klien, kepala, key: str, eid: str):
    r = await klien.post("/api/config/values/clear", headers=kepala, json={
        "key": key, "scope_type": "entity", "scope_id": eid, "reason": "pulihkan uji KB4-2"})
    assert r.status_code == 200, r.text


def _tertahan(subjek: str, pd: dict, rincian: str, suruhan: str, akhir: str = "sebelum mengajukan uang muka baru.",
              lain: int = 0) -> str:
    tambah = f" dan {lain} PD lain" if lain else ""
    return f"{subjek} masih memegang uang muka {pd['number']} ({rincian}){tambah}. {suruhan} {akhir}"


async def _cair(klien, kepala, ca_id: str, eid: str = KSC, tanggal: str = ""):
    return await klien.post(f"/api/cash-advances/{ca_id}/disburse", headers=_h(kepala, eid),
                            json={"cash_type": "kas_kecil", "account_id": REK[eid], "note": "uji KB4-2",
                                  "txn_date": tanggal})


async def _setujui_semua(klien, kepala, ca_id: str, eid: str = KSC) -> dict:
    """ALUR: setujui tiap jenjang Aturan Persetujuan sampai `approved`."""
    for _ in range(5):
        r = await klien.get(f"/api/cash-advances/{ca_id}", headers=_h(kepala, eid))
        if r.json()["status"] == "approved":
            return r.json()
        r = await klien.post(f"/api/cash-advances/{ca_id}/approve", headers=_h(kepala, eid), json={"note": "ok"})
        assert r.status_code == 200, r.text
    raise AssertionError("PD tidak sampai approved")


# ═══ 1. Ajukan PD kedua: PD pertama terbuka → 409; draf boleh; PD pertama selesai → lolos ═════════════════════════
async def test_KB4_2_U1_ajukan_kedua_tertahan_selama_pd_pertama_terbuka(klien, db, akun, sesi, peran_tanpa_acuan, siap):
    u, h = await _orang(akun, sesi, peran_tanpa_acuan, "staf")
    saya = {"id": u["id"], "name": u["name"]}
    draf = await _draf(klien, h, 250_000)                                     # draf kedua boleh disimpan
    assert draf["status"] == "draft"
    assert draf["pemegang"] == {"jenis": "pengguna", "id": u["id"], "nama": u["name"]}
    jt = _tgl(4)
    kasus = [
        ("pending_atasan", {}, "Rp 1.000.000, menunggu persetujuan", "Selesaikan atau batalkan PD itu dulu"),
        ("pending_finance", {}, "Rp 1.000.000, menunggu persetujuan", "Selesaikan atau batalkan PD itu dulu"),
        ("approved", {}, "Rp 1.000.000, disetujui, belum dicairkan", "Selesaikan atau batalkan PD itu dulu"),
        ("disbursed", {"jatuh_tempo": jt}, f"Rp 1.000.000, LPJ jatuh tempo {tanggal_panjang(jt)}",
         "Selesaikan LPJ-nya dulu"),
    ]
    for status, extra, rincian, suruhan in kasus:
        pertama = await _sisip(db, status=status, pembuat=saya, **extra)
        r = await _ajukan(klien, h, draf["id"])
        assert r.status_code == 409, (status, r.text)
        assert r.json()["detail"] == _tertahan("Anda", pertama, rincian, suruhan), r.json()
        # rincian draf: tombol Ajukan mati beralasan (kalimat server yang sama)
        d = (await klien.get(f"/api/cash-advances/{draf['id']}", headers=h)).json()
        assert (d["status"], d["bisa_ajukan"], d["alasan_ajukan"]) == ("draft", False, r.json()["detail"]), d
        await db.cash_advances.update_one({"id": pertama["id"]}, {"$set": {"status": "cancelled"}})
    # settled tetapi sisanya masih di tangan (open / returning) → tetap terbuka
    for status_sisa in ("open", "returning"):
        pertama = await _sisip(db, status="disbursed", pembuat=saya, jatuh_tempo=jt)
        await _lpj_terjurnal(db, pertama, sisa=150_000, status_sisa=status_sisa)
        r = await _ajukan(klien, h, draf["id"])
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _tertahan("Anda", pertama, "Rp 1.000.000, sisa Rp 150.000 belum dikembalikan",
                                               "Kembalikan sisanya dulu"), r.json()
        await db.cash_advance_settlements.update_one({"cash_advance_id": pertama["id"]},
                                                     {"$set": {"sisa_dikembalikan.status": "returned"}})
    # PD pertama batal / ditolak / tuntas (sisa kembali, tanpa sisa) / draf → tidak menahan
    for status in ("cancelled", "rejected", "draft"):
        await _sisip(db, status=status, pembuat=saya)
    tuntas = await _sisip(db, status="disbursed", pembuat=saya, jatuh_tempo=jt)
    await _lpj_terjurnal(db, tuntas, sisa=0)
    d = (await klien.get(f"/api/cash-advances/{draf['id']}", headers=h)).json()
    assert (d["bisa_ajukan"], d["alasan_ajukan"]) == (True, ""), d
    r = await _ajukan(klien, h, draf["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"].startswith("pending_")
    # draf ketiga masih boleh disimpan, tetapi tidak bisa diajukan (PD kedua sekarang dalam persetujuan)
    ketiga = await _draf(klien, h, 100_000)
    r = await _ajukan(klien, h, ketiga["id"])
    assert r.status_code == 409 and r.json()["detail"] == _tertahan(
        "Anda", draf, "Rp 250.000, menunggu persetujuan", "Selesaikan atau batalkan PD itu dulu"), r.text


async def test_KB4_2_U1b_pd_lama_tanpa_pemegang_milik_pembuatnya(klien, db, akun, sesi, peran_tanpa_acuan, siap):
    u, h = await _orang(akun, sesi, peran_tanpa_acuan, "staf")
    lama = await _sisip(db, status="disbursed", pembuat={"id": u["id"], "name": u["name"]}, tanpa_pemegang=True,
                        jatuh_tempo=_tgl(2))
    d = (await klien.get(f"/api/cash-advances/{lama['id']}", headers=h)).json()
    assert d["pemegang"] == {"jenis": "pengguna", "id": u["id"], "nama": u["name"]}, d
    assert (d["bisa_ajukan"], d["alasan_ajukan"]) == (False, "Hanya PD draft/ditolak yang bisa diajukan"), d
    draf = await _draf(klien, h, 300_000)
    r = await _ajukan(klien, h, draf["id"])
    assert r.status_code == 409 and r.json()["detail"].startswith(f"Anda masih memegang uang muka {lama['number']}")
    # tanpa tulisan isi-ulang: dokumen lama tetap tanpa bidang `pemegang`
    assert "pemegang" not in await db.cash_advances.find_one({"id": lama["id"]}, {"_id": 0})
    rows = (await klien.get("/api/cash-advances", headers=h)).json()
    baris = {x["id"]: x for x in rows}
    assert baris[lama["id"]]["pemegang"]["id"] == u["id"]
    assert (baris[lama["id"]]["lpj_jatuh_tempo"], baris[lama["id"]]["tenggat_status"]) == (_tgl(2), "aman")
    assert (baris[draf["id"]]["bisa_ajukan"], baris[draf["id"]]["lpj_jatuh_tempo"]) == (False, None)
    assert baris[draf["id"]]["alasan_ajukan"] == r.json()["detail"]


# ═══ 2. Finance mengetik PD untuk karyawan: batas per pemegang, bukan per pembuat ═══════════════════════════════════
async def test_KB4_2_U2_batas_per_karyawan_bukan_per_pembuat(klien, db, akun, sesi, peran_tanpa_acuan, siap):
    f, h = await _orang(akun, sesi, peran_tanpa_acuan, "finance")
    pa = await _draf(klien, h, 500_000, pemegang={"jenis": "karyawan", "id": KAR_A["id"]})
    assert pa["pemegang"] == {"jenis": "karyawan", "id": KAR_A["id"], "nama": KAR_A["name"]}, pa
    pb = await _draf(klien, h, 400_000, pemegang={"jenis": "karyawan", "id": KAR_B["id"]})
    for pd in (pa, pb):
        r = await _ajukan(klien, h, pd["id"])
        assert r.status_code == 200, r.text
    pa2 = await _draf(klien, h, 200_000, pemegang={"jenis": "karyawan", "id": KAR_A["id"]})
    r = await _ajukan(klien, h, pa2["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == _tertahan(KAR_A["name"], pa, "Rp 500.000, menunggu persetujuan",
                                           "Selesaikan atau batalkan PD itu dulu"), r.json()
    # PD Finance sendiri (pemegang = pembuat) tidak tertahan oleh PD karyawan yang ia ketik
    sendiri = await _draf(klien, h, 100_000)
    assert sendiri["pemegang"] == {"jenis": "pengguna", "id": f["id"], "nama": f["name"]}
    r = await _ajukan(klien, h, sendiri["id"])
    assert r.status_code == 200, r.text
    # ubah pemegang draf A → B: B masih memegang PD-nya → tertahan dengan nama B
    r = await klien.patch(f"/api/cash-advances/{pa2['id']}", headers=h,
                          json={"pemegang": {"jenis": "karyawan", "id": KAR_B["id"]}})
    assert r.status_code == 200 and r.json()["pemegang"]["nama"] == KAR_B["name"], r.text
    r = await _ajukan(klien, h, pa2["id"])
    assert r.status_code == 409 and r.json()["detail"].startswith(f"{KAR_B['name']} masih memegang uang muka "
                                                                  f"{pb['number']} "), r.text


async def test_KB4_2_U2b_pemegang_wajib_karyawan_aktif_pt_dokumen(klien, db, akun, sesi, peran_tanpa_acuan, siap):
    f, h = await _orang(akun, sesi, peran_tanpa_acuan, "finance")
    body = {"kegiatan": "uji", "payment_method": "cash", "lines": [{"description": "x", "qty": 1, "unit_price": 1000}]}
    kasus = [
        ({"jenis": "karyawan", "id": KAR_KANDA["id"]},
         f"{KAR_KANDA['name']} bukan karyawan PT ini. Pilih karyawan PT pengajuan dana ini."),
        ({"jenis": "karyawan", "id": KAR_KELUAR["id"]},
         f"{KAR_KELUAR['name']} sudah tidak aktif sebagai karyawan, jadi tidak bisa memegang uang muka."),
        ({"jenis": "karyawan", "id": "emp_tidak_ada"}, "Karyawan pemegang uang tidak ditemukan."),
        ({"jenis": "karyawan", "id": ""}, "Pilih karyawan yang memegang uang."),
        ({"jenis": "pengguna", "id": "usr_lain"},
         "Pemegang uang pengguna hanya pembuat PD sendiri. Untuk orang lain, pilih karyawan."),
        ({"jenis": "pemasok", "id": "x"}, "Pemegang uang hanya pembuat PD sendiri atau karyawan PT ini."),
    ]
    for pemegang, pesan in kasus:
        r = await klien.post("/api/cash-advances", headers=h, json={**body, "pemegang": pemegang})
        assert r.status_code == 400 and r.json()["detail"] == pesan, (pemegang, r.text)
    # pengguna dengan id dirinya sendiri sah
    r = await klien.post("/api/cash-advances", headers=h, json={**body, "pemegang": {"jenis": "pengguna",
                                                                                     "id": f["id"]}})
    assert r.status_code == 200 and r.json()["pemegang"]["id"] == f["id"], r.text


async def test_KB4_2_U2c_pemilih_karyawan_pd(klien, db, akun, sesi, peran_tanpa_acuan, siap):
    _, h = await _orang(akun, sesi, peran_tanpa_acuan, "finance")
    r = await klien.get("/api/cash-advances/karyawan", headers=h)
    assert r.status_code == 200, r.text
    ids = {x["id"] for x in r.json()}
    assert {KAR_A["id"], KAR_B["id"]} <= ids and KAR_KELUAR["id"] not in ids and KAR_KANDA["id"] not in ids
    assert next(x for x in r.json() if x["id"] == KAR_A["id"]) == {"id": KAR_A["id"], "code": KAR_A["code"],
                                                                   "name": KAR_A["name"]}
    r = await klien.get("/api/cash-advances/karyawan", headers=h, params={"q": "andi sopir"})
    assert [x["id"] for x in r.json()] == [KAR_A["id"]], r.text
    r = await klien.get("/api/cash-advances/karyawan", headers=h, params={"entity_id": KANDA})
    assert r.status_code == 403, r.text
    _, hl = await _orang(akun, sesi, peran_tanpa_acuan, "lihat")
    assert (await klien.get("/api/cash-advances/karyawan", headers=hl)).status_code == 403


# ═══ 3. Batas per PT dokumen (`kas.pd_terbuka_maks`), dihitung lintas PT untuk pengguna ═══════════════════════════
async def test_KB4_2_U3_batas_pengaturan_pt_dan_lintas_pt(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin,
                                                          siap):
    u, h = await _orang(akun, sesi, peran_tanpa_acuan, "staf", entitas=(KSC, KANDA), aktif=KANDA)
    hk = _h(h, KSC)
    await _setel(klien, kepala_admin, K_MAKS, 2, KANDA)
    try:
        p1 = await _draf(klien, h, 100_000)
        p2 = await _draf(klien, h, 200_000)
        p3 = await _draf(klien, h, 300_000)
        assert (await _ajukan(klien, h, p1["id"])).status_code == 200
        assert (await _ajukan(klien, h, p2["id"])).status_code == 200
        r = await _ajukan(klien, h, p3["id"])
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _tertahan("Anda", p1, "Rp 100.000, menunggu persetujuan",
                                               "Selesaikan atau batalkan PD itu dulu", lain=1), r.json()
        # PT lain bawaan 1: PD terbuka di KANDA ikut dihitung (pengguna lintas PT)
        pk = await _draf(klien, hk, 50_000)
        r = await _ajukan(klien, hk, pk["id"])
        assert r.status_code == 409 and r.json()["detail"].startswith("Anda masih memegang uang muka "), r.text
        # 0 = tanpa batas
        await _setel(klien, kepala_admin, K_MAKS, 0, KANDA)
        r = await _ajukan(klien, h, p3["id"])
        assert r.status_code == 200, r.text
        d = (await klien.get(f"/api/cash-advances/{pk['id']}", headers=hk)).json()
        assert d["bisa_ajukan"] is False, d     # KSC tetap bawaan 1
    finally:
        await _pulihkan(klien, kepala_admin, K_MAKS, KANDA)


# ═══ 4. Cairkan memeriksa ulang: PD lain yang dipegang (cair / sisa di tangan) → 409; disetujui saja → lolos ═══════
async def test_KB4_2_U4_cairkan_periksa_pd_yang_dipegang(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin,
                                                         siap):
    v = {"id": f"usr_kb42_v_{uuid.uuid4().hex[:6]}", "name": "Vina KB42"}
    a = await _sisip(db, status="approved", pembuat=v, nilai=300_000)
    b = await _sisip(db, status="approved", pembuat=v, nilai=200_000)
    r = await _cair(klien, kepala_admin, a["id"])                  # B hanya disetujui → tidak saling mengunci
    assert r.status_code == 200 and r.json()["status"] == "disbursed", r.text
    r = await _cair(klien, kepala_admin, b["id"])                  # A sekarang dipegang → B menunggu LPJ A
    assert r.status_code == 409, r.text
    jt_a = (await db.cash_advances.find_one({"id": a["id"]}))["lpj_jatuh_tempo"]
    assert r.json()["detail"] == _tertahan(v["name"], a, f"Rp 300.000, LPJ jatuh tempo {tanggal_panjang(jt_a)}",
                                           "Selesaikan LPJ-nya dulu", akhir=f"sebelum {b['number']} dicairkan."), r.json()
    assert (await db.cash_advances.find_one({"id": b["id"]}))["status"] == "approved"
    assert not await db.cash_transactions.find_one({"ref_type": "cash_advance", "ref_id": b["id"]})
    # A tuntas tetapi sisanya masih di tangan → tetap menahan; sisa kembali → lolos
    await _lpj_terjurnal(db, {**a, "total_amount": 300_000.0}, sisa=50_000)
    r = await _cair(klien, kepala_admin, b["id"])
    assert r.status_code == 409 and "sisa Rp 50.000 belum dikembalikan" in r.json()["detail"], r.text
    await db.cash_advance_settlements.update_one({"cash_advance_id": a["id"]},
                                                 {"$set": {"sisa_dikembalikan.status": "returned"}})
    r = await _cair(klien, kepala_admin, b["id"])
    assert r.status_code == 200, r.text
    # batas 0 di PT → cairkan tanpa memeriksa
    w = {"id": f"usr_kb42_w_{uuid.uuid4().hex[:6]}", "name": "Wawan KB42"}
    await _sisip(db, status="disbursed", pembuat=w, jatuh_tempo=_tgl(3))
    c = await _sisip(db, status="approved", pembuat=w, nilai=100_000)
    await _setel(klien, kepala_admin, K_MAKS, 0, KSC)
    try:
        assert (await _cair(klien, kepala_admin, c["id"])).status_code == 200
    finally:
        await _pulihkan(klien, kepala_admin, K_MAKS, KSC)


# ═══ 5. Bersamaan: dua ajukan / dua cairkan pemegang sama → satu lolos (kunci per pemegang) ═══════════════════════
async def test_KB4_2_U5_dua_ajukan_bersamaan_satu_lolos(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch, siap):
    from services import cash_advance_service as svc
    u, h = await _orang(akun, sesi, peran_tanpa_acuan, "staf")
    x, y = await _draf(klien, h, 100_000), await _draf(klien, h, 200_000)
    hasil = await asyncio.gather(_ajukan(klien, h, x["id"]), _ajukan(klien, h, y["id"]))
    assert sorted(r.status_code for r in hasil) == [200, 409], [r.text for r in hasil]
    assert await db.cash_advances.count_documents({"id": {"$in": [x["id"], y["id"]]}, "status": "draft"}) == 1
    # sela dipaksa: keduanya lolos pemeriksaan awal sebelum salah satunya menulis → kunci pemegang menahan yang kedua
    u2, h2 = await _orang(akun, sesi, peran_tanpa_acuan, "staf")
    x2, y2 = await _draf(klien, h2, 100_000), await _draf(klien, h2, 200_000)
    asli = svc.pd_terbuka

    async def lambat(*a, **k):
        rows = await asli(*a, **k)
        await asyncio.sleep(0.05)
        return rows
    monkeypatch.setattr(svc, "pd_terbuka", lambat)
    hasil = await asyncio.gather(_ajukan(klien, h2, x2["id"]), _ajukan(klien, h2, y2["id"]))
    assert sorted(r.status_code for r in hasil) == [200, 409], [r.text for r in hasil]
    kalah, menang = (next(r for r in hasil if r.status_code == c) for c in (409, 200))
    assert kalah.json()["detail"].startswith(f"Anda masih memegang uang muka {menang.json()['number']} "), kalah.text
    assert await db.cash_advances.count_documents({"id": {"$in": [x2["id"], y2["id"]]}, "status": "draft"}) == 1
    assert await db.cash_advance_locks.count_documents({}) == 0     # kunci dilepas


async def test_KB4_2_U5b_dua_cairkan_bersamaan_satu_lolos(klien, db, kepala_admin, monkeypatch, siap):
    from services import cash_advance_service as svc
    p = {"id": f"usr_kb42_p_{uuid.uuid4().hex[:6]}", "name": "Putri KB42"}
    a = await _sisip(db, status="approved", pembuat=p, nilai=100_000)
    b = await _sisip(db, status="approved", pembuat=p, nilai=200_000)
    asli = svc.pd_terbuka

    async def lambat(*args, **k):
        rows = await asli(*args, **k)
        await asyncio.sleep(0.05)
        return rows
    monkeypatch.setattr(svc, "pd_terbuka", lambat)
    hasil = await asyncio.gather(_cair(klien, kepala_admin, a["id"]), _cair(klien, kepala_admin, b["id"]))
    assert sorted(r.status_code for r in hasil) == [200, 409], [r.text for r in hasil]
    assert await db.cash_advances.count_documents({"id": {"$in": [a["id"], b["id"]]}, "status": "disbursed"}) == 1
    assert await db.cash_transactions.count_documents({"ref_type": "cash_advance",
                                                        "ref_id": {"$in": [a["id"], b["id"]]}}) == 1
    assert await db.cash_advance_locks.count_documents({}) == 0


# ═══ 6. Batalkan PD (belum cair) — pembuat atau `cash_advance.reject`, alasan ≥ 5 huruf ═══════════════════════════
async def test_KB4_2_U6_batalkan_pd(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin, siap):
    u, h = await _orang(akun, sesi, peran_tanpa_acuan, "staf")
    saya = {"id": u["id"], "name": u["name"]}
    draf = await _draf(klien, h, 100_000)
    r = await klien.post(f"/api/cash-advances/{draf['id']}/cancel", headers=h, json={"alasan": "abc "})
    assert r.status_code == 400 and r.json()["detail"] == PESAN_ALASAN_BATAL, r.text
    r = await klien.post(f"/api/cash-advances/{draf['id']}/cancel", headers=h, json={"alasan": "salah ketik nominal"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["status"], d["cancelled_reason"], d["cancelled_by_id"], d["cancelled_from"]) == (
        "cancelled", "salah ketik nominal", u["id"], "draft"), d
    jejak = await db.audit_logs.find_one({"action": "cash_advance_cancelled", "entity_id": draf["id"]}, {"_id": 0})
    assert jejak and jejak["after"]["alasan"] == "salah ketik nominal" and jejak["after"]["dari"] == "draft", jejak
    r = await klien.post(f"/api/cash-advances/{draf['id']}/cancel", headers=h, json={"alasan": "batal lagi saja"})
    assert r.status_code == 409 and r.json()["detail"] == f"PD {draf['number']} sudah dibatalkan.", r.text
    # dalam persetujuan (diajukan lewat API) → pembuat membatalkan
    kedua = await _draf(klien, h, 200_000)
    assert (await _ajukan(klien, h, kedua["id"])).status_code == 200
    r = await klien.post(f"/api/cash-advances/{kedua['id']}/cancel", headers=h, json={"alasan": "acara diundur"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled", r.text
    # disetujui → pemegang izin tolak (bukan pembuat) membatalkan; pembuat lain tanpa izin → 403; lihat saja → 403
    disetujui = await _sisip(db, status="approved", pembuat=saya)
    _, h_lain = await _orang(akun, sesi, peran_tanpa_acuan, "pembuat_lain")
    r = await klien.post(f"/api/cash-advances/{disetujui['id']}/cancel", headers=h_lain, json={"alasan": "bukan punya"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == (f"Hanya pembuat PD {disetujui['number']} ({u['name']}) atau pemegang izin menolak "
                                  "pengajuan dana yang bisa membatalkannya."), r.text
    _, h_lihat = await _orang(akun, sesi, peran_tanpa_acuan, "lihat")
    r = await klien.post(f"/api/cash-advances/{disetujui['id']}/cancel", headers=h_lihat, json={"alasan": "coba coba"})
    assert r.status_code == 403, r.text
    t, h_tolak = await _orang(akun, sesi, peran_tanpa_acuan, "penolak")
    r = await klien.post(f"/api/cash-advances/{disetujui['id']}/cancel", headers=h_tolak,
                         json={"alasan": "kegiatan dibatalkan"})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["cancelled_by_id"], r.json()["cancelled_from"]) == (
        "cancelled", t["id"], "approved")
    # sudah cair → 409; pernah dicoba dicairkan (kas tercatat) → 409 (pemegang izin tolak; PD milik orang lain)
    lain = {"id": f"usr_kb42_o_{uuid.uuid4().hex[:6]}", "name": "Orang Lain KB42"}
    cair = await _sisip(db, status="disbursed", pembuat=lain, jatuh_tempo=_tgl(3))
    r = await klien.post(f"/api/cash-advances/{cair['id']}/cancel", headers=h_tolak,
                         json={"alasan": "tidak jadi pakai"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"PD {cair['number']} sudah dicairkan, jadi tidak bisa dibatalkan. Selesaikan lewat "
                                  "LPJ dan kembalikan sisanya."), r.text
    coba = await _sisip(db, status="approved", pembuat=lain)
    await db.cash_transactions.insert_one({"id": "ctx_kb42_coba", "number": "KK-KB42-1", "ref_type": "cash_advance",
                                           "ref_id": coba["id"], "direction": "out", "status": "posted",
                                           "gl_status": "failed", "entity_id": KSC, "amount": 1_000_000})
    r = await klien.post(f"/api/cash-advances/{coba['id']}/cancel", headers=h_tolak,
                         json={"alasan": "tidak jadi pakai"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"PD {coba['number']} sudah punya kas pencairan KK-KB42-1, jadi tidak bisa "
                                  "dibatalkan. Ulangi pencairannya, lalu selesaikan lewat LPJ."), r.text
    # PD yang dibatalkan tidak dihitung terbuka
    baru = await _draf(klien, h, 100_000)
    assert (await _ajukan(klien, h, baru["id"])).status_code == 200


# ═══ 7. Tenggat LPJ: dipotret saat cair; PD lama dari waktu fitur aktif; LPJ diajukan = terpenuhi ═══════════════════
async def test_KB4_2_U7_tenggat_dipotret_saat_cair(klien, db, kepala_admin, siap):
    v = {"id": f"usr_kb42_t_{uuid.uuid4().hex[:6]}", "name": "Tono KB42"}
    a = await _sisip(db, status="approved", pembuat=v, nilai=400_000)
    r = await _cair(klien, kepala_admin, a["id"], tanggal=HARI_INI)
    assert r.status_code == 200, r.text
    assert (r.json()["lpj_jatuh_tempo"], r.json()["lpj_tenggat_hari"]) == (_tgl(7), 7), r.json()
    d = (await klien.get(f"/api/cash-advances/{a['id']}", headers=kepala_admin)).json()
    assert (d["lpj_jatuh_tempo"], d["tenggat_status"], d["tenggat_hari_lewat"]) == (_tgl(7), "aman", 0), d
    # pengaturan berubah sesudahnya tidak menggeser tenggat PD yang sudah cair; PD berikutnya memakai nilai baru
    await _setel(klien, kepala_admin, K_TENGGAT, 14, KSC)
    try:
        d = (await klien.get(f"/api/cash-advances/{a['id']}", headers=kepala_admin)).json()
        assert d["lpj_jatuh_tempo"] == _tgl(7), d
        w = {"id": f"usr_kb42_t2_{uuid.uuid4().hex[:6]}", "name": "Tini KB42"}
        b = await _sisip(db, status="approved", pembuat=w, nilai=100_000)
        r = await _cair(klien, kepala_admin, b["id"], tanggal=HARI_INI)
        assert (r.json()["lpj_jatuh_tempo"], r.json()["lpj_tenggat_hari"]) == (_tgl(14), 14), r.json()
    finally:
        await _pulihkan(klien, kepala_admin, K_TENGGAT, KSC)


async def test_KB4_2_U7b_pd_lama_dari_waktu_fitur_aktif(klien, db, kepala_admin, siap):
    from services import cash_advance_service as svc
    sejak = await svc.ensure_tenggat_aktif_sejak()      # ditulis saat backend menyala (lifespan uji)
    assert sejak and tanggal_buku(sejak) == HARI_INI
    assert await svc.ensure_tenggat_aktif_sejak() == sejak                     # sekali tulis
    v = {"id": f"usr_kb42_l_{uuid.uuid4().hex[:6]}", "name": "Lama KB42"}
    lama = await _sisip(db, status="disbursed", pembuat=v, disbursed_at=_iso_hari(-30))   # cair sebelum fitur aktif
    t = await svc.tenggat(lama)
    assert t == {"jatuh_tempo": _tgl(7), "status": "aman", "hari_lewat": 0}, t   # tidak lewat di hari pembaruan
    assert "lpj_jatuh_tempo" not in await db.cash_advances.find_one({"id": lama["id"]}, {"_id": 0})
    penanda = {"scope": "__migrations__"}
    await db.system_settings.update_one(penanda, {"$set": {svc.PENANDA_TENGGAT_AKTIF: _iso_hari(-10)}})
    try:
        assert await svc.tenggat(lama) == {"jatuh_tempo": _tgl(-3), "status": "lewat", "hari_lewat": 3}
        baru = await _sisip(db, status="disbursed", pembuat=v, disbursed_at=_iso_hari(-1))
        assert (await svc.tenggat(baru))["jatuh_tempo"] == _tgl(6)               # max(cair, aktif) + 7
    finally:
        await db.system_settings.update_one(penanda, {"$set": {svc.PENANDA_TENGGAT_AKTIF: sejak}})


async def test_KB4_2_U7c_lpj_diajukan_memenuhi_ditolak_dihitung_lagi(klien, db, kepala_admin, siap):
    from services import cash_advance_service as svc
    v = {"id": f"usr_kb42_s_{uuid.uuid4().hex[:6]}", "name": "Sari KB42"}
    pd = await _sisip(db, status="disbursed", pembuat=v, jatuh_tempo=_tgl(-2))
    assert await svc.tenggat(pd) == {"jatuh_tempo": _tgl(-2), "status": "lewat", "hari_lewat": 2}
    besok = await _sisip(db, status="disbursed", pembuat=v, jatuh_tempo=_tgl(1))
    assert (await svc.tenggat(besok))["status"] == "jatuh_tempo_besok"
    hari_ini = await _sisip(db, status="disbursed", pembuat=v, jatuh_tempo=HARI_INI)
    assert (await svc.tenggat(hari_ini))["status"] == "aman"
    r = await klien.post("/api/cash-advance-settlements", headers=kepala_admin, json={
        "cash_advance_id": pd["id"], "periode": HARI_INI[:7],
        "expense_lines": [{"date": HARI_INI, "description": "bensin", "category": "transportasi", "amount": 900_000}]})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert (await svc.tenggat(pd))["status"] == "lewat"                         # LPJ draf belum memenuhi
    assert (await klien.post(f"/api/cash-advance-settlements/{sid}/submit", headers=kepala_admin)).status_code == 200
    assert await svc.tenggat(pd) == {"jatuh_tempo": _tgl(-2), "status": "terpenuhi", "hari_lewat": 0}
    r = await klien.post(f"/api/cash-advance-settlements/{sid}/reject", headers=kepala_admin,
                         json={"note": "nota kurang"})
    assert r.status_code == 200, r.text
    assert (await svc.tenggat(pd))["status"] == "lewat"                         # LPJ ditolak → dihitung lagi
    assert await svc.tenggat({**pd, "status": "approved"}) is None              # belum cair: tanpa tenggat


# ═══ 8. Antrean Meja Keuangan "LPJ uang muka lewat tenggat" ═══════════════════════════════════════════════════════
async def test_KB4_2_U8_antrean_meja_lpj_lewat_tenggat(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin, siap):
    from services import work_desk_service as desks
    f, h = await _orang(akun, sesi, peran_tanpa_acuan, "finance")
    lewat = await _sisip(db, status="disbursed", nilai=750_000, pembuat={"id": f["id"], "name": f["name"]},
                         pemegang={"jenis": "karyawan", "id": KAR_A["id"], "nama": KAR_A["name"]},
                         jatuh_tempo=_tgl(-3))
    aman = await _sisip(db, status="disbursed", pembuat={"id": f["id"], "name": f["name"]}, jatuh_tempo=_tgl(2))
    kanda = await _sisip(db, status="disbursed", entity=KANDA, jatuh_tempo=_tgl(-1))

    async def _baris(eids) -> dict:
        out = await desks.finance_desk(AKTOR_UJI, {"entity_id": {"$in": eids}}, eids)
        q = next(x for x in out["queues"] if x["id"] == "lpj_uang_muka_lewat_tenggat")
        assert (q["label"], q["owner"]) == ("LPJ uang muka lewat tenggat", "finance"), q
        return {r["ref_id"]: r for r in q["rows"]}

    rows = await _baris([KSC])
    assert lewat["id"] in rows and aman["id"] not in rows and kanda["id"] not in rows, rows
    b = rows[lewat["id"]]
    assert (b["ref_type"], b["number"], b["title"], b["value"], b["entity_id"]) == (
        "cash_advance", lewat["number"], KAR_A["name"], 750_000.0, KSC), b
    assert (b["age_kind"], b["age_days"], b["at"], b["badge"], b["action"]) == ("overdue", 3, _tgl(-3), "lewat", "Buka")
    assert b["pemegang"] == {"jenis": "karyawan", "id": KAR_A["id"], "nama": KAR_A["name"]}
    assert (b["lpj_jatuh_tempo"], b["hari_lewat"], b["pembuat"]) == (_tgl(-3), 3, f["name"]), b
    assert kanda["id"] in await _baris([KSC, KANDA])
    # LPJ diajukan → tenggat terpenuhi → hilang dari antrean
    r = await klien.post("/api/cash-advance-settlements", headers=kepala_admin, json={
        "cash_advance_id": lewat["id"], "periode": HARI_INI[:7],
        "expense_lines": [{"date": HARI_INI, "description": "solar", "category": "transportasi", "amount": 700_000}]})
    assert r.status_code == 200, r.text
    assert (await klien.post(f"/api/cash-advance-settlements/{r.json()['id']}/submit",
                             headers=kepala_admin)).status_code == 200
    assert lewat["id"] not in await _baris([KSC])
    # daftar PD & Kas Kecil membawa lencana tenggat
    rows = {x["id"]: x for x in (await klien.get("/api/cash-advances", headers=h)).json()}
    assert (rows[aman["id"]]["tenggat_status"], rows[lewat["id"]]["tenggat_status"]) == ("aman", "terpenuhi")
    wl = (await klien.get("/api/petty-cash/worklist", headers=kepala_admin, params={"q": aman["number"]})).json()
    (baris,) = wl["items"]
    assert (baris["lpj_jatuh_tempo"], baris["tenggat_status"], baris["tenggat_hari_lewat"]) == (_tgl(2), "aman", 0)
    assert baris["pemegang"]["id"] == f["id"]


# ═══ 9. Pemberitahuan H-1 & lewat ke pembuat PD, sekali per PD per jenis ══════════════════════════════════════════
async def test_KB4_2_U9_pengingat_h1_dan_lewat_sekali(klien, db, akun, sesi, peran_tanpa_acuan, siap):
    from services import cash_advance_service as svc
    from services import scheduler_service as sch
    from services.notification_doc_ref import attach_doc_refs
    f, _ = await _orang(akun, sesi, peran_tanpa_acuan, "finance")
    pembuat = {"id": f["id"], "name": f["name"]}
    h1 = await _sisip(db, status="disbursed", nilai=300_000, pembuat=pembuat, jatuh_tempo=_tgl(1))
    lewat = await _sisip(db, status="disbursed", nilai=600_000, pembuat=pembuat, jatuh_tempo=_tgl(-2),
                         pemegang={"jenis": "karyawan", "id": KAR_B["id"], "nama": KAR_B["name"]})
    aman = await _sisip(db, status="disbursed", pembuat=pembuat, jatuh_tempo=_tgl(5))
    job = sch.JOB_MAP["lpj_tenggat_reminder"]
    assert job["kind"] == "daily" and sch.JOB_THRESHOLDS["lpj_tenggat_reminder"] == (K_TENGGAT,)
    for _ in range(2):
        res = await job["fn"]()
        assert res["scanned"] >= 3, res
    rows = await db.notifications.find({"recipient_user": f["id"], "type": "lpj_uang_muka_tenggat"},
                                       {"_id": 0}).to_list(20)
    per = {n["ref"]: n for n in rows}
    assert set(per) == {f"{h1['id']}:h-1#{f['id']}", f"{lewat['id']}:lewat#{f['id']}"}, list(per)
    n1, nl = per[f"{h1['id']}:h-1#{f['id']}"], per[f"{lewat['id']}:lewat#{f['id']}"]
    assert n1["title"] == f"LPJ uang muka jatuh tempo besok — {h1['number']}"
    assert n1["body"] == (f"LPJ {h1['number']} (Rp 300.000) untuk uang muka yang dipegang {f['name']} jatuh tempo besok, "
                          f"{tanggal_panjang(_tgl(1))}. Ajukan LPJ-nya di Kas Kecil.")
    assert nl["title"] == f"LPJ uang muka lewat tenggat — {lewat['number']}"
    assert nl["body"] == (f"LPJ {lewat['number']} (Rp 600.000) untuk uang muka yang dipegang {KAR_B['name']} lewat "
                          f"tenggat 2 hari (jatuh tempo {tanggal_panjang(_tgl(-2))}). Ajukan LPJ-nya segera di Kas Kecil.")
    assert (n1["severity"], nl["severity"], nl["entity_id"]) == ("info", "warning", KSC)
    assert aman["id"] not in {r.split(":", 1)[0] for r in per}
    (doc,) = await attach_doc_refs([{**nl}])
    assert doc["doc"] == {"ref_type": "cash_advance", "ref_id": lewat["id"], "number": lewat["number"],
                          "label": f"Pengajuan dana {lewat['number']}"}, doc
    # gagal memberi tahu → hanya log, job tetap selesai
    from services import notification_service as ns

    async def _rusak(*a, **k):
        raise RuntimeError("notifikasi rusak")
    await _sisip(db, status="disbursed", pembuat=pembuat, jatuh_tempo=_tgl(-4))
    asli = ns.create_addressed
    ns.create_addressed = _rusak
    try:
        res = await svc.job_lpj_tenggat_reminder()
        assert res["created"] == 0 and "gagal" in res["detail"], res
    finally:
        ns.create_addressed = asli


# ═══ 10. Regresi: alur PD → LPJ → kembalikan sisa / reimburse tetap; PD tuntas melepas batas ═══════════════════════
async def test_KB4_2_U10_alur_pd_lpj_sisa_reimburse_tetap(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin,
                                                          siap):
    from services import cash_advance_service as svc
    u, h = await _orang(akun, sesi, peran_tanpa_acuan, "staf")
    pd = await _draf(klien, h, 1_000_000)
    assert (await _ajukan(klien, h, pd["id"])).status_code == 200
    await _setujui_semua(klien, kepala_admin, pd["id"])
    r = await _cair(klien, kepala_admin, pd["id"], tanggal=HARI_INI)
    assert r.status_code == 200 and r.json()["status"] == "disbursed", r.text
    r = await klien.post("/api/cash-advance-settlements", headers=kepala_admin, json={
        "cash_advance_id": pd["id"], "periode": HARI_INI[:7],
        "expense_lines": [{"date": HARI_INI, "description": "tol", "category": "transportasi", "amount": 800_000}]})
    sid = r.json()["id"]
    for langkah in ("submit", "approve"):
        assert (await klien.post(f"/api/cash-advance-settlements/{sid}/{langkah}", headers=kepala_admin)).status_code \
            == 200
    stl = await db.cash_advance_settlements.find_one({"id": sid}, {"_id": 0})
    assert (stl["status"], stl["sisa_dikembalikan"]["amount"], stl["sisa_dikembalikan"]["status"]) == (
        "posted_to_gl", 200_000, "open")
    assert (await db.cash_advances.find_one({"id": pd["id"]}))["status"] == "settled"
    assert (await svc.tenggat(await db.cash_advances.find_one({"id": pd["id"]}, {"_id": 0})))["status"] == "terpenuhi"
    kedua = await _draf(klien, h, 500_000)
    r = await _ajukan(klien, h, kedua["id"])                      # sisa masih di tangan → tertahan
    assert r.status_code == 409 and "sisa Rp 200.000 belum dikembalikan" in r.json()["detail"], r.text
    r = await klien.post(f"/api/cash-advance-settlements/{sid}/return-remainder", headers=kepala_admin,
                         json={"cash_type": "kas_kecil", "account_id": REK[KSC]})
    assert r.status_code == 200 and r.json()["sisa_dikembalikan"]["status"] == "returned", r.text
    assert (await _ajukan(klien, h, kedua["id"])).status_code == 200
    # LPJ lebih dari uang muka → hutang reimburse (uang karyawan) tidak menahan PD baru
    await _setujui_semua(klien, kepala_admin, kedua["id"])
    assert (await _cair(klien, kepala_admin, kedua["id"])).status_code == 200
    r = await klien.post("/api/cash-advance-settlements", headers=kepala_admin, json={
        "cash_advance_id": kedua["id"], "periode": HARI_INI[:7],
        "expense_lines": [{"date": HARI_INI, "description": "hotel", "category": "transportasi", "amount": 650_000}]})
    sid2 = r.json()["id"]
    for langkah in ("submit", "approve"):
        assert (await klien.post(f"/api/cash-advance-settlements/{sid2}/{langkah}",
                                 headers=kepala_admin)).status_code == 200
    ketiga = await _draf(klien, h, 100_000)
    assert (await _ajukan(klien, h, ketiga["id"])).status_code == 200
    r = await klien.post(f"/api/cash-advance-settlements/{sid2}/pay-reimburse", headers=kepala_admin,
                         json={"cash_type": "kas_kecil", "account_id": REK[KSC]})
    assert r.status_code == 200 and r.json()["hutang_reimburse"]["status"] == "paid", r.text


# ═══ 11. Pengaturan aktif & terpasang ═════════════════════════════════════════════════════════════════════════════
async def test_KB4_2_U11_pengaturan_aktif_berpembaca(klien, monkeypatch):
    from pathlib import Path
    import config_registry as reg
    from services import config_health
    monkeypatch.setattr(config_health, "BACKEND", str(Path(__file__).resolve().parents[1]))   # pola uji KF-T2
    for key, fungsi in ((K_MAKS, "batas_pd_terbuka"), (K_TENGGAT, "hari_tenggat_lpj")):
        e = reg.require(key)
        assert (e["status"], e["not_used_reason"]) == ("active", ""), e
        assert e["consumers"] == (f"services/cash_advance_service.py:{fungsi}",) or \
            list(e["consumers"]) == [f"services/cash_advance_service.py:{fungsi}"], e["consumers"]
        assert config_health.check_entry(e)["wiring_status"] == "OK"
