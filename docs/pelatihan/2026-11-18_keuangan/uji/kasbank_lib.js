// Pembantu uji jalan Bagian B · KAS & BANK (F07–F10). Dipakai bersama `lib.js`.
//
//   const kb = require("./kasbank_lib");
//   await kb.menu(r, "petty-cash");                // Keuangan › Kas & Bank › Kas Kecil (klik menu seperti peserta)
//   await kb.pilih(r, "ca-disburse-cashtype", "kas_kecil");
//   const je = kb.jurnal("cash_transaction", txnId); kb.seimbang(je);
const { api, mongo, assert, sleep, rp } = require("./lib.js");

const KSC = "ent_ksc";

/** Klik menu Keuangan › Kas & Bank, lalu tab hub (`bank-accounts` · `cash-management` · `bank-reconciliation` ·
 *  `petty-cash` · `cash-holdings`). Grup menu dibuka dulu bila tertutup. */
async function menu(r, tab) {
  const p = r.page;
  const item = p.getByTestId("nav-cash-bank");
  if (!(await item.isVisible().catch(() => false))) {
    await p.getByTestId("nav-group-toggle-keuangan").click();
    await item.waitFor({ state: "visible" });
  }
  await item.click();
  await r.idle();
  if (tab) {
    await p.getByTestId(`hub-tab-${tab}`).click();
    await r.idle();
  }
}

/** Menu Akuntansi & Pajak › Buku Besar › Jurnal (cari jurnal lewat kotak cari). */
async function menuJurnal(r) {
  const p = r.page;
  const item = p.getByTestId("nav-ledger");
  if (!(await item.isVisible().catch(() => false))) {
    await p.getByTestId("nav-group-toggle-akuntansi").click();
    await item.waitFor({ state: "visible" });
  }
  await item.click();
  await r.idle();
  if (await p.getByTestId("hub-tab-general-ledger").isVisible().catch(() => false)) {
    await p.getByTestId("hub-tab-general-ledger").click();
    await r.idle();
  }
  await p.getByTestId("gl-journal-search").waitFor();
}

/** Pilih opsi KNSelect (Radix / combobox) lewat testid pemicu + nilai opsi. */
async function pilih(r, testId, value) {
  await r.tid(testId).first().click();
  const opt = r.tid(`${testId}-option-${value}`);
  await opt.first().waitFor({ state: "visible" });
  await opt.first().click();
  await sleep(250);
}

/** Konfirmasi dialog baku (ConfirmHost): klik tombol `{testId}-confirm`; kembalikan teks pesannya. */
async function konfirmasi(r, testId) {
  const box = r.tid(testId);
  await box.waitFor({ state: "visible" });
  const msg = (await box.innerText()).replace(/\s+/g, " ").trim();
  await r.tid(`${testId}-confirm`).click();
  await box.waitFor({ state: "hidden" });
  return msg;
}

/** Jurnal tidak-anulir sebuah dokumen sumber (Mongo; dibaca apa adanya untuk cek buku). */
function jurnal(sourceType, sourceId) {
  return mongo(`return db.journal_entries.find({source_type:${JSON.stringify(sourceType)},source_id:${JSON.stringify(sourceId)},
    status:{$ne:"void"}},{_id:0,id:1,number:1,date:1,source_type:1,description:1,entity_id:1,
    lines:{account_code:1,account_name:1,debit:1,credit:1}}).toArray()`);
}

/** Satu jurnal wajib ada & seimbang (Σ debit = Σ kredit, dalam sen). → jurnalnya. */
function seimbang(list, label) {
  assert(Array.isArray(list) && list.length >= 1, `${label || "jurnal"} tidak ditemukan`);
  for (const je of list) {
    const d = Math.round(je.lines.reduce((s, l) => s + Number(l.debit || 0), 0) * 100);
    const c = Math.round(je.lines.reduce((s, l) => s + Number(l.credit || 0), 0) * 100);
    assert(d > 0 && d === c, `${je.number} tidak seimbang: D ${d / 100} ≠ K ${c / 100}`);
  }
  return list[0];
}

/** Baris jurnal akun `code` sisi `sisi` ("D"/"K") bernilai `amount`? */
function adaBaris(je, code, sisi, amount) {
  return je.lines.some((l) => l.account_code === code
    && Math.abs(Number(sisi === "D" ? l.debit : l.credit) - Number(amount)) < 0.01);
}

/** "KSC/JE-00012: 1-1400 Uang Muka … (D) Rp 500.000 · 1-1110 Kas Kecil (K) Rp 500.000" — untuk catatan uji. */
function teksJurnal(je) {
  const ls = je.lines.map((l) => `${l.account_code} ${l.account_name || ""} (${Number(l.debit) ? "D" : "K"}) ${rp(Number(l.debit) || Number(l.credit))}`);
  return `${je.number}: ${ls.join(" · ")}`;
}

/** Rekening PT Sukacita menurut nama (API peserta, `/bank-accounts` = saldo + mutasi tertaut). */
async function rekening(user, nama) {
  const s = await api(user);
  const rows = await s.get(`/bank-accounts?entity_id=${KSC}`, KSC);
  const a = rows.find((x) => x.name === nama);
  assert(a, `rekening ${nama} tidak ada`);
  return a;
}

/** Transaksi kas (Mongo) menurut id. */
function kas(id) {
  return mongo(`return db.cash_transactions.findOne({id:${JSON.stringify(id)}},{_id:0})`);
}

/** Teks notifikasi/elemen (spasi dirapikan). Menunggu elemen tampil. */
async function teks(r, testId, timeout = 15000) {
  const el = r.tid(testId).first();
  await el.waitFor({ state: "visible", timeout });
  return (await el.innerText()).replace(/\s+/g, " ").trim();
}

/** Tunggu elemen `testId` berisi teks yang cocok `re` (notifikasi bisa masih berisi pesan sebelumnya). → teksnya. */
async function tunggu(r, testId, re, timeout = 15000) {
  const src = re instanceof RegExp ? re.source : String(re).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  await r.page.waitForFunction(([id, s]) => {
    const el = document.querySelector(`[data-testid="${id}"]`);
    return !!el && new RegExp(s).test((el.innerText || "").replace(/\s+/g, " "));
  }, [testId, src], { timeout });
  return teks(r, testId);
}

/** innerText dengan spasi dirapikan (NBSP dari formatCurrency → spasi biasa). */
async function isi(loc) {
  return (await loc.first().innerText()).replace(/\s+/g, " ").trim();
}

/** Sorot elemen yang akan diklik peserta (garis merah) untuk tangkapan layar; `lepas` mengembalikannya. */
async function sorot(loc) {
  await loc.first().evaluate((e) => { e.dataset.knSorot = "1"; e.style.outline = "3px solid #DC2626"; e.style.outlineOffset = "2px"; });
}
async function lepas(loc) {
  try { await loc.first().evaluate((e) => { if (e.dataset.knSorot) { e.style.outline = ""; e.style.outlineOffset = ""; delete e.dataset.knSorot; } }); }
  catch (_) { /* elemen sudah hilang */ }
}
/** Tangkapan layar dengan elemen `target` disorot (dilepas lagi sesudahnya). */
async function shotSorot(r, name, target, opts = {}) {
  await target.first().scrollIntoViewIfNeeded().catch(() => {});
  await sorot(target);
  const f = await r.shot(name, opts);
  await lepas(target);
  return f;
}

/** Buku Besar › Jurnal: cari `cari`, buka jurnal `je` (dokumen dari `jurnal()`), potret rinciannya, tutup. → teks rincian. */
async function lihatJurnal(r, cari, je, name) {
  await menuJurnal(r);
  await r.tid("gl-journal-search").fill(cari);
  const row = r.tid(`gl-journal-row-${je.id}`);
  await row.waitFor({ timeout: 20000 });
  await row.click();
  const box = r.tid("gl-journal-detail");
  await box.waitFor();
  await sleep(300);
  const t = await isi(box);
  for (const l of je.lines) assert(t.includes(l.account_code), `rincian jurnal ${je.number} tanpa akun ${l.account_code}`);
  await r.shot(name, { locator: box });
  await r.tid("gl-journal-detail-close").click();
  await box.waitFor({ state: "detached" });
  return t;
}

/** Tanggal hari ini (WIB) → { iso: "2026-11-18", bca: "18/11/2026" }. */
function hariIni() {
  const iso = new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);
  const [y, m, d] = iso.split("-");
  return { iso, bca: `${d}/${m}/${y}` };
}

/** "3.308.910,00" — nominal gaya rekening koran BCA (desimal koma). */
function nominalBca(n) {
  return Number(n).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

module.exports = { KSC, menu, menuJurnal, pilih, konfirmasi, jurnal, seimbang, adaBaris, teksJurnal, rekening, kas, teks,
  tunggu, isi, hariIni, nominalBca, sorot, lepas, shotSorot, lihatJurnal };
