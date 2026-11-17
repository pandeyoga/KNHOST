// Gabungkan tabel kasus uji variasi (hasil/V1..V4/tabel.json, ditulis V*_*.js) menjadi
// `src/variasi_piutang_kas.json`: satu baris per kasus {layar, isian, masukan, harap, hasil, catatan}.
//   node docs/pelatihan/2026-11-18_keuangan/uji/variasi/gabung_tabel.js
// `hasil`: lulus (benar tanpa perbaikan) · diperbaiki (salah sebelum perbaikan 17 Nov, kini benar) · keputusan (aturan bisnis
// yang perlu diputus pemilik). Kode kasus [Vn.m] + hasil uji jalan terakhir ditulis di depan `catatan`; kasus yang GAGAL saat
// uji jalan ditandai "UJI GAGAL" (tidak disembunyikan).
const fs = require("fs");
const path = require("path");

const HASIL = process.env.KN_OUT || path.join(__dirname, "..", "hasil");
const OUT = path.join(__dirname, "..", "..", "src", "variasi_piutang_kas.json");
const rows = [];
for (const kode of ["V1", "V2", "V3", "V4"]) {
  const f = path.join(HASIL, kode, "tabel.json");
  if (!fs.existsSync(f)) { console.error(`(lewati ${kode}: ${f} tidak ada)`); continue; }
  JSON.parse(fs.readFileSync(f, "utf8")).forEach((x, i) => {
    const uji = x.uji === "lulus" ? "uji jalan lulus" : `UJI GAGAL: ${x.bukti}`;
    rows.push({ layar: x.layar, isian: x.isian, masukan: x.masukan, harap: x.harap, hasil: x.hasil,
      catatan: `[${kode}.${i + 1}] ${uji}.${x.catatan ? " " + x.catatan : ""}` });
  });
}
// Kasus yang tidak bisa dipicu andal lewat layar sungguhan (urutan muat) — dibuktikan uji jest komponen.
const JEST = [
  { layar: "Terima pembayaran", isian: "Nominal diterima — diketik SELAGI tagihan terbuka dimuat",
    masukan: "ketik 50.000 sebelum daftar tagihan selesai dimuat (tanpa / dengan SO dibuka; 1.000.000 > sisa SO)",
    harap: "Ketikan tidak ditimpa sisa tagihan; dari baris SO: ketikan ≤ sisa → Atur sendiri sebesar ketikan, > sisa → tetap Tertua dulu (lebih bayar diputus di dialog)",
    hasil: "diperbaiki",
    catatan: "[jest] frontend/src/features/__tests__/latihVariasiTerimaBayar.test.js (gagal tanpa perbaikan). Temuan agen Hutang/Pajak/Gaji: dulu isian otomatis menimpa/bercampur dengan ketikan ('50.000' → '832.500'). Perbaikan: penanda amountTouched di ReceivePaymentModal." },
];
rows.push(...JEST);
fs.writeFileSync(OUT, JSON.stringify(rows, null, 1) + "\n");
const hit = rows.reduce((m, x) => ({ ...m, [x.hasil]: (m[x.hasil] || 0) + 1 }), {});
console.log(`${rows.length} kasus → ${path.relative(process.cwd(), OUT)} · ${JSON.stringify(hit)} · gagal uji: ${rows.filter((x) => /UJI GAGAL/.test(x.catatan)).length}`);
