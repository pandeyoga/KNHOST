"""Selesaikan bentrok penggabungan PY-T3 (kedua perilaku dipertahankan).

    python3 pyt3_selesai.py <keluaran_files_dir>
"""
import re
import sys

D = sys.argv[1]
POLA = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)


def baca(p):
    return open(f"{D}/{p}", encoding="utf-8").read()


def tulis(p, s):
    assert "<<<<<<<" not in s and ">>>>>>>" not in s, p
    open(f"{D}/{p}", "w", encoding="utf-8").write(s)


def kft1(s):
    def ganti(m):
        head, ours = m.group(1), m.group(2)
        if "PYT3_KUNCI = 10" in ours:            # konstanta: keduanya
            return head + ours
        # jumlah: komentar + total keduanya
        head = head.replace("TX-T2 pemicu faktur pajak.", "TX-T2 pemicu faktur pajak; PY-T3 sepuluh aturan hitung gaji.")
        return head.replace("+ PYT2_KUNCI + TXT2_KUNCI", "+ PYT2_KUNCI + TXT2_KUNCI + PYT3_KUNCI")
    return POLA.sub(ganti, s)


def kn32(s):
    def ganti(m):
        head, ours = m.group(1), m.group(2)
        nomor = max(int(x) for x in re.findall(r"### 9\.(\d+) ", head)) + 1 if re.findall(r"### 9\.(\d+) ", head) else 20
        ours = re.sub(r"### 9\.19 (Penggajian: aturan hitung)", f"### 9.{nomor} \\1", ours)
        return head.rstrip("\n") + "\n\n" + ours if not head.endswith("\n\n") else head + ours
    return POLA.sub(ganti, s)


s = baca("backend/tests_mem/test_KFT1_izin_pengaturan.py")
if "<<<<<<<" in s:
    tulis("backend/tests_mem/test_KFT1_izin_pengaturan.py", kft1(s))
s = baca("docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md")
if "<<<<<<<" in s:
    tulis("docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md", kn32(s))
print("selesai")
