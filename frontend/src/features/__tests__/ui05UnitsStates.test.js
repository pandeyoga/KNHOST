// UI-05 (review 2026-10-20) — FE-10 satuan antrean QC, FE-11 status muat penerimaan transfer,
// FE-12 status neraca belum diketahui, FE-13 tanda saldo kumulatif di tooltip.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import QCInspection, { quarantineTotals, formatTotals, unitOf } from "../wms/QCInspection";
import TransferReceiptPanel from "../wms/transfer/TransferReceiptPanel";
import { BalancedKpi } from "../finance/FinancialStatementsParts";
import { forecastTooltip } from "../finance/CashFlowForecastView";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../wms/QcPlanPanel", () => () => null);
jest.mock("../wms/RollInspectionModal", () => () => null);
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [], labelOf: (_k, v) => v }));
jest.mock("../wms/transfer/ReceiptRollTable", () => ({ ReceiptRollTable: () => null, ReceiptResults: () => null }));
jest.mock("../wms/transfer/ReceiptExceptions", () => () => null);
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush(); await flush();
  return { host, root };
}
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

// ─── FE-10 ───────────────────────────────────────────────────────────────────
const TASKS = [
  { id: "t1", product_name: "Katun", quarantine_qty: 120, quarantine_unit: "yard", quarantine_by_unit: { yard: 120 } },
  { id: "t2", product_name: "Knit", quarantine_qty: 35.5, quarantine_unit: "kg", quarantine_by_unit: { kg: 35.5 } },
  { id: "t3", product_name: "Campur", quarantine_qty: 15, quarantine_unit: "", quarantine_unit_mixed: true, quarantine_by_unit: { yard: 10, kg: 5 } },
];

test("FE-10: total karantina dipisah per satuan; kg dan yard tidak dijumlahkan; tidak ada label meter", () => {
  expect(quarantineTotals(TASKS)).toEqual({ yard: 130, kg: 40.5 });
  expect(formatTotals({ yard: 130, kg: 40.5 })).not.toMatch(/\bm\b/);
  expect(unitOf({ quarantine_unit: "", unit: "kg" })).toBe("kg");
});

test("FE-10: layar antrean & form keputusan memakai satuan sumber tugas", async () => {
  axios.get.mockImplementation((url) => Promise.resolve({ data: url === "/api/inbound/qc/queue" ? TASKS : [] }));
  const { host, root } = await mount(<QCInspection currentUser={{ role: "qc", permissions: {} }} selectedEntity="ent_ksc" />);
  const total = q(host, "qc-metric-quarantine-value").textContent;
  expect(total).toContain("yard");
  expect(total).toContain("kg");
  expect(total).not.toMatch(/ m$|\bm\b/);
  await act(async () => { q(host, "qc-inspect-btn-1").click(); });   // tugas kg
  expect(q(host, "qc-inspect-modal").textContent).toContain("Diterima (kg)");
  expect(q(host, "qc-unit-note")).not.toBeNull();                      // interval 4-Point tetap yard, dibedakan
  await act(async () => { root.unmount(); });
});

// ─── FE-11 ───────────────────────────────────────────────────────────────────
test("FE-11: GET penerimaan pertama gagal → error + Coba lagi (bukan Memuat selamanya); retry berhasil", async () => {
  axios.get.mockRejectedValueOnce({ response: { status: 403, data: { detail: "Akses gudang tujuan ditolak." } } });
  const { host, root } = await mount(<TransferReceiptPanel transfer={{ id: "tr1", code: "TRF-1", status: "dispatched" }} user={{ role: "warehouse" }} />);
  expect(q(host, "transfer-receipt-loading")).toBeNull();
  expect(q(host, "transfer-receipt-load-failed").textContent).toContain("Akses gudang tujuan ditolak.");
  expect(q(host, "transfer-receipt-load-failed").textContent).toContain("TRF-1");
  axios.get.mockResolvedValueOnce({ data: { counts: { pending: 2 }, rolls: [], dest_bins: [] } });
  const retry = [...host.querySelectorAll("button")].find((b) => /coba lagi/i.test(b.textContent));
  await act(async () => { retry.click(); });
  await flush();
  expect(q(host, "transfer-receipt-panel")).not.toBeNull();
  await act(async () => { root.unmount(); });
});

// ─── FE-12 ───────────────────────────────────────────────────────────────────
test("FE-12: hanya true = Seimbang; false = Tidak Seimbang; belum diketahui/memuat netral", () => {
  const txt = (props) => renderToStaticMarkup(<BalancedKpi {...props} />);
  expect(txt({ balanced: true })).toContain("Seimbang");
  expect(txt({ balanced: true })).not.toContain("Tidak");
  expect(txt({ balanced: false })).toContain("Tidak Seimbang");
  for (const props of [{ balanced: undefined }, { balanced: null }, {}]) {
    const h = txt(props);
    expect(h).not.toContain("Seimbang");
    expect(h).toContain("Belum diketahui");
  }
  expect(txt({ balanced: true, loading: true })).toContain("Memuat");
});

// ─── FE-13 ───────────────────────────────────────────────────────────────────
test("FE-13: saldo kumulatif mempertahankan tanda; arus keluar dibaca sebagai besaran", () => {
  const val = (v, key) => forecastTooltip(v, "seri", { dataKey: key })[0];
  expect(val(-100, "cumulative")).toMatch(/-/);
  expect(val(100, "cumulative")).not.toMatch(/-/);
  expect(val(0, "cumulative")).not.toMatch(/-/);
  expect(val(-50, "outflow")).not.toMatch(/-/);
  expect(val(-100, "cumulative")).not.toEqual(val(100, "cumulative"));
});
