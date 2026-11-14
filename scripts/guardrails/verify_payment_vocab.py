#!/usr/bin/env python3
"""INV-PAY-VOCAB-01 — kosakata CARA BAYAR hanya dari satu daftar induk (PM-T1, `docs/blueprint/unit/PM-T1.md`).

KELAS BUG YANG DICEGAH
======================
Sebelum PM-T1 tiap layar yang bertanya "dibayar lewat apa" menulis daftarnya sendiri: kwitansi `transfer · cash · giro ·
qris`, bayar tagihan pemasok & voucher biaya masuk `transfer · tunai · giro`, kontrabon `transfer · giro · cash`, uang
muka `tunai · transfer`, selisih bayar & antar-PT `transfer · cash`. Server membedakan tunai dengan empat himpunan
`{"cash", "tunai", "kontan"}` yang tidak sama isinya. Akibatnya cara bayar yang dimatikan untuk satu PT tetap muncul di
layar lain, dan kata yang sama ("tunai" vs "cash") tersimpan dua bentuk.

Sumber sah satu-satunya:
  * layar  — `frontend/src/config/paymentMethods.js` (`usePaymentMethods(arah)`, dari `GET /api/payment-methods`);
  * server — `backend/services/payment_method_service.py` (`normalize`, `get`, `active_for`, `is_cash`).

ATURAN
======
  F1  berkas layar (`frontend/src`, selain `__tests__`) yang memuat objek pilihan `{ value: "<kata>" … }` dengan
      <kata> ∈ transfer · cash · tunai · giro · qris · kontan;
  F2  berkas layar yang memuat larik/himpunan ≥ 2 kata itu (`["cash", "tunai"]`);
  S1  berkas server (`backend`, selain uji/benih) yang memuat literal himpunan/tuple/list ≥ 2 kata itu
      (`{"cash", "tunai", "kontan"}`, `in ("tunai", "cash")`).
Pengecualian tertulis (berkas, kata) → alasan: kosakata TERMIN (profil bayar pesanan, jenis syarat bayar), kategori kas
"Transfer / Top-up", jenis pengembalian retur, jenis rekening (bank · kas tunai). Pengecualian yang tidak lagi terpakai
= merah (daftar basi).

Pakai:  python3 scripts/guardrails/verify_payment_vocab.py
        python3 scripts/guardrails/verify_payment_vocab.py --self-test
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import Guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KATA = ("transfer", "cash", "tunai", "giro", "qris", "kontan")
_K = "|".join(KATA)
FE_SUMBER = "config/paymentMethods.js"
BE_SUMBER = "services/payment_method_service.py"

#: (berkas relatif `frontend/src`, kata) → alasan.
FE_PENGECUALIAN: Dict[Tuple[str, str], str] = {
    ("components/ReturnPolicyEditor.jsx", "cash"):
        "jenis pengembalian retur (dana tunai / kredit toko / tukar barang), bukan cara bayar",
    ("features/finance/BankAccountForm.jsx", "cash"):
        "jenis rekening (rekening bank · kas tunai), bukan cara bayar",
    ("features/settings/masters/masterFieldsConfig.js", "cash"):
        "kosakata termin: jenis syarat bayar (tunai · kredit · DP · bertahap)",
    ("features/purchasing/CashManagementView.jsx", "transfer"):
        "kategori transaksi kas \"Transfer / Top-up\", bukan cara bayar",
}
#: berkas relatif `backend` → alasan (seluruh himpunan di berkas itu dikecualikan).
BE_PENGECUALIAN: Dict[str, str] = {
    "services/customer_service.py":
        "kosakata termin: `NON_AR_METHODS` = profil bayar pesanan kontan/tunai (bukan cara bayar kwitansi)",
    "services/cashflow_forecast_service.py":
        "kosakata termin: `NON_AR_METHODS` = profil bayar pesanan tunai (bukan cara bayar kwitansi)",
}

RE_OPSI = re.compile(r"\{\s*value\s*:\s*[\"'](" + _K + r")[\"']")
RE_LARIK = re.compile(r"\[\s*[\"'](" + _K + r")[\"']\s*,\s*[\"'](" + _K + r")[\"']")


def _tanpa_komentar(src: str) -> str:
    """Buang komentar `//` dan `/* */`, pertahankan string dan nomor baris."""
    out, i, n = [], 0, len(src)
    while i < n:
        c, nx = src[i], src[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "/" and nx == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
            continue
        if c in ("'", '"', "`"):
            q = c
            out.append(c)
            i += 1
            while i < n and src[i] != q:
                if src[i] == "\\":
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            if i < n:
                out.append(src[i])
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def periksa_layar(fe_src: Path, pengecualian: Dict[Tuple[str, str], str]) -> Tuple[List[str], set, int]:
    temuan: List[str] = []
    terpakai: set = set()
    n = 0
    for p in sorted(list(fe_src.rglob("*.js")) + list(fe_src.rglob("*.jsx"))):
        rel = str(p.relative_to(fe_src)).replace(os.sep, "/")
        if "__tests__" in rel or rel.startswith("components/ui/") or rel == FE_SUMBER:
            continue
        n += 1
        src = _tanpa_komentar(p.read_text(encoding="utf-8", errors="ignore"))
        for pola, sebab in ((RE_OPSI, "pilihan cara bayar ditulis sendiri"),
                            (RE_LARIK, "himpunan kata cara bayar ditulis sendiri")):
            for m in pola.finditer(src):
                kata = m.group(1)
                if (rel, kata) in pengecualian:
                    terpakai.add((rel, kata))
                    continue
                baris = src[:m.start()].count("\n") + 1
                temuan.append(f"{rel} baris {baris}: {sebab} ({m.group(0).strip()}…) — pakai "
                              f"`usePaymentMethods(arah)` dari `{FE_SUMBER}`.")
    return temuan, terpakai, n


def _himpunan_kata(node: ast.AST) -> List[str]:
    if not isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        return []
    nilai = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    if len(nilai) != len(node.elts):
        return []
    kena = sorted({v for v in nilai if v in KATA})   # ≥ 2 kata BERBEDA (pasangan kode–label "transfer"/"Transfer" bukan)
    return kena if len(kena) >= 2 else []


def periksa_server(be: Path, pengecualian: Dict[str, str]) -> Tuple[List[str], set, int]:
    temuan: List[str] = []
    terpakai: set = set()
    n = 0
    for p in sorted(be.rglob("*.py")):
        rel = str(p.relative_to(be)).replace(os.sep, "/")
        nama = p.name
        if (rel.split("/")[0] in ("tests", "tests_mem", "scripts", "data") or nama.startswith(("test_", "seed_"))
                or nama.startswith("backend_test") or rel == BE_SUMBER):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        n += 1
        for node in ast.walk(tree):
            kena = _himpunan_kata(node)
            if not kena:
                continue
            if rel in pengecualian:
                terpakai.add(rel)
                continue
            temuan.append(f"{rel} baris {node.lineno}: himpunan kata cara bayar {sorted(set(kena))} ditulis sendiri — "
                          f"pakai `payment_method_service.normalize` / `is_cash`.")
    return temuan, terpakai, n


def jalankan(root: Path, fe_pengecualian=None, be_pengecualian=None) -> Tuple[List[str], int]:
    fe_p = FE_PENGECUALIAN if fe_pengecualian is None else fe_pengecualian
    be_p = BE_PENGECUALIAN if be_pengecualian is None else be_pengecualian
    t1, pakai1, n1 = periksa_layar(root / "frontend" / "src", fe_p)
    t2, pakai2, n2 = periksa_server(root / "backend", be_p)
    basi = [f"pengecualian basi (tidak ada lagi yang cocok): {k[0]} · {k[1]}" for k in fe_p if k not in pakai1]
    basi += [f"pengecualian basi (tidak ada lagi yang cocok): {k}" for k in be_p if k not in pakai2]
    for k, alasan in list(fe_p.items()) + [((k, ""), v) for k, v in be_p.items()]:
        if len((alasan or "").strip()) < 20:
            basi.append(f"pengecualian tanpa alasan tertulis: {k}")
    return t1 + t2 + basi, n1 + n2


def main() -> int:
    g = Guard("INV-PAY-VOCAB-01", "kosakata cara bayar hanya dari daftar induk (PM-T1)")
    temuan, n = jalankan(ROOT)
    g.bump(n)
    for t in temuan:
        g.add(t)
    return g.finish()


# ── Uji-diri: bukti-merah dua arah ─────────────────────────────────────────────────────────────────────────────────
def _repo_tiruan(berkas: Dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="kn_payvocab_"))
    for rel, isi in berkas.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(isi, encoding="utf-8")
    (d / "frontend" / "src").mkdir(parents=True, exist_ok=True)
    (d / "backend").mkdir(parents=True, exist_ok=True)
    return d


KASUS = [
    # (nama, berkas, pengecualian layar, pengecualian server, harus_merah)
    ("F1 pilihan 'tunai' di layar", {"frontend/src/A.jsx": 'const O = [{ value: "tunai", label: "Tunai" }];'},
     {}, {}, True),
    ("F1 pilihan 'transfer' satu baris options", {"frontend/src/B.jsx": 'x = {options: [{value:"transfer"}]}'},
     {}, {}, True),
    ("F2 larik kata cara bayar", {"frontend/src/C.js": 'const t = ["cash", "tunai"].includes(m);'}, {}, {}, True),
    ("F sumber resmi boleh", {"frontend/src/config/paymentMethods.js": 'const F = [{ value: "cash" }];'},
     {}, {}, False),
    ("F berkas uji boleh", {"frontend/src/x/__tests__/a.test.js": 'const F = [{ value: "cash" }];'}, {}, {}, False),
    ("F komentar tidak dihitung", {"frontend/src/D.jsx": '// [{ value: "tunai" }]\nconst a = 1;'}, {}, {}, False),
    ("F kata lain (kredit) bukan cara bayar", {"frontend/src/E.jsx": 'const O = [{ value: "credit" }];'},
     {}, {}, False),
    ("F pengecualian beralasan", {"frontend/src/F.jsx": 'const O = [{ value: "cash", label: "Kas" }];'},
     {("F.jsx", "cash"): "jenis rekening (bank · kas tunai), bukan cara bayar"}, {}, False),
    ("F pengecualian basi = merah", {"frontend/src/G.jsx": "const a = 1;"},
     {("G.jsx", "cash"): "jenis rekening (bank · kas tunai), bukan cara bayar"}, {}, True),
    ("F pengecualian tanpa alasan = merah", {"frontend/src/H.jsx": 'const O = [{ value: "cash" }];'},
     {("H.jsx", "cash"): "x"}, {}, True),
    ("S1 himpunan tunai di server", {"backend/services/a.py": 'CASH = {"cash", "tunai", "kontan"}\n'}, {}, {}, True),
    ("S1 tuple di perbandingan", {"backend/services/b.py": 'def f(m):\n    return m in ("tunai", "cash")\n'},
     {}, {}, True),
    ("S1 sumber resmi boleh", {"backend/services/payment_method_service.py": 'K = ("cash", "tunai")\n'},
     {}, {}, False),
    ("S1 satu kata + termin bukan himpunan cara bayar", {"backend/schemas_x.py": 'A = ["tunai", "tempo"]\n'},
     {}, {}, False),
    ("S1 pasangan kode–label bukan himpunan", {"backend/services/e.py": 'T = ("transfer", "Transfer")\n'},
     {}, {}, False),
    ("S1 komentar tidak dihitung", {"backend/services/c.py": '# {"cash", "tunai"}\nX = 1\n'}, {}, {}, False),
    ("S1 berkas uji & benih boleh", {"backend/tests/test_a.py": 'A = {"cash", "tunai"}\n',
                                     "backend/seed_x.py": 'A = {"cash", "tunai"}\n'}, {}, {}, False),
    ("S1 pengecualian beralasan", {"backend/services/d.py": 'N = {"kontan", "tunai", "cash"}\n'},
     {}, {"services/d.py": "kosakata termin: profil bayar pesanan kontan/tunai"}, False),
]


def self_test() -> int:
    gagal = 0
    for nama, berkas, fe_p, be_p, merah in KASUS:
        d = _repo_tiruan(berkas)
        temuan, _ = jalankan(d, fe_p, be_p)
        ok = bool(temuan) == merah
        gagal += 0 if ok else 1
        print(f"  {'OK ' if ok else 'GAGAL'} {nama}: {'merah' if temuan else 'hijau'}"
              + ("" if ok else f" (seharusnya {'merah' if merah else 'hijau'}) {temuan}"))
    print(f"  {len(KASUS) - gagal}/{len(KASUS)} kasus sesuai harapan.")
    if gagal:
        print("  SELF-TEST MERAH — penjaga kosakata cara bayar tidak bisa dipercaya.")
    else:
        print("  HIJAU — penjaga terbukti menuduh kosakata cara bayar yang ditulis sendiri.")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
