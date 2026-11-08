#!/usr/bin/env python3
"""Audit B3b (2026-11-09) — silangkan panggilan API frontend ↔ skema request backend (OpenAPI).

HANYA MEMBACA. Masukan:
  --openapi  openapi.json dari backend yang berjalan (GET /openapi.json)
  --census   keluaran scripts/audit/b3b_fe_census.js
  --backend  folder backend/ (untuk memetakan operasi → berkas:baris lewat AST)
  --out      JSON hasil + ringkasan teks di stdout

Yang dihitung per panggilan tulis (POST/PUT/PATCH) di berkas cakupan:
  * endpoint OpenAPI yang cocok (pola path), berkas:baris router
  * skema body: nama model, field wajib, field + batas (minimum/maximum/maxLength/pattern/enum)
  * kunci payload FE yang TIDAK ada di skema  → dibuang diam-diam (Pydantic v2 default extra=ignore)
  * field WAJIB skema yang tidak dikirim FE   → kandidat 422
  * endpoint tanpa body padahal FE mengirim payload → payload dibuang seluruhnya
  * body `dict` (tanpa skema) → tidak divalidasi sama sekali
Plus inventaris endpoint tulis di router cakupan: field angka tanpa batas, teks tanpa maxLength,
field rujukan (`*_id`) bertipe teks bebas.
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

SCOPE_ROUTERS = [
    "purchase_orders", "purchase_orders_extra", "goods_receipts", "ocr_samples", "inbound_scan_label",
    "inbound_receiving", "inbound_receiving_extra", "qc_inspection", "inspections", "putaway_orders", "wms",
    "warehouses", "warehouse_sites", "transfers", "deliveries", "logistics", "outbound_picking",
    "outbound_picking_extra", "cutting", "sample_orders", "cycle_count", "initial_registration", "rfid",
    "rfid_v2", "rfid_v2_ops", "label_printer", "sales_returns", "return_disposition", "purchase_returns",
    "makloon_orders", "repair_orders", "lots", "inventory", "stock_buckets", "grade_master", "settings",
    "config", "interco", "fulfillment",
]

SCOPE_FE = re.compile(
    r"^(features/(wms|rfid|inspections|transfers|mobile|logistics|samples)/|"
    r"features/inventory/(registration|lots|CycleCount|UnknownRollForm|RollCountPanel|RollReconcileTable)|"
    r"features/purchasing/(Makloon|makloon/|PurchaseReturns|ReturnDetailPanel|RollPickerModal|GrnDocVariance)|"
    r"features/admin/(po/|PurchaseOrderManagement)|features/sales/(SalesReturns|returns?/|Return)|"
    r"features/settings/(ReceivingOcrSettings|devices/|masters/GradeMasterView)|features/manager/EscalationManagement|"
    r"features/finance/interco/(IntercoReturn|Return)|"
    r"components/(LocationFields|RollPicker|QcRequestPicker|LabelPrinterModal|RollReconcileSheet|RollLabelActions|"
    r"MixedLotConfirmModal|UomInputConvert|SiteSelect|PrinterStatusWidget|RollCheckChips|ReturnTimeline))"
)


def load_router_index(backend: Path):
    """→ {(METHOD, path): (berkas, baris, fungsi, [(arg, anotasi)])}"""
    idx = {}
    for f in sorted((backend / "routers").glob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        prefixes = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                fn = node.value.func
                if (isinstance(fn, ast.Name) and fn.id == "APIRouter") or (isinstance(fn, ast.Attribute) and fn.attr == "APIRouter"):
                    pre = ""
                    for kw in node.value.keywords:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                            pre = kw.value.value
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            prefixes[t.id] = pre
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                m = dec.func.attr
                if m not in ("get", "post", "put", "patch", "delete"):
                    continue
                obj = dec.func.value
                rname = obj.id if isinstance(obj, ast.Name) else None
                if rname not in prefixes:
                    continue
                if not dec.args or not isinstance(dec.args[0], ast.Constant):
                    continue
                full = prefixes[rname] + dec.args[0].value
                args = []
                for a in node.args.args + node.args.kwonlyargs:
                    ann = ast.unparse(a.annotation) if a.annotation is not None else ""
                    args.append((a.arg, ann))
                idx[(m.upper(), full)] = (f"backend/routers/{f.name}", node.lineno, node.name, args)
    return idx


def path_regex(p):
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(p)) + "$")


def fe_url_norm(u):
    u = u.split("?")[0]
    u = re.sub(r"\{[^}]*\}", "X", u)  # placeholder FE
    if not u.startswith("/api"):
        return None
    return u.rstrip("/") or u


def resolve(schema, comps, depth=0):
    if depth > 8 or not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return dict(resolve(comps.get(name, {}), comps, depth + 1), __name__=name)
    if "anyOf" in schema:
        subs = [resolve(s, comps, depth + 1) for s in schema["anyOf"]]
        non_null = [s for s in subs if s.get("type") != "null"]
        base = dict(non_null[0]) if non_null else {}
        base["__nullable__"] = len(non_null) != len(subs)
        if len(non_null) > 1:
            base["__anyof__"] = [s.get("type") or s.get("__name__") for s in non_null]
        for k in ("default", "title", "description"):
            if k in schema:
                base[k] = schema[k]
        return base
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return dict(resolve(schema["allOf"][0], comps, depth + 1), **{k: v for k, v in schema.items() if k != "allOf"})
    return schema


def describe_field(name, sch, comps, required):
    s = resolve(sch, comps)
    t = s.get("type") or s.get("__name__") or ("enum" if "enum" in s else "?")
    out = {"field": name, "type": t, "required": required}
    for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern", "enum", "minItems", "maxItems"):
        if k in s:
            out[k] = s[k]
    if "default" in sch or "default" in s:
        out["default"] = sch.get("default", s.get("default"))
    if s.get("__nullable__"):
        out["nullable"] = True
    if t == "array":
        it = resolve(s.get("items", {}), comps)
        out["items"] = it.get("__name__") or it.get("type")
    return out


def model_fields(sch, comps, depth=0):
    s = resolve(sch, comps)
    if s.get("type") != "object" and "properties" not in s:
        return None, s
    req = set(s.get("required", []))
    fields = [describe_field(k, v, comps, k in req) for k, v in (s.get("properties") or {}).items()]
    return fields, s


def flatten_keys(keys, prefix=""):
    """kunci payload FE (struktur sensus) → set nama kunci tingkat atas + penanda spread."""
    top, spreads, nested = set(), [], {}
    for k in keys or []:
        if "spread" in k:
            spreads.append(k["spread"])
            sub = k.get("keys") or []
            for s in sub:
                if "state" in s:
                    for ss in s.get("keys") or []:
                        if "key" in ss:
                            top.add(ss["key"])
                elif "key" in s:
                    top.add(s["key"])
            continue
        if "state" in k:
            for ss in k.get("keys") or []:
                if "key" in ss:
                    top.add(ss["key"])
            continue
        if "key" in k:
            top.add(k["key"])
            if k.get("nested"):
                nested[k["key"]] = k["nested"]
    return top, spreads, nested


def nested_keys(nested_desc):
    if not nested_desc:
        return set()
    out = set()
    for n in nested_desc:
        if n.get("array"):
            for kk in n.get("keys") or []:
                if "key" in kk:
                    out.add(kk["key"])
                elif "spread" in kk:
                    out.add("…" + kk["spread"])
        elif "key" in n:
            out.add(n["key"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--openapi", required=True)
    ap.add_argument("--census", required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.loads(Path(a.openapi).read_text(encoding="utf-8"))
    comps = spec.get("components", {}).get("schemas", {})
    census = json.loads(Path(a.census).read_text(encoding="utf-8"))
    ridx = load_router_index(Path(a.backend))

    ops = []
    for p, item in spec["paths"].items():
        for m, op in item.items():
            ops.append((m.upper(), p, op, path_regex(p.rstrip("/") or p)))

    def match(method, url):
        nu = fe_url_norm(url)
        if not nu:
            return None
        nu_re = nu.replace("X", "{x}")
        cands = []
        for m, p, op, rx in ops:
            if m != method:
                continue
            pp = re.sub(r"\{[^}]+\}", "{x}", p.rstrip("/") or p)
            if pp == nu_re:
                cands.append((0, p, op))
            elif rx.match(nu.replace("X", "x1")):
                cands.append((1, p, op))
        if not cands:
            return None
        cands.sort(key=lambda c: (c[0], -len(c[1])))
        return cands[0][1], cands[0][2]

    import posixpath
    files = census["files"]

    def resolve_src(frm, source):
        if source.startswith("@/"):
            base = source[2:]
        elif source.startswith("."):
            base = posixpath.normpath(posixpath.join(posixpath.dirname(frm), source))
        else:
            return None
        for e in ("", ".jsx", ".js", "/index.jsx", "/index.js"):
            if base + e in files:
                return base + e
        return None

    # registri pembungkus API: (berkas, pemilik) → panggilan axios dengan parameter
    wrappers = {}
    for f, rec in files.items():
        for c in rec.get("apiCalls") or []:
            if c.get("owner"):
                wrappers[(f, c["owner"])] = c

    def synth_calls(f, rec):
        out = []
        for w in rec.get("wrapperCalls") or []:
            imp = (rec.get("importMap") or {}).get(w["local"])
            if not imp:
                continue
            mod = resolve_src(f, imp["source"])
            if not mod:
                continue
            owner = (imp["imported"] + "." + w["member"]) if w["member"] else imp["imported"]
            if imp["imported"] in ("default", "*") and w["member"]:
                owner = w["member"]
            c = wrappers.get((mod, owner))
            if not c:
                continue
            url = c["url"]
            for i, a in enumerate(w["args"]):
                url = url.replace("{@%d}" % i, (a or {}).get("lit") or "{x}")
            url = re.sub(r"\{@\d+\}", "{x}", url)
            sc = {"method": c["method"], "url": url, "line": w["line"], "fn": f"{owner}@{mod}:{c['line']}"}
            pi = c.get("payloadParam")
            if pi is not None and pi >= 0 and pi < len(w["args"]) and w["args"][pi]:
                a = w["args"][pi]
                if a.get("keys") is not None:
                    sc["payload"] = a["keys"]
                    if a.get("var"):
                        sc["payloadVar"] = a["var"]
                elif a.get("var"):
                    sc["payloadVar"] = a["var"]
                    sc["payload"] = None
                else:
                    sc["payloadExpr"] = a.get("expr")
            elif c.get("payload") is not None and c.get("payloadParam") is None:
                sc["payload"] = c["payload"]
            out.append(sc)
        return out

    results = []
    for f, rec in sorted(files.items()):
        if not SCOPE_FE.match(f) or "apiCalls" not in rec:
            continue
        # panggilan langsung yang URL-nya masih memuat parameter pembungkus dicatat lewat situs panggilnya
        direct = [c for c in rec["apiCalls"] if "{@" not in c.get("url", "") and c.get("payloadParam") is None]
        for c in direct + synth_calls(f, rec):
            r = {"fe": f"frontend/src/{f}:{c['line']}", "method": c["method"], "url": c["url"], "fn": c.get("fn", "")}
            mm = match(c["method"], c["url"])
            if not mm:
                r["endpoint"] = None
                results.append(r)
                continue
            p, op = mm
            r["endpoint"] = p
            src = ridx.get((c["method"], p))
            if src:
                r["be"] = f"{src[0]}:{src[1]}"
                r["be_fn"] = src[2]
            if c["method"] in ("POST", "PUT", "PATCH"):
                rb = op.get("requestBody")
                if not rb:
                    r["body"] = "TANPA_BODY"
                else:
                    sch = rb.get("content", {}).get("application/json", {}).get("schema") or \
                        next(iter(rb.get("content", {}).values()), {}).get("schema", {})
                    fields, rs = model_fields(sch, comps)
                    r["body_model"] = rs.get("__name__") or rs.get("title")
                    if fields is None or (rs.get("additionalProperties") is True and not rs.get("properties")):
                        r["body"] = "DICT_BEBAS" if rs.get("type") == "object" else f"NON_OBJECT:{rs.get('type')}"
                    else:
                        r["body"] = "MODEL"
                        r["fields"] = fields
                if c.get("payload") is not None or c.get("payloadVar"):
                    top, spreads, nested = flatten_keys(c.get("payload"))
                    r["fe_keys"] = sorted(top)
                    r["fe_spreads"] = spreads
                    r["fe_payload_var"] = c.get("payloadVar")
                    if c.get("payloadExpr"):
                        r["fe_payload_expr"] = c["payloadExpr"]
                    if r.get("body") == "MODEL":
                        names = {x["field"] for x in r["fields"]}
                        r["dropped_keys"] = sorted(k for k in top if k not in names and not k.startswith("["))
                        r["missing_required"] = sorted(x["field"] for x in r["fields"] if x["required"] and x["field"] not in top) if not spreads else []
                        # satu tingkat ke dalam: items[]
                        nd = {}
                        for k, desc in nested.items():
                            fdef = next((x for x in r["fields"] if x["field"] == k), None)
                            if fdef and fdef.get("type") == "array" and fdef.get("items") in comps:
                                sub_fields, _ = model_fields({"$ref": f"#/components/schemas/{fdef['items']}"}, comps)
                                sub_names = {x["field"] for x in sub_fields or []}
                                fk = nested_keys(desc)
                                dropped = sorted(x for x in fk if x not in sub_names and not x.startswith("…"))
                                miss = sorted(x["field"] for x in sub_fields or [] if x["required"] and x["field"] not in fk) if not any(x.startswith("…") for x in fk) else []
                                if dropped or miss:
                                    nd[k] = {"model": fdef["items"], "dropped": dropped, "missing_required": miss}
                        if nd:
                            r["nested"] = nd
                    elif r.get("body") == "TANPA_BODY" and top:
                        r["dropped_keys"] = sorted(top)
                else:
                    r["fe_keys"] = None
            else:
                if c.get("params"):
                    top, _, _ = flatten_keys(c["params"])
                    r["fe_params"] = sorted(top)
                    qnames = {prm["name"] for prm in op.get("parameters", []) if prm.get("in") == "query"}
                    r["query_params"] = sorted(qnames)
                    r["dropped_params"] = sorted(k for k in top if k not in qnames)
                else:
                    r["query_params"] = sorted(prm["name"] for prm in op.get("parameters", []) if prm.get("in") == "query")
            results.append(r)

    # inventaris endpoint tulis di router cakupan
    inv = []
    for (m, p), src in sorted(ridx.items(), key=lambda x: (x[1][0], x[1][1])):
        mod = Path(src[0]).stem
        if mod not in SCOPE_ROUTERS or m not in ("POST", "PUT", "PATCH"):
            continue
        op = spec["paths"].get(p, {}).get(m.lower())
        if not op:
            continue
        row = {"method": m, "path": p, "be": f"{src[0]}:{src[1]}", "fn": src[2], "args": src[3]}
        rb = op.get("requestBody")
        if not rb:
            row["body"] = "TANPA_BODY"
        else:
            sch = next(iter(rb.get("content", {}).values()), {}).get("schema", {})
            fields, rs = model_fields(sch, comps)
            row["body_model"] = rs.get("__name__") or rs.get("title")
            if fields is None or (rs.get("additionalProperties") is True and not rs.get("properties")):
                row["body"] = "DICT_BEBAS"
            else:
                row["body"] = "MODEL"
                row["fields"] = fields
        inv.append(row)

    # inventaris endpoint GET daftar (tanpa {param} di ujung) di router cakupan: parameter halaman/batas
    gets = []
    for (m, p), src in sorted(ridx.items(), key=lambda x: (x[1][0], x[1][1])):
        mod = Path(src[0]).stem
        if mod not in SCOPE_ROUTERS or m != "GET" or p.rstrip("/").endswith("}"):
            continue
        op = spec["paths"].get(p, {}).get("get")
        if not op:
            continue
        qp = {}
        for prm in op.get("parameters", []):
            if prm.get("in") != "query":
                continue
            s = resolve(prm.get("schema", {}), comps)
            qp[prm["name"]] = {k: s.get(k) for k in ("type", "default", "minimum", "maximum") if k in s}
        paging = {k: v for k, v in qp.items() if k in ("limit", "page", "page_size", "skip", "offset", "before", "cursor", "per_page")}
        gets.append({"path": p, "be": f"{src[0]}:{src[1]}", "fn": src[2], "query": sorted(qp), "paging": paging,
                     "search": [k for k in qp if k in ("q", "search", "query", "keyword", "term")]})

    Path(a.out).write_text(json.dumps({"calls": results, "write_endpoints": inv, "list_endpoints": gets},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"endpoint_GET_daftar_cakupan={len(gets)} tanpa_param_halaman={sum(1 for g in gets if not g['paging'])} "
          f"limit_tanpa_maks={sum(1 for g in gets if 'limit' in g['paging'] and 'maximum' not in g['paging']['limit'])}")
    n_write = sum(1 for r in results if r["method"] in ("POST", "PUT", "PATCH"))
    n_drop = sum(1 for r in results if r.get("dropped_keys"))
    n_miss = sum(1 for r in results if r.get("missing_required"))
    n_nomatch = sum(1 for r in results if r.get("endpoint") is None)
    n_dict = sum(1 for r in inv if r["body"] == "DICT_BEBAS")
    print(f"panggilan={len(results)} tulis={n_write} kunci_dibuang={n_drop} wajib_hilang={n_miss} tak_cocok={n_nomatch} | endpoint_tulis_cakupan={len(inv)} body_dict={n_dict}")


if __name__ == "__main__":
    sys.exit(main())
