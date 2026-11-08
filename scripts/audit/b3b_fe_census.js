#!/usr/bin/env node
/**
 * Audit B3b (2026-11-09) — sensus statik form, isian, panggilan API & fitur daftar di frontend.
 *
 * HANYA MEMBACA kode. Tidak mengubah apa pun. Dipakai untuk laporan
 * `docs/audit/2026-11-09-wms-rfid/B3b-*.md`.
 *
 * Cara pakai (butuh node + @babel/parser + @babel/traverse, mis. di image kn-dev-frontend):
 *   node scripts/audit/b3b_fe_census.js <dir_src> <roots.json> <keluaran.json>
 *     dir_src    : jalur `frontend/src`
 *     roots.json : daftar berkas akar (relatif terhadap src) — layar yang diaudit
 *     keluaran   : JSON per berkas {imports, apiCalls, controls, states, buttons, layout, flags}
 *
 * Yang dicatat per berkas:
 *   - apiCalls : axios.<metode>(url, payload) → metode, URL (template dirender `{x}`), kunci payload
 *                (objek literal, variabel yang ditelusuri ke deklarasinya, `...spread`, `.map(() => ({…}))`)
 *   - controls : elemen isian (Input/input/Textarea/KNSelect/ProductSelect/…) + atribut (type, min, max,
 *                step, required, placeholder, value, onChange/onValueChange, data-testid, className)
 *   - states   : `useState({...})` → kunci awal (bentuk form)
 *   - buttons  : <Button>/<button> → size, variant, className, teks
 *   - layout   : FormModal/FormSection/Dialog/PaginationBar/ListControls/TableFilter/... + atributnya
 */
const fs = require("fs");
const path = require("path");
const parser = require("@babel/parser");
const traverse = require("@babel/traverse").default;

const [, , SRC, ROOTS, OUT] = process.argv;
const roots = JSON.parse(fs.readFileSync(ROOTS, "utf8"));

const EXTS = ["", ".jsx", ".js", "/index.jsx", "/index.js"];
function resolveImport(fromFile, spec) {
  let base;
  if (spec.startsWith(".")) base = path.resolve(path.dirname(fromFile), spec);
  else if (spec.startsWith("@/")) base = path.join(SRC, spec.slice(2));
  else return null;
  for (const e of EXTS) {
    const p = base + e;
    if (fs.existsSync(p) && fs.statSync(p).isFile()) return p;
  }
  return null;
}
const FOLLOW = (abs) => {
  const rel = path.relative(SRC, abs).replace(/\\/g, "/");
  if (rel.startsWith("components/ui/")) return false;
  if (rel.includes("__tests__")) return false;
  return rel.startsWith("features/") || rel.startsWith("components/") || rel.startsWith("hooks/");
};

const CONTROL_RE = /^(Input|input|Textarea|textarea|select|Select|KNSelect|ProductSelect|BaseFabricPicker|MakloonSelect|QcRequestPicker|LocationFields|DecimalInput|MoneyInput|KNDatePicker|KNDateTimePicker|KNMonthPicker|KNTimePicker|SiteSelect|RollPicker|Checkbox|Switch|RadioGroup|UomInputConvert|PantoneFinder|VariantAxisPicker|LineFilter|SupplierSelect|CustomerSelect|WarehouseSelect|BinSelect|[A-Z][A-Za-z]*(Select|Picker|Input|Finder|Field|Fields))$/;
const LAYOUT_RE = /^(FormModal|FormSection|Dialog|DialogContent|Sheet|SheetContent|Drawer|DetailDrawer|DetailModal|DetailPopup|ConfirmModal|PaginationBar|KNPager|PagedRows|ListControls|TableFilter|FilterChips|ResponsiveTable|Table|table|SeeAllModal|EmptyState|ErrorNotice|LoadingLine|Skeleton|ListPageParts|PageTabs|HubTabs|Tabs|ListToolbar|SearchBox|ListSearch|StatusChips|ChipFilter)$/;

function jsxName(n) {
  if (!n) return "";
  if (n.type === "JSXIdentifier") return n.name;
  if (n.type === "JSXMemberExpression") return jsxName(n.object) + "." + jsxName(n.property);
  return "";
}

function main() {
  const seen = new Map();
  const queue = roots.map((r) => path.join(SRC, r)).filter((p) => fs.existsSync(p));
  const missing = roots.filter((r) => !fs.existsSync(path.join(SRC, r)));
  while (queue.length) {
    const f = queue.shift();
    if (seen.has(f)) continue;
    let code;
    try { code = fs.readFileSync(f, "utf8"); } catch { continue; }
    let ast;
    try {
      ast = parser.parse(code, { sourceType: "module", plugins: ["jsx", "classProperties", "optionalChaining", "nullishCoalescingOperator", "dynamicImport", "objectRestSpread"], errorRecovery: true });
    } catch (e) { seen.set(f, { error: String(e) }); continue; }
    const rec = census(f, code, ast);
    seen.set(f, rec);
    for (const imp of rec.imports) {
      const abs = resolveImport(f, imp);
      if (abs && FOLLOW(abs) && !seen.has(abs)) queue.push(abs);
    }
  }
  const out = { roots, missing, files: {} };
  for (const [abs, rec] of seen) out.files[path.relative(SRC, abs).replace(/\\/g, "/")] = rec;
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log(`berkas=${seen.size} akar_hilang=${missing.length}`);
}

function census(file, code, ast) {
  const src = (n) => (n && n.start != null ? code.slice(n.start, n.end) : "");
  const short = (s, k = 160) => (s.length > k ? s.slice(0, k) + "…" : s);
  const rec = { imports: [], importMap: {}, wrapperCalls: [], apiCalls: [], controls: [], states: [], buttons: [], layout: [], flags: {} };

  function renderUrl(n, p, depth = 0, params = null) {
    if (!n || depth > 5) return "";
    if (n.type === "StringLiteral") return n.value;
    if (n.type === "Identifier" && n.name !== "API" && p) {
      const b = p.scope.getBinding(n.name);
      if (b && b.kind === "param" && params) { const i = params.indexOf(n.name); if (i >= 0) return `{@${i}}`; }
      if (b && b.path.node.type === "VariableDeclarator" && b.path.node.init && ["TemplateLiteral", "StringLiteral", "BinaryExpression"].includes(b.path.node.init.type)) {
        return renderUrl(b.path.node.init, b.path, depth + 1, params);
      }
    }
    if (n.type === "TemplateLiteral") {
      let s = "";
      n.quasis.forEach((q, i) => {
        s += q.value.cooked;
        if (i < n.expressions.length) {
          const ex = n.expressions[i];
          const e = src(ex);
          if (e === "API") s += "/api";
          else if (ex.type === "Identifier") {
            const r = renderUrl(ex, p, depth + 1, params);
            s += r && !r.startsWith("{" + e) ? r : `{${short(e, 40)}}`;
          } else s += `{${short(e, 40)}}`;
        }
      });
      return s;
    }
    if (n.type === "BinaryExpression" && n.operator === "+") return renderUrl(n.left, p, depth + 1, params) + renderUrl(n.right, p, depth + 1, params);
    if (n.type === "Identifier" && n.name === "API") return "/api";
    return `{${short(src(n), 60)}}`;
  }

  function objKeys(n, p, depth = 0) {
    // → [{key, nested?, value}] ; deskriptif, bukan evaluasi
    if (!n || depth > 4) return null;
    if (n.type === "ObjectExpression") {
      const keys = [];
      for (const pr of n.properties) {
        if (pr.type === "SpreadElement") {
          const inner = pr.argument.type === "Identifier" ? resolveIdent(pr.argument.name, p, depth + 1) : objKeys(pr.argument, p, depth + 1);
          keys.push({ spread: short(src(pr.argument), 60), keys: inner });
          continue;
        }
        const k = pr.key ? (pr.key.name || pr.key.value || src(pr.key)) : "?";
        const v = pr.value || pr.body;
        const ent = { key: String(k), value: short(src(v) || (pr.shorthand ? k : ""), 90) };
        if (v) {
          const nested = describeValue(v, p, depth + 1);
          if (nested) ent.nested = nested;
        }
        keys.push(ent);
      }
      return keys;
    }
    return describeValue(n, p, depth);
  }
  function describeValue(v, p, depth) {
    if (!v || depth > 4) return null;
    if (v.type === "ObjectExpression") return objKeys(v, p, depth);
    if (v.type === "ArrayExpression") {
      const el = v.elements.find((e) => e && e.type === "ObjectExpression");
      return el ? [{ array: true, keys: objKeys(el, p, depth + 1) }] : null;
    }
    if (v.type === "CallExpression" && v.callee.type === "MemberExpression" && ["map", "flatMap"].includes(v.callee.property.name)) {
      const fn = v.arguments[0];
      if (fn && (fn.type === "ArrowFunctionExpression" || fn.type === "FunctionExpression")) {
        let body = fn.body;
        if (body.type === "BlockStatement") {
          const ret = body.body.slice().reverse().find((s) => s.type === "ReturnStatement");
          body = ret ? ret.argument : null;
        }
        if (body) {
          const r = objKeys(body, p, depth + 1);
          return r ? [{ array: true, keys: r }] : null;
        }
      }
      // .map(...).filter(...) — rantai: cari .map di dalam
    }
    if (v.type === "CallExpression" && v.callee.type === "MemberExpression" && v.callee.object.type === "CallExpression") {
      return describeValue(v.callee.object, p, depth + 1);
    }
    if (v.type === "ConditionalExpression") {
      return describeValue(v.consequent, p, depth + 1) || describeValue(v.alternate, p, depth + 1);
    }
    if (v.type === "LogicalExpression") return describeValue(v.left, p, depth + 1) || describeValue(v.right, p, depth + 1);
    return null;
  }
  function resolveIdent(name, p, depth = 0) {
    if (!p || depth > 4) return null;
    const b = p.scope.getBinding(name);
    if (!b) return null;
    const node = b.path.node;
    let base = null;
    if (node.type === "VariableDeclarator" && node.init) {
      if (node.id.type === "Identifier") base = describeValue(node.init, b.path, depth + 1);
      else if (node.id.type === "ArrayPattern" && node.init.type === "CallExpression" && src(node.init.callee) === "useState") {
        base = describeValue(node.init.arguments[0], b.path, depth + 1);
        if (base) base = [{ state: true, keys: base }];
      }
    }
    // tambahan: penugasan `name.x = …` / `name[x] = …` setelah deklarasi
    const added = [];
    for (const ref of b.referencePaths) {
      const par = ref.parentPath;
      if (par && par.node.type === "MemberExpression" && par.node.object === ref.node) {
        const asg = par.parentPath;
        if (asg && asg.node.type === "AssignmentExpression" && asg.node.left === par.node) {
          const k = par.node.computed ? `[${short(src(par.node.property), 30)}]` : par.node.property.name;
          added.push({ key: k, value: short(src(asg.node.right), 90), assigned: true });
        }
      }
    }
    if (!base && !added.length) return null;
    return [...(base || []), ...added];
  }

  function argDesc(x, p) {
    if (!x) return null;
    if (x.type === "StringLiteral") return { lit: x.value };
    if (x.type === "TemplateLiteral" && !x.expressions.length) return { lit: x.quasis[0].value.cooked };
    if (x.type === "ObjectExpression") return { keys: objKeys(x, p) };
    if (x.type === "Identifier") { const r = resolveIdent(x.name, p); return r ? { keys: r, var: x.name } : { var: x.name }; }
    return { expr: short(src(x), 80) };
  }
  traverse(ast, {
    ImportDeclaration(p) {
      rec.imports.push(p.node.source.value);
      for (const sp of p.node.specifiers) {
        rec.importMap[sp.local.name] = { source: p.node.source.value, imported: sp.type === "ImportSpecifier" ? (sp.imported.name || sp.imported.value) : (sp.type === "ImportDefaultSpecifier" ? "default" : "*") };
      }
    },
    CallExpression(p) {
      const n = p.node;
      if (n.callee.type === "Import" && n.arguments[0] && n.arguments[0].type === "StringLiteral") rec.imports.push(n.arguments[0].value);
      if (n.callee.type === "Identifier" && n.callee.name === "lazy") {
        // lazy(() => import("x"))
      }
      if (n.callee.type === "MemberExpression" && !n.callee.computed) {
        const obj = src(n.callee.object);
        const m = n.callee.property.name;
        if (/^(axios|api|http|client|apiClient)$/.test(obj) && /^(get|post|put|patch|delete)$/.test(m)) {
          const encl = p.getFunctionParent();
          const fparams = encl ? encl.node.params.map((x) => (x.type === "Identifier" ? x.name : x.type === "AssignmentPattern" && x.left.type === "Identifier" ? x.left.name : "")) : null;
          const call = { method: m.toUpperCase(), url: renderUrl(n.arguments[0], p, 0, fparams), line: n.loc.start.line };
          const a1 = n.arguments[1];
          if (m === "get" || m === "delete") {
            if (a1) call.config = short(src(a1), 200);
            if (a1 && a1.type === "ObjectExpression") {
              const prm = a1.properties.find((x) => x.key && (x.key.name === "params"));
              if (prm) call.params = objKeys(prm.value, p) || [{ expr: short(src(prm.value), 80) }];
              const data = a1.properties.find((x) => x.key && (x.key.name === "data"));
              if (data) call.payload = objKeys(data.value, p) || [{ expr: short(src(data.value), 80) }];
            }
          } else if (a1) {
            if (a1.type === "Identifier") {
              call.payloadVar = a1.name;
              const pb = p.scope.getBinding(a1.name);
              if (pb && pb.kind === "param" && fparams) call.payloadParam = fparams.indexOf(a1.name);
              call.payload = resolveIdent(a1.name, p);
            } else {
              call.payload = objKeys(a1, p);
              if (!call.payload) call.payloadExpr = short(src(a1), 200);
            }
            if (n.arguments[2]) call.config = short(src(n.arguments[2]), 160);
          } else call.payload = null;
          // fungsi pembungkus terdekat
          const fn = p.getFunctionParent();
          if (fn) {
            const id = fn.node.id ? fn.node.id.name : (fn.parentPath && fn.parentPath.node.type === "VariableDeclarator" ? src(fn.parentPath.node.id) : (fn.parentPath && fn.parentPath.node.type === "ObjectProperty" ? src(fn.parentPath.node.key) : ""));
            call.fn = id;
            // pemilik: `obj.prop` bila fungsi adalah properti objek yang diinisialisasi ke variabel
            if (fn.parentPath && fn.parentPath.node.type === "ObjectProperty") {
              const objPath = fn.parentPath.parentPath;
              if (objPath && objPath.parentPath && objPath.parentPath.node.type === "VariableDeclarator") call.owner = src(objPath.parentPath.node.id) + "." + id;
            } else if (id) call.owner = id;
          }
          rec.apiCalls.push(call);
        }
        if (/^(downloadCsv|exportCsv|toCsv|buildCsv)$/.test(m)) rec.flags.csvCall = (rec.flags.csvCall || 0) + 1;
        if (n.callee.object.type === "Identifier") {
          const on = n.callee.object.name;
          const b = p.scope.getBinding(on);
          if (b && b.kind === "module") rec.wrapperCalls.push({ local: on, member: m, line: n.loc.start.line, args: n.arguments.map((x) => argDesc(x, p)) });
        }
      }
      if (n.callee.type === "Identifier") {
        const nm = n.callee.name;
        { const b = p.scope.getBinding(nm); if (b && b.kind === "module") rec.wrapperCalls.push({ local: nm, member: null, line: n.loc.start.line, args: n.arguments.map((x) => argDesc(x, p)) }); }
        if (/csv|Csv|CSV/.test(nm)) rec.flags["csv:" + nm] = (rec.flags["csv:" + nm] || 0) + 1;
        if (/xlsx|Xlsx|XLSX|excel|Excel/.test(nm)) rec.flags["xlsx:" + nm] = (rec.flags["xlsx:" + nm] || 0) + 1;
        if (nm === "useState" && n.arguments[0] && n.arguments[0].type === "ObjectExpression" && p.parentPath.node.type === "VariableDeclarator" && p.parentPath.node.id.type === "ArrayPattern") {
          rec.states.push({ name: src(p.parentPath.node.id.elements[0]), line: n.loc.start.line, keys: objKeys(n.arguments[0], p) });
        }
      }
    },
    JSXOpeningElement(p) {
      const name = jsxName(p.node.name);
      const attrs = {};
      for (const a of p.node.attributes) {
        if (a.type === "JSXSpreadAttribute") { attrs["..."] = short(src(a.argument), 60); continue; }
        const k = a.name.type === "JSXNamespacedName" ? a.name.namespace.name + ":" + a.name.name.name : a.name.name;
        if (a.value == null) attrs[k] = true;
        else if (a.value.type === "StringLiteral") attrs[k] = a.value.value;
        else if (a.value.type === "JSXExpressionContainer") attrs[k] = "{" + short(src(a.value.expression), 140) + "}";
        else attrs[k] = short(src(a.value), 80);
      }
      const line = p.node.loc.start.line;
      const text = () => {
        const el = p.parentPath.node;
        const parts = [];
        const walk = (c) => {
          for (const ch of c || []) {
            if (ch.type === "JSXText") parts.push(ch.value.trim());
            else if (ch.type === "JSXExpressionContainer") {
              const e = ch.expression;
              if (e.type === "StringLiteral") parts.push(e.value);
              else if (e.type === "TemplateLiteral") parts.push(src(e));
              else if (e.type === "ConditionalExpression") parts.push(short(src(e), 60));
            } else if (ch.type === "JSXElement") walk(ch.children);
          }
        };
        walk(el.children);
        return short(parts.filter(Boolean).join(" "), 80);
      };
      if (name === "Button" || name === "button") {
        rec.buttons.push({ tag: name, line, size: attrs.size, variant: attrs.variant, className: attrs.className, type: attrs.type, testid: attrs["data-testid"], text: text() });
      } else if (CONTROL_RE.test(name)) {
        rec.controls.push({ tag: name, line, attrs });
      } else if (LAYOUT_RE.test(name)) {
        rec.layout.push({ tag: name, line, attrs });
      } else if (name === "Label" || name === "label") {
        rec.layout.push({ tag: name, line, attrs: { text: text(), htmlFor: attrs.htmlFor, className: attrs.className } });
      }
    },
  });
  // tanda teks
  rec.flags.placeholderCari = (code.match(/placeholder=\{?["'`][^"'`]*[Cc]ari/g) || []).length;
  rec.flags.exportConfig = (code.match(/exportConfig/g) || []).length;
  rec.flags.toList = undefined;
  rec.flags.lines = code.split("\n").length;
  return rec;
}

main();
