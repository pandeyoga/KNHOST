// HRD H5 — helper KPI (murni). Bulan terakhir + warna skor + rekap tertimbang.
import { todayWib } from "../../utils/formatters";

// 15 Nov — bulan berjalan menurut WIB (dulu zona perangkat). Mundur bulan dengan aritmetika (y, m) murni: dulu
// `setMonth(-1)` pada tanggal 31 bisa melompati/menggandakan bulan (31 Mar → "3 Mar" → Februari hilang).
export function lastMonths(n = 12, today = todayWib()) {
  const out = [];
  let y = Number(today.slice(0, 4));
  let m = Number(today.slice(5, 7));
  for (let i = 0; i < n; i++) {
    out.push(`${y}-${String(m).padStart(2, "0")}`);
    m -= 1;
    if (m === 0) { m = 12; y -= 1; }
  }
  return out;
}

export const curMonth = () => todayWib().slice(0, 7);

// Kelas warna teks berdasar skor (0–150).
export function scoreCls(s) {
  const v = Number(s) || 0;
  if (v >= 100) return "text-[#1F7A45]"; // hijau — tercapai
  if (v >= 80) return "text-[#0058CC]";  // biru — baik
  if (v >= 60) return "text-[#B7791F]";  // kuning — cukup
  return "text-[#C0341D]";               // merah — kurang
}

export function scoreBadge(s) {
  const v = Number(s) || 0;
  if (v >= 100) return { cls: "bg-[#E7F5EC] text-[#1F7A45]", label: "Tercapai" };
  if (v >= 80) return { cls: "bg-[#E7F0FF] text-[#0058CC]", label: "Baik" };
  if (v >= 60) return { cls: "bg-[#FBF3E2] text-[#B7791F]", label: "Cukup" };
  return { cls: "bg-[#FBEAE7] text-[#C0341D]", label: "Kurang" };
}

// Rekap rata-rata skor tertimbang (G3 D4-KPI-WEIGHT-01): bobot kosong = 1, bobot 0 tetap 0
// (tidak dihitung); seluruh bobot 0 → null (belum dapat dinilai).
const wOf = (r) => (r.weight === null || r.weight === undefined || r.weight === "" ? 1 : Math.max(Number(r.weight) || 0, 0));
export function weightedAvg(rows) {
  if (!rows || rows.length === 0) return 0;
  const tw = rows.reduce((a, r) => a + wOf(r), 0);
  if (tw <= 0) return null;
  const s = rows.reduce((a, r) => a + (Number(r.score) || 0) * wOf(r), 0);
  return Math.round((s / tw) * 10) / 10;
}

export const isCalendarMonth = (p) => /^\d{4}-(0[1-9]|1[0-2])$/.test(p || "");
