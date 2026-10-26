/**
 * agingBuckets — SATU definisi kelompok umur untuk layar Piutang (`ar-aging`) dan Uang Muka Pelanggan
 * (`advance-report`). Fase 3 · P4 (D-12, butir B).
 *
 * KENAPA ADA: dua layar menampilkan "umur" dengan kelompok berbeda — Piutang: Lancar / 1-30 / 31-60 / 61-90 / 90+;
 * Uang Muka: ≤ 30 / 31–60 / 61–90 / > 90 hari, dengan warna & label sendiri. Pengguna membaca dua layar itu
 * berdampingan (uang muka = piutang negatif) dan mengira batasnya beda. Keputusan pemilik D-12 B: layar dibiarkan,
 * kelompok umurnya disamakan lewat util ini (label, batas hari, warna).
 *
 * Batas sama dengan server (`ar_aging_service` & `advance_report_service`: ≤30, ≤60, ≤90, >90).
 *  · Piutang: umur = hari lewat jatuh tempo; "Lancar" = belum jatuh tempo (server mengisi `current`).
 *  · Uang Muka: umur = hari sejak kwitansi pertama; "Lancar" = diterima hari ini (umur 0 hari).
 */
export const AGING_BUCKETS = [
  { key: "current", label: "Lancar", short: "Lancar", tone: "#1B7F4B", bg: "#E6F6EC" },
  { key: "b1_30", label: "1-30 hr", short: "1-30", tone: "#B45309", bg: "#FDF3E7" },
  { key: "b31_60", label: "31-60 hr", short: "31-60", tone: "#B45309", bg: "#FDF3E7" },
  { key: "b61_90", label: "61-90 hr", short: "61-90", tone: "#C0392B", bg: "#FCEBEA" },
  { key: "b90_plus", label: "90+ hr", short: "90+", tone: "#C0392B", bg: "#FCEBEA" },
];

export const AGING_KEYS = AGING_BUCKETS.map((b) => b.key);

/** Kelompok untuk umur `days` (≤ 0 → "current"). */
export function bucketForDays(days) {
  const d = Number(days);
  if (!Number.isFinite(d) || d <= 0) return "current";
  if (d <= 30) return "b1_30";
  if (d <= 60) return "b31_60";
  if (d <= 90) return "b61_90";
  return "b90_plus";
}

/** Metadata kelompok (label/warna) dari kuncinya; kunci tak dikenal → "Lancar". */
export function bucketMeta(key) {
  return AGING_BUCKETS.find((b) => b.key === key) || AGING_BUCKETS[0];
}

/** Jumlahkan `amountOf(item)` per kelompok umur `daysOf(item)` → { current, b1_30, b31_60, b61_90, b90_plus }. */
export function sumByBucket(items, daysOf, amountOf) {
  const out = Object.fromEntries(AGING_KEYS.map((k) => [k, 0]));
  for (const it of items || []) {
    const k = bucketForDays(daysOf(it));
    out[k] = Math.round((out[k] + Number(amountOf(it) || 0)) * 100) / 100;
  }
  return out;
}
