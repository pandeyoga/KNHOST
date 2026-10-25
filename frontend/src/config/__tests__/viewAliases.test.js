// Fase 3 · P1 — pola "gabung" (alias + preset): deep link, preset, palet Ctrl+K, bilah hub, breadcrumb dari menu,
// sub-judul grup sidebar, serta jalur konteks (ViewPresetContext / AppNavContext).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import {
  NAV_STRUCTURE, HUB_TABS, breadcrumbFor, buildNavGroups, buildPaletteEntries, hubForView,
  resolveActiveNavId, resolveDeepLinkTarget,
} from "../navigationConfig";
import { VIEW_ALIASES, aliasTarget, aliasesOf, listAliases, resolveAlias } from "../viewAliases";
import { resolveView } from "../../utils/viewAlias";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { AppNavProvider, useAppNav } from "../../context/AppNavContext";
import useViewPreset from "../../hooks/useViewPreset";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/** Alias sementara (pola P8) untuk menguji preset & label tanpa mengubah registri sungguhan. */
function withTestAlias(fn) {
  VIEW_ALIASES["uji-persetujuan-saya"] = {
    to: "approval-inbox", preset: { tab: "matrix" }, label: "Persetujuan Saya (uji)", since: "D-06",
  };
  try { return fn(); } finally { delete VIEW_ALIASES["uji-persetujuan-saya"]; }
}

const menuViews = () => {
  const out = new Set();
  Object.values(HUB_TABS).flat().forEach((t) => out.add(t.view));
  NAV_STRUCTURE.forEach((e) => {
    const items = e.type === "group" ? e.items : [e];
    items.forEach((i) => { out.add(i.id); if (i.view) out.add(i.view); });
  });
  return out;
};

describe("registri alias", () => {
  test("alias lama (S14) tetap dan resolveView membaca registri yang sama", () => {
    expect(resolveAlias("approvals")).toMatchObject({ from: "approvals", to: "approval-inbox", legacy: true });
    expect(resolveView("approvals")).toBe("approval-inbox");
    expect(resolveView("finance")).toBe("finance-desk");
    expect(resolveView("purchase-orders")).toBe("purchasing");
    expect(resolveView("orders")).toBe("orders");
    expect(resolveView(undefined)).toBeUndefined();
    expect(aliasTarget("bukan-alias")).toBe("bukan-alias");
    expect(aliasesOf("approval-inbox").map((a) => a.from)).toContain("approvals");
  });

  test("tanpa rantai: tujuan alias bukan alias, dan ada di menu", () => {
    const views = menuViews();
    for (const a of listAliases()) {
      expect([a.from, resolveAlias(a.to)]).toEqual([a.from, null]);
      expect([a.from, views.has(a.to)]).toEqual([a.from, true]);
      if (a.nav) expect([a.from, views.has(a.nav)]).toEqual([a.from, true]);
    }
  });
});

describe("deep link ?view= lewat alias", () => {
  test("?view=approvals mendarat di Pusat Persetujuan (dulu: tidak ke mana-mana)", () => {
    expect(resolveDeepLinkTarget("approvals", "manager")).toMatchObject({ navId: "approval-inbox", view: "approval-inbox", alias: "approvals" });
    expect(resolveDeepLinkTarget("approvals", "admin")).toMatchObject({ view: "approval-inbox" });
    // Sales hanya punya tab Pengajuan Harga Khusus di Pusat Persetujuan → mendarat di tab yang sah itu.
    expect(resolveDeepLinkTarget("approvals", "sales")).toMatchObject({ navId: "approval-inbox", view: "price-approvals" });
  });

  test("peran tanpa akses ke layar utama: id lama diperlakukan seperti dulu (bukan pintu belakang)", () => {
    // Gudang punya menu Pesanan Pembelian tetapi TIDAK tab PO → tetap ke tab pertama miliknya, bukan PO.
    expect(resolveDeepLinkTarget("purchase-orders", "warehouse")).toMatchObject({ navId: "purchase-orders", view: "makloon-orders" });
    expect(resolveDeepLinkTarget("purchase-orders", "manager")).toMatchObject({ navId: "purchase-orders", view: "purchasing" });
    expect(resolveDeepLinkTarget("approvals", "driver")).toBeNull();
    expect(resolveDeepLinkTarget("finance", "finance")).toMatchObject({ view: "finance-desk" });
  });

  test("preset alias ikut, palet menampilkan 'Nama lama → kini di <utama>' hanya untuk peran berwenang", () => withTestAlias(() => {
    expect(resolveDeepLinkTarget("uji-persetujuan-saya", "manager")).toMatchObject({
      navId: "approval-inbox", view: "approval-inbox", preset: { tab: "matrix" }, alias: "uji-persetujuan-saya",
    });
    const pal = buildPaletteEntries("manager").find((e) => e.aliasOf === "uji-persetujuan-saya");
    expect(pal).toMatchObject({ view: "approval-inbox", navId: "approval-inbox", preset: { tab: "matrix" } });
    expect(pal.label).toMatch(/^Persetujuan Saya \(uji\) → kini di Pusat Persetujuan › Inbox Persetujuan$/);
    expect(buildPaletteEntries("warehouse").some((e) => e.aliasOf === "uji-persetujuan-saya")).toBe(false);
    // Entri alias tidak mengganggu resolusi biasa (entri asli tetap yang pertama).
    expect(resolveDeepLinkTarget("approval-inbox", "manager")).toEqual({ navId: "approval-inbox", view: "approval-inbox", tab: undefined });
  }));

  test("id lama yang disembunyikan untuk peran (ROLE_NAV.remove / hidden_views) tidak jadi pintu belakang", () => {
    VIEW_ALIASES["designer-kpi"] = { to: "rnd-designs", since: "uji" };
    try {
      expect(resolveDeepLinkTarget("designer-kpi", "admin")).toMatchObject({ view: "rnd-designs", alias: "designer-kpi" });
      expect(resolveDeepLinkTarget("rnd-designs", "md")).toMatchObject({ view: "rnd-designs" });
      expect(resolveDeepLinkTarget("designer-kpi", "md")).toBeNull();     // md: `remove: ["designer-kpi"]`
    } finally { delete VIEW_ALIASES["designer-kpi"]; }
  });

  test("bilah hub, sorotan menu & breadcrumb untuk id alias mengikuti layar utama", () => withTestAlias(() => {
    expect(hubForView("uji-persetujuan-saya", "manager")).toMatchObject({ hubId: "approval-inbox", activeTab: "approval-inbox" });
    expect(resolveActiveNavId("uji-persetujuan-saya", null, "manager")).toBe("approval-inbox");
    expect(breadcrumbFor("uji-persetujuan-saya", null, "manager")).toEqual(["Pusat Persetujuan", "Inbox Persetujuan"]);
  }));
});

describe("breadcrumb dari menu (L-05)", () => {
  test.each([
    ["amendments", ["Penjualan", "Pesanan", "Koreksi & Amandemen"]],
    ["cs-stock-analytics", ["Analitik", "Analitik Stok"]],
    ["costing", ["Analitik", "Margin & HPP"]],
    ["consolidation", ["Akuntansi & Pajak", "Laporan", "Konsolidasi Grup"]],
    ["financial-statements", ["Akuntansi & Pajak", "Laporan", "Laba-Rugi, Neraca & Arus Kas"]],
    ["profitability", ["Akuntansi & Pajak", "Laporan", "Profitabilitas & Margin"]],
    ["interco-transactions", ["Akuntansi & Pajak", "Antar Entitas (Grup)"]],
  ])("%s = sorotan sidebar", (view, crumbs) => {
    expect(breadcrumbFor(view, null, "admin")).toEqual(crumbs);
    const nid = resolveActiveNavId(view, null, "admin");
    expect(crumbs).toContain(NAV_STRUCTURE.flatMap((e) => (e.type === "group" ? e.items : [e])).find((i) => i.id === nid).label);
  });

  test("layar di luar menu & beranda peran → [] (TopBar memakai kicker cadangan)", () => {
    expect(breadcrumbFor("admin-home", "home", "admin")).toEqual([]);
    expect(breadcrumbFor("view-tak-dikenal", "orders", "admin")).toEqual([]);
    expect(breadcrumbFor("", null, "admin")).toEqual([]);
    // Standalone tanpa hub: satu crumb.
    expect(breadcrumbFor("export-center", null, "admin")).toEqual(["Pusat Export"]);
  });
});

describe("sub-judul grup sidebar ({type:'heading'})", () => {
  const group = NAV_STRUCTURE.find((e) => e.groupId === "keuangan");
  const original = group.items.slice();
  afterEach(() => { group.items.splice(0, group.items.length, ...original); });

  test("hanya Sidebar (withHeadings) yang menerima sub-judul; sub-judul tanpa menu tampak dibuang", () => {
    group.items.splice(2, 0, { type: "heading", id: "h-uji-piutang", label: "Piutang & Uang Muka" });
    group.items.push({ type: "heading", id: "h-uji-yatim", label: "Tanpa isi" });
    const plain = buildNavGroups("manager").find((g) => g.groupId === "keuangan");
    expect(plain.items.some((i) => i.type === "heading")).toBe(false);
    const withH = buildNavGroups("manager", { withHeadings: true }).find((g) => g.groupId === "keuangan");
    const ids = withH.items.map((i) => i.id);
    expect(ids.indexOf("h-uji-piutang")).toBe(ids.indexOf("ar-aging") - 1);
    expect(ids).not.toContain("h-uji-yatim");
    expect(buildPaletteEntries("manager").some((e) => String(e.navId).startsWith("h-uji"))).toBe(false);
    // Peran tanpa menu di bawah sub-judul → sub-judul ikut hilang.
    const sales = buildNavGroups("sales", { withHeadings: true }).find((g) => g.groupId === "keuangan");
    expect(sales ? sales.items.some((i) => i.type === "heading" && i.id === "h-uji-piutang") : false).toBe(false);
  });
});

describe("konteks preset & navigasi", () => {
  async function render(el) {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => { root.render(el); });
    return { host, root };
  }

  test("useViewPreset: hanya untuk view yang dituju, callback sekali per nonce", async () => {
    const seen = [];
    function Screen({ view }) {
      const p = useViewPreset(view, (x) => seen.push(`${view}:${x.tab}:${x.nonce}`));
      return <span data-testid={`p-${view}`}>{p ? p.tab : "-"}</span>;
    }
    const tree = (preset) => (
      <ViewPresetProvider preset={preset}><Screen view="approval-inbox" /><Screen view="orders" /></ViewPresetProvider>
    );
    const { host, root } = await render(tree({ view: "approval-inbox", tab: "matrix", nonce: 1 }));
    expect(host.querySelector('[data-testid="p-approval-inbox"]').textContent).toBe("matrix");
    expect(host.querySelector('[data-testid="p-orders"]').textContent).toBe("-");
    await act(async () => { root.render(tree({ view: "approval-inbox", tab: "matrix", nonce: 1 })); });
    await act(async () => { root.render(tree({ view: "approval-inbox", tab: "price", nonce: 2 })); });
    expect(seen).toEqual(["approval-inbox:matrix:1", "approval-inbox:price:2"]);
    await act(async () => { root.render(tree(null)); });
    expect(host.querySelector('[data-testid="p-approval-inbox"]').textContent).toBe("-");
    await act(async () => { root.unmount(); });
  });

  test("AppNavContext: canOpen dari menu peran, go() lewat jalur bersama (fokus → openDocument)", async () => {
    const nav = []; const docs = [];
    let api = null;
    function Probe() { api = useAppNav(); return null; }
    const { root } = await render(
      <AppNavProvider role="manager" onNavigateTo={(v, o) => nav.push([v, o])} onOpenDocument={(l) => docs.push(l)}><Probe /></AppNavProvider>);
    expect(api.canOpen("approval-inbox")).toBe(true);
    expect(api.canOpen("approvals")).toBe(true);
    expect(api.canOpen("hr-employees")).toBe(true);
    expect(api.canOpen("view-tak-dikenal")).toBe(false);
    api.go("approvals", { preset: { tab: "matrix" } });
    api.go("special-orders", { focus: { type: "special_order", id: "so1", number: "SORD-1" } });
    expect(nav).toEqual([["approvals", { preset: { tab: "matrix" }, tab: undefined, navId: undefined }]]);
    expect(docs).toEqual([{ view: "special-orders", nav_id: undefined, tab: undefined, preset: undefined,
      focus_type: "special_order", focus_id: "so1", number: "SORD-1" }]);
    await act(async () => { root.unmount(); });
    const { root: r2 } = await render(<AppNavProvider role="driver"><Probe /></AppNavProvider>);
    expect(api.canOpen("approval-inbox")).toBe(false);
    expect(api.canOpen("logistics")).toBe(true);
    await act(async () => { r2.unmount(); });
  });
});
