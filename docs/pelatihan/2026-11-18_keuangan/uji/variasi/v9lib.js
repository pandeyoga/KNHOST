// Pembantu uji V9 — BUKTI KLAIM teks materi pelatihan (bukan langkah): satu langkah `Run.step` = satu klaim yang tertulis
// di `konsep`, `cek_buku`, `kesalahan_umum`, `titik_kontrol`, atau `catatan_pelatih` sebuah materi.
//
//   const k = require("./v9lib");
//   const d = k.daftar("piutang");                  // hasil → uji/hasil/V9/piutang/{hasil.json, klaim.json, *.png}
//   await k.klaim(r, d, { kode: "F03", bagian: "kesalahan_umum.1", klaim: "…", peran: "Finance", harap: "…" }, async () => …);
//   d.simpan();
//
// `src/variasi_klaim_materi.json` disusun dari `klaim.json` semua bagian + bukti uji lama (`uji/variasi/V9_katalog.js`).
const fs = require("fs");
const path = require("path");

const OUT = process.env.KN_OUT || path.join(__dirname, "..", "hasil");

function daftar(bagian) {
  const rows = [];
  return {
    bagian, rows, n: 0,
    kode: `V9/${bagian}`,
    simpan() {
      const dir = path.join(OUT, "V9", bagian);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "klaim.json"), JSON.stringify(rows, null, 1));
    },
  };
}

/** Satu klaim = satu langkah uji. Nama langkah menyebut kode materi + bunyi klaim; gagal tetap tercatat (tidak disembunyikan). */
async function klaim(r, d, meta, fn) {
  const no = ++d.n;
  const ok = await r.step(no, meta.peran || "Finance", `${meta.kode} · ${meta.klaim}`, meta.harap, fn);
  const row = r.steps[r.steps.length - 1];
  d.rows.push({ kode: meta.kode, bagian: meta.bagian, klaim: meta.klaim, harap: meta.harap, peran: meta.peran || "Finance",
    langkah: no, uji: ok ? "lulus" : "gagal", bukti: row.info || "" });
  d.simpan();
  return ok;
}

/** Bersihkan potret lama bagian ini (nomor urut potret berubah antar-jalan). */
function bersihkan(bagian) {
  fs.rmSync(path.join(OUT, "V9", bagian), { recursive: true, force: true });
}

/** Teks rapi elemen (spasi tunggal) atau "" bila tidak ada. */
async function teks(r, testId) {
  const el = r.tid(testId);
  if (!(await el.count())) return "";
  return (await el.first().innerText()).replace(/\s+/g, " ").trim();
}

/** Ringkas jurnal: "KSC/JE-… 1-1100 D 100 · 1-1200 K 100". */
function ringkasJurnal(je) {
  return `${je.number}: ` + je.lines.map((l) => `${l.account_code} ${Number(l.debit) ? "D " + l.debit : "K " + l.credit}`).join(" · ");
}

/** Jurnal seimbang + baris harapan [[kode, "D"|"K", nominal], …] (±0,01). */
function cekJurnal(je, harap = []) {
  if (!je) throw new Error("jurnal tidak ditemukan");
  const d = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0);
  const k = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
  if (Math.abs(d - k) >= 0.01) throw new Error(`jurnal ${je.number} tidak seimbang D ${d} ≠ K ${k}`);
  for (const [kode, sisi, nom] of harap) {
    const tot = je.lines.filter((l) => l.account_code === kode).reduce((s, l) => s + Number((sisi === "D" ? l.debit : l.credit) || 0), 0);
    if (Math.abs(tot - nom) >= 0.01) throw new Error(`jurnal ${je.number}: ${kode} ${sisi} ${tot} ≠ ${nom} (${ringkasJurnal(je)})`);
  }
  return je;
}

module.exports = { daftar, klaim, bersihkan, teks, ringkasJurnal, cekJurnal };
