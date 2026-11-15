#!/usr/bin/env python3
"""Pemeriksa DEFINISI SELESAI untuk review dan audit domain + ringkasan kemajuan yang DIHITUNG (bukan klaim).

Dipakai oleh reviewer di lingkungannya sendiri dan oleh pelaksana saat pemilik kembali. Hanya membaca repo
(kecuali `progres` yang menulis `docs/reviews/PROGRES_REVIEW.md`). Aturan lengkap: `docs/reviews/PERINTAH_REVIEW_2026-11-15.md`
§A dan `docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md` §8.

    python3 scripts/review/periksa_selesai.py daftar B1          # butir wajib batch B1 (ID, unit, berkas validasi)
    python3 scripts/review/periksa_selesai.py review B1          # periksa definisi selesai batch B1 → kode 1 bila belum
    python3 scripts/review/periksa_selesai.py audit docs/audit/2026-11-16-domain   # periksa hasil audit domain
    python3 scripts/review/periksa_selesai.py progres            # ringkasan semua batch + audit → PROGRES_REVIEW.md
    python3 scripts/review/periksa_selesai.py --uji-diri         # bukti pemeriksa bisa hijau dan merah
"""
import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "docs/reviews/TRACKER.md"
HASIL = ROOT / "docs/reviews/2026-11-13/hasil"
PERINTAH_AUDIT = ROOT / "docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md"
PROGRES = ROOT / "docs/reviews/PROGRES_REVIEW.md"

BATCH = {
    "B0": {"judul": "R0 — 8 keputusan integrasi FIX-6…FIX-10 + fungsi yang diubah dua sisi", "r0": True},
    "B1": {"judul": "Keuangan Kritis/Tinggi — kas, pembayaran, piutang & hutang", "bagian": "Audit keuangan",
           "keparahan": {"Kritis", "Tinggi"}, "unit": ["PK-05", "PK-15", "PK-17", "PK-19", "PK-31", "PK-38"]},
    "B2": {"judul": "Keuangan Kritis/Tinggi — jurnal, periode, posting, laporan", "bagian": "Audit keuangan",
           "keparahan": {"Kritis", "Tinggi"},
           "unit": ["PK-07", "PK-08", "PK-09", "PK-10", "PK-11", "PK-12", "PK-13", "PK-16", "PK-18", "PK-22", "PK-23",
                    "PK-24", "PK-25", "PK-36", "PK-41", "PK-42", "PK-43", "PK-44"]},
    "B3": {"judul": "Keuangan Kritis/Tinggi — antar-PT, persediaan, retur, nota", "bagian": "Audit keuangan",
           "keparahan": {"Kritis", "Tinggi"}, "unit": ["PK-06", "PK-26", "PK-27", "PK-28", "PK-30", "PK-32", "PK-33"]},
    "B4": {"judul": "Riset modul Tinggi — kredit, insentif, pajak pesanan, pembayaran, gaji",
           "bagian": "Temuan tambahan riset modul", "keparahan": {"Kritis", "Tinggi"},
           "unit": ["CR-T3", "KM-T1", "PK-45", "PM-T2", "PM-T3", "PY-T1", "PY-T3"]},
    "B5": {"judul": "Konfigurasi & peran Tinggi", "bagian": "Audit konfigurasi dan peran", "keparahan": {"Kritis", "Tinggi"},
           "unit": ["KF-T1", "KF-T3", "KF-T6", "KP-T1", "KP-T2", "KP-T3", "KP-T4", "KP-T5", "KP-T7", "KP-T8", "PK-47",
                    "PR-T1", "PR-T2", "PR-T9"]},
    "B6": {"judul": "Keuangan Sedang/Rendah", "bagian": "Audit keuangan", "keparahan": {"Sedang", "Rendah"}},
    "B7": {"judul": "Riset modul Sedang/Rendah", "bagian": "Temuan tambahan riset modul", "keparahan": {"Sedang", "Rendah"}},
    "B8": {"judul": "Konfigurasi & peran Sedang/Rendah", "bagian": "Audit konfigurasi dan peran",
           "keparahan": {"Sedang", "Rendah"}},
}
STATUS_IKUT = {"implemented_pending_review", "verified", "reopened", "pending_decision"}
PUTUSAN_TRACKER = {"verified": "verified", "reopened": "reopened", "perlu_keputusan_pemilik": "pending_decision",
                   "terhambat_lingkungan": "implemented_pending_review"}
PUTUSAN_R0 = {"benar", "salah", "perlu_keputusan_pemilik", "terhambat_lingkungan"}
KATEGORI = {"ulang", "bersamaan", "sebagian", "pt_lain", "tanpa_izin", "periode_tertutup", "jurnal_gagal", "koreksi",
            "data_lama", "batas_nilai", "jalur_lain", "layar"}
SUB_BARIS = ["Temuan asli", "Perbaikan yang diperiksa", "Pintu lain", "Uji yang dijalankan", "Upaya membantah", "Putusan"]
SUB_R0 = ["Yang diputuskan", "Perbaikan yang diperiksa", "Pintu lain", "Uji yang dijalankan", "Upaya membantah", "Putusan"]
FUNGSI_DUA_SISI = ["_create_po_core", "submit_return", "complete_task", "close_remaining", "issue_material", "_make_roll",
                   "confirm_cut", "reserve_rolls_for_transfer", "assert_roll_rounding", "_supplier_deadline_job",
                   "cancel_line", "resolve", "_restock_returned_items", "settle_return", "reverse_settlement", "lifespan",
                   "covers"]
MIN_BARIS_DIBACA, MIN_BERKAS_DIBACA = 30, 2

RE_REF = re.compile(r"\b[\w./-]+\.(?:py|jsx|js|ts|json|sh)(?::\d+)")
RE_RANGE = re.compile(r"\b([\w./-]+\.(?:py|jsx|js|ts))[:#]L?(\d+)\s*[-–]\s*L?(\d+)")
RE_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
RE_HASIL_UJI = re.compile(r"Hasil:\s*(\d+)\s*lulus(?:\D+(\d+)\s*gagal)?", re.I)

AUDIT_BERKAS = {"A": "A-MASTER-STAGE.md", "B": "B-MAKLOON.md", "C": "C-RND.md", "D": "D-RETUR.md",
                "E": "E-QC-MDQ.md", "F": "F-PESANAN-SESUDAH-POS.md"}
AUDIT_PREFIKS = ("MS", "MK", "RD", "RT", "QM", "SO")
FIELD_TEMUAN = ["Keparahan:", "Jenis akar:", "Bukti:", "Reproduksi:", "Dampak:", "Arah perbaikan:", "Keputusan pemilik:",
                "Sudah ada:"]
STATUS_SKENARIO = {"lulus", "gagal", "terhambat"}


# ── pembaca ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def baca(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def baris_tracker():
    sec, out = "", []
    for ln in baca(TRACKER).split("\n"):
        if ln.startswith("## "):
            sec = ln[3:].strip()
        m = re.match(r"^\| ([A-Z]{2,4}-\d+[a-z]?) \| .*? \| (Kritis|Tinggi|Sedang|Rendah) \| ([^|]*) \| ([a-z_]+) \|", ln)
        if m and "2026-11-13" in sec:
            out.append({"bagian": sec.split(" — ")[0], "id": m.group(1), "keparahan": m.group(2),
                        "unit": m.group(3).strip(), "status": m.group(4)})
    return out


def isi_batch(kode):
    b = BATCH[kode]
    if b.get("r0"):
        return []
    rows = [r for r in baris_tracker() if r["bagian"] == b["bagian"] and r["keparahan"] in b["keparahan"]
            and r["status"] in STATUS_IKUT and (not b.get("unit") or r["unit"] in b["unit"])]
    return rows


def bagian(teks, tingkat):
    """{judul: isi} untuk heading `#`*tingkat (judul = teks sesudah tanda #)."""
    pola = re.compile(rf"^{'#' * tingkat} (.+)$", re.M)
    hasil, cocok = {}, list(pola.finditer(teks))
    for i, m in enumerate(cocok):
        akhir = cocok[i + 1].start() if i + 1 < len(cocok) else len(teks)
        hasil[m.group(1).strip()] = teks[m.end():akhir]
    return hasil


def cari(subs, nama):
    for k, v in subs.items():
        if k.lower().startswith(nama.lower()):
            return v
    return None


def baris_dibaca(teks):
    berkas, total = set(), 0
    for f, a, b in RE_RANGE.findall(teks):
        a, b = int(a), int(b)
        if b >= a:
            berkas.add(f)
            total += b - a + 1
    return total, berkas


def sha_ada(sha):
    return subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True).returncode == 0


# ── pemeriksa satu butir review ─────────────────────────────────────────────────────────────────────────────────────
def periksa_butir(isi, sub_wajib, putusan_sah):
    """→ (masalah[], metrik{}) untuk satu bagian `## <ID>` / `## Keputusan n`."""
    masalah, met = [], {"baris": 0, "berkas": 0, "lulus": 0, "gagal": 0, "putusan": "", "bantah": 0}
    subs = bagian(isi, 3)
    for s in sub_wajib:
        if cari(subs, s) is None:
            masalah.append(f"sub-bagian '### {s}' tidak ada")
    if masalah:
        return masalah, met
    t0 = cari(subs, sub_wajib[0])
    if not RE_REF.search(t0):
        masalah.append(f"'{sub_wajib[0]}' tanpa rujukan berkas:baris")
    tp = cari(subs, "Perbaikan yang diperiksa")
    n, fs = baris_dibaca(isi)
    met["baris"], met["berkas"] = n, len(fs)
    if "Berkas dibaca:" not in tp:
        masalah.append("'Perbaikan yang diperiksa' tanpa baris 'Berkas dibaca:'")
    if n < MIN_BARIS_DIBACA or len(fs) < MIN_BERKAS_DIBACA:
        masalah.append(f"baris kode dibaca {n} dari {len(fs)} berkas (minimum {MIN_BARIS_DIBACA} baris, "
                       f"{MIN_BERKAS_DIBACA} berkas; tulis rentang `berkas.py:120-188`)")
    if not RE_SHA.search(tp):
        masalah.append("'Perbaikan yang diperiksa' tanpa SHA commit")
    tl = cari(subs, "Pintu lain")
    if "```" not in tl or "Kesimpulan:" not in tl:
        masalah.append("'Pintu lain' wajib berisi perintah pencarian (blok ```) dan baris 'Kesimpulan:'")
    tu = cari(subs, "Uji yang dijalankan")
    m = RE_HASIL_UJI.search(tu)
    if "```" not in tu or not m:
        masalah.append("'Uji yang dijalankan' wajib berisi perintah (blok ```) dan 'Hasil: <n> lulus, <m> gagal'")
    else:
        met["lulus"], met["gagal"] = int(m.group(1)), int(m.group(2) or 0)
    tb = cari(subs, "Upaya membantah")
    upaya = [ln for ln in tb.split("\n") if re.match(r"\s*- \[(\w+)\]", ln)]
    sah = [ln for ln in upaya if re.match(r"\s*- \[(\w+)\]", ln).group(1) in KATEGORI and "Hasil:" in ln]
    met["bantah"] = len(sah)
    if len(sah) < 2:
        masalah.append(f"'Upaya membantah' {len(sah)} butir sah (minimum 2; bentuk `- [kategori] … Hasil: …`, "
                       f"kategori: {', '.join(sorted(KATEGORI))})")
    tv = cari(subs, "Putusan")
    mp = re.search(r"Putusan:\s*([a-z_]+)", tv)
    ma = re.search(r"Alasan:\s*(.+)", tv, re.S)
    if not mp or mp.group(1) not in putusan_sah:
        masalah.append(f"'Putusan:' wajib salah satu dari {sorted(putusan_sah)}")
    else:
        met["putusan"] = mp.group(1)
    if not ma or len(ma.group(1).strip()) < 60:
        masalah.append("'Alasan:' minimum 60 huruf")
    elif not (RE_REF.search(ma.group(1)) or "test_" in ma.group(1)):
        masalah.append("'Alasan:' wajib menunjuk bukti (berkas:baris atau nama uji), bukan laporan pelaksana")
    if met["putusan"] == "verified" and met["gagal"] > 0:
        masalah.append("putusan verified padahal ada uji gagal")
    return masalah, met


def kepala(teks):
    masalah = []
    m = re.search(r"Commit yang direview:\s*([0-9a-f]{7,40})", teks)
    if not m:
        masalah.append("baris 'Commit yang direview: <sha>' tidak ada")
    elif not sha_ada(m.group(1)):
        masalah.append(f"SHA {m.group(1)} tidak dikenal di repo (review harus pada commit yang sudah di-push)")
    if not re.search(r"Lingkungan:\s*\S", teks):
        masalah.append("baris 'Lingkungan: …' tidak ada (MongoDB asli/tiruan, backend hidup, data acuan)")
    return masalah


def periksa_batch(kode, cetak=True):
    """→ (selesai: bool, ringkasan{})"""
    b = BATCH[kode]
    gagal, ring = [], {"butir": 0, "lengkap": 0, "baris": 0, "lulus": 0, "gagal_uji": 0, "putusan": {}, "kurang": []}
    if b.get("r0"):
        f = HASIL / "validasi-R0.md"
        teks = baca(f)
        if not teks:
            gagal.append(f"{f.relative_to(ROOT)} belum ada")
            ring["butir"] = 9
            ring["kurang"] = [f"Keputusan {i}" for i in range(1, 9)] + ["Fungsi dua sisi"]
        else:
            gagal += kepala(teks)
            secs = bagian(teks, 2)
            for i in range(1, 9):
                ring["butir"] += 1
                isi = cari(secs, f"Keputusan {i}")
                if isi is None:
                    gagal.append(f"'## Keputusan {i}' tidak ada"); ring["kurang"].append(f"Keputusan {i}"); continue
                ms, met = periksa_butir(isi, SUB_R0, PUTUSAN_R0)
                _tambah(ring, met, not ms, f"Keputusan {i}")
                gagal += [f"Keputusan {i}: {x}" for x in ms]
            fx = cari(secs, "Fungsi yang diubah dua sisi") or ""
            hilang = [fn for fn in FUNGSI_DUA_SISI if not re.search(rf"\b{re.escape(fn)}\b", fx)]
            ring["butir"] += 1
            if hilang or not RE_REF.search(fx):
                gagal.append(f"'## Fungsi yang diubah dua sisi': belum dinilai {hilang or '(tanpa berkas:baris)'}")
                ring["kurang"].append("Fungsi dua sisi")
            else:
                ring["lengkap"] += 1
    else:
        rows = isi_batch(kode)
        per_unit = {}
        for r in rows:
            per_unit.setdefault(r["unit"], []).append(r)
        for unit, rs in sorted(per_unit.items()):
            f = HASIL / f"validasi-{unit}.md"
            teks = baca(f)
            gk = kepala(teks) if teks else [f"{f.relative_to(ROOT)} belum ada"]
            gagal += [f"{unit}: {x}" for x in gk]
            secs = bagian(teks, 2) if teks else {}
            for r in rs:
                ring["butir"] += 1
                isi = next((v for k, v in secs.items() if re.match(rf"{re.escape(r['id'])}\b", k)), None)
                if isi is None:
                    gagal.append(f"{r['id']} ({unit}): bagian '## {r['id']} …' tidak ada"); ring["kurang"].append(r["id"])
                    continue
                ms, met = periksa_butir(isi, SUB_BARIS, set(PUTUSAN_TRACKER))
                if met["putusan"] and PUTUSAN_TRACKER[met["putusan"]] != r["status"]:
                    ms.append(f"status tracker '{r['status']}' ≠ putusan '{met['putusan']}' "
                              f"(harus {PUTUSAN_TRACKER[met['putusan']]})")
                ok = not ms and not gk
                _tambah(ring, met, ok, r["id"])
                gagal += [f"{r['id']} ({unit}): {x}" for x in ms]
    selesai = not gagal and ring["lengkap"] == ring["butir"] and ring["butir"] > 0
    if cetak:
        print(f"== {kode} — {b['judul']}: {ring['lengkap']}/{ring['butir']} butir lengkap · baris kode dibaca "
              f"{ring['baris']:,} · uji {ring['lulus']} lulus / {ring['gagal_uji']} gagal · putusan {ring['putusan']}")
        for g in gagal[:60]:
            print(f"   ✗ {g}")
        if len(gagal) > 60:
            print(f"   … {len(gagal) - 60} masalah lain")
        print("HASIL:", "SELESAI" if selesai else "BELUM SELESAI")
    return selesai, ring


def _tambah(ring, met, ok, label):
    ring["baris"] += met["baris"]; ring["lulus"] += met["lulus"]; ring["gagal_uji"] += met["gagal"]
    if met["putusan"]:
        ring["putusan"][met["putusan"]] = ring["putusan"].get(met["putusan"], 0) + 1
    if ok:
        ring["lengkap"] += 1
    else:
        ring["kurang"].append(label)


# ── audit domain ────────────────────────────────────────────────────────────────────────────────────────────────────
def wajib_audit():
    """Skenario & form wajib dibaca dari tabel PERINTAH_AUDIT (satu sumber): `| A-S1 | …` dan `| A-F1 | `X.jsx` …`."""
    teks = baca(PERINTAH_AUDIT)
    sk, fm = {}, {}
    for d, n in re.findall(r"^\| ([A-F])-S(\d+) \|", teks, re.M):
        sk.setdefault(d, []).append(f"{d}-S{n}")
    for d, n, berkas in re.findall(r"^\| ([A-F])-F(\d+) \| `([\w.]+)`", teks, re.M):
        fm.setdefault(d, []).append((f"{d}-F{n}", berkas))
    return sk, fm


RE_PILIHAN = re.compile(r"<(KNSelect|select|SearchSelect|SearchableSelect|Combobox|AsyncSelect|ProductPicker|ProductSearch|"
                        r"EntitySelect|WarehouseSelect|PartnerSelect|RadioGroup)\b")


def jumlah_pilihan(nama_berkas):
    """Jumlah komponen pilihan (dropdown/radio/pencari) di berkas layar — batas bawah baris inventaris."""
    f = next(iter((ROOT / "frontend/src/features").rglob(nama_berkas)), None)
    return len(RE_PILIHAN.findall(baca(f))) if f else 0


def id_tracker():
    return set(re.findall(r"^\| ([A-Z]{2,4}-\d+) \|", baca(TRACKER), re.M))


def periksa_audit(folder: Path, cetak=True):
    sk, fm = wajib_audit()
    gagal, ring = [], {}
    if not folder.is_dir():
        print(f"folder {folder} tidak ada"); return False, {}
    rg = baca(folder / "00-RINGKASAN.md")
    if not rg:
        gagal.append("00-RINGKASAN.md belum ada")
    else:
        s = bagian(rg, 2)
        if len(re.findall(r"^\s*\d+\.\s.*\b(?:" + "|".join(AUDIT_PREFIKS) + r")-\d+", cari(s, "10 masalah terbesar") or "",
                          re.M)) < 10:
            gagal.append("ringkasan: '## 10 masalah terbesar' butuh 10 butir bernomor ber-ID")
        if not (cari(s, "Peta duplikasi") or "").strip():
            gagal.append("ringkasan: '## Peta duplikasi' kosong")
        if not re.search(r"^\s*\d+\.", cari(s, "Pertanyaan untuk pemilik") or "", re.M):
            gagal.append("ringkasan: '## Pertanyaan untuk pemilik' kosong")
    if not (folder / "bukti").is_dir():
        gagal.append("folder bukti/ tidak ada")
    trk = id_tracker()
    for d, nama in AUDIT_BERKAS.items():
        teks = baca(folder / nama)
        r = {"skenario": f"0/{len(sk.get(d, []))}", "gagal": 0, "terhambat": 0, "form": f"0/{len(fm.get(d, []))}",
             "dropdown": 0, "temuan": {}, "baris": 0}
        ring[d] = r
        if not teks:
            gagal.append(f"{nama} belum ada"); continue
        s = bagian(teks, 2)
        peta = cari(s, "Peta sumber kebenaran") or ""
        if "```" not in peta or len(RE_REF.findall(peta)) < 3:
            gagal.append(f"{nama}: 'Peta sumber kebenaran' butuh perintah pencarian + ≥3 berkas:baris penulis")
        if not (cari(s, "Pintu ganda") or "").strip():
            gagal.append(f"{nama}: 'Pintu ganda' kosong")
        mx = cari(s, "Matriks skenario") or ""
        jalan = 0
        for sid in sk.get(d, []):
            m = re.search(rf"^\| {re.escape(sid)} \|(.+)$", mx, re.M)
            if not m:
                gagal.append(f"{nama}: skenario {sid} tidak ada di matriks"); continue
            sel = [c.strip().lower() for c in m.group(1).split("|")]
            st = next((c for c in sel if c in STATUS_SKENARIO), "")
            bk = re.findall(r"bukti/[\w./-]+", m.group(1))
            if not st:
                gagal.append(f"{nama}: {sid} tanpa status lulus/gagal/terhambat"); continue
            if st != "terhambat" and (not bk or not all((folder / x).exists() for x in bk)):
                gagal.append(f"{nama}: {sid} tanpa berkas bukti yang ada di bukti/"); continue
            jalan += 1
            r["gagal"] += st == "gagal"; r["terhambat"] += st == "terhambat"
        r["skenario"] = f"{jalan}/{len(sk.get(d, []))}"
        if fm.get(d):
            inv = cari(s, "Inventaris form & dropdown") or ""
            baris_inv = [ln for ln in inv.split("\n") if ln.startswith("|") and not re.match(r"^\|\s*-", ln)]
            ada = 0
            for fid, berkas in fm[d]:
                perlu = max(1, jumlah_pilihan(berkas))
                n = sum(1 for ln in baris_inv if berkas in ln)
                if n >= perlu:
                    ada += 1
                else:
                    gagal.append(f"{nama}: form {fid} `{berkas}` diinventaris {n} baris, perlu ≥ {perlu} "
                                 f"(satu baris per komponen pilihan di berkas itu)")
            r["form"] = f"{ada}/{len(fm[d])}"
            r["dropdown"] = len([ln for ln in inv.split("\n") if ln.startswith("|") and ln.count("|") >= 7
                                 and not re.match(r"^\|\s*-", ln)]) - 1
        tm = cari(s, "Temuan") or ""
        for tid, isi in bagian(tm, 3).items():
            mid = re.match(r"((?:" + "|".join(AUDIT_PREFIKS) + r")-\d+)", tid)
            if not mid:
                continue
            hilang = [f for f in FIELD_TEMUAN if f not in isi]
            if hilang:
                gagal.append(f"{nama}: {mid.group(1)} tanpa {hilang}")
            mk = re.search(r"Keparahan:\s*(Kritis|Tinggi|Sedang|Rendah)", isi)
            if mk:
                r["temuan"][mk.group(1)] = r["temuan"].get(mk.group(1), 0) + 1
            if not RE_REF.search(isi.split("Bukti:", 1)[-1] if "Bukti:" in isi else ""):
                gagal.append(f"{nama}: {mid.group(1)} 'Bukti:' tanpa berkas:baris")
            if mid.group(1) not in trk:
                gagal.append(f"{nama}: {mid.group(1)} belum didaftarkan di TRACKER.md")
        r["baris"] = baris_dibaca(teks)[0]
        if re.search(r"\bTODO\b|\bTBD\b|belum dicek", teks):
            gagal.append(f"{nama}: masih ada 'TODO/TBD/belum dicek'")
    selesai = not gagal
    if cetak:
        print(f"== Audit domain {folder.relative_to(ROOT) if folder.is_absolute() else folder}")
        for d, r in ring.items():
            print(f"   {d} {AUDIT_BERKAS[d]:26} skenario {r['skenario']:6} (gagal {r['gagal']}, terhambat {r['terhambat']}) · "
                  f"form {r['form']:6} · dropdown {r['dropdown']} · temuan {r['temuan']} · baris dibaca {r['baris']:,}")
        for g in gagal[:80]:
            print(f"   ✗ {g}")
        print("HASIL:", "SELESAI" if selesai else "BELUM SELESAI")
    return selesai, ring


# ── ringkasan kemajuan ──────────────────────────────────────────────────────────────────────────────────────────────
def progres():
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    out = [f"# Kemajuan review & audit domain (dihasilkan `scripts/review/periksa_selesai.py progres`)", "",
           f"Dihasilkan {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} pada commit `{head}`. "
           "Angka dihitung dari berkas validasi/audit dan tracker — bukan klaim. Jangan disunting tangan.", "",
           "## Batch review", "",
           "| Batch | Isi | Butir lengkap | Baris kode dibaca | Uji lulus / gagal | Putusan | Status | Belum lengkap (maks. 8) |",
           "|---|---|---|---|---|---|---|---|"]
    for k in BATCH:
        sel, r = periksa_batch(k, cetak=False)
        out.append(f"| {k} | {BATCH[k]['judul']} | {r['lengkap']}/{r['butir']} | {r['baris']:,} | {r['lulus']} / "
                   f"{r['gagal_uji']} | {r['putusan'] or '—'} | {'SELESAI' if sel else 'belum'} | "
                   f"{', '.join(r['kurang'][:8]) or '—'} |")
    out += ["", "## Audit domain", ""]
    folders = sorted(p for p in (ROOT / "docs/audit").glob("*-domain*") if p.is_dir())
    if not folders:
        out.append("Belum ada folder `docs/audit/<tanggal>-domain/`.")
    for fd in folders:
        sel, ring = periksa_audit(fd, cetak=False)
        out += [f"### `{fd.relative_to(ROOT)}` — {'SELESAI' if sel else 'belum selesai'}", "",
                "| Domain | Skenario dijalankan | Gagal | Terhambat | Form diinventaris | Baris dropdown | Temuan | Baris dibaca |",
                "|---|---|---|---|---|---|---|---|"]
        for d, r in ring.items():
            out.append(f"| {d} {AUDIT_BERKAS[d]} | {r['skenario']} | {r['gagal']} | {r['terhambat']} | {r['form']} | "
                       f"{r['dropdown']} | {r['temuan'] or '—'} | {r['baris']:,} |")
        out.append("")
    PROGRES.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nditulis: {PROGRES.relative_to(ROOT)}")


# ── uji diri ────────────────────────────────────────────────────────────────────────────────────────────────────────
BAIK = """
### Temuan asli
backend/services/a.py:10 menulis kas tanpa jurnal.
### Perbaikan yang diperiksa
Commit abc1234. Berkas dibaca: backend/services/a.py:1-40, backend/services/b.py:5-20
### Pintu lain
```bash
grep -rn "cash_transactions.insert" backend
```
Kesimpulan: hanya satu pembuat kas.
### Uji yang dijalankan
```bash
python -m pytest tests_mem/test_x.py
```
Hasil: 12 lulus, 0 gagal
### Upaya membantah
- [ulang] kirim dua kali dengan kunci sama. Hasil: satu kas.
- [jurnal_gagal] paksa jurnal gagal. Hasil: penanda gagal muncul, bisa diulang.
### Putusan
Putusan: verified
Alasan: jalur tunggal terbukti di backend/services/a.py:22 dan uji test_x_ulang lulus; tidak ada pintu kedua.
"""


def uji_diri():
    gagal = 0

    def kasus(nama, isi, harap_bersih):
        nonlocal gagal
        ms, _ = periksa_butir(isi, SUB_BARIS, set(PUTUSAN_TRACKER))
        ok = (not ms) == harap_bersih
        gagal += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {nama} → {'bersih' if not ms else ms[0]}")
    kasus("butir lengkap → hijau", BAIK, True)
    kasus("tanpa upaya membantah → MERAH", BAIK.split("### Upaya membantah")[0] + "### Upaya membantah\n### Putusan\n"
          + BAIK.split("### Putusan")[1], False)
    kasus("baris dibaca terlalu sedikit → MERAH", BAIK.replace("a.py:1-40", "a.py:1-3").replace("b.py:5-20", "b.py:5-6"),
          False)
    kasus("alasan bersandar laporan → MERAH", BAIK.replace(
        "jalur tunggal terbukti di backend/services/a.py:22 dan uji test_x_ulang lulus; tidak ada pintu kedua.",
        "menurut laporan pelaksana semuanya sudah benar dan lengkap sehingga aman untuk ditutup."), False)
    kasus("verified padahal uji gagal → MERAH", BAIK.replace("12 lulus, 0 gagal", "11 lulus, 1 gagal"), False)
    kasus("kategori bantah asing → MERAH", BAIK.replace("[ulang]", "[asal]").replace("[jurnal_gagal]", "[coba]"), False)
    kasus("tanpa hasil uji → MERAH", BAIK.replace("Hasil: 12 lulus, 0 gagal", "semua aman"), False)
    print("SELF-TEST", "HIJAU" if not gagal else f"MERAH ({gagal} gagal)")
    return 0 if not gagal else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perintah", nargs="?", choices=["daftar", "review", "audit", "progres"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--uji-diri", action="store_true")
    a = ap.parse_args()
    if a.uji_diri:
        return uji_diri()
    if a.perintah == "daftar":
        if a.arg == "B0":
            print("B0: docs/reviews/2026-11-13/hasil/validasi-R0.md — ## Keputusan 1 … 8 + ## Fungsi yang diubah dua sisi:",
                  ", ".join(FUNGSI_DUA_SISI))
            return 0
        rows = isi_batch(a.arg)
        print(f"{a.arg} — {BATCH[a.arg]['judul']}: {len(rows)} butir, {len({r['unit'] for r in rows})} unit")
        for r in rows:
            print(f"   {r['id']:7} {r['keparahan']:7} {r['unit']:6} {r['status']:27} → hasil/validasi-{r['unit']}.md")
        return 0
    if a.perintah == "review":
        return 0 if periksa_batch(a.arg)[0] else 1
    if a.perintah == "audit":
        return 0 if periksa_audit(Path(a.arg) if Path(a.arg).is_absolute() else ROOT / a.arg)[0] else 1
    if a.perintah == "progres":
        progres(); return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:   # keluaran dipotong `head`
        sys.exit(0)
