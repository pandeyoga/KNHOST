// A1 · PESANAN SAMPAI UANG MASUK (order to cash) — PT Sukacita, dijalankan LEWAT LAYAR oleh setiap peran.
//
//   Sales (POS) → cek kredit (dalam plafon · lewat plafon → izin kredit Manajer) → Admin Sales (periksa & lepas) →
//   Gudang (pindai roll, kemas, kirim; Final Loading Check tanpa RFID = pengecualian Manajer) → Admin Sales (diterima) →
//   Finance (piutang, faktur pajak keluaran, terima transfer, rekonsiliasi bank, jejak dokumen).
//   Di tiap tahap buku dicek: jurnal seimbang dan angkanya sama dengan dokumen (SO → SJ → faktur → kwitansi → jurnal).
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/e2e/A1_order_to_cash.js            (peserta bawaan 22)
//   KN_PESERTA=23 node docs/pelatihan/2026-11-18_keuangan/uji/e2e/A1_order_to_cash.js
//
// Butuh peserta SEGAR (pelanggan "Latihan NN · Toko Kain Peserta NN" yang belum pernah dipakai A1):
//   cd backend && python scripts/seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN
// Persiapan pelatih (lewat endpoint resmi, bukan bagian latihan): plafon khusus pelanggan dibuat cukup untuk pesanan
// pertama tetapi tidak untuk pesanan kedua (kasus lewat plafon). Hasil: uji/hasil/A1/hasil.json + tangkapan layar.
const path = require("path");
const U = path.join(__dirname, "..");
const { Run, api, assert, sleep, rp, num, peserta, akunPeserta, mongo } = require(path.join(U, "lib.js"));
const { bersihkanHasil, sorot, lepas, klikSorot, bukaMenu, bukaPenagihan, barisSo, sisaSo, kwitansiTerakhir,
  jurnalKwitansi, cekJurnalSeimbang } = require(path.join(U, "piutang_lib.js"));
const kb = require(path.join(U, "kasbank_lib.js"));
const { tungguTeks, tungguToast, toastLoc } = require(path.join(U, "hutang_lib.js"));
const bk = require(path.join(U, "buku_lib.js"));

const NO = peserta("22");
const KSC = "ent_ksc";
const PELANGGAN = `Latihan ${NO} · Toko Kain Peserta ${NO}`;
const ALASAN_PLAFON = `Plafon latihan alur A1 (pesanan sampai uang masuk) — Latihan ${NO}`;
const PRODUK_PILIHAN = ["DENIM TENCEL HITAM A", "DENIM TENCEL BLUE BLACK GARMENT A", "CLOVERTEA CREPE A"];

const r2 = (n) => Math.round(Number(n || 0) * 100) / 100;
const dekat = (a, b, tol = 0.01) => Math.abs(Number(a) - Number(b)) <= tol;
const rupiahLayar = (n) => rp(n).replace("Rp ", "");   // angka layar "2.615.160" (tanpa "Rp", spasi bisa NBSP)
const isiLayar = async (loc) => (await loc.first().innerText()).replace(/\s+/g, " ").trim();

/** Produk woven Jakarta yang punya harga PT dan ≥ 3 roll bebas (roll utuh, grade A). */
function pilihProduk() {
  for (const nama of PRODUK_PILIHAN) {
    const p = mongo(`const p=db.products.findOne({name:${JSON.stringify(nama)}},{_id:0,id:1,name:1,sku:1,base_unit:1});
      if(!p) return null;
      const ep=db.entity_prices.findOne({entity_id:"${KSC}",product_id:p.id},{_id:0});
      const n=db.inventory_rolls.countDocuments({product_id:p.id,owner_entity_id:"${KSC}",warehouse_id:"wh_jakarta",
        status:"available",grade:"A",reserved_ref:null});
      return ep && n>=3 ? {...p, harga:(ep.price||ep.sell_price||0), roll_bebas:n} : null`);
    if (p) return p;
  }
  throw new Error("Tidak ada produk latihan dengan stok roll bebas di Jakarta");
}

function soDoc(id) { return mongo(`return db.sales_orders.findOne({id:"${id}"},{_id:0})`); }
function soByNumber(no) { return mongo(`return db.sales_orders.findOne({number:${JSON.stringify(no)},entity_id:"${KSC}"},{_id:0})`); }
function jurnalSo(so) {
  // Jurnal yang lahir dari SO / surat jalannya (pendapatan & HPP), tidak termasuk kwitansi.
  return mongo(`const sids=db.shipments.find({order_id:"${so.id}"},{_id:0,id:1}).toArray().map(x=>x.id);
    return db.journal_entries.find({status:{$ne:"void"},$or:[{source_id:"${so.id}"},{source_id:{$in:sids}}]},
      {_id:0,id:1,number:1,source_type:1,source_id:1,description:1,lines:1}).sort({created_at:1}).toArray()`);
}
const teksJe = (je) => `${je.number} ${je.lines.map((l) => `${l.account_code} ${Number(l.debit) ? "D" : "K"} ${rp(Number(l.debit) || Number(l.credit))}`).join(" · ")}`;

/** Masuk lewat layar login; server yang sibuk (beberapa agen/peserta bersamaan) kadang butuh > 20 detik untuk login
 *  pertama — dicoba sekali lagi sebelum langkah dinyatakan gagal. */
async function masuk(r, akun) {
  try { await r.login(akun); } catch (e) {
    r.note(`login ${akun} lambat (${String(e.message || e).split("\n")[0].slice(0, 80)}) — diulang`);
    await r.login(akun);
  }
}

/** Jendela kedua (peran lain) TANPA menutup layar peran pertama — mis. Manajer menyetujui izin kredit sementara keranjang
 *  Sales tetap terbuka. Tangkapan layar & galat 5xx tetap masuk Run yang sama. */
async function jendelaLain(r, akun, fn) {
  const asal = { page: r.page, ctx: r.ctx, who: r.who };
  const ctx = await r.browser.newContext({ viewport: { width: 1366, height: 900 }, locale: "id-ID", timezoneId: "Asia/Jakarta" });
  const page = await ctx.newPage();
  page.setDefaultTimeout(15000);
  page.on("response", (res) => {
    const u = res.url();
    if (u.includes("/api/") && res.status() >= 500) r.httpErr.push(`${res.status()} ${res.request().method()} ${u.replace(/^.*\/api/, "/api")}`);
  });
  page.on("pageerror", (e) => r.consoleErr.push(String(e.message || e).slice(0, 300)));
  r.page = page; r.ctx = ctx;
  try {
    await masuk(r, akun);
    return await fn();
  } catch (e) {
    try { await r.shot(`GAGAL-jendela-${akun.split("@")[0]}`); } catch (_) { /* jendela sudah tertutup */ }
    throw e;
  } finally {
    r.page = asal.page; r.ctx = asal.ctx; r.who = asal.who;
    await ctx.close().catch(() => {});
  }
}

/** Pilih opsi KNSelect berdasarkan teks (pilihan bisa dicari dengan mengetik). */
async function pilihTeks(r, testId, re, ketik = "") {
  await r.tid(testId).click();
  await sleep(300);
  if (ketik) { await r.page.keyboard.type(ketik); await sleep(1200); }
  const opt = r.page.getByRole("option", { name: re }).first();
  await opt.waitFor({ timeout: 10000 });
  await opt.click();
  await sleep(300);
}

/** POS: lokasi Jakarta + pelanggan peserta → katalog (gerbang POS muncul bila belum dipilih). */
async function mulaiPos(r, nama = "") {
  await bukaMenu(r, "sales", "", { grup: "penjualan", nama });
  if (await r.tid("pos-gate").isVisible().catch(() => false)) {
    await pilihTeks(r, "pos-gate-site", /^Jakarta/);
    await pilihTeks(r, "pos-gate-customer", new RegExp(PELANGGAN), `Latihan ${NO} · Toko Kain Peserta`);
    if (nama) await bk.potret(r, `${nama}-gerbang`, [r.tid("pos-gate-site"), r.tid("pos-gate-customer"), r.tid("pos-gate-start")]);
    await r.tid("pos-gate-start").click();
    await r.idle(800);
  }
  await r.tid("pos-customer-bar").waitFor();
  const cust = await isiLayar(r.tid("pos-customer-select"));
  assert(cust.includes(`Latihan ${NO}`), `pelanggan POS: ${cust}`);
}

/** Katalog → produk → [Beli per Roll] → centang `n` roll pertama (FEFO) → [Tambah ke Keranjang]. → { count, subtotal } */
async function tambahRoll(r, prod, n, nama = "") {
  await r.tid("product-search-input").fill(prod.name.replace(/ A$/, ""));
  await r.idle(1200);
  const card = r.tid(`product-image-button-${prod.id}`);
  await card.waitFor({ timeout: 20000 });
  if (nama) { await card.scrollIntoViewIfNeeded(); await bk.potret(r, `${nama}-katalog`, [r.tid("product-search-input"), r.tid(`product-card-${prod.id}`)]); }
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
    await bk.potret(r, `${nama}-pilih-roll`, [r.tid("quickview-mode-roll"), toggles.first(), r.tid("roll-picker-confirm")]);
  }
  await r.tid("roll-picker-confirm").click();
  await r.idle(800);
  if (await r.tid("quickview-close").isVisible().catch(() => false)) await r.tid("quickview-close").click();
  return { count, subtotal };
}

/** Keranjang → Checkout langkah 1 & 2 (termin NET 30, cara bayar Transfer bank) → langkah 3 Review. */
async function checkoutSampaiReview(r, nama = "") {
  await r.tid("floating-cart-button").click();
  await r.tid("checkout-step-1").waitFor();
  const sel = await isiLayar(r.tid("checkout-selected-customer"));
  assert(sel.includes(`Latihan ${NO}`), `pelanggan checkout: ${sel}`);
  if (nama) await bk.potret(r, `${nama}-checkout-1`, [r.tid("checkout-address-select"), r.tid("checkout-next")]);
  await r.tid("checkout-next").click();
  await r.tid("checkout-step-2").waitFor();
  const termin = await isiLayar(r.tid("payment-term-select"));
  assert(/NET 30/i.test(termin), `termin bawaan pelanggan: ${termin}`);
  await pilihTeks(r, "payment-method-select", /^Transfer bank/);
  await r.tid("receiving-account-field").waitFor();
  const rek = await kb.tunggu(r, "checkout-payment-destination", /BCA \d+/, 20000);
  assert(/BCA/.test(rek), `rekening tujuan: ${rek}`);
  if (nama) await bk.potret(r, `${nama}-checkout-2`, [r.tid("payment-term-select"), r.tid("payment-method-select"), r.tid("checkout-next")]);
  await r.tid("checkout-next").click();
  await r.tid("checkout-step-3").waitFor();
  await r.tid("credit-gate-box").waitFor({ timeout: 20000 });
  await r.idle(800);
  return { termin, rek };
}

(async () => {
  bersihkanHasil("A1");
  const r = await new Run("A1", "Alur ujung ke ujung: pesanan sampai uang masuk (order to cash)").start();
  // Bahan audit: respons 4xx yang terjadi di layar (sebagian memang diharapkan, mis. Gudang menekan Override → 403).
  const http4xx = [];
  r.page.on("response", (res) => {
    const u = res.url();
    if (u.includes("/api/") && res.status() >= 400 && res.status() < 500) http4xx.push(`${res.status()} ${res.request().method()} ${u.replace(/^.*\/api/, "/api").split("?")[0]} (${r.who})`);
  });
  const finAkun = akunPeserta(NO);
  const ctx = {};      // dokumen yang lahir sepanjang alur (dipakai langkah berikutnya)
  // Langkah berantai: satu langkah gagal = alur berhenti (langkah berikutnya bergantung pada dokumen sebelumnya).
  const step = async (...a) => { if (!(await r.step(...a))) throw new Error(`langkah ${a[0]} gagal — alur dihentikan`); };
  try {
    // ── 0. PERSIAPAN PELATIH (endpoint resmi) ──────────────────────────────────────────────────────────────────────
    await step(0, "Pelatih", "Persiapan: pelanggan latihan segar + plafon khusus (Finance mengajukan, Manajer menyetujui) + produk ber-stok",
      "Plafon khusus berlaku; sisa plafon cukup untuk 1 roll, tidak cukup untuk 2 roll berikutnya", async () => {
        const cust = mongo(`return db.customers.findOne({name:${JSON.stringify(PELANGGAN)}},{_id:0,id:1,name:1})`);
        assert(cust, `Pelanggan ${PELANGGAN} belum ada — jalankan: cd backend && python scripts/seed_pelatihan_keuangan_kn.py --mulai ${NO} --peserta ${NO}`);
        const pernah = mongo(`return db.credit_profile_requests.countDocuments({customer_id:"${cust.id}",reason:${JSON.stringify(ALASAN_PLAFON)}})`);
        // KN_A1_ULANG=1 hanya untuk menyusun uji (pelanggan dipakai ulang, plafon dihitung ulang); kelas = peserta segar.
        assert(!pernah || process.env.KN_A1_ULANG, `Peserta ${NO} sudah pernah dipakai A1 — pakai peserta segar (KN_PESERTA=…, seed dulu)`);
        ctx.cust = cust;
        ctx.prod = pilihProduk();
        const mgr = await api("manager");
        const fin = await api("finance");
        const awal = await mgr.get(`/customers/${cust.id}/credit-status?entity_id=${KSC}&amount=0&term_code=NET30`, KSC);
        ctx.eksposurAwal = Number(awal.gate.exposure.total || 0);
        // Pesanan 1 roll ±Rp 2,7 jt: plafon = (eksposur + 1 roll) / 75 % dibulatkan ke juta → pesanan 1 lolos tanpa
        // peringatan "mendekati plafon"; pesanan kedua 2 roll (±Rp 5,3 jt) melewati plafon.
        const satuRoll = 120 * Number(ctx.prod.harga || 20000) * 1.11;
        ctx.plafon = Math.ceil((ctx.eksposurAwal + satuRoll) / 0.75 / 1e6) * 1e6;
        const prof = await mgr.get(`/customers/${cust.id}/credit-profile?entity_id=${KSC}`, KSC);
        if (Number(prof.effective.credit_limit) === ctx.plafon && prof.effective.limit_mode === "khusus") {
          r.note(`plafon ${rp(ctx.plafon)} sudah berlaku (jalan ulang)`);
          return `plafon ${rp(ctx.plafon)} (sudah ada) · eksposur awal ${rp(ctx.eksposurAwal)} · ${ctx.prod.name}`;
        }
        if (prof.pending_request) {
          await mgr.post(`/credit-profile-requests/${prof.pending_request.id}/cancel`,
            { reason: "Diganti plafon latihan alur A1" }, KSC);
        }
        const rq = await fin.post(`/customers/${cust.id}/credit-profile-requests`, { entity_id: KSC,
          changes: { limit_mode: "khusus", credit_limit: ctx.plafon }, reason: ALASAN_PLAFON }, KSC);
        await mgr.post(`/credit-profile-requests/${rq.id}/decision`, { decision: "approve", note: "Plafon latihan A1 disetujui" }, KSC);
        const cek = await mgr.get(`/customers/${cust.id}/credit-status?entity_id=${KSC}&amount=0&term_code=NET30`, KSC);
        assert(Number(cek.gate.limit.credit_limit) === ctx.plafon, `plafon berlaku ${cek.gate.limit.credit_limit}`);
        r.note(`Peserta ${NO} · ${PELANGGAN} · plafon ${rp(ctx.plafon)} · eksposur awal ${rp(ctx.eksposurAwal)} · produk ${ctx.prod.name} (${ctx.prod.sku}) ${rp(ctx.prod.harga)}/${ctx.prod.base_unit} · ${ctx.prod.roll_bebas} roll bebas`);
        return `plafon ${rp(ctx.plafon)} · eksposur awal ${rp(ctx.eksposurAwal)} · ${ctx.prod.name}`;
      });

    // ── 1. SALES: pesanan penjualan lewat POS ─────────────────────────────────────────────────────────────────────
    await step(1, "Sales", "Masuk sebagai Sales → Penjualan › POS → pilih Lokasi gudang Jakarta & pelanggan latihan → [Buka katalog]",
      "Bilah pelanggan: nama pelanggan, 'Plafon Rp … · terpakai Rp … · sisa Rp …', lokasi Jakarta", async () => {
        await masuk(r, "sales");
        await mulaiPos(r, "pos");
        const chip = await isiLayar(r.tid("pos-credit-chip"));
        assert(chip.includes(rupiahLayar(ctx.plafon)), `chip plafon: ${chip}`);
        await bk.potret(r, "pos-pelanggan", [r.tid("pos-customer-select"), r.tid("pos-credit-chip")]);
        return chip;
      });

    await step(2, "Sales", `Cari produk → buka kartunya → [Beli per Roll] → centang 1 roll teratas (FEFO) → [Tambah ke Keranjang]`,
      "Pemilih roll: 1 roll · panjang roll · subtotal = panjang × harga", async () => {
        const t = await tambahRoll(r, ctx.prod, 1, "so1");
        ctx.subtotal1 = t.subtotal;
        return `1 roll · subtotal ${rp(t.subtotal)}`;
      });

    await step(3, "Sales", "Buka keranjang → Checkout: periksa pelanggan & alamat → [Lanjut]; termin 'Kredit NET 30 Hari', *Cara bayar* Transfer bank → [Lanjut]",
      "Termin bawaan pelanggan NET 30; rekening tujuan BCA terkunci (satu-satunya rekening penerimaan PT)", async () => {
        const c = await checkoutSampaiReview(r, "so1");
        return `${c.termin} · ${c.rek}`;
      });

    await step(4, "Sales", "Review: nyalakan [Minta Faktur Pajak]; baca Ringkasan (DPP, PPN 12% DPP 11/12, Grand total) dan kotak kredit",
      "Kotak kredit 'Kredit Aman': Eksposur = piutang terkirim + pesanan ini, Plafon, Sisa plafon > 0", async () => {
        await r.tid("checkout-tax-invoice-toggle").click();
        await sleep(400);
        const box = await isiLayar(r.tid("credit-gate-box"));
        assert(/Kredit Aman/.test(await r.text("credit-gate-box-result")), `hasil kredit: ${box}`);
        const grand = num(await r.text("cart-grand-total"));
        ctx.grandLayar1 = grand;
        const ini = num(await r.text("credit-gate-box-this"));
        const total = num(await r.text("credit-gate-box-total"));
        const sisa = num(await r.text("credit-gate-box-available"));
        assert(Math.abs(ini - grand) <= 1, `pesanan ini ${ini} ≠ grand total ${grand}`);
        assert(Math.abs(total - (ctx.eksposurAwal + grand)) <= 1, `eksposur ${total} ≠ ${ctx.eksposurAwal} + ${grand}`);
        assert(Math.abs(sisa - (ctx.plafon - total)) <= 1, `sisa plafon ${sisa}`);
        await r.tid("credit-gate-box").scrollIntoViewIfNeeded();
        await bk.potret(r, "so1-review-kredit", [r.tid("checkout-tax-invoice-toggle"), r.tid("credit-gate-box"), r.tid("cart-grand-total")]);
        return `grand ${rp(grand)} · eksposur ${rp(total)} · plafon ${rp(ctx.plafon)} · sisa ${rp(sisa)}`;
      });

    await step(5, "Sales", "Klik [Buat Sales Order]",
      "Pesan 'KSC/SO-… dibuat (Dipesan · Siap disahkan) · PPN … Grand total Rp …'; layar pindah ke daftar Pesanan. Buku: belum ada jurnal (stok baru dicadangkan)", async () => {
        await klikSorot(r, r.tid("checkout-submit"), "so1-buat");
        const msg = await tungguTeks(r, "system-notice-text", /KSC\/SO-\d+ dibuat/, 30000);
        const no = msg.match(/KSC\/SO-\d+/)[0];
        const so = soByNumber(no);
        assert(so, `SO ${no} tidak ada di DB`);
        ctx.so1 = so;
        assert(so.status === "reserved", `status SO ${so.status}`);
        assert(so.payment_term_code === "NET30" && so.needs_tax_invoice === true && so.payment_method_code === "transfer",
          `termin ${so.payment_term_code} · faktur ${so.needs_tax_invoice} · cara bayar ${so.payment_method_code}`);
        assert(Math.abs(so.grand_total - ctx.grandLayar1) <= 1, `grand SO ${so.grand_total} ≠ layar ${ctx.grandLayar1}`);
        assert(dekat(so.ppn_amount, r2(so.net_subtotal * 0.11)), `PPN ${so.ppn_amount} ≠ 11% × ${so.net_subtotal}`);
        assert(dekat(so.grand_total, so.net_subtotal + so.ppn_amount), "grand ≠ DPP + PPN");
        ctx.roll1 = so.allocations[0].rolls[0];
        const je = jurnalSo(so);
        assert(je.length === 0, `SO baru sudah punya ${je.length} jurnal`);
        await sorot(r.tid("system-notice-text"));
        await r.shot("so1-dibuat");
        await lepas(r.tid("system-notice-text"));
        r.note(`SO1 ${no}: ${so.items[0].quantity} ${so.items[0].unit} × ${rp(so.items[0].price)} = DPP ${rp(so.net_subtotal)} · PPN ${rp(so.ppn_amount)} · total ${rp(so.grand_total)} · roll ${ctx.roll1.roll_no}`);
        return `${msg} · roll ${ctx.roll1.roll_no} dicadangkan · jurnal 0`;
      });

    // ── 2. CEK KREDIT — kasus kedua: lewat plafon → izin kredit Manajer ─────────────────────────────────────────────
    await step(6, "Sales", "Kasus kedua: pesanan baru 2 roll untuk pelanggan yang sama → Checkout sampai Review",
      "Kotak kredit 'Kredit Tertahan': 'Eksposur Rp … melewati plafon Rp …'; tombol bawah 'Kredit Tertahan' mati", async () => {
        await mulaiPos(r);
        const t = await tambahRoll(r, ctx.prod, 2, "so2");
        await checkoutSampaiReview(r);
        assert(/Kredit Tertahan/i.test(await r.text("credit-gate-box-result")), "kredit tidak tertahan");
        const why = await r.text("credit-gate-box-reasons");
        assert(/melewati plafon/.test(why), `alasan: ${why}`);
        assert(await r.tid("checkout-submit").isDisabled(), "tombol buat SO tidak mati");
        ctx.grand2 = num(await r.text("cart-grand-total"));
        await r.tid("credit-gate-box").scrollIntoViewIfNeeded();
        await bk.potret(r, "so2-kredit-tertahan", [r.tid("credit-gate-box-reasons"), r.tid("credit-override-open"), r.tid("checkout-submit")]);
        return `2 roll subtotal ${rp(t.subtotal)} · grand ${rp(ctx.grand2)} · ${why}`;
      });

    await step(7, "Sales", "Klik [Ajukan izin kredit (Rp …)] → *Alasan*: Riwayat bayar baik · *Catatan* → [Ajukan izin]",
      "Pesan hijau 'Izin kredit Rp … untuk Latihan NN … diajukan — menunggu keputusan … tekan Periksa ulang kredit lalu Buat Sales Order'", async () => {
        await r.tid("credit-override-open").click();
        await r.tid("credit-override-modal").waitFor();
        const nominal = num(await r.tid("credit-override-amount").inputValue());
        assert(Math.abs(nominal - ctx.grand2) <= 1, `nominal izin ${nominal} ≠ ${ctx.grand2}`);
        await pilihTeks(r, "credit-override-reason-code", /Riwayat bayar baik/);
        await r.tid("credit-override-note").fill(`Latihan ${NO}: pesanan musim ramai, pelanggan selalu bayar tepat waktu`);
        await klikSorot(r, r.tid("credit-override-submit"), "so2-ajukan-izin");
        const msg = await tungguTeks(r, "credit-override-msg", /diajukan/, 20000);
        ctx.izin = mongo(`return db.credit_overrides.find({customer_id:"${ctx.cust.id}",status:"pending"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
        assert(ctx.izin && Math.abs(ctx.izin.amount - ctx.grand2) <= 1, "izin kredit tidak tersimpan");
        await bk.potret(r, "so2-izin-diajukan", [r.tid("credit-override-msg"), r.tid("credit-gate-box-recheck")]);
        return msg;
      });

    await step(8, "Manajer", "(jendela Manajer) Keuangan › Piutang › Kredit & Plafon → cari pelanggan → baris 'Izin Kredit Rp …' → [Setujui] → isi catatan → [Setujui]",
      "Pesan 'Izin kredit Latihan NN · … disetujui.'; baris hilang dari antrean Menunggu keputusan", async () =>
        jendelaLain(r, "manager", async () => {
          await bukaMenu(r, "ar-aging", "credit-overrides", { nama: "mgr-kredit" });
          await r.tid("credit-desk-search").fill(PELANGGAN);
          const row = r.tid(`credit-desk-row-${ctx.izin.id}`);
          await row.waitFor({ timeout: 45000 });
          const t = await isiLayar(row);
          assert(t.includes(rupiahLayar(ctx.izin.amount)) && /Izin Kredit/.test(t), `baris izin: ${t}`);
          await sorot(row);
          await klikSorot(r, r.tid(`credit-desk-approve-${ctx.izin.id}`), "mgr-izin-setujui");
          await lepas(row);
          await r.tid("credit-desk-decision").waitFor();
          await r.tid("credit-desk-decision-reason").fill("Disetujui: riwayat bayar baik, nilai di bawah wewenang manajer");
          await klikSorot(r, r.tid("credit-desk-decision-confirm"), "mgr-izin-konfirmasi");
          const n = await tungguTeks(r, "credit-desk-notice", /disetujui/, 20000);
          const iz = mongo(`return db.credit_overrides.findOne({id:"${ctx.izin.id}"},{_id:0,status:1,decided_by:1})`);
          assert(iz.status === "approved", `status izin ${iz.status}`);
          await bk.potret(r, "mgr-izin-disetujui", [r.tid("credit-desk-notice")]);
          return `${n} · oleh ${iz.decided_by}`;
        }));

    await step(9, "Sales", "Kembali ke layar Sales (keranjang masih terbuka) → [Periksa ulang kredit] → [Buat Sales Order]",
      "Kotak kredit 'Kredit Aman' + 'Izin kredit disetujui dipakai pesanan ini'; SO kedua dibuat dan mencatat izin yang dipakai", async () => {
        await klikSorot(r, r.tid("credit-gate-box-recheck"), "so2-periksa-ulang");
        await kb.tunggu(r, "credit-gate-box-result", /Kredit Aman/, 20000);
        const lift = await r.text("credit-gate-box-override");
        assert(/Izin kredit disetujui dipakai/.test(lift), `izin: ${lift}`);
        assert(!(await r.tid("checkout-submit").isDisabled()), "tombol buat SO masih mati");
        await r.tid("credit-gate-box").scrollIntoViewIfNeeded();
        await bk.potret(r, "so2-izin-dipakai", [r.tid("credit-gate-box-override"), r.tid("checkout-submit")]);
        await r.tid("checkout-submit").click();
        if (await r.tid("mixed-lot-modal").isVisible({ timeout: 3000 }).catch(() => false)) {
          await klikSorot(r, r.tid("mixed-lot-confirm"), "so2-lot-campur");
        }
        const msg = await tungguTeks(r, "system-notice-text", /KSC\/SO-\d+ dibuat/, 30000);
        await bk.potret(r, "so2-dibuat", [r.tid("system-notice-text")]);
        const so2 = soByNumber(msg.match(/KSC\/SO-\d+/)[0]);
        assert(so2 && so2.credit_override_id === ctx.izin.id, `SO2 tidak memakai izin ${ctx.izin.id}: ${so2 && so2.credit_override_id}`);
        ctx.so2 = so2;
        const iz = mongo(`return db.credit_overrides.findOne({id:"${ctx.izin.id}"},{_id:0,remaining_amount:1,status:1,used_by_orders:1})`);
        r.note(`SO2 ${so2.number} (lewat plafon) memakai izin kredit ${ctx.izin.id} · sisa izin ${rp(iz.remaining_amount)}`);
        return `${msg} · izin dipakai, sisa ${rp(iz.remaining_amount)}`;
      });

    // ── 3. ADMIN SALES: periksa & lepas ke gudang ──────────────────────────────────────────────────────────────────
    await step(10, "Admin Sales", "Masuk sebagai Admin Sales → Meja Admin Sales → Pelacak SO aktif: cari nomor SO pertama → [Periksa & lepas]",
      "Jendela 'Periksa & lepas ke gudang · KSC/SO-…': data pesanan (kiri) + daftar periksa (kanan); catatan kuning NPWP (tidak menghalangi)", async () => {
        await masuk(r, "salesadmin");
        await r.tid("sales-admin-desk").waitFor();
        await r.tid("desk-tabs-pantau").click();   // meja gelombang 1 — Pelacak SO di tab Pantau
        await r.tid("desk-so-tracker-search").fill(ctx.so1.number);
        await r.idle(600);
        const row = r.tid(`desk-so-tracker-row-${ctx.so1.id}`);
        await row.waitFor({ timeout: 20000 });
        const t = await isiLayar(row);
        assert(/Periksa & lepas/.test(t), `baris pelacak: ${t}`);
        await sorot(row);
        await klikSorot(r, r.tid(`desk-so-tracker-action-${ctx.so1.id}`), "admin-pelacak-so");
        await lepas(row);
        await r.tid("verify-dialog").waitFor();
        await r.tid("verify-checklist").waitFor({ timeout: 20000 });
        const cl = await isiLayar(r.tid("verify-checklist"));
        assert(/Alamat/.test(cl) && /Syarat pembayaran/.test(cl) && /batas kredit/i.test(cl), `daftar periksa: ${cl.slice(0, 200)}`);
        return cl.slice(0, 300);
      });

    await step(11, "Admin Sales", "Isi *Catatan pemeriksaan* → klik [Periksa & lepas ke gudang]",
      "Pesan 'KSC/SO-… diperiksa & dilepas ke gudang — tugas ambil sudah lahir.'; Pelacak SO kini 'Dikonfirmasi' dan menunggu Gudang", async () => {
        await r.tid("verify-note").fill("Alamat & termin dicek; pelanggan minta faktur pajak");
        await klikSorot(r, r.tid("verify-submit"), "admin-periksa-lepas");
        const msg = await tungguToast(r, /dilepas ke gudang/, 20000);
        const so = soDoc(ctx.so1.id);
        assert(so.status === "confirmed", `status SO ${so.status}`);
        const task = mongo(`return db.wms_tasks.findOne({order_id:"${ctx.so1.id}",flow_type:"outbound"},{_id:0,id:1,status:1,quantity:1})`);
        assert(task, "tugas ambil gudang tidak lahir");
        ctx.task = task;
        // Pelacak ikut dimuat ulang (perbaikan uji A1): baris tidak lagi menawarkan [Periksa & lepas].
        await kb.tunggu(r, `desk-so-tracker-row-${ctx.so1.id}`, /Gudang/, 20000);
        const row = await isiLayar(r.tid(`desk-so-tracker-row-${ctx.so1.id}`));
        assert(!/Periksa & lepas$/.test(row), `pelacak masih basi: ${row}`);
        // … dan Keep & Pending ikut dimuat ulang: SO yang sudah diperiksa keluar dari "Keep".
        await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="kp-keep-row-${id}"]`), ctx.so1.id, { timeout: 20000 });
        await bk.potret(r, "admin-dilepas", [toastLoc(r, /dilepas ke gudang/), r.tid(`desk-so-tracker-row-${ctx.so1.id}`)]);
        return `${msg} · pelacak: ${row.slice(0, 160)}`;
      });

    // ── 4. GUDANG: ambil (pindai roll), kemas, kirim ──────────────────────────────────────────────────────────────
    const bukaTugas = async (nama = "") => {
      await bukaMenu(r, "wms-operations", "wms-outbound", { grup: "gudang", nama });
      await r.tid("outbound-scan-panel").waitFor();
      await r.page.locator('[data-testid="outbound-filters"] input').first().fill(ctx.so1.number.replace("KSC/", ""));
      await r.idle(600);
      const t = r.tid(`outbound-task-${ctx.task.id}`);
      await t.waitFor({ timeout: 20000 });
      if (nama) await bk.potret(r, `${nama}-tugas`, [t]);
      await t.click();
      await r.tid("outbound-task-panel").waitFor();
      await r.idle(800);
    };

    await step(12, "Gudang", "Masuk sebagai Gudang (Jakarta) → Gudang & Logistik › Operasi Gudang › tab Barang Keluar → cari nomor SO → klik tugasnya",
      "Panel 'Ambil & Kirim · Siap diambil': SO, gudang Jakarta, progres 0/…; 'Roll yang harus diambil' menyebut nomor roll yang dicadangkan", async () => {
        await masuk(r, "warehouse");
        await bukaTugas("gudang");
        const t = await isiLayar(r.tid("outbound-task-panel"));
        assert(t.includes(ctx.so1.number) && t.includes(ctx.roll1.roll_no), `panel: ${t.slice(0, 250)}`);
        return t.slice(0, 260);
      });

    await step(13, "Gudang", "Ketik nomor roll di kotak *Kode roll (scan / ketik lalu Enter)* → Enter → klik [Kirim Pengambilan]",
      "Kotak hijau 'Roll RL-… · panjang · Lot · Bin' lalu notifikasi 'Pengambilan tercatat · Terkumpul … dari …'; status tugas 'Pengemasan' (siap kirim), progres 100%", async () => {
        await r.tid("outbound-roll-code").fill(ctx.roll1.roll_no);
        await r.page.keyboard.press("Enter");
        await r.tid("outbound-roll-info").waitFor({ timeout: 15000 });
        const info = await r.text("outbound-roll-info");
        assert(info.includes(ctx.roll1.roll_no), `info roll: ${info}`);
        await bk.potret(r, "gudang-pindai-roll", [r.tid("outbound-roll-code"), r.tid("outbound-roll-info"), r.tid(`scan-task-${ctx.task.id}`)]);
        await r.tid(`scan-task-${ctx.task.id}`).click();
        await r.page.getByText("Pengambilan tercatat").first().waitFor({ timeout: 20000 });
        await r.idle(1500);
        const tk = mongo(`return db.wms_tasks.findOne({id:"${ctx.task.id}"},{_id:0,status:1,picked_qty:1,quantity:1})`);
        assert(tk.status === "packing" && dekat(tk.picked_qty, tk.quantity), `tugas ${tk.status} ${tk.picked_qty}/${tk.quantity}`);
        // Perbaikan uji A1: kotak roll tidak muncul lagi sesudah pengambilan (dulu basi karena pencarian onBlur).
        assert(!(await r.tid("outbound-roll-info").isVisible().catch(() => false)), "kotak roll lama masih tampil sesudah pengambilan");
        await bk.potret(r, "gudang-terambil", [r.tid("outbound-task-panel")]);
        return `${info.slice(0, 120)} → status ${tk.status} ${tk.picked_qty}/${tk.quantity}`;
      });

    await step(14, "Gudang", "Coba [Kirim Semua] → [Kirim Sekarang] (roll latihan belum bertag RFID)",
      "Ditolak: '1 roll belum bertag RFID aktif (RL-…) — … jalankan Final Loading Check dengan pengecualian berizin.' Gudang sendiri tidak berwenang [Override]", async () => {
        await r.tid("loading-check-panel").waitFor();
        await klikSorot(r, r.tid(`dispatch-all-${ctx.task.id}`), "gudang-kirim-coba");
        await r.tid("outbound-dispatch-confirm").waitFor();
        await r.tid("outbound-dispatch-confirm-confirm").click();
        const err = await tungguTeks(r, "outbound-scan-error", /RFID|Loading Check/i, 20000);
        await bk.potret(r, "gudang-kirim-ditolak", [r.tid("outbound-scan-error"), r.tid("loading-check-panel")]);
        assert(!mongo(`return db.shipments.countDocuments({order_id:"${ctx.so1.id}"})`), "surat jalan terbit tanpa loading check");
        return err;
      });

    await step(15, "Manajer", "Masuk sebagai Manajer → Operasi Gudang › Barang Keluar → tugas SO → *Pemeriksaan Muat Akhir*: isi alasan → [Override]",
      "Kotak oranye 'OVERRIDE oleh Dewi Manager: … — berlaku untuk 1 roll saat ini.' (tercatat di audit)", async () => {
        await masuk(r, "manager");
        await bukaTugas();
        await r.tid("lc-override-reason").fill("Roll latihan belum bertag RFID, muatan dicek manual oleh supervisor");
        await klikSorot(r, r.tid("lc-override"), "mgr-loading-override");
        const t = await tungguTeks(r, "lc-last-result", /OVERRIDE/, 20000);
        await bk.potret(r, "mgr-override-tercatat", [r.tid("lc-last-result")]);
        return t;
      });

    await step(16, "Gudang", "Masuk lagi sebagai Gudang → tugas SO → [Kirim Semua] → [Kirim Sekarang]",
      "Notifikasi 'Barang terkirim · No. Surat Jalan KSC/SJ-…'; panel 'Terkirim Penuh!' + tombol [Surat Jalan]. Buku: jurnal pendapatan (Piutang D = Pendapatan K + PPN Keluaran K) dan jurnal HPP (HPP D = Persediaan K)", async () => {
        await masuk(r, "warehouse");
        await bukaTugas();
        await r.tid(`dispatch-all-${ctx.task.id}`).click();
        await r.tid("outbound-dispatch-confirm").waitFor();
        await klikSorot(r, r.tid("outbound-dispatch-confirm-confirm"), "gudang-kirim-konfirmasi", { locator: r.tid("outbound-dispatch-confirm") });
        await r.page.getByText("Barang terkirim").first().waitFor({ timeout: 30000 });
        await r.idle(1500);
        const sh = mongo(`return db.shipments.findOne({order_id:"${ctx.so1.id}"},{_id:0})`);
        assert(sh && sh.status === "dispatched", "surat jalan tidak terbit");
        ctx.sj = sh;
        const panel = await isiLayar(r.tid("outbound-task-panel"));
        assert(panel.includes(sh.shipment_no) && /Terkirim Penuh/.test(panel), `panel: ${panel.slice(0, 200)}`);
        await bk.potret(r, "gudang-terkirim", [r.tid(`view-surat-jalan-${ctx.task.id}`)]);
        // Cek buku tahap kirim.
        const so = soDoc(ctx.so1.id);
        ctx.so1 = so;
        const je = jurnalSo(so);
        const rev = je.find((j) => j.source_type === "shipment_revenue");
        const cogs = je.find((j) => j.source_type === "shipment_cogs");
        assert(rev && cogs, `jurnal kirim: ${je.map((j) => j.source_type).join(",")}`);
        cekJurnalSeimbang(rev, [["1-1200", "D", so.grand_total], ["4-1000", "K", so.net_subtotal], ["2-1200", "K", so.ppn_amount]]);
        const hpp = r2(sh.rolls.reduce((s, x) => s + Number(x.extended_cost || 0), 0));
        assert(hpp > 0 && dekat(hpp, r2(sh.rolls[0].unit_cost * sh.rolls[0].length)), `HPP roll ${hpp}`);
        cekJurnalSeimbang(cogs, [["5-1000", "D", hpp], ["1-1300", "K", hpp]]);
        ctx.jeRev = rev; ctx.jeCogs = cogs; ctx.hpp = hpp;
        r.note(`SJ ${sh.shipment_no} · ${teksJe(rev)} | ${teksJe(cogs)} · laba kotor ${rp(so.net_subtotal - hpp)}`);
        return `${sh.shipment_no} · ${teksJe(rev)} · ${teksJe(cogs)}`;
      });

    // ── 5. ADMIN SALES: barang diterima pelanggan ─────────────────────────────────────────────────────────────────
    await step(17, "Admin Sales", "Masuk sebagai Admin Sales → Penjualan › Pesanan → cari nomor SO → [Lihat detail & aksi] → [Tandai Diterima (Selesai)]",
      "Pesan 'Order KSC/SO-… ditandai DITERIMA (Selesai).'; tahap SO 'Selesai'. Buku: tidak ada jurnal baru (piutang sudah lahir saat surat jalan)", async () => {
        await masuk(r, "salesadmin");
        await bukaMenu(r, "sales-orders", "", { grup: "penjualan", nama: "admin-pesanan" });
        await r.tid("orders-search-input").fill(ctx.so1.number);
        await r.idle(1000);
        await r.tid(`order-card-${ctx.so1.id}`).click();
        await r.idle(800);
        await klikSorot(r, r.tid("so-open-full-detail"), "admin-detail-so");
        const b = r.tid(`mark-delivered-button-${ctx.so1.id}`);
        await b.waitFor({ timeout: 20000 });
        const nJe = jurnalSo(ctx.so1).length;
        await klikSorot(r, b, "admin-tandai-diterima");
        const msg = await tungguTeks(r, "system-notice-text", /DITERIMA/, 20000);
        const so = soDoc(ctx.so1.id);
        assert(so.status === "done", `status SO ${so.status}`);
        assert(jurnalSo(so).length === nJe, "tandai diterima membuat jurnal baru");
        return `${msg} · status ${so.status}`;
      });

    // ── 6. FINANCE: piutang, faktur pajak, terima transfer, rekonsiliasi, jejak dokumen ───────────────────────────
    await step(18, "Finance", "Masuk dengan akun Finance peserta → Keuangan › Piutang › Penagihan & Penerimaan → cari baris SO",
      "Baris SO: Belum Lunas = total SO, Jatuh Tempo = tanggal surat jalan + 30 hari ('30h Lagi')", async () => {
        await masuk(r, finAkun);
        await bukaPenagihan(r, "fin-piutang");
        const row = await barisSo(r, ctx.so1.id);
        const t = await isiLayar(row);
        assert(t.includes(ctx.so1.number) && t.includes(rupiahLayar(ctx.so1.grand_total)), `baris piutang: ${t}`);
        assert(/30h Lagi|29h Lagi/.test(t), `jatuh tempo: ${t}`);
        assert(dekat(sisaSo(ctx.so1.id), ctx.so1.grand_total), "sisa tagihan ≠ total SO");
        await bk.potret(r, "fin-baris-piutang", [row]);
        return t;
      });

    await step(19, "Finance", "Keuangan › Beranda Keuangan › Meja Keuangan → kartu [Faktur pajak perlu terbit]: ketik nomor SO → [Terbitkan]",
      "Bilah hijau 'Faktur Pajak KSC/FKT-… diterbitkan untuk KSC/SO-…'. Buku: faktur TIDAK membuat jurnal; PPN faktur = PPN Keluaran di jurnal pengiriman", async () => {
        await bukaMenu(r, "finance-tower", "finance-desk");
        await r.tid("finance-desk").waitFor();
        const kartuFp = r.tid("fin-desk-queue-faktur_pajak");
        await kartuFp.waitFor({ timeout: 20000 });
        await r.tid("fin-desk-search-faktur_pajak").fill(ctx.so1.number);
        const row = r.tid(`fin-desk-faktur_pajak-row-${ctx.so1.id}`);
        await row.waitFor({ timeout: 20000 });
        await sorot(row);
        await klikSorot(r, r.tid(`fin-desk-faktur_pajak-action-${ctx.so1.id}`), "fin-faktur-terbitkan", { locator: kartuFp });
        await r.tid("fkt-modal").waitFor();   // pop-up pratinjau faktur → [Terbitkan]
        await r.tid("fkt-modal-submit").click();
        const msg = await tungguToast(r, /diterbitkan/, 20000);   // hasil = toast
        const fkt = mongo(`return db.tax_invoices.findOne({order_id:"${ctx.so1.id}",status:"normal"},{_id:0})`);
        assert(fkt && msg.includes(fkt.number), `faktur: ${msg}`);
        assert(dekat(fkt.ppn_amount, ctx.so1.ppn_amount), `PPN faktur ${fkt.ppn_amount} ≠ SO ${ctx.so1.ppn_amount}`);
        assert(dekat(fkt.ppn_amount, ctx.jeRev.lines.filter((l) => l.account_code === "2-1200").reduce((s, l) => s + l.credit, 0)),
          "PPN faktur ≠ PPN Keluaran jurnal");
        assert(mongo(`return db.journal_entries.countDocuments({source_id:"${fkt.id}"})`) === 0, "faktur pajak membuat jurnal");
        ctx.fkt = fkt;
        await bk.potret(r, "fin-faktur-terbit", [toastLoc(r, /diterbitkan/)]);
        return `${msg} · DPP nilai lain ${rp(fkt.dpp)} · PPN ${rp(fkt.ppn_amount)} · jurnal faktur 0`;
      });

    await step(20, "Finance", "Keuangan › Piutang › Penagihan & Penerimaan → ikon dompet [Terima pembayaran] pada baris SO → isi *No. referensi* → [Simpan kwitansi] → [Ya, simpan]",
      "Pesan hijau 'Kwitansi KSC/AR-… (Rp …) dicatat untuk Latihan NN …'; baris SO hilang. Buku: Kas Besar / Bank (D) = Piutang Usaha (K) = total SO", async () => {
        await bukaPenagihan(r);
        await barisSo(r, ctx.so1.id);
        await klikSorot(r, r.tid(`collection-pay-${ctx.so1.id}`), "fin-terima-bayar");
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid(`ar-receipt-alloc-${ctx.so1.id}`).waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await r.idle(800);
        const alloc = Number(await r.tid(`ar-receipt-alloc-${ctx.so1.id}`).inputValue());
        assert(dekat(alloc, ctx.so1.grand_total), `alokasi ${alloc}`);
        assert(/BCA Operasional KSC/.test(await r.text("ar-receipt-account-field")), "rekening penerima bukan BCA Operasional KSC");
        await r.tid("ar-receipt-reference").fill(`TRF-A1-LATIH${NO}`);
        await r.idle(600);
        await sorot(r.tid("ar-receipt-reference"));
        await klikSorot(r, r.tid("ar-receipt-submit"), "fin-form-kwitansi");
        await lepas(r.tid("ar-receipt-reference"));
        await r.tid("ar-receipt-confirm").waitFor();
        const konf = await r.text("ar-receipt-confirm-message");
        assert(konf.includes(rp(ctx.so1.grand_total)) && /Sukacita/.test(konf), `konfirmasi: ${konf}`);
        await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), "fin-konfirmasi-kwitansi");
        const note = await tungguTeks(r, "collection-notice", /Kwitansi .*AR-\d+/, 30000);
        await r.idle(800);
        const rc = kwitansiTerakhir(ctx.so1.id);
        assert(rc && dekat(rc.amount, ctx.so1.grand_total), "kwitansi tidak sesuai");
        const je = jurnalKwitansi(rc);
        cekJurnalSeimbang(je, [["1-1100", "D", ctx.so1.grand_total], ["1-1200", "K", ctx.so1.grand_total]]);
        const so = soDoc(ctx.so1.id);
        assert(so.payment_status === "paid" && sisaSo(ctx.so1.id) <= 0.01, `status bayar ${so.payment_status}`);
        ctx.rc = rc; ctx.jeRc = je;
        ctx.kas = mongo(`return db.cash_transactions.findOne({id:"${rc.cash_txn_id}"},{_id:0})`);
        assert(ctx.kas && ctx.kas.account_id, "transaksi kas kwitansi tidak ada");
        await bk.potret(r, "fin-kwitansi-tercatat", [r.tid("collection-notice")]);
        return `${note} · ${teksJe(je)} · kas ${ctx.kas.number}`;
      });

    await step(21, "Finance", "Keuangan › Kas & Bank › Rekonsiliasi → rekening BCA Operasional KSC → [Impor mutasi bank] → tempel baris mutasi transfer pelanggan → [Pratinjau] → [Impor]",
      "Pesan 'Impor BCA — Rekening Koran (CSV): 1 baris baru …'; baris mutasi masuk berstatus belum tercocok", async () => {
        const tgl = kb.hariIni();
        ctx.ketMutasi = `TRSF E-BANKING CR ${ctx.so1.number.replace("KSC/", "")} A1 LATIHAN ${NO} TOKO KAIN PESERTA ${NO}`;
        const teks = ["Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo",
          `${tgl.bca},${ctx.ketMutasi},0000,"${kb.nominalBca(ctx.so1.grand_total)}",CR,0`].join("\n");
        await kb.menu(r, "bank-reconciliation");
        await kb.pilih(r, "recon-account-select", ctx.kas.account_id);
        await r.tid("recon-summary").waitFor();
        await r.tid("recon-import-toggle").click();
        await r.tid("recon-import-panel").waitFor();
        const fmts = await (await api(finAkun)).get("/bank-reconciliation/formats", KSC);
        const fBca = fmts.find((f) => f.bank_code === "bca" && (f.file_kind || "csv") === "csv");
        assert(fBca, "template BCA tidak ada");
        await kb.pilih(r, "recon-format-select", fBca.id);
        await r.tid("recon-raw").fill(teks);
        await r.tid("recon-preview-btn").click();
        const pv = await kb.tunggu(r, "recon-preview", /Terbaca 1 baris/);
        await kb.shotSorot(r, "fin-rekon-pratinjau", r.tid("recon-import-submit"), { locator: r.tid("recon-import-panel") });
        await r.tid("recon-import-submit").click();
        const t = await kb.tunggu(r, "recon-notice", /Impor BCA/);
        assert(/1 baris baru/.test(t), `impor: ${t}`);
        ctx.mutasi = mongo(`return db.bank_statement_lines.findOne({bank_account_id:"${ctx.kas.account_id}",description:${JSON.stringify(ctx.ketMutasi)}},{_id:0})`);
        assert(ctx.mutasi && dekat(ctx.mutasi.amount, ctx.so1.grand_total), "baris mutasi tidak tersimpan");
        return `${pv.split("Tanggal")[0]} · ${t}`;
      });

    await step(22, "Finance", "Cari baris mutasi (ketik 'A1 LATIHAN NN') → [Cocokkan] → pada kandidat transaksi kas kwitansi (nominal sama) klik [Tautkan]",
      "Pop-up 'Cocokkan mutasi bank' berisi kandidat KSC/CASH-… dengan nominal sama; sesudah Tautkan baris 'Tercocok'. Buku: tidak ada jurnal baru, kas kwitansi 'Terekonsiliasi'", async () => {
        const jeSebelum = mongo(`return db.journal_entries.countDocuments({source_id:"${ctx.kas.id}",status:{$ne:"void"}})`);
        await r.tid("recon-lines-search").fill(`A1 LATIHAN ${NO}`);
        await r.idle(500);
        const line = r.tid(`recon-line-${ctx.mutasi.id}`);
        await line.waitFor({ timeout: 20000 });
        const st = mongo(`return db.bank_statement_lines.findOne({id:"${ctx.mutasi.id}"},{_id:0,status:1,allocations:1})`);
        if (st.status !== "matched") {
          await klikSorot(r, r.tid(`recon-matchbtn-${ctx.mutasi.id}`), "fin-rekon-cocokkan", { locator: r.tid("recon-lines-table") });
          await r.tid("recon-match-modal").waitFor();
          const cand = r.tid(`recon-cand-${ctx.kas.id}`);
          await cand.waitFor({ timeout: 20000 });
          const ct = await isiLayar(cand);
          assert(ct.includes(ctx.kas.number) && ct.includes(rupiahLayar(ctx.so1.grand_total)), `kandidat: ${ct}`);
          await kb.shotSorot(r, "fin-rekon-kandidat", r.tid(`recon-pick-cand-${ctx.kas.id}`), { locator: r.tid("recon-match-modal") });
          await r.tid(`recon-pick-cand-${ctx.kas.id}`).click();
          await kb.tunggu(r, "recon-notice", /Mutasi ditautkan/, 20000);
          await r.tid("recon-match-modal").waitFor({ state: "detached" });
        } else {
          r.note("Baris mutasi A1 sudah tercocok otomatis (pengguna lain menekan Cocokkan otomatis) — diterima bila kasnya benar.");
        }
        await r.tid("recon-lines-search").fill(`A1 LATIHAN ${NO}`);
        await kb.tunggu(r, `recon-status-${ctx.mutasi.id}`, /^Tercocok$/, 20000);
        const ln = mongo(`return db.bank_statement_lines.findOne({id:"${ctx.mutasi.id}"},{_id:0,status:1,allocations:1})`);
        assert(ln.status === "matched" && (ln.allocations || []).some((a) => a.txn_id === ctx.kas.id), "mutasi tertaut ke kas lain");
        const kas = kb.kas(ctx.kas.id);
        assert(dekat(kas.reconciled_amount, kas.amount), `kas belum terekonsiliasi penuh: ${kas.reconciled_amount}`);
        const jeSesudah = mongo(`return db.journal_entries.countDocuments({source_id:"${ctx.kas.id}",status:{$ne:"void"}})`);
        assert(jeSesudah === jeSebelum, "pencocokan membuat jurnal baru");
        await kb.shotSorot(r, "fin-rekon-tercocok", r.tid(`recon-line-${ctx.mutasi.id}`), { locator: r.tid("recon-lines-table") });
        return `mutasi ${rp(ctx.mutasi.amount)} ↔ ${kas.number} · terekonsiliasi ${rp(kas.reconciled_amount)} · jurnal tetap ${jeSesudah}`;
      });

    await step(23, "Finance", "Pusat Dokumen › tab Jejak Dokumen → ketik nomor SO → klik hasilnya",
      "Rantai: SO → tugas ambil → surat jalan → jurnal Pendapatan & HPP; SO 'Dilunasi oleh' kwitansi → transaksi kas → jurnal penerimaan", async () => {
        await bk.menu(r, "alat", "document-center", "doc-trace");
        await r.tid("doc-trace-view").waitFor();
        await r.tid("trace-search-input").fill(ctx.so1.number);
        await r.tid(`trace-result-${ctx.so1.id}`).click();
        await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
        await r.tid("trace-graph").waitFor();
        await r.idle(1200);
        const g = await r.text("trace-graph");
        const harus = [ctx.so1.number, ctx.sj.shipment_no, ctx.jeRev.number, ctx.jeCogs.number, ctx.rc.number, ctx.kas.number, ctx.jeRc.number];
        const hilang = harus.filter((x) => !g.includes(x));
        assert(!hilang.length, `jejak tidak memuat: ${hilang.join(", ")}`);
        ctx.fakturDiJejak = g.includes(ctx.fkt.number);
        if (!ctx.fakturDiJejak) r.note(`Jejak Dokumen tidak menampilkan faktur pajak ${ctx.fkt.number} (dicatat di audit A1)`);
        await bk.potret(r, "fin-jejak-dokumen", [r.tid("trace-search-input"), r.tid("trace-anchor-card")], { full: true });
        await r.page.evaluate(() => {
          const el = document.querySelector('[data-testid="trace-graph"]');
          for (const e of [el, ...el.querySelectorAll("*")]) if (e.scrollWidth > e.clientWidth + 10) e.scrollLeft = e.scrollWidth;
        });
        await r.idle(300);
        await r.shot("fin-jejak-dokumen-kanan", { locator: r.tid("trace-graph") });
        return `${harus.join(" → ")}${ctx.fakturDiJejak ? ` · faktur ${ctx.fkt.number}` : " · (faktur tidak tampil)"}`;
      });

    await step(24, "Finance", "Cek buku akhir: semua jurnal SO seimbang; piutang SO kembali nol; nilai SO = SJ = faktur = kwitansi = kas",
      "1-1200 Piutang Usaha: D (pengiriman) − K (kwitansi) = 0; laba kotor = Pendapatan − HPP", async () => {
        const all = [ctx.jeRev, ctx.jeCogs, ctx.jeRc];
        for (const je of all) cekJurnalSeimbang(je, []);
        const piutang = all.flatMap((j) => j.lines).filter((l) => l.account_code === "1-1200")
          .reduce((s, l) => s + Number(l.debit || 0) - Number(l.credit || 0), 0);
        assert(dekat(piutang, 0), `saldo piutang SO ${piutang}`);
        const fkt = mongo(`return db.tax_invoices.findOne({id:"${ctx.fkt.id}"},{_id:0,grand_total:1,total:1,dpp:1,ppn_amount:1})`);
        const nilai = [ctx.so1.grand_total, ctx.rc.amount, ctx.kas.amount, ctx.mutasi.amount];
        assert(nilai.every((v) => dekat(v, ctx.so1.grand_total)), `nilai berbeda: ${nilai.join(" / ")}`);
        const laba = r2(ctx.so1.net_subtotal - ctx.hpp);
        r.note(`RINGKAS A1 ${ctx.so1.number}: DPP ${rp(ctx.so1.net_subtotal)} + PPN ${rp(ctx.so1.ppn_amount)} = ${rp(ctx.so1.grand_total)} · HPP ${rp(ctx.hpp)} · laba kotor ${rp(laba)} · SJ ${ctx.sj.shipment_no} · ${ctx.fkt.number} · ${ctx.rc.number} · ${ctx.kas.number} · SO2 ${ctx.so2 ? ctx.so2.number : "-"}`);
        return `${all.map(teksJe).join(" | ")} · piutang SO ${rp(piutang)} · laba kotor ${rp(laba)} · faktur total ${rp(fkt.grand_total || fkt.total || 0)}`;
      });
  } catch (e) {
    r.note("berhenti: " + (e && e.message ? e.message : e));
  }
  if (http4xx.length) r.note(`respons 4xx di layar: ${[...new Set(http4xx)].join(" · ")}`);
  await r.finish();
})();
