// A3 retur (pelatihan keuangan 18 Nov) — "Pakai saldo" (saldo kredit hasil Nota Kredit retur) memakai nilai bersen.
// Dulu [Maks] dan [Pakai Saldo] membulatkan ke rupiah utuh: saldo/tagihan Rp 3.386.332,50 menjadi 3.386.333 → server
// menolak ("melebihi"), dan sisa Rp 0,50 tidak pernah bisa dipakai.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { RedeemModal } from "../finance/StoreCreditModals";

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: { applied_amount: 3386332.5, number: "SCR-00001" } }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function settle() { await act(async () => {}); await act(async () => {}); }
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

test("[Maks] & [Pakai Saldo] memakai nilai bersen (tidak dibulatkan ke rupiah utuh)", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: [
    { order_id: "so_b", number: "KSC/SO-00051", outstanding: 3386332.5 }] }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<RedeemModal row={{ customer_id: "c1", customer_name: "Latihan 43", balance: 3469582.5, entity_id: "ent_ksc" }}
      onClose={() => {}} onDone={() => {}} />);
  });
  await settle();
  await click(q("sc-redeem-max"));
  expect(q("sc-redeem-amount").value).toBe("3386332.5");
  await click(q("sc-redeem-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/store-credit/redeem");
  expect(body.amount).toBe(3386332.5);
  expect(body.allocations).toEqual([{ order_id: "so_b", amount: 3386332.5 }]);
});

test("nominal di atas saldo (lebih dari pembulatan sen) tetap ditolak di layar", async () => {
  mockPost.mockClear();
  mockGet.mockImplementation(() => Promise.resolve({ data: [{ order_id: "so_b", number: "KSC/SO-1", outstanding: 9000 }] }));
  document.body.innerHTML = "";
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<RedeemModal row={{ customer_id: "c1", balance: 5000.5 }} onClose={() => {}} onDone={() => {}} />);
  });
  await settle();
  const input = q("sc-redeem-amount");
  await act(async () => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    set.call(input, "5001");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await settle();
  await click(q("sc-redeem-submit"));
  expect(mockPost).not.toHaveBeenCalled();
  expect(q("sc-redeem-error").textContent).toMatch(/Melebihi saldo/);
});
