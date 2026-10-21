// F-11-layar (uji pra-UAT 2026-10-21) — Gudang & QC membuka retur pelanggan dari layar tanpa uang.
// Keputusan pemilik (opsi b): tab Retur Pelanggan untuk warehouse/qc; detail tanpa harga/nilai & panel uang;
// tombol mengikuti izin endpoint (scan = wms.scan, QC = qc.inspect). Pemegang sales_return.view tidak berubah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { hubTabsForRole, buildNavGroups } from "../../config/navigationConfig";
import SalesReturns from "../sales/SalesReturns";
import ReturnDetail from "../sales/ReturnDetail";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
const axios = require("../../services/apiClient").default;
// Panel dirender sebagai penanda supaya terlihat panel mana yang muncul (isi panel bukan objek uji ini).
jest.mock("../sales/ReturnStepper", () => () => null);
jest.mock("../sales/ReturnQuarantinePanel", () => () => <div data-testid="m-quarantine" />);
jest.mock("../sales/ReturnChainPanel", () => () => <div data-testid="m-chain" />);
jest.mock("../sales/ReturnGradeLossPanel", () => () => <div data-testid="m-gradeloss" />);
jest.mock("../sales/ReturnDispositionPanel", () => () => <div data-testid="m-disposition" />);
jest.mock("../sales/ReturnEligibilityPanel", () => () => <div data-testid="m-eligibility" />);
jest.mock("../sales/ReturnExceptionsPanel", () => () => <div data-testid="m-exceptions" />);
jest.mock("../sales/ReturnCompensationPanel", () => () => <div data-testid="m-compensation" />);
jest.mock("../sales/ReturnReplacementPanel", () => () => <div data-testid="m-replacement" />);
jest.mock("../sales/ReturnLogisticsPanel", () => () => <div data-testid="m-logistics" />);
jest.mock("../sales/ReturnJourneyPanel", () => (p) => <div data-testid="m-journey" data-canedit={String(!!p.canEdit)} />);
jest.mock("../sales/ReturnTimelinePanel", () => (p) => <div data-testid="m-timeline" data-canedit={String(!!p.canEdit)} />);
jest.mock("../../components/ReturnTimeline", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => <div data-testid="m-docbar" />);
jest.mock("../../components/AskKnButton", () => ({ AskKnButton: () => <div data-testid="m-askkn" /> }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const RET = { id: "sret_1", number: "SRET-1", status: "approved", return_type: "retur", order_number: "SO-1",
  customer_name: "Toko A", created_at: "2026-10-20T00:00:00", attachments: [{ id: "a1", filename: "noda.jpg", size: 2048, content_type: "image/jpeg" },
                { id: "a2", filename: "surat.pdf", size: 4096, content_type: "application/pdf" }],
  items: [{ product_id: "p1", product_name: "Kain A", quantity_returned: 5, unit: "yard", roll_ids: ["r1"], roll_qtys: { r1: 5 },
            unit_price_est: 44000, line_total_est: 220000 }], estimated_value: 220000 };
const GRADE = { field_visibility: ["grade", "lot", "origin"] };
const warehouse = { id: "u1", role: "warehouse", permissions: { ...GRADE, wms: ["view", "scan"], qc: ["view", "inspect"], order: ["view"] } };
const qc = { id: "u2", role: "qc", permissions: { ...GRADE, qc: ["view", "inspect"] } };
const sales = { id: "u3", role: "sales", permissions: { sales_return: ["view", "create", "update"], order: ["view"] } };

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
const heads = (host) => [...host.querySelectorAll("th")].map((t) => t.textContent.trim());

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockImplementation((url) => {
    if (url === "/api/sales-returns/sret_1") return Promise.resolve({ data: RET });
    if (url === "/api/sales-returns") return Promise.resolve({ data: { items: [RET], total: 1 } });
    return Promise.resolve({ data: url.endsWith("status-counts") ? { approved: 1, all: 1 } : [] });
  });
});

test("tab Retur Pelanggan & menu Retur terlihat untuk Gudang dan QC; Desainer tidak", () => {
  for (const role of ["warehouse", "qc"]) {
    expect(hubTabsForRole("returns-hub", role).map((t) => t.view)).toContain("returns");
    expect(buildNavGroups(role, { showComingSoon: false }).some((g) => g.id === "returns-hub")).toBe(true);
  }
  expect(hubTabsForRole("returns-hub", "designer").map((t) => t.view)).not.toContain("returns");
});

test.each([["warehouse", warehouse, true], ["qc", qc, false]])(
  "detail %s: tanpa harga/nilai & panel uang; scan mengikuti wms.scan, QC mengikuti qc.inspect",
  async (_name, user, canScan) => {
    const { host, root } = await mount(<ReturnDetail ret={RET} token="t" currentUser={user} canApprove={false} onBack={() => {}} />);
    expect(heads(host)).not.toContain("Harga");
    expect(heads(host)).not.toContain("Nilai");
    expect(q(host, "return-estimated-value")).toBeNull();
    for (const id of ["m-askkn", "m-docbar", "m-eligibility", "m-exceptions", "m-compensation", "m-replacement",
                      "m-logistics", "m-quarantine", "m-chain", "m-gradeloss", "m-disposition"]) {
      expect(q(host, id)).toBeNull();
    }
    expect(q(host, "m-journey").dataset.canedit).toBe("false");            // keluhan/tonggak = sales_return.update
    expect(q(host, "m-timeline").dataset.canedit).toBe(String(canScan));     // form scan = wms.scan
    expect(q(host, "start-inspect-btn")).not.toBeNull();                    // QC = qc.inspect
    expect(q(host, "upload-attachment-btn")).toBeNull();                    // unggah = sales_return.update
    // Keputusan owner 2026-10-21 — foto/video bukti keluhan boleh diunduh Gudang/QC; lampiran lain tidak.
    expect(q(host, "attachment-a1").querySelector("a").getAttribute("href")).toBe("/api/sales-returns/sret_1/attachments/a1/download");
    expect(q(host, "attachment-a2").querySelector("a")).toBeNull();
    expect(axios.get).not.toHaveBeenCalledWith("/api/credit-notes", expect.anything());
    await act(async () => { root.unmount(); });
  });

test("detail Sales (sales_return.view): harga, nilai & panel tetap seperti sebelumnya", async () => {
  const { host, root } = await mount(<ReturnDetail ret={RET} token="t" currentUser={sales} canApprove={false} onBack={() => {}} />);
  expect(heads(host)).toEqual(expect.arrayContaining(["Harga", "Nilai"]));
  expect(q(host, "return-estimated-value")).not.toBeNull();
  for (const id of ["m-askkn", "m-docbar", "m-compensation", "m-quarantine", "m-chain", "m-disposition"]) {
    expect(q(host, id)).not.toBeNull();
  }
  expect(q(host, "m-timeline").dataset.canedit).toBe("true");
  expect(q(host, "m-journey").dataset.canedit).toBe("true");
  expect(q(host, "upload-attachment-btn")).not.toBeNull();
  expect(q(host, "attachment-a1").querySelector("a")).not.toBeNull();   // Sales: semua lampiran tetap bisa diunduh
  expect(q(host, "attachment-a2").querySelector("a")).not.toBeNull();
  await act(async () => { root.unmount(); });
});

test("daftar Gudang: tanpa kolom Nilai/Nota Kredit & tanpa Buat Retur; Sales tetap lengkap", async () => {
  let m = await mount(<SalesReturns currentUser={warehouse} />);
  expect(q(m.host, "returns-table")).not.toBeNull();
  expect(heads(m.host)).not.toContain("Nilai (CN)");
  expect(heads(m.host)).not.toContain("Nota Kredit");
  expect(q(m.host, "create-return-btn")).toBeNull();
  expect(q(m.host, "return-stat-pending")).toBeNull();
  await act(async () => { m.root.unmount(); });
  m = await mount(<SalesReturns currentUser={sales} />);
  expect(heads(m.host)).toEqual(expect.arrayContaining(["Nilai (CN)", "Nota Kredit"]));
  expect(q(m.host, "create-return-btn")).not.toBeNull();
  await act(async () => { m.root.unmount(); });
});
