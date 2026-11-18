// R1 · Transfer masuk dengan KODE BAYAR — unggah rekening koran Excel, pratinjau (dikenali otomatis), impor, Cocokkan
// otomatis: baris tertaut ke kas kwitansi peserta karena berita transfer memuat kode bayar pesanannya.
// Cek buku: kas kwitansi "Terekonsiliasi", tidak ada jurnal baru (pencocokan hanya menautkan).
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R1_kode_bayar.js
const { Run, assert, rp } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R1", "Rekonsiliasi · transfer masuk berkode bayar — cocok otomatis").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("kode_bayar");
  const [mf] = c.barisManifest("R1");
  let ln;

  await r.step(1, "Finance", "Login akun peserta → Keuangan › Kas & Bank › Rekonsiliasi → pilih rekening BCA Operasional KSC",
    "Kartu ringkasan rekening tampil; tombol [[Impor mutasi bank]] dan [[Cocokkan otomatis]] tersedia", async () => {
      await rk.bukaRekon(r, c);
      await kb.shotSorot(r, "rekonsiliasi-awal", r.tid("recon-import-toggle"));
      return `kwitansi ${k.kwitansi} · ${k.kas} ${rp(k.nominal)} · kode bayar ${k.kode_bayar}`;
    });

  await r.step(2, "Finance", `Klik [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R1")} → biarkan *Template bank* "Kenali otomatis" → [[Pratinjau]]`,
    `"Terbaca 1 baris memakai template ${rk.TEMPLATE} (dikenali otomatis) · lembar Mutasi Rekening, judul kolom di baris 7 · masuk ${rp(k.nominal)}"`, async () => {
      const x = await rk.imporExcel(r, c, "R1", { baris: 1 });
      assert(x.pratinjau.includes(rp(k.nominal)), `nominal di pratinjau: ${x.pratinjau}`);
      return `${x.pratinjau} || ${x.notice} || ${x.sumber}`;
    });

  await r.step(3, "Finance", "Klik [[Cocokkan otomatis]] → ketik \"LATIHAN NN\" di kotak cari daftar mutasi → klik angka Skor baris transfer",
    `Baris ${rp(k.nominal)} berstatus Tercocok · satu-satu · otomatis; Transaksi buku ${k.kas}; alasan skor menyebut "Kode bayar ${k.kode_bayar} cocok dengan pesanan ${k.so}"`, async () => {
      const t = await rk.cocokOtomatis(r);
      await rk.saring(r, c);
      ln = rk.baris(c, mf.keterangan);
      assert(ln.status === "matched" && ln.match_type === "auto", `baris belum tercocok otomatis: ${ln.status}/${ln.match_type}`);
      assert((ln.allocations || []).some((a) => a.txn_id === k.kas_id), "baris tertaut ke kas lain");
      await rk.tungguStatus(r, ln.id, /^Tercocok$/);
      const row = await kb.isi(r.tid(`recon-line-${ln.id}`));
      assert(row.includes(k.kas) && /satu-satu · otomatis/.test(row), `baris: ${row}`);
      await r.tid(`recon-score-${ln.id}`).click();
      const why = await kb.teks(r, `recon-score-${ln.id}-explain`);
      assert(why.includes(`Kode bayar ${k.kode_bayar} cocok dengan pesanan ${k.so}`), `alasan skor: ${why}`);
      await kb.sorot(r.tid(`recon-line-${ln.id}`));
      await r.shot("cocok-otomatis-kode-bayar", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${ln.id}`));
      return `${t} · skor ${ln.score}`;
    });

  await r.step(4, "Finance", "Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `Baris ${k.kas} berstatus Rekonsiliasi "Terekonsiliasi"; tidak ada jurnal baru (kas tetap satu jurnal)`, async () => {
      const t = rk.kasTerekonsiliasi(k.kas_id);
      await rk.cekMutasiRekening(r, c, [k.kas_id]);
      return `${t.number} ${rp(t.reconciled_amount)} / ${rp(t.amount)}`;
    });

  await r.finish();
})();
