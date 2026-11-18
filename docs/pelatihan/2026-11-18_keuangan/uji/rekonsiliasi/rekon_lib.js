// Pembantu uji jalan REKONSILIASI BANK lanjutan (R1–R9) — rekening koran EXCEL per peserta.
//
// Data buku peserta: `seed_pelatihan_keuangan_kn.py --hanya a_dasar:akun,a_dasar:mitra,g_rekon` (kartu `g_rekon:*`).
// Berkas Excel: `buat_mutasi_bank_latihan.py --keluar <KN_MUTASI>` → `<KN_MUTASI>/peserta_NN/R1_kode_bayar_NN.xlsx` …
// Skenario & hasil yang harus terlihat: docs/pelatihan/2026-11-18_keuangan/rekonsiliasi/SKENARIO_UJI_REKONSILIASI.md.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R1_kode_bayar.js
// Rekening BCA Operasional KSC dipakai bersama semua peserta: uji hanya menilai baris "LATIHAN NN" milik peserta ini.
const fs = require("fs");
const path = require("path");
const { kartu, mongo, assert, rp, api, peserta, akunPeserta } = require("../lib.js");
const kb = require("../kasbank_lib.js");

const MUTASI = process.env.KN_MUTASI || path.join(__dirname, "..", "..", "rekonsiliasi", "mutasi");
const BCA = "BCA Operasional KSC";
const TEMPLATE = "BCA — Rekening Koran (CSV)";

/** Konteks satu peserta: nomor, akun, kartu `g_rekon:*`, manifest berkas Excel, rekening BCA. */
async function siapkan(r, def = "85") {
  const NO = peserta(def);
  const k = kartu(NO);
  const g = (kunci) => {
    const v = k[`g_rekon:${kunci}`];
    assert(v, `Kartu peserta ${NO} belum punya g_rekon:${kunci} — jalankan seed --hanya a_dasar:akun,a_dasar:mitra,g_rekon`);
    return v;
  };
  const dir = path.join(MUTASI, `peserta_${NO}`);
  const mf = path.join(dir, `manifest_${NO}.json`);
  assert(fs.existsSync(mf), `Berkas Excel peserta ${NO} belum dibuat (${mf}) — jalankan buat_mutasi_bank_latihan.py`);
  const manifest = JSON.parse(fs.readFileSync(mf, "utf8"));
  const me = akunPeserta(NO);
  const bca = await kb.rekening(me, BCA);
  const ctx = {
    NO, me, k, g, bca, manifest,
    berkas: (kode) => path.join(dir, manifest.berkas[kode].berkas),
    namaBerkas: (kode) => manifest.berkas[kode].berkas,
    barisManifest: (kode) => manifest.berkas[kode].baris || [],
  };
  r.note(`Peserta ${NO} · ${me} · rekening ${bca.name} (${bca.id}) · berkas ${dir}`);
  return ctx;
}

/** Login akun peserta → Keuangan › Kas & Bank › Rekonsiliasi → pilih rekening BCA. */
async function bukaRekon(r, c, { login = true } = {}) {
  if (login) await r.login(c.me);
  await kb.menu(r, "bank-reconciliation");
  await kb.pilih(r, "recon-account-select", c.bca.id);
  await r.tid("recon-summary").waitFor();
}

/** Impor mutasi bank → Pilih berkas (Excel) → Pratinjau → Impor. Template dibiarkan "Kenali otomatis".
 *  → { pratinjau, notice }. `baris` = jumlah baris yang harus terbaca; `baru` = jumlah baris baru yang diharapkan. */
async function imporExcel(r, c, kode, { baris, baru = baris, potret = true } = {}) {
  const file = c.berkas(kode);
  const nama = c.namaBerkas(kode);
  await r.tid("recon-import-toggle").click();
  await r.tid("recon-import-panel").waitFor();
  await r.tid("recon-file-input").setInputFiles(file);
  const pilihan = await kb.tunggu(r, "recon-file-excel", nama);
  await r.tid("recon-preview-btn").click();
  const pv = await kb.tunggu(r, "recon-preview", new RegExp(`Terbaca ${baris} baris`), 30000);
  assert(pv.includes(TEMPLATE) && /dikenali otomatis/.test(pv), `pratinjau tidak memakai ${TEMPLATE} otomatis: ${pv.slice(0, 200)}`);
  assert(/lembar Mutasi Rekening, judul kolom di baris 7/.test(pv), `lembar/judul kolom: ${pv.slice(0, 200)}`);
  if (potret) await kb.shotSorot(r, `pratinjau-${kode}`, r.tid("recon-import-submit"), { locator: r.tid("recon-import-panel") });
  await r.tid("recon-import-submit").click();
  const t = await kb.tunggu(r, "recon-notice", /Impor BCA/, 30000);
  assert(new RegExp(`${baru} baris baru, ${baris - baru} dilewati`).test(t), `impor: ${t}`);
  // Kartu "Impor terakhir" ikut dimuat ulang sesudah pesan impor tampil — tunggu sampai menyebut berkas ini. Rekening
  // dipakai bersama: bila peserta lain mengimpor di sela waktu itu, kartu menyebut berkas mereka (dicatat, bukan gagal).
  const src = await kb.tunggu(r, "recon-statement-source", nama).catch(async () => kb.teks(r, "recon-statement-source"));
  if (!src.includes(nama)) r.note(`Kartu "Impor terakhir" tidak menyebut ${nama}: ${src}`);
  return { pilihan, pratinjau: pv.split("Tanggal")[0].trim(), notice: t, sumber: src };
}

/** Baris mutasi peserta menurut keterangan persis (manifest) — dari Mongo. */
function baris(c, keterangan) {
  const rows = mongo(`return db.bank_statement_lines.find({bank_account_id:${JSON.stringify(c.bca.id)},
    description:${JSON.stringify(keterangan)}},{_id:0}).sort({created_at:1}).toArray()`);
  assert(rows.length >= 1, `baris mutasi "${keterangan}" tidak ada`);
  return rows[rows.length - 1];
}

/** Kotak cari daftar mutasi = "LATIHAN NN" (rekening bersama). */
async function saring(r, c) {
  await r.tid("recon-lines-search").fill(`LATIHAN ${c.NO}`);
  await r.idle(300);
}

/** Klik [[Cocokkan otomatis]] → teks pesannya. */
async function cocokOtomatis(r) {
  await r.tid("recon-auto-match").click();
  return kb.tunggu(r, "recon-notice", /Pencocokan otomatis/, 60000);
}

const status = (r, id) => kb.teks(r, `recon-status-${id}`);
const tungguStatus = (r, id, re) => kb.tunggu(r, `recon-status-${id}`, re);

/** Kas terekonsiliasi PENUH (reconciled_amount = amount) dan tetap SATU jurnal (pencocokan tidak menerbitkan jurnal). */
function kasTerekonsiliasi(id, { jurnalTetapSatu = true } = {}) {
  const t = kb.kas(id);
  assert(t, `kas ${id} tidak ada`);
  assert(Math.abs(Number(t.reconciled_amount || 0) - Number(t.amount)) < 0.01,
    `${t.number} belum terekonsiliasi penuh (${rp(t.reconciled_amount)} dari ${rp(t.amount)})`);
  if (jurnalTetapSatu) {
    const je = kb.jurnal("cash_transaction", id);
    assert(je.length === 1, `kas ${t.number}: ${je.length} jurnal (harus tetap 1 — pencocokan tidak menerbitkan jurnal)`);
    kb.seimbang(je, `jurnal ${t.number}`);
  }
  return t;
}

/** Rekening & Saldo → kartu BCA → Mutasi: kas `ids` berstatus Rekonsiliasi "Terekonsiliasi". */
async function cekMutasiRekening(r, c, ids, nama) {
  await kb.menu(r, "bank-accounts");
  await r.tid(`bank-card-${c.bca.id}`).click();
  await r.tid("bank-ledger").waitFor();
  for (const id of ids) {
    await r.tid(`bank-recon-status-${id}`).waitFor();
    const s = await kb.teks(r, `bank-recon-status-${id}`);
    assert(s === "Terekonsiliasi", `status rekonsiliasi kas ${id}: ${s}`);
  }
  for (const id of ids) await kb.sorot(r.tid(`bank-ledger-row-${id}`));
  await r.tid(`bank-ledger-row-${ids[ids.length - 1]}`).scrollIntoViewIfNeeded();
  await r.shot(nama || "mutasi-terekonsiliasi", { locator: r.tid("bank-ledger") });
  for (const id of ids) await kb.lepas(r.tid(`bank-ledger-row-${id}`));
}

/** Sesi API peserta (cek ringkasan, dll.). */
const sesi = (c) => api(c.me);

module.exports = { MUTASI, BCA, TEMPLATE, siapkan, bukaRekon, imporExcel, baris, saring, cocokOtomatis, status,
  tungguStatus, kasTerekonsiliasi, cekMutasiRekening, sesi };
