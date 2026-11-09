"""Audit B1b — susun ulang `B1-MATRIKS-CAKUPAN.md` dari kode + anotasi kunjungan B1 & B1b (HANYA BACA kode).

Visibilitas sel = `b1_matrix_report.rows()` (tiruan `roleCanSee` + `hubTabsForRole`). Anotasi kunjungan dibaca dari
`scripts/audit/b1b_matrix_notes.json` berbentuk {"<view>": {"<peran>": {"D": "...", "HP": "..."}}} (gabungan B1 + B1b).
Sel tanpa anotasi tetap `K` / `K·p` / `K·d`. Menimpa HANYA dua tabel sel di `--out` (bawaan: berkas matriks di paket
audit; teks pengantar & tabel aplikasi HP dipertahankan) dan mencetak hitungan sel tampil / dikunjungi sebelum (B1,
`--b1-notes`) dan sesudah (B1b).

Pakai: PYTHONUTF8=1 python scripts/audit/b1b_build_matrix.py [--notes ...] [--b1-notes ...] [--out ...]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from b1_matrix_report import ROLES, rows  # noqa: E402

ROOT = HERE.parents[1]
DEF_OUT = ROOT / "docs" / "audit" / "2026-11-09-wms-rfid" / "B1-MATRIKS-CAKUPAN.md"
ABBR = {"admin": "adm", "manager": "mgr", "warehouse_admin": "wha", "warehouse": "wh", "sales": "sls",
        "sales_admin": "sla", "finance": "fin", "md": "md", "md_quality": "mdq", "qc": "qc",
        "sample_admin": "sma", "driver": "drv"}
HP_APP = {"md": "MobileMdApp", "sales": "MobileSalesApp", "sales_admin": "MobileSalesApp",
          "warehouse": "MobileWarehouseApp", "warehouse_admin": "MobileWarehouseApp", "driver": "MobileWarehouseApp"}
RESPONSIVE = ("goods-receipts", "inspections", "makloon-orders", "md-products")


def default_cell(row, role, mode):
    if not row["vis"][role]:
        return "–"
    if mode == "D":
        return "K"
    full = HP_APP.get(role) is None or row["view"] in RESPONSIVE
    return "K·p" if full else "K·d"


def build(notes):
    data = rows()
    tables, stats = {}, {}
    for mode in ("D", "HP"):
        lines = ["| Grup › Menu › Tab (view) | " + " | ".join(ABBR[r] for r in ROLES) + " |",
                 "|---|" + "---|" * len(ROLES)]
        shown = visited = 0
        for row in data:
            cells = []
            for r in ROLES:
                n = (notes.get(row["view"]) or {}).get(r) or {}
                c = n.get(mode) or default_cell(row, r, mode)
                if row["vis"][r]:
                    shown += 1
                    if not c.startswith("K"):
                        visited += 1
                cells.append(c)
            name = f"{row['group']} › {row['menu']}" + (f" › {row['tab']}" if row["tab"] else "") + f" (`{row['view']}`)"
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        tables[mode] = "\n".join(lines)
        stats[mode] = (shown, visited)
    return tables, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default=str(HERE / "b1b_matrix_notes.json"))
    ap.add_argument("--b1-notes", default="", help="anotasi B1 saja (untuk hitungan 'sebelum')")
    ap.add_argument("--out", default=str(DEF_OUT))
    a = ap.parse_args()
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8"))
    tables, stats = build(notes)
    if a.b1_notes:
        _, before = build(json.loads(Path(a.b1_notes).read_text(encoding="utf-8")))
        print("SEBELUM (B1):", {m: f"{v}/{s}" for m, (s, v) in before.items()})
    print("SESUDAH (B1b):", {m: f"{v}/{s}" for m, (s, v) in stats.items()})
    # Teks pengantar (sebelum tabel desktop) & penutup (mulai "### Aplikasi HP per peran") dipertahankan dari berkas
    # yang ada — keduanya disunting tangan; hanya dua tabel sel yang dibangkitkan ulang.
    cur = Path(a.out).read_text(encoding="utf-8")
    i, j = cur.index("### Desktop"), cur.index("### Aplikasi HP per peran")
    body = (cur[:i] + "### Desktop (1024 px)\n\n" + tables["D"] + "\n\n### HP (390 × 844)\n\n" + tables["HP"]
            + "\n\n\n" + cur[j:])
    Path(a.out).write_text(body, encoding="utf-8", newline="\n")
    print("ditulis:", a.out)


if __name__ == "__main__":
    main()
