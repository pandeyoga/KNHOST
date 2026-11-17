// F12 — Kontrabon (tukar faktur): siapa mengerjakan apa.
// Finance hanya MELIHAT & MEMBAYAR kontrabon (K-17: izin contra_bon view + pay). Kontrabon dibuat, diajukan, diverifikasi
// dan dijadwalkan oleh Manajer (izin contra_bon create/update/verify); disetujui orang KEDUA (kontrol dua orang
// "Kontrabon" bawaan = 2 orang → di data demo: Admin). Sesudah dijadwalkan, Finance mencatat pembayarannya.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F12_kontrabon.js        (bawaan peserta 04; KN_PESERTA=42 …)
const { Run, assert, rp, num, kartu, peserta, akunPeserta, mongo } = require("./lib");
const { REK_BCA, pilih, setuju, jurnalDari, cekJurnal, tungguTeks, sorot, lepas, klikPotret } = require("./hutang_lib");

const KSC = "&entity=ent_ksc";

(async () => {
  const no = peserta("04");
  const k = kartu(no);
  const tg = k["a_dasar:tagihan_kontrabon"];
  const r = await new Run("F12", "Kontrabon (tukar faktur) sampai dibayar").start();
  if (!tg) { r.note(`Kartu peserta ${no} belum punya a_dasar:tagihan_kontrabon`); await r.finish(); return; }
  const bill0 = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
  const pemasok = bill0.supplier_name;
  const total = Number(bill0.grand_total);
  r.note(`Peserta ${no} · ${tg.tagihan} (${tg.faktur_supplier}) · ${pemasok} · ${rp(total)} · status awal ${bill0.status}`);
  let cb = null;   // kontrabon yang terbit di uji ini
  const bukaCb = async () => {
    await r.go("contra-bons", KSC);
    await r.tid("contra-bons-view").waitFor();
    await r.tid("cb-filter-q").fill(cb.number);
    const row = r.tid(`cb-row-${cb.id}`);
    await row.waitFor({ timeout: 15000 });
    await row.click();
    await r.tid("cb-detail-panel").waitFor();
    await r.idle(500);
  };

  await r.step(1, "Finance", "Login akun Finance peserta, buka Keuangan › Hutang › tab [[Kontrabon]]", "Daftar kontrabon tampil; Finance juga melihat tombol [[Kontrabon baru]] (K-FIN-01) — di latihan ini kontrabon dibuat Manajer", async () => {
    await r.login(akunPeserta(no));
    await r.tid("nav-accounts-payable").click();
    await r.tid("vendor-bills-view").waitFor();
    await klikPotret(r, r.tid("hub-tab-contra-bons"), "tab-kontrabon");
    await r.tid("contra-bons-view").waitFor();
    await r.idle(800);
    await r.kfin(r.tid("cb-new"), "tombol Kontrabon baru");
    await r.shot("finance-kontrabon");
    return `kpi menunggu ${await r.text("cb-kpi-waiting")} · dijadwalkan ${await r.text("cb-kpi-scheduled")}`;
  });

  await r.step(2, "Manajer", "Login manager@, Keuangan › Hutang › Kontrabon › [[Kontrabon baru]], pilih *Supplier* pemasok peserta → [[Lanjut]]", "Ringkasan supplier: Tagihan siap ≥ 1, termin NET30, jatuh tempo diusulkan +30 hari", async () => {
    await r.login("manager");
    await r.go("contra-bons", KSC);
    await r.tid("contra-bons-view").waitFor();
    await r.idle(500);
    await klikPotret(r, r.tid("cb-new"), "manajer-kontrabon-baru");
    await r.tid("cb-create-wizard").waitFor();
    await pilih(r, "cb-create-supplier", pemasok);
    await r.tid("cb-create-prep-summary").waitFor();
    await r.idle(400);
    const ring = (await r.text("cb-create-prep-summary"));
    assert(/NET30/.test(ring), `ringkasan tanpa termin NET30: ${ring}`);
    await sorot(r.tid("cb-create-next"));
    await r.shot("wizard-supplier");
    await r.tid("cb-create-next").click();
    return ring.slice(0, 200);
  });

  await r.step(3, "Manajer", `Langkah 2: centang hanya faktur ${tg.tagihan} (${tg.faktur_supplier}) → [[Lanjut]]`, "Faktur peserta tercentang, nilai = total tagihan", async () => {
    const cek = r.tid(`cb-create-pick-${tg.tagihan_id}`);
    await cek.waitFor();
    const semua = await r.page.$$eval('[data-testid^="cb-create-pick-"]', (els) => els.map((e) => e.getAttribute("data-testid")));
    for (const t of semua) {
      const box = r.tid(t);
      const mau = t === `cb-create-pick-${tg.tagihan_id}`;
      if ((await box.isChecked()) !== mau) await box.click();
    }
    const ring = await r.text("cb-create-selected-summary");
    assert(ring.includes(rp(total).replace("Rp ", "")) || num(ring) > 0, `ringkasan pilihan: ${ring}`);
    await sorot(r.tid(`cb-create-bill-${tg.tagihan_id}`));
    await sorot(r.tid("cb-create-next"));
    await r.shot("wizard-faktur");
    await r.tid("cb-create-next").click();
    return `${semua.length} faktur ditawarkan · ${ring}`;
  });

  await r.step(4, "Manajer", "Langkah 3: periksa tanggal tukar faktur & jatuh tempo, centang *Ajukan langsung* → [[Terbitkan kontrabon]]", "Bilah hijau \"Kontrabon KSC/CB-… terbit — 1 faktur digabung, nilai bersih Rp …\"; status Diajukan", async () => {
    await r.tid("cb-create-review").waitFor();
    await r.tid("cb-create-submit-now").check();
    await sorot(r.tid("cb-create-submit-now"));
    await sorot(r.tid("cb-create-submit"));
    await r.shot("wizard-periksa");
    await r.tid("cb-create-submit").click();
    await r.tid("cb-create-wizard").waitFor({ state: "detached", timeout: 20000 });
    const msg = await tungguTeks(r, "cb-notice", /terbit/);
    cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${tg.tagihan_id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(cb, "kontrabon tidak tersimpan");
    assert(msg.includes(cb.number), `notice tanpa nomor ${cb.number}: ${msg}`);
    await tungguTeks(r, "cb-detail-status", /Diajukan/);
    assert(Math.abs(Number(cb.totals.net_payable) - total) < 0.01, `nilai bersih ${cb.totals.net_payable}`);
    await sorot(r.tid("cb-action-primary"));
    await r.shot("kontrabon-terbit");
    await lepas(r.tid("cb-action-primary"));
    return msg;
  });

  await r.step(5, "Manajer", "Di rincian kontrabon klik [[Verifikasi 3-way match]]", "Status Terverifikasi; 3-way match dijalankan ulang tanpa selisih", async () => {
    await r.idle(800);
    const b = r.tid("cb-action-primary");
    await tungguTeks(r, "cb-action-primary", /Verifikasi/);
    await b.click();
    await tungguTeks(r, "cb-detail-status", /Terverifikasi/);
    await sorot(r.tid("cb-detail-status"));
    await r.shot("kontrabon-verifikasi");
    await lepas(r.tid("cb-detail-status"));
    return await r.text("cb-notice");
  });

  await r.step(6, "Manajer", "(Coba) klik [[Setujui kontrabon]] dengan akun yang sama", "Ditolak: \"Kontrabon harus diputuskan orang lain: Anda yang mengajukannya…\" (kontrol dua orang)", async () => {
    await r.idle(800);   // daftar kontrabon dimuat ulang sesudah verifikasi — tunggu tombol utama berganti
    await tungguTeks(r, "cb-action-primary", /Setujui/);
    await r.tid("cb-action-primary").click();
    const err = await tungguTeks(r, "cb-detail-error", /orang lain/);
    await sorot(r.tid("cb-detail-error"));
    await r.shot("tolak-setuju-sendiri");
    return err;
  });

  await r.step(7, "Admin", "Login admin@ (penyetuju kedua), buka kontrabon itu → [[Setujui kontrabon]]", "Status Disetujui", async () => {
    await r.login("admin");
    await bukaCb();
    await klikPotret(r, r.tid("cb-action-primary"), "admin-setujui");
    await tungguTeks(r, "cb-detail-status", /Disetujui/);
    await sorot(r.tid("cb-detail-status"));
    await r.shot("kontrabon-disetujui");
    return await r.text("cb-notice");
  });

  await r.step(8, "Manajer", "Login manager@, buka kontrabon → [[Jadwalkan pembayaran]]: *Tanggal rencana* biarkan (= jatuh tempo), *Cara bayar* Transfer bank, *Rekening rencana* BCA Operasional KSC → [[Simpan jadwal bayar]]", "Status Dijadwalkan bayar; rincian menampilkan jadwal bayar & rekening", async () => {
    await r.login("manager");
    await bukaCb();
    await klikPotret(r, r.tid("cb-action-primary"), "manajer-jadwalkan");
    await r.tid("cb-schedule-modal").waitFor();
    await pilih(r, "cb-schedule-account", REK_BCA);
    await sorot(r.tid("cb-schedule-save"));
    await r.shot("jadwal-bayar");
    await r.tid("cb-schedule-save").click();
    await r.tid("cb-schedule-modal").waitFor({ state: "detached", timeout: 15000 });
    await tungguTeks(r, "cb-detail-status", /Dijadwalkan/);
    const doc = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0,schedule:1,status:1,due_date:1})`);
    assert(doc.status === "scheduled_payment", `status DB ${doc.status}`);
    const rek = mongo(`return db.bank_accounts.findOne({id:"${doc.schedule.bank_account_id}"},{_id:0,name:1})`);
    assert(rek && rek.name === REK_BCA, `rekening rencana ${rek && rek.name}`);
    return `jadwal ${doc.schedule.planned_payment_date} (jatuh tempo ${doc.due_date}) · ${doc.schedule.method} · ${rek.name}`;
  });

  let paid;
  await r.step(9, "Finance", "Login akun Finance peserta, Keuangan › Hutang › Kontrabon, cari nomor kontrabon, buka → [[Catat pembayaran]] → [[Bayar]] → [[Ya, bayar]]", "Form Bayar pemasok: Kontrabon KSC/CB-…, sisa = nilai bersih, rekening BCA terisi dari jadwal; sesudahnya status Sudah dibayar", async () => {
    await r.login(akunPeserta(no));
    await bukaCb();
    const b = r.tid("cb-action-primary");
    assert(/Catat pembayaran/.test(await b.innerText()), `tombol utama Finance: ${await b.innerText()}`);
    await klikPotret(r, b, "finance-catat-pembayaran");
    await r.tid("pay-supplier-modal").waitFor();
    await r.tid("pay-supplier-number").waitFor();
    assert(num(await r.text("pay-supplier-outstanding")) === Math.round(total), "sisa di form ≠ nilai bersih");
    const rek = await r.text("pay-supplier-account");
    if (!rek.includes(REK_BCA)) await pilih(r, "pay-supplier-account", REK_BCA);
    await sorot(r.tid("pay-supplier-submit"));
    await r.shot("form-bayar-kontrabon");
    await lepas(r.tid("pay-supplier-submit"));
    await r.tid("pay-supplier-submit").click();
    const msg = await r.text("pay-supplier-confirm-message");
    assert(msg.includes(REK_BCA), `konfirmasi: ${msg}`);
    await setuju(r, "pay-supplier-confirm");
    await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
    await tungguTeks(r, "cb-detail-status", /Sudah dibayar/);
    await sorot(r.tid("cb-detail-status"));
    await r.shot("kontrabon-dibayar");
    paid = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0})`);
    assert(paid.status === "paid", `status DB ${paid.status}`);
    return `konfirmasi "${msg}" · ${await r.text("cb-notice").catch(() => "")}`;
  });

  await r.step(10, "Finance", "Cek buku: tagihan & jurnal", `Tagihan ${tg.tagihan} Lunas (lewat kontrabon); jurnal Hutang Usaha (D) / Kas Besar / Bank (K) = nilai bersih, seimbang`, async () => {
    const bill = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0,status:1,amount_paid:1,grand_total:1,payments:1})`);
    assert(bill.status === "paid" && Number(bill.amount_paid) + 0.01 >= Number(bill.grand_total), `tagihan ${bill.status} ${bill.amount_paid}`);
    const p = (paid.payments || [])[0] || {};
    const ids = [p.cash_txn_id, p.payment_intent_id, p.id, cb.id].filter(Boolean);
    const je = jurnalDari(ids).find((j) => (j.lines || []).some((l) => l.account_code === "2-1100"));
    assert(je, `jurnal bayar kontrabon tidak ditemukan (${ids.join(",")})`);
    const bank = je.lines.find((l) => Number(l.credit) > 0);
    const net = Number(paid.totals.net_payable);
    return `${cekJurnal(je, [["2-1100", "D", net], [bank.account_code, "K", net]])} · tagihan ${bill.status}`;
  });

  await r.finish();
})();
