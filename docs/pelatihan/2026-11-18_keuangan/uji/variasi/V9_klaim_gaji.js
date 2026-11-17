// V9 · SDM & GAJI — bukti di LAYAR untuk klaim teks materi H01–H04, F15 dan A4 yang belum dibuktikan uji lain.
// Tiap langkah = satu klaim (`kode · klaim`), dikerjakan dengan akun peran yang benar lalu dicocokkan dengan buku.
//
//   KN_PESERTA=90 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_klaim_gaji.js
//
// Data peserta SEGAR: karyawan baru BELUM dibuat (isian Kartu Peserta › Karyawan baru), proses gaji susulan peserta
// (`d_hutang:gaji_susulan`) Diposting & belum dibayar. Hasil → uji/hasil/V9/gaji/.
const { Run, assert, peserta, akunPeserta, rp, num, sleep, mongo, kartu } = require("../lib");
const s = require("../sdm/sdm_lib");
const k9 = require("./v9lib");

const NO = peserta("90");
const REK_BCA = "BCA Operasional KSC";

(async () => {
  k9.bersihkan("gaji");
  const d = k9.daftar("gaji");
  const r = await new Run(d.kode, `V9 · Bukti klaim materi SDM & Gaji (H01–H04, F15, A4) · peserta ${NO}`).start();
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const dk = s.dataKaryawan(NO);
  const g = kartu(NO)["d_hutang:gaji_susulan"];
  const hariIni = mongo(`return new Date(Date.now()+7*3600000).toISOString().slice(0,10)`);
  let emp = null;
  const bukaRuns = async () => {
    await s.menu(r, "hrd", "hr-payroll-hub");
    await r.tid("hub-tab-hr-payroll-runs").click();
    await r.tid("payroll-runs-view").waitFor();
    await r.idle(500);
  };
  const bukaSetoran = async () => {
    await s.menu(r, "hrd", "hr-payroll-hub");
    if (await r.tid("hub-tab-hr-payroll-remittances").count()) await r.tid("hub-tab-hr-payroll-remittances").click();
    await r.tid("pay-queue").waitFor();
    await r.idle(500);
  };

  try {
    assert(g && g.status === "posted", `Kartu peserta ${NO} tanpa gaji susulan terposting`);
    assert(!s.karyawan(dk.nama), `Karyawan ${dk.nama} sudah ada — pakai peserta segar`);
    const run0 = mongo(`return db.hr_payroll_runs.findOne({id:"${g.proses_gaji_id}"},{_id:0,status:1,number:1})`);
    assert(run0.status === "posted", `proses ${run0.number} ${run0.status}`);
    r.note(`Peserta ${NO} · ${dk.nama} · proses susulan ${g.proses_gaji} (${run0.status}) bersih ${rp(g.gaji_bersih)} PPh 21 ${rp(g.pph21)}`);

    // ── H01: tanpa Tanggal Masuk → kompensasi berlaku sejak hari ini; gaji pokok tidak diubah lewat Ubah karyawan ──────
    await s.masuk(r, akunPeserta(NO));
    await step({ kode: "H01", bagian: "kesalahan_umum.1", peran: "Finance",
      klaim: "Tanggal masuk dikosongkan: kompensasi lalu berlaku sejak hari ini, bukan sejak tanggal masuk",
      harap: `Tambah Karyawan ${dk.nama} tanpa Tanggal Masuk → tersimpan; Karyawan 360° › Riwayat Kompensasi: berlaku sejak ${hariIni} (hari ini)` },
    async () => {
      await s.menu(r, "hrd", "hr-people");
      await r.tid("employees-view").waitFor();
      await r.tid("create-employee-button").click();
      await r.tid("employee-form-drawer").waitFor();
      await r.tid("employee-name-input").fill(dk.nama);
      await r.tid("employee-nik-input").fill(dk.nik);
      const pt = await r.text("employee-entity-select").catch(() => "");
      if (!/Sukacita/i.test(pt)) await s.pilih(r, "employee-entity-select", "Sukacita");
      await r.tid("employee-npwp-input").fill(dk.npwp);
      await s.pilihPersis(r, "employee-ptkp-select", dk.ptkp.replace("/", ""));
      await r.tid("employee-bank-name-input").fill(dk.bank);
      await r.tid("employee-bank-acc-input").fill(dk.rekening);
      await r.tid("employee-bank-name-acc-input").fill(dk.atas_nama);
      await r.tid("employee-salary-input").fill(String(dk.gaji_pokok).replace(/\B(?=(\d{3})+(?!\d))/g, "."));
      const tgl = await k9.teks(r, "employee-joindate-input");
      await r.shot("h01-tanpa-tanggal-masuk", { locator: r.tid("employee-form-drawer") });
      await r.tid("employee-save-button").click();
      await r.tid("employee-form-drawer").waitFor({ state: "detached", timeout: 20000 });
      emp = s.karyawan(dk.nama);
      assert(emp, "karyawan tidak tersimpan");
      const komp = mongo(`return db.hr_compensation_history.find({employee_id:"${emp.id}"},{_id:0}).toArray()`)
        || [];
      await r.tid("employee-search").fill(`Latihan ${NO}`);
      await r.tid(`detail-employee-${emp.id}`).click();
      await r.tid("emp-comp-section").waitFor({ timeout: 15000 });
      await r.idle(800);
      const t = await k9.teks(r, "emp-comp-section");
      await r.tid("emp-comp-section").scrollIntoViewIfNeeded();
      await r.shot("h01-kompensasi-hari-ini");
      const berlaku = (komp[0] && (komp[0].effective_from || komp[0].effective_date)) || "";
      assert(!emp.join_date && berlaku.slice(0, 10) === hariIni, `join_date '${emp.join_date}' · kompensasi berlaku '${berlaku}' (${JSON.stringify(komp).slice(0, 200)})`);
      await r.tid("employee-360-back").click().catch(() => {});
      await r.idle(500);
      return `isian Tanggal Masuk: '${tgl}' (kosong) · ${emp.code || emp.employee_code || emp.id} · kompensasi berlaku ${berlaku} · layar: ${t.slice(0, 150)}`;
    });

    await step({ kode: "H01", bagian: "kesalahan_umum.3", peran: "Finance",
      klaim: "Gaji pokok tidak diubah lewat Ubah karyawan; perubahan gaji diajukan di Riwayat Kompensasi",
      harap: "Ubah karyawan: kotak Gaji Pokok mati dengan petunjuk 'Ubah lewat Riwayat Kompensasi.'" },
    async () => {
      if (await r.tid("employee-360-back").count()) await r.tid("employee-360-back").click().catch(() => {});
      await s.menu(r, "hrd", "hr-people");
      await r.tid("employees-view").waitFor();
      await r.tid("employee-search").fill(`Latihan ${NO}`);
      await r.tid(`edit-employee-${emp.id}`).click();
      await r.tid("employee-form-drawer").waitFor();
      const mati = await r.tid("employee-salary-input").isDisabled();
      const hint = await k9.teks(r, "employee-salary-hint");
      await r.tid("employee-salary-input").scrollIntoViewIfNeeded();
      await r.shot("h01-ubah-gaji-mati", { locator: r.tid("employee-form-drawer") });
      await r.tid("employee-cancel-button").click();
      assert(mati && /Riwayat Kompensasi/.test(hint), `kotak gaji mati=${mati} · '${hint}'`);
      return `kotak Gaji Pokok mati · '${hint}'`;
    });

    // ── H02: masukan bersen ditolak ──────────────────────────────────────────────────────────────────────────────────
    await step({ kode: "H02", bagian: "kesalahan_umum.1", peran: "Finance",
      klaim: "Nominal masukan gaji: sen ditolak (rupiah bulat)",
      harap: "Tambah masukan Rapel '8.000.000,50' → pratinjau Rp 8.000.000,50 → [Simpan masukan] ditolak dengan pesan 'rupiah bulat'; tidak ada masukan tersimpan" },
    async () => {
      await r.go("hr-pay-components");
      await r.tid("payinput-add").waitFor({ timeout: 15000 });
      await r.tid("payinput-add").click();
      await r.tid("payinput-form").waitFor();
      await s.pilih(r, "payinput-form-emp", dk.nama);
      await s.pilihPersis(r, "payinput-form-period", s.MASA_LABEL).catch(() => {});
      const box = r.tid("payinput-form-amount");
      await box.click(); await box.press("Control+A"); await box.press("Delete");
      await r.page.keyboard.type("8.000.000,50", { delay: 15 });
      await r.tid("payinput-form-label").fill("Rapel uji sen");
      await r.tid("payinput-form-reason").fill(`V9 latihan ${NO}`);
      await sleep(400);
      await r.tid("payinput-form-submit").click();
      const err = await s.tungguTeks(r, "payinput-form-error", /bulat/, 15000);
      await r.shot("h02-sen-ditolak", { locator: r.tid("payinput-form") });
      const n = mongo(`return db.hr_pay_inputs.countDocuments({employee_id:"${emp.id}"})`);
      await r.tid("payinput-form-cancel").click();
      assert(!n, `masukan tersimpan: ${n}`);
      return `pesan: ${err} · masukan tersimpan: ${n}`;
    });

    // ── H03: jenis Reguler membuka proses yang ada; susulan tanpa masukan ─────────────────────────────────────────────
    await step({ kode: "H03", bagian: "kesalahan_umum.1", peran: "Finance",
      klaim: "Memilih jenis Reguler: proses reguler Oktober sudah ada, layar membuka proses itu, bukan membuat baru",
      harap: "Proses Gaji › Oktober 2026 · Reguler → [Hitung gaji] → rincian proses reguler yang sudah ada (KSC/PAY-00001, Diposting) terbuka; jumlah proses reguler Oktober tetap satu" },
    async () => {
      const sebelum = mongo(`return db.hr_payroll_runs.find({entity_id:"ent_ksc",period:"2026-10",run_type:"regular"},{_id:0,number:1,status:1}).toArray()`);
      await bukaRuns();
      const pt = await r.text("payroll-create-entity").catch(() => "");
      if (!/Sukacita/i.test(pt)) await s.pilih(r, "payroll-create-entity", "Sukacita");
      const persis = async (id, lbl) => { try { await s.pilihPersis(r, id, lbl); } catch (_) { await r.page.keyboard.press("Escape"); await r.idle(800); await s.pilihPersis(r, id, lbl); } };
      await persis("payroll-create-period", s.MASA_LABEL);
      await persis("payroll-create-type", "Reguler");
      await r.tid("payroll-create-submit").click();
      const msg = await s.tungguTeks(r, "payroll-notice", /siap/, 30000);
      await r.tid("payroll-run-detail").waitFor();
      const detail = await k9.teks(r, "payroll-run-detail");
      const sesudah = mongo(`return db.hr_payroll_runs.find({entity_id:"ent_ksc",period:"2026-10",run_type:"regular"},{_id:0,number:1,status:1}).toArray()`);
      await r.shot("h03-reguler-yang-ada");
      assert(sebelum.length === 1 && sesudah.length === 1 && msg.includes(sebelum[0].number), `sebelum ${JSON.stringify(sebelum)} · sesudah ${JSON.stringify(sesudah)} · ${msg}`);
      return `${msg} · proses reguler Oktober: ${sesudah.map((x) => `${x.number} ${x.status}`).join(", ")} · rincian: ${detail.slice(0, 100)}`;
    });

    await step({ kode: "H03", bagian: "kesalahan_umum.2", peran: "Finance",
      klaim: "\"Tidak ada masukan yang belum terpakai untuk Oktober 2026\": masukan belum disahkan atau periodenya salah",
      harap: "Jenis Susulan Oktober 2026 saat tidak ada masukan disahkan yang belum terpakai → [Hitung gaji] ditolak dengan pesan itu; tidak ada proses baru" },
    async () => {
      const siap = mongo(`return db.hr_pay_inputs.countDocuments({entity_id:"ent_ksc",pay_period:"2026-10",status:"approved"})`);
      assert(!siap, `ada ${siap} masukan disahkan belum terpakai (milik peserta lain) — langkah dilewati supaya tidak terserap`);
      const n0 = mongo(`return db.hr_payroll_runs.countDocuments({entity_id:"ent_ksc",period:"2026-10"})`);
      await s.pilihPersis(r, "payroll-create-type", "Susulan");
      await r.tid("payroll-create-submit").click();
      const err = await s.tungguTeks(r, "payroll-runs-error", /masukan/, 20000).catch(async () => k9.teks(r, "payroll-runs-view"));
      const n1 = mongo(`return db.hr_payroll_runs.countDocuments({entity_id:"ent_ksc",period:"2026-10"})`);
      await r.shot("h03-susulan-tanpa-masukan");
      assert(/Tidak ada masukan/.test(err) && /Oktober 2026/.test(err) && n0 === n1, `pesan '${err.slice(0, 200)}' · proses ${n0} → ${n1}`);
      return `pesan: ${err.slice(0, 200)} · proses Oktober ${n0} → ${n1}`;
    });

    // ── H04: gaji yang sudah dibayar tidak bisa dianulir ─────────────────────────────────────────────────────────────
    const lihatRun = async () => {
      await r.go("hr-payroll-runs");
      await r.tid(`payroll-run-${g.proses_gaji_id}`).waitFor({ timeout: 15000 });
      await r.tid(`payroll-run-${g.proses_gaji_id}`).click();
      await r.tid("payroll-run-detail").waitFor();
      await r.idle(600);
    };
    await s.masuk(r, "manager");
    await step({ kode: "H04", bagian: "konsep.1", peran: "Manajer",
      klaim: "Proses yang diposting (belum dibayar) masih bisa dianulir Manajer",
      harap: `Manajer membuka ${g.proses_gaji} (Diposting): tombol [Anulir] tersedia (tidak diklik)` },
    async () => {
      await lihatRun();
      const n = await r.tid("payroll-void").count();
      await r.shot("h04-diposting-ada-anulir", { locator: r.tid("payroll-run-detail") });
      assert(n === 1, `tombol Anulir ${n}`);
      return `${g.proses_gaji} Diposting · [Anulir] tersedia untuk Manajer`;
    });

    await s.masuk(r, akunPeserta(NO));
    await step({ kode: "A4", bagian: "titik_kontrol.4", peran: "Finance",
      klaim: "Bayar gaji hanya dari rekening berperuntukan Gaji",
      harap: `Setoran & Pajak › Gaji siap dibayar › [Bayar] ${g.proses_gaji}: pilihan rekening hanya rekening berperuntukan Gaji (${REK_BCA}); bayar → status Dibayar` },
    async () => {
      await bukaSetoran();
      await r.tid(`pay-queue-pay-${g.proses_gaji_id}`).click();
      await r.tid("pay-form").waitFor();
      await r.tid("pay-form-summary").waitFor({ timeout: 15000 });
      const acc = await k9.teks(r, "pay-form-account");
      if (!acc.includes(REK_BCA)) await s.pilih(r, "pay-form-account", REK_BCA);
      await r.tid("pay-form-account").click();
      const pilihan = (await r.page.getByRole("option").allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());
      await r.page.keyboard.press("Escape");
      await sleep(300);
      const pf = await k9.teks(r, "pay-form");
      const gaji = mongo(`return db.bank_accounts.find({entity_id:"ent_ksc",is_active:{$ne:false}},{_id:0,name:1,purposes:1}).toArray()`);
      await r.shot("a4-rekening-gaji", { locator: r.tid("pay-form") });
      await r.tid("pay-form-submit").click();
      await r.tid("confirm-modal-confirm").click();
      await r.tid("pay-form").waitFor({ state: "detached", timeout: 20000 });
      const run = mongo(`return db.hr_payroll_runs.findOne({id:"${g.proses_gaji_id}"},{_id:0,status:1,pay_account_name:1})`);
      assert(run.status === "paid" && run.pay_account_name === REK_BCA && pf.includes(REK_BCA), `status ${run.status} · rekening ${run.pay_account_name}`);
      const tutup = await r.tid("transfer-modal-close-x").count(); if (tutup) await r.tid("transfer-modal-close-x").click();
      const peruntukan = gaji.map((a) => `${a.name}: ${(a.purposes || []).join(",")}`).join(" | ");
      const berGaji = gaji.filter((a) => (a.purposes || []).includes("gaji")).map((a) => a.name);
      assert(pilihan.length && pilihan.every((t) => berGaji.some((n) => t.includes(n))), `pilihan ${JSON.stringify(pilihan)} · bergaji ${berGaji}`);
      return `pilihan rekening: ${pilihan.join(" | ")} (= rekening berperuntukan Gaji; ${peruntukan}) · petunjuk '${(pf.match(/Hanya rekening[^.]*\./) || [""])[0]}' · ${g.proses_gaji} ${run.status} dari ${run.pay_account_name}`;
    });

    await s.masuk(r, "manager");
    await step({ kode: "H04", bagian: "konsep.1", peran: "Manajer",
      klaim: "Gaji yang sudah dibayar tidak bisa dianulir; koreksinya lewat proses susulan",
      harap: `Manajer membuka ${g.proses_gaji} (Dibayar): tombol [Anulir] tidak ada lagi` },
    async () => {
      await lihatRun();
      const st = await k9.teks(r, "payroll-run-detail");
      const n = await r.tid("payroll-void").count();
      await r.shot("h04-dibayar-tanpa-anulir", { locator: r.tid("payroll-run-detail") });
      assert(n === 0 && /Dibayar/.test(st), `tombol Anulir ${n} · ${st.slice(0, 120)}`);
      return `${g.proses_gaji} Dibayar · [Anulir] tidak ada`;
    });

    // ── F15: masa November Rp 0; batal setoran hanya Manajer ─────────────────────────────────────────────────────────
    await s.masuk(r, akunPeserta(NO));
    let setor = null;
    await step({ kode: "F15", bagian: "kesalahan_umum.1", peran: "Finance",
      klaim: "Membiarkan Masa gaji di bulan berjalan (November): kartu menunjukkan Rp 0",
      harap: "Setoran & Pajak › Masa gaji November 2026 → kartu PPh 21 & BPJS: Kewajiban Rp 0 (gaji November belum diposting); Oktober 2026 → kewajiban > 0" },
    async () => {
      const nov = mongo(`return db.hr_payroll_runs.countDocuments({entity_id:"ent_ksc",period:"2026-11",status:{$in:["posted","paid"]}})`);
      await bukaSetoran();
      const kartuSiap = () => r.page.waitForFunction(() => /Kewajiban/.test(document.querySelector('[data-testid="remit-card-pph21"]')?.innerText || "")
        && /Kewajiban/.test(document.querySelector('[data-testid="remit-card-bpjs"]')?.innerText || ""), null, { timeout: 20000 });
      await s.pilih(r, "remit-period", "November 2026");
      await r.idle(800);
      await kartuSiap();
      const pNov = await k9.teks(r, "remit-card-pph21"); const bNov = await k9.teks(r, "remit-card-bpjs");
      await r.shot("f15-masa-november");
      await s.pilih(r, "remit-period", "Oktober 2026");
      await r.idle(800);
      await kartuSiap();
      await r.page.waitForFunction(() => !/Kewajiban\s*Rp\s*0\b/.test(document.querySelector('[data-testid="remit-card-pph21"]')?.innerText || ""), null, { timeout: 20000 }).catch(() => {});
      const pOkt = await k9.teks(r, "remit-card-pph21");
      const kewajiban = (t) => num((t.match(/Kewajiban\s*(Rp\s*[\d.,]+)/) || [])[1] || "");
      assert(!nov && kewajiban(pNov) === 0 && kewajiban(bNov) === 0 && kewajiban(pOkt) > 0, `Nov: ${pNov} | ${bNov} · Okt: ${pOkt}`);
      return `November: ${pNov} | ${bNov} · Oktober: ${pOkt}`;
    });

    await step({ kode: "F15", bagian: "catatan_pelatih", peran: "Finance",
      klaim: "Membatalkan setoran butuh izin Manajer",
      harap: `Finance [Catat Setoran] PPh 21 ${rp(g.pph21)} masa Oktober → tercatat; di Riwayat setoran Finance tidak punya [Batalkan]; Manajer punya` },
    async () => {
      const ntpn = `NTPN-V9-${NO}`;
      // Kartu Setoran & Pajak bisa tertimpa jawaban masa sebelumnya bila masa diganti cepat (temuan V9): pilih ulang
      // Oktober dan tunggu kartu PPh 21 menampilkan sisa > 0 sebelum membuka form.
      await s.pilih(r, "remit-period", "Oktober 2026");
      await r.page.waitForFunction(() => /Sisa\s*Rp\s*[1-9]/.test(document.querySelector('[data-testid="remit-card-pph21"]')?.innerText || ""), null, { timeout: 30000 });
      await r.tid("remit-create").click();
      await r.tid("remit-form").waitFor();
      await s.pilih(r, "remit-form-kind", "PPh 21");
      await r.tid("remit-form-amount").fill(String(g.pph21).replace(".", ","));
      const accSel = r.tid("remit-form-account-select");
      if (await accSel.count()) {
        let t = "";
        for (let i = 0; i < 20 && !t.includes(REK_BCA); i += 1) { t = await accSel.innerText().catch(() => ""); if (!t.includes(REK_BCA)) await sleep(250); }
        if (!t.includes(REK_BCA) && !(await accSel.isDisabled().catch(() => false))) await s.pilih(r, "remit-form-account-select", REK_BCA);
      }
      await r.tid("remit-form-ref").fill(ntpn);
      // Sisa kewajiban masa dimuat menyusul — kirim sesudah angkanya tampil (> 0).
      await r.page.waitForFunction(() => /Sisa kewajiban:\s*Rp\s*[1-9]/.test(document.querySelector('[data-testid="remit-form"]')?.innerText || ""), null, { timeout: 20000 });
      await r.tid("remit-form-submit").click();
      await r.tid("confirm-modal-confirm").click();
      await r.tid("remit-form").waitFor({ state: "detached", timeout: 20000 });
      setor = mongo(`return db.hr_statutory_remittances.find({entity_id:"ent_ksc",reference:"${ntpn}",status:"done"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(setor, "setoran tidak tersimpan");
      await r.tid(`remit-row-${setor.id}`).waitFor({ timeout: 15000 });
      const fin = await r.tid(`remit-void-${setor.id}`).count();
      await r.shot("f15-finance-tanpa-batal");
      await s.masuk(r, "manager");
      await bukaSetoran();
      await s.pilih(r, "remit-period", "Oktober 2026");
      await r.tid(`remit-row-${setor.id}`).waitFor({ timeout: 15000 });
      const mgr = await r.tid(`remit-void-${setor.id}`).count();
      await r.shot("f15-manajer-ada-batal");
      assert(!fin && mgr === 1, `tombol Batalkan: Finance ${fin} · Manajer ${mgr}`);
      return `${setor.number || setor.id} PPh 21 ${rp(setor.amount)} · [Batalkan]: Finance tidak ada · Manajer ada (tidak diklik)`;
    });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  d.simpan();
  await r.finish();
})();
