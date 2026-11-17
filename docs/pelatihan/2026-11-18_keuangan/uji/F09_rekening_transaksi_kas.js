// F09 · Rekening & Saldo + Transaksi Kas — baca saldo per rekening, catat biaya operasional yang dibayar dari bank
// (Transaksi Kas · Keluar · Kas Besar/Bank · Operasional), cek saldo, mutasi rekening, dan jurnalnya di Buku Besar.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/F09_rekening_transaksi_kas.js     (peserta 03)
//   KN_PESERTA=33 node …/F09_rekening_transaksi_kas.js
// Nominal unik per peserta: Rp 300.000 + NN × Rp 10.000 (peserta 03 → Rp 330.000) — dipakai lagi di F10 (mutasi bank);
// selisih antar-peserta > 1% supaya transaksi peserta lain tidak ikut menjadi kandidat cocok.
const { Run, assert, peserta, akunPeserta, rp, num, mongo, sleep } = require("./lib.js");
const kb = require("./kasbank_lib.js");

const NO = peserta("03");
const NOMINAL = 300000 + Number(NO) * 10000;
const DESKRIPSI = `Ongkos ekspedisi kirim kain ke Toko Kain Peserta ${NO} — Latihan ${NO}`;

(async () => {
  const r = await new Run("F09", "Rekening & Saldo + Transaksi Kas — biaya operasional dibayar dari bank").start();
  const me = akunPeserta(NO);
  let bca0 = null; let txn = null;

  await r.step(1, "Finance", "Login akun peserta → Keuangan › Kas & Bank › Rekening & Saldo",
    "Lima kartu angka (Kas & Bank buku besar · Total Saldo Rekening · Saldo Bank · Saldo Kas · Mutasi Belum Dicocokkan) dan kartu rekening BCA Operasional KSC & Kas Toko KSC dengan saldo, uang masuk/keluar, jumlah transaksi", async () => {
      await r.login(me);
      await kb.menu(r, "bank-accounts");
      await r.tid("bank-cards").waitFor();
      // Saldo bisa bergerak karena peserta lain → bandingkan layar vs API dalam satu jendela waktu (ulang bila berubah).
      let ok = false; let info = "";
      for (let i = 0; i < 4 && !ok; i++) {
        const [bca, toko] = [await kb.rekening(me, "BCA Operasional KSC"), await kb.rekening(me, "Kas Toko KSC")];
        await r.tid("bank-refresh").click(); await r.idle(300);
        const cBca = await kb.isi(r.tid(`bank-card-${bca.id}`));
        const cToko = await kb.isi(r.tid(`bank-card-${toko.id}`));
        const kBank = await kb.teks(r, "bank-kpi-bank-value"); const kKas = await kb.teks(r, "bank-kpi-cash-value");
        ok = cBca.includes(rp(bca.balance)) && cToko.includes(rp(toko.balance)) && kBank === rp(bca.balance) && kKas === rp(toko.balance);
        info = `BCA ${rp(bca.balance)} · Kas Toko ${rp(toko.balance)} · KPI bank ${kBank} · KPI kas ${kKas}`;
        bca0 = bca;
        if (!ok) await sleep(800);
      }
      assert(ok, `kartu ≠ API: ${info}`);
      assert(/Rp/.test(await kb.teks(r, "bank-kpi-gl-value")), "KPI buku besar kosong");
      await kb.shotSorot(r, "rekening-saldo", r.tid(`bank-card-${bca0.id}`));
      return info;
    });

  await r.step(2, "Finance", "Klik kartu BCA Operasional KSC → tab Mutasi",
    "Daftar mutasi: tanggal, nomor & keterangan, Masuk, Keluar, Saldo berjalan, status Rekonsiliasi (Terekonsiliasi / Sebagian / Belum); kepala: Saldo & Terekonsiliasi", async () => {
      await r.tid(`bank-card-${bca0.id}`).click();
      await r.tid("bank-ledger").waitFor();
      await r.page.waitForSelector('[data-testid^="bank-ledger-row-"]');
      const head = await kb.isi(r.tid("bank-ledger").locator(".section-head"));
      assert(/Saldo Rp/.test(head) && /Terekonsiliasi Rp/.test(head), `kepala mutasi: ${head}`);
      await r.shot("mutasi-bca", { locator: r.tid("bank-ledger") });
      await r.tid("bank-ledger-close").click();
      return head;
    });

  await r.step(3, "Finance", "Buka tab Transaksi Kas → klik [[Catat Transaksi]]",
    "Pop-up \"Catat Transaksi Kas\" dengan banner \"Dicatat di buku Sukacita Textile\", isian Jenis Kas, Arah, Nominal, Kategori, Rekening, Deskripsi", async () => {
      await r.tid("hub-tab-cash-management").click();
      await r.idle();
      await r.tid("cash-besar-card").waitFor();
      await r.idle(400);
      await kb.shotSorot(r, "transaksi-kas", r.tid("create-cash-button"));
      await r.tid("create-cash-button").click();
      await r.tid("cash-form").waitFor();
      assert(/Sukacita/.test(await kb.teks(r, "cash-form-scope")), "banner PT form");
    });

  await r.step(4, "Finance", `Isi *Jenis Kas*: Kas Besar / Bank (transfer) · *Arah*: Keluar (pengeluaran) · *Nominal*: ${rp(NOMINAL)} · *Kategori*: Operasional · *Deskripsi*: ${DESKRIPSI} → [[Catat Transaksi]]`,
    `Rekening terisi otomatis "BCA Operasional KSC" (satu-satunya rekening bank); notifikasi "Transaksi KSC/CASH-… (keluar) dicatat."`, async () => {
      await kb.pilih(r, "cash-type-select", "kas_besar");
      await kb.pilih(r, "cash-direction-select", "out");
      await r.tid("cash-amount-input").fill(String(NOMINAL));
      await kb.pilih(r, "cash-category-select", "operasional");
      await r.tid("cash-account-sole").waitFor();
      assert((await kb.teks(r, "cash-account")).includes("BCA Operasional KSC"), "rekening bukan BCA");
      await r.tid("cash-description-input").fill(DESKRIPSI);
      await sleep(400);
      await kb.shotSorot(r, "form-transaksi-kas", r.tid("submit-cash-button"), { locator: r.tid("cash-form") });
      await r.tid("submit-cash-button").click();
      const t = await kb.tunggu(r, "cash-notice", /Transaksi KSC\/CASH-\d+ \(keluar\) dicatat/);
      const nomor = t.match(/KSC\/CASH-\d+/)[0];
      txn = mongo(`return db.cash_transactions.findOne({number:"${nomor}",entity_id:"ent_ksc"},{_id:0})`);
      assert(txn && txn.direction === "out" && Math.abs(txn.amount - NOMINAL) < 0.01 && txn.account_id === bca0.id, "transaksi di DB");
      return t;
    });

  await r.step(5, "Finance", "Ketik nomor transaksi di kotak cari daftar transaksi kas",
    `Baris: nomor KSC/CASH-…, keterangan "${DESKRIPSI}", kategori Operasional, Kas Besar · Sukacita, nominal −${rp(NOMINAL)} (merah)`, async () => {
      await r.tid("cash-txn-search").fill(txn.number);
      const row = r.tid(`cash-row-${txn.id}`);
      await row.waitFor();
      const t = await kb.isi(row);
      assert(t.includes(DESKRIPSI) && /Operasional/.test(t) && /Kas Besar/.test(t) && t.includes(rp(NOMINAL)), `baris: ${t}`);
      await kb.sorot(row);
      await r.shot("daftar-transaksi-kas");
      await kb.lepas(row);
      return t;
    });

  await r.step(6, "Finance", "Cek buku: jurnal transaksi kas",
    `Jurnal Dr 6-4000 Beban Operasional Lainnya ${rp(NOMINAL)} / Cr 1-1100 Kas Besar / Bank ${rp(NOMINAL)} — seimbang`, async () => {
      const je = kb.seimbang(kb.jurnal("cash_transaction", txn.id), "jurnal transaksi kas");
      assert(kb.adaBaris(je, "6-4000", "D", NOMINAL) && kb.adaBaris(je, "1-1100", "K", NOMINAL), kb.teksJurnal(je));
      return kb.teksJurnal(je);
    });

  await r.step(7, "Finance", "Kembali ke Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `Baris baru keluar ${rp(NOMINAL)} dengan status Rekonsiliasi "Belum"; saldo BCA berkurang ${rp(NOMINAL)} oleh transaksi ini`, async () => {
      await r.tid("hub-tab-bank-accounts").click();
      await r.idle();
      await r.tid(`bank-card-${bca0.id}`).click();
      const row = r.tid(`bank-ledger-row-${txn.id}`);
      await row.waitFor();
      const t = await kb.isi(row);
      assert(t.includes(rp(NOMINAL)) && /Belum/.test(t), `baris mutasi: ${t}`);
      await kb.sorot(row);
      await row.scrollIntoViewIfNeeded();
      await r.shot("mutasi-bca-baru", { locator: r.tid("bank-ledger") });
      await r.tid("bank-ledger-close").click();
      await r.tid("bank-ledger").waitFor({ state: "detached" });
      const bca1 = await kb.rekening(me, "BCA Operasional KSC");
      return `saldo BCA ${rp(bca0.balance)} → ${rp(bca1.balance)} (termasuk transaksi peserta lain bila ada)`;
    });

  await r.step(8, "Finance", `Akuntansi & Pajak › Buku Besar › Jurnal → ketik "Latihan ${NO}" di kotak cari → klik baris jurnal bersumber ${"KSC/CASH-…"}`,
    `Rincian jurnal: 6-4000 Beban Operasional Lainnya Debit ${rp(NOMINAL)} · 1-1100 Kas Besar / Bank Kredit ${rp(NOMINAL)} · Total debit = total kredit`, async () => {
      const je = kb.jurnal("cash_transaction", txn.id)[0];
      const t = await kb.lihatJurnal(r, `Latihan ${NO}`, je, "jurnal-transaksi-kas");
      assert(t.includes(rp(NOMINAL)), `rincian jurnal: ${t.slice(0, 300)}`);
      return je.number;
    });

  await r.finish();
})();
