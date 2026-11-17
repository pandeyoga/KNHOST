// A3 — RETUR PEMBELIAN ke pemasok (Nota Debit) ujung ke ujung (PT Sukacita), lewat LAYAR dengan akun peran.
//
//   PO latihan sudah diterima & ditagih (kartu peserta: "Tagihan kontrabon") → Gudang membuat retur ke supplier per roll →
//   Manajer menyetujui → Nota Debit DN-… terbit (stok keluar, jurnal Hutang D / Persediaan K / PPN Masukan K) →
//   Finance melihat tagihan BELUM berubah → Manajer menyusun kontrabon dua tagihan pemasok dan memotong Nota Debit →
//   verifikasi → Admin menyetujui → Manajer menjadwalkan → Finance membayar NILAI BERSIH → cek buku → Jejak Dokumen.
//
//   KN_PESERTA=41 node docs/pelatihan/2026-11-18_keuangan/uji/e2e/A3_retur_pembelian.js
//   Data: backend/scripts/seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN (a_dasar: tagihan_bayar & tagihan_kontrabon
//   belum dibayar). Tagihan peserta yang dipakai di sini TIDAK boleh dipakai F11/F12 (peserta uji tersendiri, 41–49).
const { Run, assert, kartu, peserta, akunPeserta, mongo, rp, num } = require("../lib");
const { bersihkanHasil } = require("../piutang_lib");
const { REK_BCA } = require("../hutang_lib");
const R = require("./retur_lib");

const KODE = "A3_retur_pembelian";
const KSC_Q = "&entity=ent_ksc";
const LANJUT = process.env.KN_LANJUT === "1";   // hanya untuk menyusun skrip: lanjutkan retur/kontrabon yang sudah ada

(async () => {
  bersihkanHasil(KODE);
  const r = await new Run(KODE, "A3 Retur pembelian: nota debit memotong hutang lewat kontrabon").start();
  const no = peserta("41");
  const k = kartu(no);
  const tgR = k["a_dasar:tagihan_kontrabon"], tgL = k["a_dasar:tagihan_bayar"];
  if (!tgR || !tgL) throw new Error(`Kartu peserta ${no} belum lengkap — jalankan seed_pelatihan_keuangan_kn.py --mulai ${no} --peserta ${no}`);
  const billR0 = mongo(`return db.vendor_bills.findOne({id:"${tgR.tagihan_id}"},{_id:0})`);
  const billL0 = mongo(`return db.vendor_bills.findOne({id:"${tgL.tagihan_id}"},{_id:0})`);
  const po = mongo(`return db.purchase_orders.findOne({po_number:"${tgR.po}",entity_id:"${R.KSC}"},{_id:0})`);
  const pemasok = mongo(`return db.suppliers.findOne({id:"${po.supplier_id}"},{_id:0,id:1,name:1,code:1})`);
  let pret = null, cb = null;
  const segarPret = () => (pret = mongo(`return db.purchase_returns.findOne({id:"${pret.id}"},{_id:0})`));
  const muat = () => {
    pret = mongo(`return db.purchase_returns.find({po_id:"${po.id}",status:{$nin:["rejected","cancelled"]}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${tgR.tagihan_id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
  };
  if (LANJUT) {
    pret = mongo(`return db.purchase_returns.find({po_id:"${po.id}",status:{$nin:["rejected","cancelled"]}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${tgR.tagihan_id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
  }
  const roll = mongo(`return db.inventory_rolls.findOne({po_id:"${po.id}"${LANJUT ? "" : ',status:"available"'}},{_id:0})`);
  assert(roll, `PO ${tgR.po} tidak punya roll tersedia untuk diretur`);
  r.note(`Peserta ${no}: pemasok ${pemasok.name} · PO ${tgR.po} (${rp(po.grand_total)}) roll ${roll.roll_no} ${roll.length_remaining} ${roll.unit || "yard"} · tagihan ${tgR.tagihan} ${rp(billR0.grand_total)} + ${tgL.tagihan} ${rp(billL0.grand_total)}`);

  await R.langkah(r, 1, "Gudang", "Masuk sebagai warehouse@ → menu [[Retur]] → tab [[Retur ke Supplier (Nota Debit)]] → [[Buat Retur]]",
    "Pop-up 'Buat Retur ke Supplier' terbuka (Supplier, PO Referensi, Gudang, baris barang)", async (ulang) => {
      if (ulang) muat();
      if ((LANJUT || ulang) && pret) return `lewati (${pret.number} ${pret.status})`;
      await r.login("warehouse");
      await R.bukaRetur(r, "purchase-returns", "gudang-retur-supplier");
      await r.tid("purchase-returns-view").waitFor();
      await R.klikPotret(r, r.tid("create-return-button"), "gudang-buat-retur");
      await r.tid("purchase-return-form").waitFor();
    });

  await R.langkah(r, 2, "Gudang", `Pilih *Supplier* ${pemasok.name} → *PO Referensi* ${tgR.po} → [[Pilih roll]] → centang roll ${roll.roll_no} → [[Pakai]] → isi *Alasan roll ini* → [[Buat Retur]]`,
    "Pesan hijau 'Retur PRET-… dibuat (menunggu persetujuan)'; baris retur berstatus Menunggu Persetujuan", async (ulang) => {
      if (ulang) muat();
      if ((LANJUT || ulang) && pret) return "lewati";
      if (ulang || !(await r.tid("purchase-return-form").isVisible().catch(() => false))) {
        await r.login("warehouse");
        await R.bukaRetur(r, "purchase-returns");
        await r.tid("create-return-button").click();
        await r.tid("purchase-return-form").waitFor();
      }
      await r.idle(1200);   // daftar pemasok, gudang, produk & PO dimuat dulu
      await R.pilihCari(r, "return-supplier-select", pemasok.name, pemasok.id);
      await R.pilihCari(r, "return-po-select", tgR.po.replace(/^.*\//, ""), po.id);
      await r.idle(500);
      await R.klikPotret(r, r.tid("return-pick-rolls-0"), "gudang-pilih-roll");
      await r.tid("roll-picker-modal").waitFor();
      await r.tid(`roll-pick-${roll.id}`).waitFor({ timeout: 15000 });
      await r.tid(`roll-pick-${roll.id}`).click();
      await R.klikPotret(r, r.tid("roll-picker-confirm"), "gudang-roll-dipilih");
      await r.tid("roll-picker-modal").waitFor({ state: "detached" });
      const alasan = r.tid(`return-item-0-claims-roll-${roll.id}-reason`);
      await alasan.fill("Warna belang di sepanjang roll — tidak sesuai standar");
      await r.tid("return-reason-input").fill(`1 roll cacat warna dari ${tgR.po}`);
      await r.shot("gudang-form-retur", { full: true });
      await R.klikPotret(r, r.tid("submit-return-button"), "gudang-simpan-retur");
      const msg = await R.tungguTeks(r, "pret-notice", /dibuat/);
      pret = mongo(`return db.purchase_returns.find({po_id:"${po.id}",status:{$nin:["rejected","cancelled"]}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(pret && pret.status === "pending_approval", `retur beli: ${pret && pret.status}`);
      await R.sorot(r.tid(`return-row-${pret.id}`));
      await r.shot("gudang-retur-terbit");
      return `${msg} · ${pret.number} ${pret.items[0].quantity} ${pret.items[0].unit} × ${rp(pret.items[0].price)} = DPP ${R.rpBuku(pret.total_amount)} + PPN ${R.rpBuku(pret.ppn_amount)} = ${R.rpBuku(pret.grand_total)}`;
    });

  let je = null;
  await R.langkah(r, 3, "Manajer", "Masuk sebagai manager@ → Retur › Retur ke Supplier → baris retur → [[Setujui]] → [[Setujui retur]]",
    "Pesan 'Retur PRET-… disetujui. Nota debit: DN-…'; status Disetujui", async (ulang) => {
      if (ulang) muat();
      if ((LANJUT || ulang) && pret && pret.status === "approved") return `lewati (${pret.debit_note_number})`;
      await r.login("manager");
      await R.bukaRetur(r, "purchase-returns");
      await r.tid("purchase-returns-view").waitFor();
      await r.tid("pret-search").fill(pret.number);
      await r.idle(800);
      await R.klikPotret(r, r.tid(`return-approve-${pret.id}`), "manajer-setujui-retur");
      await r.tid("confirm-modal").waitFor();
      await R.sorot(r.tid("confirm-modal-confirm"));
      await r.shot("manajer-konfirmasi-setujui");
      await r.tid("confirm-modal-confirm").click();
      const msg = await R.tungguTeks(r, "pret-notice", /Nota debit/);
      segarPret();
      assert(pret.status === "approved" && pret.debit_note_number, `retur ${pret.status} DN ${pret.debit_note_number}`);
      await r.shot("manajer-nota-debit-terbit");
      return msg;
    });

  await R.langkah(r, 4, "Sistem", "Cek buku: Nota Debit, stok, jurnal retur beli",
    "Roll keluar stok (dikembalikan ke supplier); jurnal: 2-1100 Hutang Usaha (D) = DPP + PPN / 1-1300 Persediaan (K) = DPP · PPN Masukan (K) = PPN; PO mencatat nilai retur", async (ulang) => {
      if (ulang) muat();
      const rl = mongo(`return db.inventory_rolls.findOne({id:"${roll.id}"},{_id:0,status:1,length_remaining:1})`);
      assert(rl.status === "returned_supplier" || Number(rl.length_remaining) === 0, `roll ${roll.roll_no} masih ${rl.status}`);
      je = R.jurnalDari([pret.id]).find((j) => j.source_type === "purchase_return");
      assert(je, "jurnal retur beli tidak ada");
      const ppnLine = je.lines.find((l) => Number(l.credit) > 0 && Math.abs(Number(l.credit) - pret.ppn_amount) < 0.01);
      assert(ppnLine, `baris PPN Masukan ${pret.ppn_amount} tidak ada`);
      const t = R.cekJurnal(je, [["2-1100", "D", pret.grand_total], ["1-1300", "K", pret.total_amount], [ppnLine.account_code, "K", pret.ppn_amount]]);
      const po1 = mongo(`return db.purchase_orders.findOne({id:"${po.id}"},{_id:0,returned_amount:1})`);
      assert(Math.abs(Number(po1.returned_amount || 0) - pret.grand_total) < 0.01, `PO returned_amount ${po1.returned_amount}`);
      return `${pret.debit_note_number} ${R.rpBuku(pret.grand_total)} · ${t}`;
    });

  await R.langkah(r, 5, "Finance", `Akun Finance peserta → Keuangan › [[Hutang]] › tab Tagihan → cari ${tgR.tagihan}`,
    `Tagihan ${tgR.tagihan} MASIH ${rp(billR0.grand_total)} belum dibayar — Nota Debit belum memotong tagihan sampai dipakai di kontrabon/pembayaran`, async (ulang) => {
      if (ulang) muat();
      await r.login(akunPeserta(no));
      await R.menu(r, "keuangan", "accounts-payable");
      await r.tid("vendor-bills-view").waitFor();
      await r.idle(800);
      const rek = (await r.tid("vb-ap-reconciliation").count()) ? (await r.text("vb-ap-reconciliation")) : "(kartu pencocokan hutang tidak tampil)";
      await r.tid("vb-search").fill(tgR.tagihan);
      await r.idle(900);
      const row = r.tid(`vb-row-${tgR.tagihan_id}`);
      await row.waitFor({ timeout: 15000 });
      const t = (await row.innerText()).replace(/\s+/g, " ");
      const b = mongo(`return db.vendor_bills.findOne({id:"${tgR.tagihan_id}"},{_id:0,status:1,amount_paid:1,grand_total:1})`);
      assert(Number(b.amount_paid || 0) < 0.01, `tagihan sudah terbayar ${b.amount_paid}`);
      await R.sorot(row);
      if (await r.tid("vb-ap-reconciliation").count()) await R.sorot(r.tid("vb-ap-reconciliation"));
      await r.shot("finance-tagihan-belum-terpotong");
      return `baris: ${t} · pencocokan hutang: ${rek}`;
    });

  // ── Kontrabon (pola F12): dua tagihan pemasok − nota debit ─────────────────────────────────────────────────────────
  const bukaCb = async () => {
    await r.go("contra-bons", KSC_Q);
    await r.tid("contra-bons-view").waitFor();
    await r.tid("cb-filter-q").fill(cb.number);
    const row = r.tid(`cb-row-${cb.id}`);
    await row.waitFor({ timeout: 15000 });
    await row.click();
    await r.tid("cb-detail-panel").waitFor();
    await r.idle(500);
  };
  const totalTagihan = R.r2(Number(billR0.grand_total) + Number(billL0.grand_total));

  await R.langkah(r, 6, "Manajer", `manager@ → Keuangan › Hutang › [[Kontrabon]] › [[Kontrabon baru]] → *Supplier* ${pemasok.name} → [[Lanjut]] → centang ${tgL.tagihan} & ${tgR.tagihan} → [[Lanjut]] → centang *Ajukan langsung* → [[Terbitkan kontrabon]]`,
    `Kontrabon KSC/CB-… terbit berisi 2 faktur (Σ ${rp(totalTagihan)}), status Diajukan`, async (ulang) => {
      if (ulang) muat();
      assert(pret && pret.debit_note_number, "Nota Debit belum terbit — kontrabon tidak dibuat (langkah 2–3 gagal)");
      if ((LANJUT || ulang) && cb) { await r.login("manager"); await bukaCb(); return `lewati (${cb.number} ${cb.status})`; }
      await r.login("manager");
      await r.go("contra-bons", KSC_Q);
      await r.tid("contra-bons-view").waitFor();
      await r.idle(500);
      await R.klikPotret(r, r.tid("cb-new"), "manajer-kontrabon-baru");
      await r.tid("cb-create-wizard").waitFor();
      await R.pilih(r, "cb-create-supplier", pemasok.name);
      await r.tid("cb-create-prep-summary").waitFor();
      await r.idle(400);
      await r.tid("cb-create-next").click();
      for (const id of [tgL.tagihan_id, tgR.tagihan_id]) {
        const box = r.tid(`cb-create-pick-${id}`);
        await box.waitFor();
        if (!(await box.isChecked())) await box.click();
      }
      const semua = await r.page.$$eval('[data-testid^="cb-create-pick-"]', (els) => els.map((e) => e.getAttribute("data-testid")));
      for (const t of semua) {
        if (![`cb-create-pick-${tgL.tagihan_id}`, `cb-create-pick-${tgR.tagihan_id}`].includes(t) && (await r.tid(t).isChecked())) await r.tid(t).click();
      }
      await R.sorot(r.tid("cb-create-selected-summary"));
      await r.shot("manajer-wizard-faktur");
      await r.tid("cb-create-next").click();
      await r.tid("cb-create-review").waitFor();
      await r.tid("cb-create-submit-now").check();
      await R.klikPotret(r, r.tid("cb-create-submit"), "manajer-terbitkan-kontrabon");
      await r.tid("cb-create-wizard").waitFor({ state: "detached", timeout: 20000 });
      const msg = await R.tungguTeks(r, "cb-notice", /terbit/);
      cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${tgR.tagihan_id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(cb && cb.bills.length === 2, `kontrabon ${cb && cb.bills.length} faktur`);
      assert(Math.abs(Number(cb.totals.bills_total) - totalTagihan) < 0.01, `total faktur ${cb.totals.bills_total} ≠ ${totalTagihan}`);
      return msg;
    });

  let ded = null;
  await R.langkah(r, 7, "Manajer", `Di rincian kontrabon klik [[+ Tambah potongan]] → *Jenis* Retur beli (nota debit) → *Dokumen* Nota debit ${pret.debit_note_number || "DN-…"} → biarkan nominal (= sisa nota) → [[Simpan potongan]]`,
    "Potongan tercatat; nilai bersih kontrabon = Σ faktur − Nota Debit (DPP + PPN)", async (ulang) => {
      if (ulang) muat();
      ded = ((cb && cb.deductions) || []).find((d) => d.ref_id === pret.id);
      if (!((LANJUT || ulang) && ded)) {
      if (ulang) { await r.login("manager"); await bukaCb(); }
      await r.idle(600);
      await R.klikPotret(r, r.tid("cb-add-deduction"), "manajer-tambah-potongan");
      await r.tid("cb-deduction-modal").waitFor();
      await R.pilihRe(r, "cb-deduction-kind", /Retur beli/);
      await r.idle(600);
      await R.pilihRe(r, "cb-deduction-ref", new RegExp(pret.debit_note_number));
      await r.idle(400);
      await r.shot("manajer-form-potongan");
      await R.klikPotret(r, r.tid("cb-deduction-save"), "manajer-simpan-potongan");
      await r.tid("cb-deduction-modal").waitFor({ state: "detached", timeout: 15000 });
      await r.idle(800);
      }
      cb = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0})`);
      ded = (cb.deductions || []).find((d) => d.ref_id === pret.id);
      assert(ded, "potongan nota debit tidak tersimpan");
      await R.sorot(r.tid("cb-detail-panel"));
      await r.shot("manajer-kontrabon-dengan-potongan");
      const netHarus = R.r2(totalTagihan - pret.grand_total);
      assert(Math.abs(Number(ded.amount) - pret.grand_total) < 0.01,
        `potongan nota debit ${R.rpBuku(ded.amount)} ≠ nilai Nota Debit (DPP + PPN) ${R.rpBuku(pret.grand_total)} — PPN atas barang retur ikut dibayar ke pemasok`);
      assert(Math.abs(Number(cb.totals.net_payable) - netHarus) < 0.01, `nilai bersih ${cb.totals.net_payable} ≠ ${netHarus}`);
      return `potongan ${R.rpBuku(ded.amount)} · nilai bersih ${R.rpBuku(cb.totals.net_payable)}`;
    });

  const st = () => (mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0,status:1})`) || {}).status;
  const sesudah = (x, u) => (LANJUT || u) && ["verified", "approved", "scheduled_payment", "paid"].indexOf(st()) >= ["verified", "approved", "scheduled_payment", "paid"].indexOf(x);
  await R.langkah(r, 8, "Manajer", "Klik [[Verifikasi 3-way match]]", "Status Terverifikasi", async (ulang) => {
      if (ulang) muat();
      if (sesudah("verified", ulang)) return `lewati (${st()})`;
    assert(((mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0,deductions:1})`) || {}).deductions || []).some((d) => d.ref_id === pret.id),
      "potongan Nota Debit belum ada — kontrabon tidak diverifikasi (potongan hanya bisa ditambah sebelum verifikasi)");
    if (ulang) { await r.login("manager"); await bukaCb(); }
    await R.tungguTeks(r, "cb-action-primary", /Verifikasi/);
    await R.klikPotret(r, r.tid("cb-action-primary"), "manajer-verifikasi");
    await R.tungguTeks(r, "cb-detail-status", /Terverifikasi/);
    await r.shot("kontrabon-terverifikasi");
  });

  await R.langkah(r, 9, "Admin", "admin@ (penyetuju kedua) buka kontrabon → [[Setujui kontrabon]]", "Status Disetujui", async (ulang) => {
    if (ulang) muat();
    if (sesudah("approved", ulang)) return `lewati (${st()})`;
    await r.login("admin");
    await bukaCb();
    await R.tungguTeks(r, "cb-action-primary", /Setujui/);
    await R.klikPotret(r, r.tid("cb-action-primary"), "admin-setujui");
    await R.tungguTeks(r, "cb-detail-status", /Disetujui/);
  });

  await R.langkah(r, 10, "Manajer", `manager@ buka kontrabon → [[Jadwalkan pembayaran]] → *Rekening rencana* ${REK_BCA} → [[Simpan jadwal bayar]]`, "Status Dijadwalkan bayar", async (ulang) => {
    if (ulang) muat();
    if (sesudah("scheduled_payment", ulang)) return `lewati (${st()})`;
    await r.login("manager");
    await bukaCb();
    await R.tungguTeks(r, "cb-action-primary", /Jadwalkan/);   // jangan sampai menekan tombol tahap lain
    await R.klikPotret(r, r.tid("cb-action-primary"), "manajer-jadwalkan");
    await r.tid("cb-schedule-modal").waitFor();
    await R.pilih(r, "cb-schedule-account", REK_BCA);
    await r.tid("cb-schedule-save").click();
    await r.tid("cb-schedule-modal").waitFor({ state: "detached", timeout: 15000 });
    await R.tungguTeks(r, "cb-detail-status", /Dijadwalkan/);
  });

  let paid = null;
  await R.langkah(r, 11, "Finance", "Akun Finance peserta → Keuangan › Hutang › Kontrabon → buka kontrabon → [[Catat pembayaran]] → periksa *Sisa* = nilai bersih → [[Bayar]] → [[Ya, bayar]]",
    "Status Sudah dibayar; kas keluar = nilai bersih (bukan Σ faktur)", async (ulang) => {
      if (ulang) muat();
      if (sesudah("paid", ulang)) { paid = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0})`); return "lewati (sudah dibayar)"; }
      await r.login(akunPeserta(no));
      await bukaCb();
      await R.tungguTeks(r, "cb-action-primary", /Catat pembayaran/);
      await R.klikPotret(r, r.tid("cb-action-primary"), "finance-catat-pembayaran");
      await r.tid("pay-supplier-modal").waitFor();
      await r.tid("pay-supplier-number").waitFor();
      const sisa = num(await r.text("pay-supplier-outstanding"));
      assert(Math.abs(sisa - Math.round(Number(cb.totals.net_payable))) <= 1, `sisa di form ${sisa} ≠ nilai bersih ${cb.totals.net_payable}`);
      const rek = await r.text("pay-supplier-account");
      if (!rek.includes(REK_BCA)) await R.pilih(r, "pay-supplier-account", REK_BCA);
      await R.sorot(r.tid("pay-supplier-outstanding"));
      await r.shot("finance-form-bayar");
      await r.tid("pay-supplier-submit").click();
      await R.setuju(r, "pay-supplier-confirm");
      await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
      await R.tungguTeks(r, "cb-detail-status", /Sudah dibayar/);
      await r.shot("finance-kontrabon-dibayar");
      paid = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0})`);
      assert(paid.status === "paid", `status ${paid.status}`);
      return `bayar ${rp(sisa)}`;
    });

  await R.langkah(r, 12, "Sistem", "Cek buku: kedua tagihan lunas; jurnal bayar = nilai bersih; akun Hutang pemasok kembali nol",
    "Tagihan retur lunas lewat potongan non-kas, tagihan lain lunas lewat kas; Hutang Usaha (D) / Kas Besar / Bank (K) = nilai bersih; Σ debit Hutang (nota debit + bayar) = Σ tagihan", async (ulang) => {
      if (ulang) muat();
      const bills = [tgR.tagihan_id, tgL.tagihan_id].map((id) => mongo(`return db.vendor_bills.findOne({id:"${id}"},{_id:0,number:1,bill_number:1,status:1,amount_paid:1,grand_total:1})`));
      for (const b of bills) assert(b.status === "paid", `tagihan ${b.bill_number} ${b.status} (${b.amount_paid}/${b.grand_total})`);
      const p = (paid.payments || [])[0] || {};
      const ids = [p.cash_txn_id, p.payment_intent_id, p.id, cb.id].filter(Boolean);
      const jb = R.jurnalDari(ids).find((j) => (j.lines || []).some((l) => l.account_code === "2-1100"));
      assert(jb, "jurnal bayar kontrabon tidak ada");
      const net = Number(paid.totals.net_payable);
      const bank = jb.lines.find((l) => Number(l.credit) > 0);
      const t = R.cekJurnal(jb, [["2-1100", "D", net], [bank.account_code, "K", net]]);
      // Hutang pemasok: kredit tagihan (Σ) vs debit nota debit + bayar → selisih harus 0.
      const sup = pemasok.id;
      const jes = mongo(`return db.journal_entries.find({status:{$ne:"void"},"lines.account_code":"2-1100",
        $or:[{source_id:{$in:${JSON.stringify([tgR.tagihan_id, tgL.tagihan_id, pret.id, ...ids])}}}]},{_id:0,number:1,lines:1}).toArray()`) || [];
      let d = 0, kr = 0;
      for (const j of jes) for (const l of j.lines) if (l.account_code === "2-1100") { d += Number(l.debit || 0); kr += Number(l.credit || 0); }
      return `${t} · Hutang 2-1100 dari ${jes.length} jurnal: D ${R.rpBuku(d)} / K ${R.rpBuku(kr)} → sisa ${R.rpBuku(kr - d)} (pemasok ${sup})`;
    });

  await R.langkah(r, 13, "Finance", `Menu [[Pusat Dokumen]] › tab [[Jejak Dokumen]] → ketik ${tgR.po} → klik hasilnya`,
    `Rantai: ${tgR.po} → penerimaan → tagihan ${tgR.tagihan}; retur PRET-… (Nota Debit) → kontrabon KSC/CB-…`, async (ulang) => {
      if (ulang) muat();
      await R.menu(r, "alat", "document-center");
      await R.klikPotret(r, r.tid("hub-tab-doc-trace"), "finance-tab-jejak");
      await r.tid("doc-trace-view").waitFor();
      await r.tid("trace-search-input").fill(tgR.po);
      await r.tid(`trace-result-${po.id}`).click();
      await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
      await r.tid("trace-graph").waitFor();
      await r.idle(1200);
      const g = await r.text("trace-graph");
      await r.shot("jejak-po", { full: true });
      const hilang = [tgR.po, pret.number, cb.number].filter((x) => !g.includes(x));
      assert(!hilang.length, `jejak ${tgR.po} tidak memuat: ${hilang.join(", ")}`);
      return `${await r.text("trace-kpis")} · ${g.slice(0, 300)}`;
    });

  await r.finish();
})().catch((e) => { console.error(e); process.exit(1); });
