// F-15 (keputusan owner Q-04, 2026-10-21) — sample berbayar: tagihan berubah > toleransi sesudah potong →
// detail menulis "perlu persetujuan ULANG" + riwayat penyesuaian, tombol "Setujui Ulang Pembayaran" untuk Finance/Admin
// Sample; penyesuaian otomatis (≤ toleransi) tercatat tanpa tombol.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SampleOrdersView from "../samples/SampleOrdersView";
import { docLinkTarget } from "../sales_admin/workDeskApi";

jest.mock("../samples/sampleApi", () => ({
  listSampleOrders: jest.fn(), sampleStats: jest.fn().mockResolvedValue({}), cancelSampleOrder: jest.fn(),
  approveSamplePayment: jest.fn(), confirmSampleOrder: jest.fn(),
}));
jest.mock("../samples/CatalogueCreateModal", () => () => null);
jest.mock("../samples/CatalogueComponents", () => () => null);
jest.mock("../samples/CuttingDesk", () => () => null);
jest.mock("../samples/CuttingLocations", () => () => null);
const api = require("../samples/sampleApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const FIN = { role: "finance", permissions: { sample_order: ["view", "approve_payment"] } };
const base = { id: "so1", number: "KSC/SOS-00029", customer_name: "Toko Kain Sejahtera", sample_billing: "paid",
  status: "packing", grand_total: 81585, items: [], fulfillment_method: "kirim" };

async function mount(order) {
  api.listSampleOrders.mockResolvedValue([order]);
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<SampleOrdersView user={FIN} focusDoc={{ focus_type: "sample_order", focus_id: "so1" }} onClearFocus={() => {}} />); });
  await act(async () => {});
  return { host, root };
}

test("di atas toleransi: status persetujuan ulang + riwayat + tombol Setujui Ulang", async () => {
  api.approveSamplePayment.mockResolvedValue({});
  const { host, root } = await mount({ ...base, sample_payment_status: "reapproval_required",
    sample_payment_adjustments: [{ from: 69930, to: 81585, pct: 16.67, tolerance_pct: 5, auto: false }] });
  expect(q(host, "sample-detail-payment").textContent).toMatch(/persetujuan ULANG/);
  expect(q(host, "sample-detail-adjustment-0").textContent).toMatch(/Melewati toleransi → persetujuan ulang.*16.67% · toleransi 5%/);
  await act(async () => { q(host, "sample-detail-reapprove-payment").click(); });
  expect(api.approveSamplePayment).toHaveBeenCalledWith("so1");
  await act(async () => { root.unmount(); });
});

test("dalam toleransi: disesuaikan otomatis tercatat, tanpa tombol persetujuan ulang", async () => {
  const { host, root } = await mount({ ...base, sample_payment_status: "approved", sample_payment_approved_by: "Sri",
    sample_payment_adjustments: [{ from: 69930, to: 72261, pct: 3.33, tolerance_pct: 5, auto: true }] });
  expect(q(host, "sample-detail-adjustment-0").textContent).toMatch(/Disesuaikan otomatis/);
  expect(q(host, "sample-detail-reapprove-payment")).toBeNull();
  await act(async () => { root.unmount(); });
});

test("tautan dokumen pesanan sample (?doc=SOS-) → layar Pesanan Sample terfokus", () => {
  expect(docLinkTarget({ ref_type: "sample_order", ref_id: "so1", number: "KSC/SOS-00030" }))
    .toMatchObject({ view: "sample-orders", nav_id: "sample-orders", focus_type: "sample_order", focus_id: "so1" });
});
