"""KF-T8 — pembangkit nilai uji putaran pengaturan (`test_KFT8_putaran_pengaturan.py`, INV-CFG-08).

Asal: `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py` (`alt_value`, `bad_value`, `same`, `dig`) — arsip
tidak diubah. Bedanya: kunci daftar dan tabel kini benar-benar diubah (dulu hanya disimpan ulang dengan nilai sama).
`calon_lain` memberi calon berurutan — bentuk spesifikasi KF-T8 dulu, lalu bentuk cadangan, terakhir bawaan registry:

  `list`                 tambah satu butir sah (pilihan / peran / bulat menaik / teks; `value_format="regex"` → butir
                         `"uji\\d+"`) · cadangan: buang butir terakhir
  `table` ber-`columns`  tambah satu baris berisi bawaan kolom (kolom pilihan yang bawaannya sudah dipakai baris lain
                         → pilihan pertama yang belum dipakai) · cadangan: buang baris terakhir
  `table` peta           tambah pasangan `"UJI": 1` (nilai mengikuti tipe kolom nilai: pilihan → pilihan pertama) ·
                         cadangan: pasangan pertama diberi nilai lain
  `table` berjenjang     tarif baris terakhir ± 1 (baris bawaan kolom tidak sah untuk tabel tarif berjenjang)
  `table` JSON           simpan ulang (`[]`)
  `text` biasa           + " uji" · cadangan: kata pertama `example` registry (mis. nomor telepon)

Uji memakai calon pertama yang DITERIMA server (400 = pemeriksa domain di luar metadata registry menolak calon itu, mis.
peran pada kunci peta atau nomor WhatsApp); bila semua calon ditolak, kasusnya merah.

Semua fungsi murni (tanpa basis data); pilihan rujukan master (`ref`) diberikan pemanggil.
"""
import copy
import datetime
import json
from typing import Any, Dict, List, Optional, Sequence

#: Penanda "jalur ini tidak memuat nilai" (berbeda dari nilai None yang sah).
TAK_ADA = ("<tak ada>",)
ANGKA = ("int", "duration", "pct", "money", "decimal")


def gali(doc: Any, path: str) -> Any:
    """Nilai dot-path di dokumen bersarang; `TAK_ADA` bila tidak ada."""
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return TAK_ADA
        cur = cur[p]
    return cur


def sama(a: Any, b: Any) -> bool:
    """Sama secara nilai: angka toleran int/float, bool ketat, daftar/peta dibandingkan per butir."""
    if a is TAK_ADA or b is TAK_ADA:
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(sama(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(sama(x, y) for x, y in zip(a, b))
    return a == b


def _angka_lain(e: Dict[str, Any], base: Any) -> Any:
    lo, hi = e.get("min"), e.get("max")
    if e["type"] == "pct":
        lo = 0 if lo is None else lo
        hi = 100 if hi is None else hi
    try:
        b = float(base if base not in (None, "") else 0)
    except (TypeError, ValueError):
        b = 0.0
    bulat = e["type"] in ("int", "duration")
    langkah = [1, -1]
    if not bulat:
        st = float(e.get("step") or 0)
        langkah += ([st, -st] if st else []) + [0.1, -0.1, 0.01, -0.01]
    calon = [b + d for d in langkah]
    calon += [x for x in (lo, hi) if x is not None]
    if lo is not None and hi is not None:
        calon.append((lo + hi) / 2)
    for v in calon:
        v = int(round(v)) if bulat else round(v, 4)
        if (lo is None or v >= lo) and (hi is None or v <= hi) and not sama(v, b):
            return v
    return None


def _peran_dikenal() -> List[str]:
    from role_registry import role_ids
    return list(role_ids())


def _butir_baru(e: Dict[str, Any], base: List[Any]) -> Any:
    """Satu butir sah yang belum ada di daftar, atau TAK_ADA."""
    items = e.get("items") or ""
    if e.get("value_format") == "regex":
        return "uji\\d+" if "uji\\d+" not in base else TAK_ADA
    if items == "options":
        return next((o["value"] for o in e.get("options") or [] if o["value"] not in base), TAK_ADA)
    if items == "roles":
        return next((r for r in _peran_dikenal() if r not in base), TAK_ADA)
    if items == "int_asc":
        return (max(int(x) for x in base) if base else 0) + 1
    if items == "text":
        return next(f"uji{i}" for i in range(1, 1000) if f"uji{i}" not in base)
    return TAK_ADA


def _daftar_lain(e: Dict[str, Any], base: Any) -> List[Any]:
    base = list(base if isinstance(base, list) else (e.get("default") or []))
    out: List[Any] = []
    baru = _butir_baru(e, base)
    if baru is not TAK_ADA:
        out.append(base + [baru])
    if base:
        out.append(base[:-1])
    return out


def _bawaan_kolom(c: Dict[str, Any]) -> Any:
    if "default" in c:
        return copy.deepcopy(c["default"])
    t = c.get("type")
    if t == "bool":
        return False
    if t in ANGKA:
        return 0
    if t == "enum":
        return (c.get("options") or [{"value": ""}])[0]["value"]
    return ""


def _baris_baru(e: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    baris: Dict[str, Any] = {}
    for c in e.get("columns") or []:
        v = _bawaan_kolom(c)
        if c.get("type") == "enum":
            dipakai = {r.get(c["name"]) for r in rows if isinstance(r, dict)}
            if v in dipakai:
                v = next((o["value"] for o in c.get("options") or [] if o["value"] not in dipakai), v)
        baris[c["name"]] = v
    return baris


def _nilai_kolom_lain(c: Dict[str, Any], v: Any) -> Any:
    """Nilai lain untuk satu sel: pilihan berikutnya, angka + 1, teks + " uji"."""
    if c.get("type") == "enum":
        return next((o["value"] for o in c.get("options") or [] if o["value"] != v), TAK_ADA)
    if c.get("type") in (None, "", *ANGKA) and isinstance(v, (int, float)) and not isinstance(v, bool):
        return v + 1
    if isinstance(v, str):
        return (v + " uji").strip()
    return TAK_ADA


def _tabel_lain(e: Dict[str, Any], base: Any) -> List[Any]:
    shape = e.get("row_shape") or "json"
    if shape == "json":
        return []                                          # satu-satunya bentuk yang tetap simpan ulang
    if e.get("value_format") == "tarif_berjenjang":
        rows = copy.deepcopy(base if isinstance(base, list) and base else e.get("default") or [])
        if not rows:
            return []
        akhir = rows[-1]
        t = float(akhir.get("tarif_pct") or 0)
        akhir["tarif_pct"] = t + 1 if t + 1 <= 100 else t - 1
        return [rows]
    if shape == "map":
        peta = dict(base if isinstance(base, dict) else (e.get("default") or {}))
        kol = next((c for c in e.get("columns") or [] if c.get("name") == "__value"), {})
        out: List[Any] = []
        if "UJI" in peta:
            out.append({k: v for k, v in peta.items() if k != "UJI"})
        else:
            if kol.get("type") == "enum":
                nilai: Any = (kol.get("options") or [{"value": 1}])[0]["value"]
            elif kol.get("type") in (None, "", *ANGKA):
                nilai = 1
            else:
                nilai = "uji"
            out.append({**peta, "UJI": nilai})
        if peta:                                           # pasangan pertama diberi nilai lain (kunci peta tetap)
            k0 = next(iter(peta))
            lain = _nilai_kolom_lain(kol, peta[k0])
            if lain is not TAK_ADA:
                out.append({**peta, k0: lain})
        return out
    if shape == "grouped_list":
        grup = copy.deepcopy(base if isinstance(base, dict) else (e.get("default") or {}))
        isi = next(((k, v) for k, v in grup.items() if isinstance(v, list) and v), None)
        if not isi:
            return []
        k, v = isi
        grup[k] = v[:-1] if len(v) > 1 else v + [copy.deepcopy(v[-1])]
        return [grup]
    rows = list(base if isinstance(base, list) else (e.get("default") or []))
    out = [rows + [_baris_baru(e, rows)]]
    if rows:
        out.append(rows[:-1])
    return out


def _teks_lain(e: Dict[str, Any], base: Any, opsi_ref: Sequence[str]) -> List[Any]:
    teks = "" if base is None else str(base)
    if e.get("ref"):
        return [o for o in opsi_ref if str(o).lower() != teks.lower()]
    fmt = e.get("value_format") or ""
    if fmt == "json_map":
        try:
            obj = json.loads(teks) if teks.strip() else {}
        except ValueError:
            obj = {}
        if not isinstance(obj, dict):
            obj = {}
        if "UJI" in obj:
            obj.pop("UJI")
        else:
            obj["UJI"] = 1
        return [json.dumps(obj)]
    if fmt == "date":
        try:
            d = datetime.date.fromisoformat(teks.strip())
        except ValueError:
            return ["2026-01-01"]
        return [(d + datetime.timedelta(days=1)).isoformat()]
    if fmt == "multiline":
        return [(teks + "\nuji").strip()]
    out: List[Any] = [(teks + " uji").strip()]
    contoh = str(e.get("example") or "").split()
    if contoh:                                             # kata pertama contoh registry (mis. nomor telepon)
        out.append(contoh[0])
    return out


def calon_lain(e: Dict[str, Any], base: Any, opsi_ref: Sequence[str] = ()) -> List[Any]:
    """Calon nilai SAH ≠ `base` untuk entri registry `e`, urut: bentuk spesifikasi dulu, lalu bentuk cadangan
    (buang butir/baris terakhir, ubah pasangan pertama, kata pertama contoh registry), terakhir bawaan registry.
    Pemanggil memakai calon pertama yang diterima server: pemeriksa domain di luar metadata registry (mis. nomor
    WhatsApp, peran pada kunci peta) boleh menolak calon tertentu. `[]` untuk tabel JSON (simpan ulang)."""
    t = e["type"]
    if t == "bool":
        calon: List[Any] = [not bool(base)]
    elif t in ANGKA:
        calon = [_angka_lain(e, base)]
    elif t == "enum":
        calon = [o["value"] for o in e.get("options") or [] if o["value"] != base]
    elif t == "text":
        calon = _teks_lain(e, base, opsi_ref)
    elif t == "list":
        calon = _daftar_lain(e, base)
    elif t == "table":
        calon = _tabel_lain(e, base)
    else:
        calon = []
    if not simpan_ulang(e):
        calon.append(copy.deepcopy(e.get("default")))
    out: List[Any] = []
    for v in calon:
        if v is None and e.get("default") is not None:
            continue
        if v is TAK_ADA or sama(v, base) or any(sama(v, x) for x in out):
            continue
        out.append(v)
    return out


def nilai_lain(e: Dict[str, Any], base: Any, opsi_ref: Sequence[str] = ()) -> Any:
    """Calon pertama `calon_lain`; `None` bila tidak ada (tabel JSON = simpan ulang)."""
    calon = calon_lain(e, base, opsi_ref)
    return calon[0] if calon else None


def simpan_ulang(e: Dict[str, Any]) -> bool:
    """Benar hanya untuk tabel JSON — satu-satunya tipe yang diuji dengan menyimpan ulang nilai yang sama."""
    return e["type"] == "table" and (e.get("row_shape") or "json") == "json"


def nilai_tak_sah(e: Dict[str, Any]) -> List[Any]:
    """Nilai yang WAJIB ditolak 400: di luar batas, pilihan tak dikenal, tipe salah."""
    t = e["type"]
    lo, hi = e.get("min"), e.get("max")
    out: List[Any] = []
    if t == "bool":
        out.append("bukan-bool")
    elif t in ANGKA:
        if hi is not None:
            out.append(hi + 1_000_000)
        if lo is not None:
            out.append(lo - 1_000_000)
        if t == "pct" and hi is None:
            out.append(150)
        out.append("abc")
    elif t == "enum":
        out.append("__tidak_ada__")
    elif t == "text":
        out.append(12345)
        fmt = e.get("value_format") or ""
        if e.get("ref"):
            out.append("__tidak_ada__")
        elif fmt == "json_map":
            out.append("{patah")
        elif fmt == "date":
            out.append("bukan-tanggal")
    elif t == "list":
        out.append("bukan-daftar")
        items = e.get("items") or ""
        if e.get("value_format") == "regex":
            out.append(["("])
        elif items in ("options", "roles"):
            out.append(["__tidak_ada__"])
        elif items == "int_asc":
            out.append([0])
        elif items == "text":
            out.append([""])
    elif t == "table":
        out.append("bukan-tabel")
        if e.get("value_format") == "tarif_berjenjang":
            out.append([])
    return out


def ringkas(v: Any, n: int = 120) -> str:
    """Teks pendek sebuah nilai untuk pesan gagal."""
    if v is TAK_ADA:
        return "<tak ada>"
    s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else repr(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def opsi_dari(rows: Optional[Sequence[Dict[str, Any]]]) -> List[str]:
    """Nilai pilihan rujukan (`ref_options`) sebagai daftar teks."""
    return [str(o.get("value")) for o in rows or [] if o.get("value") not in (None, "")]
