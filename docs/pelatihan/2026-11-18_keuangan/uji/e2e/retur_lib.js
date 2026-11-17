// Pembantu bersama alur A3 — RETUR (penjualan & pembelian), PT Sukacita. Hanya membaca layar/DB; perubahan data
// dikerjakan lewat layar di berkas skenario (kecuali "persiapan" yang ditandai jelas).
const { assert, mongo, sleep } = require("../lib");
const { pilih, setuju, jurnalDari, cekJurnal, sorot, lepas, klikPotret, tungguTeks, menu } = require("../hutang_lib");

const KSC = "ent_ksc";
const GUDANG_JKT = "Jakarta · Gudang Sukacita";
const rpBuku = (n) => "Rp " + Number(n || 0).toLocaleString("id-ID", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const r2 = (n) => Math.round(Number(n || 0) * 100) / 100;

/** Menu samping Retur (grup Penjualan) → tab hub. */
async function bukaRetur(r, tab = "returns", nama = "") {
  const nav = r.tid("nav-returns-hub");
  if (!(await nav.isVisible().catch(() => false))) {
    await r.tid("nav-group-toggle-penjualan").click();
    await nav.waitFor({ timeout: 8000 });
  }
  if (nama) await klikPotret(r, nav, `${nama}-menu`); else await nav.click();
  await r.idle(500);
  const t = r.tid(`hub-tab-${tab}`);
  if (await t.isVisible().catch(() => false)) {
    if (nama) await klikPotret(r, t, `${nama}-tab`); else await t.click();
    await r.idle(500);
  }
}

/** Daftar Retur Pelanggan → cari nomor → buka detail. */
async function bukaDetailRetur(r, ret, nama = "") {
  await r.tid("sales-returns-view").waitFor({ timeout: 15000 });
  await r.tid("return-search").fill(ret.number);
  await r.idle(900);
  const btn = r.tid(`view-return-${ret.id}`);
  await btn.waitFor({ timeout: 15000 });
  if (nama) await klikPotret(r, btn, nama); else await btn.click();
  await r.tid("return-detail-view").waitFor({ timeout: 15000 });
  await r.idle(600);
}

/** Retur pelanggan terakhir (tidak batal) atas SO. */
function returSo(soId) {
  return mongo(`return db.sales_returns.find({order_id:"${soId}",status:{$nin:["cancelled"]}},{_id:0})
    .sort({created_at:-1}).limit(1).toArray()[0]||null`);
}
function returById(id) { return mongo(`return db.sales_returns.findOne({id:"${id}"},{_id:0})`); }

function soDoc(soId) {
  return mongo(`return db.sales_orders.findOne({id:"${soId}"},{_id:0,id:1,number:1,customer_id:1,customer_name:1,grand_total:1,
    total_amount:1,payments:1,payment_status:1,status:1,extra_billing_lines:1,items:1})`);
}
/** Sisa tagihan SO (grand total + nota debit − Σ payments). */
function sisaSo(soId) {
  const o = soDoc(soId);
  const gt = Number(o.grand_total ?? o.total_amount ?? 0)
    + (o.extra_billing_lines || []).reduce((s, x) => s + Number((x && x.gross) || 0), 0);
  return r2(gt - (o.payments || []).reduce((s, p) => s + Number(p.amount || 0), 0));
}

function notaKredit(retId) {
  return mongo(`return db.credit_notes.find({return_id:"${retId}",status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).toArray()`) || [];
}
function saldoKredit(custId) {
  // Nominal ledger sudah bertanda (terbit +, pakai −) — sama dengan `store_credit_service.balance`.
  const rows = mongo(`return db.store_credit_ledger.find({customer_id:"${custId}",entity_id:"${KSC}",status:{$ne:"void"}},{_id:0,amount:1}).toArray()`) || [];
  return r2(rows.reduce((s, x) => s + Number(x.amount || 0), 0));
}
function spk(id) { return mongo(`return db.inspections.findOne({id:"${id}"},{_id:0})`); }
function akunKas(nama) { return mongo(`return db.bank_accounts.findOne({entity_id:"${KSC}",name:${JSON.stringify(nama)}},{_id:0})`); }

/** Ringkas jurnal untuk catatan: "JE-… [kode D/K nominal …]". */
function ringkasJurnal(je) {
  return `${je.number} [` + je.lines.map((l) => `${l.account_code} ${Number(l.debit) ? "D " + r2(l.debit) : "K " + r2(l.credit)}`).join(" · ") + "]";
}

/** Tunggu kondisi DB (polling) — layar menulis lewat API, DB dibaca untuk cek buku. */
async function tunggu(fn, pesan, timeout = 20000) {
  const t0 = Date.now();
  let v;
  while (Date.now() - t0 < timeout) {
    v = fn();
    if (v) return v;
    await sleep(500);
  }
  throw new Error(pesan);
}

/** Satu langkah `Run.step` yang DIULANG SEKALI bila gagal — lingkungan dev bersama memuat ulang halaman saat kode
 *  layar berubah (agen lain menyalin berkas). `fn(ulang)`: saat `ulang=true` langkah wajib memeriksa DB dulu dan
 *  melewati aksi yang sudah terjadi (tidak boleh menggandakan transaksi). */
async function langkah(r, no, role, action, expect, fn) {
  return r.step(no, role, action, expect, async () => {
    try { return await fn(false); } catch (e) {
      r.note(`${no}: percobaan pertama gagal (${String(e && e.message || e).split("\n")[0].slice(0, 160)}) — diulang sekali`);
      await r.page.keyboard.press("Escape").catch(() => {});
      await sleep(4000);
      const out = await fn(true);
      return `(diulang) ${out === undefined ? "" : out}`;
    }
  });
}

/** Klik opsi KNSelect yang labelnya MEMUAT teks (regex) — untuk label dinamis. */
async function pilihRe(r, testId, re) {
  await r.tid(testId).click();
  const opt = r.page.getByRole("option", { name: re }).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(300);
}

/** KNSelect berpencarian: buka → ketik di kotak cari (bila ada) → klik opsi ber-nilai `nilai` (testid `<id>-option-<nilai>`).
 *  Daftar panjang (pemasok, PO) tidak merender semua opsi, jadi opsi dicari dulu seperti pengguna. */
async function pilihCari(r, testId, teks, nilai) {
  // Pemicu kadang tidak membuka daftar (pop-up form masih memuat data / fokus pindah) → coba sampai 3 kali.
  for (let i = 0; i < 3; i++) {
    await r.tid(testId).click();
    const buka = await r.tid(`${testId}-option-${nilai}`).or(r.tid(`${testId}-search`)).first()
      .waitFor({ timeout: 3000 }).then(() => true).catch(() => false);
    if (buka) break;
    await sleep(1500);   // tanpa Esc: Esc menutup pop-up form
    if (await r.tid(`${testId}-search`).isVisible().catch(() => false)) break;
  }
  const cari = r.tid(`${testId}-search`);
  if (await cari.count()) { await cari.fill(teks); await sleep(400); }
  const opt = r.tid(`${testId}-option-${nilai}`);
  await opt.waitFor({ timeout: 10000 });
  await opt.click();
  await sleep(300);
}

module.exports = { pilihCari, langkah, KSC, GUDANG_JKT, rpBuku, r2, bukaRetur, bukaDetailRetur, returSo, returById, soDoc, sisaSo, notaKredit,
  saldoKredit, spk, akunKas, ringkasJurnal, tunggu, pilihRe, pilih, setuju, jurnalDari, cekJurnal, sorot, lepas, klikPotret,
  tungguTeks, menu };
