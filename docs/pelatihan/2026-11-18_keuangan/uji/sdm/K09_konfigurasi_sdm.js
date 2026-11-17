// K09 — Konfigurasi SDM & Gaji (modul 1, fondasi): komponen gaji, PTKP & kategori TER, tarif BPJS, tabel TER, shift &
// kalender libur sebagai masukan proses gaji. Finance (K-SDM-01) MEMBACA semuanya dan melakukan SATU perubahan aman yang
// dikembalikan: menambah hari libur latihan di Desember 2026 (bulan yang belum digaji), lalu menghapusnya lagi.
//   node docs/pelatihan/2026-11-18_keuangan/uji/sdm/K09_konfigurasi_sdm.js      (bawaan peserta 51; KN_PESERTA=52 …)
const { Run, assert, peserta, akunPeserta, mongo } = require("../lib");
const s = require("./sdm_lib");

(async () => {
  const no = peserta("51");
  const d = s.dataKaryawan(no);
  const r = await new Run("K09", "Konfigurasi SDM & Gaji").start();
  const namaLibur = `Libur latihan ${no}`;
  r.note(`Peserta ${no} · libur latihan ${d.libur_latihan}`);

  await r.step(1, "Finance", "Login → Pengaturan › SDM › Aturan SDM & Penggajian", "Kelompok \"Gaji & SDM\": BPJS, PPh 21, Lembur, Prorata; Finance boleh mengubah (izin aturan gaji)", async () => {
    await s.masuk(r, akunPeserta(no));
    await s.menu(r, "settings-hub", "settings-hr");
    await r.tid("cfg-section-bpjs").waitFor({ timeout: 20000 });
    const scope = await r.text("cfg-read-scope");
    assert(/Gaji & SDM/.test(scope), `cakupan baca: ${scope}`);
    const kes = await r.text("cfg-compact-value-hr.bpjs.kes_rate_employee");
    const kesPt = await r.text("cfg-compact-value-hr.bpjs.kes_rate_employer");
    const jht = await r.text("cfg-compact-value-hr.bpjs.jht_rate_employee");
    await s.sorot(r.tid("cfg-section-bpjs"));
    await r.shot("aturan-bpjs");
    await s.lepas(r.tid("cfg-section-bpjs"));
    return `${scope.slice(0, 160)} · BPJS Kes karyawan ${kes}, perusahaan ${kesPt} · JHT karyawan ${jht}`;
  });

  await r.step(2, "Finance", "Buka kartu \"PTKP setahun per status\" dan \"Kategori tarif per status PTKP\"", "Tabel PTKP (TK/0 … K/3) dan kategori TER A/B/C per status — K/1 = kategori B", async () => {
    for (const k of ["hr.ptkp_table", "hr.pph21.ptkp_to_ter"]) {
      await r.tid(`cfg-card-toggle-${k}`).click();
      await r.idle(500);
    }
    // Isi tabel ada di kotak isian (Finance boleh mengubah) → baca nilai kotak + teks pilihan, bukan teks biasa.
    const isi = (id) => r.tid(id).evaluate((el) => [...el.querySelectorAll("input, button[role=combobox]")]
      .map((x) => (x.value !== undefined && x.tagName === "INPUT" ? x.value : x.innerText).trim()).filter(Boolean).join(" "));
    const ptkp = await isi("cfg-card-wrap-hr.ptkp_table");
    const ter = await isi("cfg-card-wrap-hr.pph21.ptkp_to_ter");
    assert(/\bK\/?1\b/.test(ptkp) && /58[.,]?500[.,]?000/.test(ptkp), `PTKP: ${ptkp.slice(0, 300)}`);
    assert(/\bK\/?1 B\b/.test(ter), `kategori TER K1: ${ter.slice(0, 300)}`);
    await r.tid("cfg-card-wrap-hr.ptkp_table").scrollIntoViewIfNeeded();
    await r.shot("ptkp-dan-kategori-ter");
    return `${ptkp.slice(0, 200)} | ${ter.slice(0, 200)}`;
  });

  await r.step(3, "Finance", "Buka kartu \"Tarif efektif PPh 21 bulanan\" (tabel TER)", "Tabel TER per kategori: batas bruto sebulan → tarif; proses gaji membaca tabel yang berlaku per tanggal", async () => {
    await r.tid("cfg-card-toggle-hr.pph21.ter_table").click();
    await r.idle(600);
    const t = (await r.tid("cfg-card-wrap-hr.pph21.ter_table").innerText()).replace(/\s+/g, " ");
    assert(/%/.test(t), `tabel TER: ${t.slice(0, 300)}`);
    await r.tid("cfg-card-wrap-hr.pph21.ter_table").scrollIntoViewIfNeeded();
    await r.shot("tabel-ter");
    return t.slice(0, 260);
  });

  await r.step(4, "Finance", "SDM › Penggajian › tab Komponen & Masukan", "Daftar komponen gaji PT: Gaji Pokok, Tunjangan, Lembur (per jam), Rapel/Insentif (masukan), BPJS & PPh 21 (undang-undang), potongan absensi", async () => {
    await s.menu(r, "hrd", "hr-payroll-hub");
    await r.tid("hub-tab-hr-pay-components").click();
    await r.tid("paycomp-table").waitFor({ timeout: 15000 });
    const kode = ["GAJI_POKOK", "TUNJANGAN", "LEMBUR", "RAPEL", "BPJS_KES", "PPH21", "POT_ALPHA", "BPJS_KES_PT"];
    for (const c of kode) await r.tid(`paycomp-row-${c}`).waitFor();
    const rapel = (await r.tid("paycomp-row-RAPEL").innerText()).replace(/\s+/g, " ");
    await s.sorot(r.tid("paycomp-row-RAPEL"));
    await r.shot("komponen-gaji", { locator: r.tid("paycomp-table") });
    await s.lepas(r.tid("paycomp-row-RAPEL"));
    return `${kode.length} komponen inti tampil · Rapel: ${rapel.slice(0, 160)}`;
  });

  await r.step(5, "Finance", "Pengaturan › SDM › tab Shift & Lokasi Absen", "Shift kerja PT (jam masuk/pulang, toleransi telat) — dasar hitung telat & lembur dari absensi", async () => {
    await s.menu(r, "settings-hub", "settings-hr");
    await r.tid("hub-tab-hr-attendance-setup").click();
    await r.tid("attendance-setup-view").waitFor();
    const row = r.page.locator('[data-testid^="setup-row-"]').first();
    await row.waitFor({ timeout: 15000 });
    const t = (await row.innerText()).replace(/\s+/g, " ");
    await r.shot("shift-kerja");
    return t.slice(0, 200);
  });

  let libur = null;
  await r.step(6, "Finance", `Tab Kalender Libur → [[Tambah hari libur]] → *Tanggal* ${d.libur_latihan} · *Jenis* Perusahaan · *Nama* ${namaLibur} → [[Simpan]]`, "Pesan \"Hari libur … ditambahkan untuk Sukacita…\"; baris baru di tabel 2026", async () => {
    await r.tid("hub-tab-hr-holidays").click();
    await r.tid("hr-holidays-view").waitFor();
    await r.idle(500);
    mongo(`db.hr_holidays.deleteMany({entity_id:"ent_ksc",name:${JSON.stringify(namaLibur)}}); return 1`);   // sisa uji gagal
    await r.tid("hr-holidays-add").click();
    await r.tid("hr-holidays-form").waitFor();
    await s.pilihTanggal(r, "hr-holidays-form-date", d.libur_latihan);
    await s.pilih(r, "hr-holidays-form-kind", "Perusahaan");
    await r.tid("hr-holidays-form-name").fill(namaLibur);
    await s.sorot(r.tid("hr-holidays-form-submit"));
    await r.shot("form-hari-libur");
    await s.lepas(r.tid("hr-holidays-form-submit"));
    await r.tid("hr-holidays-form-submit").click();
    const msg = await s.tungguTeks(r, "hr-holidays-msg", /ditambahkan/);
    libur = mongo(`return db.hr_holidays.findOne({entity_id:"ent_ksc",name:${JSON.stringify(namaLibur)}},{_id:0})`);
    assert(libur && libur.date === d.libur_latihan, `DB hari libur: ${JSON.stringify(libur)}`);
    await r.tid(`hr-holidays-row-${libur.id}`).waitFor();
    await s.sorot(r.tid(`hr-holidays-row-${libur.id}`));
    await r.shot("hari-libur-ditambah");
    await s.lepas(r.tid(`hr-holidays-row-${libur.id}`));
    return `${msg} · ${libur.date} ${libur.kind}`;
  });

  await r.step(7, "Finance", "Kembalikan: klik [[Hapus]] pada baris itu → konfirmasi [[Hapus]]", "Pesan \"Hari libur … dihapus\"; baris hilang — kalender kembali seperti semula", async () => {
    assert(libur, "hari libur latihan tidak tercatat di langkah 6");
    await r.tid(`hr-holidays-del-${libur.id}`).click();
    const msg = await s.konfirmasi(r, "konfirmasi-hapus-libur");
    await s.tungguTeks(r, "hr-holidays-msg", /dihapus/);
    await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="hr-holidays-row-${id}"]`), libur.id, { timeout: 10000 });
    const sisa = mongo(`return db.hr_holidays.countDocuments({entity_id:"ent_ksc",name:${JSON.stringify(namaLibur)}})`);
    assert(sisa === 0, `hari libur latihan masih ${sisa}`);
    await r.shot("hari-libur-dihapus");
    return `konfirmasi "${msg}" · tersisa ${sisa}`;
  });

  await r.finish();
})();
