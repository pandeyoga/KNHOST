// R4 · PECAH 1:N — pelanggan mengirim SATU transfer untuk DUA kwitansi. Cocokkan → mode "Pecah ke beberapa transaksi"
// → kotak "Kombinasi pas" menunjuk kedua kas kwitansi → [[Isi alokasi]] → [[Simpan pemecahan]].
// Cek buku: kedua kas "Terekonsiliasi" penuh, tidak ada jurnal baru.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R4_pecah.js
const { Run, assert, rp } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R4", "Rekonsiliasi · satu transfer untuk dua kwitansi — pecah 1:N").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("pecah");
  const [mf] = c.barisManifest("R4");
  let ln;

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R4")} → [[Pratinjau]] → [[Impor]] → [[Cocokkan otomatis]]`,
    `1 baris baru; sesudah Cocokkan otomatis baris ${rp(k.nominal)} TETAP "Perlu keputusan" (tidak ada SATU transaksi buku bernominal sama)`, async () => {
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R4", { baris: 1 });
      const t = await rk.cocokOtomatis(r);
      await rk.saring(r, c);
      ln = rk.baris(c, mf.keterangan);
      assert(ln.status === "unmatched", `status baris: ${ln.status}`);
      return `${x.notice} · ${t}`;
    });

  await r.step(2, "Finance", "Pada baris \"… DUA NOTA\" klik [[Cocokkan]]",
    "Pop-up \"Cocokkan mutasi bank\" mode Satu transaksi: \"Tidak ada transaksi buku yang layak … pilih “Pecah ke beberapa transaksi”\"", async () => {
      await r.tid(`recon-matchbtn-${ln.id}`).click();
      await r.tid("recon-match-modal").waitFor();
      const t = await kb.tunggu(r, "recon-cand-empty", /Pecah ke beberapa transaksi/);
      await kb.shotSorot(r, "cocokkan-satu-kosong", r.tid("recon-mode-split"), { locator: r.tid("recon-match-modal") });
      return t;
    });

  await r.step(3, "Finance", "Klik [[Pecah ke beberapa transaksi]]",
    `Kotak hijau "Kombinasi pas: ${k.kas_1} (${rp(k.nominal_1)}) + ${k.kas_2} (${rp(k.nominal_2)}) = ${rp(k.nominal)}"; kedua kas di urutan teratas dengan alasan "Bersama … pas menutup nominal transfer (+40)"`, async () => {
      await r.tid("recon-mode-split").click();
      const t = await kb.tunggu(r, "recon-split-combo-0", /Kombinasi pas/);
      assert(t.includes(k.kas_1) && t.includes(k.kas_2) && t.includes(rp(k.nominal)), `kombinasi: ${t}`);
      for (const id of [k.kas_1_id, k.kas_2_id]) {
        const ct = await kb.isi(r.tid(`recon-cand-${id}`));
        assert(/Bersama .* pas menutup nominal transfer \(\+40\)/.test(ct), `kandidat ${id}: ${ct}`);
      }
      const atas = await r.page.locator('[data-testid^="recon-cand-"]').evaluateAll((els) => els.slice(0, 2)
        .map((e) => e.getAttribute("data-testid").replace("recon-cand-", "")));
      assert(atas.includes(k.kas_1_id) && atas.includes(k.kas_2_id), `dua kandidat teratas: ${atas}`);
      await kb.shotSorot(r, "kombinasi-pas", r.tid("recon-split-combo-fill-0"), { locator: r.tid("recon-match-modal") });
      return t;
    });

  await r.step(4, "Finance", "Klik [[Isi alokasi]] → periksa nominal kedua kas → klik [[Simpan pemecahan (2 transaksi)]]",
    `Sisa belum dialokasikan Rp 0; pesan "Satu transfer dipecah ke 2 transaksi buku (${rp(k.nominal)})."; baris Tercocok · 1 transfer → banyak; Transaksi buku ${k.kas_1} dan ${k.kas_2}`, async () => {
      await r.tid("recon-split-combo-fill-0").click();
      const info = await kb.tunggu(r, "recon-split-info", /Rp\s*0(?!\d|[.,]\d)/);
      await r.shot("alokasi-terisi", { locator: r.tid("recon-match-modal") });
      await r.tid("recon-split-submit").click();
      const t = await kb.tunggu(r, "recon-notice", /dipecah ke 2 transaksi buku/);
      assert(t.includes(rp(k.nominal)), `pesan: ${t}`);
      await r.tid("recon-match-modal").waitFor({ state: "detached" });
      await rk.saring(r, c);
      await rk.tungguStatus(r, ln.id, /^Tercocok$/);
      const row = await kb.isi(r.tid(`recon-line-${ln.id}`));
      assert(row.includes(k.kas_1) && row.includes(k.kas_2) && /1 transfer → banyak/.test(row), `baris: ${row}`);
      await kb.sorot(r.tid(`recon-line-${ln.id}`));
      await r.shot("pecah-tersimpan", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${ln.id}`));
      return `${info} · ${t}`;
    });

  await r.step(5, "Finance", "Rekening & Saldo → kartu BCA Operasional KSC → Mutasi",
    `${k.kas_1} dan ${k.kas_2} "Terekonsiliasi"; tidak ada jurnal baru`, async () => {
      const a = rk.kasTerekonsiliasi(k.kas_1_id);
      const b = rk.kasTerekonsiliasi(k.kas_2_id);
      await rk.cekMutasiRekening(r, c, [k.kas_1_id, k.kas_2_id]);
      return `${a.number} ${rp(a.reconciled_amount)} · ${b.number} ${rp(b.reconciled_amount)}`;
    });

  await r.finish();
})();
