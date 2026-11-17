// Masukan pemilik 16 Nov — form Pesanan Khusus Baru (M10–M13).
// M10 induk hanya tahap kain jadi · M11 satuan ikut induk · M12 target harga opsional · M13 induk & warna tidak dobel.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CreateSpecialOrderForm from "../sales/CreateSpecialOrderForm";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../rnd/rndApi", () => ({ listColors: () => Promise.resolve([{ id: "c1", code: "KN-NVY", name: "Navy" }]) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, disabled }) => (
    <select data-testid={tid} value={value ?? ""} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>
      {!options.some((o) => o.value === "") && <option value="" />}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const TEMPLATES = [
  { id: "t_jadi", name: "Rayon Jadi", stage: "finished", base_unit: "yard" },
  { id: "t_lama", name: "Katun Lama (tanpa tahap)" },
  { id: "t_grey", name: "Grey Woven Poplin", stage: "grey", base_unit: "meter" },
  { id: "t_benang", name: "Benang Katun 30s", stage: "yarn", base_unit: "kg" },
];
const UNITS = [
  { code: "meter", label: "Meter", dimension: "length" }, { code: "yard", label: "Yard", dimension: "length" },
  { code: "kg", label: "Kilogram", dimension: "weight" }, { code: "pcs", label: "Pcs", dimension: "count" },
  { code: "lusin", label: "Lusin", dimension: "count" },
];

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
let root;
async function mount() {
  mockGet.mockImplementation((url) => Promise.resolve({ data:
    url.includes("product-templates") ? TEMPLATES
      : url.includes("uom-conversions/catalog") ? { units: UNITS, units_master: [] }
        : url.includes("design-requests/meta") ? { categories: {} } : [] }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(<CreateSpecialOrderForm token="t" onCreated={() => {}} onCancel={() => {}} />); });
  for (let i = 0; i < 4; i += 1) await act(async () => {});
}
afterEach(async () => { await act(async () => { root.unmount(); }); document.body.innerHTML = ""; mockGet.mockReset(); });
const pilih = async (el, v) => act(async () => {
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, v);
  el.dispatchEvent(new Event("change", { bubbles: true }));
});
const opsi = (el) => Array.from(el.options).map((o) => o.value).filter(Boolean);

test("M10 + M11 — induk hanya kain jadi; satuan mengikuti induk", async () => {
  await mount();
  await pilih(q("od-item-source-1"), "parent_product");
  expect(opsi(q("od-item-template-1"))).toEqual(["t_jadi", "t_lama"]);   // greige & benang tidak ditawarkan
  expect(opsi(q("od-item-unit-1"))).not.toContain("pcs");               // tanpa induk: panjang + kg saja
  await pilih(q("od-item-template-1"), "t_jadi");
  expect(q("od-item-unit-1").value).toBe("yard");                       // satuan ikut satuan dasar induk
  expect(opsi(q("od-item-unit-1"))).toEqual(["meter", "yard"]);         // dimensi sama (panjang)
});

test("M12 + M13 — target harga opsional; langkah 4 tanpa induk & warna dobel", async () => {
  await mount();
  expect(q("od-item-price-1").value).toBe("");
  expect(q("od-item-price-1").closest("label, div").textContent).toMatch(/opsional/i);
  await pilih(q("od-detail-level"), "full");
  expect(q("od-template")).toBeNull();
  expect(q("od-color")).toBeNull();
  expect(q("od-item-color-1")).not.toBeNull();   // warna diisi sekali di item
});

// M14/M15 — lini masa vertikal: tahap selesai/berjalan/belum, tanggal & pelaku, dokumen tahap, aksi di tahap berjalan.
describe("M14 — lini masa vertikal Pesanan Khusus", () => {
  const SpecialOrderChainPanel = jest.requireActual("../sales/SpecialOrderChainPanel").default;
  test("tahap berjalan menyebut sejak kapan + dokumen tahapnya; tahap selesai bertanggal", async () => {
    const order = {
      id: "od1", status: "approved", request_types: ["labdip"], detail_level: "reference",
      status_history: [{ status: "pending_approval", timestamp: "2026-11-01T00:00:00Z", user_name: "Ayu" },
        { status: "approved", timestamp: "2026-11-02T00:00:00Z", user_name: "Rina Manajer" }],
      chain: {
        phases: [["draft", "Draf"], ["pending_approval", "Menunggu persetujuan"], ["approved", "Disetujui"],
          ["sampling", "Sampling berjalan"], ["done", "Selesai"]],
        phase: "sampling", phase_parallel: [],
        samples: [{ id: "s1", number: "SMP-1", status: "in_progress", sample_types: ["labdip"], created_at: "2026-11-03T00:00:00Z" }],
      },
    };
    const host = document.createElement("div");
    document.body.appendChild(host);
    const r = createRoot(host);
    await act(async () => { r.render(<SpecialOrderChainPanel order={order} canEdit={false} canRoute={false} />); });
    const ph = (k) => host.querySelector(`[data-testid="od-phase-${k}"]`);
    expect(ph("approved").getAttribute("data-state")).toBe("done");
    expect(ph("approved").textContent).toContain("Rina Manajer");
    expect(ph("sampling").getAttribute("data-state")).toBe("now");
    expect(ph("sampling").textContent).toContain("Berjalan sejak");
    expect(ph("sampling").textContent).toContain("SMP-1");
    expect(ph("done").getAttribute("data-state")).toBe("todo");
    await act(async () => { r.unmount(); });
  });
});
