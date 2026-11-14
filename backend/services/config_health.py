"""FASE G-0 — KESEHATAN KONFIGURASI: apakah setiap setting benar-benar tersambung?

Setiap entri registry WAJIB mencantumkan `consumers` (berkas kode yang membacanya).
Modul ini memverifikasi klaim tersebut secara nyata:

  OK       berkas consumer ADA dan benar-benar menyebut kunci itu
  STALE    berkas ADA tetapi TIDAK menyebut kunci  → klaim registry basi
  MISSING  berkas TIDAK ADA (atau fungsi yang dirujuk tidak ada) → referensi salah
  NOT_USED sengaja dinyatakan tidak dipakai (dengan alasan)

KF-T3 (KF-11) — "menyebut" diperketat. Dulu cukup NAMA DAUN di berkas mana pun yang didaftarkan (`'admin'` meloloskan
`role_home.admin` lewat `permissions_config.py`). Kini (`_mentions(ref, key)`):
  (a) rujukan `berkas.py:fungsi` → fungsi itu WAJIB ada (tidak ada → MISSING) dan hanya badan fungsi itu yang dipindai
      (`ast`), ditambah konstanta modul berisi teks saja (daftar/peta kunci, mis. `CFG_KEYS`) yang DIRUJUK badan itu —
      pola "satu pemuat membaca daftar kunci modul";
  (b) cocok = kunci utuh muncul, ATAU segmen induk dan daun sama-sama muncul sebagai kata utuh; daun saja tidak cukup.
      Keluarga `kontrol.<aksi>.<x>` (KF-T6) tetap cukup menyebut literal aksinya.

Dipakai oleh layar "Kesehatan Konfigurasi" (admin) dan invarian `INV-CFG-01`.
Gate menyeluruh (memindai SELURUH repo) tetap di `scripts/audit_config_wiring.py`.
"""
import ast
import os
import re
from typing import Any, Dict, List, Optional

import config_registry as registry

BACKEND = "/app/backend"
FRONTEND = "/app/frontend/src"
_CACHE: Dict[str, str] = {}


def _read(path: str) -> str:
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        text = ""
    _CACHE[path] = text
    return text


def _resolve_path(ref: str) -> str:
    """'services/x.py:fn' → /app/backend/services/x.py · 'App.js' → /app/frontend/src/App.js"""
    file_part = ref.split(":", 1)[0].strip()
    root = BACKEND if file_part.endswith(".py") else FRONTEND
    return os.path.join(root, file_part)


def _kata(word: str, text: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(word), text) is not None


def _cocok(text: str, key: str) -> bool:
    """KF-T3 (b) — kunci utuh, ATAU segmen induk + daun sebagai kata utuh. Daun saja tidak cukup."""
    if not text:
        return False
    if key in text:
        return True
    parts = key.split(".")
    if len(parts) < 2:
        return False
    if parts[0] == "kontrol" and len(parts) == 3 and re.search(r"[\"']%s[\"']" % re.escape(parts[1]), text):
        # KF-T6 — keluarga `kontrol.<aksi>.<x>`: kuncinya dibentuk pembantu `dual_control` dari NAMA AKSI, jadi titik
        # pasang cukup menyebut literal aksinya (`tolak_bila_pelaku_sama("setujui_po", …)`).
        return True
    return _kata(parts[-2], text) and _kata(parts[-1], text)


_TREES: Dict[str, Any] = {}


def _hanya_teks(node: Any) -> bool:
    """Konstanta modul berisi teks saja (`"a.b"`, tuple/list/set/dict teks) — daftar/peta kunci, bukan dokumen bawaan."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(_hanya_teks(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.keys) and all(k is not None and _hanya_teks(k) for k in node.keys) \
            and all(_hanya_teks(v) for v in node.values)
    return False


def _badan_fungsi(path: str, text: str, name: str) -> Optional[str]:
    """KF-T3 (a) — sumber fungsi `name` (+ konstanta teks modul yang dirujuknya); None bila fungsi tidak ada."""
    if path not in _TREES:
        try:
            _TREES[path] = ast.parse(text)
        except SyntaxError:
            _TREES[path] = None
    tree = _TREES[path]
    if tree is None:
        return None
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
    if fn is None:
        return None
    parts = [ast.get_source_segment(text, fn) or ""]
    dipakai = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    for top in tree.body:
        targets = top.targets if isinstance(top, ast.Assign) else [top.target] if isinstance(top, ast.AnnAssign) else []
        value = getattr(top, "value", None)
        if value is not None and any(isinstance(t, ast.Name) and t.id in dipakai for t in targets) \
                and _hanya_teks(value):
            parts.append(ast.get_source_segment(text, top) or "")
    return "\n".join(parts)


def _mentions(ref: str, key: str) -> Optional[bool]:
    """KF-T3 — apakah rujukan `ref` (`berkas.py` atau `berkas.py:fungsi`) benar-benar menyebut `key`?

    None = berkas atau fungsi yang dirujuk tidak ada (MISSING)."""
    path = _resolve_path(ref)
    if not os.path.exists(path):
        return None
    text = _read(path)
    fn = ref.split(":", 1)[1].strip() if ":" in ref else ""
    if fn and path.endswith(".py"):
        body = _badan_fungsi(path, text, fn)
        if body is None:
            return None
        text = body
    return _cocok(text, key)


def check_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    key = entry["key"]
    ok, stale, missing, unverified = [], [], [], []
    for ref in entry["consumers"]:
        path = _resolve_path(ref)
        # Server produksi (container backend) tidak membawa kode frontend → tidak bisa dicek, bukan "salah".
        if path.startswith(FRONTEND) and not os.path.isdir(FRONTEND):
            unverified.append(ref)
            continue
        hasil = _mentions(ref, key)
        if hasil is None:
            missing.append(ref)
            continue
        (ok if hasil else stale).append(ref)
    if entry["status"] == "not_used":
        status = "NOT_USED"
    elif missing:
        status = "MISSING"
    elif not ok and not unverified:
        status = "STALE"
    else:
        status = "OK"
    return {
        "key": key, "label": entry["label"], "group": entry["group"],
        "registry_status": entry["status"], "not_used_reason": entry["not_used_reason"],
        "wiring_status": status, "risk": entry["risk"],
        "consumers_ok": ok, "consumers_stale": stale, "consumers_missing": missing,
        "consumers_unverified": unverified,
        "consumer_count": len(entry["consumers"]),
    }


def report() -> Dict[str, Any]:
    _CACHE.clear()
    _TREES.clear()
    rows = [check_entry(e) for e in registry.all_entries()]
    summary: Dict[str, int] = {}
    for r in rows:
        summary[r["wiring_status"]] = summary.get(r["wiring_status"], 0) + 1
    per_group: Dict[str, Dict[str, int]] = {}
    for r in rows:
        g = per_group.setdefault(r["group"], {})
        g[r["wiring_status"]] = g.get(r["wiring_status"], 0) + 1
    broken = [r for r in rows if r["wiring_status"] in {"MISSING", "STALE"}]
    return {
        "total": len(rows),
        "summary": summary,
        "per_group": per_group,
        "healthy": not broken,
        "broken": broken,
        "rows": rows,
        "legend": {
            "OK": "Tersambung — kode pembacanya ada dan benar-benar memakai setting ini.",
            "STALE": "Referensi kode basi — berkas ada tetapi tidak lagi menyebut setting ini.",
            "MISSING": "Referensi kode salah — berkas atau fungsinya tidak ditemukan.",
            "NOT_USED": "Sengaja tidak dipakai — lihat alasannya.",
        },
    }


def coverage() -> Dict[str, Any]:
    """Cakupan registry terhadap kunci yang benar-benar hidup di `system_settings`
    (dipakai POC/gate: memastikan tidak ada setting liar di luar registry)."""
    from config_registry import covers
    return {"registered": len(registry.all_entries()),
            "resolver": bool(covers("tax.ppn_rate"))}


def uncovered_leaves(leaves: List[str]) -> List[str]:
    """Kunci daun (dari audit) yang belum tercakup registry."""
    return [lk for lk in leaves if registry.covers(lk) is None]
