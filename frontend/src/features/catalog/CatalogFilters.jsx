import { useState } from "react";
import { ChevronDown, ChevronUp, RotateCcw, SlidersHorizontal } from "lucide-react";
import useDomainEnums from "../../hooks/useDomainEnums";
import KNSelect from "../../components/KNSelect";
import LineFilter from "../../components/LineFilter";

const EMPTY = { stage: "", fabric_type: "", line_code: "", color: "", supplier_id: "", lifecycle: "" };
export const emptyCatalogFilters = () => ({ ...EMPTY });
// Saringan yang jarang dipakai — tersembunyi di balik "Saringan lain" sampai dibuka atau ada yang terisi.
const EXTRA = ["fabric_type", "supplier_id", "color"];
// Ukuran ringkas yang sama dengan saringan bilah daftar lain (LineFilter, Retur Pelanggan).
const COMPACT = "!h-auto !w-auto min-w-[130px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";

/**
 * P01 IMP-15 — filter gabungan induk produk (nilai dari registry yang sama dengan master).
 * Pola UI 16 Nov (M20 — "banyak saringan"): saringan dirender SEBARIS di bilah daftar katalog (`display: contents`,
 * ikut membungkus bersama kotak cari & jumlah), dropdown ringkas "Semua …" seperti layar daftar lain. Yang tampil
 * bawaan: Tahap · Lini · Status. Jenis kain · Supplier · Warna/motif dibuka lewat "Saringan lain" (angka = yang
 * terisi; terbuka sendiri bila ada yang terisi). Lini memakai `LineFilter` bersama (mengikuti pagar lini akun;
 * tersembunyi bila hanya ada satu lini).
 */
export function CatalogFilters({ value, onChange, suppliers = [], allowedLines = [] }) {
  const { options } = useDomainEnums();
  const [more, setMore] = useState(false);
  const set = (k, v) => onChange({ ...value, [k]: v });
  const active = Object.values(value).some(Boolean);
  const extraCount = EXTRA.filter((k) => value[k]).length;
  const showExtra = more || extraCount > 0;
  const sel = (key, label, opts, all) => (
    <KNSelect data-testid={`catalog-filter-${key}`} className={COMPACT} value={value[key]}
      onValueChange={(v) => set(key, v || "")} aria-label={label}
      options={[{ value: "", label: all }, ...opts.map((o) => ({ value: o.value, label: `${label}: ${o.label}` }))]} />
  );
  return (
    <div className="contents" data-testid="catalog-filters">
      {sel("stage", "Tahap", options("stage"), "Semua tahap")}
      <LineFilter value={value.line_code} onChange={(v) => set("line_code", v || "")} allowed={allowedLines} testId="catalog-filter-line_code" />
      {sel("lifecycle", "Status", [{ value: "active", label: "SKU aktif" }, { value: "inactive", label: "SKU nonaktif" }, { value: "archived", label: "Induk diarsipkan" }], "Semua status")}
      {extraCount === 0 && (
        <button type="button" data-testid="catalog-filter-more" className="secondary-button btn-sm" aria-expanded={showExtra}
          onClick={() => setMore((v) => !v)}>
          <SlidersHorizontal size={13} aria-hidden="true" />{showExtra ? "Lebih sedikit" : "Saringan lain"}
          {showExtra ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
        </button>
      )}
      {showExtra && <>
        {sel("fabric_type", "Jenis kain", options("fabric_type"), "Semua jenis kain")}
        {sel("supplier_id", "Supplier", suppliers.map((s) => ({ value: s.id, label: s.name })), "Semua supplier")}
        <input data-testid="catalog-filter-color" className="field w-36 !py-1.5 text-fs-13" placeholder="Warna / motif…" aria-label="Cari warna / motif"
               value={value.color} onChange={(e) => set("color", e.target.value)} />
      </>}
      {active && <button type="button" data-testid="catalog-filter-reset" className="secondary-button btn-sm" onClick={() => { setMore(false); onChange(emptyCatalogFilters()); }}><RotateCcw size={12} />Reset</button>}
    </div>
  );
}
