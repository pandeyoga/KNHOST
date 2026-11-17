// F03 — Pembayaran sebagian (40 %) untuk SO `a_dasar:so_sebagian`, lalu baca Saldo & Umur pelanggan.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F03_bayar_sebagian.js           (peserta bawaan 02)
//   KN_PESERTA=21 node docs/pelatihan/2026-11-18_keuangan/uji/F03_bayar_sebagian.js
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("./lib");
const { KSC, bukaPenagihan, barisSo, sisaSo, kwitansiTerakhir, jurnalKwitansi, cekJurnalSeimbang,
  pelangganPeserta, pilih, sorot, lepas, klikSorot } = require("./piutang_lib");
const { bersihkanHasil } = require("./piutang_lib");

const NO = peserta("02");
const PERSEN = 0.4;

(async () => {
  bersihkanHasil("F03");
  const r = await new Run("F03", "Pembayaran sebagian & umur piutang").start();
  const k = kartu(NO);
  const so = k["a_dasar:so_sebagian"];
  const cust = pelangganPeserta(NO);
  let rc = null;
  try {
    assert(so && so.so_id && cust, `Kartu peserta ${NO} belum lengkap — jalankan seed_pelatihan_keuangan_kn.py`);
    const sisaAwal = sisaSo(so.so_id);
    assert(Math.abs(sisaAwal - so.total) < 0.01, `${so.so} sudah pernah dibayar (sisa ${sisaAwal}) — pakai peserta segar`);
    const bayar = Math.round(so.total * PERSEN);          // uang yang benar-benar ditransfer: rupiah bulat
    const sisaHarap = Math.round((sisaAwal - bayar) * 100) / 100;
    r.note(`Peserta ${NO} · ${so.so} · total ${so.total} · bayar 40% = ${bayar} · sisa harus ${sisaHarap}`);

    await r.step(1, "Finance", "Masuk → Keuangan › Piutang › tab Penagihan & Penerimaan, cari baris SO kedua",
      `Baris ${so.so}: Belum Lunas ${rp(sisaAwal)}`, async () => {
        await r.login(akunPeserta(NO));
        await bukaPenagihan(r);
        const t = (await (await barisSo(r, so.so_id)).innerText()).replace(/\s+/g, " ");
        assert(t.includes(rp(sisaAwal).replace("Rp ", "")), `baris: ${t}`);
        return t;
      });

    await r.step(2, "Finance", `Klik ikon dompet [Terima pembayaran]; ganti angka di kotak alokasi SO menjadi ${bayar} (40 %), isi No. referensi`,
      "Petunjuk kuning: 'Kurang bayar Rp … dari sisa tagihan pesanan tujuan, belum jatuh tempo (Rp …) — akan diminta keputusan saat disimpan'",
      async () => {
        await sorot(r.tid(`collection-row-${so.so_id}`));
        await klikSorot(r, r.tid(`collection-pay-${so.so_id}`), "penagihan-baris-so");
        await lepas(r.tid(`collection-row-${so.so_id}`));
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid(`ar-receipt-alloc-${so.so_id}`).waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await r.tid(`ar-receipt-alloc-${so.so_id}`).fill(String(bayar));
        await r.tid("ar-receipt-reference").fill(`TRF-LATIH${NO}-F03`);
        await r.page.waitForFunction(() => /Kurang bayar/i.test(
          (document.querySelector('[data-testid="ar-receipt-variance-hint"]') || {}).innerText || ""), null, { timeout: 10000 });
        const tot = await r.text("ar-receipt-total");
        assert(tot === rp(bayar), `Total diterima ${tot} ≠ ${rp(bayar)}`);
        const hint = await r.text("ar-receipt-variance-hint");
        assert(/belum jatuh tempo/.test(hint), `petunjuk: ${hint}`);
        await sorot(r.tid(`ar-receipt-alloc-${so.so_id}`));
        await sorot(r.tid("ar-receipt-variance-hint"));
        await r.shot("form-bayar-sebagian");
        await lepas(r.tid(`ar-receipt-alloc-${so.so_id}`));
        await lepas(r.tid("ar-receipt-variance-hint"));
        return hint;
      });

    await r.step(3, "Finance", "Klik [Simpan kwitansi] → jendela 'Selisih Pembayaran · Kurang bayar' → pilih 'Sisa tetap jadi piutang', alasan 'Bayar sebagian (disepakati)', isi catatan",
      "Kalimat 'Dibayar Rp …, seharusnya Rp … Kurang Rp … — mau bagaimana?'; 'Sisa tetap jadi piutang' DISARANKAN", async () => {
        await r.tid("ar-receipt-submit").click();
        await r.tid("payment-variance-dialog").waitFor();
        const kal = await r.text("pv-sentence");
        assert(kal.includes(rp(bayar)) && /Kurang/.test(kal), `kalimat: ${kal}`);
        await r.tid("pv-option-outstanding").click();
        const sel = await r.tid("pv-option-outstanding").getAttribute("data-selected");
        assert(sel === "1", "pilihan 'Sisa tetap jadi piutang' tidak terpilih");
        await pilih(r, "pv-reason", "Bayar sebagian (disepakati)");
        await r.tid("pv-note").fill("Pelanggan bayar 40% dulu, sisanya bulan depan");
        await sorot(r.tid("pv-option-outstanding"));
        await sorot(r.tid("pv-reason"));
        await klikSorot(r, r.tid("pv-submit"), "dialog-selisih-kurang");
        await lepas(r.tid("pv-option-outstanding"));
        return kal;
      });

    await r.step(4, "Finance", "Konfirmasi [Ya, simpan]",
      "Pesan 'Kwitansi … dicatat … Selisih diputus: Bayar sebagian (disepakati) (SLB-…)'; baris SO tetap ada dengan sisa baru", async () => {
        await r.tid("ar-receipt-confirm").waitFor();
        await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), "konfirmasi-simpan");
        await r.tid("collection-notice").waitFor({ timeout: 20000 });
        const note = await r.text("collection-notice");
        assert(/Kwitansi .*AR-\d+/.test(note) && /Selisih diputus/.test(note), `pesan: ${note}`);
        await r.idle(800);
        rc = kwitansiTerakhir(so.so_id);
        assert(rc && Math.abs(rc.amount - bayar) < 0.01, `kwitansi ${rc && rc.amount} ≠ ${bayar}`);
        const row = await barisSo(r, so.so_id);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(rp(sisaHarap).replace("Rp ", "")), `baris SO sesudah bayar: ${t}`);
        await sorot(row);
        await r.shot("penagihan-sisa-baru");
        await lepas(row);
        return `${note} · baris: ${t}`;
      });

    await r.step(5, "Finance", "Cek buku: kwitansi, sisa SO, jurnal, keputusan selisih",
      `Sisa ${so.so} = ${rp(sisaHarap)} · status bayar Sebagian · jurnal Kas/Bank (D) = Piutang (K) = ${rp(bayar)}`, async () => {
        const s = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,payment_status:1})`);
        assert(Math.abs(sisaSo(so.so_id) - sisaHarap) < 0.01, `sisa ${sisaSo(so.so_id)} ≠ ${sisaHarap}`);
        assert(s.payment_status === "partial", `payment_status ${s.payment_status}`);
        const v = mongo(`return db.ar_receipts.findOne({id:"${rc.id}"},{_id:0,variance:1}).variance`);
        assert(v && v.decision_kind === "outstanding" && v.decision_status === "done",
          `keputusan selisih: ${JSON.stringify(v && { kind: v.decision_kind, st: v.decision_status, err: v.decision_error })}`);
        const je = jurnalKwitansi(rc);
        cekJurnalSeimbang(je, [["1-1100", "D", bayar], ["1-1200", "K", bayar]]);
        return `${rc.number} · ${je.number} · keputusan ${v.decision_number}`;
      });

    await r.step(6, "Finance", "Klik tab Saldo & Umur → cari 'Latihan NN'",
      `Baris pelanggan: Belum Lunas ${rp(sisaHarap)}, kolom 'Belum jatuh tempo' terisi, status kredit 'Sehat'`, async () => {
        await klikSorot(r, r.tid("hub-tab-ar-aging"), "tab-saldo-umur");
        await r.tid("ar-aging-search").waitFor({ timeout: 15000 });
        await r.tid("ar-aging-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
        const row = r.tid(`ar-aging-row-${cust.id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(600);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(rp(sisaHarap).replace("Rp ", "")), `baris umur piutang: ${t}`);
        await klikSorot(r, row, "saldo-umur-pelanggan");
        const fin = await api(akunPeserta(NO));
        const ag = await fin.get(`/ar/aging/${cust.id}`, KSC);
        r.note("detail aging: " + JSON.stringify(ag).slice(0, 200));
        return t;
      });

    await r.step(7, "Finance", "(Baris diklik) → rincian piutang per pesanan",
      `Rincian: ${so.so} Terbayar ${rp(bayar)}, Belum Lunas ${rp(sisaHarap)}, umur 'Belum Jatuh Tempo'; Jadwal Tagihan menunjukkan sisa`, async () => {
        await r.tid("ar-aging-detail-modal").waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await r.tid("ar-aging-detail-modal").innerText()).replace(/\s+/g, " ");
        assert(t.includes(so.so) && t.includes(rp(sisaHarap).replace("Rp ", "")), `rincian: ${t.slice(0, 400)}`);
        await r.shot("saldo-umur-rincian");
        return t.slice(0, 300);
      });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  await r.finish();
})();
