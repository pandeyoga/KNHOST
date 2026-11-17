// A3 — RETUR PENJUALAN dengan kompensasi BARANG PENGGANTI (tukar barang), PT Sukacita, lewat LAYAR.
//
//   SO pelunasan penuh (sudah dilunasi) → retur 1 roll → … → Manajer selesaikan per roll "Tukar Barang" (Nota Kredit →
//   saldo khusus pengganti) → Admin Sales membuat pesanan pengganti dari panel retur (saldo retur dipakai, ditagih Rp 0)
//   → cek buku (saldo dipakai: Saldo Kredit Pelanggan D / Uang Muka Pelanggan K — pesanan pengganti belum dikirim, jadi
//   piutangnya belum lahir; uang muka direklas ke Piutang saat surat jalannya terbit). Pengiriman pesanan pengganti
//   mengikuti alur pesanan biasa (A1: periksa & lepas → ambil → surat jalan) dan tidak diulang di sini.
//   Uji adversarial O1 (18 Nov): dulu jurnalnya 2-1450 D / 1-1200 K → piutang buku besar lebih kecil dari buku pembantu
//   ("Selisih" di Saldo & Umur sebesar saldo dipakai).
//
//   KN_PESERTA=45 node docs/pelatihan/2026-11-18_keuangan/uji/e2e/A3_retur_tukar.js
//   Data: seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN (a_dasar:so_lunas BELUM dibayar; SO kedua tidak dipakai).
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("../lib");
const { bersihkanHasil } = require("../piutang_lib");
const R = require("./retur_lib");
const { alurRetur } = require("./retur_alur");

const KODE = "A3_retur_tukar";

(async () => {
  bersihkanHasil(KODE);
  const r = await new Run(KODE, "A3 Retur penjualan: tukar barang sampai pesanan pengganti").start();
  const no = peserta("45");
  const k = kartu(no);
  const so = k["a_dasar:so_lunas"];
  if (!so) throw new Error(`Kartu peserta ${no} belum lengkap — jalankan seed_pelatihan_keuangan_kn.py --mulai ${no} --peserta ${no}`);
  const cust = mongo(`return db.customers.findOne({name:"Latihan ${no} · Toko Kain Peserta ${no}"},{_id:0,id:1,name:1})`);
  r.note(`Peserta ${no}: pelanggan ${cust.name} · SO ${so.so} (${rp(so.total)})`);
  const ctx = { no, cust, ret: {} };
  const { depan, selesaikan } = alurRetur(r, ctx, { lanjut: process.env.KN_LANJUT === "1" });

  await r.step("0", "Persiapan", `Pelanggan melunasi ${so.so} lewat transfer (kwitansi dicatat akun Finance peserta lewat API — dilatih di F02)`,
    `${so.so} lunas`, async () => {
      const sisa = R.sisaSo(so.so_id);
      if (sisa > 0.009) {
        await (await api(akunPeserta(no))).post("/ar-receipts", { customer_id: cust.id, amount: sisa, method: "transfer",
          entity_id: R.KSC, notes: `Pelunasan ${so.so} sebelum retur tukar (persiapan A3)`, reference_no: `TRF-LATIH${no}-A3T`,
          allocations: [{ order_id: so.so_id, amount: sisa }] }, R.KSC);
      }
      assert(R.sisaSo(so.so_id) <= 0.009, `${so.so} belum lunas`);
      return `${so.so} dilunasi ${rp(sisa)}`;
    });

  await depan("T", so, { alasan: "Noda minyak di beberapa titik", sebab: /noda|kotor/i,
    catatan: "Pelanggan minta kain diganti dengan kain yang sama (tukar barang)." });
  await selesaikan("T", so, { value: "exchange", label: "Tukar Barang", status: "credit_settled",
    bukti: "ACC Manajer: tukar barang sama artikel & warna (WA 17/11)",
    hasil: "Retur 'Selesai: Store Credit' bertipe Penggantian; Nota Kredit CN-…; pratinjau: 'Jadi saldo pelanggan (termasuk saldo tukar barang)'",
    buku: "Jurnal sama dengan Store Credit: 4-1000 (D) · 2-1200 (D) / 2-1450 Saldo Kredit Pelanggan (K); 1-1300 (D) / 5-1000 (K)" });

  let pengganti = null;
  await r.step("T10", "Admin Sales", "salesadmin@ → Retur › Retur Pelanggan → retur ini → tab [[Kebijakan & keputusan]] → panel 'Pesanan pengganti': *Pengganti (yd)* = kewajiban → [[Buat pesanan pengganti]]",
    "Ringkasan: 'Pesanan pengganti KSC/SO-… · Nilai pengganti Rp … · saldo retur dipakai Rp … · ditagih Rp 0'", async () => {
      const ret0 = R.returById(ctx.ret.T.id);
      const saldo0 = R.saldoKredit(cust.id);
      await r.login("salesadmin");
      await R.bukaRetur(r, "returns");
      await R.bukaDetailRetur(r, ret0);
      await R.klikPotret(r, r.tid("return-tab-keputusan"), "T-adminsales-tab-keputusan");
      await r.tid("return-replacement-panel").waitFor({ timeout: 15000 });
      await R.sorot(r.tid("replacement-obligation-table"));
      await r.shot("T-adminsales-kewajiban-pengganti");
      await R.klikPotret(r, r.tid("replacement-create"), "T-adminsales-buat-pengganti");
      await r.tid("replacement-summary").waitFor({ timeout: 30000 });
      await r.idle(800);
      const teks = (await r.text("replacement-summary"));
      await R.sorot(r.tid("replacement-summary"));
      await r.shot("T-adminsales-pengganti-terbit");
      const ret = R.returById(ctx.ret.T.id);
      pengganti = R.soDoc(ret.replacement_order_id);
      assert(pengganti, "pesanan pengganti tidak tercatat di retur");
      const s = ret.replacement_summary || {};
      const saldo1 = R.saldoKredit(cust.id);
      assert(Math.abs((saldo0 - saldo1) - Number(s.credit_applied || 0)) < 0.02, `saldo ${saldo0} → ${saldo1}, dipakai ${s.credit_applied}`);
      assert(Math.abs(R.sisaSo(pengganti.id) - Number(s.to_bill || 0)) < 0.02, `sisa tagihan pengganti ${R.sisaSo(pengganti.id)} ≠ ditagih ${s.to_bill}`);
      return `${teks} · SO pengganti ${pengganti.number} total ${R.rpBuku(pengganti.grand_total)} · saldo ${R.rpBuku(saldo0)} → ${R.rpBuku(saldo1)}`;
    });

  await r.step("T11", "Sistem", "Cek buku: saldo retur dipakai untuk pesanan pengganti",
    "Jurnal pemakaian saldo: 2-1450 Saldo Kredit Pelanggan (D) / 2-1400 Uang Muka Pelanggan (K) sebesar saldo dipakai — pesanan pengganti belum dikirim, jadi tidak ada baris 1-1200 Piutang; pembayaran di pesanan bertanda uang muka (direklas ke piutang saat surat jalannya terbit)", async () => {
      const ret = R.returById(ctx.ret.T.id);
      const s = ret.replacement_summary || {};
      const red = mongo(`return db.store_credit_redemptions.find({customer_id:"${cust.id}"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      assert(red, "catatan pemakaian saldo tidak ada");
      const je = R.jurnalDari([red.id, red.number, ret.replacement_order_id]).find((j) => (j.lines || []).some((l) => l.account_code === "2-1450"));
      assert(je, "jurnal pemakaian saldo tidak ada");
      const so = R.soDoc(ret.replacement_order_id);
      assert(!["shipped", "partially_shipped", "done"].includes(so.status), `pesanan pengganti sudah dikirim (${so.status})`);
      // O1 — pesanan belum dikirim: tidak boleh mengkredit piutang (dulu 1-1200 K → "Selisih" di Saldo & Umur)
      assert(!(je.lines || []).some((l) => l.account_code === "1-1200"), `jurnal ${je.number} masih mengkredit 1-1200 Piutang`);
      const bayar = (so.payments || []).filter((p) => p.receipt_id === red.id);
      assert(bayar.length && bayar.every((p) => p.gl_bucket === "advance"), `baris bayar ${red.number} belum bertanda uang muka`);
      const rek = (await (await api(akunPeserta(no))).get(`/ar/aging?entity_id=${R.KSC}`, R.KSC)).reconciliation || {};
      return `${R.cekJurnal(je, [["2-1450", "D", Number(s.credit_applied)], ["2-1400", "K", Number(s.credit_applied)]])}`
        + ` · ${so.number} status ${so.status}, baris bayar ${red.number} bertanda uang muka`
        + ` · Saldo & Umur KSC: piutang tercatat ${R.rpBuku(rek.ar_ledger_total)}, saldo akun ${R.rpBuku(rek.gl_balance)}, selisih ${R.rpBuku(rek.difference)} (seluruh PT, bukan hanya peserta ini)`;
    });

  await r.finish();
})().catch((e) => { console.error(e); process.exit(1); });
