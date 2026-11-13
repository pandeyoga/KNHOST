// Uji jalan LAYAR — Pusat Pengaturan dan Peran & Hak Akses, lewat peramban sungguhan.
//
//   node ui_pengaturan_peran.js <folder-tangkapan-layar>
//
// Prasyarat: `python serve_mem.py` (backend :8001, database tiruan) dan frontend `yarn start:dev` di :3000.
// Tiap langkah mencetak satu baris: [OK] / [BEDA] / [GAGAL] + apa yang terlihat di layar dan apa kata API.
const { chromium } = require("playwright");
const fs = require("fs");

const BASE = process.env.KN_FE || "http://localhost:3000";
const API = (process.env.KN_BE || "http://localhost:8001") + "/api";
const SHOTS = process.argv[2] || ".";
const tid = (t) => `[data-testid="${t}"]`;
const KEY = "sales.allow_partial_shipment";
const catatan = [];
const catat = (st, nama, rinci = "") => { catatan.push({ st, nama, rinci }); console.log(`[${st}] ${nama}${rinci ? " — " + rinci : ""}`); };

async function api(token, method, path, body, entity = "ent_ksc") {
  const r = await fetch(API + path, {
    method, headers: { Authorization: `Bearer ${token}`, "X-Entity-Id": entity, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let j = null;
  try { j = await r.json(); } catch (e) { /* kosong */ }
  return { status: r.status, json: j };
}
async function tokenUntuk(email) {
  const r = await fetch(API + "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: "demo12345" }) });
  return (await r.json()).token;
}
async function buka(browser, email) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "id-ID" });
  const page = await ctx.newPage();
  const gagal = [];
  page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) gagal.push(`${r.status()} ${r.request().method()} ${r.url().replace(/^https?:\/\/[^/]+/, "").slice(0, 130)}`); });
  page.on("pageerror", (e) => gagal.push("GALAT-HALAMAN " + String(e).slice(0, 160)));
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(tid("login-email-input"), { timeout: 120000 });
  await page.fill(tid("login-email-input"), email);
  await page.fill(tid("login-password-input"), "demo12345");
  await page.click(tid("login-submit-button"));
  await page.waitForSelector(tid("login-screen"), { state: "detached", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 60000 }).catch(() => {});
  return { ctx, page, gagal };
}
async function ke(page, view) {
  await page.goto(`${BASE}/?view=${view}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(900);
}
async function pilih(page, testId, value, teks) {
  const el = page.locator(tid(testId)).first();
  const tag = await el.evaluate((e) => e.tagName.toLowerCase());
  if (tag === "select") { await el.selectOption(String(value)); return; }
  await el.click();
  const opt = page.locator(tid(`${testId}-option-${value}`));
  if (await opt.count()) { await opt.first().click(); return; }
  await page.locator('[role="option"]', { hasText: teks || String(value) }).first().click();
}
async function cariKartu(page, label, key) {
  await page.fill(tid("cfg-search"), label);
  await page.waitForSelector(tid(`cfg-card-${key}`), { timeout: 15000 });
  await page.locator(tid(`cfg-card-${key}`)).scrollIntoViewIfNeeded();
}
const teks = async (page, t) => (await page.locator(tid(t)).first().innerText().catch(() => "")).replace(/\s+/g, " ").trim();

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch();
  const tokAdmin = await tokenUntuk("admin@kainnusantara.id");
  const reg = (await api(tokAdmin, "GET", "/config/registry")).json;
  const items = reg.items || reg.entries || [];
  const entri = items.find((x) => x.key === KEY);

  // ───────────────────────── A. PUSAT PENGATURAN (Admin) ─────────────────────────
  const A = await buka(browser, "admin@kainnusantara.id");
  let page = A.page;
  await ke(page, "settings-config");
  await page.waitForSelector(tid("settings-hub"));
  const nGrup = await page.locator('[data-testid^="cfg-group-"]:not([data-testid="cfg-group-nav"]):not([data-testid="cfg-group-head"]):not([data-testid="cfg-group-show-all"])').count();
  catat(nGrup === 23 ? "OK" : "BEDA", "A1 Pusat Pengaturan terbuka", `${nGrup} kelompok di layar; registry ${items.length} kunci`);

  try {
    await cariKartu(page, entri.label, KEY);
    const sebelum = await teks(page, `cfg-value-${KEY}`);
    await page.click(tid(`cfg-input-${KEY}`));
    const akan = await teks(page, `cfg-dirty-${KEY}`);
    await page.fill(tid(`cfg-reason-${KEY}`), "uji layar audit");
    await page.screenshot({ path: `${SHOTS}/A2_sebelum_simpan.png` });
    await page.click(tid(`cfg-save-${KEY}`));
    await page.waitForSelector(tid("cfg-notice"), { timeout: 15000 });
    const notis = await teks(page, "cfg-notice");
    await page.waitForTimeout(900);
    const sesudah = await teks(page, `cfg-value-${KEY}`);
    const milik = await teks(page, `cfg-owned-${KEY}`);
    const e1 = (await api(tokAdmin, "GET", `/config/explain?key=${KEY}&entity_id=ent_ksc`)).json;
    const e2 = (await api(tokAdmin, "GET", `/config/explain?key=${KEY}&entity_id=ent_kanda`)).json;
    const okNilai = sebelum !== sesudah && String(e1.value) !== String(e2.value);
    catat(okNilai ? "OK" : "BEDA", "A2 Ubah nilai untuk satu PT lewat layar",
      `layar: "${sebelum}" → "${sesudah}" (${milik}); pemberitahuan: "${notis.slice(0, 90)}"; API PT ini=${e1.value}, PT lain=${e2.value}; teks konfirmasi: "${akan.slice(0, 120)}"`);
    await page.screenshot({ path: `${SHOTS}/A2_sesudah_simpan.png` });

    await ke(page, "settings-config");
    await cariKartu(page, entri.label, KEY);
    const ulang = await teks(page, `cfg-value-${KEY}`);
    catat(ulang === sesudah ? "OK" : "BEDA", "A3 Nilai bertahan setelah halaman dimuat ulang", `"${ulang}"`);

    await page.click(tid(`cfg-hist-${KEY}`));
    await page.waitForTimeout(1200);
    const badan = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    catat(/uji layar audit/.test(badan) ? "OK" : "BEDA", "A4 Riwayat memuat perubahan dan alasannya", /uji layar audit/.test(badan) ? "alasan tampil" : "alasan tidak ditemukan di layar");
    await page.screenshot({ path: `${SHOTS}/A4_riwayat.png` });
    await page.keyboard.press("Escape");
    await ke(page, "settings-config");
    await cariKartu(page, entri.label, KEY);
    page.once("dialog", (d) => d.accept());
    await page.click(tid(`cfg-clear-entity-${KEY}`));
    await page.waitForTimeout(600);
    // dialog konfirmasi buatan aplikasi (bila ada)
    const konf = page.locator('button:has-text("Kembalikan"), button:has-text("Ya"), button:has-text("Lanjut")').last();
    if (await page.locator(".modal-overlay, [role=dialog]").count()) { await konf.click().catch(() => {}); }
    await page.waitForTimeout(1500);
    const pulih = await teks(page, `cfg-value-${KEY}`);
    const e3 = (await api(tokAdmin, "GET", `/config/explain?key=${KEY}&entity_id=ent_ksc`)).json;
    catat(pulih === sebelum && String(e3.value) === String(e2.value) ? "OK" : "BEDA", "A5 Kembalikan ke nilai grup", `layar "${pulih}"; API ${e3.value}`);
  } catch (e) { catat("GAGAL", "A2–A5 ubah pengaturan lewat layar", String(e).slice(0, 220)); await page.screenshot({ path: `${SHOTS}/A_gagal.png` }); }

  // nilai tak sah + wajib alasan
  try {
    const angka = items.find((x) => ["pct", "int"].includes(x.type) && x.max !== null && x.max !== undefined && x.status !== "not_used" && !x.requires_reason && (x.scopes || []).includes("entity"));
    await ke(page, "settings-config");
    await cariKartu(page, angka.label, angka.key);
    await page.fill(tid(`cfg-input-${angka.key}`), String(Number(angka.max) * 10 + 7));
    await page.click(tid(`cfg-save-${angka.key}`));
    await page.waitForSelector(tid("cfg-notice"), { timeout: 15000 });
    const pesan = await teks(page, "cfg-notice");
    const ex = (await api(tokAdmin, "GET", `/config/explain?key=${angka.key}&entity_id=ent_ksc`)).json;
    catat(Number(ex.value) <= Number(angka.max) ? "OK" : "BEDA", "A6 Nilai di luar batas ditolak di layar", `${angka.key} (maks ${angka.max}); pesan: "${pesan.slice(0, 160)}"`);
    await page.screenshot({ path: `${SHOTS}/A6_nilai_tak_sah.png` });
  } catch (e) { catat("GAGAL", "A6 nilai di luar batas", String(e).slice(0, 200)); }
  try {
    const wajib = items.find((x) => x.requires_reason && x.type === "bool" && x.status !== "not_used" && (x.scopes || []).includes("entity"));
    await ke(page, "settings-config");
    await cariKartu(page, wajib.label, wajib.key);
    const seb = (await api(tokAdmin, "GET", `/config/explain?key=${wajib.key}&entity_id=ent_ksc`)).json.value;
    await page.click(tid(`cfg-input-${wajib.key}`));
    await page.click(tid(`cfg-save-${wajib.key}`));
    await page.waitForSelector(tid("cfg-notice"), { timeout: 15000 });
    const pesan = await teks(page, "cfg-notice");
    const ses = (await api(tokAdmin, "GET", `/config/explain?key=${wajib.key}&entity_id=ent_ksc`)).json.value;
    catat(String(seb) === String(ses) ? "OK" : "BEDA", "A7 Pengaturan berisiko tinggi menolak simpan tanpa alasan", `${wajib.key}; pesan: "${pesan.slice(0, 160)}"`);
  } catch (e) { catat("GAGAL", "A7 wajib alasan", String(e).slice(0, 200)); }
  catat(A.gagal.filter((g) => !/ 400 | 422 /.test(` ${g} `)).length === 0 ? "OK" : "BEDA", "A8 Panggilan API gagal selama sesi Admin di Pengaturan (di luar penolakan yang sengaja diuji)", JSON.stringify(A.gagal).slice(0, 400));

  // ───────────────────────── B. PERAN & AKUN (Admin, lewat layar) ─────────────────────────
  const LABEL = "Staf Penagihan Uji";
  try {
    await ke(page, "entities-access");
    await page.click(tid("entities-access-tab-roles"));
    await page.waitForSelector(tid("role-access-panel"));
    await page.click(tid("role-create-button"));
    await page.waitForSelector(tid("role-editor-drawer"));
    await page.fill(tid("role-editor-label"), LABEL);
    await page.fill(tid("role-editor-description"), "Menagih piutang; tidak boleh menyentuh pengaturan");
    for (const [m, l] of [["ar", "manage"], ["customer", "view"], ["approval", "view"]]) {
      await page.locator(tid(`role-level-${m}-${l}`)).scrollIntoViewIfNeeded();
      await page.click(tid(`role-level-${m}-${l}`));
    }
    const ringkas = await teks(page, "role-editor-summary");
    const pratinjau = (await page.locator(tid("role-editor-drawer")).innerText()).split("PRATINJAU MENU")[1]?.replace(/\s+/g, " ").slice(0, 400);
    await page.screenshot({ path: `${SHOTS}/B1_editor_peran.png` });
    await page.click(tid("role-editor-save"));
    await page.waitForSelector(tid("role-editor-confirm"), { timeout: 8000 });
    const konfirm = await teks(page, "role-editor-confirm");
    await page.screenshot({ path: `${SHOTS}/B1_konfirmasi_peran.png` });
    await page.click(tid("role-editor-confirm-save"));
    await page.waitForSelector(tid("role-editor-drawer"), { state: "detached", timeout: 15000 });
    await page.waitForTimeout(1000);
    const roles = (await api(tokAdmin, "GET", "/access/roles")).json;
    const daftar = roles.roles || roles;
    const baru = daftar.find((r) => r.label === LABEL);
    catat(baru ? "OK" : "BEDA", "B1 Buat peran lewat layar", `ringkasan: "${ringkas.slice(0, 120)}"; konfirmasi: "${konfirm.slice(0, 200)}"; tersimpan id=${baru?.id}, peran acuan="${baru?.base_role || ""}"`);
    catat("OK", "B1b Pratinjau menu di editor", pratinjau || "(tidak terbaca)");

    await page.click(tid("entities-access-tab-accounts"));
    await page.waitForSelector(tid("account-add-button"));
    await page.click(tid("account-add-button"));
    await page.waitForSelector(tid("account-form-drawer"));
    await page.fill(tid("account-form-name"), "Rina Penagihan");
    await page.fill(tid("account-form-email"), "rina.uji@kainnusantara.id");
    await page.fill(tid("account-form-password"), "demo12345");
    await pilih(page, "account-form-role", baru.id, LABEL);
    await page.screenshot({ path: `${SHOTS}/B2_form_akun.png` });
    await page.click(tid("account-form-submit"));
    await page.waitForTimeout(2000);
    const galatForm = await teks(page, "account-form-error") || await teks(page, "account-form-errors");
    const users = (await api(tokAdmin, "GET", "/users")).json;
    const u = (users.items || users.users || users).find((x) => x.email === "rina.uji@kainnusantara.id");
    catat(u ? "OK" : "BEDA", "B2 Buat akun lewat layar dengan peran baru", u ? `akun tersimpan, peran=${u.role}, PT asal=${u.home_entity_id}` : `tidak tersimpan; pesan form: "${galatForm.slice(0, 200)}"`);
    if (!u) await page.screenshot({ path: `${SHOTS}/B2_gagal.png` });
  } catch (e) { catat("GAGAL", "B1–B2 peran dan akun lewat layar", String(e).slice(0, 240)); await page.screenshot({ path: `${SHOTS}/B_gagal.png` }); }
  await A.ctx.close();

  // ───────────────────────── C. MASUK SEBAGAI AKUN BERPERAN BARU ─────────────────────────
  try {
    const C = await buka(browser, "rina.uji@kainnusantara.id");
    page = C.page;
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SHOTS}/C1_beranda_peran_baru.png` });
    const mendarat = new URL(page.url()).searchParams.get("view");
    const menu = await page.$$eval("aside a, aside button, nav a, nav button", (els) => [...new Set(els.map((e) => (e.innerText || "").replace(/\s+/g, " ").trim()).filter((t) => t && t.length < 40))]);
    catat("OK", "C1 Masuk sebagai peran baru", `mendarat di "${mendarat}"; menu: ${menu.join(" · ").slice(0, 500)}`);
    // Panggilan milik KERANGKA aplikasi (dipanggil di setiap layar, apa pun perannya) dipisahkan dari milik layar.
    const KERANGKA = /\/api\/(sales\/keep-pending|finance\/posting-failures\/count|hr\/employees\/me)/;
    const kerangka = [...new Set(C.gagal.filter((g) => KERANGKA.test(g)))];
    catat(kerangka.length === 0 ? "OK" : "BEDA", "C2 Kerangka aplikasi memanggil endpoint yang ditolak untuk peran ini", JSON.stringify(kerangka).slice(0, 600));
    const toast = (await page.locator('[role="status"], .toast, [data-sonner-toast]').allInnerTexts().catch(() => [])).join(" | ").slice(0, 200);
    catat(toast ? "BEDA" : "OK", "C2b Pesan galat tampil ke pengguna saat masuk", toast || "tidak ada");
    const uji = [["ar-aging", "boleh"], ["customers-crm", "boleh"], ["approval-inbox", "boleh"], ["settings-config", "tidak"], ["general-ledger", "tidak"], ["entities-access", "tidak"]];
    for (const [v, harap] of uji) {
      const n0 = C.gagal.length;
      await ke(page, v);
      const aktif = new URL(page.url()).searchParams.get("view");
      const isi = (await page.locator("main, #root").first().innerText()).replace(/\s+/g, " ").slice(0, 160);
      const g = C.gagal.slice(n0).filter((x) => !KERANGKA.test(x));
      await page.screenshot({ path: `${SHOTS}/C3_${v}.png` });
      const cocok = harap === "boleh" ? (aktif === v && g.length === 0) : (aktif !== v || /tidak (punya|memiliki|berhak)|akses/i.test(isi));
      const peringatan = (await page.locator('.notice-bar, [class*="notice"], [role="alert"]').allInnerTexts().catch(() => [])).join(" | ").replace(/\s+/g, " ").slice(0, 220);
      catat(cocok ? "OK" : "BEDA", `C3 Buka layar "${v}" (diharapkan ${harap})`, `layar aktif="${aktif}"; API gagal milik layar: ${JSON.stringify(g).slice(0, 300)}; peringatan di layar: "${peringatan}"`);
    }
    await C.ctx.close();
  } catch (e) { catat("GAGAL", "C masuk sebagai peran baru", String(e).slice(0, 240)); }

  // ───────────────────────── D. IZIN "KELOLA PENGATURAN" DI LAYAR (KF-01) ─────────────────────────
  try {
    const mods = (await api(tokAdmin, "GET", "/access/modules")).json;
    const modIds = (mods.modules || mods).map((m) => m.id);
    const levels = Object.fromEntries(modIds.map((m) => [m, "none"]));
    levels.admin = "manage";
    const r = await api(tokAdmin, "POST", "/access/roles", { label: "Pengelola Pengaturan Uji", base_role: "", levels, description: "uji layar" });
    const rid = (r.json.role || r.json).id;
    const ru = await api(tokAdmin, "POST", "/users", { name: "Dodi Pengaturan", email: "dodi.uji@kainnusantara.id", password: "demo12345", role: rid, home_entity_id: "ent_ksc", allowed_entity_ids: ["ent_ksc"] });
    if (ru.status >= 400) throw new Error("buat akun uji gagal: " + JSON.stringify(ru.json).slice(0, 200));
    const D = await buka(browser, "dodi.uji@kainnusantara.id");
    page = D.page;
    await ke(page, "settings-config");
    await page.waitForSelector(tid("settings-hub"), { timeout: 20000 });
    await page.click(tid("cfg-group-show-all")).catch(() => {});
    await page.waitForTimeout(1500);
    const bisa = await page.locator('[data-testid^="cfg-save-"]').count();
    const kunci = await page.locator('[data-testid^="cfg-readonly-"]').count();
    const hak = await teks(page, "cfg-limited-rights");
    const baca = await page.locator('[data-testid^="cfg-readonly-"]').first().innerText().catch(() => "");
    await page.screenshot({ path: `${SHOTS}/D1_pengelola_pengaturan.png`, fullPage: false });
    catat(bisa > 0 ? "OK" : "BEDA", "D1 Peran berizin 'kelola pengaturan' membuka Pusat Pengaturan", `kartu bisa disimpan di kelompok pertama: ${bisa}; kartu terkunci: ${kunci}; pemberitahuan: "${hak.slice(0, 200)}"; teks kartu terkunci: "${baca.replace(/\s+/g, " ").slice(0, 160)}"`);
    await D.ctx.close();
  } catch (e) { catat("GAGAL", "D izin kelola pengaturan di layar", String(e).slice(0, 240)); }

  await browser.close();
  fs.writeFileSync(`${SHOTS}/hasil.json`, JSON.stringify(catatan, null, 1));
  const n = (s) => catatan.filter((c) => c.st === s).length;
  console.log(`\nRingkas: ${n("OK")} OK · ${n("BEDA")} berbeda dari harapan · ${n("GAGAL")} langkah gagal dijalankan`);
})();
