/** Hub tab bar (Restrukturisasi IA) — navigasi sekunder antar-view dalam satu proses bisnis = TAB TINGKAT-1.
 *  Tab boleh punya `section` (IA 2026-10): tab dikelompokkan per seksi (urutan kemunculan pertama).
 *
 *  Fase 3 · P1 (L-01 §1.4 rencana fase 3) — gaya BAKU `.tab-bar.hub-tabs`: garis bawah biru, 13 px tebal, SATU
 *  baris (di ≤640 px digeser, tidak membungkus). Dulu pil hitam membungkus 4–5 baris dengan label seksi
 *  disisipkan di tengah baris (Pengaturan ±20 pil). Kini seksi dipisah garis tipis di dalam bilah, dan nama
 *  seksi tab aktif tampil sebagai sub-judul tipis DI BAWAH bilah. Tingkat 2 di dalam layar = `PageTabs`.
 *  Testid dipertahankan (`hub-tabs-<hub>`, `hub-tab-<view>`, `hub-section-<hub>-<seksi>`) — dipakai tur
 *  `data/tours/*` dan crawler. */
const TabButton = ({ t, active, onSelect }) => (
  <button
    type="button"
    data-testid={`hub-tab-${t.view}`}
    onClick={() => onSelect(t.view, t.tab)}
    className={`tab-button ${active ? "active" : ""}`.trim()}
    aria-current={active ? "page" : undefined}
    title={t.section ? `${t.section} › ${t.label}` : t.label}
  >
    {t.label}
  </button>
);

export const HubTabs = ({ hubId, tabs, activeView, onSelect }) => {
  if (!tabs || tabs.length < 2) return null;
  // UAT 24 Okt (P16.3) — kelompokkan per NAMA seksi (urutan kemunculan pertama), bukan hanya tab yang
  // berurutan: tab "Divisi & Persetujuan R&D" di ujung daftar dulu memunculkan label "Organisasi & Akses"
  // dua kali (dan key React ganda).
  const sections = [];
  const byName = {};
  tabs.forEach((t) => {
    const name = t.section || "";
    if (!byName[name]) { byName[name] = { name, tabs: [] }; sections.push(byName[name]); }
    byName[name].tabs.push(t);
  });
  const activeSection = (tabs.find((t) => t.view === activeView) || {}).section || "";
  return (
    <nav className="hub-tabs-wrap no-print" aria-label="Tab menu">
      <div data-testid={`hub-tabs-${hubId}`} className="tab-bar hub-tabs">
        {sections.map((s, i) => (
          <span key={s.name || "_"} className="hub-tabs-section" title={s.name || undefined}
            data-testid={s.name ? `hub-section-${hubId}-${s.name}` : undefined}>
            {i > 0 && <span className="hub-tabs-sep" aria-hidden="true" />}
            {s.tabs.map((t) => <TabButton key={t.view} t={t} active={t.view === activeView} onSelect={onSelect} />)}
          </span>
        ))}
      </div>
      {activeSection && sections.length > 1 && (
        <p className="hub-tabs-caption" data-testid={`hub-section-caption-${hubId}`}>{activeSection}</p>
      )}
    </nav>
  );
};

export default HubTabs;
