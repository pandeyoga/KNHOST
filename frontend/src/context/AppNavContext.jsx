/**
 * AppNavContext (fase 3 · P1) — SATU jalur navigasi untuk tautan di dalam layar.
 *
 * KENAPA ADA: pola "gabung" (§1.1–1.2 rencana fase 3) mengganti tabel/form duplikat dengan
 * KARTU TAUTAN ke layar utama (`components/LinkCard.jsx`) dan tombol "Buka di …". Tautan itu harus
 * lewat jalur yang sama dengan sidebar (alias → layar utama, preset, sorotan menu, gerbang peran),
 * bukan `setActiveView` sendiri-sendiri. Konteks ini diberikan oleh `AppViewRouter.jsx`.
 *
 *   const { go, canOpen, openDocument } = useAppNav();
 *   if (canOpen("pdf-templates")) go("pdf-templates", { preset: { tab: "dasar" } });
 *   go("special-orders", { focus: { type: "special_order", id: so.id, number: so.number } });
 *
 *  · `go(view, { preset, tab, navId, focus })` — `view` boleh id lama (alias). `focus` → dokumen
 *    dibuka otomatis di layar tujuan (jalur `openDocument`/`focusDoc` yang sudah ada).
 *  · `canOpen(view)` — true bila peran aktif boleh membuka layar itu (menu + alias; SSOT
 *    `resolveDeepLinkTarget`). Server tetap penjaga terakhir.
 *  · `openDocument(link)` — jalur lama `{ view, nav_id, focus_type, focus_id, number, tab, preset }`.
 *
 * Di luar provider (mis. aplikasi HP): `go` tidak melakukan apa-apa dan `canOpen` selalu false —
 * LinkCard lalu tampil sebagai ringkasan baca-saja, bukan tombol mati.
 */
import { createContext, useContext, useMemo } from "react";
import { resolveDeepLinkTarget } from "../config/navigationConfig";

const NOOP_NAV = {
  role: "",
  go: () => {},
  canOpen: () => false,
  openDocument: () => {},
};

const AppNavContext = createContext(NOOP_NAV);

export function AppNavProvider({ role, onNavigateTo, onOpenDocument, children }) {
  const value = useMemo(() => ({
    role: role || "",
    canOpen: (view) => !!(role && view && resolveDeepLinkTarget(view, role)),
    openDocument: (link) => onOpenDocument?.(link),
    go: (view, opts = {}) => {
      if (!view) return;
      const focus = opts.focus;
      if (focus && (focus.id || focus.focus_id) && onOpenDocument) {
        onOpenDocument({
          view, nav_id: opts.navId, tab: opts.tab, preset: opts.preset,
          focus_type: focus.type || focus.focus_type, focus_id: focus.id || focus.focus_id,
          number: focus.number || "",
        });
        return;
      }
      onNavigateTo?.(view, { preset: opts.preset, tab: opts.tab, navId: opts.navId });
    },
  }), [role, onNavigateTo, onOpenDocument]);
  return <AppNavContext.Provider value={value}>{children}</AppNavContext.Provider>;
}

export const useAppNav = () => useContext(AppNavContext);

export default AppNavContext;
