"""PK-46 — tabel tarif PPh 21 dibaca dari pengaturan bertanggal berlaku (docs/blueprint/unit/PK-46.md).

Data uji:
- `data/pph21_snapshot_kode_lama.json` — keluaran kode LAMA, dihasilkan `data/buat_snapshot_pph21.py` dari commit
  `ea0de78` (bukan diketik). Dipakai U1–U2.
- `data/pph21_sintetis.json` — tabel uji sintetis, BUKAN tarif nyata (dua baris per kategori). Dipakai U3–U5, U11.
- `docs/blueprint/data/pph21_terverifikasi.json` — berkas PEMILIK (K-42). Belum ada → U12–U13 dilewati dengan alasan
  "menunggu berkas pemilik (H4)"; begitu berkas diletakkan, keduanya berjalan otomatis. Tidak diganti tabel lain.

Fixture: karyawan `emp_pk46` (ent_ksc, gaji pokok Rp 80.000.000, TK0, kelas JKK II) disisipkan langsung ke
`hr_employees`. Alur: simpan pengaturan lewat `PUT /api/config/values`, proses gaji lewat `POST /api/hr/payroll/runs`
dan `POST /api/hr/payroll/runs/preview`. Satu database per modul; urutan tes U1 → U13 bermakna (U3 menyimpan tabel
sintetis berlaku 2027-01-01 yang dipakai U4–U5).
"""
from __future__ import annotations

import copy
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import config_registry as registry
from services import config_resolver as resolver
from services import hr_payroll_service as pay

pytestmark = pytest.mark.anyio

DATA = Path(__file__).resolve().parent / "data"
ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = json.loads((DATA / "pph21_snapshot_kode_lama.json").read_text(encoding="utf-8"))
SINTETIS = json.loads((DATA / "pph21_sintetis.json").read_text(encoding="utf-8"))
BERKAS_PEMILIK = ROOT / "docs/blueprint/data/pph21_terverifikasi.json"
PEMUAT = ROOT / "scripts/muat_pph21_terverifikasi.py"
ENAM = ("hr.pph21.ter_table", "hr.pph21.ptkp_to_ter", "hr.ptkp_table", "hr.pph21.pasal17_table",
        "hr.pph21.biaya_jabatan_pct", "hr.pph21.biaya_jabatan_maks_bulanan")
H4 = "menunggu berkas pemilik (H4): docs/blueprint/data/pph21_terverifikasi.json belum ada — K-42, tidak diganti tabel lain"
EMP = "emp_pk46"


def _rata(ter: dict) -> list:
    """{"A": [{batas_atas, tarif_pct}], …} (bentuk berkas) → baris registry ber-`kategori`."""
    return [{"kategori": k, **r} for k in ("A", "B", "C") for r in ter[k]]


def _per_kategori(rows: list) -> dict:
    out: dict = {}
    for r in rows:
        out.setdefault(r["kategori"], []).append({"batas_atas": r["batas_atas"], "tarif_pct": float(r["tarif_pct"])})
    return out


def _put(key, value, *, reason="uji PK-46", effective_from=""):
    return {"items": [{"key": key, "value": value, "scope_type": "global", "scope_id": "", "reason": reason,
                       "effective_from": effective_from}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _penghitung():
    """Kode baru: aturan bertanggal (bawaan) per 30 Nov 2026. Bila modul masih kode lama (bukti di commit awal),
    tanda tangan lama dipakai — U1–U2 lalu membuktikan snapshot = perilaku kode lama."""
    if hasattr(pay, "aturan_pph21"):
        aturan = await pay.aturan_pph21("2026-11-30")
        return (lambda k, b: pay.ter_rate(k, b, aturan)), (lambda **m: pay.annual_pph21(**m, aturan=aturan))
    return pay.ter_rate, pay.annual_pph21


@pytest.fixture(scope="module")
async def karyawan(db):
    await db.hr_employees.insert_one({
        "id": EMP, "code": "EMP-PK46", "name": "Karyawan Uji PK46", "entity_id": "ent_ksc", "status": "active",
        "base_salary": 80_000_000, "allowances": [], "ptkp_status": "TK0", "jkk_risk_class": "II",
        "created_at": "2026-11-14T00:00:00+00:00"})
    return EMP


async def _slip(klien, h, period: str, *, simpan: bool = False) -> dict:
    url = "/api/hr/payroll/runs" if simpan else "/api/hr/payroll/runs/preview"
    r = await klien.post(url, headers=h, json={"entity_id": "ent_ksc", "period": period})
    assert r.status_code == 200, r.text
    return next(s for s in r.json()["payslips"] if s["employee_id"] == EMP)


# ── U1–U2: perilaku tidak berubah sebelum berkas pemilik dimuat ────────────────────────────────────────────────────────
async def test_PK46_U1_tarif_bulanan_sama_dengan_snapshot_kode_lama(aplikasi):
    ter, _ = await _penghitung()
    beda = [(t["kategori"], t["bruto"], t["tarif"], ter(t["kategori"], t["bruto"])) for t in SNAPSHOT["titik_ter"]
            if ter(t["kategori"], t["bruto"]) != t["tarif"]]
    assert len(SNAPSHOT["titik_ter"]) == 334
    assert beda == []


async def test_PK46_U2_contoh_setahun_sama_sampai_rupiah(aplikasi):
    _, setahun = await _penghitung()
    for c in SNAPSHOT["contoh_setahun"]:
        assert setahun(**c["masukan"]) == c["keluaran"], c["masukan"]


# ── U3–U5: tabel baru berlaku mulai tanggalnya; tanggal lampau tetap tabel lama ───────────────────────────────────────
async def test_PK46_U3_tabel_sintetis_berlaku_mulai_2027(klien, kepala_admin):
    sintetis = _rata(SINTETIS["ter"])
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put("hr.pph21.ter_table", sintetis, effective_from="2027-01-01"))
    assert r.status_code == 200, r.text
    bawaan = _per_kategori(registry.require("hr.pph21.ter_table")["default"])
    assert (await pay.aturan_pph21("2026-12-31"))["ter"] == bawaan
    assert (await pay.aturan_pph21("2027-01-31"))["ter"] == _per_kategori(sintetis)
    # sintetis dua baris per kategori; bawaan 44/40/41 baris (isi kode lama) — keduanya benar-benar berbeda
    assert [len(v) for v in _per_kategori(sintetis).values()] == [2, 2, 2]


async def test_PK46_U4_tidak_diproyeksikan_ke_penyimpanan_lama(db, monkeypatch):
    class _Jam(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2027, 2, 1, tzinfo=datetime.timezone.utc)

    monkeypatch.setattr(resolver, "datetime", _Jam)
    hasil = await resolver.apply_due_values()
    monkeypatch.undo()
    assert hasil["applied"] >= 1                                         # baris 2027-01-01 dari U3 jatuh tempo
    baris = await db.config_values.find_one({"key": "hr.pph21.ter_table", "effective_from": "2027-01-01"}, {"_id": 0})
    assert baris["applied_at"]
    bawaan = _per_kategori(registry.require("hr.pph21.ter_table")["default"])
    assert (await pay.aturan_pph21("2026-12-31"))["ter"] == bawaan
    doc = await db.system_settings.find_one({"scope": "hr"}, {"_id": 0}) or {}
    assert "pph21" not in doc


async def test_PK46_U5_slip_per_periode_mengikuti_tanggal_berlaku(klien, kepala_admin, karyawan, monkeypatch):
    # PK-22 (FY-02) — proses gaji untuk periode yang belum dimulai kini ditolak 400: "hari ini" dibekukan 15 Jan 2027
    # supaya Desember 2026 dan Januari 2027 boleh diproses (tanggal berlaku tabel tetap dari pengaturan, bukan jam).
    import datetime as _dt
    from services import book_date
    monkeypatch.setattr(book_date, "_sekarang", lambda: _dt.datetime(2027, 1, 15, 3, 0, tzinfo=_dt.timezone.utc))
    # Karyawan: gaji pokok 80.000.000, TK0 → kategori A (bawaan dan sintetis), BPJS bawaan:
    #   bruto pajak = 80.000.000 + JKK 0,54% 432.000 + JKM 0,3% 240.000 + Kesehatan 4% × batas 12.000.000 480.000
    #               = 81.152.000
    # 2026-11 (TER, tabel bawaan A): 72.650.000 < 81.152.000 ≤ 86.350.000 → 16% → 12.984.320
    nov = await _slip(klien, kepala_admin, "2026-11")
    assert (nov["tax_gross"], nov["pph21_method"], nov["pph21_rate"], nov["pph21"]) == (81_152_000, "ter", 0.16, 12_984_320)
    # 2026-12 = masa pajak terakhir → hitung ulang setahun dengan aturan per 31-12-2026 (bawaan), 1 bulan:
    #   biaya jabatan min(5% × 81.152.000 = 4.057.600; 500.000 × 1) = 500.000
    #   iuran pensiun karyawan JHT 2% 1.600.000 + JP 1% × 10.042.300 = 100.423 → 1.700.423
    #   neto 81.152.000 − 500.000 − 1.700.423 = 78.951.577; PTKP TK0 54.000.000 → PKP 24.951.000
    #   pasal 17 lapis 1 (5%) → 1.247.550
    des = await _slip(klien, kepala_admin, "2026-12", simpan=True)
    assert (des["pph21_method"], des["pph21_annual"]["ptkp"], des["pph21"]) == ("annual_pasal17", 54_000_000, 1_247_550)
    # 2027-01 (TER, tabel SINTETIS A dari U3): 81.152.000 > 10.000.000 → 2% → 1.623.040
    jan = await _slip(klien, kepala_admin, "2027-01", simpan=True)
    assert (jan["pph21_method"], jan["pph21_rate"], jan["pph21"]) == ("ter", 0.02, 1_623_040)
    # Tabel pasal 17 sintetis juga disimpan berlaku 2027-01-01: hitung ulang Desember tetap memakai tabel 2026.
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put("hr.pph21.pasal17_table", SINTETIS["pasal17"], effective_from="2027-01-01"))
    assert r.status_code == 200, r.text
    ulang = await _slip(klien, kepala_admin, "2026-12")
    assert ulang["pph21"] == des["pph21"] == 1_247_550
    assert (await _slip(klien, kepala_admin, "2026-11"))["pph21"] == nov["pph21"]


# ── U6–U7: validasi dan wewenang ───────────────────────────────────────────────────────────────────────────────────────
async def test_PK46_U6_tabel_tidak_sah_ditolak_tanpa_baris_baru(klien, kepala_admin, db):
    dasar = _rata(SINTETIS["ter"])
    tidak_naik = [{"kategori": "A", "batas_atas": 10_000_000, "tarif_pct": 1},
                  {"kategori": "A", "batas_atas": 5_000_000, "tarif_pct": 1.5},
                  {"kategori": "A", "batas_atas": None, "tarif_pct": 2}] + [r for r in dasar if r["kategori"] != "A"]
    akhir_berbatas = [r for r in dasar if r["kategori"] != "C"] + [
        {"kategori": "C", "batas_atas": 10_000_000, "tarif_pct": 5}, {"kategori": "C", "batas_atas": 20_000_000, "tarif_pct": 6}]
    tarif_150 = copy.deepcopy(dasar)
    next(r for r in tarif_150 if r["kategori"] == "B")["tarif_pct"] = 150
    tanpa_c = [r for r in dasar if r["kategori"] != "C"]
    kasus = [(tidak_naik, ("kategori A", "baris 2", "lebih besar")),
             (akhir_berbatas, ("kategori C", "baris 2", "baris terakhir harus tanpa batas")),
             (tarif_150, ("kategori B", "baris 1", "150")),
             (tanpa_c, ("kategori C", "wajib ada"))]
    sebelum = await db.config_values.count_documents({"key": "hr.pph21.ter_table"})
    for nilai, potongan in kasus:
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("hr.pph21.ter_table", nilai))
        assert r.status_code == 400, r.text
        for p in potongan:
            assert p in _detail(r), (p, _detail(r))
    assert await db.config_values.count_documents({"key": "hr.pph21.ter_table"}) == sebelum


async def test_PK46_U7_alasan_wajib_dan_izin_kelola_gaji(klien, kepala_admin, akun, sesi, peran_tanpa_acuan,
                                                         peran_sopir):
    kunci = "hr.pph21.biaya_jabatan_maks_bulanan"
    nilai = registry.require(kunci)["default"]          # nilai sama → perilaku slip tidak berubah
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put(kunci, nilai, reason=""))
    assert r.status_code == 400, r.text
    assert "alasan" in _detail(r).lower()
    rid = await peran_tanpa_acuan({"hr": ["view", "manage_payroll"]}, label="Kelola Gaji PK46")
    h = await sesi(await akun(rid))
    r = await klien.put("/api/config/values", headers=h, json=_put(kunci, nilai))
    assert r.status_code == 200, r.text
    h = await sesi(await akun(peran_sopir))
    r = await klien.put("/api/config/values", headers=h, json=_put(kunci, nilai))
    assert r.status_code == 403, r.text


# ── U8–U9: PTKP ikut bertanggal; sifat registry ───────────────────────────────────────────────────────────────────────
async def test_PK46_U8_ptkp_naik_hanya_mulai_tanggal_berlaku(klien, kepala_admin):
    lama = dict(registry.require("hr.ptkp_table")["default"])
    baru = {**lama, "K1": lama["K1"] + 1_000_000}
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put("hr.ptkp_table", baru, effective_from="2027-01-01"))
    assert r.status_code == 200, r.text
    a26, a27 = await pay.aturan_pph21("2026-12-31"), await pay.aturan_pph21("2027-12-31")
    contoh = {"tax_gross": 150_000_000, "pension_deduction": 3_600_000, "months": 12}
    for status in lama:
        p26 = pay.annual_pph21(**contoh, ptkp_status=status, aturan=a26)["ptkp"]
        p27 = pay.annual_pph21(**contoh, ptkp_status=status, aturan=a27)["ptkp"]
        assert p26 == lama[status], status
        assert p27 == lama[status] + (1_000_000 if status == "K1" else 0), status


async def test_PK46_U9_ptkp_aktif_dan_enam_kunci_bertanggal(klien, kepala_admin):
    assert registry.require("hr.ptkp_table")["status"] == "active"
    assert registry.require("hr.ptkp_table")["not_used_reason"] == ""
    assert all(registry.require(k)["bertanggal"] is True for k in ENAM)
    r = await klien.get("/api/config/registry", headers=kepala_admin, params={"group": "sdm"})
    assert r.status_code == 200, r.text
    per = {e["key"]: e for e in r.json()["entries"]}
    assert {k: per[k]["bertanggal"] for k in ENAM} == {k: True for k in ENAM}
    assert per["hr.ptkp_table"]["status"] == "active" and per["hr.ptkp_table"]["can_edit"] is True
    assert per["hr.ter_enabled"]["bertanggal"] is False
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"group": "sdm"})
    assert r.status_code == 200, r.text
    assert {it["key"]: it["bertanggal"] for it in r.json()["items"] if it["key"] in ENAM} == {k: True for k in ENAM}


# ── U10–U11: konstanta keluar dari mesin; pemuat berkas ────────────────────────────────────────────────────────────────
def test_PK46_U10_konstanta_tarif_tidak_ada_di_mesin():
    nama = re.compile(r"\b(TER_A|TER_TABLES|PTKP_AMOUNT|PASAL17|BIAYA_JABATAN_RATE)\b")
    impor = re.compile(r"^\s*(from\s+data(\.pph21_bawaan)?\s+import|import\s+data\.pph21_bawaan)", re.M)
    backend = ROOT / "backend"
    pemuat = set()
    for f in backend.rglob("*.py"):
        rel = f.relative_to(backend).as_posix()
        if rel.startswith(("tests/", "tests_mem/")) or "__pycache__" in rel or f.name.startswith("test_"):
            continue
        teks = f.read_text(encoding="utf-8", errors="ignore")
        if nama.search(teks):
            pemuat.add(rel)
        if rel.startswith("services/"):     # mesin gaji tidak mengimpor bawaan
            assert not impor.search(teks), rel
    assert not any(p.startswith("services/") for p in pemuat), pemuat
    assert pemuat == {"data/pph21_bawaan.py", "config_catalog_ops.py"}, pemuat


def _jalankan_pemuat(berkas: Path, *mode: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PEMUAT), "--file", str(berkas), *mode], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)


def test_PK46_U11_pemuat_dry_run_dan_titik_bertentangan(tmp_path):
    r = _jalankan_pemuat(DATA / "pph21_sintetis.json", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    for k in ENAM:
        assert k in r.stdout, k
    assert "Berlaku sejak     : 2027-01-01" in r.stdout
    assert "tidak ada yang ditulis" in r.stdout
    salah = copy.deepcopy(SINTETIS)
    salah["titik_uji"][1]["tarif_pct"] = 9          # kategori A, bruto 5.000.000: tabel A memberi 1%
    berkas = tmp_path / "pph21_salah.json"
    berkas.write_text(json.dumps(salah), encoding="utf-8")
    r = _jalankan_pemuat(berkas, "--dry-run")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "titik_uji #2 (kategori A, bruto 5.000.000)" in r.stdout, r.stdout
    assert "9%" in r.stdout and "memberi 1%" in r.stdout


# ── U12–U13: tabel pemilik — MENUNGGU BERKAS (H4) ──────────────────────────────────────────────────────────────────────
def _muat_modul_pemuat():
    import importlib.util
    spec = importlib.util.spec_from_file_location("muat_pph21_terverifikasi", PEMUAT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _mulai_dari_bawaan(db):
    """Baris uji U3–U8 dicabut supaya U12–U13 hanya melihat bawaan + berkas pemilik (fixture database tiruan)."""
    await db.config_values.delete_many({"key": {"$in": list(ENAM)}})


@pytest.mark.skipif(not BERKAS_PEMILIK.exists(), reason=H4)
async def test_PK46_U13_slip_sebelum_berlaku_tidak_berubah_sesudah_apply(klien, kepala_admin, karyawan, db):
    mod = _muat_modul_pemuat()
    data = json.loads(BERKAS_PEMILIK.read_text(encoding="utf-8"))
    nilai = mod.periksa(data)
    await _mulai_dari_bawaan(db)
    d = datetime.date.fromisoformat(mod._tanggal(data["berlaku_sejak"], "berlaku_sejak"))
    sebelum = (d.replace(day=1) - datetime.timedelta(days=1))                      # periode tepat sebelum berlaku
    dua = (sebelum.replace(day=1) - datetime.timedelta(days=1))
    periode = [sebelum.strftime("%Y-%m"), dua.strftime("%Y-%m")]
    awal = {p: (await _slip(klien, kepala_admin, p))["pph21"] for p in periode}
    await mod.terapkan(data, nilai, aktor="uji PK-46")
    assert {p: (await _slip(klien, kepala_admin, p))["pph21"] for p in periode} == awal


@pytest.mark.skipif(not BERKAS_PEMILIK.exists(), reason=H4)
async def test_PK46_U12_titik_uji_pemilik_sesudah_apply(db):
    mod = _muat_modul_pemuat()
    data = json.loads(BERKAS_PEMILIK.read_text(encoding="utf-8"))
    nilai = mod.periksa(data)
    await _mulai_dari_bawaan(db)
    await mod.terapkan(data, nilai, aktor="uji PK-46")
    aturan = await pay.aturan_pph21(mod._tanggal(data["berlaku_sejak"], "berlaku_sejak"))
    per_kat: dict = {}
    for t in data["titik_uji"]:
        per_kat[t["kategori"]] = per_kat.get(t["kategori"], 0) + 1
        harap = mod._persen(t["tarif_pct"], "titik_uji") / 100
        assert pay.ter_rate(t["kategori"], mod._rupiah(t["bruto"], "titik_uji"), aturan) == pytest.approx(harap, abs=1e-12), t
    assert set(per_kat) == {"A", "B", "C"} and min(per_kat.values()) >= 5, per_kat
