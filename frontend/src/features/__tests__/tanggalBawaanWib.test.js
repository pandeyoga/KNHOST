/** @jest-environment <rootDir>/jest/utcDeviceEnvironment.js */
// 15 Nov — tanggal bawaan form/laporan mengikuti WIB, apa pun zona perangkatnya.
//
// Skenario: perangkat berzona UTC (lingkungan uji di atas), jam dibekukan pada 2026-11-14T19:30:00Z
// = Minggu 15 Nov 2026 pukul 02.30 WIB. Menurut jam perangkat masih 14 Nov — dulu Laba-Rugi bawaan berakhir 14 Nov
// (jurnal hari ini tidak tampil) dan kwitansi "Catat Pembayaran" tercatat 14 Nov. Bawaan yang benar: "2026-11-15".
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import { todayWib } from "../../utils/formatters";
import { yearOptions, ytdRangeWib, endOfPrevMonthWib } from "../finance/financeShared";
import { currentPeriod } from "../crm/crmUtils";
import { curMonth, lastMonths } from "../hr/kpiUtils";
import { todayISO } from "../purchasing/contrabon/contraBonApi";
import { monthKey, weekStart } from "../marketing/marketingShared";
import { presetRange } from "../rnd/design/DateQuickNav";
import FinancialStatementsView from "../finance/FinancialStatementsView";
// Integrasi 15 Nov: `crm/ARReceiptModal` dihapus MN-T3 → perbaikan tanggal dipindah ke dua form bayar baru.
import ReceivePaymentModal from "../finance/payments/ReceivePaymentModal";
import PaySupplierModal from "../finance/payments/PaySupplierModal";
import SampleFinishModal from "../rnd/SampleFinishModal";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setActiveEntity: () => {},
}));
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: async () => ({ needs_decision: false, direction: "none" }),
  varianceMeta: async () => ({ reasons: [] }),
  directionMeta: () => ({ label: "", bg: "#fff", fg: "#000" }),
}));
// `KNSelect` memuat `cmdk` (@radix-ui) yang tidak termuat di lingkungan uji lokal → tiruan seperti uji lain (mnt3SatuForm).
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="" />
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });

// ── Jam beku: hanya "sekarang" yang dibekukan (new Date() tanpa argumen & Date.now()); timer tetap asli. ──
const FROZEN_ISO = "2026-11-14T19:30:00Z";
const RealDate = Date;
const FROZEN_MS = RealDate.parse(FROZEN_ISO);
class FrozenDate extends RealDate {
  constructor(...args) {
    if (args.length === 0) super(FROZEN_MS);
    else super(...args);
  }
  static now() { return FROZEN_MS; }
}
beforeAll(() => { global.Date = FrozenDate; });
afterAll(() => { global.Date = RealDate; });

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return host;
}
const click = async (el) => { await act(async () => { el.click(); }); await act(async () => {}); };
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    return Promise.resolve({ data: hit ? map[hit] : null });
  });
}
afterEach(async () => {
  for (const r of roots.splice(0)) await act(async () => { r.unmount(); });
  document.body.innerHTML = "";
  mockGet.mockReset();
  mockPost.mockReset();
});

describe("prasyarat skenario", () => {
  test("perangkat berzona UTC & jam beku: menurut jam perangkat masih 14 Nov, menurut WIB sudah 15 Nov", () => {
    const now = new Date();
    expect(now.toISOString()).toBe("2026-11-14T19:30:00.000Z");
    expect(now.getTimezoneOffset()).toBe(0);                     // zona perangkat = UTC (bukan WIB)
    expect(now.getDate()).toBe(14);                              // tanggal LOKAL perangkat — sumber bug lama
    expect(now.toISOString().slice(0, 10)).toBe("2026-11-14");   // potongan ISO UTC — sumber bug lama
    expect(todayWib()).toBe("2026-11-15");
  });
});

describe("helper tanggal bawaan = WIB", () => {
  test("keuangan: rentang awal tahun s.d. hari ini, akhir bulan lalu, pilihan tahun", () => {
    expect(ytdRangeWib()).toEqual({ start: "2026-01-01", end: "2026-11-15" });
    expect(endOfPrevMonthWib()).toBe("2026-10-31");
    expect(endOfPrevMonthWib("2026-01-15")).toBe("2025-12-31");
    expect(endOfPrevMonthWib("2026-03-31")).toBe("2026-02-28");
    expect(yearOptions().map((o) => o.value)).toEqual(["2026", "2025", "2024", "2023", "2022", "2021"]);
  });

  test("periode bulan berjalan & tanggal hari ini di modul lain", () => {
    expect(currentPeriod()).toBe("2026-11");                     // CRM (target & insentif)
    expect(curMonth()).toBe("2026-11");                          // KPI HR
    expect(lastMonths(3)).toEqual(["2026-11", "2026-10", "2026-09"]);
    expect(lastMonths(3, "2026-03-31")).toEqual(["2026-03", "2026-02", "2026-01"]);   // tgl 31 tidak melompati Februari
    expect(lastMonths(2, "2026-01-10")).toEqual(["2026-01", "2025-12"]);
    expect(todayISO()).toBe("2026-11-15");                       // kontrabon: tanggal bayar/jadwal bawaan
    expect(monthKey()).toBe("2026-11");                          // kalender konten
    expect(weekStart()).toBe("2026-11-09");                      // Senin dari minggu yang memuat Minggu 15 Nov
    expect(presetRange("today")).toEqual({ from: "2026-11-15", to: "2026-11-15" });   // desain: preset "Hari ini"
    expect(presetRange("month")).toEqual({ from: "2026-11-01", to: "2026-11-30" });
  });
});

describe("layar: tanggal bawaan = 2026-11-15", () => {
  test("Laporan Keuangan · Laba-Rugi: rentang bawaan berakhir hari ini WIB (jurnal hari ini ikut)", async () => {
    routeGet({ "/finance/income-statement": null });
    await mount(<FinancialStatementsView selectedEntity="ent_ksc" />);
    const call = mockGet.mock.calls.find(([url]) => url === "/api/finance/income-statement");
    expect(call).toBeTruthy();
    expect(call[1].params).toMatchObject({ start: "2026-01-01", end: "2026-11-15", entity_id: "ent_ksc" });
  });

  test("Laporan Keuangan · Neraca: per tanggal hari ini WIB, pembanding akhir bulan lalu", async () => {
    routeGet({});
    const host = await mount(<FinancialStatementsView selectedEntity="ent_ksc" />);
    await click(q(host, "fs-tab-bs"));
    const call = mockGet.mock.calls.find(([url]) => url === "/api/finance/balance-sheet");
    expect(call).toBeTruthy();
    expect(call[1].params).toMatchObject({ as_of: "2026-11-15", compare_as_of: "2026-10-31" });
  });

  test("Terima pembayaran (kwitansi, form MN-T3): tanggal bawaan = 15 Nov", async () => {
    routeGet({
      "/payment-methods": [], "/ar-receipts/open-orders": [{ order_id: "so1", number: "KSC/SO-0001", outstanding: 50000 }],
      "/ar-receipts/deposit": {}, "/bank-accounts/receiving": [], "/settings/effective": { payment: {} },
      "/cash-holdings/me/summary": {},
    });
    const host = await mount(<ReceivePaymentModal customerId="c1" customerName="Toko A" onClose={() => {}} onDone={() => {}} />);
    expect(q(host, "ar-receipt-date").textContent).toContain("15 Nov 2026");
  });

  test("Bayar pemasok (form MN-T3): tanggal bayar bawaan = 15 Nov", async () => {
    routeGet({ "/vendor-bills/vb1": { id: "vb1", number: "VB-1", entity_id: "ent_ksc", outstanding: 70000, status: "approved" },
      "/bank-accounts": [], "/payment-methods": [], "/settings/effective": { payment: {} } });
    const host = await mount(<PaySupplierModal target={{ type: "vendor_bill", id: "vb1" }} onClose={() => {}} onPaid={() => {}} />);
    expect(q(host, "pay-supplier-date").textContent).toContain("15 Nov 2026");
  });

  test("Terima sampel fisik (R&D): tanggal bawaan = 15 Nov", async () => {
    const onConfirm = jest.fn();
    const host = await mount(<SampleFinishModal mode="finish" sample={{ number: "SMP-1" }} onClose={() => {}} onConfirm={onConfirm} />);
    await click(q(host, "sample-finish-confirm"));
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ date: "2026-11-15" }));
  });
});
