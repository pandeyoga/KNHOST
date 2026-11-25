// MEJA-10 — §5.4: lepas/teruskan ke gudang dengan pratinjau (pesanan, PT, gudang, baris) + konfirmasi.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import SalesAdminDesk from "../sales_admin/SalesAdminDesk";
import SampleAdminDesk from "../samples/SampleAdminDesk";
import ReleaseToWarehouseDialog, { orderLinesOf } from "../sales_admin/ReleaseToWarehouseDialog";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);
jest.mock("../sales_admin/CustomerGradeRulesCard", () => () => null);
jest.mock("../sales_admin/VerifyOrderDialog", () => () => null);
jest.mock("../sales_admin/FulfillmentDecisionDialog", () => () => null);
jest.mock("../home/ReturnDeskSummaryCard", () => ({
  __esModule: true, ...jest.requireActual("../home/ReturnDeskSummaryCard"),
  default: () => <div data-testid="return-desk-stub" />,
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
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
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset();
  sessionStorage.clear();
});

function berkasSumber(dir = path.join(__dirname, "..", "..")) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) return d.name === "__tests__" ? [] : berkasSumber(p);
    return /\.jsx?$/.test(d.name) ? [p] : [];
  });
}
const baca = (f) => fs.readFileSync(f, "utf8");


const wrapEnt = (el) => (
  <EntityScopeProvider selectedEntity="all" entities={[{ id: "ent_ksc", short_name: "KSC" }]}>{el}</EntityScopeProvider>);

const BARIS = { ref_type: "sales_order", ref_id: "so7", number: "SO-7", title: "Toko T", entity_id: "ent_ksc", value: 1, age_days: 2,
  action: "Lepas ke gudang", action_kind: "release",
  order_lines: [{ product_name: "Kain A", sku: "KA-1", quantity: 10, unit: "yard", warehouse: "Gudang Woven" },
                { product_name: "Kain B", sku: "KB-1", quantity: 5, unit: "yard", warehouse: "Gudang Knit" }] };

test("meja Admin Sales: Lepas ke gudang membuka pratinjau; endpoint baru dipanggil sesudah konfirmasi", async () => {
  routeGet({ "/sales-admin/desk": { queues: [{ id: "siap_dikonfirmasi", label: "Ditahan", count: 1, rows: [BARIS] }] } });
  mockPost.mockResolvedValue({ data: { released: true, order: { number: "SO-7", status: "confirmed" } } });
  await mount(wrapEnt(<SalesAdminDesk currentUser={{ permissions: { order: ["view", "confirm"] } }} onOpenDocument={() => {}} />));
  await klik("desk-action-so7");
  expect(mockPost).not.toHaveBeenCalled();
  expect(teks(q("release-confirm-order"))).toContain("SO-7 · Toko T");
  expect(teks(q("release-confirm-pt"))).toBe("KSC");
  expect(teks(q("release-confirm-warehouse"))).toContain("Gudang Woven, Gudang Knit");
  expect(document.body.querySelectorAll('[data-testid^="release-confirm-line-"]')).toHaveLength(2);
  await klik("release-confirm-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so7/release");
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SO-7") }));
  expect(q("release-confirm")).toBeNull();
});

test("galat di dalam pop-up; pop-up tetap terbuka", async () => {
  const run = jest.fn().mockRejectedValue({ response: { data: { detail: "Stok sudah dipakai pesanan lain." } } });
  const onDone = jest.fn();
  await mount(wrapEnt(<ReleaseToWarehouseDialog order={BARIS} run={run} onClose={() => {}} onDone={onDone} />));
  await klik("release-confirm-submit");
  expect(teks(q("release-confirm-error"))).toContain("Stok sudah dipakai pesanan lain.");
  expect(q("release-confirm")).not.toBeNull();
  expect(onDone).not.toHaveBeenCalled();
});

test("pesanan tanpa baris barang (Pelacak SO) dimuat dulu lewat GET /sales-orders/{id}", async () => {
  routeGet({ "/sales-orders/so9": { id: "so9", number: "SO-9", customer_name: "Toko S", entity_id: "ent_ksc",
    items: [{ product_name: "Kain Z", sku: "KZ", quantity: 4, unit: "roll", allocations: [{ warehouse_name: "Gudang Z" }] }] } });
  await mount(wrapEnt(<ReleaseToWarehouseDialog order={{ id: "so9", number: "SO-9", title: "Toko S", entity_id: "ent_ksc" }}
    run={() => Promise.resolve({})} onClose={() => {}} onDone={() => {}} />));
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so9");
  expect(teks(q("release-confirm-warehouse"))).toBe("Gudang Z");
  expect(teks(q("release-confirm-line-0"))).toContain("Kain Z");
});

test("muat pesanan gagal: kirim nonaktif, pesan galat muat (bukan 'Belum ada baris barang')", async () => {
  mockGet.mockRejectedValue({ response: { data: { detail: "Server sibuk." } } });
  const run = jest.fn().mockResolvedValue({});
  await mount(wrapEnt(<ReleaseToWarehouseDialog order={{ id: "so9", number: "SO-9", title: "Toko S", entity_id: "ent_ksc" }}
    run={run} onClose={() => {}} onDone={() => {}} />));
  expect(q("release-confirm-submit").disabled).toBe(true);
  expect(teks(q("release-confirm-load-failed"))).toContain("Gagal memuat rincian pesanan — tutup lalu coba lagi.");
  expect(q("release-confirm-no-lines")).toBeNull();
  await klik("release-confirm-submit");
  expect(run).not.toHaveBeenCalled();
});

test("sample: Teruskan ke gudang di meja lewat pop-up yang sama", async () => {
  const sos = { ref_type: "sample_order", ref_id: "sos1", number: "KSC/SOS-1", title: "Toko S", entity_id: "ent_ksc", age_days: 0,
    action: "Teruskan ke Gudang", action_kind: "confirm", order_lines: [{ product_name: "Sample A", quantity: 1, unit: "meter", warehouse: "" }] };
  routeGet({ "/sample-orders/desk": { queues: [{ id: "siap_gudang", label: "Siap", count: 1, value_kind: "count", rows: [sos] }] } });
  mockPost.mockResolvedValue({ data: { tasks_created: 1 } });
  await mount(wrapEnt(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view", "confirm"] } }} onOpenDocument={() => {}} />));
  await klik("sample-desk-action-sos1");
  expect(mockPost).not.toHaveBeenCalled();
  expect(teks(q("release-confirm-title"))).toBe("Teruskan ke gudang?");
  expect(teks(q("release-confirm-warehouse"))).toBe("—");
  await klik("release-confirm-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sample-orders/sos1/confirm");
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "KSC/SOS-1 diteruskan ke gudang — 1 tugas potong lahir." }));
});

test("orderLinesOf dari items pesanan", () => {
  expect(orderLinesOf({ items: [{ product_name: "K", sku: "S", quantity: 3, unit: "yard",
    allocations: [{ warehouse_name: "G1" }, { warehouse_name: "G1" }, { warehouse_name: "G2" }] }] }))
    .toEqual([{ product_name: "K", sku: "S", quantity: 3, unit: "yard", warehouse: "G1, G2" }]);
});

test("R6: satuan = unit jual, bukan base_unit", () => {
  const [l] = orderLinesOf({ items: [{ product_name: "K", sku: "S", quantity: 2, unit: "yard", base_unit: "meter", base_quantity: 1.8 }] });
  expect(l.unit).toBe("yard");
  expect(l.quantity).toBe(2);
});

test("setiap pemanggil lepas/teruskan memakai ReleaseToWarehouseDialog", () => {
  const pola = /\breleaseOrder\(|\bconfirmSampleOrder\(/;
  const kecuali = ["features/sales_admin/workDeskApi.js", "features/samples/sampleApi.js"];
  const salah = berkasSumber().filter((f) => !kecuali.some((k) => f.endsWith(k)) && pola.test(baca(f))
    && !baca(f).includes("ReleaseToWarehouseDialog"));
  expect(salah).toEqual([]);
});
