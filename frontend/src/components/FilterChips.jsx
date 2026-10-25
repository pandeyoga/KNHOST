/**
 * FilterChips — SARINGAN segmen baku (fase 3 · P1, L-01 §1.4): pengganti pil/segmented buatan sendiri.
 *
 * Saringan bukan tab: tab memindah ISI layar (PageTabs), chip menyaring daftar yang SAMA. Dengan begitu
 * aturan "tab maksimal 2 tingkat" terjaga — kebutuhan tingkat ke-3 menjadi chip.
 *
 *   <FilterChips testId="trf-kind" value={kind} onChange={setKind} options={[
 *     { key: "all", label: "Semua", count: 14 },
 *     { key: "warehouse", label: "Antar gudang", count: 9 },
 *     { key: "inter_entity", label: "Antar PT", count: 5 },
 *   ]} />
 *   // pilih banyak: <FilterChips multiple value={["labdip","handfeel"]} onChange={setTypes} options={…} />
 *
 * Props: `options` [{ key, label, count?, icon?, testId?, disabled?, hidden?, title? }] · `value` (kunci, atau
 *        array bila `multiple`) · `onChange(next)` · `multiple` · `clearable` (satu-pilih: klik chip aktif →
 *        `onChange(null)`) · `testId` (bawaan testid chip = `${testId}-${key}`) · `chipTestId(key)` · `ariaLabel`
 *        · `className`. Chip memakai `aria-pressed` (tombol saklar), bukan peran tab.
 */
export default function FilterChips({
  options = [], value, onChange, multiple = false, clearable = false,
  testId, chipTestId, ariaLabel = "Saringan", className = "",
}) {
  const list = (options || []).filter((o) => o && !o.hidden);
  if (list.length === 0) return null;
  const chosen = multiple ? (Array.isArray(value) ? value : []) : value;
  const isOn = (k) => (multiple ? chosen.includes(k) : chosen === k);
  const toggle = (o) => {
    if (o.disabled) return;
    if (multiple) {
      onChange?.(chosen.includes(o.key) ? chosen.filter((k) => k !== o.key) : [...chosen, o.key]);
    } else if (chosen === o.key) {
      if (clearable) onChange?.(null);
    } else {
      onChange?.(o.key);
    }
  };
  const tidOf = (o) => o.testId || (chipTestId ? chipTestId(o.key) : (testId ? `${testId}-${o.key}` : undefined));
  return (
    <div role="group" aria-label={ariaLabel} data-testid={testId} className={`filter-chips ${className}`.trim()}>
      {list.map((o) => {
        const on = isOn(o.key);
        const Icon = o.icon;
        return (
          <button key={o.key} type="button" aria-pressed={on} data-testid={tidOf(o)}
            disabled={o.disabled} title={o.title}
            className={`filter-chip ${on ? "active" : ""}`.trim()} onClick={() => toggle(o)}>
            {Icon ? <Icon size={12} aria-hidden="true" /> : null}
            <span>{o.label}</span>
            {o.count !== undefined && o.count !== null && o.count !== ""
              ? <span className="filter-chip-count">{o.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
