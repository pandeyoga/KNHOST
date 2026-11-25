// F13 — Faktur Pajak Keluaran: terbitkan dari Meja Finance, isi NSFP resmi di Akuntansi & Pajak › Pajak › Faktur Keluaran.
// Pesanan = SO terkirim peserta (`a_dasar:so_lunas`). Menerbitkan faktur TIDAK mengubah piutang/pembayaran SO (jurnal PPN
// keluaran sudah terbit saat barang dikirim), jadi aman dikerjakan sebelum/sesudah skenario pelunasan F02.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F13_faktur_pajak.js        (bawaan peserta 04; KN_PESERTA=43 …)
const { Run, assert, rp, num, kartu, peserta, akunPeserta, mongo } = require("./lib");
const { tungguTeks, tungguToast, toastLoc, menu, sorot, lepas } = require("./hutang_lib");

/** NSFP latihan unik per peserta (16 digit): 010 026 1118 0000 NN → mis. peserta 04 = 0100261118000004. */
const nsfpLatihan = (no) => `01002611180000${no}`;

(async () => {
  const no = peserta("04");
  const k = kartu(no);
  const so = k["a_dasar:so_lunas"];
  const r = await new Run("F13", "Faktur Pajak Keluaran").start();
  if (!so) { r.note(`Kartu peserta ${no} belum punya a_dasar:so_lunas`); await r.finish(); return; }
  const order = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,number:1,status:1,customer_name:1,ppn_amount:1,dpp:1,grand_total:1,net_subtotal:1,payment_status:1})`);
  const ada = mongo(`return db.tax_invoices.findOne({order_id:"${so.so_id}",status:{$nin:["batal","diganti"]}},{_id:0,number:1})`);
  r.note(`Peserta ${no} · ${order.number} · ${order.customer_name} · total ${rp(order.grand_total)} · PPN ${rp(order.ppn_amount)} · faktur sebelumnya: ${ada ? ada.number : "belum ada"}`);
  const nsfp = nsfpLatihan(no);
  let fkt = null;

  await r.step(1, "Finance", "Login akun Finance peserta → Meja Finance (Beranda). Pada kartu [[Faktur pajak perlu terbit]] ketik nomor SO di kotak cari", "Baris SO peserta tampil dengan nama pelanggan, PPN, nilai = total SO, tombol [[Terbitkan]]", async () => {
    await r.login(akunPeserta(no));
    await r.tid("finance-desk").waitFor();
    const kartuFp = r.tid("fin-desk-queue-faktur_pajak");
    await kartuFp.waitFor({ timeout: 20000 });
    await r.tid("fin-desk-search-faktur_pajak").fill(order.number);
    const row = r.tid(`fin-desk-faktur_pajak-row-${so.so_id}`);
    await row.waitFor();
    await row.scrollIntoViewIfNeeded();
    const t = (await row.innerText()).replace(/\s+/g, " ");
    assert(t.includes(order.customer_name), `baris tanpa pelanggan: ${t}`);
    assert(num(await r.text(`fin-desk-faktur_pajak-value-${so.so_id}`)) === Math.round(order.grand_total), "nilai baris ≠ total SO");
    await sorot(r.tid(`fin-desk-faktur_pajak-action-${so.so_id}`));
    await r.shot("meja-faktur-perlu-terbit", { locator: kartuFp });
    await lepas(r.tid(`fin-desk-faktur_pajak-action-${so.so_id}`));
    return t;
  });

  await r.step(2, "Finance", "Klik [[Terbitkan]] pada baris SO itu", "Toast hijau \"Faktur Pajak FKT-… diterbitkan untuk KSC/SO-…\"; baris hilang dari kartu", async () => {
    // Meja gelombang 1 — [Terbitkan] aksi DI TEMPAT (`issue_tax`): langsung jalan; hasilnya toast (bukan bilah di puncak).
    await r.tid(`fin-desk-faktur_pajak-action-${so.so_id}`).click();
    const msg = await tungguToast(r, /diterbitkan/, 20000);
    fkt = mongo(`return db.tax_invoices.findOne({order_id:"${so.so_id}",status:"normal"},{_id:0})`);
    assert(fkt, "faktur tidak tersimpan");
    assert(msg.includes(fkt.number) && msg.includes(order.number), `pesan: ${msg}`);
    await r.idle(800);
    assert(await r.tid(`fin-desk-faktur_pajak-row-${so.so_id}`).count() === 0, "baris SO masih ada di kartu");
    await sorot(toastLoc(r, /diterbitkan/));
    await r.shot("faktur-terbit");
    await lepas(toastLoc(r, /diterbitkan/));
    return `${msg} · kode ${fkt.kode_transaksi} · DPP nilai lain ${rp(fkt.dpp)} · PPN ${rp(fkt.ppn_amount)}`;
  });

  await r.step(3, "Finance", "Buka Akuntansi & Pajak › Pajak (tab Faktur Keluaran), cari nomor SO", "Baris FKT-… status Normal, NSFP \"belum diisi\", DPP · PPN · Total sama dengan SO; lencana \"Data pajak belum lengkap\" (pelanggan latihan tanpa NPWP/NIK)", async () => {
    await menu(r, "akuntansi", "tax-hub");
    await r.tid("tax-invoices-view").waitFor();
    await r.tid("fkt-search").fill(order.number);
    const row = r.tid(`fkt-row-${fkt.id}`);
    await row.waitFor();
    const t = (await row.innerText()).replace(/\s+/g, " ");
    assert(t.includes(fkt.number) && /Normal/.test(t), `baris: ${t}`);
    assert(/belum diisi/.test(await r.text(`fkt-nsfp-text-${fkt.id}`)), "NSFP tidak 'belum diisi'");
    assert(num(await r.text(`fkt-ppn-${fkt.id}`)) === Math.round(order.ppn_amount), "PPN faktur ≠ PPN SO");
    assert(num(await r.text(`fkt-total-${fkt.id}`)) === Math.round(order.grand_total), "Total faktur ≠ total SO");
    await sorot(r.tid(`fkt-nsfp-${fkt.id}`));
    await r.shot("faktur-keluaran");
    await lepas(r.tid(`fkt-nsfp-${fkt.id}`));
    return t.slice(0, 260);
  });

  await r.step(4, "Finance", `Klik ikon [[#]] (Isi NSFP resmi) → *Nomor Seri Faktur Pajak*: ${nsfp} · *Kode Transaksi*: biarkan → [[Konfirmasi]]`, "Pop-up tertutup; kolom NSFP berisi nomor yang diketik", async () => {
    await r.tid(`fkt-nsfp-${fkt.id}`).click();
    await r.tid("fkt-modal").waitFor();
    await r.tid("fkt-nsfp-input").fill(nsfp);
    await sorot(r.tid("fkt-modal-submit"));
    await r.shot("isi-nsfp");
    await r.tid("fkt-modal-submit").click();
    await r.tid("fkt-modal").waitFor({ state: "detached", timeout: 15000 });
    await tungguTeks(r, `fkt-nsfp-text-${fkt.id}`, new RegExp(nsfp));
    const doc = mongo(`return db.tax_invoices.findOne({id:"${fkt.id}"},{_id:0,nsfp:1,nsfp_key:1,kode_transaksi:1,status:1})`);
    assert(doc.nsfp === nsfp && doc.nsfp_key === nsfp, `DB nsfp ${doc.nsfp}/${doc.nsfp_key}`);
    await sorot(r.tid(`fkt-nsfp-text-${fkt.id}`));
    await sorot(r.tid(`fkt-detail-${fkt.id}`));
    await r.shot("nsfp-terisi");
    await lepas(r.tid(`fkt-nsfp-text-${fkt.id}`));
    await lepas(r.tid(`fkt-detail-${fkt.id}`));
    return `NSFP ${doc.nsfp} · kode ${doc.kode_transaksi} · status ${doc.status}`;
  });

  await r.step(5, "Finance", "Klik ikon [[i]] (Rincian faktur & aturan pajak)", "Rincian: aturan pajak yang dipakai (tarif 12%, DPP nilai lain 11/12) dan data pembeli — daftar yang belum lengkap", async () => {
    await r.tid(`fkt-detail-${fkt.id}`).click();
    await r.tid("fkt-detail-rules").waitFor();
    const rules = await r.text("fkt-detail-rules");
    const buyer = await r.text("fkt-detail-buyer");
    await r.shot("rincian-faktur");
    await r.tid("fkt-detail-close").click();
    return `${rules.slice(0, 200)} | ${buyer.slice(0, 160)}`;
  });

  await r.step(6, "Finance", "Cek buku: faktur pajak tidak membuat jurnal; PPN keluaran sudah dijurnal saat pengiriman", "Σ kredit akun PPN Keluaran pada jurnal pengiriman SO = PPN faktur; piutang & status bayar SO tidak berubah", async () => {
    const jeFkt = mongo(`return db.journal_entries.countDocuments({source_id:"${fkt.id}"})`);
    assert(jeFkt === 0, `faktur pajak punya ${jeFkt} jurnal`);
    // Jurnal pengakuan penjualan per surat jalan (`shipment_revenue`, sumber = id surat jalan pesanan ini).
    const ships = mongo(`const sids=db.shipments.find({order_id:"${so.so_id}"},{_id:0,id:1}).toArray().map(x=>x.id);
      return db.journal_entries.find({status:{$ne:"void"},source_type:"shipment_revenue",source_id:{$in:sids}},{_id:0,number:1,source_type:1,lines:1}).toArray()`);
    const ppnLines = ships.flatMap((j) => (j.lines || []).filter((l) => /PPN Keluaran/i.test(l.account_name || "")).map((l) => ({ j: j.number, k: Number(l.credit || 0) - Number(l.debit || 0), code: l.account_code })));
    const ppnGl = ppnLines.reduce((s, x) => s + x.k, 0);
    const after = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,payment_status:1,status:1})`);
    assert(after.payment_status === order.payment_status, `status bayar SO berubah ${order.payment_status} → ${after.payment_status}`);
    assert(ppnLines.length, "jurnal pengakuan penjualan (PPN keluaran) SO tidak ditemukan");
    assert(Math.abs(ppnGl - Number(fkt.ppn_amount)) < 1, `PPN keluaran buku ${ppnGl} ≠ faktur ${fkt.ppn_amount}`);
    return `jurnal faktur: 0 · PPN keluaran di buku ${ppnLines.map((x) => `${x.j} ${x.code} PPN Keluaran K ${Math.round(x.k)}`).join(", ")} · SO ${after.status}/${after.payment_status}`;
  });

  await r.finish();
})();
