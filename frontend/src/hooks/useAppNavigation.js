/**
 * useAppNavigation — state & jalur navigasi aplikasi desktop (dulu di `App.js`).
 *
 * Fase 3 · P1 (pola "gabung" §1.1) — SATU jalur navigasi untuk semua pintu masuk: sidebar, palet Ctrl+K,
 * deep link `?view=`, `openDocument` (meja/papan/jejak), notifikasi, DetailDrawer, PeriodUnlockBanner,
 * aplikasi HP (`onNavigate`) dan tautan di dalam layar (`AppNavContext.go`). Setiap pintu lewat
 * `handleNavSelect`, yang:
 *   1. menerjemahkan id lama lewat registri alias (`config/viewAliases.js`) → layar utama;
 *   2. menyimpan PRESET layar (`{ view, nonce, ...preset }`) yang dibaca layar utama lewat
 *      `useViewPreset(view)` — preset dari alias, atau `opts.preset` dari tautan;
 *   3. tetap menulis `wmsInitialTab` (kontrak lama OperationsView) bila `tab` dikirim.
 * Dulu notifikasi/drawer/banner memanggil `setActiveView` langsung → alias, preset & sorotan menu terlewat.
 */
import { useRef, useState } from "react";
import { defaultNavIdForRole, defaultViewForRole, resolveDeepLinkTarget } from "../config/navigationConfig";
import { aliasTarget, resolveAlias } from "../config/viewAliases";
import { openLogistics } from "../features/logistics/logisticsDeepLink";

export default function useAppNavigation({ role, setSidebarOpen }) {
  const [activeView, setActiveView] = useState(() => {
    const saved = JSON.parse(localStorage.getItem("kn_user") || "null");
    return saved ? defaultViewForRole(saved.role) : "sales";
  });
  const [activeNavId, setActiveNavId] = useState(() => {
    const saved = JSON.parse(localStorage.getItem("kn_user") || "null");
    return saved ? defaultNavIdForRole(saved.role) : "sales";
  });
  const [wmsInitialTab, setWmsInitialTab] = useState("stok");
  // EPIC6 — deep-link dokumen: { focus_type, focus_id } untuk auto-open di view tujuan.
  const [focusDoc, setFocusDoc] = useState(null);
  // Fase 3 · P1 — preset layar tujuan (alias / tautan): null atau { view, nonce, ...preset }.
  const [viewPreset, setViewPreset] = useState(null);
  const presetSeq = useRef(0);

  // ─── Navigation handler: receives { navId, view, tab } from grouped Sidebar ───
  // `opts.preset` (opsional) = preset eksplisit dari tautan; bila kosong dipakai preset alias.
  const handleNavSelect = (navId, view, tab, opts = {}) => {
    if (navId === "home") {
      setActiveView(defaultViewForRole(role));
      setActiveNavId(defaultNavIdForRole(role));
      setViewPreset(null);
    } else {
      const alias = resolveAlias(view || navId);
      const target = alias ? alias.to : (view || navId);
      setActiveNavId(alias?.nav || navId);
      setActiveView(target);
      if (tab) setWmsInitialTab(tab);
      const preset = opts.preset || alias?.preset || null;
      presetSeq.current += 1;
      setViewPreset(preset ? { ...preset, view: target, nonce: presetSeq.current } : null);
    }
    setSidebarOpen(false);
  };

  // Tautan berbasis NAMA LAYAR saja (notifikasi, DetailDrawer, PeriodUnlockBanner, LinkCard): menu yang
  // disorot diturunkan dari menu peran (SSOT `resolveDeepLinkTarget`); id menu/hub → tab pertama yang sah.
  // Layar di luar menu peran tetap dibuka seperti dulu (server yang menjaga datanya).
  const navigateTo = (view, opts = {}) => {
    if (!view) return;
    const t = resolveDeepLinkTarget(view, role);
    const dest = t && !t.alias ? t.view : view;
    let navId = opts.navId || t?.navId || aliasTarget(dest);
    if (navId === "home" && aliasTarget(dest) !== defaultViewForRole(role)) navId = aliasTarget(dest);
    handleNavSelect(navId, dest, opts.tab || t?.tab, opts);
  };

  // ─── EPIC6 — deep-link dokumen terkait (Process Timeline / Document Hub) ───
  // Navigasi in-app ke view tujuan + set focusDoc agar view target auto-open dokumen.
  // Cek UI UAT v3 (S15) — akun multi-PT di mode "Semua entitas": [Putuskan]/[Buka] dari meja lalu memilih PT di banner
  // me-remount layar dan dokumen tujuan hilang. Dokumen terakhir diingat lalu dibuka ulang setelah PT dipilih.
  const lastFocusRef = useRef(null);
  const openDocument = (link) => {
    if (!link || !link.view) return;
    lastFocusRef.current = link.focus_id ? { link, at: Date.now() } : null;
    handleNavSelect(link.nav_id || link.view, link.view, link.tab, { preset: link.preset });
    if (link.logistics) openLogistics(link.logistics);   // F-06 — saring daftar Logistik (mis. nomor SO untuk POD)
    if (link.focus_id) setFocusDoc({ focus_type: link.focus_type, focus_id: link.focus_id, number: link.number || "", tab: link.tab || "", from_trace: link.from_trace || null });
    else setFocusDoc(null);
  };

  return {
    activeView, setActiveView, activeNavId, setActiveNavId, wmsInitialTab,
    focusDoc, setFocusDoc, viewPreset, handleNavSelect, navigateTo, openDocument, lastFocusRef,
  };
}
