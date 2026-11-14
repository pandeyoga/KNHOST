// PK-16 (UX-06, UX-07, UX-14, RC-01, RP-02, RP-04 · K-15) — laporan dan form uang menyebut PT-nya; mode gabungan
// diberi label. Uji komponen U8–U14 (spesifikasi `docs/blueprint/unit/PK-16.md`, Uji penerimaan):
//   U8  `EntityScopeBanner` — empat teks persis (laporan/form × satu PT/gabungan), tanpa id PT, tautan Konsolidasi Grup;
//   U9  banner terpasang di tiap layar tabel pemasangan, SEBELUM angka pertama (berparameter);
//   U10 Laba-Rugi: permintaan kedua gagal → galat tampil, angka permintaan pertama hilang;
//   U11 sama untuk layar laporan lain (berparameter);
//   U12 form "Catat Transaksi Kas": banner form, tanpa isian Entitas, `entity_id` tidak dikirim;
//   U13 form jurnal manual: banner form di kepala pop-up;
//   U14 nama berkas unduhan memuat nama pendek PT / `gabungan`.
// `EntityScopeBanner` dimuat lewat `require` di dalam U8 saja, supaya U9–U14 tetap bisa dijalankan pada berkas lama
// (bukti merah: komponen itu belum ada sebelum PK-16).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import FinancialStatementsView from "../finance/FinancialStatementsView";
import ProfitabilityView from "../finance/ProfitabilityView";
import CashFlowForecastView from "../finance/CashFlowForecastView";
import BudgetView from "../finance/BudgetView";
import GeneralLedger from "../finance/GeneralLedger";
import FinanceTowerView from "../finance/FinanceTowerView";
import BiFinanceView from "../finance/BiFinanceView";
import BankAccountsView from "../finance/BankAccountsView";
import CashManagementView from "../purchasing/CashManagementView";
import JournalEntryModal from "../finance/JournalEntryModal";
import { setAccessContext } from "../../config/roles";

// PR-T7 — `canCurrent` kini "tidak" selama konteks izin belum dimuat; layar diuji sebagai Admin yang sudah masuk.
beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => true), askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
// Pemilih bawaan (cmdk/radix) & kalender (radix popover) diganti isian polos yang tetap memanggil onValueChange/onChange.
jest.mock("../../components/KNSelect", () => (p) => (
  <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
    <option value="">-</option>
    {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange && p.onChange(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
// Komponen berat yang tidak diuji di sini.
jest.mock("../costing/CostingView", () => () => <div data-testid="stub-costing" />);
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "kn_tanya_pending" }));
// recharts butuh ukuran DOM nyata — di jsdom cukup diganti kotak kosong.
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

// Konteks kepala aplikasi: tiga PT, nama pendek "konteks".
const ENTS = [
  { id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" },
  { id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" },
  { id: "ent_cs", legal_name: "PT Cipta Sandang", short_name: "Cipta" },
];
// `scope_meta` server — nama pendek SENGAJA beda dari konteks, supaya terbukti banner memakai jawaban server.
const META_ONE = {
  mode: "single", entity_ids: ["ent_ksc"], eliminated: false, label: "PT Kain Suka Cita",
  entities: [{ id: "ent_ksc", short_name: "KSC", legal_name: "PT Kain Suka Cita" }],
};
const META_ALL = {
  mode: "combined", entity_ids: ["ent_ksc", "ent_kanda", "ent_cs"], eliminated: false,
  label: "Penjumlahan semua PT (KSC, KANDA, CS) — transaksi antar-PT belum dieliminasi",
  entities: [
    { id: "ent_ksc", short_name: "KSC", legal_name: "PT Kain Suka Cita" },
    { id: "ent_kanda", short_name: "KANDA", legal_name: "CV Kanda Suka" },
    { id: "ent_cs", short_name: "CS", legal_name: "PT Cipta Sandang" },
  ],
};
const TXT = {
  reportOne: "Angka untuk PT Kain Suka Cita",
  reportAll: "Penjumlahan semua PT (KSC, KANDA, CS) — transaksi antar-PT belum dieliminasi. "
    + "Untuk angka grup, buka Konsolidasi Grup.",
  formOne: "Dicatat di buku PT Kain Suka Cita",
  formAll: "Mode Semua PT hanya untuk melihat. Pilih satu PT di kepala aplikasi sebelum menyimpan.",
};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el, { selectedEntity = "all", entities = ENTS, role = "admin", nav = () => {} } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={selectedEntity} entities={entities}>
        <AppNavProvider role={role} onNavigateTo={nav} onOpenDocument={() => {}}>{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype
    : el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await flush();
}
/** Jawaban GET per akhiran URL (kunci terpanjang menang); fungsi = dipanggil tiap permintaan. */
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const path = String(url).split("?")[0];
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => path.endsWith(k));
    const v = hit ? map[hit] : [];
    return typeof v === "function" ? v() : Promise.resolve({ data: v });
  });
}
const fail500 = () => Promise.reject(Object.assign(new Error("500"), { response: { status: 500, data: { detail: "Galat server uji" } } }));
/** a muncul sebelum b di urutan dokumen. */
const before = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

// ── U8 — komponen ─────────────────────────────────────────────────────────────────────────────────────────────────
describe("U8 — EntityScopeBanner: empat teks persis, tanpa id PT", () => {
  const load = () => require("../../components/EntityScopeBanner").default;

  test("meta satu PT: laporan 'Angka untuk …', form 'Dicatat di buku …'", async () => {
    const Banner = load();
    await mount(<div><Banner meta={META_ONE} /><Banner meta={META_ONE} variant="form" testId="f" /></div>);
    expect(norm(q("entity-scope-banner").textContent)).toBe(TXT.reportOne);
    expect([...q("entity-scope-banner").querySelectorAll("b")].map((b) => b.textContent)).toEqual(["PT Kain Suka Cita"]);
    expect(norm(q("f").textContent)).toBe(TXT.formOne);
    expect(q("entity-scope-banner-combined")).toBeNull();
    expect(document.body.textContent).not.toContain("ent_");
  });

  test("meta gabungan 3 PT: teks persis, penanda `-combined`, warna peringatan, tautan Konsolidasi Grup", async () => {
    const Banner = load();
    const nav = jest.fn();
    await mount(<div><Banner meta={META_ALL} /><Banner meta={META_ALL} variant="form" testId="f" /></div>, { nav });
    const el = q("entity-scope-banner");
    expect(norm(el.textContent)).toBe(TXT.reportAll);
    expect(q("entity-scope-banner-combined")).not.toBeNull();
    expect(el.className).toContain("bg-kn-warning-soft");
    expect([...el.querySelectorAll("b")].map((b) => b.textContent)).toEqual(["Penjumlahan semua PT", "belum"]);
    const link = q("entity-scope-banner-consolidation");
    expect(link.tagName).toBe("BUTTON");
    expect(link.textContent).toBe("Konsolidasi Grup");
    await click(link);
    expect(nav).toHaveBeenCalledWith("consolidation", expect.anything());   // tab Akuntansi & Pajak › Laporan › Konsolidasi Grup
    expect(norm(q("f").textContent)).toBe(TXT.formAll);
    expect(q("f-combined")).not.toBeNull();
    expect(document.body.textContent).not.toContain("ent_");
  });

  test("onOpenConsolidation dipakai bila diberikan; peran tanpa akses → teks tebal, bukan tombol mati", async () => {
    const Banner = load();
    const open = jest.fn();
    await mount(<Banner meta={META_ALL} onOpenConsolidation={open} />, { role: "" });
    await click(q("entity-scope-banner-consolidation"));
    expect(open).toHaveBeenCalledTimes(1);
    document.body.innerHTML = "";
    await mount(<Banner meta={META_ALL} />, { role: "sales" });
    expect(q("entity-scope-banner-consolidation")).toBeNull();
    expect(q("entity-scope-banner-consolidation-readonly").textContent).toBe("Konsolidasi Grup");
    expect(norm(q("entity-scope-banner").textContent)).toBe(TXT.reportAll);
  });

  test("tanpa meta: dihitung dari useEntityScope (satu PT dipilih; Semua PT → gabungan nama konteks)", async () => {
    const Banner = load();
    await mount(<div><Banner /><Banner variant="form" testId="f" /></div>, { selectedEntity: "ent_ksc" });
    expect(norm(q("entity-scope-banner").textContent)).toBe(TXT.reportOne);
    expect(norm(q("f").textContent)).toBe(TXT.formOne);
    document.body.innerHTML = "";
    await mount(<Banner />, { selectedEntity: "all" });
    expect(norm(q("entity-scope-banner").textContent)).toContain("Penjumlahan semua PT (Sukacita, Kanda, Cipta)");
    document.body.innerHTML = "";
    // Akun ber-satu-PT yang memilih "Semua PT" melihat banner satu PT (ASUMSI spesifikasi).
    await mount(<Banner />, { selectedEntity: "all", entities: [ENTS[1]] });
    expect(norm(q("entity-scope-banner").textContent)).toBe("Angka untuk CV Kanda Suka");
  });

  test("nama dari server yang ternyata id (PT tanpa nama) tidak pernah tampil", async () => {
    const Banner = load();
    const bare = { mode: "single", entity_ids: ["ent_x"], entities: [{ id: "ent_x", short_name: "ent_x", legal_name: "ent_x" }],
      eliminated: false, label: "ent_x" };
    await mount(<Banner meta={bare} />, { entities: [] });
    expect(norm(q("entity-scope-banner").textContent)).toBe("Angka untuk Entitas aktif");
    expect(document.body.textContent).not.toContain("ent_");
  });
});

// ── Jawaban server per layar (U9) ─────────────────────────────────────────────────────────────────────────────────
const withMeta = (body, meta = META_ALL) => ({ ...body, scope_meta: meta });
const GL_SUMMARY = { journal_count: 3, total_debit: 300, total_credit: 300, balanced: true, sources: [] };
function screenRoutes(meta = META_ALL) {
  return {
    "/finance/income-statement": withMeta({ revenue_total: 70000000, gross_profit: 30000000, net_income: 23000000, net_margin: 0.33, sections: [] }, meta),
    "/finance/balance-sheet": withMeta({ assets_total: 100, liabilities_total: 40, equity_total: 60, balanced: true,
      assets: { sections: [] }, liabilities: { sections: [] }, equity: { lines: [] } }, meta),
    "/finance/cash-flow": withMeta({ begin_cash: 10, end_cash: 20, net_change: 10, operating: { total: 10 }, investing: {}, financing: {}, reconciled: true }, meta),
    "/finance/equity-changes": withMeta({ begin_total: 10, end_total: 20, net_income: 10, movement_total: 10, components: [] }, meta),
    "/finance/profitability": withMeta({ totals: { revenue: 10, cogs: 5, margin: 5, margin_pct: 50, orders: 1 }, by_product: [], monthly: [] }, meta),
    "/finance/cashflow-forecast": withMeta({ cash_now: 10, total_inflow: 0, total_outflow: 0, projected_cash: 10, buckets: [] }, meta),
    "/finance/budget-vs-actual": withMeta({ totals: { budget: 10 }, rows: [], by_dimension: {}, alerts: [] }, meta),
    "/finance/budget-rules": { mode: "warn" },
    "/finance/budget-keys": { accounts: [], categories: [] },
    "/gl/summary": withMeta(GL_SUMMARY, meta),
    "/gl/accounts": [],
    "/gl/journal": { items: [], total: 0, page: 1, page_size: 20, has_more: false },
    "/gl/trial-balance": withMeta({ rows: [{ code: "1-1100", name: "Kas", type_label: "Aset", debit_balance: 300, credit_balance: 0 }],
      total_debit: 300, total_credit: 300, balanced: true }, meta),
    "/finance/tower": withMeta({ period: { month: "2026-10", year: 2026 }, cash: { total: 10, accounts: [] },
      ar: { outstanding: 0, aging: {}, top: [] }, ap: { outstanding: 0, aging: {}, top: [] }, working_capital: 10,
      pl: { ytd: {}, mtd: {} }, monthly: [], ratios: {} }, meta),
    "/finance/bi": withMeta({ ratios: { gross_margin: 30, net_margin: 10 }, monthly: [], entity_comparison: [] }, meta),
    "/bank-accounts": [{ id: "b1", name: "BCA Operasional", account_type: "bank", balance: 10, inflow: 0, outflow: 0,
      txn_count: 0, unreconciled_count: 0, is_active: true, entity_id: "ent_ksc" }],
    "/bank-accounts/position": { gl_total: 10, unlinked: { count: 0, net: 0 } },
    "/cash-transactions": [],
    "/cash-transactions/summary": withMeta({ kas_kecil: { balance: 10 }, kas_besar: { balance: 20 }, kas_kecil_per_entity: {} }, meta),
    "/entities": ENTS,
    "/finance/closing/status": { closed: false },
  };
}
const ADMIN = { role: "admin", permissions: { cash: ["*"], budget: ["*"], audit: ["view"] } };
const fs = (tab) => (
  <ViewPresetProvider preset={{ view: "financial-statements", nonce: 1, tab }}><FinancialStatementsView selectedEntity="all" /></ViewPresetProvider>);

// [nama layar, elemen, testid angka pertama, sebelum render (mis. pindah tab), banner dari server?]
const SCREENS = [
  ["Laba-Rugi", () => fs("pl"), "fs-pl-kpi-revenue", null, true],
  ["Neraca", () => fs("bs"), "fs-bs-kpi-assets", null, true],
  ["Arus Kas", () => fs("cf"), "cf-kpi-begin", null, true],
  ["Perubahan Ekuitas", () => fs("eq"), "eq-kpi-begin", null, true],
  ["Profitabilitas & Margin", () => <ProfitabilityView selectedEntity="all" />, "prof-kpi-revenue", null, true],
  ["Proyeksi Arus Kas", () => <CashFlowForecastView selectedEntity="all" />, "fcst-kpi-cash", null, true],
  ["Anggaran vs Realisasi", () => <BudgetView selectedEntity="all" currentUser={ADMIN} />, "budget-kpi-total", null, true],
  ["Jurnal & Buku Besar › Jurnal", () => <GeneralLedger selectedEntity="all" entities={ENTS} />, "gl-kpi-count", null, true],
  ["Jurnal & Buku Besar › Neraca Saldo", () => <GeneralLedger selectedEntity="all" entities={ENTS} />, "gl-trial-total-debit", "gl-tab-trial", true],
  ["Jurnal & Buku Besar › Buku Besar", () => <GeneralLedger selectedEntity="all" entities={ENTS} />, "gl-ledger-prompt", "gl-tab-ledger", true],
  ["Dasbor Keuangan › Posisi & Kontrol", () => <FinanceTowerView selectedEntity="all" />, "tower-kpi-cash", null, true],
  ["Dasbor Keuangan › BI Keuangan", () => <BiFinanceView selectedEntity="all" />, "bi-ratio-gross", null, true],
  ["Kas & Bank › Rekening & Saldo", () => <BankAccountsView selectedEntity="all" currentUser={ADMIN} />, "bank-kpi-gl", null, false],
  ["Kas & Bank › Transaksi Kas", () => <CashManagementView selectedEntity="all" currentUser={ADMIN} />, "cash-besar-card", null, true],
];

describe("U9 — banner terpasang di tiap layar, sebelum angka pertama", () => {
  test.each(SCREENS)("%s", async (_name, el, firstNumber, tabId, fromServer) => {
    routeGet(screenRoutes());
    await mount(el());
    if (tabId) await click(q(tabId));
    const banner = q("entity-scope-banner");
    expect(banner).not.toBeNull();
    expect(q("entity-scope-banner-combined")).not.toBeNull();
    // Layar yang endpoint-nya mengirim `scope_meta` memakai nama dari server; Rekening & Saldo dari konteks.
    expect(norm(banner.textContent)).toContain(fromServer ? "(KSC, KANDA, CS)" : "(Sukacita, Kanda, Cipta)");
    expect(banner.textContent).not.toContain("ent_");
    const first = q(firstNumber);
    expect(first).not.toBeNull();
    expect(before(banner, first)).toBe(true);
    expect(document.body.querySelectorAll('[data-testid="entity-scope-banner"]')).toHaveLength(1);
  });
});

// ── U10 — Laba-Rugi: sukses lalu gagal ────────────────────────────────────────────────────────────────────────────
describe("U10 — Laba-Rugi: ganti periode lalu gagal → angka lama hilang", () => {
  test("permintaan pertama laba bersih 23.000.000, kedua 500 → fs-pl-error tampil, 23.000.000 tidak ada", async () => {
    let calls = 0;
    const routes = screenRoutes(META_ONE);
    routeGet({ ...routes, "/finance/income-statement": () => {
      calls += 1;
      return calls === 1 ? Promise.resolve({ data: routes["/finance/income-statement"] }) : fail500();
    } });
    await mount(fs("pl"), { selectedEntity: "ent_ksc" });
    expect(document.body.textContent).toContain("23.000.000");
    await type(q("fs-pl-start"), "2026-10-01");        // ganti periode
    expect(calls).toBe(2);
    expect(q("fs-pl-error")).not.toBeNull();
    expect(document.body.textContent).not.toContain("23.000.000");
    expect(q("fs-pl-table")).toBeNull();
  });
});

// ── U11 — layar laporan lain: sukses lalu gagal (berparameter) ────────────────────────────────────────────────────
const BIG = 777000000;   // angka pembeda yang hanya ada di jawaban pertama
const U11 = [
  ["BI Keuangan", () => <BiFinanceView selectedEntity="ent_ksc" />, "/finance/bi",
    { ratios: { current_assets: BIG, current_liabilities: 1 }, monthly: [], entity_comparison: [] }, null, "bi-refresh", "bi-error"],
  ["Dasbor Keuangan", () => <FinanceTowerView selectedEntity="ent_ksc" />, "/finance/tower",
    { period: { month: "2026-10", year: 2026 }, cash: { total: BIG, accounts: [] }, ar: { outstanding: 0, aging: {}, top: [] },
      ap: { outstanding: 0, aging: {}, top: [] }, working_capital: 0, pl: { ytd: {}, mtd: {} }, monthly: [], ratios: {} },
    null, "tower-refresh", "tower-error"],
  ["Arus Kas", () => fs("cf"), "/finance/cash-flow",
    { begin_cash: BIG, end_cash: 0, net_change: 0, operating: {}, investing: {}, financing: {}, reconciled: true }, null, "cf-refresh", "cf-error"],
  ["Perubahan Ekuitas", () => fs("eq"), "/finance/equity-changes",
    { begin_total: BIG, end_total: 0, net_income: 0, movement_total: 0, components: [] }, null, "eq-refresh", "eq-error"],
  ["Neraca Saldo", () => <GeneralLedger selectedEntity="ent_ksc" entities={ENTS} />, "/gl/trial-balance",
    { rows: [{ code: "1-1100", name: "Kas", type_label: "Aset", debit_balance: BIG, credit_balance: 0 }], total_debit: BIG, total_credit: BIG, balanced: true },
    "gl-tab-trial", "gl-refresh", "gl-error"],
  ["Profitabilitas", () => <ProfitabilityView selectedEntity="ent_ksc" />, "/finance/profitability",
    { totals: { revenue: BIG, cogs: 0, margin: 0, orders: 1 }, by_product: [], monthly: [] }, null, "prof-refresh", "prof-error"],
  ["Proyeksi Arus Kas", () => <CashFlowForecastView selectedEntity="ent_ksc" />, "/finance/cashflow-forecast",
    { cash_now: BIG, total_inflow: 0, total_outflow: 0, projected_cash: 0, buckets: [] }, null, "fcst-refresh", "fcst-error"],
  ["Anggaran", () => <BudgetView selectedEntity="ent_ksc" currentUser={ADMIN} />, "/finance/budget-vs-actual",
    { totals: { budget: BIG }, rows: [], by_dimension: {}, alerts: [] }, null, "budget-refresh", "budget-error"],
  ["Rekening & Saldo", () => <BankAccountsView selectedEntity="ent_ksc" currentUser={ADMIN} />, "/bank-accounts",
    [{ id: "b1", name: "BCA Operasional", account_type: "bank", balance: BIG, inflow: 0, outflow: 0, txn_count: 0,
      unreconciled_count: 0, is_active: true, entity_id: "ent_ksc" }], null, "bank-refresh", "bank-error"],
];

describe("U11 — sukses lalu gagal: angka jawaban pertama tidak tersisa, galat tampil", () => {
  test.each(U11)("%s", async (_name, el, path, firstBody, tabId, refreshId, errorId) => {
    let failing = false;
    const routes = screenRoutes(META_ONE);
    routeGet({ ...routes, [path]: () => (failing ? fail500() : Promise.resolve({ data: firstBody })) });
    await mount(el(), { selectedEntity: "ent_ksc" });
    if (tabId) await click(q(tabId));
    expect(document.body.textContent).toContain("777.000.000");
    failing = true;
    await click(q(refreshId));
    expect(q(errorId)).not.toBeNull();
    expect(document.body.textContent).not.toContain("777.000.000");
  });
});

// ── U12 — form kas ────────────────────────────────────────────────────────────────────────────────────────────────
describe("U12 — Catat Transaksi Kas: banner form, tanpa isian Entitas, entity_id tidak dikirim", () => {
  test("PT terpilih ent_kanda", async () => {
    routeGet(screenRoutes({ ...META_ONE, entity_ids: ["ent_kanda"],
      entities: [{ id: "ent_kanda", short_name: "KANDA", legal_name: "CV Kanda Suka" }], label: "CV Kanda Suka" }));
    mockPost.mockResolvedValue({ data: { number: "KANDA/CASH-0001", direction: "out" } });
    await mount(<CashManagementView currentUser={ADMIN} selectedEntity="ent_kanda" />, { selectedEntity: "ent_kanda" });
    await click(q("create-cash-button"));
    const form = q("cash-form");
    expect(form).not.toBeNull();
    const scope = q("cash-form-scope");
    expect(scope).not.toBeNull();
    expect(form.contains(scope)).toBe(true);
    expect(norm(scope.textContent)).toBe("Dicatat di buku CV Kanda Suka");
    expect(q("cash-entity-select")).toBeNull();
    expect(document.body.textContent).not.toContain("PT Kain Suka Cita");
    expect(document.body.textContent).not.toContain("ent_");

    await type(q("cash-amount-input"), "75000");
    await type(q("cash-description-input"), "Beli ATK");
    await click(q("submit-cash-button"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/cash-transactions");
    expect(body).toEqual(expect.objectContaining({ amount: 75000, description: "Beli ATK" }));
    expect(Object.prototype.hasOwnProperty.call(body, "entity_id")).toBe(false);
    expect(typeof cfg?.headers?.["Idempotency-Key"]).toBe("string");   // PK-12 tetap utuh
  });
});

// ── U13 — form jurnal manual ──────────────────────────────────────────────────────────────────────────────────────
describe("U13 — Jurnal manual: banner form di kepala pop-up", () => {
  test("PT terpilih ent_ksc → 'Dicatat di buku PT Kain Suka Cita' di kepala; Semua PT → hanya melihat", async () => {
    routeGet({ "/finance/closing/status": { closed: false } });
    await mount(<JournalEntryModal accounts={[]} onClose={() => {}} onSaved={() => {}} />, { selectedEntity: "ent_ksc" });
    const scope = q("je-scope");
    expect(scope).not.toBeNull();
    expect(scope.closest(".kn-modal-head")).not.toBeNull();
    expect(norm(scope.textContent)).toBe(TXT.formOne);
    document.body.innerHTML = "";
    await mount(<JournalEntryModal accounts={[]} onClose={() => {}} onSaved={() => {}} />, { selectedEntity: "all" });
    expect(norm(q("je-scope").textContent)).toBe(TXT.formAll);
  });
});

// ── U14 — nama berkas unduhan ─────────────────────────────────────────────────────────────────────────────────────
describe("U14 — nama berkas unduhan memuat nama pendek PT / `gabungan`", () => {
  let names = [];
  let clickSpy;
  beforeEach(() => {
    names = [];
    URL.createObjectURL = jest.fn(() => "blob:uji");
    URL.revokeObjectURL = jest.fn();
    clickSpy = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function rec() { names.push(this.download); });
  });
  afterEach(() => { clickSpy.mockRestore(); });

  const exportRoutes = (meta) => ({ ...screenRoutes(meta), "export.csv": "csv", "export.xlsx": "xlsx" });

  test("Laba-Rugi: PT terpilih ent_ksc → nama pendek; mode gabungan → `gabungan`", async () => {
    routeGet(exportRoutes(META_ONE));
    await mount(fs("pl"), { selectedEntity: "ent_ksc" });
    await click(q("fs-pl-export"));
    expect(names).toHaveLength(1);
    expect(names[0]).toMatch(/^laba-rugi_KSC_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$/);
    document.body.innerHTML = "";
    routeGet(exportRoutes(META_ALL));
    await mount(fs("pl"), { selectedEntity: "all" });
    await click(q("fs-pl-export"));
    expect(names[1]).toMatch(/^laba-rugi_gabungan_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$/);
  });

  test.each([
    ["neraca", () => fs("bs"), "fs-bs-export", /^neraca_KSC_\d{4}-\d{2}-\d{2}\.csv$/],
    ["arus kas", () => fs("cf"), "cf-export", /^arus-kas_KSC_.+\.csv$/],
    ["perubahan ekuitas", () => fs("eq"), "eq-export", /^perubahan-ekuitas_KSC_.+\.csv$/],
    ["profitabilitas", () => <ProfitabilityView selectedEntity="ent_ksc" />, "prof-export-xlsx", /^profitabilitas_KSC_.+\.xlsx$/],
  ])("%s memuat nama pendek PT", async (_n, el, btn, rx) => {
    routeGet(exportRoutes(META_ONE));
    await mount(el(), { selectedEntity: "ent_ksc" });
    await click(q(btn));
    expect(names).toHaveLength(1);
    expect(names[0]).toMatch(rx);
  });
});
