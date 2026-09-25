"""GRN Fase 4 — aturan murni pembacaan surat jalan (§4.8): angka, qty declared, nomor PO, pencocokan baris, total.

Semua fungsi di sini MURNI (tanpa DB/IO) supaya bisa diuji unit dengan JSON `read` dari Lampiran C.
"""
import itertools
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence

UNIT_OF = {"m": "meter", "yd": "yard", "kg": "kg", "roll": "roll", "pcs": "pcs", "bal": "bal"}
COUNT_UNITS = {"roll", "pcs", "bal"}


def parse_doc_number(text: Optional[str], locale_hint: str = "unknown") -> Dict[str, Any]:
    """"1.250" → ambigu [1250, 1.25]; "2,186.00" → 2186; "19,00" → 19. locale_hint: id (koma desimal) | en | unknown."""
    s = re.sub(r"[^\d.,\-]", "", str(text or ""))
    if not re.search(r"\d", s):
        return {"value": None, "candidates": [], "ambiguous": False}

    def f(x: str) -> float:
        return float(x) if x not in ("", "-") else 0.0
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        th = "," if dec == "." else "."
        v = f(s.replace(th, "").replace(dec, "."))
        return {"value": v, "candidates": [v], "ambiguous": False}
    sep = "." if "." in s else "," if "," in s else ""
    if not sep:
        v = f(s)
        return {"value": v, "candidates": [v], "ambiguous": False}
    if s.count(sep) > 1:
        v = f(s.replace(sep, ""))
        return {"value": v, "candidates": [v], "ambiguous": False}
    head, tail = s.split(sep)
    if len(tail) == 3 and head.strip("-"):
        thousands, decimal = f(head + tail), f(f"{head}.{tail}")
        if locale_hint in ("id", "en"):
            dec_sep = "," if locale_hint == "id" else "."
            v = decimal if sep == dec_sep else thousands
            return {"value": v, "candidates": [thousands, decimal], "ambiguous": False}
        return {"value": None, "candidates": [thousands, decimal], "ambiguous": True}
    v = f(f"{head}.{tail}")
    return {"value": v, "candidates": [v], "ambiguous": False}


def resolve_by_total(candidate_lists: Sequence[Sequence[float]], total: Optional[float],
                     tol: float = 0.01) -> Optional[List[float]]:
    """Pilih satu kandidat per baris yang jumlahnya = total tercetak. Tepat satu kombinasi → itu; selain itu None."""
    if total is None or not candidate_lists or any(not c for c in candidate_lists):
        return None
    combos = 1
    for c in candidate_lists:
        combos *= len(set(c))
    if combos > 4096:
        return None
    hits = {tuple(p) for p in itertools.product(*[sorted(set(c)) for c in candidate_lists]) if abs(sum(p) - total) <= tol}
    return list(next(iter(hits))) if len(hits) == 1 else None


def qty_status(q: Dict[str, Any], parsed: Dict[str, Any]) -> str:
    if q.get("role") == "unclear":
        return "unclear"
    if parsed["ambiguous"]:
        return "ambiguous"
    if parsed["value"] is None:
        return "empty"
    if q.get("qty") is not None and abs(float(q["qty"]) - parsed["value"]) > 0.005:
        return "mismatch"
    return "ok"


def pick_declared(quantities: Iterable[Dict[str, Any]], target_unit: str = "") -> Dict[str, Any]:
    """Qty declared dari `read.quantities[]` (tiap item sudah punya `value` & `status`). Greige & unclear tak pernah dipilih."""
    out: Dict[str, Any] = {"qty": None, "unit": "", "rolls": None, "weight_kg": None, "weight_basis": None,
                           "qty_parse": "ok", "alt_lengths": []}
    usable = [q for q in quantities if q.get("role") not in ("greige_length", "greige_weight", "unclear")]
    if any(q.get("status") in ("ambiguous", "mismatch") for q in usable):
        out["qty_parse"] = next(q["status"] for q in usable if q.get("status") in ("ambiguous", "mismatch"))
    ok = [q for q in usable if q.get("status") == "ok" and q.get("value") is not None]
    for q in ok:
        unit = UNIT_OF.get(q.get("unit") or "", q.get("unit") or "")
        if q["role"] == "delivered_count" and (unit in COUNT_UNITS or not unit):
            out["rolls"] = int(round(q["value"]))
        elif q["role"] == "delivered_weight" and out["weight_kg"] is None:
            out["weight_kg"], out["weight_basis"] = q["value"], q.get("weight_basis") or "unknown"
    lengths = [q for q in ok if q["role"] == "delivered_length"]
    weights = [q for q in ok if q["role"] == "delivered_weight"]
    same = [q for q in lengths + weights if UNIT_OF.get(q.get("unit") or "", "") == target_unit]
    pick = (same or lengths or [])[:1]
    if pick:
        out["qty"], out["unit"] = pick[0]["value"], UNIT_OF.get(pick[0].get("unit") or "", pick[0].get("unit") or "")
        out["alt_lengths"] = [{"qty": q["value"], "unit": UNIT_OF.get(q.get("unit") or "", "")} for q in lengths + weights
                              if q is not pick[0]]
    elif not target_unit and weights:
        out["qty"], out["unit"] = weights[0]["value"], "kg"
    return out


DEFAULT_PO_PATTERNS = [r"(?P<core>\d{3,5})/(CST|SCB)/\d{4}", r"[A-Z]+/PO-(?P<core>\d+)"]


def po_cores(texts: Iterable[Optional[str]], patterns: Sequence[str]) -> List[str]:
    """Inti nomor PO klien dari teks bebas (grup bernama `core`); nomor milik supplier tidak cocok pola → diabaikan."""
    out: List[str] = []
    for t in texts:
        for p in patterns:
            for m in re.finditer(p, str(t or ""), flags=re.I):
                core = (m.groupdict().get("core") or "").lstrip("0")
                if core and core not in out:
                    out.append(core)
    return out


def match_po(texts: Sequence[Optional[str]], open_pos: Sequence[Dict[str, Any]], patterns: Sequence[str]) -> Dict[str, Any]:
    """po_number persis → legacy_number persis → core unik → none. Tidak pernah memilih bila kandidat > 1."""
    norm = lambda s: re.sub(r"\s+", "", str(s or "")).upper()  # noqa: E731
    raw = [norm(t) for t in texts if t]
    for field, method in (("po_number", "exact"), ("legacy_number", "legacy")):
        hits = [p for p in open_pos if p.get(field) and any(norm(p[field]) in r for r in raw)]
        if len(hits) == 1:
            return {"status": method, "po_id": hits[0]["id"], "candidates": [hits[0]["id"]]}
        if len(hits) > 1:
            return {"status": "ambiguous", "po_id": "", "candidates": [p["id"] for p in hits]}
    cores = po_cores(texts, patterns)
    hits = []
    for p in open_pos:
        pc = po_cores([p.get("po_number"), p.get("legacy_number")], patterns)
        if set(pc) & set(cores):
            hits.append(p)
    if len(hits) == 1:
        return {"status": "core", "po_id": hits[0]["id"], "candidates": [hits[0]["id"]]}
    return {"status": "ambiguous" if hits else "none", "po_id": "", "candidates": [p["id"] for p in hits]}


def similarity(a: Optional[str], b: Optional[str]) -> float:
    na = " ".join(re.sub(r"[^a-z0-9 ]", " ", str(a or "").lower()).split())
    nb = " ".join(re.sub(r"[^a-z0-9 ]", " ", str(b or "").lower()).split())
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return max(0.9, SequenceMatcher(None, na, nb).ratio())
    return SequenceMatcher(None, na, nb).ratio()


def match_line(read: Dict[str, Any], tasks: Sequence[Dict[str, Any]], supplier_items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Baris → tugas: item_code (supplier_items) → kemiripan deskripsi ≥ 0,85 & unggul ≥ 0,10 → satu-satunya baris PO."""
    code = str(read.get("item_code") or "").strip().upper()
    if code:
        prods = {s["product_id"] for s in supplier_items if str(s.get("supplier_sku") or "").upper() == code}
        hits = [t for t in tasks if t["product_id"] in prods]
        if len(hits) == 1:
            return {"status": "exact", "method": "item_code", "score": 1.0, "task_id": hits[0]["id"], "candidates": [hits[0]["id"]]}
    text = " ".join(str(read.get(k) or "") for k in ("description", "color"))
    scored = sorted(((max(similarity(text, t.get("product_name")), similarity(text, t.get("supplier_item_name")),
                          similarity(read.get("description"), t.get("product_name"))), t) for t in tasks),
                    key=lambda x: -x[0])
    if scored and scored[0][0] >= 0.85 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.10):
        return {"status": "probable", "method": "similarity", "score": round(scored[0][0], 3),
                "task_id": scored[0][1]["id"], "candidates": [t["id"] for _, t in scored[:3]]}
    if len(tasks) == 1:
        return {"status": "probable", "method": "single_line", "score": round(scored[0][0], 3) if scored else 0.0,
                "task_id": tasks[0]["id"], "candidates": [tasks[0]["id"]]}
    return {"status": "ambiguous" if tasks else "none", "method": "", "score": round(scored[0][0], 3) if scored else 0.0,
            "task_id": "", "candidates": [t["id"] for _, t in scored[:3]]}


def check_totals(lines: Sequence[Dict[str, Any]], totals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bandingkan jumlah baris (angka `value` terpilih) dengan total tercetak per satuan. Return daftar ketidakcocokan."""
    out = []
    for t in totals:
        unit = t.get("unit")
        tv = parse_doc_number(t.get("qty_text")).get("value") if t.get("qty") is None else t["qty"]
        if tv is None or not unit or unit == "other":
            continue
        vals = [q["value"] for ln in lines for q in ln.get("quantities", [])
                if q.get("unit") == unit and q.get("role", "").startswith("delivered") and q.get("value") is not None]
        if vals and abs(sum(vals) - float(tv)) > 0.01:
            out.append({"unit": unit, "printed": float(tv), "sum": round(sum(vals), 3)})
    return out


def name_mismatch(printed: Optional[str], names: Sequence[str], threshold: float = 0.6) -> bool:
    """True bila nama tercetak ada tetapi tidak mirip nama/alias mana pun (abaikan PT/CV/TBK/titik)."""
    strip = lambda s: re.sub(r"\b(pt|cv|tbk|ud)\b|[.,]", " ", str(s or "").lower())  # noqa: E731
    if not (printed or "").strip():
        return False
    return max([similarity(strip(printed), strip(n)) for n in names if n] or [0.0]) < threshold
