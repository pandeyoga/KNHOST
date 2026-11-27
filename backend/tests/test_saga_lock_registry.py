"""OPS-04 — setiap koleksi yang diklaim `atomic_claim.claim()` wajib terdaftar di Kunci Saga (terlihat & bisa dilepas).

Kas & Bank 2 (perbaikan akhir, I2) — penjaga lama hanya mencocokkan `claim("literal"`, jadi klaim lewat konstanta modul
(`_saga.claim(COLL, …)`) luput: `cash_out_requests`, `fund_transfers`, dan delapan koleksi lain tidak pernah muncul di
Kunci Saga. Kini setiap panggilan `claim` pada modul `atomic_claim` (apa pun nama aliasnya) dibaca lewat AST: argumen
pertama berupa teks, konstanta modul (`COLL = "…"`), atau konstanta yang diimpor dari modul `services`/`routers` lain.
Argumen lain (variabel lokal) WAJIB dinyatakan di `KLAIM_DINAMIS` beserta koleksi yang mungkin — klaim baru yang tidak
bisa diurai membuat penjaga ini merah, bukan diam-diam lolos.
"""
import ast
import glob
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _klaim_dinamis():
    """(berkas relatif terhadap backend/, teks argumen) → koleksi yang mungkin diklaim lewat argumen itu."""
    from services.ap_payment_service import KINDS as AP_KINDS
    return {("services/ap_payment_service.py", "coll"): {coll for coll, _aksi in AP_KINDS.values()}}


def _konstanta(path: Path) -> dict:
    out = {}
    for n in ast.parse(path.read_text(encoding="utf-8")).body:
        target = n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else getattr(n, "target", None)
        nilai = getattr(n, "value", None)
        if isinstance(target, ast.Name) and isinstance(nilai, ast.Constant) and isinstance(nilai.value, str):
            out[target.id] = nilai.value
    return out


def _klaim_di(path: Path):
    """→ (koleksi yang terurai, [(baris, teks argumen)] yang tidak terurai) untuk satu berkas."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    alias_modul, impor = set(), {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "services":
            alias_modul |= {a.asname or a.name for a in n.names if a.name == "atomic_claim"}
        elif isinstance(n, ast.ImportFrom) and n.module == "services.atomic_claim":
            for a in n.names:   # `from services.atomic_claim import claim [as …]`
                if a.name == "claim":
                    impor[a.asname or a.name] = ("__claim__", "")
        elif isinstance(n, ast.Import):
            alias_modul |= {a.asname for a in n.names if a.name == "services.atomic_claim" and a.asname}
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in ("services", "routers") \
                and n.module not in ("services", "services.atomic_claim"):
            for a in n.names:
                impor[a.asname or a.name] = (n.module, a.name)
    fungsi_claim = {nama for nama, (m, _n) in impor.items() if m == "__claim__"}
    konst = _konstanta(path)
    terurai, gagal = set(), []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and n.args):
            continue
        f = n.func
        lewat_modul = isinstance(f, ast.Attribute) and f.attr == "claim" and isinstance(f.value, ast.Name) \
            and f.value.id in alias_modul
        lewat_fungsi = isinstance(f, ast.Name) and f.id in fungsi_claim
        if not (lewat_modul or lewat_fungsi):
            continue
        a0 = n.args[0]
        nilai = None
        if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
            nilai = a0.value
        elif isinstance(a0, ast.Name) and a0.id in konst:
            nilai = konst[a0.id]
        elif isinstance(a0, ast.Name) and a0.id in impor and impor[a0.id][0] != "__claim__":
            modul, nama = impor[a0.id]
            sumber = BACKEND.joinpath(*modul.split(".")).with_suffix(".py")
            nilai = _konstanta(sumber).get(nama) if sumber.exists() else None
        if nilai:
            terurai.add(nilai)
        else:
            gagal.append((n.lineno, ast.unparse(a0)))
    return terurai, gagal


def test_every_claimed_collection_is_listed_in_saga_locks():
    from routers.saga_locks import LOCKED_COLLECTIONS
    dinamis = _klaim_dinamis()
    used, tak_terurai = set(), []
    berkas = sorted(glob.glob(str(BACKEND / "routers" / "*.py")) + glob.glob(str(BACKEND / "services" / "*.py")))
    for f in berkas:
        rel = os.path.relpath(f, BACKEND)
        terurai, gagal = _klaim_di(Path(f))
        used |= terurai
        for baris, teks in gagal:
            if (rel, teks) in dinamis:
                used |= dinamis[(rel, teks)]
            else:
                tak_terurai.append(f"{rel}:{baris} claim({teks}, …)")
    assert not tak_terurai, ("claim() dengan koleksi yang tidak bisa diurai — pakai teks/konstanta modul atau nyatakan "
                             f"di KLAIM_DINAMIS: {tak_terurai}")
    # Penjaga ini tidak boleh buta: klaim lewat konstanta modul Kas & Bank harus ikut terbaca.
    assert {"cash_out_requests", "fund_transfers", "internal_requests", "vendor_bills", "contra_bons"} <= used, used
    missing = sorted(used - set(LOCKED_COLLECTIONS))
    assert not missing, f"koleksi ber-claim() tanpa entri Kunci Saga: {missing}"


def test_penjaga_membaca_klaim_lewat_konstanta(tmp_path):
    """Swauji: `_saga.claim(COLL, …)`, alias lain, konstanta impor, dan argumen lokal yang tidak terurai."""
    (tmp_path / "contoh.py").write_text(
        "from services import atomic_claim as _saga\n"
        "from services import atomic_claim\n"
        "from services.internal_request_service import COLL as IR\n"
        "COLL = 'koleksi_konstanta'\n"
        "async def a(x):\n"
        "    await _saga.claim(COLL, 'd1', 'aksi')\n"
        "    await atomic_claim.claim(\"koleksi_teks\", 'd2', 'aksi')\n"
        "    await _saga.claim(IR, 'd3', 'aksi')\n"
        "    await _saga.claim(x, 'd4', 'aksi')\n"
        "    await lain.claim('bukan_saga', 'd5')\n", encoding="utf-8")
    terurai, gagal = _klaim_di(tmp_path / "contoh.py")
    assert terurai == {"koleksi_konstanta", "koleksi_teks", "internal_requests"}
    assert gagal == [(9, "x")]
