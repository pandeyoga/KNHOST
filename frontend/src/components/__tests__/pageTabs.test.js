// Fase 3 · P1 (L-01) — tab tingkat-2 baku (PageTabs), saringan chip (FilterChips), tab tingkat-1 bergaya baku (HubTabs).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { BarChart3 } from "lucide-react";
import PageTabs from "../PageTabs";
import FilterChips from "../FilterChips";
import HubTabs from "../HubTabs";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
}
const rerender = (el) => act(async () => { root.render(el); });
afterEach(async () => { await act(async () => { root.unmount(); }); host.remove(); });
const q = (id) => host.querySelector(`[data-testid="${id}"]`);
const click = (el) => act(async () => { el.click(); });

const TABS = [
  { key: "dashboard", label: "Dasbor & Analitik", icon: BarChart3, testId: "tab-dashboard" },
  { key: "list", label: "Daftar Pesanan", count: 12, testId: "tab-list" },
  { key: "draft", label: "Draf", count: 0 },
  { key: "arsip", label: "Arsip", disabled: true },
  { key: "rahasia", label: "Tersembunyi", hidden: true },
];

describe("PageTabs", () => {
  test("role tablist, testid tetap (tab-dashboard/tab-list) & bawaan `${testId}-${key}`, lencana 0 disembunyikan", async () => {
    await mount(<PageTabs testId="orders-tabs" tabs={TABS} value="list" onChange={() => {}} />);
    const bar = q("orders-tabs");
    expect(bar.getAttribute("role")).toBe("tablist");
    expect(bar.className).toMatch(/\btab-bar\b/);
    expect(bar.className).toMatch(/\bpage-tabs\b/);
    expect(q("tab-dashboard").getAttribute("aria-selected")).toBe("false");
    expect(q("tab-list").getAttribute("aria-selected")).toBe("true");
    expect(q("tab-list").className).toMatch(/\bactive\b/);
    expect(q("tab-list").tabIndex).toBe(0);
    expect(q("tab-dashboard").tabIndex).toBe(-1);
    expect(q("tab-list").querySelector(".tab-badge").textContent).toBe("12");
    expect(q("orders-tabs-draft").querySelector(".tab-badge")).toBeNull();
    expect(q("orders-tabs-rahasia")).toBeNull();
    expect(q("tab-dashboard").querySelector("svg")).not.toBeNull();
  });

  test("klik memanggil onChange; tab aktif & nonaktif tidak; panah melompati tab nonaktif", async () => {
    const calls = [];
    const tree = (v) => <PageTabs testId="t" tabs={TABS} value={v} onChange={(k) => calls.push(k)} />;
    await mount(tree("dashboard"));
    await click(q("tab-list"));
    await click(q("tab-dashboard"));
    await click(q("t-arsip"));
    expect(calls).toEqual(["list"]);
    await rerender(tree("draft"));
    await act(async () => { q("t-draft").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(calls[calls.length - 1]).toBe("dashboard");   // "arsip" nonaktif dilompati → kembali ke awal
    await act(async () => { q("t-draft").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true })); });
    expect(calls[calls.length - 1]).toBe("list");
    await act(async () => { q("t-draft").dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true })); });
    expect(calls).toEqual(["list", "dashboard", "list", "dashboard"]);
  });

  test("tanpa tab aktif: tab pertama tetap bisa difokus; tanpa tab = tidak dirender", async () => {
    await mount(<PageTabs testId="t" tabs={TABS} value="tidak-ada" onChange={() => {}} />);
    expect(q("tab-dashboard").tabIndex).toBe(0);
    await rerender(<PageTabs testId="t" tabs={[]} value="x" onChange={() => {}} />);
    expect(q("t")).toBeNull();
  });
});

describe("FilterChips", () => {
  const OPTS = [{ key: "all", label: "Semua", count: 14 }, { key: "wh", label: "Antar gudang", count: 9 }, { key: "pt", label: "Antar PT", count: 0 }];

  test("satu pilihan: aria-pressed, klik chip lain → onChange, klik chip aktif tidak mengosongkan kecuali clearable", async () => {
    const calls = [];
    await mount(<FilterChips testId="kind" options={OPTS} value="all" onChange={(v) => calls.push(v)} />);
    const grp = q("kind");
    expect(grp.getAttribute("role")).toBe("group");
    expect(q("kind-all").getAttribute("aria-pressed")).toBe("true");
    expect(q("kind-wh").getAttribute("aria-pressed")).toBe("false");
    expect(q("kind-pt").querySelector(".filter-chip-count").textContent).toBe("0");   // hitungan 0 tetap info saringan
    await click(q("kind-wh"));
    await click(q("kind-all"));
    expect(calls).toEqual(["wh"]);
    await rerender(<FilterChips testId="kind" options={OPTS} value="all" clearable onChange={(v) => calls.push(v)} />);
    await click(q("kind-all"));
    expect(calls).toEqual(["wh", null]);
    expect(q("kind").querySelector('[role="tab"]')).toBeNull();   // saringan BUKAN tab
  });

  test("banyak pilihan: menambah & mencabut kunci", async () => {
    const calls = [];
    await mount(<FilterChips multiple testId="jenis" options={OPTS} value={["wh"]} onChange={(v) => calls.push(v)} />);
    await click(q("jenis-pt"));
    await click(q("jenis-wh"));
    expect(calls).toEqual([["wh", "pt"], []]);
  });
});

describe("HubTabs (gaya baku tingkat-1)", () => {
  const TABS_HUB = [
    { view: "settings-config", label: "Pusat Pengaturan", section: "Sistem" },
    { view: "scheduler", label: "Penjadwal", section: "Sistem" },
    { view: "entities-access", label: "Badan Usaha & Akses", section: "Organisasi & Akses" },
    { view: "grade-master", label: "Master Grade", section: "Kamus & Dokumen" },
  ];

  test("garis bawah `.tab-bar.hub-tabs` (bukan pil hitam), testid tur & seksi dipertahankan, sub-judul seksi aktif", async () => {
    const calls = [];
    await mount(<HubTabs hubId="settings-hub" tabs={TABS_HUB} activeView="scheduler" onSelect={(v) => calls.push(v)} />);
    const bar = q("hub-tabs-settings-hub");
    expect(bar.className).toMatch(/\btab-bar\b/);
    expect(bar.className).toMatch(/\bhub-tabs\b/);
    expect(host.innerHTML).not.toMatch(/rounded-full|bg-\[#1C1C1E\]/);
    expect(q("hub-tab-scheduler").className).toMatch(/\btab-button\b/);
    expect(q("hub-tab-scheduler").getAttribute("aria-current")).toBe("page");
    expect(q("hub-tab-settings-config").getAttribute("aria-current")).toBeNull();
    expect(q("hub-section-settings-hub-Sistem")).not.toBeNull();
    expect(host.querySelectorAll(".hub-tabs-sep").length).toBe(2);
    expect(q("hub-section-caption-settings-hub").textContent).toBe("Sistem");
    await click(q("hub-tab-grade-master"));
    expect(calls).toEqual(["grade-master"]);
  });

  test("hub tanpa seksi: tanpa sub-judul; < 2 tab: tidak dirender", async () => {
    await mount(<HubTabs hubId="quality-hub" tabs={[{ view: "qc-inspection", label: "Antrean" }, { view: "inspections", label: "SPK" }]}
      activeView="inspections" onSelect={() => {}} />);
    expect(q("hub-tab-inspections").className).toMatch(/\bactive\b/);
    expect(host.querySelector(".hub-tabs-caption")).toBeNull();
    await rerender(<HubTabs hubId="x" tabs={[{ view: "a", label: "A" }]} activeView="a" onSelect={() => {}} />);
    expect(q("hub-tabs-x")).toBeNull();
  });
});
