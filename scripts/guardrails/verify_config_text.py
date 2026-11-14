#!/usr/bin/env python3
"""INV-CFG-TXT — teks Pengaturan berbahasa awam (KF-T4; `docs/blueprint/unit/KF-T4.md`, standar §2.1 dan §4 L1–L2).

Kenapa ada: penjaga bahasa repo (`scripts/audit_i18n_id.py`) hanya mengenali kunci kamus berkutip (`"label": "…"`),
sedangkan katalog Pengaturan menulis argumen `label="…"` — teks kartu tidak pernah diperiksa. Audit 13 Nov 2026
(`docs/audit/konfigurasi-peran-2026-11-13/lampiran/A_pengaturan_ux.md`) menemukan 51 label > 45 huruf, 24 kunci angka
tanpa satuan, dan arti angka 0 yang tidak tertulis. Hasil wajib **0 pelanggaran** (bukan garis dasar).

Aturan (dibaca dari registry yang sudah dimuat, jadi kunci buatan loop ikut diperiksa):
  T1  label ≤ 45 huruf                          T2  tidak ada dua label sama (tanpa membedakan huruf besar)
  T3  tanpa kata teknis (`02` §4 L1), id teknis, kode HTTP, kode keputusan
  T4  kunci angka wajib ber-satuan (satu pengecualian bercatatan)
  T5  kunci angka aktif yang boleh 0: penjelasan menyebut arti angka 0
  T6  tanpa kata yang diganti glosarium (tabel (b) unit); label juga tanpa "ambang", "SJ", "GRN".
      Frasa yang persis label menu (`hubTabs.js` / `navStructure.js`) dikecualikan
  T7  sub-judul tiap kunci terdaftar pada kelompoknya; sub-judul biasa (bukan "Lanjutan") paling banyak 14 kunci

Pemakaian:
    python scripts/guardrails/verify_config_text.py              # exit 1 bila ada pelanggaran
    python scripts/guardrails/verify_config_text.py --self-test  # satu kasus merah per aturan
"""
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BACKEND, FRONTEND, G, R, X, Guard  # noqa: E402

BATAS_LABEL = 45
BATAS_SUB_JUDUL = 14
ANGKA = ("int", "pct", "money", "decimal", "duration")
#: T4 — satu-satunya kunci angka tanpa satuan: satuannya mengikuti `commission.discount_threshold_type` (persen / Rp).
TANPA_SATUAN = {"commission.discount_threshold"}

#: T3 — kata teknis yang dilarang tampil (`02_STANDAR.md` §4 L1).
KATA_TEKNIS = ("scope", "scopes", "override", "overrides", "threshold", "thresholds", "fallback", "payload",
               "posting", "diposting")
KODE_KEPUTUSAN = re.compile(r"\b(?:DEC-\d|LN-\d|AS-\d|KLX-|P18\b|M-3\b)")
KODE_HTTP = re.compile(r"\(\s*4\d\d\s*\)")
ID_TEKNIS = re.compile(r"\b(?:ent|cr)_[a-z0-9_]+")
SNAKE = re.compile(r"(?<![\w./-])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![\w/-])")
TITIK = re.compile(r"(?<![\w.])[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+(?![\w])")

#: T6 — kata yang diganti tabel (b) unit KF-T4 (huruf besar/kecil sama saja; bentuk jamak Inggris ikut).
KATA_GANTI = ("entitas", "badan usaha", "supplier", "vendor", "customer", "approval", "approver", "pengusul",
              "manager", "role", "default", "payroll", "qty", "invoice", "refund", "round", "ronde", "sampel",
              "setting", "wiring")
KATA_GANTI_LABEL = ("ambang", "SJ", "GRN")
NOL = re.compile(r"(?<![\d.,])0(?![\d.,])")


def _pola_kata(kata: str, jamak: bool = True) -> "re.Pattern[str]":
    akhir = r"s?" if jamak and re.fullmatch(r"[a-z]+", kata) else ""
    return re.compile(r"(?<![\w-])" + re.escape(kata) + akhir + r"(?![\w-])", re.IGNORECASE)


POLA_GANTI = [(k, _pola_kata(k)) for k in KATA_GANTI]
POLA_GANTI_LABEL = [(k, re.compile(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", re.IGNORECASE if k == "ambang" else 0))
                    for k in KATA_GANTI_LABEL]
POLA_TEKNIS = [(k, _pola_kata(k, jamak=False)) for k in KATA_TEKNIS]


def teks_kunci(e: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(nama bagian, teks) yang tampil di kartu satu kunci."""
    out = [("label", e.get("label") or ""), ("penjelasan", e.get("help") or ""),
           ("dampak", e.get("impact") or ""), ("contoh", e.get("example") or ""), ("satuan", e.get("unit") or "")]
    out += [(f"pilihan '{o.get('value')}'", str(o.get("label") or "")) for o in e.get("options") or []]
    out += [(f"kolom '{c.get('name')}'", str(c.get("label") or "")) for c in e.get("columns") or []]
    if e.get("status") == "not_used":
        out.append(("alasan tidak dipakai", e.get("not_used_reason") or ""))
    return out


def _buang_menu(teks: str, menu: Iterable[str]) -> str:
    for m in sorted(menu, key=len, reverse=True):
        if m and m in teks:
            teks = teks.replace(m, " ")
    return teks


def periksa_teks(tempat: str, bagian: str, teks: str, kunci_set: Set[str], izin_set: Set[str],
                 menu: Sequence[str], label: bool = False) -> List[Tuple[str, str]]:
    """Pelanggaran T3 + T6 pada satu teks → [(aturan, pesan)]."""
    hasil: List[Tuple[str, str]] = []
    if not teks:
        return hasil
    for kata, pola in POLA_TEKNIS:
        if pola.search(teks):
            hasil.append(("T3", f"{tempat} · {bagian}: kata teknis '{kata}'"))
    if KODE_HTTP.search(teks):
        hasil.append(("T3", f"{tempat} · {bagian}: kode HTTP '{KODE_HTTP.search(teks).group(0)}'"))
    if KODE_KEPUTUSAN.search(teks):
        hasil.append(("T3", f"{tempat} · {bagian}: kode keputusan '{KODE_KEPUTUSAN.search(teks).group(0)}'"))
    if ID_TEKNIS.search(teks):
        hasil.append(("T3", f"{tempat} · {bagian}: id teknis '{ID_TEKNIS.search(teks).group(0)}'"))
    for m in TITIK.finditer(teks):
        tok = m.group(0)
        if tok in kunci_set or tok in izin_set:
            hasil.append(("T3", f"{tempat} · {bagian}: nama kunci/izin '{tok}'"))
    for m in SNAKE.finditer(teks):
        hasil.append(("T3", f"{tempat} · {bagian}: nama isian '{m.group(0)}'"))
    bersih = _buang_menu(teks, menu)
    for kata, pola in POLA_GANTI:
        if pola.search(bersih):
            hasil.append(("T6", f"{tempat} · {bagian}: '{pola.search(bersih).group(0)}' (glosarium: {kata})"))
    if label:
        for kata, pola in POLA_GANTI_LABEL:
            if pola.search(bersih):
                hasil.append(("T6", f"{tempat} · label: '{kata}'"))
    return hasil


def periksa(entries: Sequence[Dict[str, Any]], groups: Sequence[Dict[str, Any]], menu: Sequence[str],
            izin_set: Set[str]) -> List[Tuple[str, str]]:
    """Seluruh aturan T1–T7 → [(aturan, pesan)]."""
    hasil: List[Tuple[str, str]] = []
    kunci_set = {e["key"] for e in entries}
    for e in entries:
        k, lab = e["key"], e.get("label") or ""
        if len(lab) > BATAS_LABEL:
            hasil.append(("T1", f"{k}: label {len(lab)} huruf (> {BATAS_LABEL}): '{lab}'"))
        for bagian, teks in teks_kunci(e):
            hasil += periksa_teks(k, bagian, teks, kunci_set, izin_set, menu, label=bagian == "label")
        if e.get("type") in ANGKA and not (e.get("unit") or "").strip() and k not in TANPA_SATUAN:
            hasil.append(("T4", f"{k}: kunci angka ({e.get('type')}) tanpa satuan"))
        lo = e.get("min")
        if (e.get("type") in ANGKA and e.get("status") == "active" and (lo is None or lo <= 0)
                and not NOL.search(e.get("help") or "")):
            hasil.append(("T5", f"{k}: boleh bernilai 0 tetapi penjelasan tidak menyebut arti angka 0"))
    lab_hit = Counter((e.get("label") or "").strip().lower() for e in entries)
    for lab, n in lab_hit.items():
        if n > 1:
            pemilik = ", ".join(e["key"] for e in entries if (e.get("label") or "").strip().lower() == lab)
            hasil.append(("T2", f"label '{lab}' dipakai {n} kunci: {pemilik}"))
    sub: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for g in groups:
        tempat = f"kelompok {g['id']}"
        for bagian in ("label", "question"):
            hasil += periksa_teks(tempat, bagian, g.get(bagian) or "", kunci_set, izin_set, menu)
        sub[g["id"]] = {}
        for s in g.get("sections") or []:
            sub[g["id"]][s["id"]] = s
            hasil += periksa_teks(f"{tempat} · sub-judul {s['id']}", "label", s.get("label") or "", kunci_set,
                                  izin_set, menu)
    isi: Counter = Counter()
    for e in entries:
        g, s = e.get("group"), e.get("section") or ""
        if s not in sub.get(g, {}):
            hasil.append(("T7", f"{e['key']}: sub-judul '{s}' tidak terdaftar pada kelompok '{g}'"))
        else:
            isi[(g, s)] += 1
    for (g, s), n in isi.items():
        if not sub[g][s].get("advanced") and n > BATAS_SUB_JUDUL:
            hasil.append(("T7", f"kelompok {g} · sub-judul {s}: {n} kunci (> {BATAS_SUB_JUDUL}; pecah atau jadikan "
                                f"'Lanjutan (teknis)')"))
    return hasil


# ── pemuat ───────────────────────────────────────────────────────────────────
LABEL_JS = re.compile(r"""\blabel\s*:\s*(["'`])((?:(?!\1).)+)\1""")


def label_menu() -> List[str]:
    out: List[str] = []
    for rel in ("src/config/hubTabs.js", "src/config/navStructure.js"):
        p = FRONTEND / rel
        if p.exists():
            out += [m.group(2) for m in LABEL_JS.finditer(p.read_text(encoding="utf-8"))]
    return sorted(set(out))


def muat() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Set[str]]:
    sys.path.insert(0, str(BACKEND))
    import config_registry as reg  # noqa: WPS433
    izin: Set[str] = set()
    try:
        from permissions_config import DEFAULT_PERMISSIONS  # noqa: WPS433
        for perms in DEFAULT_PERMISSIONS.values():
            for res, acts in (perms or {}).items():
                izin |= {f"{res}.{a}" for a in acts if a != "*"}
    except Exception:  # noqa: BLE001 — tanpa matriks izin: cukup izin pengubah di registry
        pass
    for e in reg.all_entries():
        izin.add(".".join((e.get("permission") or ["settings", "manage"])[:2]))
    return reg.all_entries(), list(reg.GROUPS), izin


def main() -> int:
    g = Guard("INV-CFG-TXT", "teks Pengaturan berbahasa awam (label ≤ 45, satuan, arti 0, glosarium, sub-judul)")
    entries, groups, izin = muat()
    g.bump(len(entries) * 7 + len(groups))
    hasil = periksa(entries, groups, label_menu(), izin)
    per = Counter(a for a, _ in hasil)
    print(f"  {len(entries)} kunci · {len(groups)} kelompok · pelanggaran per aturan: "
          + (", ".join(f"{a}={per[a]}" for a in sorted(per)) or "0"))
    for aturan, pesan in hasil:
        g.add(f"[{aturan}] {pesan}")
    return g.finish()


def self_test() -> int:
    gagal = 0

    def cek(nama: str, ok: bool) -> None:
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    def entri(**kw: Any) -> Dict[str, Any]:
        base = {"key": "x.contoh", "group": "g", "section": "s", "label": "Contoh pengaturan",
                "help": "Penjelasan biasa. Isi 0 bila tidak dipakai.", "impact": "Dampak biasa.", "example": "",
                "unit": "hari", "type": "int", "min": 0, "status": "active", "options": [], "columns": []}
        base.update(kw)
        return base

    grp = [{"id": "g", "label": "Kelompok", "question": "Apa?", "sections": [
        {"id": "s", "label": "Sub", "advanced": False}, {"id": "t", "label": "Teknis", "advanced": True}]}]
    menu = ["Pemasok (Supplier)"]

    def aturan(entries: Sequence[Dict[str, Any]]) -> Set[str]:
        return {a for a, _ in periksa(entries, grp, menu, {"settings.manage"})}

    cek("kunci bersih → hijau", aturan([entri()]) == set())
    cek("T1 label 46 huruf → merah", "T1" in aturan([entri(label="L" * 46)]))
    cek("T2 dua label sama (huruf besar beda) → merah",
        "T2" in aturan([entri(), entri(key="x.lain", label="CONTOH PENGATURAN")]))
    cek("T3 kata 'threshold' → merah", "T3" in aturan([entri(help="Isi 0 bila threshold mati.")]))
    cek("T3 nama isian 'supplier_id' → merah", "T3" in aturan([entri(example="supplier_id kosong")]))
    cek("T3 kode HTTP '(400)' → merah", "T3" in aturan([entri(impact="Ditolak (400).")]))
    cek("T3 kode keputusan 'DEC-01' → merah", "T3" in aturan([entri(help="Isi 0 bila mati (DEC-01).")]))
    cek("T3 nama izin 'settings.manage' → merah", "T3" in aturan([entri(help="Isi 0 · izin settings.manage")]))
    cek("T4 angka tanpa satuan → merah", "T4" in aturan([entri(unit="")]))
    cek("T4 pengecualian bercatatan → hijau",
        "T4" not in aturan([entri(key="commission.discount_threshold", unit="")]))
    cek("T5 boleh 0 tanpa arti 0 → merah", "T5" in aturan([entri(help="Batas hari.")]))
    cek("T5 '10' bukan '0' berdiri sendiri → merah", "T5" in aturan([entri(help="Paling banyak 10 hari.")]))
    cek("T5 min 1 tidak wajib → hijau", "T5" not in aturan([entri(min=1, help="Batas hari.")]))
    cek("T6 'supplier' → merah", "T6" in aturan([entri(help="Isi 0 untuk semua supplier.")]))
    cek("T6 'Manager' (huruf besar) → merah", "T6" in aturan([entri(impact="Disetujui Manager.")]))
    cek("T6 frasa label menu dikecualikan → hijau",
        "T6" not in aturan([entri(impact="Buka Pemasok (Supplier) lalu pilih.")]))
    cek("T6 label 'ambang' → merah", "T6" in aturan([entri(label="Ambang selisih")]))
    cek("T6 'ambang' di penjelasan boleh → hijau", "T6" not in aturan([entri(help="Isi 0 · ambang lama.")]))
    cek("T7 sub-judul tak terdaftar → merah", "T7" in aturan([entri(section="zz")]))
    banyak = [entri(key=f"x.k{i}", label=f"Label {i}") for i in range(BATAS_SUB_JUDUL + 1)]
    cek("T7 sub-judul biasa 15 kunci → merah", "T7" in aturan(banyak))
    cek("T7 sub-judul Lanjutan 15 kunci → hijau", "T7" not in aturan([dict(b, section="t") for b in banyak]))
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
