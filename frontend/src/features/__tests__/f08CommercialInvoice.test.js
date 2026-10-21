// F-08 (uji pra-UAT 2026-10-21) — Perjalanan SO: blok "Tagihan — Faktur Komersial" dengan aksi PDF sesudah dikirim;
// sebelum dikirim hanya keterangan kapan terbit.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import OrderJourneyPanel from "../orders/OrderJourneyPanel";

jest.mock("../sales_admin/workDeskApi", () => ({ orderJourney: jest.fn() }));
jest.mock("../documents/DocumentActionsBar", () => (p) => <div data-testid="doc-bar">{`${p.docType}:${p.sourceId}:${p.label}`}</div>);
const api = require("../sales_admin/workDeskApi");
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(data) {
  api.orderJourney.mockResolvedValue(data);
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => { root.render(<OrderJourneyPanel orderId="so1" orderNumber="KSC/SO-1" />); });
  await act(async () => {});
  return { host, root };
}
const base = { order_number: "KSC/SO-1", steps: [], progress: {}, grand_total: 1, paid_total: 0, outstanding: 1 };

test("sudah dikirim → aksi PDF Faktur Komersial (jenis invoice) tampil", async () => {
  const { host, root } = await mount({ ...base, commercial_invoice: { available: true, doc_type: "invoice", number: "KSC/SO-1" } });
  expect(host.querySelector('[data-testid="doc-bar"]').textContent).toBe("invoice:so1:Faktur Komersial");
  await act(async () => { root.unmount(); });
});

test("belum dikirim → keterangan, tanpa aksi PDF", async () => {
  const { host, root } = await mount({ ...base, commercial_invoice: { available: false } });
  expect(host.querySelector('[data-testid="doc-bar"]')).toBeNull();
  expect(host.querySelector('[data-testid="journey-commercial-invoice-pending"]').textContent).toMatch(/Surat Jalan pertama/);
  await act(async () => { root.unmount(); });
});
