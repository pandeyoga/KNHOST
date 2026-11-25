// S3 · SITUASI KHUSUS PESANAN SAMPAI UANG MASUK — PT Sukacita, dijalankan LEWAT LAYAR oleh setiap peran, lalu dicocokkan
// dengan BUKU (jurnal seimbang, piutang per pesanan, uang muka 2-1400, titipan, PPN keluaran = faktur, umur piutang).
//
//   A. Pengiriman sebagian — satu SO 2 roll keluar lewat 2 surat jalan → 2 jurnal pendapatan & 2 jurnal HPP sebesar yang
//      dikirim; piutang bertahap; faktur pajak per pesanan = PPN kedua surat jalan; SATU kwitansi melunasi keduanya.
//   B. Uang muka (DP 50%) — gudang tertahan sampai DP dibayar; DP = Kas D / Uang Muka Pelanggan K; saat kirim uang muka
//      direklas ke piutang; sisa ditagih lalu lunas; uang muka pesanan kembali nol.
//   C. Batal SO ber-DP sebelum kirim — DP menjadi titipan pelanggan (tanpa jurnal baru), roll dilepas; titipan
//      dikembalikan lewat Kasus (Finance melapor, Manajer menyelesaikan): Uang Muka Pelanggan D / Bank K.
//   D. Satu transfer untuk beberapa SO — alokasi tertua dulu: SO pertama lunas, SO kedua sebagian, SO ketiga tetap.
//   E. Transfer dipotong biaya bank — di atas toleransi: sisa tetap piutang lalu Kasus "biaya bank" (Beban Adm Bank D /
//      Piutang K); di bawah toleransi: diputus otomatis (Beban Selisih Pembayaran D / Piutang K).
//
//   KN_PESERTA=72 KN_PY=/jalur/python node docs/pelatihan/2026-11-18_keuangan/uji/situasi/S3_situasi_penjualan.js
//   KN_S3_BAGIAN=A,B …   (hanya bagian tertentu; bawaan semua: A,B,C,D,E,F)
//
// Butuh peserta SEGAR dari rentang 71–75 (pelanggan "Latihan NN · Toko Kain Peserta NN" dengan dua SO terkirim awal):
//   cd backend && python scripts/seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN --hanya a_dasar:akun   (lalu
//   --hanya a_dasar:mitra, --hanya a_dasar:so_). SO ketiga (terkirim) dibuat langkah 0 lewat endpoint resmi.
// Hasil: uji/hasil/S3/hasil.json + tangkapan layar.
const path = require("path");
const U = path.join(__dirname, "..");
const { Run, api, assert, sleep, rp, num, peserta, akunPeserta, mongo, kartu } = require(path.join(U, "lib.js"));
const { bersihkanHasil, sorot, lepas, klikSorot, bukaMenu, bukaPenagihan, barisSo, sisaSo, cekJurnalSeimbang,
  pilih } = require(path.join(U, "piutang_lib.js"));
const kb = require(path.join(U, "kasbank_lib.js"));
const { tungguTeks, tungguToast, toastLoc } = require(path.join(U, "hutang_lib.js"));
const bk = require(path.join(U, "buku_lib.js"));

const NO = peserta("72");
const KSC = "ent_ksc";
const PELANGGAN = `Latihan ${NO} · Toko Kain Peserta ${NO}`;
const BAGIAN = (process.env.KN_S3_BAGIAN || "A,B,C,D,E,F").split(",").map((s) => s.trim().toUpperCase());
const PRODUK_PILIHAN = ["DENIM TENCEL HITAM A", "DENIM TENCEL TAUPE A", "DENIM TENCEL BLUE BLACK GARMENT A"];
const BIAYA_BANK = 6500;      // potongan transfer antarbank — DI ATAS toleransi Rp 5.000
const BIAYA_KECIL = 2500;     // potongan kecil — DI BAWAH toleransi Rp 5.000 (diputus otomatis)

const r2 = (n) => Math.round(Number(n || 0) * 100) / 100;
const dekat = (a, b, tol = 0.01) => Math.abs(Number(a) - Number(b)) <= tol;
const angka = (n) => rp(n).replace("Rp ", "");       // angka layar "2.615.160"
const isiLayar = async (loc) => (await loc.first().innerText()).replace(/\s+/g, " ").trim();
const teksJe = (je) => `${je.number} ${je.lines.map((l) => `${l.account_code} ${Number(l.debit) ? "D" : "K"} ${rp(Number(l.debit) || Number(l.credit))}`).join(" · ")}`;

// ── Pembaca buku (Mongo, sumber independen dari layar) ───────────────────────────────────────────────────────────────
function soDoc(id) { return mongo(`return db.sales_orders.findOne({id:"${id}"},{_id:0})`); }
function soByNumber(no) { return mongo(`return db.sales_orders.findOne({number:${JSON.stringify(no)},entity_id:"${KSC}"},{_id:0})`); }
function sjSo(id) {
  return mongo(`return db.shipments.find({order_id:"${id}",status:{$nin:["cancelled","void"]}},{_id:0}).sort({created_at:1}).toArray()`);
}
/** Jurnal pesanan: pendapatan & HPP per surat jalan + reklas uang muka (+ jurnal kwitansinya bila `kwitansi`). */
function jurnalSo(id, tipe) {
  return mongo(`const sids=db.shipments.find({order_id:"${id}"},{_id:0,id:1}).toArray().map(x=>x.id);
    return db.journal_entries.find({status:{$ne:"void"},$or:[{source_id:"${id}"},{source_id:{$in:sids}},{"ref.order_id":"${id}"}]
      ${tipe ? `,source_type:${JSON.stringify(tipe)}` : ""}},{_id:0,id:1,number:1,source_type:1,source_id:1,ref:1,lines:1,created_at:1})
      .sort({created_at:1}).toArray()`);
}
function kwitansiSo(id) {
  return mongo(`return db.ar_receipts.find({"allocations.order_id":"${id}",status:{$ne:"void"}},{_id:0}).sort({created_at:1}).toArray()`);
}
function jurnalKas(kasId) {
  return mongo(`return db.journal_entries.find({source_id:"${kasId}",status:{$ne:"void"}},{_id:0}).sort({created_at:1}).toArray()`);
}
/** Saldo satu akun dari kumpulan jurnal: Σ debit − Σ kredit. */
const saldo = (jes, kode) => r2(jes.flatMap((j) => j.lines).filter((l) => l.account_code === kode)
  .reduce((s, l) => s + Number(l.debit || 0) - Number(l.credit || 0), 0));
const sisi = (je, kode, s) => r2(je.lines.filter((l) => l.account_code === kode)
  .reduce((a, l) => a + Number((s === "D" ? l.debit : l.credit) || 0), 0));
function titipanPelanggan(custId) {
  return r2((mongo(`return db.customers.findOne({id:"${custId}"},{_id:0,deposit_balance:1})`) || {}).deposit_balance || 0);
}
/** Uang muka pesanan yang masih tertahan (pembayaran ber-ember uang muka − reklas ke piutang). */
function umTertahan(id) {
  const o = soDoc(id);
  const adv = (o.payments || []).filter((p) => p.gl_bucket === "advance").reduce((s, p) => s + Number(p.amount || 0), 0);
  const re = jurnalSo(id).filter((j) => /^advance_reclass/.test(j.source_type));
  return r2(adv - saldo(re, "2-1400"));
}

/** Produk woven Jakarta dengan harga PT dan roll utuh bebas (grade A). */
function pilihProduk(min = 6) {
  for (const nama of PRODUK_PILIHAN) {
    const p = mongo(`const p=db.products.findOne({name:${JSON.stringify(nama)}},{_id:0,id:1,name:1,sku:1,base_unit:1});
      if(!p) return null;
      const ep=db.entity_prices.findOne({entity_id:"${KSC}",product_id:p.id},{_id:0});
      const n=db.inventory_rolls.countDocuments({product_id:p.id,owner_entity_id:"${KSC}",warehouse_id:"wh_jakarta",
        status:"available",grade:"A",reserved_ref:null,length_reserved:{$in:[null,0]}});
      return ep && n>=${min} ? {...p, harga:(ep.price||ep.sell_price||0), roll_bebas:n} : null`);
    if (p) return p;
  }
  throw new Error("Tidak ada produk latihan dengan stok roll bebas di Jakarta");
}

async function masuk(r, akun) {
  try { await r.login(akun); } catch (e) {
    r.note(`login ${akun} lambat (${String(e.message || e).split("\n")[0].slice(0, 80)}) — diulang`);
    await r.login(akun);
  }
}

/** Pilih opsi KNSelect berdasarkan teks (opsi bisa dicari dengan mengetik). */
async function pilihTeks(r, testId, re, ketik = "") {
  await r.tid(testId).click();
  await sleep(300);
  if (ketik) { await r.page.keyboard.type(ketik); await sleep(1200); }
  const opt = r.page.getByRole("option", { name: re }).first();
  await opt.waitFor({ timeout: 10000 });
  await opt.click();
  await sleep(300);
}

// ── SALES: POS (pola sama dengan A1) ─────────────────────────────────────────────────────────────────────────────────
async function mulaiPos(r, nama = "") {
  await bukaMenu(r, "sales", "", { grup: "penjualan", nama });
  if (await r.tid("pos-gate").isVisible().catch(() => false)) {
    await pilihTeks(r, "pos-gate-site", /^Jakarta/);
    await pilihTeks(r, "pos-gate-customer", new RegExp(PELANGGAN), `Latihan ${NO} · Toko Kain Peserta`);
    await r.tid("pos-gate-start").click();
    await r.idle(800);
  }
  await r.tid("pos-customer-bar").waitFor();
  const cust = await isiLayar(r.tid("pos-customer-select"));
  assert(cust.includes(`Latihan ${NO}`), `pelanggan POS: ${cust}`);
}

async function tambahRoll(r, prod, n, nama = "") {
  await r.tid("product-search-input").fill(prod.name.replace(/ A$/, ""));
  await r.idle(1200);
  const card = r.tid(`product-image-button-${prod.id}`);
  await card.waitFor({ timeout: 20000 });
  await card.click();
  await r.tid("product-quickview").waitFor();
  await r.tid("quickview-mode-roll").click();
  await r.tid("roll-picker").waitFor({ timeout: 20000 });
  await r.idle(600);
  const toggles = r.page.locator("[data-testid^=roll-toggle-]");
  for (let i = 0; i < n; i += 1) { await toggles.nth(i).click(); await sleep(300); }
  const count = num(await r.text("roll-picker-count"));
  assert(count === n, `roll terpilih ${count} ≠ ${n}`);
  const subtotal = num(await r.text("roll-picker-subtotal"));
  if (nama) {
    await r.tid("roll-picker-confirm").scrollIntoViewIfNeeded();
    await bk.potret(r, `${nama}-pilih-roll`, [r.tid("roll-picker-count"), r.tid("roll-picker-confirm")]);
  }
  await r.tid("roll-picker-confirm").click();
  await r.idle(800);
  if (await r.tid("quickview-close").isVisible().catch(() => false)) await r.tid("quickview-close").click();
  return { count, subtotal };
}

/** Keranjang → Checkout langkah 1 & 2 (termin: bawaan NET 30 atau `termin` /regex/), cara bayar Transfer → Review. */
async function checkout(r, { termin = null, faktur = false, nama = "" } = {}) {
  await r.tid("floating-cart-button").click();
  await r.tid("checkout-step-1").waitFor();
  await r.tid("checkout-next").click();
  await r.tid("checkout-step-2").waitFor();
  if (termin) await pilihTeks(r, "payment-term-select", termin);
  const t = await isiLayar(r.tid("payment-term-select"));
  await pilihTeks(r, "payment-method-select", /^Transfer bank/);
  await r.tid("receiving-account-field").waitFor();
  await kb.tunggu(r, "checkout-payment-destination", /BCA \d+/, 20000);
  if (nama) await bk.potret(r, `${nama}-termin`, [r.tid("payment-term-select"), r.tid("payment-method-select")]);
  await r.tid("checkout-next").click();
  await r.tid("checkout-step-3").waitFor();
  await r.tid("credit-gate-box").waitFor({ timeout: 20000 });
  await r.idle(800);
  if (faktur) { await r.tid("checkout-tax-invoice-toggle").click(); await sleep(400); }
  const grand = num(await r.text("cart-grand-total"));
  return { termin: t, grand };
}

/** [Buat Sales Order] → SO dari notifikasi (lot campur dikonfirmasi bila muncul). */
async function buatSo(r, nama) {
  await klikSorot(r, r.tid("checkout-submit"), `${nama}-buat`);
  if (await r.tid("mixed-lot-modal").isVisible({ timeout: 3000 }).catch(() => false)) await r.tid("mixed-lot-confirm").click();
  const msg = await tungguTeks(r, "system-notice-text", /KSC\/SO-\d+ dibuat/, 30000);
  const so = soByNumber(msg.match(/KSC\/SO-\d+/)[0]);
  assert(so, `SO ${msg} tidak ada di buku`);
  await bk.potret(r, `${nama}-dibuat`, [r.tid("system-notice-text")]);
  return { so, msg };
}

// ── ADMIN SALES: periksa & lepas ─────────────────────────────────────────────────────────────────────────────────────
async function periksaLepas(r, so, nama) {
  await masuk(r, "salesadmin");
  await r.tid("sales-admin-desk").waitFor();
  await r.tid("desk-tabs-pantau").click();   // meja gelombang 1 — Pelacak SO di tab Pantau
  await r.tid("desk-so-tracker-search").fill(so.number);
  await r.idle(600);
  const row = r.tid(`desk-so-tracker-row-${so.id}`);
  await row.waitFor({ timeout: 20000 });
  await sorot(row);
  await klikSorot(r, r.tid(`desk-so-tracker-action-${so.id}`), `${nama}-periksa`);
  await lepas(row);
  await r.tid("verify-dialog").waitFor();
  await r.tid("verify-checklist").waitFor({ timeout: 20000 });
  await r.tid("verify-note").fill("Alamat, termin & isi pesanan dicek");
  await r.tid("verify-submit").click();
  const msg = await tungguToast(r, /dilepas ke gudang/, 20000);
  const s = soDoc(so.id);
  assert(s.status === "confirmed", `status SO ${s.status}`);
  const task = mongo(`return db.wms_tasks.findOne({order_id:"${so.id}",flow_type:"outbound"},{_id:0,id:1,status:1,quantity:1})`);
  assert(task, "tugas ambil gudang tidak lahir");
  return { msg, task };
}

// ── GUDANG ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async function bukaTugas(r, so, task, nama = "") {
  await bukaMenu(r, "wms-operations", "wms-outbound", { grup: "gudang" });
  await r.tid("outbound-scan-panel").waitFor();
  await r.page.locator('[data-testid="outbound-filters"] input').first().fill(so.number.replace("KSC/", ""));
  await r.idle(600);
  const t = r.tid(`outbound-task-${task.id}`);
  await t.waitFor({ timeout: 20000 });
  if (nama) await bk.potret(r, `${nama}-tugas`, [t]);
  await t.click();
  await r.tid("outbound-task-panel").waitFor();
  await r.idle(800);
}

/** Pindai satu roll lalu [Kirim Pengambilan]. */
async function ambilRoll(r, task, rollNo, nama = "") {
  await r.tid("outbound-roll-code").fill(rollNo);
  await r.page.keyboard.press("Enter");
  await r.tid("outbound-roll-info").waitFor({ timeout: 15000 });
  const info = await r.text("outbound-roll-info");
  assert(info.includes(rollNo), `info roll: ${info}`);
  if (nama) await bk.potret(r, `${nama}-pindai`, [r.tid("outbound-roll-code"), r.tid("outbound-roll-info"), r.tid(`scan-task-${task.id}`)]);
  await r.tid(`scan-task-${task.id}`).click();
  await r.page.getByText("Pengambilan tercatat").first().waitFor({ timeout: 20000 });
  await r.idle(1500);
  return mongo(`return db.wms_tasks.findOne({id:"${task.id}"},{_id:0,status:1,picked_qty:1,quantity:1,shipped_qty:1})`);
}

/** [Kirim Semua] (= semua yang sudah diambil) → [Kirim Sekarang] → surat jalan baru. */
async function kirim(r, so, task, nama) {
  const sebelum = sjSo(so.id).length;
  await r.tid(`dispatch-all-${task.id}`).click();
  await r.tid("outbound-dispatch-confirm").waitFor();
  await klikSorot(r, r.tid("outbound-dispatch-confirm-confirm"), `${nama}-kirim`, { locator: r.tid("outbound-dispatch-confirm") });
  await r.page.getByText("Barang terkirim").first().waitFor({ timeout: 30000 });
  await r.idle(1500);
  const sjs = sjSo(so.id);
  assert(sjs.length === sebelum + 1, `surat jalan baru tidak terbit (${sjs.length})`);
  return sjs[sjs.length - 1];
}

async function overrideMuat(r, so, task, nama) {
  await masuk(r, "manager");
  await bukaTugas(r, so, task);
  await r.tid("lc-override-reason").fill("Roll latihan belum bertag RFID, muatan dicek manual oleh supervisor");
  await klikSorot(r, r.tid("lc-override"), `${nama}-override`);
  return tungguTeks(r, "lc-last-result", /OVERRIDE/, 20000);
}

// ── KASUS KEUANGAN ───────────────────────────────────────────────────────────────────────────────────────────────────
/** Keuangan › Piutang › Kasus, tunggu daftar rujukan (jenis kasus, pelanggan, rekening) selesai dimuat — daftar pelanggan
 *  lengkap bisa butuh beberapa detik; [Kasus baru] yang dibuka sebelum itu belum punya pilihan jenis kasus. */
async function bukaKasus(r) {
  const muat = r.page.waitForResponse((res) => /\/api\/customers(\?|$)/.test(res.url()), { timeout: 90000 }).catch(() => null);
  await bukaMenu(r, "ar-aging", "finance-cases");
  await r.tid("finance-cases-view").waitFor();
  await muat;
  await r.idle(800);
}

// ── FINANCE: terima pembayaran dari Penagihan & Penerimaan ───────────────────────────────────────────────────────────
async function bukaFormBayar(r, soId, nama) {
  await bukaPenagihan(r);
  const row = await barisSo(r, soId);
  await sorot(row);
  await klikSorot(r, r.tid(`collection-pay-${soId}`), `${nama}-dompet`);
  await lepas(row);
  await r.tid("ar-receipt-modal").waitFor();
  await r.tid(`ar-receipt-alloc-${soId}`).waitFor();
  // Rekening penerima dimuat dari server — saat server sibuk (kelas penuh) bisa > 15 detik.
  await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'), null, { timeout: 90000 });
  await r.idle(800);
}

/** Simpan → (dialog selisih: pilih `keputusan` + `alasan`) → konfirmasi → pesan. → teks notifikasi. */
async function simpanKwitansi(r, nama, { keputusan = "", alasan = null, catatan = "" } = {}) {
  await klikSorot(r, r.tid("ar-receipt-submit"), `${nama}-simpan`);
  if (keputusan) {
    await r.tid("payment-variance-dialog").waitFor();
    await r.tid(`pv-option-${keputusan}`).click();
    if (alasan) await pilih(r, "pv-reason", alasan);
    if (catatan) await r.tid("pv-note").fill(catatan);
    await bk.potret(r, `${nama}-selisih`, [r.tid("pv-sentence"), r.tid(`pv-option-${keputusan}`), r.tid("pv-reason")]);
    await r.tid("pv-submit").click();
  }
  await r.tid("ar-receipt-confirm").waitFor();
  await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), `${nama}-konfirmasi`);
  const t = await tungguTeks(r, "collection-notice", /Kwitansi .*AR-\d+/, 60000);
  await r.idle(800);
  return t;
}

// ── Persiapan: SO ketiga terkirim lewat endpoint resmi (pelatih) ─────────────────────────────────────────────────────
async function soTerkirimApi(cust, prod) {
  const sales = await api("sales"), sa = await api("salesadmin"), wh = await api("warehouse"), mgr = await api("manager");
  const roll = mongo(`return db.inventory_rolls.find({product_id:"${prod.id}",owner_entity_id:"${KSC}",warehouse_id:"wh_jakarta",
    status:"available",grade:"A",reserved_ref:null,length_reserved:{$in:[null,0]}},{_id:0,id:1,roll_no:1,length_remaining:1})
    .sort({created_at:1}).limit(1).toArray()[0]`);
  const so = await sales.post("/sales-orders", { customer_id: cust.id, shipping_address_id: ((cust.addresses || [])[0] || {}).id || "",
    items: [{ product_id: prod.id, quantity: roll.length_remaining, unit: prod.base_unit, purchase_mode: "roll", qty_rolls: 1,
      roll_lines: [{ roll_id: roll.id, take_qty: roll.length_remaining }] }],
    entity_id: KSC, payment_term_code: "NET30", allow_backorder: false, confirm_mixed_lot: true }, KSC);
  try { await sa.post(`/sales-orders/${so.id}/verify`, { note: "Persiapan pelatih S3" }, KSC); } catch (e) { /* dicek di bawah */ }
  if (soDoc(so.id).status !== "confirmed") await sa.post(`/sales-orders/${so.id}/confirm`, {}, KSC);
  const t = mongo(`return db.wms_tasks.findOne({order_id:"${so.id}",flow_type:"outbound"},{_id:0,id:1})`);
  try { await wh.post(`/outbound/tasks/${t.id}/release`, {}, KSC); } catch (e) { /* sudah rilis */ }
  await wh.call("POST", `/outbound/tasks/${t.id}/scan-pick?roll_id=${encodeURIComponent(roll.roll_no)}`, undefined, KSC);
  await mgr.post(`/outbound/so/${so.id}/loading-check/override`, { reason: "Persiapan pelatih S3: roll latihan tanpa tag RFID" }, KSC);
  await wh.post(`/outbound/tasks/${t.id}/dispatch`, {}, KSC);
  const o = soDoc(so.id);
  assert(["shipped", "done"].includes(o.status), `SO ketiga belum terkirim: ${o.status}`);
  return o;
}

(async () => {
  bersihkanHasil("S3");
  const r = await new Run("S3", "Situasi khusus pesanan sampai uang masuk").start();
  r.page.setDefaultTimeout(30000);   // server latihan dipakai banyak pengguna sekaligus
  const http4xx = [];
  r.page.on("response", (res) => {
    const u = res.url();
    if (u.includes("/api/") && res.status() >= 400 && res.status() < 500) http4xx.push(`${res.status()} ${res.request().method()} ${u.replace(/^.*\/api/, "/api").split("?")[0]} (${r.who})`);
  });
  const finAkun = akunPeserta(NO);
  const ctx = {};
  const step = async (...a) => { if (!(await r.step(...a))) throw new Error(`langkah ${a[0]} gagal — alur dihentikan`); };
  const ada = (b) => BAGIAN.includes(b);
  try {
    // ── 0. PERSIAPAN PELATIH ───────────────────────────────────────────────────────────────────────────────────────
    await step(0, "Pelatih", "Persiapan: pelanggan latihan segar dengan tiga SO terkirim belum dibayar + produk ber-stok",
      "SO-1 dan SO-2 (data latihan), SO-3 (dibuat lewat endpoint resmi) terkirim, belum dibayar; titipan pelanggan Rp 0", async () => {
        const cust = mongo(`return db.customers.findOne({name:${JSON.stringify(PELANGGAN)}},{_id:0,id:1,name:1,addresses:1,deposit_balance:1})`);
        assert(cust, `Pelanggan ${PELANGGAN} belum ada — jalankan seed_pelatihan_keuangan_kn.py --mulai ${NO} --peserta ${NO}`);
        ctx.cust = cust;
        ctx.prod = pilihProduk();
        const k = kartu(NO);
        ctx.so1 = k["a_dasar:so_lunas"]; ctx.so2 = k["a_dasar:so_sebagian"];
        if (ada("D") || ada("E")) {
          assert(ctx.so1 && ctx.so2, "Kartu peserta belum punya dua SO terkirim (seed --hanya a_dasar:so_)");
          if (ada("D")) for (const s of [ctx.so1, ctx.so2]) assert(dekat(sisaSo(s.so_id), s.total), `${s.so} sudah pernah dibayar — pakai peserta segar`);
          // SO ketiga = SO terkirim NET 30 pelanggan ini selain dua SO data latihan dan tanpa faktur (jalan ulang: dipakai lagi).
          const s3 = mongo(`return db.sales_orders.find({customer_id:"${cust.id}",entity_id:"${KSC}",status:{$in:["shipped","done"]},
            payment_term_code:"NET30",needs_tax_invoice:{$ne:true},id:{$nin:["${ctx.so1.so_id}","${ctx.so2.so_id}"]}},{_id:0,id:1})
            .sort({created_at:1}).limit(1).toArray()[0]||null`);
          const o3 = s3 ? soDoc(s3.id) : await soTerkirimApi(cust, ctx.prod);
          ctx.so3 = { so: o3.number, so_id: o3.id, total: r2(o3.grand_total) };
          assert(dekat(sisaSo(o3.id), o3.grand_total), `${o3.number} sudah pernah dibayar`);
        }
        // KN_S3_ULANG=1 hanya untuk menyusun uji (pelanggan dipakai ulang); kelas = peserta segar (titipan awal Rp 0).
        ctx.titipAwal = titipanPelanggan(cust.id);
        assert(ctx.titipAwal < 0.01 || process.env.KN_S3_ULANG, `titipan awal ${ctx.titipAwal} ≠ 0 — pakai peserta segar`);
        const daftar = [["SO-1", ctx.so1], ["SO-2", ctx.so2], ["SO-3", ctx.so3]].filter(([, s]) => s && ctx.so3)
          .map(([k, s]) => `${k} ${s.so} ${rp(s.total)}`).join(" · ");
        r.note(`Peserta ${NO} · ${PELANGGAN} · produk ${ctx.prod.name} ${rp(ctx.prod.harga)}/${ctx.prod.base_unit} (${ctx.prod.roll_bebas} roll bebas)${daftar ? " · " + daftar : ""}`);
        return `${daftar || "tanpa SO awal (bagian D/E tidak dijalankan)"} · ${ctx.prod.name}`;
      });

    // ══ A. PENGIRIMAN SEBAGIAN ═════════════════════════════════════════════════════════════════════════════════════
    if (ada("A")) {
      await step(1, "Sales", "POS: pelanggan latihan → produk → [Beli per Roll] centang 2 roll → Checkout (NET 30, Transfer bank) → nyalakan [Minta Faktur Pajak] → [Buat Sales Order]",
        "SO baru 2 roll 'Dipesan'; dua roll dicadangkan. Buku: belum ada jurnal", async () => {
          await masuk(r, "sales");
          await mulaiPos(r, "a-pos");
          const t = await tambahRoll(r, ctx.prod, 2, "a");
          const c = await checkout(r, { faktur: true, nama: "a" });
          assert(/NET 30/i.test(c.termin), `termin ${c.termin}`);
          const { so, msg } = await buatSo(r, "a");
          assert(so.items[0].qty_rolls === 2 || (so.allocations[0].rolls || []).length === 2, "SO bukan 2 roll");
          assert(so.needs_tax_invoice === true && so.payment_term_code === "NET30", "faktur/termin SO");
          assert(jurnalSo(so.id).length === 0, "SO baru sudah berjurnal");
          ctx.A = { so, rolls: so.allocations.flatMap((a) => a.rolls || []) };
          assert(ctx.A.rolls.length === 2, `roll dicadangkan ${ctx.A.rolls.length}`);
          r.note(`A · ${so.number}: 2 roll (${ctx.A.rolls.map((x) => `${x.roll_no} ${x.length || x.take_qty}`).join(", ")}) · DPP ${rp(so.net_subtotal)} · PPN ${rp(so.ppn_amount)} · total ${rp(so.grand_total)}`);
          return `${msg} · subtotal ${rp(t.subtotal)}`;
        });

      await step(2, "Admin Sales", "Meja Admin Sales → Pelacak SO: cari SO → [Periksa & lepas] → isi catatan → [Periksa & lepas ke gudang]",
        "Pesan 'diperiksa & dilepas ke gudang'; tugas ambil gudang lahir untuk 2 roll", async () => {
          const { msg, task } = await periksaLepas(r, ctx.A.so, "a");
          ctx.A.task = task;
          return `${msg} · tugas ${task.quantity}`;
        });

      await step(3, "Gudang", "Barang Keluar → tugas SO → pindai roll PERTAMA saja → [Kirim Pengambilan]",
        "Progres 1 dari 2 roll (50%); panel kirim 'Siap dikirim' = panjang roll pertama", async () => {
          await masuk(r, "warehouse");
          await bukaTugas(r, ctx.A.so, ctx.A.task, "a-gudang");
          const tk = await ambilRoll(r, ctx.A.task, ctx.A.rolls[0].roll_no, "a-roll1");
          assert(tk.picked_qty > 0 && tk.picked_qty < tk.quantity, `terambil ${tk.picked_qty}/${tk.quantity}`);
          return `terambil ${tk.picked_qty}/${tk.quantity} · status ${tk.status}`;
        });

      await step(4, "Manajer", "Operasi Gudang › Barang Keluar → tugas SO → Pemeriksaan Muat Akhir: isi alasan → [Override]",
        "Kotak oranye 'OVERRIDE …' — berlaku untuk roll pesanan ini yang sudah dicadangkan (kedua roll)", async () => {
          const t = await overrideMuat(r, ctx.A.so, ctx.A.task, "a");
          const lc = soDoc(ctx.A.so.id).loading_check || {};
          assert((lc.manifest || []).length === 2, `manifest override ${(lc.manifest || []).length} roll`);
          await bk.potret(r, "a-override", [r.tid("lc-last-result")]);
          return t;
        });

      await step(5, "Gudang", "Tugas SO → [Kirim Semua (panjang roll 1)] → [Kirim Sekarang]",
        "Notifikasi 'Barang terkirim · KSC/SJ-…'; panel 'Terkirim Sebagian'. Buku: jurnal pendapatan & HPP sebesar roll pertama saja", async () => {
          await masuk(r, "warehouse");
          await bukaTugas(r, ctx.A.so, ctx.A.task);
          const sj = await kirim(r, ctx.A.so, ctx.A.task, "a-sj1");
          const panel = await isiLayar(r.tid("outbound-task-panel"));
          assert(/Terkirim Sebagian/.test(panel), `panel: ${panel.slice(0, 200)}`);
          await bk.potret(r, "a-terkirim-sebagian", [r.tid("outbound-task-panel")]);
          const so = soDoc(ctx.A.so.id);
          assert(so.status === "partially_shipped", `status SO ${so.status}`);
          const rev = jurnalSo(so.id, "shipment_revenue"), cogs = jurnalSo(so.id, "shipment_cogs");
          assert(rev.length === 1 && cogs.length === 1, `jurnal SJ1: ${rev.length} pendapatan, ${cogs.length} HPP`);
          const porsi = sj.qty / so.items[0].quantity;
          const harapPiutang = r2(so.grand_total * porsi);
          cekJurnalSeimbang(rev[0], []);
          assert(dekat(sisi(rev[0], "1-1200", "D"), harapPiutang, 0.02), `piutang SJ1 ${sisi(rev[0], "1-1200", "D")} ≠ ${harapPiutang}`);
          assert(dekat(sisi(rev[0], "2-1200", "K"), r2(so.ppn_amount * porsi), 0.02), "PPN SJ1 tidak pro-rata");
          const hpp1 = r2((sj.rolls || []).reduce((s, x) => s + Number(x.extended_cost || 0), 0));
          cekJurnalSeimbang(cogs[0], [["5-1000", "D", hpp1], ["1-1300", "K", hpp1]]);
          ctx.A.sj1 = sj; ctx.A.rev1 = rev[0]; ctx.A.cogs1 = cogs[0];
          r.note(`A · SJ1 ${sj.shipment_no} ${sj.qty} ${so.items[0].unit} (${Math.round(porsi * 100)}%) · ${teksJe(rev[0])} | ${teksJe(cogs[0])}`);
          return `${sj.shipment_no} · ${teksJe(rev[0])} · ${teksJe(cogs[0])}`;
        });

      await step(6, "Finance", "Keuangan › Piutang › Penagihan & Penerimaan → baris SO; lalu tab Saldo & Umur → pelanggan → rincian",
        "Baris SO: Belum Lunas = piutang surat jalan pertama saja (bukan total SO); rincian: tercatat = SJ1, 'belum dikirim' = sisa", async () => {
          await masuk(r, finAkun);
          await bukaPenagihan(r, "a-fin");
          const row = await barisSo(r, ctx.A.so.id);
          const t = await isiLayar(row);
          const piutang1 = sisi(ctx.A.rev1, "1-1200", "D");
          assert(t.includes(angka(piutang1)), `baris penagihan: ${t}`);
          await bk.potret(r, "a-penagihan-sj1", [row]);
          await klikSorot(r, r.tid("hub-tab-ar-aging"), "a-tab-umur");
          await r.tid("ar-aging-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
          const crow = r.tid(`ar-aging-row-${ctx.cust.id}`);
          await crow.waitFor({ timeout: 15000 });
          await crow.click();
          await r.tid("ar-aging-detail-modal").waitFor({ timeout: 15000 });
          await r.tid(`ar-detail-row-${ctx.A.so.id}`).waitFor({ timeout: 15000 });
          await r.idle(800);
          const d = await isiLayar(r.tid(`ar-detail-row-${ctx.A.so.id}`));
          const belum = r2(ctx.A.so.grand_total - piutang1);
          assert(d.includes(angka(piutang1)) || d.includes(angka(ctx.A.so.grand_total)), `rincian SO: ${d}`);
          await bk.potret(r, "a-umur-rincian", [r.tid(`ar-detail-row-${ctx.A.so.id}`), r.tid("ar-aging-detail-summary")]);
          return `penagihan: ${t.slice(0, 140)} · rincian: ${d.slice(0, 160)} · belum dikirim ${rp(belum)}`;
        });

      await step(7, "Gudang", "Esok harinya: tugas SO → pindai roll KEDUA → [Kirim Pengambilan] → [Kirim Semua] → [Kirim Sekarang]",
        "Surat jalan kedua terbit; panel 'Terkirim Penuh!'. Buku: jurnal pendapatan kedua = sisa (total SO − SJ1), HPP roll kedua", async () => {
          await masuk(r, "warehouse");
          await bukaTugas(r, ctx.A.so, ctx.A.task);
          const tk = await ambilRoll(r, ctx.A.task, ctx.A.rolls[1].roll_no, "a-roll2");
          assert(dekat(tk.picked_qty, tk.quantity), `terambil ${tk.picked_qty}/${tk.quantity}`);
          const sj = await kirim(r, ctx.A.so, ctx.A.task, "a-sj2");
          const panel = await isiLayar(r.tid("outbound-task-panel"));
          assert(/Terkirim Penuh/.test(panel), `panel: ${panel.slice(0, 200)}`);
          await bk.potret(r, "a-terkirim-penuh", [r.tid("outbound-task-panel")]);
          const so = soDoc(ctx.A.so.id);
          ctx.A.so = so;
          assert(so.status === "shipped", `status SO ${so.status}`);
          const rev = jurnalSo(so.id, "shipment_revenue"), cogs = jurnalSo(so.id, "shipment_cogs");
          assert(rev.length === 2 && cogs.length === 2, `jurnal: ${rev.length} pendapatan, ${cogs.length} HPP`);
          const rev2 = rev.find((j) => j.source_id === sj.id), cogs2 = cogs.find((j) => j.source_id === sj.id);
          assert(rev2 && cogs2, "jurnal SJ2 tidak bersumber surat jalan kedua");
          cekJurnalSeimbang(rev2, [["1-1200", "D", r2(so.grand_total - sisi(ctx.A.rev1, "1-1200", "D"))],
            ["2-1200", "K", r2(so.ppn_amount - sisi(ctx.A.rev1, "2-1200", "K"))],
            ["4-1000", "K", r2(so.net_subtotal - sisi(ctx.A.rev1, "4-1000", "K"))]]);
          const hpp2 = r2((sj.rolls || []).reduce((s, x) => s + Number(x.extended_cost || 0), 0));
          cekJurnalSeimbang(cogs2, [["5-1000", "D", hpp2], ["1-1300", "K", hpp2]]);
          assert(dekat(saldo(rev, "1-1200"), so.grand_total), `Σ piutang 2 SJ ${saldo(rev, "1-1200")} ≠ total SO ${so.grand_total}`);
          ctx.A.sj2 = sj; ctx.A.rev2 = rev2; ctx.A.cogs2 = cogs2;
          r.note(`A · SJ2 ${sj.shipment_no} · ${teksJe(rev2)} | ${teksJe(cogs2)} · Σ piutang ${rp(saldo(rev, "1-1200"))} = total SO`);
          return `${sj.shipment_no} · ${teksJe(rev2)} · ${teksJe(cogs2)}`;
        });

      await step(8, "Finance", "Beranda Keuangan › Meja Keuangan → kartu [Faktur pajak perlu terbit]: ketik nomor SO → [Terbitkan]",
        "Satu faktur untuk seluruh pesanan (aturan PT: per pesanan); PPN faktur = PPN keluaran SJ1 + SJ2; faktur tanpa jurnal", async () => {
          await masuk(r, finAkun);
          await bukaMenu(r, "finance-tower", "finance-desk");
          await r.tid("finance-desk").waitFor();
          await r.tid("fin-desk-queue-faktur_pajak").waitFor({ timeout: 20000 });
          await r.tid("fin-desk-search-faktur_pajak").fill(ctx.A.so.number);
          const row = r.tid(`fin-desk-faktur_pajak-row-${ctx.A.so.id}`);
          await row.waitFor({ timeout: 20000 });
          await sorot(row);
          await klikSorot(r, r.tid(`fin-desk-faktur_pajak-action-${ctx.A.so.id}`), "a-faktur");
          await r.tid("fkt-modal").waitFor();   // pop-up pratinjau faktur → [Terbitkan]
          await r.tid("fkt-modal-submit").click();
          const msg = await tungguToast(r, /diterbitkan/, 20000);   // hasil = toast
          const fkt = mongo(`return db.tax_invoices.findOne({order_id:"${ctx.A.so.id}",status:"normal"},{_id:0})`);
          assert(fkt && msg.includes(fkt.number), `faktur: ${msg}`);
          const ppnBuku = r2(sisi(ctx.A.rev1, "2-1200", "K") + sisi(ctx.A.rev2, "2-1200", "K"));
          assert(dekat(fkt.ppn_amount, ppnBuku), `PPN faktur ${fkt.ppn_amount} ≠ PPN keluaran 2 SJ ${ppnBuku}`);
          assert(mongo(`return db.journal_entries.countDocuments({source_id:"${fkt.id}"})`) === 0, "faktur membuat jurnal");
          ctx.A.fkt = fkt;
          await bk.potret(r, "a-faktur-terbit", [toastLoc(r, /diterbitkan/)]);
          return `${msg} · PPN ${rp(fkt.ppn_amount)} = ${rp(sisi(ctx.A.rev1, "2-1200", "K"))} + ${rp(sisi(ctx.A.rev2, "2-1200", "K"))}`;
        });

      await step(9, "Finance", "Penagihan & Penerimaan → ikon dompet pada baris SO → alokasi = total SO (dua surat jalan) → isi No. referensi → [Simpan kwitansi] → [Ya, simpan]",
        "Satu kwitansi melunasi kedua surat jalan. Buku: Kas Besar / Bank (D) = Piutang Usaha (K) = total SO; piutang SO = 0", async () => {
          await bukaFormBayar(r, ctx.A.so.id, "a-bayar");
          const alloc = Number(await r.tid(`ar-receipt-alloc-${ctx.A.so.id}`).inputValue());
          assert(dekat(alloc, ctx.A.so.grand_total), `alokasi ${alloc} ≠ total ${ctx.A.so.grand_total}`);
          await r.tid("ar-receipt-reference").fill(`TRF-S3A-LATIH${NO}`);
          await r.idle(1200);
          const note = await simpanKwitansi(r, "a-bayar");
          const rc = kwitansiSo(ctx.A.so.id);
          assert(rc.length === 1 && dekat(rc[0].amount, ctx.A.so.grand_total), `kwitansi ${rc.length}`);
          const je = jurnalKas(rc[0].cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", ctx.A.so.grand_total], ["1-1200", "K", ctx.A.so.grand_total]]);
          assert(sisaSo(ctx.A.so.id) <= 0.01, "SO belum lunas");
          const semua = [...jurnalSo(ctx.A.so.id), je];
          assert(dekat(saldo(semua, "1-1200"), 0), `piutang SO ${saldo(semua, "1-1200")}`);
          ctx.A.rc = rc[0]; ctx.A.jeRc = je;
          return `${note} · ${teksJe(je)} · piutang SO ${rp(saldo(semua, "1-1200"))}`;
        });

      await step(10, "Finance", "Pusat Dokumen › Jejak Dokumen → ketik nomor SO → klik hasilnya",
        "Rantai: SO → dua surat jalan → jurnal pendapatan & HPP masing-masing; faktur pajak; kwitansi → kas → jurnal penerimaan", async () => {
          await bk.menu(r, "alat", "document-center", "doc-trace");
          await r.tid("doc-trace-view").waitFor();
          await r.tid("trace-search-input").fill(ctx.A.so.number);
          await r.tid(`trace-result-${ctx.A.so.id}`).click();
          await r.tid("trace-graph").waitFor({ timeout: 20000 });
          await r.idle(1500);
          const g = await r.text("trace-graph");
          const harus = [ctx.A.so.number, ctx.A.sj1.shipment_no, ctx.A.sj2.shipment_no, ctx.A.rev1.number, ctx.A.rev2.number,
            ctx.A.cogs1.number, ctx.A.cogs2.number, ctx.A.rc.number];
          const hilang = harus.filter((x) => !g.includes(x));
          assert(!hilang.length, `jejak tidak memuat: ${hilang.join(", ")}`);
          await bk.potret(r, "a-jejak", [r.tid("trace-anchor-card")], { full: true });
          return `${harus.join(" · ")}${g.includes(ctx.A.fkt.number) ? ` · ${ctx.A.fkt.number}` : " · (faktur tidak tampil)"}`;
        });
    }

    // ══ B. UANG MUKA (DP 50%) ══════════════════════════════════════════════════════════════════════════════════════
    if (ada("B")) {
      await step(11, "Sales", "POS: pelanggan latihan → 1 roll → Checkout: termin 'DP 50% + Pelunasan', Transfer bank → [Buat Sales Order]",
        "SO baru bertermin DP 50%. Buku: belum ada jurnal", async () => {
          await masuk(r, "sales");
          await mulaiPos(r);
          await tambahRoll(r, ctx.prod, 1);
          const c = await checkout(r, { termin: /DP 50%/, nama: "b" });
          assert(/DP 50%/.test(c.termin), `termin ${c.termin}`);
          const { so, msg } = await buatSo(r, "b");
          assert(so.payment_term_code === "DP50", `termin SO ${so.payment_term_code}`);
          ctx.B = { so, roll: so.allocations[0].rolls[0] };
          ctx.B.dp = r2(so.grand_total * 0.5);
          r.note(`B · ${so.number}: total ${rp(so.grand_total)} · DP 50% ${rp(ctx.B.dp)}`);
          return msg;
        });

      await step(12, "Admin Sales", "Meja Admin Sales → Pelacak SO → [Periksa & lepas] → [Periksa & lepas ke gudang]",
        "SO dilepas ke gudang; tagihan uang muka lahir (jatuh tempo hari ini)", async () => {
          const { msg, task } = await periksaLepas(r, ctx.B.so, "b");
          ctx.B.task = task;
          return msg;
        });

      await step(13, "Gudang", "Barang Keluar → tugas SO → pindai roll → [Kirim Pengambilan]",
        "Panel merah 'Tertahan — belum dibayar sesuai termin: wajib dibayar Rp … (50%) sebelum kirim · sudah dibayar Rp 0'; tombol kirim mati", async () => {
          await masuk(r, "warehouse");
          await bukaTugas(r, ctx.B.so, ctx.B.task, "b-gudang");
          await ambilRoll(r, ctx.B.task, ctx.B.roll.roll_no);
          await r.tid("outbound-gate-summary").waitFor({ timeout: 20000 });
          const g = await r.text("outbound-gate-summary");
          assert(/Tertahan/.test(g) && g.includes(angka(ctx.B.dp)), `gerbang: ${g}`);
          assert(await r.tid(`dispatch-all-${ctx.B.task.id}`).isDisabled(), "tombol kirim tidak mati");
          await bk.potret(r, "b-tertahan", [r.tid("outbound-gate-summary"), r.tid(`dispatch-all-${ctx.B.task.id}`)]);
          return g;
        });

      await step(14, "Finance", "Penagihan & Penerimaan → baris SO (Belum Lunas = uang muka) → ikon dompet → alokasi = nominal uang muka → No. referensi → [Simpan kwitansi] → [Ya, simpan]",
        "Kwitansi uang muka. Buku: Kas Besar / Bank (D) = Uang Muka Pelanggan 2-1400 (K) — belum ada piutang & pendapatan", async () => {
          await masuk(r, finAkun);
          await bukaPenagihan(r, "b-fin");
          const row = await barisSo(r, ctx.B.so.id);
          const t = await isiLayar(row);
          assert(t.includes(angka(ctx.B.dp)), `baris uang muka: ${t}`);
          await bk.potret(r, "b-penagihan-dp", [row]);
          await bukaFormBayar(r, ctx.B.so.id, "b-dp");
          const awal = Number(await r.tid(`ar-receipt-alloc-${ctx.B.so.id}`).inputValue());
          if (!dekat(awal, ctx.B.dp)) {
            r.note(`B · form terima pembayaran mengisi alokasi ${rp(awal)} (sisa SO), bukan uang muka ${rp(ctx.B.dp)} — diketik ulang`);
            await r.tid(`ar-receipt-alloc-${ctx.B.so.id}`).fill(String(ctx.B.dp));
          }
          await r.tid("ar-receipt-reference").fill(`TRF-S3B-DP-LATIH${NO}`);
          await r.idle(1500);
          const hint = await r.text("ar-receipt-variance-hint").catch(() => "");
          await bk.potret(r, "b-form-dp", [r.tid(`ar-receipt-alloc-${ctx.B.so.id}`), r.tid("ar-receipt-variance-hint")]);
          const note = await simpanKwitansi(r, "b-dp");
          const rc = kwitansiSo(ctx.B.so.id);
          assert(rc.length === 1 && dekat(rc[0].amount, ctx.B.dp), "kwitansi DP");
          const je = jurnalKas(rc[0].cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", ctx.B.dp], ["2-1400", "K", ctx.B.dp]]);
          assert(sisi(je, "1-1200", "K") === 0, "DP mengkredit piutang padahal barang belum dikirim");
          assert(dekat(umTertahan(ctx.B.so.id), ctx.B.dp), `uang muka tertahan ${umTertahan(ctx.B.so.id)}`);
          ctx.B.rcDp = rc[0]; ctx.B.jeDp = je;
          return `${note} · ${teksJe(je)} · petunjuk: ${hint.slice(0, 120)}`;
        });

      await step(15, "Finance", "Keuangan › Piutang › Titipan & Saldo Kredit → cari pelanggan",
        "Kolom 'Uang muka' = DP (kewajiban sampai barang dikirim)", async () => {
          await klikSorot(r, r.tid("hub-tab-customer-credit"), "b-tab-titipan");
          await r.tid("cc-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
          const row = r.tid(`cc-row-${ctx.cust.id}`);
          await row.waitFor({ timeout: 15000 });
          await r.idle(800);
          const um = await r.text(`cc-advance-${ctx.cust.id}`);
          assert(dekat(num(um), ctx.B.dp, 1), `uang muka layar ${um}`);
          await bk.potret(r, "b-uang-muka", [r.tid(`cc-advance-${ctx.cust.id}`)]);
          return await isiLayar(row);
        });

      await step(16, "Manajer", "Barang Keluar → tugas SO → Pemeriksaan Muat Akhir → [Override]",
        "Kotak 'OVERRIDE …'; panel bayar kini 'Boleh kirim — termin terpenuhi'", async () => {
          const t = await overrideMuat(r, ctx.B.so, ctx.B.task, "b");
          await r.tid("outbound-gate-summary").waitFor({ timeout: 20000 });
          const g = await r.text("outbound-gate-summary");
          assert(/Boleh kirim/.test(g), `gerbang: ${g}`);
          await bk.potret(r, "b-boleh-kirim", [r.tid("outbound-gate-summary"), r.tid("lc-last-result")]);
          return `${t} · ${g}`;
        });

      await step(17, "Gudang", "Tugas SO → [Kirim Semua] → [Kirim Sekarang]",
        "Surat jalan terbit. Buku: pendapatan (Piutang D total = Pendapatan K + PPN K), HPP, dan reklas uang muka (Uang Muka Pelanggan D / Piutang K = DP)", async () => {
          await masuk(r, "warehouse");
          await bukaTugas(r, ctx.B.so, ctx.B.task);
          const sj = await kirim(r, ctx.B.so, ctx.B.task, "b-sj");
          const so = soDoc(ctx.B.so.id);
          ctx.B.so = so;
          const rev = jurnalSo(so.id, "shipment_revenue")[0], cogs = jurnalSo(so.id, "shipment_cogs")[0];
          const re = jurnalSo(so.id, "advance_reclass")[0];
          assert(rev && cogs && re, "jurnal kirim/reklas tidak lengkap");
          cekJurnalSeimbang(rev, [["1-1200", "D", so.grand_total], ["4-1000", "K", so.net_subtotal], ["2-1200", "K", so.ppn_amount]]);
          cekJurnalSeimbang(cogs, []);
          cekJurnalSeimbang(re, [["2-1400", "D", ctx.B.dp], ["1-1200", "K", ctx.B.dp]]);
          assert(umTertahan(so.id) <= 0.01, `uang muka masih tertahan ${umTertahan(so.id)}`);
          ctx.B.sj = sj; ctx.B.rev = rev; ctx.B.cogs = cogs; ctx.B.re = re;
          r.note(`B · ${sj.shipment_no} · ${teksJe(rev)} | ${teksJe(cogs)} | reklas ${teksJe(re)}`);
          return `${sj.shipment_no} · ${teksJe(rev)} · reklas ${teksJe(re)}`;
        });

      await step(18, "Finance", "Penagihan & Penerimaan → baris SO (sisa 50%) → ikon dompet → alokasi = sisa → No. referensi → [Simpan kwitansi] → [Ya, simpan]",
        "SO lunas. Buku: Kas Besar / Bank (D) = Piutang Usaha (K) = sisa; uang muka pesanan Rp 0; piutang SO Rp 0", async () => {
          await masuk(r, finAkun);
          await bukaFormBayar(r, ctx.B.so.id, "b-lunas");
          const sisa = r2(ctx.B.so.grand_total - ctx.B.dp);
          const alloc = Number(await r.tid(`ar-receipt-alloc-${ctx.B.so.id}`).inputValue());
          assert(dekat(alloc, sisa), `alokasi ${alloc} ≠ sisa ${sisa}`);
          await r.tid("ar-receipt-reference").fill(`TRF-S3B-LUNAS-LATIH${NO}`);
          await r.idle(1200);
          const note = await simpanKwitansi(r, "b-lunas");
          const rc = kwitansiSo(ctx.B.so.id);
          assert(rc.length === 2, `kwitansi ${rc.length}`);
          const je = jurnalKas(rc[1].cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", sisa], ["1-1200", "K", sisa]]);
          const semua = [...jurnalSo(ctx.B.so.id), ctx.B.jeDp, je];
          assert(dekat(saldo(semua, "1-1200"), 0), `piutang SO ${saldo(semua, "1-1200")}`);
          assert(dekat(saldo(semua, "2-1400"), 0), `uang muka SO di buku ${saldo(semua, "2-1400")}`);
          assert(dekat(saldo(semua, "1-1100"), ctx.B.so.grand_total), "kas masuk ≠ total SO");
          assert(sisaSo(ctx.B.so.id) <= 0.01, "SO belum lunas");
          ctx.B.jeLunas = je;
          return `${note} · ${teksJe(je)} · piutang SO ${rp(saldo(semua, "1-1200"))} · uang muka SO ${rp(saldo(semua, "2-1400"))}`;
        });
    }

    // ══ C. BATAL SO BER-DP ═════════════════════════════════════════════════════════════════════════════════════════
    if (ada("C")) {
      await step(19, "Sales", "POS: pelanggan latihan → 1 roll → Checkout: termin 'DP 50% + Pelunasan' → [Buat Sales Order]",
        "SO baru bertermin DP 50%; roll dicadangkan", async () => {
          await masuk(r, "sales");
          await mulaiPos(r);
          await tambahRoll(r, ctx.prod, 1);
          await checkout(r, { termin: /DP 50%/ });
          const { so, msg } = await buatSo(r, "c");
          ctx.C = { so, roll: so.allocations[0].rolls[0], dp: r2(so.grand_total * 0.5) };
          r.note(`C · ${so.number}: total ${rp(so.grand_total)} · DP ${rp(ctx.C.dp)} · roll ${ctx.C.roll.roll_no}`);
          return msg;
        });

      await step(20, "Admin Sales", "Meja Admin Sales → [Periksa & lepas] → [Periksa & lepas ke gudang]",
        "SO dilepas ke gudang", async () => {
          const { msg, task } = await periksaLepas(r, ctx.C.so, "c");
          ctx.C.task = task;
          return msg;
        });

      await step(21, "Finance", "Penagihan & Penerimaan → baris SO → ikon dompet → alokasi = uang muka → [Simpan kwitansi] → [Ya, simpan]",
        "Buku: Kas Besar / Bank (D) = Uang Muka Pelanggan (K) = DP", async () => {
          await masuk(r, finAkun);
          await bukaFormBayar(r, ctx.C.so.id, "c-dp");
          await r.tid(`ar-receipt-alloc-${ctx.C.so.id}`).fill(String(ctx.C.dp));
          await r.tid("ar-receipt-reference").fill(`TRF-S3C-DP-LATIH${NO}`);
          await r.idle(1500);
          const note = await simpanKwitansi(r, "c-dp");
          const rc = kwitansiSo(ctx.C.so.id);
          assert(rc.length === 1 && dekat(rc[0].amount, ctx.C.dp), "kwitansi DP");
          const je = jurnalKas(rc[0].cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", ctx.C.dp], ["2-1400", "K", ctx.C.dp]]);
          ctx.C.rc = rc[0]; ctx.C.je = je;
          return `${note} · ${teksJe(je)}`;
        });

      await step(22, "Admin Sales", "Penjualan › Pesanan → cari SO → [Lihat detail & aksi] → [Batal] → baca catatan kuning → isi alasan → [Ya, Batalkan SO]",
        "Catatan 'Pesanan ini sudah dibayar Rp … uang itu menjadi titipan pelanggan'; pesan '… dibatalkan, stok dilepas. Uang muka Rp … menjadi titipan pelanggan.' Buku: tanpa jurnal baru; roll kembali bebas", async () => {
          await masuk(r, "salesadmin");
          await bukaMenu(r, "sales-orders", "", { grup: "penjualan" });
          await r.tid("orders-search-input").fill(ctx.C.so.number);
          await r.idle(1000);
          await r.tid(`order-card-${ctx.C.so.id}`).click();
          await r.idle(800);
          await r.tid("so-open-full-detail").click();
          const b = r.tid(`cancel-order-button-${ctx.C.so.id}`);
          await b.waitFor({ timeout: 20000 });
          await klikSorot(r, b, "c-batal");
          await r.tid("cancel-order-dialog").waitFor();
          const cat = await r.text("cancel-order-paid-note");
          assert(cat.includes(angka(ctx.C.dp)) && /titipan/.test(cat), `catatan: ${cat}`);
          await r.tid("cancel-order-reason").fill("Pelanggan membatalkan pesanan sebelum barang dikirim");
          await klikSorot(r, r.tid("cancel-order-confirm"), "c-batal-dialog", { locator: r.tid("cancel-order-dialog") });
          const msg = await tungguTeks(r, "order-flash", /dibatalkan/, 20000);
          await bk.potret(r, "c-batal-pesan", [r.tid("order-flash")]);
          const so = soDoc(ctx.C.so.id);
          assert(so.status === "cancelled", `status SO ${so.status}`);
          assert(/Uang muka Rp/.test(msg) && msg.includes(angka(ctx.C.dp)), `pesan batal: ${msg}`);
          assert(dekat(titipanPelanggan(ctx.cust.id), r2(ctx.titipAwal + ctx.C.dp)), `titipan ${titipanPelanggan(ctx.cust.id)} ≠ DP ${ctx.C.dp}`);
          assert(!mongo(`return db.journal_entries.countDocuments({$or:[{"ref.order_id":"${ctx.C.so.id}"},{source_id:"${ctx.C.so.id}"}]})`),
            "pembatalan membuat jurnal pesanan");
          assert(dekat(saldo(jurnalKas(ctx.C.rc.cash_txn_id), "2-1400"), -ctx.C.dp), "jurnal uang muka kwitansi berubah");
          assert(dekat(sisaSo(ctx.C.so.id), so.grand_total), "terbayar SO batal ≠ 0");
          const roll = mongo(`return db.inventory_rolls.findOne({id:"${ctx.C.roll.roll_id || ctx.C.roll.id}"},{_id:0,status:1,reserved_ref:1})`);
          assert(roll && !roll.reserved_ref, `roll masih dicadangkan: ${JSON.stringify(roll)}`);
          const tugas = mongo(`return db.wms_tasks.findOne({id:"${ctx.C.task.id}"},{_id:0,status:1})`);
          assert(tugas.status === "cancelled", `tugas gudang ${tugas.status}`);
          r.note(`C · ${so.number} batal · uang muka ${rp(ctx.C.dp)} → titipan pelanggan ${rp(titipanPelanggan(ctx.cust.id))} · tanpa jurnal baru`);
          return `${msg.slice(0, 200)} · roll ${roll.status} · tugas ${tugas.status}`;
        });

      await step(23, "Finance", "Keuangan › Piutang › Titipan & Saldo Kredit → cari pelanggan",
        "Kolom 'Uang muka' Rp 0, kolom 'Titipan' = DP pesanan batal", async () => {
          await masuk(r, finAkun);
          await bukaMenu(r, "ar-aging", "customer-credit");
          await r.tid("cc-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
          const row = r.tid(`cc-row-${ctx.cust.id}`);
          await row.waitFor({ timeout: 15000 });
          await r.idle(800);
          const dep = await r.text(`cc-deposit-${ctx.cust.id}`);
          assert(dekat(num(dep), r2(ctx.titipAwal + ctx.C.dp), 1), `titipan layar ${dep}`);
          const um = await r.text(`cc-advance-${ctx.cust.id}`).catch(() => "Rp 0");
          assert(num(um) < 1, `uang muka masih ${um}`);
          await bk.potret(r, "c-titipan", [r.tid(`cc-deposit-${ctx.cust.id}`), r.tid(`cc-advance-${ctx.cust.id}`)]);
          return await isiLayar(row);
        });

      await step(24, "Finance", "Keuangan › Piutang › Kasus → [Kasus baru]: jenis 'Pengembalian dana ke pelanggan', pelanggan, nominal = titipan, cerita → [Buat kasus]",
        "Kasus baru berstatus terbuka (Finance melapor; uang keluar diselesaikan Manajer)", async () => {
          await bukaKasus(r);
          await klikSorot(r, r.tid("case-new"), "c-kasus-baru");
          await r.tid("case-create-modal").waitFor();
          await pilihTeks(r, "case-create-type", /Pengembalian dana ke pelanggan/);
          await pilihTeks(r, "case-create-customer", new RegExp(PELANGGAN), `Toko Kain Peserta ${NO}`);
          await r.tid("case-create-amount").fill(String(ctx.C.dp));
          await r.tid("case-create-desc").fill(`Pesanan ${ctx.C.so.number} dibatalkan pelanggan; uang muka diminta kembali lewat transfer`);
          await bk.potret(r, "c-kasus-isi", [r.tid("case-create-type"), r.tid("case-create-customer"), r.tid("case-create-amount")]);
          await r.tid("case-create-submit").click();
          await r.tid("case-create-modal").waitFor({ state: "detached", timeout: 20000 });
          const kasus = mongo(`return db.finance_cases.find({customer_id:"${ctx.cust.id}",case_type:"refund_pelanggan"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
          assert(kasus && dekat(kasus.amount, ctx.C.dp), "kasus tidak tersimpan");
          ctx.C.kasus = kasus;
          return `${kasus.number} · ${kasus.status} · ${rp(kasus.amount)}`;
        });

      await step(25, "Manajer", "Kasus → buka kasus → [Selesaikan lewat playbook] → 'Kembalikan dari uang muka pelanggan' → nominal & alasan → [Jalankan & selesaikan]",
        "Kasus selesai. Buku: transaksi kas keluar BCA; Uang Muka Pelanggan (D) = Kas Besar / Bank (K) = DP; titipan pelanggan Rp 0", async () => {
          await masuk(r, "manager");
          await bukaKasus(r);
          const row = r.tid(`case-row-${ctx.C.kasus.id}`);
          await row.waitFor({ timeout: 20000 });
          await row.click();
          await r.tid("case-detail").waitFor();
          await klikSorot(r, r.tid("case-open-wizard"), "c-kasus-buka");
          await r.tid("case-wizard").waitFor();
          await r.tid("case-action-refund_pelanggan").click();
          const nominal = num(await r.tid("case-field-amount").inputValue());
          assert(dekat(nominal, ctx.C.dp, 1), `nominal ${nominal}`);
          const bca = mongo(`return db.bank_accounts.findOne({entity_id:"${KSC}",name:"BCA Operasional KSC"},{_id:0,id:1})`);
          await pilihTeks(r, "case-field-account", /BCA Operasional KSC/);
          await r.tid("case-field-reason").click();
          await r.page.getByRole("option").first().click();
          await r.tid("case-field-note").fill("Uang muka pesanan batal dikembalikan ke rekening pelanggan");
          await bk.potret(r, "c-kasus-selesaikan", [r.tid("case-action-refund_pelanggan"), r.tid("case-field-amount"),
            r.tid("case-field-account"), r.tid("case-wizard-submit")]);
          await r.tid("case-wizard-submit").click();
          await r.tid("case-wizard").waitFor({ state: "detached", timeout: 30000 });
          await r.idle(1000);
          const k = mongo(`return db.finance_cases.findOne({id:"${ctx.C.kasus.id}"},{_id:0,status:1,number:1})`);
          assert(k.status === "resolved", `status kasus ${k.status}`);
          const kas = mongo(`return db.cash_transactions.find({ref_type:"ar_refund",ref_id:"${ctx.C.kasus.id}"},{_id:0}).toArray()`);
          assert(kas.length === 1 && kas[0].direction === "out" && dekat(kas[0].amount, ctx.C.dp), "kas keluar refund");
          assert(kas[0].account_id === bca.id, `rekening refund ${kas[0].account_id} ≠ BCA Operasional KSC`);
          const je = jurnalKas(kas[0].id)[0];
          cekJurnalSeimbang(je, [["2-1400", "D", ctx.C.dp], ["1-1100", "K", ctx.C.dp]]);
          assert(dekat(titipanPelanggan(ctx.cust.id), ctx.titipAwal), `titipan sesudah refund ${titipanPelanggan(ctx.cust.id)}`);
          const um = r2(saldo([ctx.C.je, je], "2-1400"));
          assert(dekat(um, 0), `uang muka DP batal di buku ${um}`);
          ctx.C.jeRefund = je;
          await bk.potret(r, "c-kasus-selesai", [r.tid("case-detail-status")]);
          return `${k.number} ${k.status} · ${kas[0].number} · ${teksJe(je)} · 2-1400 DP batal ${rp(um)}`;
        });
    }

    // ══ D. SATU TRANSFER UNTUK BEBERAPA SO ═════════════════════════════════════════════════════════════════════════
    if (ada("D")) {
      ctx.D = { bayar: r2(Math.round(ctx.so1.total) + 1000000) };
      await step(26, "Finance", `Penagihan & Penerimaan → ikon dompet pada SO-1 → pilih [Tertua dulu] → *Nominal diterima* = SO-1 penuh + Rp 1.000.000 → No. referensi → [Simpan kwitansi]`,
        "Petunjuk 'Kurang bayar … dari sisa tagihan pesanan tujuan' (tiga tagihan terbuka)", async () => {
          await masuk(r, finAkun);
          await bukaFormBayar(r, ctx.so1.so_id, "d");
          await klikSorot(r, r.tid("ar-receipt-mode-auto"), "d-tertua-dulu");
          await r.tid("ar-receipt-amount").waitFor();
          await r.tid("ar-receipt-amount").fill(String(ctx.D.bayar));
          await r.tid("ar-receipt-reference").fill(`TRF-S3D-LATIH${NO}`);
          await r.page.waitForFunction(() => /Kurang bayar/i.test(
            (document.querySelector('[data-testid="ar-receipt-variance-hint"]') || {}).innerText || ""), null, { timeout: 15000 });
          const hint = await r.text("ar-receipt-variance-hint");
          await bk.potret(r, "d-form", [r.tid("ar-receipt-amount"), r.tid("ar-receipt-variance-hint")]);
          return hint;
        });

      await step(27, "Finance", "Jendela 'Selisih Pembayaran · Kurang bayar' → 'Sisa tetap jadi piutang', alasan 'Bayar sebagian (disepakati)' → simpan → [Ya, simpan]",
        "Satu kwitansi dua alokasi: SO-1 lunas, SO-2 dibayar Rp 1.000.000, SO-3 utuh. Buku: Bank (D) = Piutang (K) = uang masuk", async () => {
          const note = await simpanKwitansi(r, "d", { keputusan: "outstanding", alasan: "Bayar sebagian (disepakati)",
            catatan: "Pelanggan melunasi tagihan lama dan mencicil tagihan kedua" });
          const rc = mongo(`return db.ar_receipts.find({customer_id:"${ctx.cust.id}",reference_no:"TRF-S3D-LATIH${NO}",status:{$ne:"void"}},{_id:0}).toArray()`);
          assert(rc.length === 1, `kwitansi ${rc.length}`);
          const al = Object.fromEntries((rc[0].allocations || []).map((a) => [a.order_id, r2(a.applied ?? a.amount)]));
          assert(dekat(al[ctx.so1.so_id], ctx.so1.total) && dekat(al[ctx.so2.so_id], r2(ctx.D.bayar - ctx.so1.total)),
            `alokasi: ${JSON.stringify(al)}`);
          assert(!al[ctx.so3.so_id], "SO-3 ikut teralokasi");
          const je = jurnalKas(rc[0].cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", ctx.D.bayar], ["1-1200", "K", ctx.D.bayar]]);
          assert(sisaSo(ctx.so1.so_id) <= 0.01, "SO-1 belum lunas");
          ctx.D.sisa2 = sisaSo(ctx.so2.so_id);
          assert(dekat(ctx.D.sisa2, r2(ctx.so2.total - (ctx.D.bayar - ctx.so1.total))), `sisa SO-2 ${ctx.D.sisa2}`);
          assert(dekat(sisaSo(ctx.so3.so_id), ctx.so3.total), "SO-3 berubah");
          ctx.D.rc = rc[0]; ctx.D.je = je;
          return `${note} · ${teksJe(je)} · sisa SO-2 ${rp(ctx.D.sisa2)}`;
        });

      await step(28, "Finance", "Tab Saldo & Umur → cari pelanggan → klik baris → rincian per pesanan",
        "SO-1 tidak ada lagi; SO-2 sisa (dibayar sebagian); SO-3 utuh — keduanya 'Belum jatuh tempo'", async () => {
          await klikSorot(r, r.tid("hub-tab-ar-aging"), "d-tab-umur");
          await r.tid("ar-aging-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
          const crow = r.tid(`ar-aging-row-${ctx.cust.id}`);
          await crow.waitFor({ timeout: 15000 });
          await r.idle(600);
          const t = await isiLayar(crow);
          const harap = r2(ctx.D.sisa2 + ctx.so3.total);
          assert(t.includes(angka(harap)), `baris umur: ${t} (harap ${rp(harap)})`);
          await crow.click();
          await r.tid("ar-aging-detail-modal").waitFor({ timeout: 15000 });
          await r.tid(`ar-detail-row-${ctx.so2.so_id}`).waitFor({ timeout: 15000 });
          assert(!(await r.tid(`ar-detail-row-${ctx.so1.so_id}`).count()), "SO-1 masih tampil");
          const d2 = await isiLayar(r.tid(`ar-detail-row-${ctx.so2.so_id}`));
          assert(d2.includes(angka(ctx.D.sisa2)), `rincian SO-2: ${d2}`);
          await bk.potret(r, "d-umur-rincian", [r.tid(`ar-detail-row-${ctx.so2.so_id}`), r.tid(`ar-detail-row-${ctx.so3.so_id}`)]);
          return `${t.slice(0, 160)} · SO-2: ${d2.slice(0, 120)}`;
        });
    }

    // ══ E. TRANSFER DIPOTONG BIAYA BANK ════════════════════════════════════════════════════════════════════════════
    if (ada("E")) {
      await step(29, "Finance", `Penagihan & Penerimaan → SO-2 → ikon dompet → alokasi = sisa − ${rp(BIAYA_BANK)} (yang benar-benar masuk) → [Simpan kwitansi] → 'Sisa tetap jadi piutang', alasan 'Dipotong biaya bank' → [Ya, simpan]`,
        `Petunjuk 'Kurang bayar ${rp(BIAYA_BANK)}' (di atas toleransi Rp 5.000) → keputusan wajib; SO-2 sisa ${rp(BIAYA_BANK)}. Buku: Bank (D) = Piutang (K) = uang masuk`, async () => {
          await masuk(r, finAkun);
          ctx.E = { sisa2: sisaSo(ctx.so2.so_id) };
          ctx.E.masuk2 = r2(ctx.E.sisa2 - BIAYA_BANK);
          await bukaFormBayar(r, ctx.so2.so_id, "e-bank");
          await r.tid(`ar-receipt-alloc-${ctx.so2.so_id}`).fill(String(ctx.E.masuk2));
          await r.tid("ar-receipt-reference").fill(`TRF-S3E-LATIH${NO}`);
          await r.page.waitForFunction(() => /Kurang bayar/i.test(
            (document.querySelector('[data-testid="ar-receipt-variance-hint"]') || {}).innerText || ""), null, { timeout: 15000 });
          const hint = await r.text("ar-receipt-variance-hint");
          assert(hint.includes(angka(BIAYA_BANK)), `petunjuk: ${hint}`);
          await bk.potret(r, "e-form-bank", [r.tid(`ar-receipt-alloc-${ctx.so2.so_id}`), r.tid("ar-receipt-variance-hint")]);
          const note = await simpanKwitansi(r, "e-bank", { keputusan: "outstanding", alasan: "Dipotong biaya bank",
            catatan: "Transfer antarbank dipotong biaya Rp 6.500" });
          const rc = mongo(`return db.ar_receipts.findOne({reference_no:"TRF-S3E-LATIH${NO}",status:{$ne:"void"}},{_id:0})`);
          assert(rc && dekat(rc.amount, ctx.E.masuk2), "kwitansi E");
          const je = jurnalKas(rc.cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", ctx.E.masuk2], ["1-1200", "K", ctx.E.masuk2]]);
          assert(dekat(sisaSo(ctx.so2.so_id), BIAYA_BANK), `sisa SO-2 ${sisaSo(ctx.so2.so_id)}`);
          ctx.E.rc = rc; ctx.E.je = je;
          return `${note} · ${teksJe(je)}`;
        });

      await step(30, "Finance", `Kasus → [Kasus baru]: jenis 'Nominal kurang karena biaya bank', pelanggan, nominal ${rp(BIAYA_BANK)}, cerita → [Buat kasus]`,
        "Kasus biaya bank terbuka", async () => {
          await bukaKasus(r);
          await r.tid("case-new").click();
          await r.tid("case-create-modal").waitFor();
          await pilihTeks(r, "case-create-type", /biaya bank/i);
          await pilihTeks(r, "case-create-customer", new RegExp(PELANGGAN), `Toko Kain Peserta ${NO}`);
          await r.tid("case-create-amount").fill(String(BIAYA_BANK));
          await r.tid("case-create-desc").fill(`Transfer pelunasan ${ctx.so2.so} masuk kurang ${rp(BIAYA_BANK)} karena biaya transfer antarbank`);
          await bk.potret(r, "e-kasus-isi", [r.tid("case-create-type"), r.tid("case-create-amount")]);
          await r.tid("case-create-submit").click();
          await r.tid("case-create-modal").waitFor({ state: "detached", timeout: 20000 });
          const kasus = mongo(`return db.finance_cases.find({customer_id:"${ctx.cust.id}",case_type:"selisih_biaya_bank"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
          assert(kasus, "kasus biaya bank tidak tersimpan");
          ctx.E.kasus = kasus;
          return `${kasus.number} · ${kasus.status}`;
        });

      await step(31, "Manajer", "Kasus → buka kasus → [Selesaikan lewat playbook] → 'Bebankan selisih ke biaya bank' → pilih SO-2, nominal → alasan → [Jalankan & selesaikan]",
        `Kasus selesai; SO-2 lunas. Buku: Beban Administrasi Bank 6-8000 (D) = Piutang Usaha (K) = ${rp(BIAYA_BANK)}`, async () => {
          await masuk(r, "manager");
          await bukaKasus(r);
          const row = r.tid(`case-row-${ctx.E.kasus.id}`);
          await row.waitFor({ timeout: 20000 });
          await row.click();
          await r.tid("case-detail").waitFor();
          await r.tid("case-open-wizard").click();
          await r.tid("case-wizard").waitFor();
          await r.tid("case-action-bebankan_biaya_bank").click();
          await pilihTeks(r, "case-field-order", new RegExp(ctx.so2.so.replace("/", "\\/")));
          const nominal = num(await r.tid("case-field-amount").inputValue());
          if (!dekat(nominal, BIAYA_BANK, 1)) await r.tid("case-field-amount").fill(String(BIAYA_BANK));
          await r.tid("case-field-reason").click();
          await r.page.getByRole("option").first().click();
          await bk.potret(r, "e-kasus-selesaikan", [r.tid("case-action-bebankan_biaya_bank"), r.tid("case-field-order"), r.tid("case-wizard-submit")]);
          await r.tid("case-wizard-submit").click();
          await r.tid("case-wizard").waitFor({ state: "detached", timeout: 30000 });
          await r.idle(1000);
          const k = mongo(`return db.finance_cases.findOne({id:"${ctx.E.kasus.id}"},{_id:0,status:1,number:1})`);
          assert(k.status === "resolved", `status kasus ${k.status}`);
          const je = mongo(`return db.journal_entries.find({status:{$ne:"void"},"lines.account_code":"6-8000",source_label:{$regex:${JSON.stringify(k.number)}}},{_id:0}).toArray()`);
          assert(je.length === 1, `jurnal biaya bank ${je.length}`);
          cekJurnalSeimbang(je[0], [["6-8000", "D", BIAYA_BANK], ["1-1200", "K", BIAYA_BANK]]);
          assert(sisaSo(ctx.so2.so_id) <= 0.01, `SO-2 sisa ${sisaSo(ctx.so2.so_id)}`);
          ctx.E.jeBank = je[0];
          await bk.potret(r, "e-kasus-selesai", [r.tid("case-detail-status")]);
          return `${k.number} ${k.status} · ${teksJe(je[0])}`;
        });

      await step(32, "Finance", `Penagihan & Penerimaan → SO-3 → ikon dompet → alokasi = total − ${rp(BIAYA_KECIL)} → [Simpan kwitansi] → [Ya, simpan]`,
        `Petunjuk 'masih dalam toleransi' — tanpa jendela keputusan; SO-3 lunas. Buku: Bank (D) = Piutang (K) = uang masuk; Beban Selisih Pembayaran 6-9100 (D) = Piutang (K) = ${rp(BIAYA_KECIL)}`, async () => {
          await masuk(r, finAkun);
          ctx.E.masuk3 = r2(ctx.so3.total - BIAYA_KECIL);
          await bukaFormBayar(r, ctx.so3.so_id, "e-kecil");
          await r.tid(`ar-receipt-alloc-${ctx.so3.so_id}`).fill(String(ctx.E.masuk3));
          await r.tid("ar-receipt-reference").fill(`TRF-S3E2-LATIH${NO}`);
          await r.idle(1800);
          const hint = await r.text("ar-receipt-variance-hint");
          await bk.potret(r, "e-form-kecil", [r.tid(`ar-receipt-alloc-${ctx.so3.so_id}`), r.tid("ar-receipt-variance-hint")]);
          const note = await simpanKwitansi(r, "e-kecil");
          const rc = mongo(`return db.ar_receipts.findOne({reference_no:"TRF-S3E2-LATIH${NO}",status:{$ne:"void"}},{_id:0})`);
          assert(rc && dekat(rc.amount, ctx.E.masuk3), "kwitansi E2");
          const je = jurnalKas(rc.cash_txn_id)[0];
          cekJurnalSeimbang(je, [["1-1100", "D", ctx.E.masuk3], ["1-1200", "K", ctx.E.masuk3]]);
          await sleep(1500);
          const wo = mongo(`return db.journal_entries.find({status:{$ne:"void"},source_type:"payment_variance_writeoff",source_label:{$regex:${JSON.stringify(rc.number)}}},{_id:0}).toArray()`);
          const wo2 = wo.length ? wo : mongo(`const d=db.payment_variance_decisions.find({receipt_id:"${rc.id}"},{_id:0,id:1}).toArray().map(x=>x.id);
            return db.journal_entries.find({status:{$ne:"void"},source_id:{$in:d}},{_id:0}).toArray()`);
          assert(wo2.length === 1, `jurnal pembulatan ${wo2.length}`);
          cekJurnalSeimbang(wo2[0], [["6-9100", "D", BIAYA_KECIL], ["1-1200", "K", BIAYA_KECIL]]);
          assert(sisaSo(ctx.so3.so_id) <= 0.01, `SO-3 sisa ${sisaSo(ctx.so3.so_id)}`);
          ctx.E.jeKecil = je; ctx.E.jeWo = wo2[0];
          return `${hint.slice(0, 140)} · ${note.slice(0, 160)} · ${teksJe(je)} · ${teksJe(wo2[0])}`;
        });
    }

    // ══ F. CEK BUKU AKHIR ══════════════════════════════════════════════════════════════════════════════════════════
    if (ada("F")) {
      await step(33, "Finance", "Cek buku akhir: piutang tiap SO = 0, uang muka & titipan pelanggan = 0, jurnal seimbang, PPN keluaran = faktur; Saldo & Umur pelanggan tanpa tagihan",
        "Semua SO situasi lunas (SO batal: terbayar 0); 2-1400 pelanggan net 0; layar Saldo & Umur tidak menampilkan piutang pelanggan", async () => {
          const out = [];
          const ids = [ctx.A && ctx.A.so.id, ctx.B && ctx.B.so.id, ctx.so1 && ada("D") && ctx.so1.so_id,
            ctx.so2 && ada("E") && ctx.so2.so_id, ctx.so3 && ada("E") && ctx.so3.so_id].filter(Boolean);
          for (const id of ids) {
            const o = soDoc(id);
            assert(sisaSo(id) <= 0.01 && o.payment_status === "paid", `${o.number} sisa ${sisaSo(id)} (${o.payment_status})`);
            const je = [...jurnalSo(id), ...kwitansiSo(id).flatMap((rc) => jurnalKas(rc.cash_txn_id))];
            for (const j of je) cekJurnalSeimbang(j, []);
            out.push(`${o.number} lunas`);
          }
          if (ctx.C) {
            const o = soDoc(ctx.C.so.id);
            assert(o.status === "cancelled" && dekat(r2((o.payments || []).reduce((s, p) => s + Number(p.amount || 0), 0)), 0), "SO batal");
            out.push(`${o.number} batal · terbayar 0`);
          }
          assert(dekat(titipanPelanggan(ctx.cust.id), ctx.titipAwal), `titipan ${titipanPelanggan(ctx.cust.id)}`);
          // 2-1400 seluruh jurnal yang menyebut pelanggan ini (kwitansi, reklas, kasus) — harus net 0.
          const rcIds = mongo(`return db.ar_receipts.find({customer_id:"${ctx.cust.id}",status:{$ne:"void"}},{_id:0,cash_txn_id:1}).toArray().map(x=>x.cash_txn_id)`);
          const kasusIds = mongo(`return db.finance_cases.find({customer_id:"${ctx.cust.id}"},{_id:0,id:1}).toArray().map(x=>x.id)`);
          const kasKasus = mongo(`return db.cash_transactions.find({ref_id:{$in:${JSON.stringify(kasusIds)}}},{_id:0,id:1}).toArray().map(x=>x.id)`);
          const soIds = mongo(`return db.sales_orders.find({customer_id:"${ctx.cust.id}"},{_id:0,id:1}).toArray().map(x=>x.id)`);
          const je14 = mongo(`return db.journal_entries.find({status:{$ne:"void"},"lines.account_code":"2-1400",$or:[{source_id:{$in:${JSON.stringify([...rcIds, ...kasKasus].filter(Boolean))}}},{"ref.order_id":{$in:${JSON.stringify(soIds)}}}]},{_id:0,number:1,lines:1}).toArray()`);
          const s14 = saldo(je14, "2-1400");
          assert(dekat(s14, 0), `2-1400 pelanggan ${s14}`);
          out.push(`2-1400 pelanggan ${rp(s14)} (${je14.length} jurnal)`);
          if (ctx.A && ctx.A.fkt) out.push(`PPN faktur ${rp(ctx.A.fkt.ppn_amount)} = PPN keluaran 2 SJ`);
          await masuk(r, finAkun);
          await bukaMenu(r, "ar-aging", "ar-aging");
          await r.tid("ar-aging-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
          await r.idle(1500);
          const ag = await (await api(finAkun)).get(`/ar/aging/${ctx.cust.id}`, KSC);
          const items = (ag.items || ag.orders || []).filter((x) => Number(x.outstanding || x.sisa || 0) > 0.01);
          assert(!items.length, `umur piutang pelanggan masih ${items.length} pesanan: ${JSON.stringify(items).slice(0, 200)}`);
          const sisaBaris = await r.tid(`ar-aging-row-${ctx.cust.id}`).count();
          out.push(sisaBaris ? `baris umur: ${await isiLayar(r.tid(`ar-aging-row-${ctx.cust.id}`))}` : "pelanggan tidak lagi tampil di Saldo & Umur");
          await r.shot("f-umur-akhir");
          r.note(`RINGKAS S3 peserta ${NO}: ${out.join(" · ")}`);
          return out.join(" · ");
        });
    }
  } catch (e) {
    r.note("berhenti: " + (e && e.message ? e.message : e));
  }
  if (http4xx.length) r.note(`respons 4xx di layar: ${[...new Set(http4xx)].join(" · ")}`);
  await r.finish();
})();
