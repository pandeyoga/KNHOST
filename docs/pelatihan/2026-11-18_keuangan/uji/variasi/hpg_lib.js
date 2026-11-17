// Pembantu uji VARIASI isian bagian HUTANG · PAJAK · GAJI · BUKU (V5–V8, pelatihan keuangan 18 Nov).
// (Berkas `vlib.js` di folder ini milik uji variasi Piutang/Kas V1–V4 — sengaja terpisah.)
// Mengetik seperti peserta (huruf demi huruf), memilih tanggal di kalender, membaca konfirmasi lalu membatalkan,
// dan menulis tabel kasus `src/variasi_hutang_pajak_gaji.json` (layar · isian · masukan · harap · hasil · catatan).
const fs = require("fs");
const path = require("path");
const { sleep, mongo } = require("../lib");

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];

/** Kosongkan isian lalu KETIK teks huruf demi huruf (bukan tempel) — sama dengan peserta di papan ketik. */
async function ketik(r, testId, text, { tempel = false } = {}) {
  const inp = r.tid(testId).first();
  await inp.click();
  await inp.press("Control+A");
  await inp.press("Backspace");
  await inp.fill("");
  if (tempel) await inp.fill(text);
  else if (text) await inp.pressSequentially(text, { delay: 15 });
  await sleep(250);
  return inp.inputValue();
}

/** Pilih tanggal ISO (YYYY-MM-DD) di KNDatePicker ber-testid: buka kalender, geser bulan, klik tanggalnya. */
async function pilihTanggal(r, testId, iso) {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  await r.tid(testId).click();
  const pop = r.tid(`${testId}-popover`);
  await pop.waitFor({ timeout: 8000 });
  for (let i = 0; i < 36; i++) {
    const cap = (await pop.locator('[aria-live="polite"]').first().innerText()).trim();
    const [nm, ty] = cap.split(/\s+/);
    const cur = Number(ty) * 12 + BULAN.indexOf(nm);
    const want = y * 12 + (m - 1);
    if (cur === want) break;
    await pop.locator(`button[name="${cur < want ? "next-month" : "previous-month"}"]`).click();
    await sleep(120);
  }
  const day = pop.locator('button[name="day"]:not(.day-outside)').filter({ hasText: new RegExp(`^${d}$`) }).first();
  if (await day.isDisabled()) throw new Error(`tanggal ${iso} tidak bisa dipilih (dikunci kalender)`);
  await day.click();
  await sleep(250);
}

/** Klik tombol kirim; bila dialog konfirmasi (askConfirm `<prefix>`) muncul → kembalikan teksnya lalu [Batal]. */
async function intipKonfirmasi(r, submitId, prefix, { batal = true } = {}) {
  await r.tid(submitId).click();
  const dlg = r.tid(`${prefix}-message`);
  await dlg.waitFor({ timeout: 6000 });
  const msg = (await dlg.innerText()).replace(/\s+/g, " ").trim();
  if (batal) {
    await r.tid(`${prefix}-cancel`).click();
    await r.tid(`${prefix}-message`).waitFor({ state: "detached", timeout: 6000 }).catch(() => {});
  }
  return msg;
}

/** Teks rupiah layar (format id-ID tanpa sen) dari angka. */
const rpLayar = (n) => "Rp " + Math.round(Number(n || 0)).toLocaleString("id-ID");

/** Tabel kasus variasi → `src/variasi_hutang_pajak_gaji.json` (digabung per uji; baris lama uji yang sama diganti). */
const TABEL = path.join(__dirname, "..", "..", "src", "variasi_hutang_pajak_gaji.json");
class Tabel {
  constructor(kode) { this.kode = kode; this.rows = []; }
  add(row) { this.rows.push({ uji: this.kode, ...row }); }
  simpan() {
    let all = [];
    try { all = JSON.parse(fs.readFileSync(TABEL, "utf8")); } catch (_) { all = []; }
    all = all.filter((x) => x.uji !== this.kode).concat(this.rows);
    fs.writeFileSync(TABEL, JSON.stringify(all, null, 2) + "\n");
  }
}

/** Jurnal tidak-void dari sumber-sumber ini (urut terbit). */
function jurnalSumber(ids) {
  return mongo(`return db.journal_entries.find({source_id:{$in:${JSON.stringify(ids.filter(Boolean))}},status:{$ne:"void"}},{_id:0})
    .sort({created_at:1}).toArray()`) || [];
}

module.exports = { ketik, pilihTanggal, intipKonfirmasi, rpLayar, Tabel, jurnalSumber, BULAN };
