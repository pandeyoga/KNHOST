#!/usr/bin/env python3
"""INV-MONEY-IDEM-01 — form uang mengirim lewat satu pintu ber-`Idempotency-Key` (PK-12: UX-01, UX-02, GL-08, FY-18).

Masalah yang dicegah: klik ganda atau kirim ulang sesudah koneksi putus pada form uang (kas, jurnal, tagihan pemasok,
kontrabon, antar-PT, aset, kas kecil, rencana bayar, denda, selisih bayar, kasus, pajak, rekonsiliasi bank) membuat dua
dokumen. Server memutar ulang jawaban pertama bila klien mengirim header `Idempotency-Key` ke jalur berawalan terdaftar
(`backend/idempotency.py`, `IDEMPOTENT_PREFIXES`). Layar mengirim lewat `frontend/src/utils/moneyRequest.js`
(`moneyPost`/`moneyPut`/`moneyPatch`/`moneyDelete`) dengan kunci dari `useIntentKey`.

Penjaga ini MERAH bila:
  1. salah satu awalan uang di `MONEY_PREFIXES` tidak ada di `IDEMPOTENT_PREFIXES` server;
  2. ada `axios.post|put|patch|delete(` langsung (di luar `moneyRequest.js` dan `__tests__`) yang URL-nya memuat jalur
     uang — sebut berkas dan baris.

Batas: URL yang dibangun dari variabel lain (bukan teks/template di argumen pertama) tidak terbaca.

Pakai:  python3 scripts/guardrails/verify_money_idempotency.py
        python3 scripts/guardrails/verify_money_idempotency.py --self-test
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend" / "src"
IDEM = ROOT / "backend" / "idempotency.py"
PINTU = "utils/moneyRequest.js"

# Tabel "Server" PK-12 — jalur uang yang wajib berkunci.
MONEY_PREFIXES = (
    "/api/gl/", "/api/cash-transactions", "/api/vendor-bills", "/api/contra-bons", "/api/interco/",
    "/api/fixed-assets", "/api/cash-advances", "/api/cash-advance-settlements", "/api/payment-plans",
    "/api/penalties", "/api/payment-variances", "/api/finance-cases", "/api/tax/pph-records",
    "/api/input-tax-invoices", "/api/tax-invoices", "/api/bank-reconciliation/lines/",
    "/api/bank-accounts", "/api/bank-account-changes",   # PM-T1 — rekening kas/bank & putusan perubahannya
    "/api/payment-reports",   # LB-T3 — lapor bayar CBD & DP: lampiran dan putusan terima/tolak
    "/api/cash-out-requests",   # Kas & Bank 2 — putusan setujui/tolak/batal pengajuan kas keluar manual
)
# Daftar-izin (berkas relatif `frontend/src`, potongan URL) → alasan ≥ 20 huruf. Awal: kosong.
ALLOW: dict[tuple[str, str], str] = {}

CALL = re.compile(r"\baxios\.(post|put|patch|delete)\s*\(")


def server_prefixes(path: Path = IDEM) -> tuple:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "IDEMPOTENT_PREFIXES" for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    return ()


def _first_arg(src: str, start: int) -> str:
    """Teks argumen pertama panggilan mulai `start` (sesudah '('), berhenti di koma kedalaman 0."""
    depth, i, out = 0, start, []
    in_tpl = False
    while i < len(src):
        ch = src[i]
        if ch == "`":
            in_tpl = not in_tpl
        elif not in_tpl:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif ch == "," and depth == 0:
                break
        out.append(ch)
        i += 1
    return "".join(out)


def _segments() -> list:
    """Potongan URL di sisi layar: '/api/gl/' → '/gl/' (layar menulis `${API}/gl/...`)."""
    return [p[len("/api"):] for p in MONEY_PREFIXES]


def scan(front: Path = FRONT) -> list:
    hits = []
    segs = _segments()
    for f in sorted(list(front.rglob("*.js")) + list(front.rglob("*.jsx"))):
        rel = f.relative_to(front).as_posix()
        if "__tests__" in rel or rel == PINTU or ".test." in rel:
            continue
        src = f.read_text(encoding="utf-8", errors="ignore")
        for m in CALL.finditer(src):
            arg = _first_arg(src, m.end())
            seg = next((s for s in segs if s in arg), None)
            if not seg or (rel, seg) in ALLOW:
                continue
            line = src.count("\n", 0, m.start()) + 1
            hits.append((rel, line, m.group(1), arg.strip()[:80]))
    return hits


def run(front: Path = FRONT, idem: Path = IDEM) -> int:
    g = Guard("INV-MONEY-IDEM-01", "form uang lewat moneyRequest.js ber-Idempotency-Key")
    srv = server_prefixes(idem)
    for p in MONEY_PREFIXES:
        g.bump()
        if p not in srv:
            g.add(f"awalan uang {p} tidak ada di IDEMPOTENT_PREFIXES ({idem.name})")
    for k, why in ALLOW.items():
        if len(why.strip()) < 20:
            g.add(f"alasan daftar-izin {k} kurang dari 20 huruf")
    hits = scan(front)
    g.bump(max(1, len(hits)))
    for rel, line, verb, arg in hits:
        g.add(f"frontend/src/{rel}:{line} — axios.{verb}({arg}) langsung ke jalur uang; pakai "
              f"money{verb.capitalize()} dari {PINTU} dengan kunci useIntentKey")
    return g.finish()


def self_test() -> int:
    """Bukti-merah: satu `axios.post` langsung ke `/cash-transactions` harus memerah; lewat pintu harus lolos."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        front = Path(d) / "src"
        (front / "utils").mkdir(parents=True)
        (front / "utils" / "moneyRequest.js").write_text("export const moneyPost = (u,b,k) => axios.post(u,b);\n")
        (front / "Kas.jsx").write_text("const a = 1;\nawait axios.post(`${API}/cash-transactions`, body);\n")
        (front / "Aman.jsx").write_text("await moneyPost(`${API}/cash-transactions`, body, k);\n"
                                        "await axios.post(`${API}/sales-leads`, body);\n")
        hits = scan(front)
        if not (len(hits) == 1 and hits[0][0] == "Kas.jsx" and hits[0][1] == 2):
            print(f"[SELF-TEST GAGAL] harus tepat satu temuan Kas.jsx:2, dapat {hits}")
            ok = False
        idem = Path(d) / "idempotency.py"
        idem.write_text('IDEMPOTENT_PREFIXES = ("/api/gl/",)\n')
        if run(front, idem) == 0:
            print("[SELF-TEST GAGAL] awalan server yang kurang tidak memerah")
            ok = False
    print("[SELF-TEST] " + ("lulus — penjaga memerah pada pelanggaran dan lolos pada pintu" if ok else "GAGAL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
