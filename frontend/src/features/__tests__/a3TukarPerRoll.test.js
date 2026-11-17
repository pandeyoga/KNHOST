// A3 retur (pelatihan keuangan 18 Nov) — "Tukar Barang" yang diputus PER ROLL tetap bertipe "retur" tetapi menunggu pesanan
// pengganti (`exchange_pending`). Dulu panel "Pesanan pengganti" hanya tampil untuk tipe "penggantian", sehingga Admin Sales
// tidak punya tombol [Buat pesanan pengganti] (uji jalan A3, peserta 49: SRET-00013 berhenti di sini).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReturnReplacementPanel from "../sales/ReturnReplacementPanel";

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../config/roles", () => ({ canCurrent: () => true }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function settle() { await act(async () => {}); await act(async () => {}); }
async function mount(el) {
  document.body.innerHTML = "";
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(el); });
  await settle();
}
const OBL = [{ product_id: "p1", product_name: "DENIM TENCEL TAUPE", unit_base: "yard", qty_base: 114.22, qty_yard: 114.22,
  conversion_error: "", sold_grade: "A", unit_price_base: 25000, value: 2855500, roll_ids: ["r1"] }];

beforeEach(() => {
  mockGet.mockReset(); mockPost.mockClear();
  mockGet.mockImplementation(() => Promise.resolve({ data: { obligation: OBL, order_id: "", order_number: "", summary: {} } }));
});

test("per roll: retur tipe 'retur' + exchange_pending → panel & tombol pengganti tampil, kirim qty kewajiban", async () => {
  await mount(<ReturnReplacementPanel ret={{ id: "sret_1", return_type: "retur", status: "credit_settled", exchange_pending: true,
    roll_outcomes: { r1: { outcome: "exchange" } } }} />);
  expect(q("return-replacement-panel")).not.toBeNull();
  expect(q("replacement-qty-p1").value).toBe("114.22");
  await act(async () => { q("replacement-create").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
  expect(mockPost).toHaveBeenCalledWith("/api/sales-returns/sret_1/replacement-order", { items: [{ product_id: "p1", qty_yard: 114.22 }] });
});

test("retur biasa tanpa tukar barang → panel tidak tampil", async () => {
  await mount(<ReturnReplacementPanel ret={{ id: "sret_2", return_type: "retur", status: "refund_settled",
    roll_outcomes: { r1: { outcome: "refund" } } }} />);
  expect(q("return-replacement-panel")).toBeNull();
  expect(mockGet).not.toHaveBeenCalled();
});

test("per roll sesudah pengganti dibuat (tidak menunggu lagi) → ringkasan tampil, tombol tidak", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: { obligation: OBL, order_id: "so_9", order_number: "KSC/SO-00090",
    summary: { replacement_total: 3169605, credit_applied: 3169605, to_bill: 0, remaining_credit: 0, rule: "" } } }));
  await mount(<ReturnReplacementPanel ret={{ id: "sret_3", return_type: "retur", status: "credit_settled", exchange_pending: false,
    replacement_order_id: "so_9", roll_outcomes: { r1: { outcome: "exchange" } } }} />);
  expect(q("replacement-summary").textContent).toMatch(/KSC\/SO-00090/);
  expect(q("replacement-create")).toBeNull();
});

test("jalur lama (tipe penggantian, per barang) tidak berubah: belum selesai → petunjuk, tanpa tombol", async () => {
  await mount(<ReturnReplacementPanel ret={{ id: "sret_4", return_type: "penggantian", status: "inspected" }} />);
  expect(q("replacement-hint").textContent).toMatch(/Store Credit/);
  expect(q("replacement-create")).toBeNull();
});
