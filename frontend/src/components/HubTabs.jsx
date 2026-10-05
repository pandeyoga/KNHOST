/** Hub tab bar (Restrukturisasi IA) — navigasi sekunder antar-view dalam satu proses bisnis.
 *  Tab boleh punya `section` (IA 2026-10): label seksi tampil saat seksi berganti. */
const TabButton = ({ t, active, onSelect }) => (
  <button
    data-testid={`hub-tab-${t.view}`}
    onClick={() => onSelect(t.view, t.tab)}
    className={`px-3.5 py-1.5 rounded-full text-[12.5px] font-semibold border transition-colors ${
      active
        ? "bg-[#1C1C1E] text-white border-[#1C1C1E]"
        : "bg-white text-[#3A3A3C] border-[#E5E5EA] hover:border-[#1C1C1E]/40 hover:bg-[#F7F7F9]"
    }`}
    aria-current={active ? "page" : undefined}
  >
    {t.label}
  </button>
);

export const HubTabs = ({ hubId, tabs, activeView, onSelect }) => {
  if (!tabs || tabs.length < 2) return null;
  const sections = [];
  tabs.forEach((t) => {
    const last = sections[sections.length - 1];
    if (last && last.name === (t.section || "")) last.tabs.push(t);
    else sections.push({ name: t.section || "", tabs: [t] });
  });
  return (
    <div data-testid={`hub-tabs-${hubId}`} className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-3 no-print">
      {sections.map((s) => (
        <div key={s.name || "_"} className="flex flex-wrap items-center gap-1.5" data-testid={s.name ? `hub-section-${hubId}-${s.name}` : undefined}>
          {s.name && <span className="mr-0.5 text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{s.name}</span>}
          {s.tabs.map((t) => <TabButton key={t.view} t={t} active={t.view === activeView} onSelect={onSelect} />)}
        </div>
      ))}
    </div>
  );
};

export default HubTabs;
