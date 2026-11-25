// F14 — Pesanan Sample berbayar: Finance memastikan uang masuk (kwitansi) lalu menyetujui pembayaran sample.
// Data awal `d_hutang:sample_berbayar`: Sales membuat SOS berbayar untuk pelanggan kedua peserta ("Latihan NN · Butik
// Sample Peserta NN"), status Menunggu ACC bayar. Kwitansi sebelum barang dikirim dijurnal Kas/Bank (D) / Uang Muka
// Pelanggan (K); persetujuan bayar tidak menjurnal — ia melepas pesanan ke Admin Sample (siap diteruskan ke gudang).
//   node docs/pelatihan/2026-11-18_keuangan/uji/F14_sample_berbayar.js        (bawaan peserta 04; KN_PESERTA=45 …)
const { Run, assert, rp, num, kartu, peserta, akunPeserta, mongo } = require("./lib");
const { REK_BCA, jurnalDari, cekJurnal, tungguTeks, menu, sorot, lepas, klikPotret } = require("./hutang_lib");

(async () => {
  const no = peserta("04");
  const k = kartu(no);
  const s = k["d_hutang:sample_berbayar"];
  const r = await new Run("F14", "Pesanan Sample berbayar — terima uang & setujui bayar").start();
  if (!s) { r.note(`Kartu peserta ${no} belum punya d_hutang:sample_berbayar`); await r.finish(); return; }
  const sos0 = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,number:1,status:1,grand_total:1,ppn_amount:1,customer_name:1,sample_payment_status:1,payment_status:1})`);
  const total = Number(sos0.grand_total);
  const ref = `TRF-SAMPLE-${no}`;
  r.note(`Peserta ${no} · ${sos0.number} · ${sos0.customer_name} · ${rp(total)} · ${sos0.status}/${sos0.sample_payment_status}`);
  let rc = null;

  await r.step(1, "Finance", "Login akun Finance peserta → Meja Finance. Pada kartu [[Sample berbayar menunggu ACC bayar]] cari nomor SOS", "Baris SOS peserta: pelanggan Butik Sample, nilai = total sample, tombol [[Tinjau]]", async () => {
    await r.login(akunPeserta(no));
    await r.tid("finance-desk").waitFor();
    const kartuS = r.tid("fin-desk-queue-sample_bayar");
    await kartuS.waitFor({ timeout: 20000 });
    await r.tid("fin-desk-search-sample_bayar").fill(sos0.number).catch(() => {});
    const row = r.tid(`fin-desk-sample_bayar-row-${s.sos_id}`);
    await row.waitFor();
    await row.scrollIntoViewIfNeeded();
    const t = (await row.innerText()).replace(/\s+/g, " ");
    assert(t.includes(sos0.customer_name), `baris: ${t}`);
    assert(num(await r.text(`fin-desk-sample_bayar-value-${s.sos_id}`)) === Math.round(total), "nilai baris ≠ total SOS");
    await sorot(r.tid(`fin-desk-sample_bayar-action-${s.sos_id}`));
    await r.shot("meja-sample-berbayar", { locator: kartuS });
    await lepas(r.tid(`fin-desk-sample_bayar-action-${s.sos_id}`));
    return t;
  });

  await r.step(2, "Finance", "Klik [[Tinjau]] → di pop-up rincian baris klik [[Tinjau]]", "Penjualan › Pesanan Sample terbuka di SOS itu: BERBAYAR, Menunggu ACC bayar, rincian Subtotal · PPN · Total, catatan \"Pembayaran belum disetujui Finance/Admin Sample.\"", async () => {
    // Meja gelombang 1 — aksi pindah layar membuka pop-up rincian dulu; tombol aksinya di sana yang membuka layar.
    await r.tid(`fin-desk-sample_bayar-action-${s.sos_id}`).click();
    await r.tid("fin-desk-detail-action").click();
    await r.tid("sample-orders-view").waitFor();
    await tungguTeks(r, "sample-detail-number", new RegExp(sos0.number.replace(/[/]/g, "\\/")));
    const tot = await r.text("sample-detail-totals");
    assert(num(tot.split("Total").pop()) === Math.round(total), `total rincian: ${tot}`);
    assert(/belum disetujui/.test(await r.text("sample-detail-payment")), "catatan pembayaran bukan 'belum disetujui'");
    await r.tid("sample-detail-approve-payment").waitFor();
    await sorot(r.tid("sample-detail-payment"));
    await r.shot("rincian-sample");
    await lepas(r.tid("sample-detail-payment"));
    return tot;
  });

  await r.step(3, "Finance", "Pastikan uang sudah masuk: Penjualan › Pelanggan, cari \"Butik Sample Peserta\" + nomor peserta, buka pelanggan → [[Terima pembayaran]]", "Form Terima pembayaran: pelanggan Butik Sample, tagihan terbuka = SOS (Belum lunas = total sample)", async () => {
    await menu(r, "penjualan", "customers-crm");
    await r.tid("customer-list").waitFor();
    await r.tid("customer-search").fill(`Butik Sample Peserta ${no}`);
    const row = r.tid(`customer-row-${s.pelanggan_id}`);
    await row.waitFor({ timeout: 15000 });
    await r.idle(400);
    await klikPotret(r, row, "cari-pelanggan-sample");
    await r.tid("customer-360-receive").waitFor({ timeout: 15000 });
    await r.idle(600);
    await klikPotret(r, r.tid("customer-360-receive"), "kartu-pelanggan-terima");
    await r.tid("ar-receipt-modal").waitFor();
    await r.tid(`ar-receipt-order-${s.sos_id}`).waitFor();
    const o = (await r.tid(`ar-receipt-order-${s.sos_id}`).innerText()).replace(/\s+/g, " ");
    assert(o.includes(sos0.number) && o.includes(rp(total).replace("Rp ", "")), `tagihan terbuka: ${o}`);
    return o;
  });

  await r.step(4, "Finance", `Isi *Nominal diterima* ${rp(total)} · *Cara bayar* Transfer bank · *Rekening penerima* BCA Operasional KSC · *No. referensi* ${ref} · alokasi [[Tertua dulu]] → [[Simpan kwitansi]] → [[Ya, simpan]]`, "Kwitansi KSC/AR-… tercatat; SOS berstatus bayar Lunas", async () => {
    await r.tid("ar-receipt-amount").fill(String(Math.round(total)));
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'), null, { timeout: 15000 }).catch(() => {});
    await r.idle(600);
    const acc = r.tid("ar-receipt-account-field");
    const accText = (await acc.innerText().catch(() => "")).replace(/\s+/g, " ");
    if (!accText.includes(REK_BCA)) {
      const sel = r.page.locator('[data-testid="ar-receipt-account-field"] [role="combobox"], [data-testid="ar-receipt-account"]').first();
      await sel.click();
      await r.page.getByRole("option", { name: new RegExp(REK_BCA) }).first().click();
    }
    await r.tid("ar-receipt-reference").fill(ref);
    await r.idle(800);
    assert(num(await r.text("ar-receipt-total")) === Math.round(total), "Total diterima ≠ total sample");
    await sorot(r.tid("ar-receipt-submit"));
    await r.shot("form-kwitansi-sample");
    await lepas(r.tid("ar-receipt-submit"));
    await r.tid("ar-receipt-submit").click();
    await r.tid("ar-receipt-confirm").waitFor();
    const msg = await r.text("ar-receipt-confirm-message");
    assert(msg.includes(REK_BCA), `konfirmasi: ${msg}`);
    await klikPotret(r, r.tid("ar-receipt-confirm-confirm"), "konfirmasi-kwitansi");
    await r.tid("ar-receipt-modal").waitFor({ state: "detached", timeout: 20000 });
    rc = mongo(`return db.ar_receipts.find({"allocations.order_id":"${s.sos_id}",status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(rc && Math.abs(Number(rc.amount) - total) < 0.01, `kwitansi DB ${rc && rc.amount}`);
    const sos = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,payment_status:1,status:1})`);
    assert(sos.payment_status === "paid", `status bayar SOS ${sos.payment_status}`);
    return `konfirmasi "${msg}" → ${rc.number} · SOS ${sos.status}/${sos.payment_status}`;
  });

  await r.step(5, "Finance", "Penjualan › Pesanan Sample, cari nomor SOS, pilih barisnya → [[Setujui Pembayaran]]", "Bilah hijau \"KSC/SOS-…: pembayaran disetujui.\"; status Siap ke gudang; \"Pembayaran disetujui <nama Anda>\"", async () => {
    await menu(r, "penjualan", "sample-orders");
    await r.tid("sample-orders-view").waitFor();
    await r.tid("sample-orders-search").fill(sos0.number);
    const row = r.tid(`sample-order-row-${s.sos_id}`);
    await row.waitFor();
    await row.click();
    await r.tid("sample-detail-approve-payment").waitFor();
    await klikPotret(r, r.tid("sample-detail-approve-payment"), "klik-setujui-pembayaran");
    const msg = await tungguTeks(r, "sample-orders-toast", /pembayaran disetujui/);
    await tungguTeks(r, "sample-detail-payment", /Pembayaran disetujui/);
    const sos = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,status:1,sample_payment_status:1,sample_payment_approved_by:1,sample_payment_approved_amount:1})`);
    assert(sos.status === "approved" && sos.sample_payment_status === "approved", `DB ${sos.status}/${sos.sample_payment_status}`);
    await sorot(r.tid("sample-detail-payment"));
    await r.shot("sample-disetujui");
    return `${msg} · DB ${sos.status} oleh ${sos.sample_payment_approved_by} (${rp(sos.sample_payment_approved_amount)})`;
  });

  await r.step(6, "Finance", "Cek buku: jurnal kwitansi sample", "Kas Besar / Bank (D) = Uang Muka Pelanggan (K) = total sample (barang belum dikirim → uang muka, belum pendapatan); persetujuan bayar tidak membuat jurnal", async () => {
    const je = jurnalDari([rc.cash_txn_id, rc.id]).find((j) => (j.lines || []).some((l) => l.account_code === "1-1100"));
    assert(je, "jurnal kwitansi tidak ditemukan");
    const um = je.lines.find((l) => Number(l.credit) > 0);
    assert(/Uang Muka/i.test(um.account_name || ""), `akun kredit ${um.account_code} ${um.account_name}`);
    const txt = cekJurnal(je, [["1-1100", "D", total], [um.account_code, "K", total]]);
    const jeSos = mongo(`return db.journal_entries.countDocuments({source_id:"${s.sos_id}"})`);
    assert(jeSos === 0, `SOS punya ${jeSos} jurnal sebelum dikirim`);
    return `${txt} · jurnal atas SOS: 0`;
  });

  await r.finish();
})();
