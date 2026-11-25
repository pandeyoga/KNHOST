// S1 · AMANDEMEN & KOREKSI PENJUALAN — PT Sukacita, dijalankan LEWAT LAYAR dengan akun setiap peran, lalu dicocokkan di BUKU.
//
//   A. SO belum terbit (belum dikirim/dibayar): Sales mengajukan koreksi harga → Manajer menyetujui → nilai SO dihitung
//      ulang tanpa jurnal; eksposur kredit ikut turun. Koreksi kedua ditolak → angka tetap, jejak tersimpan. Admin Sales
//      menghapus satu baris lewat Override SO → roll dilepas, nilai SO turun.
//   B. SO belum dikirim yang sudah menerima uang muka: Override terkunci; amandemen tidak bisa menghapus baris.
//   C. SO terkirim + faktur pajak: diskon susulan → Manajer menyetujui → Nota Kredit + jurnal (Pendapatan & PPN Keluaran
//      D / Piutang K) + draf dokumen pajak retur → Finance menerima sisa tagihan.
//   D. SO terkirim + faktur pajak: kenaikan harga kecil → Nota Debit langsung terbit (tagihan tambahan) + jurnal (Piutang D
//      / Pendapatan & PPN Keluaran K) → Finance menerima tagihan + tagihan tambahan.
//   E. Finance: Jejak Dokumen, umur piutang, PPN keluaran.
//
//   KN_PESERTA=65 node docs/pelatihan/2026-11-18_keuangan/uji/situasi/S1_amandemen_penjualan.js
//   Data: cd backend && python scripts/seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN --hanya a_dasar
//   (a_dasar: so_lunas & so_sebagian = SO terkirim belum dibayar). Persiapan lain (dua SO baru + uang muka) dibuat skrip
//   ini lewat endpoint resmi. KN_LANJUT=1 → melanjutkan peserta yang sama (langkah yang sudah lewat dilewati; hanya untuk
//   menyusun skrip — uji resmi selalu pada peserta baru).
const fs = require("fs");
const path = require("path");
const U = path.join(__dirname, "..");
const { Run, api, assert, sleep, rp, num, kartu, peserta, akunPeserta, mongo, BASE } = require(path.join(U, "lib.js"));
const { bersihkanHasil, sorot, lepas, klikSorot, bukaMenu, bukaPenagihan, barisSo, sisaSo, kwitansiTerakhir,
  jurnalKwitansi, cekJurnalSeimbang, pelangganPeserta } = require(path.join(U, "piutang_lib.js"));
const kb = require(path.join(U, "kasbank_lib.js"));
const { tungguTeks } = require(path.join(U, "hutang_lib.js"));
const bk = require(path.join(U, "buku_lib.js"));

const KODE = "S1";
const NO = peserta("65");
const KSC = "ent_ksc";
const LANJUT = process.env.KN_LANJUT === "1";
const PELANGGAN = `Latihan ${NO} · Toko Kain Peserta ${NO}`;
const STATE = path.join(process.env.KN_OUT || path.join(U, "hasil"), "S1_state", `${NO}.json`);

const r2 = (n) => Math.round(Number(n || 0) * 100) / 100;
const dekat = (a, b, tol = 0.01) => Math.abs(Number(a) - Number(b)) <= tol;
const rupiahLayar = (n) => rp(n).replace("Rp ", "");
const isiLayar = async (loc) => (await loc.first().innerText()).replace(/\s+/g, " ").trim();
const harga = (p, f) => Math.round((p * f) / 500) * 500;   // harga baru dibulatkan ke Rp 500

// ── Dokumen & buku (baca langsung dari basis data lokal) ────────────────────────────────────────────────────────────
const soDoc = (id) => mongo(`return db.sales_orders.findOne({id:"${id}"},{_id:0})`);
const amdSo = (id) => mongo(`return db.doc_amendments.find({doc_id:"${id}"},{_id:0,payload:0}).sort({created_at:1}).toArray()`);
const amdById = (id) => mongo(`return db.doc_amendments.findOne({id:"${id}"},{_id:0,payload:0})`);
const notaSo = (id) => mongo(`return db.credit_notes.find({order_id:"${id}"},{_id:0}).sort({created_at:1}).toArray()`);
const fakturSo = (id) => mongo(`return db.tax_invoices.find({order_id:"${id}"},{_id:0}).sort({created_at:1}).toArray()`);
function jurnalSo(id) {
  return mongo(`const sids=db.shipments.find({order_id:"${id}"},{_id:0,id:1}).toArray().map(x=>x.id);
    return db.journal_entries.find({status:{$ne:"void"},$or:[{source_id:"${id}"},{"ref.order_id":"${id}"},{source_id:{$in:sids}}]},
      {_id:0,id:1,number:1,source_type:1,source_id:1,lines:1}).sort({created_at:1}).toArray()`);
}
const jurnalId = (id) => mongo(`return db.journal_entries.findOne({id:"${id}"},{_id:0,id:1,number:1,source_type:1,lines:1,status:1})`);
const teksJe = (je) => `${je.number} ${je.lines.map((l) => `${l.account_code} ${Number(l.debit) ? "D" : "K"} ${rp(Number(l.debit) || Number(l.credit))}`).join(" · ")}`;
/** Saldo 1-1200 (debit − kredit) dari semua jurnal yang menyebut pesanan ini (pengiriman, nota, kwitansi). */
function piutangBukuSo(id, ekstra = []) {
  const ids = JSON.stringify(ekstra);
  return r2(mongo(`const sids=db.shipments.find({order_id:"${id}"},{_id:0,id:1}).toArray().map(x=>x.id);
    let s=0; db.journal_entries.find({status:{$ne:"void"},$or:[{source_id:"${id}"},{"ref.order_id":"${id}"},{source_id:{$in:sids.concat(${ids})}}]}).forEach(j=>{
      for(const l of j.lines){ if(l.account_code==="1-1200") s+= (l.debit||0)-(l.credit||0); } }); return s`));
}
/** Nilai SO dihitung ulang secara independen: DPP = Σ qty × harga × (1 − diskon), PPN = 11% DPP (12% × 11/12). */
function hitungSo(so) {
  const dpp = r2(so.items.reduce((s, i) => s + Number(i.quantity) * Number(i.price) * (1 - Number(i.discount_percent || 0) / 100), 0));
  const ppn = r2(dpp * 0.11);
  return { dpp, ppn, grand: r2(dpp + ppn) };
}
async function eksposur(custId) {
  const m = await api("manager");
  return (await m.get(`/customers/${custId}/credit-status?entity_id=${KSC}&amount=0&term_code=NET30`, KSC)).gate.exposure;
}

// ── Status lanjutan (hanya untuk KN_LANJUT) ─────────────────────────────────────────────────────────────────────────
function bacaState() { try { return JSON.parse(fs.readFileSync(STATE, "utf8")); } catch (_) { return {}; } }
function simpanState(s) {
  fs.mkdirSync(path.dirname(STATE), { recursive: true });
  fs.writeFileSync(path.join(path.dirname(STATE), ".gitignore"), "*\n");   // berkas kerja uji, tidak di-commit
  fs.writeFileSync(STATE, JSON.stringify(s, null, 1));
}

// ── Persiapan: dua SO baru lewat endpoint resmi (Sales), roll utuh FEFO di gudang Jakarta ───────────────────────────
function produkBerstok(n) {
  return mongo(`const rows=db.inventory_rolls.aggregate([{$match:{owner_entity_id:"${KSC}",status:"available",grade:"A",stage:"finished",
      line_code:"woven",reserved_ref:null,length_reserved:{$in:[null,0]},warehouse_id:"wh_jakarta"}},
    {$group:{_id:"$product_id",q:{$sum:"$length_remaining"},n:{$sum:1}}},{$match:{n:{$gte:4}}},{$sort:{q:-1}},{$limit:60}]).toArray();
    const out=[]; for(const r of rows){
      const p=db.products.findOne({id:r._id,import_batch:"MIGRASI_MASTER_PRODUK_KN"},{_id:0,id:1,name:1,base_unit:1});
      const ep=p&&db.entity_prices.findOne({entity_id:"${KSC}",product_id:p.id},{_id:0});
      if(p&&ep){ out.push(p); if(out.length>=${n}) break; } } return out`);
}
async function buatSo(cust) {
  const s = await api("sales");
  const items = produkBerstok(2).map((p) => {
    const rolls = mongo(`return db.inventory_rolls.find({product_id:"${p.id}",owner_entity_id:"${KSC}",status:"available",grade:"A",
      reserved_ref:null,length_reserved:{$in:[null,0]},warehouse_id:"wh_jakarta"},{_id:0,id:1,length_remaining:1}).sort({created_at:1}).limit(1).toArray()`);
    return { product_id: p.id, quantity: r2(rolls.reduce((a, x) => a + x.length_remaining, 0)), unit: p.base_unit,
      purchase_mode: "roll", qty_rolls: rolls.length, roll_lines: rolls.map((x) => ({ roll_id: x.id, take_qty: x.length_remaining })) };
  });
  assert(items.length === 2, "stok roll latihan kurang (butuh 2 produk woven di Jakarta)");
  const tgl = new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10);
  return s.post("/sales-orders", { customer_id: cust.id, shipping_address_id: ((cust.addresses || [])[0] || {}).id || "", items,
    entity_id: KSC, payment_term_code: "NET30", allow_backorder: false, confirm_mixed_lot: true, delivery_date: tgl }, KSC);
}

// ── Layar ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async function masuk(r, akun) {
  try { await r.login(akun); } catch (e) {
    r.note(`login ${akun} lambat (${String(e.message || e).split("\n")[0].slice(0, 80)}) — diulang`);
    await r.login(akun);
  }
}

/** Penjualan › Pesanan → cari nomor SO → klik barisnya → [Lihat detail & aksi]. */
async function bukaSo(r, so, nama = "") {
  await r.page.goto(BASE + "/");
  await r.idle(400);
  await bukaMenu(r, "sales-orders", "", { grup: "penjualan", nama: nama ? `${nama}-pesanan` : "" });
  await r.tid("orders-search-input").fill(so.number);
  await r.idle(1000);
  const row = r.tid(`order-card-${so.id}`);
  await row.waitFor({ timeout: 20000 });
  await row.click();
  await r.idle(600);
  if (nama) await klikSorot(r, r.tid("so-open-full-detail"), `${nama}-buka-detail`);
  else await r.tid("so-open-full-detail").click();
  await r.tid("order-detail-panel").waitFor({ timeout: 20000 });
  await r.tid("amendment-trail-panel").waitFor({ timeout: 20000 });
  // Rincian dimuat bertahap (pengiriman, instruksi bayar, faktur, jejak koreksi) — tunggu semua selesai supaya tombol
  // tidak bergeser saat diklik.
  await r.page.waitForFunction(() => !/Memuat/.test(
    (document.querySelector('[data-testid="order-detail-panel"]') || {}).innerText || "Memuat"), null, { timeout: 30000 });
  await r.idle(1200);
}

/** Klik tombol yang disorot; bila klik pertama tertahan (tombol bergeser/tertutup sesaat saat rincian dimuat ulang),
 *  sebab dari Playwright dicatat lalu dicoba lagi — percobaan terakhir memaksa klik. */
async function klikTahan(r, loc, nama) {
  await sorot(loc);
  await r.shot(nama);
  await lepas(loc);
  for (let coba = 0; coba < 3; coba += 1) {
    try { await loc.click({ timeout: 8000, force: coba === 2 }); return; } catch (e) {
      const sebab = String(e.message || e).split("\n").filter((x) => /intercept|stable|visible|enabled|detached|retrying/i.test(x)).slice(-2).join(" | ");
      r.note(`klik ${nama} tertahan (percobaan ${coba + 1}): ${sebab.slice(0, 240)}`);
      if (coba === 2) throw e;
      await r.idle(1500);
      await loc.scrollIntoViewIfNeeded().catch(() => {});
    }
  }
}

/** Panel Koreksi & Amandemen → [Ajukan Amandemen] → alasan, perubahan baris, penjelasan → tunggu pratinjau dampak. */
async function isiAmandemen(r, opsi) {
  // Server lokal dimuat ulang saat agen lain menyunting kode (--reload): daftar pesanan yang gagal dimuat sesaat
  // menutup rincian SO beserta jendela amandemen yang sedang diisi. Bila itu terjadi, jendela dibuka & diisi lagi.
  for (let coba = 0; ; coba += 1) {
    try { return await isiAmandemenSekali(r, opsi); } catch (e) {
      const terbuka = await r.tid("amd-propose-modal").isVisible().catch(() => false);
      if (terbuka || coba >= 2) throw e;
      r.note(`jendela amandemen tertutup sendiri (percobaan ${coba + 1}: ${String(e.message || e).split("\n")[0].slice(0, 120)}) — dibuka lagi`);
      await r.tid("open-amend-modal-btn").waitFor({ timeout: 30000 });
      await r.idle(1500);
    }
  }
}

async function isiAmandemenSekali(r, { alasan, ubah, catatan, nama }) {
  await r.tid("amendment-trail-panel").scrollIntoViewIfNeeded();
  await klikTahan(r, r.tid("open-amend-modal-btn"), `${nama}-ajukan`);
  await r.tid("amd-propose-modal").waitFor();
  await r.idle(600);
  // Daftar alasan dimuat terpisah sesudah jendela terbuka: buka pilihan, tunggu opsinya, ulang bila masih kosong.
  for (let coba = 0; ; coba += 1) {
    await r.tid("amd-reason-select").click();
    const opt = r.tid(`amd-reason-select-option-${alasan}`);
    try { await opt.waitFor({ state: "visible", timeout: 5000 }); await opt.click(); break; } catch (e) {
      if (coba >= 3) throw new Error(`alasan '${alasan}' tidak bisa dipilih`);
      await r.page.keyboard.press("Escape");
      await r.idle(800);
    }
  }
  await r.idle(300);
  for (const [pid, field, nilai] of ubah) {
    const id = field === "price" ? `amd-item-price-${pid}` : field === "quantity" ? `amd-item-qty-${pid}` : `amd-item-disc-${pid}`;
    await r.tid(id).fill(String(nilai));
    await sleep(200);
  }
  if (catatan) await r.tid("amd-note").fill(catatan);
  await r.idle(1200);
}

async function tungguPratinjau(r) {
  await r.page.waitForFunction(() => document.querySelector('[data-testid="amd-preview-impact"]')
    || document.querySelector('[data-testid="amd-propose-error"]'), null, { timeout: 20000 });
  await r.idle(500);
  if (await r.tid("amd-propose-error").isVisible().catch(() => false)) throw new Error(`pratinjau ditolak: ${await r.text("amd-propose-error")}`);
  return {
    sebelum: num(await r.text("amd-preview-impact-before")), sesudah: num(await r.text("amd-preview-impact-after")),
    dampak: num(await r.text("amd-preview-impact-delta")), cara: await r.text("amd-preview-impact-method"),
    putus: await isiLayar(r.tid("amd-preview-impact").locator("[data-testid=amd-preview-impact-approval], [data-testid=amd-preview-impact-autoapply]")),
    alasan: await r.text("amd-preview-impact-explain").catch(() => ""),
  };
}

/** [Ajukan Amandemen] → kartu hasil; kembalikan amandemen terbaru pesanan dari basis data. */
async function kirimAmandemen(r, so, nama) {
  const n0 = amdSo(so.id).length;
  await klikSorot(r, r.tid("amd-propose-submit"), `${nama}-kirim`);
  await r.tid("amd-result").waitFor({ timeout: 30000 });
  await r.idle(500);
  const hasil = { status: await r.text("amd-result-status"), pesan: await r.text("amd-result-message"),
    refs: await r.text("amd-result-refs").catch(() => "") };
  await bk.potret(r, `${nama}-hasil`, [r.tid("amd-result")]);
  const rows = amdSo(so.id);
  assert(rows.length === n0 + 1, `amandemen baru tidak tersimpan (${n0} → ${rows.length})`);
  await r.tid("amd-result-done").click();
  await r.idle(800);
  return { amd: rows[rows.length - 1], ...hasil };
}

/** Manajer: Penjualan › Pesanan › tab Koreksi & Amandemen → cari nomor amandemen → buka → catatan → Setujui/Tolak. */
async function putuskan(r, amd, aksi, catatan, nama) {
  await r.page.goto(BASE + "/");
  await r.idle(400);
  await bukaMenu(r, "sales-orders", "amendments", { grup: "penjualan", nama: `${nama}-menu` });
  await r.tid("amendment-center-view").waitFor();
  await r.tid("amd-search").fill(amd.number);
  await r.idle(800);
  const row = r.tid(`amd-row-${amd.id}`);
  await row.waitFor({ timeout: 20000 });
  await klikSorot(r, row, `${nama}-baris`);
  await r.tid("amd-detail-panel").waitFor({ timeout: 20000 });
  await r.tid("amd-decision-box").waitFor({ timeout: 20000 });
  await r.idle(500);
  const panel = await isiLayar(r.tid("amd-detail-panel"));
  await r.tid("amd-decision-note").fill(catatan);
  const tombol = r.tid(aksi === "approve" ? "amd-approve-btn" : "amd-reject-btn");
  await bk.potret(r, `${nama}-putus`, [r.tid("amd-decision-note"), tombol]);
  await tombol.click();
  const harap = aksi === "approve" ? /Diterapkan/i : /Ditolak/i;
  const st = await tungguTeks(r, "amd-detail-status", harap, 30000);
  await r.idle(800);
  await bk.potret(r, `${nama}-hasil`, [r.tid("amd-detail-status")], { locator: r.tid("amd-detail-panel") });
  return { panel, status: st };
}

/** Finance: Penagihan & Penerimaan → [Terima pembayaran] baris SO → nominal bawaan = sisa → [Simpan kwitansi] → [Ya, simpan]. */
async function terimaSisa(r, so, ref, nama) {
  const sisa = sisaSo(so.id);
  await r.page.goto(BASE + "/");   // tutup rincian SO yang masih terbuka
  await r.idle(400);
  await bukaPenagihan(r, `${nama}-penagihan`);
  const row = await barisSo(r, so.id);
  const t = await isiLayar(row);
  assert(t.includes(so.number) && t.includes(rupiahLayar(sisa)), `baris piutang ${so.number} ≠ sisa ${rp(sisa)}: ${t}`);
  await bk.potret(r, `${nama}-baris`, [row]);
  await klikSorot(r, r.tid(`collection-pay-${so.id}`), `${nama}-terima`);
  await r.tid("ar-receipt-modal").waitFor();
  await r.tid(`ar-receipt-alloc-${so.id}`).waitFor();
  await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
  await r.idle(800);
  const alloc = Number(await r.tid(`ar-receipt-alloc-${so.id}`).inputValue());
  assert(dekat(alloc, sisa), `alokasi bawaan ${alloc} ≠ sisa ${sisa}`);
  await r.tid("ar-receipt-reference").fill(ref);
  await r.idle(500);
  await klikSorot(r, r.tid("ar-receipt-submit"), `${nama}-form`);
  await r.tid("ar-receipt-confirm").waitFor();
  const konf = await r.text("ar-receipt-confirm-message");
  assert(konf.includes(rp(sisa)), `konfirmasi: ${konf}`);
  await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), `${nama}-konfirmasi`);
  const note = await tungguTeks(r, "collection-notice", /Kwitansi .*AR-\d+/, 30000);
  await r.idle(800);
  const rc = kwitansiTerakhir(so.id);
  assert(rc && dekat(rc.amount, sisa), "kwitansi tidak sesuai sisa tagihan");
  const je = jurnalKwitansi(rc);
  cekJurnalSeimbang(je, [["1-1100", "D", sisa], ["1-1200", "K", sisa]]);
  const o = soDoc(so.id);
  assert(o.payment_status === "paid" && sisaSo(so.id) <= 0.01, `status bayar ${o.payment_status} sisa ${sisaSo(so.id)}`);
  await bk.potret(r, `${nama}-tercatat`, [r.tid("collection-notice")]);
  return { sisa, rc, je, note };
}

/** Finance: rincian SO → [Terbitkan Faktur Pajak] (faktur per pesanan, sebelum koreksi). */
async function terbitkanFaktur(r, so, nama) {
  const ada = fakturSo(so.id).find((f) => ["normal", "pengganti"].includes(f.status) && f.doc_kind !== "retur");
  if (ada) { r.note(`faktur ${ada.number} sudah ada (jalan ulang)`); return ada; }
  const b = r.tid("issue-tax-invoice-btn");
  await b.scrollIntoViewIfNeeded();
  await klikSorot(r, b, `${nama}-faktur`);
  await r.tid("fkt-modal").waitFor();   // pop-up pratinjau faktur (TaxIssueDialog)
  await r.tid("fkt-modal-submit").click();
  const f = await (async () => {
    for (let i = 0; i < 40; i += 1) {
      const x = fakturSo(so.id).find((y) => y.status === "normal" && y.doc_kind !== "retur");
      if (x) return x;
      await sleep(500);
    }
    return null;
  })();
  assert(f, "faktur pajak tidak terbit");
  await r.tid(`tax-invoice-row-${f.id}`).waitFor({ timeout: 20000 });
  await bk.potret(r, `${nama}-faktur-terbit`, [r.tid(`tax-invoice-row-${f.id}`)]);
  return f;
}

(async () => {
  bersihkanHasil(KODE);
  const r = await new Run(KODE, "S1 Amandemen & koreksi penjualan: sebelum terbit, uang muka, nota kredit, nota debit").start();
  const http4xx = [];
  r.page.on("response", (res) => {
    const u = res.url();
    if (u.includes("/api/") && res.status() >= 400 && res.status() < 500) http4xx.push(`${res.status()} ${res.request().method()} ${u.replace(/^.*\/api/, "/api").split("?")[0]} (${r.who})`);
  });
  const fin = akunPeserta(NO);
  const st = LANJUT ? bacaState() : {};
  const ctx = {};
  const step = async (...a) => { if (!(await r.step(...a))) throw new Error(`langkah ${a[0]} gagal — alur dihentikan`); };
  const sudah = (k) => LANJUT && st[k];
  try {
    // ── 0. PERSIAPAN (endpoint resmi, bukan langkah peserta) ───────────────────────────────────────────────────────
    await step(0, "Pelatih", "Persiapan: SO-C & SO-D terkirim belum dibayar (Kartu Peserta) · SO-A & SO-B baru (2 baris, belum dikirim) · uang muka 30% SO-B",
      "Empat SO peserta siap; SO-C & SO-D belum pernah dikoreksi", async () => {
        const k = kartu(NO);
        const c = k["a_dasar:so_lunas"], d = k["a_dasar:so_sebagian"];
        assert(c && d, `Kartu peserta ${NO} belum lengkap — jalankan: cd backend && python scripts/seed_pelatihan_keuangan_kn.py --mulai ${NO} --peserta ${NO} --hanya a_dasar`);
        ctx.cust = pelangganPeserta(NO);
        ctx.soC = soDoc(c.so_id); ctx.soD = soDoc(d.so_id);
        if (!LANJUT) {
          assert(!amdSo(ctx.soC.id).length && !amdSo(ctx.soD.id).length, `SO peserta ${NO} sudah pernah dikoreksi — pakai peserta segar`);
          assert(sisaSo(ctx.soC.id) > 0 && sisaSo(ctx.soD.id) > 0, "SO-C/SO-D sudah dibayar — pakai peserta segar");
        }
        // Server bisa sedang memuat ulang (agen lain menyunting kode) → "fetch failed": SO yang sempat tersimpan dipakai,
        // bukan dibuat dua kali.
        for (const key of ["soA", "soB"]) {
          if (st[key]) continue;
          const t0 = new Date().toISOString();
          let so = null;
          for (let coba = 0; coba < 3 && !so; coba += 1) {
            try { so = await buatSo(ctx.cust); } catch (e) {
              if (!/fetch failed|ECONNRESET|socket/i.test(String(e.message))) throw e;
              await sleep(8000);
              so = mongo(`return db.sales_orders.find({customer_id:"${ctx.cust.id}",status:"reserved",created_at:{$gt:"${t0}"},
                id:{$nin:${JSON.stringify([st.soA, st.soB].filter(Boolean))}}},{_id:0,id:1}).sort({created_at:1}).limit(1).toArray()[0]||null`);
            }
          }
          assert(so, `SO ${key} gagal dibuat`);
          st[key] = so.id; simpanState(st);
        }
        ctx.soA = soDoc(st.soA); ctx.soB = soDoc(st.soB);
        if (!st.awal) {   // potret nilai awal keempat SO (angka pembanding langkah berikutnya, juga saat jalan ulang)
          const pick = (s) => ({ id: s.id, number: s.number, grand_total: s.grand_total, net_subtotal: s.net_subtotal,
            ppn_amount: s.ppn_amount, items: s.items.map((i) => ({ product_id: i.product_id, product_name: i.product_name,
              quantity: i.quantity, unit: i.unit, price: i.price })) });
          st.awal = { A: pick(ctx.soA), B: pick(ctx.soB), C: pick(ctx.soC), D: pick(ctx.soD) };
          simpanState(st);
        }
        ctx.awal = st.awal;
        if (!(ctx.soB.payments || []).some((p) => p.gl_bucket === "advance")) {
          const dp = Math.round(Number(ctx.soB.grand_total) * 0.3);
          const f = await api(fin);
          await f.post("/ar-receipts", { customer_id: ctx.cust.id, amount: dp, method: "transfer", entity_id: KSC,
            notes: `Uang muka 30% ${ctx.soB.number} (persiapan S1)`, reference_no: `TRF-DP-S1-LATIH${NO}`,
            allocations: [{ order_id: ctx.soB.id, amount: dp }] }, KSC);
          ctx.soB = soDoc(ctx.soB.id);
        }
        for (const s of [ctx.soA, ctx.soB]) assert(s.status === "reserved" && s.items.length >= 1, `${s.number} status ${s.status}`);
        ctx.dpB = r2((ctx.soB.payments || []).filter((p) => p.gl_bucket === "advance").reduce((s, p) => s + p.amount, 0));
        assert(ctx.dpB > 0, "uang muka SO-B tidak tercatat");
        const jeDp = mongo(`const rc=db.ar_receipts.findOne({"allocations.order_id":"${ctx.soB.id}",status:{$ne:"void"}},{_id:0,id:1,cash_txn_id:1});
          return db.journal_entries.findOne({source_id:{$in:[rc.id,rc.cash_txn_id]},status:{$ne:"void"}},{_id:0,number:1,lines:1})`);
        cekJurnalSeimbang(jeDp, [["1-1100", "D", ctx.dpB], ["2-1400", "K", ctx.dpB]]);
        ctx.jeDp = jeDp;
        const ringkas = (s) => `${s.number} ${s.items.map((i) => `${i.product_name} ${i.quantity} ${i.unit} × ${rp(i.price)}`).join(" + ")} = ${rp(s.grand_total)}`;
        r.note(`Peserta ${NO} · ${PELANGGAN} · SO-A ${ringkas(ctx.soA)} · SO-B ${ringkas(ctx.soB)} (uang muka ${rp(ctx.dpB)}: ${teksJe(jeDp)}) · SO-C ${ringkas(ctx.soC)} · SO-D ${ringkas(ctx.soD)}`);
        return `SO-A ${ctx.soA.number} · SO-B ${ctx.soB.number} (uang muka ${rp(ctx.dpB)}) · SO-C ${ctx.soC.number} · SO-D ${ctx.soD.number}`;
      });

    const a1 = ctx.awal.A.items[0], a2 = ctx.awal.A.items[1];

    // ── A. SO BELUM TERBIT ──────────────────────────────────────────────────────────────────────────────────────────
    await step(1, "Sales", "Masuk sebagai Sales → Penjualan › Pesanan → cari nomor SO-A → klik barisnya → [Lihat detail & aksi]",
      "Rincian SO: panel 'Koreksi & Amandemen' berisi 'Belum ada koreksi pada dokumen ini' dan tombol [Ajukan Amandemen]", async () => {
        await masuk(r, "sales");
        await bukaSo(r, ctx.soA, "a-sales");
        const t = await isiLayar(r.tid("amendment-trail-panel"));
        if (!sudah("amdA1")) assert(/Belum ada koreksi/.test(t), `panel koreksi: ${t.slice(0, 160)}`);
        await r.tid("amendment-trail-panel").scrollIntoViewIfNeeded();
        await bk.potret(r, "a-sales-panel-koreksi", [r.tid("amendment-trail-panel")]);
        return t.slice(0, 160);
      });

    ctx.hargaA1 = harga(a1.price, 0.96);
    await step(2, "Sales", `[Ajukan Amandemen] → *Label alasan* Negosiasi pelanggan → baris 1 *Harga satuan* ${rp(a1.price)} → ${rp(ctx.hargaA1)} → isi *Penjelasan tertulis* → baca Dampak Koreksi → [Ajukan Amandemen]`,
      "Dampak: Nilai sekarang → Setelah koreksi; lencana 'Dihitung ulang' + 'Butuh persetujuan Manajer' (harga di bawah harga PT). Hasil 'Menunggu persetujuan'; nilai SO belum berubah, tidak ada jurnal", async () => {
        if (sudah("amdA1")) { ctx.amdA1 = amdById(st.amdA1); return `lewati (sudah ${ctx.amdA1.number})`; }
        await isiAmandemen(r, { alasan: "customer_negotiation", ubah: [[a1.product_id, "price", ctx.hargaA1]],
          catatan: `Latihan ${NO}: pelanggan ambil 2 roll, harga baris 1 disepakati turun (WA 17/11)`, nama: "a-sales" });
        const pv = await tungguPratinjau(r);
        const harapDampak = r2(a1.quantity * (a1.price - ctx.hargaA1) * 1.11);
        assert(dekat(pv.sebelum, ctx.soA.grand_total, 1) && dekat(pv.dampak, harapDampak, 1), `pratinjau ${JSON.stringify(pv)} · harap dampak ${harapDampak}`);
        assert(/Dihitung ulang/i.test(pv.cara) && /persetujuan/i.test(pv.putus), `cara/putus: ${pv.cara} · ${pv.putus}`);
        assert(/di bawah harga PT/.test(pv.alasan), `penjelasan: ${pv.alasan}`);
        await bk.potret(r, "a-sales-pratinjau", [r.tid("amd-reason-select"), r.tid(`amd-item-price-${a1.product_id}`), r.tid("amd-preview-impact")]);
        const k = await kirimAmandemen(r, ctx.soA, "a-sales");
        assert(/Menunggu/i.test(k.status) && k.amd.status === "pending_approval", `status ${k.status} / ${k.amd.status}`);
        const so = soDoc(ctx.soA.id);
        assert(dekat(so.grand_total, ctx.soA.grand_total) && jurnalSo(ctx.soA.id).length === 0, "SO berubah sebelum disetujui / ada jurnal");
        ctx.amdA1 = k.amd; st.amdA1 = k.amd.id; simpanState(st);
        return `${k.amd.number} · ${pv.cara} · ${pv.putus} · dampak −${rp(pv.dampak)} · ${k.pesan.slice(0, 120)}`;
      });

    await step(3, "Manajer", "Masuk sebagai Manajer → Penjualan › Pesanan › tab Koreksi & Amandemen → cari nomor amandemen → klik barisnya → isi *Catatan keputusan* → [Setujui & Terapkan]",
      "Status amandemen 'Diterapkan'. Buku: total SO turun sebesar dampak dan dihitung ulang (DPP + PPN 11% DPP), tidak ada jurnal, eksposur kredit pelanggan ikut turun", async () => {
        if (LANJUT && amdSo(ctx.soA.id).some((x) => x.reason_code === "admin_override")) return "lewati (jalan ulang: sudah lewat)";
        const e0 = await eksposur(ctx.cust.id);
        let diputus = false;
        if (amdById(ctx.amdA1.id).status === "pending_approval") {
          await masuk(r, "manager");
          const h = await putuskan(r, ctx.amdA1, "approve", "Disetujui: pelanggan tetap, volume 2 roll", "a-mgr");
          assert(/Diterapkan/i.test(h.status), `status ${h.status}`);
          diputus = true;
        }
        const amd = amdById(ctx.amdA1.id);
        assert(amd.status === "applied" && amd.method === "re_derive", `amandemen ${amd.status}/${amd.method}`);
        const so = soDoc(ctx.soA.id);
        const h = hitungSo(so);
        assert(so.items[0].price === ctx.hargaA1, `harga baris 1 ${so.items[0].price}`);
        assert(dekat(so.net_subtotal, h.dpp) && dekat(so.ppn_amount, h.ppn) && dekat(so.grand_total, h.grand), `SO ${so.grand_total} ≠ hitung ${h.grand}`);
        assert(dekat(amd.impact.amount_before, ctx.awal.A.grand_total) && dekat(so.grand_total, ctx.awal.A.grand_total + amd.impact.delta),
          `SO ${so.grand_total} ≠ awal ${ctx.awal.A.grand_total} + dampak ${amd.impact.delta}`);
        assert(jurnalSo(ctx.soA.id).length === 0, "amandemen SO belum terbit membuat jurnal");
        const e1 = await eksposur(ctx.cust.id);
        if (diputus) assert(dekat(e0.open_orders - e1.open_orders, -amd.impact.delta, 1), `eksposur pesanan terbuka ${e0.open_orders} → ${e1.open_orders}`);
        ctx.soA = so; ctx.eksA = e1;
        r.note(`A: ${amd.number} diterapkan — ${ctx.soA.number} ${rp(amd.impact.amount_before)} → ${rp(so.grand_total)} (DPP ${rp(so.net_subtotal)} + PPN ${rp(so.ppn_amount)}) · jurnal 0 · eksposur pesanan terbuka ${rp(e0.open_orders)} → ${rp(e1.open_orders)}`);
        return `${amd.number} oleh ${amd.decided_by} · SO ${rp(amd.impact.amount_before)} → ${rp(so.grand_total)} · jurnal 0 · eksposur ${rp(e0.total)} → ${rp(e1.total)}`;
      });

    ctx.hargaA2 = harga(a2.price, 0.8);
    await step(4, "Sales", `Masuk lagi sebagai Sales → rincian SO-A → [Ajukan Amandemen] → *Label alasan* Negosiasi pelanggan → baris 2 *Harga satuan* ${rp(a2.price)} → ${rp(ctx.hargaA2)} → [Ajukan Amandemen]`,
      "Penjelasan dampak menyebut 'Dampak …% mencapai ambang 5%' (koreksi dijumlah dengan koreksi sebelumnya) dan harga di bawah harga PT; hasil 'Menunggu persetujuan'", async () => {
        if (sudah("amdA2")) { ctx.amdA2 = amdById(st.amdA2); return `lewati (sudah ${ctx.amdA2.number})`; }
        await masuk(r, "sales");
        await bukaSo(r, ctx.soA);
        const trail = await isiLayar(r.tid("amendment-trail-panel"));
        assert(trail.includes(ctx.amdA1.number) && /Diterapkan/i.test(trail), `jejak: ${trail.slice(0, 200)}`);
        await isiAmandemen(r, { alasan: "customer_negotiation", ubah: [[a2.product_id, "price", ctx.hargaA2]],
          catatan: `Latihan ${NO}: pelanggan minta harga baris 2 turun 20%`, nama: "a-sales2" });
        const pv = await tungguPratinjau(r);
        assert(/mencapai ambang/.test(pv.alasan), `penjelasan: ${pv.alasan}`);
        await bk.potret(r, "a-sales2-pratinjau", [r.tid("amd-preview-impact-explain")], { locator: r.tid("amd-propose-modal") });
        const k = await kirimAmandemen(r, ctx.soA, "a-sales2");
        assert(k.amd.status === "pending_approval", `status ${k.amd.status}`);
        ctx.amdA2 = k.amd; st.amdA2 = k.amd.id; simpanState(st);
        return `${k.amd.number} · dampak −${rp(pv.dampak)} · ${pv.alasan.slice(0, 160)}`;
      });

    await step(5, "Manajer", "Manajer → tab Koreksi & Amandemen → buka amandemen kedua → isi alasan penolakan → [Tolak]",
      "Status 'Ditolak'. Buku: total SO tetap (sama dengan sesudah langkah 3), tidak ada jurnal; amandemen yang ditolak tetap tercatat di jejak", async () => {
        if (LANJUT && amdSo(ctx.soA.id).some((x) => x.reason_code === "admin_override")) return "lewati (jalan ulang: sudah lewat)";
        const total0 = soDoc(ctx.soA.id).grand_total;
        if (amdById(ctx.amdA2.id).status === "pending_approval") {
          await masuk(r, "manager");
          const h = await putuskan(r, ctx.amdA2, "reject", "Ditolak: harga terlalu jauh di bawah harga PT, tawarkan diskon volume saja", "a-mgr2");
          assert(/Ditolak/i.test(h.status), `status ${h.status}`);
        }
        const amd = amdById(ctx.amdA2.id);
        assert(amd.status === "rejected" && amd.decision_note, `amandemen ${amd.status}`);
        const so = soDoc(ctx.soA.id);
        assert(dekat(so.grand_total, total0) && dekat(so.grand_total, ctx.soA.grand_total) && so.items[1].price === a2.price, `SO berubah: ${so.grand_total}`);
        assert(jurnalSo(ctx.soA.id).length === 0, "ada jurnal");
        return `${amd.number} ditolak ${amd.decided_by}: "${amd.decision_note}" · SO tetap ${rp(so.grand_total)}`;
      });

    await step(6, "Admin Sales", "Masuk sebagai Admin Sales → rincian SO-A → periksa jejak → [Edit / Override SO] → ikon hapus pada baris 2 → isi *Alasan override* → [Simpan]",
      "Jejak: amandemen pertama 'Diterapkan', kedua 'Ditolak'. Pesan '… diperbarui (1 perubahan langsung berlaku)'. Buku: baris 2 keluar, roll-nya kembali bebas, total SO dihitung ulang, jejak 'Override SO oleh Admin' (diterapkan otomatis), tidak ada jurnal", async () => {
        const rollB2 = mongo(`return db.inventory_rolls.find({"reserved_ref.id":"${ctx.soA.id}",product_id:"${a2.product_id}"},{_id:0,id:1,roll_no:1}).toArray()`);
        if (!amdSo(ctx.soA.id).some((x) => x.reason_code === "admin_override")) {
          await masuk(r, "salesadmin");
          await bukaSo(r, ctx.soA, "a-admin");
          const trail = await isiLayar(r.tid("amendment-trail-panel"));
          assert(trail.includes(ctx.amdA1.number) && trail.includes(ctx.amdA2.number) && /Ditolak/i.test(trail), `jejak: ${trail.slice(0, 240)}`);
          await bk.potret(r, "a-admin-jejak", [r.tid("amendment-trail-panel")]);
          await klikSorot(r, r.tid(`override-order-button-${ctx.soA.id}`), "a-admin-override");
          await r.tid("so-override-dialog").waitFor();
          await r.tid("override-lines").waitFor({ timeout: 20000 });
          await r.tid(`override-remove-${a2.product_id}`).click();
          await r.tid("override-reason").fill(`Latihan ${NO}: pelanggan membatalkan baris 2 sebelum dikirim`);
          await r.idle(400);
          await bk.potret(r, "a-admin-hapus-baris", [r.tid(`override-line-${a2.product_id}`), r.tid("override-reason"), r.tid("so-override-submit")]);
          await r.tid("so-override-submit").click();
          const msg = await tungguTeks(r, "order-flash", /diperbarui/, 30000);
          await bk.potret(r, "a-admin-override-hasil", [r.tid("order-flash")]);
          ctx.msgOv = msg;
        }
        const so = soDoc(ctx.soA.id);
        const h = hitungSo(so);
        assert(so.items.length === 1 && so.items[0].product_id === a1.product_id, `baris SO: ${so.items.map((i) => i.product_name).join(",")}`);
        assert(dekat(so.grand_total, h.grand), `total ${so.grand_total} ≠ hitung ${h.grand}`);
        const bebas = mongo(`return db.inventory_rolls.find({id:{$in:${JSON.stringify(rollB2.map((x) => x.id))}}},{_id:0,roll_no:1,status:1,reserved_ref:1}).toArray()`);
        assert(!rollB2.length || bebas.every((x) => x.status === "available" && !x.reserved_ref), `roll baris 2: ${JSON.stringify(bebas)}`);
        const ev = amdSo(ctx.soA.id).find((x) => x.reason_code === "admin_override");
        assert(ev && ev.status === "auto_applied" && ev.changes.some((c) => c.field === "remove"), "jejak override tidak tercatat");
        assert(jurnalSo(ctx.soA.id).length === 0, "ada jurnal");
        const e2 = await eksposur(ctx.cust.id);
        r.note(`A: ${ev.number} Override — baris ${a2.product_name} dihapus, roll ${bebas.map((x) => x.roll_no).join(",")} bebas · SO ${rp(ctx.soA.grand_total)} → ${rp(so.grand_total)} · eksposur pesanan terbuka ${rp(e2.open_orders)}`);
        ctx.soA = so;
        return `${ctx.msgOv || "(jalan ulang)"} · ${ev.number} · SO ${rp(so.grand_total)} · roll ${bebas.map((x) => x.roll_no).join(",")} ${bebas.map((x) => x.status).join(",")}`;
      });

    // ── B. SO BELUM DIKIRIM DENGAN UANG MUKA ────────────────────────────────────────────────────────────────────────
    const b2 = ctx.awal.B.items[1];
    await step(7, "Admin Sales", "Admin Sales → rincian SO-B (sudah ada uang muka) → [Edit / Override SO]",
      "Kotak kuning 'Dokumen sudah terbit (sudah ada pembayaran masuk) — koreksi lewat amandemen/nota.' Baris tidak bisa dihapus", async () => {
        await masuk(r, "salesadmin");
        await bukaSo(r, ctx.soB, "b-admin");
        const pill = await isiLayar(r.tid("order-payment-pill"));
        await klikSorot(r, r.tid(`override-order-button-${ctx.soB.id}`), "b-admin-override");
        await r.tid("so-override-dialog").waitFor();
        const lock = await tungguTeks(r, "so-override-locked", /pembayaran masuk/, 20000);
        assert(!(await r.tid("override-lines").isVisible().catch(() => false)), "baris masih bisa diubah");
        await bk.potret(r, "b-admin-terkunci", [r.tid("so-override-locked")]);
        await r.tid("so-override-close").click();
        return `${pill} · ${lock}`;
      });

    await step(8, "Sales", "Masuk sebagai Sales → rincian SO-B → [Ajukan Amandemen] → *Jumlah* baris 2 diisi 0 → baca pesan → [Batal]",
      "Pesan merah 'Jumlah harus lebih dari nol. Untuk membatalkan baris, gunakan pembatalan pesanan atau retur.'; [Ajukan Amandemen] mati. Buku: uang muka tetap di 2-1400 Uang Muka Pelanggan, SO-B tidak berubah", async () => {
        await masuk(r, "sales");
        await bukaSo(r, ctx.soB);
        await isiAmandemen(r, { alasan: "qty_adjustment", ubah: [[b2.product_id, "quantity", 0]], catatan: "", nama: "b-sales" });
        const err = await tungguTeks(r, "amd-propose-error", /lebih dari nol/, 20000);
        assert(await r.tid("amd-propose-submit").isDisabled(), "tombol Ajukan masih hidup");
        await bk.potret(r, "b-sales-qty-nol", [r.tid(`amd-item-qty-${b2.product_id}`), r.tid("amd-propose-error")], { locator: r.tid("amd-propose-modal") });
        await r.tid("amd-propose-cancel").click();
        const so = soDoc(ctx.soB.id);
        assert(so.items.length === ctx.soB.items.length && dekat(so.grand_total, ctx.soB.grand_total), "SO-B berubah");
        assert(!amdSo(ctx.soB.id).length, "amandemen SO-B tersimpan");
        const dp = r2((so.payments || []).filter((p) => p.gl_bucket === "advance").reduce((s, p) => s + p.amount, 0));
        assert(dekat(dp, ctx.dpB) && mongo(`return db.journal_entries.countDocuments({number:"${ctx.jeDp.number}",status:{$ne:"void"}})`) === 1,
          `uang muka SO-B ${dp} ≠ ${ctx.dpB}`);
        return `${err} · SO-B tetap ${rp(so.grand_total)} · uang muka ${rp(ctx.dpB)} (${teksJe(ctx.jeDp)})`;
      });

    // ── C. SO TERKIRIM: DISKON SUSULAN → NOTA KREDIT ────────────────────────────────────────────────────────────────
    const c1 = ctx.awal.C.items[0];
    await step(9, "Finance", "Masuk dengan akun Finance peserta → rincian SO-C (sudah dikirim, belum dibayar) → [Terbitkan Faktur Pajak]",
      "Baris faktur 'KSC/FKT-… Normal · PPN Rp …' = PPN Keluaran pada jurnal pengiriman. Faktur tidak membuat jurnal", async () => {
        await masuk(r, fin);
        await bukaSo(r, ctx.soC, "c-fin");
        const f = await terbitkanFaktur(r, ctx.soC, "c-fin");
        assert(dekat(f.ppn_amount, ctx.soC.ppn_amount), `PPN faktur ${f.ppn_amount} ≠ SO ${ctx.soC.ppn_amount}`);
        assert(!mongo(`return db.journal_entries.countDocuments({source_id:"${f.id}"})`), "faktur membuat jurnal");
        ctx.fktC = f;
        return `${f.number} · DPP ${rp(f.dpp)} · PPN ${rp(f.ppn_amount)}`;
      });

    ctx.hargaC = harga(c1.price, 0.92);
    await step(10, "Admin Sales", `Admin Sales → rincian SO-C → [Ajukan Amandemen] → *Label alasan* Pemberian diskon tambahan → *Harga satuan* ${rp(c1.price)} → ${rp(ctx.hargaC)} → isi penjelasan → [Ajukan Amandemen]`,
      "Kotak 'Dokumen sudah terbit (sudah terbit Faktur Pajak …)'; lencana 'Nota Kredit' + 'Butuh persetujuan'; hasil 'Menunggu persetujuan'. Nilai SO tidak pernah diubah", async () => {
        if (sudah("amdC")) { ctx.amdC = amdById(st.amdC); return `lewati (sudah ${ctx.amdC.number})`; }
        await masuk(r, "salesadmin");
        await bukaSo(r, ctx.soC, "c-admin");
        await isiAmandemen(r, { alasan: "discount_grant", ubah: [[c1.product_id, "price", ctx.hargaC]],
          catatan: `Latihan ${NO}: diskon susulan Rp ${(c1.price - ctx.hargaC).toLocaleString("id-ID")}/${c1.unit} karena pengiriman terlambat 3 hari`, nama: "c-admin" });
        const pv = await tungguPratinjau(r);
        const banner = await isiLayar(r.tid("amd-issued-banner"));
        assert(/Faktur Pajak/.test(banner), `kotak terbit: ${banner}`);
        assert(/Nota Kredit/i.test(pv.cara) && /persetujuan/i.test(pv.putus), `cara/putus: ${pv.cara} · ${pv.putus}`);
        const harap = r2(c1.quantity * (c1.price - ctx.hargaC) * 1.11);
        assert(dekat(pv.dampak, harap, 1), `dampak ${pv.dampak} ≠ ${harap}`);
        await bk.potret(r, "c-admin-pratinjau", [r.tid("amd-issued-banner"), r.tid("amd-preview-impact")], { locator: r.tid("amd-propose-modal") });
        const k = await kirimAmandemen(r, ctx.soC, "c-admin");
        assert(k.amd.status === "pending_approval" && k.amd.method === "credit_note", `${k.amd.status}/${k.amd.method}`);
        ctx.amdC = k.amd; st.amdC = k.amd.id; simpanState(st);
        return `${k.amd.number} · ${banner.slice(0, 120)} · ${pv.cara} · dampak −${rp(pv.dampak)}`;
      });

    await step(11, "Manajer", "Manajer → tab Koreksi & Amandemen → buka amandemen SO-C → isi catatan → [Setujui & Terapkan]",
      "Status 'Diterapkan'; rincian amandemen menyebut Nota Kredit KSC/CN-… . Buku: jurnal nota kredit 4-1000 Pendapatan (D) + 2-1200 PPN Keluaran (D) / 1-1200 Piutang (K); sisa piutang SO = total − nota kredit", async () => {
        if (amdById(ctx.amdC.id).status === "pending_approval") {
          await masuk(r, "manager");
          const h = await putuskan(r, ctx.amdC, "approve", "Disetujui: kompensasi keterlambatan kirim", "c-mgr");
          assert(/Diterapkan/i.test(h.status), `status ${h.status}`);
        }
        const cn = notaSo(ctx.soC.id).find((n) => n.amendment_id === ctx.amdC.id);
        assert(cn && cn.kind === "credit_note" && cn.status === "posted" && cn.gl_status === "posted", `nota: ${JSON.stringify(cn && { s: cn.status, g: cn.gl_status })}`);
        const netHarap = r2(c1.quantity * (c1.price - ctx.hargaC));
        const ppnHarap = r2(r2(ctx.soC.net_subtotal * 0.11) - r2((ctx.soC.net_subtotal - netHarap) * 0.11));
        assert(dekat(cn.net_amount, netHarap) && dekat(cn.ppn_amount, ppnHarap, 0.02), `nota ${cn.net_amount}+${cn.ppn_amount} ≠ ${netHarap}+${ppnHarap}`);
        const je = jurnalId(cn.journal_entry_id);
        cekJurnalSeimbang(je, [["4-1000", "D", cn.net_amount], ["2-1200", "D", cn.ppn_amount], ["1-1200", "K", cn.gross_amount]]);
        const so = soDoc(ctx.soC.id);
        assert(dekat(so.grand_total, ctx.soC.grand_total), "total SO asal diubah");
        assert(dekat(sisaSo(ctx.soC.id), ctx.soC.grand_total - cn.gross_amount), `sisa ${sisaSo(ctx.soC.id)}`);
        assert(dekat(piutangBukuSo(ctx.soC.id), ctx.soC.grand_total - cn.gross_amount), `1-1200 SO ${piutangBukuSo(ctx.soC.id)}`);
        ctx.cn = cn; ctx.jeCn = je;
        r.note(`C: ${ctx.amdC.number} → ${cn.number} ${rp(cn.gross_amount)} (DPP ${rp(cn.net_amount)} + PPN ${rp(cn.ppn_amount)}) · ${teksJe(je)} · sisa piutang ${rp(sisaSo(ctx.soC.id))}`);
        return `${cn.number} · ${teksJe(je)} · sisa ${rp(sisaSo(ctx.soC.id))}`;
      });

    await step(12, "Finance", "Finance → rincian SO-C → baca panel 'Koreksi & Amandemen' dan daftar Faktur Pajak",
      "Nota koreksi 'KSC/CN-… Selesai − Rp …' dengan catatan 'Nilai dokumen asal sengaja TIDAK diubah'; daftar faktur: faktur awal 'Normal' + 'Draf · dokumen retur' (PPN = PPN nota kredit)", async () => {
        await masuk(r, fin);
        await bukaSo(r, ctx.soC, "c-fin2");
        const t = await isiLayar(r.tid("amendment-trail-panel"));
        assert(t.includes(ctx.cn.number) && t.includes(rupiahLayar(ctx.cn.gross_amount)), `panel: ${t.slice(0, 300)}`);
        await r.tid("amd-trail-notes").scrollIntoViewIfNeeded();
        await bk.potret(r, "c-fin-nota-kredit", [r.tid("amd-trail-notes")]);
        const drafRetur = fakturSo(ctx.soC.id).find((f) => f.doc_kind === "retur");
        if (drafRetur) {
          assert(drafRetur.status === "draf" && dekat(drafRetur.ppn_amount, ctx.cn.ppn_amount), `dokumen retur ${drafRetur.status} ${drafRetur.ppn_amount}`);
          await r.tid(`tax-invoice-row-${drafRetur.id}`).scrollIntoViewIfNeeded();
          await bk.potret(r, "c-fin-draf-retur", [r.tid(`tax-invoice-row-${drafRetur.id}`)]);
        } else {
          r.note("C: draf dokumen pajak retur TIDAK terbentuk untuk nota kredit amandemen (diperiksa)");
        }
        ctx.drafRetur = drafRetur;
        return `${t.slice(0, 200)} · ${drafRetur ? `${drafRetur.number} draf dokumen retur PPN ${rp(drafRetur.ppn_amount)}` : "tanpa draf retur"}`;
      });

    await step(13, "Finance", "Keuangan › Piutang › Penagihan & Penerimaan → baris SO-C → [Terima pembayaran] → nominal bawaan = sisa → isi *No. referensi* → [Simpan kwitansi] → [Ya, simpan]",
      "Baris SO-C 'Belum Lunas' = total − nota kredit; kwitansi KSC/AR-… sebesar sisa. Buku: 1-1100 Kas/Bank (D) / 1-1200 Piutang (K) = sisa; piutang SO-C di buku besar kembali nol", async () => {
        if (sudah("rcC")) { ctx.rcC = kwitansiTerakhir(ctx.soC.id); return `lewati (sudah ${ctx.rcC.number})`; }
        const h = await terimaSisa(r, ctx.soC, `TRF-S1C-LATIH${NO}`, "c-fin-bayar");
        assert(dekat(h.sisa, ctx.soC.grand_total - ctx.cn.gross_amount), `sisa ${h.sisa}`);
        assert(dekat(piutangBukuSo(ctx.soC.id, [h.rc.cash_txn_id, h.rc.id]), 0), `1-1200 SO-C ${piutangBukuSo(ctx.soC.id, [h.rc.cash_txn_id, h.rc.id])}`);
        ctx.rcC = h.rc; ctx.jeRcC = h.je; st.rcC = 1; simpanState(st);
        return `${h.note} · ${teksJe(h.je)}`;
      });

    // ── D. SO TERKIRIM: KENAIKAN HARGA → NOTA DEBIT (TAGIHAN TAMBAHAN) ──────────────────────────────────────────────
    const d1 = ctx.awal.D.items[0];
    await step(14, "Finance", "Finance → rincian SO-D (sudah dikirim, belum dibayar) → [Terbitkan Faktur Pajak]",
      "Baris faktur 'KSC/FKT-… Normal · PPN Rp …' = PPN SO-D", async () => {
        await bukaSo(r, ctx.soD, "d-fin");
        const f = await terbitkanFaktur(r, ctx.soD, "d-fin");
        assert(dekat(f.ppn_amount, ctx.soD.ppn_amount), `PPN faktur ${f.ppn_amount}`);
        ctx.fktD = f;
        return `${f.number} · PPN ${rp(f.ppn_amount)}`;
      });

    ctx.hargaD = harga(d1.price, 1.04);
    await step(15, "Sales", `Masuk sebagai Sales → rincian SO-D → [Ajukan Amandemen] → *Label alasan* Koreksi harga → *Harga satuan* ${rp(d1.price)} → ${rp(ctx.hargaD)} → isi penjelasan → [Ajukan Amandemen]`,
      "Lencana 'Nota Debit' + 'Langsung diterapkan' (dampak di bawah ambang 5% dan Rp 5 juta); hasil 'Diterapkan otomatis' dengan dokumen KSC/DN-… . Buku: jurnal 1-1200 Piutang (D) / 4-1000 Pendapatan (K) + 2-1200 PPN Keluaran (K)", async () => {
        if (sudah("amdD")) { ctx.amdD = amdById(st.amdD); return `lewati (sudah ${ctx.amdD.number})`; }
        await masuk(r, "sales");
        await bukaSo(r, ctx.soD, "d-sales");
        await isiAmandemen(r, { alasan: "price_correction", ubah: [[d1.product_id, "price", ctx.hargaD]],
          catatan: `Latihan ${NO}: harga kontrak Rp ${ctx.hargaD.toLocaleString("id-ID")}/${d1.unit}, salah ketik saat pesanan dibuat`, nama: "d-sales" });
        const pv = await tungguPratinjau(r);
        assert(/Nota Debit/i.test(pv.cara) && /Langsung diterapkan/i.test(pv.putus), `cara/putus: ${pv.cara} · ${pv.putus}`);
        await bk.potret(r, "d-sales-pratinjau", [r.tid("amd-preview-impact")], { locator: r.tid("amd-propose-modal") });
        const k = await kirimAmandemen(r, ctx.soD, "d-sales");
        assert(k.amd.status === "auto_applied" && k.amd.method === "debit_note", `${k.amd.status}/${k.amd.method}`);
        assert(/DN-\d+/.test(k.refs), `dokumen hasil: ${k.refs}`);
        ctx.amdD = k.amd; ctx.refsD = k.refs; st.amdD = k.amd.id; simpanState(st);
        return `${k.amd.number} · ${k.status} · ${k.refs}`;
      });

    await step(16, "Finance", "Masuk dengan akun Finance peserta → rincian SO-D → baca bagian 'Tagihan tambahan'",
      "Tabel Nota Debit · Keterangan · Nilai · Jatuh tempo (= jatuh tempo SO); 'Total tagihan Rp …' = total SO + nota debit. Buku: jurnal nota debit seimbang, piutang SO naik sebesar nota debit", async () => {
        const dn = notaSo(ctx.soD.id).find((n) => n.amendment_id === ctx.amdD.id);
        assert(dn && dn.kind === "debit_note" && dn.status === "posted" && dn.gl_status === "posted", "nota debit belum terbit/berjurnal");
        const netHarap = r2(d1.quantity * (ctx.hargaD - d1.price));
        assert(dekat(dn.net_amount, netHarap) && dekat(dn.ppn_amount, r2(netHarap * 0.11), 0.02), `nota debit ${dn.net_amount}+${dn.ppn_amount}`);
        const je = jurnalId(dn.journal_entry_id);
        cekJurnalSeimbang(je, [["1-1200", "D", dn.gross_amount], ["4-1000", "K", dn.net_amount], ["2-1200", "K", dn.ppn_amount]]);
        await masuk(r, fin);
        await bukaSo(r, ctx.soD, "d-fin2");
        const tb = r.tid("order-extra-billing");
        await tb.waitFor({ timeout: 20000 });
        await tb.scrollIntoViewIfNeeded();
        const t = await isiLayar(tb);
        const total = r2(ctx.soD.grand_total + dn.gross_amount);
        assert(t.includes(dn.number) && t.includes(rupiahLayar(dn.gross_amount)) && t.includes(rupiahLayar(total)), `tagihan tambahan: ${t}`);
        await bk.potret(r, "d-fin-tagihan-tambahan", [tb]);
        assert(dekat(sisaSo(ctx.soD.id), total) && dekat(piutangBukuSo(ctx.soD.id), total), `sisa ${sisaSo(ctx.soD.id)} · 1-1200 ${piutangBukuSo(ctx.soD.id)}`);
        ctx.dn = dn; ctx.jeDn = je;
        r.note(`D: ${ctx.amdD.number} → ${dn.number} ${rp(dn.gross_amount)} (DPP ${rp(dn.net_amount)} + PPN ${rp(dn.ppn_amount)}) · ${teksJe(je)} · total tagihan ${rp(total)}`);
        return `${t.slice(0, 220)} · ${teksJe(je)}`;
      });

    await step(17, "Finance", "Keuangan › Piutang › Penagihan & Penerimaan → baris SO-D → [Terima pembayaran] → nominal bawaan → isi *No. referensi* → [Simpan kwitansi] → [Ya, simpan]",
      "Baris SO-D 'Belum Lunas' = total SO + nota debit; kwitansi sebesar itu. Buku: 1-1100 (D) / 1-1200 (K); piutang SO-D kembali nol", async () => {
        if (sudah("rcD")) { ctx.rcD = kwitansiTerakhir(ctx.soD.id); return `lewati (sudah ${ctx.rcD.number})`; }
        const h = await terimaSisa(r, ctx.soD, `TRF-S1D-LATIH${NO}`, "d-fin-bayar");
        assert(dekat(h.sisa, ctx.soD.grand_total + ctx.dn.gross_amount), `sisa ${h.sisa}`);
        assert(dekat(piutangBukuSo(ctx.soD.id, [h.rc.cash_txn_id, h.rc.id]), 0), "1-1200 SO-D belum nol");
        ctx.rcD = h.rc; st.rcD = 1; simpanState(st);
        return `${h.note} · ${teksJe(h.je)}`;
      });

    // ── E. FINANCE: JEJAK, UMUR PIUTANG, PPN ────────────────────────────────────────────────────────────────────────
    await step(18, "Finance", "Pusat Dokumen › tab Jejak Dokumen → ketik nomor SO-C → klik hasilnya",
      "Rantai SO-C memuat amandemen KSC/AMD-…, nota kredit KSC/CN-… dan jurnalnya, surat jalan, kwitansi", async () => {
        await r.page.goto(BASE + "/");
        await r.idle(400);
        await bk.menu(r, "alat", "document-center", "doc-trace");
        await r.tid("doc-trace-view").waitFor();
        await r.tid("trace-search-input").fill(ctx.soC.number);
        await r.tid(`trace-result-${ctx.soC.id}`).click();
        await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
        await r.tid("trace-graph").waitFor();
        await r.idle(1500);
        const g = await r.text("trace-graph");
        const harus = [ctx.soC.number, ctx.amdC.number, ctx.cn.number, ctx.jeCn.number];
        const hilang = harus.filter((x) => !g.includes(x));
        const ekstra = [ctx.rcC && ctx.rcC.number, ctx.fktC && ctx.fktC.number].filter(Boolean).filter((x) => !g.includes(x));
        if (ekstra.length) r.note(`Jejak Dokumen SO-C tidak menampilkan: ${ekstra.join(", ")}`);
        await bk.potret(r, "e-fin-jejak", [r.tid("trace-anchor-card")], { full: true });
        assert(!hilang.length, `jejak tidak memuat: ${hilang.join(", ")}`);
        return `${harus.join(" → ")}${ekstra.length ? ` · tidak tampil: ${ekstra.join(", ")}` : ""}`;
      });

    await step(19, "Finance", "Cek buku akhir: jurnal seimbang; umur piutang pelanggan; PPN keluaran vs dokumen pajak",
      "Piutang SO-C & SO-D nol (umur piutang tanpa baris SO-C/SO-D); SO-A belum berpiutang (belum dikirim); PPN: nota kredit membalik PPN (draf dokumen retur), nota debit menambah PPN tanpa dokumen pajak baru", async () => {
        const f = await api(fin);
        const ag = await f.get(`/ar/aging/${ctx.cust.id}?entity_id=${KSC}`, KSC);
        const baris = (ag.items || []).filter((x) => [ctx.soC.id, ctx.soD.id].includes(x.order_id) && Number(x.outstanding) > 0.01);
        assert(!baris.length, `umur piutang masih memuat: ${baris.map((x) => `${x.order_number} ${x.outstanding}`).join(", ")}`);
        for (const je of [ctx.jeCn, ctx.jeDn]) cekJurnalSeimbang(je, []);
        const rec = await f.get(`/tax/output-reconciliation?entity_id=${KSC}&period=${new Date().toISOString().slice(0, 7)}`, KSC);
        const unit = (re) => Object.entries(rec.causes || {}).flatMap(([k, arr]) => arr.map((u) => ({ k, u }))).filter(({ u }) => re.test(JSON.stringify(u)));
        const uC = unit(new RegExp(ctx.cn.number)), uD = unit(new RegExp(ctx.soD.number.replace("/", "\\/")));
        const tC = uC.map(({ k, u }) => `${k}: buku ${rp(u.gl_ppn)} vs dokumen ${rp(u.doc_ppn)}`).join("; ");
        const tD = uD.map(({ k, u }) => `${k}: buku ${rp(u.gl_ppn)} vs dokumen ${rp(u.doc_ppn)}`).join("; ");
        r.note(`PPN SO-C (nota kredit ${ctx.cn.number}): ${tC || "cocok"} · PPN SO-D (nota debit ${ctx.dn.number}): ${tD || "cocok"}`);
        r.note(`RINGKAS S1 peserta ${NO}: A ${ctx.soA.number} ${rp(ctx.soA.grand_total)} (jurnal 0) · B ${ctx.soB.number} uang muka ${rp(ctx.dpB)} terkunci · C ${ctx.soC.number} ${rp(ctx.soC.grand_total)} − ${ctx.cn.number} ${rp(ctx.cn.gross_amount)} = ${rp(ctx.rcC.amount)} (${ctx.rcC.number}) · D ${ctx.soD.number} ${rp(ctx.soD.grand_total)} + ${ctx.dn.number} ${rp(ctx.dn.gross_amount)} = ${rp(ctx.rcD.amount)} (${ctx.rcD.number})`);
        return `umur piutang SO-C/SO-D: 0 · ${teksJe(ctx.jeCn)} | ${teksJe(ctx.jeDn)} · PPN: ${tC || "C cocok"} | ${tD || "D cocok"}`;
      });
  } catch (e) {
    r.note("berhenti: " + (e && e.message ? e.message : e));
  }
  if (http4xx.length) r.note(`respons 4xx di layar: ${[...new Set(http4xx)].join(" · ")}`);
  await r.finish();
})();
