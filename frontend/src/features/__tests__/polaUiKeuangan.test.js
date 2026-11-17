// Pola UI gelombang Keuangan (docs/blueprint/04_POLA_UI.md · masukan pemilik 16 Nov M32, M35, M36, M37, M40):
//  · M32 Beranda Keuangan › Posisi — kartu rasio, Modal Kerja dan panel umur/terbesar/kas punya jalan ke daftar sumbernya;
//    nama di "Piutang/Hutang Terbesar" membuka kartu pelanggan/pemasok; paragraf kaki pindah ke ikon ?.
//  · M35/M36 Antar-PT — kepala satu baris, SATU tombol buat per layar (di bilah daftar), status = dropdown (bukan deret
//    tab), kartu "Dokumen terbuka" = saringan cepat; Kontrak Internal dibuka dari pop-up Transaksi Baru.
//  · M37 Bagan Akun — lingkup mengikuti PT bilah atas (tanpa deret chip ungu); Template Global = satu pilihan dropdown.
//  · M40 Lembar Insentif — satu bilah daftar (cari · periode · status dropdown · + Buat lembar), tanpa deret chip.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import FinanceTowerView from "../finance/FinanceTowerView";
import IntercoView from "../finance/interco/IntercoView";
import { OPEN_STATUS_FILTER } from "../finance/interco/intercoApi";
import ChartOfAccounts from "../finance/ChartOfAccounts";
import IncentiveSheetsView from "../incentive/IncentiveSheetsView";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

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
  __esModule: true, askConfirm: jest.fn(async () => true), askReason: jest.fn(async () => "alasan uji"), default: {},
}));
// Pemilih bawaan (radix/cmdk) diganti <select> polos — yang diuji tata letak & alurnya, bukan pemilihnya.
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={!!p.disabled}
      onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope" />);
jest.mock("recharts", () => {
  const Box = ({ children }) => <div>{children}</div>;
  return new Proxy({}, { get: (_t, k) => (k === "__esModule" ? true : Box) });
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const settle = async () => { for (let i = 0; i < 6; i += 1) await act(async () => {}); };
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await settle();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}
async function pilih(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await settle();
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

// ── M32 — Beranda Keuangan ──────────────────────────────────────────────────────────────────────────────────────────
describe("M32 — Beranda Keuangan: kartu angka bertujuan", () => {
  const TOWER = {
    period: { month: "2026-11", year: 2026 },
    cash: { total: 500000, accounts: [{ code: "1-1100", name: "Kas", balance: 500000 }] },
    ar: { outstanding: 140000, ar_ledger: 40000, exposure: 100000, overdue: 0, aging: {}, bucket_labels: [],
      top: [{ customer_id: "c1", customer_name: "Toko Kain", outstanding: 140000, oldest_days: 3 }] },
    ap: { outstanding: 90000, aging: {}, top: [{ party_id: "s1", party: "CV Benang", amount: 90000, bill_count: 2 }] },
    working_capital: 450000, working_capital_basis: "Kas + piutang tercatat − hutang",
    pl: { mtd: {}, ytd: {} }, monthly: [], ratios: { gross_margin: 27.8, net_margin: 19.6, current_ratio: 80, debt_to_equity: 0 },
  };
  const MGR = { role: "manager", permissions: { customer: ["view"], supplier: ["view"] } };

  test("rasio & Modal Kerja membuka Laporan Keuangan; panel membuka daftar; paragraf kaki → ikon ?", async () => {
    routeGet({ "/finance/tower": TOWER });
    const nav = jest.fn();
    const host = await mount(<AppNavProvider role="manager" onNavigateTo={nav}>
      <FinanceTowerView selectedEntity="ent_ksc" currentUser={MGR} />
    </AppNavProvider>);
    // Kartu rasio = tombol (dulu kotak angka saja).
    const marjin = q(host, "tower-ratio-gross");
    expect(marjin.tagName).toBe("BUTTON");
    await click(marjin);
    expect(nav).toHaveBeenLastCalledWith("financial-statements",
      expect.objectContaining({ preset: { tab: "pl", from: { view: "finance-tower" } } }));
    await click(q(host, "tower-ratio-current"));
    expect(nav.mock.calls.at(-1)[1].preset.tab).toBe("bs");
    // Modal Kerja dulu satu-satunya kartu KPI tanpa tautan → Neraca.
    await click(q(host, "tower-kpi-wc-open"));
    expect(nav.mock.calls.at(-1)[0]).toBe("financial-statements");
    expect(nav.mock.calls.at(-1)[1].preset.tab).toBe("bs");
    // Panel umur/terbesar/kas → daftar sumbernya.
    await click(q(host, "tower-ar-aging-open"));
    expect(nav.mock.calls.at(-1)[0]).toBe("ar-aging");
    await click(q(host, "tower-top-ap-open"));
    expect(nav.mock.calls.at(-1)[0]).toBe("vendor-bills");
    await click(q(host, "tower-cash-open"));
    expect(nav.mock.calls.at(-1)[0]).toBe("bank-accounts");
    // Nama pelanggan/pemasok = pembuka kartu (bukan teks mati).
    expect(q(host, "tower-ar-card-0").tagName).toBe("BUTTON");
    expect(q(host, "tower-ap-card-0").tagName).toBe("BUTTON");
    // Paragraf "Dashboard terpadu — …" tidak dipajang; isinya di ikon ?.
    expect(host.textContent).not.toContain("Dashboard terpadu");
    await click(q(host, "tower-help"));
    expect(q(host, "tower-help-text").textContent).toContain("Dashboard terpadu");
  });

  test("peran yang tidak boleh membuka Laporan Keuangan → kartu rasio tanpa klik (bukan tombol mati)", async () => {
    routeGet({ "/finance/tower": TOWER });
    const host = await mount(<FinanceTowerView selectedEntity="ent_ksc" currentUser={MGR} />);   // di luar penyedia navigasi
    expect(q(host, "tower-ratio-gross").tagName).toBe("DIV");
    expect(q(host, "tower-ar-aging-open")).toBeNull();
    expect(q(host, "tower-ar-card-0")).toBeNull();
    expect(q(host, "tower-ar-card-0-text").textContent).toBe("Toko Kain");
  });
});

// ── M35/M36 — Antar-PT ──────────────────────────────────────────────────────────────────────────────────────────────
describe("M35/M36 — Antar-PT: satu tombol buat per layar, bilah daftar satu baris", () => {
  const USER = { role: "manager", permissions: {
    interco: ["view", "create", "settle", "approve", "ship", "invoice"], interco_finance: ["view"] } };
  const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }, { id: "ent_kanda", short_name: "Kanda" }];
  const SUMMARY = { net_receivable: 0, net_payable: 1342656, total_receivable: 0, total_payable: 1342656,
    open_documents: 1, net_pairs: [] };
  const routes = () => routeGet({ "/interco/summary": SUMMARY, "/interco/transactions": [], "/interco/accounts": [],
    "/interco/settlements": [], "/interco/returns": [], "/interco/margin-report": { totals: { unrealized_margin: -67738 } },
    "/interco/meta": { defaults: { pricing_mode: "fixed_price", ppn_mode: "tanpa_ppn" } }, "/products": [] });

  test("kepala satu baris tanpa tombol buat; Transaksi Baru hanya di bilah daftar; status = dropdown", async () => {
    routes();
    const host = await mount(<IntercoView currentUser={USER} selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q(host, "interco-header")).not.toBeNull();
    expect(q(host, "interco-header").querySelectorAll("button.primary-button, button.secondary-button")).toHaveLength(0);
    expect(host.textContent).not.toContain("Dokumen kembar (PO");   // paragraf penjelasan → ikon ?
    // Satu tombol buat di layar Daftar Transaksi, di ujung bilah daftar.
    expect(host.querySelectorAll('[data-testid="interco-create-btn"]')).toHaveLength(1);
    expect(q(host, "interco-tx-toolbar").contains(q(host, "interco-create-btn"))).toBe(true);
    expect(q(host, "interco-open-settle-btn")).toBeNull();
    expect(q(host, "interco-open-contract-btn")).toBeNull();
    // Status = dropdown (dulu deret tab "Semua status · Draf · Dikonfirmasi …").
    expect(q(host, "interco-filter-status").tagName).toBe("SELECT");
    expect(q(host, "interco-filter-status-bar")).toBeNull();
    expect(q(host, "interco-tx-toolbar").contains(q(host, "interco-filter-role"))).toBe(true);
    expect(q(host, "interco-tx-toolbar").contains(q(host, "interco-tx-search"))).toBe(true);
  });

  test("kartu 'Dokumen terbuka' = saringan cepat (server menyaring beberapa status); kartu uang → tab", async () => {
    routes();
    const host = await mount(<IntercoView currentUser={USER} selectedEntity="ent_ksc" entities={ENTS} />);
    const kartu = q(host, "interco-kpi-open");
    expect(kartu.tagName).toBe("BUTTON");
    await click(kartu);
    const panggil = mockGet.mock.calls.filter(([u]) => u.endsWith("/interco/transactions"));
    expect(panggil.at(-1)[1].params.status).toBe(OPEN_STATUS_FILTER);
    expect(q(host, "interco-kpi-open").getAttribute("aria-pressed")).toBe("true");
    expect(q(host, "interco-filter-status").value).toBe(OPEN_STATUS_FILTER);
    await click(q(host, "interco-kpi-unrealized"));
    expect(q(host, "interco-margin-panel")).not.toBeNull();
    expect(q(host, "interco-kpi-unrealized").getAttribute("aria-pressed")).toBe("true");
  });

  test("Settlement: tombol buatnya Buat Pelunasan (satu); Kontrak Internal dibuka dari pop-up Transaksi Baru", async () => {
    routes();
    const host = await mount(<IntercoView currentUser={USER} selectedEntity="ent_ksc" entities={ENTS} />);
    await click(q(host, "interco-tab-settlements"));
    expect(host.querySelectorAll('[data-testid="interco-open-settle-btn"]')).toHaveLength(1);
    expect(q(host, "interco-create-btn")).toBeNull();
    await click(q(host, "interco-tab-transactions"));
    await click(q(host, "interco-create-btn"));
    const link = q(document.body, "interco-open-contract-btn");
    expect(q(document.body, "interco-create-modal").contains(link)).toBe(true);
    await click(link);
    expect(q(document.body, "interco-create-modal")).toBeNull();
    expect(q(document.body, "interco-contract-modal")).not.toBeNull();
  });
});

// ── M37 — Bagan Akun ────────────────────────────────────────────────────────────────────────────────────────────────
describe("M37 — Bagan Akun: lingkup mengikuti PT bilah atas", () => {
  const ENTS = [{ id: "ent_ksc", short_name: "Sukacita", status: "active" },
    { id: "ent_kanda", short_name: "Kanda Fabric", status: "active" }];
  const ADMIN = { role: "admin", permissions: { accounting: ["*"], audit: ["view"] } };
  const ACCOUNTS = [
    { code: "1-1000", name: "Kas", type: "asset", is_postable: true, normal_balance: "debit" },
    { code: "1-1200", name: "Piutang", type: "asset", is_postable: true, normal_balance: "debit", entity_id: "ent_ksc" },
    { code: "1-0000", name: "ASET", type: "asset", is_postable: false, normal_balance: "debit" },
    { code: "6-4000", name: "Beban Listrik", type: "expense", is_postable: true, normal_balance: "debit", is_active: false },
  ];
  const panggilAkun = () => mockGet.mock.calls.filter(([u]) => String(u).endsWith("/gl/accounts"));

  test("satu PT di bilah atas → bagan PT itu; deret chip lingkup hilang; Template Global = pilihan dropdown", async () => {
    routeGet({ "/gl/accounts": ACCOUNTS });
    const host = await mount(<ChartOfAccounts entities={ENTS} currentUser={ADMIN} selectedEntity="ent_ksc" />);
    expect(q(host, "coa-scope-tabs")).toBeNull();
    expect(q(host, "coa-scope-ent_kanda")).toBeNull();
    expect(panggilAkun().at(-1)[1]).toEqual({ params: { entity_id: "ent_ksc" } });
    expect(q(host, "coa-title").textContent).toContain("Sukacita");
    expect(q(host, "coa-badge-override-1-1200").className).toContain("kn-badge");   // lencana baku, bukan ungu buatan
    const scope = q(host, "coa-scope");
    expect([...scope.options].map((o) => o.textContent)).toEqual(["Bagan Sukacita", "Template Global"]);
    expect(q(host, "coa-toolbar").contains(scope)).toBe(true);
    await pilih(scope, "global");
    expect(panggilAkun().at(-1)[1]).toEqual({ params: {} });
    expect(q(host, "coa-title").textContent).toContain("Template Global");
  });

  test("'Semua PT' → Template Global tanpa dropdown lingkup; kartu angka = saringan cepat; satu tombol tambah", async () => {
    routeGet({ "/gl/accounts": ACCOUNTS });
    const host = await mount(<ChartOfAccounts entities={ENTS} currentUser={ADMIN} selectedEntity="all" />);
    expect(q(host, "coa-scope")).toBeNull();
    expect(panggilAkun().at(-1)[1]).toEqual({ params: {} });
    expect(q(host, "coa-title").textContent).toContain("Template Global");
    expect(q(host, "coa-toolbar-count").textContent).toBe("4 akun");
    await click(q(host, "coa-kpi-postable"));
    expect(q(host, "coa-toolbar-count").textContent).toBe("3 akun");
    expect(q(host, "coa-row-1-0000")).toBeNull();
    await click(q(host, "coa-kpi-inactive"));
    expect(q(host, "coa-toolbar-count").textContent).toBe("1 akun");
    expect(q(host, "coa-row-6-4000")).not.toBeNull();
    await click(q(host, "coa-kpi-inactive"));   // klik lagi → semua
    expect(q(host, "coa-toolbar-count").textContent).toBe("4 akun");
    expect(host.querySelectorAll('[data-testid="coa-add-toggle"]')).toHaveLength(1);
    expect(q(host, "coa-toolbar").contains(q(host, "coa-add-toggle"))).toBe(true);
    expect(q(host, "coa-scope-note")).toBeNull();   // bilah penjelasan permanen → ikon ?
  });
});

// ── M40 — Lembar Insentif ───────────────────────────────────────────────────────────────────────────────────────────
describe("M40 — Lembar Insentif: satu bilah daftar", () => {
  test("judul satu baris + ?, status = dropdown (bukan chip), tombol buat di bilah daftar", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view", "prepare"] }, view_resources: {},
      hidden_views: [], view_actions: {} });
    mockGet.mockResolvedValue({ data: { total: 0, items: [] } });
    const host = await mount(
      <EntityScopeProvider selectedEntity="ent_kanda" entities={[{ id: "ent_kanda", short_name: "Kanda" }]} canSwitch>
        <AppNavProvider role="manager"><IncentiveSheetsView /></AppNavProvider>
      </EntityScopeProvider>);
    expect(q(host, "isheets-header")).not.toBeNull();
    expect(host.textContent).not.toContain("Nominal diketik orang");   // paragraf → ikon ?
    expect(q(host, "isheets-status").tagName).toBe("SELECT");
    expect(host.querySelector('[data-testid^="isheets-status-"]')).toBeNull();   // deret chip status dicabut
    const bar = q(host, "isheets-filters");
    ["isheets-search", "isheets-period", "isheets-status", "isheets-create"].forEach((id) => expect(bar.contains(q(host, id))).toBe(true));
    await pilih(q(host, "isheets-status"), "submitted");
    expect(mockGet.mock.calls.at(-1)[1].params.status).toBe("submitted");
  });
});
