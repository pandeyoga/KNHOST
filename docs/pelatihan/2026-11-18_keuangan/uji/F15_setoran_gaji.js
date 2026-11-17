// F15 — Setoran gaji & pajak: SDM › Penggajian › Setoran & Pajak (izin payroll.pay).
// Data awal `d_hutang:gaji_susulan`: proses gaji SUSULAN milik peserta (insentif tertinggal satu karyawan, Oktober 2026)
// sudah disahkan & diposting Manajer → peserta MEMBAYAR gaji bersihnya dari rekening gaji, lalu MENYETOR PPh 21 yang
// ditambahkan proses itu (masa Oktober 2026). Proses reguler PT (KSC/PAY-00001, 6 karyawan) ikut tampil di antrean — dibayar
// pelatih sebagai peragaan (lihat catatan pelatih); setoran BPJS reguler juga peragaan pelatih.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F15_setoran_gaji.js        (bawaan peserta 04; KN_PESERTA=45 …)
const { Run, assert, rp, num, kartu, peserta, akunPeserta, mongo } = require("./lib");
const { REK_BCA, pilih, jurnalDari, cekJurnal, tungguTeks, menu, sorot, lepas, klikPotret } = require("./hutang_lib");

(async () => {
  const no = peserta("04");
  const k = kartu(no);
  const g = k["d_hutang:gaji_susulan"];
  const r = await new Run("F15", "Bayar gaji & setor PPh 21").start();
  if (!g) { r.note(`Kartu peserta ${no} belum punya d_hutang:gaji_susulan`); await r.finish(); return; }
  const run0 = mongo(`return db.hr_payroll_runs.findOne({id:"${g.proses_gaji_id}"},{_id:0,number:1,status:1,totals:1,period:1,run_type:1})`);
  const net = Number(run0.totals.net);
  const pph = Number(run0.totals.pph21);
  const ntpn = `NTPN-LATIH-${no}`;
  r.note(`Peserta ${no} · ${run0.number} (${run0.run_type} ${run0.period}) · ${g.karyawan} · bersih ${rp(net)} · PPh 21 ${rp(pph)} · status ${run0.status}`);
  let runPaid = null;
  let setor = null;

  await r.step(1, "Finance", "Login akun Finance peserta → SDM › Penggajian → tab [[Setoran & Pajak]]", `"Gaji siap dibayar" memuat proses ${run0.number} (Susulan · Oktober 2026 · 1 karyawan · ${rp(net)})`, async () => {
    await r.login(akunPeserta(no));
    await menu(r, "hrd", "hr-payroll-hub");
    // K-SDM-01 (17 Nov) — Finance kini juga memegang SDM: hub Penggajian dibuka di tab Proses Gaji → pilih tab Setoran & Pajak.
    if (await r.tid("hub-tab-hr-payroll-remittances").count()) await r.tid("hub-tab-hr-payroll-remittances").click();
    await r.tid("pay-queue").waitFor();
    const row = r.tid(`pay-queue-row-${g.proses_gaji_id}`);
    await row.waitFor({ timeout: 15000 });
    const t = (await row.innerText()).replace(/\s+/g, " ");
    assert(t.includes(run0.number) && /Susulan/i.test(t), `baris: ${t}`);
    assert(t.includes(rp(net).replace("Rp ", "")), `total bersih ${rp(net)} tidak tampil: ${t}`);
    await sorot(r.tid(`pay-queue-transfer-${g.proses_gaji_id}`));
    await r.shot("gaji-siap-dibayar", { locator: r.tid("pay-queue") });
    await lepas(r.tid(`pay-queue-transfer-${g.proses_gaji_id}`));
    return `${t} · ${await r.text("pay-queue-count")}`;
  });

  await r.step(2, "Finance", "Klik [[Daftar transfer]] pada proses Anda, lalu tutup (×)", "Daftar transfer: penerima, bank & nomor rekening, nominal = total bersih; tombol [[Unduh Excel]] untuk berkas bank", async () => {
    await r.tid(`pay-queue-transfer-${g.proses_gaji_id}`).click();
    await r.tid("transfer-panel").waitFor();
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="transfer-loading"]'), null, { timeout: 15000 });
    const t = (await r.tid("transfer-panel").innerText()).replace(/\s+/g, " ");
    assert(t.includes(g.karyawan), `nama karyawan ${g.karyawan} tidak tampil: ${t}`);
    assert(t.includes(rp(net).replace("Rp ", "")), `nominal ${rp(net)} tidak tampil: ${t}`);
    await sorot(r.tid("transfer-download"));
    await r.shot("daftar-transfer");
    await r.tid("transfer-modal-close-x").click();
    await r.tid("transfer-panel").waitFor({ state: "detached" });
    return t.slice(0, 220);
  });

  await r.step(3, "Finance", "Klik [[Bayar]] → *Rekening pembayaran* BCA Operasional KSC, *Tanggal bayar* hari ini → [[Bayar gaji]] → konfirmasi [[Bayar gaji]]", "Proses hilang dari \"Gaji siap dibayar\"; pesan sukses; status proses Dibayar", async () => {
    await klikPotret(r, r.tid(`pay-queue-pay-${g.proses_gaji_id}`), "klik-bayar-gaji", { locator: r.tid("pay-queue") });
    await r.tid("pay-form").waitFor();
    await r.tid("pay-form-summary").waitFor({ timeout: 15000 });
    const acc = await r.text("pay-form-account");
    if (!acc.includes(REK_BCA)) await pilih(r, "pay-form-account", REK_BCA);
    const ring = await r.text("pay-form-summary");
    await sorot(r.tid("pay-form-submit"));
    await r.shot("form-bayar-gaji");
    await lepas(r.tid("pay-form-submit"));
    await r.tid("pay-form-submit").click();
    const msg = await r.text("confirm-modal-message");
    assert(msg.includes(REK_BCA) && msg.includes(rp(net).replace("Rp ", "")), `konfirmasi: ${msg}`);
    await klikPotret(r, r.tid("confirm-modal-confirm"), "konfirmasi-bayar-gaji");
    await r.tid("pay-form").waitFor({ state: "detached", timeout: 20000 });
    await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="pay-queue-row-${id}"]`), g.proses_gaji_id, { timeout: 15000 });
    runPaid = mongo(`return db.hr_payroll_runs.findOne({id:"${g.proses_gaji_id}"},{_id:0})`);
    assert(runPaid.status === "paid", `status DB ${runPaid.status}`);
    const done = await r.text("pay-queue-msg").catch(() => "");
    // Sesudah bayar, layar langsung membuka Daftar transfer (sumber: rekening & tanggal bayar) → potret lalu tutup.
    await r.tid("transfer-panel").waitFor({ timeout: 10000 });
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="transfer-loading"]'), null, { timeout: 15000 });
    await r.shot("gaji-dibayar");
    const src = await r.text("transfer-source");
    assert(src.includes(REK_BCA), `sumber transfer: ${src}`);
    await r.tid("transfer-modal-close-x").click();
    await r.tid("transfer-panel").waitFor({ state: "detached" });
    return `${ring} · konfirmasi "${msg}" · ${done} · ${src} · jurnal ${runPaid.paid_journal_number} · kas ${runPaid.cash_txn_number || ""}`;
  });

  await r.step(4, "Finance", "Cek buku: jurnal bayar gaji", "Hutang Gaji (D) = Kas Besar / Bank (K) = total bersih, seimbang", async () => {
    const je = mongo(`return db.journal_entries.findOne({id:"${runPaid.paid_journal_id}"},{_id:0})`)
      || jurnalDari([runPaid.cash_txn_id, runPaid.id]).find((j) => (j.lines || []).some((l) => Number(l.credit) > 0));
    assert(je, "jurnal bayar gaji tidak ditemukan");
    const deb = je.lines.find((l) => Number(l.debit) > 0);
    const kre = je.lines.find((l) => Number(l.credit) > 0);
    assert(/Gaji/i.test(deb.account_name || ""), `akun debit ${deb.account_code} ${deb.account_name}`);
    return cekJurnal(je, [[deb.account_code, "D", net], [kre.account_code, "K", net]]);
  });

  let sisaAwal = 0;
  await r.step(5, "Finance", "Di \"Setoran BPJS dan PPh 21\" pilih *Masa gaji* Oktober 2026", "Kartu BPJS & PPh 21: Kewajiban · Sudah disetor · Sisa (dari gaji Oktober yang sudah diposting)", async () => {
    await pilih(r, "remit-period", "Oktober 2026");
    await r.idle(800);
    await r.tid("remit-card-pph21").waitFor();
    sisaAwal = num(await r.text("remit-card-pph21-sisa"));
    const bpjs = await r.text("remit-card-bpjs");
    const p21 = await r.text("remit-card-pph21");
    assert(sisaAwal + 0.5 >= pph, `sisa PPh 21 ${sisaAwal} < PPh 21 proses peserta ${pph}`);
    await sorot(r.tid("remit-create"));
    await r.shot("kewajiban-oktober");
    await lepas(r.tid("remit-create"));
    return `BPJS: ${bpjs} | PPh 21: ${p21}`;
  });

  await r.step(6, "Finance", `Klik [[Catat Setoran]] → *Jenis* PPh 21 · *Masa* Oktober 2026 · *Nominal* ${rp(pph)} (PPh 21 proses Anda) · *Tanggal setor* hari ini · *Rekening* BCA Operasional KSC · *Nomor bukti setor* ${ntpn} → [[Catat Setoran]] → konfirmasi [[Catat setoran]]`, "Pesan \"Setoran STR-… tercatat: PPh 21 Rp …\"; Sudah disetor PPh 21 naik, Sisa turun sebesar nominal; baris baru di Riwayat setoran", async () => {
    assert(pph > 0, "proses susulan peserta tanpa PPh 21 — periksa data awal d_hutang:gaji_susulan");
    await r.tid("remit-create").click();
    await r.tid("remit-form").waitFor();
    await pilih(r, "remit-form-kind", "PPh 21");
    await r.tid("remit-form-amount").fill(String(pph).replace(".", ","));   // koma desimal (PPh 21 bisa bersen)
    const accSel = r.tid("remit-form-account-select");
    if (await accSel.count()) {
      // Daftar rekening dimuat menyusul (satu rekening bank → kotak terkunci berisi rekening itu): tunggu teksnya dulu.
      let t = "";
      for (let i = 0; i < 20 && !t.trim(); i += 1) { t = await accSel.innerText().catch(() => ""); if (!t.trim()) await r.page.waitForTimeout(250); }
      if (!t.includes(REK_BCA)) await pilih(r, "remit-form-account-select", REK_BCA);
    }
    await r.tid("remit-form-ref").fill(ntpn);
    await sorot(r.tid("remit-form-submit"));
    await r.shot("form-setoran");
    await lepas(r.tid("remit-form-submit"));
    await r.tid("remit-form-submit").click();
    const msg = await r.text("confirm-modal-message");
    await klikPotret(r, r.tid("confirm-modal-confirm"), "konfirmasi-setoran");
    await r.tid("remit-form").waitFor({ state: "detached", timeout: 20000 });
    const ok = await tungguTeks(r, "remit-msg", /tercatat/);
    setor = mongo(`return db.hr_statutory_remittances.find({entity_id:"ent_ksc",reference:"${ntpn}",status:"done"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(setor && Math.abs(Number(setor.amount) - pph) < 0.01, `setoran DB ${setor && setor.amount}`);
    await r.idle(800);
    const sisa = num(await r.text("remit-card-pph21-sisa"));
    assert(Math.abs(sisaAwal - pph - sisa) <= 1, `sisa PPh 21 ${sisa}, harusnya ${sisaAwal - pph}`);
    await r.tid(`remit-row-${setor.id}`).waitFor();
    await sorot(r.tid("remit-card-pph21"));
    await sorot(r.tid(`remit-row-${setor.id}`));
    await r.shot("setoran-tercatat", { full: true });
    return `konfirmasi "${msg}" → ${ok} · sisa PPh 21 ${rp(sisaAwal)} → ${rp(sisa)}`;
  });

  await r.step(7, "Finance", "Cek buku: jurnal setoran PPh 21", "Hutang PPh 21 (D) = Kas Besar / Bank (K) = nominal setoran, seimbang; kas keluar dari BCA Operasional KSC", async () => {
    const je = setor.journal_entry_id ? mongo(`return db.journal_entries.findOne({id:"${setor.journal_entry_id}"},{_id:0})`)
      : jurnalDari([setor.cash_txn_id]).find(Boolean);
    assert(je, "jurnal setoran tidak ditemukan");
    const deb = je.lines.find((l) => Number(l.debit) > 0);
    const kre = je.lines.find((l) => Number(l.credit) > 0);
    assert(/PPh/i.test(deb.account_name || "") || deb.account_code === setor.contra_account_code, `akun debit ${deb.account_code} ${deb.account_name}`);
    const cash = mongo(`return db.cash_transactions.findOne({id:"${setor.cash_txn_id}"},{_id:0,account_id:1,number:1})`);
    const bank = mongo(`return db.bank_accounts.findOne({id:"${cash.account_id}"},{_id:0,name:1})`);
    assert(bank && bank.name === REK_BCA, `kas setoran dari ${bank && bank.name}`);
    return `${cekJurnal(je, [[deb.account_code, "D", pph], [kre.account_code, "K", pph]])} · ${setor.number} · kas ${cash.number} (${bank.name})`;
  });

  await r.finish();
})();
