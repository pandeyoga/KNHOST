"""PK-46 — muat tabel PPh 21 TERVERIFIKASI pemilik ke Pusat Pengaturan sebagai pengaturan bertanggal berlaku.

    python scripts/muat_pph21_terverifikasi.py --file docs/blueprint/data/pph21_terverifikasi.json --dry-run
    python scripts/muat_pph21_terverifikasi.py --file <berkas> --apply

Berkas berbentuk seperti `docs/blueprint/unit/PK-46.md` bagian Data (sumber, diverifikasi_oleh, tanggal_verifikasi,
berlaku_sejak, ter{A,B,C}, ptkp_ke_ter, ptkp, pasal17, biaya_jabatan, titik_uji). Isinya diisi PEMILIK; skrip ini tidak
pernah mengisi, melengkapi, atau menebak angka (keputusan K-42, titik henti H4).

Pemeriksaan (keduanya mode):
- tiap tabel berlapis lolos aturan `tarif_berjenjang` registry — aturan yang sama dengan simpan lewat Pusat Pengaturan
  (daftar tidak kosong, batas atas naik tegas, tepat baris terakhir tanpa batas, tarif 0–100); kategori A, B, C wajib ada;
- `ptkp_ke_ter` hanya memetakan ke A/B/C dan setiap statusnya punya PTKP; biaya jabatan dalam batas registry;
- `titik_uji`: paling sedikit lima per kategori, dan tiap titik cocok dengan tabel di berkas yang sama
  (dihitung dengan `ter_rate` mesin gaji).

`--dry-run` hanya mencetak enam kunci dan tanggal berlakunya. `--apply` menulis enam kunci lewat
`config_resolver.set_value(..., scope_type="global", effective_from=berlaku_sejak, reason="Tabel terverifikasi: …")`
(append-only; baris yang identik sudah ada dilewati). Menjalankan `--apply` di DATA NYATA = titik henti H3 (keputusan
pemilik). Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`).
Keluar 0 bila berkas sah (dan, pada `--apply`, tertulis); 1 bila berkas tidak sah; 2 bila argumen salah.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import config_registry as registry  # noqa: E402

KUNCI = ("hr.pph21.ter_table", "hr.pph21.ptkp_to_ter", "hr.ptkp_table", "hr.pph21.pasal17_table",
         "hr.pph21.biaya_jabatan_pct", "hr.pph21.biaya_jabatan_maks_bulanan")
KATEGORI = ("A", "B", "C")
MIN_TITIK_PER_KATEGORI = 5
WAJIB = ("sumber", "diverifikasi_oleh", "tanggal_verifikasi", "berlaku_sejak", "ter", "ptkp_ke_ter", "ptkp",
         "pasal17", "biaya_jabatan", "titik_uji")
PELAKU = "muat_pph21_terverifikasi"


class BerkasTidakSah(ValueError):
    def __init__(self, pesan: List[str]):
        super().__init__("\n".join(pesan))
        self.pesan = pesan


# ── pengurai nilai berkas (angka atau teks angka; tidak pernah menebak) ────────────────────────────────────────────────
def _rupiah(v: Any, tempat: str, boleh_kosong: bool = False) -> Any:
    if v is None and boleh_kosong:
        return None
    if isinstance(v, bool):
        raise ValueError(f"{tempat}: harus rupiah, bukan Ya/Tidak.")
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        s = re.sub(r"(?i)^rp\.?", "", v.strip()).replace(" ", "")
        if re.fullmatch(r"\d+", s):
            return int(s)
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            return int(s.replace(".", ""))
    raise ValueError(f"{tempat}: {v!r} bukan rupiah bulat yang sah (tulis mis. 5400000 atau 5.400.000).")


def _persen(v: Any, tempat: str) -> float:
    if isinstance(v, bool):
        raise ValueError(f"{tempat}: harus persen, bukan Ya/Tidak.")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().rstrip("%").strip()
        if "," in s and "." not in s and s.count(",") == 1:
            s = s.replace(",", ".")
        if re.fullmatch(r"\d+(\.\d+)?", s):
            return float(s)
    raise ValueError(f"{tempat}: {v!r} bukan persen yang sah (tulis mis. 0.25 untuk 0,25%).")


def _tanggal(v: Any, tempat: str) -> str:
    try:
        return date.fromisoformat(str(v)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{tempat}: {v!r} bukan tanggal TTTT-BB-HH.") from exc


def _jenjang(rows: Any, tempat: str, galat: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        galat.append(f"{tempat}: harus daftar baris {{batas_atas, tarif_pct}}.")
        return []
    out = []
    for i, r in enumerate(rows, 1):
        t = f"{tempat} baris {i}"
        if not isinstance(r, dict) or "batas_atas" not in r or "tarif_pct" not in r:
            galat.append(f"{t}: wajib berisi batas_atas dan tarif_pct.")
            continue
        try:
            out.append({"batas_atas": _rupiah(r["batas_atas"], f"{t} batas_atas", boleh_kosong=True),
                        "tarif_pct": _persen(r["tarif_pct"], f"{t} tarif_pct")})
        except ValueError as exc:
            galat.append(str(exc))
    return out


def _coerce(kunci: str, nilai: Any, galat: List[str]) -> Any:
    try:
        return registry.coerce(registry.require(kunci), nilai)
    except ValueError as exc:
        galat.append(f"{kunci}: {exc}")
        return None


def _rp(n: Any) -> str:
    return "tanpa batas" if n is None else f"{n:,.0f}".replace(",", ".")


def _pct(p: float) -> str:
    return f"{p:g}".replace(".", ",") + "%"


# ── pemeriksaan ───────────────────────────────────────────────────────────────────────────────────────────────────────
def periksa(data: Any) -> Dict[str, Any]:
    """Nilai enam kunci (bentuk registry) dari berkas; `BerkasTidakSah` berisi SEMUA pesan bila tidak sah."""
    galat: List[str] = []
    if not isinstance(data, dict):
        raise BerkasTidakSah(["Berkas harus objek JSON {…}."])
    hilang = [k for k in WAJIB if k not in data]
    if hilang:
        raise BerkasTidakSah([f"Bidang wajib tidak ada: {', '.join(hilang)}."])
    for k in ("sumber", "diverifikasi_oleh"):
        v = data[k]
        if not isinstance(v, str) or not v.strip() or v.strip().startswith("<"):
            galat.append(f"{k}: wajib diisi pemilik (teks, bukan isian contoh).")
    for k in ("tanggal_verifikasi", "berlaku_sejak"):
        try:
            _tanggal(data[k], k)
        except ValueError as exc:
            galat.append(str(exc))

    # TER — tiga kategori, masing-masing tabel berlapis
    ter = data["ter"]
    flat: List[Dict[str, Any]] = []
    g_ter: List[str] = []
    if not isinstance(ter, dict):
        g_ter.append("ter: harus objek {\"A\": [...], \"B\": [...], \"C\": [...]}.")
    else:
        lain = sorted(set(ter) - set(KATEGORI))
        if lain:
            g_ter.append(f"ter: kategori tidak dikenal {', '.join(lain)} (hanya A, B, C).")
        for k in KATEGORI:
            if k not in ter:
                g_ter.append(f"ter: kategori {k} wajib ada.")
                continue
            flat += [{"kategori": k, **b} for b in _jenjang(ter[k], f"ter.{k}", g_ter)]
    galat += g_ter
    nilai: Dict[str, Any] = {}
    if not g_ter:
        nilai["hr.pph21.ter_table"] = _coerce("hr.pph21.ter_table", flat, galat)

    # Pemetaan status → kategori, PTKP setahun
    peta, ptkp = data["ptkp_ke_ter"], data["ptkp"]
    if not isinstance(peta, dict) or not peta:
        galat.append("ptkp_ke_ter: harus objek {status PTKP: kategori} dan tidak kosong.")
        peta = {}
    for st, kat in peta.items():
        if kat not in KATEGORI:
            galat.append(f"ptkp_ke_ter.{st}: kategori {kat!r} tidak dikenal (hanya A, B, C).")
    ptkp_bersih: Dict[str, int] = {}
    if not isinstance(ptkp, dict) or not ptkp:
        galat.append("ptkp: harus objek {status PTKP: rupiah setahun} dan tidak kosong.")
    else:
        for st, v in ptkp.items():
            try:
                ptkp_bersih[str(st)] = _rupiah(v, f"ptkp.{st}")
            except ValueError as exc:
                galat.append(str(exc))
        tanpa = sorted(set(peta) - set(ptkp_bersih))
        if tanpa:
            galat.append(f"ptkp: status {', '.join(tanpa)} ada di ptkp_ke_ter tetapi tidak punya PTKP setahun.")
    nilai["hr.pph21.ptkp_to_ter"] = _coerce("hr.pph21.ptkp_to_ter", dict(peta), galat)
    nilai["hr.ptkp_table"] = _coerce("hr.ptkp_table", ptkp_bersih, galat)

    # Pasal 17 dan biaya jabatan
    g17: List[str] = []
    p17 = _jenjang(data["pasal17"], "pasal17", g17)
    galat += g17
    if not g17:
        nilai["hr.pph21.pasal17_table"] = _coerce("hr.pph21.pasal17_table", p17, galat)
    bj = data["biaya_jabatan"]
    if not isinstance(bj, dict) or "tarif_pct" not in bj or "maks_bulanan" not in bj:
        galat.append("biaya_jabatan: wajib berisi tarif_pct dan maks_bulanan.")
    else:
        try:
            nilai["hr.pph21.biaya_jabatan_pct"] = _coerce(
                "hr.pph21.biaya_jabatan_pct", _persen(bj["tarif_pct"], "biaya_jabatan.tarif_pct"), galat)
            nilai["hr.pph21.biaya_jabatan_maks_bulanan"] = _coerce(
                "hr.pph21.biaya_jabatan_maks_bulanan", _rupiah(bj["maks_bulanan"], "biaya_jabatan.maks_bulanan"), galat)
        except ValueError as exc:
            galat.append(str(exc))

    # Titik uji — cocok dengan tabel di berkas yang sama
    if not galat:
        galat += _periksa_titik(data["titik_uji"], nilai["hr.pph21.ter_table"])
    if galat:
        raise BerkasTidakSah(galat)
    return nilai


def _periksa_titik(titik: Any, ter_table: List[Dict[str, Any]]) -> List[str]:
    from services.hr_payroll_service import ter_rate  # algoritme yang sama dengan mesin gaji
    galat: List[str] = []
    if not isinstance(titik, list):
        return ["titik_uji: harus daftar {kategori, bruto, tarif_pct}."]
    aturan = {"ter": {}}
    for r in ter_table:
        aturan["ter"].setdefault(r["kategori"], []).append({"batas_atas": r["batas_atas"], "tarif_pct": r["tarif_pct"]})
    jumlah = {k: 0 for k in KATEGORI}
    for i, t in enumerate(titik, 1):
        tempat = f"titik_uji #{i}"
        if not isinstance(t, dict):
            galat.append(f"{tempat}: harus objek {{kategori, bruto, tarif_pct}}.")
            continue
        kat = t.get("kategori")
        if kat not in KATEGORI:
            galat.append(f"{tempat}: kategori {kat!r} tidak dikenal (hanya A, B, C).")
            continue
        try:
            bruto = _rupiah(t.get("bruto"), f"{tempat} bruto")
            harap = _persen(t.get("tarif_pct"), f"{tempat} tarif_pct")
        except ValueError as exc:
            galat.append(str(exc))
            continue
        jumlah[kat] += 1
        dapat = ter_rate(kat, bruto, aturan) * 100
        if abs(dapat - harap) > 1e-9:
            galat.append(f"{tempat} (kategori {kat}, bruto {_rp(bruto)}): berkas menulis {_pct(harap)}, "
                         f"tetapi tabel kategori {kat} di berkas yang sama memberi {_pct(round(dapat, 10))}.")
    for k, n in jumlah.items():
        if n < MIN_TITIK_PER_KATEGORI:
            galat.append(f"titik_uji: kategori {k} hanya {n} titik; wajib paling sedikit {MIN_TITIK_PER_KATEGORI} "
                         "(batas bawah, tengah, tepat di satu batas atas, di atas Rp100.000.000, di atas batas tertinggi).")
    return galat


def alasan(data: Dict[str, Any]) -> str:
    return f"Tabel terverifikasi: {data['sumber']} — {data['diverifikasi_oleh']}, {data['tanggal_verifikasi']}"


def ringkas(kunci: str, nilai: Any) -> str:
    if kunci == "hr.pph21.ter_table":
        per = {k: [r for r in nilai if r["kategori"] == k] for k in KATEGORI}
        return " · ".join(f"{k}: {len(rows)} baris, tertinggi {_pct(rows[-1]['tarif_pct'])}" for k, rows in per.items())
    if kunci == "hr.pph21.pasal17_table":
        return " · ".join(f"{'sisanya' if r['batas_atas'] is None else '≤ ' + _rp(r['batas_atas'])}: "
                          f"{_pct(r['tarif_pct'])}" for r in nilai)
    if isinstance(nilai, dict):
        return ", ".join(f"{k}={_rp(v) if isinstance(v, (int, float)) else v}" for k, v in nilai.items())
    if kunci.endswith("_pct"):
        return _pct(float(nilai))
    return f"Rp {_rp(nilai)}"


# ── tulis ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def terapkan(data: Dict[str, Any], nilai: Dict[str, Any], aktor: str = PELAKU) -> List[Tuple[str, str]]:
    """Tulis enam kunci (lapisan grup, berlaku sejak `berlaku_sejak`). Baris identik yang sudah ada dilewati."""
    from db import db
    from services import config_resolver as resolver
    eff = _tanggal(data["berlaku_sejak"], "berlaku_sejak")
    hasil: List[Tuple[str, str]] = []
    for kunci in KUNCI:
        ada = await db[resolver.COLL].find_one({"key": kunci, "scope_type": "global", "effective_from": eff,
                                                "value": nilai[kunci], "cleared": {"$ne": True}}, {"_id": 0, "id": 1})
        if ada:
            hasil.append((kunci, f"sudah ada ({ada['id']}) — dilewati"))
            continue
        row = await resolver.set_value(kunci, nilai[kunci], scope_type="global", actor=aktor, reason=alasan(data),
                                       effective_from=eff)
        hasil.append((kunci, f"ditulis {row['id']}"))
    return hasil


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Muat tabel PPh 21 terverifikasi pemilik (PK-46).")
    ap.add_argument("--file", required=True, help="berkas JSON pemilik (docs/blueprint/data/pph21_terverifikasi.json)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="periksa dan cetak saja; tidak menulis apa pun")
    mode.add_argument("--apply", action="store_true", help="tulis ke Pusat Pengaturan (data nyata = titik henti H3)")
    args = ap.parse_args(argv)

    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"GAGAL membaca {args.file}: {exc}")
        return 1
    try:
        nilai = periksa(data)
    except BerkasTidakSah as exc:
        print(f"BERKAS TIDAK SAH — {len(exc.pesan)} masalah, tidak ada yang ditulis:")
        for p in exc.pesan:
            print(f"  ✗ {p}")
        return 1

    eff = _tanggal(data["berlaku_sejak"], "berlaku_sejak")
    print(f"Sumber            : {data['sumber']}")
    print(f"Diverifikasi oleh : {data['diverifikasi_oleh']} ({data['tanggal_verifikasi']})")
    print(f"Berlaku sejak     : {eff} (lapisan grup; slip periode sebelum tanggal ini tetap memakai tabel lama)")
    print(f"Alasan perubahan  : {alasan(data)}")
    for kunci in KUNCI:
        print(f"  {kunci:<38} {registry.require(kunci)['label']}: {ringkas(kunci, nilai[kunci])}")
    print(f"Titik uji         : {len(data['titik_uji'])} titik cocok dengan tabel di berkas.")
    if eff <= date.today().isoformat():
        print("PERHATIAN: tanggal berlaku sudah lewat — slip periode sesudah tanggal itu yang dihitung ulang akan "
              "memakai tabel ini.")
    if args.dry_run:
        print("Mode --dry-run: tidak ada yang ditulis.")
        return 0
    for kunci, ket in asyncio.run(terapkan(data, nilai)):
        print(f"  {kunci:<38} {ket}")
    print("Selesai: enam kunci dimuat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
