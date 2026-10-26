import { EyeOff } from "lucide-react";
import FilterChips from "../../components/FilterChips";

// Fase 4 · R2 (L-01) — pil hitam buatan sendiri → `FilterChips multiple` (aria-pressed, gaya chip baku, satu baris
// bergulir di HP). Testid kolom tetap (`export-col-<key>`).

export default function ColumnPicker({ dataset, selected, onChange }) {
  const groups = {};
  dataset.columns.forEach((c) => {
    const g = c.source === "base" ? dataset.label : `Relasi: ${c.source_label}`;
    (groups[g] = groups[g] || []).push(c);
  });
  const toggle = (k) => onChange(selected.includes(k) ? selected.filter((x) => x !== k) : [...selected, k]);

  return (
    <div data-testid="export-column-picker" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <button type="button" data-testid="export-columns-all" className="text-[#0058CC] font-semibold"
                onClick={() => onChange(dataset.columns.map((c) => c.key))}>Pilih semua</button>
        <span className="text-[#D0D0D5]">·</span>
        <button type="button" data-testid="export-columns-base" className="text-[#0058CC] font-semibold"
                onClick={() => onChange(dataset.columns.filter((c) => c.source === "base").map((c) => c.key))}>Hanya kolom utama</button>
        <span className="text-[#D0D0D5]">·</span>
        <button type="button" data-testid="export-columns-none" className="text-[#6B6B73] font-semibold"
                onClick={() => onChange([])}>Kosongkan</button>
        <span className="ml-auto text-[#6B6B73]" data-testid="export-columns-count">{selected.length} kolom dipilih</span>
      </div>
      {Object.entries(groups).map(([g, cols]) => (
        <div key={g}>
          <p className="text-[11px] font-bold text-[#3A3A3C] mb-1">{g}</p>
          {/* Urutan kolom ekspor = urutan dicentang (sama seperti dulu): chip yang berubah di-toggle satu per satu. */}
          <FilterChips multiple className="!flex-wrap" ariaLabel={`Kolom ${g}`}
            value={selected.filter((k) => cols.some((c) => c.key === k))}
            onChange={(next) => {
              const cur = selected.filter((k) => cols.some((c) => c.key === k));
              const k = next.find((x) => !cur.includes(x)) || cur.find((x) => !next.includes(x));
              if (k) toggle(k);
            }}
            options={cols.map((c) => ({ key: c.key, label: c.label, testId: `export-col-${c.key}` }))} />
        </div>
      ))}
      {dataset.hidden_columns.length > 0 && (
        <p data-testid="export-hidden-columns" className="flex items-start gap-1.5 text-[11.5px] text-[#8E8E93]">
          <EyeOff size={12} className="mt-0.5 shrink-0" />
          Tidak tersedia untuk peran Anda: {dataset.hidden_columns.map((h) => h.label).join(", ")}
        </p>
      )}
    </div>
  );
}
