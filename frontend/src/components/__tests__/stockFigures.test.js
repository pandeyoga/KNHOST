// FIX-2 (audit 9 Nov 2026 — B1 UI-06/UI-40, B3a §10, B4 ADS) — komponen bersama "dua angka" stok + rincian.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import StockFigures, { figureState, figuresForGroup, stateOf, sumFigures } from "../StockFigures";

const DETAIL = {
  product_id: "p1", sku: "KNKNT-01", product_name: "LYFLEX NAVY", unit: "kg",
  scope: { label: "Soreang · Kanda Fabric", site_ids: ["s_srg"], entity_ids: ["ent_kanda"] },
  local: { rolls: 4, qty: 100.5, state: "ada" }, global: { rolls: 30, qty: 900, state: "ada" },
  on_hand: { local: { rolls: 5, qty: 125 }, global: { rolls: 40, qty: 1200 } },
  local_status: [{ key: "available", label: "Tersedia", qty: 100.5, rolls: 4 }, { key: "reserved", label: "Dipesan", qty: 24.5, rolls: 1 }],
  global_status: [{ key: "available", label: "Tersedia", qty: 900, rolls: 30 }, { key: "reserved", label: "Dipesan", qty: 300, rolls: 10 }],
  by_site: [{ site_id: "s_srg", site_name: "Soreang", local: true, available_qty: 100.5, available_rolls: 4,
    warehouses: [{ warehouse_id: "w1", name: "Soreang · Gudang Kanda", available_qty: 100.5, available_rolls: 4, reserved_qty: 24.5,
      committed_qty: 0, hold_qty: 0, wip_qty: 0, makloon_reserved_qty: 0 }] }],
  by_entity: [{ entity_id: "ent_kanda", entity_name: "Kanda Fabric", own: true, visible: true, available_qty: 100.5, available_rolls: 4 },
    { entity_id: "ent_ksc", entity_name: "Sukacita", own: false, visible: false, available_qty: 799.5, available_rolls: 26 }],
  incoming: [{ source: "transfer", label: "Transfer dalam perjalanan", number: "KANDA/TRF-00001", doc_id: "t1", qty: 250.65, rolls: 10,
    owner_entity_name: "Kanda Fabric", warehouse_id: "w9", warehouse_name: "Gudang Utama Kanda", warehouse_active: false, eta: "", in_atp: false },
  { source: "po", label: "PO terbuka", number: "KANDA/PO-00001", doc_id: "po1", qty: 1500, owner_entity_name: "Kanda Fabric",
    warehouse_id: "w1", warehouse_name: "Soreang · Gudang Kanda", warehouse_active: true, eta: "2026-11-05", in_atp: true }],
  atp: { horizon_days: 14, local: { available: 100.5, incoming_in_horizon: 1500, pending_demand: 0, atp: 1600.5 },
    global: { available: 900, incoming_in_horizon: 1500, pending_demand: 50, atp: 2350 } },
  definitions: { available: "Tersedia = …", local: "lokal", global: "global", incoming: "datang", atp: "atp", on_hand: "fisik" },
};

jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: jest.fn(() => Promise.resolve({ data: DETAIL })), put: jest.fn(() => Promise.resolve({ data: {} })) },
  API: "/api",
}));
jest.mock("@/utils/escapeLayers", () => ({ useEscapeClose: () => {} }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
}
afterEach(async () => { if (root) await act(async () => { root.unmount(); }); if (host) host.remove(); root = null; host = null; });
const q = (id) => document.querySelector(`[data-testid="${id}"]`);

describe("aturan angka", () => {
  test("stateOf: 0 = habis, < ambang server = rendah, selebihnya ada", () => {
    expect(stateOf(0)).toBe("habis");
    expect(stateOf(40, 100)).toBe("rendah");
    expect(stateOf(100, 100)).toBe("ada");
    expect(stateOf(41, 40)).toBe("ada");          // ambang mengikuti kiriman server, bukan ≤ 40 yang diketik di FE
  });

  test("sumFigures: varian satu keluarga + kembar tergabung dijumlah (roll & panjang), status pakai ambang server", () => {
    const fig = (l, g, lr = 1, gr = 2) => ({ unit: "yard", low_stock_qty: 100, local: { qty: l, rolls: lr }, global: { qty: g, rolls: gr } });
    const s = sumFigures([{ stock_figures: fig(10, 50) },
      { merged_members: [{ stock_figures: fig(20.25, 30) }, { stock_figures: fig(0, 25.5, 0, 1) }] }]);
    expect(s.unit).toBe("yard");
    expect(s.local).toEqual({ qty: 30.25, rolls: 2, state: "rendah" });
    expect(s.global).toEqual({ qty: 105.5, rolls: 5, state: "ada" });
    expect(sumFigures([{ id: "x" }])).toBeNull();
  });

  test("figuresForGroup: stok lokasi jualan menggantikan LOKAL; tombol jual mati hanya bila GLOBAL habis", () => {
    const group = { base: { base_unit: "kg" }, variants: [
      { id: "a", stock_figures: { unit: "kg", low_stock_qty: 100, local: { qty: 500, rolls: 20, state: "ada" }, global: { qty: 900, rolls: 30, state: "ada" } } }] };
    const atSite = figuresForGroup(group, { siteStock: { a: { own_qty: 0, rolls: 0 } }, siteName: "Soreang", entityName: "Kanda" });
    expect(atSite.local).toEqual({ qty: 0, rolls: 0, state: "habis" });
    expect(atSite.localLabel).toBe("Soreang · Kanda");
    expect(atSite.badge.key).toBe("lokal_habis");                       // bukan "Habis": PT/lokasi lain masih punya
    const none = figuresForGroup({ base: {}, variants: [{ id: "a", stock_figures: { unit: "kg", local: { qty: 0, rolls: 0 }, global: { qty: 0, rolls: 0 } } }] });
    expect(none.badge.key).toBe("habis");
  });

  test("figureState: chip Habis desktop & HP membaca angka server yang sama", () => {
    const row = { stock_figures: { local: { state: "habis" }, global: { state: "ada" } } };
    expect(figureState(row, "local")).toBe("habis");
    expect(figureState(row, "global")).toBe("ada");
    expect(figureState({}, "local", 0)).toBe("habis");                  // server lama: cadangan dari angka baris
  });
});

describe("StockFigures", () => {
  test("dua angka: LOKAL lalu GLOBAL, roll dulu lalu panjang + satuan; tanpa produk = tidak bisa diklik", async () => {
    await mount(<StockFigures testId="sf" unit="kg" local={{ qty: 100.5, rolls: 4, state: "ada" }} global={{ qty: 900, rolls: 30 }}
      localLabel="Soreang · Kanda Fabric" />);
    expect(q("sf").tagName).toBe("DIV");
    expect(q("sf-local").textContent).toMatch(/Soreang · Kanda Fabric.*4 roll · 100,5 kg/);
    expect(q("sf-global").textContent).toMatch(/Total grup \(semua PT\).*30 roll · 900 kg/);
  });

  test("HP (size lg): target sentuh ≥ 48 px & huruf ≥ 14 px; ketuk → rincian per status/lokasi/PT/akan datang/ATP", async () => {
    await mount(<StockFigures testId="sf" size="lg" unit="kg" local={DETAIL.local} global={DETAIL.global} productIds={["p1"]} />);
    const btn = q("sf");
    expect(btn.tagName).toBe("BUTTON");
    expect(btn.className).toMatch(/min-h-\[48px\]/);
    expect(btn.innerHTML).toMatch(/text-\[16px\]/);
    await act(async () => { btn.click(); });
    await act(async () => { await Promise.resolve(); });
    const api = require("../../services/apiClient").default;
    expect(api.get).toHaveBeenCalledWith("/api/stock/figures/p1", { params: {} });
    expect(q("sf-detail")).not.toBeNull();
    expect(q("sf-detail-pair").textContent).toMatch(/LOKAL · Soreang · Kanda Fabric.*4 roll · 100,5 kg.*GLOBAL.*30 roll · 900 kg/);
    expect(q("sf-detail-status").textContent).toMatch(/Dipesan.*1 roll · 24,5 kg.*10 roll · 300 kg/);
    expect(q("sf-detail-sites").textContent).toMatch(/Soreang · lokasi Anda/);
    expect(q("sf-detail-entities").textContent).toMatch(/Sukacita · angka saja/);   // PT di luar izin: angka saja
    expect(q("sf-detail-incoming").textContent).toMatch(/Transfer dalam perjalanan KANDA\/TRF-00001.*gudang non-aktif.*10 roll · 250,65 kg/);
    expect(q("sf-detail-incoming").textContent).toMatch(/PO terbuka KANDA\/PO-00001.*masuk ATP/);
    expect(q("sf-detail-atp").textContent).toMatch(/horizon 14 hari/);
    expect(q("sf-detail-atp").textContent).toMatch(/Global.*= 2\.350 kg/);
  });

  test("rincian memakai site jualan bila diberikan & bisa berganti varian", async () => {
    const api = require("../../services/apiClient").default;
    api.get.mockClear();
    await mount(<StockFigures testId="sf" unit="kg" local={DETAIL.local} global={DETAIL.global} productIds={["p1", "p2"]}
      productLabels={{ p1: "NAVY", p2: "HITAM" }} siteId="s_srg" />);
    await act(async () => { q("sf").click(); });
    await act(async () => { await Promise.resolve(); });
    expect(api.get).toHaveBeenLastCalledWith("/api/stock/figures/p1", { params: { site_id: "s_srg" } });
    const chips = q("sf-detail-variants").querySelectorAll("button");
    expect(chips.length).toBe(2);
    await act(async () => { chips[1].click(); });
    await act(async () => { await Promise.resolve(); });
    expect(api.get).toHaveBeenLastCalledWith("/api/stock/figures/p2", { params: { site_id: "s_srg" } });
  });
});
