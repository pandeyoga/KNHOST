// Trial 22 Okt 2026 — perbaikan temuan (docs/uat/2026-10-21/CATATAN_TEMUAN_TRIAL_22OKT.md).
// D2: hitung fisik GRN — panjang boleh diketik dalam satuan SJ/PO atau satuan dasar produk; satuan yang dipilih
//     ikut dikirim (server mengonversi ke satuan dasar). Dulu label "Panjang (meter)" tetapi angka disimpan sebagai yard.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import GrnCountPanel from "../wms/grn/GrnCountPanel";

const posted = [];
jest.mock("../wms/grn/grnApi", () => ({
  grnApi: {
    rolls: () => Promise.resolve([{ id: "r1", roll_no: "RL-1", grn_line_no: 1, length_initial: 109.36, unit: "yard",
      actual_task_qty: 100, lot: "L1", grade: "A", status: "receiving", scan_source: "count" }]),
    post: (...a) => { posted.push(a); return Promise.resolve({ grn: null }); },
    del: () => Promise.resolve({}),
  },
  errText: () => "gagal",
}));   // bukan jest.fn: resetMocks CRA
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A", label: "A" }] }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick();
  return root;
}

const grn = (target) => ({ id: "grn1", status: "counting", version: 1, lines: [{ line_no: 1, decision: "accept",
  target: { type: "po_task", po_number: "PO-1", sku: "LRK", product_name: "Lurik", ...target }, counted: { rolls: 1, qty: 100 } }] });

test("D2: hitung GRN — pilihan satuan SJ/PO vs stok, satuan terpilih dikirim, roll tampil dua satuan", async () => {
  posted.length = 0;
  const root = await mount(<GrnCountPanel grn={grn({ unit: "meter", base_unit: "yard" })} onChange={() => {}} canCount />);
  expect(q("grn-count-unit-1")).not.toBeNull();
  expect(q("grn-count-length-1").placeholder).toBe("Panjang (meter)");
  expect(q("grn-count-roll-r1").textContent).toMatch(/109\.36 yard \(= 100 meter\)/);
  const input = q("grn-count-length-1");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "100");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { q("grn-count-add-1").click(); });
  await tick();
  expect(posted[0][1]).toBe("lines/1/rolls");
  expect(posted[0][2]).toMatchObject({ length: 100, length_unit: "meter" });
  act(() => root.unmount());
});

test("D2: satuan SJ = satuan stok → tanpa pemilih satuan", async () => {
  const root = await mount(<GrnCountPanel grn={grn({ unit: "yard", base_unit: "yard" })} onChange={() => {}} canCount />);
  expect(q("grn-count-unit-1")).toBeNull();
  expect(q("grn-count-length-1").placeholder).toBe("Panjang (yard)");
  act(() => root.unmount());
});
