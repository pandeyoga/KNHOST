// ─── NAVIGATION CONFIG — fungsi builder + resolver (data di navStructure/navMeta) ─
// Data besar (NAV_STRUCTURE, HUB_TABS, PAGE_META, dst.) dipindah ke file terpisah
// agar file ini di bawah batas guardrail. Public API (import lama) TETAP di sini
// via re-export supaya komponen konsumen tidak perlu berubah.
import { Clock } from "lucide-react";
import { HUB_TABS, NAV_STRUCTURE } from "./navStructure";
import { PAGE_META, ROLE_HOME_REGISTRY, GUIDANCE_MAP } from "./navMeta";
// FASE E-8 (E8.1) — SATU definisi "boleh lihat menu ini?" (termasuk dua peran baru
// `sales_admin` & `finance`). Dulu keputusannya `roles.includes(role)` yang disalin di
// 5 tempat di berkas ini; peran baru harus ditambahkan ke ~40 baris `navStructure.js`.
import { isModuleNavRole, navExplicitlyHidden, roleCanSee } from "./roles";
// Fase 3 · P1 — registri alias layar (layar duplikat = tautan ke layar utama; alamat lama tetap hidup).
import { listAliases, resolveAlias } from "./viewAliases";

/** Fase 3 · P1 — sub-judul di dalam grup sidebar (`{ type: "heading", id, label }`), bukan menu. */
export const isNavHeading = (item) => !!item && item.type === "heading";

// Re-export data (backward-compat untuk konsumen yang import dari navigationConfig).
export { HUB_TABS, NAV_STRUCTURE } from "./navStructure";
export { PAGE_META, ROLE_HOME_REGISTRY, GUIDANCE_MAP } from "./navMeta";

export function hubTabsForRole(hubId, role) {
  return (HUB_TABS[hubId] || []).filter((t) => !t.hidden && roleCanSee(t.roles, role, t.view));
}

// ─── KLASIFIKASI VIEW (SSOT — dipakai App.js, jangan disalin ke komponen) ──────
// `cs-*` = konvensi "coming soon", KECUALI yang sudah punya route nyata (LIVE).
const LIVE_CS_VIEWS = [
  "cs-kpi", "cs-design-gallery", "cs-bi-hrd", "cs-pajak", "cs-stock-analytics",
  "cs-rfid-lokasi", "cs-rfid-tags", "cs-rfid-devices", "cs-rfid-gate",
  // F1b (D-14) — Daftar Harga per Pelanggan sudah punya layar & API nyata.
  "cs-price-list",
];
// Halaman landing per role — hanya di sini MetricCards & Onboarding ditampilkan.
// Fase 4 · R3 (L-06) — Operasi Gudang dikeluarkan: deretan KPI global (Produk Aktif/Jml Tersedia/…) mengulang KPI
// tab Stok yang sudah baku dan kartu "Jml Tersedia" patah 4 baris di 1440 px.
const HOME_VIEWS = ["sales", "reports"];

export const isComingSoonView = (view) =>
  typeof view === "string" && view.startsWith("cs-") && !LIVE_CS_VIEWS.includes(view);
export const isHomeView = (view) => HOME_VIEWS.includes(view);

// view → hubId (untuk render tab bar & highlight sidebar)
const HUB_VIEW_INDEX = (() => {
  const idx = {};
  for (const [hubId, tabs] of Object.entries(HUB_TABS)) {
    tabs.forEach((t) => { idx[t.view] = hubId; });
  }
  return idx;
})();

export function hubForView(view, role) {
  if (view === 'product-templates') view = 'md-products';
  // Fase 3 · P1 — id lama yang kini alias (tanpa tab sendiri) memakai bilah tab hub layar utamanya.
  if (!HUB_VIEW_INDEX[view] && resolveAlias(view)) view = resolveAlias(view).to;
  const hubId = HUB_VIEW_INDEX[view];
  if (!hubId) return null;
  const tabs = hubTabsForRole(hubId, role);
  // Tab `hidden` (alias deep-link) tetap sah bila perannya boleh — tab bar memakai tab yang tampil.
  const own = (HUB_TABS[hubId] || []).find((t) => t.view === view);
  const allowed = tabs.some((t) => t.view === view) || (own?.hidden && roleCanSee(own.roles, role, own.view));
  if (!tabs.length || !allowed) return null;
  // Alias hidden menyorot tab induknya (`aliasOf`) agar posisi pengguna tetap terlihat.
  return { hubId, tabs, activeTab: own?.hidden ? own.aliasOf || view : view };
}

// Untuk item hub: view default = tab pertama yang boleh diakses role tsb.
/** FE-03 — item hub yang semua tabnya tak terlihat oleh role = pintu mati (view hub tidak punya
 *  renderer sendiri); jangan ditampilkan. Hub tanpa daftar tab tidak terpengaruh. */
function hubWithoutTabs(item, role) {
  if (!item.hub || !(HUB_TABS[item.hub] || []).some((t) => !t.hidden)) return false;
  return hubTabsForRole(item.hub, role).length === 0;
}

function withHubView(item, role) {
  if (!item.hub) return item;
  const tabs = hubTabsForRole(item.hub, role);
  return { ...item, view: tabs.length ? tabs[0].view : (item.view || item.id) };
}

// ─── BUILD GROUPED NAVIGATION — filter per role; comingSoon → grup "Segera Hadir" ──
// ── ZONA SIDEBAR (IA) ──────────────────────────────────────────────────────────
// Prinsip: MEJA = tempat bekerja (antrean), MODUL = tempat mencari/mengelola dokumen,
// ALAT = utilitas lintas modul, AKUN = diri sendiri. Tiap entri NAV_STRUCTURE dipetakan
// ke satu zona; yang tidak terdaftar dianggap MODUL.
export const NAV_ZONES = [
  { id: "kerja", label: "Kerja Saya" },
  { id: "modul", label: "Modul" },
  { id: "alat",  label: "Alat" },
  { id: "akun",  label: "Akun" },
];
const ZONE_OF = {
  home: "kerja", "approval-inbox": "kerja", "sales-admin-desk": "kerja", "finance-desk": "kerja",
  "md-desk": "kerja", "warehouse-admin-desk": "kerja", "sample-admin-desk": "kerja", escalations: "kerja",
  analytics: "alat", "export-center": "alat", "document-center": "alat", "settings-hub": "alat", "segera-hadir": "alat",
  "hr-my-profile": "akun",
};
export function zoneOf(entry) {
  return ZONE_OF[entry.groupId || entry.id] || "modul";
}

/** Sisipkan pemisah zona (type:"zone") di depan entri pertama tiap zona; urutan zona tetap. */
export function withZones(groups) {
  const out = [];
  for (const z of NAV_ZONES) {
    const members = groups.filter((g) => zoneOf(g) === z.id);
    if (!members.length) continue;
    out.push({ type: "zone", id: `zone-${z.id}`, label: z.label });
    out.push(...members);
  }
  return out;
}

/** Fase 3 · P1 — sisipkan kembali sub-judul grup yang diikuti >=1 menu tampak (urutan asli dipertahankan). */
function keepHeadings(items, live) {
  const byId = new Map(live.map((it) => [it.id, it]));
  const out = [];
  let pending = null;
  for (const it of items || []) {
    if (isNavHeading(it)) { pending = it; continue; }
    if (!byId.has(it.id)) continue;
    if (pending) { out.push(pending); pending = null; }
    out.push(byId.get(it.id));
  }
  return out;
}

/** `opts.withHeadings` (hanya Sidebar) — ikutkan sub-judul `{type:"heading"}` di dalam grup. Konsumen lain
 *  (pratinjau peran, aplikasi HP, uji) menerima daftar menu MURNI seperti sebelumnya. */
export function buildNavGroups(role, opts = {}) {
  const showComingSoon = opts.showComingSoon !== false;
  // FASE G-0 — `ui.coming_soon_collapsed` DULU setting mati (0 consumer). Sekarang
  // benar-benar menentukan apakah grup "Segera Hadir" tampil terlipat saat aplikasi dibuka.
  const comingSoonCollapsed = opts.comingSoonCollapsed !== false;
  const result = [];
  const comingSoonItems = [];
  for (const entry of NAV_STRUCTURE) {
    const ownVisible = roleCanSee(entry.roles, role, entry.groupId || entry.id);
    if (entry.type === "standalone") {
      if (!ownVisible || hubWithoutTabs(entry, role)) continue;
      if (entry.comingSoon) comingSoonItems.push(entry);
      else result.push(withHubView(entry, role));
    } else if (entry.type === "group") {
      // FE-03 — peran kustom: induk tampil bila ada ANAK yang sah (katalog modul memberi menu anak,
      // mis. `interco-transactions`, tanpa ID grup `akuntansi`). Anak tetap disaring satu per satu,
      // jadi induk tidak membuka anak tak berizin; induk yang DISEMBUNYIKAN eksplisit tetap tertutup.
      // Peran bawaan tetap memakai `roles` grup (rancangan menu tertulis).
      if (!ownVisible && (!isModuleNavRole(role) || navExplicitlyHidden(role, entry.groupId))) continue;
      const roleItems = entry.items.filter(item => !isNavHeading(item) && roleCanSee(item.roles, role, item.id) && !hubWithoutTabs(item, role));
      if (!ownVisible && roleItems.length === 0) continue;
      const liveItems = roleItems.filter(item => !item.comingSoon).map(item => withHubView(item, role));
      const soonItems = roleItems.filter(item => item.comingSoon);
      if (liveItems.length > 0) result.push({ ...entry, items: opts.withHeadings ? keepHeadings(entry.items, liveItems) : liveItems });
      soonItems.forEach(item => comingSoonItems.push(item));
    }
  }
  if (showComingSoon && comingSoonItems.length > 0) {
    result.push({
      type: "group",
      groupId: "segera-hadir",
      label: "Segera Hadir",
      icon: Clock,
      roles: [role],
      comingSoonGroup: true,
      defaultCollapsed: comingSoonCollapsed,
      items: comingSoonItems,
    });
  }
  return result;
}

// Backward compat: flat array untuk komponen lama jika perlu
export function buildNavigation(role) {
  const groups = buildNavGroups(role);
  const flat = [];
  for (const entry of groups) {
    if (entry.type === "standalone") flat.push(entry);
    else entry.items.forEach(item => flat.push(item));
  }
  return flat;
}

// ─── COMMAND PALETTE ENTRIES (Ctrl+K) — semua tujuan navigasi role ini ─────────
export function buildPaletteEntries(role) {
  const entries = [];
  const seen = new Set();
  const push = (e) => {
    const key = `${e.view}::${e.tab || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    entries.push(e);
  };
  for (const entry of NAV_STRUCTURE) {
    if (!roleCanSee(entry.roles, role, entry.groupId || entry.id)) continue;
    const walk = (item, groupLabel) => {
      if (item.comingSoon) return;
      if (item.hub) {
        hubTabsForRole(item.hub, role).forEach((t) => push({
          navId: item.id, view: t.view, tab: t.tab,
          label: `${item.label} \u203a ${t.label}`, group: groupLabel, icon: item.icon,
        }));
      } else {
        push({ navId: item.id, view: item.view || item.id, tab: item.tab,
               label: item.label, group: groupLabel, icon: item.icon });
      }
    };
    if (entry.type === "standalone") walk(entry, "Umum");
    else entry.items.filter(i => !isNavHeading(i) && roleCanSee(i.roles, role, i.id)).forEach(i => walk(i, entry.label));
  }
  // Fase 3 · P1 — nama lama yang kini alias (punya `label`) tetap bisa dicari: "Nama lama -> kini di <utama>".
  // Hanya bila peran ini boleh membuka layar utamanya. `aliasOf` dikirim balik ke handleNavSelect (preset ikut).
  for (const a of listAliases()) {
    if (!a.label) continue;
    const target = entries.find((e) => e.view === a.to && !e.aliasOf);
    if (!target) continue;
    const key = `${a.to}::${target.tab || ""}::${a.from}`;
    if (seen.has(key)) continue;
    seen.add(key);
    entries.push({ ...target, aliasOf: a.from, preset: a.preset,
                   label: `${a.label} \u2192 kini di ${target.label}` });
  }
  return entries;
}

export function defaultViewForRole(role, registry = ROLE_HOME_REGISTRY) {
  return (registry[role] || registry.sales).view;
}
export function defaultNavIdForRole(role, registry = ROLE_HOME_REGISTRY) {
  return (registry[role] || registry.sales).navId;
}

// ─── VIEW → NAV ID INDEX (highlight sidebar = turunan dari activeView) ─────────
const VIEW_NAV_INDEX = (() => {
  const idx = {};
  const reg = (view, navId) => { (idx[view] = idx[view] || []).push(navId); };
  for (const entry of NAV_STRUCTURE) {
    const walk = (item) => {
      if (item.hub) {
        (HUB_TABS[item.hub] || []).forEach((t) => reg(t.view, item.id));
      } else {
        reg(item.view || item.id, item.id);
      }
    };
    if (entry.type === "standalone") walk(entry);
    else (entry.items || []).filter((i) => !isNavHeading(i)).forEach(walk);
  }
  return idx;
})();

export function resolveActiveNavId(activeView, currentNavId, role) {
  if (activeView === 'product-templates') activeView = 'md-products';
  if (!VIEW_NAV_INDEX[activeView] && resolveAlias(activeView)) activeView = resolveAlias(activeView).to;   // fase 3 · P1
  const candidates = VIEW_NAV_INDEX[activeView];
  if (currentNavId && candidates && candidates.includes(currentNavId)) return currentNavId;
  if (candidates && candidates.length) return candidates[0];
  const home = ROLE_HOME_REGISTRY[role];
  if (home && home.view === activeView) return home.navId;
  return currentNavId || "home";
}

// ─── DEEP-LINK `?view=<viewId>` (FASE E-4) ────────────────────────────────────
// Menerjemahkan satu `viewId` dari alamat menjadi tujuan navigasi lengkap
// ({navId, view, tab}) SESUAI PERAN. Dipakai `hooks/useViewDeepLink.js`.
// Sengaja bersandar pada `buildPaletteEntries` (sumber yang sama dengan Ctrl+K)
// supaya daftar tujuan yang sah tidak pernah bercabang dua: layar "segera hadir"
// dan layar di luar menu peran otomatis TIDAK bisa dituju lewat alamat.
export function resolveDeepLinkTarget(view, role) {
  if (view === 'product-templates') view = 'md-products';
  if (!view || !role) return null;
  // Fase 3 · P1 — ALIAS LEBIH DULU: id lama yang kini tautan dibuka di layar utamanya (dengan preset),
  // dan PERAN divalidasi terhadap layar utama. Bila peran tidak boleh membuka layar utama, id lama
  // diperlakukan seperti biasa (mis. `purchase-orders` = menu hub untuk peran tanpa tab PO).
  // Id lama yang DISEMBUNYIKAN untuk peran ini (`hidden_views` peran kustom / `ROLE_NAV.remove`) tetap tertutup:
  // alias tidak boleh menjadi pintu belakang ke layar utama lewat nama lama (§1.1 butir 6 rencana fase 3).
  const alias = navExplicitlyHidden(role, view) ? null : resolveAlias(view);
  if (alias) {
    const t = resolveDirectTarget(alias.to, role);
    if (t) {
      const navId = alias.nav && (VIEW_NAV_INDEX[alias.to] || []).includes(alias.nav) ? alias.nav : t.navId;
      return { ...t, navId, preset: alias.preset || null, alias: view };
    }
  }
  return resolveDirectTarget(view, role);
}

function resolveDirectTarget(view, role) {
  const entries = buildPaletteEntries(role).filter((e) => !e.aliasOf);
  const entry = entries.find((e) => e.view === view);
  if (entry) return { navId: entry.navId, view: entry.view, tab: entry.tab };
  // Alamat boleh juga menyebut ID MENU atau HUB (mis. `?view=ledger`) — diarahkan
  // ke tab pertama yang boleh dilihat peran ini. Tanpa ini pengguna yang menyalin
  // "ledger" dari peta navigasi mendarat di halaman depan tanpa penjelasan.
  const byNav = entries.find((e) => e.navId === view);
  if (byNav) return { navId: byNav.navId, view: byNav.view, tab: byNav.tab };
  // Tab `hidden` (alias deep-link, mis. `inspections`) → menu hub-nya, view aslinya.
  const hubId = HUB_VIEW_INDEX[view];
  const own = (HUB_TABS[hubId] || []).find((t) => t.view === view);
  if (own?.hidden && roleCanSee(own.roles, role, own.view)) {
    const sibling = entries.find((e) => HUB_VIEW_INDEX[e.view] === hubId);
    if (sibling) return { navId: sibling.navId, view };
  }
  const home = ROLE_HOME_REGISTRY[role];
  if (home && home.view === view) return { navId: home.navId, view: home.view };
  return null;
}

// ─── BREADCRUMB DARI MENU (fase 3 · P1, L-05) ─────────────────────────────────
// Kepala halaman dulu memakai `PAGE_META.kicker` yang ditulis tangan sehingga bisa berbeda dari sorotan
// sidebar (mis. Pusat Amandemen "Keuangan · Kendali" padahal menunya Penjualan › Pesanan). Kini diturunkan
// dari menu yang SAMA dengan sorotan sidebar (`resolveActiveNavId`): grup › menu › tab. `[]` = layar di luar
// menu (beranda peran, layar tanpa menu) → TopBar memakai `kicker` sebagai cadangan.
export function breadcrumbFor(view, navId, role) {
  if (!view) return [];
  let v = view === "product-templates" ? "md-products" : view;
  if (!VIEW_NAV_INDEX[v] && resolveAlias(v)) v = resolveAlias(v).to;
  const nid = resolveActiveNavId(v, navId, role);
  if (!(VIEW_NAV_INDEX[v] || []).includes(nid)) return [];
  for (const entry of NAV_STRUCTURE) {
    const items = entry.type === "standalone" ? [entry] : (entry.items || []).filter((i) => !isNavHeading(i));
    const item = items.find((i) => i.id === nid);
    if (!item) continue;
    const crumbs = [];
    if (entry.type === "group") crumbs.push(entry.label);
    crumbs.push(item.label);
    if (item.hub) {
      const tab = (HUB_TABS[item.hub] || []).find((t) => t.view === v);
      if (tab) crumbs.push(tab.label);
    }
    return crumbs.filter((c, k, arr) => c && c !== arr[k - 1] && c !== "Beranda");
  }
  return [];
}
