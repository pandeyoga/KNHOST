/**
 * designerMeta (PS-18) — kosakata & warna **KPI Desainer** di satu tempat.
 *
 * Semua istilah dibuat awam: yang dibaca pemilik usaha adalah "tepat waktu",
 * "diulang", "terlambat" — bukan "on-time ratio" atau "rework rate".
 */

/** Pilihan periode (fallback bila backend belum mengirim `period_options`). */
export const PERIOD_OPTIONS = [
  { value: "month", label: "Bulan ini" },
  { value: "30d", label: "30 hari terakhir" },
  { value: "90d", label: "90 hari terakhir" },
  { value: "all", label: "Semua waktu" },
];

/** Warna & arti huruf grade — memakai palet yang sudah dipakai layar R&D. */
export const GRADE_META = {
  A: { cls: "pill-success", tone: "#1B7F4B", label: "A" },
  B: { cls: "pill-info", tone: "#0058CC", label: "B" },
  C: { cls: "pill-warning", tone: "#B26A00", label: "C" },
  D: { cls: "pill-danger", tone: "#C0392B", label: "D" },
  "—": { cls: "pill-muted", tone: "#8E8E93", label: "—" },
};

export const gradeMeta = (letter) => GRADE_META[letter] || GRADE_META["—"];

/** Warna angka persentase: makin tinggi makin baik (on-time, ACC). */
export function goodPctTone(value) {
  if (value === null || value === undefined) return "#8E8E93";
  if (value >= 90) return "#1B7F4B";
  if (value >= 70) return "#0058CC";
  if (value >= 50) return "#B26A00";
  return "#C0392B";
}

/** Warna angka persentase: makin tinggi makin BURUK (rework). */
export function badPctTone(value) {
  if (value === null || value === undefined) return "#8E8E93";
  if (value <= 10) return "#1B7F4B";
  if (value <= 30) return "#0058CC";
  if (value <= 50) return "#B26A00";
  return "#C0392B";
}

/** Tampilkan angka atau tanda "belum ada data" — jangan pernah 0 palsu. */
export const num = (v, suffix = "") =>
  v === null || v === undefined ? "—" : `${v}${suffix}`;

/** Pecahan bobot setelah dinormalkan ke 100% (server membagi dengan total bobot komponen yang punya data). */
export function normalizedWeights(w) {
  if (!w) return null;
  const raw = { on_time: Number(w.on_time) || 0, score: Number(w.score) || 0, acc: Number(w.acc) || 0, design: Number(w.design) || 0 };
  const total = raw.on_time + raw.score + raw.acc + raw.design;
  const pct = (v) => (total > 0 ? Math.round((v * 1000) / total) / 10 : 0);
  return { total, on_time: pct(raw.on_time), score: pct(raw.score), acc: pct(raw.acc), design: pct(raw.design) };
}

const pctId = (v) => `${String(v).replace(".", ",")}%`;

/** Kalimat penjelas cara nilai dihitung (dibaca pemilik, bukan developer).
 *  UAT 24 Okt (audit UI tahap 2) — G5-38: dulu bobot mentah 40% + 40% + 20% + 20% (= 120%) ditampilkan sebagai
 *  persen. Server (`rnd_kpi_service.compute_grade`) MENORMALKAN bobot: nilai = Σ(bobot × komponen) ÷ Σ bobot.
 *  Kalimat kini memakai porsi hasil normalisasi (jumlah 100%) dan menyebut angka setelan aslinya. */
export function gradeFormula(w) {
  if (!w) return "";
  const n = normalizedWeights(w);
  const head = n && n.total > 0
    ? `Nilai = tepat waktu ${pctId(n.on_time)} + skor penilaian ${pctId(n.score)} + ` +
      `sekali-jadi (ACC) ${pctId(n.acc)} + nilai versi desain ${pctId(n.design)} ` +
      `(skala 0–2 dikonversi ×50 menjadi 0–100)`
    : "Nilai = gabungan tepat waktu, skor penilaian, sekali-jadi (ACC), dan nilai versi desain";
  const note = n && n.total > 0 && Math.round(n.total) !== 100
    ? ` Porsi ini hasil penyetaraan dari setelan bobot ${w.on_time} : ${w.score} : ${w.acc} : ${w.design ?? 0} (jumlah ${n.total}) menjadi 100%.`
    : "";
  return (
    `${head}, lalu dikurangi penalti pengulangan ` +
    `(${w.penalty_rework}× persen diulang) dan penalti keterlambatan ` +
    `(${w.penalty_overdue}× persen terlambat).${note}`
  );
}

/** Label tingkat eskalasi untuk papan SLA. */
export const TIER_META = {
  manager: { label: "Manajer", cls: "pill-warning" },
  admin: { label: "Manajer + Admin", cls: "pill-danger" },
};
export const tierMeta = (tier) => TIER_META[tier] || TIER_META.manager;
