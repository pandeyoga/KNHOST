// Kas & Bank bagian 3 (C1 kas kasir, C2 dana tetap kas kecil, C3 opname kas) — tangkapan untuk pemilik (lingkungan uji
// lokal, data acuan; BUKAN data nyata). Prasyarat: backend :8001 + frontend :3000 menyala pada cabang, DB
// `test_database` berisi data acuan (`bash scripts/dev_restore_demo.sh`). Tanpa skrip penyiapan terpisah: data dibuat di
// sini (lewat layar, atau lewat API akun peran untuk langkah yang bukan bagian 3 — panjar/LPJ, isi ulang pertama).
//
// Akun: PENCATAT / PENGHITUNG Finance `finance@` (Sri Mulyani — cash.view/create/configure/approve, ar_receipt.create,
// cash_advance.*) · PENYETUJU Manajer `manager@` (Dewi Manager — cash.approve, cash_advance.approve/disburse,
// cash_settlement.approve/pay). Admin hanya untuk bacaan API (jurnal, buku besar). PT Sukacita Textile (KSC, `ent_ksc`);
// PT tanpa kas kasir untuk pembanding kwitansi: Kanda Fabric (`ent_kanda`). Tidak ada pengaturan yang diubah.
//
// Fase (berurutan; `node tangkap_kb3.js <fase…>`, tanpa argumen = semua):
//   awal  API — keadaan awal PT KSC (rekening, saldo akun 1-1105/1-1110/1-1290/6-9200, opname, jatuh tempo).
//   r1    Finance — Rekening & Saldo › Tambah Akun › Kas tunai › Jenis kas: Kas Kasir → kartu "Kas kasir".
//   kw    Finance — Piutang › Terima pembayaran tunai → rekening penerima terisi Kas Kasir; API kwitansi KANDA (tanpa
//         kasir) → kas kecil seperti dulu.
//   dt1   Finance — Tambah Akun › Kas Kecil, Dana tetap Rp 2.000.000, Lokasi Soreang → kartu (Dana tetap, Lokasi, Isi
//         ulang, Opname).
//   dt2   API — isi ulang pertama Rp 2.000.000 dari BCA; panjar PD-1 Rp 500.000 cair → LPJ Rp 450.000 disetujui → sisa
//         Rp 50.000 dikembalikan; panjar PD-2 Rp 300.000 cair (belum LPJ).
//   dt3   Finance — Kas Kecil › chip Dana tetap (posisi, rincian) → Isi ulang (pop-up) → Pindah Dana berlencana isi ulang.
//   op1   Finance — kartu Kas Kasir › Opname → Hitung per pecahan (kurang) → hasil → baris menunggu (Setujui/Tolak mati);
//         opname kedua (lebih) di Kas Toko KSC lewat API.
//   op2   Manajer — Pusat Persetujuan › antrean opname → Opname Kas → Setujui piutang karyawan (pemilih karyawan) →
//         Setujui opname lebih (selisih kas).
//   op3   Finance — Hitung kas Kas Kecil Soreang = saldo buku → selesai tanpa jurnal; Batal penghitung (API kontrol).
//   op4   Manajer — Batalkan opname yang disetujui (alasan) → Dibatalkan, jurnal pembalik.
//   op5   Manajer — saringan Perlakuan = Piutang karyawan; pratinjau OPK → Jejak.
//   meja  API — Meja Keuangan antrean "Opname kas jatuh tempo" (data acuan: penanda aktif = hari ini → kosong, dilewati).
//   cek   API — ringkasan akhir (saldo akun, dana tetap, opname, jurnal).
const { chromium } = require("playwright");
const fs = require("fs");
const { execFileSync } = require("child_process");
const DIR = __dirname;
const OUT = DIR + "/tangkapan";
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const API = "http://localhost:8001/api";
const ENT = "ent_ksc", ENT_LAIN = "ent_kanda";
const ADMIN = "admin@kainnusantara.id", FIN = "finance@kainnusantara.id", MGR = "manager@kainnusantara.id";
const LOGF = DIR + "/tangkap_kb3_log.txt";
const DATAF = DIR + "/kb3_data.json";
const HARI = new Date().toISOString().slice(0, 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const tid = (p, id) => p.locator(`[data-testid="${id}"]`);
const clean = (p) => p.evaluate(() => document.querySelectorAll("iframe#webpack-dev-server-client-overlay").forEach((e) => e.remove())).catch(() => {});
const rp = (x) => "Rp " + Number(x || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const satu = (s) => String(s || "").replace(/\s+/g, " ").trim();
function log(s) { console.log(s); fs.appendFileSync(LOGF, s + "\n"); }
const muat = () => (fs.existsSync(DATAF) ? JSON.parse(fs.readFileSync(DATAF, "utf8")) : {});
const simpan = (patch) => { const d = { ...muat(), ...patch }; fs.writeFileSync(DATAF, JSON.stringify(d, null, 2)); return d; };
let nKunci = 0;
const kunci = (s) => `kb3-${s}-${Date.now()}-${++nKunci}`;

// ── API ────────────────────────────────────────────────────────────────────────────────────────────────────────────
const TOK = {};
async function api(email, method, path, body, { ent = ENT, extra = {} } = {}) {
  if (!TOK[email]) {
    const t = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: "demo12345" }) }).then((r) => r.json());
    TOK[email] = t.token;
  }
  const h = { Authorization: `Bearer ${TOK[email]}`, "X-Entity-Id": ent, "Content-Type": "application/json", ...extra };
  if (method !== "GET" && !h["Idempotency-Key"]) h["Idempotency-Key"] = kunci(path.replace(/[^a-z0-9]+/gi, "-").slice(0, 40));
  const r = await fetch(`${API}${path}`, { method, headers: h, body: body ? JSON.stringify(body) : undefined });
  const ct = r.headers.get("content-type") || "";
  return { status: r.status, body: ct.includes("json") ? await r.json() : await r.text() };
}
const det = (r) => (typeof r.body === "object" ? (r.body.detail ? JSON.stringify(r.body.detail) : "") : String(r.body).slice(0, 200));
const rekening = async (ent = ENT) => (await api(ADMIN, "GET", `/bank-accounts?entity_id=${ent}`, null, { ent })).body;
const rek = async (id, ent = ENT) => (await rekening(ent)).find((a) => a.id === id);
async function saldoAkun(kode, ent = ENT) {
  const r = await api(ADMIN, "GET", `/gl/accounts/${kode}/ledger?entity_id=${ent}`, null, { ent });
  return r.status === 200 ? Number(r.body.balance || 0) : NaN;
}
const AKUN = ["1-1100", "1-1105", "1-1110", "1-1290", "6-9200"];
async function saldoSemua(ent = ENT) {
  const out = {};
  for (const k of AKUN) out[k] = await saldoAkun(k, ent);
  return out;
}
const ringAkun = (s) => AKUN.map((k) => `${k} ${rp(s[k])}`).join(", ");
async function jurnal(id) {
  if (!id) return "(tanpa jurnal)";
  const j = (await api(ADMIN, "GET", `/gl/journal/${id}`)).body;
  const baris = (j.lines || []).map((l) => `${l.account_code} ${l.debit ? "D " + rp(l.debit) : "K " + rp(l.credit)}`).join(" / ");
  return `${j.number || id} (${j.status || ""}, ${j.source_type || ""}) tgl ${String(j.date || j.entry_date || "").slice(0, 10)} [${baris}]`;
}
function py(code) {
  const pre = `from pymongo import MongoClient\nimport json\ndb=MongoClient("mongodb://localhost:27017")["test_database"]\n`;
  return execFileSync("python3", ["-c", pre + code]).toString().trim();
}
const jumlahJurnal = (ent = ENT) => Number(py(`print(db.journal_entries.count_documents({"entity_id": "${ent}"}))`));
async function kasRekening(id) {
  const r = await api(ADMIN, "GET", `/bank-accounts/${id}/ledger`);
  return r.body || {};
}
async function opname(id, email = MGR) { return (await api(email, "GET", `/cash-counts/${id}`)).body; }
async function posisiDT(id) { return (await api(FIN, "GET", `/kas-kecil/dana-tetap/${id}`)).body; }
const ringDT = (p) => `dana tetap ${rp(p.dana_tetap)}, saldo buku ${rp(p.saldo_buku)}, sisa panjar ${rp(p.panjar_belum_lpj)}, ` +
  `usulan ${rp(p.usulan_isi_ulang)} → saldo + sisa panjar + usulan = ${rp(Number(p.saldo_buku) + Number(p.panjar_belum_lpj) + Number(p.usulan_isi_ulang))} ` +
  `(${Math.round((Number(p.saldo_buku) + Number(p.panjar_belum_lpj) + Number(p.usulan_isi_ulang)) * 100) === Math.round(Number(p.dana_tetap) * 100) ? "= dana tetap" : "≠ dana tetap"}); ` +
  `bisa isi ulang ${p.bisa_isi_ulang}${p.alasan_isi_ulang ? ` ("${p.alasan_isi_ulang}")` : ""}`;

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
async function pilihNilai(page, testId, value, { buka = true } = {}) {
  if (buka) { await tid(page, testId).click(); await sleep(500); }
  const opt = tid(page, `${testId}-option-${value}`).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(500);
}
async function teks(loc) { return satu(await loc.innerText({ timeout: 5000 }).catch(() => "")); }
async function konteks(browser) {
  return browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
}
async function toastTeks(p, pola) {
  const t = p.locator("li[role='status'], [data-state='open'][data-swipe-direction]").filter({ hasText: pola }).first();
  await t.waitFor({ timeout: 10000 }).catch(() => {});
  return teks(t);
}
async function sesi(browser, email) {
  const c = await konteks(browser);
  const p = await c.newPage();
  await login(p, email);
  return { c, p };
}
/** Form Tambah Akun (kas tunai): nama, jenis kas, atas nama; dana tetap + lokasi untuk kas kecil. */
async function bukaFormTunai(p, nama, holder) {
  await view(p, "bank-accounts", 7000);
  await tid(p, "bank-add-toggle").click();
  await tid(p, "bank-add-form").waitFor({ timeout: 10000 });
  await sleep(1200);
  await tid(p, "bank-form-name").fill(nama);
  await pilihNilai(p, "bank-form-type", "cash");
  await tid(p, "bank-form-holder").fill(holder);
  await sleep(600);
}
async function kirimRekening(p) {
  const tunggu = p.waitForResponse((r) => r.url().endsWith("/api/bank-accounts") && r.request().method() === "POST", { timeout: 30000 });
  await tid(p, "bank-form-submit").click();
  const r = await tunggu;
  let body = {};
  try { body = await r.json(); } catch (e) { /* bukan json */ }
  return { status: r.status(), body };
}

// ═══ awal ═══════════════════════════════════════════════════════════════════════════════════════════════════════
async function awal() {
  log(`[API] PT KSC rekening awal: ${(await rekening()).map((a) => `${a.name} (${a.id}, ${a.account_type}/${a.cash_type}, saldo ${rp(a.balance)}, ` +
    `akun ${a.gl_account_code || "-"}, akun per rekening ${a.akun_per_rekening_aktif ? "aktif" : "belum"})`).join("; ")}`);
  const s = await saldoSemua();
  log(`[API] saldo akun PT KSC awal: ${ringAkun(s)}; jurnal PT ${jumlahJurnal()}`);
  const cc = (await api(FIN, "GET", `/cash-counts?entity_id=${ENT}`)).body;
  log(`[API] opname PT KSC awal: ${cc.total}; status ${cc.statuses.map((x) => x.label).join("/")}; perlakuan ${JSON.stringify(cc.perlakuan)}`);
  const pen = py(`d=db.system_settings.find_one({"scope":"__migrations__"}) or {}\nprint(d.get("kb3_opname_kas_aktif_sejak",""))`);
  const kv = py(`print(json.dumps(list(db.config_values.find({"key":{"$regex":"^(kontrol|kas)\\\\."}},{"_id":0,"key":1,"scope_id":1,"value":1}))))`);
  log(`[API] penanda opname aktif sejak ${pen}; config_values kontrol.*/kas.* tersimpan: ${kv} (semua bawaan katalog)`);
  const rc = (await api(FIN, "GET", `/bank-accounts/receiving?method=cash&entity_id=${ENT}`)).body;
  log(`[API] rekening penerima tunai KSC awal: ${rc.map((a) => `${a.name}${a.is_default ? " (bawaan)" : ""}`).join(", ")}`);
  simpan({ saldo_awal: s, jurnal_awal: jumlahJurnal() });
}

// ═══ r1 — rekening Kas Kasir ══════════════════════════════════════════════════════════════════════════════════════
async function r1(browser) {
  const { c, p } = await sesi(browser, FIN);
  log("R1 Finance (finance@) — Rekening & Saldo › Tambah Akun › Jenis Kas tunai › Jenis kas");
  await bukaFormTunai(p, "Kas Kasir Toko KSC", "Kasir toko");
  await tid(p, "bank-form-cash-type").click();
  await sleep(800);
  const opsi = (await p.locator('[data-testid^="bank-form-cash-type-option-"]').allInnerTexts()).map(satu);
  log(`  pilihan Jenis kas: ${opsi.join(" · ")}; kalimat bantu: "${await teks(tid(p, "bank-form-cash-type-hint"))}"`);
  await shot(p, "01_rekening_form_jenis_kas_pilihan");
  await pilihNilai(p, "bank-form-cash-type", "kas_kasir", { buka: false });
  await sleep(800);
  log(`  sesudah pilih Kas Kasir: kalimat bantu "${await teks(tid(p, "bank-form-cash-type-hint"))}"; isian Dana tetap ` +
    `${await tid(p, "bank-form-dana-tetap").count() ? "ADA (salah)" : "tidak ada"}; Lokasi kerja ${await tid(p, "bank-form-location").count() ? "ada" : "tidak ada"}`);
  const centang = async (t) => (await p.locator(`[data-testid^="${t}-"]`).evaluateAll((els) => els.filter((e) => e.type === "checkbox")
    .map((e) => `${e.dataset.testid.split("-").pop()}${e.checked ? " ✓" : ""}${e.disabled ? " (nonaktif)" : ""}`))).join(", ");
  log(`  cara bayar dilayani: ${await centang("bank-form-method")}; bawaan penerimaan: ${await centang("bank-form-default")}`);
  await tid(p, "bank-form-sec-id").scrollIntoViewIfNeeded().catch(() => {});
  await shot(p, "02_rekening_form_kas_kasir_terisi");
  const r = await kirimRekening(p);
  await sleep(3500);
  log(`  [API] POST /bank-accounts: HTTP ${r.status} ${r.body.id || ""} "${r.body.name || ""}" account_type ${r.body.account_type} ` +
    `cash_type ${r.body.cash_type} gl_account_code "${r.body.gl_account_code || ""}" default_receiving_methods ${JSON.stringify(r.body.default_receiving_methods)}`);
  log(`  bilah: "${await teks(tid(p, "bank-notice"))}"`);
  const id = r.body.id;
  if (id) {
    const box = tid(p, `bank-card-box-${id}`);
    await box.waitFor({ timeout: 15000 });
    log(`  kartu: "${await teks(box)}"`);
    log(`  lencana jenis: "${await teks(tid(p, `bank-cash-type-${id}`))}"; akun buku besar: "${await teks(tid(p, `bank-gl-${id}`))}"; ` +
      `kaki kartu: ${await tid(p, `bank-card-actions-${id}`).count() ? `"${await teks(tid(p, `bank-card-actions-${id}`))}"` : "tidak ada"}`);
    await shotEl(tid(p, "bank-cards"), "03_kartu_rekening_kas_kasir");
    const a = await rek(id);
    log(`  [API] GET /bank-accounts: ${a.name} cash_type ${a.cash_type}, akun_per_rekening_aktif ${a.akun_per_rekening_aktif}, ` +
      `gl_account_code "${a.gl_account_code || ""}" (mode lama → akun kas bersama jenisnya), saldo ${rp(a.balance)}`);
    const rc = (await api(FIN, "GET", `/bank-accounts/receiving?method=cash&entity_id=${ENT}`)).body;
    log(`  [API] rekening penerima tunai KSC sesudah: ${rc.map((x) => `${x.name}${x.is_default ? " (bawaan)" : ""}`).join(", ")}`);
    simpan({ kasir: { id, name: r.body.name } });
  }
  await c.close();
}

// ═══ kw — kwitansi tunai ═════════════════════════════════════════════════════════════════════════════════════════
// Id data acuan berubah setiap `dev_restore_demo.sh` → dicari dari nama saat skrip mulai (`siapkanId`).
const CUST = { id: "", name: "Konveksi Maju Bersama" };
const CUST_LAIN = { id: "", name: "Toko Tekstil Pasar Baru" };
async function kw(browser) {
  const { kasir } = muat();
  const s0 = await saldoSemua();
  const { c, p } = await sesi(browser, FIN);
  log(`KW Finance — Piutang › ${CUST.name} › Terima pembayaran: Tunai Rp 1.500.000`);
  await view(p, "ar-aging", 8000);
  await tid(p, `ar-aging-receive-${CUST.id}`).click();
  await tid(p, "ar-receipt-modal").waitFor({ timeout: 15000 });
  await sleep(2500);
  await pilihNilai(p, "ar-receipt-method", "cash");
  await sleep(2000);
  await tid(p, "ar-receipt-amount").fill("1500000");
  await sleep(3000);
  log(`  rekening penerima terisi: "${await teks(tid(p, "ar-receipt-account"))}"; kalimat tunai: "${await teks(tid(p, "ar-receipt-cash-hint"))}"`);
  log(`  petunjuk selisih: "${(await teks(tid(p, "ar-receipt-variance-hint"))).slice(0, 220)}"`);
  await tid(p, "ar-receipt-account-field").scrollIntoViewIfNeeded().catch(() => {});
  await shot(p, "04_kwitansi_tunai_rekening_kas_kasir");
  const tunggu = p.waitForResponse((r) => r.url().endsWith("/api/ar-receipts") && r.request().method() === "POST", { timeout: 60000 });
  await tid(p, "ar-receipt-submit").click();
  await sleep(1500);
  if (await tid(p, "payment-variance-dialog").count()) {
    await tid(p, "pv-option-outstanding").click().catch(() => {});
    await sleep(400);
    await pilihNilai(p, "pv-reason", "partial_payment_agreed");
    log(`  pop-up selisih bayar: "${(await teks(tid(p, "pv-sentence"))).slice(0, 200)}" → pilih "outstanding" (sisa tetap piutang), alasan partial_payment_agreed`);
    await tid(p, "pv-submit").click();
    await sleep(1200);
  }
  await tid(p, "ar-receipt-confirm-confirm").waitFor({ timeout: 10000 });
  log(`  konfirmasi: "${await teks(tid(p, "ar-receipt-confirm-message"))}"`);
  await tid(p, "ar-receipt-confirm-confirm").click();
  const resp = await tunggu;
  const k = await resp.json().catch(() => ({}));
  await tid(p, "ar-aging-flash").waitFor({ timeout: 10000 }).catch(() => {});
  await sleep(500);
  await shot(p, "05_kwitansi_tunai_tercatat");
  log(`  bilah: "${await teks(tid(p, "ar-aging-flash"))}"`);
  log(`  [API] POST /ar-receipts: HTTP ${resp.status()} ${k.number} ${rp(k.amount)} method ${k.method} account_id ${k.account_id} ` +
    `(${k.account_id === kasir.id ? "= rekening Kas Kasir" : "BUKAN kasir"}) "${(k.account_snapshot || {}).name}", kas ${k.cash_txn_id}`);
  const kas = py(`print(json.dumps(db.cash_transactions.find_one({"id":"${k.cash_txn_id}"},{"_id":0,"number":1,"account_id":1,"cash_type":1,"account_code":1,"amount":1,"direction":1})))`);
  log(`  [API] kas kwitansi: ${kas}`);
  log(`  [API] jurnal kwitansi: ${await jurnal(k.journal_entry_id)}`);
  const s1 = await saldoSemua();
  log(`  [API] saldo akun sesudah: ${ringAkun(s1)} — 1-1105 naik ${rp(s1["1-1105"] - s0["1-1105"])}, 1-1110 berubah ${rp(s1["1-1110"] - s0["1-1110"])}`);
  log(`  [API] buku rekening Kas Kasir: saldo ${rp((await kasRekening(kasir.id)).balance)}`);
  simpan({ kwitansi: { id: k.id, number: k.number, amount: k.amount } });
  await c.close();

  log(`KW API — PT tanpa kas kasir (KANDA): kwitansi tunai ${CUST_LAIN.name} Rp 1.000.000`);
  const rl = await rekening(ENT_LAIN);
  log(`  [API] rekening KANDA: ${rl.map((a) => `${a.name} ${a.account_type}/${a.cash_type}`).join(", ")} — tanpa kas kasir`);
  const s0l = await saldoSemua(ENT_LAIN);
  const r = await api(FIN, "POST", "/ar-receipts", { customer_id: CUST_LAIN.id, amount: 1000000, method: "cash", entity_id: ENT_LAIN,
    notes: "Tangkapan KB3 — pembanding PT tanpa kasir",
    variance: { kind: "outstanding", reason_code: "partial_payment_agreed", note: "cicilan tunai" } }, { ent: ENT_LAIN });
  const b = r.body || {};
  const tunai = rl.find((a) => a.id === b.account_id) || {};
  log(`  [API] POST /ar-receipts KANDA: HTTP ${r.status} ${b.number || det(r)} account_id ${b.account_id} = "${tunai.name}" (${tunai.cash_type}), ` +
    `jurnal ${await jurnal(b.journal_entry_id)}`);
  const s1l = await saldoSemua(ENT_LAIN);
  log(`  [API] KANDA 1-1110 naik ${rp(s1l["1-1110"] - s0l["1-1110"])}, 1-1105 berubah ${rp(s1l["1-1105"] - s0l["1-1105"])}`);
  simpan({ kwitansi_kanda: { id: b.id, number: b.number } });
}

// ═══ dt1 — rekening kas kecil berdana tetap ═════════════════════════════════════════════════════════════════════
async function dt1(browser) {
  const { c, p } = await sesi(browser, FIN);
  log("DT1 Finance — Tambah Akun › Kas tunai › Kas Kecil, Dana tetap Rp 2.000.000, Lokasi Soreang");
  await bukaFormTunai(p, "Kas Kecil Gudang Soreang", "Kepala gudang Soreang");
  await pilihNilai(p, "bank-form-cash-type", "kas_kecil");
  await tid(p, "bank-form-dana-tetap").fill("2000000");
  await sleep(300);
  await tid(p, "bank-form-location").click();
  await sleep(700);
  const lok = p.locator('[data-testid^="bank-form-location-option-"]').filter({ hasText: "Soreang" }).first();
  await lok.click();
  await sleep(700);
  log(`  jenis kas: "${await teks(tid(p, "bank-form-cash-type"))}"; dana tetap "${await tid(p, "bank-form-dana-tetap").inputValue()}", ` +
    `kalimat "${await teks(tid(p, "bank-form-dana-tetap-hint"))}"; lokasi "${await teks(tid(p, "bank-form-location"))}"`);
  await shot(p, "06_rekening_form_kas_kecil_dana_tetap_lokasi");
  const r = await kirimRekening(p);
  await sleep(3500);
  log(`  [API] POST /bank-accounts: HTTP ${r.status} ${r.body.id || det(r)} cash_type ${r.body.cash_type} dana_tetap ${rp(r.body.dana_tetap)} ` +
    `location_id ${r.body.location_id} (${r.body.location_name || ""})`);
  const id = r.body.id;
  if (id) {
    const box = tid(p, `bank-card-box-${id}`);
    await box.waitFor({ timeout: 15000 });
    log(`  kartu: "${await teks(box)}"`);
    log(`  kaki kartu: "${await teks(tid(p, `bank-card-actions-${id}`))}" — Isi ulang ${await tid(p, `bank-refill-${id}`).count() ? "ada" : "TIDAK ADA"}, ` +
      `Opname ${await tid(p, `bank-opname-${id}`).count() ? "ada" : "TIDAK ADA"}; kartu BCA berkaki ` +
      `${await p.locator(`[data-testid="bank-card-actions-${BCA}"]`).count() ? "ADA (salah)" : "tidak (bank tidak diopname)"}`);
    await shotEl(tid(p, "bank-cards"), "07_kartu_kas_kecil_dana_tetap_lokasi_aksi");
    simpan({ kk: { id, name: r.body.name } });
  }
  await c.close();
}

// ═══ dt2 — data posisi dana tetap (API) ═════════════════════════════════════════════════════════════════════════
let BCA = "", KAS_TOKO = "";
async function pdCair(nominal, kegiatan) {
  // Bisa dilanjutkan: PD dengan kegiatan yang sama di PT KSC dipakai lagi (status apa pun) — tanpa PD ganda.
  const ada = ((await api(FIN, "GET", `/cash-advances?entity_id=${ENT}`)).body || []).find((x) => x.kegiatan === kegiatan);
  let pd = ada;
  if (!pd) {
    const cr = await api(FIN, "POST", "/cash-advances", { entity_id: ENT, divisi: "Gudang", kegiatan, payment_method: "cash",
      lines: [{ description: kegiatan, qty: 1, satuan: "paket", unit_price: nominal }], catatan: "Tangkapan KB3" });
    if (cr.status !== 200) { log(`  GALAT buat PD: HTTP ${cr.status} ${det(cr)}`); return null; }
    pd = cr.body;
  }
  if (pd.status === "draft") pd = (await api(FIN, "POST", `/cash-advances/${pd.id}/submit`)).body;
  const jejak = [];
  for (let i = 0; i < 6 && !["approved", "disbursed", "settled", "closed"].includes(pd.status); i++) {
    let ap = await api(MGR, "POST", `/cash-advances/${pd.id}/approve`, { note: "ok" });
    if (ap.status === 200) { jejak.push(`manager@ → ${ap.body.status}`); pd = ap.body; continue; }
    ap = await api(ADMIN, "POST", `/cash-advances/${pd.id}/approve`, { note: "ok" });
    if (ap.status === 200) { jejak.push(`admin@ → ${ap.body.status} (jenjang Admin menurut Aturan Persetujuan data acuan)`); pd = ap.body; continue; }
    log(`  GALAT setujui ${pd.number}: HTTP ${ap.status} ${det(ap)}`); return null;
  }
  if (jejak.length) log(`  [API] ${pd.number} persetujuan: ${jejak.join("; ")}`);
  if (pd.status === "approved") {
    const ds = await api(MGR, "POST", `/cash-advances/${pd.id}/disburse`, { cash_type: "kas_kecil", account_id: muat().kk.id, note: "Tangkapan KB3" });
    if (ds.status !== 200) { log(`  GALAT cairkan ${pd.number}: HTTP ${ds.status} ${det(ds)}`); return null; }
    pd = ds.body;
  }
  const d = pd.disbursement || {};
  log(`  [API] ${pd.number} ${rp(nominal)} "${kegiatan}": pemohon Sri Mulyani, status ${pd.status}, dicairkan manager@ ` +
    `kas ${d.cash_txn_number} dari rekening ${d.account_id === muat().kk.id ? "Kas Kecil Gudang Soreang" : d.account_id}, jurnal ${d.je_number}`);
  return { id: pd.id, number: pd.number };
}
async function dt2() {
  const { kk } = muat();
  log("DT2 API — isi ulang pertama, panjar & LPJ dari rekening Kas Kecil Gudang Soreang");
  let pos = await posisiDT(kk.id);
  log(`  [API] posisi awal: ${ringDT(pos)}`);
  let isi1 = (pos.riwayat || [])[0];
  if (!isi1) {
    const iu = await api(FIN, "POST", `/kas-kecil/dana-tetap/${kk.id}/isi-ulang`, { sumber_account_id: BCA, catatan: "Pengisian awal dana tetap",
      nominal_dilihat: Number(pos.usulan_isi_ulang) });
    log(`  [API] isi ulang pertama (finance@): HTTP ${iu.status} ${iu.body.number || det(iu)} ${rp(iu.body.nominal)} status ${iu.body.status} jenis ${iu.body.jenis} ` +
      `"${iu.body.jenis_label || ""}"`);
    if (iu.body.status === "menunggu_persetujuan") {
      const ap = await api(MGR, "POST", `/fund-transfers/${iu.body.id}/approve`, {});
      log(`  [API] Pindah Dana disetujui manager@: HTTP ${ap.status} ${ap.body.status}`);
    }
    isi1 = iu.body;
  } else {
    log(`  [API] isi ulang pertama sudah ada: ${isi1.number} ${rp(isi1.nominal)} ${isi1.status}`);
  }
  simpan({ isi1: { id: isi1.id, number: isi1.number } });
  const pd1 = await pdCair(500000, "Perlengkapan bongkar muat gudang Soreang");
  if (!pd1) return;
  const stlAda = ((await api(FIN, "GET", `/cash-advance-settlements?entity_id=${ENT}`)).body || []).find((x) => x.cash_advance_id === pd1.id);
  let stl = stlAda;
  if (!stl) {
    const cr = await api(FIN, "POST", "/cash-advance-settlements", { cash_advance_id: pd1.id, divisi: "Gudang", periode: HARI.slice(0, 7),
      expense_lines: [{ date: HARI, description: "Lakban, tali rafia, plastik roll", category: "office_supplies", amount: 250000 },
        { date: HARI, description: "Konsumsi bongkar muat", category: "lunch_snack_entertainment", amount: 200000 }], catatan: "Tangkapan KB3" });
    if (cr.status !== 200) { log(`  GALAT buat LPJ: HTTP ${cr.status} ${det(cr)}`); return; }
    stl = cr.body;
  }
  if (stl.status === "draft") stl = (await api(FIN, "POST", `/cash-advance-settlements/${stl.id}/submit`)).body;
  if (stl.status === "submitted") {
    const sa = await api(MGR, "POST", `/cash-advance-settlements/${stl.id}/approve`, { note: "ok" });
    if (sa.status !== 200) { log(`  GALAT setujui LPJ: HTTP ${sa.status} ${det(sa)}`); return; }
    stl = sa.body;
  }
  log(`  [API] LPJ ${stl.number} untuk ${pd1.number}: belanja ${rp(stl.total_pengeluaran)} (diajukan finance@, disetujui manager@), status ${stl.status}, ` +
    `sisa ${rp((stl.sisa_dikembalikan || {}).amount)} ${(stl.sisa_dikembalikan || {}).status}`);
  if ((stl.sisa_dikembalikan || {}).status === "open") {
    const rr = await api(MGR, "POST", `/cash-advance-settlements/${stl.id}/return-remainder`, { cash_type: "kas_kecil", account_id: kk.id });
    log(`  [API] terima sisa panjar ke Kas Kecil Gudang Soreang (manager@): HTTP ${rr.status} ${((rr.body || {}).sisa_dikembalikan || {}).status || det(rr)} ` +
      `kas ${((rr.body || {}).sisa_dikembalikan || {}).cash_txn_number || ""}`);
  }
  const pd2 = await pdCair(300000, "Ongkos angkut kain retur ke Soreang");
  pos = await posisiDT(kk.id);
  log(`  [API] posisi sesudah: ${ringDT(pos)}`);
  log(`  [API] rincian: ${(pos.rincian || []).map((r) => `${r.label} ${r.nomor} pengaruh ${rp(r.pengaruh)}`).join("; ")} — jumlah ${rp(pos.total_rincian)}; ` +
    `panjar: ${(pos.panjar || []).map((x) => `${x.nomor} ${x.keadaan_label} ${rp(x.sisa ?? x.nominal)}`).join("; ")}; ` +
    `riwayat isi ulang: ${(pos.riwayat || []).map((x) => `${x.number} ${rp(x.nominal)} ${x.status}`).join("; ")}`);
  simpan({ pd1, pd2, lpj1: { id: stl.id, number: stl.number } });
}

// ═══ dt3 — chip Dana tetap + Isi ulang ══════════════════════════════════════════════════════════════════════════
async function dt3(browser) {
  const { kk } = muat();
  const pos0 = await posisiDT(kk.id);
  const { c, p } = await sesi(browser, FIN);
  log("DT3 Finance — Kas & Bank › Kas Kecil › chip Dana tetap");
  await view(p, "petty-cash", 7000);
  await tid(p, "pc-bagian-dana-tetap").click();
  await tid(p, `dt-row-${kk.id}`).waitFor({ timeout: 15000 });
  await sleep(2000);
  log(`  baris: "${await teks(tid(p, `dt-row-${kk.id}`))}"`);
  log(`  catatan rekening tanpa dana tetap: "${await teks(tid(p, "dt-none-note"))}"`);
  await shot(p, "08_kas_kecil_chip_dana_tetap_posisi");
  await tid(p, `dt-open-${kk.id}`).click();
  await tid(p, "dt-detail-modal").waitFor({ timeout: 10000 });
  await sleep(1200);
  log(`  rincian: identitas "${await teks(tid(p, "dt-detail-identity"))}"; sejak "${await teks(tid(p, "dt-detail-since"))}"`);
  log(`  baris rincian: "${await teks(tid(p, "dt-detail-rincian"))}"`);
  log(`  sisa panjar: "${await teks(tid(p, "dt-detail-panjar"))}"; riwayat: "${await teks(tid(p, "dt-detail-history"))}"`);
  await shot(p, "09_dana_tetap_rincian");
  await p.keyboard.press("Escape");
  await sleep(800);
  log("DT3 Finance — Isi ulang (pop-up)");
  await tid(p, `dt-refill-${kk.id}`).click();
  await tid(p, "refill-form").waitFor({ timeout: 10000 });
  await sleep(2000);
  await pilihNilai(p, "refill-source", BCA);
  await sleep(600);
  log(`  pop-up: posisi "${await teks(tid(p, "refill-position"))}"; Nominal isi ulang elemen ${await tid(p, "refill-amount").evaluate((e) => e.tagName)} ` +
    `(input di pop-up: ${await tid(p, "refill-form").locator("input").count()} — catatan saja?)`);
  log(`  sumber: "${await teks(tid(p, "refill-source"))}"; ringkasan "${await teks(tid(p, "refill-summary"))}"`);
  await shot(p, "10_isi_ulang_popup_sumber_nominal_terkunci");
  const tunggu = p.waitForResponse((r) => r.url().includes(`/kas-kecil/dana-tetap/${kk.id}/isi-ulang`), { timeout: 30000 });
  await tid(p, "refill-form-submit").click();
  const resp = await tunggu;
  const d = await resp.json().catch(() => ({}));
  const req = JSON.parse(resp.request().postData() || "{}");
  const tt = await toastTeks(p, /Isi ulang/);
  await sleep(1500);
  await shot(p, "11_isi_ulang_tercatat");
  log(`  toast: "${tt}"`);
  log(`  [API] POST isi-ulang: kiriman ${JSON.stringify(req)}; HTTP ${resp.status()} ${d.number} ${rp(d.nominal)} status ${d.status} jenis ${d.jenis} ` +
    `"${d.jenis_label || ""}" dari ${d.rekening_asal} ke ${d.rekening_tujuan}; nominal = usulan sebelumnya ${rp(pos0.usulan_isi_ulang)} ` +
    `(${Math.round(d.nominal * 100) === Math.round(pos0.usulan_isi_ulang * 100) ? "sama" : "BEDA"})`);
  const pos1 = await posisiDT(kk.id);
  log(`  [API] posisi sesudah isi ulang: ${ringDT(pos1)}`);
  log(`  baris sesudah: "${await teks(tid(p, `dt-row-${kk.id}`))}"`);
  simpan({ isi2: { id: d.id, number: d.number } });
  log("DT3 Finance — Kas & Bank › Pindah Dana: lencana isi ulang");
  await view(p, "fund-transfers", 7000);
  await tid(p, `ft-row-${d.id}`).waitFor({ timeout: 15000 });
  const isi1 = muat().isi1;
  log(`  baris ${d.number}: "${await teks(tid(p, `ft-row-${d.id}`))}"; lencana "${await teks(tid(p, `ft-kind-${d.id}`))}"`);
  if (isi1) log(`  baris ${isi1.number}: lencana "${await teks(tid(p, `ft-kind-${isi1.id}`))}"`);
  await shot(p, "12_pindah_dana_lencana_isi_ulang");
  await c.close();
}

// ═══ op1 — opname kurang di Kas Kasir ═══════════════════════════════════════════════════════════════════════════
async function op1(browser) {
  const { kasir } = muat();
  const { c, p } = await sesi(browser, FIN);
  log("OP1 Finance (penghitung) — Rekening & Saldo: kaki kartu Kas Kasir › Opname");
  await view(p, "bank-accounts", 7000);
  const box = tid(p, `bank-card-box-${kasir.id}`);
  await box.waitFor({ timeout: 15000 });
  log(`  kaki kartu kasir: "${await teks(tid(p, `bank-card-actions-${kasir.id}`))}"`);
  log(`  label selisih buku besar ↔ rekening: "${await teks(tid(p, "bank-gap-label"))}"; KPI Kas & Bank (buku besar) "${await teks(tid(p, "bank-kpi-gl-value"))}", ` +
    `Total Saldo Rekening "${await teks(tid(p, "bank-kpi-total-value"))}"`);
  await shotEl(tid(p, "bank-cards"), "13_kartu_kas_kasir_tombol_opname");
  await tid(p, `bank-opname-${kasir.id}`).click();
  await tid(p, "opk-form").waitFor({ timeout: 15000 });
  await sleep(2500);
  log(`  pindah ke ${p.url().replace(BASE, "")}; rekening terisi "${await teks(tid(p, "opk-form-account"))}"; ` +
    `saldo buku di pop-up: ${/saldo buku/i.test(await teks(tid(p, "opk-form"))) ? "kata 'saldo buku' ada (subjudul)" : "tidak"}`);
  await tid(p, "opk-form-denoms-toggle").click();
  await sleep(500);
  await tid(p, "opk-form-denom-100000").fill("14");
  await tid(p, "opk-form-denom-50000").fill("1");
  await tid(p, "opk-form-note").fill("Hitung tutup toko, disaksikan kepala toko");
  await sleep(600);
  log(`  rincian pecahan: 14 × Rp 100.000 + 1 × Rp 50.000 → "${await teks(tid(p, "opk-form-denoms-total"))}"`);
  await shot(p, "14_opname_hitung_pecahan_sebelum_simpan");
  const tunggu = p.waitForResponse((r) => r.url().endsWith("/api/cash-counts") && r.request().method() === "POST", { timeout: 30000 });
  await tid(p, "opk-form-submit").click();
  const resp = await tunggu;
  const o = await resp.json().catch(() => ({}));
  await tid(p, "opk-form-result").waitFor({ timeout: 10000 });
  await sleep(800);
  await shot(p, "15_opname_hasil_selisih_kurang");
  log(`  hasil: "${await teks(tid(p, "opk-form-result"))}"`);
  log(`  [API] POST /cash-counts: HTTP ${resp.status()} ${o.number} status ${o.status} saldo_buku ${rp(o.saldo_buku)} fisik ${rp(o.jumlah_fisik)} ` +
    `selisih ${rp(o.selisih)} pecahan ${JSON.stringify(o.pecahan)} boleh_piutang ${o.boleh_piutang}`);
  await tid(p, "opk-form-done").click();
  await sleep(2000);
  const row = tid(p, `opk-row-${o.id}`);
  await row.waitFor({ timeout: 15000 });
  log(`  baris: "${await teks(row)}"`);
  log(`  Setujui nonaktif ${await tid(p, `opk-approve-${o.id}`).isDisabled().catch(() => "?")}, Tolak nonaktif ${await tid(p, `opk-reject-${o.id}`).isDisabled().catch(() => "?")}`);
  log(`  kalimat: "${await teks(tid(p, `opk-action-note-${o.id}`))}"`);
  await shot(p, "16_opname_penghitung_setujui_tolak_mati");
  const dk = await opname(o.id, FIN);
  log(`  [API] GET /cash-counts/${o.id} (penghitung): kontrol ${JSON.stringify(dk.kontrol)}`);
  const ap = await api(FIN, "POST", `/cash-counts/${o.id}/approve`, { perlakuan: "selisih_kas" });
  log(`  [API] penghitung mencoba Setujui lewat API: HTTP ${ap.status} ${det(ap)}`);
  simpan({ O1: { id: o.id, number: o.number } });
  await c.close();

  log("OP1 API — opname kedua oleh finance@ di Kas Toko KSC: uang fisik lebih Rp 25.000");
  const a = await rek(KAS_TOKO);
  const r2 = await api(FIN, "POST", "/cash-counts", { account_id: KAS_TOKO, jumlah_fisik: Number(a.balance) + 25000, catatan: "Hitung akhir pekan" });
  log(`  [API] POST /cash-counts: HTTP ${r2.status} ${r2.body.number} saldo buku ${rp(r2.body.saldo_buku)} fisik ${rp(r2.body.jumlah_fisik)} ` +
    `selisih ${rp(r2.body.selisih)} status ${r2.body.status} boleh_piutang ${r2.body.boleh_piutang}`);
  simpan({ O2: { id: r2.body.id, number: r2.body.number } });
}

// ═══ op2 — penyetuju ════════════════════════════════════════════════════════════════════════════════════════════
async function op2(browser) {
  const { O1, O2, kasir } = muat();
  const s0 = await saldoSemua();
  const { c, p } = await sesi(browser, MGR);
  log("OP2 Penyetuju (manager@) — Persetujuan › Pusat Persetujuan: antrean opname");
  await view(p, "approval-inbox", 8000);
  const chip = tid(p, "approval-inbox-backlog-cash_count");
  try {
    await chip.waitFor({ timeout: 15000 });
    await chip.scrollIntoViewIfNeeded();
    log(`  antrean: "${await teks(chip)}", bisa diklik ${!(await chip.isDisabled())}, title "${await chip.getAttribute("title")}"`);
    const lain = p.locator('[data-testid^="approval-inbox-other-"]').filter({ hasText: /OPK/ });
    log(`  "Menunggu di layar lain" baris OPK: ${(await lain.allInnerTexts()).map(satu).filter((x) => x).slice(0, 4).join(" | ") || "tidak tampil"}`);
    await shot(p, "17_pusat_persetujuan_antrean_opname");
    await chip.click();
    await tid(p, "cash-counts-view").waitFor({ timeout: 15000 });
    await sleep(3000);
    log(`  klik antrean → ${p.url().replace(BASE, "")}; Status terpilih "${await teks(tid(p, "opk-status"))}"`);
  } catch (e) {
    log(`  TEMUAN/GALAT antrean: ${e.message.slice(0, 200)} — buka layar langsung`);
    await shot(p, "galat_op2_pusat_persetujuan");
    await view(p, "cash-counts", 7000);
  }
  const bl = await api(MGR, "GET", `/approvals/backlog?entity_id=${ENT}`);
  const q = bl.status === 200 ? ((bl.body.items || bl.body.queues || []).find((x) => x.key === "cash_count") || {}) : {};
  log(`  [API] GET /approvals/backlog: HTTP ${bl.status} "${q.label || "-"}" ${q.count ?? "-"} view ${q.view || ""} preset ${JSON.stringify(q.preset || {})}`);
  await tid(p, `opk-row-${O1.id}`).waitFor({ timeout: 15000 });
  log(`  Setujui ${O1.number} aktif ${!(await tid(p, `opk-approve-${O1.id}`).isDisabled())}, Tolak aktif ${!(await tid(p, `opk-reject-${O1.id}`).isDisabled())}`);
  await shot(p, "18_opname_menunggu_penyetuju");

  log(`OP2 Penyetuju — Setujui ${O1.number} (kurang) → Piutang karyawan`);
  await tid(p, `opk-approve-${O1.id}`).click();
  await tid(p, "opk-approve-form").waitFor({ timeout: 10000 });
  await sleep(800);
  await tid(p, "opk-approve-treatment").click();
  await sleep(500);
  log(`  pilihan perlakuan: ${(await p.locator('[data-testid^="opk-approve-treatment-option-"]').allInnerTexts()).map(satu).join(" · ")}`);
  await pilihNilai(p, "opk-approve-treatment", "piutang_karyawan", { buka: false });
  await sleep(1500);
  await tid(p, "opk-approve-employee").click();
  await sleep(800);
  log(`  pemilih karyawan: ${(await p.locator('[data-testid^="opk-approve-employee-option-"]').allInnerTexts()).map(satu).join(" · ")}`);
  await shot(p, "19_setujui_piutang_karyawan_pilih_karyawan");
  const kar = p.locator('[data-testid^="opk-approve-employee-option-"]').filter({ hasText: "Agus Setiawan" }).first();
  await kar.click();
  await sleep(800);
  log(`  ringkasan: "${await teks(tid(p, "opk-approve-summary"))}"`);
  await shot(p, "20_setujui_piutang_karyawan_ringkasan");
  let tunggu = p.waitForResponse((r) => r.url().includes(`/cash-counts/${O1.id}/approve`), { timeout: 30000 });
  await tid(p, "opk-approve-submit").click();
  let resp = await tunggu;
  let h = await resp.json().catch(() => ({}));
  let tt = await toastTeks(p, /disetujui/);
  await sleep(1500);
  log(`  toast: "${tt}"`);
  log(`  [API] POST approve: HTTP ${resp.status()} status ${h.status} perlakuan ${h.perlakuan} karyawan ${h.karyawan_nama} (${h.karyawan_id}) ` +
    `kas ${h.cash_number} disetujui_oleh ${h.disetujui_oleh}`);
  const kas1 = py(`print(json.dumps(db.cash_transactions.find_one({"id":"${h.cash_id}"},{"_id":0,"number":1,"direction":1,"amount":1,"account_id":1,"ref_type":1,"ref_id":1,"description":1,"journal_entry_id":1,"karyawan_id":1,"karyawan_nama":1,"created_by":1})))`);
  log(`  [API] kas penyesuaian: ${kas1}`);
  log(`  [API] jurnal: ${await jurnal(JSON.parse(kas1).journal_entry_id)}`);
  // Daftar masih tersaring "Menunggu persetujuan" (preset antrean) → saringan dibuka supaya baris disetujui tampil.
  await pilihNilai(p, "opk-status", "empty").catch(async (e) => { log(`  catatan saringan: ${e.message.slice(0, 120)}`); await p.keyboard.press("Escape"); });
  await sleep(2500);
  await tid(p, `opk-row-${O1.id}`).waitFor({ timeout: 15000 });
  log(`  baris: "${await teks(tid(p, `opk-row-${O1.id}`))}"`);
  await shot(p, "21_opname_disetujui_piutang_karyawan");

  log(`OP2 Penyetuju — Setujui ${O2.number} (lebih) → hanya Selisih kas`);
  await tid(p, `opk-approve-${O2.id}`).waitFor({ timeout: 15000 });
  await tid(p, `opk-approve-${O2.id}`).click();
  await tid(p, "opk-approve-form").waitFor({ timeout: 10000 });
  await sleep(1000);
  await tid(p, "opk-approve-treatment").click();
  await sleep(500);
  log(`  pilihan perlakuan (lebih): ${(await p.locator('[data-testid^="opk-approve-treatment-option-"]').allInnerTexts()).map(satu).join(" · ")}`);
  await p.keyboard.press("Escape");
  await sleep(400);
  log(`  isi pop-up: "${(await teks(tid(p, "opk-approve-form"))).slice(0, 500)}"`);
  await shot(p, "22_setujui_lebih_selisih_kas_ringkasan");
  tunggu = p.waitForResponse((r) => r.url().includes(`/cash-counts/${O2.id}/approve`), { timeout: 30000 });
  await tid(p, "opk-approve-submit").click();
  resp = await tunggu;
  h = await resp.json().catch(() => ({}));
  tt = await toastTeks(p, /disetujui/);
  log(`  toast: "${tt}"`);
  log(`  [API] POST approve: HTTP ${resp.status()} status ${h.status} perlakuan ${h.perlakuan} kas ${h.cash_number}`);
  const kas2 = py(`print(json.dumps(db.cash_transactions.find_one({"id":"${h.cash_id}"},{"_id":0,"number":1,"direction":1,"amount":1,"account_id":1,"journal_entry_id":1})))`);
  log(`  [API] kas penyesuaian: ${kas2}; jurnal: ${await jurnal(JSON.parse(kas2).journal_entry_id)}`);
  const s1 = await saldoSemua();
  log(`  [API] saldo akun sesudah: ${ringAkun(s1)} — 1-1290 naik ${rp(s1["1-1290"] - s0["1-1290"])}, 1-1105 turun ${rp(s0["1-1105"] - s1["1-1105"])}, ` +
    `1-1110 naik ${rp(s1["1-1110"] - s0["1-1110"])}, 6-9200 ${rp(s1["6-9200"] - s0["6-9200"])} (beban bersaldo debit; kredit = minus)`);
  log(`  [API] buku rekening Kas Kasir: ${rp((await kasRekening(kasir.id)).balance)}; Kas Toko KSC: ${rp((await kasRekening(KAS_TOKO)).balance)}`);
  await c.close();
}

// ═══ op3 — selisih 0 → selesai ═══════════════════════════════════════════════════════════════════════════════════
async function op3(browser) {
  const { kk, O2 } = muat();
  const s0 = jumlahJurnal();
  const a = await rek(kk.id);
  const { c, p } = await sesi(browser, FIN);
  log(`OP3 Finance — Opname Kas › Hitung kas: ${a.name} uang fisik ${rp(a.balance)} (= saldo buku)`);
  await view(p, "cash-counts", 7000);
  await tid(p, "opk-create").click();
  await tid(p, "opk-form").waitFor({ timeout: 10000 });
  await sleep(1500);
  await pilihNilai(p, "opk-form-account", kk.id);
  await tid(p, "opk-form-amount").fill(String(Math.round(a.balance)));
  await tid(p, "opk-form-note").fill("Hitung serah terima kepala gudang");
  await sleep(500);
  const tunggu = p.waitForResponse((r) => r.url().endsWith("/api/cash-counts") && r.request().method() === "POST", { timeout: 30000 });
  await tid(p, "opk-form-submit").click();
  const resp = await tunggu;
  const o = await resp.json().catch(() => ({}));
  await tid(p, "opk-form-result").waitFor({ timeout: 10000 });
  await sleep(800);
  await shot(p, "23_opname_selisih_nol_selesai");
  log(`  hasil: "${await teks(tid(p, "opk-form-result"))}"`);
  log(`  [API] POST /cash-counts: HTTP ${resp.status()} ${o.number} status ${o.status} selisih ${rp(o.selisih)} kas ${o.cash_id || "-"}; jurnal PT baru ${jumlahJurnal() - s0}`);
  await tid(p, "opk-form-done").click();
  await sleep(2000);
  log(`  baris O2 (disetujui) untuk penghitung: Batal ${await tid(p, `opk-cancel-${O2.id}`).count() ? `ada, nonaktif ${await tid(p, `opk-cancel-${O2.id}`).isDisabled()}` : "tidak ada"}; ` +
    `kalimat "${await teks(tid(p, `opk-action-note-${O2.id}`))}"`);
  const bt = await api(FIN, "POST", `/cash-counts/${O2.id}/batal`, { alasan: "Coba batal oleh penghitung" });
  log(`  [API] penghitung mencoba Batal lewat API: HTTP ${bt.status} ${det(bt)}`);
  simpan({ O3: { id: o.id, number: o.number } });
  await c.close();
}

// ═══ op4 — Batal opname disetujui ═════════════════════════════════════════════════════════════════════════════════
async function op4(browser) {
  const { O2 } = muat();
  const s0 = await saldoSemua();
  const { c, p } = await sesi(browser, MGR);
  log(`OP4 Penyetuju (manager@) — Batalkan opname ${O2.number}`);
  await view(p, "cash-counts", 7000);
  await tid(p, `opk-cancel-${O2.id}`).waitFor({ timeout: 15000 });
  await tid(p, `opk-cancel-${O2.id}`).click();
  await tid(p, "opk-cancel-reason-reason").waitFor({ timeout: 10000 });
  await sleep(600);
  log(`  pop-up: "${await teks(tid(p, "opk-cancel-reason-message"))}"; tombol nonaktif saat kosong ${await tid(p, "opk-cancel-reason-confirm").isDisabled()}`);
  await tid(p, "opk-cancel-reason-reason").fill("Kelebihan ternyata uang titipan pelanggan yang belum dicatat");
  await sleep(500);
  await shot(p, "24_batal_opname_popup_alasan");
  const tunggu = p.waitForResponse((r) => r.url().includes(`/cash-counts/${O2.id}/batal`), { timeout: 30000 });
  await tid(p, "opk-cancel-reason-confirm").click();
  const resp = await tunggu;
  const h = await resp.json().catch(() => ({}));
  const tt = await toastTeks(p, /dibatalkan/);
  await sleep(1500);
  log(`  toast: "${tt}"`);
  log(`  [API] POST batal: HTTP ${resp.status()} status ${h.status} (${h.status_label}) alasan "${h.alasan_batal}" oleh ${h.dibatalkan_oleh}, ` +
    `batal_gl_status ${h.batal_gl_status}, kas ${(h.kas || {}).number} status ${(h.kas || {}).status}, pembalik ${(h.kas || {}).void_journal_number}`);
  for (const j of h.void_journal_entry_ids || []) log(`  [API] jurnal pembalik: ${await jurnal(j)}`);
  const s1 = await saldoSemua();
  log(`  [API] saldo akun: 1-1110 berubah ${rp(s1["1-1110"] - s0["1-1110"])}, 6-9200 berubah ${rp(s1["6-9200"] - s0["6-9200"])}; ` +
    `buku Kas Toko KSC ${rp((await kasRekening(KAS_TOKO)).balance)}`);
  log(`  baris: "${await teks(tid(p, `opk-row-${O2.id}`))}"`);
  await shot(p, "25_opname_dibatalkan");
  await c.close();
}

// ═══ op5 — saringan piutang karyawan, pratinjau, jejak ═══════════════════════════════════════════════════════════
async function op5(browser) {
  const { O1 } = muat();
  const { c, p } = await sesi(browser, MGR);
  log("OP5 Penyetuju — Opname Kas › Perlakuan: Piutang karyawan");
  await view(p, "cash-counts", 7000);
  await pilihNilai(p, "opk-treatment", "piutang_karyawan");
  await sleep(2500);
  const baris = (await p.locator('[data-testid^="opk-row-"]').allInnerTexts()).map(satu);
  log(`  baris tersaring (${baris.length}): ${baris.join(" | ")}`);
  await shot(p, "26_saringan_perlakuan_piutang_karyawan");
  const f = await api(MGR, "GET", `/cash-counts?entity_id=${ENT}&perlakuan=piutang_karyawan`);
  log(`  [API] GET /cash-counts?perlakuan=piutang_karyawan: ${f.body.total} — ${(f.body.items || []).map((x) => `${x.number} ${x.status_label} ${x.karyawan_nama} ${rp(x.selisih)}`).join("; ")}`);
  log(`OP5 Penyetuju — klik ${O1.number} → pratinjau`);
  await tid(p, `opk-open-${O1.id}`).click();
  await tid(p, "doc-preview-cash-count").waitFor({ timeout: 15000 });
  await sleep(2500);
  log(`  pratinjau: judul "${await teks(tid(p, "doc-preview-title"))}"; status "${await teks(tid(p, "doc-preview-status"))}"`);
  log(`  fakta "${await teks(tid(p, "doc-preview-opk-facts"))}"`);
  log(`  pecahan "${await teks(tid(p, "doc-preview-opk-denoms"))}"; kas "${await teks(tid(p, "doc-preview-opk-cash"))}"; jurnal "${await teks(tid(p, "doc-preview-opk-journal"))}"`);
  log(`  riwayat "${await teks(tid(p, "doc-preview-opk-history"))}"; kaki: Jejak ${await tid(p, "doc-preview-trace").count()}, Buka layar penuh ${await tid(p, "doc-preview-full").count()}`);
  await shot(p, "27_pratinjau_opk_piutang_karyawan");
  await tid(p, "doc-preview-trace").click();
  await tid(p, "trace-anchor-card").waitFor({ timeout: 20000 }).catch(() => {});
  await sleep(4000);
  await clean(p);
  log(`  Jejak: ${p.url().replace(BASE, "")}; jangkar "${await teks(tid(p, "trace-anchor-number"))}"`);
  const tr = await api(MGR, "GET", `/documents/trace/cash_count/${O1.id}`);
  const nodes = (tr.body.nodes || []).map((n) => `${n.doc_type}:${n.number || n.doc_number || n.id}`);
  const edges = (tr.body.edges || []).map((e) => `${e.from || e.source}→${e.to || e.target}${e.rel ? `(${e.rel})` : ""}`);
  log(`  [API] GET /documents/trace/cash_count: HTTP ${tr.status} simpul ${nodes.join(", ")}; sisi ${edges.slice(0, 8).join(", ")}`);
  const masih = await tid(p, "doc-preview-cash-count").count();
  log(`  sesudah klik Jejak: pratinjau ${masih ? "MASIH TERBUKA menutupi layar Jejak Dokumen" : "tertutup"}`);
  if (masih) {
    await shot(p, "28b_jejak_pratinjau_masih_menutupi");
    await p.keyboard.press("Escape");
    await sleep(1500);
  }
  log(`  layar Jejak: "${(await teks(tid(p, "trace-anchor-card"))).slice(0, 300)}"`);
  await shot(p, "28_jejak_opk_kas_jurnal");
  await c.close();
}

// ═══ meja ═══════════════════════════════════════════════════════════════════════════════════════════════════════
async function meja() {
  log("MEJA API — Meja Keuangan antrean \"Opname kas jatuh tempo\"");
  const r = await api(FIN, "GET", `/finance/desk?entity_id=${ENT}`);
  const q = ((r.body || {}).queues || []).find((x) => (x.key || x.id) === "opname_kas_jatuh_tempo");
  log(`  [API] GET /finance/desk (finance@): HTTP ${r.status}; antrean ${q ? `"${q.label}" ${(q.rows || q.items || []).length} baris` +
    `${(q.rows || q.items || []).length ? ": " + (q.rows || q.items).map((x) => `${x.number} ${x.subtitle}`).join("; ") : ""}` : "TIDAK ADA di jawaban"}`);
  const pen = py(`d=db.system_settings.find_one({"scope":"__migrations__"}) or {}\nprint(d.get("kb3_opname_kas_aktif_sejak",""))`);
  log(`  penanda fitur aktif ${pen}; jarak bawaan kasir 1 hari, kas kecil 7 hari → paling cepat jatuh tempo besok. ` +
    "Tidak ada rekening jatuh tempo di data acuan → kartu tidak dipotret (sesuai brief: dicatat & dilewati; penanda tidak digeser).");
}

// ═══ cek ════════════════════════════════════════════════════════════════════════════════════════════════════════
async function cek() {
  const d = muat();
  log("CEK — ringkasan akhir PT KSC");
  const s = await saldoSemua();
  log(`  awal:  ${ringAkun(d.saldo_awal)}`);
  log(`  akhir: ${ringAkun(s)}; jurnal PT ${d.jurnal_awal} → ${jumlahJurnal()}`);
  for (const k of ["kasir", "kk"]) {
    if (!d[k]) continue;
    const a = await rek(d[k].id);
    log(`  rekening ${a.name}: cash_type ${a.cash_type}, dana tetap ${rp(a.dana_tetap)}, lokasi ${a.location_name || "-"}, saldo ${rp(a.balance)}`);
  }
  if (d.kk) log(`  dana tetap: ${ringDT(await posisiDT(d.kk.id))}`);
  const all = (await api(MGR, "GET", `/cash-counts?entity_id=${ENT}&page_size=50`)).body;
  log(`  opname PT KSC: ${all.items.map((x) => `${x.number} ${x.account_name} ${x.status_label} selisih ${rp(x.selisih)}${x.perlakuan_label ? ` ${x.perlakuan_label}` : ""}` +
    `${x.karyawan_nama ? ` (${x.karyawan_nama})` : ""}${x.cash_number ? ` → ${x.cash_number}` : ""}`).join("; ")}`);
  const bl = await api(MGR, "GET", `/approvals/backlog?entity_id=${ENT}`);
  const q = bl.status === 200 ? ((bl.body.items || bl.body.queues || []).find((x) => x.key === "cash_count") || {}) : {};
  log(`  antrean Pusat Persetujuan opname (manager@): ${q.count ?? 0}`);
}

function siapkanId() {
  const r = JSON.parse(py(`c=lambda n,e: (db.customers.find_one({"name":n,"entity_id":e},{"_id":0,"id":1}) or {}).get("id","")
b=lambda n: (db.bank_accounts.find_one({"name":n,"entity_id":"${ENT}"},{"_id":0,"id":1}) or {}).get("id","")
print(json.dumps({"cust":c("${CUST.name}","${ENT}"),"cust_lain":c("${CUST_LAIN.name}","${ENT_LAIN}"),"bca":b("BCA Operasional KSC"),"kas_toko":b("Kas Toko KSC")}))`));
  if (!r.cust || !r.cust_lain || !r.bca || !r.kas_toko) throw new Error(`id data acuan tidak lengkap: ${JSON.stringify(r)}`);
  CUST.id = r.cust; CUST_LAIN.id = r.cust_lain; BCA = r.bca; KAS_TOKO = r.kas_toko;
  log(`[data acuan] ${CUST.name} ${CUST.id} · ${CUST_LAIN.name} ${CUST_LAIN.id} · BCA ${BCA} · Kas Toko KSC ${KAS_TOKO}`);
}
const FASE = { awal, r1, kw, dt1, dt2, dt3, op1, op2, op3, op4, op5, meja, cek };
(async () => {
  const pilih = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(FASE);
  siapkanId();
  const browser = await chromium.launch();
  for (const f of pilih) {
    log(`── fase ${f} (${new Date().toISOString()})`);
    try { await FASE[f](browser); } catch (e) { log(`  GALAT fase ${f}: ${e.message.slice(0, 400)}`); break; }
  }
  await browser.close();
})();
