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
 *
 * PK-44 (IA-04, IA-11) — `openDocument` menurunkan menu yang disorot dari menu peran (`resolveDeepLinkTarget`, sama
 * dengan `navigateTo`; server tidak lagi mengirim `nav_id`), meneruskan `link.tab`, dan mencatat LAYAR ASAL
 * (`origin = {view, navId, tab, label, trace}`) di `focusDoc.origin` serta di `backTo` — bilah "← Kembali ke …"
 * (`components/BackToOriginBar`). `backTo` hanya berlaku untuk layar yang dituju (`at`); memilih menu lain
 * menghapusnya. Tautan kartu angka memakai `go(view, { preset: { from: { view } } })`.
 */
import { useRef, useState } from "react";
import { defaultNavIdForRole, defaultViewForRole, resolveDeepLinkTarget } from "../config/navigationConfig";
import { PAGE_META } from "../config/navMeta";
import { aliasTarget, resolveAlias } from "../config/viewAliases";
import { openLogistics } from "../features/logistics/logisticsDeepLink";
import { openTrace } from "../features/documents/trace/traceDeepLink";

/** Nama pendek layar untuk bilah kembali: judul halaman tanpa keterangan ("Jejak Dokumen (Relasi …)" → "Jejak Dokumen"). */
export const originLabel = (view) => String(PAGE_META[view]?.title || view || "").split(/\s+[(·—]/)[0].trim();

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
  // PK-44 — layar asal untuk bilah "← Kembali ke …": { view, navId, tab, label, trace, at } (at = layar tujuan).
  const [backTo, setBackTo] = useState(null);
  const focusSeq = useRef(0);

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
      // PK-44 — asal dari tautan dokumen (`opts.origin`) atau kartu angka (`preset.from`); menu lain = tanpa asal.
      const from = opts.origin || opts.preset?.from || null;
      setBackTo(from?.view && from.view !== target ? {
        navId: from.view === activeView ? activeNavId : "", tab: "", ...from,
        label: from.label || originLabel(from.view), at: target,
      } : null);
      setSidebarOpen(false);
      return;
    }
    setBackTo(null);
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
    // PK-44 — menu yang disorot diturunkan dari menu peran (cara `navigateTo`: `nav_id` eksplisit tautan meja dulu,
    // lalu `resolveDeepLinkTarget`). Peta dokumen server tidak lagi mengirim `nav_id`.
    const t = resolveDeepLinkTarget(link.view, role);
    const dest = t && !t.alias ? t.view : link.view;
    let navId = link.nav_id || t?.navId || aliasTarget(dest);
    if (navId === "home" && aliasTarget(dest) !== defaultViewForRole(role)) navId = aliasTarget(dest);
    const origin = link.origin || { view: activeView, navId: activeNavId, tab: "", label: originLabel(activeView),
      trace: link.from_trace || null };
    // `link.tab` juga sebagai preset (layar ber-`useViewPreset` menerapkannya tiap navigasi, mis. Operasi Gudang).
    const preset = link.preset || (link.tab ? { tab: link.tab } : undefined);
    handleNavSelect(navId, dest, link.tab || t?.tab, { preset, origin });
    if (link.logistics) openLogistics(link.logistics);   // F-06 — saring daftar Logistik (mis. nomor SO untuk POD)
    focusSeq.current += 1;
    if (link.focus_id) setFocusDoc({ focus_type: link.focus_type, focus_id: link.focus_id, number: link.number || "", tab: link.tab || "", from_trace: link.from_trace || null, origin, nonce: focusSeq.current });
    else setFocusDoc(null);
  };

  // PK-44 — "← Kembali ke …": jejak yang sama (jangkar `trace`) atau layar asal lewat jalur navigasi bersama.
  const goBack = (origin) => {
    const o = origin || backTo;
    setBackTo(null);
    if (!o?.view) return;
    if (o.view === "doc-trace" && o.trace?.docId) { openTrace(o.trace); return; }
    // PK-43 — asal yang membawa preset (mis. buku besar terfilter akun & rentang) dibuka lagi dengan preset itu.
    navigateTo(o.view, { navId: o.navId || undefined, tab: o.tab || undefined, preset: o.preset || undefined });
  };

  return {
    activeView, setActiveView, activeNavId, setActiveNavId, wmsInitialTab,
    focusDoc, setFocusDoc, viewPreset, handleNavSelect, navigateTo, openDocument, lastFocusRef,
    backTo: backTo && backTo.at === activeView ? backTo : null, goBack,
  };
}
