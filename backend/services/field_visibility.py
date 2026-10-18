"""L01 (LN-012) — visibilitas atribut stok per peran: grade · LOT · asal lokal/impor.

Izin: `field_visibility.grade|lot|origin` (boleh melihat). Peran berprofil POV Sales
komersial (`sales_pov.commercial`) TIDAK PERNAH melihat grade walau diberi izin.
Penegakan di SATU choke point (middleware respons JSON + filter query) supaya layar,
API langsung, detail dan ekspor tidak bisa lupa dipagari. PDF memakai `redact()`.
"""
import json
import re
import time
from typing import Any, Dict, FrozenSet, Optional, Set
from urllib.parse import parse_qsl, urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from db import db

FIELDS = ("grade", "lot", "origin")
KEYS: Dict[str, FrozenSet[str]] = {
    "grade": frozenset({"grade", "grades", "grade_label", "grade_rank", "grade_before", "grade_after",
                        "grade_code", "stock_by_grade", "by_grade", "grade_breakdown", "min_grade",
                        "allowed_grades", "preferred_grades", "quality_grade", "grade_counts"}),
    "lot": frozenset({"lot", "lots", "lot_id", "lot_code", "lot_number", "lot_no", "dye_lot", "dye_lots",
                      "supplier_lot", "batch_lot_rolls", "batch", "has_mixed_lot", "lot_label", "by_lot"}),
    "origin": frozenset({"origin", "origin_label", "origin_code", "is_import"}),
}
# Parameter penyaring yang bisa membocorkan atribut lewat hitungan hasil.
QUERY_KEYS = {"grade": {"grade", "grades", "min_grade"}, "lot": {"lot", "lot_id", "dye_lot", "supplier_lot"},
              "origin": {"origin"}}
# Kosakata (bukan data stok) dan layar pengaturan hak akses tidak disaring.
EXEMPT_PREFIXES = ("/api/enums", "/api/auth", "/api/access", "/api/permissions", "/api/admin/roles",
                   "/api/master/grades")

_cache: Dict[str, Any] = {}
_TTL = 15.0
_version = {"n": 0}


def invalidate() -> None:
    _version["n"] += 1
    _cache.clear()


def hidden_for(perms: Dict[str, Any]) -> Set[str]:
    fv = set(perms.get("field_visibility") or [])
    if "*" in fv:
        fv = set(FIELDS)
    hidden = {f for f in FIELDS if f not in fv}
    if "commercial" in set(perms.get("sales_pov") or []):
        hidden.add("grade")
    return hidden


async def hidden_for_token(token: str) -> Set[str]:
    if not token:
        return set()
    hit = _cache.get(token)
    now = time.time()
    if hit and hit[0] > now and hit[2] == _version["n"]:
        return hit[1]
    session = await db.sessions.find_one({"token": token}, {"_id": 0, "user_id": 1})
    user = await db.users.find_one({"id": (session or {}).get("user_id")}, {"_id": 0, "role": 1}) if session else None
    hidden: Set[str] = set()
    if user:
        from dependencies import permission_matrix
        hidden = hidden_for((await permission_matrix()).get(user.get("role"), {}) or {})
    _cache[token] = (now + _TTL, hidden, _version["n"])
    return hidden


async def hidden_for_user(user: Dict[str, Any]) -> Set[str]:
    from dependencies import permission_matrix
    return hidden_for((await permission_matrix()).get(user.get("role"), {}) or {})


# Kode SKU KN: ARTIKEL(9)-ASAL(1)-WARNA(4)-GRADE(2)-CUSTOMER(2)-LOT(2) — segmen yang dirahasiakan disamarkan.
_SKU_RE = re.compile(r"\b([A-Z0-9]{9})-([A-Z])-([A-Z0-9]{4})-([A-Z0-9]{2})-([A-Z0-9]{2})-([A-Z0-9]{2})\b")
_NAME_KEYS = ("name", "product_name", "variant_name", "display_name", "label", "title", "item_name", "description")


def _mask_sku(text: str, hidden: Set[str]) -> str:
    def rep(m):
        g = list(m.groups())
        if "origin" in hidden:
            g[1] = "•"
        if "grade" in hidden:
            g[3] = "••"
        if "lot" in hidden:
            g[5] = "••"
        return "-".join(g)
    return _SKU_RE.sub(rep, text)


def _grade_of(o: Dict[str, Any]) -> str:
    va = o.get("variant_attrs")
    g = o.get("grade") or (va.get("grade") if isinstance(va, dict) else "")
    if g:
        return str(g)
    for k, v in o.items():
        if "sku" in k and isinstance(v, str):
            m = _SKU_RE.search(v)
            if m:
                return m.group(4).lstrip("X") or ""
    return ""


_LOT_TAIL = re.compile(r"\s+LOT\s+\S+\s*$")
_PG: Dict[str, str] = {}
_PG_AT = [0.0]


async def ensure_product_grades() -> None:
    """Peta product_id → grade (cache 60 dtk) untuk membersihkan nama di baris ringan {product_id, product_name}."""
    if time.time() - _PG_AT[0] < 60:
        return
    rows = await db.products.find({"grade": {"$nin": [None, ""]}}, {"_id": 0, "id": 1, "grade": 1}).to_list(50000)
    _PG.clear()
    _PG.update({r["id"]: str(r["grade"]) for r in rows})
    _PG_AT[0] = time.time()


def _strip_name(name: str, grades: Set[str], hidden: Set[str]) -> str:
    """Nama varian KN: "<ARTIKEL> <warna> <grade>[ LOT <lot>]" — akhiran grade/LOT dibuang sesuai POV."""
    lot = ""
    m = _LOT_TAIL.search(name)
    if m:
        lot, name = m.group(0), name[: m.start()]
    for grade in sorted(grades, key=len, reverse=True):
        if "grade" in hidden and name.endswith(" " + grade):
            name = name[: -len(grade) - 1]
            break
    return name if "lot" in hidden else name + lot


def redact(obj: Any, hidden: Set[str], placeholder: Optional[str] = None) -> Any:
    """L01 LN-012 — buang kunci atribut tersembunyi, samarkan segmen SKU (asal/grade/LOT) dan
    akhiran grade pada nama varian (keputusan owner 2026-10-16: kode & nama ikut disamarkan)."""
    keys = frozenset().union(*(KEYS[h] for h in hidden)) if hidden else frozenset()
    if not keys:
        return obj

    def walk(o: Any) -> Any:
        if isinstance(o, dict):
            product_ctx = any(k in o for k in ("product_id", "sku", "product_sku", "variant_attrs")) or \
                str(o.get("id", "")).startswith("prod")
            grade: Set[str] = set()
            if product_ctx and "grade" in hidden:
                grade = {g for g in (_grade_of(o), _PG.get(str(o.get("product_id") or o.get("id") or ""), "")) if g}
                for k, v in o.items():   # grade dari segmen SKU (roll ber-grade beda dari nama produk)
                    if "sku" in k and isinstance(v, str):
                        m = _SKU_RE.search(v)
                        if m and m.group(4).lstrip("X"):
                            grade.add(m.group(4).lstrip("X"))
            out = {}
            for k, v in o.items():
                if k in keys:
                    if placeholder is not None:
                        out[k] = placeholder
                    continue
                if isinstance(v, str):
                    if product_ctx and k in _NAME_KEYS and (grade or "lot" in hidden):
                        v = _strip_name(v, grade, hidden)
                    out[k] = _mask_sku(v, hidden) if "-" in v else v
                else:
                    out[k] = walk(v)
            return out
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, str) and "-" in o:
            return _mask_sku(o, hidden)
        return o
    return walk(obj)


class FieldVisibilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)
        from dependencies import extract_token
        hidden = await hidden_for_token(extract_token(request))
        if not hidden:
            return await call_next(request)
        await ensure_product_grades()
        if "lot" in hidden and path.startswith("/api/lots"):
            return Response(content=json.dumps({"detail": "Registri LOT tidak tersedia untuk peran Anda."}).encode(),
                            status_code=403, media_type="application/json")
        drop = set().union(*(QUERY_KEYS[h] for h in hidden))
        qs = parse_qsl(request.scope.get("query_string", b"").decode(), keep_blank_values=True)
        if any(k in drop for k, _ in qs):
            request.scope["query_string"] = urlencode([(k, v) for k, v in qs if k not in drop]).encode()
        response = await call_next(request)
        if "application/json" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            content = json.dumps(redact(json.loads(body), hidden), ensure_ascii=False, default=str).encode()
        except ValueError:
            content = body
        out = Response(content=content, status_code=response.status_code)
        out.raw_headers = [h for h in response.raw_headers if h[0].lower() != b"content-length"] + [
            (b"content-length", str(len(content)).encode()),
            (b"x-kn-fields-hidden", ",".join(sorted(hidden)).encode())]
        return out
