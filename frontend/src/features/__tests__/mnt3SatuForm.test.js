// MN-T3 — satu form pembayaran, kartu pelanggan, kartu pemasok, telusur angka (docs/blueprint/unit/MN-T3.md).
// Uji komponen: U1 (langkah Pilih pelanggan / alokasi pesanan), U2 (konfirmasi N5 + satu POST ber-kunci, isi = berkas
// bersama `mnt3_isi_form.json`), U4b (isi form B = berkas bersama), U5 (Semua PT → tombol mati + petunjuk), U15 (13
// peran bawaan: bagian kartu = izin; tidak ada GET tanpa izin), U16 (telusur Neraca Saldo · Anggaran · Konsolidasi).
// U6 dan U7 (serah-terima b) di bagian bawah berkas.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
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
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
    onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: () => Promise.resolve({ direction: "none" }),
  directionMeta: () => ({ label: "", bg: "", fg: "" }), varianceMeta: () => Promise.resolve({ reasons: [] }),
  varianceKindMeta: () => ({ label: "", bg: "", fg: "" }), penaltyMeta: () => ({ label: "", bg: "", fg: "" }),
  money: (n) => String(n),
}));
jest.mock("../finance/payments/PenaltyPanel", () => () => <div data-testid="stub-penalty-panel" />);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/RecordDetailModal", () => () => null);
jest.mock("../../components/StoreCreditBadge", () => () => null);
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});

/* eslint-disable import/first */
import ReceivePaymentModal from "../finance/payments/ReceivePaymentModal";
import PaySupplierModal from "../finance/payments/PaySupplierModal";
import Customer360Panel from "../crm/Customer360Panel";
import Supplier360Panel from "../purchasing/Supplier360Panel";
import { TrialBalanceTab } from "../finance/GeneralLedgerTabs";
import BudgetView from "../finance/BudgetView";
import GroupConsolidationView from "../finance/GroupConsolidationView";
import { traceDecision } from "../finance/traceLedger";
import { invalidatePaymentMethods } from "../../config/paymentMethods";
import { can } from "../../config/roles";
import BUILTIN from "../../config/__tests__/fixtures/access_builtin_fixture.json";
import ISI from "../finance/payments/__tests__/fixtures/mnt3_isi_form.json";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" },
  { id: "ent_kanda", short_name: "Kanda", legal_name: "CV Kanda Suka" }];
const M = (code, name, need = "bank") => ({ code, name, needs_account: need, needs_reference: need === "bank", needs_due_date: false });
const MASUK = [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas")];
const REK = { id: "rek_a", name: "BCA Operasional", bank_name: "BCA", account_number: "777-000-0303", holder_name: "PT KSC", is_default: true };
const SO = { order_id: "so1", number: "KSC/SO-0001", outstanding: 8000000 };
const ADMIN = { id: "u1", role: "admin", permissions: BUILTIN.permissions.admin };
const nbsp = (s) => String(s || "").replace(/ /g, " ");

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 10) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el, { selectedEntity = "ent_ksc", nav = {} } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <AppNavProvider role="admin" onNavigateTo={nav.onNavigateTo} onOpenDocument={nav.onOpenDocument}>
        <EntityScopeProvider selectedEntity={selectedEntity} entities={ENT} canSwitch>{el}<ConfirmHost /></EntityScopeProvider>
      </AppNavProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush(3);
}
async function pick(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg, url) : v });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  document.body.innerHTML = "";
});

const terimaGet = (extra = {}) => ({
  "/payment-methods": MASUK, "/ar-receipts/open-orders": [SO], "/ar-receipts/deposit": {},
  "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "transfer" ? [REK] : []),
  "/settings/effective": { payment: { wajib_nomor_referensi: false } }, "/cash-holdings/me/summary": {},
  "/customers": [{ id: "c1", name: "Toko C", code: "TC" }, { id: "c2", name: "Toko D", code: "TD" }], ...extra });

// ── U1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("U1 — tanpa customerId: langkah Pilih pelanggan; dengan preselectOrderId: alokasi terisi untuk pesanan itu", async () => {
  routeGet(terimaGet());
  await mount(<ReceivePaymentModal onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-pick-customer")).not.toBeNull();
  expect(q("ar-receipt-pick-customer").textContent).toContain("Pelanggan");
  expect(q("ar-receipt-amount")).toBeNull();                         // isian lain belum tampil
  expect(q("ar-receipt-submit").disabled).toBe(true);
  await pick(q("ar-receipt-customer"), "c1");
  expect(q("ar-receipt-pick-customer")).toBeNull();
  expect(q("ar-receipt-customer-name").textContent).toContain("Toko C");
  await act(async () => { roots[0].unmount(); }); roots = []; document.body.innerHTML = "";

  routeGet(terimaGet());
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko C" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-mode-manual").getAttribute("aria-pressed")).toBe("true");   // "Atur sendiri"
  expect(q("ar-receipt-alloc-so1").value.replace(/\D/g, "")).toBe("8000000");
  expect(q("ar-receipt-order-focus")).not.toBeNull();
});

// ── U2 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("U2 — konfirmasi memuat nominal, pelanggan, rekening, PT; klik ganda → tepat satu POST ber-Idempotency-Key; isi = berkas bersama", async () => {
  routeGet(terimaGet());
  mockPost.mockResolvedValue({ data: { id: "arc_1", number: "AR-1", amount: 5000000, applied_total: 5000000 } });
  const onDone = jest.fn();
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko C" onClose={() => {}} onDone={onDone} />);
  await type(q("ar-receipt-amount"), "5000000");
  expect(q("ar-receipt-account").value).toBe("rek_a");
  await type(q("ar-receipt-reference"), ISI.terima.reference_no);
  await type(q("ar-receipt-notes"), ISI.terima.notes);
  expect(nbsp(q("ar-receipt-submit").textContent)).toBe("Simpan kwitansi");
  await click(q("ar-receipt-submit"));
  await click(q("ar-receipt-submit"));                               // klik ganda cepat
  expect(mockPost).not.toHaveBeenCalled();
  const pesan = nbsp(q("ar-receipt-confirm-message").textContent);
  expect(pesan).toContain("Rp 5.000.000");
  expect(pesan).toContain("Toko C");
  expect(pesan).toContain("BCA");
  expect(pesan).toContain("Sukacita");
  expect(pesan).toMatch(/^Catat penerimaan Rp 5\.000\.000 dari Toko C ke .+ untuk Sukacita\?$/);
  expect(q("ar-receipt-confirm-confirm").textContent).toBe("Ya, simpan");
  await click(q("ar-receipt-confirm-confirm"));
  await flush();
  const posts = mockPost.mock.calls.filter(([u]) => u === "/api/ar-receipts");
  expect(posts).toHaveLength(1);
  expect(posts[0][2].headers["Idempotency-Key"]).toBeTruthy();
  const body = posts[0][1];
  const harap = { ...ISI.terima, customer_id: "c1", account_id: "rek_a", receipt_date: body.receipt_date };
  expect(body).toEqual(harap);
  expect(Object.keys(body)).toEqual(Object.keys(ISI.terima));
  expect(onDone).toHaveBeenCalledTimes(1);
});

// ── U4b — isi form B = berkas bersama (dikirim lapis B ke pintu tagihan & kontrabon) ─────────────────────────────────
test("U4b — form Bayar pemasok: konfirmasi N5 + satu POST ke pintu tagihan; isi = berkas bersama", async () => {
  routeGet({ "/payment-methods": MASUK, "/vendor-bills/vb1": { id: "vb1", bill_number: "VB-1", supplier_name: "Pemasok S",
    entity_id: "ent_ksc", status: "posted", financials: { outstanding: 7000000 } },
  "/ap-payments/accounts": [REK], "/ap-payments/pending": null });
  mockPost.mockResolvedValue({ data: { id: "vb1", status: "paid", payments: [] } });
  const onPaid = jest.fn();
  await mount(<PaySupplierModal target={{ type: "vendor_bill", id: "vb1" }} onClose={() => {}} onPaid={onPaid} />);
  expect(nbsp(q("pay-supplier-outstanding").textContent)).toBe("Rp 7.000.000");
  expect(q("pay-supplier-supplier").textContent).toBe("Pemasok S");
  await pick(q("pay-supplier-account"), "rek_a");
  await type(q("pay-supplier-notes"), ISI.bayar.notes);
  await click(q("pay-supplier-submit"));
  await click(q("pay-supplier-submit"));
  expect(nbsp(q("pay-supplier-confirm-message").textContent))
    .toMatch(/^Bayar Rp 7\.000\.000 ke Pemasok S dari BCA Operasional · BCA · 777-000-0303 untuk Sukacita\?$/);
  expect(q("pay-supplier-confirm-confirm").textContent).toBe("Ya, bayar");
  await click(q("pay-supplier-confirm-confirm"));
  const posts = mockPost.mock.calls.filter(([u]) => u === "/api/vendor-bills/vb1/pay");
  expect(posts).toHaveLength(1);
  expect(posts[0][2].headers["Idempotency-Key"]).toBeTruthy();
  expect(posts[0][1]).toEqual({ ...ISI.bayar, bank_account_id: "rek_a", paid_at: posts[0][1].paid_at });
  expect(Object.keys(posts[0][1])).toEqual(Object.keys(ISI.bayar));
  expect(onPaid).toHaveBeenCalledTimes(1);
});

// ── U5 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("U5 — Semua PT: tombol simpan dan bayar mati dengan petunjuknya", async () => {
  routeGet(terimaGet());
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko C" onClose={() => {}} onDone={() => {}} />,
    { selectedEntity: "all" });
  await type(q("ar-receipt-amount"), "5000000");
  expect(q("ar-receipt-submit").disabled).toBe(true);
  expect(q("ar-receipt-scope-note").textContent).toBe("Pilih satu PT untuk mencatat pembayaran.");
  await act(async () => { roots[0].unmount(); }); roots = []; document.body.innerHTML = "";

  routeGet({ "/payment-methods": MASUK, "/contra-bons/cb1": { id: "cb1", number: "CB-1", supplier_name: "Pemasok S",
    entity_id: "ent_ksc", status: "approved", totals: { outstanding: 4000000 }, payments: [] },
  "/ap-payments/accounts": [REK], "/ap-payments/pending": null });
  await mount(<PaySupplierModal target={{ type: "contra_bon", id: "cb1" }} onClose={() => {}} onPaid={() => {}} />,
    { selectedEntity: "all" });
  expect(q("pay-supplier-submit").disabled).toBe(true);
  expect(q("pay-supplier-scope-note").textContent).toBe("Pilih satu PT untuk mencatat pembayaran.");
  expect(mockPost).not.toHaveBeenCalled();
});

// ── U15 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
// Cermin tabel bagian server (`services/party_card.py`): bagian → izin (salah satu cukup).
const C_SEC = [["ringkasan", [["payment_plan", "view"], ["credit_profile", "view"]]], ["tagihan", [["payment_plan", "view"]]],
  ["pembayaran", [["ar_receipt", "view"]]], ["denda_kasus", [["penalty", "view"], ["finance_case", "view"]]],
  ["tindak_lanjut", [["order", "view"]]], ["rekening_koran", [["credit_profile", "view"], ["ar_receipt", "view"]]],
  ["riwayat", [["order", "view"]]]];
const S_SEC = [["ringkasan", [["vendor_bill", "view"]]], ["tagihan", [["vendor_bill", "view"]]], ["kontrabon", [["contra_bon", "view"]]],
  ["pembayaran", [["vendor_bill", "view"]]], ["retur", [["purchase_return", "view"]]],
  ["po_biaya", [["purchase_order", "view"], ["landed_cost", "view"]]], ["lainnya", [["supplier", "view"]]]];
const secOf = (perms, table) => table.filter(([, izin]) => izin.some(([r, a]) => can(perms, r, a))).map(([k]) => k);
// Endpoint GET yang boleh dipanggil kartu → izin (salah satu cukup).
const GET_IZIN = [
  [/\/customers\/[^/]+\/360$/, [["customer", "view"]]], [/\/customers\/[^/]+\/exposure$/, [["customer", "view"], ["credit_profile", "view"]]],
  [/\/customers\/[^/]+\/balance$/, [["payment_plan", "view"], ["credit_profile", "view"]]],
  [/\/customers\/[^/]+\/billing-schedule$/, [["payment_plan", "view"]]], [/\/penalties$/, [["penalty", "view"]]],
  [/\/finance-cases$/, [["finance_case", "view"]]], [/\/ar-receipts(\/deposit)?$/, [["ar_receipt", "view"]]],
  [/\/store-credit\/ledger$/, [["ar_receipt", "view"]]], [/\/customers\/[^/]+\/statement$/, [["credit_profile", "view"], ["ar_receipt", "view"]]],
  [/\/suppliers\/[^/]+\/(360|price-list|scorecard)$/, [["supplier", "view"]]], [/\/products$/, [["product", "view"]]],
  [/\/audit/, [["audit", "view"]]],
];
function izinGet(perms) {
  const salah = [];
  for (const [url] of mockGet.mock.calls) {
    const path = url.replace(/^\/api/, "").split("?")[0];
    const aturan = GET_IZIN.find(([re]) => re.test(path));
    if (!aturan) continue;
    if (!aturan[1].some(([r, a]) => can(perms, r, a))) salah.push(path);
  }
  return salah;
}
const LABEL_C = { tagihan: "Tagihan & Jadwal", pembayaran: "Pembayaran", denda_kasus: "Denda & Kasus", tindak_lanjut: "Tindak Lanjut",
  rekening_koran: "Rekening Koran", riwayat: "Riwayat Lain" };
const LABEL_S = { tagihan: "Tagihan", kontrabon: "Kontrabon", pembayaran: "Pembayaran", retur: "Retur", po_biaya: "PO & Biaya Masuk", lainnya: "Lainnya" };

test.each(Object.keys(BUILTIN.permissions))("U15 — kartu pelanggan & pemasok, peran bawaan %s: bagian = izin; tanpa GET tanpa izin", async (role) => {
  const perms = BUILTIN.permissions[role];
  const user = { id: `u_${role}`, role, permissions: perms };
  const cs = secOf(perms, C_SEC);
  const ss = secOf(perms, S_SEC);
  routeGet({
    "/customers/c1/360": { id: "c1", name: "Toko C", entity_id: "ent_ksc", sections_allowed: cs, credit: cs.includes("ringkasan") ? { status: "active" } : null,
      order_history: [], document_history: [], special_price_history: [], sample_history: [], collection_followups: [], stats: {} },
    "/exposure": { rows: [{ key: "eksposur", amount: 100 }, { key: "plafon", amount: 500 }] },
    "/balance": { overdue_amount: 0, deposit_balance: 0, store_credit_balance: 0 },
    "/billing-schedule": { items: [], total: 0, totals: {} }, "/penalties": { items: [] }, "/finance-cases": [],
    "/ar-receipts/deposit": { deposit_balance: 0 }, "/ar-receipts": { items: [], total: 0 }, "/store-credit/ledger": [],
    "/statement": { rows: [], opening_balance: 0, closing_balance: 0 },
    "/suppliers/s1/360": { id: "s1", name: "Pemasok S", entity_id: "ent_ksc", status: "active", sections_allowed: ss,
      payables: ss.includes("ringkasan") ? { single_entity: true, outstanding: 0, due_soon: 0, advance: 0, due_soon_days: 7, by_entity: [] } : null,
      bills: ss.includes("tagihan") ? [] : null, payments: ss.includes("pembayaran") ? [] : null,
      contra_bons: ss.includes("kontrabon") ? [] : null, returns: ss.includes("retur") ? [] : null,
      purchase_orders: can(perms, "purchase_order", "view") ? [] : null, landed_costs: can(perms, "landed_cost", "view") ? [] : null,
      documents: [], price_history: [] },
    "/price-list": [], "/scorecard": { metrics: {} },
  });
  // Kartu hanya dibuka pemegang izin lihat (`CustomerCardLink`/`SupplierCardLink`): tanpa izin → nama teks biasa.
  if (can(perms, "customer", "view")) {
    await mount(<Customer360Panel variant="card" customerId="c1" currentUser={user} selectedEntity="ent_ksc" salesUsers={[]} onBack={() => {}} />);
    const chipsC = [...document.querySelectorAll("[data-testid^='customer-360-tab-']")].map((b) => b.textContent);
    expect(chipsC).toEqual(cs.filter((k) => LABEL_C[k]).map((k) => LABEL_C[k]));
    expect(Boolean(q("customer-card-head"))).toBe(cs.includes("ringkasan"));
    expect(Boolean(q("customer-360-receive"))).toBe(can(perms, "ar_receipt", "create"));
    for (const k of cs.filter((x) => LABEL_C[x])) await click(q(`customer-360-tab-${k}`));
    await act(async () => { roots[0].unmount(); }); roots = []; document.body.innerHTML = "";
  }

  if (can(perms, "supplier", "view")) {
    await mount(<Supplier360Panel variant="card" supplierId="s1" currentUser={user} selectedEntity="ent_ksc" onBack={() => {}} />);
    const chipsS = [...document.querySelectorAll("[data-testid^='supplier-360-tab-']")].map((b) => b.textContent.replace(/\d+$/, ""));
    expect(chipsS).toEqual(ss.filter((k) => LABEL_S[k]).map((k) => LABEL_S[k]));
    expect(Boolean(q("supplier-card-head"))).toBe(ss.includes("ringkasan"));
    for (const k of ss.filter((x) => LABEL_S[x])) await click(q(`supplier-360-tab-${k}`));
  }
  expect(izinGet(perms)).toEqual([]);
});

// ── U16 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("U16 — Neraca Saldo per 2026-02-28: klik baris akun → preset {tab: ledger, code, end}", async () => {
  routeGet({ "/gl/trial-balance": { rows: [{ code: "1-1100", name: "Kas", type_label: "Aset", debit_balance: 100, credit_balance: 0 }],
    total_debit: 100, total_credit: 100, balanced: true } });
  const onDrill = jest.fn();
  await mount(<TrialBalanceTab refreshKey={0} onError={() => {}} onDrill={onDrill} selectedEntity="ent_ksc" />);
  await type(q("gl-trial-asof"), "2026-02-28");
  expect(mockGet.mock.calls.some(([u, c]) => u.includes("/gl/trial-balance") && c?.params?.as_of === "2026-02-28")).toBe(true);
  await click(q("gl-trial-row-1-1100"));
  expect(onDrill).toHaveBeenCalledWith({ tab: "ledger", code: "1-1100", end: "2026-02-28" });
  // Semua PT → petunjuk, tidak membuka buku besar
  onDrill.mockClear();
  await act(async () => { roots[0].unmount(); }); roots = []; document.body.innerHTML = "";
  await mount(<TrialBalanceTab refreshKey={0} onError={() => {}} onDrill={onDrill} selectedEntity="all" />, { selectedEntity: "all" });
  await click(q("gl-trial-row-1-1100"));
  expect(onDrill).not.toHaveBeenCalled();
  expect(q("gl-trial-trace-notice").textContent).toContain("Pilih satu PT untuk menelusuri angka ini.");
});

test("U16 — Anggaran 2026: klik angka realisasi akun → buku besar 2026-01-01 s.d. 2026-12-31", async () => {
  const row = { id: "b1", key: "6-1000", label: "Beban Gaji", dimension: "account", entity_id: "ent_ksc", budget: 100, committed: 0,
    actual: 40, remaining: 60, spent_pct: 40, used_pct: 40, status: "ok", month: 0 };
  routeGet({ "/finance/budget-vs-actual": { totals: {}, rows: [row], by_dimension: {} }, "/finance/budget-rules": null,
    "/finance/budget-keys": {} });
  const onNavigateTo = jest.fn();
  await mount(<BudgetView selectedEntity="ent_ksc" currentUser={ADMIN} />, { nav: { onNavigateTo } });
  const tahun = q("budget-year").value || String(new Date().getFullYear());
  await click(q("budget-trace-6-1000"));
  expect(onNavigateTo).toHaveBeenCalledWith("general-ledger", { preset: { tab: "ledger", code: "6-1000",
    start: `${tahun}-01-01`, end: `${tahun}-12-31`, from: { view: "budget" } }, tab: undefined, navId: undefined });
  expect(traceDecision({ code: "6-1000", range: { start: "2026-01-01", end: "2026-12-31" }, selectedEntity: "ent_ksc" }).preset)
    .toEqual({ tab: "ledger", code: "6-1000", start: "2026-01-01", end: "2026-12-31" });
});

test("U16 — Konsolidasi: angka PT lain → petunjuk pindah PT; PT aktif → Laporan Keuangan PT itu", async () => {
  const e = (id, short) => ({ entity_id: id, short_name: short, entity_name: short, revenue: 1000, cogs: 400, opex: 100,
    expense: 500, gross_profit: 600, net_income: 500, assets: 0, liabilities: 0, equity: 0, ownership_pct: 100 });
  routeGet({ "/finance/consolidation/summary": { entities: [e("ent_ksc", "Sukacita"), e("ent_kanda", "Kanda")],
    elimination: {}, consolidated: {} }, "/finance/consolidation/eliminations": [], "/gl/accounts": [] });
  const onNavigateTo = jest.fn();
  await mount(<GroupConsolidationView entities={ENT} />, { nav: { onNavigateTo } });
  await click(q("cons-trace-revenue-ent_kanda"));
  expect(q("cons-trace-notice").textContent).toContain("Pindah ke Kanda untuk menelusuri angka ini.");
  expect(onNavigateTo).not.toHaveBeenCalled();
  expect(q("cons-trace-net_income-ent_ksc")).toBeNull();            // baris laba bersih tidak bisa diklik
  await click(q("cons-trace-revenue-ent_ksc"));
  expect(onNavigateTo).toHaveBeenCalledWith("financial-statements", expect.objectContaining({
    preset: expect.objectContaining({ tab: "pl", start: expect.stringMatching(/-01-01$/), end: expect.stringMatching(/-12-31$/) }) }));
});
