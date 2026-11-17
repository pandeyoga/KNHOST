// H02 — Masukan gaji masa Oktober 2026 (Finance, K-SDM-01): (a) Komponen & Masukan › [Tambah masukan] Rapel gaji
// Oktober untuk karyawan baru H01 (menunggu disahkan Manajer — disahkan di H03 tepat sebelum proses dihitung);
// (b) Kehadiran › Lembur: ajukan lembur 2 jam untuk karyawan itu, Manajer menyetujui → masuk proses REGULER November
// (lembur & potongan absensi dihitung di proses reguler, bukan susulan).
//   node docs/pelatihan/2026-11-18_keuangan/uji/sdm/H02_masukan_gaji.js      (bawaan peserta 51; KN_PESERTA=52 …)
const { Run, assert, rp, peserta, akunPeserta, mongo } = require("../lib");
const s = require("./sdm_lib");

(async () => {
  const no = peserta("51");
  const d = s.dataKaryawan(no);
  const r = await new Run("H02", "Masukan gaji & lembur").start();
  const emp = s.karyawan(d.nama);
  if (!emp) { r.note(`Karyawan ${d.nama} belum ada — jalankan H01 dulu`); await r.finish(); return; }
  const label = "Rapel gaji Oktober (karyawan baru)";
  const alasan = `Masuk ${d.tanggal_masuk}, terlewat proses reguler Oktober`;
  r.note(`Peserta ${no} · ${emp.code} ${emp.name} · Rapel ${rp(d.masukan_nominal)} masa ${s.MASA_LABEL} · lembur ${d.lembur_jam} jam ${d.lembur_tanggal}`);
  let inp = null;
  let ot = null;

  await r.step(1, "Finance", "Login → SDM › Penggajian › tab [[Komponen & Masukan]] → bagian Masukan → [[Tambah masukan]]", "Pop-up \"Tambah masukan gaji\" (Sukacita): Karyawan · Komponen · Periode bayar · Nominal · Keterangan · Alasan", async () => {
    await s.masuk(r, akunPeserta(no));
    await s.menu(r, "hrd", "hr-payroll-hub");
    await r.tid("hub-tab-hr-pay-components").click();
    await r.tid("paycomp-table").waitFor({ timeout: 15000 });
    await r.tid("payinput-add").scrollIntoViewIfNeeded();
    await s.klikPotret(r, r.tid("payinput-add"), "tambah-masukan");
    await r.tid("payinput-form").waitFor();
    return await r.text("payinput-form-title");
  });

  await r.step(2, "Finance", `Isi: *Karyawan* ${d.nama} · *Komponen* Rapel (Pendapatan) · *Periode bayar* ${s.MASA_LABEL} · *Nominal* 8.000.000 · *Keterangan* ${label} · *Alasan* ${alasan} → [[Simpan masukan]]`, "Pesan \"Masukan … Rp 8.000.000 dicatat, menunggu disahkan.\"; baris baru status Menunggu disahkan; Finance juga melihat tombol Sahkan (K-FIN-01) — pengesahan di latihan ini diperagakan Manajer", async () => {
    await s.pilih(r, "payinput-form-emp", d.nama);
    await s.pilih(r, "payinput-form-comp", "Rapel");
    await s.pilihPersis(r, "payinput-form-period", s.MASA_LABEL);
    await r.tid("payinput-form-amount").fill("8.000.000");
    const prev = await r.text("payinput-form-amount-preview");
    assert(prev.includes(s.rupiahTanpaRp(d.masukan_nominal)), `pratinjau nominal: ${prev}`);
    await r.tid("payinput-form-label").fill(label);
    await r.tid("payinput-form-reason").fill(alasan);
    await s.sorot(r.tid("payinput-form-submit"));
    await r.shot("form-masukan", { locator: r.tid("payinput-form") });
    await s.lepas(r.tid("payinput-form-submit"));
    await r.tid("payinput-form-submit").click();
    await r.tid("payinput-form").waitFor({ state: "detached", timeout: 15000 });
    const msg = await s.tungguTeks(r, "paycomp-view", /dicatat, menunggu disahkan/);
    inp = mongo(`return db.hr_pay_inputs.find({employee_id:"${emp.id}",pay_period:"${s.MASA}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(inp && inp.status === "pending" && Number(inp.amount) === d.masukan_nominal && inp.component_code === "RAPEL",
      `DB masukan: ${JSON.stringify(inp && { s: inp.status, a: inp.amount, c: inp.component_code })}`);
    await s.pilih(r, "payinput-period", s.MASA_LABEL);
    await r.tid(`payinput-row-${inp.id}`).waitFor({ timeout: 10000 });
    await r.kfin(r.tid(`payinput-approve-${inp.id}`), "tombol Sahkan masukan");
    const st = await r.text(`payinput-status-${inp.id}`);
    await s.sorot(r.tid(`payinput-row-${inp.id}`));
    await r.shot("masukan-menunggu", { full: true });
    await s.lepas(r.tid(`payinput-row-${inp.id}`));
    return `${(msg.match(/Masukan[^.]*dicatat, menunggu disahkan\./) || [""])[0]} · status ${st} · ${await r.text("payinput-no-approve").catch(() => "")}`;
  });

  await r.step(3, "Finance", `SDM › [[Kehadiran]] › tab Lembur → [[Ajukan untuk Karyawan]] → *Karyawan* ${d.nama} · *Tanggal* 16 Nov 2026 · *Jam* ${d.lembur_jam} · *Alasan* Tutup buku akhir bulan → [[Ajukan]]`, "Pesan \"Pengajuan lembur dibuat.\"; baris lembur status Menunggu", async () => {
    await s.menu(r, "hrd", "hr-attendance-hub");
    await r.tid("hub-tab-hr-overtime").click();
    await r.tid("overtime-view").waitFor();
    await r.tid("overtime-create-button").click();
    await r.tid("overtime-create-modal").waitFor();
    await s.pilih(r, "overtime-form-employee", d.nama);
    await s.pilihTanggal(r, "overtime-form-date", d.lembur_tanggal);
    await r.tid("overtime-form-hours").fill(String(d.lembur_jam));
    await r.tid("overtime-form-reason").fill(`Tutup buku akhir bulan (latihan ${no})`);
    await s.sorot(r.tid("overtime-form-submit"));
    await r.shot("form-lembur", { locator: r.tid("overtime-create-modal") });
    await s.lepas(r.tid("overtime-form-submit"));
    await r.tid("overtime-form-submit").click();
    await r.tid("overtime-create-modal").waitFor({ state: "detached", timeout: 15000 });
    const msg = await s.tungguTeks(r, "overtime-notice", /lembur dibuat/);
    ot = mongo(`return db.hr_overtime.find({employee_id:"${emp.id}",date:"${d.lembur_tanggal}"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(ot && ot.status === "pending" && Number(ot.hours) === d.lembur_jam, `DB lembur: ${JSON.stringify(ot && { s: ot.status, h: ot.hours })}`);
    await r.tid(`overtime-row-${ot.id}`).waitFor();
    await s.sorot(r.tid(`overtime-row-${ot.id}`));
    await r.shot("lembur-diajukan");
    await s.lepas(r.tid(`overtime-row-${ot.id}`));
    return `${msg} · ${ot.hours} jam ${ot.date} · status ${ot.status}`;
  });

  await r.step(4, "Manajer", "Login Manajer → SDM › Kehadiran › Lembur → [[Setujui]] pada lembur peserta → konfirmasi [[Setujui]]", "Pesan \"Lembur disetujui & masuk perhitungan gaji.\" — dibayar di proses gaji REGULER November (jam × upah per jam × pengali)", async () => {
    await s.masuk(r, "manager");
    await r.go("hr-overtime");
    await r.tid("overtime-view").waitFor();
    await r.tid(`overtime-approve-${ot.id}`).waitFor({ timeout: 15000 });
    await r.tid(`overtime-approve-${ot.id}`).click();
    const msg = await s.konfirmasi(r, "konfirmasi-setujui-lembur");
    const ok = await s.tungguTeks(r, "overtime-notice", /disetujui/);
    const sesudah = mongo(`return db.hr_overtime.findOne({id:"${ot.id}"},{_id:0,status:1,approved_by:1})`);
    assert(sesudah.status === "approved", `status lembur ${sesudah.status}`);
    await r.shot("lembur-disetujui");
    return `konfirmasi "${msg}" → ${ok} · ${JSON.stringify(sesudah)}`;
  });

  await r.finish();
})();
