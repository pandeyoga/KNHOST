// Uji alur A1 (Pelatihan Keuangan 18 Nov — pesanan sampai uang masuk) — tiga kebingungan layar yang ditemukan saat alur
// dijalankan sebagai pengguna:
//  (a) checkout POS: izin kredit disetujui Manajer SESUDAH kotak kredit dimuat → kini ada [Periksa ulang kredit]
//      (dulu tombol tetap "Kredit Tertahan" walau pesannya menyuruh menekan Buat Sales Order lagi);
//  (b) Meja Admin Sales: Pelacak SO dimuat ulang sesudah Periksa & lepas (dulu baris tetap "Periksa & lepas");
//  (c) Barang Keluar: pencarian roll dari onBlur yang tiba SESUDAH pengambilan tercatat diabaikan (dulu kotak hijau roll
//      lama muncul lagi sehingga [Kirim Pengambilan] bisa ditekan ulang).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, disabled }) => (
    <select data-testid={tid} value={value ?? ""} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>
      {!options.some((o) => o.value === "") && <option value="" />}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../wms/LoadingCheckPanel", () => () => null);
jest.mock("../wms/SampleCutPanel", () => () => null);
jest.mock("../wms/PickListPanel", () => () => null);
jest.mock("../orders/DispatchPaymentGatePanel", () => () => null);
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn(), notifyError: jest.fn() }));

import CreditGateBox from "../pos/CreditGateBox";
import SoTrackerCard from "../sales_admin/SoTrackerCard";
import KeepPendingPanel from "../sales_admin/KeepPendingPanel";
import OutboundScanInterface from "../wms/OutboundScanInterface";
import { setAccessContext } from "../../config/roles";

if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await tick(); await tick();
  return { host, root };
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = ""; setAccessContext(null); mockGet.mockReset(); mockPost.mockReset();
});
const typeIn = async (el, v) => act(async () => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
});

const GATE_TAHAN = {
  result: "tahan", raw_result: "tahan", checked: true, override: null, pay_before_ship: false,
  exposure: { ar_delivered: 9195518, open_orders: 0, giro_outstanding: 0, deposit: 0, this_order: 5382612, total: 14578130 },
  counted: { open_orders: true, giro: true, deposit: true }, limit: { credit_limit: 13000000, available: 0 },
  reasons: [{ code: "LEWAT_PLAFON", result: "tahan", message: "Eksposur Rp 14.578.130 melewati plafon Rp 13.000.000." }],
};

test("A1(a) kredit tertahan di checkout: [Periksa ulang kredit] memanggil pemeriksaan ulang; tanpa pemanggil tidak tampil", async () => {
  setAccessContext({ role: "sales", permissions: { credit_override: ["view", "create"] } });
  const onRecheck = jest.fn();
  await mount(<CreditGateBox credit={{ gate: GATE_TAHAN }} customer={{ id: "cus1", name: "Toko P" }} amount={5382612}
    entityId="ent_ksc" onRecheck={onRecheck} />);
  expect(q("credit-override-open")).not.toBeNull();
  expect(q("credit-gate-box-recheck").textContent).toContain("Periksa ulang kredit");
  await act(async () => { q("credit-gate-box-recheck").click(); });
  expect(onRecheck).toHaveBeenCalledTimes(1);
});

test("A1(a') tanpa onRecheck (pemakai lama) tidak ada tombol periksa ulang; kredit aman tidak menampilkan tombol", async () => {
  setAccessContext({ role: "sales", permissions: { credit_override: ["view", "create"] } });
  await mount(<CreditGateBox credit={{ gate: GATE_TAHAN }} customer={{ id: "cus1", name: "Toko P" }} amount={5382612} />);
  expect(q("credit-gate-box-recheck")).toBeNull();
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  const aman = { ...GATE_TAHAN, result: "lolos", raw_result: "lolos", reasons: [] };
  await mount(<CreditGateBox credit={{ gate: aman }} customer={{ id: "cus1", name: "Toko P" }} amount={1} onRecheck={() => {}} />);
  expect(q("credit-gate-box-result").textContent).toContain("Kredit aman");
  expect(q("credit-gate-box-recheck")).toBeNull();
});

test("A1(b) Pelacak SO dimuat ulang saat refreshKey naik (meja induk baru saja melepas SO)", async () => {
  const before = { rows: [{ id: "so1", number: "KSC/SO-1", customer_name: "Toko P", status_label: "Dicadangkan",
    next_step: "Diperiksa & dilepas ke gudang", owner_label: "Admin Sales", can_act: true, action: "Periksa & lepas" }], count: 1, actionable: 1 };
  const after = { rows: [{ id: "so1", number: "KSC/SO-1", customer_name: "Toko P", status_label: "Dikonfirmasi",
    next_step: "Diambil, dicek muat & diberangkatkan", owner_label: "Admin Gudang / Staf Gudang", can_act: false }], count: 1, actionable: 0 };
  mockGet.mockResolvedValueOnce({ data: before }).mockResolvedValueOnce({ data: after });
  const el = (k) => <SoTrackerCard desk="sales_admin" testPrefix="desk" refreshKey={k} onOpen={() => {}} />;
  const { root } = await mount(el(0));
  expect(q("desk-so-tracker-action-so1").textContent).toBe("Periksa & lepas");
  await act(async () => { root.render(el(1)); });
  await tick(); await tick();
  expect(mockGet).toHaveBeenCalledTimes(2);
  expect(q("desk-so-tracker-action-so1")).toBeNull();
  expect(q("desk-so-tracker-info-so1").textContent).toContain("Admin Gudang");
});

test("A1(b') Keep & Pending dimuat ulang saat refreshKey naik (SO yang sudah diperiksa keluar dari Keep)", async () => {
  setAccessContext({ role: "sales_admin", permissions: { order: ["view", "verify"] } });
  const keep = { counts: { keep: 1, pending: 0, in_transit: 0, unique: 1 },
    keep: [{ order_id: "so1", number: "KSC/SO-1", customer_name: "Toko P", grand_total: 1000, age_days: 0 }], pending: [], in_transit: [] };
  const kosong = { counts: { keep: 0, pending: 0, in_transit: 0, unique: 0 }, keep: [], pending: [], in_transit: [] };
  mockGet.mockResolvedValueOnce({ data: keep }).mockResolvedValueOnce({ data: kosong });
  const el = (k) => <KeepPendingPanel refreshKey={k} />;
  const { root } = await mount(el(0));
  expect(mockGet).toHaveBeenCalledTimes(1);
  expect(q("kp-count-keep").textContent).toContain("1");
  await act(async () => { root.render(el(1)); });
  await tick(); await tick();
  expect(mockGet).toHaveBeenCalledTimes(2);
  expect(q("kp-count-keep").textContent).toContain("0");
});

test("A1(c) jawaban pencarian roll yang terlambat (onBlur) tidak mengisi ulang form sesudah pengambilan tercatat", async () => {
  const TASK = { id: "t1", order_id: "so1", order_number: "KSC/SO-1", status: "created", sku: "SKU1", product_id: "p1",
    product_name: "Denim", warehouse_id: "wh1", warehouse_name: "Jakarta", entity_id: "ent_ksc", quantity: 117.8,
    picked_qty: 0, unit: "yard", customer_name: "Toko P" };
  const ROLL = { id: "r1", roll_no: "RL-1", warehouse_id: "wh1", owner_entity_id: "ent_ksc", status: "reserved",
    reserved_ref: { id: "so1" }, length_remaining: 117.8, lot: "L1" };
  let lambat = null;
  let nCari = 0;
  mockGet.mockImplementation((url) => {
    if (url === "/api/inventory/rolls") {
      nCari += 1;
      if (nCari === 1) return Promise.resolve({ data: [ROLL] });
      return new Promise((res) => { lambat = () => res({ data: [ROLL] }); });   // pencarian kedua (onBlur) ditahan
    }
    if (url.startsWith("/api/outbound/tasks")) return Promise.resolve({ data: [TASK] });
    return Promise.resolve({ data: url.includes("saved-views") ? [] : {} });
  });
  mockPost.mockResolvedValue({ data: { ...TASK, status: "packing", picked_qty: 117.8 } });
  await mount(<OutboundScanInterface user={{ permissions: {} }} />);
  await act(async () => { q("outbound-task-t1").click(); });
  await tick();
  const code = q("outbound-roll-code");
  await typeIn(code, "RL-1");
  await act(async () => { code.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
  await tick();
  expect(q("outbound-roll-info").textContent).toContain("RL-1");
  // Klik tombol = kotak kode kehilangan fokus → pencarian kedua berjalan (belum dijawab), lalu pengambilan tercatat.
  await act(async () => { code.dispatchEvent(new FocusEvent("focusout", { bubbles: true })); });
  await act(async () => { q("scan-task-t1").click(); });
  await tick();
  expect(mockPost).toHaveBeenCalledWith("/api/outbound/tasks/t1/scan-pick", null, expect.anything());
  expect(q("outbound-roll-info")).toBeNull();
  expect(typeof lambat).toBe("function");
  await act(async () => { lambat(); });
  await tick();
  expect(q("outbound-roll-info")).toBeNull();          // jawaban usang diabaikan
  expect(q("outbound-roll-hint")).not.toBeNull();
});
