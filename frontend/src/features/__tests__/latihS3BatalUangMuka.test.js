// S3 (pelatihan keuangan 18 Nov) — membatalkan pesanan yang sudah menerima uang muka. Dulu dialog diam saja dan uang
// muka tertinggal di pesanan mati; kini server memindahkannya menjadi titipan pelanggan, dialog memberi tahu sebelum
// dibatalkan, dan pesan sesudahnya menyebut nominal yang dipindah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CancelOrderDialog from "../orders/CancelOrderDialog";

const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
async function settle() { await act(async () => {}); await act(async () => {}); }

function render(order, onDone) {
  document.body.innerHTML = "";
  const host = document.createElement("div");
  document.body.appendChild(host);
  act(() => { createRoot(host).render(<CancelOrderDialog order={order} onClose={() => {}} onDone={onDone} />); });
}

async function isiAlasan(v) {
  const ta = q("cancel-order-reason");
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
  await act(async () => { setter.call(ta, v); ta.dispatchEvent(new Event("input", { bubbles: true })); });
}

beforeEach(() => {
  mockPost.mockImplementation(() => Promise.resolve({ data: { status: "cancelled", advance_to_deposit: 1307580,
    open_fulfillment_refs: [] } }));
});

test("pesanan ber-uang muka: catatan titipan tampil dan pesan sesudah batal menyebut nominal yang dipindah", async () => {
  const onDone = jest.fn();
  render({ id: "so_1", number: "KSC/SO-00072", paid_total: 1307580 }, onDone);
  await settle();
  expect(teks(q("cancel-order-paid-note"))).toMatch(/sudah dibayar Rp\s?1\.307\.580.*titipan pelanggan/);
  await isiAlasan("Pelanggan membatalkan pesanan");
  await act(async () => { q("cancel-order-confirm").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_1/cancel", { reason: "Pelanggan membatalkan pesanan" });
  expect(onDone).toHaveBeenCalledTimes(1);
  expect(onDone.mock.calls[0][0].replace(/\s+/g, " ")).toMatch(
    /KSC\/SO-00072 dibatalkan, stok dilepas\. Uang muka Rp 1\.307\.580 menjadi titipan pelanggan\./);
});

test("pesanan belum dibayar: tanpa catatan titipan dan tanpa kalimat uang muka", async () => {
  mockPost.mockImplementation(() => Promise.resolve({ data: { status: "cancelled", advance_to_deposit: 0 } }));
  const onDone = jest.fn();
  render({ id: "so_2", number: "KSC/SO-00073", paid_total: 0 }, onDone);
  await settle();
  expect(q("cancel-order-paid-note")).toBeNull();
  await isiAlasan("Salah input pesanan");
  await act(async () => { q("cancel-order-confirm").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
  expect(onDone.mock.calls[0][0]).toBe("KSC/SO-00073 dibatalkan, stok dilepas.");
});
