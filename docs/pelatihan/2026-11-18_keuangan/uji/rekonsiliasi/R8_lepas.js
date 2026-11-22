// R8 · LEPAS & COCOKKAN ULANG — tautan yang keliru dilepas, lalu ditautkan lagi lewat [[Cocokkan]] → [[Tautkan]].
// Memakai baris R2 (jalankan R2 dulu). Cek buku: kas kembali "belum" saat dilepas, "Terekonsiliasi" lagi sesudah
// ditautkan; tidak ada jurnal baru maupun pembalik (pencocokan biasa tidak menyentuh jurnal).
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R8_lepas.js
const { Run, assert, rp } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R8", "Rekonsiliasi · lepas tautan lalu cocokkan ulang").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("tanpa_kode");
  const [mf] = c.barisManifest("R2");
  let ln;

  await r.step(1, "Finance", "Rekonsiliasi → BCA Operasional KSC → cari \"LATIHAN NN\" → baris transfer R2 (tanpa kode) berstatus Tercocok → klik [[Lepas]]",
    `Pesan "Tautan dilepas."; baris kembali "Perlu keputusan"; kas ${k.kas} kembali belum terekonsiliasi`, async () => {
      await rk.bukaRekon(r, c);
      await rk.saring(r, c);
      ln = rk.baris(c, mf.keterangan);
      assert(ln.status === "matched", `baris R2 belum tercocok (${ln.status}) — jalankan R2 dulu`);
      await kb.shotSorot(r, "tombol-lepas", r.tid(`recon-unmatch-${ln.id}`), { locator: r.tid("recon-lines-table") });
      await r.tid(`recon-unmatch-${ln.id}`).click();
      const t = await kb.tunggu(r, "recon-notice", /Tautan dilepas/);
      await rk.saring(r, c);
      await rk.tungguStatus(r, ln.id, /^Perlu keputusan$/);
      const kas = kb.kas(k.kas_id);
      assert(Number(kas.reconciled_amount || 0) < 0.01, `kas ${kas.number} masih ${rp(kas.reconciled_amount)} terekonsiliasi`);
      return t;
    });

  await r.step(2, "Finance", `Klik [[Cocokkan]] pada baris itu → kandidat ${k.kas} (skor 75) → [[Tautkan]]`,
    `Pop-up kandidat teratas ${k.kas} · ${rp(k.nominal)} · skor 75; pesan "Mutasi ditautkan (skor 75)."; baris Tercocok lagi`, async () => {
      await r.tid(`recon-matchbtn-${ln.id}`).click();
      await r.tid("recon-match-modal").waitFor();
      const cand = r.tid(`recon-cand-${k.kas_id}`);
      await cand.waitFor();
      const ct = await kb.isi(cand);
      assert(ct.includes(k.kas) && ct.includes(rp(k.nominal)), `kandidat: ${ct}`);
      const pertama = await r.page.locator('[data-testid^="recon-cand-"]').first().getAttribute("data-testid");
      assert(pertama === `recon-cand-${k.kas_id}`, `kandidat teratas: ${pertama}`);
      await kb.shotSorot(r, "tautkan-ulang", r.tid(`recon-pick-cand-${k.kas_id}`), { locator: r.tid("recon-match-modal") });
      await r.tid(`recon-pick-cand-${k.kas_id}`).click();
      const t = await kb.tunggu(r, "recon-notice", /Mutasi ditautkan/);
      await r.tid("recon-match-modal").waitFor({ state: "detached" });
      await rk.saring(r, c);
      await rk.tungguStatus(r, ln.id, /^Tercocok$/);
      return `${ct} · ${t}`;
    });

  await r.step(3, "Finance", "Cek buku",
    `Kas ${k.kas} "Terekonsiliasi" lagi; tetap SATU jurnal (lepas/tautkan tidak menerbitkan jurnal)`, async () => {
      const t = rk.kasTerekonsiliasi(k.kas_id);
      return `${t.number} ${rp(t.reconciled_amount)}`;
    });

  await r.finish();
})();
