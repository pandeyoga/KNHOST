// F11 — Bayar tagihan supplier (Keuangan › Hutang › Tagihan) + baca GR/IR.
// Peserta (akun Finance sendiri) mencari tagihan pemasoknya, memeriksa 3-way match, membayar dari BCA Operasional KSC,
// lalu memastikan status Lunas, jurnal Hutang Usaha (D) / Bank (K) seimbang, dan sisa GR/IR PO-nya nol.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F11_bayar_tagihan.js        (bawaan peserta 04; KN_PESERTA=41 …)
const { Run, assert, rp, num, kartu, peserta, akunPeserta, mongo } = require("./lib");
const { REK_BCA, pilih, setuju, jurnalDari, cekJurnal, tungguTeks, sorot, lepas, klikPotret } = require("./hutang_lib");

(async () => {
  const no = peserta("04");
  const k = kartu(no);
  const tg = k["a_dasar:tagihan_bayar"];
  const r = await new Run("F11", "Bayar tagihan supplier").start();
  if (!tg) { r.note(`Kartu peserta ${no} belum punya a_dasar:tagihan_bayar`); await r.finish(); return; }
  const bill0 = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
  const pemasok = bill0.supplier_name;
  const total = Number(bill0.grand_total);
  const dpp = Number(bill0.net_subtotal || bill0.total_amount);
  r.note(`Peserta ${no} · ${tg.tagihan} · PO ${tg.po} · total ${rp(total)} · status awal ${bill0.status}`);

  await r.step(1, "Finance", "Login dengan akun Finance peserta, buka Keuangan › Hutang", "Tab Tagihan tampil: kartu umur hutang + daftar tagihan PT Sukacita", async () => {
    await r.login(akunPeserta(no));
    await r.tid("finance-desk").waitFor();
    await klikPotret(r, r.tid("nav-accounts-payable"), "menu-hutang");
    await r.tid("vendor-bills-view").waitFor();
    await r.idle(800);
    const judul = await r.text("vendor-bills-title");
    assert(/Tagihan Supplier/.test(judul), `judul "${judul}"`);
    await r.tid("vb-summary-total").waitFor();
    await r.shot("daftar-tagihan");
    return `Total hutang ${await r.text("vb-summary-total")}`;
  });

  await r.step(2, "Finance", `Ketik "Latihan ${no}" di kotak cari`, "Hanya tagihan pemasok peserta yang tampil; tagihan bayar berstatus Terposting dengan Sisa = Total", async () => {
    await r.tid("vb-search").fill(`Latihan ${no}`);
    await r.idle(1200);
    const row = r.tid(`vb-row-${tg.tagihan_id}`);
    await row.waitFor();
    const t = (await row.innerText()).replace(/\s+/g, " ");
    assert(t.includes(tg.tagihan), `baris tanpa nomor ${tg.tagihan}: ${t}`);
    assert(/Terposting/.test(t) && /Cocok/.test(t), `status/pencocokan baris: ${t}`);
    assert(t.includes(rp(total).replace("Rp ", "")), `total ${rp(total)} tidak tampil: ${t}`);
    const rows = await r.page.$$eval('[data-testid^="vb-row-"]', (els) => els.map((e) => e.innerText));
    assert(rows.every((x) => x.includes(`Latihan ${no}`)), "ada baris pemasok lain di hasil cari");
    await sorot(r.tid(`vb-open-${tg.tagihan_id}`));
    await r.shot("cari-pemasok");
    await lepas(r.tid(`vb-open-${tg.tagihan_id}`));
    return `${rows.length} tagihan pemasok Latihan ${no}: ${t.slice(0, 140)}`;
  });

  await r.step(3, "Finance", "Klik [[Detail →]] pada tagihan bayar", "Rincian: Terposting · Match Bersih, \"3-way match bersih: qty & harga sesuai PO/penerimaan\" (Pesan = Terima = Tagih, Harga PO = Harga Bill), Dokumen Terkait: PO & jurnal; di kaki hanya tombol [[Bayar]]", async () => {
    await r.tid(`vb-open-${tg.tagihan_id}`).click();
    await r.tid("vendor-bill-detail-panel").waitFor();
    await r.idle(800);
    assert(/Match Bersih/.test(await r.text("vb-detail-match")), "pil pencocokan bukan Match Bersih");
    assert(/3-way match bersih/.test(await r.text("vb-match-clean")), "teks 3-way match bersih tidak tampil");
    const it = (await r.text("vb-detail-item-0")).replace(/\s+/g, " ");
    assert(/Terposting/.test(await r.text("vb-detail-status")), "status rincian bukan Terposting");
    assert(num(await r.text("vb-fin-outstanding")) === Math.round(total), "Sisa Hutang ≠ total");
    const panel = (await r.tid("vendor-bill-detail-panel").innerText()).replace(/\s+/g, " ");
    assert(panel.includes(tg.po), `PO ${tg.po} tidak disebut di rincian`);
    // Finance (lihat & bayar, K-17) tidak membatalkan tagihan — tombol Batalkan hanya untuk `vendor_bill.update`.
    assert(await r.tid("vb-action-cancel-posted").count() === 0, "Finance melihat tombol Batalkan tagihan");
    await r.tid("vb-action-pay").waitFor();
    await sorot(r.tid("vb-action-pay"));
    await r.shot("rincian-3way");
    await lepas(r.tid("vb-action-pay"));
    return `baris: ${it.slice(0, 160)} · PPN ${await r.text("vb-fin-ppn")}`;
  });

  await r.step(4, "Finance", "Klik [[Bayar]] → pilih *Rekening sumber* BCA Operasional KSC", "Form Bayar pemasok: Sisa hutang = total tagihan, Nominal terisi penuh, Cara bayar Transfer", async () => {
    await r.tid("vb-action-pay").click();
    await r.tid("pay-supplier-modal").waitFor();
    await r.tid("pay-supplier-number").waitFor();
    assert(num(await r.text("pay-supplier-outstanding")) === Math.round(total), "sisa hutang di form ≠ total");
    assert((await r.text("pay-supplier-supplier")) === pemasok, "nama pemasok di form beda");
    await pilih(r, "pay-supplier-account", REK_BCA);
    const amt = await r.tid("pay-supplier-amount").inputValue();
    assert(num(amt) === Math.round(total), `nominal terisi ${amt}`);
    const cara = await r.text("pay-supplier-method");
    await sorot(r.tid("pay-supplier-submit"));
    await r.shot("form-bayar");
    await lepas(r.tid("pay-supplier-submit"));
    return `nominal ${amt} · cara ${cara} · PT ${await r.text("pay-supplier-pt")}`;
  });

  let bill;
  await r.step(5, "Finance", "Klik [[Bayar]] lalu [[Ya, bayar]] pada konfirmasi", "Konfirmasi menyebut nominal, pemasok, rekening & PT; sesudahnya rincian berstatus Lunas, Sisa Hutang Rp 0", async () => {
    await r.tid("pay-supplier-submit").click();
    const msg = await r.text("pay-supplier-confirm-message");
    assert(msg.includes(rp(total).replace(/\s/g, " ")) || num(msg) > 0, `pesan konfirmasi: ${msg}`);
    assert(msg.includes(REK_BCA) && msg.includes(pemasok), `pesan konfirmasi tanpa rekening/pemasok: ${msg}`);
    await sorot(r.tid("pay-supplier-confirm-confirm"));
    await r.shot("konfirmasi-bayar");
    await setuju(r, "pay-supplier-confirm");
    await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
    await tungguTeks(r, "vb-detail-status", /Lunas/);
    assert(num(await r.text("vb-fin-outstanding")) === 0, "Sisa Hutang belum 0");
    await r.tid("vb-payments").waitFor();
    bill = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
    // Sisa dihitung dari grand_total − amount_paid (`vendor_bill_service.bill_financials`); field simpanan `outstanding`
    // tidak diperbarui saat bayar (temuan audit F11 — lihat laporan), jadi tidak dipakai di sini.
    assert(bill.status === "paid" && Number(bill.amount_paid) + 0.01 >= Number(bill.grand_total),
      `DB: status ${bill.status}, dibayar ${bill.amount_paid} dari ${bill.grand_total}`);
    await sorot(r.tid("vb-detail-status"));
    await r.shot("tagihan-lunas");
    await lepas(r.tid("vb-detail-status"));
    return `konfirmasi: "${msg}" · DB ${bill.status} · kas ${(bill.payments || [])[0]?.cash_txn_number || "?"}`;
  });

  await r.step(6, "Finance", "Cek buku: jurnal pembayaran", "Hutang Usaha (D) / Bank BCA Operasional (K) sebesar total tagihan, seimbang", async () => {
    const p = (bill.payments || []).find((x) => !x.voided);
    assert(p && p.cash_txn_id, "pembayaran tanpa kas");
    const je = jurnalDari([p.cash_txn_id, p.payment_intent_id, p.id]).find((j) => (j.lines || []).some((l) => l.account_code === "2-1100"));
    assert(je, "jurnal bayar dengan akun Hutang Usaha 2-1100 tidak ditemukan");
    const bankLine = je.lines.find((l) => Number(l.credit) > 0);
    const txt = cekJurnal(je, [["2-1100", "D", total], [bankLine.account_code, "K", total]]);
    const cash = mongo(`return db.cash_transactions.findOne({id:"${p.cash_txn_id}"},{_id:0,account_id:1,number:1,amount:1,direction:1,type:1})`);
    const bank = mongo(`return db.bank_accounts.findOne({id:"${cash.account_id}"},{_id:0,name:1})`);
    assert(bank && bank.name === REK_BCA, `kas keluar dari ${bank && bank.name}`);
    return `${txt} · kas ${cash.number} dari ${bank.name}`;
  });

  await r.step(7, "Finance", "Tutup rincian, buka tab [[GR/IR (Diterima Belum Ditagih)]], cari nomor PO, centang *Tampilkan yang sudah nol*", "Baris PO: Nilai diterima = Sudah ditagih (DPP), Sisa GR/IR Rp 0", async () => {
    await r.tid("vb-detail-close").click();
    await klikPotret(r, r.tid("hub-tab-gr-ir"), "tab-grir");
    await r.tid("grir-view").waitFor();
    await r.tid("grir-search").locator("input").first().fill(tg.po).catch(async () => r.tid("grir-search").fill(tg.po));
    await r.tid("grir-show-zero").check();
    const po = mongo(`return db.purchase_orders.findOne({po_number:"${tg.po}"},{_id:0,id:1})`);
    const row = r.tid(`grir-row-${po.id}`);
    await row.waitFor({ timeout: 15000 });
    await r.idle(500);
    const t = (await row.innerText()).replace(/\s+/g, " ");
    const bal = num(await r.text(`grir-balance-${po.id}`));
    assert(bal === 0, `sisa GR/IR ${bal}`);
    assert(t.split(rp(dpp).replace("Rp ", "")).length >= 3, `nilai diterima/ditagih ≠ ${rp(dpp)}: ${t}`);
    await sorot(r.tid(`grir-balance-${po.id}`));
    await r.shot("grir-po");
    return t.slice(0, 200);
  });

  await r.finish();
})();
