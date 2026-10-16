/** L01 LN-015 — tingkat Menu → Tab dalam satu modul: centang = tampil untuk peran ini.
 *  Menyembunyikan tab tidak memberi/mencabut izin aktivitas; server tetap menjaga API. */
import { HUB_TABS } from "../../../config/hubTabs";
import { PAGE_META } from "../../../config/navMeta";
import { NAV_STRUCTURE } from "../../../config/navStructure";

const NAV_LABEL = (() => {
  const out = {};
  const walk = (list) => (list || []).forEach((e) => {
    if (e.id && e.label) out[e.id] = e.label;
    if (e.groupId && e.label) out[e.groupId] = e.label;
    walk(e.items);
  });
  walk(NAV_STRUCTURE);
  Object.values(HUB_TABS).flat().forEach((t) => { if (!out[t.view]) out[t.view] = t.label; });
  return out;
})();
export const titleOf = (id) => NAV_LABEL[id] || PAGE_META[id]?.title || id;

export function navTree(module) {
  const nav = new Set(module.nav || []);
  const menus = [];
  const used = new Set();
  Object.entries(HUB_TABS).forEach(([hub, tabs]) => {
    const inMod = tabs.filter((t) => nav.has(t.view) && !t.hidden);
    if (!inMod.length) return;
    inMod.forEach((t) => used.add(t.view));
    used.add(hub);
    menus.push({ id: hub, label: titleOf(hub), tabs: inMod.map((t) => ({ id: t.view, label: t.label })) });
  });
  const single = [...nav].filter((v) => !used.has(v) && !HUB_TABS[v]);
  if (single.length) menus.push({ id: `${module.id}-lain`, label: "Menu lain", tabs: single.map((v) => ({ id: v, label: titleOf(v) })) });
  return menus;
}

export default function RoleNavTree({ module, hidden, original, disabled, off, onToggle, onSetMany }) {
  const menus = navTree(module);
  if (!menus.length) return null;
  return (
    <div className="space-y-1.5" data-testid={`role-nav-tree-${module.id}`}>
      <p className="text-[10px] font-semibold text-[#3A3A3C]">Menu & tab yang tampil {off && <span className="font-normal text-[#A8221A]">· modul “Tidak ada”: semua tersembunyi</span>}</p>
      {menus.map((m) => {
        const shown = m.tabs.filter((t) => !hidden.has(t.id)).length;
        const state = shown === 0 ? "none" : shown === m.tabs.length ? "all" : "partial";
        return (
          <div key={m.id} className="rounded-md border border-[#EFF0F2] bg-white px-2.5 py-1.5" data-testid={`role-nav-menu-${module.id}-${m.id}`}>
            <label className="flex items-center gap-1.5 text-[11px] font-bold">
              <input type="checkbox" disabled={disabled || off} data-testid={`role-nav-menu-check-${module.id}-${m.id}`}
                     checked={state === "all"} ref={(el) => { if (el) el.indeterminate = state === "partial"; }}
                     onChange={() => onSetMany(m.tabs.map((t) => t.id), state !== "all")} />
              {m.label} <span className="font-normal text-[#8E8E93]">{shown}/{m.tabs.length} tab</span>
            </label>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 pl-5">
              {m.tabs.map((t) => {
                const changed = original.has(t.id) !== hidden.has(t.id);
                return (
                  <label key={t.id} className={`flex items-center gap-1 text-[10.5px] ${changed ? "font-semibold text-[#8C4A00]" : "text-[#3C3C43]"}`}>
                    <input type="checkbox" disabled={disabled || off} data-testid={`role-nav-tab-${module.id}-${t.id}`}
                           checked={!hidden.has(t.id)} onChange={() => onToggle(t.id)} />
                    {t.label}
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
