// 14 Nov 2026 (perapian Meja Finance, keputusan pemilik) — "Bantuan & Panduan" tidak lagi melayang di atas isi
// pada layar desktop: `placement="topbar"` = tombol ikon baku + panel turun dari atas; `floating` tetap untuk ≤ 768 px.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import TourMenu from "../TourMenu";

jest.mock("../../data/tourDefinitions", () => ({
  getToursForRole: () => [{ key: "t1", id: "t1", name: "Meja Finance", description: "Antrean uang masuk" }],
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

async function mount(props) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<TourMenu userRole="finance" onSelectTour={() => {}} {...props} />); });
  return { host, root, rerender: (p) => act(async () => { root.render(<TourMenu userRole="finance" onSelectTour={() => {}} {...props} {...p} />); }) };
}

test("topbar: tombol ikon baku tanpa widget melayang; panel turun dari atas", async () => {
  const onToggleMenu = jest.fn();
  const m = await mount({ placement: "topbar", showMenu: false, onToggleMenu });
  expect(q(m.host, "tour-fab")).toBeNull();                          // tidak ada elemen `fixed` di atas isi
  const btn = q(m.host, "help-tours-button");
  expect(btn.className).toBe("icon-button");
  expect(btn.getAttribute("aria-label")).toBe("Bantuan & Panduan");
  expect(btn.getAttribute("aria-expanded")).toBe("false");
  await act(async () => { btn.click(); });
  expect(onToggleMenu).toHaveBeenCalledTimes(1);

  await m.rerender({ showMenu: true });
  expect(q(m.host, "help-tours-button").getAttribute("aria-expanded")).toBe("true");
  const panel = q(m.host, "tour-menu-panel");
  expect(panel.className).toMatch(/\btop-full\b/);
  expect(panel.className).not.toMatch(/bottom-16/);
  expect(q(m.host, "tour-menu-item-t1").textContent).toMatch(/Meja Finance/);
  await act(async () => { m.root.unmount(); });
  m.host.remove();
});

test("topbar: Esc lewat tumpukan lapisan bersama & klik di LUAR menutup panel; klik di dalam tidak", async () => {
  const onToggleMenu = jest.fn();
  const m = await mount({ placement: "topbar", showMenu: true, onToggleMenu });
  // Tanpa lapisan `fixed`: topbar ber-backdrop-filter membuat lapisan itu hanya selebar topbar (terukur di peramban).
  expect(q(m.host, "tour-menu-backdrop")).toBeNull();
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
  expect(onToggleMenu).toHaveBeenCalledTimes(1);
  await act(async () => { q(m.host, "tour-menu-panel").dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); });
  expect(onToggleMenu).toHaveBeenCalledTimes(1);
  await act(async () => { document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); });
  expect(onToggleMenu).toHaveBeenCalledTimes(2);
  await act(async () => { m.root.unmount(); });
  m.host.remove();
});

test("floating (bawaan, layar ≤ 768 px): tetap widget mengapung dengan panel di atas tombol", async () => {
  const m = await mount({ showMenu: true, onToggleMenu: () => {} });
  expect(q(m.host, "tour-fab").className).toMatch(/\bfixed\b/);
  expect(q(m.host, "tour-menu-panel").className).toMatch(/bottom-16/);
  expect(q(m.host, "tour-anchor")).toBeNull();
  expect(q(m.host, "tour-menu-backdrop")).not.toBeNull();             // klik di luar = lapisan penutup (perilaku lama)
  await act(async () => { m.root.unmount(); });
  m.host.remove();
});
