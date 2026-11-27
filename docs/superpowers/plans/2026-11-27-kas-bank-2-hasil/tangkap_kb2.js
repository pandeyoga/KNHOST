// Kas & Bank bagian 2 (C5 kategori kas manual + C6 kas keluar besar butuh orang kedua) — tangkapan sesudah (lingkungan
// uji lokal, data acuan; BUKAN data nyata). Prasyarat: backend :8001 + frontend :3000 menyala pada cabang, DB
// `test_database` berisi data acuan (`bash scripts/dev_restore_demo.sh`). Tanpa skrip penyiapan: semua data dibuat di
// sini (lewat layar, atau lewat API akun peran bila layarnya sudah dipotret).
//
// Akun: PENGAJU Finance `finance@` (Sri Mulyani — cash.view/create/approve/delete) · PENYETUJU Manajer `manager@`
// (Dewi Manager — cash.view/create/approve/delete). Admin tidak dipakai sebagai pengaju (kontrol.admin_tetap_dua_orang).
// PT Sukacita Textile (KSC, `ent_ksc`); batas bawaan Rp 1.000.000.
//
// Fase (berurutan; `node tangkap_kb2.js <fase…>`, tanpa argumen = semua):
//   k1   Pengaju — Transaksi Kas › Catat Transaksi: daftar kategori (tanpa Pembelian/Gaji); API kategori pembelian → 400.
//   k2   Pengaju — kas keluar Rp 1.000.000 → langsung tercatat (200, baris kas) — batas sendiri bukan "di atas".
//   k3   Pengaju — kas keluar Rp 2.500.000 → catatan "Di atas…" + Ajukan → 202, toast, baris menunggu, tanpa kas.
//   k4   Pengaju — Setujui/Tolak mati berkalimat, Batal aktif; pratinjau PKK; dua pengajuan lagi (API) untuk Tolak/Batal.
//   k5   Penyetuju — lonceng, Pusat Persetujuan (antrean) → Transaksi Kas → Setujui (konfirmasi) → kas terbit + pratinjau.
//   k6   Penyetuju — Tolak beralasan (pop-up kosong: tombol mati) → ditolak.
//   k7   Pengaju — lonceng (disetujui & ditolak + alasan) → pratinjau ditolak; Batal pengajuan ketiga.
//   k8   Opsional — kartu Asisten `cash_manual` di atas batas → "Diajukan — menunggu persetujuan kas keluar PKK-…".
//   cek  API saja — ringkasan akhir (status pengajuan, kas, saldo, jurnal, pemberitahuan).
//   pulih  Kembalikan pengaturan yang diubah k8 (ai.*, ai_finance pengguna) ke keadaan sebelum.
const { chromium } = require("playwright");
const fs = require("fs");
const DIR = __dirname;
const OUT = DIR + "/tangkapan";
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const API = "http://localhost:8001/api";
const ENT = "ent_ksc";
const ADMIN = "admin@kainnusantara.id", AJU = "finance@kainnusantara.id", SETUJU = "manager@kainnusantara.id";
const LOGF = DIR + "/tangkap_kb2_log.txt";
const DATAF = DIR + "/kb2_data.json";
const C5 = "Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual: pembelian barang lewat PO/tagihan pemasok, " +
  "gaji lewat Proses Gaji. Belanja kecil kebutuhan kantor pakai kategori Operasional.";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const tid = (p, id) => p.locator(`[data-testid="${id}"]`);
const clean = (p) => p.evaluate(() => document.querySelectorAll("iframe#webpack-dev-server-client-overlay").forEach((e) => e.remove())).catch(() => {});
const rp = (x) => "Rp " + Number(x || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const satu = (s) => String(s || "").replace(/\s+/g, " ").trim();
function log(s) { console.log(s); fs.appendFileSync(LOGF, s + "\n"); }
const muat = () => (fs.existsSync(DATAF) ? JSON.parse(fs.readFileSync(DATAF, "utf8")) : {});
const simpan = (patch) => { const d = { ...muat(), ...patch }; fs.writeFileSync(DATAF, JSON.stringify(d, null, 2)); return d; };

// ── API ────────────────────────────────────────────────────────────────────────────────────────────────────────────
const TOK = {};
async function api(email, method, path, body, extra = {}) {
  if (!TOK[email]) {
    const t = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: "demo12345" }) }).then((r) => r.json());
    TOK[email] = t.token;
  }
  const r = await fetch(`${API}${path}`, { method, headers: { Authorization: `Bearer ${TOK[email]}`, "X-Entity-Id": ENT,
    "Content-Type": "application/json", ...extra }, body: body ? JSON.stringify(body) : undefined });
  const ct = r.headers.get("content-type") || "";
  return { status: r.status, body: ct.includes("json") ? await r.json() : await r.text() };
}
const rekening = async () => (await api(ADMIN, "GET", `/bank-accounts?entity_id=${ENT}`)).body;
const bca = async () => (await rekening()).find((a) => a.cash_type === "kas_besar");
async function kasKsc() {
  const r = await api(ADMIN, "GET", `/cash-transactions?entity_id=${ENT}&page=1&page_size=200`);
  return r.body.items || [];
}
async function saldo() {
  const s = (await api(ADMIN, "GET", `/cash-transactions/summary?entity_id=${ENT}`)).body;
  const b = await bca();
  const led = (await api(ADMIN, "GET", `/bank-accounts/${b.id}/ledger`)).body;
  const gl = (await api(ADMIN, "GET", `/gl/accounts/1-1100/ledger?entity_id=${ENT}`)).body;
  const kas = await kasKsc();
  return { kas_besar: s.kas_besar.balance, kas_besar_out: s.kas_besar.out, kas_total: s.counts.all,
    buku_bca: led.balance, bca_txn: led.txn_count, gl_1100: gl.balance, kas_n: kas.length,
    jurnal_n: await jumlahJurnal() };
}
async function jumlahJurnal() {
  const { execFileSync } = require("child_process");
  const py = `from pymongo import MongoClient\ndb=MongoClient()["test_database"]\nprint(db.journal_entries.count_documents({"entity_id": "${ENT}"}))`;
  return Number(execFileSync("python3", ["-c", py]).toString().trim());
}
const ringSaldo = (s) => `Kas Besar (ringkasan) ${rp(s.kas_besar)} (keluar ${rp(s.kas_besar_out)}), buku BCA ${rp(s.buku_bca)} ` +
  `(${s.bca_txn} transaksi), akun 1-1100 ${rp(s.gl_1100)}, kas PT ${s.kas_n} baris, jurnal PT ${s.jurnal_n}`;
async function pengajuan(id) { return (await api(ADMIN, "GET", `/cash-out-requests/${id}`)).body; }
async function jurnal(id) {
  const j = (await api(ADMIN, "GET", `/gl/journal/${id}`)).body;
  const baris = (j.lines || []).map((l) => `${l.account_code} ${l.debit ? "D " + rp(l.debit) : "K " + rp(l.credit)}`).join(" / ");
  return `${j.number || id} (${j.status || ""}) tgl ${String(j.date || j.entry_date || "").slice(0, 10)} [${baris}]`;
}
async function notif(email, nomor) {
  const r = await api(email, "GET", "/notifications?limit=50");
  const rows = Array.isArray(r.body) ? r.body : r.body.items || [];
  return rows.filter((n) => /kas_keluar/.test(n.type || "") && (!nomor || (n.title || "").includes(nomor)));
}

// ── Layar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async function login(page, email) {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 120000 });
  await page.fill('[data-testid="login-email-input"]', email);
  await page.fill('[data-testid="login-password-input"]', "demo12345");
  await page.click('[data-testid="login-submit-button"]');
  await sleep(4500);
}
async function view(page, v, wait = 6500) {
  await page.goto(`${BASE}/?view=${v}&entity=${ENT}`, { waitUntil: "domcontentloaded" });
  await sleep(wait);
  await clean(page);
}
async function shot(page, name, full = false) {
  await clean(page);
  await sleep(400);
  await page.screenshot({ path: `${OUT}/${name}.jpg`, type: "jpeg", quality: 80, fullPage: full });
  log(`  potret ${name}.jpg`);
}
async function shotEl(loc, name) {
  await clean(loc.page());
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  await sleep(400);
  await loc.screenshot({ path: `${OUT}/${name}.jpg`, type: "jpeg", quality: 80 });
  log(`  potret ${name}.jpg`);
}
async function pilihNilai(page, testId, value) {
  await tid(page, testId).click();
  await sleep(500);
  const opt = tid(page, `${testId}-option-${value}`).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(500);
}
async function ukurBungkus(loc) {
  return loc.evaluate((el) => {
    const r = el.getBoundingClientRect();
    let w = el.parentElement;
    while (w && !/(auto|scroll)/.test(getComputedStyle(w).overflowX)) w = w.parentElement;
    return `span ${Math.round(r.width)}×${Math.round(r.height)} px (white-space ${getComputedStyle(el).whiteSpace}), ` +
      `tabel ${w ? w.scrollWidth : "?"} px dalam wadah ${w ? w.clientWidth : "?"} px` +
      `${w && w.scrollWidth > w.clientWidth ? " — MELEBAR" : " — muat"}`;
  }).catch((e) => `ukur gagal: ${e.message.slice(0, 80)}`);
}
async function teks(loc) { return satu(await loc.innerText().catch(() => "")); }
async function konteks(browser) {
  return browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
}
/** Form Catat Transaksi: Kas Besar / Bank, Keluar, nominal, kategori Operasional, keterangan. */
async function isiForm(p, nominal, ket) {
  await tid(p, "create-cash-button").click();
  await tid(p, "cash-form").waitFor({ timeout: 10000 });
  await sleep(1500);
  await pilihNilai(p, "cash-type-select", "kas_besar");
  await pilihNilai(p, "cash-direction-select", "out");
  await tid(p, "cash-amount-input").fill(String(nominal));
  await tid(p, "cash-description-input").fill(ket);
  await sleep(1500);
}
async function kirimForm(p) {
  const tunggu = p.waitForResponse((r) => r.url().endsWith("/api/cash-transactions") && r.request().method() === "POST",
    { timeout: 30000 });
  await tid(p, "submit-cash-button").click();
  const r = await tunggu;
  let body = {};
  try { body = await r.json(); } catch (e) { /* bukan json */ }
  return { status: r.status(), body };
}
/** Toast (Radix) — teks yang sedang tampil. */
async function toastTeks(p, pola) {
  const t = p.locator("li[role='status'], [data-state='open'][data-swipe-direction]").filter({ hasText: pola }).first();
  await t.waitFor({ timeout: 10000 }).catch(() => {});
  return teks(t);
}

// ═══ k1 — kategori ════════════════════════════════════════════════════════════════════════════════════════════════
async function k1(browser) {
  const s0 = await saldo();
  log(`[API] keadaan awal PT KSC: ${ringSaldo(s0)}`);
  const batas = await api(AJU, "GET", `/cash-out-requests/batas?entity_id=${ENT}`);
  log(`[API] GET /cash-out-requests/batas (pengaju): HTTP ${batas.status} ${JSON.stringify(batas.body)}`);
  const ada = (await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}`)).body;
  simpan({ saldo_awal: s0, pengajuan_awal: ada.total });
  log(`[API] pengajuan PT KSC yang sudah ada (data acuan): ${ada.items.map((x) => `${x.number} ${x.status} ${rp(x.amount)} "${x.description}" oleh ${x.pengaju.name}`).join("; ") || "-"}`);
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, AJU);
  log("K1 Pengaju (finance@) — Kas & Bank › Transaksi Kas › Catat Transaksi: buka daftar Kategori");
  await view(p, "cash-management", 7000);
  await shot(p, "01_kas_transaksi_kas_awal");
  await tid(p, "create-cash-button").click();
  await tid(p, "cash-form").waitFor({ timeout: 10000 });
  await sleep(1200);
  await tid(p, "cash-category-select").click();
  await sleep(900);
  await shot(p, "02_kas_form_kategori_tanpa_pembelian_gaji");
  const opsi = (await p.locator('[data-testid^="cash-category-select-option-"]').allInnerTexts()).map(satu);
  log(`  kategori di form: ${opsi.join(" · ")} — Pembelian ${opsi.some((o) => /pembelian/i.test(o)) ? "MASIH ADA" : "tidak ada"}, ` +
    `Gaji ${opsi.some((o) => /gaji/i.test(o)) ? "MASIH ADA" : "tidak ada"}, Transfer ${opsi.some((o) => /transfer/i.test(o)) ? "MASIH ADA" : "tidak ada"}`);
  await p.keyboard.press("Escape");
  await sleep(500);
  await c.close();

  const rek = await bca();
  for (const [kat, arah] of [["pembelian", "out"], ["gaji", "out"], ["Beli kain", "out"], ["pembelian", "in"]]) {
    const r = await api(AJU, "POST", "/cash-transactions", { cash_type: "kas_besar", direction: arah, amount: 50000,
      category: kat, description: `Uji C5 kategori ${kat}`, account_id: rek.id, entity_id: ENT },
    { "Idempotency-Key": `uji-kb2-c5-${kat}-${arah}-${Date.now()}` });
    const d = typeof r.body === "object" ? r.body.detail : r.body;
    log(`  [API] POST /cash-transactions kategori "${kat}" arah ${arah} Rp 50.000: HTTP ${r.status} "${d}" — ` +
      `${r.status === 400 && d === C5 ? "kalimat C5 persis" : "TIDAK SESUAI kalimat C5"}`);
  }
  const s1 = await saldo();
  log(`  [API] sesudah uji kategori: ${ringSaldo(s1)} — kas baru ${s1.kas_n - s0.kas_n}, jurnal baru ${s1.jurnal_n - s0.jurnal_n}`);
}

// ═══ k2 — Rp 1.000.000 langsung tercatat ═════════════════════════════════════════════════════════════════════════
async function k2(browser) {
  const s0 = await saldo();
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, AJU);
  log("K2 Pengaju — kas keluar Kas Besar / Bank Rp 1.000.000 (sama dengan batas) → langsung tercatat");
  await view(p, "cash-management", 7000);
  await isiForm(p, 1000000, "Servis AC ruang kantor");
  log(`  rekening terisi: "${await teks(tid(p, "cash-account"))}"`);
  log(`  catatan pengajuan: ${await tid(p, "cash-approval-note").count() ? `"${await teks(tid(p, "cash-approval-note"))}"` : "tidak ada"}; ` +
    `tombol kirim "${await teks(tid(p, "submit-cash-button"))}"`);
  await shot(p, "03_kas_form_1jt_tanpa_catatan_catat_transaksi");
  const r = await kirimForm(p);
  await sleep(3500);
  log(`  [API] jawaban POST /cash-transactions: HTTP ${r.status} ${r.body.number || ""} ${rp(r.body.amount)} ${r.body.direction || ""} ` +
    `ref_type ${r.body.ref_type} gl_status ${r.body.gl_status} jurnal ${r.body.journal_entry_id || "-"}${r.body.request ? " — PENGAJUAN (salah)" : ""}`);
  log(`  bilah: "${await teks(tid(p, "cash-notice"))}"`);
  if (r.body.id) {
    const row = tid(p, `cash-row-${r.body.id}`);
    await row.scrollIntoViewIfNeeded().catch(() => {});
    log(`  baris kas di daftar: ${(await teks(row)).slice(0, 200)}`);
  }
  await p.evaluate(() => window.scrollTo(0, 0));
  await sleep(600);
  await shot(p, "04_kas_1jt_tercatat_langsung", true);
  const s1 = await saldo();
  log(`  [API] sesudah: ${ringSaldo(s1)} — kas baru ${s1.kas_n - s0.kas_n}, Kas Besar turun ${rp(s0.kas_besar - s1.kas_besar)}, ` +
    `1-1100 turun ${rp(s0.gl_1100 - s1.gl_1100)}, jurnal baru ${s1.jurnal_n - s0.jurnal_n}; pengajuan baru ` +
    `${(await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}`)).body.total - (muat().pengajuan_awal || 0)}`);
  if (r.body.journal_entry_id) log(`  [API] jurnal kas 1 juta: ${await jurnal(r.body.journal_entry_id)}`);
  simpan({ kas_1jt: { id: r.body.id, number: r.body.number, status: r.status } });
  await c.close();
}

// ═══ k3 — Rp 2.500.000 → pengajuan ═══════════════════════════════════════════════════════════════════════════════
async function k3(browser) {
  const s0 = await saldo();
  const n0 = (await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}`)).body.total;
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, AJU);
  log("K3 Pengaju — kas keluar Kas Besar / Bank Rp 2.500.000 (di atas batas) → Ajukan");
  await view(p, "cash-management", 7000);
  await isiForm(p, 2500000, "Sewa tenda acara");
  log(`  catatan pengajuan: "${await teks(tid(p, "cash-approval-note"))}"; tombol kirim "${await teks(tid(p, "submit-cash-button"))}"`);
  await shot(p, "05_kas_form_2_5jt_catatan_di_atas_batas_ajukan");
  const r = await kirimForm(p);
  const tt = await toastTeks(p, /Diajukan/);
  await shot(p, "06_kas_ajukan_toast");
  log(`  toast: "${tt}"`);
  const q = r.body.request || {};
  log(`  [API] jawaban POST /cash-transactions: HTTP ${r.status}, request ${q.number} (${q.id}) status ${q.status} ` +
    `${rp(q.amount)} rekening ${q.account_name} kategori ${q.category} "${q.description}" pengaju ${q.pengaju && q.pengaju.name}; ` +
    `kas di jawaban: ${r.body.number ? r.body.number + " (SALAH)" : "tidak ada"}`);
  await sleep(2500);
  const sec = tid(p, "cash-out-pending");
  await sec.waitFor({ timeout: 15000 });
  log(`  bagian "${await teks(tid(p, "cash-out-pending-title"))}" jumlah ${await teks(tid(p, "cash-out-pending-count"))}; ` +
    `baris ${q.number}: ${(await teks(tid(p, `cash-out-row-${q.id}`))).slice(0, 300)}`);
  log(`  baris disorot: ${await tid(p, `cash-out-row-${q.id}`).evaluate((e) => e.className).catch(() => "?")}`);
  await p.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);
  await shot(p, "07_kas_bagian_menunggu_persetujuan", true);
  const s1 = await saldo();
  const n1 = (await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}`)).body.total;
  log(`  [API] sesudah: ${ringSaldo(s1)} — kas baru ${s1.kas_n - s0.kas_n}, Kas Besar berubah ${rp(s1.kas_besar - s0.kas_besar)}, ` +
    `buku BCA berubah ${rp(s1.buku_bca - s0.buku_bca)}, 1-1100 berubah ${rp(s1.gl_1100 - s0.gl_1100)}, jurnal baru ${s1.jurnal_n - s0.jurnal_n}; ` +
    `pengajuan PT ${n0} → ${n1}`);
  const db = (await pengajuan(q.id));
  log(`  [API] GET /cash-out-requests/${q.id}: status ${db.status} (${db.status_label}), kas ${JSON.stringify(db.kas)}, ` +
    `txn_date ${db.txn_date}, jejak ${(db.jejak || []).map((j) => `${j.aksi} ${j.oleh}`).join(", ")}`);
  simpan({ A: { id: q.id, number: q.number, amount: q.amount }, saldo_sebelum_setuju: s1 });
  await c.close();
}

// ═══ k4 — tampilan pengaju + pratinjau; dua pengajuan lagi ═══════════════════════════════════════════════════════
async function k4(browser) {
  const { A } = muat();
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, AJU);
  log(`K4 Pengaju — bagian menunggu: Setujui/Tolak ${A.number} mati untuk pengaju`);
  await view(p, "cash-management", 7000);
  const row = tid(p, `cash-out-row-${A.id}`);
  await row.waitFor({ timeout: 15000 });
  log(`  Setujui nonaktif ${await tid(p, `cash-out-approve-${A.id}`).isDisabled().catch(() => "?")} (title "${await tid(p, `cash-out-approve-${A.id}`).getAttribute("title").catch(() => "")}"); ` +
    `Tolak nonaktif ${await tid(p, `cash-out-reject-${A.id}`).isDisabled().catch(() => "?")} (title "${await tid(p, `cash-out-reject-${A.id}`).getAttribute("title").catch(() => "")}"); ` +
    `Batal nonaktif ${await tid(p, `cash-out-cancel-${A.id}`).isDisabled().catch(() => "?")}`);
  log(`  catatan di sel aksi: "${await teks(tid(p, `cash-out-action-note-${A.id}`))}"`);
  log(`  tata letak catatan: ${await ukurBungkus(tid(p, `cash-out-action-note-${A.id}`))}`);
  await shotEl(tid(p, "cash-out-pending"), "08_kas_pengaju_setujui_tolak_mati_berkalimat");
  log(`K4 Pengaju — klik nomor ${A.number} → pratinjau pengajuan`);
  await tid(p, `cash-out-open-${A.id}`).click();
  await tid(p, "doc-preview-cash-out-request").waitFor({ timeout: 15000 });
  await sleep(2500);
  await shot(p, "09_kas_pratinjau_pkk_menunggu");
  log(`  pratinjau: judul "${await teks(tid(p, "doc-preview-title"))}"; status "${await teks(tid(p, "doc-preview-status"))}"; ` +
    `fakta "${(await teks(tid(p, "doc-preview-cor-facts"))).slice(0, 400)}"`);
  log(`  kontrol: "${await teks(tid(p, "doc-preview-cor-control"))}"; kas: "${await teks(tid(p, "doc-preview-cor-cash-empty"))}"`);
  log(`  riwayat: "${await teks(tid(p, "doc-preview-cor-history"))}"; kaki: Jejak ${await tid(p, "doc-preview-trace").count()}, ` +
    `Buka layar penuh ${await tid(p, "doc-preview-full").count()}`);
  await p.keyboard.press("Escape");
  await sleep(800);
  await c.close();

  log("K4 Pengaju — dua pengajuan lagi lewat API (untuk Tolak & Batal; form sudah dipotret di K3)");
  const rek = await bca();
  const out = {};
  for (const [k, nom, ket] of [["B", 1800000, "Konsumsi rapat"], ["C", 1500000, "Cetak spanduk promo"]]) {
    const r = await api(AJU, "POST", "/cash-transactions", { cash_type: "kas_besar", direction: "out", amount: nom,
      category: "operasional", description: ket, account_id: rek.id }, { "Idempotency-Key": `uji-kb2-${k}-${Date.now()}` });
    const q = r.body.request || {};
    log(`  [API] ${ket} ${rp(nom)}: HTTP ${r.status} → ${q.number} (${q.id}) ${q.status}`);
    out[k] = { id: q.id, number: q.number, amount: q.amount };
  }
  simpan(out);
}

// ═══ k5 — penyetuju: lonceng, Pusat Persetujuan, Setujui ═════════════════════════════════════════════════════════
async function k5(browser) {
  const { A } = muat();
  const s0 = await saldo();
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, SETUJU);
  log(`K5 Penyetuju (manager@) — lonceng`);
  await view(p, "cash-management", 6000);
  const nf = await notif(SETUJU, A.number);
  log(`  [API] pemberitahuan penyetuju untuk ${A.number}: ${nf.map((n) => `${n.type} "${n.title}" — "${n.body}" doc ${n.doc && n.doc.ref_type}/${n.doc && n.doc.ref_id}`).join(" | ") || "TIDAK ADA"}`);
  try {
    await tid(p, "notif-bell").click();
    await tid(p, "notif-panel").waitFor({ timeout: 10000 });
    await sleep(2000);
    await shotEl(tid(p, "notif-panel"), "10_penyetuju_lonceng_kas_keluar_menunggu");
    const t = (await tid(p, "notif-panel").innerText()).split("\n").filter((x) => /kas keluar|PKK/i.test(x)).slice(0, 6);
    log(`  lonceng: ${t.join(" | ").slice(0, 400)}`);
    await p.keyboard.press("Escape");
  } catch (e) { log(`  GALAT lonceng: ${e.message.slice(0, 200)}`); }

  log("K5 Penyetuju — Persetujuan › Pusat Persetujuan: antrean \"Kas keluar manual menunggu\"");
  await view(p, "approval-inbox", 8000);
  const chip = tid(p, "approval-inbox-backlog-cash_out_request");
  let lewatChip = false;
  try {
    await chip.waitFor({ timeout: 15000 });
    await chip.scrollIntoViewIfNeeded();
    log(`  antrean: "${await teks(chip)}", bisa diklik: ${!(await chip.isDisabled())}, title "${await chip.getAttribute("title")}"`);
    const lain = p.locator('[data-testid^="approval-inbox-other-"]').filter({ hasText: /PKK/ });
    log(`  "Menunggu di layar lain" baris PKK: ${(await lain.allInnerTexts()).map(satu).filter((x) => x).slice(0, 4).join(" | ") || "tidak tampil di 5 teratas"}`);
    await shot(p, "11_penyetuju_pusat_persetujuan_antrean_kas_keluar");
    if (await chip.isDisabled()) throw new Error("chip antrean nonaktif untuk penyetuju");
    await chip.click();
    await tid(p, "cash-management-view").waitFor({ timeout: 15000 });
    lewatChip = true;
    log(`  klik antrean → ${p.url().replace(BASE, "")}`);
  } catch (e) {
    log(`  TEMUAN/GALAT antrean: ${e.message.slice(0, 200)} — buka layar langsung`);
    await shot(p, "galat_k5_pusat_persetujuan");
    await view(p, "cash-management", 7000);
  }
  await tid(p, `cash-out-row-${A.id}`).waitFor({ timeout: 20000 });
  await sleep(2500);
  log(`  bagian menunggu (penyetuju): ${(await teks(tid(p, "cash-out-pending"))).slice(0, 500)}`);
  log(`  Setujui ${A.number} aktif ${!(await tid(p, `cash-out-approve-${A.id}`).isDisabled())}, Tolak aktif ` +
    `${!(await tid(p, `cash-out-reject-${A.id}`).isDisabled())}, Batal ${await tid(p, `cash-out-cancel-${A.id}`).count() ? "ada" : "tidak ada"}`);
  const top = await tid(p, "cash-out-pending").evaluate((e) => Math.round(e.getBoundingClientRect().top));
  log(`  posisi bagian menunggu dari atas layar: ${top} px (${lewatChip ? "dari antrean" : "layar langsung"})`);
  await shot(p, "12_penyetuju_transaksi_kas_bagian_menunggu");

  log(`K5 Penyetuju — Setujui ${A.number} → konfirmasi`);
  await tid(p, `cash-out-approve-${A.id}`).click();
  await tid(p, "cash-out-approve-confirm-confirm").waitFor({ timeout: 10000 });
  await sleep(900);
  await shot(p, "13_penyetuju_setujui_konfirmasi");
  log(`  konfirmasi: "${await teks(tid(p, "cash-out-approve-confirm-message"))}"`);
  const tunggu = p.waitForResponse((r) => r.url().includes(`/cash-out-requests/${A.id}/approve`), { timeout: 30000 });
  await tid(p, "cash-out-approve-confirm-confirm").click();
  const resp = await tunggu;
  const hasil = await resp.json().catch(() => ({}));
  const tt = await toastTeks(p, /disetujui/);
  await sleep(600);
  await shot(p, "14_penyetuju_setujui_toast");
  log(`  toast: "${tt}"`);
  log(`  [API] POST approve: HTTP ${resp.status()} status ${hasil.status}, kas ${hasil.kas && hasil.kas.number} ${rp(hasil.kas && hasil.kas.amount)} ` +
    `gl ${hasil.kas && hasil.kas.gl_status} jurnal ${hasil.kas && hasil.kas.journal_number}`);
  await sleep(3000);
  // Baris kas baru di daftar ("Dari pengajuan …").
  const kas = (await kasKsc()).find((k) => k.ref_id === A.id);
  log(`  [API] kas terbit: ${kas ? `${kas.number} ${kas.direction} ${rp(kas.amount)} ref_type ${kas.ref_type}, ref_id ${kas.ref_id} ` +
    `(${kas.ref_id === A.id ? "= id pengajuan" : "BEDA"}), cash_out_request_number ${kas.cash_out_request_number}, gl_status ${kas.gl_status}, ` +
    `tanggal ${kas.txn_date}, dibuat_oleh ${kas.created_by}, disetujui_oleh ${kas.disetujui_oleh}` : "TIDAK ADA"}`);
  if (kas && kas.journal_entry_id) log(`  [API] jurnal: ${await jurnal(kas.journal_entry_id)}`);
  const q = await pengajuan(A.id);
  log(`  [API] pengajuan ${q.number}: status ${q.status}, disetujui ${q.disetujui_oleh} ${q.disetujui_pada}, cash_number ${q.cash_number}, ` +
    `jejak ${(q.jejak || []).map((j) => `${j.aksi} ${j.oleh}`).join(", ")}`);
  const s1 = await saldo();
  log(`  [API] sesudah Setujui: ${ringSaldo(s1)} — kas baru ${s1.kas_n - s0.kas_n}, Kas Besar turun ${rp(s0.kas_besar - s1.kas_besar)}, ` +
    `1-1100 turun ${rp(s0.gl_1100 - s1.gl_1100)}, jurnal baru ${s1.jurnal_n - s0.jurnal_n}`);
  if (kas) {
    const row = tid(p, `cash-row-${kas.id}`);
    await row.waitFor({ timeout: 15000 }).catch(() => {});
    await row.scrollIntoViewIfNeeded().catch(() => {});
    await sleep(800);
    log(`  baris kas di daftar: ${(await teks(row)).slice(0, 260)}`);
    log(`  sumber: "${await teks(tid(p, `cash-source-row-${kas.id}`))}"; anulir ${await tid(p, `void-cash-${kas.id}`).count() ? "tersedia" : "tidak ada"}`);
    await shot(p, "15_penyetuju_daftar_kas_dari_pengajuan");
    log(`K5 Penyetuju — klik "Dari pengajuan ${A.number}" → pratinjau (Disetujui)`);
    await tid(p, `cash-request-${kas.id}`).click();
    await tid(p, "doc-preview-cash-out-request").waitFor({ timeout: 15000 });
    await sleep(2500);
    await shot(p, "16_pratinjau_pkk_disetujui_kas_jurnal");
    log(`  pratinjau: status "${await teks(tid(p, "doc-preview-status"))}"; kas "${await teks(tid(p, "doc-preview-cor-cash"))}"; ` +
      `riwayat "${await teks(tid(p, "doc-preview-cor-history"))}"; Buka layar penuh ${await tid(p, "doc-preview-full").count()}`);
    const jl = tid(p, "doc-preview-cor-journal");
    log(`  baris Jurnal di pratinjau: ${await jl.count() ? `tautan "${await teks(jl)}" (title "${await jl.getAttribute("title")}")` : "BUKAN tautan"}`);
    await p.keyboard.press("Escape");
  }
  const nAju = await notif(AJU, A.number);
  log(`  [API] pemberitahuan pengaju untuk ${A.number}: ${nAju.map((n) => `${n.type} "${n.title}" — "${n.body}"`).join(" | ") || "TIDAK ADA"}`);
  simpan({ kasA: kas ? { id: kas.id, number: kas.number } : null });
  await c.close();
}

// ═══ k5b — Pusat Persetujuan "Menunggu di layar lain › Lihat semua": nomor PKK = tautan pratinjau ═══════════════════
async function k5b(browser) {
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, SETUJU);
  log("K5b Penyetuju — Pusat Persetujuan › Menunggu di layar lain › Lihat semua (baris PKK)");
  await view(p, "approval-inbox", 8000);
  try {
    await tid(p, "approval-inbox-others-see-all").click();
    const modal = tid(p, "approval-inbox-others-modal");
    await modal.waitFor({ timeout: 10000 });
    await sleep(1500);
    const pkk = p.locator('[data-testid^="approval-inbox-other-modal-"]').filter({ hasText: /PKK/ });
    const n = await pkk.count();
    const baris = (await pkk.allInnerTexts()).map(satu).filter((x) => /PKK/.test(x));
    log(`  baris PKK di "Lihat semua": ${baris.slice(0, 6).join(" | ") || "TIDAK ADA"} (${n} elemen)`);
    const link = p.locator('[data-testid^="approval-inbox-other-modal-doc-"]').filter({ hasText: /PKK/ }).first();
    if (await link.count()) {
      await link.scrollIntoViewIfNeeded();
      await sleep(600);
      await shot(p, "16b_penyetuju_pusat_persetujuan_lihat_semua_pkk");
      const nomor = await teks(link);
      await link.click();
      await tid(p, "doc-preview-cash-out-request").waitFor({ timeout: 15000 });
      await sleep(2000);
      await shot(p, "16c_penyetuju_pusat_persetujuan_pratinjau_pkk");
      log(`  klik ${nomor} → pratinjau "${await teks(tid(p, "doc-preview-title"))}" status "${await teks(tid(p, "doc-preview-status"))}"; ` +
        `Buka layar penuh ${await tid(p, "doc-preview-full").count()}`);
    } else {
      await shot(p, "16b_penyetuju_pusat_persetujuan_lihat_semua_pkk");
      log("  TEMUAN: tidak ada tautan nomor PKK di daftar Lihat semua");
    }
  } catch (e) { log(`  GALAT k5b: ${e.message.slice(0, 200)}`); await shot(p, "galat_k5b"); }
  await c.close();
}

// ═══ k6 — penyetuju: Tolak ═══════════════════════════════════════════════════════════════════════════════════════
async function k6(browser) {
  const { B } = muat();
  const s0 = await saldo();
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, SETUJU);
  log(`K6 Penyetuju — Tolak ${B.number} beralasan`);
  await view(p, "cash-management", 7000);
  await tid(p, `cash-out-reject-${B.id}`).waitFor({ timeout: 15000 });
  await tid(p, `cash-out-reject-${B.id}`).click();
  await tid(p, "cash-out-reject-reason-reason").waitFor({ timeout: 10000 });
  await sleep(800);
  log(`  pop-up: "${await teks(tid(p, "cash-out-reject-reason-message"))}"; tombol Tolak nonaktif saat kosong: ` +
    `${await tid(p, "cash-out-reject-reason-confirm").isDisabled()}`);
  await shot(p, "17_penyetuju_tolak_popup_kosong_tombol_mati");
  await tid(p, "cash-out-reject-reason-reason").fill("Bukan");
  await sleep(300);
  log(`  alasan "Bukan" (5 huruf): tombol nonaktif ${await tid(p, "cash-out-reject-reason-confirm").isDisabled()}`);
  await tid(p, "cash-out-reject-reason-reason").fill("Bukan biaya kantor");
  await sleep(500);
  const tunggu = p.waitForResponse((r) => r.url().includes(`/cash-out-requests/${B.id}/reject`), { timeout: 30000 });
  await tid(p, "cash-out-reject-reason-confirm").click();
  const resp = await tunggu;
  const hasil = await resp.json().catch(() => ({}));
  const tt = await toastTeks(p, /ditolak/);
  await sleep(500);
  await shot(p, "18_penyetuju_tolak_toast");
  log(`  toast: "${tt}"`);
  log(`  [API] POST reject: HTTP ${resp.status()} status ${hasil.status}, alasan_tolak "${hasil.alasan_tolak}", ditolak_oleh ${hasil.ditolak_oleh}`);
  const s1 = await saldo();
  log(`  [API] sesudah Tolak: kas baru ${s1.kas_n - s0.kas_n}, Kas Besar berubah ${rp(s1.kas_besar - s0.kas_besar)}, jurnal baru ${s1.jurnal_n - s0.jurnal_n}`);
  const nAju = await notif(AJU, B.number);
  log(`  [API] pemberitahuan pengaju untuk ${B.number}: ${nAju.map((n) => `${n.type} "${n.title}" — "${n.body}"`).join(" | ") || "TIDAK ADA"}`);
  await c.close();
}

// ═══ k7 — pengaju: lonceng, pratinjau ditolak, Batal ═════════════════════════════════════════════════════════════
async function k7(browser) {
  const { A, B, C } = muat();
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, AJU);
  log("K7 Pengaju — lonceng (disetujui & ditolak)");
  await view(p, "cash-management", 7000);
  const nB = (await notif(AJU, B.number))[0];
  try {
    await tid(p, "notif-bell").click();
    await tid(p, "notif-panel").waitFor({ timeout: 10000 });
    await sleep(2000);
    await shotEl(tid(p, "notif-panel"), "19_pengaju_lonceng_disetujui_ditolak");
    const t = (await tid(p, "notif-panel").innerText()).split("\n").filter((x) => /kas keluar|PKK|tolak|setuju/i.test(x)).slice(0, 8);
    log(`  lonceng: ${t.join(" | ").slice(0, 500)}`);
    if (nB) {
      await tid(p, `notif-item-${nB.id}`).click();
      await tid(p, "doc-preview-cash-out-request").waitFor({ timeout: 15000 });
      await sleep(2500);
      await shot(p, "20_pengaju_pratinjau_pkk_ditolak_alasan");
      log(`  klik pemberitahuan ${B.number} → ${p.url().replace(BASE, "")}; pratinjau status "${await teks(tid(p, "doc-preview-status"))}"; ` +
        `fakta "${(await teks(tid(p, "doc-preview-cor-facts"))).slice(0, 400)}"; riwayat "${await teks(tid(p, "doc-preview-cor-history"))}"; ` +
        `Buka layar penuh ${await tid(p, "doc-preview-full").count()}`);
      await p.keyboard.press("Escape");
      await sleep(800);
    }
  } catch (e) { log(`  GALAT lonceng/pratinjau: ${e.message.slice(0, 200)}`); await shot(p, "galat_k7_lonceng"); }

  log(`K7 Pengaju — Batal ${C.number}`);
  await view(p, "cash-management", 7000);
  await tid(p, `cash-out-cancel-${C.id}`).waitFor({ timeout: 15000 });
  await tid(p, `cash-out-cancel-${C.id}`).click();
  await tid(p, "cash-out-cancel-reason-reason").waitFor({ timeout: 10000 });
  await tid(p, "cash-out-cancel-reason-reason").fill("Spanduk sudah dicetak vendor sponsor");
  await sleep(600);
  await shot(p, "21_pengaju_batal_popup_alasan");
  log(`  pop-up: "${await teks(tid(p, "cash-out-cancel-reason-message"))}"`);
  log(`  tombol pop-up: penutup "${await teks(tid(p, "cash-out-cancel-reason-cancel"))}", aksi "${await teks(tid(p, "cash-out-cancel-reason-confirm"))}"`);
  const tunggu = p.waitForResponse((r) => r.url().includes(`/cash-out-requests/${C.id}/cancel`), { timeout: 30000 });
  await tid(p, "cash-out-cancel-reason-confirm").click();
  const resp = await tunggu;
  const hasil = await resp.json().catch(() => ({}));
  const tt = await toastTeks(p, /dibatalkan/);
  log(`  toast: "${tt}"`);
  log(`  [API] POST cancel: HTTP ${resp.status()} status ${hasil.status}, alasan_batal "${hasil.alasan_batal}", dibatalkan_oleh ${hasil.dibatalkan_oleh}`);
  await sleep(2500);
  await p.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);
  await shot(p, "22_pengaju_sesudah_batal_bagian_menunggu", true);
  log(`  bagian menunggu sesudah: ${(await teks(tid(p, "cash-out-pending"))).slice(0, 300) || "(tidak digambar)"}`);
  const nC = await notif(AJU, C.number);
  log(`  [API] pemberitahuan pengaju untuk ${C.number} (batal sendiri): ${nC.length} — ${nC.map((n) => n.title).join(" | ") || "tidak ada (sesuai: tidak memberi tahu diri sendiri)"}`);
  const nS = await notif(SETUJU, C.number);
  log(`  [API] pemberitahuan penyetuju untuk ${C.number}: ${nS.map((n) => `${n.type} "${n.title}" read ${n.read}`).join(" | ") || "-"}`);
  await c.close();
}

// ═══ k8 — kartu Asisten (opsional) ═════════════════════════════════════════════════════════════════════════════════
async function k8(browser) {
  log("K8 (opsional) — kartu Asisten cash_manual di atas batas → \"Diajukan — menunggu persetujuan kas keluar PKK-…\"");
  await k8kartu(browser);
}

// ═══ cek — ringkasan akhir ═══════════════════════════════════════════════════════════════════════════════════════
async function cek() {
  const d = muat();
  log("CEK — ringkasan akhir PT KSC");
  log(`  awal:  ${ringSaldo(d.saldo_awal)}`);
  const s = await saldo();
  log(`  akhir: ${ringSaldo(s)} — Kas Besar turun ${rp(d.saldo_awal.kas_besar - s.kas_besar)} (harap Rp 1.000.000 + Rp 2.500.000 ` +
    `= Rp 3.500.000), 1-1100 turun ${rp(d.saldo_awal.gl_1100 - s.gl_1100)}, kas baru ${s.kas_n - d.saldo_awal.kas_n}`);
  const all = (await api(ADMIN, "GET", `/cash-out-requests?entity_id=${ENT}&page_size=50`)).body;
  log(`  pengajuan PT KSC: ${all.items.map((x) => `${x.number} ${x.status} ${rp(x.amount)} "${x.description}"${x.cash_number ? ` → ${x.cash_number}` : ""}`).join("; ")}`);
  for (const k of ["A", "B", "C"]) {
    if (!d[k]) continue;
    const q = await pengajuan(d[k].id);
    log(`  ${q.number}: ${q.status}; kas ${q.kas ? `${q.kas.number} ${q.kas.gl_status} jurnal ${q.kas.journal_number}` : "-"}; ` +
      `alasan tolak "${q.alasan_tolak || ""}" batal "${q.alasan_batal || ""}"; jejak ${(q.jejak || []).map((j) => `${j.aksi}:${j.oleh}${j.catatan ? `(${j.catatan})` : ""}`).join(", ")}`);
  }
  const bl = (await api(SETUJU, "GET", `/approvals/backlog?entity_id=${ENT}`));
  const row = bl.status === 200 ? ((bl.body.items || []).find((x) => x.key === "cash_out_request") || {}) : {};
  log(`  antrean Pusat Persetujuan (manager@): HTTP ${bl.status} "${row.label || "-"}" ${row.count ?? "-"}`);
}

// ═══ k8 — rinci ════════════════════════════════════════════════════════════════════════════════════════════════════
// Penyiapan (dikembalikan oleh fase `pulih`): sakelar akun Asisten Keuangan Finance (`users.ai_finance` B+C), pengaturan
// PT KSC `ai.tindakan_uang_keluar` = nyala (bawaan mati, H5). Kartu disiapkan lewat alat `prepare_action` (jalur yang
// dipakai asisten; tanpa model bahasa), lalu dibuka & dijalankan dari layar Tanya KN › Tindakan.
const PY_SEBELUM = `from pymongo import MongoClient\nimport json\ndb=MongoClient()["test_database"]\n` +
  `u=db.users.find_one({"email":"${AJU}"},{"_id":0,"id":1,"ai_finance":1})\n` +
  `cv=list(db.config_values.find({"key":{"$in":["ai.enabled","ai.tindakan_uang_keluar"]}},{"_id":0,"key":1,"scope_type":1,"scope_id":1,"value":1}))\n` +
  `print(json.dumps({"user":u,"config":cv}, default=str))`;
async function k8kartu(browser) {
  const { execFileSync } = require("child_process");
  const sebelum = JSON.parse(execFileSync("python3", ["-c", PY_SEBELUM]).toString());
  if (!muat().k8_sebelum) simpan({ k8_sebelum: sebelum });
  log(`  keadaan sebelum (dipulihkan fase pulih): users.ai_finance Finance ${JSON.stringify(sebelum.user.ai_finance ?? null)}; ` +
    `config_values ${JSON.stringify(sebelum.config)}`);
  const pa = await api(ADMIN, "PATCH", `/users/${sebelum.user.id}`, { data: { ai_finance: { enabled: true, classes: ["B", "C"] } } });
  const pc = await api(ADMIN, "PUT", "/config/values", { items: [{ key: "ai.tindakan_uang_keluar", value: true,
    scope_type: "entity", scope_id: ENT, reason: "Tangkapan Kas & Bank 2 — kartu Asisten kas manual (sementara)" }] });
  log(`  [API] Admin: sakelar akun Finance B+C HTTP ${pa.status}; ai.tindakan_uang_keluar KSC = nyala HTTP ${pc.status}`);
  const rek = await bca();
  let pr = await api(AJU, "POST", "/ai/tools/prepare_action", { action: "cash_manual", user_request: "Catat kas keluar sewa sound system acara 3 juta dari BCA",
    session_id: "", args: { account_id: rek.id, direction: "out", amount: 3000000, category: "operasional",
      description: "Sewa sound system acara" } });
  if (pr.status !== 200) {
    log(`  [API] prepare_action: HTTP ${pr.status} "${typeof pr.body === "object" ? pr.body.detail : pr.body}" — coba nyalakan ai.enabled (global)`);
    const pe = await api(ADMIN, "PUT", "/config/values", { items: [{ key: "ai.enabled", value: true, scope_type: "global",
      scope_id: "", reason: "Tangkapan Kas & Bank 2 — kartu Asisten kas manual (sementara)" }] });
    log(`  [API] ai.enabled global = nyala HTTP ${pe.status}`);
    simpan({ k8_ai_enabled: true });
    pr = await api(AJU, "POST", "/ai/tools/prepare_action", { action: "cash_manual", user_request: "Catat kas keluar sewa sound system acara 3 juta dari BCA",
      session_id: "", args: { account_id: rek.id, direction: "out", amount: 3000000, category: "operasional",
        description: "Sewa sound system acara" } });
  }
  if (pr.status !== 200) { log(`  GALAT prepare_action: HTTP ${pr.status} ${JSON.stringify(pr.body).slice(0, 300)}`); return; }
  const kartu = pr.body.card;
  simpan({ kartu: { id: kartu.id } });
  log(`  [API] kartu ${kartu.id} (${kartu.action || kartu.title}) status ${kartu.status}; rencana: ` +
    `${(kartu.plan.rows || []).map((r) => `${r.label}: ${r.before ?? ""} → ${r.after ?? ""}`).join(" | ")}; ringkasan "${kartu.plan.summary}"`);
  const s0 = await saldo();
  const n0 = (await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}`)).body.total;

  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, AJU);
  log("K8 Pengaju — Tanya KN › Tindakan: buka kartu Catat kas manual Rp 3.000.000");
  await p.goto(`${BASE}/?view=tanya-kn&tab=actions&entity=${ENT}`, { waitUntil: "domcontentloaded" });
  await sleep(7000);
  await clean(p);
  try {
    await tid(p, `tanya-actions-open-${kartu.id}`).click();
    await tid(p, "tanya-actions-card-modal").waitFor({ timeout: 15000 });
    await sleep(2000);
    await shot(p, "23_asisten_kartu_kas_manual_rencana_diajukan");
    log(`  rencana di kartu: "${(await teks(tid(p, "tanya-card-plan"))).slice(0, 400)}"`);
    await tid(p, "tanya-card-reason").fill("Sewa sound system untuk acara pameran akhir bulan");
    await tid(p, "tanya-card-retype").fill("3000000");
    await sleep(600);
    await tid(p, "tanya-action-confirm").click();
    await tid(p, "tanya-card-confirm-modal-confirm").waitFor({ timeout: 10000 });
    await sleep(500);
    const tunggu = p.waitForResponse((r) => r.url().includes(`/ai/actions/${kartu.id}/confirm`), { timeout: 60000 });
    await tid(p, "tanya-card-confirm-modal-confirm").click();
    const resp = await tunggu;
    const hasil = await resp.json().catch(() => ({}));
    await tid(p, "tanya-card-outcome").waitFor({ timeout: 20000 });
    await sleep(2000);
    await shot(p, "24_asisten_kartu_hasil_diajukan_menunggu");
    log(`  [API] POST confirm: HTTP ${resp.status()} kartu ${hasil.status}; result status_code ${hasil.result && hasil.result.status_code}, ` +
      `message "${hasil.result && hasil.result.message}", document ${hasil.result && hasil.result.document && `${hasil.result.document.type} ${hasil.result.document.number}`}`);
    log(`  hasil di kartu: "${await teks(tid(p, "tanya-card-outcome"))}"`);
    log(`  lencana kartu: "${await teks(tid(p, "tanya-action-pill"))}"; baris "Berhasil — …": ${await tid(p, "tanya-card-success").count() ? "ADA" : "tidak ada"}`);
    await p.keyboard.press("Escape");
    await sleep(800);
    // Kartu yang sudah dijalankan pindah dari "Menunggu saya" ke kotak "Selesai".
    await tid(p, "tanya-actions-box-done").click();
    await tid(p, `tanya-actions-pill-${kartu.id}`).waitFor({ timeout: 15000 });
    await sleep(1500);
    log(`  Tindakan › Selesai, lencana baris kartu: "${await teks(tid(p, `tanya-actions-pill-${kartu.id}`))}"`);
    await shot(p, "25_asisten_daftar_kartu_lencana_diajukan");
  } catch (e) { log(`  GALAT kartu di layar: ${e.message.slice(0, 250)}`); await shot(p, "galat_k8_kartu"); }
  await c.close();
  const req = ((await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}&status=menunggu_persetujuan`)).body.items || [])
    .find((x) => x.ai_card_id === kartu.id);
  const s1 = await saldo();
  const n1 = (await api(AJU, "GET", `/cash-out-requests?entity_id=${ENT}`)).body.total;
  log(`  [API] pengajuan dari kartu: ${req ? `${req.number} ${req.status} ${rp(req.amount)} pengaju ${req.pengaju.name} ai_card_id ${req.ai_card_id}` : "TIDAK DITEMUKAN"}; ` +
    `pengajuan PT ${n0} → ${n1}; kas baru ${s1.kas_n - s0.kas_n}, jurnal baru ${s1.jurnal_n - s0.jurnal_n}, Kas Besar berubah ${rp(s1.kas_besar - s0.kas_besar)}`);
  if (req) simpan({ D: { id: req.id, number: req.number, amount: req.amount } });
}

/** Kembalikan yang diubah k8: sakelar akun Asisten Keuangan Finance + pengaturan ai.* ke keadaan sebelum. */
async function pulih() {
  const { execFileSync } = require("child_process");
  const d = muat();
  const seb = d.k8_sebelum;
  if (!seb) { log("PULIH — k8 tidak dijalankan; tidak ada yang dikembalikan"); return; }
  const ada = (k, t, s) => seb.config.some((x) => x.key === k && x.scope_type === t && (x.scope_id || "") === s);
  for (const [key, tipe, sid] of [["ai.tindakan_uang_keluar", "entity", ENT], ["ai.enabled", "global", ""]]) {
    if (ada(key, tipe, sid)) { log(`  ${key} ${tipe} sudah tersimpan sebelum tangkapan — tidak disentuh`); continue; }
    if (key === "ai.enabled" && !d.k8_ai_enabled) { log("  ai.enabled tidak diubah k8 — tidak disentuh"); continue; }
    const r = await api(ADMIN, "POST", "/config/values/reset", { key, scope_type: tipe, scope_id: sid,
      reason: "Selesai tangkapan Kas & Bank 2 — kembali ke bawaan sistem" });
    log(`PULIH — ${key} (${tipe}${sid ? " " + sid : ""}) ke bawaan: HTTP ${r.status}${r.status >= 400 ? " " + JSON.stringify(r.body).slice(0, 160) : ""}`);
  }
  if (seb.user.ai_finance == null) {
    // Sebelumnya isian tidak ada sama sekali (bawaan mati) → dihapus lagi supaya persis sama dengan data acuan.
    const py = `from pymongo import MongoClient\ndb=MongoClient()["test_database"]\n` +
      `r=db.users.update_one({"id":"${seb.user.id}"},{"$unset":{"ai_finance":""}})\nprint(r.modified_count)`;
    log(`PULIH — users.ai_finance Finance dihapus (sebelumnya tidak ada): diubah ${execFileSync("python3", ["-c", py]).toString().trim()}`);
  } else {
    const r = await api(ADMIN, "PATCH", `/users/${seb.user.id}`, { data: { ai_finance: seb.user.ai_finance } });
    log(`PULIH — users.ai_finance Finance dikembalikan ${JSON.stringify(seb.user.ai_finance)}: HTTP ${r.status}`);
  }
  const sesudah = JSON.parse(execFileSync("python3", ["-c", PY_SEBELUM]).toString());
  log(`  sesudah pulih: users.ai_finance ${JSON.stringify(sesudah.user.ai_finance ?? null)}; config_values ${JSON.stringify(sesudah.config)}`);
}

const FASE = { k1, k2, k3, k4, k5, k5b, k6, k7, k8, cek, pulih };
(async () => {
  const pilih = process.argv.slice(2).length ? process.argv.slice(2) : ["k1", "k2", "k3", "k4", "k5", "k5b", "k6", "k7", "cek"];
  const browser = await chromium.launch();
  for (const f of pilih) {
    log(`── fase ${f} (${new Date().toISOString()})`);
    try { await FASE[f](browser); } catch (e) { log(`  GALAT fase ${f}: ${e.message.slice(0, 400)}`); break; }
  }
  await browser.close();
})();
