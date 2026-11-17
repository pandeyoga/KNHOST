// A3 — RETUR PENJUALAN ujung ke ujung (PT Sukacita), dijalankan LEWAT LAYAR dengan akun peran yang sama dengan peserta.
//
//   Retur 1 (SO pelunasan penuh, sudah dilunasi)  → kompensasi STORE CREDIT  → saldo dipakai Finance untuk SO kedua
//   Retur 2 (SO bayar sebagian, sudah dibayar saldo) → kompensasi PENGEMBALIAN DANA (refund tunai dari BCA)
//   Tiap retur: Sales ajukan → Manajer setujui → Sales catat barang dikembalikan → Gudang scan terima → Kepala Gudang
//   tugaskan SPK QC → QC periksa & tutup SPK → Manajer selesaikan per roll → Finance cek buku. Penutup: Jejak Dokumen.
//
//   KN_PESERTA=41 node docs/pelatihan/2026-11-18_keuangan/uji/e2e/A3_retur_penjualan.js
//   Data: backend/scripts/seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN (a_dasar: so_lunas & so_sebagian BELUM dibayar).
//   KN_LANJUT=1 → melanjutkan retur yang sudah ada untuk peserta itu (langkah yang sudah lewat dilewati; hanya untuk
//   menyusun skrip — uji resmi selalu pada peserta baru).
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("../lib");
const { bersihkanHasil } = require("../piutang_lib");
const R = require("./retur_lib");
const { alurRetur } = require("./retur_alur");

const KODE = "A3_retur_penjualan";
const LANJUT = process.env.KN_LANJUT === "1";

(async () => {
  bersihkanHasil(KODE);
  const r = await new Run(KODE, "A3 Retur penjualan: store credit dipakai untuk tagihan lain, lalu pengembalian dana").start();
  const no = peserta("41");
  const k = kartu(no);
  const soA = k["a_dasar:so_lunas"], soB = k["a_dasar:so_sebagian"];
  if (!soA || !soB) throw new Error(`Kartu peserta ${no} belum lengkap — jalankan seed_pelatihan_keuangan_kn.py --mulai ${no} --peserta ${no}`);
  const cust = mongo(`return db.customers.findOne({name:"Latihan ${no} · Toko Kain Peserta ${no}"},{_id:0,id:1,name:1})`);
  r.note(`Peserta ${no}: ${akunPeserta(no)} · pelanggan ${cust.name} · SO-A ${soA.so} (${rp(soA.total)}) · SO-B ${soB.so} (${rp(soB.total)})`);
  const ctx = { no, cust, ret: {} };

  // ── 0. Persiapan (bukan langkah peserta): pelanggan sudah melunasi SO-A lewat transfer (kwitansi Finance) ──────────
  await r.step("0", "Persiapan", `Pelanggan melunasi ${soA.so} lewat transfer (kwitansi dicatat akun Finance peserta lewat API — layar ini dilatih di F02)`,
    `${soA.so} lunas (sisa Rp 0)`, async (ulang) => {
      const sisa = R.sisaSo(soA.so_id);
      if (sisa > 0.009) {
        const fin = await api(akunPeserta(no));
        await fin.post("/ar-receipts", { customer_id: cust.id, amount: sisa, method: "transfer", entity_id: R.KSC,
          notes: `Pelunasan ${soA.so} sebelum retur (persiapan A3)`, reference_no: `TRF-LATIH${no}-A3`,
          allocations: [{ order_id: soA.so_id, amount: sisa }] }, R.KSC);
      }
      assert(R.sisaSo(soA.so_id) <= 0.009, `${soA.so} belum lunas`);
      return `${soA.so} dilunasi ${rp(sisa)}`;
    });

  // ── Bagian depan retur (sama untuk tiap retur) ───────────────────────────────────────────────────────────────────
  const { depan, selesaikan } = alurRetur(r, ctx, { lanjut: LANJUT });


  await depan("A", soA, { alasan: "Warna lebih tua dari sampel", sebab: /warna/i,
    catatan: "Pelanggan mengembalikan 1 roll — warna tidak sesuai sampel. Minta dijadikan saldo untuk pesanan berikutnya." });


  await selesaikan("A", soA, { value: "store_credit", label: "Store Credit", status: "credit_settled",
    bukti: "ACC Manajer: pelanggan minta nilai retur dijadikan saldo (WA 17/11)",
    hasil: "Retur 'Selesai: Store Credit'; panel 'Nota kredit' CN-… dengan lencana 'Jurnal Terbit'; pratinjau: SO asal sudah lunas — seluruh nilai 'Jadi saldo pelanggan'",
    buku: "Nota Kredit = DPP + PPN; jurnal: 4-1000 Pendapatan (D) · 2-1200 PPN Keluaran (D) / 2-1450 Saldo Kredit Pelanggan (K); 1-1300 Persediaan (D) / 5-1000 HPP (K); saldo pelanggan naik sebesar Nota Kredit" });

  await R.langkah(r, "A10", "Finance", "Akun Finance peserta → menu [[Retur]] → retur ini → panel 'Nota kredit' → klik lencana [[Jurnal Terbit]]",
    "Pop-up jurnal Nota Kredit: Pendapatan & PPN Keluaran di Debit, Saldo Kredit Pelanggan di Kredit; Persediaan (D) / HPP (K); Total Debit = Total Kredit", async (ulang) => {
      await r.login(akunPeserta(no));
      await R.bukaRetur(r, "returns", "A-finance-retur");
      await R.bukaDetailRetur(r, R.returById(ctx.ret.A.id));
      await r.tid("return-credit-note-section").waitFor();
      await R.klikPotret(r, r.tid("credit-note-journal"), "A-finance-lencana-jurnal");
      await r.tid("gl-journal-detail").waitFor({ timeout: 20000 });
      await r.idle(600);
      const t = (await r.tid("gl-journal-detail").innerText()).replace(/\s+/g, " ");
      assert(t.includes(ctx.jeA.number), `pop-up bukan jurnal ${ctx.jeA.number}: ${t.slice(0, 200)}`);
      await r.shot("A-finance-jurnal-nota-kredit");
      await r.tid("gl-journal-detail-close").click();
      await r.tid("gl-journal-detail").waitFor({ state: "detached", timeout: 10000 });
      return t.slice(0, 300);
    });

  await R.langkah(r, "A11", "Finance", `Keuangan › [[Piutang]] › tab [[Titipan & Saldo Kredit]] → cari pelanggan Latihan ${no} → buka barisnya → [[Pakai saldo]] → *Pesanan piutang tujuan* ${soB.so} → [[Maks]] → [[Pakai Saldo]]`,
    `Pesan hijau 'Berhasil dipakai Rp … (SCR-…)'; sisa tagihan ${soB.so} berkurang; saldo pelanggan berkurang sebesar yang dipakai`, async (ulang) => {
      const ada = mongo(`return db.store_credit_redemptions.findOne({customer_id:"${cust.id}","allocations.order_id":"${soB.so_id}",status:{$ne:"void"}},{_id:0,number:1,applied_amount:1})`);
      if (ulang && ada) { ctx.pakaiSaldo = { pakai: ada.applied_amount }; return `lewati (sudah ${ada.number} ${R.rpBuku(ada.applied_amount)})`; }
      const sisa0 = R.sisaSo(soB.so_id), saldo0 = R.saldoKredit(cust.id);
      const pakai = R.r2(Math.min(sisa0, saldo0));
      if (ulang) await r.login(akunPeserta(no));
      await R.menu(r, "keuangan", "ar-aging");
      await R.klikPotret(r, r.tid("hub-tab-customer-credit"), "A-finance-tab-saldo");
      await r.tid("customer-credit-view").waitFor();
      await r.tid("cc-search").fill(`Latihan ${no}`);
      await r.idle(800);
      await R.klikPotret(r, r.tid(`cc-toggle-${cust.id}`), "A-finance-buka-pelanggan");
      await R.klikPotret(r, r.tid(`cc-redeem-${cust.id}`), "A-finance-pakai-saldo");
      await r.tid("sc-redeem-modal").waitFor();
      await r.idle(800);
      await R.pilihRe(r, "sc-redeem-order", new RegExp(soB.so.replace(/[/]/g, "\\/")));
      await r.tid("sc-redeem-max").click();
      await R.sorot(r.tid("sc-redeem-amount"));
      await R.klikPotret(r, r.tid("sc-redeem-submit"), "A-finance-simpan-pakai-saldo");
      await r.tid("sc-redeem-ok").waitFor({ timeout: 20000 });
      const ok = await r.text("sc-redeem-ok");
      await r.shot("A-finance-saldo-terpakai");
      const sisa1 = R.sisaSo(soB.so_id), saldo1 = R.saldoKredit(cust.id);
      assert(Math.abs((sisa0 - sisa1) - pakai) < 0.02, `sisa ${soB.so}: ${sisa0} → ${sisa1}, harus turun ${pakai}`);
      assert(Math.abs((saldo0 - saldo1) - pakai) < 0.02, `saldo: ${saldo0} → ${saldo1}, harus turun ${pakai}`);
      const red = mongo(`return db.store_credit_redemptions.find({customer_id:"${cust.id}"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      const jr = R.jurnalDari([red.id]).concat(R.jurnalDari([red.number]))[0];
      const t = R.cekJurnal(jr, [["2-1450", "D", pakai], ["1-1200", "K", pakai]]);
      ctx.pakaiSaldo = { pakai, red, jr };
      return `${ok} · sisa ${soB.so} ${R.rpBuku(sisa1)} · saldo ${R.rpBuku(saldo1)} · ${t}`;
    });

  // ── Retur 2: SO-B (sudah dibayar dengan saldo) → Pengembalian Dana ─────────────────────────────────────────────────
  await depan("B", soB, { alasan: "Kain berlubang di beberapa titik", sebab: /sobek|lubang|cacat/i,
    catatan: "Pelanggan mengembalikan 1 roll dan minta uang dikembalikan (transfer)." });
  await selesaikan("B", soB, { value: "refund", label: "Pengembalian Dana", status: "refund_settled", kas: true,
    bukti: "ACC Manajer: pelanggan minta pengembalian dana via transfer (WA 17/11)",
    hasil: "Retur 'Selesai: Pengembalian Dana'; pratinjau 'Ke mana nilainya': potong sisa tagihan SO asal (bila masih ada) lalu 'Refund tunai ke pelanggan'; Nota Kredit CN-… + transaksi kas keluar",
    buku: "Jurnal: 4-1000 (D) · 2-1200 (D) / 1-1200 Piutang (K, bagian yang memotong tagihan) · 1-1100 Kas Besar / Bank (K, refund); 1-1300 (D) / 5-1000 (K); mutasi kas keluar BCA = refund" });

  await R.langkah(r, "B10", "Finance", "Akun Finance peserta → Keuangan › [[Kas & Bank]] › tab [[Transaksi Kas]] → cari 'Refund' atau nomor transaksi",
    "Baris kas keluar 'Refund tunai retur SRET-…/P1 → Latihan NN …', kategori Refund Retur Jual, rekening BCA, nominal = refund", async (ulang) => {
      const kt = ctx.kasB;
      assert(kt, "transaksi kas refund tidak ada");
      await r.login(akunPeserta(no));
      await R.menu(r, "keuangan", "cash-bank");
      await R.klikPotret(r, r.tid("hub-tab-cash-management"), "B-finance-tab-transaksi-kas");
      await r.tid("cash-txn-search").fill(kt.number);
      await r.idle(800);
      const row = r.tid(`cash-row-${kt.id}`);
      await row.waitFor({ timeout: 15000 });
      const t = (await row.innerText()).replace(/\s+/g, " ");
      await R.sorot(row);
      await r.shot("B-finance-kas-refund");
      await R.lepas(row);
      return t;
    });

  // ── Jejak Dokumen ─────────────────────────────────────────────────────────────────────────────────────────────────
  await R.langkah(r, "C1", "Finance", `Menu [[Pusat Dokumen]] › tab [[Jejak Dokumen]] → ketik ${soA.so} → klik hasilnya`,
    `Rantai: ${soA.so} → surat jalan → kwitansi pelunasan; retur ${ctx.ret.A && ctx.ret.A.number} → Nota Kredit; jurnal`, async (ulang) => {
      if (ulang) await r.login(akunPeserta(no));
      await R.menu(r, "alat", "document-center");
      await R.klikPotret(r, r.tid("hub-tab-doc-trace"), "C-finance-tab-jejak");
      await r.tid("doc-trace-view").waitFor();
      await r.tid("trace-search-input").fill(soA.so);
      await r.tid(`trace-result-${soA.so_id}`).click();
      await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
      await r.tid("trace-graph").waitFor();
      await r.idle(1200);
      const g = (await r.text("trace-graph"));
      const harus = [soA.so, ctx.ret.A.number, ctx.cnA.number];
      const hilang = harus.filter((x) => !g.includes(x));
      await r.shot("C-jejak-so-a", { full: true });
      assert(!hilang.length, `jejak ${soA.so} tidak memuat: ${hilang.join(", ")}`);
      return `${(await r.text("trace-kpis"))} · ${g.slice(0, 300)}`;
    });

  await r.finish();
})().catch((e) => { console.error(e); process.exit(1); });
