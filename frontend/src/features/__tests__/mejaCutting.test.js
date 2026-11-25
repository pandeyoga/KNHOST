// MEJA-15 — §5.6: Meja Cutting memakai DeskQueueCard; pelanggan & SKU tampil; terima hasil potong lewat pop-up.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";
import CuttingDesk, { toCuttingQueues } from "../samples/CuttingDesk";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), isCancel: () => false,
    defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});

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
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).sort((a, b) => b.length - a.length).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset(); sessionStorage.clear();
});

const DATA = { wait_thresholds: { warn_minutes: 60, late_minutes: 240 }, late_count: 0, queues: [
  { key: "to_cut", label: "Menunggu dipotong gudang", rows: [] },
  { key: "to_receive", label: "Hasil potong — menunggu diterima", rows: [
    { task_id: "t9", order_id: "o1", order_number: "SOS-9", customer_name: "Butik Melati", product_name: "Kain Batik", sku: "KB-9",
      sample_kind: "standard", quantity: 1.5, unit: "meter", warehouse_id: "w1", warehouse_name: "Gudang A", wait_minutes: 30,
      roll_owner_entity_id: "ent_ksc", cut_at: "2026-11-25T02:00:00Z" },
    { task_id: "t10", order_id: "o1", order_number: "SOS-9", customer_name: "Butik Melati", product_name: "Kain Lurik", sku: "KL-1",
      sample_kind: "standard", quantity: 1, unit: "meter", warehouse_id: "w1", warehouse_name: "Gudang A", wait_minutes: 20,
      roll_owner_entity_id: "ent_ksc" }] }] };

test("toCuttingQueues: baris memuat pelanggan, SKU, aksi hanya bila boleh terima", () => {
  const tr = toCuttingQueues(DATA, { canReceive: true }).find((x) => x.id === "to_receive");
  expect(tr.id).toBe("to_receive");
  expect(tr.rows[0]).toMatchObject({ ref_type: "wms_task", ref_id: "t9", row_key: "t9", number: "SOS-9", title: "Butik Melati",
    value: 1.5, unit: "meter", action: "Terima", action_kind: "receive_cut", order_id: "o1" });
  expect(tr.rows[0].subtitle).toContain("Kain Batik · KB-9");
  expect(toCuttingQueues(DATA, { canReceive: false }).find((x) => x.id === "to_receive").rows[0].action).toBe("");
});

test("baris menyebut pelanggan; rincian menyebut SKU; kartu ukuran tetap", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [{ id: "w1", name: "Gudang A" }] });
  await mount(<CuttingDesk canReceive />);
  expect(teks(q("cutting-title-t9"))).toBe("Butik Melati");
  expect(q("cutting-queue-to_receive").className).toContain("sm:h-[412px]");
  await klik("cutting-row-t9");
  expect(teks(q("cutting-detail-field-subtitle"))).toMatch(/Kain Batik · KB-9/);
});

test("Terima: pop-up lokasi + terima semua potongan pesanan", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [{ id: "w1", name: "Gudang A" }] });
  mockPost.mockResolvedValue({ data: { received: 2, failed: [] } });
  await mount(<CuttingDesk canReceive />);
  await klik("cutting-action-t9");
  expect(mockPost).not.toHaveBeenCalled();
  await klik("cutting-receive-all");
  await klik("cutting-receive-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/cutting/orders/o1/receive", { to_warehouse_id: "w1" });
  expect(mockToast).toHaveBeenCalled();
});

test("Terima satu baris memakai endpoint tugas; galat tampil di dalam pop-up", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [{ id: "w1", name: "Gudang A" }] });
  mockPost.mockRejectedValue({ response: { data: { detail: "Roll belum tiba" } } });
  await mount(<CuttingDesk canReceive />);
  await klik("cutting-action-t10");
  await klik("cutting-receive-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/cutting/tasks/t10/receive", { to_warehouse_id: "w1" });
  expect(q("cutting-receive-submit")).not.toBeNull();
  expect(document.body.textContent).toContain("Roll belum tiba");
});

test("tanpa izin terima: tidak ada tombol aksi", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [] });
  await mount(<CuttingDesk canReceive={false} />);
  expect(q("cutting-action-t9")).toBeNull();
});

test("tanpa px mentah & hex", () => {
  for (const rel of ["../samples/CuttingDesk.jsx", "../samples/CuttingReceiveDialog.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/text-\[\d/); expect(src).not.toMatch(/#[0-9A-Fa-f]{6}\b/);
  }
});
