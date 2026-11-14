// PK-41 (RP-03, RP-06, RP-07, RP-08, RP-09, RP-12) — layar laporan pendukung membaca angka baru server.
// Uji komponen (bagian layar spesifikasi `docs/blueprint/unit/PK-41.md`; U17 = uji jalan di lingkungan A):
//   Piutang: judul kolom dari `bucket_labels` (kolom pertama "Belum jatuh tempo"), baris pencocokan di bawah total;
//            rincian pelanggan → baris per surat jalan + "Belum dikirim", status umur ikon + teks;
//   Arus Kas: baris "Saldo awal rekening yang didaftarkan periode ini" di bawah Kas Awal + keterangan metode;
//   Profitabilitas: sub-teks "sesudah nota kredit", panel "Pencocokan ke Laba-Rugi" (lima baris), kalimat kaki baru;
//   Control Tower: sub-teks piutang "tercatat · belum dikirim", modal kerja dari `working_capital_basis`;
//   Hutang Pemasok: kelompok pertama "Belum jatuh tempo", kartu pencocokan ke saldo akun hutang;
//   Kartu angka: rupiah di sub-teks tidak dipatah (`kpiSubParts`).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";
import ARAgingView from "../finance/ARAgingView";
import ARAgingDetail from "../finance/ARAgingDetail";
import CashFlowTab from "../finance/CashFlowTab";
import ProfitabilityView from "../finance/ProfitabilityView";
import FinanceTowerView from "../finance/FinanceTowerView";
import VendorBillsView from "../purchasing/VendorBillsView";
import { setAccessContext } from "../../config/roles";

beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../costing/CostingView", () => () => <div data-testid="stub-costing" />);
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "kn_tanya_pending" }));
jest.mock("../finance/payments/PenaltyPanel", () => () => null);
jest.mock("../../components/StoreCreditBadge", () => () => null);
jest.mock("../purchasing/VendorBillCreateModal", () => () => null);
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
const txt = (id) => norm(q(id)?.textContent);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity="ent_ksc" entities={ENTS}>
        <AppNavProvider role="admin" onNavigateTo={() => {}} onOpenDocument={() => {}}>{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const path = String(url).split("?")[0];
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => path.endsWith(k));
    const v = hit ? map[hit] : [];
    return typeof v === "function" ? v() : Promise.resolve({ data: v });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset();
  document.body.innerHTML = "";
});

// ── Piutang ──────────────────────────────────────────────────────────────────────────────────────────────────────
const LABELS = [
  { key: "current", label: "Belum jatuh tempo" }, { key: "b1_30", label: "1–15 hari" },
  { key: "b31_60", label: "16–45 hari" }, { key: "b61_90", label: "46–90 hari" }, { key: "b90_plus", label: "> 90 hari" }];
const AGING = {
  entity_name: "Sukacita", is_consolidated: false, config: { denda_rate_pct_per_month: 0 }, penalty_policy: {},
  bucket_labels: LABELS,
  totals: { current: 60000, b1_30: 0, b31_60: 40000, b61_90: 0, b90_plus: 0, total: 100000, overdue: 40000,
    ar_ledger: 40000, exposure: 60000, customers: 1, orders: 1 },
  customers: [{ customer_id: "cus1", customer_name: "Toko Satu", current: 60000, b31_60: 40000, outstanding: 100000,
    overdue: 40000, oldest_days: 45, credit_status: "warning" }],
  reconciliation: { ar_ledger_total: 40000, gl_balance: 40000, difference: 0,
    note: "Piutang tercatat sama dengan saldo akun piutang per 15 November 2026." },
};

describe("Piutang — judul kolom dari pengaturan, pencocokan ke saldo akun", () => {
  test("judul kolom = bucket_labels; kolom pertama 'Belum jatuh tempo'; baris pencocokan di bawah total", async () => {
    routeGet({ "/ar/aging": AGING });
    await mount(<ARAgingView selectedEntity="ent_ksc" currentUser={{ permissions: {} }} />);
    expect(["current", "b1_30", "b31_60", "b61_90", "b90_plus"].map((k) => txt(`ar-aging-col-${k}`))).toEqual(
      ["Belum jatuh tempo", "1–15 hari", "16–45 hari", "46–90 hari", "> 90 hari"]);
    expect(q("ar-aging-table").className).toContain("head-wrap");
    expect(txt("ar-aging-reconciliation")).toContain(
      "Piutang tercatat Rp 40.000 · Saldo akun piutang Rp 40.000 · Selisih Rp 0");
    expect(txt("ar-rec-note")).toBe("Piutang tercatat sama dengan saldo akun piutang per 15 November 2026.");
    expect(q("ar-rec-ledger").className).toContain("whitespace-nowrap");
    expect(document.body.textContent).not.toContain("Lancar (Belum JT)");
  });

  test("batas dua kolom: kolom yang tidak dipakai server tidak tampil", async () => {
    routeGet({ "/ar/aging": { ...AGING, bucket_labels: LABELS.filter((b) => b.key !== "b61_90") } });
    await mount(<ARAgingView selectedEntity="ent_ksc" currentUser={{ permissions: {} }} />);
    expect(q("ar-aging-col-b61_90")).toBeNull();
    expect(q("ar-aging-col-b90_plus")).not.toBeNull();
  });

  test("rincian pelanggan: pesanan dibuka → baris per surat jalan + Belum dikirim; status umur ikon + teks", async () => {
    const detail = {
      customer_name: "Toko Satu", totals: { total: 100000, ar_ledger: 40000, exposure: 60000 },
      items: [{ order_id: "so1", order_number: "SO-1", due_date: "2026-10-01", days_late: 45, overdue: true,
        grand_total: 100000, paid_total: 0, outstanding: 100000, ar_ledger: 40000, exposure: 60000, denda_estimate: 0,
        penalties: [],
        lines: [
          { sumber: "surat_jalan", ref_id: "sj1", ref_number: "SJ-001", tanggal: "2026-09-01", jatuh_tempo: "2026-10-01",
            nilai: 40000, terbayar: 0, sisa: 40000, hari_lewat: 45, jurnal_id: "je1" },
          { sumber: "belum_dikirim", ref_id: "so1", ref_number: "SO-1", tanggal: null, jatuh_tempo: null,
            nilai: 60000, terbayar: 0, sisa: 60000, hari_lewat: 0, uang_muka: 0 }] }],
      penalties: [],
    };
    await mount(<ARAgingDetail detail={detail} customerId="cus1" loading={false} currentUser={{ permissions: {} }}
      onAccrue={() => {}} onRefresh={() => {}} onClose={() => {}} />);
    const pill = q("ar-detail-age-so1");
    expect(pill.className).toContain("status-pill");
    expect(pill.querySelector("svg")).not.toBeNull();
    expect(norm(pill.textContent)).toBe("Telat 45 hari");
    expect(q("ar-detail-lines-so1")).toBeNull();
    await click(q("ar-detail-toggle-so1"));
    expect(q("ar-detail-toggle-so1").getAttribute("aria-expanded")).toBe("true");
    const head = [...q("ar-detail-lines-table-so1").querySelectorAll("th")].map((th) => norm(th.textContent));
    expect(head).toEqual(["Surat Jalan", "Tanggal", "Jatuh Tempo", "Nilai", "Terbayar", "Sisa", "Hari Lewat"]);
    const sj = [...q("ar-line-so1-surat_jalan").querySelectorAll("td")].map((td) => norm(td.textContent));
    expect(sj[0]).toBe("SJ-001");
    expect(sj.slice(3)).toEqual(["Rp 40.000", "Rp 0", "Rp 40.000", "45 hari"]);
    const bd = [...q("ar-line-so1-belum_dikirim").querySelectorAll("td")].map((td) => norm(td.textContent));
    expect([bd[0], bd[1], bd[2], bd[5], bd[6]]).toEqual(["Belum dikirim", "—", "—", "Rp 60.000", "—"]);
  });
});

// ── Arus Kas ─────────────────────────────────────────────────────────────────────────────────────────────────────
describe("Arus Kas — saldo awal rekening bukan arus pendanaan", () => {
  test("baris saldo awal rekening di bawah Kas Awal + keterangan metode langsung", async () => {
    routeGet({ "/finance/cash-flow": {
      operating: { label: "Arus Kas dari Aktivitas Operasi", net_income: 250, working_capital: [], total: 250 },
      investing: { label: "Arus Kas dari Aktivitas Investasi", lines: [], total: 130 },
      financing: { label: "Arus Kas dari Aktivitas Pendanaan", lines: [], total: 500 },
      net_change: 880, begin_cash: 900, opening_balance_additions: 200, begin_cash_adjusted: 1100, end_cash: 1980,
      opening_balance_label: "Saldo awal rekening yang didaftarkan periode ini", reconciled: true,
      method_label: "Metode langsung: tiap jurnal kas digolongkan menurut jenis transaksinya." } });
    await mount(<CashFlowTab selectedEntity="ent_ksc" />);
    const sel = (tr) => [...tr.querySelectorAll("td")].map((td) => norm(td.textContent));
    const row = q("cf-opening-row");
    expect(sel(row)).toEqual(["Saldo awal rekening yang didaftarkan periode ini", "Rp 200"]);
    expect(sel(row.previousElementSibling)).toEqual(["Kas Awal Periode", "Rp 900"]);
    expect(txt("cf-method")).toContain("Metode langsung: tiap jurnal kas digolongkan menurut jenis transaksinya.");
    expect(txt("cf-kpi-begin-sub")).toBe("ditambah saldo awal rekening baru Rp 200");
    expect(document.body.textContent).not.toContain("tak langsung");
  });
});

// ── Profitabilitas ───────────────────────────────────────────────────────────────────────────────────────────────
describe("Profitabilitas — nota kredit dan pencocokan ke Laba-Rugi", () => {
  const REC = [
    { key: "margin", label: "Marjin kotor layar ini", amount: 32000 },
    { key: "inventory_adjustments", label: "Penghapusan dan penyesuaian persediaan (akun beban pokok selain HPP)", amount: -12000 },
    { key: "interco", label: "Penjualan antar-PT (tidak termasuk di layar ini)", amount: 0 },
    { key: "unexplained", label: "Selisih belum dijelaskan", amount: 0 },
    { key: "gross_profit_pl", label: "Laba kotor menurut Laba-Rugi", amount: 20000 }];
  const PROF = { totals: { revenue: 80000, credit_notes: 20000, cogs: 48000, margin: 32000, margin_pct: 40, orders: 1 },
    by_product: [], monthly: [], estimate: { totals: { revenue: 0 } }, reconciliation: REC };

  test("sub-teks 'sesudah nota kredit', lima baris pencocokan, kalimat kaki baru", async () => {
    routeGet({ "/finance/profitability": PROF });
    await mount(<ProfitabilityView selectedEntity="ent_ksc" />);
    expect(txt("prof-kpi-revenue-sub")).toContain("sesudah nota kredit Rp 20.000");
    const rows = [...q("prof-reconciliation-table").querySelectorAll("tr")]
      .map((tr) => [...tr.querySelectorAll("td")].map((td) => norm(td.textContent)).join(" | "));
    expect(rows).toEqual([
      "Marjin kotor layar ini | Rp 32.000",
      "Penghapusan dan penyesuaian persediaan (akun beban pokok selain HPP) | -Rp 12.000",
      "Penjualan antar-PT (tidak termasuk di layar ini) | Rp 0",
      "Selisih belum dijelaskan | Rp 0",
      "Laba kotor menurut Laba-Rugi | Rp 20.000"]);
    expect(txt("prof-footnote")).toContain("Marjin = pendapatan barang terkirim (tanpa PPN, dikurangi nota kredit) − "
      + "biaya roll saat dikirim (dikurangi barang retur yang kembali ke stok). Pesanan lama tanpa surat jalan memakai "
      + "harga pokok rata-rata.");
    expect(document.body.textContent).not.toContain("WAC × qty");
  });

  test("tanpa izin HPP (server tidak mengirim pencocokan) → panel tidak tampil", async () => {
    routeGet({ "/finance/profitability": { ...PROF, reconciliation: undefined } });
    await mount(<ProfitabilityView selectedEntity="ent_ksc" />);
    expect(q("prof-reconciliation")).toBeNull();
  });
});

// ── Control Tower ────────────────────────────────────────────────────────────────────────────────────────────────
describe("Control Tower — piutang tercatat & modal kerja", () => {
  test("sub-teks kartu Piutang dan Modal Kerja", async () => {
    routeGet({ "/finance/tower": {
      period: { month: "2026-11", year: 2026 }, cash: { total: 500000, accounts: [] },
      ar: { outstanding: 140000, ar_ledger: 40000, exposure: 100000, overdue: 0, aging: {}, top: [], bucket_labels: LABELS },
      ap: { outstanding: 100000, aging: {}, top: [] }, working_capital: 440000,
      working_capital_basis: "Kas + piutang tercatat − hutang", pl: { mtd: {}, ytd: {} }, monthly: [], ratios: {} } });
    await mount(<FinanceTowerView selectedEntity="ent_ksc" />);
    expect(txt("tower-kpi-ar-sub")).toBe("tercatat Rp 40.000 · belum dikirim Rp 100.000");
    expect(txt("tower-kpi-wc-sub")).toBe("Kas + piutang tercatat − hutang");
    // rupiah di sub-teks utuh satu baris
    const spans = [...q("tower-kpi-ar-sub").querySelectorAll("span.whitespace-nowrap")].map((s) => norm(s.textContent));
    expect(spans).toEqual(["Rp 40.000", "Rp 100.000"]);
  });
});

// ── Hutang Pemasok ───────────────────────────────────────────────────────────────────────────────────────────────
describe("Hutang Pemasok — belum jatuh tempo dan pencocokan ke saldo akun hutang", () => {
  test("kelompok pertama 'Belum jatuh tempo'; kartu pencocokan", async () => {
    routeGet({
      "/vendor-bills": { items: [], total: 0, has_more: false }, "/vendor-bills/status-counts": {},
      "/purchase-orders": [],
      "/vendor-bills/payables/summary": {
        total_outstanding: 100000, aging: { not_due: 100000, "1-30": 0, "31-60": 0, "61-90": 0, ">90": 0 },
        aging_labels: [{ key: "not_due", label: "Belum jatuh tempo" }, { key: "1-30", label: "1–30 hari" },
          { key: "31-60", label: "31–60 hari" }, { key: "61-90", label: "61–90 hari" }, { key: ">90", label: "> 90 hari" }],
        by_supplier: [], bills: [],
        reconciliation: { bills_outstanding: 100000, landed_cost_outstanding: 10000, debit_notes_open: 20000,
          expected_gl: 90000, gl_balance: 90000, unexplained: 0 } } });
    await mount(<VendorBillsView currentUser={{ permissions: {} }} selectedEntity="ent_ksc" />);
    expect(txt("vb-summary-not-due")).toContain("Belum jatuh tempo");
    expect(txt("vb-summary-not-due")).toContain("Rp 100.000");
    expect(txt("vb-summary-1-30")).toContain("Lewat 1–30 hari");
    expect(norm(q("vb-ap-reconciliation").querySelector("p").textContent)).toBe(
      "Tagihan belum lunas Rp 100.000 + Biaya masuk belum dibayar Rp 10.000 − Nota debit belum dipotong Rp 20.000 "
      + "= Rp 90.000 · Saldo akun hutang Rp 90.000");
    expect(txt("vb-rec-unexplained")).toBe("Cocok dengan saldo akun hutang.");
    expect(document.body.textContent).not.toContain("Umur 0–30 hari");
  });
});
