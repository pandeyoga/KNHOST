// MEJA-7 — tab Pantau (§5.1, §5.5): baris Pelacak SO bisa dibuka (termasuk yang bukan wewenang meja), huruf ≥ 12 px.
// R7: aksi dialog (inPlaceActions) langsung dijalankan; aksi pindah layar membuka rincian dulu.
// R18: baris `tr` hanya klik tetikus (tanpa role/tabIndex); jalur papan ketik = tombol nomor SO.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import SoTrackerCard, { trackerRowToDeskRow } from "../sales_admin/SoTrackerCard";
import { soTrackerLink } from "../sales_admin/workDeskApi";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: jest.fn(), defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = ""; mockGet.mockReset();
});

const TRACK = { count: 3, actionable: 2, rows: [
  { id: "so1", number: "SO-1", customer_name: "Toko A", status: "reserved", status_label: "Dicadangkan", next_step: "Diperiksa & dilepas",
    owner_label: "Admin Sales", owner_roles: ["sales_admin"], can_act: true, action: "Periksa & lepas", grand_total: 1000,
    created_at: "2026-11-20T03:00:00Z", updated_at: "2026-11-21T03:00:00Z", idle_days: 4, entity_id: "ent_ksc", order_type: "regular" },
  { id: "so2", number: "SO-2", customer_name: "Toko B", status: "confirmed", status_label: "Dikonfirmasi", next_step: "Diambil",
    owner_label: "Admin Gudang", owner_roles: ["warehouse_admin"], can_act: false, grand_total: 2000,
    created_at: "2026-11-20T03:00:00Z", updated_at: "2026-11-21T03:00:00Z", idle_days: 4, entity_id: "ent_ksc", order_type: "regular" },
  { id: "so3", number: "SO-3", customer_name: "Toko C", status: "confirmed", status_label: "Dikonfirmasi", next_step: "Bukti terima",
    owner_label: "Admin Sales", owner_roles: ["sales_admin"], can_act: true, action: "Buka SO", grand_total: 3000,
    created_at: "2026-11-20T03:00:00Z", updated_at: "2026-11-21T03:00:00Z", idle_days: 1, entity_id: "ent_ksc", order_type: "regular" }] };

test("baris bukan wewenang meja tetap bisa dibuka: rincian tanpa aksi, dengan Buka layar penuh", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  const onOpen = jest.fn(); const onOpenFull = jest.fn();
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" onOpen={onOpen} onOpenFull={onOpenFull} showRefresh={false} />);
  expect(q("desk-so-tracker-refresh")).toBeNull();
  await klik("desk-so-tracker-row-so2");
  expect(teks(q("desk-so-tracker-detail-title"))).toContain("SO-2 · Toko B");
  expect(q("desk-so-tracker-detail-action")).toBeNull();
  await klik("desk-so-tracker-detail-open-full");
  expect(onOpenFull).toHaveBeenCalledWith(expect.objectContaining({ id: "so2" }));
});

test("aksi di tempat langsung dijalankan; aksi pindah layar membuka rincian dulu (R7)", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  const onOpen = jest.fn();
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" onOpen={onOpen} inPlaceActions={["Periksa & lepas"]} />);
  await klik("desk-so-tracker-action-so1");
  expect(onOpen).toHaveBeenCalledTimes(1);
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "so1" })); expect(q("desk-so-tracker-detail")).toBeNull();
  // aksi navigasi: rincian terbuka dulu, aksi bertanda pindah layar, baru onOpen dari rincian
  await klik("desk-so-tracker-action-so3");
  expect(onOpen).toHaveBeenCalledTimes(1);
  expect(q("desk-so-tracker-detail")).not.toBeNull();
  expect(q("desk-so-tracker-detail-action-nav")).not.toBeNull();
  await klik("desk-so-tracker-detail-action");
  expect(onOpen).toHaveBeenCalledTimes(2);
  expect(onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "so3" }));
});

test("klik baris membuka rincian; baris tanpa role/tabIndex; Enter pada tombol nomor membuka sekali", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" />);
  const tr = q("desk-so-tracker-row-so1");
  expect(tr.getAttribute("role")).toBeNull(); expect(tr.hasAttribute("tabindex")).toBe(false);
  const nomor = q("desk-so-tracker-number-so1");
  expect(nomor.className).toContain("link-button");
  expect(nomor.querySelector("span").className).toContain("text-fs-13");
  // Enter pada <button> = klik bawaan peramban; klik tombol tidak boleh membuka dua kali (gelembung ke tr diabaikan)
  await klik("desk-so-tracker-number-so1");
  expect(document.body.querySelectorAll('[data-testid="desk-so-tracker-detail"]').length).toBe(1);
});

test("label kolom 12 px tanpa huruf besar; tautan SOS ke Pesanan Sample", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" />);
  const head = q("desk-so-tracker-head");
  expect(head.className).toContain("text-fs-12"); expect(head.className).not.toContain("uppercase");
  expect(q("desk-so-tracker-help")).not.toBeNull();
  expect(soTrackerLink({ id: "s1", number: "SOS-1", order_type: "sample", owner_roles: ["sample_admin"] }))
    .toMatchObject({ view: "sample-orders", focus_type: "sample_order", focus_id: "s1" });
});

test("trackerRowToDeskRow memetakan baris pelacak", () => {
  const r = trackerRowToDeskRow(TRACK.rows[0]);
  expect(r).toMatchObject({ ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", value: 1000, age_days: 4,
    badge: "reserved", entity_id: "ent_ksc", action: "Periksa & lepas", action_kind: "tracker" });
  expect(r._tracker).toBe(TRACK.rows[0]);
  expect(trackerRowToDeskRow(TRACK.rows[1]).action).toBe("");
});

test("berkas Pantau tanpa px mentah & hex", () => {
  for (const rel of ["../sales_admin/SoTrackerCard.jsx", "../sales_admin/KeepPendingPanel.jsx",
                     "../sales_admin/CustomerGradeRulesCard.jsx", "../home/ReturnDeskSummaryCard.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/text-\[\d/); expect(src).not.toMatch(/#[0-9A-Fa-f]{6}\b/); expect(src).not.toMatch(/text-2xl/);
  }
});
