// V9 · PIUTANG — bukti di LAYAR untuk klaim teks materi F02–F06 yang belum dibuktikan uji lain (bukan langkah materi).
// Tiap langkah = satu klaim (`kode · klaim`), dikerjakan dengan akun peran yang benar lalu dicocokkan dengan buku.
// Klaim dikelompokkan per BLOK; tiap blok memakai dokumen satu peserta SEGAR dan hasilnya ke uji/hasil/V9/piutang-<blok>/.
//
//   KN_BLOK="toleransi:89,umur:86,denda:88,janji:86,tertua:90,kembalikan:88" \
//     node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_klaim_piutang.js
//
// Data: `seed_pelatihan_keuangan_kn.py --mulai 86 --peserta 90`. Blok yang membayar memakai SO pelunasan & bayar sebagian
// peserta (belum dibayar); blok denda memakai rencana cicilan tanpa nota denda. Blok umur & janji tidak mengubah buku.
const { Run, api, assert, kartu, akunPeserta, mongo, rp, sleep } = require("../lib");
const { KSC, bukaMenu, bukaPenagihan, barisSo, sisaSo, pelangganPeserta, titipan, pilih } = require("../piutang_lib");
const k9 = require("./v9lib");

const BLOK = (process.env.KN_BLOK || "toleransi:89,umur:86,denda:88,janji:86,tertua:90,kembalikan:88")
  .split(",").map((x) => x.trim()).filter(Boolean).map((x) => { const [b, n] = x.split(":"); return [b, String(n).padStart(2, "0")]; });
const r2 = (v) => Math.round(Number(v || 0) * 100) / 100;
const idr = (n) => Number(n).toLocaleString("id-ID", { maximumFractionDigits: 2 });

const kwitansiSejak = (custId, sejak) => mongo(`return db.ar_receipts.find({customer_id:"${custId}",status:{$ne:"void"},
  created_at:{$gt:"${sejak}"}},{_id:0}).sort({created_at:1}).toArray()`);
const kini = () => mongo(`return new Date().toISOString()`);
const jurnalSumber = (ids) => mongo(`return db.journal_entries.find({source_id:{$in:${JSON.stringify(ids.filter(Boolean))}},
  status:{$ne:"void"}},{_id:0}).sort({created_at:1}).toArray()`);
const keputusan = (rcId) => mongo(`return db.payment_variance_decisions.find({receipt_id:"${rcId}"},{_id:0}).sort({created_at:1}).toArray()`);
const alokasi = (rc) => (rc.allocations || []).map((x) => `${x.order_number} ${idr(x.applied)}`).join(", ");

function pembantu(r) {
  return {
    async bukaForm(soId) {
      if (await r.tid("ar-receipt-modal").count()) { await r.tid("ar-receipt-cancel").click(); await r.idle(300); }
      await bukaPenagihan(r);
      await barisSo(r, soId);
      await r.tid(`collection-pay-${soId}`).click();
      await r.tid("ar-receipt-modal").waitFor();
      await r.tid(`ar-receipt-alloc-${soId}`).waitFor();
      await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
      await r.idle(700);
    },
    async ketik(testId, teks) {
      const box = r.tid(testId).first();
      await box.click(); await box.press("Control+A"); await box.press("Delete");
      await r.page.keyboard.type(teks, { delay: 12 });
      await sleep(1600);   // penilaian selisih ditunda 450 ms + permintaan API
    },
    async konfirmasiSimpan() {
      await r.tid("ar-receipt-confirm").waitFor();
      await r.tid("ar-receipt-confirm-confirm").click();
      await r.tid("collection-notice").waitFor({ timeout: 20000 });
      await r.idle(600);
      return r.text("collection-notice");
    },
    async putuskanManajer(rcId, kind, note) {
      await r.login("manager");
      await bukaMenu(r, "ar-aging", "payment-plans");
      await r.tid("pp-tab-selisih").click();
      await r.tid(`pv-decide-${rcId}`).waitFor({ timeout: 20000 });
      await r.tid(`pv-decide-${rcId}`).click();
      await r.tid("payment-variance-dialog").waitFor();
      await sleep(600);
      await r.tid(`pv-option-${kind}`).click();
      await r.tid("pv-note").fill(note);
      await r.shot(`manajer-putus-${kind}`);
      await r.tid("pv-submit").click();
      await r.page.waitForFunction(() => !document.querySelector('[data-testid="payment-variance-dialog"]'), null, { timeout: 20000 });
    },
  };
}

// ── Blok TOLERANSI (F03): kurang bayar ≤ toleransi otomatis; > toleransi → keputusan berlabel; hapus sisa wajib Manajer ──
async function blokToleransi(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const h = pembantu(r);
  const k = kartu(NO); const cust = pelangganPeserta(NO);
  const SL = k["a_dasar:so_lunas"]; const SS = k["a_dasar:so_sebagian"];
  for (const so of [SL, SS]) assert(so && Math.abs(sisaSo(so.so_id) - so.total) < 0.01, `${so && so.so} sudah dibayar — pakai peserta segar`);
  r.note(`Peserta ${NO}: ${SL.so} ${SL.total} · ${SS.so} ${SS.total}`);
  await r.login(akunPeserta(NO));
  const kurang = 3000;
  await step({ kode: "F03", bagian: "catatan_pelatih", peran: "Finance",
    klaim: "Selisih di dalam toleransi (bawaan Rp 5.000) diputus otomatis sebagai pembulatan",
    harap: `Bayar ${SL.so} kurang Rp 3.000 → tanpa jendela selisih; SO lunas; keputusan 'Pembulatan' otomatis; jurnal hapus sisa receh 6-9100 (D) / 1-1200 (K) Rp 3.000` },
  async () => {
    await h.bukaForm(SL.so_id);
    const bayar = r2(SL.total - kurang);
    await h.ketik(`ar-receipt-alloc-${SL.so_id}`, idr(bayar));
    const hint = await k9.teks(r, "ar-receipt-variance-hint");
    const sejak = kini();
    await r.tid("ar-receipt-submit").click();
    await sleep(800);
    assert(!(await r.tid("payment-variance-dialog").count()), "jendela selisih muncul padahal selisih ≤ toleransi");
    const msg = await h.konfirmasiSimpan();
    const [rc] = kwitansiSejak(cust.id, sejak);
    assert(rc && Math.abs(rc.amount - bayar) < 0.01, `kwitansi ${rc && rc.amount}`);
    assert(sisaSo(SL.so_id) < 0.01, `sisa SO ${sisaSo(SL.so_id)}`);
    const dec = keputusan(rc.id);
    assert(dec.length === 1 && dec[0].kind === "rounding_writeoff" && dec[0].auto, `keputusan ${JSON.stringify(dec.map((x) => x.kind))}`);
    const je = jurnalSumber([dec[0].id]);
    assert(je.length === 1, `jurnal keputusan ${je.length}`);
    k9.cekJurnal(je[0], [["6-9100", "D", kurang], ["1-1200", "K", kurang]]);
    await r.shot("f03-toleransi-otomatis");
    return `petunjuk: ${hint} · ${msg} · ${dec[0].number} ${dec[0].kind} · ${k9.ringkasJurnal(je[0])}`;
  });

  const gap = 50000;
  let rcWo = null;
  await step({ kode: "F03", bagian: "konsep.1", peran: "Finance",
    klaim: "Selisih di atas toleransi meminta keputusan berlabel: sisa tetap piutang, ubah jadwal, atau hapus sisa (wajib Manajer)",
    harap: "Jendela 'Selisih Pembayaran · Kurang bayar' berisi tiga pilihan; 'Hapus sisa kurang bayar' berlencana WAJIB MANAGER; 'Ubah jadwal' mati bila pesanan belum punya rencana" },
  async () => {
    await h.bukaForm(SS.so_id);
    await h.ketik(`ar-receipt-alloc-${SS.so_id}`, idr(r2(SS.total - gap)));
    await r.tid("ar-receipt-submit").click();
    await r.tid("payment-variance-dialog").waitFor();
    await sleep(600);
    const o = {};
    for (const kd of ["outstanding", "reschedule", "writeoff"]) {
      o[kd] = { ada: await r.tid(`pv-option-${kd}`).count(), mati: await r.tid(`pv-option-${kd}`).isDisabled(),
        t: await k9.teks(r, `pv-option-${kd}`) };
    }
    assert(o.outstanding.ada && !o.outstanding.mati && /DISARANKAN/i.test(o.outstanding.t), `pilihan sisa tetap piutang: ${o.outstanding.t}`);
    assert(o.reschedule.ada && o.reschedule.mati && /belum punya rencana/.test(o.reschedule.t), `pilihan ubah jadwal: ${o.reschedule.t}`);
    assert(o.writeoff.ada && /WAJIB MANAGER/i.test(o.writeoff.t) && /Beban Selisih Pembayaran/.test(o.writeoff.t), `pilihan hapus sisa: ${o.writeoff.t}`);
    await r.shot("f03-jendela-kurang-bayar");
    return Object.entries(o).map(([kd, v]) => `${kd}${v.mati ? " (mati)" : ""}: ${v.t.slice(0, 110)}`).join(" | ");
  });

  await step({ kode: "F03", bagian: "kesalahan_umum.1", peran: "Finance",
    klaim: "'Hapus sisa kurang bayar' membebankan sisa piutang ke beban dan wajib Manajer",
    harap: "Finance memilih Hapus sisa → kwitansi tetap tercatat, keputusan TIDAK dijalankan (perlu penyetuju) dan selisih masuk antrean Selisih Bayar; belum ada jurnal beban; sisa SO tetap Rp 50.000" },
  async () => {
    await r.tid("pv-option-writeoff").click();
    await r.tid("pv-note").fill(`V9 latihan ${NO}: uji hapus sisa oleh Finance`);
    const sejak = kini();
    await r.tid("pv-submit").click();
    const msg = await h.konfirmasiSimpan();
    [rcWo] = kwitansiSejak(cust.id, sejak);
    assert(rcWo, "kwitansi tidak tersimpan");
    const v = rcWo.variance || {};
    assert(v.needs_decision && !v.decision_id && /penyetuju/i.test(v.decision_error || ""), `selisih kwitansi ${JSON.stringify(v).slice(0, 300)}`);
    assert(Math.abs(sisaSo(SS.so_id) - gap) < 0.01, `sisa SO ${sisaSo(SS.so_id)}`);
    assert(!keputusan(rcWo.id).length, "keputusan hapus sisa ikut tersimpan");
    assert(/antrean Selisih Bayar/.test(msg), `pesan: ${msg}`);
    await r.shot("f03-hapus-sisa-finance-antre");
    return `${msg} · sisa ${SS.so} ${rp(sisaSo(SS.so_id))}`;
  });

  await step({ kode: "F03", bagian: "kesalahan_umum.1", peran: "Manajer",
    klaim: "Hapus sisa diputus Manajer: sisa dibebankan ke Beban Selisih Pembayaran, pesanan lunas",
    harap: "Manajer: Piutang › Rencana & Denda › tab Selisih Bayar → [Putuskan] → Hapus sisa → jurnal 6-9100 (D) / 1-1200 (K) Rp 50.000; SO lunas" },
  async () => {
    await h.putuskanManajer(rcWo.id, "writeoff", `V9 latihan ${NO}: sisa disetujui dihapus`);
    const dec = keputusan(rcWo.id);
    assert(dec.length === 1 && dec[0].kind === "writeoff" && dec[0].status === "done", `keputusan ${JSON.stringify(dec.map((x) => [x.kind, x.status]))}`);
    const je = jurnalSumber([dec[0].id]);
    k9.cekJurnal(je[0], [["6-9100", "D", gap], ["1-1200", "K", gap]]);
    assert(sisaSo(SS.so_id) < 0.01, `sisa SO ${sisaSo(SS.so_id)}`);
    return `${dec[0].number} oleh ${dec[0].decided_by} · ${k9.ringkasJurnal(je[0])} · ${SS.so} lunas`;
  });
}

// ── Blok UMUR & JADWAL (F03, F05): kotak cari Saldo & Umur; Finance tanpa Susun Jadwal — tidak mengubah buku ───────────
async function blokUmur(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const k = kartu(NO); const CIC = k["b_piutang:cicilan"]; const SL = k["a_dasar:so_lunas"];
  assert(!mongo(`return db.payment_plans.countDocuments({doc_id:"${SL.so_id}",origin:{$ne:"term"},status:{$ne:"void"}})`),
    `${SL.so} sudah punya rencana bayar`);
  await r.login(akunPeserta(NO));
  await step({ kode: "F03", bagian: "kesalahan_umum.3", peran: "Finance",
    klaim: "Kotak cari Saldo & Umur menerima nama pelanggan atau sales, bukan nomor SO",
    harap: `Cari '${CIC.so}' → 'Tidak ada piutang terbuka.'; cari 'Cicilan ${NO}' → baris pelanggan tampil; petunjuk kotak 'Cari pelanggan / sales...'` },
  async () => {
    await bukaMenu(r, "ar-aging", "ar-aging");
    const ph = await r.tid("ar-aging-search").getAttribute("placeholder");
    await r.tid("ar-aging-search").fill(CIC.so);
    await r.idle(1200);
    const nSo = await r.page.locator('[data-testid^="ar-aging-row-"]').count();
    await r.shot("f03-cari-nomor-so");
    await r.tid("ar-aging-search").fill(`Cicilan ${NO}`);
    await r.tid(`ar-aging-row-${CIC.pelanggan_id}`).waitFor({ timeout: 15000 });
    const nNama = await r.page.locator('[data-testid^="ar-aging-row-"]').count();
    assert(nSo === 0 && nNama >= 1 && /pelanggan/i.test(ph || ""), `nomor SO → ${nSo} baris; nama → ${nNama}; petunjuk '${ph}'`);
    return `petunjuk '${ph}' · cari ${CIC.so} → ${nSo} baris · cari 'Cicilan ${NO}' → ${nNama} baris`;
  });

  async function bukaPanelSo(so) {
    await bukaMenu(r, "sales-orders", "", { grup: "penjualan" });
    await r.tid("orders-search-input").fill(so.so);
    await r.idle(1000);
    await r.tid(`order-card-${so.so_id}`).click();
    await r.idle(800);
    await r.tid("so-open-full-detail").click();
    await r.tid("so-payment-panel").waitFor({ timeout: 20000 });
    await r.idle(1200);
  }
  await step({ kode: "F05", bagian: "kesalahan_umum.0", peran: "Finance",
    klaim: "Rencana baru disusun Admin Penjualan atau Manajer; Finance tidak punya tombol Susun Jadwal",
    harap: `Rincian ${SL.so} (belum berencana) untuk Finance: panel 'Jadwal Pembayaran & Denda' tanpa tombol [Susun Jadwal]; Admin Sales & Manajer melihat tombol itu` },
  async () => {
    await bukaPanelSo(SL);
    const fin = await r.tid("sop-edit").count();
    const kosong = await k9.teks(r, "sop-empty");
    await r.shot("f05-finance-tanpa-susun-jadwal");
    const lain = {};
    for (const akun of ["salesadmin", "manager"]) {
      await r.login(akun);
      await bukaPanelSo(SL);
      lain[akun] = (await r.tid("sop-edit").count()) ? await k9.teks(r, "sop-edit") : "";
      await r.page.keyboard.press("Escape");
    }
    assert(fin === 0 && /Susun Jadwal/.test(lain.manager) && /Susun Jadwal/.test(lain.salesadmin),
      `Finance sop-edit=${fin} · Admin Sales '${lain.salesadmin}' · Manajer '${lain.manager}'`);
    return `Finance: tanpa tombol (${kosong.slice(0, 60)}…) · Admin Sales: [${lain.salesadmin}] · Manajer: [${lain.manager}]`;
  });
}

// ── Blok DENDA (F05): usulan, kartu Rencana aktif, ubah/bebaskan oleh Manajer ───────────────────────────────────────────
async function blokDenda(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const CIC = kartu(NO)["b_piutang:cicilan"];
  assert(CIC && !mongo(`return db.penalties.countDocuments({plan_id:"${CIC.rencana_id}"})`), `${CIC && CIC.rencana} sudah punya nota denda`);
  let pen = null;
  await r.login(akunPeserta(NO));
  await step({ kode: "F05", bagian: "konsep.2", peran: "Finance",
    klaim: "Nota denda lahir sebagai usulan dan belum masuk buku; Finance hanya bisa menerbitkan",
    harap: "[Buat Nota Denda] → nota USULAN tanpa jurnal; di Antrean Denda Finance melihat [Terbitkan] tanpa [Ubah Nominal]/[Bebaskan]" },
  async () => {
    await bukaMenu(r, "ar-aging", "ar-aging");
    await r.tid("ar-aging-search").fill(`Cicilan ${NO}`);
    await r.tid(`ar-aging-row-${CIC.pelanggan_id}`).click();
    await r.tid("ar-aging-detail-modal").waitFor();
    await r.idle(1200);
    await r.tid("ar-aging-accrue").click();
    await r.tid("ar-aging-accrue-notice").waitFor({ timeout: 20000 });
    pen = mongo(`return db.penalties.findOne({plan_id:"${CIC.rencana_id}"},{_id:0})`);
    assert(pen && pen.status === "draft", `nota ${pen && pen.status}`);
    assert(!mongo(`return db.journal_entries.countDocuments({source_id:"${pen.id}"})`), "nota usulan berjurnal");
    await r.page.keyboard.press("Escape");
    await r.idle(400);
    await bukaMenu(r, "ar-aging", "payment-plans");
    await r.tid("pp-tab-denda").click();
    await r.tid("pp-search").fill(pen.number);
    await r.tid(`penalty-row-${pen.id}`).waitFor({ timeout: 15000 });
    await r.idle(600);
    const tombol = { issue: await r.tid(`penalty-issue-${pen.id}`).count(), adjust: await r.tid(`penalty-adjust-${pen.id}`).count(),
      waive: await r.tid(`penalty-waive-${pen.id}`).count() };
    assert(tombol.issue === 1 && !tombol.adjust && !tombol.waive, `tombol Finance ${JSON.stringify(tombol)}`);
    await r.shot("f05-usulan-finance");
    return `${pen.number} ${rp(pen.amount)} usulan, 0 jurnal · tombol Finance ${JSON.stringify(tombol)}`;
  });

  await step({ kode: "F05", bagian: "catatan_pelatih", peran: "Finance",
    klaim: "Saat kotak cari berisi nomor nota, kartu RENCANA AKTIF dan jumlah di tab Jadwal Pembayaran ikut tersaring dan bisa menunjukkan 0",
    harap: "Kartu 'Rencana aktif' TIDAK ikut tersaring (sama dengan saat kotak cari kosong); hanya angka di tab Jadwal Pembayaran yang menjadi 0" },
  async () => {
    const kpiCari = await k9.teks(r, "pp-kpi-plans");
    const tabCari = await k9.teks(r, "pp-tab-jadwal");
    await r.shot("f05-cari-nota-kpi");
    await r.tid("pp-search").fill("");
    await r.idle(1500);
    const kpiKosong = await k9.teks(r, "pp-kpi-plans");
    const tabKosong = await k9.teks(r, "pp-tab-jadwal");
    const n = (s) => Number((String(s).match(/(\d+)\s*$/) || [])[1] || NaN);
    assert(kpiCari === kpiKosong && n(kpiKosong) > 0, `kartu Rencana aktif: dicari '${kpiCari}' · kosong '${kpiKosong}'`);
    assert(n(tabCari) === 0 && n(tabKosong) > 0, `tab Jadwal: dicari '${tabCari}' · kosong '${tabKosong}'`);
    return `dicari ${pen.number}: kartu '${kpiCari}', tab '${tabCari}' · kosong: kartu '${kpiKosong}', tab '${tabKosong}'`;
  });

  await step({ kode: "F05", bagian: "konsep.2", peran: "Manajer",
    klaim: "Selama masih usulan, nominal denda bisa diubah Manajer (tanpa jurnal)",
    harap: "Manajer: [Ubah Nominal] pada nota usulan → nominal baru tersimpan, status tetap usulan, belum ada jurnal" },
  async () => {
    await r.login("manager");
    await bukaMenu(r, "ar-aging", "payment-plans");
    await r.tid("pp-tab-denda").click();
    await r.tid("pp-search").fill(pen.number);
    await r.tid(`penalty-adjust-${pen.id}`).waitFor({ timeout: 15000 });
    await r.tid(`penalty-adjust-${pen.id}`).click();
    await r.tid("penalty-dialog").waitFor();
    const box = r.tid("penalty-dialog-amount");
    await box.click(); await box.press("Control+A"); await box.press("Delete");
    await r.page.keyboard.type("15000", { delay: 12 });
    await r.tid("penalty-dialog-reason").click();
    await r.page.getByRole("option").first().click();
    await r.tid("penalty-dialog-note").fill(`V9 latihan ${NO}: nego denda`);
    await r.shot("f05-manajer-ubah-nominal");
    await r.tid("penalty-dialog-submit").click();
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="penalty-dialog"]'), null, { timeout: 20000 });
    const p = mongo(`return db.penalties.findOne({id:"${pen.id}"},{_id:0})`);
    assert(Math.abs(p.amount - 15000) < 0.01 && ["draft", "adjusted"].includes(p.status), `nota ${p.status} ${p.amount}`);
    assert(!mongo(`return db.journal_entries.countDocuments({source_id:"${pen.id}"})`), "nota usulan berjurnal sesudah diubah");
    pen = p;
    return `${p.number}: ${rp(15000)} · status ${p.status} · jurnal 0`;
  });

  await r.login(akunPeserta(NO));
  await step({ kode: "F05", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "Setelah terbit, Finance tidak bisa mengubah atau membebaskan denda",
    harap: "Finance [Terbitkan] → jurnal 1-1270 (D) / 4-9300 (K) Rp 15.000; pada nota terbit Finance tidak melihat [Ubah Nominal]/[Bebaskan]" },
  async () => {
    await bukaMenu(r, "ar-aging", "payment-plans");
    await r.tid("pp-tab-denda").click();
    await r.tid("pp-search").fill(pen.number);
    await r.tid(`penalty-issue-${pen.id}`).waitFor({ timeout: 15000 });
    await r.tid(`penalty-issue-${pen.id}`).click();
    await r.tid("confirm-modal").waitFor();
    await r.tid("confirm-modal-confirm").click();
    await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="penalty-issue-${id}"]`), pen.id, { timeout: 20000 });
    const p = mongo(`return db.penalties.findOne({id:"${pen.id}"},{_id:0})`);
    const je = mongo(`return db.journal_entries.findOne({id:"${p.je_id}"},{_id:0})`);
    k9.cekJurnal(je, [["1-1270", "D", 15000], ["4-9300", "K", 15000]]);
    await r.tid("pp-filter-issued").click();
    await r.tid(`penalty-row-${pen.id}`).waitFor({ timeout: 15000 });
    const t = { adjust: await r.tid(`penalty-adjust-${pen.id}`).count(), waive: await r.tid(`penalty-waive-${pen.id}`).count() };
    assert(!t.adjust && !t.waive, `tombol Finance pada nota terbit ${JSON.stringify(t)}`);
    await r.shot("f05-terbit-finance");
    pen = p;
    return `${p.number} terbit · ${k9.ringkasJurnal(je)} · tombol ubah/bebaskan Finance: tidak ada`;
  });

  await step({ kode: "F05", bagian: "kesalahan_umum.2", peran: "Manajer",
    klaim: "Membebaskan denda yang sudah terbit butuh Manajer dan jurnal pembalik",
    harap: "Manajer [Bebaskan] → status Dibebaskan; jurnal pembalik 4-9300 (D) / 1-1270 (K) Rp 15.000; jurnal terbit tetap ada" },
  async () => {
    await r.login("manager");
    await bukaMenu(r, "ar-aging", "payment-plans");
    await r.tid("pp-tab-denda").click();
    await r.tid("pp-filter-issued").click();
    await r.tid("pp-search").fill(pen.number);
    await r.tid(`penalty-waive-${pen.id}`).waitFor({ timeout: 15000 });
    await r.tid(`penalty-waive-${pen.id}`).click();
    await r.tid("penalty-dialog").waitFor();
    await r.tid("penalty-dialog-reason").click();
    await r.page.getByRole("option").first().click();
    await r.tid("penalty-dialog-note").fill(`V9 latihan ${NO}: denda dibebaskan`);
    await r.shot("f05-manajer-bebaskan");
    await r.tid("penalty-dialog-submit").click();
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="penalty-dialog"]'), null, { timeout: 20000 });
    const p = mongo(`return db.penalties.findOne({id:"${pen.id}"},{_id:0})`);
    assert(p.status === "waived", `status ${p.status}`);
    const asli = mongo(`return db.journal_entries.findOne({id:"${pen.je_id}"},{_id:0})`);
    const balik = mongo(`return db.journal_entries.findOne({id:"${p.reversal_je_id}"},{_id:0})`);
    assert(asli, "jurnal terbit hilang");
    assert(balik, `jurnal pembalik tidak ada (reversal_je_id '${p.reversal_je_id}')`);
    k9.cekJurnal(balik, [["4-9300", "D", 15000], ["1-1270", "K", 15000]]);
    return `${p.number} ${p.status} · asli ${asli.number} (${asli.status}) · pembalik ${k9.ringkasJurnal(balik)}`;
  });
}

// ── Blok JANJI (F06): janji bayar / tindak lanjut penagihan butuh izin ubah pesanan ─────────────────────────────────────
async function blokJanji(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const CIC = kartu(NO)["b_piutang:cicilan"];
  await r.login(akunPeserta(NO));
  await step({ kode: "F06", bagian: "kesalahan_umum.3", peran: "Finance",
    klaim: "Janji bayar dicatat lewat ikon telepon di Penagihan & Penerimaan — berlaku untuk Finance?",
    harap: "Teks lama SALAH untuk Finance: server menolak tindak lanjut/janji dari Finance (izin ubah pesanan). Sesudah perbaikan ikon telepon & lonceng tidak tampil bagi Finance; ikon Terima pembayaran tetap" },
  async () => {
    await bukaPenagihan(r);
    await barisSo(r, CIC.so_id);
    const ikon = { telepon: await r.tid(`collection-followup-${CIC.so_id}`).count(), lonceng: await r.tid(`collection-mark-${CIC.so_id}`).count(),
      bayar: await r.tid(`collection-pay-${CIC.so_id}`).count() };
    await r.shot("f06-finance-tanpa-ikon-janji");
    const fin = await api(akunPeserta(NO));
    let apiRes = "";
    try {
      await fin.post(`/customers/${CIC.pelanggan_id}/followups`, { customer_id: CIC.pelanggan_id, order_id: CIC.so_id,
        note: "uji izin", outcome: "promised", promise_date: "2026-12-01", promise_amount: 100000 }, KSC);
      apiRes = "server menerima";
    } catch (e) { apiRes = `server ${e.status}: ${String(e.detail || e.message).slice(0, 120)}`; }
    assert(/server 403/.test(apiRes), `janji dari Finance: ${apiRes}`);
    assert(!ikon.telepon && !ikon.lonceng && ikon.bayar, `ikon Finance ${JSON.stringify(ikon)}`);
    return `ikon Finance ${JSON.stringify(ikon)} · simpan janji lewat server: ${apiRes}`;
  });

  await step({ kode: "F06", bagian: "kesalahan_umum.3", peran: "Admin Sales",
    klaim: "Janji bayar dicatat pemegang izin ubah pesanan (Admin Sales) lewat ikon telepon di Penagihan & Penerimaan",
    harap: "Admin Sales: ikon telepon → Hasil 'Dijanjikan bayar' + tanggal + nominal → [Simpan] → pesan 'Tindak lanjut … dicatat.'; tercatat janji bertanggal & bernominal" },
  async () => {
    await r.login("salesadmin");
    try { await bukaPenagihan(r); } catch (_) { await r.go("collection-worklist"); await r.tid("collection-worklist").waitFor(); }
    await barisSo(r, CIC.so_id);
    await r.tid(`collection-followup-${CIC.so_id}`).click();
    await r.tid("worklist-followup-modal").waitFor();
    await r.tid("worklist-followup-note").fill(`V9 latihan ${NO}: pelanggan janji transfer cicilan 1`);
    await pilih(r, "worklist-followup-outcome", "Dijanjikan bayar");
    const besok = mongo(`const d=new Date(Date.now()+7*86400000+7*3600000);return d.toISOString().slice(0,10)`);
    const { pilihTanggal } = require("./vlib");
    await pilihTanggal(r, "worklist-followup-promise-date", besok);
    const box = r.tid("worklist-followup-promise-amount");
    await box.click(); await box.press("Control+A"); await box.press("Delete");
    await r.page.keyboard.type(String(CIC.cicilan_1), { delay: 12 });
    await r.shot("f06-adminsales-janji");
    const sejak = kini();
    await r.tid("worklist-followup-submit").click();
    await r.tid("collection-notice").waitFor({ timeout: 20000 });
    const msg = await r.text("collection-notice");
    const fu = mongo(`return db.collection_followups.find({customer_id:"${CIC.pelanggan_id}",created_at:{$gt:"${sejak}"}},{_id:0}).toArray()`);
    assert(fu.length === 1 && fu[0].outcome === "promised" && fu[0].promise_date === besok && Math.abs(fu[0].promise_amount - CIC.cicilan_1) < 0.01,
      `tindak lanjut ${JSON.stringify(fu.map((x) => [x.outcome, x.promise_date, x.promise_amount]))}`);
    return `${msg} · janji ${rp(fu[0].promise_amount)} · ${fu[0].promise_date} oleh ${fu[0].created_by}`;
  });
}

// ── Blok TERTUA (F02, F04): Tertua dulu ke SO tertua; Tunai → Kas Kecil; kelebihan receh ───────────────────────────────
async function blokTertua(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const h = pembantu(r);
  const k = kartu(NO); const cust = pelangganPeserta(NO);
  // Dua SO terkirim yang belum dibayar: bawaan kartu "SO untuk pelunasan penuh" + "SO untuk bayar sebagian"; peserta yang
  // dokumen dasarnya sudah terpakai memakai SO tambahan `V9_siapkan.py --so 2` → KN_SO_KUNCI="v9:so_1,v9:so_2".
  const [kL, kS] = (process.env.KN_SO_KUNCI || "a_dasar:so_lunas,a_dasar:so_sebagian").split(",");
  const SL = k[kL]; const SS = k[kS];
  for (const so of [SL, SS]) assert(so && Math.abs(sisaSo(so.so_id) - so.total) < 0.01, `${so && so.so} sudah dibayar — pakai peserta segar`);
  r.note(`Peserta ${NO}: ${SL.so} ${SL.total} · ${SS.so} ${SS.total}`);
  await r.login(akunPeserta(NO));
  let rcB = null;
  await step({ kode: "F02", bagian: "kesalahan_umum.0", peran: "Finance",
    klaim: "Dengan Tertua dulu, uang dialokasikan ke SO tertua lebih dulu, bukan ke SO yang dimaksud",
    harap: `Form dibuka dari baris ${SS.so} → [Tertua dulu] → nominal Rp 1.000.000 → kwitansi teralokasi ke ${SL.so} (lebih tua); ${SS.so} tetap utuh` },
  async () => {
    await h.bukaForm(SS.so_id);
    await r.tid("ar-receipt-mode-auto").click();
    await sleep(300);
    await h.ketik("ar-receipt-amount", "1.000.000");
    await pilih(r, "ar-receipt-method", "Tunai");
    await sleep(1200);
    const hintTunai = await k9.teks(r, "ar-receipt-cash-hint");
    const rek = await k9.teks(r, "ar-receipt-payment-fields");
    r.note(`Tunai: ${hintTunai} · ${rek.slice(0, 120)}`);
    await r.shot("f02-tunai-kas-kecil");
    const sejak = kini();
    await r.tid("ar-receipt-submit").click();
    await sleep(800);
    if (await r.tid("payment-variance-dialog").count()) {
      await r.tid("pv-option-outstanding").click();
      await pilih(r, "pv-reason", "Bayar sebagian (disepakati)");
      await r.tid("pv-note").fill(`V9 latihan ${NO}: uji tertua dulu`);
      await r.tid("pv-submit").click();
    }
    const msg = await h.konfirmasiSimpan();
    [rcB] = kwitansiSejak(cust.id, sejak);
    // Tertua dulu: SO tertua (SL) dilunasi lebih dulu; SO yang dibuka (SS) hanya menerima SISA uang sesudah SL lunas.
    const al = rcB.allocations || [];
    const keSL = al.filter((x) => x.order_id === SL.so_id).reduce((s, x) => s + Number(x.applied || 0), 0);
    const keSS = al.filter((x) => x.order_id === SS.so_id).reduce((s, x) => s + Number(x.applied || 0), 0);
    assert(al.length && al[0].order_id === SL.so_id, `alokasi pertama bukan SO tertua: ${alokasi(rcB)}`);
    assert(Math.abs(keSL - 1000000) < 0.01 && keSS < 0.01, `ke ${SL.so} ${keSL} · ke ${SS.so} ${keSS}`);
    await r.shot("f02-tertua-dulu");
    return `${msg} · alokasi ${alokasi(rcB)} · ${SS.so} (yang dibuka) menerima ${rp(keSS)} · sisa ${SL.so} ${rp(sisaSo(SL.so_id))} · ${SS.so} ${rp(sisaSo(SS.so_id))}`;
  });

  await step({ kode: "F02", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "Cara bayar Tunai: uang tercatat masuk Kas Kecil, bukan bank",
    harap: "Kwitansi Tunai (langkah sebelumnya): petunjuk 'Tunai → masuk Kas Kecil'; rekening Kas Toko KSC; jurnal 1-1110 Kas Kecil (D) / 1-1200 Piutang (K), tanpa 1-1100" },
  async () => {
    const kas = mongo(`return db.cash_transactions.findOne({id:"${rcB.cash_txn_id}"},{_id:0})`);
    const rek = mongo(`return db.bank_accounts.findOne({id:"${kas.account_id}"},{_id:0,name:1})`);
    const je = jurnalSumber([rcB.cash_txn_id, rcB.id]);
    assert(je.length >= 1, "jurnal kwitansi tidak ada");
    k9.cekJurnal(je[0], [["1-1110", "D", rcB.amount], ["1-1200", "K", rcB.amount]]);
    assert(!je[0].lines.some((l) => l.account_code === "1-1100"), "jurnal Tunai menyentuh 1-1100 Bank");
    assert(kas.cash_type === "kas_kecil", `jenis kas ${kas.cash_type}`);
    return `${rcB.number} metode ${rcB.method} · kas ${kas.number} ${kas.cash_type} · rekening ${rek && rek.name} · ${k9.ringkasJurnal(je[0])}`;
  });

  let rcLebih = null; let dep0 = 0; let hintLebih = "";
  await step({ kode: "F04", bagian: "kesalahan_umum.1", peran: "Finance",
    klaim: "Tertua dulu saat masih ada tagihan terbuka lain: uang dipakai melunasi tagihan itu lebih dulu, bukan menjadi titipan",
    harap: `[Tertua dulu] nominal = sisa ${SL.so} + sisa ${SS.so} + Rp 3.000 → satu kwitansi melunasi KEDUA SO; yang tersisa hanya Rp 3.000` },
  async () => {
    const nominal = r2(sisaSo(SL.so_id) + sisaSo(SS.so_id) + 3000);
    dep0 = titipan(cust.id);
    await h.bukaForm(SS.so_id);
    await r.tid("ar-receipt-mode-auto").click();
    await sleep(300);
    await h.ketik("ar-receipt-amount", idr(nominal));
    await r.page.waitForFunction(() => /toleransi/.test(document.querySelector('[data-testid="ar-receipt-variance-hint"]')?.innerText || ""),
      null, { timeout: 10000 }).catch(() => {});
    hintLebih = await k9.teks(r, "ar-receipt-variance-hint");
    const sejak = kini();
    await r.tid("ar-receipt-submit").click();
    await sleep(800);
    assert(!(await r.tid("payment-variance-dialog").count()), "jendela selisih muncul untuk lebih bayar Rp 3.000");
    const msg = await h.konfirmasiSimpan();
    [rcLebih] = kwitansiSejak(cust.id, sejak);
    assert(sisaSo(SL.so_id) < 0.01 && sisaSo(SS.so_id) < 0.01, `sisa ${sisaSo(SL.so_id)} / ${sisaSo(SS.so_id)}`);
    assert((rcLebih.allocations || []).length === 2, `alokasi ${alokasi(rcLebih)}`);
    await r.shot("f04-tertua-dulu-dua-so");
    return `${msg} · alokasi ${alokasi(rcLebih)}`;
  });

  await step({ kode: "F04", bagian: "catatan_pelatih", peran: "Finance",
    klaim: "Kelebihan bayar Rp 5.000 atau kurang dianggap pembulatan (toleransi) dan tidak menjadi titipan",
    harap: "Fakta (teks dikoreksi): kelebihan ≤ Rp 5.000 diputus OTOMATIS sebagai pembulatan — tanpa jendela keputusan — lalu MENJADI titipan pelanggan (2-1400 kredit Rp 3.000)" },
  async () => {
    assert(rcLebih, "kwitansi lebih bayar tidak ada");
    const dec = keputusan(rcLebih.id);
    const dep1 = titipan(cust.id);
    const je = jurnalSumber([rcLebih.cash_txn_id, rcLebih.id]);
    k9.cekJurnal(je[0], [["2-1400", "K", 3000]]);
    assert(dec.length === 1 && dec[0].kind === "rounding_deposit" && dec[0].auto, `keputusan ${JSON.stringify(dec.map((x) => x.kind))}`);
    assert(Math.abs(dep1 - dep0 - 3000) < 0.01, `titipan ${dep0} → ${dep1}`);
    return `petunjuk: ${hintLebih} · ${dec[0].number} ${dec[0].kind} (otomatis) · titipan ${rp(dep0)} → ${rp(dep1)} · ${k9.ringkasJurnal(je[0])}`;
  });
}

// ── Blok KEMBALIKAN (F04): pilihan kembalikan ke pelanggan wajib Manajer ───────────────────────────────────────────────
async function blokKembalikan(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const h = pembantu(r);
  const k = kartu(NO); const cust = pelangganPeserta(NO);
  const A = k["a_dasar:so_lunas"]; const B = k["a_dasar:so_sebagian"];
  const lebih = 100000;
  let rc = null; const dep0 = titipan(cust.id);
  await r.login(akunPeserta(NO));
  // Persiapan (bukan klaim): pelanggan harus tinggal punya SATU SO terbuka supaya lebih bayar tidak terserap tagihan lain.
  const terbuka = [A, B].filter((so) => sisaSo(so.so_id) > 0.01);
  assert(terbuka.length >= 1, `peserta ${NO}: tidak ada SO terbuka`);
  if (terbuka.length === 2) {
    await h.bukaForm(B.so_id);
    await r.tid("ar-receipt-submit").click();
    await h.konfirmasiSimpan();
    assert(sisaSo(B.so_id) < 0.01, `persiapan: ${B.so} belum lunas`);
    r.note(`Persiapan: ${B.so} dilunasi persis (Atur sendiri) supaya pelanggan hanya punya ${A.so} terbuka`);
  }
  const SL = [A, B].find((so) => sisaSo(so.so_id) > 0.01);
  const sisaSL = sisaSo(SL.so_id);
  r.note(`Satu-satunya SO terbuka: ${SL.so} sisa ${rp(sisaSL)}`);
  await step({ kode: "F04", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "'Kembalikan ke pelanggan' wajib Manajer; Finance memilih deposit atau alokasi",
    harap: `Lebih bayar ${rp(lebih)} → pilihan 'Kembalikan ke pelanggan (kas keluar)' berlencana WAJIB MANAGER; Finance memilihnya → kwitansi tersimpan, keputusan tidak dijalankan (perlu penyetuju), selisih masuk antrean` },
  async () => {
    await h.bukaForm(SL.so_id);
    await r.tid("ar-receipt-mode-auto").click();
    await sleep(300);
    await h.ketik("ar-receipt-amount", idr(r2(sisaSL + lebih)));
    await r.tid("ar-receipt-submit").click();
    await r.tid("payment-variance-dialog").waitFor();
    await sleep(600);
    const sentence = await k9.teks(r, "pv-sentence");
    const t = await k9.teks(r, "pv-option-refund");
    assert(/Lebih/.test(sentence) && /WAJIB MANAGER/i.test(t), `jendela: ${sentence} · pilihan kembalikan: ${t}`);
    await r.tid("pv-option-refund").click();
    await sleep(1200);
    await r.tid("pv-note").fill(`V9 latihan ${NO}: uji kembalikan oleh Finance`);
    await r.shot("f04-kembalikan-finance");
    const sejak = kini();
    await r.tid("pv-submit").click();
    const msg = await h.konfirmasiSimpan();
    [rc] = kwitansiSejak(cust.id, sejak);
    const v = rc.variance || {};
    assert(v.needs_decision && !v.decision_id && /penyetuju/i.test(v.decision_error || ""), `selisih ${JSON.stringify(v).slice(0, 300)}`);
    assert(!keputusan(rc.id).length, "keputusan kembalikan ikut tersimpan");
    return `${sentence} · pilihan: ${t.slice(0, 90)} · ${msg}`;
  });

  await step({ kode: "F04", bagian: "kesalahan_umum.2", peran: "Manajer",
    klaim: "Kelebihan yang menunggu diputus Manajer (di sini: disimpan sebagai deposit)",
    harap: `Manajer: Selisih Bayar → [Putuskan] → Simpan sebagai deposit → titipan pelanggan +${rp(lebih)}; antrean bersih` },
  async () => {
    await h.putuskanManajer(rc.id, "deposit", `V9 latihan ${NO}: jadi titipan`);
    const dec = keputusan(rc.id);
    assert(dec.length === 1 && dec[0].kind === "deposit" && dec[0].status === "done", `keputusan ${JSON.stringify(dec.map((x) => x.kind))}`);
    assert(Math.abs(titipan(cust.id) - dep0 - lebih) < 0.01, `titipan ${dep0} → ${titipan(cust.id)}`);
    return `${dec[0].number} ${dec[0].kind} oleh ${dec[0].decided_by} · titipan ${rp(dep0)} → ${rp(titipan(cust.id))}`;
  });
}

const JALAN = { toleransi: blokToleransi, umur: blokUmur, denda: blokDenda, janji: blokJanji, tertua: blokTertua, kembalikan: blokKembalikan };
const JUDUL = { toleransi: "toleransi & hapus sisa (F03)", umur: "Saldo & Umur, Susun Jadwal (F03, F05)", denda: "nota denda (F05)",
  janji: "janji bayar (F06)", tertua: "Tertua dulu, Tunai, kelebihan receh (F02, F04)", kembalikan: "kembalikan ke pelanggan (F04)" };

(async () => {
  let semua = true;
  for (const [blok, no] of BLOK) {
    const fn = JALAN[blok];
    if (!fn) { console.log(`blok tidak dikenal: ${blok}`); semua = false; continue; }
    k9.bersihkan(`piutang-${blok}`);
    const d = k9.daftar(`piutang-${blok}`);
    const r = await new Run(d.kode, `V9 · Bukti klaim materi Piutang — ${JUDUL[blok]} · peserta ${no}`).start();
    try { await fn(r, d, no); } catch (e) { r.note("berhenti: " + e.message); }
    d.simpan();
    semua = (await r.finish()) && semua;
  }
  process.exitCode = semua ? 0 : 1;
})();
