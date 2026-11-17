// H04 — Bayar gaji & slip (Finance, K-SDM-01): proses susulan Oktober 2026 peserta (H03, Diposting) dibayar dari
// rekening berperuntukan Gaji → daftar transfer (rekening karyawan dari H01) → jurnal bayar Hutang Gaji (D) / Bank (K)
// → slip gaji PDF berkop PT → lanjut F15: kewajiban PPh 21 masa Oktober naik sebesar PPh 21 proses ini dan disetor.
//   node docs/pelatihan/2026-11-18_keuangan/uji/sdm/H04_bayar_gaji_slip.js      (bawaan peserta 51; KN_PESERTA=52 …)
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { Run, assert, rp, num, peserta, akunPeserta, mongo } = require("../lib");
const s = require("./sdm_lib");

(async () => {
  const no = peserta("51");
  const d = s.dataKaryawan(no);
  const r = await new Run("H04", "Bayar gaji & slip").start();
  const emp = s.karyawan(d.nama);
  let run = emp && s.prosesKaryawan(emp.id);
  if (!run || !["posted", "paid"].includes(run.status)) {
    r.note(`Proses gaji peserta ${no} belum Diposting (${run && run.status}) — jalankan H01–H03 dulu`); await r.finish(); return;
  }
  const net = Number(run.totals.net);
  const pph = Number(run.totals.pph21);
  const ntpn = `NTPN-SDM-${no}`;
  r.note(`Peserta ${no} · ${run.number} (${run.run_type} ${run.period}) · bersih ${rp(net)} · PPh 21 ${rp(pph)} · status ${run.status}`);
  let slip = null;
  let setor = null;

  await r.step(1, "Finance", "Login → SDM › Penggajian › Proses Gaji → pilih proses Anda (Diposting) → [[Bayar]]", "Pop-up \"Bayar gaji\": rekening berperuntukan Gaji, tanggal bayar, ringkasan \"Total bersih Rp … untuk 1 karyawan\"", async () => {
    await s.masuk(r, akunPeserta(no));
    await s.menu(r, "hrd", "hr-payroll-hub");
    await r.tid("hub-tab-hr-payroll-runs").click();
    await r.tid(`payroll-run-${run.id}`).waitFor({ timeout: 15000 });
    await r.tid(`payroll-run-${run.id}`).click();
    await r.tid("payroll-pay").waitFor();
    await s.klikPotret(r, r.tid("payroll-pay"), "klik-bayar", { locator: r.tid("payroll-run-detail") });
    await r.tid("pay-form").waitFor();
    await r.tid("pay-form-summary").waitFor({ timeout: 15000 });
    const acc = await r.text("pay-form-account");
    if (!acc.includes(s.REK_BCA)) await s.pilih(r, "pay-form-account", s.REK_BCA);
    const ring = await r.text("pay-form-summary");
    assert(ring.includes(s.rupiahTanpaRp(net)) && /1 karyawan/.test(ring), `ringkasan: ${ring}`);
    await s.sorot(r.tid("pay-form-submit"));
    await r.shot("form-bayar");
    await s.lepas(r.tid("pay-form-submit"));
    return `${await r.text("pay-form-account")} · ${ring}`;
  });

  await r.step(2, "Finance", "Klik [[Bayar gaji]] → konfirmasi [[Bayar gaji]]", "Status Dibayar; Daftar transfer terbuka: \"Dibayar … dari BCA Operasional KSC\", baris Andi Pratama · BCA · nomor rekening · gaji bersih", async () => {
    await r.tid("pay-form-submit").click();
    const msg = await s.konfirmasi(r, "konfirmasi-bayar");
    assert(msg.includes(s.REK_BCA) && msg.includes(s.rupiahTanpaRp(net)), `konfirmasi: ${msg}`);
    await r.tid("pay-form").waitFor({ state: "detached", timeout: 20000 });
    run = mongo(`return db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0})`);
    assert(run.status === "paid", `status ${run.status}`);
    if (!(await r.tid("transfer-panel").isVisible().catch(() => false))) await r.tid("payroll-paid-transfer").click();
    await r.tid("transfer-panel").waitFor({ timeout: 10000 });
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="transfer-loading"]'), null, { timeout: 15000 });
    const t = (await r.tid("transfer-panel").innerText()).replace(/\s+/g, " ");
    assert(t.includes(d.rekening) && t.includes(s.rupiahTanpaRp(net)), `daftar transfer: ${t.slice(0, 300)}`);
    const src = await r.text("transfer-source");
    assert(src.includes(s.REK_BCA), `sumber: ${src}`);
    await s.sorot(r.tid("transfer-download"));
    await r.shot("daftar-transfer");
    await s.lepas(r.tid("transfer-download"));
    return `"${msg}" · ${src} · ${t.slice(0, 200)}`;
  });

  await r.step(3, "Finance", "Klik [[Unduh Excel]] di Daftar transfer, lalu tutup (×)", "Berkas Excel daftar transfer (untuk unggah ke internet banking) terunduh", async () => {
    const [dl] = await Promise.all([r.page.waitForEvent("download", { timeout: 20000 }), r.tid("transfer-download").click()]);
    const f = path.join(r.dir, `transfer-${no}${path.extname(dl.suggestedFilename()) || ".xlsx"}`);
    await dl.saveAs(f);
    const ukuran = fs.statSync(f).size;
    assert(ukuran > 1000, `berkas transfer ${ukuran} bita`);
    await r.tid("transfer-modal-close-x").click();
    await r.tid("transfer-panel").waitFor({ state: "detached" });
    return `${dl.suggestedFilename()} (${ukuran} bita)`;
  });

  await r.step(4, "Finance", "Cek buku: jurnal bayar gaji", "2-1600 Hutang Gaji (D) = 1-1100 Kas Besar / Bank (K) = gaji bersih — seimbang; kas keluar dari BCA Operasional KSC", async () => {
    const je = mongo(`return db.journal_entries.findOne({id:"${run.paid_journal_id}"},{_id:0})`);
    assert(je, "jurnal bayar tidak ditemukan");
    const kre = je.lines.find((l) => Number(l.credit) > 0);
    const ring = s.cekJurnal(je, [["2-1600", "D", net], [kre.account_code, "K", net]]);
    const ref = await r.text("payroll-paid-info").catch(() => "");
    await s.sorot(r.tid("payroll-paid-info"));
    await r.shot("dibayar", { locator: r.tid("payroll-run-detail") });
    await s.lepas(r.tid("payroll-paid-info"));
    return `${ring} · ${ref}`;
  });

  await r.step(5, "Finance", "Klik [[Cari slip]] → ketik nama karyawan → klik barisnya → [[Unduh / Lihat PDF]]", "Slip gaji PDF berkop PT Sukacita Textile: nama, masa Oktober 2026, Rapel, PPh 21, gaji bersih", async () => {
    await r.tid("payroll-slip-search-toggle").click();
    await r.tid("payslips-view").waitFor();
    const cari = r.page.locator('[data-testid="payslips-view"] input[type="search"], [data-testid="payslips-view"] input').first();
    await cari.fill(`Latihan ${no}`);
    await r.idle(500);
    slip = mongo(`return db.hr_payslips.findOne({run_id:"${run.id}",employee_id:"${emp.id}"},{_id:0,id:1,number:1})`);
    await r.tid(`payslip-row-${slip.id}`).click();
    await r.tid("payslip-detail-pdf").waitFor();
    await s.sorot(r.tid("payslip-detail-pdf"));
    await r.shot("cari-slip");
    await s.lepas(r.tid("payslip-detail-pdf"));
    r.ctx.on("page", (pg) => pg.close().catch(() => {}));   // PDF dibuka di tab baru (blob) — cukup berkasnya
    const [resp] = await Promise.all([
      r.page.waitForResponse((x) => x.url().includes(`/hr/payslips/${slip.id}/pdf`), { timeout: 30000 }),
      r.tid("payslip-detail-pdf").click(),
    ]);
    assert(resp.status() === 200, `PDF ${resp.status()}`);
    const pdf = path.join(r.dir, `slip-${no}.pdf`);
    fs.writeFileSync(pdf, await resp.body());
    const teks = execFileSync("pdftotext", ["-layout", pdf, "-"]).toString().replace(/\s+/g, " ");
    for (const w of ["Sukacita Textile", "Andi Pratama", "Rapel", s.rupiahTanpaRp(net)]) assert(teks.includes(w), `PDF tanpa "${w}": ${teks.slice(0, 300)}`);
    const n = String(++r.n).padStart(2, "0");
    execFileSync("pdftoppm", ["-png", "-r", "80", "-f", "1", "-l", "1", "-singlefile", pdf, path.join(r.dir, `${n}-slip-pdf`)]);
    return `${slip.number} · PDF ${fs.statSync(pdf).size} bita · ${teks.slice(0, 220)}`;
  });

  await r.step(6, "Finance", "Tab [[Setoran & Pajak]] → *Masa gaji* Oktober 2026", "Kartu PPh 21 Oktober: Kewajiban memuat PPh 21 proses Anda (Rp 80.000); Sisa = Kewajiban − Sudah disetor", async () => {
    await r.go("hr-payroll-remittances");   // sesudah PDF dibuka di tab baru, kembali lewat alamat tab
    await r.tid("remit-period").waitFor({ timeout: 15000 });
    await s.pilih(r, "remit-period", s.MASA_LABEL);
    await r.idle(800);
    await r.tid("remit-card-pph21").waitFor();
    const sisa = num(await r.text("remit-card-pph21-sisa"));
    assert(sisa + 0.5 >= pph, `sisa PPh 21 ${sisa} < ${pph}`);
    await s.sorot(r.tid("remit-card-pph21"));
    await r.shot("kewajiban-oktober");
    await s.lepas(r.tid("remit-card-pph21"));
    return `${await r.text("remit-card-pph21")}`;
  });

  await r.step(7, "Finance", `Lanjutan F15: [[Catat Setoran]] → *Jenis* PPh 21 · *Masa* Oktober 2026 · *Nominal* ${s.rupiahTanpaRp(pph)} · *Rekening* BCA Operasional KSC · *Nomor bukti setor* ${ntpn} → [[Catat Setoran]] → konfirmasi`, "Pesan \"Setoran KSC/STR-… tercatat: PPh 21 Rp …\"; jurnal 2-1800 Hutang PPh 21 (D) = Bank (K)", async () => {
    const sisaAwal = num(await r.text("remit-card-pph21-sisa"));
    await r.tid("remit-create").click();
    await r.tid("remit-form").waitFor();
    await s.pilih(r, "remit-form-kind", "PPh 21");
    const masa = await r.text("remit-form-period").catch(() => "");
    if (masa && !masa.includes(s.MASA_LABEL)) await s.pilihPersis(r, "remit-form-period", s.MASA_LABEL);
    await r.tid("remit-form-amount").fill(String(pph).replace(".", ","));
    const accSel = r.tid("remit-form-account-select");
    if (await accSel.count()) {
      // Daftar rekening dimuat menyusul (satu rekening bank → kotak terkunci berisi rekening itu): tunggu teksnya dulu.
      let t = "";
      for (let i = 0; i < 20 && !t.trim(); i += 1) { t = await accSel.innerText().catch(() => ""); if (!t.trim()) await r.page.waitForTimeout(250); }
      if (!t.includes(s.REK_BCA)) await s.pilih(r, "remit-form-account-select", s.REK_BCA);
    }
    await r.tid("remit-form-ref").fill(ntpn);
    await s.sorot(r.tid("remit-form-submit"));
    await r.shot("form-setoran");
    await s.lepas(r.tid("remit-form-submit"));
    await r.tid("remit-form-submit").click();
    const msg = await s.konfirmasi(r, "konfirmasi-setoran");
    await r.tid("remit-form").waitFor({ state: "detached", timeout: 20000 });
    const ok = await s.tungguTeks(r, "remit-msg", /tercatat/);
    setor = mongo(`return db.hr_statutory_remittances.find({entity_id:"ent_ksc",reference:"${ntpn}",status:"done"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(setor && setor.period === s.MASA && Math.abs(Number(setor.amount) - pph) < 0.01, `setoran DB ${JSON.stringify(setor && { p: setor.period, a: setor.amount })}`);
    await r.idle(800);
    const sisa = num(await r.text("remit-card-pph21-sisa"));
    assert(Math.abs(sisaAwal - pph - sisa) <= 1, `sisa PPh 21 ${sisa}, harusnya ${sisaAwal - pph}`);
    const je = setor.journal_entry_id ? mongo(`return db.journal_entries.findOne({id:"${setor.journal_entry_id}"},{_id:0})`)
      : s.jurnalDari([setor.cash_txn_id]).find(Boolean);
    const kre = je.lines.find((l) => Number(l.credit) > 0);
    const ring = s.cekJurnal(je, [["2-1800", "D", pph], [kre.account_code, "K", pph]]);
    await r.shot("setoran-tercatat");
    return `"${msg}" → ${ok} · ${ring}`;
  });

  await r.finish();
})();
