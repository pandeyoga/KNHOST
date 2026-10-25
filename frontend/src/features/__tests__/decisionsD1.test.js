// Keputusan pemilik 26 Okt (audit UI tahap 2) — D1 Keuangan:
// K-03 rincian PPN seragam (utils/taxBreakdown), B4 nominal kasus opsional, K-10 centang konfirmasi mati bawaan,
// K-15 tutup buku diblokir saat Suspense ≠ 0 (admin tembus dgn alasan), K-01 piutang semua pelanggan berlabel,
// K-02 "Kas & Bank" = buku besar + label selisih, K-07 posisi bersih antar-PT.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { taxBreakdownRows, docDpp, docGrandTotal, usesDppNilaiLain } from "../../utils/taxBreakdown";
import CaseCreateModal from "../finance/cases/CaseCreateModal";
import IntercoCreateModal from "../finance/interco/IntercoCreateModal";
import ClosingView from "../finance/ClosingView";
import BankAccountsView from "../finance/BankAccountsView";
import AdminHome from "../home/AdminHome";
import SalesHome from "../home/SalesHome";
import { BalancesPanel } from "../finance/interco/IntercoPanels";
import { askConfirm, askReason } from "../../services/confirmService";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => "mutasi bank belum dikenali"),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
jest.mock("../../components/PeriodUnlockCard", () => () => null);
jest.mock("../../components/OpeningCostBanner", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};   // jsdom (ErrorNotice menggulir)

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).find((k) => url.includes(k));
    if (!hit) return Promise.resolve({ data: [] });
    const v = map[hit];
    return v instanceof Error ? Promise.reject(v) : Promise.resolve({ data: v });
  });
}
function setValue(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await act(async () => {});
  await act(async () => {});
}

// CRA memasang `resetMocks: true` → implementasi mock dipasang ulang tiap uji.
beforeEach(() => {
  askConfirm.mockImplementation(async () => true);
  askReason.mockImplementation(async () => "mutasi bank belum dikenali");
});
afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

const SO_NL = { net_subtotal: 202318.4, dpp: 185458.53, dpp_nilai_lain: true, ppn_rate: 12, ppn_mode: "excluded",
  ppn_amount: 22255.02, grand_total: 224573.42, total_amount: 202318.4 };

test("K-03: rincian DPP · DPP nilai lain (11/12) · PPN · Total (termasuk PPN) — sama dengan PDF", () => {
  const rows = taxBreakdownRows(SO_NL);
  expect(rows.map((r) => r.label)).toEqual([
    "DPP (harga sebelum PPN)", "DPP nilai lain (11/12)", "PPN 12% × DPP nilai lain", "Total (termasuk PPN)"]);
  expect(rows[0].value).toBeCloseTo(202318.4, 2);
  expect(rows[3]).toMatchObject({ strong: true, value: 224573.42 });
  // PPN 11% biasa, harga termasuk PPN, tanpa PPN
  expect(taxBreakdownRows({ ppn_rate: 11, ppn_amount: 110, grand_total: 1110, dpp: 1000, dpp_nilai_lain: false })
    .map((r) => r.label)).toEqual(["DPP (harga sebelum PPN)", "PPN 11%", "Total (termasuk PPN)"]);
  const inc = taxBreakdownRows({ ppn_rate: 11, ppn_amount: 110, grand_total: 1110, ppn_mode: "included" });
  expect(inc[0].value).toBe(1000);
  expect(inc[1].label).toBe("PPN 11% (sudah termasuk dalam harga)");
  expect(taxBreakdownRows({ grand_total: 500, ppn_amount: 0 })).toEqual([{ key: "total", label: "Total", value: 500, strong: true }]);
  // PO lama tanpa bendera: DPP = 11/12 × harga → dikenali sebagai DPP nilai lain; label PPN Masukan
  const po = { dpp: 110000000, ppn_rate: 12, ppn_amount: 13200000, grand_total: 133200000 };
  expect(usesDppNilaiLain(po)).toBe(true);
  expect(docDpp(po)).toBe(120000000);
  expect(docGrandTotal(po)).toBe(133200000);
  expect(taxBreakdownRows(po, { ppnLabel: "PPN Masukan" })[2].label).toBe("PPN Masukan 12% × DPP nilai lain");
});

test("B4: 'Buat kasus' aktif tanpa nominal; cerita tetap ≥ 5 huruf", async () => {
  const { host } = await mount(<CaseCreateModal playbooks={[{ code: "double_payment", label: "Bayar ganda", question: "?" }]}
    customers={[]} suppliers={[]} onClose={() => {}} onCreated={() => {}} />);
  const btn = q(host, "case-create-submit");
  expect(btn.disabled).toBe(true);
  await act(async () => { setValue(q(host, "case-create-desc"), "Tran"); });
  expect(btn.disabled).toBe(true);                         // 4 huruf
  await act(async () => { setValue(q(host, "case-create-desc"), "Transfer dobel"); });
  expect(btn.disabled).toBe(false);                        // nominal kosong boleh
  expect(host.textContent).toContain("(opsional)");
  mockPost.mockResolvedValue({ data: { id: "fc1" } });
  await click(btn);
  expect(mockPost).toHaveBeenCalledWith("/api/finance-cases", expect.objectContaining({ amount: 0, description: "Transfer dobel" }));
});

test("K-10: Transaksi Antar-PT Baru — 'Langsung dikonfirmasi' tidak tercentang bawaan", async () => {
  routeGet({ "/products": [] });
  const ents = [{ id: "ent_a", short_name: "Sukacita" }, { id: "ent_b", short_name: "Cipta" }];
  const { host } = await mount(<IntercoCreateModal entities={ents} currentEntityId="ent_a" onClose={() => {}} />);
  expect(q(host, "interco-create-submit-now").checked).toBe(false);
  expect(q(host, "interco-create-submit-now-hint").textContent).toContain("draf");
});

const CLOSING_PREVIEW = {
  can_close: true, suspense_warning: true, suspense_blocks_close: true, suspense_balance: 1500000,
  suspense_override_min_len: 5, net_income: 0, residual_net_income: 0, closing_lines: [],
  revenue_total: 0, expense_total: 0,
};
const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }];

test("K-15: Suspense ≠ 0 — non-admin diblokir tanpa POST", async () => {
  routeGet({ "/finance/closing/preview": CLOSING_PREVIEW, "/finance/closing": [] });
  const mgr = { role: "manager", permissions: { accounting: ["view", "manage"] } };
  const { host } = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={mgr} />);
  await click(q(host, "closing-close-btn"));
  expect(mockPost).not.toHaveBeenCalled();
  expect(askReason).not.toHaveBeenCalled();
  expect(host.textContent).toContain("Tutup buku diblokir");
  expect(host.textContent).toContain("Hanya Admin");
});

test("K-15: admin menembus blokir Suspense dengan alasan (≥ 5 huruf) yang dikirim ke server", async () => {
  routeGet({ "/finance/closing/preview": CLOSING_PREVIEW, "/finance/closing": [] });
  mockPost.mockResolvedValue({ data: { period_label: "Oktober 2026", journal_entry_number: null,
    suspense_override: { reason: "mutasi bank belum dikenali" } } });
  const admin = { role: "admin", permissions: { accounting: ["*"] } };
  const { host } = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={admin} />);
  await click(q(host, "closing-close-btn"));
  expect(askReason).toHaveBeenCalledWith(expect.objectContaining({ reasonMinLength: 5, danger: true }));
  expect(askConfirm).toHaveBeenCalled();
  expect(mockPost).toHaveBeenCalledWith("/api/finance/closing/close",
    expect.objectContaining({ suspense_override_reason: "mutasi bank belum dikenali", entity_id: "ent_ksc" }));
  expect(q(host, "closing-notice").textContent).toContain("menembus blokir Suspense");
});

test("K-02: Rekening & Saldo — angka utama = buku besar, selisih dijelaskan", async () => {
  routeGet({
    "/bank-accounts/position": { gl_total: 913600000, gl_accounts: [], unlinked: { count: 20, inflow: 140000000, outflow: 1400000, net: 138600000 } },
    "/bank-accounts": [{ id: "b1", name: "BCA Operasional", account_type: "bank", bank_name: "BCA", balance: 775000000,
      txn_count: 0, unreconciled_count: 0, is_active: true, entity_id: "ent_ksc" }],
  });
  const { host } = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ permissions: {} }} />);
  expect(q(host, "bank-kpi-gl-value").textContent).toContain("913.600.000");
  expect(q(host, "bank-kpi-gl-sub").textContent).toContain("buku besar");
  expect(q(host, "bank-kpi-total-value").textContent).toContain("775.000.000");
  const gap = q(host, "bank-gap-label");
  expect(gap.textContent).toContain("138.600.000");
  expect(gap.textContent).toContain("20 transaksi kas belum tertaut");
});

test("K-01: Control Tower — piutang semua pelanggan berlabel sumber, baris 'Tanpa sales'", async () => {
  routeGet({
    "/home/admin": {
      sales: {}, ar: { outstanding: 407850942, overdue: 1193250, ar_ledger: 189300000, exposure: 218550942,
        overdue_customers: 1, scope: "semua pelanggan" },
      top_overdue: [{ sales_id: "", sales_name: "Tanpa sales", has_sales: false, overdue_amount: 1193250,
        ar_outstanding: 1193250, overdue_customers: 1 }],
      approvals: { items: [], total: 0 }, approvals_pending: 0, waiting_boards: [], leaderboard_top: [],
      // K-04 (permintaan D2) — KPI Stok Rendah = definisi tunggal; papan "Stok Perlu Reorder" = saran reorder (ROP).
      low_stock: { count: 7, items: [], threshold: 100, label: "produk dengan tersedia di atas 0 dan di bawah 100" },
      reorder: { count: 1, items: [{ product_id: "p1", product_name: "Batik Parang", sku: "BTK-1", on_hand: 20, reorder_point: 50 }] },
    },
  });
  const nav = jest.fn();
  const { host } = await mount(<AdminHome token="t" selectedEntity="ent_ksc" onNavigate={nav} />);
  expect(q(host, "kpi-belum-lunas").textContent).toContain("Semua pelanggan");
  expect(q(host, "kpi-belum-lunas").textContent).toContain("407.850.942");
  expect(q(host, "kpi-piutang-lewat-tempo").textContent).toContain("sama dengan layar Piutang");
  expect(q(host, "admin-home-overdue-row-none").textContent).toContain("Tanpa sales");
  expect(host.textContent).not.toContain("Pelanggan ber-sales");
  const low = q(host, "kpi-stok-rendah");
  expect(low.textContent).toContain("7");
  expect(low.textContent).toContain("tersedia < 100");
  await click(low);
  expect(nav).toHaveBeenCalledWith("operations");
  expect(q(host, "admin-home-lowstock").textContent).toContain("Batik Parang");   // papan reorder tetap
});

test("K-11 (permintaan D3): Beranda sales — papan PO Custom yang disaring server berlabel 'pelanggan Anda'", async () => {
  routeGet({
    "/home/sales": {
      period: "2026-10", commission: {}, target: {}, kpi: {}, history: [], customers: [], collections: [], recent_orders: [],
      waiting_boards: [{ key: "special_order", label: "PO custom", count: 0, rows: [], owner_scoped: true }],
    },
  });
  const { host } = await mount(<SalesHome token="t" user={{ role: "sales" }} onNavigate={() => {}} />);
  expect(q(host, "sales-home-boards").textContent).toContain("pelanggan Anda");
});

test("K-07: Saldo Antar-PT — posisi bersih per pasangan PT di atas rincian bruto", async () => {
  const { host } = await mount(<BalancesPanel accounts={[]} canWrite={false} netPairs={[{
    debtor_entity_id: "ent_b", debtor_entity_name: "Cipta Sandang", creditor_entity_id: "ent_a",
    creditor_entity_name: "Sukacita", net: 700, gross_debtor_owes: 1000, gross_creditor_owes: 300 }]} />);
  const row = q(host, "interco-net-ent_b-ent_a");
  expect(row.textContent).toContain("Cipta Sandang");
  expect(row.textContent).toContain("700");
  expect(host.textContent).toContain("Rincian per arah dagang (bruto)");
});
