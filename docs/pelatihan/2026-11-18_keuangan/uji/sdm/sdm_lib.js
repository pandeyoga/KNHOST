// Pembantu bersama skenario SDM & GAJI (K09, H01–H04, A4) — keputusan pemilik K-SDM-01 (17 Nov 2026): Finance memegang SDM.
// Isian per peserta = `backend/scripts/latih_keuangan/f_sdm.py` (`data_karyawan`) — Kartu Peserta "f_sdm:karyawan_baru".
// Masa gaji latihan: Oktober 2026, proses SUSULAN per peserta (gaji November baru bisa dibayar 30 Nov — lihat f_sdm.py).
const { assert, kartu, mongo, sleep } = require("../lib");
const hl = require("../hutang_lib");

const MASA = "2026-10";
const MASA_LABEL = "Oktober 2026";
const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];

/** Isian per peserta (cermin `f_sdm.data_karyawan`); kartu peserta dipakai bila ada. */
function dataKaryawan(no) {
  const n = Number(no);
  const kode = String(no).padStart(2, "0");
  const dasar = {
    nama: `Latihan ${kode} · Andi Pratama`, nik: `32730115089${String(n).padStart(5, "0")}`, tanggal_masuk: "2026-10-01",
    ptkp: "K/1", npwp: `09.254.294.3-4${String(n % 100).padStart(2, "0")}.000`, bank: "BCA",
    rekening: `88000${String(n).padStart(5, "0")}`, atas_nama: "Andi Pratama", gaji_pokok: 7500000,
    tunjangan: "Tunjangan transport", tunjangan_nominal: 500000, masa_gaji: MASA, masukan: "Rapel", masukan_nominal: 8000000,
    lembur_tanggal: "2026-11-16", lembur_jam: 2, libur_latihan: `2026-12-${String(10 + (n % 15)).padStart(2, "0")}`,
  };
  let k = {};
  try { k = kartu(kode)["f_sdm:karyawan_baru"] || {}; } catch (_) { k = {}; }
  return { ...dasar, ...k };
}

/** Karyawan peserta di DB (dibuat H01). */
function karyawan(nama) {
  return mongo(`return db.hr_employees.findOne({name:${JSON.stringify(nama)},entity_id:"ent_ksc"},{_id:0})`);
}

/** Proses gaji susulan masa latihan yang memuat karyawan ini (terbaru, tidak batal). */
function prosesKaryawan(empId) {
  return mongo(`const s=db.hr_payslips.find({employee_id:"${empId}",period:"${MASA}"},{_id:0,run_id:1}).toArray().map(x=>x.run_id);
    return db.hr_payroll_runs.find({id:{$in:s},status:{$nin:["cancelled","void"]}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
}

/** Pilih tanggal ISO di KNDatePicker (react-day-picker 8): geser bulan sampai judulnya cocok, lalu klik hari. */
async function pilihTanggal(r, testId, iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const judul = `${BULAN[m - 1]} ${y}`;
  await r.tid(testId).click();
  const pop = r.tid(`${testId}-popover`);
  await pop.waitFor();
  for (let i = 0; i < 24; i += 1) {
    const cap = (await pop.innerText()).split("\n").find((t) => /\d{4}$/.test(t.trim())) || "";
    if (cap.trim() === judul) break;
    const [cy] = cap.trim().split(" ").slice(-1).map(Number);
    const cm = BULAN.indexOf(cap.trim().split(" ")[0]) + 1;
    const maju = cy < y || (cy === y && cm < m);
    await pop.locator(`button[name="${maju ? "next-month" : "previous-month"}"]`).click();
    await sleep(150);
  }
  await pop.locator('button[name="day"]:not(.day-outside)').filter({ hasText: new RegExp(`^${d}$`) }).first().click();
  await sleep(300);
}

/** Tunggu API hidup (server dev dimuat ulang saat berkas backend berubah — beberapa agent bekerja bersamaan). */
async function tungguApi(maks = 120000) {
  const { API } = require("../lib");
  const t0 = Date.now();
  while (Date.now() - t0 < maks) {
    try { const res = await fetch(API + "/"); if (res.ok) return; } catch (_) { /* belum hidup */ }
    await sleep(2000);
  }
}

/** Login lewat layar, diulang bila server sedang dimuat ulang. */
async function masuk(r, key, coba = 3) {
  for (let i = 1; i <= coba; i += 1) {
    await tungguApi();
    try { await r.login(key); return; } catch (e) {
      if (i === coba) throw e;
      r.note(`login ${key} diulang (${i}): ${String(e.message || e).split("\n")[0].slice(0, 80)}`);
      await sleep(4000);
    }
  }
}

/** Pilih opsi KNSelect dengan label PERSIS (mis. "K1" — bukan "TK1" yang juga memuat "K1"). */
async function pilihPersis(r, testId, label) {
  await r.tid(testId).click();
  const opt = r.page.getByRole("option", { name: label, exact: true }).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(300);
}

/** Klik "Ya" di dialog konfirmasi baku (`confirm-modal-confirm`), potret dulu bila diberi nama. */
async function konfirmasi(r, nama) {
  const b = r.tid("confirm-modal-confirm");
  await b.waitFor({ timeout: 10000 });
  const msg = await r.text("confirm-modal-message").catch(() => "");
  if (nama) await hl.klikPotret(r, b, nama);
  else await b.click();
  await r.tid("confirm-modal-confirm").waitFor({ state: "detached", timeout: 15000 }).catch(() => {});
  return msg;
}

/** Ringkas baris jurnal: "6-1000 Beban Gaji D 8.000.000 · …". */
function teksJurnal(je) {
  return (je.lines || []).map((l) => `${l.account_code} ${l.account_name || ""} ${Number(l.debit) ? "D " + Math.round(l.debit)
    : "K " + Math.round(l.credit)}`).join(" · ");
}

function rupiahTanpaRp(n) { return Math.round(Number(n || 0)).toLocaleString("id-ID"); }

module.exports = { ...hl, MASA, MASA_LABEL, dataKaryawan, karyawan, prosesKaryawan, pilihTanggal, pilihPersis, konfirmasi, masuk,
  tungguApi, teksJurnal,
  rupiahTanpaRp, assert };
