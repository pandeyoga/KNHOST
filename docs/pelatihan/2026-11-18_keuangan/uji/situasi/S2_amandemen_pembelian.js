// S2 — AMANDEMEN & SITUASI KHUSUS PENGADAAN (PT Sukacita) — LEWAT LAYAR, tiap peran dengan akunnya, lalu dicocokkan
// dengan BUKU. Jalur utama Pengadaan sampai Bayar (A2) tidak diulang; di sini situasi yang menyimpang dari jalur itu:
//
//   A. PO-1 — amandemen SEBELUM barang datang, lalu batal:
//      Manajer buat PO 1.000 yard (tanpa persetujuan, di bawah Rp 100 juta) → revisi harga (v2, langsung berlaku)
//      → revisi qty 7.000 yard (v3, nilai ≥ Rp 100 juta → persetujuan ulang; Manajer pembuat terkunci) → Admin setuju
//      → Finance membaca riwayat versi (tanpa jurnal) → pemasok batal → Manajer batalkan PO → tetap tanpa jurnal & hutang.
//   B. PO-2 — penerimaan SEBAGIAN, lebih tagih, sisa ditutup lewat amandemen:
//      Manajer buat PO 1.000 yard → Gudang terima 600 → eskalasi → Manajer sesuaikan tugas 600 → Gudang selesaikan
//      (jurnal GR) → Manajer catat faktur 700 yard: layar menahan "lebih tagih"; draf 700 ditolak server → draf
//      dibatalkan → tagihan 600 cocok bersih (jurnal tagihan) → amandemen "Tutup sisa" qty 1.000 → 600 → Admin setuju
//      → PO Selesai, Belum Ditagih Rp 0, GR/IR PO = 0.
//   C. PO-3 — tagihan dengan SELISIH HARGA (3-way mismatch):
//      Manajer buat PO 500 yard @ Rp 14.000 → Gudang terima 500 (jurnal GR) → Manajer catat faktur @ Rp 15.000
//      → "Ada selisih (perlu persetujuan)" → Manajer (pembuat) tidak bisa menyetujui → Admin setujui & posting → jurnal
//      tagihan (selisih Rp 500.000 tetap di GR/IR karena akun selisih harga belum dipetakan — K-26) → Finance: GR/IR,
//      hutang per pemasok, Jejak Dokumen.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/situasi/S2_amandemen_pembelian.js            (bawaan peserta 66)
//   KN_PESERTA=67 node …   ·   KN_MULAI=10 node …  → lanjut dari langkah 10 memakai keadaan tersimpan (perbaikan skrip)
// Butuh: akun & pemasok peserta (`seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN --hanya a_dasar:akun` lalu
// `--hanya a_dasar:mitra`). Satu peserta = satu putaran (tiga PO baru untuk pemasok peserta itu).
const fs = require("fs");
const path = require("path");
const { Run, assert, rp, num, sleep, peserta, akunPeserta, mongo } = require("../lib");
const { setuju, jurnalDari, cekJurnal, tungguTeks, sorot, lepas, klikPotret } = require("../hutang_lib");

const SKU = "DMO-GRY-WVN-001";          // Grey Woven Katun Poplin (yard)
const HARGA = 14000;                    // Rp/yard (harga PO)
const PPN = (dpp) => Math.round(dpp * 11 / 12 * 0.12);   // PPN 12% × DPP nilai lain 11/12 = 11% DPP

// PO-1 (situasi 1 & 5)
const P1 = { qty: 1000, harga2: 14500, qty3: 7000 };
P1.dpp1 = P1.qty * HARGA; P1.dpp2 = P1.qty * P1.harga2; P1.dpp3 = P1.qty3 * P1.harga2;
// PO-2 (situasi 2 & 4)
const P2 = { qty: 1000, terima: 600, tagihLebih: 700, roll: 6 };
P2.gr = P2.terima * HARGA; P2.ppn = PPN(P2.gr); P2.total = P2.gr + P2.ppn;
// PO-3 (situasi 3)
const P3 = { qty: 500, hargaFaktur: 15000, roll: 5 };
P3.gr = P3.qty * HARGA; P3.dppFaktur = P3.qty * P3.hargaFaktur; P3.ppn = PPN(P3.dppFaktur); P3.total = P3.dppFaktur + P3.ppn;
P3.selisih = P3.dppFaktur - P3.gr;

const NO = peserta("66");
const MULAI = Number(process.env.KN_MULAI || 1);
const SAMPAI = Number(process.env.KN_SAMPAI || 99);
const langkah = (no) => no >= MULAI && no <= SAMPAI;
const PEMASOK = `Latihan ${NO} · Pemasok Grey Peserta ${NO}`;
const TAG = Date.now().toString(36).toUpperCase().slice(-4);
const FINANCE = akunPeserta(NO);

const r0 = new Run("S2", "Amandemen & situasi khusus pengadaan — PT Sukacita");
const FKEADAAN = path.join(r0.dir, "keadaan.json");
let K = {};
if (MULAI > 1) K = JSON.parse(fs.readFileSync(FKEADAAN, "utf8"));
const simpan = () => fs.writeFileSync(FKEADAAN, JSON.stringify(K, null, 2));

const db1 = (coll, q, proj = "{_id:0}") => mongo(`return db.${coll}.findOne(${q},${proj})`);
const po = (id) => db1("purchase_orders", `{id:"${id}"}`);
const tugasPo = (id) => mongo(`return db.wms_tasks.find({po_id:"${id}",flow_type:"inbound"},{_id:0,id:1,status:1,expected_qty:1,received_qty:1}).sort({created_at:1}).toArray()`) || [];
/** Semua jurnal (tidak void) yang menaut ke PO: ref.po_id atau dokumen turunannya (tugas gudang, tagihan). */
const jurnalPo = (id) => {
  const ids = [id, ...tugasPo(id).map((t) => t.id),
    ...(mongo(`return db.vendor_bills.find({po_id:"${id}"},{_id:0,id:1}).toArray()`) || []).map((b) => b.id)];
  return mongo(`return db.journal_entries.find({status:{$ne:"void"},$or:[{"ref.po_id":"${id}"},{source_id:{$in:${JSON.stringify(ids)}}}]},{_id:0,number:1,source_type:1,lines:1}).toArray()`) || [];
};
/** Sisa GR/IR (kredit − debit akun 2-1150) satu PO langsung dari jurnal. */
const sisaGrir = (id) => jurnalPo(id).reduce((s, j) => s + j.lines.filter((l) => l.account_code === "2-1150")
  .reduce((a, l) => a + Number(l.credit || 0) - Number(l.debit || 0), 0), 0);

/** Buka menu samping (grup dibuka dulu bila tertutup), lalu tab hub bila disebut. */
async function buka(r, navId, tab, group) {
  const item = r.tid(`nav-${navId}`);
  if (!(await item.isVisible().catch(() => false)) && group) {
    await r.tid(`nav-group-toggle-${group}`).click();
    await item.waitFor({ timeout: 8000 });
  }
  await item.click();
  await r.idle(600);
  if (tab) {
    const t = r.tid(`hub-tab-${tab}`);
    if (await t.isVisible().catch(() => false)) { await t.click(); await r.idle(600); }
  }
}

/** KNSelect yang bisa dicari: klik, ketik, pilih opsi yang memuat teks. */
async function pilihCari(r, testId, ketik, re) {
  for (let i = 0; ; i++) {
    await r.tid(testId).first().click();
    await sleep(300);
    if (ketik) { await r.page.keyboard.type(ketik, { delay: 20 }); await sleep(500); }
    const opt = r.page.getByRole("option").filter({ hasText: re || ketik }).first();
    try {
      await opt.waitFor({ timeout: 5000 });
      await opt.click();
      await sleep(300);
      return;
    } catch (e) {
      if (await r.page.locator('[role="listbox"],[cmdk-list]').first().isVisible().catch(() => false)) await r.page.keyboard.press("Escape");
      if (i >= 2) throw new Error(`opsi "${re || ketik}" tidak ada di ${testId}`);
      await sleep(1500);
    }
  }
}

// ── Layar Pesanan Pembelian ─────────────────────────────────────────────────────────────────────────────────────────
async function tutupPopup(r) {
  for (const id of ["po-detail-popup", "vendor-bill-detail-panel"]) {
    if (await r.tid(id).isVisible().catch(() => false)) {
      await r.page.keyboard.press("Escape");
      await r.tid(id).waitFor({ state: "detached", timeout: 8000 }).catch(() => {});
      await r.idle(300);
    }
  }
}
async function layarPo(r) {
  await tutupPopup(r);
  await buka(r, "purchase-orders", "purchasing", "pembelian");
  await r.tid("po-management-panel").waitFor();
  await r.idle(500);
}
async function bukaPo(r, p) {
  await layarPo(r);
  await r.tid("po-search").fill(p.number);
  await r.idle(900);
  const row = r.tid(`po-card-${p.id}`);
  await row.waitFor({ timeout: 15000 });
  await row.click();
  await r.tid("po-detail-popup").waitFor();
  await r.tid("po-compact-panel").waitFor();
  await r.idle(800);
}

/** Manajer: [Buat PO] › Beli Barang Jadi → pemasok peserta, lokasi Jakarta, satu baris barang → (potret) → [Simpan]. */
async function buatPo(r, qty, catatan, potret) {
  await layarPo(r);
  await klikPotret(r, r.tid("create-po-button"), `${potret}-buat-po`);
  await r.tid("mode-finished-goods").click();
  await r.tid("po-create-modal").waitFor();
  await r.idle(800);
  await pilihCari(r, "supplier-master-select", `Latihan ${NO}`, PEMASOK);
  await pilihCari(r, "po-ship-to-site", "", "Jakarta");
  await r.tid("po-notes-input").fill(catatan);
  await pilihCari(r, "item-product-select", SKU, SKU);
  await r.tid("po-price-hint").waitFor({ timeout: 10000 }).catch(() => {});   // harga acuan termuat dulu, baru ditimpa
  await r.idle(800);
  await r.tid("item-qty-input").fill(String(qty));
  await r.idle(600);
  const unit = await r.text("item-unit-select");
  if (!/yard/i.test(unit)) await pilihCari(r, "item-unit-select", "", /^yard/i);
  const harga = r.tid("item-price-input");
  await harga.click(); await harga.fill(String(HARGA)); await r.page.keyboard.press("Tab");
  await r.idle(400);
  assert(num(await harga.inputValue()) === HARGA, `harga di isian ${await harga.inputValue()}`);
  await pilihCari(r, "item-expected-grade-select", "", /^A\b|Grade A/);
  await r.tid("add-item-button").click();
  await r.tid("po-item-row-0").waitFor();
  await r.idle(500);
  const dpp = qty * HARGA;
  const tot = await r.text("summary-grand-total");
  assert(num(await r.text("po-item-linetotal-0")) === dpp, `subtotal baris ${await r.text("po-item-linetotal-0")} ≠ ${rp(dpp)}`);
  assert(num(await r.text("summary-subtotal")) === dpp, `Subtotal form ${await r.text("summary-subtotal")} ≠ ${rp(dpp)}`);
  assert(num(tot) === dpp + PPN(dpp), `total form ${tot} ≠ ${rp(dpp + PPN(dpp))}`);
  await sorot(r.tid("po-pricing-summary"));
  await klikPotret(r, r.tid("submit-po-button"), `${potret}-isi-po`);
  await lepas(r.tid("po-pricing-summary"));
  await r.tid("po-create-modal").waitFor({ state: "detached", timeout: 20000 });
  const msg = await tungguTeks(r, "po-mgmt-notice", /dibuat/);
  const d = mongo(`return db.purchase_orders.find({supplier_name:${JSON.stringify(PEMASOK)},notes:${JSON.stringify(catatan)}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
  assert(d, "PO tidak tersimpan");
  assert(Math.abs(d.total_amount - dpp) < 0.01 && Math.abs(d.grand_total - dpp - PPN(dpp)) < 0.01, `nilai PO ${d.total_amount}/${d.grand_total}`);
  return { po: { id: d.id, number: d.po_number }, msg, doc: d };
}

/** Rincian PO terbuka → [Revisi / Amandemen PO] (pop-up amandemen siap diisi). */
async function bukaAmandemen(r, p, potret) {
  await bukaPo(r, p);
  try { await klikPotret(r, r.tid("amend-po-button"), potret); } catch (e) { throw new Error(String(e.message).replace(/\s+/g, " ").slice(0, 480)); }
  await r.tid("po-amend-modal").waitFor();
  await r.idle(500);
}

// ── Pusat Persetujuan › Persetujuan Pembelian ────────────────────────────────────────────────────────────────────────
async function bukaPersetujuan(r, p) {
  await tutupPopup(r);
  await buka(r, "approval-inbox", "purchase-approval");
  await r.tid("purchase-approval-view").waitFor();
  await r.idle(800);
  const cari = r.tid("po-approval-search");
  if (await cari.isVisible().catch(() => false)) { await cari.fill(p.number); await r.idle(400); }
  await r.tid(`po-approval-row-${p.id}`).waitFor({ timeout: 15000 });
}

// ── Gudang: Barang Masuk › Scan Terima per PO ───────────────────────────────────────────────────────────────────────
async function bukaTugas(r, p, taskId) {
  await buka(r, "wms-operations", "goods-receipts", "gudang");
  await r.tid("goods-receipts-view").waitFor();
  await r.tid("grn-view-tab-legacy").click();
  await r.tid("inbound-scan-panel").waitFor();
  await r.idle(800);
  await r.tid("inbound-search").fill(p.number);
  await r.idle(500);
  const row = r.tid(`inbound-task-${taskId}`);
  await row.waitFor({ timeout: 15000 });
  return row;
}
async function inputManual(r, taskId, qty, dye) {
  await r.tid("inbound-mode-manual").click();
  await r.tid("receive-doc-qty-input").waitFor();
  await r.tid("receive-doc-qty-input").fill(String(qty));
  await r.tid("scan-dye-lot-input").fill(dye);
  await r.idle(600);
}
/** Pop-up "Goods Receipt — Rincian Roll": n roll × 100 yard, SJ pemasok → [Selesaikan Penerimaan]. */
async function rincianRoll(r, n, perRoll, sj, dye, potret) {
  await r.tid("gr-catchweight-modal").waitFor();
  await r.idle(500);
  for (let i = 1; i < n; i++) {
    if (!(await r.tid(`gr-roll-length-${i}`).isVisible().catch(() => false))) await r.tid("gr-add-roll").click();
  }
  for (let i = 0; i < n; i++) {
    await r.tid(`gr-roll-length-${i}`).fill(String(perRoll));
    await r.tid(`gr-roll-dyelot-${i}`).fill(dye);
  }
  await r.tid("gr-supplier-lot").fill(`LOT-${NO}-${TAG}`);
  await r.tid("gr-supplier-dn").fill(sj);
  await r.idle(400);
  await klikPotret(r, r.tid("gr-submit-complete"), potret);
  await r.tid("gr-catchweight-modal").waitFor({ state: "detached", timeout: 30000 });
  await r.tid("gr-lot-result").waitFor({ timeout: 15000 });
}

// ── Tagihan pemasok ─────────────────────────────────────────────────────────────────────────────────────────────────
async function layarTagihan(r) {
  await tutupPopup(r);
  await buka(r, "accounts-payable", "vendor-bills", "keuangan");
  await r.tid("vendor-bills-view").waitFor();
  await r.idle(600);
}
async function formTagihan(r, p, faktur, potret) {
  await layarTagihan(r);
  await klikPotret(r, r.tid("create-vendor-bill-button"), potret);
  await r.tid("vendor-bill-create-modal").waitFor();
  await r.idle(600);
  await pilihCari(r, "vb-po-select", p.number, p.number);
  await r.tid("vb-item-row-0").waitFor({ timeout: 15000 });
  await r.tid("vb-invoice-input").fill(faktur);
  await r.idle(400);
}
async function bukaTagihan(r, bill) {
  await layarTagihan(r);
  await r.tid("vb-search").fill(bill.number);
  await r.idle(900);
  await r.tid(`vb-open-${bill.id}`).click();
  await r.tid("vendor-bill-detail-panel").waitFor();
  await r.idle(800);
}

(async () => {
  const r = await r0.start();
  const tolak = new Set();
  r.page.on("response", (res) => {
    if (res.status() === 403 && res.url().includes("/api/")) {
      const k = `${r.who.split("@")[0]} ${res.request().method()} ${res.url().replace(/^.*\/api/, "/api").split("?")[0]}`;
      if (!tolak.has(k)) { tolak.add(k); r.note(`403: ${k}`); }
    }
  });
  const sup = db1("suppliers", `{name:${JSON.stringify(PEMASOK)}}`);
  if (!sup) { r.note(`Pemasok ${PEMASOK} belum ada — jalankan seed peserta ${NO} (a_dasar:akun, a_dasar:mitra)`); await r.finish(); return; }
  K.sup = sup.id;
  if (MULAI === 1) {   // hutang pemasok sebelum putaran ini (peserta baru = Rp 0)
    K.hutangAwal = mongo(`return db.vendor_bills.aggregate([{$match:{supplier_id:"${sup.id}",status:{$in:["posted","paid"]}}},{$group:{_id:null,n:{$sum:1},sisa:{$sum:"$outstanding"}}}]).toArray()[0]||{n:0,sisa:0}`);
    simpan();
  }
  r.note(`Peserta ${NO} · ${PEMASOK} · PO-1 ${P1.qty} yd → harga ${rp(P1.harga2)} → ${P1.qty3} yd · PO-2 ${P2.qty} yd terima ${P2.terima} · PO-3 ${P3.qty} yd faktur @ ${rp(P3.hargaFaktur)}`);

  // ═══ A. PO-1 — amandemen sebelum barang datang, lalu batal ═════════════════════════════════════════════════════════
  if (langkah(1)) await r.step(1, "Manajer", `Login manager@ → Pembelian › Pesanan Pembelian → [[Buat PO]] → [[Beli Barang Jadi]] → *Supplier* ${PEMASOK} · *Lokasi kirim* Jakarta · *Catatan* · baris: Grey Woven Katun Poplin ${P1.qty.toLocaleString("id-ID")} yard × ${rp(HARGA)}, Grade A → [[+]] → [[Simpan PO]]`,
    `Ringkasan: Subtotal ${rp(P1.dpp1)} · DPP (nilai lain 11/12) ${rp(Math.round(P1.dpp1 * 11 / 12))} · PPN 12% ${rp(PPN(P1.dpp1))} · Total ${rp(P1.dpp1 + PPN(P1.dpp1))}; sesudah simpan: "PO KSC/PO-… dibuat — tidak perlu persetujuan…", status Menunggu barang (di bawah Rp 100 juta)`, async () => {
      await r.login("manager");
      const { po: p, msg, doc } = await buatPo(r, P1.qty, `S2 PO-1 Latihan ${NO} ${TAG}`, "manajer-po1");
      K.po1 = p; simpan();
      assert(doc.approval_status === "not_required" && doc.status === "pending", `PO-1 ${doc.status}/${doc.approval_status}`);
      const t = tugasPo(p.id);
      assert(t.length === 1 && Number(t[0].expected_qty) === P1.qty, `tugas gudang ${JSON.stringify(t)}`);
      await sorot(r.tid("po-mgmt-notice"));
      await r.shot("manajer-po1-dibuat");
      await lepas(r.tid("po-mgmt-notice"));
      return `${msg} · ${p.number} v${doc.version || 1} · tugas Barang Masuk ${t[0].expected_qty} yard`;
    });

  if (langkah(2)) await r.step(2, "Manajer", `Klik baris PO-1 → di rincian klik [[Revisi / Amandemen PO]] → *Harga* ${rp(P1.harga2)} · *Alasan* "Konfirmasi harga baru dari pemasok" → [[Simpan Revisi]]`,
    `Pesan "PO … direvisi (v2) — langsung berlaku, tidak perlu persetujuan ulang"; nilai ${rp(P1.dpp2)} + PPN ${rp(PPN(P1.dpp2))}; tugas Barang Masuk tetap ${P1.qty.toLocaleString("id-ID")} yard; tidak ada jurnal`, async () => {
      if (r.who !== "manager@kainnusantara.id") await r.login("manager");
      await bukaAmandemen(r, K.po1, "manajer-po1-rincian");
      await r.tid("po-amend-reason").fill("Konfirmasi harga baru dari pemasok");
      const h = r.tid("po-amend-item-price-0");
      await h.click(); await h.fill(String(P1.harga2)); await r.page.keyboard.press("Tab");
      await r.idle(400);
      assert(num(await r.text("po-amend-est-net")) === P1.dpp2, `perkiraan ${await r.text("po-amend-est-net")}`);
      await sorot(r.tid("po-amend-estimate"));
      await klikPotret(r, r.tid("po-amend-submit"), "manajer-po1-revisi-harga");
      await lepas(r.tid("po-amend-estimate"));
      await r.tid("po-amend-modal").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "po-mgmt-notice", /direvisi \(v2\)/);
      const d = po(K.po1.id);
      assert(d.version === 2 && d.status === "pending" && d.approval_status === "not_required", `PO-1 v${d.version} ${d.status}/${d.approval_status}`);
      assert(Math.abs(d.total_amount - P1.dpp2) < 0.01, `nilai v2 ${d.total_amount}`);
      const t = tugasPo(K.po1.id).filter((x) => x.status !== "cancelled");
      assert(t.length === 1 && Number(t[0].expected_qty) === P1.qty, `tugas ${JSON.stringify(t)}`);
      assert(jurnalPo(K.po1.id).length === 0, "amandemen menerbitkan jurnal");
      return `${msg} · ${rp(d.total_amount)} + PPN ${rp(d.ppn_amount)} = ${rp(d.grand_total)}`;
    });

  if (langkah(3)) await r.step(3, "Manajer", `Buka lagi rincian PO-1 → [[Revisi / Amandemen PO]] → *Qty* ${P1.qty3.toLocaleString("id-ID")} · *Alasan* "Tambahan pesanan untuk stok cabang" → [[Simpan Revisi]]`,
    `Perkiraan ${rp(P1.dpp3)} (≥ Rp 100 juta) → pesan "direvisi (v3). Menunggu persetujuan ulang Manajer…"; status Menunggu persetujuan; tugas Barang Masuk dihapus sampai disetujui`, async () => {
      await bukaAmandemen(r, K.po1, "manajer-po1-rincian-v2");
      await r.tid("po-amend-reason").fill("Tambahan pesanan untuk stok cabang");
      await r.tid("po-amend-item-qty-0").fill(String(P1.qty3));
      await r.idle(400);
      assert(num(await r.text("po-amend-est-net")) === P1.dpp3, `perkiraan ${await r.text("po-amend-est-net")}`);
      await sorot(r.tid("po-amend-estimate"));
      await klikPotret(r, r.tid("po-amend-submit"), "manajer-po1-revisi-qty");
      await lepas(r.tid("po-amend-estimate"));
      await r.tid("po-amend-modal").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "po-mgmt-notice", /direvisi \(v3\)/);
      const d = po(K.po1.id);
      assert(d.version === 3 && d.status === "waiting_approval" && d.approval_status === "pending", `PO-1 v${d.version} ${d.status}/${d.approval_status}`);
      const aktif = tugasPo(K.po1.id).filter((x) => !["cancelled", "completed"].includes(x.status));
      assert(aktif.length === 0, `tugas gudang masih ada: ${JSON.stringify(aktif)}`);
      return `${msg} · alasan persetujuan ${d.approval_reason} · peran ${d.required_approval_role}`;
    });

  if (langkah(4)) await r.step(4, "Manajer", "Pusat Persetujuan › tab Persetujuan Pembelian → cari nomor PO-1",
    `Baris PO-1: ${rp(P1.dpp3 + PPN(P1.dpp3))} (DPP ${rp(P1.dpp3)}), Menunggu; kolom Aksi terkunci "PO Anda — disetujui orang lain" (pembuat PO tidak menyetujui revisi PO-nya sendiri)`, async () => {
      if (r.who !== "manager@kainnusantara.id") await r.login("manager");
      await bukaPersetujuan(r, K.po1);
      const row = (await r.tid(`po-approval-row-${K.po1.id}`).innerText()).replace(/\s+/g, " ");
      assert(row.includes(rp(P1.dpp3 + PPN(P1.dpp3)).replace("Rp ", "")), `total di baris: ${row}`);
      assert(await r.tid(`po-approve-${K.po1.id}`).count() === 0, "Manajer pembuat melihat tombol Setujui");
      const kunci = await r.text(`po-approve-locked-${K.po1.id}`);
      assert(/PO Anda/.test(kunci), `alasan kunci: "${kunci}"`);
      await sorot(r.tid(`po-approval-row-${K.po1.id}`));
      await r.shot("manajer-po1-terkunci");
      await lepas(r.tid(`po-approval-row-${K.po1.id}`));
      return row.slice(0, 220);
    });

  if (langkah(5)) await r.step(5, "Admin", "Login admin@ → Pusat Persetujuan › Persetujuan Pembelian → baris PO-1 → [[Setujui]]",
    `Pesan "PO … disetujui penuh…"; PO-1 v3 berlaku; tugas Barang Masuk ${P1.qty3.toLocaleString("id-ID")} yard dibuat untuk Gudang`, async () => {
      await r.login("admin");
      await bukaPersetujuan(r, K.po1);
      await klikPotret(r, r.tid(`po-approve-${K.po1.id}`), "admin-setujui-po1");
      const msg = await tungguTeks(r, "po-approval-notice", /disetujui/);
      const d = po(K.po1.id);
      assert(d.approval_status === "approved" && d.status === "pending", `PO-1 ${d.status}/${d.approval_status}`);
      const t = tugasPo(K.po1.id).filter((x) => x.status === "waiting_goods");
      assert(t.length === 1 && Number(t[0].expected_qty) === P1.qty3, `tugas ${JSON.stringify(tugasPo(K.po1.id))}`);
      return `${msg} · disetujui ${d.approved_by} · tugas ${t[0].expected_qty} yard`;
    });

  if (langkah(6)) await r.step(6, "Finance", `Login akun peserta (${FINANCE}) → Pembelian › Pesanan Pembelian → cari PO-1 → klik baris → gulir ke Riwayat Amandemen → buka v3 dan v2`,
    `Lencana v3; Riwayat Amandemen: v3 "Tambahan pesanan untuk stok cabang" (Qty ${P1.qty.toLocaleString("id-ID")} → ${P1.qty3.toLocaleString("id-ID")}, Grand Total), v2 "Konfirmasi harga…" (Harga ${HARGA.toLocaleString("id-ID")} → ${P1.harga2.toLocaleString("id-ID")}); Finance juga melihat tombol revisi/batal (K-FIN-01); belum ada jurnal`, async () => {
      await r.login(FINANCE);
      await bukaPo(r, K.po1);
      assert(/v3/.test(await r.text("po-version-badge")), "lencana versi bukan v3");
      await r.kfin(r.tid("amend-po-button"), "tombol revisi PO"); await r.kfin(r.tid("cancel-po-button"), "tombol batal PO");
      const hist = r.tid("po-version-history");
      await hist.waitFor();
      const isi = async (v) => {   // riwayat = akordeon: satu versi terbuka sekaligus
        if (!(await r.tid(`po-amendment-detail-${v}`).isVisible().catch(() => false))) await r.tid(`po-amendment-toggle-${v}`).click();
        await r.tid(`po-amendment-detail-${v}`).waitFor();
        await r.idle(300);
        return (await r.tid(`po-amendment-${v}`).innerText()).replace(/\s+/g, " ");
      };
      const v3 = await isi(3);
      assert(/Qty/.test(v3) && v3.includes(P1.qty3.toLocaleString("id-ID")), `v3: ${v3}`);
      assert(/Dewi|Manager|Manajer/i.test(v3) && !/oleh Admin/.test(v3), `pengubah v3: ${v3}`);
      await hist.scrollIntoViewIfNeeded();
      await sorot(hist);
      await r.shot("finance-po1-riwayat-v3");
      const v2 = await isi(2);
      assert(/Harga/.test(v2) && v2.includes(P1.harga2.toLocaleString("id-ID")), `v2: ${v2}`);
      await r.shot("finance-po1-riwayat-v2");
      await lepas(hist);
      assert(jurnalPo(K.po1.id).length === 0, "ada jurnal untuk PO-1");
      return `v3: ${v3.slice(0, 160)} · v2: ${v2.slice(0, 120)}`;
    });

  if (langkah(7)) await r.step(7, "Manajer", "Login manager@ → Pesanan Pembelian → buka PO-1 → [[Batalkan PO]] → [[Batalkan PO]] (konfirmasi)",
    "Pesan \"KSC/PO-… berhasil dibatalkan.\"; status Dibatalkan; tugas Barang Masuk ikut dibatalkan", async () => {
      await r.login("manager");
      await bukaPo(r, K.po1);
      await klikPotret(r, r.tid("cancel-po-button"), "manajer-po1-batalkan");
      const m = await tungguTeks(r, "po-confirm-modal-message", /membatalkan/);
      await sorot(r.tid("po-confirm-modal-confirm"));
      await r.shot("manajer-po1-konfirmasi-batal");
      await setuju(r, "po-confirm-modal");
      const msg = await tungguTeks(r, "po-mgmt-notice", /dibatalkan/);
      const d = po(K.po1.id);
      assert(d.status === "cancelled", `PO-1 ${d.status}`);
      const t = tugasPo(K.po1.id);
      assert(t.every((x) => x.status === "cancelled"), `tugas ${JSON.stringify(t)}`);
      await r.shot("manajer-po1-dibatalkan");
      return `${m} → ${msg}`;
    });

  if (langkah(8)) await r.step(8, "Buku", "Cek buku PO-1 (dibatalkan tanpa penerimaan)",
    "Tidak ada jurnal (GR, tagihan, kliring) untuk PO-1; tidak ada tagihan/hutang; tidak ada tugas gudang terbuka", async () => {
      const je = jurnalPo(K.po1.id);
      assert(je.length === 0, `jurnal PO-1: ${je.map((j) => j.number).join(", ")}`);
      const vb = mongo(`return db.vendor_bills.countDocuments({po_id:"${K.po1.id}"})`);
      assert(vb === 0, `tagihan PO-1 ${vb}`);
      const d = po(K.po1.id);
      return `jurnal 0 · tagihan 0 · status ${d.status} · versi v${d.version} · ${(d.amendments || []).length} amandemen`;
    });

  // ═══ B. PO-2 — terima sebagian, lebih tagih, sisa ditutup lewat amandemen ═══════════════════════════════════════════
  const DYE2 = `DL-S2-${NO}`;
  const SJ2 = `SJ-S2-${NO}-${TAG}`;
  if (langkah(9)) await r.step(9, "Manajer", `Buat PO-2 seperti langkah 1: ${P2.qty.toLocaleString("id-ID")} yard × ${rp(HARGA)} → [[Simpan PO]]`,
    `PO-2 ${rp(P2.qty * HARGA)} + PPN ${rp(PPN(P2.qty * HARGA))}, tanpa persetujuan; tugas Barang Masuk ${P2.qty.toLocaleString("id-ID")} yard`, async () => {
      if (r.who !== "manager@kainnusantara.id") await r.login("manager");
      const { po: p, msg } = await buatPo(r, P2.qty, `S2 PO-2 Latihan ${NO} ${TAG}`, "manajer-po2");
      K.po2 = p;
      const t = tugasPo(p.id);
      K.task2 = t[0].id; simpan();
      return `${msg} · tugas ${t[0].expected_qty} yard`;
    });

  if (langkah(10)) await r.step(10, "Gudang", `Login warehouse@ → Gudang › Operasi Gudang › Barang Masuk → tab Scan Terima per PO → cari PO-2 → klik tugasnya → [[Input Manual]] → *Qty diterima* ${P2.terima} · *Dye Lot* ${DYE2} → [[Kirim Hasil Scan]]`,
    `Pesan "Penerimaan tercatat — Diterima ${P2.terima} dari ${P2.qty.toLocaleString("id-ID")} yard"; tugas Sedang diterima`, async () => {
      await r.login("warehouse");
      const row = await bukaTugas(r, K.po2, K.task2);
      await row.click();
      await r.tid("inbound-mode-toggle").waitFor();
      await inputManual(r, K.task2, P2.terima, DYE2);
      await klikPotret(r, r.tid(`scan-task-${K.task2}`), "gudang-po2-terima-600");
      await r.idle(1200);
      const t = db1("wms_tasks", `{id:"${K.task2}"}`, "{_id:0,status:1,received_qty:1}");
      assert(Number(t.received_qty) === P2.terima && t.status === "receiving", `tugas ${JSON.stringify(t)}`);
      return `tugas ${t.status} · diterima ${t.received_qty}`;
    });

  if (langkah(11)) await r.step(11, "Gudang", `Pada tugas PO-2 tidak ada tombol [[Selesaikan]] (diterima ${P2.terima} < pesanan ${P2.qty.toLocaleString("id-ID")}). Klik [[Eskalasi]] → *Alasan* "Pemasok hanya mengirim ${P2.terima} yard; sisa ${P2.qty - P2.terima} yard tidak dikirim" → [[Eskalasi]]`,
    `Panel tugas menulis "Sisa PO: ${P2.qty - P2.terima} yard" dan hanya menawarkan [[Eskalasi]]; sesudah eskalasi pesan "Dieskalasi ke manajer", tugas berstatus Dieskalasi`, async () => {
      assert(await r.tid(`complete-task-${K.task2}`).count() === 0, "tombol Selesaikan tampil walau barang kurang");
      await klikPotret(r, r.tid("inbound-escalate-open"), "gudang-po2-hanya-eskalasi");
      await r.tid("inbound-escalate-modal").waitFor();
      await r.tid("inbound-escalate-reason").fill(`Pemasok hanya mengirim ${P2.terima} yard; sisa ${P2.qty - P2.terima} yard tidak dikirim (Latihan ${NO})`);
      await klikPotret(r, r.tid("inbound-escalate-submit"), "gudang-po2-eskalasi");
      await r.tid("inbound-escalate-modal").waitFor({ state: "detached", timeout: 15000 });
      const t = db1("wms_tasks", `{id:"${K.task2}"}`, "{_id:0,status:1,escalation:1}");
      assert(t.status === "escalated", `status ${t.status}`);
      return `${t.status} · alasan "${t.escalation.reason}"`;
    });

  if (langkah(12)) await r.step(12, "Manajer", `Login manager@ → Meja Saya → kartu "Perlu keputusan — eskalasi gudang" → baris PO-2 → [[Tinjau & Selesaikan]] pada kartu PO-2 → *Qty disesuaikan* ${P2.terima} · *Catatan penyelesaian* → [[Selesaikan & Lanjutkan Tugas]]`,
    `Kartu eskalasi: Diharapkan ${P2.qty.toLocaleString("id-ID")} · Diterima ${P2.terima} yard; sesudah diselesaikan tugas kembali ke Gudang berstatus Siap diselesaikan (harapan ${P2.terima} yard)`, async () => {
      await r.login("manager");
      await r.tid("nav-my-desk").click();
      await r.idle(1500);
      const baris = r.tid(`my-desk-row-${K.task2}`);
      await baris.waitFor({ timeout: 15000 });
      await sorot(r.tid("my-desk-queue-eskalasi_keputusan"));
      await r.shot("manajer-meja-eskalasi");
      await lepas(r.tid("my-desk-queue-eskalasi_keputusan"));
      const aksi = r.tid(`my-desk-action-${K.task2}`);
      await ((await aksi.isVisible().catch(() => false)) ? aksi : baris).click();
      await r.tid("my-desk-detail-action").click();   // meja gelombang 1 — aksi pindah layar dari pop-up rincian
      await r.tid("escalation-dashboard").waitFor({ timeout: 15000 });
      await r.idle(800);
      await klikPotret(r, r.tid(`resolve-task-${K.task2}`), "manajer-tinjau-eskalasi");
      await r.tid("escalation-resolve-modal").waitFor();
      await r.tid("esc-adjusted-qty").fill(String(P2.terima));
      await r.tid("esc-resolution-notes").fill(`Sudah konfirmasi ke pemasok: hanya ${P2.terima} yard dikirim, sisa tidak dikirim. Qty disesuaikan.`);
      await klikPotret(r, r.tid("escalation-resolve-submit"), "manajer-selesaikan-eskalasi");
      await r.tid("escalation-resolve-modal").waitFor({ state: "detached", timeout: 15000 });
      const t = db1("wms_tasks", `{id:"${K.task2}"}`, "{_id:0,status:1,expected_qty:1,received_qty:1}");
      assert(t.status === "qc_check" && Number(t.expected_qty) === P2.terima, `tugas ${JSON.stringify(t)}`);
      return `tugas ${t.status} · harapan ${t.expected_qty} · diterima ${t.received_qty}`;
    });

  if (langkah(13)) await r.step(13, "Gudang", `Login warehouse@ → Barang Masuk › Scan Terima per PO → tugas PO-2 → [[Selesaikan]] → pop-up Rincian Roll: ${P2.roll} roll × 100 yard ([[+ Tambah roll]]), Dye Lot, *Lot supplier*, *No. SJ supplier* ${SJ2} → [[Selesaikan Penerimaan]]`,
    `Σ roll = ${P2.terima} yard ✓; pesan "Barang masuk gudang"; roll masuk karantina menunggu pemeriksaan kedatangan; PO-2 "Diterima sebagian" ${P2.terima}/${P2.qty.toLocaleString("id-ID")}`, async () => {
      await r.login("warehouse");
      const row = await bukaTugas(r, K.po2, K.task2);
      await row.click();
      await r.tid(`complete-task-${K.task2}`).waitFor();
      await r.tid(`complete-task-${K.task2}`).click();
      await rincianRoll(r, P2.roll, 100, SJ2, DYE2, "gudang-po2-rincian-roll");
      await r.shot("gudang-po2-hasil-penerimaan");
      const d = po(K.po2.id);
      assert(d.status === "partial" && Number(d.items[0].received_qty) === P2.terima, `PO-2 ${d.status} ${d.items[0].received_qty}`);
      const rolls = mongo(`return db.inventory_rolls.countDocuments({$or:[{po_id:"${K.po2.id}"},{"acquired.ref_id":"${K.po2.id}"}]})`);
      return `PO-2 ${d.status} · diterima ${d.items[0].received_qty}/${d.items[0].quantity} · ${rolls} roll`;
    });

  if (langkah(14)) await r.step(14, "Buku", "Cek buku: jurnal penerimaan PO-2",
    `Persediaan Barang 1-1300 (D) ${rp(P2.gr)} / Hutang Belum Ditagih (GR/IR) 2-1150 (K) ${rp(P2.gr)} — hanya ${P2.terima} yard yang diterima, seimbang`, async () => {
      const je = jurnalDari([K.task2]).find((j) => j.source_type === "goods_receipt");
      assert(je, "jurnal GR PO-2 tidak ada");
      K.je_gr2 = je.number; simpan();
      return cekJurnal(je, [["1-1300", "D", P2.gr], ["2-1150", "K", P2.gr]]);
    });

  const FAKTUR2 = `INV-S2-${NO}-${TAG}`;
  if (langkah(15)) await r.step(15, "Manajer", `Login manager@ → Keuangan › Hutang › Tagihan → [[Buat Tagihan]] → *Pesanan Pembelian* PO-2 · *No. Faktur Supplier* ${FAKTUR2} → *Qty Tagih* ${P2.tagihLebih} (angka di faktur pemasok)`,
    `Baris: Dipesan ${P2.qty.toLocaleString("id-ID")} · Diterima ${P2.terima} · Sisa Tagih ${P2.terima}; Cocok? "Lebih tagih"; ringkasan "Lebih tagih (tidak bisa dikirim)"; tombol utama berubah menjadi [[Perbaiki Kelebihan Tagih Dulu]] dan mati`, async () => {
      await r.login("manager");
      await formTagihan(r, K.po2, FAKTUR2, "manajer-po2-tagihan-baru");
      assert(num(await r.tid("vb-item-billed-0").inputValue()) === P2.terima, "qty tagih bawaan ≠ diterima");
      await r.tid("vb-item-billed-0").fill(String(P2.tagihLebih));
      await r.idle(400);
      const match = await r.text("vb-overall-match");
      assert(/Lebih tagih/i.test(match), `pencocokan: ${match}`);
      assert(await r.tid("vb-submit-now").isDisabled(), "tombol kirim tidak mati");
      const tombol = await r.text("vb-submit-now");
      await sorot(r.tid("vb-overall-match"));
      await sorot(r.tid("vb-item-row-0"));
      await r.shot("manajer-po2-lebih-tagih");
      await lepas(r.tid("vb-overall-match"));
      await lepas(r.tid("vb-item-row-0"));
      return `${match} · tombol "${tombol}" (mati)`;
    });

  if (langkah(15)) await r.step(16, "Manajer", "Klik [[Simpan Draf]] (draf dicatat apa adanya) → buka draf itu dari daftar → [[Kirim]]",
    "Draf tersimpan (status Draf, Lebih tagih); [[Kirim]] ditolak: \"3-way match GAGAL — lebih tagih (… Tagih 700 melebihi sisa yang boleh ditagih 600 (diterima) …). Draf tidak bisa diubah — batalkan draf ini, lalu buat tagihan baru…\"; status tetap Draf, tidak ada jurnal", async () => {
      await klikPotret(r, r.tid("vb-save-draft"), "manajer-po2-simpan-draf");
      await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
      const b = mongo(`return db.vendor_bills.find({po_id:"${K.po2.id}",supplier_invoice_no:"${FAKTUR2}"},{_id:0,id:1,bill_number:1,status:1,match_status:1}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(b && b.status === "draft" && b.match_status === "blocked", `draf ${JSON.stringify(b)}`);
      K.draf2 = { id: b.id, number: b.bill_number }; simpan();
      await bukaTagihan(r, K.draf2);
      await klikPotret(r, r.tid("vb-action-submit"), "manajer-po2-kirim-draf");
      await r.idle(1200);
      const panel = (await r.tid("vendor-bill-detail-panel").innerText()).replace(/\s+/g, " ");
      const m = panel.match(/3-way match GAGAL[^.]*\.[^.]*\./);
      assert(m && /batalkan draf/.test(panel), `pesan tolak tidak tampil: ${panel.slice(0, 400)}`);
      await r.shot("manajer-po2-draf-ditolak");
      const b2 = db1("vendor_bills", `{id:"${K.draf2.id}"}`, "{_id:0,status:1}");
      assert(b2.status === "draft", `status ${b2.status}`);
      assert(jurnalDari([K.draf2.id]).length === 0, "draf berjurnal");
      return `${K.draf2.number} draf · ${m[0].slice(0, 220)}`;
    });

  if (langkah(17)) await r.step(17, "Manajer", `Di rincian draf klik [[Batalkan]] → *Alasan pembatalan* "Qty faktur salah — pemasok hanya mengirim ${P2.terima} yard" → [[Batalkan Tagihan]]`,
    "Draf berstatus Dibatalkan; nomor faktur pemasok bebas dipakai lagi; tidak ada jurnal", async () => {
      if (!(await r.tid("vendor-bill-detail-panel").isVisible().catch(() => false))) {
        if (r.who !== "manager@kainnusantara.id") await r.login("manager");
        await bukaTagihan(r, K.draf2);
      }
      await klikPotret(r, r.tid("vb-action-cancel"), "manajer-po2-batalkan-draf");
      await r.tid("vb-cancel-confirm").waitFor();
      await r.tid("vb-cancel-confirm-reason").fill(`Qty faktur salah — pemasok hanya mengirim ${P2.terima} yard`);
      await setuju(r, "vb-cancel-confirm");
      await r.idle(1200);
      const b = db1("vendor_bills", `{id:"${K.draf2.id}"}`, "{_id:0,status:1,cancel_reason:1}");
      assert(b.status === "cancelled", `status ${b.status}`);
      assert(jurnalDari([K.draf2.id]).length === 0, "pembatalan draf berjurnal");
      return `${K.draf2.number} ${b.status} · ${b.cancel_reason}`;
    });

  if (langkah(18)) await r.step(18, "Manajer", `[[Buat Tagihan]] → PO-2 · *No. Faktur Supplier* ${FAKTUR2} (faktur yang sudah diperbaiki pemasok) → biarkan *Qty Tagih* ${P2.terima} → [[Kirim & Posting]]`,
    `Pencocokan "Cocok bersih"; Subtotal ${rp(P2.gr)}; pesan "Tagihan VB-… dibuat — langsung terposting (cocok bersih)."; Total ${rp(P2.total)} = DPP ${rp(P2.gr)} + PPN ${rp(P2.ppn)}`, async () => {
      if (r.who !== "manager@kainnusantara.id") await r.login("manager");
      await formTagihan(r, K.po2, FAKTUR2, "manajer-po2-tagihan-ulang");
      assert(num(await r.tid("vb-item-billed-0").inputValue()) === P2.terima, "qty tagih bawaan ≠ diterima");
      const match = await r.text("vb-overall-match");
      assert(/Cocok bersih/i.test(match), `pencocokan: ${match}`);
      assert(num(await r.text("vb-gross-total")) === P2.gr, "subtotal");
      await sorot(r.tid("vb-overall-match"));
      await klikPotret(r, r.tid("vb-submit-now"), "manajer-po2-tagihan-cocok");
      await lepas(r.tid("vb-overall-match"));
      const confirm = r.tid("confirm-modal");
      if (await confirm.isVisible({ timeout: 2000 }).catch(() => false)) await setuju(r, "confirm-modal");
      await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "vb-notice", /terposting/);
      const b = mongo(`return db.vendor_bills.find({po_id:"${K.po2.id}",status:{$nin:["cancelled","draft"]}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      assert(b && b.status === "posted" && Math.abs(b.grand_total - P2.total) < 0.01, `tagihan ${b && b.status} ${b && b.grand_total}`);
      K.bill2 = { id: b.id, number: b.bill_number }; simpan();
      return `${msg} · ${b.bill_number} · DPP ${rp(b.total_amount)} · PPN ${rp(b.ppn_amount)} · total ${rp(b.grand_total)}`;
    });

  if (langkah(19)) await r.step(19, "Buku", "Cek buku: jurnal tagihan PO-2 & sisa GR/IR",
    `GR/IR 2-1150 (D) ${rp(P2.gr)} + PPN Masukan 1-1500 (D) ${rp(P2.ppn)} / Hutang Usaha 2-1100 (K) ${rp(P2.total)}; sisa GR/IR PO-2 = Rp 0 (yang diterima = yang ditagih)`, async () => {
      const je = jurnalDari([K.bill2.id]).find((j) => j.source_type === "vendor_bill");
      assert(je, "jurnal tagihan PO-2 tidak ada");
      K.je_bill2 = je.number; simpan();
      const s = sisaGrir(K.po2.id);
      assert(Math.abs(s) < 0.01, `sisa GR/IR PO-2 ${s}`);
      return `${cekJurnal(je, [["2-1150", "D", P2.gr], ["1-1500", "D", P2.ppn], ["2-1100", "K", P2.total]])} · sisa GR/IR PO-2 ${rp(s)}`;
    });

  if (langkah(20)) await r.step(20, "Manajer", `Pesanan Pembelian → buka PO-2 (Diterima sebagian, Belum Ditagih ${rp(PPN(P2.qty * HARGA) + P2.qty * HARGA - P2.total)}) → [[Revisi / Amandemen PO]] → pada baris yang sudah diterima klik [[Tutup sisa — qty jadi ${P2.terima} (= diterima)]] → *Alasan* "Pemasok tidak sanggup mengirim sisa ${P2.qty - P2.terima} yard" → [[Simpan Revisi]]`,
    `Baris terkunci (harga/satuan/diskon), hanya "Tutup sisa"; perkiraan ${rp(P2.gr)}; pesan "direvisi (v2). Menunggu persetujuan ulang…"; PO-2 Menunggu persetujuan`, async () => {
      if (r.who !== "manager@kainnusantara.id") await r.login("manager");
      await bukaPo(r, K.po2);
      const belum = await r.text("po-unbilled").catch(() => "");
      await sorot(r.tid("po-billing-summary"));
      await r.shot("manajer-po2-sebelum-tutup-sisa");
      await lepas(r.tid("po-billing-summary"));
      await klikPotret(r, r.tid("amend-po-button"), "manajer-po2-buka-revisi");
      await r.tid("po-amend-modal").waitFor();
      await r.idle(400);
      assert(await r.tid("po-amend-item-qty-0").isDisabled(), "qty baris diterima tidak terkunci");
      await r.tid("po-amend-reason").fill(`Pemasok tidak sanggup mengirim sisa ${P2.qty - P2.terima} yard`);
      await r.tid("po-amend-item-close-rest-0").click();
      await r.idle(400);
      assert(num(await r.tid("po-amend-item-qty-0").inputValue()) === P2.terima, "qty tidak menjadi qty diterima");
      assert(num(await r.text("po-amend-est-net")) === P2.gr, `perkiraan ${await r.text("po-amend-est-net")}`);
      await sorot(r.tid("po-amend-item-close-0"));
      await klikPotret(r, r.tid("po-amend-submit"), "manajer-po2-tutup-sisa");
      await lepas(r.tid("po-amend-item-close-0"));
      await r.tid("po-amend-modal").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "po-mgmt-notice", /direvisi \(v2\)/);
      const d = po(K.po2.id);
      assert(d.version === 2 && d.status === "waiting_approval", `PO-2 v${d.version} ${d.status}`);
      return `sebelum: Belum Ditagih ${belum} · ${msg} · alasan persetujuan ${d.approval_reason}`;
    });

  if (langkah(21)) await r.step(21, "Admin", "Login admin@ → Pusat Persetujuan › Persetujuan Pembelian → baris PO-2 → [[Setujui]]",
    `Pesan "PO … disetujui penuh. Barang sudah diterima seluruhnya — PO Selesai, tidak ada tugas Barang Masuk baru."; PO-2 berstatus Selesai (${P2.terima}/${P2.terima})`, async () => {
      await r.login("admin");
      await bukaPersetujuan(r, K.po2);
      await klikPotret(r, r.tid(`po-approve-${K.po2.id}`), "admin-setujui-po2");
      const msg = await tungguTeks(r, "po-approval-notice", /PO Selesai/);
      const d = po(K.po2.id);
      assert(d.status === "completed", `PO-2 ${d.status} (harus Selesai)`);
      const t = tugasPo(K.po2.id);
      assert(t.length === 1 && t[0].id === K.task2 && Number(t[0].expected_qty) === P2.terima, `tugas ${JSON.stringify(t)}`);
      return `${msg} · PO-2 ${d.status} · tugas tetap 1 (${t[0].status}, harapan ${t[0].expected_qty})`;
    });

  if (langkah(22)) await r.step(22, "Finance", "Login akun peserta → Pesanan Pembelian → buka PO-2",
    `Status Selesai · v2 · Status Penagihan: Nilai PO ${rp(P2.total)} = Sudah Ditagih ${rp(P2.total)} · Belum Ditagih Rp 0; Riwayat Amandemen v2 Qty ${P2.qty.toLocaleString("id-ID")} → ${P2.terima}`, async () => {
      await r.login(FINANCE);
      await bukaPo(r, K.po2);
      const unb = await r.text("po-unbilled");
      assert(num(unb) === 0, `Belum Ditagih ${unb}`);
      assert(/v2/.test(await r.text("po-version-badge")), "versi");
      const bill = (await r.tid("po-billing-summary").innerText()).replace(/\s+/g, " ");
      assert(bill.split(rp(P2.total).replace("Rp ", "")).length >= 3, `ringkasan tagihan ${bill}`);
      await sorot(r.tid("po-billing-summary"));
      await r.shot("finance-po2-selesai");
      await lepas(r.tid("po-billing-summary"));
      return bill.slice(0, 200);
    });

  // ═══ C. PO-3 — tagihan dengan selisih harga ═════════════════════════════════════════════════════════════════════
  const DYE3 = `DL-S2-${NO}-3`;
  const SJ3 = `SJ-S2-${NO}-${TAG}-3`;
  if (langkah(23)) await r.step(23, "Manajer", `Login manager@ → buat PO-3 seperti langkah 1: ${P3.qty} yard × ${rp(HARGA)} → [[Simpan PO]]`,
    `PO-3 ${rp(P3.gr)} + PPN ${rp(PPN(P3.gr))}, tanpa persetujuan; tugas Barang Masuk ${P3.qty} yard`, async () => {
      await r.login("manager");
      const { po: p, msg } = await buatPo(r, P3.qty, `S2 PO-3 Latihan ${NO} ${TAG}`, "manajer-po3");
      K.po3 = p;
      K.task3 = tugasPo(p.id)[0].id; simpan();
      return msg;
    });

  if (langkah(24)) await r.step(24, "Gudang", `Login warehouse@ → Barang Masuk › Scan Terima per PO → PO-3 → [[Input Manual]] ${P3.qty} yard → [[Kirim Hasil Scan]] → [[Selesaikan]] → ${P3.roll} roll × 100 yard, SJ ${SJ3} → [[Selesaikan Penerimaan]]`,
    `Diterima ${P3.qty} dari ${P3.qty} yard → "Barang masuk gudang"; PO-3 Selesai (diterima penuh)`, async () => {
      await r.login("warehouse");
      const row = await bukaTugas(r, K.po3, K.task3);
      await row.click();
      await r.tid("inbound-mode-toggle").waitFor();
      await inputManual(r, K.task3, P3.qty, DYE3);
      await r.tid(`scan-task-${K.task3}`).click();
      await r.page.waitForFunction((id) => !!document.querySelector(`[data-testid="complete-task-${id}"]`), K.task3, { timeout: 15000 });
      await r.idle(600);
      await r.tid(`complete-task-${K.task3}`).click();
      await rincianRoll(r, P3.roll, 100, SJ3, DYE3, "gudang-po3-rincian-roll");
      const d = po(K.po3.id);
      assert(Number(d.items[0].received_qty) === P3.qty, `diterima ${d.items[0].received_qty}`);
      const je = jurnalDari([K.task3]).find((j) => j.source_type === "goods_receipt");
      assert(je, "jurnal GR PO-3 tidak ada");
      K.je_gr3 = je.number; simpan();
      return `PO-3 ${d.status} · ${cekJurnal(je, [["1-1300", "D", P3.gr], ["2-1150", "K", P3.gr]])}`;
    });

  const FAKTUR3 = `INV-S2-${NO}-${TAG}-3`;
  if (langkah(25)) await r.step(25, "Manajer", `Login manager@ → Tagihan → [[Buat Tagihan]] → PO-3 · *No. Faktur Supplier* ${FAKTUR3} → *Harga* ${rp(P3.hargaFaktur)} (harga di faktur pemasok)`,
    `Baris: harga PO ${rp(HARGA)}, Cocok? "Selisih" +7,1%; ringkasan "Ada selisih (perlu persetujuan)"; Subtotal ${rp(P3.dppFaktur)}; tombol [[Kirim (minta persetujuan)]]`, async () => {
      await r.login("manager");
      await formTagihan(r, K.po3, FAKTUR3, "manajer-po3-tagihan-baru");
      const h = r.tid("vb-item-price-0");
      await h.click(); await h.fill(String(P3.hargaFaktur)); await r.page.keyboard.press("Tab");
      await r.idle(400);
      const match = await r.text("vb-overall-match");
      assert(/Ada selisih/i.test(match), `pencocokan ${match}`);
      assert(num(await r.text("vb-gross-total")) === P3.dppFaktur, "subtotal");
      const tombol = await r.text("vb-submit-now");
      assert(/minta persetujuan/i.test(tombol), `tombol ${tombol}`);
      await sorot(r.tid("vb-item-row-0"));
      await sorot(r.tid("vb-overall-match"));
      await r.shot("manajer-po3-selisih-harga");
      await lepas(r.tid("vb-item-row-0"));
      await lepas(r.tid("vb-overall-match"));
      return `${match} · tombol "${tombol}"`;
    });

  if (langkah(25)) await r.step(26, "Manajer", "Klik [[Kirim (minta persetujuan)]] → buka tagihan itu",
    `Status Menunggu Persetujuan; pengecualian "Harga ${rp(P3.hargaFaktur)} menyimpang +7,14% dari harga PO ${rp(HARGA)} (toleransi ±5%)"; Manajer pembuat tidak melihat [[Setujui & Posting]] — petunjuk "Tagihan Anda — disetujui orang lain (kontrol dua orang)"; belum ada jurnal & hutang`, async () => {
      await r.tid("vb-submit-now").click();
      const confirm = r.tid("confirm-modal");
      if (await confirm.isVisible({ timeout: 2000 }).catch(() => false)) await setuju(r, "confirm-modal");
      await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
      await r.idle(800);
      const b = mongo(`return db.vendor_bills.find({po_id:"${K.po3.id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      assert(b && b.status === "pending_approval" && b.match_status === "warning", `tagihan ${b && b.status}/${b && b.match_status}`);
      K.bill3 = { id: b.id, number: b.bill_number }; simpan();
      await bukaTagihan(r, K.bill3);
      const ex = await r.text("vb-match-exceptions");
      assert(ex.includes(`Harga ${rp(P3.hargaFaktur)} menyimpang +7,14% dari harga PO ${rp(HARGA)}`), `pengecualian ${ex}`);
      assert(/disetujui orang lain/.test(await r.text("vb-decide-hint").catch(() => "")), "petunjuk kontrol dua orang tidak tampil");
      assert(await r.tid("vb-action-approve").count() === 0, "pembuat tagihan melihat tombol Setujui");
      const hint = await r.text("vb-decide-hint").catch(() => "");
      await sorot(r.tid("vb-match-exceptions"));
      await r.shot("manajer-po3-menunggu-persetujuan");
      await lepas(r.tid("vb-match-exceptions"));
      assert(jurnalDari([K.bill3.id]).length === 0, "tagihan menunggu persetujuan sudah berjurnal");
      return `${b.bill_number} ${b.status} · ${ex.slice(0, 160)} · petunjuk "${hint}"`;
    });

  if (langkah(27)) await r.step(27, "Admin", "Login admin@ → Keuangan › Hutang › Tagihan → buka tagihan PO-3 → [[Setujui & Posting]] → konfirmasi [[Setujui & Posting]]",
    `Status Terposting; Total ${rp(P3.total)} = DPP ${rp(P3.dppFaktur)} + PPN ${rp(P3.ppn)}; baris "Selisih harga terhadap PO ${rp(P3.selisih)}" + catatan "masih berada di akun GR/IR karena akun Selisih harga pembelian belum diatur…"`, async () => {
      await r.login("admin");
      await bukaTagihan(r, K.bill3);
      await klikPotret(r, r.tid("vb-action-approve"), "admin-po3-setujui");
      await r.tid("vb-approve-confirm").waitFor();
      await setuju(r, "vb-approve-confirm");
      await r.idle(1500);
      const b = db1("vendor_bills", `{id:"${K.bill3.id}"}`, "{_id:0,status:1,approved_by:1,grand_total:1,ppn_amount:1,price_variance_amount:1,price_variance_posted:1}");
      assert(b.status === "posted" && Math.abs(b.grand_total - P3.total) < 0.01, `tagihan ${JSON.stringify(b)}`);
      assert(Math.abs(b.price_variance_amount - P3.selisih) < 0.01, `selisih ${b.price_variance_amount}`);
      if (!(await r.tid("vb-price-variance").isVisible().catch(() => false))) await bukaTagihan(r, K.bill3);
      const v = await r.text("vb-price-variance");
      await sorot(r.tid("vb-price-variance"));
      await r.shot("admin-po3-terposting-selisih");
      await lepas(r.tid("vb-price-variance"));
      return `disetujui ${b.approved_by} · ${v} · terposting ke akun selisih: ${b.price_variance_posted}`;
    });

  if (langkah(28)) await r.step(28, "Buku", "Cek buku: jurnal tagihan PO-3 (selisih harga)",
    `GR/IR 2-1150 (D) ${rp(P3.dppFaktur)} (= ${rp(P3.gr)} nilai PO + ${rp(P3.selisih)} selisih, karena akun selisih harga belum dipetakan) + PPN Masukan 1-1500 (D) ${rp(P3.ppn)} / Hutang Usaha 2-1100 (K) ${rp(P3.total)}; sisa GR/IR PO-3 = −${rp(P3.selisih)} (bersaldo debit)`, async () => {
      const je = jurnalDari([K.bill3.id]).find((j) => j.source_type === "vendor_bill");
      assert(je, "jurnal tagihan PO-3 tidak ada");
      K.je_bill3 = je.number; simpan();
      const peta = (je.lines || []).some((l) => !["2-1150", "1-1500", "2-1100"].includes(l.account_code));
      let txt;
      if (peta) {   // akun selisih harga SUDAH dipetakan (lingkungan lain): GR/IR = nilai PO, selisih ke akun petaan
        txt = cekJurnal(je, [["2-1150", "D", P3.gr], ["1-1500", "D", P3.ppn], ["2-1100", "K", P3.total]]);
        r.note("akun selisih harga pembelian terpetakan — selisih dijurnal ke akun itu, GR/IR PO-3 kembali 0");
      } else txt = cekJurnal(je, [["2-1150", "D", P3.dppFaktur], ["1-1500", "D", P3.ppn], ["2-1100", "K", P3.total]]);
      const s = sisaGrir(K.po3.id);
      assert(Math.abs(s - (peta ? 0 : -P3.selisih)) < 0.01, `sisa GR/IR PO-3 ${s}`);
      return `${txt} · sisa GR/IR PO-3 ${rp(s)}`;
    });

  // ═══ Finance: GR/IR, hutang per pemasok, Jejak Dokumen ═════════════════════════════════════════════════════════════
  if (langkah(29)) await r.step(29, "Finance", `Login akun peserta → Keuangan › Hutang › tab GR/IR → centang *Tampilkan yang sudah nol* → ketik nomor PO-2, lalu nomor PO-3, lalu nomor PO-1`,
    `PO-2: diterima ${rp(P2.gr)} = ditagih ${rp(P2.gr)}, sisa Rp 0; PO-3: diterima ${rp(P3.gr)}, ditagih ${rp(P3.dppFaktur)}, sisa −${rp(P3.selisih)} "termasuk selisih harga"; PO-1 (batal) tidak ada; peringatan akun "Selisih harga pembelian" belum diatur`, async () => {
      await r.login(FINANCE);
      await buka(r, "accounts-payable", "gr-ir", "keuangan");
      await r.tid("grir-view").waitFor();
      await r.tid("grir-show-zero").check();
      const cari = async (p) => { await r.tid("grir-search").fill(p.number); await r.idle(900); };
      await cari(K.po2);
      await r.tid(`grir-row-${K.po2.id}`).waitFor({ timeout: 15000 });
      const b2 = num(await r.text(`grir-balance-${K.po2.id}`));
      assert(b2 === 0, `sisa PO-2 ${b2}`);
      await sorot(r.tid(`grir-row-${K.po2.id}`));
      await r.shot("finance-grir-po2");
      await lepas(r.tid(`grir-row-${K.po2.id}`));
      await cari(K.po3);
      await r.tid(`grir-row-${K.po3.id}`).waitFor({ timeout: 15000 });
      const b3 = await r.text(`grir-balance-${K.po3.id}`);
      const m3 = b3.match(/(-|−)?\s?Rp\s?[\d.]+/);   // sel memuat juga "termasuk selisih harga Rp …"
      assert(m3 && num(m3[0]) === -P3.selisih, `sisa PO-3 ${b3}`);
      assert(/selisih harga/i.test(b3), `keterangan selisih harga tidak tampil: ${b3}`);
      const miss = await r.tid("grir-mapping-missing").isVisible().catch(() => false);
      await sorot(r.tid(`grir-row-${K.po3.id}`));
      await r.shot("finance-grir-po3", { full: true });
      await lepas(r.tid(`grir-row-${K.po3.id}`));
      await cari(K.po1);
      assert(await r.tid(`grir-row-${K.po1.id}`).count() === 0, "PO-1 batal muncul di GR/IR");
      return `PO-2 sisa ${rp(b2)} · PO-3 sisa ${b3} · PO-1 tidak ada · peringatan pemetaan ${miss ? "tampil" : "tidak tampil"}`;
    });

  if (langkah(30)) await r.step(30, "Finance", `Keuangan › Hutang › Tagihan → ketik nomor faktur pemasok materi ini (${FAKTUR2})`,
    `Tagihan PO-2 ${rp(P2.total)} dan PO-3 ${rp(P3.total)} Terposting (draf lebih tagih Dibatalkan) → hutang pemasok bertambah ${rp(P2.total + P3.total)} (peserta baru: total ${rp(P2.total + P3.total)}); kartu "Cocok dengan saldo akun hutang"`, async () => {
      await layarTagihan(r);
      await r.tid("vb-search").fill(FAKTUR2);
      await r.idle(1200);
      for (const b of [K.bill2, K.bill3]) await r.tid(`vb-row-${b.id}`).waitFor({ timeout: 15000 });
      const out = mongo(`return db.vendor_bills.aggregate([{$match:{supplier_id:"${K.sup}",status:{$in:["posted","paid"]}}},{$group:{_id:null,n:{$sum:1},sisa:{$sum:"$outstanding"},tot:{$sum:"$grand_total"}}}]).toArray()[0]||{n:0,sisa:0}`);
      const awal = K.hutangAwal || { n: 0, sisa: 0 };
      assert(out.n === awal.n + 2 && Math.abs(out.sisa - awal.sisa - (P2.total + P3.total)) < 0.01,
        `hutang pemasok ${JSON.stringify(out)} (awal ${JSON.stringify(awal)})`);
      const rec = await r.text("vb-rec-unexplained").catch(() => "");
      await sorot(r.tid(`vb-row-${K.bill2.id}`)); await sorot(r.tid(`vb-row-${K.bill3.id}`));
      await r.shot("finance-hutang-pemasok");
      await lepas(r.tid(`vb-row-${K.bill2.id}`)); await lepas(r.tid(`vb-row-${K.bill3.id}`));
      return `hutang ${PEMASOK}: ${out.n} tagihan terposting · sisa ${rp(out.sisa)} (awal ${rp(awal.sisa)} + ${rp(P2.total + P3.total)}) · ${rec}`;
    });

  if (langkah(31)) await r.step(31, "Finance", "Pusat Dokumen › tab Jejak Dokumen → ketik nomor PO-2 → klik hasilnya",
    "Rantai PO-2 (v2) → tugas terima → tagihan (yang dibatalkan dan yang terposting) → jurnal penerimaan & jurnal tagihan", async () => {
      await buka(r, "document-center", "doc-trace");
      await r.tid("doc-trace-view").waitFor();
      await r.tid("trace-search-input").fill(K.po2.number);
      await r.tid(`trace-result-${K.po2.id}`).click();
      await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
      await r.tid("trace-graph").waitFor();
      await r.idle(1500);
      const g = await r.text("trace-graph");
      const harus = [K.po2.number, K.bill2.number, K.je_gr2, K.je_bill2].filter(Boolean);
      const hilang = harus.filter((x) => !g.includes(x));
      await r.shot("finance-jejak-po2", { full: true });
      await r.page.evaluate(() => {
        const el = document.querySelector('[data-testid="trace-graph"]');
        for (const e of [el, ...el.querySelectorAll("*")]) if (e.scrollWidth > e.clientWidth + 10) e.scrollLeft = e.scrollWidth;
      });
      await r.idle(300);
      await r.shot("finance-jejak-po2-kanan", { locator: r.tid("trace-graph") });
      assert(!hilang.length, `jejak tidak memuat: ${hilang.join(", ")}`);
      return `rantai memuat ${harus.join(" → ")}${g.includes(K.draf2.number) ? ` (+ draf batal ${K.draf2.number})` : ""}`;
    });

  if (tolak.size) r.note(`Penolakan izin yang tercatat: ${[...tolak].join(" · ")}`);
  await r.finish();
})();
