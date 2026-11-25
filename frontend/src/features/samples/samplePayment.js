/** Kekurangan uang sample berbayar: total − uang tercatat (`paid_total` dari kwitansi); 0 bila lunas / gratis. */
export function sampleKurangBayar(o) {
  if (!o || o.sample_billing !== "paid") return 0;
  const k = Math.round(((Number(o.grand_total) || 0) - (Number(o.paid_total) || 0)) * 100) / 100;
  return k > 0.5 ? k : 0;
}

/** Pemeriksaan uang masuk untuk persetujuan bayar sample — satu aturan untuk daftar dan meja. */
export function cekUangMasukSample(o) {
  return { total: Number(o?.grand_total) || 0, masuk: Number(o?.paid_total) || 0, kurang: sampleKurangBayar(o) };
}
