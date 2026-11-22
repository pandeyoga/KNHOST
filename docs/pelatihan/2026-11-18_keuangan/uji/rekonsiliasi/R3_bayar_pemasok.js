// R3 · Transfer KELUAR ke pemasok — berita transfer memuat nomor tagihan pemasok. Cocokkan otomatis menautkan baris ke
// kas pembayaran tagihan (nominal + tanggal + nomor referensi + nama). Cek buku: kas "Terekonsiliasi", tagihan tetap
// Lunas, tidak ada jurnal baru.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R3_bayar_pemasok.js
const { Run, assert, rp, mongo } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R3", "Rekonsiliasi · transfer keluar ke pemasok — cocok otomatis lewat nomor tagihan").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("bayar_pemasok");
  const [mf] = c.barisManifest("R3");
  let ln;

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R3")} → [[Pratinjau]] → [[Impor]]`,
    `Pratinjau "Terbaca 1 baris … keluar ${rp(k.nominal)}"; pesan "1 baris baru, 0 dilewati"`, async () => {
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R3", { baris: 1 });
      assert(x.pratinjau.includes(rp(k.nominal)), `nominal keluar di pratinjau: ${x.pratinjau}`);
      return `${x.pratinjau} || ${x.notice}`;
    });

  await r.step(2, "Finance", "Klik [[Cocokkan otomatis]] → cari \"LATIHAN NN\" → klik angka Skor baris TRSF E-BANKING DB",
    `Baris keluar ${rp(k.nominal)} Tercocok · satu-satu · otomatis ke ${k.kas}; alasan skor menyebut "nomor referensi '${k.tagihan}' ada di transaksi buku"`, async () => {
      const t = await rk.cocokOtomatis(r);
      await rk.saring(r, c);
      ln = rk.baris(c, mf.keterangan);
      assert(ln.status === "matched" && ln.match_type === "auto", `baris belum tercocok otomatis: ${ln.status}/${ln.match_type}`);
      assert((ln.allocations || []).some((a) => a.txn_id === k.kas_id), "baris tertaut ke kas lain");
      await rk.tungguStatus(r, ln.id, /^Tercocok$/);
      await r.tid(`recon-score-${ln.id}`).click();
      const why = await kb.teks(r, `recon-score-${ln.id}-explain`);
      assert(why.includes(`nomor referensi '${k.tagihan}'`), `alasan skor: ${why}`);
      await kb.sorot(r.tid(`recon-line-${ln.id}`));
      await r.shot("cocok-otomatis-tagihan", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${ln.id}`));
      return `${t} · skor ${ln.score} · ${why}`;
    });

  await r.step(3, "Finance", "Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `Baris ${k.kas} (Pembayaran ${k.tagihan}) "Terekonsiliasi"; tagihan ${k.tagihan} tetap Lunas; tidak ada jurnal baru`, async () => {
      const t = rk.kasTerekonsiliasi(k.kas_id);
      const vb = mongo(`return db.vendor_bills.findOne({id:${JSON.stringify(k.tagihan_id)}},{_id:0,status:1,number:1})`);
      assert(vb && vb.status === "paid", `status tagihan ${k.tagihan}: ${vb && vb.status}`);
      await rk.cekMutasiRekening(r, c, [k.kas_id]);
      return `${t.number} ${rp(t.reconciled_amount)} · tagihan ${k.tagihan} ${vb.status}`;
    });

  await r.finish();
})();
