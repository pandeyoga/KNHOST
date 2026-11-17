// F04 — Lebih bayar → titipan (deposit) pelanggan → dipakai melunasi tagihan berikutnya.
// Urutan: sesudah F02 (so_lunas lunas) & F03 (so_sebagian dibayar sebagian). Bila belum, prasyaratnya dijalankan lewat
// API dengan akun peserta (supaya berkas bisa diulang pada peserta segar). Langkah 7 = susulan PELATIH:
//   cd backend && python -m scripts.latih_keuangan.b_piutang --berikut NN
//   node docs/pelatihan/2026-11-18_keuangan/uji/F04_lebih_bayar_titipan.js           (peserta bawaan 02)
//   KN_PESERTA=21 KN_PY=/jalur/venv/bin/python node …/F04_lebih_bayar_titipan.js
const path = require("path");
const { execFileSync } = require("child_process");
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("./lib");
const { KSC, bukaPenagihan, barisSo, sisaSo, kwitansiTerakhir, jurnalKwitansi, cekJurnalSeimbang, pelangganPeserta,
  titipan, sorot, lepas, klikSorot } = require("./piutang_lib");
const { bersihkanHasil } = require("./piutang_lib");

const NO = peserta("02");
const BACKEND = path.resolve(__dirname, "../../../../backend");

/** Prasyarat F02/F03 lewat API (akun peserta) bila peserta segar. */
async function prasyarat(k, cust) {
  const fin = await api(akunPeserta(NO));
  const lunas = k["a_dasar:so_lunas"];
  const s1 = sisaSo(lunas.so_id);
  if (s1 > 0.01) {
    await fin.post("/ar-receipts", { customer_id: cust.id, amount: s1, method: "transfer", entity_id: KSC,
      reference_no: `TRF-LATIH${NO}-F02`, allocations: [{ order_id: lunas.so_id, amount: s1 }] }, KSC);
  }
  const seb = k["a_dasar:so_sebagian"];
  if (Math.abs(sisaSo(seb.so_id) - seb.total) < 0.01) {
    const bayar = Math.round(seb.total * 0.4);
    await fin.post("/ar-receipts", { customer_id: cust.id, amount: bayar, method: "transfer", entity_id: KSC,
      reference_no: `TRF-LATIH${NO}-F03`, allocations: [{ order_id: seb.so_id, amount: bayar }],
      variance: { kind: "outstanding", reason_code: "partial_payment_agreed", note: "prasyarat F04" } }, KSC);
  }
}

(async () => {
  bersihkanHasil("F04");
  const r = await new Run("F04", "Lebih bayar → titipan pelanggan → dipakai").start();
  let k = kartu(NO);
  const so = k["a_dasar:so_sebagian"];
  const cust = pelangganPeserta(NO);
  let rc = null;
  let berikut = null;
  try {
    assert(so && cust, `Kartu peserta ${NO} belum lengkap`);
    assert(titipan(cust.id) < 0.01, `pelanggan peserta ${NO} sudah punya titipan — pakai peserta segar`);
    assert(!k["b_piutang:so_berikut"], `peserta ${NO} sudah punya so_berikut — pakai peserta segar`);
    await prasyarat(k, cust);
    const sisa = sisaSo(so.so_id);
    assert(sisa > 0.01, `${so.so} sudah lunas — pakai peserta segar`);
    const terbuka = (await (await api(akunPeserta(NO))).get(`/ar-receipts/open-orders?customer_id=${cust.id}`, KSC));
    assert(terbuka.length === 1 && terbuka[0].order_id === so.so_id,
      `pelanggan harus hanya punya ${so.so} terbuka (ada: ${terbuka.map((o) => o.number).join(", ")})`);
    const transfer = Math.ceil((sisa + 1) / 500000) * 500000;      // pelanggan mentransfer angka bulat di atas sisa
    const lebih = Math.round((transfer - sisa) * 100) / 100;
    r.note(`Peserta ${NO} · ${so.so} sisa ${sisa} · transfer ${transfer} · lebih ${lebih}`);

    await r.step(1, "Finance", "Penagihan & Penerimaan → ikon dompet [Terima pembayaran] pada SO kedua → pilih [Tertua dulu]",
      `Form terbuka; 'Nominal diterima' bisa diisi (awal = sisa ${rp(sisa)})`, async () => {
        await r.login(akunPeserta(NO));
        await bukaPenagihan(r);
        await barisSo(r, so.so_id);
        await sorot(r.tid(`collection-row-${so.so_id}`));
        await klikSorot(r, r.tid(`collection-pay-${so.so_id}`), "penagihan-baris-so");
        await lepas(r.tid(`collection-row-${so.so_id}`));
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid(`ar-receipt-alloc-${so.so_id}`).waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await klikSorot(r, r.tid("ar-receipt-mode-auto"), "form-pilih-tertua-dulu");
        await r.tid("ar-receipt-amount").waitFor();
        return await r.tid("ar-receipt-amount").inputValue();
      });

    await r.step(2, "Finance", `Isi *Nominal diterima* ${transfer} (sesuai mutasi bank) + No. referensi, klik [Simpan kwitansi]`,
      `Petunjuk kuning 'Lebih bayar ${rp(lebih)} dari sisa tagihan pesanan tujuan (${rp(sisa)})'`, async () => {
        await r.tid("ar-receipt-amount").fill(String(transfer));
        await r.tid("ar-receipt-reference").fill(`TRF-LATIH${NO}-F04`);
        await r.page.waitForFunction(() => /Lebih bayar/i.test(
          (document.querySelector('[data-testid="ar-receipt-variance-hint"]') || {}).innerText || ""), null, { timeout: 10000 });
        const hint = await r.text("ar-receipt-variance-hint");
        assert(hint.includes(rp(lebih).replace("Rp ", "")), `petunjuk: ${hint}`);
        await sorot(r.tid("ar-receipt-amount"));
        await sorot(r.tid("ar-receipt-variance-hint"));
        await klikSorot(r, r.tid("ar-receipt-submit"), "form-lebih-bayar");
        await lepas(r.tid("ar-receipt-variance-hint"));
        return hint;
      });

    await r.step(3, "Finance", "Jendela 'Selisih Pembayaran · Lebih bayar' → pilih 'Simpan sebagai deposit pelanggan', alasan 'Pelanggan transfer berlebih' → [Lanjutkan & simpan kwitansi]",
      `Kalimat 'Dibayar ${rp(transfer)}, seharusnya ${rp(sisa)} … Lebih ${rp(lebih)}'`, async () => {
        await r.tid("payment-variance-dialog").waitFor();
        const kal = await r.text("pv-sentence");
        assert(/Lebih/.test(kal) && kal.includes(rp(transfer)), `kalimat: ${kal}`);
        await r.tid("pv-option-deposit").click();
        assert(await r.tid("pv-option-deposit").getAttribute("data-selected") === "1", "pilihan deposit tidak terpilih");
        const alasan = await r.tid("pv-reason").innerText();
        assert(/transfer berlebih/i.test(alasan), `alasan bawaan: ${alasan}`);
        await sorot(r.tid("pv-option-deposit"));
        await sorot(r.tid("pv-reason"));
        await klikSorot(r, r.tid("pv-submit"), "dialog-selisih-lebih");
        return kal;
      });

    await r.step(4, "Finance", "Konfirmasi [Ya, simpan]",
      `Pesan 'Kwitansi … (${rp(transfer)}) … ${rp(sisa)} melunasi tagihan, ${rp(lebih)} menjadi titipan pelanggan. Selisih diputus: Pelanggan transfer berlebih (SLB-…)'; baris SO hilang`, async () => {
        await r.tid("ar-receipt-confirm").waitFor();
        const msg = await r.text("ar-receipt-confirm-message");
        assert(msg.includes(rp(transfer)), `konfirmasi: ${msg}`);
        await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), "konfirmasi-simpan");
        await r.tid("collection-notice").waitFor({ timeout: 20000 });
        const note = await r.text("collection-notice");
        assert(/Kwitansi .*AR-\d+/.test(note) && /Selisih diputus/.test(note) && note.includes(rp(transfer))
          && note.includes(`${rp(lebih)} menjadi titipan pelanggan`), `pesan: ${note}`);
        await r.idle(800);
        assert(await r.tid(`collection-row-${so.so_id}`).count() === 0, "baris SO masih tampil");
        await sorot(r.tid("collection-notice"));
        await r.page.evaluate(() => window.scrollTo(0, 0));
        await r.shot("kwitansi-lebih-bayar");
        await lepas(r.tid("collection-notice"));
        return note;
      });

    await r.step(5, "Finance", "Cek buku: SO lunas, titipan pelanggan, jurnal kwitansi",
      `Titipan pelanggan ${rp(lebih)} · jurnal: Kas Besar/Bank (D) ${rp(transfer)} = Piutang Usaha (K) ${rp(sisa)} + Uang Muka Pelanggan (K) ${rp(lebih)}`,
      async () => {
        rc = kwitansiTerakhir(so.so_id);
        assert(rc && Math.abs(rc.amount - transfer) < 0.01 && Math.abs(rc.unapplied_amount - lebih) < 0.01,
          `kwitansi ${JSON.stringify(rc && { a: rc.amount, u: rc.unapplied_amount })}`);
        assert(rc.variance && rc.variance.decision_kind === "deposit" && rc.variance.decision_status === "done",
          `keputusan ${JSON.stringify(rc.variance)}`);
        assert(sisaSo(so.so_id) <= 0.01, "SO belum lunas");
        assert(Math.abs(titipan(cust.id) - lebih) < 0.01, `titipan ${titipan(cust.id)} ≠ ${lebih}`);
        const je = jurnalKwitansi(rc);
        cekJurnalSeimbang(je, [["1-1100", "D", transfer], ["1-1200", "K", sisa], ["2-1400", "K", lebih]]);
        return `${rc.number} · ${je.number}: ${je.lines.map((l) => `${l.account_code} D${l.debit} K${l.credit}`).join(" · ")}`;
      });

    await r.step(6, "Finance", "Klik tab Titipan & Saldo Kredit → cari 'Latihan NN'",
      `Baris pelanggan: kolom Deposit ${rp(lebih)}, Jumlah ${rp(lebih)}`, async () => {
        await r.page.evaluate(() => window.scrollTo(0, 0));
        await klikSorot(r, r.tid("hub-tab-customer-credit"), "tab-titipan");
        await r.tid("cc-search").waitFor({ timeout: 15000 });
        await r.tid("cc-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
        const row = r.tid(`cc-row-${cust.id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(rp(lebih).replace("Rp ", "")), `baris titipan: ${t}`);
        await sorot(r.tid(`cc-deposit-${cust.id}`));
        await r.shot("titipan-pelanggan");
        await lepas(r.tid(`cc-deposit-${cust.id}`));
        return t;
      });

    await r.step(7, "Pelatih", "Susulan: tagihan berikutnya pelanggan (python -m scripts.latih_keuangan.b_piutang --berikut NN)",
      "Pesanan baru terkirim (belum dibayar) muncul di Penagihan & Penerimaan", async () => {
        const py = process.env.KN_PY || "python3";
        const out = execFileSync(py, ["-m", "scripts.latih_keuangan.b_piutang", "--berikut", String(Number(NO))],
          { cwd: BACKEND, env: process.env, timeout: 300000 }).toString();
        k = kartu(NO);
        berikut = k["b_piutang:so_berikut"];
        assert(berikut && berikut.so_id, `so_berikut tidak tercatat: ${out}`);
        return `${berikut.so} · ${rp(berikut.total)}`;
      });

    await r.step(8, "Finance", "Tab Penagihan & Penerimaan → [Terima pembayaran] SO baru → centang 'Pakai titipan' → [Simpan kwitansi]",
      `'Nominal diterima' = ${"total − titipan"}; Total diterima = total SO (uang + titipan); 'Nominal sesuai tagihan'`, async () => {
        await bukaPenagihan(r);
        await barisSo(r, berikut.so_id);
        await sorot(r.tid(`collection-row-${berikut.so_id}`));
        await klikSorot(r, r.tid(`collection-pay-${berikut.so_id}`), "penagihan-so-berikut");
        await lepas(r.tid(`collection-row-${berikut.so_id}`));
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid("ar-receipt-deposit-box").waitFor();
        const box = await r.text("ar-receipt-deposit-box");
        assert(box.includes(rp(lebih).replace("Rp ", "")), `kotak titipan: ${box}`);
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await sorot(r.tid("ar-receipt-deposit-box"));
        await r.tid("ar-receipt-use-deposit").check();
        await r.tid("ar-receipt-reference").fill(`TRF-LATIH${NO}-F04B`);
        await r.idle(1200);
        const uang = Math.round((berikut.total - lebih) * 100) / 100;
        const nominal = await r.text("ar-receipt-amount-manual");
        assert(nominal === rp(uang), `Nominal diterima ${nominal} ≠ ${rp(uang)}`);
        const tot = (await r.tid("ar-receipt-total").locator("..").innerText()).replace(/\s+/g, " ");
        assert(tot.includes(rp(berikut.total).replace("Rp ", "")) && /titipan/.test(tot), `total: ${tot}`);
        const hint = await r.text("ar-receipt-variance-hint");
        assert(/tidak ada selisih/i.test(hint), `selisih: ${hint}`);
        await sorot(r.tid("ar-receipt-amount-manual"));
        await klikSorot(r, r.tid("ar-receipt-submit"), "form-pakai-titipan");
        return `${nominal} · ${tot}`;
      });

    await r.step(9, "Finance", "Konfirmasi [Ya, simpan]; cek buku",
      "SO baru lunas, titipan Rp 0; jurnal: Kas/Bank (D) uang baru + Uang Muka Pelanggan (D) titipan = Piutang (K) total SO",
      async () => {
        await r.tid("ar-receipt-confirm").waitFor();
        const msg = await r.text("ar-receipt-confirm-message");
        assert(msg.includes(rp(berikut.total)), `konfirmasi: ${msg}`);
        await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), "konfirmasi-pakai-titipan");
        await r.tid("collection-notice").waitFor({ timeout: 20000 });
        const note = await r.text("collection-notice");
        await r.idle(800);
        await r.page.evaluate(() => window.scrollTo(0, 0));
        await r.shot("kwitansi-pakai-titipan");
        const rc2 = kwitansiTerakhir(berikut.so_id);
        const uang = Math.round((berikut.total - lebih) * 100) / 100;
        assert(rc2 && Math.abs(rc2.amount - uang) < 0.01 && Math.abs(rc2.used_deposit - lebih) < 0.01,
          `kwitansi ${JSON.stringify(rc2 && { a: rc2.amount, d: rc2.used_deposit })}`);
        assert(sisaSo(berikut.so_id) <= 0.01, "SO baru belum lunas");
        assert(titipan(cust.id) < 0.01, `titipan tersisa ${titipan(cust.id)}`);
        const je = jurnalKwitansi(rc2);
        cekJurnalSeimbang(je, [["1-1100", "D", uang], ["2-1400", "D", lebih], ["1-1200", "K", berikut.total]]);
        return `${note} · ${je.number}: ${je.lines.map((l) => `${l.account_code} D${l.debit} K${l.credit}`).join(" · ")}`;
      });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  await r.finish();
})();
