// Pelatihan 18 Nov (V9 — bukti klaim materi F06): Penagihan & Penerimaan menampilkan ikon "Catat tindak lanjut"
// (janji bayar) dan "Tandai sudah diingatkan" untuk Finance, padahal server menyimpannya dengan izin `order.update`
// (routers/crm.py) → 403 saat disimpan. Kini kedua ikon hanya tampil bagi pemegang izin ubah pesanan; ikon Terima
// pembayaran tetap mengikuti `ar_receipt.create`.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../crm/ARReceiptsHistory", () => () => null);
jest.mock("../finance/payments/ReceivePaymentModal", () => () => null);
jest.mock("../finance/cards/partyCards", () => ({ CustomerCardLink: ({ name }) => <span>{name}</span> }));

// eslint-disable-next-line import/first
import CollectionWorklist from "../crm/CollectionWorklist";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ROW = { order_id: "so_1", order_number: "KSC/SO-00042", customer_id: "cust_1", customer_name: "Latihan 86 · Toko Kain",
  sales_name: "Ayu", outstanding: 1600204, due_date: "2026-10-28", overdue: true, days_late: 20, reminded: false };

let host; let root;
async function render(perms) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(<CollectionWorklist currentUser={{ role: "x", permissions: perms }} selectedEntity="ent_ksc" />); });
  for (let i = 0; i < 6; i += 1) await act(async () => {});
}
const q = (id) => host.querySelector(`[data-testid="${id}"]`);

beforeEach(() => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("collection-reminders") ? [ROW] : [] }));
});
afterEach(async () => {
  await act(async () => { root.unmount(); });
  host.remove();
});

test("Finance (tanpa izin ubah pesanan): tanpa ikon tindak lanjut & tandai diingatkan; ikon terima bayar tetap ada", async () => {
  await render({ ar_receipt: ["view", "create"], order: ["view", "approve_price_edit", "release_unpaid"] });
  expect(q("collection-row-so_1")).not.toBeNull();
  expect(q("collection-pay-so_1")).not.toBeNull();
  expect(q("collection-followup-so_1")).toBeNull();
  expect(q("collection-mark-so_1")).toBeNull();
});

test("Pemegang izin ubah pesanan (Sales/Admin Sales): ikon tindak lanjut & tandai diingatkan tampil", async () => {
  await render({ order: ["view", "update"] });
  expect(q("collection-followup-so_1")).not.toBeNull();
  expect(q("collection-mark-so_1")).not.toBeNull();
  expect(q("collection-pay-so_1")).toBeNull();
});
