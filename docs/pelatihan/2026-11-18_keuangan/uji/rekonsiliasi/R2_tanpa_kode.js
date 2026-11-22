// R2 · Transfer masuk TANPA kode — berita transfer hanya menyebut nama pelanggan. Cocokkan otomatis TIDAK menautkan
// (skor 75 < ambang 80) tetapi memberi USULAN; peserta memeriksa lalu menekan "Terima usulan".
// Cek buku: kas kwitansi "Terekonsiliasi", tidak ada jurnal baru.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R2_tanpa_kode.js
const { Run, assert, rp } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R2", "Rekonsiliasi · transfer tanpa kode — usulan, tautkan manual").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("tanpa_kode");
  const [mf] = c.barisManifest("R2");
  let ln;

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R2")} → [[Pratinjau]] → [[Impor]]`,
    `Pratinjau "Terbaca 1 baris … masuk ${rp(k.nominal)}"; pesan "Impor BCA — Rekening Koran (CSV): 1 baris baru, 0 dilewati"`, async () => {
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R2", { baris: 1 });
      return `${x.pratinjau} || ${x.notice}`;
    });

  await r.step(2, "Finance", "Klik [[Cocokkan otomatis]] → cari \"LATIHAN NN\"",
    `Baris ${rp(k.nominal)} TETAP "Perlu keputusan" dengan tombol usulan "Terima usulan: ${k.kas} · ${rp(k.nominal)} (skor 75)"; alasan skor: Nominal sama (+40) · Tanggal sama (+20) · nama mirip (+15)`, async () => {
      const t = await rk.cocokOtomatis(r);
      await rk.saring(r, c);
      ln = rk.baris(c, mf.keterangan);
      const sug = (ln.suggestions || [])[0] || {};
      if (ln.status === "matched") {
        // Aturan pencocokan yang DISETUJUI (Pengaturan › Aturan bank) menambah +15 → otomatis. Dicatat, bukan gagal.
        assert((ln.allocations || []).some((a) => a.txn_id === k.kas_id), "baris tertaut otomatis ke kas lain");
        r.note(`Baris sudah tertaut otomatis (skor ${ln.score}) — ada aturan pencocokan aktif untuk pola ini.`);
        return `${t} · otomatis karena aturan`;
      }
      assert(ln.status === "unmatched", `status baris: ${ln.status}`);
      assert(sug.id === k.kas_id, `usulan teratas bukan kas peserta: ${JSON.stringify(ln.suggestions || []).slice(0, 200)}`);
      assert(sug.score >= 60 && sug.score < 80, `skor usulan ${sug.score} (harus 60–79)`);
      const btn = r.tid(`recon-accept-${ln.id}-${k.kas_id}`);
      const bt = await kb.isi(btn);
      assert(bt.includes(k.kas) && bt.includes(rp(k.nominal)) && /skor 75/.test(bt), `tombol usulan: ${bt}`);
      await r.tid(`recon-score-${ln.id}`).click();
      const why = await kb.teks(r, `recon-score-${ln.id}-explain`);
      assert(/Nominal sama/.test(why) && /Tanggal sama/.test(why) && /nama mirip/.test(why), `alasan skor: ${why}`);
      await kb.shotSorot(r, "usulan-skor-75", btn, { locator: r.tid("recon-lines-table") });
      await r.tid(`recon-score-${ln.id}`).click();
      return `${t} · ${bt} · ${why}`;
    });

  await r.step(3, "Finance", `Periksa usulan (nominal, tanggal, nama pelanggan sama dengan kwitansi ${k.kwitansi}) → klik [[Terima usulan: ${k.kas} …]]`,
    `Pesan "Mutasi ditautkan ke ${k.kas} (skor 75)."; baris Tercocok · satu-satu (manual); Transaksi buku ${k.kas}`, async () => {
      if (ln.status === "matched") return "dilewati — sudah tertaut otomatis";
      await r.tid(`recon-accept-${ln.id}-${k.kas_id}`).click();
      const t = await kb.tunggu(r, "recon-notice", new RegExp(`Mutasi ditautkan ke ${k.kas.replace(/\//g, "\\/")}`));
      await rk.saring(r, c);
      await rk.tungguStatus(r, ln.id, /^Tercocok$/);
      ln = rk.baris(c, mf.keterangan);
      assert(ln.match_type === "manual" && (ln.allocations || []).some((a) => a.txn_id === k.kas_id), "tautan manual ke kas peserta");
      const row = await kb.isi(r.tid(`recon-line-${ln.id}`));
      assert(row.includes(k.kas) && /satu-satu/.test(row) && !/otomatis/.test(row), `baris: ${row}`);
      await kb.sorot(r.tid(`recon-line-${ln.id}`));
      await r.shot("usulan-diterima", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${ln.id}`));
      return t;
    });

  await r.step(4, "Finance", "Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `Baris ${k.kas} "Terekonsiliasi"; tidak ada jurnal baru`, async () => {
      const t = rk.kasTerekonsiliasi(k.kas_id);
      await rk.cekMutasiRekening(r, c, [k.kas_id]);
      return `${t.number} ${rp(t.reconciled_amount)}`;
    });

  await r.finish();
})();
