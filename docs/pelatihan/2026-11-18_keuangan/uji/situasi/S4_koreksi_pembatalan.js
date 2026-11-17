// S4 — Koreksi & pembatalan: kas, hutang, piutang, gaji, jurnal (situasi khusus, modul 5).
//
// Lima kesalahan yang sering terjadi, masing-masing dibatalkan DI LAYAR oleh peran yang berwenang lalu dicocokkan di BUKU:
//   A. Bayar tagihan pemasok dari rekening yang salah (Kas Toko) → Finance membatalkan pembayaran → jurnal pembalik →
//      hutang & kas kembali → bayar ulang dari BCA.                                            (izin bayar = izin batal, K-37)
//   B. Kwitansi piutang salah nominal → Finance TIDAK bisa membatalkan → Manajer membatalkan → piutang kembali → kwitansi
//      benar dicatat ulang.
//   C. Proses gaji susulan yang sudah DIPOSTING salah nominal → Manajer menganulir (jurnal gaji dibalik bertanggal 31 Okt)
//      → masukan diperbaiki → hitung, ajukan, sahkan, posting ulang → dibayar → gaji yang sudah DIBAYAR tidak bisa dianulir.
//   D. Jurnal umum Manajer salah akun → Balik Jurnal (alasan wajib) → jurnal koreksi; Finance hanya melihat. Lalu kas masuk
//      "Lain-lain" (masuk Akun Sementara 1-9999) direklasifikasi Manajer ke Pendapatan Lain-lain di Tutup Buku.
//   E. Transaksi kas salah kategori yang sudah dicocokkan dengan mutasi bank → anulir ditolak → Finance melepas cocok →
//      Manajer menganulir → dicatat ulang dengan kategori benar → dicocokkan lagi.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/situasi/S4_koreksi_pembatalan.js        (bawaan peserta 76)
//   KN_PESERTA=77 KN_BAGIAN=AB node …                                                   (hanya bagian A & B)
// Data peserta: `seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN` (tagihan pemasok, SO lunas, gaji susulan).
// Peserta yang sudah dipakai tidak bisa diulang (dokumennya sudah dibatalkan/dibayar).
const { Run, api, assert, rp, num, kartu, peserta, akunPeserta, mongo, sleep } = require("../lib");
const hl = require("../hutang_lib");
const kb = require("../kasbank_lib");
const pl = require("../piutang_lib");
const s = require("../sdm/sdm_lib");
const bl = require("../buku_lib");

const NO = peserta("76");
const BAGIAN = (process.env.KN_BAGIAN || "ABCDE").toUpperCase();
const KSC = "ent_ksc";
const REK_TOKO = "Kas Toko KSC";
const REK_BCA = "BCA Operasional KSC";

// ── pembantu buku ──────────────────────────────────────────────────────────────────────────────────────────────────
const jurnalId = (id) => mongo(`return db.journal_entries.findOne({id:${JSON.stringify(id)}},{_id:0})`);
const jurnalNomor = (no) => mongo(`return db.journal_entries.findOne({number:${JSON.stringify(no)},entity_id:"${KSC}"},{_id:0})`);
const pembalikKas = (txnId) => mongo(`return db.journal_entries.findOne({source_type:"cash_transaction_void",
  source_id:${JSON.stringify(txnId)},status:{$ne:"void"}},{_id:0})`);
const kas = (id) => mongo(`return db.cash_transactions.findOne({id:${JSON.stringify(id)}},{_id:0})`);
const kasNomor = (no) => mongo(`return db.cash_transactions.findOne({number:${JSON.stringify(no)},entity_id:"${KSC}"},{_id:0})`);
/** Baris jejak audit terbaru untuk aksi + dokumen: siapa (actor, role), kapan, alasan. */
const jejak = (action, rid) => {
  const a = mongo(`return db.audit_logs.find({action:${JSON.stringify(action)},entity_id:${JSON.stringify(rid)}},
    {_id:0,actor:1,role:1,reason:1,timestamp:1,after:1}).sort({timestamp:-1}).limit(1).toArray()[0]||null`);
  // Kwitansi & kas menyimpan alasan di isi jejak (`after.reason`), dokumen lain di kolom alasan — keduanya tampil di
  // Jejak Audit Admin sebagai "Alasan: …".
  if (a) a.alasan = a.reason || (a.after && a.after.reason) || "";
  return a;
};
const hariIni = () => kb.hariIni().iso;

/** Jurnal `balik` = cermin `asli`: per akun, debit pembalik = kredit asli dan sebaliknya; seimbang. */
function cermin(asli, balik) {
  assert(asli && balik, "jurnal asli / pembalik tidak ada");
  const sum = (je, sisi) => {
    const m = {};
    for (const l of je.lines) m[l.account_code] = Math.round(((m[l.account_code] || 0) + Number(l[sisi] || 0)) * 100);
    return m;
  };
  const [ad, ak, bd, bk] = [sum(asli, "debit"), sum(asli, "credit"), sum(balik, "debit"), sum(balik, "credit")];
  for (const kode of new Set([...Object.keys(ad), ...Object.keys(bd)])) {
    assert((ad[kode] || 0) === (bk[kode] || 0) && (ak[kode] || 0) === (bd[kode] || 0),
      `pembalik ${balik.number} bukan cermin ${asli.number} di akun ${kode}`);
  }
  return `${balik.number} (${String(balik.date).slice(0, 10)}) membalik ${asli.number}: ${kb.teksJurnal(balik).split(": ")[1]}`;
}

/** Manajer bekerja di PT Sukacita (kepala aplikasi), bukan "Semua PT". */
async function pilihPT(r) {
  const sw = r.tid("entity-switcher");
  if (!(await sw.count())) return;
  const lbl = await r.text("entity-switcher");
  if (/Sukacita/.test(lbl) && !/Semua/.test(lbl)) return;
  await sw.click();
  await r.tid(`entity-option-${KSC}`).click();
  await r.idle(1200);
}

async function masukManajer(r) {
  await s.masuk(r, "manager");
  await pilihPT(r);
}

(async () => {
  const r = await new Run("S4", "Koreksi & pembatalan — kas, hutang, piutang, gaji, jurnal").start();
  bl.bersihkanGambar(r);
  const me = akunPeserta(NO);
  const k = kartu(NO);
  const FIN = (await api(me)).user.name;
  r.note(`Peserta ${NO} (${me}, ${FIN}) · bagian ${BAGIAN}`);

  // ═══════════════════════════════ A. PEMBAYARAN TAGIHAN PEMASOK SALAH REKENING ═══════════════════════════════════
  if (BAGIAN.includes("A")) {
    const tg = k["a_dasar:tagihan_bayar"];
    let bill = tg && mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
    const total = bill ? Number(bill.grand_total) : 0;
    let pay1 = null; let pay2 = null;
    const bukaTagihan = async () => {
      await hl.menu(r, "keuangan", "accounts-payable");
      await r.tid("vendor-bills-view").waitFor();
      await r.tid("vb-search").fill(`Latihan ${NO}`);
      await r.idle(900);
      await r.tid(`vb-open-${tg.tagihan_id}`).click();
      await r.tid("vendor-bill-detail-panel").waitFor();
      await r.idle(600);
    };

    await r.step(1, "Finance", `Bayar tagihan ${tg ? tg.tagihan : "pemasok"} dari rekening yang SALAH: Keuangan › Hutang → cari "Latihan ${NO}" → [[Detail →]] → [[Bayar]] → *Rekening sumber* ${REK_TOKO} → [[Bayar]] → [[Ya, bayar]]`,
      `Konfirmasi menyebut ${REK_TOKO}; tagihan berstatus Lunas, Sisa Hutang Rp 0 (kesalahan belum terlihat dari layar tagihan)`, async () => {
        assert(bill && bill.status === "posted" && Number(bill.amount_paid || 0) < 0.01,
          `tagihan ${tg && tg.tagihan} bukan Terposting belum dibayar (${bill && bill.status}) — pakai peserta segar`);
        await s.masuk(r, me);
        await bukaTagihan();
        await r.tid("vb-action-pay").click();
        await r.tid("pay-supplier-modal").waitFor();
        await r.tid("pay-supplier-number").waitFor();
        await hl.pilih(r, "pay-supplier-account", REK_TOKO);
        assert(num(await r.tid("pay-supplier-amount").inputValue()) === Math.round(total), "nominal bayar ≠ total tagihan");
        await hl.sorot(r.tid("pay-supplier-account"));
        await r.shot("a-bayar-rekening-salah", { locator: r.tid("pay-supplier-modal") });
        await hl.lepas(r.tid("pay-supplier-account"));
        await r.tid("pay-supplier-submit").click();
        const msg = await r.text("pay-supplier-confirm-message");
        assert(msg.includes(REK_TOKO), `konfirmasi tanpa ${REK_TOKO}: ${msg}`);
        await hl.setuju(r, "pay-supplier-confirm");
        await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
        await hl.tungguTeks(r, "vb-detail-status", /Lunas/);
        bill = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
        pay1 = (bill.payments || []).find((p) => !p.voided);
        assert(bill.status === "paid" && pay1 && pay1.cash_txn_id, `DB: ${bill.status}`);
        return `konfirmasi "${msg}" · ${tg.tagihan} Lunas · kas ${pay1.cash_txn_number}`;
      });

    await r.step(2, "Finance", "Cek buku: jurnal pembayaran yang salah",
      `2-1100 Hutang Usaha (D) ${rp(total)} · 1-1110 Kas Kecil (K) ${rp(total)} — uang tercatat keluar dari Kas Toko, bukan dari bank`, async () => {
        const je = kb.seimbang(kb.jurnal("cash_transaction", pay1.cash_txn_id), "jurnal bayar");
        assert(kb.adaBaris(je, "2-1100", "D", total) && kb.adaBaris(je, "1-1110", "K", total), kb.teksJurnal(je));
        const c = kas(pay1.cash_txn_id);
        const rek = mongo(`return db.bank_accounts.findOne({id:"${c.account_id}"},{_id:0,name:1})`);
        assert(rek.name === REK_TOKO, `kas keluar dari ${rek.name}`);
        await hl.sorot(r.tid("vb-payments"));
        await r.shot("a-tagihan-lunas-salah", { locator: r.tid("vendor-bill-detail-panel") });
        await hl.lepas(r.tid("vb-payments"));
        return `${kb.teksJurnal(je)} · ${c.number} dari ${rek.name}`;
      });

    await r.step(3, "Finance", `Di bagian Pembayaran klik [[Batalkan]] → isi *Alasan* "Salah rekening: dibayar dari Kas Toko, seharusnya transfer BCA" → [[Batalkan pembayaran]]`,
      `Dialog "Batalkan pembayaran ${rp(total)}?" menyebut nomor kas yang dianulir; sesudahnya pesan "${tg ? tg.tagihan : "VB-…"}: pembayaran dibatalkan, jurnalnya dibalik — hutang terbuka kembali.", baris pembayaran dicoret dengan tanda Dibatalkan + alasan + nama pembatal, status Terposting, Sisa Hutang ${rp(total)}, tombol [[Bayar]] muncul lagi; Riwayat: "Pembayaran dicatat … transfer dari ${REK_TOKO}" lalu "Pembayaran dibatalkan · ${FIN} — <alasan>"`, async () => {
        const btn = r.tid(`vb-payment-void-${pay1.id}`);
        await btn.waitFor();
        await hl.klikPotret(r, btn, "a-tombol-batalkan-bayar", { locator: r.tid("vendor-bill-detail-panel") });
        await r.tid("vb-payment-void-confirm").waitFor();
        const pesan = await r.text("vb-payment-void-confirm-message");
        assert(pesan.includes(pay1.cash_txn_number), `dialog tanpa nomor kas: ${pesan}`);
        await r.tid("vb-payment-void-confirm-reason").fill("Salah rekening: dibayar dari Kas Toko, seharusnya transfer BCA");
        await r.shot("a-alasan-batal-bayar", { locator: r.tid("vb-payment-void-confirm").locator(".modal-card").first() }).catch(() => r.shot("a-alasan-batal-bayar"));
        await r.tid("vb-payment-void-confirm-confirm").click();
        await r.tid(`vb-payment-voided-${pay1.id}`).waitFor({ timeout: 20000 });
        await hl.tungguTeks(r, "vb-detail-status", /Terposting/);
        assert(num(await r.text("vb-fin-outstanding")) === Math.round(total), "Sisa Hutang belum kembali penuh");
        await r.tid("vb-action-pay").waitFor();
        const tl = await r.text("vb-timeline");
        assert(/Pembayaran dibatalkan/.test(tl) && tl.includes(FIN) && /Salah rekening/.test(tl), `riwayat: ${tl.slice(-300)}`);
        assert(tl.includes(`dari ${REK_TOKO}`) && !/kas_kecil/.test(tl), `riwayat tanpa nama rekening: ${tl.slice(-300)}`);
        const alasan = await r.text(`vb-payment-void-reason-${pay1.id}`);
        assert(alasan.startsWith("Salah rekening: dibayar dari Kas Toko") && alasan.includes(FIN), `alasan batal: ${alasan}`);
        const notice = await r.text("vb-notice").catch(() => "");
        assert(/pembayaran dibatalkan/.test(notice) && !/payment_void/.test(notice), `pesan halaman: ${notice}`);
        await hl.sorot(r.tid("vb-payments")); await hl.sorot(r.tid("vb-timeline"));
        await r.shot("a-bayar-dibatalkan", { locator: r.tid("vendor-bill-detail-panel") });
        await hl.lepas(r.tid("vb-payments")); await hl.lepas(r.tid("vb-timeline"));
        return `dialog "${pesan}" · pesan halaman "${notice}" · riwayat …${tl.slice(-160)}`;
      });

    await r.step(4, "Finance", "Cek buku: jurnal pembalik, kas, hutang, jejak audit",
      `Jurnal pembalik bertanggal hari ini = cermin jurnal bayar: 1-1110 Kas Kecil (D) · 2-1100 Hutang Usaha (K) ${rp(total)}; kas Kas Toko berstatus dianulir; jejak audit: ${FIN}, alasan tersimpan`, async () => {
        const c = kas(pay1.cash_txn_id);
        assert(c.status === "void" && c.void_journal_entry_id, `kas ${c.number} status ${c.status}`);
        const asli = mongo(`return db.journal_entries.findOne({source_type:"cash_transaction",source_id:"${c.id}"},{_id:0})`);
        const balik = jurnalId(c.void_journal_entry_id);
        const t = cermin(asli, balik);
        assert(String(balik.date).slice(0, 10) === hariIni(), `tanggal pembalik ${balik.date}`);
        const a = jejak("vendor_bill_payment_voided", tg.tagihan_id);
        assert(a && a.actor === FIN && /Salah rekening/.test(a.alasan), `jejak audit: ${JSON.stringify(a)}`);
        bill = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
        assert(Math.abs(Number(bill.amount_paid)) < 0.01 && bill.status === "posted", `tagihan ${bill.status} dibayar ${bill.amount_paid}`);
        return `${t} · kas ${c.number} void · audit ${a.actor} (${a.role}) ${a.timestamp.slice(0, 19)} "${a.alasan}"`;
      });

    await r.step(5, "Finance", `Bayar ulang dengan benar: [[Bayar]] → *Rekening sumber* ${REK_BCA} → [[Bayar]] → [[Ya, bayar]]`,
      `Tagihan Lunas lagi; daftar Pembayaran: satu baris dicoret (Kas Toko, dibatalkan) + satu baris aktif (BCA)`, async () => {
        await r.tid("vb-action-pay").click();
        await r.tid("pay-supplier-modal").waitFor();
        await r.tid("pay-supplier-number").waitFor();
        await hl.pilih(r, "pay-supplier-account", REK_BCA);
        await r.tid("pay-supplier-submit").click();
        const msg = await r.text("pay-supplier-confirm-message");
        assert(msg.includes(REK_BCA), `konfirmasi: ${msg}`);
        await hl.setuju(r, "pay-supplier-confirm");
        await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
        await hl.tungguTeks(r, "vb-detail-status", /Lunas/);
        bill = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
        pay2 = (bill.payments || []).find((p) => !p.voided);
        assert(pay2 && pay2.id !== pay1.id && bill.status === "paid", "pembayaran ulang tidak tercatat");
        await r.tid(`vb-payment-${pay2.id}`).waitFor();
        await hl.sorot(r.tid("vb-payments"));
        await r.shot("a-bayar-ulang-lunas", { locator: r.tid("vendor-bill-detail-panel") });
        await hl.lepas(r.tid("vb-payments"));
        return `"${msg}" · ${await r.text("vb-payments")}`;
      });

    await r.step(6, "Finance", "Cek buku: jurnal bayar ulang & saldo hutang tagihan ini",
      `2-1100 Hutang Usaha (D) · 1-1100 Kas Besar / Bank (K) ${rp(total)}; mutasi Hutang Usaha tagihan ini: tagihan (K) − bayar salah (D) + pembalik (K) − bayar benar (D) = 0`, async () => {
        const je = kb.seimbang(kb.jurnal("cash_transaction", pay2.cash_txn_id), "jurnal bayar ulang");
        assert(kb.adaBaris(je, "2-1100", "D", total) && kb.adaBaris(je, "1-1100", "K", total), kb.teksJurnal(je));
        const ids = [pay1.cash_txn_id, pay2.cash_txn_id];
        const jes = mongo(`return db.journal_entries.find({$or:[{source_id:{$in:${JSON.stringify(ids)}}},{source_id:"${tg.tagihan_id}"},
          {"ref.vendor_bill_id":"${tg.tagihan_id}"}],status:{$ne:"void"}},{_id:0,number:1,lines:1}).toArray()`);
        let net = 0;
        for (const j of jes) for (const l of j.lines) if (l.account_code === "2-1100") net += Number(l.debit || 0) - Number(l.credit || 0);
        const kasBca = kas(pay2.cash_txn_id);
        assert(mongo(`return db.bank_accounts.findOne({id:"${kasBca.account_id}"},{_id:0,name:1}).name`) === REK_BCA, "bayar ulang bukan dari BCA");
        return `${kb.teksJurnal(je)} · jurnal tagihan ini: ${jes.map((j) => j.number).join(", ")} · neto 2-1100 ${rp(net)} (tagihan K + bayar D + pembalik + bayar ulang)`;
      });
  }

  // ═══════════════════════════════ B. KWITANSI PIUTANG SALAH NOMINAL ═════════════════════════════════════════════
  if (BAGIAN.includes("B")) {
    const so = k["a_dasar:so_lunas"];
    const sisa0 = so ? pl.sisaSo(so.so_id) : 0;
    const benar = Math.round(sisa0);                 // transfer pelanggan (rupiah bulat)
    const salah = benar - 100000;                    // salah baca bukti transfer: 3.349.148 → 3.249.148
    let rc = null; let rc2 = null;
    r.note(`B: ${so && so.so} sisa ${sisa0} · transfer ${benar} · tercatat salah ${salah}`);

    await r.step(7, "Finance", `Catat kwitansi dengan nominal SALAH: Keuangan › Piutang › Penagihan & Penerimaan → baris ${so ? so.so : "SO"} → ikon dompet → ganti alokasi menjadi ${salah.toLocaleString("id-ID")} → [[Simpan kwitansi]] → "Sisa tetap jadi piutang" → [[Ya, simpan]]`,
      `Kwitansi tercatat; ${so ? so.so : "SO"} berstatus bayar Sebagian dengan sisa ±Rp 100.000`, async () => {
        assert(so && Math.abs(sisa0 - so.total) < 0.01, `${so && so.so} sudah pernah dibayar — pakai peserta segar`);
        await s.masuk(r, me);
        await pl.bukaPenagihan(r);
        await (await pl.barisSo(r, so.so_id)).waitFor();
        await r.tid(`collection-pay-${so.so_id}`).click();
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid(`ar-receipt-alloc-${so.so_id}`).waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await r.tid(`ar-receipt-alloc-${so.so_id}`).fill(String(salah));
        await r.tid("ar-receipt-reference").fill(`TRF-LATIH${NO}-S4`);
        await r.page.waitForFunction(() => /Kurang bayar/i.test(
          (document.querySelector('[data-testid="ar-receipt-variance-hint"]') || {}).innerText || ""), null, { timeout: 10000 });
        await pl.sorot(r.tid(`ar-receipt-alloc-${so.so_id}`));
        await r.shot("b-kwitansi-nominal-salah");
        await pl.lepas(r.tid(`ar-receipt-alloc-${so.so_id}`));
        await r.tid("ar-receipt-submit").click();
        await r.tid("payment-variance-dialog").waitFor();
        await r.tid("pv-option-outstanding").click();
        await pl.pilih(r, "pv-reason", "Bayar sebagian (disepakati)");
        await r.tid("pv-note").fill("Menurut bukti transfer pelanggan");
        await r.tid("pv-submit").click();
        await r.tid("ar-receipt-confirm").waitFor();
        await r.tid("ar-receipt-confirm-confirm").click();
        await r.tid("collection-notice").waitFor({ timeout: 20000 });
        const note = await r.text("collection-notice");
        rc = pl.kwitansiTerakhir(so.so_id);
        assert(rc && Math.abs(rc.amount - salah) < 0.01, `kwitansi ${rc && rc.amount} ≠ ${salah}`);
        const st = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,payment_status:1}).payment_status`);
        assert(st === "partial", `status bayar ${st}`);
        return `${note} · sisa ${rp(pl.sisaSo(so.so_id))}`;
      });

    await r.step(8, "Finance", `Rekening koran BCA menunjukkan transfer ${rp(benar)}, bukan ${rp(salah)}. Di Riwayat Pembayaran (AR) ketik nomor kwitansi`,
      "Baris kwitansi tampil dengan nominal salah; Finance juga melihat ikon Batalkan (K-FIN-01) — di peragaan ini Manajer membatalkan sebagai orang kedua yang memeriksa bukti", async () => {
        const je = pl.jurnalKwitansi(rc);
        pl.cekJurnalSeimbang(je, [["1-1100", "D", salah], ["1-1200", "K", salah]]);
        await r.tid("ar-history-search").fill(rc.number);
        const row = r.tid(`ar-history-row-${rc.id}`);
        await row.waitFor();
        await r.idle(500);
        await r.kfin(r.tid(`ar-history-void-${rc.id}`), "ikon Batalkan kwitansi");
        await pl.sorot(row);
        await r.shot("b-finance-tanpa-batalkan");
        await pl.lepas(row);
        return `${rc.number} ${rp(rc.amount)} · jurnal ${je.number} Kas/Bank (D) = Piutang (K) ${rp(salah)}`;
      });

    await r.step(9, "Manajer", `Login Manajer → Keuangan › Piutang › Penagihan & Penerimaan → Riwayat Pembayaran (AR) → cari nomor kwitansi → ikon [[Batalkan]] → *Alasan* "Salah nominal: mutasi BCA ${rp(benar)}, tercatat ${rp(salah)}" → [[Batalkan Penerimaan]]`,
      `Dialog menyebut nominal yang dibalik (pembayaran pesanan, kas, titipan); kwitansi berstatus Dianulir (nominal dicoret), kolom Selisih "Ikut dianulir"; baris ${so ? so.so : "SO"} kembali di daftar penagihan dengan sisa penuh`, async () => {
        await masukManajer(r);
        await pl.bukaPenagihan(r);
        await r.tid("ar-history-search").fill(rc.number);
        const btn = r.tid(`ar-history-void-${rc.id}`);
        await btn.waitFor({ timeout: 15000 });
        await pl.sorot(r.tid(`ar-history-row-${rc.id}`));
        await pl.klikSorot(r, btn, "b-manajer-batalkan-kwitansi");
        await pl.lepas(r.tid(`ar-history-row-${rc.id}`));
        await r.tid("ar-void-confirm").waitFor();
        const pesan = await r.text("ar-void-confirm-message");
        assert(pesan.includes(rp(salah)), `dialog: ${pesan}`);
        await r.tid("ar-void-confirm-reason").fill(`Salah nominal: mutasi BCA ${rp(benar)}, tercatat ${rp(salah)}`);
        await r.shot("b-alasan-batal-kwitansi", { locator: r.tid("ar-void-confirm").locator(".modal-card").first() }).catch(() => r.shot("b-alasan-batal-kwitansi"));
        await r.tid("ar-void-confirm-confirm").click();
        await kb.tunggu(r, `ar-history-status-${rc.id}`, /Dianulir/, 20000);
        const sel = await r.text(`ar-history-variance-${rc.id}`);
        assert(/Ikut dianulir/.test(sel) && !/perlu diputus/i.test(sel), `kolom Selisih kwitansi batal: ${sel}`);
        await pl.sorot(r.tid(`ar-history-row-${rc.id}`));
        await r.shot("b-kwitansi-dianulir");
        await pl.lepas(r.tid(`ar-history-row-${rc.id}`));
        return `dialog "${pesan}"`;
      });

    await r.step(10, "Manajer", "Cek buku: jurnal pembalik kwitansi, piutang pesanan, jejak audit",
      `Jurnal pembalik hari ini: 1-1200 Piutang Usaha (D) · 1-1100 Kas Besar / Bank (K) ${rp(salah)}; ${so ? so.so : "SO"} kembali Belum Bayar dengan sisa ${rp(sisa0)}; keputusan selisih ikut dibatalkan; jejak audit Manajer + alasan`, async () => {
        const v = mongo(`return db.ar_receipts.findOne({id:"${rc.id}"},{_id:0})`);
        assert(v.status === "void", `status kwitansi ${v.status}`);
        const asli = pl.jurnalKwitansi(rc);
        const balik = pembalikKas(rc.cash_txn_id);
        const t = cermin(asli, balik);
        assert(String(balik.date).slice(0, 10) === hariIni(), `tanggal pembalik ${balik.date}`);
        assert(Math.abs(pl.sisaSo(so.so_id) - sisa0) < 0.01, `sisa SO ${pl.sisaSo(so.so_id)} ≠ ${sisa0}`);
        const st = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,payment_status:1}).payment_status`);
        assert(st === "unpaid", `status bayar SO ${st}`);
        const decId = (v.variance || {}).reversed_decision_id || (v.variance || {}).decision_id;
        const dec = decId && mongo(`return db.payment_variance_decisions.findOne({id:"${decId}"},{_id:0,status:1,number:1})`);
        assert(dec && dec.status === "reversed", `keputusan selisih ${JSON.stringify(dec)}`);
        const a = jejak("ar_receipt_voided", rc.id);
        assert(a && a.role === "manager" && /Salah nominal/.test(a.alasan), `jejak audit: ${JSON.stringify(a)}`);
        return `${t} · ${so.so} ${st} sisa ${rp(sisa0)} · keputusan selisih ${dec.number || decId} ${dec.status} · audit ${a.actor} ${a.timestamp.slice(0, 19)} "${a.alasan}"`;
      });

    await r.step(11, "Finance", `Login Finance → catat ulang kwitansi yang benar: baris ${so ? so.so : "SO"} → ikon dompet → alokasi ${benar.toLocaleString("id-ID")} → [[Simpan kwitansi]] → [[Ya, simpan]]`,
      `"Nominal sesuai tagihan — tidak ada selisih"; kwitansi baru tercatat; ${so ? so.so : "SO"} Lunas`, async () => {
        await s.masuk(r, me);
        await pl.bukaPenagihan(r);
        await (await pl.barisSo(r, so.so_id)).waitFor();
        await r.tid(`collection-pay-${so.so_id}`).click();
        await r.tid("ar-receipt-modal").waitFor();
        await r.tid(`ar-receipt-alloc-${so.so_id}`).waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
        await r.tid(`ar-receipt-alloc-${so.so_id}`).fill(String(benar));
        await r.tid("ar-receipt-reference").fill(`TRF-LATIH${NO}-S4-BENAR`);
        await r.idle(1000);
        const hint = await r.text("ar-receipt-variance-hint");
        assert(/tidak ada selisih/i.test(hint), `petunjuk: ${hint}`);
        await r.tid("ar-receipt-submit").click();
        await r.tid("ar-receipt-confirm").waitFor();
        await r.tid("ar-receipt-confirm-confirm").click();
        await r.tid("collection-notice").waitFor({ timeout: 20000 });
        rc2 = pl.kwitansiTerakhir(so.so_id);
        assert(rc2 && rc2.id !== rc.id, "kwitansi baru tidak ditemukan");
        await r.tid("ar-history-search").fill(`TRF-LATIH${NO}-S4`);
        await r.tid(`ar-history-row-${rc2.id}`).waitFor().catch(() => {});
        await r.idle(600);
        await r.shot("b-kwitansi-benar");
        return `${hint} · ${await r.text("collection-notice")}`;
      });

    await r.step(12, "Finance", "Cek buku: kwitansi benar & piutang",
      `Jurnal 1-1100 Kas Besar / Bank (D) · 1-1200 Piutang Usaha (K) ${rp(sisa0)}; ${so ? so.so : "SO"} Lunas, sisa Rp 0; neto piutang pesanan dari tiga jurnal kwitansi = pelunasan penuh`, async () => {
        const je = pl.jurnalKwitansi(rc2);
        pl.cekJurnalSeimbang(je, [["1-1100", "D", rc2.amount], ["1-1200", "K", rc2.amount]]);
        assert(Math.abs(rc2.amount - sisa0) < 0.01, `kwitansi ${rc2.amount} ≠ ${sisa0}`);
        const st = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,payment_status:1}).payment_status`);
        assert(st === "paid" && pl.sisaSo(so.so_id) <= 0.01, `SO ${st} sisa ${pl.sisaSo(so.so_id)}`);
        return `${rc2.number} ${rp(rc2.amount)} · ${je.number} · ${so.so} ${st}`;
      });
  }

  // ═══════════════════════════════ C. PROSES GAJI DIPOSTING SALAH → ANULIR → ULANG ═══════════════════════════════
  if (BAGIAN.includes("C")) {
    const g = k["d_hutang:gaji_susulan"];
    let run = g && mongo(`return db.hr_payroll_runs.findOne({id:"${g.proses_gaji_id}"},{_id:0})`);
    const inp0 = run && mongo(`return db.hr_pay_inputs.findOne({used_run_id:"${run.id}"},{_id:0})`);
    const BENAR = 800000;
    let inp1 = null; let run2 = null;
    const bukaProses = async (id) => {
      await r.go("hr-payroll-runs");
      await r.tid(`payroll-run-${id}`).waitFor({ timeout: 15000 });
      await r.tid(`payroll-run-${id}`).click();
      await r.tid("payroll-run-detail").waitFor();
      await r.idle(500);
    };

    await r.step(13, "Manajer", `Login Manajer → SDM › Penggajian › Proses Gaji → pilih ${g ? g.proses_gaji : "proses susulan"} (Diposting) → [[Anulir]] → *Alasan* "Nominal insentif salah, seharusnya Rp 800.000" → [[Anulir]]`,
      `Dialog menyebut periode, jenis Susulan, jumlah karyawan, gaji bersih, PT dan "Jurnal gaji akan dibalik"; status Dianulir dengan bilah "Dianulir oleh … · jurnal pembalik KSC/JE-…: <alasan>"`, async () => {
        assert(run && run.status === "posted" && inp0, `proses ${g && g.proses_gaji} bukan Diposting (${run && run.status}) — pakai peserta segar`);
        assert(!mongo(`return db.cash_transactions.findOne({ref_id:"${run.id}",status:{$ne:"void"}},{_id:0,id:1})`), "proses sudah punya kas bayar");
        await masukManajer(r);
        await bukaProses(run.id);
        assert(/Diposting/.test(await r.text("payroll-detail-status")), "status awal bukan Diposting");
        await hl.klikPotret(r, r.tid("payroll-void"), "c-tombol-anulir-gaji", { locator: r.tid("payroll-run-detail") });
        await r.tid("confirm-modal").waitFor();
        const pesan = await r.text("confirm-modal-message");
        assert(/Oktober 2026/.test(pesan) && /dibalik/.test(pesan) && /Sukacita/.test(pesan), `dialog: ${pesan}`);
        await r.tid("confirm-modal-reason").fill("Nominal insentif salah, seharusnya Rp 800.000");
        await r.shot("c-alasan-anulir", { locator: r.tid("confirm-modal").locator(".modal-card").first() }).catch(() => r.shot("c-alasan-anulir"));
        await r.tid("confirm-modal-confirm").click();
        await hl.tungguTeks(r, "payroll-notice", /dianulir; jurnal gaji dibalik/, 30000);
        const bar = await r.text("payroll-void-reason");
        assert(/Dianulir/.test(bar) && /KSC\/JE-/.test(bar) && /Nominal insentif salah/.test(bar), `bilah: ${bar}`);
        await hl.sorot(r.tid("payroll-void-reason"));
        await r.shot("c-gaji-dianulir", { locator: r.tid("payroll-run-detail") });
        await hl.lepas(r.tid("payroll-void-reason"));
        return `dialog "${pesan}" · ${bar}`;
      });

    await r.step(14, "Manajer", "Cek buku: jurnal pembalik gaji, masukan, jejak audit",
      `Jurnal pembalik bertanggal 31 Okt 2026 (tanggal jurnal gaji asal, bukan hari ini) = cermin jurnal gaji: Hutang Gaji 2-1600 (D) + Hutang PPh 21 2-1800 (D) · beban (K); masukan insentif kembali "Disahkan" (bisa dipakai lagi)`, async () => {
        run = mongo(`return db.hr_payroll_runs.findOne({id:"${run.id}"},{_id:0})`);
        assert(run.status === "void" && run.void_journal_id, `status ${run.status}`);
        const asli = jurnalId(run.journal_id);
        const balik = jurnalId(run.void_journal_id);
        const t = cermin(asli, balik);
        assert(String(balik.date).slice(0, 10) === String(asli.date).slice(0, 10), `tanggal pembalik ${balik.date} ≠ ${asli.date}`);
        const i = mongo(`return db.hr_pay_inputs.findOne({id:"${inp0.id}"},{_id:0,status:1})`);
        assert(i.status === "approved", `masukan ${i.status}`);
        const a = jejak("hr.payroll.run_void", run.id);
        assert(a && a.role === "manager" && /insentif salah/.test(a.alasan), `jejak: ${JSON.stringify(a)}`);
        return `asli ${kb.teksJurnal(asli)} · ${t} · masukan ${i.status} · audit ${a.actor} ${a.timestamp.slice(0, 19)}`;
      });

    await r.step(15, "Manajer", `Tab Komponen & Masukan → *Periode bayar* Oktober 2026 → masukan "${inp0 ? inp0.label : "Insentif"}" ${inp0 ? rp(inp0.amount) : ""} (Disahkan) → [[Batalkan]] → *Alasan* "Nominal salah, diganti Rp 800.000" → [[Batalkan masukan]]`,
      "Pesan \"Masukan … dibatalkan.\"; status Dibatalkan (tidak ikut proses gaji)", async () => {
        await r.go("hr-pay-components");
        await r.tid("payinput-period").waitFor({ timeout: 15000 });
        await s.pilihPersis(r, "payinput-period", s.MASA_LABEL);
        const btn = r.tid(`payinput-cancel-${inp0.id}`);
        await btn.waitFor({ timeout: 15000 });
        await btn.scrollIntoViewIfNeeded();
        await hl.sorot(r.tid(`payinput-row-${inp0.id}`));
        await hl.klikPotret(r, btn, "c-batalkan-masukan");
        await hl.lepas(r.tid(`payinput-row-${inp0.id}`));
        await r.tid("confirm-modal-reason").fill("Nominal salah, diganti Rp 800.000");
        await r.tid("confirm-modal-confirm").click();
        await s.tungguTeks(r, "paycomp-view", /dibatalkan\./);
        const i = mongo(`return db.hr_pay_inputs.findOne({id:"${inp0.id}"},{_id:0,status:1})`);
        assert(i.status === "cancelled", `masukan ${i.status}`);
        return `masukan ${inp0.label} ${rp(inp0.amount)} → ${i.status}`;
      });

    await r.step(16, "Finance", `Login Finance → tab Komponen & Masukan → [[Tambah masukan]]: *Karyawan* ${inp0 ? inp0.employee_name : ""} · *Komponen* Insentif (Pendapatan) — bukan "Komisi / insentif penjualan" · *Periode bayar* Oktober 2026 · *Nominal* 800.000 · *Keterangan* Insentif tertinggal (koreksi) · *Alasan* Koreksi proses ${g ? g.proses_gaji : ""} → [[Simpan masukan]]`,
      "Pesan \"… dicatat, menunggu disahkan.\"; status Menunggu disahkan", async () => {
        await s.masuk(r, me);
        await s.menu(r, "hrd", "hr-payroll-hub");
        await r.tid("hub-tab-hr-pay-components").click();
        await r.tid("paycomp-table").waitFor({ timeout: 15000 });
        await r.tid("payinput-add").scrollIntoViewIfNeeded();
        // Daftar karyawan dimuat sesudah pop-up terbuka; kotak pilihan berganti bentuk (daftar pendek → daftar ber-cari)
        // saat datanya tiba — tunggu dulu supaya daftar yang dibuka tidak tertutup sendiri.
        await Promise.all([r.page.waitForResponse((x) => x.url().includes("/hr/employees"), { timeout: 15000 }).catch(() => {}),
          r.tid("payinput-add").click()]);
        await r.tid("payinput-form").waitFor();
        await r.idle(800);
        await s.pilihPersis(r, "payinput-form-emp", inp0.employee_name);
        await s.pilihPersis(r, "payinput-form-comp", "Insentif (Pendapatan)");   // bukan "Komisi / insentif penjualan" (hanya proses reguler)
        await s.pilihPersis(r, "payinput-form-period", s.MASA_LABEL);
        await r.tid("payinput-form-amount").fill("800.000");
        await r.tid("payinput-form-label").fill("Insentif tertinggal (koreksi)");
        await r.tid("payinput-form-reason").fill(`Koreksi proses ${g.proses_gaji} — Latihan ${NO}`);
        await hl.sorot(r.tid("payinput-form-submit"));
        await r.shot("c-masukan-benar", { locator: r.tid("payinput-form") });
        await hl.lepas(r.tid("payinput-form-submit"));
        await r.tid("payinput-form-submit").click();
        await r.tid("payinput-form").waitFor({ state: "detached", timeout: 15000 });
        await s.tungguTeks(r, "paycomp-view", /dicatat, menunggu disahkan/);
        inp1 = mongo(`return db.hr_pay_inputs.find({employee_id:"${inp0.employee_id}",pay_period:"${s.MASA}",reason:/Latihan ${NO}$/,
          status:"pending"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
        assert(inp1 && Number(inp1.amount) === BENAR && inp1.component_code === inp0.component_code,
          `masukan baru: ${JSON.stringify(inp1 && { a: inp1.amount, s: inp1.status, k: inp1.component_code })}`);
        return `${inp1.label} ${rp(inp1.amount)} · ${inp1.status}`;
      });

    await r.step(17, "Manajer", "Login Manajer → Komponen & Masukan → Oktober 2026 → [[Sahkan]] masukan koreksi → konfirmasi",
      "Status Disahkan — siap dimuat proses gaji susulan", async () => {
        await masukManajer(r);
        await r.go("hr-pay-components");
        await r.tid("payinput-period").waitFor({ timeout: 15000 });
        await s.pilihPersis(r, "payinput-period", s.MASA_LABEL);
        await r.tid(`payinput-approve-${inp1.id}`).waitFor({ timeout: 15000 });
        await r.tid(`payinput-approve-${inp1.id}`).click();
        await s.konfirmasi(r);
        await s.tungguTeks(r, "paycomp-view", /disahkan\./);
        const lain = mongo(`return db.hr_pay_inputs.find({entity_id:"${KSC}",pay_period:"${s.MASA}",status:"approved",id:{$ne:"${inp1.id}"}},
          {_id:0,label:1,employee_name:1,amount:1}).toArray()`);
        assert(!lain.length, `masukan disahkan lain menunggu di Oktober (akan ikut proses susulan): ${JSON.stringify(lain)}`);
        return `${await r.text(`payinput-status-${inp1.id}`)}`;
      });

    await r.step(18, "Finance", "Login Finance → Proses Gaji → *Periode* Oktober 2026 · *Jenis* Susulan → [[Hitung Susulan Oktober 2026]] → [[Ajukan]]",
      `Proses baru 1 karyawan, bruto ${rp(BENAR)}; status Diajukan`, async () => {
        await s.masuk(r, me);
        await r.go("hr-payroll-runs");
        await r.tid("payroll-runs-view").waitFor();
        const pt = await r.text("payroll-create-entity").catch(() => "");
        if (!/Sukacita/i.test(pt)) await s.pilih(r, "payroll-create-entity", "Sukacita");
        await s.pilihPersis(r, "payroll-create-period", s.MASA_LABEL);
        await s.pilihPersis(r, "payroll-create-type", "Susulan");
        await r.tid("payroll-create-submit").click();
        await s.tungguTeks(r, "payroll-notice", /siap \(\d+ karyawan\)/, 30000);
        run2 = mongo(`return db.hr_payroll_runs.findOne({id:(db.hr_pay_inputs.findOne({id:"${inp1.id}"})||{}).used_run_id},{_id:0})`);
        assert(run2 && run2.status === "draft" && run2.totals.employees === 1 && Math.abs(run2.totals.gross - BENAR) < 0.01,
          `proses baru: ${JSON.stringify(run2 && { s: run2.status, e: run2.totals.employees, g: run2.totals.gross })}`);
        await r.tid("payroll-submit").click();
        await s.tungguTeks(r, "payroll-notice", /Ajukan berhasil/);
        await r.shot("c-proses-ulang-diajukan", { locator: r.tid("payroll-run-detail") });
        return `${run2.number} bruto ${rp(run2.totals.gross)} · PPh 21 ${rp(run2.totals.pph21)} · bersih ${rp(run2.totals.net)}`;
      });

    await r.step(19, "Manajer", "Login Manajer → Proses Gaji → pilih proses baru → [[Sahkan]] → konfirmasi", "Status Disahkan", async () => {
      await masukManajer(r);
      await bukaProses(run2.id);
      await r.tid("payroll-approve").click();
      await s.konfirmasi(r);
      await s.tungguTeks(r, "payroll-notice", /Sahkan berhasil/);
      return mongo(`return db.hr_payroll_runs.findOne({id:"${run2.id}"},{_id:0,status:1}).status`);
    });

    await r.step(20, "Finance", "Login Finance → Proses Gaji → pilih proses baru → [[Posting Jurnal]] → konfirmasi",
      `Status Diposting; jurnal gaji baru bertanggal buku 31 Okt 2026, bruto ${rp(BENAR)}`, async () => {
        await s.masuk(r, me);
        await bukaProses(run2.id);
        await r.tid("payroll-post-gl").click();
        await s.konfirmasi(r);
        await s.tungguTeks(r, "payroll-notice", /Posting jurnal berhasil/, 30000);
        run2 = mongo(`return db.hr_payroll_runs.findOne({id:"${run2.id}"},{_id:0})`);
        const je = jurnalId(run2.journal_id);
        const t = run2.totals;
        const beban = je.lines.filter((l) => Number(l.debit) > 0);
        assert(Math.abs(beban.reduce((a, l) => a + Number(l.debit), 0) - BENAR) < 0.01, `beban ${kb.teksJurnal(je)}`);
        hl.cekJurnal(je, [["2-1600", "K", t.net], ["2-1800", "K", t.pph21]]);
        assert(String(je.date).slice(0, 10) === "2026-10-31", `tanggal ${je.date}`);
        await hl.sorot(r.tid("payroll-journal-ref"));
        await r.shot("c-posting-ulang", { locator: r.tid("payroll-run-detail") });
        await hl.lepas(r.tid("payroll-journal-ref"));
        return `${kb.teksJurnal(je)} · tanggal ${je.date}`;
      });

    await r.step(21, "Finance", `[[Bayar]] → *Rekening* ${REK_BCA} → [[Bayar gaji]] → konfirmasi`,
      "Status Dibayar; tombol Anulir TIDAK ada; tertulis \"Gaji yang sudah dibayar tidak bisa dianulir; koreksinya lewat proses susulan.\"", async () => {
        await r.tid("payroll-pay").click();
        await r.tid("pay-form").waitFor();
        await r.tid("pay-form-summary").waitFor({ timeout: 15000 });
        const acc = await r.text("pay-form-account");
        if (!acc.includes(REK_BCA)) await s.pilih(r, "pay-form-account", REK_BCA);
        await r.tid("pay-form-submit").click();
        await s.konfirmasi(r);
        await r.tid("pay-form").waitFor({ state: "detached", timeout: 20000 });
        await r.tid("transfer-panel").waitFor({ timeout: 10000 }).catch(() => {});   // Daftar transfer terbuka sendiri sesudah bayar
        if (await r.tid("transfer-modal-close-x").isVisible().catch(() => false)) {
          await r.tid("transfer-modal-close-x").click();
          await r.tid("transfer-panel").waitFor({ state: "detached" }).catch(() => {});
        }
        await r.tid("payroll-paid-hint").waitFor({ timeout: 15000 });
        run2 = mongo(`return db.hr_payroll_runs.findOne({id:"${run2.id}"},{_id:0})`);
        assert(run2.status === "paid", `status ${run2.status}`);
        assert(!(await r.tid("payroll-void").count()), "tombol Anulir tampil untuk gaji yang sudah dibayar");
        await hl.sorot(r.tid("payroll-paid-hint"));
        await r.shot("c-dibayar-tanpa-anulir", { locator: r.tid("payroll-run-detail") });
        await hl.lepas(r.tid("payroll-paid-hint"));
        return `${await r.text("payroll-paid-hint")} · ${await r.text("payroll-paid-info").catch(() => "")}`;
      });

    await r.step(22, "Manajer", "Login Manajer → buka proses yang sudah Dibayar; lalu Keuangan › Kas & Bank › Transaksi Kas → cari nomor kas bayar gaji",
      "Manajer juga tidak melihat Anulir pada proses Dibayar; kas bayar gaji bertuliskan \"Anulir lewat Proses Gaji\" (tidak bisa dianulir dari layar kas). Koreksi gaji yang sudah dibayar = masukan penyesuaian (boleh minus) di proses gaji berikutnya", async () => {
        await masukManajer(r);
        await bukaProses(run2.id);
        assert(!(await r.tid("payroll-void").count()), "Manajer melihat tombol Anulir untuk gaji Dibayar");
        const kasBayar = kas(run2.cash_txn_id || "__none__");
        assert(kasBayar, "kas bayar gaji tidak ditemukan");
        await kb.menu(r, "cash-management");
        await r.tid("cash-txn-search").fill(kasBayar.number);
        await r.tid(`cash-row-${kasBayar.id}`).waitFor({ timeout: 15000 });
        const note = await kb.teks(r, `void-cash-note-${kasBayar.id}`);
        assert(/^Anulir lewat Proses Gaji$/.test(note), `catatan kas gaji: ${note}`);
        assert(!(await r.tid(`void-cash-${kasBayar.id}`).count()), "tombol anulir kas gaji tampil");
        await kb.shotSorot(r, "c-kas-gaji-tanpa-anulir", r.tid(`void-cash-note-${kasBayar.id}`));
        // Server juga menolak anulir proses Dibayar (tanpa mengubah apa pun) — bukti aturan, bukan aksi pengguna.
        let tolak = "";
        try { await (await api("manager")).post(`/hr/payroll/runs/${run2.id}/void`, { reason: "uji aturan gaji dibayar" }, KSC); }
        catch (e) { tolak = `${e.status} ${JSON.stringify(e.detail).slice(0, 160)}`; }
        assert(/^409/.test(tolak), `anulir proses Dibayar tidak ditolak: ${tolak}`);
        return `kas ${kasBayar.number}: "${note}" · server: ${tolak}`;
      });
  }

  // ═══════════════════════════════ D. JURNAL UMUM SALAH AKUN + REKLAS AKUN SEMENTARA ═════════════════════════════
  if (BAGIAN.includes("D")) {
    const NOM = 1200000 + Number(NO) * 1000;      // contoh peserta 76: Rp 1.276.000
    const KET = `Sewa gudang tambahan November — Latihan ${NO}`;
    const SUSP = 150000 + Number(NO) * 500;        // contoh peserta 76: Rp 188.000
    const KET_SUSP = `Penjualan kardus bekas — Latihan ${NO}`;
    const TYPO = NOM - 9000;                       // salah ketik di jurnal koreksi: 1.276.000 → 1.267.000
    let je1 = null; let jeRev = null; let je2 = null; let jeTypo = null; let kasMasuk = null; let reklas = null;
    const bukaJurnal = async () => {
      await kb.menuJurnal(r);
      await r.tid("gl-journal-search").fill(`Latihan ${NO}`);
      await r.idle(800);
    };
    const jurnalManual = async (debit, kredit, nama, nominal = NOM) => {
      await r.tid("gl-new-journal").click();
      await r.tid("je-modal").waitFor();
      await r.tid("je-description").fill(KET);
      await bl.pilih(r, "je-line-account-0", debit, debit);
      await r.tid("je-line-debit-0").fill(String(nominal));
      await bl.pilih(r, "je-line-account-1", kredit, kredit);
      await r.tid("je-line-credit-1").fill(String(nominal));
      await r.idle(300);
      await hl.sorot(r.tid("je-submit"));
      await r.shot(nama, { locator: r.tid("je-modal") });
      await hl.lepas(r.tid("je-submit"));
      await r.tid("je-submit").click();
      await r.tid("je-modal").waitFor({ state: "detached", timeout: 20000 });
      return kb.tunggu(r, "gl-notice", /Jurnal manual/);
    };
    const manualTerbaru = () => mongo(`return db.journal_entries.find({entity_id:"${KSC}",source_type:"manual",description:${JSON.stringify(KET)},
      status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).toArray()`);

    await r.step(23, "Manajer", `Login Manajer (PT Sukacita) → Akuntansi & Pajak › Buku Besar › Jurnal → [[Jurnal Baru]] → *Keterangan* "${KET}" · baris 1 *Akun* 6-3000 Beban Utilitas (SALAH) *Debit* ${NOM.toLocaleString("id-ID")} · baris 2 *Akun* 2-1900 Kewajiban Lancar Lainnya *Kredit* ${NOM.toLocaleString("id-ID")} → [[Posting Jurnal]]`,
      "Pesan \"Jurnal manual berhasil diposting.\"; jurnal bersumber Manual, seimbang", async () => {
        await masukManajer(r);
        await kb.menuJurnal(r);
        const t = await jurnalManual("6-3000", "2-1900", "d-jurnal-salah-akun");
        je1 = manualTerbaru()[0];
        assert(je1, "jurnal manual tidak ditemukan");
        kb.seimbang([je1]);
        assert(kb.adaBaris(je1, "6-3000", "D", NOM) && kb.adaBaris(je1, "2-1900", "K", NOM), kb.teksJurnal(je1));
        return `${t} · ${kb.teksJurnal(je1)}`;
      });

    await r.step(24, "Manajer", `Ketik "Latihan ${NO}" di kotak cari → klik jurnal itu → [[Balik Jurnal]] → *Tanggal* hari ini · *Alasan* "Salah akun: sewa gudang tercatat di Beban Utilitas" → [[Buat Jurnal Pembalik]]`,
      "Rincian jurnal punya dua tombol: [[Anulir Jurnal]] (khusus jurnal manual) dan [[Balik Jurnal]]; form pembalik: tanggal wajib di periode terbuka, jurnal asli tidak diubah. Sesudahnya muncul jurnal Pembalik baru", async () => {
        await bukaJurnal();
        await r.tid(`gl-journal-row-${je1.id}`).click();
        await r.tid("gl-journal-detail").waitFor();
        await r.tid("gl-journal-void").waitFor();
        await hl.klikPotret(r, r.tid("gl-journal-reverse"), "d-tombol-balik-jurnal", { locator: r.tid("gl-journal-detail") });
        await r.tid("gl-reverse-form").waitFor();
        await r.tid("gl-reverse-reason").fill("Salah akun: sewa gudang tercatat di Beban Utilitas");
        await hl.sorot(r.tid("gl-reverse-submit"));
        await r.shot("d-form-pembalik", { locator: r.tid("gl-journal-detail") });
        await hl.lepas(r.tid("gl-reverse-submit"));
        await r.tid("gl-reverse-submit").click();
        await r.tid("gl-journal-detail").waitFor({ state: "detached", timeout: 20000 });
        jeRev = mongo(`return db.journal_entries.findOne({source_type:"reversal",source_id:"${je1.id}",status:{$ne:"void"}},{_id:0})`);
        assert(jeRev, "jurnal pembalik tidak terbentuk");
        return cermin(je1, jeRev);
      });

    await r.step(25, "Manajer", `[[Jurnal Baru]] koreksi, tetapi SALAH KETIK nominal: *Keterangan* sama · baris 1 *Akun* 6-2000 Beban Sewa *Debit* ${TYPO.toLocaleString("id-ID")} · baris 2 *Akun* 2-1900 *Kredit* ${TYPO.toLocaleString("id-ID")} → [[Posting Jurnal]]`,
      "Jurnal terposting; di daftar terlihat nominalnya tidak sama dengan jurnal yang dibalik (salah ketik, ketahuan hari itu juga)", async () => {
        await r.tid("gl-journal-search").fill("");
        const t = await jurnalManual("6-2000", "2-1900", "d-koreksi-salah-ketik", TYPO);
        jeTypo = manualTerbaru().find((j) => j.id !== je1.id);
        assert(jeTypo && kb.adaBaris(jeTypo, "6-2000", "D", TYPO), "jurnal koreksi salah ketik");
        return `${t} · ${kb.teksJurnal(jeTypo)}`;
      });

    await r.step(26, "Manajer", `Klik jurnal salah ketik itu → [[Anulir Jurnal]] → *Alasan anulir* "Salah ketik nominal, dicatat ulang" → [[Anulir Jurnal]]`,
      `Dialog meminta alasan dan menyebut nominal ${rp(TYPO)} & buku Sukacita ("tanpa jurnal pembalik"); jurnal berstatus Anulir, rincian bertuliskan "Dianulir oleh … · Salah ketik nominal, dicatat ulang"; tidak lagi dihitung di buku besar`, async () => {
        await bukaJurnal();
        await r.tid(`gl-journal-row-${jeTypo.id}`).click();
        await r.tid("gl-journal-detail").waitFor();
        await hl.klikPotret(r, r.tid("gl-journal-void"), "d-tombol-anulir-jurnal", { locator: r.tid("gl-journal-detail") });
        await r.tid("gl-void-confirm").waitFor();
        const pesan = await r.text("gl-void-confirm-message");
        assert(pesan.includes(rp(TYPO)) && /Sukacita/.test(pesan) && /tanpa jurnal pembalik/.test(pesan), `dialog: ${pesan}`);
        await r.tid("gl-void-confirm-reason").fill("Salah ketik nominal, dicatat ulang");
        await r.shot("d-alasan-anulir-jurnal", { locator: r.tid("gl-void-confirm").locator(".modal-card").first() });
        await r.tid("gl-void-confirm-confirm").click();
        await r.tid("gl-journal-detail").waitFor({ state: "detached", timeout: 20000 });
        const v = jurnalId(jeTypo.id);
        assert(v.status === "void" && v.void_reason === "Salah ketik nominal, dicatat ulang", `jurnal: ${v.status} ${v.void_reason}`);
        const a = jejak("journal_entry_voided", jeTypo.id);
        assert(a && a.role === "manager" && /Salah ketik/.test(a.alasan), `jejak: ${JSON.stringify(a)}`);
        await r.tid(`gl-journal-row-${jeTypo.id}`).click();
        await r.tid("gl-journal-detail").waitFor();
        const note = await kb.teks(r, "gl-journal-void-note");
        assert(/Dianulir oleh/.test(note) && /Salah ketik nominal/.test(note), `catatan anulir: ${note}`);
        assert(!(await r.tid("gl-journal-reverse").count()), "jurnal Anulir masih bisa dibalik");
        await hl.sorot(r.tid("gl-journal-void-note"));
        await r.shot("d-jurnal-dianulir", { locator: r.tid("gl-journal-detail") });
        await hl.lepas(r.tid("gl-journal-void-note"));
        await r.tid("gl-journal-detail-close").click();
        return `dialog "${pesan}" · ${note} · audit ${a.actor} "${a.alasan}"`;
      });

    await r.step(27, "Manajer", `[[Jurnal Baru]] koreksi yang benar: baris 1 *Akun* 6-2000 Beban Sewa *Debit* ${NOM.toLocaleString("id-ID")} · baris 2 *Akun* 2-1900 *Kredit* ${NOM.toLocaleString("id-ID")} → [[Posting Jurnal]]`,
      "Jurnal koreksi terposting. Cari nomor jurnal yang salah → tampil jurnal itu + jurnal Pembalik-nya (keterangan \"Pembalik KSC/JE-…: alasan\"); cari \"Latihan NN\" → jurnal salah, jurnal salah ketik (Anulir), jurnal koreksi", async () => {
        await r.tid("gl-journal-search").fill("");
        const t = await jurnalManual("6-2000", "2-1900", "d-jurnal-koreksi");
        je2 = manualTerbaru().find((j) => j.id !== je1.id);
        assert(je2 && je2.id !== jeTypo.id && kb.adaBaris(je2, "6-2000", "D", NOM) && kb.adaBaris(je2, "2-1900", "K", NOM), "jurnal koreksi");
        // Jurnal pembalik berketerangan "Pembalik <nomor asli>: <alasan>" — dicari dengan NOMOR jurnal asli, bukan keterangannya.
        await r.tid("gl-journal-search").fill(je1.number);
        await r.idle(800);
        for (const j of [je1, jeRev]) await r.tid(`gl-journal-row-${j.id}`).waitFor({ timeout: 15000 });
        await hl.sorot(r.tid("gl-journal-search"));
        await r.shot("d-asli-dan-pembalik");
        await hl.lepas(r.tid("gl-journal-search"));
        await bukaJurnal();
        for (const j of [je1, jeTypo, je2]) await r.tid(`gl-journal-row-${j.id}`).waitFor({ timeout: 15000 });
        assert(/Anulir/.test(await kb.isi(r.tid(`gl-journal-row-${jeTypo.id}`))), "baris jurnal salah ketik tidak berstatus Anulir");
        await r.shot("d-daftar-latihan");
        return `${t} · ${kb.teksJurnal(je2)} · cari "${je1.number}" → ${je1.number} + ${jeRev.number}; cari "Latihan ${NO}" → ${je1.number}, ${jeTypo.number} (Anulir), ${je2.number}`;
      });

    await r.step(28, "Finance", `Login Finance → Buku Besar › Jurnal → cari "Latihan ${NO}" → klik jurnal yang salah`,
      "Finance melihat semua jurnal itu; rincian jurnal salah bertuliskan \"Sudah dibalik oleh KSC/JE-… · <alasan>\"; jurnal yang sudah dibalik tidak bisa dibalik lagi", async () => {
        await s.masuk(r, me);
        await bukaJurnal();
        await r.kfin(r.tid("gl-new-journal"), "tombol Jurnal Baru");
        await r.tid(`gl-journal-row-${je1.id}`).click();
        await r.tid("gl-journal-detail").waitFor();
        const note = await kb.teks(r, "gl-journal-reversed-note");
        assert(note.includes(jeRev.number) && /Salah akun/.test(note), `catatan: ${note}`);
        await r.kfin(r.tid("gl-journal-reverse"), "tombol Balik pada jurnal yang sudah dibalik"); await r.kfin(r.tid("gl-journal-void"), "tombol Anulir pada jurnal yang sudah dibalik");
        await hl.sorot(r.tid("gl-journal-reversed-note"));
        await r.shot("d-finance-lihat-dibalik", { locator: r.tid("gl-journal-detail") });
        await hl.lepas(r.tid("gl-journal-reversed-note"));
        await r.tid("gl-journal-detail-close").click();
        return note;
      });

    await r.step(29, "Finance", "Cek buku: empat jurnal & jejak audit",
      `Jurnal salah ketik (Anulir) tidak dihitung; neto akun dari tiga jurnal lainnya: 6-3000 Beban Utilitas Rp 0 · 6-2000 Beban Sewa ${rp(NOM)} (D) · 2-1900 ${rp(NOM)} (K); jurnal asli tidak diubah (status Terposting, ditandai sudah dibalik); jejak audit pembalikan: Manajer + alasan`, async () => {
        const net = {};
        const hidup = mongo(`return db.journal_entries.find({id:{$in:${JSON.stringify([je1.id, jeRev.id, jeTypo.id, je2.id])}},
          status:{$ne:"void"}},{_id:0,id:1,lines:1}).toArray()`);
        assert(hidup.length === 3 && !hidup.some((j) => j.id === jeTypo.id), `jurnal terhitung: ${hidup.map((j) => j.id)}`);
        for (const j of hidup) for (const l of j.lines) net[l.account_code] = (net[l.account_code] || 0) + Number(l.debit || 0) - Number(l.credit || 0);
        assert(Math.abs(net["6-3000"] || 0) < 0.01 && Math.abs(net["6-2000"] - NOM) < 0.01 && Math.abs(net["2-1900"] + NOM) < 0.01, JSON.stringify(net));
        const asli = jurnalId(je1.id);
        assert(asli.status !== "void" && asli.reversed_by_entry_id === jeRev.id, `jurnal asli: ${asli.status} ${asli.reversed_by_entry_id}`);
        const a = jejak("journal_entry_reversed", je1.id);
        assert(a && a.role === "manager" && /Salah akun/.test(a.alasan), `jejak: ${JSON.stringify(a)}`);
        return `neto ${JSON.stringify(net)} · audit ${a.actor} ${a.timestamp.slice(0, 19)} "${a.alasan}"`;
      });

    await r.step(30, "Finance", `Keuangan › Kas & Bank › Transaksi Kas → [[Catat Transaksi]]: *Jenis Kas* Kas Besar / Bank · *Arah* Masuk · *Nominal* ${SUSP.toLocaleString("id-ID")} · *Kategori* Lain-lain · *Deskripsi* "${KET_SUSP}" → [[Catat Transaksi]]`,
      "Transaksi tercatat; jurnalnya 1-1100 Kas Besar / Bank (D) · 1-9999 Akun Sementara (K) — kas masuk \"Lain-lain\" belum punya akun pendapatan, jadi ditampung dulu", async () => {
        await kb.menu(r, "cash-management");
        await r.tid("create-cash-button").click();
        await r.tid("cash-form").waitFor();
        await kb.pilih(r, "cash-type-select", "kas_besar");
        await kb.pilih(r, "cash-direction-select", "in");
        await r.tid("cash-amount-input").fill(String(SUSP));
        await kb.pilih(r, "cash-category-select", "lain");
        await r.tid("cash-account-sole").waitFor().catch(() => {});
        await r.tid("cash-description-input").fill(KET_SUSP);
        await r.tid("submit-cash-button").click();
        const t = await kb.tunggu(r, "cash-notice", /Transaksi KSC\/CASH-\d+ \(masuk\) dicatat/);
        kasMasuk = kasNomor(t.match(/KSC\/CASH-\d+/)[0]);
        const je = kb.seimbang(kb.jurnal("cash_transaction", kasMasuk.id), "jurnal kas masuk");
        assert(kb.adaBaris(je, "1-1100", "D", SUSP) && kb.adaBaris(je, "1-9999", "K", SUSP), kb.teksJurnal(je));
        return `${t} · ${kb.teksJurnal(je)}`;
      });

    await r.step(31, "Manajer", "Login Manajer → Akuntansi & Pajak › Tutup Buku → buka seksi [[Akun sementara]]",
      "Bilah oranye \"Akun Suspense (1-9999): −Rp … · Belum nol — reklasifikasi ke akun yang benar sebelum tutup buku\"; daftar jurnal yang menyentuh 1-9999 memuat kas masuk peserta", async () => {
        await masukManajer(r);
        await bl.menu(r, "akuntansi", "closing");
        await r.tid("closing-view").waitFor();
        await r.tid("closing-section-akun-sementara-toggle").click();
        await r.tid("suspense-panel").waitFor({ timeout: 15000 });
        const jeKas = kb.jurnal("cash_transaction", kasMasuk.id)[0];
        await r.tid(`suspense-row-${jeKas.id}`).waitFor({ timeout: 15000 });
        const bal = await r.text("suspense-balance");
        const db0 = bl.saldoAkun(["1-9999"])["1-9999"] || 0;
        assert(bl.dekat(bl.uang(bal), db0), `saldo layar ${bal} ≠ buku ${db0}`);
        await hl.sorot(r.tid(`suspense-row-${jeKas.id}`));
        await r.shot("d-akun-sementara", { locator: r.tid("closing-section-akun-sementara") });
        await hl.lepas(r.tid(`suspense-row-${jeKas.id}`));
        return `saldo 1-9999 PT Sukacita ${bal} (buku ${rp(db0)}) · baris ${jeKas.number}`;
      });

    await r.step(32, "Manajer", `Isi Reklasifikasi: *Entitas* Sukacita · *Posisi Saldo* Kredit · *Nominal* ${SUSP.toLocaleString("id-ID")} (hanya transaksi ini — jangan saldo seluruhnya) · *Akun Tujuan* 4-9000 Pendapatan Lain-lain · *Catatan* "${KET_SUSP}" → [[Reklasifikasi]]`,
      `Pesan "Reklasifikasi suspense berhasil. Jurnal: KSC/JE-…"; saldo 1-9999 berkurang ${rp(SUSP)}`, async () => {
        const sebelum = bl.saldoAkun(["1-9999"])["1-9999"] || 0;
        await kb.pilih(r, "suspense-entity", KSC).catch(() => {});
        await kb.pilih(r, "suspense-side", "credit");
        await r.tid("suspense-amount").fill(String(SUSP));
        await bl.pilih(r, "suspense-target", "4-9000", "4-9000");
        await r.tid("suspense-note").fill(KET_SUSP);
        await hl.sorot(r.tid("suspense-submit"));
        await r.shot("d-form-reklas", { locator: r.tid("suspense-reclass-form") });
        await hl.lepas(r.tid("suspense-submit"));
        await r.tid("suspense-submit").click();
        const t = await kb.tunggu(r, "closing-notice", /Reklasifikasi suspense berhasil/, 20000);
        reklas = jurnalNomor(t.match(/KSC\/JE-\d+/)[0]);
        kb.seimbang([reklas]);
        assert(kb.adaBaris(reklas, "1-9999", "D", SUSP) && kb.adaBaris(reklas, "4-9000", "K", SUSP), kb.teksJurnal(reklas));
        const sesudah = bl.saldoAkun(["1-9999"])["1-9999"] || 0;
        assert(Math.abs(sesudah - sebelum - SUSP) < 0.01, `saldo 1-9999 ${sebelum} → ${sesudah}`);
        await r.tid(`suspense-row-${reklas.id}`).waitFor({ timeout: 15000 }).catch(() => {});
        await r.shot("d-reklas-selesai", { locator: r.tid("closing-section-akun-sementara") });
        return `${t} · ${kb.teksJurnal(reklas)} · saldo 1-9999 ${rp(sebelum)} → ${rp(sesudah)} (tanggal jurnal ${String(reklas.date).slice(0, 10)})`;
      });
  }

  // ═══════════════════════════════ E. TRANSAKSI KAS SALAH KATEGORI + REKONSILIASI ════════════════════════════════
  if (BAGIAN.includes("E")) {
    const NOM = 410000 + Number(NO) * 100;          // contoh peserta 76: Rp 417.600 (unik per peserta)
    const KET = `Ongkos ekspedisi kirim kain — S4 Latihan ${NO}`;
    const tgl = kb.hariIni();
    let bca = null; let kas1 = null; let kas2 = null; let baris = null;
    const catatKas = async (kategori, nama) => {
      await kb.menu(r, "cash-management");
      await r.tid("create-cash-button").click();
      await r.tid("cash-form").waitFor();
      await kb.pilih(r, "cash-type-select", "kas_besar");
      await kb.pilih(r, "cash-direction-select", "out");
      await r.tid("cash-amount-input").fill(String(NOM));
      await kb.pilih(r, "cash-category-select", kategori);
      await r.tid("cash-account-sole").waitFor().catch(() => {});
      await r.tid("cash-description-input").fill(KET);
      await sleep(300);
      await kb.shotSorot(r, nama, r.tid("cash-category-select"), { locator: r.tid("cash-form") });
      await r.tid("submit-cash-button").click();
      const t = await kb.tunggu(r, "cash-notice", /Transaksi KSC\/CASH-\d+ \(keluar\) dicatat/);
      return { t, txn: kasNomor(t.match(/KSC\/CASH-\d+/)[0]) };
    };
    const bukaRekon = async () => {
      await kb.menu(r, "bank-reconciliation");
      await kb.pilih(r, "recon-account-select", bca.id);
      await r.tid("recon-summary").waitFor();
      await r.tid("recon-lines-search").fill(`S4 LATIHAN ${NO}`);
      await r.idle(400);
    };
    const garisBank = () => mongo(`return db.bank_statement_lines.findOne({bank_account_id:"${bca.id}",description:{$regex:"S4 LATIHAN ${NO}$"}},{_id:0})`);
    const tautkan = async (txn, nama) => {
      await r.tid(`recon-matchbtn-${baris.id}`).click();
      await r.tid("recon-match-modal").waitFor();
      const cand = r.tid(`recon-cand-${txn.id}`);
      await cand.waitFor({ timeout: 15000 });
      const ct = await kb.isi(cand);
      await kb.shotSorot(r, nama, r.tid(`recon-pick-cand-${txn.id}`), { locator: r.tid("recon-match-modal") });
      await r.tid(`recon-pick-cand-${txn.id}`).click();
      const t = await kb.tunggu(r, "recon-notice", /Mutasi ditautkan/);
      await r.tid("recon-match-modal").waitFor({ state: "detached" });
      return `${t} · kandidat ${ct}`;
    };

    await r.step(33, "Finance", `Login Finance → Kas & Bank › Transaksi Kas → [[Catat Transaksi]]: Kas Besar / Bank · Keluar · *Nominal* ${NOM.toLocaleString("id-ID")} · *Kategori* Pembelian (SALAH — seharusnya Operasional) · *Deskripsi* "${KET}" → [[Catat Transaksi]]`,
      `Transaksi tercatat; jurnalnya 1-1300 Persediaan Barang (D) · 1-1100 Kas Besar / Bank (K) — ongkos kirim salah masuk nilai persediaan`, async () => {
        await s.masuk(r, me);
        bca = await kb.rekening(me, REK_BCA);
        const h = await catatKas("pembelian", "e-kas-kategori-salah");
        kas1 = h.txn;
        const je = kb.seimbang(kb.jurnal("cash_transaction", kas1.id), "jurnal kas");
        assert(kb.adaBaris(je, "1-1300", "D", NOM) && kb.adaBaris(je, "1-1100", "K", NOM), kb.teksJurnal(je));
        return `${h.t} · ${kb.teksJurnal(je)}`;
      });

    await r.step(34, "Finance", `Kas & Bank › Rekonsiliasi → rekening ${REK_BCA} → [[Impor mutasi bank]] → template BCA (CSV) → tempel baris rekening koran ongkos ekspedisi → [[Pratinjau]] → [[Impor]] → pada baris itu [[Cocokkan]] → [[Tautkan]] kandidat ${"KSC/CASH-…"}`,
      "Baris mutasi berstatus Tercocok dan tertaut ke kas yang salah kategori (kesalahan belum terlihat di rekonsiliasi — nominal sama)", async () => {
        const fmts = await (await api(me)).get("/bank-reconciliation/formats", KSC);
        const fBca = fmts.find((f) => f.bank_code === "bca" && (f.file_kind || "csv") === "csv");
        assert(fBca, "template BCA tidak ada");
        const TEKS = ["Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo",
          `${tgl.bca},TRSF E-BANKING DB EKSPEDISI S4 LATIHAN ${NO},0000,"${kb.nominalBca(NOM)}",DB,0`].join("\n");
        await kb.menu(r, "bank-reconciliation");
        await kb.pilih(r, "recon-account-select", bca.id);
        await r.tid("recon-summary").waitFor();
        await r.tid("recon-import-toggle").click();
        await r.tid("recon-import-panel").waitFor();
        await kb.pilih(r, "recon-format-select", fBca.id);
        await r.tid("recon-raw").fill(TEKS);
        await r.tid("recon-preview-btn").click();
        await kb.tunggu(r, "recon-preview", /Terbaca 1 baris/);
        await r.tid("recon-import-submit").click();
        const imp = await kb.tunggu(r, "recon-notice", /Impor BCA/);
        baris = garisBank();
        assert(baris && baris.status === "unmatched", `baris mutasi: ${JSON.stringify(baris && baris.status)}`);
        await r.tid("recon-lines-search").fill(`S4 LATIHAN ${NO}`);
        await r.idle(400);
        const t = await tautkan(kas1, "e-cocokkan-kas-salah");
        await kb.tunggu(r, `recon-status-${baris.id}`, /^Tercocok$/);
        assert(Math.abs(Number(kas(kas1.id).reconciled_amount || 0) - NOM) < 0.01, "kas belum terekonsiliasi");
        r.note(`Teks rekening koran S4 peserta ${NO}:\n${TEKS}`);
        return `${imp} · ${t}`;
      });

    await r.step(35, "Manajer", `Manajer memeriksa jurnal persediaan dan menemukan ongkos kirim di 1-1300. Login Manajer → Kas & Bank › Transaksi Kas → cari nomor kas → ikon [[Anulir]] → *Alasan* "Salah kategori: ongkos kirim bukan pembelian" → [[Anulir Transaksi]]`,
      "Ditolak dengan pesan merah \"Transaksi sudah dicocokkan dengan mutasi bank — lepaskan dulu.\"; kas tetap aktif", async () => {
        await masukManajer(r);
        await kb.menu(r, "cash-management");
        await r.tid("cash-besar-card").waitFor().catch(() => {});   // ringkasan selesai dimuat (memuat ulang menghapus pesan galat)
        await r.idle(800);
        await r.tid("cash-txn-search").fill(kas1.number);
        await r.tid(`void-cash-${kas1.id}`).waitFor({ timeout: 15000 });
        await r.tid(`void-cash-${kas1.id}`).click();
        await r.tid("cash-void-modal").waitFor();
        await r.tid("cash-void-modal-reason").fill("Salah kategori: ongkos kirim bukan pembelian");
        await r.tid("cash-void-modal-confirm").click();
        const err = await kb.tunggu(r, "cash-error", /dicocokkan dengan mutasi bank/);
        await r.tid("cash-error").first().evaluate((e) => { e.style.outline = "3px solid #DC2626"; e.style.outlineOffset = "2px"; },
          null, { timeout: 2000 }).catch(() => {});
        await r.shot("e-anulir-ditolak");
        assert(kas(kas1.id).status !== "void", "kas ter-anulir padahal sudah dicocokkan");
        return err;
      });

    await r.step(36, "Finance", "Login Finance → Kas & Bank › Rekonsiliasi → cari \"S4 LATIHAN NN\" → pada baris Tercocok klik [[Lepas]]",
      "Pesan \"Tautan dilepas.\"; baris kembali \"Perlu keputusan\"; kas kembali Belum direkonsiliasi", async () => {
        await s.masuk(r, me);
        await bukaRekon();
        await r.tid(`recon-unmatch-${baris.id}`).waitFor({ timeout: 15000 });
        await kb.shotSorot(r, "e-lepas-cocok", r.tid(`recon-unmatch-${baris.id}`), { locator: r.tid("recon-lines-table") });
        await r.tid(`recon-unmatch-${baris.id}`).click();
        const t = await kb.tunggu(r, "recon-notice", /Tautan dilepas/);
        await kb.tunggu(r, `recon-status-${baris.id}`, /Perlu keputusan/);
        assert(Number(kas(kas1.id).reconciled_amount || 0) < 0.01, "kas masih tercatat terekonsiliasi");
        return t;
      });

    await r.step(37, "Manajer", "Login Manajer → Transaksi Kas → cari nomor kas → [[Anulir]] → alasan → [[Anulir Transaksi]]",
      "Pesan \"Transaksi … dianulir.\"; baris hilang dari daftar transaksi kas aktif", async () => {
        await masukManajer(r);
        await kb.menu(r, "cash-management");
        await r.tid("cash-txn-search").fill(kas1.number);
        await r.tid(`void-cash-${kas1.id}`).waitFor({ timeout: 15000 });
        await r.tid(`void-cash-${kas1.id}`).click();
        await r.tid("cash-void-modal").waitFor();
        const pesan = await r.text("cash-void-modal-message");
        assert(pesan.includes(rp(NOM)) && /jurnal pembalik/.test(pesan), `dialog: ${pesan}`);
        await r.tid("cash-void-modal-reason").fill("Salah kategori: ongkos kirim bukan pembelian");
        await r.shot("e-alasan-anulir-kas", { locator: r.tid("cash-void-modal").locator(".modal-card").first() }).catch(() => r.shot("e-alasan-anulir-kas"));
        await r.tid("cash-void-modal-confirm").click();
        const t = await kb.tunggu(r, "cash-notice", /dianulir/);
        await r.tid(`cash-row-${kas1.id}`).waitFor({ state: "detached", timeout: 15000 });
        return `dialog "${pesan}" · ${t}`;
      });

    await r.step(38, "Manajer", "Cek buku: jurnal pembalik kas & jejak",
      `Jurnal pembalik hari ini: 1-1100 Kas Besar / Bank (D) · 1-1300 Persediaan Barang (K) ${rp(NOM)}; kas berstatus dianulir dengan alasan & nama Manajer; jejak audit tersimpan`, async () => {
        const c = kas(kas1.id);
        assert(c.status === "void" && /Salah kategori/.test(c.void_reason || "") && c.voided_by, `kas: ${c.status} ${c.void_reason} ${c.voided_by}`);
        const asli = mongo(`return db.journal_entries.findOne({source_type:"cash_transaction",source_id:"${c.id}"},{_id:0})`);
        const t = cermin(asli, jurnalId(c.void_journal_entry_id));
        const a = jejak("cash_transaction_voided", c.id);
        assert(a && a.role === "manager" && /Salah kategori/.test(a.alasan), `jejak: ${JSON.stringify(a)}`);
        return `${t} · ${c.number} void oleh ${c.voided_by} "${c.void_reason}" · audit ${a.timestamp.slice(0, 19)}`;
      });

    await r.step(39, "Finance", `Login Finance → catat ulang dengan kategori benar: Transaksi Kas → [[Catat Transaksi]] Kas Besar / Bank · Keluar · ${NOM.toLocaleString("id-ID")} · *Kategori* Operasional · deskripsi sama → [[Catat Transaksi]]`,
      `Jurnal 6-4000 Beban Operasional Lainnya (D) · 1-1100 Kas Besar / Bank (K) ${rp(NOM)}`, async () => {
        await s.masuk(r, me);
        const h = await catatKas("operasional", "e-kas-kategori-benar");
        kas2 = h.txn;
        const je = kb.seimbang(kb.jurnal("cash_transaction", kas2.id), "jurnal kas benar");
        assert(kb.adaBaris(je, "6-4000", "D", NOM) && kb.adaBaris(je, "1-1100", "K", NOM), kb.teksJurnal(je));
        return `${h.t} · ${kb.teksJurnal(je)}`;
      });

    await r.step(40, "Finance", "Rekonsiliasi → cari \"S4 LATIHAN NN\" → [[Cocokkan]] → [[Tautkan]] kandidat kas yang baru",
      "Kandidat hanya kas yang baru (kas yang dianulir tidak ditawarkan); baris Tercocok lagi", async () => {
        await bukaRekon();
        await r.tid(`recon-matchbtn-${baris.id}`).waitFor({ timeout: 15000 });
        const t = await tautkan(kas2, "e-cocokkan-ulang");
        assert(!(await r.tid(`recon-cand-${kas1.id}`).count()), "kas dianulir masih jadi kandidat");
        await kb.tunggu(r, `recon-status-${baris.id}`, /^Tercocok$/);
        baris = garisBank();
        assert((baris.allocations || []).some((x) => x.txn_id === kas2.id) && !(baris.allocations || []).some((x) => x.txn_id === kas1.id),
          `alokasi mutasi: ${JSON.stringify(baris.allocations)}`);
        await kb.sorot(r.tid(`recon-line-${baris.id}`));
        await r.shot("e-tercocok-ulang", { locator: r.tid("recon-lines-table") });
        await kb.lepas(r.tid(`recon-line-${baris.id}`));
        return t;
      });

    await r.step(41, "Finance", "Cek buku: neto empat jurnal kas",
      `1-1300 Persediaan neto Rp 0 · 6-4000 Beban Operasional ${rp(NOM)} (D) · 1-1100 Kas Besar / Bank ${rp(NOM)} (K) sekali saja — sama dengan mutasi bank`, async () => {
        const jes = mongo(`return db.journal_entries.find({source_id:{$in:["${kas1.id}","${kas2.id}"]},status:{$ne:"void"}},{_id:0,number:1,lines:1}).toArray()`);
        const net = {};
        for (const j of jes) for (const l of j.lines) net[l.account_code] = (net[l.account_code] || 0) + Number(l.debit || 0) - Number(l.credit || 0);
        assert(jes.length === 3, `jumlah jurnal ${jes.length}`);
        assert(Math.abs(net["1-1300"] || 0) < 0.01 && Math.abs(net["6-4000"] - NOM) < 0.01 && Math.abs(net["1-1100"] + NOM) < 0.01, JSON.stringify(net));
        assert(Math.abs(Number(kas(kas2.id).reconciled_amount || 0) - NOM) < 0.01, "kas baru belum terekonsiliasi");
        return `${jes.map((j) => j.number).join(", ")} · neto ${JSON.stringify(net)}`;
      });
  }

  await r.finish();
})();
