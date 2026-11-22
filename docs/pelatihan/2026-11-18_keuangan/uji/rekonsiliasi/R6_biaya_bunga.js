// R6 · BIAYA ADMINISTRASI & BUNGA BANK — dua baris yang memang TIDAK ADA di buku (bank memotong/menambah sendiri).
// Dibukukan langsung dari layar Rekonsiliasi: [[Catat biaya bank]] (keluar) dan [[Catat bunga bank]] (masuk), masing-masing
// dengan konfirmasi. Cek buku: kas baru + jurnal seimbang (Dr Beban Adm Bank / Cr Bank; Dr Bank / Cr Pendapatan Bunga).
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R6_biaya_bunga.js
const { Run, assert, rp, api } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R6", "Rekonsiliasi · biaya administrasi & bunga bank — catat dari layar rekonsiliasi").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const [mAdm, mBunga] = c.barisManifest("R6");
  let adm;
  let bunga;

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R6")} → [[Pratinjau]] → [[Impor]]`,
    `2 baris baru: BIAYA ADM LATIHAN NN ${rp(mAdm.nominal)} (keluar) dan BUNGA LATIHAN NN ${rp(mBunga.nominal)} (masuk)`, async () => {
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R6", { baris: 2 });
      await rk.saring(r, c);
      adm = rk.baris(c, mAdm.keterangan);
      bunga = rk.baris(c, mBunga.keterangan);
      assert(adm.direction === "out" && bunga.direction === "in", "arah dana baris biaya/bunga");
      return x.notice;
    });

  await r.step(2, "Finance", `Pada baris BIAYA ADM klik [[Catat biaya bank]] → periksa dialog → [[Catat biaya bank]]`,
    `Dialog "Catat biaya bank?" menyebut ${rp(mAdm.nominal)} dan PT Sukacita; pesan "Biaya bank dibukukan (Dr Beban Adm Bank / Cr Bank)."; baris Tercocok · "Biaya bank · akun 6-8000"`, async () => {
      await r.tid(`recon-charge-${adm.id}`).click();
      await r.tid("recon-charge-confirm").waitFor();
      await r.shot("konfirmasi-biaya-bank", { locator: r.tid("recon-charge-confirm").locator(".modal-card") });
      const msg = await kb.konfirmasi(r, "recon-charge-confirm");
      assert(msg.includes(rp(mAdm.nominal)) && /Sukacita/.test(msg), `dialog: ${msg}`);
      const t = await kb.tunggu(r, "recon-notice", /Biaya bank dibukukan/);
      await rk.saring(r, c);
      await rk.tungguStatus(r, adm.id, /^Tercocok$/);
      const row = await kb.isi(r.tid(`recon-line-${adm.id}`));
      assert(/Biaya bank · akun 6-8000/.test(row), `baris: ${row}`);
      return t;
    });

  await r.step(3, "Finance", `Pada baris BUNGA klik [[Catat bunga bank]] → periksa dialog → [[Catat bunga bank]]`,
    `Dialog "Catat bunga bank?" menyebut ${rp(mBunga.nominal)}; pesan "Bunga · jasa giro dibukukan (Dr Bank / Cr Pendapatan Bunga)."; baris Tercocok`, async () => {
      await r.tid(`recon-interest-${bunga.id}`).click();
      await r.tid("recon-interest-confirm").waitFor();
      await r.shot("konfirmasi-bunga-bank", { locator: r.tid("recon-interest-confirm").locator(".modal-card") });
      const msg = await kb.konfirmasi(r, "recon-interest-confirm");
      assert(msg.includes(rp(mBunga.nominal)), `dialog: ${msg}`);
      const t = await kb.tunggu(r, "recon-notice", /Bunga · jasa giro dibukukan/);
      await rk.saring(r, c);
      await rk.tungguStatus(r, bunga.id, /^Tercocok$/);
      await kb.sorot(r.tid(`recon-line-${adm.id}`));
      await kb.sorot(r.tid(`recon-line-${bunga.id}`));
      await r.shot("biaya-bunga-tercatat", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${adm.id}`));
      await kb.lepas(r.tid(`recon-line-${bunga.id}`));
      return t;
    });

  await r.step(4, "Finance", `Cek jurnal: Akuntansi & Pajak › Buku Besar › Jurnal → cari "BUNGA LATIHAN ${c.NO}" → buka jurnalnya`,
    `Biaya: 6-8000 Beban Administrasi Bank Debit ${rp(mAdm.nominal)} / 1-1100 Bank Kredit. Bunga: 1-1100 Bank Debit ${rp(mBunga.nominal)} / 4-9000 Pendapatan Lain-lain Kredit (akun pemetaan kas_bank.pendapatan_bunga). Keduanya seimbang; kas baru terekonsiliasi`, async () => {
      adm = rk.baris(c, mAdm.keterangan);
      bunga = rk.baris(c, mBunga.keterangan);
      const kasAdm = rk.kasTerekonsiliasi(adm.charge.cash_txn_id, { jurnalTetapSatu: false });
      const kasBunga = rk.kasTerekonsiliasi(bunga.charge.cash_txn_id, { jurnalTetapSatu: false });
      assert(kasAdm.direction === "out" && kasBunga.direction === "in", "arah kas biaya/bunga");
      assert(kasAdm.account_id === c.bca.id && kasBunga.account_id === c.bca.id, "kas tidak di rekening BCA");
      // Akun lawan = PEMETAAN AKUN yang berlaku untuk PT ini (Pengaturan › Pemetaan Akun): kas_bank.beban_bank (bawaan
      // 6-8000 Beban Administrasi Bank) dan kas_bank.pendapatan_bunga (bawaan 4-9000 Pendapatan Lain-lain).
      const peta = (await (await api("admin")).get(`/gl/account-mappings?entity_id=${kb.KSC}`, kb.KSC)).rows || [];
      const akun = (key) => (peta.find((x) => x.key === key) || {}).account_code;
      const [beban, bungaAkun] = [akun("kas_bank.beban_bank"), akun("kas_bank.pendapatan_bunga")];
      assert(beban && bungaAkun, "pemetaan akun kas_bank.beban_bank / kas_bank.pendapatan_bunga tidak terbaca");
      const jeAdm = kb.seimbang(kb.jurnal("cash_transaction", kasAdm.id), "jurnal biaya bank");
      assert(kb.adaBaris(jeAdm, beban, "D", mAdm.nominal), `jurnal biaya (Dr ${beban}): ${kb.teksJurnal(jeAdm)}`);
      const bank = jeAdm.lines.find((l) => Number(l.credit) > 0);
      const jeB = kb.seimbang(kb.jurnal("cash_transaction", kasBunga.id), "jurnal bunga bank");
      assert(kb.adaBaris(jeB, bank.account_code, "D", mBunga.nominal), `jurnal bunga sisi bank: ${kb.teksJurnal(jeB)}`);
      assert(kb.adaBaris(jeB, bungaAkun, "K", mBunga.nominal), `jurnal bunga (Cr ${bungaAkun}): ${kb.teksJurnal(jeB)}`);
      await kb.lihatJurnal(r, `BUNGA LATIHAN ${c.NO}`, jeB, "jurnal-bunga-bank");
      return `${kb.teksJurnal(jeAdm)} || ${kb.teksJurnal(jeB)}`;
    });

  await r.finish();
})();
