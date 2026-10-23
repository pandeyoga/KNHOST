// UAT 23 Okt (permintaan pemilik) — penyelesaian retur PER ROLL: outcome campuran, roll yang belum siap "Belum diputus",
// roll yang sudah diputus tampil terkunci, nilai dari pratinjau server, simpan mengirim keputusan per roll.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReturnRollSettleModal from "../sales/ReturnRollSettleModal";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => (props) => (
  <select data-testid={props["data-testid"]} value={props.value} onChange={(e) => props.onValueChange(e.target.value)}>
    {(props.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
const axios = require("../../services/apiClient").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const wait = (ms) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });
const ok = (v, l) => ({ value: v, label: l, ok: true, why: "" });
const no = (v, l, why) => ({ value: v, label: l, ok: false, why });

const STATE = {
  mode: true, status: "inspected", settlements: [{ id: "rst1", seq: 1, status: "done" }],
  rows: [
    { roll_id: "r1", roll_no: "RL-1", product_name: "Denim", unit: "yard", actual_qty: 114.98, grade: "B", cut_treatment: "bs",
      settled: {}, options: [no("refund", "Pengembalian Dana", "Roll sudah dipecah"), ok("cutloss", "Cutloss")] },
    { roll_id: "r2", roll_no: "RL-2", product_name: "Denim", unit: "yard", actual_qty: 118.07, grade: "B",
      settled: {}, options: [ok("refund", "Pengembalian Dana"), ok("exchange", "Tukar Barang"), no("cutloss", "Cutloss", "Catat qty cacat")] },
    { roll_id: "r3", roll_no: "RL-3", product_name: "Denim", unit: "yard", actual_qty: 120, grade: "A",
      settled: { seq: 1, outcome: "reject", outcome_label: "Tolak klaim", qty_back: 120 }, options: [] },
  ],
};
const PREVIEW = {
  rolls: [{ roll_id: "r1", qty_stock: 0, qty_cut: 3, qty_back: 111.98, credit_amount: 75000 },
          { roll_id: "r2", qty_stock: 118.07, qty_cut: 0, qty_back: 0, credit_amount: 2951750 }],
  lines: [{ roll_no: "RL-1", outcome_label: "Cutloss", product_name: "Denim", quantity: 3, unit: "yard", unit_price: 25000, line_total: 75000 }],
  net_amount: 3026750, ppn_amount: 332942.5, gross_amount: 3359692.5, cogs_amount: 2125260, post_stock: true, blocked: "",
  split: [{ kind: "source_bill", label: "Potong sisa tagihan KSC/SO-00001", amount: 3359692.5 }], journal: [], basis: "x",
  source_bill_checked: true, order_number: "KSC/SO-00001",
};

test("modal per roll: pilihan hanya outcome sah, roll terputus terkunci, nilai per roll & simpan keputusan campuran", async () => {
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/roll-settlement") ? STATE : [] }));
  axios.post.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/preview") ? PREVIEW : { status: "inspected" } }));
  const done = jest.fn(async () => null);
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<ReturnRollSettleModal ret={{ id: "sret_1", number: "SRET-1" }} open onClose={() => {}} onDone={done} />); });
  await wait(10);
  const sel1 = q(host, "roll-settle-outcome-RL-1");
  expect([...sel1.options].map((o) => o.value)).toEqual(["", "cutloss"]);           // outcome tak sah tidak ditawarkan
  expect(q(host, "roll-settle-row-RL-1").textContent).toMatch(/Belum bisa: Pengembalian Dana/);
  expect(q(host, "roll-settle-done-RL-3").textContent).toMatch(/P1 · Tolak klaim/);   // sudah diputus → terkunci
  expect(q(host, "roll-settle-outcome-RL-3")).toBeNull();
  await act(async () => { sel1.value = "cutloss"; sel1.dispatchEvent(new Event("change", { bubbles: true })); });
  const sel2 = q(host, "roll-settle-outcome-RL-2");
  await act(async () => { sel2.value = "refund"; sel2.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(q(host, "roll-settle-payout")).not.toBeNull();                               // ada cutloss → pilihan kompensasi
  expect(q(host, "roll-settle-refund-account")).not.toBeNull();                        // ada pengembalian dana → akun kas
  await wait(450);
  const [purl, pbody] = axios.post.mock.calls.at(-1);
  expect(purl).toBe("/api/sales-returns/sret_1/roll-settlement/preview");
  expect(pbody.rolls).toEqual([{ roll_id: "r1", outcome: "cutloss" }, { roll_id: "r2", outcome: "refund" }]);
  expect(q(host, "roll-settle-row-RL-1").textContent).toMatch(/3 yard \(BS\).*111,98 yard.*75\.000/);
  expect(q(host, "settle-preview-gross").textContent).toMatch(/3\.359\.69[23]/);
  await act(async () => { q(host, "roll-settle-confirm").click(); });
  await wait(10);
  const [surl, sbody] = axios.post.mock.calls.at(-1);
  expect(surl).toBe("/api/sales-returns/sret_1/roll-settlement");
  expect(sbody).toMatchObject({ payout: "store_credit", rolls: [{ roll_id: "r1", outcome: "cutloss" }, { roll_id: "r2", outcome: "refund" }] });
  expect(done).toHaveBeenCalled();
  act(() => root.unmount());
});
