/** Kerangka layar daftar seragam (gaya Pesanan Khusus): judul + aksi, KPI, cari, tab status. */
import { Search, X } from "lucide-react";

export function PageHeader({ icon: Icon, title, subtitle, actions, testId }) {
  return (
    <div className="view-header" data-testid={testId}>
      <div className="min-w-0">
        <h1 className="view-title flex items-center gap-2">{Icon && <Icon size={20} />} {title}</h1>
        {subtitle && <p className="view-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function MetricRow({ items, testId }) {
  const cols = { 3: "sm:grid-cols-3", 4: "sm:grid-cols-4", 5: "sm:grid-cols-5" }[items.length] || "sm:grid-cols-4";
  return (
    <div data-testid={testId} className={`grid grid-cols-2 gap-2 ${cols}`}>
      {items.map(({ label, value, icon: Icon, hint, tone, testId: tid }, i) => (
        <div key={label} className="metric-card" data-testid={tid || (testId ? `${testId}-${i}` : undefined)}>
          {Icon && <div className="metric-icon"><Icon size={16} /></div>}
          <div className="metric-body">
            <div className="metric-label">{label}</div>
            <div className="metric-value tabular-nums" style={tone ? { color: tone } : undefined}>{value}</div>
            {hint && <div className="metric-hint">{hint}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder, testId, children }) {
  return (
    <div className="filter-bar">
      <div className="search-box">
        <Search size={14} />
        <input data-testid={testId} type="text" placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
        {value && <button type="button" aria-label="Hapus pencarian" data-testid={testId ? `${testId}-clear` : undefined} onClick={() => onChange("")}><X size={12} /></button>}
      </div>
      {children}
    </div>
  );
}

/** tabs: [{ key, label, count? }] · testId(key) → data-testid tiap tab. */
export function StatusTabs({ tabs, value, onChange, testId, groupTestId }) {
  return (
    <div className="tab-bar" data-testid={groupTestId}>
      {tabs.map((t) => (
        <button key={t.key} type="button" data-testid={testId?.(t.key)}
          className={`tab-button ${value === t.key ? "active" : ""}`} onClick={() => onChange(t.key)}>
          {t.label}
          {t.count ? <span className="tab-badge">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
