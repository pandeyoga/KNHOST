// R5 · GABUNG N:1 — pelanggan membayar SATU kwitansi lewat DUA transfer. Centang kedua baris → [[Gabung ke 1 transaksi]]
// → kandidat teratas = kas kwitansi ("Sisa transaksi pas sama dengan total mutasi terpilih") → klik.
// Cek buku: kas "Terekonsiliasi" penuh oleh dua baris, tidak ada jurnal baru.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R5_gabung.js
const { Run, assert, rp } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R5", "Rekonsiliasi · dua transfer untuk satu kwitansi — gabung N:1").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("gabung");
  const [m1, m2] = c.barisManifest("R5");
  let l1;
  let l2;

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R5")} → [[Pratinjau]] → [[Impor]] → [[Cocokkan otomatis]]`,
    `2 baris baru (${rp(k.bagian_1)} dan ${rp(k.bagian_2)}); keduanya TETAP "Perlu keputusan"`, async () => {
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R5", { baris: 2 });
      const t = await rk.cocokOtomatis(r);
      await rk.saring(r, c);
      l1 = rk.baris(c, m1.keterangan);
      l2 = rk.baris(c, m2.keterangan);
      assert(l1.status === "unmatched" && l2.status === "unmatched", `status: ${l1.status}/${l2.status}`);
      return `${x.notice} · ${t}`;
    });

  await r.step(2, "Finance", "Centang kotak di kiri kedua baris \"… TAHAP SATU\" dan \"… TAHAP DUA\"",
    `Bilah biru "2 mutasi dipilih · total ${rp(k.nominal)} — bisa digabung ke SATU transaksi buku" dengan tombol [[Gabung ke 1 transaksi]]`, async () => {
      await r.tid(`recon-pick-${l1.id}`).check();
      await r.tid(`recon-pick-${l2.id}`).check();
      const t = await kb.tunggu(r, "recon-group-bar", /2 mutasi/);
      assert(t.includes(rp(k.nominal)), `bilah gabung: ${t}`);
      await kb.shotSorot(r, "dua-baris-dipilih", r.tid("recon-group-open"));
      return t;
    });

  await r.step(3, "Finance", "Klik [[Gabung ke 1 transaksi]]",
    `Pop-up "Gabung 2 mutasi ke satu transaksi buku · total ${rp(k.nominal)}"; kandidat teratas ${k.kas} sisa ${rp(k.nominal)} dengan alasan "Sisa transaksi pas sama dengan total mutasi terpilih (+40)"`, async () => {
      await r.tid("recon-group-open").click();
      const cand = r.tid(`recon-group-cand-${k.kas_id}`);
      await cand.waitFor();
      const ct = await kb.isi(cand);
      assert(/Sisa transaksi pas sama dengan total mutasi terpilih/.test(ct) && ct.includes(rp(k.nominal)), `kandidat: ${ct}`);
      const pertama = await r.page.locator('[data-testid^="recon-group-cand-"]').first().getAttribute("data-testid");
      assert(pertama === `recon-group-cand-${k.kas_id}`, `kandidat teratas: ${pertama}`);
      await kb.shotSorot(r, "kandidat-gabung", cand);
      return ct;
    });

  await r.step(4, "Finance", `Klik baris ${k.kas}`,
    `Pesan "2 mutasi digabung ke transaksi ${k.kas} (${rp(k.nominal)})."; kedua baris Tercocok · banyak → 1`, async () => {
      await r.tid(`recon-group-cand-${k.kas_id}`).click();
      const t = await kb.tunggu(r, "recon-notice", /2 mutasi digabung/);
      assert(t.includes(k.kas) && t.includes(rp(k.nominal)), `pesan: ${t}`);
      await rk.saring(r, c);
      for (const l of [l1, l2]) {
        await rk.tungguStatus(r, l.id, /^Tercocok$/);
        const row = await kb.isi(r.tid(`recon-line-${l.id}`));
        assert(row.includes(k.kas) && /banyak → 1/.test(row), `baris: ${row}`);
      }
      await r.shot("gabung-tersimpan", { locator: r.tid("recon-lines-table") });
      return t;
    });

  await r.step(5, "Finance", "Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `${k.kas} "Terekonsiliasi" (${rp(k.bagian_1)} + ${rp(k.bagian_2)}); tidak ada jurnal baru`, async () => {
      const t = rk.kasTerekonsiliasi(k.kas_id);
      assert((t.matched_line_ids || []).length === 2, `kas ${t.number} tertaut ke ${(t.matched_line_ids || []).length} baris`);
      await rk.cekMutasiRekening(r, c, [k.kas_id]);
      return `${t.number} ${rp(t.reconciled_amount)} dari 2 baris`;
    });

  await r.finish();
})();
