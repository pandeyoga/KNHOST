// V9 · KAS & BANK — bukti di LAYAR untuk klaim teks materi F07–F10 yang belum dibuktikan uji lain (bukan langkah materi).
// Tiap langkah = satu klaim (`kode · klaim`), dikerjakan dengan akun peran yang benar lalu dicocokkan dengan buku.
//
//   KN_PESERTA=87 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_klaim_kas.js
//
// Data peserta SEGAR (`seed_pelatihan_keuangan_kn.py`): PD kas kecil disetujui (belum cair), setoran titipan sales menunggu,
// kwitansi transfer (kas BCA belum tercocok). Hasil → uji/hasil/V9/kas/.
const { Run, assert, kartu, peserta, akunPeserta, rp, sleep, mongo } = require("../lib");
const kb = require("../kasbank_lib");
const k9 = require("./v9lib");

const NO = peserta("87");
const LPJ = [
  { desc: "Sewa mobil & bensin kunjungan 3 kota", cat: "transportasi", akun: "6-4600", amount: 400000 },
  { desc: "Cetak katalog & materai", cat: "fotocopy_printing_jilid_materai", akun: "6-4300", amount: 150000 },
];
const PAKAI = LPJ.reduce((s, l) => s + l.amount, 0);   // 550.000 > PD 500.000 → kekurangan dana Rp 50.000

(async () => {
  k9.bersihkan("kas");
  const d = k9.daftar("kas");
  const r = await new Run(d.kode, `V9 · Bukti klaim materi Kas & Bank (F07–F10) · peserta ${NO}`).start();
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const K = kartu(NO);
  const pd = K["c_kas:pd_kas_kecil"]; const tt = K["c_kas:titipan_sales"]; const kt = K["c_kas:kwitansi_transfer"];
  const toast = (re) => kb.tunggu(r, "pc-toast", re);
  const bukaPd = async () => {
    if (await r.tid("pc-detail-modal").count()) { await r.tid("pc-detail-modal-close-x").click(); await r.idle(300); }
    await kb.menu(r, "petty-cash");
    await r.tid("pc-search").fill(pd.pd);
    await r.tid(`pc-row-${pd.pd_id}`).waitFor();
    // [Buka] — atau, bila baris berisi tombol [Bayar] (hutang reimburse terbuka), klik barisnya (sama dengan peserta).
    if (await r.tid(`pc-open-${pd.pd_id}`).count()) await r.tid(`pc-open-${pd.pd_id}`).click();
    else await r.tid(`pc-row-${pd.pd_id}`).click();
    await r.tid("ca-detail").waitFor();
    await r.idle(500);
  };
  let stl = null;
  const muatStl = () => mongo(`return db.cash_advance_settlements.find({cash_advance_id:"${pd.pd_id}"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);

  try {
    assert(pd && tt && kt, `Kartu peserta ${NO} belum lengkap (c_kas)`);
    const ca0 = mongo(`return db.cash_advances.findOne({id:"${pd.pd_id}"},{_id:0,status:1})`);
    assert(ca0.status === "approved", `PD ${pd.pd} sudah ${ca0.status} — pakai peserta segar`);
    r.note(`Peserta ${NO} · ${pd.pd} ${rp(pd.nominal)} · setoran ${tt.setoran} ${rp(tt.nominal)} · kwitansi transfer ${kt.kwitansi} ${kt.kas} ${rp(kt.nominal)}`);

    // ── F07: pencairan → Tanda Terima ───────────────────────────────────────────────────────────────────────────────
    await r.login(akunPeserta(NO));
    await step({ kode: "F07", bagian: "catatan_pelatih", peran: "Finance",
      klaim: "Sesudah pencairan, tombol [Tanda Terima] mencetak bukti serah uang ke karyawan",
      harap: "PD dicairkan (Kas Toko KSC) → tombol [Tanda Terima] tampil di rincian PD dan membuka cetakan 'Tanda Terima' bernominal PD" },
    async () => {
      await bukaPd();
      assert(!(await r.tid("ca-print-tt").count()), "Tanda Terima sudah tampil sebelum dicairkan");
      await r.tid("ca-disburse-btn").click();
      await r.tid("ca-disburse-modal").waitFor();
      await r.tid("ca-disburse-account-sole").waitFor();
      await r.tid("ca-disburse-confirm").click();
      await kb.konfirmasi(r, "ca-disburse-money-confirm");
      await toast(/dicairkan/);
      await r.tid("ca-print-tt").waitFor({ timeout: 15000 });
      const [popup] = await Promise.all([r.ctx.waitForEvent("page", { timeout: 15000 }).catch(() => null), r.tid("ca-print-tt").click()]);
      let isi = "";
      if (popup) { await popup.waitForLoadState().catch(() => {}); await sleep(800); isi = (await popup.locator("body").innerText()).replace(/\s+/g, " "); await popup.close(); }
      assert(/TANDA TERIMA/i.test(isi) && isi.includes(pd.pd), `cetakan Tanda Terima: ${isi.slice(0, 200) || "(tidak terbuka)"}`);
      await r.shot("f07-tanda-terima");
      return `tombol [Tanda Terima] tampil sesudah cair · cetakan: ${isi.slice(0, 160)}`;
    });

    // ── F07: LPJ Draf — Manajer tidak bisa menyetujui; bukti hanya bisa diunggah selama Draf ──────────────────────────
    await step({ kode: "F07", bagian: "kesalahan_umum.2", peran: "Finance",
      klaim: "LPJ yang belum [Ajukan] tetap Draf; bukti hanya bisa diunggah selama Draf",
      harap: `[Simpan LPJ] (2 nota, total ${rp(PAKAI)}) → status Draf, tombol [Ajukan] & [Unggah Bukti] tampil` },
    async () => {
      await r.tid("pc-settle-btn").click();
      await r.tid("stl-form").waitFor();
      for (let i = 0; i < LPJ.length; i++) {
        if (i > 0) await r.tid("stl-add-line").click();
        await r.tid(`stl-line-desc-${i}`).fill(LPJ[i].desc);
        await kb.pilih(r, `stl-line-cat-${i}`, LPJ[i].cat);
        await r.tid(`stl-line-amount-${i}`).fill(String(LPJ[i].amount));
      }
      await r.tid("stl-divisi").fill("Penjualan");
      await sleep(300);
      await r.tid("stl-submit").click();
      await r.tid("stl-form").waitFor({ state: "hidden" });
      await r.tid("stl-detail").waitFor();
      stl = muatStl();
      const s = await kb.teks(r, "stl-detail-status");
      const tombol = { ajukan: await r.tid("stl-submit-btn").count(), unggah: await r.tid("stl-attach-btn").count(),
        setujui: await r.tid("stl-approve-btn").count() };
      assert(s === "Draf" && tombol.ajukan && tombol.unggah && !tombol.setujui, `status ${s} · ${JSON.stringify(tombol)}`);
      await r.shot("f07-lpj-draf");
      return `${stl.number} ${s} · total ${rp(stl.total_pengeluaran)} · tombol ${JSON.stringify(tombol)}`;
    });

    await step({ kode: "F07", bagian: "kesalahan_umum.2", peran: "Manajer",
      klaim: "LPJ yang masih Draf tidak bisa disetujui Manajer",
      harap: "Manajer membuka PD yang LPJ-nya Draf: tidak ada [Setujui & Posting GL] maupun [Tolak]" },
    async () => {
      await r.login("manager");
      await bukaPd();
      await r.tid("stl-detail").waitFor();
      const s = await kb.teks(r, "stl-detail-status");
      const t = { setujui: await r.tid("stl-approve-btn").count(), tolak: await r.tid("stl-reject-btn").count() };
      assert(s === "Draf" && !t.setujui && !t.tolak, `status ${s} · ${JSON.stringify(t)}`);
      await r.shot("f07-manajer-lpj-draf");
      return `Manajer melihat ${stl.number} ${s} · tombol ${JSON.stringify(t)}`;
    });

    await r.login(akunPeserta(NO));
    await step({ kode: "F07", bagian: "catatan_pelatih", peran: "Finance",
      klaim: "Finance tidak bisa menyetujui LPJ; sesudah diajukan bukti tidak bisa diunggah lagi",
      harap: "Finance [Ajukan] → status Diajukan; Finance tidak melihat [Setujui & Posting GL]/[Tolak]; tombol [Unggah Bukti] hilang" },
    async () => {
      await bukaPd();
      await r.tid("stl-submit-btn").click();
      await toast(`${stl.number} diajukan`);
      await r.idle(400);
      const s = await kb.teks(r, "stl-detail-status");
      const t = { setujui: await r.tid("stl-approve-btn").count(), tolak: await r.tid("stl-reject-btn").count(),
        unggah: await r.tid("stl-attach-btn").count() };
      assert(s === "Diajukan" && !t.setujui && !t.tolak && !t.unggah, `status ${s} · ${JSON.stringify(t)}`);
      await r.shot("f07-finance-lpj-diajukan");
      return `${stl.number} ${s} · tombol Finance ${JSON.stringify(t)}`;
    });

    // ── F07: LPJ ditolak → Perbaiki & Ajukan Lagi ──────────────────────────────────────────────────────────────────
    await step({ kode: "F07", bagian: "catatan_pelatih", peran: "Manajer",
      klaim: "Manajer bisa menolak LPJ dengan alasan",
      harap: "Manajer [Tolak] → isi alasan → status Ditolak; alasan tampil di rincian; belum ada jurnal" },
    async () => {
      await r.login("manager");
      await bukaPd();
      await r.tid("stl-reject-btn").click();
      await r.tid("stl-reject-modal").waitFor();
      await r.tid("stl-reject-modal-reason").fill("Nota sewa mobil belum dilampirkan");
      await r.tid("stl-reject-modal-confirm").click();
      await toast(`${stl.number} ditolak`);
      await r.idle(400);
      const s = await kb.teks(r, "stl-detail-status");
      const why = await kb.teks(r, "stl-rejected-reason");
      assert(/Ditolak/.test(s) && /belum dilampirkan/.test(why), `status ${s} · ${why}`);
      assert(!kb.jurnal("petty_cash_settlement", stl.id).length, "LPJ ditolak berjurnal");
      return `${stl.number} ${s} · ${why}`;
    });

    await r.login(akunPeserta(NO));
    await step({ kode: "F07", bagian: "catatan_pelatih", peran: "Finance",
      klaim: "Bila LPJ ditolak Manajer, pembuat LPJ klik [Perbaiki & Ajukan Lagi]",
      harap: "Finance (pembuat LPJ) melihat [Perbaiki & Ajukan Lagi] → form terbuka dengan pesan penolakan → [Simpan & Ajukan Lagi] → status Diajukan" },
    async () => {
      await bukaPd();
      await r.tid("stl-reopen-btn").waitFor({ timeout: 15000 });
      await r.shot("f07-perbaiki-ajukan-lagi");
      await r.tid("stl-reopen-btn").click();
      await r.tid("stl-form").waitFor();
      const label = await kb.teks(r, "stl-submit");
      const tolak = (await r.tid("stl-form-rejected").count()) ? await kb.teks(r, "stl-form-rejected") : "";
      await r.tid("stl-submit").click();
      await r.tid("stl-form").waitFor({ state: "hidden" });
      await r.idle(800);
      stl = muatStl();
      assert(stl.status === "submitted" && /Ajukan Lagi/.test(label), `status ${stl.status} · tombol '${label}'`);
      return `form: '${tolak.slice(0, 100)}' · tombol [${label}] → ${stl.number} ${stl.status}`;
    });

    // ── F07: biaya > uang muka → 2-1650 + Bayar Reimburse ───────────────────────────────────────────────────────────
    await step({ kode: "F07", bagian: "cek_buku.4", peran: "Manajer",
      klaim: "Bila biaya lebih besar dari uang muka: LPJ mencatat 2-1650 Hutang Reimburse Karyawan (K)",
      harap: `Manajer [Setujui & Posting GL] → jurnal beban (D) ${rp(PAKAI)} = 1-1400 Uang Muka (K) ${rp(pd.nominal)} + 2-1650 Hutang Reimburse (K) ${rp(PAKAI - pd.nominal)}` },
    async () => {
      await r.login("manager");
      await bukaPd();
      await r.tid("stl-approve-btn").click();
      await kb.konfirmasi(r, "stl-approve-confirm");
      await toast(`${stl.number} disetujui`);
      const je = kb.seimbang(kb.jurnal("petty_cash_settlement", stl.id), "jurnal LPJ");
      for (const l of LPJ) assert(kb.adaBaris(je, l.akun, "D", l.amount), `beban ${l.akun}: ${kb.teksJurnal(je)}`);
      assert(kb.adaBaris(je, "1-1400", "K", pd.nominal) && kb.adaBaris(je, "2-1650", "K", PAKAI - pd.nominal), kb.teksJurnal(je));
      return kb.teksJurnal(je);
    });

    await r.login(akunPeserta(NO));
    await step({ kode: "F07", bagian: "cek_buku.4", peran: "Finance",
      klaim: "Kelebihan pengeluaran memunculkan tombol [Bayar Reimburse]",
      harap: `Finance: daftar Kas Kecil berisi [Bayar]; rincian: bilah 'Kelebihan pengeluaran ${rp(PAKAI - pd.nominal)} harus dibayar ke …' + [Bayar Reimburse] → kas keluar; jurnal 2-1650 (D) / Kas-Bank (K) ${rp(PAKAI - pd.nominal)}` },
    async () => {
      await kb.menu(r, "petty-cash");
      await r.tid("pc-search").fill(pd.pd);
      await r.tid(`pc-row-${pd.pd_id}`).waitFor();
      await r.idle(400);
      const daftar = (await r.tid(`pc-pay-${pd.pd_id}`).count()) ? await kb.teks(r, `pc-pay-${pd.pd_id}`) : "";
      await r.shot("f07-daftar-bayar");
      await bukaPd();
      const bar = await kb.teks(r, "stl-reimburse-bar");
      const btn = await kb.teks(r, "stl-pay-reimburse-btn");
      assert(/Bayar Reimburse/.test(btn) && bar.includes(rp(PAKAI - pd.nominal)), `bilah: ${bar} · tombol ${btn}`);
      await r.shot("f07-bayar-reimburse");
      await r.tid("stl-pay-reimburse-btn").click();
      await r.tid("stl-reimburse-modal").waitFor();
      await r.tid("stl-reimburse-modal-account-sole").waitFor();
      await r.tid("stl-reimburse-modal-submit").click();
      await kb.konfirmasi(r, "stl-reimburse-confirm");
      await r.tid("stl-reimburse-paid").waitFor({ timeout: 20000 });
      const s = muatStl();
      const kas = kb.kas(s.hutang_reimburse.cash_txn_id);
      const je = kb.seimbang(kb.jurnal("cash_transaction", kas.id), "jurnal reimburse");
      const kasAkun = je.lines.find((l) => Number(l.credit) > 0);
      assert(kb.adaBaris(je, "2-1650", "D", PAKAI - pd.nominal) && kasAkun && /^1-11/.test(kasAkun.account_code)
        && Math.abs(Number(kasAkun.credit) - (PAKAI - pd.nominal)) < 0.01, kb.teksJurnal(je));
      await r.tid("pc-detail-modal-close-x").click().catch(() => {});
      await r.idle(300);
      assert(/Bayar/.test(daftar), `tombol di daftar Kas Kecil: '${daftar}'`);
      return `daftar: [${daftar}] · rincian: ${bar} · [${btn}] → ${kas.number} · ${kb.teksJurnal(je)}`;
    });

    // ── F08: setoran ditolak — titipan tetap atas nama sales ────────────────────────────────────────────────────────
    await step({ kode: "F08", bagian: "konsep.3", peran: "Finance",
      klaim: "Bila uangnya kurang, setoran ditolak ([Tolak] + alasan) dan titipan tetap tercatat atas nama sales",
      harap: `Titipan Sales › Setoran menunggu: [Tolak] ${tt.setoran} + alasan → status Ditolak; titipan ${tt.titipan} tetap 'Dipegang'; tidak ada kas masuk & jurnal` },
    async () => {
      const kas0 = mongo(`return db.cash_transactions.countDocuments({ref_id:"${tt.setoran_id}"})`);
      if (await r.tid("pc-detail-modal").count()) { await r.tid("pc-detail-modal-close-x").click(); await r.idle(300); }
      await kb.menu(r, "cash-holdings");
      await r.tid(`cth-reject-${tt.setoran_id}`).waitFor({ timeout: 15000 });
      await r.tid(`cth-reject-${tt.setoran_id}`).click();
      await r.tid("cth-reject-confirm").waitFor();
      await r.tid("cth-reject-confirm-reason").fill(`Uang dihitung kurang Rp 50.000 — Latihan ${NO}`);
      await r.shot("f08-tolak-setoran");
      await r.tid("cth-reject-confirm-confirm").click();
      await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="cth-receive-${id}"]`), tt.setoran_id, { timeout: 20000 });
      const dep = mongo(`return db.cash_deposits.findOne({id:"${tt.setoran_id}"},{_id:0,allocations:0})`);
      const hold = mongo(`return db.cash_holdings.findOne({id:"${tt.titipan_id}"},{_id:0,status:1,amount:1})`);
      const kas1 = mongo(`return db.cash_transactions.countDocuments({ref_id:"${tt.setoran_id}"})`);
      const jur = mongo(`return db.journal_entries.countDocuments({source_id:"${tt.setoran_id}"})`);
      assert(dep.status === "ditolak" && kas1 === kas0 && !jur, `setoran ${JSON.stringify(dep).slice(0, 300)} · kas ${kas0}→${kas1} · jurnal ${jur}`);
      assert(hold && hold.status === "dipegang", `titipan ${JSON.stringify(hold)}`);
      const alasan = Object.entries(dep).filter(([kk]) => /reason|alasan|note/i.test(kk)).map(([kk, v]) => `${kk}: ${v}`).join("; ");
      return `setoran ${tt.setoran} ${dep.status} (${alasan}) · titipan ${tt.titipan} ${hold.status} ${rp(hold.amount)} · kas & jurnal: tidak ada`;
    });

    // ── F09: kotak cari Jurnal menemukan nomor KSC/CASH-… (kolom Sumber) ────────────────────────────────────────────
    await step({ kode: "F09", bagian: "catatan_pelatih", peran: "Finance",
      klaim: "Kotak cari Jurnal mencari nomor jurnal dan keterangan, bukan nomor KSC/CASH di kolom Sumber",
      harap: `Fakta (teks dikoreksi): ketik ${kt.kas} di kotak cari Jurnal → jurnal kwitansi transfer ${kt.kwitansi} ditemukan (pencarian kini membaca nomor sumber)` },
    async () => {
      const je = kb.seimbang(kb.jurnal("cash_transaction", kt.kas_id), "jurnal kas kwitansi");
      await kb.menuJurnal(r);
      await r.tid("gl-journal-search").fill(kt.kas);
      const row = r.tid(`gl-journal-row-${je.id}`);
      await row.waitFor({ timeout: 20000 });
      const t = await kb.isi(row);
      const n = await r.page.locator('[data-testid^="gl-journal-row-"]').count();
      await kb.shotSorot(r, "f09-cari-nomor-kas", row);
      return `cari '${kt.kas}' → ${n} jurnal · ${t.slice(0, 160)}`;
    });

    // ── F10: [Lepas] membatalkan pencocokan; [Abaikan] tidak membukukan biaya ─────────────────────────────────────────
    const tgl = kb.hariIni();
    const bca = await kb.rekening(akunPeserta(NO), "BCA Operasional KSC");
    const ADM = 15000;
    const TEKS = ["Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo",
      `${tgl.bca},TRSF E-BANKING CR V9 LATIHAN ${NO} TOKO KAIN PESERTA ${NO},0000,"${kb.nominalBca(kt.nominal)}",CR,0`,
      `${tgl.bca},BIAYA ADM V9 LATIHAN ${NO},0000,"${kb.nominalBca(ADM)}",DB,0`].join("\n");
    const baris = () => {
      const rows = mongo(`return db.bank_statement_lines.find({bank_account_id:"${bca.id}",description:{$regex:"V9 LATIHAN ${NO}( |$)"}},
        {_id:0,id:1,description:1,status:1,allocations:1}).toArray()`);
      return { cr: rows.find((x) => /^TRSF/.test(x.description)), adm: rows.find((x) => /^BIAYA ADM/.test(x.description)) };
    };
    await step({ kode: "F10", bagian: "kesalahan_umum.3", peran: "Finance",
      klaim: "Salah pencocokan dibatalkan dengan [Lepas]",
      harap: `Impor 2 baris → [Cocokkan] mutasi CR ke ${kt.kas} → Tercocok, kas 'Terekonsiliasi' → [Lepas] → baris kembali 'Perlu keputusan', kas kembali belum terekonsiliasi; tanpa jurnal` },
    async () => {
      await kb.menu(r, "bank-reconciliation");
      await kb.pilih(r, "recon-account-select", bca.id);
      await r.tid("recon-summary").waitFor();
      await r.tid("recon-import-toggle").click();
      await r.tid("recon-import-panel").waitFor();
      const fmts = await (await require("../lib").api(akunPeserta(NO))).get("/bank-reconciliation/formats", kb.KSC);
      const fBca = fmts.find((f) => f.bank_code === "bca" && (f.file_kind || "csv") === "csv");
      await kb.pilih(r, "recon-format-select", fBca.id);
      await r.tid("recon-raw").fill(TEKS);
      await r.tid("recon-preview-btn").click();
      await kb.tunggu(r, "recon-preview", /Terbaca 2 baris/);
      await r.tid("recon-import-submit").click();
      await kb.tunggu(r, "recon-notice", /2 baris baru/);
      const b = baris();
      await r.tid("recon-lines-search").fill(`V9 LATIHAN ${NO}`);
      await r.idle(400);
      const jeAwal = mongo(`return db.journal_entries.countDocuments({created_at:{$gt:"${new Date(Date.now() - 1000).toISOString()}"}})`);
      await r.tid(`recon-matchbtn-${b.cr.id}`).click();
      await r.tid("recon-match-modal").waitFor();
      await r.tid(`recon-cand-${kt.kas_id}`).waitFor({ timeout: 15000 });
      await r.tid(`recon-pick-cand-${kt.kas_id}`).click();
      await kb.tunggu(r, "recon-notice", /Mutasi ditautkan/);
      await r.tid("recon-match-modal").waitFor({ state: "detached" });
      await kb.tunggu(r, `recon-status-${b.cr.id}`, /^Tercocok$/);
      const kasCocok = kb.kas(kt.kas_id);
      assert(Number(kasCocok.reconciled_amount || 0) > 0, `kas belum terekonsiliasi: ${kasCocok.reconciled_amount}`);
      await kb.shotSorot(r, "f10-sebelum-lepas", r.tid(`recon-unmatch-${b.cr.id}`), { locator: r.tid("recon-lines-table") });
      await r.tid(`recon-unmatch-${b.cr.id}`).click();
      await kb.tunggu(r, "recon-notice", /Tautan dilepas/);
      await kb.tunggu(r, `recon-status-${b.cr.id}`, /Perlu keputusan/);
      const kasLepas = kb.kas(kt.kas_id);
      const line = baris().cr;
      assert(line.status === "unmatched" && !(line.allocations || []).length, `baris ${JSON.stringify(line)}`);
      assert(!Number(kasLepas.reconciled_amount || 0), `kas masih terekonsiliasi ${kasLepas.reconciled_amount}`);
      return `${line.description}: Tercocok ke ${kt.kas} → [Lepas] → ${line.status}; kas terekonsiliasi ${rp(kasCocok.reconciled_amount)} → ${rp(kasLepas.reconciled_amount || 0)}`;
    });

    await step({ kode: "F10", bagian: "kesalahan_umum.3", peran: "Finance",
      klaim: "[Abaikan] pada baris biaya admin tidak membukukan beban bank (pakai [Catat biaya bank])",
      harap: "[Abaikan] baris BIAYA ADM → status Diabaikan, tanpa transaksi kas & jurnal beban; [Batal abaikan] mengembalikannya ke antrean" },
    async () => {
      const b = baris();
      const n0 = mongo(`return db.cash_transactions.countDocuments({account_id:"${bca.id}",description:{$regex:"V9 LATIHAN ${NO}"}})`);
      await r.tid(`recon-ignore-${b.adm.id}`).click();
      const dlg = r.tid("recon-ignore-confirm");
      if (await dlg.count()) {
        if (await r.tid("recon-ignore-confirm-reason").count()) await r.tid("recon-ignore-confirm-reason").fill("uji V9");
        await r.tid("recon-ignore-confirm-confirm").click();
      }
      await kb.tunggu(r, `recon-status-${b.adm.id}`, /Diabaikan/);
      const st = baris().adm.status;
      const n1 = mongo(`return db.cash_transactions.countDocuments({account_id:"${bca.id}",description:{$regex:"V9 LATIHAN ${NO}"}})`);
      const jur = mongo(`return db.journal_entries.countDocuments({description:{$regex:"BIAYA ADM V9 LATIHAN ${NO}"}})`);
      assert(st === "ignored" && n1 === n0 && !jur, `status ${st} · kas ${n0}→${n1} · jurnal ${jur}`);
      await r.shot("f10-diabaikan", { locator: r.tid("recon-lines-table") });
      await r.tid(`recon-unignore-${b.adm.id}`).click();
      await kb.tunggu(r, `recon-status-${b.adm.id}`, /Perlu keputusan/);
      return `BIAYA ADM ${rp(ADM)}: [Abaikan] → ${st}, kas baru 0, jurnal 0 · [Batal abaikan] → ${baris().adm.status}`;
    });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  d.simpan();
  await r.finish();
})();
