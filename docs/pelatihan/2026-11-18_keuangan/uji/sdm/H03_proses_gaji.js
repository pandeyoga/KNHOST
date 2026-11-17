// H03 — Proses gaji (K-SDM-01, pemisahan tugas): Manajer mengesahkan masukan Rapel peserta → Finance menghitung proses
// SUSULAN Oktober 2026 (1 karyawan: karyawan baru H01) → Finance mengajukan → Manajer mengesahkan → Finance memposting
// jurnal: Beban Gaji 6-1000 (D) = Hutang Gaji 2-1600 (K) + Hutang PPh 21 2-1800 (K). BPJS tidak dihitung di proses
// susulan (hanya proses reguler) — lihat A4 untuk jurnal proses reguler.
//   node docs/pelatihan/2026-11-18_keuangan/uji/sdm/H03_proses_gaji.js      (bawaan peserta 51; KN_PESERTA=52 …)
const { Run, assert, rp, peserta, akunPeserta, mongo } = require("../lib");
const s = require("./sdm_lib");

(async () => {
  const no = peserta("51");
  const d = s.dataKaryawan(no);
  const r = await new Run("H03", "Proses gaji susulan").start();
  const emp = s.karyawan(d.nama);
  const inp = emp && mongo(`return db.hr_pay_inputs.find({employee_id:"${emp.id}",pay_period:"${s.MASA}",status:{$in:["pending","approved"]}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
  if (!emp || !inp) { r.note(`Karyawan/masukan peserta ${no} belum ada — jalankan H01 & H02 dulu`); await r.finish(); return; }
  r.note(`Peserta ${no} · ${emp.code} ${emp.name} · masukan ${inp.label} ${rp(inp.amount)} (${inp.status})`);
  let run = null;

  await r.step(1, "Manajer", "Login Manajer → SDM › Penggajian › Komponen & Masukan → *Periode bayar* Oktober 2026 → [[Sahkan]] pada masukan peserta → konfirmasi [[Sahkan]]", "Pesan \"Masukan … disahkan.\"; status Disahkan — siap dimuat proses gaji", async () => {
    await s.masuk(r, "manager");
    await r.go("hr-pay-components");
    await r.tid("payinput-period").waitFor({ timeout: 15000 });
    await s.pilihPersis(r, "payinput-period", s.MASA_LABEL);
    if (inp.status === "pending") {
      await r.tid(`payinput-approve-${inp.id}`).waitFor({ timeout: 15000 });
      await r.tid(`payinput-approve-${inp.id}`).click();
      const msg = await s.konfirmasi(r, "konfirmasi-sahkan-masukan");
      await s.tungguTeks(r, "paycomp-view", new RegExp(`Masukan ${inp.label.replace(/[()]/g, ".")} disahkan\\.`));
      r.note(`konfirmasi: ${msg}`);
    }
    const st = mongo(`return db.hr_pay_inputs.findOne({id:"${inp.id}"},{_id:0,status:1,approved_by:1})`);
    assert(st.status === "approved", `status masukan ${st.status}`);
    await r.tid(`payinput-row-${inp.id}`).scrollIntoViewIfNeeded();
    await s.sorot(r.tid(`payinput-row-${inp.id}`));
    await r.shot("masukan-disahkan");
    await s.lepas(r.tid(`payinput-row-${inp.id}`));
    // Proses susulan memuat SEMUA masukan disahkan yang belum terpakai pada masa itu → hitung segera sesudah disahkan.
    const lain = mongo(`return db.hr_pay_inputs.countDocuments({entity_id:"ent_ksc",pay_period:"${s.MASA}",status:"approved",id:{$ne:"${inp.id}"}})`);
    if (lain) r.note(`PERHATIAN: ${lain} masukan disahkan lain menunggu di ${s.MASA_LABEL} — akan ikut proses susulan berikutnya`);
    return `${await r.text(`payinput-status-${inp.id}`)} oleh ${st.approved_by || "Manajer"} · masukan lain menunggu: ${lain}`;
  });

  await r.step(2, "Finance", "Login Finance → SDM › Penggajian › Proses Gaji → *PT* Sukacita · *Periode* Oktober 2026 · *Jenis* Susulan → [[Hitung gaji]]", "Pesan \"Penggajian KSC/PAY-… (Susulan) siap (1 karyawan).\"; status Draf; slip karyawan baru: Rapel Rp 8.000.000, PPh 21 TER B", async () => {
    await s.masuk(r, akunPeserta(no));
    await s.menu(r, "hrd", "hr-payroll-hub");
    await r.tid("hub-tab-hr-payroll-runs").click();
    await r.tid("payroll-runs-view").waitFor();
    const pt = await r.text("payroll-create-entity").catch(() => "");
    if (!/Sukacita/i.test(pt)) await s.pilih(r, "payroll-create-entity", "Sukacita");
    await s.pilihPersis(r, "payroll-create-period", s.MASA_LABEL);
    await s.pilihPersis(r, "payroll-create-type", "Susulan");
    await r.tid("payroll-create-type-hint").waitFor();
    await s.klikPotret(r, r.tid("payroll-create-submit"), "hitung-susulan");
    const msg = await s.tungguTeks(r, "payroll-notice", /siap \(\d+ karyawan\)/, 30000);
    run = s.prosesKaryawan(emp.id);
    assert(run && run.run_type === "susulan" && run.status === "draft", `DB proses: ${JSON.stringify(run && { t: run.run_type, s: run.status })}`);
    assert(run.totals.employees === 1, `proses memuat ${run.totals.employees} karyawan (masukan peserta lain ikut?) — batalkan draf lalu hitung lagi`);
    assert(Math.abs(Number(run.totals.gross) - d.masukan_nominal) < 0.01, `bruto ${run.totals.gross}`);
    await r.tid("payroll-run-detail").waitFor();
    return `${msg} · ${run.number} bruto ${rp(run.totals.gross)} · PPh 21 ${rp(run.totals.pph21)} · bersih ${rp(run.totals.net)}`;
  });

  await r.step(3, "Finance", "Klik nama karyawan di tabel slip untuk membuka rinciannya", "Pendapatan: Rapel Rp 8.000.000 · Potongan: PPh 21 (TER B) · Gaji bersih; tanpa BPJS (proses susulan)", async () => {
    const slip = mongo(`return db.hr_payslips.findOne({run_id:"${run.id}",employee_id:"${emp.id}"},{_id:0})`);
    assert(slip && slip.ter_category === "B", `kategori TER ${slip && slip.ter_category}`);
    await r.tid(`payslip-toggle-${slip.id}`).click();
    await r.tid(`payslip-detail-${slip.id}`).waitFor();
    const t = (await r.tid(`payslip-detail-${slip.id}`).innerText()).replace(/\s+/g, " ");
    assert(/Rapel/.test(t) && t.includes("8.000.000"), `rincian slip: ${t.slice(0, 300)}`);
    await r.tid("payroll-payslips-table").scrollIntoViewIfNeeded();
    await r.shot("rincian-slip", { locator: r.tid("payroll-run-detail") });
    return `${slip.number} · TER ${slip.ter_category} ${(Number(slip.pph21_rate) * 100).toFixed(2)}% · PPh 21 ${rp(slip.pph21)} · bersih ${rp(slip.net)} · ${t.slice(0, 160)}`;
  });

  await r.step(4, "Finance", "Klik [[Ajukan]]", "Status Diajukan; Finance juga melihat tombol Sahkan (K-FIN-01) — pengesahan di latihan ini diperagakan Manajer (orang kedua)", async () => {
    await s.klikPotret(r, r.tid("payroll-submit"), "ajukan", { locator: r.tid("payroll-actions") });
    await s.tungguTeks(r, "payroll-notice", /Ajukan berhasil/);
    const st = mongo(`return db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0,status:1})`).status;
    assert(st === "pending_approval", `status ${st}`);
    await r.kfin(r.tid("payroll-approve"), "tombol Sahkan proses gaji");
    await r.shot("diajukan", { locator: r.tid("payroll-run-detail") });
    return `status ${st} · ${await r.text("payroll-actions").catch(() => "")}`;
  });

  await r.step(5, "Manajer", "Login Manajer → SDM › Penggajian › Proses Gaji → pilih proses peserta → [[Sahkan]] → konfirmasi [[Sahkan]]", "Konfirmasi menyebut periode, jenis Susulan, 1 karyawan, gaji bersih, PT; status Disahkan", async () => {
    await s.masuk(r, "manager");
    await r.go("hr-payroll-runs");
    await r.tid(`payroll-run-${run.id}`).waitFor({ timeout: 15000 });
    await r.tid(`payroll-run-${run.id}`).click();
    await r.tid("payroll-approve").waitFor();
    await r.tid("payroll-approve").click();
    const msg = await s.konfirmasi(r, "konfirmasi-sahkan");
    assert(/Oktober 2026/.test(msg) && /1 karyawan/.test(msg), `konfirmasi: ${msg}`);
    await s.tungguTeks(r, "payroll-notice", /Sahkan berhasil/);
    const st = mongo(`return db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0,status:1,approved_by:1})`);
    assert(st.status === "approved", `status ${st.status}`);
    await r.shot("disahkan", { locator: r.tid("payroll-run-detail") });
    return `"${msg}" · ${st.status} oleh ${st.approved_by}`;
  });

  await r.step(6, "Finance", "Login Finance → Proses Gaji → pilih proses Anda → [[Posting Jurnal]] → konfirmasi [[Posting]]", "Status Diposting; \"Jurnal gaji KSC/JE-… · tanggal buku 31 Okt 2026\"; proses masuk antrean \"Gaji siap dibayar\"", async () => {
    await s.masuk(r, akunPeserta(no));
    await r.go("hr-payroll-runs");
    await r.tid(`payroll-run-${run.id}`).waitFor({ timeout: 15000 });
    await r.tid(`payroll-run-${run.id}`).click();
    await r.tid("payroll-post-gl").waitFor();
    await r.tid("payroll-post-gl").click();
    const msg = await s.konfirmasi(r, "konfirmasi-posting");
    await s.tungguTeks(r, "payroll-notice", /Posting jurnal berhasil/, 30000);
    run = mongo(`return db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0})`);
    assert(run.status === "posted" && run.journal_id, `status ${run.status}`);
    const ref = await r.text("payroll-journal-ref");
    await s.sorot(r.tid("payroll-journal-ref"));
    await r.shot("diposting", { locator: r.tid("payroll-run-detail") });
    await s.lepas(r.tid("payroll-journal-ref"));
    return `"${msg}" · ${ref}`;
  });

  await r.step(7, "Finance", "Cek buku: jurnal gaji proses Anda", "6-1000 Beban Gaji (D) Rp 8.000.000 = 2-1600 Hutang Gaji (K) gaji bersih + 2-1800 Hutang PPh 21 (K) — seimbang, tanggal 31 Okt 2026 (akhir masa gaji)", async () => {
    const je = mongo(`return db.journal_entries.findOne({id:"${run.journal_id}"},{_id:0})`);
    const t = run.totals;
    const ring = s.cekJurnal(je, [["6-1000", "D", t.gross], ["2-1600", "K", t.net], ["2-1800", "K", t.pph21]]);
    assert(je.date === "2026-10-31", `tanggal jurnal ${je.date}`);
    assert(Number(t.pph21) > 0, "PPh 21 nol — periksa PTKP/TER");
    return `${ring} · tanggal ${je.date}`;
  });

  await r.finish();
})();
