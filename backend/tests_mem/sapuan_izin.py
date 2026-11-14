#!/usr/bin/env python3
"""PR-T8 — INV-PERM-02: penjaga matriks izin BERJALAN (peran × endpoint) di lingkungan B.

    python backend/tests_mem/sapuan_izin.py                    # mode cepat: lima akun pertama
    python backend/tests_mem/sapuan_izin.py --penuh            # + 13 peran bawaan (GET) + 12 peran "{peran} Kosong"
    python backend/tests_mem/sapuan_izin.py --awalan /api/costing --keluaran /tmp/sapuan.json
    python backend/tests_mem/sapuan_izin.py --uji-diri         # bukti-merah penilai M0–M8 (tanpa aplikasi)

Aplikasi utuh dinyalakan di atas database tiruan (`boot_app`, PK-02; tidak pernah menyentuh MongoDB asli). Peran uji
dibuat lewat `POST /api/access/roles`, akun lewat `POST /api/users`, sesinya lewat `POST /api/auth/login`. Satu-satunya
fixture sisip: sesi Admin pembuat (sandi seed acak, pola `conftest.sesi`). Lalu tiap rute `/api/*` dipanggil oleh tiap
akun — paling lemah dulu, supaya tulisan yang lolos tidak mengubah hasil akun berikutnya — dan hasilnya dinilai:

  kelas jawaban  ditolak = 401/403 · tak_teruji = 422 · galat = 5xx/pengecualian · lolos = lainnya (termasuk 404)
  izin diminta   header `X-Permission-Denied`; tanpa header: teks lama "Permission ditolak: <sumber daya>.<aksi>"
                 digabung dengan jejak pemeriksa inti (`dependencies.has_permission` / `require_permission` /
                 `require_any_permission`: pasangan yang diperiksa dan tidak dipegang selama permintaan itu)

  M0  tanpa_token lolos di luar PUBLIC_ALLOWLIST (scripts/guardrails/verify_auth_coverage.py)
  M1  kosong lolos di luar LOGIN_ONLY (backend/login_only_endpoints.py), PUBLIC_ALLOWLIST, dan `menunggu_unit`
  M2  penuh mendapat 403 pada GET di luar `tolak_bukan_izin`
  M3  mgr0 (peran dasar Manajer, semua modul "Tidak ada") lolos pada rute yang menolak kosong (rute PUBLIC_ALLOWLIST
      tidak dinilai M3–M5: jawabannya tidak bergantung pada peran)
  M4  (--penuh) "{peran} Kosong" lolos pada rute yang menolak kosong
  M5  (--penuh) peran bawaan ditolak 403 dengan izin yang DIPEGANGNYA, atau lolos pada rute yang bagi kosong ditolak
      dengan izin yang tak satu pun dipegangnya (izin menurut `GET /api/access/roles`)
  M6  rute tak_teruji di luar `tak_teruji`; rute galat di luar `galat_dikenal`
  M7  daftar basi: entri berkas harapan / LOGIN_ONLY / PUBLIC_ALLOWLIST tanpa rute; `menunggu_unit` yang kini menolak
      kosong; `tolak_bukan_izin`/`tak_teruji`/`galat_dikenal` yang tidak lagi terjadi; baris harapan tanpa alasan
  M8  akun uji tidak lagi 200 di `GET /api/auth/me` sesudah sapuan, atau jumlah `users`/`custom_roles` ≠ seed + buatan

Keluar 0 bila tidak ada pelanggaran, 1 bila ada. Aturan untuk endpoint baru: `backend/tests_mem/README.md`.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import collections
import contextlib
import contextvars
import datetime
import io
import json
import os
import re
import secrets
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FOLDER = Path(__file__).resolve().parent
BACKEND = FOLDER.parent
REPO = BACKEND.parent
BERKAS_HARAPAN = FOLDER / "sapuan_izin_harapan.json"
BERKAS_PUBLIK = REPO / "scripts" / "guardrails" / "verify_auth_coverage.py"
PT = "ent_ksc"
BATAS_DETIK = 30          # satu permintaan yang tidak selesai (aliran tanpa akhir) dihitung galat
LEWATI_AWALAN = "/api/auth/logout"

TANPA_TOKEN, KOSONG, PENUH, MGR0, SOPIR = "tanpa_token", "kosong", "penuh", "mgr0", "sopir"
AKUN_CEPAT = (TANPA_TOKEN, KOSONG, PENUH, MGR0, SOPIR)

BAGIAN_BERALASAN = ("tolak_bukan_izin", "menunggu_unit", "tak_teruji", "galat_dikenal")
BAGIAN_HARAPAN = BAGIAN_BERALASAN + ("isi_contoh",)
KUNCI_ISI = {"json", "query", "data", "path", "alasan"}
ALASAN_NAMA = {"reason", "alasan", "note", "notes", "catatan", "keterangan", "remarks", "comment"}
POLA_KUNCI = re.compile(r"^(GET|POST|PUT|PATCH|DELETE) /api/\S*$")

ARTI = {
    "M0": "terbuka tanpa login",
    "M1": "lolos tanpa izin (rute berizin, atau login-saja tanpa putusan)",
    "M2": "menolak pemegang izin",
    "M3": "terbuka karena peran dasar Manajer",
    "M4": "terbuka karena peran dasar",
    "M5": "server tidak mengikuti matriks",
    "M6": "gerbang tidak teruji / galat baru",
    "M7": "daftar basi",
    "M8": "sesi atau akun berubah di tengah sapuan",
}


# ─── Kelas jawaban dan izin yang diminta ────────────────────────────────────
def kelas(kode: int) -> str:
    if kode in (401, 403):
        return "ditolak"
    if kode == 422:
        return "tak_teruji"
    if kode < 0 or kode >= 500:
        return "galat"
    return "lolos"


_POLA_TOLAK = re.compile(r"Permission ditolak:(.*)", re.S)
_POLA_PASANGAN = re.compile(r"\b([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*|\*)")


def _pasangan(teks: str) -> List[str]:
    return list(dict.fromkeys(f"{a}.{b}" for a, b in _POLA_PASANGAN.findall(teks or "")))


def izin_dari_teks(teks: str) -> List[str]:
    """Pola lama `Permission ditolak: order.view` / `… butuh salah satu dari a.b / c.d` → ["order.view", …]."""
    m = _POLA_TOLAK.search(teks or "")
    return _pasangan(m.group(1)) if m else []


def izin_diminta(kode: int, header: str, teks: str, jejak: Sequence[Tuple[str, str, bool]]) -> Optional[List[str]]:
    """Izin yang diminta sebuah penolakan 403. Bukan 403 → None.

    Header `X-Permission-Denied` (PR-T6) bila ada. Tanpa header: pasangan di teks lama DIGABUNG dengan pasangan dari
    jejak pemeriksa inti yang tidak dipegang — teks hanya menyebut pemeriksaan TERAKHIR (mis. `rnd.view` lalu
    `hr.view` → "Permission ditolak: hr.view"), jejak menyebut seluruh rantai "salah satu dari", dan kalimat Z6 tidak
    memuat `x.y`."""
    if kode != 403:
        return None
    if header:
        return _pasangan(header)
    return list(dict.fromkeys(izin_dari_teks(teks) + [f"{sd}.{aksi}" for sd, aksi, ada in jejak if not ada]))


def memegang(izin: Dict[str, List[str]], pasangan: str) -> bool:
    sd, _, aksi = pasangan.partition(".")
    daftar = (izin or {}).get(sd) or []
    return aksi in daftar or "*" in daftar


# ─── Jejak pemeriksa izin inti (hanya selama permintaan sapuan) ─────────────
_JEJAK: "contextvars.ContextVar[Optional[list]]" = contextvars.ContextVar("sapuan_izin_jejak", default=None)


class _DaftarTerekam(list):
    """`aksi in daftar` dicatat (sumber daya, aksi, dipegang?) — pola `has_permission`/`require_any_permission`."""

    sd = ""

    def __contains__(self, aksi):
        ada = list.__contains__(self, aksi)
        j = _JEJAK.get()
        if j is not None and aksi != "*":
            j.append((self.sd, aksi, ada or list.__contains__(self, "*")))
        return ada


class _IzinTerekam(dict):
    def get(self, k, d=None):
        v = dict.get(self, k, d)
        if isinstance(v, list):
            w = _DaftarTerekam(v)
            w.sd = k
            return w
        return v


class _MatriksTerekam(dict):
    def get(self, k, d=None):
        v = dict.get(self, k, d)
        return _IzinTerekam(v) if isinstance(v, dict) else v


def pasang_jejak() -> None:
    """Bungkus `dependencies.permission_matrix` (dipanggil lewat nama global HANYA oleh tiga pemeriksa inti di
    `dependencies.py`). Di luar permintaan sapuan pembungkus mengembalikan matriks apa adanya. Kode aplikasi tidak
    diubah; pembungkus hanya hidup di proses sapuan."""
    import dependencies
    if getattr(dependencies.permission_matrix, "_sapuan_izin", False):
        return
    asli = dependencies.permission_matrix

    async def permission_matrix():
        m = await asli()
        return _MatriksTerekam(m) if _JEJAK.get() is not None and isinstance(m, dict) else m

    permission_matrix._sapuan_izin = True
    permission_matrix._asli = asli
    dependencies.permission_matrix = permission_matrix


def lepas_jejak() -> None:
    import dependencies
    asli = getattr(dependencies.permission_matrix, "_asli", None)
    if asli is not None:
        dependencies.permission_matrix = asli


# ─── Isi permintaan dari skema OpenAPI (dipindahkan dari bukti/t9_tulis_tanpa_izin.py) ─────
class PembuatIsi:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.komp = spec.get("components", {}).get("schemas", {})

    def deref(self, s):
        n = 0
        while isinstance(s, dict) and "$ref" in s and n < 20:
            s = self.komp.get(s["$ref"].split("/")[-1], {})
            n += 1
        return s or {}

    def contoh(self, s, nama: str = "", depth: int = 0):
        """Nilai contoh yang lolos validasi bentuk untuk satu skema."""
        s = self.deref(s)
        if depth > 6:
            return None
        for k in ("anyOf", "oneOf"):
            if k in s:
                pil = [self.deref(x) for x in s[k]]
                non_null = [x for x in pil if x.get("type") != "null"]
                return self.contoh(non_null[0], nama, depth + 1) if non_null else None
        if "allOf" in s:
            gab = {}
            for x in s["allOf"]:
                v = self.contoh(x, nama, depth + 1)
                if isinstance(v, dict):
                    gab.update(v)
                else:
                    return v
            return gab
        if "enum" in s:
            return s["enum"][0]
        if "const" in s:
            return s["const"]
        t = s.get("type")
        if t == "object" or "properties" in s:
            req = set(s.get("required", []))
            return {k: self.contoh(v, k, depth + 1) for k, v in (s.get("properties") or {}).items() if k in req}
        if t == "array":
            n = s.get("minItems", 1)
            return [self.contoh(s.get("items", {}), nama, depth + 1) for _ in range(max(1, n))]
        if t == "integer":
            lo = s.get("minimum", s.get("exclusiveMinimum", 0) + (1 if "exclusiveMinimum" in s else 0))
            return int(max(lo, 1))
        if t == "number":
            lo = s.get("minimum", 0)
            if "exclusiveMinimum" in s:
                lo = s["exclusiveMinimum"] + 1
            return float(max(lo, 1))
        if t == "boolean":
            return True
        if t == "string":
            fmt = s.get("format", "")
            n = nama.lower()
            if fmt == "date" or n.endswith("_date") or n in ("date", "tanggal", "as_of", "due_date"):
                return "2026-11-13"
            if fmt == "date-time" or n.endswith("_at"):
                return "2026-11-13T08:00:00+00:00"
            if fmt == "email" or "email" in n:
                return "uji@contoh.id"
            if "period" in n or n in ("month", "bulan"):
                return "2026-11"
            if s.get("pattern"):
                p = s["pattern"]
                if "\\d{4}-\\d{2}-\\d{2}" in p:
                    return "2026-11-13"
                if "\\d{4}-\\d{2}" in p:
                    return "2026-11"
            if any(t in n for t in ("phone", "telp", "whatsapp")) or n in ("hp", "wa", "no_hp"):
                v = "081234567890"
            elif n in ALASAN_NAMA or n.endswith("_reason"):
                v = "Uji sapuan izin otomatis"     # validator alasan: minimal 5 huruf
            else:
                v = "uji"
            ml = s.get("minLength", 0)
            if ml > len(v):
                v = v + "x" * (ml - len(v))
            if s.get("maxLength") is not None:
                v = v[:max(int(s["maxLength"]), 1)]
            return v
        return {}

    @staticmethod
    def _berkas(s) -> bool:
        return isinstance(s, dict) and (s.get("format") == "binary" or "contentMediaType" in s)

    def _op(self, metode: str, jalur: str) -> Dict[str, Any]:
        kunci = re.sub(r"\{([^}:]+):[^}]*\}", r"{\1}", jalur)          # `{p:path}` → `{p}` (bentuk OpenAPI)
        return (self.spec.get("paths", {}).get(kunci) or {}).get(metode.lower()) or {}

    def jalur_isi(self, metode: str, jalur: str, tetap: Optional[Dict[str, Any]] = None) -> str:
        """Parameter jalur: `x`, kecuali skema menuntut bilangan (→ 1) atau enum (→ nilai pertama); `tetap` menimpa."""
        op = self._op(metode, jalur)
        nilai_ = {}
        for p in op.get("parameters") or []:
            if p.get("in") == "path":
                s = self.deref(p.get("schema", {}))
                pil = [self.deref(x) for x in s.get("anyOf", [s])]
                s = next((x for x in pil if x.get("type") != "null"), s)
                if "enum" in s:
                    nilai_[p["name"]] = str(s["enum"][0])
                elif s.get("type") in ("integer", "number"):
                    nilai_[p["name"]] = "1"
        nilai_.update({k: str(v) for k, v in (tetap or {}).items()})
        return re.sub(r"\{([^}:]+)(:[^}]*)?\}", lambda m: nilai_.get(m.group(1), "x"), jalur)

    def permintaan(self, metode: str, jalur: str) -> Dict[str, Any]:
        """Argumen `httpx.request` (json/data/files/params) untuk satu rute."""
        op = self._op(metode, jalur)
        kw: Dict[str, Any] = {}
        rb = (op.get("requestBody") or {}).get("content") or {}
        if "application/json" in rb:
            kw["json"] = self.contoh(rb["application/json"].get("schema", {}))
        elif "multipart/form-data" in rb:
            s = self.deref(rb["multipart/form-data"].get("schema", {}))
            data, files = {}, {}
            for k in s.get("required", []):
                p = self.deref((s.get("properties") or {}).get(k, {}))
                isi = p.get("items") if p.get("type") == "array" else p
                if self._berkas(self.deref(isi or {})):
                    files[k] = ("uji.txt", b"uji", "text/plain")
                else:
                    data[k] = self.contoh(p, k)
            kw["files"] = files or {"file": ("uji.txt", b"uji", "text/plain")}
            if data:
                kw["data"] = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in data.items()}
        elif "application/x-www-form-urlencoded" in rb:
            kw["data"] = self.contoh(rb["application/x-www-form-urlencoded"].get("schema", {}))
        q = {}
        for p in op.get("parameters") or []:
            if p.get("in") == "query" and p.get("required"):
                q[p["name"]] = self.contoh(p.get("schema", {}), p["name"])
        if q:
            kw["params"] = q
        return kw


# ─── Daftar putusan: berkas harapan, LOGIN_ONLY, PUBLIC_ALLOWLIST ───────────
def muat_publik() -> List[str]:
    """`PUBLIC_ALLOWLIST` dibaca dari sumber penjaga statik (tanpa mengimpornya)."""
    pohon = ast.parse(BERKAS_PUBLIK.read_text())
    for n in pohon.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "PUBLIC_ALLOWLIST" for t in n.targets):
            return sorted(ast.literal_eval(n.value))
    raise SystemExit(f"PUBLIC_ALLOWLIST tidak ditemukan di {BERKAS_PUBLIK}")


def muat_login_saja() -> List[str]:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from login_only_endpoints import LOGIN_ONLY
    return sorted(f"{m} {p}" for m, p in LOGIN_ONLY)


def muat_harapan(path: Path = BERKAS_HARAPAN) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def periksa_harapan(harapan: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Bentuk berkas harapan: [(kunci, masalah)] — baris tanpa alasan ditolak."""
    salah: List[Tuple[str, str]] = []
    for bagian, isi in harapan.items():
        if bagian.startswith("_"):
            continue
        if bagian not in BAGIAN_HARAPAN:
            salah.append((bagian, "bagian tidak dikenal"))
            continue
        if not isinstance(isi, dict):
            salah.append((bagian, "bukan objek"))
            continue
        for kunci, nilai in isi.items():
            if not POLA_KUNCI.match(kunci):
                salah.append((kunci, f"{bagian}: kunci harus 'METODE /api/…'"))
            if bagian in BAGIAN_BERALASAN:
                if not isinstance(nilai, str) or not nilai.strip():
                    salah.append((kunci, f"{bagian}: tanpa alasan"))
            elif not isinstance(nilai, dict) or not set(nilai) <= KUNCI_ISI or not (set(nilai) - {"alasan"}):
                salah.append((kunci, "isi_contoh: harus objek berisi json/query/data/path"))
    if (harapan.get("tolak_bukan_izin") or {}):
        for kunci in harapan["tolak_bukan_izin"]:
            if not kunci.startswith("GET "):
                salah.append((kunci, "tolak_bukan_izin: hanya rute GET (akun penuh hanya menyapu GET)"))
    return salah


# ─── Penilai (fungsi murni atas hasil) ──────────────────────────────────────
@dataclass
class Konteks:
    rute: List[str]                                   # "METODE jalur" yang disapu
    semua_rute: set                                   # "METODE jalur" semua rute /api di aplikasi
    publik: Dict[str, Optional[str]]                  # entri PUBLIC_ALLOWLIST → kunci rute hidup (None = tidak ada)
    login_saja: List[str]
    harapan: Dict[str, Any]
    awalan: str = ""
    akun_kosong_lain: List[str] = field(default_factory=list)       # "{peran} Kosong" selain mgr0 (--penuh)
    peran_izin: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)   # akun peran bawaan → izin
    sesi_akhir: Dict[str, int] = field(default_factory=dict)
    jumlah: Dict[str, Tuple[int, int]] = field(default_factory=dict)            # koleksi → (seed + buatan, nyata)
    pesan: Dict[str, Dict[str, str]] = field(default_factory=dict)


def _dalam(kunci: str, awalan: str) -> bool:
    return kunci.split(" ", 1)[1].startswith(awalan or "/api/")


def nilai(hasil: Dict[str, Dict[str, list]], k: Konteks) -> List[Dict[str, Any]]:
    """Pelanggaran M0–M8 dari hasil sapuan `{akun: {"METODE jalur": [kode, kelas, izin]}}`."""
    out: List[Dict[str, Any]] = []
    H = {b: dict(k.harapan.get(b) or {}) for b in BAGIAN_HARAPAN}

    def tambah(m, kunci, akun, kode=None, catatan=""):
        metode, jalur = kunci.split(" ", 1) if " " in kunci else ("", kunci)
        pesan = (k.pesan.get(akun) or {}).get(kunci, "")
        out.append({"kode": m, "metode": metode, "jalur": jalur, "akun": akun, "jawaban": kode,
                    "pesan": pesan[:80], "catatan": catatan})

    def r(akun, kunci):
        return (hasil.get(akun) or {}).get(kunci)

    def kls(akun, kunci):
        v = r(akun, kunci)
        return v[1] if v else None

    publik_hidup = {v for v in k.publik.values() if v}
    login = set(k.login_saja)
    for kunci in k.rute:
        # M0 — terbuka tanpa login
        if kls(TANPA_TOKEN, kunci) == "lolos" and kunci not in publik_hidup:
            tambah("M0", kunci, TANPA_TOKEN, r(TANPA_TOKEN, kunci)[0])
        # M1 — lolos tanpa izin
        if (kls(KOSONG, kunci) == "lolos" and kunci not in login and kunci not in publik_hidup
                and kunci not in H["menunggu_unit"]):
            tambah("M1", kunci, KOSONG, r(KOSONG, kunci)[0])
        # M2 — menolak pemegang izin
        v = r(PENUH, kunci)
        if v and v[0] == 403 and kunci.startswith("GET ") and kunci not in H["tolak_bukan_izin"]:
            tambah("M2", kunci, PENUH, 403, "izin: " + (", ".join(v[2] or []) or "—"))
        # Rute tanpa sesi (PUBLIC_ALLOWLIST) tidak dinilai M3–M5: jawabannya tidak bergantung pada peran (mis. login
        # yang dikunci sesudah beberapa percobaan gagal → 429 bagi akun yang datang belakangan).
        kosong_tolak = kls(KOSONG, kunci) == "ditolak" and kunci not in publik_hidup
        # M3 — terbuka karena peran dasar Manajer
        if kosong_tolak and kls(MGR0, kunci) == "lolos":
            tambah("M3", kunci, MGR0, r(MGR0, kunci)[0],
                   "juga tertutup bagi Sopir" if kls(SOPIR, kunci) == "ditolak" else "")
        # M4 — terbuka karena peran dasar lain
        for akun in k.akun_kosong_lain:
            if kosong_tolak and kls(akun, kunci) == "lolos":
                tambah("M4", kunci, akun, r(akun, kunci)[0])
        # M5 — peran bawaan vs matriks
        q = (r(KOSONG, kunci) or [None, None, None])[2] or []
        for akun, izin in k.peran_izin.items():
            v = r(akun, kunci)
            if not v:
                continue
            if kunci in publik_hidup:
                continue
            if v[0] == 403 and any(memegang(izin, p) for p in (v[2] or [])):
                tambah("M5", kunci, akun, 403, "ditolak padahal memegang " +
                       ", ".join(p for p in v[2] if memegang(izin, p)))
            elif v[1] == "lolos" and kosong_tolak and q and not any(memegang(izin, p) for p in q):
                tambah("M5", kunci, akun, v[0], "lolos tanpa memegang " + ", ".join(q))
        # M6 — tak teruji / galat (satu baris per rute)
        for jenis, bagian in (("tak_teruji", "tak_teruji"), ("galat", "galat_dikenal")):
            kena = [a for a in hasil if kls(a, kunci) == jenis]
            if kena and kunci not in H[bagian]:
                tambah("M6", kunci, kena[0], r(kena[0], kunci)[0],
                       f"{jenis}" + (f" (juga {len(kena) - 1} akun lain)" if len(kena) > 1 else ""))
    # M7 — daftar basi
    disapu = set(k.rute)
    for kunci, masalah in periksa_harapan(k.harapan):
        tambah("M7", kunci, "", None, f"berkas harapan: {masalah}")
    for bagian in BAGIAN_HARAPAN:
        for kunci in H[bagian]:
            if not POLA_KUNCI.match(kunci) or not _dalam(kunci, k.awalan):
                continue
            if kunci not in k.semua_rute:
                tambah("M7", kunci, "", None, f"{bagian}: rute tidak ada")
                continue
            if kunci not in disapu:
                continue
            if bagian == "menunggu_unit" and kls(KOSONG, kunci) == "ditolak":
                tambah("M7", kunci, KOSONG, r(KOSONG, kunci)[0], "menunggu_unit: kini menolak kosong — hapus barisnya")
            elif bagian == "tolak_bukan_izin" and (r(PENUH, kunci) or [0])[0] != 403:
                tambah("M7", kunci, PENUH, (r(PENUH, kunci) or [None])[0], "tolak_bukan_izin: penuh tidak lagi 403")
            elif bagian == "tak_teruji" and not any(kls(a, kunci) == "tak_teruji" for a in hasil):
                tambah("M7", kunci, "", None, "tak_teruji: tidak lagi 422 — hapus barisnya")
            elif bagian == "galat_dikenal" and not any(kls(a, kunci) == "galat" for a in hasil):
                tambah("M7", kunci, "", None, "galat_dikenal: tidak lagi galat — hapus barisnya")
    for kunci in k.login_saja:
        if _dalam(kunci, k.awalan) and kunci not in k.semua_rute:
            tambah("M7", kunci, "", None, "LOGIN_ONLY: rute tidak ada")
    for entri, hidup in k.publik.items():
        if hidup is None and ("/api" + entri.split(" ", 1)[1]).startswith(k.awalan or "/api/"):
            tambah("M7", entri, "", None, "PUBLIC_ALLOWLIST: rute tidak ada")
    # M8 — sesi dan akun sesudah sapuan
    for akun, kode in k.sesi_akhir.items():
        if kode != 200:
            tambah("M8", "GET /api/auth/me", akun, kode, "sesi akun uji mati di tengah sapuan")
    for koleksi, (harap, nyata) in k.jumlah.items():
        if harap != nyata:
            tambah("M8", koleksi, "", nyata, f"jumlah {koleksi}: harap {harap} (seed + buatan sapuan), nyata {nyata}")
    return out


# ─── Penyapu (aplikasi di dalam proses) ─────────────────────────────────────
@dataclass
class Akun:
    kode: str
    kepala: Dict[str, str]
    hanya_get: bool
    peran: str = ""
    label: str = ""
    dasar: str = ""
    bawaan: bool = False      # akun peran bawaan (mode penuh) — dinilai M5
    kosong_lain: bool = False  # "{peran} Kosong" selain mgr0 (mode penuh) — dinilai M4


def daftar_rute(app, awalan: str = "") -> List[Tuple[str, str]]:
    rute = set()
    for rt in app.routes:
        jalur = getattr(rt, "path", "")
        if not jalur.startswith("/api/") or (awalan and not jalur.startswith(awalan)):
            continue
        if jalur.startswith(LEWATI_AWALAN):
            continue
        for m in (getattr(rt, "methods", None) or set()) - {"HEAD", "OPTIONS"}:
            rute.add((m, jalur))
    return sorted(rute, key=lambda x: (x[1], x[0]))


def semua_kunci_rute(app) -> set:
    return {f"{m} {rt.path}" for rt in app.routes if getattr(rt, "path", "").startswith("/api/")
            for m in (getattr(rt, "methods", None) or set()) - {"HEAD", "OPTIONS"}}


def petakan_publik(publik: Iterable[str], semua: set) -> Dict[str, Optional[str]]:
    """`POST /auth/login` (jalur dekorator) → `POST /api/auth/login` (rute hidup); jalur absolut apa adanya; awalan
    router lain dicocokkan ujung."""
    out: Dict[str, Optional[str]] = {}
    for entri in publik:
        m, p = entri.split(" ", 1)
        if entri in semua:                       # jalur absolut (rute di luar routers/, mis. `server.py`)
            out[entri] = entri
            continue
        if f"{m} /api{p}" in semua:
            out[entri] = f"{m} /api{p}"
            continue
        cocok = [x for x in semua if x.startswith(m + " /api/") and x.endswith(p)]
        out[entri] = cocok[0] if len(cocok) == 1 else None
    return out


def _spec_untuk(app, rute: Sequence[Tuple[str, str]]) -> Dict[str, Any]:
    from fastapi.openapi.utils import get_openapi
    jalur = {p for _, p in rute}
    pilih = [rt for rt in app.routes if getattr(rt, "path", "") in jalur]
    return get_openapi(title=app.title, version=app.version, routes=pilih)


def _detail(r) -> str:
    try:
        d = r.json()
        d = d.get("detail", d) if isinstance(d, dict) else d
        return d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return r.text or ""


async def panggil(c, metode: str, url: str, kepala: Dict[str, str], kw: Dict[str, Any]):
    """→ (kode, pesan, izin_diminta). Cookie dibersihkan supaya tiap permintaan hanya membawa sesinya sendiri."""
    jejak: list = []
    token = _JEJAK.set(jejak)
    try:
        c.cookies.clear()
        r = await asyncio.wait_for(c.request(metode, url, headers=kepala, **kw), BATAS_DETIK)
        kode, pesan, header = r.status_code, (_detail(r) if r.status_code >= 400 else ""), \
            r.headers.get("X-Permission-Denied", "")
    except Exception as exc:  # noqa: BLE001
        kode, pesan, header = -1, f"{type(exc).__name__}: {exc}", ""
    finally:
        _JEJAK.reset(token)
    return kode, pesan, izin_diminta(kode, header, pesan, jejak)


async def _buat_peran(c, HA, label: str, dasar: str, levels: Dict[str, str], ada: set) -> str:
    nama, n = label, 2
    while nama in ada:
        nama, n = f"{label} {n}", n + 1
    ada.add(nama)
    r = await c.post("/api/access/roles", headers=HA, json={"label": nama, "base_role": dasar, "levels": levels,
                                                            "description": "peran sapuan PR-T8"})
    if r.status_code != 200:
        raise SystemExit(f"membuat peran {nama!r} gagal: {r.status_code} {r.text[:200]}")
    j = r.json()
    return (j.get("role") or j)["id"]


async def _buat_akun(c, HA, kode: str, peran: str, nonce: str) -> Dict[str, str]:
    email = f"sapuan.{kode}.{nonce}@uji.id"
    sandi = "Sapuan-" + secrets.token_urlsafe(12)
    r = await c.post("/api/users", headers=HA, json={"name": f"Sapuan {kode}", "email": email, "role": peran,
                                                     "password": sandi, "home_entity_id": PT,
                                                     "allowed_entity_ids": [PT]})
    if r.status_code != 200:
        raise SystemExit(f"membuat akun {kode} ({peran}) gagal: {r.status_code} {r.text[:200]}")
    c.cookies.clear()
    r = await c.post("/api/auth/login", json={"email": email, "password": sandi})
    c.cookies.clear()
    if r.status_code != 200:
        raise SystemExit(f"login akun {kode} gagal: {r.status_code} {r.text[:200]}")
    j = r.json()
    tok = j.get("token") or j.get("session_token") or (j.get("session") or {}).get("token")
    if not tok:
        raise SystemExit(f"login akun {kode}: token tidak ada di jawaban ({sorted(j)})")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": PT}


async def siapkan_akun(c, HA, *, penuh: bool = False) -> Tuple[List[Akun], Dict[str, int]]:
    """Peran dan akun uji, urut paling lemah dulu. → (akun, {"users": dibuat, "custom_roles": dibuat})."""
    mods = (await c.get("/api/access/modules", headers=HA)).json()
    mods = mods.get("modules", mods) if isinstance(mods, dict) else mods
    roles = (await c.get("/api/access/roles", headers=HA)).json()
    roles = roles.get("roles", roles) if isinstance(roles, dict) else roles
    ada = {ro.get("label", "") for ro in roles}
    bawaan = [ro for ro in roles if not ro.get("custom")]
    nonce = uuid.uuid4().hex[:6]
    tidak_ada = {m["id"]: "none" for m in mods}
    tertinggi = {m["id"]: [x for x in ("manage", "view", "none") if x in (m.get("levels_available") or ["none",
                                                                                                         "view",
                                                                                                         "manage"])][0]
                 for m in mods}
    dibuat = {"users": 0, "custom_roles": 0}

    async def peran(label, dasar, levels):
        dibuat["custom_roles"] += 1
        return await _buat_peran(c, HA, label, dasar, levels, ada)

    async def akun(kode, rid, hanya_get, label="", dasar="", is_bawaan=False, kosong_lain=False):
        dibuat["users"] += 1
        return Akun(kode, await _buat_akun(c, HA, kode, rid, nonce), hanya_get, rid, label, dasar, is_bawaan,
                    kosong_lain)

    lemah: List[Akun] = [Akun(TANPA_TOKEN, {"X-Entity-Id": PT}, False)]
    lemah.append(await akun(KOSONG, await peran("Tanpa Acuan Kosong", "", tidak_ada), False, "Tanpa Acuan Kosong"))
    lemah.append(await akun(SOPIR, "driver", False, "Sopir"))
    lemah.append(await akun(MGR0, await peran("Manajer Kosong", "manager", tidak_ada), False, "Manajer Kosong",
                            "manager"))
    if penuh:
        for ro in bawaan:
            if ro["id"] in ("admin", "manager"):
                continue
            lbl = f"{ro.get('label') or ro['id']} Kosong"
            lemah.append(await akun(f"{ro['id']}0", await peran(lbl, ro["id"], tidak_ada), False, lbl, ro["id"],
                                    kosong_lain=True))
    kuat = [await akun(PENUH, await peran("Tanpa Acuan Penuh", "", tertinggi), True, "Tanpa Acuan Penuh")]
    if penuh:
        for ro in bawaan:
            kuat.append(await akun(ro["id"], ro["id"], True, ro.get("label", ""), "", True))
    return lemah + kuat, dibuat


async def jalankan(c, app, HA: Dict[str, str], *, penuh: bool = False, awalan: str = "",
                   harapan: Optional[Dict[str, Any]] = None, keluaran: Optional[str] = None,
                   cetak=print, db=None) -> Tuple[int, Dict[str, Any]]:
    """Sapuan utuh di aplikasi yang sudah menyala (`server.lifespan` dimasuki pemanggil). → (kode keluar, laporan)."""
    if db is None:
        from db import db as _db
        db = _db
    harapan = muat_harapan() if harapan is None else harapan
    t0 = time.monotonic()
    pasang_jejak()
    seed = {k: await db[k].count_documents({}) for k in ("users", "custom_roles")}
    akun, dibuat = await siapkan_akun(c, HA, penuh=penuh)
    rute = daftar_rute(app, awalan)
    pembuat = PembuatIsi(_spec_untuk(app, rute))
    isi_tetap = harapan.get("isi_contoh") or {}
    kw_rute: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for m, p in rute:
        kunci = f"{m} {p}"
        tetap = isi_tetap.get(kunci) or {}
        kw = pembuat.permintaan(m, p)
        for kk in ("json", "data", "query"):            # isi_contoh menggantikan bagian yang disebutnya saja
            if kk in tetap:
                kw[{"query": "params"}.get(kk, kk)] = tetap[kk]
        kw_rute[kunci] = (pembuat.jalur_isi(m, p, tetap.get("path")), kw)
    hasil: Dict[str, Dict[str, list]] = {}
    pesan: Dict[str, Dict[str, str]] = {}
    lama: Dict[str, float] = {}
    for a in akun:
        t1 = time.monotonic()
        res, ps = {}, {}
        for m, p in rute:
            if a.hanya_get and m != "GET":
                continue
            kunci = f"{m} {p}"
            url, kw = kw_rute[kunci]
            kode, teks, izin = await panggil(c, m, url, a.kepala, kw)
            res[kunci] = [kode, kelas(kode), izin]
            if teks:
                ps[kunci] = teks[:300]
        hasil[a.kode], pesan[a.kode] = res, ps
        lama[a.kode] = time.monotonic() - t1
    sesi_akhir = {}
    for a in akun:
        if "Authorization" in a.kepala:
            c.cookies.clear()
            sesi_akhir[a.kode] = (await c.get("/api/auth/me", headers=a.kepala)).status_code
    nyata = {k: await db[k].count_documents({}) for k in ("users", "custom_roles")}
    roles = (await c.get("/api/access/roles", headers=HA)).json()
    roles = roles.get("roles", roles) if isinstance(roles, dict) else roles
    izin_peran = {ro["id"]: ro.get("permissions") or {} for ro in roles}
    semua = semua_kunci_rute(app)
    k = Konteks(rute=[f"{m} {p}" for m, p in rute], semua_rute=semua, publik=petakan_publik(muat_publik(), semua),
                login_saja=muat_login_saja(), harapan=harapan, awalan=awalan,
                akun_kosong_lain=[a.kode for a in akun if a.kosong_lain],
                peran_izin={a.kode: izin_peran.get(a.peran, {}) for a in akun if a.bawaan},
                sesi_akhir=sesi_akhir, jumlah={kk: (seed[kk] + dibuat[kk], nyata[kk]) for kk in seed}, pesan=pesan)
    pelanggaran = nilai(hasil, k)
    total = time.monotonic() - t0
    laporan = {
        "versi": 1, "mode": "penuh" if penuh else "cepat", "awalan": awalan or "/api/",
        "rute": len(rute), "rute_get": sum(1 for m, _ in rute if m == "GET"),
        "permintaan": sum(len(v) for v in hasil.values()), "lama_detik": round(total, 1),
        "akun": {a.kode: {"peran": a.peran, "label": a.label, "peran_dasar": a.dasar, "hanya_get": a.hanya_get,
                          "lama_detik": round(lama[a.kode], 1)} for a in akun},
        "hasil": hasil, "pesan": pesan, "sesi_akhir": sesi_akhir,
        "jumlah": {kk: {"seed": seed[kk], "buatan_sapuan": dibuat[kk], "nyata": nyata[kk]} for kk in seed},
        "pelanggaran": pelanggaran,
    }
    if keluaran:
        Path(keluaran).write_text(json.dumps(laporan, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    cetak_laporan(laporan, cetak)
    return (1 if pelanggaran else 0), laporan


def cetak_laporan(lap: Dict[str, Any], cetak=print) -> None:
    cetak("== INV-PERM-02 — matriks izin berjalan (peran × endpoint) ==")
    cetak(f"mode {lap['mode']} · awalan {lap['awalan']} · {lap['rute']} rute ({lap['rute_get']} GET) · "
          f"{lap['permintaan']} permintaan · {lap['lama_detik']} dtk")
    cetak(f"  {'akun':<16} {'peran':<26} {'ditolak':>8} {'lolos':>6} {'422':>5} {'galat':>6} {'dtk':>6}")
    for kode, info in lap["akun"].items():
        c = collections.Counter(v[1] for v in lap["hasil"][kode].values())
        cetak(f"  {kode:<16} {(info['label'] or info['peran'] or '—')[:26]:<26} {c['ditolak']:>8} {c['lolos']:>6} "
              f"{c['tak_teruji']:>5} {c['galat']:>6} {info['lama_detik']:>6}")
    cetak("  sesi akhir GET /api/auth/me: " + " · ".join(f"{k} {v}" for k, v in lap["sesi_akhir"].items()))
    cetak("  jumlah dokumen: " + " · ".join(f"{k} {v['seed']} seed + {v['buatan_sapuan']} sapuan = "
                                            f"{v['seed'] + v['buatan_sapuan']} (terhitung {v['nyata']})"
                                            for k, v in lap["jumlah"].items()))
    pel = lap["pelanggaran"]
    hit = collections.Counter(p["kode"] for p in pel)
    cetak(f"  pelanggaran: {len(pel)}" + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(hit.items())) + ")"
                                          if pel else ""))
    for p in pel:
        cetak(f"  {p['kode']} {p['metode']:<6} {p['jalur']:<60} {p['akun'] or '—':<12} "
              f"{p['jawaban'] if p['jawaban'] is not None else '—':>4}  {p['pesan']!r}"
              + (f"  [{p['catatan']}]" if p["catatan"] else ""))
    cetak("HIJAU — tidak ada pelanggaran." if not pel
          else f"MERAH — {len(pel)} pelanggaran (arti kode: lihat docstring).")


# ─── Bukti-merah penilai (tanpa aplikasi) ───────────────────────────────────
def uji_diri() -> int:
    """Tiap kode M harus bisa memerah, dan hasil bersih harus hijau."""
    R = lambda kode, izin=None: [kode, kelas(kode), izin]  # noqa: E731
    dasar = dict(rute=["GET /api/a"], semua_rute={"GET /api/a", "POST /api/b", "POST /api/auth/login"},
                 publik={"POST /auth/login": "POST /api/auth/login"}, login_saja=[], harapan={})
    bersih = {TANPA_TOKEN: {"GET /api/a": R(401)}, KOSONG: {"GET /api/a": R(403, ["order.view"])},
              PENUH: {"GET /api/a": R(200)}, MGR0: {"GET /api/a": R(403, ["order.view"])},
              SOPIR: {"GET /api/a": R(403, ["order.view"])}}

    def ganti(akun, v):
        h = json.loads(json.dumps(bersih))
        h[akun]["GET /api/a"] = v
        return h

    kasus = [
        ("hasil bersih → hijau", bersih, {}, []),
        ("tanpa_token 200 → M0 (+M1 karena kosong juga lolos)",
         {**ganti(TANPA_TOKEN, R(200)), KOSONG: {"GET /api/a": R(200)}}, {}, ["M0", "M1"]),
        ("kosong 200 → M1", ganti(KOSONG, R(200)), {}, ["M1"]),
        ("kosong 200 di LOGIN_ONLY → hijau", ganti(KOSONG, R(200)), {"login_saja": ["GET /api/a"]}, []),
        ("kosong 200 di menunggu_unit → hijau", ganti(KOSONG, R(200)),
         {"harapan": {"menunggu_unit": {"GET /api/a": "KP-T4"}}}, []),
        ("penuh 403 → M2", ganti(PENUH, R(403, [])), {}, ["M2"]),
        ("penuh 403 di tolak_bukan_izin → hijau", ganti(PENUH, R(403, [])),
         {"harapan": {"tolak_bukan_izin": {"GET /api/a": "kepemilikan"}}}, []),
        ("mgr0 200 → M3 bertanda Sopir", ganti(MGR0, R(200)), {}, ["M3"]),
        ("{peran} Kosong 200 → M4", {**bersih, "sales0": {"GET /api/a": R(200)}}, {"akun_kosong_lain": ["sales0"]},
         ["M4"]),
        ("peran bawaan: Sales lolos tanpa izin, Finance ditolak padahal memegang → M5 ×2",
         {**bersih, "sales": {"GET /api/a": R(200)}, "finance": {"GET /api/a": R(403, ["order.view"])}},
         {"peran_izin": {"sales": {"customer": ["view"]}, "finance": {"order": ["view"]}}}, ["M5", "M5"]),
        ("422 → M6", ganti(KOSONG, R(422)), {}, ["M6"]),
        ("500 → M6", ganti(SOPIR, R(500)), {}, ["M6"]),
        ("500 di galat_dikenal → hijau", ganti(SOPIR, R(500)),
         {"harapan": {"galat_dikenal": {"GET /api/a": "PK-47"}}}, []),
        ("tolak_bukan_izin untuk rute yang tidak ada → M7", bersih,
         {"harapan": {"tolak_bukan_izin": {"GET /api/hilang": "uji"}}}, ["M7"]),
        ("baris harapan tanpa alasan → M7", ganti(PENUH, R(403, [])),
         {"harapan": {"tolak_bukan_izin": {"GET /api/a": ""}}}, ["M7"]),
        ("menunggu_unit yang kini menolak kosong → M7", bersih,
         {"harapan": {"menunggu_unit": {"GET /api/a": "KP-T4"}}}, ["M7"]),
        ("LOGIN_ONLY tanpa rute → M7", bersih, {"login_saja": ["GET /api/hilang"]}, ["M7"]),
        ("PUBLIC_ALLOWLIST tanpa rute → M7", bersih, {"publik": {"GET /hilang": None}}, ["M7"]),
        ("sesi mati → M8", bersih, {"sesi_akhir": {KOSONG: 401, PENUH: 200}}, ["M8"]),
        ("akun bertambah → M8", bersih, {"jumlah": {"users": (8, 9)}}, ["M8"]),
        ("rute PUBLIC_ALLOWLIST: 429 bagi {peran} Kosong bukan M4", {**bersih, "sales0": {"GET /api/a": R(429)}},
         {"akun_kosong_lain": ["sales0"], "publik": {"GET /a": "GET /api/a"}}, []),
        ("izin rantai 'salah satu dari': Sales memegang pasangan pertama → bukan M5",
         {**bersih, KOSONG: {"GET /api/a": R(403, ["rnd.view", "hr.view"])}, "sales": {"GET /api/a": R(200)}},
         {"peran_izin": {"sales": {"rnd": ["view"]}}}, []),
        ("izin dari teks lama", None, {}, None),
    ]
    gagal = 0
    print("== SELF-TEST INV-PERM-02 (penilai matriks izin harus bisa MEMERAH) ==")
    for nama, h, ubah, harap in kasus:
        if h is None:
            dapat = [izin_dari_teks("Permission ditolak: butuh salah satu dari order.view / customer.view"),
                     izin_diminta(403, "accounting.view", "", []), izin_diminta(403, "", "Z6", [("a", "b", True),
                                                                                              ("c", "d", False)]),
                     izin_diminta(403, "", "Permission ditolak: hr.view", [("rnd", "view", False),
                                                                          ("hr", "view", False)]),
                     izin_diminta(200, "", "", [("c", "d", False)])]
            ok = dapat == [["order.view", "customer.view"], ["accounting.view"], ["c.d"], ["hr.view", "rnd.view"],
                           None]
        else:
            k = Konteks(**{**dasar, **ubah})
            dapat = sorted(p["kode"] for p in nilai(h, k))
            ok = dapat == sorted(harap)
            if ok and nama.startswith("mgr0"):
                ok = nilai(h, k)[0]["catatan"] == "juga tertutup bagi Sopir"
        gagal += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {nama}  (dapat={dapat})")
    print("  HIJAU — penilai terbukti memerah untuk M0–M8." if not gagal else "  SELF-TEST MERAH.")
    return gagal


# ─── Titik masuk ────────────────────────────────────────────────────────────
async def _utama(args) -> int:
    os.environ["KN_REQUIRED_INDEX_MODE"] = "warn"     # PK-14 — sama dengan tests_mem/conftest.py
    import boot_app  # noqa: F401 — HARUS sebelum modul aplikasi: klien MongoDB diganti tiruan
    import logging

    import httpx
    import server
    from db import db
    from mongomock_motor import AsyncMongoMockClient

    import db as _dbmod
    if not isinstance(_dbmod.client, AsyncMongoMockClient):
        raise SystemExit("sapuan_izin hanya boleh berjalan di database tiruan")
    logging.disable(logging.CRITICAL)
    harapan = muat_harapan(Path(args.harapan)) if args.harapan else muat_harapan()
    awal = server.lifespan(server.app)
    # Cetakan proses awal (termasuk sandi acak seed tiruan) disenyapkan; `server.lifespan` dimasuki tangan supaya
    # keluaran sapuan sendiri tetap tampil.
    with contextlib.redirect_stdout(io.StringIO()):
        await awal.__aenter__()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
        tok = "tok_sapuan_admin_" + uuid.uuid4().hex
        await db.sessions.insert_one({"token": tok, "user_id": admin["id"], "created_at": now,
                                      "expires_at": now + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=120) as c:
            kode, _ = await jalankan(c, server.app, {"Authorization": f"Bearer {tok}", "X-Entity-Id": PT},
                                     penuh=args.penuh, awalan=args.awalan, harapan=harapan, keluaran=args.keluaran,
                                     db=db)
    finally:
        await awal.__aexit__(None, None, None)
    return kode


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="INV-PERM-02 — penjaga matriks izin berjalan (PR-T8)")
    ap.add_argument("--penuh", action="store_true", help="tambah 13 peran bawaan (GET) dan 12 peran '{peran} Kosong'")
    ap.add_argument("--awalan", default="", help="hanya rute berawalan ini (mis. /api/costing)")
    ap.add_argument("--keluaran", default="", help="simpan hasil per rute per akun ke berkas JSON")
    ap.add_argument("--harapan", default="", help=f"berkas harapan (bawaan {BERKAS_HARAPAN.name})")
    ap.add_argument("--uji-diri", action="store_true", help="bukti-merah penilai M0–M8 (tanpa aplikasi)")
    args = ap.parse_args(argv)
    if args.uji_diri:
        return 1 if uji_diri() else 0
    return asyncio.run(_utama(args))


if __name__ == "__main__":
    sys.exit(main())
