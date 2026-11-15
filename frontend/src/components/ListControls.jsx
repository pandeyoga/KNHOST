/**
 * ListControls — kontrol daftar (tab status bergaris + jumlah, cari di kiri, filter sesudahnya).
 *
 * FIX-8 (Standar UI Gudang v1 tahap 2 · B4 §3.13): berkas ini TIDAK lagi punya implementasi sendiri — `StatusTabs`
 * dan `SearchBox` adalah komponen yang sama dengan `ListPageParts` (satu versi kotak cari & tab status). API lama
 * dipertahankan: `testIdPrefix`, angka 0 tetap tampil, `SearchBox` tanpa pembungkus bilah saring.
 */
import { SearchInput, StatusTabs as BaseStatusTabs } from "./ListPageParts";

export function StatusTabs({ tabs, value, onChange, testIdPrefix = "status-tab" }) {
  return <BaseStatusTabs tabs={tabs} value={value} onChange={onChange} testIdPrefix={testIdPrefix} showZero />;
}

export function SearchBox({ value, onChange, placeholder, testId, ariaLabel }) {
  return <SearchInput value={value} onChange={onChange} placeholder={placeholder} testId={testId} ariaLabel={ariaLabel} />;
}

export function ListToolbar({ children, testId }) {
  return <div data-testid={testId} className="filter-bar mb-3">{children}</div>;
}


// Pengganti dropdown status: opsi {value,label} → tab bergaris. `countOf(value)` opsional (undefined = tanpa angka).
export function OptionTabs({ options, value, onChange, testId, countOf }) {
  return (
    <StatusTabs value={value || ""} onChange={onChange} testIdPrefix={testId}
      tabs={(options || []).map((o) => ({ key: o.value || "", label: o.label, testKey: o.value || "all",
        count: countOf ? countOf(o.value || "") : undefined }))} />
  );
}
