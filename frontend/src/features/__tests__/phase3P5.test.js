// Fase 3 · P5 — rantai pasok: satu daftar transfer (D-16), satu alur stock opname dengan metode RFID (D-15),
// SPK inspeksi ber-preset "Hanya yang DITAHAN" (D-28), satu pop-up rincian PO (D-18), tautan skor mitra (D-22).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";

import TransferList, { transferKindOf } from "../wms/transfer/TransferList";
import StockOpnameTab from "../wms/StockOpnameTab";
import POCompactPanel from "../admin/po/POCompactPanel";
import InspectionsView from "../inspections/InspectionsView";
import MakloonClaimsView from "../purchasing/makloon/MakloonClaimsView";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(() => Promise.resolve({ data: {} })), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
}
afterEach(async () => { if (root) await act(async () => { root.unmount(); }); host?.remove(); root = null; axios.get.mockReset(); });
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);

describe("D-16 — satu daftar transfer dengan kolom Jenis", () => {
  const rows = [
    { id: "t1", code: "KSC/TRF-00001", status: "waiting_approval", transfer_kind: "inter_entity",
      source_entity_name: "Sukacita", dest_entity_name: "Kanda", source_warehouse_name: "WH A", dest_warehouse_name: "WH B",
      items: [{ sku: "K1", product_name: "Katun", qty: 10, unit: "yard" }] },
    { id: "t2", code: "KSC/TRF-00002", status: "completed", source_warehouse_name: "WH A", dest_warehouse_name: "WH C", items: [] },
  ];
  test("record lama tanpa transfer_kind = antar gudang (sama dengan server)", () => {
    expect(transferKindOf(rows[0])).toBe("inter_entity");
    expect(transferKindOf(rows[1])).toBe("intra_entity");
  });
  test("tiap transfer tampil SEKALI dengan lencana jenis; testid baris lama dipertahankan", () => {
    const html = renderToStaticMarkup(<TransferList rows={rows} onOpen={() => {}} />);
    expect(html.match(/data-testid="transfer-card-t1"/g)).toHaveLength(1);
    expect(html).toContain('data-testid="transfer-kind-t1"');
    expect(html).toContain("Antar PT");
    expect(html).toContain("Antar gudang");
    expect(html).toContain('data-testid="transfer-route-t1"');
  });
});

describe("D-15 — stock opname: metode Sapu RFID hanya untuk peran yang dulu membuka Lokasi RFID", () => {
  beforeEach(() => { axios.get.mockImplementation(() => Promise.resolve({ data: [] })); });
  test("gudang (boleh membuka Lokasi RFID) melihat chip metode; pilih RFID → panel sapuan", async () => {
    const picked = [];
    await mount(
      <AppNavProvider role="warehouse">
        <StockOpnameTab method="count" onMethodChange={(m) => picked.push(m)} warehouses={[{ id: "wh1", name: "Bandung" }]}
          cycleCountProps={{ token: "x", warehouses: [], products: [] }} />
      </AppNavProvider>);
    expect(q("wms-opname-method-count")).not.toBeNull();
    await act(async () => { q("wms-opname-method-rfid").click(); });
    expect(picked).toEqual(["rfid"]);
  });
  test("manajer (tanpa menu RFID) tidak melihat metode RFID walau preset meminta", async () => {
    await mount(
      <AppNavProvider role="manager">
        <StockOpnameTab method="rfid" warehouses={[]} cycleCountProps={{ token: "x", warehouses: [], products: [] }} />
      </AppNavProvider>);
    expect(q("wms-opname-method-row")).toBeNull();
    expect(q("wms-opname-rfid")).toBeNull();
  });
  test("tautan ke sesi opname tertentu selalu membuka Hitung fisik", async () => {
    await mount(
      <AppNavProvider role="warehouse">
        <StockOpnameTab method="rfid" warehouses={[]}
          cycleCountProps={{ token: "x", warehouses: [], products: [], focusSessionId: "cc1" }} />
      </AppNavProvider>);
    expect(q("wms-opname-rfid")).toBeNull();
  });
});

describe("D-28 — SPK Inspeksi ber-preset 'Hanya yang DITAHAN'", () => {
  test("preset { hold: true } menyalakan saringan dan dikirim ke server sebagai hold_only", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.includes("meta")
      ? { kinds: [], statuses: [], policy: {} } : { items: [], total: 0, stats: {} } }));
    await mount(
      <ViewPresetProvider preset={{ view: "inspections", nonce: 1, hold: true }}>
        <InspectionsView currentUser={{ role: "manager", permissions: {} }} />
      </ViewPresetProvider>);
    await flush();
    expect(q("ins-chip-hold").getAttribute("aria-pressed")).toBe("true");
    const listCalls = axios.get.mock.calls.filter(([url]) => url.endsWith("/inspections"));
    expect(listCalls.some(([, cfg]) => cfg?.params?.hold_only === true)).toBe(true);
  });
});

describe("D-18 — kepala ringkas PO di dalam satu pop-up", () => {
  const po = { id: "po1", po_number: "PO-1", status: "pending", items: [] };
  test("tanpa onOpenFull/onClose: tidak ada tombol 'Lihat detail lengkap' (pop-up kedua) atau tutup ganda", () => {
    const html = renderToStaticMarkup(<POCompactPanel po={po} currentUser={{ role: "admin", permissions: {} }} />);
    expect(html).not.toContain("po-open-full-detail");
    expect(html).not.toContain("po-compact-close");
  });
});

describe("D-22 — Klaim Selisih Makloon menautkan skor mitra", () => {
  test("tabel skor tidak lagi digandakan; peran berwenang melihat tombol ke Kinerja Mitra Makloon", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.includes("scorecard")
      ? [{ makloon_id: "mk1", makloon_name: "Mitra A", steps: 3 }] : [] }));
    await mount(
      <AppNavProvider role="manager">
        <MakloonClaimsView currentUser={{ role: "manager", permissions: {} }} />
      </AppNavProvider>);
    await flush();
    expect(q("partner-scorecard")).toBeNull();
    expect(q("makloon-claims-score-link-open")).not.toBeNull();
    expect(q("makloon-claims-score-link").textContent).toContain("1 mitra dinilai");
  });
});
