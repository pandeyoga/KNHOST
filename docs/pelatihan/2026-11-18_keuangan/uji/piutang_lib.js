// Pembantu bersama skenario bagian A — PIUTANG (F02–F06). Hanya membaca layar/DB; tidak mengubah data.
const fs = require("fs");
const path = require("path");
const { assert, mongo, sleep } = require("./lib");

const KSC = "ent_ksc";

/** Sorot elemen yang akan diklik (garis merah) supaya peserta melihat tombolnya di tangkapan layar. */
async function sorot(loc) {
  await loc.scrollIntoViewIfNeeded();
  await loc.evaluate((e) => { e.style.outline = "3px solid #DC2626"; e.style.outlineOffset = "2px"; });
}
async function lepas(loc) {
  try { await loc.evaluate((e) => { e.style.outline = ""; e.style.outlineOffset = ""; }); } catch (_) { /* elemen hilang */ }
}
/** Sorot → potret → lepas sorotan → klik (satu langkah "klik tombol ini"). */
async function klikSorot(r, loc, nama) {
  await sorot(loc);
  const f = await r.shot(nama);
  await lepas(loc);
  await loc.click();
  return f;
}

/** Navigasi lewat MENU seperti peserta: sidebar `nav-<navId>` (grup dibuka bila tertutup) lalu tab hub `hub-tab-<tab>`.
 *  `nama` → potret menu yang disorot sebelum diklik (sidebar, lalu tab). */
async function bukaMenu(r, navId, tab = "", { grup = "keuangan", nama = "" } = {}) {
  const nav = r.tid(`nav-${navId}`);
  if (!(await nav.isVisible().catch(() => false))) {
    await r.tid(`nav-group-toggle-${grup}`).click();
    await nav.waitFor({ timeout: 8000 });
  }
  if (nama) await klikSorot(r, nav, `${nama}-menu`); else await nav.click();
  await r.idle(500);
  if (tab) {
    const t = r.tid(`hub-tab-${tab}`);
    await t.waitFor({ timeout: 10000 });
    if (nama) await klikSorot(r, t, `${nama}-tab`); else await t.click();
    await r.idle(500);
  }
}

/** Keuangan › Piutang › Penagihan & Penerimaan (view `collection-worklist`), tunggu daftar selesai dimuat. */
async function bukaPenagihan(r, nama = "") {
  await bukaMenu(r, "ar-aging", "collection-worklist", { nama });
  await r.tid("collection-worklist").waitFor();
  await r.page.waitForFunction(() => !document.querySelector('[data-testid="collection-loading"]'), null, { timeout: 20000 });
  await r.idle(400);
}

/** Baris SO di daftar penagihan (daftar bisa panjang → gulir ke barisnya). */
async function barisSo(r, soId) {
  const row = r.tid(`collection-row-${soId}`);
  await row.waitFor({ timeout: 15000 });
  await row.scrollIntoViewIfNeeded();
  return row;
}

/** Sisa tagihan SO (grand total + nota debit − Σ payments[]), sama dengan `customer_service._order_*`. */
function sisaSo(soId) {
  const o = mongo(`return db.sales_orders.findOne({id:"${soId}"},{_id:0,grand_total:1,total_amount:1,extra_billing_lines:1,payments:1})`);
  if (!o) throw new Error(`SO ${soId} tidak ada`);
  const gt = Number(o.grand_total ?? o.total_amount ?? 0)
    + (o.extra_billing_lines || []).reduce((s, x) => s + Number((x && x.gross) || 0), 0);
  const paid = (o.payments || []).reduce((s, p) => s + Number(p.amount || 0), 0);
  return Math.round((gt - paid) * 100) / 100;
}

/** Kwitansi terbaru (tidak batal) yang dialokasikan ke SO / milik pelanggan. */
function kwitansiTerakhir(soId) {
  return mongo(`return db.ar_receipts.find({"allocations.order_id":"${soId}",status:{$ne:"void"}},{_id:0})
    .sort({created_at:-1}).limit(1).toArray()[0]||null`);
}
function kwitansiPelanggan(custId) {
  return mongo(`return db.ar_receipts.find({customer_id:"${custId}",status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
}

/** Jurnal kas kwitansi (Dr bank / Cr piutang [+ Cr uang muka]) — sumbernya transaksi kas kwitansi. */
function jurnalKwitansi(rc) {
  const ids = [rc.cash_txn_id, rc.id].filter(Boolean);
  const je = mongo(`return db.journal_entries.find({source_id:{$in:${JSON.stringify(ids)}},status:{$ne:"void"}},{_id:0})
    .sort({created_at:1}).toArray()`);
  assert(je && je.length, `jurnal kwitansi ${rc.number} tidak ditemukan`);
  return je[0];
}

/** Jurnal seimbang + baris yang diharapkan: [[kode, "D"|"K", nominal], …] (nominal dicocokkan ±0,01). */
function cekJurnalSeimbang(je, harap) {
  const d = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0);
  const k = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
  assert(Math.abs(d - k) < 0.01, `jurnal ${je.number} tidak seimbang D ${d} ≠ K ${k}`);
  for (const [kode, sisi, nom] of harap) {
    const tot = je.lines.filter((l) => l.account_code === kode)
      .reduce((s, l) => s + Number(sisi === "D" ? l.debit : l.credit || 0), 0);
    assert(Math.abs(tot - nom) < 0.01, `jurnal ${je.number}: ${kode} ${sisi} ${tot} ≠ ${nom}`);
  }
  return je;
}

function pelangganPeserta(no) {
  return mongo(`return db.customers.findOne({name:"Latihan ${no} · Toko Kain Peserta ${no}"},{_id:0})`);
}

/** Saldo titipan (uang muka) pelanggan dari dokumen pelanggan (sumber `ar_receipt_service.get_deposit_balance`). */
function titipan(custId) {
  const c = mongo(`return db.customers.findOne({id:"${custId}"},{_id:0,deposit_balance:1})`);
  return Number((c && c.deposit_balance) || 0);
}

/** Pilih opsi KNSelect (Radix Select / combobox) berdasarkan teks label. */
async function pilih(r, testId, label) {
  await r.tid(testId).click();
  const opt = r.page.getByRole("option", { name: label }).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(300);
}

/** Hapus potret lama skenario (nomor urut berubah antar-jalan) sebelum `new Run(kode)`. */
function bersihkanHasil(kode) {
  fs.rmSync(path.join(process.env.KN_OUT || path.join(__dirname, "hasil"), kode), { recursive: true, force: true });
}

module.exports = { KSC, bersihkanHasil, sorot, lepas, klikSorot, bukaMenu, bukaPenagihan, barisSo, sisaSo, kwitansiTerakhir, kwitansiPelanggan, jurnalKwitansi,
  cekJurnalSeimbang, pelangganPeserta, titipan, pilih };
