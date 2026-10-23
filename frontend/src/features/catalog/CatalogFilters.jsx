import { RotateCcw } from "lucide-react";
import useDomainEnums from "../../hooks/useDomainEnums";
import KNSelect from "../../components/KNSelect";

const EMPTY = { stage: "", fabric_type: "", line_code: "", color: "", supplier_id: "", lifecycle: "" };
export const emptyCatalogFilters = () => ({ ...EMPTY });

/** P01 IMP-15 — filter gabungan induk produk (nilai dari registry yang sama dengan master). */
export function CatalogFilters({ value, onChange, suppliers = [] }) {
  const { options } = useDomainEnums();
  const set = (k, v) => onChange({ ...value, [k]: v });
  const active = Object.values(value).some(Boolean);
  const sel = (key, label, opts) => (
    <KNSelect data-testid={`catalog-filter-${key}`} className="field !w-auto !py-1.5 text-xs" value={value[key]}
      onValueChange={(v) => set(key, v)} aria-label={label}
      options={[{ value: "", label: `${label}: semua` }, ...opts.map((o) => ({ value: o.value, label: o.label }))]} />
  );
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="catalog-filters">
      {sel("stage", "Tahap", options("stage"))}
      {sel("fabric_type", "Jenis kain", options("fabric_type"))}
      {sel("line_code", "Lini", options("product_line"))}
      {sel("supplier_id", "Supplier", suppliers.map((s) => ({ value: s.id, label: s.name })))}
      {sel("lifecycle", "Status", [{ value: "active", label: "SKU aktif" }, { value: "inactive", label: "SKU nonaktif" }, { value: "archived", label: "Induk diarsipkan" }])}
      <input data-testid="catalog-filter-color" className="field !w-40 !py-1.5 text-xs" placeholder="Warna / motif"
             value={value.color} onChange={(e) => set("color", e.target.value)} />
      {active && <button data-testid="catalog-filter-reset" className="secondary-button !py-1 text-xs" onClick={() => onChange(emptyCatalogFilters())}><RotateCcw size={12} />Reset</button>}
    </div>
  );
}
