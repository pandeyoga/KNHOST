// Pelatihan Keuangan 18 Nov (F05) — kartu ringkasan Rencana & Denda. Dulu kartu "Rencana aktif" dan "Rencana ada baris
// telat" ikut tersaring kotak cari (mis. nomor nota denda → 0), sedangkan kartu denda dari server tetap seluruh PT.
// Kini semua kartu = seluruh PT; hanya daftar yang mengikuti pencarian.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PaymentPlansView from "../finance/payments/PaymentPlansView";

const mockPlans = jest.fn();
jest.mock("../finance/payments/paymentApi", () => {
  const asli = jest.requireActual("../finance/payments/paymentApi");
  return { ...asli,
    listPlans: (...a) => mockPlans(...a),
    listPenalties: () => Promise.resolve({ items: [], stats: { draft_amount: 0, issued_outstanding: 21545, waived_amount: 0 } }),
    listVariances: () => Promise.resolve({ stats: { pending: 0 } }) };
});
jest.mock("../finance/payments/PenaltyPanel", () => () => null);
jest.mock("../finance/payments/PaymentVarianceQueue", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const RENCANA = [{ id: "pl1", number: "KSC/PLAN-00001", status: "active", overdue_count: 1, lines: [] },
  { id: "pl2", number: "KSC/PLAN-00002", status: "active", overdue_count: 0, lines: [] }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tunggu = async () => { for (let i = 0; i < 6; i += 1) { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); } };   // eslint-disable-line no-await-in-loop

beforeEach(() => {
  jest.useFakeTimers();
  mockPlans.mockImplementation((p) => Promise.resolve({ items: p.q ? [] : RENCANA }));
});
afterEach(() => { jest.useRealTimers(); document.body.innerHTML = ""; mockPlans.mockReset(); });

test("cari nomor nota → daftar tersaring, kartu rencana tetap seluruh PT", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<PaymentPlansView currentUser={{ permissions: {} }} selectedEntity="ent_ksc" />);
  });
  await act(async () => { jest.advanceTimersByTime(350); });
  jest.useRealTimers();
  await tunggu();
  expect(q("pp-kpi-plans").textContent).toContain("2");
  expect(q("pp-kpi-overdue").textContent).toContain("1");

  jest.useFakeTimers();
  const kotak = q("pp-search");
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(kotak, "KSC/PEN-00001"); kotak.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => { jest.advanceTimersByTime(350); });
  jest.useRealTimers();
  await tunggu();
  expect(mockPlans).toHaveBeenCalledWith(expect.objectContaining({ q: "KSC/PEN-00001" }));
  expect(q("pp-kpi-plans").textContent).toContain("2");
  expect(q("pp-kpi-overdue").textContent).toContain("1");
});
