// FE-07 (review 2026-10-20) — error aksi retur tampil di layar aktif; modal hanya ditutup bila berhasil;
// klik ulang selama proses tidak mengirim dua kali.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SalesReturns from "../sales/SalesReturns";
import ReturnSettleModal from "../sales/ReturnSettleModal";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
const axios = require("../../services/apiClient").default;
// Panel informasi di detail tidak relevan untuk alur error aksi — dikosongkan agar tes fokus (mock data mereka berbeda-beda).
jest.mock("../sales/ReturnStepper", () => () => null);
jest.mock("../sales/ReturnSpkPanel", () => () => null);
jest.mock("../sales/ReturnQuarantinePanel", () => () => null);
jest.mock("../sales/ReturnChainPanel", () => () => null);
jest.mock("../sales/ReturnGradeLossPanel", () => () => null);
jest.mock("../sales/ReturnDispositionPanel", () => () => null);
jest.mock("../sales/ReturnJourneyPanel", () => () => null);
jest.mock("../sales/ReturnTimelinePanel", () => () => null);
jest.mock("../sales/ReturnEligibilityPanel", () => () => null);
jest.mock("../sales/ReturnExceptionsPanel", () => () => null);
jest.mock("../sales/ReturnCompensationPanel", () => () => null);
jest.mock("../sales/ReturnReplacementPanel", () => () => null);
jest.mock("../sales/ReturnLogisticsPanel", () => () => null);
jest.mock("../../components/ReturnTimeline", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../../components/AskKnButton", () => ({ AskKnButton: () => null }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});

const RET = { id: "sret_1", number: "SRET-1", status: "pending_approval", return_type: "customer", order_number: "SO-1",
  customer_name: "Toko A", items: [{ product_id: "p1", quantity_returned: 5, unit: "yard" }], created_at: "2026-10-20T00:00:00" };
const manager = { id: "u1", role: "manager", permissions: { sales_return: ["view", "approve", "reject"], field_visibility: [] } };

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

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockImplementation((url) => {
    if (url === "/api/sales-returns/sret_1") return Promise.resolve({ data: RET });
    return Promise.resolve({ data: url.endsWith("/sales-returns") ? { items: [], total: 0 } : [] });
  });
});

test("approve ditolak server (409): pesan tampil di DETAIL yang sedang terbuka", async () => {
  axios.post.mockRejectedValue({ response: { status: 409, data: { detail: "Status retur sudah berubah." } } });
  const { host, root } = await mount(<SalesReturns currentUser={manager} focusDoc={{ focus_type: "sales_return", focus_id: "sret_1" }} onClearFocus={() => {}} />);
  expect(q(host, "return-detail-view")).not.toBeNull();
  await act(async () => { q(host, "approve-return-btn").click(); });
  await flush();
  expect(q(host, "return-detail-view")).not.toBeNull();
  expect(q(host, "return-action-error")?.textContent).toContain("Status retur sudah berubah.");
  await act(async () => { root.unmount(); });
});

test("klik ulang saat approve masih diproses tidak mengirim permintaan kedua", async () => {
  let release;
  axios.post.mockImplementation(() => new Promise((r) => { release = r; }));
  const { host, root } = await mount(<SalesReturns currentUser={manager} focusDoc={{ focus_type: "sales_return", focus_id: "sret_1" }} onClearFocus={() => {}} />);
  const btn = q(host, "approve-return-btn");
  await act(async () => { btn.click(); btn.click(); });
  expect(axios.post).toHaveBeenCalledTimes(1);
  await act(async () => { release({ data: { ...RET, status: "approved" } }); });
  await flush();
  await act(async () => { root.unmount(); });
});

test("modal tolak: gagal → modal & alasan tetap, pesan tampil di modal", async () => {
  axios.post.mockRejectedValue({ response: { status: 403, data: { detail: "Permission ditolak: sales_return.reject" } } });
  const { host, root } = await mount(<SalesReturns currentUser={manager} focusDoc={{ focus_type: "sales_return", focus_id: "sret_1" }} onClearFocus={() => {}} />);
  await act(async () => { q(host, "reject-return-btn").click(); });
  const ta = q(host, "reject-reason-input");
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
  await act(async () => { setter.call(ta, "Barang tidak sesuai"); ta.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => { q(host, "confirm-reject-btn").click(); });
  await flush();
  expect(q(host, "reject-modal")).not.toBeNull();
  expect(q(host, "reject-reason-input").value).toBe("Barang tidak sesuai");
  expect(q(host, "reject-error")?.textContent).toContain("sales_return.reject");
  await act(async () => { root.unmount(); });
});

test("modal penyelesaian: gagal → tetap terbuka dengan pesan; berhasil → ditutup", async () => {
  const ret = { ...RET, status: "inspected" };
  for (const [result, closed] of [["Gagal settle: QC belum lengkap", false], [null, true]]) {
    const onClose = jest.fn();
    const onSettle = jest.fn().mockResolvedValue(result);
    const { host, root } = await mount(<ReturnSettleModal ret={ret} open onClose={onClose} onSettle={onSettle} />);
    await act(async () => { q(host, "confirm-settle-btn").click(); });
    await flush();
    expect(onSettle).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(closed ? 1 : 0);
    if (!closed) expect(q(host, "settle-error")?.textContent).toContain("QC belum lengkap");
    await act(async () => { root.unmount(); });
  }
});
