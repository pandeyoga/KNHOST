#!/usr/bin/env python3
"""Pemeriksa konsistensi blueprint. Baca-saja terhadap kode; hanya menulis STATUS.md bila diminta.

    python docs/blueprint/alat/cek_blueprint.py            # periksa indeks, berkas unit, jangkar kode
    python docs/blueprint/alat/cek_blueprint.py --status   # buat STATUS.md awal (menolak bila sudah ada)

Yang diperiksa:
  1. Tiap baris INDEKS_UNIT.md punya berkas unit/<ID>.md, dan sebaliknya.
  2. Prasyarat menunjuk unit yang ada; tiap temuan ditutup tepat satu unit.
  3. Berkas unit memuat bagian wajib templat.
  4. Jangkar kode `path:baris` (`simbol`): berkas ada, baris dalam jangkauan, simbol ada dalam ±25 baris
     atau baris itu berada di dalam fungsi/kelas bernama simbol tersebut (definisinya ≤ 400 baris di atas).
Keluar dengan kode 1 bila ada yang bermasalah.
"""
import collections
import re
import sys
from pathlib import Path

BP = Path(__file__).resolve().parents[1]
ROOT = BP.parents[1]
WAJIB = ["## Tujuan", "## Keadaan sekarang", "## Perubahan", "## Uji penerimaan", "## Langkah kerja",
         "## Di luar lingkup", "## Asumsi dan risiko"]
RX_ID = r"(?:PK-\d+|(?:PR|KF|KP|MN|KM|CR|PM|TX|PY|AG)-T\d+)"
RX_ANCHOR = re.compile(r"`((?:backend|frontend|scripts|deploy|docs)/[\w./\-]+\.(?:py|jsx|js|md|sh|yml|json))"
                       r"(?::(\d+)(?:-(\d+))?)?`(?:\s*\(`([^`]+)`\))?")


def baca_indeks():
    units = []
    for line in (BP / "INDEKS_UNIT.md").read_text(encoding="utf-8").splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 10 and re.fullmatch(RX_ID, cols[2] or ""):
            units.append({"urut": cols[1], "id": cols[2], "judul": cols[3], "jalur": cols[4], "prasyarat": cols[5],
                          "menutup": cols[6], "risiko": cols[7], "henti": cols[8], "asal": cols[9]})
    return units


def cek_jangkar(path: Path):
    galat = []
    txt = path.read_text(encoding="utf-8")
    n = 0
    # Berkas yang belum ada sah bila unit ini yang melahirkannya: cukup SATU penyebutan di dekat kata
    # "baru/lahir/dibuat/ditulis"; penyebutan lain atas path yang sama ikut dianggap sah.
    baru = set()
    for m in RX_ANCHOR.finditer(txt):
        sekitar = txt[max(0, m.start() - 140): m.end() + 80].lower()
        if any(k in sekitar for k in ("baru", "lahir", "dibuat", "ditulis", "migrasi")):
            baru.add(m.group(1))
    for m in RX_ANCHOR.finditer(txt):
        rel, l1, l2, sym = m.groups()
        n += 1
        fp = ROOT / rel
        if not fp.exists():
            if rel in baru or "tests_mem" in rel or "/tests/test_bp_" in rel or "/hasil/" in rel \
                    or rel.startswith("scripts/migrate_") or rel.endswith("STATUS.md"):
                continue
            # Tanpa nomor baris dan foldernya ada (atau folder data blueprint): dianggap berkas yang akan dibuat unit.
            # Dengan nomor baris pasti keliru — tidak mungkin menunjuk baris di berkas yang belum ada.
            if not l1 and ((fp.parent.exists() and fp.parent.is_dir())
                           or rel.startswith(("docs/blueprint/data/", "backend/data/"))):
                continue
            galat.append(f"berkas tidak ada: {rel}")
            continue
        if not l1:
            continue
        lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
        a, b = int(l1), int(l2 or l1)
        if b > len(lines) + 1:
            galat.append(f"baris di luar jangkauan: {rel}:{l1} (berkas {len(lines)} baris)")
            continue
        if sym and not sym.strip().startswith(("/", "@", "GET", "POST", "PUT", "PATCH", "DELETE")):
            nama = re.split(r"[\s(=.:,]", sym.strip())[0]
            seg = "\n".join(lines[max(0, a - 26): min(len(lines), b + 25)])
            if nama and nama not in seg:
                # Jangkar boleh menunjuk baris di DALAM fungsi yang disebut: cari definisinya ke atas.
                atas = "\n".join(lines[max(0, a - 400): a])
                if not re.search(rf"(?:def|class|const|function)\s+{re.escape(nama)}\b|^\s*{re.escape(nama)}\s*[=:]",
                                 atas, re.M):
                    galat.append(f"simbol `{nama}` tidak ditemukan dekat {rel}:{l1}")
    return n, galat


def main() -> int:
    units = baca_indeks()
    ids = [u["id"] for u in units]
    masalah = []
    for k, v in collections.Counter(ids).items():
        if v > 1:
            masalah.append(f"INDEKS: ID kembar {k}")
    berkas = {p.stem for p in (BP / "unit").glob("*.md") if not p.stem.startswith("_")}
    for i in ids:
        if i not in berkas:
            masalah.append(f"belum ada berkas unit/{i}.md")
    for b in sorted(berkas - set(ids)):
        masalah.append(f"berkas unit/{b}.md tidak ada di INDEKS")
    tutup = collections.defaultdict(list)
    for u in units:
        for p in re.findall(RX_ID, u["prasyarat"]):
            if p not in ids:
                masalah.append(f"{u['id']}: prasyarat {p} tidak ada di INDEKS")
        for t in re.findall(r"\b[A-Z]{2}(?:-UX)?-\d+\b", u["menutup"]):
            tutup[t].append(u["id"])
    for t, l in tutup.items():
        if len(l) > 1:
            masalah.append(f"temuan {t} ditutup lebih dari satu unit: {', '.join(l)}")
    total_jangkar = 0
    for i in ids:
        p = BP / "unit" / f"{i}.md"
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        if not txt.startswith(f"# {i} "):
            masalah.append(f"unit/{i}.md: judul tidak diawali '# {i} —'")
        for w in WAJIB:
            if w not in txt:
                masalah.append(f"unit/{i}.md: bagian '{w}' tidak ada")
        if "| Menutup temuan |" not in txt or "| Prasyarat |" not in txt:
            masalah.append(f"unit/{i}.md: tabel kepala tidak lengkap")
        n, g = cek_jangkar(p)
        total_jangkar += n
        masalah += [f"unit/{i}.md: {x}" for x in g]
    for extra in ("00_ATURAN_EKSEKUSI.md", "02_STANDAR.md", "03_LINGKUNGAN_UJI.md"):
        n, g = cek_jangkar(BP / extra)
        total_jangkar += n
        masalah += [f"{extra}: {x}" for x in g]

    if "--status" in sys.argv:
        tujuan = BP / "STATUS.md"
        if tujuan.exists():
            print("STATUS.md sudah ada — tidak ditimpa.")
        else:
            baris = ["# Status unit kerja", "",
                     "Papan kerja agen pelaksana. Aturan mengubahnya: `00_ATURAN_EKSEKUSI.md` §5. Urutan = urutan "
                     "pengerjaan (`INDEKS_UNIT.md`).", "",
                     "| # | ID | Judul | Prasyarat | Status | Commit | Laporan | Catatan |", "|---|---|---|---|---|---|---|---|"]
            for u in units:
                pr = re.findall(RX_ID, u["prasyarat"])
                henti = u["henti"] not in ("—", "", "-")
                tahan_awal = henti and "sesudahnya" not in u["henti"] and "bila" not in u["henti"] \
                    and "untuk" not in u["henti"] and "H5" not in u["henti"]
                if tahan_awal:
                    st = "tahan"
                elif pr or "tervalidasi" in u["prasyarat"]:
                    st = "menunggu"
                else:
                    st = "siap"
                cat = f"Titik henti {u['henti']}" if henti else ""
                baris.append(f"| {u['urut']} | {u['id']} | {u['judul']} | {u['prasyarat']} | {st} |  |  | {cat} |")
            baris += ["", "## Menunggu pemilik", "",
                      "Diisi agen saat sebuah unit masuk `tahan`: satu kalimat pertanyaan, pilihan yang tersedia, usulan.",
                      "", "| Unit | Pertanyaan | Pilihan | Usulan |", "|---|---|---|---|", "",
                      "## Catatan sesi", "", "Diisi agen di akhir tiap sesi: tanggal, unit yang selesai, unit yang "
                      "tertahan dan mengapa.", ""]
            tujuan.write_text("\n".join(baris), encoding="utf-8", newline="\n")
            print("STATUS.md dibuat.")

    print(f"unit di indeks: {len(ids)} · berkas unit: {len(berkas)} · jangkar diperiksa: {total_jangkar} · "
          f"masalah: {len(masalah)}")
    for m in masalah:
        print("  -", m)
    return 1 if masalah else 0


if __name__ == "__main__":
    sys.exit(main())
