/**
 * PageTabs — TAB TINGKAT-2 baku di dalam satu layar (fase 3 · P1, aturan L-01 §1.4 rencana fase 3).
 *
 * Aturan tab maksimal 2 tingkat: tingkat 1 = HubTabs (bilah hub, di atas layar), tingkat 2 = PageTabs.
 * Saringan BUKAN tab — pakai `FilterChips` atau KNSelect. Kebutuhan tingkat ke-3 → chip, seksi berjudul,
 * atau pop-up. Pil hitam (`rounded-full … bg-[#1C1C1E]`), tombol-toggle `primary-button !py-1.5`, `TabBtn`
 * buatan sendiri dan `cfg-group-btn` dijaga ratchet `scripts/guardrails/verify_page_tabs.py` (hanya boleh turun).
 *
 * Tampilan = `.tab-bar` + `.tab-button` (garis bawah biru, sama dengan StatusTabs). Di layar ≤640 px bilah
 * tidak membungkus: satu baris yang bisa digeser, tab aktif digulir ke pandangan.
 *
 *   <PageTabs testId="orders-tabs" value={tab} onChange={setTab} tabs={[
 *     { key: "dashboard", label: "Dasbor & Analitik", icon: BarChart3, testId: "tab-dashboard" },
 *     { key: "list", label: "Daftar Pesanan", count: 12, testId: "tab-list" },
 *   ]} />
 *
 * Props: `tabs` [{ key, label, count?, icon?, testId?, disabled?, hidden?, title? }] · `value` · `onChange(key)`
 *        · `testId` (bilah; bawaan testid tab = `${testId}-${key}`) · `tabTestId(key)` · `ariaLabel` · `className`.
 * `count` 0 tidak ditampilkan kecuali `showZero: true` pada tab itu.
 */
import { useEffect, useRef } from "react";

export default function PageTabs({
  tabs = [], value, onChange, testId, tabTestId, ariaLabel = "Tab halaman", className = "",
}) {
  const barRef = useRef(null);
  const visible = (tabs || []).filter((t) => t && !t.hidden);
  const activeIdx = visible.findIndex((t) => t.key === value);

  // Tab aktif selalu terlihat di bilah yang bergulir (HP). Sengaja TIDAK memakai scrollIntoView supaya
  // halaman tidak ikut melompat secara vertikal.
  useEffect(() => {
    const bar = barRef.current;
    if (!bar || bar.scrollWidth <= bar.clientWidth) return;
    const el = bar.querySelector('[aria-selected="true"]');
    if (!el) return;
    const left = el.offsetLeft;
    const right = left + el.offsetWidth;
    if (left < bar.scrollLeft) bar.scrollLeft = Math.max(0, left - 8);
    else if (right > bar.scrollLeft + bar.clientWidth) bar.scrollLeft = right - bar.clientWidth + 8;
  }, [value]);

  if (visible.length === 0) return null;

  const tidOf = (t) => t.testId || (tabTestId ? tabTestId(t.key) : (testId ? `${testId}-${t.key}` : undefined));
  const select = (t) => { if (!t.disabled && t.key !== value) onChange?.(t.key); };

  // Papan tombol (pola WAI-ARIA tabs): ←/→ pindah tab, Home/End ke ujung.
  const onKeyDown = (e, idx) => {
    const enabled = visible.map((t, i) => (t.disabled ? -1 : i)).filter((i) => i >= 0);
    if (!enabled.length) return;
    const pos = enabled.indexOf(idx);
    let next = null;
    if (e.key === "ArrowRight") next = enabled[(pos + 1) % enabled.length];
    else if (e.key === "ArrowLeft") next = enabled[(pos - 1 + enabled.length) % enabled.length];
    else if (e.key === "Home") next = enabled[0];
    else if (e.key === "End") next = enabled[enabled.length - 1];
    if (next === null) return;
    e.preventDefault();
    select(visible[next]);
    barRef.current?.querySelectorAll('[role="tab"]')[next]?.focus();
  };

  return (
    <div ref={barRef} role="tablist" aria-label={ariaLabel} data-testid={testId}
      className={`tab-bar page-tabs ${className}`.trim()}>
      {visible.map((t, i) => {
        const active = i === activeIdx;
        const Icon = t.icon;
        const showCount = t.count !== undefined && t.count !== null && t.count !== ""
          && (Number(t.count) !== 0 || t.showZero);
        return (
          <button key={t.key} type="button" role="tab" aria-selected={active}
            tabIndex={active || (activeIdx < 0 && i === 0) ? 0 : -1}
            data-testid={tidOf(t)} disabled={t.disabled} title={t.title}
            className={`tab-button ${active ? "active" : ""}`.trim()}
            onClick={() => select(t)} onKeyDown={(e) => onKeyDown(e, i)}>
            {Icon ? <Icon size={14} className="tab-icon" aria-hidden="true" /> : null}
            <span>{t.label}</span>
            {showCount ? <span className="tab-badge">{t.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
