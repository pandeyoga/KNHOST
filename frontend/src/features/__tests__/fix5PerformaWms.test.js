/**
 * FIX-5 (audit WMS-RFID 9 Nov 2026) — performa & daftar besar di sisi klien.
 *  · UI-51  — `loadAll` tidak lagi diulang hanya karena objek `user` dibuat ulang `/auth/me` (dulu 3× per buka).
 *  · LST-01 — daftar berbatas server menyebut "a–b dari N" + "Muat berikutnya" (tidak memotong diam-diam).
 *  · UI-46  — baris antrean Lokasi Rak dirender saat mendekati layar (LazyMount); 12 baris pertama langsung.
 *  · B4 §3.8 — roll dikelompokkan Produk › Lot › Lokasi › Roll (agregat server), tertutup bawaan.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import { useAppActions } from "../../hooks/useAppActions";
import ListLimitNote, { metaFromHeaders } from "../wms/ListLimitNote";
import LazyMount from "../wms/location/LazyMount";
import RollGroupView from "../wms/inventory/RollGroupView";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let captured = [];
let respond = () => ({ data: {} });
const realAdapter = axios.defaults.adapter;
beforeEach(() => {
  captured = [];
  respond = () => ({ data: {} });
  axios.defaults.adapter = async (config) => {
    captured.push(config);
    const r = respond(config);
    return { data: r.data, status: 200, statusText: "OK", headers: r.headers || {}, config };
  };
  localStorage.clear();
});
afterAll(() => { axios.defaults.adapter = realAdapter; });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 4; i += 1) await act(async () => {});
  return { host, root, rerender: async (next) => { await act(async () => { root.render(next); }); for (let i = 0; i < 4; i += 1) await act(async () => {}); } };
}
const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); for (let i = 0; i < 4; i += 1) await act(async () => {}); };

// ── UI-51 ──────────────────────────────────────────────────────────────────────────────────────────────
function Harness({ state }) { useAppActions(state); return null; }
const noop = () => {};
const stateFor = (user) => ({
  user, token: "t", auditFilters: {}, selectedCustomer: null, selectedAddress: "", cart: [], data: {}, selectedEntity: "all",
  setUser: noop, setToken: noop, setActiveView: noop, setNotice: noop, setOnboarding: noop, setShowOnboarding: noop,
  setData: noop, setTemplates: noop, setUoms: noop, setMovements: noop, setTasks: noop, setUsers: noop, setPermissions: noop,
  setAuditLogs: noop, setSelectedCustomer: noop, setSelectedAddress: noop, setSelectedProduct: noop, setBreakdown: noop,
  setCart: noop, setLastDocument: noop, setLastLabel: noop, setPreviewHtml: noop, setActiveDetail: noop, setLoading: noop,
  setEntities: noop, setNotifications: noop, setUnreadCount: noop, setNotifMeta: noop, setSettings: noop, setPaymentTerms: noop,
  setEntityContext: noop, setSelectedEntity: noop, setActiveNavId: noop, setLocationChoice: noop,
});
const dashCalls = () => captured.filter((c) => /\/dashboard/.test(c.url)).length;

test("UI-51: objek user baru dengan identitas & izin sama TIDAK memuat ulang dasbor; izin berubah memuat ulang", async () => {
  const perms = { wms: ["view"] };
  const u1 = { id: "u1", role: "warehouse", permissions: perms };
  const m = await mount(<Harness state={stateFor(u1)} />);
  expect(dashCalls()).toBe(1);
  await m.rerender(<Harness state={stateFor({ ...u1, role_label: "Petugas Gudang" })} />);   // /auth/me pulih sesi
  await m.rerender(<Harness state={stateFor({ ...u1, permissions: { wms: ["view"] } })} />); // segar berkala, isi sama
  expect(dashCalls()).toBe(1);
  await m.rerender(<Harness state={stateFor({ ...u1, permissions: { wms: ["view", "update"] } })} />);
  expect(dashCalls()).toBe(2);
  await act(async () => m.root.unmount());
});

// ── LST-01 ─────────────────────────────────────────────────────────────────────────────────────────────
test("LST-01: catatan batas tampil hanya bila terpotong, menyebut jumlah sungguhan & memanggil muat berikutnya", async () => {
  const more = jest.fn();
  const a = await mount(<ListLimitNote meta={{ total: 50, truncated: false, shown: 50, skip: 0 }} onMore={more} />);
  expect(a.host.textContent).toBe("");
  const b = await mount(<ListLimitNote meta={{ total: 4700, truncated: true, shown: 100, skip: 0 }} noun="kedatangan" onMore={more} testId="t" />);
  expect(b.host.textContent).toMatch(/kedatangan 1–100 dari 4\.700/);
  await click(b.host.querySelector('[data-testid="t-more"]'));
  expect(more).toHaveBeenCalledTimes(1);
  expect(metaFromHeaders({ headers: { "x-total-count": "250", "x-truncated": "1" } }, 200, 0))
    .toEqual({ total: 250, truncated: true, shown: 200, skip: 0 });
  expect(metaFromHeaders({ headers: {} }, 3, 0)).toBeNull();
});

// ── UI-46 ──────────────────────────────────────────────────────────────────────────────────────────────
test("UI-46: LazyMount menunda baris berat sampai mendekati layar (eager langsung)", async () => {
  const observers = [];
  window.IntersectionObserver = class { constructor(cb) { this.cb = cb; observers.push(this); } observe() {} disconnect() {} };
  try {
    const m = await mount(<div>
      <LazyMount eager><span data-testid="row-a">A</span></LazyMount>
      <LazyMount testId="lazy-b"><span data-testid="row-b">B</span></LazyMount>
    </div>);
    expect(m.host.querySelector('[data-testid="row-a"]')).not.toBeNull();
    expect(m.host.querySelector('[data-testid="row-b"]')).toBeNull();
    expect(m.host.querySelector('[data-testid="lazy-b"]')).not.toBeNull();
    await act(async () => { observers[0].cb([{ isIntersecting: true }]); });
    expect(m.host.querySelector('[data-testid="row-b"]')).not.toBeNull();
  } finally { delete window.IntersectionObserver; }
});

// ── B4 §3.8 ────────────────────────────────────────────────────────────────────────────────────────────
test("roll berkelompok: produk → lot → lokasi → roll (fisik, tanpa lot = __none__), tertutup bawaan", async () => {
  respond = (c) => {
    const p = c.params || {};
    if (/roll-groups/.test(c.url) && p.level === "product") {
      return { data: { level: "product", total: 1, roll_total: 3, groups: [{ product_id: "p1", sku: "SKU1", product_name: "Katun",
        roll_count: 3, total_length: 90, unit: "meter", lot_count: 2, warehouse_count: 1, status_counts: { available: 3 } }] } };
    }
    if (/roll-groups/.test(c.url) && p.level === "lot") {
      return { data: { level: "lot", total: 2, groups: [
        { product_id: "p1", lot: "L1", roll_count: 2, total_length: 60, unit: "meter", min_length: 30, max_length: 30, location_count: 1, status_counts: { available: 2 } },
        { product_id: "p1", lot: "", roll_count: 1, total_length: 30, unit: "meter", min_length: 30, max_length: 30, location_count: 1, status_counts: { available: 1 } }] } };
    }
    if (/roll-groups/.test(c.url) && p.level === "location") {
      return { data: { level: "location", total: 1, groups: [{ product_id: "p1", lot: p.lot, warehouse_id: "wh1", warehouse_name: "Jakarta",
        bin_id: "", bin_code: "", roll_count: 1, total_length: 30, unit: "meter", status_counts: { available: 1 } }] } };
    }
    if (/inventory\/rolls/.test(c.url)) {
      return { data: { items: [{ id: "r9", roll_no: "R-009", length_remaining: 30, unit: "meter", grade: "A", status: "available" }],
        total: 1, page: 1, page_size: 50, has_more: false } };
    }
    return { data: {} };
  };
  const m = await mount(<RollGroupView params={{ location_view: 1, owner_entity_id: "ent_ksc" }} search="" />);
  const groupReq = captured.find((c) => /roll-groups/.test(c.url));
  expect(groupReq.params).toMatchObject({ level: "product", owner_entity_id: "ent_ksc", page: 1 });
  expect(m.host.textContent).toMatch(/3 roll/);
  expect(m.host.querySelector('[data-testid="rg-lots-p1"]')).toBeNull();   // tertutup bawaan
  await click(m.host.querySelector('[data-testid="rg-product-p1"]'));
  expect(m.host.querySelector('[data-testid="rg-lot-p1-L1"]')).not.toBeNull();
  await click(m.host.querySelector('[data-testid="rg-lot-p1-none"]'));
  const locReq = captured.find((c) => /roll-groups/.test(c.url) && c.params.level === "location");
  expect(locReq.params).toMatchObject({ product_id: "p1", lot: "" });
  await click(m.host.querySelector('[data-testid="rg-loc-wh1-none"]'));
  const rollReq = captured.find((c) => /inventory\/rolls/.test(c.url));
  expect(rollReq.params).toMatchObject({ product_id: "p1", lot: "__none__", warehouse_id: "wh1", bin_id: "", scope: "physical" });
  expect(m.host.querySelector('[data-testid="rg-roll-r9"]')).not.toBeNull();
  await act(async () => m.root.unmount());
});
