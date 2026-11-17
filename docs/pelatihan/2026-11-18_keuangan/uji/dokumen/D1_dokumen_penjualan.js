// D1 — Dokumen PENJUALAN yang terbit dari data peserta: Konfirmasi Pesanan, Faktur Komersial, Surat Pengambilan,
// Daftar Kemasan, Surat Jalan, pesanan sample. PDF diunduh lewat tombol LAYAR (Pusat Dokumen › Unduh PDF) dan lewat
// API (`/pdf/render/…`), lalu ISI dicocokkan dengan database dan FORMAT diperiksa (A4, Rp gaya Indonesia, terbilang =
// total termasuk sen, tanpa label Inggris, kolom tidak terpotong). Gambar halaman di hasil/D1/*.png.
//
//   KN_PESERTA=81 node docs/pelatihan/2026-11-18_keuangan/uji/dokumen/D1_dokumen_penjualan.js
const { Run, api, assert, kartu, peserta, akunPeserta, mongo } = require("../lib");
const dk = require("./dokumen_lib");
const kb = require("../kasbank_lib");

const NO = peserta("81");

/** Isi pesanan + pengiriman + roll dari DB (pembanding). */
function dataSo(soId) {
  return mongo(`const o=db.sales_orders.findOne({id:${JSON.stringify(soId)}},{_id:0});
    const shp=db.shipments.find({order_id:o.id},{_id:0,shipment_no:1,created_at:1,created_by:1,rolls:1,qty:1,unit:1}).sort({created_at:1}).toArray();
    const ids=[].concat(...shp.map(s=>(s.rolls||[]).map(r=>r.roll_id)));
    const rolls=db.inventory_rolls.find({id:{$in:ids}},{_id:0,id:1,roll_no:1,length_initial:1,unit:1}).toArray();
    return {o, shp, rolls}`);
}

/** Total yang harus tercetak (K-03): DPP = total − PPN, DPP nilai lain, PPN, Total. */
function harusTotal(o) {
  const out = [dk.rpCetak(o.grand_total)];
  if (Number(o.ppn_amount) > 0) {
    out.push(`DPP (harga sebelum PPN) ${dk.rpCetak(Math.round((o.grand_total - o.ppn_amount) * 100) / 100)}`);
    if (o.dpp_nilai_lain) out.push(`DPP nilai lain (11/12) ${dk.rpCetak(o.dpp)}`);
    out.push(dk.rpCetak(o.ppn_amount));
  }
  return out;
}

/** Baris barang pesanan: nama, "121,85 yard", harga, subtotal. */
const harusBaris = (o) => o.items.flatMap((it) => [{ kata: it.product_name }, `${dk.qty(it.quantity)} ${it.unit}`,
  dk.rpCetak(it.price), dk.rpCetak(it.line_total ?? it.subtotal)]);

(async () => {
  const k = kartu(NO);
  const r = await new Run("D1", `Dokumen penjualan peserta ${NO} — isi & format`).start();
  const so = { lunas: k["a_dasar:so_lunas"], sebagian: k["a_dasar:so_sebagian"], jejak: k["e_buku:so_jejak"],
    cicilan: k["b_piutang:cicilan"], sample: k["d_hutang:sample_berbayar"] };
  if (!so.lunas || !so.jejak) { r.note(`Kartu peserta ${NO} belum lengkap — jalankan seed --mulai ${NO} --peserta ${NO}`); await r.finish(); return; }
  const sesi = await api(akunPeserta(NO));
  const pt = dk.profilPt(mongo, "ent_ksc");
  const kop = [pt.nama, pt.npwp && `NPWP ${pt.npwp}`];
  const hasil = {};

  /** Unduh via API + cek umum + cek isi. */
  const cek = async (no, judul, docType, sid, nama, harus, extra) => r.step(no, "Finance", judul,
    "PDF A4 · kop PT dari Profil PT · nomor/tanggal/pihak/baris/total = database · terbilang = total · tanpa label Inggris", async () => {
      const d = dk.simpan(r, nama, await dk.unduhApi(sesi, `/pdf/render/${docType}/${sid}?format=pdf`));
      const masalah = [...dk.cekFormat(d), ...dk.hilang(d, [...kop, ...harus]).map((h) => `tidak tercetak: "${h}"`)];
      if (extra) masalah.push(...(extra(d) || []));
      hasil[nama] = { halaman: d.halaman, png: d.png, masalah };
      dk.wajib(masalah, nama);
      return `${d.halaman} hlm · ${d.png.join(", ")}`;
    });

  // ── 1. Tombol layar: Pusat Dokumen › Faktur Komersial › Unduh PDF (cara peserta) ─────────────────────────────────
  await r.step(1, "Finance", "Login akun peserta → Pusat Dokumen (Cetak PDF): pilih jenis [[Faktur Komersial]], cari nomor SO, klik ikon [[Unduh PDF]]",
    "Berkas PDF terunduh; isinya sama dengan cetak API (selain stempel 'Dicetak')", async () => {
      await r.login(akunPeserta(NO));
      await r.go("document-center");
      await r.tid("document-center").waitFor();
      await kb.pilih(r, "dc-doctype-select", "invoice");
      await r.tid("dc-search").fill(so.lunas.so);
      await r.tid(`dc-row-${so.lunas.so_id}`).waitFor({ timeout: 20000 });
      await r.shot("pusat-dokumen-faktur", { locator: r.tid("document-center") });
      const [dl] = await Promise.all([r.page.waitForEvent("download"), r.tid(`dc-download-${so.lunas.so_id}`).click()]);
      const buf = require("fs").readFileSync(await dl.path());
      const layar = dk.simpan(r, "faktur-layar", buf);
      const lewatApi = dk.simpan(r, "faktur-api", await dk.unduhApi(sesi, `/pdf/render/invoice/${so.lunas.so_id}?format=pdf`));
      const bersih = (t) => dk.rata(t).replace(/Dicetak \d{2} \w{3} \d{4}( [\d.]+ WIB)?/g, "");
      assert(bersih(layar.text) === bersih(lewatApi.text), "isi PDF tombol layar ≠ PDF API");
      return `${dl.suggestedFilename()} · ${layar.halaman} hlm`;
    });

  // ── 2. Faktur Komersial — belum dibayar / dibayar sebagian / cicilan ─────────────────────────────────────────────
  for (const [i, key] of [["2", "lunas"], ["3", "sebagian"], ["4", "cicilan"]]) {
    if (!so[key]) continue;
    const { o, shp } = dataSo(so[key].so_id);
    const paid = Number(o.paid_total || 0);
    const harus = [o.number.replace("SO-", "INV-"), o.customer_name, ...harusBaris(o), ...harusTotal(o),
      `Terbilang: ${dk.terbilang(o.grand_total)}`, `Termin Bayar ${o.payment_term_name}`,
      `Sudah dibayar ${dk.rpCetak(paid)}`];
    const extra = (d) => {
      const m = [];
      const t = dk.rata(d.text);
      const lunas = Math.round((o.grand_total - paid) * 100) / 100 <= 0.01;
      // Faktur yang sudah LUNAS mencetak "Jatuh Tempo Lunas" (tidak ada tagihan terbuka) — rancangan resolver.
      if (lunas) { if (!/Jatuh Tempo Lunas/.test(t)) m.push("faktur lunas tidak bertulisan 'Jatuh Tempo Lunas'"); }
      else if (!/Jatuh Tempo \d{2} \w{3} \d{4}/.test(t)) m.push("jatuh tempo tidak tercetak");
      if (!lunas && key !== "cicilan" && shp.length) {   // NET 30 dari tanggal surat jalan
        const jt = new Date(new Date(shp[0].created_at).getTime() + 30 * 86400000).toISOString();
        if (!t.includes(`Jatuh Tempo ${dk.tgl(jt)}`)) m.push(`jatuh tempo ≠ SJ + 30 hari (${dk.tgl(jt)})`);
        const sisa = Math.round((o.grand_total - paid) * 100) / 100;
        if (!t.includes(`Sisa tagihan ${dk.rpCetak(sisa)}`)) m.push(`sisa tagihan ≠ ${dk.rpCetak(sisa)}`);
      }
      const tb = dk.terbilangTercetak(d.text);
      if (tb !== dk.terbilang(o.grand_total)) m.push(`terbilang "${tb}" ≠ "${dk.terbilang(o.grand_total)}"`);
      return m;
    };
    await cek(i, `Faktur Komersial ${o.number} (${o.payment_status})`, "invoice", o.id, `faktur-${o.number.slice(-5)}`, harus, extra);
  }

  // ── 3. Konfirmasi Pesanan (SO) & pesanan sample ──────────────────────────────────────────────────────────────────
  for (const [i, key] of [["5", "sebagian"], ["6", "sample"]]) {
    const sid = so[key] && (so[key].so_id || so[key].sos_id);
    if (!sid) continue;
    const { o } = dataSo(sid);
    await cek(i, `Konfirmasi Pesanan ${o.number}`, "sales_order", o.id, `pesanan-${o.number.replace(/\W+/g, "-")}`,
      [o.number, ...harusBaris(o), ...harusTotal(o), `Terbilang: ${dk.terbilang(o.grand_total)}`]);
  }

  // ── 4. Gudang: Surat Jalan, Daftar Kemasan, Surat Pengambilan — jumlah roll & kuantitas = yang dikirim ─────────────
  for (const [i, key] of [["7", "jejak"], ["8", "lunas"]]) {
    const { o, shp, rolls } = dataSo(so[key].so_id);
    const nRoll = rolls.length;
    const tot = Math.round(rolls.reduce((a, x) => a + Number(x.length_initial || 0), 0) * 100) / 100;
    const unit = (rolls[0] || {}).unit || "";
    const rollNo = rolls.map((x) => x.roll_no);
    await cek(`${i}a`, `Surat Jalan ${shp[0] && shp[0].shipment_no} (${o.number})`, "delivery_note", o.id,
      `surat-jalan-${o.number.slice(-5)}`, [shp[0].shipment_no, o.number, `Total Roll ${nRoll}`,
        `Total Kuantitas ${dk.qty(tot)} ${unit}`, ...rollNo, `Dibuat Oleh`, shp[0].created_by, dk.tgl(shp[0].created_at)],
      (d) => (/roll_[0-9a-f]{6,}/.test(d.text) ? ["id roll internal tercetak (bukan nomor roll)"] : []));
    await cek(`${i}b`, `Daftar Kemasan ${o.number}`, "packing_list", o.id, `daftar-kemasan-${o.number.slice(-5)}`,
      [o.number, shp[0].shipment_no, `Total Koli/Roll ${nRoll}`, `Total Kuantitas ${dk.qty(tot)} ${unit}`]);
    await cek(`${i}c`, `Surat Pengambilan ${o.number}`, "picking_list", o.id, `surat-pengambilan-${o.number.slice(-5)}`,
      [o.number, `Jumlah Baris ${nRoll}`, `Total Kuantitas ${dk.qty(tot)} ${unit}`, ...rollNo]);
  }

  r.note(`Rangkuman per dokumen: ${JSON.stringify(Object.fromEntries(Object.entries(hasil).map(([k2, v]) => [k2, v.masalah.length ? v.masalah : "lulus"])))}`);
  await r.finish();
})();
