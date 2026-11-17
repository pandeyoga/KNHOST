// Pembantu bersama bagian D — ORIENTASI, BUKU BESAR & JEJAK DOKUMEN, LAPORAN & TUTUP BUKU (F01, F16–F18).
// Hanya MEMBACA layar/DB. Cek buku dihitung LANGSUNG dari `journal_entries` (bukan dari layanan laporan aplikasi),
// supaya angka layar dibandingkan dengan sumber yang independen.
const { assert, mongo, num, sleep } = require("./lib");

const KSC = "ent_ksc";

/** Klik menu samping seperti peserta: buka grup bila butirnya belum terlihat, klik butir, lalu (opsional) tab hub. */
async function menu(r, group, item, tab) {
  const it = r.tid(`nav-${item}`);
  if (!(await it.isVisible().catch(() => false))) {
    await r.tid(`nav-group-toggle-${group}`).click();
    await it.waitFor({ state: "visible" });
  }
  await it.click();
  await r.idle();
  if (tab) {
    await r.tid(`hub-tab-${tab}`).click();
    await r.idle();
  }
}

/** Saldo (debit − kredit) per akun dari jurnal terposting PT, opsional sampai/antara tanggal (YYYY-MM-DD). */
function saldoAkun(codes, { entity = KSC, start = "", end = "", tanpaPenutup = false } = {}) {
  const m = { entity_id: entity, status: { $ne: "void" } };
  if (tanpaPenutup) m.source_type = { $ne: "closing" };
  const date = {};
  if (start) date.$gte = start;
  if (end) date.$lte = end + "T23:59:59";
  if (start || end) m.date = date;
  const match = codes ? { "lines.account_code": { $in: codes } } : {};
  return mongo(`const out={}; db.journal_entries.aggregate([{$match:${JSON.stringify(m)}},{$unwind:"$lines"},
    {$match:${JSON.stringify(match)}},{$group:{_id:"$lines.account_code",d:{$sum:"$lines.debit"},c:{$sum:"$lines.credit"}}}])
    .forEach(x=>{out[x._id]=Math.round((x.d-x.c)*100)/100}); return out;`);
}

/** Ringkasan laba-rugi dari jurnal (awalan kode: 4 = pendapatan, 5 = HPP/beban pokok, 6 = beban operasional). */
function labaRugiDb(start, end, entity = KSC) {
  const s = saldoAkun(null, { entity, start, end, tanpaPenutup: true });
  const sum = (pre) => Object.entries(s).filter(([k]) => k.startsWith(pre)).reduce((a, [, v]) => a + v, 0);
  const revenue = -sum("4"), cogs = sum("5"), opex = sum("6");
  const r2 = (x) => Math.round(x * 100) / 100;
  return { revenue: r2(revenue), cogs: r2(cogs), opex: r2(opex), gross: r2(revenue - cogs), net: r2(revenue - cogs - opex), saldo: s };
}

/** Posisi neraca dari jurnal sampai tanggal (termasuk jurnal penutup): aset, kewajiban, ekuitas, laba berjalan. */
function neracaDb(end, entity = KSC) {
  const s = saldoAkun(null, { entity, end });
  const sum = (pre) => Object.entries(s).filter(([k]) => k.startsWith(pre)).reduce((a, [, v]) => a + v, 0);
  const r2 = (x) => Math.round(x * 100) / 100;
  const aset = sum("1"), kewajiban = -sum("2"), ekuitas = -sum("3"), laba = -(sum("4") + sum("5") + sum("6"));
  return { aset: r2(aset), kewajiban: r2(kewajiban), ekuitas: r2(ekuitas), laba_berjalan: r2(laba),
    selisih: r2(aset - kewajiban - ekuitas - laba), saldo: s };
}

/** Uang dari layar ("Rp 1.234.567" / "−Rp 5" / "(Rp 5)") → angka. Mengambil token rupiah TERAKHIR di teks supaya
 *  tanda hubung pada label (mis. "Laba-Rugi Rp 5") tidak terbaca sebagai minus. */
function uang(s) {
  const t = String(s || "");
  const all = [...t.matchAll(/([−-]\s*)?(\()?Rp\s*([\d.]+)(,\d+)?/g)];
  if (!all.length) return num(t);
  const m = all[all.length - 1];
  const v = Number(m[3].replace(/\./g, "") + (m[4] ? "." + m[4].slice(1) : ""));
  return (m[1] || m[2]) ? -v : v;
}

/** Bandingkan nilai layar ↔ buku. Angka berjalan (agent/peserta lain memposting) → ulang baca sampai cocok. */
async function cocokBerulang(fn, { kali = 4, jeda = 1500, muatUlang } = {}) {
  let last = "";
  for (let i = 0; i < kali; i++) {
    const res = await fn();
    if (res === true || (res && res.ok)) return res.info || "";
    last = res && res.info ? res.info : String(res);
    if (muatUlang) await muatUlang();
    await sleep(jeda);
  }
  throw new Error(`angka layar ≠ buku setelah ${kali}× baca ulang: ${last}`);
}

const dekat = (a, b, tol = 1) => Math.abs(Math.round(Number(a)) - Math.round(Number(b))) <= tol;

function jurnal(nomor) {
  const je = mongo(`return db.journal_entries.findOne({number:${JSON.stringify(nomor)},entity_id:"${KSC}"},{_id:0})`);
  assert(je, `jurnal ${nomor} tidak ada di buku`);
  return je;
}

function seimbang(je) {
  const d = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0);
  const k = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
  assert(Math.abs(d - k) < 0.01, `jurnal ${je.number} tidak seimbang D ${d} ≠ K ${k}`);
  return Math.round(d * 100) / 100;
}

function sisi(je, kode, s) {
  return Math.round(je.lines.filter((l) => l.account_code === kode)
    .reduce((a, l) => a + Number((s === "D" ? l.debit : l.credit) || 0), 0) * 100) / 100;
}

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];

/** Pilih opsi KNSelect seperti peserta: klik kotak pilihan → (ketik di *Cari…* bila ada) → klik opsinya. */
async function pilih(r, testId, value, cari = "") {
  await r.tid(testId).click();
  const search = r.tid(`${testId}-search`);
  if (cari && await search.isVisible().catch(() => false)) await search.fill(cari);
  await r.tid(`${testId}-option-${value}`).click();
  await r.idle(400);
}

/** Hapus tangkapan layar lama di folder hasil skenario (nomor gambar dipakai panduan — sisa run gagal mengacaukannya). */
function bersihkanGambar(r) {
  const fs = require("fs");
  const path = require("path");
  for (const f of fs.readdirSync(r.dir)) if (/\.png$/.test(f)) fs.unlinkSync(path.join(r.dir, f));
}

/** Sorot elemen yang diklik/dibaca peserta (garis merah) sebelum dipotret — dilepas lagi oleh `potret`. */
async function sorot(...locs) {
  for (const loc of locs) {
    const l = loc.first();
    if (!(await l.count().catch(() => 0))) continue;
    await l.evaluate((e) => { e.style.outline = "3px solid #DC2626"; e.style.outlineOffset = "2px"; e.dataset.knSorot = "1"; })
      .catch(() => {});
  }
}

async function lepasSorot(r) {
  await r.page.evaluate(() => document.querySelectorAll("[data-kn-sorot]").forEach((e) => {
    e.style.outline = ""; e.style.outlineOffset = ""; delete e.dataset.knSorot;
  })).catch(() => {});
}

/** Potret dengan sorotan: `potret(r, "nama", [locator…], opsi r.shot)`. */
async function potret(r, nama, locs = [], opts = {}) {
  await sorot(...locs);
  try { return await r.shot(nama, opts); } finally { await lepasSorot(r); }
}

module.exports = { KSC, sorot, lepasSorot, potret, bersihkanGambar, menu, saldoAkun, labaRugiDb, neracaDb, uang, cocokBerulang, dekat, jurnal, seimbang, sisi, BULAN, pilih };
