// S5 — Hutang & Piutang per Pihak (situasi khusus, modul 5).
//
// Permintaan pemilik: hutang/piutang tidak hanya per PO/SO, tetapi per pihak — klik satu pemasok/pelanggan → semua
// hutang/piutangnya → langsung dibayar/diterima dari situ.
//   A. Hutang per Pemasok (Keuangan › Hutang › Hutang per Pemasok): cari pemasok peserta → rincian → centang dua tagihan →
//      [Bayar terpilih] → satu form, satu konfirmasi (total, pemasok, rekening, PT) → tiap tagihan dibayar lewat pintu
//      bayar yang sama dengan form satu tagihan → buku: per tagihan satu kas keluar + jurnal 2-1100 (D) / 1-1100 (K), sisa 0.
//      Unduh rekap hutang per pemasok (CSV).
//   B. Piutang per Pelanggan (Keuangan › Piutang › Saldo & Umur): pelanggan peserta → rincian → Rekening koran (+ Cetak PDF)
//      → Manajer mencatat janji bayar (izin `order.update`) → Finance [Terima pembayaran] untuk DUA SO sekaligus ("Atur
//      sendiri") → buku: satu kwitansi, satu jurnal 1-1100 (D) / 1-1200 (K), sisa kedua SO 0, rekening koran saldo akhir 0.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/situasi/S5_per_pihak.js         (bawaan peserta 91)
//   KN_PESERTA=92 KN_BAGIAN=A node …                                            (hanya bagian A)
// Data peserta: `seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN` (dua tagihan pemasok terposting + dua SO terkirim).
// Peserta yang sudah dipakai tidak bisa diulang (tagihan & SO-nya sudah dibayar).
const fs = require("fs");
const { Run, api, assert, rp, num, kartu, peserta, akunPeserta, mongo, sleep } = require("../lib");
const hl = require("../hutang_lib");
const kb = require("../kasbank_lib");
const pl = require("../piutang_lib");
const s = require("../sdm/sdm_lib");
const bk = require("../buku_lib");

const NO = peserta("91");
const BAGIAN = (process.env.KN_BAGIAN || "AB").toUpperCase();
const KSC = "ent_ksc";
const REK_BCA = "BCA Operasional KSC";
const r2 = (n) => Math.round(Number(n) * 100) / 100;
const angka = (n) => rp(n).replace("Rp ", "");
const isi = async (loc) => (await loc.first().innerText()).replace(/\s+/g, " ").trim();
const tagihan = (id) => mongo(`return db.vendor_bills.findOne({id:${JSON.stringify(id)}},{_id:0})`);

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

/** Keuangan › Piutang › Saldo & Umur → cari pelanggan peserta → baris pelanggan. */
async function barisPelanggan(r, cust, nama = "") {
  await pl.bukaMenu(r, "ar-aging", "ar-aging", { nama });
  await r.tid("ar-aging-view").waitFor();
  await r.tid("ar-aging-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
  const row = r.tid(`ar-aging-row-${cust.id}`);
  await row.waitFor({ timeout: 20000 });
  await r.idle(500);
  return row;
}

async function bukaRincianPelanggan(r, cust, so) {
  const row = await barisPelanggan(r, cust);
  await row.click();
  await r.tid("ar-aging-detail-modal").waitFor({ timeout: 15000 });
  await r.tid(`ar-detail-row-${so}`).waitFor({ timeout: 20000 });
  await r.idle(600);
}

(async () => {
  const r = await new Run("S5", "Hutang & Piutang per Pihak").start();
  bk.bersihkanGambar(r);
  const me = akunPeserta(NO);
  const k = kartu(NO);
  const FIN = (await api(me)).user.name;
  r.note(`Peserta ${NO} (${me}, ${FIN}) · bagian ${BAGIAN}`);
  const ctx = {};

  // ═══════════════════════════════════════ A. HUTANG PER PEMASOK ═══════════════════════════════════════════════════
  if (BAGIAN.includes("A")) {
    const t1 = k["a_dasar:tagihan_bayar"];
    const t2 = k["a_dasar:tagihan_kontrabon"];
    const sup = mongo(`return db.suppliers.findOne({name:"Latihan ${NO} · Pemasok Grey Peserta ${NO}"},{_id:0,id:1,name:1})`);
    const ids = [t1 && t1.tagihan_id, t2 && t2.tagihan_id];
    const total = r2(Number(t1 && t1.total) + Number(t2 && t2.total));
    ctx.A = { sup, ids, total };

    await r.step(1, "Finance", `Masuk dengan akun Finance Anda. Buka Keuangan › Hutang, lalu tab [[Hutang per Pemasok]]`,
      "Satu baris per pemasok: kolom umur (Belum jatuh tempo, 1–30, 31–60, 61–90, > 90 hari), Sisa hutang, Jatuh tempo terdekat, Potongan; kartu angka Total hutang · Lewat jatuh tempo · Lewat lebih dari 60 hari · Potongan belum dipakai", async () => {
        assert(sup && sup.id, `pemasok Latihan ${NO} tidak ada — jalankan seed peserta`);
        for (const id of ids) {
          const b = tagihan(id);
          assert(b && b.status === "posted" && Number(b.amount_paid || 0) < 0.01, `tagihan ${id} bukan Terposting belum dibayar — pakai peserta segar`);
        }
        await s.masuk(r, me);
        await pl.bukaMenu(r, "accounts-payable", "ap-by-supplier", { nama: "a-menu" });
        await r.tid("ap-party-view").waitFor();
        await r.tid("ap-party-table").waitFor({ timeout: 20000 });
        await r.idle(600);
        const tot = await r.text("ap-party-kpi-total");
        return `kartu Total hutang: ${tot}`;
      });

    await r.step(2, "Finance", `Ketik "Latihan ${NO}" di kotak cari`,
      `Baris "Latihan ${NO} · Pemasok Grey Peserta ${NO}": PT Sukacita · 2 tagihan, Sisa hutang ${rp(total)} (contoh), umur Belum jatuh tempo`, async () => {
        await r.tid("ap-party-search").fill(`Latihan ${NO}`);
        const row = r.tid(`ap-party-row-${sup.id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(400);
        const t = await isi(row);
        assert(t.includes(angka(total)) && /2 tagihan/.test(t), `baris pemasok: ${t}`);
        const j = await (await api(me)).get(`/vendor-bills/payables/by-supplier?entity_id=${KSC}`, KSC);
        const b = j.rows.find((x) => x.supplier_id === sup.id);
        assert(b && Math.abs(b.outstanding - total) < 0.01 && b.bill_count === 2, `server: ${JSON.stringify(b)}`);
        await bk.potret(r, "a-baris-pemasok", [row, r.tid(`ap-party-total-${sup.id}`)]);
        return `${t}`;
      });

    await r.step(3, "Finance", "Klik [[Rincian & bayar]] di baris pemasok",
      `Jendela rincian: nama pemasok (tautan kartu), PT Sukacita, kartu Sisa hutang ${rp(total)} · Lewat jatuh tempo · Bisa dibayar langsung · Lewat kontrabon; tabel dua tagihan (nomor tagihan, faktur pemasok, PO, jatuh tempo, umur, sisa) dengan kotak centang & [[Bayar]]; bagian Kontrabon terbuka dan Potongan belum dipakai`, async () => {
        await hl.klikPotret(r, r.tid(`ap-party-open-${sup.id}`), "a-tombol-rincian");
        await r.tid("ap-supplier-detail").waitFor();
        for (const id of ids) await r.tid(`ap-detail-bill-${id}`).waitFor({ timeout: 15000 });
        await r.idle(500);
        const t = await r.text("ap-detail-total");
        assert(t.includes(angka(total)), `kartu sisa: ${t}`);
        assert(await r.tid("ap-detail-contra-bons").count(), "bagian kontrabon tidak tampil");
        await bk.potret(r, "a-rincian-pemasok", [r.tid("ap-detail-metrics")], { locator: r.tid("ap-supplier-detail") });
        return `${t} · ${await r.text("ap-detail-toolbar-count")}`;
      });

    await r.step(4, "Finance", "Centang kotak di kepala tabel (pilih semua tagihan yang bisa dibayar langsung), lalu klik [[Bayar terpilih]]",
      `Tombol berubah menjadi "Bayar terpilih (2) · ${rp(total)}"; form "Bayar beberapa tagihan" terbuka: PT Sukacita, Rekening sumber, Tanggal bayar, Cara bayar, Catatan, dan tabel nominal per tagihan yang terisi sisa`, async () => {
        await r.tid("ap-detail-check-all").check();
        await r.idle(300);
        const b = await r.text("ap-detail-pay-many");
        assert(/\(2\)/.test(b) && b.includes(angka(total)), `tombol: ${b}`);
        await hl.klikPotret(r, r.tid("ap-detail-pay-many"), "a-bayar-terpilih", { locator: r.tid("ap-supplier-detail") });
        await r.tid("pay-many-modal").waitFor();
        for (const id of ids) await r.tid(`pay-many-amount-${id}`).waitFor();
        return b;
      });

    await r.step(5, "Finance", `Pilih *Rekening sumber* ${REK_BCA}. *Cara bayar* Transfer. *Catatan* "TRF-S5-LATIH${NO}". Periksa nominal tiap tagihan`,
      `Nominal = sisa tiap tagihan (${rp(t1.total)} dan ${rp(t2.total)}, contoh); Total dibayar ${rp(total)}; tombol [[Bayar 2 tagihan · ${rp(total)}]] aktif`, async () => {
        await r.page.waitForFunction(() => !!document.querySelector('[data-testid="pay-many-account"]'), null, { timeout: 15000 });
        await sleep(800);
        await hl.pilih(r, "pay-many-account", REK_BCA);
        await r.tid("pay-many-notes").fill(`TRF-S5-LATIH${NO}`);
        for (const [id, n] of [[t1.tagihan_id, t1.total], [t2.tagihan_id, t2.total]]) {
          assert(Math.abs(num(await r.tid(`pay-many-amount-${id}`).inputValue()) - n) < 0.01, `nominal ${id} ≠ sisa`);
        }
        const tot = await r.text("pay-many-total");
        assert(tot.includes(angka(total)), `total: ${tot}`);
        const btn = await r.text("pay-many-submit");
        assert(!(await r.tid("pay-many-submit").isDisabled()), `tombol mati: ${btn}`);
        await bk.potret(r, "a-form-bayar-banyak", [r.tid("pay-many-account"), r.tid("pay-many-total")], { locator: r.tid("pay-many-modal") });
        return `${tot} · ${btn}`;
      });

    await r.step(6, "Finance", "Klik [[Bayar 2 tagihan]], baca konfirmasi, lalu klik [[Ya, bayar]]",
      `Konfirmasi: "Bayar 2 tagihan senilai ${rp(total)} ke Latihan ${NO} · Pemasok Grey Peserta ${NO} dari ${REK_BCA} … untuk Sukacita? Tiap tagihan dicatat sebagai pembayaran sendiri …"; hasil per tagihan "Lunas", ringkasan "2 tagihan dibayar, total ${rp(total)}"`, async () => {
        await r.tid("pay-many-submit").click();
        await r.tid("pay-many-confirm").waitFor();
        const msg = await r.text("pay-many-confirm-message");
        assert(msg.includes(angka(total)) && msg.includes(REK_BCA) && msg.includes("Sukacita") && msg.includes(`Peserta ${NO}`), `konfirmasi: ${msg}`);
        await r.shot("a-konfirmasi", { locator: r.tid("pay-many-confirm") });
        await hl.setuju(r, "pay-many-confirm");
        await r.tid("pay-many-results").waitFor({ timeout: 60000 });
        await hl.tungguTeks(r, "pay-many-summary", /2 tagihan dibayar/, 30000);
        for (const id of ids) assert(/Lunas/.test(await r.text(`pay-many-result-${id}`)), `hasil ${id}`);
        await bk.potret(r, "a-hasil-bayar", [r.tid("pay-many-summary")], { locator: r.tid("pay-many-modal") });
        return `${msg} → ${await r.text("pay-many-summary")}`;
      });

    await r.step(7, "Finance", "Cek buku: tiap tagihan satu pembayaran, satu kas keluar, satu jurnal",
      `Per tagihan: 2-1100 Hutang Usaha (D) · 1-1100 Kas Besar / Bank (K) sebesar nominalnya (${rp(t1.total)} dan ${rp(t2.total)}, contoh); kedua tagihan Lunas, sisa Rp 0; kas keluar dari ${REK_BCA}`, async () => {
        const bca = hl.rekening(REK_BCA);
        const out = [];
        for (const [id, n] of [[t1.tagihan_id, t1.total], [t2.tagihan_id, t2.total]]) {
          const b = tagihan(id);
          const pays = (b.payments || []).filter((p) => !p.voided);
          assert(b.status === "paid" && pays.length === 1 && Math.abs(Number(b.amount_paid) - n) < 0.01, `${b.bill_number}: ${b.status} · ${pays.length} bayar`);
          const kas = mongo(`return db.cash_transactions.find({ref_type:"vendor_bill",ref_id:"${id}",status:{$ne:"void"}},{_id:0}).toArray()`);
          assert(kas.length === 1 && kas[0].account_id === bca.id && Math.abs(kas[0].amount - n) < 0.01, `kas ${b.bill_number}: ${kas.length}`);
          const je = kb.seimbang(kb.jurnal("cash_transaction", kas[0].id), `jurnal ${b.bill_number}`);
          assert(kb.adaBaris(je, "2-1100", "D", n) && kb.adaBaris(je, "1-1100", "K", n), kb.teksJurnal(je));
          out.push(`${b.bill_number} ${kas[0].number} ${kb.teksJurnal(je)}`);
        }
        ctx.A.jurnal = out;
        return out.join(" | ");
      });

    await r.step(8, "Finance", "Tutup form ([[Tutup]]). Baca rincian pemasok dan daftar Hutang per Pemasok",
      "Rincian: \"Tidak ada tagihan terbuka.\", Sisa hutang Rp 0; daftar: pemasok peserta tidak muncul lagi (hutangnya lunas)", async () => {
        await r.tid("pay-many-close").click();
        await r.tid("pay-many-modal").waitFor({ state: "detached", timeout: 15000 });
        await r.tid("ap-detail-empty").waitFor({ timeout: 20000 });
        const t = await r.text("ap-detail-total");
        assert(/Rp\s?0\b/.test(t), `sisa sesudah bayar: ${t}`);
        await bk.potret(r, "a-rincian-lunas", [r.tid("ap-detail-notice"), r.tid("ap-detail-empty")], { locator: r.tid("ap-supplier-detail") });
        await r.tid("ap-detail-close").click();
        await r.idle(800);
        assert(!(await r.tid(`ap-party-row-${sup.id}`).count()), "pemasok masih di daftar");
        return `${t} · ${await r.text("ap-detail-notice").catch(() => "")}`.trim();
      });

    await r.step(9, "Finance", "Hapus kata cari. Klik [[Unduh]] di bilah daftar",
      "Berkas CSV \"hutang-per-pemasok_semua_….csv\" terunduh: kolom Pemasok; PT; Tagihan terbuka; umur; Sisa hutang; Jatuh tempo terdekat; Uang muka; Nota debit (dibuka di Excel)", async () => {
        await r.tid("ap-party-search").fill("");
        await r.idle(500);
        const [dl] = await Promise.all([r.page.waitForEvent("download", { timeout: 15000 }),
          hl.klikPotret(r, r.tid("ap-party-download"), "a-unduh")]);
        const f = await dl.path();
        const txt = fs.readFileSync(f, "utf8");
        assert(/^﻿?Pemasok;PT;Tagihan terbuka;/.test(txt), `kepala CSV: ${txt.slice(0, 80)}`);
        assert(!txt.includes(`Peserta ${NO};`), "pemasok peserta (sudah lunas) masih di rekap");
        return `${dl.suggestedFilename()} · ${txt.split(/\r?\n/).length - 1} baris`;
      });
  }

  // ═══════════════════════════════════════ B. PIUTANG PER PELANGGAN ════════════════════════════════════════════════
  if (BAGIAN.includes("B")) {
    const a = k["a_dasar:so_lunas"];
    const b = k["a_dasar:so_sebagian"];
    const cust = pl.pelangganPeserta(NO);
    const total = r2(Number(a && a.total) + Number(b && b.total));
    ctx.B = { cust, total };
    const n0 = 9;

    await r.step(n0 + 1, "Finance", `Buka Keuangan › Piutang › tab [[Saldo & Umur]]. Ketik "Latihan ${NO} · Toko Kain Peserta" di kotak cari`,
      `Baris pelanggan "Latihan ${NO} · Toko Kain Peserta ${NO}": Belum Lunas ${rp(total)} (contoh, dua SO terkirim), kolom umur Belum jatuh tempo, tombol [[Terima]]`, async () => {
        assert(cust && a && b, "pelanggan/SO peserta tidak ada — jalankan seed peserta");
        for (const so of [a.so_id, b.so_id]) assert(pl.sisaSo(so) > 1, `SO ${so} sudah lunas — pakai peserta segar`);
        if (!BAGIAN.includes("A")) await s.masuk(r, me);
        const row = await barisPelanggan(r, cust, "b-menu");
        const t = await isi(row);
        assert(t.includes(angka(total)), `baris pelanggan: ${t} (harap ${rp(total)})`);
        await bk.potret(r, "b-baris-pelanggan", [row]);
        return t;
      });

    await r.step(n0 + 2, "Finance", "Klik baris pelanggan",
      `Rincian piutang: dua pesanan (${a.so} dan ${b.so}, contoh) dengan jatuh tempo, umur, sisa; tombol kepala [[Rekening koran]] dan [[Terima pembayaran]]; per pesanan [[Bayar]]`, async () => {
        await r.tid(`ar-aging-row-${cust.id}`).click();
        await r.tid("ar-aging-detail-modal").waitFor({ timeout: 15000 });
        for (const so of [a.so_id, b.so_id]) await r.tid(`ar-detail-row-${so}`).waitFor({ timeout: 20000 });
        await r.idle(600);
        assert(await r.tid("ar-aging-statement").count(), "tombol Rekening koran tidak tampil");
        await bk.potret(r, "b-rincian-pelanggan", [r.tid("ar-aging-statement"), r.tid("ar-aging-pay")], { locator: r.tid("ar-aging-detail") });
        return await r.text("ar-aging-detail-summary");
      });

    await r.step(n0 + 3, "Finance", "Klik [[Rekening koran]]",
      `Bagian Rekening koran terbuka di rincian: Dari (tanggal 1 bulan ini) – Sampai (hari ini), baris Saldo awal, surat jalan (Tagihan), Saldo akhir = piutang tercatat ${rp(total)} (contoh); tombol [[Cetak PDF]] dan [[Salin pengingat]] bila izin ada`, async () => {
        await hl.klikPotret(r, r.tid("ar-aging-statement"), "b-tombol-rekening-koran", { locator: r.tid("ar-aging-detail") });
        await r.tid("customer-statement-table").waitFor({ timeout: 20000 });
        await r.idle(600);
        const akhir = await r.text("customer-statement-table-closing");
        const st = await (await api(me)).get(`/customers/${cust.id}/statement?entity_id=${KSC}`, KSC);
        assert(Math.abs(Number(st.closing_balance) - total) < 0.01 || akhir.includes(angka(st.closing_balance)), `saldo akhir ${st.closing_balance}`);
        assert(akhir.includes(angka(st.closing_balance)), `layar saldo akhir: ${akhir}`);
        ctx.B.saldoAwalRk = st.closing_balance;
        await bk.potret(r, "b-rekening-koran", [r.tid("customer-statement-table-closing"), r.tid("customer-statement-pdf")], { locator: r.tid("ar-aging-statement-panel") });
        return `${akhir} · server saldo akhir ${rp(st.closing_balance)}`;
      });

    await r.step(n0 + 4, "Finance", "Klik [[Cetak PDF]]",
      "Berkas \"rekening-koran-….pdf\" terunduh (berkop PT); pesan \"PDF rekening koran sudah diunduh.\"", async () => {
        const [dl] = await Promise.all([r.page.waitForEvent("download", { timeout: 60000 }), r.tid("customer-statement-pdf").click()]);
        const f = await dl.path();
        const head = fs.readFileSync(f).slice(0, 5).toString();
        assert(head === "%PDF-", `bukan PDF: ${head}`);
        await hl.tungguTeks(r, "customer-statement-notice", /PDF rekening koran/);
        // Nama berkas = kode/nama pelanggan tanpa tanda baca (dulu nama ber-"·" membuat berkas tersimpan "download").
        assert(/^rekening-koran-[a-z0-9-]+\.pdf$/.test(dl.suggestedFilename()), `nama berkas: ${dl.suggestedFilename()}`);
        await bk.potret(r, "b-pdf-terunduh", [r.tid("customer-statement-notice")], { locator: r.tid("ar-aging-statement-panel") });
        return `${dl.suggestedFilename()} · ${fs.statSync(f).size} byte`;
      });

    await r.step(n0 + 5, "Manajer", `Pelanggan menjanjikan transfer. Masuk sebagai Manajer (manager@), PT Sukacita. Buka Saldo & Umur, cari pelanggan, klik barisnya. Pada ${b.so} klik [[Janji bayar]]`,
      "Form \"Tindak Lanjut Penagihan\": Catatan, Hasil, (bila \"Dijanjikan bayar\") Tanggal janji & Nominal janji", async () => {
        await s.masuk(r, "manager");
        await pilihPT(r);
        await bukaRincianPelanggan(r, cust, b.so_id);
        const btn = r.tid(`ar-aging-promise-${b.so_id}`);
        await btn.waitFor({ timeout: 10000 });
        await hl.klikPotret(r, btn, "b-tombol-janji", { locator: r.tid("ar-aging-detail") });
        await r.tid("worklist-followup-modal").waitFor();
        return "form tindak lanjut terbuka";
      });

    await r.step(n0 + 6, "Manajer", `Isi *Catatan* "Janji transfer 2 SO — S5 latihan ${NO}", *Hasil* Dijanjikan bayar, *Tanggal janji* hari ini, *Nominal janji* ${rp(total)}. Klik [[Simpan]]`,
      "Pesan \"Tindak lanjut untuk … dicatat.\" di rincian; janji tercatat di kartu pelanggan › Tindak Lanjut", async () => {
        await r.tid("worklist-followup-note").fill(`Janji transfer 2 SO — S5 latihan ${NO}`);
        await hl.pilih(r, "worklist-followup-outcome", "Dijanjikan bayar");
        await r.tid("worklist-followup-promise-date").waitFor();
        await s.pilihTanggal(r, "worklist-followup-promise-date", kb.hariIni().iso);
        await r.tid("worklist-followup-promise-amount").fill(String(total));
        await bk.potret(r, "b-form-janji", [r.tid("worklist-followup-outcome")], { locator: r.tid("worklist-followup-modal") });
        await r.tid("worklist-followup-submit").click();
        await hl.tungguTeks(r, "ar-aging-followup-notice", /dicatat/);
        const fu = mongo(`return db.collection_followups.find({customer_id:"${cust.id}",order_id:"${b.so_id}"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
        assert(fu && fu.outcome === "promised" && Math.abs(Number(fu.promise_amount) - total) < 0.01, `janji: ${JSON.stringify(fu).slice(0, 200)}`);
        await bk.potret(r, "b-janji-tercatat", [r.tid("ar-aging-followup-notice")], { locator: r.tid("ar-aging-detail") });
        return `${await r.text("ar-aging-followup-notice")} · janji ${fu.promise_date} ${rp(fu.promise_amount)} oleh ${fu.created_by}`;
      });

    await r.step(n0 + 7, "Finance", "Transfer pelanggan masuk. Masuk lagi dengan akun Finance, buka rincian pelanggan (Saldo & Umur → klik baris), klik [[Terima pembayaran]]",
      "Form \"Terima pembayaran\": PT Sukacita, pelanggan terisi, daftar tagihan terbuka kedua SO, pilihan alokasi Tertua dulu / Atur sendiri", async () => {
        await s.masuk(r, me);
        await bukaRincianPelanggan(r, cust, a.so_id);
        await hl.klikPotret(r, r.tid("ar-aging-pay"), "b-tombol-terima", { locator: r.tid("ar-aging-detail") });
        await r.tid("ar-receipt-modal").waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'), null, { timeout: 90000 });
        await r.idle(800);
        return await r.text("ar-receipt-customer-name");
      });

    await r.step(n0 + 8, "Finance", `Klik [[Atur sendiri]]. Isi alokasi ${a.so} = ${rp(a.total)} dan ${b.so} = ${rp(b.total)} (sisa masing-masing, contoh). *Rekening penerima* ${REK_BCA}, *No. referensi* "TRF-S5-PLG-LATIH${NO}"`,
      `Nominal diterima = jumlah alokasi ${rp(total)}; tidak ada petunjuk selisih`, async () => {
        await r.tid("ar-receipt-mode-manual").click();
        await r.idle(400);
        await r.tid(`ar-receipt-alloc-${a.so_id}`).fill(String(a.total));
        await r.tid(`ar-receipt-alloc-${b.so_id}`).fill(String(b.total));
        const acc = r.tid("ar-receipt-account");
        if (await acc.count()) {
          const cur = await isi(acc);
          if (!cur.includes(REK_BCA)) await hl.pilih(r, "ar-receipt-account", REK_BCA);
        }
        await r.tid("ar-receipt-reference").fill(`TRF-S5-PLG-LATIH${NO}`);
        await r.idle(600);
        const tot = await r.text("ar-receipt-total");
        assert(tot.includes(angka(total)), `total form: ${tot}`);
        await bk.potret(r, "b-form-terima", [r.tid("ar-receipt-mode-manual"), r.tid(`ar-receipt-alloc-${a.so_id}`), r.tid(`ar-receipt-alloc-${b.so_id}`), r.tid("ar-receipt-total")], { locator: r.tid("ar-receipt-modal") });
        return tot;
      });

    await r.step(n0 + 9, "Finance", "Klik [[Simpan kwitansi]], baca konfirmasi, klik [[Ya, simpan]]",
      `Konfirmasi "Catat penerimaan ${rp(total)} dari Latihan ${NO} · Toko Kain Peserta ${NO} ke ${REK_BCA} … untuk Sukacita?"; pesan kwitansi di rincian; kedua SO hilang dari rincian ("Tidak ada pesanan terbuka.")`, async () => {
        await r.tid("ar-receipt-submit").click();
        await r.tid("ar-receipt-confirm").waitFor({ timeout: 20000 });
        const msg = await r.text("ar-receipt-confirm-message");
        assert(msg.includes(angka(total)) && msg.includes("Sukacita"), `konfirmasi: ${msg}`);
        await r.shot("b-konfirmasi-terima", { locator: r.tid("ar-receipt-confirm") });
        await hl.setuju(r, "ar-receipt-confirm");
        await r.tid("ar-receipt-modal").waitFor({ state: "detached", timeout: 60000 });
        const note = await hl.tungguTeks(r, "ar-aging-detail-notice", /Kwitansi|dicatat/i, 30000);
        await r.tid("ar-aging-detail-empty").waitFor({ timeout: 30000 });
        await bk.potret(r, "b-rincian-lunas", [r.tid("ar-aging-detail-notice"), r.tid("ar-aging-detail-empty")], { locator: r.tid("ar-aging-detail") });
        return `${msg} → ${note}`;
      });

    await r.step(n0 + 10, "Finance", "Cek buku: satu kwitansi dengan dua alokasi, satu kas masuk, satu jurnal",
      `1-1100 Kas Besar / Bank (D) ${rp(total)} · 1-1200 Piutang Usaha (K) ${rp(total)} (contoh); sisa ${a.so} dan ${b.so} Rp 0`, async () => {
        const rc = mongo(`return db.ar_receipts.find({customer_id:"${cust.id}",reference_no:"TRF-S5-PLG-LATIH${NO}",status:{$ne:"void"}},{_id:0}).toArray()`);
        assert(rc.length === 1, `kwitansi ${rc.length}`);
        const al = Object.fromEntries((rc[0].allocations || []).map((x) => [x.order_id, r2(x.applied ?? x.amount)]));
        assert(Math.abs(al[a.so_id] - a.total) < 0.01 && Math.abs(al[b.so_id] - b.total) < 0.01, `alokasi ${JSON.stringify(al)}`);
        const je = pl.jurnalKwitansi(rc[0]);
        pl.cekJurnalSeimbang(je, [["1-1100", "D", total], ["1-1200", "K", total]]);
        for (const so of [a.so_id, b.so_id]) assert(pl.sisaSo(so) <= 0.01, `sisa ${so} = ${pl.sisaSo(so)}`);
        ctx.B.rc = rc[0]; ctx.B.je = je;
        return `${rc[0].number} · ${kb.teksJurnal(je)}`;
      });

    await r.step(n0 + 11, "Finance", "Klik [[Rekening koran]] lagi di rincian pelanggan",
      `Baris baru kwitansi ${"(Pembayaran / Kredit)"} ${rp(total)}; Saldo akhir Rp 0`, async () => {
        const btn = r.tid("ar-aging-statement");
        if (!(await r.tid("ar-aging-statement-panel").count())) await btn.click();
        await r.tid("customer-statement-show").click();
        await r.idle(1200);
        await hl.tungguTeks(r, "customer-statement-table-closing", /Rp\s?0\b/, 20000);
        const akhir = await r.text("customer-statement-table-closing");
        await bk.potret(r, "b-rekening-koran-lunas", [r.tid("customer-statement-table-closing")], { locator: r.tid("ar-aging-statement-panel") });
        return akhir;
      });
  }

  await r.finish();
})().catch(async (e) => { console.error(e); process.exitCode = 1; });
