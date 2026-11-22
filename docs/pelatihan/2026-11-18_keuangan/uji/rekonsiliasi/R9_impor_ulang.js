// R9 · IMPOR ULANG — rekening koran lengkap (R0, semua baris R1–R7) diunggah lagi: semua baris sudah pernah masuk dan
// DILEWATI (tidak ada mutasi ganda). Lalu ringkasan baris peserta: tidak ada yang tersisa "Perlu keputusan".
// Jalankan sesudah R1–R8.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R9_impor_ulang.js
const { Run, assert, mongo } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R9", "Rekonsiliasi · impor ulang rekening koran lengkap — tidak ada mutasi ganda").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const n = c.manifest.berkas.R0.baris_total;
  const milik = () => mongo(`return db.bank_statement_lines.find({bank_account_id:${JSON.stringify(c.bca.id)},
    description:{$regex:"LATIHAN ${c.NO}( |$)"}},{_id:0,id:1,status:1,description:1}).toArray()`);

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R0")} → [[Pratinjau]] → [[Impor]]`,
    `Pratinjau "Terbaca ${n} baris"; pesan "… 0 baris baru, ${n} dilewati (sudah pernah masuk)."`, async () => {
      const sebelum = milik().length;
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R0", { baris: n, baru: 0 });
      assert(milik().length === sebelum, `jumlah baris peserta berubah ${sebelum} → ${milik().length}`);
      return `${x.notice} · baris peserta tetap ${sebelum}`;
    });

  await r.step(2, "Finance", "Saring status \"Perlu keputusan\" → cari \"LATIHAN NN\"",
    `Tidak ada baris LATIHAN NN tersisa: ${n} baris = Tercocok (R1–R6) + Dititipkan (R7)`, async () => {
      const rows = milik();
      assert(rows.length === n, `baris peserta ${rows.length} ≠ ${n}`);
      const sisa = rows.filter((x) => x.status === "unmatched");
      assert(!sisa.length, `masih perlu keputusan: ${sisa.map((x) => x.description).join("; ")}`);
      await r.tid("recon-filter-status").click();
      await r.tid("recon-filter-status-option-unmatched").click();
      await r.idle(400);
      await rk.saring(r, c);
      for (const x of rows) assert(!(await r.tid(`recon-line-${x.id}`).count()), `baris ${x.description} tampil di saringan`);
      await r.shot("tidak-ada-sisa", { locator: r.tid("recon-lines-table") });
      const hit = rows.reduce((a, x) => ({ ...a, [x.status]: (a[x.status] || 0) + 1 }), {});
      return JSON.stringify(hit);
    });

  await r.finish();
})();
