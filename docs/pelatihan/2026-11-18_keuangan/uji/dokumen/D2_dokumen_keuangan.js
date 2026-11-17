// D2 — Dokumen KEUANGAN yang dicetak peserta: Kwitansi (titipan, transfer, pelunasan), Tagihan Supplier, Tanda Terima
// Kontrabon, Faktur Pajak, Pesanan Pembelian, Rekening Koran pelanggan, Slip Gaji (cetak server, PDF), lalu Form
// Pengajuan Dana (PD), Tanda Terima pencairan, LPJ, Bukti Kas Keluar/Masuk (cetak di PERAMBAN lewat tombol layar —
// jendela cetak disimpan sebagai PDF A4). Isi dicocokkan dengan database, format diperiksa (lihat dokumen_lib.cekFormat).
//
//   KN_PESERTA=81 node docs/pelatihan/2026-11-18_keuangan/uji/dokumen/D2_dokumen_keuangan.js
const fs = require("fs");
const { Run, api, kartu, peserta, akunPeserta, mongo } = require("../lib");
const dk = require("./dokumen_lib");
const kb = require("../kasbank_lib");

const NO = peserta("81");
const one = (js) => mongo(js);

(async () => {
  const k = kartu(NO);
  const r = await new Run("D2", `Dokumen keuangan peserta ${NO} — isi & format`).start();
  const sesi = await api(akunPeserta(NO));
  const admin = await api("admin");
  const pt = dk.profilPt(mongo, "ent_ksc");
  const kop = [pt.nama, pt.npwp && `NPWP ${pt.npwp}`];
  const ringkas = {};

  const cekPdf = async (no, role, judul, nama, unduh, harus, extra, opsi = {}) => r.step(no, role, judul,
    "PDF A4 · kop PT · nomor/pihak/nominal = database · terbilang = nominal (termasuk sen) · tanpa label Inggris", async () => {
      const d = dk.simpan(r, nama, await unduh());
      const masalah = [...dk.cekFormat(d, opsi), ...dk.hilang(d, [...(opsi.tanpaKop ? [] : kop), ...harus])
        .map((h) => `tidak tercetak: "${h}"`)];
      if (extra) masalah.push(...(extra(d) || []));
      ringkas[nama] = masalah.length ? masalah : "lulus";
      dk.wajib(masalah, nama);
      return `${d.halaman} hlm · ${d.png.join(", ")}`;
    });
  const tbSama = (n) => (d) => {
    const t = dk.terbilangTercetak(d.text);
    return t === dk.terbilang(n) ? [] : [`terbilang "${t}" ≠ "${dk.terbilang(n)}"`];
  };

  // ── 1. Kwitansi (AR) ────────────────────────────────────────────────────────────────────────────────────────────
  const kw = [k["c_kas:titipan_sales"] && k["c_kas:titipan_sales"].kwitansi, k["c_kas:kwitansi_transfer"] && k["c_kas:kwitansi_transfer"].kwitansi,
    k["e_buku:so_jejak"] && k["e_buku:so_jejak"].kwitansi].filter(Boolean);
  for (const [i, nomor] of kw.entries()) {
    const rc = one(`return db.ar_receipts.findOne({number:${JSON.stringify(nomor)}},{_id:0})`);
    const so = (rc.allocations || []).map((a) => a.invoice_number || a.order_number).filter(Boolean);
    await cekPdf(`1.${i + 1}`, "Finance", `Kwitansi ${nomor} (${rc.payment_method_code || rc.method})`, `kwitansi-${nomor.slice(-5)}`,
      () => dk.unduhApi(sesi, `/pdf/render/ar_receipt/${rc.id}?format=pdf`),
      ["Kwitansi", nomor, rc.customer_name, `Jumlah Diterima ${dk.rpCetak(rc.amount)}`, `Total Diterima ${dk.rpCetak(rc.amount)}`, ...so,
        rc.reference_no && `No. referensi ${rc.reference_no}`], tbSama(rc.amount));
  }

  // ── 2. Tagihan Supplier & Kontrabon & PO ──────────────────────────────────────────────────────────────────────
  for (const [i, key] of [["2.1", "a_dasar:tagihan_bayar"], ["2.2", "a_dasar:tagihan_kontrabon"]]) {
    if (!k[key]) continue;
    const vb = one(`return db.vendor_bills.findOne({id:${JSON.stringify(k[key].tagihan_id)}},{_id:0})`);
    const base = Math.round((vb.grand_total - vb.ppn_amount) * 100) / 100;
    // Sisa = total − terbayar − selisih ditutup (rumus layar Hutang); field tersimpan `outstanding` bisa tertinggal.
    const sisa = Math.max(0, Math.round((vb.grand_total - (vb.amount_paid || 0) - (vb.ap_variance_closed || 0)) * 100) / 100);
    if (Math.abs(sisa - Number(vb.outstanding)) > 0.01) r.note(`${vb.bill_number}: field tersimpan outstanding ${vb.outstanding} / payment_status ${vb.payment_status} tidak ikut diperbarui saat dilunasi (status ${vb.status}); cetakan memakai rumus terbayar → sisa ${sisa}`);
    await cekPdf(i, "Finance", `Tagihan Supplier ${vb.bill_number} (${vb.status})`, `tagihan-${vb.bill_number}`,
      () => dk.unduhApi(sesi, `/pdf/render/vendor_bill/${vb.id}?format=pdf`),
      ["Tagihan Supplier", vb.bill_number, vb.supplier_name, vb.supplier_invoice_no, `Ref PO ${vb.po_number}`,
        `Jatuh Tempo ${dk.tgl(vb.due_date)}`, ...vb.items.flatMap((it) => [{ kata: it.product_name }, `${dk.qty(it.billed_qty ?? it.quantity)} ${it.unit}`, dk.rpCetak(it.line_total)]),
        `DPP (harga sebelum PPN) ${dk.rpCetak(base)}`, vb.dpp && `DPP nilai lain (11/12) ${dk.rpCetak(vb.dpp)}`,
        dk.rpCetak(vb.ppn_amount), `Total (termasuk PPN) ${dk.rpCetak(vb.grand_total)}`,
        `Sudah dibayar ${dk.rpCetak(vb.amount_paid)}`, `Sisa hutang ${dk.rpCetak(sisa)}`],
      (d) => [...tbSama(vb.grand_total)(d), ...(/po_[0-9a-f]{8,}/.test(d.text) ? ["id PO internal tercetak"] : [])]);
  }
  const cb = one(`return db.contra_bons.findOne({supplier_name:/Peserta ${NO}$/},{_id:0},{sort:{created_at:-1}})`);
  if (cb) {
    await cekPdf("2.3", "Finance", `Tanda Terima Kontrabon ${cb.number}`, `kontrabon-${cb.number.slice(-5)}`,
      () => dk.unduhApi(sesi, `/pdf/render/contra_bon/${cb.id}?format=pdf`),
      [cb.number, cb.supplier_name, ...(cb.bills || []).flatMap((b) => [b.supplier_invoice_no, b.bill_number, b.po_number, dk.rpCetak(b.applied_amount)]),
        `Nilai Bersih Dibayar ${dk.rpCetak(cb.totals.net_payable)}`, `Jatuh Tempo`, dk.tgl(cb.due_date)], tbSama(cb.totals.net_payable));
  } else r.note("Kontrabon peserta belum ada (jalankan F12 untuk peserta ini)");
  const po = one(`return db.purchase_orders.findOne({po_number:${JSON.stringify((k["a_dasar:tagihan_bayar"] || {}).po)}},{_id:0})`);
  if (po) {
    await cekPdf("2.4", "Finance", `Pesanan Pembelian ${po.po_number}`, `po-${po.po_number.slice(-5)}`,
      () => dk.unduhApi(sesi, `/pdf/render/purchase_order/${po.id}?format=pdf`),
      [po.po_number, po.supplier_name, ...po.items.flatMap((it) => [{ kata: it.product_name }, `${dk.qty(it.quantity)} ${it.unit}`, dk.rpCetak(it.price)]),
        `Total (termasuk PPN) ${dk.rpCetak(po.grand_total)}`, "NPWP Supplier"], tbSama(po.grand_total));
  }

  // ── 3. Faktur Pajak keluaran (F13) ────────────────────────────────────────────────────────────────────────────
  const so86 = k["a_dasar:so_lunas"];
  const fp = so86 && one(`return db.tax_invoices.findOne({order_id:${JSON.stringify(so86.so_id)},status:"normal"},{_id:0})`);
  if (fp) {
    await cekPdf("3", "Finance", `Faktur Pajak ${fp.number} (NSFP ${fp.nsfp || "belum"})`, `faktur-pajak-${fp.number.slice(-5)}`,
      () => dk.unduhApi(sesi, `/pdf/render/tax_invoice/${fp.id}?format=pdf`),
      ["Faktur Pajak", fp.number, fp.nsfp && `NSFP ${fp.nsfp}`, `Kode Transaksi ${fp.kode_transaksi}`, fp.customer_name,
        `DPP nilai lain (11/12) ${dk.rpCetak(fp.dpp)}`, dk.rpCetak(fp.ppn_amount), dk.rpCetak(fp.grand_total), fp.order_number],
      tbSama(fp.grand_total));
  } else r.note("Faktur pajak peserta belum terbit (jalankan F13 untuk peserta ini)");

  // ── 4. Rekening koran pelanggan & slip gaji ─────────────────────────────────────────────────────────────────
  const cust = one(`return db.customers.findOne({name:"Latihan ${NO} · Toko Kain Peserta ${NO}"},{_id:0,id:1,name:1})`);
  const hari = new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 10);
  await cekPdf("4.1", "Finance", `Rekening Koran ${cust.name}`, "rekening-koran",
    () => dk.unduhApi(sesi, `/customers/${cust.id}/statement.pdf?entity_id=ent_ksc&from=${hari.slice(0, 8)}01&to=${hari}`),
    ["Rekening Koran Pelanggan", cust.name, "Saldo awal", "Saldo akhir"], (d) => {
      return /Kas in\b/.test(d.text) ? ["keterangan jurnal \"Kas in\" (arah kas berbahasa Inggris, dari gl_service)"] : [];
    });
  const pay = k["d_hutang:gaji_susulan"];
  const slip = pay && one(`return db.hr_payslips.findOne({run_id:${JSON.stringify(pay.proses_gaji_id)}},{_id:0,id:1,number:1,net:1,employee_name:1,entity_id:1})`);
  if (slip) {
    await cekPdf("4.2", "Admin", `Slip Gaji ${slip.number} (${slip.employee_name})`, `slip-gaji-${slip.number.slice(-5)}`,
      () => dk.unduhApi(admin, `/hr/payslips/${slip.id}/pdf`),
      ["SLIP GAJI", slip.number, slip.employee_name, dk.rpCetak(slip.net), pt.nama], null, { tanpaKop: true });
  }

  // ── 5. Cetak sisi peramban: PD, Tanda Terima, LPJ, Bukti Kas (tombol layar → jendela cetak → PDF A4) ──────────────
  const popup = async (nama, klik) => {
    const [pop] = await Promise.all([r.page.waitForEvent("popup"), klik()]);
    await pop.waitForLoadState("load");
    await pop.waitForTimeout(400);
    const buf = await pop.pdf({ format: "A4", printBackground: true, margin: { top: "12mm", bottom: "12mm", left: "10mm", right: "10mm" } });
    fs.writeFileSync(require("path").join(r.dir, `${nama}.html`), await pop.content());
    await pop.close();
    return buf;
  };
  const pd = k["c_kas:pd_kas_kecil"];
  const ca = pd && one(`return db.cash_advances.findOne({id:${JSON.stringify(pd.pd_id)}},{_id:0})`);
  const stl = ca && one(`return db.cash_advance_settlements.findOne({cash_advance_id:${JSON.stringify(ca.id)}},{_id:0})`);
  await r.step("5.0", "Finance", "Login akun peserta → Keuangan › Kas & Bank › Kas Kecil, cari PD, klik [[Buka]]",
    "Rincian PD + LPJ tampil dengan tombol [[Cetak PD]], [[Tanda Terima]], cetak LPJ", async () => {
      await r.login(akunPeserta(NO));
      await kb.menu(r, "petty-cash");
      await r.tid("pc-search").fill(pd.pd);
      await r.tid(`pc-open-${pd.pd_id}`).click();
      await r.tid("ca-detail").waitFor();
      await r.idle(300);
      await r.shot("pd-rincian-tombol-cetak", { locator: r.tid("ca-detail") });
    });
  if (ca) {
    await cekPdf("5.1", "Finance", `Klik [[Cetak PD]] → Form Pengajuan Dana ${ca.number}`, `pd-${ca.number.slice(-5)}`,
      () => popup(`pd-${ca.number.slice(-5)}`, () => r.tid("ca-print").click()),
      ["Pengajuan Dana", ca.number, `TOTAL PENGAJUAN ${dk.rpCetak(ca.total_amount)}`, ...(ca.lines || []).map((l) => l.description),
        "Atasan Langsung", "Pimpinan", "Bagian Keuangan"], tbSama(ca.total_amount), { tanpaKop: true });
    await cekPdf("5.2", "Finance", `Klik [[Tanda Terima]] → tanda terima pencairan ${ca.number}`, `tanda-terima-${ca.number.slice(-5)}`,
      () => popup(`tanda-terima-${ca.number.slice(-5)}`, () => r.tid("ca-print-tt").click()),
      ["Tanda Terima", dk.rpCetak(ca.total_amount)], tbSama(ca.total_amount), { tanpaKop: true });
  }
  if (stl) {
    await cekPdf("5.3", "Finance", `Klik cetak LPJ ${stl.number}`, `lpj-${stl.number.slice(-5)}`,
      () => popup(`lpj-${stl.number.slice(-5)}`, () => r.tid("stl-print").click()),
      ["Pertanggungjawaban", stl.number, ca.number, `TOTAL PENGELUARAN ${dk.rpCetak(stl.total_pengeluaran)}`,
        `DANA DITERIMA (PD) ${dk.rpCetak(stl.total_pettycash)}`, ...(stl.expense_lines || []).map((l) => l.description)],
      null, { tanpaKop: true });
  }
  // Bukti kas: ongkos ekspedisi F09 (keluar) dan penerimaan kwitansi bersen (masuk).
  const kasKeluar = one(`return db.cash_transactions.findOne({description:/Peserta ${NO} — Latihan ${NO}$/,direction:"out"},{_id:0,number:1,amount:1,journal_entry_id:1})`);
  // Kas penerimaan kwitansi jejak (F16) — nominal bersen (Rp …,50) menguji angka & terbilang bukti kas.
  const kasMasuk = one(`return db.cash_transactions.findOne({number:${JSON.stringify((k["e_buku:so_jejak"] || {}).kas || "")}},{_id:0,number:1,amount:1,journal_entry_id:1})`);
  for (const [i, kas, btn, judul] of [["5.4", kasKeluar, "gl-print-payment-voucher", "Bukti Kas Keluar"],
    ["5.5", kasMasuk, "gl-print-received-voucher", "Bukti Kas Masuk"]]) {
    if (!kas) { r.note(`${judul}: transaksi kas peserta tidak ditemukan`); continue; }
    const je = one(`return db.journal_entries.findOne({id:${JSON.stringify(kas.journal_entry_id)}},{_id:0,id:1,number:1,total_debit:1})`);
    await cekPdf(i, "Finance", `Buku Besar › Jurnal ${je.number} → [[${judul}]] (${kas.number}, ${dk.rpCetak(kas.amount)})`,
      `bukti-kas-${i === "5.4" ? "keluar" : "masuk"}-${je.number.slice(-5)}`,
      async () => {
        await r.page.reload();   // tutup panel PD/LPJ (modal) sebelum pindah menu
        await r.idle();
        await kb.menuJurnal(r);
        await r.tid("gl-journal-search").fill(je.number);
        await r.tid(`gl-journal-row-${je.id}`).waitFor({ timeout: 20000 });
        await r.tid(`gl-journal-row-${je.id}`).click();
        await r.tid("gl-journal-detail").waitFor();
        const b = await popup(`bukti-kas-${i}`, () => r.tid(btn).click());
        await r.tid("gl-journal-detail-close").click();
        return b;
      },
      [judul, je.number, `TOTAL ${dk.rpCetak(je.total_debit)} ${dk.rpCetak(je.total_debit)}`], tbSama(je.total_debit), { tanpaKop: true });
  }

  r.note(`Rangkuman: ${JSON.stringify(ringkas)}`);
  await r.finish();
})();
