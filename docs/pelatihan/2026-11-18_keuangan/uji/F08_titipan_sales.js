// F08 · Titipan Sales — sales menagih tunai di toko pelanggan (kwitansi → titipan di tangan sales) lalu menyetor;
// Finance menerima setoran itu ke Kas Toko. Cek layar + buku (piutang pelanggan sudah turun saat kwitansi, kas baru masuk
// saat setoran diterima, jurnal Dr Kas / Cr Piutang Titipan Karyawan seimbang).
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/F08_titipan_sales.js       (peserta 03)
//   KN_PESERTA=33 node …/F08_titipan_sales.js
// Data awal: `scripts/latih_keuangan/c_kas.py` (kartu `c_kas:titipan_sales`: SO, kwitansi, titipan TTP, setoran STT).
const { Run, assert, kartu, peserta, akunPeserta, rp, mongo } = require("./lib.js");
const kb = require("./kasbank_lib.js");

const NO = peserta("03");

(async () => {
  const r = await new Run("F08", "Titipan Sales — terima setoran tunai sales ke Kas Toko").start();
  const k = kartu(NO)["c_kas:titipan_sales"];
  if (!k) { r.note(`Kartu peserta ${NO} belum punya c_kas:titipan_sales — jalankan seed --hanya c_kas:`); await r.finish(); return; }
  let toko = null; let dep = null;

  await r.step(1, "Finance", "Login akun peserta → Keuangan › Kas & Bank › Titipan Sales → bagian \"Setoran menunggu diterima\"",
    `Baris ${k.setoran}: Penyetor ${k.penyetor}, Jumlah ${rp(k.nominal)}, Catatan "Setoran tunai Latihan ${NO} · …"; tombol [[Terima setoran]] dan [[Tolak]]`, async () => {
      await r.login(akunPeserta(NO));
      toko = await kb.rekening(akunPeserta(NO), "Kas Toko KSC");
      await kb.menu(r, "cash-holdings");
      const row = r.tid(`cth-deposit-row-${k.setoran_id}`);
      await row.waitFor();
      const t = await kb.isi(row);
      assert(t.includes(k.setoran) && t.includes(rp(k.nominal)) && t.includes(`Latihan ${NO}`), `baris setoran: ${t}`);
      assert(await r.tid(`cth-receive-${k.setoran_id}`).isEnabled(), "tombol Terima setoran mati");
      await kb.shotSorot(r, "setoran-menunggu", r.tid(`cth-receive-${k.setoran_id}`), { locator: r.tid("cth-deposits") });
      return t;
    });

  await r.step(2, "Finance", `Di "Titipan belum disetor" ketik Latihan ${NO} di kotak cari → klik [[Lihat kwitansi]] pada ${k.penyetor}`,
    `Baris ${k.titipan}: Kwitansi ${k.kwitansi}, Pelanggan Latihan ${NO} · Toko Kain Peserta ${NO}, Belum disetor ${rp(k.nominal)}, Status Dipegang`, async () => {
      await r.tid("cth-search").fill(`Latihan ${NO}`);
      await r.idle(400);
      const holder = mongo(`return db.cash_holdings.findOne({id:"${k.titipan_id}"},{_id:0,holder_user_id:1})`).holder_user_id;
      await kb.shotSorot(r, "titipan-per-pemegang", r.tid(`cth-holder-open-${holder}`), { locator: r.tid("cth-holdings") });
      await r.tid(`cth-holder-open-${holder}`).click();
      const row = r.tid(`cth-holding-row-${k.titipan_id}`);
      await row.waitFor();
      const t = await kb.isi(row);
      assert(t.includes(k.kwitansi) && t.includes(`Latihan ${NO}`) && /Dipegang/.test(t), `baris titipan: ${t}`);
      await kb.sorot(row);
      await r.shot("titipan-dipegang", { locator: r.tid("cth-holdings") });
      await kb.lepas(row);
      return t;
    });

  await r.step(3, "Finance", `Cek jurnal kwitansi titipan: Akuntansi & Pajak › Buku Besar › Jurnal → ketik nomor kwitansi (${k.kwitansi}) → klik baris sumber "Titipan Tunai Sales"`,
    `Jurnal "Titipan tunai sales · Titipan tunai ${k.penyetor} · ${k.kwitansi} …": 1-1280 Piutang Titipan Karyawan Debit ${rp(k.nominal)} · 1-1200 Piutang Usaha Kredit ${rp(k.nominal)}. Piutang pelanggan sudah lunas, tetapi BELUM ada kas — uangnya masih di tangan sales`, async () => {
      const je = kb.seimbang(kb.jurnal("cash_holding", k.titipan_id), "jurnal titipan");
      assert(kb.adaBaris(je, "1-1280", "D", k.nominal) && kb.adaBaris(je, "1-1200", "K", k.nominal), kb.teksJurnal(je));
      const so = mongo(`return db.sales_orders.findOne({id:"${k.so_id}"},{_id:0,payment_status:1,paid_amount:1,grand_total:1})`);
      assert(so.payment_status === "paid", `status bayar ${k.so}: ${so.payment_status}`);
      const rc = mongo(`return db.ar_receipts.findOne({number:"${k.kwitansi}",entity_id:"ent_ksc"},{_id:0,id:1})`);
      const kasRc = mongo(`return db.cash_transactions.countDocuments({ref_type:"ar_receipt",ref_id:"${rc.id}",status:{$ne:"void"}})`);
      assert(kasRc === 0, "kwitansi titipan tidak boleh membuat kas");
      await kb.lihatJurnal(r, k.kwitansi, je, "jurnal-titipan");
      return `${kb.teksJurnal(je)} · ${k.so} ${so.payment_status}`;
    });

  await r.step(4, "Finance", `Klik [[Terima setoran]] pada ${k.setoran} → *Masuk ke rekening*: Kas Toko KSC → [[Terima setoran]] → konfirmasi [[Ya, terima setoran]]`,
    `Pesan "Setoran ${k.setoran} (${rp(k.nominal)}) diterima ke Kas Toko KSC."; baris hilang dari "Setoran menunggu diterima"`, async () => {
      await kb.menu(r, "cash-holdings");
      await r.tid(`cth-receive-${k.setoran_id}`).click();
      await r.tid("cth-receive-form").waitFor();
      assert((await kb.teks(r, "cth-receive-amount")) === rp(k.nominal), "jumlah di form");
      await kb.pilih(r, "cth-receive-account-select", toko.id);
      await kb.shotSorot(r, "form-terima-setoran", r.tid("cth-receive-form-submit"), { locator: r.tid("cth-receive-form") });
      await r.tid("cth-receive-form-submit").click();
      await r.tid("cth-receive-confirm").waitFor();
      await r.shot("konfirmasi-terima-setoran", { locator: r.tid("cth-receive-confirm").locator(".modal-card") });
      const msg = await kb.konfirmasi(r, "cth-receive-confirm");
      assert(msg.includes(rp(k.nominal)) && msg.includes("Kas Toko KSC") && msg.includes(k.setoran), `konfirmasi: ${msg}`);
      const t = await kb.tunggu(r, "cth-msg", `Setoran ${k.setoran}`);
      assert(t.includes(rp(k.nominal)) && t.includes("Kas Toko KSC") && /diterima/.test(t), `pesan: ${t}`);
      await r.tid(`cth-deposit-row-${k.setoran_id}`).waitFor({ state: "detached" });
      await r.shot("setoran-diterima");
      return t;
    });

  await r.step(5, "Finance", `Cek jurnal setoran: Buku Besar › Jurnal → ketik nomor setoran (${k.setoran}) → klik baris sumber "Kas"`,
    `Jurnal "Kas masuk · Setoran ${k.setoran} — ${k.penyetor}": 1-1110 Kas Kecil Debit ${rp(k.nominal)} · 1-1280 Piutang Titipan Karyawan Kredit ${rp(k.nominal)} — titipan sales kembali nol (titipan ${k.titipan} berstatus Disetor)`, async () => {
      dep = mongo(`return db.cash_deposits.findOne({id:"${k.setoran_id}"},{_id:0})`);
      assert(dep.status === "diterima" && dep.account_id === toko.id, `setoran: ${dep.status}`);
      const txn = kb.kas(dep.cash_txn_id);
      assert(txn.direction === "in" && Math.abs(txn.amount - k.nominal) < 0.01 && txn.account_id === toko.id, "kas setoran");
      const je = kb.seimbang(kb.jurnal("cash_transaction", txn.id), "jurnal setoran");
      assert(kb.adaBaris(je, "1-1110", "D", k.nominal) && kb.adaBaris(je, "1-1280", "K", k.nominal), kb.teksJurnal(je));
      const h = mongo(`return db.cash_holdings.findOne({id:"${k.titipan_id}"},{_id:0,status:1,amount:1,deposited_amount:1})`);
      assert(h.status === "disetor" && Math.abs(h.amount - h.deposited_amount) < 0.01, `titipan: ${h.status}`);
      await kb.lihatJurnal(r, k.setoran, je, "jurnal-setoran");
      return `${txn.number} · ${kb.teksJurnal(je)}`;
    });

  await r.step(6, "Finance", "Keuangan › Kas & Bank › Rekening & Saldo → klik kartu Kas Toko KSC → tab Mutasi",
    `Baris masuk ${rp(k.nominal)} "Setoran …" dari ${k.penyetor} di Kas Toko KSC`, async () => {
      await kb.menu(r, "bank-accounts");
      await r.tid(`bank-card-${toko.id}`).click();
      await r.tid("bank-ledger").waitFor();
      const row = r.tid(`bank-ledger-row-${dep.cash_txn_id}`);
      await row.waitFor();
      const t = await kb.isi(row);
      assert(t.includes(rp(k.nominal)), `baris mutasi: ${t}`);
      await kb.sorot(row);
      await row.scrollIntoViewIfNeeded();
      await r.shot("mutasi-kas-toko", { locator: r.tid("bank-ledger") });
      return t;
    });

  await r.finish();
})();
