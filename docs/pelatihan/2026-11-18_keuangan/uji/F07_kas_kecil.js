// F07 · Kas Kecil — cairkan pengajuan dana (PD) karyawan, pertanggungjawaban (LPJ) dengan bukti, persetujuan manajer,
// lalu terima kembali sisa uang muka. Cek layar + buku (kas keluar/masuk Kas Toko, jurnal uang muka & beban seimbang —
// dilihat peserta di Akuntansi & Pajak › Buku Besar › Jurnal, dicocokkan uji dengan data buku).
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/F07_kas_kecil.js          (peserta 03)
//   KN_PESERTA=34 node docs/pelatihan/2026-11-18_keuangan/uji/F07_kas_kecil.js
// Data awal: `scripts/latih_keuangan/c_kas.py` (kartu `c_kas:pd_kas_kecil` = PD yang sudah disetujui berjenjang).
const os = require("os");
const path = require("path");
const { Run, assert, kartu, peserta, akunPeserta, rp, sleep, mongo } = require("./lib.js");
const kb = require("./kasbank_lib.js");

const NO = peserta("03");
const LPJ = [
  { desc: "Bensin & tol kunjungan pelanggan", cat: "transportasi", akun: "6-4600", amount: 185000 },
  { desc: "Fotokopi katalog & materai", cat: "fotocopy_printing_jilid_materai", akun: "6-4300", amount: 47000 },
];
const PAKAI = LPJ.reduce((s, l) => s + l.amount, 0);   // 232.000

(async () => {
  const r = await new Run("F07", "Kas Kecil — cairkan PD, LPJ dengan bukti, terima sisa").start();
  const k = kartu(NO)["c_kas:pd_kas_kecil"];
  if (!k) { r.note(`Kartu peserta ${NO} belum punya c_kas:pd_kas_kecil — jalankan seed --hanya c_kas:`); await r.finish(); return; }
  const SISA = k.nominal - PAKAI;
  let kasToko0 = null; let ca = null; let stl = null; let sisaKas = null;
  const toast = (re) => kb.tunggu(r, "pc-toast", re);
  const bukaPd = async () => {
    await kb.menu(r, "petty-cash");
    await r.tid("pc-search").fill(k.pd);
    await r.tid(`pc-row-${k.pd_id}`).waitFor();
    await r.tid(`pc-open-${k.pd_id}`).click();
    await r.tid("ca-detail").waitFor();
    await r.idle(300);
  };

  await r.step(1, "Finance", "Login akun peserta, buka Keuangan › Kas & Bank › Kas Kecil, ketik \"Latihan NN\" di kotak cari",
    `Baris ${k.pd}: Keperluan "Latihan ${NO} · Kunjungan Toko Kain Peserta ${NO}", pemohon ${k.pemohon}, Jumlah ${rp(k.nominal)}, Tahap "Diajukan" dengan keterangan "Disetujui"`, async () => {
      await r.login(akunPeserta(NO));
      kasToko0 = await kb.rekening(akunPeserta(NO), "Kas Toko KSC");
      await kb.menu(r, "petty-cash");
      await r.tid("pc-search").fill(`Latihan ${NO}`);
      const row = r.tid(`pc-row-${k.pd_id}`);
      await row.waitFor();
      const t = await kb.isi(row);
      assert(t.includes(k.pd) && t.includes(rp(k.nominal)), `baris PD: ${t}`);
      assert(/Diajukan/.test(t) && /Disetujui/.test(t), `tahap PD: ${t}`);
      await kb.shotSorot(r, "daftar-kas-kecil", r.tid(`pc-open-${k.pd_id}`));
      return `${k.pd} · saldo Kas Toko awal ${rp(kasToko0.balance)}`;
    });

  await r.step(2, "Finance", "Klik [[Buka]] pada PD → periksa rincian & Riwayat Persetujuan",
    "Status PD Disetujui, Total Pengajuan Rp 500.000; Riwayat Persetujuan: Atasan Langsung, Pimpinan, Bagian Keuangan — Disetujui; tombol [[Cairkan]] tersedia", async () => {
      await r.tid(`pc-open-${k.pd_id}`).click();
      await r.tid("ca-detail").waitFor();
      assert((await kb.teks(r, "ca-detail-status")) === "Disetujui", "status bukan Disetujui");
      assert((await kb.teks(r, "ca-detail-total")) === rp(k.nominal), "total PD");
      assert(await r.tid("ca-approval-2").isVisible(), "riwayat persetujuan < 3");
      await kb.shotSorot(r, "pd-disetujui", r.tid("ca-disburse-btn"), { locator: r.tid("pc-detail-modal") });
    });

  await r.step(3, "Finance", "Klik [[Cairkan]] → *Sumber Kas*: Kas Kecil (tunai) · *Rekening*: Kas Toko KSC (terisi otomatis) → [[Cairkan Dana]] → di dialog konfirmasi klik [[Cairkan Dana]]",
    `Dialog konfirmasi menyebut Rp 500.000, Kas Toko KSC dan Sukacita Textile; lalu notifikasi "${k.pd} dicairkan (Rp 500.000)."; status Dicairkan; baris "Kas Keluar KSC/CASH-… · Kas Kecil"`, async () => {
      await r.tid("ca-disburse-btn").click();
      await r.tid("ca-disburse-modal").waitFor();
      await r.tid("ca-disburse-account-sole").waitFor();   // rekening kas kecil tunggal → terisi otomatis
      const rek = await kb.teks(r, "ca-disburse-account");
      assert(rek.includes("Kas Toko KSC"), `rekening: ${rek}`);
      await kb.shotSorot(r, "form-cairkan", r.tid("ca-disburse-confirm"), { locator: r.tid("ca-disburse-modal") });
      await r.tid("ca-disburse-confirm").click();
      await r.tid("ca-disburse-money-confirm").waitFor();
      await r.shot("konfirmasi-cairkan", { locator: r.tid("ca-disburse-money-confirm").locator(".modal-card") });
      const msg = await kb.konfirmasi(r, "ca-disburse-money-confirm");
      assert(msg.includes(rp(k.nominal)) && /Kas Toko KSC/.test(msg), `konfirmasi: ${msg}`);
      const t = await toast(`${k.pd} dicairkan`);
      assert(t.includes(rp(k.nominal)), `notifikasi: ${t}`);
      await r.idle(300);
      assert((await kb.teks(r, "ca-detail-status")) === "Dicairkan", "status setelah cair");
      ca = mongo(`return db.cash_advances.findOne({id:"${k.pd_id}"},{_id:0,status:1,disbursement:1})`);
      assert(ca.status === "disbursed" && ca.disbursement && ca.disbursement.cash_txn_number, "PD belum disbursed di DB");
      await kb.shotSorot(r, "pd-dicairkan", r.tid("pc-settle-btn"), { locator: r.tid("pc-detail-modal") });
      return `${ca.disbursement.cash_txn_number}`;
    });

  await r.step(4, "Finance", `Cek jurnal pencairan: Akuntansi & Pajak › Buku Besar › Jurnal → ketik nomor PD (${k.pd}) di kotak cari → klik baris jurnal sumber "Kas"`,
    `Jurnal "Kas keluar · Pencairan ${k.pd} …": 1-1400 Uang Muka & Biaya Dibayar Dimuka Debit Rp 500.000 · 1-1110 Kas Kecil Kredit Rp 500.000; total debit = total kredit`, async () => {
      const txn = kb.kas(ca.disbursement.cash_txn_id);
      assert(txn && txn.direction === "out" && Math.abs(txn.amount - k.nominal) < 0.01 && txn.account_id === kasToko0.id,
        `kas cair: ${JSON.stringify(txn && { d: txn.direction, a: txn.amount, acc: txn.account_id })}`);
      const je = kb.seimbang(kb.jurnal("cash_transaction", txn.id), "jurnal pencairan");
      assert(kb.adaBaris(je, "1-1400", "D", k.nominal) && kb.adaBaris(je, "1-1110", "K", k.nominal), kb.teksJurnal(je));
      await r.tid("pc-detail-modal-close-x").click();          // tutup rincian PD dulu, lalu pindah menu
      await r.tid("pc-detail-modal").waitFor({ state: "detached" });
      await kb.lihatJurnal(r, k.pd, je, "jurnal-pencairan");
      return kb.teksJurnal(je);
    });

  await r.step(5, "Finance", "Kembali ke Kas Kecil → buka PD → klik [[Pertanggungjawabkan]] → isi dua baris pengeluaran (Tanggal, Uraian, Kategori, Nominal; baris kedua lewat [[Tambah Baris]]) → [[Simpan LPJ]]",
    `Ringkasan per Kategori tampil; Total Pengeluaran ${rp(PAKAI)}, Sisa Uang Muka (dikembalikan sesudah disetujui) ${rp(SISA)}; notifikasi "KSC/STL-… disimpan."; LPJ berstatus Draf`, async () => {
      await bukaPd();
      await r.tid("pc-settle-btn").click();
      await r.tid("stl-form").waitFor();
      for (let i = 0; i < LPJ.length; i++) {
        if (i > 0) await r.tid("stl-add-line").click();
        await r.tid(`stl-line-desc-${i}`).fill(LPJ[i].desc);
        await kb.pilih(r, `stl-line-cat-${i}`, LPJ[i].cat);
        await r.tid(`stl-line-amount-${i}`).fill(String(LPJ[i].amount));
      }
      await r.tid("stl-divisi").fill("Penjualan");
      await sleep(300);
      assert((await kb.teks(r, "stl-total-pengeluaran")) === rp(PAKAI), "total pengeluaran di form");
      assert((await kb.teks(r, "stl-sisa")) === rp(SISA), "sisa di form");
      await kb.shotSorot(r, "form-lpj", r.tid("stl-submit"), { locator: r.tid("stl-form") });
      await r.tid("stl-submit").click();
      await r.tid("stl-form").waitFor({ state: "hidden" });
      await toast(/STL-\d+ disimpan/);
      await r.tid("stl-detail").waitFor();
      assert((await kb.teks(r, "stl-detail-status")) === "Draf", "status LPJ bukan Draf");
      stl = mongo(`return db.cash_advance_settlements.findOne({cash_advance_id:"${k.pd_id}",status:{$ne:"rejected"}},{_id:0,id:1,number:1,total_pengeluaran:1})`);
      assert(stl && Math.abs(stl.total_pengeluaran - PAKAI) < 0.01, "LPJ di DB");
      return stl.number;
    });

  await r.step(6, "Finance", "Di rincian LPJ (bawah) klik [[Unggah Bukti]] → pilih foto nota → lalu klik [[Ajukan]] (atas kartu LPJ)",
    `"Lampiran bukti (1)" berisi nama berkas + gambar kecil; notifikasi "KSC/STL-… diajukan."; status LPJ Diajukan`, async () => {
      const nota = path.join(os.tmpdir(), `nota-latihan-${NO}.png`);
      const np = await r.ctx.newPage();
      await np.setViewportSize({ width: 420, height: 300 });
      await np.setContent(`<div style="font:16px monospace;padding:18px;border:2px dashed #555;width:360px">
        <b>SPBU 34.401.12 BANDUNG</b><br>Pertalite 18,5 L ......... Rp 185.000<br>Tol Pasteur ............ (termasuk)<br>
        ${new Date().toLocaleDateString("id-ID")} · Latihan ${NO}<br><br><b>FOTOKOPI JAYA</b><br>Katalog + materai .... Rp 47.000</div>`);
      await np.screenshot({ path: nota });
      await np.close();
      await r.tid("stl-attach-input").setInputFiles(nota);
      await r.page.waitForFunction(() => /Lampiran bukti \(1\)/.test(document.querySelector('[data-testid="stl-attachments"]')?.innerText || ""));
      await toast(/dilampirkan/);
      await kb.shotSorot(r, "lpj-bukti", r.tid("stl-submit-btn"), { locator: r.tid("stl-detail") });
      await r.tid("stl-submit-btn").click();
      await toast(`${stl.number} diajukan`);
      await r.idle(300);
      assert((await kb.teks(r, "stl-detail-status")) === "Diajukan", "status LPJ bukan Diajukan");
      const att = mongo(`return (db.cash_advance_settlements.findOne({id:"${stl.id}"},{_id:0,attachments:1}).attachments||[]).length`);
      assert(att >= 1, "lampiran tidak tersimpan");
    });

  await r.step(7, "Manajer (pelatih)", "Login manager@ → Kas & Bank › Kas Kecil → buka PD peserta → di kartu LPJ klik [[Setujui & Posting GL]] → konfirmasi [[Setujui & Posting]]",
    `Notifikasi "KSC/STL-… disetujui & diposting ke GL."; status LPJ Terposting GL; bilah kuning "Sisa uang muka ${rp(SISA)} harus dikembalikan ${k.pemohon}."`, async () => {
      await r.login("manager");
      await bukaPd();
      await kb.shotSorot(r, "lpj-menunggu-manajer", r.tid("stl-approve-btn"), { locator: r.tid("stl-detail") });
      await r.tid("stl-approve-btn").click();
      const msg = await kb.konfirmasi(r, "stl-approve-confirm");
      assert(msg.includes(rp(PAKAI)), `konfirmasi setujui: ${msg}`);
      await toast(`${stl.number} disetujui & diposting ke GL`);
      await r.idle(300);
      assert((await kb.teks(r, "stl-detail-status")) === "Terposting GL", "status LPJ");
      const bar = await kb.teks(r, "stl-remainder-bar");
      assert(bar.includes(rp(SISA)) && bar.includes(k.pemohon), `bilah sisa (harus menyebut pemohon PD ${k.pemohon}): ${bar}`);
      await r.shot("lpj-disetujui", { locator: r.tid("stl-detail") });
    });

  await r.step(8, "Finance", `Login akun peserta → cek jurnal LPJ: Buku Besar › Jurnal → ketik nomor LPJ (KSC/STL-…) → klik baris "LPJ Kas Kecil"`,
    `Jurnal "Pertanggungjawaban kas kecil KSC/STL-…": Debit 6-4600 Beban Transportasi & BBM ${rp(LPJ[0].amount)} · Debit 6-4300 Beban Cetak, Fotokopi & Materai ${rp(LPJ[1].amount)} · Kredit 1-1400 Uang Muka ${rp(PAKAI)}`, async () => {
      const je = kb.seimbang(kb.jurnal("petty_cash_settlement", stl.id), "jurnal LPJ");
      for (const l of LPJ) assert(kb.adaBaris(je, l.akun, "D", l.amount), `beban ${l.akun}: ${kb.teksJurnal(je)}`);
      assert(kb.adaBaris(je, "1-1400", "K", PAKAI), `kredit uang muka: ${kb.teksJurnal(je)}`);
      await r.login(akunPeserta(NO));
      await kb.lihatJurnal(r, stl.number, je, "jurnal-lpj");
      return kb.teksJurnal(je);
    });

  await r.step(9, "Finance", "Kas & Bank › Kas Kecil → buka PD → klik [[Terima Pengembalian Sisa Rp …]] → *Jenis kas*: Kas Kecil (tunai) · *Rekening*: Kas Toko KSC · *Tanggal*: hari ini → [[Terima Pengembalian]] → konfirmasi [[Terima Pengembalian]]",
    `Notifikasi "Sisa uang muka KSC/STL-… diterima (KSC/CASH-…)."; ringkasan LPJ "Sisa Dikembalikan · KSC/CASH-…" ${rp(SISA)}; di daftar Kas Kecil tahap PD menjadi "Selesai"`, async () => {
      await bukaPd();
      await kb.shotSorot(r, "lpj-sisa-terbuka", r.tid("stl-return-btn"), { locator: r.tid("stl-detail") });
      await r.tid("stl-return-btn").click();
      await r.tid("stl-return-modal").waitFor();
      await r.tid("stl-return-modal-account-sole").waitFor();
      await kb.shotSorot(r, "form-terima-sisa", r.tid("stl-return-modal-submit"), { locator: r.tid("stl-return-modal") });
      await r.tid("stl-return-modal-submit").click();
      const msg = await kb.konfirmasi(r, "stl-return-confirm");
      assert(msg.includes(rp(SISA)) && msg.includes("Kas Toko KSC"), `konfirmasi: ${msg}`);
      await toast(`Sisa uang muka ${stl.number} diterima`);
      await r.idle(300);
      const lbl = await kb.teks(r, "stl-detail-sisa-label");
      assert(/Sisa Dikembalikan · KSC\/CASH-/.test(lbl) && (await kb.teks(r, "stl-detail-sisa")) === rp(SISA), `ringkasan sisa: ${lbl}`);
      await r.shot("sisa-diterima", { locator: r.tid("stl-detail") });
      await r.tid("pc-detail-modal-close-x").click();
      await r.tid("pc-search").fill(k.pd);
      await r.page.waitForFunction((id) => /Selesai/.test(document.querySelector(`[data-testid="pc-row-stage-${id}"]`)?.innerText || ""), k.pd_id);
      await r.shot("pd-selesai");
      return lbl;
    });

  await r.step(10, "Finance", "Cek jurnal pengembalian sisa: Buku Besar › Jurnal → ketik nomor LPJ → klik baris sumber \"Kas\" (Kas masuk · Pengembalian sisa uang muka …)",
    `Jurnal: 1-1110 Kas Kecil Debit ${rp(SISA)} · 1-1400 Uang Muka Kredit ${rp(SISA)}. Uang muka PD kembali nol: Rp 500.000 (cair) − ${rp(PAKAI)} (LPJ) − ${rp(SISA)} (sisa) = Rp 0`, async () => {
      const s = mongo(`return db.cash_advance_settlements.findOne({id:"${stl.id}"},{_id:0,sisa_dikembalikan:1,status:1})`);
      assert(s.sisa_dikembalikan.status === "returned", "sisa belum returned");
      sisaKas = kb.kas(s.sisa_dikembalikan.cash_txn_id);
      assert(sisaKas.direction === "in" && Math.abs(sisaKas.amount - SISA) < 0.01 && sisaKas.account_id === kasToko0.id, "kas masuk sisa");
      const je = kb.seimbang(kb.jurnal("cash_transaction", sisaKas.id), "jurnal pengembalian");
      assert(kb.adaBaris(je, "1-1110", "D", SISA) && kb.adaBaris(je, "1-1400", "K", SISA), kb.teksJurnal(je));
      // Saldo 1-1400 dari tiga jurnal PD ini = 0 (D cair − K LPJ − K sisa).
      const ids = [ca.disbursement.cash_txn_id, stl.id, sisaKas.id];
      const net = mongo(`let n=0; db.journal_entries.find({source_id:{$in:${JSON.stringify(ids)}},status:{$ne:"void"}}).forEach(j=>j.lines.forEach(l=>{if(l.account_code==="1-1400") n+= (l.debit||0)-(l.credit||0);})); return Math.round(n*100)/100;`);
      assert(Math.abs(net) < 0.01, `saldo uang muka PD bukan 0: ${net}`);
      await kb.lihatJurnal(r, stl.number, je, "jurnal-pengembalian");
      return `${kb.teksJurnal(je)} · saldo uang muka PD = ${rp(net)}`;
    });

  await r.step(11, "Finance", "Keuangan › Kas & Bank › Rekening & Saldo → klik kartu Kas Toko KSC → tab Mutasi",
    `Ada baris keluar ${rp(k.nominal)} (Pencairan ${k.pd}) dan baris masuk ${rp(SISA)} (Pengembalian sisa uang muka) — bersih Kas Toko turun ${rp(PAKAI)} karena transaksi Anda`, async () => {
      await kb.menu(r, "bank-accounts");
      await r.tid(`bank-card-${kasToko0.id}`).click();
      await r.tid("bank-ledger").waitFor();
      const keluar = r.tid(`bank-ledger-row-${ca.disbursement.cash_txn_id}`);
      const masuk = r.tid(`bank-ledger-row-${sisaKas.id}`);
      await keluar.waitFor(); await masuk.waitFor();
      assert((await kb.isi(keluar)).includes(rp(k.nominal)), "baris keluar");
      assert((await kb.isi(masuk)).includes(rp(SISA)), "baris masuk");
      await kb.sorot(keluar); await kb.sorot(masuk);
      await masuk.scrollIntoViewIfNeeded();
      await r.shot("mutasi-kas-toko", { locator: r.tid("bank-ledger") });
      const toko = await kb.rekening(akunPeserta(NO), "Kas Toko KSC");
      return `saldo Kas Toko ${rp(kasToko0.balance)} → ${rp(toko.balance)} (selisih ${rp(toko.balance - kasToko0.balance)}; termasuk transaksi peserta lain bila ada)`;
    });

  await r.finish();
})();
