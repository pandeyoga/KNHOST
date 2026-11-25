// V10 — K-FIN-01: Finance memegang akses yang SAMA dengan Manajer (keputusan pemilik 17 Nov 2026 malam, kata-kata asli:
// "untuk sekarang finance juga memiliki akses yang sama dengan manager dan jangan dipisah"). Bukti di LAYAR dengan akun
// Finance peserta (bawaan finance.latih01): layar khas Manajer terbuka, tombol aksinya tampil, dan aksinya berhasil (bukan 403).
//   node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V10_finance_setara_manajer.js       (KN_PESERTA=01 bawaan)
//
// Yang diuji (semua dikerjakan Finance di layar; persiapan & pembersihan lewat API):
//   1 Meja Saya = Meja Manajer · 2 Pusat Persetujuan · 3 Kredit & Plafon: Setujui izin kredit (dulu Manajer saja)
//   4 Kontrabon: Setujui (dulu Manajer/Admin) — kontrol dua orang tetap: pengaju Manajer, penyetuju Finance
//   5 Jurnal Baru + Balik Jurnal (dulu Buku Besar lihat saja) — efek bersih nol
//   6 Tutup Buku September 2026 (bulan kosong, seperti F18) — dibuka kembali Admin sesudahnya
//   7 Penggajian: Sahkan masukan gaji & Sahkan proses gaji (dulu Manajer, K-SDM-01) — dibatalkan sesudahnya
//   8 Pusat Pengaturan › Keuangan & Pajak: pengaturan berizin Manajer bisa diubah Finance; yang khusus Admin tetap terkunci
// Data: kartu peserta (izin kredit `b_piutang:izin_kredit`, tagihan `a_dasar:tagihan_kontrabon`) — hanya bila belum dipakai.
const { Run, api, assert, rp, kartu, peserta, akunPeserta, mongo } = require("../lib");
const { pilih: pilihLabel, tungguTeks, sorot, lepas, klikPotret, menu } = require("../hutang_lib");
const bl = require("../buku_lib");

const KSC = "ent_ksc";
const MASA = "2026-11";
const TUTUP = "2026-09";
const KET = "Uji K-FIN-01 — Finance setara Manajer";

(async () => {
  const no = peserta("01");
  const akun = akunPeserta(no);
  const k = kartu(no);
  const r = await new Run("V10", "K-FIN-01 — Finance setara Manajer di layar").start();
  const fin = await api(akun);
  const mgr = await api("manager");
  const adm = await api("admin");
  r.note(`Akun ${akun}@ (${fin.user.name}) · peran ${fin.user.role}`);

  // ── Persiapan (API) ───────────────────────────────────────────────────────────────────────────────────────────────
  const izin = k["b_piutang:izin_kredit"];
  const izinDoc = izin && mongo(`return db.credit_overrides.findOne({id:"${izin.izin_id}"},{_id:0,id:1,status:1,customer_name:1,amount:1})`);
  const tg = k["a_dasar:tagihan_kontrabon"];
  const bill = tg && mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0,id:1,status:1,supplier_id:1,supplier_name:1,grand_total:1,bill_number:1})`);
  const sudahCb = tg && mongo(`return db.contra_bons.findOne({"bills.bill_id":"${tg.tagihan_id}",status:{$ne:"cancelled"}},{_id:0,id:1,number:1,status:1,notes:1,approved_by:1})`);
  // Kontrabon yang sudah DISETUJUI tidak bisa dibatalkan: putaran ulang memeriksa kontrabon uji dari putaran sebelumnya.
  const cbLama = sudahCb && sudahCb.notes === KET && sudahCb.status === "approved" ? sudahCb : null;
  let cb = null;
  if (bill && !sudahCb) {
    cb = await mgr.post("/contra-bons", { supplier_id: bill.supplier_id, entity_id: KSC, bills: [{ bill_id: bill.id }],
      notes: KET, submit_now: true }, KSC);
    cb = await mgr.post(`/contra-bons/${cb.id}/verify`, {}, KSC);
    r.note(`Kontrabon ${cb.number} dibuat, diajukan & diverifikasi Manajer (${bill.bill_number} ${rp(bill.grand_total)})`);
  } else r.note(`Tagihan kontrabon peserta ${no} tidak tersedia / sudah berkontrabon — langkah 4 tanpa data`);
  const emp = mongo(`return db.hr_employees.findOne({entity_id:"${KSC}",status:"active",code:"EMP-00001"},{_id:0,id:1,name:1})`);
  const inputLain = mongo(`return db.hr_pay_inputs.countDocuments({entity_id:"${KSC}",pay_period:"${MASA}",status:{$in:["pending","approved"]}})`);
  assert(!inputLain, `${inputLain} masukan gaji lain menunggu di ${MASA} — uji gaji dihentikan agar tidak ikut terproses`);
  const inp = await fin.post("/hr/payroll/inputs", { employee_id: emp.id, component_code: "RAPEL", pay_period: MASA,
    amount: 100000, label: "Uji K-FIN-01", reason: KET }, KSC);
  r.note(`Masukan gaji ${inp.id} (${emp.name}, ${rp(inp.amount)}, ${MASA}) dicatat Finance — menunggu disahkan`);
  let run = null;
  let closingId = "";
  let je = null;

  try {
    await r.step(1, "Finance", `Login ${akun}@ → menu [[Meja Saya]]`, "Judul halaman 'Meja Saya' (antrean keputusan Manajer); menu samping memuat Tutup Buku, Pusat Persetujuan, SDM", async () => {
      await r.login(akun);
      await r.go("my-desk");
      // Meja gelombang 1 (§5.1) — satu kepala: judul meja = judul halaman di bilah atas (tanpa judul kedua di meja).
      await r.tid("my-desk").waitFor({ timeout: 20000 });
      const judul = await r.text("page-title");
      assert(/Meja Saya/.test(judul), `judul meja: ${judul}`);
      await r.idle(800);
      await r.shot("meja-manajer");
      return judul;
    });

    await r.step(2, "Finance", "Buka Pusat Persetujuan", "Layar terbuka tanpa galat akses; tab persetujuan lintas modul (matriks) tersedia seperti untuk Manajer", async () => {
      await r.go("approval-inbox");
      await r.tid("approval-inbox-view").waitFor({ timeout: 20000 });
      await r.idle(800);
      const t = await r.text("approval-inbox-title");
      assert(!(await r.page.getByText(/belum punya akses/i).count()), "pesan akses ditolak tampil");
      await r.shot("pusat-persetujuan");
      return `${t} · ${await r.text("approval-inbox-backlog").catch(() => "")}`.slice(0, 200);
    });

    await r.step(3, "Finance", "Keuangan › Piutang › tab [[Kredit & Plafon]] → izin kredit peserta → [[Setujui]] → catatan → [[Setujui]]", "Tombol Setujui/Tolak tampil (dulu khusus Manajer); status izin Disetujui", async () => {
      assert(izinDoc && izinDoc.status === "pending", `izin kredit peserta ${no} tidak menunggu: ${JSON.stringify(izinDoc)}`);
      await r.go("credit-overrides", `&entity=${KSC}`);
      await r.tid("credit-desk-view").waitFor({ timeout: 20000 });
      await r.tid("credit-desk-search").fill(izinDoc.customer_name);
      await r.idle(800);
      await r.tid(`credit-desk-row-${izinDoc.id}`).waitFor({ timeout: 20000 });
      await klikPotret(r, r.tid(`credit-desk-approve-${izinDoc.id}`), "izin-kredit-setujui");
      await r.tid("credit-desk-decision-reason").fill(`${KET}: plafon sementara disetujui`);
      await r.tid("credit-desk-decision-confirm").click();
      await tungguTeks(r, "credit-desk-notice", /disetujui|Disetujui/);
      const st = mongo(`return db.credit_overrides.findOne({id:"${izinDoc.id}"},{_id:0,status:1,approved_by:1,decided_by:1})`);
      assert(["approved", "active"].includes(st.status), `status ${st.status}`);
      await r.shot("izin-kredit-disetujui");
      return `${izinDoc.customer_name} ${rp(izinDoc.amount)} → ${st.status} oleh ${st.approved_by || st.decided_by || "Finance"}`;
    });

    await r.step(4, "Finance", "Keuangan › Hutang › tab [[Kontrabon]] → kontrabon Terverifikasi yang diajukan Manajer → [[Setujui kontrabon]]", "Status Disetujui (dulu Manajer/Admin); kontrol dua orang: pengaju (Manajer) ≠ penyetuju (Finance)", async () => {
      if (!cb && cbLama) {   // putaran ulang: tagihan peserta sudah dipakai kontrabon uji yang disetujui Finance
        assert(cbLama.approved_by === fin.user.name, `kontrabon ${cbLama.number} disetujui ${cbLama.approved_by}`);
        await r.go("contra-bons", `&entity=${KSC}`);
        await r.tid("contra-bons-view").waitFor();
        await r.tid("cb-filter-q").fill(cbLama.number);
        await r.tid(`cb-row-${cbLama.id}`).click();
        await tungguTeks(r, "cb-detail-status", /Disetujui/);
        await r.shot("kontrabon-disetujui-putaran-lalu");
        return `${cbLama.number} sudah disetujui ${cbLama.approved_by} pada putaran sebelumnya (kontrabon disetujui tidak bisa dibatalkan)`;
      }
      assert(cb, "tidak ada kontrabon uji");
      await r.go("contra-bons", `&entity=${KSC}`);
      await r.tid("contra-bons-view").waitFor();
      await r.tid("cb-filter-q").fill(cb.number);
      await r.tid(`cb-row-${cb.id}`).waitFor({ timeout: 15000 });
      await r.tid(`cb-row-${cb.id}`).click();
      await r.tid("cb-detail-panel").waitFor();
      await tungguTeks(r, "cb-action-primary", /Setujui/);
      await klikPotret(r, r.tid("cb-action-primary"), "kontrabon-setujui");
      await tungguTeks(r, "cb-detail-status", /Disetujui/);
      const d = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0,status:1,approved_by:1,submitted_by:1})`);
      assert(d.status === "approved", `status ${d.status}`);
      await r.shot("kontrabon-disetujui");
      return `${cb.number} → ${d.status} · diajukan ${d.submitted_by || "Manajer"}, disetujui ${d.approved_by || fin.user.name}`;
    });

    await r.step(5, "Finance", `Akuntansi & Pajak › Buku Besar › Jurnal → [[Jurnal Baru]] → '${KET}' · 6-2000 Debit 1.000 · 2-1900 Kredit 1.000 → [[Posting Jurnal]] → buka jurnalnya → [[Balik Jurnal]]`, "Tombol Jurnal Baru tampil (dulu Finance lihat saja); jurnal seimbang terposting; jurnal pembalik terbit (efek bersih nol)", async () => {
      await menu(r, "akuntansi", "ledger");
      await r.tid("gl-view").waitFor();
      await r.tid("gl-new-journal").click();
      await r.tid("je-modal").waitFor();
      await r.tid("je-description").fill(KET);
      await bl.pilih(r, "je-line-account-0", "6-2000", "6-2000");
      await r.tid("je-line-debit-0").fill("1000");
      await bl.pilih(r, "je-line-account-1", "2-1900", "2-1900");
      await r.tid("je-line-credit-1").fill("1000");
      await r.idle(300);
      await r.shot("jurnal-baru", { locator: r.tid("je-modal") });
      await r.tid("je-submit").click();
      await r.tid("je-modal").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "gl-notice", /Jurnal manual/);
      je = mongo(`return db.journal_entries.find({entity_id:"${KSC}",source_type:"manual",description:${JSON.stringify(KET)},status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(je, "jurnal manual tidak ditemukan");
      const d = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0), c = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
      assert(Math.abs(d - c) < 0.01 && d === 1000, `jurnal tidak seimbang ${d}/${c}`);
      await r.tid("gl-journal-search").fill(KET);
      await r.idle(800);
      await r.tid(`gl-journal-row-${je.id}`).click();
      await r.tid("gl-journal-detail").waitFor();
      await klikPotret(r, r.tid("gl-journal-reverse"), "balik-jurnal", { locator: r.tid("gl-journal-detail") });
      await r.tid("gl-reverse-form").waitFor();
      await r.tid("gl-reverse-reason").fill("Uji K-FIN-01 selesai — dibalik");
      await r.tid("gl-reverse-submit").click();
      await r.tid("gl-journal-detail").waitFor({ state: "detached", timeout: 20000 });
      const rev = mongo(`return db.journal_entries.findOne({source_type:"reversal",source_id:"${je.id}",status:{$ne:"void"}},{_id:0,number:1,lines:1})`);
      assert(rev, "jurnal pembalik tidak terbentuk");
      return `${msg} · ${je.number} D/K ${rp(d)} · pembalik ${rev.number}`;
    });

    await r.step(6, "Finance", "Akuntansi & Pajak › Tutup Buku → Bulanan · September 2026 → [[Pratinjau]] → [[Tutup Buku]] → konfirmasi", "Tombol Tutup Buku tampil & berhasil (dulu Manajer); September tertutup (bulan kosong). Admin membukanya kembali sesudah uji", async () => {
      const ada = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
      assert(!ada.some((c) => c.period_key === TUTUP && c.status === "closed"), "September sudah tertutup sebelum uji");
      const isi = mongo(`return db.journal_entries.countDocuments({entity_id:"${KSC}",status:{$ne:"void"},date:{$gte:"${TUTUP}-01",$lte:"${TUTUP}-30T23:59:59"}})`);
      assert(isi === 0, `September berisi ${isi} jurnal — tidak ditutup`);
      await menu(r, "akuntansi", "closing");
      await r.tid("closing-view").waitFor();
      await bl.pilih(r, "closing-period-type", "month");
      await bl.pilih(r, "closing-month", "09");
      await bl.pilih(r, "closing-year", "2026");
      await r.tid("closing-preview-btn").click();
      await r.tid("closing-preview").waitFor({ timeout: 20000 });
      await r.idle(600);
      await klikPotret(r, r.tid("closing-close-btn"), "tutup-buku");
      await r.tid("closing-confirm").waitFor();
      await r.tid("closing-confirm-confirm").click();
      const notice = await tungguTeks(r, "closing-notice", /berhasil ditutup/, 30000);
      const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
      const rec = cl.find((c) => c.period_key === TUTUP && c.status === "closed");
      assert(rec, "catatan tutup buku tidak ada");
      closingId = rec.id;
      await r.shot("september-tertutup");
      return `${notice} · ditutup oleh ${rec.closed_by || fin.user.name}`;
    });

    await r.step(7, "Finance", `SDM › Penggajian › Komponen & Masukan → periode November 2026 → [[Sahkan]] masukan → lalu Proses Gaji → proses susulan November (diajukan Manajer) → [[Sahkan]]`, "Kedua tombol Sahkan tampil (dulu khusus Manajer, K-SDM-01) dan berhasil; proses & masukan uji dibatalkan sesudahnya", async () => {
      await r.go("hr-pay-components");
      await r.tid("payinput-period").waitFor({ timeout: 15000 });
      await pilihLabel(r, "payinput-period", "November 2026");
      await r.tid(`payinput-approve-${inp.id}`).waitFor({ timeout: 15000 });
      await klikPotret(r, r.tid(`payinput-approve-${inp.id}`), "sahkan-masukan");
      await r.tid("confirm-modal-confirm").click();
      await tungguTeks(r, "paycomp-view", /disahkan/);
      const st = mongo(`return db.hr_pay_inputs.findOne({id:"${inp.id}"},{_id:0,status:1})`).status;
      assert(st === "approved", `status masukan ${st}`);
      run = await mgr.post("/hr/payroll/runs", { entity_id: KSC, period: MASA, run_type: "susulan" }, KSC);
      assert(run.totals && run.totals.employees === 1, `proses susulan memuat ${run.totals && run.totals.employees} karyawan`);
      await mgr.post(`/hr/payroll/runs/${run.id}/submit`, {}, KSC);
      await r.go("hr-payroll-runs");
      await r.tid(`payroll-run-${run.id}`).waitFor({ timeout: 15000 });
      await r.tid(`payroll-run-${run.id}`).click();
      await r.tid("payroll-approve").waitFor();
      await klikPotret(r, r.tid("payroll-approve"), "sahkan-proses-gaji");
      const msg = await r.text("confirm-modal-message").catch(() => "");
      await r.tid("confirm-modal-confirm").click();
      await tungguTeks(r, "payroll-notice", /Sahkan berhasil/);
      const pr = mongo(`return db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0,status:1,approved_by:1})`);
      assert(pr.status === "approved", `status proses ${pr.status}`);
      await r.shot("proses-gaji-disahkan");
      return `masukan ${st} · ${run.number} ${pr.status} oleh ${pr.approved_by} · "${msg.slice(0, 120)}"`;
    });

    await r.step(8, "Finance", "Pengaturan › Keuangan & Pajak › kelompok [[Pajak, pembukuan & antar-PT]] → 'LPJ kas kecil wajib berlampiran bukti' (izin Akuntansi Kelola) dan 'Faktur pajak elektronik' (khusus Admin)", "Yang pertama bisa diubah (kotak isian + [[Simpan]], seperti Manajer; dulu terkunci untuk Finance); yang kedua tetap terkunci 'Hanya pemegang akses …' (Manajer pun sama)", async () => {
      await r.go("settings-cfg-finance");
      await r.tid("cfg-group-pajak-pembukuan").click();
      await r.idle(800);
      const kunci = ["finance.lpj_wajib_lampiran", "tax.efaktur_enabled"];
      const out = [];
      for (const key of kunci) {
        const card = r.tid(`cfg-card-${key}`);
        await card.waitFor({ timeout: 20000 });
        await card.scrollIntoViewIfNeeded();
        if (!(await r.tid(`cfg-save-${key}`).count()) && !(await r.tid(`cfg-readonly-${key}`).count()))
          await r.tid(`cfg-card-toggle-${key}`).click();
        await r.idle(400);
        out.push({ key, ubah: await r.tid(`cfg-save-${key}`).count() > 0, kunci: await r.tid(`cfg-readonly-${key}`).count() > 0 });
      }
      assert(out[0].ubah && !out[0].kunci, `${kunci[0]}: ${JSON.stringify(out[0])}`);
      assert(out[1].kunci && !out[1].ubah, `${kunci[1]}: ${JSON.stringify(out[1])}`);
      await r.tid(`cfg-card-${kunci[0]}`).scrollIntoViewIfNeeded();
      await sorot(r.tid(`cfg-save-${kunci[0]}`));
      await r.shot("pengaturan-keuangan", { locator: r.tid(`cfg-card-${kunci[0]}`) });
      await lepas(r.tid(`cfg-save-${kunci[0]}`));
      return out.map((o) => `${o.key}: ${o.ubah ? "bisa diubah" : "terkunci"}`).join(" · ");
    });
  } finally {
    // ── Pembersihan (API): kembalikan data bersama ke keadaan sebelum uji ─────────────────────────────────────────────
    try { if (closingId) { await adm.post(`/finance/closing/${closingId}/reopen`, {}, KSC); r.note(`September dibuka kembali (Admin)`); } }
    catch (e) { r.note(`GAGAL membuka kembali September: ${e.message}`); }
    try {
      if (run) { await mgr.post(`/hr/payroll/runs/${run.id}/cancel`, { reason: `${KET} — dibatalkan sesudah uji` }, KSC); r.note(`Proses ${run.number} dibatalkan`); }
    } catch (e) { r.note(`GAGAL membatalkan proses gaji: ${e.message}`); }
    try { await fin.post(`/hr/payroll/inputs/${inp.id}/cancel`, { reason: `${KET} — dibatalkan sesudah uji` }, KSC); r.note("Masukan gaji uji dibatalkan"); }
    catch (e) { r.note(`GAGAL membatalkan masukan: ${e.message}`); }
    const cek = mongo(`return {tutup:db.period_closings?db.period_closings.countDocuments({entity_id:"${KSC}",period_key:"${TUTUP}",status:"closed"}):null,
      masukan:db.hr_pay_inputs.findOne({id:"${inp.id}"},{_id:0,status:1}).status,
      proses:${run ? `db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0,status:1}).status` : "null"}}`);
    r.note(`Keadaan akhir: ${JSON.stringify(cek)}`);
  }
  await r.finish();
})();
