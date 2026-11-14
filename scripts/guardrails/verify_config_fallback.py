#!/usr/bin/env python3
"""INV-CFG-09 / INV-CFG-10 — cadangan pengaturan = bawaan registry; nilai PT diteruskan (unit KF-T8, standar §2.2).

Kenapa ada: audit 13 Nov 2026 (KF-06) menemukan 11 kunci yang nilai cadangannya di kode berbeda dari bawaan registry
(`tax.get("ppn_rate", 0)` padahal bawaan 12) — bila dokumen pengaturan tidak memuat kuncinya, mesin memakai angka yang
tidak tampil di layar. KF-T2 membetulkannya; penjaga ini mencegahnya kembali. KF-10: kunci berlapis PT dibaca tanpa
PT dokumennya, jadi nilai khusus PT tampak tersimpan tetapi tidak berakibat.

Yang dipindai: untuk tiap entri registry AKTIF, berkas Python pada `consumers`-nya (diurai `ast`; rujukan layar `.js`
dilewati). Registry dibaca dari pohon yang dipindai (`--root`), jadi pohon lama dinilai dengan registry-nya sendiri.

INV-CFG-09 (bawaan):
  (a) `<apa pun>.get("<daun>", <cadangan>)` — `<daun>` = segmen terakhir kunci;
  (b) `<pembacaan kunci> or <cadangan>` — pembacaan kunci = pemanggilan yang memuat kunci utuh, atau `.get("<daun>")`;
  (c) `<cadangan>` berupa konstanta huruf besar modul (`BATAS = 5`, `DEFAULTS["x"]`) yang nilainya literal.
  Merah bila cadangan ≠ bawaan registry; sama dengan bawaan juga merah ("pakai config_registry.default_of") kecuali
  kunci `bool`. `None` bukan cadangan (artinya "tidak ada").
INV-CFG-10 (`--entity`): kunci yang `scopes`-nya memuat `entity` dibaca `value_of("<kunci>")` (juga lewat nama impor
  lain, `value_of as _cfg_value`) tanpa argumen konteks, atau dengan konteks literal `{}` / `{"entity_id": ""}` / `None`.

Pengecualian: `scripts/guardrails/config_fallback_allow.json` — daftar `{"file", "line_text", "key", "alasan"}`
(`"mode": "entity"` untuk INV-CFG-10). Butir cocok bila berkas & kunci sama dan `line_text` termuat di baris temuan.
Butir yang tidak lagi cocok dengan temuan mana pun = merah ("pengecualian basi"), jadi daftarnya hanya bisa berkurang.

Pemakaian:
    python scripts/guardrails/verify_config_fallback.py                     # INV-CFG-09 (exit 1 bila ada temuan)
    python scripts/guardrails/verify_config_fallback.py --entity            # INV-CFG-10
    python scripts/guardrails/verify_config_fallback.py [--entity] --self-test
    python scripts/guardrails/verify_config_fallback.py --root <folder>     # pindai pohon lain (mis. salinan lama)
"""
import argparse
import ast
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, G, R, X, Guard  # noqa: E402

ALLOW_FILE = Path(__file__).resolve().parent / "config_fallback_allow.json"
MODE_BAWAAN, MODE_ENTITY = "bawaan", "entity"
_TIDAK = object()     # bukan cadangan literal


# ── registry & sumber ─────────────────────────────────────────────────────────────────────────────────────────────
def load_registry(root: Path) -> List[Dict[str, Any]]:
    backend = str(root / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    import config_registry as reg  # noqa: WPS433 — memuat seluruh katalog
    return [copy.deepcopy(e) for e in reg.all_entries()]


def consumer_files(entries: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """{berkas relatif backend: [entri aktif yang merujuknya]} — hanya berkas Python."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries:
        if e.get("status") != "active":
            continue
        for ref in e.get("consumers") or ():
            rel = str(ref).split(":", 1)[0].strip()
            if rel.endswith(".py") and e not in out.setdefault(rel, []):
                out[rel].append(e)
    return out


def read_sources(root: Path, files: Iterable[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for rel in files:
        p = root / "backend" / rel
        try:
            out[rel] = p.read_text(encoding="utf-8")
        except OSError:
            continue
    return out


_POHON: Dict[int, Optional[ast.Module]] = {}


def _urai(text: str) -> Optional[ast.Module]:
    """`ast.parse` sekali per isi berkas (uji-diri menyuntik satu berkas dan memindai ulang sisanya)."""
    k = hash(text)
    if k not in _POHON:
        try:
            _POHON[k] = ast.parse(text)
        except SyntaxError:
            _POHON[k] = None
    return _POHON[k]


# ── nilai literal & pembanding ────────────────────────────────────────────────────────────────────────────────────
def _konstanta_modul(tree: ast.Module) -> Dict[str, Any]:
    """Konstanta HURUF BESAR tingkat modul yang nilainya literal (bentuk (c))."""
    out: Dict[str, Any] = {}
    for top in tree.body:
        targets = top.targets if isinstance(top, ast.Assign) else [top.target] if isinstance(top, ast.AnnAssign) else []
        value = getattr(top, "value", None)
        if value is None:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id.isupper():
                try:
                    out[t.id] = ast.literal_eval(value)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    pass
    return out


def cadangan(node: ast.AST, konst: Dict[str, Any]) -> Tuple[Any, str]:
    """(nilai, bentuk) bila `node` cadangan literal: `a` literal · `c` konstanta modul; `_TIDAK` bila bukan."""
    try:
        return ast.literal_eval(node), "a"
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        pass
    if isinstance(node, ast.Name) and node.id.isupper() and node.id in konst:
        return konst[node.id], f"c:{node.id}"
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id.isupper() \
            and node.value.id in konst and isinstance(node.slice, ast.Constant):
        wadah = konst[node.value.id]
        if isinstance(wadah, dict) and node.slice.value in wadah:
            return wadah[node.slice.value], f"c:{node.value.id}[{node.slice.value!r}]"
    return _TIDAK, ""


def sama(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(sama(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(sama(a[k], b[k]) for k in a)
    return a == b


def _leaf(key: str) -> str:
    return key.rsplit(".", 1)[-1]


def _is_get(node: ast.AST, leaf: str) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
            and bool(node.args) and isinstance(node.args[0], ast.Constant) and node.args[0].value == leaf)


def _membaca(node: ast.AST, e: Dict[str, Any]) -> bool:
    """(b) — ruas kiri `or` ADALAH pembacaan kunci `e` (sesudah `await` dibuka): pemanggilan berargumen kunci utuh
    (`value_of("<kunci>", …)`, `val("<kunci>")`), atau `.get("<daun>"[, <x>])` — `th.get("a_max", 20.0) or 20.0`
    menilai `<x>` (bentuk a) DAN `or 20.0` (bentuk b: nilai 0 yang sah menjadi 20). Pemanggilan yang hanya MEMUAT
    pembacaan di argumennya (`d.get("x", d.get("<daun>", 0)) or 0`) bukan pembacaan kunci itu."""
    key, leaf = e["key"], _leaf(e["key"])
    while isinstance(node, ast.Await):
        node = node.value
    if not isinstance(node, ast.Call):
        return False
    if _is_get(node, leaf):
        return True
    return any(isinstance(a, ast.Constant) and a.value == key for a in list(node.args) + [k.value for k in node.keywords])


# ── INV-CFG-09 ────────────────────────────────────────────────────────────────────────────────────────────────────
def _potongan(text: str, node: ast.AST) -> str:
    """Teks kode simpul temuan (baris pertamanya) — dipakai `line_text` pengecualian supaya tidak ikut basi bila bagian
    lain barisnya disunting."""
    seg = ast.get_source_segment(text, node) or ""
    return seg.splitlines()[0].strip() if seg else ""


def _temuan(rel: str, lines: List[str], node: ast.AST, e: Dict[str, Any], nilai: Any, bentuk: str, jenis: str,
            mode: str = MODE_BAWAAN, text: str = "") -> Optional[Dict[str, Any]]:
    bawaan = e.get("default")
    if mode == MODE_BAWAAN:
        if sama(nilai, bawaan):
            if e.get("type") == "bool":
                return None
            pesan = f"cadangan {nilai!r} sama dengan bawaan — pakai `config_registry.default_of(\"{e['key']}\")`"
        else:
            pesan = f"cadangan {nilai!r} ≠ bawaan registry {bawaan!r}"
        if bentuk.startswith("c:"):
            pesan += f" (lewat konstanta {bentuk[2:]})"
    else:
        pesan = nilai
    no = getattr(node, "lineno", 0)
    return {"mode": mode, "file": f"backend/{rel}", "line": no, "line_text": lines[no - 1].strip() if no else "",
            "potongan": _potongan(text, node) if text else "", "nilai": nilai if mode == MODE_BAWAAN else None,
            "key": e["key"], "bentuk": jenis if not bentuk.startswith("c:") else f"{jenis}+c", "pesan": pesan}


def scan_bawaan(sources: Dict[str, str], per_file: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rel, text in sorted(sources.items()):
        entries = per_file.get(rel) or []
        if not entries:
            continue
        tree = _urai(text)
        if tree is None:
            continue
        lines = text.splitlines()
        konst = _konstanta_modul(tree)
        by_leaf: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            by_leaf.setdefault(_leaf(e["key"]), []).append(e)
        for n in ast.walk(tree):
            # (a) / (c): `.get("<daun>", <cadangan>)`
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" \
                    and len(n.args) >= 2 and isinstance(n.args[0], ast.Constant) and n.args[0].value in by_leaf:
                nilai, bentuk = cadangan(n.args[1], konst)
                if nilai is not _TIDAK and nilai is not None:
                    for e in by_leaf[n.args[0].value]:
                        t = _temuan(rel, lines, n, e, nilai, bentuk, "a", text=text)
                        if t:
                            out.append(t)
            # (b) / (c): `<pembacaan kunci> or <cadangan>`
            if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or) and len(n.values) >= 2:
                nilai, bentuk = cadangan(n.values[-1], konst)
                if nilai is _TIDAK or nilai is None:
                    continue
                for e in entries:
                    if any(_membaca(v, e) for v in n.values[:-1]):
                        t = _temuan(rel, lines, n, e, nilai, bentuk, "b", text=text)
                        if t:
                            out.append(t)
    return _unik(out)


# ── INV-CFG-10 ────────────────────────────────────────────────────────────────────────────────────────────────────
def _konteks_kosong(node: Optional[ast.AST]) -> Optional[str]:
    """Alasan bila argumen konteks `value_of` tidak meneruskan PT; None bila meneruskan (atau tidak bisa dinilai)."""
    if node is None:
        return "tanpa argumen konteks"
    if isinstance(node, ast.Constant) and node.value is None:
        return "konteks None"
    if isinstance(node, ast.Dict):
        if not node.keys:
            return "konteks {}"
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == "entity_id" and isinstance(v, ast.Constant) \
                    and v.value in ("", None):
                return f"konteks {{\"entity_id\": {v.value!r}}}"
    return None


def _nama_value_of(tree: ast.Module) -> set:
    """`value_of` + nama lainnya di berkas ini (`from services.config_resolver import value_of as _cfg_value`)."""
    nama = {"value_of"}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("config_resolver"):
            nama |= {a.asname for a in n.names if a.name == "value_of" and a.asname}
    return nama


def scan_entity(sources: Dict[str, str], per_file: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rel, text in sorted(sources.items()):
        keys = {e["key"]: e for e in per_file.get(rel) or [] if "entity" in (e.get("scopes") or ())}
        if not keys:
            continue
        tree = _urai(text)
        if tree is None:
            continue
        lines = text.splitlines()
        nama = _nama_value_of(tree)
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and n.args):
                continue
            fn = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
            a0 = n.args[0]
            if fn not in nama or not (isinstance(a0, ast.Constant) and a0.value in keys):
                continue
            ctx = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "ctx"), None)
            sebab = _konteks_kosong(ctx)
            if sebab:
                out.append(_temuan(rel, lines, n, keys[a0.value], f"value_of(\"{a0.value}\") {sebab} — nilai PT "
                                   f"dokumen tidak diteruskan", "", "pt", MODE_ENTITY, text=text))
    return _unik(out)


def _unik(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        k = (r["file"], r["line"], r["key"], r["bentuk"], r["pesan"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return sorted(out, key=lambda r: (r["file"], r["line"], r["key"]))


# ── pengecualian ──────────────────────────────────────────────────────────────────────────────────────────────────
def load_allow(path: Path = ALLOW_FILE) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"[FAIL] berkas pengecualian {path} tidak bisa dibaca: {exc}")
    return data.get("pengecualian", data) if isinstance(data, dict) else data


def _cocok(a: Dict[str, Any], t: Dict[str, Any]) -> bool:
    return a.get("file") == t["file"] and a.get("key") == t["key"] and str(a.get("line_text") or "") in t["line_text"]


def apply_allow(temuan: List[Dict[str, Any]], allow: List[Dict[str, Any]], mode: str):
    """(sisa temuan, pengecualian terpakai, pengecualian basi, pengecualian tanpa alasan) untuk satu mode."""
    milik = [a for a in allow if (a.get("mode") or MODE_BAWAAN) == mode]
    sisa = [t for t in temuan if not any(_cocok(a, t) for a in milik)]
    basi = [a for a in milik if not any(_cocok(a, t) for t in temuan)]
    tanpa_alasan = [a for a in milik if not str(a.get("alasan") or "").strip() or not str(a.get("line_text") or "").strip()]
    return sisa, [a for a in milik if a not in basi], basi, tanpa_alasan


# ── jalan ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def analyse(root: Path, mode: str, sources_extra: Optional[Dict[str, str]] = None,
            allow: Optional[List[Dict[str, Any]]] = None, entries: Optional[List[Dict[str, Any]]] = None):
    entries = entries if entries is not None else load_registry(root)
    per_file = consumer_files(entries)
    sources = read_sources(root, per_file)
    if sources_extra:
        sources = {**sources, **sources_extra}
    temuan = scan_bawaan(sources, per_file) if mode == MODE_BAWAAN else scan_entity(sources, per_file)
    allow = load_allow() if allow is None else allow
    sisa, pakai, basi, tanpa_alasan = apply_allow(temuan, allow, mode)
    return {"entries": entries, "per_file": per_file, "sources": sources, "temuan": temuan, "sisa": sisa,
            "pakai": pakai, "basi": basi, "tanpa_alasan": tanpa_alasan}


#: Jenis pengecualian yang sebenarnya TEMUAN (dicetak tiap jalan supaya tidak terlupa); jenis lain dicetak dengan `--rinci`.
JENIS_TEMUAN = ("berdampak", "beda_bawaan", "garis_dasar")


def report(h: Dict[str, Any], mode: str, rinci: bool = False) -> int:
    inv = "INV-CFG-09" if mode == MODE_BAWAAN else "INV-CFG-10"
    judul = ("cadangan kode = bawaan registry" if mode == MODE_BAWAAN
             else "kunci berlapis PT dibaca dengan PT dokumennya")
    g = Guard(inv, judul)
    g.bump(len(h["per_file"]))
    for t in h["sisa"]:
        g.add(f"{t['file']}:{t['line']} [{t['key']}] ({t['bentuk']}) {t['pesan']} — `{t['line_text'][:90]}`")
    for a in h["basi"]:
        g.add(f"pengecualian basi: {a.get('file')} [{a.get('key')}] `{a.get('line_text')}` — tidak cocok dengan kode "
              f"lagi; hapus dari {ALLOW_FILE.name}")
    for a in h["tanpa_alasan"]:
        g.add(f"pengecualian tanpa alasan/baris: {a.get('file')} [{a.get('key')}]")
    per_jenis: Dict[str, int] = {}
    for a in h["pakai"]:
        per_jenis[a.get("jenis") or "-"] = per_jenis.get(a.get("jenis") or "-", 0) + 1
    rincian = " · ".join(f"{k} {n}" for k, n in sorted(per_jenis.items()))
    print(f"  {len(h['per_file'])} berkas pemakai · {len(h['temuan'])} temuan mentah · temuan tersisa {len(h['sisa'])} · "
          f"pengecualian dipakai {len(h['pakai'])}" + (f" ({rincian})" if rincian else ""))
    for a in h["pakai"]:
        if rinci or (a.get("jenis") in JENIS_TEMUAN):
            print(f"  ~ dikecualikan [{a.get('jenis', '-')}]: {a['file']} [{a['key']}] `{a['line_text'][:70]}` — "
                  f"{a['alasan']}")
    return g.finish()


def self_test(mode: str) -> int:
    """Bukti-merah: suntikan pelanggaran WAJIB tertangkap, pengecualian basi WAJIB memerah, bentuk sah tidak dituduh."""
    entries = load_registry(ROOT)
    ok = True

    def cek(nama: str, benar: bool, rinci: str = "") -> None:
        nonlocal ok
        ok &= benar
        print(f"  {'✓' if benar else '✗'} {nama}{(' — ' + rinci) if rinci and not benar else ''}")

    nyata = analyse(ROOT, mode, entries=entries)
    cek(f"[1] pohon nyata: 0 temuan tersisa, 0 pengecualian basi (temuan {len(nyata['sisa'])}, basi "
        f"{len(nyata['basi'])})", not nyata["sisa"] and not nyata["basi"] and not nyata["tanpa_alasan"])

    if mode == MODE_BAWAAN:
        rel = "services/config_service.py"
        asal = nyata["sources"].get(rel, "")

        def suntik(kode: str) -> List[Dict[str, Any]]:
            h = analyse(ROOT, mode, sources_extra={rel: asal + "\n\n" + kode + "\n"}, entries=entries)
            return [t for t in h["sisa"] if t["key"] == "tax.ppn_rate" and "uji_kft8" in t["line_text"]]

        t2 = suntik("def _uji_kft8(tax):\n    return tax.get(\"ppn_rate\", 0)  # uji_kft8")
        cek("[2] suntikan `tax.get(\"ppn_rate\", 0)` terdeteksi (bentuk a, 0 ≠ 12)",
            any(t["bentuk"] == "a" and "≠ bawaan" in t["pesan"] for t in t2), str(t2))
        t3 = suntik("def _uji_kft8(tax):\n    return float(tax.get(\"ppn_rate\") or 11)  # uji_kft8")
        cek("[3] suntikan `tax.get(\"ppn_rate\") or 11` terdeteksi (bentuk b)", any(t["bentuk"] == "b" for t in t3),
            str(t3))
        t4 = suntik("PPN_UJI_KFT8 = 11.0\n\ndef _uji_kft8(tax):\n    return tax.get(\"ppn_rate\", PPN_UJI_KFT8)  # uji_kft8")
        cek("[4] suntikan konstanta `PPN_UJI_KFT8 = 11.0` sebagai cadangan terdeteksi (bentuk c)",
            any(t["bentuk"] == "a+c" for t in t4), str(t4))
        t5 = suntik("def _uji_kft8(tax):\n    return tax.get(\"ppn_rate\", 12.0)  # uji_kft8")
        cek("[5] cadangan sama dengan bawaan (bukan bool) tetap merah \"pakai config_registry.default_of\"",
            any("default_of" in t["pesan"] for t in t5), str(t5))
        rel_b = "services/config_service.py"
        h6 = analyse(ROOT, mode, sources_extra={rel_b: asal + "\n\ndef _uji_kft8(tax):\n    return tax.get("
                                                "\"dpp_nilai_lain\", True)  # uji_kft8\n"}, entries=entries)
        cek("[6] kunci bool dengan cadangan = bawaan tidak dituduh",
            not [t for t in h6["sisa"] if "uji_kft8" in t["line_text"]])
    else:
        rel = "routers/products.py"
        asal = nyata["sources"].get(rel, "")

        def suntik(kode: str) -> List[Dict[str, Any]]:
            h = analyse(ROOT, mode, sources_extra={rel: asal + "\n\n" + kode + "\n"}, entries=entries)
            return [t for t in h["sisa"] if t["key"] == "inventory.default_uom" and "uji_kft8" in t["line_text"]]

        cek("[2] suntikan `value_of(\"inventory.default_uom\")` tanpa konteks terdeteksi",
            bool(suntik("async def _uji_kft8():\n    return await value_of(\"inventory.default_uom\")  # uji_kft8")))
        cek("[3] suntikan `value_of(\"inventory.default_uom\", {\"entity_id\": \"\"})` terdeteksi",
            bool(suntik("async def _uji_kft8():\n    return await value_of(\"inventory.default_uom\", "
                        "{\"entity_id\": \"\"})  # uji_kft8")))
        cek("[4] `value_of(\"inventory.default_uom\", {\"entity_id\": doc[\"entity_id\"]})` tidak dituduh",
            not suntik("async def _uji_kft8(doc):\n    return await value_of(\"inventory.default_uom\", "
                       "{\"entity_id\": doc[\"entity_id\"]})  # uji_kft8"))

    # Pengecualian basi: butir yang tidak cocok dengan kode mana pun WAJIB memerah.
    palsu = {"file": "backend/services/config_service.py", "key": "tax.ppn_rate", "line_text": "baris_yang_tidak_ada_kft8",
             "alasan": "uji-diri", **({"mode": MODE_ENTITY} if mode == MODE_ENTITY else {})}
    h7 = analyse(ROOT, mode, allow=load_allow() + [palsu], entries=entries)
    cek(f"[{7 if mode == MODE_BAWAAN else 5}] pengecualian basi terdeteksi", any(a == palsu for a in h7["basi"]))
    print("SELF-TEST:", f"{G}PASS{X} — penjaga terbukti bisa memerah" if ok else f"{R}FAIL{X}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--entity", action="store_true", help="INV-CFG-10: kunci berlapis PT dibaca dengan PT dokumen")
    ap.add_argument("--self-test", action="store_true", help="bukti-merah penjaga")
    ap.add_argument("--root", default="", help="pindai pohon lain (bawaan: repo ini)")
    ap.add_argument("--json", action="store_true", help="cetak temuan sebagai JSON")
    ap.add_argument("--rinci", action="store_true", help="cetak SEMUA pengecualian yang dipakai")
    args = ap.parse_args()
    mode = MODE_ENTITY if args.entity else MODE_BAWAAN
    if args.self_test:
        return self_test(mode)
    root = Path(args.root).resolve() if args.root else ROOT
    h = analyse(root, mode)
    if args.json:
        print(json.dumps({k: h[k] for k in ("temuan", "sisa", "pakai", "basi")}, ensure_ascii=False, indent=1,
                         default=str))
        return 1 if (h["sisa"] or h["basi"] or h["tanpa_alasan"]) else 0
    if root != ROOT:
        print(f"  pohon dipindai: {root}")
    return report(h, mode, rinci=args.rinci)


if __name__ == "__main__":
    raise SystemExit(main())
