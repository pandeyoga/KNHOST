// Pembantu uji VARIASI isian (pelatihan keuangan 18 Nov): satu kasus = satu langkah `Run.step` + satu baris tabel
// `src/variasi_piutang_kas.json` (layar · isian · masukan · harap · hasil · catatan).
//
//   const v = require("./vlib");
//   const t = v.tabel("V1");                       // kumpulan baris tabel skenario ini
//   await v.kasus(r, t, { layar, isian, masukan, harap, hasil: "diperbaiki", catatan }, async () => { … });
//   t.simpan();                                    // → hasil/V1/tabel.json (digabung `gabung_tabel.js`)
const fs = require("fs");
const path = require("path");
const { sleep } = require("../lib");

const OUT = process.env.KN_OUT || path.join(__dirname, "..", "hasil");

function tabel(kode) {
  const rows = [];
  return {
    rows,
    simpan() {
      const dir = path.join(OUT, kode);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "tabel.json"), JSON.stringify(rows, null, 1));
    },
  };
}

let nomor = 0;
/** Satu kasus variasi: langkah uji + baris tabel. `meta.hasil` = lulus | diperbaiki | keputusan (sebelum uji).
 *  Gagal saat uji → baris tabel bertanda `uji: "gagal"` + pesan galatnya (tidak disembunyikan). */
async function kasus(r, t, meta, fn) {
  const no = ++nomor;
  const ok = await r.step(no, meta.peran || "Finance", `${meta.layar} · ${meta.isian}: ${meta.masukan}`, meta.harap, fn);
  const row = r.steps[r.steps.length - 1];
  t.rows.push({ layar: meta.layar, isian: meta.isian, masukan: meta.masukan, harap: meta.harap,
    hasil: meta.hasil || "lulus", catatan: meta.catatan || "", uji: ok ? "lulus" : "gagal", bukti: row.info || "" });
  return ok;
}

/** Kosongkan kotak lalu ketik huruf demi huruf seperti peserta (`tempel=true` → isi sekaligus seperti Ctrl+V). */
async function ketik(r, testId, teks, { tempel = false } = {}) {
  const box = r.tid(testId).first();
  await box.click();
  await box.press("Control+A");
  await box.press("Delete");
  if (tempel) await box.fill(teks);
  else await r.page.keyboard.type(teks, { delay: 15 });
  await sleep(150);
}

/** innerText rapi (NBSP → spasi) atau "-" bila elemen tidak ada. */
async function teksAtau(r, testId) {
  const el = r.tid(testId);
  if (!(await el.count())) return "-";
  return (await el.first().innerText()).replace(/\s+/g, " ").trim();
}

/** Bilangan dari "Rp 3.374.123" (format Indonesia). */
const angka = (s) => Number(String(s || "").replace(/[^\d,-]/g, "").replace(",", ".")) || 0;
const r2 = (v) => Math.round(Number(v || 0) * 100) / 100;

module.exports = { tabel, kasus, ketik, teksAtau, angka, r2 };

const BULAN = ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober",
  "november", "desember"];
/** Pilih tanggal ISO di KNDatePicker `testId` lewat kalender (tombol bulan berikut/sebelum, lalu klik harinya). */
async function pilihTanggal(r, testId, iso) {
  const [y, m, d] = iso.split("-").map(Number);
  await r.tid(testId).first().click();
  const pop = r.tid(`${testId}-popover`);
  await pop.waitFor();
  for (let i = 0; i < 60; i++) {
    const cap = (await pop.locator('[aria-live="polite"]').first().innerText()).trim().toLowerCase();
    const [bn, th] = cap.split(/\s+/);
    const diff = (y - Number(th)) * 12 + (m - (BULAN.indexOf(bn) + 1));
    if (diff === 0) break;
    await pop.locator(`button[name="${diff > 0 ? "next-month" : "previous-month"}"]`).click();
    await sleep(80);
  }
  await pop.locator('button[name="day"]:not(.day-outside)').filter({ hasText: new RegExp(`^${d}$`) }).first().click();
  await pop.waitFor({ state: "hidden" });
}
module.exports.pilihTanggal = pilihTanggal;
