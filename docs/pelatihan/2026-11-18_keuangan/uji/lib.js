// Pembantu uji jalan (Playwright) — Pelatihan Keuangan 18 Nov 2026.
//
// Setiap skenario = satu berkas `Fxx_*.js` yang memakai `Run`: login lewat LAYAR dengan akun peran, klik tombol yang sama
// dengan yang dipakai peserta, lalu mencocokkan hasil di LAYAR dan di BUKU (API: jurnal seimbang, saldo, status).
// Hasil per langkah ditulis ke `hasil/<kode>/hasil.json` + tangkapan layar `hasil/<kode>/*.png`.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/F01_beranda.js
//   KN_BASE=http://localhost:3000 KN_API=http://localhost:8001/api node …   (bawaan = lingkungan lokal)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.KN_BASE || "http://localhost:3000";
const API = process.env.KN_API || "http://localhost:8001/api";
const PASS = process.env.KN_PASS || "demo12345";
const OUT = process.env.KN_OUT || path.join(__dirname, "hasil");
const MAIL = "@kainnusantara.id";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const email = (k) => (k.includes("@") ? k : k + MAIL);
const rp = (n) => "Rp " + Math.round(Number(n || 0)).toLocaleString("id-ID");
const num = (s) => Number(String(s || "").replace(/[^0-9,-]/g, "").replace(/\./g, "").replace(",", ".")) || 0;

class ApiSession {
  constructor(token, user) { this.token = token; this.user = user; }
  async call(method, p, body, entity) {
    const headers = { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" };
    if (entity) headers["X-Entity-Id"] = entity;
    const r = await fetch(API + p, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    const txt = await r.text();
    let data; try { data = txt ? JSON.parse(txt) : {}; } catch { data = txt; }
    if (!r.ok) {
      const e = new Error(`${method} ${p} → ${r.status}: ${JSON.stringify(data && data.detail !== undefined ? data.detail : data).slice(0, 400)}`);
      e.status = r.status; e.detail = data && data.detail; throw e;
    }
    return data;
  }
  get(p, entity) { return this.call("GET", p, undefined, entity); }
  post(p, body = {}, entity) { return this.call("POST", p, body, entity); }
  patch(p, body = {}, entity) { return this.call("PATCH", p, body, entity); }
}

const _tok = {};
async function api(key) {
  const em = email(key);
  if (_tok[em]) return _tok[em];
  const r = await fetch(API + "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: em, password: PASS }) });
  const d = await r.json();
  if (!r.ok) throw new Error(`login API ${em} → ${r.status}: ${JSON.stringify(d).slice(0, 200)}`);
  _tok[em] = new ApiSession(d.token, d.user);
  return _tok[em];
}

class Run {
  constructor(code, title) {
    this.code = code; this.title = title; this.steps = []; this.httpErr = []; this.consoleErr = []; this.notes = [];
    this.dir = path.join(OUT, code); fs.mkdirSync(this.dir, { recursive: true });
    this.n = 0; this.who = "";
  }

  async start({ width = 1366, height = 900, scale = 1 } = {}) {
    this.browser = await chromium.launch({ args: ["--no-proxy-server"] });
    this.ctx = await this.browser.newContext({ viewport: { width, height }, deviceScaleFactor: scale, locale: "id-ID",
      timezoneId: "Asia/Jakarta" });
    this.page = await this.ctx.newPage();
    this.page.setDefaultTimeout(15000);
    this.page.on("response", (res) => {
      const u = res.url();
      if (u.includes("/api/") && res.status() >= 500) this.httpErr.push(`${res.status()} ${res.request().method()} ${u.replace(/^.*\/api/, "/api")}`);
    });
    this.page.on("pageerror", (e) => this.consoleErr.push(String(e.message || e).slice(0, 300)));
    this.page.on("console", (m) => {
      if (m.type() === "error" && !/favicon|ResizeObserver|Download the React DevTools|net::ERR_ABORTED/.test(m.text()))
        this.consoleErr.push(m.text().slice(0, 300));
    });
    return this;
  }

  async login(key) {
    const p = this.page;
    await this.ctx.clearCookies();
    await p.goto(BASE + "/");
    await p.evaluate(() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) { /* abaikan */ } });
    await p.goto(BASE + "/");
    await p.getByTestId("login-email-input").fill(email(key));
    await p.getByTestId("login-password-input").fill(PASS);
    await p.getByTestId("login-submit-button").click();
    await p.waitForFunction(() => !document.querySelector('[data-testid="login-submit-button"]'), null, { timeout: 20000 });
    await this.idle();
    this.who = email(key);
  }

  async go(view, extra = "") {
    await this.page.goto(`${BASE}/?view=${view}${extra}`);
    await this.idle();
  }

  async idle(ms = 600) {
    try { await this.page.waitForLoadState("networkidle", { timeout: 12000 }); } catch (e) { /* layar polling */ }
    await sleep(ms);
  }

  tid(id) { return this.page.getByTestId(id); }

  async text(id) { return (await this.tid(id).first().innerText()).replace(/\s+/g, " ").trim(); }

  async shot(name, opts = {}) {
    const f = path.join(this.dir, `${String(++this.n).padStart(2, "0")}-${name}.png`);
    if (opts.locator) await opts.locator.screenshot({ path: f });
    else await this.page.screenshot({ path: f, fullPage: !!opts.full });
    return f;
  }

  // Satu langkah pelatihan: nomor, peran, apa yang dilakukan, hasil yang harus terlihat. Gagal = dicatat + potret.
  async step(no, role, action, expect, fn) {
    const t0 = Date.now();
    const row = { no, role, action, expect, ok: false, ms: 0, info: "" };
    try {
      const info = await fn();
      row.ok = true; row.info = info === undefined ? "" : String(info);
    } catch (e) {
      row.info = String(e && e.message ? e.message : e).split("\n")[0].slice(0, 500);
      try { row.shot = await this.shot(`GAGAL-${no}`); } catch (_) { /* abaikan */ }
    }
    row.ms = Date.now() - t0;
    this.steps.push(row);
    console.log(`${row.ok ? "✓" : "✗"} ${this.code}.${no} [${role}] ${action}${row.info ? " — " + row.info : ""}`);
    return row.ok;
  }

  note(s) { this.notes.push(s); console.log("  · " + s); }

  async finish() {
    const ok = this.steps.length > 0 && this.steps.every((s) => s.ok) && this.httpErr.length === 0;
    const out = { code: this.code, title: this.title, ok, at: new Date().toISOString(), base: BASE,
      steps: this.steps, http_5xx: this.httpErr, console_errors: [...new Set(this.consoleErr)].slice(0, 30), notes: this.notes };
    fs.writeFileSync(path.join(this.dir, "hasil.json"), JSON.stringify(out, null, 2));
    console.log(`${ok ? "LULUS" : "GAGAL"} ${this.code} — ${this.steps.filter((s) => s.ok).length}/${this.steps.length} langkah` +
      (this.httpErr.length ? ` · ${this.httpErr.length} galat 5xx` : ""));
    if (this.browser) await this.browser.close();
    process.exitCode = ok ? 0 : 1;
    return ok;
  }
}

function assert(cond, msg) { if (!cond) throw new Error(msg); }

// Kartu Peserta (hasil `seed_pelatihan_keuangan_kn.py`) — dibaca langsung dari Mongo lokal (uji hanya di lingkungan lokal).
// kartu("02") → { "a_dasar:so_lunas": { so, so_id, total, … }, … }
function kartu(no) {
  const { execFileSync } = require("child_process");
  const kode = String(no).padStart(2, "0");
  const out = execFileSync("docker", ["exec", "kn-mongo", "mongosh", "--quiet", process.env.KN_DB || "test_database", "--eval",
    `JSON.stringify(((db.migrations.findOne({id:"pelatihan_keuangan"})||{}).peserta||{})["${kode}"]||{})`]).toString();
  return JSON.parse(out.trim() || "{}");
}

// Nomor peserta untuk uji: KN_PESERTA=07 node Fxx.js (bawaan per berkas).
const peserta = (def) => String(process.env.KN_PESERTA || def).padStart(2, "0");
const akunPeserta = (no) => `finance.latih${String(no).padStart(2, "0")}`;

// Sumber `mongosh` untuk cek buku langsung (jurnal seimbang, saldo) bila API tidak menyediakan.
function mongo(js) {
  const { execFileSync } = require("child_process");
  return JSON.parse(execFileSync("docker", ["exec", "kn-mongo", "mongosh", "--quiet", process.env.KN_DB || "test_database",
    "--eval", `JSON.stringify((()=>{${js}})())`]).toString().trim() || "null");
}

module.exports = { Run, api, assert, sleep, rp, num, email, kartu, peserta, akunPeserta, mongo, BASE, API };
