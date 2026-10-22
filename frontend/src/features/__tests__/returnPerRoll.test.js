// Permintaan pemilik 23 Okt — klaim retur PER ROLL (alasan, kondisi, checklist, foto) dan keputusan Terima/Tolak
// per roll oleh pemegang `sales_return.decide_rolls`.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CreateReturnForm from "../sales/CreateReturnForm";
import ReturnRollsPanel from "../sales/ReturnRollsPanel";
import { claimErrors, claimsToItem } from "../sales/ReturnRollClaims";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => (props) => (
  <select data-testid={props["data-testid"]} value={props.value} onChange={(e) => props.onValueChange(e.target.value)}>
    {(props.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const PRODUCT = { product_id: "p1", product_name: "Kain A", sku: "SKU-A", unit: "yard", max: 30 };
const ROLLS = [{ roll_id: "r1", roll_no: "RL-1", product_id: "p1", remaining: 10, unit: "yard", shipment_no: "SJ-1" },
               { roll_id: "r2", roll_no: "RL-2", product_id: "p1", remaining: 20, unit: "yard", shipment_no: "SJ-1" }];
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const wait = (ms) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const setValue = async (el, v) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true })); });
};
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return { host, root };
}

test("claimsToItem: qty baris = jumlah klaim roll; detail per roll ikut, berkas foto tidak", () => {
  const it = claimsToItem(PRODUCT, {
    r1: { qty: "10", condition: "ok", reason: "hangtag lepas", hangtag_missing: true, cut_by_customer: false, files: [{}] },
    r2: { qty: "5.5", condition: "damaged", reason: "sudah dipotong", hangtag_missing: false, cut_by_customer: true, files: [] },
  });
  expect(it).toMatchObject({ product_id: "p1", quantity_returned: 15.5, roll_ids: ["r1", "r2"], roll_qtys: { r1: 10, r2: 5.5 },
                             condition: "damaged" });
  expect(it.roll_details.r2).toEqual({ condition: "damaged", reason: "sudah dipotong", hangtag_missing: false, cut_by_customer: true });
  expect(it.roll_details.r1.files).toBeUndefined();
});

test("claimErrors: qty nol, melebihi sisa roll, dan alasan kosong ditolak per roll", () => {
  expect(claimErrors(PRODUCT, ROLLS, { r1: { qty: "0", reason: "noda" } })).toEqual(["RL-1: qty harus lebih dari 0"]);
  expect(claimErrors(PRODUCT, ROLLS, { r1: { qty: "11", reason: "noda" } })[0]).toMatch(/RL-1: qty melebihi sisa/);
  expect(claimErrors(PRODUCT, ROLLS, { r2: { qty: "5", reason: " " } })).toEqual(["RL-2: isi alasan roll ini"]);
  expect(claimErrors(PRODUCT, ROLLS, { r2: { qty: "5", reason: "noda" } })).toEqual([]);
});

test("form: roll dicentang → isian per roll; kirim membawa roll_details & foto per roll ber-roll_id", async () => {
  axios.get.mockImplementation((url) => {
    if (url === "/api/sales-returns/eligible-orders") return Promise.resolve({ data: { items: [{ id: "so_a", number: "SO-A", customer_name: "Toko A", status: "shipped" }], total: 1 } });
    if (url === "/api/sales-returns/returnable") return Promise.resolve({ data: { products: [{ ...PRODUCT, remaining: 30 }], rolls: ROLLS } });
    return Promise.resolve({ data: {} });
  });
  axios.post.mockImplementation((url) => Promise.resolve({ data: url === "/api/sales-returns" ? { id: "sret_1" } : { id: "sret_1", status: "pending_approval" } }));
  const onCreated = jest.fn();
  const { host, root } = await mount(<CreateReturnForm variant="modal" onCreated={onCreated} onCancel={() => {}} />);
  await wait(350);
  const sel = q(host, "return-order-select");
  await act(async () => { sel.value = "so_a"; sel.dispatchEvent(new Event("change", { bubbles: true })); });
  await flush();
  const base = "return-item-p1-roll";
  expect(q(host, `${base}-r1-reason`)).toBeNull();   // belum dicentang → belum ada isian
  await act(async () => { q(host, `${base}-r1-check`).click(); q(host, `${base}-r2-check`).click(); });
  await setValue(q(host, `${base}-r1-reason`), "Hangtag lepas");
  await setValue(q(host, `${base}-r2-reason`), "Sudah dipotong 3 yard");
  await setValue(q(host, `${base}-r2-qty`), "12");
  await act(async () => { q(host, `${base}-r1-hangtag`).click(); q(host, `${base}-r2-cut`).click(); });
  const photo = new File(["x"], "potong.jpg", { type: "image/jpeg" });
  const inp = q(host, `${base}-r2-photo-input`);
  Object.defineProperty(inp, "files", { value: [photo], configurable: true });
  await act(async () => { inp.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(q(host, "return-item-p1-total").textContent).toContain("22");
  await act(async () => { q(host, "save-return-btn").click(); });
  await flush(); await flush();
  const [, body] = axios.post.mock.calls.find(([u]) => u === "/api/sales-returns");
  expect(body.submit_now).toBe(false);   // ada foto → draf dulu, unggah, baru diajukan
  expect(body.items).toHaveLength(1);
  expect(body.items[0]).toMatchObject({ quantity_returned: 22, roll_ids: ["r1", "r2"], roll_qtys: { r1: 10, r2: 12 } });
  expect(body.items[0].roll_details.r1).toMatchObject({ reason: "Hangtag lepas", hangtag_missing: true, cut_by_customer: false });
  expect(body.items[0].roll_details.r2).toMatchObject({ reason: "Sudah dipotong 3 yard", cut_by_customer: true });
  const up = axios.post.mock.calls.find(([u]) => u === "/api/sales-returns/sret_1/attachments");
  expect(up[1].get("roll_id")).toBe("r2");
  expect(axios.post.mock.calls.some(([u]) => u === "/api/sales-returns/sret_1/submit")).toBe(true);
  expect(onCreated).toHaveBeenCalled();
  await act(async () => { root.unmount(); });
});

const RET = { id: "sret_1", status: "pending_approval", attachments: [{ id: "a1", roll_id: "r2", filename: "potong.jpg" }] };
const ITEM = { product_id: "p1", product_name: "Kain A", sku: "SKU-A", unit: "yard", quantity_returned: 30, qty_rolls: 2,
  roll_ids: ["r1", "r2"], roll_qtys: { r1: 10, r2: 20 }, roll_nos: { r1: "RL-1", r2: "RL-2" },
  roll_details: { r1: { reason: "hangtag", condition: "ok", hangtag_missing: true },
                  r2: { reason: "dipotong", condition: "ok", cut_by_customer: true } } };

test("panel: pemegang decide_rolls menolak roll dengan alasan → POST roll-decisions; tanpa izin tak ada tombol", async () => {
  axios.post.mockResolvedValue({ data: {} });
  const onChanged = jest.fn();
  let m = await mount(<ReturnRollsPanel ret={RET} items={[ITEM]} fullView canDecide onChanged={onChanged} />);
  expect(q(m.host, "return-roll-r2").textContent).toContain("Sudah dipotong");
  expect(q(m.host, "return-roll-r2").querySelector("a").getAttribute("href")).toBe("/api/sales-returns/sret_1/attachments/a1/download");
  await act(async () => { q(m.host, "roll-reject-r2").click(); });
  await act(async () => { q(m.host, "roll-decisions-save").click(); });
  expect(q(m.host, "roll-decisions-error").textContent).toMatch(/alasan tolak/i);   // alasan wajib
  expect(axios.post).not.toHaveBeenCalled();
  await setValue(q(m.host, "roll-reject-reason-r2"), "Kain sudah dipotong");
  await act(async () => { q(m.host, "roll-accept-r1").click(); });
  await act(async () => { q(m.host, "roll-decisions-save").click(); });
  await flush();
  expect(axios.post).toHaveBeenCalledWith("/api/sales-returns/sret_1/roll-decisions", { decisions: [
    { roll_id: "r2", decision: "reject", reason: "Kain sudah dipotong" }, { roll_id: "r1", decision: "accept", reason: "" }] });
  expect(onChanged).toHaveBeenCalled();
  await act(async () => { m.root.unmount(); });
  m = await mount(<ReturnRollsPanel ret={RET} items={[{ ...ITEM, rejected_rolls: [{ roll_id: "r3", roll_no: "RL-3", qty: 5, unit: "yard", reason: "dipotong", by: "Admin" }] }]}
    fullView={false} canDecide={false} />);
  expect(q(m.host, "roll-reject-r2")).toBeNull();
  expect(q(m.host, "roll-decisions-save")).toBeNull();
  expect(q(m.host, "return-item-value-0")).toBeNull();
  expect(q(m.host, "return-roll-rejected-r3").textContent).toContain("Ditolak");
  await act(async () => { m.root.unmount(); });
});
