// F10 · Rekonsiliasi Bank — tempel mutasi rekening koran BCA (3 baris dari transaksi peserta sendiri), pratinjau &
// impor, cocokkan otomatis (kode bayar), cocokkan manual satu baris (biaya F09), bukukan biaya administrasi bank, lalu
// baca ringkasan. Cek buku: mutasi tertaut ke kas yang benar, kas "Terekonsiliasi", jurnal biaya bank seimbang.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/F10_rekonsiliasi_bank.js     (peserta 03; jalankan F09 lebih dulu)
//   KN_PESERTA=35 node …/F10_rekonsiliasi_bank.js
// Akun BCA dipakai bersama semua peserta & agen lain: uji hanya mencocokkan/menilai baris milik peserta ini
// (keterangan memuat "LATIHAN NN"); hasil "Cocokkan otomatis" orang lain atas baris kita juga diterima.
const { Run, assert, kartu, peserta, akunPeserta, rp, mongo, sleep, api } = require("./lib.js");
const kb = require("./kasbank_lib.js");

const NO = peserta("03");
const BIAYA_ADM = 15000;

(async () => {
  const r = await new Run("F10", "Rekonsiliasi Bank — impor mutasi, cocokkan otomatis & manual, biaya bank").start();
  const me = akunPeserta(NO);
  const k = kartu(NO)["c_kas:kwitansi_transfer"];
  if (!k) { r.note(`Kartu peserta ${NO} belum punya c_kas:kwitansi_transfer — jalankan seed --hanya c_kas:`); await r.finish(); return; }
  const kode = k.kode_bayar || (mongo(`return db.payment_codes.findOne({order_id:"${k.so_id}",status:{$ne:"batal"}},{_id:0,code:1})`) || {}).code;
  const bca = await kb.rekening(me, "BCA Operasional KSC");
  // Biaya F09 milik peserta (Transaksi Kas · Keluar · BCA · "… — Latihan NN"), terbaru yang belum tercocok.
  const f09 = mongo(`return db.cash_transactions.find({entity_id:"ent_ksc",account_id:"${bca.id}",direction:"out",ref_type:"manual",
    status:{$ne:"void"},description:{$regex:"Latihan ${NO}$"},reconciled_amount:{$not:{$gte:0.01}}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0] || null`);
  if (!f09) {
    r.note(`Transaksi F09 peserta ${NO} (Keluar · BCA · "… — Latihan ${NO}", belum tercocok) tidak ada — jalankan F09 dulu.`);
    await r.finish(); return;
  }
  const tgl = kb.hariIni();
  const TEKS = [
    "Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo",
    `${tgl.bca},TRSF E-BANKING CR ${kode} LATIHAN ${NO} TOKO KAIN PESERTA ${NO},0000,"${kb.nominalBca(k.nominal)}",CR,0`,
    `${tgl.bca},TRSF E-BANKING DB EKSPEDISI LATIHAN ${NO},0000,"${kb.nominalBca(f09.amount)}",DB,0`,
    `${tgl.bca},BIAYA ADM LATIHAN ${NO},0000,"${kb.nominalBca(BIAYA_ADM)}",DB,0`,
  ].join("\n");
  const baris = {};
  const cariBaris = () => {
    const rows = mongo(`return db.bank_statement_lines.find({bank_account_id:"${bca.id}",description:{$regex:"LATIHAN ${NO}( |$)"},
      stmt_date:"${tgl.iso}"},{_id:0,id:1,description:1,status:1,amount:1,direction:1,allocations:1,charge:1,import_source:1,match_type:1}).toArray()`);
    for (const x of rows) {
      if (/^TRSF E-BANKING CR/.test(x.description)) baris.cr = x;
      else if (/EKSPEDISI/.test(x.description)) baris.f09 = x;
      else if (/^BIAYA ADM/.test(x.description)) baris.adm = x;
    }
    return rows.length;
  };
  const status = (id) => kb.teks(r, `recon-status-${id}`);
  const tungguStatus = (id, label) => kb.tunggu(r, `recon-status-${id}`, label);
  const saring = async () => {
    await r.tid("recon-lines-search").fill(`LATIHAN ${NO}`);
    await r.idle(300);
  };

  await r.step(1, "Finance", "Login akun peserta → Keuangan › Kas & Bank › Rekonsiliasi → pilih rekening BCA Operasional KSC",
    "Kartu ringkasan: Rekening (bersih) · Buku (bersih) · Tercocok · Perlu keputusan · Dana titipan · Selisih rekening vs buku; tab Mutasi & Pencocokan", async () => {
      assert(kode, "kode bayar pesanan kwitansi transfer tidak ditemukan");
      await r.login(me);
      await kb.menu(r, "bank-reconciliation");
      await kb.pilih(r, "recon-account-select", bca.id);
      await r.tid("recon-summary").waitFor();
      await kb.shotSorot(r, "rekonsiliasi-awal", r.tid("recon-import-toggle"));
      return `kas F09 ${f09.number} ${rp(f09.amount)} · kwitansi ${k.kwitansi} ${k.kas} ${rp(k.nominal)} · kode bayar ${kode}`;
    });

  await r.step(2, "Finance", "Klik [[Impor mutasi bank]] → *Template bank*: BCA — Rekening Koran (CSV) · CSV → tempel 4 baris teks rekening koran (lihat kotak teks) → [[Pratinjau]]",
    `"Terbaca 3 baris memakai template BCA — Rekening Koran (CSV) · masuk ${rp(k.nominal)} · keluar ${rp(f09.amount + BIAYA_ADM)}"; tabel pratinjau 3 baris (Masuk / Keluar)`, async () => {
      await r.tid("recon-import-toggle").click();
      await r.tid("recon-import-panel").waitFor();
      const fmts = await (await api(me)).get("/bank-reconciliation/formats", kb.KSC);
      const fBca = fmts.find((f) => f.bank_code === "bca" && (f.file_kind || "csv") === "csv");
      assert(fBca, "template BCA tidak ada");
      await kb.pilih(r, "recon-format-select", fBca.id);
      await r.tid("recon-raw").fill(TEKS);
      await r.tid("recon-preview-btn").click();
      const t = await kb.tunggu(r, "recon-preview", /Terbaca 3 baris/);
      assert(t.includes("BCA — Rekening Koran (CSV)") && t.includes(rp(k.nominal)) && t.includes(rp(f09.amount + BIAYA_ADM)), `pratinjau: ${t.slice(0, 200)}`);
      await kb.shotSorot(r, "pratinjau-impor", r.tid("recon-import-submit"), { locator: r.tid("recon-import-panel") });
      return t.split("Tanggal")[0];
    });

  await r.step(3, "Finance", "Klik [[Impor]]",
    "Pesan \"Impor BCA — Rekening Koran (CSV): 3 baris baru, 0 dilewati (sudah pernah masuk).\"; kartu Rekening (bersih) menyebut \"Impor terakhir: tempel baris oleh <nama Anda>\"", async () => {
      await r.tid("recon-import-submit").click();
      const t = await kb.tunggu(r, "recon-notice", /Impor BCA/);
      assert(/3 baris baru, 0 dilewati/.test(t), `impor: ${t}`);
      assert(cariBaris() === 3, "3 baris mutasi peserta tidak tersimpan");
      assert(Object.values(baris).every((x) => x.import_source === "tempel"), "asal mutasi bukan 'tempel'");
      const src = await kb.teks(r, "recon-statement-source");
      assert(/tempel baris/.test(src), `asal mutasi di kartu: ${src}`);
      await saring();
      await r.tid(`recon-line-${baris.cr.id}`).waitFor();
      await r.shot("mutasi-terimpor", { locator: r.tid("recon-lines-table") });
      await kb.shotSorot(r, "tombol-cocokkan-otomatis", r.tid("recon-auto-match"));
      return t;
    });

  await r.step(4, "Finance", "Klik [[Cocokkan otomatis]] → cari \"LATIHAN NN\" di kotak cari daftar mutasi → klik angka Skor pada baris TRSF E-BANKING CR",
    `Pesan "Pencocokan otomatis: … tertaut (skor ≥ 80) …"; baris transfer masuk ${rp(k.nominal)} berstatus Tercocok · satu-satu · otomatis, Transaksi buku ${k.kas}; alasan skor menyebut "Kode bayar ${kode} cocok dengan pesanan ${k.so}"`, async () => {
      await r.tid("recon-auto-match").click();
      const t = await kb.tunggu(r, "recon-notice", /Pencocokan otomatis/, 60000);
      await saring();
      cariBaris();
      assert(baris.cr.status === "matched", `baris CR belum tercocok: ${baris.cr.status}`);
      assert((baris.cr.allocations || []).some((a) => a.txn_id === k.kas_id), "baris CR tertaut ke kas lain");
      await tungguStatus(baris.cr.id, /^Tercocok$/);
      const row = await kb.isi(r.tid(`recon-line-${baris.cr.id}`));
      assert(row.includes(k.kas), `transaksi buku di baris: ${row}`);
      await r.tid(`recon-score-${baris.cr.id}`).click();
      const why = await kb.teks(r, `recon-score-${baris.cr.id}-explain`);
      assert(why.includes(`Kode bayar ${kode}`), `alasan skor: ${why}`);
      await kb.sorot(r.tid(`recon-matchbtn-${baris.f09.id}`));
      await r.shot("cocok-otomatis", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-matchbtn-${baris.f09.id}`));
      await r.tid(`recon-score-${baris.cr.id}`).click();
      assert(baris.f09.status === "unmatched", `baris biaya F09 seharusnya belum tercocok: ${baris.f09.status}`);
      return `${t} · ${row.slice(0, 120)}`;
    });

  await r.step(5, "Finance", `Pada baris TRSF E-BANKING DB EKSPEDISI (${rp(f09.amount)}) klik [[Cocokkan]] → pada kandidat ${f09.number} (nominal sama, skor tertinggi) klik [[Tautkan]]`,
    `Pop-up "Cocokkan mutasi bank" berisi kandidat ${f09.number} · nominal ${rp(f09.amount)} · skor 60 (Nominal sama, Tanggal sama); sesudah Tautkan: pesan "Mutasi ditautkan (skor 60)." dan baris Tercocok`, async () => {
      assert((await status(baris.f09.id)) === "Perlu keputusan", "status awal baris F09");
      await r.tid(`recon-matchbtn-${baris.f09.id}`).click();
      await r.tid("recon-match-modal").waitFor();
      const cand = r.tid(`recon-cand-${f09.id}`);
      await cand.waitFor();
      const ct = await kb.isi(cand);
      assert(ct.includes(f09.number) && ct.includes(rp(f09.amount)) && /skor 60/.test(ct), `kandidat: ${ct}`);
      await kb.shotSorot(r, "cocok-manual", r.tid(`recon-pick-cand-${f09.id}`), { locator: r.tid("recon-match-modal") });
      await r.tid(`recon-pick-cand-${f09.id}`).click();
      const t = await kb.tunggu(r, "recon-notice", /Mutasi ditautkan/);
      await r.tid("recon-match-modal").waitFor({ state: "detached" });
      await saring();
      await tungguStatus(baris.f09.id, /^Tercocok$/);
      cariBaris();
      assert((baris.f09.allocations || []).some((a) => a.txn_id === f09.id), "baris F09 tertaut ke kas lain");
      return `${t} · ${ct}`;
    });

  await r.step(6, "Finance", `Pada baris BIAYA ADM (${rp(BIAYA_ADM)}, keluar) klik [[Catat biaya bank]] → konfirmasi [[Catat biaya bank]]`,
    `Dialog "Catat biaya bank?" menyebut nominal ${rp(BIAYA_ADM)} dan PT; sesudah konfirmasi pesan "Biaya bank dibukukan (Dr Beban Adm Bank / Cr Bank)."; baris Tercocok dengan keterangan "Biaya bank · akun 6-8000" dan Transaksi buku KSC/CASH-… baru`, async () => {
      await kb.shotSorot(r, "tombol-biaya-bank", r.tid(`recon-charge-${baris.adm.id}`), { locator: r.tid("recon-lines-table") });
      await r.tid(`recon-charge-${baris.adm.id}`).click();
      await r.tid("recon-charge-confirm").waitFor();
      await r.shot("konfirmasi-biaya-bank", { locator: r.tid("recon-charge-confirm").locator(".modal-card") });
      const msg = await kb.konfirmasi(r, "recon-charge-confirm");
      assert(msg.includes(rp(BIAYA_ADM)) && /Sukacita/.test(msg), `konfirmasi biaya bank: ${msg}`);
      const t = await kb.tunggu(r, "recon-notice", /Biaya bank dibukukan/);
      await saring();
      await tungguStatus(baris.adm.id, /^Tercocok$/);
      const row = await kb.isi(r.tid(`recon-line-${baris.adm.id}`));
      assert(/Biaya bank · akun 6-8000/.test(row), `baris biaya: ${row}`);
      await kb.sorot(r.tid(`recon-line-${baris.adm.id}`));
      await r.shot("biaya-bank", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${baris.adm.id}`));
      return t;
    });

  await r.step(7, "Finance", `Cek jurnal biaya bank: Akuntansi & Pajak › Buku Besar › Jurnal → ketik "BIAYA ADM LATIHAN ${NO}" → klik baris bersumber "Kas"`,
    `Jurnal "Kas out · Biaya bank — BIAYA ADM LATIHAN ${NO}": 6-8000 Beban Administrasi Bank Debit ${rp(BIAYA_ADM)} · 1-1100 Kas Besar / Bank Kredit ${rp(BIAYA_ADM)}. Baris yang hanya DICOCOKKAN (transfer masuk & biaya F09) tidak menerbitkan jurnal baru`, async () => {
      cariBaris();
      for (const id of [k.kas_id, f09.id]) {
        const c = kb.kas(id);
        assert(Math.abs(Number(c.reconciled_amount || 0) - Number(c.amount)) < 0.01, `${c.number} belum terekonsiliasi penuh`);
      }
      const ch = baris.adm.charge || {};
      const c = kb.kas(ch.cash_txn_id);
      assert(c && c.direction === "out" && Math.abs(c.amount - BIAYA_ADM) < 0.01 && c.account_id === bca.id, "kas biaya bank");
      const je = kb.seimbang(kb.jurnal("cash_transaction", c.id), "jurnal biaya bank");
      assert(kb.adaBaris(je, "6-8000", "D", BIAYA_ADM) && kb.adaBaris(je, "1-1100", "K", BIAYA_ADM), kb.teksJurnal(je));
      // Pencocokan tidak menerbitkan jurnal: kas kwitansi & kas F09 tetap satu jurnal masing-masing.
      for (const id of [k.kas_id, f09.id]) assert(kb.jurnal("cash_transaction", id).length === 1, `jurnal ganda untuk kas ${id}`);
      await kb.lihatJurnal(r, `BIAYA ADM LATIHAN ${NO}`, je, "jurnal-biaya-bank");
      return `${c.number} · ${kb.teksJurnal(je)}`;
    });

  await r.step(8, "Finance", "Saring *Mutasi dari tanggal* & *sampai tanggal* = hari ini, lalu klik kartu [[Tercocok]]",
    "Kartu ringkasan mengikuti periode hari ini; daftar hanya baris Tercocok — ketiga baris LATIHAN NN ada di sana; Selisih rekening vs buku = mutasi bersih − buku bersih hari ini (semua peserta)", async () => {
      await kb.menu(r, "bank-reconciliation");
      await kb.pilih(r, "recon-account-select", bca.id);
      await r.tid("recon-summary").waitFor();
      for (const id of ["recon-filter-start", "recon-filter-end"]) {
        await r.tid(id).click();
        const pop = r.tid(`${id}-popover`);
        await pop.waitFor();
        const hari = String(Number(tgl.iso.slice(8, 10)));   // tombol tanggal hari ini (bukan hari bulan lain)
        await pop.locator('button[name="day"]:not(.day-outside)').filter({ hasText: new RegExp(`^${hari}$`) }).first().click();
        await sleep(300);
      }
      await r.tid("recon-card-matched").click();
      await r.idle(400);
      await saring();
      for (const x of [baris.cr, baris.f09, baris.adm]) await r.tid(`recon-line-${x.id}`).waitFor();
      const s = await (await api(me)).get(`/bank-reconciliation/summary?bank_account_id=${bca.id}&start=${tgl.iso}&end=${tgl.iso}`, kb.KSC);
      assert(Number(await kb.teks(r, "recon-matched")) === s.matched, "kartu Tercocok ≠ API");
      const dif = await kb.teks(r, "recon-difference");
      const angka = (x) => Number(String(x).replace(/[^0-9]/g, "")) * (/-/.test(String(x)) ? -1 : 1);
      assert(Math.abs(angka(dif) - s.difference) <= 1, `kartu selisih ${dif} ≠ API ${rp(s.difference)}`);   // ±1: pembulatan sen
      await r.tid("recon-filter-bar").scrollIntoViewIfNeeded();
      await r.page.evaluate(() => window.scrollTo(0, 0));
      await kb.sorot(r.tid("recon-card-matched"));
      await r.shot("ringkasan-periode");
      await kb.lepas(r.tid("recon-card-matched"));
      return `hari ini: rekening bersih ${rp(s.statement.net)} · buku bersih ${rp(s.book.net)} · tercocok ${s.matched} · perlu keputusan ${s.unmatched_lines} · selisih ${rp(s.difference)}`;
    });

  await r.step(9, "Finance", "Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `Baris ${k.kas}, ${f09.number} dan kas biaya bank berstatus Rekonsiliasi "Terekonsiliasi"`, async () => {
      await kb.menu(r, "bank-accounts");
      await r.tid(`bank-card-${bca.id}`).click();
      await r.tid("bank-ledger").waitFor();
      const ids = [k.kas_id, f09.id, baris.adm.charge.cash_txn_id];
      for (const id of ids) {
        await r.tid(`bank-recon-status-${id}`).waitFor();
        assert((await kb.teks(r, `bank-recon-status-${id}`)) === "Terekonsiliasi", `status rekonsiliasi ${id}`);
      }
      for (const id of ids) await kb.sorot(r.tid(`bank-ledger-row-${id}`));
      await r.tid(`bank-ledger-row-${ids[2]}`).scrollIntoViewIfNeeded();
      await r.shot("mutasi-terekonsiliasi", { locator: r.tid("bank-ledger") });
    });

  r.note(`Teks rekening koran peserta ${NO}:\n${TEKS}`);
  await r.finish();
})();
