// Fase 3 · P4 — Keuangan, hutang & pajak: D-10 (ringkasan laba-rugi), D-11 (satu layar margin), D-12 B (kelompok
// umur sama), D-13 B (kartu kas kecil per PT), D-14 (PT dari header), D-20 (satu rekap PPN), L-03/L-08 (FormModal,
// KPI nol netral) dan kepala panel rincian piutang di HP.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import { AGING_BUCKETS, bucketForDays, sumByBucket } from "../finance/agingBuckets";
import { KpiCard } from "../finance/financeShared";
import ClosingView from "../finance/ClosingView";
import PeriodUnlockView from "../finance/PeriodUnlockView";
import FinanceTowerView from "../finance/FinanceTowerView";
import BiFinanceView from "../finance/BiFinanceView";
import ProfitabilityView from "../finance/ProfitabilityView";
import FinancialStatementsView from "../finance/FinancialStatementsView";
import AdvanceReportView from "../finance/AdvanceReportView";
import ARAgingDetail from "../finance/ARAgingDetail";
import TaxCenterView from "../finance/TaxCenterView";
import InputTaxView from "../purchasing/InputTaxView";
import CashManagementView from "../purchasing/CashManagementView";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => true), askReason: jest.fn(async () => "alasan uji"),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
// recharts butuh ukuran DOM nyata — di jsdom cukup diganti kotak kosong.
jest.mock("recharts", () => {
  const Box = ({ children }) => <div>{typeof children === "function" ? null : null}</div>;
  return new Proxy({}, { get: () => Box });
});
jest.mock("../../components/StoreCreditBadge", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
let mounted = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return host;
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    if (!hit) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: map[hit] });
  });
}
afterEach(async () => {
  for (const r of mounted) await act(async () => { r.unmount(); });
  mounted = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }, { id: "ent_cs", short_name: "Cipta" }];
const MGR = { role: "manager", permissions: { accounting: ["view", "manage"], period: ["unlock"] } };

describe("D-12 B — agingBuckets (satu definisi Piutang & Uang Muka)", () => {
  test("label & batas sama dengan Piutang: Lancar / 1-30 / 31-60 / 61-90 / 90+", () => {
    expect(AGING_BUCKETS.map((b) => b.label)).toEqual(["Lancar", "1-30 hr", "31-60 hr", "61-90 hr", "90+ hr"]);
    expect([0, 1, 30, 31, 60, 61, 90, 91, -3].map(bucketForDays))
      .toEqual(["current", "b1_30", "b1_30", "b31_60", "b31_60", "b61_90", "b61_90", "b90_plus", "current"]);
    expect(sumByBucket([{ d: 0, v: 5 }, { d: 12, v: 10 }, { d: 95, v: 7.5 }], (x) => x.d, (x) => x.v))
      .toEqual({ current: 5, b1_30: 10, b31_60: 0, b61_90: 0, b90_plus: 7.5 });
  });

  test("Uang Muka Pelanggan memakai 5 kelompok yang sama (dihitung dari umur pesanan)", async () => {
    routeGet({ "/ar/advance-report": { totals: { liability: 15, advance_orders: 15 }, rows: [
      { customer_id: "c1", customer_name: "Butik", advance_orders: 15, deposit_balance: 0, total: 15, oldest_days: 40,
        orders: [{ order_id: "o1", order_number: "SO-1", age_days: 0, advance_unrecognized: 5, receipts: [] },
          { order_id: "o2", order_number: "SO-2", age_days: 40, advance_unrecognized: 10, receipts: [] }] }] } });
    const host = await mount(<AdvanceReportView selectedEntity="ent_ksc" />);
    expect(q(host, "advance-bucket-current").textContent).toContain("Lancar");
    expect(q(host, "advance-bucket-current").textContent).toContain("5");
    expect(q(host, "advance-bucket-b31_60").textContent).toContain("10");
    expect(q(host, "advance-bucket-0_30")).toBeNull();          // kelompok lama "≤ 30 hari" hilang
  });
});

describe("D-14 — Tutup Buku & Buka Periode memakai PT dari header", () => {
  test("Tutup Buku: tanpa pemilih PT lokal / KPI 'Entitas Aktif'; header satu PT → data PT itu", async () => {
    routeGet({ "/finance/closing": [] });
    const host = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={MGR} />);
    expect(q(host, "closing-entity-select")).toBeNull();
    expect(q(host, "closing-kpi-entity")).toBeNull();
    expect(q(host, "closing-entity-label").textContent).toContain("Sukacita");
    expect(mockGet).toHaveBeenCalledWith("/api/finance/closing", { params: { entity_id: "ent_ksc" } });
  });

  test("Tutup Buku: header 'Semua' → kartu pilih badan usaha (EntityRequiredNotice), tanpa memuat data", async () => {
    routeGet({ "/finance/closing": [] });
    const host = await mount(<ClosingView selectedEntity="all" entities={ENTS} currentUser={MGR} />);
    expect(q(host, "closing-entity-required").textContent).toContain("Pilih badan usaha untuk tutup buku");
    expect(q(host, "closing-close-btn")).toBeNull();
    expect(mockGet).not.toHaveBeenCalled();
  });

  test("Buka Periode: pemilih lokal dihapus; header 'Semua' → EntityRequiredNotice", async () => {
    routeGet({ "/finance/closing": [], "/finance/period-unlocks": [] });
    let host = await mount(<PeriodUnlockView selectedEntity="ent_cs" entities={ENTS} currentUser={MGR} />);
    expect(q(host, "plu-entity-select")).toBeNull();
    expect(q(host, "plu-entity-label").textContent).toContain("Cipta");
    host = await mount(<PeriodUnlockView selectedEntity="all" entities={ENTS} currentUser={MGR} />);
    expect(q(host, "plu-entity-required")).not.toBeNull();
  });
});

describe("D-10 — ringkasan laba-rugi tidak berulang", () => {
  const TOWER = {
    period: { month: "2026-10", year: 2026 },
    cash: { total: 913600000, accounts: [{ code: "1-1100", name: "Kas", balance: 913600000 }] },
    ar: { outstanding: 1000, overdue: 0, aging: {}, top: [] }, ap: { outstanding: 0, aging: {}, top: [] },
    working_capital: 1000, pl: { ytd: { revenue: 500000000, net_income: 50000000, net_margin: 10 }, mtd: { revenue: 0, net_income: 0 } },
    monthly: [], ratios: { gross_margin: 30, net_margin: 10 },
  };

  test("Dasbor Keuangan: satu kartu Laba-Rugi YTD + tautan; Marjin Bersih & Posisi Kas masing-masing sekali", async () => {
    routeGet({ "/finance/tower": TOWER });
    const host = await mount(
      <AppNavProvider role="manager"><FinanceTowerView selectedEntity="ent_ksc" /></AppNavProvider>);
    expect(q(host, "tower-pl-ytd")).not.toBeNull();
    expect(q(host, "tower-pl-link")).not.toBeNull();
    expect(q(host, "tower-kpi-margin-ytd")).toBeNull();
    expect(host.textContent.match(/Marjin Bersih/g)).toHaveLength(1);
    expect(q(host, "tower-cash-total")).toBeNull();
    expect(host.textContent.match(/913\.600\.000/g)).toHaveLength(2);   // kartu KPI + baris akun (rincian), bukan total kedua
    expect(q(host, "tower-kpi-rev-mtd-value").className).toContain("text-[#8E8E93]");   // Rp 0 netral (L-08)
  });

  test("BI Keuangan: kartu KPI atas dihapus, rasio Marjin Bersih tetap sekali + tautan", async () => {
    routeGet({ "/finance/bi": { kpi: { revenue: 1, net_margin: 5 }, ratios: { net_margin: 5 }, monthly: [], entity_comparison: [] } });
    const host = await mount(<BiFinanceView selectedEntity="ent_ksc" />);
    expect(q(host, "bi-kpi-revenue")).toBeNull();
    expect(q(host, "bi-kpi-margin")).toBeNull();
    expect(q(host, "bi-ratio-net")).not.toBeNull();
    expect(host.textContent.match(/Marjin Bersih/g)).toHaveLength(1);
    expect(q(host, "bi-pl-link-readonly")).not.toBeNull();    // di luar provider → kalimat sumber, bukan tombol mati
  });

  test("Laporan Keuangan menerima preset tab (tautan dari layar ringkasan)", async () => {
    routeGet({});
    const host = await mount(
      <ViewPresetProvider preset={{ view: "financial-statements", nonce: 1, tab: "bs" }}>
        <FinancialStatementsView selectedEntity="ent_ksc" />
      </ViewPresetProvider>);
    expect(q(host, "fs-tab-bs").getAttribute("aria-selected")).toBe("true");
  });
});

describe("D-11 — Profitabilitas & Margin satu layar", () => {
  test("tab Realisasi | Margin katalog; preset {tab:'katalog'} membuka CostingView tanpa tautan lama", async () => {
    routeGet({ "/costing/wac": [], "/finance/profitability": { totals: {} } });
    const host = await mount(
      <ViewPresetProvider preset={{ view: "profitability", nonce: 1, tab: "katalog" }}>
        <ProfitabilityView selectedEntity="ent_ksc" />
      </ViewPresetProvider>);
    expect(q(host, "prof-tabs-katalog").getAttribute("aria-selected")).toBe("true");
    expect(q(host, "costing-view")).not.toBeNull();
    expect(q(host, "costing-link-profitability")).toBeNull();
    await act(async () => { q(host, "prof-tabs-realisasi").click(); });
    await act(async () => {});
    expect(q(host, "prof-realisasi")).not.toBeNull();
  });

  test("tab katalog digerbang peran yang boleh membuka Margin & HPP", async () => {
    routeGet({ "/finance/profitability": { totals: {} } });
    const host = await mount(<AppNavProvider role="sales"><ProfitabilityView selectedEntity="ent_ksc" /></AppNavProvider>);
    expect(q(host, "prof-tabs-katalog")).toBeNull();
    expect(q(host, "prof-tabs-realisasi")).not.toBeNull();
  });
});

describe("D-20 — rekap PPN hanya di Pajak (PPN & PPh)", () => {
  test("Faktur Masukan: tanpa kartu ringkasan & tab Rekap; satu baris posisi PPN + tautan", async () => {
    routeGet({
      "/input-tax-invoices/eligible-bills": [], "/input-tax-invoices": [],
      "/tax/vat-summary": { period: "2026-10", net_ppn: -2500, position: "lebih_bayar", position_label: "Lebih Bayar" },
    });
    const host = await mount(<InputTaxView currentUser={{ permissions: {} }} selectedEntity="ent_ksc" />);
    expect(q(host, "it-summary")).toBeNull();
    expect(q(host, "it-view-rekap")).toBeNull();
    expect(q(host, "it-ppn-position-text").textContent).toContain("Lebih Bayar");
    expect(q(host, "it-ppn-link-readonly")).not.toBeNull();
  });

  test("Pajak: rincian PPN Masukan per pemasok → tautan ke Faktur Masukan (masa sama)", async () => {
    routeGet({ "/tax/summary": { period: "2026-10", periods: ["2026-10"], config: { is_pkp: true }, entity: {},
      ppn: { keluaran: {}, masukan: { ppn: 100, count: 2 }, masukan_by_supplier: [{ supplier_name: "A", count: 2, dpp: 1, ppn: 100 }] } } });
    const nav = [];
    const host = await mount(
      <AppNavProvider role="manager" onNavigateTo={(v, o) => nav.push([v, o.preset])}>
        <TaxCenterView currentUser={MGR} selectedEntity="ent_ksc" />
      </AppNavProvider>);
    expect(q(host, "tax-masukan-table")).toBeNull();
    expect(q(host, "tax-masukan-link-count").textContent).toBe("1 pemasok");
    await act(async () => { q(host, "tax-masukan-link-open").click(); });
    expect(nav).toEqual([["input-tax", { period: "2026-10" }]]);
  });
});

describe("D-13 B — kartu 'Kas Kecil per Entitas' hanya bila > 1 PT", () => {
  const base = { kas_kecil: { balance: 10 }, kas_besar: { balance: 20 } };
  test.each([
    [{ ent_ksc: { balance: 10 } }, false],
    [{ ent_ksc: { balance: 10 }, ent_cs: { balance: 5 } }, true],
  ])("per entitas %j → tampil %s", async (perEntity, shown) => {
    routeGet({ "/cash-transactions/summary": { ...base, kas_kecil_per_entity: perEntity }, "/entities": ENTS });
    const host = await mount(<CashManagementView currentUser={{ role: "admin", permissions: {} }} selectedEntity="all" />);
    expect(!!q(host, "cash-per-entity-card")).toBe(shown);
    expect(q(host, "cash-source-label")).not.toBeNull();    // label sumber K-02 tetap
  });
});

describe("L-08 & kepala panel piutang", () => {
  test("KpiCard: tanpa garis kiri warna, nilai nol netral", async () => {
    const host = await mount(<div><KpiCard testId="k0" label="Kas" value="Rp 0" tone="text-[#C0392B]" />
      <KpiCard testId="k1" label="Kas" value="Rp 5" tone="text-[#C0392B]" /></div>);
    expect(q(host, "k0-value").className).toContain("text-[#8E8E93]");
    expect(q(host, "k1-value").className).toContain("text-[#C0392B]");
    expect(q(host, "k0").querySelector("span.absolute")).toBeNull();
  });

  test("rincian piutang: judul + × di baris pertama, ringkasan & aksi di baris kedua (membungkus)", async () => {
    const host = await mount(<ARAgingDetail customerId="c1" loading={false} onClose={() => {}} onAccrue={() => {}}
      currentUser={{ permissions: { penalty: ["issue"] } }}
      detail={{ customer_name: "Butik Bali", totals: { total: 100, ar_ledger: 60, exposure: 40 }, items: [] }} />);
    const head = q(host, "ar-aging-detail").querySelector(".section-head");
    expect(head.className).toContain("flex-wrap");
    expect(head.children[1].getAttribute("data-testid")).toBe("ar-aging-detail-close");
    expect(q(host, "ar-aging-detail-summary").textContent).toContain("ledger");
    expect(q(host, "ar-aging-accrue")).not.toBeNull();
  });
});
