"""GRN Fase 4 — aturan murni pembacaan surat jalan (§4.8): angka, qty declared, nomor PO, pencocokan baris, total.

Semua fungsi di sini MURNI (tanpa DB/IO) supaya bisa diuji unit dengan JSON `read` dari Lampiran C.
"""
import itertools
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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


def desc_key(read: Dict[str, Any]) -> str:
    """Kunci pemetaan profil: kode barang, atau deskripsi+warna yang dinormalkan."""
    code = re.sub(r"[.$]", "_", str(read.get("item_code") or "").strip().upper())
    if code:
        return f"code:{code}"
    text = " ".join(re.sub(r"[^a-z0-9 ]", " ", " ".join(str(read.get(k) or "") for k in ("description", "color")).lower()).split())
    return f"desc:{text}" if text else ""


def infer_locale(qty_text: Optional[str]) -> str:
    """Format angka yang TERBUKTI dari satu teks: id (1.250,00 · 19,00) | en (2,186.00 · 12.5) | '' (tak bisa ditentukan)."""
    s = re.sub(r"[^\d.,]", "", str(qty_text or ""))
    if "." in s and "," in s:
        return "id" if s.rfind(",") > s.rfind(".") else "en"
    for sep, loc in ((",", "id"), (".", "en")):
        if s.count(sep) == 1:
            tail = s.split(sep)[1]
            if 1 <= len(tail) <= 2:
                return loc
    return ""


def _norm_code(s: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def _color_score(color: str, t: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """Warna di SJ = warna VERSI SUPPLIER; dibandingkan dengan nama/kode warna supplier yang tersinkron ke produk KN,
    lalu nama warna internal sebagai cadangan. None = tidak ada data warna untuk dibandingkan."""
    cands = [(v.get("supplier_color_code"), "supplier_color_code") for v in t.get("supplier_colors") or []]
    cands += [(v.get("supplier_color_name"), "supplier_color") for v in t.get("supplier_colors") or []]
    cands += [(t.get("internal_color"), "internal_color")]
    cands = [(c, k) for c, k in cands if c]
    if not color or not cands:
        return None, ""
    for c, k in cands:
        if k == "supplier_color_code" and _norm_code(c) and _norm_code(c) in _norm_code(color):
            return 1.0, k
    best = max(((similarity(color, c), k) for c, k in cands), key=lambda x: x[0])
    return best


def _line_score(read: Dict[str, Any], t: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    desc, color = str(read.get("description") or ""), str(read.get("color") or "")
    names = [(n, "supplier_name") for n in t.get("supplier_names") or [] if n] + [(t.get("product_name"), "internal_name")]
    full = f"{desc} {color}".strip()
    name_best = max(((max(similarity(desc, n), similarity(full, n)), k, n) for n, k in names if n),
                    key=lambda x: x[0], default=(0.0, "", ""))
    cs, ck = _color_score(color, t)
    score = name_best[0] if cs is None else 0.6 * name_best[0] + 0.4 * cs
    return score, {"name_via": name_best[1], "name": name_best[2], "color_via": ck, "color_score": cs}


def match_line(read: Dict[str, Any], tasks: Sequence[Dict[str, Any]], supplier_items: Sequence[Dict[str, Any]],
               item_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Baris SJ (nama & warna VERSI SUPPLIER) → tugas PO (produk KN). Urutan: pemetaan profil (riwayat SJ yang dicek)
    → kode supplier (`supplier_items.supplier_sku`) → kode warna supplier (unik) → kemiripan nama barang supplier
    (`supplier_item_name`) + warna supplier (`products.supplier_colors`), nama/warna internal hanya cadangan
    → satu-satunya baris PO. Skor ≥ 0,85 & unggul ≥ 0,10 = probable; selain itu ambiguous (manusia memilih)."""
    learned = (item_map or {}).get(desc_key(read)) or {}
    if learned.get("product_id"):
        hits = [t for t in tasks if t.get("product_id") == learned["product_id"]]
        if len(hits) == 1:
            return {"status": "exact", "method": "profile", "score": 1.0, "task_id": hits[0]["id"],
                    "candidates": [hits[0]["id"]], "via": {"name_via": "profile"}}
    code = _norm_code(read.get("item_code"))
    if code:
        prods = {s["product_id"] for s in supplier_items if _norm_code(s.get("supplier_sku")) == code}
        hits = [t for t in tasks if t["product_id"] in prods]
        if len(hits) == 1:
            sname = next((s.get("supplier_item_name") for s in supplier_items if _norm_code(s.get("supplier_sku")) == code
                          and s["product_id"] == hits[0]["product_id"]), "")
            return {"status": "exact", "method": "item_code", "score": 1.0, "task_id": hits[0]["id"],
                    "candidates": [hits[0]["id"]], "via": {"name_via": "supplier_sku", "name": sname}}
        hits = [t for t in tasks if any(_norm_code(v.get("supplier_color_code")) == code
                                        for v in t.get("supplier_colors") or [] if v.get("supplier_color_code"))]
        if len(hits) == 1:
            return {"status": "exact", "method": "supplier_color_code", "score": 1.0, "task_id": hits[0]["id"],
                    "candidates": [hits[0]["id"]], "via": {"color_via": "supplier_color_code"}}
    scored = sorted(((*_line_score(read, t), t) for t in tasks), key=lambda x: -x[0])
    if scored and scored[0][0] >= 0.85 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.10):
        return {"status": "probable", "method": "similarity", "score": round(scored[0][0], 3), "via": scored[0][1],
                "task_id": scored[0][2]["id"], "candidates": [t["id"] for _, _, t in scored[:3]]}
    if len(tasks) == 1:
        return {"status": "probable", "method": "single_line", "score": round(scored[0][0], 3) if scored else 0.0,
                "task_id": tasks[0]["id"], "candidates": [tasks[0]["id"]], "via": scored[0][1] if scored else {}}
    return {"status": "ambiguous" if tasks else "none", "method": "", "score": round(scored[0][0], 3) if scored else 0.0,
            "task_id": "", "candidates": [t["id"] for _, _, t in scored[:3]], "via": {}}


def assign_packing_groups(lines: Sequence[Dict[str, Any]], groups: Sequence[Dict[str, Any]]) -> Tuple[Dict[int, List[Dict[str, Any]]], List[int]]:
    """Fase 6 — kelompok packing list → baris SJ (stok). Lot sama → kemiripan item_hint ≥ 0,6 & unggul → (tanpa
    item_hint) satu-satunya baris stok / urutan bila jumlah kelompok = jumlah baris. Return ({line_no: [roll...]}, [indeks kelompok tak terpetakan])."""
    stock = [ln for ln in lines if not ln.get("is_non_stock")]
    out: Dict[int, List[Dict[str, Any]]] = {}
    lost: List[int] = []
    for gi, g in enumerate(groups):
        target = None
        if g.get("lot"):
            hit = [ln for ln in stock if str((ln.get("read") or {}).get("lot") or "").strip().upper() == str(g["lot"]).strip().upper()]
            target = hit[0] if len(hit) == 1 else None
        if target is None and g.get("item_hint"):
            sc = sorted(((similarity(g["item_hint"], " ".join(str((ln.get("read") or {}).get(k) or "")
                                                              for k in ("description", "color"))), ln) for ln in stock),
                        key=lambda x: -x[0])
            if sc and sc[0][0] >= 0.6 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.1):
                target = sc[0][1]
        elif target is None and stock:   # tanpa petunjuk barang: satu-satunya baris / urutan bila jumlah sama
            target = stock[0] if len(stock) == 1 else (stock[gi] if len(groups) == len(stock) else None)
        if target is None:
            lost.append(gi)
            continue
        bucket = out.setdefault(target["line_no"], [])
        for r in g.get("rolls") or []:
            bucket.append({"seq": len(bucket) + 1, "length": r.get("length"), "length_unit": r.get("length_unit") or "",
                           "length_text": r.get("length_text") or "", "weight_kg": r.get("weight_kg"),
                           "lot": g.get("lot") or "", "grade": g.get("grade") or "", "group": g.get("group_label") or ""})
    return out, lost


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
