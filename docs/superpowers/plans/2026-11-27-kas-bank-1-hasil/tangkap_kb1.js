// F1 Kwitansi otomatis dari mutasi + Kas & Bank bagian 1 — tangkapan sesudah (lingkungan uji lokal, data acuan; BUKAN
// data nyata). Prasyarat: backend :8001 + frontend :3000 menyala pada cabang; `python siapkan_kb1.py` sudah membuat
// kb1_data.json + mutasi_uji_kb1.csv (pesanan CBD & DP50 PT KSC tertahan "Bayar dicek Finance", kode bayar lahir).
//
// Akun: Finance `finance@` (pengimpor mutasi, penyetuju pindah saldo, pembuat Pindah Dana yang butuh dua orang) ·
// Admin `admin@` (penyiap pindah saldo, pembuat/penerima Pindah Dana, penyetuju Pindah Dana Finance) · Sales `sales@`.
// Keduanya (Finance & Admin) memegang accounting.manage + cash.approve.
//
// Fase (jalankan berurutan; `node tangkap_kb1.js <fase…>`, tanpa argumen = semua):
//   f1      Finance — Rekonsiliasi › impor CSV → kwitansi otomatis + kartu; pratinjau kwitansi; Meja Keuangan kartu
//           "Mutasi berkode perlu dicek" → pop-up → form Catat kwitansi (tidak disimpan).
//   f1s     Sales — pesanan CBD sesudah kwitansi otomatis (Perjalanan) + notifikasi.
//   ps1     Admin — Rekening & Saldo (penanda) → Akun per rekening (pratinjau) → Siapkan → usulan menunggu.
//   ps2     Finance — Pusat Persetujuan → Setujui (angka terbaru) → 409 "Angka berubah" (kas baru lewat API) → Setujui.
//   ps3     Admin — Rekening & Saldo sesudah aktif + form Ubah (akun hanya-baca); cek API saldo sub-akun = buku kas.
//   pd1     Admin — Pindah Dana dua tahap → Dalam perjalanan → Terima; Kontrol dua orang "Pindah dana" = 2 orang (KSC).
//   pd2     Finance — Pindah Dana menunggu persetujuan (Setujui mati untuk pembuat).
//   pd3     Admin — Setujui (konfirmasi) → pratinjau PDN → Batal beralasan; Transaksi Kas tanpa Transfer/Top-up; cek API akhir.
//   cek     API saja — jurnal pindah saldo & Pindah Dana, kas lama tertaut, kas manual kategori transfer ditolak.
//   pulih   Kontrol dua orang "Pindah dana" KSC dikembalikan ke bawaan sistem.
const { chromium } = require("playwright");
const fs = require("fs");
const DIR = __dirname;
const OUT = DIR + "/tangkapan";
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const API = "http://localhost:8001/api";
const ENT = "ent_ksc";
const DATA = JSON.parse(fs.readFileSync(DIR + "/kb1_data.json", "utf8"));
const CSV = DIR + "/" + DATA.mutasi.csv;
const ADMIN = "admin@kainnusantara.id", FIN = "finance@kainnusantara.id";
const LOGF = DIR + "/tangkap_kb1_log.txt";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const tid = (p, id) => p.locator(`[data-testid="${id}"]`);
const clean = (p) => p.evaluate(() => document.querySelectorAll("iframe#webpack-dev-server-client-overlay").forEach((e) => e.remove())).catch(() => {});
const rp = (x) => "Rp " + Number(x || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const satu = (s) => String(s || "").replace(/\s+/g, " ").trim();
function log(s) { console.log(s); fs.appendFileSync(LOGF, s + "\n"); }

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
async function saldoAkun(code) {
  const r = await api(ADMIN, "GET", `/gl/accounts/${code}/ledger?entity_id=${ENT}`);
  return r.status === 200 ? r.body.balance : `HTTP ${r.status}`;
}
/** Tiap rekening: saldo buku kas (`/bank-accounts/{id}/ledger`) vs saldo akun buku besarnya; akun lama 1-1100/1-1110/1-1150. */
async function cekSaldo(judul) {
  log(`  [API] ${judul}`);
  const out = {};
  for (const a of await rekening()) {
    const led = (await api(ADMIN, "GET", `/bank-accounts/${a.id}/ledger`)).body;
    const akun = a.gl_account_code || "";
    const gl = akun ? await saldoAkun(akun) : null;
    const sama = akun ? (Math.abs(Number(gl) - Number(led.balance)) < 0.005 ? "SAMA" : `BEDA ${rp(Number(gl) - Number(led.balance))}`) : "-";
    log(`    ${a.name}: buku kas ${rp(led.balance)} (${led.txn_count} transaksi) · akun ${akun || "(belum)"} ${akun ? rp(gl) : ""} → ${sama}`);
    out[a.id] = { name: a.name, buku: led.balance, akun, gl };
  }
  for (const c of ["1-1100", "1-1110", "1-1150"]) log(`    akun ${c}: ${rp(await saldoAkun(c))}`);
  return out;
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
/** KNSelect: buka lalu klik opsi bernilai `value` (testid `<id>-option-<value>`). */
async function pilihNilai(page, testId, value) {
  await tid(page, testId).click();
  await sleep(500);
  const opt = tid(page, `${testId}-option-${value}`).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(500);
}
/** KNDatePicker: buka lalu klik hari `hari` di bulan yang tampil (bukan hari bulan sebelah). */
async function pilihHari(page, testId, hari) {
  await tid(page, testId).click();
  const pop = tid(page, `${testId}-popover`);
  await pop.waitFor({ timeout: 8000 });
  await pop.locator('button[name="day"]:not(.day-outside)', { hasText: new RegExp(`^${hari}$`) }).first().click();
  await sleep(500);
}
/** Kalimat di sel aksi: ukuran span + lebar tabel vs wadah gulirnya (temuan 1 tangkapan pertama: tabel melebar). */
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
const hariIni = () => new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 10);   // WIB
const besok = () => new Date(Date.now() + 31 * 3600e3).toISOString().slice(0, 10);
async function barisMutasi() {
  const r = await api(FIN, "GET", `/bank-reconciliation/lines?bank_account_id=${DATA.rekening.id}`);
  const semua = r.body || [];
  const cari = (kode) => semua.find((l) => (l.description || "").includes(kode));
  return { auto: cari(DATA.cbd.pay_code), kartu: cari(DATA.dp.pay_code) };
}

// ═══ F1 — Finance: impor mutasi → kwitansi otomatis + kartu ═══════════════════════════════════════════════════════
async function f1(browser) {
  const { cbd, dp } = DATA;
  log(`F1 — pesanan CBD ${cbd.number} (kode ${cbd.pay_code}, wajib sebelum gudang ${rp(cbd.shortfall)}), DP50 ${dp.number} ` +
    `(kode ${dp.pay_code}, wajib ${rp(dp.shortfall)}); berkas ${DATA.mutasi.csv}: baris (a) ${rp(DATA.mutasi.tepat)} kode CBD, ` +
    `(b) ${rp(DATA.mutasi.lebih)} kode DP50 (lebih dari tagihan)`);
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, FIN);
  log("F1-1 Finance — Meja Keuangan sebelum impor (kartu Uang masuk: kedua pesanan Tertahan bayar)");
  await view(p, "finance-desk", 8000);
  await shot(p, "01_f1_meja_keuangan_sebelum_impor");

  log("F1-2 Finance — Rekonsiliasi › Impor mutasi bank (BCA Operasional KSC): unggah CSV → Pratinjau → Impor");
  await view(p, "bank-reconciliation", 7000);
  log(`  rekening terpilih: ${await teks(tid(p, "recon-account-select"))}`);
  await tid(p, "recon-import-toggle").click();
  await tid(p, "recon-import-panel").waitFor({ timeout: 10000 });
  await tid(p, "recon-file-input").setInputFiles(CSV);
  await sleep(800);
  await tid(p, "recon-preview-btn").click();
  await tid(p, "recon-preview").waitFor({ timeout: 20000 });
  await sleep(1200);
  await shot(p, "02_f1_rekon_impor_pratinjau");
  log(`  pratinjau: ${(await teks(tid(p, "recon-preview"))).slice(0, 260)}`);
  await tid(p, "recon-import-submit").click();
  await tid(p, "recon-notice").waitFor({ timeout: 30000 });
  await sleep(4000);
  log(`  bilah hasil: "${await teks(tid(p, "recon-notice"))}"`);
  const { auto, kartu } = await barisMutasi();
  const f1a = (auto && auto.f1) || {}, f1k = (kartu && kartu.f1) || {};
  const kw = f1a.receipt_id ? (await api(FIN, "GET", `/ar-receipts/${f1a.receipt_id}`)).body : {};
  log(`  [API] baris (a) ${rp(auto && auto.amount)}: status ${auto && auto.status}, match_type ${auto && auto.match_type}, ` +
    `f1 ${f1a.status}/jalur ${f1a.jalur}, kwitansi ${kw.number || f1a.receipt_id} ${rp(kw.amount)} source ${kw.source} ` +
    `bank_verified ${kw.bank_verified}, kas tertaut ${(auto && auto.matched_txn_ids || []).join(",")}`);
  log(`  [API] baris (b) ${rp(kartu && kartu.amount)}: status ${kartu && kartu.status}, f1 ${f1k.status}, alasan_kode ` +
    `${f1k.alasan_kode}, alasan "${f1k.alasan}"`);
  const rowA = tid(p, `recon-line-${auto.id}`);
  await rowA.scrollIntoViewIfNeeded();
  await sleep(800);
  await shot(p, "03_f1_rekon_hasil_impor");
  const tabel = p.locator("table").filter({ has: rowA }).first();
  await shotEl(tabel, "04_f1_rekon_baris_otomatis_dan_kartu");
  log(`  baris (a) di layar: ${(await teks(rowA)).slice(0, 220)}`);
  log(`  baris (b) di layar: ${(await teks(tid(p, `recon-line-${kartu.id}`))).slice(0, 260)}`);

  log("F1-3 Finance — pratinjau kwitansi otomatis (Penagihan & Penerimaan › riwayat kwitansi)");
  try {
    await view(p, "collection-worklist", 7000);
    await tid(p, "ar-history-search").fill(kw.number);
    await sleep(3000);
    await tid(p, `ar-history-number-${kw.id}`).click();
    await tid(p, "doc-preview").waitFor({ timeout: 15000 });
    await sleep(2500);
    await shot(p, "05_f1_pratinjau_kwitansi_otomatis");
    log(`  asal kwitansi di pratinjau: "${await teks(tid(p, "doc-preview-ar-receipt-source"))}"`);
    await p.keyboard.press("Escape");
  } catch (e) { log(`  GALAT pratinjau kwitansi: ${e.message.slice(0, 200)}`); await shot(p, "galat_f1_pratinjau_kwitansi"); }

  log("F1-4 Finance — Meja Keuangan: kartu \"Mutasi berkode perlu dicek\" → pop-up → Catat kwitansi");
  await view(p, "finance-desk", 9000);
  await shot(p, "06_f1_meja_keuangan_mutasi_berkode");
  const btn = tid(p, `fin-desk-uang_masuk-number-${kartu.id}`);
  const baris = p.locator(`[data-testid^="fin-desk-uang_masuk-"][data-testid$="-${kartu.id}"]`);
  log(`  baris kartu di meja: ${(await teks(baris.first())).slice(0, 200)} | aksi "${await teks(tid(p, `fin-desk-uang_masuk-action-${kartu.id}`))}"` +
    ` | lencana "${await teks(tid(p, `fin-desk-uang_masuk-badge-${kartu.id}`))}"`);
  const uangMasuk = (await p.locator('[data-testid^="fin-desk-uang_masuk-number-"]').allInnerTexts()).map(satu);
  log(`  baris kartu Uang masuk: ${uangMasuk.join(" · ")} — pesanan CBD ${cbd.number} ${uangMasuk.includes(cbd.number) ? "MASIH ada" : "sudah tidak ada"}`);
  await btn.click();
  await tid(p, "fin-desk-bankline-panel").waitFor({ timeout: 15000 });
  await sleep(3500);
  await shot(p, "07_f1_meja_popup_mutasi_berkode");
  log(`  pop-up alasan: "${await teks(tid(p, "fin-desk-bankline-reason"))}" · tombol "${await teks(tid(p, "fin-desk-detail-action"))}"`);
  log(`  pop-up ${await teks(tid(p, "fin-desk-detail-field-subtitle"))}`);
  await tid(p, "fin-desk-detail-action").click();
  await tid(p, "ar-receipt-modal").waitFor({ timeout: 15000 });
  await sleep(3000);
  await shot(p, "08_f1_meja_form_catat_kwitansi_dari_mutasi");
  log(`  form: nominal "${await teks(tid(p, "ar-receipt-amount-line"))}", tanggal "${await teks(tid(p, "ar-receipt-date-line"))}", ` +
    `rekening dikunci ${await tid(p, "ar-receipt-account").isDisabled().catch(() => "?")}, referensi "${await tid(p, "ar-receipt-reference").inputValue().catch(() => "")}"` +
    ` — tidak disimpan (kartu dibiarkan)`);
  await p.keyboard.press("Escape");
  await c.close();
}

// ═══ F1 — Sales: pesanan CBD lepas ════════════════════════════════════════════════════════════════════════════════
async function f1s(browser) {
  const { cbd, dp } = DATA;
  const so = (await api(ADMIN, "GET", `/sales-orders/${cbd.id}`)).body;
  const so2 = (await api(ADMIN, "GET", `/sales-orders/${dp.id}`)).body;
  log(`F1-5 Sales — pesanan sesudah impor. [API] ${cbd.number}: status ${so.status}, pay_hold ${so.pay_hold ? "MASIH" : "dibuka"}, ` +
    `bayar ${so.payment_status}, release.waiting "${(so.release || {}).waiting || ""}"; ${dp.number}: status ${so2.status}, ` +
    `pay_hold ${so2.pay_hold ? "masih" : "dibuka"}, bayar ${so2.payment_status}`);
  // Tugas gudang dibaca langsung dari koleksi `wms_tasks` (rute /wms/tasks tidak menyaring order_id).
  const { execFileSync } = require("child_process");
  const py = `from pymongo import MongoClient\nimport json,sys\ndb=MongoClient()["test_database"]\n` +
    `print(json.dumps({o: [t["id"] + " " + str(t.get("flow_type")) + " " + str(t.get("status")) for t in db.wms_tasks.find({"order_id": o})] for o in sys.argv[1:]}))`;
  const tugas = JSON.parse(execFileSync("python3", ["-c", py, cbd.id, dp.id]).toString());
  log(`  [DB] tugas gudang: ${cbd.number} → ${tugas[cbd.id].join(", ") || "tidak ada"}; ${dp.number} → ` +
    `${tugas[dp.id].join(", ") || "tidak ada (masih tertahan)"}`);
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, cbd.sales_email);
  try {
    await view(p, "orders", 6000);
    if (await tid(p, "tab-list").count()) { await tid(p, "tab-list").click().catch(() => {}); await sleep(1500); }
    await tid(p, "orders-search-input").fill(cbd.number);
    await sleep(2500);
    await tid(p, `order-card-${cbd.id}`).first().click();
    await sleep(3500);
    await tid(p, "order-pane-journey").click();
    const jr = tid(p, "order-journey-panel");
    await jr.waitFor({ timeout: 15000 });
    await sleep(2500);
    await shot(p, "09_f1_sales_pesanan_cbd_lepas_perjalanan");
    log(`  Perjalanan, tahap kini: ${await teks(tid(p, "journey-current"))}`);
  } catch (e) { log(`  GALAT Perjalanan: ${e.message.slice(0, 200)}`); await shot(p, "galat_f1_sales"); }
  try {
    await tid(p, "notif-bell").click();
    await tid(p, "notif-panel").waitFor({ timeout: 10000 });
    await sleep(2000);
    await shotEl(tid(p, "notif-panel"), "10_f1_sales_notifikasi_bayar_masuk_mutasi");
    const t = (await tid(p, "notif-panel").innerText()).split("\n").filter((x) => /mutasi|kwitansi|dilepas/i.test(x)).slice(0, 4);
    log(`  notifikasi: ${t.join(" | ").slice(0, 300)}`);
  } catch (e) { log(`  GALAT notifikasi: ${e.message.slice(0, 200)}`); }
  await c.close();
}

// ═══ KB1 — pindah saldo: Admin menyiapkan ═════════════════════════════════════════════════════════════════════════
async function ps1(browser) {
  await cekSaldo("sebelum pindah saldo");
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, ADMIN);
  log("KB1-1 Admin — Kas & Bank › Rekening & Saldo (PT Sukacita/KSC): penanda PT belum memakai akun per rekening");
  await view(p, "bank-accounts", 7000);
  await shot(p, "11_kb1_rekening_sebelum_penanda");
  log(`  penanda: "${await teks(tid(p, "bank-gl-mode"))}"`);
  for (const a of await rekening()) log(`  kartu ${a.name}: "${await teks(tid(p, `bank-gl-${a.id}`))}"`);
  log("KB1-2 Admin — klik \"Siapkan pindah saldo\" → Akun per rekening (pratinjau)");
  await tid(p, "bank-gl-mode-link").click();
  await tid(p, "kas-per-rekening-view").waitFor({ timeout: 15000 });
  await tid(p, "ps-sec-accounts").waitFor({ timeout: 20000 });
  await sleep(2500);
  await p.evaluate(() => window.scrollTo(0, 0));
  await shot(p, "12_kb1_akun_per_rekening_pratinjau", true);
  const pv = (await api(ADMIN, "GET", `/kas-per-rekening/${ENT}/pratinjau`)).body;
  log(`  [API] pratinjau: aktif ${pv.aktif}, total dipindah ${rp(pv.total_dipindah)}, posting gagal ${pv.posting_gagal}, sidik ${pv.sidik}; ` +
    pv.rekening.map((r) => `${r.nama} → ${r.akun_tujuan}${r.akun_tujuan_baru ? " (baru)" : ""} saldo buku ${rp(r.saldo_buku)}, dipindah ${rp(r.dipindah)} dari ${r.asal.map((x) => x.akun).join("+")}`).join("; "));
  log("KB1-3 Admin — Siapkan pindah saldo (pop-up) → Siapkan usulan");
  await tid(p, "ps-prepare").click();
  await tid(p, "ps-prepare-form").waitFor({ timeout: 10000 });
  await sleep(1500);
  await shot(p, "13_kb1_siapkan_popup");
  log(`  pilihan akun: ${(await Promise.all(pv.rekening.map(async (r) => `${r.nama} = "${await teks(tid(p, `ps-prepare-account-${r.id}`))}"`))).join("; ")}`);
  log(`  ringkasan: "${await teks(tid(p, "ps-prepare-summary"))}"`);
  await tid(p, "ps-prepare-submit").click();
  await sleep(4500);
  const us = (await api(ADMIN, "GET", `/kas-per-rekening/usulan?entity_id=${ENT}`)).body.items[0];
  log(`  [API] usulan ${us.id}: status ${us.status}, disiapkan ${us.disiapkan_oleh}; kontrol untuk Admin: ${JSON.stringify(us.kontrol)}`);
  const akunBaru = (await api(ADMIN, "GET", `/gl/accounts?entity_id=${ENT}&active_only=true`)).body;
  const sub = (Array.isArray(akunBaru) ? akunBaru : akunBaru.items || []).filter((a) => /^1-11[01]0-\d\d$/.test(a.code || ""));
  log(`  [API] sub-akun dibuat saat disiapkan: ${sub.map((a) => `${a.code} ${a.name} is_cash=${a.is_cash}`).join("; ") || "(tidak terbaca)"}`);
  await tid(p, `ps-proposal-${us.id}`).scrollIntoViewIfNeeded();
  await sleep(800);
  await shot(p, "14_kb1_usulan_menunggu_setujui_mati_untuk_penyiap");
  log(`  tombol Setujui nonaktif: ${await tid(p, `ps-approve-${us.id}`).isDisabled().catch(() => "?")}; alasan: "${await teks(tid(p, `ps-approve-why-${us.id}`))}"`);
  log(`  tata letak alasan: ${await ukurBungkus(tid(p, `ps-approve-why-${us.id}`))}`);
  log(`  bilah: "${await teks(tid(p, "ps-mode"))}" · alasan Siapkan mati: "${await teks(tid(p, "ps-prepare-why"))}"`);
  await c.close();
}

// ═══ KB1 — pindah saldo: orang kedua (Finance) menyetujui; 409 ══════════════════════════════════════════════════════
async function ps2(browser) {
  const us = (await api(FIN, "GET", `/kas-per-rekening/usulan?entity_id=${ENT}`)).body.items.find((u) => u.status === "menunggu");
  log(`KB1-4 Finance — usulan ${us.id} menunggu; kontrol untuk Finance: ${JSON.stringify(us.kontrol)}`);
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, FIN);
  await view(p, "approval-inbox", 8000);
  const chip = tid(p, "approval-inbox-backlog-pindah_saldo_kas");
  try {
    await chip.waitFor({ timeout: 15000 });
    await chip.scrollIntoViewIfNeeded();
    await shot(p, "15_kb1_pusat_persetujuan_antrean_pindah_saldo");
    log(`  antrean di Pusat Persetujuan: "${await teks(chip)}", bisa diklik: ${!(await chip.isDisabled())}`);
    if (await chip.isDisabled()) throw new Error("chip antrean nonaktif untuk Finance");
    await chip.click();
    await tid(p, "kas-per-rekening-view").waitFor({ timeout: 15000 });
    log(`  klik antrean → layar Akun per rekening (${p.url().replace(BASE, "")})`);
  } catch (e) {
    log(`  TEMUAN/GALAT antrean: ${e.message.slice(0, 200)} — buka layar langsung`);
    await view(p, "kas-per-rekening", 7000);
  }
  await tid(p, `ps-approve-${us.id}`).waitFor({ timeout: 20000 });
  await sleep(1500);
  await tid(p, `ps-approve-${us.id}`).click();
  await tid(p, "ps-approve-summary").waitFor({ timeout: 20000 });
  await sleep(1500);
  await shot(p, "16_kb1_setujui_popup_angka_terbaru");
  log(`  pop-up Setujui: "${await teks(tid(p, "ps-approve-summary"))}"`);
  // 409 — kas baru di PT ini sesudah pop-up dibuka (lewat API, seperti "tab lain").
  const kas = await api(ADMIN, "POST", "/cash-transactions", { cash_type: "kas_kecil", direction: "out", amount: 150000,
    category: "operasional", description: "Beli air galon & tisu toko (uji 409 pindah saldo)", entity_id: ENT,
    account_id: (await rekening()).find((a) => a.cash_type === "kas_kecil").id }, { "Idempotency-Key": `uji-kb1-409-${Date.now()}` });
  log(`  [API] kas baru sesudah pop-up dibuka: HTTP ${kas.status} ${kas.body.number || ""} ${rp(kas.body.amount)} (Kas Toko KSC, keluar)`);
  await tid(p, "ps-approve-submit").click();
  await tid(p, "ps-approve-form-error").waitFor({ timeout: 15000 });
  await tid(p, "ps-approve-summary").waitFor({ timeout: 15000 });
  await sleep(1500);
  await shot(p, "17_kb1_setujui_409_angka_berubah");
  log(`  galat di pop-up: "${await teks(tid(p, "ps-approve-form-error"))}"; angka dimuat ulang: "${await teks(tid(p, "ps-approve-total"))}"`);
  await tid(p, "ps-approve-submit").click();
  await tid(p, "ps-approve-form").waitFor({ state: "detached", timeout: 30000 });
  await sleep(4000);
  const u2 = (await api(FIN, "GET", `/kas-per-rekening/usulan?entity_id=${ENT}`)).body.items.find((u) => u.id === us.id);
  log(`  [API] sesudah Setujui: usulan ${u2.status}, diputus ${u2.diputus_oleh || u2.disetujui_oleh || ""}, jurnal ${u2.journal_number || u2.journal_id || ""}, dipindah ${rp(u2.total_dipindah || u2.dipindah)}`);
  await p.evaluate(() => window.scrollTo(0, 0));   // potret satu halaman penuh dari atas (bila tergulir, kepala ikut bergeser)
  await sleep(800);
  await shot(p, "18_kb1_akun_per_rekening_sesudah_aktif", true);
  log(`  bilah: "${await teks(tid(p, "ps-mode"))}"; cek: "${await teks(tid(p, "ps-active-check"))}"`);
  await c.close();
  await cekSaldo("sesudah pindah saldo disetujui (sub-akun = buku kas; akun lama)");
}

// ═══ KB1 — Rekening & Saldo sesudah aktif ═══════════════════════════════════════════════════════════════════════
async function ps3(browser) {
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, ADMIN);
  log("KB1-5 Admin — Rekening & Saldo sesudah PT aktif");
  await view(p, "bank-accounts", 7000);
  await shot(p, "19_kb1_rekening_sesudah_aktif");
  log(`  baris alat: "${await teks(tid(p, "bank-gl-mode"))}"`);
  const rek = await rekening();
  for (const a of rek) log(`  kartu ${a.name}: "${await teks(tid(p, `bank-gl-${a.id}`))}" · [API] gl_account_code ${a.gl_account_code}, aktif ${a.akun_per_rekening_aktif}, sejak ${a.akun_per_rekening_sejak}`);
  const bca = rek.find((a) => a.cash_type === "kas_besar");
  await tid(p, `bank-card-${bca.id}`).click();
  await tid(p, "bank-ledger-edit").waitFor({ timeout: 15000 });
  await tid(p, "bank-ledger-edit").click();
  await tid(p, "bank-form-gl").waitFor({ timeout: 15000 });
  await sleep(1200);
  await shot(p, "20_kb1_form_ubah_rekening_akun_hanya_baca");
  log(`  form Ubah: "${await teks(tid(p, "bank-form-gl"))}"`);
  await c.close();
}

// ═══ Pindah Dana — dua tahap (Admin) + kontrol dua orang ═════════════════════════════════════════════════════════
async function pd1(browser) {
  const rek = await rekening();
  const bca = rek.find((a) => a.cash_type === "kas_besar"), toko = rek.find((a) => a.cash_type === "kas_kecil");
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, ADMIN);
  log("PD-1 Admin — Kas & Bank › Pindah Dana › + Pindah Dana: setor tunai Kas Toko → BCA, Rp 5.000.000, biaya Rp 6.500, terima besok");
  await view(p, "fund-transfers", 6500);
  await tid(p, "ft-create").click();
  await tid(p, "ft-form").waitFor({ timeout: 10000 });
  await sleep(1500);
  await pilihNilai(p, "ft-form-from", toko.id);
  await pilihNilai(p, "ft-form-to", bca.id);
  await tid(p, "ft-form-amount").fill("5000000");
  await tid(p, "ft-form-fee").fill("6500");
  await pilihHari(p, "ft-form-receive-date", Number(besok().slice(8)));
  await tid(p, "ft-form-note").fill("Setor tunai hasil penjualan toko ke BCA (setor sore, masuk besok)");
  await sleep(800);
  await shot(p, "21_pd_form_dua_tahap");
  log(`  ringkasan form: "${await teks(tid(p, "ft-form-summary"))}"`);
  await tid(p, "ft-form-submit").click();
  await tid(p, "ft-form").waitFor({ state: "detached", timeout: 20000 });
  await sleep(3500);
  const d1 = (await api(ADMIN, "GET", `/fund-transfers?entity_id=${ENT}`)).body.items[0];
  log(`  [API] ${d1.number}: status ${d1.status}, nominal ${rp(d1.nominal)}, biaya ${rp(d1.biaya)}, kirim ${d1.tanggal_kirim}, rencana terima ${d1.tanggal_terima}`);
  await shot(p, "22_pd_daftar_dalam_perjalanan");
  log(`  baris: ${(await teks(tid(p, `ft-row-${d1.id}`))).slice(0, 240)}`);
  await cekSaldo(`sesudah ${d1.number} dikirim (dalam perjalanan: transit 1-1150 terisi)`);
  log(`PD-2 Admin — Terima ${d1.number}: pop-up tanggal (dana sudah masuk hari ini → tanggal diganti ${hariIni()})`);
  await tid(p, `ft-receive-${d1.id}`).click();
  await tid(p, "ft-receive-form").waitFor({ timeout: 10000 });
  await sleep(800);
  log(`  tanggal bawaan pop-up: "${await teks(tid(p, "ft-receive-date"))}"`);
  await pilihHari(p, "ft-receive-date", Number(hariIni().slice(8)));
  await shot(p, "23_pd_terima_popup_tanggal");
  await tid(p, "ft-receive-submit").click();
  await tid(p, "ft-receive-form").waitFor({ state: "detached", timeout: 20000 });
  await sleep(3500);
  const d1b = (await api(ADMIN, "GET", `/fund-transfers/${d1.id}`)).body;
  log(`  [API] ${d1b.number}: status ${d1b.status}, diterima ${d1b.tanggal_diterima}, kas ${(d1b.kas || []).map((k) => `${k.number} ${k.direction} ${rp(k.amount)}`).join(", ")}`);
  await shot(p, "24_pd_daftar_selesai");
  await cekSaldo(`sesudah ${d1.number} diterima`);

  log("PD-3 Admin — Pengaturan › Persetujuan › Kontrol dua orang: \"Pindah dana antar rekening\" = Harus dua orang (Sukacita)");
  await view(p, "settings-dual-control", 7000);
  log(`  lapisan: "${await teks(tid(p, "dual-scope"))}"`);
  const row = tid(p, "dual-row-pindah_dana");
  await row.scrollIntoViewIfNeeded();
  await pilihNilai(p, "dual-min-pindah_dana", "2");
  await tid(p, "dual-save").click();
  await tid(p, "dual-save-confirm-reason").waitFor({ timeout: 10000 });
  await tid(p, "dual-save-confirm-reason").fill("Uji tangkapan Kas & Bank 1 — Pindah Dana KSC butuh orang kedua");
  await tid(p, "dual-save-confirm-confirm").click();
  await sleep(3500);
  await row.scrollIntoViewIfNeeded();
  await shot(p, "25_pd_kontrol_dua_orang_pindah_dana");
  log(`  baris: "${await teks(row)}"; pesan: "${await teks(tid(p, "dual-ok"))}"`);
  await c.close();
}

// ═══ Pindah Dana — menunggu persetujuan (Finance membuat) ═════════════════════════════════════════════════════════
async function pd2(browser) {
  const rek = await rekening();
  const bca = rek.find((a) => a.cash_type === "kas_besar"), toko = rek.find((a) => a.cash_type === "kas_kecil");
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, FIN);
  log("PD-4 Finance — + Pindah Dana: isi kas kecil BCA → Kas Toko, Rp 2.000.000, sekali jalan (kontrol 2 orang)");
  await view(p, "fund-transfers", 6500);
  await tid(p, "ft-create").click();
  await tid(p, "ft-form").waitFor({ timeout: 10000 });
  await sleep(1500);
  await pilihNilai(p, "ft-form-from", bca.id);
  await pilihNilai(p, "ft-form-to", toko.id);
  await tid(p, "ft-form-amount").fill("2000000");
  await tid(p, "ft-form-note").fill("Isi kas kecil toko minggu ini");
  await sleep(600);
  log(`  ringkasan form: "${await teks(tid(p, "ft-form-summary"))}"`);
  await tid(p, "ft-form-submit").click();
  await tid(p, "ft-form").waitFor({ state: "detached", timeout: 20000 });
  await sleep(3500);
  const d2 = (await api(FIN, "GET", `/fund-transfers?entity_id=${ENT}`)).body.items[0];
  log(`  [API] ${d2.number}: status ${d2.status}, kas ${(d2.kas || []).length}; kontrol untuk Finance ${JSON.stringify(d2.kontrol)}`);
  await shot(p, "26_pd_menunggu_setujui_mati_untuk_pembuat");
  log(`  tombol Setujui nonaktif: ${await tid(p, `ft-approve-${d2.id}`).isDisabled().catch(() => "?")}; catatan: "${await teks(tid(p, `ft-action-note-${d2.id}`))}"`);
  log(`  tata letak catatan: ${await ukurBungkus(tid(p, `ft-action-note-${d2.id}`))}`);
  await c.close();
}

// ═══ Pindah Dana — Admin menyetujui, pratinjau, batal; Transaksi Kas ═══════════════════════════════════════════════
async function pd3(browser) {
  const daftar = (await api(ADMIN, "GET", `/fund-transfers?entity_id=${ENT}`)).body.items;
  const d2 = daftar.find((d) => d.status === "menunggu_persetujuan");
  const d1 = daftar.find((d) => d.tanggal_terima !== d.tanggal_kirim) || daftar[daftar.length - 1];
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, ADMIN);
  log(`PD-5 Admin — Setujui ${d2.number} (dibuat Finance)`);
  await view(p, "fund-transfers", 6500);
  await tid(p, `ft-approve-${d2.id}`).click();
  await tid(p, "ft-approve-confirm").waitFor({ timeout: 10000 });
  await sleep(800);
  await shot(p, "27_pd_setujui_konfirmasi");
  log(`  konfirmasi: "${await teks(tid(p, "ft-approve-confirm-message"))}"`);
  await tid(p, "ft-approve-confirm-confirm").click();
  await sleep(4500);
  const d2b = (await api(ADMIN, "GET", `/fund-transfers/${d2.id}`)).body;
  log(`  [API] ${d2b.number}: status ${d2b.status}, kas ${(d2b.kas || []).map((k) => `${k.number} ${k.direction} ${rp(k.amount)}`).join(", ")}`);
  await shot(p, "28_pd_daftar_sesudah_disetujui");
  await cekSaldo(`sesudah ${d2.number} disetujui`);

  log(`PD-6 Admin — pratinjau dokumen ${d1.number} (klik nomor)`);
  await tid(p, `ft-open-${d1.id}`).click();
  await tid(p, "doc-preview-fund-transfer").waitFor({ timeout: 15000 });
  await sleep(2500);
  await shot(p, "29_pd_pratinjau_pdn");
  log(`  pratinjau: judul "${await teks(tid(p, "doc-preview-title"))}", kas: ${(await teks(tid(p, "doc-preview-ft-cash"))).slice(0, 300)}`);
  log(`  riwayat: "${await teks(tid(p, "doc-preview-ft-history"))}"`);
  log(`  tombol kaki: Jejak ${await tid(p, "doc-preview-trace").count()}, Buka layar penuh ${await tid(p, "doc-preview-full").count()}`);
  await p.keyboard.press("Escape");
  await sleep(1000);

  log(`PD-7 Admin — Batal ${d2b.number} beralasan`);
  await tid(p, `ft-cancel-${d2.id}`).click();
  await tid(p, "ft-cancel-reason").waitFor({ timeout: 10000 });
  await tid(p, "ft-cancel-reason-reason").fill("Kas kecil toko ternyata masih cukup minggu ini");
  await sleep(600);
  await shot(p, "30_pd_batal_alasan");
  log(`  pesan batal: "${await teks(tid(p, "ft-cancel-reason-message"))}"`);
  await tid(p, "ft-cancel-reason-confirm").click();
  await sleep(4500);
  const d2c = (await api(ADMIN, "GET", `/fund-transfers/${d2.id}`)).body;
  log(`  [API] ${d2c.number}: status ${d2c.status}, alasan "${d2c.alasan_batal || ""}", kas ${(d2c.kas || []).map((k) => `${k.number} ${k.status || ""}`).join(", ")}`);

  log("PD-8 Admin — Transaksi Kas › Catat Transaksi: kategori tanpa Transfer/Top-up + \"Pakai Pindah Dana\"");
  await view(p, "cash-management", 7000);
  await tid(p, "create-cash-button").click();
  await tid(p, "cash-form").waitFor({ timeout: 10000 });
  await sleep(1200);
  await shot(p, "31_kas_form_tanpa_transfer_pakai_pindah_dana");
  log(`  petunjuk: "${await teks(tid(p, "cash-fund-transfer-link"))}"`);
  await tid(p, "cash-category-select").click();
  await sleep(800);
  await shot(p, "32_kas_form_daftar_kategori");
  const opsi = await p.locator('[data-testid^="cash-category-select-option-"]').allInnerTexts();
  log(`  kategori: ${opsi.map(satu).join(" · ")} — Transfer/Top-up ${opsi.some((o) => /transfer|top/i.test(o)) ? "MASIH ADA" : "tidak ada"}`);
  await p.keyboard.press("Escape");
  await sleep(500);
  if (await tid(p, "cash-form").count()) { await tid(p, "cancel-cash-button").click().catch(() => {}); await sleep(800); }
  await tid(p, "cash-txn-search").fill("PDN");
  await sleep(3500);
  await shot(p, "33_kas_daftar_kas_pindah_dana");
  const sumber = await p.locator('[data-testid^="cash-source-row-"]').allInnerTexts();
  log(`  sumber kas: ${sumber.map(satu).slice(0, 6).join(" | ")}`);
  const anul = await p.getByText(/Anulir lewat Pindah Dana/).allInnerTexts().catch(() => []);
  log(`  "Anulir lewat Pindah Dana": ${anul.length} baris${anul[0] ? ` — "${satu(anul[0])}"` : ""}`);
  const catatanAnulir = p.locator('[data-testid^="void-cash-note-"]').first();
  if (await catatanAnulir.count()) log(`  tata letak "Anulir lewat …": ${await ukurBungkus(catatanAnulir)}`);
  await c.close();
  await cekSaldo("akhir (sesudah Pindah Dana & pembatalan)");
}

// ═══ Cek API tambahan (tanpa layar) ═════════════════════════════════════════════════════════════════════════════════
async function jurnal(id) {
  const j = (await api(ADMIN, "GET", `/gl/journal/${id}`)).body;
  const baris = (j.lines || []).map((l) => `${l.account_code} ${l.debit ? "D " + rp(l.debit) : "K " + rp(l.credit)}`).join(" / ");
  return `${j.number || id} tgl ${String(j.date || j.entry_date || "").slice(0, 10)} [${baris}]`;
}
async function cek() {
  const { execFileSync } = require("child_process");
  log("CEK — jurnal & data di balik layar");
  const us = (await api(ADMIN, "GET", `/kas-per-rekening/usulan?entity_id=${ENT}`)).body.items[0];
  log(`  pindah saldo ${us.id}: ${us.status}, disiapkan ${us.disiapkan_oleh}, disetujui ${us.disetujui_oleh}, tanggal jurnal ` +
    `${us.tanggal_jurnal}, kas lama ditautkan ${us.kas_ditautkan}; jurnal ${await jurnal(us.journal_entry_id)}`);
  const kasLama = ((us.hitungan_disiapkan || {}).kas_tanpa_rekening || {}).tunggal || [];
  const ids = kasLama.flatMap((t) => t.kas_ids);
  const py = `from pymongo import MongoClient\nimport json,sys\ndb=MongoClient()["test_database"]\n` +
    `print(json.dumps([(c["number"], c.get("account_id")) for c in db.cash_transactions.find({"id": {"$in": json.loads(sys.argv[1])}})]))`;
  log(`  kas lama tanpa rekening sesudah disetujui (number, account_id): ${execFileSync("python3", ["-c", py, JSON.stringify(ids)]).toString().trim()}`);
  for (const d of (await api(ADMIN, "GET", `/fund-transfers?entity_id=${ENT}`)).body.items.reverse()) {
    const full = (await api(ADMIN, "GET", `/fund-transfers/${d.id}`)).body;
    log(`  ${full.number} (${full.status}; transit ${full.akun_transit || "-"}, beban bank ${full.akun_beban_bank || "-"}):`);
    for (const k of full.kas || []) {
      log(`    ${k.number} ${k.peran} ${k.direction} ${rp(k.amount)} ${k.account_name} → ${await jurnal(k.journal_entry_id)}` +
        (k.void_journal_entry_id ? ` · pembalik ${await jurnal(k.void_journal_entry_id)}` : ""));
    }
  }
  const tolak = await api(ADMIN, "POST", "/cash-transactions", { cash_type: "kas_kecil", direction: "out", amount: 1000,
    category: "transfer", description: "Uji: kategori Transfer/Top-up harus ditolak", entity_id: ENT },
  { "Idempotency-Key": `uji-kb1-transfer-${Date.now()}` });
  log(`  kas manual kategori "transfer" (D3): HTTP ${tolak.status} "${typeof tolak.body === "object" ? tolak.body.detail : tolak.body}"`);
}

/** Kembalikan pengaturan yang diubah tangkapan: Kontrol dua orang "Pindah dana antar rekening" PT KSC → bawaan sistem. */
async function pulih() {
  const r = await api(ADMIN, "POST", "/config/values/reset", { key: "kontrol.pindah_dana.min_orang", scope_type: "entity",
    scope_id: ENT, reason: "Selesai tangkapan Kas & Bank 1 — kembali ke bawaan sistem" });
  const aturan = (await api(ADMIN, "GET", `/kontrol/aturan?entity_id=${ENT}`)).body;
  const row = (aturan.rows || []).find((x) => x.aksi === "pindah_dana") || {};
  log(`PULIH — kontrol.pindah_dana.min_orang KSC dikembalikan ke bawaan: HTTP ${r.status}; sekarang min_orang "${row.min_orang}" (sumber ${row.sumber})`);
}

const FASE = { f1, f1s, ps1, ps2, ps3, pd1, pd2, pd3, cek, pulih };
(async () => {
  const pilih = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(FASE);
  const browser = await chromium.launch();
  for (const f of pilih) {
    log(`── fase ${f} (${new Date().toISOString()})`);
    try { await FASE[f](browser); } catch (e) { log(`  GALAT fase ${f}: ${e.message.slice(0, 400)}`); break; }
  }
  await browser.close();
})();
