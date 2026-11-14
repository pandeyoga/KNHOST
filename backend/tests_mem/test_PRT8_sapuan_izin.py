"""PR-T8 U2–U10, U12 — penjaga matriks izin berjalan (docs/blueprint/unit/PR-T8.md).

Rute sementara didaftarkan ke `server.app` di dalam tes (awalan `/api/_uji/`) dan dicabut sesudahnya; sapuan
(`sapuan_izin.jalankan`, sama dengan baris perintah) dijalankan dengan `awalan="/api/_uji"` dan berkas harapan yang
berlaku (`sapuan_izin_harapan.json`) — entri di luar awalan tidak ikut dinilai. U8 memanggil penilai langsung dengan
hasil buatan. U1, U11, U15 (seluruh rute, mode cepat dan penuh) dijalankan dari baris perintah — terlalu lama untuk
pytest; keluarannya dilampirkan di laporan. Modul sendiri (basis data sendiri): sapuan membuat peran dan akun.
"""
import copy
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

import role_registry
import sapuan_izin as si
from dependencies import current_user, require_permission
from permissions_config import DEFAULT_PERMISSIONS

pytestmark = pytest.mark.anyio

AWALAN = "/api/_uji"
UNIT_PEMEGANG = ("PK-17", "KF-T1", "KP-T4", "PR-T4")   # spesifikasi: `menunggu_unit` hanya untuk unit ini


@pytest.fixture(scope="module", autouse=True)
def _lepas_jejak():
    yield
    si.lepas_jejak()


@contextmanager
def rute_sementara(app, jalur: str, fungsi, metode: str = "GET"):
    app.add_api_route(jalur, fungsi, methods=[metode])
    rt = app.router.routes[-1]
    app.openapi_schema = None
    try:
        yield f"{metode} {jalur}"
    finally:
        app.router.routes.remove(rt)
        app.openapi_schema = None


async def sapu(klien, aplikasi, kepala_admin, db, *, harapan=None, awalan=AWALAN, **kw):
    baris: list = []
    kode, lap = await si.jalankan(klien, aplikasi, kepala_admin, awalan=awalan,
                                  harapan=si.muat_harapan() if harapan is None else harapan,
                                  cetak=baris.append, db=db, **kw)
    return kode, lap, baris


def kode_m(lap, kunci=None):
    return sorted(p["kode"] for p in lap["pelanggaran"]
                  if kunci is None or f"{p['metode']} {p['jalur']}" == kunci)


# ── Rute sementara ──────────────────────────────────────────────────────────
async def _tanpa_sesi():
    return {"ok": True}


async def _login_saja(request: Request):
    await current_user(request)
    return {"ok": True}


async def _gerbang_nama_peran(request: Request):
    user = await require_permission(request, "order", "view")
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Khusus Manajer")
    return {"ok": True}


async def _peran_dasar_manajer(request: Request):
    user = await current_user(request)
    if role_registry.role_in(user.get("role"), ("manager",)):
        return {"ok": True}
    raise HTTPException(status_code=403, detail="Khusus Manajer")


class IsiBerpola(BaseModel):
    kode: str = Field(pattern=r"^KN-\d{4}$")


async def _berpola(isi: IsiBerpola, request: Request):
    await require_permission(request, "order", "create")
    return {"ok": isi.kode}


async def _berizin(request: Request):
    await require_permission(request, "order", "view")
    return {"ok": True}


# ── Uji ─────────────────────────────────────────────────────────────────────
async def test_PRT8_U2_rute_tanpa_penegak_M0(aplikasi, klien, kepala_admin, db):
    with rute_sementara(aplikasi, f"{AWALAN}/tanpa-sesi", _tanpa_sesi) as kunci:
        kode, lap, baris = await sapu(klien, aplikasi, kepala_admin, db)
    assert kode == 1
    assert kode_m(lap, kunci).count("M0") == 1
    m0 = [p for p in lap["pelanggaran"] if p["kode"] == "M0"]
    assert [(p["metode"], p["jalur"], p["akun"], p["jawaban"]) for p in m0] == [("GET", f"{AWALAN}/tanpa-sesi",
                                                                                 "tanpa_token", 200)]
    assert any(b.startswith("  M0 GET") for b in baris)            # satu baris layar per pelanggaran


async def test_PRT8_U3_login_saja_tanpa_putusan_M1(aplikasi, klien, kepala_admin, db):
    with rute_sementara(aplikasi, f"{AWALAN}/login-saja", _login_saja) as kunci:
        kode, lap, _ = await sapu(klien, aplikasi, kepala_admin, db)
    assert kode == 1
    assert kode_m(lap) == ["M1"] and kode_m(lap, kunci) == ["M1"]
    assert lap["hasil"]["tanpa_token"][kunci][0] == 401


async def test_PRT8_U4_gerbang_nama_peran_menolak_pemegang_izin_M2(aplikasi, klien, kepala_admin, db):
    with rute_sementara(aplikasi, f"{AWALAN}/nama-peran", _gerbang_nama_peran) as kunci:
        kode, lap, _ = await sapu(klien, aplikasi, kepala_admin, db)
    assert kode == 1
    assert kode_m(lap) == ["M2"]
    (p,) = lap["pelanggaran"]
    assert (p["akun"], p["jawaban"], f"{p['metode']} {p['jalur']}") == ("penuh", 403, kunci)
    assert lap["hasil"]["kosong"][kunci][:3] == [403, "ditolak", ["order.view"]]   # penolakan izin bagi kosong


async def test_PRT8_U5_terbuka_lewat_peran_dasar_manajer_M3(aplikasi, klien, kepala_admin, db):
    with rute_sementara(aplikasi, f"{AWALAN}/peran-dasar", _peran_dasar_manajer, "POST") as kunci:
        kode, lap, baris = await sapu(klien, aplikasi, kepala_admin, db)
    assert kode == 1
    assert kode_m(lap) == ["M3"]
    (p,) = lap["pelanggaran"]
    assert (p["akun"], p["jawaban"], p["catatan"]) == ("mgr0", 200, "juga tertutup bagi Sopir")
    assert [lap["hasil"][a][kunci][0] for a in ("tanpa_token", "kosong", "sopir", "mgr0")] == [401, 403, 403, 200]
    assert kunci not in lap["hasil"]["penuh"]                                     # akun penuh hanya GET
    assert any("juga tertutup bagi Sopir" in b for b in baris)


async def test_PRT8_U6_isi_tak_lolos_validasi_M6_lalu_isi_contoh(aplikasi, klien, kepala_admin, db):
    harapan = si.muat_harapan()
    with rute_sementara(aplikasi, f"{AWALAN}/berpola", _berpola, "POST") as kunci:
        kode, lap, _ = await sapu(klien, aplikasi, kepala_admin, db, harapan=harapan)
        assert kode == 1
        assert kode_m(lap) == ["M6"]                                              # satu baris per rute
        assert {lap["hasil"][a][kunci][1] for a in ("tanpa_token", "kosong", "sopir", "mgr0")} == {"tak_teruji"}
        dengan = copy.deepcopy(harapan)
        dengan.setdefault("isi_contoh", {})[kunci] = {"json": {"kode": "KN-0001"}}
        kode2, lap2, _ = await sapu(klien, aplikasi, kepala_admin, db, harapan=dengan)
    assert (kode2, kode_m(lap2)) == (0, [])
    assert [lap2["hasil"][a][kunci][0] for a in ("tanpa_token", "kosong", "sopir", "mgr0")] == [401, 403, 403, 403]


async def test_PRT8_U7_entri_harapan_tanpa_rute_M7(aplikasi, klien, kepala_admin, db):
    harapan = copy.deepcopy(si.muat_harapan())
    harapan.setdefault("tolak_bukan_izin", {})[f"GET {AWALAN}/tidak-ada"] = "uji U7: rute sudah dihapus"
    with rute_sementara(aplikasi, f"{AWALAN}/berizin", _berizin):
        kode, lap, _ = await sapu(klien, aplikasi, kepala_admin, db, harapan=harapan)
    assert kode == 1
    assert kode_m(lap) == ["M7"]
    assert lap["pelanggaran"][0]["jalur"] == f"{AWALAN}/tidak-ada"
    # baris tanpa alasan ditolak skrip
    harapan["tolak_bukan_izin"][f"GET {AWALAN}/tidak-ada"] = ""
    assert any("tanpa alasan" in m for _, m in si.periksa_harapan(harapan))


async def test_PRT8_U8_peran_bawaan_tidak_mengikuti_matriks_M5():
    # Hasil buatan: rute menuntut `accounting.view` (bagi kosong ditolak dengan izin itu). Sales (tidak memegang
    # accounting.view) lolos → M5; Finance (memegang accounting.view) ditolak 403 berizin accounting.view → M5.
    assert "view" in DEFAULT_PERMISSIONS["finance"]["accounting"] and "accounting" not in DEFAULT_PERMISSIONS["sales"]
    kunci = "GET /api/_uji/akuntansi"
    R = lambda kode, izin=None: [kode, si.kelas(kode), izin]  # noqa: E731
    hasil = {"tanpa_token": {kunci: R(401)}, "kosong": {kunci: R(403, ["accounting.view"])},
             "penuh": {kunci: R(200)}, "mgr0": {kunci: R(403, ["accounting.view"])},
             "sopir": {kunci: R(403, ["accounting.view"])},
             "sales": {kunci: R(200)}, "finance": {kunci: R(403, ["accounting.view"])}}
    k = si.Konteks(rute=[kunci], semua_rute={kunci}, publik={}, login_saja=[], harapan={},
                   peran_izin={"sales": DEFAULT_PERMISSIONS["sales"], "finance": DEFAULT_PERMISSIONS["finance"]})
    pel = si.nilai(hasil, k)
    assert sorted((p["kode"], p["akun"]) for p in pel) == [("M5", "finance"), ("M5", "sales")]


async def test_PRT8_U9_U10_costing_dan_sesi_akhir(aplikasi, klien, kepala_admin, db, tmp_path):
    berkas = tmp_path / "sapuan.json"
    users0 = await db.users.count_documents({})
    roles0 = await db.custom_roles.count_documents({})
    kode, lap, baris = await sapu(klien, aplikasi, kepala_admin, db, awalan="/api/costing", keluaran=str(berkas))
    assert kode == 0, baris
    isi = json.loads(berkas.read_text())
    wac = {a: isi["hasil"][a]["GET /api/costing/wac"] for a in ("kosong", "penuh", "mgr0", "sopir")}
    assert {a: v[0] for a, v in wac.items()} == {"kosong": 403, "penuh": 200, "mgr0": 403, "sopir": 403}
    assert all(len(v) == 3 for v in wac.values())                                 # [kode, kelas, izin_diminta]
    assert wac["kosong"][1] == "ditolak" and wac["kosong"][2]                      # izin yang diminta terbaca
    assert (isi["akun"]["penuh"]["label"], isi["akun"]["mgr0"]["label"]) == ("Tanpa Acuan Penuh", "Manajer Kosong")
    # U10 — keempat akun bersesi tetap 200; jumlah users / custom_roles = sebelum + buatan sapuan (4 akun, 3 peran)
    assert isi["sesi_akhir"] == {"kosong": 200, "sopir": 200, "mgr0": 200, "penuh": 200}
    assert (await db.users.count_documents({}), await db.custom_roles.count_documents({})) == (users0 + 4, roles0 + 3)
    assert isi["jumlah"]["users"]["buatan_sapuan"] == 4 and isi["jumlah"]["custom_roles"]["buatan_sapuan"] == 3
    assert not [p for p in isi["pelanggaran"] if p["kode"] == "M8"]


async def test_PRT8_berkas_harapan_beralasan():
    harapan = si.muat_harapan()
    assert si.periksa_harapan(harapan) == []
    assert set(k for k in harapan if not k.startswith("_")) == set(si.BAGIAN_HARAPAN)
    for kunci, alasan in harapan["menunggu_unit"].items():
        assert alasan.startswith(UNIT_PEMEGANG), (kunci, alasan)


async def test_PRT8_uji_diri_baris_perintah():
    r = subprocess.run([sys.executable, str(Path(si.__file__)), "--uji-diri"], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout and r.stdout.count("[PASS]") >= 20
