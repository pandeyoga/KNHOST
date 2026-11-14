// Pratinjau menu yang akan terlihat oleh peran dengan tingkat akses tertentu.
// PR-T6 — peran BAWAAN: pewarisnya peran itu sendiri + `navAdded` (menu yang dibuka izin di luar izin bawaannya, dari
// pratinjau server); menu/tab tambahan diberi tanda "baru". Peran kustom: menu dari tingkat modul + peran dasar.
import { useMemo } from "react";
import { Menu } from "lucide-react";

import { buildNavGroups, hubTabsForRole } from "../../../config/navigationConfig";
import { setPreviewAccess, setPreviewRoleNav } from "../../../config/roles";

const viewResources = (modules) => {
  const idx = {};
  modules.forEach((m) => (m.nav || []).forEach((v) => { idx[v] = [...new Set([...(idx[v] || []), ...m.resources])]; }));
  return idx;
};

const ALWAYS_NAV = ["hr-my-profile"];

/** Cermin `access_modules.nav_for_levels` di server. */
export function navForLevels(modules, levels) {
  const add = new Set(ALWAYS_NAV);
  const remove = new Set();
  for (const m of modules) {
    const lvl = levels[m.id] || "none";
    (m.nav || []).forEach((id) => (lvl === "none" ? remove : add).add(id));
  }
  add.forEach((id) => remove.delete(id));
  return { add: [...add], remove: [...remove] };
}

/** Grup menu terstruktur untuk satu aturan pratinjau: [{id, label, items: [{label, tabs: [label]}]}]. */
function previewGroups(rule, perms, hidden, modules) {
  setPreviewRoleNav(rule);
  setPreviewAccess(perms || {}, [...(hidden || [])], viewResources(modules));
  const tabsOf = (hub) => (hub ? hubTabsForRole(hub, "__preview").map((t) => t.label) : []);
  const out = buildNavGroups("__preview", { showComingSoon: false }).map((g) => (g.type === "standalone"
    ? { id: g.id, label: g.label, items: tabsOf(g.hub).length > 1 ? tabsOf(g.hub).map((t) => ({ label: t, tabs: [] })) : [] }
    : { id: g.groupId, label: g.label, items: (g.items || []).map((it) => {
      const tabs = tabsOf(it.hub);
      return { label: it.label, tabs: tabs.length > 1 ? tabs : [] };
    }) }));
  setPreviewRoleNav(null);
  setPreviewAccess(null);
  return out;
}

function NewMark({ on }) {
  return on ? <span className="ml-0.5 rounded-full bg-kn-success-soft px-1 font-semibold text-kn-success-text" data-testid="role-menu-preview-new">baru</span> : null;
}

export default function RoleMenuPreview({ modules, levels, baseRole, perms, hidden, builtinId = "", navAdded = [] }) {
  const { groups, fresh } = useMemo(() => {
    if (builtinId) {
      const base = previewGroups({ inherit: builtinId, add: [], remove: [] }, perms, hidden, modules);
      const now = previewGroups({ inherit: builtinId, add: navAdded || [], remove: [] }, perms, hidden, modules);
      const known = new Set(base.flatMap((g) => [`g:${g.id}`, ...g.items.flatMap((it) => [`i:${g.id}:${it.label}`,
        ...it.tabs.map((t) => `t:${g.id}:${it.label}:${t}`)])]));
      return { groups: now, fresh: (key) => !known.has(key) };
    }
    const nav = navForLevels(modules, levels);
    return { groups: previewGroups({ inherit: baseRole || null, add: nav.add, remove: nav.remove }, perms, hidden, modules),
      fresh: () => false };
  }, [modules, levels, baseRole, perms, hidden, builtinId, navAdded]);

  const total = groups.reduce((n, g) => n + Math.max(1, g.items.length), 0);
  return (
    <div className="rounded-md border border-kn-divider bg-white p-2.5" data-testid="role-menu-preview">
      <div className="mb-1.5 flex items-center gap-1.5">
        <Menu size={13} className="text-kn-action" />
        <p className="kicker !mb-0">Pratinjau menu ({total} layar)</p>
      </div>
      {groups.length === 0 ? (
        <p className="text-fs-12 text-kn-danger-text" data-testid="role-menu-preview-empty">
          Tidak ada menu yang akan terlihat. Nyalakan minimal satu modul.
        </p>
      ) : (
        <ul className="max-h-72 space-y-1 overflow-auto pr-1">
          {groups.map((g) => (
            <li key={g.id} data-testid={`role-menu-preview-${g.id}`}>
              <p className="text-fs-12 font-bold text-kn-text">{g.label}<NewMark on={fresh(`g:${g.id}`)} /></p>
              {g.items.length > 0 && (
                <p className="text-fs-12 leading-snug text-kn-text-2">
                  {g.items.map((it, i) => (
                    <span key={it.label}>
                      {i > 0 && " · "}{it.label}<NewMark on={!fresh(`g:${g.id}`) && fresh(`i:${g.id}:${it.label}`)} />
                      {it.tabs.length > 0 && <> ({it.tabs.map((t, j) => <span key={t}>{j > 0 && " · "}{t}<NewMark on={!fresh(`i:${g.id}:${it.label}`) && fresh(`t:${g.id}:${it.label}:${t}`)} /></span>)})</>}
                    </span>
                  ))}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-1.5 text-fs-12 text-kn-text-2" data-testid="role-menu-preview-note">
        Daftar ini hanya menu. Lihat Ringkasan peran untuk apa yang bisa dilakukan.
      </p>
    </div>
  );
}
