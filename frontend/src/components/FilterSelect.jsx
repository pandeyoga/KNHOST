/**
 * FilterSelect — saringan berbentuk DROPDOWN dengan API sama seperti `FilterChips` (pola UI 16 Nov, `04_POLA_UI.md`
 * prinsip 2: "Dropdown untuk memilih — tidak ada deret chip/tombol/tab untuk nilai saringan").
 *
 *   <FilterSelect testId="rnd-samples-status" ariaLabel="Status sample" value={status} onChange={setStatus}
 *     options={[{ key: "", label: "Semua status", count: 12 }, { key: "draft", label: "Draf", count: 3 }]} />
 *
 * Props: `options` [{ key, label, count?, hidden?, disabled? }] · `value` · `onChange(key)` · `testId` (dipasang di
 * pemicu KNSelect) · `ariaLabel` · `className` · `clearable` + `allLabel` (opsi "Semua" → `onChange(null)`). Jumlah tampil di label opsi: "Draf (3)". Satu-pilih saja; saringan
 * pilih-banyak tetap `FilterChips multiple`.
 */
import KNSelect from "./KNSelect";

export default function FilterSelect({ options = [], value, onChange, testId, ariaLabel = "Saringan", className = "",
  clearable = false, allLabel = "Semua" }) {
  let list = (options || []).filter((o) => o && !o.hidden);
  if (list.length === 0) return null;
  // Saringan yang dulu "klik chip aktif = kosongkan" (FilterChips `clearable`) → opsi "Semua" bernilai kosong (null).
  const clear = clearable && !list.some((o) => (o.key ?? "") === "");
  if (clear) list = [{ key: "", label: allLabel }, ...list];
  const withCount = (o) => (o.count !== undefined && o.count !== null && o.count !== "" ? `${o.label} (${o.count})` : o.label);
  return (
    <KNSelect data-testid={testId} aria-label={ariaLabel}
      className={`field !w-auto min-w-[160px] ${className}`.trim()}
      value={value ?? ""} onValueChange={(v) => onChange?.(clear && v === "" ? null : v)}
      options={list.map((o) => ({ value: o.key ?? "", label: withCount(o), disabled: o.disabled }))} />
  );
}
