// F02 — Terima pelunasan penuh (transfer bank) untuk SO `a_dasar:so_lunas` peserta.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F02_pelunasan_penuh.js          (peserta bawaan 02)
//   KN_PESERTA=21 node docs/pelatihan/2026-11-18_keuangan/uji/F02_pelunasan_penuh.js
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("./lib");
const { bukaPenagihan, barisSo, kwitansiTerakhir, jurnalKwitansi, sisaSo, cekJurnalSeimbang, sorot, lepas,
  klikSorot } = require("./piutang_lib");
const { bersihkanHasil } = require("./piutang_lib");

const NO = peserta("02");

(async () => {
  bersihkanHasil("F02");
  const r = await new Run("F02", "Terima pelunasan penuh — transfer bank").start();
  const k = kartu(NO);
  const so = k["a_dasar:so_lunas"];
  let rc = null;
  try {
    assert(so && so.so_id, `Kartu peserta ${NO} belum punya a_dasar:so_lunas — jalankan seed_pelatihan_keuangan_kn.py`);
    const sisaAwal = sisaSo(so.so_id);
    r.note(`Peserta ${NO} · ${so.so} · total ${so.total} · sisa ${sisaAwal}`);
    if (sisaAwal <= 0.01) throw new Error(`${so.so} sudah lunas — pakai peserta segar (KN_PESERTA=2x)`);

    await r.step(1, "Finance", "Masuk dengan akun peserta → Perlu Tindakan · kartu 'Uang masuk perlu dicatat'",
      "Kartu 'Uang masuk perlu dicatat' tampil di Perlu Tindakan", async () => {
        await r.login(akunPeserta(NO));
        const kartuUang = r.page.getByText("Uang masuk perlu dicatat").first();
        await kartuUang.waitFor();
        await r.shot("meja-finance");
        return r.who;
      });

    await r.step(2, "Finance", "Keuangan › Piutang › tab Penagihan & Penerimaan — cari baris SO",
      `Baris ${so.so}: Belum Lunas ${rp(sisaAwal)}, jatuh tempo ±30 hari lagi`, async () => {
        await bukaPenagihan(r, "menu-piutang");
        const row = await barisSo(r, so.so_id);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(so.so), `baris tidak memuat ${so.so}: ${t}`);
        assert(t.includes(rp(sisaAwal).replace("Rp ", "")), `nominal ${rp(sisaAwal)} tidak tampil: ${t}`);
        return t;
      });

    await r.step(3, "Finance", "Klik ikon dompet [Terima pembayaran] pada baris SO",
      "Form 'Terima pembayaran' terbuka: alokasi 'Atur sendiri' terisi sisa SO, rekening BCA Operasional KSC terkunci", async () => {
        await sorot(r.tid(`collection-row-${so.so_id}`));
        await klikSorot(r, r.tid(`collection-pay-${so.so_id}`), "penagihan-baris-so");
        await lepas(r.tid(`collection-row-${so.so_id}`));
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid(`ar-receipt-alloc-${so.so_id}`).waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await r.idle(900);
        const alloc = Number(await r.tid(`ar-receipt-alloc-${so.so_id}`).inputValue());
        assert(Math.abs(alloc - sisaAwal) < 0.01, `alokasi terisi ${alloc}, harus ${sisaAwal}`);
        const rek = await r.text("ar-receipt-account-field");
        assert(/BCA Operasional KSC/.test(rek), `rekening penerima bukan BCA Operasional KSC: ${rek}`);
        const tot = await r.text("ar-receipt-total");
        assert(tot === rp(sisaAwal), `Total diterima ${tot} ≠ ${rp(sisaAwal)}`);
        await r.shot("form-terima-pembayaran");
        return `alokasi ${alloc} · ${rek}`;
      });

    await r.step(4, "Finance", "Ketik nominal sesuai mutasi bank (rupiah bulat) di kotak alokasi SO, isi No. referensi, klik [Simpan kwitansi]",
      "Kotak alokasi tetap = sisa tagihan persis (tidak bisa melebihi); 'Nominal sesuai tagihan — tidak ada selisih'", async () => {
        const bulat = String(Math.round(sisaAwal));
        await r.tid(`ar-receipt-alloc-${so.so_id}`).fill(bulat);
        await r.tid("ar-receipt-reference").fill(`TRF-LATIH${NO}-F02`);
        await r.idle(1200);
        const alloc = Number(await r.tid(`ar-receipt-alloc-${so.so_id}`).inputValue());
        assert(Math.abs(alloc - sisaAwal) < 0.01, `alokasi berubah jadi ${alloc}`);
        const hint = await r.text("ar-receipt-variance-hint");
        assert(/tidak ada selisih/i.test(hint), `petunjuk selisih: ${hint}`);
        await sorot(r.tid("ar-receipt-reference"));
        await sorot(r.tid(`ar-receipt-alloc-${so.so_id}`));
        await klikSorot(r, r.tid("ar-receipt-submit"), "form-nominal-referensi");
        await lepas(r.tid("ar-receipt-reference"));
        await lepas(r.tid(`ar-receipt-alloc-${so.so_id}`));
        return `ketik ${bulat} → tersimpan ${alloc} · ${hint}`;
      });

    await r.step(5, "Finance", "Periksa kalimat konfirmasi → klik [Ya, simpan]",
      "Konfirmasi 'Catat penerimaan Rp … dari Latihan NN … ke BCA Operasional KSC … untuk Sukacita?'; lalu pesan hijau 'Kwitansi KSC/AR-… (Rp …) dicatat …' dan baris SO hilang",
      async () => {
        const c = r.tid("ar-receipt-confirm");
        await c.waitFor();
        const msg = await r.text("ar-receipt-confirm-message");
        assert(msg.includes(rp(sisaAwal)) && /BCA Operasional KSC/.test(msg) && /Sukacita/.test(msg), `konfirmasi: ${msg}`);
        await klikSorot(r, r.tid("ar-receipt-confirm-confirm"), "konfirmasi-simpan");
        await r.tid("collection-notice").waitFor({ timeout: 20000 });
        const note = await r.text("collection-notice");
        assert(/Kwitansi .*AR-\d+/.test(note), `pesan: ${note}`);
        await r.idle(800);
        assert(await r.tid(`collection-row-${so.so_id}`).count() === 0, "baris SO masih tampil di daftar penagihan");
        rc = kwitansiTerakhir(so.so_id);
        assert(rc, "kwitansi tidak ditemukan di DB");
        assert(Math.abs(rc.amount - sisaAwal) < 0.01, `nominal kwitansi ${rc.amount} ≠ ${sisaAwal}`);
        await sorot(r.tid("collection-notice"));
        await r.page.evaluate(() => window.scrollTo(0, 0));
        await r.shot("kwitansi-tercatat");
        await lepas(r.tid("collection-notice"));
        return `${msg} → ${note}`;
      });

    await r.step(6, "Finance", "Cek buku: SO lunas, piutang 0",
      `${so.so}: status bayar Lunas, sisa Rp 0`, async () => {
        const s = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,payment_status:1,paid_total:1,grand_total:1})`);
        assert(s.payment_status === "paid", `payment_status = ${s.payment_status}`);
        assert(sisaSo(so.so_id) <= 0.01, `sisa SO ${sisaSo(so.so_id)}`);
        const fin = await api(akunPeserta(NO));
        const det = await fin.get(`/ar-receipts/${rc.id}`, "ent_ksc");
        assert(det.allocations.length === 1 && det.allocations[0].order_id === so.so_id, "alokasi kwitansi salah");
        assert(Number(det.unapplied_amount || 0) < 0.01, `ada sisa tak teralokasi ${det.unapplied_amount}`);
        return `${det.number} · status bayar ${s.payment_status}`;
      });

    await r.step(7, "Finance", "Di Riwayat Pembayaran (AR) cari nomor kwitansi, klik label [Jurnal Terbit]",
      "Jurnal terbuka: 1-1100 Kas Besar / Bank (Debit) dan 1-1200 Piutang Usaha (Kredit) sama besar = nominal kwitansi", async () => {
        await r.tid("ar-history-search").fill(rc.number);
        await r.tid(`ar-history-row-${rc.id}`).waitFor();
        await r.idle(600);
        const row = (await r.tid(`ar-history-row-${rc.id}`).innerText()).replace(/\s+/g, " ");
        assert(row.includes(so.so) && row.includes(rp(sisaAwal).replace("Rp ", "")), `baris riwayat: ${row}`);
        await klikSorot(r, r.tid(`ar-history-journal-${rc.id}`), "riwayat-kwitansi");
        await r.tid("gl-journal-detail").waitFor({ timeout: 20000 });
        await r.idle(800);
        const t = (await r.tid("gl-journal-detail").innerText()).replace(/\s+/g, " ");
        assert(/Kas Besar \/ Bank/.test(t) && /Piutang Usaha/.test(t), `isi jurnal: ${t.slice(0, 300)}`);
        await r.shot("jurnal-kwitansi");
        const je = jurnalKwitansi(rc);
        cekJurnalSeimbang(je, [["1-1100", "D", sisaAwal], ["1-1200", "K", sisaAwal]]);
        return `${je.number}: ${je.lines.map((l) => `${l.account_code} D${l.debit} K${l.credit}`).join(" · ")}`;
      });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  await r.finish();
})();
