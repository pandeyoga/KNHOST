"""Ekspor data alur ke berkas yang bisa diedit: LEMBAR_HASIL_UAT.md & SKENARIO_UAT.json."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sections  # noqa: E402
import back  # noqa: E402
import front  # noqa: E402
import sched  # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, ".."))


def plain(s):
    s = re.sub(r"\[\[([^\]]+)\]\]", r"[\1]", s or "")
    return s.replace("**", "").replace("`", "").replace("*", "").replace("\n", " ")


def main():
    flows = []
    for code, kicker, title, fn, rows, chips, lead, info in sections.FLOWS:
        steps = []
        for r in rows:
            no, role, nav, act, dec, exp, test = (list(r) + [""] * 7)[:7]
            if isinstance(role, tuple):
                role = role[0]
            steps.append({"id": no, "peran": role, "navigasi": plain(nav), "aktivitas": plain(act),
                          "keputusan": plain(dec), "hasil_diharapkan": plain(exp), "uji_pra_uat": plain(test),
                          "status": "NOT_RUN"})
        flows.append({"kode": code, "judul": title, "sesi": chips[0] if chips else "", "ringkasan": plain(lead), "langkah": steps})
    data = {"dokumen": "KN-UAT-E2E-002", "versi": "2.0", "disusun": "2026-10-21",
            "kandidat_uji": {"pertama": "main@af24f9c + lokal", "uji_ulang": "main@a3f7936 + lokal (03.05)"},
            "jadwal": {"hari_1": [dict(zip(["waktu", "menit", "sesi", "tujuan", "aktivitas", "peran", "data", "output"], r)) for r in sched.DAY1],
                       "hari_2": [dict(zip(["waktu", "menit", "sesi", "tujuan", "aktivitas", "peran", "data", "output"], r)) for r in sched.DAY2]},
            "keputusan": [dict(zip(["id", "langkah", "pertanyaan", "pemutus", "pilihan", "aturan"], d)) for d in front.DECISIONS],
            "alur": flows,
            "akses": [dict(zip(["id", "peran", "menu", "boleh", "tidak_boleh", "uji_pra_uat"], a)) for a in back.ACCESS],
            "konsistensi": [dict(zip(["id", "pemeriksaan", "harus_benar", "uji_pra_uat"], k)) for k in back.CONSIST],
            "temuan": [dict(zip(["id", "prioritas", "langkah", "temuan", "dampak", "akar_masalah", "rencana", "uji_regresi", "keputusan_owner"],
                                [plain(x) for x in f])) for f in back.FINDINGS]}
    json.dump(data, open(os.path.join(OUT, "SKENARIO_UAT.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)

    md = ["# Lembar hasil UAT — ERP Kain Nusantara (KN-UAT-E2E-002 v2.0)", "",
          "**Tanggal:** Hari 1 ______ · Hari 2 ______  **Kandidat (URL/commit):** ______  **Fasilitator:** ______  **Pencatat:** ______", "",
          "Status: `L` Lulus · `G` Gagal · `T` Terblokir · `TD` Tidak diuji. Isi nomor dokumen sistem & ID temuan.", ""]
    for code, kicker, title, fn, rows, chips, lead, info in sections.FLOWS:
        md += [f"## {title}", "", "| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |", "|---|---|---|---|---|---|"]
        for r in rows:
            role = r[1][0] if isinstance(r[1], tuple) else r[1]
            md.append(f"| {r[0]} | {role} | {back._short(plain(r[3] if r[3] and r[3] != '—' else r[2]), 110)} |  |  |  |")
        md.append("")
    md += ["## J — Akses per peran", "", "| ID | Peran | Uji | Status | Catatan |", "|---|---|---|---|---|"]
    md += [f"| {a[0]} | {a[1]} | positif & negatif akses |  |  |" for a in back.ACCESS]
    md += ["", "## K — Konsistensi data", "", "| ID | Pemeriksaan | Status | Catatan |", "|---|---|---|---|"]
    md += [f"| {k[0]} | {k[1]} |  |  |" for k in back.CONSIST]
    md += ["", "## Form satu temuan", "", "| Field | Isi |", "|---|---|"]
    md += [f"| {x} |  |" for x in ("ID temuan / langkah", "Akun / peran / badan usaha", "Dokumen / roll", "Langkah reproduksi",
                                   "Seharusnya", "Yang terjadi / dampak", "Bug / keputusan bisnis / data", "Prioritas / PIC / target", "Commit perbaikan / retest")]
    md += ["", "## Penutupan", "", "- Lulus ___ · Gagal ___ · Terblokir ___ · Tidak diuji ___",
           "- Alur dinyatakan siap pakai: ___", "- Keputusan bisnis yang diambil: ___", "- Rencana perbaikan & tanggal uji ulang: ___",
           "- Tanda tangan: pemilik proses ___ · Production IT ___ · fasilitator ___ · pencatat ___", ""]
    open(os.path.join(OUT, "LEMBAR_HASIL_UAT.md"), "w", encoding="utf-8", newline="\n").write("\n".join(md))
    n = sum(len(f["langkah"]) for f in flows)
    print("langkah:", n, "keputusan:", len(front.DECISIONS), "temuan:", len(back.FINDINGS))


if __name__ == "__main__":
    main()
