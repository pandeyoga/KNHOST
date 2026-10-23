/**
 * UAT 24 Okt (P11.4) — dua status pemeriksaan sebuah roll, dibaca dari penanda DATAR di roll:
 *   MD Quality : ✓ dicek · sampling (lolos tanpa dicek, ikut keputusan SPK MD) · belum
 *   QC 4-point : ✓ diinspeksi · belum
 * Dipakai di daftar roll, detail roll, baris SPK, pilih roll pesanan, dan Lokasi Rak.
 */
export function rollCheckState(roll = {}) {
  const md = roll.md_quality_checked ? "ok" : roll.md_quality_via_sampling ? "sampling" : "none";
  const fp = roll.inspected_4point ? "ok" : "none";
  return { md, fp };
}

const MD = {
  ok: ["MDQ ✓", "bg-[#E8F6EE] text-[#1B7F4B]", "Sudah dicek MD Quality"],
  sampling: ["MDQ sampling", "bg-[#FFF4E0] text-[#8A5300]", "Lolos karantina tanpa dicek MD Quality (ikut sampel SPK)"],
  none: ["MDQ belum", "bg-[#F2F2F5] text-[#6B6B73]", "Belum dicek MD Quality"],
};
const FP = {
  ok: ["4-pt ✓", "bg-[#E8F6EE] text-[#1B7F4B]", "Sudah diinspeksi QC 4-point"],
  none: ["4-pt belum", "bg-[#F2F2F5] text-[#6B6B73]", "Belum diinspeksi QC 4-point"],
};

export default function RollCheckChips({ roll, testId = "roll-check", className = "" }) {
  if (!roll) return null;
  const { md, fp } = rollCheckState(roll);
  const spk = roll.md_quality_spk || (roll.md_quality_via_sampling || {}).spk || "";
  const chip = ([label, cls, title], key, extra = "") => (
    <span key={key} data-testid={`${testId}-${key}`} title={`${title}${extra}`}
      className={`whitespace-nowrap rounded-full px-1.5 py-[1px] text-[10px] font-bold ${cls}`}>{label}</span>
  );
  return (
    <span className={`inline-flex flex-wrap items-center gap-1 ${className}`} data-testid={testId}>
      {chip(MD[md], "md", spk ? ` · ${spk}` : "")}
      {chip(FP[fp], "4p", roll.inspected_4point_spk ? ` · ${roll.inspected_4point_spk}` : "")}
    </span>
  );
}

/** Pilihan filter stok berdasarkan status pemeriksaan (parameter `check` di GET /inventory/rolls). */
export const ROLL_CHECK_FILTERS = [
  { value: "", label: "Semua status cek" },
  { value: "no_mdq", label: "Belum dicek MD Quality" },
  { value: "mdq_sampling", label: "MDQ lewat sampling" },
  { value: "no_4point", label: "Belum 4-point" },
];
