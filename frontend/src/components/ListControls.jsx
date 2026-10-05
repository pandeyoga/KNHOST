import { Search, XCircle } from "lucide-react";

// Standar daftar: tab status bergaris bawah + jumlah, lalu baris alat (cari di kiri, filter sesudahnya).
export function StatusTabs({ tabs, value, onChange, testIdPrefix = "status-tab" }) {
  return (
    <div className="tab-bar" data-testid={`${testIdPrefix}-bar`}>
      {tabs.map((t) => (
        <button key={t.key || "all"} type="button" data-testid={`${testIdPrefix}-${t.testKey || t.key || "all"}`}
          className={`tab-button ${value === t.key ? "active" : ""}`} onClick={() => onChange(t.key)}>
          {t.label}
          {t.count != null && <span className="tab-badge">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder, testId }) {
  return (
    <div className="search-box">
      <Search size={14} />
      <input data-testid={testId} type="text" placeholder={placeholder} value={value}
        onChange={(e) => onChange(e.target.value)} />
      {value && (
        <button type="button" data-testid={`${testId}-clear`} aria-label="Hapus pencarian" onClick={() => onChange("")}>
          <XCircle size={14} />
        </button>
      )}
    </div>
  );
}

export function ListToolbar({ children, testId }) {
  return <div data-testid={testId} className="filter-bar mb-3">{children}</div>;
}
