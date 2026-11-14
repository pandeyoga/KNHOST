#!/usr/bin/env python3
"""INV-PERM-01 — SETIAP IZIN DI KATALOG DIPERIKSA SERVER; tiap sumber daya punya tepat satu modul & label (unit PR-T5).

MASALAH YANG DICEGAH (audit konfigurasi & peran 13 Nov 2026, PR-07 / PR-UX-16)
================================================================================
Layar "Peran & Hak Akses" menawarkan setiap pasangan (sumber daya, aksi) di `backend/permissions_config.py`. Puluhan
pasangan tidak pernah diperiksa server (`reports.view`, `order.print`, `sales_pov.commercial`, …): admin mencentang
atau mencabutnya dan TIDAK ADA yang berubah — tombol izin palsu (standar `02_STANDAR.md` §3.2 & §4 L5).

ATURAN — tiap pasangan di `DEFAULT_PERMISSIONS` (+ `EXTRA_ACTIONS`) wajib salah satu:
  1. punya PEMERIKSA LITERAL di `backend/`: dua konstanta string berurutan `"<sumber daya>", "<aksi>"` sebagai argumen
     panggilan (`require_permission(request, "order", "view")`, `has_permission(u, "order", "view")`) atau tupel/daftar
     dua string `("order", "view")` (`require_any_permission(request, [("order", "view"), …])`). Berkas definisi katalog
     (`permissions_config.py`, `access_modules.py`), data migrasi (`bootstrap.py`), dan berkas uji tidak dihitung;
  2. diperiksa lewat KATALOG PERSETUJUAN (`backend/approval_kinds.py`: `permissions`/`reject_permissions` tiap jenis;
     pintunya memanggil `approval_policy_service.assert_can_decide`/`can_decide` yang memeriksa `perm_pairs`);
  3. tercantum di `DINAMIS` di bawah — nama aksi dirakit atau dikirim sebagai variabel — bersama berkas pemeriksanya
     dan penanda teks yang wajib ada di berkas itu. Entri yang ternyata SUDAH punya pemeriksa literal = merah (daftar
     basi); `"*"` = semua aksi sumber daya itu (templat laporan Tanya KN, satu aksi per templat);
  4. tercantum di `MENUNGGU_KPT4` — kosong sejak unit KP-T4 selesai (5 pasangan setuju/tolak PO, tagihan pemasok, dan
     voucher biaya masuk kini lewat aturan 2). Daftar ini wajib tetap kosong.
Tambahan: tiap sumber daya di `DEFAULT_PERMISSIONS` masuk TEPAT SATU modul `MODULE_CATALOG` dan punya label
(`RESOURCE_LABEL`); tiap sumber daya modul ada di `DEFAULT_PERMISSIONS`; tiap aksi punya label (`ACTION_LABEL[aksi]` atau
`ACTION_LABEL["<sumber daya>.<aksi>"]`); tiap pasangan `SENSITIVE_ACTIONS` ada di katalog.

Pakai:
    python scripts/guardrails/verify_permission_checked.py
    python scripts/guardrails/verify_permission_checked.py --self-test   # bukti-merah: sisipan wajib tertangkap
    python scripts/guardrails/verify_permission_checked.py --list        # cetak pasangan per golongan pemeriksa
"""
from __future__ import annotations

import ast
import copy
import os
import re
import sys
from typing import Dict, Iterable, List, Set, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard, G, R, X  # noqa: E402

sys.path.insert(0, str(BACKEND))

Pair = Tuple[str, str]

#: Golongan 3 — diperiksa dinamis: pasangan → (berkas pemeriksa relatif `backend/`, penanda teks di berkas itu).
DINAMIS: Dict[Pair, Tuple[str, str]] = {
    **{("field_visibility", a): ("services/field_visibility.py", "def hidden_for") for a in ("grade", "lot", "origin")},
    **{("goods_receipt", a): ("routers/goods_receipts.py", "async def _act(") for a in ("create", "count", "close")},
    **{("od_fulfillment", a): ("services/special_order_fulfillment.py", '"od_fulfillment", action')
       for a in ("view", "override_default", "cancel")},
    **{("rnd", f"{a}_{t}"): ("routers/rnd.py", "async def _require_typed(")
       for a in ("assess", "decide") for t in ("labdip", "handfeel", "proofing")},
    ("sales_return", "split_cutloss"): ("routers/sales_return_exceptions.py", '"split_cutloss")'),
    ("finance_amendment", "approve"): ("routers/amendments.py", '"approval_permission"'),
    ("order", "approve_price_edit"): ("services/amendment_service.py", 'PRICE_EDIT_PERMISSION = "order.approve_price_edit"'),
    ("period", "backdate"): ("routers/gl.py", '"backdate" in matrix'),
    ("ai_template", "*"): ("routers/ai_analytics.py", 'has_permission(user, "ai_template", tpl["id"])'),
}
#: Golongan 4 — menunggu unit KP-T4. KP-T4 selesai: kosong, dan harus tetap kosong.
MENUNGGU_KPT4: Dict[Pair, str] = {}

TIDAK_DIHITUNG = {"permissions_config.py", "access_modules.py", "bootstrap.py"}
_UJI = re.compile(r"^(test_|backend_test)|_test\.py$|_smoke|_fase")


def backend_sources() -> Iterable[Tuple[str, str]]:
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = sorted(d for d in dirs if d not in ("tests", "tests_mem", "__pycache__", "data", "tools", "uploads"))
        for f in sorted(files):
            if f.endswith(".py") and f not in TIDAK_DIHITUNG and not _UJI.search(f):
                p = os.path.join(root, f)
                with open(p, encoding="utf-8") as fh:
                    yield os.path.relpath(p, BACKEND), fh.read()


def _str(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def literal_pairs(sources: Iterable[Tuple[str, str]]) -> Dict[Pair, str]:
    """Pasangan → berkas pertama yang memuat pemeriksa literalnya."""
    out: Dict[Pair, str] = {}
    for rel, txt in sources:
        try:
            tree = ast.parse(txt)
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            found: List[Pair] = []
            if isinstance(n, ast.Call):
                vals = [_str(a) for a in n.args]
                found += [(vals[i], vals[i + 1]) for i in range(len(vals) - 1) if vals[i] and vals[i + 1]]
            elif isinstance(n, (ast.Tuple, ast.List)) and len(n.elts) == 2:
                a, b = _str(n.elts[0]), _str(n.elts[1])
                if a and b:
                    found.append((a, b))
            for p in found:
                out.setdefault(p, rel)
    return out


def approval_pairs() -> Tuple[Set[Pair], List[str]]:
    """Golongan 2 — pasangan izin katalog persetujuan + masalah bila pintunya tidak memeriksa `perm_pairs`."""
    problems: List[str] = []
    try:
        import approval_kinds as ak
    except Exception as exc:  # noqa: BLE001
        return set(), [f"approval_kinds tidak bisa dibaca: {exc}"]
    svc = (BACKEND / "services" / "approval_policy_service.py").read_text(encoding="utf-8")
    if "perm_pairs(" not in svc or "has_permission(" not in svc:
        problems.append("services/approval_policy_service.py tidak lagi memeriksa izin `perm_pairs` (has_permission)")
    pairs: Set[Pair] = set()
    for k in ak.APPROVAL_KINDS.values():
        for p in [*k["permissions"], *k["reject_permissions"]]:
            res, _, act = p.partition(".")
            pairs.add((res, act))
    return pairs, problems


def catalog_pairs(perms: Dict[str, Dict[str, List[str]]], extra: Dict[str, List[str]]) -> Set[Pair]:
    out = {(r, a) for mods in perms.values() for r, acts in mods.items() for a in acts}
    return out | {(r, a) for r, acts in extra.items() for a in acts}


def scan(perms, extra, catalog, res_label, act_label, sensitive, literal, appr, appr_problems,
         dinamis=None, menunggu=None, file_text=None) -> Tuple[List[str], int]:
    dinamis = DINAMIS if dinamis is None else dinamis
    menunggu = MENUNGGU_KPT4 if menunggu is None else menunggu
    file_text = file_text or (lambda rel: (BACKEND / rel).read_text(encoding="utf-8") if (BACKEND / rel).exists() else None)
    problems: List[str] = list(appr_problems)
    pairs = catalog_pairs(perms, extra)
    checks = 0
    for r, a in sorted(pairs):
        checks += 1
        if (r, a) in literal or (r, a) in appr or (r, a) in dinamis or (r, "*") in dinamis or (r, a) in menunggu:
            continue
        problems.append(f"{r}.{a}: tidak punya pemeriksa di backend/ (literal, katalog persetujuan, atau DINAMIS) — "
                        "pasang pemeriksanya atau hapus pasangannya dari permissions_config.py")
    resources = {r for r, _ in pairs}
    for (r, a), (rel, mark) in sorted(dinamis.items()):
        checks += 1
        txt = file_text(rel)
        if a == "*":
            if r not in resources:
                problems.append(f"DINAMIS {r}.*: sumber daya tidak ada di katalog (daftar basi)")
        elif (r, a) not in pairs:
            problems.append(f"DINAMIS {r}.{a}: pasangan tidak ada di katalog (daftar basi)")
        elif (r, a) in literal:
            problems.append(f"DINAMIS {r}.{a}: sudah punya pemeriksa literal ({literal[(r, a)]}) — hapus dari DINAMIS")
        if txt is None:
            problems.append(f"DINAMIS {r}.{a}: berkas pemeriksa {rel} tidak ada")
        elif mark not in txt:
            problems.append(f"DINAMIS {r}.{a}: penanda {mark!r} tidak ditemukan di {rel}")
    for (r, a) in sorted(menunggu):
        problems.append(f"MENUNGGU_KPT4 {r}.{a}: KP-T4 sudah selesai — daftar ini wajib kosong")
    owner: Dict[str, List[str]] = {}
    for m in catalog:
        for r in m["resources"]:
            owner.setdefault(r, []).append(m["id"])
            if r not in resources:
                problems.append(f"modul {m['id']}: sumber daya {r} tidak ada di DEFAULT_PERMISSIONS")
    for r in sorted(resources):
        checks += 1
        if len(owner.get(r, [])) != 1:
            problems.append(f"sumber daya {r}: harus masuk tepat satu modul (sekarang: {owner.get(r, [])})")
        if not res_label.get(r):
            problems.append(f"sumber daya {r}: tidak punya label (RESOURCE_LABEL)")
    for r, a in sorted(pairs):
        if not (act_label.get(a) or act_label.get(f"{r}.{a}")):
            problems.append(f"aksi {r}.{a}: tidak punya label (ACTION_LABEL)")
    for (r, a) in sorted(sensitive):
        checks += 1
        if (r, a) not in pairs:
            problems.append(f"SENSITIVE_ACTIONS {r}.{a}: pasangan tidak ada di katalog")
    return problems, checks


def _live():
    import access_modules as am
    from permissions_config import DEFAULT_PERMISSIONS, EXTRA_ACTIONS
    appr, appr_problems = approval_pairs()
    return dict(perms=DEFAULT_PERMISSIONS, extra=EXTRA_ACTIONS, catalog=am.MODULE_CATALOG,
                res_label=am.RESOURCE_LABEL, act_label=am.ACTION_LABEL, sensitive=getattr(am, "SENSITIVE_ACTIONS", {}),
                literal=literal_pairs(backend_sources()), appr=appr, appr_problems=appr_problems)


def main() -> int:
    live = _live()
    if "--list" in sys.argv:
        pairs = catalog_pairs(live["perms"], live["extra"])
        for r, a in sorted(pairs):
            how = ("literal " + live["literal"][(r, a)] if (r, a) in live["literal"] else
                   "katalog persetujuan" if (r, a) in live["appr"] else
                   "dinamis " + (DINAMIS.get((r, a)) or DINAMIS.get((r, "*")) or ("?",))[0]
                   if ((r, a) in DINAMIS or (r, "*") in DINAMIS) else "TANPA PEMERIKSA")
            print(f"{r}.{a}\t{how}")
    problems, checks = scan(**live)
    g = Guard("INV-PERM-01", "setiap izin di katalog diperiksa server; sumber daya bermodul & berlabel")
    g.bump(checks)
    for p in problems:
        g.add(p)
    return g.finish()


def self_test() -> int:
    """Bukti-merah: katalog nyata lulus; tiap sisipan pelanggaran wajib tertangkap (dan hanya itu)."""
    live = _live()
    gagal = 0

    def cek(nama: str, ok: bool, rinci: str = "") -> None:
        nonlocal gagal
        print(f"  {(G + 'OK  ') if ok else (R + 'GAGAL')}{X} {nama}{(' — ' + rinci) if rinci and not ok else ''}")
        gagal += 0 if ok else 1

    def jalankan(**ubah):
        args = {**live, **ubah}
        return scan(**args)[0]

    print("verify_permission_checked --self-test")
    base = jalankan()
    cek("katalog nyata lulus", not base, "; ".join(base[:3]))

    perms = copy.deepcopy(live["perms"])
    perms["admin"]["order"] = list(perms["admin"]["order"]) + ["zz_uji_tanpa_pemeriksa"]
    act = {**live["act_label"], "zz_uji_tanpa_pemeriksa": "Uji"}
    hasil = jalankan(perms=perms, act_label=act)
    cek("pasangan tanpa pemeriksa tertangkap", any(p.startswith("order.zz_uji_tanpa_pemeriksa:") for p in hasil),
        str(hasil[:2]))
    cek("…dan hanya itu", len(hasil) == 1, str(hasil))

    cek("pemeriksa literal dikenali (kode sisipan)",
        ("order", "zz_uji_tanpa_pemeriksa") in literal_pairs(
            [("x.py", 'await require_permission(request, "order", "zz_uji_tanpa_pemeriksa")')]))
    cek("tupel require_any_permission dikenali",
        ("qc", "zz") in literal_pairs([("x.py", 'X = [("inspection", "view"), ("qc", "zz")]')]))
    cek("komentar tidak dihitung", not literal_pairs([("x.py", '# require_permission(request, "a", "b")')]))

    perms2 = copy.deepcopy(live["perms"])
    perms2["admin"]["zz_sumber_uji"] = ["view"]
    lit = {**live["literal"], ("zz_sumber_uji", "view"): "x.py"}
    hasil = jalankan(perms=perms2, literal=lit)
    cek("sumber daya tanpa modul & label tertangkap",
        any("zz_sumber_uji: harus masuk tepat satu modul" in p for p in hasil)
        and any("zz_sumber_uji: tidak punya label" in p for p in hasil), str(hasil))

    act2 = {k: v for k, v in live["act_label"].items() if k not in ("approve_count",)}
    hasil = jalankan(act_label=act2)
    cek("aksi tanpa label tertangkap", any("approve_count: tidak punya label" in p for p in hasil), str(hasil[:2]))

    din = {**DINAMIS, ("order", "view"): ("routers/sales_orders.py", "def ")}
    hasil = jalankan(dinamis=din)
    cek("entri DINAMIS basi (sudah literal) tertangkap", any("DINAMIS order.view: sudah punya" in p for p in hasil),
        str(hasil[:2]))
    din = {**DINAMIS, ("rnd", "assess_labdip"): ("routers/rnd.py", "penanda_yang_tidak_ada_zz")}
    hasil = jalankan(dinamis=din)
    cek("penanda berkas pemeriksa hilang tertangkap", any("penanda" in p for p in hasil), str(hasil[:2]))

    hasil = jalankan(menunggu={("purchase_order", "reject"): "KP-T4"})
    cek("MENUNGGU_KPT4 tidak kosong tertangkap", any(p.startswith("MENUNGGU_KPT4") for p in hasil), str(hasil))

    sens = {**live["sensitive"], ("order", "zz_berisiko"): "uji"}
    hasil = jalankan(sensitive=sens)
    cek("SENSITIVE_ACTIONS di luar katalog tertangkap", any("SENSITIVE_ACTIONS order.zz_berisiko" in p for p in hasil))

    print(f"{G if not gagal else R}{'LULUS' if not gagal else 'GAGAL'}{X} — {gagal} kasus gagal")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
