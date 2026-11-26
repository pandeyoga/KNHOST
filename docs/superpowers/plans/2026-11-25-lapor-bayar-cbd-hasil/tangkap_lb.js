// Lapor Bayar CBD — tangkapan sesudah (lingkungan uji lokal, data acuan; BUKAN data nyata).
// Prasyarat: backend :8001 + frontend :3000 menyala; `python siapkan_lb.py` sudah membuat lb_data.json
// (pesanan CBD & DP50 tertahan di "Bayar dicek Finance").
// Alur yang dipotret:
//   1. Sales (desktop) — rincian pesanan CBD: tahap tertahan + Perjalanan; dialog Lapor bayar → kirim.
//   2. Sales (HP) — pesanan DP50: dialog Lapor bayar di HP → kirim.
//   3. Finance — Meja Keuangan: pop-up lapor bayar CBD → Terima → pesanan lepas ke gudang.
//   4. Finance — pop-up lapor bayar DP50 → Tolak (alasan) → notifikasi sales.
//   5. Admin Sales — Pelacak SO tahap pesanan; Faktur Komersial DP50 (masih tertahan) bercap "Belum dibayar".
const { chromium } = require("playwright");
const fs = require("fs");
const { execFileSync } = require("child_process");
const DIR = __dirname;
const OUT = DIR + "/tangkapan";
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const API = "http://localhost:8001/api";
const DATA = JSON.parse(fs.readFileSync(DIR + "/lb_data.json", "utf8"));
const log = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const tid = (p, id) => p.locator(`[data-testid="${id}"]`);
const clean = (p) => p.evaluate(() => document.querySelectorAll("iframe#webpack-dev-server-client-overlay").forEach((e) => e.remove())).catch(() => {});

async function api(email, method, path, body) {
  const t = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "demo12345" }) }).then((r) => r.json());
  const r = await fetch(`${API}${path}`, { method, headers: { Authorization: `Bearer ${t.token}`, "X-Entity-Id": "ent_ksc",
    "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const ct = r.headers.get("content-type") || "";
  return { status: r.status, body: ct.includes("json") ? await r.json() : Buffer.from(await r.arrayBuffer()) };
}
async function login(page, email) {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 90000 });
  await page.fill('[data-testid="login-email-input"]', email);
  await page.fill('[data-testid="login-password-input"]', "demo12345");
  await page.click('[data-testid="login-submit-button"]');
  await sleep(4000);
}
async function shot(page, name, full = false) {
  await clean(page);
  await page.screenshot({ path: `${OUT}/${name}.jpg`, type: "jpeg", quality: 72, fullPage: full });
  log.push(`  potret ${name}.jpg`);
}
async function shotEl(loc, name) {
  await clean(loc.page());
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  await loc.screenshot({ path: `${OUT}/${name}.jpg`, type: "jpeg", quality: 75 });
  log.push(`  potret ${name}.jpg`);
}
async function view(page, v, wait = 6000) {
  await page.goto(`${BASE}/?view=${v}`, { waitUntil: "domcontentloaded" });
  await sleep(wait);
}
async function pilih(page, testId, re) {
  await tid(page, testId).click();
  await sleep(400);
  const opt = page.getByRole("option", { name: re }).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(400);
}
/** Bukti transfer tiruan (gambar PNG dari HTML) — bukan bukti nyata. */
async function buatBukti(browser) {
  const p = await browser.newPage({ viewport: { width: 420, height: 260 } });
  await p.setContent(`<div style="font:15px sans-serif;padding:18px;border:2px solid #1a5fb4;border-radius:10px;margin:10px">
    <b>CONTOH BUKTI TRANSFER (UJI)</b><br>Bank BCA · ${new Date().toISOString().slice(0, 10)}<br>
    Ke: PT Kain Sejahtera Cemerlang<br>Nominal: sesuai pesanan<br><small>Dibuat skrip tangkapan — bukan data nyata</small></div>`);
  const f = `${DIR}/bukti_uji.png`;
  await p.screenshot({ path: f });
  await p.close();
  return f;
}
async function bukaPesanan(page, so) {
  await view(page, "orders", 5000);
  if (await tid(page, "tab-list").count()) { await tid(page, "tab-list").click().catch(() => {}); await sleep(1500); }
  await tid(page, "orders-search-input").fill(so.number);
  await sleep(2500);
  const row = tid(page, `order-card-${so.id}`);
  await row.first().waitFor({ timeout: 20000 });
  await row.first().click();
  await sleep(3500);
}
async function isiLapor(page, bukti, ref) {
  const dlg = page.locator('[role="dialog"]').filter({ has: tid(page, "lapor-bayar-amount") }).first();
  await tid(page, "lapor-bayar-amount").waitFor({ timeout: 15000 });
  const m = await tid(page, "lapor-bayar-method").innerText().catch(() => "");
  if (!/Transfer/i.test(m)) await pilih(page, "lapor-bayar-method", /Transfer/i);
  await sleep(800);
  await tid(page, "lapor-bayar-reference").fill(ref);
  await tid(page, "lapor-bayar-file").setInputFiles(bukti);
  await sleep(800);
  return dlg;
}
async function laporanPesanan(so) {
  const r = await api("finance@kainnusantara.id", "GET", `/sales-orders/${so.id}/payment-reports`);
  return (r.body.items || [])[0];
}
async function bukaBarisMeja(page, repId) {
  const btn = page.locator(`button[data-testid*="-number-"][data-testid*="${repId}"]`).first();
  await btn.waitFor({ timeout: 20000 });
  await btn.scrollIntoViewIfNeeded();
  await btn.click();
  await page.locator('[data-testid$="-payreport-panel"]').first().waitFor({ timeout: 20000 });
  await sleep(2500);
}

(async () => {
  const browser = await chromium.launch();
  const bukti = await buatBukti(browser);
  const { cbd, dp } = DATA;
  log.push(`Pesanan CBD ${cbd.number} (kurang ${cbd.shortfall}), DP50 ${dp.number} (kurang ${dp.shortfall})`);

  // 1. Sales desktop — CBD
  const c1 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const s = await c1.newPage();
  try {
    log.push("1. Sales desktop — rincian pesanan CBD");
    await login(s, "sales@kainnusantara.id");
    await bukaPesanan(s, cbd);
    await shot(s, "01_sales_rincian_cbd_tertahan");
    const gate = tid(s, "so-gate");
    if (await gate.count()) await shotEl(gate, "02_sales_panel_tahap_bayar");
    const jr = tid(s, "order-journey-panel");
    if (await jr.count()) {
      await shotEl(jr, "03_sales_perjalanan_bayar_dicek");
      log.push(`  Perjalanan, tahap kini: ${(await tid(s, "journey-current").innerText().catch(() => "?")).replace(/\s+/g, " ")}`);
    }
    await tid(s, "so-gate-lapor-open").click();
    const dlg = await isiLapor(s, bukti, "TRF-UJI-CBD-01");
    await shotEl(dlg, "04_sales_dialog_lapor_bayar_desktop");
    await tid(s, "lapor-bayar-submit").click();
    await sleep(4000);
    if (await gate.count()) await shotEl(gate, "05_sales_laporan_menunggu");
    const rep = await laporanPesanan(cbd);
    log.push(`  laporan ${rep && rep.number} status ${rep && rep.status}, bukti ${rep && (rep.attachments || []).length}`);
  } catch (e) { log.push(`  GALAT sales desktop: ${e.message.slice(0, 200)}`); await shot(s, "galat_sales_desktop"); }
  await c1.close();

  // 2. Sales HP — DP50
  const c2 = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const h = await c2.newPage();
  try {
    log.push("2. Sales HP — pesanan DP50");
    await login(h, "sales@kainnusantara.id");
    await h.goto(`${BASE}/?m=orders`, { waitUntil: "domcontentloaded" });
    await sleep(6000);
    const card = tid(h, `mobile-order-${dp.id}`);
    await card.waitFor({ timeout: 20000 });
    await card.locator("button").first().click();
    await sleep(2500);
    await shotEl(card, "06_hp_pesanan_dp_tertahan");
    await tid(h, `m-gate-${dp.id}-lapor-open`).click();
    await isiLapor(h, bukti, "TRF-UJI-DP-01");
    await shot(h, "07_hp_dialog_lapor_bayar");
    await tid(h, "lapor-bayar-submit").click();
    await sleep(4000);
    const rep = await laporanPesanan(dp);
    log.push(`  laporan ${rep && rep.number} status ${rep && rep.status}, bukti ${rep && (rep.attachments || []).length}`);
  } catch (e) { log.push(`  GALAT sales HP: ${e.message.slice(0, 200)}`); await shot(h, "galat_sales_hp"); }
  await c2.close();

  // 3–4. Finance — Meja Keuangan: Terima (CBD), Tolak (DP50)
  const c3 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const f = await c3.newPage();
  try {
    log.push("3. Finance — Meja Keuangan, lapor bayar CBD → Terima");
    await login(f, "finance@kainnusantara.id");
    await view(f, "finance-desk", 8000);
    await shot(f, "08_meja_keuangan_antrean");
    const repC = await laporanPesanan(cbd);
    await bukaBarisMeja(f, repC.id);
    await shot(f, "09_meja_keuangan_popup_lapor_bayar");
    await tid(f, `pay-report-${repC.id}-terima`).click();
    await tid(f, "pay-report-confirm").waitFor({ timeout: 10000 });
    await shot(f, "10_meja_keuangan_konfirmasi_terima");
    log.push(`  pesan konfirmasi: ${(await tid(f, "pay-report-confirm-message").innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 220)}`);
    await tid(f, "pay-report-confirm-confirm").click();
    await sleep(5000);
    await shot(f, "11_meja_keuangan_sesudah_terima");
    const so = await api("finance@kainnusantara.id", "GET", `/sales-orders/${cbd.id}`);
    const r2 = await laporanPesanan(cbd);
    log.push(`  sesudah Terima: laporan ${r2.status}, kwitansi ${r2.receipt_number || r2.receipt_id || "-"}; pesanan ${so.body.status}, ` +
      `pay_hold ${so.body.pay_hold ? "masih" : "dibuka"}, bayar ${so.body.payment_status}`);
    await f.keyboard.press("Escape").catch(() => {});

    log.push("4. Finance — lapor bayar DP50 → Tolak");
    await view(f, "finance-desk", 8000);
    const repD = await laporanPesanan(dp);
    await bukaBarisMeja(f, repD.id);
    await shot(f, "12_meja_keuangan_popup_lapor_dp");
    await tid(f, `pay-report-${repD.id}-tolak`).click();
    await tid(f, "pay-report-reason").waitFor({ timeout: 10000 });
    await tid(f, "pay-report-reason-reason").fill("Nominal di bukti tidak sama dengan mutasi rekening BCA hari ini");
    await sleep(500);
    await shot(f, "13_meja_keuangan_tolak_alasan");
    await tid(f, "pay-report-reason-confirm").click();
    await sleep(4000);
    const r3 = await laporanPesanan(dp);
    log.push(`  sesudah Tolak: laporan ${r3.status}, alasan "${r3.reject_reason || r3.reason || ""}"`);
  } catch (e) { log.push(`  GALAT finance: ${e.message.slice(0, 200)}`); await shot(f, "galat_finance"); }
  await c3.close();

  // 4b. Sales — notifikasi tolak + pesanan CBD sudah lepas
  const c4 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const s2 = await c4.newPage();
  try {
    log.push("4b. Sales — notifikasi & pesanan CBD sesudah diterima");
    await login(s2, "sales@kainnusantara.id");
    await tid(s2, "notif-bell").click();
    await tid(s2, "notif-panel").waitFor({ timeout: 10000 });
    await sleep(2000);
    await shotEl(tid(s2, "notif-panel"), "14_sales_notifikasi_ditolak_diterima");
    const teks = (await tid(s2, "notif-panel").innerText()).split("\n").filter((x) => /laporan|lapor|bayar/i.test(x)).slice(0, 6);
    log.push(`  baris notifikasi: ${teks.join(" | ").slice(0, 400)}`);
    await s2.keyboard.press("Escape").catch(() => {});
    await bukaPesanan(s2, cbd);
    await shot(s2, "15_sales_rincian_cbd_sesudah_terima");
    const jr = tid(s2, "order-journey-panel");
    if (await jr.count()) {
      await shotEl(jr, "16_sales_perjalanan_sesudah_terima");
      log.push(`  Perjalanan, tahap kini: ${(await tid(s2, "journey-current").innerText().catch(() => "?")).replace(/\s+/g, " ")}`);
    }
  } catch (e) { log.push(`  GALAT sales notif: ${e.message.slice(0, 200)}`); await shot(s2, "galat_sales_notif"); }
  await c4.close();

  // 5. Admin Sales — Pelacak SO; Faktur Komersial DP50 bercap "Belum dibayar"
  const c5 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const a = await c5.newPage();
  try {
    log.push("5. Admin Sales — Pelacak SO");
    await login(a, "salesadmin@kainnusantara.id");
    await view(a, "sales-admin-desk", 7000);
    await tid(a, "desk-tabs-pantau").click().catch(() => {});
    await sleep(1500);
    await tid(a, "desk-so-tracker-search").fill(dp.number);
    await sleep(2500);
    const row = tid(a, `desk-so-tracker-row-${dp.id}`);
    await row.waitFor({ timeout: 15000 });
    await shot(a, "17_admin_sales_pelacak_dp_bayar_dicek");
    log.push(`  baris pelacak: ${(await row.innerText()).replace(/\s+/g, " ").slice(0, 200)}`);
  } catch (e) { log.push(`  GALAT admin sales: ${e.message.slice(0, 200)}`); await shot(a, "galat_admin_sales"); }
  await c5.close();
  try {
    const pdf = await api("sales@kainnusantara.id", "GET", `/pdf/render/invoice/${dp.id}`);
    log.push(`5b. Faktur Komersial DP50: HTTP ${pdf.status}`);
    if (pdf.status === 200) {
      fs.writeFileSync(`${DIR}/faktur_dp.pdf`, pdf.body);
      execFileSync("pdftoppm", ["-jpeg", "-r", "80", "-f", "1", "-l", "1", "-singlefile", `${DIR}/faktur_dp.pdf`, `${OUT}/18_faktur_komersial_belum_dibayar`]);
      const txt = execFileSync("pdftotext", ["-f", "1", "-l", "1", `${DIR}/faktur_dp.pdf`, "-"]).toString();
      log.push(`  cap/status di PDF: ${/Belum dibayar/i.test(txt) ? "\"Belum dibayar\" ADA" : "TIDAK ditemukan"}`);
      fs.unlinkSync(`${DIR}/faktur_dp.pdf`);
    }
  } catch (e) { log.push(`  GALAT PDF: ${e.message.slice(0, 200)}`); }
  fs.unlinkSync(bukti);
  await browser.close();
  fs.writeFileSync(`${DIR}/tangkap_lb_log.txt`, log.join("\n") + "\n");
  console.log(log.join("\n"));
})();
